"""Shrinkage page composition shell.

The shell owns route-level profiling and delegates the established page
workspace to :mod:`shrinkage_page_runtime`.  Engineering and publication
authority remain in the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class ShrinkagePageContext:
    route_slug: str = "shrinkage"
    source: str = "shrinkage_page"


def _runtime() -> ModuleType:
    return import_module("shrinkage_page_runtime")


def build_shrinkage_page_context() -> ShrinkagePageContext:
    return ShrinkagePageContext()


def compute_shrinkage_results(publish: bool = True) -> dict:
    """Compatibility export; calculation authority remains in the runtime."""

    return _runtime().compute_shrinkage_results(publish=publish)


def compute_shrinkage_components_for_crack_control() -> dict:
    """Compatibility export for the established Crack Control consumer."""

    return _runtime().compute_shrinkage_components_for_crack_control()


def render_shrinkage_page() -> None:
    from state_and_helpers import render_timing_mark

    context = build_shrinkage_page_context()
    render_timing_mark("shrinkage_page.shell.setup", route=context.route_slug)
    render_timing_mark("shrinkage_page.shell.workspace.start")
    try:
        _runtime().render_shrinkage()
    finally:
        render_timing_mark("shrinkage_page.shell.workspace.end")


def render_shrinkage() -> None:
    from state_and_helpers import speed_profiled

    profiled_render = speed_profiled(
        "ui_render.shrinkage_page.render_shrinkage",
        category="render",
    )(render_shrinkage_page)
    profiled_render()


def __getattr__(name: str):
    return getattr(_runtime(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime())))


__all__ = [
    "ShrinkagePageContext",
    "build_shrinkage_page_context",
    "compute_shrinkage_components_for_crack_control",
    "compute_shrinkage_results",
    "render_shrinkage",
    "render_shrinkage_page",
]
