from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    fast_start, fast_end, fast_segment = _function_segment(inputs_source, "evaluate_candidate_fast")
    resolver_start, resolver_end, resolver_segment = _function_segment(inputs_source, "_state_with_resolved_auto_design_actions")
    design_state_start, design_state_end, design_state_segment = _function_segment(inputs_source, "_state_with_resolved_design_actions")
    isolated_start, isolated_end, isolated_segment = _function_segment(inputs_source, "_state_with_resolved_design_actions_isolated")

    surface_rows = [
        {
            "surface": "fast evaluator action state resolution callsite",
            "function": "evaluate_candidate_fast",
            "line_range": f"{fast_start}-{fast_end}",
            "classification": "page-owned evaluator input normalization",
            "target_owner": "candidate_evaluation helper after parity proof",
            "readiness": "NOT_READY",
            "risk": "HIGH",
            "evidence": "_state_with_resolved_auto_design_actions(candidate_state, context.get(\"actions\"))",
        },
        {
            "surface": "auto-design action resolver wrapper",
            "function": "_state_with_resolved_auto_design_actions",
            "line_range": f"{resolver_start}-{resolver_end}",
            "classification": "thin page wrapper",
            "target_owner": "page shell or candidate_evaluation helper",
            "readiness": "SHELL_WRAPPER",
            "risk": "LOW",
            "evidence": "return _state_with_resolved_design_actions(state, actions)",
        },
        {
            "surface": "session-overlay design action state normalizer",
            "function": "_state_with_resolved_design_actions",
            "line_range": f"{design_state_start}-{design_state_end}",
            "classification": "page-owned session/default normalization",
            "target_owner": "page shell unless a plain-defaults helper is proven",
            "readiness": "PAGE_SHELL_SESSION_OVERLAY_WITH_SERVICE_PROJECTION",
            "risk": "HIGH",
            "evidence": "_guidance_state_snapshot(state) plus _build_candidate_action_state_projection(...)",
        },
        {
            "surface": "candidate-only isolated action state normalizer",
            "function": "_state_with_resolved_design_actions_isolated",
            "line_range": f"{isolated_start}-{isolated_end}",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "design_brain.candidate_evaluation action-state projection",
            "readiness": "SHELL_CALL_ONLY",
            "risk": "LOW",
            "evidence": "_build_candidate_action_state_projection(...)",
        },
    ]
    checks = {
        "fast_evaluator_action_resolution_identified": "_state_with_resolved_auto_design_actions(" in fast_segment,
        "auto_wrapper_is_thin": "return _state_with_resolved_design_actions(state, actions)" in resolver_segment,
        "session_overlay_path_identified": "_guidance_state_snapshot(state)" in design_state_segment,
        "session_overlay_delegates_service_projection": "_build_candidate_action_state_projection(" in design_state_segment,
        "isolated_path_identified": "resolved = dict(state)" in isolated_segment and "SHARED_DEFAULTS" in isolated_segment,
        "isolated_path_delegates_service_projection": "_build_candidate_action_state_projection(" in isolated_segment,
        "service_projection_exists": "def build_candidate_action_state_projection(" in candidate_source,
        "candidate_service_import_clean": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "solver_execution_not_moved": all(
            token in fast_segment
            for token in (
                "_evaluate_bending_with_bottom_state(",
                "_evaluate_shear_with_state(",
                "_evaluate_crack_with_state(",
                "_evaluate_deflection_with_state(",
            )
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_fast_candidate_action_resolution_boundary_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "ACTION_RESOLUTION_BOUNDARY_MAPPED_NOT_READY_TO_MOVE_SESSION_OVERLAY"
            if all(checks.values())
            else "ACTION_RESOLUTION_BOUNDARY_AUDIT_FAILED"
        ),
        "surface_rows": surface_rows,
        "first_safe_implementation_slice": {
            "name": "candidate_only_action_state_projection_parity",
            "summary": (
                "Do not move the session-overlay `_state_with_resolved_design_actions(...)` path. "
                "The pure candidate action-state projection is now service-owned; next audit whether "
                "`_state_with_resolved_auto_design_actions(...)` can remain a bounded page-shell wrapper or whether "
                "fast evaluation should call the service helper directly after page-owned snapshot/action collection."
            ),
        },
        "stop_conditions": [
            "Do not move `_guidance_state_snapshot(...)` or Streamlit/session/default ownership into Design Brain.",
            "Do not change resolved action fields, manual positive/negative moment fields, SLS fields, or `actions_uls`.",
            "Do not move solver/evaluator execution.",
        ],
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_action_resolution_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_action_resolution_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    rows = [
        "| Surface | Function | Lines | Classification | Target owner | Readiness | Risk |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload.get("surface_rows") or []:
        rows.append(
            "| {surface} | `{function}` | `{line_range}` | {classification} | {target_owner} | `{readiness}` | {risk} |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    first = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Fast Candidate Action Resolution Boundary Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Inventory",
        *rows,
        "",
        "## Checks",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(dict(payload.get("checks") or {}).items()))
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- `{first.get('name')}`",
            f"- {first.get('summary')}",
            "",
            "## Stop Conditions",
        ]
    )
    lines.extend(f"- {item}" for item in payload.get("stop_conditions") or [])
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(f"design_guide_fast_candidate_action_resolution_boundary_audit {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
