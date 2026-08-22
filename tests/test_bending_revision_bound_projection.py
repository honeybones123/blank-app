from __future__ import annotations

import inspect
from types import SimpleNamespace

import bending_core
from ui.diagrams import stress_strain_diagram
from inputs_application.engineering_input_store import InputSnapshotStore


def test_stress_strain_projection_uses_committed_revision_not_stale_mirrors(
    monkeypatch,
) -> None:
    session = {
        "active_beam_id": "B1",
        "b": 250.0,
        "D": 300.0,
        "bot1_count": 3,
        "db_bot_1": 10,
    }
    committed = {
        "b": 300.0,
        "D": 600.0,
        "cover_bot": 30.0,
        "cover_top": 30.0,
        "cover_side": 30.0,
        "rowgap_bot": 60.0,
        "lig_d": 10.0,
        "bot_row_count": 2,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 24,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": 3,
        "bot_row_2_dia": 24,
        "top_row_count": 1,
        "top_row_1_mode": "Count",
        "top_row_1_bars": 2,
        "top_row_1_dia": 10,
        "fc": 40.0,
        "fsy": 500.0,
        "Ec": 30000.0,
        "Es": 200000.0,
    }
    InputSnapshotStore(session).commit_for_beam(
        "B1", committed, source="test:apply"
    )
    monkeypatch.setattr(
        bending_core,
        "st",
        SimpleNamespace(session_state=session),
    )
    monkeypatch.setattr(
        bending_core,
        "current_authoritative_family",
        lambda _state, _family: {"dn_mm": 157.0, "d_mm": 531.0},
    )

    projection = bending_core._stress_strain_state("ULS")

    assert projection["b"] == 300.0
    assert projection["D"] == 600.0
    assert projection["d"] == 531.0
    assert projection["c"] == 157.0
    assert projection["d"] != 255.0
    assert projection["Ec"] == 30000.0
    assert projection["Es"] == 200000.0


def test_explicit_projection_state_and_authority_are_used_together() -> None:
    projection = bending_core._stress_strain_state(
        "ULS",
        input_state={
            "b": 325.0,
            "D": 650.0,
            "d": 590.0,
            "Ast_bot": 3769.9,
            "nb_bot": 3,
            "db_bot": 40.0,
            "cover_bot": 30.0,
            "rowgap_bot": 60.0,
            "lig_d": 10.0,
            "fc": 40.0,
            "fsy": 500.0,
            "Ec": 30000.0,
            "Es": 200000.0,
        },
        authoritative_bending={"dn_mm": 203.0, "d_mm": 590.0},
    )

    assert (projection["b"], projection["D"]) == (325.0, 650.0)
    assert projection["d"] == 590.0
    assert projection["c"] == 203.0


def test_plot_builder_cannot_replace_revision_bound_depth_with_widget_mirror() -> None:
    source = inspect.getsource(stress_strain_diagram.plot_stress_strain_profiles)

    assert 'state_dict.get("d", geom_bundle["d_value"])' in source
    assert 'get_param("d", geom_bundle["d_value"])' not in source
