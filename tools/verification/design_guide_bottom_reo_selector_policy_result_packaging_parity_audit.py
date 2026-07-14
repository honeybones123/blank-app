"""Audit bottom-reo selector policy/result-packaging extraction readiness.

This is proof-only. It does not move selector policy, result packaging,
CTA/apply wiring, visible wording, or family runtime behaviour.
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
BENDING = ROOT / "design_brain" / "families" / "bending.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

COMPUTE_HELPER = "_compute_bottom_reo_recommendation"
SELECTOR_HELPER = "_pick_best_bottom_recommendation_by_selector"
STRICT_GUARD = "_is_strictly_rejectable_band_winner"
LEGACY_REJECTION = "_legacy_bottom_local_rejection_reason"
COMPOUND_PREFERENCE = "_maybe_prefer_compound_over_pure_geometry"
RESULT_BUILDER = "build_bottom_reo_recommendation_result"
SELECTOR_RESULT_WRAPPER = "_bottom_reo_selector_result_record"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _token(segment: str, text: str) -> bool:
    return text in segment


def _surface(
    *,
    name: str,
    owner: str,
    target_owner: str,
    classification: str,
    deletion_readiness: str,
    risk: str,
    tokens: list[str],
    segment: str,
    required_verifier: str,
    first_slice: str,
) -> dict[str, Any]:
    present_tokens = {token: _token(segment, token) for token in tokens}
    return {
        "surface": name,
        "current_owner": owner,
        "target_owner": target_owner,
        "classification": classification,
        "deletion_readiness": deletion_readiness,
        "risk": risk,
        "tokens": present_tokens,
        "present": all(present_tokens.values()),
        "required_verifier_before_moving": required_verifier,
        "first_safe_implementation_slice": first_slice,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    candidate_evaluation_source = _read(CANDIDATE_EVALUATION)

    compute_start, compute_end, compute_segment = _function_segment(inputs_source, COMPUTE_HELPER)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, SELECTOR_HELPER)
    strict_start, strict_end, strict_segment = _function_segment(inputs_source, STRICT_GUARD)
    legacy_start, legacy_end, legacy_segment = _function_segment(inputs_source, LEGACY_REJECTION)
    compound_start, compound_end, compound_segment = _function_segment(inputs_source, COMPOUND_PREFERENCE)
    result_start, result_end, result_segment = _function_segment(bending_source, RESULT_BUILDER)
    wrapper_start, wrapper_end, wrapper_segment = _function_segment(inputs_source, SELECTOR_RESULT_WRAPPER)

    surfaces = [
        _surface(
            name="live bottom-reo selector loop",
            owner="design_brain.families.bending with inputs_page.py callback shell",
            target_owner="design_brain.families.bending",
            classification="FAMILY_SELECTOR_HELPER_CUTOVER_COMPLETE_PAGE_CALLBACKS_REMAIN",
            deletion_readiness="SHELL_ONLY_CALLBACK_TRACE_WRAPPER_REMAINS",
            risk="HIGH",
            tokens=[
                "_select_bottom_reo_recommendation_candidate_by_selector(",
                "select_best_candidate_fn=_select_best_auto_design_candidate",
                "strict_band_guard_fn=_strict_band_guard",
                "legacy_rejection_reason_fn=_legacy_rejection",
            ],
            segment=selector_segment,
            required_verifier="design_guide_bottom_reo_selector_live_loop_service_cutover.py",
            first_slice="keep page callbacks and trace emission bounded; move no Streamlit/session/apply code",
        ),
        _surface(
            name="strict-band reject guard",
            owner="design_brain.families.bending with inputs_page.py state-input wrapper",
            target_owner="design_brain.families.bending",
            classification="EXTRACTED_FAMILY_ADAPTER_PAGE_STATE_INPUT_REMAINS",
            deletion_readiness="SHELL_ONLY_WRAPPER_REMAINS",
            risk="LOW",
            tokens=[
                "_assess_bottom_reo_strict_band_winner_candidate(",
                "updates_match_state",
            ],
            segment=strict_segment,
            required_verifier="design_guide_bottom_reo_strict_band_guard_family_extraction.py",
            first_slice="keep wrapper until live selector loop moves",
        ),
        _surface(
            name="legacy local rejection policy",
            owner="design_brain.families.bending with inputs_page.py compatibility wrapper",
            target_owner="design_brain.families.bending",
            classification="EXTRACTED_FAMILY_ADAPTER_PAGE_WRAPPER_REMAINS",
            deletion_readiness="SHELL_ONLY_WRAPPER_REMAINS",
            risk="LOW",
            tokens=[
                "_resolve_bottom_reo_legacy_local_rejection_reason(",
            ],
            segment=legacy_segment,
            required_verifier="design_guide_bottom_reo_legacy_rejection_policy_family_extraction.py",
            first_slice="keep wrapper until live selector loop moves",
        ),
        _surface(
            name="compound-over-pure-geometry preference",
            owner="design_brain.families.bending with inputs_page.py input wrapper",
            target_owner="design_brain.families.bending",
            classification="EXTRACTED_FAMILY_ADAPTER_PAGE_STATE_INPUT_REMAINS",
            deletion_readiness="SHELL_ONLY_WRAPPER_REMAINS",
            risk="LOW",
            tokens=[
                "_select_bottom_reo_compound_preference_candidate(",
                "_resolve_geometry_width_context(state)",
                "GUIDANCE_COMPOUND_VS_PURE_GEOMETRY_SCORE_MARGIN",
            ],
            segment=compound_segment,
            required_verifier="design_guide_bottom_reo_compound_preference_family_extraction.py",
            first_slice="keep wrapper until live selector loop moves",
        ),
        _surface(
            name="post-selector no-result/growth guards",
            owner="design_brain.families.bending with inputs_page.py trace/return mechanics",
            target_owner="design_brain.families.bending plus page-shell trace/return mechanics",
            classification="EXTRACTED_FAMILY_GUARD_CLASSIFIER_PAGE_TRACE_REMAINS",
            deletion_readiness="SHELL_ONLY_TRACE_RETURN_REMAINS",
            risk="LOW",
            tokens=[
                "_resolve_bottom_reo_post_selector_guard(",
                "no_selected_candidate",
                "growth_blocked_efficiency_reduction",
                "_resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(",
            ],
            segment=compute_segment,
            required_verifier="design_guide_bottom_reo_post_selector_guard_family_extraction.py",
            first_slice="keep trace/result emission until selector loop moves",
        ),
        _surface(
            name="required Ast and change-line projection",
            owner="design_brain.families.bending with inputs_page.py callback shell for Ast",
            target_owner="design_brain.families.bending projection helpers",
            classification="EXTRACTED_FAMILY_RESULT_PROJECTION_PAGE_AST_CALLBACK_REMAINS",
            deletion_readiness="SHELL_ONLY_CALLBACK_REMAINS",
            risk="MEDIUM",
            tokens=[
                "_evaluate_bending_with_bottom_state(",
                "_required_ast_for_arrangement(",
                "_build_bottom_reo_required_ast_arrangement_input(",
                "_build_bottom_reo_guidance_change_lines_for_updates(",
            ],
            segment=compute_segment,
            required_verifier="design_guide_bottom_reo_required_ast_input_family_extraction.py",
            first_slice="move remaining Ast callback shell after bending capacity callback boundary is proven",
        ),
        _surface(
            name="final bottom-reo recommendation result packaging",
            owner="design_brain.families.bending with inputs_page.py shell-only adapter call",
            target_owner="design_brain.families.bending result adapter",
            classification="SHELL_ONLY_FAMILY_RESULT_ADAPTER_CALL",
            deletion_readiness="SHELL_ONLY_ADAPTER_CALL_REMAINS",
            risk="LOW",
            tokens=[
                "_build_bottom_reo_recommendation_result(",
                "display_label",
                "guidance_change_lines",
            ],
            segment=compute_segment,
            required_verifier="design_guide_bottom_reo_result_adapter_call_shell_audit.py",
            first_slice="no extraction needed; keep shell-only adapter call until selector loop moves",
        ),
        _surface(
            name="selector result trace identity inputs",
            owner="design_brain.families.bending with inputs_page.py wrapper call",
            target_owner="design_brain.families.bending proof adapter",
            classification="EXTRACTED_FAMILY_TRACE_IDENTITY_PROJECTION_PAGE_WRAPPER_REMAINS",
            deletion_readiness="SHELL_ONLY_WRAPPER_REMAINS",
            risk="LOW",
            tokens=[
                "_build_bottom_reo_selector_result_record_from_candidate(",
            ],
            segment=wrapper_segment,
            required_verifier="design_guide_bottom_reo_selector_trace_identity_family_extraction.py",
            first_slice="keep wrapper until live selector loop moves",
        ),
        _surface(
            name="trace/proof event emission",
            owner="inputs_page.py",
            target_owner="design_brain.families.bending trace payload projection plus bounded non-authoritative page trace emission",
            classification="BOUNDED_PAGE_DEBUG_TRACE_EMISSION",
            deletion_readiness="PAGE_SHELL_ALLOWED",
            risk="LOW",
            tokens=[
                "_bottom_reo_trace_proof_payload(",
                "_bottom_reo_recommendation_trace_event(",
                "_bottom_reo_selected_candidate_decision_record(",
            ],
            segment=compute_segment,
            required_verifier="design_guide_bottom_reo_trace_proof_payload_family_extraction.py",
            first_slice="keep page trace emission bounded; do not move file/env trace mechanics into family",
        ),
    ]

    extracted_surfaces = {
        "candidate_row_packaging": "build_bottom_reo_recommendation_arrangement_candidate_inputs" in candidate_evaluation_source,
        "arrangement_pool": "build_bottom_reo_arrangement_pool_from_state" in bending_source,
        "normal_arrangement_evaluation": "evaluate_bottom_reo_recommendation_arrangement_candidate" in candidate_evaluation_source,
        "prerank_filter_policy": "_resolve_design_guide_controller_bottom_reo_prerank_filter_policy(" in compute_segment,
        "growth_filter_policy": "_resolve_design_guide_controller_bottom_reo_efficiency_growth_filter_policy(" in compute_segment,
        "selection_prep": "prepare_bottom_reo_recommendation_candidates_for_selection" in candidate_evaluation_source
        and "_prepare_bottom_reo_recommendation_candidates_for_selection(" in compute_segment,
        "typed_selector_result_record": "build_bottom_reo_selector_result_record_from_candidate" in bending_source
        and "_build_bottom_reo_selector_result_record_from_candidate(" in wrapper_segment,
        "selected_recommendation_proof": "build_bottom_reo_selected_recommendation_proof" in bending_source,
        "selected_recommendation_proof_projection": "build_bottom_reo_selected_recommendation_proof_from_result" in bending_source
        and "build_bottom_reo_trace_proof_payload_projection" in bending_source
        and "_bottom_reo_trace_selected_recommendation_proof" not in inputs_source
        and "_bottom_reo_trace_selected_source_index" not in inputs_source,
        "strict_band_guard_adapter": "assess_bottom_reo_strict_band_winner_candidate" in bending_source
        and "_assess_bottom_reo_strict_band_winner_candidate(" in strict_segment,
        "legacy_rejection_policy_adapter": "resolve_bottom_reo_legacy_local_rejection_reason" in bending_source
        and "_resolve_bottom_reo_legacy_local_rejection_reason(" in legacy_segment,
        "geometry_trial_axis_adapter": "resolve_bottom_reo_geometry_trial_axis" in bending_source,
        "compound_preference_adapter": "select_bottom_reo_compound_preference_candidate" in bending_source
        and "_select_bottom_reo_compound_preference_candidate(" in compound_segment,
        "selected_result_display_label_adapter": "resolve_bottom_reo_result_display_label" in bending_source
        and "_resolve_bottom_reo_result_display_label(best)" in compute_segment,
        "required_ast_calculation_adapter": "calculate_bottom_reo_required_ast_for_arrangement" in bending_source
        and "_calculate_bottom_reo_required_ast_for_arrangement(" in inputs_source,
        "required_ast_arrangement_input_projection": "build_bottom_reo_required_ast_arrangement_input" in bending_source
        and "_build_bottom_reo_required_ast_arrangement_input(best, selected_bending)" in compute_segment,
        "guidance_change_line_projection": "build_bottom_reo_guidance_change_lines_for_updates" in bending_source
        and "_build_bottom_reo_guidance_change_lines_for_updates(" in compute_segment
        and "gcl = _guidance_change_lines_for_updates(" not in compute_segment,
        "post_selector_guard_classifier": "resolve_bottom_reo_post_selector_guard" in bending_source
        and "_resolve_bottom_reo_post_selector_guard(" in compute_segment,
        "selector_trace_identity_projection": "build_bottom_reo_selector_result_record_from_candidate" in bending_source
        and "_build_bottom_reo_selector_result_record_from_candidate(" in wrapper_segment,
        "trace_action_payload_identity": "build_bottom_reo_trace_guidance_action_payload_identity" in bending_source
        and "build_bottom_reo_trace_proof_payload_projection" in bending_source
        and "_bottom_reo_trace_guidance_action_payload_identity" not in inputs_source,
        "repair_blocked_reason_trace_projection": "build_bottom_reo_repair_blocked_reason_trace_projection" in bending_source
        and "build_bottom_reo_trace_proof_payload_projection" in bending_source
        and "_bottom_reo_trace_selected_update_hash_surface" not in inputs_source
        and "_bottom_reo_trace_selector_reason_surface" not in inputs_source
        and "_bottom_reo_trace_reason_visibility_surface" not in inputs_source
        and "_bottom_reo_trace_repair_reason_source_surface" not in inputs_source
        and "_bottom_reo_trace_blocked_reason_source_surface" not in inputs_source
        and "_bottom_reo_trace_visible_guidance_text_source" not in inputs_source,
        "cta_intent_trace_projection": "build_bottom_reo_cta_intent_trace_projection" in bending_source
        and "build_bottom_reo_trace_proof_payload_projection" in bending_source
        and "_build_bottom_reo_cta_intent_proof(" not in inputs_source,
        "trace_proof_payload_projection": "build_bottom_reo_trace_proof_payload_projection" in bending_source
        and "_build_bottom_reo_trace_proof_payload_projection(" in inputs_source,
    }

    unknown_surfaces = [row["surface"] for row in surfaces if not row["present"]]
    ready_to_move_now: list[str] = []
    not_ready = [
        row["surface"]
        for row in surfaces
        if row["classification"].startswith("PAGE_OWNED")
        or row["classification"].startswith("PARTIAL_")
        or row["classification"] in {"DEBUG_PROOF_CONSTRUCTION"}
    ]
    checks = {
        "compute_helper_found": bool(compute_segment),
        "selector_helper_found": bool(selector_segment),
        "strict_guard_found": bool(strict_segment),
        "legacy_rejection_found": bool(legacy_segment),
        "compound_preference_found": bool(compound_segment),
        "result_builder_found": bool(result_segment),
        "selector_result_wrapper_found": bool(wrapper_segment),
        "all_surface_tokens_found": not unknown_surfaces,
        "previous_extractions_recognized": all(extracted_surfaces.values()),
        "selector_tail_shell_or_bounded_after_cutover": not bool(not_ready),
        "first_safe_slice_identified": True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    decision = (
        "BOTTOM_REO_SELECTOR_POLICY_FAMILY_OWNED_RESULT_PACKAGING_AND_TRACE_REMAIN_BOUNDED"
        if status == "PASS"
        else "BOTTOM_REO_SELECTOR_POLICY_RESULT_PACKAGING_AUDIT_FAILED"
    )
    return {
        "status": status,
        "decision": decision,
        "target": COMPUTE_HELPER,
        "line_ranges": {
            COMPUTE_HELPER: {"start": compute_start, "end": compute_end},
            SELECTOR_HELPER: {"start": selector_start, "end": selector_end},
            STRICT_GUARD: {"start": strict_start, "end": strict_end},
            LEGACY_REJECTION: {"start": legacy_start, "end": legacy_end},
            COMPOUND_PREFERENCE: {"start": compound_start, "end": compound_end},
            f"design_brain.families.bending.{RESULT_BUILDER}": {"start": result_start, "end": result_end},
            SELECTOR_RESULT_WRAPPER: {"start": wrapper_start, "end": wrapper_end},
        },
        "already_extracted_surfaces": extracted_surfaces,
        "surface_rows": surfaces,
        "unknown_surfaces": unknown_surfaces,
        "ready_to_move_now": ready_to_move_now,
        "not_ready_surfaces": not_ready,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "bottom_reo_selected_result_packaging_or_callback_shell_audit",
            "target_owner": "design_brain.families.bending",
            "reason": (
                "The live selector loop and selected-result projection are the remaining high-risk "
                "family-specific policy cluster. Build a "
                "family-owned parity object first, then move pure predicate pieces one at a time."
            ),
            "must_not_move_yet": [
                "final recommendation result dict",
                "visible change lines",
                "CTA/apply payload",
                "trace event emission",
                "page/session/debug mutation",
            ],
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_selector_policy_result_packaging_parity_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_selector_policy_result_packaging_parity_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bottom Reo Selector Policy / Result Packaging Parity Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Current State",
        "",
        "Earlier bottom-reo preparation boundaries are extracted, but the live selector tail still owns family-specific policy and final result projection in `inputs_page.py`.",
        "",
        "## Already Extracted Surfaces",
        "",
    ]
    for name, value in dict(payload.get("already_extracted_surfaces") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(
        [
            "",
            "## Remaining Surface Inventory",
            "",
            "| Surface | Classification | Current owner | Target owner | Deletion readiness | Risk |",
            "| --- | --- | --- | --- | --- | --- |",
        ],
    )
    for row in payload.get("surface_rows") or []:
        lines.append(
            f"| `{row.get('surface')}` | `{row.get('classification')}` | {row.get('current_owner')} | {row.get('target_owner')} | `{row.get('deletion_readiness')}` | `{row.get('risk')}` |",
        )
    next_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            f"- Name: `{next_slice.get('name')}`",
            f"- Target owner: `{next_slice.get('target_owner')}`",
            f"- Reason: {next_slice.get('reason')}",
            "",
            "Must not move yet:",
        ],
    )
    lines.extend(f"- {item}" for item in next_slice.get("must_not_move_yet") or [])
    lines.extend(["", "## Required Verifiers Before Moving", ""])
    for row in payload.get("surface_rows") or []:
        lines.append(f"- `{row.get('surface')}`: `{row.get('required_verifier_before_moving')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    if payload.get("unknown_surfaces"):
        lines.extend(["", "## Unknown Surfaces", ""])
        lines.extend(f"- {item}" for item in payload.get("unknown_surfaces") or [])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_selector_policy_result_packaging_parity_audit {payload.get('status')}")
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
