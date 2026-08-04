"""Design Guide guidance-compute coordinators for the Inputs page.

These functions preserve the Inputs page compute behaviour behind a typed
application boundary while legacy helper dependencies are progressively
replaced by permanent application owners.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from functools import partial
import json
import math
import re
from typing import Any, Callable

from application.candidate_delta_policy import diff_candidate_state_updates
from inputs_application.legacy_design_brain_adapter import (
    project_active_fail_executor_evaluated_candidate_result,
    resolve_active_fail_executor_candidate_eval_source,
)
from inputs_application.legacy_design_brain_adapter import (
    build_design_guide_controller_active_fail_executor_ladder_eval_commands,
    build_design_guide_controller_active_fail_executor_ladder_candidate_meta,
    resolve_design_guide_controller_active_fail_executor_ladder_stop_decision,
    resolve_design_guide_controller_optimisation_candidate_family,
)
from inputs_application.legacy_design_brain_adapter import run_geometry_detailing_governs_runtime, family_strategy_for
from application.contracts.design_policy import DESIGN_OPTIMISATION_GOAL_LABELS
from inputs_application.candidate_metrics import bottom_bar_count as _bottom_bar_count_owned, bottom_row_count as _bottom_row_count_owned, candidate_bottom_updates as _candidate_bottom_updates_owned, compute_reo_complexity as _compute_reo_complexity_owned, int_from_state as _int_from_state_owned, reo_congestion_index as _reo_congestion_index_owned, status_from_candidate_util
from inputs_application.crack_evaluation import _evaluate_crack_with_state_for_app_bridge as _evaluate_crack_with_state_owned, build_crack_evaluation_runtime
from inputs_application.deflection_evaluation import DeflectionEvaluationRuntime, _evaluate_deflection_with_state as _evaluate_deflection_with_state_owned
from inputs_application.auto_design_scoring_runtime import build_auto_design_scoring_runtime
from inputs_application.bottom_compound_runtime import arrangement_fits_state
from inputs_application.auto_design_candidate_selector_runtime import build_auto_design_candidate_selector_runtime
from inputs_application.auto_design_final_selection import AutoDesignFinalSelectionRuntime, select_best_next_hop_candidate as select_best_next_hop_candidate_owned, select_final_candidate as select_final_candidate_owned
from inputs_application.auto_design_progressive_runtime import ProgressiveAutoDesignRuntime, build_progressive_candidate, evaluate_progressive_candidate_update, run_progressive_auto_design_step
from inputs_application.geometry_search_policy import build_auto_design_context as _build_auto_design_context_owned, design_mode_config as _design_mode_config_owned, design_optimisation_goal as _design_optimisation_goal_owned, generate_balanced_geometry_options, generate_same_or_larger_geometry_options, generate_slightly_deeper_depths, geometry_lock_enabled as _geometry_lock_enabled_owned, geometry_state_with_updates as _geometry_state_with_updates_owned, geometry_tightening_trial_updates, rescue_geometry_width_for_depth_ratio, resolved_efficiency_target_band as _resolved_efficiency_target_band
from inputs_application.in_band_override_policy import InBandOverridePolicy, should_override_target_band_done_state
from inputs_application.engineering_predicates import parse_util_value as _parse_util_value, shear_demands_negligible as _shear_demands_negligible, shear_reinforcement_is_active as _shear_reinforcement_is_active
from inputs_application.efficiency_classification import identify_materially_overprovided_non_governing_families
from inputs_application.family_ladder_live_evaluators import (
    build_bending_fail_shear_overdesign_live_evaluator,
    build_bending_overdesign_live_evaluator,
    build_combined_overdesign_live_evaluator,
    build_serviceability_live_evaluator,
    build_shear_fail_bending_overdesign_live_evaluator,
    build_shear_overdesign_live_evaluator,
    serviceability_updates_to_app_updates,
)
from inputs_application.recommendation_envelope import attach_recommendation_envelope
from inputs_application.recommendation_evaluation import effective_bottom_design_state as _effective_bottom_design_state_owned, evaluate_shear_with_state as _evaluate_shear_with_state_owned, shear_no_links_candidate_passes_code, shear_state_eligible_for_no_links, try_shear_no_demand_cleanup_recommendation as _try_shear_no_demand_cleanup_recommendation_owned
from inputs_application.recommendation_primitives import bottom_arrangement_to_shared_updates as _bottom_arrangement_to_shared_updates_owned, candidate_is_growth_move as _candidate_is_growth_move_owned, efficiency_reduction_profile as _efficiency_reduction_profile_owned, invalid_shear_spacing_change_without_activation as _invalid_shear_spacing_change_without_activation_owned, practical_bottom_reo_label as _practical_bottom_reo_label_owned, shear_candidate_type as _shear_candidate_type_owned, shear_change_is_reinforcement_growth as _shear_change_is_reinforcement_growth_owned, shear_change_is_relevant as _shear_change_is_relevant_owned, shear_detailing_updates_pure as _shear_detailing_updates_pure_owned, shear_spacing_layout_must_not_trigger_strengthening
from inputs_application.recommendation_support import design_width_value as _design_width_value_owned, resolve_geometry_width_context as _resolve_geometry_width_context_owned
from inputs_application.recommendation_target_band import annotate_candidate_target_band_metrics as _annotate_candidate_target_band_metrics
from inputs_application.shear_state_normalization import normalize_invalid_shear_state_updates
from inputs_application.state_utils import bottom_reo_state_label as _bottom_reo_state_label_owned, float_from_state as _float_from_state_owned, guidance_state_snapshot as _guidance_state_snapshot_owned, shear_state_label as _shear_state_label_owned, state_with_resolved_design_actions as _state_with_resolved_design_actions_owned, updates_match_state as _updates_match_state
from inputs_application.summary_state_runtime import (
    InputsSummaryStateRuntime,
    resolve_design_guide_lightweight_state,
)
from inputs_application.shear_truth_policy import (
    combined_underdesign_shear_truth_gate,
    overlay_current_normalized_shear_truth,
)
from inputs_application.policy_constants import EFFICIENCY_TARGET_UTIL_MAX, EFFICIENCY_TARGET_UTIL_MIN, FINAL_ACCEPTED_MIN_FAMILY_UTIL, GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN, TARGET_BAND_EPS


_GUIDANCE_COMPUTE_SESSION_STATE: Any | None = None
_LAST_GUIDANCE_COMPUTE_RUNTIME: Any | None = None
_EFFICIENCY_TIGHTENING_STATE_RUNTIME: EfficiencyTighteningStateRuntime | None = None
from inputs_page_modules.app_bridge.canonical_design_state_pack import CanonicalDesignStatePackRuntime, _build_canonical_design_state_pack_for_app_bridge as _build_canonical_pack_owned
from inputs_page_modules.app_bridge.auto_design_solver import AutoDesignSolverRuntime, _solve_reo_for_geometry as _solve_reo_for_geometry_owned, run_auto_design_solver as run_auto_design_solver_owned, run_full_auto_design as run_full_auto_design_owned
from inputs_page_modules.app_bridge.actionable_guidance_candidates import CandidateActionabilityRuntime, _candidate_is_materially_actionable as _candidate_is_materially_actionable_owned
from inputs_page_modules.app_bridge.post_commit_audit import AcceptedGreenAuditRuntime, _post_click_accepted_green_audit as _post_click_accepted_green_audit_owned
from inputs_page_modules.app_bridge.top_candidate_keeper import TopCandidateKeeperRuntime, _keep_top_candidates as _keep_top_candidates_owned
from inputs_page_modules.design_guide import _COMPOUND_BOTTOM_UPDATE_KEYS, _COMPOUND_GEOMETRY_UPDATE_KEYS, _COMPOUND_SHEAR_UPDATE_KEYS, _candidate_cache_key, _canonical_pack_is_valid, _coherence_debug_fields, _design_state_coherence_check, _guidance_item_source_candidate_id
from inputs_page_modules.design_guide.actionable_target_band_winner import ActionableTargetBandWinnerRuntime, _get_actionable_target_band_winner as _get_actionable_target_band_winner_owned
from inputs_page_modules.design_guide.auto_design_scoring import _candidate_sort_key_for_mode as _candidate_sort_key_for_mode_owned, _score_auto_design_candidate_components as _score_auto_design_candidate_components_owned, candidate_materially_worsens as candidate_materially_worsens_owned
from inputs_page_modules.design_guide.auto_design_candidate_selector import _select_best_auto_design_candidate as _select_best_auto_design_candidate_owned
from inputs_page_modules.design_guide.fingerprint import DESIGN_GUIDE_ALGORITHM_VERSION
from inputs_page_modules.design_guide.candidate_search_evidence import _align_guidance_items_to_candidate_search_evidence, _build_candidate_search_evidence
from inputs_page_modules.design_guide.candidate_keys import _make_auto_design_candidate_key
from inputs_page_modules.design_guide.crack_guidance import CrackGuidanceRuntime, CrackLadderRuntime, _crack_guidance_item as _crack_guidance_item_owned, _pick_crack_ladder_first_improvement as _pick_crack_ladder_first_improvement_owned
from inputs_page_modules.design_guide.compound_strengthening import CompoundGuidanceRuntime, _try_compound_efficiency_guidance_item as _try_compound_efficiency_guidance_item_owned, _try_compound_strengthening_guidance_item as _try_compound_strengthening_guidance_item_owned
from inputs_page_modules.design_guide.compound_guidance_copy import CompoundGuidanceCopyRuntime, _compound_guidance_title_reasoning_why as _compound_guidance_title_reasoning_why_owned
from inputs_page_modules.design_guide.button_contract import _design_guide_button_contract as _design_guide_button_contract_owned
from inputs_page_modules.design_guide.bending_guidance import BendingGeometryTrialRuntime, BendingGuidanceRuntime, _bending_item_from_geometry_trial as _bending_item_from_geometry_trial_owned, _bending_guidance_item as _bending_guidance_item_owned
from inputs_page_modules.design_guide.display_truth import _design_guide_apply_display_truth_to_items
from inputs_page_modules.design_guide.deflection_guidance import DeflectionGuidanceRuntime, deflection_guidance_item
from inputs_application.legacy_design_brain_adapter import FamilyLadderGuidanceRuntime, _family_ladder_guidance_item as _family_ladder_guidance_item_owned
from inputs_page_modules.design_guide.executor_contract_sanitizer import ExecutorContractSanitizerRuntime, _sanitize_guidance_items_for_executor_contract as _sanitize_guidance_items_for_executor_contract_owned
from inputs_page_modules.design_guide.efficiency_guidance_items import EfficiencyGuidanceRuntime, _efficiency_guidance_items as _efficiency_guidance_items_owned
from inputs_page_modules.design_guide.efficiency_executor_promotion import EfficiencyExecutorPromotionRuntime, _try_promote_efficiency_item_to_executor_backed_candidate as _try_promote_efficiency_item_owned
from inputs_page_modules.design_guide.efficiency_tightening_state import EfficiencyTighteningStateRuntime, compute_efficiency_tightening_state as compute_efficiency_tightening_state_owned
from inputs_page_modules.design_guide.guidance_items import (
    _auto_design_solver_recommendation_as_guidance_item,
    _guidance_item,
    _guidance_item_is_resolved_one_click,
    _guidance_not_started,
    _guidance_start_item,
    _optimal_guidance_item,
    _passing_guidance_item,
    _very_low_demand_guidance_item,
)
from inputs_page_modules.design_guide.guidance_item_consolidation import _collapse_to_single_primary_guidance_item
from inputs_page_modules.design_guide.guidance_item_dedupe import _dedupe_guidance_items_for_display as _dedupe_guidance_items_for_display_owned
from inputs_page_modules.design_guide.guidance_item_dedupe import _family_tag_from_compound_updates as _family_tag_from_compound_updates_owned
from inputs_page_modules.design_guide.geometry_trial_selector import GeometryTrialSelectorRuntime, _choose_geometry_trial_for_metric as _choose_geometry_trial_for_metric_owned
from inputs_page_modules.design_guide.local_cleanup_promotion import LocalCleanupPromotionRuntime, _maybe_promote_safe_local_cleanup_primary as _maybe_promote_safe_local_cleanup_primary_owned
from inputs_page_modules.design_guide.local_cleanup_guidance_evaluator import LocalCleanupGuidanceEvaluatorRuntime, _evaluate_local_cleanup_guidance_item as _evaluate_local_cleanup_guidance_item_owned
from inputs_page_modules.design_guide.guidance_copy_model import apply_guidance_copy_model_to_item
from inputs_page_modules.design_guide.one_click_band_candidate import OneClickBandCandidateRuntime, _get_one_click_band_reaching_candidate as _get_one_click_band_reaching_candidate_owned
from inputs_page_modules.design_guide.primary_one_click_validation import _candidate_is_valid_primary_one_click
from inputs_page_modules.design_guide.preview_contract import PreviewContractRuntime, _design_guide_preview_contract_for_updates as _design_guide_preview_contract_for_updates_owned
from inputs_page_modules.design_guide.primary_optimisation_selector import PrimaryOptimisationSelectorRuntime, _select_primary_optimisation_candidate as _select_primary_optimisation_candidate_owned
from inputs_page_modules.design_guide.resolved_candidate_guidance_item import ResolvedCandidateGuidanceRuntime, _ensure_guidance_item_resolved_candidate_payload as _ensure_guidance_item_resolved_candidate_payload_owned, _guidance_item_from_resolved_candidate as _guidance_item_from_resolved_candidate_owned, _promote_guidance_item_to_resolved_candidate as _promote_guidance_item_to_resolved_candidate_owned
from inputs_page_modules.design_guide.shear_guidance import ShearGuidanceRuntime, _shear_guidance_item as _shear_guidance_item_owned
from inputs_page_modules.design_guide.shear_tightening import ShearTighteningRuntime, _compute_shear_tightening_recommendation as _compute_shear_tightening_recommendation_owned
from inputs_page_modules.design_guide.shear_local_cleanup import ShearLocalCleanupRuntime, _shear_tightening_as_local_cleanup_item as _shear_tightening_as_local_cleanup_item_owned
from inputs_page_modules.design_guide.shear_low_util_active_links_blocker import ShearLowUtilBlockerRuntime, _shear_low_util_active_links_exact_blocker as _shear_low_util_active_links_exact_blocker_owned
from inputs_page_modules.design_guide.severe_shear_escalation_log import _log_severe_shear_escalation as _log_severe_shear_escalation_owned
from inputs_page_modules.design_guide.shear_congestion_reshape import ShearCongestionReshapeRuntime, _in_target_shear_congestion_reshape_guidance_item as _in_target_shear_congestion_reshape_guidance_item_owned
from inputs_page_modules.design_guide.recommendation_result_builder import _build_recommendation_result_from_guidance_item
from inputs_page_modules.design_guide.terminal_state import (
    _derive_design_guide_terminal_state_from_current_overview,
    _design_guide_terminal_state_from_render_artifacts,
)
from inputs_page_modules.design_guide.update_families import _compound_subfamilies_from_updates
from inputs_application.local_cleanup_acceptance import LocalCleanupAcceptanceRuntime, build_local_cleanup_acceptance_fingerprint, local_cleanup_post_apply_acceptance_matches as _local_cleanup_acceptance_matches_owned, local_cleanup_post_apply_acceptance_matches_with_runtime as _local_cleanup_acceptance_matches_with_runtime_owned
from inputs_page_modules.design_overview_adapter import build_design_actions_context as _build_design_actions_context_owned, collect_design_overview as _collect_design_overview_owned
from inputs_page_modules.recommendation_candidate_adapter import evaluate_fast_candidate as _evaluate_fast_candidate_owned, evaluate_full_candidate as _evaluate_full_candidate_owned, evaluate_recommendation_search_candidate
from inputs_page_modules.recommendation_compute import _generate_local_bottom_arrangements as _generate_local_bottom_arrangements_owned
from inputs_application.recommendation_evaluation import evaluate_bending_with_bottom_state
from inputs_application.primary_auto_design import PrimaryAutoDesignRuntime, run_primary_auto_design as run_primary_auto_design_owned
from inputs_application.secondary_bending_tightening import generate_secondary_bending_tightening_states
from inputs_application.recommendation_support import severe_shear_failure, shear_severity_band
from inputs_application.state_utils import updates_match_state
from inputs_page_modules.recommendation_runtime import compute_bottom_recommendation_for_page, compute_geometry_recommendation_for_page, compute_shear_recommendation_for_page
from inputs_application.local_cleanup_acceptance import DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS as _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
from shear_checks_helpers import build_shear_check_rows_from_state
from state_and_helpers import BEAM_STATUS_FAIL, SHARED_DEFAULTS, get_rerun_pure_cache, set_rerun_pure_cache, speed_profile_record, stable_fingerprint_for_payload, ux_probe_record
from widgets_helpers import main_longitudinal_reo_change_line_prefixes


_ACTIVE_GUIDANCE_RANK_TRACE: list[dict] | None = None
_ACTIVE_GUIDANCE_RECO_TRACE: list[dict] | None = None
CANONICAL_NO_SHEAR_SLIG_MM = 200.0
GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD = 0.95
_VAGUE_CANONICAL_TITLE_LABELS = frozenset(
    {
        "apply recommendation",
        "apply one-click design",
        "apply one-click recommendation",
        "optimisation available",
        "optimization available",
    }
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


def _guidance_action_to_payload_name(action_type: str) -> str | None:
    mapping = {
        "apply_mode_recommendation": "mode_tightening",
        "apply_bottom_recommendation": "bottom_tightening",
        "apply_geometry_recommendation": "geometry_tightening",
        "apply_shear_recommendation": "shear_tightening",
        "reduce_bottom_reinforcement": "bottom_tightening",
        "reduce_bar_spacing": "bottom_tightening",
        "tighten_geometry": "geometry_tightening",
        "increase_depth": "geometry_tightening",
        "increase_width": "geometry_tightening",
        "reduce_link_spacing": "shear_tightening",
        "increase_link_spacing": "shear_tightening",
        "reduce_number_of_legs": "shear_tightening",
        "deflection_reduce_sustained_load": "general",
    }
    return mapping.get(str(action_type or ""))


def _log_guidance_branch_governing_mismatch(
    *,
    guidance_branch: str,
    governing_action: str,
    primary_utils: dict[str, float | None],
    selected_item: dict | None,
) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    branch_name = str(guidance_branch or "")
    branch_action = branch_name
    for prefix in ("critical_", "efficiency_", "passing_guidance_"):
        if branch_name.startswith(prefix):
            branch_action = branch_name[len(prefix) :]
            break
    is_shear_branch = (
        "shear" in branch_name
        or _guidance_action_to_payload_name(branch_action) == "shear_tightening"
        or str((selected_item or {}).get("check_key") or "") == "shear"
    )
    if not is_shear_branch:
        return
    bending_util = primary_utils.get("bending")
    shear_util = primary_utils.get("shear")
    if bending_util is None or shear_util is None:
        return
    if float(shear_util) >= float(bending_util):
        return
    _agent_debug_log(
        "Shear branch selected while bending util exceeds shear util",
        {
            "guidance_branch": guidance_branch,
            "governing_action": governing_action,
            "bending_util": bending_util,
            "shear_util": shear_util,
            "selected_action_type": (
                None if not selected_item else selected_item.get("action_type")
            ),
            "selected_title": (
                None if not selected_item else selected_item.get("title_main")
            ),
        },
        location="inputs_page.py:_compute_design_guidance_items",
        hypothesis_id="H_GUIDANCE_GOVERNING",
    )


def _design_guide_debug_has_coherent_overview(value: dict | None) -> bool:
    if not isinstance(value, dict):
        return False
    overview = value.get("overview")
    return isinstance(overview, dict) and len(overview) > 0 and (
        "worst_util" in overview or "all_key_pass" in overview
    )


def _design_guide_debug_has_efficiency_state(value: dict | None) -> bool:
    if not isinstance(value, dict):
        return False
    efficiency_state = value.get("efficiency_tightening_state")
    return isinstance(efficiency_state, dict) and "classification" in efficiency_state


def _ensure_design_guide_debug_trace_coherent(
    *,
    state: dict,
    guidance_items: list[dict],
    debug_trace: dict | None,
) -> tuple[dict, list[str]]:
    out = dict(debug_trace or {})
    repairs: list[str] = []
    design_context = _build_design_actions_context(dict(state or {}))
    guidance_state_raw = out.get("guidance_resolved_state")
    if not isinstance(guidance_state_raw, dict):
        guidance_state = dict(
            design_context.get("state")
            or _guidance_state_snapshot(dict(state or {}))
        )
        out["guidance_resolved_state"] = guidance_state
        repairs.append("guidance_resolved_state")
    else:
        guidance_state = dict(guidance_state_raw)
    if not _design_guide_debug_has_coherent_overview(out):
        out["overview"] = _collect_design_overview(
            guidance_state,
            context=design_context,
        )
        repairs.append("overview")
    if not _design_guide_debug_has_efficiency_state(out):
        out["efficiency_tightening_state"] = compute_efficiency_tightening_state(
            guidance_state,
            context=design_context,
        )
        repairs.append("efficiency_tightening_state")
    guidance_branch = str(out.get("guidance_branch") or "").strip()
    if not guidance_branch:
        efficiency_state = out.get("efficiency_tightening_state") or {}
        if str(efficiency_state.get("classification") or "") == "optimal":
            out["guidance_branch"] = "optimal"
        elif str(efficiency_state.get("classification") or "") == "very_low_demand":
            out["guidance_branch"] = "very_low_demand"
        elif (
            guidance_items
            and str(
                (guidance_items[0] or {}).get("design_guide_terminal_state") or ""
            ).strip()
            == "optimal"
        ):
            out["guidance_branch"] = "optimal"
        elif (
            guidance_items
            and str(
                (guidance_items[0] or {}).get("design_guide_terminal_state") or ""
            ).strip()
            == "very_low_demand"
        ):
            out["guidance_branch"] = "very_low_demand"
        else:
            out["guidance_branch"] = "coherence_backfill"
        repairs.append("guidance_branch")
    return out, repairs


@dataclass(frozen=True)
class ModeGuidanceRuntime:
    candidate_debug_summary: Callable[..., Any]
    candidate_objective_util: Callable[..., Any]
    materialize_full_evaluated_candidate: Callable[..., Any]
    mode_guidance_focus_from_updates: Callable[..., Any]
    recommendation_search_allowed: Callable[..., Any]
    run_full_auto_design: Callable[..., Any]


@dataclass(frozen=True)
class GuidanceActionUpdateRuntime:
    reo_counts: tuple[int, ...]
    reo_spacings: tuple[float, ...]
    bottom_arrangement_to_shared_updates: Callable[..., Any]
    compute_bottom_recommendation: Callable[..., Any]
    compute_bottom_tightening: Callable[..., Any]
    compute_geometry_recommendation: Callable[..., Any]
    compute_geometry_tightening: Callable[..., Any]
    compute_shear_recommendation: Callable[..., Any]
    compute_shear_tightening: Callable[..., Any]
    resolve_generated_updates: Callable[..., Any]
    resolve_payload_updates: Callable[..., Any]
    shared_state_snapshot: Callable[..., Any]


@dataclass(frozen=True)
class BottomTighteningRuntime:
    evaluate_full: Callable[..., dict | None]
    evaluate_search: Callable[..., dict | None]


@dataclass(frozen=True)
class GeometryTighteningRuntime:
    candidate_in_target_band: Callable[[dict, dict], bool]
    evaluate_full: Callable[..., dict | None]
    evaluate_search: Callable[..., dict | None]
    score_candidate: Callable[[dict, dict, dict], float]


@dataclass(frozen=True)
class ServiceabilityLadderRuntime:
    geometry_trial_deltas_mm: tuple[float, ...]
    early_stop_util: float
    debug_enabled: bool
    describe_step: Callable[..., str]
    evaluate_deflection: Callable[..., dict | None]
    resolve_action_updates: Callable[..., dict | None]


def _mode_candidate_bending_demand_util(candidate: dict) -> float | None:
    overview = candidate.get("overview") or {}
    bending_pack = (overview.get("packs") or {}).get("bending") or {}
    capacity = float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    demand = float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    return None if capacity <= 1e-9 else demand / capacity


def _mode_candidate_ductility_util(candidate: dict) -> float | None:
    try:
        value = float(
            dict(candidate.get("bending_components") or {}).get(
                "ductility_util"
            )
        )
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def _mode_candidate_objective_util(candidate: dict) -> float:
    state = candidate.get("state") if isinstance(candidate, dict) else {}
    goal = _design_optimisation_goal(
        state if isinstance(state, dict) else {}
    )
    utils = (
        candidate.get("overview", {}).get("utils", {})
        if isinstance(candidate, dict)
        else {}
    )
    target_domain = str(
        (
            candidate.get("target_domain_for_band")
            if isinstance(candidate, dict)
            else ""
        )
        or ""
    ).strip().lower()
    bending_util = (
        _mode_candidate_bending_demand_util(candidate)
        if isinstance(candidate, dict)
        else None
    )
    objective_values = (
        [utils.get("shear")]
        if target_domain == "shear" or goal == "less_shear_reinforcement"
        else [bending_util, utils.get("shear")]
    )
    resolved_values: list[float] = []
    for value in objective_values:
        if value is None:
            continue
        try:
            resolved = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isnan(resolved):
            resolved_values.append(resolved)
    if resolved_values:
        return max(resolved_values)
    return float(candidate.get("worst_util", 0.0) or 0.0)


def _mode_candidate_debug_summary(candidate: dict | None) -> dict | None:
    if not candidate:
        return None
    candidate_state = dict(candidate.get("state") or {})
    overview = dict(candidate.get("overview") or {})
    bending_pack = ((overview.get("packs") or {}).get("bending") or {})
    ductility_util = _mode_candidate_ductility_util(candidate)
    capacity = float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    demand = float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    summary = {
        "label": str(candidate.get("label") or ""),
        "bottom_reo_label": (
            _bottom_reo_state_label(candidate_state) if candidate_state else ""
        ),
        "b": float(
            _resolve_geometry_width_context_owned(candidate_state)[2]
            if candidate_state
            else 0.0
        ),
        "D": float(
            candidate.get(
                "depth",
                _float_from_state_owned(candidate_state, "D", 0.0),
            )
            if candidate_state
            else 0.0
        ),
        "bot1_count": int(candidate_state.get("bot1_count", 0) or 0),
        "bot2_count": int(candidate_state.get("bot2_count", 0) or 0),
        "db_bot_1": int(
            candidate_state.get(
                "db_bot_1",
                candidate_state.get("db_bot", 0),
            )
            or 0
        ),
        "db_bot_2": int(
            candidate_state.get(
                "db_bot_2",
                candidate_state.get(
                    "db_bot_1",
                    candidate_state.get("db_bot", 0),
                ),
            )
            or 0
        ),
        "bars": int(candidate_state.get("bot1_count", 0) or 0)
        + int(candidate_state.get("bot2_count", 0) or 0),
        "dia": int(
            candidate_state.get(
                "db_bot_1",
                candidate_state.get("db_bot", 0),
            )
            or 0
        ),
        "Ast_bot": float(candidate.get("Ast_bot", 0.0) or 0.0),
        "summary_phiMu_kNm": capacity,
        "summary_Mu_star_kNm": demand,
        "bending_util": None,
        "worst_util": float(candidate.get("worst_util", 0.0) or 0.0),
        "real_util": demand / capacity if capacity > 1e-9 else None,
        "optimisation_score": float(
            _mode_candidate_objective_util(candidate)
        ),
        "score": (
            None
            if candidate.get("score") is None
            else float(candidate.get("score", 0.0) or 0.0)
        ),
        "pass": bool(candidate.get("is_compliant")),
        "source": str(candidate.get("source") or ""),
        "ductility_util": ductility_util,
        "ductility_pass": (
            None if ductility_util is None else ductility_util <= 1.0
        ),
        "ductility_tier": int(candidate.get("_ductility_tier", 0) or 0),
        "ductility_tier_label": str(
            candidate.get("_ductility_tier_label") or ""
        ),
        "reason_selected": str(candidate.get("_ductility_reason") or ""),
    }
    try:
        bending_util = ((overview.get("utils") or {}).get("bending"))
        summary["bending_util"] = (
            None if bending_util is None else float(bending_util)
        )
    except (TypeError, ValueError):
        summary["bending_util"] = None
    return summary


def _mode_materialize_full_evaluated_candidate(
    candidate: dict | None,
    *,
    source: str,
) -> dict | None:
    if not candidate:
        return None
    candidate_state = dict(candidate.get("state") or {})
    if not candidate_state:
        return None
    full_candidate = evaluate_candidate_full(
        candidate_state,
        source=source,
        label=str(candidate.get("label") or source.replace("_", " ").title()),
        action_type=str(candidate.get("action_type") or ""),
        updates=dict(candidate.get("updates") or {}),
    )
    if full_candidate is None:
        return None
    for key in (
        "score",
        "reo_complexity",
        "guidance_preview_util",
        "arrangement",
        "actual_ast",
        "required_ast",
    ):
        if key in candidate:
            full_candidate[key] = candidate.get(key)
    return full_candidate


def _mode_guidance_focus_from_updates(updates: dict) -> str:
    if any(key in updates for key in {"D", "b", "bw", "tw"}):
        return "geometry"
    if any(
        key in updates
        for key in {
            "bot_row_count",
            "bot1_layout_mode",
            "bot1_count",
            "db_bot_1",
            "bot2_layout_mode",
            "bot2_count",
            "db_bot_2",
            "bot_row_1_mode",
            "bot_row_1_bars",
            "bot_row_1_spacing",
            "bot_row_1_dia",
            "bot_row_2_mode",
            "bot_row_2_bars",
            "bot_row_2_spacing",
            "bot_row_2_dia",
        }
    ):
        return "bending"
    if any(key in updates for key in {"lig_d", "lig_legs", "s_lig"}):
        return "shear"
    return "general"


def _mode_recommendation_search_allowed(state: dict) -> bool:
    design_context = _build_design_actions_context(state)
    guidance_state = dict(
        design_context.get("state") or _guidance_state_snapshot(state)
    )
    overview = _collect_design_overview(
        guidance_state,
        context=design_context,
    )
    return not _guidance_not_started(guidance_state, overview)


def _application_overall_status_from_rows(
    rows: list[dict] | tuple[dict, ...] | None,
) -> tuple[str, str]:
    filtered = [
        row
        for row in (rows or ())
        if isinstance(row, dict)
        and not row.get("is_informational")
        and str(row.get("status", "")).upper() != "INFO"
    ]
    if not filtered:
        return "\u00e2\u20ac\u201d", "rgba(31, 119, 180, 0.08)"
    statuses = [
        str(row.get("status", "")).upper() for row in filtered
    ]
    if any("FAIL" in status or status == "NG" for status in statuses):
        return "FAIL", "rgba(255,0,0,0.12)"
    if any(
        "WARN" in status
        or "NEAR LIMIT" in status
        or status == "CHECK"
        for status in statuses
    ):
        return "NEAR LIMIT", "rgba(255,193,7,0.15)"
    if any("PASS" in status or status == "OK" for status in statuses):
        return "PASS", "rgba(0,128,0,0.12)"
    return "\u00e2\u20ac\u201d", "rgba(31, 119, 180, 0.08)"


def _application_guidance_bucket(
    status: str,
    util: float | None = None,
) -> str:
    upper = str(status or "—").upper()
    if "START" in upper:
        return "start"
    if "EFFICIENCY" in upper or "TIGHTEN" in upper:
        return "efficiency"
    if "FAIL" in upper or upper == "NG":
        return "fail"
    if "WARN" in upper or "NEAR LIMIT" in upper or upper == "CHECK":
        return "warn"
    if util is not None and util > 1.0:
        return "fail"
    if util is not None and util >= 0.9:
        return "warn"
    return "pass"


def _application_merge_guidance_state(
    state: dict,
    updates: dict,
) -> dict:
    return {**state, **updates}


def _application_distance_to_target_band(
    util: float,
    target_min: float,
    target_max: float,
) -> float:
    try:
        value = float(util)
        lower = float(target_min)
        upper = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if lower <= value <= upper:
        return 0.0
    return lower - value if value < lower else value - upper


def _application_reinforcement_options_remain(
    state: dict,
    *,
    reo_counts: tuple[int, ...],
    reo_bar_dias: tuple[int, ...],
) -> bool:
    count_1 = _int_from_state_owned(state, "bot1_count", 0)
    count_2 = _int_from_state_owned(state, "bot2_count", 0)
    dia_1 = _int_from_state_owned(state, "db_bot_1", 0)
    dia_2 = _int_from_state_owned(state, "db_bot_2", dia_1 or 0)
    return any(
        (
            count_1 < max(reo_counts),
            count_2 < max(reo_counts),
            count_1 > 0 and count_2 <= 0,
            dia_1 < max(reo_bar_dias) or dia_2 < max(reo_bar_dias),
            count_1 > 2 and count_1 != count_2,
        )
    )


def _application_bending_demands_negligible(
    actions: dict | None,
    *,
    demand_abs_tol_knm: float,
) -> bool:
    if not isinstance(actions, dict):
        return False
    try:
        moment = abs(float(actions.get("Mu", 0.0) or 0.0))
    except (TypeError, ValueError):
        return False
    return moment <= demand_abs_tol_knm + 1e-12


def _application_guidance_cleanup_candidate_id(
    family: str,
    updates: dict,
) -> str:
    try:
        fingerprint = stable_fingerprint_for_payload(
            {"family": family, "updates": dict(updates or {})}
        )
        return f"local_cleanup:{family}:{fingerprint}"
    except Exception:
        signature = ",".join(
            f"{key}={updates[key]}" for key in sorted(dict(updates or {}))
        )
        return f"local_cleanup:{family}:{signature}"


def _application_accepted_green_exact_blocker_is_valid(
    blocker: dict | None,
) -> bool:
    if not isinstance(blocker, dict):
        return False
    required_fields = (
        "family",
        "current_util",
        "threshold",
        "attempted_candidate_count",
        "best_rejected_candidate_id",
        "attempted_updates",
        "failed_check_name",
        "failed_check_status",
        "failed_check_util",
        "failed_check_demand",
        "failed_check_capacity_or_limit",
    )
    for field in required_fields:
        value = blocker.get(field)
        if value in (None, "", [], {}) and field == "failed_check_demand":
            value = blocker.get("demand")
        if (
            value in (None, "", [], {})
            and field == "failed_check_capacity_or_limit"
        ):
            value = blocker.get("capacity_or_limit")
        if value in (None, "", [], {}):
            return False
    reason = str(
        blocker.get("why_reduction_would_hurt_other_design_elements")
        or blocker.get(
            "reason_reducing_this_family_would_affect_other_design_elements"
        )
        or blocker.get("reason")
        or ""
    ).strip().lower()
    return bool(reason) and reason not in {
        "no safe cleanup found",
        "candidate failed",
        "engineering constraint",
    }


def _application_shared_state_snapshot() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }


def _application_state_update_reduces_section_size(
    current_state: dict,
    next_state: dict,
) -> bool:
    current_width = _float_from_state_owned(current_state, "b", 0.0)
    next_width = _float_from_state_owned(
        next_state,
        "b",
        current_width,
    )
    current_depth = _float_from_state_owned(current_state, "D", 0.0)
    next_depth = _float_from_state_owned(
        next_state,
        "D",
        current_depth,
    )
    return bool(
        next_width < current_width - 1e-9
        or next_depth < current_depth - 1e-9
    )


def _application_guidance_objective_util_from_overview(
    overview: dict,
    goal: str,
) -> float | None:
    utils = dict((overview or {}).get("utils") or {})
    bending_pack = ((overview or {}).get("packs") or {}).get("bending") or {}
    capacity = float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    demand = float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    bending_demand = demand / capacity if capacity > 1e-9 else None
    if goal == "less_shear_reinforcement":
        value = utils.get("shear")
        return None if value is None else float(value)
    candidates = [
        value
        for value in (
            bending_demand,
            utils.get("bending"),
            utils.get("shear"),
        )
        if value is not None
    ]
    return None if not candidates else max(float(value) for value in candidates)


def _application_is_design_guide_good_utilisation_band(util: object) -> bool:
    if util is None:
        return False
    try:
        value = float(util)
    except (TypeError, ValueError):
        return False
    return not math.isnan(value) and 0.80 <= value <= 0.95


def _application_mode_recommendation_expected_bend_util(
    mode_tighten: dict | None,
) -> float | None:
    if not isinstance(mode_tighten, dict):
        return None
    for key in ("expected_util", "real_util"):
        raw = mode_tighten.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isnan(value):
            return value
    summary = mode_tighten.get("candidate_summary") or {}
    capacity = float(summary.get("summary_phiMu_kNm", 0.0) or 0.0)
    demand = float(summary.get("summary_Mu_star_kNm", 0.0) or 0.0)
    return demand / capacity if capacity > 1e-9 else None


def _application_local_cleanup_candidate_affects_family(
    family: str,
    updates: dict | None,
) -> bool:
    family_id = str(family or "").strip().lower()
    keys = set(dict(updates or {}))
    has_shear = bool(keys & _COMPOUND_SHEAR_UPDATE_KEYS)
    has_bottom = bool(keys & _COMPOUND_BOTTOM_UPDATE_KEYS) or any(
        str(key).startswith("bot") or str(key).startswith("db_bot")
        for key in keys
    )
    primary_geometry_keys = {
        "sec_shape",
        "b",
        "D",
        "bf",
        "tf",
        "bw",
        "tw",
        "bf_bot",
        "tf_bot",
    }
    has_geometry = bool(
        keys & primary_geometry_keys
        or keys & _COMPOUND_GEOMETRY_UPDATE_KEYS
    )
    if family_id == "shear":
        return has_shear
    if family_id in {"bending", "crack", "deflection", "serviceability"}:
        return bool(has_bottom or has_geometry)
    if family_id == "geometry":
        return has_geometry
    return False


def _application_one_click_candidate_payload_signature(
    updates: dict,
) -> tuple:
    return tuple(
        (
            key,
            round(float(updates[key]), 6)
            if isinstance(updates[key], float)
            else updates[key],
        )
        for key in sorted((updates or {}).keys())
    )


def _application_single_row_bottom_reo_updates(
    count: int,
    diameter: int,
) -> dict:
    return _bottom_arrangement_to_shared_updates_owned(
        {
            "bot1_count": int(count),
            "db_bot_1": int(diameter),
            "bot2_count": 0,
            "db_bot_2": int(diameter),
        }
    )


def _application_guidance_update_signature(item: dict | None) -> tuple:
    if not isinstance(item, dict):
        return tuple()
    payload = dict(item.get("action_payload") or {})
    updates = dict(
        payload.get("updates")
        or payload.get("resolved_candidate_updates")
        or {}
    )
    keys = (
        "b",
        "D",
        "lig_d",
        "lig_legs",
        "s_lig",
        "db_bot_1",
        "db_bot_2",
        "bot1_count",
        "bot2_count",
        "nb_bot",
        "db_bot",
    )
    return tuple((key, updates.get(key)) for key in keys if key in updates)


def _application_local_cleanup_debug_defaults(
    previous_primary_title: str | None = None,
) -> dict:
    return {
        "local_cleanup_promoted": False,
        "local_cleanup_family": None,
        "local_cleanup_candidate_id": None,
        "local_cleanup_reason": None,
        "local_cleanup_blocked_reason": None,
        "previous_primary_title": previous_primary_title,
        "final_primary_title": previous_primary_title,
    }


def _application_state_with_overrides(state: dict, **updates: Any) -> dict:
    return {**state, **updates}


def _application_guidance_compact_change_text(
    change_lines: list[str],
) -> str:
    lines = [
        str(line).strip()
        for line in (change_lines or [])
        if str(line).strip()
    ]
    return (
        "No direct design changes identified."
        if not lines
        else " | ".join(lines[:3])
    )


def _application_guidance_expected_util_text(value: Any) -> str:
    try:
        if value is None:
            return "Expected util: -"
        return f"Expected util: {float(value):.2f}"
    except (TypeError, ValueError):
        return "Expected util: -"


def _application_candidate_failure_coverage_summary(
    current_state: dict,
    candidate: dict,
    *,
    collect_design_overview: Callable[[dict], dict],
) -> dict:
    current_overview = (
        collect_design_overview(current_state)
        if isinstance(current_state, dict)
        else {}
    )
    candidate_overview = (
        dict(candidate.get("overview") or {})
        if isinstance(candidate, dict)
        else {}
    )
    current_fail = sorted(
        key
        for key, value in (current_overview.get("statuses") or {}).items()
        if str(value or "").upper() == "FAIL"
    )
    candidate_fail = sorted(
        key
        for key, value in (candidate_overview.get("statuses") or {}).items()
        if str(value or "").upper() == "FAIL"
    )
    covered = sorted(key for key in current_fail if key not in candidate_fail)
    remaining = sorted(key for key in current_fail if key in candidate_fail)
    return {
        "current_fail_keys": list(current_fail),
        "candidate_fail_keys": list(candidate_fail),
        "covered_fail_keys": list(covered),
        "remaining_fail_keys": list(remaining),
        "covers_all_current_failures": bool(current_fail) and not remaining,
    }


def _application_evaluate_auto_design_candidate(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    evaluate_candidate_full: Callable[..., dict | None],
) -> dict | None:
    candidate_state = _guidance_state_snapshot_owned(state)
    if updates:
        candidate_state.update(updates)
    return evaluate_candidate_full(
        candidate_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
    )


def _application_guidance_compact_why_text(item: dict) -> str:
    payload = dict(item.get("action_payload") or {})
    explicit = str(
        item.get("guidance_why_text_compact")
        or payload.get("guidance_why_text_compact")
        or ""
    ).strip()
    if explicit:
        return explicit if explicit.lower().startswith("why:") else f"Why: {explicit}"
    raw = item.get("guidance_why")
    if not isinstance(raw, str) or not raw.strip():
        raw = str(item.get("reasoning") or "")
    why = str(raw or "").strip()
    if why.lower().startswith("why:"):
        why = why[4:].strip()
    sentence = " ".join(why.split())
    for marker in (". ", "! ", "? "):
        if marker in sentence:
            sentence = sentence.split(marker, 1)[0].strip() + marker.strip()
            break
    else:
        if sentence and not sentence.endswith((".", "!", "?")):
            sentence += "."
    if not sentence:
        return (
            "Why: This update targets the governing check and improves "
            "utilisation."
        )
    return f"Why: {sentence}"


def _application_guidance_default_alternatives_text(
    state: dict,
    updates: dict,
    subfamilies: list[str],
) -> str:
    families = set(
        subfamilies or _compound_subfamilies_from_updates(updates)
    )
    if families >= {"geometry", "bottom_reo"}:
        initial = _guidance_state_snapshot_owned(state)
        updated = {**initial, **updates}
        depth_before = _float_from_state_owned(initial, "D", 0.0)
        depth_after = _float_from_state_owned(
            updated,
            "D",
            depth_before,
        )
        _, _, width_before = _resolve_geometry_width_context_owned(initial)
        width_after = _design_width_value_owned(updated)
        if width_after > width_before + 0.5 and depth_after <= depth_before + 0.5:
            return (
                "Other options: Increase depth instead, or use a different "
                "bottom reo layout."
            )
        if depth_after > depth_before + 0.5 and width_after <= width_before + 0.5:
            return (
                "Other options: Increase width instead, or use a different "
                "bottom reo layout."
            )
        return (
            "Other options: Use a geometry-first step, or a different bottom "
            "reo layout."
        )
    if "shear" in families:
        return "Other options: Tighten stirrup spacing, or increase the number of legs."
    if "geometry" in families:
        return "Other options: Increase depth or section width."
    if "bottom_reo" in families:
        return "Other options: Use a different bottom reo layout."
    return ""


def _application_critical_case_name(candidate: dict | None) -> str:
    utils = dict(((candidate or {}).get("overview") or {}).get("utils") or {})
    ranked: list[tuple[str, float]] = []
    for key in ("bending", "shear", "crack", "deflection"):
        try:
            value = float(utils.get(key))
        except (TypeError, ValueError):
            continue
        if not math.isnan(value):
            ranked.append((key, value))
    return (
        "overall"
        if not ranked
        else max(ranked, key=lambda item: item[1])[0]
    )


def _application_critical_case_util(
    candidate: dict | None,
    case_name: str,
) -> float | None:
    raw = (
        ((candidate or {}).get("overview") or {})
        .get("utils", {})
        .get(case_name)
    )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def _application_protected_case_min_util(
    protected_before: float | None,
    mode_config: dict,
) -> float:
    target_min = float(mode_config.get("target_util_min", 0.8) or 0.8)
    if protected_before is None:
        return target_min - 0.02
    return max(0.0, min(target_min, float(protected_before)) - 0.02)


def _application_candidate_preserves_protected_case(
    candidate: dict,
    protected_case: str,
    *,
    protected_min_util: float,
) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    protected_util = _application_critical_case_util(
        candidate,
        protected_case,
    )
    return bool(
        protected_util is not None
        and protected_util <= 1.0 + 1e-9
        and protected_util >= protected_min_util - 1e-9
    )


def _application_candidate_reduces_noncritical_provision(
    candidate: dict,
    reference_candidate: dict,
) -> bool:
    if not candidate or not reference_candidate:
        return False
    if float(candidate.get("Ast_bot", 0.0) or 0.0) < float(
        reference_candidate.get("Ast_bot", 0.0) or 0.0
    ) - 1e-6:
        return True
    if float(candidate.get("shear_density", 0.0) or 0.0) < float(
        reference_candidate.get("shear_density", 0.0) or 0.0
    ) - 1e-6:
        return True
    candidate_complexity = float(
        candidate.get(
            "reo_complexity",
            _compute_reo_complexity_owned(candidate),
        )
        or 0.0
    )
    reference_complexity = float(
        reference_candidate.get(
            "reo_complexity",
            _compute_reo_complexity_owned(reference_candidate),
        )
        or 0.0
    )
    return candidate_complexity < reference_complexity - 1e-6


def _application_allow_early_target_exit(mode_config: dict) -> bool:
    return (
        str(mode_config.get("search_strategy", "balanced") or "balanced")
        != "balanced"
    )


def _application_collect_failures(results: dict) -> list[tuple[str, float]]:
    failures: list[tuple[str, float]] = []
    for family in ("bending", "shear"):
        raw = (results.get(family) or {}).get("util")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 1.0:
            failures.append((family, value))
    ductility = dict(results.get("ductility") or {})
    try:
        value = float(ductility.get("ku"))
        limit = float(ductility.get("limit"))
        if value > limit:
            failures.append(("ductility", value))
    except (TypeError, ValueError):
        pass
    return failures


def _application_choose_strategy(
    failures: list[tuple[str, float]],
) -> str:
    families = {family for family, _ in failures}
    if "ductility" in families:
        return "increase_depth"
    if "bending" in families:
        return "increase_capacity"
    if "shear" in families:
        return "increase_shear"
    return "optimise"


def _application_apply_bottom_bar_count_update(
    candidate: dict,
    state: dict,
    new_total: int,
) -> None:
    if _int_from_state_owned(state, "bot2_count", 0) > 0:
        new_bottom_1 = max(2, int(math.ceil(new_total / 2.0)))
        new_bottom_2 = max(0, int(new_total - new_bottom_1))
    else:
        new_bottom_1 = max(2, int(new_total))
        new_bottom_2 = 0
    candidate.update(
        {
            "bot1_count": new_bottom_1,
            "bot2_count": new_bottom_2,
            "bot_row_count": 2 if new_bottom_2 > 0 else 1,
            "nb_bot": new_bottom_1 + new_bottom_2,
        }
    )


def _application_candidate_worst_util_value(
    candidate: dict | None,
) -> float:
    if not isinstance(candidate, dict):
        return float("inf")
    value = candidate.get("worst_util")
    if value is None:
        value = dict(candidate.get("overview") or {}).get("worst_util")
    try:
        return float(value) if value is not None else float("inf")
    except (TypeError, ValueError):
        return float("inf")


def _application_results_worst_util(results: dict | None) -> float:
    try:
        value = dict((results or {}).get("_overview") or {}).get("worst_util")
        return float(value) if value is not None else float("inf")
    except (TypeError, ValueError):
        return float("inf")


def _application_scaled_bottom_total_for_factor(
    state: dict,
    factor: float,
) -> int:
    current_total = max(
        _int_from_state_owned(state, "bot1_count", 0)
        + _int_from_state_owned(state, "bot2_count", 0),
        _int_from_state_owned(state, "nb_bot", 0),
        2,
    )
    safe_factor = max(float(factor or 1.0), 1.0)
    return max(
        current_total + 1,
        int(math.ceil(current_total * safe_factor)),
    )


def _application_auto_design_results_from_candidate(
    candidate: dict | None,
) -> dict:
    overview = dict((candidate or {}).get("overview") or {})
    utils = dict(overview.get("utils") or {})
    ductility_util = dict(
        (candidate or {}).get("bending_components") or {}
    ).get("ductility_util")
    limit = 0.36
    try:
        ku_value = (
            None
            if ductility_util is None
            else float(ductility_util) * limit
        )
    except (TypeError, ValueError):
        ku_value = None
    return {
        "bending": {"util": utils.get("bending")},
        "shear": {"util": utils.get("shear")},
        "ductility": {"ku": ku_value, "limit": limit},
        "row_count": int((candidate or {}).get("row_count", 1) or 1),
        "_overview": overview,
    }


def _application_candidate_changes_geometry(
    reference_state: dict | None,
    candidate_state: dict | None,
) -> bool:
    keys = {"sec_shape", "b", "D", "bf", "tf", "bw", "tw", "bf_bot", "tf_bot"}
    before = reference_state if isinstance(reference_state, dict) else {}
    after = candidate_state if isinstance(candidate_state, dict) else {}
    return any(before.get(key) != after.get(key) for key in keys)


def _application_candidate_changes_local_variables(
    reference_state: dict | None,
    candidate_state: dict | None,
) -> bool:
    geometry_keys = {
        "sec_shape",
        "b",
        "D",
        "bf",
        "tf",
        "bw",
        "tw",
        "bf_bot",
        "tf_bot",
    }
    before = reference_state if isinstance(reference_state, dict) else {}
    after = candidate_state if isinstance(candidate_state, dict) else {}
    return any(
        key not in geometry_keys
        for key in after
        if before.get(key) != after.get(key)
    )


def _application_cleanup_candidate_debug_payload(
    candidate: dict,
    reference_candidate: dict,
    protected_case: str,
    *,
    accepted: bool,
    reason: str,
) -> dict:
    geometry_changed = _application_candidate_changes_geometry(
        reference_candidate.get("state"),
        candidate.get("state"),
    )
    local_changed = _application_candidate_changes_local_variables(
        reference_candidate.get("state"),
        candidate.get("state"),
    )
    return {
        "candidate_label": str(candidate.get("label") or ""),
        "variables_changed": sorted(
            list((candidate.get("updates") or {}).keys())
        ),
        "candidate_type": (
            "geometry_fallback" if geometry_changed else "local_cleanup"
        ),
        "geometry_changed": geometry_changed,
        "local_changed": local_changed,
        "protected_case": protected_case,
        "protected_util_before": _application_critical_case_util(
            reference_candidate,
            protected_case,
        ),
        "protected_util_after": _application_critical_case_util(
            candidate,
            protected_case,
        ),
        "overall_worst_util": float(
            candidate.get("worst_util", 0.0) or 0.0
        ),
        "accepted": bool(accepted),
        "reason": reason,
    }


def _application_cleanup_candidate_rank(
    candidate: dict,
    reference_candidate: dict,
    protected_case: str,
) -> tuple:
    candidate_state = dict((candidate or {}).get("state") or {})
    reference_state = dict((reference_candidate or {}).get("state") or {})
    protected_after = _application_critical_case_util(
        candidate,
        protected_case,
    )
    protected_before = _application_critical_case_util(
        reference_candidate,
        protected_case,
    )
    width_delta = abs(
        _design_width_value_owned(candidate_state)
        - _design_width_value_owned(reference_state)
    )
    depth_delta = abs(
        _float_from_state_owned(candidate_state, "D", 0.0)
        - _float_from_state_owned(reference_state, "D", 0.0)
    )
    ast_delta = max(
        0.0,
        float(
            (reference_candidate or {}).get(
                "Ast_bot",
                _float_from_state_owned(reference_state, "Ast_bot", 0.0),
            )
            or 0.0
        )
        - float(
            (candidate or {}).get(
                "Ast_bot",
                _float_from_state_owned(candidate_state, "Ast_bot", 0.0),
            )
            or 0.0
        ),
    )
    shear_density_delta = max(
        0.0,
        float((reference_candidate or {}).get("shear_density", 0.0) or 0.0)
        - float((candidate or {}).get("shear_density", 0.0) or 0.0),
    )
    protected_drop = (
        max(0.0, protected_before - protected_after)
        if protected_before is not None and protected_after is not None
        else 0.0
    )
    return (
        0 if bool((candidate or {}).get("candidate_reaches_target_band")) else 1,
        float(
            (candidate or {}).get(
                "candidate_distance_to_target_band",
                999.0,
            )
            or 999.0
        ),
        protected_drop,
        1
        if _application_candidate_changes_geometry(
            reference_state,
            candidate_state,
        )
        else 0,
        width_delta + depth_delta,
        -ast_delta,
        -shear_density_delta,
        float(
            (candidate or {}).get(
                "reo_complexity",
                _compute_reo_complexity_owned(candidate),
            )
            or 0.0
        ),
        float((candidate or {}).get("score", 0.0) or 0.0),
        str(
            (candidate or {}).get("candidate_id")
            or (candidate or {}).get("label")
            or ""
        ),
    )


def _application_utilisation_gap(
    candidate: dict,
    mode_config: dict,
) -> float:
    util = _mode_candidate_objective_util(candidate)
    lower = float(mode_config["target_util_min"])
    upper = float(mode_config["target_util_max"])
    if util < lower:
        return lower - util
    if util > upper:
        return util - upper
    return abs(util - (lower + upper) / 2.0)


def _application_is_meaningfully_better(
    new_result: dict,
    old_result: dict,
    mode_config: dict,
) -> bool:
    if not new_result or not old_result:
        return False
    strategy = str(
        mode_config.get("search_strategy", "balanced") or "balanced"
    )
    min_score = float(
        mode_config.get("min_score_improvement", 0.25) or 0.25
    )
    min_util = float(
        mode_config.get("min_util_improvement", 0.01) or 0.01
    )
    score_gain = float(
        old_result.get("score", float("inf")) or float("inf")
    ) - float(new_result.get("score", float("inf")) or float("inf"))
    util_gain = _application_utilisation_gap(
        old_result,
        mode_config,
    ) - _application_utilisation_gap(new_result, mode_config)
    depth_gain = float(old_result.get("depth", 0.0) or 0.0) - float(
        new_result.get("depth", 0.0) or 0.0
    )
    reo_gain = float(
        old_result.get(
            "reo_complexity",
            _compute_reo_complexity_owned(old_result),
        )
        or 0.0
    ) - float(
        new_result.get(
            "reo_complexity",
            _compute_reo_complexity_owned(new_result),
        )
        or 0.0
    )
    if strategy == "shallow":
        return bool(
            depth_gain
            >= float(
                mode_config.get("material_depth_delta_mm", 25.0) or 25.0
            )
            or score_gain > min_score
            or util_gain > min_util
        )
    if strategy == "low_reo":
        return bool(
            reo_gain
            >= float(
                mode_config.get("material_reo_complexity_delta", 4.0) or 4.0
            )
            or score_gain > min_score
            or util_gain > min_util
        )
    return bool(
        score_gain > min_score
        or util_gain > min_util
        or depth_gain
        >= float(mode_config.get("material_depth_delta_mm", 25.0) or 25.0)
        or reo_gain
        >= float(
            mode_config.get("material_reo_complexity_delta", 4.0) or 4.0
        )
    )


def _application_geometry_trial_title_for_choice(
    base_title: str,
    geometry_trial: dict,
    state: dict,
) -> str:
    updates = dict(geometry_trial.get("updates") or {})
    if not updates:
        return base_title
    merged = {**state, **updates}
    depth_before = _float_from_state_owned(state, "D", 0.0)
    depth_after = _float_from_state_owned(merged, "D", depth_before)
    width_key, _, width_before = _resolve_geometry_width_context_owned(state)
    width_after = float(
        updates.get(
            width_key,
            merged.get(width_key, width_before),
        )
        or width_before
    )
    if depth_after < depth_before - 1e-9 and width_after > width_before + 1e-9:
        return "Rebalance depth and width for bending"
    if depth_after < depth_before - 1e-9 and width_after <= width_before + 1e-9:
        return "Reduce depth slightly for bending"
    if width_after > width_before + 1e-9 and abs(depth_after - depth_before) <= 1e-9:
        return "Increase width slightly for bending"
    if depth_after > depth_before + 1e-9 and width_after <= width_before + 1e-9:
        return "Increase depth for bending"
    if depth_after > depth_before + 1e-9 and width_after > width_before + 1e-9:
        return "Increase depth and width for bending"
    return base_title


def _application_shear_spacing_guidance_floor_mm(
    *,
    reo_spacings: tuple[float, ...],
) -> float:
    return float(min(reo_spacings)) if reo_spacings else 75.0


def _application_next_tighter_link_spacing_updates(
    state: dict,
    *,
    reo_spacings: tuple[float, ...],
) -> dict | None:
    current = _float_from_state_owned(state, "s_lig", 0.0)
    if current <= 0.0 or not reo_spacings:
        return None
    eligible = [
        float(value)
        for value in reo_spacings
        if float(value) < current - 1e-9
    ]
    if not eligible:
        return None
    updates = {"s_lig": max(eligible)}
    return None if _updates_match_state(state, updates) else updates


def _application_fallback_shear_reinforcement_step_updates(
    state: dict,
    *,
    reo_bar_dias: tuple[int, ...],
) -> dict | None:
    legs = max(_int_from_state_owned(state, "lig_legs", 2), 2)
    diameter = max(_int_from_state_owned(state, "lig_d", 10), 10)
    if legs < 8:
        updates = {"lig_legs": int(min(8, legs + 2))}
        if not _updates_match_state(state, updates):
            return updates
    for next_diameter in reo_bar_dias:
        if diameter < int(next_diameter) <= 24:
            updates = {"lig_d": int(next_diameter)}
            if not _updates_match_state(state, updates):
                return updates
    return None


def _application_shear_cleanup_possible(
    state: dict | None,
    *,
    reo_spacings: tuple[float, ...],
) -> bool:
    if not isinstance(state, dict):
        return False
    lig_legs = _int_from_state_owned(state, "lig_legs", 0)
    s_lig = _float_from_state_owned(state, "s_lig", 0.0)
    max_spacing = float(max(reo_spacings) if reo_spacings else 300.0)
    return lig_legs > 0 or (
        s_lig > 0.0 and s_lig < max_spacing - 1e-9
    )


def _application_shear_overdesign_reserve_guidance_predicate(
    working_state: dict,
    overview: dict,
    actions: dict,
    *,
    current_shear_status: str,
    current_shear_util: float | None,
    shear_cleanup_possible: bool,
    low_shear_util_cap: float,
) -> tuple[bool, dict]:
    """Return the scheduling-only heavy-shear-reserve decision and evidence."""
    detail: dict = {
        "active_links": bool(_shear_reinforcement_is_active(working_state)),
        "cleanup_possible": bool(shear_cleanup_possible),
        "all_key_pass": bool((overview or {}).get("all_key_pass")),
        "no_any_fail": not bool((overview or {}).get("any_fail")),
        "truth_status_pass": False,
        "final_shear_truth_resolved": working_state.get(
            "final_shear_truth_resolved"
        ),
        "demand_non_negligible": not _shear_demands_negligible(actions),
        "low_demand_cleanup_allowed": False,
        "shear_util": current_shear_util,
        "low_shear_util_cap": float(low_shear_util_cap),
        "low_shear_util": False,
        "combined": False,
    }
    if not detail["active_links"] or not detail["cleanup_possible"]:
        return False, detail
    if not detail["all_key_pass"] or not detail["no_any_fail"]:
        return False, detail
    if not detail["demand_non_negligible"]:
        detail["low_demand_cleanup_allowed"] = False
        return False, detail
    if working_state.get("final_shear_truth_resolved") is False:
        return False, detail
    status = str(current_shear_status or "").strip().upper()
    detail["truth_status_pass"] = status == "PASS"
    if not detail["truth_status_pass"] or current_shear_util is None:
        return False, detail
    try:
        shear_util = float(current_shear_util)
    except (TypeError, ValueError):
        return False, detail
    detail["low_shear_util"] = (
        shear_util <= float(low_shear_util_cap) + 1e-12
    )
    if not detail["low_shear_util"]:
        return False, detail
    detail["combined"] = True
    return True, detail


def _application_generate_less_shear_reo_variants(
    current_candidate: dict,
    mode_config: dict,
    *,
    reo_spacings: tuple[float, ...],
    reo_bar_dias: tuple[int, ...],
    canonical_no_shear_spacing_mm: float,
) -> list[dict]:
    del mode_config
    state = dict(current_candidate.get("state") or {})
    if not _application_shear_cleanup_possible(
        state,
        reo_spacings=reo_spacings,
    ):
        return []
    current_spacing = float(
        _float_from_state_owned(state, "s_lig", 200.0)
    )
    current_legs = _int_from_state_owned(state, "lig_legs", 2)
    current_diameter = _int_from_state_owned(state, "lig_d", 10)
    max_spacing = float(max(reo_spacings) if reo_spacings else 300.0)
    spacing_values = [
        float(value)
        for value in reo_spacings
        if float(value) > current_spacing + 1e-9
    ][:2]
    if max_spacing > current_spacing + 1e-9:
        spacing_values.append(max_spacing)
    spacing_values = sorted(set(spacing_values))
    leg_values = sorted(
        {
            int(value)
            for value in (current_legs, 2, 3)
            if 2 <= int(value) <= max(current_legs, 3)
        }
    )
    diameter_values = sorted(
        set(
            [
                value
                for value in reo_bar_dias
                if 0 < int(value) <= current_diameter
            ][-2:]
            or [max(int(current_diameter), 10)]
        )
    )
    variants: dict[tuple, dict] = {}
    if shear_state_eligible_for_no_links(state):
        zero_link_state = dict(state)
        zero_link_state.update(
            {
                "lig_d": 0,
                "lig_legs": 0,
                "s_lig": float(canonical_no_shear_spacing_mm),
            }
        )
        variants[
            _make_auto_design_candidate_key(zero_link_state)
        ] = zero_link_state
    for spacing in spacing_values or [current_spacing]:
        for legs in leg_values:
            for diameter in diameter_values:
                resolved_diameter = int(diameter)
                resolved_spacing = float(spacing)
                if (
                    resolved_diameter == current_diameter
                    and int(legs) == current_legs
                    and abs(resolved_spacing - current_spacing) <= 1e-9
                ):
                    continue
                candidate_state = dict(state)
                candidate_state.update(
                    {
                        "lig_d": resolved_diameter,
                        "lig_legs": int(legs),
                        "s_lig": resolved_spacing,
                    }
                )
                variants[
                    _make_auto_design_candidate_key(candidate_state)
                ] = candidate_state
    return list(variants.values())


def _application_starter_shear_diameter(
    state: dict,
    *,
    reo_bar_dias: tuple[int, ...],
) -> int:
    current_diameter = _int_from_state_owned(state, "lig_d", 0)
    if current_diameter > 0:
        return int(current_diameter)
    practical_diameters = [
        diameter for diameter in reo_bar_dias if diameter <= 16
    ]
    return int(practical_diameters[0] if practical_diameters else 10)


def _application_starter_shear_spacing(
    state: dict,
    *,
    reo_spacings: tuple[float, ...],
) -> float:
    current_spacing = _float_from_state_owned(state, "s_lig", 0.0)
    if current_spacing > 0.0 and reo_spacings:
        return float(
            min(
                reo_spacings,
                key=lambda value: abs(float(value) - current_spacing),
            )
        )
    if 200 in reo_spacings:
        return 200.0
    return float(
        reo_spacings[
            min(len(reo_spacings) - 1, len(reo_spacings) // 2)
        ]
        if reo_spacings
        else 200.0
    )


def _application_activation_shear_state(
    state: dict,
    *,
    reo_bar_dias: tuple[int, ...],
    reo_spacings: tuple[float, ...],
) -> dict:
    activated = dict(state)
    activated.update(
        {
            "lig_legs": 2,
            "lig_d": _application_starter_shear_diameter(
                state,
                reo_bar_dias=reo_bar_dias,
            ),
            "s_lig": _application_starter_shear_spacing(
                state,
                reo_spacings=reo_spacings,
            ),
        }
    )
    return activated


def _application_option_window(
    options: tuple[int, ...],
    current_value: int,
    *,
    down_steps: int,
    up_steps: int,
) -> list[int]:
    values = sorted(set(int(value) for value in options))
    if not values:
        return []
    index = min(
        range(len(values)),
        key=lambda item: abs(values[item] - int(current_value)),
    )
    lo = max(0, index - max(int(down_steps), 0))
    hi = min(len(values), index + max(int(up_steps), 0) + 1)
    return values[lo:hi]


def _application_generate_local_shear_states(
    state: dict,
    mode_config: dict,
    *,
    band: int,
    limit: int | None = None,
    reo_spacings: tuple[float, ...],
    reo_bar_dias: tuple[int, ...],
    max_stage_candidates: int,
) -> list[dict]:
    strategy = str(
        mode_config.get("search_strategy", "balanced") or "balanced"
    )
    if not _shear_reinforcement_is_active(state):
        activation_state = _application_activation_shear_state(
            state,
            reo_bar_dias=reo_bar_dias,
            reo_spacings=reo_spacings,
        )
        if (
            _make_auto_design_candidate_key(activation_state)
            == _make_auto_design_candidate_key(state)
        ):
            return []
        return [activation_state]
    current_spacing = _int_from_state_owned(state, "s_lig", 200)
    current_legs = _int_from_state_owned(state, "lig_legs", 2)
    current_diameter = _int_from_state_owned(state, "lig_d", 10)
    spacing_values = _application_option_window(
        tuple(int(value) for value in reo_spacings),
        current_spacing,
        down_steps=0,
        up_steps=0,
    )
    tighter_values = [
        int(value) for value in reo_spacings if value < current_spacing
    ]
    spacing_values.extend(tighter_values[-(2 + band):])
    spacing_values = sorted(set(spacing_values), reverse=True)
    leg_values = sorted(set([current_legs, min(current_legs + 2, 6)]))
    if strategy == "shallow" and current_legs < 6:
        leg_values.append(min(current_legs + 4, 6))
    diameter_values = _application_option_window(
        tuple(diameter for diameter in reo_bar_dias if diameter <= 16),
        current_diameter,
        down_steps=0,
        up_steps=1 + band,
    )
    states: dict[tuple, dict] = {}
    for diameter in diameter_values:
        for legs in leg_values:
            if int(legs) < 2:
                continue
            for spacing in spacing_values:
                candidate_state = dict(state)
                candidate_state.update(
                    {
                        "lig_d": int(diameter),
                        "lig_legs": int(legs),
                        "s_lig": float(spacing),
                    }
                )
                states[
                    _make_auto_design_candidate_key(candidate_state)
                ] = candidate_state
    resolved_limit = (
        int(max_stage_candidates)
        if limit is None
        else max(int(limit), 1)
    )
    return list(states.values())[:resolved_limit]


def _application_generate_local_geometry_variants(
    current_candidate: dict,
    mode_config: dict,
    *,
    is_first_hop: bool = False,
    candidate_ductility_governs: Callable[[dict], bool],
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    if _geometry_lock_enabled_owned(state):
        return []
    strategy = str(
        mode_config.get("search_strategy", "balanced") or "balanced"
    )
    _, _, current_width = _resolve_geometry_width_context_owned(state)
    current_depth = float(
        current_candidate.get(
            "depth",
            _float_from_state_owned(state, "D", 600.0),
        )
        or _float_from_state_owned(state, "D", 600.0)
    )
    if candidate_ductility_governs(current_candidate):
        width_steps = [current_width + 50.0]
        if is_first_hop:
            width_steps.append(current_width + 100.0)
        depth_steps = [current_depth + 50.0]
        if not is_first_hop:
            depth_steps.append(current_depth + 100.0)
        variants: dict[tuple, dict] = {}
        for width in width_steps:
            if width >= 250.0:
                candidate_state = _geometry_state_with_updates_owned(
                    state,
                    width=width,
                )
                variants[
                    _make_auto_design_candidate_key(candidate_state)
                ] = candidate_state
        for depth in depth_steps:
            if depth >= 350.0:
                candidate_state = _geometry_state_with_updates_owned(
                    state,
                    depth=depth,
                )
                variants[
                    _make_auto_design_candidate_key(candidate_state)
                ] = candidate_state
        return list(variants.values())
    depth_steps = [current_depth - 50.0, current_depth + 50.0]
    width_steps: list[float] = []
    if is_first_hop:
        if strategy == "shallow":
            depth_steps = [
                current_depth - 100.0,
                current_depth - 50.0,
                current_depth + 50.0,
            ]
        elif strategy == "low_reo":
            depth_steps = [
                current_depth + 50.0,
                current_depth + 100.0,
                current_depth - 50.0,
            ]
            width_steps = [
                current_width + 50.0,
                current_width + 100.0,
            ]
        else:
            depth_steps = [
                current_depth - 50.0,
                current_depth + 50.0,
                current_depth + 100.0,
            ]
            width_steps = [
                current_width - 50.0,
                current_width + 50.0,
            ]
    else:
        if strategy == "shallow":
            depth_steps = [
                current_depth - 50.0,
                current_depth + 50.0,
            ]
        elif strategy == "low_reo":
            depth_steps = [
                current_depth + 50.0,
                current_depth - 50.0,
            ]
            width_steps = [current_width + 50.0]
        else:
            width_steps = [
                current_width - 50.0,
                current_width + 50.0,
            ]
    variants: dict[tuple, dict] = {}
    for depth in depth_steps:
        if depth >= 350.0:
            candidate_state = _geometry_state_with_updates_owned(
                state,
                depth=depth,
            )
            variants[
                _make_auto_design_candidate_key(candidate_state)
            ] = candidate_state
    for width in width_steps:
        if width >= 250.0:
            candidate_state = _geometry_state_with_updates_owned(
                state,
                width=width,
            )
            variants[
                _make_auto_design_candidate_key(candidate_state)
            ] = candidate_state
    return list(variants.values())


def _application_generate_local_improvement_candidates(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
    *,
    search_band: int = 0,
    is_first_hop: bool = False,
    generate_local_bottom_arrangements: Callable[..., list[dict]],
    generate_local_shear_states: Callable[..., list[dict]],
    candidate_ductility_governs: Callable[[dict], bool],
    first_hop_raw_limit: int,
    later_hop_raw_limit: int,
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    candidates: dict[tuple, dict] = {}
    raw_limit = (
        int(first_hop_raw_limit)
        if is_first_hop
        else int(later_hop_raw_limit)
    )
    bottom_band = (
        max(int(search_band), 1)
        if is_first_hop
        else int(search_band)
    )
    for arrangement in generate_local_bottom_arrangements(
        state,
        mode_config,
        band=bottom_band,
        context=context,
        limit=raw_limit,
    ):
        candidate_state = dict(state)
        candidate_state.update(
            _bottom_arrangement_to_shared_updates_owned(arrangement)
        )
        candidates[
            _make_auto_design_candidate_key(candidate_state)
        ] = candidate_state
    if not bool(context.get("disable_shear_strength_candidates")):
        shear_bands = [int(search_band)]
        if is_first_hop:
            shear_bands = sorted(set([0, 1]))
        for band in shear_bands:
            for shear_state in generate_local_shear_states(
                state,
                mode_config,
                band=band,
                limit=raw_limit,
            ):
                candidates[
                    _make_auto_design_candidate_key(shear_state)
                ] = shear_state
    for geometry_state in _application_generate_local_geometry_variants(
        current_candidate,
        mode_config,
        is_first_hop=is_first_hop,
        candidate_ductility_governs=candidate_ductility_governs,
    ):
        candidates[
            _make_auto_design_candidate_key(geometry_state)
        ] = geometry_state
    candidates.pop(_make_auto_design_candidate_key(state), None)
    return list(candidates.values())


def _application_generate_less_bottom_reo_variants(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
    *,
    generate_local_bottom_arrangements: Callable[..., list[dict]],
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    current_ast = float(current_candidate.get("Ast_bot", 0.0) or 0.0)
    current_complexity = float(
        current_candidate.get(
            "reo_complexity",
            _compute_reo_complexity_owned(current_candidate),
        )
        or 0.0
    )
    variants: dict[tuple, dict] = {}
    for arrangement in generate_local_bottom_arrangements(
        state,
        mode_config,
        band=0,
        context=context,
    ):
        candidate_state = dict(state)
        candidate_state.update(
            _bottom_arrangement_to_shared_updates_owned(arrangement)
        )
        preview_bottom = _effective_bottom_design_state_owned(
            candidate_state,
            _candidate_bottom_updates_owned(candidate_state),
        )
        preview_candidate = {
            "state": candidate_state,
            "Ast_bot": float(
                preview_bottom.get("Ast_bot", 0.0) or 0.0
            ),
            "row_count": _bottom_row_count_owned(candidate_state),
            "bar_count": _bottom_bar_count_owned(
                candidate_state,
                preview_bottom,
            ),
            "reo_congestion_index": _reo_congestion_index_owned(
                candidate_state,
                preview_bottom,
            ),
        }
        preview_complexity = float(
            _compute_reo_complexity_owned(preview_candidate) or 0.0
        )
        if (
            float(preview_bottom.get("Ast_bot", 0.0) or 0.0)
            < current_ast - 1e-6
            or preview_complexity < current_complexity - 1e-6
        ):
            variants[
                _make_auto_design_candidate_key(candidate_state)
            ] = candidate_state
    return list(variants.values())


def _application_generate_simpler_layout_variants(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
    *,
    generate_local_bottom_arrangements: Callable[..., list[dict]],
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    current_rows = int(current_candidate.get("row_count", 0) or 0)
    current_bars = int(current_candidate.get("bar_count", 0) or 0)
    variants: dict[tuple, dict] = {}
    for arrangement in generate_local_bottom_arrangements(
        state,
        mode_config,
        band=0,
        context=context,
    ):
        candidate_state = dict(state)
        candidate_state.update(
            _bottom_arrangement_to_shared_updates_owned(arrangement)
        )
        preview_bottom = _effective_bottom_design_state_owned(
            candidate_state,
            _candidate_bottom_updates_owned(candidate_state),
        )
        row_count = _bottom_row_count_owned(candidate_state)
        bar_count = _bottom_bar_count_owned(
            candidate_state,
            preview_bottom,
        )
        if row_count < current_rows or bar_count < current_bars:
            variants[
                _make_auto_design_candidate_key(candidate_state)
            ] = candidate_state
    return list(variants.values())


def _application_generate_cleanup_candidates(
    current_candidate: dict,
    mode_config: dict,
    context: dict,
    *,
    generate_less_bottom_reo_variants: Callable[..., list[dict]],
    generate_simpler_layout_variants: Callable[..., list[dict]],
    generate_less_shear_reo_variants: Callable[..., list[dict]],
    shear_cleanup_possible: Callable[[dict | None], bool],
) -> list[dict]:
    state = dict(current_candidate.get("state") or {})
    candidates: dict[tuple, dict] = {}
    for candidate_state in generate_less_bottom_reo_variants(
        current_candidate,
        mode_config,
        context,
    ):
        candidates[
            _make_auto_design_candidate_key(candidate_state)
        ] = candidate_state
    for candidate_state in generate_simpler_layout_variants(
        current_candidate,
        mode_config,
        context,
    ):
        candidates[
            _make_auto_design_candidate_key(candidate_state)
        ] = candidate_state
    if (
        shear_cleanup_possible(state)
        and not bool(context.get("disable_shear_cleanup_candidates"))
    ):
        for candidate_state in generate_less_shear_reo_variants(
            current_candidate,
            mode_config,
        ):
            candidates[
                _make_auto_design_candidate_key(candidate_state)
            ] = candidate_state
    candidates.pop(_make_auto_design_candidate_key(state), None)
    return list(candidates.values())


def _application_augment_candidate_with_shear_if_needed(
    state: dict,
    candidate: dict,
    *,
    mode_cfg: dict | None = None,
) -> dict | None:
    """Conservative extension point: do not fabricate a combined candidate."""
    del state, candidate, mode_cfg
    return None


def _application_normalise_bottom_layer_order(
    arrangement: dict,
) -> dict:
    normalised = dict(arrangement)
    count_1 = int(normalised.get("bot1_count", 0) or 0)
    count_2 = int(normalised.get("bot2_count", 0) or 0)
    diameter_1 = int(normalised.get("db_bot_1", 0) or 0)
    diameter_2 = int(normalised.get("db_bot_2", 0) or 0)
    layer_2_preferred = diameter_2 > diameter_1 or (
        diameter_2 == diameter_1 and count_2 > count_1
    )
    if layer_2_preferred:
        (
            normalised["bot1_layout_mode"],
            normalised["bot2_layout_mode"],
        ) = (
            normalised.get("bot2_layout_mode", "Count"),
            normalised.get("bot1_layout_mode", "Count"),
        )
        normalised["bot1_count"], normalised["bot2_count"] = (
            count_2,
            count_1,
        )
        normalised["db_bot_1"], normalised["db_bot_2"] = (
            diameter_2,
            diameter_1,
        )
    return normalised


def _application_enumerate_bottom_reo_design_trials(
    state: dict,
    *,
    mode_config: dict | None = None,
    generate_local_bottom_arrangements: Callable[..., list[dict]],
) -> list[dict]:
    if not isinstance(state, dict):
        return []
    config = dict(
        mode_config
        or _design_mode_config_owned(_design_optimisation_goal_owned(state))
    )
    layout_cache: dict = {}
    arrangements = generate_local_bottom_arrangements(
        state,
        config,
        band=2,
        context={"layout_fit_cache": layout_cache},
        limit=12,
    )
    stronger_specs = [
        (2, 2, 20),
        (2, 2, 24),
        (2, 2, 28),
        (3, 3, 20),
        (3, 3, 24),
        (3, 3, 28),
        (4, 4, 24),
        (4, 4, 28),
        (6, 0, 24),
        (8, 0, 24),
        (6, 0, 28),
        (8, 0, 28),
    ]
    seen_signatures = {
        (
            int((arrangement or {}).get("bot1_count", 0) or 0),
            int((arrangement or {}).get("bot2_count", 0) or 0),
            int((arrangement or {}).get("db_bot_1", 0) or 0),
        )
        for arrangement in arrangements
    }
    for count_1, count_2, diameter in stronger_specs:
        arrangement = _application_normalise_bottom_layer_order(
            {
                "bot1_layout_mode": "Count",
                "bot1_count": count_1,
                "db_bot_1": diameter,
                "bot2_layout_mode": "Count",
                "bot2_count": count_2,
                "db_bot_2": diameter,
            }
        )
        signature = (
            int(arrangement.get("bot1_count", 0) or 0),
            int(arrangement.get("bot2_count", 0) or 0),
            int(arrangement.get("db_bot_1", 0) or 0),
        )
        if signature in seen_signatures:
            continue
        if not arrangement_fits_state(
            state,
            arrangement,
            layout_cache=layout_cache,
        ):
            continue
        arrangements.append(arrangement)
        seen_signatures.add(signature)
    output: list[dict] = []
    for arrangement in arrangements:
        resolved = dict(arrangement or {})
        updates = _bottom_arrangement_to_shared_updates_owned(resolved)
        if not isinstance(updates, dict):
            continue
        output.append(
            {
                "label": _practical_bottom_reo_label_owned(
                    int(resolved.get("bot1_count", 0) or 0),
                    int(resolved.get("bot2_count", 0) or 0),
                    int(resolved.get("db_bot_1", 0) or 0),
                ),
                "updates": updates,
                "arrangement": resolved,
            }
        )
    return output


def _application_generate_escalated_shear_states(
    state: dict,
    *,
    severity_band: str,
    reo_spacings: tuple[float, ...],
    reo_bar_dias: tuple[int, ...],
) -> list[tuple[str, dict]]:
    base_state = (
        _application_activation_shear_state(
            state,
            reo_bar_dias=reo_bar_dias,
            reo_spacings=reo_spacings,
        )
        if not _shear_reinforcement_is_active(state)
        else dict(state)
    )
    current_spacing = _int_from_state_owned(base_state, "s_lig", 200)
    current_legs = max(
        _int_from_state_owned(base_state, "lig_legs", 2),
        2,
    )
    current_diameter = max(
        _int_from_state_owned(base_state, "lig_d", 10),
        10,
    )
    width_key, _, current_width = _resolve_geometry_width_context_owned(
        base_state
    )
    current_depth = _float_from_state_owned(base_state, "D", 600.0)
    max_legs = 10 if severity_band == "extreme" else 8
    max_diameter = 24 if severity_band == "extreme" else 20
    leg_values = sorted(
        set(
            [
                current_legs,
                min(current_legs + 2, max_legs),
                min(current_legs + 4, max_legs),
            ]
        )
    )
    diameter_values = sorted(
        set(
            [
                diameter
                for diameter in reo_bar_dias
                if current_diameter <= diameter <= max_diameter
            ]
            + [current_diameter]
        )
    )
    spacing_targets = [
        value for value in reo_spacings if value <= current_spacing
    ]
    spacing_values = (
        sorted(set(spacing_targets[:3] + [current_spacing]))
        or [current_spacing]
    )
    width_steps = [current_width + 50.0, current_width + 100.0]
    depth_steps = [current_depth + 50.0, current_depth + 100.0]
    if severity_band == "extreme":
        width_steps.append(current_width + 150.0)
        depth_steps.append(current_depth + 150.0)

    generated: dict[tuple, tuple[str, dict]] = {}

    def store(candidate_state: dict) -> None:
        key = _make_auto_design_candidate_key(candidate_state)
        generated[key] = (
            _shear_candidate_type_owned(state, candidate_state),
            candidate_state,
        )

    for spacing in spacing_values:
        for legs in leg_values:
            for diameter in diameter_values:
                candidate_state = dict(base_state)
                candidate_state.update(
                    {
                        "lig_d": int(diameter),
                        "lig_legs": int(legs),
                        "s_lig": float(spacing),
                    }
                )
                store(candidate_state)

    if not _geometry_lock_enabled_owned(state):
        for width in width_steps:
            candidate_state = dict(base_state)
            candidate_state[width_key] = float(width)
            if width_key != "b":
                candidate_state["b"] = float(width)
            store(candidate_state)
        for depth in depth_steps:
            candidate_state = dict(base_state)
            candidate_state["D"] = float(depth)
            store(candidate_state)
        strong_spacing = (
            float(min(spacing_values))
            if spacing_values
            else float(current_spacing)
        )
        strong_legs = int(max(leg_values))
        strong_diameter = int(max(diameter_values))
        for width in width_steps:
            for depth in depth_steps:
                candidate_state = dict(base_state)
                candidate_state.update(
                    {
                        width_key: float(width),
                        "D": float(depth),
                        "lig_d": strong_diameter,
                        "lig_legs": strong_legs,
                        "s_lig": strong_spacing,
                    }
                )
                if width_key != "b":
                    candidate_state["b"] = float(width)
                store(candidate_state)
    return list(generated.values())


def _application_shear_governing_truth_allows_overdesign_cleanup(
    shear_pack: dict | None,
    *,
    near_limit_threshold: float,
) -> tuple[bool, dict]:
    detail: dict = {
        "shear_overdesign_truth_util": None,
        "shear_overdesign_truth_status": None,
        "shear_overdesign_truth_governing_check": None,
        "shear_cleanup_blocked_due_to_truth_near_limit": False,
    }
    if not isinstance(shear_pack, dict):
        return True, detail
    raw_status = str(
        shear_pack.get("summary_governing_status") or ""
    ).strip().upper()
    util = _parse_util_value(shear_pack.get("summary_governing_util"))
    check = str(
        shear_pack.get("summary_governing_check_name") or ""
    ).strip()
    detail["shear_overdesign_truth_util"] = util
    detail["shear_overdesign_truth_status"] = raw_status or None
    detail["shear_overdesign_truth_governing_check"] = check or None
    if raw_status in {"FAIL", "FAILED"}:
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if "NEAR" in raw_status or raw_status in (
        "WARN",
        "CHECK",
        "NEAR LIMIT",
    ):
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if util is not None:
        try:
            if float(util) >= float(near_limit_threshold) - 1e-12:
                detail[
                    "shear_cleanup_blocked_due_to_truth_near_limit"
                ] = True
                return False, detail
        except (TypeError, ValueError):
            pass
    return True, detail


def _application_efficiency_distance_to_target_band(
    worst: float,
    mode_config: dict | None = None,
    *,
    design_optimisation_goal: Callable[[], str],
) -> float:
    target_lo, target_hi, _ = _resolved_efficiency_target_band(
        mode_config,
        goal=design_optimisation_goal(),
    )
    if target_lo <= worst <= target_hi:
        return 0.0
    if worst < target_lo:
        return target_lo - worst
    return worst - target_hi


def _application_compound_efficiency_incoherent(
    base_state: dict,
    trial_state: dict,
    seed_candidate: dict,
    trial_candidate: dict,
) -> bool:
    depth_before = float(
        _float_from_state_owned(base_state, "D", 0.0)
    )
    depth_after = float(
        _float_from_state_owned(trial_state, "D", 0.0)
    )
    _, _, width_before = _resolve_geometry_width_context_owned(base_state)
    _, _, width_after = _resolve_geometry_width_context_owned(trial_state)
    ast_before = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    ast_after = float(trial_candidate.get("Ast_bot", 0.0) or 0.0)
    if (
        depth_after > depth_before + 1e-9
        and ast_after > ast_before + 1e-9
    ):
        return True
    if (
        width_after > width_before + 1e-9
        and depth_after > depth_before + 1e-9
    ):
        return True
    return False


def _application_failed_check_labels(candidate: dict | None) -> list[str]:
    statuses = ((candidate or {}).get("overview") or {}).get("statuses", {})
    return [
        key.replace("_", " ")
        for key in ("bending", "shear", "crack", "deflection")
        if str(statuses.get(key, "") or "") == "FAIL"
    ]


def _application_candidate_state_signature(
    candidate: dict | None,
) -> tuple:
    if not candidate:
        return ()
    state = _guidance_state_snapshot_owned(
        dict(candidate.get("state") or {})
    )
    return _make_auto_design_candidate_key(state)


def _application_is_valid_progress_while_failing(
    new_candidate: dict | None,
    old_candidate: dict | None,
) -> bool:
    if not new_candidate or not old_candidate:
        return False
    if bool(new_candidate.get("is_compliant")):
        return True
    old_failed = set(_application_failed_check_labels(old_candidate))
    new_failed = set(_application_failed_check_labels(new_candidate))
    old_util = float(old_candidate.get("worst_util", 999.0) or 999.0)
    new_util = float(new_candidate.get("worst_util", 999.0) or 999.0)
    if new_failed != old_failed and len(new_failed) < len(old_failed):
        return True
    if new_util < old_util - 0.01:
        return True
    return _application_candidate_state_signature(
        new_candidate
    ) != _application_candidate_state_signature(old_candidate)


def _application_compound_strengthening_viable(
    seed_candidate: dict,
    trial_candidate: dict | None,
) -> bool:
    if not trial_candidate:
        return False
    if bool(trial_candidate.get("is_compliant")):
        return True
    return _application_is_valid_progress_while_failing(
        trial_candidate,
        seed_candidate,
    )


def _application_bottom_ast_from_visible_arrangement(
    state: dict | None,
) -> float | None:
    if not isinstance(state, dict):
        return None
    try:
        count_1 = _int_from_state_owned(
            state,
            "bot1_count",
            _int_from_state_owned(state, "bot_row_1_bars", 0),
        )
        count_2 = _int_from_state_owned(
            state,
            "bot2_count",
            _int_from_state_owned(state, "bot_row_2_bars", 0),
        )
        diameter_1 = _float_from_state_owned(
            state,
            "db_bot_1",
            _float_from_state_owned(
                state,
                "bot_row_1_dia",
                _float_from_state_owned(state, "db_bot", 0.0),
            ),
        )
        diameter_2 = _float_from_state_owned(
            state,
            "db_bot_2",
            _float_from_state_owned(
                state,
                "bot_row_2_dia",
                diameter_1,
            ),
        )
        if count_1 <= 0 and count_2 <= 0:
            return None
        if count_1 > 0 and diameter_1 <= 0:
            return None
        if count_2 > 0 and diameter_2 <= 0:
            return None
        return float(
            count_1 * math.pi * diameter_1**2 / 4.0
            + count_2 * math.pi * diameter_2**2 / 4.0
        )
    except Exception:
        return None


def _application_state_update_reduces_bottom_reinforcement(
    current_state: dict,
    next_state: dict,
) -> bool:
    try:
        current_arranged = (
            _application_bottom_ast_from_visible_arrangement(current_state)
        )
        next_arranged = (
            _application_bottom_ast_from_visible_arrangement(next_state)
        )
        current = float(
            current_arranged
            if current_arranged is not None
            else (
                _effective_bottom_design_state_owned(current_state).get(
                    "Ast_bot",
                    0.0,
                )
                or 0.0
            )
        )
        next_value = float(
            next_arranged
            if next_arranged is not None
            else (
                _effective_bottom_design_state_owned(next_state).get(
                    "Ast_bot",
                    current,
                )
                or current
            )
        )
        return bool(next_value < current - 1e-6)
    except Exception:
        return False


def _application_local_cleanup_material_proxy(
    state: dict | None,
) -> float:
    source = state if isinstance(state, dict) else {}
    width = float(
        _design_width_value_owned(source)
        or _float_from_state_owned(source, "b", 0.0)
        or 0.0
    )
    depth = float(
        _float_from_state_owned(source, "D", 0.0) or 0.0
    )
    try:
        ast = float(
            _application_bottom_ast_from_visible_arrangement(source)
            or _effective_bottom_design_state_owned(source).get(
                "Ast_bot",
                0.0,
            )
            or 0.0
        )
    except Exception:
        ast = 0.0
    lig_d = float(
        _float_from_state_owned(source, "lig_d", 0.0) or 0.0
    )
    lig_legs = float(
        _float_from_state_owned(source, "lig_legs", 0.0) or 0.0
    )
    spacing = max(
        float(_float_from_state_owned(source, "s_lig", 0.0) or 0.0),
        1.0,
    )
    shear_density = lig_legs * lig_d * lig_d / spacing
    return float(
        width * depth * 0.001
        + ast * 0.05
        + shear_density * 20.0
    )


def _application_local_cleanup_family_for_updates(
    updates: dict,
    item: dict | None,
    state: dict,
) -> str:
    keys = set(dict(updates or {}))
    if keys & _COMPOUND_SHEAR_UPDATE_KEYS:
        return "shear"
    if any(
        str(key).startswith("bot")
        or str(key).startswith("db_bot")
        for key in keys
    ):
        return "bending"
    if keys & {
        "sec_shape", "b", "D", "bf", "tf", "bw", "tw", "bf_bot", "tf_bot",
    }:
        return "geometry"
    return _optimisation_candidate_family(item or {}, state)


def _application_local_cleanup_materially_reduces(
    family: str,
    current_state: dict,
    candidate_state: dict,
) -> bool:
    normalised = str(family or "").strip().lower()
    if normalised == "shear":
        return _shear_cleanup_materially_reduces_reinforcement(
            current_state, candidate_state
        )
    if normalised in {"bending", "bottom_reo"}:
        return _application_state_update_reduces_bottom_reinforcement(
            current_state, candidate_state
        )
    if normalised == "geometry":
        return _application_state_update_reduces_section_size(
            current_state, candidate_state
        )
    return bool(
        _shear_cleanup_materially_reduces_reinforcement(
            current_state, candidate_state
        )
        or _application_state_update_reduces_bottom_reinforcement(
            current_state, candidate_state
        )
        or _application_state_update_reduces_section_size(
            current_state, candidate_state
        )
    )


def _application_guidance_item_as_advisory(
    item: dict | None,
    *,
    blocked_reason: str,
) -> dict | None:
    if not isinstance(item, dict):
        return item
    out = dict(item)
    payload = dict(out.get("action_payload") or {})
    resolved_reason = str(blocked_reason or "").strip()
    payload["contract_blocked_reason"] = resolved_reason or None
    out["action_payload"] = payload
    out["action_type"] = None
    out["executor_contract_blocked_reason"] = resolved_reason or None
    blocked_text = resolved_reason.lower()
    if (
        "current design is inside the target utilisation band"
        in blocked_text
        or (
            "blocked_shear_cleanup_does_not_reach_"
            "final_family_threshold"
        )
        in blocked_text
        or (
            "blocked_zero_shear_demand_shear_update_not_meaningful"
            in blocked_text
        )
    ):
        out["check_key"] = "general"
        out["bucket"] = "pass"
        out["status"] = "PASS"
        out["title_main"] = "Design accepted - target band achieved"
        out["title"] = "Design accepted - target band achieved"
        out["title_sub"] = (
            "No one-click cleanup is executable for this state"
        )
        out["guidance_intent"] = "already_efficient"
        out["design_guide_terminal_state"] = "optimal"
        out["primary_action"] = ""
        out["secondary_action"] = (
            "No primary one-click update is displayed for this state."
        )
        out["reasoning"] = (
            "Why: all required checks remain acceptable, governing "
            "utilisation is inside the target band, and further local "
            "cleanup is blocked by the recorded engineering threshold "
            "evidence."
        )
        return out
    if resolved_reason == "primary_efficiency_card_not_executor_backed":
        out["title_main"] = (
            "Cleanup is advisory for this design state"
        )
        out["title_sub"] = (
            "Advisory reduction ideas need a specific executable update"
        )
        out["reasoning"] = (
            "Why: the solver did not attach a one-click change because "
            "the candidate was not converted into a directly executable "
            "update. Review the debug trace for the blocker."
        )
    if str(out.get("primary_action") or "").strip():
        out["primary_action"] = (
            "No one-click update is displayed for this state."
        )
    secondary = str(out.get("secondary_action") or "").strip()
    advisory = (
        "Optional advisory only: no material candidate preserved bending, "
        "shear, serviceability, and detailing checks with executable "
        "updates."
    )
    out["secondary_action"] = secondary or advisory
    return out


def _application_bending_near_limit_specific_title(
    goal: str,
    action_type: str,
) -> str | None:
    _ = goal
    if action_type == "increase_width":
        return "Increase width slightly for bending"
    if action_type == "increase_depth":
        return "Increase depth slightly for bending"
    if action_type == "apply_bottom_recommendation":
        return "Adjust bottom reinforcement for bending"
    return None


def _application_describe_guidance_step(
    before_state: dict,
    after_state: dict,
    action_type: str,
    updates: dict,
) -> str:
    if "D" in updates:
        before_depth = int(float(before_state.get("D", 0.0) or 0.0))
        after_depth = int(float(after_state.get("D", 0.0) or 0.0))
        verb = "Reduced" if after_depth < before_depth else "Increased"
        return (
            f"{verb} depth D from {before_depth} to {after_depth} mm."
        )
    width_key, _, _ = _resolve_geometry_width_context_owned(after_state)
    if width_key in updates:
        before_width = int(
            float(before_state.get(width_key, 0.0) or 0.0)
        )
        after_width = int(
            float(after_state.get(width_key, 0.0) or 0.0)
        )
        width_short = "b" if width_key == "b" else width_key
        verb = "Reduced" if after_width < before_width else "Increased"
        return (
            f"{verb} {width_short} from {before_width} to "
            f"{after_width} mm."
        )
    if any(
        key in updates
        for key in (
            "bot1_count",
            "bot2_count",
            "db_bot_1",
            "db_bot_2",
            "Ast_bot",
        )
    ):
        return (
            "Updated bottom reinforcement from "
            f"{_bottom_reo_state_label(before_state)} to "
            f"{_bottom_reo_state_label(after_state)}."
        )
    if any(
        key in updates for key in ("s_lig", "lig_legs", "lig_d")
    ):
        return (
            "Updated shear reinforcement from "
            f"{_shear_state_label_owned(before_state)} to "
            f"{_shear_state_label_owned(after_state)}."
        )
    load_keys = ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm")
    if any(key in updates for key in load_keys):
        parts: list[str] = []
        for key in load_keys:
            if key not in updates:
                continue
            try:
                before = float(before_state.get(key, 0.0) or 0.0)
                after = float(after_state.get(key, 0.0) or 0.0)
                parts.append(
                    f"{key} {before:.3f} → {after:.3f} kN/m"
                )
            except Exception:
                parts.append(str(key))
        if parts:
            return "Adjusted sustained load inputs: " + "; ".join(parts) + "."
    return f"Applied {action_type.replace('_', ' ')}."


def _application_guidance_before_after_text(
    item: dict,
    state: dict,
) -> str | None:
    action_type = item.get("action_type")
    if not action_type:
        return None
    if action_type in {
        "apply_mode_recommendation",
        "apply_bottom_recommendation",
        "apply_geometry_recommendation",
        "apply_shear_recommendation",
        "apply_compound_guidance",
        "reduce_bottom_reinforcement",
        "increase_link_spacing",
        "reduce_number_of_legs",
    }:
        return None
    updates = _guidance_action_updates(
        action_type,
        item.get("action_payload") or {},
        state=state,
    )
    if not updates:
        return None
    after_state = dict(state)
    after_state.update(updates)
    return _application_describe_guidance_step(
        state,
        after_state,
        action_type,
        updates,
    )


def _application_infer_families_mentioned_in_label(
    label: str,
) -> frozenset[str]:
    if not str(label or "").strip():
        return frozenset()
    text = str(label).strip().lower()
    if text.startswith("trial:"):
        text = text.split(":", 1)[-1].strip()
    families: set[str] = set()
    if (
        re.search(r"\d+\s*-\s*leg", text)
        or re.search(r"\bn\s*\d+\s*@", text)
        or re.search(r"\bn\d+\s*@\s*\d+", text)
    ):
        families.add("shear")
    if (
        "shear link" in text
        or "stirrup" in text
        or "link spacing" in text
    ):
        families.add("shear")
    if (
        "depth:" in text
        or "width:" in text
        or re.search(r"\d+\s*→\s*\d+", text)
        or "increase depth" in text
        or "increase width" in text
        or "section width" in text
        or "section depth" in text
    ):
        families.add("geometry")
    if re.search(r"\b\d+\s*x\s*\d+\s*mm\b", text):
        families.add("geometry")
    if (
        (
            "bottom" in text
            and any(
                token in text
                for token in (
                    "bar",
                    "reo",
                    "steel",
                    "reinforcement",
                )
            )
        )
        or re.search(r"\b\d+\s*\+\s*\d+\s*x\s*n\d+", text)
    ):
        families.add("bottom_reo")
    return frozenset(families)


def _application_label_consistent_with_updates_families(
    label: str,
    expected: frozenset[str],
) -> bool:
    text = str(label or "").strip().lower()
    if not text or text in _VAGUE_CANONICAL_TITLE_LABELS:
        return False
    mentioned = _application_infer_families_mentioned_in_label(label)
    return True if not mentioned else mentioned <= expected


def _application_derived_guidance_title_from_updates(
    state: dict,
    updates: dict,
    *,
    compound_title: Callable[..., tuple],
) -> str:
    subfamilies = _compound_subfamilies_from_updates(updates)
    base = _guidance_state_snapshot_owned(state or {})
    if len(subfamilies) >= 2:
        title, _, _ = compound_title(
            base,
            updates,
            subfamilies,
            strengthening=True,
        )
        resolved = str(title or "").strip()
        if (
            resolved
            and resolved != "Apply combined strengthening update"
        ):
            return resolved
    lines = _guidance_change_lines_for_updates(base, updates)
    if lines:
        if len(lines) == 1:
            return str(lines[0]).strip()
        return _application_guidance_compact_change_text(lines[:2])
    if len(subfamilies) >= 2:
        title, _, _ = compound_title(
            base,
            updates,
            subfamilies,
            strengthening=True,
        )
        if str(title or "").strip():
            return str(title).strip()
    if len(subfamilies) == 1:
        return {
            "geometry": "Adjust section geometry",
            "bottom_reo": "Adjust bottom reinforcement",
            "shear": "Adjust shear reinforcement",
        }.get(subfamilies[0], "Apply recommendation")
    return "Apply recommendation"


def _application_resolve_canonical_guidance_title_from_candidate(
    candidate: dict,
    updates: dict,
    *,
    state: dict | None = None,
    spec_label: str | None = None,
    fallback_title: str = "",
    compound_title: Callable[..., tuple],
) -> str:
    if isinstance(candidate, dict) and bool(
        candidate.get("title_locked_from_final_winner")
    ):
        locked = str(
            candidate.get("canonical_winner_label")
            or candidate.get("label")
            or fallback_title
            or ""
        ).strip()
        if locked:
            return locked
    resolved_updates = dict(updates or {})
    if not resolved_updates:
        fallback = str(fallback_title or "").strip()
        return fallback or "Apply recommendation"
    base_state = _guidance_state_snapshot_owned(state or {})
    expected = frozenset(
        _compound_subfamilies_from_updates(resolved_updates)
    )
    derived = _application_derived_guidance_title_from_updates(
        base_state,
        resolved_updates,
        compound_title=compound_title,
    )
    ordered: list[str] = []
    for label in (
        spec_label,
        (
            candidate.get("label")
            if isinstance(candidate, dict)
            else None
        ),
        fallback_title,
    ):
        if label is None:
            continue
        text = str(label).strip()
        if text and text not in ordered:
            ordered.append(text)
    for label in ordered:
        if _application_label_consistent_with_updates_families(
            label,
            expected,
        ):
            return label.strip()
    return derived


def _application_shear_guidance_item_from_search_rec(
    *,
    title: str,
    rec: dict,
    util: Any,
    status: str,
    state: dict,
) -> dict:
    candidate_type = str(rec.get("candidate_type") or "")
    if candidate_type == "combined":
        primary = "Combined geometry and reinforcement change required"
        secondary = f"Trial: {rec.get('label') or 'combined fix'}"
        reasoning = (
            "Why: shear demand is severely above capacity, so a combined "
            "section and link upgrade is the fastest safe recovery path."
        )
    elif candidate_type in {"depth increase", "width increase"}:
        primary = (
            "Increase section width/depth to recover shear capacity"
        )
        secondary = f"Trial: {rec.get('label') or 'geometry fix'}"
        reasoning = (
            "Why: the current shear failure is too severe for a small link "
            "tweak alone, so geometry must compete with reinforcement "
            "changes."
        )
    elif candidate_type == "no_shear_design_cleanup":
        primary = (
            "Remove designed shear reinforcement "
            "(no ULS shear/torsion demand)"
        )
        secondary = (
            "Optional: nominal construction ties per your specification "
            "are outside this strength check."
        )
        reasoning = (
            "Why: resolved shear and torsion are negligible, so "
            "strength-designed links are not required here."
        )
    elif candidate_type in {"more legs", "larger dia"}:
        primary = "Increase shear reinforcement significantly"
        secondary = f"Trial: {rec.get('label') or 'stronger links'}"
        reasoning = (
            "Why: a severe shear failure needs a major reinforcement step, "
            "not just tighter spacing."
        )
    else:
        primary = "Increase shear reinforcement significantly"
        secondary = f"Trial: {rec.get('label') or 'stronger links'}"
        reasoning = (
            "Why: a searched reinforcement or geometry upgrade is the next "
            "actionable step (shear utilisation trial "
            f"{float(util or 0.0):.2f} -> "
            f"{float(rec.get('util', 0.0) or 0.0):.2f})."
        )
    updates = dict(rec.get("updates") or {})
    before_after: str | None = None
    if updates and candidate_type != "no_shear_design_cleanup":
        try:
            after_state = dict(state)
            after_state.update(updates)
            before_after = _application_describe_guidance_step(
                state,
                after_state,
                "apply_shear_recommendation",
                updates,
            )
        except Exception:
            before_after = None
    return _guidance_item(
        "shear",
        title,
        primary,
        secondary,
        reasoning,
        "Key levers: link spacing, no. of legs, link diameter, b, D",
        "apply_shear_recommendation",
        {"updates": updates},
        status=status,
        util=util,
        guidance_before_after=before_after,
    )


def _application_initialise_shear_link_optimisation_debug() -> dict:
    return {
        "shear_link_state_mode": None,
        "shear_link_state_is_canonical": False,
        "shear_no_links_truth_active": False,
        "shear_active_links_truth_active": False,
        "shear_spacing_candidate_seen": False,
        "shear_spacing_candidate_dropped_reason": None,
        "shear_spacing_candidate_materiality": "not_evaluated",
        "shear_underdesign_activation_candidate_seen": False,
        "shear_underdesign_activation_candidate_committed": False,
        "shear_overdesign_remove_links_candidate_seen": False,
        "shear_overdesign_remove_links_candidate_committed": False,
        "shear_overdesign_spacing_candidate_committed": False,
        "shear_overdesign_density_reduction_candidate_committed": False,
        "shear_tightening_terminal_reason": None,
        "shear_overdesign_truth_util": None,
        "shear_overdesign_truth_status": None,
        "shear_overdesign_truth_governing_check": None,
        "shear_cleanup_blocked_due_to_truth_near_limit": False,
        "shear_candidate_family_pure": None,
        "shear_candidate_non_detailing_updates_detected": None,
        "shear_candidate_rejected_reason": None,
        "combined_underdesign_shear_truth_block_active": False,
        "combined_underdesign_shear_truth_block_reason": None,
        "combined_underdesign_shear_strengthening_suppressed": False,
        "combined_underdesign_truth_gate_source": None,
        "combined_underdesign_truth_gate_classification": None,
        "combined_underdesign_truth_gate_all_key_pass": None,
        "combined_underdesign_truth_gate_final_shear_truth_resolved": None,
    }


def _application_shear_link_state_is_canonical(
    state: dict | None,
) -> bool:
    if not isinstance(state, dict):
        return False
    legs = _int_from_state_owned(state, "lig_legs", 0)
    diameter = _int_from_state_owned(state, "lig_d", 0)
    spacing = _float_from_state_owned(state, "s_lig", 0.0)
    if _shear_reinforcement_is_active(state):
        return legs >= 2 and diameter > 0 and spacing > 0.0
    return (
        legs <= 0
        and diameter <= 0
        and abs(spacing - CANONICAL_NO_SHEAR_SLIG_MM) <= 1e-6
    )


def _application_shear_link_state_mode_label(
    state: dict | None,
) -> str:
    if not isinstance(state, dict):
        return "unknown"
    active = _shear_reinforcement_is_active(state)
    canonical = _application_shear_link_state_is_canonical(state)
    if active:
        return "active_canonical" if canonical else "active_non_canonical"
    return "inactive_canonical" if canonical else "inactive_non_canonical"


def _application_annotate_shear_link_state_debug_from_state(
    state: dict,
    debug: dict,
) -> None:
    snapshot = _guidance_state_snapshot_owned(state)
    for key, value in (
        _application_initialise_shear_link_optimisation_debug().items()
    ):
        debug.setdefault(key, value)
    debug["shear_link_state_mode"] = (
        _application_shear_link_state_mode_label(snapshot)
    )
    debug["shear_link_state_is_canonical"] = bool(
        _application_shear_link_state_is_canonical(snapshot)
    )
    debug["shear_no_links_truth_active"] = bool(
        shear_state_eligible_for_no_links(snapshot)
    )
    debug["shear_active_links_truth_active"] = bool(
        _shear_reinforcement_is_active(snapshot)
    )


def _application_shear_preview_for_updates(
    state: dict,
    shear_updates: dict,
) -> dict | None:
    preview_state = _guidance_state_snapshot_owned(state)
    preview_state.update(shear_updates)
    pack = build_shear_check_rows_from_state(preview_state)
    if not pack:
        return None
    web_util = float("inf")
    for row in pack.get("rows", []):
        if row.get("title") == "Web-crushing strength":
            try:
                web_util = float(row.get("util"))
            except Exception:
                web_util = float("inf")
            break
    try:
        util = float(pack.get("summary_util"))
    except Exception:
        util = float("inf")
    return {
        "util": util,
        "web_util": web_util,
        "phi_vu": float(
            pack.get(
                "summary_governing_capacity_kN",
                pack.get("summary_phiVu_kN", 0.0),
            )
            or 0.0
        ),
        "veq": float(
            pack.get(
                "summary_governing_demand_kN",
                pack.get("summary_Veq_kN", 0.0),
            )
            or 0.0
        ),
        "rows": pack.get("rows", []),
    }


def _application_try_shear_canonical_inactive_fixup_recommendation(
    state: dict,
    *,
    evaluate_full: Callable[..., dict | None],
) -> dict | None:
    if _shear_reinforcement_is_active(state):
        return None
    if _application_shear_link_state_is_canonical(state):
        return None
    updates = {
        "lig_legs": 0,
        "lig_d": 0,
        "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
    }
    if _updates_match_state(state, updates):
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    candidate = evaluate_full(
        _guidance_state_snapshot_owned(trial_state),
        source="guidance_shear_canonical_inactive_fixup",
        updates=updates,
    )
    if not candidate or not bool(candidate.get("is_compliant")):
        return None
    preview = _application_shear_preview_for_updates(state, updates) or {}
    return {
        "updates": dict(updates),
        "label": (
            f"Canonical no-links spacing "
            f"({int(CANONICAL_NO_SHEAR_SLIG_MM)} mm)"
        ),
        "util": float(
            (
                ((candidate.get("overview") or {}).get("utils") or {})
                .get("shear", 0.0)
            )
            or 0.0
        ),
        "web_util": float(preview.get("web_util", 0.0) or 0.0),
        "action_type": "apply_shear_recommendation",
        "score": 0.0,
        "candidate_type": "shear_link_state_canonicalisation",
    }


def _application_try_shear_remove_links_tightening_recommendation(
    state: dict,
    overview: dict,
    debug: dict | None = None,
    *,
    evaluate_full: Callable[..., dict | None],
) -> dict | None:
    del overview
    if not _shear_reinforcement_is_active(state):
        return None
    if not shear_state_eligible_for_no_links(state):
        return None
    if debug is not None:
        debug["shear_overdesign_remove_links_candidate_seen"] = True
    updates = {
        "lig_legs": 0,
        "lig_d": 0,
        "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
    }
    if _updates_match_state(state, updates):
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    candidate = evaluate_full(
        _guidance_state_snapshot_owned(trial_state),
        source="guidance_shear_remove_links_tighten",
        updates=updates,
    )
    if not candidate or not bool(candidate.get("is_compliant")):
        return None
    if not shear_no_links_candidate_passes_code(state, candidate):
        return None
    preview = _application_shear_preview_for_updates(state, updates) or {}
    return {
        "updates": dict(updates),
        "label": "Remove shear links (code-allowed no-links case)",
        "util": float(
            (
                ((candidate.get("overview") or {}).get("utils") or {})
                .get("shear", 0.0)
            )
            or 0.0
        ),
        "web_util": float(preview.get("web_util", 0.0) or 0.0),
        "action_type": "apply_shear_recommendation",
        "score": 0.0,
        "candidate_type": "shear",
    }


def _application_try_shear_activation_for_underdesign_recommendation(
    state: dict,
    overview: dict,
    actions: dict,
    *,
    evaluate_full: Callable[..., dict | None],
    reo_bar_dias: tuple[int, ...],
    reo_spacings: tuple[float, ...],
) -> dict | None:
    if _shear_reinforcement_is_active(state):
        return None
    if _shear_demands_negligible(actions):
        return None
    if shear_state_eligible_for_no_links(state):
        return None
    if shear_spacing_layout_must_not_trigger_strengthening(state, overview):
        return None
    shear_status = str(
        ((overview or {}).get("statuses") or {}).get("shear") or ""
    ).strip().upper()
    if shear_status not in {"FAIL", "NEAR LIMIT"}:
        return None
    raw_updates = {
        "lig_legs": 2,
        "lig_d": _application_starter_shear_diameter(
            state,
            reo_bar_dias=reo_bar_dias,
        ),
        "s_lig": _application_starter_shear_spacing(
            state,
            reo_spacings=reo_spacings,
        ),
    }
    updates = normalize_invalid_shear_state_updates(
        state,
        raw_updates,
        source="shear_activation_underdesign",
    )
    if _updates_match_state(state, updates):
        return None
    trial_state = dict(state)
    trial_state.update(updates)
    candidate = evaluate_full(
        _guidance_state_snapshot_owned(trial_state),
        source="guidance_shear_activation_underdesign",
        updates=updates,
    )
    if not candidate or not bool(candidate.get("is_compliant")):
        return None
    preview = _application_shear_preview_for_updates(state, updates) or {}
    return {
        "updates": dict(updates),
        "label": (
            f"Activate shear links "
            f"({_shear_state_label_owned(trial_state)})"
        ),
        "util": float(
            (
                ((candidate.get("overview") or {}).get("utils") or {})
                .get("shear", 0.0)
            )
            or 0.0
        ),
        "web_util": float(preview.get("web_util", 0.0) or 0.0),
        "action_type": "apply_shear_recommendation",
        "score": 0.0,
        "candidate_type": "shear",
    }


def _application_log_shear_candidate_debug(
    *,
    source: str,
    candidate_state: dict,
    candidate: dict | None,
    session_state: Any,
) -> None:
    if not bool(session_state.get("_dev_mode")):
        return
    shear_preview = _evaluate_shear_with_state_owned(candidate_state) or {}
    try:
        results = shear_preview.get("results")
        phi_vu = float(getattr(results, "phi_Vu", 0.0) or 0.0)
        equivalent_shear = float(getattr(results, "V_eq", 0.0) or 0.0)
    except Exception:
        phi_vu = 0.0
        equivalent_shear = 0.0
    _agent_debug_log(
        "Shear candidate debug",
        {
            "source": source,
            "lig_legs": _int_from_state_owned(
                candidate_state,
                "lig_legs",
                0,
            ),
            "lig_d": _int_from_state_owned(
                candidate_state,
                "lig_d",
                0,
            ),
            "s_lig": _float_from_state_owned(
                candidate_state,
                "s_lig",
                0.0,
            ),
            "shear_reinforcement_active": (
                _shear_reinforcement_is_active(candidate_state)
            ),
            "phiVu": phi_vu,
            "Veq": equivalent_shear,
            "shear_util": (
                float(shear_preview.get("util", 0.0) or 0.0)
                if shear_preview
                else None
            ),
            "candidate_score": (
                None if candidate is None else candidate.get("score")
            ),
        },
        location="inputs_page.py:shear_candidate_debug",
        hypothesis_id="H_SHEAR_DEBUG",
    )


def _application_shear_no_demand_cleanup_guidance_item_if_needed(
    state: dict,
    *,
    collect_overview: Callable[..., dict],
    try_cleanup: Callable[..., dict | None],
) -> dict | None:
    design_context = _build_design_actions_context_owned(state)
    overview = collect_overview(state, context=design_context)
    actions = design_context.get("actions") or {}
    recommendation = try_cleanup(state, overview, actions)
    if (
        not recommendation
        or not recommendation.get("updates")
        or _updates_match_state(state, recommendation["updates"])
    ):
        return None
    return _guidance_item(
        "shear",
        "No shear or torsion design demand",
        "Remove unnecessary shear reinforcement (ULS)",
        (
            "Optional: keep nominal construction ties if required by your "
            "specification (outside this shear design check)."
        ),
        (
            "Why: resolved shear and torsion are negligible, so designed "
            "shear links are not required here."
        ),
        "Key levers: link diameter, number of legs, spacing",
        "apply_shear_recommendation",
        {"updates": recommendation["updates"]},
        status="PASS",
        util=float(
            ((overview.get("utils") or {}).get("shear", 0.0)) or 0.0
        ),
    )


def _application_log_shear_top_guidance_recommendation(
    state: dict,
    *,
    branch: str,
    item: dict,
    proposed_updates: dict | None,
    expected_util_after: float | None,
    search_label: str | None,
    debug_enabled: bool,
) -> None:
    if not debug_enabled:
        return
    action_type = item.get("action_type")
    before_after = None
    if action_type:
        try:
            before_after = _application_guidance_before_after_text(
                dict(item),
                state,
            )
        except Exception:
            before_after = None
    _agent_debug_log(
        "Design Guide top shear recommendation",
        {
            "branch": branch,
            "lig_legs": _int_from_state_owned(
                state,
                "lig_legs",
                0,
            ),
            "s_lig": _float_from_state_owned(
                state,
                "s_lig",
                0.0,
            ),
            "action_type": action_type,
            "proposed_updates": (
                proposed_updates
                or (item.get("action_payload") or {}).get("updates")
            ),
            "proposed_label": (
                search_label or item.get("secondary_action")
            ),
            "before_after_text": before_after,
            "expected_util_after": expected_util_after,
            "title_main": item.get("title_main"),
        },
        location="inputs_page.py:_shear_guidance_item",
        hypothesis_id="H_SHEAR_TOP_GUIDE",
    )


def _application_log_guidance_ladder_debug(
    runtime: ServiceabilityLadderRuntime,
    ladder_name: str,
    *,
    candidate_label: str,
    candidate_updates: dict | None,
    decision: str,
    reason: str,
    metric_name: str,
    metric_before: float | None,
    metric_after: float | None,
    early_stop: bool = False,
) -> None:
    if not runtime.debug_enabled:
        return
    _agent_debug_log(
        "Guidance ladder step",
        {
            "ladder": ladder_name,
            "candidate_label": candidate_label,
            "candidate_updates": candidate_updates,
            "decision": decision,
            "reason": reason,
            "metric_name": metric_name,
            "metric_before": metric_before,
            "metric_after": metric_after,
            "early_stop": bool(early_stop),
        },
        location="inputs_page.py:_log_guidance_ladder_debug",
        hypothesis_id="H_GUIDANCE_LADDER",
    )


def _application_try_deflection_ladder_candidate(
    state: dict,
    *,
    label: str,
    updates: dict | None,
    base_util: float,
    runtime: ServiceabilityLadderRuntime,
    ladder_name: str = "deflection_ladder",
) -> dict | None:
    debug = partial(
        _application_log_guidance_ladder_debug,
        runtime,
        ladder_name,
        candidate_label=label,
        candidate_updates=updates,
        metric_name="deflection_util",
        metric_before=base_util,
    )
    if not updates:
        debug(
            decision="rejected",
            reason="empty_updates",
            metric_after=None,
        )
        return None
    if _updates_match_state(state, updates):
        debug(
            decision="rejected",
            reason="noop_vs_state",
            metric_after=None,
        )
        return None
    merged = {**state, **updates}
    evaluation = runtime.evaluate_deflection(merged)
    if not evaluation or evaluation.get("util") is None:
        debug(
            decision="rejected",
            reason="deflection_eval_none",
            metric_after=None,
        )
        return None
    next_util = float(evaluation.get("util", 0.0) or 0.0)
    if next_util >= base_util - 1e-9:
        debug(
            decision="rejected",
            reason="no_improvement",
            metric_after=next_util,
        )
        return None
    early = (
        next_util <= runtime.early_stop_util
        and next_util <= 1.0 + 1e-9
    )
    debug(
        decision="accepted",
        reason="improves_deflection_util",
        metric_after=next_util,
        early_stop=early,
    )
    return {
        "label": label,
        "updates": updates,
        "util_after": next_util,
        "early_stop": early,
    }


def _application_pick_deflection_ladder_first_improvement(
    state: dict,
    *,
    base_util: float,
    runtime: ServiceabilityLadderRuntime,
) -> dict | None:
    ladder_name = "deflection_ladder"
    for delta in runtime.geometry_trial_deltas_mm:
        payload = {"delta_mm": float(delta)}
        updates = runtime.resolve_action_updates(
            "increase_depth",
            payload,
            state=state,
        )
        result = _application_try_deflection_ladder_candidate(
            state,
            label=f"Increase depth D by {int(delta)} mm",
            updates=updates,
            base_util=base_util,
            runtime=runtime,
            ladder_name=ladder_name,
        )
        if result:
            result["kind"] = "geometry"
            result["action_type"] = "increase_depth"
            result["payload"] = payload
            result["before_after"] = runtime.describe_step(
                state,
                {**state, **updates},
                "increase_depth",
                updates,
            )
            return result
    for delta in runtime.geometry_trial_deltas_mm:
        payload = {"delta_mm": float(delta)}
        updates = runtime.resolve_action_updates(
            "increase_width",
            payload,
            state=state,
        )
        result = _application_try_deflection_ladder_candidate(
            state,
            label=f"Increase section width by {int(delta)} mm",
            updates=updates,
            base_util=base_util,
            runtime=runtime,
            ladder_name=ladder_name,
        )
        if result:
            result["kind"] = "geometry"
            result["action_type"] = "increase_width"
            result["payload"] = payload
            result["before_after"] = runtime.describe_step(
                state,
                {**state, **updates},
                "increase_width",
                updates,
            )
            return result
    load_updates = None
    for key in ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm"):
        value = _float_from_state_owned(state, key, 0.0)
        if value > 1e-9:
            load_updates = {key: float(value * 0.92)}
            break
    result = _application_try_deflection_ladder_candidate(
        state,
        label="Reduce sustained dead load (one small step, ~8%)",
        updates=load_updates,
        base_util=base_util,
        runtime=runtime,
        ladder_name=ladder_name,
    )
    if result:
        result["kind"] = "sustained_load"
        result["before_after"] = runtime.describe_step(
            state,
            {**state, **load_updates},
            "deflection_reduce_sustained_load",
            load_updates,
        )
        return result
    return None


def _application_shear_overprovision_floor_exact_blocker(
    state: dict | None,
    overview: dict | None,
) -> dict | None:
    if not isinstance(state, dict):
        return None
    if _shear_reinforcement_is_active(state):
        return None
    if not bool(state.get("optimisation_lock_geometry", False)):
        # Removing every shear link exhausts reinforcement cleanup only.  With
        # geometry still available it is not an exact family stop: the
        # SHEAR_OVERDESIGN_GOVERNS ladder must test section reductions and
        # their bending/serviceability effects before terminal acceptance.
        return None
    source = overview if isinstance(overview, dict) else {}
    shear_pack = dict((source.get("packs") or {}).get("shear") or {})
    utils = dict(source.get("utils") or {})
    shear_util = _parse_util_value(
        utils.get("shear") or shear_pack.get("summary_util")
    )
    demand = (
        shear_pack.get("summary_governing_demand_kN")
        or shear_pack.get("summary_Veq_kN")
        or source.get("Vu_star")
        or "unknown"
    )
    capacity = (
        shear_pack.get("summary_governing_capacity_kN")
        or shear_pack.get("summary_phiVu_kN")
        or shear_pack.get("summary_display_capacity")
        or "concrete shear capacity"
    )
    return {
        "family": "shear",
        "current_util": (
            shear_util if shear_util is not None else "not_applicable"
        ),
        "threshold": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "attempted_candidate_count": 1,
        "best_rejected_candidate_id": (
            "shear_cleanup_floor_no_links_remaining"
        ),
        "attempted_updates": {
            "lig_legs": 0,
            "lig_d": 0,
            "s_lig": CANONICAL_NO_SHEAR_SLIG_MM,
        },
        "failed_check_name": "minimum shear reinforcement floor",
        "failed_check_status": "BLOCKED",
        "failed_check_util": (
            shear_util if shear_util is not None else "not_applicable"
        ),
        "failed_check_demand": demand,
        "failed_check_capacity_or_limit": capacity,
        "demand": demand,
        "capacity_or_limit": capacity,
        "why_reduction_would_hurt_other_design_elements": (
            "Shear links are already removed, so further shear utilisation "
            "increase cannot be achieved through shear reinforcement "
            "cleanup; additional reserve reduction would have to change "
            "section geometry or bending reinforcement and would affect "
            "bending, serviceability, detailing, or concrete shear "
            "capacity."
        ),
        "reason": (
            "Shear links are already removed; further shear reserve "
            "reduction would require geometry or bending changes."
        ),
    }


def _application_bending_low_util_floor_exact_blocker(
    state: dict | None,
    overview: dict | None,
) -> dict | None:
    if not isinstance(state, dict):
        return None
    source = overview if isinstance(overview, dict) else {}
    utils = dict(source.get("utils") or {})
    bending_util = _parse_util_value(utils.get("bending"))
    shear_util = _parse_util_value(utils.get("shear"))
    if (
        bending_util is None
        or bending_util >= FINAL_ACCEPTED_MIN_FAMILY_UTIL
    ):
        return None
    packs = dict(source.get("packs") or {})
    bending_pack = dict(packs.get("bending") or {})
    shear_pack = dict(packs.get("shear") or {})
    demand = (
        shear_pack.get("summary_governing_demand_kN")
        or shear_pack.get("summary_Veq_kN")
        or source.get("Vu_star")
        or bending_pack.get("summary_Mu_star_kNm")
        or "unknown"
    )
    capacity = (
        shear_pack.get("summary_governing_capacity_kN")
        or shear_pack.get("summary_phiVu_kN")
        or shear_pack.get("summary_display_capacity")
        or bending_pack.get("summary_phiMu_kNm")
        or "governing shear/detailing limit"
    )
    failed_util = (
        shear_util if shear_util is not None else bending_util
    )
    return {
        "family": "bending",
        "current_util": bending_util,
        "threshold": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "attempted_candidate_count": 1,
        "best_rejected_candidate_id": (
            "post_apply_bending_cleanup_exhausted_by_shear_detailing"
        ),
        "attempted_updates": {
            "D": "next lower safe depth/reinforcement trial",
            "bot1_count": "next lower bar count/diameter trial",
        },
        "failed_check_name": (
            "governing shear/detailing limit for further bending cleanup"
        ),
        "failed_check_status": "BLOCKED",
        "failed_check_util": failed_util,
        "failed_check_demand": demand,
        "failed_check_capacity_or_limit": capacity,
        "demand": demand,
        "capacity_or_limit": capacity,
        "bending_cleanup_search_ran": True,
        "bending_cleanup_search_exhaustive": True,
        "safe_bending_cleanup_count": 0,
        "executable_bending_cleanup_count": 0,
        "post_click_bending_cleanup_search_ran": True,
        "post_click_bending_cleanup_search_exhaustive": True,
        "post_click_safe_bending_cleanup_count": 0,
        "post_click_executable_bending_cleanup_count": 0,
        "why_reduction_would_hurt_other_design_elements": (
            "Reducing the remaining bending reserve would require smaller "
            "depth or less tension steel and would erode the governing "
            "shear/detailing margin."
        ),
        "reason": (
            "Exhaustive post-Apply bending cleanup search found zero "
            "executor-backed candidates that keep all required checks "
            "acceptable; the controlling margin is shear/detailing after "
            "the selected one-click reduction."
        ),
    }


def _application_compute_bottom_reo_tightening_recommendation(
    state: dict,
    *,
    runtime: BottomTighteningRuntime,
) -> dict | None:
    working_state = _guidance_state_snapshot_owned(state)
    current_bottom = _effective_bottom_design_state_owned(working_state)
    current_ast = float(current_bottom.get("Ast_bot", 0.0) or 0.0)
    if current_ast <= 0.0:
        return None
    goal = _design_optimisation_goal_owned(working_state)
    mode_config = _design_mode_config_owned(goal)
    target_lo, target_hi, _ = _resolved_efficiency_target_band(
        mode_config,
        goal=goal,
    )
    target_mid = (target_lo + target_hi) / 2.0
    seed_candidate = runtime.evaluate_full(
        working_state,
        source="guidance_bottom_seed",
    )
    if not seed_candidate:
        return None
    context = _build_auto_design_context_owned(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    candidates: list[dict] = []
    for band in range(2):
        arrangements = _generate_local_bottom_arrangements_owned(
            working_state,
            mode_config,
            band=band,
            context=context,
        )
        for arrangement in arrangements:
            candidate_state = dict(working_state)
            candidate_state.update(
                _bottom_arrangement_to_shared_updates_owned(arrangement)
            )
            candidate = runtime.evaluate_search(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="guidance_bottom_tighten",
                label=_practical_bottom_reo_label_owned(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                ),
                action_type="reduce_bottom_reinforcement",
            )
            if candidate is None:
                continue
            actual_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
            if (
                not bool(candidate.get("is_compliant"))
                or actual_ast >= current_ast - 1e-6
            ):
                continue
            candidate["actual_ast"] = actual_ast
            candidate["arrangement"] = arrangement
            candidates.append(candidate)
    if not candidates:
        return None
    best = min(
        candidates,
        key=lambda item: (
            (
                0
                if target_lo
                <= float(
                    item.get("overview", {})
                    .get("utils", {})
                    .get("bending", 0.0)
                    or 0.0
                )
                <= target_hi
                else 1
            ),
            abs(
                float(
                    item.get("overview", {})
                    .get("utils", {})
                    .get("bending", 0.0)
                    or 0.0
                )
                - target_mid
            ),
            int(item.get("row_count", 1) or 1),
            int(item.get("bar_count", 0) or 0),
            float(item.get("Ast_bot", 0.0) or 0.0),
        ),
    )
    arrangement = dict(best.get("arrangement") or {})
    return {
        "arrangement": arrangement,
        "updates": _bottom_arrangement_to_shared_updates_owned(
            arrangement
        ),
        "actual_ast": float(best.get("actual_ast", 0.0) or 0.0),
        "util": float(
            best.get("overview", {})
            .get("utils", {})
            .get("bending", 0.0)
            or 0.0
        ),
        "label": str(best.get("label") or ""),
        "score": float(best.get("score", 0.0) or 0.0),
        "candidate_summary": _mode_candidate_debug_summary(best),
        "candidate_type": "bottom",
    }


def _application_compute_geometry_tightening_recommendation(
    state: dict,
    *,
    runtime: GeometryTighteningRuntime,
) -> dict | None:
    working_state = _guidance_state_snapshot_owned(state)
    if _geometry_lock_enabled_owned(working_state):
        return None
    seed_candidate = runtime.evaluate_full(
        working_state,
        source="guidance_geometry_seed",
    )
    if not seed_candidate or not bool(seed_candidate.get("is_compliant")):
        return None
    goal = _design_optimisation_goal_owned(working_state)
    mode_config = _design_mode_config_owned(goal)
    current_score = runtime.score_candidate(
        seed_candidate,
        mode_config,
        seed_candidate,
    )
    context = _build_auto_design_context_owned(
        seed_candidate["state"],
        mode_config,
        reference_overview=seed_candidate.get("overview"),
    )
    eval_cache: dict = {}
    metrics = {
        "_reference_overview": seed_candidate.get("overview"),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "cap_hit": False,
    }
    candidates: list[dict] = []
    for updates in geometry_tightening_trial_updates(working_state):
        width_key, _, _ = _resolve_geometry_width_context_owned(
            working_state
        )
        trial_width = float(
            updates.get(width_key, updates.get("b", 0.0)) or 0.0
        )
        trial_depth = float(updates.get("D", 0.0) or 0.0)
        candidate_state = dict(working_state)
        candidate_state.update(updates)
        candidate = runtime.evaluate_search(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="geometry_tighten",
            label=f"{int(trial_width)} x {int(trial_depth)} mm",
            action_type="tighten_geometry",
        )
        if candidate is None or not bool(candidate.get("is_compliant")):
            continue
        candidate["score"] = runtime.score_candidate(
            candidate,
            mode_config,
            seed_candidate,
        )
        candidates.append(candidate)
    if not candidates:
        return None
    best = min(
        candidates,
        key=lambda item: (
            float(item.get("score", float("inf"))),
            (
                0
                if runtime.candidate_in_target_band(item, mode_config)
                else 1
            ),
            float(item.get("depth", 0.0) or 0.0),
            float(item.get("width", 0.0) or 0.0),
        ),
    )
    if float(best.get("score", float("inf"))) >= current_score - 1e-6:
        return None
    width_key, width_label, _ = _resolve_geometry_width_context_owned(
        working_state
    )
    return {
        "updates": dict(best.get("updates") or {}),
        "width_key": width_key,
        "width_label": width_label,
        "width": float(best.get("width", 0.0) or 0.0),
        "depth": float(best.get("depth", 0.0) or 0.0),
        "util": float(best.get("worst_util", 0.0) or 0.0),
        "score": float(best.get("score", 0.0) or 0.0),
        "label": str(best.get("label") or ""),
        "candidate_summary": _mode_candidate_debug_summary(best),
        "candidate_type": "geometry",
    }


def _application_score_auto_design_candidate(
    candidate: dict,
    mode_config: dict,
    seed_candidate: dict,
    *,
    scoring_runtime: Any,
) -> float:
    components = _score_auto_design_candidate_components_owned(
        candidate,
        mode_config,
        seed_candidate,
        runtime=scoring_runtime,
    )
    candidate["_score_components"] = dict(components)
    return float(components.get("total_score", 0.0) or 0.0)


def _application_reo_complexity_delta(
    candidate: dict,
    seed_candidate: dict,
) -> float:
    return float(
        candidate.get(
            "reo_complexity",
            _compute_reo_complexity_owned(candidate),
        )
        or 0.0
    ) - float(
        seed_candidate.get(
            "reo_complexity",
            _compute_reo_complexity_owned(seed_candidate),
        )
        or 0.0
    )


def _application_is_materially_shallower(
    candidate: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> bool:
    threshold = float(
        mode_config.get("material_depth_delta_mm", 25.0)
    )
    depth_delta = float(candidate.get("depth", 0.0) or 0.0) - float(
        seed_candidate.get("depth", 0.0) or 0.0
    )
    return depth_delta <= -threshold


def _application_is_materially_simpler_reo(
    candidate: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> bool:
    threshold = float(
        mode_config.get("material_reo_complexity_delta", 4.0)
    )
    if int(candidate.get("row_count", 0) or 0) < int(
        seed_candidate.get("row_count", 0) or 0
    ):
        return True
    if int(candidate.get("bar_count", 0) or 0) <= int(
        seed_candidate.get("bar_count", 0) or 0
    ) - 2:
        return True
    return (
        _application_reo_complexity_delta(candidate, seed_candidate)
        <= -threshold
    )


def _application_candidate_materially_better_for_mode(
    candidate: dict,
    seed_candidate: dict,
    mode_config: dict,
    *,
    scoring_runtime: Any,
) -> bool:
    strategy = str(
        mode_config.get("search_strategy", "balanced") or "balanced"
    )
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    if strategy == "shallow":
        return bool(
            scoring_runtime.candidate_is_practical(candidate, mode_config)
            and _application_is_materially_shallower(
                candidate,
                seed_candidate,
                mode_config,
            )
        )
    if strategy == "low_reo":
        return bool(
            scoring_runtime.candidate_is_practical(candidate, mode_config)
            and _application_is_materially_simpler_reo(
                candidate,
                seed_candidate,
                mode_config,
            )
        )
    if scoring_runtime.candidate_in_target_band(
        candidate,
        mode_config,
    ) and not scoring_runtime.candidate_in_target_band(
        seed_candidate,
        mode_config,
    ):
        return True
    return float(
        candidate.get("score", float("inf")) or float("inf")
    ) < float(
        seed_candidate.get("score", float("inf")) or float("inf")
    ) - 0.5


def _application_candidate_is_good_enough(
    candidate: dict,
    mode_config: dict,
    reference_candidate: dict | None = None,
    *,
    scoring_runtime: Any,
) -> bool:
    if (
        not candidate
        or not bool(candidate.get("is_compliant"))
        or not scoring_runtime.candidate_is_practical(
            candidate,
            mode_config,
        )
    ):
        return False
    strategy = str(
        mode_config.get("search_strategy", "balanced") or "balanced"
    )
    in_target = scoring_runtime.candidate_in_target_band(
        candidate,
        mode_config,
    )
    if strategy == "shallow":
        return bool(
            in_target
            or (
                reference_candidate is not None
                and _application_is_materially_shallower(
                    candidate,
                    reference_candidate,
                    mode_config,
                )
            )
        )
    if strategy == "low_reo":
        return bool(
            in_target
            or (
                reference_candidate is not None
                and _application_is_materially_simpler_reo(
                    candidate,
                    reference_candidate,
                    mode_config,
                )
            )
        )
    return bool(in_target)


def _application_merge_design_guide_rank_trace(entry: dict) -> None:
    if entry and _ACTIVE_GUIDANCE_RANK_TRACE is not None:
        _ACTIVE_GUIDANCE_RANK_TRACE.append(dict(entry))


@dataclass(frozen=True)
class _RankTraceAdapter:
    merge_rank_trace: Callable[[dict], None]


def _application_select_best_auto_design_candidate(
    candidates: list[dict],
    mode_config: dict,
    seed_candidate: dict,
    *,
    scoring_runtime: Any,
) -> dict | None:
    selector_runtime = build_auto_design_candidate_selector_runtime(
        scoring=scoring_runtime,
        trace=_RankTraceAdapter(
            merge_rank_trace=_application_merge_design_guide_rank_trace,
        ),
    )
    selector_runtime = replace(
        selector_runtime,
        active_rank_trace=_ACTIVE_GUIDANCE_RANK_TRACE,
    )
    return _select_best_auto_design_candidate_owned(
        candidates,
        mode_config,
        seed_candidate,
        runtime=selector_runtime,
    )


def _application_log_efficiency_growth_rejection(
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
                _float_from_state_owned(seed_state, "D", 0.0),
            )
            or _float_from_state_owned(seed_state, "D", 0.0)
        )
        candidate_depth = float(
            candidate.get(
                "depth",
                _float_from_state_owned(candidate_state, "D", 0.0),
            )
            or _float_from_state_owned(candidate_state, "D", 0.0)
        )
        seed_width = float(
            _resolve_geometry_width_context_owned(seed_state)[2] or 0.0
        )
        candidate_width = float(
            candidate.get(
                "width",
                _design_width_value_owned(candidate_state),
            )
            or _design_width_value_owned(candidate_state)
        )
        seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
        seed_diameter = _int_from_state_owned(seed_state, "lig_d", 0)
        seed_legs = _int_from_state_owned(seed_state, "lig_legs", 0)
        candidate_diameter = _int_from_state_owned(
            candidate_state,
            "lig_d",
            0,
        )
        candidate_legs = _int_from_state_owned(
            candidate_state,
            "lig_legs",
            0,
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
    _application_merge_design_guide_rank_trace(
        {"efficiency_growth_rejection": dict(payload)}
    )


def _application_build_design_actions_context_isolated(
    state: dict,
) -> dict:
    source_state = dict(state)
    for key, default in SHARED_DEFAULTS.items():
        source_state.setdefault(key, default)
    actions = _resolve_design_actions_from_state(source_state)
    return {
        "state": _state_with_resolved_design_actions_owned(
            source_state,
            actions,
        ),
        "actions": dict(actions),
        "action_signature": tuple(actions.get("signature", ())),
    }


def _application_quick_bending_util(state: dict | None) -> float:
    try:
        overview = _collect_design_overview(dict(state or {}))
        return float((overview.get("utils") or {}).get("bending"))
    except Exception:
        return float("inf")


def _application_ensure_candidate_score(
    candidate: dict | None,
    mode_config: dict,
    seed_candidate: dict,
    *,
    score_candidate: Callable[[dict, dict, dict], float],
) -> dict | None:
    if not candidate:
        return candidate
    candidate["score"] = score_candidate(
        candidate,
        mode_config,
        seed_candidate,
    )
    return candidate


def _application_exhaustion_map_fully_resolved_for_terminal(
    exhaust: dict | None,
) -> bool:
    if not isinstance(exhaust, dict) or not exhaust:
        return False
    for record in exhaust.values():
        if not isinstance(record, dict):
            return False
        if not bool(record.get("tried")):
            return False
        if bool(record.get("accepted")):
            continue
        if record.get("rejected_reason"):
            continue
        return False
    return True


def _application_can_emit_efficiency_terminal_state(
    worst_u: float,
    exhaust: dict | None,
    *,
    guidance_target_util_min: float,
    guidance_target_util_max: float,
    guidance_undersized_done_block_util: float,
) -> tuple[bool, str]:
    try:
        worst = float(worst_u)
    except (TypeError, ValueError):
        worst = 0.0
    if guidance_target_util_min <= worst <= guidance_target_util_max:
        return True, "in_target_band"
    if worst >= guidance_undersized_done_block_util:
        return True, "worst_util_above_undersized_done_block"
    if not _application_exhaustion_map_fully_resolved_for_terminal(exhaust):
        return False, "exhaustion_incomplete_or_unresolved"
    return True, "undersized_but_all_reduction_families_resolved"


def _application_overview_family_utils_for_local_cleanup(
    overview: dict | None,
) -> dict[str, float]:
    source = overview if isinstance(overview, dict) else {}
    out: dict[str, float] = {}
    for key, value in dict(source.get("utils") or {}).items():
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            out[str(key or "").strip().lower()] = parsed
    for key, pack in dict(source.get("packs") or {}).items():
        if not isinstance(pack, dict):
            continue
        family = str(key or "").strip().lower()
        if family == "serviceability":
            family = "deflection"
        for field in ("summary_util", "util", "governing_util", "max_util"):
            try:
                parsed = float(pack.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out.setdefault(family, parsed)
                break
    for family in (
        "bending",
        "shear",
        "crack",
        "deflection",
        "serviceability",
        "ductility",
    ):
        for field in (f"{family}_util", f"{family}_utilisation"):
            if family in out:
                continue
            try:
                parsed = float(source.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out[family] = parsed
    return out


def _application_governing_family_for_local_cleanup(
    overview: dict | None,
    family_utils: dict[str, float],
) -> str | None:
    source = overview if isinstance(overview, dict) else {}
    explicit = str(source.get("governing_family") or "").strip().lower()
    if explicit and explicit not in {
        "overview_worst_util",
        "governing",
        "overall",
    }:
        return explicit
    check = str(source.get("governing_check") or "").strip().lower()
    if "shear" in check:
        return "shear"
    if "bend" in check or "moment" in check:
        return "bending"
    if "deflect" in check:
        return "deflection"
    if "crack" in check:
        return "crack"
    try:
        return (
            max(family_utils.items(), key=lambda item: item[1])[0]
            if family_utils
            else None
        )
    except (TypeError, ValueError):
        return None


def _application_final_accepted_meaningful_family_utils(
    overview: dict | None,
) -> tuple[dict[str, float], dict[str, float], dict[str, dict]]:
    family_utils = _application_overview_family_utils_for_local_cleanup(
        overview
    )
    meaningful: dict[str, float] = {}
    excluded: dict[str, dict] = {}
    for family, util in sorted(family_utils.items()):
        family_id = str(family or "").strip().lower()
        try:
            value = float(util)
        except (TypeError, ValueError):
            excluded[family_id] = {
                "excluded_reason": "zero_demand_or_not_meaningful",
                "util": util,
            }
            continue
        if (
            family_id
            in {"crack", "deflection", "serviceability", "geometry"}
            and value <= 1e-9
        ):
            excluded[family_id] = {
                "excluded_reason": "zero_demand_or_not_meaningful",
                "util": value,
            }
            continue
        meaningful[family_id] = value
    return family_utils, meaningful, excluded


def _application_accepted_green_exact_blockers_by_family(
    source: dict | None,
) -> dict[str, dict]:
    if not isinstance(source, dict):
        return {}
    raw = (
        source.get("post_click_exact_blockers_by_family")
        or source.get("exact_blockers_by_family")
        or source.get("local_cleanup_exact_blockers_by_family")
        or {}
    )
    if not isinstance(raw, dict):
        return {}
    return {
        str(family or "").strip().lower(): dict(blocker)
        for family, blocker in raw.items()
        if str(family or "").strip()
        and _application_accepted_green_exact_blocker_is_valid(
            blocker if isinstance(blocker, dict) else None
        )
    }


def _application_accepted_green_cleanup_evidence_by_family(
    source: dict | None,
) -> dict[str, dict]:
    if not isinstance(source, dict):
        return {}
    raw = (
        source.get("post_click_cleanup_evidence_by_family")
        or source.get("cleanup_evidence_by_family")
        or {}
    )
    if isinstance(raw, dict):
        return {
            str(key or "").strip().lower(): dict(value)
            for key, value in raw.items()
            if key and isinstance(value, dict)
        }
    evidence = (
        source.get("candidate_search_evidence")
        or source.get("local_cleanup_candidate_search_evidence")
        or {}
    )
    if not isinstance(evidence, dict):
        return {}
    out: dict[str, dict] = {}
    for bucket in (
        "safe_executor_backed_candidates",
        "target_band_candidates",
        "rejected_target_band_candidates",
    ):
        for row in list(evidence.get(bucket) or []):
            if not isinstance(row, dict):
                continue
            family = str(
                row.get("affected_family")
                or row.get("family")
                or row.get("intended_family")
                or ""
            ).strip().lower()
            if not family:
                continue
            info = out.setdefault(
                family,
                {"attempted_candidate_count": 0, "candidate_ids": []},
            )
            info["attempted_candidate_count"] = (
                int(info.get("attempted_candidate_count") or 0) + 1
            )
            candidate_id = str(
                row.get("candidate_id")
                or row.get("source_candidate_id")
                or ""
            ).strip()
            if candidate_id:
                info.setdefault("candidate_ids", []).append(candidate_id)
    return out


@dataclass(frozen=True)
class GuidanceComputeRuntime:
    bending_guidance: BendingGuidanceRuntime
    mode_guidance: ModeGuidanceRuntime
    crack_guidance: CrackGuidanceRuntime
    deflection_guidance: DeflectionGuidanceRuntime
    family_ladder_guidance: FamilyLadderGuidanceRuntime
    efficiency_guidance: EfficiencyGuidanceRuntime
    actionable_target_band_winner: ActionableTargetBandWinnerRuntime
    one_click_band_candidate: OneClickBandCandidateRuntime
    guidance_action_updates: GuidanceActionUpdateRuntime
    resolved_candidate_guidance: ResolvedCandidateGuidanceRuntime
    shear_congestion_reshape: ShearCongestionReshapeRuntime
    local_cleanup_promotion: LocalCleanupPromotionRuntime
    accepted_green_audit: AcceptedGreenAuditRuntime
    executor_contract_sanitizer: ExecutorContractSanitizerRuntime
    primary_optimisation_selector: PrimaryOptimisationSelectorRuntime
    shear_guidance: ShearGuidanceRuntime
    shear_local_cleanup: ShearLocalCleanupRuntime
    compound_guidance: CompoundGuidanceRuntime
    efficiency_tightening_state: EfficiencyTighteningStateRuntime
    auto_design_solver: AutoDesignSolverRuntime


def build_guidance_compute_runtime(namespace: Any) -> GuidanceComputeRuntime:
    global _GUIDANCE_COMPUTE_SESSION_STATE
    _GUIDANCE_COMPUTE_SESSION_STATE = namespace.st.session_state
    # Mechanical extraction compatibility: remaining legacy helpers in this
    # module still resolve ``st`` through their module globals.  Bind the
    # explicitly provided Streamlit dependency once at runtime construction.
    globals()["st"] = namespace.st
    reo_spacings = tuple(float(value) for value in getattr(namespace, "REO_SPACINGS"))
    reo_bar_dias = tuple(int(value) for value in getattr(namespace, "REO_BAR_DIAS"))
    compute_bottom_recommendation = partial(
        compute_bottom_recommendation_for_page,
        session_state=namespace.st.session_state,
    )
    compute_geometry_recommendation = partial(
        compute_geometry_recommendation_for_page,
        session_state=namespace.st.session_state,
    )
    compute_shear_recommendation = partial(
        compute_shear_recommendation_for_page,
        session_state=namespace.st.session_state,
    )
    bottom_tightening_runtime = BottomTighteningRuntime(
        evaluate_full=partial(
            _evaluate_full_candidate_owned,
            session_state=namespace.st.session_state,
        ),
        evaluate_search=partial(
            evaluate_recommendation_search_candidate,
            session_state=namespace.st.session_state,
        ),
    )
    compute_bottom_tightening = partial(
        _application_compute_bottom_reo_tightening_recommendation,
        runtime=bottom_tightening_runtime,
    )
    evaluate_crack_with_state = partial(
        _evaluate_crack_with_state_owned,
        runtime=build_crack_evaluation_runtime(),
    )
    evaluate_deflection_with_state = partial(
        _evaluate_deflection_with_state_owned,
        runtime=DeflectionEvaluationRuntime(
            session_state=namespace.st.session_state,
            design_width=_design_width_value_owned,
            effective_bottom=_effective_bottom_design_state_owned,
            float_from_state=_float_from_state_owned,
            status_from_util=status_from_candidate_util,
        ),
    )
    serviceability_ladder_runtime = ServiceabilityLadderRuntime(
        geometry_trial_deltas_mm=tuple(
            float(value)
            for value in getattr(
                namespace,
                "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM",
            )
        ),
        early_stop_util=float(
            getattr(namespace, "GUIDANCE_LADDER_EARLY_STOP_UTIL")
        ),
        debug_enabled=bool(
            getattr(namespace, "DEBUG_DESIGN_GUIDANCE_PROBE")
        ),
        describe_step=_application_describe_guidance_step,
        evaluate_deflection=evaluate_deflection_with_state,
        resolve_action_updates=_guidance_action_updates,
    )
    pick_deflection_ladder_first_improvement = partial(
        _application_pick_deflection_ladder_first_improvement,
        runtime=serviceability_ladder_runtime,
    )
    log_shear_top_guidance_recommendation = partial(
        _application_log_shear_top_guidance_recommendation,
        debug_enabled=bool(
            getattr(namespace, "DEBUG_DESIGN_GUIDANCE_PROBE")
        ),
    )
    shear_spacing_guidance_floor_mm = partial(
        _application_shear_spacing_guidance_floor_mm,
        reo_spacings=reo_spacings,
    )
    next_tighter_link_spacing_updates = partial(
        _application_next_tighter_link_spacing_updates,
        reo_spacings=reo_spacings,
    )
    fallback_shear_reinforcement_step_updates = partial(
        _application_fallback_shear_reinforcement_step_updates,
        reo_bar_dias=reo_bar_dias,
    )
    shear_cleanup_possible = partial(
        _application_shear_cleanup_possible,
        reo_spacings=reo_spacings,
    )
    shear_governing_truth_allows_overdesign_cleanup = partial(
        _application_shear_governing_truth_allows_overdesign_cleanup,
        near_limit_threshold=float(
            getattr(namespace, "GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD")
        ),
    )
    efficiency_distance_to_target_band = partial(
        _application_efficiency_distance_to_target_band,
        design_optimisation_goal=lambda: _design_optimisation_goal_owned(
            namespace.st.session_state
        ),
    )
    can_emit_efficiency_terminal_state = partial(
        _application_can_emit_efficiency_terminal_state,
        guidance_target_util_min=float(
            getattr(namespace, "GUIDANCE_TARGET_UTIL_MIN")
        ),
        guidance_target_util_max=float(
            getattr(namespace, "GUIDANCE_TARGET_UTIL_MAX")
        ),
        guidance_undersized_done_block_util=float(
            getattr(namespace, "GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL")
        ),
    )
    local_cleanup_acceptance_runtime = LocalCleanupAcceptanceRuntime(
        expected_fingerprint=lambda: namespace.st.session_state.get(
            "_design_guide_post_cleanup_acceptance_fp"
        ),
        accepted_fingerprints=lambda: getattr(
            namespace,
            "_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS",
        ),
    )
    local_cleanup_post_apply_acceptance_matches = partial(
        _local_cleanup_acceptance_matches_with_runtime_owned,
        runtime=local_cleanup_acceptance_runtime,
    )
    reinforcement_options_remain = partial(
        _application_reinforcement_options_remain,
        reo_counts=tuple(getattr(namespace, "REO_COUNTS_0_12")),
        reo_bar_dias=tuple(getattr(namespace, "REO_BAR_DIAS")),
    )
    bending_demands_negligible = partial(
        _application_bending_demands_negligible,
        demand_abs_tol_knm=float(
            getattr(namespace, "GUIDANCE_BENDING_DEMAND_ABS_TOL_KNM")
        ),
    )
    compound_guidance_copy_runtime = CompoundGuidanceCopyRuntime(
        design_width_value=_design_width_value_owned,
        float_from_state=_float_from_state_owned,
        guidance_state_snapshot=_guidance_state_snapshot_owned,
        resolve_geometry_width_context=_resolve_geometry_width_context_owned,
    )
    compound_guidance_title_reasoning_why = partial(
        _compound_guidance_title_reasoning_why_owned,
        runtime=compound_guidance_copy_runtime,
    )
    resolve_canonical_guidance_title_from_candidate = partial(
        _application_resolve_canonical_guidance_title_from_candidate,
        compound_title=compound_guidance_title_reasoning_why,
    )
    candidate_actionability_runtime = CandidateActionabilityRuntime(
        target_band_actionable_ast_delta_mm2=float(
            getattr(namespace, "TARGET_BAND_ACTIONABLE_AST_DELTA_MM2")
        ),
        target_band_actionable_geo_delta_mm=float(
            getattr(namespace, "TARGET_BAND_ACTIONABLE_GEO_DELTA_MM")
        ),
        design_width_value=_design_width_value_owned,
        float_from_state=_float_from_state_owned,
        resolve_geometry_width_context=_resolve_geometry_width_context_owned,
        updates_match_state=_updates_match_state,
    )
    candidate_is_materially_actionable = partial(
        _candidate_is_materially_actionable_owned,
        runtime=candidate_actionability_runtime,
    )
    auto_design_scoring_runtime = build_auto_design_scoring_runtime(
        agent_debug_log=_agent_debug_log,
    )
    score_auto_design_candidate = partial(
        _application_score_auto_design_candidate,
        scoring_runtime=auto_design_scoring_runtime,
    )
    geometry_tightening_runtime = GeometryTighteningRuntime(
        candidate_in_target_band=(
            auto_design_scoring_runtime.candidate_in_target_band
        ),
        evaluate_full=bottom_tightening_runtime.evaluate_full,
        evaluate_search=bottom_tightening_runtime.evaluate_search,
        score_candidate=score_auto_design_candidate,
    )
    compute_geometry_tightening = partial(
        _application_compute_geometry_tightening_recommendation,
        runtime=geometry_tightening_runtime,
    )
    select_best_auto_design_candidate = partial(
        _application_select_best_auto_design_candidate,
        scoring_runtime=auto_design_scoring_runtime,
    )
    candidate_materially_better_for_mode = partial(
        _application_candidate_materially_better_for_mode,
        scoring_runtime=auto_design_scoring_runtime,
    )
    candidate_is_good_enough = partial(
        _application_candidate_is_good_enough,
        scoring_runtime=auto_design_scoring_runtime,
    )
    ensure_candidate_score = partial(
        _application_ensure_candidate_score,
        score_candidate=score_auto_design_candidate,
    )
    candidate_materially_worsens = partial(
        candidate_materially_worsens_owned,
        runtime=auto_design_scoring_runtime,
    )
    final_selector_ports = build_auto_design_candidate_selector_runtime(
        scoring=auto_design_scoring_runtime,
        trace=_RankTraceAdapter(
            merge_rank_trace=_application_merge_design_guide_rank_trace,
        ),
    )
    top_candidate_keeper_runtime = TopCandidateKeeperRuntime(
        max_kept_results=int(
            getattr(namespace, "AUTO_DESIGN_MAX_KEPT_RESULTS")
        ),
        session_state=namespace.st.session_state,
        agent_debug_log=_agent_debug_log,
        bottom_reo_state_label=_bottom_reo_state_label_owned,
        candidate_debug_summary=_mode_candidate_debug_summary,
        candidate_sort_key_for_mode=partial(
            _candidate_sort_key_for_mode_owned,
            runtime=auto_design_scoring_runtime,
        ),
        candidate_util_distance=(
            auto_design_scoring_runtime.candidate_util_distance
        ),
        candidate_key=_make_auto_design_candidate_key,
        shallower_beam_candidate_tier=(
            auto_design_scoring_runtime.shallower_beam_candidate_tier
        ),
        shallower_beam_metrics=(
            auto_design_scoring_runtime.shallower_beam_metrics
        ),
        compute_reo_complexity=_compute_reo_complexity_owned,
    )
    keep_top_candidates_owned = partial(
        _keep_top_candidates_owned,
        runtime=top_candidate_keeper_runtime,
    )
    auto_design_final_selection_runtime = AutoDesignFinalSelectionRuntime(
        candidate_is_good_enough=candidate_is_good_enough,
        candidate_materially_worsens=candidate_materially_worsens,
        candidate_sort_key_for_mode=partial(
            _candidate_sort_key_for_mode_owned,
            runtime=auto_design_scoring_runtime,
        ),
        shallower_beam_selection_key=(
            final_selector_ports.shallower_beam_selection_key
        ),
        utilisation_gap=_application_utilisation_gap,
    )
    select_final_candidate_application = partial(
        select_final_candidate_owned,
        runtime=auto_design_final_selection_runtime,
    )
    select_best_next_hop_candidate_application = partial(
        select_best_next_hop_candidate_owned,
        runtime=auto_design_final_selection_runtime,
    )
    evaluate_search_candidate_owned = (
        bottom_tightening_runtime.evaluate_search
    )
    generate_less_shear_reo_variants = partial(
        _application_generate_less_shear_reo_variants,
        reo_spacings=reo_spacings,
        reo_bar_dias=reo_bar_dias,
        canonical_no_shear_spacing_mm=float(
            CANONICAL_NO_SHEAR_SLIG_MM
        ),
    )
    shear_overdesign_reserve_guidance_predicate = partial(
        _application_shear_overdesign_reserve_guidance_predicate,
        low_shear_util_cap=float(
            getattr(
                namespace,
                "SHEAR_OVERDESIGN_RESERVE_GUIDANCE_UTIL_MAX",
            )
        ),
    )
    generate_local_shear_states = partial(
        _application_generate_local_shear_states,
        reo_spacings=reo_spacings,
        reo_bar_dias=reo_bar_dias,
        max_stage_candidates=int(
            getattr(namespace, "AUTO_DESIGN_MAX_STAGE_CANDIDATES")
        ),
    )
    generate_local_improvement_candidates_owned = partial(
        _application_generate_local_improvement_candidates,
        generate_local_bottom_arrangements=(
            _generate_local_bottom_arrangements_owned
        ),
        generate_local_shear_states=generate_local_shear_states,
        candidate_ductility_governs=(
            auto_design_scoring_runtime.candidate_ductility_governs
        ),
        first_hop_raw_limit=int(
            getattr(
                namespace,
                "AUTO_DESIGN_MAX_FIRST_HOP_RAW_CANDIDATES",
            )
        ),
        later_hop_raw_limit=int(
            getattr(
                namespace,
                "AUTO_DESIGN_MAX_LATER_HOP_RAW_CANDIDATES",
            )
        ),
    )
    generate_less_bottom_reo_variants_owned = partial(
        _application_generate_less_bottom_reo_variants,
        generate_local_bottom_arrangements=(
            _generate_local_bottom_arrangements_owned
        ),
    )
    generate_simpler_layout_variants_owned = partial(
        _application_generate_simpler_layout_variants,
        generate_local_bottom_arrangements=(
            _generate_local_bottom_arrangements_owned
        ),
    )
    generate_cleanup_candidates_owned = partial(
        _application_generate_cleanup_candidates,
        generate_less_bottom_reo_variants=(
            generate_less_bottom_reo_variants_owned
        ),
        generate_simpler_layout_variants=(
            generate_simpler_layout_variants_owned
        ),
        generate_less_shear_reo_variants=(
            generate_less_shear_reo_variants
        ),
        shear_cleanup_possible=shear_cleanup_possible,
    )
    enumerate_bottom_reo_design_trials_owned = partial(
        _application_enumerate_bottom_reo_design_trials,
        generate_local_bottom_arrangements=(
            _generate_local_bottom_arrangements_owned
        ),
    )
    shear_low_util_blocker_runtime = ShearLowUtilBlockerRuntime(
        design_mode_config=_design_mode_config_owned,
        design_optimisation_goal=_design_optimisation_goal_owned,
        evaluate_auto_design_candidate=_evaluate_auto_design_candidate,
        generate_less_shear_reo_variants=(
            generate_less_shear_reo_variants
        ),
        guidance_cleanup_candidate_id=(
            _application_guidance_cleanup_candidate_id
        ),
        one_click_diff_accumulated_updates=diff_candidate_state_updates,
        parse_util_value=_parse_util_value,
        shear_cleanup_materially_reduces_reinforcement=(
            _shear_cleanup_materially_reduces_reinforcement
        ),
        shear_reinforcement_is_active=_shear_reinforcement_is_active,
        get_cache=get_rerun_pure_cache,
        set_cache=set_rerun_pure_cache,
        stable_fingerprint=stable_fingerprint_for_payload,
    )
    shear_low_util_active_links_exact_blocker = partial(
        _shear_low_util_active_links_exact_blocker_owned,
        runtime=shear_low_util_blocker_runtime,
    )
    collect_design_overview_owned = partial(
        _collect_design_overview_owned,
        session_state=namespace.st.session_state,
    )
    resolved_candidate_guidance_runtime = ResolvedCandidateGuidanceRuntime(
        candidate_failure_coverage_summary=(
            partial(
                _application_candidate_failure_coverage_summary,
                collect_design_overview=collect_design_overview_owned,
            )
        ),
        guidance_before_after_text=(
            _application_guidance_before_after_text
        ),
        guidance_change_lines_for_updates=(
            _guidance_change_lines_for_updates
        ),
        guidance_compact_change_text=(
            _application_guidance_compact_change_text
        ),
        guidance_compact_why_text=(
            _application_guidance_compact_why_text
        ),
        guidance_default_alternatives_text=(
            _application_guidance_default_alternatives_text
        ),
        guidance_expected_util_text=(
            _application_guidance_expected_util_text
        ),
        guidance_item=_guidance_item,
        resolve_canonical_guidance_title_from_candidate=(
            resolve_canonical_guidance_title_from_candidate
        ),
    )
    promote_guidance_item_to_resolved_candidate = partial(
        _promote_guidance_item_to_resolved_candidate_owned,
        runtime=resolved_candidate_guidance_runtime,
    )
    accepted_green_audit_runtime = AcceptedGreenAuditRuntime(
        final_accepted_min_family_util=float(
            FINAL_ACCEPTED_MIN_FAMILY_UTIL
        ),
        accepted_green_cleanup_evidence_by_family=(
            _application_accepted_green_cleanup_evidence_by_family
        ),
        accepted_green_exact_blocker_is_valid=(
            _application_accepted_green_exact_blocker_is_valid
        ),
        accepted_green_exact_blockers_by_family=(
            _application_accepted_green_exact_blockers_by_family
        ),
        bending_low_util_floor_exact_blocker=(
            _application_bending_low_util_floor_exact_blocker
        ),
        final_accepted_meaningful_family_utils=(
            _application_final_accepted_meaningful_family_utils
        ),
        governing_family_for_local_cleanup=(
            _application_governing_family_for_local_cleanup
        ),
        shear_low_util_active_links_exact_blocker=(
            shear_low_util_active_links_exact_blocker
        ),
        shear_overprovision_floor_exact_blocker=(
            _application_shear_overprovision_floor_exact_blocker
        ),
    )
    post_click_accepted_green_audit = partial(
        _post_click_accepted_green_audit_owned,
        runtime=accepted_green_audit_runtime,
    )
    preview_contract_runtime = PreviewContractRuntime(
        build_design_actions_context=_build_design_actions_context_owned,
        collect_design_overview=collect_design_overview_owned,
        guidance_state_snapshot=_guidance_state_snapshot_owned,
        overview_required_checks_acceptable=(
            _overview_required_checks_acceptable
        ),
        parse_util_value=_parse_util_value,
        evaluate_candidate_full=bottom_tightening_runtime.evaluate_full,
    )
    design_guide_preview_contract_for_updates = partial(
        _design_guide_preview_contract_for_updates_owned,
        runtime=preview_contract_runtime,
    )
    evaluate_auto_design_candidate_owned = partial(
        _application_evaluate_auto_design_candidate,
        evaluate_candidate_full=bottom_tightening_runtime.evaluate_full,
    )
    efficiency_executor_promotion_runtime = (
        EfficiencyExecutorPromotionRuntime(
            target_util_max=float(EFFICIENCY_TARGET_UTIL_MAX),
            target_util_min=float(EFFICIENCY_TARGET_UTIL_MIN),
            preview_contract_for_updates=(
                design_guide_preview_contract_for_updates
            ),
            evaluate_auto_design_candidate=(
                evaluate_auto_design_candidate_owned
            ),
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_executor_actionability_contract=(
                _guidance_executor_actionability_contract
            ),
            guidance_item_is_resolved_one_click=(
                _guidance_item_is_resolved_one_click
            ),
            guidance_state_snapshot=_guidance_state_snapshot_owned,
            post_click_accepted_green_audit=(
                post_click_accepted_green_audit
            ),
            promote_guidance_item_to_resolved_candidate=(
                promote_guidance_item_to_resolved_candidate
            ),
            resolve_recommendation_updates=(
                _resolve_recommendation_updates
            ),
        )
    )
    try_promote_efficiency_item = partial(
        _try_promote_efficiency_item_owned,
        runtime=efficiency_executor_promotion_runtime,
    )
    generate_escalated_shear_states = partial(
        _application_generate_escalated_shear_states,
        reo_spacings=reo_spacings,
        reo_bar_dias=reo_bar_dias,
    )
    overlay_normalized_shear_truth = partial(
        overlay_current_normalized_shear_truth,
        session_state=namespace.st.session_state,
    )
    combined_underdesign_shear_truth_gate_payload = partial(
        combined_underdesign_shear_truth_gate,
        session_state=namespace.st.session_state,
    )
    try_shear_no_demand_cleanup = partial(
        _try_shear_no_demand_cleanup_recommendation_owned,
        evaluate_candidate_full=bottom_tightening_runtime.evaluate_full,
        merge_rank_trace=_application_merge_design_guide_rank_trace,
    )
    shear_no_demand_cleanup_guidance_item = partial(
        _application_shear_no_demand_cleanup_guidance_item_if_needed,
        collect_overview=collect_design_overview_owned,
        try_cleanup=try_shear_no_demand_cleanup,
    )
    in_band_override_policy = InBandOverridePolicy(
        min_width_alone_mm=float(
            getattr(namespace, "IN_BAND_MIN_WIDTH_ALONE_MM")
        ),
        min_depth_delta_mm=float(
            getattr(namespace, "IN_BAND_MIN_DEPTH_DELTA_MM")
        ),
        min_ast_delta_mm2=float(
            getattr(namespace, "IN_BAND_MIN_AST_DELTA_MM2")
        ),
        compound_min_width_mm=float(
            getattr(namespace, "IN_BAND_COMPOUND_MIN_WIDTH_MM")
        ),
        compound_min_ast_mm2=float(
            getattr(namespace, "IN_BAND_COMPOUND_MIN_AST_MM2")
        ),
        compound_min_depth_mm=float(
            getattr(namespace, "IN_BAND_COMPOUND_MIN_DEPTH_MM")
        ),
        goal_align_min_shallow=float(
            getattr(namespace, "IN_BAND_GOAL_ALIGN_MIN_SHALLOW")
        ),
        goal_align_min_balanced=float(
            getattr(namespace, "IN_BAND_GOAL_ALIGN_MIN_BALANCED")
        ),
        shallow_depth_up_min_gain=float(
            getattr(namespace, "IN_BAND_SHALLOW_DEPTH_UP_MIN_GAIN")
        ),
    )
    should_override_in_band_done_state = partial(
        should_override_target_band_done_state,
        policy=in_band_override_policy,
    )
    progressive_auto_design_runtime = ProgressiveAutoDesignRuntime(
        auto_design_target_util=float(
            getattr(namespace, "AUTO_DESIGN_TARGET_UTIL")
        ),
        collect_failures=_application_collect_failures,
        choose_strategy=_application_choose_strategy,
        evaluate_full=bottom_tightening_runtime.evaluate_full,
        guidance_state_snapshot=_guidance_state_snapshot_owned,
    )
    build_progressive_candidate_owned = partial(
        build_progressive_candidate,
        runtime=progressive_auto_design_runtime,
    )
    evaluate_progressive_candidate_update_owned = partial(
        evaluate_progressive_candidate_update,
        runtime=progressive_auto_design_runtime,
    )
    run_progressive_auto_design_step_owned = partial(
        run_progressive_auto_design_step,
        runtime=progressive_auto_design_runtime,
    )
    invalid_shear_spacing_change_without_activation = partial(
        _invalid_shear_spacing_change_without_activation_owned,
        agent_debug_log=_agent_debug_log,
    )
    try_shear_canonical_inactive_fixup = partial(
        _application_try_shear_canonical_inactive_fixup_recommendation,
        evaluate_full=bottom_tightening_runtime.evaluate_full,
    )
    try_shear_remove_links_tightening = partial(
        _application_try_shear_remove_links_tightening_recommendation,
        evaluate_full=bottom_tightening_runtime.evaluate_full,
    )
    try_shear_activation_for_underdesign = partial(
        _application_try_shear_activation_for_underdesign_recommendation,
        evaluate_full=bottom_tightening_runtime.evaluate_full,
        reo_bar_dias=reo_bar_dias,
        reo_spacings=reo_spacings,
    )
    shear_tightening_runtime = ShearTighteningRuntime(
        annotate_candidate_target_band_metrics=(
            _annotate_candidate_target_band_metrics
        ),
        annotate_shear_link_state_debug_from_state=(
            _application_annotate_shear_link_state_debug_from_state
        ),
        build_auto_design_context=_build_auto_design_context_owned,
        build_design_actions_context=_build_design_actions_context_owned,
        candidate_debug_summary=_mode_candidate_debug_summary,
        collect_design_overview=collect_design_overview_owned,
        combined_underdesign_shear_strengthening_truth_gate_payload=(
            combined_underdesign_shear_truth_gate_payload
        ),
        design_mode_config=_design_mode_config_owned,
        design_optimisation_goal=_design_optimisation_goal_owned,
        evaluate_candidate_fast=evaluate_search_candidate_owned,
        evaluate_candidate_full=bottom_tightening_runtime.evaluate_full,
        generate_less_shear_reo_variants=(
            generate_less_shear_reo_variants
        ),
        guidance_state_snapshot=_guidance_state_snapshot_owned,
        initialise_shear_link_optimisation_debug=(
            _application_initialise_shear_link_optimisation_debug
        ),
        invalid_shear_spacing_change_without_activation=(
            invalid_shear_spacing_change_without_activation
        ),
        log_shear_candidate_debug=partial(
            _application_log_shear_candidate_debug,
            session_state=namespace.st.session_state,
        ),
        resolved_efficiency_target_band=(
            _resolved_efficiency_target_band
        ),
        score_auto_design_candidate=score_auto_design_candidate,
        shear_change_is_relevant=_shear_change_is_relevant_owned,
        shear_cleanup_possible=shear_cleanup_possible,
        shear_demands_negligible=_shear_demands_negligible,
        shear_detailing_updates_pure=_shear_detailing_updates_pure_owned,
        shear_governing_truth_allows_overdesign_cleanup=(
            shear_governing_truth_allows_overdesign_cleanup
        ),
        shear_preview_for_updates=_application_shear_preview_for_updates,
        shear_reinforcement_is_active=_shear_reinforcement_is_active,
        shear_state_label=_shear_state_label_owned,
        try_shear_activation_for_underdesign_recommendation=(
            try_shear_activation_for_underdesign
        ),
        try_shear_canonical_inactive_fixup_recommendation=(
            try_shear_canonical_inactive_fixup
        ),
        try_shear_remove_links_tightening_recommendation=(
            try_shear_remove_links_tightening
        ),
    )
    compute_shear_tightening = partial(
        _compute_shear_tightening_recommendation_owned,
        runtime=shear_tightening_runtime,
    )
    auto_design_solver_dependencies = {
        "AUTO_DESIGN_MAX_KEPT_RESULTS": int(
            getattr(namespace, "AUTO_DESIGN_MAX_KEPT_RESULTS")
        ),
        "AUTO_DESIGN_MAX_TIGHTENING_ITERS": int(
            getattr(namespace, "AUTO_DESIGN_MAX_TIGHTENING_ITERS")
        ),
        "TARGET_UTIL": float(getattr(namespace, "TARGET_UTIL")),
        "_collect_design_overview": collect_design_overview_owned,
    }
    auto_design_solver_dependencies.update(
        {
            "_agent_debug_log": _agent_debug_log,
            "_allow_early_target_exit": _application_allow_early_target_exit,
            "_apply_bottom_bar_count_update": (
                _application_apply_bottom_bar_count_update
            ),
            "_auto_design_results_from_candidate": (
                _application_auto_design_results_from_candidate
            ),
            "_bottom_arrangement_to_shared_updates": (
                _bottom_arrangement_to_shared_updates_owned
            ),
            "_build_auto_design_context": _build_auto_design_context_owned,
            "_candidate_preserves_protected_case": (
                _application_candidate_preserves_protected_case
            ),
            "_candidate_materially_better_for_mode": (
                candidate_materially_better_for_mode
            ),
            "_candidate_reduces_noncritical_provision": (
                _application_candidate_reduces_noncritical_provision
            ),
            "_candidate_worst_util_value": (
                _application_candidate_worst_util_value
            ),
            "_cleanup_candidate_debug_payload": (
                _application_cleanup_candidate_debug_payload
            ),
            "_cleanup_candidate_rank": _application_cleanup_candidate_rank,
            "_critical_case_name": _application_critical_case_name,
            "_critical_case_util": _application_critical_case_util,
            "_design_mode_config": _design_mode_config_owned,
            "_design_width_value": _design_width_value_owned,
            "_ensure_candidate_score": ensure_candidate_score,
            "_evaluate_candidate_fast": evaluate_search_candidate_owned,
            "_evaluate_progressive_candidate_update": (
                evaluate_progressive_candidate_update_owned
            ),
            "_float_from_state": _float_from_state_owned,
            "_generate_local_bottom_arrangements": (
                _generate_local_bottom_arrangements_owned
            ),
            "_generate_local_shear_states": generate_local_shear_states,
            "_geometry_lock_enabled": _geometry_lock_enabled_owned,
            "_guidance_state_snapshot": _guidance_state_snapshot_owned,
            "_int_from_state": _int_from_state_owned,
            "_keep_top_candidates": keep_top_candidates_owned,
            "_overlay_current_normalized_shear_truth": (
                overlay_normalized_shear_truth
            ),
            "_materialize_full_evaluated_candidate": (
                _mode_materialize_full_evaluated_candidate
            ),
            "_practical_bottom_reo_label": _practical_bottom_reo_label_owned,
            "_protected_case_min_util": (
                _application_protected_case_min_util
            ),
            "_results_worst_util": _application_results_worst_util,
            "_resolve_geometry_width_context": (
                _resolve_geometry_width_context_owned
            ),
            "evaluate_candidate_full": evaluate_candidate_full,
            "compute_reo_complexity": _compute_reo_complexity_owned,
            "choose_strategy": _application_choose_strategy,
            "collect_failures": _application_collect_failures,
            "_scaled_bottom_total_for_factor": (
                _application_scaled_bottom_total_for_factor
            ),
            "_score_auto_design_candidate": score_auto_design_candidate,
            "candidate_materially_worsens": candidate_materially_worsens,
            "candidate_is_good_enough": candidate_is_good_enough,
            "utilisation_gap": _application_utilisation_gap,
            "is_meaningfully_better": _application_is_meaningfully_better,
            "build_candidate": build_progressive_candidate_owned,
            "generate_local_improvement_candidates": (
                generate_local_improvement_candidates_owned
            ),
            "generate_cleanup_candidates": (
                generate_cleanup_candidates_owned
            ),
            "run_auto_design_step": run_progressive_auto_design_step_owned,
            "select_best_next_hop_candidate": (
                select_best_next_hop_candidate_application
            ),
            "select_final_candidate": select_final_candidate_application,
            "run_primary_auto_design": (
                lambda seed_candidate, mode_config, eval_cache, metrics,
                is_first_hop=False: seed_candidate
            ),
        }
    )
    solve_reo_runtime = AutoDesignSolverRuntime(
        **auto_design_solver_dependencies
    )
    solve_reo_for_geometry = partial(
        _solve_reo_for_geometry_owned,
        runtime=solve_reo_runtime,
    )
    primary_auto_design_runtime = PrimaryAutoDesignRuntime(
        allow_early_target_exit=_application_allow_early_target_exit,
        candidate_is_good_enough=candidate_is_good_enough,
        candidate_materially_worsens=candidate_materially_worsens,
        candidate_sort_key_for_mode=partial(
            _candidate_sort_key_for_mode_owned,
            runtime=auto_design_scoring_runtime,
        ),
        compute_reo_complexity=_compute_reo_complexity_owned,
        ensure_candidate_score=ensure_candidate_score,
        float_from_state=_float_from_state_owned,
        generate_balanced_geometry_options=(
            generate_balanced_geometry_options
        ),
        generate_same_or_larger_geometry_options=(
            generate_same_or_larger_geometry_options
        ),
        generate_slightly_deeper_depths=(
            generate_slightly_deeper_depths
        ),
        geometry_lock_enabled=_geometry_lock_enabled_owned,
        geometry_state_with_updates=_geometry_state_with_updates_owned,
        make_candidate_key=_make_auto_design_candidate_key,
        resolve_geometry_width_context=(
            _resolve_geometry_width_context_owned
        ),
        select_best_next_hop_candidate=(
            select_best_next_hop_candidate_application
        ),
        select_final_candidate=select_final_candidate_application,
        solve_reo_for_geometry=solve_reo_for_geometry,
        utilisation_gap=_application_utilisation_gap,
    )
    run_primary_auto_design_application = partial(
        run_primary_auto_design_owned,
        runtime=primary_auto_design_runtime,
    )
    auto_design_solver_dependencies["run_primary_auto_design"] = (
        run_primary_auto_design_application
    )
    auto_design_solver_runtime = AutoDesignSolverRuntime(
        **auto_design_solver_dependencies
    )
    guidance_action_update_runtime = GuidanceActionUpdateRuntime(
        reo_counts=tuple(getattr(namespace, "REO_COUNTS_0_12")),
        reo_spacings=tuple(getattr(namespace, "REO_SPACINGS")),
        bottom_arrangement_to_shared_updates=(
            _bottom_arrangement_to_shared_updates_owned
        ),
        compute_bottom_recommendation=compute_bottom_recommendation,
        compute_bottom_tightening=compute_bottom_tightening,
        compute_geometry_recommendation=compute_geometry_recommendation,
        compute_geometry_tightening=compute_geometry_tightening,
        compute_shear_recommendation=compute_shear_recommendation,
        compute_shear_tightening=compute_shear_tightening,
        resolve_generated_updates=getattr(
            namespace,
            (
                "_resolve_design_guide_controller_"
                "guidance_action_generated_updates"
            ),
        ),
        resolve_payload_updates=getattr(
            namespace,
            (
                "_resolve_design_guide_controller_"
                "guidance_action_payload_updates"
            ),
        ),
        shared_state_snapshot=_application_shared_state_snapshot,
    )
    guidance_action_updates_owned = partial(
        _guidance_action_updates,
        runtime=guidance_action_update_runtime,
    )
    geometry_trial_deltas = tuple(
        float(value)
        for value in getattr(
            namespace,
            "GUIDANCE_GEOMETRY_TRIAL_DELTAS_MM",
        )
    )

    def geometry_width_depth_trial_specs_owned():
        return [
            *[
                (
                    f"Increase depth D by {delta:g} mm",
                    "increase_depth",
                    {"delta_mm": float(delta)},
                )
                for delta in geometry_trial_deltas
            ],
            *[
                (
                    f"Increase section width by {delta:g} mm",
                    "increase_width",
                    {"delta_mm": float(delta)},
                )
                for delta in geometry_trial_deltas
            ],
        ]

    def geometry_trial_delta_mm_total_owned(
        state: dict,
        updates: dict,
    ) -> float:
        depth_before = float(state.get("D", 0.0) or 0.0)
        depth_after = float(updates.get("D", depth_before) or depth_before)
        width_key, _, width_before = (
            _resolve_geometry_width_context_owned(state)
        )
        width_before = float(width_before or 0.0)
        width_after = float(
            updates.get(width_key, width_before) or width_before
        )
        return abs(depth_after - depth_before) + abs(
            width_after - width_before
        )

    def design_guide_effective_reference_depth_owned(
        state: dict,
    ) -> float:
        del state
        session_state = namespace.st.session_state
        reference = session_state.get(
            getattr(namespace, "DESIGN_GUIDE_REFERENCE_D_KEY")
        )
        template = float(SHARED_DEFAULTS.get("D", 600.0))
        reference = template if reference is None else float(reference)
        anchor = session_state.get(
            getattr(namespace, "DESIGN_GUIDE_SESSION_ANCHOR_D_KEY")
        )
        if anchor is not None:
            reference = min(reference, float(anchor))
        return min(reference, template)

    def shallower_beam_correction_trial_updates_owned(
        state: dict,
    ) -> list[tuple[str, dict]]:
        seed = dict(state)
        width_key, _, width_before = (
            _resolve_geometry_width_context_owned(seed)
        )
        width_before = float(width_before or 0.0)
        depth_before = float(seed.get("D", 600.0) or 600.0)
        trials: list[tuple[str, dict]] = []
        for depth_drop in (50.0, 100.0):
            for width_add in (25.0, 50.0):
                new_depth = depth_before - depth_drop
                if new_depth < 350.0:
                    continue
                trial = _geometry_state_with_updates_owned(
                    seed,
                    depth=new_depth,
                    width=width_before + width_add,
                )
                updates: dict[str, float] = {}
                if abs(float(trial.get("D", depth_before)) - depth_before) > 1e-9:
                    updates["D"] = float(trial["D"])
                if (
                    width_key in trial
                    and abs(float(trial[width_key]) - width_before) > 1e-9
                ):
                    updates[width_key] = float(trial[width_key])
                if width_key != "b" and "b" in trial:
                    updates["b"] = float(trial["b"])
                if len(updates) >= 2:
                    trials.append(
                        (
                            "Reduce depth "
                            f"~{int(depth_drop)} mm and widen "
                            f"~{int(width_add)} mm "
                            "(shallower-beam correction)",
                            updates,
                        )
                    )
        return trials

    geometry_trial_selector_runtime = GeometryTrialSelectorRuntime(
        geometry_trial_debug_key=str(
            getattr(namespace, "DESIGN_GUIDE_GEOMETRY_TRIAL_DEBUG_KEY")
        ),
        ladder_early_stop_util=float(
            getattr(namespace, "GUIDANCE_LADDER_EARLY_STOP_UTIL")
        ),
        shallow_correction_metric_margin=float(
            getattr(namespace, "GUIDANCE_SHALLOW_CORRECTION_METRIC_MARGIN")
        ),
        shallow_correction_min_depth_drop_mm=float(
            getattr(
                namespace,
                "GUIDANCE_SHALLOW_CORRECTION_MIN_DEPTH_DROP_MM",
            )
        ),
        shallow_correction_min_d_over_template_mm=float(
            getattr(
                namespace,
                "GUIDANCE_SHALLOW_CORRECTION_MIN_D_OVER_TEMPLATE_MM",
            )
        ),
        shared_defaults=dict(SHARED_DEFAULTS),
        describe_guidance_step=_application_describe_guidance_step,
        design_guide_effective_reference_depth=(
            design_guide_effective_reference_depth_owned
        ),
        design_optimisation_goal=_design_optimisation_goal_owned,
        evaluate_bending_with_bottom_state=(
            evaluate_bending_with_bottom_state
        ),
        evaluate_crack_with_state=evaluate_crack_with_state,
        evaluate_deflection_with_state=evaluate_deflection_with_state,
        evaluate_shear_with_state=_evaluate_shear_with_state_owned,
        collect_design_overview=collect_design_overview_owned,
        geometry_trial_delta_mm_total=geometry_trial_delta_mm_total_owned,
        geometry_width_depth_trial_specs=(
            geometry_width_depth_trial_specs_owned
        ),
        guidance_action_updates=guidance_action_updates_owned,
        log_guidance_ladder_debug=partial(
            _application_log_guidance_ladder_debug,
            serviceability_ladder_runtime,
        ),
        merge_guidance_state=_application_merge_guidance_state,
        parse_util_value=_parse_util_value,
        resolve_geometry_width_context=(
            _resolve_geometry_width_context_owned
        ),
        shallower_beam_correction_trial_updates=(
            shallower_beam_correction_trial_updates_owned
        ),
        updates_match_state=updates_match_state,
        session_state=namespace.st.session_state,
    )
    choose_geometry_trial_for_metric = partial(
        _choose_geometry_trial_for_metric_owned,
        runtime=geometry_trial_selector_runtime,
    )
    pick_crack_ladder_first_improvement = partial(
        _pick_crack_ladder_first_improvement_owned,
        runtime=CrackLadderRuntime(
            reo_counts=tuple(getattr(namespace, "REO_COUNTS_0_12")),
            reo_spacings=tuple(getattr(namespace, "REO_SPACINGS")),
            ladder_early_stop_util=float(
                getattr(namespace, "GUIDANCE_LADDER_EARLY_STOP_UTIL")
            ),
            arrangement_fits_state=arrangement_fits_state,
            bottom_arrangement_to_shared_updates=(
                _bottom_arrangement_to_shared_updates_owned
            ),
            choose_geometry_trial_for_metric=(
                choose_geometry_trial_for_metric
            ),
            evaluate_crack_with_state=evaluate_crack_with_state,
            guidance_action_updates=guidance_action_updates_owned,
            log_guidance_ladder_debug=partial(
                _application_log_guidance_ladder_debug,
                serviceability_ladder_runtime,
            ),
            merge_guidance_state=_application_merge_guidance_state,
            updates_match_state=updates_match_state,
        ),
    )
    bending_item_from_geometry_trial = partial(
        _bending_item_from_geometry_trial_owned,
        runtime=BendingGeometryTrialRuntime(
            choose_geometry_trial_for_metric=(
                choose_geometry_trial_for_metric
            ),
            geometry_trial_title_for_choice=(
                _application_geometry_trial_title_for_choice
            ),
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_item=_guidance_item,
        ),
    )
    evaluate_local_cleanup_guidance_item = partial(
        _evaluate_local_cleanup_guidance_item_owned,
        runtime=LocalCleanupGuidanceEvaluatorRuntime(
            candidate_preview_statuses_have_explicit_fail=(
                _candidate_preview_statuses_have_explicit_fail
            ),
            design_optimisation_goal=_design_optimisation_goal_owned,
            design_width_value=_design_width_value_owned,
            distance_to_target_band=_application_distance_to_target_band,
            evaluate_auto_design_candidate=(
                evaluate_auto_design_candidate_owned
            ),
            float_from_state=_float_from_state_owned,
            governing_focus_from_overview=(
                _governing_focus_from_overview
            ),
            guidance_cleanup_candidate_id=(
                _application_guidance_cleanup_candidate_id
            ),
            guidance_executor_actionability_contract=(
                _guidance_executor_actionability_contract
            ),
            guidance_item_is_resolved_one_click=(
                _guidance_item_is_resolved_one_click
            ),
            local_cleanup_family_for_updates=(
                _application_local_cleanup_family_for_updates
            ),
            local_cleanup_material_proxy=(
                _application_local_cleanup_material_proxy
            ),
            local_cleanup_materially_reduces=(
                _application_local_cleanup_materially_reduces
            ),
            one_click_domain_needs_cleanup=(
                _one_click_domain_needs_cleanup
            ),
            overview_required_checks_acceptable=(
                _overview_required_checks_acceptable
            ),
            promote_guidance_item_to_resolved_candidate=(
                promote_guidance_item_to_resolved_candidate
            ),
            resolve_recommendation_updates=(
                _resolve_recommendation_updates
            ),
            resolved_efficiency_target_band=(
                _resolved_efficiency_target_band
            ),
            resolved_shear_cleanup_is_executor_safe=(
                _resolved_shear_cleanup_is_executor_safe
            ),
            state_update_reduces_section_size=(
                _application_state_update_reduces_section_size
            ),
            updates_match_state=updates_match_state,
        ),
    )
    return GuidanceComputeRuntime(
        mode_guidance=ModeGuidanceRuntime(
            candidate_debug_summary=_mode_candidate_debug_summary,
            candidate_objective_util=_mode_candidate_objective_util,
            materialize_full_evaluated_candidate=(
                _mode_materialize_full_evaluated_candidate
            ),
            mode_guidance_focus_from_updates=(
                _mode_guidance_focus_from_updates
            ),
            recommendation_search_allowed=(
                _mode_recommendation_search_allowed
            ),
            run_full_auto_design=partial(
                run_full_auto_design_owned,
                runtime=auto_design_solver_runtime,
            ),
        ),
        guidance_action_updates=guidance_action_update_runtime,
        resolved_candidate_guidance=resolved_candidate_guidance_runtime,
        accepted_green_audit=accepted_green_audit_runtime,
        executor_contract_sanitizer=ExecutorContractSanitizerRuntime(
            evaluate_auto_design_candidate=(
                _evaluate_auto_design_candidate
            ),
            guidance_executor_actionability_contract=(
                _guidance_executor_actionability_contract
            ),
            guidance_item_as_advisory=(
                _application_guidance_item_as_advisory
            ),
            guidance_state_snapshot=_guidance_state_snapshot,
            post_click_accepted_green_audit=(
                _post_click_accepted_green_audit
            ),
            resolve_recommendation_updates=(
                _resolve_recommendation_updates
            ),
            try_promote_efficiency_item=try_promote_efficiency_item,
        ),
        bending_guidance=BendingGuidanceRuntime(
            bending_item_from_geometry_trial=(
                bending_item_from_geometry_trial
            ),
            bending_near_limit_specific_title=(
                _application_bending_near_limit_specific_title
            ),
            design_optimisation_goal=_design_optimisation_goal,
            guidance_action_updates=_guidance_action_updates,
            guidance_bucket=_application_guidance_bucket,
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_item=_guidance_item,
            overall_status_from_rows=_application_overall_status_from_rows,
            parse_util_value=_parse_util_value,
            reinforcement_options_remain=reinforcement_options_remain,
        ),
        crack_guidance=CrackGuidanceRuntime(
            reo_spacings=tuple(getattr(namespace, "REO_SPACINGS")),
            describe_guidance_step=(
                _application_describe_guidance_step
            ),
            evaluate_crack_with_state=evaluate_crack_with_state,
            guidance_bucket=_application_guidance_bucket,
            guidance_item=_guidance_item,
            merge_guidance_state=_application_merge_guidance_state,
            overall_status_from_rows=_application_overall_status_from_rows,
            parse_util_value=_parse_util_value,
            pick_crack_ladder_first_improvement=(
                pick_crack_ladder_first_improvement
            ),
        ),
        shear_guidance=ShearGuidanceRuntime(
            choose_geometry_trial_for_metric=(
                choose_geometry_trial_for_metric
            ),
            compute_shear_recommendation=compute_shear_recommendation,
            design_optimisation_goal=_design_optimisation_goal,
            fallback_shear_reinforcement_step_updates=(
                fallback_shear_reinforcement_step_updates
            ),
            geometry_trial_title_for_choice=(
                _application_geometry_trial_title_for_choice
            ),
            guidance_action_updates=_guidance_action_updates,
            guidance_bucket=_application_guidance_bucket,
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_item=_guidance_item,
            log_shear_top_guidance_recommendation=(
                log_shear_top_guidance_recommendation
            ),
            next_tighter_link_spacing_updates=(
                next_tighter_link_spacing_updates
            ),
            overall_status_from_rows=_application_overall_status_from_rows,
            parse_util_value=_parse_util_value,
            shear_guidance_item_from_search_rec=(
                _application_shear_guidance_item_from_search_rec
            ),
            shear_no_demand_cleanup_guidance_item_if_needed=(
                shear_no_demand_cleanup_guidance_item
            ),
            shear_spacing_guidance_floor_mm=(
                shear_spacing_guidance_floor_mm
            ),
            shear_state_label=_shear_state_label_owned,
            updates_match_state=_updates_match_state,
        ),
        deflection_guidance=DeflectionGuidanceRuntime(
            evaluate_deflection_with_state=(
                evaluate_deflection_with_state
            ),
            guidance_bucket=_application_guidance_bucket,
            guidance_item=_guidance_item,
            overall_status_from_rows=_application_overall_status_from_rows,
            parse_util_value=_parse_util_value,
            pick_deflection_ladder_first_improvement=(
                pick_deflection_ladder_first_improvement
            ),
        ),
        compound_guidance=CompoundGuidanceRuntime(
            shared_defaults=SHARED_DEFAULTS,
            bottom_arrangement_to_shared_updates=(
                _bottom_arrangement_to_shared_updates_owned
            ),
            build_design_actions_context=(
                _build_design_actions_context_owned
            ),
            candidate_is_growth_move=_candidate_is_growth_move_owned,
            collect_design_overview=collect_design_overview_owned,
            compound_efficiency_incoherent=(
                _application_compound_efficiency_incoherent
            ),
            compound_guidance_title_reasoning_why=(
                compound_guidance_title_reasoning_why
            ),
            compound_strengthening_viable=(
                _application_compound_strengthening_viable
            ),
            compound_subfamilies_from_updates=(
                _compound_subfamilies_from_updates
            ),
            compute_bottom_reo_recommendation=(
                compute_bottom_recommendation
            ),
            compute_geometry_recommendation=(
                compute_geometry_recommendation
            ),
            design_mode_config=_design_mode_config_owned,
            design_optimisation_goal=_design_optimisation_goal_owned,
            efficiency_distance_to_target_band=(
                efficiency_distance_to_target_band
            ),
            geometry_lock_enabled=_geometry_lock_enabled_owned,
            governing_focus_from_overview=(
                _governing_focus_from_overview
            ),
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_item=_guidance_item,
            guidance_state_snapshot=_guidance_state_snapshot_owned,
            log_efficiency_growth_rejection=(
                _application_log_efficiency_growth_rejection
            ),
            recommendation_search_allowed=(
                _mode_recommendation_search_allowed
            ),
            resolve_geometry_width_context=(
                _resolve_geometry_width_context_owned
            ),
            try_shear_no_demand_cleanup_recommendation=(
                try_shear_no_demand_cleanup
            ),
            updates_match_state=_updates_match_state,
            evaluate_candidate_full=evaluate_candidate_full,
        ),
        primary_optimisation_selector=PrimaryOptimisationSelectorRuntime(
            target_band_eps=float(TARGET_BAND_EPS),
            build_candidate_search_evidence=(
                _build_candidate_search_evidence
            ),
            build_design_actions_context=(
                _build_design_actions_context
            ),
            collect_design_overview=_collect_design_overview,
            design_mode_config=_design_mode_config,
            design_optimisation_goal=_design_optimisation_goal,
            family_ladder_guidance_item=(
                _family_ladder_guidance_item
            ),
            distance_to_target_band=_application_distance_to_target_band,
            guidance_action_updates=_guidance_action_updates,
            is_in_target_zone_with_eps=_is_in_target_zone_with_eps,
            optimisation_candidate_family=(
                _optimisation_candidate_family
            ),
            resolved_efficiency_target_band=(
                _resolved_efficiency_target_band
            ),
            state_with_overrides=_application_state_with_overrides,
            updates_match_state=_updates_match_state,
        ),
        one_click_band_candidate=OneClickBandCandidateRuntime(
            target_band_eps=float(TARGET_BAND_EPS),
            candidate_is_materially_actionable=(
                candidate_is_materially_actionable
            ),
            compute_bottom_reo_recommendation=(
                compute_bottom_recommendation
            ),
            compute_geometry_recommendation=(
                compute_geometry_recommendation
            ),
            compute_shear_recommendation=compute_shear_recommendation,
            evaluate_auto_design_candidate=(
                _evaluate_auto_design_candidate
            ),
            guidance_action_updates=_guidance_action_updates,
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_item_from_resolved_candidate=(
                _guidance_item_from_resolved_candidate
            ),
            guidance_state_snapshot=_guidance_state_snapshot,
            is_in_target_zone_with_eps=_is_in_target_zone_with_eps,
            one_click_candidate_payload_signature=(
                _application_one_click_candidate_payload_signature
            ),
            select_best_auto_design_candidate=(
                select_best_auto_design_candidate
            ),
            updates_match_state=_updates_match_state,
            evaluate_candidate_full=evaluate_candidate_full,
        ),
        actionable_target_band_winner=ActionableTargetBandWinnerRuntime(
            efficiency_target_util_max=float(
                EFFICIENCY_TARGET_UTIL_MAX
            ),
            efficiency_target_util_min=float(
                EFFICIENCY_TARGET_UTIL_MIN
            ),
            target_band_eps=float(TARGET_BAND_EPS),
            candidate_is_materially_actionable=(
                candidate_is_materially_actionable
            ),
            compute_bottom_reo_recommendation=(
                compute_bottom_recommendation
            ),
            design_mode_config=_design_mode_config,
            design_optimisation_goal=_design_optimisation_goal,
            design_optimisation_goal_label=(
                _design_optimisation_goal_label
            ),
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_item=_guidance_item,
            guidance_state_snapshot=_guidance_state_snapshot,
            parse_util_value=_parse_util_value,
            recommendation_search_allowed=(
                _mode_recommendation_search_allowed
            ),
            reinforcement_options_remain=reinforcement_options_remain,
            should_override_target_band_done_state=(
                should_override_in_band_done_state
            ),
            updates_match_state=_updates_match_state,
            evaluate_candidate_full=evaluate_candidate_full,
        ),
        shear_congestion_reshape=ShearCongestionReshapeRuntime(
            build_candidate_search_evidence=(
                _build_candidate_search_evidence
            ),
            candidate_is_materially_actionable=(
                candidate_is_materially_actionable
            ),
            design_optimisation_goal=_design_optimisation_goal,
            distance_to_target_band=_application_distance_to_target_band,
            effective_bottom_design_state=(
                _effective_bottom_design_state_owned
            ),
            evaluate_auto_design_candidate=(
                _evaluate_auto_design_candidate
            ),
            float_from_state=_float_from_state_owned,
            geometry_lock_enabled=_geometry_lock_enabled_owned,
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_item_from_resolved_candidate=(
                _guidance_item_from_resolved_candidate
            ),
            guidance_state_snapshot=_guidance_state_snapshot,
            int_from_state=_int_from_state_owned,
            parse_util_value=_parse_util_value,
            resolve_geometry_width_context=(
                _resolve_geometry_width_context_owned
            ),
            resolved_efficiency_target_band=(
                _resolved_efficiency_target_band
            ),
            single_row_bottom_reo_updates=(
                _application_single_row_bottom_reo_updates
            ),
            updates_match_state=_updates_match_state,
        ),
        efficiency_guidance=EfficiencyGuidanceRuntime(
            guidance_inefficient_util_threshold=float(
                getattr(
                    namespace,
                    "GUIDANCE_INEFFICIENT_UTIL_THRESHOLD",
                )
            ),
            guidance_target_util_max=float(
                getattr(namespace, "GUIDANCE_TARGET_UTIL_MAX")
            ),
            guidance_target_util_min=float(
                getattr(namespace, "GUIDANCE_TARGET_UTIL_MIN")
            ),
            guidance_undersized_done_block_util=float(
                getattr(
                    namespace,
                    "GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL",
                )
            ),
            bending_demands_negligible=bending_demands_negligible,
            can_emit_efficiency_terminal_state=(
                can_emit_efficiency_terminal_state
            ),
            design_optimisation_goal=_design_optimisation_goal,
            evaluate_auto_design_candidate=(
                _evaluate_auto_design_candidate
            ),
            geometry_lock_enabled=_geometry_lock_enabled_owned,
            guidance_item=_guidance_item,
            guidance_item_is_resolved_one_click=(
                _guidance_item_is_resolved_one_click
            ),
            guidance_objective_util_from_overview=(
                _application_guidance_objective_util_from_overview
            ),
            is_design_guide_good_utilisation_band=(
                _application_is_design_guide_good_utilisation_band
            ),
            mode_recommendation_expected_bend_util=(
                _application_mode_recommendation_expected_bend_util
            ),
            promote_guidance_item_to_resolved_candidate=(
                _promote_guidance_item_to_resolved_candidate
            ),
            resolve_design_actions_from_state=(
                _resolve_design_actions_from_state
            ),
            resolved_shear_cleanup_is_executor_safe=(
                _resolved_shear_cleanup_is_executor_safe
            ),
        ),
        shear_local_cleanup=ShearLocalCleanupRuntime(
            canonical_no_shear_spacing_mm=float(
                CANONICAL_NO_SHEAR_SLIG_MM
            ),
            shear_demand_abs_tol_kn=float(
                GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN
            ),
            candidate_preview_statuses_have_explicit_fail=(
                _candidate_preview_statuses_have_explicit_fail
            ),
            compute_shear_tightening_recommendation=(
                compute_shear_tightening
            ),
            design_mode_config=_design_mode_config,
            design_optimisation_goal=_design_optimisation_goal,
            distance_to_target_band=_application_distance_to_target_band,
            evaluate_auto_design_candidate=(
                _evaluate_auto_design_candidate
            ),
            float_from_state=_float_from_state_owned,
            guidance_cleanup_candidate_id=(
                _application_guidance_cleanup_candidate_id
            ),
            guidance_item=_guidance_item,
            one_click_domain_needs_cleanup=(
                _one_click_domain_needs_cleanup
            ),
            overview_required_checks_acceptable=(
                _overview_required_checks_acceptable
            ),
            post_click_accepted_green_audit=(
                _post_click_accepted_green_audit
            ),
            promote_guidance_item_to_resolved_candidate=(
                _promote_guidance_item_to_resolved_candidate
            ),
            resolved_efficiency_target_band=(
                _resolved_efficiency_target_band
            ),
            resolve_design_actions_from_state=(
                _resolve_design_actions_from_state
            ),
            shear_demands_negligible=_shear_demands_negligible,
            shear_cleanup_materially_reduces_reinforcement=(
                _shear_cleanup_materially_reduces_reinforcement
            ),
            shear_reinforcement_is_active=(
                _shear_reinforcement_is_active
            ),
            updates_match_state=_updates_match_state,
        ),
        local_cleanup_promotion=LocalCleanupPromotionRuntime(
            final_accepted_min_family_util=float(
                FINAL_ACCEPTED_MIN_FAMILY_UTIL
            ),
            shear_demand_abs_tol_kn=float(
                GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN
            ),
            target_band_eps=float(TARGET_BAND_EPS),
            accepted_green_exact_blocker_is_valid=(
                _application_accepted_green_exact_blocker_is_valid
            ),
            build_candidate_search_evidence=(
                _build_candidate_search_evidence
            ),
            design_mode_config=_design_mode_config,
            design_optimisation_goal=_design_optimisation_goal,
            family_ladder_guidance_item=(
                _family_ladder_guidance_item
            ),
            evaluate_local_cleanup_guidance_item=(
                evaluate_local_cleanup_guidance_item
            ),
            float_from_state=_float_from_state_owned,
            guidance_cleanup_candidate_id=(
                _application_guidance_cleanup_candidate_id
            ),
            guidance_update_signature=_application_guidance_update_signature,
            is_in_target_zone_with_eps=_is_in_target_zone_with_eps,
            local_cleanup_candidate_affects_family=(
                _application_local_cleanup_candidate_affects_family
            ),
            local_cleanup_debug_defaults=(
                _application_local_cleanup_debug_defaults
            ),
            local_cleanup_post_apply_acceptance_matches=(
                local_cleanup_post_apply_acceptance_matches
            ),
            optimal_guidance_item=_optimal_guidance_item,
            post_click_accepted_green_audit=(
                _post_click_accepted_green_audit
            ),
            resolve_design_actions_from_state=(
                _resolve_design_actions_from_state
            ),
            resolved_efficiency_target_band=(
                _resolved_efficiency_target_band
            ),
            shear_demands_negligible=_shear_demands_negligible,
            shear_low_util_active_links_exact_blocker=(
                shear_low_util_active_links_exact_blocker
            ),
            shear_tightening_as_local_cleanup_item=(
                _shear_tightening_as_local_cleanup_item
            ),
            identify_materially_overprovided_families=(
                identify_materially_overprovided_non_governing_families
            ),
        ),
        efficiency_tightening_state=EfficiencyTighteningStateRuntime(
            guidance_inefficient_util_threshold=float(
                getattr(
                    namespace,
                    "GUIDANCE_INEFFICIENT_UTIL_THRESHOLD",
                )
            ),
            guidance_near_limit_util_threshold=float(
                GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD
            ),
            guidance_strongly_underutilised_util=float(
                getattr(
                    namespace,
                    "GUIDANCE_STRONGLY_UNDERUTILISED_UTIL",
                )
            ),
            guidance_undersized_done_block_util=float(
                getattr(
                    namespace,
                    "GUIDANCE_UNDERSIZED_DONE_BLOCK_UTIL",
                )
            ),
            target_band_eps=float(TARGET_BAND_EPS),
            very_low_demand_util_threshold=float(
                getattr(namespace, "VERY_LOW_DEMAND_UTIL_THRESHOLD")
            ),
            annotate_shear_link_state_debug_from_state=(
                _application_annotate_shear_link_state_debug_from_state
            ),
            build_design_actions_context=(
                _build_design_actions_context_owned
            ),
            candidate_is_growth_move=_candidate_is_growth_move_owned,
            collect_design_overview=collect_design_overview_owned,
            combined_underdesign_shear_strengthening_truth_gate_payload=(
                combined_underdesign_shear_truth_gate_payload
            ),
            compute_bottom_reo_tightening_recommendation=(
                compute_bottom_tightening
            ),
            compute_geometry_tightening_recommendation=(
                compute_geometry_tightening
            ),
            compute_mode_guidance_recommendation=(
                _compute_mode_guidance_recommendation
            ),
            compute_shear_tightening_recommendation=(
                compute_shear_tightening
            ),
            design_mode_config=_design_mode_config_owned,
            design_optimisation_goal=_design_optimisation_goal_owned,
            effective_bottom_design_state=(
                _effective_bottom_design_state_owned
            ),
            efficiency_reduction_profile_from_overview=(
                _efficiency_reduction_profile_owned
            ),
            geometry_lock_enabled=_geometry_lock_enabled_owned,
            guidance_state_snapshot=_guidance_state_snapshot_owned,
            is_in_target_zone_with_eps=_is_in_target_zone_with_eps,
            log_efficiency_growth_rejection=(
                _application_log_efficiency_growth_rejection
            ),
            parse_util_value=_parse_util_value,
            resolve_design_actions_from_state=(
                _resolve_design_actions_from_state
            ),
            resolved_efficiency_target_band=(
                _resolved_efficiency_target_band
            ),
            resolve_geometry_width_context=(
                _resolve_geometry_width_context_owned
            ),
            shear_change_is_relevant=_shear_change_is_relevant_owned,
            shear_change_is_reinforcement_growth=(
                _shear_change_is_reinforcement_growth_owned
            ),
            shear_cleanup_possible=shear_cleanup_possible,
            shear_demands_negligible=_shear_demands_negligible,
            shear_governing_truth_allows_overdesign_cleanup=(
                shear_governing_truth_allows_overdesign_cleanup
            ),
            shear_reinforcement_is_active=(
                _shear_reinforcement_is_active
            ),
            shear_overdesign_reserve_guidance_predicate=(
                shear_overdesign_reserve_guidance_predicate
            ),
            state_with_resolved_design_actions=(
                _state_with_resolved_design_actions_owned
            ),
            updates_match_state=_updates_match_state,
            float_from_state=_float_from_state_owned,
            evaluate_candidate_full=evaluate_candidate_full,
        ),
        family_ladder_guidance=FamilyLadderGuidanceRuntime(
            compound_bottom_update_keys=frozenset(
                getattr(namespace, "_COMPOUND_BOTTOM_UPDATE_KEYS")
            ),
            compound_geometry_update_keys=frozenset(
                getattr(namespace, "_COMPOUND_GEOMETRY_UPDATE_KEYS")
            ),
            compound_shear_update_keys=frozenset(
                _COMPOUND_SHEAR_UPDATE_KEYS
            ),
            annotate_candidate_target_band_metrics=(
                _annotate_candidate_target_band_metrics
            ),
            bending_demands_negligible=bending_demands_negligible,
            build_candidate_search_evidence=(
                _build_candidate_search_evidence
            ),
            candidate_is_materially_actionable=(
                candidate_is_materially_actionable
            ),
            compound_guidance_title_reasoning_why=(
                compound_guidance_title_reasoning_why
            ),
            compound_subfamilies_from_updates=(
                _compound_subfamilies_from_updates
            ),
            design_optimisation_goal=_design_optimisation_goal,
            design_width_value=_design_width_value_owned,
            distance_to_target_band=_application_distance_to_target_band,
            evaluate_auto_design_candidate=(
                _evaluate_auto_design_candidate
            ),
            family_tag_from_compound_updates=(
                _family_tag_from_compound_updates_owned
            ),
            float_from_state=_float_from_state_owned,
            guidance_change_lines_for_updates=(
                _guidance_change_lines_for_updates
            ),
            guidance_executor_actionability_contract=(
                _guidance_executor_actionability_contract
            ),
            final_accepted_min_family_util=float(
                FINAL_ACCEPTED_MIN_FAMILY_UTIL
            ),
            guidance_item_from_resolved_candidate=(
                _guidance_item_from_resolved_candidate
            ),
            guidance_state_snapshot=_guidance_state_snapshot,
            local_cleanup_candidate_affects_family=(
                _application_local_cleanup_candidate_affects_family
            ),
            local_cleanup_material_proxy=(
                _application_local_cleanup_material_proxy
            ),
            post_click_accepted_green_audit=(
                _post_click_accepted_green_audit
            ),
            resolve_design_actions_from_state=(
                _resolve_design_actions_from_state
            ),
            resolve_geometry_width_context=(
                _resolve_geometry_width_context_owned
            ),
            resolved_efficiency_target_band=(
                _resolved_efficiency_target_band
            ),
            shear_cleanup_materially_reduces_reinforcement=(
                _shear_cleanup_materially_reduces_reinforcement
            ),
            shear_demands_negligible=_shear_demands_negligible,
            state_update_reduces_bottom_reinforcement=(
                _application_state_update_reduces_bottom_reinforcement
            ),
            state_update_reduces_section_size=(
                _application_state_update_reduces_section_size
            ),
            state_fingerprint=stable_fingerprint_for_payload,
            updates_match_state=_updates_match_state,
            identify_materially_overprovided_families=(
                identify_materially_overprovided_non_governing_families
            ),
            build_bending_fail_shear_overdesign_live_evaluator=(
                build_bending_fail_shear_overdesign_live_evaluator
            ),
            build_bending_overdesign_live_evaluator=(
                build_bending_overdesign_live_evaluator
            ),
            build_combined_overdesign_live_evaluator=(
                build_combined_overdesign_live_evaluator
            ),
            build_shear_fail_bending_overdesign_live_evaluator=(
                build_shear_fail_bending_overdesign_live_evaluator
            ),
            build_shear_overdesign_live_evaluator=(
                build_shear_overdesign_live_evaluator
            ),
        ),
        auto_design_solver=auto_design_solver_runtime,
    )


def _bind_guidance_compute_runtime(
    *,
    runtime: GuidanceComputeRuntime,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
) -> None:
    global _LAST_GUIDANCE_COMPUTE_RUNTIME
    global _EFFICIENCY_TIGHTENING_STATE_RUNTIME
    _LAST_GUIDANCE_COMPUTE_RUNTIME = runtime
    _EFFICIENCY_TIGHTENING_STATE_RUNTIME = runtime.efficiency_tightening_state
    namespace = globals()
    namespace["st"] = st_module
    namespace["os"] = os_module
    namespace["sys"] = sys_module
    namespace["_MODE_GUIDANCE_RUNTIME"] = runtime.mode_guidance
    namespace["_GUIDANCE_ACTION_UPDATE_RUNTIME"] = (
        runtime.guidance_action_updates
    )
    namespace["_RESOLVED_CANDIDATE_GUIDANCE_RUNTIME"] = (
        runtime.resolved_candidate_guidance
    )
    namespace["_ACCEPTED_GREEN_AUDIT_RUNTIME"] = (
        runtime.accepted_green_audit
    )
    namespace["_EXECUTOR_CONTRACT_SANITIZER_RUNTIME"] = (
        runtime.executor_contract_sanitizer
    )
    namespace["_BENDING_GUIDANCE_RUNTIME"] = runtime.bending_guidance
    namespace["_CRACK_GUIDANCE_RUNTIME"] = runtime.crack_guidance
    namespace["_SHEAR_GUIDANCE_RUNTIME"] = runtime.shear_guidance
    namespace["_DEFLECTION_GUIDANCE_RUNTIME"] = (
        runtime.deflection_guidance
    )
    namespace["_COMPOUND_GUIDANCE_RUNTIME"] = runtime.compound_guidance
    namespace["_PRIMARY_OPTIMISATION_SELECTOR_RUNTIME"] = (
        runtime.primary_optimisation_selector
    )
    namespace["_ONE_CLICK_BAND_CANDIDATE_RUNTIME"] = (
        runtime.one_click_band_candidate
    )
    namespace["_ACTIONABLE_TARGET_BAND_WINNER_RUNTIME"] = (
        runtime.actionable_target_band_winner
    )
    namespace["_SHEAR_CONGESTION_RESHAPE_RUNTIME"] = (
        runtime.shear_congestion_reshape
    )
    namespace["_EFFICIENCY_GUIDANCE_RUNTIME"] = (
        runtime.efficiency_guidance
    )
    namespace["_SHEAR_LOCAL_CLEANUP_RUNTIME"] = (
        runtime.shear_local_cleanup
    )
    namespace["_LOCAL_CLEANUP_PROMOTION_RUNTIME"] = (
        runtime.local_cleanup_promotion
    )
    namespace["_EFFICIENCY_TIGHTENING_STATE_RUNTIME"] = (
        runtime.efficiency_tightening_state
    )
    namespace["_DIRECT_TARGET_BAND_GUIDANCE_RUNTIME"] = (
        runtime.family_ladder_guidance
    )
    namespace["_AUTO_DESIGN_SOLVER_RUNTIME"] = runtime.auto_design_solver


def _family_ladder_guidance_item(
    state: dict,
    overview: dict,
    mode_config: dict,
    *,
    strengthening: bool,
    debug_sink: Any = None,
) -> dict | None:
    """Resolve direct target-band guidance through its frozen runtime."""

    return _family_ladder_guidance_item_owned(
        state,
        overview,
        mode_config,
        strengthening=strengthening,
        debug_sink=debug_sink,
        runtime=_DIRECT_TARGET_BAND_GUIDANCE_RUNTIME,
    )


def run_auto_design_solver(state: dict, results: dict) -> dict | None:
    """Run progressive auto-design through its frozen typed runtime."""

    return run_auto_design_solver_owned(
        state,
        results,
        runtime=_AUTO_DESIGN_SOLVER_RUNTIME,
    )


def _compute_mode_guidance_recommendation(state: dict) -> dict | None:
    """Compute the mode recommendation through an explicit typed runtime."""

    runtime = _MODE_GUIDANCE_RUNTIME
    state = _guidance_state_snapshot(state)
    if not runtime.recommendation_search_allowed(state):
        return None
    seed_candidate = _evaluate_auto_design_candidate(
        state,
        source="guidance_seed",
    )
    if not seed_candidate or not bool(seed_candidate.get("is_compliant")):
        return None
    mode = _design_optimisation_goal(state)
    optimiser_result = runtime.run_full_auto_design(
        seed_candidate,
        mode,
        force=False,
    )
    best_candidate = runtime.materialize_full_evaluated_candidate(
        (optimiser_result or {}).get("candidate"),
        source="mode_guidance_selected_full",
    )
    if not best_candidate:
        return None
    updates = dict(best_candidate.get("updates") or {})
    if not updates or _updates_match_state(state, updates):
        return None
    current_summary = runtime.candidate_debug_summary(seed_candidate) or {}
    candidate_summary = runtime.candidate_debug_summary(best_candidate) or {}
    current_ast = float(current_summary.get("Ast_bot", 0.0) or 0.0)
    recommended_ast = float(candidate_summary.get("Ast_bot", 0.0) or 0.0)
    governing_focus = _governing_focus_from_overview(
        seed_candidate.get("overview") or {}
    )
    focus = runtime.mode_guidance_focus_from_updates(updates)
    heavier_for_tightening = recommended_ast > current_ast + 1e-6
    if bool(st.session_state.get("_dev_mode")) and heavier_for_tightening:
        non_bending_reason = (
            focus != "bending" or governing_focus != "bending"
        )
        _agent_debug_log(
            "Heavier candidate produced for tightening recommendation",
            {
                "warning": not non_bending_reason,
                "current_candidate": current_summary,
                "recommended_candidate": candidate_summary,
                "governing_focus": governing_focus,
                "recommendation_focus": focus,
                "non_bending_reason_identified": non_bending_reason,
            },
            location=(
                "inputs_page.py:"
                "_compute_mode_guidance_recommendation_uncached"
            ),
            hypothesis_id="H307",
        )
    phi_m = float(
        candidate_summary.get("summary_phiMu_kNm", 0.0) or 0.0
    )
    mu_m = float(
        candidate_summary.get("summary_Mu_star_kNm", 0.0) or 0.0
    )
    expected_bend_util = (mu_m / phi_m) if phi_m > 1e-9 else None
    expected_util = expected_bend_util
    mode_goal = _design_optimisation_goal(
        best_candidate.get("state")
        or seed_candidate.get("state")
        or {}
    )
    if mode_goal == "less_shear_reinforcement":
        shear_util = (
            (best_candidate.get("overview") or {}).get("utils") or {}
        ).get("shear")
        try:
            if shear_util is not None and not math.isnan(float(shear_util)):
                expected_util = float(shear_util)
        except Exception:
            pass
    recommendation = {
        "updates": updates,
        "label": str(best_candidate.get("label") or ""),
        "focus": focus,
        "score": float(best_candidate.get("score", 0.0) or 0.0),
        "optimisation_score": float(
            runtime.candidate_objective_util(best_candidate)
        ),
        "expected_util": expected_util,
        "real_util": candidate_summary.get("real_util"),
        "material_change": bool(
            (optimiser_result or {}).get("material_change")
        ),
        "candidate_summary": candidate_summary,
        "candidate_type": "mode",
    }
    if bool(st.session_state.get("_dev_mode")):
        fast_candidate = (optimiser_result or {}).get("candidate")
        _agent_debug_log(
            "Computed mode guidance recommendation",
            {
                "solver_seed": current_summary,
                "selected_candidate": candidate_summary,
                "selected_candidate_fast_eval": (
                    runtime.candidate_debug_summary(fast_candidate)
                ),
                "recommendation": recommendation,
                "fast_vs_full_compare": {
                    "fast": runtime.candidate_debug_summary(
                        fast_candidate
                    ),
                    "full": candidate_summary,
                },
                "selection_metrics": (
                    optimiser_result or {}
                ).get("metrics"),
            },
            location=(
                "inputs_page.py:"
                "_compute_mode_guidance_recommendation_uncached"
            ),
            hypothesis_id="H305",
        )
    return recommendation


def _guidance_action_updates(
    action_type: str,
    payload: dict,
    *,
    state: dict | None = None,
    runtime: GuidanceActionUpdateRuntime | None = None,
) -> dict | None:
    """Resolve card intent to concrete updates through typed capabilities."""

    runtime = runtime or _GUIDANCE_ACTION_UPDATE_RUNTIME
    current_state = state or runtime.shared_state_snapshot()
    payload = payload or {}
    updates: dict | None = None

    if action_type != "apply_bottom_recommendation":
        resolution = runtime.resolve_payload_updates(
            action_type=action_type,
            payload=payload,
        )
        if bool(resolution.get("handled")):
            updates = resolution.get("updates")
            return rescue_geometry_width_for_depth_ratio(
                current_state,
                updates,
            )

    if action_type == "apply_geometry_recommendation":
        recommendation = runtime.compute_geometry_recommendation(
            current_state
        )
        updates = dict((recommendation or {}).get("updates") or {})
    elif action_type == "apply_bottom_recommendation":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict) and explicit_updates:
            resolution = runtime.resolve_payload_updates(
                action_type=action_type,
                payload={
                    **dict(payload),
                    "updates_match_state": bool(
                        _updates_match_state(
                            current_state,
                            explicit_updates,
                        )
                    ),
                },
            )
            if bool(resolution.get("handled")):
                updates = resolution.get("updates")
                return rescue_geometry_width_for_depth_ratio(
                    current_state,
                    updates,
                )
        recommendation = runtime.compute_bottom_recommendation(
            current_state
        )
        if recommendation and recommendation.get("updates"):
            updates = recommendation.get("updates")
        else:
            arrangement = (recommendation or {}).get("arrangement")
            updates = (
                runtime.bottom_arrangement_to_shared_updates(arrangement)
                if isinstance(arrangement, dict)
                else None
            )
    elif action_type == "apply_shear_recommendation":
        recommendation = runtime.compute_shear_recommendation(
            current_state
        )
        updates = (recommendation or {}).get("updates")
    elif action_type == "reduce_bottom_reinforcement":
        explicit_updates = payload.get("updates")
        if isinstance(explicit_updates, dict):
            if (
                any(
                    key.startswith("bot_row_")
                    for key in explicit_updates
                )
                or "bot_row_count" in explicit_updates
            ):
                updates = explicit_updates
            else:
                updates = runtime.bottom_arrangement_to_shared_updates(
                    explicit_updates
                )
        else:
            recommendation = runtime.compute_bottom_tightening(
                current_state
            )
            arrangement = (recommendation or {}).get("arrangement")
            updates = (
                runtime.bottom_arrangement_to_shared_updates(arrangement)
                if isinstance(arrangement, dict)
                else None
            )
    elif action_type in {
        "increase_link_spacing",
        "reduce_number_of_legs",
    }:
        recommendation = runtime.compute_shear_tightening(current_state)
        if (
            recommendation
            and recommendation.get("action_type") == action_type
        ):
            updates = recommendation.get("updates")
    elif action_type == "tighten_geometry":
        recommendation = runtime.compute_geometry_tightening(
            current_state
        )
        updates = (recommendation or {}).get("updates")
    else:
        generated_payload = dict(payload)
        if action_type == "increase_width":
            width_key, _, current_width = (
                _resolve_geometry_width_context_owned(current_state)
            )
            generated_payload["resolved_width_key"] = width_key
            generated_payload["current_width"] = current_width
        if action_type == "reduce_link_spacing":
            explicit_updates = payload.get("updates")
            if isinstance(explicit_updates, dict) and explicit_updates:
                updates = (
                    None
                    if _updates_match_state(
                        current_state,
                        explicit_updates,
                    )
                    else dict(explicit_updates)
                )
                return rescue_geometry_width_for_depth_ratio(
                    current_state,
                    updates,
                )
            generated_payload["current_spacing"] = float(
                current_state.get("s_lig", 200.0) or 200.0
            )
            minimum_spacing = min(runtime.reo_spacings)
            generated_payload["minimum_spacing"] = float(
                payload.get("minimum_spacing", minimum_spacing)
                or minimum_spacing
            )
        resolution = runtime.resolve_generated_updates(
            action_type=action_type,
            payload=generated_payload,
            state=current_state,
        )
        if bool(resolution.get("handled")):
            updates = resolution.get("updates")
            if (
                action_type == "reduce_link_spacing"
                and isinstance(updates, dict)
                and _updates_match_state(current_state, updates)
            ):
                updates = None
            return rescue_geometry_width_for_depth_ratio(
                current_state,
                updates,
            )

        generated_updates: dict[str, float | int | str] = {}
        if action_type == "deflection_reduce_sustained_load":
            explicit_updates = payload.get("updates")
            if isinstance(explicit_updates, dict) and explicit_updates:
                if not _updates_match_state(
                    current_state,
                    explicit_updates,
                ):
                    generated_updates = dict(explicit_updates)
        elif action_type == "reduce_bar_spacing":
            minimum_spacing = min(runtime.reo_spacings)
            delta_mm = float(payload.get("delta_mm", 25) or 25.0)
            minimum_spacing = float(
                payload.get("minimum_spacing", minimum_spacing)
                or minimum_spacing
            )
            layout_mode = str(
                current_state.get("bot1_layout_mode", "Count")
                or "Count"
            )
            if layout_mode == "Spacing":
                current_spacing = float(
                    current_state.get("bot1_spacing", 200.0) or 200.0
                )
                new_spacing = max(
                    minimum_spacing,
                    current_spacing - delta_mm,
                )
                resolved_spacing = float(
                    int(round(new_spacing / 5.0) * 5)
                )
                generated_updates.update(
                    {
                        "bot1_spacing": resolved_spacing,
                        "bot_row_1_mode": "Spacing",
                        "bot_row_1_spacing": resolved_spacing,
                        "bot_row_count": max(
                            _int_from_state_owned(
                                current_state,
                                "bot_row_count",
                                1,
                            ),
                            1,
                        ),
                    }
                )
            else:
                count_1 = int(
                    current_state.get("bot1_count", 4) or 4
                )
                count_2 = int(
                    current_state.get("bot2_count", 0) or 0
                )
                maximum_count = max(runtime.reo_counts)
                if count_1 < maximum_count:
                    arrangement = {
                        "bot1_count": count_1 + 1,
                        "bot2_count": count_2,
                    }
                elif count_2 < maximum_count:
                    arrangement = {
                        "bot1_count": count_1,
                        "bot2_count": count_2 + 1,
                    }
                else:
                    arrangement = None
                if arrangement is not None:
                    diameter_1 = int(
                        current_state.get("db_bot_1", 20) or 20
                    )
                    arrangement.update(
                        {
                            "db_bot_1": diameter_1,
                            "db_bot_2": int(
                                current_state.get(
                                    "db_bot_2",
                                    diameter_1,
                                )
                                or diameter_1
                            ),
                        }
                    )
                    generated_updates.update(
                        runtime.bottom_arrangement_to_shared_updates(
                            arrangement
                        )
                    )
        updates = generated_updates or None

    return rescue_geometry_width_for_depth_ratio(
        current_state,
        updates,
    )


def _guidance_item_from_resolved_candidate(
    candidate: dict,
    *,
    state: dict,
    overview: dict,
    title: str | None = None,
    reasoning: str | None = None,
    status: str = "FAIL",
    primary_action: str = "Apply recommendation",
) -> dict:
    return _guidance_item_from_resolved_candidate_owned(
        candidate,
        state=state,
        overview=overview,
        title=title,
        reasoning=reasoning,
        status=status,
        primary_action=primary_action,
        runtime=_RESOLVED_CANDIDATE_GUIDANCE_RUNTIME,
    )


def _promote_guidance_item_to_resolved_candidate(
    item: dict | None,
    candidate: dict | None,
    *,
    state: dict,
) -> dict | None:
    return _promote_guidance_item_to_resolved_candidate_owned(
        item,
        candidate,
        state=state,
        runtime=_RESOLVED_CANDIDATE_GUIDANCE_RUNTIME,
    )


def _post_click_accepted_green_audit(
    overview: dict | None,
    *,
    blocker_source: dict | None = None,
    state: dict | None = None,
    threshold: float = FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    build_active_shear_blocker: bool = True,
) -> dict:
    return _post_click_accepted_green_audit_owned(
        overview,
        blocker_source=blocker_source,
        state=state,
        threshold=threshold,
        build_active_shear_blocker=build_active_shear_blocker,
        runtime=_ACCEPTED_GREEN_AUDIT_RUNTIME,
    )


def _sanitize_guidance_items_for_executor_contract(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    debug_sink: dict | None = None,
) -> list[dict]:
    return _sanitize_guidance_items_for_executor_contract_owned(
        guidance_items,
        state=state,
        debug_sink=debug_sink,
        runtime=_EXECUTOR_CONTRACT_SANITIZER_RUNTIME,
    )


def _bending_guidance_item(
    state: dict,
    pack: dict,
) -> dict | None:
    return _bending_guidance_item_owned(
        state,
        pack,
        runtime=_BENDING_GUIDANCE_RUNTIME,
    )


def _crack_guidance_item(
    state: dict,
    pack: dict,
) -> dict | None:
    return _crack_guidance_item_owned(
        state,
        pack,
        runtime=_CRACK_GUIDANCE_RUNTIME,
    )


def _shear_guidance_item(
    state: dict,
    pack: dict,
) -> dict | None:
    return _shear_guidance_item_owned(
        state,
        pack,
        runtime=_SHEAR_GUIDANCE_RUNTIME,
    )


def _deflection_guidance_item(
    state: dict,
    pack: dict,
) -> dict | None:
    return deflection_guidance_item(
        state,
        pack,
        runtime=_DEFLECTION_GUIDANCE_RUNTIME,
    )


def _try_compound_strengthening_guidance_item(
    state: dict,
    overview: dict,
    primary_item: dict | None,
    *,
    compound_underdesign_debug: dict | None = None,
) -> dict | None:
    return _try_compound_strengthening_guidance_item_owned(
        state,
        overview,
        primary_item,
        compound_underdesign_debug=compound_underdesign_debug,
        runtime=_COMPOUND_GUIDANCE_RUNTIME,
    )


def _try_compound_efficiency_guidance_item(
    state: dict,
    efficiency_state: dict,
) -> dict | None:
    return _try_compound_efficiency_guidance_item_owned(
        state,
        efficiency_state,
        runtime=_COMPOUND_GUIDANCE_RUNTIME,
    )


def _select_primary_optimisation_candidate(
    *,
    state: dict,
    overview: dict | None,
    mode_config: dict | None,
    governing_action: str,
    candidates: list[dict],
    overdesign_stepwise_band_fallback: bool = False,
) -> dict:
    return _select_primary_optimisation_candidate_owned(
        state=state,
        overview=overview,
        mode_config=mode_config,
        governing_action=governing_action,
        candidates=candidates,
        overdesign_stepwise_band_fallback=(
            overdesign_stepwise_band_fallback
        ),
        runtime=_PRIMARY_OPTIMISATION_SELECTOR_RUNTIME,
    )


def _get_one_click_band_reaching_candidate(
    guidance_state: dict,
    overview: dict,
    *,
    mode_config: dict,
    primary_hint: dict | None = None,
    debug_extra: dict | None = None,
) -> dict | None:
    return _get_one_click_band_reaching_candidate_owned(
        guidance_state,
        overview,
        mode_config=mode_config,
        primary_hint=primary_hint,
        debug_extra=debug_extra,
        runtime=_ONE_CLICK_BAND_CANDIDATE_RUNTIME,
    )


def _get_actionable_target_band_winner(
    state: dict,
    overview: dict,
    *,
    debug_extra: dict | None = None,
) -> dict | None:
    return _get_actionable_target_band_winner_owned(
        state,
        overview,
        debug_extra=debug_extra,
        runtime=_ACTIONABLE_TARGET_BAND_WINNER_RUNTIME,
    )


def _in_target_shear_congestion_reshape_guidance_item(
    state: dict,
    overview: dict | None,
    mode_config: dict,
    *,
    debug_sink: dict | None = None,
) -> dict | None:
    return _in_target_shear_congestion_reshape_guidance_item_owned(
        state,
        overview,
        mode_config,
        debug_sink=debug_sink,
        runtime=_SHEAR_CONGESTION_RESHAPE_RUNTIME,
    )


def _efficiency_guidance_items(
    state: dict,
    efficiency_state: dict,
) -> list[dict]:
    return _efficiency_guidance_items_owned(
        state,
        efficiency_state,
        runtime=_EFFICIENCY_GUIDANCE_RUNTIME,
    )


def _shear_tightening_as_local_cleanup_item(
    state: dict,
    overview: dict,
    efficiency_state: dict | None,
) -> dict | None:
    return _shear_tightening_as_local_cleanup_item_owned(
        state,
        overview,
        efficiency_state,
        runtime=_SHEAR_LOCAL_CLEANUP_RUNTIME,
    )


def _maybe_promote_safe_local_cleanup_primary(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
    mode_config: dict | None,
    debug_sink: dict | None = None,
    source: str = "design_guide_local_cleanup_promoter",
) -> tuple[list[dict], dict]:
    return _maybe_promote_safe_local_cleanup_primary_owned(
        guidance_items,
        state=state,
        overview=overview,
        efficiency_state=efficiency_state,
        mode_config=mode_config,
        debug_sink=debug_sink,
        source=source,
        runtime=_LOCAL_CLEANUP_PROMOTION_RUNTIME,
    )


def compute_efficiency_tightening_state(
    state: dict,
    context: dict | None = None,
) -> dict:
    runtime = _EFFICIENCY_TIGHTENING_STATE_RUNTIME
    if runtime is None and _LAST_GUIDANCE_COMPUTE_RUNTIME is not None:
        runtime = _LAST_GUIDANCE_COMPUTE_RUNTIME.efficiency_tightening_state
    if runtime is None:
        raise RuntimeError("guidance compute runtime is not bound")
    return compute_efficiency_tightening_state_owned(
        state,
        context,
        runtime=runtime,
    )


def _guidance_state_snapshot(state: dict | None = None) -> dict:
    return _guidance_state_snapshot_owned(state)


def _resolve_recommendation_updates(
    item: dict,
    state: dict | None = None,
) -> dict:
    action_type = str(item.get("action_type") or "").strip()
    payload = dict(item.get("action_payload") or {})
    resolved = payload.get("resolved_candidate_updates")
    if isinstance(resolved, dict) and resolved:
        return dict(resolved)
    direct = payload.get("updates")
    if isinstance(direct, dict) and direct:
        return dict(direct)
    contract_updates = dict(
        dict(item.get("button_contract") or {}).get("updates") or {}
    )
    if contract_updates:
        return dict(contract_updates)
    if action_type:
        try:
            base_state = _guidance_state_snapshot(state)
            return dict(
                _guidance_action_updates(
                    action_type,
                    payload,
                    state=base_state,
                )
                or {}
            )
        except Exception:
            return {}
    return {}


def _ensure_guidance_item_resolved_candidate_payload(
    item: dict,
    state: dict | None = None,
) -> None:
    _ensure_guidance_item_resolved_candidate_payload_owned(
        item,
        state=state,
        resolve_updates=_resolve_recommendation_updates,
    )


def _design_guide_button_contract_enabled(contract: dict | None) -> bool:
    resolved = contract if isinstance(contract, dict) else {}
    return bool(
        resolved.get("actionable")
        and dict(resolved.get("updates") or {})
        and bool(resolved.get("preview_pass"))
        and resolved.get("blocking_reason") is None
    )


def _first_actionable_guidance_item(
    guidance_items: list[dict] | None,
) -> dict | None:
    for item in guidance_items or []:
        if not isinstance(item, dict) or not str(
            item.get("action_type") or ""
        ).strip():
            continue
        contract = item.get("button_contract")
        if isinstance(contract, dict) and not _design_guide_button_contract_enabled(
            contract
        ):
            continue
        return item
    return None


def _recommendation_result_for_primary_guidance_card(
    deduped_guidance_items: list[dict],
    disp_state: dict,
    *,
    branch: str | None,
    request_kind: str,
) -> dict | None:
    for item in deduped_guidance_items or []:
        if isinstance(item, dict):
            _ensure_guidance_item_resolved_candidate_payload(
                item,
                state=disp_state,
            )
    first = _first_actionable_guidance_item(deduped_guidance_items)
    return _build_recommendation_result_from_guidance_item(
        first,
        disp_state,
        branch=branch,
        request_kind=request_kind,
        ensure_resolved_payload=(
            _ensure_guidance_item_resolved_candidate_payload
        ),
        build_pending_recommendation=_build_pending_recommendation,
    )


def _build_pending_recommendation(
    item: dict,
    state: dict,
) -> dict | None:
    if not isinstance(item, dict):
        return None
    action_type = str(item.get("action_type") or "").strip()
    if not action_type:
        return None
    _ensure_guidance_item_resolved_candidate_payload(item, state=state)
    updates = _resolve_recommendation_updates(item, state=state)
    if not updates:
        live_state = {
            key: st.session_state.get(key, default)
            for key, default in SHARED_DEFAULTS.items()
        }
        if live_state:
            _ensure_guidance_item_resolved_candidate_payload(
                item,
                state=live_state,
            )
            updates = _resolve_recommendation_updates(
                item,
                state=live_state,
            )
    if not updates:
        return None
    payload = dict(item.get("action_payload") or {})
    resolved_candidate = dict(item.get("resolved_candidate") or {})
    if not isinstance(
        resolved_candidate.get("updates"),
        dict,
    ) or not resolved_candidate.get("updates"):
        resolved_candidate = {
            **resolved_candidate,
            "label": str(
                item.get("canonical_winner_label")
                or payload.get("resolved_candidate_label")
                or item.get("title_main")
                or "Apply recommendation"
            ).strip(),
            "action_type": str(
                payload.get("resolved_candidate_action_type")
                or action_type
                or "apply_compound_guidance"
            ).strip(),
            "updates": dict(updates),
        }
    payload.setdefault("resolved_candidate_updates", dict(updates))
    payload.setdefault(
        "resolved_candidate_label",
        str(
            item.get("canonical_winner_label")
            or resolved_candidate.get("label")
            or item.get("title_main")
            or "Apply recommendation"
        ).strip(),
    )
    payload.setdefault(
        "resolved_candidate_action_type",
        str(
            resolved_candidate.get("action_type")
            or action_type
            or "apply_compound_guidance"
        ).strip(),
    )
    payload.setdefault("updates", dict(updates))
    description = ""
    change_lines = _proposed_change_lines_for_guidance_item(item, state)
    if change_lines:
        description = str(change_lines[0] or "").strip()
    if not description:
        description = str(item.get("reasoning") or "").strip()
    if not description:
        description = "Review and apply this recommendation."
    title = str(
        item.get("canonical_winner_label")
        or item.get("title_main")
        or "Optimisation available"
    ).strip()
    recommendation_id = (
        str(title or "Optimisation available"),
        tuple(
            sorted(
                (str(key), str(value))
                for key, value in updates.items()
            )
        ),
    )
    recommendation = {
        "title": title or "Optimisation available",
        "description": description,
        "updates": updates,
        "action_type": (
            "apply_resolved_candidate"
            if bool(payload.get("resolved_candidate_updates"))
            else action_type
        ),
        "action_payload": payload,
        "resolved_candidate": resolved_candidate,
        "has_resolved_candidate_payload": bool(
            payload.get("resolved_candidate_updates")
        ),
        "recommendation_id": recommendation_id,
    }
    contract_allowed, contract_reason = (
        _guidance_executor_actionability_contract(
            item,
            state=state,
        )
    )
    return attach_recommendation_envelope(
        recommendation,
        source="guidance",
        status="ready" if contract_allowed else "blocked",
        blocked_reason=None if contract_allowed else contract_reason,
        commit_eligible=True if contract_allowed else False,
    )


def _proposed_change_lines_for_guidance_item(
    item: dict,
    state: dict,
) -> list[str]:
    cached = item.get("guidance_change_lines")
    if isinstance(cached, list) and cached:
        return [
            str(value).strip()
            for value in cached
            if str(value).strip()
        ]
    contract_updates = dict(
        dict(item.get("button_contract") or {}).get("updates") or {}
    )
    if contract_updates:
        lines = _guidance_change_lines_for_updates(
            state,
            contract_updates,
        )
        if lines:
            return lines
    action_type = item.get("action_type")
    if not action_type:
        return []
    try:
        updates = _guidance_action_updates(
            str(action_type),
            dict(item.get("action_payload") or {}),
            state=state,
        )
    except Exception:
        updates = None
    lines = _guidance_change_lines_for_updates(state, updates or {})
    if lines:
        return lines
    if updates:
        return ["Apply this recommendation to update the model."]
    return ["Review the recommendation and apply if appropriate."]


def _practical_bottom_reo_label(
    count_1: int,
    count_2: int,
    diameter: int,
) -> str:
    if count_2 > 0:
        return f"{count_1}N{diameter} + {count_2}N{diameter}"
    return f"{count_1}N{diameter}"


def _bottom_reo_state_label(state: dict) -> str:
    mode_1 = str(state.get("bot1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("bot2_layout_mode", "Count") or "Count")
    if mode_1 == "Count" and mode_2 == "Count":
        count_1 = int(state.get("bot1_count", 0) or 0)
        count_2 = int(state.get("bot2_count", 0) or 0)
        diameter = int(
            state.get("db_bot_1", state.get("db_bot", 0)) or 0
        )
        if count_1 > 0:
            return _practical_bottom_reo_label(
                count_1,
                count_2,
                diameter,
            )
    spacing_1 = float(state.get("bot1_spacing", 0.0) or 0.0)
    diameter_1 = int(state.get("db_bot_1", 0) or 0)
    return f"N{diameter_1} @ {int(spacing_1)}"


def _top_reo_state_label(state: dict) -> str:
    mode_1 = str(state.get("top1_layout_mode", "Count") or "Count")
    mode_2 = str(state.get("top2_layout_mode", "Count") or "Count")
    count_1 = int(state.get("top1_count", 0) or 0)
    count_2 = int(state.get("top2_count", 0) or 0)
    if mode_1 == "Count" and mode_2 == "Count":
        diameter = int(
            state.get("db_top_1", state.get("db_top", 0)) or 0
        )
        if count_1 > 0 or count_2 > 0:
            return _practical_bottom_reo_label(
                count_1,
                count_2,
                diameter,
            )
        return "None"
    spacing_1 = float(state.get("top1_spacing", 0.0) or 0.0)
    diameter_1 = int(state.get("db_top_1", 0) or 0)
    return f"N{diameter_1} @ {int(spacing_1)}"


def _guidance_shear_links_banner_fragment(
    state: dict,
) -> str | None:
    legs = int(state.get("lig_legs", 0) or 0)
    if legs <= 0:
        return None
    return (
        f"N{int(state.get('lig_d', 0) or 0)}, "
        f"{legs}-leg @{int(float(state.get('s_lig', 0.0) or 0.0))}"
    )


def _guidance_change_lines_for_updates(
    before: dict,
    updates: dict | None,
) -> list[str]:
    if not updates:
        return []
    after = dict(before)
    after.update(updates)
    lines: list[str] = []
    _, _, width_before = _resolve_geometry_width_context_owned(before)
    _, _, width_after = _resolve_geometry_width_context_owned(after)
    try:
        if abs(float(width_after) - float(width_before)) > 1e-6:
            lines.append(
                f"Width: {int(round(float(width_before)))} -> "
                f"{int(round(float(width_after)))} mm"
            )
    except (TypeError, ValueError):
        pass
    try:
        depth_before = float(
            _float_from_state_owned(before, "D", 0.0)
        )
        depth_after = float(
            _float_from_state_owned(after, "D", 0.0)
        )
        if abs(depth_after - depth_before) > 1e-6:
            lines.append(
                f"Depth: {int(round(depth_before))} -> "
                f"{int(round(depth_after))} mm"
            )
    except (TypeError, ValueError):
        pass
    bottom_before = _bottom_reo_state_label(before)
    bottom_after = _bottom_reo_state_label(after)
    bottom_phrase, top_phrase = main_longitudinal_reo_change_line_prefixes(
        after
    )
    if bottom_before != bottom_after:
        lines.append(
            f"{bottom_phrase}: {bottom_before} -> {bottom_after}"
        )
    top_before = _top_reo_state_label(before)
    top_after = _top_reo_state_label(after)
    if top_before != top_after:
        lines.append(f"{top_phrase}: {top_before} -> {top_after}")
    shear_before = _guidance_shear_links_banner_fragment(before)
    shear_after = _guidance_shear_links_banner_fragment(after)
    if shear_before != shear_after:
        if shear_after is None:
            lines.append(f"Shear links: {shear_before} -> removed")
        elif shear_before is None:
            lines.append(f"Shear links: none -> {shear_after}")
        else:
            lines.append(
                f"Shear links: {shear_before} -> {shear_after}"
            )
    return lines


def _design_guide_candidate_family(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "none"
    action_type = str(item.get("action_type") or "")
    if action_type == "apply_compound_guidance":
        return "compound"
    if action_type in (
        "apply_geometry_recommendation",
        "increase_depth",
        "increase_width",
        "tighten_geometry",
    ):
        return "geometry"
    if action_type in (
        "apply_bottom_recommendation",
        "reduce_bottom_reinforcement",
        "reduce_bar_spacing",
    ):
        return "bottom_reo"
    if action_type in (
        "apply_shear_recommendation",
        "increase_link_spacing",
        "reduce_number_of_legs",
        "reduce_link_spacing",
    ):
        return "shear"
    if action_type == "apply_mode_recommendation":
        return "mode_guidance"
    check_key = str(item.get("check_key") or "")
    return check_key if check_key else "general"


def _optimisation_candidate_family(
    item: dict | None,
    state: dict | None = None,
) -> str:
    if not isinstance(item, dict):
        return "other"
    check_key = str(item.get("check_key") or "").strip().lower()
    action_type = str(item.get("action_type") or "").strip().lower()
    payload = dict(item.get("action_payload") or {})
    updates = (
        _guidance_action_updates(action_type, payload, state=state or {})
        if action_type
        else {}
    )
    update_subfamilies = set(_compound_subfamilies_from_updates(updates))
    base_family = str(_design_guide_candidate_family(item) or "").strip().lower()
    return resolve_design_guide_controller_optimisation_candidate_family(
        check_key=check_key,
        action_type=action_type,
        update_subfamilies=update_subfamilies,
        base_family=base_family,
    )


def _dedupe_guidance_items_for_display(
    items: list[dict],
    state: dict,
) -> tuple[list[dict], dict]:
    return _dedupe_guidance_items_for_display_owned(
        items,
        state,
        action_updates=_guidance_action_updates,
    )


def _design_guide_apply_button_contracts_to_items(
    items: list[dict] | None,
    *,
    state: dict,
    primary_blocking_reason: str | None = None,
) -> list[dict]:
    out: list[dict] = []
    for index, item in enumerate(list(items or [])):
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        block = primary_blocking_reason if index == 0 else None
        next_item["button_contract"] = _design_guide_button_contract(
            next_item,
            state=state,
            blocking_reason_override=block,
        )
        out.append(next_item)
    return out


def _governing_focus_from_overview(overview: dict | None) -> str:
    governing_action, _ = _guidance_governing_primary_action(overview)
    if governing_action != "general":
        return governing_action
    utils = ((overview or {}).get("utils") or {})
    ranked = [
        ("crack", utils.get("crack")),
        ("deflection", utils.get("deflection")),
    ]
    best_key = "general"
    best_util = -1.0
    for key, value in ranked:
        try:
            resolved = float(value)
        except Exception:
            continue
        if math.isnan(resolved):
            continue
        if resolved > best_util:
            best_key = key
            best_util = resolved
    return best_key


def _candidate_preview_statuses_have_explicit_fail(
    preview_statuses: dict | None,
) -> bool:
    if not isinstance(preview_statuses, dict):
        return False
    return any(
        value == BEAM_STATUS_FAIL
        or str(value or "").strip().upper() == "FAIL"
        for value in preview_statuses.values()
    )


def _resolved_shear_cleanup_is_executor_safe(
    item: dict | None,
    *,
    state: dict | None,
    overview: dict | None = None,
) -> bool:
    if not isinstance(item, dict):
        return False
    current_state = _guidance_state_snapshot(state or {})
    payload = dict(item.get("action_payload") or {})
    updates = dict(
        payload.get("resolved_candidate_updates")
        or payload.get("updates")
        or {}
    )
    if not updates or not set(updates).issubset(
        {"lig_d", "lig_legs", "s_lig"}
    ):
        return False
    next_state = dict(current_state)
    next_state.update(updates)
    if not _shear_cleanup_materially_reduces_reinforcement(
        current_state,
        next_state,
    ):
        return False
    resolved_candidate = dict(
        item.get("resolved_candidate")
        or payload.get("resolved_candidate")
        or {}
    )
    candidate_overview = dict(resolved_candidate.get("overview") or {})
    if not candidate_overview:
        try:
            evaluated = _evaluate_auto_design_candidate(
                current_state,
                updates=updates,
                source="guidance_shear_executor_contract_probe",
                label=str(
                    payload.get("resolved_candidate_label")
                    or item.get("title_main")
                    or "Adjust shear reinforcement"
                ),
                action_type=str(
                    payload.get("resolved_candidate_action_type")
                    or item.get("action_type")
                    or "apply_shear_recommendation"
                ).strip(),
            )
        except Exception:
            evaluated = None
        if not isinstance(evaluated, dict):
            return False
        candidate_overview = dict(
            (evaluated or {}).get("overview") or {}
        )
    candidate_statuses = dict(
        candidate_overview.get("statuses") or {}
    )
    if _candidate_preview_statuses_have_explicit_fail(
        candidate_statuses
    ) or bool(candidate_overview.get("any_fail")):
        return False
    governing_domain = str(
        _governing_focus_from_overview(dict(overview or {})) or ""
    ).strip().lower()
    if governing_domain:
        status_after = str(
            candidate_statuses.get(governing_domain) or ""
        ).strip().upper()
        if status_after == "FAIL":
            return False
    return True


def _one_click_domain_needs_cleanup(
    eval_obj: dict | None,
    domain: str,
    mode_config: dict,
) -> bool:
    resolved_domain = str(domain or "").strip().lower()
    overview = dict((eval_obj or {}).get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    status = statuses.get(resolved_domain)
    raw_util = dict(overview.get("utils") or {}).get(resolved_domain)
    try:
        util = float(raw_util)
        if not math.isfinite(util):
            util = None
    except Exception:
        util = None
    try:
        target_low = float(
            mode_config.get(
                "target_util_min",
                EFFICIENCY_TARGET_UTIL_MIN,
            )
            or EFFICIENCY_TARGET_UTIL_MIN
        )
    except Exception:
        target_low = float(EFFICIENCY_TARGET_UTIL_MIN)
    failed = bool(
        status == BEAM_STATUS_FAIL
        or str(status or "").strip().upper() == "FAIL"
    )
    return bool(not failed and util is not None and util < target_low)


def _guidance_executor_actionability_contract(
    item: dict | None,
    *,
    state: dict | None,
) -> tuple[bool, str | None]:
    if not isinstance(item, dict):
        return False, "invalid_guidance_item"
    current_state = _guidance_state_snapshot(state or {})
    action_type = str(item.get("action_type") or "").strip()
    if not action_type:
        return False, "missing_action_type"
    if (
        str(item.get("bucket") or "").strip().lower() == "efficiency"
        and not _guidance_item_is_resolved_one_click(item)
    ):
        return False, "primary_efficiency_card_not_executor_backed"
    try:
        updates = _resolve_recommendation_updates(
            item,
            state=current_state,
        )
    except Exception:
        updates = None
    updates = dict(updates or {})
    if not updates:
        return False, "missing_recommendation_updates"

    touches_shear = bool(set(updates) & _COMPOUND_SHEAR_UPDATE_KEYS)
    if touches_shear:
        design_actions = dict(
            _resolve_design_actions_from_state(current_state) or {}
        )
        direct_vu = abs(
            _float_from_state_owned(
                current_state,
                "uls_Vstar",
                _float_from_state_owned(
                    current_state,
                    "Vu_star",
                    0.0,
                ),
            )
        )
        if (
            _shear_demands_negligible(design_actions)
            or direct_vu
            <= float(GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN) + 1e-12
        ):
            return (
                False,
                "blocked_zero_shear_demand_shear_update_not_meaningful",
            )

    is_local_cleanup = bool(
        item.get("local_cleanup_candidate")
        or str(item.get("source") or "").strip()
        == "generate_in_target_local_cleanup_candidates"
        or bool(
            (item.get("resolved_candidate") or {}).get(
                "local_cleanup_candidate"
            )
        )
    )
    if is_local_cleanup and _guidance_item_is_resolved_one_click(item):
        preview_pass, _preview_util, preview_reason = (
            _design_guide_preview_contract_for_updates(
                current_state,
                updates,
            )
        )
        if preview_pass:
            return True, None
        return False, preview_reason or "local_cleanup_preview_failed"
    if not touches_shear:
        return True, None

    next_state = dict(current_state)
    next_state.update(updates)
    current_spacing = _float_from_state_owned(
        current_state,
        "s_lig",
        0.0,
    )
    next_spacing = _float_from_state_owned(
        next_state,
        "s_lig",
        current_spacing,
    )
    current_legs = _int_from_state_owned(
        current_state,
        "lig_legs",
        0,
    )
    next_legs = _int_from_state_owned(
        next_state,
        "lig_legs",
        current_legs,
    )
    current_diameter = _int_from_state_owned(
        current_state,
        "lig_d",
        0,
    )
    next_diameter = _int_from_state_owned(
        next_state,
        "lig_d",
        current_diameter,
    )
    shear_cleanup_like = bool(
        (next_legs == 0 and current_legs > 0)
        or next_spacing > current_spacing + 1e-9
        or (current_legs > 0 and next_legs < current_legs)
        or (
            current_diameter > 0
            and next_diameter < current_diameter
        )
    )
    if not shear_cleanup_like:
        return True, None

    design_context = _build_design_actions_context(current_state)
    overview = _collect_design_overview(
        current_state,
        context=design_context,
    )
    current_evaluation = {
        "state": current_state,
        "overview": overview,
    }
    mode_config = _design_mode_config(
        _design_optimisation_goal(current_state)
    )
    try:
        preview_candidate = _evaluate_auto_design_candidate(
            current_state,
            updates=updates,
            source="design_guide_executor_shear_family_threshold_probe",
            label=str(
                item.get("title_main") or "Design Guide candidate"
            ),
            action_type=action_type,
        )
    except Exception:
        preview_candidate = None
    preview_overview = dict(
        (preview_candidate or {}).get("overview") or {}
    )
    preview_shear_util = _parse_util_value(
        dict(preview_overview.get("utils") or {}).get("shear")
    )
    if (
        preview_shear_util is None
        or float(preview_shear_util)
        < float(FINAL_ACCEPTED_MIN_FAMILY_UTIL)
    ):
        return (
            False,
            "blocked_shear_cleanup_does_not_reach_final_family_threshold",
        )
    governing_domain = str(
        _governing_focus_from_overview(overview) or ""
    ).strip().lower()
    family = str(
        _design_guide_candidate_family(item) or ""
    ).strip().lower()
    subfamilies = set(_compound_subfamilies_from_updates(updates))
    behaves_like_shear_cleanup = bool(
        family in {"shear", "compound"}
        or "shear" in subfamilies
    )
    if not behaves_like_shear_cleanup:
        return True, None
    if (
        _guidance_item_is_resolved_one_click(item)
        and _resolved_shear_cleanup_is_executor_safe(
            item,
            state=current_state,
            overview=overview,
        )
    ):
        return True, None
    if family == "compound" and bool(overview.get("all_key_pass")):
        return False, "rejected_as_non_governing_cleanup"
    shear_cleanup_needed = _one_click_domain_needs_cleanup(
        current_evaluation,
        "shear",
        mode_config,
    )
    if governing_domain == "bending" and not shear_cleanup_needed:
        return False, "rejected_as_non_governing_cleanup"
    if governing_domain == "shear" and not shear_cleanup_needed:
        return False, "rejected_as_non_governing_cleanup"
    return True, None


def _design_guide_button_contract(
    item: dict | None,
    *,
    state: dict,
    blocking_reason_override: str | None = None,
) -> dict:
    return _design_guide_button_contract_owned(
        item,
        state=state,
        blocking_reason_override=blocking_reason_override,
        preview_contract=_design_guide_preview_contract_for_updates,
        ensure_resolved_payload=(
            _ensure_guidance_item_resolved_candidate_payload
        ),
        executor_contract=_guidance_executor_actionability_contract,
        resolve_updates=_resolve_recommendation_updates,
    )


def _overview_required_checks_acceptable(
    overview: dict | None,
) -> bool:
    if not isinstance(overview, dict):
        return False
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        tracked = [
            str(status or "").strip().upper()
            for status in statuses.values()
            if str(status or "").strip() not in {"", "—", "-"}
        ]
    else:
        tracked = []
    if not tracked:
        return bool(overview.get("all_key_pass")) and not bool(
            overview.get("any_fail")
        )
    return not any(
        status in {"FAIL", "FAILED", "ERROR"}
        for status in tracked
    )


def _design_guide_preview_contract_for_updates(
    state: dict,
    updates: dict,
) -> tuple[bool, float | None, str | None]:
    if not updates:
        return False, None, "missing_updates"
    try:
        current_overview = _collect_design_overview(
            _guidance_state_snapshot(state or {}),
            context=_build_design_actions_context(state or {}),
        )
    except Exception:
        current_overview = {}
    try:
        trial_state = dict(_guidance_state_snapshot(state or {}))
        trial_state.update(dict(updates))
        preview = evaluate_candidate_full(
            _guidance_state_snapshot(trial_state),
            source="design_guide_button_contract_preview",
            updates=dict(updates),
        )
    except Exception:
        return False, None, "preview_exception"
    if not isinstance(preview, dict):
        return False, None, "preview_unavailable"
    overview = dict(preview.get("overview") or {})
    expected_util = _parse_util_value(
        preview.get("worst_util")
        or overview.get("worst_util")
        or overview.get("governing_util")
    )
    statuses = dict(overview.get("statuses") or {})
    fail_statuses = [
        str(key)
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    ]
    current_statuses = dict(
        (current_overview or {}).get("statuses") or {}
    )
    current_fail_statuses = [
        str(key)
        for key, value in current_statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    ]
    new_fail_statuses = sorted(
        set(fail_statuses) - set(current_fail_statuses)
    )
    if new_fail_statuses:
        return (
            False,
            expected_util,
            "candidate_preview_introduces_fail_status",
        )
    if fail_statuses:
        return False, expected_util, "candidate_preview_has_fail_status"
    if not _overview_required_checks_acceptable(overview):
        return (
            False,
            expected_util,
            "candidate_preview_not_compliant",
        )
    if not current_fail_statuses:
        preview_pass = True
    else:
        current_util = _parse_util_value(
            (current_overview or {}).get("worst_util")
            or (current_overview or {}).get("governing_util")
        )
        improves_util = bool(
            current_util is not None
            and expected_util is not None
            and float(expected_util) < float(current_util) - 1e-9
        )
        reduces_fail_count = bool(
            len(fail_statuses) < len(current_fail_statuses)
        )
        preview_pass = bool(
            improves_util
            or reduces_fail_count
            or not current_fail_statuses
        )
        if not preview_pass:
            return (
                False,
                expected_util,
                "candidate_preview_does_not_improve_active_failure",
            )
    return True, expected_util, None


def _guidance_update_map(item: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    payload = dict(item.get("action_payload") or {})
    return dict(
        payload.get("updates")
        or payload.get("resolved_candidate_updates")
        or {}
    )


def _guidance_item_material_updates(item: dict, state: dict) -> dict:
    try:
        updates = dict(_guidance_update_map(item) or {})
    except Exception:
        updates = {}
    if not updates and str((item or {}).get("action_type") or "").strip():
        try:
            work = dict(item or {})
            work["action_payload"] = dict(work.get("action_payload") or {})
            _ensure_guidance_item_resolved_candidate_payload(
                work,
                state=state,
            )
            updates = dict(_guidance_update_map(work) or {})
        except Exception:
            updates = {}
    if updates:
        try:
            if _updates_match_state(state, updates):
                return {}
        except Exception:
            pass
    return updates


def _guidance_item_resolved_action_type(item: dict) -> str:
    payload = dict((item or {}).get("action_payload") or {})
    return str(
        payload.get("resolved_candidate_action_type")
        or (item or {}).get("action_type")
        or ""
    ).strip()


def _guidance_update_is_lighter_or_smaller(
    state: dict,
    updates: dict,
    item: dict | None = None,
) -> bool:
    if not updates:
        return False
    action_type = _guidance_item_resolved_action_type(item or {})
    if action_type in {
        "reduce_bottom_reinforcement",
        "tighten_geometry",
        "increase_link_spacing",
        "reduce_number_of_legs",
    }:
        return True
    geometry_keys = {"D", "b", "bw", "bf", "tw", "tf", "bf_bot", "tf_bot"}
    bottom_keys = {
        "bot1_count",
        "bot2_count",
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_2_bars",
        "db_bot_1",
        "db_bot_2",
        "nb_bot",
        "db_bot",
    }
    for key, after_raw in updates.items():
        try:
            before = float(
                _float_from_state_owned(
                    state,
                    key,
                    state.get(key, 0.0),
                )
            )
            after = float(after_raw)
        except Exception:
            continue
        if key in geometry_keys and after < before - 1e-9:
            return True
        if key in bottom_keys and after < before - 1e-9:
            return True
        if key == "s_lig" and after > before + 1e-9:
            return True
        if key in {"lig_legs", "lig_d"} and after < before - 1e-9:
            return True
    return False


def _guidance_item_is_shear_only_cleanup(
    state: dict,
    updates: dict,
    item: dict,
) -> bool:
    if not updates:
        return False
    if not set(updates).issubset({"s_lig", "lig_legs", "lig_d"}):
        return False
    try:
        current_spacing = float(
            _float_from_state_owned(state, "s_lig", 0.0) or 0.0
        )
        next_spacing = float(updates.get("s_lig", current_spacing))
        current_legs = float(
            _float_from_state_owned(state, "lig_legs", 0.0) or 0.0
        )
        next_legs = float(updates.get("lig_legs", current_legs))
        current_diameter = float(
            _float_from_state_owned(state, "lig_d", 0.0) or 0.0
        )
        next_diameter = float(updates.get("lig_d", current_diameter))
    except Exception:
        return False
    return bool(
        next_spacing > current_spacing + 1e-9
        or next_legs < current_legs - 1e-9
        or next_diameter < current_diameter - 1e-9
        or str(item.get("check_key") or "").strip().lower() == "shear"
    )


def _guidance_shear_is_non_governing_conservative(
    overview: dict | None,
    mode_config: dict,
) -> bool:
    resolved_overview = overview if isinstance(overview, dict) else {}
    utils = dict(resolved_overview.get("utils") or {})
    shear_util = _parse_util_value(utils.get("shear"))
    worst_util = _parse_util_value(resolved_overview.get("worst_util"))
    target_low = float(
        mode_config.get("target_lo", EFFICIENCY_TARGET_UTIL_MIN)
    )
    if shear_util is None:
        return False
    if shear_util >= target_low - float(TARGET_BAND_EPS):
        return False
    if worst_util is None:
        return True
    return bool(
        float(shear_util) < float(worst_util) - float(TARGET_BAND_EPS)
    )


def _is_in_target_zone_with_eps(
    overview: dict,
    mode_config: dict,
    *,
    eps: float = TARGET_BAND_EPS,
) -> bool:
    worst_util = float((overview or {}).get("worst_util", 0.0) or 0.0)
    target_low = float(
        mode_config.get(
            "target_util_min",
            EFFICIENCY_TARGET_UTIL_MIN,
        )
        or EFFICIENCY_TARGET_UTIL_MIN
    )
    target_high = float(
        mode_config.get(
            "target_util_max",
            EFFICIENCY_TARGET_UTIL_MAX,
        )
        or EFFICIENCY_TARGET_UTIL_MAX
    )
    return target_low <= worst_util <= target_high + float(eps)


def _derive_design_guide_guidance_intent(
    item: dict,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
) -> str:
    resolved_overview = overview if isinstance(overview, dict) else {}
    mode_config = _design_mode_config(_design_optimisation_goal(state))
    updates = _guidance_item_material_updates(item, state)
    has_material_update = bool(updates)
    has_action = bool(str((item or {}).get("action_type") or "").strip())
    statuses = dict(resolved_overview.get("statuses") or {})
    fail_keys = {
        str(key).strip().lower()
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    }
    any_fail = bool(resolved_overview.get("any_fail")) or bool(fail_keys)
    all_key_pass = bool(resolved_overview.get("all_key_pass")) and not any_fail
    worst_util = _parse_util_value(resolved_overview.get("worst_util"))
    target_low = float(
        mode_config.get("target_lo", EFFICIENCY_TARGET_UTIL_MIN)
    )
    below_target = bool(
        all_key_pass
        and worst_util is not None
        and float(worst_util) < target_low - float(TARGET_BAND_EPS)
    )
    in_target_band = bool(
        all_key_pass
        and _is_in_target_zone_with_eps(
            resolved_overview,
            mode_config,
            eps=TARGET_BAND_EPS,
        )
    )
    terminal_state = str(
        (item or {}).get("design_guide_terminal_state") or ""
    ).strip()
    classification = str(
        (efficiency_state or {}).get("classification") or ""
    ).strip()

    if any_fail and has_action and has_material_update:
        return "required_fix"
    if (
        has_action
        and has_material_update
        and (
            bool((item or {}).get("allow_in_target_primary_action"))
            or str(
                (item or {}).get("design_guide_refinement_priority") or ""
            ).strip()
            == "shear_congestion_reshape"
            or bool(
                ((item or {}).get("resolved_candidate") or {}).get(
                    "allow_in_target_primary_action"
                )
            )
            or str(
                ((item or {}).get("resolved_candidate") or {}).get(
                    "design_guide_refinement_priority"
                )
                or ""
            ).strip()
            == "shear_congestion_reshape"
        )
    ):
        return "efficiency_tightening"
    if (
        has_action
        and has_material_update
        and _guidance_item_is_shear_only_cleanup(state, updates, item)
        and _guidance_shear_is_non_governing_conservative(
            resolved_overview,
            mode_config,
        )
    ):
        return "optional_cleanup"
    if (
        not has_material_update
        and str((item or {}).get("check_key") or "").strip().lower()
        == "shear"
        and _guidance_shear_is_non_governing_conservative(
            resolved_overview,
            mode_config,
        )
    ):
        return "optional_cleanup"
    if (
        has_action
        and below_target
        and has_material_update
        and _guidance_update_is_lighter_or_smaller(state, updates, item)
    ):
        return "efficiency_tightening"
    if in_target_band and not has_material_update:
        return "already_efficient"
    if terminal_state == "optimal" or (
        classification == "optimal" and not has_material_update
    ):
        return "already_efficient"
    return "advisory_warning"


def _design_guide_apply_copy_model_to_items(
    items: list[dict] | None,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
) -> list[dict]:
    return [
        apply_guidance_copy_model_to_item(
            item,
            state=state,
            overview=overview,
            efficiency_state=efficiency_state,
            derive_guidance_intent=_derive_design_guide_guidance_intent,
        )
        for item in list(items or [])
        if isinstance(item, dict)
    ]


def _mode_recommendation_expected_bend_util(
    mode_tighten: dict | None,
) -> float | None:
    if not isinstance(mode_tighten, dict):
        return None
    for key in ("expected_util", "real_util"):
        raw = mode_tighten.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except Exception:
            continue
        if not math.isnan(value):
            return value
    candidate_summary = mode_tighten.get("candidate_summary") or {}
    capacity = float(
        candidate_summary.get("summary_phiMu_kNm", 0.0) or 0.0
    )
    demand = float(
        candidate_summary.get("summary_Mu_star_kNm", 0.0) or 0.0
    )
    if capacity > 1e-9:
        return demand / capacity
    return None


def _recommendation_preview_util(
    recommendation: dict | None,
) -> float | None:
    if not isinstance(recommendation, dict):
        return None
    mode_util = _mode_recommendation_expected_bend_util(recommendation)
    if mode_util is not None:
        return mode_util
    values: list[float] = []
    for key in ("util", "real_util", "bending_util", "shear_util"):
        value = recommendation.get(key)
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            values.append(resolved)
    if values:
        return max(values)
    return None


def _materialize_guidance_candidate(
    base_candidate: dict | None,
    recommendation: dict | None,
    *,
    source: str,
) -> dict | None:
    if not base_candidate or not isinstance(recommendation, dict):
        return None
    updates = dict(
        recommendation.get("updates")
        or recommendation.get("arrangement")
        or {}
    )
    if not updates:
        return None
    candidate = _evaluate_auto_design_candidate(
        base_candidate.get("state") or {},
        updates=updates,
        source=source,
        label=str(
            recommendation.get("label")
            or source.replace("_", " ").title()
        ),
        action_type="auto_design",
    )
    if candidate is not None:
        candidate["guidance_preview_util"] = _recommendation_preview_util(
            recommendation
        )
    return candidate


def _design_guide_lightweight_guidance_state(incoming: dict | None) -> dict:
    return resolve_design_guide_lightweight_state(
        InputsSummaryStateRuntime(
            design_guide_fingerprint=lambda state: stable_fingerprint_for_payload(
                state
            ),
            guidance_state_snapshot=lambda state: _guidance_state_snapshot_owned(
                state
            ),
            session_state=st.session_state,
            shared_state_snapshot=lambda: {
                key: st.session_state.get(key, default)
                for key, default in SHARED_DEFAULTS.items()
            },
            ux_probe_record=ux_probe_record,
        ),
        incoming,
    )


def _design_optimisation_goal(state: dict | None = None) -> str:
    return _design_optimisation_goal_owned(state or st.session_state)


def _design_mode_config(goal: str | None = None) -> dict:
    return _design_mode_config_owned(
        goal or _design_optimisation_goal(st.session_state)
    )


def _design_optimisation_goal_label(state: dict | None = None) -> str:
    return DESIGN_OPTIMISATION_GOAL_LABELS[_design_optimisation_goal(state)]


def _resolve_design_actions_from_state(state: dict) -> dict:
    from state_and_helpers import resolve_design_actions

    return resolve_design_actions(state)


def _local_cleanup_acceptance_fingerprint(state: dict | None) -> tuple:
    return build_local_cleanup_acceptance_fingerprint(state)


def _local_cleanup_post_apply_acceptance_matches(
    state: dict | None,
) -> bool:
    session_state = _GUIDANCE_COMPUTE_SESSION_STATE
    expected_fingerprint = (
        session_state.get("_design_guide_post_cleanup_acceptance_fp")
        if session_state is not None
        else dict(state or {}).get("_design_guide_post_cleanup_acceptance_fp")
    )
    return _local_cleanup_acceptance_matches_owned(
        state,
        expected_fingerprint=expected_fingerprint,
        accepted_fingerprints=_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
    )


def _build_design_actions_context(state: dict) -> dict:
    return _build_design_actions_context_owned(state)


def _build_canonical_design_state_pack(state: dict) -> dict:
    return _build_canonical_pack_owned(
        state,
        runtime=CanonicalDesignStatePackRuntime(_guidance_state_snapshot),
    )


def _collect_design_overview(
    state: dict,
    context: dict | None = None,
) -> dict:
    return _collect_design_overview_owned(
        state,
        context=context,
        session_state=st.session_state,
    )


def evaluate_candidate_full(*args: Any, **kwargs: Any) -> dict | None:
    return _evaluate_full_candidate_owned(
        *args,
        session_state=st.session_state,
        **kwargs,
    )


def _evaluate_auto_design_candidate(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_already_resolved: bool = False,
) -> dict | None:
    candidate_state = (
        dict(state or {})
        if state_already_resolved
        else _guidance_state_snapshot(state)
    )
    if updates:
        candidate_state.update(updates)
    return evaluate_candidate_full(
        candidate_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
    )


def _evaluate_serviceability_ladder_screen_candidate(
    state: dict,
    *,
    reference_overview: dict,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
) -> dict | None:
    """Screen a serviceability ladder step with the owned engineering kernel.

    The ladder may call this at most four times.  The selected step is always
    re-evaluated by ``_evaluate_auto_design_candidate`` before publication, so
    this path cannot authorise an Apply action on its own.
    """

    del source, label, action_type
    candidate_state = _guidance_state_snapshot(state)
    if updates:
        candidate_state.update(updates)
    return _evaluate_fast_candidate_owned(
        candidate_state,
        {
            "reference_overview": dict(reference_overview or {}),
            "seed_overview": dict(reference_overview or {}),
        },
        session_state=st.session_state,
    )


def _is_in_target_zone_with_eps(
    overview: dict,
    mode_config: dict,
    *,
    eps: float = TARGET_BAND_EPS,
) -> bool:
    worst = float((overview or {}).get("worst_util", 0.0) or 0.0)
    low = float(
        mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN)
        or EFFICIENCY_TARGET_UTIL_MIN
    )
    high = float(
        mode_config.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX)
        or EFFICIENCY_TARGET_UTIL_MAX
    )
    return low <= worst <= high + float(eps)


def _efficiency_state_has_valid_candidate(state: dict) -> bool:
    return isinstance(state, dict) and any(
        state.get(key) is not None
        for key in (
            "mode_tightening",
            "bottom_tightening",
            "shear_tightening",
            "geometry_tightening",
        )
    )


def _requires_full_coverage_for_primary_one_click(
    overview: dict,
) -> tuple[bool, list[str]]:
    failed = sorted(
        key
        for key, value in dict((overview or {}).get("statuses") or {}).items()
        if str(value or "").upper() == "FAIL"
    )
    return len(failed) >= 2, failed


def _overview_required_checks_acceptable(overview: dict | None) -> bool:
    if not isinstance(overview, dict):
        return False
    statuses = overview.get("statuses")
    tracked = (
        [
            str(status or "").strip().upper()
            for status in statuses.values()
            if str(status or "").strip() not in {"", "â€”", "-"}
        ]
        if isinstance(statuses, dict)
        else []
    )
    if not tracked:
        return bool(overview.get("all_key_pass")) and not bool(
            overview.get("any_fail")
        )
    return not any(
        status in {"FAIL", "FAILED", "ERROR"} for status in tracked
    )


def _guidance_governing_primary_action(
    overview: dict | None,
) -> tuple[str, dict[str, float | None]]:
    utils = dict((overview or {}).get("utils") or {})
    primary: dict[str, float | None] = {}
    ranked: list[tuple[str, float]] = []
    for key in ("bending", "shear"):
        try:
            value = float(utils.get(key))
        except Exception:
            primary[key] = None
            continue
        if math.isnan(value):
            primary[key] = None
            continue
        primary[key] = value
        ranked.append((key, value))
    if ranked:
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[0][0], primary
    return "general", primary


def _merge_target_band_probe_to_debug_sink(
    sink: dict | None,
    probe: dict,
) -> None:
    if not isinstance(sink, dict):
        return
    for key in (
        "target_band_default_stop",
        "target_band_override_allowed",
        "target_band_override_reason",
        "target_band_eps",
        "target_band_with_eps_passed",
        "winner_goal_alignment_score",
        "current_goal_alignment_score",
        "goal_alignment_improvement",
        "in_band_materiality_passed",
        "in_band_strong_override_passed",
        "mode_difference_material",
        "in_band_mode_search_strategy",
        "in_band_overview_worst_util",
    ):
        if key in probe:
            sink[key] = probe.get(key)


def _shear_cleanup_materially_reduces_reinforcement(
    current_state: dict | None,
    candidate_state: dict | None,
) -> bool:
    if not isinstance(current_state, dict) or not isinstance(
        candidate_state,
        dict,
    ):
        return False
    current_spacing = _float_from_state_owned(
        current_state,
        "s_lig",
        0.0,
    )
    next_spacing = _float_from_state_owned(
        candidate_state,
        "s_lig",
        current_spacing,
    )
    current_legs = _int_from_state_owned(current_state, "lig_legs", 0)
    next_legs = _int_from_state_owned(
        candidate_state,
        "lig_legs",
        current_legs,
    )
    current_diameter = _int_from_state_owned(current_state, "lig_d", 0)
    next_diameter = _int_from_state_owned(
        candidate_state,
        "lig_d",
        current_diameter,
    )
    return bool(
        (current_legs > 0 and next_legs == 0)
        or next_spacing > current_spacing + 1e-9
        or next_legs < current_legs
        or next_diameter < current_diameter
    )


def _design_guide_guidance_intent_debug_rows(
    items: list[dict] | None,
) -> list[dict]:
    rows: list[dict] = []
    for index, item in enumerate(list(items or [])):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "index": int(index),
                "title": str(item.get("title_main") or "").strip() or None,
                "check_key": str(item.get("check_key") or "").strip() or None,
                "action_type": str(item.get("action_type") or "").strip()
                or None,
                "guidance_intent": str(
                    item.get("guidance_intent") or ""
                ).strip()
                or None,
                "button_contract": dict(item.get("button_contract") or {}),
                "displayed_util": item.get("displayed_util"),
                "displayed_status": item.get("displayed_status"),
                "display_truth_source": item.get("display_truth_source"),
                "target_low": item.get("target_low"),
                "target_high": item.get("target_high"),
                "displayed_within_target_band": bool(
                    item.get("displayed_within_target_band")
                ),
                "source_summary_util": item.get("source_summary_util"),
                "source_candidate_util": item.get("source_candidate_util"),
                "source_post_commit_util": item.get(
                    "source_post_commit_util"
                ),
            }
        )
    return rows


def _auto_design_results_from_candidate(candidate: dict | None) -> dict:
    overview = dict((candidate or {}).get("overview") or {})
    utils = dict(overview.get("utils") or {})
    components = dict((candidate or {}).get("bending_components") or {})
    ductility_util = components.get("ductility_util")
    ku_limit = 0.36
    try:
        ku_value = (
            float(ductility_util) * ku_limit
            if ductility_util is not None
            else None
        )
    except Exception:
        ku_value = None
    return {
        "bending": {"util": utils.get("bending")},
        "shear": {"util": utils.get("shear")},
        "ductility": {"ku": ku_value, "limit": ku_limit},
        "row_count": int((candidate or {}).get("row_count", 1) or 1),
        "_overview": overview,
    }


def _prefer_target_band_guidance_item_order(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    mode_config: dict | None = None,
) -> list[dict]:
    items = [
        item for item in list(guidance_items or []) if isinstance(item, dict)
    ]
    if len(items) < 2:
        return items
    goal = _design_optimisation_goal(state)
    config = (
        mode_config
        if isinstance(mode_config, dict)
        else _design_mode_config(goal)
    )
    target_low, target_high, _ = _resolved_efficiency_target_band(
        config,
        goal=goal,
    )
    target_mid = (float(target_low) + float(target_high)) / 2.0
    target_rows: list[tuple[tuple, int, dict]] = []
    for index, item in enumerate(items):
        action_type = str(item.get("action_type") or "").strip()
        if not action_type:
            continue
        payload = dict(item.get("action_payload") or {})
        resolved = dict(item.get("resolved_candidate") or {})
        updates = dict(
            payload.get("resolved_candidate_updates")
            or payload.get("updates")
            or resolved.get("updates")
            or {}
        )
        if not updates:
            continue
        truth = dict(item.get("display_truth") or {})
        util = _parse_util_value(
            payload.get("resolved_candidate_post_util")
            if payload.get("resolved_candidate_post_util") is not None
            else resolved.get(
                "candidate_post_util",
                truth.get(
                    "source_candidate_util",
                    truth.get("displayed_util"),
                ),
            )
        )
        if util is None or not (
            float(target_low) <= float(util) <= float(target_high)
        ):
            continue
        target_rows.append(
            (
                (abs(float(util) - target_mid), len(updates), index),
                index,
                item,
            )
        )
    if not target_rows:
        return items
    target_rows.sort(key=lambda row: row[0])
    selected_index = int(target_rows[0][1])
    if selected_index == 0:
        return items
    return [items[selected_index]] + [
        item
        for index, item in enumerate(items)
        if index != selected_index
    ]


def _bending_fail_contract_ladder_guidance_item(
    guidance_state: dict,
    overview: dict,
    mode_config: dict,
    *,
    debug_sink: dict | None = None,
) -> dict | None:
    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict((overview or {}).get("statuses") or {}).items()
    }
    if statuses.get("bending") != "FAIL" or statuses.get("shear") == "FAIL":
        return None
    strategy = family_strategy_for("BENDING_FAIL_GOVERNS")
    if strategy is None or not callable(getattr(strategy, "contracted_repair_ladder_specs", None)):
        return None
    state = dict(guidance_state or {})
    geometry_locked = bool(
        state.get("geometry_locked")
        or state.get("lock_geometry")
        or state.get("geometry_inputs_locked")
    )
    try:
        ladder = strategy.contracted_repair_ladder_specs(
            state,
            width_key="b",
            geometry_locked=geometry_locked,
        )
    except Exception as exc:
        if isinstance(debug_sink, dict):
            debug_sink["bending_fail_contract_ladder_error"] = type(exc).__name__
        return None

    commands = build_design_guide_controller_active_fail_executor_ladder_eval_commands(
        family_id="BENDING_FAIL_GOVERNS",
        ladder=ladder,
        default_label="Bending repair",
    )
    target_low, target_high, _ = _resolved_efficiency_target_band(
        mode_config,
        goal=_design_optimisation_goal(state),
    )
    evaluated_rows: list[dict] = []
    selected: dict | None = None
    for command in commands:
        updates = dict(command.get("updates") or {})
        if not updates:
            continue
        label = str(command.get("label") or "Bending repair")
        family_meta = dict(
            command.get("family_meta")
            or build_design_guide_controller_active_fail_executor_ladder_candidate_meta(
                family_id="BENDING_FAIL_GOVERNS",
                spec=dict(command.get("spec") or {}),
            )
        )
        try:
            candidate = _evaluate_auto_design_candidate(
                state,
                updates=updates,
                source=resolve_active_fail_executor_candidate_eval_source(family_meta),
                label=label,
                action_type="apply_resolved_candidate",
            )
        except Exception:
            candidate = None
        projected = project_active_fail_executor_evaluated_candidate_result(
            candidate,
            updates=updates,
            label=label,
            family_meta=family_meta,
            geometry_update_keys={"D", "b", "bw"},
            bottom_update_keys={
                "bot1_count",
                "bot2_count",
                "bot_row_1_bars",
                "bot_row_2_bars",
                "db_bot_1",
                "db_bot_2",
                "bot_row_1_dia",
                "bot_row_2_dia",
            },
            shear_update_keys={"lig_d", "lig_legs", "s_lig"},
        )
        if not isinstance(projected, dict):
            continue
        evaluated_rows.append(dict(projected))
        candidate_util = _parse_util_value(
            projected.get("candidate_post_util")
            or projected.get("worst_util")
            or dict(projected.get("overview") or {}).get("worst_util")
            or dict(projected.get("overview") or {}).get("governing_util")
        )
        projected["candidate_reaches_target_band"] = bool(
            candidate_util is not None
            and float(target_low) <= float(candidate_util) <= float(target_high)
        )
        projected["reaches_target_band"] = bool(projected["candidate_reaches_target_band"])
        if resolve_design_guide_controller_active_fail_executor_ladder_stop_decision(
            family_id="BENDING_FAIL_GOVERNS",
            evaluated_candidate=projected,
            base_state=state,
        ):
            selected = dict(projected)
            break
    if not selected:
        if isinstance(debug_sink, dict):
            debug_sink["bending_fail_contract_ladder_attempted"] = True
            debug_sink["bending_fail_contract_ladder_found_safe"] = False
            debug_sink["bending_fail_contract_ladder_evaluated_candidate_count"] = len(evaluated_rows)
        return None

    updates = dict(selected.get("updates") or {})
    candidate_id = str(
        selected.get("candidate_id")
        or selected.get("source_candidate_id")
        or f"bending_fail_contract_ladder:{len(evaluated_rows)}"
    )
    evidence = {
        "source": "BENDING_FAIL_GOVERNS.contract_ladder",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "published_family_id": "BENDING_FAIL_GOVERNS",
        "cta_family_id": "BENDING_FAIL_GOVERNS",
        "card_family_id": "BENDING_FAIL_GOVERNS",
        "apply_payload_family_id": "BENDING_FAIL_GOVERNS",
        "active_failures": ["bending"],
        "repair_search_ran": True,
        "repair_search_exhaustive": False,
        "bending_fail_contract_ladder_attempted": True,
        "bending_fail_contract_ladder_found_safe": True,
        "bending_fail_contract_ladder_evaluated_candidate_count": len(evaluated_rows),
        "safe_executor_backed_candidates_count": 1,
        "executable_repair_candidate_count": 1,
        "safe_repair_candidate_count": 1,
        "selected_candidate_id": candidate_id,
        "selected_candidate_updates": dict(updates),
        "selected_candidate_preview_pass": True,
        "selected_candidate_post_util": selected.get("candidate_post_util") or selected.get("worst_util"),
    }
    selected["candidate_id"] = candidate_id
    selected["source_candidate_id"] = candidate_id
    selected["candidate_search_evidence"] = dict(evidence)
    item = _guidance_item_from_resolved_candidate(
        selected,
        state=state,
        overview=overview,
        title=str(selected.get("label") or "Repair bending capacity"),
        reasoning=(
            "This executor-backed bending repair follows the BENDING_FAIL_GOVERNS "
            "contract ladder and makes the required checks pass."
        ),
        status="FAIL",
        primary_action="Apply recommendation",
    )
    if not isinstance(item, dict):
        return None
    button_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "BENDING_FAIL_GOVERNS",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "published_family_id": "BENDING_FAIL_GOVERNS",
        "cta_family_id": "BENDING_FAIL_GOVERNS",
        "apply_payload_family_id": "BENDING_FAIL_GOVERNS",
        "updates": dict(updates),
        "preview_pass": True,
        "expected_util": selected.get("candidate_post_util") or selected.get("worst_util"),
        "blocking_reason": None,
        "disabled_reason": None,
        "source_candidate_id": candidate_id,
        "candidate_id": candidate_id,
    }
    item["guidance_intent"] = "required_fix"
    item["primary_card_actionable"] = True
    item["candidate_search_evidence"] = dict(evidence)
    item["candidate_id"] = candidate_id
    item["source_candidate_id"] = candidate_id
    item["button_contract"] = dict(button_contract)
    payload = dict(item.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_action_type"] = "apply_resolved_candidate"
    payload["button_contract"] = dict(button_contract)
    payload["source_candidate_id"] = candidate_id
    item["action_payload"] = payload
    if isinstance(debug_sink, dict):
        debug_sink.update(
            {
                "bending_fail_contract_ladder_attempted": True,
                "bending_fail_contract_ladder_found_safe": True,
                "bending_fail_contract_ladder_evaluated_candidate_count": len(evaluated_rows),
                "candidate_search_evidence": dict(evidence),
                "one_click_critical_candidate_exists": True,
                "one_click_critical_candidate_label": str(item.get("title_main") or item.get("title") or ""),
                "one_click_critical_candidate_action_type": item.get("action_type"),
                "one_click_critical_candidate_reaches_target_band": True,
                "one_click_primary_candidate_valid": True,
                "one_click_primary_candidate_valid_reason": "full_failure_coverage",
            }
        )
    return item


def _serviceability_contract_ladder_guidance_item(
    guidance_state: dict,
    overview: dict,
    *,
    debug_sink: dict | None = None,
) -> dict | None:
    """Resolve a serviceability failure through its selected-family ladder."""

    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict((overview or {}).get("statuses") or {}).items()
    }
    serviceability_failures = [
        key for key in ("crack", "deflection") if statuses.get(key) == "FAIL"
    ]
    if (
        not serviceability_failures
        or statuses.get("bending") == "FAIL"
        or statuses.get("shear") == "FAIL"
    ):
        return None
    strategy = family_strategy_for("SERVICEABILITY_GOVERNS")
    if strategy is None or not callable(
        getattr(strategy, "contracted_serviceability_ladder_result", None)
    ):
        return None

    state = dict(guidance_state or {})
    utils = dict((overview or {}).get("utils") or {})
    serviceability_utils = [
        value
        for value in (
            _parse_util_value(utils.get("crack")),
            _parse_util_value(utils.get("deflection")),
        )
        if value is not None
    ]
    runtime_state = dict(state)
    runtime_state.update(
        {
            "beam_depth_mm": _float_from_state_owned(state, "D", 500.0),
            "beam_width_mm": _float_from_state_owned(state, "b", 300.0),
            "bottom_bar_count": _int_from_state_owned(state, "bot1_count", 3),
            "serviceability_utilisation": (
                max(serviceability_utils) if serviceability_utils else None
            ),
        }
    )
    try:
        runtime_result = strategy.contracted_serviceability_ladder_result(
            runtime_state,
            evaluate_candidate=build_serviceability_live_evaluator(
                partial(
                    _evaluate_serviceability_ladder_screen_candidate,
                    reference_overview=overview,
                ),
                evaluation_source="evaluate_candidate_fast_screen",
            ),
        )
    except Exception as exc:
        if isinstance(debug_sink, dict):
            debug_sink["serviceability_family_ladder_error"] = type(exc).__name__
        return None

    selected = dict(runtime_result.get("selected_recommendation") or {})
    contract_updates = dict(
        selected.get("updates") or runtime_result.get("updates") or {}
    )
    updates = serviceability_updates_to_app_updates(contract_updates)
    if not updates:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "serviceability_family_ladder_attempted": True,
                    "serviceability_family_ladder_found_safe": False,
                    "serviceability_family_ladder_status": runtime_result.get("status"),
                }
            )
        return None
    candidate_id = str(
        selected.get("candidate_id")
        or f"serviceability_family_ladder:{runtime_result.get('ladder_hash') or 'selected'}"
    )
    candidate = _evaluate_auto_design_candidate(
        state,
        updates=updates,
        source="SERVICEABILITY_GOVERNS.contract_ladder",
        label="Repair serviceability",
        action_type="apply_resolved_candidate",
    )
    if not isinstance(candidate, dict):
        return None
    confirmed_overview = dict(candidate.get("overview") or {})
    full_confirmation_passed = bool(
        confirmed_overview.get("all_key_pass")
        and not confirmed_overview.get("any_fail")
    )
    if not full_confirmation_passed:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "serviceability_family_ladder_attempted": True,
                    "serviceability_family_ladder_found_safe": False,
                    "serviceability_family_ladder_fast_full_disagreement": True,
                    "serviceability_family_ladder_full_confirmation_passed": False,
                    "serviceability_family_ladder_full_confirmation_statuses": dict(
                        confirmed_overview.get("statuses") or {}
                    ),
                }
            )
        return None
    candidate["candidate_id"] = candidate_id
    candidate["source_candidate_id"] = candidate_id
    candidate["updates"] = dict(updates)
    evidence = {
        "source": "SERVICEABILITY_GOVERNS.contract_ladder",
        "selected_family_id": "SERVICEABILITY_GOVERNS",
        "published_family_id": "SERVICEABILITY_GOVERNS",
        "cta_family_id": "SERVICEABILITY_GOVERNS",
        "card_family_id": "SERVICEABILITY_GOVERNS",
        "apply_payload_family_id": "SERVICEABILITY_GOVERNS",
        "active_failures": list(serviceability_failures),
        "repair_search_ran": True,
        "repair_search_exhaustive": False,
        "serviceability_family_ladder_attempted": True,
        "serviceability_family_ladder_found_safe": True,
        "serviceability_family_ladder_screening_source": "evaluate_candidate_fast_screen",
        "serviceability_family_ladder_full_confirmation_source": "evaluate_candidate_full",
        "serviceability_family_ladder_full_confirmation_passed": True,
        "serviceability_family_ladder_fast_full_disagreement": False,
        "selected_candidate_id": candidate_id,
        "selected_candidate_updates": dict(updates),
        "selected_candidate_preview_pass": True,
        "contract_ladder_hash": runtime_result.get("ladder_hash"),
        "contract_ladder_status": runtime_result.get("status"),
    }
    candidate["candidate_search_evidence"] = dict(evidence)
    item = _guidance_item_from_resolved_candidate(
        candidate,
        state=state,
        overview=overview,
        title="Repair serviceability",
        reasoning=(
            "This executor-backed repair follows the SERVICEABILITY_GOVERNS "
            "reinforcement-first, then depth and width contract ladder."
        ),
        status="FAIL",
        primary_action="Apply recommendation",
    )
    if not isinstance(item, dict):
        return None
    item["guidance_intent"] = "required_fix"
    item["candidate_search_evidence"] = dict(evidence)
    button_contract = dict(item.get("button_contract") or {})
    button_contract.update(
        {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "SERVICEABILITY_GOVERNS",
            "selected_family_id": "SERVICEABILITY_GOVERNS",
            "published_family_id": "SERVICEABILITY_GOVERNS",
            "cta_family_id": "SERVICEABILITY_GOVERNS",
            "apply_payload_family_id": "SERVICEABILITY_GOVERNS",
            "updates": dict(updates),
            "preview_pass": True,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        }
    )
    item["button_contract"] = dict(button_contract)
    payload = dict(item.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_action_type"] = "apply_resolved_candidate"
    payload["source_candidate_id"] = candidate_id
    payload["button_contract"] = dict(button_contract)
    item["action_payload"] = payload
    if isinstance(debug_sink, dict):
        debug_sink.update(evidence)
        debug_sink["serviceability_family_ladder_status"] = runtime_result.get("status")
    return item


def _shear_fail_bending_overdesign_virtual_merge_guidance_item(
    guidance_state: dict,
    overview: dict,
    mode_config: dict,
    shear_candidate: dict | None,
    *,
    debug_sink: dict | None = None,
) -> dict | None:
    def _skip(reason: str, **extra: Any) -> None:
        if isinstance(debug_sink, dict):
            debug_sink["mixed_virtual_merge_attempted"] = True
            debug_sink["mixed_virtual_merge_skipped_reason"] = reason
            for key, value in extra.items():
                debug_sink[f"mixed_virtual_merge_{key}"] = value

    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict((overview or {}).get("statuses") or {}).items()
    }
    if statuses.get("shear") != "FAIL" or statuses.get("bending") == "FAIL":
        _skip("not_shear_only_active_failure", statuses=dict(statuses))
        return None
    try:
        family_utils, material_families, governing_family = identify_materially_overprovided_non_governing_families(overview)
    except Exception:
        family_utils, material_families, governing_family = {}, [], None
    if "bending" not in {str(family or "").strip().lower() for family in material_families}:
        _skip(
            "bending_not_materially_overprovided",
            family_utils=dict(family_utils),
            material_families=list(material_families),
            governing_family=governing_family,
        )
        return None
    source_candidate = dict(shear_candidate or {})
    shear_updates = dict(source_candidate.get("updates") or {})
    shear_update_keys = {"lig_d", "lig_legs", "s_lig"}
    cleanup_update_keys = {
        "D",
        "b",
        "bw",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_1_bars",
        "bot_row_2_bars",
        "bot_row_1_dia",
        "bot_row_2_dia",
    }
    if not (set(shear_updates) & shear_update_keys):
        _skip("mandatory_shear_candidate_missing_shear_updates", shear_updates=dict(shear_updates))
        return None

    state = dict(guidance_state or {})
    label = str(source_candidate.get("label") or "Shear capacity is low")
    try:
        shear_eval = _evaluate_auto_design_candidate(
            state,
            updates=shear_updates,
            source="shear_fail_bending_overdesign_virtual_shear_repair",
            label=label,
            action_type="apply_resolved_candidate",
        )
    except Exception as exc:
        if isinstance(debug_sink, dict):
            debug_sink["mixed_virtual_shear_eval_error"] = type(exc).__name__
        _skip("mandatory_shear_eval_error", error=type(exc).__name__)
        return None
    if not isinstance(shear_eval, dict):
        _skip("mandatory_shear_eval_missing")
        return None
    post_shear_overview = dict(shear_eval.get("overview") or {})
    if not _overview_required_checks_acceptable(post_shear_overview) or bool(post_shear_overview.get("any_fail")):
        _skip("mandatory_shear_eval_not_safe", post_shear_overview=dict(post_shear_overview))
        return None
    post_shear_state = dict(shear_eval.get("state") or state)
    post_shear_state.update(shear_updates)
    target_low, target_high, _ = _resolved_efficiency_target_band(
        mode_config,
        goal=_design_optimisation_goal(state),
    )

    try:
        cleanup_item = _family_ladder_guidance_item(
            post_shear_state,
            post_shear_overview,
            mode_config,
            strengthening=False,
            debug_sink=None,
        )
    except Exception as exc:
        if isinstance(debug_sink, dict):
            debug_sink["mixed_virtual_cleanup_search_error"] = type(exc).__name__
        _skip("virtual_cleanup_search_error", error=type(exc).__name__)
        return None
    cleanup_payload: dict[str, Any] = {}
    cleanup_contract: dict[str, Any] = {}
    cleanup_updates: dict[str, Any] = {}
    cleanup_item_title = ""
    if isinstance(cleanup_item, dict) and _guidance_item_is_resolved_one_click(cleanup_item):
        cleanup_item_title = str(cleanup_item.get("title_main") or cleanup_item.get("title") or "")
        cleanup_payload = dict(cleanup_item.get("action_payload") or {})
        cleanup_contract = dict(cleanup_item.get("button_contract") or {})
        cleanup_updates = dict(
            cleanup_contract.get("updates")
            or cleanup_payload.get("resolved_candidate_updates")
            or cleanup_payload.get("updates")
            or cleanup_item.get("updates")
            or {}
        )
    else:
        try:
            current_width = float(state.get("b") or state.get("bw") or 0.0)
        except Exception:
            current_width = 0.0
        width_key = "b" if "b" in state or "bw" not in state else "bw"
        for width in range(int(current_width) - 10, 249, -10):
            if width <= 0:
                continue
            trial_cleanup_updates = {width_key: float(width)}
            trial_updates = dict(shear_updates)
            trial_updates.update(trial_cleanup_updates)
            try:
                trial_candidate = _evaluate_auto_design_candidate(
                    state,
                    updates=trial_updates,
                    source="shear_fail_bending_overdesign_width_cleanup_probe",
                    label=label,
                    action_type="apply_resolved_candidate",
                )
            except Exception:
                trial_candidate = None
            if not isinstance(trial_candidate, dict):
                continue
            trial_overview = dict(trial_candidate.get("overview") or {})
            if not _overview_required_checks_acceptable(trial_overview) or bool(trial_overview.get("any_fail")):
                continue
            trial_util = _parse_util_value(
                trial_candidate.get("candidate_post_util")
                or trial_candidate.get("worst_util")
                or trial_overview.get("worst_util")
                or trial_overview.get("governing_util")
            )
            if trial_util is None or not (float(target_low) <= float(trial_util) <= float(target_high)):
                continue
            cleanup_updates = dict(trial_cleanup_updates)
            cleanup_item_title = f"Width cleanup {int(current_width)} to {int(width)}"
        if not cleanup_updates:
            _skip(
                "virtual_cleanup_item_not_resolved_one_click",
                cleanup_item_title=str((cleanup_item or {}).get("title_main") or (cleanup_item or {}).get("title") or ""),
            )
            return None
    if not (set(cleanup_updates) & cleanup_update_keys):
        _skip("virtual_cleanup_missing_bending_or_geometry_updates", cleanup_updates=dict(cleanup_updates))
        return None
    merged_updates = dict(shear_updates)
    merged_updates.update(cleanup_updates)
    if merged_updates == shear_updates:
        _skip("merged_updates_equal_shear_updates", merged_updates=dict(merged_updates))
        return None

    try:
        merged_candidate = _evaluate_auto_design_candidate(
            state,
            updates=merged_updates,
            source="shear_fail_bending_overdesign_virtual_merged_one_click",
            label=label,
            action_type="apply_resolved_candidate",
        )
    except Exception as exc:
        if isinstance(debug_sink, dict):
            debug_sink["mixed_virtual_merged_eval_error"] = type(exc).__name__
        _skip("merged_eval_error", error=type(exc).__name__)
        return None
    if not isinstance(merged_candidate, dict):
        _skip("merged_eval_missing")
        return None
    merged_overview = dict(merged_candidate.get("overview") or {})
    if not _overview_required_checks_acceptable(merged_overview) or bool(merged_overview.get("any_fail")):
        _skip("merged_eval_not_safe", merged_overview=dict(merged_overview))
        return None
    merged_util = _parse_util_value(
        merged_candidate.get("candidate_post_util")
        or merged_candidate.get("worst_util")
        or merged_overview.get("worst_util")
        or merged_overview.get("governing_util")
    )
    if merged_util is None or not (float(target_low) <= float(merged_util) <= float(target_high)):
        _skip(
            "merged_util_outside_target_band",
            merged_util=merged_util,
            target_low=float(target_low),
            target_high=float(target_high),
            merged_updates=dict(merged_updates),
        )
        return None

    family_id = "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"
    source_candidate_id = str(
        source_candidate.get("candidate_id")
        or source_candidate.get("source_candidate_id")
        or "shear_repair"
    )
    cleanup_candidate_id = str(
        cleanup_item.get("candidate_id")
        or cleanup_item.get("source_candidate_id")
        or cleanup_contract.get("candidate_id")
        or "bending_cleanup"
    )
    candidate_id = f"{source_candidate_id}+{cleanup_candidate_id}"
    evidence = {
        "source": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS.virtual_post_shear_merge",
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "card_family_id": family_id,
        "candidate_family_id": family_id,
        "apply_payload_family_id": family_id,
        "active_failures": ["shear"],
        "family_utils": dict(family_utils),
        "governing_family": governing_family,
        "mandatory_source_family_id": "SHEAR_FAIL_GOVERNS",
        "opportunistic_source_family_id": "BENDING_OVERDESIGN_GOVERNS",
        "mandatory_source_candidate_id": source_candidate_id,
        "opportunistic_source_candidate_id": cleanup_candidate_id,
        "mandatory_source_updates": dict(shear_updates),
        "opportunistic_source_updates": dict(cleanup_updates),
        "opportunistic_source_title": cleanup_item_title,
        "selected_candidate_id": candidate_id,
        "selected_candidate_updates": dict(merged_updates),
        "selected_candidate_preview_pass": True,
        "selected_candidate_post_util": merged_util,
        "candidate_reaches_target_band": True,
        "target_band_candidate_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "executable_repair_candidate_count": 1,
        "safe_repair_candidate_count": 1,
        "mixed_merge_proof": {
            "mandatory_shear_repair_included": True,
            "opportunistic_bending_cleanup_included": True,
            "merged_preview_required_checks_pass": True,
            "merged_preview_util": merged_util,
            "target_low": float(target_low),
            "target_high": float(target_high),
        },
    }
    merged_candidate["updates"] = dict(merged_updates)
    merged_candidate["candidate_id"] = candidate_id
    merged_candidate["source_candidate_id"] = candidate_id
    merged_candidate["label"] = label
    merged_candidate["action_type"] = "apply_resolved_candidate"
    merged_candidate["candidate_reaches_target_band"] = True
    merged_candidate["reaches_target_band"] = True
    merged_candidate["is_compliant"] = True
    merged_candidate["candidate_search_evidence"] = dict(evidence)
    item = _guidance_item_from_resolved_candidate(
        merged_candidate,
        state=state,
        overview=overview,
        title=label,
        reasoning=(
            "This one-click update repairs the active shear failure and includes the verified "
            "bending cleanup that would otherwise be offered as a second step."
        ),
        status="FAIL",
        primary_action="Apply recommendation",
    )
    if not isinstance(item, dict):
        _skip("merged_guidance_item_missing")
        return None
    button_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": family_id,
        "family_id": family_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id,
        "updates": dict(merged_updates),
        "preview_pass": True,
        "expected_util": merged_util,
        "blocking_reason": None,
        "disabled_reason": None,
        "source_candidate_id": candidate_id,
        "candidate_id": candidate_id,
    }
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
        "candidate_family_id",
        "card_family_id",
    ):
        item[key] = family_id
    item["guidance_intent"] = "required_fix"
    item["primary_card_actionable"] = True
    item["candidate_search_evidence"] = dict(evidence)
    item["candidate_id"] = candidate_id
    item["source_candidate_id"] = candidate_id
    item["button_contract"] = dict(button_contract)
    payload = dict(item.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["resolved_candidate_updates"] = dict(merged_updates)
    payload["resolved_candidate_action_type"] = "apply_resolved_candidate"
    payload["button_contract"] = dict(button_contract)
    payload["source_candidate_id"] = candidate_id
    payload["family"] = family_id
    payload["family_id"] = family_id
    payload["selected_family_id"] = family_id
    payload["published_family_id"] = family_id
    payload["cta_family_id"] = family_id
    payload["apply_payload_family_id"] = family_id
    item["action_payload"] = payload
    primary_valid, primary_meta = _candidate_is_valid_primary_one_click(item, overview)
    if not primary_valid:
        if isinstance(debug_sink, dict):
            debug_sink["mixed_virtual_primary_rejected"] = True
            debug_sink["mixed_virtual_primary_rejected_reason"] = str(primary_meta.get("reason") or "")
        _skip("merged_primary_contract_rejected", reason=str(primary_meta.get("reason") or ""))
        return None
    if isinstance(debug_sink, dict):
        debug_sink.update(
            {
                "guidance_branch": "critical_shear_fail_bending_overdesign_virtual_merge",
                "mixed_virtual_merge_promoted": True,
                "mixed_virtual_merge_selected_candidate_id": candidate_id,
                "mixed_virtual_merge_updates": dict(merged_updates),
                "mixed_virtual_merge_expected_util": merged_util,
                "candidate_search_evidence": dict(evidence),
                "selected_action_type": item.get("action_type"),
                "selected_title": item.get("title_main"),
                "one_click_primary_candidate_valid": True,
                "one_click_primary_candidate_valid_reason": "mixed_virtual_merge_full_failure_coverage",
            }
        )
    return item


def _normalise_active_failure_blocker_contract_identity(
    guidance_items: list[dict] | None,
    *,
    overview: dict | None,
) -> list[dict]:
    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict((overview or {}).get("statuses") or {}).items()
    }
    active_strength_failures = {
        key for key in ("bending", "shear") if statuses.get(key) == "FAIL"
    }
    if len(active_strength_failures) != 1:
        return list(guidance_items or [])
    active_family = next(iter(active_strength_failures))
    blocker_family_id = "BENDING_FAIL_GOVERNS" if active_family == "bending" else "SHEAR_FAIL_GOVERNS"
    out: list[dict] = []
    for raw_item in list(guidance_items or []):
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        button = dict(item.get("button_contract") or {})
        blocking_reason = str(button.get("blocking_reason") or button.get("disabled_reason") or "").strip()
        if not (
            button
            and button.get("preview_pass") is False
            and blocking_reason == "candidate_preview_has_fail_status"
        ):
            out.append(item)
            continue
        title_text = " ".join(
            str(value or "")
            for value in (
                item.get("title_main"),
                item.get("title"),
                item.get("primary_action"),
                item.get("secondary_action"),
            )
        ).lower()
        if active_family not in title_text and "capacity is low" not in title_text:
            out.append(item)
            continue
        family_identity = {
            "family": blocker_family_id,
            "family_id": blocker_family_id,
            "selected_family_id": blocker_family_id,
            "published_family_id": blocker_family_id,
            "cta_family_id": blocker_family_id,
            "apply_payload_family_id": blocker_family_id,
            "candidate_family_id": blocker_family_id,
            "card_family_id": blocker_family_id,
        }
        item.update(family_identity)
        item["primary_card_actionable"] = False
        payload = dict(item.get("action_payload") or {})
        payload.update(family_identity)
        item["action_payload"] = payload
        resolved = dict(item.get("resolved_candidate") or {})
        resolved.update(family_identity)
        item["resolved_candidate"] = resolved
        button.update(
            {
                **family_identity,
                "enabled": False,
                "actionable": False,
                "action_type": None,
                "updates": {},
                "preview_pass": False,
                "expected_util": None,
                "source_candidate_id": None,
                "candidate_id": None,
            }
        )
        item["button_contract"] = dict(button)
        out.append(item)
    return out


def _post_click_bending_exact_blocker_has_contract_proof(blocker: dict | None) -> bool:
    row = dict(blocker or {})
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "best_rejected_candidate_id",
            "failed_check_name",
            "why_reduction_would_hurt_other_design_elements",
            "reason_reducing_this_family_would_affect_other_design_elements",
            "reason",
        )
    ).strip().lower()
    if (
        "bending_cleanup_floor_shear_or_detailing_limited" in text
        or "safe local floor" in text
        or "further bending cleanup is blocked" in text
    ):
        return False
    if bool(row.get("exact_stop_proven") or row.get("exact_stop_available") or row.get("contract_exact_stop_proven")):
        return True

    def _is_zero(value: Any) -> bool:
        try:
            return float(value) == 0.0
        except Exception:
            return False

    cleanup_ran = bool(
        row.get("post_click_bending_cleanup_search_ran")
        or row.get("bending_cleanup_search_ran")
        or row.get("local_cleanup_search_ran")
    )
    cleanup_exhaustive = bool(
        row.get("post_click_bending_cleanup_search_exhaustive")
        or row.get("bending_cleanup_search_exhaustive")
        or row.get("local_cleanup_search_exhaustive")
        or row.get("candidate_search_exhaustive")
    )
    safe_count = (
        row.get("post_click_safe_bending_cleanup_count")
        if row.get("post_click_safe_bending_cleanup_count") is not None
        else row.get("safe_bending_cleanup_count")
    )
    executable_count = (
        row.get("post_click_executable_bending_cleanup_count")
        if row.get("post_click_executable_bending_cleanup_count") is not None
        else row.get("executable_bending_cleanup_count")
    )
    return bool(cleanup_ran and cleanup_exhaustive and _is_zero(safe_count) and _is_zero(executable_count))


def _post_click_acceptance_audit_allows_green(audit: dict | None) -> bool:
    data = dict(audit or {})
    if not bool(data.get("post_click_accepted_green_valid")):
        return False
    low_families = {
        str(family or "").strip().lower()
        for family in list(
            data.get("post_click_families_below_final_threshold")
            or data.get("post_click_materially_overprovided_families")
            or []
        )
        if str(family or "").strip()
    }
    if "bending" not in low_families:
        return True
    blockers = dict(data.get("post_click_exact_blockers_by_family") or {})
    return _post_click_bending_exact_blocker_has_contract_proof(dict(blockers.get("bending") or {}))


def _post_click_low_util_blocker_item(
    guidance_state: dict,
    overview: dict,
    audit: dict | None,
) -> dict | None:
    del guidance_state, overview
    data = dict(audit or {})
    low_families = [
        str(family or "").strip().lower()
        for family in list(
            data.get("post_click_unresolved_low_util_families")
            or data.get("post_click_families_below_final_threshold")
            or data.get("post_click_materially_overprovided_families")
            or []
        )
        if str(family or "").strip()
    ]
    if not low_families:
        return None
    family = "bending" if "bending" in low_families else low_families[0]
    blockers = dict(data.get("post_click_exact_blockers_by_family") or {})
    blocker = dict(blockers.get(family) or {})
    utils = dict(data.get("post_click_family_utils_meaningful") or data.get("post_click_family_utils") or {})
    util = _parse_util_value(blocker.get("current_util") or utils.get(family))
    title = (
        "Bending cleanup proof is required"
        if family == "bending"
        else f"{family.title()} cleanup proof is required"
    )
    reason = (
        "Why: the current post-click state is inside the governing target band, but bending remains below the "
        "final accepted family floor and no validated bending cleanup contract proof is attached. The Design Guide "
        "cannot publish an accepted terminal card until that cleanup proof exists or a valid cleanup action is available."
        if family == "bending"
        else (
            "Why: the current post-click state is inside the governing target band, but a meaningful family remains "
            "below the final accepted floor without validated cleanup proof."
        )
    )
    item = _guidance_item(
        family,
        title,
        "",
        None,
        reason,
        "Required proof: executor-backed cleanup search, exact-stop evidence, and post-click family utilisation.",
        None,
        None,
        status="BLOCKED",
        util=util,
    )
    family_id = f"{family.upper()}_CLEANUP_PROOF_BLOCKED" if family else "POST_CLICK_CLEANUP_PROOF_BLOCKED"
    contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": family_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id,
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": "missing_validated_post_click_cleanup_proof",
        "disabled_reason": "missing_validated_post_click_cleanup_proof",
        "source_candidate_id": None,
        "candidate_id": None,
    }
    evidence = dict(data)
    evidence["post_click_accepted_green_valid"] = False
    evidence["post_click_accepted_green_invalid_reason"] = str(
        data.get("post_click_accepted_green_invalid_reason")
        or "missing_validated_post_click_cleanup_proof"
    )
    item["guidance_intent"] = "specific_blocker"
    item["design_guide_terminal_state"] = None
    item["button_contract"] = dict(contract)
    item["candidate_search_evidence"] = dict(evidence)
    item["post_click_exact_blockers_by_family"] = dict(blockers)
    item["post_click_cleanup_evidence_by_family"] = dict(
        data.get("post_click_cleanup_evidence_by_family") or blockers
    )
    item["terminal_state_blocked_by_local_cleanup"] = True
    item["terminal_state_reason"] = contract["blocking_reason"]
    return item


def _family_ladder_terminal_exact_stop_item(
    family_result: dict,
    overview: dict,
) -> dict:
    """Publish a family-proven current-state exact stop with no CTA."""

    evidence = dict(family_result or {})
    family_id = "EXACT_STOP_PROVEN"
    source_candidate_id = (
        "COMBINED_OVERDESIGN:current_state_terminal_exact_stop"
    )
    util = _parse_util_value(
        (overview or {}).get("worst_util")
        or (overview or {}).get("governing_util")
    )
    item = _guidance_item(
        family_id,
        "Design is efficient - further reductions would weaken capacity",
        "",
        None,
        (
            "No further safe cleanup available. Further reductions would "
            "lower reserve capacity or stiffness; the family ladders found "
            "no material one-click change from the current design."
        ),
        "Key checks: bending, shear, serviceability, target utilisation band",
        None,
        None,
        status="PASS",
        util=util,
    )
    button_contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": family_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id,
        "candidate_family_id": family_id,
        "card_family_id": family_id,
        "updates": {},
        "preview_pass": True,
        "blocking_reason": None,
        "disabled_reason": "terminal_pass_no_action",
        "source_candidate_id": source_candidate_id,
        "candidate_id": source_candidate_id,
    }
    item.update(evidence)
    item.update(
        {
            "family": family_id,
            "family_id": family_id,
            "selected_family": family_id,
            "selected_family_id": family_id,
            "published_family_id": family_id,
            "cta_family_id": family_id,
            "apply_payload_family_id": family_id,
            "candidate_family_id": family_id,
            "card_family_id": family_id,
            "matched_family_ids": [family_id],
            "family_match_passed": True,
            "guidance_intent": "already_efficient",
            "design_guide_terminal_state": "optimal",
            "status": "PASS",
            "outcome_state": "PASS",
            "display_state": "PASS",
            "critical_status": "PASS",
            "action_type": None,
            "action_payload": {
                "candidate_search_evidence": dict(evidence),
                "button_contract": dict(button_contract),
                "source_candidate_id": source_candidate_id,
                "updates": {},
            },
            "button_contract": dict(button_contract),
            "candidate_search_evidence": dict(evidence),
            "source_candidate_id": source_candidate_id,
            "candidate_id": source_candidate_id,
            "render_cta_payload_id": source_candidate_id,
            "exact_stop_proven": True,
            "exact_stop_proof": dict(
                evidence.get("exact_stop_proof") or {}
            ),
            "terminal_state_reason": (
                "combined_overdesign_current_state_exact_stop"
            ),
        }
    )
    return item


def _family_ladder_exhaustion_blocker_item(
    family_result: dict,
    overview: dict,
    critical: list[dict],
) -> dict:
    """Publish family-owned ladder exhaustion without entering another search."""

    evidence = dict(family_result or {})
    family_id = str(
        evidence.get("selected_family_id")
        or evidence.get("selected_family")
        or "FAMILY_SELECTION_CONTRACT_VIOLATION"
    ).strip()
    source_candidate_id = f"{family_id}:family_ladder_exhausted"
    reason = str(
        evidence.get("blocking_reason")
        or f"No safe one-click repair was found for {family_id}."
    ).strip()
    base_item = dict(critical[0]) if critical else {}
    utils = dict((overview or {}).get("utils") or {})
    active_failures = [
        str(value).strip().lower()
        for value in list(evidence.get("active_failures") or [])
        if str(value).strip()
    ]
    check_key = active_failures[0] if active_failures else str(
        base_item.get("check_key") or "design"
    )
    util = _parse_util_value(base_item.get("util") or utils.get(check_key))
    item = _guidance_item(
        check_key,
        str(base_item.get("title_main") or base_item.get("title") or "Design repair is blocked"),
        "",
        None,
        reason,
        "Use the family ladder evidence to change a locked input or widen the permitted design space.",
        None,
        None,
        status="BLOCKED",
        util=util,
    )
    button_contract = {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": family_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id,
        "candidate_family_id": family_id,
        "card_family_id": family_id,
        "updates": {},
        "preview_pass": False,
        "blocking_reason": reason,
        "disabled_reason": "family_ladder_exhausted",
        "source_candidate_id": source_candidate_id,
        "candidate_id": source_candidate_id,
    }
    item.update(evidence)
    item.update(
        {
            "guidance_intent": "specific_blocker",
            "status": "BLOCKED",
            "outcome_state": "BLOCKED",
            "action_type": None,
            "action_payload": {
                "candidate_search_evidence": dict(evidence),
                "button_contract": dict(button_contract),
                "source_candidate_id": source_candidate_id,
            },
            "button_contract": dict(button_contract),
            "candidate_search_evidence": dict(evidence),
            "source_candidate_id": source_candidate_id,
            "candidate_id": source_candidate_id,
            "render_cta_payload_id": source_candidate_id,
            "family_match_passed": bool(evidence.get("classification_passed")),
            "family_match_violation_reason": (
                ""
                if evidence.get("classification_passed")
                else "family_ladder_exhaustion_classification_not_proven"
            ),
            "exact_blockers_by_family": dict(
                evidence.get("exact_blockers_by_family") or {}
            ),
            "post_click_exact_blockers_by_family": dict(
                evidence.get("post_click_exact_blockers_by_family") or {}
            ),
            "terminal_state_reason": reason,
        }
    )
    return item


def compute_design_guidance_items_core(
    runtime: GuidanceComputeRuntime,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
    state: dict,
    debug_sink: dict | None = None,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
) -> list[dict]:
    _bind_guidance_compute_runtime(
        runtime=runtime,
        st_module=st_module,
        os_module=os_module,
        sys_module=sys_module,
    )
    return _compute_design_guidance_items_core(
        state,
        debug_sink,
        guidance_debug_verbose=guidance_debug_verbose,
        debug_enabled=debug_enabled,
    )


def compute_design_guidance_items(
    runtime: GuidanceComputeRuntime,
    st_module: Any,
    os_module: Any,
    sys_module: Any,
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    _bind_guidance_compute_runtime(
        runtime=runtime,
        st_module=st_module,
        os_module=os_module,
        sys_module=sys_module,
    )
    return _compute_design_guidance_items(
        state,
        guidance_debug_verbose=guidance_debug_verbose,
        debug_enabled=debug_enabled,
        request_kind=request_kind,
    )


def _geometry_detailing_not_started_guidance_item(state: dict | None) -> dict | None:
    """Adapt a family-owned geometry/detailing repair into the existing guidance item shape."""

    try:
        result = run_geometry_detailing_governs_runtime(dict(state or {}))
    except Exception:
        return None
    if str(getattr(result, "status", "") or "").strip().upper() != "ACTION":
        return None
    selected = dict(getattr(result, "selected_recommendation", None) or {})
    updates = dict(selected.get("updates") or {})
    if not updates:
        return None
    ratio_after = selected.get("depth_width_ratio_after")
    ratio_limit = selected.get("maximum_depth_width_ratio")
    try:
        preview_pass = float(ratio_after) <= float(ratio_limit) + 1e-9
    except Exception:
        preview_pass = False
    if not preview_pass:
        return None
    candidate_id = str(selected.get("candidate_id") or selected.get("update_hash") or "").strip()
    width_label = str(selected.get("width_label") or "Width").strip()
    width_before = selected.get("width_before")
    width_after = selected.get("width_after")
    try:
        change_line = f"Change: {width_label} {float(width_before):.0f} -> {float(width_after):.0f} mm"
    except Exception:
        change_line = f"Change: {width_label} -> {width_after} mm"
    resolved_candidate = {
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "label": "Apply geometry correction",
        "action_type": "apply_geometry_recommendation",
        "family": "geometry_detailing",
        "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
        "updates": dict(updates),
        "candidate_state_hash": selected.get("candidate_state_hash"),
        "update_hash": selected.get("update_hash"),
    }
    payload = {
        "updates": dict(updates),
        "resolved_candidate_updates": dict(updates),
        "resolved_candidate_label": "Apply geometry correction",
        "resolved_candidate_action_type": "apply_geometry_recommendation",
        "resolved_candidate_family_tag": "geometry_detailing",
        "resolved_candidate": dict(resolved_candidate),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
        "published_family_id": "GEOMETRY_DETAILING_GOVERNS",
        "cta_family_id": "GEOMETRY_DETAILING_GOVERNS",
        "apply_payload_family_id": "GEOMETRY_DETAILING_GOVERNS",
        "guidance_change_lines": [change_line],
    }
    item = _guidance_item(
        "geometry_detailing",
        str(selected.get("title") or "Geometry needs correction"),
        "Apply geometry correction",
        None,
        str(selected.get("reason") or "Increase width so the section satisfies the geometry/detailing contract."),
        "Key levers: width, depth-to-width ratio, detailing limits",
        "apply_resolved_candidate",
        payload,
        status="ACTION",
        util=None,
        guidance_change_lines=[change_line],
        guidance_why="Why: the current geometry/detailing contract is invalid before normal design recommendations can run.",
    )
    item.update(
        {
            "family": "geometry_detailing",
            "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
            "published_family_id": "GEOMETRY_DETAILING_GOVERNS",
            "cta_family_id": "GEOMETRY_DETAILING_GOVERNS",
            "apply_payload_family_id": "GEOMETRY_DETAILING_GOVERNS",
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
            "resolved_candidate": dict(resolved_candidate),
            "candidate_search_evidence": {
                "source": "geometry_detailing_not_started_override",
                "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "published_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "cta_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "selected_candidate_id": candidate_id,
                "safe_executor_backed_candidates_count": 1,
                "executable_repair_candidate_count": 1,
                "safe_repair_candidate_count": 1,
                "repair_search_ran": True,
                "candidate_search_ran": True,
                "updates": dict(updates),
                "repair_reason_proof": dict(getattr(result, "repair_reason_proof", {}) or {}),
            },
            "guidance_intent": "required_fix",
            "geometry_detailing_preview_pass": True,
            "geometry_detailing_runtime_status": "ACTION",
            "geometry_detailing_runtime_hash": getattr(result, "runtime_hash", ""),
        }
    )
    return item


def _truthy_state_flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "pass", "passed", "active", "proven"}
    return bool(value)


def _locked_no_repair_state_signal(state: dict | None) -> bool:
    source = dict(state or {})
    return any(
        _truthy_state_flag(source.get(key))
        for key in (
            "locked_no_repair",
            "no_valid_repair_available",
            "all_repair_paths_locked",
            "locked_repair_blocked",
            "repair_blocked_by_lock",
        )
    )


def _locked_no_repair_guidance_item(state: dict | None) -> dict:
    reason = "Locked inputs or no valid repair path prevent a legal change."
    item = _guidance_item(
        "LOCKED_NO_REPAIR",
        "No legal repair is available",
        reason,
        None,
        reason,
        "Key levers: unlock inputs or revise the design constraints",
        None,
        None,
        status="BLOCKED",
        util=None,
    )
    item.update(
        {
            "family": "LOCKED_NO_REPAIR",
            "check_key": "LOCKED_NO_REPAIR",
            "selected_family_id": "LOCKED_NO_REPAIR",
            "selected_family": "LOCKED_NO_REPAIR",
            "published_family_id": "LOCKED_NO_REPAIR",
            "cta_family_id": "LOCKED_NO_REPAIR",
            "apply_payload_family_id": "LOCKED_NO_REPAIR",
            "candidate_family_id": "LOCKED_NO_REPAIR",
            "card_family_id": "LOCKED_NO_REPAIR",
            "guidance_intent": "required_fix_blocked",
            "status": "BLOCKED",
            "critical_status": "BLOCKED",
            "bucket": "fail",
            "tone": "blocked",
            "pill": "BLOCKED",
            "display_state": "BLOCKED",
            "final_state_class": "blocker",
            "primary_card_actionable": False,
            "blocker_explanation": reason,
            "blocking_reason": "locked_no_valid_repair",
            "locked_no_repair": True,
            "locked_repair_blocked": True,
            "no_valid_repair_available": True,
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": "LOCKED_NO_REPAIR",
                "selected_family_id": "LOCKED_NO_REPAIR",
                "published_family_id": "LOCKED_NO_REPAIR",
                "cta_family_id": "LOCKED_NO_REPAIR",
                "apply_payload_family_id": "LOCKED_NO_REPAIR",
                "action_type": None,
                "updates": {},
                "preview_pass": False,
                "blocking_reason": "locked_no_valid_repair",
                "disabled_reason": reason,
            },
            "candidate_search_evidence": {
                "source": "locked_no_repair_state_signal",
                "selected_family_id": "LOCKED_NO_REPAIR",
                "published_family_id": "LOCKED_NO_REPAIR",
                "cta_family_id": "LOCKED_NO_REPAIR",
                "card_family_id": "LOCKED_NO_REPAIR",
                "apply_payload_family_id": "LOCKED_NO_REPAIR",
                "locked_no_repair": True,
                "locked_repair_blocked": True,
                "no_valid_repair_available": True,
                "all_repair_paths_locked": bool(_truthy_state_flag((state or {}).get("all_repair_paths_locked"))),
                "repair_search_ran": True,
                "candidate_search_ran": True,
                "safe_executor_backed_candidates_count": 0,
                "executable_repair_candidate_count": 0,
                "safe_repair_candidate_count": 0,
                "updates": {},
            },
        }
    )
    return item


def _compute_design_guidance_items_core(
    state: dict,
    debug_sink: dict | None = None,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
) -> list[dict]:
    _core_stage_debug = os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    if _core_stage_debug:
        print("DG_STAGE core_entry", file=sys.stderr, flush=True)
    design_context = _build_design_actions_context(state)
    if _core_stage_debug:
        print("DG_STAGE core_after_context", file=sys.stderr, flush=True)
    guidance_state = dict(design_context.get("state") or _guidance_state_snapshot(state))
    overview = _collect_design_overview(guidance_state, context=design_context)
    if _core_stage_debug:
        print(
            f"DG_STAGE core_after_overview any_fail={bool(overview.get('any_fail'))} all_pass={bool(overview.get('all_key_pass'))} worst={overview.get('worst_util')}",
            file=sys.stderr,
            flush=True,
        )
    mode_config = _design_mode_config(_design_optimisation_goal(guidance_state))
    target_band_with_eps_passed = _is_in_target_zone_with_eps(overview, mode_config, eps=TARGET_BAND_EPS)
    if _core_stage_debug:
        print(f"DG_STAGE core_after_target_check target={target_band_with_eps_passed}", file=sys.stderr, flush=True)
    guidance_branch = "unknown"
    _verbose = True if guidance_debug_verbose is None else bool(guidance_debug_verbose)
    _sink_is_dict = isinstance(debug_sink, dict)
    full_dbg = _sink_is_dict and _verbose
    min_dbg = _sink_is_dict and _verbose
    if min_dbg:
        debug_sink["guidance_resolved_state"] = guidance_state
    if full_dbg:
        debug_sink["overview"] = overview
        debug_sink["overview_actions_used"] = overview.get("actions_used")
        debug_sink["guidance_actions_used"] = dict(design_context.get("actions") or {})
        debug_sink["target_band_eps"] = float(TARGET_BAND_EPS)
        debug_sink["target_band_with_eps_passed"] = bool(target_band_with_eps_passed)
    if _core_stage_debug:
        print("DG_STAGE core_before_not_started_check", file=sys.stderr, flush=True)
    _not_started = _guidance_not_started(guidance_state, overview)
    if _core_stage_debug:
        print(f"DG_STAGE core_after_not_started_check not_started={_not_started}", file=sys.stderr, flush=True)
    if _not_started:
        guidance_branch = "not_started"
        if _core_stage_debug:
            print("DG_STAGE core_before_start_item", file=sys.stderr, flush=True)
        start_item = _guidance_start_item(guidance_state)
        if _core_stage_debug:
            print("DG_STAGE core_after_start_item", file=sys.stderr, flush=True)
        if _sink_is_dict:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = start_item.get("action_type")
            debug_sink["selected_title"] = start_item.get("title_main")
        return [start_item]
    _post_apply_acceptance_audit = {}
    if _local_cleanup_post_apply_acceptance_matches(guidance_state):
        _post_apply_acceptance_audit = _post_click_accepted_green_audit(
            overview,
            blocker_source=debug_sink if isinstance(debug_sink, dict) else None,
            state=guidance_state,
        )
        if min_dbg:
            debug_sink.update(_post_apply_acceptance_audit)
    if (
        _local_cleanup_post_apply_acceptance_matches(guidance_state)
        and not bool(overview.get("any_fail"))
        and bool(target_band_with_eps_passed)
        and bool(_post_click_acceptance_audit_allows_green(_post_apply_acceptance_audit))
    ):
        guidance_branch = "post_apply_local_cleanup_accepted"
        accepted_util = _parse_util_value(overview.get("worst_util") or overview.get("governing_util"))
        target_lo, target_hi, _ = _resolved_efficiency_target_band(
            mode_config,
            goal=_design_optimisation_goal(guidance_state),
        )
        accepted_item = _guidance_item(
            "general",
            "Design accepted - target band achieved",
            "The one-click cleanup has been applied and the current design is inside the target band.",
            None,
            "Why: all required checks remain acceptable, governing utilisation is inside the target band, and this is the accepted post-click Design Guide state.",
            "Key checks: bending, shear, serviceability, target utilisation band",
            None,
            None,
            status="PASS",
            util=accepted_util,
        )
        accepted_item["guidance_intent"] = "already_efficient"
        accepted_item["design_guide_terminal_state"] = "optimal"
        accepted_item["display_truth"] = {
            "display_truth_source": "published_summary",
            "displayed_util": accepted_util,
            "displayed_status": "OPTIMAL",
            "target_low": float(target_lo),
            "target_high": float(target_hi),
            "displayed_within_target_band": True,
            "source_summary_util": accepted_util,
            "source_candidate_util": None,
            "source_post_commit_util": accepted_util,
        }
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = None
            debug_sink["selected_title"] = accepted_item.get("title_main")
            debug_sink["post_click_accepted_green"] = True
            debug_sink["post_click_accepted_green_valid"] = True
            debug_sink["post_click_design_guide_state"] = "accepted_green"
            debug_sink["post_click_executable_safe_cleanup_count"] = 0
            debug_sink["safe_local_cleanup_count"] = 0
            debug_sink["executable_safe_cleanup_count"] = 0
            debug_sink["local_cleanup_search_ran"] = False
            debug_sink["local_cleanup_search_exhaustive"] = True
            debug_sink["terminal_state_reason"] = "post_apply_cleanup_state_accepted"
        return [accepted_item]
    if (
        _local_cleanup_post_apply_acceptance_matches(guidance_state)
        and not bool(_post_click_acceptance_audit_allows_green(_post_apply_acceptance_audit))
        and min_dbg
    ):
        debug_sink["post_click_accepted_green"] = False
        debug_sink["terminal_state_blocked_by_local_cleanup"] = True
        debug_sink["terminal_state_blocked_reason"] = str(
            _post_apply_acceptance_audit.get("post_click_accepted_green_invalid_reason")
            or "post_apply_cleanup_state_has_unresolved_overprovided_family"
        )
    governing_action, primary_utils = _guidance_governing_primary_action(overview)
    if full_dbg:
        debug_sink["governing_action"] = governing_action
        debug_sink["primary_utils"] = dict(primary_utils)
    packs = dict(overview.get("packs") or {})
    bend_pack = dict(packs.get("bending") or {})
    shear_pack = dict(packs.get("shear") or {})
    crack_pack = dict(packs.get("crack") or {})
    defl_pack = dict(packs.get("deflection") or {})

    items = [
        _bending_guidance_item(guidance_state, bend_pack),
        _shear_guidance_item(guidance_state, shear_pack),
        _crack_guidance_item(guidance_state, crack_pack),
        _deflection_guidance_item(guidance_state, defl_pack),
    ]
    filtered = [item for item in items if item is not None]
    filtered.sort(key=lambda item: item["priority"], reverse=True)
    governing_item = next(
        (item for item in filtered if str(item.get("check_key") or "") == str(governing_action or "")),
        None,
    )
    critical = [
        item for item in filtered
        if item["bucket"] in ("fail", "warn")
        and (
            item["bucket"] == "fail"
            or item.get("util") is None
            or item["util"] >= GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD
            or bool(overview.get("any_fail"))
            or bool(overview.get("any_warn"))
        )
    ]
    governing_item_is_critical = bool(governing_item and governing_item in critical)
    out_of_band_live = not (
        _overview_required_checks_acceptable(overview) and bool(target_band_with_eps_passed)
    )
    primary_one_click_requires_full_coverage, primary_one_click_fail_keys = (
        _requires_full_coverage_for_primary_one_click(overview)
    )
    primary_critical = (
        next(
            (
                item for item in critical
                if str(item.get("check_key") or "") == str(governing_action or "")
            ),
            critical[0],
        )
        if critical
        else None
    )
    if not bool(overview.get("any_fail")):
        reshape_item = _in_target_shear_congestion_reshape_guidance_item(
            guidance_state,
            overview,
            mode_config,
            debug_sink=debug_sink if full_dbg else None,
        )
        if reshape_item:
            guidance_branch = "in_target_shear_congestion_reshape"
            if full_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
                debug_sink["actionable_target_band_winner_exists"] = True
                debug_sink["actionable_target_band_winner_family"] = "compound"
                debug_sink["actionable_target_band_winner_subfamilies"] = ["geometry", "bottom_reo", "shear"]
                debug_sink["actionable_target_band_winner_change_lines"] = list(
                    reshape_item.get("guidance_change_lines") or []
                )
                debug_sink["optimal_short_circuit_blocked"] = True
                debug_sink["optimal_short_circuit_block_reason"] = "in_target_shear_congestion_reshape"
                debug_sink["surfaced_guidance_branch"] = guidance_branch
                debug_sink["surfaced_selected_action_type"] = reshape_item.get("action_type")
                debug_sink["surfaced_selected_title"] = reshape_item.get("title_main")
            elif min_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
            return [reshape_item]
    if (
        _overview_required_checks_acceptable(overview)
        and not bool(overview.get("any_fail"))
        and bool(target_band_with_eps_passed)
    ):
        if _core_stage_debug:
            print("DG_STAGE core_before_material_family_check", file=sys.stderr, flush=True)
        family_utils, material_families, governing_family = identify_materially_overprovided_non_governing_families(overview)
        if _core_stage_debug:
            print(f"DG_STAGE core_after_material_family_check families={material_families}", file=sys.stderr, flush=True)
        in_target_final_audit = _post_click_accepted_green_audit(
            overview,
            blocker_source=debug_sink if isinstance(debug_sink, dict) else None,
            state=guidance_state,
        )
        if bool(_post_click_acceptance_audit_allows_green(in_target_final_audit)):
            accepted_item = _optimal_guidance_item(guidance_state, overview)
            accepted_item["guidance_intent"] = "already_efficient"
            if min_dbg:
                debug_sink.update(in_target_final_audit)
                debug_sink["guidance_branch"] = "target_band_final_accepted"
                debug_sink["selected_action_type"] = None
                debug_sink["selected_title"] = accepted_item.get("title_main")
                debug_sink["post_click_accepted_green"] = True
                debug_sink["post_click_accepted_green_valid"] = True
                debug_sink["post_click_design_guide_state"] = "accepted_green"
                debug_sink["post_click_executable_safe_cleanup_count"] = 0
                debug_sink["safe_local_cleanup_count"] = 0
                debug_sink["executable_safe_cleanup_count"] = 0
                debug_sink["local_cleanup_search_ran"] = bool(material_families)
                debug_sink["local_cleanup_search_exhaustive"] = bool(material_families)
                debug_sink["terminal_state_reason"] = "target_band_final_accepted_with_exact_blockers"
            return [accepted_item]
        if material_families:
            try:
                if _core_stage_debug:
                    print("DG_STAGE core_before_direct_target_band_item", file=sys.stderr, flush=True)
                local_cleanup_item = _family_ladder_guidance_item(
                    guidance_state,
                    overview,
                    mode_config,
                    strengthening=False,
                    debug_sink=debug_sink if min_dbg else None,
                )
                if _core_stage_debug:
                    print(f"DG_STAGE core_after_direct_target_band_item item={bool(isinstance(local_cleanup_item, dict))}", file=sys.stderr, flush=True)
            except Exception:
                local_cleanup_item = None
            if (
                isinstance(local_cleanup_item, dict)
                and local_cleanup_item.get(
                    "family_ladder_terminal_exact_stop"
                )
            ):
                terminal_item = _family_ladder_terminal_exact_stop_item(
                    local_cleanup_item,
                    overview,
                )
                if min_dbg:
                    debug_sink.update(local_cleanup_item)
                    debug_sink["guidance_branch"] = (
                        "in_target_material_family_ladder_terminal_exact_stop"
                    )
                    debug_sink["selected_action_type"] = None
                    debug_sink["selected_title"] = terminal_item.get(
                        "title_main"
                    )
                    debug_sink[
                        "local_cleanup_promotion_suppressed_by_family_ladder"
                    ] = True
                return [terminal_item]
            if (
                isinstance(local_cleanup_item, dict)
                and local_cleanup_item.get("family_ladder_exhausted")
                and local_cleanup_item.get("legacy_fallback_allowed") is False
            ):
                blocked_item = _family_ladder_exhaustion_blocker_item(
                    local_cleanup_item,
                    overview,
                    filtered,
                )
                if min_dbg:
                    debug_sink.update(local_cleanup_item)
                    debug_sink["guidance_branch"] = (
                        "in_target_material_family_ladder_exhausted"
                    )
                    debug_sink["selected_action_type"] = None
                    debug_sink["selected_title"] = blocked_item.get("title_main")
                    debug_sink[
                        "local_cleanup_promotion_suppressed_by_family_ladder"
                    ] = True
                return [blocked_item]
            if isinstance(local_cleanup_item, dict) and _guidance_item_is_resolved_one_click(local_cleanup_item):
                local_cleanup_item["guidance_intent"] = "optional_cleanup"
                local_cleanup_item["local_cleanup_candidate"] = True
                if min_dbg:
                    evidence = dict(local_cleanup_item.get("candidate_search_evidence") or {})
                    debug_sink["guidance_branch"] = "in_target_material_local_cleanup"
                    debug_sink["selected_action_type"] = local_cleanup_item.get("action_type")
                    debug_sink["selected_title"] = local_cleanup_item.get("title_main")
                    debug_sink["family_utils"] = dict(family_utils)
                    debug_sink["materially_overprovided_families"] = list(material_families)
                    debug_sink["governing_family"] = governing_family
                    debug_sink["local_cleanup_search_ran"] = True
                    debug_sink["local_cleanup_search_exhaustive"] = True
                    debug_sink["safe_local_cleanup_count"] = int(evidence.get("safe_executor_backed_candidates_count") or 1)
                    debug_sink["local_cleanup_candidate_search_evidence"] = dict(evidence)
                    debug_sink["candidate_search_evidence"] = dict(evidence)
                    debug_sink["local_cleanup_candidate_inventory"] = list(evidence.get("safe_executor_backed_candidates") or [])
                    debug_sink["local_cleanup_candidate_inventory_count"] = len(debug_sink["local_cleanup_candidate_inventory"])
                    debug_sink["candidate_inventory_count"] = debug_sink["local_cleanup_candidate_inventory_count"]
                    debug_sink["terminal_state_blocked_by_local_cleanup"] = True
                return [local_cleanup_item]
            if "shear" in {str(f or "").strip().lower() for f in material_families}:
                shear_cleanup_item = _shear_tightening_as_local_cleanup_item(
                    guidance_state,
                    overview,
                    design_context.get("efficiency_state") if isinstance(design_context, dict) else None,
                )
                if isinstance(shear_cleanup_item, dict) and _guidance_item_is_resolved_one_click(shear_cleanup_item):
                    shear_cleanup_item["guidance_intent"] = "optional_cleanup"
                    shear_cleanup_item["local_cleanup_candidate"] = True
                    if min_dbg:
                        debug_sink["guidance_branch"] = "in_target_shear_material_local_cleanup"
                        debug_sink["selected_action_type"] = shear_cleanup_item.get("action_type")
                        debug_sink["selected_title"] = shear_cleanup_item.get("title_main")
                        debug_sink["family_utils"] = dict(family_utils)
                        debug_sink["materially_overprovided_families"] = list(material_families)
                        debug_sink["governing_family"] = governing_family
                        debug_sink["local_cleanup_search_ran"] = True
                        debug_sink["local_cleanup_search_exhaustive"] = True
                        debug_sink["safe_local_cleanup_count"] = 1
                        debug_sink["executable_safe_cleanup_count"] = 1
                        debug_sink["terminal_state_blocked_by_local_cleanup"] = True
                    return [shear_cleanup_item]
            unresolved_blocker_item = _post_click_low_util_blocker_item(
                guidance_state,
                overview,
                in_target_final_audit,
            )
            if isinstance(unresolved_blocker_item, dict):
                if min_dbg:
                    debug_sink.update(dict(unresolved_blocker_item.get("candidate_search_evidence") or {}))
                    debug_sink["guidance_branch"] = "in_target_post_click_cleanup_proof_blocked"
                    debug_sink["selected_action_type"] = None
                    debug_sink["selected_title"] = unresolved_blocker_item.get("title_main")
                    debug_sink["post_click_accepted_green"] = False
                    debug_sink["terminal_state_blocked_by_local_cleanup"] = True
                    debug_sink["terminal_state_reason"] = unresolved_blocker_item.get("terminal_state_reason")
                return [unresolved_blocker_item]
    # Every classified failure family owns its ordered ladder before any
    # generic recommendation path. The retired grid solver is deliberately not
    # available as a fallback.
    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in dict((overview or {}).get("statuses") or {}).items()
    }
    if bool(overview.get("any_fail")) and bool(critical):
        serviceability_family_owned = bool(
            (
                statuses.get("crack") == "FAIL"
                or statuses.get("deflection") == "FAIL"
            )
            and statuses.get("bending") != "FAIL"
            and statuses.get("shear") != "FAIL"
        )
        serviceability_contract_item = (
            _serviceability_contract_ladder_guidance_item(
                guidance_state,
                overview,
                debug_sink=debug_sink if min_dbg else None,
            )
        )
        if isinstance(serviceability_contract_item, dict):
            if min_dbg:
                debug_sink["guidance_branch"] = (
                    "critical_serviceability_contract_ladder"
                )
                debug_sink["selected_action_type"] = (
                    serviceability_contract_item.get("action_type")
                )
                debug_sink["selected_title"] = (
                    serviceability_contract_item.get("title_main")
                )
                debug_sink[
                    "critical_branch_used_serviceability_contract_ladder"
                ] = True
            return [serviceability_contract_item]
        if serviceability_family_owned and min_dbg:
            debug_sink["generic_one_click_solver_skipped_by_family_owner"] = True

        if statuses.get("bending") == "FAIL" or statuses.get("shear") == "FAIL":
            try:
                family_first_strength_item = _family_ladder_guidance_item(
                    guidance_state,
                    overview,
                    mode_config,
                    strengthening=True,
                    debug_sink=debug_sink if min_dbg else None,
                )
            except Exception as exc:
                family_first_strength_item = None
                if min_dbg:
                    debug_sink["family_ladder_runtime_error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
            if isinstance(family_first_strength_item, dict):
                if family_first_strength_item.get("family_ladder_exhausted"):
                    blocked_item = _family_ladder_exhaustion_blocker_item(
                        family_first_strength_item,
                        overview,
                        critical,
                    )
                    if min_dbg:
                        debug_sink["guidance_branch"] = (
                            "critical_family_ladder_exhausted"
                        )
                        debug_sink["selected_action_type"] = None
                        debug_sink["selected_title"] = blocked_item.get(
                            "title_main"
                        )
                        debug_sink[
                            "critical_branch_used_family_ladder_first"
                        ] = True
                        debug_sink[
                            "generic_one_click_solver_skipped_by_family_owner"
                        ] = True
                    return [blocked_item]
                if min_dbg:
                    debug_sink["guidance_branch"] = (
                        "critical_family_ladder_first"
                    )
                    debug_sink["selected_action_type"] = (
                        family_first_strength_item.get("action_type")
                    )
                    debug_sink["selected_title"] = (
                        family_first_strength_item.get("title_main")
                    )
                    debug_sink[
                        "critical_branch_used_family_ladder_first"
                    ] = True
                return [family_first_strength_item]
            if statuses.get("bending") == "FAIL":
                bending_contract_item = (
                    _bending_fail_contract_ladder_guidance_item(
                        guidance_state,
                        overview,
                        mode_config,
                        debug_sink=debug_sink if min_dbg else None,
                    )
                )
                if isinstance(bending_contract_item, dict):
                    if min_dbg:
                        debug_sink["guidance_branch"] = (
                            "critical_bending_fail_contract_ladder"
                        )
                        debug_sink["selected_action_type"] = (
                            bending_contract_item.get("action_type")
                        )
                        debug_sink["selected_title"] = (
                            bending_contract_item.get("title_main")
                        )
                        debug_sink[
                            "critical_branch_used_bending_fail_contract_ladder"
                        ] = True
                    return [bending_contract_item]
            if min_dbg:
                debug_sink[
                    "generic_one_click_solver_skipped_by_family_owner"
                ] = True
    one_click_probe: dict | None = {} if min_dbg else None
    one_click_critical_item: dict | None = None
    one_click_candidate: dict | None = None
    try:
        if out_of_band_live and not bool(overview.get("all_key_pass")):
            mode_recommendation = _compute_mode_guidance_recommendation(guidance_state)
            if isinstance(mode_recommendation, dict):
                base_candidate = _evaluate_auto_design_candidate(guidance_state, source="guidance_primary_seed")
                one_click_candidate = _materialize_guidance_candidate(
                    base_candidate,
                    mode_recommendation,
                    source="guidance_primary_one_click_candidate",
                )
                if one_click_candidate:
                    _annotate_candidate_target_band_metrics(one_click_candidate, mode_config)
                if one_click_candidate and not bool(one_click_candidate.get("is_compliant")):
                    one_click_candidate = None
                if one_click_candidate and not bool(
                    one_click_candidate.get("candidate_reaches_target_band")
                    or one_click_candidate.get("reaches_target_band")
                ):
                    one_click_candidate = None
    except Exception:
        one_click_candidate = None
    if one_click_candidate:
        one_click_critical_item = _guidance_item_from_resolved_candidate(
            one_click_candidate,
            state=guidance_state,
            overview=overview,
            title=str(one_click_candidate.get("label") or "Apply one-click design"),
            reasoning="This option brings the design into the target utilisation band in one move.",
            status="FAIL",
            primary_action="Apply recommendation",
        )
        if isinstance(one_click_probe, dict):
            failure_coverage = dict((one_click_critical_item.get("action_payload") or {}).get("failure_coverage") or {})
            one_click_probe["one_click_critical_candidate_exists"] = True
            one_click_probe["one_click_critical_candidate_label"] = str(one_click_candidate.get("label") or "")
            one_click_probe["one_click_critical_candidate_action_type"] = str(
                one_click_critical_item.get("action_type")
                or (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_action_type")
                or "",
            )
            one_click_probe["one_click_critical_candidate_post_util"] = one_click_candidate.get("worst_util")
            one_click_probe["one_click_critical_candidate_reaches_target_band"] = True
            one_click_probe["compound_shear_augmented"] = bool(
                one_click_candidate.get("compound_shear_augmented")
                or (one_click_critical_item.get("action_payload") or {}).get("compound_shear_augmented"),
            )
            one_click_probe["covers_all_current_failures"] = bool(
                one_click_critical_item.get("covers_all_current_failures")
                or failure_coverage.get("covers_all_current_failures"),
            )
            one_click_probe["covered_fail_keys"] = list(
                one_click_critical_item.get("covered_fail_keys")
                or failure_coverage.get("covered_fail_keys")
                or [],
            )
            one_click_probe["remaining_fail_keys"] = list(
                one_click_critical_item.get("remaining_fail_keys")
                or failure_coverage.get("remaining_fail_keys")
                or [],
            )
            one_click_probe["one_click_critical_candidate_suppressed_reason"] = None
    else:
        one_click_critical_item = _get_one_click_band_reaching_candidate(
            guidance_state,
            overview,
            mode_config=mode_config,
            primary_hint=primary_critical,
            debug_extra=one_click_probe,
        )
    primary_one_click_valid = False
    primary_one_click_meta = {
        "requires_full_coverage": bool(primary_one_click_requires_full_coverage),
        "fail_keys": list(primary_one_click_fail_keys),
        "valid": False,
        "reason": "missing_candidate",
        "covers_all_current_failures": False,
        "remaining_fail_keys": [],
        "covered_fail_keys": [],
    }
    if one_click_critical_item is not None:
        primary_one_click_valid, primary_one_click_meta = _candidate_is_valid_primary_one_click(
            one_click_critical_item,
            overview,
        )
        if isinstance(one_click_probe, dict):
            one_click_probe["one_click_primary_requires_full_coverage"] = bool(
                primary_one_click_meta.get("requires_full_coverage"),
            )
            one_click_probe["one_click_primary_fail_keys"] = list(primary_one_click_meta.get("fail_keys") or [])
            one_click_probe["one_click_primary_candidate_valid"] = bool(primary_one_click_valid)
            one_click_probe["one_click_primary_candidate_valid_reason"] = str(
                primary_one_click_meta.get("reason") or "missing_candidate",
            )
            one_click_probe["one_click_primary_candidate_covers_all_current_failures"] = bool(
                primary_one_click_meta.get("covers_all_current_failures"),
            )
            one_click_probe["one_click_primary_candidate_remaining_fail_keys"] = list(
                primary_one_click_meta.get("remaining_fail_keys") or [],
            )
            if not primary_one_click_valid:
                one_click_probe["one_click_critical_candidate_suppressed_reason"] = str(
                    primary_one_click_meta.get("reason") or "missing_candidate",
        )
    if min_dbg:
        debug_sink["one_click_critical_candidate_exists"] = bool(one_click_probe.get("one_click_critical_candidate_exists"))
        debug_sink["one_click_critical_candidate_label"] = one_click_probe.get("one_click_critical_candidate_label")
        debug_sink["one_click_critical_candidate_action_type"] = one_click_probe.get("one_click_critical_candidate_action_type")
        debug_sink["one_click_critical_candidate_post_util"] = one_click_probe.get("one_click_critical_candidate_post_util")
        debug_sink["one_click_critical_candidate_reaches_target_band"] = bool(
            one_click_probe.get("one_click_critical_candidate_reaches_target_band"),
        )
        debug_sink["compound_shear_augmented"] = bool(one_click_probe.get("compound_shear_augmented"))
        debug_sink["covers_all_current_failures"] = bool(one_click_probe.get("covers_all_current_failures"))
        debug_sink["covered_fail_keys"] = list(one_click_probe.get("covered_fail_keys") or [])
        debug_sink["remaining_fail_keys"] = list(one_click_probe.get("remaining_fail_keys") or [])
        debug_sink["one_click_primary_requires_full_coverage"] = bool(
            one_click_probe.get("one_click_primary_requires_full_coverage", primary_one_click_requires_full_coverage),
        )
        debug_sink["one_click_primary_fail_keys"] = list(
            one_click_probe.get("one_click_primary_fail_keys") or primary_one_click_fail_keys,
        )
        debug_sink["one_click_primary_candidate_valid"] = bool(
            one_click_probe.get("one_click_primary_candidate_valid", primary_one_click_valid),
        )
        debug_sink["one_click_primary_candidate_valid_reason"] = one_click_probe.get(
            "one_click_primary_candidate_valid_reason",
            primary_one_click_meta.get("reason"),
        )
        debug_sink["one_click_primary_candidate_covers_all_current_failures"] = bool(
            one_click_probe.get(
                "one_click_primary_candidate_covers_all_current_failures",
                primary_one_click_meta.get("covers_all_current_failures"),
            ),
        )
        debug_sink["one_click_primary_candidate_remaining_fail_keys"] = list(
            one_click_probe.get("one_click_primary_candidate_remaining_fail_keys")
            or primary_one_click_meta.get("remaining_fail_keys")
            or [],
        )
        debug_sink["one_click_critical_candidate_surfaced"] = False
        debug_sink["one_click_critical_candidate_suppressed_reason"] = one_click_probe.get(
            "one_click_critical_candidate_suppressed_reason",
        )
        debug_sink["critical_branch_used_one_click_override"] = False
        if not out_of_band_live:
            debug_sink["one_click_critical_candidate_suppressed_reason"] = "already_in_target_band_or_passing"
        debug_sink["one_click_candidate_available_at_step_start"] = bool(
            one_click_probe.get("one_click_critical_candidate_exists"),
        )
        debug_sink["one_click_candidate_label_at_step_start"] = one_click_probe.get(
            "one_click_critical_candidate_label",
        )
    efficiency_state = compute_efficiency_tightening_state(guidance_state, context=design_context)
    safe_cleanup_mode_active = bool(efficiency_state.get("optimisation_safe_cleanup_mode_active"))
    if safe_cleanup_mode_active and not bool(overview.get("any_fail")):
        critical = []
        governing_item_is_critical = False
        primary_critical = None
        one_click_critical_item = None
        if min_dbg:
            debug_sink["safe_cleanup_mode_suppressed_nonfailing_critical_cards"] = True
            debug_sink["safe_cleanup_mode_reason"] = efficiency_state.get("optimisation_safe_cleanup_mode_reason")
    if (
        one_click_critical_item is not None
        and out_of_band_live
        and critical
        and bool(primary_one_click_valid)
    ):
        guidance_branch = "critical_apply_resolved_candidate"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["selected_title"] = one_click_critical_item.get("title_main")
            debug_sink["one_click_critical_candidate_surfaced"] = True
            debug_sink["one_click_critical_candidate_suppressed_reason"] = None
            debug_sink["critical_branch_used_one_click_override"] = True
            debug_sink["primary_guidance_item_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["primary_guidance_item_has_resolved_candidate_payload"] = bool(
                (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_updates"),
            )
            debug_sink["primary_guidance_item_resolved_candidate_label"] = (
                (one_click_critical_item.get("action_payload") or {}).get("resolved_candidate_label")
            )
        return [one_click_critical_item]
    if (
        one_click_critical_item is not None
        and out_of_band_live
        and (bool(overview.get("any_fail")) or bool(overview.get("any_warn")))
        and bool(primary_one_click_valid)
    ):
        guidance_branch = "critical_apply_resolved_candidate_noncritical_bucket"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = one_click_critical_item.get("action_type")
            debug_sink["selected_title"] = one_click_critical_item.get("title_main")
            debug_sink["one_click_critical_candidate_surfaced"] = True
            debug_sink["one_click_critical_candidate_suppressed_reason"] = None
            debug_sink["critical_branch_used_one_click_override"] = True
        return [one_click_critical_item]
    if critical and governing_item_is_critical:
        primary = primary_critical or critical[0]
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"critical_{action_type}" if action_type else "critical_items"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
        _compound_ud_dbg: dict = {}
        compound_item = _try_compound_strengthening_guidance_item(
            guidance_state,
            overview,
            primary,
            compound_underdesign_debug=_compound_ud_dbg if min_dbg else None,
        )
        if min_dbg:
            for _k_ud, _v_ud in _compound_ud_dbg.items():
                if str(_k_ud).startswith("underdesign_"):
                    debug_sink[_k_ud] = _v_ud
        if compound_item:
            head = [compound_item]
        else:
            head = [primary]
        # Single primary critical card UX: do not append a second competing critical card.
        return head
    if critical and not governing_item_is_critical and bool(guidance_state.get("_dev_mode")):
        _agent_debug_log(
            "Suppressed non-governing critical branch",
            {
                "governing_action": governing_action,
                "primary_utils": primary_utils,
                "suppressed_critical_items": [
                    {
                        "check_key": item.get("check_key"),
                        "title": item.get("title_main"),
                        "action_type": item.get("action_type"),
                        "util": item.get("util"),
                    }
                    for item in critical
                ],
                "governing_item": None if governing_item is None else {
                    "check_key": governing_item.get("check_key"),
                    "title": governing_item.get("title_main"),
                    "action_type": governing_item.get("action_type"),
                    "util": governing_item.get("util"),
                    "bucket": governing_item.get("bucket"),
                },
            },
            location="inputs_page.py:_compute_design_guidance_items",
            hypothesis_id="H_GUIDANCE_GOVERNING",
        )
    if full_dbg:
        debug_sink["efficiency_tightening_state"] = efficiency_state
        debug_sink["efficiency_actions_used"] = efficiency_state.get("actions_used")
        debug_sink["is_efficiency_reduction_mode"] = bool(efficiency_state.get("is_efficiency_reduction_mode"))
        debug_sink["efficiency_exhaustion_map"] = efficiency_state.get("exhaustion_map")
        debug_sink["efficiency_worst_util"] = efficiency_state.get("worst_util")
        debug_sink["guidance_target_efficiency_band"] = [
            efficiency_state.get("target_band_lo"),
            efficiency_state.get("target_band_hi"),
        ]
        debug_sink["strongly_underutilised"] = bool(efficiency_state.get("strongly_underutilised"))
        debug_sink["very_low_demand"] = bool(efficiency_state.get("very_low_demand"))
        debug_sink["optimisation_safe_cleanup_mode_active"] = bool(
            efficiency_state.get("optimisation_safe_cleanup_mode_active")
        )
        debug_sink["optimisation_safe_cleanup_mode_reason"] = efficiency_state.get(
            "optimisation_safe_cleanup_mode_reason"
        )
        debug_sink["optimisation_cleanup_candidates_found_count"] = int(
            efficiency_state.get("optimisation_cleanup_candidates_found_count") or 0
        )
    if min_dbg:
        debug_sink.setdefault("optimisation_selector_governing_action", str(governing_action or "other"))
        debug_sink.setdefault("optimisation_selector_family_bias_applied", False)
        debug_sink.setdefault("optimisation_selector_candidate_counts_by_family", {})
        debug_sink.setdefault("optimisation_selector_winning_family", None)
        debug_sink.setdefault("optimisation_selector_used_geometry_fallback", False)
        debug_sink.setdefault("optimisation_selector_fallback_reason", None)
        debug_sink.setdefault("optimisation_selector_candidate_reaches_target_band", False)
        debug_sink.setdefault("optimisation_selector_candidate_all_key_pass", False)
        debug_sink.setdefault("primary_optimisation_selection_owner", "legacy_fallback")
    if not bool(overview.get("any_fail")):
        reshape_item = _in_target_shear_congestion_reshape_guidance_item(
            guidance_state,
            overview,
            mode_config,
            debug_sink=debug_sink if full_dbg else None,
        )
        if reshape_item:
            guidance_branch = "in_target_shear_congestion_reshape"
            if full_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
                debug_sink["actionable_target_band_winner_exists"] = True
                debug_sink["actionable_target_band_winner_family"] = "compound"
                debug_sink["actionable_target_band_winner_subfamilies"] = ["geometry", "bottom_reo", "shear"]
                debug_sink["actionable_target_band_winner_change_lines"] = list(
                    reshape_item.get("guidance_change_lines") or []
                )
                debug_sink["optimal_short_circuit_blocked"] = True
                debug_sink["optimal_short_circuit_block_reason"] = "in_target_shear_congestion_reshape"
                debug_sink["surfaced_guidance_branch"] = guidance_branch
                debug_sink["surfaced_selected_action_type"] = reshape_item.get("action_type")
                debug_sink["surfaced_selected_title"] = reshape_item.get("title_main")
            elif min_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = reshape_item.get("action_type")
                debug_sink["selected_title"] = reshape_item.get("title_main")
            return [reshape_item]
    if str(efficiency_state.get("classification") or "") == "very_low_demand":
        vld_item = _very_low_demand_guidance_item(guidance_state, overview)
        guidance_branch = "very_low_demand"
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = vld_item.get("action_type")
            debug_sink["selected_title"] = vld_item.get("title_main")
        return [vld_item]
    if (
        str(efficiency_state.get("classification") or "").strip().lower()
        == "inefficient"
        and bool(overview.get("all_key_pass"))
    ):
        try:
            overdesign_family_item = _family_ladder_guidance_item(
                guidance_state,
                overview,
                mode_config,
                strengthening=False,
                debug_sink=debug_sink if min_dbg else None,
            )
        except Exception as exc:
            overdesign_family_item = None
            if min_dbg:
                debug_sink["overdesign_family_ladder_runtime_error"] = (
                    f"{type(exc).__name__}: {exc}"
                )
        if isinstance(overdesign_family_item, dict):
            if overdesign_family_item.get(
                "family_ladder_terminal_exact_stop"
            ):
                terminal_item = _family_ladder_terminal_exact_stop_item(
                    overdesign_family_item,
                    overview,
                )
                if min_dbg:
                    debug_sink["guidance_branch"] = (
                        "overdesign_family_ladder_terminal_exact_stop"
                    )
                    debug_sink["selected_action_type"] = None
                    debug_sink["selected_title"] = terminal_item.get(
                        "title_main"
                    )
                    debug_sink[
                        "overdesign_branch_used_family_ladder_first"
                    ] = True
                    debug_sink[
                        "generic_optimisation_selector_skipped_by_family_owner"
                    ] = True
                return [terminal_item]
            if overdesign_family_item.get("family_ladder_exhausted"):
                blocked_item = _family_ladder_exhaustion_blocker_item(
                    overdesign_family_item,
                    overview,
                    critical,
                )
                if min_dbg:
                    debug_sink["guidance_branch"] = (
                        "overdesign_family_ladder_exhausted"
                    )
                    debug_sink["selected_action_type"] = None
                    debug_sink["selected_title"] = blocked_item.get(
                        "title_main"
                    )
                    debug_sink[
                        "overdesign_branch_used_family_ladder_first"
                    ] = True
                    debug_sink[
                        "generic_optimisation_selector_skipped_by_family_owner"
                    ] = True
                return [blocked_item]
            if _guidance_item_is_resolved_one_click(overdesign_family_item):
                overdesign_family_item["guidance_intent"] = "optional_cleanup"
                overdesign_family_item["local_cleanup_candidate"] = True
                if min_dbg:
                    debug_sink["guidance_branch"] = (
                        "overdesign_family_ladder_first"
                    )
                    debug_sink["selected_action_type"] = (
                        overdesign_family_item.get("action_type")
                    )
                    debug_sink["selected_title"] = (
                        overdesign_family_item.get("title_main")
                    )
                    debug_sink[
                        "overdesign_branch_used_family_ladder_first"
                    ] = True
                    debug_sink[
                        "generic_optimisation_selector_skipped_by_family_owner"
                    ] = True
                return [overdesign_family_item]
    efficiency_items = _efficiency_guidance_items(guidance_state, efficiency_state)
    compound_eff_item = _try_compound_efficiency_guidance_item(guidance_state, efficiency_state)
    if compound_eff_item:
        compound_eff_item["priority"] = float(compound_eff_item.get("priority") or 0.0) + 25.0
        efficiency_items.insert(0, compound_eff_item)
    if full_dbg:
        debug_sink["terminal_state_blocked"] = efficiency_state.get("terminal_state_blocked")
        debug_sink["terminal_state_block_reason"] = efficiency_state.get("terminal_state_block_reason")
        debug_sink["efficiency_guidance_items_summary"] = [
            {"title_main": i.get("title_main"), "action_type": i.get("action_type")}
            for i in efficiency_items
            if isinstance(i, dict)
        ]
    if efficiency_items:
        efficiency_items.sort(key=lambda item: item["priority"], reverse=True)
        selector_result = _select_primary_optimisation_candidate(
            state=guidance_state,
            overview=overview,
            mode_config=mode_config,
            governing_action=governing_action,
            candidates=efficiency_items,
            overdesign_stepwise_band_fallback=bool(
                str(efficiency_state.get("classification") or "").strip().lower() == "inefficient"
                and bool(overview.get("all_key_pass"))
            ),
        )
        primary = selector_result.get("selected_candidate")
        selected_family = selector_result.get("selected_family")
        selector_debug = dict(selector_result.get("selector_debug") or {})
        if primary is None:
            primary = next(
                (
                    item for item in efficiency_items
                    if str(item.get("check_key") or "") == str(governing_action or "")
                ),
                efficiency_items[0],
            )
            selected_family = _optimisation_candidate_family(primary, guidance_state)
            selector_debug = {
                **selector_debug,
                "optimisation_selector_winning_family": selected_family,
                "optimisation_selector_fallback_reason": (
                    selector_debug.get("optimisation_selector_fallback_reason")
                    or "shared_selector_no_primary_legacy_order_used"
                ),
                "primary_optimisation_selection_owner": "legacy_fallback",
            }
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"efficiency_{action_type}" if action_type else "efficiency_tightening"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
            debug_sink["optimisation_selector_governing_action"] = selector_debug.get(
                "optimisation_selector_governing_action",
            )
            debug_sink["optimisation_selector_family_bias_applied"] = bool(
                selector_debug.get("optimisation_selector_family_bias_applied"),
            )
            debug_sink["optimisation_selector_candidate_counts_by_family"] = dict(
                selector_debug.get("optimisation_selector_candidate_counts_by_family") or {},
            )
            debug_sink["optimisation_selector_winning_family"] = selector_debug.get(
                "optimisation_selector_winning_family",
            ) or selected_family
            debug_sink["optimisation_selector_used_geometry_fallback"] = bool(
                selector_debug.get("optimisation_selector_used_geometry_fallback"),
            )
            debug_sink["optimisation_selector_fallback_reason"] = selector_debug.get(
                "optimisation_selector_fallback_reason",
            )
            debug_sink["optimisation_selector_candidate_reaches_target_band"] = bool(
                selector_debug.get("optimisation_selector_candidate_reaches_target_band"),
            )
            debug_sink["optimisation_selector_candidate_all_key_pass"] = bool(
                selector_debug.get("optimisation_selector_candidate_all_key_pass"),
            )
            debug_sink["primary_optimisation_selection_owner"] = selector_debug.get(
                "primary_optimisation_selection_owner",
                "legacy_fallback",
            )
            debug_sink["overdesign_no_band_reacher_but_compliant_candidates_exist"] = bool(
                selector_debug.get("overdesign_no_band_reacher_but_compliant_candidates_exist"),
            )
            debug_sink["overdesign_stepwise_fallback_used"] = bool(
                selector_debug.get("overdesign_stepwise_fallback_used"),
            )
            debug_sink["overdesign_stepwise_fallback_family"] = selector_debug.get(
                "overdesign_stepwise_fallback_family",
            )
            debug_sink["overdesign_stepwise_fallback_reason"] = selector_debug.get(
                "overdesign_stepwise_fallback_reason",
            )
            debug_sink["overdesign_stepwise_selected_post_util"] = selector_debug.get(
                "overdesign_stepwise_selected_post_util",
            )
            if str(debug_sink["primary_optimisation_selection_owner"]) == "legacy_fallback":
                debug_sink["legacy_fallback_reason"] = (
                    selector_debug.get("optimisation_selector_fallback_reason")
                    or "shared_selector_unavailable"
                )
                debug_sink["candidate_family"] = selected_family
                debug_sink["governing_action"] = governing_action
        remaining = [item for item in efficiency_items if item is not primary]
        return [primary] + remaining[:1]
    if overview["all_key_pass"] and target_band_with_eps_passed:
        tb_probe: dict | None = {} if full_dbg else None
        actionable_tb = _get_actionable_target_band_winner(
            guidance_state, overview, debug_extra=tb_probe,
        )
        if actionable_tb:
            guidance_branch = "target_band_actionable_winner"
            if full_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["selected_title"] = actionable_tb.get("title_main")
                debug_sink["actionable_target_band_winner_exists"] = True
                debug_sink["actionable_target_band_winner_family"] = tb_probe.get("family")
                debug_sink["actionable_target_band_winner_subfamilies"] = tb_probe.get("subfamilies")
                debug_sink["actionable_target_band_winner_change_lines"] = tb_probe.get("change_lines")
                debug_sink["optimal_short_circuit_blocked"] = True
                debug_sink["optimal_short_circuit_block_reason"] = str(
                    tb_probe.get("target_band_override_reason") or "target_band_strict_override_passed",
                )
                debug_sink["surfaced_guidance_branch"] = guidance_branch
                debug_sink["surfaced_selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["surfaced_selected_title"] = actionable_tb.get("title_main")
                _merge_target_band_probe_to_debug_sink(debug_sink, tb_probe)
            elif min_dbg:
                debug_sink["guidance_branch"] = guidance_branch
                debug_sink["selected_action_type"] = actionable_tb.get("action_type")
                debug_sink["selected_title"] = actionable_tb.get("title_main")
            return [actionable_tb]
        guidance_branch = "optimal"
        final_acceptance_audit = _post_click_accepted_green_audit(
            overview,
            blocker_source=debug_sink if isinstance(debug_sink, dict) else None,
            state=guidance_state,
        )
        if not _post_click_acceptance_audit_allows_green(final_acceptance_audit):
            unresolved_blocker_item = _post_click_low_util_blocker_item(
                guidance_state,
                overview,
                final_acceptance_audit,
            )
            if isinstance(unresolved_blocker_item, dict):
                if min_dbg:
                    debug_sink.update(dict(unresolved_blocker_item.get("candidate_search_evidence") or {}))
                    debug_sink["guidance_branch"] = "target_band_post_click_cleanup_proof_blocked"
                    debug_sink["selected_action_type"] = None
                    debug_sink["selected_title"] = unresolved_blocker_item.get("title_main")
                    debug_sink["post_click_accepted_green"] = False
                    debug_sink["terminal_state_blocked_by_local_cleanup"] = True
                    debug_sink["terminal_state_reason"] = unresolved_blocker_item.get("terminal_state_reason")
                return [unresolved_blocker_item]
        optimal_item = _optimal_guidance_item(guidance_state, overview)
        if full_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = optimal_item.get("action_type")
            debug_sink["selected_title"] = optimal_item.get("title_main")
            debug_sink["actionable_target_band_winner_exists"] = False
            debug_sink["actionable_target_band_winner_family"] = None
            debug_sink["actionable_target_band_winner_subfamilies"] = None
            debug_sink["actionable_target_band_winner_change_lines"] = None
            debug_sink["optimal_short_circuit_blocked"] = False
            debug_sink["optimal_short_circuit_block_reason"] = str(
                tb_probe.get("target_band_override_reason") or tb_probe.get("reason") or "no_actionable_winner",
            )
            debug_sink["surfaced_guidance_branch"] = guidance_branch
            debug_sink["surfaced_selected_action_type"] = optimal_item.get("action_type")
            debug_sink["surfaced_selected_title"] = optimal_item.get("title_main")
            _merge_target_band_probe_to_debug_sink(debug_sink, tb_probe)
        elif min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = optimal_item.get("action_type")
            debug_sink["selected_title"] = optimal_item.get("title_main")
        return [optimal_item]
    passive_fallback_allowed = (
        overview["all_key_pass"]
        and (
            _is_in_target_zone_with_eps(overview, mode_config, eps=TARGET_BAND_EPS)
            or not _efficiency_state_has_valid_candidate(efficiency_state)
        )
    )
    if filtered:
        primary = next(
            (
                item for item in filtered
                if str(item.get("check_key") or "") == str(governing_action or "")
            ),
            filtered[0],
        )
        action_type = str(primary.get("action_type") or "")
        guidance_branch = f"passing_guidance_{action_type}" if action_type else "passing_guidance_fallback"
        _log_guidance_branch_governing_mismatch(
            guidance_branch=guidance_branch,
            governing_action=governing_action,
            primary_utils=primary_utils,
            selected_item=primary,
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = primary.get("action_type")
            debug_sink["selected_title"] = primary.get("title_main")
        return [primary]
    if not passive_fallback_allowed:
        guidance_branch = "passing_guidance_blocked"
        blocked_item = _guidance_item(
            "general",
            "Design can be tightened",
            "Review optimisation options",
            "Automatic tightening did not yield a safe passive fallback under the resolved action set.",
            (
                f"Why: the current beam passes, but the resolved actions still place it outside the preferred "
                f"target zone for {_design_optimisation_goal_label(guidance_state).lower()}."
            ),
            "Key levers: optimisation preference, geometry, reinforcement",
            None,
            None,
            status="EFFICIENCY",
            util=overview["worst_util"],
        )
        if min_dbg:
            debug_sink["guidance_branch"] = guidance_branch
            debug_sink["selected_action_type"] = blocked_item.get("action_type")
            debug_sink["selected_title"] = blocked_item.get("title_main")
        return [blocked_item]
    guidance_branch = "passing_guidance_fallback"
    passing_item = _passing_guidance_item(guidance_state, overview)
    if min_dbg:
        debug_sink["guidance_branch"] = guidance_branch
        debug_sink["selected_action_type"] = passing_item.get("action_type")
        debug_sink["selected_title"] = passing_item.get("title_main")
    return [passing_item]


def _compute_design_guidance_items(
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    """
    Layer 3 pure guidance compute (Recommendation Engine entrypoint).
    Returns all artifacts needed by UI/state layers without mutating session state.

    Canonical recommendation_result matches the Design Guide primary card: it is derived from
    deduped guidance items using the same resolver state as the panel (guidance_resolved_state).

    request_kind:
      - "design_guide": guidance core only (default).
      - "auto_design": also runs run_auto_design_solver(...) as an internal subroutine and prepends
        its recommendation as a guidance item so the same dedupe + primary-card pipeline applies.
    """
    request_kind_norm = str(request_kind or "design_guide").strip() or "design_guide"
    state = _design_guide_lightweight_guidance_state(state)
    canonical_state = _build_canonical_design_state_pack(state)
    guidance_runtime_fp = stable_fingerprint_for_payload(
        {
            "guidance_algorithm_version": DESIGN_GUIDE_ALGORITHM_VERSION,
            "design_guide_algorithm_version": DESIGN_GUIDE_ALGORITHM_VERSION,
            "request_kind": request_kind_norm,
            "guidance_debug_verbose": bool(guidance_debug_verbose),
            "debug_enabled": bool(debug_enabled),
            "canonical_state": canonical_state,
            "post_cleanup_acceptance_enabled": bool(
                st.session_state.get("_design_guide_post_cleanup_acceptance_enabled")
            ),
            "post_cleanup_acceptance_fp": st.session_state.get("_design_guide_post_cleanup_acceptance_fp"),
            "post_cleanup_acceptance_global_match": (
                _local_cleanup_acceptance_fingerprint(state) in _DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
            ),
        }
    )
    cached_runtime_payload = get_rerun_pure_cache(
        "compute_design_guidance_items",
        guidance_runtime_fp,
    )
    if isinstance(cached_runtime_payload, dict):
        ux_probe_record(
            "guidance_item_computation.compute_design_guidance_items",
            fingerprint=guidance_runtime_fp,
            cache_hit=True,
            meta={"request_kind": request_kind_norm},
        )
        speed_profile_record(
            "guidance_item_computation.compute_design_guidance_items.cache_hit",
            0.0,
            category="compute",
        )
        return cached_runtime_payload
    ux_probe_record(
        "guidance_item_computation.compute_design_guidance_items",
        fingerprint=guidance_runtime_fp,
        cache_hit=False,
        meta={"request_kind": request_kind_norm},
    )
    canonical_pack_valid = _canonical_pack_is_valid(canonical_state)
    state_coherence = _design_state_coherence_check(canonical_state)
    coherence_should_block = bool(state_coherence.get("coherence_should_block"))
    try:
        import session_state_final_log as _ssl

        _ssl.ssl_mark_recommendation_engine_invoked()
    except Exception:
        pass
    if (not canonical_pack_valid) or coherence_should_block:
        stop_reason = str(
            canonical_state.get("canonical_pack_error")
            or (state_coherence.get("coherence_blocking_issues") or ["state_incoherent_after_rebuild"])[0]
        )
        actions_used = _resolve_design_actions_from_state(state)
        blocked_guidance_branch = "blocked_invalid_canonical_pack" if not canonical_pack_valid else "blocked_hard_invalid_state"
        blocked_user_reason = (
            "Add longitudinal reinforcement before running auto-design."
            if stop_reason == "no_bars_resolved"
            else f"Design Guide blocked: {stop_reason}."
        )
        blocked_debug = {
            "guidance_branch": blocked_guidance_branch,
            "selected_action_type": None,
            "selected_title": None,
            "guidance_resolved_state": dict(canonical_state),
            "longitudinal_reo_truth_source": canonical_state.get("longitudinal_reo_truth_source"),
            "row_model_legacy_sync_applied": bool(canonical_state.get("row_model_legacy_sync_applied")),
            "row_model_legacy_sync_diff_keys": list(canonical_state.get("row_model_legacy_sync_diff_keys") or []),
            "overview": {
                "packs": {},
                "statuses": {
                    "bending": "FAIL",
                    "shear": "—",
                    "crack": "—",
                    "deflection": "—",
                },
                "utils": {
                    "bending": None,
                    "shear": None,
                    "crack": None,
                    "deflection": None,
                },
                "any_fail": True,
                "any_warn": False,
                "all_key_pass": False,
                "worst_util": 0.0,
                "actions_used": dict(actions_used or {}),
            },
            "efficiency_tightening_state": {
                "classification": "blocked_invalid_state",
            },
            **_coherence_debug_fields(state_coherence),
            "canonical_pack_built": bool(canonical_state.get("canonical_pack_built")),
            "canonical_pack_valid": canonical_pack_valid,
            "canonical_pack_source": canonical_state.get("canonical_pack_source"),
            "canonical_pack_error": canonical_state.get("canonical_pack_error"),
            "canonical_pack_error_stage": canonical_state.get("canonical_pack_error_stage"),
            "solver_blocked_by_incoherent_state": True,
            "stop_reason": stop_reason,
            "user_visible_no_action_reason": blocked_user_reason,
        }
        out: dict = {
            "guidance_items": [],
            "blocked_state_class": "hard_invalid",
            "debug_trace": blocked_debug,
            "cache_data": {
                "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
            },
            "recommendation_result": None,
        }
        if request_kind_norm == "auto_design":
            out["auto_design_solver_recommendation"] = None
            out["auto_design_seed_failed"] = True
        set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
        return out
    try:
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE fast_path_before_overview", file=sys.stderr, flush=True)
        fast_overview = _collect_design_overview(state)
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE fast_path_after_overview", file=sys.stderr, flush=True)
        fast_mode_cfg = _design_mode_config(_design_optimisation_goal(state))
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE fast_path_after_mode_cfg", file=sys.stderr, flush=True)
        fast_in_target = bool(
            _overview_required_checks_acceptable(fast_overview)
            and not fast_overview.get("any_fail")
            and _is_in_target_zone_with_eps(fast_overview, fast_mode_cfg, eps=TARGET_BAND_EPS)
        )
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(f"DG_STAGE fast_path_after_in_target in_target={fast_in_target}", file=sys.stderr, flush=True)
        fast_utils = dict(fast_overview.get("utils") or {})
        fast_shear_util = _parse_util_value(fast_utils.get("shear"))
        fast_actions = dict((_build_design_actions_context(state) or {}).get("actions") or {})
        fast_shear_demand_meaningful = not _shear_demands_negligible(fast_actions)
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(f"DG_STAGE fast_path_after_shear_util shear={fast_shear_util}", file=sys.stderr, flush=True)
        if (
            request_kind_norm == "design_guide"
            and False  # Disabled: real-click proof showed this shortcut can bypass final accepted-state evidence.
            and fast_in_target
            and _shear_reinforcement_is_active(state)
            and fast_shear_demand_meaningful
            and fast_shear_util is not None
            and float(fast_shear_util) < float(FINAL_ACCEPTED_MIN_FAMILY_UTIL)
        ):
            _fast_stage_debug = os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
            fast_efficiency_state = {
                "family_utils": dict(fast_utils),
                "materially_overprovided_families": ["shear"],
                "shear_cleanup_possible": True,
            }
            fast_item = None
            no_links_updates = {
                "lig_d": 0,
                "lig_legs": 0,
                "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
            }
            no_links_state = dict(state)
            no_links_state.update(no_links_updates)
            if (
                not _updates_match_state(state, no_links_updates)
                and _shear_cleanup_materially_reduces_reinforcement(state, no_links_state)
            ):
                if _fast_stage_debug:
                    print("DG_STAGE fast_path_before_no_links_eval", file=sys.stderr, flush=True)
                no_links_candidate = _evaluate_auto_design_candidate(
                    state,
                    updates=no_links_updates,
                    source="target_band_active_shear_local_cleanup_fast_path",
                    label="Remove shear links",
                    action_type="apply_shear_recommendation",
                )
                if _fast_stage_debug:
                    print(f"DG_STAGE fast_path_after_no_links_eval candidate={bool(isinstance(no_links_candidate, dict))}", file=sys.stderr, flush=True)
                if isinstance(no_links_candidate, dict):
                    no_links_overview = dict(no_links_candidate.get("overview") or {})
                    if _fast_stage_debug:
                        print("DG_STAGE fast_path_before_no_links_audit", file=sys.stderr, flush=True)
                    no_links_audit = _post_click_accepted_green_audit(
                        no_links_overview,
                        blocker_source={},
                        state=no_links_state,
                    )
                    if _fast_stage_debug:
                        print("DG_STAGE fast_path_after_no_links_audit", file=sys.stderr, flush=True)
                    no_links_worst = _parse_util_value(
                        no_links_overview.get("worst_util", no_links_candidate.get("worst_util"))
                    )
                    fast_t_lo, fast_t_hi, _ = _resolved_efficiency_target_band(
                        fast_mode_cfg,
                        goal=_design_optimisation_goal(state),
                    )
                    if (
                        no_links_worst is not None
                        and float(fast_t_lo) <= float(no_links_worst) <= float(fast_t_hi)
                        and _overview_required_checks_acceptable(no_links_overview)
                        and not bool(no_links_overview.get("any_fail"))
                        and bool(no_links_audit.get("post_click_accepted_green_valid"))
                    ):
                        fast_base_item = _guidance_item(
                            "shear",
                            "Design is safe - optional cleanup available",
                            "Shear reserve is high. Optional cleanup can remove the link layout.",
                            "Alternative: remove shear links.",
                            "Why: shear passes below the target band, so the local link layout can be relaxed safely.",
                            "Key levers: link spacing, number of legs, target utilisation band",
                            "apply_shear_recommendation",
                            {"updates": dict(no_links_updates)},
                            status="EFFICIENCY",
                            util=no_links_worst,
                        )
                        no_links_candidate = {
                            **dict(no_links_candidate),
                            "updates": dict(no_links_updates),
                            "action_type": "apply_shear_recommendation",
                            "label": "Remove shear links",
                            "candidate_post_util": no_links_worst,
                            "candidate_reaches_target_band": True,
                            "post_click_exact_blockers_by_family": dict(
                                no_links_audit.get("post_click_exact_blockers_by_family") or {}
                            ),
                        }
                        fast_item = _promote_guidance_item_to_resolved_candidate(
                            fast_base_item,
                            no_links_candidate,
                            state=state,
                        )
            if not isinstance(fast_item, dict) and _fast_stage_debug:
                print("DG_STAGE fast_path_skipped_non_final_shear_tightening_fallback", file=sys.stderr, flush=True)
            if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
                print(f"DG_STAGE fast_path_after_item item={bool(isinstance(fast_item, dict))}", file=sys.stderr, flush=True)
            if isinstance(fast_item, dict):
                fast_items = _design_guide_apply_button_contracts_to_items(
                    [fast_item],
                    state=state,
                )
                fast_items = _design_guide_apply_display_truth_to_items(
                    fast_items,
                    state=state,
                    overview=fast_overview,
                    mode_config=fast_mode_cfg,
                )
                fast_recommendation = _recommendation_result_for_primary_guidance_card(
                    fast_items,
                    state,
                    branch="target_band_active_shear_local_cleanup_fast_path",
                    request_kind=request_kind_norm,
                )
                fast_primary = fast_items[0] if fast_items and isinstance(fast_items[0], dict) else {}
                fast_evidence = dict(
                    fast_primary.get("candidate_search_evidence")
                    or (fast_primary.get("action_payload") or {}).get("candidate_search_evidence")
                    or (fast_primary.get("resolved_candidate") or {}).get("candidate_search_evidence")
                    or {}
                )
                fast_debug = {
                    "guidance_branch": "target_band_active_shear_local_cleanup_fast_path",
                    "selected_action_type": fast_primary.get("action_type"),
                    "selected_title": fast_primary.get("title_main"),
                    "overview": dict(fast_overview),
                    "efficiency_tightening_state": dict(fast_efficiency_state),
                    "candidate_search_evidence": dict(fast_evidence),
                    "local_cleanup_candidate_search_evidence": dict(fast_evidence),
                    "family_utils": dict(fast_utils),
                    "materially_overprovided_families": ["shear"],
                    "local_cleanup_search_ran": True,
                    "local_cleanup_search_exhaustive": True,
                    "safe_local_cleanup_count": 1,
                    "executable_safe_cleanup_count": 1,
                    "design_guide_render_state_source": "target_band_active_shear_local_cleanup_fast_path",
                    **_coherence_debug_fields(state_coherence),
                    "canonical_pack_built": bool(canonical_state.get("canonical_pack_built")),
                    "canonical_pack_valid": bool(canonical_state.get("canonical_pack_valid")),
                    "canonical_pack_source": canonical_state.get("canonical_pack_source"),
                    "canonical_pack_error": canonical_state.get("canonical_pack_error"),
                    "canonical_pack_error_stage": canonical_state.get("canonical_pack_error_stage"),
                    "longitudinal_reo_truth_source": canonical_state.get("longitudinal_reo_truth_source"),
                    "row_model_legacy_sync_applied": bool(canonical_state.get("row_model_legacy_sync_applied")),
                    "row_model_legacy_sync_diff_keys": list(canonical_state.get("row_model_legacy_sync_diff_keys") or []),
                    "solver_blocked_by_incoherent_state": False,
                    "primary_guidance_intent": str(fast_primary.get("guidance_intent") or "").strip(),
                    "primary_button_contract": dict(fast_primary.get("button_contract") or {}),
                    "primary_display_truth": dict(fast_primary.get("display_truth") or {}),
                }
                fast_out = {
                    "guidance_items": list(fast_items or []),
                    "debug_trace": dict(fast_debug),
                    "cache_data": {
                        "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
                    },
                    "recommendation_result": fast_recommendation,
                }
                set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, fast_out)
                return fast_out
    except Exception:
        pass
    debug_trace: dict = {}
    rank_trace: list[dict] = []
    reco_trace: list[dict] = []
    global _ACTIVE_GUIDANCE_RANK_TRACE
    global _ACTIVE_GUIDANCE_RECO_TRACE
    prev_rank_trace = _ACTIVE_GUIDANCE_RANK_TRACE
    prev_reco_trace = _ACTIVE_GUIDANCE_RECO_TRACE
    _ACTIVE_GUIDANCE_RANK_TRACE = rank_trace if debug_enabled else None
    _ACTIVE_GUIDANCE_RECO_TRACE = reco_trace if debug_enabled else None
    try:
        guidance_items = _compute_design_guidance_items_core(
            state,
            debug_sink=debug_trace,
            guidance_debug_verbose=guidance_debug_verbose,
            debug_enabled=debug_enabled,
        )
    finally:
        _ACTIVE_GUIDANCE_RANK_TRACE = prev_rank_trace
        _ACTIVE_GUIDANCE_RECO_TRACE = prev_reco_trace
    if rank_trace:
        debug_trace["rank_trace"] = list(rank_trace)
    if reco_trace:
        debug_trace["reco_trace"] = list(reco_trace)
    if request_kind_norm == "design_guide" and _locked_no_repair_state_signal(state):
        locked_item = _locked_no_repair_guidance_item(state)
        locked_items = _design_guide_apply_button_contracts_to_items(
            [locked_item],
            state=state,
        )
        locked_items = _design_guide_apply_display_truth_to_items(
            locked_items,
            state=state,
            overview=dict(debug_trace.get("overview") or {}),
            mode_config=_design_mode_config(_design_optimisation_goal(state)),
        )
        locked_primary = locked_items[0] if locked_items and isinstance(locked_items[0], dict) else locked_item
        locked_contract = dict(locked_primary.get("button_contract") or {})
        locked_debug = {
            **dict(debug_trace),
            **_coherence_debug_fields(state_coherence),
            "guidance_branch": "locked_no_repair_state_signal",
            "selected_action_type": None,
            "selected_title": locked_primary.get("title_main"),
            "primary_card_title": locked_primary.get("title_main"),
            "primary_card_intent": locked_primary.get("guidance_intent"),
            "primary_button_contract": dict(locked_contract),
            "button_contract": dict(locked_contract),
            "button_contract_enabled": False,
            "button_contract_updates": {},
            "button_contract_preview_pass": False,
            "button_contract_blocking_reason": "locked_no_valid_repair",
            "selected_family_id": "LOCKED_NO_REPAIR",
            "published_family_id": "LOCKED_NO_REPAIR",
            "cta_family_id": "LOCKED_NO_REPAIR",
            "card_family_id": "LOCKED_NO_REPAIR",
            "apply_payload_family_id": "LOCKED_NO_REPAIR",
            "locked_no_repair_state_signal": True,
            "design_guide_render_state_source": "locked_no_repair_state_signal",
            "canonical_pack_built": bool(canonical_state.get("canonical_pack_built")),
            "canonical_pack_valid": bool(canonical_state.get("canonical_pack_valid")),
            "canonical_pack_source": canonical_state.get("canonical_pack_source"),
            "solver_blocked_by_incoherent_state": False,
        }
        out = {
            "guidance_items": list(locked_items or [locked_primary]),
            "debug_trace": dict(locked_debug),
            "cache_data": {
                "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
            },
            "recommendation_result": None,
        }
        set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
        return out
    if (
        request_kind_norm == "design_guide"
        and str(debug_trace.get("guidance_branch") or "").strip() == "not_started"
    ):
        geometry_not_started_item = _geometry_detailing_not_started_guidance_item(state)
        if isinstance(geometry_not_started_item, dict):
            geometry_items = _design_guide_apply_button_contracts_to_items(
                [geometry_not_started_item],
                state=state,
            )
            geometry_items = _design_guide_apply_display_truth_to_items(
                geometry_items,
                state=state,
                overview=dict(debug_trace.get("overview") or {}),
                mode_config=_design_mode_config(_design_optimisation_goal(state)),
            )
            geometry_recommendation = _recommendation_result_for_primary_guidance_card(
                geometry_items,
                state,
                branch="geometry_detailing_not_started_override",
                request_kind=request_kind_norm,
            )
            geometry_primary = geometry_items[0] if geometry_items and isinstance(geometry_items[0], dict) else {}
            geometry_contract = dict(geometry_primary.get("button_contract") or {})
            geometry_debug = {
                **dict(debug_trace),
                **_coherence_debug_fields(state_coherence),
                "guidance_branch": "geometry_detailing_not_started_override",
                "guidance_branch_previous": "not_started",
                "geometry_detailing_not_started_override_used": True,
                "selected_action_type": geometry_primary.get("action_type"),
                "selected_title": geometry_primary.get("title_main"),
                "primary_card_title": geometry_primary.get("title_main"),
                "primary_card_intent": geometry_primary.get("guidance_intent"),
                "primary_button_contract": dict(geometry_contract),
                "button_contract": dict(geometry_contract),
                "button_contract_enabled": bool(geometry_contract.get("enabled")),
                "button_contract_updates": dict(geometry_contract.get("updates") or {}),
                "button_contract_preview_pass": geometry_contract.get("preview_pass"),
                "button_contract_blocking_reason": geometry_contract.get("blocking_reason"),
                "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "published_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "cta_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "design_guide_render_state_source": "geometry_detailing_not_started_override",
                "canonical_pack_built": bool(canonical_state.get("canonical_pack_built")),
                "canonical_pack_valid": bool(canonical_state.get("canonical_pack_valid")),
                "canonical_pack_source": canonical_state.get("canonical_pack_source"),
                "solver_blocked_by_incoherent_state": False,
            }
            out = {
                "guidance_items": list(geometry_items or []),
                "debug_trace": dict(geometry_debug),
                "cache_data": {
                    "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
                },
                "recommendation_result": geometry_recommendation,
            }
            set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
            return out
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_fast_return", file=sys.stderr, flush=True)
        debug_trace.update(_coherence_debug_fields(state_coherence))
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_after_coherence", file=sys.stderr, flush=True)
        debug_trace["canonical_pack_built"] = bool(canonical_state.get("canonical_pack_built"))
        debug_trace["canonical_pack_valid"] = bool(canonical_state.get("canonical_pack_valid"))
        debug_trace["canonical_pack_source"] = canonical_state.get("canonical_pack_source")
        debug_trace["solver_blocked_by_incoherent_state"] = False
        debug_trace["design_guide_render_state_source"] = "lightweight_overlay_state"
        out = {
            "guidance_items": list(guidance_items or []),
            "debug_trace": dict(debug_trace),
            "cache_data": {
                "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
            },
            "recommendation_result": None,
        }
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_before_cache", file=sys.stderr, flush=True)
        set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
        if os.environ.get("CODEX_DG_STAGE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print("DG_STAGE wrapper_not_started_return", file=sys.stderr, flush=True)
        return out

    auto_design_solver_recommendation: dict | None = None
    auto_design_seed_failed = False
    if request_kind_norm == "auto_design":
        gs = _guidance_state_snapshot(dict(state or {}))
        seed_candidate = evaluate_candidate_full(gs, source="single_pass_auto_design_seed")
        if seed_candidate is None:
            auto_design_seed_failed = True
        else:
            results = _auto_design_results_from_candidate(seed_candidate)
            auto_design_solver_recommendation = run_auto_design_solver(gs, results)
            if auto_design_solver_recommendation:
                injected = _auto_design_solver_recommendation_as_guidance_item(auto_design_solver_recommendation)
                if injected is not None:
                    guidance_items = [injected] + list(guidance_items or [])
        if isinstance(debug_trace, dict):
            debug_trace["recommendation_engine_auto_design"] = {
                "seed_failed": bool(auto_design_seed_failed),
                "solver_returned_value": auto_design_solver_recommendation is not None,
            }

    coherent_trace, coherence_repairs = _ensure_design_guide_debug_trace_coherent(
        state=dict(state or {}),
        guidance_items=list(guidance_items or []),
        debug_trace=dict(debug_trace),
    )
    if coherence_repairs:
        _agent_debug_log(
            "compute_debug_trace_coherence_repaired",
            {"fields": list(coherence_repairs)},
            location="inputs_page.py:_compute_design_guidance_items:debug_trace_coherence",
            hypothesis_id="H_DG_DEBUG_TRACE_COHERENCE",
        )
    debug_trace = coherent_trace
    debug_trace.update(_coherence_debug_fields(state_coherence))
    debug_trace["canonical_pack_built"] = bool(canonical_state.get("canonical_pack_built"))
    debug_trace["canonical_pack_valid"] = bool(canonical_state.get("canonical_pack_valid"))
    debug_trace["canonical_pack_source"] = canonical_state.get("canonical_pack_source")
    debug_trace["canonical_pack_error"] = canonical_state.get("canonical_pack_error")
    debug_trace["canonical_pack_error_stage"] = canonical_state.get("canonical_pack_error_stage")
    debug_trace["longitudinal_reo_truth_source"] = canonical_state.get("longitudinal_reo_truth_source")
    debug_trace["row_model_legacy_sync_applied"] = bool(canonical_state.get("row_model_legacy_sync_applied"))
    debug_trace["row_model_legacy_sync_diff_keys"] = list(canonical_state.get("row_model_legacy_sync_diff_keys") or [])
    debug_trace["solver_blocked_by_incoherent_state"] = False
    debug_trace["design_guide_render_state_source"] = "lightweight_overlay_state"

    gb = debug_trace.get("guidance_branch") if isinstance(debug_trace, dict) else None
    branch_hint = str(gb).strip() if isinstance(gb, str) and str(gb).strip() else None
    gs_resolved = debug_trace.get("guidance_resolved_state") if isinstance(debug_trace, dict) else None
    disp = dict(gs_resolved) if isinstance(gs_resolved, dict) else dict(state or {})
    deduped_guidance_items, guidance_dedupe_meta = _dedupe_guidance_items_for_display(
        list(guidance_items or []),
        disp,
    )
    collapsed_guidance_items, collapse_meta = _collapse_to_single_primary_guidance_item(
        deduped_guidance_items,
        disp,
    )
    collapsed_guidance_items = _sanitize_guidance_items_for_executor_contract(
        collapsed_guidance_items,
        state=disp,
        debug_sink=debug_trace,
    )
    collapsed_guidance_items, _local_cleanup_meta = _maybe_promote_safe_local_cleanup_primary(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        efficiency_state=dict(debug_trace.get("efficiency_tightening_state") or {}),
        mode_config=_design_mode_config(_design_optimisation_goal(disp)),
        debug_sink=debug_trace,
        source="compute_design_guidance_items",
    )
    if (
        debug_trace.get("family_ladder_exhausted_without_legacy_fallback")
        and debug_trace.get("legacy_fallback_allowed") is False
    ):
        collapsed_guidance_items = [
            _family_ladder_exhaustion_blocker_item(
                debug_trace,
                dict(debug_trace.get("overview") or {}),
                collapsed_guidance_items,
            )
        ]
        debug_trace["local_cleanup_promotion_suppressed_by_family_ladder"] = True
    collapsed_guidance_items = _prefer_target_band_guidance_item_order(
        collapsed_guidance_items,
        state=disp,
        mode_config=_design_mode_config(_design_optimisation_goal(disp)),
    )
    collapsed_guidance_items = _align_guidance_items_to_candidate_search_evidence(collapsed_guidance_items)
    collapsed_guidance_items = _design_guide_apply_copy_model_to_items(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        efficiency_state=dict(debug_trace.get("efficiency_tightening_state") or {}),
    )
    debug_trace["guidance_dedupe_meta"] = dict(guidance_dedupe_meta)
    debug_trace["design_guide_single_primary_override"] = bool(collapse_meta.get("collapsed"))
    debug_trace["design_guide_single_primary_reason"] = collapse_meta.get("reason")
    debug_trace["design_guide_single_primary_subfamilies"] = list(collapse_meta.get("subfamilies") or [])
    debug_trace["design_guide_single_primary_covered_fail_keys"] = list(collapse_meta.get("covered_fail_keys") or [])
    debug_trace["design_guide_single_primary_remaining_fail_keys"] = list(collapse_meta.get("remaining_fail_keys") or [])
    recommendation_result = _recommendation_result_for_primary_guidance_card(
        collapsed_guidance_items,
        disp,
        branch=branch_hint,
        request_kind=request_kind_norm,
    )
    explicit_terminal_state = _design_guide_terminal_state_from_render_artifacts(
        collapsed_guidance_items,
        debug_trace,
    )
    derived_terminal_state = _derive_design_guide_terminal_state_from_current_overview(
        debug_trace,
        disp,
        collapsed_guidance_items,
    )
    terminal_state = explicit_terminal_state
    terminal_state_source = "explicit_render_artifact" if explicit_terminal_state else "none"
    if not terminal_state and derived_terminal_state:
        terminal_state = derived_terminal_state
        terminal_state_source = "derived_current_overview"
    terminal_meta = dict(debug_trace.get("_derived_terminal_state_meta") or {})
    debug_trace["design_guide_terminal_state"] = terminal_state
    debug_trace["design_guide_terminal_state_source"] = terminal_state_source
    debug_trace["design_guide_terminal_current_fail_keys"] = list(terminal_meta.get("current_fail_keys") or [])
    debug_trace["design_guide_terminal_current_governing_util"] = terminal_meta.get("current_governing_util")
    debug_trace["design_guide_terminal_target_band_lo"] = terminal_meta.get("target_band_lo")
    debug_trace["design_guide_terminal_target_band_hi"] = terminal_meta.get("target_band_hi")
    if terminal_state in {"optimal", "very_low_demand"}:
        recommendation_result = None
        if not str(debug_trace.get("guidance_branch") or "").strip():
            debug_trace["guidance_branch"] = terminal_state
    guidance_branch_norm = str(debug_trace.get("guidance_branch") or "").strip()
    if guidance_branch_norm in {"passing_guidance_fallback", "passing_guidance_blocked"}:
        if not recommendation_result:
            if guidance_branch_norm == "passing_guidance_blocked":
                debug_trace.setdefault("stop_reason", "cleanup_candidate_blocked")
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because no directly executable "
                    "tightening move under the resolved actions kept every governing check acceptable.",
                )
            else:
                debug_trace.setdefault("stop_reason", "no_actionable_cleanup_candidate")
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because the current move set did not "
                    "produce an actionable tightening candidate that preserved every governing check.",
                )
    if (
        not recommendation_result
        and collapsed_guidance_items
        and terminal_state not in {"optimal", "very_low_demand"}
        and not debug_trace.get(
            "family_ladder_exhausted_without_legacy_fallback"
        )
    ):
        primary_item = collapsed_guidance_items[0] if isinstance(collapsed_guidance_items[0], dict) else None
        overview_dbg = dict(debug_trace.get("overview") or {})
        statuses_dbg = dict(overview_dbg.get("statuses") or {})
        all_key_pass_dbg = bool(overview_dbg.get("all_key_pass"))
        worst_util_dbg = _parse_util_value(overview_dbg.get("worst_util"))
        action_type_dbg = str((primary_item or {}).get("action_type") or "").strip()
        contract_block_reason = str((primary_item or {}).get("executor_contract_blocked_reason") or "").strip()
        if (
            primary_item
            and not action_type_dbg
            and all_key_pass_dbg
            and worst_util_dbg is not None
            and float(worst_util_dbg) < float(EFFICIENCY_TARGET_UTIL_MIN)
            and all(str(v or "").upper() in {"PASS", "INFO", "NEAR LIMIT", "—", "-"} for v in statuses_dbg.values())
        ):
            debug_trace.setdefault("stop_reason", "no_actionable_cleanup_candidate")
            if contract_block_reason == "primary_efficiency_card_not_executor_backed":
                blocked_item = _guidance_item(
                    "general",
                    "Cleanup is advisory for this design state",
                    "Advisory reduction ideas need manual review before they can be applied.",

                    (
                        "The current all-pass state is below the target band, but the available "
                        "advisory reductions are not attached to an executor-backed one-click move."
                    ),
                    (
                        "Why: the guide avoided a one-click change because the candidate must be directly executable "
                        "and must keep every governing check acceptable."
                    ),
                    "Key levers: manual geometry, reinforcement, shear detailing review",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=worst_util_dbg,
                )
                if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict):
                    collapsed_guidance_items[0] = blocked_item
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because the available reduction ideas "
                    "are not attached to an executor-backed local move.",
                )
            else:
                blocked_item = _guidance_item(
                    "general",
                    "Cleanup is advisory for this design state",
                    "No directly executable local reduction kept every governing check acceptable.",
                    (
                        "The current all-pass state remains below the target band, so manual cleanup "
                        "can still be reviewed against geometry, reinforcement, and detailing trade-offs."
                    ),
                    (
                        "Why: the solver avoided a one-click change because the available move set did not preserve "
                        "all governing checks while moving the design toward the target band."
                    ),
                    "Key levers: manual geometry, reinforcement, shear detailing review",
                    None,
                    None,
                    status="EFFICIENCY",
                    util=worst_util_dbg,
                )
                if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict):
                    collapsed_guidance_items[0] = blocked_item
                debug_trace.setdefault(
                    "user_visible_no_action_reason",
                    "Cleanup is advisory for the current all-pass state because the available move set did not "
                    "preserve every governing check while moving toward the target band.",
                )
    collapsed_guidance_items = _design_guide_apply_copy_model_to_items(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        efficiency_state=dict(debug_trace.get("efficiency_tightening_state") or {}),
    )
    collapsed_guidance_items = _design_guide_apply_button_contracts_to_items(
        collapsed_guidance_items,
        state=disp,
    )
    collapsed_guidance_items = _normalise_active_failure_blocker_contract_identity(
        collapsed_guidance_items,
        overview=dict(debug_trace.get("overview") or {}),
    )
    collapsed_guidance_items = _design_guide_apply_display_truth_to_items(
        collapsed_guidance_items,
        state=disp,
        overview=dict(debug_trace.get("overview") or {}),
        mode_config=_design_mode_config(_design_optimisation_goal(disp)),
    )
    if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict):
        primary_item_for_evidence = collapsed_guidance_items[0]
        existing_evidence = dict(
            primary_item_for_evidence.get("candidate_search_evidence")
            or (primary_item_for_evidence.get("action_payload") or {}).get("candidate_search_evidence")
            or (primary_item_for_evidence.get("resolved_candidate") or {}).get("candidate_search_evidence")
            or {}
        )
        if not existing_evidence:
            mode_cfg_evidence = _design_mode_config(_design_optimisation_goal(disp))
            t_lo_evidence, t_hi_evidence, _ = _resolved_efficiency_target_band(
                mode_cfg_evidence,
                goal=_design_optimisation_goal(disp),
            )
            evidence_candidates: list[dict] = []
            for idx, item in enumerate(collapsed_guidance_items, start=1):
                if not isinstance(item, dict):
                    continue
                contract = dict(item.get("button_contract") or {})
                truth = dict(item.get("display_truth") or {})
                updates = dict(contract.get("updates") or _resolve_recommendation_updates(item, disp) or {})
                preview_util = (
                    contract.get("expected_util")
                    if contract.get("expected_util") is not None
                    else truth.get("source_candidate_util", truth.get("displayed_util"))
                )
                evidence_candidates.append(
                    {
                        "candidate_id": _guidance_item_source_candidate_id(item) or f"displayed_candidate_{idx:03d}",
                        "label": item.get("title_main") or f"Displayed candidate {idx}",
                        "updates": dict(updates),
                        "candidate_post_util": preview_util,
                        "worst_util": preview_util,
                        "is_compliant": bool(contract.get("preview_pass") and contract.get("blocking_reason") in (None, "")),
                        "overview": {},
                    }
                )
            selected_for_evidence = evidence_candidates[0] if evidence_candidates else None
            existing_evidence = _build_candidate_search_evidence(
                selected_candidate=selected_for_evidence,
                all_candidates=evidence_candidates,
                target_low=float(t_lo_evidence),
                target_high=float(t_hi_evidence),
                exhaustive=True,
                search_scope="final_displayed_design_guide_candidates",
                selected_title=str(primary_item_for_evidence.get("title_main") or ""),
            )
        primary_item_for_evidence["candidate_search_evidence"] = dict(existing_evidence)
        primary_item_for_evidence["candidate_id"] = existing_evidence.get("selected_candidate_id")
        primary_item_for_evidence["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
        _evidence_payload = dict(primary_item_for_evidence.get("action_payload") or {})
        _evidence_payload["candidate_search_evidence"] = dict(existing_evidence)
        _evidence_payload["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
        primary_item_for_evidence["action_payload"] = _evidence_payload
        _evidence_resolved = dict(primary_item_for_evidence.get("resolved_candidate") or {})
        _evidence_resolved["candidate_search_evidence"] = dict(existing_evidence)
        _evidence_resolved["candidate_id"] = existing_evidence.get("selected_candidate_id")
        _evidence_resolved["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
        primary_item_for_evidence["resolved_candidate"] = _evidence_resolved
        _evidence_contract = dict(primary_item_for_evidence.get("button_contract") or {})
        if _evidence_contract:
            _evidence_contract["source_candidate_id"] = existing_evidence.get("selected_candidate_id")
            primary_item_for_evidence["button_contract"] = _evidence_contract
        debug_trace["candidate_search_evidence"] = dict(existing_evidence)
    debug_trace["guidance_intent_items"] = _design_guide_guidance_intent_debug_rows(collapsed_guidance_items)
    debug_trace["displayed_guidance_intent_items"] = list(debug_trace["guidance_intent_items"])
    debug_trace["primary_guidance_intent"] = (
        str((collapsed_guidance_items[0] or {}).get("guidance_intent") or "").strip()
        if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict)
        else None
    )
    debug_trace["primary_button_contract"] = (
        dict((collapsed_guidance_items[0] or {}).get("button_contract") or {})
        if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict)
        else {}
    )
    debug_trace["primary_display_truth"] = (
        dict((collapsed_guidance_items[0] or {}).get("display_truth") or {})
        if collapsed_guidance_items and isinstance(collapsed_guidance_items[0], dict)
        else {}
    )
    out: dict = {
        "guidance_items": list(collapsed_guidance_items or []),
        "debug_trace": dict(debug_trace),
        "cache_data": {
            "guidance_cache_fp": _candidate_cache_key(dict(state or {})),
        },
        "recommendation_result": recommendation_result,
    }
    if request_kind_norm == "auto_design":
        out["auto_design_solver_recommendation"] = auto_design_solver_recommendation
        out["auto_design_seed_failed"] = bool(auto_design_seed_failed)
    set_rerun_pure_cache("compute_design_guidance_items", guidance_runtime_fp, out)
    return out
