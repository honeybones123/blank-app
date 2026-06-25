import json
import os
from datetime import datetime
from typing import Any, Callable

from design_brain.publication import DesignGuideApplyButtonBindingResult


def record_design_guide_apply_button_contract_snapshot(
    *,
    source: str,
    input_items: list,
    output_items: list[dict],
    input_hashes_before: list[str],
    input_object_ids: list[int],
    state: dict,
    primary_blocking_reason: str | None,
    binding_result: DesignGuideApplyButtonBindingResult | None = None,
    snapshot_hash: Callable[[object], str],
    button_contract_enabled: Callable[[dict | None], bool],
    primary_apply_state_fingerprint: Callable[[dict | None], str],
) -> None:
    path = os.environ.get("DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH", "").strip()
    if not path:
        return

    def _item_identity(item: dict | None, index: int) -> str:
        if not isinstance(item, dict):
            return f"non_dict_{index}"
        identity = (
            item.get("id")
            or item.get("candidate_id")
            or item.get("source_candidate_id")
            or item.get("title_main")
            or item.get("title")
            or f"item_{index}"
        )
        return str(identity)

    def _payload_identity(payload: dict | None, fallback: str | None = None) -> str | None:
        if not isinstance(payload, dict):
            return fallback
        value = (
            payload.get("id")
            or payload.get("payload_id")
            or payload.get("candidate_id")
            or payload.get("source_candidate_id")
            or fallback
        )
        return str(value) if value not in (None, "") else None

    def _item_snapshot(item: dict | None, index: int) -> dict:
        if not isinstance(item, dict):
            return {"index": index, "identity": _item_identity(item, index), "is_dict": False}
        contract = dict(item.get("button_contract") or {})
        action_payload = dict(item.get("action_payload") or {})
        candidate_payload = dict(
            item.get("resolved_candidate")
            or item.get("candidate")
            or item.get("candidate_payload")
            or {}
        )
        disabled_reason = (
            contract.get("disabled_reason")
            or contract.get("blocking_reason")
            or item.get("blocking_reason")
            or item.get("cta_reason")
        )
        selected_family = item.get("selected_family") or item.get("family") or item.get("check_key")
        return {
            "index": index,
            "identity": _item_identity(item, index),
            "is_dict": True,
            "hash": snapshot_hash(item),
            "keys": sorted(str(key) for key in item.keys()),
            "selected_family": selected_family,
            "published_family": item.get("published_family_id") or item.get("selected_family_id"),
            "apply_family": (
                item.get("selected_action_family")
                or action_payload.get("family")
                or contract.get("family")
                or selected_family
            ),
            "cta_label": item.get("primary_action") or item.get("cta_label") or contract.get("label"),
            "cta_enabled": bool(button_contract_enabled(contract)),
            "cta_reason": disabled_reason,
            "button_contract_enabled": bool(button_contract_enabled(contract)),
            "disabled_reason": disabled_reason,
            "button_contract_action_type": contract.get("action_type"),
            "button_contract_keys": sorted(str(key) for key in contract.keys()),
            "button_contract_hash": snapshot_hash(contract),
            "button_contract_updates_hash": snapshot_hash(contract.get("updates") or {}),
            "apply_payload_identity": _payload_identity(action_payload, _payload_identity(contract)),
            "apply_payload_hash": snapshot_hash(action_payload or contract.get("updates") or {}),
            "candidate_payload_identity": _payload_identity(
                candidate_payload,
                _item_identity(item, index),
            ),
            "candidate_payload_hash": snapshot_hash(candidate_payload),
            "state_fingerprint": item.get("state_fingerprint")
            or item.get("final_visible_state_fingerprint")
            or contract.get("state_fingerprint"),
            "debug_keys": sorted(
                str(key)
                for key in item.keys()
                if "debug" in str(key).lower() or "contract" in str(key).lower()
            ),
        }

    try:
        input_after_hashes = [
            snapshot_hash(item) if isinstance(item, dict) else snapshot_hash(str(item))
            for item in input_items
        ]
        before_snapshots = [
            _item_snapshot(item, index)
            for index, item in enumerate(input_items)
            if isinstance(item, dict)
        ]
        after_snapshots = [
            _item_snapshot(item, index)
            for index, item in enumerate(output_items)
            if isinstance(item, dict)
        ]
        added_fields_by_item: list[dict] = []
        for index, after in enumerate(after_snapshots):
            before_keys = set(before_snapshots[index].get("keys") or []) if index < len(before_snapshots) else set()
            after_keys = set(after.get("keys") or [])
            added_fields_by_item.append(
                {
                    "index": index,
                    "identity": after.get("identity"),
                    "added_keys": sorted(after_keys - before_keys),
                    "contract_or_debug_keys": list(after.get("debug_keys") or []),
                }
            )
        same_object_indices = [
            index
            for index, item in enumerate(output_items)
            if index < len(input_object_ids) and isinstance(item, dict) and id(item) == input_object_ids[index]
        ]
        primary_after = after_snapshots[0] if after_snapshots else {}
        row = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "source": str(source or "").strip(),
            "typed_binding_result": (
                binding_result.to_dict()
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else {}
            ),
            "input_item_count": len(input_items),
            "output_item_count": len(output_items),
            "input_item_identities": [
                _item_identity(item, index) for index, item in enumerate(input_items)
            ],
            "output_item_identities": [
                _item_identity(item, index) for index, item in enumerate(output_items)
            ],
            "item_ids_before": [
                _item_identity(item, index) for index, item in enumerate(input_items)
            ],
            "item_ids_after": [
                _item_identity(item, index) for index, item in enumerate(output_items)
            ],
            "input_hashes_before": list(input_hashes_before),
            "input_hashes_after_call": input_after_hashes,
            "input_items_mutated_in_place": input_after_hashes != list(input_hashes_before),
            "output_reuses_input_object": bool(same_object_indices),
            "same_object_indices": same_object_indices,
            "primary_blocking_reason": primary_blocking_reason,
            "selected_family": primary_after.get("selected_family"),
            "published_family": primary_after.get("published_family"),
            "apply_family": primary_after.get("apply_family"),
            "cta_label": primary_after.get("cta_label"),
            "cta_enabled": primary_after.get("cta_enabled"),
            "cta_reason": primary_after.get("cta_reason"),
            "button_contract_enabled": primary_after.get("button_contract_enabled"),
            "disabled_reason": primary_after.get("disabled_reason"),
            "state_fingerprint": primary_apply_state_fingerprint(state or {}),
            "apply_payload_identity": primary_after.get("apply_payload_identity"),
            "apply_payload_hash": primary_after.get("apply_payload_hash"),
            "candidate_payload_identity": primary_after.get("candidate_payload_identity"),
            "candidate_payload_hash": primary_after.get("candidate_payload_hash"),
            "items_before": before_snapshots,
            "items_after": after_snapshots,
            "contract_debug_data_added_to_items": added_fields_by_item,
            "button_contract_inputs": (
                [item.to_dict() for item in binding_result.button_contract_inputs]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_results": (
                [item.to_dict() for item in binding_result.button_contract_results]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_scalars": (
                [item.to_dict() for item in binding_result.button_contract_scalars]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_probe_inputs": (
                [item.to_dict() for item in binding_result.button_contract_actionability_probe_inputs]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_probe_outputs": (
                [item.to_dict() for item in binding_result.button_contract_actionability_probe_outputs]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_resolutions": (
                [item.to_dict() for item in binding_result.button_contract_actionability_resolutions]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_helper_outputs": (
                [item.to_dict() for item in binding_result.button_contract_actionability_helper_outputs]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_inputs": (
                [item.to_dict() for item in binding_result.button_contract_actionability_inputs]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_predicates": (
                [item.to_dict() for item in binding_result.button_contract_actionability_predicates]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_applications": (
                [item.to_dict() for item in binding_result.button_contract_actionability_applications]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_actionability_decisions": (
                [item.to_dict() for item in binding_result.button_contract_actionability_decisions]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_update_resolution_inputs": (
                [item.to_dict() for item in binding_result.button_contract_update_resolution_inputs]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_update_resolution_decisions": (
                [item.to_dict() for item in binding_result.button_contract_update_resolution_decisions]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_update_resolutions": (
                [item.to_dict() for item in binding_result.button_contract_update_resolutions]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "button_contract_work_mutations": (
                [item.to_dict() for item in binding_result.button_contract_work_mutations]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "promotion_decisions": (
                [decision.to_dict() for decision in binding_result.promotion_decisions]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
            "safe_executor_evidence_rows": (
                [row.to_dict() for row in binding_result.safe_executor_evidence_rows]
                if isinstance(binding_result, DesignGuideApplyButtonBindingResult)
                else []
            ),
        }
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, sort_keys=True) + "\n")
    except (OSError, TypeError, ValueError):
        return
