"""Bridge-independent production adapter for candidate Design overviews."""

from __future__ import annotations

from typing import Any, Mapping

from bending_checks_helpers import build_bending_check_rows_from_state
from inputs_application.candidate_metrics import (
    candidate_bottom_updates,
    status_from_candidate_util,
)
from inputs_application.crack_evaluation import (
    _evaluate_crack_with_state_for_app_bridge,
    build_crack_evaluation_runtime,
)
from inputs_application.deflection_evaluation import (
    DeflectionEvaluationRuntime,
    _evaluate_deflection_with_state_for_app_bridge,
)
from inputs_application.recommendation_evaluation import effective_bottom_design_state
from inputs_application.recommendation_support import design_width_value
from inputs_application.state_utils import (
    float_from_state,
    guidance_state_snapshot,
    state_with_resolved_design_actions,
)
from inputs_page_modules.app_bridge.design_overview_collector import (
    DesignOverviewRuntime,
    _collect_design_overview,
)
from shear_checks_helpers import build_shear_check_rows_from_state
from state_and_helpers import (
    get_rerun_pure_cache,
    resolve_design_actions,
    set_rerun_pure_cache,
    stable_fingerprint_for_payload,
    ux_probe_record,
)


def _parse_util(value: Any) -> float | None:
    if value in (None, "", "—"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None


def _overall_status(rows: list[dict]) -> tuple[str, str]:
    filtered = [
        row
        for row in rows or []
        if isinstance(row, dict)
        and not row.get("is_informational")
        and str(row.get("status", "")).upper() != "INFO"
    ]
    if not filtered:
        return "—", "rgba(31, 119, 180, 0.08)"
    statuses = [str(row.get("status", "")).upper() for row in filtered]
    if any("FAIL" in status or status == "NG" for status in statuses):
        return "FAIL", "rgba(255,0,0,0.12)"
    if any(
        "WARN" in status or "NEAR LIMIT" in status or status == "CHECK"
        for status in statuses
    ):
        return "NEAR LIMIT", "rgba(255,193,7,0.15)"
    if any("PASS" in status or status == "OK" for status in statuses):
        return "PASS", "rgba(0,128,0,0.12)"
    return "—", "rgba(31, 119, 180, 0.08)"


def build_design_actions_context(state: dict) -> dict:
    source = guidance_state_snapshot(state)
    actions = resolve_design_actions(source)
    return {
        "state": state_with_resolved_design_actions(source, actions),
        "actions": dict(actions),
        "action_signature": tuple(actions.get("signature", ())),
    }


def _build_crack_pack(state: dict) -> dict:
    crack = _evaluate_crack_with_state_for_app_bridge(
        state,
        bottom_updates=candidate_bottom_updates(state),
        runtime=build_crack_evaluation_runtime(),
    )
    if crack is None:
        return {"summary_util": None, "rows": []}
    util = float(crack.get("util", 0.0) or 0.0)
    stress = float(crack.get("sigma_sr", 0.0) or 0.0)
    allowable = float(crack.get("sigma_allow_table", 0.0) or 0.0)
    crack_width = float(crack.get("w_calc", 0.0) or 0.0)
    width_limit = float_from_state(state, "wmax_char_limit", 0.3)
    return {
        "summary_util": util,
        "rows": [
            {
                "uid": "crk_step_4",
                "title": "Governing outcome",
                "value": "Both checks pass" if util <= 1.0 else "One or more checks fail",
                "limit": "Table stress + direct width",
                "util": "—",
                "status": "PASS" if util <= 1.0 else "FAIL",
                "route_page": "crack",
            },
            {
                "uid": "crk_step_2",
                "title": "Table-based crack control check",
                "value": f"σ_sr = {stress:.1f} MPa",
                "limit": f"σ_allow = {allowable:.1f} MPa" if allowable > 0.0 else "—",
                "util": f"{stress / allowable:.2f}" if allowable > 0.0 else "—",
                "status": status_from_candidate_util(
                    stress / allowable if allowable > 0.0 else None
                ),
                "route_page": "crack",
            },
            {
                "uid": "crk_step_3",
                "title": "Direct crack width check",
                "value": f"w = {crack_width:.3f} mm",
                "limit": f"w'max = {width_limit:.3f} mm" if width_limit > 0.0 else "—",
                "util": f"{crack_width / width_limit:.2f}" if width_limit > 0.0 else "—",
                "status": status_from_candidate_util(
                    crack_width / width_limit if width_limit > 0.0 else None
                ),
                "route_page": "crack",
            },
        ],
    }


def _build_deflection_pack(
    state: dict,
    *,
    session_state: Mapping[str, Any],
) -> dict:
    result = _evaluate_deflection_with_state_for_app_bridge(
        state,
        bottom_updates=candidate_bottom_updates(state),
        runtime=DeflectionEvaluationRuntime(
            session_state=session_state,
            design_width=design_width_value,
            effective_bottom=effective_bottom_design_state,
            float_from_state=float_from_state,
            status_from_util=status_from_candidate_util,
        ),
    )
    if result is None:
        return {
            "summary_delta_total_mm": None,
            "summary_defl_limit_mm": None,
            "summary_util_total": None,
            "rows": [],
        }
    return dict(result.get("pack") or {})


def _stage3_shear_truth(state: dict | None) -> dict:
    keys = (
        "shear_truth_status",
        "shear_truth_reason",
        "shear_truth_governing_check_name",
        "shear_truth_governing_reason",
        "shear_truth_governing_source",
        "final_shear_status_source",
        "final_shear_truth_resolved",
        "final_shear_truth_failure_reason",
        "final_shear_truth_bundle_complete",
        "shear_provided_input_spacing_mm",
        "shear_input_spacing_mm",
        "shear_sectional_check_spacing_mm",
        "shear_effective_spacing_mm",
        "shear_required_spacing_mm",
        "shear_governing_spacing_source",
        "published_result_spacing_mm",
        "published_result_spacing_meaning",
    )
    source = dict(state or {})
    result = {key: source.get(key) for key in keys}
    result["design_guide_shear_truth_source"] = "final_published_shear_truth"
    result["final_shear_truth_normalized_source"] = source.get(
        "_final_shear_truth_normalized_source"
    )
    result["final_shear_truth_normalized_latest"] = dict(
        source.get("_final_shear_truth_normalized_latest") or {}
    )
    return result


def _stage3_remaining_issue(state: dict, overview: dict) -> str | None:
    shear_status = str(
        (overview.get("statuses") or {}).get("shear") or ""
    ).strip().upper()
    design_status = str(state.get("shear_design_status") or "").strip().upper()
    unresolved = state.get("final_shear_truth_resolved") is False
    failure = bool(
        str(state.get("final_shear_truth_failure_reason") or "").strip()
        or str(state.get("shear_truth_status") or "").strip()
    )
    if design_status == "INVALID" and shear_status == "PASS":
        return "truth"
    if unresolved and failure and shear_status == "PASS":
        return "truth"
    return None


def collect_design_overview(
    state: dict,
    context: dict | None = None,
    *,
    session_state: Mapping[str, Any],
) -> dict:
    return _collect_design_overview(
        state,
        context=context,
        runtime=DesignOverviewRuntime(
            build_bending_pack=build_bending_check_rows_from_state,
            build_crack_pack=_build_crack_pack,
            build_deflection_pack=lambda current: _build_deflection_pack(
                current,
                session_state=session_state,
            ),
            build_actions_context=build_design_actions_context,
            build_shear_pack=build_shear_check_rows_from_state,
            overall_status=_overall_status,
            parse_util=_parse_util,
            resolve_actions=resolve_design_actions,
            stage3_shear_truth=_stage3_shear_truth,
            stage3_remaining_issue=_stage3_remaining_issue,
            state_with_actions=state_with_resolved_design_actions,
            get_cache=get_rerun_pure_cache,
            set_cache=set_rerun_pure_cache,
            stable_fingerprint=stable_fingerprint_for_payload,
            probe_record=ux_probe_record,
        ),
    )


__all__ = ["build_design_actions_context", "collect_design_overview"]
