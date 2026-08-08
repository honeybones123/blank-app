"""Longitudinal reinforcement row schema and snapshot migration policy."""

from __future__ import annotations

import copy

LONGITUDINAL_REO_MAX_ROWS = 4

def _longitudinal_row_key(section: str, row_index: int, field: str) -> str:
    return f"{section}_row_{row_index}_{field}"

def _build_longitudinal_row_defaults(section: str) -> dict:
    # Row-1 baseline matches NEW_BEAM_STARTER_DEFAULTS (3N10 bot, 2N10 top).
    default_bars = 2 if section == "top" else 3
    default_dia = 10.0
    defaults = {
        f"{section}_row_count": 1,
    }
    for row_index in range(1, LONGITUDINAL_REO_MAX_ROWS + 1):
        defaults[_longitudinal_row_key(section, row_index, "mode")] = "Count"
        defaults[_longitudinal_row_key(section, row_index, "bars")] = default_bars if row_index == 1 else 0
        defaults[_longitudinal_row_key(section, row_index, "spacing")] = 200
        defaults[_longitudinal_row_key(section, row_index, "dia")] = default_dia
    return defaults

def _longitudinal_row_param_keys(section: str) -> list[str]:
    keys = [f"{section}_row_count"]
    for row_index in range(1, LONGITUDINAL_REO_MAX_ROWS + 1):
        keys.extend([
            _longitudinal_row_key(section, row_index, "mode"),
            _longitudinal_row_key(section, row_index, "bars"),
            _longitudinal_row_key(section, row_index, "spacing"),
            _longitudinal_row_key(section, row_index, "dia"),
        ])
    return keys

def _longitudinal_row_tab_keys(page_prefix: str, section: str) -> dict:
    mappings = {
        f"{page_prefix}_{section}_row_count": f"{section}_row_count",
    }
    for row_index in range(1, LONGITUDINAL_REO_MAX_ROWS + 1):
        for field in ("mode", "bars", "spacing", "dia"):
            mappings[f"{page_prefix}_{section}_row_{row_index}_{field}"] = _longitudinal_row_key(section, row_index, field)
    return mappings

def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)

def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)

def _build_longitudinal_row_updates_from_legacy(source: dict | None) -> dict:
    source = source if isinstance(source, dict) else {}
    updates: dict[str, object] = {}
    for section in ("top", "bot"):
        legacy_prefix = "top" if section == "top" else "bot"
        default_bars = 2 if section == "top" else 4
        default_dia = 16.0 if section == "top" else 20.0
        active_row_count = 1
        for row_index in range(1, LONGITUDINAL_REO_MAX_ROWS + 1):
            mode_key = _longitudinal_row_key(section, row_index, "mode")
            bars_key = _longitudinal_row_key(section, row_index, "bars")
            spacing_key = _longitudinal_row_key(section, row_index, "spacing")
            dia_key = _longitudinal_row_key(section, row_index, "dia")
            if row_index <= 2:
                legacy_mode_key = f"{legacy_prefix}{row_index}_layout_mode"
                legacy_count_key = f"{legacy_prefix}{row_index}_count"
                legacy_spacing_key = f"{legacy_prefix}{row_index}_spacing"
                legacy_nb_or_s_key = f"nb_or_s_{legacy_prefix}_{row_index}"
                legacy_dia_key = f"db_{legacy_prefix}_{row_index}"
                mode = str(source.get(legacy_mode_key, "Count") or "Count")
                legacy_nb_or_s = _safe_float(source.get(legacy_nb_or_s_key, 0.0), 0.0)
                bars = _safe_int(
                    source.get(legacy_count_key, legacy_nb_or_s if mode == "Count" else (default_bars if row_index == 1 else 0)),
                    default_bars if row_index == 1 else 0,
                )
                spacing = _safe_int(
                    source.get(legacy_spacing_key, legacy_nb_or_s if mode == "Spacing" and legacy_nb_or_s > 0.0 else 200),
                    200,
                )
                dia = _safe_float(source.get(legacy_dia_key, default_dia), default_dia)
                is_active = bars > 0 or (mode == "Spacing" and legacy_nb_or_s > 0.0)
                if row_index == 1 or is_active:
                    active_row_count = max(active_row_count, row_index)
            else:
                mode = "Count"
                bars = 0
                spacing = 200
                dia = default_dia
            updates[mode_key] = mode
            updates[bars_key] = bars
            updates[spacing_key] = spacing
            updates[dia_key] = dia
        updates[f"{section}_row_count"] = active_row_count
    return updates

def _snapshot_uses_row_model(source: dict | None) -> bool:
    source = source if isinstance(source, dict) else {}
    return any(key in source for key in ("top_row_count", "bot_row_count"))

def migrate_longitudinal_reo_snapshot(snapshot: dict | None) -> dict:
    snapshot = copy.deepcopy(snapshot if isinstance(snapshot, dict) else {})
    if _snapshot_uses_row_model(snapshot):
        return snapshot
    snapshot.update(_build_longitudinal_row_updates_from_legacy(snapshot))
    return snapshot

__all__ = [
    "LONGITUDINAL_REO_MAX_ROWS", "migrate_longitudinal_reo_snapshot",
]


