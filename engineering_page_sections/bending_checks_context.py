"""Typed presentation inputs for the Bending calculation checks.

The authoritative engineering values are calculated and published before this
module is called.  This module only selects the active moment-sign projection
and packages the exact values consumed by the existing ULS, SLS, and minimum
strength renderers.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from calculations.bending import compression_block_lever_arm_values
from engineering_page_sections.bending_page_context import BendingPageSnapshot


def _readonly_results(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class BendingUlsChecksInput:
    results: Mapping[str, Any]
    width_mm: float
    overall_depth_mm: float
    concrete_strength_mpa: float
    steel_yield_strength_mpa: float
    reinforcement_area_mm2: float
    effective_depth_mm: float
    demand_kNm: float
    moment_sign: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", _readonly_results(self.results))

    def mutable_results(self) -> dict[str, Any]:
        return dict(self.results)


@dataclass(frozen=True, slots=True)
class BendingSlsChecksInput:
    results: Mapping[str, Any]
    width_mm: float
    overall_depth_mm: float
    effective_depth_mm: float
    reinforcement_area_mm2: float
    concrete_modulus_mpa: float
    steel_modulus_mpa: float
    demand_kNm: float
    moment_sign: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", _readonly_results(self.results))

    def mutable_results(self) -> dict[str, Any]:
        return dict(self.results)


@dataclass(frozen=True, slots=True)
class BendingMinimumStrengthChecksInput:
    results: Mapping[str, Any]
    width_mm: float
    overall_depth_mm: float
    concrete_strength_mpa: float
    steel_yield_strength_mpa: float
    reinforcement_area_mm2: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", _readonly_results(self.results))

    def mutable_results(self) -> dict[str, Any]:
        return dict(self.results)


@dataclass(frozen=True, slots=True)
class BendingChecksSnapshot:
    """One revision-matched input for all three Bending check tabs."""

    uls: BendingUlsChecksInput
    sls: BendingSlsChecksInput
    minimum_strength: BendingMinimumStrengthChecksInput


def build_bending_checks_snapshot(
    *,
    page_snapshot: BendingPageSnapshot,
    base_results: Mapping[str, Any],
    width_mm: float,
    overall_depth_mm: float,
    concrete_strength_mpa: float,
    steel_yield_strength_mpa: float,
    concrete_modulus_mpa: float,
    steel_modulus_mpa: float,
    positive_effective_depth_mm: float,
) -> BendingChecksSnapshot:
    """Project the active published case without rerunning engineering."""

    moment_sign = page_snapshot.view.selected_detail_view
    showing_negative = page_snapshot.view.showing_negative
    active_results = dict(base_results)

    if showing_negative:
        case = page_snapshot.negative_case
        case_results = case.results
        neutral_axis_mm = float(case_results.get("dn_mm", 0.0) or 0.0)
        gamma = float(
            case_results.get("gamma", base_results.get("gamma", 0.0)) or 0.0
        )
        effective_depth_mm = float(
            case_results.get("d_mm", case.effective_depth_mm)
            or case.effective_depth_mm
        )
        lever_arm = compression_block_lever_arm_values(
            dn_mm=neutral_axis_mm,
            gamma=gamma,
            d_mm=effective_depth_mm,
        )
        active_results.update(
            {
                "phi_Mu_cap": float(
                    case_results.get("phi_Mu_kNm", 0.0) or 0.0
                ),
                "Mu_util": float(case_results.get("util", 0.0) or 0.0),
                "ku": float(case_results.get("ku", 0.0) or 0.0),
                "c": neutral_axis_mm,
                "a": lever_arm["a"],
                "z": lever_arm["z"],
                "d": effective_depth_mm,
            }
        )
    else:
        case = page_snapshot.positive_case
        case_results = case.results
        effective_depth_mm = float(positive_effective_depth_mm)
        active_results.update(case_results)
        active_results.update(
            {
                "phi_Mu_cap": float(
                    case_results.get(
                        "phi_Mu_kNm", base_results.get("phi_Mu_cap", 0.0)
                    )
                    or 0.0
                ),
                "Mu_util": float(
                    case_results.get("util", base_results.get("Mu_util", 0.0))
                    or 0.0
                ),
                "ku": float(
                    case_results.get("ku", base_results.get("ku", 0.0)) or 0.0
                ),
                "c": float(
                    case_results.get("dn_mm", base_results.get("c", 0.0))
                    or 0.0
                ),
                "d": float(
                    case_results.get("d_mm", positive_effective_depth_mm)
                    or positive_effective_depth_mm
                ),
            }
        )

    common = dict(
        results=active_results,
        width_mm=float(width_mm),
        overall_depth_mm=float(overall_depth_mm),
        concrete_strength_mpa=float(concrete_strength_mpa),
        steel_yield_strength_mpa=float(steel_yield_strength_mpa),
        reinforcement_area_mm2=float(case.reinforcement_area_mm2),
    )
    return BendingChecksSnapshot(
        uls=BendingUlsChecksInput(
            **common,
            effective_depth_mm=effective_depth_mm,
            demand_kNm=float(case.uls_demand_kNm),
            moment_sign=moment_sign,
        ),
        sls=BendingSlsChecksInput(
            results=active_results,
            width_mm=float(width_mm),
            overall_depth_mm=float(overall_depth_mm),
            effective_depth_mm=effective_depth_mm,
            reinforcement_area_mm2=float(case.reinforcement_area_mm2),
            concrete_modulus_mpa=float(concrete_modulus_mpa),
            steel_modulus_mpa=float(steel_modulus_mpa),
            demand_kNm=float(case.sls_demand_kNm),
            moment_sign=moment_sign,
        ),
        minimum_strength=BendingMinimumStrengthChecksInput(**common),
    )


__all__ = [
    "BendingChecksSnapshot",
    "BendingMinimumStrengthChecksInput",
    "BendingSlsChecksInput",
    "BendingUlsChecksInput",
    "build_bending_checks_snapshot",
]
