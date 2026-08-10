"""V2-owned composition root for authoritative engineering calculations.

The snapshot is intentionally called through this single typed boundary. It
does not import the V1 Runtime or access Streamlit state.
"""

from __future__ import annotations

import math
from dataclasses import replace

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.engineering_result import EngineeringResult
from inputs_v2.engineering.bending_capacity import (
    BendingCapacityInput,
    calculate_bending_capacity,
)
from inputs_v2.engineering.crack_control import CrackControlInput, calculate_crack_control
from inputs_v2.engineering.deflection import (
    DeflectionInput,
    calculate_deflection,
    derive_equivalent_udl_from_actions,
    resolve_equivalent_loads,
)
from inputs_v2.engineering.shear_capacity import (
    ShearCapacityInput,
    compute_shear_capacity_values,
)
from inputs_v2.engineering.shear_detailing import ShearDetailingInput, calculate_shear_detailing
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement
from inputs_v2.engineering.check_metadata import check_metadata
from inputs_v2.engineering.time_dependent import (
    LoadingAgeFactorInput,
    calculate_loading_age_factor,
)
from inputs_v2.domain.reinforcement_arrangement import ReinforcementArrangement


def _legacy_payload(inputs: BeamInputs, arrangement: ReinforcementArrangement | None = None) -> dict[str, object]:
    # The authoritative calculation payload must use the fitted arrangement,
    # including every longitudinal layer.  Previously this used only the
    # single-row widget count, so a two-layer diagram could display eight bars
    # while bending capacity was calculated from four (or fewer).
    bottom_count = arrangement.total_bar_count if arrangement is not None else inputs.bottom.bars
    bottom_diameter = arrangement.bar_diameter_mm if arrangement is not None else inputs.bottom.diameter_mm
    bottom_area = bottom_count * 3.141592653589793 * bottom_diameter**2 / 4.0
    top_area = inputs.top.bars * 3.141592653589793 * inputs.top.diameter_mm**2 / 4.0
    d = arrangement.effective_depth_mm if arrangement is not None else inputs.depth_mm - inputs.bottom.cover_mm - inputs.bottom.diameter_mm / 2.0
    return {
        "b": inputs.width_mm, "D": inputs.depth_mm, "L": inputs.span_mm,
        "fc": inputs.materials.concrete_strength_mpa,
        "fsy": inputs.materials.reinforcement_strength_mpa,
        "phi_bend": 0.85, "Ast_bot": bottom_area, "Ast_top": top_area,
        "d": d, "do": inputs.top.cover_mm + inputs.top.diameter_mm / 2.0,
    }


def _nonzero(value: float | None) -> bool:
    try:
        return abs(float(value or 0.0)) > 1e-12
    except (TypeError, ValueError):
        return False


