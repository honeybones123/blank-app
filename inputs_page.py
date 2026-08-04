"""Live Inputs page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import streamlit as st

from inputs_page_modules.landing import (
    inputs_has_design_actions_or_loads,
    render_inputs_landing_card as _render_inputs_landing_card,
)
from inputs_application.page_runtime import (
    build_inputs_page_runtime,
)
from inputs_application.engineering_workspace import (
    build_engineering_workspace_runtime,
    render_engineering_workspace_calculation,
    render_engineering_workspace_controls,
    render_engineering_workspace_design_brain,
    render_engineering_workspace_widgets,
)
from inputs_page_modules.fragments import (
    run_inputs_fragment,
    run_inputs_polling_fragment,
)
from state_and_helpers import (
    render_timing_mark,
    speed_profiled,
)


_INPUTS_PAGE_RUNTIME = build_inputs_page_runtime()
_ENGINEERING_WORKSPACE_RUNTIME = build_engineering_workspace_runtime(
    _INPUTS_PAGE_RUNTIME
)
make_beam_3d_figure = _INPUTS_PAGE_RUNTIME.make_beam_3d_figure
make_summary_cross_section_figure = (
    _INPUTS_PAGE_RUNTIME.make_summary_cross_section_figure
)


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


def build_inputs_session_source_snapshot(*args: Any, **kwargs: Any) -> Any:
    from inputs_page_modules.session import build_inputs_session_source_snapshot as builder

    return builder(*args, **kwargs)


def build_inputs_widget_group_view_model(*args: Any, **kwargs: Any) -> Any:
    from inputs_page_modules.widgets import build_inputs_widget_group_view_model as builder

    return builder(*args, **kwargs)


def build_inputs_summary_view_model(*args: Any, **kwargs: Any) -> Any:
    from inputs_page_modules.summaries import build_inputs_summary_view_model as builder

    return builder(*args, **kwargs)


def build_inputs_diagram_view_model(*args: Any, **kwargs: Any) -> Any:
    from inputs_page_modules.diagrams import build_inputs_diagram_view_model as builder

    return builder(*args, **kwargs)


def build_inputs_calculation_explainer_source_snapshot(
    *args: Any, **kwargs: Any
) -> Any:
    from inputs_page_modules.calculations import (
        build_inputs_calculation_explainer_source_snapshot as builder,
    )

    return builder(*args, **kwargs)


def build_inputs_calculation_explainer_source_hash(*args: Any, **kwargs: Any) -> Any:
    from inputs_page_modules.calculations import (
        build_inputs_calculation_explainer_source_hash as builder,
    )

    return builder(*args, **kwargs)


def build_inputs_calculation_explainer_view_model(*args: Any, **kwargs: Any) -> Any:
    from inputs_page_modules.calculations import (
        build_inputs_calculation_explainer_view_model as builder,
    )

    return builder(*args, **kwargs)


def _render_engineering_workspace_calculation(
    *,
    page_context: dict[str, Any],
    workspace_slot: Any = None,
) -> dict[str, Any]:
    return render_engineering_workspace_calculation(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
        workspace_slot=workspace_slot,
    )


def _render_engineering_workspace_controls(
    *,
    page_context: dict[str, Any],
) -> bool:
    return render_engineering_workspace_controls(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
    )


def _render_engineering_workspace_design_brain(
    *,
    page_context: dict[str, Any],
    design_brain_slot: Any = None,
) -> None:
    render_engineering_workspace_design_brain(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
        design_brain_slot=design_brain_slot,
    )


def _render_engineering_workspace_widgets(
    *,
    page_context: dict[str, Any],
) -> bool:
    return render_engineering_workspace_widgets(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
    )


def render_inputs_page() -> None:
    """Future Inputs entry point.

    The shell owns route-order composition. The section coordinators are still
    bridged while their remaining dependencies are moved out of the old page.
    """

    ss = st.session_state
    ss["_inputs_page_shell_render_count"] = int(
        ss.get("_inputs_page_shell_render_count", 0) or 0
    ) + 1
    # A full-page rerun creates fresh Streamlit slots even when the committed
    # input revision did not change.  The presented-revision markers are only
    # valid for the lifetime of the previous shell: retaining them makes the
    # polling fragments skip their first draw and leaves the new slots blank.
    # Fragment-only reruns do not execute this shell, so they still reuse the
    # visible summary/Design Guide until a new input revision is committed.
    ss.pop("_inputs_calculation_workspace_presented_revision", None)
    ss.pop("_inputs_design_brain_presented_revision", None)

    render_timing_mark("inputs_page.shell.setup.start")
    page_context = _INPUTS_PAGE_RUNTIME.render_page_setup(ss=ss)
    render_timing_mark("inputs_page.shell.setup.end")
    # Static route chrome belongs to the page shell.  Keeping the title outside
    # every polling fragment prevents calculation or Design Brain refreshes
    # from marking the whole page identity as stale.
    st.title("Inputs")
    # Sibling fragments share revisioned stores, not a render boundary. The
    # calculation and Design Brain regions poll for a newly committed input
    # revision; controls and engineering widgets remain independently usable.
    render_timing_mark("inputs_page.shell.calculation.start")
    run_inputs_polling_fragment(
        st_module=st,
        fragment_name="engineering_calculation_workspace",
        render_fn=_render_engineering_workspace_calculation,
        kwargs={
            "page_context": page_context,
        },
        run_every_s=1.0,
    )
    render_timing_mark("inputs_page.shell.calculation.end")

    render_timing_mark("inputs_page.shell.controls.start")
    run_inputs_fragment(
        st_module=st,
        fragment_name="engineering_controls_workspace",
        render_fn=_render_engineering_workspace_controls,
        kwargs={"page_context": page_context},
    )
    render_timing_mark("inputs_page.shell.controls.end")

    render_timing_mark("inputs_page.shell.design_brain.start")
    run_inputs_polling_fragment(
        st_module=st,
        fragment_name="design_brain_workspace",
        render_fn=_render_engineering_workspace_design_brain,
        kwargs={
            "page_context": page_context,
        },
        run_every_s=1.0,
    )
    render_timing_mark("inputs_page.shell.design_brain.end")

    render_timing_mark("inputs_page.shell.widgets.start")
    run_inputs_fragment(
        st_module=st,
        fragment_name="engineering_input_workspace",
        render_fn=_render_engineering_workspace_widgets,
        kwargs={"page_context": page_context},
    )
    render_timing_mark("inputs_page.shell.widgets.end")

    render_timing_mark("inputs_page.shell.tail.start")
    _INPUTS_PAGE_RUNTIME.render_tail(
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
