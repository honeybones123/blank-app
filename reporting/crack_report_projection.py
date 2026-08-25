"""Pure presentation/publication projections for selectable crack methods."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from application.contracts.concrete_crack_shrinkage import (
    AS5100WallCrackControlResult,
    C766CrackControlResult,
    C766EndRestraintResult,
)


@dataclass(frozen=True, slots=True)
class CrackReportProjection:
    result_values: Mapping[str, Any]

    def result_update(self) -> dict[str, Any]:
        return dict(self.result_values)


def _projection(values: Mapping[str, Any]) -> CrackReportProjection:
    return CrackReportProjection(MappingProxyType(dict(values)))


def project_as5100_wall_result(
    result: AS5100WallCrackControlResult,
) -> CrackReportProjection:
    return _projection(
        {
            "method": result.method.value,
            "reference": (
                f"{result.reference.document} {result.reference.edition}, "
                f"Clause {result.reference.clause}"
            ),
            "required_area_per_face_mm2_per_m": (
                result.required_area_per_face_mm2_per_m
            ),
            "maximum_spacing_mm": result.maximum_spacing_mm,
            "area_utilisation": result.area_utilisation,
            "passes": result.passes,
            "warnings": list(result.warnings),
        }
    )


def project_c766_end_result(
    result: C766EndRestraintResult,
    *,
    restraint_type: str,
) -> CrackReportProjection:
    return _projection(
        {
            "method": result.method.value,
            "restraint_type": str(restraint_type),
            "reference": (
                f"{result.reference.document}, Equation 3.12 and "
                "Equations 3.21-3.23"
            ),
            "crack_inducing_strain": result.crack_inducing_strain,
            "maximum_crack_spacing_mm": result.maximum_crack_spacing_mm,
            "characteristic_crack_width_mm": (
                result.characteristic_crack_width_mm
            ),
            "warnings": list(result.warnings),
        }
    )


def project_c766_result(
    result: C766CrackControlResult,
    *,
    restraint_type: str,
    shrinkage_components: Mapping[str, Any],
) -> CrackReportProjection:
    return _projection(
        {
            "method": result.method.value,
            "restraint_type": str(restraint_type),
            "reference": (
                f"{result.reference.document}, {result.reference.clause}"
            ),
            "restrained_strain": result.restrained_strain,
            "crack_initiates": result.crack_initiates,
            "crack_inducing_strain": result.crack_inducing_strain,
            "maximum_crack_spacing_mm": result.maximum_crack_spacing_mm,
            "characteristic_crack_width_mm": (
                result.characteristic_crack_width_mm
            ),
            "shrinkage_source_method": shrinkage_components["method"],
            "autogenous_shrinkage_early": float(
                shrinkage_components["autogenous_early"]
            ),
            "autogenous_shrinkage_long_term": float(
                shrinkage_components["autogenous_long_term"]
            ),
            "drying_shrinkage": float(shrinkage_components["drying_long_term"]),
            "c766_relaxation_factor_early": 0.65,
            "c766_relaxation_factor_long_term": 0.50,
            "warnings": list(result.warnings),
        }
    )


def project_as3600_results(values: Mapping[str, Any]) -> CrackReportProjection:
    keys = (
        "sigma_allow_table",
        "sigma_sr",
        "w_calc",
        "wmax_char",
        "passes_table",
        "passes_w",
        "crack_width",
        "crack_sr_max_mm",
        "crack_utilisation",
    )
    return _projection({key: values[key] for key in keys})


__all__ = [
    "CrackReportProjection",
    "project_as3600_results",
    "project_as5100_wall_result",
    "project_c766_end_result",
    "project_c766_result",
]
