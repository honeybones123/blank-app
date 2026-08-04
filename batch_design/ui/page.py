"""Streamlit page renderer for Batch Design."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from batch_design.importers.spacegass_excel import SpaceGassExcelImporter
from batch_design.runner import DesignBrainAdapter, run_reviewed_batch_design
from batch_design.store import BatchDesignWorkflowState
from batch_design.ui.assignment_panel import render_assignment_panel
from batch_design.ui.import_panel import render_import_panel
from batch_design.ui.preview_table import render_preview_table
from batch_design.ui.project_beam_load_table import (
    ACTION_COLUMNS,
    ACTION_LABELS,
    apply_project_beam_load_editor_rows,
    project_beam_load_editor_frame,
    project_beam_templates_from_frame,
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
WORKFLOW_SUMMARY_EXPANDED_KEY = "batch_design_workflow_summary_expanded"
WORKFLOW_MODE_KEY = "batch_design_workflow_mode"
WORKFLOW_MODE_RUN_DESIGN = "Run design"
WORKFLOW_MODE_AUTO_ASSIGN = "Auto assign"


def get_batch_design_workflow_state(session_state: MutableMapping[str, Any] | None = None) -> BatchDesignWorkflowState:
    state = st.session_state if session_state is None else session_state
    workflow = state.get(WORKFLOW_STATE_KEY)
    if not isinstance(workflow, BatchDesignWorkflowState):
        workflow = BatchDesignWorkflowState()
        state[WORKFLOW_STATE_KEY] = workflow
    return workflow


def _render_project_beam_controls(ctx: BatchDesignPageContext) -> None:
    active_beam_id = ctx.active_beam_id
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
            selected_beam_id = st.selectbox(
                "Active set",
                options=beam_order,
                index=beam_order.index(active_beam_id) if active_beam_id in beam_order else 0,
                format_func=lambda beam_id: ctx.beam_labels.get(beam_id, beam_id),
                key="beam_manager_active_selector",
                help="Select the project beam used as the base concrete assumptions for manual batch rows.",
            )
            if selected_beam_id != active_beam_id and ctx.set_active_beam(selected_beam_id):
                ctx.force_refresh("beam_selector_change")
                ctx.log_rerun("beam_selector_change")
                st.rerun()
        else:
            st.caption("No stored project beams yet.")

    with spacer_col:
        st.empty()

    with add_beam_col:
        if st.button("+ Add", key="beam_manager_add_button", use_container_width=True):
            ctx.add_beam()
            ctx.force_refresh("add_beam")
            ctx.log_rerun("add_beam")
            st.rerun()

    with dup_beam_col:
        if st.button("Duplicate", key="beam_manager_duplicate_button", use_container_width=True):
            ctx.duplicate_beam()
            ctx.force_refresh("duplicate_beam")
            ctx.log_rerun("duplicate_beam")
            st.rerun()

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
            st.rerun()

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
            st.rerun()


def _render_project_beam_design_editor(ctx: BatchDesignPageContext, workflow: BatchDesignWorkflowState) -> None:
    st.markdown("### Project beams")
    _render_project_beam_controls(ctx)

    schedule_df = ctx.build_schedule_editor_df()
    if schedule_df is None or schedule_df.empty:
        st.caption("No project beams are available yet.")
        return

    editor_df = project_beam_load_editor_frame(schedule_df, workflow)
    visible_columns = [
        "active",
        "beam_id",
        "capacity_status",
        "beam_label",
        "sec_shape",
        "b",
        "D",
        "L",
        *ACTION_COLUMNS,
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

    edited_schedule_df = st.data_editor(
        editor_df,
        key="batch_design_project_beam_reo_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_order=visible_columns,
        disabled=["active", "beam_id", "capacity_status"],
        column_config={
            "active": st.column_config.TextColumn("Active", disabled=True),
            "beam_id": st.column_config.TextColumn("Beam ID", disabled=True),
            "capacity_status": st.column_config.TextColumn("Capacity", disabled=True),
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

    summary = workflow.preview_summary()
    status_col, apply_col, save_col = st.columns([2.7, 1.25, 1.5], gap="medium", vertical_alignment="center")
    with status_col:
        st.caption(
            f"{summary['valid']} valid load row(s), {summary['invalid']} invalid, "
            f"{summary['reviewed']} ready for design."
        )
    with apply_col:
        if st.button("Apply Beam/Reo/Load Edits", key="batch_design_apply_project_beam_reo_edits", use_container_width=True):
            changed_beam_ids = ctx.sync_schedule_editor_df(edited_schedule_df)
            apply_project_beam_load_editor_rows(workflow, edited_schedule_df)
            st.session_state["batch_design_imported_rows"] = workflow.imported_cases
            st.session_state["batch_design_import_errors"] = workflow.validation.errors
            st.session_state["batch_design_import_warnings"] = workflow.validation.warnings
            if ctx.active_beam_id in changed_beam_ids:
                st.session_state["_beam_skip_auto_persist_once"] = True
            ctx.force_refresh("batch_design_project_beam_reo_edits")
            ctx.log_rerun("batch_design_project_beam_reo_edits")
            st.rerun()
    with save_col:
        if st.button("Save Active Beam Back To Table", key="batch_design_save_active_beam_to_table", use_container_width=True):
            ctx.save_active_to_table()
            ctx.force_refresh("batch_design_save_active_beam_to_table")
            ctx.log_rerun("batch_design_save_active_beam_to_table")
            st.rerun()

    if workflow.validation.errors:
        st.warning(f"{len(workflow.validation.errors)} load issue(s) must be fixed before design.")


def _render_import_workflow(workflow: BatchDesignWorkflowState) -> None:
    st.markdown("### Import final member actions")
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
            with st.spinner("Running Design Brain for reviewed batch rows..."):
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
        st.caption("Runs the batch design for included rows using the current settings.")

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
            text-decoration: none !important;
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
        div[data-testid="stElementContainer"]:has(.batch-design-workspace-expander-anchor)
          + div[data-testid="stLayoutWrapper"] > div[data-testid="stExpander"] details {
            border: 0 !important;
            margin: -68px 0 -1.35rem !important;
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
        <div class="batch-design-hero" role="button" aria-label="Toggle Batch design workspace">
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


def _render_workflow_summary_banner(
    workflow: BatchDesignWorkflowState,
    *,
    project_beam_count: int,
    candidate_beam_count: int,
) -> bool:
    expanded = bool(st.session_state.get(WORKFLOW_SUMMARY_EXPANDED_KEY, False))
    summary = workflow.preview_summary()
    status_text = "Ready for setup" if not workflow.design_results else "Results available"
    caret = "^" if expanded else "v"
    label = (
        f"[ ]  Summary  |  {status_text}  |  "
        f"{_plural_label(project_beam_count, 'Project beam')}  |  "
        f"{_plural_label(summary['imported'], 'Imported action')}  |  "
        f"{_plural_label(candidate_beam_count, 'Candidate beam')}  |  {caret}"
    )
    if st.button(label, key="batch_design_workflow_summary_toggle", use_container_width=True):
        expanded = not expanded
        st.session_state[WORKFLOW_SUMMARY_EXPANDED_KEY] = expanded
        st.rerun()
    return expanded


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


def _render_workflow_mode_selector() -> str:
    current_mode = st.session_state.get(WORKFLOW_MODE_KEY, WORKFLOW_MODE_RUN_DESIGN)
    if current_mode not in {WORKFLOW_MODE_RUN_DESIGN, WORKFLOW_MODE_AUTO_ASSIGN}:
        current_mode = WORKFLOW_MODE_RUN_DESIGN
        st.session_state[WORKFLOW_MODE_KEY] = current_mode
    mode_cols = st.columns(2, gap="small")
    with mode_cols[0]:
        if st.button(
            WORKFLOW_MODE_RUN_DESIGN,
            key="batch_design_workflow_mode_run_design",
            type="primary" if current_mode == WORKFLOW_MODE_RUN_DESIGN else "secondary",
            use_container_width=True,
        ):
            current_mode = WORKFLOW_MODE_RUN_DESIGN
            st.session_state[WORKFLOW_MODE_KEY] = current_mode
    with mode_cols[1]:
        if st.button(
            WORKFLOW_MODE_AUTO_ASSIGN,
            key="batch_design_workflow_mode_auto_assign",
            type="primary" if current_mode == WORKFLOW_MODE_AUTO_ASSIGN else "secondary",
            use_container_width=True,
        ):
            current_mode = WORKFLOW_MODE_AUTO_ASSIGN
            st.session_state[WORKFLOW_MODE_KEY] = current_mode
    return current_mode


def _render_auto_assign_hint() -> None:
    if st.button(
        "Auto assign  -  Assign candidate beams to project beams.  v",
        key="batch_design_auto_assign_hint",
        use_container_width=True,
    ):
        st.session_state[WORKFLOW_MODE_KEY] = WORKFLOW_MODE_AUTO_ASSIGN
        st.rerun()


def _render_design_workflow_card(ctx: BatchDesignPageContext, workflow: BatchDesignWorkflowState) -> None:
    st.markdown("### Design workflow")
    schedule_export_df = ctx.build_schedule_export_df()
    project_beam_count = len(ctx.beam_order or [])
    candidate_beam_count = len(project_beam_templates_from_frame(schedule_export_df))
    expanded = _render_workflow_summary_banner(
        workflow,
        project_beam_count=project_beam_count,
        candidate_beam_count=candidate_beam_count,
    )
    if not expanded:
        return

    _render_workflow_expanded_metadata(
        workflow,
        project_beam_count=project_beam_count,
        candidate_beam_count=candidate_beam_count,
    )
    mode = _render_workflow_mode_selector()
    if mode == WORKFLOW_MODE_AUTO_ASSIGN:
        render_assignment_panel(
            st,
            workflow=workflow,
            current_project_templates=project_beam_templates_from_frame(schedule_export_df),
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
    _render_batch_design_workspace_banner_visual(
        workflow,
        project_beam_count=len(ctx.beam_order or []),
    )

    with st.expander(
        _batch_design_workspace_banner_label(
            workflow,
            project_beam_count=len(ctx.beam_order or []),
        ),
        expanded=False,
    ):
        with st.container(border=True):
            with st.container(border=True):
                _render_project_beam_design_editor(ctx, workflow)
            with st.container(border=True):
                _render_import_workflow(workflow)
            with st.container(border=True):
                _render_design_workflow_card(ctx, workflow)
            with st.container(border=True):
                _render_results_export(workflow)
    st.markdown("<div style='height: 0.85rem;'></div>", unsafe_allow_html=True)