def _calculate_serviceability(
    inputs: BeamInputs,
    payload: dict[str, object],
    effective_depth_mm: float,
) -> dict[str, object]:
    """Run the copied V1 deflection path only when an SLS load exists."""

    sls = inputs.serviceability
    # Serviceability must use explicit SLS actions only. ULS actions are not a
    # substitute for crack-width or deflection loads.
    moment = sls.moment_knm
    has_load = any(
        _nonzero(value)
        for value in (
            moment,
            sls.shear_kn,
            sls.permanent_udl_knm_per_m,
            sls.imposed_udl_knm_per_m,
            sls.equivalent_udl_knm_per_m,
        )
    )
    limit_mm = inputs.span_mm / inputs.deflection.limit_ratio
    base: dict[str, object] = {
        "status": "NOT RUN" if not has_load else "PASS",
        "deflection_util": None,
        "deflection_mm": None,
        "short_term_deflection_mm": None,
        "long_term_deflection_mm": None,
        "limit_mm": limit_mm,
        "limit_ratio": inputs.deflection.limit_ratio,
        "effective_depth_mm": effective_depth_mm,
        "serviceability_loads_present": has_load,
    }
    if not has_load:
        return base

    span_m = inputs.span_mm / 1000.0
    # Zero-valued action fields mean “not supplied” when explicit UDLs exist;
    # this preserves the V1 load-resolution precedence.
    moment = moment if _nonzero(moment) else None
    shear = sls.shear_kn if _nonzero(sls.shear_kn) else None
    derived_udl = derive_equivalent_udl_from_actions(
        moment_knm=moment,
        shear_kn=shear,
        span_m=span_m,
        support_condition=inputs.deflection.support_condition,
    )
    g_used, q_used = resolve_equivalent_loads(
        derived_udl=derived_udl,
        equivalent_udl=(
            sls.equivalent_udl_knm_per_m
            if _nonzero(sls.equivalent_udl_knm_per_m)
            else None
        ),
        permanent_udl=sls.permanent_udl_knm_per_m if _nonzero(sls.permanent_udl_knm_per_m) else None,
        imposed_udl=sls.imposed_udl_knm_per_m if _nonzero(sls.imposed_udl_knm_per_m) else None,
    )
    if abs(float(g_used) + float(q_used)) <= 1e-12:
        return base
    result = calculate_deflection(DeflectionInput(
        span_m=span_m,
        concrete_modulus_mpa=30000.0,
        concrete_strength_mpa=inputs.materials.concrete_strength_mpa,
        effective_width_mm=inputs.width_mm,
        web_width_mm=inputs.width_mm,
        effective_depth_mm=effective_depth_mm,
        tension_steel_area_mm2=float(payload["Ast_bot"]),
        compression_steel_area_mm2=float(payload["Ast_top"]),
        permanent_udl_kn_per_m=float(g_used),
        imposed_udl_kn_per_m=float(q_used),
        sustained_load_factor=sls.sustained_load_factor,
        support_condition=inputs.deflection.support_condition,
    ))
    delta_short = result.short_term_mm
    delta_long = result.long_term_addition_mm
    delta_total = result.total_mm
    util = delta_total / limit_mm if limit_mm > 0 else None
    return {
        **base,
        "status": "FAIL" if util is not None and util > 1.0 else "PASS",
        "deflection_util": util,
        "deflection_mm": delta_total,
        "short_term_deflection_mm": delta_short,
        "long_term_deflection_mm": delta_long,
        "equivalent_permanent_udl_knm_per_m": float(g_used),
        "equivalent_imposed_udl_knm_per_m": float(q_used),
    }


def _sls_outer_steel_stress(
    inputs: BeamInputs,
    steel_area_mm2: float,
    effective_depth_mm: float,
) -> float:
    """Match the V1 cracked-section SLS outer-steel stress calculation."""

    moment = float(inputs.serviceability.moment_knm)
    if not _nonzero(moment) or steel_area_mm2 <= 0.0 or effective_depth_mm <= 0.0:
        return 0.0
    ec = 30000.0
    es = 200000.0
    transformed = (es / ec) * steel_area_mm2
    coefficient = inputs.width_mm / 2.0
    discriminant = transformed**2 + 4.0 * coefficient * transformed * effective_depth_mm
    neutral_axis = (-transformed + math.sqrt(max(discriminant, 0.0))) / (2.0 * coefficient)
    neutral_axis = max(1.0, min(neutral_axis, inputs.depth_mm))
    cracked_inertia = (
        inputs.width_mm * neutral_axis**3 / 3.0
        + transformed * (effective_depth_mm - neutral_axis) ** 2
    )
    if cracked_inertia <= 0.0:
        return 0.0
    curvature = (moment * 1e6) / (ec * cracked_inertia)
    return float(es * curvature * (effective_depth_mm - neutral_axis))


