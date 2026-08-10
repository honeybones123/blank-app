from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _inputs_app() -> AppTest:
    app = AppTest.from_file("streamlit_app.py", default_timeout=60).run()
    app.radio[0].set_value("inputs")
    return app.run()


def _selector(app: AppTest):
    return next(
        toggle
        for toggle in app.toggle
        if toggle.label == "Use Load Analysis design as main"
    )


def _width(app: AppTest):
    return next(
        widget for widget in app.number_input if widget.label == "Width b (mm)"
    )


def _branches(app: AppTest) -> dict:
    return app.session_state.filtered_state["_beam_design_branch_snapshots_v1"][
        "beam_1"
    ]


def test_selector_preserves_independent_branches_and_creates_no_design_revision() -> None:
    app = _inputs_app()
    assert not app.exception

    # One typed edit changes the displayed branch exactly once, and rendering
    # the unchanged page cannot manufacture another engineering revision.
    initial = _branches(app)["beam_inputs"]
    _width(app).set_value(275.0)
    app.run()
    edited = _branches(app)["beam_inputs"]
    assert edited["revision"] == initial["revision"] + 1
    assert edited["payload"]["b"] == 275.0
    app.run()
    assert _branches(app)["beam_inputs"]["revision"] == edited["revision"]

    before_toggle = _branches(app)
    selection_before = app.session_state.filtered_state[
        "_beam_main_design_selection_v1"
    ]["beam_1"]
    _selector(app).set_value(True)
    app.run()
    after_toggle = _branches(app)
    selection_after = app.session_state.filtered_state[
        "_beam_main_design_selection_v1"
    ]["beam_1"]
    assert _selector(app).value is True
    assert any(
        caption.value == "Main design: Load Analysis" for caption in app.caption
    )
    assert selection_after["revision"] == selection_before["revision"] + 1
    assert after_toggle["beam_inputs"]["revision"] == before_toggle["beam_inputs"]["revision"]
    assert after_toggle["load_analysis"]["revision"] == before_toggle["load_analysis"]["revision"]

    # Inputs now edits only LOAD_ANALYSIS. The stored Beam Inputs design stays
    # intact and returns exactly when the display pointer is switched back.
    load_before = after_toggle["load_analysis"]
    _width(app).set_value(325.0)
    app.run()
    load_edited = _branches(app)
    assert load_edited["load_analysis"]["revision"] == load_before["revision"] + 1
    assert load_edited["load_analysis"]["payload"]["b"] == 325.0
    assert load_edited["beam_inputs"]["payload"]["b"] == 275.0
    app.run()
    assert (
        _branches(app)["load_analysis"]["revision"]
        == load_edited["load_analysis"]["revision"]
    )

    before_restore = _branches(app)
    _selector(app).set_value(False)
    app.run()
    restored = _branches(app)
    assert _selector(app).value is False
    assert _width(app).value == 275.0
    assert any(caption.value == "Main design: Beam Inputs" for caption in app.caption)
    assert restored["beam_inputs"]["revision"] == before_restore["beam_inputs"]["revision"]
    assert restored["load_analysis"]["revision"] == before_restore["load_analysis"]["revision"]
    assert not app.exception

