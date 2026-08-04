"""Shear page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class ShearPageContext:
    route_slug: str = "shear"
    source: str = "shear_page"


def _runtime() -> ModuleType:
    return import_module("shear_page_runtime")


def build_shear_page_context() -> ShearPageContext:
    return ShearPageContext()


def compute_shear_results(publish: bool = True) -> dict:
    """Compatibility export; calculation orchestration lives outside the shell."""

    return _runtime().compute_shear_results(publish=publish)


def render_shear_page() -> None:
    from state_and_helpers import render_timing_mark

    context = build_shear_page_context()
    render_timing_mark("shear_page.shell.setup", route=context.route_slug)
    render_timing_mark("shear_page.shell.workspace.start")
    try:
        _runtime().render_shear()
    finally:
        render_timing_mark("shear_page.shell.workspace.end")


def render_shear() -> None:
    from state_and_helpers import speed_profiled

    profiled_render = speed_profiled(
        "ui_render.shear_page.render_shear",
        category="render",
    )(render_shear_page)
    profiled_render()


def __getattr__(name: str):
    return getattr(_runtime(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime())))


__all__ = [
    "ShearPageContext",
    "build_shear_page_context",
    "compute_shear_results",
    "render_shear",
    "render_shear_page",
]
