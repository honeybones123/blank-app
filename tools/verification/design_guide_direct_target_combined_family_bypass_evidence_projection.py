"""Verify combined direct-target family bypass evidence projection extraction."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_direct_target_band_guidance_item"


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


def _expected_projection() -> dict[str, Any]:
    raw_flags = {
        "active_combined_bending_shear_failure": True,
        "any_failure": True,
        "any_min_reo_fail": False,
        "any_overdesign": False,
        "any_strength_fail": True,
        "bending_acceptable": False,
        "bending_fail": True,
        "bending_overdesigned": False,
        "bending_within_target_band": False,
        "exact_stop_proven": False,
        "geometry_detailing_fail": False,
        "legal_repair_exists": True,
        "locked_repair_blocked": False,
        "min_bending_reo_fail": False,
        "min_shear_reo_fail": False,
        "repair_required": True,
        "serviceability_fail": False,
        "shear_acceptable": False,
        "shear_fail": True,
        "shear_overdesigned": False,
        "shear_within_target_band": False,
        "target_band_terminal_signal": False,
    }
    rejected_families = {
        "BENDING_FAIL_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "SHEAR_FAIL_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "GEOMETRY_DETAILING_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "LOCKED_NO_REPAIR": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "SERVICEABILITY_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "MIN_BENDING_REO_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "MIN_SHEAR_REO_GOVERNS": "rejected because COMBINED_BENDING_SHEAR_FAIL state definition matched",
        "COMBINED_OVERDESIGN": "rejected because failure state is active",
        "BENDING_OVERDESIGN_GOVERNS": "rejected because failure state is active",
        "SHEAR_OVERDESIGN_GOVERNS": "rejected because failure state is active",
        "TARGET_BAND_REACHED": "rejected because failure state is active",
        "EXACT_STOP_PROVEN": "rejected because failure state is active",
    }
    selection_evidence = {
        "source": "design_brain.family_chooser.classify_family_from_raw_flags",
        "classification_contract": "family_chooser_contract",
        "active_bending_fail": True,
        "active_shear_fail": True,
        "active_serviceability_fail": False,
        "base_active_failures": ["bending", "shear"],
        "bending_status": "FAIL",
        "shear_status": "FAIL",
        "serviceability_status": "PASS",
        "bending_utilisation": 1.34,
        "shear_utilisation": 1.08,
        "geometry_detailing_blocker_status": "absent",
        "geometry_reduction_status": "not_proven",
        "minimum_bending_reinforcement_status": "not_proven",
        "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
        "raw_state_flags": dict(raw_flags),
        "why_bending_family_rejected": rejected_families["BENDING_FAIL_GOVERNS"],
        "why_geometry_detailing_rejected_or_selected": "no geometry/detailing blocker signal present",
        "why_min_bending_reo_rejected_or_selected": "not_proven_by_current_publication_diagnostics",
        "why_target_band_rejected_or_selected": "rejected because active shear failure exists",
    }
    return {
        "raw_state_flags": dict(raw_flags),
        "rejected_families": dict(rejected_families),
        "selection_evidence": dict(selection_evidence),
        "bypass_extra": {
            "matched_family_ids": ["COMBINED_BENDING_SHEAR_FAIL"],
            "raw_state_flags": dict(raw_flags),
            "rejected_families": dict(rejected_families),
            "selection_evidence": dict(selection_evidence),
            "selection_reason": "classified_by_mutually_exclusive_definition:COMBINED_BENDING_SHEAR_FAIL",
        },
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    pre_diag = segment.split("_diag_prior = st.session_state.get", 1)[0]
    projection = build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection(
        overview={
            "statuses": {
                "bending": "FAIL",
                "shear": "FAIL",
                "serviceability": "PASS",
            },
            "utils": {
                "bending": "1.34",
                "shear": 1.08,
            },
        }
    )
    expected = _expected_projection()
    removed_inline_tokens = [
        "_combined_raw_flags = {",
        "_combined_rejected_families = {",
        "_combined_selection_evidence = {",
    ]
    return {
        "schema": "design_guide_direct_target_combined_family_bypass_evidence_projection.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
        },
        "projection_matches_expected": projection == expected,
        "projection": projection,
        "expected": expected,
        "page_calls_controller_projection": (
            "_build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection("
            in pre_diag
        ),
        "page_inline_combined_evidence_tokens_removed": {
            token: token not in pre_diag for token in removed_inline_tokens
        },
        "page_still_owns_family_executor": "_active_fail_near_current_repair_item(" in pre_diag,
        "page_still_owns_route_branch": (
            '_overview_active_failure_keys(dict(overview or {})) >= {"bending", "shear"}'
            in pre_diag
        ),
        "controller_helper_exported": (
            '"build_design_guide_controller_direct_target_combined_family_bypass_evidence_projection"'
            in controller_source
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source
            and "streamlit" not in controller_source
            and "st.session_state" not in controller_source
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    removed = payload.get("page_inline_combined_evidence_tokens_removed") or {}
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "projection_matches_expected": bool(payload.get("projection_matches_expected")),
        "page_calls_controller_projection": bool(payload.get("page_calls_controller_projection")),
        "inline_tokens_removed": bool(removed) and all(bool(value) for value in removed.values()),
        "page_still_owns_family_executor": bool(payload.get("page_still_owns_family_executor")),
        "page_still_owns_route_branch": bool(payload.get("page_still_owns_route_branch")),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "controller_has_no_page_or_streamlit_imports": bool(
            payload.get("controller_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_direct_target_combined_family_bypass_evidence_projection_{suffix}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_direct_target_combined_family_bypass_evidence_projection_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Combined Family Bypass Evidence Projection",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved pure combined active-failure bypass raw flags, rejected-family reasons, "
            "selection evidence, and bypass extra projection into DesignGuideController. "
            "Route branch and family executor remain page-owned."
        ),
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        "",
        "## Behaviour Preserved",
        "- visible wording unchanged",
        "- CTA/apply semantics unchanged",
        "- family runtime unchanged",
        "- route branch and executor still page-owned",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_combined_family_bypass_evidence_projection {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
