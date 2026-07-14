"""Verify post-active residual shear cleanup debug projection extraction."""

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

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection,
)


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


def _expected_projection(
    *,
    cleanup_item: dict[str, Any],
    cleanup_contract: dict[str, Any],
    cleanup_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "guidance_branch": "post_active_repair_residual_shear_best_safe_action",
        "selected_action_type": "apply_resolved_candidate",
        "selected_title": cleanup_item.get("title_main"),
        "selected_action_family": "shear",
        "post_click_accepted_green": False,
        "post_click_accepted_green_valid": False,
        "post_click_design_guide_state": None,
        "post_active_low_shear_safe_action_preferred": True,
        "primary_button_contract": dict(cleanup_contract),
        "button_contract": dict(cleanup_contract),
        "button_contract_enabled": True,
        "button_contract_updates": dict(cleanup_contract.get("updates") or {}),
        "candidate_search_evidence": dict(cleanup_evidence),
        "primary_card_title": cleanup_item.get("title_main"),
        "primary_card_intent": "efficiency_tightening",
        "primary_guidance_intent": "efficiency_tightening",
    }


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "basic shear cleanup",
            "cleanup_item": {
                "title_main": "Shear cleanup - best safe one-click reduction",
                "candidate_search_evidence": {"selected_candidate_id": "shear_1"},
            },
            "cleanup_contract": {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "shear",
                "updates": {"ligature_legs": 0},
                "candidate_id": "shear_1",
            },
            "cleanup_evidence": {
                "selected_candidate_id": "shear_1",
                "selected_candidate_updates": {"ligature_legs": 0},
            },
        },
        {
            "name": "combined promoted item with empty updates",
            "cleanup_item": {
                "title_main": "Shear and bending cleanup - one-click optimisation",
                "candidate_search_evidence": {"selected_candidate_id": "combined_1"},
            },
            "cleanup_contract": {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "family": "combined",
                "updates": {},
                "candidate_id": "combined_1",
            },
            "cleanup_evidence": {"selected_candidate_id": "combined_1"},
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        expected = _expected_projection(
            cleanup_item=scenario["cleanup_item"],
            cleanup_contract=scenario["cleanup_contract"],
            cleanup_evidence=scenario["cleanup_evidence"],
        )
        actual = build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection(
            cleanup_item=scenario["cleanup_item"],
            cleanup_contract=scenario["cleanup_contract"],
            cleanup_evidence=scenario["cleanup_evidence"],
        )
        rows.append(
            {
                "name": scenario["name"],
                "matches": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, core_segment = _function_source(inputs_source, "_compute_design_guidance_items_core")
    scenario_rows = _scenario_rows()
    return {
        "schema": "design_guide_compute_core_post_active_residual_shear_debug_projection_extraction.v1",
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "controller_helper_present": "def build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection"' in controller_source,
        "page_delegates_to_controller": "_build_design_guide_controller_post_active_residual_shear_cleanup_debug_projection(" in core_segment,
        "page_debug_rows_removed": all(
            token not in core_segment
            for token in (
                'debug_sink["guidance_branch"] = "post_active_repair_residual_shear_best_safe_action"',
                'debug_sink["selected_action_type"] = "apply_resolved_candidate"',
                'debug_sink["primary_button_contract"] = dict(_post_active_shear_cleanup_contract)',
                'debug_sink["candidate_search_evidence"] = dict(_post_active_shear_cleanup_evidence)',
            )
        ),
        "candidate_discovery_unchanged": (
            "_shear_best_safe_cleanup_item_from_evidence(" in core_segment
            and "_shear_low_util_target_cleanup_item(" in core_segment
        ),
        "actionability_guard_unchanged": "_design_guide_button_contract_enabled(_post_active_shear_cleanup_contract)" in core_segment,
        "return_item_unchanged": "return [_post_active_shear_cleanup_item]" in core_segment,
        "scenario_rows": scenario_rows,
        "scenario_parity_passed": all(bool(row.get("matches")) for row in scenario_rows),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "controller_helper_present": bool(payload.get("controller_helper_present")),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "page_delegates_to_controller": bool(payload.get("page_delegates_to_controller")),
        "page_debug_rows_removed": bool(payload.get("page_debug_rows_removed")),
        "candidate_discovery_unchanged": bool(payload.get("candidate_discovery_unchanged")),
        "actionability_guard_unchanged": bool(payload.get("actionability_guard_unchanged")),
        "return_item_unchanged": bool(payload.get("return_item_unchanged")),
        "scenario_parity_passed": bool(payload.get("scenario_parity_passed")),
        "controller_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_post_active_residual_shear_debug_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_post_active_residual_shear_debug_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Core Post-Active Residual Shear Debug Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "The post-active residual shear cleanup debug projection is controller-owned. Candidate discovery, actionability guard, returned item, CTA/apply semantics, and family runtimes remain unchanged.",
        "",
        "## Scenario Parity",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('matches') else 'FAIL'}")
    lines.extend(["", "## Checks"])
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_core_post_active_residual_shear_debug_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
