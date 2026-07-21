"""Auto-design candidate selection coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_AUTO_DESIGN_CANDIDATE_SELECTOR_DEPENDENCIES: tuple[str, ...] = (
    "_ACTIVE_GUIDANCE_RANK_TRACE",
    "_annotate_candidate_target_band_metrics",
    "_band_reacher_delta_metrics",
    "_candidate_in_target_band",
    "_candidate_violation_score",
    "_design_optimisation_goal",
    "_design_width_value",
    "_float_from_state",
    "_int_from_state",
    "_merge_design_guide_rank_trace",
    "_score_auto_design_candidate",
    "_score_band_reaching_candidate_for_goal",
    "_shallower_beam_selection_key",
    "is_valid_reo_layout",
)


def bind_auto_design_candidate_selector_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _AUTO_DESIGN_CANDIDATE_SELECTOR_DEPENDENCIES
            if name in namespace
        }
    )


def _select_best_auto_design_candidate(candidates: list[dict], mode_config: dict, seed_candidate: dict) -> dict | None:
    if not candidates:
        return None
    valid_candidates: list[dict] = []
    for candidate in candidates:
        cs = dict(candidate.get("state") or {})
        beam_width = float(_design_width_value(cs) or 0.0)
        cover = float(_float_from_state(cs, "cover_side", 40.0) or 40.0)
        bot1_count = int(_int_from_state(cs, "bot1_count", 0) or 0)
        bot2_count = int(_int_from_state(cs, "bot2_count", 0) or 0)
        db_bot_1 = float(_float_from_state(cs, "db_bot_1", 0.0) or 0.0)
        db_bot_2 = float(_float_from_state(cs, "db_bot_2", db_bot_1) or db_bot_1)

        row1_valid = is_valid_reo_layout(
            bot1_count,
            db_bot_1,
            beam_width,
            cover,
            max(db_bot_1, 25.0),
        )
        row2_valid = True
        if bot2_count > 0:
            row2_valid = is_valid_reo_layout(
                bot2_count,
                db_bot_2,
                beam_width,
                cover,
                max(db_bot_2, 25.0),
            )
        if not row1_valid or not row2_valid:
            continue  # reject immediately

        _annotate_candidate_target_band_metrics(candidate, mode_config)
        candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        valid_candidates.append(candidate)
    candidates = valid_candidates
    if not candidates:
        return None
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    compliant = [candidate for candidate in candidates if candidate.get("is_compliant")]
    band_reachers = [candidate for candidate in compliant if candidate.get("candidate_reaches_target_band")]
    one_click_available = len(band_reachers) > 0
    current_in_band = bool(seed_candidate.get("is_compliant")) and _candidate_in_target_band(seed_candidate, mode_config)
    in_band = [candidate for candidate in compliant if _candidate_in_target_band(candidate, mode_config)]
    best_scored_compliant = (
        (
            min(compliant, key=lambda item: _shallower_beam_selection_key(item, seed_candidate, mode_config))
            if strategy == "shallow" else
            min(compliant, key=lambda item: (item["score"], item["depth"], item["width"]))
        )
        if compliant else None
    )
    best_scored_in_band = (
        (
            min(in_band, key=lambda item: _shallower_beam_selection_key(item, seed_candidate, mode_config))
            if strategy == "shallow" else
            min(in_band, key=lambda item: (item["score"], item["depth"], item["width"]))
        )
        if in_band else None
    )
    if _ACTIVE_GUIDANCE_RANK_TRACE is not None:
        local_only = bool(compliant) and not one_click_available
        reason = (
            "at_least_one_compliant_candidate_reaches_target_band_in_one_move"
            if one_click_available
            else (
                "no_compliant_candidate_reaches_target_band_in_one_move"
                if compliant
                else "no_compliant_candidates"
            )
        )
        _merge_design_guide_rank_trace(
            {
                "auto_design_convergence_selection": {
                    "one_click_convergence_available": one_click_available,
                    "one_click_convergence_reason": reason,
                    "local_step_selected_only_because_no_band_reaching_candidate": local_only,
                    "compliant_count": len(compliant),
                    "band_reacher_count": len(band_reachers),
                    "winner_pool_mode": (
                        "band_reachers_only"
                        if (not current_in_band and bool(band_reachers))
                        else "all_compliant"
                    ),
                    "band_reacher_labels_considered": [
                        str(c.get("label") or "")[:100]
                        for c in band_reachers[:24]
                    ],
                },
            },
        )
    winner: dict | None = None
    selected_because_band = False
    winner_pool_mode = "all_compliant"
    winner_goal_score: float | None = None
    runner_up_goal_score: float | None = None
    goal_tie_break_reason: str | None = None
    if compliant:
        force_band_reacher_pool = bool((not current_in_band) and band_reachers)
        if force_band_reacher_pool:
            pool = band_reachers
            selected_because_band = True
            winner_pool_mode = "band_reachers_only"
        else:
            pool = compliant
            selected_because_band = False
            winner_pool_mode = "all_compliant"
        if selected_because_band:
            goal = _design_optimisation_goal(dict(seed_candidate.get("state") or {}))
            pref = "shallower" if goal == "shallower_beam" else "balanced"
            current_state = dict(seed_candidate.get("state") or {})
            ranked_pool: list[tuple[tuple, dict]] = []
            for item in pool:
                gscore, greason = _score_band_reaching_candidate_for_goal(
                    item,
                    goal,
                    current_state,
                    mode_config,
                )
                deltas = _band_reacher_delta_metrics(item, current_state)
                item["winning_candidate_goal_preference"] = pref
                item["candidate_goal_score"] = gscore
                item["candidate_goal_tie_break_reason"] = greason
                item["candidate_goal_delta_d_mm"] = deltas.get("delta_d")
                item["candidate_goal_delta_ast_mm2"] = deltas.get("delta_ast")
                item["candidate_goal_delta_w_mm"] = deltas.get("delta_w")
                if goal == "shallower_beam":
                    rank_key = (
                        float(gscore),
                        float(deltas.get("result_depth", item.get("depth", 0.0)) or 0.0),
                        float(deltas.get("delta_ast", 0.0) or 0.0),
                        float(deltas.get("delta_w", 0.0) or 0.0),
                        _shallower_beam_selection_key(item, seed_candidate, mode_config) if strategy == "shallow" else (),
                        float(item.get("score", 0.0) or 0.0),
                        float(item.get("depth", 0.0) or 0.0),
                        float(item.get("width", 0.0) or 0.0),
                    )
                else:
                    rank_key = (
                        float(gscore),
                        float(item.get("score", 0.0) or 0.0),
                        float(deltas.get("congestion", 0.0) or 0.0),
                        float(deltas.get("row_pen", 0.0) or 0.0),
                        float(deltas.get("delta_d", 0.0) or 0.0),
                        float(deltas.get("delta_w", 0.0) or 0.0),
                        float(deltas.get("delta_ast", 0.0) or 0.0),
                        float(item.get("depth", 0.0) or 0.0),
                        float(item.get("width", 0.0) or 0.0),
                    )
                ranked_pool.append((rank_key, item))
            ranked_pool.sort(key=lambda row: row[0])
            winner = ranked_pool[0][1]
            winner_goal_score = float(winner.get("candidate_goal_score", 0.0) or 0.0)
            goal_tie_break_reason = str(winner.get("candidate_goal_tie_break_reason") or "")
            if len(ranked_pool) > 1:
                runner = ranked_pool[1][1]
                runner_up_goal_score = float(runner.get("candidate_goal_score", 0.0) or 0.0)
                winner["runner_up_goal_score"] = runner_up_goal_score
        else:
            if strategy == "shallow":
                winner = min(pool, key=lambda item: _shallower_beam_selection_key(item, seed_candidate, mode_config))
            else:
                winner = min(
                    pool,
                    key=lambda item: (
                        item["score"],
                        float(item.get("candidate_distance_to_target_band") or 0.0),
                        item["depth"],
                        item["width"],
                    ),
                )
    else:
        winner = min(
            candidates,
            key=lambda item: (
                _candidate_violation_score(item),
                _shallower_beam_selection_key(item, seed_candidate, mode_config) if strategy == "shallow" else (),
                item["score"],
                item["depth"],
                item["width"],
            ),
        )
        selected_because_band = False
    if winner is not None:
        winner["winning_candidate_post_util"] = winner.get("candidate_post_util")
        winner["winning_candidate_reaches_target_band"] = winner.get("candidate_reaches_target_band")
        winner["winning_candidate_distance_to_target_band"] = winner.get("candidate_distance_to_target_band")
        winner["winning_candidate_selected_because_reaches_band"] = selected_because_band
        winner["winning_candidate_selected_from_band_reachers"] = selected_because_band
        winner["winner_pool_mode"] = winner_pool_mode
        winner["band_reacher_labels_considered"] = [str(c.get("label") or "")[:100] for c in band_reachers[:24]]
        winner["winning_candidate_goal_score"] = winner_goal_score
        winner["runner_up_goal_score"] = runner_up_goal_score
        winner["goal_tie_break_reason"] = goal_tie_break_reason
        winner["winning_candidate_goal_preference"] = (
            "shallower"
            if _design_optimisation_goal(dict(seed_candidate.get("state") or {})) == "shallower_beam"
            else "balanced"
        )
        _wl = str(winner.get("label") or "").strip()
        if _wl:
            winner["canonical_winner_label"] = _wl
            winner["title_locked_from_final_winner"] = True
        if _ACTIVE_GUIDANCE_RANK_TRACE is not None:
            _merge_design_guide_rank_trace(
                {
                    "auto_design_goal_tie_break": {
                        "winning_candidate_goal_score": winner_goal_score,
                        "runner_up_goal_score": runner_up_goal_score,
                        "goal_tie_break_reason": goal_tie_break_reason,
                        "winning_candidate_goal_preference": winner.get("winning_candidate_goal_preference"),
                        "winner_label": str(winner.get("label") or ""),
                    },
                    "auto_design_final_selector": {
                        "winner_pool_mode": winner_pool_mode,
                        "selected_because_band": selected_because_band,
                        "final_winner_label": str(winner.get("label") or ""),
                        "final_winner_reaches_target_band": bool(winner.get("candidate_reaches_target_band")),
                        "final_winner_post_util": winner.get("candidate_post_util"),
                        "final_winner_goal_score": winner_goal_score,
                    },
                },
            )
    return winner


__all__ = [
    "bind_auto_design_candidate_selector_dependencies",
    "_select_best_auto_design_candidate",
]
