"""Inputs widget render-section orchestration."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_page_modules.fragments import rerun_inputs_current_scope


def _rerun_inputs_fragment_or_app(st_module: Any) -> None:
    """Prefer a local fragment rerun, with compatibility for older Streamlit."""
    rerun_inputs_current_scope(st_module)


def _render_inputs_widget_subfragment(
    *,
    section_fn: Callable[..., Any],
    section_kwargs: dict[str, Any],
) -> Any:
    """Stable child-fragment entry point for one independent input section."""

    return section_fn(**section_kwargs)


def render_inputs_widget_sections(
    *,
    st_module: Any,
    ss: dict,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    inputs_render_audit: dict[str, str],
    fast_focus_section: str | None,
    fast_get_param,
    corrected_invalid_shear_state: bool,
    mark: Callable[[str], None],
    sub_mark: Callable[[str], None],
    run_fragment_fn: Callable[..., Any],
    render_diagram_fragment_fn: Callable[..., Any] | None = None,
    top_section_layout_slots_fn: Callable[..., tuple],
    design_actions_section_fn: Callable[..., None],
    geometry_materials_top_section_fn: Callable[..., None],
    create_reinforcement_columns_fn: Callable[[], tuple],
    get_section_shape_for_reinforcement_fn: Callable[[], str],
    normalized_sec_shape_fn: Callable[[str], str],
    longitudinal_pair_labels_fn: Callable[..., tuple[str, str]],
    bottom_reinforcement_column_fn: Callable[..., None],
    top_reinforcement_column_fn: Callable[..., None],
    shear_reinforcement_column_fn: Callable[..., None],
    flange_reinforcement_fn: Callable[..., None],
    detailed_support_lower_row_fn: Callable[..., None],
    post_widget_autopersist_fn: Callable[..., bool],
):
    render_started_ns = time.perf_counter_ns()
    render_start_revision = int(
        InputSnapshotStore(st_module.session_state).current().revision or 0
    )
    # Retain the injectable child-render hook as a compatibility seam while
    # keeping diagram rendering in the parent workspace boundary.
    _ = run_fragment_fn
    section_timings_ms: dict[str, float] = {}
    def render_section(
        fragment_name: str,
        section_fn: Callable[..., Any],
        **section_kwargs: Any,
    ) -> Any:
        section_started_ns = time.perf_counter_ns()
        if callable(run_fragment_fn):
            result = run_fragment_fn(
                st_module=st_module,
                fragment_name=f"engineering_input_section_{fragment_name}",
                render_fn=section_fn,
                kwargs=section_kwargs,
            )
        else:
            result = _render_inputs_widget_subfragment(
                section_fn=section_fn,
                section_kwargs=section_kwargs,
            )
        section_timings_ms[fragment_name] = round(
            (time.perf_counter_ns() - section_started_ns) / 1_000_000,
            3,
        )
        return result

    (
        bottom_slot,
        shear_slot,
        model_slot,
        actions_slot,
        geometry_slot,
        right_diagram,
    ) = top_section_layout_slots_fn(
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        inputs_render_audit=inputs_render_audit,
        fast_focus_section=fast_focus_section,
        mark=mark,
    )
    _ = bottom_slot
    _ = shear_slot

    render_section(
        "design_actions",
        design_actions_section_fn,
        actions_slot=actions_slot,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        sub_mark=sub_mark,
    )

    render_section(
        "geometry_materials",
        geometry_materials_top_section_fn,
        geometry_slot=geometry_slot,
        right_diagram=right_diagram,
        model_slot=model_slot,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        mark=mark,
        sub_mark=sub_mark,
    )

    col_bot_reo, col_top_reo, col_shear_mat = create_reinforcement_columns_fn()
    sec_shape_reo_ui = get_section_shape_for_reinforcement_fn()
    is_ti_reo_ui = normalized_sec_shape_fn(sec_shape_reo_ui) in ("T", "I")
    bot_hdr, top_hdr = longitudinal_pair_labels_fn(
        sec_shape_reo_ui,
        variant="inputs_compact" if not inputs_detailed_mode else "inputs_detailed",
    )
    # Keep the Inputs page's primary reinforcement sections aligned with the
    # other H2 sections while using clear, user-facing names.
    bot_hdr = "Bottom Reinforcement"
    top_hdr = "Top Reinforcement"

    render_section(
        "bottom_reinforcement",
        bottom_reinforcement_column_fn,
        col_bot_reo=col_bot_reo,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        sec_shape_reo_ui=sec_shape_reo_ui,
        is_ti_reo_ui=bool(is_ti_reo_ui),
        bot_hdr=bot_hdr,
    )

    render_section(
        "top_reinforcement",
        top_reinforcement_column_fn,
        col_top_reo=col_top_reo,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        sec_shape_reo_ui=sec_shape_reo_ui,
        is_ti_reo_ui=bool(is_ti_reo_ui),
        top_hdr=top_hdr,
    )

    render_section(
        "shear_reinforcement",
        shear_reinforcement_column_fn,
        col_shear_mat=col_shear_mat,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        fast_focus_section=fast_focus_section,
        corrected_invalid_shear_state=bool(corrected_invalid_shear_state),
        sync_callbacks=sync_callbacks,
    )

    render_section(
        "flange_reinforcement",
        flange_reinforcement_fn,
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
    )
    render_section(
        "detailed_support",
        detailed_support_lower_row_fn,
        inputs_detailed_mode=bool(inputs_detailed_mode),
        sync_callbacks=sync_callbacks,
        fast_get_param=fast_get_param,
        mark=mark,
        sub_mark=sub_mark,
    )
    # Render the input preview after all widget sections have reconciled their
    # callbacks.  The diagram remains in the same right-hand model slot, but
    # it now receives the final committed snapshot for this page transaction;
    # it cannot publish a one-revision-behind Plotly figure.
    if callable(render_diagram_fragment_fn):
        render_diagram_fragment_fn(
            inputs_detailed_mode=bool(inputs_detailed_mode),
            sync_callbacks=sync_callbacks,
            right_diagram=right_diagram,
            model_slot=model_slot,
        )

    # A Streamlit widget callback may commit while this render is already in
    # flight. In that case the just-emitted diagram belonged to the previous
    # revision. Schedule one bounded settle rerun so the visible diagram and
    # summaries are guaranteed to share the final transaction; the next pass
    # starts at the same revision and does not rerun again.
    settled_revision = int(
        InputSnapshotStore(st_module.session_state).current().revision or 0
    )
    if settled_revision > render_start_revision:
        fragments_disabled = str(
            os.environ.get("CODEX_ENABLE_INPUTS_FRAGMENTS", "0")
        ).strip().lower() in {"0", "false", "no", "off"}
        st_module.session_state["_inputs_diagram_settle_revision"] = settled_revision
        # In the V2-shaped full-page path, do not interrupt this render from
        # inside the widget coordinator.  The page shell owns the single
        # bounded settle pass after all sibling regions have completed; an
        # in-flight rerun here can terminate before the latest diagram identity
        # is published and leave the old Plotly frame visible.  Preserve the
        # explicit legacy-fragment behaviour for rollback/measurement mode.
        if not fragments_disabled:
            rerun_inputs_current_scope(st_module)

    autopersist_started_ns = time.perf_counter_ns()
    result = post_widget_autopersist_fn(ss=ss)
    section_timings_ms["post_widget_autopersist"] = round(
        (time.perf_counter_ns() - autopersist_started_ns) / 1_000_000,
        3,
    )
    ss["_inputs_widget_section_timings_ms"] = {
        "sections": section_timings_ms,
        "total": round(
            (time.perf_counter_ns() - render_started_ns) / 1_000_000,
            3,
        ),
    }
    return result


def render_inputs_top_reinforcement_column(
    *,
    st_module: Any,
    col_top_reo,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    sec_shape_reo_ui,
    is_ti_reo_ui: bool,
    top_hdr: str,
    longitudinal_reo_widget_audit_snapshot_fn: Callable[[str], Any],
    get_widget_key_for_shared_fn: Callable[..., str | None],
    seed_widget_from_shared_fn: Callable[..., None],
    recommendation_section_header_fn: Callable[..., None],
    render_longitudinal_reo_row_config_controls_fn: Callable[..., None],
    render_longitudinal_reo_rows_fn: Callable[..., None],
    number_row_fn: Callable[..., None],
    reo_layout_mode: list,
    reo_counts_0_12: list,
    reo_spacings: list,
    reo_bar_dias: list,
) -> None:
    _ = inputs_detailed_mode
    with col_top_reo:
        longitudinal_reo_widget_audit_snapshot_fn("before_longitudinal_widget_render_top")
        w_rowgap_top = get_widget_key_for_shared_fn("rowgap_top", prefix="inputs_") or "inputs_rowgap_top"
        seed_widget_from_shared_fn(w_rowgap_top, "rowgap_top", 60.0)
        rowgap_top_val = float(
            st_module.session_state.get(
                w_rowgap_top,
                st_module.session_state.get("rowgap_top", 60.0),
            )
        )

        recommendation_section_header_fn(
            top_hdr,
            help_text=(
                "Top web longitudinal reinforcement for hogging, load reversal, or compression-side layers "
                "(T/I: stem/web steel, not flange bars). Uses the same row layout model as bottom reinforcement."
            ),
            level="h2",
            render_popover_content=lambda: (
                st_module.markdown(
                    "Edit top web bars directly here; values stay in sync with bending, section, and crack checks. "
                    "There is no separate automated top-reo suggestion on this page yet."
                )
            ),
            render_popover_always=lambda: render_longitudinal_reo_row_config_controls_fn(
                page_prefix="inputs",
                section="top",
                sync_callbacks=sync_callbacks,
                rowgap_widget_key=w_rowgap_top,
                rowgap_default=rowgap_top_val,
                rowgap_help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
                sec_shape=sec_shape_reo_ui,
            ),
        )
        render_longitudinal_reo_rows_fn(
            page_prefix="inputs",
            section="top",
            sync_callbacks=sync_callbacks,
            layout_modes=reo_layout_mode,
            count_options=reo_counts_0_12,
            spacing_options=reo_spacings,
            dia_options=reo_bar_dias,
            single_column=True,
            sec_shape=sec_shape_reo_ui,
        )

        cover_top_val = float(
            st_module.session_state.get(
                "inputs_cover_top",
                fast_get_param("cover_top", 40.0),
            )
        )
        number_row_fn(
            "Top cover (mm)",
            "inputs_cover_top",
            cover_top_val,
            sync_callbacks,
            help_text=(
                "Clear cover to the top web bars. For T/I sections, flange top cover is set with flange reinforcement."
                if is_ti_reo_ui
                else "Clear cover to the top bars."
            ),
        )


def render_inputs_bottom_reinforcement_column(
    *,
    st_module: Any,
    col_bot_reo,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    sec_shape_reo_ui,
    is_ti_reo_ui: bool,
    bot_hdr: str,
    longitudinal_reo_widget_audit_snapshot_fn: Callable[[str], Any],
    get_widget_key_for_shared_fn: Callable[..., str | None],
    seed_widget_from_shared_fn: Callable[..., None],
    recommendation_section_header_fn: Callable[..., None],
    bottom_recommendation_panel_fn: Callable[..., None],
    render_longitudinal_reo_row_config_controls_fn: Callable[..., None],
    agent_debug_log_fn: Callable[..., None],
    render_longitudinal_reo_rows_fn: Callable[..., None],
    number_row_fn: Callable[..., None],
    reo_layout_mode: list,
    reo_counts_0_12: list,
    reo_spacings: list,
    reo_bar_dias: list,
) -> None:
    with col_bot_reo:
        longitudinal_reo_widget_audit_snapshot_fn("before_longitudinal_widget_render")
        w_rowgap_bot = get_widget_key_for_shared_fn("rowgap_bot", prefix="inputs_") or "inputs_rowgap_bot"
        seed_widget_from_shared_fn(w_rowgap_bot, "rowgap_bot", 60.0)
        rowgap_bot_val = float(st_module.session_state.get(w_rowgap_bot, fast_get_param("rowgap_bot", 60.0)))

        recommendation_section_header_fn(
            bot_hdr,
            help_text=(
                "Show the current bottom (web) reinforcement recommendation, the optimisation goal, "
                "the predicted impact, and apply the suggested arrangement. "
                "For T and I sections this is web steel, not flange bars."
            ),
            level="h2",
            render_popover_content=lambda: bottom_recommendation_panel_fn(
                button_key="inputs_apply_bottom_recommendation",
                source="fast_mode:bottom_recommendation" if not inputs_detailed_mode else "detailed_mode:bottom_recommendation",
                compact=not inputs_detailed_mode,
            ),
            render_popover_always=lambda: render_longitudinal_reo_row_config_controls_fn(
                page_prefix="inputs",
                section="bot",
                sync_callbacks=sync_callbacks,
                rowgap_widget_key=w_rowgap_bot,
                rowgap_default=rowgap_bot_val,
                rowgap_help_text="Clear vertical gap between Layer 1 and Layer 2 (mm).",
                sec_shape=sec_shape_reo_ui,
            ),
        )
        if bool(st_module.session_state.get("_dev_mode")):
            agent_debug_log_fn(
                "Bottom reo live snapshot before row widgets (dev)",
                {
                    "shared": {
                        "bot1_count": st_module.session_state.get("bot1_count"),
                        "db_bot_1": st_module.session_state.get("db_bot_1"),
                        "bot_row_1_bars": st_module.session_state.get("bot_row_1_bars"),
                        "bot_row_1_dia": st_module.session_state.get("bot_row_1_dia"),
                    },
                    "widget": {
                        "inputs_bot1_count": st_module.session_state.get("inputs_bot1_count"),
                        "inputs_db_bot_1": st_module.session_state.get("inputs_db_bot_1"),
                        "inputs_bot_row_1_bars": st_module.session_state.get("inputs_bot_row_1_bars"),
                        "inputs_bot_row_1_dia": st_module.session_state.get("inputs_bot_row_1_dia"),
                    },
                },
                location="inputs_page.py:render_inputs:before_bottom_reo_rows",
                hypothesis_id="H_BOT_REO_WIDGET_ALIGN",
            )
        render_longitudinal_reo_rows_fn(
            page_prefix="inputs",
            section="bot",
            sync_callbacks=sync_callbacks,
            layout_modes=reo_layout_mode,
            count_options=reo_counts_0_12,
            spacing_options=reo_spacings,
            dia_options=reo_bar_dias,
            single_column=True,
            sec_shape=sec_shape_reo_ui,
        )

        cover_bot_val = float(st_module.session_state.get("inputs_cover_bot", fast_get_param("cover_bot", 40.0)))
        number_row_fn(
            "Bottom cover (mm)",
            "inputs_cover_bot",
            cover_bot_val,
            sync_callbacks,
            help_text=(
                "Clear cover to the bottom web bars. "
                "For T/I sections, flange bottom cover is set with bottom flange reinforcement."
                if is_ti_reo_ui
                else "Clear cover to the bottom bars."
            ),
        )


def render_inputs_flange_reinforcement(
    *,
    st_module: Any,
    sync_callbacks: dict,
    fast_get_param,
    select_row_fn: Callable[..., None],
    number_row_fn: Callable[..., None],
    reo_bar_dias: list,
) -> None:
    ss = st_module.session_state
    sec_shape_for_flange = str(ss.get("sec_shape", fast_get_param("sec_shape", "RECT")) or "RECT")
    if sec_shape_for_flange in ("T", "I"):
        st_module.markdown("### Flange reinforcement")
        st_module.caption("Only used for T and I sections. Flange groups are resolved into real bar coordinates for crack/shear participation.")
        flange_col_a, flange_col_b = st_module.columns(2, gap="large")
        with flange_col_a:
            select_row_fn(
                "Enable top flange bars",
                "inputs_top_flange_reo_enabled",
                [False, True],
                bool(ss.get("top_flange_reo_enabled", False)),
                sync_callbacks,
                help_text="Enable explicit top flange reinforcement groups.",
            )
            select_row_fn(
                "Mirror top left/right",
                "inputs_top_flange_mirror_lr",
                [True, False],
                bool(ss.get("top_flange_mirror_lr", True)),
                sync_callbacks,
                help_text="When enabled, the right-side top flange group mirrors the left-side values.",
            )
            number_row_fn("Top flange left bars", "inputs_top_flange_left_count", float(ss.get("top_flange_left_count", 0) or 0), sync_callbacks, help_text="Total bars in top-left flange group.")
            select_row_fn("Top flange left dia (mm)", "inputs_top_flange_left_dia", reo_bar_dias, int(ss.get("top_flange_left_dia", 16) or 16), sync_callbacks)
            number_row_fn("Top flange left rows", "inputs_top_flange_left_rows", float(ss.get("top_flange_left_rows", 1) or 1), sync_callbacks)
            number_row_fn("Top flange left row spacing (mm)", "inputs_top_flange_left_row_spacing", float(ss.get("top_flange_left_row_spacing", 60.0) or 60.0), sync_callbacks)
            select_row_fn(
                "Top flange left clear spacing mode",
                "inputs_top_flange_left_clear_spacing_mode",
                ["count", "spacing"],
                str(ss.get("top_flange_left_clear_spacing_mode", "count") or "count"),
                sync_callbacks,
            )
            if not bool(ss.get("top_flange_mirror_lr", True)):
                number_row_fn("Top flange right bars", "inputs_top_flange_right_count", float(ss.get("top_flange_right_count", 0) or 0), sync_callbacks)
                select_row_fn("Top flange right dia (mm)", "inputs_top_flange_right_dia", reo_bar_dias, int(ss.get("top_flange_right_dia", 16) or 16), sync_callbacks)
                number_row_fn("Top flange right rows", "inputs_top_flange_right_rows", float(ss.get("top_flange_right_rows", 1) or 1), sync_callbacks)
                number_row_fn("Top flange right row spacing (mm)", "inputs_top_flange_right_row_spacing", float(ss.get("top_flange_right_row_spacing", 60.0) or 60.0), sync_callbacks)
                select_row_fn(
                    "Top flange right clear spacing mode",
                    "inputs_top_flange_right_clear_spacing_mode",
                    ["count", "spacing"],
                    str(ss.get("top_flange_right_clear_spacing_mode", "count") or "count"),
                    sync_callbacks,
                )
        with flange_col_b:
            select_row_fn(
                "Enable bottom flange bars",
                "inputs_bot_flange_reo_enabled",
                [False, True],
                bool(ss.get("bot_flange_reo_enabled", False)),
                sync_callbacks,
                help_text="Enable explicit bottom flange reinforcement groups (I-sections only; ignored for T bottom flange).",
            )
            select_row_fn(
                "Mirror bottom left/right",
                "inputs_bot_flange_mirror_lr",
                [True, False],
                bool(ss.get("bot_flange_mirror_lr", True)),
                sync_callbacks,
                help_text="When enabled, the right-side bottom flange group mirrors the left-side values.",
            )
            number_row_fn("Bottom flange left bars", "inputs_bot_flange_left_count", float(ss.get("bot_flange_left_count", 0) or 0), sync_callbacks)
            select_row_fn("Bottom flange left dia (mm)", "inputs_bot_flange_left_dia", reo_bar_dias, int(ss.get("bot_flange_left_dia", 20) or 20), sync_callbacks)
            number_row_fn("Bottom flange left rows", "inputs_bot_flange_left_rows", float(ss.get("bot_flange_left_rows", 1) or 1), sync_callbacks)
            number_row_fn("Bottom flange left row spacing (mm)", "inputs_bot_flange_left_row_spacing", float(ss.get("bot_flange_left_row_spacing", 60.0) or 60.0), sync_callbacks)
            select_row_fn(
                "Bottom flange left clear spacing mode",
                "inputs_bot_flange_left_clear_spacing_mode",
                ["count", "spacing"],
                str(ss.get("bot_flange_left_clear_spacing_mode", "count") or "count"),
                sync_callbacks,
            )
            if not bool(ss.get("bot_flange_mirror_lr", True)):
                number_row_fn("Bottom flange right bars", "inputs_bot_flange_right_count", float(ss.get("bot_flange_right_count", 0) or 0), sync_callbacks)
                select_row_fn("Bottom flange right dia (mm)", "inputs_bot_flange_right_dia", reo_bar_dias, int(ss.get("bot_flange_right_dia", 20) or 20), sync_callbacks)
                number_row_fn("Bottom flange right rows", "inputs_bot_flange_right_rows", float(ss.get("bot_flange_right_rows", 1) or 1), sync_callbacks)
                number_row_fn("Bottom flange right row spacing (mm)", "inputs_bot_flange_right_row_spacing", float(ss.get("bot_flange_right_row_spacing", 60.0) or 60.0), sync_callbacks)
                select_row_fn(
                    "Bottom flange right clear spacing mode",
                    "inputs_bot_flange_right_clear_spacing_mode",
                    ["count", "spacing"],
                    str(ss.get("bot_flange_right_clear_spacing_mode", "count") or "count"),
                    sync_callbacks,
                )
        st_module.markdown("#### Flange transverse detailing (optional)")
        st_module.caption("Detailing/distribution reinforcement in flange regions only. Not used in primary web shear capacity.")
        tr_col1, tr_col2 = st_module.columns(2, gap="large")
        with tr_col1:
            select_row_fn("Enable top flange transverse", "inputs_top_flange_transverse_enabled", [False, True], bool(ss.get("top_flange_transverse_enabled", False)), sync_callbacks)
            select_row_fn("Top flange transverse dia (mm)", "inputs_top_flange_transverse_dia", reo_bar_dias, int(ss.get("top_flange_transverse_dia", 10) or 10), sync_callbacks)
            number_row_fn("Top flange transverse spacing (mm)", "inputs_top_flange_transverse_spacing", float(ss.get("top_flange_transverse_spacing", 200.0) or 200.0), sync_callbacks)
            number_row_fn("Top flange transverse legs", "inputs_top_flange_transverse_legs", float(ss.get("top_flange_transverse_legs", 2) or 2), sync_callbacks)
        with tr_col2:
            select_row_fn("Enable bottom flange transverse", "inputs_bot_flange_transverse_enabled", [False, True], bool(ss.get("bot_flange_transverse_enabled", False)), sync_callbacks)
            select_row_fn("Bottom flange transverse dia (mm)", "inputs_bot_flange_transverse_dia", reo_bar_dias, int(ss.get("bot_flange_transverse_dia", 10) or 10), sync_callbacks)
            number_row_fn("Bottom flange transverse spacing (mm)", "inputs_bot_flange_transverse_spacing", float(ss.get("bot_flange_transverse_spacing", 200.0) or 200.0), sync_callbacks)
            number_row_fn("Bottom flange transverse legs", "inputs_bot_flange_transverse_legs", float(ss.get("bot_flange_transverse_legs", 2) or 2), sync_callbacks)


def render_inputs_shear_reinforcement_column(
    *,
    st_module: Any,
    col_shear_mat,
    inputs_detailed_mode: bool,
    fast_focus_section: str | None,
    corrected_invalid_shear_state: bool,
    sync_callbacks: dict,
    render_fast_next_hint_fn: Callable[[str], None],
    recommendation_section_header_fn: Callable[..., None],
    shear_recommendation_panel_fn: Callable[..., None],
    get_widget_key_for_shared_fn: Callable[..., str | None],
    shared_state_snapshot_fn: Callable[[], dict],
    request_shear_widget_seed_from_shared_fn: Callable[[str], None],
    seed_widget_from_shared_fn: Callable[..., None],
    agent_debug_log_fn: Callable[..., None],
    select_row_fn: Callable[..., None],
    number_row_fn: Callable[..., None],
    reo_bar_dias: list,
) -> None:
    ss = st_module.session_state
    with col_shear_mat:
        if not inputs_detailed_mode and fast_focus_section == "shear":
            render_fast_next_hint_fn("Next step: confirm or auto-design the shear reinforcement below.")
        recommendation_section_header_fn(
            "Shear" if not inputs_detailed_mode else "Shear reinforcement",
            help_text=(
                "Show the current shear recommendation, the optimisation goal, "
                "the predicted impact, and apply the suggested links."
            ),
            level="h2",
            render_popover_content=lambda: shear_recommendation_panel_fn(
                button_key="inputs_apply_shear_recommendation",
                source="fast_mode:shear_recommendation" if not inputs_detailed_mode else "detailed_mode:shear_recommendation",
                compact=not inputs_detailed_mode,
            ),
        )

        w_lig_d = get_widget_key_for_shared_fn("lig_d", prefix="inputs_") or "inputs_lig_d"
        w_lig_legs = get_widget_key_for_shared_fn("lig_legs", prefix="inputs_") or "inputs_lig_legs"
        w_s_lig = get_widget_key_for_shared_fn("s_lig", prefix="inputs_") or "inputs_s_lig"
        shared_lig_d = int(shared_state_snapshot_fn().get("lig_d", 0) or 0)
        shared_lig_legs = int(shared_state_snapshot_fn().get("lig_legs", 0) or 0)
        shared_s_lig = float(shared_state_snapshot_fn().get("s_lig", 200.0) or 200.0)
        try:
            widget_lig_d_pre = int(ss.get(w_lig_d, 0) or 0)
            widget_lig_legs_pre = int(ss.get(w_lig_legs, 0) or 0)
        except Exception:
            widget_lig_d_pre = 0
            widget_lig_legs_pre = 0
        if shared_lig_d <= 0 and shared_lig_legs <= 0 and (widget_lig_d_pre > 0 or widget_lig_legs_pre > 0):
            request_shear_widget_seed_from_shared_fn("render_inputs:shared_no_links_widget_stale")
        if corrected_invalid_shear_state:
            request_shear_widget_seed_from_shared_fn("render_inputs:corrected_invalid_shear_state")
        pending_shear_seed = ss.pop("_pending_shear_widget_seed_from_shared", None)
        widget_keys_seeded: list[str] = []
        if isinstance(pending_shear_seed, dict):
            for widget_key in (
                w_lig_d,
                w_lig_legs,
                w_s_lig,
                "shear_lig_d",
                "shear_lig_legs",
                "shear_s_lig",
            ):
                ss.pop(widget_key, None)
                ss.pop(f"_cached_{widget_key}", None)
            seed_widget_from_shared_fn(w_lig_d, "lig_d", 0)
            widget_keys_seeded.append(w_lig_d)
            seed_widget_from_shared_fn(w_lig_legs, "lig_legs", 0)
            widget_keys_seeded.append(w_lig_legs)
            seed_widget_from_shared_fn(w_s_lig, "s_lig", 200.0)
            widget_keys_seeded.append(w_s_lig)
            seed_widget_from_shared_fn("shear_lig_d", "lig_d", 0)
            widget_keys_seeded.append("shear_lig_d")
            seed_widget_from_shared_fn("shear_lig_legs", "lig_legs", 0)
            widget_keys_seeded.append("shear_lig_legs")
            seed_widget_from_shared_fn("shear_s_lig", "s_lig", 200.0)
            widget_keys_seeded.append("shear_s_lig")
        ss["_inputs_shear_seed_consume_audit"] = {
            "consumed": bool(isinstance(pending_shear_seed, dict)),
            "reason": pending_shear_seed.get("reason") if isinstance(pending_shear_seed, dict) else None,
            "shared": pending_shear_seed.get("shared") if isinstance(pending_shear_seed, dict) else None,
            "widget_keys_seeded": list(widget_keys_seeded),
        }
        seed_widget_from_shared_fn(w_lig_d, "lig_d", 0)
        seed_widget_from_shared_fn(w_lig_legs, "lig_legs", 0)
        seed_widget_from_shared_fn(w_s_lig, "s_lig", 200.0)
        widget_lig_d = ss.get(w_lig_d)
        widget_lig_legs = ss.get(w_lig_legs)
        widget_s_lig = ss.get(w_s_lig)
        ss["_inputs_shear_truth_audit"] = {
            "page_slug": str(ss.get("page_slug") or ""),
            "shared": {
                "lig_d": ss.get("lig_d"),
                "lig_legs": ss.get("lig_legs"),
                "s_lig": ss.get("s_lig"),
            },
            "inputs_widgets": {
                "inputs_lig_d": ss.get("inputs_lig_d"),
                "inputs_lig_legs": ss.get("inputs_lig_legs"),
                "inputs_s_lig": ss.get("inputs_s_lig"),
            },
            "shear_widgets": {
                "shear_lig_d": ss.get("shear_lig_d"),
                "shear_lig_legs": ss.get("shear_lig_legs"),
                "shear_s_lig": ss.get("shear_s_lig"),
            },
            "refresh_flags": {
                "_pending_inputs_apply_refresh_present": bool(ss.get("_inputs_pending_refresh_present_before_pop")),
                "_force_inputs_widget_reseed_once": bool(ss.get("_force_inputs_widget_reseed_once")),
                "_inputs_longitudinal_reo_force_refresh_processed_this_run": bool(ss.get("_inputs_longitudinal_reo_force_refresh_processed_this_run")),
                "_inputs_shear_force_refresh_processed_this_run": bool(ss.get("_inputs_shear_force_refresh_processed_this_run")),
                "_pending_shear_widget_seed_from_shared_present": bool(isinstance(pending_shear_seed, dict)),
            },
            "seed_request_reason": pending_shear_seed.get("reason") if isinstance(pending_shear_seed, dict) else None,
            "seed_consume_audit_present": bool(ss.get("_inputs_shear_seed_consume_audit")),
        }
        lig_d_val = int(widget_lig_d if widget_lig_d is not None else shared_lig_d)
        lig_legs_val = int(widget_lig_legs if widget_lig_legs is not None else shared_lig_legs)
        s_lig_val = float(widget_s_lig if widget_s_lig is not None else shared_s_lig)
        if bool(ss.get("_dev_mode")):
            agent_debug_log_fn(
                "Shear widget/model audit",
                {
                    "shared": {
                        "lig_d": shared_lig_d,
                        "lig_legs": shared_lig_legs,
                        "s_lig": shared_s_lig,
                    },
                    "widgets": {
                        "inputs_lig_d": widget_lig_d,
                        "inputs_lig_legs": widget_lig_legs,
                        "inputs_s_lig": widget_s_lig,
                    },
                    "rendered_values": {
                        "lig_d": lig_d_val,
                        "lig_legs": lig_legs_val,
                        "s_lig": s_lig_val,
                    },
                    "fast_model_uses_overlay_state": True,
                },
                location="inputs_page.py:render_inputs:shear_widget_audit",
                hypothesis_id="H_SHEAR_WIDGET",
            )

        select_row_fn(
            "Link dia (mm)",
            w_lig_d,
            {0: "0 (off)"} | {dia: str(dia) for dia in reo_bar_dias},
            int(lig_d_val),
            sync_callbacks,
            help_text="Nominal diameter of shear reinforcement links (mm).",
            seed_session_state=False,
        )
        select_row_fn(
            "No. of legs",
            w_lig_legs,
            [0] + list(range(2, 13)),
            int(lig_legs_val),
            sync_callbacks,
            help_text="Number of legs per shear link. Use 0 for no links; 2 or more for active shear reinforcement.",
            seed_session_state=False,
        )
        number_row_fn(
            "Link spacing (mm)",
            w_s_lig,
            s_lig_val,
            sync_callbacks,
            help_text="Centre-to-centre spacing of shear links along the member (mm).",
        )


def render_inputs_detailed_support_lower_row(
    *,
    st_module: Any,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    mark: Callable[[str], None],
    sub_mark: Callable[[str], None],
    page_divider_fn: Callable[[], None],
    materials_and_section_2d_fn: Callable[..., None],
    time_dependent_inputs_fn: Callable[..., None],
    ducts_prestress_voids_inputs_fn: Callable[..., None],
    label_with_hover_fn: Callable[..., None],
    number_row_fn: Callable[..., None],
) -> None:
    ss = st_module.session_state
    sub_mark("reinforcement")

    if inputs_detailed_mode:
        materials_and_section_2d_fn(sync_callbacks)
        page_divider_fn()
    sub_mark("shear_torsion")

    if inputs_detailed_mode:
        col_td, col_ducts, col_crack = st_module.columns([1.15, 1.0, 0.85], gap="large")

        with col_td:
            time_dependent_inputs_fn(sync_callbacks)

        with col_ducts:
            ducts_prestress_voids_inputs_fn(sync_callbacks)

        with col_crack:
            st_module.subheader("Crack Control Inputs")

            options = ["A1", "A2", "B1", "B2", "C1", "C2"]

            current = fast_get_param("exposure_class", "B1")

            if current not in options:
                current = "B1"

            col_exp_label, col_exp_input = st_module.columns([1, 2])
            with col_exp_label:
                label_with_hover_fn("Exposure class", "Exposure classification to AS 3600 – controls allowable crack width.")
            with col_exp_input:
                if "inputs_exposure_class" in ss:
                    st_module.selectbox(
                        "Exposure class",
                        options,
                        key="inputs_exposure_class",
                        on_change=sync_callbacks["inputs_exposure_class"],
                        label_visibility="collapsed",
                    )
                else:
                    st_module.selectbox(
                        "Exposure class",
                        options,
                        key="inputs_exposure_class",
                        index=options.index(current),
                        on_change=sync_callbacks["inputs_exposure_class"],
                        label_visibility="collapsed",
                    )

            member_options = ["Primarily flexure", "Primarily tension"]
            member_current = ss.get("crack_member_type", "Primarily flexure")

            col1, col2 = st_module.columns([1, 2])
            with col1:
                label_with_hover_fn(
                    "Resultant action",
                    "Affects default k₂ assumption and crack model interpretation.",
                )
            with col2:
                st_module.selectbox(
                    "Resultant action",
                    options=member_options,
                    index=member_options.index(member_current) if member_current in member_options else 0,
                    key="inputs_crack_member_type",
                    on_change=sync_callbacks["inputs_crack_member_type"],
                    label_visibility="collapsed",
                )

            k1_options = [0.8, 1.6]
            k1_current = float(ss.get("crack_k1", 0.8))

            col1, col2 = st_module.columns([1, 2])
            with col1:
                label_with_hover_fn(
                    "k₁ (bond coefficient)",
                    "0.8 for deformed bars, 1.6 for plain bars.",
                )
            with col2:
                st_module.selectbox(
                    "k1",
                    options=k1_options,
                    index=k1_options.index(k1_current) if k1_current in k1_options else 0,
                    format_func=lambda x: "Deformed bars (k₁ = 0.8)" if abs(x - 0.8) < 1e-9 else "Plain bars (k₁ = 1.6)",
                    key="inputs_crack_k1",
                    on_change=sync_callbacks["inputs_crack_k1"],
                    label_visibility="collapsed",
                )

            k2_seed = 0.5 if member_current == "Primarily flexure" else 1.0
            number_row_fn(
                "k₂ (strain distribution factor)",
                "inputs_crack_k2",
                float(ss.get("crack_k2", k2_seed)),
                sync_callbacks,
                help_text="Default 0.5 for flexure, 1.0 for tension. Adjust only if using a different assumed strain distribution.",
            )
    sub_mark("end")
    mark("render_inputs_widgets")


def render_inputs_geometry_materials_top_section(
    *,
    st_module: Any,
    geometry_slot,
    right_diagram,
    model_slot,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    fast_get_param,
    mark: Callable[[str], None],
    sub_mark: Callable[[str], None],
    recommendation_section_header_fn: Callable[..., None],
    geometry_recommendation_panel_fn: Callable[..., None],
    select_row_fn: Callable[..., None],
    number_row_fn: Callable[..., None],
    materials_subsection_fn: Callable[..., None],
    section_2d_diagram_block_fn: Callable[..., None],
    resolved_inputs_model_state_fn: Callable[[], tuple[dict, dict]],
    fast_model_block_fn: Callable[..., None],
    page_divider_fn: Callable[[], None],
) -> None:
    render_started_ns = time.perf_counter_ns()
    ss = st_module.session_state
    stage_started_ns = time.perf_counter_ns()
    model_state, model_state_debug = resolved_inputs_model_state_fn()
    stage_timings_ms = {
        "resolve_model_state": round(
            (time.perf_counter_ns() - stage_started_ns) / 1_000_000,
            3,
        )
    }
    stage_started_ns = time.perf_counter_ns()
    with geometry_slot:
        recommendation_section_header_fn(
            "Geometry & Materials" if not inputs_detailed_mode else "Geometry",
            help_text=(
                "Show the current geometry recommendation, the optimisation goal, "
                "the predicted impact, and apply the suggested geometry."
            ),
            level="h2",
            render_popover_content=lambda: geometry_recommendation_panel_fn(
                button_key="inputs_apply_geometry_recommendation",
                source="fast_mode:geometry_recommendation" if not inputs_detailed_mode else "detailed_mode:geometry_recommendation",
                compact=not inputs_detailed_mode,
            ),
        )

        shape_options = ["RECT", "T", "I"]
        sec_shape_current = ss.get("sec_shape", "RECT")
        if sec_shape_current not in shape_options:
            sec_shape_current = "RECT"

        select_row_fn(
            "Section shape",
            "inputs_sec_shape",
            shape_options,
            sec_shape_current,
            sync_callbacks,
            help_text="Select section type. Geometry inputs below update based on this selection.",
        )

        d_val = float(ss.get("inputs_D", fast_get_param("D", 600.0)))
        l_val = float(ss.get("inputs_L", fast_get_param("L", 3000.0)))
        cover_side_val = float(ss.get("inputs_cover_side", fast_get_param("cover_side", 40.0)))
        sec_shape = ss.get("inputs_sec_shape", ss.get("sec_shape", "RECT"))

        if sec_shape == "RECT":
            b_val = float(ss.get("inputs_b", fast_get_param("b", 400.0)))
            number_row_fn(
                "Width b (mm)",
                "inputs_b",
                b_val,
                sync_callbacks,
                help_text="Rectangular section width.",
            )

        elif sec_shape == "T":
            bf_val = float(ss.get("inputs_bf", fast_get_param("bf", 600.0)))
            tf_val = float(ss.get("inputs_tf", fast_get_param("tf", 120.0)))
            bw_val = float(ss.get("inputs_bw", fast_get_param("bw", 300.0)))

            number_row_fn("Flange width bf (mm)", "inputs_bf", bf_val, sync_callbacks)
            number_row_fn("Flange thickness tf (mm)", "inputs_tf", tf_val, sync_callbacks)
            number_row_fn("Web width bw (mm)", "inputs_bw", bw_val, sync_callbacks, help_text="Stem/web width for T section.")

        elif sec_shape == "I":
            bf_val = float(ss.get("inputs_bf", fast_get_param("bf", 600.0)))
            tf_val = float(ss.get("inputs_tf", fast_get_param("tf", 120.0)))
            tw_val = float(ss.get("inputs_tw", fast_get_param("tw", 200.0)))

            number_row_fn("Top flange width bf (mm)", "inputs_bf", bf_val, sync_callbacks)
            number_row_fn("Top flange thickness tf (mm)", "inputs_tf", tf_val, sync_callbacks)
            number_row_fn("Web thickness tw (mm)", "inputs_tw", tw_val, sync_callbacks)

        number_row_fn(
            "Depth D (mm)",
            "inputs_D",
            d_val,
            sync_callbacks,
            help_text="Overall section depth from compression face to soffit.",
        )

        number_row_fn(
            "Span L (mm)",
            "inputs_L",
            l_val,
            sync_callbacks,
            help_text="Clear span used for deflection checks.",
        )

        if inputs_detailed_mode:
            number_row_fn(
                "Side cover (mm)",
                "inputs_cover_side",
                cover_side_val,
                sync_callbacks,
                help_text="Clear side cover to longitudinal reinforcement and ducts.",
            )
        if not inputs_detailed_mode:
            materials_subsection_fn(sync_callbacks, show_heading=False)
    stage_timings_ms["geometry_material_controls"] = round(
        (time.perf_counter_ns() - stage_started_ns) / 1_000_000,
        3,
    )
    sub_mark("geometry")
    mark("top_inputs_widgets")
    # The parent workspace now owns a dedicated diagram fragment.  Keeping
    # diagram/material presentation out of this geometry child prevents a
    # reinforcement edit from recomputing into a parent-owned slot.  Detailed
    # materials and the fast model are rendered by that sibling fragment.
    if inputs_detailed_mode:
        page_divider_fn()
    stage_timings_ms["diagram_material_presentation"] = 0.0
    stage_timings_ms["total"] = round(
        (time.perf_counter_ns() - render_started_ns) / 1_000_000,
        3,
    )
    ss["_inputs_geometry_section_stage_timings_ms"] = stage_timings_ms
    sub_mark("materials")
    mark("render_diagrams")


def render_inputs_design_actions_section(
    *,
    st_module: Any,
    actions_slot,
    inputs_detailed_mode: bool,
    sync_callbacks: dict,
    sub_mark: Callable[[str], None],
    design_actions_anchor_id: str,
    info_i_button_fn: Callable[..., Any],
    get_widget_key_for_shared_fn: Callable[..., str | None],
    commit_design_action_widgets_to_shared_fn: Callable[[str], None],
    mirror_design_action_proxies_from_shared_fn: Callable[[str], None],
    is_design_governing_fn: Callable[[], bool],
    hydrate_design_action_widgets_from_shared_fn: Callable[..., None],
    design_action_widget_specs_fn: Callable[[str], list],
    make_design_action_widget_callback_fn: Callable[..., Any],
    render_design_action_number_row_fn: Callable[..., None],
    reconcile_design_action_widgets_with_shared_fn: Callable[[str], None],
    debug_check_design_action_consistency_fn: Callable[[dict], None],
    shared_state_snapshot_fn: Callable[[], dict],
) -> None:
    _ = sync_callbacks
    with actions_slot:
        st_module.markdown(
            f'<div id="{design_actions_anchor_id}" style="height:0;margin:0;padding:0;"></div>',
            unsafe_allow_html=True,
        )
        title_col, info_col = st_module.columns([20, 1], gap="small")
        with title_col:
            st_module.markdown("## Design Actions")

        legacy_manual = "Manual design actions (inputs below)"
        legacy_design = "Teaching SFD/BMD page (|M|max, |V|max)"

        current_actions_source = st_module.session_state.get(
            "actions_source",
            legacy_manual,
        )

        if current_actions_source == "Manual design actions":
            current_actions_source = legacy_manual
        elif current_actions_source == "Calculated design actions (from SFD/BMD)":
            current_actions_source = legacy_design

        design_actions_toggle_default = current_actions_source == legacy_design
        itk_calculated = "inputs_use_calculated_actions"
        itk_calculated_intent = "_inputs_use_calculated_actions_user_intent"
        user_intent_pending = bool(st_module.session_state.get(itk_calculated_intent, False))
        if (
            (not user_intent_pending)
            and itk_calculated in st_module.session_state
            and bool(st_module.session_state[itk_calculated]) != bool(design_actions_toggle_default)
        ):
            st_module.session_state[itk_calculated] = bool(design_actions_toggle_default)
            _rerun_inputs_fragment_or_app(st_module)

        with info_col:
            with info_i_button_fn(
                help_text="Explain where design demand comes from and control whether loads are manual or linked to the Design page."
            ):
                st_module.markdown("**What sets demand**")
                st_module.markdown("- ULS actions drive bending and shear strength checks.")
                st_module.markdown("- SLS actions drive crack and deflection serviceability checks.")
                st_module.markdown("- When linked to the Design page, this screen follows the critical actions from the SFD/BMD workflow.")
                st_module.markdown("**When to change it**")
                st_module.markdown("- Use manual inputs for quick studies or hand-checking one beam.")
                st_module.markdown("- Use linked actions when demand should stay tied to the analysed load model.")
                st_module.markdown("**What to avoid**")
                st_module.markdown("- Do not compare a ULS strength result against an SLS load view by mistake.")
                st_module.divider()

                def _on_inputs_use_calculated_actions_change() -> None:
                    st_module.session_state[itk_calculated_intent] = True
                    st_module.session_state["inputs_dirty"] = True
                    st_module.session_state["_inputs_dirty"] = True

                use_calculated_actions = st_module.toggle(
                    "Use calculated design actions",
                    value=design_actions_toggle_default,
                    key="inputs_use_calculated_actions",
                    on_change=_on_inputs_use_calculated_actions_change,
                    help=(
                        "When enabled, the design actions below are taken from the "
                        "Design / SFD-BMD page and become read-only."
                    ),
                )

                selected_mode_preview = "design" if use_calculated_actions else "manual"
                actions_mode_preview = legacy_design if selected_mode_preview == "design" else legacy_manual
                if actions_mode_preview == legacy_design:
                    st_module.caption("Design actions: From SFD/BMD")
                else:
                    st_module.caption("Design actions: Manual inputs")

                preview_mode = st_module.session_state.get("loads_edit_mode", "ULS")
                toggle_widget_key = get_widget_key_for_shared_fn("loads_edit_toggle", prefix="inputs_") or "inputs_loads_edit_toggle"
                edit_sls = st_module.toggle(
                    "View SLS loads",
                    key=toggle_widget_key,
                    help="Toggle which load set is shown below. ULS drives bending/shear; SLS drives crack/deflection.",
                )
                preview_mode = "SLS" if edit_sls else "ULS"
                preview_action_verb = "viewing" if selected_mode_preview == "design" else "editing"
                st_module.caption(f"Currently {preview_action_verb}: **{preview_mode}** loads")

        selected_mode = "design" if use_calculated_actions else "manual"
        mapped_source = legacy_design if selected_mode == "design" else legacy_manual

        source_changed = st_module.session_state.get("actions_source") != mapped_source
        mode_changed = st_module.session_state.get("actions_mode") != selected_mode

        if source_changed:
            st_module.session_state["actions_source"] = mapped_source

        if mode_changed:
            st_module.session_state["actions_mode"] = selected_mode

        if source_changed or mode_changed:
            st_module.session_state["inputs_dirty"] = True
            st_module.session_state["_inputs_dirty"] = True
            _rerun_inputs_fragment_or_app(st_module)

        prev_mode = st_module.session_state.get("loads_edit_mode", "ULS")
        toggle_widget_key = get_widget_key_for_shared_fn("loads_edit_toggle", prefix="inputs_") or "inputs_loads_edit_toggle"
        new_mode = "SLS" if edit_sls else "ULS"

        if new_mode != prev_mode:
            previous_prefix = "sls" if str(prev_mode).upper() == "SLS" else "uls"
            commit_design_action_widgets_to_shared_fn(previous_prefix)
            st_module.session_state["loads_edit_mode"] = new_mode
            mirror_design_action_proxies_from_shared_fn("sls" if str(new_mode).upper() == "SLS" else "uls")
            st_module.session_state["_force_design_action_widget_hydrate"] = True
            st_module.session_state["inputs_dirty"] = True
            st_module.session_state["_inputs_dirty"] = True
            _rerun_inputs_fragment_or_app(st_module)
        else:
            st_module.session_state["loads_edit_mode"] = new_mode

        if user_intent_pending:
            st_module.session_state[itk_calculated_intent] = False

        design_controls = is_design_governing_fn()
        if design_controls:
            st_module.info("Locked: Loads are controlled by the Design page (SFD/BMD). Edit loads there.")

        selected_mode = st_module.session_state.get("loads_edit_mode", "ULS")
        selected_prefix = "sls" if selected_mode == "SLS" else "uls"
        force_design_action_hydrate = bool(st_module.session_state.pop("_force_design_action_widget_hydrate", False))
        hydrate_design_action_widgets_from_shared_fn(
            selected_prefix,
            force=force_design_action_hydrate,
            design_controls=design_controls,
        )

        for spec in design_action_widget_specs_fn(selected_prefix):
            shared_key = str(spec.get("shared_key", ""))
            if not inputs_detailed_mode and (
                shared_key == "P_star" or shared_key.endswith("_Mstar_neg_manual")
            ):
                continue
            callback = make_design_action_widget_callback_fn(
                str(spec["widget_key"]),
                shared_key,
                spec.get("proxy_key"),
            )
            render_design_action_number_row_fn(
                label=str(spec["label"]),
                widget_key=str(spec["widget_key"]),
                help_text=str(spec["help_text"]),
                on_change=callback,
                disabled=bool(spec["disabled_in_design_mode"]) and design_controls,
            )

        if not design_controls:
            reconcile_design_action_widgets_with_shared_fn(selected_prefix)

        debug_check_design_action_consistency_fn(shared_state_snapshot_fn())
        sub_mark("loads")
        sub_mark("design_actions")


def render_inputs_materials_and_section_2d(
    *,
    st_module: Any,
    sync_callbacks: dict,
    get_widget_key_for_shared_fn: Callable[..., str | None],
    select_row_fn: Callable[..., None],
    is_design_governing_fn: Callable[[], bool],
    resolve_support_and_deflection_defaults_fn: Callable[[], dict],
    caption_deflection_limit_ratio_fn: Callable[[], None],
    number_row_fn: Callable[..., None],
    render_3d_diagram_block_fn: Callable[[], None],
    deflection_limit_help_text: str,
    k_v_method_options: list,
) -> None:
    mat_col, sec2d_col = st_module.columns([1.15, 1.85], gap="large")

    with mat_col:
        st_module.subheader("Support conditions")

        faces_options = [
            "Slab \u2013 one face exposed",
            "Slab \u2013 two faces exposed",
            "Beam \u2013 three faces exposed",
            "Column \u2013 four faces exposed",
        ]
        faces_current = st_module.session_state.get("member_faces_exposed", "Beam \u2013 three faces exposed")
        if faces_current not in faces_options:
            faces_current = "Beam \u2013 three faces exposed"

        w_faces = get_widget_key_for_shared_fn("member_faces_exposed", prefix="inputs_") or "inputs_member_faces_exposed"
        select_row_fn(
            "Member / faces exposed",
            w_faces,
            faces_options,
            faces_current,
            sync_callbacks,
            help_text="Number of faces exposed to drying environment (affects shrinkage calculations).",
        )

        env_options = [
            "Arid environment",
            "Interior environment",
            "Temperate inland environment",
            "Tropical / near-coastal / coastal environment",
        ]
        env_current = st_module.session_state.get("shrinkage_env", "Temperate inland environment")
        if env_current not in env_options:
            env_current = "Temperate inland environment"

        w_env = get_widget_key_for_shared_fn("shrinkage_env", prefix="inputs_") or "inputs_shrinkage_env"
        select_row_fn(
            "Shrinkage environment (Table 3.1.7.2)",
            w_env,
            env_options,
            env_current,
            sync_callbacks,
            help_text="Shrinkage environment classification per AS 3600 Table 3.1.7.2.",
        )

        creep_env_options = [
            "Arid environment",
            "Interior environment",
            "Temperate inland environment",
            "Tropical / near-coastal / coastal environment",
        ]
        creep_env_current = st_module.session_state.get("env_option", "Temperate inland environment")
        if creep_env_current not in creep_env_options:
            creep_env_current = "Temperate inland environment"

        w_creep_env = get_widget_key_for_shared_fn("env_option", prefix="inputs_") or "inputs_env_option"
        select_row_fn(
            "Creep environment (Tables 3.1.8.2 & 3.1.8.3)",
            w_creep_env,
            creep_env_options,
            creep_env_current,
            sync_callbacks,
            help_text="Creep environment classification per AS 3600 Tables 3.1.8.2 & 3.1.8.3.",
        )

        design_controls = is_design_governing_fn()
        support_bundle = resolve_support_and_deflection_defaults_fn()
        support_current = support_bundle["support_current"]
        support_options = support_bundle["support_options"]
        w_support = get_widget_key_for_shared_fn("defl_support_type", prefix="inputs_") or "inputs_defl_support_type"
        if design_controls:
            st_module.info(
                "\U0001f512 Support condition (k\u2082) is **auto-derived** from the Design / SFD model "
                "(matches deflection calculations)."
            )
        select_row_fn(
            "Support condition (k\u2082)",
            w_support,
            support_options,
            support_current,
            sync_callbacks,
            help_text="Support condition determines the deflection coefficient k\u2082 used in AS 3600 deflection calculations.",
            disabled=design_controls,
        )

        w_defl_limit = get_widget_key_for_shared_fn("defl_limit_ratio", prefix="inputs_") or "inputs_defl_limit_ratio"
        defl_limit_val = support_bundle["defl_limit_val"]
        defl_limit_options_by_ratio = support_bundle["defl_limit_options_by_ratio"]
        select_row_fn(
            "Deflection limit L/\u0394",
            w_defl_limit,
            defl_limit_options_by_ratio,
            defl_limit_val,
            sync_callbacks,
            help_text=deflection_limit_help_text,
        )
        caption_deflection_limit_ratio_fn()

        st_module.markdown("")
        st_module.subheader("Shear section parameters")

        w_d_g = get_widget_key_for_shared_fn("d_g", prefix="inputs_") or "inputs_d_g"
        w_k_v_method = get_widget_key_for_shared_fn("k_v_method", prefix="inputs_") or "inputs_k_v_method"

        d_g_val = float(st_module.session_state.get("d_g", 20.0))
        k_v_val = st_module.session_state.get("k_v_method", "General \u03b5x-based (Cl. 8.2.4.2)")

        number_row_fn(
            "Maximum aggregate size d_g (mm)",
            w_d_g,
            d_g_val,
            sync_callbacks,
            help_text="Maximum aggregate size used in shear provisions (mm).",
        )

        select_row_fn(
            "k_v method",
            w_k_v_method,
            k_v_method_options,
            k_v_val,
            sync_callbacks,
            help_text="Select the k_v method for shear capacity (AS 3600 8.2.4.2 vs 8.2.4.3).",
        )

    with sec2d_col:
        render_3d_diagram_block_fn()


__all__ = [
    "render_inputs_bottom_reinforcement_column",
    "render_inputs_detailed_support_lower_row",
    "render_inputs_design_actions_section",
    "render_inputs_flange_reinforcement",
    "render_inputs_geometry_materials_top_section",
    "render_inputs_materials_and_section_2d",
    "render_inputs_shear_reinforcement_column",
    "render_inputs_top_reinforcement_column",
    "render_inputs_widget_sections",
]
