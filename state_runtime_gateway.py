"""Low-level runtime gateway for legacy session-backed engineering modules.

This module deliberately imports no page, renderer, calculation core, report,
or ``state_and_helpers`` module.  The application state owner registers its
validated functions and contract collections once initialization is complete.
Consumers can then depend inward on this narrow gateway without creating a
cycle back through the high-level state/calculation orchestrator.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from typing import Any, Callable, Mapping

import streamlit as st

from calculations.design_actions import resolve_design_actions_from_state


SHARED_DEFAULTS: dict[str, Any] = {}
RESULT_KEYS: set[str] = set()
DERIVED_KEYS: set[str] = set()
TAB_KEYS: dict[str, str] = {}
NONZERO_REQUIRED_SHARED_KEYS: set[str] = set()


@dataclass(frozen=True)
class StateRuntimeBindings:
    get_param: Callable[..., Any]
    update_results: Callable[..., Any]
    get_longitudinal_row_inputs: Callable[..., Any]
    get_sync_callbacks: Callable[..., Any]
    speed_profile_record: Callable[..., Any]
    speed_profile_section: Callable[..., Any]
    resolve_widget_key: Callable[..., Any]
    zero_allowed: Callable[..., Any]
    audit: Callable[..., Any]
    mark_user_edit: Callable[..., Any]
    set_shared: Callable[..., Any]
    canonical_s_lig_raw: Callable[..., Any]
    get_canonical_s_lig: Callable[..., Any]
    get_active_s_lig_widget_value: Callable[..., Any]


_bindings: StateRuntimeBindings | None = None


def configure_state_runtime_gateway(
    bindings: StateRuntimeBindings,
    *,
    shared_defaults: Mapping[str, Any],
    result_keys: set[str],
    derived_keys: set[str],
    tab_keys: Mapping[str, str],
    nonzero_required_shared_keys: set[str],
) -> None:
    """Register the live state owner while preserving stable proxy objects."""

    global _bindings
    if not isinstance(bindings, StateRuntimeBindings):
        raise TypeError("bindings must be StateRuntimeBindings")
    SHARED_DEFAULTS.clear()
    SHARED_DEFAULTS.update(dict(shared_defaults))
    RESULT_KEYS.clear()
    RESULT_KEYS.update(set(result_keys))
    DERIVED_KEYS.clear()
    DERIVED_KEYS.update(set(derived_keys))
    TAB_KEYS.clear()
    TAB_KEYS.update(dict(tab_keys))
    NONZERO_REQUIRED_SHARED_KEYS.clear()
    NONZERO_REQUIRED_SHARED_KEYS.update(set(nonzero_required_shared_keys))
    _bindings = bindings


def state_runtime_gateway_configured() -> bool:
    return _bindings is not None


def _require_bindings() -> StateRuntimeBindings:
    if _bindings is None:
        raise RuntimeError(
            "state runtime gateway is not configured; import state_and_helpers "
            "during application composition before running session-backed cores"
        )
    return _bindings


def get_param(name: str, default: Any = None) -> Any:
    if _bindings is not None:
        return _bindings.get_param(name, default)
    value = st.session_state.get(name)
    if value is not None:
        return value
    shared_default = SHARED_DEFAULTS.get(name, default)
    return shared_default if shared_default is not None else default


def update_results(*args: Any, **kwargs: Any) -> Any:
    return _require_bindings().update_results(*args, **kwargs)


def resolve_design_actions(state: dict | None = None) -> dict:
    source = state if isinstance(state, dict) else st.session_state
    return resolve_design_actions_from_state(source)


def is_design_governing() -> bool:
    return st.session_state.get("actions_mode", "manual") == "design"


def get_longitudinal_row_inputs(
    section: str,
    source: dict | None = None,
) -> list[dict]:
    return _require_bindings().get_longitudinal_row_inputs(section, source)


def get_sync_callbacks() -> Any:
    return _require_bindings().get_sync_callbacks()


def speed_profile_record(
    name: str,
    elapsed_ms: float,
    category: str = "compute",
) -> None:
    if _bindings is not None:
        _bindings.speed_profile_record(name, elapsed_ms, category)


@contextmanager
def speed_profile_section(name: str, category: str = "compute"):
    if _bindings is None:
        yield
        return
    with _bindings.speed_profile_section(name, category):
        yield


def resolve_widget_key(widget_key: str) -> str:
    return str(_require_bindings().resolve_widget_key(widget_key))


def zero_allowed(shared_key: str) -> bool:
    return bool(_require_bindings().zero_allowed(shared_key))


def _audit(
    event: str,
    shared_key: str,
    widget_key: str = "",
    old: Any = None,
    new: Any = None,
    extra: dict | None = None,
) -> Any:
    return _require_bindings().audit(
        event,
        shared_key,
        widget_key,
        old,
        new,
        extra,
    )


def mark_user_edit(*args: Any, **kwargs: Any) -> Any:
    return _require_bindings().mark_user_edit(*args, **kwargs)


def set_shared(key: str, value: Any, *, source: str = "") -> None:
    _require_bindings().set_shared(key, value, source=source)


def canonical_s_lig_raw(state: dict) -> Any:
    return _require_bindings().canonical_s_lig_raw(state)


def get_canonical_s_lig(state: dict) -> float:
    return float(_require_bindings().get_canonical_s_lig(state))


def get_active_s_lig_widget_value(state: dict) -> tuple:
    return tuple(_require_bindings().get_active_s_lig_widget_value(state))


def _debug_log_path() -> str:
    return os.path.join(
        os.path.expanduser("~/Documents"),
        "blank_app_state_tripwire.log",
    )


__all__ = [
    "DERIVED_KEYS",
    "NONZERO_REQUIRED_SHARED_KEYS",
    "RESULT_KEYS",
    "SHARED_DEFAULTS",
    "StateRuntimeBindings",
    "TAB_KEYS",
    "_audit",
    "_debug_log_path",
    "canonical_s_lig_raw",
    "configure_state_runtime_gateway",
    "get_active_s_lig_widget_value",
    "get_canonical_s_lig",
    "get_longitudinal_row_inputs",
    "get_param",
    "get_sync_callbacks",
    "is_design_governing",
    "mark_user_edit",
    "resolve_design_actions",
    "resolve_widget_key",
    "set_shared",
    "speed_profile_record",
    "speed_profile_section",
    "state_runtime_gateway_configured",
    "update_results",
    "zero_allowed",
]
