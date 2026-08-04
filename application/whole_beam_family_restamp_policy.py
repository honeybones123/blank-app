"""Application-owned whole-beam family restamping policy."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping


_BENDING_UPDATE_KEYS = {
    "D", "b", "bw", "bot1_count", "bot2_count", "db_bot_1", "db_bot_2",
    "bot_row_1_bars", "bot_row_2_bars", "bot_row_1_dia", "bot_row_2_dia",
}
_SHEAR_UPDATE_KEYS = {"lig_d", "lig_legs", "s_lig"}
_ALLOWED_RESTAMPS = {
    ("BENDING_FAIL_GOVERNS", "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"),
    ("SHEAR_FAIL_GOVERNS", "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS"),
}


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _normalise_active_family(value: Any, *, statuses: Mapping[str, Any]) -> str:
    family = str(value or "").strip()
    upper = family.upper()
    aliases = {"BENDING": "BENDING_FAIL_GOVERNS", "SHEAR": "SHEAR_FAIL_GOVERNS"}
    if upper in aliases and str(statuses.get(family.lower()) or "").strip().upper() == "FAIL":
        return aliases[upper]
    return upper


def restamp_primary_guidance_family_from_whole_beam(
    guidance_items: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    guidance_debug: Mapping[str, Any] | None,
    *,
    family_classifier: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    items = [deepcopy(dict(item)) for item in list(guidance_items or []) if isinstance(item, Mapping)]
    debug = _mapping(guidance_debug)
    if not items:
        return items, debug, {"restamped": False, "reason": "no_primary_item"}
    overview = _mapping(debug.get("overview"))
    statuses = {
        str(key or "").strip().lower(): str(value or "").strip().upper()
        for key, value in _mapping(overview.get("statuses")).items()
    }
    utils = _mapping(overview.get("utils"))
    if not statuses and not utils:
        return items, debug, {"restamped": False, "reason": "no_overview"}

    def util(domain: str) -> float | None:
        try:
            value = utils.get(domain)
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def not_applicable(domain: str) -> bool:
        status = statuses.get(domain, "")
        return status in {"CAPACITY", "INFO", "NOT RUN", "NOT_RUN", "NOT SUPPLIED"} or (util(domain) is None and not status)

    item = _mapping(items[0])
    button = _mapping(item.get("button_contract") or debug.get("primary_button_contract"))
    action_payload = _mapping(item.get("action_payload"))
    resolved = _mapping(item.get("resolved_candidate"))
    updates = _mapping(
        button.get("updates")
        or action_payload.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or resolved.get("updates")
        or item.get("updates")
    )
    if not updates:
        return items, debug, {"restamped": False, "reason": "no_updates"}
    current_family = _normalise_active_family(
        item.get("selected_family_id")
        or button.get("selected_family_id")
        or button.get("family")
        or item.get("family")
        or item.get("check_key"),
        statuses=statuses,
    )
    if current_family not in {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"}:
        return items, debug, {"restamped": False, "reason": "family_not_active_repair", "current_family": current_family}
    bending_util = util("bending")
    shear_util = util("shear")
    target_low = 0.85
    whole_beam = {
        "bending_state": "FAIL" if statuses.get("bending") == "FAIL" else "TARGET" if not_applicable("bending") else "OVERDESIGNED" if bending_util is not None and bending_util < target_low else "TARGET",
        "shear_state": "FAIL" if statuses.get("shear") == "FAIL" else "TARGET" if not_applicable("shear") else "OVERDESIGNED" if shear_util is not None and shear_util < target_low else "TARGET",
        "bending_utilisation": bending_util if bending_util is not None else 0.9,
        "shear_utilisation": shear_util if shear_util is not None else 0.9,
        "can_strengthen_bending": bool(set(updates) & _BENDING_UPDATE_KEYS),
        "can_strengthen_shear": bool(set(updates) & _SHEAR_UPDATE_KEYS),
        "can_optimise_shear_without_hurting_bending": bool(not not_applicable("shear") and shear_util is not None and shear_util < target_low),
        "can_optimise_bending_without_hurting_shear": bool(not not_applicable("bending") and bending_util is not None and bending_util < target_low),
    }
    chooser = family_classifier(whole_beam)
    selected_family = str(chooser.get("selected_family_id") or "").strip().upper()
    if (current_family, selected_family) not in _ALLOWED_RESTAMPS:
        return items, debug, {"restamped": False, "reason": "chooser_family_not_mixed", "current_family": current_family, "chooser_family": selected_family, "whole_beam": whole_beam}
    identity = {
        "family": selected_family,
        "family_id": selected_family,
        "selected_family_id": selected_family,
        "published_family_id": selected_family,
        "cta_family_id": selected_family,
        "apply_payload_family_id": selected_family,
        "candidate_family_id": selected_family,
        "card_family_id": selected_family,
    }
    for target in (item, button, action_payload, resolved):
        target.update(identity)
    item["button_contract"] = button
    item["action_payload"] = action_payload
    item["resolved_candidate"] = resolved
    item["matched_family_ids"] = list(chooser.get("matched_family_ids") or [selected_family])
    item["family_chooser_contract"] = "family_chooser_contract"
    item["family_selection_source"] = "design_brain.whole_beam_family_restamp.restamp_primary_guidance_family_from_whole_beam"
    items[0] = item
    meta = {"restamped": True, "from_family": current_family, "to_family": selected_family, "whole_beam": whole_beam, "classification_hash": chooser.get("classification_hash")}
    debug.update({
        "primary_item": item,
        "primary_button_contract": button,
        "button_contract": button,
        "displayed_primary_button_contract": button,
        "selected_family_id": selected_family,
        "published_family_id": selected_family,
        "cta_family_id": selected_family,
        "matched_family_ids": list(item["matched_family_ids"]),
        "family_chooser_contract": "family_chooser_contract",
        "overview_family_chooser_restamp": meta,
    })
    return items, debug, meta


__all__ = ["restamp_primary_guidance_family_from_whole_beam"]
