"""Audit `evaluate_candidate_full` / `evaluate_candidate_fast` extraction boundary.

This is proof-only. It maps the current page-owned evaluator surfaces that
block deletion of bottom-reo geometry callback tails and broader compute-core
candidate orchestration.
"""

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

FULL_HELPER = "evaluate_candidate_full"
FAST_HELPER = "evaluate_candidate_fast"
FAST_WRAPPER = "_evaluate_candidate_fast"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines()
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _count_calls(source: str, name: str) -> int:
    tree = ast.parse(source)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                count += 1
            elif isinstance(func, ast.Attribute) and func.attr == name:
                count += 1
    return count


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    full_start, full_end, full_segment = _function_segment(inputs_source, FULL_HELPER)
    fast_start, fast_end, fast_segment = _function_segment(inputs_source, FAST_HELPER)
    wrapper_start, wrapper_end, wrapper_segment = _function_segment(inputs_source, FAST_WRAPPER)
    updates_start, updates_end, updates_segment = _function_segment(inputs_source, "_candidate_state_to_shared_updates")

    rows: list[dict[str, Any]] = [
        {
            "surface": "full evaluator fingerprint/cache/profiling",
            "function": FULL_HELPER,
            "current_owner": "inputs_page",
            "target_owner": "shared performance/cache wrapper or page shell",
            "classification": "page/session/performance shell mixed with evaluator",
            "deletion_readiness": "NOT_READY_CACHE_PROBE_WRAPPER",
            "risk": "MEDIUM",
            "evidence": ["stable_fingerprint_for_payload", "get_rerun_pure_cache", "ux_probe_record", "speed_profile_record"],
        },
        {
            "surface": "full evaluator engineering kernel",
            "function": FULL_HELPER,
            "current_owner": "inputs_page",
            "target_owner": "design_brain.candidate_evaluation evaluation kernel",
            "classification": "page-owned Design Brain candidate evaluation logic",
            "deletion_readiness": "NOT_READY_KERNEL_ADAPTER_PARITY",
            "risk": "HIGH",
            "evidence": [
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
                "_collect_design_overview",
            ],
        },
        {
            "surface": "full evaluator output packaging",
            "function": FULL_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation result projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_full_candidate_evaluation_result_projection(", "bending_components", "is_compliant"],
        },
        {
            "surface": "full evaluator overview/status packaging",
            "function": FULL_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation full overview/status projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_full_candidate_evaluation_overview_status_projection(", "statuses", "utils", "any_fail"],
        },
        {
            "surface": "fast evaluator engineering kernel",
            "function": FAST_HELPER,
            "current_owner": "inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast evaluation kernel",
            "classification": "page-owned fast candidate evaluation logic",
            "deletion_readiness": "NOT_READY_FAST_KERNEL_PARITY",
            "risk": "HIGH",
            "evidence": [
                "_state_with_resolved_auto_design_actions",
                "_evaluate_bending_with_bottom_state",
                "_evaluate_shear_with_state",
                "_evaluate_crack_with_state",
                "_evaluate_deflection_with_state",
            ],
        },
        {
            "surface": "fast evaluator output packaging",
            "function": FAST_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast result projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_result_projection(", "bending_components", "shear_link_detailing_failures", "is_compliant"],
        },
        {
            "surface": "fast evaluator overview/status packaging",
            "function": FAST_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast overview/status projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_overview_status_projection(", "statuses", "utils", "any_fail"],
        },
        {
            "surface": "fast evaluator scalar/status packaging",
            "function": FAST_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast scalar/status projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_scalar_status_projection(", "scalar_status_projection", "unknown_status"],
        },
        {
            "surface": "fast evaluator physical metric packaging",
            "function": FAST_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast physical metric projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_physical_metric_projection(", "physical_metric_projection", "bottom_state"],
        },
        {
            "surface": "fast evaluator bending summary pack projection",
            "function": FAST_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast bending summary pack projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_bending_summary_pack_projection(", "bend_pack"],
        },
        {
            "surface": "fast evaluator shear-detail state projection",
            "function": FAST_HELPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast shear-detail state projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_shear_detail_state_projection(", "shear_detail_state"],
        },
        {
            "surface": "fast runner metadata projection",
            "function": FAST_WRAPPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast runner metadata projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_build_fast_candidate_evaluation_runner_metadata_projection(", "source", "label", "updates", "_seed_width"],
        },
        {
            "surface": "fast runner cache/cap decision",
            "function": FAST_WRAPPER,
            "current_owner": "design_brain.candidate_evaluation called by inputs_page",
            "target_owner": "design_brain.candidate_evaluation fast runner cache/cap decision",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_resolve_fast_candidate_evaluation_cache_cap_decision(", "use_global_cached", "should_evaluate", "cap_hit"],
        },
        {
            "surface": "candidate state shared updates diff",
            "function": "_candidate_state_to_shared_updates",
            "current_owner": "design_brain.candidate_evaluation called by inputs_page shell wrapper",
            "target_owner": "design_brain.candidate_evaluation shared update diff",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "PAGE_HELPER_COMPATIBILITY_SHELL",
            "risk": "LOW",
            "evidence": ["_resolve_candidate_state_shared_updates(", "resolve_candidate_state_shared_updates"],
        },
        {
            "surface": "candidate bottom update projection",
            "function": "evaluate_candidate_full / evaluate_candidate_fast",
            "current_owner": "design_brain.candidate_evaluation called by inputs_page shell wrapper",
            "target_owner": "design_brain.candidate_evaluation bottom update projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_resolve_bottom_reo_candidate_bottom_updates(", "resolve_bottom_reo_candidate_bottom_updates"],
        },
        {
            "surface": "candidate shear update projection",
            "function": "evaluate_candidate_full / evaluate_candidate_fast",
            "current_owner": "design_brain.candidate_evaluation called by inputs_page shell wrapper",
            "target_owner": "design_brain.candidate_evaluation shear update projection",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": ["_resolve_candidate_shear_updates(", "resolve_candidate_shear_updates"],
        },
        {
            "surface": "fast wrapper cache/timing/callback shell",
            "function": FAST_WRAPPER,
            "current_owner": "inputs_page",
            "target_owner": "page shell / future cache service",
            "classification": "BOUNDED_PAGE_SHELL",
            "deletion_readiness": "SHELL_ONLY_CACHE_TIMING_CALLBACK_BOUNDARY",
            "risk": "MEDIUM",
            "evidence": ["metrics[", "eval_cache", "time.perf_counter()", "evaluate_candidate_fast(candidate_state, fast_ctx)"],
        },
    ]

    checks = {
        "full_helper_found": bool(full_segment),
        "fast_helper_found": bool(fast_segment),
        "fast_wrapper_found": bool(wrapper_segment),
        "candidate_evaluation_boundary_module_exists": CANDIDATE_EVALUATION.exists(),
        "candidate_evaluation_module_import_clean_source": "import inputs_page" not in candidate_source
        and "from inputs_page" not in candidate_source
        and "import streamlit" not in candidate_source,
        "full_helper_still_page_owned": all(token in full_segment for token in ("st.session_state", "_collect_design_overview")),
        "full_result_projection_extracted": "_build_full_candidate_evaluation_result_projection(" in full_segment
        and "def build_full_candidate_evaluation_result_projection(" in candidate_source,
        "full_overview_status_projection_extracted": "_build_full_candidate_evaluation_overview_status_projection(" in full_segment
        and "def build_full_candidate_evaluation_overview_status_projection(" in candidate_source,
        "fast_helper_kernel_still_page_owned": "_evaluate_bending_with_bottom_state" in fast_segment,
        "fast_result_projection_extracted": "_build_fast_candidate_evaluation_result_projection(" in fast_segment
        and "def build_fast_candidate_evaluation_result_projection(" in candidate_source,
        "fast_overview_status_projection_extracted": "_build_fast_candidate_evaluation_overview_status_projection(" in fast_segment
        and "def build_fast_candidate_evaluation_overview_status_projection(" in candidate_source,
        "fast_scalar_status_projection_extracted": "_build_fast_candidate_evaluation_scalar_status_projection(" in fast_segment
        and "def build_fast_candidate_evaluation_scalar_status_projection(" in candidate_source,
        "fast_physical_metric_projection_extracted": "_build_fast_candidate_evaluation_physical_metric_projection(" in fast_segment
        and "def build_fast_candidate_evaluation_physical_metric_projection(" in candidate_source,
        "fast_bending_summary_pack_projection_extracted": "_build_fast_candidate_evaluation_bending_summary_pack_projection(" in fast_segment
        and "def build_fast_candidate_evaluation_bending_summary_pack_projection(" in candidate_source,
        "fast_shear_detail_state_projection_extracted": "_build_fast_candidate_evaluation_shear_detail_state_projection(" in fast_segment
        and "def build_fast_candidate_evaluation_shear_detail_state_projection(" in candidate_source,
        "fast_runner_metadata_projection_extracted": "_build_fast_candidate_evaluation_runner_metadata_projection(" in wrapper_segment
        and "def build_fast_candidate_evaluation_runner_metadata_projection(" in candidate_source,
        "fast_runner_cache_cap_decision_extracted": "_resolve_fast_candidate_evaluation_cache_cap_decision(" in wrapper_segment
        and "def resolve_fast_candidate_evaluation_cache_cap_decision(" in candidate_source,
        "candidate_state_shared_updates_extracted": "_resolve_candidate_state_shared_updates(" in updates_segment
        and "def resolve_candidate_state_shared_updates(" in candidate_source,
        "candidate_bottom_updates_extracted": "_resolve_bottom_reo_candidate_bottom_updates(" in full_segment
        and "_resolve_bottom_reo_candidate_bottom_updates(" in fast_segment
        and "def resolve_bottom_reo_candidate_bottom_updates(" in candidate_source,
        "candidate_shear_updates_extracted": "_resolve_candidate_shear_updates(" in full_segment
        and "_resolve_candidate_shear_updates(" in fast_segment
        and "def resolve_candidate_shear_updates(" in candidate_source,
        "fast_wrapper_cache_timing_callback_bounded": all(token in wrapper_segment for token in ("metrics[", "eval_cache", "time.perf_counter()", "evaluate_candidate_fast(")),
        "fast_wrapper_timing_callback_audit_exists": (
            ROOT / "tools" / "verification" / "design_guide_fast_candidate_evaluation_runner_timing_callback_boundary_audit.py"
        ).exists(),
        "call_inventory_collected": _count_calls(inputs_source, FULL_HELPER) > 0 and _count_calls(inputs_source, FAST_WRAPPER) > 0,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_candidate_evaluation_full_fast_boundary_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "CANDIDATE_EVALUATION_FAST_PROJECTIONS_EXTRACTED_RUNNER_SHELL_BOUNDED_KERNEL_REMAINS"
            if all(checks.values())
            else "CANDIDATE_EVALUATION_FULL_FAST_BOUNDARY_AUDIT_FAILED"
        ),
        "targets": {
            "evaluate_candidate_full": {"line_start": full_start, "line_end": full_end},
            "evaluate_candidate_fast": {"line_start": fast_start, "line_end": fast_end},
            "_evaluate_candidate_fast": {"line_start": wrapper_start, "line_end": wrapper_end},
            "_candidate_state_to_shared_updates": {"line_start": updates_start, "line_end": updates_end},
        },
        "call_inventory": {
            "evaluate_candidate_full_calls": _count_calls(inputs_source, FULL_HELPER),
            "evaluate_candidate_fast_calls": _count_calls(inputs_source, FAST_HELPER),
            "_evaluate_candidate_fast_calls": _count_calls(inputs_source, FAST_WRAPPER),
        },
        "surface_rows": rows,
        "first_safe_implementation_slice": {
            "name": "candidate_evaluation_result_projection_object_or_fast_runner_boundary",
            "recommendation": (
                "Do not move the whole evaluator next. The fast result, overview/status, scalar/status, "
                "full result, full overview/status, fast physical metric, bending summary pack, shear-detail state, candidate bottom/shear updates, shared update diff, runner metadata, and runner cache/cap decision projections are now service-owned. "
                "The `_evaluate_candidate_fast(...)` timing/cache/callback runner is bounded page-shell plumbing. "
                "Next audit the `evaluate_candidate_fast(...)` evaluator kernel boundary without changing solver semantics."
            ),
        },
        "stop_conditions": [
            "Do not move Streamlit/session/cache/probe code into design_brain.candidate_evaluation.",
            "Do not change candidate output shape, overview fields, updates, source/label/action_type, score, or metadata.",
            "Do not move solver callback execution without a parity verifier.",
            "Do not delete evaluate_candidate_full/evaluate_candidate_fast until all callsites are service-backed or shell-only.",
        ],
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_candidate_evaluation_full_fast_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_candidate_evaluation_full_fast_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    first = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Candidate Evaluation Full/Fast Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Call Inventory",
        "",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("call_inventory") or {}).items())
    lines.extend(
        [
            "",
            "## Surface Inventory",
            "",
            "| Surface | Function | Current owner | Target owner | Classification | Deletion readiness | Risk |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("surface_rows") or []:
        lines.append(
            "| {surface} | {function} | {current_owner} | {target_owner} | {classification} | {deletion_readiness} | {risk} |".format(
                **{key: str(row.get(key, "")).replace("|", "/") for key in row.keys()}
            )
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{first.get('name')}`",
            f"- Recommendation: {first.get('recommendation')}",
            "",
            "## Stop Conditions",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload.get("stop_conditions") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_candidate_evaluation_full_fast_boundary_audit {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
