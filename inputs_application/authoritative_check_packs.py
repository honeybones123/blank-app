"""Read-only access to the current V2 engineering check packs.

This is a presentation adapter, not a calculation path.  Result pages may use
it to render the same already-published checks as Inputs and Design Brain.
When no revision-matched authoritative result exists, callers receive an
explicit unavailable pack.  Result pages must never silently recalculate with
an older page-local implementation.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from application.design_result_store import EngineeringResultStore
from application.contracts.design_brain import coerce_authoritative_design_result
from inputs_application.engineering_input_store import InputSnapshotStore


_RESULTS_BY_BEAM_KEY = "_inputs_authoritative_design_result_by_beam_v1"
_RESULT_REVISIONS_BY_BEAM_KEY = (
    "_inputs_authoritative_design_result_revision_by_beam_v1"
)


def _current_result_and_input_state(
    state: Mapping[str, Any],
) -> tuple[Any, Any, int | None]:
    """Resolve the beam-owned publication before the transient active slot.

    General calculation pages share the active beam but do not mount the
    Inputs workspace.  Their read path must therefore use the persistent
    per-beam publication instead of depending on whichever page last wrote
    the compatibility ``authoritative_design_result`` slot.
    """

    result_store = EngineeringResultStore(state)  # type: ignore[arg-type]
    input_store = InputSnapshotStore(state)  # type: ignore[arg-type]
    beam_id = str(state.get("active_beam_id") or "").strip()

    if beam_id:
        results_by_beam = state.get(_RESULTS_BY_BEAM_KEY)
        revisions_by_beam = state.get(_RESULT_REVISIONS_BY_BEAM_KEY)
        if isinstance(results_by_beam, Mapping):
            result = coerce_authoritative_design_result(
                results_by_beam.get(beam_id)
            )
            if result is not None:
                raw_revision = (
                    revisions_by_beam.get(beam_id)
                    if isinstance(revisions_by_beam, Mapping)
                    else None
                )
                source_revision = (
                    int(raw_revision) if raw_revision is not None else None
                )
                return (
                    result,
                    input_store.current_for_beam(beam_id),
                    source_revision,
                )

    return result_store.current(), input_store.current(), result_store.source_input_revision()


def current_authoritative_check_pack(
    state: Mapping[str, Any],
    family: str,
) -> dict[str, Any] | None:
    """Return a defensive copy of one revision-matched V2 summary pack."""

    # Stores require only mapping operations; a plain test dictionary remains
    # a valid adapter.  Mapping implementations that are not mutable simply
    # cannot contain the session-owned result keys and will return ``None``.
    try:
        result, input_state, source_revision = _current_result_and_input_state(state)
    except (AttributeError, TypeError):
        return None
    if result is None:
        return None

    if source_revision is not None and source_revision != input_state.revision:
        return None

    calculations = dict(result.current_calculations or {})
    packs = calculations.get("packs")
    if not isinstance(packs, Mapping):
        return None
    pack = packs.get(str(family))
    if not isinstance(pack, Mapping) or pack.get("source") != "inputs_v2":
        return None
    projected = copy.deepcopy(dict(pack))
    # Detailed Bending cards consume the exact same calculation family as the
    # summary pack.  Attach the already-published facts here rather than
    # letting the result page invoke a second bending solver.
    if str(family) == "bending":
        families = calculations.get("families")
        if isinstance(families, Mapping):
            bending = families.get("bending")
            ductility = families.get("ductility")
            if isinstance(bending, Mapping):
                projected["authoritative_family"] = copy.deepcopy(dict(bending))
            if isinstance(ductility, Mapping):
                projected["authoritative_ductility_family"] = copy.deepcopy(
                    dict(ductility)
                )
    return projected


def unavailable_authoritative_check_pack(family: str) -> dict[str, Any]:
    """Return a visible safe state without invoking another calculator."""

    family_name = str(family or "engineering").strip().lower()
    titles = {
        "bending": "Bending result unavailable",
        "shear": "Shear result unavailable",
        "crack": "Crack-control result unavailable",
        "deflection": "Deflection result unavailable",
    }
    row = {
        "uid": f"authoritative_{family_name}_unavailable",
        "title": titles.get(family_name, "Engineering result unavailable"),
        "row_type": "authoritative_unavailable",
        "action": "Awaiting current calculation",
        "capacity": "—",
        "calculated": "—",
        "requirement": "Awaiting current calculation",
        "value": "Awaiting current calculation",
        "limit": "—",
        "util": "—",
        "status": "INFO",
        "ok": None,
        "is_informational": True,
        "is_primary": True,
        "route_page": family_name,
        "tab": family_name,
    }
    return {
        "source": "inputs_v2_unavailable",
        "availability": "unavailable",
        "rows": [row],
    }


def authoritative_check_pack_or_unavailable(
    state: Mapping[str, Any], family: str
) -> dict[str, Any]:
    """One-way read boundary used by every general result page."""

    return current_authoritative_check_pack(
        state, family
    ) or unavailable_authoritative_check_pack(family)


def current_authoritative_family(
    state: Mapping[str, Any],
    family: str,
) -> dict[str, Any] | None:
    """Return one revision-matched calculation family without recalculating."""

    try:
        result, input_state, source_revision = _current_result_and_input_state(state)
    except (AttributeError, TypeError):
        return None
    if result is None:
        return None
    if source_revision is not None and source_revision != input_state.revision:
        return None
    calculations = dict(result.current_calculations or {})
    if calculations.get("source") != "inputs_v2":
        return None
    families = calculations.get("families")
    if not isinstance(families, Mapping):
        return None
    values = families.get(str(family))
    return copy.deepcopy(dict(values)) if isinstance(values, Mapping) else None


__all__ = [
    "authoritative_check_pack_or_unavailable",
    "current_authoritative_check_pack",
    "current_authoritative_family",
    "unavailable_authoritative_check_pack",
]
