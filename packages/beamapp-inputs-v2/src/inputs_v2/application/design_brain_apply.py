"""Typed, revision-safe Design Brain proposal boundary for Inputs V2."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Generic, TypeVar

from inputs_v2.application.input_commands import UpdateFirstSlice, apply_input_command
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Candidate(Generic[T]):
    candidate_id: str
    source_revision: int
    source_hash: str
    proposal: T
    rationale: str
    row_counts: tuple[int, ...] = ()
    row_diameters_mm: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    applied: bool
    reason: str
    inputs: BeamInputs


def propose_neutral_candidate(current: BeamInputs) -> Candidate[UpdateFirstSlice]:
    """Return an unchanged canonical proposal for one family to modify explicitly."""
    proposal = UpdateFirstSlice(
        width_mm=current.width_mm,
        depth_mm=current.depth_mm,
        span_mm=current.span_mm,
        section_shape=current.section_shape,
        width_locked=current.width_locked,
        depth_locked=current.depth_locked,
        bottom_mode=current.bottom.mode,
        bottom_bars=current.bottom.bars,
        bottom_spacing_mm=current.bottom.spacing_mm,
        bottom_diameter_mm=current.bottom.diameter_mm,
        bottom_cover_mm=current.bottom.cover_mm,
        top_mode=current.top.mode,
        top_bars=current.top.bars,
        top_spacing_mm=current.top.spacing_mm,
        top_diameter_mm=current.top.diameter_mm,
        top_cover_mm=current.top.cover_mm,
        shear_diameter_mm=current.shear.diameter_mm,
        shear_legs=current.shear.legs,
        shear_spacing_mm=current.shear.spacing_mm,
        concrete_strength_mpa=current.materials.concrete_strength_mpa,
        reinforcement_strength_mpa=current.materials.reinforcement_strength_mpa,
        bending_moment_knm=current.actions.bending_moment_knm,
        torsion_knm=current.actions.torsion_knm,
        shear_force_kn=current.actions.shear_force_kn,
        axial_force_kn=current.actions.axial_force_kn,
        applied_prestress_kn=current.actions.applied_prestress_kn,
        left_support=current.supports.left_type,
        right_support=current.supports.right_type,
        shrinkage_time_days=current.time_dependent.shrinkage_time_days,
        creep_time_days=current.time_dependent.creep_time_days,
        age_at_loading_days=current.time_dependent.age_at_loading_days,
        duct_count=current.voids.ducts,
        duct_diameter_mm=current.voids.diameter_mm,
        deflection_support_condition=current.deflection.support_condition,
        deflection_limit_ratio=current.deflection.limit_ratio,
        sls_moment_knm=current.serviceability.moment_knm,
        sls_shear_kn=current.serviceability.shear_kn,
        sls_permanent_udl_knm_per_m=current.serviceability.permanent_udl_knm_per_m,
        sls_imposed_udl_knm_per_m=current.serviceability.imposed_udl_knm_per_m,
        sls_equivalent_udl_knm_per_m=current.serviceability.equivalent_udl_knm_per_m,
        sls_sustained_load_factor=current.serviceability.sustained_load_factor,
        crack_width_limit_mm=current.serviceability.crack_width_limit_mm,
        crack_member_type=current.serviceability.crack_member_type,
        crack_k1=current.serviceability.crack_k1,
        crack_k2=current.serviceability.crack_k2,
        crack_creep_coefficient=current.serviceability.creep_coefficient,
        crack_shrinkage_microstrain=current.serviceability.shrinkage_microstrain,
        sls_use_uls_fallback=current.serviceability.use_uls_fallback,
        shear_kv_method=current.shear.kv_method,
        exposed_faces=current.time_dependent.exposed_faces,
        creep_environment=current.time_dependent.creep_environment,
        shrinkage_environment=current.time_dependent.shrinkage_environment,
        sustained_stress_ratio=current.time_dependent.stress_ratio,
        sustained_concrete_stress_mpa=current.time_dependent.sustained_concrete_stress_mpa,
        concrete_modulus_mpa=current.time_dependent.concrete_modulus_mpa,
    )
    current_rows = (
        tuple(current.bottom_arrangement.rows)
        if current.bottom_arrangement is not None
        else ()
    )
    return Candidate(
        "neutral-candidate-seed",
        current.revision,
        current.content_hash,
        proposal,
        "Unchanged candidate seed; the selected family owns every mutation.",
        tuple(row.bar_count for row in current_rows),
        tuple(
            float(row.bar_diameter_mm or current.bottom.diameter_mm)
            for row in current_rows
        ),
    )


def apply_candidate(
    current: BeamInputs,
    candidate: Candidate[UpdateFirstSlice],
) -> ApplyOutcome:
    if candidate.source_revision != current.revision or candidate.source_hash != current.content_hash:
        return ApplyOutcome(False, "stale_candidate", current)
    proposal = candidate.proposal
    if proposal.width_locked != current.width_locked or proposal.depth_locked != current.depth_locked:
        return ApplyOutcome(False, "lock_state_mutation_forbidden", current)
    if current.width_locked and proposal.width_mm != current.width_mm:
        return ApplyOutcome(False, "width_locked", current)
    if current.depth_locked and proposal.depth_mm != current.depth_mm:
        return ApplyOutcome(False, "depth_locked", current)
    try:
        # The immutable arrangement is authoritative: its row counts must be
        # reflected in the canonical bottom-bar count before validation.
        if candidate.row_counts:
            proposal = replace(proposal, bottom_bars=sum(candidate.row_counts))
        updated = apply_input_command(current, proposal)
    except ValueError:
        return ApplyOutcome(False, "candidate_validation_failed", current)
    # ``apply_input_command`` intentionally rebuilds dependent engineering
    # state, including ``bottom_arrangement``.  Preserve the committed clear
    # row gap explicitly while testing a candidate; otherwise a two-row input
    # silently falls back to the 25 mm default and appears to gain effective
    # depth that the published Apply command cannot reproduce.
    committed_row_gap = (
        float(current.bottom_arrangement.clear_row_gap_mm)
        if current.bottom_arrangement is not None
        else None
    )
    fit = evaluate_arrangement(
        updated,
        (updated.bottom.bars,),
        min_row_gap_mm=committed_row_gap,
    )
    if candidate.row_counts:
        fit = evaluate_arrangement(
            updated,
            candidate.row_counts,
            row_diameters_mm=(candidate.row_diameters_mm or None),
            min_row_gap_mm=committed_row_gap,
        )
    if not fit.accepted:
        return ApplyOutcome(False, "reinforcement_fit_failed", current)
    if candidate.row_counts:
        updated = replace(updated, bottom_arrangement=fit.arrangement).validated()
    return ApplyOutcome(True, "applied", updated)
