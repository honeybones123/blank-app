from application.bottom_reinforcement_policy import (
    format_longitudinal_reinforcement_rows,
)


def test_compact_reinforcement_summary_keeps_every_active_row() -> None:
    state = {
        "bot_row_count": 2,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 24,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": 3,
        "bot_row_2_dia": 24,
    }

    assert (
        format_longitudinal_reinforcement_rows(state, face="bottom")
        == "3-N24 + 3-N24"
    )


def test_inactive_stored_second_row_is_not_displayed() -> None:
    state = {
        "bot_row_count": 1,
        "bot_row_1_bars": 3,
        "bot_row_1_dia": 20,
        "bot_row_2_bars": 3,
        "bot_row_2_dia": 20,
    }

    assert (
        format_longitudinal_reinforcement_rows(state, face="bottom")
        == "3-N20"
    )
