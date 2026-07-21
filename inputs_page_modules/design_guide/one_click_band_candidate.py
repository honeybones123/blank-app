"""One-click target-band candidate coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_ONE_CLICK_BAND_CANDIDATE_DEPENDENCIES: tuple[str, ...] = (
    "TARGET_BAND_EPS",
    "_candidate_is_materially_actionable",
    "_compute_bottom_reo_recommendation",
    "_compute_geometry_recommendation",
    "_compute_shear_recommendation",
    "_evaluate_auto_design_candidate",
    "_guidance_action_updates",
    "_guidance_change_lines_for_updates",
    "_guidance_item_from_resolved_candidate",
    "_guidance_state_snapshot",
    "_is_in_target_zone_with_eps",
    "_one_click_candidate_payload_signature",
    "_select_best_auto_design_candidate",
    "_updates_match_state",
    "evaluate_candidate_full",
)


def bind_one_click_band_candidate_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _ONE_CLICK_BAND_CANDIDATE_DEPENDENCIES
            if name in namespace
        }
    )


def _get_one_click_band_reaching_candidate(
    guidance_state: dict,
    overview: dict,
    *,
    mode_config: dict,
    primary_hint: dict | None = None,
    debug_extra: dict | None = None,
) -> dict | None:
    if isinstance(debug_extra, dict):
        debug_extra["one_click_critical_candidate_exists"] = False
        debug_extra["one_click_critical_candidate_label"] = None
        debug_extra["one_click_critical_candidate_action_type"] = None
        debug_extra["one_click_critical_candidate_post_util"] = None
        debug_extra["one_click_critical_candidate_reaches_target_band"] = False
        debug_extra["compound_shear_augmented"] = False
        debug_extra["covers_all_current_failures"] = False
        debug_extra["covered_fail_keys"] = []
        debug_extra["remaining_fail_keys"] = []
        debug_extra["one_click_critical_candidate_surfaced"] = False
        debug_extra["one_click_critical_candidate_suppressed_reason"] = "not_checked"
        debug_extra["critical_branch_used_one_click_override"] = False

    seed_candidate = evaluate_candidate_full(
        _guidance_state_snapshot(guidance_state),
        source="one_click_critical_seed",
    )
    if not seed_candidate:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "seed_eval_failed"
        return None
    overview_in_band = bool(overview.get("all_key_pass")) and _is_in_target_zone_with_eps(
        overview,
        mode_config,
        eps=TARGET_BAND_EPS,
    )
    if overview_in_band:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "already_in_target_band"
        return None

    option_specs: list[dict] = []

    def _add_option(
        *,
        updates: dict | None,
        action_type: str,
        payload: dict,
        label: str,
        source: str,
        family_tag: str | None = None,
        subfamilies: list[str] | None = None,
    ) -> None:
        u = dict(updates or {})
        if not u or _updates_match_state(guidance_state, u):
            return
        if not _candidate_is_materially_actionable(guidance_state, u):
            return
        option_specs.append(
            {
                "updates": u,
                "action_type": str(action_type),
                "payload": dict(payload),
                "label": str(label or "").strip() or "Apply one-click recommendation",
                "source": str(source),
                "family_tag": family_tag,
                "subfamilies": list(subfamilies or []),
            },
        )

    if isinstance(primary_hint, dict):
        at = str(primary_hint.get("action_type") or "")
        if at:
            hint_payload = dict(primary_hint.get("action_payload") or {})
            hint_updates = _guidance_action_updates(at, hint_payload, state=guidance_state)
            _add_option(
                updates=hint_updates,
                action_type=at,
                payload=hint_payload,
                label=str(primary_hint.get("title_main") or primary_hint.get("primary_action") or at),
                source="primary_hint",
            )

    bottom_rec = _compute_bottom_reo_recommendation(guidance_state)
    if isinstance(bottom_rec, dict):
        bu = dict(bottom_rec.get("updates") or {})
        if bu:
            is_compound = bool(bottom_rec.get("recommendation_compound"))
            rec_title = str(
                bottom_rec.get("guidance_recommendation_title")
                or bottom_rec.get("label")
                or "Apply bottom recommendation"
            )
            _add_option(
                updates=bu,
                action_type="apply_compound_guidance" if is_compound else "apply_bottom_recommendation",
                payload={
                    "updates": bu,
                    "guidance_banner_title": rec_title,
                    "label": rec_title,
                },
                label=rec_title,
                source="bottom_recommendation",
                family_tag=str(bottom_rec.get("recommendation_family_tag") or ""),
                subfamilies=list(bottom_rec.get("subfamilies") or []) if isinstance(bottom_rec.get("subfamilies"), list) else [],
            )

    geom_rec = _compute_geometry_recommendation(guidance_state)
    if isinstance(geom_rec, dict):
        gu = dict(geom_rec.get("updates") or {})
        if gu:
            g_label = str(geom_rec.get("label") or "Apply geometry recommendation")
            _add_option(
                updates=gu,
                action_type="apply_geometry_recommendation",
                payload={"updates": gu, "label": g_label},
                label=g_label,
                source="geometry_recommendation",
            )

    shear_rec = _compute_shear_recommendation(guidance_state)
    if isinstance(shear_rec, dict):
        su = dict(shear_rec.get("updates") or {})
        if su:
            s_label = str(shear_rec.get("label") or "Apply shear recommendation")
            _add_option(
                updates=su,
                action_type="apply_shear_recommendation",
                payload={"updates": su, "label": s_label},
                label=s_label,
                source="shear_recommendation",
            )

    if not option_specs:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "no_actionable_options"
        return None

    uniq: dict[tuple, dict] = {}
    for spec in option_specs:
        sig = _one_click_candidate_payload_signature(spec.get("updates") or {})
        uniq[sig] = spec
    option_specs = list(uniq.values())

    candidates: list[dict] = []
    for idx, spec in enumerate(option_specs):
        cand = _evaluate_auto_design_candidate(
            guidance_state,
            updates=dict(spec.get("updates") or {}),
            source=f"one_click_critical_option_{idx}",
            label=str(spec.get("label") or "one_click_option"),
            action_type=str(spec.get("action_type") or ""),
        )
        if not cand:
            continue
        cand["_one_click_spec"] = spec
        candidates.append(cand)
    if not candidates:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "candidate_eval_failed"
        return None

    winner = _select_best_auto_design_candidate(candidates, mode_config, seed_candidate)
    if not winner:
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "no_selector_winner"
        return None
    if not bool(winner.get("is_compliant")):
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "selector_winner_not_compliant"
        return None
    if not bool(winner.get("candidate_reaches_target_band")):
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "selector_winner_not_band_reaching"
            debug_extra["one_click_critical_candidate_post_util"] = winner.get("candidate_post_util")
            debug_extra["one_click_critical_candidate_reaches_target_band"] = False
        return None
    spec = dict(winner.get("_one_click_spec") or {})
    updates = dict(spec.get("updates") or {})
    if _updates_match_state(guidance_state, updates):
        if isinstance(debug_extra, dict):
            debug_extra["one_click_critical_candidate_suppressed_reason"] = "winner_noop_updates"
        return None

    action_type = str(spec.get("action_type") or winner.get("action_type") or "apply_compound_guidance")
    clines = _guidance_change_lines_for_updates(guidance_state, updates)
    post_util = float(winner.get("candidate_post_util", 0.0) or 0.0)
    cur_util = float(seed_candidate.get("worst_util", 0.0) or 0.0)
    resolved_candidate = dict(winner)
    spec_or_winner_label = str(spec.get("label") or winner.get("label") or "Apply one-click recommendation")
    canon_title = str(
        winner.get("canonical_winner_label") or winner.get("label") or spec_or_winner_label or "",
    ).strip() or spec_or_winner_label
    resolved_candidate["canonical_winner_label"] = canon_title
    resolved_candidate["title_locked_from_final_winner"] = True
    resolved_candidate["resolved_candidate_label_raw"] = canon_title
    resolved_candidate["label"] = canon_title
    title = canon_title
    resolved_candidate["action_type"] = action_type
    resolved_candidate["updates"] = dict(updates)
    resolved_candidate["recommendation_family_tag"] = spec.get("family_tag")
    resolved_candidate["subfamilies"] = list(spec.get("subfamilies") or [])
    resolved_candidate["candidate_reaches_target_band"] = bool(winner.get("candidate_reaches_target_band"))
    resolved_candidate["worst_util"] = winner.get("candidate_post_util")
    resolved_candidate["recommendation_change_lines"] = clines or []
    item = _guidance_item_from_resolved_candidate(
        resolved_candidate,
        state=guidance_state,
        overview=overview,
        title=title,
        reasoning=f"Why: this option reaches the target band in one move ({cur_util:.2f} → {post_util:.2f}).",
        status="FAIL",
        primary_action="Apply recommendation",
    )
    if isinstance(debug_extra, dict):
        failure_coverage = dict(item.get("failure_coverage") or {})
        debug_extra["one_click_critical_candidate_exists"] = True
        debug_extra["one_click_critical_candidate_label"] = title
        debug_extra["one_click_critical_candidate_action_type"] = "apply_resolved_candidate"
        debug_extra["one_click_critical_candidate_post_util"] = post_util
        debug_extra["one_click_critical_candidate_reaches_target_band"] = bool(winner.get("candidate_reaches_target_band"))
        debug_extra["compound_shear_augmented"] = bool(resolved_candidate.get("compound_shear_augmented"))
        debug_extra["covers_all_current_failures"] = bool(
            item.get("covers_all_current_failures")
            or failure_coverage.get("covers_all_current_failures"),
        )
        debug_extra["covered_fail_keys"] = list(
            item.get("covered_fail_keys")
            or failure_coverage.get("covered_fail_keys")
            or [],
        )
        debug_extra["remaining_fail_keys"] = list(
            item.get("remaining_fail_keys")
            or failure_coverage.get("remaining_fail_keys")
            or [],
        )
        debug_extra["one_click_critical_candidate_suppressed_reason"] = None
    return item


__all__ = [
    "bind_one_click_band_candidate_dependencies",
    "_get_one_click_band_reaching_candidate",
]
