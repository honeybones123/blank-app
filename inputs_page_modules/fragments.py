"""Small optional Streamlit fragment boundary helpers."""

from __future__ import annotations

import os
from typing import Any, Callable


_FRAGMENT_WRAPPERS: dict[
    tuple[str, Callable[..., Any]],
    Callable[..., Any],
] = {}
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


def _track_fragment(
    st_module: Any,
    fragment_name: str,
    render_fn: Callable[..., Any],
    **payload: Any,
) -> Any:
    """Render inside the fragment that Streamlit already owns."""

    del st_module, fragment_name
    return render_fn(**payload)


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


def rerun_inputs_app_scope(st_module: Any) -> None:
    """Request an intentional app-wide refresh through the shared boundary."""

    try:
        st_module.rerun(scope="app")
    except TypeError:
        # Compatibility with Streamlit versions predating scoped reruns.
        st_module.rerun()


__all__ = [
    "rerun_inputs_app_scope",
    "rerun_inputs_current_scope",
    "run_inputs_fragment",
]
