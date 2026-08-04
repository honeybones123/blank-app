"""Governing-domain tightening candidate orchestration for the Design Guide."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from state_and_helpers import BEAM_STATUS_FAIL


_GOVERNING_DOMAIN_TIGHTENING_CANDIDATES_DEPENDENCIES: tuple[str, ...] = (
    "EFFICIENCY_TARGET_UTIL_MIN",
    "_build_design_actions_context_isolated",
    "_candidate_target_domains_for_band",
    "_candidate_objective_util",
    "_compute_bottom_reo_recommendation",
    "_effective_bottom_design_state",
    "_float_from_state",
    "_generate_shear_governing_candidates",
    "_governing_focus_from_overview",
    "_guidance_state_snapshot",
    "_int_from_state",
    "_one_click_diff_accumulated_updates",
    "_one_click_domain_needs_cleanup",
    "_one_click_eval_domain_scores",
    "_one_click_required_domains_satisfied",
    "generate_cleanup_candidates",
    "generate_less_bottom_reo_variants",
    "generate_less_shear_reo_variants",
    "generate_simpler_layout_variants",
    "generate_smaller_geometry_variants",
)


@dataclass(frozen=True)
class GoverningDomainTighteningRuntime:
    efficiency_target_util_min: float
    build_design_actions_context_isolated: Callable[..., Any]
    candidate_target_domains_for_band: Callable[..., Any]
    candidate_objective_util: Callable[..., Any]
    compute_bottom_reo_recommendation: Callable[..., Any]
    effective_bottom_design_state: Callable[..., Any]
    float_from_state: Callable[..., Any]
    generate_shear_governing_candidates: Callable[..., Any]
    governing_focus_from_overview: Callable[..., Any]
    guidance_state_snapshot: Callable[..., Any]
    int_from_state: Callable[..., Any]
    one_click_diff_accumulated_updates: Callable[..., Any]
    one_click_domain_needs_cleanup: Callable[..., Any]
    one_click_eval_domain_scores: Callable[..., Any]
    one_click_required_domains_satisfied: Callable[..., Any]
    generate_cleanup_candidates: Callable[..., Any]
    generate_less_bottom_reo_variants: Callable[..., Any]
    generate_less_shear_reo_variants: Callable[..., Any]
    generate_simpler_layout_variants: Callable[..., Any]
    generate_smaller_geometry_variants: Callable[..., Any]


def _runtime_dependencies(
    runtime: GoverningDomainTighteningRuntime | None,
) -> dict[str, Any]:
    if runtime is None:
        return {
            name: globals()[name]
            for name in _GOVERNING_DOMAIN_TIGHTENING_CANDIDATES_DEPENDENCIES
        }
    return {
        "EFFICIENCY_TARGET_UTIL_MIN": runtime.efficiency_target_util_min,
        **{
            f"_{name}": getattr(runtime, name)
            for name in (
                "build_design_actions_context_isolated",
                "candidate_target_domains_for_band",
                "candidate_objective_util",
                "compute_bottom_reo_recommendation",
                "effective_bottom_design_state",
                "float_from_state",
                "generate_shear_governing_candidates",
                "governing_focus_from_overview",
                "guidance_state_snapshot",
                "int_from_state",
                "one_click_diff_accumulated_updates",
                "one_click_domain_needs_cleanup",
                "one_click_eval_domain_scores",
                "one_click_required_domains_satisfied",
            )
        },
        **{
            name: getattr(runtime, name)
            for name in (
                "generate_cleanup_candidates",
                "generate_less_bottom_reo_variants",
                "generate_less_shear_reo_variants",
                "generate_simpler_layout_variants",
                "generate_smaller_geometry_variants",
            )
        },
    }


def bind_governing_domain_tightening_candidates_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _GOVERNING_DOMAIN_TIGHTENING_CANDIDATES_DEPENDENCIES
            if name in namespace
        }
    )


def _one_click_generate_multi_domain_refinement_states(
    working_state: dict,
    cur_eval: dict,
    mode_config: dict,
    *,
    runtime: GoverningDomainTighteningRuntime | None = None,
) -> list[dict]:
    """Small local vector search for bending/shear target-band frontiers."""
    deps = _runtime_dependencies(runtime)
    _candidate_target_domains_for_band = deps[
        "_candidate_target_domains_for_band"
    ]
    _one_click_required_domains_satisfied = deps[
        "_one_click_required_domains_satisfied"
    ]
    _one_click_eval_domain_scores = deps["_one_click_eval_domain_scores"]
    _guidance_state_snapshot = deps["_guidance_state_snapshot"]
    _float_from_state = deps["_float_from_state"]
    _int_from_state = deps["_int_from_state"]
    _one_click_diff_accumulated_updates = deps[
        "_one_click_diff_accumulated_updates"
    ]
    domains = set(_candidate_target_domains_for_band(cur_eval or {}))
    if not {"bending", "shear"}.issubset(domains):
        return []
    if _one_click_required_domains_satisfied(cur_eval, mode_config):
        return []

    scores = _one_click_eval_domain_scores(cur_eval, mode_config)
    bending = dict(scores.get("bending") or {})
    shear = dict(scores.get("shear") or {})
    if not (bool(bending.get("under")) and bool(shear.get("pass"))):
        return []

    base = _guidance_state_snapshot(dict(working_state or {}))
    cur_d = float(_float_from_state(base, "D", 0.0) or 0.0)
    cur_spacing = float(_float_from_state(base, "s_lig", 0.0) or 0.0)
    cur_legs = int(_int_from_state(base, "lig_legs", 0) or 0)
    cur_dia = int(_int_from_state(base, "lig_d", 0) or 0)
    if cur_d <= 0.0 or cur_spacing <= 0.0 or cur_legs <= 0 or cur_dia <= 0:
        return []

    states: list[dict] = []
    seen: set[tuple] = set()
    if bool(shear.get("under")):
        # Both domains are overdesigned: reduce bending capacity and relax shear detailing together.
        depth_options = [cur_d - 25.0, cur_d - 50.0]
        leg_options: list[int] = []
        for legs in (max(2, cur_legs - 2), max(2, cur_legs - 1), cur_legs):
            if legs > 0 and legs not in leg_options:
                leg_options.append(legs)
        spacing_offsets = [20.0, 25.0, 30.0, 35.0, 40.0, 15.0, 45.0, 50.0]
        for new_d in depth_options:
            if new_d <= 200.0:
                continue
            for new_legs in leg_options:
                for offset in spacing_offsets:
                    new_spacing = cur_spacing + offset
                    if new_spacing <= cur_spacing + 1e-6:
                        continue
                    st = dict(base)
                    st.update(
                        {
                            "D": float(new_d),
                            "lig_d": int(cur_dia),
                            "lig_legs": int(new_legs),
                            "s_lig": float(new_spacing),
                        }
                    )
                    updates = _one_click_diff_accumulated_updates(base, st)
                    if not updates:
                        continue
                    key = tuple(sorted((str(k), str(v)) for k, v in updates.items()))
                    if key in seen:
                        continue
                    seen.add(key)
                    states.append(st)
    else:
        # When bending is still overdesigned but shear is already passing, search a small
        # paired frontier that reduces bending capacity while preserving shear adequacy.
        depth_options = [cur_d - 25.0, cur_d - 50.0]
        leg_options = [cur_legs, cur_legs + 1, cur_legs + 2]
        spacing_offsets = [-20.0, -25.0, -30.0, -35.0, -40.0, -15.0, -45.0, -50.0]
        for new_d in depth_options:
            if new_d <= 200.0:
                continue
            for new_legs in leg_options:
                if new_legs <= 0:
                    continue
                for offset in spacing_offsets:
                    new_spacing = cur_spacing + offset
                    if new_spacing < 75.0:
                        continue
                    st = dict(base)
                    st.update(
                        {
                            "D": float(new_d),
                            "lig_d": int(cur_dia),
                            "lig_legs": int(new_legs),
                            "s_lig": float(new_spacing),
                        }
                    )
                    updates = _one_click_diff_accumulated_updates(base, st)
                    if not updates:
                        continue
                    key = tuple(sorted((str(k), str(v)) for k, v in updates.items()))
                    if key in seen:
                        continue
                    seen.add(key)
                    states.append(st)
    return states


def _generate_tightening_candidates_for_governing_domain(
    working_state: dict,
    cur_eval: dict,
    mode_config: dict,
    *,
    tightening_step_count: int = 0,
    runtime: GoverningDomainTighteningRuntime | None = None,
) -> tuple[list[dict], dict]:
    """
    Governing-action-first tightening candidate orchestration.
    Returns (prioritized_candidates, trace_meta).
    """
    deps = _runtime_dependencies(runtime)
    EFFICIENCY_TARGET_UTIL_MIN = deps["EFFICIENCY_TARGET_UTIL_MIN"]
    _build_design_actions_context_isolated = deps[
        "_build_design_actions_context_isolated"
    ]
    _candidate_objective_util = deps["_candidate_objective_util"]
    _compute_bottom_reo_recommendation = deps[
        "_compute_bottom_reo_recommendation"
    ]
    _effective_bottom_design_state = deps[
        "_effective_bottom_design_state"
    ]
    _float_from_state = deps["_float_from_state"]
    _generate_shear_governing_candidates = deps[
        "_generate_shear_governing_candidates"
    ]
    _governing_focus_from_overview = deps[
        "_governing_focus_from_overview"
    ]
    _guidance_state_snapshot = deps["_guidance_state_snapshot"]
    _one_click_diff_accumulated_updates = deps[
        "_one_click_diff_accumulated_updates"
    ]
    _one_click_domain_needs_cleanup = deps[
        "_one_click_domain_needs_cleanup"
    ]
    generate_cleanup_candidates = deps["generate_cleanup_candidates"]
    generate_less_bottom_reo_variants = deps[
        "generate_less_bottom_reo_variants"
    ]
    generate_less_shear_reo_variants = deps[
        "generate_less_shear_reo_variants"
    ]
    generate_simpler_layout_variants = deps[
        "generate_simpler_layout_variants"
    ]
    generate_smaller_geometry_variants = deps[
        "generate_smaller_geometry_variants"
    ]
    overview = dict((cur_eval or {}).get("overview") or {})
    target_domain_override = str((cur_eval or {}).get("target_domain_for_band") or "").strip().lower()
    governing_domain = (
        target_domain_override
        if target_domain_override in ("bending", "shear")
        else _governing_focus_from_overview(overview)
    )
    current_candidate = dict(cur_eval or {})
    current_candidate["state"] = _guidance_state_snapshot(dict(working_state or {}))
    current_candidate["depth"] = float(_float_from_state(working_state, "D", 0.0) or 0.0)
    current_candidate["Ast_bot"] = float((_effective_bottom_design_state(working_state) or {}).get("Ast_bot", 0.0) or 0.0)
    context = _build_design_actions_context_isolated(dict(working_state or {}))
    multi_domain_refinement = _one_click_generate_multi_domain_refinement_states(
        working_state,
        cur_eval,
        mode_config,
        runtime=runtime,
    )

    prioritized_states: list[tuple[str, list[dict]]] = []
    pruned_families: list[str] = []
    family_depth_reached = "none"
    cur_u = _candidate_objective_util(cur_eval)
    target_lo = float(mode_config.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    materially_under_target = bool(math.isfinite(cur_u) and cur_u < target_lo - 0.03)
    if governing_domain == "bending":
        statuses_bd = dict(overview.get("statuses") or {})
        bending_status = statuses_bd.get("bending")
        bending_failing = bool(
            bending_status == BEAM_STATUS_FAIL
            or str(bending_status or "").strip().upper() == "FAIL",
        )
        strength_states: list[dict] = []
        if bending_failing:
            bottom_rec_bd = None
            try:
                bottom_rec_bd = _compute_bottom_reo_recommendation(dict(working_state or {}))
            except Exception:
                bottom_rec_bd = None
            bottom_updates_bd = dict((bottom_rec_bd or {}).get("updates") or {})
            if bottom_updates_bd:
                ws_bd = dict(working_state or {})
                st_bd = dict(ws_bd)
                st_bd.update(bottom_updates_bd)
                if _one_click_diff_accumulated_updates(ws_bd, st_bd):
                    strength_states.append(st_bd)
        bottom_variants = list(generate_less_bottom_reo_variants(current_candidate, mode_config, context) or [])
        bottom_primary = bottom_variants[:8]
        bottom_secondary = bottom_variants[8:24] if materially_under_target or tightening_step_count > 0 else []
        geom_variants = list(generate_smaller_geometry_variants(current_candidate, mode_config) or [])
        depth_variants: list[dict] = []
        width_variants: list[dict] = []
        for gst in geom_variants:
            updates_g = _one_click_diff_accumulated_updates(working_state, gst)
            if not updates_g:
                continue
            has_depth = "D" in updates_g
            has_width = ("b" in updates_g) or ("bw" in updates_g)
            if has_depth and not has_width:
                depth_variants.append(gst)
            elif has_width and not has_depth:
                width_variants.append(gst)
            elif has_depth:
                depth_variants.append(gst)
            elif has_width:
                width_variants.append(gst)
        compound_variants = list(generate_simpler_layout_variants(current_candidate, mode_config, context) or [])
        if bending_failing:
            prioritized_states = [
                ("multi_domain_refinement", multi_domain_refinement),
                ("bending_strengthen_bottom_recommendation", strength_states),
                ("bottom_reduction_primary", bottom_primary),
                ("bottom_reduction_secondary", bottom_secondary),
                ("geometry_reduction_depth", depth_variants),
                ("geometry_reduction_width", width_variants),
                ("compound_geometry_bottom", compound_variants),
                ("non_governing_cleanup", generate_cleanup_candidates(current_candidate, mode_config, context)),
            ]
        else:
            prioritized_states = [
                ("multi_domain_refinement", multi_domain_refinement),
                ("bottom_reduction_primary", bottom_primary),
                ("bottom_reduction_secondary", bottom_secondary),
                ("geometry_reduction_depth", depth_variants),
                ("geometry_reduction_width", width_variants),
                ("compound_geometry_bottom", compound_variants),
                ("non_governing_cleanup", generate_cleanup_candidates(current_candidate, mode_config, context)),
            ]
        pruned_families.extend(["shear_first_grid", "broad_growth_geometry"])
    elif governing_domain == "shear":
        secondary_fail_keys = sorted(
            key
            for key, val in (overview.get("statuses") or {}).items()
            if str(val or "").upper() == "FAIL" and str(key or "").strip().lower() != "shear"
        )
        if secondary_fail_keys:
            bottom_variant_count = 0
            compound_variant_count = 0
            bottom_rec_label = None
            try:
                bottom_variant_count = len(generate_less_bottom_reo_variants(current_candidate, mode_config, context) or [])
            except Exception:
                bottom_variant_count = -1
            try:
                compound_variant_count = len(generate_simpler_layout_variants(current_candidate, mode_config, context) or [])
            except Exception:
                compound_variant_count = -1
            try:
                bottom_rec = _compute_bottom_reo_recommendation(dict(working_state or {}))
                bottom_rec_label = str((bottom_rec or {}).get("label") or "").strip() or None
            except Exception:
                bottom_rec_label = None
        if _one_click_domain_needs_cleanup(cur_eval, "shear", mode_config):
            prioritized_states = [
                ("multi_domain_refinement", multi_domain_refinement),
                ("shear_cleanup", list(generate_less_shear_reo_variants(current_candidate, mode_config) or [])),
                ("non_governing_cleanup", generate_cleanup_candidates(current_candidate, mode_config, context)),
            ]
            pruned_families.extend(["shear_first_grid", "broad_growth_geometry"])
        else:
            return _generate_shear_governing_candidates(working_state, cur_eval, mode_config)
    elif governing_domain in ("crack", "deflection"):
        prioritized_states = [
            ("geometry_reduction_depth_width", generate_smaller_geometry_variants(current_candidate, mode_config)),
            ("bottom_reduction", generate_less_bottom_reo_variants(current_candidate, mode_config, context)),
            ("non_governing_cleanup", generate_cleanup_candidates(current_candidate, mode_config, context)),
        ]
        pruned_families.extend(["broad_growth_geometry", "shear_first_grid"])
    else:
        prioritized_states = [
            ("bottom_reduction", generate_less_bottom_reo_variants(current_candidate, mode_config, context)),
            ("geometry_reduction_depth_width", generate_smaller_geometry_variants(current_candidate, mode_config)),
        ]
        pruned_families.extend(["broad_growth_geometry"])

    out: list[dict] = []
    seen_update_keys: set[tuple] = set()
    considered_families: list[str] = []
    for family, states in prioritized_states:
        considered_families.append(family)
        for st in states[:16]:
            updates = _one_click_diff_accumulated_updates(working_state, st)
            if not updates:
                continue
            uk = tuple(sorted((str(k), str(v)) for k, v in updates.items()))
            if uk in seen_update_keys:
                continue
            seen_update_keys.add(uk)
            out.append(
                {
                    "item": {"action_payload": {"guidance_change_summary_compact": f"Tightening {family} candidate"}},
                    "action_type": "tightening_domain_candidate",
                    "title": f"Tightening: {family}",
                    "raw_updates": dict(updates),
                    "_tightening_family": family,
                },
            )
            family_depth_reached = family
    meta = {
        "governing_domain": governing_domain,
        "candidate_families_considered": considered_families,
        "candidate_families_pruned": pruned_families,
        "candidate_family_depth_reached": family_depth_reached,
    }
    return out, meta
