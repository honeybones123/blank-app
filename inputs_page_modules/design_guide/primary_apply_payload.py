"""Primary Design Guide Apply payload assembly."""

from __future__ import annotations

from typing import Any


_PRIMARY_APPLY_PAYLOAD_DEPENDENCIES: tuple[str, ...] = (
    "_design_guide_apply_updates_current_state_guard",
    "_design_guide_button_contract_enabled",
    "_design_guide_primary_apply_state_fingerprint",
    "_guidance_item_family",
    "_guidance_item_source_candidate_id",
    "_normalise_design_guide_candidate_id",
    "_resolve_recommendation_updates",
    "stable_fingerprint_for_payload",
)


def bind_primary_apply_payload_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRIMARY_APPLY_PAYLOAD_DEPENDENCIES
            if name in namespace
        }
    )


def _build_design_guide_primary_apply_payload(
    *,
    item: dict,
    rec: dict,
    button_contract: dict,
    state: dict,
) -> dict:
    contract = dict(button_contract or {})
    updates = dict(contract.get("updates") or {})
    action_type = str(contract.get("action_type") or "").strip()
    family = str(contract.get("family") or _guidance_item_family(item) or rec.get("family") or "").strip()
    if not (_design_guide_button_contract_enabled(contract) and action_type == "apply_resolved_candidate" and updates):
        return {}
    visible_updates = dict(_resolve_recommendation_updates(dict(item or {}), state=state) or updates)
    current_state_apply_guard = _design_guide_apply_updates_current_state_guard(state, updates)
    if not current_state_apply_guard.get("pass"):
        return {}
    candidate_id = _normalise_design_guide_candidate_id(
        _guidance_item_source_candidate_id(item),
        contract.get("source_candidate_id"),
        contract.get("candidate_id"),
        rec.get("source_candidate_id"),
        rec.get("candidate_id"),
        family=family,
        updates=updates,
    )
    state_fp = _design_guide_primary_apply_state_fingerprint(state)
    payload = {
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "action_type": action_type,
        "family": family,
        "updates": dict(updates),
        "visible_updates": dict(visible_updates),
        "button_contract_updates": dict(updates),
        "preview_status": "PASS" if contract.get("preview_pass") is True else "FAIL",
        "preview_pass": bool(contract.get("preview_pass")),
        "expected_util": contract.get("expected_util"),
        "label": str(
            contract.get("label")
            or item.get("title_main")
            or item.get("title")
            or rec.get("title")
            or rec.get("label")
            or "Apply recommendation"
        ).strip(),
        "source": "design_guide_primary_render",
        "render_fingerprint": str(
            stable_fingerprint_for_payload(
                {
                    "candidate_id": candidate_id,
                    "action_type": action_type,
                    "family": family,
                    "updates": dict(updates),
                    "state_fingerprint": state_fp,
                }
            )
        ),
        "state_fingerprint": state_fp,
    }
    return payload
