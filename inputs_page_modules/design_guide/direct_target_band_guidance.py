"""Direct target-band guidance coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_DIRECT_TARGET_BAND_GUIDANCE_DEPENDENCIES: tuple[str, ...] = (
    "_COMPOUND_BOTTOM_UPDATE_KEYS",
    "_COMPOUND_GEOMETRY_UPDATE_KEYS",
    "_COMPOUND_SHEAR_UPDATE_KEYS",
    "_annotate_candidate_target_band_metrics",
    "_bending_demands_negligible",
    "_bottom_arrangement_to_shared_updates",
    "_bottom_bar_count_from_state",
    "_bottom_row_count_from_state",
    "_build_candidate_search_evidence",
    "_build_design_actions_context_isolated",
    "_candidate_action_type_for_updates",
    "_candidate_bottom_updates",
    "_candidate_is_materially_actionable",
    "_compound_guidance_title_reasoning_why",
    "_compound_subfamilies_from_updates",
    "_design_optimisation_goal",
    "_design_width_value",
    "_direct_candidate_final_cleanup_key",
    "_distance_to_target_band",
    "_effective_bottom_design_state",
    "_enumerate_bottom_reo_design_trials",
    "_evaluate_auto_design_candidate",
    "_evaluate_updates",
    "_family_tag_from_compound_updates",
    "_float_from_state",
    "_generate_escalated_shear_states",
    "_generate_local_bottom_arrangements",
    "_geometry_state_with_updates",
    "_guidance_change_lines_for_updates",
    "_guidance_item_from_resolved_candidate",
    "_guidance_state_snapshot",
    "_local_cleanup_candidate_affects_family",
    "_local_cleanup_material_proxy",
    "_one_click_diff_accumulated_updates",
    "_post_click_accepted_green_audit",
    "_resolve_design_actions_from_state",
    "_resolve_geometry_width_context",
    "_resolved_efficiency_target_band",
    "_shear_cleanup_materially_reduces_reinforcement",
    "_shear_demands_negligible",
    "_state_update_reduces_bottom_reinforcement",
    "_state_update_reduces_section_size",
    "_updates_match_state",
    "generate_less_shear_reo_variants",
    "identify_materially_overprovided_non_governing_families",
    "math",
    "os",
)


def bind_direct_target_band_guidance_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _DIRECT_TARGET_BAND_GUIDANCE_DEPENDENCIES
            if name in namespace
        }
    )


def _direct_target_band_guidance_item(
    state: dict,
    overview: dict | None,
    mode_config: dict,
    *,
    strengthening: bool,
    debug_sink: dict | None = None,
) -> dict | None:
    """Search a direct one-click update before accepting stepwise target-band movement."""
    base = _guidance_state_snapshot(dict(state or {}))
    if not base:
        return None
    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal(base))
    width_key, _, base_width = _resolve_geometry_width_context(base)
    base_width = float(base_width or 0.0)
    base_depth = float(_float_from_state(base, "D", 0.0) or 0.0)
    if base_width <= 0.0 or base_depth <= 0.0:
        return None

    if strengthening:
        width_values = [base_width + step for step in (0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0, 225.0, 250.0, 275.0, 300.0)]
        depth_values = [base_depth + step for step in (0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0, 225.0, 250.0, 275.0, 300.0)]
    else:
        width_values = [base_width - step for step in (0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0)]
        depth_values = [base_depth - step for step in (0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0)]
    width_values = sorted({float(v) for v in width_values if float(v) >= 250.0})
    depth_values = sorted({float(v) for v in depth_values if float(v) >= 300.0})
    if strengthening:
        width_values = sorted(width_values)
        depth_values = sorted(depth_values)
    else:
        width_values = sorted(width_values, reverse=True)
        depth_values = sorted(depth_values, reverse=True)

    candidates: list[dict] = []
    seen_updates: set[tuple] = set()
    try:
        max_evals = int(os.environ.get("DESIGN_GUIDE_DIRECT_TARGET_BAND_MAX_EVALS", "600") or 600)
    except (TypeError, ValueError):
        max_evals = 600
    max_evals = max(250, min(6000, max_evals))
    material_family_set: set[str] = set()
    if not strengthening:
        try:
            _, material_families, _ = identify_materially_overprovided_non_governing_families(dict(overview or {}))
            material_family_set = {str(family or "").strip().lower() for family in list(material_families or [])}
        except Exception:
            material_family_set = set()

    def _candidate_action_type_for_updates(updates: dict) -> str:
        keys = set(updates.keys())
        has_geom = bool(keys & _COMPOUND_GEOMETRY_UPDATE_KEYS)
        has_bottom = bool(keys & _COMPOUND_BOTTOM_UPDATE_KEYS)
        has_shear = bool(keys & _COMPOUND_SHEAR_UPDATE_KEYS)
        if sum(1 for flag in (has_geom, has_bottom, has_shear) if flag) >= 2:
            return "apply_resolved_candidate"
        if has_shear:
            return "apply_shear_recommendation"
        if has_bottom:
            return "apply_bottom_recommendation"
        if has_geom:
            return "apply_geometry_recommendation" if strengthening else "tighten_geometry"
        return "apply_resolved_candidate"

    def _evaluate_updates(updates: dict, label: str) -> None:
        if len(candidates) >= max_evals:
            return
        u = dict(updates or {})
        if not u or _updates_match_state(base, u):
            return
        if not _candidate_is_materially_actionable(base, u):
            return
        if not strengthening:
            trial_state_for_materiality = dict(base)
            trial_state_for_materiality.update(u)
            if material_family_set and not any(
                _local_cleanup_candidate_affects_family(family, u)
                for family in material_family_set
            ):
                return
            before_proxy = _local_cleanup_material_proxy(base)
            after_proxy = _local_cleanup_material_proxy(trial_state_for_materiality)
            if after_proxy >= before_proxy - 1e-6:
                return
            if _state_update_reduces_section_size(base, trial_state_for_materiality) is False:
                try:
                    w0 = float(_design_width_value(base) or 0.0)
                    w1 = float(_design_width_value(trial_state_for_materiality) or w0)
                    d0 = float(_float_from_state(base, "D", 0.0) or 0.0)
                    d1 = float(_float_from_state(trial_state_for_materiality, "D", d0) or d0)
                    if w1 > w0 + 1e-9 or d1 > d0 + 1e-9:
                        return
                except Exception:
                    pass
            if not (
                _state_update_reduces_section_size(base, trial_state_for_materiality)
                or _state_update_reduces_bottom_reinforcement(base, trial_state_for_materiality)
                or _shear_cleanup_materially_reduces_reinforcement(base, trial_state_for_materiality)
            ):
                return
        sig = tuple(sorted((str(k), str(v)) for k, v in u.items()))
        if sig in seen_updates:
            return
        seen_updates.add(sig)
        action_type = _candidate_action_type_for_updates(u)
        try:
            cand = _evaluate_auto_design_candidate(
                base,
                updates=u,
                source="design_guide_direct_target_band_search",
                label=label,
                action_type=action_type,
            )
        except Exception:
            cand = None
        if not isinstance(cand, dict):
            return
        _annotate_candidate_target_band_metrics(cand, mode_config)
        # Direct Design Guide evidence must use the same governing preview
        # utilisation the visible summary will publish after the click.
        try:
            preview_worst = float(((cand.get("overview") or {}).get("worst_util")))
        except (TypeError, ValueError):
            preview_worst = None
        if preview_worst is not None and math.isfinite(preview_worst):
            cand["candidate_post_util"] = preview_worst
            cand["worst_util"] = preview_worst
            cand["candidate_distance_to_target_band"] = _distance_to_target_band(
                preview_worst,
                float(t_lo),
                float(t_hi),
            )
            cand["candidate_reaches_target_band"] = bool(float(t_lo) <= preview_worst <= float(t_hi))
        cand["updates"] = dict(u)
        cand["action_type"] = "apply_resolved_candidate"
        trial_state_for_final_audit = dict(base)
        trial_state_for_final_audit.update(u)
        final_acceptance_audit = _post_click_accepted_green_audit(
            dict(cand.get("overview") or {}),
            blocker_source=dict(cand),
            state=trial_state_for_final_audit,
        )
        cand["final_acceptance_audit"] = dict(final_acceptance_audit)
        cand["final_accepted_green_valid"] = bool(
            final_acceptance_audit.get("post_click_accepted_green_valid")
        )
        cand["final_unresolved_low_util_families"] = list(
            final_acceptance_audit.get("post_click_unresolved_low_util_families") or []
        )
        cand["final_families_below_threshold"] = list(
            final_acceptance_audit.get("post_click_families_below_final_threshold") or []
        )
        if not strengthening:
            trial_state = dict(base)
            trial_state.update(u)
            before_proxy = _local_cleanup_material_proxy(base)
            after_proxy = _local_cleanup_material_proxy(trial_state)
            cand["candidate_complexity_score"] = len(u)
            cand["material_proxy_before"] = before_proxy
            cand["material_proxy_after"] = after_proxy
            cand["material_proxy_delta"] = after_proxy - before_proxy
            cand["net_efficiency_delta"] = before_proxy - after_proxy
            cand["is_executable"] = True
            cand["advisory_only"] = False
            if material_family_set:
                affected = [
                    family for family in sorted(material_family_set)
                    if _local_cleanup_candidate_affects_family(family, u)
                ]
                cand["affected_family"] = affected[0] if len(affected) == 1 else "combined"
        cand["guidance_change_lines"] = _guidance_change_lines_for_updates(base, u)
        subfamilies = _compound_subfamilies_from_updates(u)
        cand["subfamilies"] = list(subfamilies)
        cand["recommendation_family_tag"] = _family_tag_from_compound_updates(u, base)
        title, _, _ = _compound_guidance_title_reasoning_why(
            base,
            u,
            subfamilies,
            strengthening=bool(strengthening),
        )
        cand["label"] = str(title or label or "Direct target-band candidate")
        candidates.append(cand)

    shear_options: list[dict] = [{}]
    try:
        if strengthening:
            for _, shear_state in list(_generate_escalated_shear_states(base, severity_band="severe") or [])[:18]:
                su = _one_click_diff_accumulated_updates(base, shear_state)
                if su:
                    shear_options.append(dict(su))
        else:
            seed_for_shear = _evaluate_auto_design_candidate(base, source="direct_target_band_shear_seed")
            if isinstance(seed_for_shear, dict):
                for shear_state in list(generate_less_shear_reo_variants(seed_for_shear, mode_config) or [])[:12]:
                    su = _one_click_diff_accumulated_updates(base, shear_state)
                    if su:
                        shear_options.append(dict(su))
    except Exception:
        shear_options = [{}]
    dedup_shear: dict[tuple, dict] = {}
    for option in shear_options:
        sig = tuple(sorted((str(k), str(v)) for k, v in dict(option or {}).items()))
        dedup_shear[sig] = dict(option or {})
    shear_options = list(dedup_shear.values())

    keep_bottom_updates = _candidate_bottom_updates(base)
    for width in width_values:
        for depth in depth_values:
            geom_state = _geometry_state_with_updates(base, width=width, depth=depth)
            geom_updates: dict[str, object] = {}
            gw = float(_design_width_value(geom_state) or width)
            gd = float(_float_from_state(geom_state, "D", depth) or depth)
            if abs(gw - base_width) > 1e-9:
                geom_updates[width_key] = gw
                if width_key != "b":
                    geom_updates["b"] = gw
            if abs(gd - base_depth) > 1e-9:
                geom_updates["D"] = gd
            for shear_updates in shear_options[:8]:
                merged_geom = dict(geom_updates)
                merged_geom.update(dict(shear_updates or {}))
                _evaluate_updates(merged_geom, "Direct geometry target-band search")

            trial_bottoms: list[dict] = []
            if strengthening:
                try:
                    trial_bottoms = list(_enumerate_bottom_reo_design_trials(geom_state, mode_config=mode_config) or [])
                except Exception:
                    trial_bottoms = []
            else:
                current_eval = {
                    "state": geom_state,
                    "Ast_bot": float((_effective_bottom_design_state(geom_state) or {}).get("Ast_bot", 0.0) or 0.0),
                    "row_count": _bottom_row_count_from_state(geom_state),
                    "bar_count": _bottom_bar_count_from_state(geom_state, _effective_bottom_design_state(geom_state)),
                }
                try:
                    ctx = _build_design_actions_context_isolated(geom_state)
                    trial_bottoms = [
                        {"updates": _bottom_arrangement_to_shared_updates(arr), "label": "Direct bottom target-band search"}
                        for arr in _generate_local_bottom_arrangements(geom_state, mode_config, band=1, context=ctx, limit=18)
                    ]
                except Exception:
                    trial_bottoms = []
            if keep_bottom_updates:
                trial_bottoms.insert(0, {"updates": keep_bottom_updates, "label": "Keep current bottom reinforcement"})
            for trial in trial_bottoms[:24]:
                merged = dict(geom_updates)
                merged.update(dict(trial.get("updates") or {}))
                for shear_updates in shear_options[:8]:
                    merged_with_shear = dict(merged)
                    merged_with_shear.update(dict(shear_updates or {}))
                    _evaluate_updates(merged_with_shear, str(trial.get("label") or "Direct target-band search"))

    if not candidates:
        if isinstance(debug_sink, dict):
            debug_sink["direct_target_band_search_used"] = True
            debug_sink["direct_target_band_search_candidate_count"] = 0
            debug_sink["local_cleanup_candidate_search_evidence"] = _build_candidate_search_evidence(
                selected_candidate=None,
                all_candidates=[],
                target_low=float(t_lo),
                target_high=float(t_hi),
                exhaustive=True,
                search_scope="design_guide_direct_target_band_search",
                selected_title=None,
            )
        return None
    safe = [c for c in candidates if bool(c.get("is_compliant")) and bool((c.get("overview") or {}).get("all_key_pass"))]
    if not safe:
        evidence = _build_candidate_search_evidence(
            selected_candidate=None,
            all_candidates=candidates,
            target_low=float(t_lo),
            target_high=float(t_hi),
            exhaustive=True,
            search_scope="design_guide_direct_target_band_search",
            selected_title=None,
        )
        if isinstance(debug_sink, dict):
            debug_sink["direct_target_band_search_used"] = True
            debug_sink["direct_target_band_search_candidate_count"] = len(candidates)
            debug_sink["candidate_search_evidence"] = dict(evidence)
            debug_sink["local_cleanup_candidate_search_evidence"] = dict(evidence)
        return None
    target = [
        c for c in safe
        if c.get("candidate_post_util") is not None
        and float(t_lo) <= float(c.get("candidate_post_util")) <= float(t_hi)
    ]
    current_material_family_set = set(material_family_set)

    def _direct_candidate_final_cleanup_key(c: dict) -> tuple:
        updates = dict(c.get("updates") or {})
        overview_after = dict(c.get("overview") or {})
        final_audit = dict(c.get("final_acceptance_audit") or {})
        final_valid = bool(
            c.get("final_accepted_green_valid")
            or final_audit.get("post_click_accepted_green_valid")
        )
        unresolved_low = list(
            c.get("final_unresolved_low_util_families")
            or final_audit.get("post_click_unresolved_low_util_families")
            or []
        )
        below_threshold = list(
            c.get("final_families_below_threshold")
            or final_audit.get("post_click_families_below_final_threshold")
            or []
        )
        if overview_after:
            _, remaining_families, _ = identify_materially_overprovided_non_governing_families(overview_after)
            remaining_count = len(remaining_families)
        else:
            remaining_count = 99
        affected_current = {
            family
            for family in current_material_family_set
            if _local_cleanup_candidate_affects_family(family, updates)
        }
        missing_current_count = len(current_material_family_set - affected_current) if current_material_family_set else 0
        try:
            material_delta = float(c.get("material_proxy_delta") or 0.0)
        except Exception:
            material_delta = 0.0
        return (
            0 if final_valid else 1,
            len(unresolved_low),
            len(below_threshold),
            remaining_count,
            missing_current_count,
            len(dict(c.get("updates") or {})),
            material_delta,
            str(c.get("label") or ""),
        )

    if target:
        target_mid = (float(t_lo) + float(t_hi)) / 2.0
        selected = min(
            target,
            key=lambda c: (
                _direct_candidate_final_cleanup_key(c),
                abs(float(c.get("candidate_post_util") or 0.0) - target_mid),
            ),
        )
    else:
        selected = min(
            safe,
            key=lambda c: (
                _direct_candidate_final_cleanup_key(c),
                _distance_to_target_band(float(c.get("candidate_post_util") or c.get("worst_util") or 0.0), t_lo, t_hi),
            ),
        )
    evidence = _build_candidate_search_evidence(
        selected_candidate=selected,
        all_candidates=candidates,
        target_low=float(t_lo),
        target_high=float(t_hi),
        exhaustive=True,
        search_scope="design_guide_direct_target_band_search",
        selected_title=str(selected.get("label") or ""),
    )
    selected["candidate_search_evidence"] = dict(evidence)
    selected["candidate_id"] = evidence.get("selected_candidate_id")
    selected["source_candidate_id"] = evidence.get("selected_candidate_id")
    selected["canonical_winner_label"] = str(selected.get("label") or "Direct target-band candidate")
    selected["title_locked_from_final_winner"] = True
    selected_updates_for_family = dict(selected.get("updates") or {})
    selected_update_keys = {str(key) for key in selected_updates_for_family}
    width_only_cleanup = bool(selected_update_keys) and selected_update_keys.issubset(
        {"b", "bw", "beam_width", "beam_width_mm"}
    )
    try:
        direct_design_actions = _resolve_design_actions_from_state(base)
    except Exception:
        direct_design_actions = {}
    shear_overdesign_width_cleanup = bool(
        (not strengthening)
        and width_only_cleanup
        and _bending_demands_negligible(direct_design_actions)
        and not _shear_demands_negligible(direct_design_actions)
    )
    if shear_overdesign_width_cleanup:
        selected["family"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["selected_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["published_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["cta_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["apply_payload_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["candidate_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["card_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["contract_runtime_authority"] = "run_shear_overdesign_governs_runtime"
        selected["contract_runtime_driven"] = True
        selected["recommendation_family_tag"] = "SHEAR_OVERDESIGN_GOVERNS"
        selected["subfamilies"] = ["shear"]
        evidence["family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["selected_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["published_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["cta_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["apply_payload_family_id"] = "SHEAR_OVERDESIGN_GOVERNS"
        evidence["contract_runtime_authority"] = "run_shear_overdesign_governs_runtime"
        evidence["contract_runtime_driven"] = True
        evidence["contract_width_cleanup_owned_by_shear_overdesign"] = True
    item = _guidance_item_from_resolved_candidate(
        selected,
        state=base,
        overview=dict(overview or {}),
        title=str(selected.get("label") or "Direct target-band candidate"),
        reasoning=(
            "This option searches the available geometry and reinforcement moves before "
            "accepting an outside-target step."
        ),
        status="FAIL" if bool((overview or {}).get("any_fail")) else "EFFICIENCY",
        primary_action="Apply recommendation",
    )
    item["candidate_search_evidence"] = dict(evidence)
    item["local_cleanup_candidate"] = True
    item["source"] = "generate_in_target_local_cleanup_candidates"
    _published_family_id = str(
        evidence.get("selected_family_id")
        or evidence.get("family_id")
        or evidence.get("cta_family_id")
        or ""
    ).strip()
    item["affected_family"] = _published_family_id or item.get("family") or item.get("check_key")
    payload = dict(item.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["source_candidate_id"] = evidence.get("selected_candidate_id")
    if _published_family_id:
        payload["family_id"] = _published_family_id
        payload["selected_family_id"] = _published_family_id
        payload["published_family_id"] = _published_family_id
        payload["cta_family_id"] = _published_family_id
        payload["apply_payload_family_id"] = _published_family_id
    item["action_payload"] = payload
    resolved = dict(item.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["candidate_id"] = evidence.get("selected_candidate_id")
    resolved["source_candidate_id"] = evidence.get("selected_candidate_id")
    if _published_family_id:
        resolved["family_id"] = _published_family_id
        resolved["selected_family_id"] = _published_family_id
        resolved["published_family_id"] = _published_family_id
        resolved["cta_family_id"] = _published_family_id
        resolved["apply_payload_family_id"] = _published_family_id
    item["resolved_candidate"] = resolved
    if isinstance(debug_sink, dict):
        debug_sink["direct_target_band_search_used"] = True
        debug_sink["direct_target_band_search_candidate_count"] = len(candidates)
        debug_sink["candidate_search_evidence"] = dict(evidence)
        debug_sink["local_cleanup_candidate_search_evidence"] = dict(evidence)
    return item


__all__ = [
    "bind_direct_target_band_guidance_dependencies",
    "_direct_target_band_guidance_item",
]
