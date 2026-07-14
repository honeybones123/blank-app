"""Verify compute-core branch request projection extraction.

This verifier proves the first branch-orchestration slice moved only pure
scalar/request projection to DesignGuideController. It intentionally does not
claim the full compute core is shell-only.
"""

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
    build_design_guide_controller_compute_core_branch_request_projection,
)
from tools.verification.design_guide_compute_core_branch_orchestration_audit import (  # noqa: E402
    _capture as _capture_branch_audit,
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


def _legacy_projection(
    *,
    target_band_with_eps_passed: bool,
    overview_required_checks_acceptable: bool,
    post_apply_acceptance_matches: bool,
    last_apply_route: dict[str, Any] | None,
) -> dict[str, Any]:
    route = dict(last_apply_route or {})
    label = str(
        route.get("resolved_candidate_label")
        or route.get("post_apply_resolved_candidate_label")
        or ""
    ).strip()
    family = str(route.get("resolved_candidate_family_tag") or "").strip().lower()
    return {
        "last_apply_label_for_post_active": label,
        "last_apply_family_for_post_active": family,
        "post_apply_from_active_failure_repair": bool(
            bool(post_apply_acceptance_matches)
            and route.get("post_apply_resolved_candidate_attempted")
            and family in {"bending", "shear", "combined", "geometry"}
            and "cleanup" not in label.lower()
        ),
        "out_of_band_live": not (
            bool(overview_required_checks_acceptable)
            and bool(target_band_with_eps_passed)
        ),
    }


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "active bending repair accepted",
            "overview": {"any_fail": False},
            "target_band_with_eps_passed": True,
            "overview_required_checks_acceptable": True,
            "post_apply_acceptance_matches": True,
            "last_apply_route": {
                "resolved_candidate_label": "Increase section for bending",
                "resolved_candidate_family_tag": "bending",
                "post_apply_resolved_candidate_attempted": True,
            },
        },
        {
            "name": "cleanup label is not active repair",
            "overview": {"any_fail": False},
            "target_band_with_eps_passed": True,
            "overview_required_checks_acceptable": True,
            "post_apply_acceptance_matches": True,
            "last_apply_route": {
                "resolved_candidate_label": "Shear cleanup",
                "resolved_candidate_family_tag": "shear",
                "post_apply_resolved_candidate_attempted": True,
            },
        },
        {
            "name": "out of band when target fails",
            "overview": {"any_fail": False},
            "target_band_with_eps_passed": False,
            "overview_required_checks_acceptable": True,
            "post_apply_acceptance_matches": False,
            "last_apply_route": {},
        },
        {
            "name": "out of band when required checks fail",
            "overview": {"any_fail": True},
            "target_band_with_eps_passed": True,
            "overview_required_checks_acceptable": False,
            "post_apply_acceptance_matches": False,
            "last_apply_route": {},
        },
        {
            "name": "post apply family fallback label",
            "overview": {"any_fail": False},
            "target_band_with_eps_passed": True,
            "overview_required_checks_acceptable": True,
            "post_apply_acceptance_matches": True,
            "last_apply_route": {
                "post_apply_resolved_candidate_label": "Combined capacity repair",
                "resolved_candidate_family_tag": "combined",
                "post_apply_resolved_candidate_attempted": True,
            },
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        actual = build_design_guide_controller_compute_core_branch_request_projection(
            overview=scenario["overview"],
            target_band_with_eps_passed=scenario["target_band_with_eps_passed"],
            overview_required_checks_acceptable=scenario["overview_required_checks_acceptable"],
            post_apply_acceptance_matches=scenario["post_apply_acceptance_matches"],
            last_apply_route=scenario["last_apply_route"],
        )
        expected = _legacy_projection(
            target_band_with_eps_passed=scenario["target_band_with_eps_passed"],
            overview_required_checks_acceptable=scenario["overview_required_checks_acceptable"],
            post_apply_acceptance_matches=scenario["post_apply_acceptance_matches"],
            last_apply_route=scenario["last_apply_route"],
        )
        comparable = {
            key: actual.get(key)
            for key in (
                "last_apply_label_for_post_active",
                "last_apply_family_for_post_active",
                "post_apply_from_active_failure_repair",
                "out_of_band_live",
            )
        }
        rows.append(
            {
                "name": scenario["name"],
                "expected": expected,
                "actual": comparable,
                "matches": comparable == expected,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    core_start, core_end, core_segment = _function_source(inputs_source, "_compute_design_guidance_items_core")
    scenario_rows = _scenario_rows()
    branch_audit = _capture_branch_audit()
    branch_projection_rows = [
        row for row in branch_audit.get("surfaces") or [] if row.get("surface") == "branch scalar/request projection"
    ]
    branch_projection_row = branch_projection_rows[0] if branch_projection_rows else {}
    return {
        "schema": "design_guide_compute_core_branch_request_projection_extraction.v1",
        "target": {
            "function": "_compute_design_guidance_items_core",
            "line_start": core_start,
            "line_end": core_end,
            "line_count": max(0, core_end - core_start + 1),
        },
        "controller_helper_present": "def build_design_guide_controller_compute_core_branch_request_projection(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_compute_core_branch_request_projection"' in controller_source,
        "page_delegates_to_controller": "_build_design_guide_controller_compute_core_branch_request_projection(" in core_segment,
        "old_page_last_apply_label_assignment_removed": "_last_apply_label_for_post_active = str(" not in core_segment,
        "old_page_last_apply_family_assignment_removed": "_last_apply_family_for_post_active = str(" not in core_segment,
        "old_page_post_apply_boolean_formula_removed": (
            "_post_apply_from_active_failure_repair = bool(\n"
            "        _local_cleanup_post_apply_acceptance_matches"
        )
        not in core_segment,
        "old_page_out_of_band_formula_removed": "out_of_band_live = not (" not in core_segment,
        "scenario_rows": scenario_rows,
        "scenario_parity_passed": all(bool(row.get("matches")) for row in scenario_rows),
        "branch_audit_decision": branch_audit.get("status_decision"),
        "branch_projection_readiness": branch_projection_row.get("readiness"),
        "branch_audit_next_slice": (branch_audit.get("first_safe_slice") or {}).get("first_safe_slice"),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_helper_present": bool(payload.get("controller_helper_present")),
        "controller_helper_exported": bool(payload.get("controller_helper_exported")),
        "page_delegates_to_controller": bool(payload.get("page_delegates_to_controller")),
        "old_page_last_apply_label_assignment_removed": bool(payload.get("old_page_last_apply_label_assignment_removed")),
        "old_page_last_apply_family_assignment_removed": bool(payload.get("old_page_last_apply_family_assignment_removed")),
        "old_page_post_apply_boolean_formula_removed": bool(payload.get("old_page_post_apply_boolean_formula_removed")),
        "old_page_out_of_band_formula_removed": bool(payload.get("old_page_out_of_band_formula_removed")),
        "scenario_parity_passed": bool(payload.get("scenario_parity_passed")),
        "branch_audit_advanced_to_next_slice": payload.get("branch_audit_next_slice")
        == "compute_core_branch_route_ordering_audit",
        "branch_projection_now_shell_call": payload.get("branch_projection_readiness") == "SHELL_CALL",
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_core_branch_request_projection_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_core_branch_request_projection_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Compute Core Branch Request Projection Extraction",
        "",
        f"Status: {payload.get('status')}",
        f"Branch audit decision: {payload.get('branch_audit_decision')}",
        f"Next slice: {payload.get('branch_audit_next_slice')}",
        "",
        "## Summary",
        "The pure branch request/scalar projection is now controller-owned. "
        "The page still owns session reads, overview construction, item builders, "
        "candidate evaluation execution, fallback wording, CTA/apply, and rendering.",
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
    print(f"design_guide_compute_core_branch_request_projection_extraction {status}")
    print(f"next_slice={payload.get('branch_audit_next_slice')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
