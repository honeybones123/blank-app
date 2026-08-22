"""V2-owned composition root for authoritative engineering calculations.

The snapshot is intentionally called through this single typed boundary. It
does not import the V1 Runtime or access Streamlit state.
"""

from __future__ import annotations

import math
from dataclasses import replace

from inputs_v2.domain.beam_inputs import BeamInputs, KvMethod
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
from inputs_v2.engineering.sls_cracked_section import (
    CrackedSectionLayer,
    solve_sls_cracked_section,
)
from inputs_v2.engineering.time_dependent import (
    LoadingAgeFactorInput,
    basic_creep_coeff,
    calc_eps_cse,
    calc_k1_shrinkage,
    calc_k2_creep,
    calc_k4,
    calc_k5,
    calc_k6,
    calculate_loading_age_factor,
    creep_closest_th,
    creep_coefficient_value,
    creep_strain_values,
    exposed_perimeter_geometry_values,
    final_creep_coeff_table,
    shrinkage_closest_th,
    shrinkage_eps_final,
    shrinkage_total_values,
    sustained_creep_stress_mpa,
)
from inputs_v2.domain.reinforcement_arrangement import ReinforcementArrangement
from inputs_v2.domain.serviceability_source import ServiceabilityActionSource


def _legacy_payload(inputs: BeamInputs, arrangement: ReinforcementArrangement | None = None) -> dict[str, object]:
    # The authoritative calculation payload must use the fitted arrangement,
    # including every longitudinal layer.  Previously this used only the
    # single-row widget count, so a two-layer diagram could display eight bars
    # while bending capacity was calculated from four (or fewer).
    bottom_count = arrangement.total_bar_count if arrangement is not None else inputs.bottom.bars
    bottom_diameter = arrangement.outer_bar_diameter_mm if arrangement is not None else inputs.bottom.diameter_mm
    bottom_area = (
        arrangement.total_steel_area_mm2
        if arrangement is not None
        else bottom_count * 3.141592653589793 * bottom_diameter**2 / 4.0
    )
    top_area = inputs.top.bars * 3.141592653589793 * inputs.top.diameter_mm**2 / 4.0
    d = arrangement.effective_depth_mm if arrangement is not None else inputs.depth_mm - inputs.bottom.cover_mm - inputs.bottom.diameter_mm / 2.0
    bottom_layers = (
        tuple(
            (
                row.bar_count * math.pi * row.bar_diameter_mm**2 / 4.0,
                inputs.depth_mm - row.centre_from_tension_face_mm,
            )
            for row in arrangement.rows
        )
        if arrangement is not None
        else ((bottom_area, d),)
    )
    bottom_layer_labels = (
        tuple(
            f"Bottom reinforcement — {row.bar_count}-N{row.bar_diameter_mm:g}"
            for row in arrangement.rows
        )
        if arrangement is not None
        else (f"Bottom reinforcement — {bottom_count}-N{bottom_diameter:g}",)
    )
    top_depth = inputs.top.cover_mm + inputs.top.diameter_mm / 2.0
    return {
        "b": inputs.width_mm, "D": inputs.depth_mm, "L": inputs.span_mm,
        "fc": inputs.materials.concrete_strength_mpa,
        "fsy": inputs.materials.reinforcement_strength_mpa,
        "phi_bend": 0.85, "Ast_bot": bottom_area, "Ast_top": top_area,
        "d": d, "do": top_depth,
        "section_shape": inputs.section_shape,
        "flange_width_mm": inputs.flange_width_mm,
        "flange_thickness_mm": inputs.flange_thickness_mm,
        "web_width_mm": inputs.web_width_mm,
        "bottom_layers": bottom_layers,
        "top_layers": ((top_area, top_depth),) if top_area > 0.0 else (),
        "bottom_layer_labels": bottom_layer_labels,
        "top_layer_labels": (
            (f"Top reinforcement — {inputs.top.bars}-N{inputs.top.diameter_mm:g}",)
            if top_area > 0.0 else ()
        ),
    }


