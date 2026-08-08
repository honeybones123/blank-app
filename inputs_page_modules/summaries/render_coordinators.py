"""Inputs summary render coordinators."""

from __future__ import annotations

import streamlit as st

from widgets_helpers import page_divider
from application.design_actions_adapters import adapt_design_actions_from_state
from inputs_application.session_services import InputsSessionServices

from .builders import build_inputs_summary_html
from .models import InputsSummarySourceSnapshot
from .source_from_design_result import build_summary_source_from_design_result


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
    """Render only a revision-matched authoritative Design Brain result."""

    summary_state = dict(kwargs.get("summary_state") or {})
    services = InputsSessionServices.from_mapping(st.session_state)
    authoritative = services.engineering_results.current()
    if authoritative is None or not summary_state:
        st.session_state["_inputs_summary_authority"] = {
            "source": "unavailable",
            "reason": "missing_design_result",
        }
        st.info("Design checks are being calculated for the current inputs.")
        page_divider()
        return

    input_revision = int(services.input_snapshots.current().revision or 0)
    result_revision = services.engineering_results.source_input_revision()
    if result_revision is None or int(result_revision) != input_revision:
        st.session_state["_inputs_summary_authority"] = {
            "source": "unavailable",
            "reason": "revision_mismatch",
            "input_revision": input_revision,
            "result_revision": result_revision,
        }
        st.info("Design checks are being refreshed for the current inputs.")
        page_divider()
        return

    projection = build_summary_source_from_design_result(
        result=authoritative,
        actions=adapt_design_actions_from_state(summary_state),
        st_module=st,
        scenario_id=str(st.session_state.get("active_beam_id") or "inputs"),
        scenario_label=str(st.session_state.get("active_beam_id") or "Inputs"),
    )
    st.session_state["_inputs_summary_authority"] = {
        "source": "authoritative_design_result",
        "engineering_hash": authoritative.engineering_hash,
    }
    st.markdown(
        _build_summary_cards_html_for_current_state(projection.source),
        unsafe_allow_html=True,
    )
    page_divider()


def render_inputs_summary_container_current(
    *,
    st_module,
    summary_container,
    sync_callbacks: dict,
    render_title: bool = True,
    result_cache_key: str,
    inputs_show_landing_dashboard_fn,
    render_landing_card_fn,
    render_summary_expanders_and_tables_fn,
    summary_state=None,
) -> None:
    def render_summary_table(results):
        _ = results
        render_summary_expanders_and_tables_fn(
            summary_state=summary_state,
        )

    with summary_container:
        if render_title:
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
