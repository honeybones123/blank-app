"""One-click candidate solver coordination for the Inputs page."""

from __future__ import annotations

from typing import Any


_ONE_CLICK_CANDIDATE_SOLVER_DEPENDENCIES: tuple[str, ...] = (
    "EFFICIENCY_TARGET_UTIL_MAX",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "_COMPOUND_BOTTOM_UPDATE_KEYS",
    "_COMPOUND_GEOMETRY_UPDATE_KEYS",
    "_annotate_candidate_target_band_metrics",
    "_augment_candidate_with_shear_if_needed",
    "_build_candidate_search_evidence",
    "_candidate_bottom_updates",
    "_candidate_cache_key",
    "_collect_design_overview",
    "_compound_guidance_title_reasoning_why",
    "_compound_subfamilies_from_updates",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_design_width_value",
    "_effective_bottom_design_state",
    "_enumerate_bottom_reo_design_trials",
    "_evaluate_auto_design_candidate",
    "_family_tag_from_compound_updates",
    "_float_from_state",
    "_geometry_state_with_updates",
    "_guidance_change_lines_for_updates",
    "_merge_design_guide_rank_trace",
    "_prefer_augmented_candidate",
    "_quick_bending_util",
    "time",
    "speed_profile_record",
)


def bind_one_click_candidate_solver_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _ONE_CLICK_CANDIDATE_SOLVER_DEPENDENCIES
            if name in namespace
        }
    )


