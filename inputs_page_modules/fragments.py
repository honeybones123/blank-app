"""Small optional Streamlit fragment boundary helpers."""

from __future__ import annotations

import os
from typing import Any, Callable


_FRAGMENT_WRAPPERS: dict[
    tuple[str, Callable[..., Any]],
    Callable[..., Any],
] = {}
_FRAGMENT_IDS_KEY = "_inputs_fragment_ids_v1"
_FRAGMENT_WAKE_KEY = "_inputs_fragment_wake_v1"


def _current_fragment_id() -> str | None:
    """Read the active Streamlit fragment id without making it a hard dependency."""

    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            get_script_run_ctx,
            ThreadState,
        )

        # Streamlit 1.60 moved the active fragment id from ScriptRunContext to
        # FragmentThreadState.  The old context attribute is still used by
        # some supported versions, so prefer the new owner and retain the
        # compatibility fallback.
        try:
            thread_state = ThreadState.get()
            fragment_id = str(getattr(thread_state, "fragment_id", "") or "").strip()
            if fragment_id:
                return fragment_id
        except (AttributeError, RuntimeError, TypeError):
            pass
        context = get_script_run_ctx(suppress_warning=True)
        return str(getattr(context, "fragment_id", "") or "").strip() or None
    except (ImportError, AttributeError, RuntimeError, TypeError):
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


def _stop_fragment_auto_rerun(fragment_id: str | None) -> None:
    if not fragment_id:
        return
    enqueue = _framework_enqueue()
    if enqueue is None:
        return
    try:
        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

        message = ForwardMsg()
        message.stop_auto_rerun.fragment_ids.append(fragment_id)
        enqueue(message)
    except (ImportError, AttributeError, TypeError, ValueError):
        return


def _track_fragment(
    st_module: Any,
    fragment_name: str,
    render_fn: Callable[..., Any],
    **payload: Any,
) -> Any:
    """Record the fragment id and consume one-shot wake requests."""

    fragment_id = _current_fragment_id()
    if fragment_id:
        ids = dict(st_module.session_state.get(_FRAGMENT_IDS_KEY) or {})
        ids[str(fragment_name)] = fragment_id
        st_module.session_state[_FRAGMENT_IDS_KEY] = ids
    wake = dict(st_module.session_state.get(_FRAGMENT_WAKE_KEY) or {})
    started_wake = wake.get(str(fragment_name))
    started_revision = (
        started_wake.get("revision")
        if isinstance(started_wake, dict)
        else None
    )
    try:
        return render_fn(**payload)
    finally:
        # A commit can arrive while this fragment is rendering.  Reading the
        # wake map only before the render used to overwrite that newer wake in
        # the finally block, stopping the diagram one revision behind during
        # rapid edits.  Consume only the wake that started this render; leave a
        # newer revision queued so Streamlit performs the catch-up rerun.
        current_wake = dict(st_module.session_state.get(_FRAGMENT_WAKE_KEY) or {})
        pending_wake = current_wake.get(str(fragment_name))
        pending_revision = (
            pending_wake.get("revision")
            if isinstance(pending_wake, dict)
            else None
        )
        newer_pending = (
            pending_revision is not None
            and (
                started_revision is None
                or int(pending_revision) > int(started_revision)
            )
        )
        if fragment_id and str(fragment_name) in current_wake and not newer_pending:
            current_wake.pop(str(fragment_name), None)
            st_module.session_state[_FRAGMENT_WAKE_KEY] = current_wake
            _stop_fragment_auto_rerun(fragment_id)


def run_inputs_fragment(
    *,
    st_module: Any,
    fragment_name: str,
    render_fn: Callable[..., Any],
    kwargs: dict[str, Any] | None = None,
    force_fragment: bool = False,
) -> Any:
    """Run one existing renderer in a fragment when the runtime supports it."""

    payload = dict(kwargs or {})
    # The V2 Inputs page uses one deterministic page transaction.  Keep the
    # fragment path available as an explicit rollback/measurement mode, but
    # make the V2-shaped full-page path the safe product default.
    disabled = (
        not force_fragment
        and str(os.environ.get("CODEX_ENABLE_INPUTS_FRAGMENTS", "1"))
        .strip()
        .lower()
        in {"0", "false", "no", "off"}
    )
    fragment = getattr(st_module, "fragment", None)
    mode = "full_page_fallback"
    if callable(fragment) and not disabled:
        mode = "fragment"
        st_module.session_state[f"_inputs_{fragment_name}_fragment_mode"] = mode
        cache_key = (str(fragment_name), render_fn)
        wrapped = _FRAGMENT_WRAPPERS.get(cache_key)
        if wrapped is None:
            def _fragment_entry(**fragment_payload: Any) -> Any:
                return _track_fragment(
                    st_module,
                    fragment_name,
                    render_fn,
                    **fragment_payload,
                )

            wrapped = fragment(_fragment_entry)
            _FRAGMENT_WRAPPERS[cache_key] = wrapped
        return wrapped(**payload)
    st_module.session_state[f"_inputs_{fragment_name}_fragment_mode"] = mode
    return render_fn(**payload)


