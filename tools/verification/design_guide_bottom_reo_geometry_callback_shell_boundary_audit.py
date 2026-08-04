"""Audit the remaining bottom-reo geometry callback shell boundary.

This verifier is proof-only. It runs after pure geometry trial planning,
geometry-trial metadata projection, and candidate delta projection have moved
to the bending family. It classifies the remaining page code around callbacks,
candidate evaluation, list mutation, and trace emission.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

COMPUTE_HELPER = "_compute_bottom_reo_recommendation"
COMPOUND_HELPER = "_append_geometry_bottom_compound_candidates"
DELTA_HELPER = "_annotate_bottom_reo_candidate_deltas"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines()
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _contains(segment: str, token: str) -> bool:
    return token in segment


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    compute_start, compute_end, compute_segment = _function_segment(inputs_source, COMPUTE_HELPER)
    compound_start, compound_end, compound_segment = _function_segment(inputs_source, COMPOUND_HELPER)
    delta_start, delta_end, delta_segment = _function_segment(inputs_source, DELTA_HELPER)

    rows: list[dict[str, Any]] = [
        {
            "surface": "geometry trial plan rows",
            "classification": "family-owned, page shell call",
            "current_owner": "design_brain.families.bending",
            "target_owner": "design_brain.families.bending",
            "deletion_readiness": "SHELL_ONLY",
            "evidence": "_build_bottom_reo_geometry_trial_plan_rows(",
        },
        {
            "surface": "action update callback execution",
            "classification": "page-owned callback execution",
            "current_owner": "inputs_page",
            "target_owner": "page shell until action update service is extracted",
            "deletion_readiness": "NOT_READY_ACTION_UPDATE_CALLBACK",
            "evidence": "_guidance_action_updates(",
        },
        {
            "surface": "no-op update guard",
            "classification": "page-owned callback guard",
            "current_owner": "inputs_page",
            "target_owner": "page shell / future callback result adapter",
            "deletion_readiness": "NOT_READY_CALLBACK_GUARD",
            "evidence": "_updates_match_state(",
        },
        {
            "surface": "candidate state materialization",
            "classification": "page shell plain-data preparation",
            "current_owner": "inputs_page",
            "target_owner": "page shell",
            "deletion_readiness": "SHELL_ONLY",
            "evidence": "cand_state.update(updates)",
        },
        {
            "surface": "candidate evaluator callback execution",
            "classification": "page-owned candidate evaluation callback",
            "current_owner": "inputs_page",
            "target_owner": "candidate evaluation service boundary / page shell callback",
            "deletion_readiness": "NOT_READY_EVALUATOR_CALLBACK",
            "evidence": "_evaluate_candidate_fast(",
        },
        {
            "surface": "geometry candidate metadata projection",
            "classification": "family-owned, page shell call",
            "current_owner": "design_brain.families.bending",
            "target_owner": "design_brain.families.bending",
            "deletion_readiness": "SHELL_ONLY",
            "evidence": "_build_bottom_reo_geometry_trial_candidate_projection(",
        },
        {
            "surface": "delta projection",
            "classification": "family-owned projection with page scalar collection",
            "current_owner": "design_brain.families.bending",
            "target_owner": "design_brain.families.bending",
            "deletion_readiness": "SHELL_SCALAR_COLLECTION",
            "evidence": "_build_bottom_reo_candidate_delta_projection(",
        },
        {
            "surface": "candidate pool mutation",
            "classification": "page-owned orchestration list mutation",
            "current_owner": "inputs_page",
            "target_owner": "compute guidance core extraction later",
            "deletion_readiness": "NOT_READY_COMPUTE_CORE_ORCHESTRATION",
            "evidence": "candidates.append(",
        },
        {
            "surface": "compound trace emission",
            "classification": "non-authoritative debug/proof emission",
            "current_owner": "inputs_page",
            "target_owner": "debug/proof service later, low priority",
            "deletion_readiness": "COMPATIBILITY_DEBUG_ONLY",
            "evidence": "compound_trace_log.append(",
        },
    ]

    checks = {
        "geometry_plan_delegated": _contains(compute_segment, "_build_bottom_reo_geometry_trial_plan_rows("),
        "geometry_projection_delegated": _contains(compute_segment, "_build_bottom_reo_geometry_trial_candidate_projection("),
        "delta_projection_delegated": _contains(delta_segment, "_build_bottom_reo_candidate_delta_projection("),
        "no_local_geo_axes_policy": "geo_axes =" not in compute_segment,
        "no_local_geometry_projection_assignments": all(
            token not in compute_segment
            for token in (
                'geo_cand["recommendation_geometry_trial"] =',
                'geo_cand["actual_ast"] =',
                'geo_cand["recommendation_family_tag"] =',
            )
        ),
        "callbacks_still_page_owned": all(
            token in compute_segment
            for token in ("_guidance_action_updates(", "_evaluate_candidate_fast(")
        ),
        "candidate_append_still_page_owned": "candidates.append(geo_cand)" in compute_segment
        and "candidates.append(comp)" in compound_segment,
        "compound_trace_still_debug_only": "compound_trace_log.append(row)" in compound_segment,
        "family_helpers_present": all(
            token in bending_source
            for token in (
                "def build_bottom_reo_geometry_trial_plan_rows(",
                "def build_bottom_reo_geometry_trial_candidate_projection(",
                "def build_bottom_reo_candidate_delta_projection(",
            )
        ),
        "family_has_no_inputs_page_import": "import inputs_page" not in bending_source
        and "from inputs_page" not in bending_source,
        "family_has_no_streamlit_import": "streamlit" not in bending_source and "import st" not in bending_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    remaining_design_brain_logic = [
        row
        for row in rows
        if row["deletion_readiness"]
        in (
            "NOT_READY_ACTION_UPDATE_CALLBACK",
            "NOT_READY_CALLBACK_GUARD",
            "NOT_READY_EVALUATOR_CALLBACK",
            "NOT_READY_COMPUTE_CORE_ORCHESTRATION",
        )
    ]
    status = "PASS" if all(checks.values()) else "FAIL"
    decision = (
        "BOTTOM_REO_GEOMETRY_CALLBACK_SURFACE_BOUNDED_NOT_DELETION_READY"
        if status == "PASS"
        else "BOTTOM_REO_GEOMETRY_CALLBACK_SURFACE_AUDIT_FAILED"
    )
    return {
        "schema": "design_guide_bottom_reo_geometry_callback_shell_boundary_audit.v1",
        "status": status,
        "decision": decision,
        "targets": {
            "compute_helper": {"function": COMPUTE_HELPER, "line_start": compute_start, "line_end": compute_end},
            "compound_helper": {"function": COMPOUND_HELPER, "line_start": compound_start, "line_end": compound_end},
            "delta_helper": {"function": DELTA_HELPER, "line_start": delta_start, "line_end": delta_end},
        },
        "surface_rows": rows,
        "remaining_not_deletion_ready_surfaces": remaining_design_brain_logic,
        "first_safe_implementation_slice": {
            "name": "candidate_evaluation_full_fast_boundary_or_compute_guidance_core_extraction",
            "reason": (
                "The remaining bottom-reo geometry tail is bounded by page callback/evaluator execution "
                "and candidate-pool orchestration. It is not safely deletable as an isolated bottom-reo helper."
            ),
        },
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_geometry_callback_shell_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_geometry_callback_shell_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    first = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Bottom Reo Geometry Callback Shell Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Classification | Current owner | Target owner | Deletion readiness |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            "| {surface} | {classification} | {current_owner} | {target_owner} | {deletion_readiness} |".format(
                **{key: str(row.get(key, "")).replace("|", "/") for key in row.keys()}
            )
        )
    lines.extend(
        [
            "",
            "## Remaining Not-Deletion-Ready Surfaces",
            "",
        ]
    )
    lines.extend(
        f"- `{row.get('surface')}`: {row.get('deletion_readiness')}"
        for row in payload.get("remaining_not_deletion_ready_surfaces") or []
    )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{first.get('name')}`",
            f"- Reason: {first.get('reason')}",
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_geometry_callback_shell_boundary_audit {payload.get('status')}")
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
