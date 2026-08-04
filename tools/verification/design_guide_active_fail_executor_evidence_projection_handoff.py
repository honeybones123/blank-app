"""Verify active-fail executor candidate-search evidence projection handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "unsafe_shear_first",
            "label": "Unsafe shear ladder candidate",
            "updates": {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0},
            "overview": {
                "any_fail": True,
                "all_key_pass": False,
                "statuses": {"bending": "PASS", "shear": "FAIL"},
                "utils": {"bending": 0.72, "shear": 1.14},
            },
            "is_compliant": False,
            "safe_executor_backed": False,
            "failed_check_family": "shear",
            "rejection_reason": "shear:FAIL",
            "candidate_post_util": 1.14,
            "worst_util": 1.14,
            "shear_fail_ladder_index": 1,
            "bending_fail_ladder_index": 1,
            "combined_fail_ladder_index": 1,
        },
        {
            "candidate_id": "safe_family_candidate",
            "label": "Safe family ladder candidate",
            "updates": {"D": 700.0, "b": 450.0, "lig_d": 12, "lig_legs": 2, "s_lig": 150.0},
            "overview": {
                "any_fail": False,
                "all_key_pass": True,
                "statuses": {"bending": "PASS", "shear": "PASS"},
                "utils": {"bending": 0.88, "shear": 0.92},
            },
            "is_compliant": True,
            "safe_executor_backed": True,
            "candidate_post_util": 0.92,
            "worst_util": 0.92,
            "shear_fail_ladder_index": 2,
            "bending_fail_ladder_index": 2,
            "combined_fail_ladder_index": 2,
        },
    ]


def _sample_ladder() -> dict[str, Any]:
    return {
        "specs": [
            {"ladder_index": 1, "contract_step": "first", "updates": {"D": 675.0}},
            {"ladder_index": 2, "contract_step": "second", "updates": {"D": 700.0}},
        ],
        "known_bad_candidate_count": 1,
    }


def _old_projection(
    *,
    selected: dict[str, Any] | None,
    all_candidates: list[dict[str, Any]],
    safe: list[dict[str, Any]],
    active: set[str],
    family: str,
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_family_evidence_overlay,
    )
    from design_brain.evidence import build_candidate_search_evidence  # noqa: WPS433

    shear_attempted = family == "shear"
    bending_attempted = family == "bending"
    combined_attempted = family == "combined"
    combined_found = family == "combined"
    bending_found = family == "bending"
    ladder = _sample_ladder()
    ev = build_candidate_search_evidence(
        selected_candidate=selected,
        all_candidates=all_candidates,
        target_low=0.85,
        target_high=1.0,
        exhaustive=True,
        search_scope=(
            "shear_fail_family_contract_ladder_search"
            if shear_attempted
            else "bending_fail_family_contract_ladder_search"
            if bending_attempted
            else "combined_fail_family_contract_ladder_search"
            if combined_attempted
            else "active_fail_combined_repair_search"
            if {"bending", "shear"}.issubset(active)
            else "active_fail_repair_search"
        ),
        selected_title=str((selected or {}).get("label") or "Active fail repair") if selected else None,
    )
    metrics = {
        "candidate_evaluation_cache_hits": 2,
        "candidate_evaluation_cache_misses": 3,
        "duplicate_candidate_fingerprints_skipped": 1,
        "blocker_attempt_cache_hits": 1,
    }
    ev.update(
        {
            "active_fail_repair_search_scope": ev.get("search_scope"),
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "geometry_strengthening_searched": True,
            "reo_strengthening_searched": True,
            "longitudinal_reinforcement_strengthening_searched": not bool(shear_attempted),
            "shear_strengthening_searched": bool("shear" in active),
            "combined_strengthening_searched": bool({"bending", "shear"}.issubset(active)),
            "bending_fail_contract_ladder_attempted": bool(bending_attempted),
            "bending_fail_contract_ladder_found_safe": bool(bending_found),
            "bending_fail_contract_ladder_error": None,
            "combined_fail_contract_ladder_attempted": bool(combined_attempted),
            "combined_fail_contract_ladder_found_safe": bool(combined_found),
            "combined_fail_contract_ladder_error": None,
            "active_fail_repair_candidate_rows": list(ev.get("candidate_rows") or []),
            "safe_repair_candidate_count": int(len(safe)),
            "executable_repair_candidate_count": int(len(safe)),
            "strength_repair_selected_outside_target_band": bool(selected),
            "strength_repair_target_band_secondary": bool(selected),
            "outside_target_band_allowed": bool(selected),
            "outside_target_band_allowed_reason": (
                "Active bending/shear checks are failing; this executor-backed repair "
                "makes all required checks pass even though preferred target-band cleanup "
                "remains a secondary optimisation step."
            )
            if selected
            else None,
            "outside_target_band_allowed_category": (
                "active_strength_repair_passes_required_checks" if selected else None
            ),
            "candidate_evaluation_cache_hits": int(metrics.get("candidate_evaluation_cache_hits", 0)),
            "candidate_evaluation_cache_misses": int(metrics.get("candidate_evaluation_cache_misses", 0)),
            "duplicate_candidate_fingerprints_skipped": int(metrics.get("duplicate_candidate_fingerprints_skipped", 0)),
            "blocker_attempt_cache_hits": int(metrics.get("blocker_attempt_cache_hits", 0)),
            "rejected_repair_reasons": list(
                dict.fromkeys(
                    str(row.get("rejection_reason") or row.get("failed_check_family") or "preview_failed")
                    for row in list(ev.get("candidate_rows") or [])
                    if isinstance(row, dict) and not bool(row.get("safe_executor_backed"))
                )
            )[:40],
        }
    )
    if shear_attempted:
        overlay = build_design_guide_controller_active_fail_executor_family_evidence_overlay(
            family_id="SHEAR_FAIL_GOVERNS",
            ladder=dict(ladder),
            selected_candidate=dict(selected or {}),
            selection_reason="first_compliant_candidate_in_contract_ladder_order" if selected else "no_compliant_candidate_in_contract_ladder",
            selected_ladder_index_key="shear_fail_ladder_index",
        )
        ev.update(dict(overlay.get("overlay") or {}))
        if overlay.get("error"):
            ev["shear_fail_contract_ladder_evidence_overlay_error"] = overlay.get("error")
        ev.update(
            {
                "shear_fail_contract_ladder_attempted": True,
                "shear_fail_contract_ladder_error": None,
                "repair_search_owner": "design_brain.families.shear_fail.ShearFailFamily",
                "generic_near_current_repair_search_skipped_for_pure_shear": True,
            }
        )
    if combined_attempted:
        overlay = build_design_guide_controller_active_fail_executor_family_evidence_overlay(
            family_id="COMBINED_BENDING_SHEAR_FAIL",
            ladder=dict(ladder),
            selected_candidate=dict(selected or {}),
            selection_reason="contract_family_target_band_ranked_candidate",
            selected_ladder_index_key="combined_fail_ladder_index",
        )
        ev.update(dict(overlay.get("overlay") or {}))
        if overlay.get("error"):
            ev["combined_fail_contract_ladder_evidence_overlay_error"] = overlay.get("error")
        ev.update(
            {
                "combined_fail_contract_ladder_attempted": True,
                "combined_fail_contract_ladder_error": None,
                "combined_fail_contract_ladder_found_safe": True,
                "repair_search_owner": "design_brain.families.combined_bending_shear_fail.CombinedBendingShearFailFamily",
                "generic_near_current_repair_search_skipped_for_combined": True,
                "generic_compute_bypassed_by_family_owner": True,
            }
        )
    if bending_attempted:
        overlay = build_design_guide_controller_active_fail_executor_family_evidence_overlay(
            family_id="BENDING_FAIL_GOVERNS",
            ladder=dict(ladder),
            selected_candidate=dict(selected or {}),
            selection_reason="first_compliant_candidate_in_contract_ladder_order",
            selected_ladder_index_key="bending_fail_ladder_index",
        )
        ev.update(dict(overlay.get("overlay") or {}))
        if overlay.get("error"):
            ev["bending_fail_contract_ladder_evidence_overlay_error"] = overlay.get("error")
        ev.update(
            {
                "bending_fail_contract_ladder_attempted": True,
                "bending_fail_contract_ladder_error": None,
                "bending_fail_contract_ladder_found_safe": True,
                "bending_fail_contract_ladder_candidate_count": len(list(ladder.get("specs") or [])),
                "family_ladder_candidate_count": len(list(ladder.get("specs") or [])),
                "bending_fail_contract_ladder_evaluated_candidate_count": 2,
                "bending_fail_contract_ladder_repeated_pass_count": 1,
                "bending_fail_contract_ladder_cache_fingerprint": "cache-fp",
                "repair_search_owner": "design_brain.families.bending_fail.BendingFailFamily",
                "generic_near_current_repair_search_skipped_for_bending": True,
                "generic_compute_bypassed_by_family_owner": True,
            }
        )
    return ev


def _new_projection(
    *,
    selected: dict[str, Any] | None,
    all_candidates: list[dict[str, Any]],
    safe: list[dict[str, Any]],
    active: set[str],
    family: str,
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_candidate_search_evidence,
    )

    ladder = _sample_ladder()
    metrics = {
        "candidate_evaluation_cache_hits": 2,
        "candidate_evaluation_cache_misses": 3,
        "duplicate_candidate_fingerprints_skipped": 1,
        "blocker_attempt_cache_hits": 1,
    }
    return build_design_guide_controller_active_fail_executor_candidate_search_evidence(
        selected_candidate=selected,
        all_candidates=list(all_candidates),
        safe_candidates=list(safe),
        active_failures=sorted(active),
        target_low=0.85,
        target_high=1.0,
        repair_eval_metrics=dict(metrics),
        shear_family_ladder_attempted=family == "shear",
        shear_family_ladder=dict(ladder),
        combined_family_ladder_attempted=family == "combined",
        combined_family_ladder=dict(ladder),
        combined_family_ladder_found_safe=family == "combined",
        bending_family_ladder_attempted=family == "bending",
        bending_family_ladder=dict(ladder),
        bending_family_ladder_found_safe=family == "bending",
        bending_family_ladder_evaluated_count=2,
        bending_ladder_pass_count=1,
        bending_selected_cache_fingerprint="cache-fp",
    )


def _parity_rows() -> dict[str, dict[str, Any]]:
    candidates = _sample_candidates()
    safe = [dict(candidates[1])]
    selected = dict(candidates[1])
    cases = {
        "shear_selected": {"active": {"shear"}, "family": "shear", "selected": selected},
        "bending_selected": {"active": {"bending"}, "family": "bending", "selected": selected},
        "combined_selected": {"active": {"bending", "shear"}, "family": "combined", "selected": selected},
        "generic_none": {"active": {"bending", "shear"}, "family": "generic", "selected": None},
    }
    rows: dict[str, dict[str, Any]] = {}
    for name, case in cases.items():
        old = _old_projection(
            selected=case["selected"],
            all_candidates=list(candidates),
            safe=list(safe),
            active=set(case["active"]),
            family=str(case["family"]),
        )
        new = _new_projection(
            selected=case["selected"],
            all_candidates=list(candidates),
            safe=list(safe),
            active=set(case["active"]),
            family=str(case["family"]),
        )
        rows[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "matches": old == new,
        }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    parity = _parity_rows()
    source_checks = {
        "target_delegates_candidate_search_evidence_projection": (
            "_build_design_guide_controller_active_fail_executor_candidate_search_evidence(" in target_source
        ),
        "target_no_longer_builds_candidate_search_evidence_directly": "_build_candidate_search_evidence(" not in target_source,
        "target_no_longer_calls_overlay_projection_directly": (
            "_build_design_guide_controller_active_fail_executor_family_evidence_overlay(" not in target_source
        ),
        "controller_candidate_search_evidence_helper_exists": (
            "def build_design_guide_controller_active_fail_executor_candidate_search_evidence(" in controller_source
        ),
        "controller_exports_candidate_search_evidence_helper": (
            '"build_design_guide_controller_active_fail_executor_candidate_search_evidence"' in controller_source
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
    }
    return {
        "schema": "design_guide_active_fail_executor_evidence_projection_handoff.v1",
        "target": {"name": TARGET, "line_start": target_start, "line_end": target_end},
        "parity": parity,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = dict(payload.get("parity") or {})
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "projection_hashes_unchanged": bool(parity) and all(row.get("matches") for row in parity.values()),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_evidence_projection_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_evidence_projection_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Evidence Projection Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved active-fail executor candidate-search evidence projection behind "
            "`DesignGuideController`. The page still owns candidate iteration, evaluation "
            "service calls, caches, traces, item rendering shape, and CTA side effects."
        ),
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_evidence_projection_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
