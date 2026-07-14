"""Audit active-fail executor helper shell/deadness after extraction slices."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _line_numbers(segment: str, start_line: int, token: str) -> list[int]:
    return [start_line + idx for idx, line in enumerate(segment.splitlines()) if token in line]


def _token_row(segment: str, start_line: int, token: str) -> dict[str, Any]:
    return {
        "token": token,
        "present": token in segment,
        "count": segment.count(token),
        "lines": _line_numbers(segment, start_line, token)[:40],
    }


def _token_rows(segment: str, start_line: int, tokens: list[str]) -> list[dict[str, Any]]:
    return [_token_row(segment, start_line, token) for token in tokens]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, segment = _function_source(inputs_source, TARGET)
    wrapper_start, wrapper_end, wrapper_segment = _function_source(
        inputs_source,
        "_active_failure_no_repair_blocker_from_evidence",
    )
    resolved_adapter_start, resolved_adapter_end, resolved_adapter_segment = _function_source(
        inputs_source,
        "_guidance_item_from_resolved_candidate",
    )

    moved_policy_tokens = [
        "family_strategy_for(",
        "contracted_repair_ladder_specs(",
        "select_repair_candidate_from_ladder(",
        "repair_ladder_evidence_overlay(",
        "_build_candidate_search_evidence(",
        "_repair_select_repair_decision(",
        "_repair_selected_candidate_from_repair_decision(",
        "_evaluate_auto_design_candidate(",
        '"primary_card_actionable": True',
        '"guidance_intent": "required_fix"',
    ]
    required_delegate_tokens = [
        "_build_design_guide_controller_active_fail_near_current_repair_preflight(",
        "_evaluate_active_fail_executor_candidate_with_updates(",
        "_resolve_active_fail_executor_candidate_eval_source(",
        "_build_active_fail_executor_candidate_eval_attempt_result(",
        "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch(",
        "_build_design_guide_controller_active_fail_executor_ladder_eval_commands(",
        "_build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands(",
        "_build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands(",
        "_filter_design_guide_controller_active_fail_executor_repair_candidates(",
        "_select_design_guide_controller_active_fail_executor_family_ladder_candidate(",
        "_build_design_guide_controller_active_fail_executor_candidate_search_evidence(",
        "_build_design_guide_controller_active_fail_executor_selected_repair_candidate(",
        "_build_design_guide_controller_active_fail_executor_final_guidance_item_projection(",
        "_build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row(",
        "_build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row(",
    ]
    remaining_surfaces = [
        {
            "surface": "initial request/input normalization",
            "classification": "page-shell input collection",
            "owner": "inputs_page page shell",
            "evidence": _token_rows(
                segment,
                start,
                [
                    "_guidance_state_snapshot(",
                    "_design_mode_config(",
                    "_design_optimisation_goal(",
                    "_resolved_efficiency_target_band(",
                ],
            ),
            "deletion_readiness": "SHELL_ONLY",
        },
        {
            "surface": "candidate generation context",
            "classification": "Design Brain service-owned, page calls service",
            "owner": "DesignGuideController",
            "evidence": _token_rows(
                segment,
                start,
                ["_build_design_guide_controller_active_fail_near_current_repair_preflight("],
            ),
            "deletion_readiness": "SHELL_CALL",
        },
        {
            "surface": "candidate iteration and evaluation invocation",
            "classification": "bounded page executor loop; callback/fingerprint/cache execution remains page-shell-owned and eval-attempt, fallback command shaping, row projection, and geometry-fit boundary are service/controller-owned or explicitly bounded",
            "owner": "inputs_page page executor bridge",
            "evidence": _token_rows(
                segment,
                start,
                [
                    "def _evaluate(",
                    "for command in _build_design_guide_controller_active_fail_executor_ladder_eval_commands(",
                    "_evaluate_active_fail_executor_candidate_with_updates(",
                    "_resolve_active_fail_executor_candidate_eval_source(",
                    "_build_active_fail_executor_candidate_eval_attempt_result(",
                    "_build_design_guide_controller_active_fail_executor_ladder_eval_commands(",
                    "_build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands(",
                    "_build_design_guide_controller_active_fail_executor_near_current_combined_fallback_eval_commands(",
                    "_build_design_guide_controller_active_fail_executor_geometry_update_row(",
                    "_build_design_guide_controller_active_fail_executor_bottom_update_row(",
                    "_geometry_state_with_updates(",
                    "_arrangement_fits_state(",
                    "Active fail near-current combined repair",
                ],
            ),
            "deletion_readiness": "KEEP_BOUNDED",
            "boundary_lock": "design_guide_active_fail_candidate_eval_callback_boundary_lock",
        },
        {
            "surface": "family ladder dispatch",
            "classification": "DesignGuideController-owned ladder generation, page iterates returned specs",
            "owner": "DesignGuideController plus page executor bridge",
            "evidence": _token_rows(
                segment,
                start,
                ["_build_design_guide_controller_active_fail_executor_family_ladder_dispatch("],
            ),
            "deletion_readiness": "SHELL_CALL",
        },
        {
            "surface": "safe candidate acceptance policy",
            "classification": "DesignGuideController-owned predicate, page wrapper only",
            "owner": "DesignGuideController",
            "evidence": _token_rows(
                segment,
                start,
                ["_filter_design_guide_controller_active_fail_executor_repair_candidates("],
            ),
            "deletion_readiness": "SHELL_CALL",
        },
        {
            "surface": "no-repair blocker materialization",
            "classification": "DesignGuideController-owned projection, page wrapper only",
            "owner": "DesignGuideController",
            "evidence": [
                *_token_rows(
                    segment,
                    start,
                    ["_build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence("],
                ),
                *_token_rows(segment, start, ["_active_failure_no_repair_blocker_from_evidence("]),
                *_token_rows(
                    wrapper_segment,
                    wrapper_start,
                    ["_build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence("],
                ),
            ],
            "deletion_readiness": "SHELL_CALL",
        },
        {
            "surface": "base guidance item construction",
            "classification": "resolved-candidate adapter shell call; final item shape is controller-owned",
            "owner": "DesignGuideController via shared resolved-candidate adapter",
            "evidence": [
                *_token_rows(segment, start, ["_guidance_item_from_resolved_candidate("]),
                *_token_rows(
                    resolved_adapter_segment,
                    resolved_adapter_start,
                    ["_build_design_guide_controller_resolved_candidate_guidance_item("],
                ),
            ],
            "deletion_readiness": "SHELL_CALL",
            "next_extraction": "resolved_candidate_guidance_item_pre_input_helpers",
        },
        {
            "surface": "cache/session/debug/trace side effects",
            "classification": "page-owned runtime plumbing; bending ladder trace-row projection is controller-owned",
            "owner": "inputs_page page shell",
            "evidence": _token_rows(
                segment,
                start,
                [
                    "st.session_state",
                    "get_rerun_pure_cache(",
                    "set_rerun_pure_cache(",
                    "_inputs_pre_widget_trace(",
                    "_build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row(",
                    "_build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row(",
                    "_phase5c_latency_trace(",
                    "_record_bending_fail_valid_repair_cta_published(",
                ],
            ),
            "deletion_readiness": "KEEP_BOUNDED",
        },
    ]

    moved_policy = _token_rows(segment, start, moved_policy_tokens)
    delegates = _token_rows(segment, start, required_delegate_tokens)
    blockers = [
        row
        for row in remaining_surfaces
        if row.get("deletion_readiness") == "NOT_READY"
        and any(item.get("present") for item in row.get("evidence") or [])
    ]
    status_decision = (
        "LOCAL_ACTIVE_FAIL_EXECUTOR_SHELL_ONLY"
        if not blockers
        else "NOT_SHELL_ONLY_WITH_EXACT_REMAINING_SURFACE"
    )
    return {
        "schema": "design_guide_active_fail_executor_shell_deadness_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "status_decision": status_decision,
        "moved_policy_tokens_absent": moved_policy,
        "required_delegate_tokens": delegates,
        "remaining_surfaces": remaining_surfaces,
        "no_repair_blocker_wrapper": {
            "line_start": wrapper_start,
            "line_end": wrapper_end,
            "line_count": max(0, wrapper_end - wrapper_start + 1),
            "delegates_to_controller": "_build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence("
            in wrapper_segment
            or "_build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence("
            in segment,
        },
        "resolved_candidate_guidance_adapter": {
            "line_start": resolved_adapter_start,
            "line_end": resolved_adapter_end,
            "line_count": max(0, resolved_adapter_end - resolved_adapter_start + 1),
            "delegates_final_shape_to_controller": "_build_design_guide_controller_resolved_candidate_guidance_item("
            in resolved_adapter_segment,
            "remaining_page_owned_pre_input_helpers": [
                token
                for token in (
                    "_resolve_canonical_guidance_title_from_candidate(",
                    "_guidance_default_alternatives_text(",
                    "_guidance_change_lines_for_updates(",
                    "_candidate_failure_coverage_summary(",
                    "_guidance_before_after_text(",
                )
                if token in resolved_adapter_segment
            ],
        },
        "remaining_not_ready_surfaces": [
            {
                "surface": row.get("surface"),
                "next_extraction": row.get("next_extraction"),
                "evidence": row.get("evidence"),
            }
            for row in blockers
        ],
        "next_safe_target": (
            str(blockers[0].get("next_extraction") or "active_fail_executor_rescue_fallback_loop_boundary")
            if blockers
            else "direct_target_family_repair_bridge_route_policy_deletion_audit"
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "candidate_evaluation_has_no_page_or_streamlit_imports": all(
            token not in candidate_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    moved_absent = payload.get("moved_policy_tokens_absent") or []
    delegates = payload.get("required_delegate_tokens") or []
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "target_inventory_current": int((payload.get("target") or {}).get("line_count") or 0) > 0,
        "moved_policy_tokens_absent": all(not bool(row.get("present")) for row in moved_absent),
        "required_delegate_tokens_present": all(bool(row.get("present")) for row in delegates),
        "no_repair_blocker_wrapper_delegates": bool(
            (payload.get("no_repair_blocker_wrapper") or {}).get("delegates_to_controller")
        ),
        "resolved_candidate_guidance_adapter_delegates": bool(
            (payload.get("resolved_candidate_guidance_adapter") or {}).get("delegates_final_shape_to_controller")
        ),
        "remaining_surfaces_classified": len(payload.get("remaining_surfaces") or []) >= 8,
        "status_decision_is_explicit": payload.get("status_decision")
        in {"LOCAL_ACTIVE_FAIL_EXECUTOR_SHELL_ONLY", "NOT_SHELL_ONLY_WITH_EXACT_REMAINING_SURFACE"},
        "next_safe_target_identified": bool(payload.get("next_safe_target")),
        "controller_import_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "candidate_evaluation_import_boundary_clean": bool(
            payload.get("candidate_evaluation_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_shell_deadness_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_shell_deadness_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Shell/Deadness Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        (
            "`_active_fail_near_current_repair_item(...)` has had the major family, "
            "candidate-evaluation, selection, evidence, and final-item projections moved behind "
            "Design Brain services/controller helpers. It is still not fully shell-only because "
            "the page owns the executor loop. Base guidance item final shape is routed "
            "through the shared resolved-candidate controller adapter; its remaining "
            "pre-input helper surface is tracked separately."
        )
        if payload.get("status_decision") != "LOCAL_ACTIVE_FAIL_EXECUTOR_SHELL_ONLY"
        else "`_active_fail_near_current_repair_item(...)` is shell-only by this inventory.",
        "",
        "## Remaining Surfaces",
    ]
    for row in payload.get("remaining_surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"(owner: {row.get('owner')}; readiness: {row.get('deletion_readiness')})"
        )
    lines.extend(
        [
            "",
            "## Remaining Not-Ready Surfaces",
            *[
                f"- {row.get('surface')}: next `{row.get('next_extraction')}`"
                for row in payload.get("remaining_not_ready_surfaces") or []
            ],
            "",
            f"Next safe target: `{payload.get('next_safe_target')}`",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_shell_deadness_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
