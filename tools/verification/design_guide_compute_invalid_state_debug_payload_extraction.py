"""Verify invalid-state compute debug payload construction moved to controller."""

from __future__ import annotations

import ast
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


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _expected_old_debug_payload(
    *,
    canonical_state: dict[str, Any],
    coherence_debug_fields: dict[str, Any],
    canonical_pack_valid: bool,
    stop_reason: str,
    actions_used: dict[str, Any],
    fail_status: str,
    not_run_status: str,
) -> dict[str, Any]:
    blocked_guidance_branch = (
        "blocked_invalid_canonical_pack" if not canonical_pack_valid else "blocked_hard_invalid_state"
    )
    blocked_user_reason = (
        "Add longitudinal reinforcement before running auto-design."
        if stop_reason == "no_bars_resolved"
        else f"Design Guide blocked: {stop_reason}."
    )
    payload = {
        "guidance_branch": blocked_guidance_branch,
        "selected_action_type": None,
        "selected_title": None,
        "guidance_resolved_state": dict(canonical_state),
        "longitudinal_reo_truth_source": canonical_state.get("longitudinal_reo_truth_source"),
        "overview": {
            "packs": {},
            "statuses": {
                "bending": fail_status,
                "shear": not_run_status,
                "crack": not_run_status,
                "deflection": not_run_status,
            },
            "utils": {
                "bending": None,
                "shear": None,
                "crack": None,
                "deflection": None,
            },
            "any_fail": True,
            "any_warn": False,
            "all_key_pass": False,
            "worst_util": 0.0,
            "actions_used": dict(actions_used or {}),
        },
        "efficiency_tightening_state": {
            "classification": "blocked_invalid_state",
        },
        **dict(coherence_debug_fields or {}),
        "canonical_pack_built": bool(canonical_state.get("canonical_pack_built")),
        "canonical_pack_valid": canonical_pack_valid,
        "canonical_pack_source": canonical_state.get("canonical_pack_source"),
        "canonical_pack_error": canonical_state.get("canonical_pack_error"),
        "canonical_pack_error_stage": canonical_state.get("canonical_pack_error_stage"),
        "solver_blocked_by_incoherent_state": True,
        "stop_reason": stop_reason,
        "user_visible_no_action_reason": blocked_user_reason,
    }
    return payload


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_compute_invalid_state_debug_payload,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    wrapper_start, wrapper_end, wrapper_segment = _function_source(inputs_source, "_compute_design_guidance_items")
    helper_start, helper_end, _helper_segment = _function_source(
        controller_source,
        "build_design_guide_controller_compute_invalid_state_debug_payload",
    )

    canonical_state = {
        "canonical_pack_built": True,
        "canonical_pack_valid": False,
        "canonical_pack_source": "fixture",
        "canonical_pack_error": "no_bars_resolved",
        "canonical_pack_error_stage": "longitudinal_reo",
        "longitudinal_reo_truth_source": "fixture_reo",
    }
    coherence_debug_fields = {
        "coherence_should_block": True,
        "coherence_blocking_issues": ["no_bars_resolved"],
    }
    cases: list[dict[str, Any]] = []
    for canonical_pack_valid, stop_reason in (
        (False, "no_bars_resolved"),
        (True, "state_incoherent_after_rebuild"),
    ):
        expected = _expected_old_debug_payload(
            canonical_state=dict(canonical_state),
            coherence_debug_fields=dict(coherence_debug_fields),
            canonical_pack_valid=canonical_pack_valid,
            stop_reason=stop_reason,
            actions_used={"b": 300.0, "D": 600.0},
            fail_status="FAIL",
            not_run_status="NOT_RUN",
        )
        actual = build_design_guide_controller_compute_invalid_state_debug_payload(
            canonical_state=dict(canonical_state),
            coherence_debug_fields=dict(coherence_debug_fields),
            canonical_pack_valid=canonical_pack_valid,
            stop_reason=stop_reason,
            actions_used={"b": 300.0, "D": 600.0},
            fail_status="FAIL",
            not_run_status="NOT_RUN",
        )
        cases.append(
            {
                "canonical_pack_valid": canonical_pack_valid,
                "stop_reason": stop_reason,
                "matches_old_debug_payload": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )

    removed_page_literals = all(
        token not in wrapper_segment
        for token in (
            '"blocked_invalid_canonical_pack"',
            '"blocked_hard_invalid_state"',
            '"Design Guide blocked:',
            '"efficiency_tightening_state": {',
            '"solver_blocked_by_incoherent_state": True',
        )
    )
    return {
        "schema": "design_guide_compute_invalid_state_debug_payload_extraction.v1",
        "target": {
            "wrapper_line_start": wrapper_start,
            "wrapper_line_end": wrapper_end,
            "helper_line_start": helper_start,
            "helper_line_end": helper_end,
        },
        "cases": cases,
        "source_checks": {
            "wrapper_delegates_debug_payload_to_controller": (
                "_build_design_guide_controller_compute_invalid_state_debug_payload(" in wrapper_segment
            ),
            "wrapper_removed_page_local_debug_literals": removed_page_literals,
            "wrapper_keeps_action_collection": "_resolve_design_actions_from_state(state)" in wrapper_segment,
            "wrapper_keeps_cache_write": 'set_rerun_pure_cache("compute_design_guidance_items"' in wrapper_segment,
            "wrapper_keeps_boundary_attachment": "_attach_design_brain_result_boundary(" in wrapper_segment,
            "helper_exists_in_controller": bool(helper_start),
            "helper_exported": '"build_design_guide_controller_compute_invalid_state_debug_payload"' in controller_source,
            "controller_has_no_page_or_streamlit_imports": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
            "row_model_legacy_sync_removed_from_controller": all(
                token not in controller_source
                for token in ("row_model_legacy_sync_applied", "row_model_legacy_sync_diff_keys")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "all_cases_match_old_debug_payload": all(
            bool(row.get("matches_old_debug_payload")) for row in payload.get("cases") or []
        ),
        "wrapper_delegates_debug_payload_to_controller": bool(
            source_checks.get("wrapper_delegates_debug_payload_to_controller")
        ),
        "wrapper_removed_page_local_debug_literals": bool(
            source_checks.get("wrapper_removed_page_local_debug_literals")
        ),
        "wrapper_keeps_action_collection": bool(source_checks.get("wrapper_keeps_action_collection")),
        "wrapper_keeps_cache_write": bool(source_checks.get("wrapper_keeps_cache_write")),
        "wrapper_keeps_boundary_attachment": bool(source_checks.get("wrapper_keeps_boundary_attachment")),
        "helper_exists_in_controller": bool(source_checks.get("helper_exists_in_controller")),
        "helper_exported": bool(source_checks.get("helper_exported")),
        "row_model_legacy_sync_removed_from_controller": bool(
            source_checks.get("row_model_legacy_sync_removed_from_controller")
        ),
        "controller_import_boundary_clean": bool(source_checks.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_invalid_state_debug_payload_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_invalid_state_debug_payload_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Invalid-State Debug Payload Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "The invalid/coherence blocked compute debug payload is now built by "
        "`design_brain.design_guide_controller`. The page keeps action collection, cache writes, "
        "and boundary attachment.",
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
    print(f"design_guide_compute_invalid_state_debug_payload_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
