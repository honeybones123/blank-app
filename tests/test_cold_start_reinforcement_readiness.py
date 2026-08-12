from inputs_application.page_runtime.setup import (
    _reconcile_initial_reinforcement_widget_state,
)


def test_cold_start_reconciles_incomplete_active_row_from_valid_widget() -> None:
    state = {
        "bot_row_count": 1,
        "bot_row_1_bars": 0,
        "top_row_count": 1,
        "top_row_1_bars": 2,
    }

    reconciled, changed = _reconcile_initial_reinforcement_widget_state(
        state,
        {"inputs_bot_row_1_bars": 3},
    )

    assert changed is True
    assert reconciled["bot_row_1_bars"] == 3
    assert state["bot_row_1_bars"] == 0


def test_cold_start_does_not_repair_invalid_state_without_valid_widget() -> None:
    state = {
        "bot_row_count": 1,
        "bot_row_1_bars": 1,
        "top_row_count": 1,
        "top_row_1_bars": 2,
    }

    reconciled, changed = _reconcile_initial_reinforcement_widget_state(
        state,
        {"inputs_bot_row_1_bars": 1},
    )

    assert changed is False
    assert reconciled["bot_row_1_bars"] == 1


def test_cold_start_does_not_replace_an_already_valid_row() -> None:
    state = {
        "bot_row_count": 1,
        "bot_row_1_bars": 4,
        "top_row_count": 1,
        "top_row_1_bars": 2,
    }

    reconciled, changed = _reconcile_initial_reinforcement_widget_state(
        state,
        {"inputs_bot_row_1_bars": 3},
    )

    assert changed is False
    assert reconciled["bot_row_1_bars"] == 4
