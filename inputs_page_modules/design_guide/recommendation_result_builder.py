"""Recommendation-result construction for Design Guide guidance items."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Callable


_RECOMMENDATION_RESULT_BUILDER_DEPENDENCIES: tuple[str, ...] = (
    "_build_pending_recommendation",
    "_ensure_guidance_item_resolved_candidate_payload",
)


def bind_recommendation_result_builder_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _RECOMMENDATION_RESULT_BUILDER_DEPENDENCIES
            if name in namespace
        }
    )


def _build_recommendation_result_from_guidance_item(
    item: dict | None,
    state: dict | None,
    *,
    branch: str | None = None,
    request_kind: str = "design_guide",
    ensure_resolved_payload: Callable[..., None] | None = None,
    build_pending_recommendation: Callable[..., dict | None] | None = None,
) -> dict | None:
    """
    Layer 3 pure: build canonical recommendation_result from one guidance item.
    Does not write session state. May deep-copy internally to avoid mutating callers' dicts.
    """
    if not isinstance(item, dict):
        return None
    base_state = dict(state or {})
    work = copy.deepcopy(item)
    ensure_payload = (
        ensure_resolved_payload
        or _ensure_guidance_item_resolved_candidate_payload
    )
    build_pending = (
        build_pending_recommendation
        or _build_pending_recommendation
    )
    ensure_payload(work, state=base_state)
    pending = build_pending(work, base_state)
    if not isinstance(pending, dict):
        return None
    updates = dict(pending.get("updates") or {})
    if not updates:
        return None
    title = str(
        work.get("canonical_winner_label")
        or pending.get("title")
        or work.get("title_main")
        or "Optimisation available",
    ).strip()
    stable = {
        "title": title,
        "updates": sorted((str(k), updates[k]) for k in sorted(updates.keys())),
    }
    recommendation_id = hashlib.sha256(
        json.dumps(stable, default=str, sort_keys=True).encode("utf-8"),
    ).hexdigest()
    action_type = str(pending.get("action_type") or "").strip()
    winner_id = hashlib.sha256(
        f"{action_type}|{recommendation_id}".encode("utf-8"),
    ).hexdigest()
    summary = str(work.get("primary_action") or "").strip() or None
    reasoning = str(work.get("reasoning") or "").strip() or None
    metrics: dict = {}
    util_val = work.get("util")
    if util_val is not None:
        try:
            metrics["util"] = float(util_val)
        except Exception:
            metrics["util"] = util_val
    if work.get("status"):
        metrics["status"] = work.get("status")
    if work.get("bucket"):
        metrics["bucket"] = work.get("bucket")
    apply_payload = dict(pending.get("action_payload") or {})
    branch_out = str(branch).strip() if isinstance(branch, str) and str(branch).strip() else None
    out_rr = {
        "recommendation_id": recommendation_id,
        "winner_id": winner_id,
        "title": title,
        "summary": summary,
        "reasoning": reasoning,
        "source": "recommendation_engine",
        "request_kind": (str(request_kind).strip() or "design_guide"),
        "branch": branch_out,
        "updates": dict(updates),
        "metrics": metrics,
        # Primary apply contract for apply_recommendation_result (mirrors pending action_type / action_payload).
        "apply": {
            "mode": action_type,
            "payload": apply_payload,
        },
    }
    if str(work.get("canonical_winner_label") or "").strip():
        out_rr["canonical_winner_label"] = str(work.get("canonical_winner_label")).strip()
    if work.get("title_locked_from_final_winner"):
        out_rr["title_locked_from_final_winner"] = True
    return out_rr


__all__ = [
    "bind_recommendation_result_builder_dependencies",
    "_build_recommendation_result_from_guidance_item",
]
