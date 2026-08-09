"""Adapter for the isolated Inputs V2 Design Brain.

This module is the only Runtime boundary that knows how to load the V2
implementation.  Pages, stores, jobs, and Apply code receive only the
application-owned ``DesignBrainRequest``/``DesignBrainExecution`` contracts.

V2 is the authoritative default composition.  The legacy implementation is
available only through the explicit rollback binding, and must not shape V2
inputs, results, publication, display, or Apply semantics.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Mapping

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
    build_authoritative_design_result,
    stable_authority_hash,
)
from application.design_brain_port import DesignBrainExecution, DesignBrainRequest
from application.v2_source_manifest import source_manifest_hash


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
) -> int:
    bars = _integer(mapping, *keys, default=default)
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


def _resolved_actions(snapshot: EngineeringInputSnapshot) -> dict[str, Any]:
    actions = _mapping(snapshot.design_actions)
    resolved = _mapping(actions.get("resolved"))
    return resolved or actions


def _merge_primary(primary: Mapping[str, Any], fallback: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    merged.update(primary)
    return merged


def _v2_api():
    """Load the installed V2 distribution at the single composition boundary."""

    from inputs_v2.application.design_guide_orchestrator import (  # noqa: PLC0415
        DesignGuideOrchestrator,
    )
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
    from inputs_v2.application.engineering_advice import (  # noqa: PLC0415
        EngineeringAdviceResult,
        EngineeringCheck,
        clause_reference,
        effects_for_changes,
        format_engineering_advice,
        verified_changes,
    )
    from inputs_v2.presentation.view_models.design_brain_card import (  # noqa: PLC0415
        build_design_brain_card_view_model,
    )

    return {
        "DesignGuideOrchestrator": DesignGuideOrchestrator,
        "CalculationCoordinator": CalculationCoordinator,
        "EngineeringCalculator": EngineeringCalculator,
        "ActionInputs": ActionInputs,
        "BeamInputs": BeamInputs,
        "DeflectionInputs": DeflectionInputs,
        "LayoutMode": LayoutMode,
        "LongitudinalReinforcement": LongitudinalReinforcement,
        "MaterialInputs": MaterialInputs,
        "ServiceabilityInputs": ServiceabilityInputs,
        "ShearReinforcement": ShearReinforcement,
        "SupportInputs": SupportInputs,
        "TimeDependentInputs": TimeDependentInputs,
        "VoidInputs": VoidInputs,
        "evaluate_arrangement": evaluate_arrangement,
        "clause_reference": clause_reference,
        "EngineeringAdviceResult": EngineeringAdviceResult,
        "EngineeringCheck": EngineeringCheck,
        "effects_for_changes": effects_for_changes,
        "format_engineering_advice": format_engineering_advice,
        "verified_changes": verified_changes,
        "build_design_brain_card_view_model": build_design_brain_card_view_model,
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

    span_mm = _number(geometry, "L", "span_mm", default=2000.0)
    if "L" not in geometry and "span_mm" not in geometry and geometry.get("span_m") is not None:
        span_mm = _number(geometry, "span_m", default=2.0) * 1000.0

    bottom_bars = _v2_longitudinal_bar_count(
        reinforcement,
        "bot_row_1_bars",
        "bot1_count",
        "bot1_bars",
        default=3,
    )
    bottom_diameter = _v2_longitudinal_diameter(
        reinforcement,
        "bot_row_1_dia",
        "db_bot_1",
        "db_bot",
        default=10,
    )
    bottom_cover = _v2_longitudinal_cover(reinforcement, "cover_bot")
    top = api["LongitudinalReinforcement"](
        mode=api["LayoutMode"].COUNT,
        bars=_v2_longitudinal_bar_count(
            reinforcement,
            "top_bars",
            "top_row_1_bars",
            default=2,
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
    shear = api["ShearReinforcement"](
        diameter_mm=_integer(reinforcement, "lig_d", default=0),
        legs=_integer(reinforcement, "lig_legs", default=0),
        spacing_mm=_number(reinforcement, "s_lig", default=200.0),
    )
    v2_inputs = api["BeamInputs"](
        revision=int(revision),
        width_mm=_number(geometry, "b", "bw", default=250.0),
        depth_mm=_number(geometry, "D", "d", default=300.0),
        span_mm=span_mm,
        section_shape=_normalise_shape(geometry.get("sec_shape")),
        width_locked=_boolean(locks, "optimisation_lock_width", "lock_width", "width_locked"),
        depth_locked=_boolean(locks, "optimisation_lock_depth", "lock_depth", "depth_locked"),
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
        ),
        supports=api["SupportInputs"](
            str(settings.get("left_support") or "Pinned"),
            str(settings.get("right_support") or "Roller"),
        ),
        time_dependent=api["TimeDependentInputs"](
            shrinkage_time_days=_number(resolved, "shrinkage_time_days", default=365.0),
            creep_time_days=_number(resolved, "creep_time_days", default=365.0),
            age_at_loading_days=_number(resolved, "age_at_loading_days", default=28.0),
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
            # A committed V1 snapshot must never turn ULS demand into an
            # implicit SLS demand. Direct V2 fixtures retain their historical
            # fallback for compatibility, while the production adapter opts
            # into explicit-load semantics.
            use_uls_fallback=False,
        ),
    ).validated()

    row_counts = []
    for key in ("bot_row_1_bars", "bot_row_2_bars"):
        value = reinforcement.get(key)
        if value not in (None, "") and int(float(value)) > 0:
            row_counts.append(int(float(value)))
    if not row_counts:
        row_counts = [bottom.bars]
    if sum(row_counts) != bottom.bars:
        row_counts = [bottom.bars]
    fit = api["evaluate_arrangement"](v2_inputs, tuple(row_counts))
    if fit.accepted:
        v2_inputs = replace(v2_inputs, bottom_arrangement=fit.arrangement).validated()
    return v2_inputs, tuple(row_counts), serviceability_loads


def _proposal_updates(proposal: Any, row_counts: tuple[int, ...]) -> dict[str, Any]:
    values = asdict(proposal)
    rows = tuple(row_counts) or (int(values.get("bottom_bars", 0)),)
    updates: dict[str, Any] = {
        "b": values.get("width_mm"),
        "D": values.get("depth_mm"),
        "L": values.get("span_mm"),
        "sec_shape": values.get("section_shape"),
        "bot_row_count": len(rows),
        "bot_row_1_bars": rows[0],
        "bot_row_1_spacing": values.get("bottom_spacing_mm"),
        "bot_row_1_dia": values.get("bottom_diameter_mm"),
        "cover_bot": values.get("bottom_cover_mm"),
        "top_bars": values.get("top_bars"),
        "top_spacing": values.get("top_spacing_mm"),
        "db_top": values.get("top_diameter_mm"),
        "cover_top": values.get("top_cover_mm"),
        "lig_d": values.get("shear_diameter_mm"),
        "lig_legs": values.get("shear_legs"),
        "s_lig": values.get("shear_spacing_mm"),
    }
    if len(rows) > 1:
        updates.update(
            {
                "bot_row_2_bars": rows[1],
                "bot_row_2_spacing": values.get("bottom_spacing_mm"),
                "bot_row_2_dia": values.get("bottom_diameter_mm"),
            }
        )
    return {key: value for key, value in updates.items() if value is not None}


def _resolved_inputs_projection(
    source: Mapping[str, Any] | None,
    current: Any,
) -> dict[str, Any]:
    """Expose the committed V2 model as the neutral current-input projection."""

    resolved = dict(source or {})
    resolved.update(
        {
            "b": current.width_mm,
            "D": current.depth_mm,
            "L": current.span_mm,
            "sec_shape": current.section_shape,
            "fc": current.materials.concrete_strength_mpa,
            "fsy": current.materials.reinforcement_strength_mpa,
            "bot_row_1_bars": current.bottom.bars,
            "bot_row_1_dia": current.bottom.diameter_mm,
            "bot_row_1_spacing": current.bottom.spacing_mm,
            "cover_bot": current.bottom.cover_mm,
            "top_bars": current.top.bars,
            "db_top": current.top.diameter_mm,
            "top_spacing": current.top.spacing_mm,
            "cover_top": current.top.cover_mm,
            "lig_d": current.shear.diameter_mm,
            "lig_legs": current.shear.legs,
            "s_lig": current.shear.spacing_mm,
            "Mu": current.actions.bending_moment_knm,
            "Vu": current.actions.shear_force_kn,
            "Tu": current.actions.torsion_knm,
            "Nu": current.actions.axial_force_kn,
            "defl_limit_ratio": current.deflection.limit_ratio,
            "deflection_support_condition": current.deflection.support_condition,
            "SLS_M": current.serviceability.moment_knm,
            "SLS_V": current.serviceability.shear_kn,
            "g_udl_kNm_per_m": current.serviceability.permanent_udl_knm_per_m,
            "q_udl_kNm_per_m": current.serviceability.imposed_udl_knm_per_m,
            "w_sls_kNm_per_m": current.serviceability.equivalent_udl_knm_per_m,
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


def _calculation_owned_check_metadata(
    calculation: Any,
    check_id: str,
) -> dict[str, Any] | None:
    """Find V2's calculation-owned metadata for one engineering check.

    Clause references must be projected from the calculation result, rather
    than reconstructed in the Runtime adapter.  That keeps the V2 calculation
    the single authority for both the check and its AS 3600 reference.
    """

    for family in getattr(calculation, "families", {}).values():
        if not isinstance(family, Mapping):
            continue
        metadata = family.get("check_metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        reference = metadata.get(check_id)
        if isinstance(reference, Mapping):
            return dict(reference)
    return None


def _clause_metadata(api: Mapping[str, Any], calculation: Any) -> dict[str, Any]:
    checks = (
        "bending_capacity",
        "bending_ductility",
        "shear_strength",
        "short_term_deflection",
        "long_term_deflection",
        "general_crack_control",
        "direct_crack_width",
        "durability_cover",
    )
    references = []
    for check_id in checks:
        reference = api["clause_reference"](
            check_id,
            _calculation_owned_check_metadata(calculation, check_id),
        )
        if reference is not None:
            references.append(asdict(reference))
    return {"standard": "AS 3600", "edition": "2018", "references": references}


def _v2_display_projection(
    *,
    api: Mapping[str, Any],
    current: Any,
    decision: Any,
) -> dict[str, Any]:
    """Serialize V2's own card view model without recreating its decisions."""

    card = api["build_design_brain_card_view_model"](decision, current)
    advice = decision.advice
    return {
        "state_class": card.state_class,
        "badge": card.badge,
        "heading": card.heading,
        "governing_utilisation": card.governing_utilisation,
        "show_apply": card.show_apply,
        "advice_text": api["format_engineering_advice"](advice),
        "changes": [asdict(change) for change in advice.recommended_changes],
        "effects": list(advice.engineering_effects),
        "apply_allowed": bool(advice.apply_allowed),
        "current_failing": any(check.status == "fail" for check in advice.current_checks),
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
        _row(uid="v2_bending_minimum_capacity", title="Minimum design capacity requirement", route_page="bending", action="Code minimum capacity", capacity=f"ϕMu,cap = {_display(bending.get('minimum_capacity_knm'), unit='kNm')}", util="—", status="INFO", informational=True),
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

    summary_packs = {
        "bending": {
            "source": "inputs_v2",
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
    }
    summary_packs["bending"]["rows"] = bending_rows
    summary_packs["shear"]["rows"] = shear_rows
    summary_packs["crack"]["rows"] = crack_rows
    summary_packs["deflection"]["rows"] = deflection_rows
    return summary_packs


def _neutral_publication_projection(
    *,
    family: str,
    reason: str,
    accepted: bool,
    candidate_payload: Mapping[str, Any],
    updates: Mapping[str, Any],
    clause_metadata: Mapping[str, Any],
    source_revision: int,
    source_hash: str,
    v2_display: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the application publication shape without importing V1 types.

    The page renderer consumes the neutral ``AuthoritativeDesignResult`` but
    historically expects a nested final-publication/CTA/display projection.
    Keep that compatibility shape here, at the replacement boundary, so the
    V2 implementation does not leak native objects or force the page to call
    the legacy Design Brain formatter.
    """

    family_id = str(family or "").strip() or "UNKNOWN"
    reason_text = str(reason or "").strip() or "no_design_action"
    v2_display_map = dict(v2_display or {})
    apply_allowed = bool(v2_display_map.get("apply_allowed", accepted))
    update_map = dict(updates or {}) if apply_allowed else {}
    candidate_id = str(candidate_payload.get("candidate_id") or "").strip() or None
    action_type = "apply_resolved_candidate" if apply_allowed and update_map else None
    outcome_state = "ACTION" if action_type else (
        "PASS" if reason_text in {"no_bending_demand", "serviceability_not_failed"}
        else "BLOCKED"
    )
    # The standalone V2 card renders the governing enum identifier verbatim.
    # Preserve that exact answer surface in Runtime instead of title-casing it
    # during neutral publication projection.
    display_title = family_id
    apply_payload = {
        "updates": dict(update_map),
        "resolved_candidate_updates": dict(update_map),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "family": family_id,
        "resolved_candidate_family_tag": family_id,
        "action_type": action_type,
        "resolved_candidate_action_type": action_type,
        "source_input_revision": int(source_revision),
        "source_engineering_hash": source_hash,
        "v2_source_hash": source_hash,
        "review_before_apply": True,
    }
    apply_payload["state_fingerprint"] = stable_authority_hash(
        {"source_revision": source_revision, "source_hash": source_hash, "updates": update_map}
    )
    apply_payload["render_fingerprint"] = stable_authority_hash(
        {"family": family_id, "candidate_id": candidate_id, "updates": update_map}
    )
    cta_model = {
        "enabled": bool(action_type),
        "actionable": bool(action_type),
        "apply_allowed": bool(action_type),
        "label": "Apply recommendation" if action_type else None,
        "action_type": action_type,
        "family": family_id,
        "updates": dict(update_map),
        "source_candidate_id": candidate_id,
        "apply_payload_summary": dict(apply_payload),
        "disabled_reason": None if action_type else reason_text,
        "review_before_apply": True,
        "product_driving": True,
    }
    cta_model["button_contract_hash"] = stable_authority_hash(cta_model)
    v2_state_class = str(v2_display_map.get("state_class") or ("action" if action_type else outcome_state.lower()))
    v2_badge = str(v2_display_map.get("badge") or ("ACTION" if action_type else outcome_state))
    v2_advice_text = str(v2_display_map.get("advice_text") or "")
    v2_heading = str(v2_display_map.get("heading") or family_id)
    v2_governing_utilisation = float(v2_display_map.get("governing_utilisation") or 0.0)
    # The visual badge describes the current engineering state, which may be
    # BLOCKED when the current design fails even though V2 has produced an
    # approved repair candidate.  Publication outcome is the Apply authority:
    # keep it ACTION whenever an actionable candidate exists, otherwise a
    # terminal PASS/BLOCKED state.  Conflating these two states made the card
    # show an enabled Apply button that the canonical executor then rejected.
    publication_outcome_state = "ACTION" if action_type else v2_badge
    display_model = {
        "title": display_title,
        "badge": v2_badge,
        "summary": v2_advice_text or reason_text.replace("_", " "),
        "status": v2_badge,
        "bucket": v2_state_class,
        "colour_state": v2_state_class,
        "card_class": f"inputs-v2-design-guide-item {v2_state_class}",
        "display_state": v2_badge,
        "blocker_explanation": None if action_type else reason_text.replace("_", " "),
        "clause_metadata": dict(clause_metadata),
        "selected_family_id": family_id,
        "v2_state_class": v2_state_class,
        "v2_badge": v2_badge,
        "v2_advice_text": v2_advice_text,
        "v2_heading": v2_heading,
        "v2_governing_utilisation": v2_governing_utilisation,
        "v2_show_apply": bool(v2_display_map.get("show_apply", apply_allowed)),
        "v2_no_design_actions": bool(v2_display_map.get("no_design_actions")),
        "v2_changes": list(v2_display_map.get("changes") or []),
        "v2_apply_allowed": bool(v2_display_map.get("apply_allowed", apply_allowed)),
        "renderer_driving": True,
    }
    display_model["final_card_model_hash"] = stable_authority_hash(display_model)
    item = {
        "title": display_title,
        "title_main": display_title,
        "summary": display_model["summary"],
        "status": publication_outcome_state,
        "outcome_state": publication_outcome_state,
        "family": family_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id,
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "updates": dict(update_map),
        "resolved_candidate_updates": dict(update_map),
        "action_payload": dict(apply_payload),
        "button_contract": dict(cta_model),
    }
    evidence = {
        "published_item_id": candidate_id,
        "selected_family": family_id,
        "publication_reason": reason_text,
        "blocker_reason": None if action_type else reason_text,
        "candidate_search_evidence": {
            "candidate_id": candidate_id,
            "accepted": bool(action_type),
            "source_revision": int(source_revision),
            "source_hash": source_hash,
        },
        "target_band_proof": {"low": 0.85, "high": 1.0},
        "clause_metadata": dict(clause_metadata),
    }
    publication_base = {
        "published_item_id": candidate_id,
        "selected_family": family_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "outcome_state": publication_outcome_state,
        "post_click_design_guide_state": publication_outcome_state,
        "publication_reason": reason_text,
        "blocker_reason": None if action_type else reason_text,
        "source_hash": source_hash,
        "source_revision": int(source_revision),
        "guidance_items": [item],
        "display": dict(display_model),
        "cta": dict(cta_model),
        "evidence": dict(evidence),
        "verifier_payload": {
            "outcome_state": publication_outcome_state,
            "selected_family_id": family_id,
            "published_family_id": family_id,
            "cta_family_id": family_id,
            "candidate_id": candidate_id,
            "source_input_revision": int(source_revision),
            "source_engineering_hash": source_hash,
            "review_before_apply": True,
        },
        "apply_payload": dict(apply_payload),
    }
    publication_hash = stable_authority_hash(publication_base)
    publication = {**publication_base, "publication_hash": publication_hash}
    verifier_payload = {
        **dict(publication_base["verifier_payload"]),
        "publication_hash": publication_hash,
        "final_publication_authority_hash": publication_hash,
    }
    display_model = {**display_model, "publication_hash": publication_hash}
    cta_model = {**cta_model, "publication_hash": publication_hash}
    return {
        "publication": publication,
        "display_model": display_model,
        "cta_model": cta_model,
        "apply_payload": apply_payload,
        "verifier_payload": verifier_payload,
        "publication_hash": publication_hash,
    }


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


class NewDesignBrainAdapter:
    """Adapt the isolated V2 orchestrator to the neutral application port."""

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        # Streamlit can retain a fragment callback while reloading an
        # application module. In that narrow case the callback may carry an
        # equivalent request object created by the previous module instance.
        # Keep the neutral port strict at the service boundary, but accept the
        # same typed request structurally here so a development reload cannot
        # turn a valid widget edit into a Design Brain crash.
        if not isinstance(request, DesignBrainRequest) and not all(
            hasattr(request, field)
            for field in (
                "engineering_snapshot",
                "input_revision",
                "family_hint",
                "resolved_inputs",
                "engineering_calculations",
                "debug_enabled",
            )
        ):
            raise TypeError("request must be a DesignBrainRequest")
        if request.input_revision is None:
            raise ValueError("V2 adapter requires an input revision")
        api = _v2_api()
        v2_source_manifest = source_manifest_hash()
        current, row_counts, serviceability_loads = _beam_inputs_from_snapshot(
            request.engineering_snapshot,
            api,
            int(request.input_revision),
            request.resolved_inputs,
        )
        has_design_actions = any(
            (
                current.actions.bending_moment_knm,
                current.actions.torsion_knm,
                current.actions.shear_force_kn,
                abs(current.actions.axial_force_kn),
            )
        )
        if has_design_actions:
            # This is the exact decision contract consumed by V2's own card.
            # The former Runtime path called ``preview`` and then rebuilt the
            # status/badge/heading independently, which caused card and
            # acceptance differences whenever V2 changed.
            decision = api["DesignGuideOrchestrator"]().decide(current)
            candidate = decision.candidate
            before = decision.current_result
            after = decision.proposed_result or before
            accepted = bool(decision.apply_allowed)
            family = str(decision.family.value)
            reason = str(decision.reason)
            changed_fields = tuple(decision.changed_fields)
            v2_display = _v2_display_projection(
                api=api,
                current=current,
                decision=decision,
            )
        else:
            # V2 deliberately does not run its Design Guide with no actions.
            # It shows a separate waiting card while the ordinary engineering
            # calculation remains available to the summary region.
            candidate = None
            before = api["CalculationCoordinator"](
                api["EngineeringCalculator"]()
            ).calculate_current(current).result
            if before is None:
                raise ValueError("V2 calculation did not produce a current no-load result")
            after = before
            accepted = False
            family = "NO_DESIGN_ACTIONS"
            reason = "no_design_actions"
            changed_fields = ()
            v2_display = {
                "state_class": "empty",
                "badge": "NO LOADS",
                "heading": "Design Brain waiting for actions",
                "governing_utilisation": 0.0,
                "show_apply": False,
                "apply_allowed": False,
                "no_design_actions": True,
                "advice_text": (
                    "No design actions entered. Add loads and the Design Brain "
                    "will check and optimise your beam."
                ),
                "changes": [],
                "effects": [],
                "current_failing": False,
            }
        # V2 deliberately leaves ``row_counts`` empty for candidates whose
        # authoritative proposal changes only the total bottom-bar count
        # (for example the shear-failure ladder).  Passing the current input
        # rows as a fallback changes the displayed V2 proposal back to the
        # old count at the Runtime Apply boundary.  Let _proposal_updates
        # derive the one-row arrangement from proposal.bottom_bars instead.
        updates = (
            _proposal_updates(candidate.proposal, candidate.row_counts)
            if candidate is not None and accepted
            else {}
        )
        candidate_payload = (
            {
                "candidate_id": candidate.candidate_id,
                "source_revision": candidate.source_revision,
                "source_hash": candidate.source_hash,
                "rationale": candidate.rationale,
                "row_counts": list(candidate.row_counts),
                "proposal": asdict(candidate.proposal),
            }
            if candidate is not None
            else {}
        )
        publication_projection = _neutral_publication_projection(
            family=family,
            reason=reason,
            accepted=accepted,
            candidate_payload=candidate_payload,
            updates=updates,
            clause_metadata=_clause_metadata(api, before),
            source_revision=int(request.input_revision),
            source_hash=request.engineering_snapshot.engineering_hash,
            v2_display=v2_display,
        )
        # The neutral result contract carries the canonical publication in the
        # same envelope as the legacy path.  UI/store consumers intentionally
        # read ``final_design_guide_publication`` from that envelope; exposing
        # only the V2 publication body here makes a valid ready job look like
        # an empty Design Guide (and consequently hides its Apply CTA).
        publication_body = {
            **publication_projection["publication"],
            "source": "inputs_v2",
            "v2_source_revision": before.source_revision,
            "v2_source_manifest_hash": v2_source_manifest,
            "final_publication_verifier_payload": publication_projection["verifier_payload"],
            "final_publication_authority_hash": publication_projection["publication_hash"],
            "final_publication_display_hash": publication_projection["display_model"].get(
                "final_card_model_hash"
            ),
            "final_publication_cta_hash": publication_projection["cta_model"].get(
                "button_contract_hash"
            ),
        }
        canonical_publication = {
            # Compatibility aliases keep diagnostics and non-rendering stores
            # able to inspect the publication without knowing its nested UI
            # shape.  Renderers still consume the canonical nested body below.
            "selected_family": publication_body.get("selected_family"),
            "selected_family_id": publication_body.get("selected_family_id"),
            "outcome_state": publication_body.get("outcome_state"),
            "source_revision": publication_body.get("source_revision"),
            "source_hash": publication_body.get("source_hash"),
            "guidance_items": list(publication_body.get("guidance_items") or []),
            "guidance_debug": {
                "source": "inputs_v2",
                "family_contract_version": "inputs_v2.family.v1",
                "selected_family_id": family,
            },
            "recommendation_result": {
                "source": "inputs_v2",
                "family": family,
                "accepted": accepted,
            },
            "final_design_guide_publication": publication_body,
            "final_publication_verifier_payload": publication_projection["verifier_payload"],
            "final_publication_publication_hash": publication_projection["publication_hash"],
            "final_publication_authority_hash": publication_projection["publication_hash"],
            "publication_hash": publication_projection["publication_hash"],
            "authoritative_publication_source": "inputs_v2",
            "authoritative_publication_evidence": dict(publication_body.get("evidence") or {}),
        }
        # Design Brain owns the recommendation/publication fields and V2 now
        # also publishes the revision-matched summary packs.  The Runtime
        # renderer can consume those packs without rebuilding legacy checks.
        current_calculations = {
            **dict(request.engineering_calculations or {}),
            "source": "inputs_v2",
            "actions_used": _actions_used_projection(current),
            "resolved_inputs": _resolved_inputs_projection(
                request.resolved_inputs,
                current,
            ),
            "v2_source_manifest_hash": v2_source_manifest,
            "v2_source_revision": before.source_revision,
            "v2_source_hash": before.source_hash,
            "v2_status": before.status,
            "v2_summary": before.summary,
            "families": dict(before.families),
            "packs": _v2_summary_packs(
                current=current,
                families=before.families,
            ),
            # Batch Design is a consumer of the V2 proposal, not a second
            # calculator.  Publish the already-verified post-proposal packs
            # beside the current packs so batch rows can report the exact
            # result V2 selected, without re-deriving a candidate in Runtime.
            "proposed_packs": _v2_summary_packs(
                current=current,
                families=after.families,
            ),
            "serviceability_loads": serviceability_loads,
            "proposed_families": dict(after.families),
        }
        result = build_authoritative_design_result(
            engineering_snapshot=request.engineering_snapshot,
            current_calculations=current_calculations,
            governing_family=family,
            family_contract_version="inputs_v2.family.v1",
            family_outcome=reason,
            selected_candidate=candidate_payload if accepted else None,
            selected_candidate_absence=None if accepted else {
                "reason": reason,
                "candidate_id": candidate_payload.get("candidate_id"),
            },
            selected_updates=updates if accepted else {},
            candidate_evaluation={
                "accepted": accepted,
                "changed_fields": list(changed_fields),
                "target_low": 0.85,
                "target_high": 1.0,
                "before": dict(before.families),
                "after": dict(after.families),
            },
            candidate_acceptance_proof={
                "source_revision_matches": candidate is None or candidate.source_revision == current.revision,
                "source_hash_matches": candidate is None or candidate.source_hash == current.content_hash,
                "v2_source_manifest_hash": v2_source_manifest,
                "reinforcement_fit": dict(after.families.get("reinforcement_fit", {})),
                "review_before_apply": True,
            },
            blocker_or_exhaustion_proof={
                "reason": reason,
                "accepted": accepted,
                "family": family,
                "v2_source_manifest_hash": v2_source_manifest,
            },
            final_publication=canonical_publication,
            display_model=publication_projection["display_model"],
            cta_model=publication_projection["cta_model"],
            apply_payload=publication_projection["apply_payload"],
        )
        return DesignBrainExecution(
            result=result,
            stage_trace=("v2.input_mapping", "v2.family_classification", "v2.candidate_preview", "v2.neutral_projection"),
            pipeline_applied=True,
            bypass_reason=None if accepted else reason,
            input_revision=int(request.input_revision),
        )


__all__ = [
    "NewDesignBrainAdapter",
    "calculate_v2_authoritative_result",
]