def _solve_one_click_candidate(
    state: dict,
    *,
    goal: str | None = None,
    expanded: bool = False,
    debug_enabled: bool = False,
) -> dict | None:
    """
    Bounded one-click solver:
    - searches a practical space of geometry + bottom reinforcement combinations
    - returns the best compliant candidate near the target band
    - returns None if no compliant candidate exists in the bounded search space

    Uses a small geometry grid first; if no in-band compliant candidate is found, reruns with
    the full grid (expanded=True) to match the legacy search breadth.
    """
    if not isinstance(state, dict):
        return None

    goal_name = str(goal or _design_optimisation_goal(state) or "balanced")
    mode_cfg = _design_mode_config(goal_name)
    target_min = float(mode_cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    target_max = float(mode_cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    width_key, _, base_width = _resolve_geometry_width_context(state)
    base_width = float(base_width or 0.0)
    base_depth = float(_float_from_state(state, "D", 0.0) or 0.0)

    width_steps_full = [0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0]
    depth_steps_full = [0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0]
    width_steps_small = [0.0, 25.0, 50.0]
    depth_steps_small = [0.0, 25.0, 50.0, 75.0]

    def _distance_to_band(util: float) -> float:
        if util < target_min:
            return target_min - util
        if util > target_max:
            return util - target_max
        return 0.0

    def _run_pass(width_steps: list[float], depth_steps: list[float]) -> tuple[list[dict], int, int, float | None, list[int], dict[float, list[dict]]]:
        _run_pass_t0 = time.perf_counter()
        evaluated_candidates: list[dict] = []
        explored_candidates = 0
        skipped_invalid = 0
        best_noncompliant_worst_util = None
        bottom_trial_cache: dict[float, list[dict]] = {}
        observed_bottom_trial_counts: list[int] = []
        seen_keys: set[tuple] = set()
        current_overview = _collect_design_overview(state)
        current_fail_keys = sorted(
            [
                key
                for key, val in (current_overview.get("statuses") or {}).items()
                if str(val or "").upper() == "FAIL"
            ],
        )

        def _resolve_failure_coverage(candidate: dict) -> dict:
            coverage = dict(candidate.get("failure_coverage") or candidate.get("failure_coverage_summary") or {})
            if not coverage:
                candidate_overview = dict(candidate.get("overview") or {})
                candidate_fail_keys = sorted(
                    [
                        key
                        for key, val in (candidate_overview.get("statuses") or {}).items()
                        if str(val or "").upper() == "FAIL"
                    ],
                )
                covered = sorted([k for k in current_fail_keys if k not in candidate_fail_keys])
                remaining = sorted([k for k in current_fail_keys if k in candidate_fail_keys])
                coverage = {
                    "current_fail_keys": list(current_fail_keys),
                    "candidate_fail_keys": list(candidate_fail_keys),
                    "covered_fail_keys": list(covered),
                    "remaining_fail_keys": list(remaining),
                    "covers_all_current_failures": len(current_fail_keys) > 0 and len(remaining) == 0,
                }
            candidate["failure_coverage"] = dict(coverage)
            candidate["failure_coverage_summary"] = dict(coverage)
            candidate["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
            candidate["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
            candidate["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])
            return coverage

        def _prefer_augmented_candidate(base_candidate: dict, augmented_candidate: dict) -> bool:
            if not (isinstance(base_candidate, dict) and isinstance(augmented_candidate, dict)):
                return False
            base_compliant = bool(base_candidate.get("is_compliant"))
            augmented_compliant = bool(augmented_candidate.get("is_compliant"))
            if augmented_compliant and not base_compliant:
                return True
            if not (base_compliant and augmented_compliant):
                return False
            base_cov = _resolve_failure_coverage(base_candidate)
            aug_cov = _resolve_failure_coverage(augmented_candidate)
            base_covered = len(base_cov.get("covered_fail_keys") or [])
            aug_covered = len(aug_cov.get("covered_fail_keys") or [])
            if aug_covered > base_covered:
                return True
            if aug_covered != base_covered:
                return False
            try:
                base_dist = float(base_candidate.get("candidate_distance_to_target_band", float("inf")) or float("inf"))
            except Exception:
                base_dist = float("inf")
            try:
                aug_dist = float(augmented_candidate.get("candidate_distance_to_target_band", float("inf")) or float("inf"))
            except Exception:
                aug_dist = float("inf")
            return aug_dist < base_dist

        for db in width_steps:
            for dD in depth_steps:
                geom_state = _geometry_state_with_updates(
                    state,
                    depth=(base_depth + dD) if dD else None,
                    width=(base_width + db) if db else None,
                )
                geom_updates: dict[str, object] = {}
                geom_D = float(_float_from_state(geom_state, "D", base_depth) or base_depth)
                if abs(geom_D - base_depth) > 1e-9:
                    geom_updates["D"] = geom_D
                geom_w = float(_design_width_value(geom_state) or base_width)
                if abs(geom_w - base_width) > 1e-9:
                    geom_updates[width_key] = geom_w
                    if width_key != "b":
                        geom_updates["b"] = geom_w

                width_bucket = round(float(geom_w), 3)
                trial_pool = bottom_trial_cache.get(width_bucket)
                if trial_pool is None:
                    try:
                        trial_pool = list(_enumerate_bottom_reo_design_trials(geom_state, mode_config=mode_cfg) or [])
                    except Exception:
                        trial_pool = []
                    if not trial_pool:
                        trial_pool = [{"label": "Keep current bottom reo", "updates": {}}]
                    bottom_trial_cache[width_bucket] = trial_pool
                observed_bottom_trial_counts.append(len(trial_pool))

                for trial in trial_pool:
                    trial_updates = dict(trial.get("updates") or {})
                    merged_updates = dict(geom_updates)
                    merged_updates.update(trial_updates)
                    if not merged_updates:
                        continue
                    trial_state = dict(state)
                    trial_state.update(merged_updates)
                    trial_key = _candidate_cache_key(trial_state)
                    if trial_key in seen_keys:
                        continue
                    seen_keys.add(trial_key)
                    if _quick_bending_util(trial_state) > 2.0:
                        continue
                    explored_candidates += 1
                    update_keys = set(merged_updates.keys())
                    has_geom = bool(update_keys & _COMPOUND_GEOMETRY_UPDATE_KEYS)
                    has_bottom = bool(update_keys & _COMPOUND_BOTTOM_UPDATE_KEYS)
                    if has_geom and has_bottom:
                        candidate_action_type = "apply_compound_guidance"
                    elif has_bottom:
                        candidate_action_type = "apply_bottom_recommendation"
                    else:
                        candidate_action_type = "apply_geometry_recommendation"
                    try:
                        evaluated = _evaluate_auto_design_candidate(
                            state,
                            updates=merged_updates,
                            source="one_click_solver_search",
                            label=str(trial.get("label") or "Apply one-click design"),
                            action_type=candidate_action_type,
                        )
                    except Exception:
                        skipped_invalid += 1
                        continue
                    if not isinstance(evaluated, dict):
                        skipped_invalid += 1
                        continue
                    _annotate_candidate_target_band_metrics(evaluated, mode_cfg)
                    post_util = evaluated.get("candidate_post_util", evaluated.get("worst_util"))
                    try:
                        post_util = float(post_util) if post_util is not None else None
                    except Exception:
                        post_util = None
                    if post_util is None:
                        continue
                    reaches_band = bool(target_min <= post_util <= target_max)
                    resolved = dict(evaluated)
                    resolved["candidate_reaches_target_band"] = reaches_band
                    resolved["reaches_target_band"] = reaches_band
                    resolved["updates"] = dict(merged_updates)
                    resolved["action_type"] = "apply_resolved_candidate"
                    resolved["guidance_change_lines"] = _guidance_change_lines_for_updates(state, merged_updates)
                    subfamilies = _compound_subfamilies_from_updates(merged_updates)
                    resolved["subfamilies"] = list(subfamilies)
                    resolved["recommendation_family_tag"] = _family_tag_from_compound_updates(merged_updates, state)
                    resolved["is_compound"] = bool(has_geom and has_bottom)
                    resolved["compound_shear_augmented"] = False
                    title, _, _ = _compound_guidance_title_reasoning_why(
                        state,
                        merged_updates,
                        subfamilies,
                        strengthening=True,
                    )
                    resolved["label"] = str(title or trial.get("label") or "Apply one-click design")
                    _resolve_failure_coverage(resolved)
                    candidates_to_add = [resolved]
                    augmented = _augment_candidate_with_shear_if_needed(
                        state,
                        resolved,
                        mode_cfg=mode_cfg,
                    )
                    if isinstance(augmented, dict):
                        _resolve_failure_coverage(augmented)
                        if _prefer_augmented_candidate(resolved, augmented):
                            augmented["one_click_compound_preferred"] = True
                        candidates_to_add.append(augmented)
                    for candidate_variant in candidates_to_add:
                        evaluated_candidates.append(candidate_variant)
                        if not bool(candidate_variant.get("is_compliant")):
                            try:
                                wu = float(candidate_variant.get("worst_util", 0.0) or 0.0)
                                if best_noncompliant_worst_util is None or wu < best_noncompliant_worst_util:
                                    best_noncompliant_worst_util = wu
                            except Exception:
                                pass

        speed_profile_record(
            "candidate_generation.solve_one_click_candidate.run_pass",
            (time.perf_counter() - _run_pass_t0) * 1000.0,
            category="compute",
        )
        return (
            evaluated_candidates,
            explored_candidates,
            skipped_invalid,
            best_noncompliant_worst_util,
            observed_bottom_trial_counts,
            bottom_trial_cache,
        )

    def _trace_no_compliant(
        explored: int,
        skipped: int,
        obs_counts: list[int],
        btcache: dict[float, list[dict]],
        bnu: float | None,
        *,
        solver_expanded: bool,
    ) -> None:
        if not debug_enabled:
            return
        _merge_design_guide_rank_trace(
            {
                "one_click_solver": {
                    "searched": True,
                    "goal": goal_name,
                    "explored_candidates": explored,
                    "skipped_invalid": skipped,
                    "compliant_count": 0,
                    "band_reacher_count": 0,
                    "result": "no_compliant_candidates",
                    "one_click_solver_expanded": bool(solver_expanded),
                },
            },
        )

    def _trace_winner(
        winner: dict,
        all_candidates: list[dict],
        band_reachers: list[dict],
        explored: int,
        skipped: int,
        *,
        solver_expanded: bool,
    ) -> None:
        evidence = _build_candidate_search_evidence(
            selected_candidate=winner,
            all_candidates=list(all_candidates or []),
            target_low=float(target_min),
            target_high=float(target_max),
            exhaustive=bool(solver_expanded),
            search_scope="one_click_solver_geometry_bottom_shear_compound",
            selected_title=str(winner.get("label") or ""),
        )
        winner["candidate_search_evidence"] = dict(evidence)
        winner["candidate_id"] = evidence.get("selected_candidate_id")
        winner["source_candidate_id"] = evidence.get("selected_candidate_id")
        if not debug_enabled:
            return
        _merge_design_guide_rank_trace(
            {
                "one_click_solver": {
                    "searched": True,
                    "goal": goal_name,
                    "explored_candidates": explored,
                    "skipped_invalid": skipped,
                    "compliant_count": sum(1 for c in all_candidates if bool(c.get("is_compliant"))),
                    "band_reacher_count": len(band_reachers),
                    "used_pool": "all_scored_candidates",
                    "winner_label": winner.get("label"),
                    "winner_post_util": winner.get("candidate_post_util", winner.get("worst_util")),
                    "winner_reaches_target_band": bool(winner.get("candidate_reaches_target_band")),
                    "one_click_solver_expanded": bool(solver_expanded),
                    "candidate_search_evidence": dict(evidence),
                },
            },
        )

    if not expanded:
        small_candidates, ex_s, sk_s, bnu_s, obs_s, btc_s = _run_pass(width_steps_small, depth_steps_small)
        if small_candidates:
            current_ast = float(
                (
                    _effective_bottom_design_state(
                        state,
                        _candidate_bottom_updates(state),
                    ).get("Ast_bot", 0.0)
                    or 0.0
                ),
            )
            scored_small = []
            for candidate in small_candidates:
                util = candidate.get("candidate_post_util", candidate.get("worst_util"))
                scored_small.append(
                    (
                        (
                            0 if bool(candidate.get("is_compliant")) else 1,
                            0 if bool(candidate.get("covers_all_current_failures")) else 1,
                            len(candidate.get("remaining_fail_keys") or []),
                            -len(candidate.get("covered_fail_keys") or []),
                            0 if bool(candidate.get("one_click_compound_preferred")) else 1,
                            float(candidate.get("candidate_distance_to_target_band", _distance_to_band(float(util or 0.0)))),
                        score_candidate(util, candidate, current_ast=current_ast, goal=goal_name),
                        ),
                        candidate,
                    ),
                )
            scored_small.sort(key=lambda row: row[0])
            winner = scored_small[0][1]
            band_small = [c for c in small_candidates if bool(c.get("candidate_reaches_target_band"))]
            _trace_winner(winner, small_candidates, band_small, ex_s, sk_s, solver_expanded=False)
            if not bool(winner.get("candidate_reaches_target_band")):
                return _solve_one_click_candidate(
                    state,
                    goal=goal,
                    expanded=True,
                    debug_enabled=debug_enabled,
                )
            _wl = str(winner.get("label") or "").strip()
            if _wl:
                winner["canonical_winner_label"] = _wl
                winner["title_locked_from_final_winner"] = True
            return winner
        return _solve_one_click_candidate(
            state,
            goal=goal,
            expanded=True,
            debug_enabled=debug_enabled,
        )

    evaluated_candidates, explored_candidates, skipped_invalid, best_noncompliant_worst_util, observed_bottom_trial_counts, bottom_trial_cache = _run_pass(
        width_steps_full,
        depth_steps_full,
    )

    if not evaluated_candidates:
        _trace_no_compliant(
            explored_candidates,
            skipped_invalid,
            observed_bottom_trial_counts,
            bottom_trial_cache,
            best_noncompliant_worst_util,
            solver_expanded=True,
        )
        return None

    current_ast = float(
        (
            _effective_bottom_design_state(
                state,
                _candidate_bottom_updates(state),
            ).get("Ast_bot", 0.0)
            or 0.0
        ),
    )
    scored_candidates: list[tuple[tuple, dict]] = []
    for candidate in evaluated_candidates:
        util = candidate.get("candidate_post_util", candidate.get("worst_util"))
        scored_candidates.append(
            (
                (
                    0 if bool(candidate.get("is_compliant")) else 1,
                    0 if bool(candidate.get("covers_all_current_failures")) else 1,
                    len(candidate.get("remaining_fail_keys") or []),
                    -len(candidate.get("covered_fail_keys") or []),
                    0 if bool(candidate.get("one_click_compound_preferred")) else 1,
                    float(candidate.get("candidate_distance_to_target_band", _distance_to_band(float(util or 0.0)))),
                score_candidate(util, candidate, current_ast=current_ast, goal=goal_name),
                ),
                candidate,
            ),
        )
    scored_candidates.sort(key=lambda row: row[0])
    winner = scored_candidates[0][1]
    band_reachers = [c for c in evaluated_candidates if bool(c.get("candidate_reaches_target_band"))]
    _trace_winner(
        winner,
        evaluated_candidates,
        band_reachers,
        explored_candidates,
        skipped_invalid,
        solver_expanded=True,
    )
    _wl = str(winner.get("label") or "").strip()
    if _wl:
        winner["canonical_winner_label"] = _wl
        winner["title_locked_from_final_winner"] = True
    return winner


__all__ = [
    "bind_one_click_candidate_solver_dependencies",
    "_solve_one_click_candidate",
]
