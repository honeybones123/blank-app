"""Streamlit page renderer for Batch Design."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from batch_design.importers.spacegass_excel import SpaceGassExcelImporter
from batch_design.models import BatchAssignmentResult
from batch_design.runner import DesignBrainAdapter, run_reviewed_batch_design
from batch_design.store import BatchDesignWorkflowState
from batch_design.ui.assignment_panel import render_assignment_panel
from batch_design.ui.import_panel import render_import_panel
from batch_design.ui.preview_table import render_preview_table
from batch_design.ui.project_beam_load_table import (
    ACTION_COLUMNS,
    ACTION_LABELS,
    apply_project_beam_load_editor_rows,
    project_beam_editor_styler,
    project_beam_load_editor_frame,
    project_beam_templates_from_frame,
)
from batch_design.ui.passive_capacity import (
    PASSIVE_CAPACITY_CACHE_KEY,
    apply_passive_capacity_checks,
)
from batch_design.ui.results_table import render_results_table


@dataclass
class BatchDesignPageContext:
    session_state: Mapping[str, Any]
    beam_order: list[str]
    active_beam_id: str | None
    beam_labels: dict[str, str]
    set_active_beam: Callable[[str], bool]
    add_beam: Callable[[], Any]
    duplicate_beam: Callable[[], Any]
    delete_beam: Callable[[str | None], Any]
    reset_workspace: Callable[[], Any]
    force_refresh: Callable[[str], Any]
    log_rerun: Callable[[str], Any]
    build_schedule_preview_df: Callable[[], pd.DataFrame]
    build_schedule_editor_df: Callable[[], pd.DataFrame]
    sync_schedule_editor_df: Callable[[pd.DataFrame], set[str]]
    publish_batch_design_results: Callable[[list[Any]], set[str]]
    build_schedule_export_df: Callable[[], pd.DataFrame]
    get_active_summary: Callable[[], dict[str, Any]]
    format_status_badge: Callable[..., str]
    format_last_checked: Callable[[Any], str]
    make_section_preview_figure: Callable[[], Any]
    render_plotly_diagram: Callable[..., Any]
    save_active_to_table: Callable[[], Any]
    apply_resync: Callable[..., Any]
    design_brain_adapter: DesignBrainAdapter | None = None


WORKFLOW_STATE_KEY = "batch_design_workflow_state"
WORKFLOW_MODE_KEY = "batch_design_workflow_mode"
WORKFLOW_MODE_RUN_DESIGN = "Run design"
WORKFLOW_MODE_AUTO_ASSIGN = "Auto assign"
WORKSPACE_OPEN_KEY = "batch_design_workspace_open"
PROJECT_BEAM_TABLE_FRAME_KEY = "batch_design_project_beam_table_frame"
RUN_DESIGN_REQUEST_KEY = "_batch_design_run_requested"
AUTO_ASSIGN_REQUEST_KEY = "_batch_design_auto_assign_requested"
ACTIVE_BEAM_SELECTOR_KEY = "beam_manager_active_selector"


def _request_batch_design_run() -> None:
    """Queue one batch run before Streamlit starts the next page transaction."""

    st.session_state[RUN_DESIGN_REQUEST_KEY] = True


def _request_batch_auto_assign() -> None:
    """Queue one assignment before Streamlit starts the next transaction."""

    st.session_state[AUTO_ASSIGN_REQUEST_KEY] = True


def _toggle_batch_design_workspace() -> None:
    """Toggle the visible Batch workspace without relying on a CSS overlay."""

    st.session_state[WORKSPACE_OPEN_KEY] = not bool(
        st.session_state.get(WORKSPACE_OPEN_KEY, False)
    )


def _activate_selected_project_beam(ctx: BatchDesignPageContext) -> None:
    """Promote the selector value through the one active-beam boundary.

    A selectbox stores its own value in Streamlit session state.  Handling the
    difference *after* rendering left that widget value able to disagree with
    ``active_beam_id`` during a fragment rerun.  Batch Design could therefore
    publish a proposal for one beam while the Inputs Design Brain evaluated a
    different beam.  A callback runs before the next render, so the selector,
    stored beam record and revisioned Inputs transaction now change together.
    """

    selected_beam_id = str(st.session_state.get(ACTIVE_BEAM_SELECTOR_KEY) or "").strip()
    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    if not selected_beam_id or selected_beam_id == active_beam_id:
        return
    if ctx.set_active_beam(selected_beam_id):
        # Beam revisions are independent per beam. Arm the Inputs atomic
        # presentation gate so a switch between equal numeric revisions is
        # still revealed only after the selected beam's complete controls and
        # result projection have arrived.
        st.session_state["_inputs_atomic_revision_guard_pending"] = True
        ctx.force_refresh("beam_selector_change")
        ctx.log_rerun("beam_selector_change")


def _project_beam_editor_changed(before: pd.DataFrame, after: pd.DataFrame) -> bool:
    """Return whether a user-editable Project Beams cell actually changed.

    ``st.data_editor`` returns a dataframe on every page render.  Treating
    that return value as an edit caused a save/rerun loop that consumed clicks
    on the controls immediately below the table.
    """

    editable_columns = (
        "use_for_auto_design",
        "beam_label",
        "sec_shape",
        "b", "D", "L", "bf", "tf", "bw", "tw",
        "cover_top", "cover_bot", "cover_side", "fc", "fsy",
        "bot1_count", "db_bot_1", "top1_count", "db_top_1",
        "lig_d", "lig_legs", "s_lig",
        *ACTION_COLUMNS,
    )
    if list(before.index) != list(after.index) or set(before.columns) != set(after.columns):
        return True

    def normalise(value: Any) -> Any:
        try:
            if bool(pd.isna(value)):
                return None
        except (TypeError, ValueError):
            pass
        return value

    for column in editable_columns:
        if column not in before.columns or column not in after.columns:
            continue
        for old_value, new_value in zip(before[column], after[column], strict=True):
            if normalise(old_value) != normalise(new_value):
                return True
    return False


def _rerun_batch_design_page() -> None:
    """Refresh the active Inputs region after a batch command."""

    st.session_state[WORKSPACE_OPEN_KEY] = True
    # The Batch card lives inside the Inputs workspace fragment.  Reusing the
    # shared boundary keeps a batch result local when Streamlit permits it and
    # retains the supported app-level fallback for non-fragment callers.
    from inputs_page_modules.fragments import rerun_inputs_current_scope

    rerun_inputs_current_scope(st)


def get_batch_design_workflow_state(session_state: MutableMapping[str, Any] | None = None) -> BatchDesignWorkflowState:
    state = st.session_state if session_state is None else session_state
    workflow = state.get(WORKFLOW_STATE_KEY)
    if not isinstance(workflow, BatchDesignWorkflowState):
        workflow = BatchDesignWorkflowState()
        state[WORKFLOW_STATE_KEY] = workflow
    return workflow


def _render_project_beam_controls(ctx: BatchDesignPageContext) -> None:
    # ``active_beam_id`` is the application authority.  Do not let a retained
    # selectbox value choose a different beam for the visible UI.
    active_beam_id = str(
        st.session_state.get("active_beam_id") or ctx.active_beam_id or ""
    ).strip() or None
    beam_order = list(ctx.beam_order or [])
    if active_beam_id not in beam_order and beam_order:
        active_beam_id = beam_order[0]

    beam_selector_col, spacer_col, add_beam_col, dup_beam_col, del_beam_col, reset_workspace_col = st.columns(
        [2.1, 1.5, 0.9, 1.05, 0.95, 1.35],
        gap="medium",
        vertical_alignment="bottom",
    )

    with beam_selector_col:
        if beam_order:
            # Synchronise programmatic changes (add/delete/batch promotion)
            # before the widget is created.  User changes go through the
            # callback above rather than a post-render branch.
            if st.session_state.get(ACTIVE_BEAM_SELECTOR_KEY) != active_beam_id:
                st.session_state[ACTIVE_BEAM_SELECTOR_KEY] = active_beam_id
            st.selectbox(
                "Active set",
                options=beam_order,
                # The application authority has already seeded the widget key.
                # ``index`` would be a second competing default and Streamlit
                # warns (and can transiently display an unformatted raw id)
                # when both are supplied during a project-beam switch.
                index=None,
                format_func=lambda beam_id: ctx.beam_labels.get(beam_id, beam_id),
                key=ACTIVE_BEAM_SELECTOR_KEY,
                help="Select the project beam used as the base concrete assumptions for manual batch rows.",
                on_change=_activate_selected_project_beam,
                args=(ctx,),
            )
        else:
            st.caption("No stored project beams yet.")

    with spacer_col:
        st.empty()

    with add_beam_col:
        if st.button("+ Add", key="beam_manager_add_button", use_container_width=True):
            ctx.add_beam()
            ctx.force_refresh("add_beam")
            ctx.log_rerun("add_beam")
            _rerun_batch_design_page()

    with dup_beam_col:
        if st.button("Duplicate", key="beam_manager_duplicate_button", use_container_width=True):
            ctx.duplicate_beam()
            ctx.force_refresh("duplicate_beam")
            ctx.log_rerun("duplicate_beam")
            _rerun_batch_design_page()

    with del_beam_col:
        if st.button(
            "Delete",
            key="beam_manager_delete_button",
            use_container_width=True,
            disabled=len(beam_order) <= 1,
        ):
            ctx.delete_beam(active_beam_id)
            ctx.force_refresh("delete_beam")
            ctx.log_rerun("delete_beam")
            _rerun_batch_design_page()

    with reset_workspace_col:
        if st.button(
            "Reset workspace",
            key="beam_manager_reset_workspace",
            use_container_width=True,
            help="Reset the project beam workspace. Batch imported rows are not deleted.",
        ):
            ctx.reset_workspace()
            ctx.apply_resync(source="workspace_reset_clean_starter")
            ctx.force_refresh("reset_workspace")
            ctx.log_rerun("reset_workspace")
            _rerun_batch_design_page()


def _render_project_beam_design_editor(ctx: BatchDesignPageContext, workflow: BatchDesignWorkflowState) -> None:
    st.markdown("### Project beams")
    _render_project_beam_controls(ctx)

    schedule_df = ctx.build_schedule_editor_df()
    if schedule_df is None or schedule_df.empty:
        st.caption("No project beams are available yet.")
        # Keep the importer available even before the first project-beam row
        # exists, but render it in this same workspace rather than creating a
        # second, unrelated import card.
        _render_import_workflow(workflow)
        _render_workflow_mode_selector(ctx, workflow)
        return

    passive_capacity_cache = st.session_state.setdefault(
        PASSIVE_CAPACITY_CACHE_KEY,
        {},
    )
    schedule_df = apply_passive_capacity_checks(
        schedule_df,
        adapter=ctx.design_brain_adapter,
        beam_records=st.session_state.get("beam_records"),
        assumptions=workflow.assumptions,
        cache=passive_capacity_cache,
    )
    editor_df = project_beam_load_editor_frame(schedule_df, workflow)
    visible_columns = [
        "active",
        "beam_id",
        "use_for_auto_design",
        "design_state",
        "current_phi_mu_knm",
        "current_phi_vu_kn",
        "current_utilisation",
        "bending_utilisation",
        "shear_utilisation",
        "crack_utilisation",
        "deflection_utilisation",
        "beam_label",
        "sec_shape",
        "b",
        "D",
        "L",
        # Keep all imported axes in the stored frame, but show only the
        # quantities consumed by the one-axis design model.
        "n_star",
        "vy_star",
        "mx_star",
        "mz_star",
        "bf",
        "tf",
        "bw",
        "tw",
        "cover_top",
        "cover_bot",
        "cover_side",
        "fc",
        "fsy",
        "bot1_count",
        "db_bot_1",
        "top1_count",
        "db_top_1",
        "lig_d",
        "lig_legs",
        "s_lig",
    ]
    visible_columns = [column for column in visible_columns if column in editor_df.columns]

    editor_epoch = int(
        st.session_state.get("_batch_design_project_beam_editor_epoch", 0) or 0
    )
    edited_schedule_df = st.data_editor(
        project_beam_editor_styler(editor_df),
        key=f"batch_design_project_beam_reo_editor_{editor_epoch}",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_order=visible_columns,
        disabled=[
            "active",
            "beam_id",
            "capacity_status",
            "design_state",
            "current_phi_mu_knm",
            "current_phi_vu_kn",
            "current_utilisation",
            "bending_utilisation",
            "shear_utilisation",
            "crack_utilisation",
            "deflection_utilisation",
        ],
        column_config={
            "active": st.column_config.TextColumn("Active", disabled=True),
            "beam_id": st.column_config.TextColumn("Beam ID", disabled=True),
            "use_for_auto_design": st.column_config.CheckboxColumn(
                "Use for auto assign",
                help="Use this beam's complete geometry and reinforcement as an Auto assign template.",
                default=False,
            ),
            "design_state": st.column_config.TextColumn("Design state", disabled=True),
            "current_phi_mu_knm": st.column_config.NumberColumn(
                "Current phiMu (kNm)", format="%.1f", disabled=True
            ),
            "current_phi_vu_kn": st.column_config.NumberColumn(
                "Current phiVu (kN)", format="%.1f", disabled=True
            ),
            "current_utilisation": st.column_config.TextColumn(
                "Current utilisation", disabled=True
            ),
            "bending_utilisation": st.column_config.TextColumn("Bending", disabled=True),
            "shear_utilisation": st.column_config.TextColumn("Shear", disabled=True),
            "crack_utilisation": st.column_config.TextColumn("Crack", disabled=True),
            "deflection_utilisation": st.column_config.TextColumn("Deflection", disabled=True),
            "beam_label": st.column_config.TextColumn("Beam Label"),
            "sec_shape": st.column_config.SelectboxColumn("Section", options=["RECT", "T", "I"]),
            "b": st.column_config.NumberColumn("b"),
            "D": st.column_config.NumberColumn("D"),
            "L": st.column_config.NumberColumn("L"),
            **{
                column: st.column_config.NumberColumn(label)
                for column, label in ACTION_LABELS.items()
            },
            "bf": st.column_config.NumberColumn("bf"),
            "tf": st.column_config.NumberColumn("tf"),
            "bw": st.column_config.NumberColumn("bw"),
            "tw": st.column_config.NumberColumn("tw"),
            "cover_top": st.column_config.NumberColumn("Top cover"),
            "cover_bot": st.column_config.NumberColumn("Bottom cover"),
            "cover_side": st.column_config.NumberColumn("Side cover"),
            "fc": st.column_config.NumberColumn("f'c"),
            "fsy": st.column_config.NumberColumn("fsy"),
            "bot1_count": st.column_config.NumberColumn("Bottom bars"),
            "db_bot_1": st.column_config.NumberColumn("Bottom dia"),
            "top1_count": st.column_config.NumberColumn("Top bars"),
            "db_top_1": st.column_config.NumberColumn("Top dia"),
            "lig_d": st.column_config.NumberColumn("Lig dia"),
            "lig_legs": st.column_config.NumberColumn("Lig legs"),
            "s_lig": st.column_config.NumberColumn("Lig spacing"),
        },
    )
    st.caption(
        "Row colours and current capacities use the authoritative calculator only. "
        "Batch Design Brain runs only when Run design or Auto assign is pressed."
    )
    # Preserve the exact table projection the user can see.  Run design must
    # consume this same frame; rebuilding from a separate raw schedule can
    # lose current design actions during a Streamlit rerun.
    st.session_state[PROJECT_BEAM_TABLE_FRAME_KEY] = edited_schedule_df.copy(deep=True)

    # ``st.data_editor`` returns the edited frame on the rerun caused by a
    # cell change. Commit it immediately through the canonical beam-table
    # callback, refresh the workflow projection, and rerun only the active
    # Inputs scope so summaries/diagrams see the new revision.
    changed_beam_ids = (
        ctx.sync_schedule_editor_df(edited_schedule_df)
        if _project_beam_editor_changed(editor_df, edited_schedule_df)
        else set()
    )
    if changed_beam_ids:
        apply_project_beam_load_editor_rows(workflow, edited_schedule_df)
        st.session_state["batch_design_imported_rows"] = workflow.imported_cases
        st.session_state["batch_design_import_errors"] = workflow.validation.errors
        st.session_state["batch_design_import_warnings"] = workflow.validation.warnings
        ctx.force_refresh("batch_design_project_beam_table_auto_save")
        ctx.log_rerun("batch_design_project_beam_table_auto_save")
        _rerun_batch_design_page()

    if workflow.validation.errors:
        st.warning(f"{len(workflow.validation.errors)} load issue(s) must be fixed before design.")
        for issue in workflow.validation.errors:
            member_id = str(getattr(issue, "member_id", "") or "row").strip() or "row"
            field = str(getattr(issue, "field", "") or "input").strip() or "input"
            message = str(getattr(issue, "message", "Invalid value.") or "Invalid value.").strip()
            st.caption(f"{member_id} · {field}: {message}")

    # The upload control belongs to the project-beam table workflow.  Keeping
    # it here makes the relationship explicit and removes the old standalone
    # import card while preserving the existing importer/validation path.
    _render_import_workflow(workflow)
    _render_workflow_mode_selector(ctx, workflow)


def _render_import_workflow(workflow: BatchDesignWorkflowState) -> None:
    uploaded_file = render_import_panel(st)
    if uploaded_file is not None:
        imported = SpaceGassExcelImporter().import_rows(uploaded_file)
        validation = workflow.replace_imported_cases(imported.rows)
        st.session_state["batch_design_imported_rows"] = workflow.imported_cases
        st.session_state["batch_design_import_warnings"] = imported.warnings + validation.warnings
        st.session_state["batch_design_import_errors"] = validation.errors
        if validation.errors:
            st.warning(f"{len(validation.errors)} imported row issue(s) must be fixed or excluded before design.")
        render_preview_table(st, imported.rows)


def _run_batch_design_now(workflow: BatchDesignWorkflowState, ctx: BatchDesignPageContext) -> None:
    """Run the current Project Beams table, without requiring an import."""

    # The editable table is the project source of truth.  Rebuild the batch
    # cases from its current actions before checking whether the run is ready;
    # otherwise a project with no uploaded spreadsheet looks incorrectly empty.
    current_schedule_df = st.session_state.get(PROJECT_BEAM_TABLE_FRAME_KEY)
    if not isinstance(current_schedule_df, pd.DataFrame):
        current_schedule_df = ctx.build_schedule_editor_df()
    apply_project_beam_load_editor_rows(workflow, current_schedule_df)
    st.session_state["batch_design_imported_rows"] = workflow.imported_cases
    st.session_state["batch_design_import_errors"] = workflow.validation.errors
    st.session_state["batch_design_import_warnings"] = workflow.validation.warnings

    blocked = workflow.blocked_run_reasons()
    if blocked:
        st.warning(" ".join(blocked))
        for issue in workflow.validation.errors:
            member_id = str(getattr(issue, "member_id", "") or "row").strip() or "row"
            field = str(getattr(issue, "field", "") or "input").strip() or "input"
            message = str(getattr(issue, "message", "Invalid value.") or "Invalid value.").strip()
            st.caption(f"{member_id} · {field}: {message}")
        return
    if ctx.design_brain_adapter is None:
        st.info("Design Brain adapter is not connected for this app session.")
        return

    with st.spinner("Calculating current capacities, then running optimisation..."):
        results = run_reviewed_batch_design(
            workflow,
            ctx.design_brain_adapter,
            assumptions=workflow.assumptions,
        )
    st.session_state["batch_design_design_results"] = results
    published_beam_ids = ctx.publish_batch_design_results(results)
    failures = [result for result in results if result.passed is False or result.error]
    if failures:
        st.warning(
            f"Design Brain completed for {len(results)} row(s); "
            f"{len(failures)} row(s) need review."
        )
    else:
        st.success(f"Design Brain completed for {len(results)} row(s).")
    # The editable table was rendered before the button handler.  Re-run once
    # after publishing so its live Design state changes immediately.
    if published_beam_ids:
        _rerun_batch_design_page()


def _run_auto_assign_now(workflow: BatchDesignWorkflowState, ctx: BatchDesignPageContext) -> None:
    """Assign checked whole-beam templates to unticked target beams.

    Each possible source is checked through the V2 current-design path using
    the target member's loads. This is deliberately not the retired capacity
    matching shortcut: a target receives the source's actual geometry and reo
    only after that exact arrangement has passed V2 for the target loads.
    """

    schedule_df = st.session_state.get(PROJECT_BEAM_TABLE_FRAME_KEY)
    if not isinstance(schedule_df, pd.DataFrame):
        schedule_df = ctx.build_schedule_editor_df()
    apply_project_beam_load_editor_rows(workflow, schedule_df)
    source_ids = {
        str(row.get("beam_id") or "").strip()
        for row in schedule_df.to_dict("records")
        if bool(row.get("use_for_auto_design", False))
    }
    source_ids.discard("")
    if not source_ids:
        st.warning("Tick at least one beam in ‘Use for auto assign’ first.")
        return
    if ctx.design_brain_adapter is None:
        st.info("Design Brain adapter is not connected for this app session.")
        return

    beam_records = st.session_state.get("beam_records") or {}
    targets = [
        case for case in workflow.runnable_cases()
        if str(case.member_id or "").strip() not in source_ids
    ]
    if not targets:
        st.info("No unticked, valid project beams are available to assign.")
        return

    assignment_results: list[BatchAssignmentResult] = []
    selected_results = []
    for target in targets:
        viable: list[tuple[float, str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for source_id in sorted(source_ids):
            source_record = beam_records.get(source_id)
            source_params = (
                dict(source_record.get("params") or {})
                if isinstance(source_record, dict)
                else {}
            )
            if not source_params:
                rejected.append({"template_id": source_id, "reason": "template input snapshot is unavailable"})
                continue
            try:
                result = ctx.design_brain_adapter.run_case(
                    target,
                    assumptions=workflow.assumptions,
                    base_state=source_params,
                    request_kind="template_assignment",
                )
            except Exception as exc:
                rejected.append({"template_id": source_id, "reason": str(exc)})
                continue
            try:
                utilisation = float(result.utilisation)
            except (TypeError, ValueError):
                utilisation = None
            if result.passed is not True or utilisation is None or utilisation > 1.0:
                rejected.append(
                    {
                        "template_id": source_id,
                        "reason": result.error or "template does not pass the target beam's V2 checks",
                    }
                )
                continue
            viable.append((abs(1.0 - utilisation), source_id, result))

        if not viable:
            assignment_results.append(
                BatchAssignmentResult(
                    member_id=target.member_id,
                    assigned_template_id=None,
                    assigned_label=None,
                    passed=False,
                    reason="No checked beam passed V2 for this target beam's loads.",
                    rejected_candidates=rejected,
                )
            )
            continue

        _, source_id, selected = min(viable, key=lambda candidate: (candidate[0], candidate[1]))
        raw_result = dict(selected.raw_result or {})
        raw_result["auto_design_source_beam_id"] = source_id
        raw_result["auto_design_template_params"] = dict(
            (beam_records.get(source_id) or {}).get("params") or {}
        )
        selected.raw_result = raw_result
        selected_results.append(selected)
        source_label = str((beam_records.get(source_id) or {}).get("beam_label") or source_id)
        assignment_results.append(
            BatchAssignmentResult(
                member_id=target.member_id,
                assigned_template_id=source_id,
                assigned_label=source_label,
                passed=True,
                reason=(
                    f"Applied the checked template with the closest passing V2 utilisation "
                    f"({float(selected.utilisation):.3f})."
                ),
                utilisation=float(selected.utilisation),
                rejected_candidates=rejected,
            )
        )

    workflow.replace_assignment_results(assignment_results)
    st.session_state["batch_design_assignment_results"] = assignment_results
    updated_beam_ids = ctx.publish_batch_design_results(selected_results)
    if updated_beam_ids:
        _rerun_batch_design_page()


def _render_run_design(workflow: BatchDesignWorkflowState, ctx: BatchDesignPageContext) -> None:
    st.markdown("#### Run design")
    blocked = workflow.blocked_run_reasons()
    settings_col_left, settings_col_right = st.columns([1.8, 1.0], gap="medium")
    with settings_col_right:
        summary = workflow.preview_summary()
        st.markdown("##### Run design settings")
        st.caption(f"Included rows: {summary['runnable']} valid / {summary['invalid']} invalid / {summary['reviewed']} ready")
        st.caption("Design mode: Closest utilisation")
        st.caption("Reinforcement source: From project beams")
        st.caption("Validation: Ready to run" if not blocked else "Validation: Setup required")

    with settings_col_left:
        if blocked:
            st.warning(" ".join(blocked))
            st.button("Run design", key="batch_design_run_design_blocked", disabled=True, use_container_width=False)
            st.caption("Runs the batch design for included rows using the current settings.")
            return

        st.caption(f"{len(workflow.runnable_cases())} reviewed row(s) are ready for the Design Brain runner.")
        if ctx.design_brain_adapter is None:
            st.info("Design Brain adapter is not connected for this app session.")
        elif st.button("Run design", key="batch_design_run_design"):
            with st.spinner("Calculating current capacities, then running optimisation..."):
                results = run_reviewed_batch_design(
                    workflow,
                    ctx.design_brain_adapter,
                    assumptions=workflow.assumptions,
                )
            st.session_state["batch_design_design_results"] = results
            failures = [result for result in results if result.passed is False or result.error]
            if failures:
                st.warning(
                    f"Design Brain completed for {len(results)} row(s); "
                    f"{len(failures)} row(s) need review."
                )
            else:
                st.success(f"Design Brain completed for {len(results)} row(s).")
        st.caption("Calculates each current beam capacity first, then optimises included rows.")

    if workflow.design_results:
        passed = len([result for result in workflow.design_results if result.passed is True])
        failed = len([result for result in workflow.design_results if result.passed is False or result.error])
        st.caption(
            f"Latest run: {len(workflow.design_results)} result(s), "
            f"{passed} passing, {failed} needing review."
        )
        render_results_table(st, workflow.design_results)


def _plural_label(count: int, singular: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _workflow_last_updated_text(workflow: BatchDesignWorkflowState) -> str:
    if workflow.design_results:
        return f"{len(workflow.design_results)} result(s)"
    if workflow.assignment_results:
        return f"{len(workflow.assignment_results)} assignment(s)"
    return "Not run yet"


def _batch_workspace_status_text(workflow: BatchDesignWorkflowState) -> str:
    if workflow.design_results:
        return "Results available"
    if workflow.imported_cases:
        return "Ready for review"
    return "Ready for setup"


def _inject_batch_design_workspace_banner_css() -> None:
    st.markdown(
        """
        <style>
        .batch-design-hero {
            display: flex;
            align-items: center;
            gap: 13px;
            width: 100%;
            min-height: 58px;
            padding: 10px 16px;
            margin: 0;
            background: #ffffff;
            border: 1px solid #d9dfeb;
            border-radius: 16px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.055);
            transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
            cursor: pointer;
            /* The real click target is the transparent Streamlit expander
               summary layered over this visual banner. */
            pointer-events: none;
            text-decoration: none !important;
        }
        /* The decorative banner lives in the element immediately before the
           real expander. Let pointer events pass through that whole host
           element, not just the banner's inner div, so the native summary
           receives the click. */
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor) {
            pointer-events: none;
        }
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor)
          + div[data-testid="stLayoutWrapper"] {
            position: relative;
            z-index: 100;
            margin-top: -68px !important;
        }
        .batch-design-hero:hover {
            border-color: #c9d2e3;
            box-shadow: 0 9px 24px rgba(15, 23, 42, 0.075);
            transform: translateY(-1px);
        }
        .batch-design-hero-icon {
            flex: 0 0 auto;
            width: 36px;
            height: 36px;
            display: grid;
            place-items: center;
            border-radius: 10px;
            border: 1px solid #dce3f1;
            background: #f8faff;
            color: #36599f;
            font-size: 20px;
            font-weight: 800;
            line-height: 1;
            box-shadow: inset 0 0 0 1px rgba(54, 89, 159, 0.035);
        }
        .batch-design-hero-main {
            min-width: 0;
            flex: 1 1 auto;
        }
        .batch-design-hero-chips {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .batch-design-hero-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            min-height: 24px;
            padding: 0 9px;
            border-radius: 7px;
            border: 1px solid #d9dfeb;
            background: #fbfcff;
            color: #15223a;
            font-size: 12px;
            font-weight: 760;
            white-space: nowrap;
        }
        .batch-design-hero-chip strong {
            font-weight: 850;
        }
        .batch-design-hero-chip small {
            font-size: 12px;
            font-weight: 780;
        }
        .batch-design-chip-icon {
            display: inline-flex;
            width: 15px;
            height: 15px;
            align-items: center;
            justify-content: center;
            color: currentColor;
        }
        .batch-design-chip-icon svg {
            display: block;
            width: 15px;
            height: 15px;
            stroke: currentColor;
            stroke-width: 2.35;
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .batch-design-chip-blue {
            border-color: #cfddf7;
            background: #f7faff;
            color: #12264d;
        }
        .batch-design-chip-green {
            border-color: #cfe8d8;
            background: #f4fbf6;
            color: #0c5f34;
        }
        .batch-design-chip-cyan {
            border-color: #cbe4f3;
            background: #f6fbfe;
            color: #153a5d;
        }
        .batch-design-chip-orange {
            border-color: #efd4c2;
            background: #fff8f3;
            color: #6f3614;
        }
        .batch-design-chip-grey {
            border-color: #d8dde7;
            background: #f9fafc;
            color: #26344d;
        }
        .batch-design-hero-separator {
            width: 1px;
            align-self: stretch;
            min-height: 27px;
            background: #dce2ec;
            margin: 0 1px 0 2px;
        }
        .batch-design-hero-caret {
            margin-left: auto;
            color: #5b6b84;
            font-size: 16px;
            font-weight: 850;
        }
        /* Each visible chip is a real Streamlit button.  This preserves the
           formatted shell while making every part of it a safe open/close
           target; unlike the former invisible expander, none covers content
           below the banner. */
        div.st-key-batch_design_workspace_shell {
            margin: 0 0 0.85rem 0;
            padding: 9px 13px !important;
            border-radius: 16px !important;
            border-color: #d9dfeb !important;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.055);
        }
        div.st-key-batch_design_workspace_shell button {
            min-height: 28px;
            padding: 0.22rem 0.55rem;
            border-radius: 7px !important;
            font-size: 0.75rem;
            font-weight: 720;
            white-space: nowrap;
        }
        div.st-key-batch_design_workspace_toggle_caret button {
            border: 0 !important;
            background: transparent !important;
            color: #5b6b84 !important;
            font-size: 1rem;
            padding: 0.1rem 0.15rem;
        }
        div.st-key-batch_design_workspace_beams button {
            color: #12264d !important;
            background: #f7faff !important;
            border-color: #cfddf7 !important;
        }
        div.st-key-batch_design_workspace_designed button,
        div.st-key-batch_design_workspace_ready button {
            color: #0c5f34 !important;
            background: #f4fbf6 !important;
            border-color: #cfe8d8 !important;
        }
        div.st-key-batch_design_workspace_assigned button {
            color: #153a5d !important;
            background: #f6fbfe !important;
            border-color: #cbe4f3 !important;
        }
        div.st-key-batch_design_workspace_imported button {
            color: #6f3614 !important;
            background: #fff8f3 !important;
            border-color: #efd4c2 !important;
        }
        div.st-key-batch_design_workspace_constraints button {
            color: #26344d !important;
            background: #f9fafc !important;
            border-color: #d8dde7 !important;
        }
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor)
          + div[data-testid="stLayoutWrapper"] > div[data-testid="stExpander"] details {
            border: 0 !important;
            margin: 0 0 -1.35rem !important;
            position: relative;
            z-index: 5;
            background: transparent !important;
        }
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor)
          + div[data-testid="stLayoutWrapper"] > div[data-testid="stExpander"] details summary {
            min-height: 58px;
            background: transparent !important;
            border: 0 !important;
            border-radius: 16px !important;
            box-shadow: none !important;
            padding: 0 !important;
            opacity: 0;
            cursor: pointer;
        }
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor)
          + div[data-testid="stLayoutWrapper"] > div[data-testid="stExpander"] details summary p {
            color: #101a2d !important;
            font-size: 0.92rem !important;
            font-weight: 760 !important;
            line-height: 1.45;
            white-space: normal;
        }
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor)
          + div[data-testid="stLayoutWrapper"] > div[data-testid="stExpander"] details summary svg {
            color: #5b6b84 !important;
        }
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor)
          + div[data-testid="stLayoutWrapper"] > div[data-testid="stExpander"] details > div {
            border: 1px solid #e2e7f0 !important;
            border-top: 0 !important;
            border-radius: 0 0 16px 16px !important;
            padding-top: 0.85rem !important;
            margin-top: 0 !important;
            background: #ffffff !important;
        }
        @media (max-width: 900px) {
            .batch-design-hero {
                align-items: flex-start;
                min-height: 66px;
                padding: 13px 16px;
                gap: 12px;
            }
            .batch-design-hero-chip {
                font-size: 11px;
                min-height: 26px;
                padding: 0 8px;
            }
            .batch-design-hero-separator {
                display: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _batch_design_workspace_banner_label(
    workflow: BatchDesignWorkflowState,
    *,
    project_beam_count: int,
) -> str:
    summary = workflow.preview_summary()
    status_text = _batch_workspace_status_text(workflow)
    constraints_text = "row issues" if workflow.validation.errors else "none"
    project_beam_label = _plural_label(project_beam_count, "project beam")
    imported_label = f"{summary['imported']} imported actions"
    return (
        f"[>]  Batch design workspace    "
        f"B{project_beam_count} {project_beam_label.split(' ', 1)[1]}  |  "
        f"OK {summary['design_results']} auto designed  |  "
        f"AS {summary['assignment_results']} auto assigned  |  "
        f"D {imported_label}  |  "
        f"{status_text}  |  "
        f"Constraints: {constraints_text}"
    )


def _render_batch_design_workspace_toggle_shell(
    workflow: BatchDesignWorkflowState,
    *,
    project_beam_count: int,
) -> None:
    """Render the coloured Batch shell using only real, local controls."""

    summary = workflow.preview_summary()
    status_text = _batch_workspace_status_text(workflow)
    constraints_text = "row issues" if workflow.validation.errors else "none"
    workspace_open = bool(st.session_state.get(WORKSPACE_OPEN_KEY, False))
    shared_button_args = {
        "type": "secondary",
        "width": "content",
        "on_click": _toggle_batch_design_workspace,
        "help": "Show or hide project beams",
    }
    with st.container(
        border=True,
        horizontal=True,
        vertical_alignment="center",
        gap="small",
        key="batch_design_workspace_shell",
    ):
        st.button(
            "⌃" if workspace_open else "⌄",
            key="batch_design_workspace_toggle_caret",
            **shared_button_args,
        )
        st.button(
            f"▣  B{project_beam_count} project beam{'s' if project_beam_count != 1 else ''}",
            key="batch_design_workspace_beams",
            **shared_button_args,
        )
        st.button(
            f"✓  OK {summary['design_results']} auto designed",
            key="batch_design_workspace_designed",
            **shared_button_args,
        )
        st.button(
            f"♙  AS {summary['assignment_results']} auto assigned",
            key="batch_design_workspace_assigned",
            **shared_button_args,
        )
        st.button(
            f"⇩  D {summary['imported']} imported actions",
            key="batch_design_workspace_imported",
            **shared_button_args,
        )
        st.button(
            f"⚑  {status_text}",
            key="batch_design_workspace_ready",
            **shared_button_args,
        )
        st.button(
            f"◇  Constraints: {constraints_text}",
            key="batch_design_workspace_constraints",
            **shared_button_args,
        )


def _render_batch_design_workspace_banner_visual(
    workflow: BatchDesignWorkflowState,
    *,
    project_beam_count: int,
) -> None:
    summary = workflow.preview_summary()
    status_text = _batch_workspace_status_text(workflow)
    constraints_text = "row issues" if workflow.validation.errors else "none"
    project_beam_label = _plural_label(project_beam_count, "project beam")
    imported_label = f"{summary['imported']} imported actions"
    st.markdown(
        f"""
        <span class="batch-design-workspace-expander-anchor"></span>
        <div class="batch-design-hero" aria-label="Batch design workspace summary">
          <span class="batch-design-hero-icon">[&gt;]</span>
          <span class="batch-design-hero-main">
            <span class="batch-design-hero-chips">
              <span class="batch-design-hero-chip batch-design-chip-blue">
                <span class="batch-design-chip-icon"><svg viewBox="0 0 24 24"><path d="M4 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><path d="M8 21v-4h6v4"/><path d="M8 7h.01M12 7h.01M8 11h.01M12 11h.01M18 9h2v12"/></svg></span><strong>B{project_beam_count}</strong><span>{project_beam_label.split(" ", 1)[1]}</span>
              </span>
              <span class="batch-design-hero-separator"></span>
              <span class="batch-design-hero-chip batch-design-chip-green">
                <span class="batch-design-chip-icon"><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/><circle cx="12" cy="12" r="10"/></svg></span><strong>OK {summary['design_results']}</strong><span>auto designed</span>
              </span>
              <span class="batch-design-hero-chip batch-design-chip-cyan">
                <span class="batch-design-chip-icon"><svg viewBox="0 0 24 24"><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></svg></span><strong>AS {summary['assignment_results']}</strong><span>auto assigned</span>
              </span>
              <span class="batch-design-hero-chip batch-design-chip-orange">
                <span class="batch-design-chip-icon"><svg viewBox="0 0 24 24"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg></span><strong>D {imported_label}</strong>
              </span>
              <span class="batch-design-hero-chip batch-design-chip-green">
                <span class="batch-design-chip-icon"><svg viewBox="0 0 24 24"><path d="M5 22V4"/><path d="M5 4h12l-1 4 1 4H5"/></svg></span><small>{status_text}</small>
              </span>
              <span class="batch-design-hero-chip batch-design-chip-grey">
                <span class="batch-design-chip-icon"><svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/></svg></span><span>Constraints: <strong>{constraints_text}</strong></span>
              </span>
            </span>
          </span>
          <span class="batch-design-hero-caret">v</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_workflow_summary(
    workflow: BatchDesignWorkflowState,
    *,
    project_beam_count: int,
    candidate_beam_count: int,
) -> None:
    summary = workflow.preview_summary()
    status_text = "Ready for setup" if not workflow.design_results else "Results available"
    st.caption(
        "Summary  ·  "
        f"{status_text}  ·  "
        f"{_plural_label(project_beam_count, 'Project beam')}  ·  "
        f"{_plural_label(summary['imported'], 'Imported action')}  ·  "
        f"{_plural_label(candidate_beam_count, 'Candidate beam')}"
    )


def _render_workflow_expanded_metadata(
    workflow: BatchDesignWorkflowState,
    *,
    project_beam_count: int,
    candidate_beam_count: int,
) -> None:
    summary = workflow.preview_summary()
    meta_cols = st.columns(4, gap="medium")
    with meta_cols[0]:
        st.caption("Imported rows")
        st.write(f"{summary['valid']} valid / {summary['invalid']} invalid / {summary['reviewed']} ready")
    with meta_cols[1]:
        st.caption("Candidate beam source")
        st.write("From project beams")
    with meta_cols[2]:
        st.caption("Design mode (default)")
        st.write("Closest utilisation")
    with meta_cols[3]:
        st.caption("Last updated")
        st.write(_workflow_last_updated_text(workflow))
    st.caption("Review the summary above, then configure and run the design workflow.")
    st.caption(
        f"{_plural_label(project_beam_count, 'project beam')} and "
        f"{_plural_label(candidate_beam_count, 'candidate beam')} are available."
    )


def _current_workflow_mode() -> str:
    current_mode = st.session_state.get(WORKFLOW_MODE_KEY, WORKFLOW_MODE_RUN_DESIGN)
    if current_mode not in {WORKFLOW_MODE_RUN_DESIGN, WORKFLOW_MODE_AUTO_ASSIGN}:
        current_mode = WORKFLOW_MODE_RUN_DESIGN
        st.session_state[WORKFLOW_MODE_KEY] = current_mode
    return current_mode


def _render_workflow_mode_selector(ctx: BatchDesignPageContext, workflow: BatchDesignWorkflowState) -> str:
    current_mode = _current_workflow_mode()
    mode_cols = st.columns(2, gap="small")
    with mode_cols[0]:
        st.button(
            WORKFLOW_MODE_RUN_DESIGN,
            key="batch_design_workflow_mode_run_design",
            type="primary" if current_mode == WORKFLOW_MODE_RUN_DESIGN else "secondary",
            use_container_width=True,
            on_click=_request_batch_design_run,
        )
        # A callback runs before the page body, so this durable one-shot
        # request cannot be lost while the Inputs shell rebuilds.
        if st.session_state.pop(RUN_DESIGN_REQUEST_KEY, False):
            current_mode = WORKFLOW_MODE_RUN_DESIGN
            st.session_state[WORKFLOW_MODE_KEY] = current_mode
            _run_batch_design_now(workflow, ctx)
    with mode_cols[1]:
        auto_assign_clicked = st.button(
            WORKFLOW_MODE_AUTO_ASSIGN,
            key="batch_design_workflow_mode_auto_assign",
            type="primary" if current_mode == WORKFLOW_MODE_AUTO_ASSIGN else "secondary",
            use_container_width=True,
        )
        # This control is a command, not a navigation control.  It must be
        # handled in the button's own render pass: fragment callbacks can run
        # outside the parent Inputs fragment and lose a queued request before
        # this coordinator sees it.  The direct branch is the same dependable
        # pattern used by the Run design command above.
        if auto_assign_clicked:
            current_mode = WORKFLOW_MODE_AUTO_ASSIGN
            st.session_state[WORKFLOW_MODE_KEY] = current_mode
            _run_auto_assign_now(workflow, ctx)
    return current_mode


def _render_auto_assign_hint() -> None:
    if st.button(
        "Auto assign  -  Assign candidate beams to project beams.  v",
        key="batch_design_auto_assign_hint",
        use_container_width=True,
    ):
        st.session_state[WORKFLOW_MODE_KEY] = WORKFLOW_MODE_AUTO_ASSIGN
        _rerun_batch_design_page()


def _render_design_workflow_card(ctx: BatchDesignPageContext, workflow: BatchDesignWorkflowState) -> None:
    st.markdown("### Design workflow")
    schedule_export_df = ctx.build_schedule_export_df()
    project_beam_count = len(ctx.beam_order or [])
    candidate_beam_count = len(project_beam_templates_from_frame(schedule_export_df))
    _render_workflow_summary(
        workflow,
        project_beam_count=project_beam_count,
        candidate_beam_count=candidate_beam_count,
    )
    _render_workflow_expanded_metadata(
        workflow,
        project_beam_count=project_beam_count,
        candidate_beam_count=candidate_beam_count,
    )
    mode = _current_workflow_mode()
    if mode == WORKFLOW_MODE_AUTO_ASSIGN:
        render_assignment_panel(
            st,
            workflow=workflow,
            selected_template_count=sum(
                1
                for record in (st.session_state.get("beam_records") or {}).values()
                if isinstance(record, dict)
                and bool((record.get("meta") or {}).get("use_for_auto_design", False))
            ),
            target_count=sum(
                1
                for case in workflow.runnable_cases()
                if str(case.member_id or "") not in {
                    str(beam_id)
                    for beam_id, record in (st.session_state.get("beam_records") or {}).items()
                    if isinstance(record, dict)
                    and bool((record.get("meta") or {}).get("use_for_auto_design", False))
                }
            ),
            on_auto_assign=lambda: _run_auto_assign_now(workflow, ctx),
        )
    else:
        _render_run_design(workflow, ctx)
        _render_auto_assign_hint()


def _render_results_export(workflow: BatchDesignWorkflowState) -> None:
    st.markdown("### Results & export")
    if workflow.design_results:
        render_results_table(st, workflow.design_results)
    else:
        st.caption("Batch result export is owned by the batch_design package.")


def render_batch_design_page(ctx: BatchDesignPageContext) -> None:
    workflow = get_batch_design_workflow_state(st.session_state)
    _inject_batch_design_workspace_banner_css()
    st.markdown("## Batch design")
    _render_batch_design_workspace_toggle_shell(
        workflow,
        project_beam_count=len(ctx.beam_order or []),
    )
    workspace_open = bool(st.session_state.get(WORKSPACE_OPEN_KEY, False))
    # The shell is made of real controls, not a decorative HTML card or
    # invisible expander overlay, so it can open and close without stealing
    # clicks from the project-beam controls below.
    if workspace_open:
        with st.container(border=True):
            _render_project_beam_design_editor(ctx, workflow)
    st.markdown("<div style='height: 0.85rem;'></div>", unsafe_allow_html=True)
