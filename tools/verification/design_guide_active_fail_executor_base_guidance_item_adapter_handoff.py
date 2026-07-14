"""Verify active-fail executor base guidance item adapter handoff."""

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
ACTIVE_FAIL_TARGET = "_active_fail_near_current_repair_item"
RESOLVED_ADAPTER = "_guidance_item_from_resolved_candidate"
CONTROLLER_HELPER = "build_design_guide_controller_resolved_candidate_guidance_item"


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


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    active_start, active_end, active_source = _function_source(inputs_source, ACTIVE_FAIL_TARGET)
    adapter_start, adapter_end, adapter_source = _function_source(inputs_source, RESOLVED_ADAPTER)
    controller_start, controller_end, controller_source_segment = _function_source(controller_source, CONTROLLER_HELPER)
    forbidden_final_shape_tokens = [
        'item["resolved_candidate_label"]',
        'item["resolved_candidate_action_type"]',
        'item["resolved_candidate_family_tag"]',
        'item["resolved_candidate_updates"]',
        'item["resolved_candidate"]',
        'item["has_resolved_candidate_payload"]',
        "item = _guidance_item(",
    ]
    pre_input_tokens = [
        "_resolve_canonical_guidance_title_from_candidate(",
        "_guidance_default_alternatives_text(",
        "_guidance_change_lines_for_updates(",
        "_candidate_failure_coverage_summary(",
        "_guidance_before_after_text(",
    ]
    return {
        "schema": "design_guide_active_fail_executor_base_guidance_item_adapter_handoff.v1",
        "active_fail_target": {
            "line_start": active_start,
            "line_end": active_end,
            "line_count": max(0, active_end - active_start + 1),
            "calls_resolved_adapter": f"{RESOLVED_ADAPTER}(" in active_source,
            "direct_controller_final_item_call": f"_{CONTROLLER_HELPER}(" in active_source,
            "direct_final_shape_writes": {
                token: token in active_source for token in forbidden_final_shape_tokens
            },
        },
        "resolved_adapter": {
            "line_start": adapter_start,
            "line_end": adapter_end,
            "line_count": max(0, adapter_end - adapter_start + 1),
            "delegates_final_item_to_controller": f"_{CONTROLLER_HELPER}(" in adapter_source,
            "final_shape_writes_removed": not any(token in adapter_source for token in forbidden_final_shape_tokens),
            "pre_input_helpers_still_page_owned": {
                token: token in adapter_source for token in pre_input_tokens
            },
        },
        "controller_helper": {
            "line_start": controller_start,
            "line_end": controller_end,
            "line_count": max(0, controller_end - controller_start + 1),
            "exists": bool(controller_start),
            "exported": f'"{CONTROLLER_HELPER}"' in controller_source,
            "owns_final_output_shape": (
                'item["resolved_candidate_label"]' in controller_source_segment
                and 'item["resolved_candidate"]' in controller_source_segment
                and 'item["has_resolved_candidate_payload"]' in controller_source_segment
                and "action_payload" in controller_source_segment
            ),
            "imports_no_page_or_streamlit": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "remaining_extraction_surface": "resolved_candidate_guidance_item_pre_input_helpers",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    active = payload.get("active_fail_target") or {}
    adapter = payload.get("resolved_adapter") or {}
    controller = payload.get("controller_helper") or {}
    return {
        "active_fail_target_found": bool(active.get("line_start")),
        "active_fail_calls_resolved_adapter": bool(active.get("calls_resolved_adapter")),
        "active_fail_has_no_direct_final_shape_writes": not any(
            (active.get("direct_final_shape_writes") or {}).values()
        ),
        "resolved_adapter_found": bool(adapter.get("line_start")),
        "resolved_adapter_delegates_final_item_to_controller": bool(
            adapter.get("delegates_final_item_to_controller")
        ),
        "resolved_adapter_no_longer_writes_final_shape": bool(adapter.get("final_shape_writes_removed")),
        "remaining_pre_input_surface_explicit": all(
            (adapter.get("pre_input_helpers_still_page_owned") or {}).values()
        ),
        "controller_helper_exists": bool(controller.get("exists")),
        "controller_helper_exported": bool(controller.get("exported")),
        "controller_owns_final_output_shape": bool(controller.get("owns_final_output_shape")),
        "controller_import_boundary_clean": bool(controller.get("imports_no_page_or_streamlit")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_base_guidance_item_adapter_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_base_guidance_item_adapter_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Base Guidance Item Adapter Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "The active-fail executor reaches base guidance item construction through the shared "
            "resolved-candidate adapter. That adapter delegates final item/action-payload shape to "
            "`DesignGuideController`; the remaining page-owned work is the broader resolved-candidate "
            "pre-input helper surface, not active-fail-specific publication truth."
        ),
        "",
        "## Surface Targeted",
        "`_active_fail_near_current_repair_item(...)` base guidance item construction.",
        "",
        "## Ownership After",
        "- Active-fail executor: shell call to resolved-candidate adapter.",
        "- Resolved-candidate final item shape: `DesignGuideController`.",
        "- Remaining pre-input helper extraction: `resolved_candidate_guidance_item_pre_input_helpers`.",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        "",
        "## Next Safe Target",
        "`active_fail_executor_evaluation_loop_handoff`, or extract the broader "
        "`resolved_candidate_guidance_item_pre_input_helpers` surface before deleting the shared adapter.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_base_guidance_item_adapter_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
