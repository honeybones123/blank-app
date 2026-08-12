"""The sole canonical input mutation boundary for Inputs V2."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs, DeflectionInputs, KvMethod, LongitudinalReinforcement, LayoutMode, MaterialInputs, ServiceabilityInputs, ShearReinforcement, SupportInputs, TimeDependentInputs, VoidInputs


@dataclass(frozen=True, slots=True)
class UpdateFirstSlice:
    width_mm: float
    depth_mm: float
    bottom_mode: LayoutMode
    bottom_bars: int
    bottom_spacing_mm: float
    bottom_diameter_mm: int
    bottom_cover_mm: float
    top_mode: LayoutMode = LayoutMode.COUNT
    top_bars: int = 2
    top_spacing_mm: float = 150.0
    top_diameter_mm: int = 10
    top_cover_mm: float = 40.0
    shear_diameter_mm: int = 0
    shear_legs: int = 0
    shear_spacing_mm: float = 200.0
    concrete_strength_mpa: float = 40.0
    reinforcement_strength_mpa: float = 500.0
    bending_moment_knm: float = 0.0
    torsion_knm: float = 0.0
    shear_force_kn: float = 0.0
    axial_force_kn: float = 0.0
    applied_prestress_kn: float = 0.0
    left_support: str = "Pinned"
    right_support: str = "Roller"
    span_mm: float = 2000.0
    section_shape: str = "RECT"
    width_locked: bool = False
    depth_locked: bool = False
    shrinkage_time_days: float = 365.0
    creep_time_days: float = 365.0
    age_at_loading_days: float = 28.0
    duct_count: int = 0
    duct_diameter_mm: float = 0.0
    deflection_support_condition: str = "Simply supported"
    deflection_limit_ratio: float = 250.0
    sls_moment_knm: float | None = None
    sls_shear_kn: float | None = None
    sls_permanent_udl_knm_per_m: float | None = None
    sls_imposed_udl_knm_per_m: float | None = None
    sls_equivalent_udl_knm_per_m: float | None = None
    sls_sustained_load_factor: float | None = None
    crack_width_limit_mm: float | None = None
    crack_member_type: str | None = None
    crack_k1: float | None = None
    crack_k2: float | None = None
    crack_creep_coefficient: float | None = None
    crack_shrinkage_microstrain: float | None = None
    sls_use_uls_fallback: bool | None = None
    shear_kv_method: KvMethod | None = None
    exposed_faces: str | None = None
    creep_environment: str | None = None
    shrinkage_environment: str | None = None
    sustained_stress_ratio: float | None = None
    sustained_concrete_stress_mpa: float | None = None
    concrete_modulus_mpa: float | None = None


def apply_input_command(current: BeamInputs, command: UpdateFirstSlice) -> BeamInputs:
    bottom = LongitudinalReinforcement(
        mode=LayoutMode(command.bottom_mode),
        bars=int(command.bottom_bars),
        spacing_mm=float(command.bottom_spacing_mm),
        diameter_mm=int(command.bottom_diameter_mm),
        cover_mm=float(command.bottom_cover_mm),
    )
    top = LongitudinalReinforcement(
        mode=LayoutMode(command.top_mode), bars=int(command.top_bars),
        spacing_mm=float(command.top_spacing_mm), diameter_mm=int(command.top_diameter_mm),
        cover_mm=float(command.top_cover_mm),
    )
    shear = ShearReinforcement(
        diameter_mm=int(command.shear_diameter_mm), legs=int(command.shear_legs),
        spacing_mm=float(command.shear_spacing_mm),
        kv_method=(
            current.shear.kv_method
            if command.shear_kv_method is None
            else KvMethod(command.shear_kv_method)
        ),
    )
    materials = MaterialInputs(command.concrete_strength_mpa, command.reinforcement_strength_mpa)
    actions = ActionInputs(
        bending_moment_knm=command.bending_moment_knm,
        torsion_knm=command.torsion_knm,
        shear_force_kn=command.shear_force_kn,
        axial_force_kn=command.axial_force_kn,
        applied_prestress_kn=command.applied_prestress_kn,
    )
    supports = SupportInputs(command.left_support, command.right_support)
    existing_time = current.time_dependent
    time_dependent = TimeDependentInputs(
        shrinkage_time_days=command.shrinkage_time_days,
        creep_time_days=command.creep_time_days,
        age_at_loading_days=command.age_at_loading_days,
        exposed_faces=existing_time.exposed_faces if command.exposed_faces is None else command.exposed_faces,
        creep_environment=existing_time.creep_environment if command.creep_environment is None else command.creep_environment,
        shrinkage_environment=(
            existing_time.shrinkage_environment
            if command.shrinkage_environment is None
            else command.shrinkage_environment
        ),
        stress_ratio=(
            existing_time.stress_ratio
            if command.sustained_stress_ratio is None
            else command.sustained_stress_ratio
        ),
        sustained_concrete_stress_mpa=(
            existing_time.sustained_concrete_stress_mpa
            if command.sustained_concrete_stress_mpa is None
            else command.sustained_concrete_stress_mpa
        ),
        concrete_modulus_mpa=(
            existing_time.concrete_modulus_mpa
            if command.concrete_modulus_mpa is None
            else command.concrete_modulus_mpa
        ),
    )
    voids = VoidInputs(command.duct_count, command.duct_diameter_mm)
    deflection = DeflectionInputs(command.deflection_support_condition, command.deflection_limit_ratio)
    existing_sls = current.serviceability
    serviceability = ServiceabilityInputs(
        moment_knm=existing_sls.moment_knm if command.sls_moment_knm is None else command.sls_moment_knm,
        shear_kn=existing_sls.shear_kn if command.sls_shear_kn is None else command.sls_shear_kn,
        permanent_udl_knm_per_m=(
            existing_sls.permanent_udl_knm_per_m
            if command.sls_permanent_udl_knm_per_m is None
            else command.sls_permanent_udl_knm_per_m
        ),
        imposed_udl_knm_per_m=(
            existing_sls.imposed_udl_knm_per_m
            if command.sls_imposed_udl_knm_per_m is None
            else command.sls_imposed_udl_knm_per_m
        ),
        equivalent_udl_knm_per_m=(
            existing_sls.equivalent_udl_knm_per_m
            if command.sls_equivalent_udl_knm_per_m is None
            else command.sls_equivalent_udl_knm_per_m
        ),
        sustained_load_factor=(
            existing_sls.sustained_load_factor
            if command.sls_sustained_load_factor is None
            else command.sls_sustained_load_factor
        ),
        crack_width_limit_mm=(
            existing_sls.crack_width_limit_mm
            if command.crack_width_limit_mm is None
            else command.crack_width_limit_mm
        ),
        crack_member_type=(
            existing_sls.crack_member_type
            if command.crack_member_type is None
            else command.crack_member_type
        ),
        crack_k1=existing_sls.crack_k1 if command.crack_k1 is None else command.crack_k1,
        crack_k2=existing_sls.crack_k2 if command.crack_k2 is None else command.crack_k2,
        creep_coefficient=(
            existing_sls.creep_coefficient
            if command.crack_creep_coefficient is None
            else command.crack_creep_coefficient
        ),
        shrinkage_microstrain=(
            existing_sls.shrinkage_microstrain
            if command.crack_shrinkage_microstrain is None
            else command.crack_shrinkage_microstrain
        ),
        use_uls_fallback=(
            existing_sls.use_uls_fallback
            if command.sls_use_uls_fallback is None
            else command.sls_use_uls_fallback
        ),
    )
    candidate = current.next_revision(
        width_mm=command.width_mm,
        depth_mm=command.depth_mm,
        span_mm=command.span_mm,
        section_shape=command.section_shape,
        width_locked=command.width_locked,
        depth_locked=command.depth_locked,
        bottom=bottom,
        top=top,
        shear=shear,
        materials=materials,
        actions=actions,
        supports=supports,
        time_dependent=time_dependent,
        voids=voids,
        deflection=deflection,
        serviceability=serviceability,
    )
    if candidate.content_hash == current.content_hash:
        return current
    return candidate
