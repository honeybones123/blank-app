"""Local-cleanup primary promotion coordination for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_LOCAL_CLEANUP_PROMOTION_DEPENDENCIES: tuple[str, ...] = (
    "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
    "GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN",
    "TARGET_BAND_EPS",
    "_accepted_green_exact_blocker_is_valid",
    "_build_candidate_search_evidence",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_family_ladder_guidance_item",
    "_evaluate_local_cleanup_guidance_item",
    "_float_from_state",
    "_guidance_cleanup_candidate_id",
    "_guidance_update_signature",
    "_is_in_target_zone_with_eps",
    "_local_cleanup_candidate_affects_family",
    "_local_cleanup_debug_defaults",
    "_local_cleanup_post_apply_acceptance_matches",
    "_optimal_guidance_item",
    "_post_click_accepted_green_audit",
    "_resolve_design_actions_from_state",
    "_resolved_efficiency_target_band",
    "_shear_demands_negligible",
    "_shear_low_util_active_links_exact_blocker",
    "_shear_tightening_as_local_cleanup_item",
    "identify_materially_overprovided_non_governing_families",
)


@dataclass(frozen=True)
class LocalCleanupPromotionRuntime:
    final_accepted_min_family_util: float
    shear_demand_abs_tol_kn: float
    target_band_eps: float
    accepted_green_exact_blocker_is_valid: Callable[..., Any]
    build_candidate_search_evidence: Callable[..., Any]
    design_mode_config: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    family_ladder_guidance_item: Callable[..., Any]
    evaluate_local_cleanup_guidance_item: Callable[..., Any]
    float_from_state: Callable[..., Any]
    guidance_cleanup_candidate_id: Callable[..., Any]
    guidance_update_signature: Callable[..., Any]
    is_in_target_zone_with_eps: Callable[..., Any]
    local_cleanup_candidate_affects_family: Callable[..., Any]
    local_cleanup_debug_defaults: Callable[..., Any]
    local_cleanup_post_apply_acceptance_matches: Callable[..., Any]
    optimal_guidance_item: Callable[..., Any]
    post_click_accepted_green_audit: Callable[..., Any]
    resolve_design_actions_from_state: Callable[..., Any]
    resolved_efficiency_target_band: Callable[..., Any]
    shear_demands_negligible: Callable[..., Any]
    shear_low_util_active_links_exact_blocker: Callable[..., Any]
    shear_tightening_as_local_cleanup_item: Callable[..., Any]
    identify_materially_overprovided_families: Callable[..., Any]


def _bind_local_cleanup_promotion_runtime(
    runtime: LocalCleanupPromotionRuntime,
) -> None:
    globals().update(
        {
            "FINAL_ACCEPTED_MIN_FAMILY_UTIL": runtime.final_accepted_min_family_util,
            "GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN": runtime.shear_demand_abs_tol_kn,
            "TARGET_BAND_EPS": runtime.target_band_eps,
            "_accepted_green_exact_blocker_is_valid": runtime.accepted_green_exact_blocker_is_valid,
            "_build_candidate_search_evidence": runtime.build_candidate_search_evidence,
            "_design_mode_config": runtime.design_mode_config,
            "_design_optimisation_goal": runtime.design_optimisation_goal,
            "_family_ladder_guidance_item": runtime.family_ladder_guidance_item,
            "_evaluate_local_cleanup_guidance_item": runtime.evaluate_local_cleanup_guidance_item,
            "_float_from_state": runtime.float_from_state,
            "_guidance_cleanup_candidate_id": runtime.guidance_cleanup_candidate_id,
            "_guidance_update_signature": runtime.guidance_update_signature,
            "_is_in_target_zone_with_eps": runtime.is_in_target_zone_with_eps,
            "_local_cleanup_candidate_affects_family": runtime.local_cleanup_candidate_affects_family,
            "_local_cleanup_debug_defaults": runtime.local_cleanup_debug_defaults,
            "_local_cleanup_post_apply_acceptance_matches": runtime.local_cleanup_post_apply_acceptance_matches,
            "_optimal_guidance_item": runtime.optimal_guidance_item,
            "_post_click_accepted_green_audit": runtime.post_click_accepted_green_audit,
            "_resolve_design_actions_from_state": runtime.resolve_design_actions_from_state,
            "_resolved_efficiency_target_band": runtime.resolved_efficiency_target_band,
            "_shear_demands_negligible": runtime.shear_demands_negligible,
            "_shear_low_util_active_links_exact_blocker": runtime.shear_low_util_active_links_exact_blocker,
            "_shear_tightening_as_local_cleanup_item": runtime.shear_tightening_as_local_cleanup_item,
            "identify_materially_overprovided_non_governing_families": runtime.identify_materially_overprovided_families,
        }
    )


def bind_local_cleanup_promotion_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _LOCAL_CLEANUP_PROMOTION_DEPENDENCIES
            if name in namespace
        }
    )


def _publication_family_id_for_local_cleanup(family: Any) -> str:
    normalised = str(family or "").strip().lower()
    if normalised == "bending":
        return "BENDING_OVERDESIGN_GOVERNS"
    if normalised == "shear":
        return "SHEAR_OVERDESIGN_GOVERNS"
    if normalised == "combined":
        return "COMBINED_OVERDESIGN"
    if normalised == "geometry":
        return "GEOMETRY_DETAILING_GOVERNS"
    return str(family or "").strip()


def _stamp_local_cleanup_publication_family(item: dict, family_id: str) -> dict:
    if not family_id:
        return item
    stamped = dict(item)
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
    ):
        stamped[key] = family_id
    payload = dict(stamped.get("action_payload") or {})
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
    ):
        payload[key] = family_id
    summary = dict(payload.get("apply_payload_summary") or {})
    if summary:
        for key in (
            "family",
            "family_id",
            "selected_family_id",
            "published_family_id",
            "cta_family_id",
            "apply_payload_family_id",
        ):
            summary[key] = family_id
        payload["apply_payload_summary"] = summary
    stamped["action_payload"] = payload
    resolved = dict(stamped.get("resolved_candidate") or {})
    for key in (
        "family",
        "family_id",
        "selected_family_id",
        "published_family_id",
        "cta_family_id",
        "apply_payload_family_id",
    ):
        resolved[key] = family_id
    stamped["resolved_candidate"] = resolved
    return stamped


def _maybe_promote_safe_local_cleanup_primary(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
    mode_config: dict | None,
    debug_sink: dict | None = None,
    source: str = "design_guide_local_cleanup_promoter",
    runtime: LocalCleanupPromotionRuntime | None = None,
) -> tuple[list[dict], dict]:
    if runtime is not None:
        _bind_local_cleanup_promotion_runtime(runtime)
    items = [item for item in list(guidance_items or []) if isinstance(item, dict)]
    previous_primary_title = str((items[0] or {}).get("title_main") or "").strip() if items else None
    debug = _local_cleanup_debug_defaults(previous_primary_title)
    ov = overview if isinstance(overview, dict) else {}
    mode_cfg = mode_config if isinstance(mode_config, dict) else _design_mode_config(_design_optimisation_goal(state))
    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_cfg, goal=_design_optimisation_goal(state))

    if bool(ov.get("any_fail")):
        debug["local_cleanup_blocked_reason"] = "active_failure_needs_strengthening"
        if isinstance(debug_sink, dict):
            debug_sink.update(debug)
        return items, debug

    family_utils, materially_overprovided_families, governing_family = identify_materially_overprovided_non_governing_families(ov)
    cleanup_actions = dict(_resolve_design_actions_from_state(state) or {})
    cleanup_direct_vu = abs(_float_from_state(state, "uls_Vstar", _float_from_state(state, "Vu_star", 0.0)))
    if (
        _shear_demands_negligible(cleanup_actions)
        or cleanup_direct_vu <= float(GUIDANCE_SHEAR_DEMAND_ABS_TOL_KN) + 1e-12
    ):
        materially_overprovided_families = [
            family for family in materially_overprovided_families
            if str(family).strip().lower() != "shear"
        ]
    debug["family_utils"] = dict(family_utils)
    debug["materially_overprovided_families"] = list(materially_overprovided_families)
    debug["materially_overprovided_threshold"] = 0.70
    debug["governing_family"] = governing_family

    current_worst_for_direct = None
    try:
        current_worst_for_direct = float(ov.get("worst_util") or 0.0)
    except Exception:
        current_worst_for_direct = None
    current_in_target_for_cleanup_acceptance = bool(
        _is_in_target_zone_with_eps(ov, mode_cfg, eps=TARGET_BAND_EPS)
        or (
            current_worst_for_direct is not None
            and float(t_lo) - 0.015 <= float(current_worst_for_direct) <= float(t_hi) + 1e-9
        )
    )
    if current_in_target_for_cleanup_acceptance and not materially_overprovided_families:
        debug["local_cleanup_blocked_reason"] = "accepted_green_no_materially_overprovided_family"
        debug["local_cleanup_search_ran"] = False
        debug["safe_local_cleanup_count"] = 0
        debug["executable_safe_cleanup_count"] = 0
        debug["terminal_state_reason"] = "accepted_green_no_materially_overprovided_family"
        if isinstance(debug_sink, dict):
            debug_sink.update(debug)
        return [], debug
    if current_in_target_for_cleanup_acceptance:
        shear_low_blocker = None
        if "shear" in {str(f or "").strip().lower() for f in materially_overprovided_families}:
            shear_low_blocker = _shear_low_util_active_links_exact_blocker(
                state,
                ov,
                threshold=FINAL_ACCEPTED_MIN_FAMILY_UTIL,
            )
        if _accepted_green_exact_blocker_is_valid(shear_low_blocker):
            exact_blockers = dict(debug.get("post_click_exact_blockers_by_family") or {})
            exact_blockers["shear"] = dict(shear_low_blocker)
            debug["post_click_exact_blockers_by_family"] = exact_blockers
            debug["post_click_accepted_green_valid"] = True
            debug["post_click_unresolved_low_util_families"] = []
            debug["local_cleanup_blocked_reason"] = "accepted_green_low_shear_exact_blocker"
            debug["local_cleanup_search_ran"] = True
            debug["local_cleanup_search_exhaustive"] = True
            debug["safe_local_cleanup_count"] = 0
            debug["executable_safe_cleanup_count"] = 0
            debug["terminal_state_reason"] = "accepted_green_low_shear_exact_blocker"
            if isinstance(debug_sink, dict):
                debug_sink.update(debug)
            accepted_item = _optimal_guidance_item(state, ov)
            accepted_item["guidance_intent"] = "already_efficient"
            return [accepted_item], debug
        in_target_acceptance_audit = _post_click_accepted_green_audit(
            ov,
            blocker_source=debug_sink if isinstance(debug_sink, dict) else None,
            state=state,
        )
        debug.update(in_target_acceptance_audit)
        if not bool(in_target_acceptance_audit.get("post_click_accepted_green_valid")):
            debug["terminal_state_blocked_by_local_cleanup"] = True
        else:
            debug["local_cleanup_blocked_reason"] = "accepted_green_no_unresolved_materially_overprovided_family"
            debug["local_cleanup_search_ran"] = False
            debug["safe_local_cleanup_count"] = 0
            debug["executable_safe_cleanup_count"] = 0
            debug["terminal_state_reason"] = "accepted_green_no_unresolved_materially_overprovided_family"
            if isinstance(debug_sink, dict):
                debug_sink.update(debug)
            return [], debug
    if _local_cleanup_post_apply_acceptance_matches(state):
        post_apply_audit = _post_click_accepted_green_audit(
            ov,
            blocker_source=debug_sink if isinstance(debug_sink, dict) else None,
            state=state,
        )
        debug.update(post_apply_audit)
        if bool(post_apply_audit.get("post_click_accepted_green_valid")):
            debug["local_cleanup_blocked_reason"] = "post_apply_cleanup_state_already_accepted"
            debug["local_cleanup_search_ran"] = False
            debug["safe_local_cleanup_count"] = 0
            debug["executable_safe_cleanup_count"] = 0
            debug["terminal_state_reason"] = "post_apply_cleanup_state_accepted"
            if isinstance(debug_sink, dict):
                debug_sink.update(debug)
            return [], debug
        debug["local_cleanup_blocked_reason"] = str(
            post_apply_audit.get("post_click_accepted_green_invalid_reason")
            or "post_apply_cleanup_state_has_unresolved_overprovided_family"
        )
        debug["terminal_state_blocked_by_local_cleanup"] = True

    candidate_rows: list[tuple[dict, dict]] = []
    blocked_reasons: list[str] = []
    candidate_items = list(items)
    direct_cleanup_search_evidence: dict = {}
    try:
        should_run_direct_cleanup_search = bool(
            current_worst_for_direct is not None
            and (
                current_worst_for_direct < float(t_lo) - 1e-9
                or (
                    current_worst_for_direct <= float(t_hi) + 1e-9
                    and bool(materially_overprovided_families)
                )
            )
        )
        direct_tightening_item = (
            _family_ladder_guidance_item(
                state,
                ov,
                mode_cfg,
                strengthening=False,
                debug_sink=debug_sink if isinstance(debug_sink, dict) else None,
            )
            if should_run_direct_cleanup_search
            else None
        )
        if isinstance(debug_sink, dict):
            direct_cleanup_search_evidence = dict(debug_sink.get("local_cleanup_candidate_search_evidence") or {})
    except Exception:
        direct_tightening_item = None
    if isinstance(direct_tightening_item, dict):
        direct_tightening_item["local_cleanup_candidate"] = True
        direct_tightening_item["source"] = "generate_in_target_local_cleanup_candidates"
        candidate_items.insert(0, direct_tightening_item)
    shear_item = _shear_tightening_as_local_cleanup_item(state, ov, efficiency_state)
    if isinstance(shear_item, dict):
        candidate_items.append(shear_item)

    for idx, item in enumerate(candidate_items):
        promoted, detail = _evaluate_local_cleanup_guidance_item(
            item,
            state=state,
            overview=ov,
            mode_config=mode_cfg,
            source=f"{source}_{idx}",
        )
        if isinstance(promoted, dict):
            candidate_rows.append((promoted, detail))
        else:
            reason = str(detail.get("blocked_reason") or "").strip()
            if reason:
                blocked_reasons.append(reason)

    if not candidate_rows:
        debug["local_cleanup_blocked_reason"] = blocked_reasons[0] if blocked_reasons else "no_valid_local_cleanup_candidate"
        if direct_cleanup_search_evidence:
            debug["local_cleanup_candidate_search_evidence"] = dict(direct_cleanup_search_evidence)
            debug["candidate_search_evidence"] = dict(direct_cleanup_search_evidence)
            inventory = []
            for bucket in ("target_band_candidates", "safe_executor_backed_candidates", "rejected_target_band_candidates"):
                inventory.extend([dict(row) for row in list(direct_cleanup_search_evidence.get(bucket) or []) if isinstance(row, dict)])
            debug["local_cleanup_candidate_inventory"] = inventory[:80]
            debug["local_cleanup_candidate_inventory_count"] = len(inventory)
            debug["candidate_inventory_count"] = len(inventory)
            debug["local_cleanup_search_exhaustive"] = bool(direct_cleanup_search_evidence.get("candidate_search_exhaustive"))
            debug["local_cleanup_search_ran"] = bool(materially_overprovided_families)
            debug["safe_local_cleanup_count"] = int(direct_cleanup_search_evidence.get("safe_executor_backed_candidates_count") or 0)
            debug["executable_safe_cleanup_count"] = int(
                sum(1 for row in inventory if bool(row.get("safe_executor_backed")) and not bool(row.get("advisory_only")))
            )
            debug["advisory_cleanup_count"] = int(
                sum(1 for row in inventory if bool(row.get("advisory_only")))
            )
            debug["local_cleanup_blocked_reasons_by_family"] = {
                family: [debug["local_cleanup_blocked_reason"]]
                for family in materially_overprovided_families
            }
        if isinstance(debug_sink, dict):
            debug_sink.update(debug)
        return items, debug

    material_family_set = {str(family).strip().lower() for family in materially_overprovided_families}

    def _cleanup_selection_key(row: tuple[dict, dict]) -> tuple:
        candidate_item, detail = row
        candidate_family = str(detail.get("family") or "").strip().lower()
        updates = dict(
            (candidate_item.get("action_payload") or {}).get("resolved_candidate_updates")
            or candidate_item.get("resolved_candidate_updates")
            or (candidate_item.get("resolved_candidate") or {}).get("updates")
            or {}
        )
        exact_family = candidate_family in material_family_set
        affects_material = any(
            _local_cleanup_candidate_affects_family(family, updates)
            for family in material_family_set
        )
        complexity = int(detail.get("candidate_complexity_score") or len(updates) or 0)
        material_delta = float(detail.get("material_proxy_delta") or 0.0)
        candidate_overview = dict(
            (candidate_item.get("resolved_candidate") or {}).get("overview")
            or (candidate_item.get("action_payload") or {}).get("candidate_overview")
            or detail.get("overview")
            or {}
        )
        candidate_state = dict(state)
        candidate_state.update(updates)
        final_audit = (
            _post_click_accepted_green_audit(
                candidate_overview,
                blocker_source=candidate_item,
                state=candidate_state,
            )
            if candidate_overview
            else {}
        )
        final_valid = bool(final_audit.get("post_click_accepted_green_valid"))
        unresolved_low_count = len(list(final_audit.get("post_click_unresolved_low_util_families") or []))
        below_threshold_count = len(list(final_audit.get("post_click_families_below_final_threshold") or []))
        if candidate_overview:
            _, candidate_material_families, _ = identify_materially_overprovided_non_governing_families(candidate_overview)
            remaining_material_count = len(candidate_material_families)
        else:
            remaining_material_count = 99
        direct_target_candidate = str(candidate_item.get("source") or "").strip() == "generate_in_target_local_cleanup_candidates"
        return (
            0 if final_valid else 1,
            unresolved_low_count,
            below_threshold_count,
            remaining_material_count,
            0 if direct_target_candidate else 1,
            0 if exact_family else 1 if affects_material else 2,
            complexity,
            float(row[1].get("distance", float("inf")) or float("inf")),
            material_delta,
            str(row[0].get("title_main") or ""),
        )

    best, best_detail = min(
        candidate_rows,
        key=_cleanup_selection_key,
    )
    best_publication_family_id = _publication_family_id_for_local_cleanup(best_detail.get("family"))
    local_candidate_dicts: list[dict] = []
    for idx, (candidate_item, detail) in enumerate(candidate_rows, start=1):
        item_payload = dict(candidate_item.get("action_payload") or {})
        item_resolved = dict(candidate_item.get("resolved_candidate") or {})
        item_updates = dict(
            item_payload.get("resolved_candidate_updates")
            or candidate_item.get("resolved_candidate_updates")
            or item_resolved.get("updates")
            or {}
        )
        item_util = (
            candidate_item.get("resolved_candidate_post_util")
            if candidate_item.get("resolved_candidate_post_util") is not None
            else item_payload.get("resolved_candidate_post_util", item_resolved.get("candidate_post_util", item_resolved.get("worst_util")))
        )
        local_candidate_dicts.append(
            {
                "candidate_id": detail.get("candidate_id") or _guidance_cleanup_candidate_id(str(detail.get("family") or "cleanup"), item_updates),
                "label": candidate_item.get("title_main") or item_resolved.get("label") or f"Local cleanup {idx}",
                "updates": dict(item_updates),
                "candidate_post_util": item_util,
                "worst_util": item_util,
                "is_compliant": True,
                "overview": dict(item_resolved.get("overview") or {}),
                "candidate_complexity_score": detail.get("candidate_complexity_score"),
                "net_efficiency_delta": detail.get("net_efficiency_delta"),
                "material_proxy_before": detail.get("material_proxy_before"),
                "material_proxy_after": detail.get("material_proxy_after"),
                "material_proxy_delta": detail.get("material_proxy_delta"),
                "is_executable": bool(detail.get("is_executable")),
                "advisory_only": bool(detail.get("advisory_only")),
                "affected_family": detail.get("family"),
            }
        )
    selected_candidate_for_evidence = next(
        (
            cand
            for cand in local_candidate_dicts
            if str(cand.get("candidate_id") or "") == str(best_detail.get("candidate_id") or "")
        ),
        local_candidate_dicts[0] if local_candidate_dicts else None,
    )
    existing_best_evidence = dict(
        best.get("candidate_search_evidence")
        or (best.get("action_payload") or {}).get("candidate_search_evidence")
        or (best.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    if str(existing_best_evidence.get("search_scope") or "") == "design_guide_direct_target_band_search":
        evidence = dict(existing_best_evidence)
    else:
        evidence = _build_candidate_search_evidence(
            selected_candidate=selected_candidate_for_evidence,
            all_candidates=local_candidate_dicts,
            target_low=float(t_lo),
            target_high=float(t_hi),
            exhaustive=True,
            search_scope="safe_local_cleanup_surviving_geometry_bottom_shear",
            selected_title=str(best.get("title_main") or ""),
        )
    evidence_inventory = []
    for _bucket in ("target_band_candidates", "safe_executor_backed_candidates", "rejected_target_band_candidates"):
        evidence_inventory.extend([dict(row) for row in list(evidence.get(_bucket) or []) if isinstance(row, dict)])
    best["candidate_search_evidence"] = dict(evidence)
    best["candidate_id"] = evidence.get("selected_candidate_id")
    best["source_candidate_id"] = evidence.get("selected_candidate_id")
    best_payload = dict(best.get("action_payload") or {})
    best_payload["candidate_search_evidence"] = dict(evidence)
    best_payload["source_candidate_id"] = evidence.get("selected_candidate_id")
    best["action_payload"] = best_payload
    best_resolved = dict(best.get("resolved_candidate") or {})
    best_resolved["candidate_search_evidence"] = dict(evidence)
    best_resolved["candidate_id"] = evidence.get("selected_candidate_id")
    best_resolved["source_candidate_id"] = evidence.get("selected_candidate_id")
    best["resolved_candidate"] = best_resolved
    best = _stamp_local_cleanup_publication_family(best, best_publication_family_id)
    remaining = [
        item for item in items
        if _guidance_update_signature(item) != _guidance_update_signature(best)
    ]
    promoted_items = [best] + remaining[:1]
    debug.update(
        {
        "local_cleanup_promoted": True,
            "local_cleanup_family": best_detail.get("family"),
            "local_cleanup_publication_family_id": best_publication_family_id,
            "local_cleanup_candidate_id": best_detail.get("candidate_id"),
            "local_cleanup_reason": "safe_executor_backed_cleanup_preferred_over_terminal_or_noop_primary",
            "local_cleanup_blocked_reason": None,
            "final_primary_title": str(best.get("title_main") or "").strip() or None,
            "candidate_search_evidence": dict(evidence),
            "local_cleanup_candidate_search_evidence": dict(evidence),
            "local_cleanup_candidate_inventory": evidence_inventory[:80],
            "local_cleanup_candidate_inventory_count": len(evidence_inventory),
            "candidate_inventory_count": len(evidence_inventory),
            "local_cleanup_search_ran": bool(materially_overprovided_families),
            "local_cleanup_search_exhaustive": True,
            "safe_local_cleanup_count": len(local_candidate_dicts),
            "executable_safe_cleanup_count": len([c for c in local_candidate_dicts if bool(c.get("is_executable")) and not bool(c.get("advisory_only"))]),
            "advisory_cleanup_count": len([c for c in local_candidate_dicts if bool(c.get("advisory_only"))]),
            "local_cleanup_blocked_reasons_by_family": {},
        },
    )
    if isinstance(debug_sink, dict):
        debug_sink.update(debug)
        debug_sink["guidance_branch"] = f"local_cleanup_{debug['local_cleanup_family'] or 'general'}"
        debug_sink["selected_action_type"] = best.get("action_type")
        debug_sink["selected_title"] = best.get("title_main")
        debug_sink["design_guide_terminal_state"] = None
        debug_sink["stop_reason"] = None
        debug_sink["user_visible_no_action_reason"] = None
    return promoted_items, debug


__all__ = [
    "bind_local_cleanup_promotion_dependencies",
    "_maybe_promote_safe_local_cleanup_primary",
]