def _authoritative_sls_cracked_section(
    inputs: BeamInputs,
    payload: dict[str, object],
    *,
    ignore_compression_reinforcement: bool = False,
) -> dict[str, object]:
    """Build the one cracked-section result used by engineering and teaching."""

    bottom_layers = tuple(payload.get("bottom_layers", ()) or ())
    top_layers = tuple(payload.get("top_layers", ()) or ())
    bottom_labels = tuple(payload.get("bottom_layer_labels", ()) or ())
    top_labels = tuple(payload.get("top_layer_labels", ()) or ())
    layer_inputs: list[CrackedSectionLayer] = []
    for index, (area, depth_from_top) in enumerate(bottom_layers):
        label = (
            str(bottom_labels[index])
            if index < len(bottom_labels)
            else f"Bottom reinforcement layer {index + 1}"
        )
        layer_inputs.append(
            CrackedSectionLayer(
                layer_id=f"B{index + 1}",
                label=label,
                area_mm2=float(area),
                depth_from_top_mm=float(depth_from_top),
            )
        )
    for index, (area, depth_from_top) in enumerate(top_layers):
        label = (
            str(top_labels[index])
            if index < len(top_labels)
            else f"Top reinforcement layer {index + 1}"
        )
        layer_inputs.append(
            CrackedSectionLayer(
                layer_id=f"T{index + 1}",
                label=label,
                area_mm2=float(area),
                depth_from_top_mm=float(depth_from_top),
            )
        )
    moment = float(inputs.serviceability.moment_knm or 0.0)
    return solve_sls_cracked_section(
        width_mm=float(inputs.width_mm),
        depth_mm=float(inputs.depth_mm),
        concrete_modulus_mpa=float(inputs.time_dependent.concrete_modulus_mpa),
        service_moment_knm=abs(moment),
        layers=tuple(layer_inputs),
        section_shape=str(inputs.section_shape),
        flange_width_mm=inputs.flange_width_mm,
        flange_thickness_mm=inputs.flange_thickness_mm,
        web_width_mm=inputs.web_width_mm,
        moment_sign="negative" if moment < 0.0 else "positive",
        ignore_compression_reinforcement=ignore_compression_reinforcement,
    )


def _nonzero(value: float | None) -> bool:
    try:
        return abs(float(value or 0.0)) > 1e-12
    except (TypeError, ValueError):
        return False


def _gross_section_properties_from_top(inputs: BeamInputs) -> tuple[float, float, float]:
    """Return gross area, centroid and second moment about the centroid."""

    D = float(inputs.depth_mm)
    if inputs.section_shape == "RECT":
        strips = ((0.0, D, float(inputs.width_mm)),)
    else:
        bf = float(inputs.flange_width_mm or inputs.width_mm)
        tf = float(inputs.flange_thickness_mm or 0.0)
        bw = float(inputs.web_width_mm or inputs.width_mm)
        if inputs.section_shape == "T":
            strips = ((0.0, tf, bf), (tf, D, bw))
        else:
            strips = ((0.0, tf, bf), (tf, D - tf, bw), (D - tf, D, bf))
    areas = tuple(width * (end - start) for start, end, width in strips)
    area = sum(areas)
    centroid = sum(
        strip_area * (start + end) / 2.0
        for strip_area, (start, end, _width) in zip(areas, strips)
    ) / area
    inertia = sum(
        width * (end - start) ** 3 / 12.0
        + strip_area * (((start + end) / 2.0) - centroid) ** 2
        for strip_area, (start, end, width) in zip(areas, strips)
    )
    return area, centroid, inertia


