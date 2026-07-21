"""Inputs summary render coordinators."""

from __future__ import annotations

import html

import streamlit as st

from ui_seamless_steps import inject_seamless_steps_css
from widgets_helpers import page_divider

from .builders import build_inputs_summary_html
from .models import InputsSummaryCardSource, InputsSummarySourceSnapshot


def _build_summary_cards_html_for_current_state(
    summary_source: InputsSummarySourceSnapshot | None = None,
    *,
    shear_detail_note_html: str = "",
) -> str:
    if summary_source is None:
        raise RuntimeError("page-owned summary HTML fallback has been removed")
    return build_inputs_summary_html(
        summary_source,
        shear_detail_note_html=shear_detail_note_html,
    )


def render_inputs_summary_expanders_and_tables_current_coordinator(**kwargs) -> None:
    BENDING_ROWS = kwargs["BENDING_ROWS"]
    SHEAR_ROWS = kwargs["SHEAR_ROWS"]
    CRACK_ROWS = kwargs["CRACK_ROWS"]
    DEFLECTION_ROWS = kwargs["DEFLECTION_ROWS"]
    defl_pack = kwargs["defl_pack"]
    bending_cap = kwargs["bending_cap"]
    bending_demand = kwargs["bending_demand"]
    bending_util_str = kwargs["bending_util_str"]
    bending_status = kwargs["bending_status"]
    shear_cap = kwargs["shear_cap"]
    shear_demand = kwargs["shear_demand"]
    shear_util_str = kwargs["shear_util_str"]
    shear_status = kwargs["shear_status"]
    shear_summary_status_note = kwargs["shear_summary_status_note"]
    shear_governing_name = kwargs["shear_governing_name"]
    shear_governing_source = kwargs["shear_governing_source"]
    shear_reason = kwargs["shear_reason"]
    crack_cap = kwargs["crack_cap"]
    crack_demand = kwargs["crack_demand"]
    crack_util_str = kwargs["crack_util_str"]
    crack_status = kwargs["crack_status"]
    defl_cap = kwargs["defl_cap"]
    defl_demand = kwargs["defl_demand"]
    defl_util_str = kwargs["defl_util_str"]
    defl_status = kwargs["defl_status"]

    inject_seamless_steps_css()

    if not BENDING_ROWS:
        st.info("Bending results not available yet. Check inputs or visit Bending page for details.")
    if not SHEAR_ROWS:
        st.info("Shear results not available yet. Check inputs or visit Shear page for details.")
    if not CRACK_ROWS:
        st.info("Crack results not available yet. Check inputs or visit Crack Control page for details.")
    if not DEFLECTION_ROWS:
        st.info("Deflection results not available yet. Check inputs or visit Deflection page for details.")

    shear_governing_is_sectional = shear_governing_source == "sectional_shear_capacity"
    shear_gov_note_parts = []
    if shear_governing_name and not shear_governing_is_sectional:
        shear_gov_note_parts.append(
            f"<div style='font-size:0.82rem;opacity:0.68;margin:0.35rem 0 0.1rem 0;'>"
            f"Governing check: {html.escape(shear_governing_name)}</div>"
        )
    if shear_reason and not shear_governing_is_sectional:
        shear_gov_note_parts.append(
            f"<div style='font-size:0.8rem;opacity:0.62;margin:0 0 0.15rem 0;'>"
            f"Reason: {html.escape(shear_reason)}</div>"
        )
    shear_gov_note_html = "".join(shear_gov_note_parts)

    summary_source = InputsSummarySourceSnapshot(
        scenario_id=str(st.session_state.get("active_beam_id") or "inputs"),
        scenario_label=str(st.session_state.get("active_beam_id") or "Inputs"),
        bending=InputsSummaryCardSource(
            family="bending",
            title="Bending &mdash; ULS check",
            capacity=str(bending_cap),
            action=str(bending_demand),
            utilisation=str(bending_util_str),
            status=str(bending_status),
            rows=tuple(dict(row) for row in BENDING_ROWS),
            capacity_label="Calculated capacity",
            action_label="Applied design action",
        ),
        shear=InputsSummaryCardSource(
            family="shear",
            title="Shear &mdash; ULS check",
            capacity=str(shear_cap),
            action=str(shear_demand),
            utilisation=str(shear_util_str),
            status=str(shear_status),
            rows=tuple(dict(row) for row in SHEAR_ROWS),
            capacity_label="Calculated capacity",
            action_label="Applied design action",
            status_note_html=str(shear_summary_status_note or ""),
        ),
        crack=InputsSummaryCardSource(
            family="crack",
            title="Crack control &mdash; SLS check",
            capacity=str(crack_cap),
            action=str(crack_demand),
            utilisation=str(crack_util_str),
            status=str(crack_status),
            rows=tuple(dict(row) for row in CRACK_ROWS),
            capacity_label="Calculated capacity",
            action_label="Applied design action",
        ),
        deflection=InputsSummaryCardSource(
            family="deflection",
            title="Deflection &mdash; SLS check",
            capacity=str(defl_cap),
            action=str(defl_demand),
            utilisation=str(defl_util_str),
            status=str(defl_status),
            rows=tuple(dict(row) for row in DEFLECTION_ROWS),
            capacity_label="Calculated capacity",
            action_label="Applied design action",
        ),
        geometry={},
        actions={},
        run_state={"deflection_summary_present": bool(defl_pack)},
    )
    summary_cards_html = _build_summary_cards_html_for_current_state(
        summary_source,
        shear_detail_note_html=shear_gov_note_html,
    )
    st.markdown(summary_cards_html, unsafe_allow_html=True)

    page_divider()


def render_inputs_summary_container_current(
    *,
    st_module,
    summary_container,
    sync_callbacks: dict,
    result_cache_key: str,
    inputs_show_landing_dashboard_fn,
    render_landing_card_fn,
    render_summary_expanders_and_tables_fn,
    BENDING_ROWS,
    SHEAR_ROWS,
    CRACK_ROWS,
    DEFLECTION_ROWS,
    defl_pack,
    governing_check,
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
) -> None:
    def render_summary_table(results):
        _ = results
        render_summary_expanders_and_tables_fn(
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

    with summary_container:
        st_module.title("Inputs")
        show_landing = inputs_show_landing_dashboard_fn()
        if show_landing:
            render_landing_card_fn(sync_callbacks=sync_callbacks, st_module=st_module)
        else:
            render_summary_table(st_module.session_state.get(result_cache_key))


__all__ = [
    "_build_summary_cards_html_for_current_state",
    "render_inputs_summary_container_current",
    "render_inputs_summary_expanders_and_tables_current_coordinator",
]
