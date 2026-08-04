"""Bridge-independent production assembly for recommendation candidate evaluation."""

from __future__ import annotations

from typing import Any, Mapping

from inputs_application.candidate_metrics import (
    bottom_bar_count,
    bottom_row_count,
    candidate_bottom_updates,
    candidate_shear_updates,
    int_from_state,
    reo_congestion_index,
    status_from_candidate_util,
    candidate_state_to_shared_updates,
    compute_reo_complexity,
)
from inputs_application.candidate_search_evaluation import (
    CandidateSearchEvaluationRuntime,
    evaluate_search_candidate,
)
from inputs_application.crack_evaluation import (
    _evaluate_crack_with_state_for_app_bridge,
    build_crack_evaluation_runtime,
)
from inputs_application.deflection_evaluation import (
    DeflectionEvaluationRuntime,
    _evaluate_deflection_with_state_for_app_bridge,
)
from inputs_application.fast_candidate_evaluator import (
    FastCandidateEvaluationRuntime,
    evaluate_candidate_fast,
)
from inputs_application.candidate_full_evaluation import (
    FullCandidateEvaluationRuntime,
    evaluate_candidate_full_for_app_bridge,
)
from inputs_application.legacy_design_brain_adapter import (
    build_full_candidate_evaluation_result_projection,
)
from inputs_application.recommendation_evaluation import (
    effective_bottom_design_state,
    evaluate_bending_with_bottom_state,
    evaluate_shear_with_state,
)
from inputs_application.recommendation_support import design_width_value
from inputs_application.state_utils import (
    float_from_state,
    state_with_resolved_design_actions,
    uls_action_from_state,
)
from inputs_page_modules.design_overview_adapter import (
    build_design_actions_context,
    collect_design_overview,
)
from inputs_page_modules.design_guide.candidate_keys import _candidate_cache_key
from inputs_page_modules.recommendation_eval_cache import (
    get_recommendation_eval_cache,
)
from state_and_helpers import (
    get_rerun_pure_cache,
    set_rerun_pure_cache,
    stable_fingerprint_for_payload,
    ux_probe_record,
)


def _candidate_overview_state(
    candidate_state: dict,
    bottom_updates: dict | None,
) -> dict:
    merged = dict(candidate_state or {})
    bottom = effective_bottom_design_state(candidate_state, bottom_updates)
    effective_depth = float(bottom.get("d_centroid", 0.0) or 0.0)
    if effective_depth > 0.0:
        merged["d"] = effective_depth
    bar_count = int(bottom.get("nb_bot", 0) or 0)
    diameter = float(bottom.get("db_bot", 0.0) or 0.0)
    if bar_count > 0 and diameter > 0.0:
        merged.update(
            Ast_bot=float(bottom.get("Ast_bot", 0.0) or 0.0),
            db_bot=diameter,
            nb_bot=bar_count,
        )
    return merged


def _phi_mu_capacity(bending: dict | None) -> float:
    return float((bending or {}).get("phi_Mu_cap", 0.0) or 0.0)


def _log_capacity_mismatch(
    *,
    pack_phi_knm: float,
    direct_phi_knm: float,
    session_state: Mapping[str, Any],
) -> None:
    tolerance = max(
        max(abs(pack_phi_knm), abs(direct_phi_knm), 1.0) * 0.02,
        0.5,
    )
    if (
        abs(pack_phi_knm - direct_phi_knm) > tolerance
        and bool(session_state.get("_dev_mode"))
    ):
        raise AssertionError(
            "AUTO DESIGN USING STALE CAPACITY: pack phiMu vs direct bending phi_Mu_cap"
        )


