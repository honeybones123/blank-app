"""Revision-bound read model for the active beam's engineering inputs.

General result pages must not reconstruct geometry from mutable Streamlit
widget mirrors.  Design Brain Apply commits an immutable beam snapshot first;
this adapter projects that snapshot into the existing calculation-ready field
names without creating another state owner or publishing any result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

from inputs_application.engineering_input_store import (
    InputSnapshotState,
    InputSnapshotStore,
)
from inputs_application.engineering_state_projection import (
    rebuild_engineering_derived_state,
)


@dataclass(frozen=True)
class ActiveBeamEngineeringState:
    """One immutable presentation projection for the routed beam revision."""

    beam_id: str
    revision: int
    engineering_hash: str | None
    authority_hash: str | None
    values: Mapping[str, Any]
    source: str


def resolve_live_active_beam_id(
    session_state: Mapping[str, Any],
    *,
    fallback_beam_id: str | None = None,
) -> str:
    """Resolve the beam currently owned by live session routing.

    An outer Streamlit page-shell context can remain alive while the unified
    Inputs workspace fragment switches beams.  The session route is therefore
    the current identity; a captured context is only a startup fallback.
    """

    return str(
        session_state.get("active_beam_id")
        or session_state.get("_inputs_engineering_input_store_active_beam_id")
        or fallback_beam_id
        or ""
    ).strip()


def resolve_active_beam_engineering_state(
    session_state: MutableMapping[str, Any],
    *,
    beam_id: str | None = None,
) -> ActiveBeamEngineeringState:
    """Return calculation-ready values from the active committed snapshot.

    The session mapping is used only as a migration fallback when an old saved
    project has no typed beam snapshot yet.  It is copied before derivation so
    this read path can never mutate widget/session ownership.
    """

    resolved_beam_id = str(
        beam_id or resolve_live_active_beam_id(session_state)
    ).strip()
    snapshot = (
        InputSnapshotStore(session_state).current_for_beam(resolved_beam_id)
        if resolved_beam_id
        else InputSnapshotState()
    )
    if snapshot.snapshot:
        baseline = snapshot.to_dict()
        source = "committed_beam_snapshot"
    else:
        baseline = {
            str(key): value
            for key, value in dict(session_state).items()
            if not str(key).startswith("_")
        }
        source = "legacy_session_fallback"

    values = rebuild_engineering_derived_state(baseline)
    return ActiveBeamEngineeringState(
        beam_id=resolved_beam_id,
        revision=int(snapshot.revision or 0),
        engineering_hash=snapshot.engineering_hash,
        authority_hash=snapshot.authority_hash,
        values=dict(values),
        source=source,
    )


__all__ = [
    "ActiveBeamEngineeringState",
    "resolve_live_active_beam_id",
    "resolve_active_beam_engineering_state",
]
