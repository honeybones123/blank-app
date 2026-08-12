"""AS 3600 strain-compatible bending-capacity calculation.

The neutral axis, steel stresses and strength-reduction factor are resolved
together.  Section-shape data is explicit so rectangular, T and symmetric I
sections do not silently share rectangular compression-block equilibrium.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


STEEL_MODULUS_MPA = 200_000.0
ULTIMATE_CONCRETE_STRAIN = 0.003


def resolve_bending_faces(moment_sign: str) -> tuple[str, str, bool]:
    sign = str(moment_sign or "positive").strip().lower()
    is_hogging = sign == "negative"
    return ("top", "bottom", True) if is_hogging else ("bottom", "top", False)


def stress_block_factors(fc_mpa: float) -> tuple[float, float]:
    """AS 3600:2018 Clause 8.1.3 rectangular stress-block factors."""
    fc = float(fc_mpa or 0.0)
    return max(0.67, 0.85 - 0.0015 * fc), max(0.67, 0.97 - 0.0025 * fc)


def bending_strength_reduction_factor(ku: float, maximum: float = 0.85) -> float:
    """AS 3600:2018 Table 2.2.2(b)(i), Class N, pure bending."""
    if not math.isfinite(ku) or ku <= 0.0:
        return 0.65
    return min(float(maximum), max(0.65, min(0.85, 1.24 - 13.0 * ku / 12.0)))


def _shape_segments(
    *, shape: str, depth_mm: float, compression_face: str,
    width_mm: float, flange_width_mm: float, flange_thickness_mm: float,
    web_width_mm: float,
) -> tuple[tuple[float, float, float], ...]:
    """Return non-overlapping (start, end, width) strips from compression face."""
    D = depth_mm
    section_shape = str(shape or "RECT").upper()
    if section_shape == "RECT":
        return ((0.0, D, width_mm),)

    bf = flange_width_mm
    tf = flange_thickness_mm
    bw = web_width_mm
    if section_shape == "T":
        if compression_face == "top":
            return ((0.0, tf, bf), (tf, D, bw))
        return ((0.0, D - tf, bw), (D - tf, D, bf))

    # I sections are symmetric about the horizontal centroid in the current
    # contract, so the same strip definition applies from either face.
    return ((0.0, tf, bf), (tf, D - tf, bw), (D - tf, D, bf))


def _area_and_centroid_to_depth(
    segments: tuple[tuple[float, float, float], ...], depth_mm: float,
) -> tuple[float, float]:
    area = 0.0
    first_moment = 0.0
    for start, end, width in segments:
        used_end = min(end, max(0.0, depth_mm))
        if used_end <= start:
            continue
        strip_area = width * (used_end - start)
        area += strip_area
        first_moment += strip_area * (start + used_end) / 2.0
    return area, (first_moment / area if area > 0.0 else 0.0)


def _steel_stress_mpa(depth_from_compression_mm: float, neutral_axis_mm: float, fsy: float) -> float:
    strain = ULTIMATE_CONCRETE_STRAIN * (
        neutral_axis_mm - depth_from_compression_mm
    ) / neutral_axis_mm
    return max(-fsy, min(fsy, STEEL_MODULUS_MPA * strain))


def _normalise_layers(
    *, D: float, bottom_layers: tuple[tuple[float, float], ...],
    top_layers: tuple[tuple[float, float], ...], bottom_area: float,
    top_area: float, bottom_depth: float, top_depth: float,
) -> tuple[tuple[float, float, str], ...]:
    layers: list[tuple[float, float, str]] = []
    if bottom_layers:
        layers.extend((float(area), float(y), "bottom") for area, y in bottom_layers)
    elif bottom_area > 0.0:
        layers.append((bottom_area, bottom_depth, "bottom"))
    if top_layers:
        layers.extend((float(area), float(y), "top") for area, y in top_layers)
    elif top_area > 0.0:
        layers.append((top_area, top_depth, "top"))
    return tuple((area, min(D, max(0.0, y)), face) for area, y, face in layers if area > 0.0)


def solve_bending_capacity(moment_sign: str, M_star_kNm: float, inputs: dict) -> dict:
    sign = str(moment_sign or "positive").strip().lower()
    if sign not in {"positive", "negative"}:
        sign = "positive"
    tension_face, compression_face, is_hogging = resolve_bending_faces(sign)

    b = float(inputs.get("b", 0.0) or 0.0)
    D = float(inputs.get("D", 0.0) or 0.0)
    fc = float(inputs.get("fc", 0.0) or 0.0)
    fsy = float(inputs.get("fsy", 0.0) or 0.0)
    phi_max = float(inputs.get("phi_bend", 0.85) or 0.85)
    shape = str(inputs.get("section_shape", "RECT") or "RECT").upper()
    bf = float(inputs.get("flange_width_mm", b) or b)
    tf = float(inputs.get("flange_thickness_mm", 0.0) or 0.0)
    bw = float(inputs.get("web_width_mm", b) or b)
    bottom_area = float(inputs.get("Ast_bot", 0.0) or 0.0)
    top_area = float(inputs.get("Ast_top", 0.0) or 0.0)
    bottom_depth = float(inputs.get("d", 0.0) or 0.0)
    top_depth = float(inputs.get("do", 0.0) or 0.0)
    bottom_layers = tuple(inputs.get("bottom_layers", ()) or ())
    top_layers = tuple(inputs.get("top_layers", ()) or ())
    alpha2, gamma = stress_block_factors(fc)

    shape_valid = (
        shape in {"RECT", "T", "I"}
        and min(b, D, fc, fsy, phi_max) > 0.0
        and (shape == "RECT" or (bf >= bw > 0.0 and 0.0 < tf < D))
        and (shape != "I" or 2.0 * tf < D)
    )
    layers_top = _normalise_layers(
        D=D, bottom_layers=bottom_layers, top_layers=top_layers,
        bottom_area=bottom_area, top_area=top_area,
        bottom_depth=bottom_depth, top_depth=top_depth,
    ) if D > 0.0 else ()
    transformed_layers = tuple(
        (area, D - y if is_hogging else y, face) for area, y, face in layers_top
    )
    tension_layers = tuple(
        (area, x) for area, x, face in transformed_layers if face == tension_face
    )
    Ast = sum(area for area, _x in tension_layers)
    d_mm = (
        sum(area * x for area, x in tension_layers) / Ast if Ast > 0.0 else 0.0
    )
    tension_steel_label = "Bottom reinforcement" if tension_face == "bottom" else "Top reinforcement"

    if not shape_valid or Ast <= 0.0 or d_mm <= 0.0:
        demand = max(0.0, float(M_star_kNm or 0.0))
        return {
            "moment_sign": sign, "M_star_kNm": demand, "phi_Mu_kNm": 0.0,
            "Mu_nom_kNm": 0.0, "util": 0.0 if demand <= 0.0 else float("inf"),
            "status": "—", "dn_mm": float("nan"), "ku": float("nan"),
            "phi": 0.65, "tension_face": tension_face,
            "compression_face": compression_face, "tension_steel_label": tension_steel_label,
            "alpha2": alpha2, "gamma": gamma, "d_mm": d_mm,
            "Ast_tension_mm2": Ast, "shape_equilibrium_valid": False,
            "compression_steel_area_mm2": 0.0, "compression_concrete_area_mm2": 0.0,
        }

    segments = _shape_segments(
        shape=shape, depth_mm=D, compression_face=compression_face,
        width_mm=b, flange_width_mm=bf, flange_thickness_mm=tf, web_width_mm=bw,
    )

    def equilibrium(dn: float) -> tuple[float, float, float, tuple[tuple[float, float, float], ...]]:
        block_depth = min(D, gamma * dn)
        concrete_area, concrete_centroid = _area_and_centroid_to_depth(segments, block_depth)
        concrete_force = alpha2 * fc * concrete_area
        steel_values: list[tuple[float, float, float]] = []
        force_sum = concrete_force
        for area, x, _face in transformed_layers:
            stress = _steel_stress_mpa(x, dn, fsy)
            # The equivalent rectangular block is gross concrete area. Remove
            # displaced block stress where a steel layer lies inside it.
            net_stress = stress - (alpha2 * fc if x <= block_depth else 0.0)
            force = area * net_stress
            force_sum += force
            steel_values.append((force, x, stress))
        return force_sum, concrete_force, concrete_centroid, tuple(steel_values)

    low = max(1e-6, D * 1e-9)
    high = D
    low_force = equilibrium(low)[0]
    high_force = equilibrium(high)[0]
    while high_force < 0.0 and high < 100.0 * D:
        high *= 2.0
        high_force = equilibrium(high)[0]
    if low_force > 0.0 or high_force < 0.0:
        dn = float("nan")
    else:
        for _ in range(100):
            mid = (low + high) / 2.0
            if equilibrium(mid)[0] > 0.0:
                high = mid
            else:
                low = mid
        dn = (low + high) / 2.0

    if not math.isfinite(dn):
        demand = max(0.0, float(M_star_kNm or 0.0))
        return {
            "moment_sign": sign, "M_star_kNm": demand, "phi_Mu_kNm": 0.0,
            "Mu_nom_kNm": 0.0, "util": float("inf"), "status": "—",
            "dn_mm": dn, "ku": dn, "phi": 0.65, "tension_face": tension_face,
            "compression_face": compression_face, "tension_steel_label": tension_steel_label,
            "alpha2": alpha2, "gamma": gamma, "d_mm": d_mm,
            "Ast_tension_mm2": Ast, "shape_equilibrium_valid": False,
            "compression_steel_area_mm2": 0.0, "compression_concrete_area_mm2": 0.0,
        }

    residual, concrete_force, concrete_centroid, steel_values = equilibrium(dn)
    block_depth = min(D, gamma * dn)
    moment_nmm = concrete_force * concrete_centroid + sum(
        force * x for force, x, _stress in steel_values
    )
    Mu_nom = abs(moment_nmm) / 1_000_000.0
    ku = dn / d_mm
    phi = bending_strength_reduction_factor(ku, phi_max)
    phi_Mu = phi * Mu_nom
    demand = max(0.0, float(M_star_kNm or 0.0))
    util = demand / phi_Mu if phi_Mu > 0.0 else (0.0 if demand <= 0.0 else float("inf"))
    status = "INFO" if demand <= 1e-9 else ("PASS" if util <= 1.0 else "FAIL")
    compression_steel_area = sum(
        area for (area, x, _face), (_force, _sx, stress)
        in zip(transformed_layers, steel_values) if stress > 0.0 and x < dn
    )
    compression_concrete_area, _ = _area_and_centroid_to_depth(segments, min(D, dn))
    tension_force = -sum(min(force, 0.0) for force, _x, _stress in steel_values)
    compression_steel_force = sum(
        max(force, 0.0) for force, _x, _stress in steel_values
    )
    resultant_lever_arm = (
        abs(moment_nmm) / tension_force if tension_force > 0.0 else 0.0
    )

    return {
        "moment_sign": sign, "M_star_kNm": demand, "phi_Mu_kNm": phi_Mu,
        "Mu_nom_kNm": Mu_nom, "util": util, "status": status,
        "dn_mm": dn, "ku": ku, "phi": phi, "tension_face": tension_face,
        "compression_face": compression_face, "tension_steel_label": tension_steel_label,
        "alpha2": alpha2, "gamma": gamma, "d_mm": d_mm,
        "Ast_tension_mm2": Ast, "shape_equilibrium_valid": True,
        "equilibrium_residual_n": residual,
        "block_depth_mm": block_depth,
        "concrete_force_n": concrete_force,
        "concrete_centroid_mm": concrete_centroid,
        "tension_force_n": tension_force,
        "compression_steel_force_n": compression_steel_force,
        "resultant_lever_arm_mm": resultant_lever_arm,
        "compression_steel_area_mm2": compression_steel_area,
        "compression_concrete_area_mm2": compression_concrete_area,
        "steel_layer_forces_n": tuple(value[0] for value in steel_values),
        "steel_layer_depths_mm": tuple(value[1] for value in steel_values),
        "steel_layer_stresses_mpa": tuple(value[2] for value in steel_values),
    }


@dataclass(frozen=True)
class BendingCapacityInput:
    width_mm: float
    depth_mm: float
    concrete_strength_mpa: float
    reinforcement_strength_mpa: float
    capacity_factor: float
    bottom_steel_area_mm2: float
    top_steel_area_mm2: float
    positive_effective_depth_mm: float
    top_steel_depth_mm: float
    section_shape: str = "RECT"
    flange_width_mm: float | None = None
    flange_thickness_mm: float | None = None
    web_width_mm: float | None = None
    bottom_layers: tuple[tuple[float, float], ...] = ()
    top_layers: tuple[tuple[float, float], ...] = ()


def calculate_bending_capacity(
    *, moment_sign: str, demand_knm: float, values: BendingCapacityInput,
) -> dict:
    return solve_bending_capacity(moment_sign, demand_knm, {
        "b": values.width_mm, "D": values.depth_mm,
        "fc": values.concrete_strength_mpa, "fsy": values.reinforcement_strength_mpa,
        "phi_bend": values.capacity_factor, "Ast_bot": values.bottom_steel_area_mm2,
        "Ast_top": values.top_steel_area_mm2, "d": values.positive_effective_depth_mm,
        "do": values.top_steel_depth_mm, "section_shape": values.section_shape,
        "flange_width_mm": values.flange_width_mm or values.width_mm,
        "flange_thickness_mm": values.flange_thickness_mm or 0.0,
        "web_width_mm": values.web_width_mm or values.width_mm,
        "bottom_layers": values.bottom_layers, "top_layers": values.top_layers,
    })


__all__ = [
    "BendingCapacityInput", "bending_strength_reduction_factor",
    "calculate_bending_capacity", "solve_bending_capacity", "stress_block_factors",
]
