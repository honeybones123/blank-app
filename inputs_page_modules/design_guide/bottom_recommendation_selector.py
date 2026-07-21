"""Bottom-reinforcement recommendation selector coordination."""

from __future__ import annotations

from typing import Any


_BOTTOM_RECOMMENDATION_SELECTOR_DEPENDENCIES: tuple[str, ...] = (
    "GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS",
    "_candidate_ductility_governs",
    "_candidate_ductility_util",
    "_geometry_trial_axis_for_bottom_rec",
    "_is_strictly_rejectable_band_winner",
    "_legacy_bottom_local_rejection_reason",
    "_log_design_reco_candidate_rank",
    "_merge_design_guide_rank_trace",
    "_score_auto_design_candidate",
    "_select_best_auto_design_candidate",
    "_updates_match_state",
)


def bind_bottom_recommendation_selector_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _BOTTOM_RECOMMENDATION_SELECTOR_DEPENDENCIES
            if name in namespace
        }
    )


def _collapse_bottom_geometry_width_depth_trials(
    filtered: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
    efficiency_reduction_only: bool = False,
) -> list[dict]:
    if efficiency_reduction_only:
        _merge_design_guide_rank_trace(
            {
                "bottom_geo_collapse": {
                    "geometry_mode": "reduction",
                    "chosen_axis": None,
                    "chosen_axis_reason": "efficiency_reduction_only_skip_growth_axis_compare",
                    "rejected_growth_axes": ["depth", "width"],
                }
            }
        )
        return filtered
    pure = [c for c in filtered if not c.get("recommendation_compound")]
    compounds = [c for c in filtered if c.get("recommendation_compound")]
    geo = [c for c in pure if c.get("recommendation_geometry_trial")]
    reo = [c for c in pure if not c.get("recommendation_geometry_trial")]
    if not geo or not reo:
        return filtered
    depth_geo = [c for c in geo if _geometry_trial_axis_for_bottom_rec(c, state) == "depth"]
    width_geo = [c for c in geo if _geometry_trial_axis_for_bottom_rec(c, state) == "width"]
    if not depth_geo or not width_geo:
        return filtered
    for c in depth_geo + width_geo:
        if c.get("score") is None:
            c["score"] = _score_auto_design_candidate(c, mode_config, seed_candidate)
    best_depth = _select_best_auto_design_candidate(depth_geo, mode_config, seed_candidate)
    best_width = _select_best_auto_design_candidate(width_geo, mode_config, seed_candidate)
    if not best_depth or not best_width:
        return filtered
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow":
        sd = float(best_depth.get("score", float("inf")) or float("inf"))
        sw = float(best_width.get("score", float("inf")) or float("inf"))
        if sw <= sd + GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS:
            chosen = best_width
            depth_beat_width_reason = (
                f"depth_score_not_better_by_{GUIDANCE_SHALLOW_GEOMETRY_SCORE_TIE_EPS:.0f}"
                if sd + 1e-9 < sw
                else "scores_tied_prefer_width"
            )
        else:
            chosen = best_depth
            depth_beat_width_reason = "depth_score_materially_better_than_width"
        _merge_design_guide_rank_trace(
            {
                "bottom_geo_collapse": {
                    "geometry_mode": "growth",
                    "best_depth_score": sd,
                    "best_width_score": sw,
                    "chosen_axis": "width" if chosen is best_width else "depth",
                    "depth_beat_width_reason": depth_beat_width_reason,
                }
            }
        )
    else:
        chosen = _select_best_auto_design_candidate([best_depth, best_width], mode_config, seed_candidate)
        if chosen:
            _merge_design_guide_rank_trace(
                {
                    "bottom_geo_collapse": {
                        "geometry_mode": "growth",
                        "chosen_axis": _geometry_trial_axis_for_bottom_rec(chosen, state),
                        "chosen_axis_reason": "balanced_mode_best_of_width_depth",
                    }
                }
            )
    if not chosen:
        return compounds + pure
    other_geo = [
        c for c in geo if _geometry_trial_axis_for_bottom_rec(c, state) not in ("depth", "width")
    ]
    return compounds + reo + [chosen] + other_geo


