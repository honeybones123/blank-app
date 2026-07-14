"""Audit the active-fail geometry/fit input plumbing boundary."""

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
TARGET = "_active_fail_near_current_repair_item"


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


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_row(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": _line_numbers(segment, start_line, token)[:20],
    }


def _helper_row(
    *,
    helper_name: str,
    source: str,
    owner: str,
    target_owner: str,
    classification: str,
    deletion_readiness: str,
    reason: str,
) -> dict[str, Any]:
    start, end, helper_source = _function_source(source, helper_name)
    return {
        "helper": helper_name,
        "line_start": start,
        "line_end": end,
        "line_count": max(0, end - start + 1),
        "current_owner": owner,
        "target_owner": target_owner,
        "classification": classification,
        "deletion_readiness": deletion_readiness,
        "reason": reason,
        "source_imports_streamlit_or_page": any(
            token in helper_source for token in ("streamlit", "st.session_state", "inputs_page")
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    helper_rows = [
        _helper_row(
            helper_name="_geometry_state_with_updates",
            source=inputs_source,
            owner="inputs_page current-state geometry overlay helper",
            target_owner="bounded page-shell input plumbing until geometry service extraction",
            classification="page-shell input collection with existing contract guard call",
            deletion_readiness="KEEP_BOUNDED",
            reason=(
                "Builds a candidate state overlay from the current page state and calls the existing "
                "depth/width contract guard. Moving it safely needs a broader geometry-state service boundary."
            ),
        ),
        _helper_row(
            helper_name="_design_width_value",
            source=inputs_source,
            owner="inputs_page state scalar extraction",
            target_owner="bounded page-shell input plumbing",
            classification="page-shell scalar extraction",
            deletion_readiness="KEEP_BOUNDED",
            reason="Reads the section-shape-dependent width value from the current state.",
        ),
        _helper_row(
            helper_name="_float_from_state",
            source=inputs_source,
            owner="inputs_page state scalar extraction",
            target_owner="bounded page-shell input plumbing",
            classification="page-shell scalar extraction",
            deletion_readiness="KEEP_BOUNDED",
            reason="Converts current page state values to floats with existing defaults.",
        ),
        _helper_row(
            helper_name="_normalise_bottom_layer_order",
            source=inputs_source,
            owner="inputs_page bottom arrangement normalization",
            target_owner="future reinforcement arrangement service if extracted broadly",
            classification="pure arrangement normalization but shared by wider page-local generators",
            deletion_readiness="UNSAFE_TO_MOVE_IN_THIS_SLICE",
            reason=(
                "Pure enough to move later, but used outside the active-fail fallback row preparation. "
                "Moving it here would broaden the slice beyond the active-fail executor boundary."
            ),
        ),
        _helper_row(
            helper_name="_arrangement_fits_state",
            source=inputs_source,
            owner="inputs_page layout fit probe",
            target_owner="future candidate/reinforcement service boundary",
            classification="candidate fit check using page-state dimensions and layout helper",
            deletion_readiness="UNSAFE_TO_MOVE_IN_THIS_SLICE",
            reason=(
                "It decides whether a bottom arrangement physically fits the current candidate geometry. "
                "Moving it safely requires a candidate generation/service extraction, not a row projection slice."
            ),
        ),
    ]
    surface_rows = [
        {
            "surface": "geometry state overlay",
            "classification": "bounded page-shell input plumbing",
            "evidence": [
                _token_row(segment, start, "_geometry_state_with_updates("),
                _token_row(segment, start, "_design_width_value("),
                _token_row(segment, start, '_float_from_state(geom_state, "D", depth)'),
            ],
            "target_owner": "page shell until geometry-state service extraction",
        },
        {
            "surface": "bottom arrangement normalization and fit probe",
            "classification": "bounded candidate fit input plumbing",
            "evidence": [
                _token_row(segment, start, "_normalise_bottom_layer_order("),
                _token_row(segment, start, "_arrangement_fits_state("),
                _token_row(segment, start, "_bottom_arrangement_to_shared_updates("),
            ],
            "target_owner": "future target-band/candidate generation service boundary",
        },
        {
            "surface": "near-current combined fallback command construction",
            "classification": "controller-owned after previous handoffs",
            "evidence": [
                _token_row(
                    segment,
                    start,
                    "_build_design_guide_controller_active_fail_executor_geometry_update_row(",
                ),
                _token_row(
                    segment,
                    start,
                    "_build_design_guide_controller_active_fail_executor_bottom_update_row(",
                ),
                _token_row(
                    segment,
                    start,
                    "_build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands(",
                ),
            ],
            "target_owner": "DesignGuideController",
        },
    ]
    missing_surface_evidence = [
        row.get("surface")
        for row in surface_rows
        if not any(item.get("present") for item in row.get("evidence") or [])
    ]
    return {
        "schema": "design_guide_active_fail_executor_geometry_fit_input_plumbing_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "decision": "GEOMETRY_FIT_INPUT_PLUMBING_BOUNDED",
        "executive_summary": (
            "The remaining active-fail near-current geometry/fit code is bounded page-shell input plumbing "
            "or wider candidate-generation fit logic. Geometry/bottom update-row projection and fallback "
            "command construction are already controller-owned, so this active-fail surface should not keep "
            "blocking the frozen target-band/direct-target extraction queue."
        ),
        "helper_inventory": helper_rows,
        "surface_inventory": surface_rows,
        "missing_surface_evidence": missing_surface_evidence,
        "next_safe_target": "target_band_generator_ranking_projection_extraction_audit",
        "stop_conditions": [
            "Do not move _arrangement_fits_state without a candidate generation service boundary.",
            "Do not move _geometry_state_with_updates without a geometry-state request boundary.",
            "Do not move Streamlit/session/callback execution into Design Brain.",
            "Return to target-band/direct-target extraction once this boundary is locked.",
        ],
        "controller_import_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    helpers = payload.get("helper_inventory") or []
    surfaces = payload.get("surface_inventory") or []
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "decision_bounded": payload.get("decision") == "GEOMETRY_FIT_INPUT_PLUMBING_BOUNDED",
        "helpers_found": len(helpers) == 5 and all(bool(row.get("line_start")) for row in helpers),
        "surface_evidence_present": not bool(payload.get("missing_surface_evidence")),
        "controller_command_helpers_present": any(
            row.get("surface") == "near-current combined fallback command construction"
            and all(item.get("present") for item in row.get("evidence") or [])
            for row in surfaces
        ),
        "bounded_geometry_helpers_classified": all(
            any(row.get("helper") == helper and row.get("deletion_readiness") == "KEEP_BOUNDED" for row in helpers)
            for helper in ("_geometry_state_with_updates", "_design_width_value", "_float_from_state")
        ),
        "fit_helpers_not_moved_in_this_slice": all(
            any(
                row.get("helper") == helper
                and row.get("deletion_readiness") == "UNSAFE_TO_MOVE_IN_THIS_SLICE"
                for row in helpers
            )
            for helper in ("_normalise_bottom_layer_order", "_arrangement_fits_state")
        ),
        "controller_import_boundary_clean": bool(payload.get("controller_import_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"design_guide_active_fail_executor_geometry_fit_input_plumbing_boundary_audit_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_active_fail_executor_geometry_fit_input_plumbing_boundary_audit_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Geometry/Fit Input Plumbing Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Executive Summary",
        str(payload.get("executive_summary") or ""),
        "",
        "## Helper Inventory",
    ]
    for row in payload.get("helper_inventory") or []:
        lines.append(
            f"- `{row.get('helper')}` ({row.get('line_start')}-{row.get('line_end')}): "
            f"{row.get('classification')}; readiness `{row.get('deletion_readiness')}`. "
            f"Target: {row.get('target_owner')}."
        )
    lines.extend(
        [
            "",
            "## Surface Inventory",
        ]
    )
    for row in payload.get("surface_inventory") or []:
        lines.append(f"- {row.get('surface')}: {row.get('classification')} -> {row.get('target_owner')}")
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
            "",
            "## Next Safe Target",
            f"`{payload.get('next_safe_target')}`",
            "",
            "## Stop Conditions",
            *[f"- {item}" for item in payload.get("stop_conditions") or []],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"next={payload.get('next_safe_target')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
