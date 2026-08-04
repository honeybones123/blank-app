"""Top-candidate trimming coordination for the Inputs app bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Callable


@dataclass(frozen=True)
class TopCandidateKeeperRuntime:
    max_kept_results: int
    session_state: Any
    agent_debug_log: Callable[..., None]
    bottom_reo_state_label: Callable[[dict], str]
    candidate_debug_summary: Callable[[dict | None], dict | None]
    candidate_sort_key_for_mode: Callable[..., tuple]
    candidate_util_distance: Callable[..., float]
    candidate_key: Callable[[dict], tuple]
    shallower_beam_candidate_tier: Callable[[dict], tuple]
    shallower_beam_metrics: Callable[[dict, dict], dict]
    compute_reo_complexity: Callable[[dict], float]


_TOP_CANDIDATE_KEEPER_DEPENDENCIES: tuple[str, ...] = (
    "AUTO_DESIGN_MAX_KEPT_RESULTS",
    "st",
    "_agent_debug_log",
    "_bottom_reo_state_label",
    "_candidate_debug_summary",
    "_candidate_sort_key_for_mode",
    "_candidate_util_distance",
    "_make_auto_design_candidate_key",
    "_shallower_beam_candidate_tier",
    "_shallower_beam_metrics",
    "compute_reo_complexity",
)


def bind_top_candidate_keeper_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _TOP_CANDIDATE_KEEPER_DEPENDENCIES
            if name in namespace
        }
    )


def _candidate_dominates_for_mode(
    candidate_a: dict,
    candidate_b: dict,
    mode_config: dict,
    *,
    runtime: TopCandidateKeeperRuntime | None = None,
) -> bool:
    if runtime is None:
        namespace = globals()
        runtime = TopCandidateKeeperRuntime(
            max_kept_results=namespace["AUTO_DESIGN_MAX_KEPT_RESULTS"],
            session_state=namespace["st"].session_state,
            agent_debug_log=namespace["_agent_debug_log"],
            bottom_reo_state_label=namespace["_bottom_reo_state_label"],
            candidate_debug_summary=namespace["_candidate_debug_summary"],
            candidate_sort_key_for_mode=namespace[
                "_candidate_sort_key_for_mode"
            ],
            candidate_util_distance=namespace["_candidate_util_distance"],
            candidate_key=namespace["_make_auto_design_candidate_key"],
            shallower_beam_candidate_tier=namespace[
                "_shallower_beam_candidate_tier"
            ],
            shallower_beam_metrics=namespace["_shallower_beam_metrics"],
            compute_reo_complexity=namespace["compute_reo_complexity"],
        )
    _candidate_util_distance = runtime.candidate_util_distance
    _shallower_beam_metrics = runtime.shallower_beam_metrics
    compute_reo_complexity = runtime.compute_reo_complexity
    if not candidate_a or not candidate_b:
        return False
    if not bool(candidate_a.get("is_compliant")) or not bool(candidate_b.get("is_compliant")):
        return False
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    util_a = _candidate_util_distance(candidate_a, mode_config)
    util_b = _candidate_util_distance(candidate_b, mode_config)
    complexity_a = float(candidate_a.get("reo_complexity", compute_reo_complexity(candidate_a)) or 0.0)
    complexity_b = float(candidate_b.get("reo_complexity", compute_reo_complexity(candidate_b)) or 0.0)
    depth_a = float(candidate_a.get("depth", 0.0) or 0.0)
    depth_b = float(candidate_b.get("depth", 0.0) or 0.0)
    if strategy == "shallow":
        metrics_a = _shallower_beam_metrics(
            candidate_a,
            {
                "state": dict(candidate_a.get("state") or {}),
                "depth": float(candidate_a.get("_seed_depth", depth_a) or depth_a),
                "width": float(candidate_a.get("_seed_width", float(candidate_a.get("width", 0.0) or 0.0)) or float(candidate_a.get("width", 0.0) or 0.0)),
                "Ast_bot": float(candidate_a.get("_seed_ast_bot", candidate_a.get("Ast_bot", 0.0)) or candidate_a.get("Ast_bot", 0.0) or 0.0),
            },
        )
        metrics_b = _shallower_beam_metrics(
            candidate_b,
            {
                "state": dict(candidate_b.get("state") or {}),
                "depth": float(candidate_b.get("_seed_depth", depth_b) or depth_b),
                "width": float(candidate_b.get("_seed_width", float(candidate_b.get("width", 0.0) or 0.0)) or float(candidate_b.get("width", 0.0) or 0.0)),
                "Ast_bot": float(candidate_b.get("_seed_ast_bot", candidate_b.get("Ast_bot", 0.0)) or candidate_b.get("Ast_bot", 0.0) or 0.0),
            },
        )
        return (
            (0 if metrics_a.get("materially_shallower") else 1) <= (0 if metrics_b.get("materially_shallower") else 1)
            and depth_a <= depth_b
            and float(metrics_a.get("width_growth", 0.0) or 0.0) <= float(metrics_b.get("width_growth", 0.0) or 0.0)
            and float(metrics_a.get("reinforcement_growth", 0.0) or 0.0) <= float(metrics_b.get("reinforcement_growth", 0.0) or 0.0)
            and complexity_a <= complexity_b
            and util_a <= util_b
            and (
                (0 if metrics_a.get("materially_shallower") else 1) < (0 if metrics_b.get("materially_shallower") else 1)
                or depth_a < depth_b
                or float(metrics_a.get("width_growth", 0.0) or 0.0) < float(metrics_b.get("width_growth", 0.0) or 0.0)
                or float(metrics_a.get("reinforcement_growth", 0.0) or 0.0) < float(metrics_b.get("reinforcement_growth", 0.0) or 0.0)
                or complexity_a < complexity_b
                or util_a < util_b
            )
        )
    if strategy == "low_reo":
        rows_a = int(candidate_a.get("row_count", 0) or 0)
        rows_b = int(candidate_b.get("row_count", 0) or 0)
        bars_a = int(candidate_a.get("bar_count", 0) or 0)
        bars_b = int(candidate_b.get("bar_count", 0) or 0)
        return (
            complexity_a <= complexity_b
            and rows_a <= rows_b
            and bars_a <= bars_b
            and depth_a <= depth_b
            and util_a <= util_b
            and (
                complexity_a < complexity_b
                or rows_a < rows_b
                or bars_a < bars_b
                or depth_a < depth_b
                or util_a < util_b
            )
        )
    return (
        util_a <= util_b
        and depth_a <= depth_b
        and complexity_a <= complexity_b
        and (util_a < util_b or depth_a < depth_b or complexity_a < complexity_b)
    )


def _keep_top_candidates(
    candidates: list[dict],
    mode_config: dict,
    *,
    limit: int,
    runtime: TopCandidateKeeperRuntime | None = None,
) -> list[dict]:
    if runtime is None:
        namespace = globals()
        runtime = TopCandidateKeeperRuntime(
            max_kept_results=namespace["AUTO_DESIGN_MAX_KEPT_RESULTS"],
            session_state=namespace["st"].session_state,
            agent_debug_log=namespace["_agent_debug_log"],
            bottom_reo_state_label=namespace["_bottom_reo_state_label"],
            candidate_debug_summary=namespace["_candidate_debug_summary"],
            candidate_sort_key_for_mode=namespace[
                "_candidate_sort_key_for_mode"
            ],
            candidate_util_distance=namespace["_candidate_util_distance"],
            candidate_key=namespace["_make_auto_design_candidate_key"],
            shallower_beam_candidate_tier=namespace[
                "_shallower_beam_candidate_tier"
            ],
            shallower_beam_metrics=namespace["_shallower_beam_metrics"],
            compute_reo_complexity=namespace["compute_reo_complexity"],
        )
    AUTO_DESIGN_MAX_KEPT_RESULTS = runtime.max_kept_results
    st_session_state = runtime.session_state
    _agent_debug_log = runtime.agent_debug_log
    _bottom_reo_state_label = runtime.bottom_reo_state_label
    _candidate_debug_summary = runtime.candidate_debug_summary
    _candidate_sort_key_for_mode = runtime.candidate_sort_key_for_mode
    _make_auto_design_candidate_key = runtime.candidate_key
    _shallower_beam_candidate_tier = (
        runtime.shallower_beam_candidate_tier
    )
    _shallower_beam_metrics = runtime.shallower_beam_metrics
    compute_reo_complexity = runtime.compute_reo_complexity
    limit = min(max(int(limit), 1), AUTO_DESIGN_MAX_KEPT_RESULTS)
    deduped: dict[tuple, dict] = {}
    for candidate in candidates:
        if not candidate:
            continue
        candidate.setdefault("reo_complexity", compute_reo_complexity(candidate))
        key = _make_auto_design_candidate_key(candidate.get("state") or {})
        existing = deduped.get(key)
        if existing is None or _candidate_sort_key_for_mode(candidate, mode_config) < _candidate_sort_key_for_mode(existing, mode_config):
            deduped[key] = candidate
    ordered = sorted(deduped.values(), key=lambda item: _candidate_sort_key_for_mode(item, mode_config))
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    if strategy == "shallow" and bool(st_session_state.get("_dev_mode")) and ordered:
        selected_candidate = ordered[0]
        selected_tier, selected_tier_label = _shallower_beam_candidate_tier(selected_candidate)
        def _baseline_for(item: dict) -> dict:
            return {
                "state": dict(item.get("state") or {}),
                "depth": float(item.get("_seed_depth", item.get("depth", 0.0)) or 0.0),
                "width": float(item.get("_seed_width", item.get("width", 0.0)) or 0.0),
                "Ast_bot": float(item.get("_seed_ast_bot", item.get("Ast_bot", 0.0)) or 0.0),
            }
        best_local_candidate = next(
            (item for item in ordered if _shallower_beam_candidate_tier(item)[0] == 0),
            None,
        )
        best_width_candidate = next(
            (
                item for item in ordered
                if bool(item.get("is_compliant")) and _shallower_beam_candidate_tier(item)[0] == 1
            ),
            None,
        )
        best_depth_candidate = next(
            (
                item for item in ordered
                if bool(item.get("is_compliant")) and _shallower_beam_candidate_tier(item)[0] in (2, 3)
            ),
            None,
        )
        selected_metrics = _shallower_beam_metrics(selected_candidate, _baseline_for(selected_candidate))
        if selected_tier >= 2 and best_width_candidate is not None:
            _agent_debug_log(
                "Depth selected before width in shallower_beam mode — verify ranking justification",
                {
                    "selected_candidate": _candidate_debug_summary(selected_candidate),
                    "selected_tier": selected_tier_label,
                    "best_width_candidate": _candidate_debug_summary(best_width_candidate),
                    "best_width_tier": _shallower_beam_candidate_tier(best_width_candidate)[1],
                    "selected_sort_key": _candidate_sort_key_for_mode(selected_candidate, mode_config),
                    "best_width_sort_key": _candidate_sort_key_for_mode(best_width_candidate, mode_config),
                },
                location="inputs_page.py:_keep_top_candidates",
                hypothesis_id="H_SHALLOW_WIDTH_FIRST",
            )
        if not bool(selected_metrics.get("materially_shallower")) and (
            float(selected_metrics.get("width_growth", 0.0) or 0.0) >= 100.0
            or float(selected_metrics.get("reinforcement_growth", 0.0) or 0.0) >= 150.0
        ):
            _agent_debug_log(
                "Selected candidate is not materially shallower — verify shallower_beam ranking",
                {
                    "selected_candidate": _candidate_debug_summary(selected_candidate),
                    "shallowness_metrics": selected_metrics,
                },
                location="inputs_page.py:_keep_top_candidates",
                hypothesis_id="H_TRUE_SHALLOW",
            )
        def _shallow_debug_payload(item: dict | None) -> dict | None:
            if not item:
                return None
            shallow_metrics = _shallower_beam_metrics(item, _baseline_for(item))
            shear_pack = (((item.get("overview") or {}).get("packs") or {}).get("shear") or {})
            bending_pack = (((item.get("overview") or {}).get("packs") or {}).get("bending") or {})
            return {
                "label": item.get("label"),
                "b": item.get("width"),
                "D": item.get("depth"),
                "bottom_reo_label": _bottom_reo_state_label(dict(item.get("state") or {})),
                "Ast_bot": item.get("Ast_bot"),
                "phiMu": bending_pack.get("summary_phiMu_kNm"),
                "Mu_star": bending_pack.get("summary_Mu_star_kNm"),
                "bending_util": ((item.get("overview") or {}).get("utils") or {}).get("bending"),
                "phiVu": shear_pack.get("summary_governing_capacity_kN", shear_pack.get("summary_phiVu_kN")),
                "Veq": shear_pack.get("summary_governing_demand_kN", shear_pack.get("summary_Veq_kN")),
                "shear_util": ((item.get("overview") or {}).get("utils") or {}).get("shear"),
                "shallowness_score": ((item.get("_score_components") or {}).get("shallowness_score")),
                "width_growth_penalty": ((item.get("_score_components") or {}).get("width_growth_penalty")),
                "reinforcement_growth_penalty": ((item.get("_score_components") or {}).get("reinforcement_growth_penalty")),
                "total_score": item.get("score"),
                "reason": "selected" if item is selected_candidate else "comparison candidate",
                "shallowness_metrics": shallow_metrics,
            }
        _agent_debug_log(
            "Shallower beam candidate comparison",
            {
                "best_bottom_reo_local_candidate": _shallow_debug_payload(best_local_candidate),
                "best_width_reo_candidate": _shallow_debug_payload(best_width_candidate),
                "best_depth_candidate": _shallow_debug_payload(best_depth_candidate),
                "final_selected_candidate": _shallow_debug_payload(selected_candidate),
            },
            location="inputs_page.py:_keep_top_candidates",
            hypothesis_id="H_SHALLOW_COMPARE",
        )
    kept: list[dict] = []
    candidate_audit: list[dict] = []
    for candidate in ordered:
        decision = "kept"
        if any(
            _candidate_dominates_for_mode(
                existing,
                candidate,
                mode_config,
                runtime=runtime,
            )
            for existing in kept
        ):
            decision = "discarded_dominated"
            if len(candidate_audit) < 8:
                candidate_audit.append({
                    **(_candidate_debug_summary(candidate) or {}),
                    "decision": decision,
                })
            continue
        if len(kept) >= limit:
            decision = "discarded_limit"
            if len(candidate_audit) < 8:
                candidate_audit.append({
                    **(_candidate_debug_summary(candidate) or {}),
                    "decision": decision,
                })
            continue
        kept.append(candidate)
        if len(candidate_audit) < 8:
            candidate_audit.append({
                **(_candidate_debug_summary(candidate) or {}),
                "decision": decision,
            })
    if bool(st_session_state.get("_dev_mode")) and candidate_audit:
        _agent_debug_log(
            "Ranked kept auto-design candidates",
            {
                "mode": str(mode_config.get("label") or ""),
                "limit": int(limit),
                "ranked_candidates": candidate_audit,
            },
            location="inputs_page.py:_keep_top_candidates",
            hypothesis_id="H304",
        )
        if any(bool(candidate.get("_ductility_priority")) for candidate in ordered):
            _agent_debug_log(
                "Ranked ductility candidates",
                {
                    "mode": str(mode_config.get("label") or ""),
                    "top_candidates": candidate_audit,
                },
                location="inputs_page.py:_keep_top_candidates:ductility",
                hypothesis_id="H304_DUCTILITY",
            )
    return kept
