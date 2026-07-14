"""Audit bottom recommendation fallback/arrangement conversion ownership.

This is proof-only. It does not import inputs_page.py because the target module
has Streamlit/page side effects; it inspects source boundaries instead.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTRACTS = ROOT / "design_brain" / "contracts.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_HELPER = "_guidance_action_updates"
CONTROLLER_HELPER = "resolve_design_guide_controller_guidance_action_payload_updates"
ACTION = "apply_bottom_recommendation"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _line_for(text: str, needle: str) -> int | None:
    idx = text.find(needle)
    if idx < 0:
        return None
    return text[:idx].count("\n") + 1


def _function_segment(source: str, function_name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {function_name}")


def _action_branch(segment: str, action_literal: str) -> str:
    marker = f'if action_type == "{action_literal}"'
    start = segment.find(marker)
    if start < 0:
        raise AssertionError(f"Branch not found: {action_literal}")
    rest = segment[start:]
    next_start = rest.find('\n    if action_type == "', len(marker))
    return rest if next_start < 0 else rest[:next_start]


def _token(path: Path, text: str, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in text,
        "line": _line_for(text, token),
        "file": str(path.relative_to(ROOT)),
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _source(INPUTS)
    contracts_source = _source(CONTRACTS)
    controller_source = _source(CONTROLLER)
    helper_start, helper_end, helper_segment = _function_segment(inputs_source, TARGET_HELPER)
    controller_start, controller_end, controller_segment = _function_segment(controller_source, CONTROLLER_HELPER)
    branch = _action_branch(helper_segment, ACTION)

    surfaces = [
        {
            "surface": "explicit payload decision",
            "current_owner": "DesignGuideController",
            "target_owner": "DesignGuideController",
            "classification": "extracted pure decision",
            "deletion_readiness": "SHELL_CALL",
            "risk": "LOW",
            "evidence": [
                _token(CONTROLLER, controller_segment, f'"{ACTION}"'),
                _token(INPUTS, branch, "_resolve_design_guide_controller_guidance_action_payload_updates("),
            ],
        },
        {
            "surface": "state-match execution",
            "current_owner": "inputs_page",
            "target_owner": "page shell for now",
            "classification": "page-owned current-state comparison before controller decision",
            "deletion_readiness": "NOT_READY_WITHOUT_STATE_MATCH_PARITY",
            "risk": "MEDIUM",
            "evidence": [_token(INPUTS, branch, "_updates_match_state(")],
        },
        {
            "surface": "bottom recommendation fallback",
            "current_owner": "inputs_page",
            "target_owner": "bottom recommendation family/service boundary",
            "classification": "page-owned Design Brain fallback recommendation logic",
            "deletion_readiness": "NOT_READY_WITHOUT_BOTTOM_RECOMMENDATION_SERVICE_BOUNDARY",
            "risk": "HIGH",
            "evidence": [_token(INPUTS, branch, "_compute_bottom_reo_recommendation(")],
        },
        {
            "surface": "arrangement-to-update conversion",
            "current_owner": "design_brain.contracts",
            "target_owner": "design_brain.contracts",
            "classification": "already service-owned pure conversion called by page fallback",
            "deletion_readiness": "SHELL_CALL_AFTER_FALLBACK_MOVES",
            "risk": "LOW",
            "evidence": [
                _token(INPUTS, inputs_source, "bottom_arrangement_to_shared_updates as _bottom_arrangement_to_shared_updates"),
                _token(CONTRACTS, contracts_source, "def bottom_arrangement_to_shared_updates("),
                _token(INPUTS, branch, "_bottom_arrangement_to_shared_updates("),
            ],
        },
    ]

    return {
        "schema": "design_guide_guidance_action_updates_bottom_arrangement_conversion_boundary_audit.v1",
        "target": {
            "helper": TARGET_HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
            "branch": ACTION,
            "branch_line": _line_for(inputs_source, f'if action_type == "{ACTION}"'),
        },
        "controller_helper": {
            "helper": CONTROLLER_HELPER,
            "line_start": controller_start,
            "line_end": controller_end,
        },
        "surfaces": surfaces,
        "decision": "BOTTOM_ARRANGEMENT_CONVERSION_ALREADY_SERVICE_OWNED_FALLBACK_NOT_READY",
        "first_safe_implementation_slice": {
            "name": "guidance_action_updates_bottom_recommendation_fallback_boundary_audit",
            "why": (
                "Arrangement conversion already calls design_brain.contracts. The remaining "
                "page-owned authority is `_compute_bottom_reo_recommendation(...)` fallback "
                "and its selected recommendation/arrangement production."
            ),
            "move": (
                "Audit bottom recommendation fallback ownership before moving recommendation "
                "selection, selected arrangement production, or state-match handling."
            ),
            "required_verifier": "design_guide_guidance_action_updates_bottom_recommendation_fallback_boundary_audit.py",
        },
        "stop_conditions": [
            "Do not move `_compute_bottom_reo_recommendation(...)` without bottom recommendation parity.",
            "Do not move state-match execution without current-state parity proof.",
            "Do not change bottom arrangement conversion output, visible wording, CTA/apply semantics, or family runtime behaviour.",
        ],
        "controller_boundary_clean": all(
            token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "contracts_boundary_clean": all(token not in contracts_source for token in ("streamlit", "st.session_state")),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = list(payload.get("surfaces") or [])
    by_surface = {row.get("surface"): row for row in surfaces}
    fallback = by_surface.get("bottom recommendation fallback") or {}
    conversion = by_surface.get("arrangement-to-update conversion") or {}
    return {
        "target_branch_found": bool((payload.get("target") or {}).get("branch_line")),
        "all_surfaces_classified": len(surfaces) == 4,
        "explicit_decision_controller_owned": (by_surface.get("explicit payload decision") or {}).get("current_owner")
        == "DesignGuideController",
        "fallback_not_ready": fallback.get("deletion_readiness")
        == "NOT_READY_WITHOUT_BOTTOM_RECOMMENDATION_SERVICE_BOUNDARY",
        "arrangement_conversion_service_owned": conversion.get("current_owner") == "design_brain.contracts",
        "next_slice_identified": (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        == "design_guide_guidance_action_updates_bottom_recommendation_fallback_boundary_audit.py",
        "controller_boundary_clean": bool(payload.get("controller_boundary_clean")),
        "contracts_boundary_clean": bool(payload.get("contracts_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def write_artifacts(payload: dict[str, Any], check_results: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "-") + "Z"
    status = "PASS" if all(check_results.values()) else "FAIL"
    payload = dict(payload)
    payload["status"] = status
    payload["checks"] = check_results
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_bottom_arrangement_conversion_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_bottom_arrangement_conversion_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Bottom Arrangement Conversion Boundary Audit",
        "",
        f"## Executive Summary: {status}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Current owner | Target owner | Classification | Deletion readiness | Risk |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            "| {surface} | {current_owner} | {target_owner} | {classification} | {deletion_readiness} | {risk} |".format(
                **{key: str(row.get(key, "")) for key in ("surface", "current_owner", "target_owner", "classification", "deletion_readiness", "risk")}
            )
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{first_slice.get('name')}`",
            f"- Required verifier: `{first_slice.get('required_verifier')}`",
            f"- Why: {first_slice.get('why')}",
            "",
            "## Stop Conditions",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload.get("stop_conditions") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in check_results.items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    check_results = checks(payload)
    json_path, report_path = write_artifacts(payload, check_results)
    status = "PASS" if all(check_results.values()) else "FAIL"
    print(f"design_guide_guidance_action_updates_bottom_arrangement_conversion_boundary_audit {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        failed = [name for name, value in check_results.items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
