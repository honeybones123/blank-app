from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_load_analysis_edit_survives_navigation_without_branch_copy() -> None:
    app = AppTest.from_file("streamlit_app.py", default_timeout=60).run()
    app.radio[0].set_value("design")
    app.run()

    dead_udl = next(widget for widget in app.number_input if widget.key == "load_g_udl")
    dead_udl.set_value(12.0)
    app.run()

    state = app.session_state.filtered_state
    beam_id = str(state["active_beam_id"])
    stored = state["_load_analysis_snapshot_by_beam_v1"][beam_id]
    assert stored["analysis"]["g_udl_kNm_per_m"] == 12.0
    stored_revision = int(stored["revision"])

    app.radio[0].set_value("inputs")
    app.run()
    app.radio[0].set_value("design")
    app.run()

    returned = next(widget for widget in app.number_input if widget.key == "load_g_udl")
    state = app.session_state.filtered_state
    stored = state["_load_analysis_snapshot_by_beam_v1"][beam_id]
    assert returned.value == 12.0
    assert stored["analysis"]["g_udl_kNm_per_m"] == 12.0
    assert int(stored["revision"]) == stored_revision
    assert not app.exception


def test_current_page_slug_wins_over_stale_compatibility_marker() -> None:
    app = AppTest.from_file("streamlit_app.py", default_timeout=60).run()
    app.radio[0].set_value("design")
    app.run()

    # Reproduce the live navigation condition that previously lost loads:
    # the current router says design while the old compatibility marker still
    # names Inputs when the widget callback executes.
    app.session_state["page_slug"] = "design"
    app.session_state["_active_page_slug"] = "inputs"
    dead_udl = next(widget for widget in app.number_input if widget.key == "load_g_udl")
    dead_udl.set_value(7.0)
    app.run()

    state = app.session_state.filtered_state
    beam_id = str(state["active_beam_id"])
    stored = state["_load_analysis_snapshot_by_beam_v1"][beam_id]
    assert stored["analysis"]["g_udl_kNm_per_m"] == 7.0
    assert not app.exception
