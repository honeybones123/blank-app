"""Primary optimisation candidate selection coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_PRIMARY_OPTIMISATION_SELECTOR_DEPENDENCIES: tuple[str, ...] = (
    "TARGET_BAND_EPS",
    "_build_candidate_search_evidence",
    "_build_design_actions_context",
    "_collect_design_overview",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_direct_target_band_guidance_item",
    "_distance_to_target_band",
    "_guidance_action_updates",
    "_is_in_target_zone_with_eps",
    "_optimisation_candidate_family",
    "_resolved_efficiency_target_band",
    "_state_with_overrides",
    "_updates_match_state",
)


def bind_primary_optimisation_selector_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRIMARY_OPTIMISATION_SELECTOR_DEPENDENCIES
            if name in namespace
        }
    )


def _select_primary_optimisation_candidate(
    *,
    state: dict,
    overview: dict | None,
    mode_config: dict | None,
    governing_action: str,
    candidates: list[dict],
    overdesign_stepwise_band_fallback: bool = False,
) -> dict:
    selector_debug = {
        "optimisation_selector_governing_action": str(governing_action or "other"),
        "optimisation_selector_family_bias_applied": False,
        "optimisation_selector_candidate_counts_by_family": {},
        "optimisation_selector_winning_family": None,
        "optimisation_selector_used_geometry_fallback": False,
        "optimisation_selector_fallback_reason": None,
        "optimisation_selector_candidate_reaches_target_band": False,
        "optimisation_selector_candidate_all_key_pass": False,
        "primary_optimisation_selection_owner": "legacy_fallback",
        "overdesign_no_band_reacher_but_compliant_candidates_exist": False,
        "overdesign_stepwise_fallback_used": False,
        "overdesign_stepwise_fallback_family": None,
        "overdesign_stepwise_fallback_reason": None,
        "overdesign_stepwise_selected_post_util": None,
        "candidate_search_evidence": {},
    }
    if not candidates:
        selector_debug["optimisation_selector_fallback_reason"] = "no_candidates"
        return {
            "selected_candidate": None,
            "selected_family": None,
            "fallback_reason": "no_candidates",
            "selector_debug": selector_debug,
        }

    family_order = []
    gov = str(governing_action or "").strip().lower()
    if gov in {"bending", "shear"}:
        counterpart = "shear" if gov == "bending" else "bending"
        family_order = [gov, counterpart, "compound", "geometry", "other"]
        selector_debug["optimisation_selector_family_bias_applied"] = True
    else:
        family_order = ["bending", "shear", "compound", "geometry", "other"]
        selector_debug["optimisation_selector_fallback_reason"] = "non_directional_governing_action"

    mode_cfg = mode_config if isinstance(mode_config, dict) else _design_mode_config(_design_optimisation_goal(state))
    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_cfg, goal=_design_optimisation_goal(state))
    evaluated: list[dict] = []
    counts_by_family: dict[str, int] = {}
    for item in candidates:
        family = _optimisation_candidate_family(item, state)
        counts_by_family[family] = int(counts_by_family.get(family, 0)) + 1
        payload = dict(item.get("action_payload") or {})
        action_type = str(item.get("action_type") or "")
        updates = _guidance_action_updates(action_type, payload, state=state) if action_type else {}
        trial_overview = None
        if updates and not _updates_match_state(state, updates):
            try:
                trial_context = _build_design_actions_context(_state_with_overrides(state, **updates))
                trial_state = dict(trial_context.get("state") or {})
                trial_overview = _collect_design_overview(trial_state, context=trial_context)
            except Exception:
                trial_overview = None
        resolved_overview = trial_overview if isinstance(trial_overview, dict) else dict(overview or {})
        candidate_all_key_pass = bool(resolved_overview.get("all_key_pass"))
        candidate_reaches_target_band = _is_in_target_zone_with_eps(resolved_overview, mode_cfg, eps=TARGET_BAND_EPS)
        try:
            trial_wu = float((resolved_overview or {}).get("worst_util") or 0.0)
        except (TypeError, ValueError):
            trial_wu = float("inf")
        cand_dist = _distance_to_target_band(trial_wu, t_lo, t_hi)
        evaluated.append(
            {
                "item": item,
                "family": family,
                "updates": dict(updates or {}),
                "label": str(item.get("title_main") or item.get("primary_action") or family),
                "all_key_pass": candidate_all_key_pass,
                "is_compliant": candidate_all_key_pass,
                "reaches_target_band": bool(candidate_reaches_target_band),
                "candidate_reaches_target_band": bool(candidate_reaches_target_band),
                "trial_worst_util": trial_wu,
                "candidate_post_util": trial_wu,
                "overview": dict(resolved_overview or {}),
                "candidate_distance_to_target_band": float(cand_dist),
                "source_priority": float(item.get("priority") or 0.0),
            }
        )

    selector_debug["optimisation_selector_candidate_counts_by_family"] = counts_by_family
    viable = [row for row in evaluated if bool(row.get("all_key_pass"))]
    any_band_reacher_viable = bool(any(bool(row.get("reaches_target_band")) for row in viable))
    selector_debug["overdesign_no_band_reacher_but_compliant_candidates_exist"] = bool(
        overdesign_stepwise_band_fallback and bool(viable) and not any_band_reacher_viable
    )

    selected = None
    selected_family = None
    fallback_reason = None
    if any_band_reacher_viable:
        selected = min(
            [row for row in viable if bool(row.get("reaches_target_band"))],
            key=lambda r: (
                family_order.index(str(r.get("family") or "other"))
                if str(r.get("family") or "other") in family_order
                else len(family_order),
                -float(r.get("source_priority") or 0.0),
                float(r.get("candidate_distance_to_target_band") or 0.0),
            ),
        )
        selected_family = str(selected.get("family") or "other")
    for fam in family_order:
        if selected is not None:
            break
        fam_rows = [row for row in viable if str(row.get("family") or "") == fam]
        if fam_rows:
            if overdesign_stepwise_band_fallback:
                selected = min(
                    fam_rows,
                    key=lambda r: (
                        float(r.get("candidate_distance_to_target_band") or float("inf")),
                        -float(r.get("source_priority") or 0.0),
                    ),
                )
                selector_debug["overdesign_stepwise_fallback_used"] = True
                selector_debug["overdesign_stepwise_fallback_family"] = fam
                selector_debug["overdesign_stepwise_fallback_reason"] = (
                    "inefficient_all_pass_no_one_hop_band_reacher_best_compliant_by_distance"
                )
                selector_debug["overdesign_stepwise_selected_post_util"] = selected.get("trial_worst_util")
            else:
                selected = fam_rows[0]
            selected_family = fam
            if fam == "geometry":
                fallback_reason = "geometry_fallback_no_viable_governing_family"
            break

    if selected is None and evaluated:
        fallback_reason = fallback_reason or "no_viable_pass_candidate_family_bias_fallback"
        selected = evaluated[0]
        selected_family = str(selected.get("family") or "other")

    selector_debug["optimisation_selector_winning_family"] = selected_family
    selector_debug["optimisation_selector_used_geometry_fallback"] = bool(selected_family == "geometry")
    selector_debug["optimisation_selector_fallback_reason"] = fallback_reason
    selector_debug["optimisation_selector_candidate_reaches_target_band"] = bool(
        selected.get("reaches_target_band") if isinstance(selected, dict) else False
    )
    selector_debug["optimisation_selector_candidate_all_key_pass"] = bool(
        selected.get("all_key_pass") if isinstance(selected, dict) else False
    )
    selector_debug["primary_optimisation_selection_owner"] = "shared_selector"
    if (
        isinstance(selected, dict)
        and not bool(selected.get("reaches_target_band"))
        and bool((overview or {}).get("all_key_pass"))
    ):
        direct_item = _direct_target_band_guidance_item(
            state,
            overview,
            mode_cfg,
            strengthening=False,
            debug_sink=selector_debug,
        )
        if isinstance(direct_item, dict):
            direct_evidence = dict(direct_item.get("candidate_search_evidence") or {})
            direct_target_count = int(direct_evidence.get("target_band_candidate_count") or 0)
            if direct_target_count > 0 or direct_evidence.get("search_scope") == "design_guide_direct_target_band_search":
                selector_debug["primary_optimisation_selection_owner"] = "direct_target_band_search"
                selector_debug["optimisation_selector_candidate_reaches_target_band"] = bool(direct_target_count > 0)
                selector_debug["candidate_search_evidence"] = dict(direct_evidence)
                return {
                    "selected_candidate": direct_item,
                    "selected_family": _optimisation_candidate_family(direct_item, state),
                    "fallback_reason": None,
                    "selector_debug": selector_debug,
                }
    evidence = _build_candidate_search_evidence(
        selected_candidate=selected,
        all_candidates=evaluated,
        target_low=float(t_lo),
        target_high=float(t_hi),
        exhaustive=True,
        search_scope="design_guide_efficiency_geometry_bottom_shear_compound",
        selected_title=(
            (selected.get("item") or {}).get("title_main")
            if isinstance(selected, dict) and isinstance(selected.get("item"), dict)
            else None
        ),
    )
    selector_debug["candidate_search_evidence"] = dict(evidence)
    if isinstance(selected, dict) and isinstance(selected.get("item"), dict):
        selected["item"]["candidate_search_evidence"] = dict(evidence)
        selected["item"]["candidate_id"] = evidence.get("selected_candidate_id")
        selected["item"]["source_candidate_id"] = evidence.get("selected_candidate_id")
        selected_payload = dict(selected["item"].get("action_payload") or {})
        selected_payload["candidate_search_evidence"] = dict(evidence)
        selected_payload["source_candidate_id"] = evidence.get("selected_candidate_id")
        selected["item"]["action_payload"] = selected_payload

    return {
        "selected_candidate": selected.get("item") if isinstance(selected, dict) else None,
        "selected_family": selected_family,
        "fallback_reason": fallback_reason,
        "selector_debug": selector_debug,
    }


__all__ = [
    "bind_primary_optimisation_selector_dependencies",
    "_select_primary_optimisation_candidate",
]
