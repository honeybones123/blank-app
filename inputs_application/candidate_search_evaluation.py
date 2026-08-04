"""Candidate-search evaluation coordination over explicit runtime ports."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable


@dataclass(frozen=True)
class CandidateSearchEvaluationRuntime:
    evaluate_fast: Callable[[dict, dict], dict | None]
    candidate_key: Callable[[dict], Any]
    get_global_cache: Callable[[], dict]
    global_cache_enabled: bool
    max_total_unique_evals: int
    compute_reo_complexity: Callable[[dict], float]
    state_to_shared_updates: Callable[[dict, dict], dict]
    design_width: Callable[[dict], float]
    float_from_state: Callable[[dict, str, float], float]
    effective_bottom: Callable[[dict, dict | None], dict]


def evaluate_search_candidate(
    candidate_state: dict,
    *,
    seed_state: dict,
    context: dict,
    eval_cache: dict,
    metrics: dict,
    source: str,
    runtime: CandidateSearchEvaluationRuntime,
    label: str | None = None,
    action_type: str | None = None,
) -> dict | None:
    metrics["generated_count"] = int(metrics.get("generated_count", 0)) + 1
    key = runtime.candidate_key(candidate_state)
    global_cache = runtime.get_global_cache()
    use_global_cache = bool(runtime.global_cache_enabled) and isinstance(
        global_cache,
        dict,
    )
    context.setdefault("seen_candidate_keys", set()).add(key)
    cache_has_key = key in eval_cache
    cached = eval_cache.get(key)
    if not cache_has_key:
        global_cached = global_cache.get(key) if use_global_cache else None
        if use_global_cache and isinstance(global_cached, dict):
            cached = dict(global_cached)
            eval_cache[key] = cached
            metrics["cache_hits"] = int(metrics.get("cache_hits", 0)) + 1
            metrics["global_cache_hits"] = int(metrics.get("global_cache_hits", 0)) + 1
        else:
            if int(metrics.get("unique_eval_count", 0) or 0) >= int(
                runtime.max_total_unique_evals
            ):
                metrics["cap_hit"] = True
                return None
            started_at = perf_counter()
            metrics["unique_eval_count"] = int(metrics.get("unique_eval_count", 0)) + 1
            fast_context = dict(context)
            reference = metrics.get("_reference_overview")
            if reference is not None:
                fast_context["reference_overview"] = reference
            cached = runtime.evaluate_fast(candidate_state, fast_context)
            metrics["fast_eval_total_ms"] = float(
                metrics.get("fast_eval_total_ms", 0.0) or 0.0
            ) + ((perf_counter() - started_at) * 1000.0)
            if cached is None:
                eval_cache[key] = None
                return None
            cached = dict(cached)
            cached["reo_complexity"] = runtime.compute_reo_complexity(cached)
            eval_cache[key] = cached
            if use_global_cache:
                global_cache[key] = dict(cached)
    else:
        metrics["cache_hits"] = int(metrics.get("cache_hits", 0)) + 1
        if cached is None:
            return None
    candidate = dict(cached)
    candidate["source"] = source
    candidate["label"] = label or candidate.get("label") or source.replace(
        "_",
        " ",
    ).title()
    candidate["action_type"] = action_type
    candidate["state"] = dict(candidate_state)
    candidate["updates"] = runtime.state_to_shared_updates(seed_state, candidate_state)
    candidate["_seed_width"] = float(runtime.design_width(seed_state) or 0.0)
    candidate["_seed_depth"] = float(
        runtime.float_from_state(seed_state, "D", 0.0) or 0.0
    )
    candidate["_seed_ast_bot"] = float(
        (runtime.effective_bottom(seed_state, None) or {}).get("Ast_bot", 0.0) or 0.0
    )
    candidate["reo_complexity"] = float(
        candidate.get(
            "reo_complexity",
            runtime.compute_reo_complexity(candidate),
        )
        or 0.0
    )
    return candidate


__all__ = ["CandidateSearchEvaluationRuntime", "evaluate_search_candidate"]
