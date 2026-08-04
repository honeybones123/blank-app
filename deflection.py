"""Deflection page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class DeflectionPageContext:
    route_slug: str = "deflection"
    source: str = "deflection"


def _runtime() -> ModuleType:
    return import_module("deflection_page_runtime")


def build_deflection_page_context() -> DeflectionPageContext:
    return DeflectionPageContext()


def render_deflection_page() -> None:
    from state_and_helpers import render_timing_mark

    context = build_deflection_page_context()
    render_timing_mark("deflection_page.shell.setup", route=context.route_slug)
    render_timing_mark("deflection_page.shell.workspace.start")
    try:
        _runtime().render_deflection()
    finally:
        render_timing_mark("deflection_page.shell.workspace.end")


def render_deflection() -> None:
    from state_and_helpers import speed_profiled

    profiled_render = speed_profiled(
        "ui_render.deflection_page.render_deflection",
        category="render",
    )(render_deflection_page)
    profiled_render()


def __getattr__(name: str):
    if name in {
        "_deflection_support_options_for_value",
        "_derive_equiv_udl_from_actions",
        "_governing_span_support_pair",
        "_support_props",
        "compute_and_store_multispan_deflection_metrics",
        "deflection_has_service_load_for_calc",
        "get_deflection_diagram_support_condition",
        "get_resolved_deflection_support_type",
    }:
        return getattr(import_module("deflection_support"), name)
    return getattr(_runtime(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime())))


__all__ = [
    "DeflectionPageContext",
    "_deflection_support_options_for_value",
    "_derive_equiv_udl_from_actions",
    "_governing_span_support_pair",
    "_support_props",
    "build_deflection_page_context",
    "compute_and_store_multispan_deflection_metrics",
    "deflection_has_service_load_for_calc",
    "get_deflection_diagram_support_condition",
    "get_resolved_deflection_support_type",
    "render_deflection",
    "render_deflection_page",
]
