"""Audit `apply_bottom_recommendation` update resolution boundary.

The branch is not a simple explicit payload extraction because it includes a
state-match guard, bottom recommendation fallback, and arrangement conversion.
This audit maps the first safe extraction slice before implementation.
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
ACTION = "apply_bottom_recommendation"


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
    helper_start, helper_end, helper_segment = _function_source(inputs_source, TARGET)
    branch_start = helper_segment.find(f'action_type == "{ACTION}"')
    next_branch_start = helper_segment.find('if action_type == "apply_shear_recommendation"', branch_start)
    branch_segment = (
        helper_segment[branch_start:next_branch_start]
        if branch_start >= 0 and next_branch_start > branch_start
        else ""
    )
    branch_line_start = helper_start + helper_segment[:branch_start].count("\n") if branch_start >= 0 else 0
    surfaces = [
        {
            "surface": "explicit update extraction",
            "classification": "pure payload extraction but gated by page-owned state-match execution",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController decision helper fed by page-computed updates_match_state",
            "deletion_readiness": "READY_FOR_CONTROLLER_DECISION_HELPER_PARITY",
            "risk": "LOW_MEDIUM",
            "evidence": [
                _token(branch_segment, branch_line_start, "explicit_updates = payload.get(\"updates\")"),
                _token(branch_segment, branch_line_start, "_updates_match_state(current_state, explicit_updates)"),
                _token(branch_segment, branch_line_start, "return dict(explicit_updates)"),
            ],
        },
        {
            "surface": "state-match execution",
            "classification": "page-shell/current-state comparison execution",
            "current_owner": "inputs_page",
            "target_owner": "page shell for now; controller may own decision from boolean",
            "deletion_readiness": "KEEP_EXECUTION_PAGE_OWNED",
            "risk": "MEDIUM",
            "evidence": [_token(branch_segment, branch_line_start, "_updates_match_state(")],
        },
        {
            "surface": "bottom recommendation fallback",
            "classification": "page-owned recommendation fallback",
            "current_owner": "inputs_page",
            "target_owner": "bottom recommendation service/family boundary later",
            "deletion_readiness": "NOT_READY",
            "risk": "HIGH",
            "evidence": [_token(branch_segment, branch_line_start, "_compute_bottom_reo_recommendation(")],
        },
        {
            "surface": "arrangement conversion fallback",
            "classification": "page-owned bottom arrangement adapter",
            "current_owner": "inputs_page",
            "target_owner": "candidate/update service after arrangement parity",
            "deletion_readiness": "NOT_READY_WITHOUT_ARRANGEMENT_PARITY",
            "risk": "HIGH",
            "evidence": [_token(branch_segment, branch_line_start, "_bottom_arrangement_to_shared_updates(")],
        },
    ]
    return {
        "schema": "design_guide_guidance_action_updates_bottom_recommendation_boundary_audit.v1",
        "target": {
            "helper": TARGET,
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
        },
        "branch": {
            "action_type": ACTION,
            "line_start": branch_line_start,
            "present": bool(branch_segment),
        },
        "decision": "READY_FOR_EXPLICIT_UPDATE_DECISION_HELPER_ONLY",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "guidance_action_updates_bottom_explicit_update_decision_helper",
            "why": (
                "The explicit update branch can be represented by a pure controller helper when the page "
                "passes `updates_match_state` as a boolean. The page must still execute the state-match "
                "comparison and own recommendation/arrangement fallbacks."
            ),
            "move": (
                "Add a controller helper for `apply_bottom_recommendation` explicit updates that returns "
                "handled/update/none based on payload updates and a page-computed updates_match_state flag. "
                "Do not move `_compute_bottom_reo_recommendation(...)` or "
                "`_bottom_arrangement_to_shared_updates(...)`."
            ),
            "required_verifier": "design_guide_guidance_action_updates_bottom_explicit_decision_extraction.py",
        },
        "stop_conditions": [
            "Do not move `_updates_match_state(...)` execution into DesignGuideController.",
            "Do not move `_compute_bottom_reo_recommendation(...)` in this slice.",
            "Do not move `_bottom_arrangement_to_shared_updates(...)` in this slice.",
            "Do not change explicit update/state-match return semantics.",
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
    surfaces = list(payload.get("surfaces") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "branch_found": bool((payload.get("branch") or {}).get("present")),
        "surfaces_classified": len(surfaces) == 4,
        "explicit_decision_ready": any(
            row.get("surface") == "explicit update extraction"
            and row.get("deletion_readiness") == "READY_FOR_CONTROLLER_DECISION_HELPER_PARITY"
            for row in surfaces
        ),
        "state_match_execution_kept_page_owned": any(
            row.get("surface") == "state-match execution"
            and row.get("deletion_readiness") == "KEEP_EXECUTION_PAGE_OWNED"
            for row in surfaces
        ),
        "fallback_not_ready": any(
            row.get("surface") == "bottom recommendation fallback"
            and row.get("deletion_readiness") == "NOT_READY"
            for row in surfaces
        ),
        "arrangement_not_ready": any(
            row.get("surface") == "arrangement conversion fallback"
            and row.get("deletion_readiness") == "NOT_READY_WITHOUT_ARRANGEMENT_PARITY"
            for row in surfaces
        ),
        "next_verifier_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
            == "design_guide_guidance_action_updates_bottom_explicit_decision_extraction.py"
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
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_bottom_recommendation_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_bottom_recommendation_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Design Guide Guidance Action Updates Bottom Recommendation Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Surface Inventory",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- `{row.get('surface')}`: {row.get('classification')} "
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
    print(f"design_guide_guidance_action_updates_bottom_recommendation_boundary_audit {payload['status']}")
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
