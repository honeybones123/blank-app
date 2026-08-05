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
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
    build_authoritative_design_result,
    stable_authority_hash,
)
from application.design_brain_port import DesignBrainExecution, DesignBrainRequest
from application.v2_source_manifest import source_manifest_hash


V2_SOURCE_ROOT_ENV = "INPUTS_V2_SOURCE_ROOT"
DEFAULT_V2_SOURCE_ROOT = Path(
    r"C:\Users\jonathon\Documents\Codex\2026-08-03\why\work\inputs-v2-lab"
)


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


def _v2_api(source_root: Path):
    """Load V2 modules lazily at the single composition boundary."""

    src_root = source_root / "src"
    if not src_root.is_dir():
        raise FileNotFoundError(f"V2 source directory does not exist: {src_root}")
    src_text = str(src_root.resolve())
    if src_text not in sys.path:
        sys.path.insert(0, src_text)

    from inputs_v2.application.design_guide_orchestrator import (  # noqa: PLC0415
        DesignGuideOrchestrator,
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

    return {
        "DesignGuideOrchestrator": DesignGuideOrchestrator,
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

    bottom_bars = _integer(
        reinforcement,
        "bot_row_1_bars",
        "bot1_count",
        "bot1_bars",
        default=3,
    )
    bottom_diameter = _integer(
        reinforcement,
        "bot_row_1_dia",
        "db_bot_1",
        "db_bot",
        default=10,
    )
    bottom_spacing = _number(
        reinforcement,
        "bot_row_1_spacing",
        "bot1_spacing",
        default=150.0,
    )
    bottom_cover = _number(reinforcement, "cover_bot", default=40.0)
    top = api["LongitudinalReinforcement"](
        mode=api["LayoutMode"].COUNT,
        bars=_integer(reinforcement, "top_bars", "top_row_1_bars", default=2),
        spacing_mm=_number(reinforcement, "top_spacing", "top_row_1_spacing", default=150.0),
        diameter_mm=_integer(reinforcement, "db_top", "top_dia", default=10),
        cover_mm=_number(reinforcement, "cover_top", default=40.0),
    )
    bottom = api["LongitudinalReinforcement"](
        mode=api["LayoutMode"].COUNT,
        bars=max(2, bottom_bars),
        spacing_mm=bottom_spacing,
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
            _number(settings, "defl_limit_ratio", default=250.0),
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
            "SLS_M": current.serviceability.moment_knm,
            "SLS_V": current.serviceability.shear_kn,
            "g_udl_kNm_per_m": current.serviceability.permanent_udl_knm_per_m,
            "q_udl_kNm_per_m": current.serviceability.imposed_udl_knm_per_m,
            "w_sls_kNm_per_m": current.serviceability.equivalent_udl_knm_per_m,
        }
    )
    return resolved


def _clause_metadata(api: Mapping[str, Any]) -> dict[str, Any]:
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
        reference = api["clause_reference"](check_id)
        if reference is not None:
            references.append(asdict(reference))
    return {"standard": "AS 3600", "edition": "2018", "references": references}


def _v2_display_projection(
    *,
    api: Mapping[str, Any],
    current: Any,
    decision: Any,
    candidate: Any,
) -> dict[str, Any]:
    """Project the V2 lab's exact Design Guide state into neutral data.

    The V2 lab computes its card state from the current checks, governing
    family, candidate preview, and verified changes.  Repeating that decision
    here would create a second Design Brain, so this function calls the V2
    advice contracts and only serialises their result for the Runtime UI.
    """

    preview = decision.preview
    before = preview.before
    after = preview.after
    family_name = str(decision.family.value)
    current_b = float(before.families.get("bending", {}).get("util", 0.0) or 0.0)
    current_shear = before.families.get("shear", {})
    current_shear_cap = float(current_shear.get("phi_Vu", 0.0) or 0.0)
    current_s = (
        abs(float(current.actions.shear_force_kn)) / current_shear_cap
        if current_shear_cap > 0
        else 0.0
    )
    current_d = float(
        before.families.get("serviceability", {}).get("deflection_util", 0.0) or 0.0
    )
    current_failing = current_b > 1.0 or current_s > 1.0 or current_d > 1.0
    all_checks_pass = all(
        float(values.get("util", values.get("deflection_util", 0.0)) or 0.0) <= 1.0
        for values in after.families.values()
        if isinstance(values, dict)
    )
    changes = tuple(
        api["verified_changes"](current, candidate.proposal, candidate.row_counts)
    )
    effects = tuple(api["effects_for_changes"](changes))
    if not effects and current.bottom.bars <= 2:
        effects = (
            "Further bending optimisation is blocked because the bottom reinforcement is already at the minimum required.",
        )
    proposed_b = float(after.families.get("bending", {}).get("util", 0.0) or 0.0)
    proposed_shear = after.families.get("shear", {})
    proposed_shear_cap = float(proposed_shear.get("phi_Vu", 0.0) or 0.0)
    proposed_s = (
        abs(float(current.actions.shear_force_kn)) / proposed_shear_cap
        if proposed_shear_cap > 0
        else 0.0
    )
    proposed_d = float(
        after.families.get("serviceability", {}).get("deflection_util", 0.0) or 0.0
    )
    check = api["EngineeringCheck"]
    clause = api["clause_reference"]
    advice = api["EngineeringAdviceResult"](
        current_checks=(
            check("bending_capacity", "Bending", clause_reference=clause("bending_capacity"), status="fail" if current_b > 1 else "pass", utilisation=current_b),
            check("shear_strength", "Shear", clause_reference=clause("shear_strength"), status="fail" if current_s > 1 else "pass", utilisation=current_s),
            check("short_term_deflection", "Deflection", clause_reference=clause("short_term_deflection"), status="fail" if current_d > 1 else "pass", utilisation=current_d),
        ),
        proposed_checks=(
            check("bending_capacity", "Bending", clause_reference=clause("bending_capacity"), status="fail" if proposed_b > 1 else "pass", utilisation=proposed_b),
            check("shear_strength", "Shear", clause_reference=clause("shear_strength"), status="fail" if proposed_s > 1 else "pass", utilisation=proposed_s),
            check("short_term_deflection", "Deflection", clause_reference=clause("short_term_deflection"), status="fail" if proposed_d > 1 else "pass", utilisation=proposed_d),
        ),
        recommended_changes=changes,
        engineering_effects=effects,
        governing_check=family_name,
        clause_references=("AS 3600 2018 Clauses 8.1.3, 8.2.3.1, 8.5.3.1",),
        verified_compliance=bool(preview.accepted),
        apply_allowed=(family_name != "TARGET_BAND_REACHED")
        and bool(preview.accepted)
        and bool(changes),
        blocked_reason=None if preview.accepted else str(preview.reason),
        outcome_type=family_name,
    )
    if current_failing:
        state_class, badge = "fail", "BLOCKED"
    elif (
        family_name == "TARGET_BAND_REACHED"
        and all_checks_pass
        and str(preview.reason)
        in {"no_improving_shear_cleanup", "no_safe_shear_cleanup", "no_improving_bending_cleanup"}
    ):
        state_class, badge = "pass", "PASS"
    elif family_name in {
        "BENDING_OVERDESIGN_GOVERNS",
        "SHEAR_OVERDESIGN_GOVERNS",
        "COMBINED_OVERDESIGN",
    }:
        state_class, badge = "optimise", "ACTION"
    elif preview.accepted or family_name in {"TARGET_BAND_REACHED", "EXACT_STOP_PROVEN"}:
        state_class, badge = "pass", "PASS"
    elif family_name in {
        "BENDING_FAIL_GOVERNS",
        "SHEAR_FAIL_GOVERNS",
        "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS",
        "BENDING_AND_SHEAR_FAIL_GOVERN",
        "GEOMETRY_DETAILING_GOVERNS",
        "SERVICEABILITY_GOVERNS",
        "LOCKED_NO_REPAIR",
    }:
        state_class, badge = "fail", "BLOCKED" if not preview.accepted else "ACTION"
    else:
        state_class, badge = "info", "INFO"
    return {
        "state_class": state_class,
        "badge": badge,
        "advice_text": api["format_engineering_advice"](advice),
        "changes": [asdict(change) for change in changes],
        "effects": list(effects),
        "apply_allowed": bool(advice.apply_allowed),
        "current_failing": current_failing,
    }


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
    title_family = family_id.replace("_", " ").title()
    # V2 renders the governing family as the card title; the advice text
    # carries the proposed change and result details.
    display_title = title_family
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
    outcome_state = v2_badge
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
        "v2_changes": list(v2_display_map.get("changes") or []),
        "v2_apply_allowed": bool(v2_display_map.get("apply_allowed", apply_allowed)),
        "renderer_driving": True,
    }
    display_model["final_card_model_hash"] = stable_authority_hash(display_model)
    item = {
        "title": display_title,
        "title_main": display_title,
        "summary": display_model["summary"],
        "status": outcome_state,
        "outcome_state": outcome_state,
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
        "outcome_state": outcome_state,
        "post_click_design_guide_state": outcome_state,
        "publication_reason": reason_text,
        "blocker_reason": None if action_type else reason_text,
        "source_hash": source_hash,
        "source_revision": int(source_revision),
        "guidance_items": [item],
        "display": dict(display_model),
        "cta": dict(cta_model),
        "evidence": dict(evidence),
        "verifier_payload": {
            "outcome_state": outcome_state,
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


class NewDesignBrainAdapter:
    """Adapt the isolated V2 orchestrator to the neutral application port."""

    def __init__(self, *, source_root: Path | str | None = None) -> None:
        configured = source_root or os.environ.get(V2_SOURCE_ROOT_ENV)
        self._source_root = Path(configured) if configured else DEFAULT_V2_SOURCE_ROOT

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        if not isinstance(request, DesignBrainRequest):
            raise TypeError("request must be a DesignBrainRequest")
        if request.input_revision is None:
            raise ValueError("V2 adapter requires an input revision")
        api = _v2_api(self._source_root)
        v2_source_manifest = source_manifest_hash(self._source_root)
        current, row_counts, serviceability_loads = _beam_inputs_from_snapshot(
            request.engineering_snapshot,
            api,
            int(request.input_revision),
            request.resolved_inputs,
        )
        decision = api["DesignGuideOrchestrator"]().preview(current)
        preview = decision.preview
        candidate = preview.candidate
        accepted = bool(preview.accepted)
        updates = _proposal_updates(candidate.proposal, candidate.row_counts or row_counts)
        candidate_payload = {
            "candidate_id": candidate.candidate_id,
            "source_revision": candidate.source_revision,
            "source_hash": candidate.source_hash,
            "rationale": candidate.rationale,
            "row_counts": list(candidate.row_counts),
            "proposal": asdict(candidate.proposal),
        }
        v2_display = _v2_display_projection(
            api=api,
            current=current,
            decision=decision,
            candidate=candidate,
        )
        publication_projection = _neutral_publication_projection(
            family=str(decision.family.value),
            reason=str(preview.reason),
            accepted=accepted,
            candidate_payload=candidate_payload,
            updates=updates,
            clause_metadata=_clause_metadata(api),
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
            "v2_source_revision": preview.before.source_revision,
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
                "selected_family_id": str(decision.family.value),
            },
            "recommendation_result": {
                "source": "inputs_v2",
                "family": str(decision.family.value),
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
        result = build_authoritative_design_result(
            engineering_snapshot=request.engineering_snapshot,
            current_calculations={
                "source": "inputs_v2",
                "resolved_inputs": _resolved_inputs_projection(
                    request.resolved_inputs,
                    current,
                ),
                "v2_source_manifest_hash": v2_source_manifest,
                "v2_source_revision": preview.before.source_revision,
                "v2_source_hash": preview.before.source_hash,
                "v2_status": preview.before.status,
                "v2_summary": preview.before.summary,
                "families": dict(preview.before.families),
                "serviceability_loads": serviceability_loads,
                "proposed_families": dict(preview.after.families),
            },
            governing_family=str(decision.family.value),
            family_contract_version="inputs_v2.family.v1",
            family_outcome=str(preview.reason),
            selected_candidate=candidate_payload if accepted else None,
            selected_candidate_absence=None if accepted else {
                "reason": str(preview.reason),
                "candidate_id": candidate.candidate_id,
            },
            selected_updates=updates if accepted else {},
            candidate_evaluation={
                "accepted": accepted,
                "changed_fields": list(preview.changed_fields),
                "target_low": preview.target_low,
                "target_high": preview.target_high,
                "before": dict(preview.before.families),
                "after": dict(preview.after.families),
            },
            candidate_acceptance_proof={
                "source_revision_matches": candidate.source_revision == current.revision,
                "source_hash_matches": candidate.source_hash == current.content_hash,
                "v2_source_manifest_hash": v2_source_manifest,
                "reinforcement_fit": dict(preview.after.families.get("reinforcement_fit", {})),
                "review_before_apply": True,
            },
            blocker_or_exhaustion_proof={
                "reason": str(preview.reason),
                "accepted": accepted,
                "family": str(decision.family.value),
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
            bypass_reason=None if accepted else str(preview.reason),
            input_revision=int(request.input_revision),
        )


__all__ = ["DEFAULT_V2_SOURCE_ROOT", "NewDesignBrainAdapter", "V2_SOURCE_ROOT_ENV"]
