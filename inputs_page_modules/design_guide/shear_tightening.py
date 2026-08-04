"""Shear tightening recommendation coordination for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Callable


@dataclass(frozen=True)
class ShearTighteningRuntime:
    annotate_candidate_target_band_metrics: Callable[..., Any]
    annotate_shear_link_state_debug_from_state: Callable[..., Any]
    build_auto_design_context: Callable[..., Any]
    build_design_actions_context: Callable[..., Any]
    candidate_debug_summary: Callable[..., Any]
    collect_design_overview: Callable[..., Any]
    combined_underdesign_shear_strengthening_truth_gate_payload: Callable[..., Any]
    design_mode_config: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    evaluate_candidate_fast: Callable[..., Any]
    evaluate_candidate_full: Callable[..., Any]
    generate_less_shear_reo_variants: Callable[..., Any]
    guidance_state_snapshot: Callable[..., Any]
    initialise_shear_link_optimisation_debug: Callable[..., Any]
    invalid_shear_spacing_change_without_activation: Callable[..., Any]
    log_shear_candidate_debug: Callable[..., Any]
    resolved_efficiency_target_band: Callable[..., Any]
    score_auto_design_candidate: Callable[..., Any]
    shear_change_is_relevant: Callable[..., Any]
    shear_cleanup_possible: Callable[..., Any]
    shear_demands_negligible: Callable[..., Any]
    shear_detailing_updates_pure: Callable[..., Any]
    shear_governing_truth_allows_overdesign_cleanup: Callable[..., Any]
    shear_preview_for_updates: Callable[..., Any]
    shear_reinforcement_is_active: Callable[..., Any]
    shear_state_label: Callable[..., Any]
    try_shear_activation_for_underdesign_recommendation: Callable[..., Any]
    try_shear_canonical_inactive_fixup_recommendation: Callable[..., Any]
    try_shear_remove_links_tightening_recommendation: Callable[..., Any]


_SHEAR_TIGHTENING_DEPENDENCIES: tuple[str, ...] = (
    "_annotate_candidate_target_band_metrics",
    "_annotate_shear_link_state_debug_from_state",
    "_build_auto_design_context",
    "_build_design_actions_context",
    "_candidate_debug_summary",
    "_collect_design_overview",
    "_combined_underdesign_shear_strengthening_truth_gate_payload",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_evaluate_candidate_fast",
    "_guidance_state_snapshot",
    "_initialise_shear_link_optimisation_debug",
    "_invalid_shear_spacing_change_without_activation",
    "_log_shear_candidate_debug",
    "_resolved_efficiency_target_band",
    "_score_auto_design_candidate",
    "_shear_change_is_relevant",
    "_shear_cleanup_possible",
    "_shear_demands_negligible",
    "_shear_detailing_updates_pure",
    "_shear_governing_truth_allows_overdesign_cleanup",
    "_shear_preview_for_updates",
    "_shear_reinforcement_is_active",
    "_shear_state_label",
    "_try_shear_activation_for_underdesign_recommendation",
    "_try_shear_canonical_inactive_fixup_recommendation",
    "_try_shear_remove_links_tightening_recommendation",
    "evaluate_candidate_full",
    "generate_less_shear_reo_variants",
)


def bind_shear_tightening_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_TIGHTENING_DEPENDENCIES
            if name in namespace
        }
    )


def _compute_shear_tightening_recommendation(
    state: dict,
    *,
    runtime: ShearTighteningRuntime | None = None,
    out_debug: dict | None = None,
) -> dict | None:
    if runtime is None:
        namespace = globals()
        runtime = ShearTighteningRuntime(
            **{
                field_name: namespace[f"_{field_name}"]
                if f"_{field_name}" in namespace
                else namespace[field_name]
                for field_name in ShearTighteningRuntime.__dataclass_fields__
            }
        )
    if runtime is not None:
        _annotate_candidate_target_band_metrics = (
            runtime.annotate_candidate_target_band_metrics
        )
        _annotate_shear_link_state_debug_from_state = (
            runtime.annotate_shear_link_state_debug_from_state
        )
        _build_auto_design_context = runtime.build_auto_design_context
        _build_design_actions_context = runtime.build_design_actions_context
        _candidate_debug_summary = runtime.candidate_debug_summary
        _collect_design_overview = runtime.collect_design_overview
        _combined_underdesign_shear_strengthening_truth_gate_payload = (
            runtime
            .combined_underdesign_shear_strengthening_truth_gate_payload
        )
        _design_mode_config = runtime.design_mode_config
        _design_optimisation_goal = runtime.design_optimisation_goal
        _evaluate_candidate_fast = runtime.evaluate_candidate_fast
        _guidance_state_snapshot = runtime.guidance_state_snapshot
        _initialise_shear_link_optimisation_debug = (
            runtime.initialise_shear_link_optimisation_debug
        )
        _invalid_shear_spacing_change_without_activation = (
            runtime.invalid_shear_spacing_change_without_activation
        )
        _log_shear_candidate_debug = runtime.log_shear_candidate_debug
        _resolved_efficiency_target_band = (
            runtime.resolved_efficiency_target_band
        )
        _score_auto_design_candidate = runtime.score_auto_design_candidate
        _shear_change_is_relevant = runtime.shear_change_is_relevant
        _shear_cleanup_possible = runtime.shear_cleanup_possible
        _shear_demands_negligible = runtime.shear_demands_negligible
        _shear_detailing_updates_pure = runtime.shear_detailing_updates_pure
        _shear_governing_truth_allows_overdesign_cleanup = (
            runtime.shear_governing_truth_allows_overdesign_cleanup
        )
        _shear_preview_for_updates = runtime.shear_preview_for_updates
        _shear_reinforcement_is_active = (
            runtime.shear_reinforcement_is_active
        )
        _shear_state_label = runtime.shear_state_label
        _try_shear_activation_for_underdesign_recommendation = (
            runtime.try_shear_activation_for_underdesign_recommendation
        )
        _try_shear_canonical_inactive_fixup_recommendation = (
            runtime.try_shear_canonical_inactive_fixup_recommendation
        )
        _try_shear_remove_links_tightening_recommendation = (
            runtime.try_shear_remove_links_tightening_recommendation
        )
        evaluate_candidate_full = runtime.evaluate_candidate_full
        generate_less_shear_reo_variants = (
            runtime.generate_less_shear_reo_variants
        )
    dbg = out_debug if out_debug is not None else {}
    for _k, _v in _initialise_shear_link_optimisation_debug().items():
        dbg.setdefault(_k, _v)

    state = _guidance_state_snapshot(state)
    design_context = _build_design_actions_context(state)
    overview = _collect_design_overview(state, context=design_context)
    actions = design_context.get("actions") or {}
    _annotate_shear_link_state_debug_from_state(state, dbg)
    shear_pack_cur = (((overview or {}).get("packs") or {}).get("shear") or {})
    truth_allow_overdesign_cleanup, _truth_od_detail = _shear_governing_truth_allows_overdesign_cleanup(shear_pack_cur)
    dbg.update(dict(_truth_od_detail))

    # Canonical inactive fixup runs before activation; see docstring on _try_shear_canonical_inactive_fixup_recommendation.
    canon_rec = _try_shear_canonical_inactive_fixup_recommendation(state)
    if canon_rec:
        dbg["shear_tightening_terminal_reason"] = "canonical_inactive_storage_fixup"
        dbg["shear_link_state_is_canonical"] = True
        return canon_rec

    if not _shear_change_is_relevant(overview, actions) and not _shear_cleanup_possible(state):
        dbg["shear_tightening_terminal_reason"] = "not_relevant_no_cleanup"
        return None

    if _shear_demands_negligible(actions) and _shear_reinforcement_is_active(state):
        dbg["shear_tightening_terminal_reason"] = "no_demand_not_meaningful_for_final_tightening"
        return None

    if not _shear_reinforcement_is_active(state):
        dbg["shear_underdesign_activation_candidate_seen"] = True
        _gate_payload = _combined_underdesign_shear_strengthening_truth_gate_payload(
            state,
            overview=overview,
            efficiency_classification=None,
        )
        dbg.update(_gate_payload)
        if bool(_gate_payload.get("combined_underdesign_shear_truth_block_active")):
            dbg["shear_underdesign_activation_candidate_committed"] = False
            dbg["shear_tightening_terminal_reason"] = "underdesign_shear_strengthening_truth_blocked"
            return None
        act_rec = _try_shear_activation_for_underdesign_recommendation(state, overview, actions)
        if act_rec:
            dbg["shear_underdesign_activation_candidate_committed"] = True
            dbg["shear_tightening_terminal_reason"] = "underdesign_activation"
            return act_rec
        dbg["shear_tightening_terminal_reason"] = "inactive_no_underdesign_activation"
        return None

    if not truth_allow_overdesign_cleanup:
        dbg["shear_tightening_terminal_reason"] = "overdesign_cleanup_blocked_governing_truth"
        dbg["shear_candidate_family_pure"] = True
        dbg.setdefault("shear_candidate_non_detailing_updates_detected", tuple())
        return None

    remove_rec = _try_shear_remove_links_tightening_recommendation(state, overview, dbg)
    if remove_rec:
        dbg["shear_overdesign_remove_links_candidate_committed"] = True
        dbg["shear_tightening_terminal_reason"] = "overdesign_remove_links"
        return remove_rec

    current_spacing = float(state.get("s_lig", 200.0) or 200.0)
    current_legs = int(state.get("lig_legs", 2) or 2)
    current_dia = int(state.get("lig_d", 10) or 10)
    current_density = (current_legs * max(current_dia, 1) ** 2) / max(current_spacing, 1.0)

    mode_config = _design_mode_config(_design_optimisation_goal(state))
    target_lo, target_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal(state))
    target_mid = (target_lo + target_hi) / 2.0
    seed_candidate = evaluate_candidate_full(state, source="guidance_shear_seed")
    if not seed_candidate:
        dbg["shear_tightening_terminal_reason"] = "no_seed_candidate"
        return None
    context = _build_auto_design_context(
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
    for candidate_state in generate_less_shear_reo_variants(seed_candidate, mode_config):
        spacing_try = float(candidate_state.get("s_lig", current_spacing) or current_spacing)
        if abs(spacing_try - current_spacing) > 1e-9:
            dbg["shear_spacing_candidate_seen"] = True
        candidate = _evaluate_candidate_fast(
            candidate_state,
            seed_state=seed_candidate["state"],
            context=context,
            eval_cache=eval_cache,
            metrics=metrics,
            source="guidance_shear_tighten",
            label=_shear_state_label(candidate_state),
            action_type="increase_link_spacing",
        )
        if _invalid_shear_spacing_change_without_activation(
            state,
            candidate_state,
            source="guidance_shear_tighten",
        ):
            if abs(spacing_try - current_spacing) > 1e-9:
                dbg["shear_spacing_candidate_dropped_reason"] = "invalid_spacing_without_activation"
                dbg["shear_spacing_candidate_materiality"] = "guard_reject"
            continue
        if candidate is None or not bool(candidate.get("is_compliant")):
            if abs(spacing_try - current_spacing) > 1e-9:
                dbg["shear_spacing_candidate_dropped_reason"] = "non_compliant_or_failed_eval"
                dbg["shear_spacing_candidate_materiality"] = "compliance"
            _log_shear_candidate_debug(
                source="guidance_shear_tighten",
                candidate_state=candidate_state,
                candidate=candidate,
            )
            continue
        _pure_u, _bad_u = _shear_detailing_updates_pure(dict(candidate.get("updates") or {}))
        if not _pure_u:
            dbg["shear_candidate_family_pure"] = False
            dbg["shear_candidate_non_detailing_updates_detected"] = tuple(_bad_u)
            dbg["shear_candidate_rejected_reason"] = "non_shear_detailing_updates"
            continue
        dbg["shear_candidate_family_pure"] = True
        dbg["shear_candidate_non_detailing_updates_detected"] = tuple()
        dbg["shear_candidate_rejected_reason"] = None
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        _log_shear_candidate_debug(
            source="guidance_shear_tighten",
            candidate_state=candidate_state,
            candidate=candidate,
        )
        spacing = float(candidate_state.get("s_lig", current_spacing) or current_spacing)
        legs = int(candidate_state.get("lig_legs", current_legs) or current_legs)
        dia = int(candidate_state.get("lig_d", current_dia) or current_dia)
        candidate_density = (legs * max(dia, 1) ** 2) / max(spacing, 1.0)
        if candidate_density >= current_density - 1e-9:
            if abs(spacing - current_spacing) > 1e-9 or legs != current_legs or dia != current_dia:
                dbg["shear_spacing_candidate_dropped_reason"] = "no_compliant_density_reduction_candidates"
                dbg["shear_spacing_candidate_materiality"] = "density_ordering"
            continue
        spacing_increase = max(spacing - current_spacing, 0.0)
        leg_reduction = max(current_legs - legs, 0)
        dia_reduction = max(current_dia - dia, 0)
        if spacing_increase <= 0.0 and leg_reduction <= 0 and dia_reduction <= 0:
            continue
        candidate["action_type"] = "increase_link_spacing" if spacing_increase > 0.0 else "reduce_number_of_legs"
        candidate["label"] = f"{legs}-leg N{dia} @ {int(spacing)}"
        candidates.append(candidate)

    if not candidates:
        dbg.setdefault("shear_spacing_candidate_dropped_reason", "no_compliant_density_reduction_candidates")
        dbg["shear_tightening_terminal_reason"] = "no_compliant_density_reduction_candidates"
        return None

    best = min(
        candidates,
        key=lambda item: (
            0 if target_lo <= float(item.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0) <= target_hi else 1,
            abs(float(item.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0) - target_mid),
            0 if str(item.get("action_type") or "") == "increase_link_spacing" else 1,
            -float(item.get("state", {}).get("s_lig", current_spacing) or current_spacing),
            int(item.get("state", {}).get("lig_legs", current_legs) or current_legs),
            int(item.get("state", {}).get("lig_d", current_dia) or current_dia),
        ),
    )
    _best_pure, _best_bad = _shear_detailing_updates_pure(dict(best.get("updates") or {}))
    if not _best_pure:
        dbg["shear_tightening_terminal_reason"] = "non_shear_detailing_best_rejected"
        dbg["shear_candidate_non_detailing_updates_detected"] = tuple(_best_bad)
        dbg["shear_candidate_family_pure"] = False
        return None
    dbg["shear_overdesign_spacing_candidate_committed"] = str(best.get("action_type") or "") == "increase_link_spacing"
    dbg["shear_overdesign_density_reduction_candidate_committed"] = True
    dbg["shear_tightening_terminal_reason"] = "spacing_or_leg_reduction"
    preview = _shear_preview_for_updates(state, dict(best.get("updates") or {})) or {}
    ct = "no_shear_design_cleanup" if str(best.get("candidate_type") or "") == "no_shear_design_cleanup" else "shear"
    try:
        _annotate_candidate_target_band_metrics(best, mode_config)
    except Exception:
        pass
    return {
        "updates": dict(best.get("updates") or {}),
        "label": str(best.get("label") or ""),
        "util": float(best.get("overview", {}).get("utils", {}).get("shear", 0.0) or 0.0),
        "web_util": float(preview.get("web_util", best.get("overview", {}).get("utils", {}).get("shear", 0.0)) or 0.0),
        "action_type": str(best.get("action_type") or "increase_link_spacing"),
        "score": float(best.get("score", 0.0) or 0.0),
        "candidate_summary": _candidate_debug_summary(best),
        "candidate_type": ct,
        "resolved_candidate": dict(best),
        "resolved_candidate_updates": dict(best.get("updates") or {}),
        "resolved_candidate_label": str(best.get("label") or ""),
        "resolved_candidate_action_type": str(best.get("action_type") or "increase_link_spacing"),
        "resolved_candidate_post_util": best.get("candidate_post_util", best.get("worst_util")),
        "resolved_candidate_reaches_target_band": bool(
            best.get("candidate_reaches_target_band") or best.get("reaches_target_band")
        ),
    }


__all__ = [
    "ShearTighteningRuntime",
    "bind_shear_tightening_dependencies",
    "_compute_shear_tightening_recommendation",
]
