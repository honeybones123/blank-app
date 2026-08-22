"""Passive authoritative capacity projection for the editable beam table.

The table needs immediate engineering status, but it must never start Design
Brain recommendation search.  This module calls only the adapter's explicit
``evaluate_current_case`` boundary, caches that calculation-only result, and
projects it onto the visible rows.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any, Mapping, MutableMapping

import pandas as pd

from batch_design.models import BatchBeamCase, BatchDesignResult
from batch_design.runner import current_capacity_projection
from batch_design.ui.project_beam_load_table import project_beam_cases_from_frame


PASSIVE_CAPACITY_CACHE_KEY = "_batch_design_passive_capacity_cache_v1"
PASSIVE_CAPACITY_CACHE_LIMIT = 64


def _stable_fingerprint(
    case: BatchBeamCase,
    *,
    base_state: Mapping[str, Any],
    assumptions: Mapping[str, Any] | None,
) -> str:
    payload = {
        "case": asdict(case),
        # This is the stored parameter snapshot for one beam, not the raw
        # Streamlit session.  It contains the geometry, materials and reo that
        # define the authoritative calculation.
        "base_state": dict(base_state),
        "assumptions": dict(assumptions or {}),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _empty_projection(*, error: str | None = None) -> dict[str, Any]:
    return {
        "calculated": False,
        "passed": None,
        "utilisation": None,
        "family_utilisations": {},
        "family_capacities": {},
        "statuses": {},
        "error": error,
    }


def _apply_projection(row: dict[str, Any], projection: Mapping[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    capacities = dict(projection.get("family_capacities") or {})
    utilisations = dict(projection.get("family_utilisations") or {})
    statuses = {
        str(key): str(value or "").strip().upper()
        for key, value in dict(projection.get("statuses") or {}).items()
    }
    error = str(projection.get("error") or "").strip()
    passed = projection.get("passed")
    overall = "CHECK" if error else ("PASS" if passed is True else "FAIL")
    if passed is None and not error:
        overall = "NOT RUN"

    updated.update(
        {
            "capacity_status": overall,
            "overall_status": overall,
            "strength_status": "FAIL" if any(
                statuses.get(name) == "FAIL" for name in ("bending", "shear")
            ) else ("PASS" if overall == "PASS" else overall),
            "bending_status": statuses.get("bending", overall),
            "shear_status": statuses.get("shear", overall),
            "crack_status": statuses.get("crack", statuses.get("crack_control", overall)),
            "deflection_status": statuses.get("deflection", overall),
            "design_utilisation": projection.get("utilisation"),
            "current_utilisation": projection.get("utilisation"),
            "current_phi_mu_knm": capacities.get("bending"),
            "current_phi_vu_kn": capacities.get("shear"),
            "Mu_utilisation": utilisations.get("bending"),
            "Vu_utilisation": utilisations.get("shear"),
            "bending_utilisation": utilisations.get("bending"),
            "shear_utilisation": utilisations.get("shear"),
            "crack_utilisation": utilisations.get("crack"),
            "deflection_utilisation": utilisations.get("deflection"),
            "passive_capacity_error": error or None,
        }
    )
    return updated


def apply_passive_capacity_checks(
    frame: pd.DataFrame,
    *,
    adapter: Any,
    beam_records: Mapping[str, Any] | None,
    assumptions: Mapping[str, Any] | None,
    cache: MutableMapping[str, dict[str, Any]],
) -> pd.DataFrame:
    """Return rows with immediate capacity status and no recommendation search."""

    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy(deep=True)

    evaluate_current_case = getattr(adapter, "evaluate_current_case", None)
    rows = [dict(row) for row in frame.to_dict("records")]
    cases_by_member = {
        str(case.member_id): case for case in project_beam_cases_from_frame(frame)
    }
    records = dict(beam_records or {})
    active_fingerprints: set[str] = set()
    projected_rows: list[dict[str, Any]] = []

    for row in rows:
        member_id = str(row.get("beam_id") or "").strip()
        case = cases_by_member.get(member_id)
        if case is None:
            projected_rows.append(
                _apply_projection(row, _empty_projection())
            )
            continue
        if not callable(evaluate_current_case):
            projected_rows.append(
                _apply_projection(
                    row,
                    _empty_projection(error="Authoritative capacity evaluator is unavailable."),
                )
            )
            continue

        record = records.get(member_id)
        base_state = (
            dict(record.get("params") or {})
            if isinstance(record, dict)
            else {}
        )
        if not base_state:
            base_state = dict(row)
        fingerprint = _stable_fingerprint(
            case,
            base_state=base_state,
            assumptions=assumptions,
        )
        active_fingerprints.add(fingerprint)
        projection = cache.get(fingerprint)
        if not isinstance(projection, dict):
            try:
                result = evaluate_current_case(
                    case,
                    assumptions=assumptions,
                    base_state=base_state,
                )
                if not isinstance(result, BatchDesignResult):
                    raise TypeError("Current capacity evaluator returned an invalid result.")
                projection = current_capacity_projection(result)
            except Exception as exc:  # table remains usable with an explicit row state
                projection = _empty_projection(error=str(exc))
            cache[fingerprint] = dict(projection)
        projected_rows.append(_apply_projection(row, projection))

    # Keep the presentation cache bounded to live/recent beam identities.
    for key in tuple(cache):
        if key not in active_fingerprints and len(cache) > PASSIVE_CAPACITY_CACHE_LIMIT:
            cache.pop(key, None)
    while len(cache) > PASSIVE_CAPACITY_CACHE_LIMIT:
        cache.pop(next(iter(cache)), None)

    return pd.DataFrame(projected_rows, columns=projected_rows[0].keys())


__all__ = [
    "PASSIVE_CAPACITY_CACHE_KEY",
    "PASSIVE_CAPACITY_CACHE_LIMIT",
    "apply_passive_capacity_checks",
]
