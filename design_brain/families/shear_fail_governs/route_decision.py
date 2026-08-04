from __future__ import annotations

from typing import Any


def _as_plain_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def build_shear_fail_route_success_result(
    *,
    decision: dict,
    item: dict,
    diagnostics: dict,
    evidence: dict,
    button: dict,
    updates: dict,
    candidate_id: str,
    candidate_title: str,
    expected_util: Any,
    family_route_owner: str,
    candidate_strategy: str,
    ranking_strategy: str,
    evidence_strategy: str,
    publication_rule: str,
    cta_rule: str,
    stale_blocker_keys: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    decision_in = _as_plain_dict(decision)
    item_in = _as_plain_dict(item)
    diagnostics_out = _as_plain_dict(diagnostics)
    evidence_in = _as_plain_dict(evidence)
    button_out = _as_plain_dict(button)
    updates_out = _as_plain_dict(updates)

    card = _as_plain_dict(decision_in.get("card"))
    card.update(
        {
            "title": "Shear capacity is low",
            "badge": "REPAIR",
            "intent": "required_fix",
            "theme": "fail",
            "css_bucket": "fail",
            "use_success_style": False,
            "family": "shear",
            "check_key": "shear",
            "body": (
                "Active shear capacity is failing; this one-click repair is "
                "executor-backed and keeps all required checks acceptable."
            ),
            "status_text": "FAIL",
        }
    )
    presentation = _as_plain_dict(decision_in.get("presentation"))
    presentation.update(
        {
            "theme": "fail",
            "css_bucket": "fail",
            "use_success_style": False,
            "headline": "Shear capacity is low",
            "subtext": card["body"],
            "show_apply_button": True,
            "critical_status": "FAIL",
            "guidance_intent": "required_fix",
        }
    )
    button_out.update(
        {
            "enabled": True,
            "actionable": True,
            "family": "shear",
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates_out),
            "preview_pass": True,
            "blocking_reason": None,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "selected_family_id": "SHEAR_FAIL_GOVERNS",
            "published_family_id": "SHEAR_FAIL_GOVERNS",
            "cta_family_id": "SHEAR_FAIL_GOVERNS",
        }
    )
    if expected_util is not None:
        button_out["expected_util"] = expected_util

    evidence_base = dict(evidence_in)
    for stale_key in stale_blocker_keys:
        evidence_base.pop(stale_key, None)
    evidence_out = {
        **evidence_base,
        "active_strength_repair_action": True,
        "active_strength_repair_family": "shear",
        "governing_family": "SHEAR_FAIL_GOVERNS",
        "family_routing_used": True,
        "family_route_owner": family_route_owner,
        "selected_candidate_id": candidate_id,
        "selected_candidate_title": candidate_title,
        "selected_candidate_updates": dict(updates_out),
        "safe_repair_candidate_count": max(int(evidence_in.get("safe_repair_candidate_count") or 0), 1),
        "executable_repair_candidate_count": max(int(evidence_in.get("executable_repair_candidate_count") or 0), 1),
    }

    item_out = dict(item_in)
    for stale_key in stale_blocker_keys:
        item_out.pop(stale_key, None)
    item_out.update(
        {
            "title_main": "Shear capacity is low",
            "title": "Shear capacity is low",
            "family": "shear",
            "check_key": "shear",
            "selected_action_family": "shear",
            "guidance_intent": "required_fix",
            "primary_action": "Run one-click auto design",
            "primary_card_actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates_out),
            "selected_action_updates": dict(updates_out),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "selected_family_id": "SHEAR_FAIL_GOVERNS",
            "published_family_id": "SHEAR_FAIL_GOVERNS",
            "cta_family_id": "SHEAR_FAIL_GOVERNS",
            "card_family_id": "SHEAR_FAIL_GOVERNS",
            "family_route_owner": family_route_owner,
            "candidate_search_evidence": dict(evidence_out),
            "final_visible_design_guide_item": True,
            "final_visible_resolver_reason": "shear_fail_family_owner_repair_action",
        }
    )
    contract_for_item = _as_plain_dict(item_out.get("button_contract"))
    contract_for_item.update(
        {
            "enabled": True,
            "actionable": True,
            "family": "shear",
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates_out),
            "preview_pass": True,
            "blocking_reason": None,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
        }
    )
    item_out["button_contract"] = dict(contract_for_item)
    action_payload = _as_plain_dict(item_out.get("action_payload"))
    action_payload.update(
        {
            "family": "shear",
            "resolved_candidate_family_tag": "shear",
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_updates": dict(updates_out),
            "updates": dict(updates_out),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(evidence_out),
            "button_contract": dict(contract_for_item),
        }
    )
    item_out["action_payload"] = dict(action_payload)
    resolved = _as_plain_dict(item_out.get("resolved_candidate"))
    resolved.update(
        {
            "family": "shear",
            "recommendation_family_tag": "shear",
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates_out),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(evidence_out),
        }
    )
    item_out["resolved_candidate"] = dict(resolved)
    diagnostics_out.update(
        {
            "family_routing_used": True,
            "fallback_used": False,
            "fallback_reason": None,
            "candidate_source": candidate_strategy,
            "ranking_source": ranking_strategy,
            "evidence_source": evidence_strategy,
            "publication_source": publication_rule,
            "cta_source": cta_rule,
            "visible_title": "Shear capacity is low",
            "cta_updates_preserved": sorted(str(key) for key in updates_out.keys()),
        }
    )
    debug_out = _as_plain_dict(decision_in.get("debug"))
    for stale_key in stale_blocker_keys:
        debug_out.pop(stale_key, None)
    debug_out["shear_fail_family_routing"] = dict(diagnostics_out)
    decision_out = dict(decision_in)
    decision_out.update(
        {
            "card": card,
            "presentation": presentation,
            "button_contract": button_out,
            "candidate_search_evidence": evidence_out,
            "debug": debug_out,
        }
    )
    return {
        "used": True,
        "decision": decision_out,
        "primary_item": item_out,
        "diagnostics": diagnostics_out,
        "evidence": evidence_out,
    }


__all__ = ["build_shear_fail_route_success_result"]
