from __future__ import annotations

from pathlib import Path
from inputs_v2.app import build_snapshot_payload

from streamlit.testing.v1 import AppTest
import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "inputs_v2" / "app.py"


def _started_app() -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=10).run()
    if not app.session_state["v2_design_started"]:
        next(button for button in app.button if button.label == "Go to Design Inputs").click().run()
    return app


def test_initial_state_matches_current_landing_flow() -> None:
    app = AppTest.from_file(str(APP), default_timeout=10).run()
    assert not app.exception
    assert app.session_state["v2_design_started"] is False
    assert any("Start Your Design" in item.value for item in app.markdown)
    assert any(button.label == "Go to Design Inputs" for button in app.button)


def test_runtime_reference_defaults_are_preserved_in_v2() -> None:
    app = _started_app()
    inputs = app.session_state["inputs_v2_beam_inputs"]
    assert (inputs.width_mm, inputs.depth_mm, inputs.span_mm) == (250.0, 300.0, 2000.0)
    assert (inputs.bottom.bars, inputs.bottom.diameter_mm) == (3, 10)
    assert (inputs.top.bars, inputs.top.diameter_mm) == (2, 10)
    assert (inputs.shear.diameter_mm, inputs.shear.legs) == (0, 0)


def test_json_snapshot_download_is_revision_tagged() -> None:
    app = _started_app()
    inputs = app.session_state["inputs_v2_beam_inputs"]
    payload = build_snapshot_payload("v2-lab-beam", inputs)
    assert payload["revision"] == inputs.revision
    assert payload["content_hash"] == inputs.content_hash
    assert payload["inputs"]["section_shape"] == inputs.section_shape


def test_first_slice_widget_edit_updates_diagram_revision() -> None:
    app = _started_app()
    assert not app.exception
    assert any("Calculation complete" in item.value for item in app.caption)
    assert len(app.number_input) >= 2
    assert len(app.selectbox) >= 3

    bars = next(widget for widget in app.selectbox if widget.label == "Bars")
    bars.set_value(7).run()
    assert not app.exception
    state = app.session_state["inputs_v2_beam_inputs"]
    assert state.revision == 1
    assert state.bottom.bars == 7
    assert len(app.get("plotly_chart")) == 1


def test_initial_widget_values_match_canonical_defaults() -> None:
    app = _started_app()
    assert not app.exception
    assert app.session_state["inputs_v2_beam_inputs"].span_mm == 2000.0
    assert app.session_state["v2_concrete_strength"] == 40
    assert app.session_state["v2_reinforcement_strength"] == 500
    assert app.session_state["v2_shear_spacing_mm"] == 200.0


def test_invalid_geometry_is_visible_without_partial_state_change() -> None:
    app = _started_app()
    width = next(widget for widget in app.number_input if widget.label == "Width b (mm)")
    width.set_value(100.0).run()
    original = app.session_state["inputs_v2_beam_inputs"]
    assert not app.exception
    assert app.session_state["inputs_v2_beam_inputs"] == original
    assert any("Beam width" in item.value for item in app.error)


@pytest.mark.skip(reason="Detailed-only controls are intentionally absent from the V1 Fast surface")
def test_extended_parity_controls_commit_through_canonical_model() -> None:
    app = _started_app()
    assert not app.exception
    assert any(widget.label == "Shrinkage time (days)" for widget in app.number_input)
    assert any(widget.label == "Number of ducts crossing web" for widget in app.number_input)
    assert any(widget.label == "Deflection support condition" for widget in app.selectbox)
    ducts = next(widget for widget in app.number_input if widget.label == "Number of ducts crossing web")
    ducts.set_value(2).run()
    state = app.session_state["inputs_v2_beam_inputs"]
    assert state.revision == 1
    assert state.voids.ducts == 2


@pytest.mark.skip(reason="V2 lab-only downloads are hidden from the V1-parity page")
def test_isolated_save_load_and_fixture_report_boundary() -> None:
    app = _started_app()
    save = next(button for button in app.button if button.label == "💾 Save")
    save.click().run()
    assert not app.exception
    assert "Saved revision" in app.session_state["v2_save_status"]
    assert any(button.label == "Load saved" for button in app.button)
    assert len(app.download_button) == 4
    assert any(item.label == "Download lab report (fixture)" for item in app.download_button)
    assert any(item.label == "Download lab report (CSV fixture)" for item in app.download_button)
    assert any(item.label == "Download Inputs V2 snapshot (JSON)" for item in app.download_button)


