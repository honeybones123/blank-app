"""Compound strengthening guidance coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_COMPOUND_STRENGTHENING_DEPENDENCIES: tuple[str, ...] = (
    "SHARED_DEFAULTS",
    "_bottom_arrangement_to_shared_updates",
    "_build_design_actions_context",
    "_candidate_is_growth_move",
    "_collect_design_overview",
    "_compound_efficiency_incoherent",
    "_compound_guidance_title_reasoning_why",
    "_compound_strengthening_viable",
    "_compound_subfamilies_from_updates",
    "_compute_bottom_reo_recommendation",
    "_compute_geometry_recommendation",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_efficiency_distance_to_target_band",
    "_geometry_lock_enabled",
    "_governing_focus_from_overview",
    "_guidance_change_lines_for_updates",
    "_guidance_item",
    "_guidance_state_snapshot",
    "_log_efficiency_growth_rejection",
    "_recommendation_search_allowed",
    "_resolve_geometry_width_context",
    "_try_shear_no_demand_cleanup_recommendation",
    "_updates_match_state",
    "evaluate_candidate_full",
)


def bind_compound_strengthening_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _COMPOUND_STRENGTHENING_DEPENDENCIES
            if name in namespace
        }
    )


def _try_compound_strengthening_guidance_item(
    state: dict,
    overview: dict,
    primary_item: dict | None,
    *,
    compound_underdesign_debug: dict | None = None,
) -> dict | None:
    if not _recommendation_search_allowed(state):
        return None
    if str((primary_item or {}).get("check_key") or "") != "bending":
        return None
    seed_c = evaluate_candidate_full(_guidance_state_snapshot(state), source="compound_strengthen_seed")
    if not seed_c:
        return None

    def _compound_shared_updates_delta(base_state: dict, final_state: dict) -> dict:
        base_s = _guidance_state_snapshot(base_state)
        fin_s = _guidance_state_snapshot(final_state)
        return {
            k: fin_s[k]
            for k in SHARED_DEFAULTS.keys()
            if base_s.get(k) != fin_s.get(k)
        }

    # Bounded escalation: re-run geometry/bottom/shear-cleanup recommenders from a progressed
    # work state when merged trials remain non-compliant, without surfacing non-compliant primaries.
    max_escalation_steps = 5
    dbg = compound_underdesign_debug if isinstance(compound_underdesign_debug, dict) else None
    work = dict(_guidance_state_snapshot(state))
    total_candidates_evaluated = 0
    compliant_trials_seen = 0
    best_compliant_wu = float("inf")
    best_compliant_bundle: tuple[dict, list[str], dict, dict] | None = None
    best_any_wu = float("inf")
    last_merged_pairs_count = 0
    last_had_geo = False
    last_had_bot = False
    last_had_clean = False
    escalation_stalled = False
    steps_used = 0
    prev_progress_wu = float(seed_c.get("worst_util", 999.0) or 999.0)

    for esc in range(max_escalation_steps):
        steps_used = esc + 1
        geo_rec = None if _geometry_lock_enabled(work) else _compute_geometry_recommendation(work)
        bot_rec = _compute_bottom_reo_recommendation(work)
        design_context = _build_design_actions_context(work)
        actions = design_context.get("actions") or {}
        overview_w = _collect_design_overview(work, context=design_context)
        shear_clean = _try_shear_no_demand_cleanup_recommendation(work, overview_w, actions)

        geo_u = dict((geo_rec or {}).get("updates") or {})
        bot_u = {}
        if bot_rec:
            bot_u = dict(bot_rec.get("updates") or {})
            if not bot_u and isinstance(bot_rec.get("arrangement"), dict):
                bot_u = dict(_bottom_arrangement_to_shared_updates(bot_rec["arrangement"]) or {})
        clean_u = dict((shear_clean or {}).get("updates") or {})

        merged_pairs: list[tuple[dict, list[str]]] = []

        def _consider(merged: dict) -> None:
            if not merged or _updates_match_state(work, merged):
                return
            subs = _compound_subfamilies_from_updates(merged)
            if len(set(subs)) < 2:
                return
            merged_pairs.append((merged, subs))

        _consider({**geo_u, **bot_u})
        _consider({**clean_u, **bot_u})
        _consider({**clean_u, **geo_u})
        _consider({**clean_u, **geo_u, **bot_u})

        last_merged_pairs_count = len(merged_pairs)
        last_had_geo = bool(geo_u)
        last_had_bot = bool(bot_u)
        last_had_clean = bool(clean_u)
        if not merged_pairs:
            if esc == 0 and isinstance(compound_underdesign_debug, dict):
                compound_underdesign_debug.update(
                    {
                        "underdesign_compound_candidates_found_count": 0,
                        "underdesign_compound_compliant_count": 0,
                        "underdesign_compound_best_post_util": None,
                        "underdesign_compound_search_bounds": {
                            "variants_evaluated": 0,
                            "geometry_locked": bool(_geometry_lock_enabled(state)),
                            "max_escalation_steps": int(max_escalation_steps),
                            "escalation_steps_used": 0,
                            "escalation_stalled": False,
                        },
                        "underdesign_compound_escalation_exhausted": False,
                        "underdesign_primary_candidate_noncompliant": False,
                        "underdesign_primary_candidate_surface_reason": "no_merged_geometry_bottom_variants",
                    },
                )
            if esc == 0:
                return None
            last_merged_pairs_count = 0
            escalation_stalled = True
            break

        round_best_compliant: tuple[float, dict, list[str], dict, dict] | None = None
        round_best_nc: tuple[float, dict] | None = None

        for merged, subs in merged_pairs:
            trial_st = dict(_guidance_state_snapshot(work))
            trial_st.update(merged)
            trial_c = evaluate_candidate_full(
                _guidance_state_snapshot(trial_st),
                source=f"compound_strengthen_rank_e{esc}",
                updates=merged,
            )
            if not trial_c or not _compound_strengthening_viable(seed_c, trial_c):
                continue
            total_candidates_evaluated += 1
            wu = float(trial_c.get("worst_util", 999.0) or 999.0)
            if wu < best_any_wu - 1e-9:
                best_any_wu = wu

            single_best = float("inf")
            if geo_u:
                tg = dict(_guidance_state_snapshot(work))
                tg.update(geo_u)
                cg = evaluate_candidate_full(
                    _guidance_state_snapshot(tg),
                    source=f"compound_strengthen_geo_only_e{esc}",
                )
                if cg:
                    single_best = min(single_best, float(cg.get("worst_util", 999.0) or 999.0))
            if bot_u:
                tb = dict(_guidance_state_snapshot(work))
                tb.update(bot_u)
                cb = evaluate_candidate_full(
                    _guidance_state_snapshot(tb),
                    source=f"compound_strengthen_bot_only_e{esc}",
                )
                if cb:
                    single_best = min(single_best, float(cb.get("worst_util", 999.0) or 999.0))
            if single_best < float("inf") and wu > single_best + 1e-6:
                continue

            if bool(trial_c.get("is_compliant")):
                compliant_trials_seen += 1
                if round_best_compliant is None or wu < round_best_compliant[0] - 1e-9:
                    round_best_compliant = (
                        wu,
                        merged,
                        subs,
                        trial_c,
                        dict(_guidance_state_snapshot(trial_st)),
                    )
            else:
                if round_best_nc is None or wu < round_best_nc[0] - 1e-9:
                    round_best_nc = (wu, dict(_guidance_state_snapshot(trial_st)))

        if round_best_compliant is not None:
            wu_c, merged_c, subs_c, _tc, trial_final = round_best_compliant
            if wu_c < best_compliant_wu - 1e-9:
                best_compliant_wu = wu_c
                best_compliant_bundle = (merged_c, subs_c, _tc, trial_final)
            break

        if esc >= max_escalation_steps - 1:
            break
        if round_best_nc is None:
            escalation_stalled = True
            break
        wu_nc, trial_next = round_best_nc
        if wu_nc >= prev_progress_wu - 1e-6:
            escalation_stalled = True
            break
        work = trial_next
        prev_progress_wu = wu_nc

    if dbg is not None:
        dbg["underdesign_compound_candidates_found_count"] = int(total_candidates_evaluated)
        dbg["underdesign_compound_compliant_count"] = int(compliant_trials_seen)
        dbg["underdesign_compound_best_post_util"] = (
            float(best_compliant_wu)
            if best_compliant_bundle is not None
            else (
                float(best_any_wu)
                if total_candidates_evaluated > 0 and best_any_wu < float("inf")
                else None
            )
        )
        dbg["underdesign_compound_search_bounds"] = {
            "variants_evaluated": int(last_merged_pairs_count),
            "trials_after_viability_filters": int(total_candidates_evaluated),
            "geometry_locked": bool(_geometry_lock_enabled(state)),
            "had_geo_updates": bool(last_had_geo),
            "had_bot_updates": bool(last_had_bot),
            "had_shear_cleanup_updates": bool(last_had_clean),
            "max_escalation_steps": int(max_escalation_steps),
            "escalation_steps_used": int(steps_used),
            "escalation_stalled": bool(escalation_stalled),
        }

    if not best_compliant_bundle:
        if dbg is not None:
            exhausted = bool(
                compliant_trials_seen == 0
                and total_candidates_evaluated > 0
                and (escalation_stalled or steps_used >= max_escalation_steps),
            )
            dbg["underdesign_compound_escalation_exhausted"] = exhausted
            dbg["underdesign_primary_candidate_noncompliant"] = bool(
                total_candidates_evaluated > 0 and compliant_trials_seen == 0,
            )
            if exhausted:
                dbg["underdesign_primary_candidate_surface_reason"] = (
                    "compound_escalation_exhausted_no_compliant_within_bounds"
                )
            else:
                dbg["underdesign_primary_candidate_surface_reason"] = (
                    "compound_suppressed_no_compliant_merged_strengthening_trial"
                    if total_candidates_evaluated > 0
                    else "compound_suppressed_no_evaluable_trials"
                )
        return None

    _merged_c, _subs, _trial_c, trial_final = best_compliant_bundle
    absolute_updates = _compound_shared_updates_delta(state, trial_final)
    if not absolute_updates:
        absolute_updates = dict(_merged_c)

    if dbg is not None:
        dbg["underdesign_compound_escalation_exhausted"] = False
        dbg["underdesign_primary_candidate_noncompliant"] = False
        dbg["underdesign_primary_candidate_surface_reason"] = "surfaced_compliant_compound_strengthening"
        wk, _, _ = _resolve_geometry_width_context(state)
        dbg["underdesign_compound_search_bounds"]["had_geo_updates"] = any(
            k in ("D", "b", wk) for k in absolute_updates
        )
        dbg["underdesign_compound_search_bounds"]["had_bot_updates"] = any(
            str(k).startswith("bot") or k in ("db_bot", "db_bot_1", "db_bot_2") for k in absolute_updates
        )
        dbg["underdesign_compound_search_bounds"]["had_shear_cleanup_updates"] = any(
            k in ("lig_d", "lig_legs", "s_lig") for k in absolute_updates
        )

    subs_abs = _compound_subfamilies_from_updates(absolute_updates)
    title, reasoning, guidance_why = _compound_guidance_title_reasoning_why(
        state,
        absolute_updates,
        subs_abs,
        strengthening=True,
    )
    c_lines = _guidance_change_lines_for_updates(state, absolute_updates)
    return _guidance_item(
        "bending",
        title,
        "Apply recommendation",
        None,
        reasoning,
        "Key levers: depth D, beam width, bottom reinforcement, shear links",
        "apply_compound_guidance",
        {
            "updates": absolute_updates,
            "guidance_banner_title": title,
            "guidance_banner_summary": reasoning,
        },
        status=str((primary_item or {}).get("status") or "FAIL"),
        util=(primary_item or {}).get("util"),
        guidance_change_lines=c_lines or None,
        guidance_why=guidance_why,
    )


def _try_compound_efficiency_guidance_item(state: dict, efficiency_state: dict) -> dict | None:
    if str(efficiency_state.get("classification") or "") == "optimal":
        return None
    if str(efficiency_state.get("classification") or "") == "very_low_demand":
        return None
    if efficiency_state.get("mode_tightening"):
        return None
    if not bool(efficiency_state.get("is_efficiency_reduction_mode")):
        return None
    if not _recommendation_search_allowed(state):
        return None

    overview = efficiency_state.get("overview") or {}
    filter_growth = bool(efficiency_state.get("filter_growth_candidates"))
    mode_cfg = _design_mode_config(_design_optimisation_goal(state))

    seed_c = evaluate_candidate_full(_guidance_state_snapshot(state), source="compound_efficiency_seed")
    if not seed_c:
        return None

    bottom_t = efficiency_state.get("bottom_tightening")
    geometry_t = efficiency_state.get("geometry_tightening")
    shear_t = efficiency_state.get("shear_tightening")

    design_context = _build_design_actions_context(state)
    actions = dict(design_context.get("actions") or {})
    shear_clean = _try_shear_no_demand_cleanup_recommendation(state, overview, actions)

    bottom_u: dict = {}
    if bottom_t and isinstance(bottom_t.get("arrangement"), dict):
        bottom_u = dict(_bottom_arrangement_to_shared_updates(bottom_t["arrangement"]) or {})

    geo_u = dict((geometry_t or {}).get("updates") or {})
    clean_u = dict((shear_clean or {}).get("updates") or {})
    shear_u = dict((shear_t or {}).get("updates") or {}) if shear_t else {}
    shear_merge = clean_u if clean_u else shear_u

    candidates_ranked: list[tuple[float, dict, dict]] = []

    for merged in (
        {**geo_u, **bottom_u},
        {**shear_merge, **bottom_u},
        {**shear_merge, **geo_u},
    ):
        if not merged or _updates_match_state(state, merged):
            continue
        subs = _compound_subfamilies_from_updates(merged)
        if len(set(subs)) < 2:
            continue
        trial_st = dict(state)
        trial_st.update(merged)
        trial_c = evaluate_candidate_full(
            _guidance_state_snapshot(trial_st),
            source="compound_efficiency_rank",
            updates=merged,
        )
        if not trial_c or not bool(trial_c.get("is_compliant")):
            continue
        if filter_growth and _candidate_is_growth_move(seed_c, trial_c):
            _log_efficiency_growth_rejection(
                candidate_family="compound",
                seed_candidate=seed_c,
                candidate=trial_c,
            )
            continue
        if filter_growth and _compound_efficiency_incoherent(state, trial_st, seed_c, trial_c):
            continue
        w_after = float(((trial_c.get("overview") or {}).get("worst_util")) or 0.0)
        dist = _efficiency_distance_to_target_band(w_after, mode_cfg)
        candidates_ranked.append((dist, merged, trial_c))

    if not candidates_ranked:
        return None
    candidates_ranked.sort(key=lambda row: row[0])
    _dist, merged, _trial_c = candidates_ranked[0]
    subs = _compound_subfamilies_from_updates(merged)
    title, reasoning, guidance_why = _compound_guidance_title_reasoning_why(
        state, merged, subs, strengthening=False,
    )
    worst = float(overview.get("worst_util", 0.0) or 0.0)
    focus = _governing_focus_from_overview(overview)
    ce_lines = _guidance_change_lines_for_updates(state, merged)
    return _guidance_item(
        focus,
        title,
        "Apply recommendation",
        None,
        reasoning,
        "Key levers: depth D, beam width, bottom reinforcement, shear links",
        "apply_compound_guidance",
        {
            "updates": merged,
            "guidance_banner_title": title,
            "guidance_banner_summary": reasoning,
        },
        status="EFFICIENCY",
        util=worst,
        guidance_change_lines=ce_lines or None,
        guidance_why=guidance_why,
    )


__all__ = [
    "bind_compound_strengthening_dependencies",
    "_try_compound_efficiency_guidance_item",
    "_try_compound_strengthening_guidance_item",
]
