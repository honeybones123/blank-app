"""Live Inputs page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import streamlit as st

from inputs_page_modules.calculations import (
    build_inputs_calculation_explainer_source_hash,
    build_inputs_calculation_explainer_source_snapshot,
    build_inputs_calculation_explainer_view_model,
)
from inputs_page_modules.diagrams import build_inputs_diagram_view_model
from inputs_page_modules.landing import (
    inputs_has_design_actions_or_loads,
    render_inputs_landing_card as _render_inputs_landing_card,
)
from inputs_page_route_coordinators import (
    make_beam_3d_figure,
    make_summary_cross_section_figure,
    render_inputs_page_setup_current_coordinator,
    render_inputs_summary_pipeline_current_coordinator,
    render_inputs_tail_current_coordinator,
    render_inputs_widget_sections_current_coordinator,
)
from inputs_page_modules.session import build_inputs_session_source_snapshot
from inputs_page_modules.summaries import build_inputs_summary_view_model
from inputs_page_modules.widgets import build_inputs_widget_group_view_model
from state_and_helpers import render_timing_mark, speed_profiled


@dataclass(frozen=True)
class InputsPageSnapshot:
    """Thin shell snapshot boundary; it owns no engineering calculations."""

    session: Any = None
    source: str = "inputs_page"


@dataclass(frozen=True)
class InputsPageViewModel:
    """Named section handles for the future composed page."""

    summaries: Any = None
    batch_design: Any = None
    design_guide: Any = None
    diagrams: Any = None
    calculations: Any = None


def build_inputs_page_snapshot(session: Any = None) -> InputsPageSnapshot:
    return InputsPageSnapshot(session=session)


def build_inputs_page_view_model(page_snapshot: InputsPageSnapshot | None = None) -> InputsPageViewModel:
    _ = page_snapshot
    return InputsPageViewModel()


def render_inputs_landing_card(*, sync_callbacks: dict | None = None) -> None:
    _render_inputs_landing_card(sync_callbacks=sync_callbacks, st_module=st)


def render_inputs_page() -> None:
    """Future Inputs entry point.

    The shell owns route-order composition. The section coordinators are still
    bridged while their remaining dependencies are moved out of the old page.
    """

    ss = st.session_state

    render_timing_mark("inputs_page.shell.setup.start")
    page_context = render_inputs_page_setup_current_coordinator(ss=ss)
    render_timing_mark("inputs_page.shell.setup.end")
    render_timing_mark("inputs_page.shell.widgets.start")
    skip_active_beam_record_write = render_inputs_widget_sections_current_coordinator(
        ss=ss,
        inputs_detailed_mode=page_context["inputs_detailed_mode"],
        sync_callbacks=page_context["sync_callbacks"],
        inputs_render_audit=page_context["inputs_render_audit"],
        fast_focus_section=page_context["fast_focus_section"],
        fast_get_param=page_context["fast_get_param"],
        corrected_invalid_shear_state=page_context["corrected_invalid_shear_state"],
        mark=page_context["mark"],
        sub_mark=page_context["sub_mark"],
    )
    render_timing_mark("inputs_page.shell.widgets.end")

    render_timing_mark("inputs_page.shell.summary.start")
    render_inputs_summary_pipeline_current_coordinator(
        ss=ss,
        summary_container=page_context["summary_container"],
        sync_callbacks=page_context["sync_callbacks"],
        skip_active_beam_record_write=skip_active_beam_record_write,
        mark=page_context["mark"],
    )
    render_timing_mark("inputs_page.shell.summary.end")

    render_timing_mark("inputs_page.shell.tail.start")
    render_inputs_tail_current_coordinator(
        inputs_render_audit=page_context["inputs_render_audit"],
        before_state=page_context["before_state"],
        mark=page_context["mark"],
        perf_start=page_context["perf_start"],
        perf_marks=page_context["perf_marks"],
        sub_marks=page_context["sub_marks"],
        t0=page_context["t0"],
    )
    render_timing_mark("inputs_page.shell.tail.end")


render_inputs = speed_profiled(
    "ui_render.inputs_page.render_inputs",
    category="render",
)(render_inputs_page)


EXTRACTED_MODULE_BOUNDARIES: dict[str, Callable[..., Any]] = {
    "session": build_inputs_session_source_snapshot,
    "widgets": build_inputs_widget_group_view_model,
    "summaries": build_inputs_summary_view_model,
    "diagrams": build_inputs_diagram_view_model,
    "calculation_source": build_inputs_calculation_explainer_source_snapshot,
    "calculation_source_hash": build_inputs_calculation_explainer_source_hash,
    "calculations": build_inputs_calculation_explainer_view_model,
}


__all__ = [
    "EXTRACTED_MODULE_BOUNDARIES",
    "InputsPageSnapshot",
    "InputsPageViewModel",
    "build_inputs_page_snapshot",
    "build_inputs_page_view_model",
    "inputs_has_design_actions_or_loads",
    "make_beam_3d_figure",
    "make_summary_cross_section_figure",
    "render_inputs",
    "render_inputs_landing_card",
    "render_inputs_page",
]
