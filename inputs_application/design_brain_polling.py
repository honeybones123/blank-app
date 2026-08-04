"""Triggered polling lifecycle for the Inputs Design Brain fragment.

Streamlit's public fragment API can create a periodic fragment timer, but it
does not currently expose a public way for a sibling widget fragment to wake
that timer or for the Design Brain fragment to stop it after publication.  The
small, capability-checked adapter below contains that framework-specific edge.
Application code deals only in start/stop operations and revisioned probes.
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any


DESIGN_BRAIN_POLLING_STATE_KEY = "_inputs_design_brain_polling_state_v1"
DEFAULT_DESIGN_BRAIN_POLL_INTERVAL_S = 1.0
INITIAL_DESIGN_BRAIN_WAKE_INTERVAL_S = 0.1


def _current_fragment_id() -> str | None:
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            ThreadState,
        )

        return str(ThreadState.get().fragment_id or "").strip() or None
    except (ImportError, RuntimeError, AttributeError):
        return None


def _framework_enqueue() -> Callable[[Any], None] | None:
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            get_script_run_ctx,
        )

        context = get_script_run_ctx(suppress_warning=True)
        return context.enqueue if context is not None else None
    except (ImportError, AttributeError, TypeError):
        return None


def _record(
    session_state: MutableMapping[str, Any],
    *,
    fragment_id: str | None,
    active: bool,
    action: str,
    reason: str,
    revision: int | None,
    supported: bool,
) -> dict[str, Any]:
    value = {
        "fragment_id": fragment_id,
        "active": bool(active),
        "last_action": str(action),
        "last_reason": str(reason),
        "last_revision": int(revision) if revision is not None else None,
        "supported": bool(supported),
    }
    session_state[DESIGN_BRAIN_POLLING_STATE_KEY] = value
    return value


def register_design_brain_fragment(
    session_state: MutableMapping[str, Any],
    *,
    fragment_id: str | None = None,
    revision: int | None = None,
) -> str | None:
    """Remember the Design Brain fragment target on each fragment execution."""

    resolved_id = str(fragment_id or _current_fragment_id() or "").strip() or None
    prior = dict(session_state.get(DESIGN_BRAIN_POLLING_STATE_KEY) or {})
    if resolved_id is None:
        _record(
            session_state,
            fragment_id=str(prior.get("fragment_id") or "").strip() or None,
            active=bool(prior.get("active", False)),
            action="register_unavailable",
            reason="not_running_inside_fragment",
            revision=revision,
            supported=False,
        )
        return None
    # A run_every fragment schedules its next tick immediately before its body
    # executes. Mark it active here; a terminal branch below will cancel it.
    _record(
        session_state,
        fragment_id=resolved_id,
        active=True,
        action="registered",
        reason="fragment_execution",
        revision=revision,
        supported=True,
    )
    return resolved_id


def start_design_brain_polling(
    session_state: MutableMapping[str, Any],
    *,
    reason: str,
    revision: int | None = None,
    interval_s: float = DEFAULT_DESIGN_BRAIN_POLL_INTERVAL_S,
    enqueue: Callable[[Any], None] | None = None,
) -> bool:
    """Wake the registered fragment after a new input transaction."""

    prior = dict(session_state.get(DESIGN_BRAIN_POLLING_STATE_KEY) or {})
    fragment_id = str(prior.get("fragment_id") or "").strip() or None
    target_enqueue = enqueue or _framework_enqueue()
    if fragment_id is None or target_enqueue is None:
        _record(
            session_state,
            fragment_id=fragment_id,
            active=bool(prior.get("active", False)),
            action="start_unavailable",
            reason=reason,
            revision=revision,
            supported=False,
        )
        return False
    try:
        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

        message = ForwardMsg()
        message.auto_rerun.interval = max(0.1, float(interval_s))
        message.auto_rerun.fragment_id = fragment_id
        target_enqueue(message)
    except (ImportError, AttributeError, TypeError, ValueError):
        _record(
            session_state,
            fragment_id=fragment_id,
            active=bool(prior.get("active", False)),
            action="start_unavailable",
            reason=reason,
            revision=revision,
            supported=False,
        )
        return False
    _record(
        session_state,
        fragment_id=fragment_id,
        active=True,
        action="started",
        reason=reason,
        revision=revision,
        supported=True,
    )
    return True


def stop_design_brain_polling(
    session_state: MutableMapping[str, Any],
    *,
    reason: str,
    revision: int | None = None,
    enqueue: Callable[[Any], None] | None = None,
) -> bool:
    """Cancel future ticks when the target revision reaches a terminal state."""

    prior = dict(session_state.get(DESIGN_BRAIN_POLLING_STATE_KEY) or {})
    fragment_id = str(prior.get("fragment_id") or "").strip() or None
    target_enqueue = enqueue or _framework_enqueue()
    if fragment_id is None or target_enqueue is None:
        _record(
            session_state,
            fragment_id=fragment_id,
            active=bool(prior.get("active", True)),
            action="stop_unavailable",
            reason=reason,
            revision=revision,
            supported=False,
        )
        return False
    try:
        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

        message = ForwardMsg()
        message.stop_auto_rerun.fragment_ids.append(fragment_id)
        target_enqueue(message)
    except (ImportError, AttributeError, TypeError, ValueError):
        _record(
            session_state,
            fragment_id=fragment_id,
            active=bool(prior.get("active", True)),
            action="stop_unavailable",
            reason=reason,
            revision=revision,
            supported=False,
        )
        return False
    _record(
        session_state,
        fragment_id=fragment_id,
        active=False,
        action="stopped",
        reason=reason,
        revision=revision,
        supported=True,
    )
    return True


__all__ = [
    "DEFAULT_DESIGN_BRAIN_POLL_INTERVAL_S",
    "INITIAL_DESIGN_BRAIN_WAKE_INTERVAL_S",
    "DESIGN_BRAIN_POLLING_STATE_KEY",
    "register_design_brain_fragment",
    "start_design_brain_polling",
    "stop_design_brain_polling",
]
