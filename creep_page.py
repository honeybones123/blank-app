"""Creep page composition shell.

The shell owns route-level profiling and delegates the existing presentation
workspace to :mod:`creep_page_runtime`.  Keeping this module deliberately
small gives Creep the same loading boundary as Bending and Shear without
changing engineering ownership or the rendered DOM.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class CreepPageContext:
    route_slug: str = "creep"
    source: str = "creep_page"


def _runtime() -> ModuleType:
    return import_module("creep_page_runtime")


def build_creep_page_context() -> CreepPageContext:
    return CreepPageContext()


def compute_creep_results(publish: bool = True) -> dict:
    """Compatibility export; calculation authority remains in the runtime."""

    return _runtime().compute_creep_results(publish=publish)


def render_creep_page() -> None:
    from state_and_helpers import render_timing_mark

    context = build_creep_page_context()
    render_timing_mark("creep_page.shell.setup", route=context.route_slug)
    render_timing_mark("creep_page.shell.workspace.start")
    try:
        _runtime().render_creep()
    finally:
        render_timing_mark("creep_page.shell.workspace.end")


def render_creep() -> None:
    from state_and_helpers import speed_profiled

    profiled_render = speed_profiled(
        "ui_render.creep_page.render_creep",
        category="render",
    )(render_creep_page)
    profiled_render()


def __getattr__(name: str):
    return getattr(_runtime(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime())))


__all__ = [
    "CreepPageContext",
    "build_creep_page_context",
    "compute_creep_results",
    "render_creep",
    "render_creep_page",
]
