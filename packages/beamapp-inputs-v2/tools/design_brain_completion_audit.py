"""Run concise, deterministic Design Brain family completion fixtures.

This audit is deliberately independent of Streamlit.  It exercises the one
classifier/orchestrator boundary, the family-owned ladders and the shared
candidate gateway, then emits only compact evidence suitable for CI logs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inputs_v2.application.candidate_evaluation import complete_compliance
from inputs_v2.application.design_brain_families import DesignFamily
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    LongitudinalReinforcement,
    ServiceabilityInputs,
    ShearReinforcement,
)


@dataclass(frozen=True, slots=True)
class AuditCase:
    case_id: str
    inputs: BeamInputs
    expected_family: DesignFamily
    expected_status: str
    expected_blocker_code: str | None = None


def _base(*, links: bool = True) -> BeamInputs:
    return BeamInputs(
        width_mm=300.0,
        depth_mm=500.0,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=24),
        shear=(
            ShearReinforcement(diameter_mm=12, legs=2, spacing_mm=200.0)
            if links
            else ShearReinforcement()
        ),
    ).validated()


def _with_utilisations(
    base: BeamInputs,
    *,
    bending: float = 0.0,
    shear: float = 0.0,
) -> BeamInputs:
    result = DesignBrainService()._calculator.calculate_current(base).result
    if result is None:
        raise RuntimeError("baseline calculation unavailable")
    bending_capacity = float(result.families["bending"]["phi_Mu_kNm"])
    shear_capacity = float(result.families["shear"]["phi_Vu"])
    return replace(
        base,
        actions=ActionInputs(
            bending_moment_knm=bending * bending_capacity,
            shear_force_kn=shear * shear_capacity,
        ),
    ).validated()


def cases() -> tuple[AuditCase, ...]:
    linked = _base(links=True)
    unlinked = _base(links=False)
    serviceability = replace(
        _with_utilisations(unlinked, bending=0.70),
        serviceability=ServiceabilityInputs(
            moment_knm=500.0,
            permanent_udl_knm_per_m=1.0,
            equivalent_udl_knm_per_m=1.0,
        ),
    ).validated()
    detailed_shear_failure = replace(
        _with_utilisations(linked, bending=0.90, shear=0.40),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=600.0),
    ).validated()
    exact_shear_stop = replace(
        _with_utilisations(linked, bending=0.90, shear=0.40),
        width_locked=True,
        depth_locked=True,
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=300.0),
    ).validated()
    exact_combined_stop = replace(
        _with_utilisations(linked, bending=0.40, shear=0.40),
        width_locked=True,
        depth_locked=True,
        bottom=LongitudinalReinforcement(bars=4, diameter_mm=16),
        shear=ShearReinforcement(diameter_mm=10, legs=2, spacing_mm=300.0),
    ).validated()
    return (
        AuditCase(
            "no_design_actions",
            BeamInputs().validated(),
            DesignFamily.INPUT_REQUIRED,
            "INPUT_REQUIRED",
        ),
        AuditCase(
            "geometry_detailing",
            BeamInputs(
                width_mm=200.0,
                depth_mm=450.0,
                actions=ActionInputs(bending_moment_knm=10.0),
            ).validated(),
            DesignFamily.GEOMETRY_DETAILING_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "combined_failure",
            _with_utilisations(linked, bending=1.20, shear=1.20),
            DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN,
            "ACTION",
        ),
        AuditCase(
            "bending_failure_shear_cleanup",
            _with_utilisations(linked, bending=1.20, shear=0.40),
            DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "shear_failure_bending_optimise",
            _with_utilisations(linked, bending=0.40, shear=1.20),
            DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "bending_failure",
            _with_utilisations(unlinked, bending=1.20),
            DesignFamily.BENDING_FAIL_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "shear_failure",
            _with_utilisations(linked, bending=0.90, shear=1.20),
            DesignFamily.SHEAR_FAIL_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "serviceability_failure",
            serviceability,
            DesignFamily.SERVICEABILITY_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "combined_overdesign",
            _with_utilisations(linked, bending=0.40, shear=0.40),
            DesignFamily.COMBINED_OVERDESIGN,
            "ACTION",
        ),
        AuditCase(
            "bending_overdesign",
            _with_utilisations(unlinked, bending=0.40),
            DesignFamily.BENDING_OVERDESIGN_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "shear_overdesign",
            _with_utilisations(linked, bending=0.90, shear=0.40),
            DesignFamily.SHEAR_OVERDESIGN_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "zero_shear_cleanup",
            _with_utilisations(linked, bending=0.90, shear=0.0),
            DesignFamily.SHEAR_OVERDESIGN_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "detailed_minimum_shear_failure_below_capacity",
            detailed_shear_failure,
            DesignFamily.SHEAR_FAIL_GOVERNS,
            "ACTION",
        ),
        AuditCase(
            "exhausted_shear_overdesign",
            exact_shear_stop,
            DesignFamily.EXACT_STOP_PROVEN,
            "PASS",
        ),
        AuditCase(
            "exhausted_combined_overdesign",
            exact_combined_stop,
            DesignFamily.EXACT_STOP_PROVEN,
            "PASS",
        ),
        AuditCase(
            "target_band",
            _with_utilisations(linked, bending=0.90, shear=0.90),
            DesignFamily.TARGET_BAND_REACHED,
            "PASS",
        ),
        AuditCase(
            "locked_unrepairable_bending_failure",
            replace(
                _with_utilisations(unlinked, bending=20.0),
                width_locked=True,
                depth_locked=True,
            ).validated(),
            DesignFamily.BENDING_FAIL_GOVERNS,
            "BLOCKED",
            "geometry_locked",
        ),
        AuditCase(
            "locked_geometry_failure",
            BeamInputs(
                width_mm=200.0,
                depth_mm=450.0,
                width_locked=True,
                depth_locked=True,
                actions=ActionInputs(bending_moment_knm=10.0),
            ).validated(),
            DesignFamily.GEOMETRY_DETAILING_GOVERNS,
            "BLOCKED",
            "geometry_locked",
        ),
        AuditCase(
            "locked_combined_failure",
            replace(
                _with_utilisations(linked, bending=20.0, shear=20.0),
                width_locked=True,
                depth_locked=True,
            ).validated(),
            DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN,
            "BLOCKED",
            "geometry_locked",
        ),
        AuditCase(
            "locked_bending_failure_shear_cleanup",
            replace(
                _with_utilisations(linked, bending=20.0, shear=0.40),
                width_locked=True,
                depth_locked=True,
            ).validated(),
            DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS,
            "BLOCKED",
            "geometry_locked",
        ),
        AuditCase(
            "locked_shear_failure_bending_optimise",
            replace(
                _with_utilisations(linked, bending=0.40, shear=20.0),
                width_locked=True,
                depth_locked=True,
            ).validated(),
            DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS,
            "BLOCKED",
            "geometry_locked",
        ),
        AuditCase(
            "locked_shear_failure",
            replace(
                _with_utilisations(linked, bending=0.90, shear=20.0),
                width_locked=True,
                depth_locked=True,
            ).validated(),
            DesignFamily.SHEAR_FAIL_GOVERNS,
            "BLOCKED",
            "geometry_locked",
        ),
        AuditCase(
            "locked_serviceability_failure",
            replace(
                serviceability,
                width_locked=True,
                depth_locked=True,
            ).validated(),
            DesignFamily.SERVICEABILITY_GOVERNS,
            "BLOCKED",
            "geometry_locked",
        ),
    )


def _audit_case(case: AuditCase) -> dict[str, object]:
    decision = DesignGuideOrchestrator().decide(case.inputs)
    evidence = decision.search_evidence
    issues: list[str] = []
    if decision.family is not case.expected_family:
        issues.append(
            f"family:{decision.family.value}!={case.expected_family.value}"
        )
    if decision.status.value != case.expected_status:
        issues.append(f"status:{decision.status.value}!={case.expected_status}")
    if decision.status.value == "ACTION":
        if not decision.apply_allowed or decision.candidate is None:
            issues.append("action_without_applyable_candidate")
        if not decision.changed_fields:
            issues.append("action_without_changes")
        if not complete_compliance(decision.proposed_result):
            issues.append("action_without_complete_compliance")
        proposal = decision.candidate.proposal if decision.candidate is not None else None
        if proposal is not None and decision.family in {
            DesignFamily.BENDING_OVERDESIGN_GOVERNS,
            DesignFamily.SHEAR_OVERDESIGN_GOVERNS,
            DesignFamily.COMBINED_OVERDESIGN,
        }:
            current_bottom = case.inputs.bottom.bars * case.inputs.bottom.diameter_mm**2
            proposed_bottom = proposal.bottom_bars * proposal.bottom_diameter_mm**2
            current_links = (
                case.inputs.shear.legs
                * case.inputs.shear.diameter_mm**2
                / max(case.inputs.shear.spacing_mm, 1.0)
            )
            proposed_links = (
                proposal.shear_legs
                * proposal.shear_diameter_mm**2
                / max(proposal.shear_spacing_mm, 1.0)
            )
            current_concrete = case.inputs.width_mm * case.inputs.depth_mm
            proposed_concrete = proposal.width_mm * proposal.depth_mm
            reductions = {
                "bottom": proposed_bottom < current_bottom - 1e-9,
                "shear": proposed_links < current_links - 1e-9,
                "geometry": proposed_concrete < current_concrete - 1e-9,
            }
            required_domains = {
                DesignFamily.BENDING_OVERDESIGN_GOVERNS: ("bottom", "geometry"),
                DesignFamily.SHEAR_OVERDESIGN_GOVERNS: ("shear", "geometry"),
                DesignFamily.COMBINED_OVERDESIGN: ("bottom", "shear", "geometry"),
            }[decision.family]
            if not any(reductions[domain] for domain in required_domains):
                issues.append("overdesign_action_without_material_reduction")
    else:
        if decision.apply_allowed:
            issues.append("non_action_allows_apply")
    current_compliant = complete_compliance(decision.current_result)
    if not current_compliant and decision.status.value == "PASS":
        issues.append("current_failure_published_as_pass")
    if decision.status.value == "PASS":
        if decision.candidate is not None:
            issues.append("pass_retains_candidate")
        if decision.changed_fields:
            issues.append("pass_retains_changes")
    if decision.status.value == "BLOCKED":
        if not evidence.governing_blocker:
            issues.append("blocked_without_governing_blocker")
        if evidence.exhausted:
            if evidence.completed_stage_ids != evidence.declared_stage_ids:
                issues.append("exact_stop_without_all_completed_stages")
            if any(not stage.stop_reason for stage in evidence.stages):
                issues.append("exact_stop_without_stage_stop_reason")
            if current_compliant and not evidence.budget_exhausted:
                issues.append("exhausted_compliant_optimisation_not_terminal_pass")
        actual_blocker_code = (
            decision.advice.blocker.blocker_code
            if decision.advice.blocker is not None
            else None
        )
        if (
            case.expected_blocker_code is not None
            and actual_blocker_code != case.expected_blocker_code
        ):
            issues.append(
                f"blocker:{actual_blocker_code}!={case.expected_blocker_code}"
            )
    if decision.reason.endswith("_not_failed"):
        issues.append("selected_failure_family_rejected_its_own_entry")
    record_count = len(evidence.candidate_records)
    stage_attempts = sum(count for _, count in evidence.stage_attempt_counts)
    if record_count != stage_attempts:
        issues.append(f"candidate_record_mismatch:{record_count}!={stage_attempts}")
    if not DesignBrainService._has_sls(case.inputs):
        for family_name in ("serviceability", "crack_control"):
            status = str(
                decision.proposed_result.families.get(family_name, {}).get("status", "")
            ).upper()
            if status not in {"NOT RUN", "INFO"}:
                issues.append(f"private_proxy_leaked:{family_name}:{status}")

    return {
        "case": case.case_id,
        "family": decision.family.value,
        "status": decision.status.value,
        "apply": decision.apply_allowed,
        "attempted": evidence.candidates_attempted,
        "valid": evidence.candidates_valid,
        "records": record_count,
        "budget_exhausted": evidence.budget_exhausted,
        "reason": decision.reason,
        "issues": issues,
    }


def main() -> int:
    rows = [_audit_case(case) for case in cases()]
    payload = {
        "cases": rows,
        "passed": sum(not row["issues"] for row in rows),
        "failed": sum(bool(row["issues"]) for row in rows),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
