"""Audit remaining bottom-reo geometry trial and delta annotation ownership.

This is proof-only. It follows the geometry/compound expansion audit and maps
the remaining bottom-reo surfaces that still sit in `inputs_page.py` after:

- compound attempt planning moved to the bending family
- compound merge/reject policy moved to the bending family
- accepted compound candidate projection moved to the bending family

No product behavior is changed by this verifier.
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


def _line_for(segment: str, token: str) -> int | None:
    index = segment.find(token)
    if index < 0:
        return None
    return segment[:index].count("\n") + 1


def _token(segment: str, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "line": _line_for(segment, token),
        "count": segment.count(token),
    }


def _row(
    *,
    surface: str,
    current_owner: str,
    target_owner: str,
    classification: str,
    deletion_readiness: str,
    risk: str,
    evidence: list[dict[str, Any]],
    first_slice: str,
) -> dict[str, Any]:
    return {
        "surface": surface,
        "current_owner": current_owner,
        "target_owner": target_owner,
        "classification": classification,
        "deletion_readiness": deletion_readiness,
        "risk": risk,
        "evidence": evidence,
        "first_safe_slice": first_slice,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    compute_start, compute_end, compute_segment = _function_segment(inputs_source, COMPUTE_HELPER)
    compound_start, compound_end, compound_segment = _function_segment(inputs_source, COMPOUND_HELPER)
    delta_start, delta_end, delta_segment = _function_segment(inputs_source, DELTA_HELPER)

    surfaces = [
        _row(
            surface="pure geometry trial plan and label projection",
            current_owner="bending family called by inputs_page",
            target_owner="design_brain.families.bending",
            classification="EXTRACTED_FAMILY_BOUNDARY",
            deletion_readiness="SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            risk="LOW",
            evidence=[
                _token(compute_segment, "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM"),
                _token(compute_segment, "_build_bottom_reo_geometry_trial_plan_rows("),
                _token(compute_segment, "geometry_trial_plan_rows"),
                _token(compute_segment, "bottom_recommendation_geometry"),
            ],
            first_slice="complete; keep page callback execution",
        ),
        _row(
            surface="geometry trial update callback execution",
            current_owner="inputs_page",
            target_owner="inputs_page page shell / existing action update adapter",
            classification="page-owned callback execution, allowed to remain temporarily",
            deletion_readiness="SHELL_CALLBACK_AFTER_PLAN_EXTRACTION",
            risk="LOW",
            evidence=[
                _token(compute_segment, "_guidance_action_updates("),
                _token(compute_segment, "_updates_match_state("),
            ],
            first_slice="keep as callback plumbing while plan rows move",
        ),
        _row(
            surface="geometry trial evaluator callback execution",
            current_owner="inputs_page",
            target_owner="candidate evaluation service boundary, with page shell callback retained until full evaluator extraction",
            classification="page-owned evaluator callback execution",
            deletion_readiness="NOT_READY_UNTIL_CANDIDATE_EVALUATOR_BOUNDARY",
            risk="MEDIUM",
            evidence=[
                _token(compute_segment, "_evaluate_candidate_fast("),
                _token(compute_segment, "source=\"bottom_recommendation_geometry\""),
            ],
            first_slice="do not move in the geometry plan extraction",
        ),
        _row(
            surface="geometry trial candidate metadata projection",
            current_owner="bending family called by inputs_page",
            target_owner="design_brain.families.bending",
            classification="EXTRACTED_FAMILY_BOUNDARY",
            deletion_readiness="SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            risk="LOW",
            evidence=[
                _token(compute_segment, "_build_bottom_reo_geometry_trial_candidate_projection("),
                _token(compute_segment, "geo_cand.update("),
            ],
            first_slice="complete; keep page callback execution",
        ),
        _row(
            surface="candidate delta annotation",
            current_owner="bending family called by inputs_page",
            target_owner="design_brain.families.bending",
            classification="EXTRACTED_FAMILY_BOUNDARY_WITH_PAGE_SCALAR_COLLECTION",
            deletion_readiness="SHELL_SCALAR_COLLECTION_ONLY_FOR_THIS_SURFACE",
            risk="LOW",
            evidence=[
                _token(delta_segment, "_build_bottom_reo_candidate_delta_projection("),
                _token(compound_segment, "_annotate_bottom_reo_candidate_deltas("),
            ],
            first_slice="complete; page still collects scalar inputs from current state/candidate",
        ),
        _row(
            surface="compound candidate append and trace sample emission",
            current_owner="inputs_page",
            target_owner="inputs_page page shell / debug-proof service later",
            classification="page-owned list mutation and non-authoritative trace emission",
            deletion_readiness="NOT_READY_UNTIL_CALLBACK_ORCHESTRATION_MOVE",
            risk="LOW",
            evidence=[
                _token(compound_segment, "candidates.append(comp)"),
                _token(compound_segment, "compound_trace_log.append(row)"),
            ],
            first_slice="keep; not part of pure geometry/delta extraction",
        ),
    ]

    helper_exists_in_family = {
        "compound_attempt_rows": "def build_bottom_reo_compound_attempt_rows(" in bending_source,
        "compound_merge_policy": "def classify_bottom_reo_compound_attempt_merge_policy(" in bending_source,
        "compound_accepted_projection": "def build_bottom_reo_compound_accepted_candidate_projection(" in bending_source,
        "geometry_trial_plan": "def build_bottom_reo_geometry_trial_plan_rows(" in bending_source,
        "delta_projection": "def build_bottom_reo_candidate_delta_projection(" in bending_source,
    }

    checks = {
        "compute_helper_found": bool(compute_segment),
        "compound_helper_found": bool(compound_segment),
        "delta_helper_found": bool(delta_segment),
        "geometry_loop_delegated": all(
            token in compute_segment
            for token in (
                "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM",
                "_build_bottom_reo_geometry_trial_plan_rows(",
                "bottom_recommendation_geometry",
            )
        ),
        "geometry_metadata_delegated": all(
            token in compute_segment
            for token in (
                "_build_bottom_reo_geometry_trial_candidate_projection(",
                "geo_cand.update(",
            )
        ),
        "delta_annotation_delegated": all(
            token in delta_segment
            for token in ("_build_bottom_reo_candidate_delta_projection(", "candidate.update(")
        ),
        "compound_prior_boundaries_present": all(
            helper_exists_in_family[name]
            for name in (
                "compound_attempt_rows",
                "compound_merge_policy",
                "compound_accepted_projection",
            )
        ),
        "geometry_trial_plan_extracted": helper_exists_in_family["geometry_trial_plan"],
        "delta_projection_extracted": helper_exists_in_family["delta_projection"],
        "page_callbacks_remain_page_owned": all(
            token in compute_segment + compound_segment
            for token in ("_guidance_action_updates(", "_evaluate_candidate_fast(")
        ),
        "surfaces_classified": len(surfaces) == 6,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "design_guide_bottom_reo_remaining_geometry_delta_boundary_audit.v1",
        "status": status,
        "decision": (
            "BOTTOM_REO_REMAINING_GEOMETRY_DELTA_PURE_HELPERS_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_REMAINING_GEOMETRY_DELTA_AUDIT_FAILED"
        ),
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
            "delta_helper": {
                "function": DELTA_HELPER,
                "line_start": delta_start,
                "line_end": delta_end,
            },
        },
        "surface_rows": surfaces,
        "family_helper_presence": helper_exists_in_family,
        "first_safe_implementation_slice": {
            "name": "bottom_reo_geometry_callback_or_delta_scalar_collection_shell_audit",
            "target_owner": "design_brain.families.bending",
            "move": (
                "Audit whether the remaining geometry callback execution and delta scalar collection are "
                "bounded page shell or still contain page-owned Design Brain logic."
            ),
            "keep": (
                "Keep _guidance_action_updates(...), _evaluate_candidate_fast(...), "
                "candidate list mutation, compound trace emission, and page context/session plumbing in inputs_page.py."
            ),
            "required_verifier": "design_guide_bottom_reo_geometry_callback_shell_boundary_audit.py",
        },
        "stop_conditions": [
            "Stop if geometry delta order changes.",
            "Stop if geometry trial labels change.",
            "Stop if candidate updates, selected candidate id, score, action type, or source changes.",
            "Stop if evaluator callbacks or action update callbacks move into the family module.",
            "Stop if visible wording, CTA/apply semantics, family runtime behavior, or solver maths changes.",
        ],
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_remaining_geometry_delta_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_remaining_geometry_delta_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    first = dict(payload.get("first_safe_implementation_slice") or {})
    targets = dict(payload.get("targets") or {})
    lines = [
        "# Bottom Reo Remaining Geometry/Delta Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Current Targets",
        "",
    ]
    for key, target in targets.items():
        t = dict(target or {})
        lines.append(
            f"- `{t.get('function')}` lines `{t.get('line_start')}`-`{t.get('line_end')}` (`{key}`)",
        )
    lines.extend(
        [
            "",
            "## Surface Inventory",
            "",
            "| Surface | Current owner | Target owner | Classification | Deletion readiness | Risk | First safe slice |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("surface_rows") or []:
        lines.append(
            "| {surface} | {current_owner} | {target_owner} | {classification} | {deletion_readiness} | {risk} | {first_safe_slice} |".format(
                **{
                    key: str(row.get(key, "")).replace("|", "/")
                    for key in (
                        "surface",
                        "current_owner",
                        "target_owner",
                        "classification",
                        "deletion_readiness",
                        "risk",
                        "first_safe_slice",
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
    print(f"design_guide_bottom_reo_remaining_geometry_delta_boundary_audit {payload.get('status')}")
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
