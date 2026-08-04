"""Crack-control page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class CrackPageContext:
    route_slug: str = "crack"
    source: str = "crack_page"


def _runtime() -> ModuleType:
    return import_module("crack_page_runtime")


def build_crack_page_context() -> CrackPageContext:
    return CrackPageContext()


def render_crack_page_workspace() -> None:
    from state_and_helpers import render_timing_mark

    context = build_crack_page_context()
    render_timing_mark("crack_page.shell.setup", route=context.route_slug)
    render_timing_mark("crack_page.shell.workspace.start")
    try:
        _runtime().render_crack()
    finally:
        render_timing_mark("crack_page.shell.workspace.end")


def render_crack() -> None:
    from state_and_helpers import speed_profiled

    profiled_render = speed_profiled(
        "ui_render.crack_page.render_crack",
        category="render",
    )(render_crack_page_workspace)
    profiled_render()


def render_crack_control() -> None:
    render_crack()


def render_crack_page() -> None:
    render_crack()


def __getattr__(name: str):
    if name in {
        "_nearest_key",
        "calc_eps_diff",
        "calc_sr_max",
        "table_sigma_max_A",
        "table_sigma_max_B",
    }:
        return getattr(import_module("calculations.crack_control"), name)
    return getattr(_runtime(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime())))


__all__ = [
    "CrackPageContext",
    "_nearest_key",
    "build_crack_page_context",
    "calc_eps_diff",
    "calc_sr_max",
    "render_crack",
    "render_crack_control",
    "render_crack_page",
    "render_crack_page_workspace",
    "table_sigma_max_A",
    "table_sigma_max_B",
]
