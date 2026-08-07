"""Live Inputs page composition shell."""

from __future__ import annotations

from dataclasses import dataclass
import copy
import os
from typing import Any, Callable

import streamlit as st

from inputs_page_modules.landing import (
    INPUTS_DESIGN_STARTED_KEY,
    inputs_has_design_actions_or_loads,
    inputs_show_landing_dashboard,
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
from inputs_page_modules.session.longitudinal_reo_widget_sync import (
    hydrate_inputs_longitudinal_reo_widgets_for_revision,
)
from inputs_page_modules.fragments import run_inputs_fragment
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


def _render_v2_workspace_fragment(*, page_context: dict[str, Any]) -> dict[str, Any]:
    """Render the single V2 transaction inside one stable page fragment."""

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
    """Future Inputs entry point.

    The shell owns route-order composition. The section coordinators are still
    bridged while their remaining dependencies are moved out of the old page.
    """

    ss = st.session_state
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
    st.title("Inputs")

    # Match V2's explicit landing boundary. Runtime previously rendered the
    # calculation, Design Brain, widgets, and diagram siblings underneath the
    # landing card. That could expose a zero-input recommendation while the
    # page still said "Start Your Design" and made the empty state do needless
    # engineering work. Existing non-zero actions count as started (including
    # restored beams); the landing button sets the presentation-only flag.
    if inputs_has_design_actions_or_loads(
        get_param_fn=page_context["fast_get_param"],
    ):
        ss[INPUTS_DESIGN_STARTED_KEY] = True
    # Browser verifiers exercise widget/diagram transactions directly. Keep
    # their fixture sessions out of the product landing flow; this does not
    # affect normal users and leaves V2's explicit landing boundary intact.
    if str(os.environ.get("CODEX_BROWSER_TEST_MODE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        ss[INPUTS_DESIGN_STARTED_KEY] = True
    show_landing = inputs_show_landing_dashboard(
        get_param_fn=page_context["fast_get_param"],
        same_page_rerun_has_non_landing_state=bool(
            ss.get(INPUTS_DESIGN_STARTED_KEY, False)
            # A committed V2 input transaction is itself proof that the user
            # has entered the workspace.  Do not let route/session hydration
            # drop the presentation-only flag and send a live widget edit
            # back to the landing branch, which would leave the old diagram
            # probe on screen while the canonical revision advances.
            or InputSnapshotStore(ss).current().revision > 0
        ),
        capacity_context_matches=False,
    )
    if show_landing:
        render_inputs_landing_card(
            sync_callbacks=page_context["sync_callbacks"],
        )
        _INPUTS_PAGE_RUNTIME.render_batch_design_manager(
            ss=ss,
            beam_labels=page_context["beam_labels"],
            beam_order=page_context["beam_order"],
            active_beam_id=page_context["active_beam_id"],
        )
        st.subheader("Design mode")
        # V2 stops here: no calculation, Design Brain, widgets, or diagram
        # fragment runs until the user explicitly starts the workspace.
        st.stop()

    # The Inputs shell has one V2-shaped transaction.  Calculation, summary,
    # Design Brain, controls, widgets, and diagrams all consume the same
    # committed snapshot and revision; there is no alternate sibling-fragment
    # composition that can render a stale revision.
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
        # Inputs controls are intentionally local to this workspace.  The
        # batch and Design Guide commands are now queued callbacks, so they
        # no longer depend on an ephemeral full-page button rerun.
        force_fragment=True,
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

    # A browser widget callback can finish its canonical commit while the
    # current full-page transaction is already rendering.  V2's single-page
    # renderer naturally sees that commit on the next pass; the Runtime still
    # has legacy section coordinators that may have emitted the previous
    # diagram before the callback settled.  Re-run once at the page boundary
    # when that happens so the visible diagram cannot remain one revision
    # behind the committed inputs.  This is deliberately bounded per revision
    # and only applies to the default V2-shaped full-page path.
    active_beam_id = str(ss.get("active_beam_id") or "").strip()
    current_input = InputSnapshotStore(ss).current_for_beam(active_beam_id)
    diagram_identity = dict(ss.get("_inputs_model_2d_source_identity") or {})
    current_revision = int(current_input.revision or 0)
    diagram_revision = int(diagram_identity.get("input_revision") or 0)
    last_settle_revision = int(ss.get("_inputs_page_diagram_settle_revision") or 0)
    if (
        active_beam_id
        and diagram_identity
        and current_revision > diagram_revision
        and current_revision != last_settle_revision
    ):
        ss["_inputs_page_diagram_settle_revision"] = current_revision
        st.rerun()


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
