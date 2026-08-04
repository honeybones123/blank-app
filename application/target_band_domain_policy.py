"""Application-owned target-band domain update policy."""

from __future__ import annotations


_TARGET_BAND_GEOMETRY_UPDATE_KEYS = frozenset(
    {"b", "bw", "D", "bf", "tf", "tw", "bf_bot", "tf_bot"},
)
_TARGET_BAND_BOTTOM_UPDATE_KEYS = frozenset(
    {
        "bot_row_count", "bot1_layout_mode", "bot1_count", "bot1_spacing", "db_bot_1",
        "bot2_layout_mode", "bot2_count", "bot2_spacing", "db_bot_2",
        "bot_row_1_mode", "bot_row_1_bars", "bot_row_1_spacing", "bot_row_1_dia",
        "bot_row_2_mode", "bot_row_2_bars", "bot_row_2_spacing", "bot_row_2_dia",
        "bot_row_3_mode", "bot_row_3_bars", "bot_row_3_spacing", "bot_row_3_dia",
        "bot_row_4_mode", "bot_row_4_bars", "bot_row_4_spacing", "bot_row_4_dia",
        "Ast_bot",
    },
)
_TARGET_BAND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})


def resolve_target_band_domains_touched_by_updates(
    updates: dict[str, object] | None,
) -> set[str]:
    """Return target-band domains affected by a plain update payload."""

    keys = set(dict(updates or {}).keys())
    touched: set[str] = set()
    if keys & _TARGET_BAND_SHEAR_UPDATE_KEYS:
        touched.add("shear")
    if keys & (_TARGET_BAND_BOTTOM_UPDATE_KEYS | _TARGET_BAND_GEOMETRY_UPDATE_KEYS):
        touched.add("bending")
    return touched


def resolve_target_band_candidate_domains_for_updates(
    base_domains: list[str] | tuple[str, ...] | set[str] | None,
    updates: dict[str, object] | None = None,
) -> list[str]:
    """Merge existing target-band domains with domains touched by updates."""

    domains = {str(domain or "").strip().lower() for domain in (base_domains or [])}
    domains |= resolve_target_band_domains_touched_by_updates(updates)
    return [domain for domain in ("bending", "shear") if domain in domains]


__all__ = [
    "resolve_target_band_candidate_domains_for_updates",
    "resolve_target_band_domains_touched_by_updates",
]
