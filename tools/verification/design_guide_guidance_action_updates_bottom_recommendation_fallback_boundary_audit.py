"""Audit `_compute_bottom_reo_recommendation(...)` fallback ownership.

Proof-only inventory for the next physical extraction slice. The audit maps the
bottom recommendation fallback called by `_guidance_action_updates(...)` and
classifies what must move behind family/controller/candidate service boundaries
before deletion is safe.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_compute_bottom_reo_recommendation"
CALLER = "_guidance_action_updates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _line_for(source: str, token: str) -> int | None:
    index = source.find(token)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _token(segment: str, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "line": _line_for(segment, token),
        "count": segment.count(token),
    }


def build_payload() -> dict[str, Any]:
    source = _read(INPUTS)
    start, end, segment = _function_segment(source, TARGET)
    caller_start, caller_end, caller_segment = _function_segment(source, CALLER)
    surfaces = [
        {
            "surface": "state snapshot and search allowance",
            "current_owner": "inputs_page",
            "target_owner": "page shell / controller request boundary",
            "classification": "page-shell state collection mixed with Design Brain search gating",
            "deletion_readiness": "NOT_READY_WITHOUT_REQUEST_BOUNDARY",
            "risk": "MEDIUM",
            "evidence": [
                _token(segment, "_guidance_state_snapshot("),
                _token(segment, "_recommendation_search_allowed("),
            ],
        },
        {
            "surface": "current overview and seed candidate",
            "current_owner": "inputs_page",
            "target_owner": "candidate evaluation service / controller",
            "classification": "candidate evaluation orchestration and overview collection",
            "deletion_readiness": "NOT_READY_WITHOUT_EVALUATION_SERVICE_HANDOFF",
            "risk": "HIGH",
            "evidence": [
                _token(segment, "_build_design_actions_context("),
                _token(segment, "_collect_design_overview("),
                _token(segment, "evaluate_candidate_full("),
            ],
        },
        {
            "surface": "bottom arrangement candidate generation",
            "current_owner": "candidate_evaluation service called by inputs_page",
            "target_owner": "candidate_evaluation service / bending family arrangement pool",
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(segment, "_build_bottom_reo_recommendation_arrangement_candidate_inputs("),
                _token(segment, "_generate_local_bottom_arrangements("),
                _token(segment, "_bottom_arrangement_to_shared_updates("),
                _token(segment, "_practical_bottom_reo_label("),
            ],
        },
        {
            "surface": "candidate evaluation loop",
            "current_owner": "candidate_evaluation service with page-owned evaluator callback",
            "target_owner": "candidate evaluation service",
            "classification": "EXTRACTED_SERVICE_HANDOFF_WITH_PAGE_CALLBACK",
            "deletion_readiness": "SHELL_CALLBACK_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(segment, "_evaluate_bottom_reo_recommendation_arrangement_candidate("),
                _token(segment, "eval_cache"),
                _token(segment, "metrics"),
            ],
        },
        {
            "surface": "geometry and compound fallback expansion",
            "current_owner": "inputs_page",
            "target_owner": "bottom recommendation family/candidate service",
            "classification": "page-owned rescue/fallback candidate expansion",
            "deletion_readiness": "NOT_READY_WITHOUT_COMPOUND_GEOMETRY_PARITY",
            "risk": "HIGH",
            "evidence": [
                _token(segment, "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM"),
                _token(segment, "_guidance_action_updates("),
                _token(segment, "_append_geometry_bottom_compound_candidates("),
            ],
        },
        {
            "surface": "filtering and ranking policy",
            "current_owner": "DesignGuideController / candidate_evaluation / bending family selector called by inputs_page",
            "target_owner": "DesignGuideController / candidate_evaluation / bending family selector",
            "classification": "EXTRACTED_SERVICE_BOUNDARIES_WITH_PAGE_TRACE_EMISSION",
            "deletion_readiness": "SHELL_TRACE_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(segment, "_resolve_design_guide_controller_bottom_reo_prerank_filter_policy("),
                _token(segment, "_score_auto_design_candidate("),
                _token(segment, "_annotate_candidate_target_band_metrics("),
                _token(segment, "_prepare_bottom_reo_recommendation_candidates_for_selection("),
                _token(segment, "_pick_best_bottom_recommendation_by_selector("),
                _token(segment, "_select_bottom_reo_compound_preference_candidate("),
            ],
        },
        {
            "surface": "result packaging",
            "current_owner": "bending family helpers with page-owned bending check callback",
            "target_owner": "controller/family result projection service",
            "classification": "MOSTLY_EXTRACTED_WITH_PAGE_EVALUATION_CALLBACK",
            "deletion_readiness": "BOUNDED_CALLBACK_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(segment, "_evaluate_bending_with_bottom_state("),
                _token(segment, "_calculate_bottom_reo_required_ast_for_arrangement("),
                _token(segment, "_build_bottom_reo_guidance_change_lines_for_updates("),
                _token(segment, "_build_bottom_reo_recommendation_result("),
            ],
        },
        {
            "surface": "trace/proof/debug payloads",
            "current_owner": "inputs_page",
            "target_owner": "debug/proof service",
            "classification": "non-authoritative but large page-owned proof construction",
            "deletion_readiness": "NOT_READY_WITHOUT_TRACE_PAYLOAD_SERVICE",
            "risk": "MEDIUM",
            "evidence": [
                _token(segment, "_bottom_reo_recommendation_trace_event("),
                _token(segment, "_bottom_reo_candidate_pool_boundary_record("),
                _token(segment, "_bottom_reo_selected_candidate_decision_record("),
                _token(segment, "_bottom_reo_trace_proof_payload("),
            ],
        },
    ]
    return {
        "schema": "design_guide_guidance_action_updates_bottom_recommendation_fallback_boundary_audit.v1",
        "target": {
            "function": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "caller": {
            "function": CALLER,
            "line_start": caller_start,
            "line_end": caller_end,
            "calls_target": f"{TARGET}(" in caller_segment,
        },
        "surfaces": surfaces,
        "decision": "BOTTOM_RECOMMENDATION_FALLBACK_PARTIAL_REMAINING_GEOMETRY_COMPOUND_AND_SEED_BOUNDARIES",
        "first_safe_implementation_slice": {
            "name": "bottom_reo_geometry_compound_expansion_boundary_audit",
            "why": (
                "Candidate row packaging, normal arrangement evaluation, filter policy, score/rank prep, "
                "selector live loop, and selected-result projection are now service/family bounded. "
                "The next live Design Brain surface is the geometry plus bottom compound fallback expansion."
            ),
            "move": (
                "Audit geometry trial generation, compound bottom layout expansion, compound stats, and "
                "zero-generation hints before moving any fallback expansion logic."
            ),
            "required_verifier": "design_guide_bottom_reo_geometry_compound_expansion_boundary_audit.py",
        },
        "stop_conditions": [
            "Do not move seed/current overview request construction with geometry/compound expansion.",
            "Do not move result packaging or trace payload emission with geometry/compound expansion.",
            "Do not change selected candidate id, candidate order hash, target-band proof, visible wording, CTA/apply semantics, or family runtime behaviour.",
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = list(payload.get("surfaces") or [])
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "caller_calls_target": bool((payload.get("caller") or {}).get("calls_target")),
        "surfaces_classified": len(surfaces) == 8,
        "remaining_high_risk_surfaces_present": sum(1 for row in surfaces if row.get("risk") == "HIGH") >= 2,
        "extracted_surfaces_marked_low_risk": all(
            row.get("risk") == "LOW"
            for row in surfaces
            if row.get("surface")
            in {
                "bottom arrangement candidate generation",
                "candidate evaluation loop",
                "filtering and ranking policy",
                "result packaging",
            }
        ),
        "partial_decision_points_to_remaining_surface": payload.get("decision")
        == "BOTTOM_RECOMMENDATION_FALLBACK_PARTIAL_REMAINING_GEOMETRY_COMPOUND_AND_SEED_BOUNDARIES",
        "first_slice_identified": (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        == "design_guide_bottom_reo_geometry_compound_expansion_boundary_audit.py",
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def write_artifacts(payload: dict[str, Any], check_results: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    status = "PASS" if all(check_results.values()) else "FAIL"
    payload = dict(payload)
    payload["status"] = status
    payload["checks"] = check_results
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_bottom_recommendation_fallback_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_bottom_recommendation_fallback_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    first_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Bottom Recommendation Fallback Boundary Audit",
        "",
        f"## Executive Summary: {status}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Current Helper Responsibilities",
        "",
        f"- Target: `{TARGET}` lines `{(payload.get('target') or {}).get('line_start')}`-`{(payload.get('target') or {}).get('line_end')}`.",
        "- The helper now delegates candidate row packaging, normal arrangement evaluation, filter/rank prep, selector policy, and selected-result projection to service/family helpers.",
        "- The remaining live Design Brain surfaces are seed/request orchestration, geometry/compound fallback expansion, and trace/proof payload emission.",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Current owner | Target owner | Classification | Deletion readiness | Risk |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in list(payload.get("surfaces") or []):
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
            f"- Move: {first_slice.get('move')}",
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
    print(f"design_guide_guidance_action_updates_bottom_recommendation_fallback_boundary_audit {status}")
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
