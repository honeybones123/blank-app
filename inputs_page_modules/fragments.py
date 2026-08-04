"""Small optional Streamlit fragment boundary helpers."""

from __future__ import annotations

import os
from typing import Any, Callable


_FRAGMENT_WRAPPERS: dict[
    tuple[str, Callable[..., Any]],
    Callable[..., Any],
] = {}


def run_inputs_fragment(
    *,
    st_module: Any,
    fragment_name: str,
    render_fn: Callable[..., Any],
    kwargs: dict[str, Any] | None = None,
) -> Any:
    """Run one existing renderer in a fragment when the runtime supports it."""

    payload = dict(kwargs or {})
    disabled = str(os.environ.get("CODEX_ENABLE_INPUTS_FRAGMENTS") or "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }
    fragment = getattr(st_module, "fragment", None)
    mode = "full_page_fallback"
    if callable(fragment) and not disabled:
        mode = "fragment"
        st_module.session_state[f"_inputs_{fragment_name}_fragment_mode"] = mode
        cache_key = (str(fragment_name), render_fn)
        wrapped = _FRAGMENT_WRAPPERS.get(cache_key)
        if wrapped is None:
            wrapped = fragment(render_fn)
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
    fragment = getattr(st_module, "fragment", None)
    if not callable(fragment):
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
        wrapped = fragment(run_every=max(0.1, float(run_every_s)))(render_fn)
        _FRAGMENT_WRAPPERS[cache_key] = wrapped
    st_module.session_state[f"_inputs_{fragment_name}_polling_interval_s"] = float(
        run_every_s
    )
    return wrapped(**payload)


__all__ = ["run_inputs_fragment", "run_inputs_polling_fragment"]
