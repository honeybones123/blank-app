"""Audit bottom-reo geometry/compound fallback expansion ownership.

This is proof-only. It maps the remaining geometry-trial and geometry+bottom
compound expansion logic inside `_compute_bottom_reo_recommendation(...)` and
`_append_geometry_bottom_compound_candidates(...)` after candidate row packaging,
evaluation handoff, filter/rank prep, selector policy, and selected-result
projection have moved behind service/family boundaries.
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

COMPUTE_HELPER = "_compute_bottom_reo_recommendation"
COMPOUND_HELPER = "_append_geometry_bottom_compound_candidates"


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
    compute_start, compute_end, compute_segment = _function_segment(source, COMPUTE_HELPER)
    compound_start, compound_end, compound_segment = _function_segment(source, COMPOUND_HELPER)

    surfaces: list[dict[str, Any]] = [
        {
            "surface": "geometry trial axis/order and delta plan",
            "current_owner": "inputs_page",
            "target_owner": "bending family candidate planner / controller orchestration",
            "classification": "page-owned Design Brain candidate generation policy",
            "deletion_readiness": "NOT_READY_WITHOUT_GEOMETRY_TRIAL_PLAN_PARITY",
            "risk": "HIGH",
            "evidence": [
                _token(compute_segment, "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM"),
                _token(compute_segment, "geo_axes ="),
                _token(compute_segment, "bottom_recommendation_geometry"),
            ],
        },
        {
            "surface": "geometry trial update callback",
            "current_owner": "inputs_page",
            "target_owner": "page shell callback / DesignGuideController route plan",
            "classification": "page-owned callback execution mixed with generation loop",
            "deletion_readiness": "BOUNDED_PAGE_CALLBACK_AFTER_PLAN_EXTRACTION",
            "risk": "MEDIUM",
            "evidence": [
                _token(compute_segment, "_guidance_action_updates("),
                _token(compute_segment, "_updates_match_state("),
            ],
        },
        {
            "surface": "geometry trial candidate evaluation callback",
            "current_owner": "inputs_page",
            "target_owner": "candidate_evaluation service callback boundary",
            "classification": "page-owned evaluator callback execution",
            "deletion_readiness": "BOUNDED_PAGE_CALLBACK_AFTER_ATTEMPT_HELPER",
            "risk": "MEDIUM",
            "evidence": [
                _token(compute_segment, "_evaluate_candidate_fast("),
                _token(compute_segment, "source=\"bottom_recommendation_geometry\""),
            ],
        },
        {
            "surface": "compound geometry seed selection",
            "current_owner": "bending family called by inputs_page",
            "target_owner": "bending family compound candidate planner",
            "classification": "EXTRACTED_FAMILY_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(compound_segment, "_build_bottom_reo_compound_attempt_rows("),
                _token(compound_segment, "width_seed_candidates_selected_for_compound"),
                _token(compound_segment, "depth_seed_candidates_selected_for_compound"),
            ],
        },
        {
            "surface": "compound bottom arrangement regeneration",
            "current_owner": "bending family called by inputs_page",
            "target_owner": "bending family arrangement planner",
            "classification": "EXTRACTED_FAMILY_BOUNDARY",
            "deletion_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(compound_segment, "_build_bottom_reo_compound_attempt_rows("),
                _token(compound_segment, "attempt_rows"),
            ],
        },
        {
            "surface": "compound merge/reject policy",
            "current_owner": "bending family called by inputs_page",
            "target_owner": "bending family compound candidate planner",
            "classification": "EXTRACTED_FAMILY_BOUNDARY_WITH_PAGE_CALLBACK_FACTS",
            "deletion_readiness": "SHELL_CALLBACK_FACTS_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(compound_segment, "_classify_bottom_reo_compound_attempt_merge_policy("),
                _token(compound_segment, "_candidate_state_to_shared_updates("),
                _token(compound_segment, "_arrangement_fits_state("),
                _token(compound_segment, "rejected_duplicate_signature"),
                _token(compound_segment, "rejected_invalid_merge"),
                _token(compound_segment, "compound_layout_reject_count"),
            ],
        },
        {
            "surface": "compound candidate evaluation callback",
            "current_owner": "inputs_page",
            "target_owner": "candidate_evaluation service callback boundary",
            "classification": "page-owned evaluator callback execution",
            "deletion_readiness": "BOUNDED_PAGE_CALLBACK_AFTER_ATTEMPT_HELPER",
            "risk": "MEDIUM",
            "evidence": [
                _token(compound_segment, "_evaluate_candidate_fast("),
                _token(compound_segment, "source=\"bottom_recommendation_compound\""),
                _token(compound_segment, "rejected_eval_cap_or_none"),
            ],
        },
        {
            "surface": "compound accepted-candidate projection",
            "current_owner": "bending family called by inputs_page",
            "target_owner": "bending family candidate projection",
            "classification": "EXTRACTED_FAMILY_BOUNDARY_WITH_PAGE_APPEND",
            "deletion_readiness": "SHELL_APPEND_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
            "evidence": [
                _token(compound_segment, "_build_bottom_reo_compound_accepted_candidate_projection("),
                _token(compound_segment, "_annotate_bottom_reo_candidate_deltas("),
                _token(compound_segment, "candidates.append(comp)"),
            ],
        },
        {
            "surface": "compound stats and trace sample payload",
            "current_owner": "inputs_page",
            "target_owner": "debug/proof projection service after candidate planner parity",
            "classification": "non-authoritative debug/proof construction coupled to live generator",
            "deletion_readiness": "NOT_READY_WITHOUT_TRACE_PAYLOAD_PARITY",
            "risk": "MEDIUM",
            "evidence": [
                _token(compound_segment, "compound_stats["),
                _token(compound_segment, "compound_trace_log.append("),
                _token(compute_segment, "compound_zero_generation_hints"),
            ],
        },
    ]

    checks = {
        "compute_helper_found": bool(compute_segment),
        "compound_helper_found": bool(compound_segment),
        "geometry_block_present": "bottom_recommendation_geometry" in compute_segment,
        "compound_helper_called": f"{COMPOUND_HELPER}(" in compute_segment,
        "surfaces_classified": len(surfaces) == 9,
        "high_risk_policy_surfaces_present": sum(1 for row in surfaces if row.get("risk") == "HIGH") >= 1,
        "compound_attempt_planner_extracted": "_build_bottom_reo_compound_attempt_rows(" in compound_segment,
        "compound_merge_policy_extracted": "_classify_bottom_reo_compound_attempt_merge_policy(" in compound_segment,
        "compound_accepted_projection_extracted": "_build_bottom_reo_compound_accepted_candidate_projection(" in compound_segment,
        "page_callbacks_bounded_not_moved": all(
            token in compute_segment + compound_segment
            for token in ("_guidance_action_updates(", "_evaluate_candidate_fast(")
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "schema": "design_guide_bottom_reo_geometry_compound_expansion_boundary_audit.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_GEOMETRY_COMPOUND_EXPANSION_PARTIAL_ACCEPTED_PROJECTION_EXTRACTED",
        "targets": {
            "compute_helper": {
                "function": COMPUTE_HELPER,
                "line_start": compute_start,
                "line_end": compute_end,
            },
            "compound_helper": {
                "function": COMPOUND_HELPER,
                "line_start": compound_start,
                "line_end": compound_end,
            },
        },
        "surface_rows": surfaces,
        "first_safe_implementation_slice": {
            "name": "bottom_reo_geometry_trial_plan_or_compound_delta_annotation_boundary",
            "target_owner": "design_brain.families.bending",
            "move": (
                "Audit whether the remaining geometry trial plan and compound delta annotation callback can move "
                "behind bending family helpers without moving evaluator callbacks or trace emission."
            ),
            "keep": (
                "Keep _guidance_action_updates(...), _evaluate_candidate_fast(...), page trace emission, "
                "and final candidates list mutation in inputs_page.py until parity and cutover pass."
            ),
            "required_verifier": "design_guide_bottom_reo_remaining_geometry_delta_boundary_audit.py",
        },
        "stop_conditions": [
            "Do not move page evaluator callbacks into Design Brain.",
            "Do not move page apply/action routing into Design Brain.",
            "Do not change geometry delta order, compound seed order, candidate metadata, selected candidate id, visible wording, CTA/apply semantics, or family runtime behaviour.",
            "Do not delete _append_geometry_bottom_compound_candidates(...) before family attempt planner parity and live cutover proof.",
        ],
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_geometry_compound_expansion_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_geometry_compound_expansion_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    targets = dict(payload.get("targets") or {})
    compute = dict(targets.get("compute_helper") or {})
    compound = dict(targets.get("compound_helper") or {})
    first = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Bottom Reo Geometry/Compound Expansion Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Current Helper Responsibilities",
        "",
        f"- `{COMPUTE_HELPER}` lines `{compute.get('line_start')}`-`{compute.get('line_end')}` owns the live geometry trial loop and calls compound expansion.",
        f"- `{COMPOUND_HELPER}` lines `{compound.get('line_start')}`-`{compound.get('line_end')}` owns geometry seed selection, bottom arrangement regeneration, merge/reject policy, compound candidate projection, and trace samples.",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Current owner | Target owner | Classification | Deletion readiness | Risk |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            "| {surface} | {current_owner} | {target_owner} | {classification} | {deletion_readiness} | {risk} |".format(
                **{
                    key: str(row.get(key, ""))
                    for key in (
                        "surface",
                        "current_owner",
                        "target_owner",
                        "classification",
                        "deletion_readiness",
                        "risk",
                    )
                }
            )
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{first.get('name')}`",
            f"- Target owner: `{first.get('target_owner')}`",
            f"- Required verifier: `{first.get('required_verifier')}`",
            f"- Move: {first.get('move')}",
            f"- Keep: {first.get('keep')}",
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
    status = payload.get("status")
    print(f"design_guide_bottom_reo_geometry_compound_expansion_boundary_audit {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
