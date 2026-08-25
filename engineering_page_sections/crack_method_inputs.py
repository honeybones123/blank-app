"""Selectable Crack Control method widgets and detached input values."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import streamlit as st

from application.contracts.concrete_crack_shrinkage import (
    CrackControlMethod,
    RestraintType,
)
from state_and_helpers import get_param


CRACK_METHOD_LABELS = {
    CrackControlMethod.EXISTING_AS3600.value: (
        "Existing StructuralBase method (AS 3600:2018)"
    ),
    CrackControlMethod.AS5100_WALL.value: (
        "AS 5100.5:2017 restrained wall (Clause 11.7.2)"
    ),
    CrackControlMethod.CIRIA_C766_EC2.value: (
        "CIRIA C766 + EC2 equation method"
    ),
}


@dataclass(frozen=True, slots=True)
class AS5100WallInputValues:
    thickness_mm: float
    horizontal_area_per_face_mm2_per_m: float
    vertical_spacing_mm: float
    in_base_zone: bool


@dataclass(frozen=True, slots=True)
class C766EndInputValues:
    restraint_type: str
    effective_modular_ratio: float
    non_uniform_stress_coefficient: float
    stress_distribution_coefficient: float
    characteristic_tensile_strength_mpa: float
    total_reinforcement_ratio: float
    reinforcement_modulus_mpa: float
    cover_mm: float
    bar_diameter_mm: float
    effective_reinforcement_ratio: float


@dataclass(frozen=True, slots=True)
class C766GeneralInputValues:
    restraint_type: str
    temperature_drop_early_c: float
    temperature_change_long_term_c: float
    thermal_expansion_microstrain_per_c: float
    restraint_early: float
    restraint_medium: float
    restraint_long: float
    tensile_strain_capacity_microstrain: float
    cover_mm: float
    bar_diameter_mm: float
    effective_reinforcement_ratio: float
    shrinkage_components: Mapping[str, Any]


def _method_number(
    label: str,
    key: str,
    shared_key: str,
    default: float,
    sync_callbacks: Mapping[str, Any],
    **kwargs: Any,
) -> float:
    if key not in st.session_state:
        st.session_state[key] = float(get_param(shared_key, default))
    return float(
        st.number_input(
            label,
            key=key,
            on_change=sync_callbacks[key],
            **kwargs,
        )
    )


def render_crack_method_selector(
    sync_callbacks: Mapping[str, Any],
) -> str:
    method_options = list(CRACK_METHOD_LABELS)
    method_current = str(
        get_param(
            "crack_control_method",
            CrackControlMethod.EXISTING_AS3600.value,
        )
    )
    if method_current not in method_options:
        method_current = CrackControlMethod.EXISTING_AS3600.value
    return str(
        st.selectbox(
            "Calculation method",
            options=method_options,
            index=method_options.index(method_current),
            format_func=lambda value: CRACK_METHOD_LABELS[value],
            key="crack_method",
            on_change=sync_callbacks["crack_method"],
        )
    )


def render_as5100_wall_inputs(
    sync_callbacks: Mapping[str, Any],
) -> AS5100WallInputValues:
    st.caption("AS 5100.5:2017 incorporating Amendment No. 1 - Clause 11.7.2")
    c1, c2 = st.columns(2)
    with c1:
        thickness = _method_number(
            "Wall thickness (mm)",
            "crack_wall_thickness",
            "crack_wall_thickness_mm",
            600.0,
            sync_callbacks,
            min_value=1.0,
            step=25.0,
        )
        area = _method_number(
            "Provided horizontal area per face (mm²/m)",
            "crack_wall_area",
            "crack_wall_horizontal_area_per_face",
            2750.0,
            sync_callbacks,
            min_value=0.0,
            step=50.0,
        )
    with c2:
        if "crack_wall_base_zone" not in st.session_state:
            st.session_state["crack_wall_base_zone"] = bool(
                get_param("crack_wall_in_base_zone", False)
            )
        in_base_zone = st.checkbox(
            "Base zone (height equal to wall thickness)",
            key="crack_wall_base_zone",
            on_change=sync_callbacks["crack_wall_base_zone"],
        )
        spacing = _method_number(
            "Provided vertical spacing (mm)",
            "crack_wall_spacing",
            "crack_wall_vertical_spacing_mm",
            150.0,
            sync_callbacks,
            min_value=1.0,
            step=25.0,
        )
    return AS5100WallInputValues(
        thickness_mm=thickness,
        horizontal_area_per_face_mm2_per_m=area,
        vertical_spacing_mm=spacing,
        in_base_zone=bool(in_base_zone),
    )


def render_as5100_wall_result_metrics(result: Any) -> None:
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Required per face",
        f"{result.required_area_per_face_mm2_per_m:,.0f} mm²/m",
    )
    m2.metric("Maximum spacing", f"{result.maximum_spacing_mm:,.0f} mm")
    m3.metric("Status", "PASS" if result.passes else "FAIL")
    st.info(result.warnings[0])


def render_c766_inputs(
    sync_callbacks: Mapping[str, Any],
    *,
    shrinkage_components: Mapping[str, Any] | None,
) -> C766EndInputValues | C766GeneralInputValues:
    st.caption(
        "CIRIA C766 equation path; temperature and restraint are explicit "
        "designer inputs."
    )
    restraint_options = [
        RestraintType.CONTINUOUS_EDGE.value,
        RestraintType.END.value,
        RestraintType.INTERNAL.value,
    ]
    restraint_current = str(
        get_param("crack_c766_restraint_type", restraint_options[0])
    )
    if restraint_current not in restraint_options:
        restraint_current = restraint_options[0]
    restraint = str(
        st.selectbox(
            "Restraint type",
            options=restraint_options,
            index=restraint_options.index(restraint_current),
            format_func=lambda value: value.replace("_", " ").title(),
            key="crack_c766_restraint",
            on_change=sync_callbacks["crack_c766_restraint"],
        )
    )
    if restraint == RestraintType.END.value:
        c1, c2, c3 = st.columns(3)
        with c1:
            alpha_e = _method_number(
                "Effective modular ratio αe",
                "crack_c766_alpha_e",
                "crack_c766_modular_ratio",
                7.0,
                sync_callbacks,
                min_value=0.000001,
            )
            coefficient_k = _method_number(
                "Non-uniform stress coefficient k",
                "crack_c766_k",
                "crack_c766_non_uniform_k",
                0.65,
                sync_callbacks,
                min_value=0.000001,
            )
            coefficient_kc = _method_number(
                "Stress-distribution coefficient kc",
                "crack_c766_kc",
                "crack_c766_stress_distribution_kc",
                1.0,
                sync_callbacks,
                min_value=0.000001,
            )
        with c2:
            fctk = _method_number(
                "Characteristic tensile strength at cracking (MPa)",
                "crack_c766_fctk",
                "crack_c766_characteristic_tensile_mpa",
                2.0,
                sync_callbacks,
                min_value=0.000001,
            )
            rho_total = _method_number(
                "Total reinforcement / tension-area ratio",
                "crack_c766_rho_total",
                "crack_c766_total_reinforcement_ratio",
                0.01,
                sync_callbacks,
                min_value=0.000001,
                format="%.5f",
            )
            es_mpa = float(get_param("Es", 200_000.0))
            st.caption(
                f"Reinforcement modulus Es = {es_mpa:,.0f} MPa "
                "(shared material input)"
            )
        with c3:
            cover = _method_number(
                "Cover (mm)",
                "crack_c766_cover",
                "crack_c766_cover_mm",
                45.0,
                sync_callbacks,
                min_value=0.0,
            )
            diameter = _method_number(
                "Bar diameter (mm)",
                "crack_c766_db",
                "crack_c766_bar_diameter_mm",
                20.0,
                sync_callbacks,
                min_value=1.0,
            )
            rho_eff = _method_number(
                "Effective reinforcement ratio",
                "crack_c766_rho_eff",
                "crack_c766_effective_reinforcement_ratio",
                0.01,
                sync_callbacks,
                min_value=0.000001,
                format="%.5f",
            )
        return C766EndInputValues(
            restraint_type=restraint,
            effective_modular_ratio=alpha_e,
            non_uniform_stress_coefficient=coefficient_k,
            stress_distribution_coefficient=coefficient_kc,
            characteristic_tensile_strength_mpa=fctk,
            total_reinforcement_ratio=rho_total,
            reinforcement_modulus_mpa=es_mpa,
            cover_mm=cover,
            bar_diameter_mm=diameter,
            effective_reinforcement_ratio=rho_eff,
        )

    if shrinkage_components is None:
        raise ValueError("C766 continuous/internal restraint requires shrinkage inputs")
    epsca_early = float(shrinkage_components["autogenous_early"]) * 1e6
    epsca_long = float(shrinkage_components["autogenous_long_term"]) * 1e6
    drying = float(shrinkage_components["drying_long_term"])
    c1, c2, c3 = st.columns(3)
    with c1:
        t1 = _method_number(
            "Early temperature drop T1 / ΔT (°C)",
            "crack_c766_t1",
            "crack_c766_t1_c",
            46.1,
            sync_callbacks,
            min_value=0.0,
        )
        t2 = _method_number(
            "Long-term temperature change T2 (°C)",
            "crack_c766_t2",
            "crack_c766_t2_c",
            20.0,
            sync_callbacks,
            min_value=0.0,
        )
        alpha_micro = _method_number(
            "Thermal expansion (µε/°C)",
            "crack_c766_alpha",
            "crack_c766_alpha_micro_per_c",
            12.0,
            sync_callbacks,
            min_value=0.0,
        )
    with c2:
        r1 = _method_number(
            "Early restraint R1",
            "crack_c766_r1",
            "crack_c766_restraint_early",
            0.676,
            sync_callbacks,
            min_value=0.0,
            max_value=1.0,
        )
        r2 = _method_number(
            "Medium-term restraint R2",
            "crack_c766_r2",
            "crack_c766_restraint_medium",
            0.644,
            sync_callbacks,
            min_value=0.0,
            max_value=1.0,
        )
        r3 = _method_number(
            "Long-term restraint R3",
            "crack_c766_r3",
            "crack_c766_restraint_long",
            0.644,
            sync_callbacks,
            min_value=0.0,
            max_value=1.0,
        )
    with c3:
        ectu_micro = _method_number(
            "Tensile strain capacity (µε)",
            "crack_c766_ectu",
            "crack_c766_tensile_capacity_micro",
            70.0,
            sync_callbacks,
            min_value=0.0,
        )
        st.metric(
            f"Calculated autogenous shrinkage at "
            f"{shrinkage_components['early_age_days']:.0f} d",
            f"{epsca_early:.1f} µε",
        )
        st.metric(
            f"Calculated autogenous shrinkage at "
            f"{shrinkage_components['age_days']:.0f} d",
            f"{epsca_long:.1f} µε",
        )
        st.metric("Calculated drying shrinkage", f"{drying * 1e6:.1f} µε")
        source_label = (
            "EC2/C766"
            if shrinkage_components["method"] == "ec2_c766"
            else "AS 3600"
        )
        st.caption(
            f"Calculated automatically from the Shrinkage page "
            f"({source_label} method)."
        )
        st.caption(
            "C766 creep-relaxation factors are applied automatically: "
            "K1 = 0.65 and K2 = 0.50."
        )
    g1, g2, g3 = st.columns(3)
    with g1:
        cover = _method_number(
            "Cover (mm)",
            "crack_c766_cover",
            "crack_c766_cover_mm",
            45.0,
            sync_callbacks,
            min_value=0.0,
        )
    with g2:
        diameter = _method_number(
            "Bar diameter (mm)",
            "crack_c766_db",
            "crack_c766_bar_diameter_mm",
            20.0,
            sync_callbacks,
            min_value=1.0,
        )
    with g3:
        rho_eff = _method_number(
            "Effective reinforcement ratio",
            "crack_c766_rho_eff",
            "crack_c766_effective_reinforcement_ratio",
            0.01,
            sync_callbacks,
            min_value=0.000001,
            format="%.5f",
        )
    return C766GeneralInputValues(
        restraint_type=restraint,
        temperature_drop_early_c=t1,
        temperature_change_long_term_c=t2,
        thermal_expansion_microstrain_per_c=alpha_micro,
        restraint_early=r1,
        restraint_medium=r2,
        restraint_long=r3,
        tensile_strain_capacity_microstrain=ectu_micro,
        cover_mm=cover,
        bar_diameter_mm=diameter,
        effective_reinforcement_ratio=rho_eff,
        shrinkage_components=MappingProxyType(dict(shrinkage_components)),
    )


def render_c766_result_metrics(result: Any) -> None:
    if hasattr(result, "restrained_strain"):
        m1, m2, m3 = st.columns(3)
        m1.metric("Restrained strain", f"{result.restrained_strain * 1e6:,.0f} µε")
        m2.metric(
            "Crack width",
            f"{(result.characteristic_crack_width_mm or 0.0):.3f} mm",
        )
        m3.metric("Crack initiation", "YES" if result.crack_initiates else "NO")
    else:
        m1, m2 = st.columns(2)
        m1.metric(
            "Crack-inducing strain",
            f"{result.crack_inducing_strain * 1e6:,.0f} µε",
        )
        m2.metric(
            "Crack width",
            f"{(result.characteristic_crack_width_mm or 0.0):.3f} mm",
        )
    st.warning(result.warnings[0])


__all__ = [
    "AS5100WallInputValues",
    "C766EndInputValues",
    "C766GeneralInputValues",
    "CRACK_METHOD_LABELS",
    "render_as5100_wall_inputs",
    "render_as5100_wall_result_metrics",
    "render_c766_inputs",
    "render_c766_result_metrics",
    "render_crack_method_selector",
]