def _pick_best_bottom_recommendation_by_selector(
    candidates: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> dict | None:
    pool = [c for c in candidates if c]
    seed_bu = ((seed_candidate.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        seed_bu_f = float(seed_bu) if seed_bu is not None else None
    except (TypeError, ValueError):
        seed_bu_f = None
    ductility_seed = _candidate_ductility_governs(seed_candidate)
    seed_du = _candidate_ductility_util(seed_candidate)
    while pool:
        pick = _select_best_auto_design_candidate(pool, mode_config, seed_candidate)
        if pick is None:
            return None
        _band_seen = bool(pick.get("candidate_reaches_target_band")) and bool(pick.get("is_compliant"))
        if _band_seen:
            _strict_reject, _strict_reason = _is_strictly_rejectable_band_winner(pick, state=state)
            if _strict_reject:
                _log_design_reco_candidate_rank(
                    domain="bending",
                    event="rejected",
                    candidate=pick,
                    reason=f"strict_band_reject:{_strict_reason}",
                )
                _merge_design_guide_rank_trace(
                    {
                        "final_selector_band_winner_seen": True,
                        "final_selector_band_winner_accepted": False,
                        "final_selector_band_winner_rejected_reason": str(_strict_reason),
                        "final_selector_used_strict_band_accept_rule": True,
                        "winner_pool_mode": pick.get("winner_pool_mode"),
                        "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                    },
                )
                pool = [x for x in pool if x is not pick]
                continue
            _legacy_reason = _legacy_bottom_local_rejection_reason(
                pick,
                seed_candidate=seed_candidate,
                seed_bu_f=seed_bu_f,
                ductility_seed=ductility_seed,
                seed_du=seed_du,
            )
            _log_design_reco_candidate_rank(
                domain="bending",
                event="accepted",
                candidate=pick,
                reason="strict_band_winner_accept",
                util_before=seed_du if ductility_seed else seed_bu_f,
                util_after=_candidate_ductility_util(pick) if ductility_seed else pick.get("candidate_post_util"),
            )
            _merge_design_guide_rank_trace(
                {
                    "final_selector_band_winner_seen": True,
                    "final_selector_band_winner_accepted": True,
                    "final_selector_band_winner_rejected_reason": None,
                    "final_selector_used_strict_band_accept_rule": True,
                    "winner_pool_mode": pick.get("winner_pool_mode"),
                    "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                    "final_winner_label": str(pick.get("label") or ""),
                    "final_winner_reaches_target_band": bool(pick.get("candidate_reaches_target_band")),
                    "final_winner_post_util": pick.get("candidate_post_util"),
                    "final_winner_goal_score": pick.get("candidate_goal_score"),
                    "final_selector_band_winner_would_have_legacy_reject_reason": _legacy_reason,
                    "final_selector_band_winner_accepted_over_legacy_gate": bool(_legacy_reason),
                },
            )
            return pick
        if not str(pick.get("label") or "").strip():
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="missing_label",
            )
            pool = [x for x in pool if x is not pick]
            continue
        if _updates_match_state(state, pick.get("updates") or {}):
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="noop_updates_match_state",
            )
            pool = [x for x in pool if x is not pick]
            continue
        bu = ((pick.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            bu_f = float(bu) if bu is not None else None
        except (TypeError, ValueError):
            bu_f = None
        if bu_f is None:
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="missing_bending_util",
            )
            pool = [x for x in pool if x is not pick]
            continue
        if ductility_seed:
            pdu = _candidate_ductility_util(pick)
            if seed_du is not None and pdu is not None and float(pdu) >= float(seed_du) - 1e-9:
                _log_design_reco_candidate_rank(
                    domain="bending",
                    event="rejected",
                    candidate=pick,
                    reason="ductility_not_improved",
                    util_before=float(seed_du),
                    util_after=float(pdu) if pdu is not None else None,
                )
                pool = [x for x in pool if x is not pick]
                continue
        elif seed_bu_f is not None and float(bu_f) >= float(seed_bu_f) - 1e-9:
            _log_design_reco_candidate_rank(
                domain="bending",
                event="rejected",
                candidate=pick,
                reason="bending_util_not_improved",
                util_before=float(seed_bu_f),
                util_after=float(bu_f),
            )
            pool = [x for x in pool if x is not pick]
            continue
        _log_design_reco_candidate_rank(
            domain="bending",
            event="accepted",
            candidate=pick,
            reason="selector_top_valid",
            util_before=seed_du if ductility_seed else seed_bu_f,
            util_after=_candidate_ductility_util(pick) if ductility_seed else bu_f,
        )
        _merge_design_guide_rank_trace(
            {
                "final_selector_band_winner_seen": False,
                "final_selector_band_winner_accepted": False,
                "final_selector_band_winner_rejected_reason": None,
                "final_selector_used_strict_band_accept_rule": False,
                "winner_pool_mode": pick.get("winner_pool_mode"),
                "selected_because_band": bool(pick.get("winning_candidate_selected_from_band_reachers")),
                "final_winner_label": str(pick.get("label") or ""),
                "final_winner_reaches_target_band": bool(pick.get("candidate_reaches_target_band")),
                "final_winner_post_util": pick.get("candidate_post_util"),
                "final_winner_goal_score": pick.get("candidate_goal_score"),
            },
        )
        return pick
    return None
