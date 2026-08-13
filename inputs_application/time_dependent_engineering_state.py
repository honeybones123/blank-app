"""Committed engineering projection for creep and shrinkage pages.

The time-dependent pages historically read mutable session mirrors.  Inputs now
commits through :class:`InputSnapshotStore`, so those mirrors can be stale after
fragment edits or Design Brain Apply.  This module provides one read-only
boundary from the active beam snapshot to the values needed by creep and
shrinkage.  It performs no publication and mutates no session state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

from calculations.deflection import derive_sustained_stress_ratio
from calculations.design_actions import resolve_design_actions_from_state
from inputs_application.engineering_input_store import InputSnapshotState, InputSnapshotStore
from inputs_application.engineering_state_projection import (
    rebuild_engineering_derived_state,
)
from section_props.props import compute_gross_props


@dataclass(frozen=True)
class TimeDependentEngineeringState:
    beam_id: str
    revision: int
    engineering_hash: str | None
    values: Mapping[str, Any]


def _section_dimensions(state: Mapping[str, Any]) -> tuple[str, dict[str, float]]:
    shape = str(state.get("sec_shape") or "RECT").strip().upper()
    if shape not in {"RECT", "T", "I"}:
        shape = "RECT"
    dimensions = {
        key: float(state.get(key, 0.0) or 0.0)
        for key in ("b", "D", "bf", "tf", "bw", "tw")
    }
    return shape, dimensions


def resolve_time_dependent_engineering_state(
    session_state: MutableMapping[str, Any],
    *,
    beam_id: str | None = None,
) -> TimeDependentEngineeringState:
    """Resolve current creep/shrinkage drivers from the committed beam input.

    Load Analysis page-local loads are deliberately absent.  Only the committed
    Inputs snapshot and its own ULS/SLS action contract are considered.
    """

    resolved_beam_id = str(
        beam_id or session_state.get("active_beam_id") or ""
    ).strip()
    store = InputSnapshotStore(session_state)
    snapshot = (
        store.current_for_beam(resolved_beam_id)
        if resolved_beam_id
        else InputSnapshotState()
    )
    if not snapshot.snapshot:
        # Old saved sessions are readable during migration, but this fallback is
        # a defensive copy and never becomes a second write owner.
        baseline = {
            key: value
            for key, value in dict(session_state).items()
            if not str(key).startswith("_")
        }
        revision = 0
        engineering_hash = None
    else:
        baseline = dict(snapshot.snapshot)
        revision = int(snapshot.revision)
        engineering_hash = snapshot.engineering_hash

    values = rebuild_engineering_derived_state(baseline)
    shape, dimensions = _section_dimensions(values)
    try:
        gross = compute_gross_props(shape, dimensions)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        gross = compute_gross_props("RECT", dimensions)
    values.update(gross)

    actions = resolve_design_actions_from_state(values)
    sustained = derive_sustained_stress_ratio(
        fc_mpa=float(values.get("fc", 0.0) or 0.0),
        sls_m_pos_kNm=float(actions.get("SLS_M_pos", 0.0) or 0.0),
        sls_m_neg_kNm=float(actions.get("SLS_M_neg", 0.0) or 0.0),
        z_top_mm3=float(gross.get("Ztop_g", 0.0) or 0.0),
        z_bot_mm3=float(gross.get("Zbot_g", 0.0) or 0.0),
    )
    values.update(
        {
            "stress_ratio": float(sustained["stress_ratio"]),
            "sustained_Mstar_kNm": float(sustained["M_sust_kNm"]),
            "sustained_sigma_cs_mpa": float(sustained["sigma_cs_mpa"]),
            "sustained_section_modulus_mm3": float(sustained["Z_comp_mm3"]),
            "sustained_compression_fibre": str(sustained["compression_fibre"]),
        }
    )
    return TimeDependentEngineeringState(
        beam_id=resolved_beam_id,
        revision=revision,
        engineering_hash=engineering_hash,
        values=dict(values),
    )


__all__ = [
    "TimeDependentEngineeringState",
    "resolve_time_dependent_engineering_state",
]