def evaluate_full_candidate(
    candidate_state: dict,
    *,
    session_state: Mapping[str, Any],
    source: str = "full_eval",
    label: str | None = None,
    action_type: str | None = None,
    updates: dict | None = None,
) -> dict | None:
    crack_runtime = build_crack_evaluation_runtime()
    deflection_runtime = DeflectionEvaluationRuntime(
        session_state=session_state,
        design_width=design_width_value,
        effective_bottom=effective_bottom_design_state,
        float_from_state=float_from_state,
        status_from_util=status_from_candidate_util,
    )
    return evaluate_candidate_full_for_app_bridge(
        candidate_state,
        source=source,
        label=label,
        action_type=action_type,
        updates=updates,
        runtime=FullCandidateEvaluationRuntime(
            session_state=session_state,
            stable_fingerprint=stable_fingerprint_for_payload,
            get_cache=get_rerun_pure_cache,
            set_cache=set_rerun_pure_cache,
            probe_record=ux_probe_record,
            build_projection=build_full_candidate_evaluation_result_projection,
            bottom_bar_count=bottom_bar_count,
            bottom_row_count=bottom_row_count,
            build_actions_context=build_design_actions_context,
            candidate_bottom_updates=candidate_bottom_updates,
            candidate_shear_updates=candidate_shear_updates,
            overview_state=_candidate_overview_state,
            collect_overview=lambda state, **kwargs: collect_design_overview(
                state,
                session_state=session_state,
                **kwargs,
            ),
            design_width=design_width_value,
            effective_bottom=effective_bottom_design_state,
            evaluate_bending=evaluate_bending_with_bottom_state,
            evaluate_crack=lambda state, **kwargs: _evaluate_crack_with_state_for_app_bridge(
                state,
                runtime=crack_runtime,
                **kwargs,
            ),
            evaluate_deflection=lambda state, **kwargs: _evaluate_deflection_with_state_for_app_bridge(
                state,
                runtime=deflection_runtime,
                **kwargs,
            ),
            evaluate_shear=evaluate_shear_with_state,
            float_from_state=float_from_state,
            int_from_state=int_from_state,
            log_capacity_mismatch=lambda **kwargs: _log_capacity_mismatch(
                session_state=session_state,
                **kwargs,
            ),
            phi_mu_capacity=_phi_mu_capacity,
            reo_congestion=reo_congestion_index,
            status_from_util=status_from_candidate_util,
        ),
    )


def evaluate_fast_candidate(
    candidate_state: dict,
    context: dict,
    *,
    session_state: Mapping[str, Any],
) -> dict | None:
    crack_runtime = build_crack_evaluation_runtime()
    deflection_runtime = DeflectionEvaluationRuntime(
        session_state=session_state,
        design_width=design_width_value,
        effective_bottom=effective_bottom_design_state,
        float_from_state=float_from_state,
        status_from_util=status_from_candidate_util,
    )
    return evaluate_candidate_fast(
        candidate_state,
        context,
        runtime=FastCandidateEvaluationRuntime(
            bottom_bar_count=bottom_bar_count,
            bottom_row_count=bottom_row_count,
            candidate_bottom_updates=candidate_bottom_updates,
            candidate_shear_updates=candidate_shear_updates,
            design_width=design_width_value,
            effective_bottom=effective_bottom_design_state,
            evaluate_bending=evaluate_bending_with_bottom_state,
            evaluate_crack=lambda state, **kwargs: _evaluate_crack_with_state_for_app_bridge(
                state,
                runtime=crack_runtime,
                **kwargs,
            ),
            evaluate_deflection=lambda state, **kwargs: _evaluate_deflection_with_state_for_app_bridge(
                state,
                runtime=deflection_runtime,
                **kwargs,
            ),
            evaluate_shear=evaluate_shear_with_state,
            float_from_state=float_from_state,
            int_from_state=int_from_state,
            reo_congestion=reo_congestion_index,
            resolve_actions=state_with_resolved_design_actions,
            status_from_util=status_from_candidate_util,
            uls_action=uls_action_from_state,
        ),
    )


def evaluate_recommendation_search_candidate(
    candidate_state: dict,
    *,
    seed_state: dict,
    context: dict,
    eval_cache: dict,
    metrics: dict,
    source: str,
    session_state: Mapping[str, Any],
    label: str | None = None,
    action_type: str | None = None,
) -> dict | None:
    return evaluate_search_candidate(
        candidate_state,
        seed_state=seed_state,
        context=context,
        eval_cache=eval_cache,
        metrics=metrics,
        source=source,
        label=label,
        action_type=action_type,
        runtime=CandidateSearchEvaluationRuntime(
            evaluate_fast=lambda state, current_context: evaluate_fast_candidate(
                state,
                current_context,
                session_state=session_state,
            ),
            candidate_key=_candidate_cache_key,
            get_global_cache=lambda: get_recommendation_eval_cache(
                session_state,
                enabled=False,
            ),
            global_cache_enabled=False,
            max_total_unique_evals=100,
            compute_reo_complexity=compute_reo_complexity,
            state_to_shared_updates=candidate_state_to_shared_updates,
            design_width=design_width_value,
            float_from_state=float_from_state,
            effective_bottom=effective_bottom_design_state,
        ),
    )


__all__ = [
    "evaluate_fast_candidate",
    "evaluate_full_candidate",
    "evaluate_recommendation_search_candidate",
]
