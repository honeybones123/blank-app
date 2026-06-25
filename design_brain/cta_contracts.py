"""Pure CTA/button source-precedence selectors.

This module intentionally does not import ``inputs_page``. Live source
collection, Streamlit/session state, publication recovery, and mutation remain
page-owned.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any


def _stable_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _record_attr(source_records: Any, name: str, default: Any = None) -> Any:
    return getattr(source_records, name, default)


@dataclass(frozen=True)
class DesignGuideButtonContractSourceResolution:
    winning_button_contract: dict
    winning_button_contract_source: str
    winning_update_payload: dict
    winning_update_payload_source: str
    winning_action_type: str | None
    winning_action_type_source: str
    winning_candidate: dict
    winning_candidate_source: str
    apply_enabled: bool
    apply_actionable: bool
    disabled_reason: str | None
    final_cta_action_payload_summary: dict
    final_published_item_hash: str
    source_candidates: dict


def build_design_guide_button_contract_source_resolution(
    *,
    winning_button_contract: dict | None,
    winning_button_contract_source: str,
    winning_update_payload: dict | None,
    winning_update_payload_source: str,
    winning_action_type: str | None,
    winning_action_type_source: str,
    winning_candidate: dict | None,
    winning_candidate_source: str,
    apply_enabled: bool,
    apply_actionable: bool,
    disabled_reason: str | None,
    final_cta_action_payload_summary: dict | None,
    final_published_item_hash: str,
    source_candidates: dict | None,
) -> DesignGuideButtonContractSourceResolution:
    """Normalize CTA source-precedence proof output; not product-driving."""
    return DesignGuideButtonContractSourceResolution(
        winning_button_contract=dict(winning_button_contract or {}),
        winning_button_contract_source=str(winning_button_contract_source or ""),
        winning_update_payload=dict(winning_update_payload or {}),
        winning_update_payload_source=str(winning_update_payload_source or ""),
        winning_action_type=(
            str(winning_action_type).strip()
            if winning_action_type is not None and str(winning_action_type).strip()
            else None
        ),
        winning_action_type_source=str(winning_action_type_source or ""),
        winning_candidate=dict(winning_candidate or {}),
        winning_candidate_source=str(winning_candidate_source or ""),
        apply_enabled=bool(apply_enabled),
        apply_actionable=bool(apply_actionable),
        disabled_reason=(
            str(disabled_reason).strip()
            if disabled_reason is not None and str(disabled_reason).strip()
            else None
        ),
        final_cta_action_payload_summary=dict(final_cta_action_payload_summary or {}),
        final_published_item_hash=str(final_published_item_hash or ""),
        source_candidates=copy.deepcopy(dict(source_candidates or {})),
    )


def _button_contract_source_summary(contract: dict | None) -> dict:
    contract_d = dict(contract or {})
    return {
        "present": bool(contract_d),
        "enabled": bool(contract_d.get("enabled")),
        "actionable": bool(contract_d.get("actionable")),
        "action_type": contract_d.get("action_type"),
        "family": contract_d.get("family"),
        "updates": dict(contract_d.get("updates") or {}),
        "updates_hash": _stable_hash(contract_d.get("updates") or {}),
        "candidate_id": contract_d.get("candidate_id"),
        "source_candidate_id": contract_d.get("source_candidate_id"),
        "expected_util": contract_d.get("expected_util"),
        "disabled_reason": contract_d.get("blocking_reason") or contract_d.get("disabled_reason"),
        "hash": _stable_hash(contract_d),
    }


def _cta_action_payload_summary(payload: dict | None) -> dict:
    payload_d = dict(payload or {})
    updates = dict(
        payload_d.get("updates")
        or payload_d.get("action_updates")
        or payload_d.get("resolved_candidate_updates")
        or {}
    )
    return {
        "action_type": payload_d.get("action_type") or payload_d.get("type"),
        "updates": updates,
        "updates_hash": _stable_hash(updates),
        "candidate_id": payload_d.get("candidate_id"),
        "source_candidate_id": payload_d.get("source_candidate_id"),
        "family": payload_d.get("family") or payload_d.get("resolved_candidate_family_tag"),
        "payload_hash": _stable_hash(payload_d),
    }


def select_design_guide_button_contract_source_precedence(
    *,
    source_records: Any,
    button_contract_source_precedence_order: tuple[str, ...] | list[str],
    payload_source_precedence_order: dict | None,
    candidate_source_keys: tuple[str, ...] | list[str],
    source_payload_labels: dict | None = None,
) -> dict:
    """Select CTA source precedence from explicit typed source records.

    Returns the field mapping consumed by
    ``build_design_guide_button_contract_source_resolution``.
    """

    del payload_source_precedence_order  # The contract data is passed through for boundary parity.

    displayed_item = copy.deepcopy(dict(_record_attr(source_records, "displayed_primary_item", {}) or {}))
    final_contract = dict(displayed_item.get("button_contract") or {})
    final_contract_summary = _button_contract_source_summary(final_contract)
    source_map = copy.deepcopy(dict(_record_attr(source_records, "source_candidates", {}) or {}))

    def _summary_matches_final(summary: dict | None) -> bool:
        summary_d = dict(summary or {})
        if not summary_d.get("present"):
            return False
        if summary_d.get("hash") and summary_d.get("hash") == final_contract_summary.get("hash"):
            return True
        comparable_keys = (
            "enabled",
            "actionable",
            "action_type",
            "family",
            "candidate_id",
            "source_candidate_id",
            "expected_util",
            "disabled_reason",
        )
        if any(summary_d.get(key) != final_contract_summary.get(key) for key in comparable_keys):
            return False
        return dict(summary_d.get("updates") or {}) == dict(final_contract_summary.get("updates") or {})

    label_map = dict(source_payload_labels or {})
    source_order = list(label_map)
    source_order.extend(key for key in list(candidate_source_keys or ()) if key not in source_order)
    source_order.extend(key for key in source_map if key not in source_order)

    winning_source = ""
    for source_key in source_order:
        source_key_s = str(source_key)
        if not source_key_s.endswith("_source"):
            continue
        source_summary = dict(source_map.get(source_key_s) or {})
        if source_summary.get("present"):
            winning_source = source_key_s
            break

    for source_key in source_order:
        if winning_source:
            break
        if _summary_matches_final(dict(source_map.get(source_key) or {})):
            winning_source = str(source_key)
            break

    if not winning_source:
        primary_item = dict(_record_attr(source_records, "primary_item", {}) or {})
        contract_lookup = {
            "primary.button_contract": _button_contract_source_summary(
                dict(primary_item.get("button_contract") or {})
            ),
            "debug.displayed_primary_button_contract": _button_contract_source_summary(
                _record_attr(source_records, "debug_displayed_primary_button_contract", {})
            ),
            "debug.primary_button_contract": _button_contract_source_summary(
                _record_attr(source_records, "debug_primary_button_contract", {})
            ),
            "debug.button_contract": _button_contract_source_summary(
                _record_attr(source_records, "debug_button_contract", {})
            ),
        }
        for source_key in list(button_contract_source_precedence_order or ()):
            if _summary_matches_final(contract_lookup.get(str(source_key))):
                winning_source = str(source_key)
                source_map.setdefault(winning_source, contract_lookup.get(str(source_key)) or {})
                break

    if not winning_source:
        winning_source = "displayed_primary_item.button_contract"
        source_map.setdefault(winning_source, final_contract_summary)

    winning_contract = dict(source_map.get(winning_source) or final_contract_summary)
    final_updates = dict(final_contract.get("updates") or {})
    if not final_updates:
        final_updates = dict(displayed_item.get("selected_action_updates") or displayed_item.get("updates") or {})

    action_payload = dict(displayed_item.get("action_payload") or {})
    action_payload_summary = _cta_action_payload_summary(action_payload)
    source_labels = dict(label_map.get(winning_source) or {})

    winning_action_type = (
        displayed_item.get("action_type")
        or final_contract.get("action_type")
        or action_payload.get("action_type")
        or action_payload.get("resolved_candidate_action_type")
    )
    winning_candidate = {
        "candidate_id": displayed_item.get("candidate_id")
        or final_contract.get("candidate_id")
        or action_payload.get("candidate_id"),
        "source_candidate_id": displayed_item.get("source_candidate_id")
        or final_contract.get("source_candidate_id")
        or action_payload.get("source_candidate_id"),
        "family": displayed_item.get("family")
        or displayed_item.get("check_key")
        or final_contract.get("family")
        or action_payload.get("family")
        or action_payload.get("resolved_candidate_family_tag"),
    }
    return {
        "winning_button_contract": winning_contract,
        "winning_button_contract_source": winning_source,
        "winning_update_payload": final_updates,
        "winning_update_payload_source": str(source_labels.get("update_payload") or ""),
        "winning_action_type": winning_action_type,
        "winning_action_type_source": str(source_labels.get("action_type") or ""),
        "winning_candidate": winning_candidate,
        "winning_candidate_source": str(source_labels.get("candidate") or ""),
        "apply_enabled": bool(final_contract.get("enabled")),
        "apply_actionable": bool(final_contract.get("actionable")),
        "disabled_reason": final_contract.get("blocking_reason") or final_contract.get("disabled_reason"),
        "final_cta_action_payload_summary": action_payload_summary,
        "final_published_item_hash": str(displayed_item.get("identity_hash") or _stable_hash(displayed_item)),
        "source_candidates": source_map,
    }


__all__ = [
    "DesignGuideButtonContractSourceResolution",
    "build_design_guide_button_contract_source_resolution",
    "select_design_guide_button_contract_source_precedence",
]