def test_section_shape_edit_uses_canonical_command() -> None:
    app = _started_app()
    shape = next(widget for widget in app.selectbox if widget.label == "Section shape")
    shape.set_value("T").run()
    assert not app.exception
    state = app.session_state["inputs_v2_beam_inputs"]
    assert state.section_shape == "T"
    assert state.revision == 1


def test_design_brain_family_and_preview_are_visible() -> None:
    app = _started_app()
    assert not app.exception
    assert any("Design Brain" in item.value for item in app.markdown)

def test_target_band_state_has_no_apply_button() -> None:
    app = _started_app()
    assert any(
        "No design actions entered. Add loads and the Design Brain will check and optimise your beam."
        in item.value
        for item in app.markdown
    )
    assert not any(button.label == "Apply recommendation" and not button.disabled for button in app.button)


def test_design_brain_selects_shear_family_when_shear_fails() -> None:
    app = _started_app()
    shear_action = next(widget for widget in app.number_input if widget.label == "Design shear Vu* (kN)")
    shear_action.set_value(300.0).run()
    assert not app.exception
    assert any("SHEAR_FAIL" in item.value for item in app.markdown)


def test_detailed_mode_exposes_time_dependent_and_void_inputs() -> None:
    app = _started_app()
    mode = next(widget for widget in app.radio if widget.label == "Design mode")
    mode.set_value("Detailed").run()
    assert not app.exception
    assert any(widget.label == "Shrinkage time (days)" for widget in app.number_input)
    assert any(widget.label == "Number of ducts crossing web" for widget in app.number_input)


@pytest.mark.skip(reason="Design Brain lab controls are not part of the V1 Inputs page")
def test_design_brain_fixture_applies_through_canonical_boundary() -> None:
    app = _started_app()
    apply_button = next(button for button in app.button if button.label == "Apply lab recommendation")
    apply_button.click().run()
    assert not app.exception
    assert app.session_state["inputs_v2_beam_inputs"].bottom.bars == 4
    assert app.session_state["inputs_v2_beam_inputs"].revision == 1


@pytest.mark.skip(reason="Lab persistence controls are not part of the V1 Inputs page")
def test_lab_persistence_action_writes_only_isolated_project_file() -> None:
    app = _started_app()
    persist = next(button for button in app.button if button.label == "Persist lab file")
    persist.click().run()
    assert not app.exception
    project_file = ROOT / "outputs" / "v2-projects" / "v2-lab-beam.json"
    assert project_file.exists()
    assert "Persisted revision" in app.session_state["v2_file_status"]


@pytest.mark.skip(reason="Lab persistence controls are not part of the V1 Inputs page")
def test_lab_persistence_action_restores_the_versioned_model() -> None:
    app = _started_app()
    persist = next(button for button in app.button if button.label == "Persist lab file")
    persist.click().run()
    restore = next(button for button in app.button if button.label == "Restore lab file")
    restore.click().run()
    assert not app.exception
    assert app.session_state["inputs_v2_beam_inputs"].revision == 0
    assert "Restored revision" in app.session_state["v2_file_status"]


@pytest.mark.skip(reason="Batch fixture controls are not part of the V1 Inputs page")
def test_batch_fixture_action_reports_each_isolated_beam_revision() -> None:
    app = _started_app()
    ids = next(widget for widget in app.text_input if widget.label == "Beam IDs (comma separated)")
    ids.set_value("B1, B2").run()
    next(button for button in app.button if button.label == "Calculate batch (fixture)").click().run()
    assert not app.exception
    assert app.session_state["v2_batch_status"] == "B1: revision 0; B2: revision 0"


@pytest.mark.skip(reason="Batch fixture controls are not part of the V1 Inputs page")
def test_batch_fixture_action_rejects_duplicate_beam_ids() -> None:
    app = _started_app()
    ids = next(widget for widget in app.text_input if widget.label == "Beam IDs (comma separated)")
    ids.set_value("B1, B1").run()
    next(button for button in app.button if button.label == "Calculate batch (fixture)").click().run()
    assert not app.exception
    assert app.session_state["v2_batch_status"] == "batch beam IDs must be unique"
