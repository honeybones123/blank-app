"""Typed, formatting-neutral projection of a Design Brain decision."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.application.design_brain_decision import DecisionStatus, FamilyDecision


@dataclass(frozen=True, slots=True)
class DesignBrainCardViewModel:
    state_class: str
    badge: str
    heading: str
    governing_utilisation: float
    show_apply: bool
    body: str | None = None


def build_design_brain_card_view_model(decision: FamilyDecision, current) -> DesignBrainCardViewModel:
    """Project authoritative state without making a new engineering decision."""
    current_failed = any(check.status == "fail" for check in decision.advice.current_checks)
    # Colour describes the current engineering state, not whether a proposal
    # happens to be available.  Apply visibility is an independent contract.
    if decision.status is DecisionStatus.INPUT_REQUIRED:
        state_class = "empty"
    elif current_failed:
        state_class = "fail"
    elif decision.status is DecisionStatus.PASS:
        state_class = "pass"
    elif decision.status in {DecisionStatus.ACTION, DecisionStatus.BLOCKED}:
        state_class = "optimise"
    else:
        state_class = {
            DecisionStatus.INPUT_REQUIRED: "warn",
            DecisionStatus.PROVISIONAL: "info",
        }[decision.status]
    active = tuple(
        check.utilisation
        for check in decision.advice.current_checks
        if check.utilisation is not None
        and (
            check.check_id == "bending_capacity" and abs(float(current.actions.bending_moment_knm)) > 1e-9
            or check.check_id == "shear_strength" and abs(float(current.actions.shear_force_kn)) > 1e-9
            or check.check_id == "short_term_deflection" and any(
                abs(float(value or 0.0)) > 1e-12
                for value in (
                    current.serviceability.moment_knm,
                    current.serviceability.shear_kn,
                    current.serviceability.permanent_udl_knm_per_m,
                    current.serviceability.imposed_udl_knm_per_m,
                    current.serviceability.equivalent_udl_knm_per_m,
                )
            )
        )
    )
    input_required = decision.status is DecisionStatus.INPUT_REQUIRED
    return DesignBrainCardViewModel(
        state_class=state_class,
        badge="NO LOADS" if input_required else decision.status.value,
        heading="Design Brain waiting for actions" if input_required else decision.display_heading,
        governing_utilisation=max(active, default=0.0),
        show_apply=decision.apply_allowed,
        body=(
            "No design actions entered. Add loads and the Design Brain will check and optimise your beam."
            if input_required
            else None
        ),
    )
