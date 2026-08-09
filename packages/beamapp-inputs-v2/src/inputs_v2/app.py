"""Standalone Streamlit entry point for the isolated Inputs V2 proof."""

from __future__ import annotations

import sys
import json
from dataclasses import replace
from pathlib import Path

# The standalone Streamlit entry point is launched from the lab root. Add only
# this lab's own source directory so the app never needs the live Runtime path.
_SRC_ROOT = Path(__file__).resolve().parents[1]
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import streamlit as st

from inputs_v2.application.input_commands import UpdateFirstSlice, apply_input_command
from inputs_v2.application.calculation_coordinator import calculate_fixture_current, calculate_legacy_shadow_current
from inputs_v2.application.lab_services import BeamInputsRepository, export_fixture_report, new_json_repository, new_memory_repository
from inputs_v2.domain.beam_inputs import ALLOWED_BAR_DIAMETERS, BeamInputs, LayoutMode, ShearReinforcement
from inputs_v2.application.report_exports import request_for_current
from inputs_v2.application.design_brain_service import DesignBrainService
from inputs_v2.application.engineering_advice import format_engineering_advice
from inputs_v2.presentation.view_models.design_brain_card import build_design_brain_card_view_model
from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
from inputs_v2.application.design_brain.search_profile import SearchProfile
from inputs_v2.application.rollout import shadow_results_enabled
from inputs_v2.application.batch_design import BatchBeam, calculate_fixture_batch
from inputs_v2.presentation.components.diagram_panel import build_3d_figure, build_section_figure
from inputs_v2.presentation.foundations import scoped_css
from inputs_v2.presentation.view_models.input_diagram import build_input_diagram_view_model


MODEL_KEY = "inputs_v2_beam_inputs"
ERROR_KEY = "inputs_v2_validation_error"
REPOSITORY_KEY = "inputs_v2_repository"
BEAM_ID = "v2-lab-beam"


def _calculate_fixture(inputs: BeamInputs):
    """Keep presentation dependent on the application calculation boundary."""
    return calculate_legacy_shadow_current(inputs) if shadow_results_enabled() else calculate_fixture_current(inputs)


def build_snapshot_payload(beam_id: str, inputs: BeamInputs) -> dict[str, object]:
    """Build the revision-tagged, canonical JSON export payload."""
    return {
        "schema": "inputs_v2.beam_inputs.v1",
        "beam_id": beam_id,
        "revision": inputs.revision,
        "content_hash": inputs.content_hash,
        "inputs": inputs.canonical_payload,
    }


def _model() -> BeamInputs:
    value = st.session_state.get(MODEL_KEY)
    if isinstance(value, BeamInputs):
        # Streamlit can retain an object from a previous code revision during
        # hot reload. Rebuild it through the canonical model when new fields
        # have been added, rather than allowing stale session state to crash
        # the page.
        if not hasattr(value, "span_mm"):
            value = BeamInputs(
                revision=value.revision,
                width_mm=value.width_mm,
                depth_mm=value.depth_mm,
                span_mm=2000.0,
                bottom=value.bottom,
                top=value.top,
                shear=value.shear,
                materials=value.materials,
                actions=value.actions,
                supports=value.supports,
            ).validated()
            st.session_state[MODEL_KEY] = value
        elif value.revision == 0 and value.shear.diameter_mm == 10 and value.shear.legs == 2:
            # Migrate the disposable lab's earlier defaults to the Runtime
            # contract's explicit shear-off initial state.
            value = replace(value, shear=ShearReinforcement(0, 0, value.shear.spacing_mm)).validated()
            st.session_state[MODEL_KEY] = value
        elif (
            value.revision == 0
            and value.width_mm == 400.0
            and value.depth_mm == 600.0
            and value.bottom.bars == 5
            and value.bottom.diameter_mm == 20
        ):
            # Migrate the earlier disposable scaffold defaults to the V1
            # reference defaults. This is intentionally limited to revision
            # zero so an edited design can never be silently overwritten.
            value = BeamInputs().validated()
            st.session_state[MODEL_KEY] = value
        return value
    value = BeamInputs().validated()
    st.session_state[MODEL_KEY] = value
    return value


def _repository() -> BeamInputsRepository:
    repository = st.session_state.get(REPOSITORY_KEY)
    if repository is None or not all(hasattr(repository, method) for method in ("save", "load")):
        repository = new_memory_repository()
        st.session_state[REPOSITORY_KEY] = repository
    return repository


