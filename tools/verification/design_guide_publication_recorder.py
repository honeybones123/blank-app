import json
import os
from datetime import datetime
from typing import Callable

from design_brain.publication import DesignGuidePublicationContext


def record_design_guide_publication_snapshot(
    resolution: dict,
    *,
    source: str,
    input_count: int,
    publication_context: DesignGuidePublicationContext | None = None,
    snapshot_hash: Callable[[object], str],
    candidate_identities: Callable[[list[dict] | None], list[str]],
    button_contract_enabled: Callable[[dict | None], bool],
) -> None:
    path = os.environ.get("DESIGN_GUIDE_PUBLICATION_SNAPSHOT_PATH", "").strip()
    if not path:
        return
    try:
        item = dict((resolution or {}).get("item") or {})
        contract = dict(item.get("button_contract") or {})
        action_payload = dict(item.get("action_payload") or {})
        candidate_payload = dict(
            item.get("resolved_candidate")
            or item.get("candidate")
            or item.get("candidate_payload")
            or {}
        )
        evidence = dict(item.get("candidate_search_evidence") or {})
        context_payload = publication_context.to_dict() if publication_context is not None else {}
        row = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "source": str(source or "").strip(),
            "input_guidance_candidates_count": int(input_count or 0),
            "context_identity": {
                "resolved_input_summary_hash": snapshot_hash(
                    context_payload.get("resolved_inputs_summary") or {}
                ),
                "shared_state_snapshot_hash": snapshot_hash(
                    context_payload.get("shared_state_snapshot") or {}
                ),
                "guidance_state_snapshot_hash": snapshot_hash(
                    context_payload.get("guidance_state_snapshot") or {}
                ),
                "overview_hash": snapshot_hash(
                    context_payload.get("current_design_overview") or {}
                ),
                "candidate_identities": candidate_identities(
                    list(context_payload.get("candidate_items") or [])
                ),
            },
            "render_reason": (resolution or {}).get("render_reason"),
            "state_fingerprint": (resolution or {}).get("state_fingerprint"),
            "selected_final_item_identity": (
                item.get("id")
                or item.get("candidate_id")
                or item.get("source_candidate_id")
                or item.get("title_main")
                or item.get("title")
            ),
            "selected_family": item.get("selected_family") or item.get("family") or item.get("check_key"),
            "published_family": item.get("published_family_id") or item.get("selected_family_id"),
            "terminal_status": item.get("design_guide_terminal_state") or item.get("status"),
            "classification": {
                "guidance_intent": item.get("guidance_intent"),
                "action_type": item.get("action_type") or contract.get("action_type"),
                "bucket": item.get("bucket"),
                "is_advisory": bool(item.get("is_advisory")),
                "is_repair": str(item.get("guidance_intent") or "").strip() == "required_fix",
                "is_optimisation": "cleanup" in str(item.get("guidance_intent") or item.get("action_type") or "").lower(),
                "is_pass": str(item.get("bucket") or item.get("status") or "").strip().lower() == "pass",
                "is_fail": str(item.get("bucket") or item.get("status") or "").strip().lower() in {"fail", "error"},
            },
            "cta": {
                "eligible": bool(button_contract_enabled(contract)),
                "reason": contract.get("blocking_reason") or item.get("blocking_reason") or item.get("cta_reason"),
                "label": item.get("primary_action") or item.get("cta_label"),
            },
            "apply_payload_identity": action_payload.get("id") or action_payload.get("payload_id") or contract.get("payload_id"),
            "apply_payload_hash": snapshot_hash(action_payload or contract.get("updates") or {}),
            "candidate_payload_identity": (
                candidate_payload.get("id")
                or candidate_payload.get("candidate_id")
                or item.get("candidate_id")
                or item.get("source_candidate_id")
            ),
            "candidate_payload_hash": snapshot_hash(candidate_payload),
            "route_owner": (
                item.get("family_route_owner")
                or evidence.get("family_route_owner")
                or dict((resolution or {}).get("debug") or {}).get("family_route_owner")
            ),
            "contract_binding_state": {
                "enabled": bool(button_contract_enabled(contract)),
                "action_type": contract.get("action_type"),
                "updates_hash": snapshot_hash(contract.get("updates") or {}),
                "blocking_reason": contract.get("blocking_reason"),
            },
            "evidence_keys_used_for_publication": sorted(str(key) for key in evidence.keys()),
            "fallback_or_promoted_item_identity": (
                item.get("fallback_item_id")
                or item.get("promoted_item_id")
                or item.get("source_candidate_id")
            ),
            "final_visible": {
                "title": item.get("title_main") or item.get("title"),
                "text": item.get("primary_action") or item.get("guidance_why") or item.get("reasoning"),
                "reasons": item.get("reasons") or item.get("guidance_reasons") or [],
            },
            "debug_keys": sorted(str(key) for key in dict((resolution or {}).get("debug") or {}).keys()),
        }
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, sort_keys=True) + "\n")
    except (OSError, TypeError, ValueError):
        return
