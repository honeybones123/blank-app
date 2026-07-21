"""Design Guide update-family classification helpers."""

from __future__ import annotations


_COMPOUND_GEOMETRY_UPDATE_KEYS = frozenset(
    {"b", "bw", "D", "bf", "tf", "tw", "bf_bot", "tf_bot"},
)
_COMPOUND_BOTTOM_UPDATE_KEYS = frozenset(
    {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "bot1_spacing",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "bot2_spacing",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
        "bot_row_3_mode",
        "bot_row_3_bars",
        "bot_row_3_spacing",
        "bot_row_3_dia",
        "bot_row_4_mode",
        "bot_row_4_bars",
        "bot_row_4_spacing",
        "bot_row_4_dia",
        "Ast_bot",
    },
)
_COMPOUND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})


def _compound_subfamilies_from_updates(updates: dict) -> list[str]:
    if not updates:
        return []
    keys = set(updates.keys())
    out: list[str] = []
    if keys & _COMPOUND_GEOMETRY_UPDATE_KEYS:
        out.append("geometry")
    if keys & _COMPOUND_BOTTOM_UPDATE_KEYS:
        out.append("bottom_reo")
    if keys & _COMPOUND_SHEAR_UPDATE_KEYS:
        out.append("shear")
    return out


__all__ = [
    "_COMPOUND_BOTTOM_UPDATE_KEYS",
    "_COMPOUND_GEOMETRY_UPDATE_KEYS",
    "_COMPOUND_SHEAR_UPDATE_KEYS",
    "_compound_subfamilies_from_updates",
]
