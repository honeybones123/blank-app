"""Small session-owned Apply trace primitives."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, MutableMapping
import uuid

from inputs_application.policy_constants import DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY


DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY = "_design_guide_apply_trace_run_id"
DESIGN_GUIDE_APPLY_TRACE_META_KEY = "_design_guide_apply_trace_meta"


def begin_design_guide_apply_trace(
    session_state: MutableMapping[str, Any],
    *,
    recommendation: dict | None,
    source: str,
    append_trace: Callable[..., Any],
) -> str | None:
    if not isinstance(recommendation, dict):
        return None
    run_id = f"dgapply_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:10]}"
    action_type = str(
        recommendation.get("action_type")
        or recommendation.get("_source")
        or "apply_recommendation"
    ).strip() or "apply_recommendation"
    meta = {
        "run_id": run_id,
        "source": str(source or "design_guide_apply").strip() or "design_guide_apply",
        "action_type": action_type,
        "title": str(recommendation.get("title") or "").strip(),
        "starting_worst_util": None,
    }
    session_state[DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY] = run_id
    session_state[DESIGN_GUIDE_APPLY_TRACE_META_KEY] = dict(meta)
    append_trace(
        "run_start",
        dict(meta),
        run_id=run_id,
        source=meta["source"],
    )
    return run_id


def end_design_guide_apply_trace(
    session_state: MutableMapping[str, Any],
    *,
    stop_reason: str,
    append_trace: Callable[..., Any],
    final_updates: dict | None = None,
    winner_label: str | None = None,
    **_: Any,
) -> None:
    run_id = str(
        session_state.pop(DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY, "")
        or f"dgapply_recovered_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:10]}"
    )
    meta = dict(session_state.pop(DESIGN_GUIDE_APPLY_TRACE_META_KEY, {}) or {})
    updates = dict(final_updates or {})
    last_apply_route = dict(
        session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}
    )
    applied_updates = dict(last_apply_route.get("applied_updates") or {})
    applied_updates_cover_trace = bool(updates) and all(
        key in applied_updates and applied_updates[key] == value
        for key, value in updates.items()
    )
    typed_apply_preverified = bool(
        str(stop_reason or "").strip() == "typed_apply_committed"
        and updates
        and last_apply_route.get("typed_apply_canonical_candidate_preverified")
        is True
        and last_apply_route.get("post_apply_all_key_pass") is True
        and last_apply_route.get("post_apply_any_fail") is False
        and last_apply_route.get("payload_binding_match") is True
        and last_apply_route.get("payload_update_match") is True
        and applied_updates_cover_trace
    )
    preview_worst_util = last_apply_route.get("post_apply_preview_worst_util")
    typed_statuses = (
        {"canonical_candidate_preverified": "PASS"}
        if typed_apply_preverified
        else {}
    )
    append_trace(
        "run_end",
        {
            "status": "pass" if updates else "no_action",
            "stop_reason": str(stop_reason or "apply_recommendation"),
            "winner_label": str(winner_label or meta.get("title") or "Apply recommendation"),
            "final_updates": updates,
            "final_live_worst_util": preview_worst_util,
            "post_commit_live_worst_util": preview_worst_util,
            "post_commit_live_statuses": typed_statuses,
            "all_key_pass": typed_apply_preverified,
            "typed_apply_commit_proof": {
                "proven": typed_apply_preverified,
                "candidate_preverified": last_apply_route.get(
                    "typed_apply_canonical_candidate_preverified"
                )
                is True,
                "payload_binding_match": last_apply_route.get(
                    "payload_binding_match"
                )
                is True,
                "payload_update_match": last_apply_route.get(
                    "payload_update_match"
                )
                is True,
                "applied_updates_match_trace": applied_updates_cover_trace,
            },
            "current_overview": {
                "all_key_pass": typed_apply_preverified,
                "any_fail": not typed_apply_preverified,
                "worst_util": preview_worst_util,
                "proof_source": (
                    "canonical_preverified_typed_apply"
                    if typed_apply_preverified
                    else None
                ),
            },
            "last_apply_route": last_apply_route,
            "compare": {
                "run_id": run_id,
                "action_signature": meta.get("action_type"),
                "goal": "design_guide_apply",
                "starting_worst_util": meta.get("starting_worst_util"),
                "ending_worst_util": None,
                "stop_reason": str(stop_reason or "apply_recommendation"),
                "winner_label": str(winner_label or meta.get("title") or "Apply recommendation"),
                "final_updates": updates,
            },
        },
        run_id=run_id,
        source=str(meta.get("source") or "design_guide_apply"),
    )


def set_design_guide_live_breadcrumb(
    session_state: MutableMapping[str, Any],
    label: str,
    extra: dict | None = None,
) -> None:
    session_state["_dg_live_breadcrumb"] = {
        "label": str(label),
        "extra": dict(extra or {}),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


__all__ = [
    "DESIGN_GUIDE_APPLY_TRACE_META_KEY",
    "DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY",
    "begin_design_guide_apply_trace",
    "end_design_guide_apply_trace",
    "set_design_guide_live_breadcrumb",
]
