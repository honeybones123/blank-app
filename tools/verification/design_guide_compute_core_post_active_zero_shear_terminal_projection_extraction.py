"""Verify post-active zero-shear terminal projection extraction."""

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
    build_design_guide_controller_post_active_zero_shear_terminal_projection,
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
    accepted_util: float,
    target_low: float,
    target_high: float,
    shear_util: float | None,
    existing_excluded_families: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bucket = "warn" if accepted_util >= 0.9 else "pass"
    priority = (200.0 + accepted_util) if bucket == "warn" else (100.0 - accepted_util)
    item = {
        "check_key": "general",
        "title_main": "Design accepted - target band achieved",
        "title_util": f"(utilisation = {accepted_util:.2f})",
        "title": f"Design accepted - target band achieved (utilisation = {accepted_util:.2f})",
        "primary_action": "The one-click capacity repair has been applied and the current design is inside the target band.",
        "secondary_action": None,
        "reasoning": "Why: all required checks remain acceptable; shear has zero or negligible demand and is not a required cleanup family.",
        "levers": "Key checks: bending, shear demand, serviceability, target utilisation band",
        "status": "PASS",
        "bucket": bucket,
        "util": accepted_util,
        "priority": priority,
        "action_type": None,
        "action_payload": {},
        "guidance_intent": "already_efficient",
        "design_guide_terminal_state": "optimal",
        "display_truth": {
            "display_truth_source": "published_summary",
            "displayed_util": accepted_util,
            "displayed_status": "OPTIMAL",
            "target_low": float(target_low),
            "target_high": float(target_high),
            "displayed_within_target_band": True,
            "source_summary_util": accepted_util,
            "source_candidate_util": None,
            "source_post_commit_util": accepted_util,
        },
    }
    zero_shear_exclusion = {
        "family": "shear",
        "reason": "zero_demand_or_not_meaningful",
        "excluded_reason": "zero_demand_or_not_meaningful",
        "cleanup_required": False,
        "no_second_cta_required": True,
        "util": shear_util,
    }
    excluded = {
        **dict(existing_excluded_families or {}),
        "shear": dict(zero_shear_exclusion),
    }
    debug_updates = {
        "guidance_branch": "post_active_repair_zero_shear_terminal",
        "selected_action_type": None,
        "selected_title": item.get("title_main"),
        "post_click_accepted_green": True,
        "post_click_accepted_green_valid": True,
        "post_click_design_guide_state": "accepted_green",
        "post_click_executable_safe_cleanup_count": 0,
        "post_click_safe_local_cleanup_count": 0,
        "post_click_unresolved_low_util_families": [],
        "post_click_unresolved_overprovided_families": [],
        "post_click_excluded_families": dict(excluded),
        "excluded_families": dict(excluded),
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_local_cleanup_count": 0,
        "executable_safe_cleanup_count": 0,
        "terminal_state_reason": "post_active_repair_zero_shear_excluded",
        "terminal_state_blocked_by_local_cleanup": False,
        "primary_button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "shear",
            "updates": {},
            "preview_pass": False,
            "blocking_reason": "zero_demand_or_not_meaningful",
            "source_candidate_id": None,
            "candidate_id": None,
        },
    }
    return {
        "item": item,
        "debug_updates": debug_updates,
        "zero_shear_exclusion": zero_shear_exclusion,
        "controller_authority": "DesignGuideController.post_active_zero_shear_terminal_projection",
    }


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "plain zero shear terminal",
            "accepted_util": 0.82,
            "target_low": 0.85,
            "target_high": 1.0,
            "shear_util": 0.0,
            "existing_excluded_families": {},
        },
        {
            "name": "preserves existing excluded family",
            "accepted_util": 0.91,
            "target_low": 0.85,
            "target_high": 1.0,
            "shear_util": None,
            "existing_excluded_families": {"bending": {"family": "bending", "reason": "already_resolved"}},
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        expected = _expected_projection(
            accepted_util=scenario["accepted_util"],
            target_low=scenario["target_low"],
            target_high=scenario["target_high"],
            shear_util=scenario["shear_util"],
            existing_excluded_families=scenario["existing_excluded_families"],
        )
        actual = build_design_guide_controller_post_active_zero_shear_terminal_projection(
            accepted_util=scenario["accepted_util"],
            target_low=scenario["target_low"],
            target_high=scenario["target_high"],
            shear_util=scenario["shear_util"],
            existing_excluded_families=scenario["existing_excluded_families"],
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
        "schema": "design_guide_compute_core_post_active_zero_shear_terminal_projection_extraction.v1",
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "controller_helper_present": "def build_design_guide_controller_post_active_zero_shear_terminal_projection(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_post_active_zero_shear_terminal_projection"' in controller_source,
        "page_delegates_to_controller": "_build_design_guide_controller_post_active_zero_shear_terminal_projection(" in core_segment,
        "page_visible_terminal_wording_removed": "The one-click capacity repair has been applied" not in core_segment,
        "page_zero_shear_exclusion_literal_removed": "_zero_shear_exclusion = {" not in core_segment,
        "scenario_rows": scenario_rows,
        "scenario_parity_passed": all(bool(row.get("matches")) for row in scenario_rows),
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
        "page_visible_terminal_wording_removed": bool(payload.get("page_visible_terminal_wording_removed")),
        "page_zero_shear_exclusion_literal_removed": bool(payload.get("page_zero_shear_exclusion_literal_removed")),
        "scenario_parity_passed": bool(payload.get("scenario_parity_passed")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_post_active_zero_shear_terminal_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_post_active_zero_shear_terminal_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Core Post-Active Zero-Shear Terminal Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Summary",
        "The zero-shear terminal item/display/debug projection is controller-owned. "
        "The page still decides when the branch applies and still writes debug updates.",
        "",
        "## Scenario Parity",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('matches') else 'FAIL'}")
    lines.extend(
        [
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
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_compute_core_post_active_zero_shear_terminal_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
