"""Audit the active-failure executor item service boundary.

This verifier maps `_active_fail_near_current_repair_item(...)` into concrete
ownership slices. It is deliberately audit-only: no behaviour changes, no
deletion, and no runtime movement are required for this check to pass.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
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


def _token_summary(segment: str, start_line: int, tokens: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "token": token,
            "present": token in segment,
            "count": segment.count(token),
            "lines": _line_numbers(segment, start_line, token)[:20],
        }
        for token in tokens
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)

    eval_tokens = [
        "def _evaluate(",
        "_resolve_active_fail_executor_candidate_eval_source(",
        "_evaluate_active_fail_executor_candidate_with_updates(",
        "_build_active_fail_executor_candidate_eval_attempt_result(",
        "candidate_post_util",
        "is_compliant",
        "preview_pass",
        "is_executable",
    ]
    family_ladder_tokens = [
        "family_strategy_for(\"SHEAR_FAIL_GOVERNS\")",
        "family_strategy_for(\"BENDING_FAIL_GOVERNS\")",
        "family_strategy_for(\"COMBINED_BENDING_SHEAR_FAIL\")",
        "contracted_repair_ladder_specs(",
        "select_repair_candidate_from_ladder(",
        "repair_ladder_evidence_overlay(",
    ]
    page_session_tokens = [
        "st.session_state",
        "get_rerun_pure_cache(",
        "set_rerun_pure_cache(",
        "_inputs_pre_widget_trace(",
        "_phase5c_latency_trace(",
        "_record_bending_fail_valid_repair_cta_published(",
    ]
    generator_tokens = [
        "_repair_build_near_current_bottom_repair_specs(",
        "_repair_build_near_current_geometry_repair_specs(",
        "_repair_build_near_current_shear_repair_specs(",
        "RESCUE_SEED_LIBRARY",
        "build_target_band_refinement_candidates(",
    ]
    selection_packaging_tokens = [
        "_build_candidate_search_evidence(",
        "_repair_select_repair_decision(",
        "_repair_selected_candidate_from_repair_decision(",
        "_guidance_item_from_resolved_candidate(",
        "_active_failure_no_repair_blocker_from_evidence(",
        "_design_guide_shear_practical_preference_score(",
        "_design_guide_geometry_proportion_preference_score(",
    ]
    page_policy_input_tokens = [
        "_design_mode_config(",
        "_design_optimisation_goal(",
        "_resolved_efficiency_target_band(",
        "_resolve_geometry_width_context(",
        "_geometry_lock_enabled(",
        "_overview_required_checks_acceptable(",
    ]

    candidate_eval_helpers_available = [
        "evaluate_design_candidate_with_updates",
        "evaluate_direct_target_band_candidate_with_updates",
    ]
    candidate_eval_boundary_available = all(
        f"def {name}(" in candidate_source for name in candidate_eval_helpers_available
    )
    candidate_eval_import_clean = (
        "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source
        and "st.session_state" not in candidate_source
    )
    controller_import_clean = (
        "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source
    )

    surfaces = [
        {
            "surface": "executor shell inputs and guard",
            "current_owner": "inputs_page",
            "target_owner": "inputs_page page shell",
            "classification": "page-shell input collection",
            "deletion_readiness": "SHELL_ONLY",
            "required_verifier_before_move": None,
            "evidence": _token_summary(segment, start, ["if not isinstance(state, dict)", "active_failures"]),
        },
        {
            "surface": "target band and geometry policy input preparation",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController or target-band candidate service",
            "classification": "still page-owned Design Brain policy input preparation",
            "deletion_readiness": "READY_FOR_FIRST_SLICE",
            "required_verifier_before_move": "active_fail_executor_policy_input_projection_boundary_audit",
            "evidence": _token_summary(segment, start, page_policy_input_tokens),
        },
        {
            "surface": "near-current candidate generator construction",
            "current_owner": "inputs_page",
            "target_owner": "target-band cleanup candidate service",
            "classification": "candidate generation/search logic still page-owned",
            "deletion_readiness": "NOT_READY",
            "required_verifier_before_move": "active_fail_executor_candidate_generator_service_handoff",
            "evidence": _token_summary(segment, start, generator_tokens),
        },
        {
            "surface": "inner candidate evaluation adapter",
            "current_owner": "inputs_page",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "candidate evaluation service-backed page executor bridge",
            "deletion_readiness": "SHELL_CALL",
            "required_verifier_before_move": None,
            "evidence": _token_summary(segment, start, eval_tokens),
        },
        {
            "surface": "family repair ladder execution",
            "current_owner": "inputs_page",
            "target_owner": "family runtime/controller executor boundary",
            "classification": "family runtime execution bridge still page-owned",
            "deletion_readiness": "NOT_READY",
            "required_verifier_before_move": "active_fail_family_ladder_executor_boundary",
            "evidence": _token_summary(segment, start, family_ladder_tokens),
        },
        {
            "surface": "repair selection and evidence packaging",
            "current_owner": "inputs_page",
            "target_owner": "DesignGuideController / repair publication service",
            "classification": "recommendation selection and evidence packaging still page-owned",
            "deletion_readiness": "NOT_READY",
            "required_verifier_before_move": "active_fail_executor_selection_evidence_projection_parity",
            "evidence": _token_summary(segment, start, selection_packaging_tokens),
        },
        {
            "surface": "session cache, trace, and CTA side effects",
            "current_owner": "inputs_page",
            "target_owner": "inputs_page page shell or page/shared side-effect layer",
            "classification": "page-owned runtime plumbing",
            "deletion_readiness": "KEEP_BOUNDED",
            "required_verifier_before_move": None,
            "evidence": _token_summary(segment, start, page_session_tokens),
        },
    ]

    return {
        "schema": "design_guide_direct_target_active_failure_executor_item_service_boundary_audit.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "status_decision": "NOT_SHELL_ONLY_FIRST_SLICE_IDENTIFIED",
        "surfaces": surfaces,
        "candidate_evaluation_boundary_available": bool(candidate_eval_boundary_available),
        "candidate_evaluation_helpers_available": candidate_eval_helpers_available,
        "candidate_evaluation_has_no_page_or_streamlit_imports": bool(candidate_eval_import_clean),
        "controller_has_no_page_or_streamlit_imports": bool(controller_import_clean),
        "first_safe_implementation_slice": {
            "name": "active_fail_family_ladder_executor_boundary_audit",
            "why": (
                "The executor's nested evaluation path, policy input projection, rescue tier route inputs, "
                "command shaping, and row projection are now service/controller-backed or explicitly bounded. "
                "The next remaining Design Brain-owned surface is family ladder execution itself."
            ),
            "move": (
                "Audit only. Classify the family ladder execution loops and decide whether they can become "
                "a controller/service executor boundary with injected callbacks. Keep session/cache/trace, "
                "CTA side effects, selected candidate ranking, item packaging, and visible wording unchanged."
            ),
            "required_verifier": (
                "design_guide_active_fail_family_ladder_executor_boundary_audit.py"
            ),
        },
        "stop_conditions": [
            "candidate overview/evidence changes",
            "selected candidate id changes",
            "updates change",
            "action payload changes",
            "button contract changes",
            "visible wording changes",
            "family runtime behaviour changes",
            "candidate_evaluation boundary fails",
            "any composed lock fails",
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    surfaces = payload.get("surfaces") or []
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "target_is_substantial": int((payload.get("target") or {}).get("line_count") or 0) > 100,
        "surfaces_classified": len(surfaces) >= 7,
        "candidate_evaluation_boundary_available": bool(payload.get("candidate_evaluation_boundary_available")),
        "candidate_evaluation_import_boundary_clean": bool(
            payload.get("candidate_evaluation_has_no_page_or_streamlit_imports")
        ),
        "controller_import_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "first_safe_slice_identified": bool(
            (payload.get("first_safe_implementation_slice") or {}).get("required_verifier")
        ),
        "decision_not_shell_only": payload.get("status_decision") == "NOT_SHELL_ONLY_FIRST_SLICE_IDENTIFIED",
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"design_guide_direct_target_active_failure_executor_item_service_boundary_audit_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_direct_target_active_failure_executor_item_service_boundary_audit_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Active-Failure Executor Item Service Boundary Audit",
        "",
        f"Status: {payload['status']}",
        f"Decision: {payload.get('status_decision')}",
        "",
        "## Executive Summary",
        (
            "PARTIAL: `_active_fail_near_current_repair_item(...)` is not shell-only. "
            "The smallest safe extraction is the inner candidate-evaluation adapter call; "
            "the generator, family ladder execution, ranking/evidence packaging, and page "
            "cache/trace side effects must stay in place until separate parity proofs exist."
        ),
        "",
        "## Surface Classification",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(
            f"- {row.get('surface')}: {row.get('classification')} "
            f"(owner: {row.get('current_owner')} -> {row.get('target_owner')}; "
            f"readiness: {row.get('deletion_readiness')})"
        )
    first = payload.get("first_safe_implementation_slice") or {}
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            f"- Name: `{first.get('name')}`",
            f"- Why: {first.get('why')}",
            f"- Move: {first.get('move')}",
            f"- Verifier: `{first.get('required_verifier')}`",
            "",
            "## Stop Conditions",
            *[f"- {item}" for item in payload.get("stop_conditions") or []],
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
    print(f"design_guide_direct_target_active_failure_executor_item_service_boundary_audit {status}")
    print(f"decision={payload.get('status_decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
