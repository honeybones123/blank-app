"""Design Guide title-alignment verification coordination."""

from __future__ import annotations

from typing import Any


_TITLE_ALIGNMENT_VERIFICATION_DEPENDENCIES: tuple[str, ...] = (
    "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT",
    "_compound_subfamilies_from_updates",
    "_first_actionable_guidance_item",
    "_infer_families_mentioned_in_label",
    "_label_consistent_with_updates_families",
    "_resolve_recommendation_updates",
    "_selector_final_winner_label_from_guidance_debug",
)


def bind_title_alignment_verification_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _TITLE_ALIGNMENT_VERIFICATION_DEPENDENCIES
            if name in namespace
        }
    )


def _design_guide_title_alignment_verification_record(
    *,
    guidance_items: list[dict],
    guidance_debug: dict | None,
    disp_state: dict,
    recommendation_result: dict | None,
    pending_recommendation: dict | None,
) -> dict:
    """
    One-shot verification: primary actionable item, pending, recommendation_result, and top card title
    share one canonical title; title text matches update families. Emitted every Design Guide cycle.
    """

    def _nt(x: object) -> str:
        return str(x or "").strip()

    actionable = _first_actionable_guidance_item(guidance_items)
    top = guidance_items[0] if guidance_items else None
    winning_candidate_is_primary_card = bool(
        actionable is not None and top is not None and actionable is top,
    )

    canon_from_item = _nt(actionable.get("canonical_winner_label")) if actionable else ""
    dbg_sel = _selector_final_winner_label_from_guidance_debug(guidance_debug)
    selector_final_winner_label = canon_from_item or dbg_sel

    t_main = _nt(actionable.get("title_main")) if actionable else ""
    t_card = _nt(top.get("title_main")) if top else ""
    t_rr = _nt(recommendation_result.get("title")) if recommendation_result else ""
    rc_lab = _nt((actionable.get("resolved_candidate") or {}).get("label")) if actionable else ""
    t_rr_canon = _nt(recommendation_result.get("canonical_winner_label")) if recommendation_result else ""

    pending_skipped_for_auto_design = bool(
        isinstance(pending_recommendation, dict)
        and str(pending_recommendation.get("_source") or "").strip() == "auto_design",
    )
    t_pending = ""
    if isinstance(pending_recommendation, dict) and not pending_skipped_for_auto_design:
        t_pending = _nt(pending_recommendation.get("title"))

    updates: dict = {}
    if recommendation_result and isinstance(recommendation_result.get("updates"), dict):
        updates = dict(recommendation_result["updates"])
    elif actionable:
        try:
            updates = dict(_resolve_recommendation_updates(actionable, state=disp_state) or {})
        except Exception:
            updates = {}

    derived_update_family = list(_compound_subfamilies_from_updates(updates))

    if not actionable:
        _dbg = guidance_debug if isinstance(guidance_debug, dict) else {}
        _eff_st = _dbg.get("efficiency_tightening_state")
        _eff_cls = str((_eff_st or {}).get("classification") or "") if isinstance(_eff_st, dict) else ""
        _top_term = str((top or {}).get("design_guide_terminal_state") or "")
        terminal_optimal_align = _eff_cls == "optimal" or _top_term == "optimal"
        terminal_vld_align = _eff_cls == "very_low_demand" or _top_term == "very_low_demand"
        _term_state = (
            "optimal"
            if terminal_optimal_align
            else ("very_low_demand" if terminal_vld_align else None)
        )
        _align_reason = (
            "terminal_optimal_no_recommendation"
            if terminal_optimal_align
            else (
                "terminal_very_low_demand_no_recommendation"
                if terminal_vld_align
                else "no_actionable_guidance_item"
            )
        )
        return {
            "event": DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT,
            "selector_final_winner_label": selector_final_winner_label,
            "resolved_candidate_label": None,
            "winner_updates": {},
            "guidance_item_title_main": None,
            "pending_recommendation_title": t_pending or None,
            "recommendation_result_title": t_rr or None,
            "displayed_card_title": t_card or None,
            "pending_skipped_for_auto_design": pending_skipped_for_auto_design,
            "winning_candidate_is_primary_card": False,
            "titles_all_equal": True,
            "derived_update_family": [],
            "title_family_matches_updates": True,
            "selector_label_matches_display_chain": True,
            "design_guide_terminal_state": _term_state,
            "design_guide_has_actionable_recommendation": False,
            "design_guide_terminal_positive": bool(terminal_optimal_align or terminal_vld_align),
            "design_guide_title_alignment_ok": True,
            "alignment_verdict_reason": _align_reason,
        }

    if not updates:
        return {
            "event": DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT,
            "selector_final_winner_label": selector_final_winner_label,
            "resolved_candidate_label": rc_lab or None,
            "winner_updates": {},
            "guidance_item_title_main": t_main,
            "pending_recommendation_title": t_pending or None,
            "recommendation_result_title": t_rr or None,
            "displayed_card_title": t_card or None,
            "pending_skipped_for_auto_design": pending_skipped_for_auto_design,
            "winning_candidate_is_primary_card": winning_candidate_is_primary_card,
            "titles_all_equal": False,
            "derived_update_family": [],
            "title_family_matches_updates": False,
            "selector_label_matches_display_chain": False,
            "design_guide_terminal_state": None,
            "design_guide_has_actionable_recommendation": bool(actionable),
            "design_guide_terminal_positive": False,
            "design_guide_title_alignment_ok": False,
            "alignment_verdict_reason": "actionable_but_empty_winner_updates",
        }

    expected_families = frozenset(derived_update_family)
    if t_main and expected_families:
        title_family_matches_updates = _label_consistent_with_updates_families(t_main, expected_families)
    elif t_main:
        title_family_matches_updates = not bool(_infer_families_mentioned_in_label(t_main))
    else:
        title_family_matches_updates = False

    titles_to_compare = [t_main, t_rr, t_card]
    if t_pending:
        titles_to_compare.append(t_pending)
    if rc_lab:
        titles_to_compare.append(rc_lab)
    if t_rr_canon:
        titles_to_compare.append(t_rr_canon)
    non_empty = [x for x in titles_to_compare if x]
    titles_all_equal = len(set(non_empty)) <= 1 if non_empty else False

    title_locked = bool(
        actionable.get("title_locked_from_final_winner") and canon_from_item,
    )
    if title_locked:
        chain_parts = [t_main, t_rr, t_card, rc_lab, canon_from_item]
        if t_pending:
            chain_parts.append(t_pending)
        if t_rr_canon:
            chain_parts.append(t_rr_canon)
        selector_label_matches_display_chain = all(_nt(p) == canon_from_item for p in chain_parts)
        if dbg_sel and dbg_sel != canon_from_item:
            selector_label_matches_display_chain = False
    else:
        selector_label_matches_display_chain = True

    design_guide_title_alignment_ok = bool(
        winning_candidate_is_primary_card
        and titles_all_equal
        and title_family_matches_updates
        and bool(t_main)
        and selector_label_matches_display_chain
    )

    return {
        "event": DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT,
        "selector_final_winner_label": selector_final_winner_label,
        "resolved_candidate_label": rc_lab or None,
        "winner_updates": dict(updates),
        "guidance_item_title_main": t_main,
        "pending_recommendation_title": t_pending or None,
        "recommendation_result_title": t_rr or None,
        "displayed_card_title": t_card or None,
        "pending_skipped_for_auto_design": pending_skipped_for_auto_design,
        "winning_candidate_is_primary_card": winning_candidate_is_primary_card,
        "titles_all_equal": titles_all_equal,
        "derived_update_family": derived_update_family,
        "title_family_matches_updates": title_family_matches_updates,
        "selector_label_matches_display_chain": selector_label_matches_display_chain,
        "design_guide_terminal_state": None,
        "design_guide_has_actionable_recommendation": True,
        "design_guide_terminal_positive": False,
        "design_guide_title_alignment_ok": design_guide_title_alignment_ok,
        "alignment_verdict_reason": (
            None
            if design_guide_title_alignment_ok
            else (
                "selector_display_chain_mismatch"
                if not selector_label_matches_display_chain
                else (
                    "titles_mismatch"
                    if not titles_all_equal
                    else (
                        "title_family_mismatch"
                        if not title_family_matches_updates
                        else (
                            "primary_card_not_actionable"
                            if not winning_candidate_is_primary_card
                            else "unknown"
                        )
                    )
                )
            )
        ),
    }


__all__ = [
    "bind_title_alignment_verification_dependencies",
    "_design_guide_title_alignment_verification_record",
]
