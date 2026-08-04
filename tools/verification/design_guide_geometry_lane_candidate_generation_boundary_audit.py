"""Audit geometry lane candidate-generation boundary for target-band extraction.

This is proof-only. It records why generate_smaller_geometry_variants(...)
is not yet safe to move wholesale and identifies the smallest safe next
service boundary.
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
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "generate_smaller_geometry_variants"
SUPPORT_HELPERS = [
    "_geometry_lock_enabled",
    "_resolve_geometry_width_context",
    "_geometry_state_with_updates",
    "_make_auto_design_candidate_key",
]

EXPECTED_TOKENS = {
    "target_calls_geometry_lock": "_geometry_lock_enabled(state)",
    "target_reads_search_strategy": 'mode_config.get("search_strategy"',
    "target_resolves_width_context": "_resolve_geometry_width_context(state)",
    "target_uses_geometry_update_helper": "_geometry_state_with_updates(",
    "target_uses_candidate_key_wrapper": "_make_auto_design_candidate_key(",
    "target_checks_min_depth": "GUIDANCE_MIN_PRACTICAL_DEPTH_MM",
    "target_checks_min_width": "GUIDANCE_MIN_PRACTICAL_WIDTH_MM",
    "geometry_update_calls_contract_guard": "_geometry_updates_with_depth_width_contract_guard(",
    "width_context_supports_rect_t_i": 'sec_shape == "T"',
    "lock_helper_reads_page_state_fallback": "else st.session_state",
}


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


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _build_payload() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(source, TARGET)
    service_owned_wrapper = "_generate_smaller_geometry_candidate_states(" in target_source
    service_lane_source = (
        _function_source(candidate_source, "generate_smaller_geometry_candidate_states")[2]
        if service_owned_wrapper
        else ""
    )
    helpers = {}
    for helper in SUPPORT_HELPERS:
        start, end, segment = _function_source(source, helper)
        helpers[helper] = {
            "line_start": start,
            "line_end": end,
            "line_count": end - start + 1,
            "caller_count": _count_callers(source, helper),
            "called_names": _called_names(segment),
        }

    geometry_update_source = _function_source(source, "_geometry_state_with_updates")[2]
    width_wrapper_source = _function_source(source, "_resolve_geometry_width_context")[2]
    if "_resolve_geometry_width_context_service(" in width_wrapper_source:
        width_context_source = _function_source(candidate_source, "resolve_geometry_width_context")[2]
    else:
        width_context_source = width_wrapper_source
    lock_source = _function_source(source, "_geometry_lock_enabled")[2]
    combined_source = "\n".join([target_source, geometry_update_source, width_context_source, lock_source])

    checks = {
        "target_calls_geometry_lock": "_geometry_lock_enabled(state)" in target_source,
        "target_checks_min_depth": "GUIDANCE_MIN_PRACTICAL_DEPTH_MM" in target_source,
        "target_checks_min_width": "GUIDANCE_MIN_PRACTICAL_WIDTH_MM" in target_source,
        "target_reads_search_strategy": 'mode.get("search_strategy"' in service_lane_source
        if service_owned_wrapper
        else 'mode_config.get("search_strategy"' in target_source,
        "target_resolves_width_context": "resolve_geometry_width_context(state)" in service_lane_source
        if service_owned_wrapper
        else "_resolve_geometry_width_context(state)" in target_source,
        "target_uses_geometry_update_helper": "geometry_state_fn(" in service_lane_source
        if service_owned_wrapper
        else "_geometry_state_with_updates(" in target_source,
        "target_uses_candidate_key_wrapper": "candidate_key_fn(" in service_lane_source
        if service_owned_wrapper
        else "_make_auto_design_candidate_key(" in target_source,
        "geometry_update_calls_contract_guard": "_geometry_updates_with_depth_width_contract_guard(" in combined_source,
        "width_context_supports_rect_t_i": 'sec_shape == "T"' in combined_source,
        "lock_helper_reads_page_state_fallback": "else st.session_state" in combined_source,
    }

    target_called_names = _called_names(target_source)
    live_callers = _count_callers(source, TARGET)
    page_owned_dependencies = [
        "_geometry_lock_enabled",
        "_resolve_geometry_width_context",
        "_geometry_state_with_updates",
        "_make_auto_design_candidate_key",
        "_float_from_state",
        "_geometry_updates_with_depth_width_contract_guard",
    ]

    missing_checks = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not missing_checks else "FAIL"
    if status != "PASS":
        decision = "AUDIT_INCOMPLETE"
    elif service_owned_wrapper:
        decision = "GEOMETRY_LANE_SERVICE_OWNED_WRAPPER"
    else:
        decision = "NOT_READY_GEOMETRY_PLAIN_DATA_BOUNDARY_REQUIRED"

    return {
        "status": status,
        "surface": "geometry_lane_candidate_generation_boundary",
        "decision": decision,
        "product_behavior_changed": False,
        "target": {
            "function": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": target_end - target_start + 1,
            "caller_count": live_callers,
            "called_names": target_called_names,
            "token_lines": {
                token: _line_numbers(target_source, target_start, token)
                for token in [
                    "_geometry_lock_enabled(",
                    "_resolve_geometry_width_context(",
                    "_geometry_state_with_updates(",
                    "_make_auto_design_candidate_key(",
                    "GUIDANCE_MIN_PRACTICAL_DEPTH_MM",
                    "GUIDANCE_MIN_PRACTICAL_WIDTH_MM",
                ]
            },
        },
        "support_helpers": helpers,
        "checks": checks,
        "missing_checks": missing_checks,
        "classification": {
            "current_owner": "design_brain.candidate_evaluation" if service_owned_wrapper else "inputs_page.py",
            "target_owner": "geometry candidate generation service or candidate_evaluation geometry lane helper",
            "current_state": "service-owned lane orchestration with page compatibility wrapper"
            if service_owned_wrapper
            else "page-owned candidate generation lane body with page geometry helper dependencies",
            "deletion_readiness": "COMPATIBILITY_ONLY" if service_owned_wrapper else "NOT_READY",
            "risk": "LOW" if service_owned_wrapper else "MEDIUM",
        },
        "page_owned_dependencies": page_owned_dependencies,
        "must_remain_page_shell_for_now": [
            "current_candidate and mode_config collection",
            "live caller compatibility wrapper",
            "page geometry lock fallback to session state until plain state is always passed",
        ],
        "move_candidates": [
            *(
                []
                if service_owned_wrapper
                else [
                    {
                        "name": "plain geometry width context resolver",
                        "reason": "pure section-shape-to-width-key/value mapping once given plain state",
                        "target_owner": "design_brain.candidate_evaluation or geometry service",
                        "first_safe_slice": "extract _resolve_geometry_width_context plain-data equivalent with parity for RECT/T/I",
                    },
                    {
                        "name": "plain geometry update projection",
                        "reason": "candidate-state width/depth rounding and width-key propagation can move after contract guard boundary is represented",
                        "target_owner": "geometry service",
                        "first_safe_slice": "audit _geometry_state_with_updates and depth/width contract guard before moving",
                    },
                ]
            )
        ],
        "stop_conditions": [
            "Do not move generate_smaller_geometry_variants wholesale while _geometry_state_with_updates owns guarded update behaviour.",
            "Do not move geometry lock fallback that can read st.session_state into Design Brain.",
            "Do not delete the page wrapper while there are live callers outside the target-band generator.",
        ],
        "recommended_next_slice": "audit bottom-reo lane helpers"
        if service_owned_wrapper
        else "extract a plain-data geometry width-context service helper with parity for RECT/T/I before touching candidate generation",
        "extraction_complete_estimate": "99%",
    }


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_geometry_lane_candidate_generation_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_geometry_lane_candidate_generation_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    target = payload["target"]
    checks = payload["checks"]
    return "\n".join(
        [
            "# Geometry Lane Candidate Generation Boundary Audit",
            "",
            "## Executive Summary",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
            f"- Product behavior changed: `{payload['product_behavior_changed']}`",
            "",
            "## Surface Targeted",
            f"- Function: `{target['function']}`",
            f"- Lines: `{target['line_start']}-{target['line_end']}`",
            f"- Caller count: `{target['caller_count']}`",
            "",
            "## Current Ownership",
            f"- Current owner: `{payload['classification']['current_owner']}`",
            f"- Target owner: `{payload['classification']['target_owner']}`",
            f"- Deletion readiness: `{payload['classification']['deletion_readiness']}`",
            "",
            "## Checks",
            *[f"- `{name}`: `{passed}`" for name, passed in checks.items()],
            "",
            "## Page-Owned Dependencies",
            *[f"- `{name}`" for name in payload["page_owned_dependencies"]],
            "",
            "## Move Candidates",
            *[
                f"- `{row['name']}` -> `{row['target_owner']}`: {row['first_safe_slice']}"
                for row in payload["move_candidates"]
            ],
            "",
            "## Stop Conditions",
            *[f"- {item}" for item in payload["stop_conditions"]],
            "",
            "## Next Safe Slice",
            payload["recommended_next_slice"],
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