def _file_repository():
    root = _SRC_ROOT.parent / "outputs" / "v2-projects"
    return new_json_repository(root)


def _seed_widgets(inputs: BeamInputs) -> None:
    defaults = {
        "v2_width_mm": inputs.width_mm,
        "v2_depth_mm": inputs.depth_mm,
        "v2_span_mm": getattr(inputs, "span_mm", 2000.0),
        "v2_section_shape": inputs.section_shape,
        "v2_bottom_mode": inputs.bottom.mode.value,
        "v2_bottom_bars": inputs.bottom.bars,
        "v2_bottom_spacing_mm": inputs.bottom.spacing_mm,
        "v2_bottom_diameter_mm": inputs.bottom.diameter_mm,
        "v2_bottom_cover_mm": inputs.bottom.cover_mm,
        "v2_top_mode": inputs.top.mode.value,
        "v2_top_bars": inputs.top.bars,
        "v2_top_spacing_mm": inputs.top.spacing_mm,
        "v2_top_diameter_mm": inputs.top.diameter_mm,
        "v2_top_cover_mm": inputs.top.cover_mm,
        "v2_shear_diameter_mm": inputs.shear.diameter_mm,
        "v2_shear_legs": inputs.shear.legs,
        "v2_shear_spacing_mm": inputs.shear.spacing_mm,
        "v2_concrete_strength": inputs.materials.concrete_strength_mpa,
        "v2_reinforcement_strength": inputs.materials.reinforcement_strength_mpa,
        "v2_bending_moment": inputs.actions.bending_moment_knm,
        "v2_torsion": inputs.actions.torsion_knm,
        "v2_shear_force": inputs.actions.shear_force_kn,
        "v2_axial_force": inputs.actions.axial_force_kn,
        "v2_left_support": inputs.supports.left_type,
        "v2_right_support": inputs.supports.right_type,
        "v2_shrinkage_time_days": inputs.time_dependent.shrinkage_time_days,
        "v2_creep_time_days": inputs.time_dependent.creep_time_days,
        "v2_age_at_loading_days": inputs.time_dependent.age_at_loading_days,
        "v2_duct_count": inputs.voids.ducts,
        "v2_duct_diameter_mm": inputs.voids.diameter_mm,
        "v2_deflection_support": inputs.deflection.support_condition,
        "v2_deflection_limit_ratio": inputs.deflection.limit_ratio,
        "v2_width_locked": inputs.width_locked,
        "v2_depth_locked": inputs.depth_locked,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _commit_widgets() -> None:
    current = _model()
    shear_diameter = int(st.session_state["v2_shear_diameter_mm"])
    shear_legs = int(st.session_state["v2_shear_legs"])
    # Keep the two shear controls editable in either order. Turning either
    # control off atomically turns off the complete link definition.
    if shear_diameter > 0 and shear_legs == 0:
        shear_legs = 2
        st.session_state["v2_shear_legs"] = 2
    elif shear_diameter == 0 or shear_legs == 0:
        shear_diameter, shear_legs = 0, 0
        st.session_state["v2_shear_diameter_mm"] = 0
        st.session_state["v2_shear_legs"] = 0
    command = UpdateFirstSlice(
        width_mm=float(st.session_state["v2_width_mm"]),
        depth_mm=float(st.session_state["v2_depth_mm"]),
        span_mm=float(st.session_state["v2_span_mm"]),
        section_shape=str(st.session_state["v2_section_shape"]),
        width_locked=bool(st.session_state["v2_width_locked"]),
        depth_locked=bool(st.session_state["v2_depth_locked"]),
        bottom_mode=LayoutMode(st.session_state["v2_bottom_mode"]),
        bottom_bars=int(st.session_state["v2_bottom_bars"]),
        bottom_spacing_mm=float(st.session_state["v2_bottom_spacing_mm"]),
        bottom_diameter_mm=int(st.session_state["v2_bottom_diameter_mm"]),
        bottom_cover_mm=float(st.session_state["v2_bottom_cover_mm"]),
        top_mode=LayoutMode(st.session_state["v2_top_mode"]),
        top_bars=int(st.session_state["v2_top_bars"]),
        top_spacing_mm=float(st.session_state["v2_top_spacing_mm"]),
        top_diameter_mm=int(st.session_state["v2_top_diameter_mm"]),
        top_cover_mm=float(st.session_state["v2_top_cover_mm"]),
        shear_diameter_mm=shear_diameter,
        shear_legs=shear_legs,
        shear_spacing_mm=float(st.session_state["v2_shear_spacing_mm"]),
        concrete_strength_mpa=float(st.session_state["v2_concrete_strength"]),
        reinforcement_strength_mpa=float(st.session_state["v2_reinforcement_strength"]),
        bending_moment_knm=float(st.session_state["v2_bending_moment"]),
        torsion_knm=float(st.session_state["v2_torsion"]),
        shear_force_kn=float(st.session_state["v2_shear_force"]),
        axial_force_kn=float(st.session_state["v2_axial_force"]),
        left_support=str(st.session_state["v2_left_support"]),
        right_support=str(st.session_state["v2_right_support"]),
        shrinkage_time_days=float(st.session_state["v2_shrinkage_time_days"]),
        creep_time_days=float(st.session_state["v2_creep_time_days"]),
        age_at_loading_days=float(st.session_state["v2_age_at_loading_days"]),
        duct_count=int(st.session_state["v2_duct_count"]),
        duct_diameter_mm=float(st.session_state["v2_duct_diameter_mm"]),
        deflection_support_condition=str(st.session_state["v2_deflection_support"]),
        deflection_limit_ratio=float(st.session_state["v2_deflection_limit_ratio"]),
    )
    try:
        st.session_state[MODEL_KEY] = apply_input_command(current, command)
        st.session_state[ERROR_KEY] = ""
    except ValueError as exc:
        st.session_state[ERROR_KEY] = str(exc)


def _section_heading(label: str) -> None:
    st.markdown(
        f'<div class="inputs-v2-root"><div class="inputs-v2-card-label">{label}<span class="inputs-v2-section-info">i⌄</span></div></div>',
        unsafe_allow_html=True,
    )


def _compact_select(label: str, options, *, key: str, format_func=None) -> None:
    """Match V1's label/field row rhythm for reinforcement controls."""
    label_col, field_col = st.columns([0.35, 0.65], gap="small")
    label_col.markdown(f'<div class="inputs-v2-root inputs-v2-row-label">{label}</div>', unsafe_allow_html=True)
    field_col.selectbox(label, options, key=key, format_func=format_func or str, label_visibility="collapsed", on_change=_commit_widgets)


def _compact_number(label: str, *, key: str, min_value: float, max_value: float, step: float, help: str = "") -> None:
    label_col, field_col = st.columns([0.35, 0.65], gap="small")
    label_col.markdown(f'<div class="inputs-v2-root inputs-v2-row-label">{label}</div>', unsafe_allow_html=True)
    field_col.number_input(label, min_value=min_value, max_value=max_value, step=step, key=key, label_visibility="collapsed", on_change=_commit_widgets, help=help)


def _render_input_summary(inputs: BeamInputs, shadow_result=None) -> None:
    """Render the Runtime-shaped engineering check cards from V2 values."""
    if shadow_result is None:
        # Keep the summary populated even if an upstream preview calculation
        # failed; the summary owns a read-only calculation fallback.
        try:
            shadow_result = calculate_legacy_shadow_current(inputs)
        except Exception:
            shadow_result = None
    action = float(inputs.actions.bending_moment_knm)
    shear = float(inputs.actions.shear_force_kn)
    bending_family = shadow_result.families.get("bending", {}) if shadow_result is not None else {}
    shear_family = shadow_result.families.get("shear", {}) if shadow_result is not None else {}
    phi_mu = float(bending_family.get("phi_Mu_kNm", 0.0))
    bend_util = float(bending_family.get("util", 0.0))
    phi_vu = float(shear_family.get("phi_Vu", 0.0))
    shear_util = abs(shear) / phi_vu if phi_vu > 0 else 0.0
    crack_family = shadow_result.families.get("crack_control", {}) if shadow_result is not None else {}
    serviceability_family = shadow_result.families.get("serviceability", {}) if shadow_result is not None else {}
    crack_width = float(crack_family.get("width_mm", 0.0) or 0.0)
    crack_limit = float(crack_family.get("limit_mm", 0.30) or 0.30)
    crack_util = float(crack_family.get("util", 0.0) or 0.0)
    deflection_mm = float(serviceability_family.get("deflection_mm", 0.0) or 0.0)
    deflection_limit = float(serviceability_family.get("limit_mm", inputs.span_mm / inputs.deflection.limit_ratio) or 0.0)
    deflection_util = float(serviceability_family.get("deflection_util", 0.0) or 0.0)
    crack_status = str(crack_family.get("status", "NOT RUN")).upper()
    service_status = str(serviceability_family.get("status", "NOT RUN")).upper()
    cards = (
        ("bending", "Bending — ULS check", "Applied design action", f"Mu*(+) = {action:.1f} kNm" if action else "Mu*(+) = —", "Calculated capacity", f"ϕMu(+) = {phi_mu:.1f} kNm", f"{bend_util:.2f}" if action else "—", "INFO" if not action else "PASS" if bend_util <= 1.0 else "FAIL"),
        ("shear", "Shear — ULS check", "Applied design action", f"V*eq = {shear:.1f} kN" if shear else "V*eq = —", "Calculated capacity", f"ϕVu = {phi_vu:.1f} kN" if phi_vu else "ϕVu = —", f"{shear_util:.2f}" if shear else "—", "INFO" if not shear else "PASS" if shear_util <= 1.0 else "FAIL"),
        ("crack", "Crack control — SLS check", "Calculated width", f"w = {crack_width:.3f} mm", "Allowable width", f"w′max = {crack_limit:.3f} mm", f"{crack_util:.2f}" if crack_status != "NOT RUN" else "—", "PASS" if crack_status == "PASS" else "FAIL" if crack_status == "FAIL" else "INFO"),
        ("deflection", "Deflection — SLS check", "Calculated deflection", f"δ = {deflection_mm:.2f} mm", "Allowable deflection", f"δlim = {deflection_limit:.2f} mm (L/{inputs.deflection.limit_ratio:.0f})", f"{deflection_util:.2f}" if service_status != "NOT RUN" else "—", "PASS" if service_status == "PASS" else "FAIL" if service_status == "FAIL" else "INFO"),
    )
    html_parts = []
    for family, title, action_label, action_value, capacity_label, capacity_value, utilisation, status in cards:
        tone = "pass" if status == "PASS" else "fail" if status == "FAIL" else "info"
        family_key = "crack_control" if family == "crack" else "serviceability" if family == "deflection" else family
        family_data = shadow_result.families.get(family_key, {}) if shadow_result is not None else {}
        details_list = [(title, capacity_value, action_value, utilisation, status)]
        # Keep the expanded presentation aligned to the Runtime check rows
        # shown in the reference cards; internal engineering fields stay out.
        allowed = {
            "bending": {"phi_Mu_kNm", "Ast_bot", "Ast_min", "ku", "ku_lim", "service_moment_knm", "minimum_capacity_knm"},
            "shear": {"phi_Vu", "V_eq", "torsion_cracking", "phi_Vu_max", "web_crushing"},
            "crack_control": {"width_mm", "limit_mm", "sigma_sr", "sigma_allow_table", "table_util", "width_util"},
            "serviceability": {"deflection_mm", "limit_mm", "short_term_deflection_mm", "long_term_deflection_mm", "deflection_util"},
        }.get(family_key, set())
        exact_rows = {
            "bending": (("Positive bending", "phi_Mu_kNm", "Mu*(+)"), ("Minimum tensile reinforcement", "Ast_tension_mm2", "As,provided"), ("Ductility limit", "ku", "k_u"), ("Service bending moment", "service_moment_knm", "M_s"), ("Minimum design capacity requirement", "minimum_capacity_knm", "(M_u,cap)_min")),
            "shear": (("Sectional shear capacity", "phi_Vu", "ϕVu"), ("Torsion cracking check", "torsion_cracking", "Reference"), ("Web-crushing strength", "phi_Vu_max", "ϕVu,max")),
            "crack_control": (("Governing outcome", "status", "Result"), ("Table-based crack control check", "sigma_allow_table", "σ_allow"), ("Direct crack width check", "width_mm", "w′max")),
            "serviceability": (("Total deflection (short + long-term)", "deflection_mm", "δtotal"), ("Short-term deflection (total load)", "short_term_deflection_mm", "δshort"), ("Additional long-term deflection", "long_term_deflection_mm", "δlong")),
        }.get(family_key, ())
        for label, key, value_label in exact_rows:
            value = family_data.get(key)
            rendered = "—" if value is None or str(value).upper() == "NOT RUN" else f"{value:.3f}" if isinstance(value, float) else str(value)
            row_status = "INFO" if rendered == "—" else ("FAIL" if key in {"width_mm", "deflection_mm"} and float(value or 0) > float(family_data.get("limit_mm", 1)) else "PASS")
            details_list.append((label, rendered, value_label, "—", row_status))
        details = tuple(details_list)
        rows = ''.join(f'<tr class="check-row-{row_status.lower()}"><td>{name}</td><td>{capacity}</td><td>{applied}</td><td>{util}</td><td>{row_status}</td></tr>' for name, capacity, applied, util, row_status in details)
        html_parts.append(
            f'<div class="inputs-v2-check-card status-{tone}"><details class="inputs-v2-check-details">'
            f'<summary class="inputs-v2-check-main" aria-label="Expand checks">'
            f'<div class="inputs-v2-check-icon">{family[:1].upper()}</div><div class="inputs-v2-check-title">{title}</div>'
            f'<div class="inputs-v2-check-metric"><small>{action_label}</small><b>{action_value}</b></div>'
            f'<div class="inputs-v2-check-metric"><small>{capacity_label}</small><b>{capacity_value}</b></div>'
            f'<div class="inputs-v2-check-metric"><small>Utilisation</small><b>{utilisation}</b></div>'
            f'<div class="inputs-v2-check-status">{status}</div><div class="inputs-v2-check-chevron">⌄</div>'
            f'</summary><div class="inputs-v2-check-table-wrap"><table><thead><tr><th>Check</th><th>Calculated capacity</th><th>Applied design action</th><th>Utilisation</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></details></div>'
        )
    st.markdown('<div class="inputs-v2-root inputs-v2-check-stack">' + ''.join(html_parts) + '</div>', unsafe_allow_html=True)
    if shadow_result is not None and not bool(shadow_result.families.get("serviceability", {}).get("serviceability_loads_present", False)):
        st.caption("Crack control provisionally assessed because SLS actions were not provided.")


def _render_bottom_controls() -> None:
    _section_heading("Bottom Reinforcement")
    _compact_select("Layout", [mode.value for mode in LayoutMode], key="v2_bottom_mode")
    if st.session_state["v2_bottom_mode"] == LayoutMode.COUNT.value:
        _compact_select("Bars", list(range(2, 13)), key="v2_bottom_bars")
    else:
        _compact_select("Spacing (mm)", list(range(50, 501, 25)), key="v2_bottom_spacing_mm")
    _compact_select("Ø (mm)", list(ALLOWED_BAR_DIAMETERS), key="v2_bottom_diameter_mm", format_func=lambda value: f"{value}")
    _compact_number("Bottom cover (mm)", key="v2_bottom_cover_mm", min_value=10.0, max_value=150.0, step=5.0, help="Clear cover to the bottom bars.")


def _render_top_controls() -> None:
    _section_heading("Top Reinforcement")
    _compact_select("Layout", [mode.value for mode in LayoutMode], key="v2_top_mode")
    if st.session_state["v2_top_mode"] == LayoutMode.COUNT.value:
        _compact_select("Bars", list(range(2, 13)), key="v2_top_bars")
    else:
        _compact_select("Spacing (mm)", list(range(50, 501, 25)), key="v2_top_spacing_mm")
    _compact_select("Ø (mm)", list(ALLOWED_BAR_DIAMETERS), key="v2_top_diameter_mm", format_func=lambda value: f"{value}")
    _compact_number("Top cover (mm)", key="v2_top_cover_mm", min_value=10.0, max_value=150.0, step=5.0, help="Clear cover to the top bars.")


def _render_shear_controls() -> None:
    _section_heading("Shear")
    _compact_select("Link dia (mm)", [0, *ALLOWED_BAR_DIAMETERS], key="v2_shear_diameter_mm", format_func=lambda value: "0 (off)" if value == 0 else f"{value}")
    _compact_select("No. of legs", [0, 2, 4, 6, 8], key="v2_shear_legs")
    _compact_number("Link spacing (mm)", key="v2_shear_spacing_mm", min_value=0.0, max_value=1000.0, step=25.0)


def _render_batch_status() -> None:
    """Render the V1 batch-design strip without exposing lab controls."""
    st.subheader("Batch design")
    st.markdown(
        '<div class="inputs-v2-root"><div class="inputs-v2-batch-status">'
        '<span>[&gt;]</span><span><b>B1</b> project beam</span>'
        '<span>OK 0 auto designed</span><span>AS 0 auto assigned</span>'
        '<span>D 0 imported actions</span><span>Ready for setup</span>'
        '<span>Constraints: none</span></div></div>', unsafe_allow_html=True,
    )


def _render_design_guide_fixture() -> None:
    """Render the compact V1 Design Guide landing card as a fixture."""
    st.subheader("Design Guide")
    st.markdown(
        '<div class="inputs-v2-root inputs-v2-guide-card">'
        '<span class="inputs-v2-guide-pass">PASS</span>'
        '<span>Reduce section size and rebalance bottom reinforcement</span>'
        '<span class="inputs-v2-guide-preview">Preview utilisation 1.00 PASS</span>'
        '<span class="inputs-v2-guide-chevron">›</span></div>',
        unsafe_allow_html=True,
    )


def _reset_widget_state_after_apply() -> None:
    for key in tuple(st.session_state.keys()):
        if key.startswith("v2_") and key not in {"v2_design_mode", "v2_design_started"}:
            del st.session_state[key]


def _render_design_brain() -> None:
    """Render the authoritative application decision without reinterpreting it."""
    st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-card-label">Design Brain</div></div>', unsafe_allow_html=True)
    current = _model()
    try:
        decision = DesignGuideOrchestrator(
            SearchProfile.for_mode(st.session_state.get("v2_design_mode", "Fast"))
        ).decide(current)
    except Exception as exc:
        st.error(f"Design Brain unavailable: {exc}")
        return

    card = build_design_brain_card_view_model(decision, current)
    state_class = card.state_class
    advice_text = card.body or format_engineering_advice(decision.advice)
    summary_label = f"**{card.badge}**  **{card.heading}**  |  Governing utilisation: {card.governing_utilisation:.2f}"
    st.markdown(
        f'<span class="inputs-v2-brain-state-{state_class}" aria-hidden="true">{decision.family.value}</span>',
        unsafe_allow_html=True,
    )
    with st.expander(summary_label, expanded=False):
        st.markdown(
            f'<div class="inputs-v2-root inputs-v2-design-guide-copy {state_class}">'
            f'<div>{advice_text.replace(chr(10), "<br>")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="inputs-v2-design-guide-cta-gap"></div>', unsafe_allow_html=True)
    if card.show_apply and st.button("Apply recommendation", key="v2_design_brain_apply", use_container_width=True):
        outcome = DesignBrainService().apply_decision(current, decision)
        if outcome.applied:
            st.session_state[MODEL_KEY] = outcome.inputs
            _reset_widget_state_after_apply()
            st.success("Recommendation applied through the canonical input command.")
            st.rerun()
        else:
            st.error(f"Recommendation rejected: {outcome.reason}")


def _render_detailed_controls() -> None:
    """Render calculation-driving families omitted from Fast mode."""
    st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-card-label">Actions and supports</div></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        _compact_select("Left support", ["Pinned", "Roller", "Fixed"], key="v2_left_support")
    with right:
        _compact_select("Right support", ["Pinned", "Roller", "Fixed"], key="v2_right_support")
    st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-card-label">Deflection and time-dependent inputs</div></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        _compact_select("Deflection support condition", ["Simply supported", "Continuous", "Cantilever", "Fixed-ended"], key="v2_deflection_support")
        _compact_number("Shrinkage time (days)", key="v2_shrinkage_time_days", min_value=0.0, max_value=10000.0, step=1.0)
        _compact_number("Creep time (days)", key="v2_creep_time_days", min_value=0.0, max_value=10000.0, step=1.0)
    with right:
        _compact_select("Deflection limit (L/)", [200.0, 250.0, 300.0, 400.0], key="v2_deflection_limit_ratio", format_func=lambda value: f"L/{int(value)}")
        _compact_number("Age at loading (days)", key="v2_age_at_loading_days", min_value=0.0, max_value=10000.0, step=1.0)
    st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-card-label">Ducts / prestress voids</div></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        _compact_number("Number of ducts crossing web", key="v2_duct_count", min_value=0, max_value=100, step=1)
    with right:
        _compact_number("Duct diameter (mm)", key="v2_duct_diameter_mm", min_value=0.0, max_value=1000.0, step=1.0)


def render() -> None:
    st.set_page_config(page_title="Beamapp Inputs V2 Lab", layout="wide")
    st.markdown(scoped_css(), unsafe_allow_html=True)
    st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-kicker">Project: Unsaved / New project</div></div>', unsafe_allow_html=True)
    header_left, header_right = st.columns([1.35, 1.0])
    with header_left:
        st.title("Beam design")
    with header_right:
        save_col, report_col = st.columns(2)
        if save_col.button("💾 Save", use_container_width=True):
            current = _model()
            _repository().save(BEAM_ID, current)
            st.session_state["v2_save_status"] = f"Saved revision {current.revision}"
        if report_col.button("📄 PDF Report", use_container_width=True):
            # The artifact is published below once the current revision has
            # been calculated; the header action remains presentation-only.
            st.session_state["v2_report_requested"] = True
        saved = _repository().load(BEAM_ID)
        if saved is not None and st.button("Load saved", key="v2_load_saved"):
            st.session_state[MODEL_KEY] = saved
            st.session_state["v2_save_status"] = f"Loaded revision {saved.revision}"
            st.rerun()
        if st.session_state.get("v2_save_status"):
            st.caption(st.session_state["v2_save_status"])
    st.markdown(
        '<div class="inputs-v2-root inputs-v2-nav">'
        '<span class="inputs-v2-nav-active">Inputs</span><span>Design</span>'
        '<span>Bending</span><span>Shear</span><span>Creep</span>'
        '<span>Shrinkage</span><span>Crack Control</span><span>Deflection</span>'
        '</div>', unsafe_allow_html=True,
    )
    st.title("Inputs")
    inputs = _model()

    st.session_state.setdefault("v2_design_started", False)
    # Match the current page's first-run landing state. Presentation-only
    # navigation is separate from the canonical BeamInputs model.
    if not st.session_state.get("v2_design_started", False):
        st.markdown(
            '<div class="inputs-v2-root"><div class="inputs-v2-landing"><div class="inputs-v2-landing-title">Start Your Design</div>'
            '<div>This tool requires design actions or applied loads to begin.</div>'
            '<div class="inputs-v2-landing-label">You can:</div>'
            '<ul><li>Enter design actions (M*, V*, sigma)</li>'
            '<li>Use the Design Mode to generate loads automatically</li></ul></div></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="inputs-v2-landing-actions"):
            start_a, start_b = st.columns(2)
            if start_a.button("Go to Design Inputs", use_container_width=True):
                st.session_state["v2_design_started"] = True
                st.rerun()
            start_b.button("Open Design Mode", disabled=True, use_container_width=True)
        _render_batch_status()
        if st.session_state.pop("v2_report_requested", False):
            report_result = _calculate_fixture(inputs)
            if report_result is not None:
                pdf_artifact = export_fixture_report(
                    request_for_current(BEAM_ID, inputs, "pdf"), inputs, report_result
                )
                st.download_button(
                    "Download PDF Report",
                    data=pdf_artifact.content,
                    file_name=pdf_artifact.filename,
                    mime=pdf_artifact.media_type,
                    key="v2_landing_pdf_report",
                )
        st.markdown(
            '<div class="inputs-v2-root"><div class="inputs-v2-card-label">Design mode</div></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    _seed_widgets(inputs)
    try:
        shadow_for_summary = calculate_legacy_shadow_current(inputs)
    except Exception:
        shadow_for_summary = None
    _render_input_summary(inputs, shadow_for_summary)
    _render_design_brain()
    _render_batch_status()
    report_request = request_for_current(BEAM_ID, inputs, "html")
    report_result = _calculate_fixture(inputs)
    if report_result is None:
        st.error("Calculation result was stale; edit was not published.")
        st.stop()
    report_artifact = export_fixture_report(report_request, inputs, report_result)
    csv_artifact = export_fixture_report(
        request_for_current(BEAM_ID, inputs, "csv"), inputs, report_result
    )
    pdf_artifact = export_fixture_report(
        request_for_current(BEAM_ID, inputs, "pdf"), inputs, report_result
    )
    if st.session_state.pop("v2_report_requested", False):
        st.download_button(
            "Download PDF Report",
            data=pdf_artifact.content,
            file_name=pdf_artifact.filename,
            mime=pdf_artifact.media_type,
            key="v2_header_pdf_report",
        )
    controls, diagram = st.columns([1.1, 0.9], gap="large")
    with controls:
        st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-card-label">Design mode</div></div>', unsafe_allow_html=True)
        st.radio("Design mode", ["Fast", "Detailed"], horizontal=True, key="v2_design_mode", label_visibility="collapsed")
        st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-card-label">Design Actions</div></div>', unsafe_allow_html=True)
        _compact_number("Positive design moment Mu*+ (kNm)", key="v2_bending_moment", min_value=0.0, max_value=100000.0, step=5.0)
        _compact_number("Design torsion Tu* (kNm)", key="v2_torsion", min_value=0.0, max_value=100000.0, step=5.0)
        _compact_number("Design shear Vu* (kN)", key="v2_shear_force", min_value=0.0, max_value=10000.0, step=5.0)
        _compact_number("Axial force N* (kN)", key="v2_axial_force", min_value=-100000.0, max_value=100000.0, step=5.0)
        st.caption("Design actions will use the same canonical action model as the production adapter.")
        st.markdown('<div class="inputs-v2-root"><div class="inputs-v2-card-label">Geometry & Materials</div></div>', unsafe_allow_html=True)
        _compact_select("Section shape", ["RECT", "T", "I"], key="v2_section_shape")
        _compact_number("Width b (mm)", key="v2_width_mm", min_value=50.0, max_value=3000.0, step=25.0)
        st.checkbox("Lock width", key="v2_width_locked", on_change=_commit_widgets)
        _compact_number("Depth D (mm)", key="v2_depth_mm", min_value=200.0, max_value=5000.0, step=25.0)
        st.checkbox("Lock depth", key="v2_depth_locked", on_change=_commit_widgets)
        _compact_number("Span L (mm)", key="v2_span_mm", min_value=500.0, max_value=100000.0, step=100.0)
        _compact_number("Steel MPa", key="v2_reinforcement_strength", min_value=200.0, max_value=1000.0, step=10.0)
        _compact_number("Concrete MPa", key="v2_concrete_strength", min_value=10.0, max_value=120.0, step=1.0)

        error = str(st.session_state.get(ERROR_KEY) or "")
        if error:
            st.error(error)

        current = _model()
        fixture_result = _calculate_fixture(current)
        if fixture_result is None:
            st.error("Calculation result was stale; edit was not published.")
            st.stop()
        st.info(fixture_result.summary)
        if fixture_result.status not in {"error", "updating"}:
            st.caption(f"Calculation complete - revision {fixture_result.source_revision}")
        try:
            shadow_result = calculate_legacy_shadow_current(current)
            st.session_state["v2_shadow_result"] = shadow_result
        except Exception as exc:
            st.session_state["v2_shadow_error"] = str(exc)
        if st.query_params.get("diagnostics") == "1":
            st.markdown(
                f'<div class="inputs-v2-root"><div class="inputs-v2-diagnostic">revision={current.revision} - hash={current.content_hash[:12]} - result_revision={fixture_result.source_revision}</div></div>',
                unsafe_allow_html=True,
            )

    with diagram:
        current = _model()
        view_model = build_input_diagram_view_model(current)
        st.radio("Diagram", ["2D section", "3D section"], horizontal=True, key="v2_diagram_mode", label_visibility="collapsed")
        st.markdown(f'<div class="inputs-v2-root"><div class="inputs-v2-card-label">{st.session_state["v2_diagram_mode"]}</div></div>', unsafe_allow_html=True)
        st.plotly_chart(
            build_3d_figure(view_model) if st.session_state["v2_diagram_mode"] == "3D section" else build_section_figure(view_model),
            use_container_width=True,
            key=f"inputs_v2_diagram_{view_model.source_revision}",
            config={"displayModeBar": False, "responsive": True},
        )
        st.caption(
            f"{view_model.width_mm:.0f} x {view_model.depth_mm:.0f} mm - "
            f"{view_model.resolved_bar_count}-N{current.bottom.diameter_mm} bottom bars"
        )

    # The reinforcement families span the page beneath the controls/diagram
    # row, matching the Runtime Inputs composition rather than being trapped
    # inside the left controls column.
    st.markdown('<div class="inputs-v2-root inputs-v2-section-divider"></div>', unsafe_allow_html=True)
    bottom_col, top_col, shear_col = st.columns(3, gap="large")
    with bottom_col:
        _render_bottom_controls()
    with top_col:
        _render_top_controls()
    with shear_col:
        _render_shear_controls()
    if st.session_state.get("v2_design_mode", "Fast") == "Detailed":
        st.markdown('<div class="inputs-v2-root inputs-v2-section-divider"></div>', unsafe_allow_html=True)
        _render_detailed_controls()


if __name__ == "__main__":
    render()

