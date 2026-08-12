"""Design (SFD/BMD) page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class DesignPageContext:
    route_slug: str = "design"
    source: str = "sfd_bmd_page"


def _runtime() -> ModuleType:
    return import_module("design_page_runtime")


def build_design_page_context() -> DesignPageContext:
    return DesignPageContext()


def _render_design_workspace_fragment() -> None:
    from state_and_helpers import render_timing_mark

    context = build_design_page_context()
    render_timing_mark("design_page.shell.workspace.start")
    try:
        _runtime().render_sfd_bmd_page()
    finally:
        render_timing_mark("design_page.shell.workspace.end")


def render_sfd_bmd_page_workspace() -> None:
    from state_and_helpers import render_timing_mark

    context = build_design_page_context()
    render_timing_mark("design_page.shell.setup", route=context.route_slug)
    # Load Analysis owns its own page/runtime fragment.  Do not route it
    # through the shared Inputs fragment: that wrapper carries Inputs-page
    # workspace reconciliation and publication state, which can rehydrate
    # stale beam widgets or make Apply appear to jump between results.
    _render_design_workspace_fragment()


def render_sfd_bmd_page() -> None:
    from state_and_helpers import speed_profiled

    profiled_render = speed_profiled(
        "ui_render.design_page.render_sfd_bmd_page",
        category="render",
    )(render_sfd_bmd_page_workspace)
    profiled_render()


def __getattr__(name: str):
    if name in {
        "_clamp_x",
        "_compute_diagram_arrays",
        "_defl_support_type_from_selection",
        "_prepare_sfd_bmd_plot_state",
        "diagram_cache_fingerprint",
        "plot_sfd_bmd_plotly",
    }:
        return getattr(import_module("beam_diagram_runtime"), name)
    return getattr(_runtime(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime())))


__all__ = [
    "DesignPageContext",
    "_clamp_x",
    "_compute_diagram_arrays",
    "_defl_support_type_from_selection",
    "_prepare_sfd_bmd_plot_state",
    "build_design_page_context",
    "diagram_cache_fingerprint",
    "plot_sfd_bmd_plotly",
    "render_sfd_bmd_page",
    "render_sfd_bmd_page_workspace",
]
