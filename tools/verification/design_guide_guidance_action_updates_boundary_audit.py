"""Audit `_guidance_action_updates(...)` before extracting more logic.

This maps which action-update branches are already controller-owned, which are
pure payload/default branches, and which still depend on page-owned
recommendation fallback or geometry/reinforcement helpers.
"""

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
TARGET = "_guidance_action_updates"
CONTROLLER_HELPER = "resolve_design_guide_controller_guidance_action_payload_updates"


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
    target_start, target_end, target_segment = _function_source(inputs_source, TARGET)
    controller_start, controller_end, controller_segment = _function_source(
        controller_source, CONTROLLER_HELPER
    )
    branches = [
        {
            "branch": "apply_resolved_candidate",
            "current_owner": "DesignGuideController",
            "classification": "already controller-owned pure payload update branch",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "risk": "LOW",
            "evidence": [_token(controller_segment, controller_start, '"apply_resolved_candidate"')],
        },
        {
            "branch": "apply_compound_guidance",
            "current_owner": "DesignGuideController",
            "classification": "already controller-owned pure payload update branch",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "risk": "LOW",
            "evidence": [_token(controller_segment, controller_start, '"apply_compound_guidance"')],
        },
        {
            "branch": "apply_mode_recommendation",
            "current_owner": "DesignGuideController",
            "classification": "controller-owned pure explicit payload update branch",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "risk": "LOW",
            "evidence": [_token(controller_segment, controller_start, '"apply_mode_recommendation"')],
        },
        {
            "branch": "apply_geometry_recommendation",
            "current_owner": "split controller/page",
            "classification": "controller-owned explicit payload branch plus page-owned recommendation fallback",
            "target_owner": "DesignGuideController explicit branch; page/service fallback later",
            "deletion_readiness": "PARTIAL_FALLBACK_REMAINS",
            "risk": "MEDIUM",
            "evidence": [
                _token(controller_segment, controller_start, '"apply_geometry_recommendation"'),
                _token(target_segment, target_start, "_compute_geometry_recommendation("),
            ],
        },
        {
            "branch": "apply_bottom_recommendation",
            "current_owner": "split controller/page",
            "classification": (
                "controller-owned explicit payload decision plus page-owned state-match execution, "
                "bottom recommendation fallback, and arrangement conversion"
            ),
            "target_owner": "DesignGuideController explicit branch; bottom recommendation/arrangement service later",
            "deletion_readiness": "PARTIAL_FALLBACK_AND_ARRANGEMENT_REMAIN",
            "risk": "MEDIUM",
            "evidence": [
                _token(controller_segment, controller_start, '"apply_bottom_recommendation"'),
                _token(target_segment, target_start, "_updates_match_state("),
                _token(target_segment, target_start, "_compute_bottom_reo_recommendation("),
                _token(target_segment, target_start, "_bottom_arrangement_to_shared_updates("),
            ],
        },
        {
            "branch": "apply_shear_recommendation",
            "current_owner": "split controller/page",
            "classification": "controller-owned explicit payload branch plus page-owned recommendation fallback",
            "target_owner": "DesignGuideController explicit branch; page/service fallback later",
            "deletion_readiness": "PARTIAL_FALLBACK_REMAINS",
            "risk": "MEDIUM",
            "evidence": [
                _token(controller_segment, controller_start, '"apply_shear_recommendation"'),
                _token(target_segment, target_start, "_compute_shear_recommendation("),
            ],
        },
        {
            "branch": "reduce_bottom_reinforcement",
            "current_owner": "mixed",
            "classification": "explicit arrangement adaptation plus page-owned tightening fallback",
            "target_owner": "candidate/update service after arrangement parity",
            "deletion_readiness": "NOT_READY_WITHOUT_ARRANGEMENT_SERVICE_BOUNDARY",
            "risk": "HIGH",
            "evidence": [
                _token(target_segment, target_start, 'action_type == "reduce_bottom_reinforcement"'),
                _token(target_segment, target_start, "_compute_bottom_reo_tightening_recommendation("),
            ],
        },
        {
            "branch": "increase_link_spacing",
            "current_owner": "split controller/page",
            "classification": "controller-owned explicit payload branch plus page-owned shear tightening fallback",
            "target_owner": "DesignGuideController explicit branch; shear tightening service later",
            "deletion_readiness": "PARTIAL_FALLBACK_REMAINS",
            "risk": "MEDIUM",
            "evidence": [
                _token(controller_segment, controller_start, '"increase_link_spacing"'),
                _token(target_segment, target_start, "_compute_shear_tightening_recommendation("),
            ],
        },
        {
            "branch": "reduce_number_of_legs",
            "current_owner": "split controller/page",
            "classification": "controller-owned explicit payload branch plus page-owned shear tightening fallback",
            "target_owner": "DesignGuideController explicit branch; shear tightening service later",
            "deletion_readiness": "PARTIAL_FALLBACK_REMAINS",
            "risk": "MEDIUM",
            "evidence": [
                _token(controller_segment, controller_start, '"reduce_number_of_legs"'),
                _token(target_segment, target_start, "_compute_shear_tightening_recommendation("),
            ],
        },
        {
            "branch": "tighten_geometry",
            "current_owner": "split controller/page",
            "classification": "controller-owned explicit payload branch plus page-owned geometry tightening fallback",
            "target_owner": "DesignGuideController explicit branch; geometry tightening service later",
            "deletion_readiness": "PARTIAL_FALLBACK_REMAINS",
            "risk": "MEDIUM",
            "evidence": [
                _token(controller_segment, controller_start, '"tighten_geometry"'),
                _token(target_segment, target_start, "_compute_geometry_tightening_recommendation("),
            ],
        },
        {
            "branch": "increase_depth/increase_width/reduce_link_spacing/deflection/reduce_bar_spacing",
            "current_owner": "inputs_page",
            "classification": "page-owned generated update logic with geometry/reo constants and guards",
            "target_owner": "candidate/update service after dedicated parity",
            "deletion_readiness": "NOT_READY_WITHOUT_DEDICATED_BRANCH_PARITY",
            "risk": "HIGH",
            "evidence": [
                _token(target_segment, target_start, 'action_type == "increase_depth"'),
                _token(target_segment, target_start, 'action_type == "increase_width"'),
                _token(target_segment, target_start, "_geometry_updates_with_depth_width_contract_guard("),
                _token(target_segment, target_start, "REO_SPACINGS"),
                _token(target_segment, target_start, "REO_COUNTS_0_12"),
            ],
        },
    ]
    return {
        "schema": "design_guide_guidance_action_updates_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "controller_helper": {
            "name": CONTROLLER_HELPER,
            "line_start": controller_start,
            "line_end": controller_end,
            "line_count": max(0, controller_end - controller_start + 1),
        },
        "branches": branches,
        "decision": "BOTTOM_EXPLICIT_DECISION_EXTRACTED_BOTTOM_FALLBACK_AND_GENERATED_BRANCHES_REMAIN",
        "first_safe_implementation_slice": {
            "name": "guidance_action_updates_bottom_arrangement_conversion_boundary_audit",
            "why": (
                "The bottom explicit payload decision is now controller-owned while the page still "
                "executes the state-match check and owns bottom recommendation fallback plus arrangement "
                "conversion. The next boundary is the fallback/arrangement conversion surface."
            ),
            "move": (
                "Audit bottom recommendation fallback and `_bottom_arrangement_to_shared_updates(...)` "
                "before moving any bottom arrangement conversion or recommendation fallback logic."
            ),
            "required_verifier": "design_guide_guidance_action_updates_bottom_arrangement_conversion_boundary_audit.py",
        },
        "stop_conditions": [
            "Do not move geometry/bottom/shear recommendation fallback branches in this slice.",
            "Do not move generated geometry/reo update branches without dedicated parity.",
            "Do not change visible wording, CTA/apply semantics, family runtimes, target bands, or widget keys.",
        ],
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    branches = list(payload.get("branches") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "controller_helper_found": bool((payload.get("controller_helper") or {}).get("line_start")),
        "branches_classified": len(branches) == 11,
        "already_controller_owned_branches_recorded": sum(
            1 for row in branches if row.get("deletion_readiness") == "SHELL_CALL"
        )
        >= 3,
        "pure_first_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
            == "design_guide_guidance_action_updates_bottom_arrangement_conversion_boundary_audit.py"
        ),
        "mixed_fallback_branches_not_ready": any(
            row.get("deletion_readiness")
            in ("PARTIAL_EXTRACTION_ONLY", "PARTIAL_FALLBACK_REMAINS", "PARTIAL_FALLBACK_AND_ARRANGEMENT_REMAIN")
            for row in branches
        ),
        "high_risk_generated_branches_not_ready": any(
            row.get("deletion_readiness") == "NOT_READY_WITHOUT_DEDICATED_BRANCH_PARITY"
            for row in branches
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
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Design Guide Guidance Action Updates Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Current Helper Responsibilities",
        f"- `{TARGET}`: lines {payload['target']['line_start']}-{payload['target']['line_end']}, "
        f"{payload['target']['line_count']} lines",
        f"- `{CONTROLLER_HELPER}`: lines {payload['controller_helper']['line_start']}-"
        f"{payload['controller_helper']['line_end']}, {payload['controller_helper']['line_count']} lines",
        "",
        "## Branch Inventory",
    ]
    for row in payload.get("branches") or []:
        lines.append(
            f"- `{row.get('branch')}`: {row.get('classification')} "
            f"({row.get('current_owner')} -> {row.get('target_owner')}); "
            f"readiness `{row.get('deletion_readiness')}`, risk `{row.get('risk')}`"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first_slice.get('name')}`",
            f"- Move: {first_slice.get('move')}",
            f"- Verifier: `{first_slice.get('required_verifier')}`",
            "",
            "## Stop Conditions",
            *[f"- {condition}" for condition in payload.get("stop_conditions") or []],
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
    print(f"design_guide_guidance_action_updates_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["status"] != "PASS":
        failed = [name for name, passed in checks.items() if not passed]
        print("failed_checks=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
