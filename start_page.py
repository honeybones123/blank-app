"""Start-page presentation and initial navigation for the beam application."""

from __future__ import annotations

import copy
from typing import Any, Callable

import streamlit as st

from application.app_metadata import application_metadata
from application.disclaimer_config import DISCLAIMER
from application.opening_page_preferences import (
    clear_opening_page_preference,
    load_opening_page_preference,
    normalise_opening_page,
    save_opening_page_preference,
)
from ui.opening_page_preference_bridge import render_pending_guest_preference_write
from application.reference_registry import reference_entries
from application.user_preference_store import save_account_preference


PENDING_NAV_PAGE_SLUG_KEY = "_pending_nav_page_slug"
DISCLAIMER_ACCEPTANCE_PREFERENCE_KEY = "beam_disclaimer_accepted_version"
OPENING_PAGE_LABELS = {
    "start": "Start",
    "inputs": "Beam Inputs",
    "design": "Load Analysis",
}


def _render_card_styles() -> None:
    st.markdown(
        """
<style>
.start-page-intro { margin: .15rem 0 1rem; }
.start-page-intro p { margin: .3rem 0 0; color:#475569; font-size:.95rem; line-height:1.5; }
div[data-testid="stHorizontalBlock"]:has(.st-key-start_beam_inputs_card) { align-items:stretch !important; gap:1rem !important; }
.st-key-start_beam_inputs_card,
.st-key-start_load_analysis_card {
  height:100%; min-height:455px; box-sizing:border-box; padding:1rem;
  border:1px solid #dce3ec; border-radius:12px; background:#fff;
  box-shadow:0 3px 10px rgba(15,23,42,.06);
}
.st-key-start_load_analysis_card { border-color:rgba(37,99,235,.34); background:rgba(37,99,235,.035); }
.st-key-start_beam_inputs_card > div[data-testid="stVerticalBlock"],
.st-key-start_load_analysis_card > div[data-testid="stVerticalBlock"] { height:100%; }
.start-path-copy h3 { margin:0 0 .4rem !important; color:#182230 !important; font-size:1.08rem !important; font-weight:700 !important; }
.start-path-copy p { margin:0 0 .55rem; color:#334155; font-size:.92rem; font-weight:400; line-height:1.45; }
.start-path-copy p.secondary { margin-bottom:0; color:#64748b; font-size:.86rem; }
.st-key-start_open_beam_inputs,
.st-key-start_open_load_analysis { margin-top:auto !important; }
.st-key-start_open_beam_inputs button { border:1px solid #2563eb !important; background:#fff !important; color:#2563eb !important; }
.st-key-start_open_beam_inputs button:hover,
.st-key-start_open_beam_inputs button:focus-visible { border-color:#1d4ed8 !important; background:rgba(37,99,235,.06) !important; color:#1d4ed8 !important; }
.st-key-start_open_load_analysis button { border:1px solid #2563eb !important; background:#2563eb !important; color:#fff !important; }
.st-key-start_open_load_analysis button:hover,
.st-key-start_open_load_analysis button:focus-visible { border-color:#1d4ed8 !important; background:#1d4ed8 !important; color:#fff !important; }
.start-path-help { margin:.8rem 0 1.1rem; color:#475569; font-size:.9rem; }
.start-secondary-panel { border:1px solid #e2e8f0; border-radius:12px; padding:.9rem 1rem; background:#fff; }
.start-notice { border-left:4px solid #2563eb; background:rgba(37,99,235,.05); border-radius:10px; padding:.8rem .95rem; }
.start-notice h3 { margin:0 0 .3rem !important; font-size:1rem !important; }
.start-notice p { margin:0; color:#475569; font-size:.9rem; line-height:1.5; }
.start-metadata { margin:1.15rem 0 .2rem; color:#64748b; font-size:.78rem; line-height:1.45; }
@media (max-width:700px) {
  .st-key-start_beam_inputs_card,
  .st-key-start_load_analysis_card { min-height:0; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _compact_load_figures() -> tuple[Any, Any]:
    from ui.diagrams.moment_shear_diagram import (
        figure_bmd_from_state,
        plot_load_diagram_plotly,
    )

    load_figure = plot_load_diagram_plotly(
        case="Simple beam – UDL over entire span",
        L=6.0,
        params={"w": 12.0},
        support_condition="Simply supported",
    )
    load_figure.layout.annotations = tuple(
        annotation
        for annotation in (load_figure.layout.annotations or ())
        if bool(annotation.showarrow)
    )
    load_figure.update_layout(
        autosize=True,
        height=115,
        margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    load_figure.update_xaxes(visible=False)
    load_figure.update_yaxes(visible=False, range=[-0.34, 0.62])

    x_values = [index * 0.25 for index in range(25)]
    moment_values = [x_value * (6.0 - x_value) for x_value in x_values]
    bmd_figure = figure_bmd_from_state(
        {
            "x_plot": x_values,
            "M_plot": moment_values,
            "support_positions_plot": [0.0, 6.0],
            "support_types_plot": ["pinned", "roller"],
            "L": 6.0,
            "preview_x_m": None,
            "design_x_m": None,
            "preview_M": None,
            "x_pad": 0.35,
            "support_type": "simply_supported",
        }
    )
    bmd_figure.update_layout(
        autosize=True,
        height=105,
        margin=dict(l=4, r=4, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    bmd_figure.update_xaxes(visible=False)
    bmd_figure.update_yaxes(visible=False)
    return load_figure, bmd_figure


def _show_disclaimer_dialog(user_id: str) -> None:
    @st.dialog("Design disclaimer", width="large")
    def _dialog() -> None:
        st.caption(f"Version {DISCLAIMER.version} · Effective {DISCLAIMER.effective_date}")
        for heading, body in DISCLAIMER.full_sections:
            st.markdown(f"### {heading}")
            st.write(body)
        acknowledged = st.checkbox(
            "I have read and acknowledge this disclaimer.",
            key="start_disclaimer_acknowledge_checkbox",
        )
        if st.button(
            "Confirm acknowledgement",
            key="start_disclaimer_confirm",
            type="primary",
            disabled=not acknowledged,
            width="stretch",
        ):
            st.session_state["_accepted_disclaimer_version"] = DISCLAIMER.version
            if user_id:
                result = save_account_preference(
                    user_id,
                    DISCLAIMER_ACCEPTANCE_PREFERENCE_KEY,
                    DISCLAIMER.version,
                )
                if not result.saved:
                    st.warning("Acknowledgement was kept for this session because account storage is unavailable.")
            st.success("Disclaimer acknowledgement recorded.")

    _dialog()


def _show_full_references_dialog() -> None:
    @st.dialog("References and design basis", width="large")
    def _dialog() -> None:
        metadata = application_metadata()
        for entry in reference_entries():
            st.markdown(f"### {entry.standard_title} ({entry.identifier})")
            st.write(f"Edition: {entry.edition}")
            st.write(f"Amendment status: {entry.amendment_status}")
            st.write(f"Used for: {entry.application_use}")
            st.write("Modules/checks: " + ", ".join(entry.modules))
            st.caption(entry.qualifications)
        st.caption(f"Calculation engine: {metadata.calculation_engine_version}")

    _dialog()


def _show_assumptions_dialog() -> None:
    @st.dialog("Assumptions and limitations", width="large")
    def _dialog() -> None:
        for entry in reference_entries():
            if entry.key in {"assumptions_limitations", "clause_register"}:
                st.markdown(f"### {entry.row_title}")
                st.write(entry.application_use)
                st.caption(entry.qualifications)
        st.info("Calculation-specific assumptions and clause references remain on each calculation page.")

    _dialog()


def render_start_page(
    *,
    make_cross_section_figure_fn: Callable[[], Any],
    user_id: str = "",
) -> None:
    """Render navigation and design-basis content without owning calculations."""
    _render_card_styles()
    st.title("Start your beam design")
    st.markdown(
        '<div class="start-page-intro"><p>Choose whether to define the beam directly or calculate its design actions from applied loads.</p></div>',
        unsafe_allow_html=True,
    )

    def _navigate(page_slug: str) -> None:
        st.session_state[PENDING_NAV_PAGE_SLUG_KEY] = page_slug
        # Navigation is the one Start-page action that intentionally changes
        # the shell.  Other Start widgets remain inside the page fragment.
        st.rerun()

    beam_col, load_col = st.columns(2, gap="medium")
    with beam_col:
        with st.container(key="start_beam_inputs_card"):
            st.markdown(
                """
<div class="start-path-copy">
  <h3>Beam Inputs</h3>
  <p>Enter known design actions and define the beam size, materials and reinforcement.</p>
  <p class="secondary">Best when you already have design actions or want to check or edit an existing beam.</p>
</div>
""",
                unsafe_allow_html=True,
            )
            section_figure = copy.deepcopy(make_cross_section_figure_fn())
            if section_figure is not None:
                section_figure.update_layout(autosize=True, height=225, margin=dict(l=4, r=4, t=4, b=4))
                section_figure.update_xaxes(showticklabels=False, title_text=None)
                section_figure.update_yaxes(showticklabels=False, title_text=None)
                st.plotly_chart(
                    section_figure,
                    key="start_shared_beam_section_chart",
                    width="stretch",
                    config={"displayModeBar": False, "responsive": True},
                )
            st.button(
                "Open Beam Inputs",
                key="start_open_beam_inputs",
                width="stretch",
                on_click=_navigate,
                args=("inputs",),
            )

    with load_col:
        with st.container(key="start_load_analysis_card"):
            st.markdown(
                """
<div class="start-path-copy">
  <h3>Load Analysis</h3>
  <p>Define the supports, span and applied loads to calculate the beam's design actions and diagrams.</p>
  <p class="secondary">Best when you know the loads but have not calculated the design actions.</p>
</div>
""",
                unsafe_allow_html=True,
            )
            load_figure, bmd_figure = _compact_load_figures()
            st.plotly_chart(
                load_figure,
                key="start_shared_load_chart",
                width="stretch",
                config={"displayModeBar": False, "responsive": True},
            )
            st.plotly_chart(
                bmd_figure,
                key="start_shared_bmd_chart",
                width="stretch",
                config={"displayModeBar": False, "responsive": True},
            )
            st.button(
                "Open Load Analysis",
                key="start_open_load_analysis",
                width="stretch",
                on_click=_navigate,
                args=("design",),
            )

    st.markdown(
        '<p class="start-path-help">Not sure where to start? Use Load Analysis if you know the loads but not the design actions.</p>',
        unsafe_allow_html=True,
    )

    st.markdown("## Default opening page")
    st.write("Choose which page opens when you start a new beam design.")
    if user_id:
        saved_default = load_opening_page_preference(
            user_id=user_id,
            session_state=st.session_state,
        )
    else:
        query_saved = st.query_params.get("opening_page_pref")
        if isinstance(query_saved, list):
            query_saved = query_saved[0] if query_saved else None
        saved_default = normalise_opening_page(
            st.session_state.get("_opening_page_preference") or query_saved
        )
    st.session_state.setdefault("start_default_opening_page_choice", saved_default)
    selected_default = st.radio(
        "Default opening page",
        options=("start", "inputs", "design"),
        format_func=lambda value: OPENING_PAGE_LABELS[value],
        key="start_default_opening_page_choice",
        horizontal=True,
        label_visibility="collapsed",
    )
    remember = st.checkbox("Remember my choice", key="start_remember_opening_page")

    def _clear_saved_opening_preference() -> None:
        result = clear_opening_page_preference(
            user_id=user_id,
            session_state=st.session_state,
        )
        if result is not None and not result.saved:
            st.session_state["_start_preference_flash"] = (
                "warning",
                result.error or "The account preference could not be cleared.",
            )
        else:
            st.session_state["_start_preference_flash"] = (
                "success",
                "Saved preference cleared. New beam designs will open on Start.",
            )

    save_col, clear_col = st.columns(2, gap="small")
    with save_col:
        if st.button("Save opening preference", key="start_save_opening_preference", width="stretch"):
            result = save_opening_page_preference(
                user_id=user_id,
                value=selected_default,
                remember=remember,
                session_state=st.session_state,
            )
            if result is not None and not result.saved:
                st.warning(result.error or "The account preference could not be saved.")
            else:
                st.success("Opening preference saved. It will apply to new beam designs.")
    with clear_col:
        st.button(
            "Clear saved preference",
            key="start_clear_opening_preference",
            width="stretch",
            on_click=_clear_saved_opening_preference,
        )

    flash = st.session_state.pop("_start_preference_flash", None)
    if isinstance(flash, tuple) and len(flash) == 2:
        level, message = flash
        if level == "warning":
            st.warning(str(message))
        else:
            st.success(str(message))

    st.markdown("## Getting started")
    with st.container(key="start_getting_started"):
        st.markdown(
            "1. Define the beam geometry, materials and reinforcement.\n"
            "2. Enter known design actions or calculate them from supports and loads.\n"
            "3. Review the design checks and Design Brain recommendations."
        )

    st.markdown("## Important design notice")
    st.markdown(
        f'<div class="start-notice"><h3>Important design notice</h3><p>{DISCLAIMER.short_notice}</p></div>',
        unsafe_allow_html=True,
    )
    if st.button("Read full disclaimer", key="start_read_full_disclaimer"):
        _show_disclaimer_dialog(user_id)

    st.markdown("## References and design basis")
    st.write(
        "Calculations are based on the Australian Standards, project inputs and engineering assumptions identified below. "
        "Confirm that the nominated standards, editions and project requirements are appropriate for the design."
    )
    for entry in reference_entries():
        label = f"{entry.row_title} · {entry.identifier} · {entry.edition}"
        with st.expander(label, expanded=False):
            st.write(entry.standard_title)
            st.caption(entry.amendment_status)
    refs_col, assumptions_col = st.columns(2, gap="small")
    with refs_col:
        if st.button("View full references", key="start_view_full_references", width="stretch"):
            _show_full_references_dialog()
    with assumptions_col:
        if st.button(
            "View assumptions and limitations",
            key="start_view_assumptions",
            width="stretch",
        ):
            _show_assumptions_dialog()

    metadata = application_metadata()
    st.markdown(
        (
            '<p class="start-metadata">'
            f'Application {metadata.application_version} · '
            f'Calculation engine {metadata.calculation_engine_version} · '
            f'References {metadata.reference_set_version} · '
            f'Last updated {metadata.last_updated_date}'
            '</p>'
        ),
        unsafe_allow_html=True,
    )
    render_pending_guest_preference_write(st.session_state)


__all__ = ["render_start_page"]
