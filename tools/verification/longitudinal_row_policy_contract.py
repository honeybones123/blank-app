from application.longitudinal_row_policy import (
    _build_longitudinal_row_defaults,
    _build_longitudinal_row_updates_from_legacy,
    _longitudinal_row_param_keys,
    _longitudinal_row_tab_keys,
    migrate_longitudinal_reo_snapshot,
)


def main() -> None:
    defaults = _build_longitudinal_row_defaults("bot")
    assert defaults["bot_row_count"] == 1
    assert defaults["bot_row_1_bars"] == 3
    assert defaults["bot_row_4_bars"] == 0
    assert len(_longitudinal_row_param_keys("bot")) == 17
    assert _longitudinal_row_tab_keys("inputs", "top")["inputs_top_row_2_dia"] == "top_row_2_dia"

    legacy = {
        "bot1_layout_mode": "Count", "bot1_count": 5, "db_bot_1": 20.0,
        "bot2_layout_mode": "Spacing", "bot2_spacing": 150, "db_bot_2": 16.0,
        "nb_or_s_bot_2": 150,
    }
    updates = _build_longitudinal_row_updates_from_legacy(legacy)
    assert updates["bot_row_count"] == 2
    assert updates["bot_row_1_bars"] == 5
    assert updates["bot_row_2_mode"] == "Spacing"
    assert updates["bot_row_2_spacing"] == 150

    migrated = migrate_longitudinal_reo_snapshot(legacy)
    assert migrated["bot_row_1_bars"] == 5
    existing = {"bot_row_count": 3, "bot_row_1_bars": 9}
    assert migrate_longitudinal_reo_snapshot(existing) == existing
    assert migrate_longitudinal_reo_snapshot(existing) is not existing
    print("longitudinal_row_policy_contract PASS")


if __name__ == "__main__":
    main()