def _calculate_crack_control(
    inputs: BeamInputs,
    payload: dict[str, object],
    effective_depth_mm: float,
    arrangement: ReinforcementArrangement | None,
) -> dict[str, object]:
    """Run the copied V1 crack-control equations for explicit SLS moment."""

    sls = inputs.serviceability
    moment = sls.moment_knm
    # No ULS fallback: crack control is meaningful only with an explicit SLS
    # moment/load case.
    if not _nonzero(moment):
        return {
            "status": "NOT RUN",
            "util": None,
            "width_mm": None,
            "limit_mm": sls.crack_width_limit_mm,
            "effective_depth_mm": effective_depth_mm,
            "serviceability_loads_present": False,
        }
    rows = arrangement.rows if arrangement is not None else ()
    spacing = rows[0].clear_spacing_mm if rows else inputs.bottom.spacing_mm
    steel_area = float(payload["Ast_bot"])
    if moment != sls.moment_knm:
        # Keep the fallback local and deterministic without mutating the
        # immutable input snapshot used for source hashing.
        inputs_for_stress = replace(
            inputs,
            serviceability=replace(sls, moment_knm=moment),
        )
    else:
        inputs_for_stress = inputs
    sigma_sr = _sls_outer_steel_stress(inputs_for_stress, steel_area, effective_depth_mm)
    crack = calculate_crack_control(CrackControlInput(
        width_mm=inputs.width_mm,
        depth_mm=inputs.depth_mm,
        cover_mm=inputs.bottom.cover_mm,
        bar_diameter_mm=inputs.bottom.diameter_mm,
        bar_spacing_mm=spacing,
        steel_area_mm2=steel_area,
        concrete_strength_mpa=inputs.materials.concrete_strength_mpa,
        concrete_modulus_mpa=30000.0,
        steel_modulus_mpa=200000.0,
        steel_strength_mpa=inputs.materials.reinforcement_strength_mpa,
        crack_width_limit_mm=sls.crack_width_limit_mm,
        member_type=sls.crack_member_type,
        outer_steel_stress_mpa=sigma_sr,
        creep_coefficient=sls.creep_coefficient,
        shrinkage_strain=sls.shrinkage_microstrain * 1e-6,
        bond_factor=sls.crack_k1,
        strain_distribution_factor=sls.crack_k2,
    ))
    util = max(crack.utilisation_table, crack.utilisation_w)
    return {
        "status": "FAIL" if util > 1.0 else "PASS",
        "util": util,
        "width_mm": crack.w_calc,
        "limit_mm": sls.crack_width_limit_mm,
        "sigma_sr": sigma_sr,
        "sigma_allow_table": crack.sigma_allow_table,
        "table_util": crack.utilisation_table,
        "width_util": crack.utilisation_w,
        "effective_depth_mm": effective_depth_mm,
        "serviceability_loads_present": True,
    }


