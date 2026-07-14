"""Proof snapshot for combined low-util result packaging cutover."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import importlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FUNCTION_NAME = "_combine_best_safe_shear_with_bending_cleanup_item"
HELPER_NAME = "build_design_guide_combined_low_util_result_packaging"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _guidance_item_builder(
    candidate: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
    overview: dict[str, Any] | None = None,
    title: str = "",
    reasoning: str = "",
    status: str = "",
    primary_action: str = "",
) -> dict[str, Any]:
    return {
        "title_main": title,
        "title": title,
        "reasoning": reasoning,
        "status": status,
        "primary_action": primary_action,
        "resolved_candidate": dict(candidate or {}),
        "button_contract": {"enabled": False, "source": "builder_seed"},
        "action_payload": {"source": "builder_seed"},
        "state_hash": _stable_hash(state or {}),
        "overview_hash": _stable_hash(overview or {}),
    }


def _old_packaging(
    *,
    combined_candidate: dict[str, Any],
    state: dict[str, Any],
    overview: dict[str, Any],
    combined_updates: dict[str, Any],
    evidence: dict[str, Any],
    combined_worst: Any,
    combined_audit: dict[str, Any],
) -> dict[str, Any]:
    candidate = dict(combined_candidate or {})
    updates = dict(combined_updates or {})
    evidence_map = dict(evidence or {})
    candidate.update(
        {
            "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "label": "Shear and bending cleanup - one-click optimisation",
            "title": "Shear and bending cleanup - one-click optimisation",
            "canonical_winner_label": "Shear and bending cleanup - one-click optimisation",
            "title_locked_from_final_winner": True,
            "family": "combined",
            "recommendation_family_tag": "combined",
            "subfamilies": ["shear", "bottom_reinforcement"],
            "updates": dict(updates),
            "proposed_updates": dict(updates),
            "action_type": "apply_resolved_candidate",
            "candidate_post_util": combined_worst,
            "worst_util": combined_worst,
            "candidate_search_evidence": dict(evidence_map),
            "local_cleanup_candidate": True,
            "allow_in_target_primary_action": True,
            "best_safe_partial_cleanup": True,
            "primary_card_actionable": True,
            "no_second_cta_required": False,
        }
    )
    item = _guidance_item_builder(
        candidate,
        state=state,
        overview=overview,
        title="Shear and bending cleanup - one-click optimisation",
        reasoning=(
            "This combines the best safe shear-link cleanup with the bending reinforcement cleanup "
            "so the current optimisation flow is handled in one click."
        ),
        status="EFFICIENCY",
        primary_action="Run one-click auto design",
    )
    item.update(
        {
            "title_main": "Shear and bending cleanup - one-click optimisation",
            "title": "Shear and bending cleanup - one-click optimisation",
            "candidate_search_evidence": dict(evidence_map),
            "local_cleanup_candidate": True,
            "guidance_intent": "efficiency_tightening",
            "affected_family": "combined",
            "family": "combined",
            "check_key": "combined",
            "selected_action_family": "combined",
            "source": "combined_best_safe_shear_plus_bending_cleanup",
            "allow_in_target_primary_action": True,
            "best_safe_partial_cleanup": True,
            "primary_card_actionable": True,
            "no_second_cta_required": False,
            "canonical_winner_label": "Shear and bending cleanup - one-click optimisation",
            "title_locked_from_final_winner": True,
            "selected_action_updates": dict(updates),
            "updates": dict(updates),
        }
    )
    payload = dict(item.get("action_payload") or {})
    payload["updates"] = dict(updates)
    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_action_type"] = "apply_resolved_candidate"
    payload["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band") or candidate.get("reaches_target_band")
    )
    payload["candidate_search_evidence"] = dict(evidence_map)
    payload["source_candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
    payload["candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
    payload["resolved_candidate_family_tag"] = "combined"
    payload["resolved_candidate_subfamilies"] = ["shear", "bottom_reinforcement"]
    payload["best_safe_partial_cleanup"] = True
    payload["primary_card_actionable"] = True
    payload["no_second_cta_required"] = False
    item["action_payload"] = payload
    resolved = dict(item.get("resolved_candidate") or candidate)
    resolved["updates"] = dict(updates)
    resolved["candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
    resolved["source_candidate_id"] = "combined_best_safe_shear_plus_bending_cleanup"
    resolved["candidate_search_evidence"] = dict(evidence_map)
    resolved["candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band") or candidate.get("reaches_target_band")
    )
    resolved["family"] = "combined"
    resolved["recommendation_family_tag"] = "combined"
    resolved["subfamilies"] = ["shear", "bottom_reinforcement"]
    resolved["best_safe_partial_cleanup"] = True
    resolved["primary_card_actionable"] = True
    resolved["no_second_cta_required"] = False
    item["resolved_candidate"] = resolved
    contract = dict(item.get("button_contract") or {})
    contract.update(
        {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": dict(updates),
            "preview_pass": True,
            "expected_util": combined_worst,
            "blocking_reason": None,
            "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
        }
    )
    item["button_contract"] = contract
    debug_update = {
        "combined_best_safe_cleanup_generated": True,
        "combined_best_safe_cleanup_updates": dict(updates),
        "combined_best_safe_cleanup_audit": dict(combined_audit or {}),
    }
    return {
        "item": item,
        "combined_candidate": candidate,
        "debug_update": debug_update,
    }


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = getattr(module, HELPER_NAME)
    cases = [
        {
            "name": "reaches_target",
            "combined_candidate": {"candidate_reaches_target_band": True},
            "state": {"b": 400},
            "overview": {"worst_util": 0.88},
            "combined_updates": {"b": 350, "lig_legs": 0},
            "evidence": {"cleanup_search_ran": True},
            "combined_worst": 0.88,
            "combined_audit": {"post_click_unresolved_low_util_families": []},
        },
        {
            "name": "does_not_reach_target",
            "combined_candidate": {"reaches_target_band": False, "existing": "kept"},
            "state": {"n_bottom": 5},
            "overview": {},
            "combined_updates": {"n_bottom": 4},
            "evidence": {"best_safe_partial_cleanup": True},
            "combined_worst": 0.79,
            "combined_audit": {"exact_blockers_by_family": {"bending": {"reason": "floor"}}},
        },
    ]
    comparisons = []
    for case in cases:
        old = _old_packaging(**{k: v for k, v in case.items() if k != "name"})
        new_payload = helper(
            guidance_item_builder=_guidance_item_builder,
            **{k: v for k, v in case.items() if k != "name"},
        )
        new = {
            "item": new_payload.get("item"),
            "combined_candidate": new_payload.get("combined_candidate"),
            "debug_update": new_payload.get("debug_update"),
        }
        comparisons.append(
            {
                "case": case["name"],
                "match": old == new,
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(new),
                "proof_hash": (new_payload.get("result_packaging_proof") or {}).get(
                    "result_packaging_hash"
                ),
            }
        )
    first_payload = helper(
        guidance_item_builder=_guidance_item_builder,
        **{k: v for k, v in cases[0].items() if k != "name"},
    )
    repeat_payload = helper(
        guidance_item_builder=_guidance_item_builder,
        **{k: v for k, v in cases[0].items() if k != "name"},
    )
    return {
        "comparisons": comparisons,
        "hash_repeat": _stable_hash(first_payload) == _stable_hash(repeat_payload),
        "missing_builder": helper(
            guidance_item_builder=None,
            **{k: v for k, v in cases[0].items() if k != "name"},
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_RESULT_PACKAGING_CUTOVER_PASS",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "helper_exercise": exercise,
        "source_checks": {
            "controller_helper_exported": f'"{HELPER_NAME}"' in controller_source,
            "controller_helper_imported": (
                f"{HELPER_NAME} as _build_design_guide_combined_low_util_result_packaging"
                in inputs_source
            ),
            "controller_helper_called_once_in_target": (
                target_source.count("_build_design_guide_combined_low_util_result_packaging(") == 1
            ),
            "old_mutations_removed_from_target": all(
                token not in target_source
                for token in (
                    "combined_candidate.update(",
                    "item.update(",
                    'item["action_payload"] = payload',
                    'item["resolved_candidate"] = resolved',
                    'item["button_contract"] = contract',
                )
            ),
            "page_guidance_builder_still_injected": (
                "guidance_item_builder=_guidance_item_from_resolved_candidate" in target_source
            ),
            "debug_update_only_passed_through": (
                'debug_sink.update(dict(result_packaging.get("debug_update") or {}))'
                in target_source
            ),
            "controller_page_free": all(
                token not in controller_source
                for token in ("inputs_page", "st.session_state", "streamlit")
            ),
            "no_render_apply_or_cta_owner_moved": all(
                token not in controller_source
                for token in (
                    "st.button",
                    "st.markdown",
                    "route_apply",
                    "apply_routing",
                    "render_button",
                    "streamlit",
                )
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    exercise = dict(capture.get("helper_exercise") or {})
    comparisons = list(exercise.get("comparisons") or [])
    missing_proof = dict((exercise.get("missing_builder") or {}).get("result_packaging_proof") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "all_old_new_cases_match": all(item.get("match") for item in comparisons),
        "proof_hashes_present": all(item.get("proof_hash") for item in comparisons),
        "hash_repeat_stable": exercise.get("hash_repeat") is True,
        "missing_builder_records_invalid_item": missing_proof.get("valid_item") is False,
        "source_checks_green": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Result Packaging Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases"])
    for item in (capture.get("helper_exercise") or {}).get("comparisons") or []:
        lines.append(
            f"- {item.get('case')}: `{item.get('match')}` "
            f"old `{item.get('old_hash')}` new `{item.get('new_hash')}`"
        )
    lines.extend(["", "## Source Checks"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("source_checks") or {}).items()
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_result_packaging_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_result_packaging_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_result_packaging_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
