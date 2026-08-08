"""Inputs summary pipeline orchestration."""

from __future__ import annotations

from typing import Any, Callable

from inputs_application.summary_contracts import InputsSummaryCalculationSource


def render_inputs_summary_pipeline(
    *,
    ss: dict,
    st_module: Any,
    summary_container,
    sync_callbacks: dict,
    skip_active_beam_record_write: bool,
    mark: Callable[[str], None],
    render_title: bool = True,
    region_context=None,
    summary_state_cache_fn: Callable[..., tuple],
    pack_meta_fn: Callable[..., dict],
    hc_log_fn: Callable[..., None],
    summary_rows_from_packs_fn: Callable[..., tuple],
    summary_guidance_cache_fn: Callable[..., tuple],
    summary_row_finalization_fn: Callable[..., None],
    summary_container_fn: Callable[..., None],
) -> InputsSummaryCalculationSource:
    state_cache_kwargs = {
        "ss": ss,
        "mark": mark,
    }
    if region_context is not None:
        state_cache_kwargs["region_context"] = region_context
    (
        summary_state,
        summary_state_debug,
        bend_pack,
        shear_pack,
        crack_pack,
        defl_pack,
    ) = summary_state_cache_fn(**state_cache_kwargs)

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
    summary_container_fn(
        summary_state=summary_state,
        summary_container=summary_container,
        sync_callbacks=sync_callbacks,
        render_title=render_title,
    )
    mark("render_summary")
    return InputsSummaryCalculationSource(
        bending_rows=tuple(dict(row) for row in BENDING_ROWS),
        shear_rows=tuple(dict(row) for row in SHEAR_ROWS),
        crack_rows=tuple(dict(row) for row in CRACK_ROWS),
        deflection_rows=tuple(dict(row) for row in DEFLECTION_ROWS),
        results_version=int(ss.get("results_version", 0) or 0),
        summary_action_fp=ss.get("_summary_cache_action_fp"),
    )


__all__ = [
    "InputsSummaryCalculationSource",
    "render_inputs_summary_pipeline",
]
