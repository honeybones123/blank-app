"""V2-owned single-span serviceability deflection calculation."""

from __future__ import annotations

import math
from dataclasses import dataclass


_SUPPORT_COEFFICIENTS = {
    "Simply supported": 5.0 / 384.0,
    # The domain does not yet distinguish continuous end/interior spans.
    # Use the larger AS 3600 end-span coefficient for the generic choice.
    "Continuous": 2.4 / 384.0,
    "Pinned–Pinned": 5.0 / 384.0,
    "Continuous – end span": 2.4 / 384.0,
    "Continuous – interior span": 1.5 / 384.0,
    "Fixed-ended": 1.0 / 384.0,
    "Fixed–Pinned": 1.0 / 185.0,
    "Pinned–Fixed": 1.0 / 185.0,
    "Cantilever": 1.0 / 8.0,
}


@dataclass(frozen=True)
class DeflectionInput:
    span_m: float
    concrete_modulus_mpa: float
    concrete_strength_mpa: float
    effective_width_mm: float
    web_width_mm: float
    effective_depth_mm: float
    tension_steel_area_mm2: float
    compression_steel_area_mm2: float
    permanent_udl_kn_per_m: float
    imposed_udl_kn_per_m: float
    sustained_load_factor: float
    support_condition: str


@dataclass(frozen=True)
class DeflectionResult:
    effective_inertia_mm4: float
    short_term_mm: float
    sustained_short_term_mm: float
    long_term_addition_mm: float
    total_mm: float
    support_coefficient: float
    sustained_deflection_factor: float


def derive_equivalent_udl_from_actions(
    *, moment_knm: float | None, shear_kn: float | None, span_m: float,
    support_condition: str,
) -> float | None:
    """Derive the legacy conservative equivalent full-span UDL."""
    if not math.isfinite(span_m) or span_m <= 0.0 or span_m > 50.0:
        return None
    cantilever = support_condition.strip() == "Cantilever"
    moment_udl = (
        (2.0 if cantilever else 8.0) * abs(moment_knm) / span_m**2
        if moment_knm is not None and math.isfinite(moment_knm) else None
    )
    shear_udl = (
        (1.0 if cantilever else 2.0) * abs(shear_kn) / span_m
        if shear_kn is not None and math.isfinite(shear_kn) else None
    )
    if moment_udl is None:
        return shear_udl
    if shear_udl is None:
        return moment_udl
    implied_moment = abs(shear_kn) * span_m / (2.0 if cantilever else 4.0)
    ratio = abs(moment_knm) / implied_moment if implied_moment > 0.0 else None
    return (
        0.5 * (moment_udl + shear_udl)
        if ratio is not None and 0.85 <= ratio <= 1.15
        else max(moment_udl, shear_udl)
    )


def resolve_equivalent_loads(
    *, derived_udl: float | None, equivalent_udl: float | None,
    permanent_udl: float | None, imposed_udl: float | None,
) -> tuple[float, float]:
    """Preserve the established load-source precedence and g/q split."""
    if derived_udl is not None:
        used = derived_udl
    elif equivalent_udl is not None:
        used = equivalent_udl
    else:
        used = float(permanent_udl or 0.0) + float(imposed_udl or 0.0)
    explicit_total = float(permanent_udl or 0.0) + float(imposed_udl or 0.0)
    if used > 0.0:
        if permanent_udl is not None and imposed_udl is not None and explicit_total > 0.0:
            permanent_ratio = float(permanent_udl) / explicit_total
            return used * permanent_ratio, used * (1.0 - permanent_ratio)
        return used, 0.0
    return float(permanent_udl or 0.0), float(imposed_udl or 0.0)


def calculate_effective_inertia(
    *, concrete_strength_mpa: float, effective_width_mm: float,
    web_width_mm: float, effective_depth_mm: float, tension_steel_area_mm2: float,
) -> float:
    """AS 3600 simplified effective inertia with legacy numerical clamps."""
    fc = max(concrete_strength_mpa, 1.0)
    width = max(effective_width_mm, 1.0)
    web = max(web_width_mm, 1.0)
    depth = max(effective_depth_mm, 1.0)
    beta = width / web
    ratio = tension_steel_area_mm2 / (width * depth)
    ratio_limit = 0.001 * fc ** (1.0 / 3.0) / beta ** (2.0 / 3.0)
    if ratio >= ratio_limit:
        k1 = (5.0 - 0.04 * fc) * ratio + 0.002
        maximum = 0.1 * width * depth**3 / beta ** (2.0 / 3.0)
    else:
        k1 = 0.055 * fc ** (1.0 / 3.0) / beta ** (2.0 / 3.0) - 50.0 * ratio
        maximum = 0.06 * width * depth**3 / beta ** (2.0 / 3.0)
    return max(min(k1 * width * depth**3, maximum), 0.0)


def calculate_deflection(values: DeflectionInput) -> DeflectionResult:
    """Calculate short- and long-term deflection for a full-span UDL."""
    _validate(values)
    inertia = calculate_effective_inertia(
        concrete_strength_mpa=values.concrete_strength_mpa,
        effective_width_mm=values.effective_width_mm,
        web_width_mm=values.web_width_mm,
        effective_depth_mm=values.effective_depth_mm,
        tension_steel_area_mm2=values.tension_steel_area_mm2,
    )
    span_mm = values.span_m * 1000.0
    coefficient = _SUPPORT_COEFFICIENTS.get(
        values.support_condition, _SUPPORT_COEFFICIENTS["Simply supported"]
    )
    denominator = max(values.concrete_modulus_mpa, 1.0) * max(inertia, 1.0)
    total_load = values.permanent_udl_kn_per_m + values.imposed_udl_kn_per_m
    sustained_load = (
        values.permanent_udl_kn_per_m
        + values.sustained_load_factor * values.imposed_udl_kn_per_m
    )
    short = coefficient * total_load * span_mm**4 / denominator
    sustained_short = coefficient * sustained_load * span_mm**4 / denominator
    steel_ratio = (
        values.compression_steel_area_mm2 / values.tension_steel_area_mm2
        if values.tension_steel_area_mm2 > 0.0 else 0.0
    )
    sustained_factor = max(2.0 - 1.2 * steel_ratio, 0.8)
    long_addition = sustained_factor * sustained_short
    return DeflectionResult(
        effective_inertia_mm4=inertia,
        short_term_mm=short,
        sustained_short_term_mm=sustained_short,
        long_term_addition_mm=long_addition,
        total_mm=short + long_addition,
        support_coefficient=coefficient,
        sustained_deflection_factor=sustained_factor,
    )


def _validate(values: DeflectionInput) -> None:
    for name, value in vars(values).items():
        if name != "support_condition" and not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
    if values.span_m <= 0.0:
        raise ValueError("span_m must be greater than zero")


__all__ = [
    "DeflectionInput", "DeflectionResult", "calculate_deflection",
    "calculate_effective_inertia", "derive_equivalent_udl_from_actions",
    "resolve_equivalent_loads",
]
