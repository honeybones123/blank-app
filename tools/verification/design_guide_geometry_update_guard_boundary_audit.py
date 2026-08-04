"""Audit geometry state update and depth/width guard boundary.

Proof-only. This identifies what remains page-owned around
_geometry_state_with_updates(...) before moving geometry lane candidate
generation.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
GEOMETRY_RATIO = ROOT / "design_brain" / "families" / "bending_fail_governs" / "geometry_ratio.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(node.end_lineno or node.lineno)
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _count_callers(source: str, name: str) -> int:
    return max(0, source.count(f"{name}(") - source.count(f"def {name}("))


def _called_names(segment: str) -> list[str]:
    tree = ast.parse(segment)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return sorted(names)


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    family_source = _read(GEOMETRY_RATIO)
    state_start, state_end, state_source = _function_source(inputs_source, "_geometry_state_with_updates")
    guard_start, guard_end, guard_source = _function_source(inputs_source, "_geometry_updates_with_depth_width_contract_guard")
    projection_start, projection_end, projection_source = _function_source(
        candidate_source,
        "build_geometry_update_projection",
    )
    family_guard_start, family_guard_end, family_guard_source = _function_source(
        family_source,
        "guard_bending_depth_width_geometry_update",
    )

    checks = {
        "state_helper_uses_service_width_context_wrapper": "_resolve_geometry_width_context(base_state)" in state_source,
        "state_helper_delegates_projection": "_build_geometry_update_projection(" in state_source,
        "projection_helper_rounds_depth_to_10mm": 'raw_updates["D"] = float(int(round(max(min_depth' in projection_source,
        "projection_helper_rounds_width_to_10mm": "resolved_width = float(int(round(max(min_width" in projection_source,
        "projection_helper_mirrors_non_b_width_to_b": 'if resolved_width_key != "b":' in projection_source and 'raw_updates["b"] = resolved_width' in projection_source,
        "state_helper_calls_page_guard_wrapper": "_geometry_updates_with_depth_width_contract_guard(" in state_source,
        "guard_wrapper_calls_family_policy": "_guard_bending_depth_width_geometry_update(" in guard_source,
        "guard_wrapper_extracts_width_lock": "_geometry_width_lock_enabled(base)" in guard_source,
        "guard_wrapper_uses_family_min_width_input": "minimum_practical_width=GUIDANCE_MIN_PRACTICAL_WIDTH_MM" in guard_source,
        "projection_helper_has_no_family_guard_call": "_guard_bending_depth_width_geometry_update" not in projection_source
        and "guard_bending_depth_width_geometry_update" not in projection_source,
        "projection_helper_has_no_inputs_page_import": "inputs_page" not in candidate_source,
        "projection_helper_has_no_streamlit_import": "streamlit" not in candidate_source and "st." not in projection_source,
        "family_policy_is_design_brain_owned": "def guard_bending_depth_width_geometry_update(" in family_source,
        "family_policy_has_no_inputs_page_import": "inputs_page" not in family_source,
        "family_policy_has_no_streamlit_import": "streamlit" not in family_source and "st." not in family_guard_source,
    }

    status = "PASS" if all(checks.values()) else "FAIL"
    decision = "NOT_READY_UPDATE_PROJECTION_BOUNDARY_REQUIRED" if status == "PASS" else "AUDIT_INCOMPLETE"
    return {
        "status": status,
        "surface": "geometry_update_guard_boundary",
        "decision": decision,
        "product_behavior_changed": False,
        "extraction_complete_estimate": "99%",
        "state_helper": {
            "function": "_geometry_state_with_updates",
            "line_start": state_start,
            "line_end": state_end,
            "line_count": state_end - state_start + 1,
            "caller_count": _count_callers(inputs_source, "_geometry_state_with_updates"),
            "called_names": _called_names(state_source),
        },
        "guard_wrapper": {
            "function": "_geometry_updates_with_depth_width_contract_guard",
            "line_start": guard_start,
            "line_end": guard_end,
            "line_count": guard_end - guard_start + 1,
            "caller_count": _count_callers(inputs_source, "_geometry_updates_with_depth_width_contract_guard"),
            "called_names": _called_names(guard_source),
        },
        "projection_helper": {
            "function": "build_geometry_update_projection",
            "line_start": projection_start,
            "line_end": projection_end,
            "line_count": projection_end - projection_start + 1,
            "called_names": _called_names(projection_source),
        },
        "family_policy": {
            "function": "guard_bending_depth_width_geometry_update",
            "file": str(GEOMETRY_RATIO),
            "line_start": family_guard_start,
            "line_end": family_guard_end,
            "line_count": family_guard_end - family_guard_start + 1,
        },
        "checks": checks,
        "classification": {
            "family_policy": "already Design Brain/family-owned",
            "guard_wrapper": "page-shell extraction wrapper around family policy",
            "projection_helper": "Design Brain service-owned geometry update projection and candidate-state materialization",
            "state_helper": "page compatibility wrapper around service projection and page guard wrapper",
            "deletion_readiness": "NOT_READY",
            "risk": "MEDIUM",
        },
        "page_owned_truth_remaining": [
            "width-lock extraction for guard wrapper",
            "page guard-wrapper call sequencing",
        ],
        "first_safe_implementation_slice": "attempt generate_smaller_geometry_variants shell handoff now that width context and update projection are service-owned",
        "stop_conditions": [
            "Do not move _geometry_state_with_updates wholesale until width-lock and guard-wrapper inputs are represented as plain data.",
            "Do not duplicate family D/b policy outside bending_fail_governs.geometry_ratio.",
            "Do not delete the page wrapper while multiple live callers still call it directly.",
        ],
    }


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_geometry_update_guard_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_geometry_update_guard_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Geometry Update Guard Boundary Audit",
            "",
            "## Executive Summary",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
            f"- Product behavior changed: `{payload['product_behavior_changed']}`",
            "",
            "## Current Ownership",
            f"- Family policy: `{payload['classification']['family_policy']}`",
            f"- Guard wrapper: `{payload['classification']['guard_wrapper']}`",
            f"- State helper: `{payload['classification']['state_helper']}`",
            "",
            "## Surfaces",
            f"- `{payload['state_helper']['function']}` lines `{payload['state_helper']['line_start']}-{payload['state_helper']['line_end']}`, callers `{payload['state_helper']['caller_count']}`",
            f"- `{payload['guard_wrapper']['function']}` lines `{payload['guard_wrapper']['line_start']}-{payload['guard_wrapper']['line_end']}`, callers `{payload['guard_wrapper']['caller_count']}`",
            f"- `{payload['family_policy']['function']}` lines `{payload['family_policy']['line_start']}-{payload['family_policy']['line_end']}`",
            "",
            "## Checks",
            *[f"- `{name}`: `{passed}`" for name, passed in payload["checks"].items()],
            "",
            "## Page-Owned Truth Remaining",
            *[f"- {item}" for item in payload["page_owned_truth_remaining"]],
            "",
            "## First Safe Implementation Slice",
            payload["first_safe_implementation_slice"],
            "",
            "## Stop Conditions",
            *[f"- {item}" for item in payload["stop_conditions"]],
            "",
        ]
    )


def main() -> int:
    payload = _build_payload()
    payload["artifact_paths"] = _write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
