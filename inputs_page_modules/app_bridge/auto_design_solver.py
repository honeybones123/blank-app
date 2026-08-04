"""Progressive auto-design solver bridge coordination."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Callable

from inputs_application.legacy_design_brain_adapter import CandidateEvaluationRegistry


_AUTO_DESIGN_SOLVER_DEPENDENCIES: tuple[str, ...] = (
    "AUTO_DESIGN_MAX_KEPT_RESULTS",
    "AUTO_DESIGN_MAX_TIGHTENING_ITERS",
    "TARGET_UTIL",
    "_agent_debug_log",
    "_allow_early_target_exit",
    "_apply_bottom_bar_count_update",
    "_auto_design_results_from_candidate",
    "_bottom_arrangement_to_shared_updates",
    "_build_auto_design_context",
    "_candidate_preserves_protected_case",
    "_candidate_materially_better_for_mode",
    "_candidate_reduces_noncritical_provision",
    "_candidate_worst_util_value",
    "_cleanup_candidate_debug_payload",
    "_cleanup_candidate_rank",
    "_collect_design_overview",
    "_critical_case_name",
    "_critical_case_util",
    "_design_mode_config",
    "_design_width_value",
    "_ensure_candidate_score",
    "_evaluate_candidate_fast",
    "_evaluate_progressive_candidate_update",
    "_float_from_state",
    "_generate_local_bottom_arrangements",
    "_generate_local_shear_states",
    "_geometry_lock_enabled",
    "_guidance_state_snapshot",
    "_int_from_state",
    "_keep_top_candidates",
    "_materialize_full_evaluated_candidate",
    "_overlay_current_normalized_shear_truth",
    "_protected_case_min_util",
    "_practical_bottom_reo_label",
    "_results_worst_util",
    "_resolve_geometry_width_context",
    "_score_auto_design_candidate",
    "_scaled_bottom_total_for_factor",
    "build_candidate",
    "choose_strategy",
    "collect_failures",
    "compute_reo_complexity",
    "evaluate_candidate_full",
    "candidate_materially_worsens",
    "candidate_is_good_enough",
    "generate_local_improvement_candidates",
    "generate_cleanup_candidates",
    "is_meaningfully_better",
    "run_primary_auto_design",
    "select_best_next_hop_candidate",
    "select_final_candidate",
    "run_auto_design_step",
    "utilisation_gap",
)


@dataclass(frozen=True)
class AutoDesignSolverRuntime:
    AUTO_DESIGN_MAX_KEPT_RESULTS: int
    AUTO_DESIGN_MAX_TIGHTENING_ITERS: int
    TARGET_UTIL: float
    _agent_debug_log: Callable[..., Any]
    _allow_early_target_exit: Callable[..., Any]
    _apply_bottom_bar_count_update: Callable[..., Any]
    _auto_design_results_from_candidate: Callable[..., Any]
    _bottom_arrangement_to_shared_updates: Callable[..., Any]
    _build_auto_design_context: Callable[..., Any]
    _candidate_preserves_protected_case: Callable[..., Any]
    _candidate_materially_better_for_mode: Callable[..., Any]
    _candidate_reduces_noncritical_provision: Callable[..., Any]
    _candidate_worst_util_value: Callable[..., Any]
    _cleanup_candidate_debug_payload: Callable[..., Any]
    _cleanup_candidate_rank: Callable[..., Any]
    _collect_design_overview: Callable[..., Any]
    _critical_case_name: Callable[..., Any]
    _critical_case_util: Callable[..., Any]
    _design_mode_config: Callable[..., Any]
    _design_width_value: Callable[..., Any]
    _ensure_candidate_score: Callable[..., Any]
    _evaluate_candidate_fast: Callable[..., Any]
    _evaluate_progressive_candidate_update: Callable[..., Any]
    _float_from_state: Callable[..., Any]
    _generate_local_bottom_arrangements: Callable[..., Any]
    _generate_local_shear_states: Callable[..., Any]
    _geometry_lock_enabled: Callable[..., Any]
    _guidance_state_snapshot: Callable[..., Any]
    _int_from_state: Callable[..., Any]
    _keep_top_candidates: Callable[..., Any]
    _materialize_full_evaluated_candidate: Callable[..., Any]
    _overlay_current_normalized_shear_truth: Callable[..., Any]
    _protected_case_min_util: Callable[..., Any]
    _practical_bottom_reo_label: Callable[..., Any]
    _results_worst_util: Callable[..., Any]
    _resolve_geometry_width_context: Callable[..., Any]
    _score_auto_design_candidate: Callable[..., Any]
    _scaled_bottom_total_for_factor: Callable[..., Any]
    build_candidate: Callable[..., Any]
    choose_strategy: Callable[..., Any]
    collect_failures: Callable[..., Any]
    compute_reo_complexity: Callable[..., Any]
    evaluate_candidate_full: Callable[..., Any]
    candidate_materially_worsens: Callable[..., Any]
    candidate_is_good_enough: Callable[..., Any]
    generate_local_improvement_candidates: Callable[..., Any]
    generate_cleanup_candidates: Callable[..., Any]
    is_meaningfully_better: Callable[..., Any]
    run_primary_auto_design: Callable[..., Any]
    select_best_next_hop_candidate: Callable[..., Any]
    select_final_candidate: Callable[..., Any]
    run_auto_design_step: Callable[..., Any]
    utilisation_gap: Callable[..., Any]


def _bind_auto_design_solver_runtime(runtime: AutoDesignSolverRuntime) -> None:
    globals().update(
        {
            field_name: getattr(runtime, field_name)
            for field_name in runtime.__dataclass_fields__
        }
    )


def bind_auto_design_solver_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _AUTO_DESIGN_SOLVER_DEPENDENCIES
            if name in namespace
        }
    )


def _build_progressive_candidate_updates(
    state: dict,
    results: dict,
    failures: list[tuple[str, float]],
    *,
    strategy: str,
) -> list[tuple[str, dict]]:
    width_key, _, current_width = _resolve_geometry_width_context(state)
    current_depth = _float_from_state(state, "D", 600.0)
    worst_util = _results_worst_util(results)
    if not math.isfinite(worst_util):
        worst_util = 1.0
    required_factor = max(float(worst_util) / TARGET_UTIL, 1.0)
    aggressive = worst_util > 2.0
    scale_factor = max(required_factor, 1.3 if aggressive else 1.0)
    current_spacing = _float_from_state(state, "s_lig", 200.0)

    compound_updates = build_candidate(state, strategy, results)
    if aggressive:
        compound_updates["D"] = float(current_depth * 1.3)
        _apply_bottom_bar_count_update(
            compound_updates,
            state,
            _scaled_bottom_total_for_factor(state, 1.3),
        )
    else:
        # Direct targeting toward utilisation 0.85.
        if required_factor > 1.0:
            compound_updates["D"] = float(current_depth * max(1.0, min(required_factor, 1.35)))
            _apply_bottom_bar_count_update(
                compound_updates,
                state,
                _scaled_bottom_total_for_factor(state, max(1.05, min(required_factor, 1.35))),
            )

    if any(name == "shear" for name, _ in failures):
        compound_updates["s_lig"] = float(max(75.0, current_spacing * (0.6 if aggressive else 0.7)))
        compound_updates["lig_legs"] = int(max(_int_from_state(state, "lig_legs", 2), 2))

    geometry_updates: dict[str, object] = {}
    if required_factor > 1.0:
        geometry_updates["D"] = float(current_depth * max(1.05, min(scale_factor, 1.4)))
    if int(results.get("row_count", 1) or 1) > 3 or required_factor > 1.2:
        geometry_updates[width_key] = float(current_width * (1.15 if aggressive else 1.08))
        if width_key != "b":
            geometry_updates["b"] = float(geometry_updates[width_key])
    if any(name == "shear" for name, _ in failures):
        geometry_updates["s_lig"] = float(max(75.0, current_spacing * (0.8 if aggressive else 0.9)))
        geometry_updates["lig_legs"] = int(max(_int_from_state(state, "lig_legs", 2), 2))

    reo_updates: dict[str, object] = {}
    if required_factor > 1.0:
        _apply_bottom_bar_count_update(
            reo_updates,
            state,
            _scaled_bottom_total_for_factor(state, max(1.05, min(scale_factor, 1.4))),
        )
    if any(name == "shear" for name, _ in failures):
        reo_updates["s_lig"] = float(max(75.0, current_spacing * (0.65 if aggressive else 0.75)))
        reo_updates["lig_legs"] = int(max(_int_from_state(state, "lig_legs", 2), 2))

    # Priority order is intentional: compound first, then geometry-only, then reo-only.
    prioritised_candidates = [
        ("compound", dict(compound_updates)),
        ("geometry", dict(geometry_updates)),
        ("reo", dict(reo_updates)),
    ]
    cleaned: list[tuple[str, dict]] = []
    for candidate_type, updates in prioritised_candidates:
        resolved = {
            key: value
            for key, value in dict(updates or {}).items()
            if state.get(key) != value
        }
        if resolved:
            cleaned.append((candidate_type, resolved))
    return cleaned


def _solve_reo_for_geometry(
    geometry_state: dict,
    *,
    mode_config: dict,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
    runtime: AutoDesignSolverRuntime | None = None,
) -> dict | None:
    if runtime is not None:
        _bind_auto_design_solver_runtime(runtime)
    solve_started = time.perf_counter()
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=metrics.get("_reference_overview"),
    )
    frontier: list[dict] = []
    base_candidate = _evaluate_candidate_fast(
        geometry_state,
        seed_state=seed_candidate["state"],
        context=context,
        eval_cache=eval_cache,
        metrics=metrics,
        source="geometry_seed",
        label=f"{int(_design_width_value(geometry_state))} x {int(_float_from_state(geometry_state, 'D', 0.0))} mm",
        action_type="auto_design",
    )
    if base_candidate is not None:
        frontier.append(base_candidate)
        if candidate_is_good_enough(base_candidate, mode_config) and _allow_early_target_exit(mode_config):
            metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
            return base_candidate

    max_frontier = int(mode_config.get("max_frontier", 4) or 4)
    for band in range(2):
        if metrics.get("cap_hit"):
            break

        gen_started = time.perf_counter()
        arrangements = _generate_local_bottom_arrangements(geometry_state, mode_config, band=band, context=context)
        metrics["candidate_generation_ms"] = float(metrics.get("candidate_generation_ms", 0.0) or 0.0) + ((time.perf_counter() - gen_started) * 1000.0)
        bottom_candidates: list[dict] = []
        for arrangement in arrangements:
            if metrics.get("cap_hit"):
                break
            candidate_state = dict(geometry_state)
            candidate_state.update(_bottom_arrangement_to_shared_updates(arrangement))
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="reo_band",
                label=_practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                ),
                action_type="auto_design",
            )
            if candidate is not None:
                bottom_candidates.append(candidate)
                if candidate_is_good_enough(candidate, mode_config) and _allow_early_target_exit(mode_config):
                    metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
                    return candidate

        prune_started = time.perf_counter()
        frontier = _keep_top_candidates(frontier + bottom_candidates, mode_config, limit=max_frontier)
        metrics["pruning_total_ms"] = float(metrics.get("pruning_total_ms", 0.0) or 0.0) + ((time.perf_counter() - prune_started) * 1000.0)
        metrics["kept_count"] = max(int(metrics.get("kept_count", 0) or 0), len(frontier))

        refined_candidates: list[dict] = []
        if not bool(context.get("disable_shear_strength_candidates")):
            for candidate in list(frontier):
                if metrics.get("cap_hit"):
                    break
                shear_started = time.perf_counter()
                shear_states = _generate_local_shear_states(candidate["state"], mode_config, band=band)
                metrics["candidate_generation_ms"] = float(metrics.get("candidate_generation_ms", 0.0) or 0.0) + ((time.perf_counter() - shear_started) * 1000.0)
                for shear_state in shear_states:
                    if metrics.get("cap_hit"):
                        break
                    refined = _evaluate_candidate_fast(
                        shear_state,
                        seed_state=seed_candidate["state"],
                        context=context,
                        eval_cache=eval_cache,
                        metrics=metrics,
                        source="shear_band",
                        label=str(candidate.get("label") or "Shear refinement"),
                        action_type="auto_design",
                    )
                    if refined is not None:
                        refined_candidates.append(refined)
                        if candidate_is_good_enough(refined, mode_config) and _allow_early_target_exit(mode_config):
                            metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
                            return refined

        prune_started = time.perf_counter()
        frontier = _keep_top_candidates(frontier + refined_candidates, mode_config, limit=max_frontier)
        metrics["pruning_total_ms"] = float(metrics.get("pruning_total_ms", 0.0) or 0.0) + ((time.perf_counter() - prune_started) * 1000.0)
        metrics["kept_count"] = max(int(metrics.get("kept_count", 0) or 0), len(frontier))

        best_candidate = frontier[0] if frontier else None
        if best_candidate and candidate_is_good_enough(best_candidate, mode_config) and _allow_early_target_exit(mode_config):
            metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
            return best_candidate

    best = frontier[0] if frontier else None
    metrics["solve_reo_total_ms"] = float(metrics.get("solve_reo_total_ms", 0.0) or 0.0) + ((time.perf_counter() - solve_started) * 1000.0)
    return best


def run_final_tightening_pass(
    initial_candidate: dict,
    mode_config: dict,
    *,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
    is_first_hop: bool = False,
) -> dict:
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=metrics.get("_reference_overview"),
    )
    _ensure_candidate_score(initial_candidate, mode_config, seed_candidate)
    current = initial_candidate
    best = initial_candidate
    explored: list[dict] = [initial_candidate]
    stop_reason = "no_more_candidates"
    for iteration in range(AUTO_DESIGN_MAX_TIGHTENING_ITERS):
        if metrics.get("cap_hit"):
            stop_reason = "evaluation_cap_hit"
            break
        neighbour_states = generate_local_improvement_candidates(
            current,
            mode_config,
            context,
            search_band=1 if is_first_hop and iteration == 0 else 0,
            is_first_hop=is_first_hop and iteration == 0,
        )
        if not neighbour_states:
            stop_reason = "no_more_candidates"
            break
        candidate_results: list[dict] = []
        for candidate_state in neighbour_states:
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="final_tightening",
                label="Final tightening",
                action_type="auto_design",
            )
            if candidate is not None:
                _ensure_candidate_score(candidate, mode_config, seed_candidate)
                if candidate_materially_worsens(candidate, current, mode_config, phase="tightening"):
                    continue
                candidate_results.append(candidate)
        candidate_results = _keep_top_candidates(candidate_results, mode_config, limit=AUTO_DESIGN_MAX_KEPT_RESULTS)
        if not candidate_results:
            stop_reason = "no_more_candidates"
            break
        explored.extend(candidate_results)
        next_best = select_best_next_hop_candidate(current, candidate_results, mode_config, phase="tightening")
        best = select_final_candidate(explored + [best], mode_config, baseline_candidate=best) or best
        metrics["tightening_iterations"] = iteration + 1
        if next_best is None:
            stop_reason = "no_meaningful_candidate"
            break
        if not is_meaningfully_better(next_best, current, mode_config):
            stop_reason = "no_meaningful_improvement"
            break
        current = next_best
        best = select_final_candidate([best, current], mode_config, baseline_candidate=best) or best
        if candidate_is_good_enough(best, mode_config, reference_candidate=seed_candidate):
            stop_reason = "reached_target_zone"
            break
    else:
        stop_reason = "iteration_cap_hit"
    metrics["tightening_stop_reason"] = stop_reason
    return best


def run_cleanup_pass(
    initial_candidate: dict,
    mode_config: dict,
    *,
    seed_candidate: dict,
    eval_cache: dict,
    metrics: dict,
) -> dict:
    context = _build_auto_design_context(
        seed_candidate["state"],
        mode_config,
        reference_overview=metrics.get("_reference_overview"),
    )
    current = initial_candidate
    best = initial_candidate
    protected_case = _critical_case_name(seed_candidate)
    protected_before = _critical_case_util(initial_candidate, protected_case)
    protected_min_util = _protected_case_min_util(protected_before, mode_config)
    metrics["protected_case"] = protected_case
    metrics["protected_util_before_cleanup"] = protected_before
    metrics["protected_min_util"] = protected_min_util
    metrics["cleanup_geometry_locked"] = bool(context.get("geometry_locked"))
    stop_reason = "no_more_safe_local_reductions"
    for iteration in range(AUTO_DESIGN_MAX_TIGHTENING_ITERS):
        candidate_states = generate_cleanup_candidates(current, mode_config, context)
        if not candidate_states:
            stop_reason = "no_more_local_cleanup_candidates"
            break
        candidate_results: list[dict] = []
        for candidate_state in candidate_states:
            candidate = _evaluate_candidate_fast(
                candidate_state,
                seed_state=seed_candidate["state"],
                context=context,
                eval_cache=eval_cache,
                metrics=metrics,
                source="cleanup_pass",
                label="Cleanup",
                action_type="auto_design",
            )
            if candidate is None:
                continue
            _ensure_candidate_score(candidate, mode_config, seed_candidate)
            shear_util_after = _critical_case_util(candidate, "shear")
            if shear_util_after is not None and shear_util_after > 1.0 + 1e-9:
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="shear_strength_exceeded"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            if not _candidate_reduces_noncritical_provision(candidate, current):
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="no_noncritical_reduction"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            if not _candidate_preserves_protected_case(candidate, protected_case, protected_min_util=protected_min_util):
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="protected_case_not_preserved"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            if candidate_materially_worsens(candidate, current, mode_config, phase="cleanup"):
                _agent_debug_log(
                    "Cleanup candidate reviewed",
                    _cleanup_candidate_debug_payload(candidate, current, protected_case, accepted=False, reason="materially_worsens_current"),
                    location="inputs_page.py:run_cleanup_pass",
                    hypothesis_id="H_CLEANUP",
                )
                continue
            candidate_results.append(candidate)
        if not candidate_results:
            stop_reason = "no_more_safe_local_reductions"
            break
        ranked = sorted(candidate_results, key=lambda item: _cleanup_candidate_rank(item, current, protected_case))
        next_best = ranked[0]
        _agent_debug_log(
            "Cleanup candidate reviewed",
            _cleanup_candidate_debug_payload(next_best, current, protected_case, accepted=True, reason="best_safe_local_cleanup"),
            location="inputs_page.py:run_cleanup_pass",
            hypothesis_id="H_CLEANUP",
        )
        best = next_best
        current = next_best
        metrics["cleanup_iterations"] = iteration + 1
    else:
        stop_reason = "cleanup_iteration_cap_hit"
    metrics["cleanup_stop_reason"] = stop_reason
    metrics["cleanup_selected_score"] = float(best.get("score", 0.0) or 0.0) if best else None
    return best


def run_full_auto_design(
    seed_candidate: dict,
    mode: str,
    force: bool = False,
    is_first_hop: bool = False,
    *,
    runtime: AutoDesignSolverRuntime | None = None,
) -> dict:
    if runtime is not None:
        _bind_auto_design_solver_runtime(runtime)

    run_started = time.perf_counter()
    mode_config = _design_mode_config(mode)
    eval_cache = CandidateEvaluationRegistry()
    ref_overview = None
    if seed_candidate:
        ref_overview = seed_candidate.get("overview")
        if ref_overview is None and seed_candidate.get("state"):
            ref_overview = _collect_design_overview(seed_candidate["state"])
    metrics = {
        "mode": mode,
        "force": bool(force),
        "optimisation_lock_geometry": _geometry_lock_enabled((seed_candidate or {}).get("state") or {}),
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "candidate_generation_ms": 0.0,
        "pruning_total_ms": 0.0,
        "solve_reo_total_ms": 0.0,
        "kept_count": 0,
        "cap_hit": False,
        "_reference_overview": ref_overview,
    }

    primary_best = run_primary_auto_design(seed_candidate, mode_config, eval_cache, metrics, is_first_hop=is_first_hop)
    metrics["phase_c"] = "final_tightening"
    tightened_best = run_final_tightening_pass(
        primary_best,
        mode_config,
        seed_candidate=seed_candidate,
        eval_cache=eval_cache,
        metrics=metrics,
        is_first_hop=is_first_hop,
    )
    metrics["phase_d"] = "cleanup_noncritical"
    cleaned_best = run_cleanup_pass(
        tightened_best,
        mode_config,
        seed_candidate=seed_candidate,
        eval_cache=eval_cache,
        metrics=metrics,
    )
    _ensure_candidate_score(primary_best, mode_config, seed_candidate)
    _ensure_candidate_score(tightened_best, mode_config, seed_candidate)
    _ensure_candidate_score(cleaned_best, mode_config, seed_candidate)
    selected = select_final_candidate([seed_candidate, primary_best, tightened_best, cleaned_best], mode_config, baseline_candidate=seed_candidate) or cleaned_best or tightened_best or primary_best or seed_candidate
    selected = _materialize_full_evaluated_candidate(selected, source="run_full_auto_design:selected_full") or selected
    _final_bending = evaluate_candidate_full(
        dict(selected["state"]),
        source="run_full_auto_design:post_select_bending_verify",
        label=str(selected.get("label") or ""),
        action_type=str(selected.get("action_type") or "auto_design"),
        updates=dict(selected.get("updates") or {}),
    )
    if _final_bending is not None:
        for key in ("reo_complexity", "guidance_preview_util", "arrangement", "actual_ast", "required_ast"):
            if key in selected:
                _final_bending[key] = selected.get(key)
        selected = _final_bending
    selected["score"] = _score_auto_design_candidate(selected, mode_config, seed_candidate)
    material_change = _candidate_materially_better_for_mode(selected, seed_candidate, mode_config)
    metrics["primary_selected_score"] = float(primary_best.get("score", 0.0) or 0.0) if primary_best else None
    metrics["tightened_selected_score"] = float(tightened_best.get("score", 0.0) or 0.0) if tightened_best else None
    metrics["cleanup_selected_score"] = float(cleaned_best.get("score", 0.0) or 0.0) if cleaned_best else None
    metrics["selected_source"] = str(selected.get("source") or "")
    metrics["selected_score"] = float(selected.get("score", 0.0) or 0.0)
    metrics["material_change"] = bool(material_change)
    metrics["selected_depth"] = float(selected.get("depth", 0.0) or 0.0)
    metrics["selected_reo_complexity"] = float(selected.get("reo_complexity", compute_reo_complexity(selected)) or 0.0)
    metrics.update(
        {
            "candidate_registry_unique_evaluations": int(len(eval_cache)),
            "candidate_registry_compute_count": int(eval_cache.compute_count),
            "candidate_registry_cache_hit_count": int(eval_cache.cache_hit_count),
            "candidate_registry_scope": "run_full_auto_design",
        }
    )
    metrics["total_runtime_ms"] = (time.perf_counter() - run_started) * 1000.0
    _agent_debug_log(
        "Auto-design final selection",
        {
            "mode": mode,
            "phase": "cleanup_noncritical",
            "stop_reason": str(metrics.get("cleanup_stop_reason") or metrics.get("tightening_stop_reason") or ""),
            "optimisation_lock_geometry": bool(metrics.get("optimisation_lock_geometry")),
            "protected_case": str(metrics.get("protected_case") or ""),
            "protected_util_before_cleanup": metrics.get("protected_util_before_cleanup"),
            "selected_score": float(selected.get("score", 0.0) or 0.0),
            "selected_util_gap": float(utilisation_gap(selected, mode_config)),
            "selected_depth": float(selected.get("depth", 0.0) or 0.0),
            "selected_reo_complexity": float(selected.get("reo_complexity", compute_reo_complexity(selected)) or 0.0),
        },
        location="inputs_page.py:run_full_auto_design:final",
        hypothesis_id="H26",
    )
    metrics_out = dict(metrics)
    metrics_out.pop("_reference_overview", None)
    return {
        "candidate": selected,
        "metrics": metrics_out,
        "material_change": material_change,
    }


def run_auto_design_solver(
    state: dict,
    results: dict,
    *,
    runtime: AutoDesignSolverRuntime | None = None,
) -> dict | None:
    """
    Internal progressive auto-design subroutine for the Recommendation Engine.
    Not a top-level entrypoint: callers should use _compute_design_guidance_items(..., request_kind="auto_design").
    """
    if runtime is not None:
        _bind_auto_design_solver_runtime(runtime)

    working = _overlay_current_normalized_shear_truth(dict(state or {}))
    current_results = dict(results or {})
    current_eval = evaluate_candidate_full(
        _overlay_current_normalized_shear_truth(_guidance_state_snapshot(working)),
        source="progressive_auto_design_seed",
        label="Progressive seed",
        action_type="auto_design",
        updates={},
    )
    if isinstance(current_eval, dict):
        current_results = _auto_design_results_from_candidate(current_eval)

    util_value = _results_worst_util(current_results)
    if util_value < 1.0:
        return {
            "title": "Design is efficient - further reductions would weaken capacity",
            "description": "The current design is inside the target band.",
            "updates": {},
            "meta": {
                "status": "no_action",
                "util": util_value if math.isfinite(util_value) else None,
            },
            "has_resolved_candidate_payload": False,
        }

    best_overall: dict | None = None
    best_overall_util = float("inf")
    progressive_steps: list[str] = []
    final_failures: list[tuple[str, float]] = []
    final_strategy = "increase_capacity"

    for pass_idx in range(1, 4):
        failures = collect_failures(current_results)
        final_failures = list(failures)
        strategy = choose_strategy(failures) if failures else "increase_capacity"
        final_strategy = strategy
        candidate_updates = _build_progressive_candidate_updates(
            working,
            current_results,
            failures,
            strategy=strategy,
        )
        if not candidate_updates:
            break

        evaluated_candidates: list[dict] = []
        for candidate_type, updates in candidate_updates:
            candidate = _evaluate_progressive_candidate_update(
                working,
                updates,
                pass_idx=pass_idx,
                candidate_type=candidate_type,
            )
            if candidate is not None:
                evaluated_candidates.append(candidate)

        if not evaluated_candidates:
            break

        # Keep top-N by utilisation (including failing util > 1 candidates).
        evaluated_candidates.sort(
            key=lambda item: (
                _candidate_worst_util_value(item),
                int(item.get("candidate_priority", 9) or 9),
            ),
        )
        top_candidates = evaluated_candidates[:3]
        selected = top_candidates[0]
        selected_util = _candidate_worst_util_value(selected)
        progressive_steps.append(
            f"Pass {pass_idx}: selected {selected.get('candidate_type')} candidate (util {selected_util:.2f}).",
        )

        if selected_util < best_overall_util:
            best_overall = dict(selected)
            best_overall_util = selected_util

        updates = dict(selected.get("updates") or {})
        if not updates:
            break
        working.update(updates)
        current_results = _auto_design_results_from_candidate(selected)

        if selected_util < 1.0:
            break

    if best_overall is None:
        fallback_candidate, failures, strategy = run_auto_design_step(working, current_results)
        final_failures = failures
        final_strategy = strategy
        if not fallback_candidate:
            return {
                "title": "Design is efficient - further reductions would weaken capacity",
                "description": "The current design is inside the target band.",
                "updates": {},
                "meta": {
                    "status": "no_action",
                    "util": util_value if math.isfinite(util_value) else None,
                },
                "has_resolved_candidate_payload": False,
            }
        best_overall = _evaluate_progressive_candidate_update(
            working,
            dict(fallback_candidate),
            pass_idx=0,
            candidate_type="fallback",
        )
        if best_overall is None:
            best_overall = {
                "label": "Fallback auto-design recommendation",
                "action_type": "auto_design",
                "updates": dict(fallback_candidate),
                "candidate_type": "fallback",
                "worst_util": util_value,
            }

    updates = dict(best_overall.get("updates") or {})
    failure_labels = ", ".join(name for name, _ in final_failures) or "none"
    resulting_util = _candidate_worst_util_value(best_overall)
    recommendation_id = (
        "auto_design_solver_progressive",
        final_strategy,
        tuple(sorted((str(k), str(v)) for k, v in updates.items())),
    )
    resolved_candidate = {
        "label": str(best_overall.get("label") or "Progressive auto-design recommendation"),
        "action_type": "auto_design",
        "updates": dict(updates),
        "candidate_post_util": None if not math.isfinite(resulting_util) else resulting_util,
        "candidate_reaches_target_band": bool(math.isfinite(resulting_util) and resulting_util <= TARGET_UTIL + 0.05),
        "candidate_type": str(best_overall.get("candidate_type") or "compound"),
    }
    return {
        "title": "Auto Design Solution",
        "description": (
            f"Strategy: {final_strategy}. Failing checks: {failure_labels}. "
            f"Best progressive util: {resulting_util:.2f}."
        ),
        "updates": dict(updates),
        "source": "auto_design_solver",
        "recommendation_id": recommendation_id,
        "resolved_candidate": resolved_candidate,
        "has_resolved_candidate_payload": bool(updates),
        "resolved_candidate_updates": dict(updates),
        "resolved_candidate_label": resolved_candidate["label"],
        "resolved_candidate_action_type": "auto_design",
        "resolved_candidate_post_util": resolved_candidate["candidate_post_util"],
        "resolved_candidate_reaches_target_band": resolved_candidate["candidate_reaches_target_band"],
        "meta": {
            "status": "ready",
            "util": None if not math.isfinite(resulting_util) else resulting_util,
            "passes_used": len(progressive_steps),
            "steps": progressive_steps,
        },
    }
