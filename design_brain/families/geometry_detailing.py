"""Geometry/detailing governing-family runtime."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from design_brain.families.base import DiagnosticFamilyStrategy, FamilyStrategyMetadata
from design_brain.families.bending_fail_governs.geometry_ratio import (
    bending_depth_width_ratio_limit,
    depth_width_ratio,
)
from design_brain.shared.schemas import FamilyResult


FAMILY_ID = "GEOMETRY_DETAILING_GOVERNS"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _geometry_width_context(state: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT").upper()
    if sec_shape == "T":
        return "bw", "Web width bw", _float(state.get("bw", state.get("inputs_bw", state.get("b", state.get("inputs_b", 300.0)))), 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw", _float(state.get("tw", state.get("inputs_tw", state.get("b", state.get("inputs_b", 200.0)))), 200.0)
    return "b", "Width b", _float(state.get("b", state.get("inputs_b", 300.0)), 300.0)


@dataclass(frozen=True)
class GeometryDetailingRecommendation:
    candidate_id: str
    lane_id: str
    title: str
    reason: str
    updates: dict[str, Any]
    depth_width_ratio_before: float | None
    depth_width_ratio_after: float | None
    maximum_depth_width_ratio: float
    depth: float
    width_before: float
    width_after: float
    width_key: str
    width_label: str
    update_hash: str
    candidate_state_hash: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeometryDetailingGovernsResult:
    family_id: str
    status: str
    selected_strategy_lane: str | None
    selected_recommendation: dict[str, Any] | None
    candidate_repairs: tuple[dict[str, Any], ...] = ()
    repair_reason_proof: dict[str, Any] = field(default_factory=dict)
    blocked_reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    cta_intent_proof: dict[str, Any] = field(default_factory=dict)
    runtime_hash: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "status": self.status,
            "selected_strategy_lane": self.selected_strategy_lane,
            "selected_recommendation": self.selected_recommendation,
            "candidate_repairs": tuple(self.candidate_repairs),
            "repair_reason_proof": dict(self.repair_reason_proof),
            "blocked_reason": self.blocked_reason,
            "evidence": dict(self.evidence),
            "cta_intent_proof": dict(self.cta_intent_proof),
            "runtime_hash": self.runtime_hash,
        }


def run_geometry_detailing_governs_runtime(
    base_state: dict[str, Any] | None,
    *,
    constraints: dict[str, Any] | None = None,
) -> GeometryDetailingGovernsResult:
    """Return a family-owned correction for invalid geometry/detailing input.

    First locked scope: D/b ratio breaches. The family proposes width growth only;
    it never reduces depth/width and does not render, publish, or route apply.
    """

    state = dict(base_state or {})
    constraint_d = dict(constraints or {})
    width_key, width_label, width = _geometry_width_context(state)
    depth = _float(state.get("D", state.get("inputs_D")), 0.0)
    limit = float(bending_depth_width_ratio_limit())
    ratio_before = depth_width_ratio(width=width, depth=depth)
    base_surface = {
        "family_id": FAMILY_ID,
        "width_key": width_key,
        "width": width,
        "depth": depth,
        "depth_width_ratio": ratio_before,
        "maximum_depth_width_ratio": limit,
    }
    if ratio_before is None or ratio_before <= limit + 1e-9:
        evidence = {
            **base_surface,
            "applicable": False,
            "reason": "geometry_detailing_contract_satisfied",
        }
        return GeometryDetailingGovernsResult(
            family_id=FAMILY_ID,
            status="NOT_APPLICABLE",
            selected_strategy_lane=None,
            selected_recommendation=None,
            evidence=evidence,
            runtime_hash=_stable_hash(evidence),
        )

    if bool(constraint_d.get("geometry_locked") or constraint_d.get("width_locked")):
        evidence = {
            **base_surface,
            "applicable": True,
            "repair_available": False,
            "blocked_reason": "width_growth_locked",
        }
        return GeometryDetailingGovernsResult(
            family_id=FAMILY_ID,
            status="BLOCKED",
            selected_strategy_lane="WIDTH_RESCUE_FOR_DEPTH_WIDTH_RATIO",
            selected_recommendation=None,
            blocked_reason="width_growth_locked",
            evidence=evidence,
            repair_reason_proof={
                "source": "geometry_detailing_depth_width_ratio",
                "reason": "depth_width_ratio_above_contract_limit",
                "depth_width_ratio": ratio_before,
                "maximum_depth_width_ratio": limit,
            },
            runtime_hash=_stable_hash(evidence),
        )

    required_width = float(int(math.ceil(max(width, depth / limit) / 10.0) * 10))
    updates: dict[str, Any] = {width_key: required_width}
    if width_key != "b" and "b" in state:
        updates["b"] = required_width
    candidate_state = dict(state)
    candidate_state.update(updates)
    ratio_after = depth_width_ratio(width=required_width, depth=depth)
    update_hash = _stable_hash(updates)
    candidate_state_hash = _stable_hash(
        {
            "D": depth,
            width_key: required_width,
            "sec_shape": state.get("sec_shape", "RECT"),
        }
    )
    recommendation = GeometryDetailingRecommendation(
        candidate_id=f"geometry_detailing_width_rescue:{update_hash}",
        lane_id="WIDTH_RESCUE_FOR_DEPTH_WIDTH_RATIO",
        title="Geometry needs correction",
        reason="Increase width so the section satisfies the depth-to-width ratio contract.",
        updates=updates,
        depth_width_ratio_before=ratio_before,
        depth_width_ratio_after=ratio_after,
        maximum_depth_width_ratio=limit,
        depth=depth,
        width_before=width,
        width_after=required_width,
        width_key=width_key,
        width_label=width_label,
        update_hash=update_hash,
        candidate_state_hash=candidate_state_hash,
    ).as_dict()
    evidence = {
        **base_surface,
        "applicable": True,
        "repair_available": True,
        "selected_candidate_id": recommendation["candidate_id"],
        "selected_update_hash": update_hash,
        "candidate_state_hash": candidate_state_hash,
        "width_after": required_width,
        "depth_width_ratio_after": ratio_after,
    }
    cta_intent = {
        "proof_only": True,
        "action_type": "apply_resolved_candidate",
        "family": "geometry_detailing",
        "selected_family_id": FAMILY_ID,
        "update_hash": update_hash,
        "candidate_state_hash": candidate_state_hash,
    }
    return GeometryDetailingGovernsResult(
        family_id=FAMILY_ID,
        status="ACTION",
        selected_strategy_lane="WIDTH_RESCUE_FOR_DEPTH_WIDTH_RATIO",
        selected_recommendation=recommendation,
        candidate_repairs=(recommendation,),
        repair_reason_proof={
            "source": "geometry_detailing_depth_width_ratio",
            "reason": "depth_width_ratio_above_contract_limit",
            "depth_width_ratio": ratio_before,
            "maximum_depth_width_ratio": limit,
            "repair_update_hash": update_hash,
        },
        evidence=evidence,
        cta_intent_proof=cta_intent,
        runtime_hash=_stable_hash(
            {
                "evidence": evidence,
                "selected_recommendation": recommendation,
                "cta_intent_proof": cta_intent,
            }
        ),
    )


def evaluate_geometry_detailing_governs(context: dict[str, Any]) -> FamilyResult:
    base_state = dict(context.get("base_state") or context.get("state") or context.get("payload") or {})
    constraints = dict(context.get("constraints") or {})
    result = run_geometry_detailing_governs_runtime(base_state, constraints=constraints)
    selected = dict(result.selected_recommendation or {})
    return FamilyResult(
        family_id=FAMILY_ID,
        is_applicable=result.status in {"ACTION", "BLOCKED"},
        status=result.status,
        selected_candidate=selected or None,
        updates=dict(selected.get("updates") or {}),
        blockers=(
            [{"reason": result.blocked_reason, "source": FAMILY_ID}]
            if result.blocked_reason
            else []
        ),
        evidence={
            "runtime": result.as_dict(),
            "repair_reason_proof": dict(result.repair_reason_proof),
            "candidate_repairs": tuple(result.candidate_repairs),
        },
        cta_contract=dict(result.cta_intent_proof),
        lock_proof={
            "runtime_authority": "run_geometry_detailing_governs_runtime",
            "family_id": FAMILY_ID,
            "runtime_hash": result.runtime_hash,
            "product_rendering_owned_by_family": False,
            "apply_routing_owned_by_family": False,
        },
    )


class GeometryDetailingFamily(DiagnosticFamilyStrategy):
    metadata = FamilyStrategyMetadata(
        governing_state=FAMILY_ID,
        owner="design_brain.families.geometry_detailing.GeometryDetailingFamily",
        candidate_strategy="contract_owned_depth_width_ratio_width_rescue",
        ranking_strategy="single_width_rescue_candidate_for_ratio_breach",
        evidence_strategy="geometry_detailing_depth_width_ratio_repair_evidence",
        publication_rule="geometry_detailing_action_or_locked_blocker",
        cta_rule="executor_backed_apply_cta_for_geometry_width_rescue",
        affected_by_shared_helpers=("spacing_checks", "cover_checks", "capacity_checks", "candidate_schema"),
        regression_id="geometry_governs_stop_regression",
        migrated=True,
    )

    def generate_candidates(self, context) -> dict[str, Any]:
        state = dict(context.payload or {})
        if not state:
            state = dict(context.primary or {})
        result = run_geometry_detailing_governs_runtime(
            state,
            constraints=dict(context.evidence.get("constraints") or {}),
        )
        return result.as_dict()


__all__ = [
    "FAMILY_ID",
    "GeometryDetailingFamily",
    "GeometryDetailingGovernsResult",
    "GeometryDetailingRecommendation",
    "evaluate_geometry_detailing_governs",
    "run_geometry_detailing_governs_runtime",
]
