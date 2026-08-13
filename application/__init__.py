"""Application-layer orchestration helpers for the Streamlit app.

The package exports remain available for compatibility, but are resolved
lazily.  Importing an application-owned contract must never initialize the
concrete Design Brain, presentation adapters, or session-state stores.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_EXPORTS = {
    "AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY": (
        "application.design_result_store",
        "AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY",
    ),
    "AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY": (
        "application.design_result_store",
        "AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY",
    ),
    "AuthoritativeDesignResultStore": (
        "application.design_result_store",
        "AuthoritativeDesignResultStore",
    ),
    "DesignResultReuseDecision": (
        "application.design_result_store",
        "DesignResultReuseDecision",
    ),
    "ensure_design_result": (
        "application.design_run_coordinator",
        "ensure_design_result",
    ),
    "ApplyCommandResult": ("application.apply_command", "ApplyCommandResult"),
    "execute_apply_command": ("application.apply_command", "execute_apply_command"),
    "guidance_payload_from_authoritative_design_result": (
        "application.guidance_result_adapter",
        "guidance_payload_from_authoritative_design_result",
    ),
    "DESIGN_ACTION_INPUT_KEYS": (
        "application.engineering_snapshot",
        "DESIGN_ACTION_INPUT_KEYS",
    ),
    "DESIGN_SETTING_INPUT_KEYS": (
        "application.engineering_snapshot",
        "DESIGN_SETTING_INPUT_KEYS",
    ),
    "GEOMETRY_INPUT_KEYS": (
        "application.engineering_snapshot",
        "GEOMETRY_INPUT_KEYS",
    ),
    "MATERIAL_INPUT_KEYS": (
        "application.engineering_snapshot",
        "MATERIAL_INPUT_KEYS",
    ),
    "REINFORCEMENT_INPUT_KEYS": (
        "application.engineering_snapshot",
        "REINFORCEMENT_INPUT_KEYS",
    ),
    "build_engineering_input_snapshot_from_resolved_state": (
        "application.engineering_snapshot",
        "build_engineering_input_snapshot_from_resolved_state",
    ),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
