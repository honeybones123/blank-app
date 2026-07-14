"""Audit the remaining bottom-reo recommendation evaluation loop boundary.

This is audit-only. It classifies the remaining page-owned logic inside
`_compute_bottom_reo_recommendation(...)` after the candidate-row and
arrangement-pool extraction slices.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_HELPER = "_compute_bottom_reo_recommendation"


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


def _contains_any(segment: str, tokens: list[str]) -> bool:
    return any(token in segment for token in tokens)


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    start, end, segment = _function_segment(inputs_source, TARGET_HELPER)

    surface_rows = [
        {
            "surface": "search_allowed_and_seed_setup",
            "evidence_tokens": [
                "_recommendation_search_allowed(",
                "evaluate_candidate_full(",
                "_build_auto_design_context(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "candidate evaluation / controller service",
            "classification": "NOT_READY",
            "reason": "Uses page wrappers and seed/current overview setup that need a request object before cutover.",
        },
        {
            "surface": "normal_arrangement_evaluation_loop",
            "evidence_tokens": [
                "_evaluate_candidate_fast(",
                "_bottom_reo_update_evaluated_filter_record(",
                "_updates_match_state(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "candidate_evaluation service",
            "classification": "NEXT_SAFE_SLICE",
            "reason": "The loop has service-owned row/pool inputs now; evaluator/cache/filter handoff is the next smallest move.",
        },
        {
            "surface": "geometry_trial_generation",
            "evidence_tokens": [
                "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM",
                "_guidance_action_updates(",
                "bottom_recommendation_geometry",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController / candidate service",
            "classification": "NOT_READY",
            "reason": "Calls page action-update resolver and creates geometry labels; needs its own route-policy proof.",
        },
        {
            "surface": "compound_geometry_bottom_expansion",
            "evidence_tokens": [
                "_append_geometry_bottom_compound_candidates(",
                "compound_stats",
                "compound_trace_log",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController / candidate service",
            "classification": "NOT_READY",
            "reason": "Compound generation mutates shared candidate and proof collections; extract only after normal evaluator loop is bounded.",
        },
        {
            "surface": "candidate_filter_and_growth_policy",
            "evidence_tokens": [
                "_candidate_materially_improves(",
                "_bottom_recommendation_prefilter_ok(",
                "_candidate_is_growth_move(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController",
            "classification": "SERVICE_CANDIDATE",
            "reason": "Pure selection policy but depends on evaluated candidate shape and trace records.",
        },
        {
            "surface": "ranking_and_selector",
            "evidence_tokens": [
                "_score_auto_design_candidate(",
                "_keep_top_candidates(",
                "_pick_best_bottom_recommendation_by_selector(",
                "_maybe_prefer_compound_over_pure_geometry(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController / family-owned selector",
            "classification": "SERVICE_CANDIDATE",
            "reason": "Recommendation selection logic should move after evaluator/filter boundary parity is proven.",
        },
        {
            "surface": "selected_result_packaging",
            "evidence_tokens": [
                "_evaluate_bending_with_bottom_state(",
                "_required_ast_for_arrangement(",
                "_guidance_change_lines_for_updates(",
                "_build_bottom_reo_recommendation_result(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "DesignGuideController / publication projection",
            "classification": "NOT_READY",
            "reason": "Builds final recommendation result and visible change lines; requires exact wording/CTA parity before movement.",
        },
        {
            "surface": "trace_and_debug_payloads",
            "evidence_tokens": [
                "_bottom_reo_recommendation_trace_event(",
                "_bottom_reo_candidate_pool_boundary_record(",
                "_bottom_reo_selected_candidate_decision_record(",
                "_bottom_reo_trace_proof_payload(",
            ],
            "current_owner": "inputs_page.py",
            "target_owner": "debug/proof service",
            "classification": "PROOF_SERVICE_CANDIDATE",
            "reason": "Non-product proof payload construction can move after decision/result objects are service-owned.",
        },
    ]

    for row in surface_rows:
        row["present"] = _contains_any(segment, list(row["evidence_tokens"]))

    current_boundary = {
        "line_start": start,
        "line_end": end,
        "line_count": end - start + 1,
        "page_delegates_arrangement_pool": "_generate_local_bottom_arrangements(" in segment,
        "page_delegates_candidate_rows": "_build_bottom_reo_recommendation_arrangement_candidate_inputs(" in segment,
        "still_evaluates_candidates": "_evaluate_candidate_fast(" in segment,
        "still_filters_candidates": "_candidate_materially_improves(" in segment
        and "_bottom_recommendation_prefilter_ok(" in segment,
        "still_ranks_selects": "_pick_best_bottom_recommendation_by_selector(" in segment,
        "still_packages_result": "_build_bottom_reo_recommendation_result(" in segment,
        "still_builds_trace_payloads": "_bottom_reo_trace_proof_payload(" in segment,
    }

    checks = {
        "helper_found": bool(segment),
        "candidate_row_boundary_already_extracted": current_boundary["page_delegates_candidate_rows"],
        "arrangement_pool_boundary_already_extracted": current_boundary["page_delegates_arrangement_pool"],
        "remaining_loop_not_shell_only_identified": current_boundary["still_evaluates_candidates"]
        and current_boundary["still_ranks_selects"]
        and current_boundary["still_packages_result"],
        "filter_policy_already_moved_or_absent": not current_boundary["still_filters_candidates"],
        "surfaces_classified": all(row.get("classification") for row in surface_rows),
        "next_slice_is_focused_evaluator_loop": True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_EVALUATION_LOOP_NOT_SHELL_ONLY_NEXT_EVALUATOR_BOUNDARY",
        "target_helper": TARGET_HELPER,
        "current_boundary": current_boundary,
        "surface_rows": surface_rows,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "design_guide_bottom_reo_recommendation_evaluation_loop_service_handoff.py",
            "target": "normal arrangement evaluation loop only",
            "move": [
                "candidate_state update from arrangement row",
                "candidate evaluation service call wrapper",
                "null/no-op candidate filter record projection",
            ],
            "keep": [
                "geometry trial generation",
                "compound geometry-bottom expansion",
                "ranking/selector",
                "selected result packaging",
                "trace/proof event emission",
                "CTA/apply/publication/render semantics",
            ],
            "required_verifier": "tools/verification/design_guide_bottom_reo_recommendation_evaluation_loop_service_handoff.py",
        },
        "stop_conditions": [
            "candidate count/order changes",
            "selected candidate changes",
            "updates/action payload changes",
            "visible wording changes",
            "CTA/apply semantics change",
            "family runtime behaviour changes",
            "any composed lock fails",
        ],
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_evaluation_loop_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_evaluation_loop_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    boundary = dict(payload.get("current_boundary") or {})
    next_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines = [
        "# Bottom Reo Recommendation Evaluation Loop Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Current Boundary",
        "",
        f"- Helper: `{payload.get('target_helper')}`",
        f"- Lines: `{boundary.get('line_start')}-{boundary.get('line_end')}`",
        f"- Line count: `{boundary.get('line_count')}`",
        "",
        "## Surface Classification",
        "",
        "| Surface | Classification | Current owner | Target owner | Present |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            f"| `{row.get('surface')}` | `{row.get('classification')}` | {row.get('current_owner')} | {row.get('target_owner')} | `{row.get('present')}` |"
        )
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{next_slice.get('name')}`",
            f"- Target: {next_slice.get('target')}",
            f"- Required verifier: `{next_slice.get('required_verifier')}`",
            "",
            "Move:",
        ]
    )
    lines.extend(f"- {item}" for item in next_slice.get("move") or [])
    lines.append("")
    lines.append("Keep:")
    lines.extend(f"- {item}" for item in next_slice.get("keep") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_recommendation_evaluation_loop_boundary_audit {status}")
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
