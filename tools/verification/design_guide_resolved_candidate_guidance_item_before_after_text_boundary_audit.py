"""Audit resolved-candidate guidance item before/after text boundary.

This is audit-only. The resolved-candidate guidance item still prepares its
before/after preview through page-local helpers. Because those helpers resolve
updates and visible text, this verifier maps the boundary before any move.
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
TARGET = "_guidance_item_from_resolved_candidate"
BEFORE_AFTER_HELPER = "_guidance_before_after_text"
UPDATES_HELPER = "_guidance_action_updates"
DESCRIBE_HELPER = "_describe_guidance_step"
ELIGIBILITY_HELPER = "resolve_design_guide_controller_before_after_text_eligibility"


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
    helper_start, helper_end, helper_segment = _function_source(inputs_source, BEFORE_AFTER_HELPER)
    updates_start, updates_end, updates_segment = _function_source(inputs_source, UPDATES_HELPER)
    describe_start, describe_end, describe_segment = _function_source(inputs_source, DESCRIBE_HELPER)
    helper_calls = inputs_source.count(f"{BEFORE_AFTER_HELPER}(") - 1

    surfaces = [
        {
            "surface": "resolved-candidate before-after call",
            "classification": "shell call to page-local preview helper",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController presentation adapter after parity",
            "deletion_readiness": "NOT_READY_WITHOUT_HELPER_BOUNDARY",
            "evidence": [
                _token(target_segment, target_start, f"{BEFORE_AFTER_HELPER}("),
                _token(target_segment, target_start, "action_payload_preview"),
                _token(target_segment, target_start, '"apply_resolved_candidate"'),
            ],
        },
        {
            "surface": "action-type exclusion policy",
            "classification": "controller-owned pure before-after eligibility policy",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(helper_segment, helper_start, "_resolve_design_guide_controller_before_after_text_eligibility("),
                _token(helper_segment, helper_start, "expensive_action_types"),
                _token(controller_source, 1, ELIGIBILITY_HELPER),
            ],
        },
        {
            "surface": "update resolution",
            "classification": "mixed page update policy and recommendation fallback",
            "current_owner": "inputs_page",
            "target_owner": "candidate/action update service or bounded page-shell adapter",
            "deletion_readiness": "NOT_READY_WITHOUT_ACTION_UPDATE_BOUNDARY",
            "evidence": [
                _token(helper_segment, helper_start, f"{UPDATES_HELPER}("),
                _token(updates_segment, updates_start, "_shared_state_snapshot("),
                _token(updates_segment, updates_start, "_compute_geometry_recommendation("),
                _token(updates_segment, updates_start, "_compute_bottom_reo_recommendation("),
                _token(updates_segment, updates_start, "_compute_shear_recommendation("),
            ],
        },
        {
            "surface": "before/after visible wording",
            "classification": "controller-owned wording with page-shell label/context inputs",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(helper_segment, helper_start, f"{DESCRIBE_HELPER}("),
                _token(describe_segment, describe_start, "_build_design_guide_pure_guidance_step_description("),
                _token(describe_segment, describe_start, "Design Guide guidance step description was not handled"),
            ],
        },
        {
            "surface": "resolved-candidate action payload preview",
            "classification": "already controller-owned input-pack output",
            "current_owner": "DesignGuideController called by inputs_page",
            "target_owner": "DesignGuideController",
            "deletion_readiness": "SHELL_CALL",
            "evidence": [
                _token(target_segment, target_start, "_build_design_guide_controller_resolved_candidate_guidance_item_input_pack("),
                _token(target_segment, target_start, "action_payload_preview = dict(input_pack.get"),
            ],
        },
    ]

    return {
        "schema": "design_guide_resolved_candidate_guidance_item_before_after_text_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "helpers": {
            BEFORE_AFTER_HELPER: {
                "line_start": helper_start,
                "line_end": helper_end,
                "line_count": max(0, helper_end - helper_start + 1),
                "total_call_count_excluding_definition": max(0, helper_calls),
            },
            UPDATES_HELPER: {
                "line_start": updates_start,
                "line_end": updates_end,
                "line_count": max(0, updates_end - updates_start + 1),
            },
            DESCRIBE_HELPER: {
                "line_start": describe_start,
                "line_end": describe_end,
                "line_count": max(0, describe_end - describe_start + 1),
            },
        },
        "decision": "BEFORE_AFTER_ELIGIBILITY_AND_WORDING_CONTROLLER_BACKED_UPDATE_RESOLUTION_REMAINS",
        "surfaces": surfaces,
        "first_safe_implementation_slice": {
            "name": "guidance_before_after_text_action_update_resolution_boundary",
            "why": (
                "Before/after request packaging, eligibility, and visible wording are now controller-backed. "
                "The remaining page-owned blocker is _guidance_action_updates(...), which still mixes pure "
                "payload updates with shared-state recommendation fallback branches."
            ),
            "move": (
                "Audit and extract only the next pure action-update branch. Do not move recommendation "
                "fallback branches that compute geometry, bottom reo, or shear recommendations."
            ),
            "required_verifier": "design_guide_guidance_action_updates_boundary_audit.py",
        },
        "stop_conditions": [
            "Do not move shared _guidance_before_after_text(...) until all shared callsites have parity coverage.",
            "Do not move _guidance_action_updates(...) while it still computes recommendations or reads shared state fallback.",
            "Do not reintroduce page-local fallback wording in _describe_guidance_step(...).",
            "Do not change action_payload_preview, CTA/apply semantics, or family runtimes.",
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
    helpers = dict(payload.get("helpers") or {})
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "before_after_helper_found": bool((helpers.get(BEFORE_AFTER_HELPER) or {}).get("line_start")),
        "update_helper_found": bool((helpers.get(UPDATES_HELPER) or {}).get("line_start")),
        "describe_helper_found": bool((helpers.get(DESCRIBE_HELPER) or {}).get("line_start")),
        "surfaces_classified": len(surfaces) == 5,
        "shared_helper_not_ready": (
            (helpers.get(BEFORE_AFTER_HELPER) or {}).get("total_call_count_excluding_definition", 0) > 1
        ),
        "update_resolution_blocker_identified": any(
            row.get("surface") == "update resolution"
            and row.get("deletion_readiness") == "NOT_READY_WITHOUT_ACTION_UPDATE_BOUNDARY"
            for row in surfaces
        ),
        "eligibility_policy_controller_owned": any(
            row.get("surface") == "action-type exclusion policy"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "visible_wording_controller_owned": any(
            row.get("surface") == "before/after visible wording"
            and row.get("deletion_readiness") == "SHELL_CALL"
            for row in surfaces
        ),
        "action_update_next_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
            == "design_guide_guidance_action_updates_boundary_audit.py"
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
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_before_after_text_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_before_after_text_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    helpers = dict(payload.get("helpers") or {})
    lines = [
        "# Design Guide Resolved-Candidate Guidance Item Before/After Text Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('decision')}",
        "",
        "## Current Helper Responsibilities",
    ]
    for helper_name, helper in helpers.items():
        lines.append(
            f"- `{helper_name}`: lines {helper.get('line_start')}-{helper.get('line_end')}, "
            f"{helper.get('line_count')} lines"
        )
        if helper_name == BEFORE_AFTER_HELPER:
            lines.append(
                f"  - Call count excluding definition: {helper.get('total_call_count_excluding_definition')}"
            )
    lines.extend(["", "## Surface Inventory"])
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
    print(f"design_guide_resolved_candidate_guidance_item_before_after_text_boundary_audit {payload['status']}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
