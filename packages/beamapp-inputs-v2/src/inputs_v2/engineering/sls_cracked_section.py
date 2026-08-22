"""Authoritative elastic cracked-section analysis for SLS bending.

The solver owns the transformed-section calculation used by crack control and
the Bending teaching cards.  Coordinates supplied by callers are measured
from the physical top face; internally they are transformed to the current
compression face so sagging and hogging use the same equilibrium equation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Iterable

from inputs_v2.engineering.bending_capacity import _shape_segments


STEEL_MODULUS_MPA = 200_000.0


@dataclass(frozen=True, slots=True)
class CrackedSectionLayer:
    """One physical longitudinal reinforcement layer."""

    layer_id: str
    label: str
    area_mm2: float
    depth_from_top_mm: float


def classify_reinforcement_layer(
    depth_from_compression_mm: float,
    neutral_axis_mm: float,
    *,
    tolerance_mm: float = 1e-7,
) -> str:
    """Classify a layer from its current position relative to a trial NA."""

    distance = float(depth_from_compression_mm) - float(neutral_axis_mm)
    if distance > float(tolerance_mm):
        return "tension"
    if distance < -float(tolerance_mm):
        return "compression"
    return "neutral"


def _concrete_properties(
    segments: tuple[tuple[float, float, float], ...],
    neutral_axis_mm: float,
) -> tuple[float, float, float, float]:
    """Return area, centroid, first moment and inertia of compression concrete."""

    area = 0.0
    first_about_face = 0.0
    inertia_about_neutral_axis = 0.0
    for start, end, width in segments:
        used_end = min(float(end), max(0.0, float(neutral_axis_mm)))
        if used_end <= float(start):
            continue
        height = used_end - float(start)
        strip_area = float(width) * height
        centroid = (float(start) + used_end) / 2.0
        area += strip_area
        first_about_face += strip_area * centroid
        inertia_about_neutral_axis += (
            float(width) * height**3 / 12.0
            + strip_area * (float(neutral_axis_mm) - centroid) ** 2
        )
    centroid = first_about_face / area if area > 0.0 else 0.0
    first_moment = area * (float(neutral_axis_mm) - centroid)
    return area, centroid, first_moment, inertia_about_neutral_axis


def solve_sls_cracked_section(
    *,
    width_mm: float,
    depth_mm: float,
    concrete_modulus_mpa: float,
    steel_modulus_mpa: float = STEEL_MODULUS_MPA,
    service_moment_knm: float = 0.0,
    layers: Iterable[CrackedSectionLayer],
    section_shape: str = "RECT",
    flange_width_mm: float | None = None,
    flange_thickness_mm: float | None = None,
    web_width_mm: float | None = None,
    moment_sign: str = "positive",
    ignore_compression_reinforcement: bool = False,
    classification_tolerance_mm: float = 1e-7,
) -> dict[str, object]:
    """Solve the cracked transformed section and publish reusable evidence.

    Gross concrete is retained in the compression region.  Consequently,
    reinforcement on the compression side contributes ``(n - 1) A_s``;
    tension-side reinforcement contributes ``n A_s``.
    """

    b = float(width_mm)
    depth = float(depth_mm)
    ec = float(concrete_modulus_mpa)
    es = float(steel_modulus_mpa)
    if min(b, depth, ec, es) <= 0.0:
        raise ValueError("SLS cracked-section geometry and elastic moduli must be positive")

    shape = str(section_shape or "RECT").upper()
    sign = str(moment_sign or "positive").strip().lower()
    if sign not in {"positive", "negative"}:
        sign = "positive"
    compression_face = "bottom" if sign == "negative" else "top"
    bf = float(flange_width_mm or b)
    tf = float(flange_thickness_mm or 0.0)
    bw = float(web_width_mm or b)
    if shape not in {"RECT", "T", "I"}:
        raise ValueError(f"Unsupported cracked-section shape: {shape}")
    if shape != "RECT" and not (bf >= bw > 0.0 and 0.0 < tf < depth):
        raise ValueError("Flanged cracked-section geometry is invalid")
    if shape == "I" and not 2.0 * tf < depth:
        raise ValueError("I-section flange thicknesses must not overlap")

    physical_layers = tuple(
        layer
        for layer in layers
        if float(layer.area_mm2) > 0.0
        and math.isfinite(float(layer.area_mm2))
        and math.isfinite(float(layer.depth_from_top_mm))
    )
    if not physical_layers:
        raise ValueError("At least one active reinforcement layer is required")

    transformed_layers = tuple(
        (
            layer,
            depth - float(layer.depth_from_top_mm)
            if compression_face == "bottom"
            else float(layer.depth_from_top_mm),
        )
        for layer in physical_layers
    )
    transformed_layers = tuple(
        (layer, min(depth, max(0.0, x))) for layer, x in transformed_layers
    )
    segments = _shape_segments(
        shape=shape,
        depth_mm=depth,
        compression_face=compression_face,
        width_mm=b,
        flange_width_mm=bf,
        flange_thickness_mm=tf,
        web_width_mm=bw,
    )
    modular_ratio = es / ec
    compression_factor = modular_ratio - 1.0

    def residual(neutral_axis_mm: float) -> float:
        _area, _centroid, concrete_q, _inertia = _concrete_properties(
            segments, neutral_axis_mm
        )
        value = concrete_q
        for layer, x in transformed_layers:
            distance = float(x) - float(neutral_axis_mm)
            state = classify_reinforcement_layer(
                x,
                neutral_axis_mm,
                tolerance_mm=classification_tolerance_mm,
            )
            if state == "tension":
                value -= modular_ratio * float(layer.area_mm2) * distance
            elif state == "compression" and not ignore_compression_reinforcement:
                value += compression_factor * float(layer.area_mm2) * (-distance)
        return value

    low = max(1e-9, depth * 1e-12)
    high = depth
    low_residual = residual(low)
    high_residual = residual(high)
    if low_residual > 0.0 or high_residual < 0.0:
        raise ValueError("Cracked neutral-axis residual is not bracketed by the section depth")

    scale = max(
        abs(low_residual),
        abs(high_residual),
        b * depth**2,
        1.0,
    )
    solver_tolerance = max(1e-8, scale * 1e-12)
    iterations = 0
    for iterations in range(1, 121):
        mid = (low + high) / 2.0
        mid_residual = residual(mid)
        if abs(mid_residual) <= solver_tolerance:
            low = high = mid
            break
        if mid_residual > 0.0:
            high = mid
        else:
            low = mid
    neutral_axis = (low + high) / 2.0
    final_residual = residual(neutral_axis)
    concrete_area, concrete_centroid, concrete_q, concrete_inertia = (
        _concrete_properties(segments, neutral_axis)
    )

    moment_nmm = abs(float(service_moment_knm)) * 1_000_000.0
    layer_results: list[dict[str, object]] = []
    steel_inertia = 0.0
    for layer, x in transformed_layers:
        signed_distance = float(x) - neutral_axis
        state = classify_reinforcement_layer(
            x,
            neutral_axis,
            tolerance_mm=classification_tolerance_mm,
        )
        if state == "tension":
            factor = modular_ratio
            first_moment = factor * float(layer.area_mm2) * signed_distance
            residual_contribution = -first_moment
        elif state == "compression":
            factor = 0.0 if ignore_compression_reinforcement else compression_factor
            first_moment = factor * float(layer.area_mm2) * (-signed_distance)
            residual_contribution = first_moment
        else:
            state = "neutral"
            factor = 0.0
            first_moment = 0.0
            residual_contribution = 0.0
        inertia_contribution = factor * float(layer.area_mm2) * signed_distance**2
        steel_inertia += inertia_contribution
        layer_results.append(
            {
                **asdict(layer),
                "depth_from_compression_mm": float(x),
                "signed_distance_from_na_mm": signed_distance,
                "state": state,
                "included": not (state == "compression" and ignore_compression_reinforcement),
                "transformed_factor": factor,
                "transformed_area_mm2": factor * float(layer.area_mm2),
                "first_moment_mm3": first_moment,
                "residual_contribution_mm3": residual_contribution,
                "inertia_contribution_mm4": inertia_contribution,
            }
        )

    cracked_inertia = concrete_inertia + steel_inertia
    curvature = moment_nmm / (ec * cracked_inertia) if cracked_inertia > 0.0 else 0.0
    for result in layer_results:
        strain = curvature * float(result["signed_distance_from_na_mm"])
        result["strain"] = strain
        result["stress_mpa"] = es * strain

    neutral_axis_from_top = (
        depth - neutral_axis if compression_face == "bottom" else neutral_axis
    )
    concrete_extreme_strain = -curvature * neutral_axis
    return {
        "method": "elastic_cracked_transformed_section",
        "section_shape": shape,
        "moment_sign": sign,
        "compression_face": compression_face,
        "ignore_compression_reinforcement": bool(ignore_compression_reinforcement),
        "width_mm": b,
        "depth_mm": depth,
        "flange_width_mm": bf,
        "flange_thickness_mm": tf,
        "web_width_mm": bw,
        "concrete_modulus_mpa": ec,
        "steel_modulus_mpa": es,
        "modular_ratio": modular_ratio,
        "neutral_axis_depth_mm": neutral_axis,
        "neutral_axis_depth_from_top_mm": neutral_axis_from_top,
        "concrete_compression_area_mm2": concrete_area,
        "concrete_centroid_from_compression_mm": concrete_centroid,
        "concrete_first_moment_mm3": concrete_q,
        "concrete_inertia_mm4": concrete_inertia,
        "steel_inertia_mm4": steel_inertia,
        "cracked_inertia_mm4": cracked_inertia,
        "equilibrium_residual_mm3": final_residual,
        "solver_tolerance_mm3": solver_tolerance,
        "solver_iterations": iterations,
        "service_moment_knm": abs(float(service_moment_knm)),
        "curvature_per_mm": curvature,
        "concrete_extreme_strain": concrete_extreme_strain,
        "concrete_extreme_stress_mpa": ec * concrete_extreme_strain,
        "layers": tuple(layer_results),
    }


__all__ = [
    "CrackedSectionLayer",
    "STEEL_MODULUS_MPA",
    "classify_reinforcement_layer",
    "solve_sls_cracked_section",
]
