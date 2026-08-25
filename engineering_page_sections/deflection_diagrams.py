"""Deflection diagram-section input adapters."""

from __future__ import annotations

import math
from typing import Any, Callable, Mapping


def deflection_diagram_reo_layers(
    D_mm: float,
    *,
    state: Mapping[str, Any],
    get_parameter: Callable[[str, Any], Any],
) -> dict:
    """Return visual-only reinforcement layers for the deflected-shape diagram."""

    def _as_float(value, default: float = 0.0) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return float(default)
        return result if math.isfinite(result) else float(default)

    def _first_number(*keys: str, default: float = 0.0) -> float:
        for key in keys:
            value = state.get(key)
            if value is None:
                value = get_parameter(key, None)
            if value is not None:
                return _as_float(value, default)
        return float(default)

    def _layers(section: str) -> list[dict]:
        is_bottom = section == "bot"
        cover = _first_number(
            "cover_bot" if is_bottom else "cover_top",
            default=40.0,
        )
        rowgap = _first_number(
            "defl_rowgap_bot" if is_bottom else "defl_rowgap_top",
            "rowgap_bot" if is_bottom else "rowgap_top",
            default=60.0,
        )
        row_count = int(
            max(
                min(
                    _first_number(
                        f"defl_{section}_row_count",
                        f"{section}_row_count",
                        default=1.0,
                    ),
                    4.0,
                ),
                0.0,
            )
        )
        layers = []
        previous_y = previous_db = None
        for row_idx in range(1, row_count + 1):
            count = int(
                max(
                    _first_number(
                        f"defl_{section}_row_{row_idx}_bars",
                        f"{section}_row_{row_idx}_bars",
                        f"defl_{section}{row_idx}_count",
                        f"{section}{row_idx}_count",
                        default=0.0,
                    ),
                    0.0,
                )
            )
            spacing = _first_number(
                f"defl_{section}_row_{row_idx}_spacing",
                f"{section}_row_{row_idx}_spacing",
                f"defl_{section}{row_idx}_spacing",
                f"{section}{row_idx}_spacing",
                default=0.0,
            )
            diameter = _first_number(
                f"defl_{section}_row_{row_idx}_dia",
                f"{section}_row_{row_idx}_dia",
                f"defl_db_{section}_{row_idx}",
                f"db_{section}_{row_idx}",
                default=20.0 if is_bottom else 16.0,
            )
            if diameter <= 0.0 or (count <= 0 and spacing <= 0.0):
                continue
            if previous_y is None:
                y_from_top = (
                    float(D_mm) - cover - 0.5 * diameter
                    if is_bottom
                    else cover + 0.5 * diameter
                )
            elif is_bottom:
                y_from_top = previous_y - 0.5 * previous_db - rowgap - 0.5 * diameter
            else:
                y_from_top = previous_y + 0.5 * previous_db + rowgap + 0.5 * diameter
            previous_y, previous_db = y_from_top, diameter
            layers.append(
                {
                    "count": count,
                    "spacing": spacing,
                    "db": diameter,
                    "y_from_top_mm": max(0.0, min(float(D_mm), y_from_top)),
                }
            )
        return layers

    return {"bottom": _layers("bot"), "top": _layers("top")}


__all__ = ["deflection_diagram_reo_layers"]
