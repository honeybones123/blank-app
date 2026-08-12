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
    render_engineering_workspace,
)
from inputs_application.workspace_context import InputsWorkspaceContext
from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.action_source_control import (
    INPUTS_ACTION_SOURCE_TOGGLE_KEY,
    authoritative_action_source_projection,
    render_action_source_toggle,
    synchronize_load_analysis_actions_for_inputs,
    uses_load_analysis_actions,
)
from inputs_application.load_analysis_state_store import LoadAnalysisStateStore
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


def _render_v2_workspace_fragment(*, page_context: dict[str, Any]) -> dict[str, Any]:
    """Render the single V2 transaction inside one stable page fragment."""

    load_analysis_store = LoadAnalysisStateStore(st.session_state)

    def _commit_selected_action_source(_selected: bool) -> None:
        projected_keys = synchronize_load_analysis_actions_for_inputs(
            st.session_state,
            draft=load_analysis_store.current().to_dict(),
            results=load_analysis_store.results(),
        )
        _request_inputs_engineering_commit(
            INPUTS_ACTION_SOURCE_TOGGLE_KEY,
            changed_keys=tuple(
                sorted({"actions_mode", "actions_source", *projected_keys})
            ),
            # The toggle callback already causes the owning fragment to rerun.
            # Scheduling another fragment wake here creates overlapping runs
            # and can truncate the page below Design Actions.
            wake_fragments=False,
        )

    # Both Beam Inputs and Load Analysis render this same branch selector.
    # Its widget keys are projections of the existing canonical action-source
    # contract, so changing either page cannot create a split source state.
    render_action_source_toggle(
        st,
        widget_key=INPUTS_ACTION_SOURCE_TOGGLE_KEY,
        after_commit=_commit_selected_action_source,
    )

    # Load Analysis owns its loads and solved actions. Beam Inputs receives a
    # one-way, derived ULS/SLS projection only while that source is selected.
    # Running this idempotently also catches a newer Load Analysis solve after
    # the user returns to Inputs without manufacturing a second authority.
    projected_keys = synchronize_load_analysis_actions_for_inputs(
        st.session_state,
        draft=load_analysis_store.current().to_dict(),
        results=load_analysis_store.results(),
    )
    # The Load Analysis page may already have projected the latest actions into
    # shared state before Inputs is opened.  In that case ``projected_keys`` is
    # empty even though the beam-owned input transaction still contains the
    # former manual actions.  Compare the typed projection with the committed
    # beam snapshot as well, so navigation cannot leave widgets on the live
    # Load Analysis values while summaries and Design Brain evaluate zeros.
    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    committed_actions = (
        InputSnapshotStore(st.session_state)
        .current_for_beam(active_beam_id)
        .to_dict()
        if active_beam_id
        else {}
    )
    action_projection = authoritative_action_source_projection(st.session_state)
    projection_commit_keys = tuple(
        sorted(
            key
            for key, value in action_projection.items()
            if committed_actions.get(key) != value
        )
    ) if uses_load_analysis_actions(st.session_state) else ()
    action_commit_keys = tuple(sorted({*projected_keys, *projection_commit_keys}))
    if action_commit_keys:
        _request_inputs_engineering_commit(
            INPUTS_ACTION_SOURCE_TOGGLE_KEY,
            changed_keys=action_commit_keys,
            wake_fragments=False,
        )

    # A fragment rerun does not pass through the page-level setup boundary.
    # Commit the visible design-action draft before consuming a queued Apply
    # command so the candidate is applied to the same action state that was
    # calculated and displayed.  Applying first can otherwise combine the
    # candidate updates with an older zero-action beam snapshot while leaving
    # the 200 kNm widget visible.
    _INPUTS_PAGE_RUNTIME.reconcile_design_actions()
    if not uses_load_analysis_actions(st.session_state):
        # Reconciliation writes the visible manual controls to their canonical
        # ULS/SLS owners.  Close that command by idempotently committing the
        # active action set before calculation/publication is read below.
        # This is required even when the reconcile call reports no difference:
        # an earlier proxy-only callback may already have updated shared state
        # while the beam-owned snapshot still contains the previous action.
        # ``_request_inputs_engineering_commit`` is content-idempotent, so an
        # already complete callback transaction creates no extra revision.
        selected_prefix = (
            "sls"
            if str(st.session_state.get("loads_edit_mode", "ULS") or "ULS")
            .strip()
            .upper()
            == "SLS"
            else "uls"
        )
        _request_inputs_engineering_commit(
            "inputs_load_Mstar_pos_proxy",
            changed_keys=(
                f"{selected_prefix}_Mstar",
                f"{selected_prefix}_Mstar_pos_manual",
                f"{selected_prefix}_Mstar_neg_manual",
                f"{selected_prefix}_Vstar",
                f"{selected_prefix}_Nstar",
            ),
            wake_fragments=False,
        )

    # Apply is owned by the same V2 workspace fragment as the Design Brain
    # button.  Processing the queued command here keeps the explicit Apply
    # interaction scoped to this workspace instead of forcing a page rerun.
    # The page-level setup remains as a fallback for non-fragment routes.
    _INPUTS_PAGE_RUNTIME.handle_pending_apply()

    # Fragment reruns do not execute the page setup coordinator.  Reconcile
    # the visible Inputs reinforcement controls from the committed beam
    # snapshot before any workspace region (calculation, Design Brain, or
    # widgets) renders.  This prevents the page from displaying Ø24 while V2
    # evaluates the committed Ø40 transaction, which can otherwise select a
    # different family and recommendation.
    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip() or None
    input_store = InputSnapshotStore(st.session_state)
    beam_snapshot = input_store.current_for_beam(active_beam_id or "")
    hydrate_inputs_longitudinal_reo_widgets_for_revision(
        state=st.session_state,
        revision=int(beam_snapshot.revision or input_store.current().revision or 0),
        active_beam_id=active_beam_id,
        copy_deepcopy_fn=copy.deepcopy,
    )

    return render_engineering_workspace(
        st_module=st,
        runtime=_ENGINEERING_WORKSPACE_RUNTIME,
        page_context=page_context,
        include_design_brain=True,
        include_controls=True,
        include_widgets=True,
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
    # snapshot.  Setup deliberately reads the current widget projection, so
    # waiting until the workspace fragment is too late: a stale widget value
    # could otherwise overwrite a newer committed beam row before V2 runs.
    active_beam_id = str(ss.get("active_beam_id") or "").strip() or None
    input_store = InputSnapshotStore(ss)
    beam_snapshot = input_store.current_for_beam(active_beam_id or "")
    hydrate_inputs_longitudinal_reo_widgets_for_revision(
        state=ss,
        revision=int(beam_snapshot.revision or input_store.current().revision or 0),
        active_beam_id=active_beam_id,
        copy_deepcopy_fn=copy.deepcopy,
    )
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
    # Build one explicit context for all sibling regions.  Session state stays
    # the storage mechanism, but page consumers now share the same snapshot
    # and service handles for this render.
    page_context["workspace_context"] = InputsWorkspaceContext.from_session(
        ss,
        active_beam_id=page_context.get("active_beam_id"),
    )
    render_timing_mark("inputs_page.shell.setup.end")
    # Static route chrome belongs to the page shell.  Keeping the title outside
    # every polling fragment prevents calculation or Design Brain refreshes
    # from marking the whole page identity as stale.
    with page_title_placeholder.container():
        render_result_page_title("Beam Inputs")

    # The Inputs shell has one V2-shaped transaction. Calculation, summary,
    # Design Brain, controls, widgets, and diagrams all consume the same
    # committed snapshot and revision. Keep that transaction inside one
    # optional Streamlit fragment: widget callbacks and Apply then rerun only
    # this workspace, while the shell remains the safe full-page fallback when
    # fragments are disabled or unsupported.
    for section_name in (
        "engineering_calculation_workspace",
        "engineering_controls_workspace",
        "design_brain_workspace",
        "engineering_input_workspace",
    ):
        ss[f"_inputs_{section_name}_fragment_mode"] = "v2_workspace"
    render_timing_mark("inputs_page.shell.workspace.start")
    run_inputs_fragment(
        st_module=st,
        fragment_name="engineering_workspace",
        render_fn=_render_v2_workspace_fragment,
        kwargs={"page_context": page_context},
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

    # The unified engineering workspace owns summary, diagram, calculation
    # and Design Brain refresh. All page controls settle through this one
    # shell transaction; no sibling fragment can publish an interim result.


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
