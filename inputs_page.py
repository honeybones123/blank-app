"""Live Inputs page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Callable

import streamlit as st

from inputs_page_modules.landing import (
    INPUTS_DESIGN_STARTED_KEY,
    inputs_has_design_actions_or_loads,
    render_inputs_landing_card as _render_inputs_landing_card,
)
from inputs_application.page_runtime import (
    build_inputs_page_runtime,
)
from inputs_application.engineering_workspace import (
    build_engineering_workspace_runtime,
    render_inputs_deferred_design_brain_fragment,
    build_inputs_controls_region_context,
    render_inputs_controls_fragment_section,
    render_engineering_workspace,
    render_inputs_widget_fragment_section,
)
from inputs_application.workspace_context import InputsWorkspaceContext
from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.action_source_transaction import (
    render_inputs_action_source_transaction,
)
from inputs_page_modules.session.longitudinal_reo_widget_sync import (
    hydrate_inputs_longitudinal_reo_widgets_for_revision,
)
from inputs_page_modules.fragments import run_inputs_fragment
from state_and_helpers import (
    _request_inputs_engineering_commit,
    render_timing_mark,
    speed_profiled,
)
from widgets_helpers import render_result_page_title


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
    _render_inputs_landing_card(
        sync_callbacks=sync_callbacks,
        st_module=st,
        # This is the same shared, state-driven section builder used by the
        # Inputs model and result-page summaries; the landing card only applies
        # a compact Plotly layout to a copied figure.
        make_cross_section_figure_fn=make_summary_cross_section_figure,
    )


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


def hydrate_committed_design_action_widgets(
    *,
    force: bool = False,
    resolved_projection: bool = False,
) -> None:
    """Project committed ULS/SLS actions into their shared page widgets."""

    _INPUTS_PAGE_RUNTIME.hydrate_design_action_widgets(
        force=force,
        resolved_projection=resolved_projection,
    )


def _render_v2_workspace_fragment(*, page_context: dict[str, Any]) -> None:
    """Render controls/widgets without waiting for engineering calculations."""

    # Streamlit executes the Apply button callback before re-entering this
    # fragment. Consume that immutable, revision-bound command first: no
    # action-source projection, widget reconciliation or rendering may advance
    # state between the user's click and the atomic Apply validation/commit.
    _INPUTS_PAGE_RUNTIME.handle_pending_apply()

    # Action-source ownership is an application transaction, not a page-shell
    # concern. Keep pointer/projection/reconcile ordering behind one boundary.
    render_inputs_action_source_transaction(
        st_module=st,
        runtime=_INPUTS_PAGE_RUNTIME,
        request_commit=_request_inputs_engineering_commit,
        hydrate_actions=hydrate_committed_design_action_widgets,
    )

    # Fragment reruns do not execute the page setup coordinator. Reconcile the
    # visible Inputs reinforcement controls from the committed beam snapshot
    # before any workspace region renders.
    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip() or None
    input_store = InputSnapshotStore(st.session_state)
    beam_snapshot = input_store.current_for_beam(active_beam_id or "")
    hydrate_inputs_longitudinal_reo_widgets_for_revision(
        state=st.session_state,
        revision=int(beam_snapshot.revision or 0),
        active_beam_id=active_beam_id,
        copy_deepcopy_fn=copy.deepcopy,
    )

    controls_context = build_inputs_controls_region_context(
        page_context=page_context,
    )
    detailed_mode = render_inputs_controls_fragment_section(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        region_context=controls_context,
    )
    st.session_state["_inputs_detailed_mode"] = bool(detailed_mode)
    detailed_mode = _INPUTS_PAGE_RUNTIME.render_design_mode_selector(
        sync_callbacks=page_context["sync_callbacks"],
    )
    render_inputs_widget_fragment_section(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
        inputs_detailed_mode=bool(detailed_mode),
    )


def _render_inputs_engineering_fragment(*, page_context: dict[str, Any]) -> dict[str, Any]:
    """Render only the authoritative engineering result region."""

    return render_engineering_workspace(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
        include_design_brain=False,
        include_controls=False,
        include_widgets=False,
    )


def _render_inputs_async_design_brain_fragment(*, page_context: dict[str, Any]) -> None:
    render_inputs_deferred_design_brain_fragment(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
    )


def render_inputs_page() -> None:
    page_title_placeholder = st.empty()
    """Future Inputs entry point.

    The shell owns route-order composition. The section coordinators are still
    bridged while their remaining dependencies are moved out of the old page.
    """

    ss = st.session_state
    # Start now owns initial navigation. Beam Inputs always renders its existing
    # workspace, including the zero-action state used to enter direct actions.
    ss[INPUTS_DESIGN_STARTED_KEY] = True
    ss["_inputs_page_shell_render_count"] = int(
        ss.get("_inputs_page_shell_render_count", 0) or 0
    ) + 1
    # Reconcile the widget mirror before page setup builds the authoritative
    # snapshot. Setup deliberately reads the current widget projection, so
    # waiting until the workspace fragment is too late: a stale widget value
    # could otherwise overwrite a newer committed beam row before V2 runs.
    active_beam_id = str(ss.get("active_beam_id") or "").strip() or None
    input_store = InputSnapshotStore(ss)
    beam_snapshot = input_store.current_for_beam(active_beam_id or "")
    hydrate_inputs_longitudinal_reo_widgets_for_revision(
        state=ss,
        revision=int(beam_snapshot.revision or 0),
        active_beam_id=active_beam_id,
        copy_deepcopy_fn=copy.deepcopy,
    )
    render_timing_mark("inputs_page.shell.setup.start")
    page_context = _INPUTS_PAGE_RUNTIME.render_page_setup(ss=ss)
    # Build one explicit context for all sibling regions. Session state stays
    # the storage mechanism, but page consumers now share the same snapshot
    # and service handles for this render.
    page_context["workspace_context"] = InputsWorkspaceContext.from_session(
        ss,
        active_beam_id=page_context.get("active_beam_id"),
    )
    render_timing_mark("inputs_page.shell.setup.end")
    # Static route chrome belongs to the page shell. Keeping the title outside
    # the unified workspace fragment preserves page identity during scoped
    # widget and Apply transactions.
    with page_title_placeholder.container():
        render_result_page_title("Beam Inputs")

    # Keep controls, authoritative engineering results, and Design Brain in
    # separate ordered fragments so each region owns only its own refresh.
    for section_name in (
        "engineering_calculation",
        "engineering_controls",
        "design_brain_workspace",
        "engineering_workspace",
    ):
        ss[f"_inputs_{section_name}_fragment_mode"] = "v2_workspace"
    render_timing_mark("inputs_page.shell.workspace.start")
    run_inputs_fragment(
        st_module=st,
        fragment_name="engineering_calculation",
        render_fn=_render_inputs_engineering_fragment,
        kwargs={"page_context": page_context},
        force_fragment=True,
        run_every=0.5,
    )
    run_inputs_fragment(
        st_module=st,
        fragment_name="engineering_controls",
        render_fn=_render_v2_workspace_fragment,
        kwargs={"page_context": page_context},
    )
    run_inputs_fragment(
        st_module=st,
        fragment_name="design_brain",
        render_fn=_render_inputs_async_design_brain_fragment,
        kwargs={"page_context": page_context},
        force_fragment=True,
        run_every=0.5,
    )
    render_timing_mark("inputs_page.shell.workspace.end")

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

    # The unified engineering workspace owns summary, diagrams, calculations,
    # controls, widgets, and the revision-bound Design Brain publication.


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
