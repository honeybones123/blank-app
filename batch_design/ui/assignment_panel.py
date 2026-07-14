"""Auto-assignment stage UI boundary."""

from __future__ import annotations

import json

from batch_design.assignment import assign_batch_cases
from batch_design.importers.project_import import import_beams_from_project
from batch_design.models import BatchBeamTemplate
from batch_design.store import BatchDesignWorkflowState
from batch_design.ui.results_table import assignment_results_frame


def _load_other_project_templates(st, workflow: BatchDesignWorkflowState | None) -> list[BatchBeamTemplate]:
    uploaded_project = st.file_uploader(
        "Other StructuralBase project",
        type=["json"],
        key="batch_design_assignment_other_project_json",
    )
    if uploaded_project is None:
        if workflow is None:
            return []
        return list(workflow.metadata.get("assignment_other_project_templates") or [])

    try:
        payload = json.loads(uploaded_project.getvalue().decode("utf-8"))
        templates = import_beams_from_project(payload, as_templates=True)
    except Exception as exc:
        st.warning(f"Could not import other project beams: {exc}")
        return []

    if workflow is not None:
        workflow.metadata["assignment_other_project_templates"] = templates
    return list(templates)


def render_assignment_panel(
    st,
    *,
    workflow: BatchDesignWorkflowState | None = None,
    current_project_templates: list[BatchBeamTemplate] | None = None,
) -> None:
    source = st.radio(
        "Assignment library",
        options=["Current project beams", "Other project beams"],
        horizontal=True,
        key="batch_design_assignment_source",
    )

    if source == "Current project beams":
        candidates = list(current_project_templates or [])
    else:
        candidates = _load_other_project_templates(st, workflow)

    st.caption(f"{len(candidates)} candidate beam(s) available from {source.lower()}.")

    pref_cols = st.columns(4, gap="small")
    with pref_cols[0]:
        same_depth = st.checkbox("Same depth", value=False, key="batch_design_assign_same_depth")
    with pref_cols[1]:
        same_width = st.checkbox("Same width", value=False, key="batch_design_assign_same_width")
    with pref_cols[2]:
        same_reo_cage = st.checkbox("Same reo", value=False, key="batch_design_assign_same_reo")
    with pref_cols[3]:
        closest_utilisation = st.checkbox("Closest utilisation", value=True, key="batch_design_assign_closest_util")

    if workflow is None:
        return

    runnable_cases = workflow.runnable_cases()
    disabled = not runnable_cases or not candidates
    if st.button("Auto Assign", key="batch_design_auto_assign", disabled=disabled):
        results = assign_batch_cases(
            runnable_cases,
            candidates,
            preferences={
                "same_depth": same_depth,
                "same_width": same_width,
                "same_reo_cage": same_reo_cage,
                "closest_utilisation": closest_utilisation,
            },
        )
        workflow.replace_assignment_results(results)
        st.session_state["batch_design_assignment_results"] = results
        st.rerun()

    if disabled:
        st.caption("Auto Assign needs reviewed load rows and at least one candidate beam.")

    if workflow.assignment_results:
        st.dataframe(assignment_results_frame(workflow.assignment_results), use_container_width=True)