def _minimum_flexural_steel_area(inputs: BeamInputs, effective_depth_mm: float) -> float:
    """AS 3600:2018 Cl. 8.1.6.1(2), positive bending direction."""

    D = float(inputs.depth_mm)
    d = float(effective_depth_mm)
    fctf = 0.6 * math.sqrt(float(inputs.materials.concrete_strength_mpa))
    fsy = float(inputs.materials.reinforcement_strength_mpa)
    bw = float(inputs.web_width_mm or inputs.width_mm)
    alpha_b = 0.20
    if inputs.section_shape in {"T", "I"}:
        bef = float(inputs.flange_width_mm or bw)
        Ds = float(inputs.flange_thickness_mm or 0.0)
        width_ratio = bef / bw
        if inputs.section_shape == "T":
            # Positive bending puts the web in tension for the current
            # top-flanged T-section contract.
            alpha_b = max(
                0.20 + (width_ratio - 1.0) * (0.4 * Ds / D - 0.18),
                0.20 * width_ratio ** 0.25,
            )
        else:
            # The bottom flange of the symmetric I-section is in tension.
            alpha_b = max(
                0.20 + (width_ratio - 1.0) * (0.25 * Ds / D - 0.08),
                0.20 * width_ratio ** (2.0 / 3.0),
            )
    return alpha_b * (D / d) ** 2 * (fctf / fsy) * bw * d


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
        "action_source": (
            ServiceabilityActionSource.ACTUAL_SLS_ACTIONS.value
            if has_load
            else ServiceabilityActionSource.NOT_PROVIDED.value
        ),
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
    web_width = float(inputs.web_width_mm or inputs.width_mm)
    compression_width = float(inputs.width_mm)
    if inputs.section_shape == "I" and inputs.flange_width_mm is not None:
        compression_width = float(inputs.flange_width_mm)
    elif (
        inputs.section_shape == "T"
        and inputs.flange_width_mm is not None
        and float(sls.moment_knm or 0.0) >= 0.0
    ):
        compression_width = float(inputs.flange_width_mm)
    result = calculate_deflection(DeflectionInput(
        span_m=span_m,
        concrete_modulus_mpa=inputs.time_dependent.concrete_modulus_mpa,
        concrete_strength_mpa=inputs.materials.concrete_strength_mpa,
        effective_width_mm=compression_width,
        web_width_mm=web_width,
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


def _sls_cracked_section_response(
    inputs: BeamInputs,
    payload: dict[str, object],
) -> dict[str, object]:
    """Return the authoritative multi-layer cracked-section publication."""

    return _authoritative_sls_cracked_section(inputs, payload)


def _calculate_crack_control(
    inputs: BeamInputs,
    payload: dict[str, object],
    effective_depth_mm: float,
    arrangement: ReinforcementArrangement | None,
    cracked_section: dict[str, object],
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
            "action_source": ServiceabilityActionSource.NOT_PROVIDED.value,
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
    if inputs_for_stress is not inputs:
        cracked_section = _sls_cracked_section_response(inputs_for_stress, payload)
    tension_layers = tuple(
        layer
        for layer in tuple(cracked_section.get("layers", ()) or ())
        if isinstance(layer, dict) and layer.get("state") == "tension"
    )
    outer_layer = max(
        tension_layers,
        key=lambda layer: float(layer.get("depth_from_compression_mm", 0.0) or 0.0),
        default=None,
    )
    sigma_sr = abs(float(outer_layer.get("stress_mpa", 0.0) or 0.0)) if outer_layer else 0.0
    neutral_axis_depth = float(cracked_section.get("neutral_axis_depth_mm", 0.0) or 0.0)
    crack = calculate_crack_control(CrackControlInput(
        width_mm=inputs.width_mm,
        depth_mm=inputs.depth_mm,
        cover_mm=inputs.bottom.cover_mm,
        bar_diameter_mm=(
            arrangement.outer_bar_diameter_mm
            if arrangement is not None
            else inputs.bottom.diameter_mm
        ),
        bar_spacing_mm=spacing,
        steel_area_mm2=steel_area,
        concrete_strength_mpa=inputs.materials.concrete_strength_mpa,
        concrete_modulus_mpa=inputs.time_dependent.concrete_modulus_mpa,
        steel_modulus_mpa=200000.0,
        steel_strength_mpa=inputs.materials.reinforcement_strength_mpa,
        crack_width_limit_mm=sls.crack_width_limit_mm,
        member_type=sls.crack_member_type,
        outer_steel_stress_mpa=sigma_sr,
        creep_coefficient=sls.creep_coefficient,
        shrinkage_strain=sls.shrinkage_microstrain * 1e-6,
        bond_factor=sls.crack_k1,
        strain_distribution_factor=sls.crack_k2,
        neutral_axis_depth_mm=neutral_axis_depth,
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
        "action_source": ServiceabilityActionSource.ACTUAL_SLS_ACTIONS.value,
        "sls_cracked_section": cracked_section,
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
                section_shape=str(payload["section_shape"]),
                flange_width_mm=payload["flange_width_mm"],
                flange_thickness_mm=payload["flange_thickness_mm"],
                web_width_mm=payload["web_width_mm"],
                bottom_layers=tuple(payload["bottom_layers"]),
                top_layers=tuple(payload["top_layers"]),
                bottom_layer_labels=tuple(payload["bottom_layer_labels"]),
                top_layer_labels=tuple(payload["top_layer_labels"]),
            ),
        )
        sls_cracked_section = _authoritative_sls_cracked_section(inputs, payload)
        sls_cracked_section_ignore_compression = _authoritative_sls_cracked_section(
            inputs,
            payload,
            ignore_compression_reinforcement=True,
        )
        bending["sls_cracked_section"] = sls_cracked_section
        bending["sls_cracked_section_ignore_compression"] = (
            sls_cracked_section_ignore_compression
        )
        # Row-level values consumed by the Runtime-style summary contract.
        # These are sourced from the same immutable calculation payload.
        bending["Ast_tension_mm2"] = float(payload["Ast_bot"])
        # AS 3600:2018 Cl. 8.1.6.1: the reinforcement expression is a
        # deemed-to-satisfy route; the actual nominal Muo route remains valid.
        fctf = 0.6 * math.sqrt(float(inputs.materials.concrete_strength_mpa))
        ast_min = _minimum_flexural_steel_area(inputs, float(payload["d"]))
        bending["Ast_min_mm2"] = ast_min
        bending["service_moment_knm"] = float(inputs.serviceability.moment_knm)
        # Publish the minimum flexural-strength check with the authoritative
        # bending result so no summary or family has to reconstruct it.
        _gross_area, gross_centroid_from_top, gross_inertia = (
            _gross_section_properties_from_top(inputs)
        )
        gross_section_modulus_mm3 = gross_inertia / (
            float(inputs.depth_mm) - gross_centroid_from_top
        )
        cracking_moment_knm = (
            fctf * gross_section_modulus_mm3 / 1_000_000.0
        )
        minimum_capacity_knm = 1.2 * cracking_moment_knm
        nominal_mu_knm = float(bending.get("Mu_nom_kNm", 0.0) or 0.0)
        minimum_capacity_util = (
            minimum_capacity_knm / nominal_mu_knm if nominal_mu_knm > 0.0 else None
        )
        bending["Mcr_kNm"] = cracking_moment_knm
        bending["minimum_capacity_knm"] = minimum_capacity_knm
        bending["minimum_capacity_util"] = minimum_capacity_util
        bending["minimum_capacity_status"] = (
            "PASS" if nominal_mu_knm >= minimum_capacity_knm else "FAIL"
        )
        deemed_reinforcement_ok = float(payload["Ast_bot"]) >= ast_min
        actual_strength_ok = nominal_mu_knm >= minimum_capacity_knm
        bending["minimum_tensile_deemed_status"] = (
            "PASS" if deemed_reinforcement_ok else "FAIL"
        )
        bending["minimum_tensile_status"] = (
            "PASS" if deemed_reinforcement_ok or actual_strength_ok else "FAIL"
        )
        bending["check_metadata"] = check_metadata(
            "bending_capacity",
            "bending_phi_factor",
            "minimum_flexural_strength",
        )
        ku = float(bending.get("ku", 0.0) or 0.0)
        ductility_limit = 0.36
        ku_is_valid = math.isfinite(ku) and ku > 0.0
        bending_util = float(bending.get("util", 0.0) or 0.0)
        # AS 3600:2018+A1 Clause 8.1.5 applies its additional requirements
        # only where BOTH k_uo > 0.36 and M* > 0.8 phi M_uo.  A high neutral
        # axis parameter at lower demand is therefore not, by itself, a
        # mandatory failure.
        conditional_triggered = bool(
            ku_is_valid
            and ku > ductility_limit
            and bending_util > 0.8
        )
        compression_steel_area = float(
            bending.get("compression_steel_area_mm2", 0.0) or 0.0
        )
        compression_concrete_area = float(
            bending.get("compression_concrete_area_mm2", 0.0) or 0.0
        )
        compression_steel_ratio = (
            compression_steel_area / compression_concrete_area
            if compression_concrete_area > 0.0
            else 0.0
        )
        compression_steel_ok = compression_steel_ratio >= 0.01
        analysis_verified = bool(inputs.clause_815_analysis_verified)
        restraint_verified = bool(inputs.compression_reinforcement_restrained)
        conditional_requirements_satisfied = bool(
            not conditional_triggered
            or (compression_steel_ok and analysis_verified and restraint_verified)
        )
        failed_requirements: list[str] = []
        if conditional_triggered and not conditional_requirements_satisfied:
            failed_requirements.append("neutral_axis_limit_exceeded")
            if not analysis_verified:
                failed_requirements.append("clause_815_analysis_not_verified")
            if not compression_steel_ok:
                failed_requirements.append("compression_reinforcement_below_one_percent")
            if not restraint_verified:
                failed_requirements.append("compression_reinforcement_restraint_not_verified")
        ductility = {
            "status": (
                "NOT RUN"
                if not ku_is_valid
                else "PASS"
                if not conditional_triggered or conditional_requirements_satisfied
                else "FAIL"
            ),
            "ku": ku,
            "limit": ductility_limit,
            "util": ku / ductility_limit if ku_is_valid and ductility_limit else None,
            "effective_depth_mm": float(payload["d"]),
            "bending_demand_ratio": bending_util,
            "conditional_triggered": conditional_triggered,
            "analysis_verified": analysis_verified,
            "compression_steel_area_mm2": compression_steel_area,
            "compression_concrete_area_mm2": compression_concrete_area,
            "compression_steel_ratio": compression_steel_ratio,
            "minimum_compression_steel_ratio": 0.01,
            "compression_steel_requirement_satisfied": compression_steel_ok,
            "compression_reinforcement_restrained": restraint_verified,
            "conditional_requirements_satisfied": conditional_requirements_satisfied,
            "failed_requirements": tuple(failed_requirements),
            "check_metadata": check_metadata("bending_ductility"),
        }
        shear_input = ShearCapacityInput(
            b=inputs.width_mm, D=inputs.depth_mm, d=payload["d"],
            fc=inputs.materials.concrete_strength_mpa,
            fsy=inputs.materials.reinforcement_strength_mpa, Ec=30000.0, Es=200000.0,
            M_star=inputs.actions.bending_moment_knm, V_star=inputs.actions.shear_force_kn,
            T_star=inputs.actions.torsion_knm, N_star=inputs.actions.axial_force_kn,
            # P_v is the applied prestress action carried by Runtime. A_pt and
            # f_po describe actual prestressing steel, which the current beam
            # input contract does not yet define. Ordinary top reinforcement
            # must never be substituted for either prestressing-steel term.
            P_v=inputs.actions.applied_prestress_kn,
            phi=0.75, sigma_cp=0.0, A_st=payload["Ast_bot"], A_pt=0.0,
            f_po=0.0, A_ct=inputs.width_mm * inputs.depth_mm, d_g=20.0,
            lig_d=inputs.shear.diameter_mm, legs=inputs.shear.legs,
            s_lig=inputs.shear.spacing_mm,
            use_general_kv=inputs.shear.kv_method is KvMethod.GENERAL,
            sum_duct=0.0,
            k_d=1.0,
            side_cover_mm=inputs.side_cover_mm,
        )
        shear = compute_shear_capacity_values(shear_input)
        # Publish the exact authoritative general-method input mapping for
        # auditability without changing the numerical component's established
        # parity surface.
        shear.update(
            {
                "P_v": float(shear_input.P_v),
                "A_st": float(shear_input.A_st),
                "A_pt": float(shear_input.A_pt),
                "f_po": float(shear_input.f_po),
            }
        )
        shear["kv_method"] = (
            inputs.shear.kv_method.value
        )
        shear["kv_check_id"] = (
            "kv_general_method"
            if inputs.shear.kv_method is KvMethod.GENERAL
            else "kv_simplified_method"
        )
        cage_fit = evaluate_arrangement(
            inputs,
            tuple(row.bar_count for row in arrangement.rows)
            if arrangement is not None else (inputs.bottom.bars,),
        )
        cage_arrangement = cage_fit.arrangement if cage_fit.accepted else arrangement
        # Longitudinal reinforcement and link legs live in the web for T and
        # symmetric-I sections.  Capacity, fit and detailing must therefore
        # use one identical cage width; falling back to the flange/legacy
        # rectangular width can hide impossible cages.
        cage_width_mm = float(inputs.web_width_mm or inputs.width_mm)
        cage_bar_coordinates: list[tuple[float, float, float]] = []
        cage_rows = tuple(cage_arrangement.rows) if cage_arrangement is not None else ()
        for row in cage_rows:
            diameter = float(row.bar_diameter_mm or inputs.bottom.diameter_mm)
            start_x = float(inputs.side_cover_mm) + float(inputs.shear.diameter_mm) + diameter / 2.0
            pitch = diameter + float(row.clear_spacing_mm)
            cage_bar_coordinates.extend(
                (start_x + index * pitch, float(row.centre_from_tension_face_mm), diameter)
                for index in range(int(row.bar_count))
            )
        top_diameter = float(inputs.top.diameter_mm)
        top_usable_width = cage_width_mm - 2.0 * (
            float(inputs.side_cover_mm) + float(inputs.shear.diameter_mm)
        )
        top_clear = (
            (top_usable_width - int(inputs.top.bars) * top_diameter)
            / (int(inputs.top.bars) - 1)
            if int(inputs.top.bars) > 1
            else top_usable_width
        )
        top_start_x = float(inputs.side_cover_mm) + float(inputs.shear.diameter_mm) + top_diameter / 2.0
        cage_bar_coordinates.extend(
            (
                top_start_x + index * (top_diameter + top_clear),
                float(inputs.depth_mm) - float(inputs.top.cover_mm) - float(inputs.shear.diameter_mm) - top_diameter / 2.0,
                top_diameter,
            )
            for index in range(int(inputs.top.bars))
        )
        shear_detailing = calculate_shear_detailing(ShearDetailingInput(
            reinforcement_area_mm2=float(shear.get("Asv", 0.0) or 0.0),
            spacing_mm=float(inputs.shear.spacing_mm),
            concrete_strength_mpa=float(inputs.materials.concrete_strength_mpa),
            web_width_mm=float(shear.get("b_v", inputs.width_mm) or inputs.width_mm),
            reinforcement_strength_mpa=float(inputs.materials.reinforcement_strength_mpa),
            section_depth_mm=float(inputs.depth_mm),
            effective_legs=int(inputs.shear.legs),
            link_diameter_mm=float(inputs.shear.diameter_mm),
            # BeamInputs currently carries one cover per longitudinal face;
            # the bottom cover is the canonical side-cover proxy used by the
            # fitted section layout and reproduces cover + link radius.
            side_cover_mm=float(inputs.side_cover_mm),
            longitudinal_bar_coordinates_mm=tuple(cage_bar_coordinates),
        ))
        shear.update(shear_detailing.as_family_values())
        shear["transverse_reinforcement_required"] = bool(
            abs(float(inputs.actions.shear_force_kn)) > float(shear.get("Vuc_kN", 0.0) or 0.0)
        )
        shear["check_metadata"] = check_metadata(
            "shear_strength", "shear_web_crushing", "concrete_shear_capacity",
            "kv_general_method" if inputs.shear.kv_method is KvMethod.GENERAL else "kv_simplified_method",
            "transverse_reinforcement_required", "minimum_shear_reinforcement",
            "shear_reinforcement_capacity", "additional_longitudinal_shear_reinforcement",
        )
        loading_age = calculate_loading_age_factor(
            LoadingAgeFactorInput(inputs.time_dependent.age_at_loading_days)
        )
        time_geometry = exposed_perimeter_geometry_values(
            inputs.width_mm,
            inputs.depth_mm,
            inputs.time_dependent.exposed_faces,
        )
        creep_th = creep_closest_th(time_geometry["th_raw"])
        shrinkage_th = shrinkage_closest_th(time_geometry["th_raw"])
        equation_th = time_geometry["th_raw"]
        phi_cc_b = basic_creep_coeff(inputs.materials.concrete_strength_mpa)
        k2 = calc_k2_creep(inputs.time_dependent.creep_time_days, equation_th)
        k4 = calc_k4(inputs.time_dependent.creep_environment)
        k5 = calc_k5(inputs.materials.concrete_strength_mpa, equation_th, k4)
        k6 = calc_k6(inputs.time_dependent.stress_ratio)
        phi_cc_t = creep_coefficient_value(
            k2=k2,
            k3=loading_age.k3,
            k4=k4,
            k5=k5,
            k6=k6,
            phi_cc_b=phi_cc_b,
        )
        phi_cc_star_table = final_creep_coeff_table(
            inputs.materials.concrete_strength_mpa,
            inputs.time_dependent.creep_environment,
            creep_th,
        )
        sigma0 = sustained_creep_stress_mpa(
            sustained_sigma_cs_mpa=inputs.time_dependent.sustained_concrete_stress_mpa,
            stress_ratio=inputs.time_dependent.stress_ratio,
            fc_mpa=inputs.materials.concrete_strength_mpa,
        )
        creep_strain = creep_strain_values(
            phi_cc_t,
            sigma0,
            inputs.time_dependent.concrete_modulus_mpa,
        )
        creep = {
            **time_geometry,
            "th_creep_mm": creep_th,
            "phi_cc_b": phi_cc_b,
            "phi_cc_t": phi_cc_t,
            "phi_cc_star_table": phi_cc_star_table,
            "k2_creep": k2,
            "k3_age_loading": loading_age.k3,
            "k3_creep": loading_age.k3,
            "k4_creep": k4,
            "k5_creep": k5,
            "k6_creep": k6,
            "stress_ratio": inputs.time_dependent.stress_ratio,
            "sustained_sigma_cs_mpa": sigma0,
            **creep_strain,
            "check_metadata": check_metadata("creep_coefficient"),
        }
        shrinkage_k1 = calc_k1_shrinkage(
            inputs.time_dependent.shrinkage_time_days,
            equation_th,
        )
        eps_cse = calc_eps_cse(
            inputs.materials.concrete_strength_mpa,
            inputs.time_dependent.shrinkage_time_days,
        )
        eps_csd_final = shrinkage_eps_final(
            inputs.materials.concrete_strength_mpa,
            inputs.time_dependent.shrinkage_environment,
            shrinkage_th,
        )
        shrinkage = {
            **time_geometry,
            "th_shrinkage_mm": shrinkage_th,
            "k1_shrinkage": shrinkage_k1,
            "eps_cse": eps_cse,
            "eps_csd_final": eps_csd_final,
            **shrinkage_total_values(shrinkage_k1, eps_cse, eps_csd_final),
            "check_metadata": check_metadata("shrinkage_strain"),
        }
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
        crack_control = _calculate_crack_control(
            inputs,
            payload,
            effective_d,
            fit_arrangement,
            sls_cracked_section,
        )
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
            "cage_width_mm": cage_width_mm,
            "section_shape": inputs.section_shape,
            "check_metadata": check_metadata("durability_cover"),
        }
        geometry = {
            "section_shape": inputs.section_shape,
            "web_width_mm": cage_width_mm,
            "flange_width_mm": inputs.flange_width_mm,
            "flange_thickness_mm": inputs.flange_thickness_mm,
            "concrete_area_mm2": inputs.section_geometry.concrete_area_mm2,
            "depth_width_ratio": float(inputs.depth_mm) / max(cage_width_mm, 1.0),
            "maximum_depth_width_ratio": 2.0,
            "status": "PASS" if float(inputs.depth_mm) <= 2.0 * cage_width_mm else "FAIL",
        }
        return EngineeringResult(
            inputs.revision, inputs.content_hash, "production-shadow",
            "Copied V1 formulas running inside the isolated V2 engineering boundary.",
            families={"bending": bending, "ductility": ductility, "shear": shear, "creep": creep, "shrinkage": shrinkage, "creep_shrinkage": creep, "serviceability": serviceability, "crack_control": crack_control, "reinforcement_fit": reinforcement_fit, "geometry": geometry},
        )

