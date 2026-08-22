from __future__ import annotations

from inputs_application.active_beam_engineering_state import (
    resolve_live_active_beam_id,
    resolve_active_beam_engineering_state,
)
from inputs_application.engineering_input_store import InputSnapshotStore


def test_committed_beam_snapshot_wins_over_stale_widget_mirrors() -> None:
    session = {
        "active_beam_id": "B1",
        # Deliberately stale pre-Apply compatibility mirrors.
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
        "rowgap_top": 60.0,
        "lig_d": 10,
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
    }
    InputSnapshotStore(session).commit_for_beam(
        "B1", committed, source="test:design_brain_apply"
    )

    resolved = resolve_active_beam_engineering_state(session)

    assert resolved.source == "committed_beam_snapshot"
    assert resolved.values["b"] == 300.0
    assert resolved.values["D"] == 600.0
    assert resolved.values["nb_bot"] == 6
    assert resolved.values["Ast_bot"] > 2700.0
    assert resolved.values["d"] > 500.0


def test_active_beam_switch_selects_each_beams_own_revision() -> None:
    session = {"active_beam_id": "B1"}
    store = InputSnapshotStore(session)
    store.commit_for_beam(
        "B1",
        {"b": 250.0, "D": 300.0, "bot1_count": 3, "db_bot_1": 10},
        source="test:B1",
    )
    store.commit_for_beam(
        "B2",
        {"b": 400.0, "D": 700.0, "bot1_count": 4, "db_bot_1": 20},
        source="test:B2",
    )

    session["active_beam_id"] = "B1"
    b1 = resolve_active_beam_engineering_state(session)
    session["active_beam_id"] = "B2"
    b2 = resolve_active_beam_engineering_state(session)

    assert (b1.beam_id, b1.values["b"], b1.values["D"]) == ("B1", 250.0, 300.0)
    assert (b2.beam_id, b2.values["b"], b2.values["D"]) == ("B2", 400.0, 700.0)


def test_live_beam_route_wins_over_stale_page_shell_context() -> None:
    session = {
        "active_beam_id": "B2",
        "_inputs_engineering_input_store_active_beam_id": "B1",
    }

    assert resolve_live_active_beam_id(
        session,
        fallback_beam_id="B1",
    ) == "B2"


def test_single_beam_projection_uses_input_store_route_without_batch_id() -> None:
    session: dict[str, object] = {}
    store = InputSnapshotStore(session)
    committed = store.commit_for_beam(
        "active",
        {
            "b": 275.0,
            "D": 550.0,
            "cover_bot": 40.0,
            "bot_row_count": 1,
            "bot_row_1_bars": 2,
            "bot_row_1_dia": 32,
        },
        source="test:single_beam_apply",
    )

    # A non-batch session need not expose the batch compatibility route.
    assert "active_beam_id" not in session
    projected = resolve_active_beam_engineering_state(session)

    assert projected.beam_id == "active"
    assert projected.revision == committed.revision
    assert projected.source == "committed_beam_snapshot"
    assert projected.values["b"] == 275.0
    assert projected.values["D"] == 550.0