def run_inputs_polling_fragment(
    *,
    st_module: Any,
    fragment_name: str,
    render_fn: Callable[..., Any],
    kwargs: dict[str, Any] | None = None,
    run_every_s: float = 0.5,
) -> Any:
    """Run a revision-aware fragment on a bounded polling interval."""

    payload = dict(kwargs or {})
    disabled = str(
        os.environ.get("CODEX_ENABLE_INPUTS_FRAGMENTS", "1")
    ).strip().lower() in {"0", "false", "no", "off"}
    fragment = getattr(st_module, "fragment", None)
    if not callable(fragment) or disabled:
        st_module.session_state[
            f"_inputs_{fragment_name}_fragment_mode"
        ] = "full_page_fallback"
        return render_fn(**payload)
    st_module.session_state[
        f"_inputs_{fragment_name}_fragment_mode"
    ] = "fragment"
    cache_key = (f"polling:{fragment_name}:{float(run_every_s):g}", render_fn)
    wrapped = _FRAGMENT_WRAPPERS.get(cache_key)
    if wrapped is None:
        def _fragment_entry(**fragment_payload: Any) -> Any:
            return _track_fragment(
                st_module,
                fragment_name,
                render_fn,
                **fragment_payload,
            )

        wrapped = fragment(run_every=max(0.1, float(run_every_s)))(
            _fragment_entry
        )
        _FRAGMENT_WRAPPERS[cache_key] = wrapped
    st_module.session_state[f"_inputs_{fragment_name}_polling_interval_s"] = float(
        run_every_s
    )
    return wrapped(**payload)


def current_inputs_fragment_id(st_module: Any, fragment_name: str) -> str | None:
    ids = st_module.session_state.get(_FRAGMENT_IDS_KEY)
    if not isinstance(ids, dict):
        return None
    value = str(ids.get(str(fragment_name)) or "").strip()
    return value or None


def active_inputs_fragment_id() -> str | None:
    """Return the fragment currently executing, if this is a fragment rerun."""

    return _current_fragment_id()


def rerun_inputs_current_scope(st_module: Any) -> None:
    """Rerun the active Inputs fragment, falling back to an app rerun.

    Widget callbacks execute before the fragment body. A plain ``st.rerun``
    from one of those callbacks widens a local edit into a full-page rerun.
    The active fragment id is the authoritative signal; remembered session
    ids and environment flags are not used to choose the scope.
    """

    if _current_fragment_id():
        try:
            st_module.rerun(scope="fragment")
            return
        except (TypeError, RuntimeError):
            # Older Streamlit versions reject unsupported fragment scopes
            # with these exceptions.
            pass
        except Exception as exc:
            # During the *initial* execution of an @st.fragment body,
            # Streamlit exposes a fragment id but explicitly forbids
            # ``scope='fragment'``.  That is not a user-facing error: widen
            # this one rerun to the supported app scope.  Re-raise unrelated
            # runtime faults rather than hiding them.
            if exc.__class__.__name__ != "StreamlitAPIException":
                raise
    st_module.rerun()


def rerun_inputs_active_fragment(st_module: Any) -> None:
    """Rerun only the live Inputs fragment; never widen to app scope."""

    if not _current_fragment_id():
        raise RuntimeError("No active Inputs fragment is available for a scoped rerun")
    st_module.rerun(scope="fragment")


def request_inputs_fragment_wake(
    st_module: Any,
    fragment_name: str,
    *,
    revision: int | None = None,
    interval_s: float = 0.1,
) -> bool:
    """Wake one sibling fragment once after a committed input revision."""

    fragment_id = current_inputs_fragment_id(st_module, fragment_name)
    enqueue = _framework_enqueue()
    if fragment_id is None or enqueue is None:
        return False
    try:
        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

        message = ForwardMsg()
        message.auto_rerun.interval = max(0.1, float(interval_s))
        message.auto_rerun.fragment_id = fragment_id
        enqueue(message)
    except (ImportError, AttributeError, TypeError, ValueError):
        return False
    wake = dict(st_module.session_state.get(_FRAGMENT_WAKE_KEY) or {})
    wake[str(fragment_name)] = {
        "revision": int(revision) if revision is not None else None,
    }
    st_module.session_state[_FRAGMENT_WAKE_KEY] = wake
    st_module.session_state[f"_inputs_{fragment_name}_polling_state"] = {
        "active": True,
        "last_action": "woken",
        "last_reason": "input_transaction",
        "last_revision": int(revision) if revision is not None else None,
    }
    return True


def stop_inputs_fragment_polling(
    st_module: Any,
    fragment_name: str,
    *,
    reason: str = "matching_revision_ready",
    revision: int | None = None,
) -> bool:
    """Stop a polling fragment after its requested revision is terminal.

    The next widget transaction calls :func:`request_inputs_fragment_wake`,
    so a stopped calculation fragment never needs a background timer just to
    discover that nothing changed.
    """

    fragment_id = current_inputs_fragment_id(st_module, fragment_name)
    if fragment_id is None:
        return False
    _stop_fragment_auto_rerun(fragment_id)
    st_module.session_state[f"_inputs_{fragment_name}_polling_state"] = {
        "active": False,
        "last_action": "stopped",
        "last_reason": str(reason),
        "last_revision": int(revision) if revision is not None else None,
    }
    return True


__all__ = [
    "current_inputs_fragment_id",
    "request_inputs_fragment_wake",
    "rerun_inputs_active_fragment",
    "rerun_inputs_current_scope",
    "run_inputs_fragment",
    "run_inputs_polling_fragment",
    "stop_inputs_fragment_polling",
]
