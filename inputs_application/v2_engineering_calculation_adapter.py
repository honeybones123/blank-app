"""Calculation-only boundary for the installed Inputs V2 engineering engine.

Load Analysis and other non-Inputs consumers use this module without importing
Design Brain orchestration, recommendation, rendering, CTA, or Apply code.
"""

from __future__ import annotations

from functools import lru_cache
from dataclasses import asdict, replace
from typing import Any, Mapping

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)
from application.v2_source_manifest import source_manifest_hash
from calculations.deflection import derive_sustained_stress_ratio
from section_props.props import compute_gross_props


V2_ENGINEERING_CALCULATION_CONTRACT_VERSION = "inputs_v2.calculation.v7"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(mapping: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return float(default)


def _integer(mapping: Mapping[str, Any], *keys: str, default: int = 0) -> int:
    return int(round(_number(mapping, *keys, default=float(default))))


def _boolean(mapping: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        if key not in mapping:
            continue
        value = mapping.get(key)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "locked"}
        return bool(value)
    return False


_V2_DEFLECTION_LIMIT_RATIOS = frozenset({200.0, 250.0, 300.0, 400.0})
_V2_LONGITUDINAL_DIAMETERS = frozenset({10, 12, 16, 20, 24, 28, 32, 36, 40})


def _v2_longitudinal_bar_count(
    mapping: Mapping[str, Any],
    *keys: str,
    default: int,
    allow_zero: bool = False,
) -> int:
    bars = _integer(mapping, *keys, default=default)
    # Top steel is optional.  A configured zero is an engineering value, not a
    # missing/invalid count that should silently recover the old default.
    if allow_zero and bars == 0:
        return 0
    return bars if 2 <= bars <= 12 else int(default)


def _v2_longitudinal_diameter(
    mapping: Mapping[str, Any],
    *keys: str,
    default: int = 10,
) -> int:
    diameter = _integer(mapping, *keys, default=default)
    return diameter if diameter in _V2_LONGITUDINAL_DIAMETERS else int(default)


def _v2_longitudinal_cover(
    mapping: Mapping[str, Any],
    *keys: str,
    default: float = 40.0,
) -> float:
    cover = _number(mapping, *keys, default=default)
    return cover if 10.0 <= cover <= 150.0 else float(default)


def _v2_longitudinal_spacing(
    mapping: Mapping[str, Any],
    *keys: str,
    default: float = 150.0,
) -> float:
    """Supply a valid spacing placeholder for V2 count-based layouts.

    Legacy Runtime snapshots can persist ``0`` because longitudinal spacing is
    inactive when reinforcement is entered by bar count.  V2 validates the
    field even in count mode, so normalise only invalid legacy values at this
    adapter boundary without changing the saved Runtime snapshot.
    """

    spacing = _number(mapping, *keys, default=default)
    return spacing if 50.0 <= spacing <= 500.0 else float(default)


def _v2_deflection_limit_ratio(mapping: Mapping[str, Any]) -> float:
    """Normalize legacy Runtime values at the V2 boundary.

    The old Runtime exposed L/500 while the standalone V2 contract exposes
    200/250/300/400.  A persisted legacy value must not crash the automatic
    calculation region; it is projected to V2's documented default and the
    committed V2 model becomes the displayed authority for that revision.
    """

    ratio = _number(mapping, "defl_limit_ratio", default=250.0)
    return ratio if ratio in _V2_DEFLECTION_LIMIT_RATIOS else 250.0


def _normalise_shape(value: Any) -> str:
    shape = str(value or "RECT").strip().upper()
    if shape in {"RECTANGULAR", "RECTANGLE"}:
        return "RECT"
    return shape if shape in {"RECT", "T", "I"} else "RECT"


def _v2_kv_method(value: Any, api: Mapping[str, Any]):
    """Map Runtime labels to the explicit V2 shear-method contract.

    Runtime historically persisted presentation labels rather than an
    engineering enum.  Resolve those aliases once at this adapter boundary
    and fail closed for an unknown non-empty value so the calculator cannot
    silently run the wrong AS 3600 branch.
    """

    raw = str(value or "").strip()
    normalised = raw.casefold()
    if not normalised or "8.2.4.3" in normalised or "simplified" in normalised:
        return api["KvMethod"].SIMPLIFIED
    if "8.2.4.2" in normalised or "general" in normalised:
        return api["KvMethod"].GENERAL
    raise ValueError(f"Unsupported shear k_v method: {raw}")


def _resolved_actions(snapshot: EngineeringInputSnapshot) -> dict[str, Any]:
    actions = _mapping(snapshot.design_actions)
    resolved = _mapping(actions.get("resolved"))
    return resolved or actions


def _merge_primary(primary: Mapping[str, Any], fallback: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    merged.update(primary)
    return merged


def _derived_sustained_creep_state(
    *,
    geometry: Mapping[str, Any],
    materials: Mapping[str, Any],
    actions: Mapping[str, Any],
) -> dict[str, float]:
    """Derive creep stress from the same resolved SLS action used by V2.

    Creep strain is stress-dependent.  Passing the SLS moment into the
    serviceability contract without also deriving its concrete stress left the
    authoritative creep family at zero strain.  Keep this derivation at the
    calculation adapter boundary so every consumer receives the same result.
    """

    shape = _normalise_shape(geometry.get("sec_shape"))
    dimensions = {
        key: _number(geometry, key, default=0.0)
        for key in ("b", "D", "bf", "tf", "bw", "tw")
    }
    try:
        gross = compute_gross_props(shape, dimensions)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        gross = compute_gross_props("RECT", dimensions)
    sustained = derive_sustained_stress_ratio(
        fc_mpa=_number(materials, "fc", default=0.0),
        sls_m_pos_kNm=_number(actions, "SLS_M_pos", default=0.0),
        sls_m_neg_kNm=_number(actions, "SLS_M_neg", default=0.0),
        z_top_mm3=_number(gross, "Ztop_g", default=0.0),
        z_bot_mm3=_number(gross, "Zbot_g", default=0.0),
    )
    return {
        "stress_ratio": float(sustained["stress_ratio"]),
        "sustained_sigma_cs_mpa": float(sustained["sigma_cs_mpa"]),
    }


def _bottom_row_specs(reinforcement: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    """Return every committed bottom row without collapsing it into row 1.

    Runtime stores both canonical row keys and historical widget aliases.  The
    authoritative adapter resolves those aliases once and keeps the exact row
    counts and diameters used by the diagram and detailed pages.
    """

    row_1_count = _integer(
        reinforcement,
        "bot_row_1_bars",
        "bot1_count",
        "bot1_bars",
        default=3,
    )
    row_1_diameter = _v2_longitudinal_diameter(
        reinforcement,
        "bot_row_1_dia",
        "db_bot_1",
        "db_bot",
        default=10,
    )
    rows: list[tuple[int, int]] = [(row_1_count, row_1_diameter)]

    row_2_count = _integer(
        reinforcement,
        "bot_row_2_bars",
        "bot2_count",
        "bot2_bars",
        default=0,
    )
    # ``bot_row_count`` is the authoritative activation flag used by the
    # Runtime editor and section diagram.  Inactive row values are retained so
    # a user can switch back to two rows without re-entering them, but they
    # must not contribute to the engineering calculation.  Older snapshots do
    # not contain this field, so infer their active rows from the stored count.
    declared_row_count = (
        _integer(reinforcement, "bot_row_count", default=1)
        if "bot_row_count" in reinforcement
        else (2 if row_2_count > 0 else 1)
    )
    if declared_row_count not in {1, 2}:
        raise ValueError("Bottom reinforcement row count must be one or two.")

    if declared_row_count == 2 and row_2_count > 0:
        row_2_diameter = _v2_longitudinal_diameter(
            reinforcement,
            "bot_row_2_dia",
            "db_bot_2",
            default=row_1_diameter,
        )
        rows.append((row_2_count, row_2_diameter))

    if any(count < 2 for count, _diameter in rows):
        raise ValueError("Each active bottom reinforcement row must contain at least two bars.")
    total = sum(count for count, _diameter in rows)
    if not 2 <= total <= 12:
        raise ValueError("Total bottom reinforcement bar count must be between 2 and 12.")
    return tuple(rows)



@lru_cache(maxsize=1)
def _v2_api():
    """Load only the installed V2 calculation contracts.

    This module deliberately excludes Design Brain orchestration, advice,
    publication and Apply authority so non-Inputs pages can calculate without
    importing the concrete Design Brain adapter.
    """

    from inputs_v2.application.calculation_coordinator import (  # noqa: PLC0415
        CalculationCoordinator,
    )
    from inputs_v2.engineering.engineering_calculator import (  # noqa: PLC0415
        EngineeringCalculator,
    )
    from inputs_v2.domain.beam_inputs import (  # noqa: PLC0415
        ActionInputs,
        BeamInputs,
        DeflectionInputs,
        KvMethod,
        LayoutMode,
        LongitudinalReinforcement,
        MaterialInputs,
        ServiceabilityInputs,
        ShearReinforcement,
        SupportInputs,
        TimeDependentInputs,
        VoidInputs,
    )
    from inputs_v2.engineering.reinforcement_fit import (  # noqa: PLC0415
        evaluate_arrangement,
    )

    return {
        "CalculationCoordinator": CalculationCoordinator,
        "EngineeringCalculator": EngineeringCalculator,
        "ActionInputs": ActionInputs,
        "BeamInputs": BeamInputs,
        "DeflectionInputs": DeflectionInputs,
        "KvMethod": KvMethod,
        "LayoutMode": LayoutMode,
        "LongitudinalReinforcement": LongitudinalReinforcement,
        "MaterialInputs": MaterialInputs,
        "ServiceabilityInputs": ServiceabilityInputs,
        "ShearReinforcement": ShearReinforcement,
        "SupportInputs": SupportInputs,
        "TimeDependentInputs": TimeDependentInputs,
        "VoidInputs": VoidInputs,
        "evaluate_arrangement": evaluate_arrangement,
    }


def _beam_inputs_from_snapshot(
    snapshot: EngineeringInputSnapshot,
    api: Mapping[str, Any],
    revision: int,
    resolved_inputs: Mapping[str, Any] | None = None,
):
    resolved = _mapping(resolved_inputs)
    geometry = _merge_primary(_mapping(snapshot.geometry), resolved)
    materials = _merge_primary(_mapping(snapshot.materials), resolved)
    reinforcement = _merge_primary(_mapping(snapshot.reinforcement), resolved)
    settings = _merge_primary(_mapping(snapshot.design_settings), resolved)
    locks = _mapping(snapshot.locked_variables)
    actions = _merge_primary(_resolved_actions(snapshot), resolved)
    serviceability_loads = _merge_primary(
        _mapping(_mapping(snapshot.design_actions).get("serviceability_loads")),
        resolved,
    )
    sustained_creep = _derived_sustained_creep_state(
        geometry=geometry,
        materials=materials,
        actions=actions,
    )

    span_mm = _number(geometry, "L", "span_mm", default=2000.0)
    if "L" not in geometry and "span_mm" not in geometry and geometry.get("span_m") is not None:
        span_mm = _number(geometry, "span_m", default=2.0) * 1000.0

    exposed_faces_raw = str(resolved.get("faces_option") or "").strip()
    exposed_faces_key = exposed_faces_raw.replace("â€“", "-").replace("–", "-").lower()
    if not exposed_faces_raw or "three faces" in exposed_faces_key:
        exposed_faces = "Beam – three faces exposed"
    elif "one face" in exposed_faces_key:
        exposed_faces = "Slab – one face exposed"
    else:
        exposed_faces = exposed_faces_raw

    bottom_rows = _bottom_row_specs(reinforcement)
    bottom_bars = sum(count for count, _diameter in bottom_rows)
    bottom_diameter = bottom_rows[0][1]
    bottom_cover = _v2_longitudinal_cover(reinforcement, "cover_bot")
    top = api["LongitudinalReinforcement"](
        mode=api["LayoutMode"].COUNT,
        bars=_v2_longitudinal_bar_count(
            reinforcement,
            "top_row_1_bars",
            "top_bars",
            default=2,
            allow_zero=True,
        ),
        spacing_mm=_v2_longitudinal_spacing(
            reinforcement,
            "top_spacing",
            "top_row_1_spacing",
        ),
        diameter_mm=_v2_longitudinal_diameter(
            reinforcement,
            "db_top",
            "top_dia",
        ),
        cover_mm=_v2_longitudinal_cover(reinforcement, "cover_top"),
    )
    bottom = api["LongitudinalReinforcement"](
        mode=api["LayoutMode"].COUNT,
        bars=bottom_bars,
        spacing_mm=_v2_longitudinal_spacing(
            reinforcement,
            "bot_row_1_spacing",
            "bot1_spacing",
        ),
        diameter_mm=bottom_diameter,
        cover_mm=bottom_cover,
    )
    kv_method_value = (
        settings.get("k_v_method")
        or settings.get("kv_method")
        or settings.get("shear_k_v_method")
        or ""
    )
    from inputs_application.shear_state_normalization import normalize_shear_link_pair

    shear_pair = normalize_shear_link_pair(
        {
            "lig_d": _integer(reinforcement, "lig_d", default=0),
            "lig_legs": _integer(reinforcement, "lig_legs", default=0),
        }
    )
    shear = api["ShearReinforcement"](
        diameter_mm=shear_pair["lig_d"],
        legs=shear_pair["lig_legs"],
        spacing_mm=_number(reinforcement, "s_lig", default=200.0),
        kv_method=_v2_kv_method(kv_method_value, api),
    )
    section_shape = _normalise_shape(geometry.get("sec_shape"))
    section_width = _number(
        geometry,
        "bw" if section_shape == "T" else "tw" if section_shape == "I" else "b",
        "b",
        default=250.0,
    )
    flange_width = _number(geometry, "bf", default=section_width)
    web_width = _number(
        geometry,
        "tw" if section_shape == "I" else "bw",
        "b",
        default=section_width,
    )
    flange_thickness = _number(geometry, "tf", default=0.0)
    v2_inputs = api["BeamInputs"](
        revision=int(revision),
        width_mm=section_width,
        depth_mm=_number(geometry, "D", "d", default=300.0),
        span_mm=span_mm,
        section_shape=section_shape,
        flange_width_mm=flange_width if section_shape in {"T", "I"} else None,
        flange_thickness_mm=flange_thickness if section_shape in {"T", "I"} else None,
        web_width_mm=web_width if section_shape in {"T", "I"} else None,
        clause_815_analysis_verified=_boolean(
            settings, "clause_815_analysis_verified", "advanced_analysis_verified"
        ),
        compression_reinforcement_restrained=_boolean(
            settings, "compression_reinforcement_restrained", "compression_steel_restrained"
        ),
        width_locked=_boolean(locks, "optimisation_lock_width", "lock_width", "width_locked"),
        depth_locked=_boolean(locks, "optimisation_lock_depth", "lock_depth", "depth_locked"),
        side_cover_mm=_number(
            reinforcement,
            "cover_side",
            default=bottom_cover,
        ),
        bottom=bottom,
        top=top,
        shear=shear,
        materials=api["MaterialInputs"](
            concrete_strength_mpa=_number(materials, "fc", default=40.0),
            reinforcement_strength_mpa=_number(materials, "fsy", default=500.0),
        ),
        actions=api["ActionInputs"](
            bending_moment_knm=_number(actions, "Mu", "Mu_pos", default=0.0),
            torsion_knm=_number(actions, "Tu", default=0.0),
            shear_force_kn=_number(actions, "Vu", default=0.0),
            axial_force_kn=_number(actions, "Nu", default=0.0),
            applied_prestress_kn=_number(actions, "P", "Pu", "P_star", default=0.0),
        ),
        supports=api["SupportInputs"](
            str(settings.get("left_support") or "Pinned"),
            str(settings.get("right_support") or "Roller"),
        ),
        time_dependent=api["TimeDependentInputs"](
            shrinkage_time_days=_number(resolved, "t_shrink", "shrinkage_time_days", default=365.0),
            creep_time_days=_number(resolved, "t_creep", "creep_time_days", default=365.0),
            age_at_loading_days=_number(resolved, "age_at_loading", "age_at_loading_days", default=28.0),
            exposed_faces=exposed_faces,
            creep_environment=str(resolved.get("creep_env") or "Temperate inland environment"),
            shrinkage_environment=str(resolved.get("shrinkage_env") or "Temperate inland environment"),
            stress_ratio=sustained_creep["stress_ratio"],
            sustained_concrete_stress_mpa=sustained_creep[
                "sustained_sigma_cs_mpa"
            ],
            concrete_modulus_mpa=_number(resolved, "Ec", default=30000.0),
        ),
        voids=api["VoidInputs"](
            ducts=_integer(resolved, "duct_count", "ducts", default=0),
            diameter_mm=_number(resolved, "duct_diameter_mm", "duct_diameter", default=0.0),
        ),
        deflection=api["DeflectionInputs"](
            str(settings.get("deflection_support_condition") or "Simply supported"),
            _v2_deflection_limit_ratio(settings),
        ),
        serviceability=api["ServiceabilityInputs"](
            moment_knm=_number(actions, "SLS_M", "SLS_M_pos", "sls_Mstar", default=0.0),
            shear_kn=_number(actions, "SLS_V", "sls_Vstar", default=0.0),
            permanent_udl_knm_per_m=_number(
                serviceability_loads,
                "g_udl_kNm_per_m",
                "g_kNm",
                "g_line_kNm",
                default=0.0,
            ),
            imposed_udl_knm_per_m=_number(
                serviceability_loads,
                "q_udl_kNm_per_m",
                "q_kNm",
                "q_line_kNm",
                default=0.0,
            ),
            equivalent_udl_knm_per_m=_number(
                serviceability_loads,
                "w_sls_kNm_per_m",
                "w_sls",
                default=0.0,
            ),
            sustained_load_factor=_number(
                serviceability_loads,
                "psi_udl",
                "psi_s",
                "defl_psi_s",
                default=0.4,
            ),
            crack_width_limit_mm=_number(
                serviceability_loads,
                "wmax_char_limit",
                default=0.3,
            ),
            crack_member_type=str(
                serviceability_loads.get("crack_member_type") or "Primarily flexure"
            ),
            crack_k1=_number(serviceability_loads, "crack_k1", default=0.8),
            crack_k2=_number(serviceability_loads, "crack_k2", "crk_k2", default=0.5),
            creep_coefficient=_number(serviceability_loads, "phi_cc_t", default=2.0),
            shrinkage_microstrain=_number(
                serviceability_loads,
                "eps_cs_total_micro",
                default=300.0,
            ),
            # Runtime summaries and saved inputs always retain explicit SLS
            # semantics.  This flag only authorises the installed Design
            # Brain service to construct its private, non-persistent 0.60 ULS
            # proxy while ranking candidates when genuine SLS actions are
            # absent.  The ordinary calculator ignores the flag.
            use_uls_fallback=True,
        ),
    ).validated()

    row_counts = tuple(count for count, _diameter in bottom_rows)
    row_diameters = tuple(diameter for _count, diameter in bottom_rows)
    fit = api["evaluate_arrangement"](
        v2_inputs,
        row_counts,
        row_diameters_mm=row_diameters,
        min_row_gap_mm=_number(reinforcement, "rowgap_bot", default=60.0),
    )
    if fit.accepted:
        v2_inputs = replace(v2_inputs, bottom_arrangement=fit.arrangement).validated()
    return v2_inputs, row_counts, serviceability_loads



def _resolved_inputs_projection(
    source: Mapping[str, Any] | None,
    current: Any,
) -> dict[str, Any]:
    """Expose the committed V2 model as the neutral current-input projection."""

    resolved = dict(source or {})
    arrangement_rows = tuple(current.bottom_arrangement.rows) if current.bottom_arrangement else ()
    first_row = arrangement_rows[0] if arrangement_rows else None
    second_row = arrangement_rows[1] if len(arrangement_rows) > 1 else None
    resolved.update(
        {
            "b": current.width_mm,
            "D": current.depth_mm,
            "L": current.span_mm,
            "sec_shape": current.section_shape,
            "fc": current.materials.concrete_strength_mpa,
            "fsy": current.materials.reinforcement_strength_mpa,
            "bot_row_1_bars": first_row.bar_count if first_row else current.bottom.bars,
            "bot1_count": first_row.bar_count if first_row else current.bottom.bars,
            "bot_row_1_dia": (
                first_row.bar_diameter_mm
                if first_row and first_row.bar_diameter_mm
                else current.bottom.diameter_mm
            ),
            "db_bot_1": (
                first_row.bar_diameter_mm
                if first_row and first_row.bar_diameter_mm
                else current.bottom.diameter_mm
            ),
            "bot_row_1_spacing": current.bottom.spacing_mm,
            "bot_row_2_bars": second_row.bar_count if second_row else 0,
            "bot2_count": second_row.bar_count if second_row else 0,
            "bot_row_2_dia": (
                second_row.bar_diameter_mm
                if second_row and second_row.bar_diameter_mm
                else 0
            ),
            "db_bot_2": (
                second_row.bar_diameter_mm
                if second_row and second_row.bar_diameter_mm
                else 0
            ),
            "cover_bot": current.bottom.cover_mm,
            "top_bars": current.top.bars,
            "db_top": current.top.diameter_mm,
            "top_spacing": current.top.spacing_mm,
            "cover_top": current.top.cover_mm,
            "lig_d": current.shear.diameter_mm,
            "lig_legs": current.shear.legs,
            "s_lig": current.shear.spacing_mm,
            "k_v_method": (
                "General εx-based (Cl. 8.2.4.2)"
                if current.shear.use_general_kv
                else "Simplified method (Cl. 8.2.4.3)"
            ),
            "Mu": current.actions.bending_moment_knm,
            "Vu": current.actions.shear_force_kn,
            "Tu": current.actions.torsion_knm,
            "Nu": current.actions.axial_force_kn,
            "P_star": current.actions.applied_prestress_kn,
            "defl_limit_ratio": current.deflection.limit_ratio,
            "deflection_support_condition": current.deflection.support_condition,
            "SLS_M": current.serviceability.moment_knm,
            "SLS_V": current.serviceability.shear_kn,
            "g_udl_kNm_per_m": current.serviceability.permanent_udl_knm_per_m,
            "q_udl_kNm_per_m": current.serviceability.imposed_udl_knm_per_m,
            "w_sls_kNm_per_m": current.serviceability.equivalent_udl_knm_per_m,
            "t_shrink": current.time_dependent.shrinkage_time_days,
            "t_creep": current.time_dependent.creep_time_days,
            "age_at_loading": current.time_dependent.age_at_loading_days,
            "faces_option": current.time_dependent.exposed_faces,
            "creep_env": current.time_dependent.creep_environment,
            "shrinkage_env": current.time_dependent.shrinkage_environment,
            "stress_ratio": current.time_dependent.stress_ratio,
            "sustained_sigma_cs_mpa": current.time_dependent.sustained_concrete_stress_mpa,
        }
    )
    if current.section_shape == "T":
        resolved.pop("b", None)
        resolved.update(
            {
                "bw": current.web_width_mm,
                "bf": current.flange_width_mm,
                "tf": current.flange_thickness_mm,
            }
        )
    elif current.section_shape == "I":
        resolved.pop("b", None)
        resolved.update(
            {
                "tw": current.web_width_mm,
                "bf": current.flange_width_mm,
                "tf": current.flange_thickness_mm,
            }
        )
    return resolved


def _actions_used_projection(current: Any) -> dict[str, float]:
    """Expose the committed V2 action model to summary consumers.

    The Inputs summary uses this small neutral projection to distinguish an
    active check from an informational/no-load check.  V2 owns the action
    values, so leaving this out makes the summary overlay default to zeros and
    hides otherwise valid ULS utilisation/status values.
    """

    return {
        "Mu_signed": float(current.actions.bending_moment_knm or 0.0),
        "Mu": float(current.actions.bending_moment_knm or 0.0),
        "Vu": float(current.actions.shear_force_kn or 0.0),
        "Tu": float(current.actions.torsion_knm or 0.0),
        "Nu": float(current.actions.axial_force_kn or 0.0),
        "SLS_M_signed": float(current.serviceability.moment_knm or 0.0),
        "SLS_M": float(current.serviceability.moment_knm or 0.0),
        "SLS_V": float(current.serviceability.shear_kn or 0.0),
    }



def _v2_summary_packs(*, current: Any, families: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Project V2 family results into the Runtime summary-pack shape.

    The summary is a presentation consumer, not a second calculator. Keeping
    this projection at the V2 adapter boundary lets the existing Runtime cards
    consume the same family result as Design Brain while the old dictionary
    check builders are retired behind shadow tests.
    """

    def _family(name: str) -> dict[str, Any]:
        value = families.get(name) if isinstance(families, Mapping) else None
        return dict(value) if isinstance(value, Mapping) else {}

    def _status(value: Any, *, informational: bool = False) -> str:
        if informational:
            return "INFO"
        text = str(value or "").strip().upper()
        return text if text in {"PASS", "FAIL", "WARN", "CHECK", "INFO"} else "—"

    def _row(
        *,
        uid: str,
        title: str,
        route_page: str,
        action: Any = "—",
        capacity: Any = "—",
        util: Any = None,
        status: Any = "—",
        informational: bool = False,
        primary: bool = False,
    ) -> dict[str, Any]:
        return {
            "uid": uid,
            "title": title,
            "row_type": "v2_family",
            "action": action,
            "capacity": capacity,
            "calculated": capacity,
            "requirement": action,
            "value": action,
            "limit": capacity,
            "util": util if util is not None else "—",
            "status": _status(status, informational=informational),
            "ok": None if informational else (_status(status) == "PASS"),
            "is_informational": informational,
            "is_primary": primary,
            "route_page": route_page,
            "tab": route_page,
        }

    bending = _family("bending")
    shear = _family("shear")
    crack = _family("crack_control")
    serviceability = _family("serviceability")
    creep = _family("creep")
    shrinkage = _family("shrinkage")
    mu = float(getattr(current.actions, "bending_moment_knm", 0.0) or 0.0)
    vu = float(getattr(current.actions, "shear_force_kn", 0.0) or 0.0)
    phi_mu = bending.get("phi_Mu_kNm")
    phi_vu = shear.get("phi_Vu")
    shear_util = (
        abs(vu) / float(phi_vu)
        if phi_vu not in (None, "") and float(phi_vu or 0.0) > 0.0
        else 0.0
    )
    crack_run = bool(crack.get("serviceability_loads_present"))
    deflection_run = bool(serviceability.get("serviceability_loads_present"))

    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number == number else None

    def _display(value: Any, *, unit: str = "", decimals: int = 1) -> str:
        number = _number(value)
        if number is None:
            return "—"
        suffix = f" {unit}" if unit else ""
        return f"{number:.{decimals}f}{suffix}"

    def _status_for_util(util: Any, *, fallback: Any = "INFO") -> str:
        number = _number(util)
        if number is None:
            return _status(
                fallback,
                informational=str(fallback).strip().upper() in {"INFO", "NOT RUN"},
            )
        return "PASS" if number <= 1.0 else "FAIL"

    # The V2 standalone card is the visual authority for these values.  Keep
    # the raw numbers in the family result, but project the exact V2 display
    # strings into the legacy summary-pack boundary so the Runtime renderer
    # cannot fall back to Python's long float representation.
    bending_action_display = f"Mu*(+) = {mu:.1f} kNm" if abs(mu) > 1e-9 else "Mu*(+) = —"
    bending_capacity_display = (
        f"ϕMu(+) = {float(phi_mu):.1f} kNm"
        if phi_mu not in (None, "")
        else "ϕMu(+) = —"
    )
    bending_util_display = (
        f"{float(bending.get('util')):.2f}"
        if bending.get("util") not in (None, "")
        else "—"
    )
    shear_util_display = f"{shear_util:.2f}" if abs(vu) > 1e-9 else "—"
    shear_status = (
        "PASS" if abs(vu) > 1e-9 and shear_util <= 1.0
        else "FAIL" if abs(vu) > 1e-9
        else "INFO"
    )
    shear_informational = abs(vu) <= 1e-9

    # Expose the already-calculated V2 family evidence that the compact
    # Runtime projection previously discarded.  This is presentation only:
    # no legacy calculation is called from this adapter.
    bending_status = (
        _status_for_util(bending.get("util"), fallback=bending.get("status"))
        if abs(mu) > 1e-9
        else "INFO"
    )
    bending_informational = abs(mu) <= 1e-9
    ductility = _family("ductility")
    bending_rows = [
        _row(uid="v2_bending_capacity", title="Flexural strength capacity", route_page="bending", action=bending_action_display, capacity=bending_capacity_display, util=bending_util_display, status=bending_status, informational=bending_informational, primary=True),
        _row(uid="v2_bending_minimum_tensile", title="Minimum tensile reinforcement", route_page="bending", action=f"As,provided = {_display(bending.get('Ast_tension_mm2'), unit='mm²', decimals=0)}", capacity=f"As,min = {_display(bending.get('Ast_min_mm2'), unit='mm²', decimals=0)}", util="—", status=bending.get("minimum_tensile_status") or "INFO", informational=bending.get("Ast_min_mm2") is None),
        _row(uid="v2_bending_ductility", title="Ductility limit", route_page="bending", action=f"k_u = {_display(ductility.get('ku'), decimals=3)}", capacity=f"k_u,lim = {_display(ductility.get('limit'), decimals=2)}", util=_display(ductility.get("util"), decimals=2), status=ductility.get("status") or "INFO", informational=ductility.get("ku") is None),
        _row(uid="v2_bending_service_moment", title="Service bending moment", route_page="bending", action="SLS design / manual actions", capacity=f"M_s = {_display(bending.get('service_moment_knm'), unit='kNm')}", util="—", status="INFO", informational=True),
        _row(uid="v2_bending_minimum_capacity", title="Minimum design capacity requirement", route_page="bending", action=f"Mu,min = {_display(bending.get('minimum_capacity_knm'), unit='kNm')}", capacity=f"ϕMu,cap = {_display(bending.get('phi_Mu_kNm'), unit='kNm')}", util=_display(bending.get("minimum_capacity_util"), decimals=2), status=bending.get("minimum_capacity_status") or "INFO", informational=bending.get("minimum_capacity_knm") is None),
    ]

    shear_capacity_display = f"ϕVu = {_display(phi_vu, unit='kN')}"
    shear_action_display = f"V*eq = {vu:.1f} kN" if abs(vu) > 1e-9 else "V*eq = —"
    shear_rows = [
        _row(uid="v2_shear_capacity", title="Sectional shear capacity", route_page="shear", action=shear_action_display, capacity=shear_capacity_display, util=shear_util_display, status=shear_status, informational=shear_informational, primary=True),
        _row(uid="v2_shear_torsion", title="Torsion cracking check", route_page="shear", action=("Torsion design required" if shear.get("torsion_required") else "Torsion design not required"), capacity=f"Reference: 0.25 ϕTcr = {_display(shear.get('torsion_required_limit'), unit='kNm')}", util="—", status="INFO", informational=True),
        _row(uid="v2_shear_web_crushing", title="Web-crushing strength", route_page="shear", action=shear_action_display, capacity=f"Vu,max = {_display(shear.get('Vu_max_kN'), unit='kN')}", util="—", status="INFO" if shear.get("web_ok") is None else ("PASS" if shear.get("web_ok") else "FAIL"), informational=shear.get("web_ok") is None),
        _row(uid="v2_shear_reinforcement", title="Transverse reinforcement requirement", route_page="shear", action=("Shear reinforcement required" if shear.get("transverse_reinforcement_required") else "No shear reinforcement required"), capacity="V2 shear verification", util="—", status="INFO", informational=True),
    ]

    crack_status = _status(crack.get("status"), informational=not crack_run)
    crack_rows = [
        _row(uid="v2_crack_governing", title="Governing outcome", route_page="crack", action=("Serviceability checks assessed" if crack_run else "SLS actions not supplied"), capacity="Table stress + direct width", util="—", status=crack_status, informational=not crack_run, primary=True),
        _row(uid="v2_crack_table", title="Table-based crack control check", route_page="crack", action=f"σsr = {_display(crack.get('sigma_sr'), unit='MPa')}", capacity=f"σallow = {_display(crack.get('sigma_allow_table'), unit='MPa')}", util=_display(crack.get("table_util"), decimals=2), status=_status_for_util(crack.get("table_util"), fallback="INFO"), informational=not crack_run),
        _row(uid="v2_crack_width", title="Direct crack width check", route_page="crack", action=f"w = {_display(crack.get('width_mm'), unit='mm', decimals=3)}", capacity=f"w′max = {_display(crack.get('limit_mm'), unit='mm', decimals=3)}", util=_display(crack.get("width_util"), decimals=2), status=_status_for_util(crack.get("width_util"), fallback=crack_status), informational=not crack_run),
    ]

    deflection_status = _status(serviceability.get("status"), informational=not deflection_run)
    deflection_limit = serviceability.get("limit_mm")
    deflection_rows = [
        _row(uid="v2_deflection_total", title="Total deflection (short + long-term)", route_page="deflection", action=f"δtotal = {_display(serviceability.get('deflection_mm'), unit='mm', decimals=2)}", capacity=f"δlim = {_display(deflection_limit, unit='mm', decimals=2)}", util=_display(serviceability.get("deflection_util"), decimals=2), status=deflection_status, informational=not deflection_run, primary=True),
        _row(uid="v2_deflection_short", title="Short-term deflection (total load)", route_page="deflection", action=f"δshort = {_display(serviceability.get('short_term_deflection_mm'), unit='mm', decimals=2)}", capacity=f"δlim = {_display(deflection_limit, unit='mm', decimals=2)}", util="—", status="INFO" if not deflection_run else "PASS", informational=not deflection_run),
        _row(uid="v2_deflection_long", title="Additional long-term deflection", route_page="deflection", action=f"δlong = {_display(serviceability.get('long_term_deflection_mm'), unit='mm', decimals=2)}", capacity=f"δlim = {_display(deflection_limit, unit='mm', decimals=2)}", util="—", status="INFO" if not deflection_run else "PASS", informational=not deflection_run),
    ]
    # Deflection cards label the measured response as ``calculated`` and the
    # allowable response as ``requirement``.  The generic engineering row uses
    # action/capacity terminology, so make the specialised projection explicit
    # instead of allowing the legacy renderer to reverse these columns.
    for row in deflection_rows:
        row["calculated"] = row.get("action", "—")
        row["requirement"] = row.get("capacity", "—")

    summary_packs = {
        "bending": {
            "source": "inputs_v2",
            "authoritative_family": dict(bending),
            "authoritative_ductility_family": dict(ductility),
            "summary_phiMu_kNm": phi_mu,
            "summary_Mu_star_kNm": mu,
            "summary_Ms_sls_kNm": bending.get("service_moment_knm"),
            "summary_util": bending.get("util"),
            "summary_Mcr_kNm": bending.get("Mcr_kNm"),
            "rows": [
                _row(
                    uid="v2_bending_capacity",
                    title="Bending capacity",
                    route_page="bending",
                    action=bending_action_display,
                    capacity=bending_capacity_display,
                    util=bending_util_display,
                    status=bending.get("status"),
                )
            ],
        },
        "shear": {
            "source": "inputs_v2",
            "summary_display_source": "inputs_v2",
            "summary_display_capacity": (
                f"ϕVu = {float(phi_vu):.1f} kN" if phi_vu not in (None, "") else "ϕVu = —"
            ),
            "summary_display_demand": (
                f"V*eq = {vu:.1f} kN" if abs(vu) > 1e-9 else "V*eq = —"
            ),
            "summary_phiVu_kN": phi_vu,
            "summary_Veq_kN": vu,
            "summary_util": shear_util,
            "summary_status": shear_status,
            "summary_governing_source": "v2_shear_capacity",
            "rows": [
                _row(
                    uid="v2_shear_capacity",
                    title="Shear capacity",
                    route_page="shear",
                    action=(f"V*eq = {vu:.1f} kN" if abs(vu) > 1e-9 else "V*eq = —"),
                    capacity=(f"ϕVu = {float(phi_vu):.1f} kN" if phi_vu not in (None, "") else "ϕVu = —"),
                    util=shear_util_display,
                    status=shear_status,
                    informational=shear_informational,
                )
            ],
        },
        "crack": {
            "source": "inputs_v2",
            "action_source": crack.get("action_source"),
            "rows": [
                _row(
                    uid="v2_crack_control",
                    title="Crack control",
                    route_page="crack",
                    action=(crack.get("width_mm") if crack_run else "Not supplied"),
                    capacity=(crack.get("limit_mm") if crack_run else "—"),
                    util=(crack.get("util") if crack_run else None),
                    status=(crack.get("status") if crack_run else "INFO"),
                    informational=not crack_run,
                )
            ],
        },
        "deflection": {
            "source": "inputs_v2",
            "action_source": serviceability.get("action_source"),
            "summary_delta_total_mm": serviceability.get("deflection_mm") if deflection_run else 0.0,
            "summary_defl_limit_mm": serviceability.get("limit_mm") if deflection_run else 0.0,
            "summary_util_total": serviceability.get("deflection_util") if deflection_run else None,
            "rows": [
                _row(
                    uid="v2_deflection",
                    title="Deflection",
                    route_page="deflection",
                    action=(serviceability.get("deflection_mm") if deflection_run else "Not supplied"),
                    capacity=(serviceability.get("limit_mm") if deflection_run else "—"),
                    util=(serviceability.get("deflection_util") if deflection_run else None),
                    status=(serviceability.get("status") if deflection_run else "INFO"),
                    informational=not deflection_run,
                )
            ],
        },
        "creep": {
            "source": "inputs_v2",
            "phi_cc_t": creep.get("phi_cc_t"),
            "phi_cc_star_table": creep.get("phi_cc_star_table"),
            "eps_cc_micro": creep.get("eps_cc_micro"),
            "rows": [],
        },
        "shrinkage": {
            "source": "inputs_v2",
            "eps_cs_total": shrinkage.get("eps_cs_total"),
            "eps_cs_total_micro": shrinkage.get("eps_cs_total_micro"),
            "eps_cse": shrinkage.get("eps_cse"),
            "eps_csd_t": shrinkage.get("eps_csd_t"),
            "rows": [],
        },
    }
    summary_packs["bending"]["rows"] = bending_rows
    summary_packs["shear"]["rows"] = shear_rows
    summary_packs["crack"]["rows"] = crack_rows
    summary_packs["deflection"]["rows"] = deflection_rows
    return summary_packs



def calculate_v2_authoritative_result(
    *,
    engineering_snapshot: EngineeringInputSnapshot,
    resolved_inputs: Mapping[str, Any],
    input_revision: int,
) -> AuthoritativeDesignResult:
    """Calculate one revision-matched V2 result without running Design Brain.

    This is the sibling calculation path used before the Design Guide starts.
    It uses the same V2 calculator and input mapping as the Design Brain
    adapter, but publishes only engineering families and summary packs.
    """

    api = _v2_api()
    current, _row_counts, serviceability_loads = _beam_inputs_from_snapshot(
        engineering_snapshot,
        api,
        int(input_revision),
        resolved_inputs,
    )
    publication = api["CalculationCoordinator"](
        api["EngineeringCalculator"]()
    ).calculate_current(current)
    if publication.stale or publication.result is None:
        raise ValueError("V2 calculation result is stale")
    calculated = publication.result
    families = dict(calculated.families)
    manifest = source_manifest_hash()
    current_calculations = {
        "source": "inputs_v2",
        "calculation_contract_version": V2_ENGINEERING_CALCULATION_CONTRACT_VERSION,
        "actions_used": _actions_used_projection(current),
        "resolved_inputs": _resolved_inputs_projection(resolved_inputs, current),
        "v2_source_manifest_hash": manifest,
        "v2_source_revision": int(calculated.source_revision),
        "v2_source_hash": calculated.source_hash,
        "v2_status": calculated.status,
        "v2_summary": calculated.summary,
        "families": families,
        "packs": _v2_summary_packs(current=current, families=families),
        "serviceability_loads": serviceability_loads,
    }
    return build_authoritative_design_result(
        engineering_snapshot=engineering_snapshot,
        current_calculations=current_calculations,
        family_contract_version="inputs_v2.family.v1",
        family_outcome="engineering_calculation_ready",
    )



__all__ = [
    "V2_ENGINEERING_CALCULATION_CONTRACT_VERSION",
    "calculate_v2_authoritative_result",
]
