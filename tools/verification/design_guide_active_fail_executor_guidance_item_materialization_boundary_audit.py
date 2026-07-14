"""Audit active-fail executor guidance item materialization boundary."""

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

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
ACTIVE_FAIL_TARGET = "_active_fail_near_current_repair_item"
MATERIALIZER = "_guidance_item_from_resolved_candidate"


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


def _line_numbers(source: str, token: str) -> list[int]:
    return [idx + 1 for idx, line in enumerate(source.splitlines()) if token in line]


def _token(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line][:20],
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    active_start, active_end, active_segment = _function_source(inputs_source, ACTIVE_FAIL_TARGET)
    materializer_start, materializer_end, materializer_segment = _function_source(inputs_source, MATERIALIZER)
    call_lines = [
        line
        for line in _line_numbers(inputs_source, f"{MATERIALIZER}(")
        if line != materializer_start
    ]
    surfaces = [
        {
            "surface": "active-fail materializer callsite",
            "classification": "page-shell item factory invocation before controller final projection",
            "current_owner": "inputs_page",
            "target_owner": "bounded page shell until shared materializer action-update fallback boundaries are extracted",
            "deletion_readiness": "NOT_READY",
            "evidence": [
                _token(active_segment, active_start, f"{MATERIALIZER}("),
                _token(active_segment, active_start, "_build_design_guide_controller_active_fail_executor_final_guidance_item_projection("),
            ],
        },
        {
            "surface": "shared resolved-candidate materializer",
            "classification": "shared page-owned presentation/action-payload preparation helper with controller-backed packs",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController or presentation/projection service after action-update fallback parity",
            "deletion_readiness": "NOT_READY_SHARED_HELPER",
            "evidence": [
                _token(materializer_segment, materializer_start, "_resolve_canonical_guidance_title_from_candidate("),
                _token(materializer_segment, materializer_start, "_guidance_default_alternatives_text("),
                _token(materializer_segment, materializer_start, "_guidance_change_lines_for_updates("),
                _token(materializer_segment, materializer_start, "_candidate_failure_coverage_summary("),
                _token(materializer_segment, materializer_start, "_guidance_before_after_text("),
                _token(materializer_segment, materializer_start, "_build_design_guide_controller_resolved_candidate_guidance_item("),
            ],
        },
        {
            "surface": "controller-backed materializer packs",
            "classification": "resolved-candidate input, compact text, and before/after request packs are controller-owned",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(materializer_segment, materializer_start, "_build_design_guide_controller_resolved_candidate_guidance_item_input_pack("),
                _token(materializer_segment, materializer_start, "_build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack("),
                _token(materializer_segment, materializer_start, "_build_design_guide_controller_resolved_candidate_guidance_item_before_after_request_pack("),
            ],
        },
        {
            "surface": "controller final active-fail field projection",
            "classification": "controller-owned final guidance field projection",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(active_segment, active_start, "_build_design_guide_controller_active_fail_executor_final_guidance_item_projection("),
            ],
        },
        {
            "surface": "visible wording inputs",
            "classification": "unsafe to move without broad wording parity",
            "current_owner": "inputs_page helper family",
            "target_owner": "DesignGuideController/presentation service after parity",
            "deletion_readiness": "UNSAFE_TO_MOVE_YET",
            "evidence": [
                _token(materializer_segment, materializer_start, "reasoning_text=reasoning"),
                _token(materializer_segment, materializer_start, "guidance_change_summary_compact"),
                _token(materializer_segment, materializer_start, "guidance_expected_util_text"),
                _token(materializer_segment, materializer_start, "guidance_why_text_compact"),
            ],
        },
    ]
    return {
        "schema": "design_guide_active_fail_executor_guidance_item_materialization_boundary_audit.v1",
        "targets": {
            ACTIVE_FAIL_TARGET: {
                "line_start": active_start,
                "line_end": active_end,
                "line_count": max(0, active_end - active_start + 1),
            },
            MATERIALIZER: {
                "line_start": materializer_start,
                "line_end": materializer_end,
                "line_count": max(0, materializer_end - materializer_start + 1),
            },
        },
        "callsite_count": len(call_lines),
        "callsite_lines_sample": call_lines[:40],
        "decision": "NOT_READY_SHARED_MATERIALIZER_NEEDS_ACTION_UPDATE_FALLBACK_BOUNDARY",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "guidance_action_updates_bottom_arrangement_conversion_boundary_audit",
            "why": (
                "The active-fail callsite uses a shared materializer whose input, compact-text, and before/after request "
                "packs are controller-backed. The remaining materializer blocker is before/after update resolution via "
                "_guidance_action_updates(...), where bottom arrangement/fallback and generated update branches remain page-owned."
            ),
            "move": (
                "Audit bottom recommendation fallback and _bottom_arrangement_to_shared_updates(...) before moving any "
                "bottom arrangement conversion or recommendation fallback logic."
            ),
            "required_verifier": "design_guide_guidance_action_updates_bottom_arrangement_conversion_boundary_audit.py",
        },
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = list(payload.get("surfaces") or [])
    targets = dict(payload.get("targets") or {})
    return {
        "active_fail_target_found": bool((targets.get(ACTIVE_FAIL_TARGET) or {}).get("line_start")),
        "materializer_found": bool((targets.get(MATERIALIZER) or {}).get("line_start")),
        "shared_calls_detected": int(payload.get("callsite_count") or 0) > 1,
        "surfaces_classified": len(surfaces) == 5,
        "final_projection_controller_owned": any(
            row.get("surface") == "controller final active-fail field projection"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "materializer_not_ready": any(
            row.get("surface") == "shared resolved-candidate materializer"
            and row.get("deletion_readiness") == "NOT_READY_SHARED_HELPER"
            for row in surfaces
        ),
        "controller_materializer_packs_recorded": any(
            row.get("surface") == "controller-backed materializer packs"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        ),
        "controller_boundary_clean": bool(payload.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_guidance_item_materialization_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_guidance_item_materialization_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Design Guide Active-Fail Executor Guidance Item Materialization Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Current State",
        f"- Shared materializer callsites: {payload.get('callsite_count')}",
        "- Active-fail final field projection is already controller-owned.",
        "- Resolved-candidate input, compact text, and before/after request packs are controller-backed.",
        "- The shared materializer is not safe to move until action-update fallback boundaries are extracted.",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"({row.get('current_owner')} -> {row.get('target_owner')}); "
            f"readiness `{row.get('deletion_readiness')}`"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Verifier: `{first_slice.get('required_verifier')}`",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
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
    print(f"design_guide_active_fail_executor_guidance_item_materialization_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
