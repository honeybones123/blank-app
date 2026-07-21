"""Inputs summary pipeline orchestration."""

from __future__ import annotations

from typing import Any, Callable


def render_inputs_summary_pipeline(
    *,
    ss: dict,
    st_module: Any,
    summary_container,
    sync_callbacks: dict,
    skip_active_beam_record_write: bool,
    mark: Callable[[str], None],
    summary_state_cache_fn: Callable[..., tuple],
    pack_meta_fn: Callable[..., dict],
    hc_log_fn: Callable[..., None],
    summary_rows_from_packs_fn: Callable[..., tuple],
    summary_display_state_fn: Callable[..., tuple],
    summary_guidance_cache_fn: Callable[..., tuple],
    summary_row_finalization_fn: Callable[..., None],
    calculation_explainer_trace_fn: Callable[..., None],
    summary_container_fn: Callable[..., None],
    pre_widget_trace_fn: Callable[..., None],
) -> None:
    (
        summary_state,
        summary_state_debug,
        bend_pack,
        shear_pack,
        crack_pack,
        defl_pack,
    ) = summary_state_cache_fn(ss=ss, mark=mark)

    hc_log_fn(
        "summary.pack_meta",
        bending=pack_meta_fn("bending", bend_pack),
        shear=pack_meta_fn("shear", shear_pack),
        crack=pack_meta_fn("crack", crack_pack),
        deflection=pack_meta_fn("deflection", defl_pack),
    )

    hc_log_fn(
        "state.snapshot",
        keys_count=len(st_module.session_state.keys()),
        has_actions_uls=isinstance(
            st_module.session_state.get("actions_uls"),
            dict,
        ),
        sample_keys=sorted(list(st_module.session_state.keys()))[:120],
    )

    (
        BENDING_ROWS,
        SHEAR_ROWS,
        CRACK_ROWS,
        DEFLECTION_ROWS,
        bend_err,
        shear_err,
        crack_err,
        defl_err,
        delta_total,
        defl_limit,
        defl_util,
    ) = summary_rows_from_packs_fn(
        bend_pack=bend_pack,
        shear_pack=shear_pack,
        crack_pack=crack_pack,
        defl_pack=defl_pack,
    )
    _ = bend_err
    _ = shear_err
    _ = crack_err
    _ = defl_err
    _ = delta_total
    _ = defl_limit
    _ = defl_util

    (
        bending_cap,
        bending_demand,
        bending_util_str,
        bending_status,
        bending_colour,
        shear_cap,
        shear_demand,
        shear_util_str,
        shear_status,
        shear_colour,
        shear_summary_status_note,
        shear_governing_name,
        shear_governing_source,
        shear_reason,
        crack_cap,
        crack_demand,
        crack_util_str,
        crack_status,
        crack_colour,
        defl_cap,
        defl_demand,
        defl_util_str,
        defl_status,
        defl_colour,
    ) = summary_display_state_fn(
        summary_state=summary_state,
        shear_pack=shear_pack,
        BENDING_ROWS=BENDING_ROWS,
        SHEAR_ROWS=SHEAR_ROWS,
        CRACK_ROWS=CRACK_ROWS,
        DEFLECTION_ROWS=DEFLECTION_ROWS,
    )
    summary_guidance_items, governing_check = summary_guidance_cache_fn(
        summary_state=summary_state,
        summary_state_debug=summary_state_debug,
    )
    _ = summary_guidance_items

    summary_row_finalization_fn(
        skip_active_beam_record_write=bool(skip_active_beam_record_write),
        BENDING_ROWS=BENDING_ROWS,
        SHEAR_ROWS=SHEAR_ROWS,
        CRACK_ROWS=CRACK_ROWS,
        DEFLECTION_ROWS=DEFLECTION_ROWS,
    )
    results_version = int(ss.get("results_version", 0) or 0)
    summary_action_fp = ss.get("_summary_cache_action_fp")
    calculation_explainer_trace_fn(
        BENDING_ROWS=BENDING_ROWS,
        SHEAR_ROWS=SHEAR_ROWS,
        CRACK_ROWS=CRACK_ROWS,
        DEFLECTION_ROWS=DEFLECTION_ROWS,
        results_version=results_version,
        summary_action_fp=summary_action_fp,
        trace_fn=pre_widget_trace_fn,
    )

    summary_container_fn(
        summary_container=summary_container,
        sync_callbacks=sync_callbacks,
        BENDING_ROWS=BENDING_ROWS,
        SHEAR_ROWS=SHEAR_ROWS,
        CRACK_ROWS=CRACK_ROWS,
        DEFLECTION_ROWS=DEFLECTION_ROWS,
        defl_pack=defl_pack,
        governing_check=governing_check,
        bending_cap=bending_cap,
        bending_demand=bending_demand,
        bending_util_str=bending_util_str,
        bending_status=bending_status,
        bending_colour=bending_colour,
        shear_cap=shear_cap,
        shear_demand=shear_demand,
        shear_util_str=shear_util_str,
        shear_status=shear_status,
        shear_colour=shear_colour,
        shear_summary_status_note=shear_summary_status_note,
        shear_governing_name=shear_governing_name,
        shear_governing_source=shear_governing_source,
        shear_reason=shear_reason,
        crack_cap=crack_cap,
        crack_demand=crack_demand,
        crack_util_str=crack_util_str,
        crack_status=crack_status,
        crack_colour=crack_colour,
        defl_cap=defl_cap,
        defl_demand=defl_demand,
        defl_util_str=defl_util_str,
        defl_status=defl_status,
        defl_colour=defl_colour,
    )
    mark("render_summary")


__all__ = ["render_inputs_summary_pipeline"]
