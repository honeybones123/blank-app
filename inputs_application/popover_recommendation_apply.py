"""Typed application boundary for the three Inputs recommendation popovers."""

from __future__ import annotations

from typing import Any, Callable, MutableMapping

from inputs_application.adapters import SharedStateSessionPort
from inputs_application.contracts import InputsSessionMutation
from state_and_helpers import SHARED_DEFAULTS


def bottom_arrangement_to_shared_updates(arrangement: dict[str, Any]) -> dict[str, Any]:
    """Project a bottom-bar arrangement onto the canonical shared-state fields."""

    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    return {
        "bot1_layout_mode": "Count",
        "bot1_count": count_1,
        "db_bot_1": dia_1,
        "bot2_layout_mode": "Count",
        "bot2_count": count_2,
        "db_bot_2": dia_2,
        "bot_row_count": 2 if count_2 > 0 else 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": count_1,
        "bot_row_1_spacing": 0.0,
        "bot_row_1_dia": dia_1,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": count_2,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": dia_2,
    }


def plan_popover_recommendation_mutation(
    recommendation: dict[str, Any] | None,
    *,
    kind: str,
) -> InputsSessionMutation:
    """Convert one computed popover recommendation into a typed mutation."""

    recommendation = dict(recommendation or {})
    updates = dict(recommendation.get("updates") or {})
    if kind == "bottom" and not updates:
        updates = bottom_arrangement_to_shared_updates(
            dict(recommendation.get("arrangement") or {})
        )
    shared_updates = {
        key: value
        for key, value in updates.items()
        if key in SHARED_DEFAULTS and not str(key).startswith("_")
    }
    if not shared_updates:
        return InputsSessionMutation(
            status="failed",
            reason=f"{kind}_popover_recommendation_has_no_shared_updates",
        )
    return InputsSessionMutation(
        updates=shared_updates,
        removals=("_auto_design_last_fingerprint",),
        rerun_required=True,
        status="rerun_required",
        reason=f"{kind}_popover_recommendation_planned",
    )


def execute_popover_recommendation_apply(
    *,
    kind: str,
    source: str,
    session_state: MutableMapping[str, Any],
    recommendation: dict[str, Any] | None,
    set_shared: Callable[..., None],
    finalize_publish: Callable[..., Any],
    persist_active_beam: Callable[[], Any],
    invalidate_caches: Callable[..., Any],
    rerun: Callable[[], Any],
) -> bool:
    """Recompute, commit, invalidate and rerun one recommendation transaction."""

    mutation = plan_popover_recommendation_mutation(
        recommendation,
        kind=kind,
    )
    if mutation.status == "failed":
        return False
    SharedStateSessionPort(
        session_state=session_state,
        set_shared=set_shared,
        finalize_publish=finalize_publish,
        persist_active_beam=persist_active_beam,
        source=source,
        focus_section=None,
        store_post_apply_acceptance=False,
    ).commit(mutation)
    invalidate_caches(
        reason=source,
        updated_keys=sorted(mutation.updates),
        preserve_apply_banner=False,
    )
    session_state["_popover_recommendation_apply_probe"] = {
        "kind": kind,
        "source": source,
        "status": mutation.status,
        "updates": dict(mutation.updates),
    }
    # This function is invoked by a Streamlit widget callback.  Streamlit
    # schedules the owning fragment rerun after the callback returns; calling
    # rerun() here is a no-op in deployed builds and can leave the UI showing
    # the old publication before the replacement result settles.
    return True


__all__ = [
    "bottom_arrangement_to_shared_updates",
    "execute_popover_recommendation_apply",
    "plan_popover_recommendation_mutation",
]
