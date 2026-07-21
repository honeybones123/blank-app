"""Geometry/bottom compound candidate coordination for Inputs recommendations."""

from __future__ import annotations

from typing import Any


_RECOMMENDATION_COMPOUND_CANDIDATE_DEPENDENCIES: tuple[str, ...] = (
    "_annotate_bottom_reo_candidate_deltas",
    "_arrangement_fits_state",
    "_bottom_arrangement_to_shared_updates",
    "_bottom_recommendation_compound_effective_signature",
    "_bottom_recommendation_compound_title",
    "_candidate_state_to_shared_updates",
    "_compound_merged_signature_preview",
    "_evaluate_candidate_fast",
    "_generate_local_bottom_arrangements",
    "_geometry_trial_axis_for_bottom_rec",
    "_practical_bottom_reo_label",
    "_select_top_geometry_seeds_for_compound",
    "_updates_match_state",
)


def bind_recommendation_compound_candidate_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _RECOMMENDATION_COMPOUND_CANDIDATE_DEPENDENCIES
            if name in namespace
        }
    )


def _append_geometry_bottom_compound_candidates(
    *,
    state: dict,
    seed_candidate: dict,
    candidates: list[dict],
    mode_config: dict,
    context: dict,
    eval_cache: dict,
    metrics: dict,
    compound_stats: dict,
    compound_trace_log: list[dict],
) -> None:
    """Width/depth + bottom reo compounds using layouts regenerated on geometry-adjusted states."""
    seed_state = seed_candidate["state"]
    layout_cache_cmp = context.setdefault("layout_fit_cache", {})
    width_geo_all = [
        c
        for c in candidates
        if c.get("recommendation_geometry_trial")
        and _geometry_trial_axis_for_bottom_rec(c, state) == "width"
    ]
    depth_geo_all = [
        c
        for c in candidates
        if c.get("recommendation_geometry_trial")
        and _geometry_trial_axis_for_bottom_rec(c, state) == "depth"
    ]
    compound_stats["geometry_seed_candidates_considered"] = len(width_geo_all) + len(depth_geo_all)

    seen_compound_sigs: set[tuple] = set()

    def _trace_sample(
        *,
        axis: str,
        geo_lbl: str,
        ro_lbl: str | None,
        merged_preview: dict,
        result: str,
        reason: str,
        score: float | None = None,
    ) -> None:
        if len(compound_trace_log) >= 48:
            return
        row: dict = {
            "family": "compound",
            "subfamilies": ["geometry", "bottom_reo"],
            "axis": axis,
            "width_seed_label": geo_lbl if axis == "width" else None,
            "depth_seed_label": geo_lbl if axis == "depth" else None,
            "bottom_trial_label": ro_lbl,
            "merged_signature": merged_preview,
            "result": result,
            "reason": reason,
        }
        if score is not None:
            row["score"] = score
        compound_trace_log.append(row)

    def _consume_axis(axis: str, seed_limit: int, selected_key: str, trials_key: str) -> None:
        seeds = _select_top_geometry_seeds_for_compound(candidates, state, axis, limit=seed_limit)
        compound_stats[selected_key] = len(seeds)
        if not seeds:
            _trace_sample(
                axis=axis,
                geo_lbl="",
                ro_lbl=None,
                merged_preview={},
                result="skipped",
                reason=f"no_{axis}_geometry_seeds_after_dedupe",
            )
            return
        for geo_cand in seeds:
            geo_upd = dict(geo_cand.get("updates") or {})
            geo_lbl = str(geo_cand.get("label") or "")
            base_state = dict(state)
            base_state.update(geo_upd)
            local_arrs: list[dict] = []
            seen_a: set[tuple[int, int, int]] = set()
            for band in (0, 1):
                for arrangement in _generate_local_bottom_arrangements(
                    base_state,
                    mode_config,
                    band=band,
                    context=context,
                    limit=18,
                ):
                    sig_a = (
                        int(arrangement.get("bot1_count", 0) or 0),
                        int(arrangement.get("bot2_count", 0) or 0),
                        int(arrangement.get("db_bot_1", 0) or 0),
                    )
                    if sig_a in seen_a:
                        continue
                    seen_a.add(sig_a)
                    local_arrs.append(arrangement)
                    if len(local_arrs) >= 26:
                        break
                if len(local_arrs) >= 26:
                    break

            for arrangement in local_arrs:
                b_upd = _bottom_arrangement_to_shared_updates(arrangement)
                ro_lbl = _practical_bottom_reo_label(
                    int(arrangement.get("bot1_count", 0) or 0),
                    int(arrangement.get("bot2_count", 0) or 0),
                    int(arrangement.get("db_bot_1", 0) or 0),
                )
                if _updates_match_state(base_state, b_upd):
                    compound_stats["rejected_no_layout_variation"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=_compound_merged_signature_preview(
                            seed_state,
                            dict(base_state),
                        ),
                        result="rejected",
                        reason="no_layout_variation_vs_geometry_adjusted_state",
                    )
                    continue
                compound_state = dict(base_state)
                compound_state.update(b_upd)
                merged_sig = _bottom_recommendation_compound_effective_signature(seed_state, compound_state)
                merged_preview = _compound_merged_signature_preview(seed_state, compound_state)
                if merged_sig in seen_compound_sigs:
                    compound_stats["rejected_duplicate_signature"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="duplicate_signature",
                    )
                    continue
                merged_upd_check = _candidate_state_to_shared_updates(seed_state, compound_state)
                if not merged_upd_check:
                    compound_stats["rejected_invalid_merge"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="invalid_merge_empty_updates",
                    )
                    continue
                if _updates_match_state(state, merged_upd_check):
                    compound_stats["rejected_same_as_current"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="same_as_current_live_state",
                    )
                    continue
                if not _arrangement_fits_state(compound_state, arrangement, layout_cache=layout_cache_cmp):
                    compound_stats["compound_layout_reject_count"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="layout_no_fit",
                    )
                    continue
                compound_stats[trials_key] += 1
                clabel = f"{geo_lbl} + {ro_lbl}"
                comp = _evaluate_candidate_fast(
                    compound_state,
                    seed_state=seed_state,
                    context=context,
                    eval_cache=eval_cache,
                    metrics=metrics,
                    source="bottom_recommendation_compound",
                    label=clabel,
                    action_type="apply_bottom_recommendation",
                )
                if comp is None or _updates_match_state(state, comp.get("updates") or {}):
                    compound_stats["rejected_eval_cap_or_none"] += 1
                    _trace_sample(
                        axis=axis,
                        geo_lbl=geo_lbl,
                        ro_lbl=ro_lbl,
                        merged_preview=merged_preview,
                        result="rejected",
                        reason="eval_cap_or_noop_updates",
                    )
                    continue
                if not comp.get("is_compliant"):
                    compound_stats["rejected_noncompliant"] += 1
                seen_compound_sigs.add(merged_sig)
                compound_stats["compound_candidates_generated_count"] += 1
                comp["recommendation_compound"] = True
                comp["recommendation_geometry_trial"] = True
                comp["recommendation_bottom_trial"] = True
                comp["subfamilies"] = ["geometry", "bottom_reo"]
                comp["recommendation_family_tag"] = f"compound_{axis}_bottom"
                comp["compound_geo_axis"] = axis
                comp["arrangement"] = dict(arrangement)
                comp["actual_ast"] = float(comp.get("Ast_bot", 0.0) or 0.0)
                comp["guidance_recommendation_title"] = _bottom_recommendation_compound_title(axis, geo_lbl)
                _annotate_bottom_reo_candidate_deltas(comp, seed_candidate, state)
                candidates.append(comp)
                sc = comp.get("score")
                _trace_sample(
                    axis=axis,
                    geo_lbl=geo_lbl,
                    ro_lbl=ro_lbl,
                    merged_preview=merged_preview,
                    result="accepted_pool",
                    reason="evaluated_ok",
                    score=float(sc) if sc is not None else None,
                )

    _consume_axis("width", 3, "width_seed_candidates_selected_for_compound", "bottom_layout_trials_attempted_on_width_state")
    _consume_axis("depth", 2, "depth_seed_candidates_selected_for_compound", "bottom_layout_trials_attempted_on_depth_state")


__all__ = [
    "bind_recommendation_compound_candidate_dependencies",
    "_append_geometry_bottom_compound_candidates",
]