class EngineeringCalculator:
    def calculate(self, inputs: BeamInputs) -> EngineeringResult:
        return self.calculate_with_arrangement(inputs, inputs.bottom_arrangement)

    def calculate_with_arrangement(self, inputs: BeamInputs, arrangement: ReinforcementArrangement | None) -> EngineeringResult:
        payload = _legacy_payload(inputs, arrangement)
        bending = calculate_bending_capacity(
            moment_sign="positive",
            demand_knm=inputs.actions.bending_moment_knm,
            values=BendingCapacityInput(
                width_mm=float(payload["b"]),
                depth_mm=float(payload["D"]),
                concrete_strength_mpa=float(payload["fc"]),
                reinforcement_strength_mpa=float(payload["fsy"]),
                capacity_factor=float(payload["phi_bend"]),
                bottom_steel_area_mm2=float(payload["Ast_bot"]),
                top_steel_area_mm2=float(payload["Ast_top"]),
                positive_effective_depth_mm=float(payload["d"]),
                top_steel_depth_mm=float(payload["do"]),
            ),
        )
        # Row-level values consumed by the Runtime-style summary contract.
        # These are sourced from the same immutable calculation payload.
        bending["Ast_tension_mm2"] = float(payload["Ast_bot"])
        fctf = 0.6 * float(inputs.materials.concrete_strength_mpa) ** (2.0 / 3.0)
        ast_min = 0.4 * (fctf / float(inputs.materials.reinforcement_strength_mpa)) * float(inputs.width_mm) * float(payload["d"])
        bending["Ast_min_mm2"] = ast_min
        bending["minimum_tensile_status"] = "PASS" if float(payload["Ast_bot"]) >= ast_min else "FAIL"
        bending["service_moment_knm"] = float(inputs.serviceability.moment_knm)
        bending["minimum_capacity_knm"] = None
        bending["check_metadata"] = check_metadata("bending_capacity", "minimum_flexural_strength")
        ku = float(bending.get("ku", 0.0) or 0.0)
        ductility_limit = 0.4
        ductility = {
            "status": "FAIL" if ku > ductility_limit else "PASS",
            "ku": ku,
            "limit": ductility_limit,
            "util": ku / ductility_limit if ductility_limit else 0.0,
            "effective_depth_mm": float(payload["d"]),
            "check_metadata": check_metadata("bending_ductility"),
        }
        shear_input = ShearCapacityInput(
            b=inputs.width_mm, D=inputs.depth_mm, d=payload["d"],
            fc=inputs.materials.concrete_strength_mpa,
            fsy=inputs.materials.reinforcement_strength_mpa, Ec=30000.0, Es=200000.0,
            M_star=inputs.actions.bending_moment_knm, V_star=inputs.actions.shear_force_kn,
            T_star=inputs.actions.torsion_knm, N_star=inputs.actions.axial_force_kn,
            P_v=0.0, phi=0.75, sigma_cp=0.0, A_st=payload["Ast_bot"], A_pt=payload["Ast_top"],
            f_po=0.0, A_ct=inputs.width_mm * inputs.depth_mm, d_g=20.0,
            lig_d=inputs.shear.diameter_mm, legs=inputs.shear.legs,
            s_lig=inputs.shear.spacing_mm, use_general_kv=False, sum_duct=0.0, k_d=1.0,
        )
        shear = compute_shear_capacity_values(shear_input)
        shear_detailing = calculate_shear_detailing(ShearDetailingInput(
            reinforcement_area_mm2=float(shear.get("Asv", 0.0) or 0.0),
            spacing_mm=float(inputs.shear.spacing_mm),
            concrete_strength_mpa=float(inputs.materials.concrete_strength_mpa),
            web_width_mm=float(shear.get("b_v", inputs.width_mm) or inputs.width_mm),
            reinforcement_strength_mpa=float(inputs.materials.reinforcement_strength_mpa),
            section_depth_mm=float(inputs.depth_mm),
        ))
        shear.update(shear_detailing.as_family_values())
        shear["transverse_reinforcement_required"] = bool(
            abs(float(inputs.actions.shear_force_kn)) > float(shear.get("Vuc_kN", 0.0) or 0.0)
        )
        shear["check_metadata"] = check_metadata(
            "shear_strength", "shear_web_crushing", "concrete_shear_capacity",
            "transverse_reinforcement_required", "minimum_shear_reinforcement",
            "shear_reinforcement_capacity",
        )
        loading_age = calculate_loading_age_factor(
            LoadingAgeFactorInput(inputs.time_dependent.age_at_loading_days)
        )
        creep = {"k3_age_loading": loading_age.k3}
        fit = evaluate_arrangement(
            inputs,
            tuple(row.bar_count for row in arrangement.rows)
            if arrangement is not None else (inputs.bottom.bars,),
        )
        fit_arrangement = fit.arrangement if fit.accepted else arrangement
        effective_d = float(
            fit_arrangement.effective_depth_mm
            if fit_arrangement is not None
            else payload["d"]
        )
        serviceability = _calculate_serviceability(inputs, payload, effective_d)
        serviceability["check_metadata"] = check_metadata("short_term_deflection", "long_term_deflection", "span_depth_check")
        crack_control = _calculate_crack_control(inputs, payload, effective_d, fit_arrangement)
        crack_control["check_metadata"] = check_metadata("general_crack_control", "crack_table_method", "direct_crack_width")
        reinforcement_fit = {
            "accepted": fit.accepted,
            "layer_count": fit.arrangement.layer_count,
            "effective_depth_mm": fit.arrangement.effective_depth_mm,
            "congestion_class": fit.congestion.congestion_class,
            "failure_reasons": fit.failure_reasons,
            "vertical_fit_ok": fit.vertical_fit,
            "horizontal_fit_ok": fit.horizontal_fit,
            "aggregate_clearance_ok": fit.aggregate_clearance_ok,
            "cover_mm": float(inputs.bottom.cover_mm),
            "cover_status": "PASS" if float(inputs.bottom.cover_mm) > 0.0 else "FAIL",
            "check_metadata": check_metadata("durability_cover"),
        }
        geometry = {
            "depth_width_ratio": float(inputs.depth_mm) / max(float(inputs.width_mm), 1.0),
            "maximum_depth_width_ratio": 2.0,
            "status": "PASS" if float(inputs.depth_mm) <= 2.0 * float(inputs.width_mm) else "FAIL",
        }
        return EngineeringResult(
            inputs.revision, inputs.content_hash, "production-shadow",
            "Copied V1 formulas running inside the isolated V2 engineering boundary.",
            families={"bending": bending, "ductility": ductility, "shear": shear, "creep_shrinkage": creep, "serviceability": serviceability, "crack_control": crack_control, "reinforcement_fit": reinforcement_fit, "geometry": geometry},
        )

