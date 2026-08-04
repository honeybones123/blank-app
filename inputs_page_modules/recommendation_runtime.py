"""Permanent page-level assembly for typed recommendation runtimes."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

from inputs_application.geometry_candidate_ranking import rank_geometry_candidates
from inputs_application.geometry_recommendation import (
    GeometryCandidateRuntime,
    compute_geometry_recommendation,
)
from inputs_application.shear_truth_policy import (
    combined_underdesign_shear_truth_gate,
)
from inputs_application.auto_design_scoring_runtime import (
    build_auto_design_scoring_runtime,
)
from inputs_application.bottom_compound_runtime import (
    build_bottom_compound_runtime,
)
from inputs_application.bottom_selector_runtime import (
    build_bottom_selector_runtime,
)
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import float_from_state
from inputs_page_modules.recommendation_candidate_adapter import (
    evaluate_full_candidate,
    evaluate_recommendation_search_candidate,
)
from inputs_page_modules.design_overview_adapter import (
    build_design_actions_context,
    collect_design_overview,
)
from inputs_page_modules.recommendation_compute import (
    BottomRecommendationRuntime,
    RecommendationEvaluationRuntime,
    RecommendationTraceRuntime,
    ShearRecommendationRuntime,
    compute_bottom_reo_recommendation,
    compute_shear_recommendation,
)


_AGENT_DEBUG_LOG_PATH = "/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents/GitHub/complete-app/.cursor/debug.log"


def _agent_debug_log(
    message: str,
    data: dict | None = None,
    *,
    location: str,
    hypothesis_id: str,
    run_id: str = "auto_design_debug",
) -> None:
    try:
        timestamp = int(datetime.now().timestamp() * 1000)
        payload = {
            "id": f"log_{timestamp}_{hypothesis_id}",
            "timestamp": timestamp,
            "location": location,
            "message": message,
            "data": data or {},
            "runId": run_id,
            "hypothesisId": hypothesis_id,
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def build_recommendation_trace_runtime(
    *,
    session_state: Mapping[str, Any],
) -> RecommendationTraceRuntime:
    active_recommendation_trace = None
    active_rank_trace = None

    def append_recommendation_trace(entry: dict) -> None:
        if active_recommendation_trace is not None:
            active_recommendation_trace.append(dict(entry))

    def merge_rank_trace(entry: dict) -> None:
        if entry and active_rank_trace is not None:
            active_rank_trace.append(dict(entry))

    def log_candidate_rank(
        *,
        domain: str,
        event: str,
        candidate: dict | None,
        reason: str,
        util_before: float | None = None,
        util_after: float | None = None,
    ) -> None:
        payload = {
            "domain": domain,
            "event": event,
            "reason": reason,
            "candidate_label": (
                None if candidate is None else str(candidate.get("label") or "")
            ),
            "candidate_source": (
                None if candidate is None else str(candidate.get("source") or "")
            ),
            "candidate_type": (
                None
                if candidate is None
                else str(
                    candidate.get("shear_candidate_type")
                    or candidate.get("shear_ladder_branch")
                    or candidate.get("recommendation_geometry_trial")
                    or ""
                )
            ),
            "branch": (
                None
                if candidate is None
                else str(candidate.get("shear_ladder_branch") or "")
            ),
            "updates": (
                None
                if candidate is None
                else dict(candidate.get("updates") or {})
            ),
            "score": None if candidate is None else candidate.get("score"),
            "util_before": util_before,
            "util_after": util_after,
            "candidate_post_util": (
                None
                if candidate is None
                else candidate.get("candidate_post_util")
            ),
            "candidate_reaches_target_band": (
                None
                if candidate is None
                else candidate.get("candidate_reaches_target_band")
            ),
            "candidate_distance_to_target_band": (
                None
                if candidate is None
                else candidate.get("candidate_distance_to_target_band")
            ),
        }
        _agent_debug_log(
            "Design recommendation ranking",
            payload,
            location="inputs_page.py:_log_design_reco_candidate_rank",
            hypothesis_id="H_DESIGN_RECO_RANK",
        )
        append_recommendation_trace(payload)

    def log_efficiency_growth_rejection(
        *,
        candidate_family: str,
        seed_candidate: dict,
        candidate: dict | None,
        extra: dict | None = None,
    ) -> None:
        deltas = {}
        if candidate and seed_candidate:
            seed_state = dict(seed_candidate.get("state") or {})
            candidate_state = dict(candidate.get("state") or {})
            seed_depth = float(
                seed_candidate.get(
                    "depth",
                    float_from_state(seed_state, "D", 0.0),
                )
                or float_from_state(seed_state, "D", 0.0)
            )
            candidate_depth = float(
                candidate.get(
                    "depth",
                    float_from_state(candidate_state, "D", 0.0),
                )
                or float_from_state(candidate_state, "D", 0.0)
            )
            seed_width = float(resolve_geometry_width_context(seed_state)[2])
            candidate_width = float(
                candidate.get(
                    "width",
                    resolve_geometry_width_context(candidate_state)[2],
                )
                or resolve_geometry_width_context(candidate_state)[2]
            )
            seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
            candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
            seed_diameter = int(float(seed_state.get("lig_d", 0) or 0))
            seed_legs = int(float(seed_state.get("lig_legs", 0) or 0))
            candidate_diameter = int(
                float(candidate_state.get("lig_d", 0) or 0)
            )
            candidate_legs = int(
                float(candidate_state.get("lig_legs", 0) or 0)
            )
            deltas = {
                "delta_D_mm": round(candidate_depth - seed_depth, 3),
                "delta_b_mm": round(candidate_width - seed_width, 3),
                "delta_Ast_bot": round(candidate_ast - seed_ast, 3),
                "removed_shear_links": bool(
                    (seed_diameter > 0 or seed_legs >= 2)
                    and candidate_diameter <= 0
                    and candidate_legs < 2
                ),
            }
        payload = {
            "event": "rejected",
            "candidate_family": candidate_family,
            "reason": "growth_move_blocked_in_efficiency_mode",
            **deltas,
        }
        if extra:
            payload.update(extra)
        merge_rank_trace({"efficiency_growth_rejection": dict(payload)})

    return RecommendationTraceRuntime(
        agent_debug_log=_agent_debug_log,
        active_recommendation_trace=active_recommendation_trace,
        append_recommendation_trace=append_recommendation_trace,
        candidate_debug_enabled=bool(session_state.get("_dev_mode")),
        log_candidate_rank=log_candidate_rank,
        log_efficiency_growth_rejection=log_efficiency_growth_rejection,
        merge_rank_trace=merge_rank_trace,
    )


def compute_geometry_recommendation_for_page(
    state: dict,
    *,
    session_state: Mapping[str, Any],
) -> dict | None:
    return compute_geometry_recommendation(
        state,
        runtime=GeometryCandidateRuntime(
            evaluate_full=lambda candidate_state, **kwargs: evaluate_full_candidate(
                candidate_state,
                session_state=session_state,
                **kwargs,
            ),
            evaluate_fast=lambda candidate_state, **kwargs: evaluate_recommendation_search_candidate(
                candidate_state,
                session_state=session_state,
                **kwargs,
            ),
            rank=rank_geometry_candidates,
            max_stage_candidates=20,
        ),
    )


def compute_shear_recommendation_for_page(
    state: dict,
    *,
    session_state: Mapping[str, Any],
) -> dict | None:
    trace = build_recommendation_trace_runtime(session_state=session_state)
    return compute_shear_recommendation(
        ShearRecommendationRuntime(
            trace=trace,
            evaluation=build_recommendation_evaluation_runtime(
                session_state=session_state,
            ),
            scoring=build_auto_design_scoring_runtime(
                agent_debug_log=trace.agent_debug_log,
            ),
        ),
        state,
    )


def compute_bottom_recommendation_for_page(
    state: dict,
    *,
    session_state: Mapping[str, Any],
) -> dict | None:
    trace = build_recommendation_trace_runtime(session_state=session_state)
    evaluation = build_recommendation_evaluation_runtime(
        session_state=session_state,
    )
    scoring = build_auto_design_scoring_runtime(
        agent_debug_log=trace.agent_debug_log,
    )
    return compute_bottom_reo_recommendation(
        BottomRecommendationRuntime(
            trace=trace,
            compound=build_bottom_compound_runtime(
                evaluate_candidate_fast=evaluation.evaluate_candidate_fast,
            ),
            evaluation=evaluation,
            scoring=scoring,
            selector=build_bottom_selector_runtime(
                scoring=scoring,
                trace=trace,
            ),
        ),
        state,
    )


def build_recommendation_actions_context(state: dict) -> dict:
    return build_design_actions_context(state)


def build_recommendation_evaluation_runtime(
    *,
    session_state: Mapping[str, Any],
) -> RecommendationEvaluationRuntime:
    return RecommendationEvaluationRuntime(
        build_design_actions_context=build_recommendation_actions_context,
        collect_design_overview=lambda state, context=None: collect_recommendation_overview(
            state,
            context=context,
            session_state=session_state,
        ),
        combined_shear_truth_gate=lambda state, **kwargs: combined_underdesign_shear_truth_gate(
            state,
            session_state=session_state,
            **kwargs,
        ),
        evaluate_candidate_fast=lambda candidate_state, **kwargs: evaluate_recommendation_candidate_fast(
            candidate_state,
            session_state=session_state,
            **kwargs,
        ),
        evaluate_candidate_full=lambda candidate_state, **kwargs: evaluate_recommendation_candidate_full(
            candidate_state,
            session_state=session_state,
            **kwargs,
        ),
    )


def collect_recommendation_overview(
    state: dict,
    context: dict | None = None,
    *,
    session_state: Mapping[str, Any],
) -> dict:
    return collect_design_overview(
        state,
        context=context,
        session_state=session_state,
    )


def evaluate_recommendation_candidate_full(
    candidate_state: dict,
    *,
    session_state: Mapping[str, Any],
    **kwargs: Any,
) -> dict | None:
    return evaluate_full_candidate(
        candidate_state,
        session_state=session_state,
        **kwargs,
    )


def evaluate_recommendation_candidate_fast(
    candidate_state: dict,
    *,
    session_state: Mapping[str, Any],
    **kwargs: Any,
) -> dict | None:
    return evaluate_recommendation_search_candidate(
        candidate_state,
        session_state=session_state,
        **kwargs,
    )


__all__ = [
    "build_recommendation_actions_context",
    "build_recommendation_evaluation_runtime",
    "build_recommendation_trace_runtime",
    "collect_recommendation_overview",
    "compute_bottom_recommendation_for_page",
    "compute_geometry_recommendation_for_page",
    "compute_shear_recommendation_for_page",
    "evaluate_recommendation_candidate_fast",
    "evaluate_recommendation_candidate_full",
]
