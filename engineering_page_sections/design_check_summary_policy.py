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


def load_analysis_action_projection(
    *,
    uls_m_pos: float,
    uls_m_neg: float,
    uls_v: float,
    sls_m_pos: float,
    sls_m_neg: float,
    sls_v: float,
) -> dict[str, Any]:
    """Return the complete page-local action aliases for one analysis result.

    The engineering snapshot resolver intentionally supports historical action
    aliases.  A Load Analysis calculation must replace all of those aliases at
    its read-only calculation boundary; otherwise a Beam Inputs action can win
    precedence and leak into the analysis summary.
    """

    uls_pos = max(0.0, float(uls_m_pos))
    uls_neg = max(0.0, float(uls_m_neg))
    sls_pos = max(0.0, float(sls_m_pos))
    sls_neg = max(0.0, float(sls_m_neg))
    return {
        "actions_mode": "design",
        "actions_source": "Teaching SFD/BMD page (|M|max, |V|max)",
        "design_actions_source": "max",
        "M_pos_max_uls_kNm": uls_pos,
        "M_neg_min_uls_kNm": -uls_neg,
        "sfd_Mmax_abs_kNm": max(uls_pos, uls_neg),
        "sfd_Vmax_abs_kN": abs(float(uls_v)),
        "uls_Mstar": max(uls_pos, uls_neg),
        "uls_Mstar_pos_manual": uls_pos,
        "uls_Mstar_neg_manual": uls_neg,
        "uls_Vstar": abs(float(uls_v)),
        "M_pos_max_sls_kNm": sls_pos,
        "M_neg_min_sls_kNm": -sls_neg,
        "sfd_Msls_max_kNm": max(sls_pos, sls_neg),
        "sfd_Vsls_max_kN": abs(float(sls_v)),
        "sls_Mstar": max(sls_pos, sls_neg),
        "sls_Mstar_pos_manual": sls_pos,
        "sls_Mstar_neg_manual": sls_neg,
        "sls_Vstar": abs(float(sls_v)),
    }


def resolve_header_check_state(
    action: float,
    capacity: float | None,
    fallback_utilisation: str,
    rows: Iterable[Mapping[str, Any]],
) -> tuple[str, str]:
    """Resolve status and utilisation from the values visible in the card."""
    try:
        action_value = abs(float(action))
    except (TypeError, ValueError):
        action_value = 0.0
    if not math.isfinite(action_value) or action_value <= 1e-12:
        return "\u2014", "INFO"
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
