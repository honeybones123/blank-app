"""Permanent typed primary objective search for Inputs auto design."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PrimaryAutoDesignRuntime:
    allow_early_target_exit: Callable[..., Any]
    candidate_is_good_enough: Callable[..., Any]
    candidate_materially_worsens: Callable[..., Any]
    candidate_sort_key_for_mode: Callable[..., Any]
    compute_reo_complexity: Callable[..., Any]
    ensure_candidate_score: Callable[..., Any]
    float_from_state: Callable[..., Any]
    generate_balanced_geometry_options: Callable[..., Any]
    generate_same_or_larger_geometry_options: Callable[..., Any]
    generate_slightly_deeper_depths: Callable[..., Any]
    geometry_lock_enabled: Callable[..., Any]
    geometry_state_with_updates: Callable[..., Any]
    make_candidate_key: Callable[..., Any]
    resolve_geometry_width_context: Callable[..., Any]
    select_best_next_hop_candidate: Callable[..., Any]
    select_final_candidate: Callable[..., Any]
    solve_reo_for_geometry: Callable[..., Any]
    utilisation_gap: Callable[..., Any]


def run_primary_auto_design(
    seed_candidate: dict,
    mode_config: dict,
    eval_cache: dict,
    metrics: dict,
    *,
    is_first_hop: bool = False,
    runtime: PrimaryAutoDesignRuntime,
) -> dict:
    def solve(geometry_state: dict) -> dict | None:
        return runtime.solve_reo_for_geometry(
            geometry_state,
            mode_config=mode_config,
            seed_candidate=seed_candidate,
            eval_cache=eval_cache,
            metrics=metrics,
        )

    def choose_better(
        current_best: dict | None,
        candidate: dict | None,
    ) -> dict | None:
        if candidate is None:
            return current_best
        if current_best is None:
            return candidate
        if runtime.candidate_materially_worsens(
            candidate,
            current_best,
            mode_config,
            phase="mode_search",
        ):
            return current_best
        if not bool(current_best.get("is_compliant")):
            return (
                runtime.select_best_next_hop_candidate(
                    current_best,
                    [current_best, candidate],
                    mode_config,
                    phase="solve_to_pass",
                )
                or current_best
            )
        if runtime.candidate_sort_key_for_mode(
            candidate,
            mode_config,
        ) < runtime.candidate_sort_key_for_mode(
            current_best,
            mode_config,
        ):
            return candidate
        return current_best

    def shallow_geometry_options(
        candidate: dict,
        *,
        include_deeper: bool,
    ) -> list[dict]:
        seed_state = dict(candidate.get("state") or {})
        if runtime.geometry_lock_enabled(seed_state):
            return []
        seed_depth = float(
            candidate.get(
                "depth",
                runtime.float_from_state(seed_state, "D", 600.0),
            )
            or runtime.float_from_state(seed_state, "D", 600.0)
        )
        _, _, current_width = runtime.resolve_geometry_width_context(
            seed_state
        )
        target_depths = [
            seed_depth - 100.0,
            seed_depth - 50.0,
            seed_depth,
        ]
        if include_deeper:
            target_depths.extend(
                [seed_depth + 50.0, seed_depth + 100.0]
            )
        width_steps = [current_width, current_width + 50.0]
        if is_first_hop:
            width_steps.append(current_width + 100.0)
        options: dict[tuple, dict] = {}
        for depth in target_depths:
            if depth < 350.0:
                continue
            for width in width_steps:
                state = runtime.geometry_state_with_updates(
                    seed_state,
                    depth=depth,
                    width=width,
                )
                options[runtime.make_candidate_key(state)] = state
        return list(options.values())

    def optimise_shallow(candidate: dict) -> dict:
        best = candidate
        seed_state = dict(candidate.get("state") or {})
        seed_depth = float(
            candidate.get(
                "depth",
                runtime.float_from_state(seed_state, "D", 600.0),
            )
            or runtime.float_from_state(seed_state, "D", 600.0)
        )
        _, _, current_width = runtime.resolve_geometry_width_context(
            seed_state
        )
        same_geometry = solve(seed_state)
        best = choose_better(best, same_geometry) or best
        if same_geometry and runtime.candidate_is_good_enough(
            same_geometry,
            mode_config,
            reference_candidate=candidate,
        ):
            return same_geometry

        priority: dict[tuple, dict] = {}
        if is_first_hop:
            for depth, width in (
                (seed_depth - 50.0, current_width + 100.0),
                (seed_depth - 50.0, current_width + 50.0),
                (seed_depth, current_width + 50.0),
            ):
                if depth < 350.0:
                    continue
                state = runtime.geometry_state_with_updates(
                    seed_state,
                    depth=depth,
                    width=width,
                )
                priority[runtime.make_candidate_key(state)] = state
        for state in priority.values():
            if metrics.get("cap_hit"):
                return best
            result = solve(state)
            best = choose_better(best, result) or best
            if result and runtime.candidate_is_good_enough(
                result,
                mode_config,
                reference_candidate=candidate,
            ):
                return result

        if not is_first_hop and not bool(candidate.get("is_compliant")):
            for state in runtime.generate_slightly_deeper_depths(candidate):
                if metrics.get("cap_hit"):
                    return best
                result = solve(state)
                best = choose_better(best, result) or best
                if result and _is_valid_progress_while_failing(
                    result,
                    candidate,
                    make_candidate_key=runtime.make_candidate_key,
                ):
                    return result
        for state in shallow_geometry_options(
            candidate,
            include_deeper=False,
        ):
            if metrics.get("cap_hit"):
                return best
            result = solve(state)
            best = choose_better(best, result) or best
            if result and runtime.candidate_is_good_enough(
                result,
                mode_config,
                reference_candidate=candidate,
            ):
                return result
        for state in shallow_geometry_options(
            candidate,
            include_deeper=True,
        ):
            if float(
                state.get("D", candidate.get("depth", 0.0)) or 0.0
            ) <= float(candidate.get("depth", 0.0) or 0.0):
                continue
            if metrics.get("cap_hit"):
                return best
            result = solve(state)
            best = choose_better(best, result) or best
            if result and runtime.candidate_is_good_enough(
                result,
                mode_config,
                reference_candidate=candidate,
            ):
                return result
        return best

    def optimise_low_reo(candidate: dict) -> dict:
        best = candidate
        same_geometry = solve(candidate["state"])
        best = choose_better(best, same_geometry) or best
        if same_geometry and runtime.candidate_is_good_enough(
            same_geometry,
            mode_config,
            reference_candidate=candidate,
        ):
            return same_geometry
        for state in runtime.generate_same_or_larger_geometry_options(
            candidate
        ):
            if metrics.get("cap_hit"):
                return best
            result = solve(state)
            best = choose_better(best, result) or best
            if result and runtime.candidate_is_good_enough(
                result,
                mode_config,
                reference_candidate=candidate,
            ):
                return result
        return best

    def optimise_balanced(candidate: dict) -> dict:
        best = solve(candidate["state"]) or candidate
        if (
            runtime.candidate_is_good_enough(
                best,
                mode_config,
                reference_candidate=candidate,
            )
            and runtime.allow_early_target_exit(mode_config)
        ):
            return best
        for state in runtime.generate_balanced_geometry_options(candidate):
            if metrics.get("cap_hit"):
                return best
            result = solve(state)
            best = choose_better(best, result) or best
            if (
                result
                and runtime.candidate_is_good_enough(
                    result,
                    mode_config,
                    reference_candidate=candidate,
                )
                and runtime.allow_early_target_exit(mode_config)
            ):
                return result
        return best

    def objective_search(candidate: dict) -> dict:
        if runtime.geometry_lock_enabled(
            (candidate or {}).get("state") or {}
        ):
            return solve(candidate["state"]) or candidate
        strategy = str(
            mode_config.get("search_strategy", "balanced") or "balanced"
        )
        if strategy == "shallow":
            return optimise_shallow(candidate)
        if strategy == "low_reo":
            return optimise_low_reo(candidate)
        return optimise_balanced(candidate)

    runtime.ensure_candidate_score(
        seed_candidate,
        mode_config,
        seed_candidate,
    )
    if bool(seed_candidate.get("is_compliant")) and (
        _candidate_in_target_zone(seed_candidate, mode_config)
    ):
        metrics["phase_a"] = "seed_in_target_cleanup_only"
        metrics["phase_b"] = "cleanup_only"
        return seed_candidate
    phase_results = [seed_candidate]
    feasibility = seed_candidate
    metrics["phase_a"] = (
        "seed_already_compliant"
        if bool(seed_candidate.get("is_compliant"))
        else "search_for_compliance"
    )
    if not bool(seed_candidate.get("is_compliant")):
        feasibility = objective_search(seed_candidate) or seed_candidate
        runtime.ensure_candidate_score(
            feasibility,
            mode_config,
            seed_candidate,
        )
        phase_results.append(feasibility)
    objective_seed = (
        runtime.select_final_candidate(
            phase_results,
            mode_config,
            baseline_candidate=seed_candidate,
        )
        or feasibility
        or seed_candidate
    )
    metrics["phase_b"] = "objective_search"
    objective = objective_search(objective_seed) or objective_seed
    runtime.ensure_candidate_score(
        objective,
        mode_config,
        seed_candidate,
    )
    phase_results.append(objective)
    selected = (
        runtime.select_final_candidate(
            phase_results,
            mode_config,
            baseline_candidate=seed_candidate,
        )
        or objective
        or objective_seed
    )
    metrics["primary_phase_result"] = {
        "is_compliant": bool(selected.get("is_compliant")),
        "util_gap": runtime.utilisation_gap(selected, mode_config),
        "depth": float(selected.get("depth", 0.0) or 0.0),
        "reo_complexity": float(
            selected.get(
                "reo_complexity",
                runtime.compute_reo_complexity(selected),
            )
            or 0.0
        ),
    }
    return selected


def _candidate_in_target_zone(
    candidate: dict,
    mode_config: dict,
) -> bool:
    if not candidate or not bool(candidate.get("is_compliant")):
        return False
    util = float(candidate.get("worst_util", 0.0) or 0.0)
    target_min = float(
        mode_config.get("target_util_min", 0.80) or 0.80
    )
    target_max = float(
        mode_config.get("target_util_max", 0.90) or 0.90
    )
    return target_min <= util <= target_max


def _is_valid_progress_while_failing(
    new_candidate: dict | None,
    old_candidate: dict | None,
    *,
    make_candidate_key: Callable[[dict], tuple],
) -> bool:
    if not new_candidate or not old_candidate:
        return False
    if bool(new_candidate.get("is_compliant")):
        return True

    def failures(candidate: dict) -> set[str]:
        statuses = (
            (candidate.get("overview") or {}).get("statuses", {}) or {}
        )
        return {
            key
            for key in ("bending", "shear", "crack", "deflection")
            if str(statuses.get(key, "") or "") == "FAIL"
        }

    old_failed = failures(old_candidate)
    new_failed = failures(new_candidate)
    old_util = float(old_candidate.get("worst_util", 999.0) or 999.0)
    new_util = float(new_candidate.get("worst_util", 999.0) or 999.0)
    if new_failed != old_failed and len(new_failed) < len(old_failed):
        return True
    if new_util < old_util - 0.01:
        return True
    return make_candidate_key(
        dict(new_candidate.get("state") or {})
    ) != make_candidate_key(dict(old_candidate.get("state") or {}))
__all__ = ["PrimaryAutoDesignRuntime", "run_primary_auto_design"]
