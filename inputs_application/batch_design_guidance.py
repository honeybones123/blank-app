"""Runtime adapter for authoritative V2 Batch Design guidance."""

from __future__ import annotations

from typing import Any

from application.design_brain_port import DesignBrainRequest
from application.engineering_snapshot import build_engineering_input_snapshot_from_resolved_state
from application.guidance_result_adapter import guidance_payload_from_authoritative_design_result
from inputs_application.design_brain_composition import (
    build_new_design_brain_service,
    calculate_v2_authoritative_result,
)

_V2_BATCH_DESIGN_BRAIN_SERVICE = None

def compute_design_guidance_items(
    state: dict,
    *,
    guidance_debug_verbose: bool | None = None,
    debug_enabled: bool = False,
    request_kind: str = "design_guide",
) -> dict:
    """Run the same V2 Design Brain used by the main Inputs card.

    Batch Design historically called the retired V1 guidance runner.  Under
    the V2-only composition that function returned an empty compatibility
    payload, so batch rows silently bypassed the authoritative Design Brain.
    Keep the batch adapter's dictionary shape, but derive every value from the
    neutral service result instead of reintroducing a second calculator.
    """

    del guidance_debug_verbose, debug_enabled
    if not isinstance(state, dict):
        raise TypeError("design guidance state must be a dictionary")
    snapshot = build_engineering_input_snapshot_from_resolved_state(state)
    revision = int(
        state.get("_inputs_workspace_revision")
        or state.get("input_revision")
        or state.get("_inputs_input_revision")
        or 1
    )
    current_design_only = str(request_kind or "").strip() == "current_design"
    if current_design_only:
        # Batch Design evaluates the member exactly as entered before asking
        # the Design Brain to optimise it.  This sibling V2 calculation path
        # publishes the same authoritative families/packs without running the
        # recommendation search.
        result = calculate_v2_authoritative_result(
            engineering_snapshot=snapshot,
            resolved_inputs=dict(state),
            input_revision=revision,
        )
    else:
        global _V2_BATCH_DESIGN_BRAIN_SERVICE
        if _V2_BATCH_DESIGN_BRAIN_SERVICE is None:
            _V2_BATCH_DESIGN_BRAIN_SERVICE = build_new_design_brain_service()
        execution = _V2_BATCH_DESIGN_BRAIN_SERVICE.run(
            DesignBrainRequest(
                engineering_snapshot=snapshot,
                resolved_inputs=dict(state),
                input_revision=revision,
            )
        )
        result = execution.result
    payload = guidance_payload_from_authoritative_design_result(result)
    calculations = dict(result.current_calculations or {})
    # A reviewed batch run is asking V2 to design the member, not merely to
    # report the capacity of its starting geometry.  When V2 has accepted a
    # proposal, it has already published verified post-proposal packs at the
    # adapter boundary.  Consume those exact packs; otherwise retain the
    # current-result packs so an exhausted/blocked candidate remains visible
    # as a failure instead of being represented as a passing redesign.
    candidate_evaluation = (
        dict(result.candidate_evaluation)
        if isinstance(result.candidate_evaluation, dict)
        else {}
    )
    template_assignment = request_kind == "template_assignment"
    candidate_accepted = not (template_assignment or current_design_only) and bool(
        isinstance(result.selected_candidate, dict)
        and candidate_evaluation.get("accepted")
    )
    packs_key = "proposed_packs" if candidate_accepted else "packs"
    packs = dict(calculations.get(packs_key) or calculations.get("packs") or {})

    def _number(value: Any) -> float | None:
        try:
            if value in (None, "", "�", "-"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    # This map crosses the neutral Batch Design boundary with the result that
    # V2 actually calculated. The table displays these stored values rather
    # than deriving a second set of utilisations from its own row projection.
    family_utilisations: dict[str, float | None] = {
        "bending": None,
        "shear": None,
        "crack": None,
        "deflection": None,
    }
    family_capacities: dict[str, float | None] = {
        "bending": None,
        "shear": None,
    }
    statuses: dict[str, str] = {}
    utilisations: list[float] = []
    for family, pack in packs.items():
        if not isinstance(pack, dict):
            continue
        rows = list(pack.get("rows") or [])
        status = str(pack.get("summary_status") or "").strip().upper()
        if not status and rows and isinstance(rows[0], dict):
            status = str(rows[0].get("status") or "").strip().upper()
        if status:
            statuses[str(family)] = status
        util = _number(pack.get("summary_util"))
        if util is None:
            util = _number(pack.get("summary_util_total"))
        if util is None and rows and isinstance(rows[0], dict):
            util = _number(rows[0].get("util"))
        if str(family) in family_utilisations:
            family_utilisations[str(family)] = util
        capacity_keys = {
            "bending": ("summary_phiMu_kNm",),
            "shear": ("summary_phiVu_kN", "summary_governing_capacity_kN"),
        }.get(str(family), ())
        for capacity_key in capacity_keys:
            capacity = _number(pack.get(capacity_key))
            if capacity is not None:
                family_capacities[str(family)] = capacity
                break
        if util is not None:
            utilisations.append(util)
    worst_util = max(utilisations, default=None)
    any_fail = any(status == "FAIL" for status in statuses.values())
    selected = dict(result.selected_candidate or {})
    overview = {
        "statuses": statuses,
        "any_fail": any_fail,
        "all_key_pass": not any_fail,
        "worst_util": worst_util,
        "family_utilisations": family_utilisations,
        "family_capacities": family_capacities,
    }
    payload["debug_trace"] = {
        "overview": overview,
        "source": "inputs_v2",
        "result_basis": "verified_v2_proposal" if candidate_accepted else "current_design",
        "request_kind": str(request_kind or "design_guide"),
        "input_revision": revision,
        "engineering_hash": result.engineering_hash,
    }
    payload["design_brain_result"] = {
        "selected_candidate_label": (
            selected.get("candidate_id")
            or selected.get("label")
            or result.governing_family
        ),
        "selected_section": selected.get("section"),
        "utilisation": worst_util,
        "result_basis": "verified_v2_proposal" if candidate_accepted else "current_design",
        # Batch Design owns the member records, so carry V2's exact
        # approved changes across this neutral adapter boundary.  The batch
        # publisher can then update the selected member without reproducing
        # V2 candidate generation or guessing reinforcement values.
        "selected_updates": (
            dict(result.selected_updates) if candidate_accepted else {}
        ),
        "selected_candidate": selected if candidate_accepted else {},
        "source": "inputs_v2",
    }
    return payload

__all__ = ["compute_design_guidance_items"]
