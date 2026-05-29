"""Export a local optimisation candidate audit for the shear-governing terminal case.

This is an investigation tool only. It reads browser-live verifier evidence and
source-code structure; it does not call production solvers or mutate app state.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
CASE_ID = "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _latest_real_user_artifact() -> Path:
    candidates = sorted(
        REPO.glob("real_user_design_guide_ladder_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            data = _load_json(path)
        except Exception:
            continue
        if any(str(case.get("case_id")) == CASE_ID for case in data.get("cases") or []):
            return path
    raise FileNotFoundError(f"no real-user artifact contains {CASE_ID}")


def _case_from_artifact(path: Path) -> dict[str, Any]:
    data = _load_json(path)
    for case in data.get("cases") or []:
        if str(case.get("case_id")) == CASE_ID:
            return dict(case)
    raise KeyError(CASE_ID)


def _inventory_row(source: str, candidate: dict[str, Any], *, selected: bool = False) -> dict[str, Any]:
    updates = dict(
        candidate.get("proposed_updates")
        or candidate.get("updates")
        or candidate.get("selected_candidate_updates")
        or {}
    )
    overview = dict(candidate.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    return {
        "candidate_id": candidate.get("candidate_id") or candidate.get("selected_candidate_id"),
        "source_generator": source,
        "family_affected": candidate.get("family") or candidate.get("candidate_family") or _family_from_updates(updates),
        "action_type": candidate.get("action_type"),
        "proposed_updates": updates,
        "expected_bending_util": _nested_get(overview, "utils", "bending"),
        "expected_shear_util": _nested_get(overview, "utils", "shear"),
        "expected_worst_or_governing_util": candidate.get("preview_util")
        or candidate.get("candidate_post_util")
        or candidate.get("worst_util"),
        "expected_status": "PASS" if candidate.get("safe_executor_backed") else "REJECTED",
        "commit_eligible": bool(candidate.get("safe_executor_backed")),
        "one_click_resolved": bool(candidate.get("safe_executor_backed") and updates),
        "selected": bool(selected),
        "rejected": not bool(selected),
        "rejection_reasons": [
            value
            for value in (
                candidate.get("rejection_category"),
                candidate.get("rejection_reason"),
            )
            if value
        ],
        "internal_bad_update_keys": candidate.get("internal_bad_update_keys"),
        "candidate_preview_has_fail_status": bool(
            any(str(value).upper() == "FAIL" for value in statuses.values())
            or candidate.get("failed_check_status") == "FAIL"
        ),
        "preview_fail_keys": [
            key for key, value in statuses.items() if str(value).upper() == "FAIL"
        ],
        "preview_status_by_family": statuses,
        "preview_phiMu": _nested_get(overview, "packs", "bending", "summary_phiMu_kNm"),
        "preview_phiVu": _nested_get(overview, "packs", "shear", "summary_phiVu_kN"),
        "preview_required_Ast": _nested_get(overview, "packs", "bending", "required_Ast_mm2"),
        "preview_Ast_provided": _nested_get(overview, "packs", "bending", "bending_pos", "Ast_tension_mm2"),
        "preview_ductility_status": statuses.get("ductility"),
        "preview_crack_status": statuses.get("crack"),
        "preview_deflection_status": statuses.get("deflection"),
        "preview_detailing_status": statuses.get("detailing") or statuses.get("spacing_detailing"),
    }


def _nested_get(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _family_from_updates(updates: dict[str, Any]) -> str:
    keys = set(updates)
    if keys & {"lig_d", "lig_legs", "s_lig"}:
        return "shear"
    if keys & {"bot1_count", "db_bot_1", "bot_row_1_bars", "bot_row_1_dia", "nb_bot", "db_bot"}:
        return "bending"
    if keys & {"b", "bw", "D"}:
        return "geometry"
    return "other"


def _candidate_inventory(case: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = dict(case.get("candidate_search_evidence") or {})
    rows: list[dict[str, Any]] = []
    selected_id = evidence.get("selected_candidate_id")
    for key, source in (
        ("target_band_candidates", "engine_target_band_candidates"),
        ("safe_executor_backed_candidates", "engine_safe_executor_backed_candidates"),
        ("rejected_target_band_candidates", "engine_rejected_target_band_candidates"),
        ("local_cleanup_candidates", "engine_safe_local_cleanup_candidates"),
    ):
        for candidate in evidence.get(key) or []:
            rows.append(_inventory_row(source, dict(candidate), selected=str(candidate.get("candidate_id")) == str(selected_id)))
    if not rows:
        selected_candidate = {
            "candidate_id": evidence.get("selected_candidate_id"),
            "title": evidence.get("selected_candidate_title"),
            "proposed_updates": evidence.get("selected_candidate_updates") or {},
            "preview_util": evidence.get("selected_candidate_util"),
            "rejection_category": "no_candidate_generated",
            "rejection_reason": "engine received no material cleanup candidate rows",
        }
        rows.append(_inventory_row("engine_selected_placeholder", selected_candidate, selected=False))
    return rows


def _rejection_summary(inventory: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in inventory:
        reasons = list(row.get("rejection_reasons") or [])
        if not reasons and row.get("rejected"):
            reasons = ["no_candidate_generated"]
        for reason in reasons:
            counter[str(reason)] += 1
    for reason in case.get("local_cleanup_blocked_reasons") or []:
        counter[str(reason)] += 1
    if not counter:
        counter["no_candidate_generated"] += 1
    return dict(counter)


def _space_audit(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = dict(case.get("candidate_search_evidence") or {})
    total = int(evidence.get("total_candidates_considered") or 0)
    return {
        "reduce_bottom_bar_count": {
            "attempted": False,
            "generator_function": "_generate_local_bottom_arrangements / _direct_target_band_guidance_item",
            "number_of_candidates": 0,
            "why_not_attempted": "Direct bottom target-band search is only inserted by _maybe_promote_safe_local_cleanup_primary when current_worst < target_low. This case has current_worst inside target band, so the direct tightening item is not created.",
        },
        "reduce_bottom_bar_diameter": {
            "attempted": False,
            "generator_function": "_generate_local_bottom_arrangements / _direct_target_band_guidance_item",
            "number_of_candidates": 0,
            "why_not_attempted": "Same gate as bottom count: in-target governing utilisation short-circuits the direct bottom arrangement search.",
        },
        "reduce_section_depth_D": {
            "attempted": False,
            "generator_function": "_direct_target_band_guidance_item geometry loop",
            "number_of_candidates": 0,
            "why_not_attempted": "The geometry target-band search is not invoked for in-target terminal states because current_worst is not below target_low.",
        },
        "reduce_section_width_b": {
            "attempted": False,
            "generator_function": "_direct_target_band_guidance_item geometry loop",
            "number_of_candidates": 0,
            "why_not_attempted": "The geometry target-band search is not invoked for in-target terminal states because current_worst is not below target_low.",
        },
        "reduce_geometry_and_reinforcement_together": {
            "attempted": False,
            "generator_function": "_direct_target_band_guidance_item combined geometry + bottom loop",
            "number_of_candidates": 0,
            "why_not_attempted": "Combined trials exist in code but are behind the below-target/direct-tightening path; they are not run once the governing util is in target.",
        },
        "adjust_top_reinforcement_if_not_needed": {
            "attempted": False,
            "generator_function": None,
            "number_of_candidates": 0,
            "why_not_attempted": "No Design Guide local cleanup path found for top reinforcement in this contract path.",
        },
        "preserve_shear_capacity_while_reducing_bending_capacity": {
            "attempted": False,
            "generator_function": None,
            "number_of_candidates": 0,
            "why_not_attempted": "The engine only received the terminal no-action item; no bottom-only cleanup preserving shear was generated or passed through.",
        },
        "reduce_bending_reserve_without_changing_shear_links": {
            "attempted": False,
            "generator_function": "_direct_target_band_guidance_item bottom-only trials",
            "number_of_candidates": 0,
            "why_not_attempted": "Bottom-only trials are inside the direct target-band search path, which was not invoked for an in-target governing utilisation.",
        },
        "trial_combinations_rather_than_one_hop_single_parameter_moves": {
            "attempted": False,
            "generator_function": "_direct_target_band_guidance_item",
            "number_of_candidates": 0,
            "why_not_attempted": "The combination search exists but is not called for this in-target terminal state.",
        },
        "terminal_placeholder_only": {
            "attempted": True,
            "generator_function": "resolve_design_guide_decision / terminal already-efficient item",
            "number_of_candidates": total,
            "why_not_attempted": None,
        },
    }


def _best_rejected(inventory: list[dict[str, Any]], summary: dict[str, int]) -> dict[str, Any]:
    cleanup_rows = [row for row in inventory if row.get("family_affected") in {"bending", "geometry"}]
    if cleanup_rows:
        row = cleanup_rows[0]
        return {
            "candidate_id": row.get("candidate_id"),
            "proposed_updates": row.get("proposed_updates"),
            "what_improved": "candidate touched bending/geometry",
            "exact_reason_rejected": row.get("rejection_reasons"),
            "likely_secondary_update_to_make_safe": None,
            "failure_type": "candidate_contract_or_preview",
        }
    return {
        "candidate_id": None,
        "proposed_updates": {},
        "what_improved": None,
        "exact_reason_rejected": "No bending/geometry cleanup candidate was generated or passed into the engine. The only rejected row is the terminal no-action placeholder with empty updates.",
        "likely_secondary_update_to_make_safe": "Run a dedicated in-target local cleanup generator that enumerates bottom-only, geometry-only, and combined geometry+bottom candidates, then preview each against shear/serviceability/detailing.",
        "failure_type": "candidate_generation_search_space_gap",
        "rejection_reason_summary": summary,
    }


def main() -> int:
    artifact = _latest_real_user_artifact()
    case = _case_from_artifact(artifact)
    inventory = _candidate_inventory(case)
    rejection_summary = _rejection_summary(inventory, case)
    audit = {
        "case_id": CASE_ID,
        "source_artifact": str(artifact),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "starting_state": {
            "intended_inputs": case.get("intended_inputs"),
            "visible_inputs_before": case.get("visible_inputs_before"),
            "visible_summary_before": case.get("visible_summary_before"),
            "button_contract": case.get("button_contract"),
        },
        "family_utils": dict(case.get("family_utils") or {}),
        "materially_overprovided_families": list(case.get("materially_overprovided_families") or []),
        "candidate_inventory": inventory,
        "candidate_space_audit": _space_audit(case),
        "rejection_reason_summary": rejection_summary,
        "best_rejected_candidate": _best_rejected(inventory, rejection_summary),
        "missing_candidate_families": [
            "bottom_reinforcement_only_cleanup",
            "geometry_only_cleanup",
            "combined_geometry_and_bottom_reinforcement_cleanup",
            "top_reinforcement_cleanup",
            "in_target_local_cleanup_combination_search",
        ],
        "source_path_diagnosis": {
            "_maybe_promote_safe_local_cleanup_primary": "Evaluates collapsed guidance items, optional direct tightening only when current_worst < target_low, and shear cleanup only when shear cleanup is needed.",
            "_direct_target_band_guidance_item": "Contains geometry, bottom, shear, and combined candidate loops, but it is not called for this in-target governing state.",
            "resolve_design_guide_decision": "Receives raw_candidates=list(collapsed_guidance_items), which for this case is only the terminal item.",
        },
        "recommended_next_patch": {
            "classification": "generator/search-space problem, not formula/ranking/apply problem",
            "summary": "Add a dedicated in-target non-governing local cleanup generator before terminal no-action. It should enumerate bottom-only, geometry-only, and combined geometry+bottom cleanup candidates for materially overprovided families and pass the full raw candidate set to design_guidance_engine.",
            "safety_contract": [
                "preview each candidate from fresh derived state",
                "require all required statuses PASS",
                "reject internal_bad_update_keys and partial failing final updates",
                "preserve shear/serviceability/ductility/detailing",
                "only block terminal when safe_local_cleanup_count > 0",
            ],
        },
    }
    out = REPO / "tools" / f"local_optimisation_candidate_audit_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    out.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(out), "candidate_count": len(inventory), "missing_candidate_families": audit["missing_candidate_families"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
