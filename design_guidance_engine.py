"""Compatibility wrapper for the Design Guide brain.

The implementation now lives in ``design_brain.engine``. Keep this module so
existing imports, including legacy helper imports used by old diagnostics,
continue to resolve unchanged.
"""

from design_brain import engine as _engine

globals().update(
    {
        name: getattr(_engine, name)
        for name in dir(_engine)
        if not name.startswith("__")
    }
)

def legacy_item_from_decision(base_item, decision):
    """Return the legacy primary item shape for terminal engine decisions.

    Old Inputs-page callers still expect this helper while the Design Brain
    engine owns the actual decision. Keep this as a narrow compatibility shim:
    non-terminal decisions flow through unchanged.
    """

    if not isinstance(base_item, dict) or not isinstance(decision, dict):
        return base_item

    card = dict(decision.get("card") or {})
    presentation = dict(decision.get("presentation") or {})
    button_contract = dict(decision.get("button_contract") or {})
    outcome = dict(decision.get("target_band_outcome") or {})
    debug = dict(decision.get("debug") or {})

    intent = str(card.get("intent") or presentation.get("guidance_intent") or "").strip()
    terminal_state = str(presentation.get("design_guide_terminal_state") or "").strip()
    terminal_reason = str(debug.get("decision_reason") or "").strip()
    is_terminal = (
        intent == "already_efficient"
        or terminal_state in {"optimal", "very_low_demand"}
        or terminal_reason == "terminal_in_target"
    )
    if not is_terminal:
        return base_item

    item = dict(base_item)
    title = card.get("title") or presentation.get("headline") or item.get("title_main") or item.get("title")
    body = card.get("body") or presentation.get("subtext") or item.get("reason") or item.get("body")
    item.update(
        {
            "title": title,
            "title_main": title,
            "reason": body,
            "body": body,
            "guidance_intent": "already_efficient",
            "design_guide_terminal_state": terminal_state or "optimal",
            "button_contract": button_contract,
            "candidate_search_evidence": dict(decision.get("candidate_search_evidence") or {}),
        }
    )
    display_truth = dict(item.get("display_truth") or {})
    display_truth.update(
        {
            "display_truth_source": (
                presentation.get("display_truth_source")
                or card.get("display_truth_source")
                or display_truth.get("display_truth_source")
                or "published_summary"
            ),
            "displayed_util": (
                presentation.get("displayed_util")
                if presentation.get("displayed_util") is not None
                else card.get("displayed_util")
            ),
            "displayed_status": presentation.get("displayed_status") or card.get("status_text") or "OPTIMAL",
            "displayed_within_target_band": True,
            "target_low": (
                presentation.get("target_low")
                if presentation.get("target_low") is not None
                else card.get("target_low")
            ),
            "target_high": (
                presentation.get("target_high")
                if presentation.get("target_high") is not None
                else card.get("target_high")
            ),
            "source_summary_util": (
                presentation.get("source_summary_util")
                if presentation.get("source_summary_util") is not None
                else outcome.get("current_util")
            ),
            "source_candidate_util": (
                presentation.get("source_candidate_util")
                if presentation.get("source_candidate_util") is not None
                else outcome.get("preview_util")
            ),
            "source_post_commit_util": (
                presentation.get("source_post_commit_util")
                if presentation.get("source_post_commit_util") is not None
                else outcome.get("post_click_util")
            ),
        }
    )
    item["display_truth"] = display_truth
    return item


__all__ = [name for name in globals() if not name.startswith("__")]
