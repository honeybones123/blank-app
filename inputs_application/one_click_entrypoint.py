"""Permanent production entrypoint for the Inputs one-click transaction."""

from __future__ import annotations

import os
import sys
from typing import Any

import streamlit as st

from inputs_application.guidance_entrypoint import (
    build_guidance_entrypoint_runtime,
)
from inputs_application.one_click_runtime_provider import (
    build_partial_one_click_runtime_provider,
    missing_one_click_runtime_dependencies,
)
from inputs_page_modules.auto_design_compute import (
    run_one_click_auto_design_coordinator,
)


def build_one_click_runtime_provider(
    *,
    st_module: Any = st,
) -> Any:
    guidance_runtime = build_guidance_entrypoint_runtime(
        st_module=st_module,
        os_module=os,
        sys_module=sys,
    )
    provider = build_partial_one_click_runtime_provider(
        st_module=st_module,
        guidance_runtime=guidance_runtime,
    )
    missing = missing_one_click_runtime_dependencies(provider)
    if missing:
        raise RuntimeError(
            "Permanent one-click provider is incomplete: "
            + ", ".join(missing)
        )
    return provider


def run_one_click_auto_design(
    *,
    trigger_fingerprint: tuple | None = None,
    entry_source: str = "inputs_handle_auto_design",
    st_module: Any = st,
    sys_module: Any = sys,
) -> dict:
    """Run one-click using only the typed permanent application provider."""
    return run_one_click_auto_design_coordinator(
        build_one_click_runtime_provider(st_module=st_module),
        st_module,
        sys_module,
        trigger_fingerprint=trigger_fingerprint,
        entry_source=entry_source,
    )


__all__ = [
    "build_one_click_runtime_provider",
    "run_one_click_auto_design",
]
