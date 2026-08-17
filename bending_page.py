"""Bending page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class BendingPageContext:
    route_slug: str = "bending"
    source: str = "bending_page"


def _runtime() -> ModuleType:
    return import_module("bending_page_runtime")


def _install_presentation_performance_policy() -> None:
    """Install Bending's presentation-only card policy before page render."""

    from engineering_page_sections.calcbox_performance import (
        install_bending_hybrid_calcbox_runtime,
    )

    install_bending_hybrid_calcbox_runtime(import_module("bending_tabs"))


def build_bending_page_context() -> BendingPageContext:
    return BendingPageContext()


def compute_bending_results(publish: bool = True) -> dict:
    """Compatibility export; calculation orchestration lives outside the shell."""

    return _runtime().compute_bending_results(publish=publish)


def render_bending_page() -> None:
    from state_and_helpers import render_timing_mark

    context = build_bending_page_context()
    render_timing_mark("bending_page.shell.setup", route=context.route_slug)
    _install_presentation_performance_policy()
    render_timing_mark("bending_page.shell.workspace.start")
    try:
        _runtime().render_bending()
    finally:
        render_timing_mark("bending_page.shell.workspace.end")


def render_bending() -> None:
    from state_and_helpers import speed_profiled

    profiled_render = speed_profiled(
        "ui_render.bending_page.render_bending",
        category="render",
    )(render_bending_page)
    profiled_render()


def __getattr__(name: str):
    """Temporary compatibility bridge for existing tests and report callers."""

    return getattr(_runtime(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime())))


__all__ = [
    "BendingPageContext",
    "build_bending_page_context",
    "compute_bending_results",
    "render_bending",
    "render_bending_page",
]
