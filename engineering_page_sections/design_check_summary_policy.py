"""Pure value-selection policy for the Design page check summary."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any


_NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")


def format_strength(value: float | None, units: str) -> str:
    if value is None or value <= 0 or not math.isfinite(float(value)):
        return "\u2014"
    return f"{value:.2f} {units}"


def resolve_header_check_state(
    action: float,
    capacity: float | None,
    fallback_utilisation: str,
    rows: Iterable[Mapping[str, Any]],
) -> tuple[str, str]:
    """Resolve status and utilisation from the values visible in the card."""
    utilisation = _ratio(action, capacity)
    if utilisation is None:
        utilisation = _first_number(fallback_utilisation)
    if utilisation is None:
        row_utilisations = [
            parsed
            for row in rows
            if (parsed := _first_number(row.get("util"))) is not None
        ]
        if row_utilisations:
            utilisation = max(row_utilisations)
    if utilisation is None:
        return "\u2014", "NOT CHECKED"
    if utilisation > 1.0:
        status = "FAIL"
    elif utilisation >= 0.9:
        status = "NEAR LIMIT"
    else:
        status = "PASS"
    return f"{utilisation:.2f}", status


def serviceability_values(
    rows: Iterable[Mapping[str, Any]], *, preferred_title: str = ""
) -> tuple[str, str, str, str]:
    materialised_rows = list(rows)
    preferred = str(preferred_title or "").strip().lower()
    primary = next(
        (row for row in materialised_rows if preferred and preferred in str(row.get("title") or "").lower()),
        next(
            (row for row in materialised_rows if row.get("is_primary")),
            next((row for row in materialised_rows if not row.get("is_informational")), {}),
        ),
    )
    return (
        str(primary.get("capacity") or primary.get("limit") or "\u2014"),
        str(primary.get("action") or primary.get("value") or "\u2014"),
        str(primary.get("util") or "\u2014"),
        str(primary.get("status") or "INFO"),
    )


def _ratio(action: float, capacity: float | None) -> float | None:
    try:
        action_value = abs(float(action))
        capacity_value = float(capacity) if capacity is not None else 0.0
    except (TypeError, ValueError):
        return None
    if action_value <= 1e-12 or capacity_value <= 0.0:
        return None
    if not math.isfinite(action_value) or not math.isfinite(capacity_value):
        return None
    return action_value / capacity_value


def _first_number(value: Any) -> float | None:
    match = _NUMBER_PATTERN.search(str(value or ""))
    return float(match.group(0)) if match else None
