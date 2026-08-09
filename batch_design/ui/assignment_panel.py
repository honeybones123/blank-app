"""Auto-assignment stage UI boundary."""

from __future__ import annotations

from batch_design.store import BatchDesignWorkflowState
from batch_design.ui.results_table import assignment_results_frame


def render_assignment_panel(
    st,
    *,
    workflow: BatchDesignWorkflowState | None = None,
    selected_template_count: int = 0,
    target_count: int = 0,
    on_auto_assign=None,
) -> None:
    st.caption(
        "Tick ‘Use for auto design’ in the Project beams table to choose whole-beam templates. "
        "Each unticked beam is checked against those templates using its own loads."
    )
    disabled = workflow is None or selected_template_count == 0 or target_count == 0 or on_auto_assign is None
    if st.button("Auto assign", key="batch_design_auto_assign", disabled=disabled):
        on_auto_assign()

    if disabled:
        st.caption("Auto assign needs at least one checked template and one valid unticked beam.")

    if workflow and workflow.assignment_results:
        st.dataframe(assignment_results_frame(workflow.assignment_results), width="stretch")
