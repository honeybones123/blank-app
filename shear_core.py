# shear_core.py
from dataclasses import replace
from typing import Any, Mapping
import math
import json
import time
import os
import streamlit as st
import numpy as np
from shear_checks_helpers import (
    compute_canonical_shear_truth,
    resolve_shear_spacing_truth,
)
from shear_calculation_runtime import ShearInputs, ShearResults, run_shear_calc
from state_runtime_gateway import (
    get_longitudinal_row_inputs,
    get_param,
    resolve_design_actions,
    speed_profile_record,
    speed_profile_section,
    update_results,
)
from calculations.shear import (
    approximate_concrete_tension_area_mm2,
    compute_midspan_spacing_result as _calc_compute_midspan_spacing_result,
    derive_eps_top_bot_for_step4_diagram,
    required_asv_per_s as _calc_required_asv_per_s,
    spacing_from_demand as _calc_spacing_from_demand,
    stirrup_area_mm2,
)
from ui.diagrams.shear_zone_layout_diagram import (
    build_shear_zone_layout_strip_figure as _shared_build_shear_zone_layout_strip_figure,
)
try:
    from shear_visuals import _dbg_log  # type: ignore
except Exception:
    def _dbg_log(message: str, data: dict[str, Any], *, hypothesis_id: str, run_id: str = "ss_psf_debug") -> None:
        return None


SHEAR_TRUTH_EPS = 1e-9


def _resolve_canonical_shear_truth(
    *,
    sectional_ok: bool | None,
    envelope_ok: bool | None,
    governing_util: float | None,
    governing_reason: str,
    governing_source: str,
    s_eff_mm: float | None,
    s_req_mm: float | None,
    provided_spacing_mm: float | None,
) -> dict:
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            out = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(out) or math.isinf(out):
            return None
        return out

    util_f = _safe_float(governing_util)
    eff_f = _safe_float(s_eff_mm)
    req_f = _safe_float(s_req_mm)
    prov_f = _safe_float(provided_spacing_mm)

    if util_f is not None:
        canonical_status = "PASS" if util_f <= 1.0 + SHEAR_TRUTH_EPS else "FAIL"
        canonical_reason = str(governing_reason or "").strip() or (
            "governing_shear_util_within_unity"
            if canonical_status == "PASS"
            else "governing_shear_util_exceeds_unity"
        )
        canonical_resolved = True
    else:
        canonical_status = "FAIL"
        canonical_reason = str(governing_reason or "").strip() or (
            "missing_governing_shear_util"
            if sectional_ok is not True or envelope_ok is not True
            else "unresolved_governing_shear_truth"
        )
        canonical_resolved = False

    canonical_source = str(governing_source or "").strip() or "unresolved_governing_shear_truth"

    return {
        "canonical_shear_status": canonical_status,
        "canonical_shear_ok": canonical_status == "PASS",
        "canonical_shear_util": util_f,
        "canonical_shear_reason": canonical_reason,
        "canonical_shear_source": canonical_source,
        "canonical_shear_resolved": canonical_resolved,
        "canonical_shear_effective_spacing_mm": eff_f,
        "canonical_shear_required_spacing_mm": req_f,
        "canonical_shear_provided_spacing_mm": prov_f,
    }


def _normalise_final_shear_publication(
    *,
    shear_design_status_out: str | None,
    final_shear_status_source: str,
    final_shear_truth_resolved: bool,
    final_shear_truth_failure_reason: str | None,
    shear_util_governing_out: float | None,
    canonical_pub: Any,
    zone_payload: dict[str, Any] | None,
    session_state: Mapping[str, Any],
    provided_mm: float,
    required_mm: float | None,
    effective_mm: float,
    governing_spacing_source: str,
) -> dict[str, Any]:
    """
    Last publication normaliser before update_results: skip-path truth labels, source-aware
    published_result_spacing_mm, explicit spacing reason, and no-false-PASS clamp.
    """
    _out_st = shear_design_status_out
    _src = final_shear_status_source
    _res = final_shear_truth_resolved
    _fail = final_shear_truth_failure_reason
    _ugu = shear_util_governing_out
    _gov = str(governing_spacing_source or "").strip().lower()
    _tol_sp = 0.51

    if _src == "sectional_zone_or_invalid_skip":
        _res = False
        if str(_out_st or "").strip().upper() == "INVALID":
            _src = "canonical_skipped_invalid_design_state"
            _fail = "invalid_shear_design_state_before_canonical"
        elif _out_st == "no_reo":
            _src = "canonical_skipped_no_reo"
            _fail = "ligatures_not_modeled_no_reo"
        else:
            _src = "canonical_skipped_insufficient_ligatures"
            _fail = "ligatures_below_canonical_publication_threshold"
        if str(_out_st or "").strip().upper() == "PASS":
            _out_st = "FAIL"
            _fail = (
                f"{_fail};sectional_pass_downgraded_without_canonical_truth"
                if _fail
                else "sectional_pass_downgraded_without_canonical_truth"
            )

    # Product rule: when a valid end/support-zone required spacing exists,
    # final shear publication should use that spacing as the Vu/check spacing.
    # Midspan spacing remains separate detailing output in the zone payload.
    if required_mm is not None and float(required_mm) > 0.0:
        _gov = "required"
        _pr_mm = float(required_mm)
        _meaning = "governing_required"
    elif _gov == "required":
        if required_mm is not None and float(required_mm) > 0.0:
            _pr_mm: float | None = float(required_mm)
        else:
            _pr_mm = float(effective_mm)
        _meaning = "governing_required"
    elif _gov == "provided":
        _pr_mm = float(provided_mm)
        _meaning = "provided"
    else:
        _pr_mm = float(effective_mm)
        _meaning = "effective_check"

    if _gov == "required" and required_mm is not None and abs(float(required_mm) - float(provided_mm)) > _tol_sp:
        _fsr = (
            "published_result_spacing_mm is governing required/envelope spacing (source-aware); "
            "provided input remains in shared_s_lig and shear_provided_input_spacing_mm (not overwritten)."
        )
    elif _gov == "provided":
        _fsr = (
            "published_result_spacing_mm matches provided input; governing_spacing_source is 'provided'."
        )
    else:
        _fsr = (
            "published_result_spacing_mm follows effective/check spacing; "
            "governing_spacing_source is indeterminate or mixed — see shear_governing_spacing_source."
        )

    return {
        "shear_design_status_out": _out_st,
        "final_shear_status_source": _src,
        "final_shear_truth_resolved": _res,
        "final_shear_truth_failure_reason": _fail,
        "published_result_spacing_mm": _pr_mm,
        "published_result_spacing_meaning": _meaning,
        "final_shear_spacing_reason": _fsr,
    }


class ShearLayoutError(ValueError):
    def __init__(self, message: str, *, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload


def cot(rad: float) -> float:
    with speed_profile_section("derived_result_computation.shear_capacity.subfunction.cot", category="compute"):
        return 1.0 / math.tan(rad)


def required_asv_per_s(V, phi, Vuc, fy, dv, *, cot_theta_v: float = 1.0):
    """
    Required A_sv/s (mm^2/mm) from along-span shear demand array.
    Inputs V and Vuc in kN; fy in MPa; dv in mm.
    Matches sectional V_us = (A_sv/s)·f_yv·d_v·cot(θ_v) (AS 3600 truss analogy).
    """
    with speed_profile_section(
        "derived_result_computation.shear_capacity.subfunction.required_asv_per_s",
        category="compute",
    ):
        return _calc_required_asv_per_s(V, phi, Vuc, fy, dv, cot_theta_v=cot_theta_v)


def spacing_from_demand(
    Vi_kN: float,
    phi: float,
    Vuc_kN: float,
    fy_mpa: float,
    dv_mm: float,
    Asv_mm2: float,
    D_mm: float,
    s_min_mm: float,
    *,
    cot_theta_v: float = 1.0,
    increment_mm: float = 10.0,
) -> float:
    """Demand-based spacing from local V(x), clamped to code/practical limits."""
    with speed_profile_section(
        "derived_result_computation.shear_capacity.subfunction.spacing_from_demand",
        category="compute",
    ):
        return _calc_spacing_from_demand(
            Vi_kN,
            phi,
            Vuc_kN,
            fy_mpa,
            dv_mm,
            Asv_mm2,
            D_mm,
            s_min_mm,
            cot_theta_v=cot_theta_v,
            increment_mm=increment_mm,
        )


def compute_midspan_spacing_result(
    *,
    V_mid_kN: float,
    phi: float,
    Vuc_kN: float,
    fy_mpa: float,
    dv_mm: float,
    Asv_mm2: float,
    D_mm: float,
    s_min_mm: float,
    cot_theta_v: float,
    increment_mm: float,
) -> tuple[float, str]:
    """
    Required midspan spacing from shear demand at x = L/2 (same physics as spacing_from_demand).
    Returns (s_mm, mode) where mode is max_spacing or shear_demand.
    """
    with speed_profile_section(
        "derived_result_computation.shear_capacity.subfunction.compute_midspan_spacing_result",
        category="compute",
    ):
        return _calc_compute_midspan_spacing_result(
            V_mid_kN=V_mid_kN,
            phi=phi,
            Vuc_kN=Vuc_kN,
            fy_mpa=fy_mpa,
            dv_mm=dv_mm,
            Asv_mm2=Asv_mm2,
            D_mm=D_mm,
            s_min_mm=s_min_mm,
            cot_theta_v=cot_theta_v,
            increment_mm=increment_mm,
        )


def ensure_shear_report_built(
    session_state: Mapping[str, Any] | None = None,
    results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Lazily build the detailed shear report tree only when a report/detail consumer
    asks for it. This keeps diagrams out of the hot engineering compute path.
    """
    _lazy_total_t0 = time.perf_counter()
    state = session_state if session_state is not None else st.session_state
    results_dict = results if isinstance(results, dict) else None
    if results_dict is None:
        raw_results = state.get("results", {})
        results_dict = raw_results if isinstance(raw_results, dict) else {}

    existing = results_dict.get("shear_report")
    if isinstance(existing, dict) and existing.get("tabs"):
        return existing

    shear_steps = list(results_dict.get("shear_steps", []) or state.get("shear_steps", []) or [])
    if not shear_steps:
        return {}

    _section_t0 = time.perf_counter()
    from reporting.step_projection import steps_to_tabs_boxes
    from reporting.fig_export import export_box_diagram_png
    try:
        from reporting.fig_export import call_with_supported_kwargs
    except Exception:
        from fig_export import call_with_supported_kwargs
    from shear_diagrams import (
        plot_shear_torsion_section_2d,
        plot_shear_step1_theta_cracks_3d,
        make_mcft_longitudinal_strain_profile_fig,
    )
    speed_profile_record(
        "shear_report_lazy.imports",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="render",
    )

    _section_t0 = time.perf_counter()
    steps_with_diagrams = [dict(step or {}) for step in shear_steps]
    try:
        from section_layout import compute_section_layout
        layout = compute_section_layout()
        dims = dict(layout.get("dims", {}) or {})
        shape_name = str(layout.get("shape_name", state.get("sec_shape", "RECT")))
        reo = list(state.get("resolved_longitudinal_bars", []) or [])
    except Exception:
        dims = {}
        shape_name = str(state.get("sec_shape", "RECT"))
        reo = []

    try:
        actions = resolve_design_actions()
        mu_signed = float(actions.get("Mu_signed", 0.0) or 0.0)
    except Exception:
        mu_signed = 0.0
    active_tension_face = "top" if mu_signed < 0.0 else "bottom"

    try:
        theta_deg = float(results_dict.get("shear_theta_v_deg", state.get("shear_theta_v_deg", 45.0)) or 45.0)
    except (TypeError, ValueError):
        theta_deg = 45.0
    try:
        eps_x = float(results_dict.get("shear_eps_x", state.get("shear_eps_x", 0.0)) or 0.0)
    except (TypeError, ValueError):
        eps_x = 0.0
    try:
        L_mm = float(state.get("L") or 0.0)
    except (TypeError, ValueError):
        L_mm = 0.0
    eps_top, eps_bot = derive_eps_top_bot_for_step4_diagram(eps_x)

    diag1 = export_box_diagram_png(
        lambda: call_with_supported_kwargs(
            plot_shear_step1_theta_cracks_3d,
            L_mm=L_mm,
            b_mm=float(state.get("b") or 0.0),
            D_mm=float(state.get("D") or 0.0),
            theta_deg=theta_deg,
        ),
        key="shear_1_torsion",
        caption="Torsion cracking / diagonal crack field",
        w_mm=65,
        h_mm=40,
    )
    diag2 = export_box_diagram_png(
        lambda: plot_shear_torsion_section_2d(
            shape_name=shape_name,
            dims=dims,
            reo=reo,
            show_labels=True,
            tension_face=active_tension_face,
        ),
        key="shear_2_section",
        caption="Section + torsion/shear idealisation",
        w_mm=65,
        h_mm=40,
    )
    diag3 = export_box_diagram_png(
        lambda: make_mcft_longitudinal_strain_profile_fig(eps_top, eps_x, eps_bot),
        key="shear_4_epsx",
        caption="MCFT longitudinal strain profile",
        w_mm=65,
        h_mm=40,
    )
    if len(steps_with_diagrams) >= 2:
        steps_with_diagrams[1]["diagram"] = diag1
    if len(steps_with_diagrams) >= 4:
        steps_with_diagrams[3]["diagram"] = diag2
    if len(steps_with_diagrams) >= 5:
        steps_with_diagrams[4]["diagram"] = diag3
    speed_profile_record(
        "shear_report_lazy.diagrams",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="render",
    )

    _section_t0 = time.perf_counter()
    shear_report = steps_to_tabs_boxes(
        module_title="Shear (ULS)",
        steps=steps_with_diagrams,
        default_tab="ULS Checks",
    )
    try:
        actions = resolve_design_actions()
        vu_star = float(actions.get("Vu", 0.0) or 0.0)
    except Exception:
        vu_star = 0.0
    try:
        phi_vu_cap = float(results_dict.get("phi_Vu_cap", state.get("phi_Vu_cap", 0.0)) or 0.0)
    except (TypeError, ValueError):
        phi_vu_cap = 0.0
    try:
        vu_util = results_dict.get("Vu_utilisation", state.get("Vu_utilisation"))
        vu_util = float(vu_util) if vu_util is not None else None
    except (TypeError, ValueError):
        vu_util = None
    outcome = (
        "PASS" if (vu_util is not None and vu_util <= 1.0) else
        "FAIL" if vu_util is not None else
        "N/A"
    )
    shear_report["summary"] = shear_report.get("summary", [
        ("Demand", f"{vu_star:.1f} kN"),
        ("Capacity", f"{phi_vu_cap:.1f} kN"),
        ("Utilisation", f"{vu_util:.2f}" if vu_util is not None else "N/A"),
        ("Outcome", outcome),
    ])
    speed_profile_record(
        "shear_report_lazy.build_tabs",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="render",
    )

    try:
        results_dict["shear_report"] = shear_report
    except Exception:
        pass
    try:
        state["shear_report"] = shear_report
    except Exception:
        pass
    try:
        session_results = state.get("results", {})
        if isinstance(session_results, dict):
            session_results["shear_report"] = shear_report
    except Exception:
        pass

    speed_profile_record(
        "shear_report_lazy.total",
        (time.perf_counter() - _lazy_total_t0) * 1000.0,
        category="render",
    )
    return shear_report


def compute_shear_zones(
    *,
    L_mm: float,
    d_mm: float,
    results: ShearResults,
    inp: ShearInputs,
    is_cantilever: bool,
    lig_d_mm: float,
    legs: int,
    spacing_increment_mm: float = 10.0,
) -> dict | None:
    """
    3-zone constructible stirrup spacing layout (support / shear span / midspan).

    Always returns a layout dict when L and d_v are valid (including shear FAIL and
    zero / undefined stirrups — uses a notional bar basis for spacing display only).

    Uses V_eq, V_uc, θ_v, d_v, f_syv from the sectional shear model (unchanged).
    """
    _compute_shear_zones_t0 = time.perf_counter()
    design_governing = str(get_param("actions_mode", "manual") or "manual").strip().lower() == "design"
    L = float(L_mm)
    if L <= 1.0:
        raise ValueError("Shear design requires valid geometry (L and d_v) for detailing")
    L_m = L / 1000.0
    n = 51
    x = np.linspace(0.0, L_m, n)

    _section_t0 = time.perf_counter()
    if design_governing:
        shear_x_raw = np.asarray(get_param("shear_x") or [], dtype=float)
        shear_V_raw = np.asarray(get_param("shear_V") or [], dtype=float)
        if shear_x_raw.size > 0 and shear_V_raw.size > 0 and shear_x_raw.size == shear_V_raw.size:
            shear_x = x
            shear_V = np.interp(x, shear_x_raw, shear_V_raw)
        else:
            raise ValueError("Design mode requires SFD V(x)")
    else:
        V_star = float(get_param("uls_Vstar") or 0.0)
        shear_x = x
        # Manual mode assumes a simply supported UDL shear diagram:
        # peak shear at supports, reducing linearly to zero at midspan.
        shear_V = V_star * (2.0 * np.abs(x - L_m / 2.0) / max(L_m, 1e-9))
        shear_V = np.maximum(shear_V, 0.0)
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.shear_distribution",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    _section_t0 = time.perf_counter()
    from shear_zone_spacing import asv_min_over_s_mm, code_s_max_mm, practical_s_min_mm
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.spacing_helpers_import",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    _section_t0 = time.perf_counter()
    d_v = float(results.d_v)
    d_eff = float(d_mm)
    b_v = float(results.b_v)
    fc = float(inp.fc)
    Asv = float(results.Asv)
    f_syv = float(results.f_syv)
    V_eq = float(results.V_eq)
    Vuc = float(results.Vuc_kN)
    theta_v_rad = float(results.theta_v_rad)
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.layout_resolution",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    if d_v <= 1.0:
        raise ValueError("Shear design requires valid geometry (L and d_v) for detailing")

    _section_t0 = time.perf_counter()
    cot_t = cot(theta_v_rad)
    if cot_t <= 1e-12:
        cot_t = 1.0

    asv_min = asv_min_over_s_mm(fc, b_v, f_syv)
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.material_and_theta",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    _section_t0 = time.perf_counter()
    legs_i_raw = int(legs) if abs(float(legs) - round(float(legs))) < 0.01 else int(round(float(legs)))
    use_notional = bool(legs_i_raw <= 0 or Asv <= 1e-6)
    if use_notional:
        lig_disp = max(float(lig_d_mm), 10.0)
        legs_disp = 2
        asv_for_spacing = stirrup_area_mm2(legs_disp, lig_disp)
    else:
        lig_disp = max(float(lig_d_mm), 1.0)
        legs_disp = max(legs_i_raw, 1)
        asv_for_spacing = float(Asv)
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.reinforcement_layout_basis",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    _section_t0 = time.perf_counter()
    s_max = code_s_max_mm(d_eff)
    s_min_prac = practical_s_min_mm(lig_disp)
    inc = max(float(spacing_increment_mm), 1.0)
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.spacing_limits",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    if len(shear_x) != len(shear_V) or len(shear_x) < 2:
        raise ValueError(
            "Shear V(x) is required for zoned shear design. Run SFD/BMD or enable synthetic distribution."
        )
    shear_x = np.asarray(shear_x, dtype=float)
    shear_V = np.abs(np.asarray(shear_V, dtype=float))
    if not np.all(np.isfinite(shear_x)) or not np.all(np.isfinite(shear_V)):
        raise ValueError("Shear distribution V(x) contains non-finite values")

    _section_t0 = time.perf_counter()
    _mid_idx = int(len(shear_V) // 2) if shear_V.size else 0
    V_mid_kN = float(shear_V[_mid_idx]) if shear_V.size else 0.0
    shear_mid_spacing_calc_mm, shear_mid_spacing_mode = compute_midspan_spacing_result(
        V_mid_kN=V_mid_kN,
        phi=float(inp.phi),
        Vuc_kN=float(Vuc),
        fy_mpa=float(f_syv),
        dv_mm=float(d_v),
        Asv_mm2=float(asv_for_spacing),
        D_mm=float(d_eff),
        s_min_mm=float(s_min_prac),
        cot_theta_v=float(cot_t),
        increment_mm=float(inc),
    )
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.midspan_spacing",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    _section_t0 = time.perf_counter()
    req_asv_s = np.maximum(
        required_asv_per_s(shear_V, inp.phi, Vuc, f_syv, d_v, cot_theta_v=cot_t),
        asv_min,
    )
    asv_over_s_req = float(np.max(req_asv_s)) if req_asv_s.size else float(asv_min)
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.required_profile",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    _section_t0 = time.perf_counter()
    spacing_profile = np.array(
        [
            spacing_from_demand(
                Vi_kN=float(v_i),
                phi=float(inp.phi),
                Vuc_kN=float(Vuc),
                fy_mpa=float(f_syv),
                dv_mm=float(d_v),
                Asv_mm2=float(asv_for_spacing),
                D_mm=float(d_eff),
                s_min_mm=float(s_min_prac),
                cot_theta_v=float(cot_t),
                increment_mm=float(inc),
            )
            for v_i in shear_V
        ],
        dtype=float,
    )
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.spacing_profile_loop",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    z1_end = min(1.5 * d_v, L)
    z2_end = min(0.5 * L, L)
    z1_lo, z1_hi = 0.0, z1_end
    z2_lo, z2_hi = z1_hi, max(z1_hi, z2_end)
    z3_lo, z3_hi = z2_hi, L

    warnings: list[str] = []
    if use_notional:
        warnings.append(
            f"No stirrups defined (or $A_{{sv}}\\approx 0$); zone spacings use a notional "
            f"**N{int(round(lig_disp))}** ({legs_disp}-leg) basis for layout only."
        )

    # Auto-correction: tighten spacing until compliant OR all locations reach minimum spacing.
    _section_t0 = time.perf_counter()
    prov_asv_s = asv_for_spacing / np.maximum(spacing_profile, 1e-9)
    while True:
        util0 = np.where(req_asv_s > 1e-12, prov_asv_s / req_asv_s, 1e9)
        min_util0 = float(np.min(util0)) if util0.size else float("inf")
        if min_util0 >= 1.0:
            break
        at_min_mask = spacing_profile <= s_min_prac + 1e-9
        fail_mask = (req_asv_s > 1e-12) & (prov_asv_s + 1e-9 < req_asv_s)
        if np.all(~fail_mask | at_min_mask):
            break
        spacing_profile[fail_mask & ~at_min_mask] = np.maximum(
            s_min_prac,
            np.floor((spacing_profile[fail_mask & ~at_min_mask] * 0.9) / inc + 1e-9) * inc,
        )
        spacing_profile = np.minimum(spacing_profile, s_max)
        prov_asv_s = asv_for_spacing / np.maximum(spacing_profile, 1e-9)
    # Practical detailing output: round down to 5 mm increments and re-apply limits.
    spacing_profile = np.clip(
        np.floor(spacing_profile / 5.0 + 1e-9) * 5.0,
        s_min_prac,
        s_max,
    )
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.autocorrection_loop",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )
    # --- Determine governing behaviour ---
    s_max = min(0.75 * float(d_eff), 500.0)
    profile_min = float(np.min(spacing_profile)) if spacing_profile.size else float(s_max)
    profile_max = float(np.max(spacing_profile)) if spacing_profile.size else float(s_max)
    is_max_governed = abs(profile_min - s_max) < 1e-3 and abs(profile_max - s_max) < 1e-3
    is_varying = (profile_max - profile_min) > 5.0
    _dbg_log(
        "spacing governing mode",
        {
            "is_max_governed": is_max_governed,
            "is_varying": is_varying,
            "s_max": s_max,
            "profile_min": profile_min,
            "profile_max": profile_max,
        },
        run_id="fix",
        hypothesis_id="GOV",
    )

    s_raw_tight = asv_for_spacing / max(asv_over_s_req, 1e-12)
    if s_raw_tight < s_min_prac - 1e-6:
        warnings.append(
            "Required spacing too tight — increase bar size or number of legs."
        )

    shear_x_mm = shear_x * 1000.0
    x_positions_mm = shear_x_mm
    end_limit_mm = min(1.5 * float(d_mm), 0.5 * float(L))
    if is_cantilever:
        end_mask = x_positions_mm <= end_limit_mm + 1e-9
        mid_mask = x_positions_mm > end_limit_mm + 1e-9
    else:
        end_mask = (x_positions_mm <= end_limit_mm + 1e-9) | (
            x_positions_mm >= (float(L) - end_limit_mm - 1e-9)
        )
        mid_mask = ~end_mask
    s_end = float(np.min(spacing_profile[end_mask])) if np.any(end_mask) else float(np.min(spacing_profile))
    s_mid = float(np.min(spacing_profile[mid_mask])) if np.any(mid_mask) else float(s_end)

    _FILL_RED = "rgba(255,0,0,0.15)"
    _FILL_ORANGE = "rgba(255,165,0,0.15)"
    if is_cantilever:
        strip_segments = [
            {"zone": "support", "x0_mm": 0.0, "x1_mm": end_limit_mm, "spacing_mm": float(s_end), "color": "rgba(220, 75, 75, 0.88)"},
            {"zone": "mid", "x0_mm": end_limit_mm, "x1_mm": float(L), "spacing_mm": float(s_mid), "color": "rgba(255, 155, 60, 0.9)"},
        ]
    else:
        strip_segments = [
            {"zone": "end", "x0_mm": 0.0, "x1_mm": end_limit_mm, "spacing_mm": float(s_end), "color": "rgba(220, 75, 75, 0.88)"},
            {"zone": "mid", "x0_mm": end_limit_mm, "x1_mm": max(end_limit_mm, float(L) - end_limit_mm), "spacing_mm": float(s_mid), "color": "rgba(255, 155, 60, 0.9)"},
            {"zone": "end", "x0_mm": max(end_limit_mm, float(L) - end_limit_mm), "x1_mm": float(L), "spacing_mm": float(s_end), "color": "rgba(220, 75, 75, 0.88)"},
        ]
    strip_segments = [seg for seg in strip_segments if float(seg["x1_mm"]) > float(seg["x0_mm"]) + 1e-9]
    zones_m = [
        {
            "start": float(seg["x0_mm"]) / 1000.0,
            "end": float(seg["x1_mm"]) / 1000.0,
            "spacing": float(seg["spacing_mm"]) / 1000.0,
            "label": (
                "Support zone"
                if str(seg["zone"]) == "support"
                else "End zone" if str(seg["zone"]) == "end" else "Mid span"
            ),
            "fillcolor": _FILL_RED if str(seg["zone"]) in {"support", "end"} else _FILL_ORANGE,
        }
        for seg in strip_segments
    ]

    def _spacing_at_x_mm(x_mm: float) -> float:
        for seg in strip_segments:
            if float(seg["x0_mm"]) - 1e-9 <= x_mm <= float(seg["x1_mm"]) + 1e-9:
                return float(seg["spacing_mm"])
        return float(s_end)

    prov_asv_s = np.array([asv_for_spacing / max(_spacing_at_x_mm(xm), 1e-9) for xm in shear_x_mm], dtype=float)
    util = np.where(req_asv_s > 1e-12, prov_asv_s / req_asv_s, 1e9)
    asv_over_s_provided = float(np.min(prov_asv_s)) if prov_asv_s.size else 0.0

    min_index = int(np.argmin(util)) if util.size else 0
    min_util = float(util[min_index]) if util.size else float("inf")
    x_crit = float(shear_x[min_index]) if shear_x.size else 0.0
    envelope_status = "PASS" if min_util <= 1.0 + SHEAR_TRUTH_EPS else "FAIL"
    if envelope_status == "FAIL":
        warnings.append("Envelope non-compliance detected: provided A_sv/s is below required at one or more locations.")

    req_end = float(np.max(req_asv_s[end_mask])) if np.any(end_mask) else float(asv_min)
    req_mid = float(np.max(req_asv_s[mid_mask])) if np.any(mid_mask) else float(req_end)

    dia_i = int(round(lig_disp))
    bar_only = f"N{dia_i}"
    bar_label_legs = f"{bar_only} ({legs_disp}-leg)"

    s_in = float(inp.s_lig)
    if is_cantilever:
        summary_lines = [
            f"Provided spacing (input, $s_{{lig}}$): {s_in:.0f} mm",
            f"Required spacing (end zone, demand/code layout): {s_end:.0f} mm",
            f"Support zone (0–1.5$d$) — layout: {bar_label_legs} @ {s_end:.0f} mm",
            f"Mid span — layout: {bar_only} @ {s_mid:.0f} mm",
        ]
    else:
        summary_lines = [
            f"Provided spacing (input, $s_{{lig}}$): {s_in:.0f} mm",
            f"Required spacing (end zone, demand/code layout): {s_end:.0f} mm",
            f"End zone (0–1.5$d$) — layout: {bar_label_legs} @ {s_end:.0f} mm",
            f"Mid span — layout: {bar_only} @ {s_mid:.0f} mm",
            f"End zone (mirror) — layout: {bar_only} @ {s_end:.0f} mm",
        ]

    summary_lines.append(
        f"Envelope check: {envelope_status} (worst util {min_util:.2f} @ x={x_crit:.2f} m) — "
        "effective spacing used in the sectional φV_u check is published separately after auto/apply rules."
    )
    _section_t0 = time.perf_counter()
    payload = {
        "beam_length_mm": L,
        "d_mm": d_eff,
        "d_v_mm": d_v,
        "is_cantilever": bool(is_cantilever),
        "asv_over_s_req": float(asv_over_s_req),
        "asv_over_s_min": float(asv_min),
        "asv_over_s_provided": float(asv_over_s_provided),
        "governing_mode": "SMAX" if is_max_governed else "DEMAND",
        "v_source_mode": "design" if design_governing else "manual",
        "s_max_code_mm": float(s_max),
        "s_max_mm": float(s_max),
        "s_min_practical_mm": float(s_min_prac),
        "spacing_increment_mm": float(inc),
        "lig_d_mm": float(lig_disp),
        "legs": int(legs_disp),
        "legs_input": int(max(legs_i_raw, 0)),
        "spacing_uses_notional_asv": bool(use_notional),
        "bar_label": bar_label_legs,
        "bar_label_short": bar_only,
        "zone_1": {"range": (0.0, end_limit_mm), "spacing": float(s_end), "asv_over_s_demand": float(max(req_end, asv_min))},
        "zone_2": {"range": (end_limit_mm, max(end_limit_mm, float(L) - end_limit_mm)), "spacing": float(s_mid), "asv_over_s_demand": float(max(req_mid, asv_min))},
        "zone_3": (
            None
            if is_cantilever
            else {"range": (max(end_limit_mm, float(L) - end_limit_mm), float(L)), "spacing": float(s_end), "asv_over_s_demand": float(max(req_end, asv_min))}
        ),
        "shear_x": [float(v) for v in shear_x.tolist()],
        "shear_V": [float(v) for v in shear_V.tolist()],
        "V_max": float(np.max(shear_V)) if shear_V.size else 0.0,
        "req_asv_s": [float(v) for v in req_asv_s.tolist()],
        "prov_asv_s": [float(v) for v in prov_asv_s.tolist()],
        "shear_util_min": float(min_util),
        "shear_util_x": float(x_crit),
        "shear_envelope_status": envelope_status,
        "shear_spacing_end_mm": float(s_end),
        "shear_spacing_mid_mm": float(s_mid),
        "shear_spacing_governing": "max" if is_max_governed else "demand",
        "shear_spacing_profile_min": float(profile_min),
        "shear_spacing_profile_max": float(profile_max),
        "shear_s_end": float(s_end),
        "shear_s_mid": float(s_mid),
        "shear_mid_spacing_calc_mm": float(shear_mid_spacing_calc_mm),
        "shear_mid_spacing_mode": str(shear_mid_spacing_mode),
        "provided_input_spacing_mm": float(s_in),
        "provided_spacing_mm": float(s_in),
        "required_spacing_mm": float(s_end),
        "V_mid_kN": float(V_mid_kN),
        "strip_segments_mm": strip_segments,
        "zones": zones_m,
        "summary_lines": summary_lines,
        "warnings": list(dict.fromkeys(warnings)),
    }
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones.payload_build",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )
    if envelope_status != "PASS":
        spacing_at_crit = float(_spacing_at_x_mm(x_crit * 1000.0))
        req_crit = float(req_asv_s[min_index]) if req_asv_s.size else 0.0
        prov_crit = float(prov_asv_s[min_index]) if prov_asv_s.size else 0.0
        suggestions: list[str] = []
        if spacing_at_crit <= s_min_prac + 1e-9:
            suggestions.append("Increase number of ligature legs or bar size")
        else:
            suggestions.append("Reduce spacing near critical region")
        speed_profile_record(
            "derived_result_computation.shear_capacity.compute_shear_zones",
            (time.perf_counter() - _compute_shear_zones_t0) * 1000.0,
            category="compute",
        )
        raise ShearLayoutError(
            "Shear design FAILED.\n"
            f"Min utilisation: {min_util:.2f} at x={x_crit:.2f} m\n"
            f"Spacing at critical location: {spacing_at_crit:.0f} mm (minimum practical {s_min_prac:.0f} mm)\n"
            f"Required A_sv/s at critical location: {req_crit:.3f} mm²/mm\n"
            f"Provided A_sv/s at critical location: {prov_crit:.3f} mm²/mm\n"
            f"Suggested fix: {', '.join(suggestions)}",
            payload=payload,
        )
    speed_profile_record(
        "derived_result_computation.shear_capacity.compute_shear_zones",
        (time.perf_counter() - _compute_shear_zones_t0) * 1000.0,
        category="compute",
    )
    return payload


def build_shear_zone_layout_strip_figure(
    payload: dict,
    *,
    beam_depth_m: float = 0.18,
    title: str | None = None,
    show_stirrup_marks: bool = True,
    max_stirrup_marks: int = 400,
    reference_width_px: float = 640.0,
    min_tick_spacing_px: float = 6.0,
):
    return _shared_build_shear_zone_layout_strip_figure(
        payload,
        beam_depth_m=beam_depth_m,
        title=title,
        show_stirrup_marks=show_stirrup_marks,
        max_stirrup_marks=max_stirrup_marks,
        reference_width_px=reference_width_px,
        min_tick_spacing_px=min_tick_spacing_px,
    )


# ------------------------------------------------------------
#  CORE COMPUTE FUNCTION (reads from session state, no UI)
# ------------------------------------------------------------
def _compute_shear_capacity():
    """
    Compute shear capacity using current session state values.
    Reads all inputs from get_param(), calls run_shear_calc(), and updates results.
    No Streamlit UI - pure computation.
    """
    _compute_shear_capacity_t0 = time.perf_counter()
    # Read geometry and materials
    _section_t0 = time.perf_counter()
    b = get_param("b", 300.0)
    D = get_param("D", 600.0)
    d = get_param("d", 560.0)
    fc = get_param("fc", 32.0)
    fsy = get_param("fsy", 500.0)
    Ec = get_param("Ec", 30000.0)
    Es = get_param("Es", 200000.0)
    
    # Read actions
    M_star = get_param("Mu_star", 0.0)
    V_star = get_param("Vu_star", 0.0)
    T_star = get_param("Tu_star", 0.0)
    N_star = get_param("N_star", 0.0)
    P_v = get_param("P_star", 0.0)
    
    # Read reinforcement
    lig_d = get_param("lig_d", 10.0)
    legs = get_param("lig_legs", 2)
    s_lig = get_param("s_lig", 200.0)
    
    # Default values for prestress/ducts (not commonly used)
    A_st = get_param("Ast_bot", 0.0)
    A_pt = 0.0
    f_po = 0.0
    A_ct = approximate_concrete_tension_area_mm2(b, D)
    d_g = 20.0  # Default aggregate size
    sum_duct = get_param("n_ducts", 0) * get_param("duct_dia", 0.0) if get_param("n_ducts", 0) > 0 else 0.0
    k_d = 0.0  # No ducts by default
    
    # Shear parameters
    use_general_kv = True  # Use general method by default
    phi = get_param("phi_shear", 0.75)  # Default shear phi
    sigma_cp = 0.0  # No prestress compression by default
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.read_session_inputs",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="state_mutation",
    )
    
    # Build shape_name/dims/reo for diagrams (same logic as Inputs/Bending)
    sec_shape = get_param("sec_shape", "RECT")
    if sec_shape == "T":
        shape_name = "T-Section"
        dims = {
            "bf": float(get_param("bf", 600.0)),
            "tf": float(get_param("tf", 120.0)),
            "bw": float(get_param("bw", 300.0)),
            "D":  float(get_param("D", 600.0)),
        }
    elif sec_shape == "I":
        shape_name = "I-Section"
        dims = {
            "bf": float(get_param("bf", 600.0)),
            "tf": float(get_param("tf", 120.0)),
            "tw": float(get_param("tw", 200.0)),
            "D":  float(get_param("D", 600.0)),
        }
    else:
        shape_name = "Rectangle (b × D)"
        dims = {
            "b": float(get_param("b", 300.0)),
            "D": float(get_param("D", 600.0)),
        }

    cover_top = float(get_param("cover_top", 40.0))
    cover_bot = float(get_param("cover_bot", 40.0))
    cover_side = get_param("cover_side", None)
    if cover_side is None:
        cover_side = min(cover_top, cover_bot)
    cover_side = float(cover_side)
    s_min = float(get_param("s_min", 25.0))

    top_rows = get_longitudinal_row_inputs("top")
    bottom_rows = get_longitudinal_row_inputs("bot")
    primary_top_row = next((row for row in top_rows if row.get("active")), None)
    primary_bottom_row = next((row for row in bottom_rows if row.get("active")), None)
    total_top_bars = int(float(get_param("total_top_bars", 0.0) or 0.0))
    total_bottom_bars = int(float(get_param("total_bot_bars", 0.0) or 0.0))
    if total_top_bars <= 0:
        total_top_bars = sum(int(row.get("bars", 0) or 0) for row in top_rows if row.get("active") and row.get("mode") == "Count")
    if total_bottom_bars <= 0:
        total_bottom_bars = sum(int(row.get("bars", 0) or 0) for row in bottom_rows if row.get("active") and row.get("mode") == "Count")

    reo = {
        "cover_top": cover_top,
        "cover_bot": cover_bot,
        "cover_side": cover_side,
        "top_rows": top_rows,
        "bottom_rows": bottom_rows,
        "rowgap_bot": float(get_param("rowgap_bot", 60.0)),
        "rowgap_top": float(get_param("rowgap_top", 60.0)),
        # Backwards-compatible totals
        "nb_top": total_top_bars,
        "db_top": float((primary_top_row or {}).get("dia", get_param("db_top", 16.0)) or 16.0),
        "nb_bot": total_bottom_bars,
        "db_bot": float((primary_bottom_row or {}).get("dia", get_param("db_bot", 20.0)) or 20.0),
        "min_clear_spacing": s_min,
        "lig_d": float(get_param("lig_d", 0.0)),
        "lig_legs": int(get_param("lig_legs", 0)),
        "top_flange_reo_enabled": bool(get_param("top_flange_reo_enabled", False)),
        "bot_flange_reo_enabled": bool(get_param("bot_flange_reo_enabled", False)),
        "top_flange_mirror_lr": bool(get_param("top_flange_mirror_lr", True)),
        "bot_flange_mirror_lr": bool(get_param("bot_flange_mirror_lr", True)),
        "top_flange_left_count": int(get_param("top_flange_left_count", 0) or 0),
        "top_flange_left_dia": float(get_param("top_flange_left_dia", 16.0) or 16.0),
        "top_flange_left_rows": int(get_param("top_flange_left_rows", 1) or 1),
        "top_flange_left_row_spacing": float(get_param("top_flange_left_row_spacing", 60.0) or 60.0),
        "top_flange_right_count": int(get_param("top_flange_right_count", 0) or 0),
        "top_flange_right_dia": float(get_param("top_flange_right_dia", 16.0) or 16.0),
        "top_flange_right_rows": int(get_param("top_flange_right_rows", 1) or 1),
        "top_flange_right_row_spacing": float(get_param("top_flange_right_row_spacing", 60.0) or 60.0),
        "bot_flange_left_count": int(get_param("bot_flange_left_count", 0) or 0),
        "bot_flange_left_dia": float(get_param("bot_flange_left_dia", 20.0) or 20.0),
        "bot_flange_left_rows": int(get_param("bot_flange_left_rows", 1) or 1),
        "bot_flange_left_row_spacing": float(get_param("bot_flange_left_row_spacing", 60.0) or 60.0),
        "bot_flange_right_count": int(get_param("bot_flange_right_count", 0) or 0),
        "bot_flange_right_dia": float(get_param("bot_flange_right_dia", 20.0) or 20.0),
        "bot_flange_right_rows": int(get_param("bot_flange_right_rows", 1) or 1),
        "bot_flange_right_row_spacing": float(get_param("bot_flange_right_row_spacing", 60.0) or 60.0),
        "top_flange_transverse_enabled": bool(get_param("top_flange_transverse_enabled", False)),
        "bot_flange_transverse_enabled": bool(get_param("bot_flange_transverse_enabled", False)),
        "top_flange_transverse_dia": float(get_param("top_flange_transverse_dia", 10.0) or 10.0),
        "bot_flange_transverse_dia": float(get_param("bot_flange_transverse_dia", 10.0) or 10.0),
        "top_flange_transverse_spacing": float(get_param("top_flange_transverse_spacing", 200.0) or 200.0),
        "bot_flange_transverse_spacing": float(get_param("bot_flange_transverse_spacing", 200.0) or 200.0),
        "top_flange_transverse_legs": int(get_param("top_flange_transverse_legs", 2) or 2),
        "bot_flange_transverse_legs": int(get_param("bot_flange_transverse_legs", 2) or 2),
    }

    shear_longitudinal_tension_increment = 0.0
    shear_Ast_required_tension_envelope = float(A_st or 0.0)
    shear_Ast_available_anchored_active = float(A_st or 0.0)
    shear_Ast_available_anchored_web = float(A_st or 0.0)
    shear_Ast_available_anchored_flange = 0.0
    shear_flange_bars_participating = False
    shear_longitudinal_detailing_ok = True
    active_tension_face = "bottom"
    active_tension_width_mm = float(b)
    active_tension_warning = ""
    flange_transverse_detailing_note = ""
    flange_transverse_reo_present_top = bool(get_param("top_flange_transverse_enabled", False))
    flange_transverse_reo_present_bottom = bool(get_param("bot_flange_transverse_enabled", False))
    flange_transverse_spacing_top = float(get_param("top_flange_transverse_spacing", 0.0) or 0.0)
    flange_transverse_spacing_bottom = float(get_param("bot_flange_transverse_spacing", 0.0) or 0.0)

    _section_t0 = time.perf_counter()
    try:
        from section_layout import compute_section_layout
        from section_props.reo_layout import (
            resolve_longitudinal_bars_from_layout,
            resolve_active_tension_reinforcement,
            resolve_crack_tension_width,
        )
        actions = resolve_design_actions()
        moment_sign = "negative" if float(actions.get("Mu_signed", 0.0) or 0.0) < 0.0 else "positive"
        layout = compute_section_layout()
        dims_resolved = dict(layout.get("dims", {}) or {})
        shape_resolved = str(layout.get("shape_name", sec_shape))
        bars = list(st.session_state.get("resolved_longitudinal_bars", []) or [])
        if not bars:
            bars = resolve_longitudinal_bars_from_layout(
                shape_name=shape_resolved,
                dims=dims_resolved,
                reo_layout=dict(layout.get("reo_layout", {}) or {}),
            )
        active = resolve_active_tension_reinforcement(
            dims_resolved,
            bars,
            moment_sign,
        )
        crack_w = resolve_crack_tension_width(
            sec_shape,
            dims_resolved,
            moment_sign,
            active.get("active_bars", []),
        )
        active_tension_face = str(active.get("tension_face", "bottom"))
        A_st = float(active.get("Ast_active_mm2", A_st) or A_st)
        active_tension_width_mm = float(crack_w.get("crack_tension_width_mm", b) or b)
        shear_Ast_available_anchored_active = sum(
            float(bar.get("area_mm2", 0.0) or 0.0)
            for bar in active.get("active_bars", [])
            if bool(bar.get("anchored", True))
        )
        shear_Ast_available_anchored_web = sum(
            float(bar.get("area_mm2", 0.0) or 0.0)
            for bar in active.get("active_web_bars", [])
            if bool(bar.get("anchored", True))
        )
        shear_Ast_available_anchored_flange = sum(
            float(bar.get("area_mm2", 0.0) or 0.0)
            for bar in active.get("active_flange_bars", [])
            if bool(bar.get("anchored", True))
        )
        shear_flange_bars_participating = shear_Ast_available_anchored_flange > 0.0
        shear_longitudinal_tension_increment = abs(float(V_star or 0.0)) * 1000.0
        shear_Ast_required_increment = shear_longitudinal_tension_increment / max(float(fsy or 0.0), 1.0)
        shear_Ast_required_tension_envelope = max(float(A_st or 0.0), float(shear_Ast_required_increment))
        shear_longitudinal_detailing_ok = shear_Ast_available_anchored_active + 1e-9 >= shear_Ast_required_tension_envelope
        # Flange transverse reinforcement is detailing/distribution only and does not
        # contribute to primary web-based shear capacity (Vu).
        wide_flange = float(dims_resolved.get("bf", 0.0) or 0.0) > 1.6 * max(float(dims_resolved.get("bw", dims_resolved.get("tw", 0.0)) or 0.0), 1.0)
        top_tension = active_tension_face == "top"
        bottom_tension = active_tension_face == "bottom"
        has_flange_longitudinal_active = bool(shear_flange_bars_participating)
        has_transverse_on_active_face = (
            (top_tension and flange_transverse_reo_present_top)
            or (bottom_tension and flange_transverse_reo_present_bottom)
        )
        if sec_shape in ("T", "I") and wide_flange and has_flange_longitudinal_active and not has_transverse_on_active_face:
            flange_transverse_detailing_note = (
                "Wide flange tension region has distributed longitudinal bars but no transverse flange "
                "detailing reinforcement is defined. Consider transverse flange bars/ties for crack "
                "distribution, cage stability, and local detailing."
            )
        if sec_shape in ("T", "I") and active_tension_face == "top" and not shear_flange_bars_participating:
            active_tension_warning = (
                "Top tension reinforcement is concentrated in the web. For wide flanges under hogging, "
                "distributed flange bars may be required for realistic crack control and detailing."
            )
    except Exception:
        pass
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.resolve_layout_reinforcement",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    # Build input object
    _section_t0 = time.perf_counter()
    inp = ShearInputs(
        b=b,
        D=D,
        d=d,
        fc=fc,
        fsy=fsy,
        Ec=Ec,
        Es=Es,
        M_star=M_star,
        V_star=V_star,
        T_star=T_star,
        N_star=N_star,
        P_v=P_v,
        phi=phi,
        sigma_cp=sigma_cp,
        A_st=A_st,
        A_pt=A_pt,
        f_po=f_po,
        A_ct=A_ct,
        d_g=d_g,
        lig_d=lig_d,
        legs=legs,
        s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.build_input_object",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )
    
    # Run calculation (session inputs — governs Checks 5–9 and published φVu, etc.)
    _section_t0 = time.perf_counter()
    results = run_shear_calc(inp)
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.run_shear_calc_session",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    L_mm = float(get_param("L", 0.0))
    if not L_mm or L_mm <= 0:
        L_mm = float(get_param("span_L_m", 3.0)) * 1000.0

    _legs_i = int(legs) if abs(legs - round(legs)) < 0.01 else int(round(legs))
    _legs_i = max(_legs_i, 0)

    shear_ok_sectional = bool(float(results.phi_Vu) + 1e-9 >= float(results.V_eq))
    auto_mode = bool(get_param("shear_auto_design", False))
    auto_design_active = bool(get_param("auto_design_active", False))

    zone_results = results
    zone_inp = inp
    zone_lig_d = float(lig_d)
    zone_legs = max(_legs_i, 0)
    shear_design_status: str | None = None
    sel_lig_d_mm: float | None = None
    sel_legs_f: float | None = None
    extra_zone_warnings: list[str] = []

    if shear_ok_sectional:
        shear_design_status = "PASS"
    else:
        shear_design_status = "FAIL"

    if _legs_i < 2 and shear_design_status != "AUTO-DESIGNED":
        shear_design_status = "no_reo"

    shear_zone_payload: dict | None = None
    shear_design_status_out: str | None = None
    _section_t0 = time.perf_counter()
    try:
        from deflection_support import get_deflection_diagram_support_condition

        _sup_lbl = str(
            get_deflection_diagram_support_condition(st.session_state).get("support_type", "") or ""
        )
        _is_cantilever = "cantilever" in _sup_lbl.lower()
        shear_zone_payload = compute_shear_zones(
            L_mm=L_mm,
            d_mm=float(d),
            results=zone_results,
            inp=zone_inp,
            is_cantilever=_is_cantilever,
            lig_d_mm=float(zone_lig_d),
            legs=max(int(zone_legs), 0),
        )
        if shear_zone_payload and extra_zone_warnings:
            _w = list(shear_zone_payload.get("warnings") or [])
            _w.extend(extra_zone_warnings)
            shear_zone_payload = {**shear_zone_payload, "warnings": list(dict.fromkeys(_w))}
        shear_design_status_out = shear_design_status
    except Exception as _zone_exc:
        if "Shear distribution V(x) must be defined" in str(_zone_exc):
            raise ValueError(
                "Shear V(x) is required for zoned shear design. Run SFD/BMD or enable synthetic distribution."
            ) from _zone_exc
        else:
            _zone_eq_kN = float(results.V_eq or 0.0)
            if isinstance(_zone_exc, ShearLayoutError) and _zone_eq_kN <= 1e-9:
                shear_zone_payload = {}
                shear_design_status_out = "PASS" if shear_ok_sectional else shear_design_status
                shear_design_status = shear_design_status_out
                _zone_exc = None
            else:
                _failed_payload = getattr(_zone_exc, "payload", None)
                _phi_vu_current = float(results.phi_Vu or 0.0)
                _vu_util_current = (float(results.V_eq) / _phi_vu_current) if _phi_vu_current > 0.0 else float("nan")
                _phi_vu_max_current = float(inp.phi) * float(results.Vu_max_kN or 0.0)
                _fail_s_end = (
                    float((_failed_payload or {}).get("shear_spacing_end_mm", 0.0) or 0.0)
                    if isinstance(_failed_payload, dict)
                    else None
                )
                _fail_req_mm = (
                    float(_fail_s_end) if _fail_s_end is not None and float(_fail_s_end) > 0.0 else None
                )
                _fail_eff_mm = float(inp.s_lig)
                _fail_truth = resolve_shear_spacing_truth(
                    provided_spacing_mm=float(inp.s_lig),
                    required_spacing_mm=_fail_req_mm,
                    effective_spacing_mm=_fail_eff_mm,
                )
                if isinstance(_failed_payload, dict):
                    _failed_payload = {
                        **_failed_payload,
                        "provided_spacing_mm": float(inp.s_lig),
                        "required_spacing_mm": _fail_req_mm,
                        "effective_spacing_mm": _fail_eff_mm,
                        "governing_spacing_source": str(_fail_truth.get("governing_spacing_source") or ""),
                    }
                _gov_fail = str(_fail_truth.get("governing_spacing_source") or "")
                _fail_governing_util = None if math.isnan(_vu_util_current) else _vu_util_current
                _fail_canonical = _resolve_canonical_shear_truth(
                    sectional_ok=bool(getattr(results, "shear_ok", False)),
                    envelope_ok=False,
                    governing_util=_fail_governing_util,
                    governing_reason=f"zone_failure: {str(_zone_exc)[:400]}",
                    governing_source="zone_compute_error",
                    s_eff_mm=_fail_eff_mm,
                    s_req_mm=_fail_req_mm,
                    provided_spacing_mm=float(inp.s_lig),
                )
                _fail_contradiction_detected = False
                _fail_contradiction_reason = ""
                if _fail_governing_util is not None and float(_fail_governing_util) <= 1.0 + SHEAR_TRUTH_EPS:
                    _fail_contradiction_detected = True
                    _fail_contradiction_reason = "published_fail_with_governing_util_lte_1"
                _nf_zone = _normalise_final_shear_publication(
                    shear_design_status_out=str(_fail_canonical.get("canonical_shear_status") or "FAIL"),
                    final_shear_status_source="canonical_skipped_zone_compute_error",
                    final_shear_truth_resolved=False,
                    final_shear_truth_failure_reason="zone_compute_error",
                    shear_util_governing_out=_fail_governing_util,
                    canonical_pub=None,
                    zone_payload=_failed_payload if isinstance(_failed_payload, dict) else None,
                    session_state=st.session_state,
                    provided_mm=float(inp.s_lig),
                    required_mm=_fail_req_mm,
                    effective_mm=_fail_eff_mm,
                    governing_spacing_source=_gov_fail,
                )
                _zone_spacing_reason = str(_nf_zone.get("final_shear_spacing_reason") or "").strip()
                if not _zone_spacing_reason:
                    _zone_spacing_reason = (
                        "Zone compute failure path; spacing uses best-available sectional input and any partial envelope data."
                    )
                _zone_spacing_reason = (
                    f"{_zone_spacing_reason} Publication path: zone_failure_invalid (compute_shear_zones exception)."
                )
                _nf_zone = {**_nf_zone, "final_shear_spacing_reason": _zone_spacing_reason}
                if isinstance(_failed_payload, dict):
                    _failed_payload = {
                        **_failed_payload,
                        "final_shear_publication_path": "zone_failure_invalid",
                        "final_shear_status_source": _nf_zone["final_shear_status_source"],
                        "final_shear_truth_resolved": _nf_zone["final_shear_truth_resolved"],
                        "final_shear_truth_failure_reason": _nf_zone["final_shear_truth_failure_reason"],
                        "published_result_spacing_mm": _nf_zone["published_result_spacing_mm"],
                        "published_result_spacing_meaning": _nf_zone["published_result_spacing_meaning"],
                        "final_shear_spacing_reason": _nf_zone["final_shear_spacing_reason"],
                    }
                update_results(
                phi_Vu_cap=_phi_vu_current,
                Vu_utilisation=_vu_util_current if not math.isnan(_vu_util_current) else 0.0,
                phi_Vu_max_kN=_phi_vu_max_current,
                V_eq_kN=float(results.V_eq or 0.0),
                shear_zone_results=_failed_payload,
                shear_design_status=_nf_zone["shear_design_status_out"],
                shear_design_error=str(_zone_exc),
                shear_x=(_failed_payload or {}).get("shear_x", []),
                shear_V=(_failed_payload or {}).get("shear_V", []),
                V_max=float((_failed_payload or {}).get("V_max", 0.0) or 0.0),
                req_asv_s=(_failed_payload or {}).get("req_asv_s", []),
                prov_asv_s=(_failed_payload or {}).get("prov_asv_s", []),
                shear_util_min=_fail_canonical.get("canonical_shear_util"),
                shear_util_x=(_failed_payload or {}).get("shear_util_x", None),
                shear_envelope_status=_fail_canonical.get("canonical_shear_status"),
                shear_k_v=float(results.k_v or 0.0),
                shear_theta_v_deg=float(results.theta_v_deg or 0.0),
                shear_theta_v_rad=float(results.theta_v_rad or 0.0),
                shear_Vuc_kN=float(results.Vuc_kN or 0.0),
                shear_Vus_kN=float(results.Vus_kN or 0.0),
                shear_Vu_total_kN=float(results.Vu_total_kN or 0.0),
                shear_spacing_end_mm=float((_failed_payload or {}).get("shear_spacing_end_mm", 0.0) or 0.0),
                shear_spacing_mid_mm=float((_failed_payload or {}).get("shear_spacing_mid_mm", 0.0) or 0.0),
                shear_s_end=float((_failed_payload or {}).get("shear_s_end", 0.0) or 0.0),
                shear_s_mid=float((_failed_payload or {}).get("shear_s_mid", 0.0) or 0.0),
                shear_mid_spacing_calc_mm=float((_failed_payload or {}).get("shear_mid_spacing_calc_mm", 0.0) or 0.0),
                shear_mid_spacing_mode=str((_failed_payload or {}).get("shear_mid_spacing_mode") or ""),
                V_mid_kN=float((_failed_payload or {}).get("V_mid_kN", 0.0) or 0.0),
                shear_provided_input_spacing_mm=float(inp.s_lig),
                shear_input_spacing_mm=float(inp.s_lig),
                shear_sectional_check_spacing_mm=float(inp.s_lig),
                shear_required_spacing_mm=_fail_req_mm,
                shear_effective_spacing_mm=_fail_eff_mm,
                shear_debug_s_eff_mm=_fail_s_end,
                shear_governing_spacing_source=str(_fail_truth.get("governing_spacing_source") or ""),
                canonical_shear_status=_fail_canonical.get("canonical_shear_status"),
                canonical_shear_ok=bool(_fail_canonical.get("canonical_shear_ok")),
                canonical_shear_util=_fail_canonical.get("canonical_shear_util"),
                canonical_shear_reason=_fail_canonical.get("canonical_shear_reason"),
                canonical_shear_source=_fail_canonical.get("canonical_shear_source"),
                canonical_shear_effective_spacing_mm=_fail_canonical.get("canonical_shear_effective_spacing_mm"),
                canonical_shear_required_spacing_mm=_fail_canonical.get("canonical_shear_required_spacing_mm"),
                canonical_shear_provided_spacing_mm=_fail_canonical.get("canonical_shear_provided_spacing_mm"),
                canonical_shear_spacing_override_active=bool(
                    _fail_canonical.get("canonical_shear_spacing_override_active")
                ),
                canonical_shear_spacing_override_reason=str(
                    _fail_canonical.get("canonical_shear_spacing_override_reason") or ""
                ),
                shear_governing_check_name="Zone compute error",
                shear_governing_demand_kN=float(results.V_eq or 0.0),
                shear_governing_capacity_kN=float(results.phi_Vu or 0.0),
                shear_governing_util=_fail_canonical.get("canonical_shear_util"),
                shear_governing_status=_fail_canonical.get("canonical_shear_status"),
                shear_governing_reason=_fail_canonical.get("canonical_shear_reason"),
                shear_governing_source=_fail_canonical.get("canonical_shear_source"),
                shear_truth_status=_fail_canonical.get("canonical_shear_status"),
                shear_truth_reason=f"zone_failure: {str(_zone_exc)[:400]}",
                shear_truth_inconsistent_status_override=None,
                shear_truth_util_governing=_fail_canonical.get("canonical_shear_util"),
                shear_truth_web_util_governing=None,
                shear_util_governing=_fail_canonical.get("canonical_shear_util"),
                final_shear_status_source=_nf_zone["final_shear_status_source"],
                final_shear_truth_resolved=_nf_zone["final_shear_truth_resolved"],
                final_shear_truth_failure_reason=_nf_zone["final_shear_truth_failure_reason"],
                published_result_spacing_mm=_nf_zone["published_result_spacing_mm"],
                published_result_spacing_meaning=_nf_zone["published_result_spacing_meaning"],
                final_shear_spacing_reason=_nf_zone["final_shear_spacing_reason"],
                final_shear_publication_path="zone_failure_invalid",
                final_shear_truth_bundle_complete=True,
                summary_shear_truth_consume_reason="explicit_final_truth_bundle",
                shear_truth_contradiction_detected=_fail_contradiction_detected,
                shear_truth_contradiction_reason=_fail_contradiction_reason,
                shear_auto_selected_lig_d_mm=None,
                shear_auto_selected_legs=None,
                shear_M_uls_kNm=list(st.session_state.get("shear_M_uls_kNm") or []),
                shear_M_sls_kNm=list(st.session_state.get("shear_M_sls_kNm") or []),
                moment_x=list(st.session_state.get("moment_x") or st.session_state.get("shear_x") or []),
                moment_values=list(
                    st.session_state.get("moment_values") or st.session_state.get("shear_M_sls_kNm") or []
                ),
                crack_bmd_cache_fingerprint=str(st.session_state.get("crack_bmd_cache_fingerprint") or ""),
                bmd_support_positions_m=list(st.session_state.get("bmd_support_positions_m") or []),
                bmd_support_types=list(st.session_state.get("bmd_support_types") or []),
                )
                if isinstance(_zone_exc, ShearLayoutError):
                    shear_zone_payload = _failed_payload if isinstance(_failed_payload, dict) else {}
                    shear_design_status_out = str(_nf_zone.get("shear_design_status_out") or "FAIL")
                    shear_design_status = shear_design_status_out
                elif "V(x)" in str(_zone_exc):
                    raise ValueError("Shear design requires valid V(x) from SFD") from _zone_exc
                else:
                    raise ValueError(str(_zone_exc)) from _zone_exc
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.compute_shear_zones_and_zone_publish",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    # Align sectional Vus check with detailed spacing by using the end-zone governing spacing.
    # Shared/widget s_lig remains the user-provided input; we do not write envelope spacing back.
    _section_t0 = time.perf_counter()
    _s_eff_mm = None
    if isinstance(shear_zone_payload, dict):
        _s_eff_mm = float(shear_zone_payload.get("shear_spacing_end_mm", 0.0) or 0.0)
    # When "Apply auto spacing" is on, re-run the sectional check using governing end-zone spacing only
    # (in-memory); canonical s_lig in session is unchanged.
    if auto_mode and _s_eff_mm is not None and _s_eff_mm > 0.0:
        try:
            results = run_shear_calc(replace(inp, s_lig=float(_s_eff_mm)))
        except Exception as _realign_exc:
            pass
    # Product rule: sectional shear capacity is always checked against the
    # provided spacing input. Zone/end required spacing remains available as
    # detailing/report context only; it must not replace the provided spacing
    # in the φVu calculation.
    _s_used_for_vus = float(inp.s_lig)
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.auto_spacing_realign",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    # Calculate utilisation
    shear_util = results.V_eq / results.phi_Vu if results.phi_Vu > 0 else float("nan")
    
    # Calculate crushing utilisation (web crushing check)
    # Capacity is phi * Vu_max, demand is V_eq
    phi_Vu_max = phi * results.Vu_max_kN
    Vuc_util = results.V_eq / phi_Vu_max if phi_Vu_max > 0 else float("nan")
    
    # ------------------ Build detailed shear steps (for PDF) ------------------
    _section_t0 = time.perf_counter()
    shear_steps = [
        {
            "title": "Inputs & actions",
            "clause": "AS 3600:2018 Cl. 8.2",
            "formula": ["Given design inputs"],
            "substitution": [
                f"b = {inp.b:.0f} mm, D = {inp.D:.0f} mm, d = {inp.d:.0f} mm",
                f"f'c = {inp.fc:.1f} MPa, f_sy = {inp.fsy:.0f} MPa",
                f"M* = {inp.M_star:.1f} kNm, V* = {inp.V_star:.1f} kN, T* = {inp.T_star:.2f} kNm",
                f"φ = {inp.phi:.2f}",
            ],
            "equations": [
                f"b = {inp.b:.0f} mm, D = {inp.D:.0f} mm, d = {inp.d:.0f} mm",
                f"f'c = {inp.fc:.1f} MPa, f_sy = {inp.fsy:.0f} MPa",
                f"M* = {inp.M_star:.1f} kNm, V* = {inp.V_star:.1f} kN, T* = {inp.T_star:.2f} kNm",
                f"φ = {inp.phi:.2f}",
            ],
            "result": f"V* = {inp.V_star:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Torsion cracking check (screening)",
            "clause": "AS 3600:2018 Cl. 8.2.1",
            "formula": [
                "T_cr = 0.33√f'c · A_cp²/u_c · √(1+σ_cp/(0.33√f'c))",
                "T_req?  T* > 0.25φT_cr",
            ],
            "substitution": [
                f"A_cp = b·D = {results.A_cp:.0f} mm²",
                f"u_c = 2(b + D) = {results.u_c:.0f} mm",
                f"T_cr = {results.Tcr_kNm:.2f} kNm",
                f"T* ? 0.25φT_cr ⇒ {inp.T_star:.2f} ? {results.torsion_required_limit:.2f}",
            ],
            "equations": [
                f"A_cp = b·D = {results.A_cp:.0f} mm²",
                f"u_c = 2(b + D) = {results.u_c:.0f} mm",
                f"T_cr = {results.Tcr_kNm:.2f} kNm",
                f"T_req?  T* > 0.25φT_cr  ⇒  {inp.T_star:.2f} > {results.torsion_required_limit:.2f}",
            ],
            "result": f"Torsion required: {results.torsion_required}",
            "notes": [f"Torsion required: {results.torsion_required}"],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Equivalent shear",
            "clause": "AS 3600:2018 Cl. 8.2.1",
            "formula": [
                "V_t,eq = 0.9·T*·u_h/(2A_o)",
                "V_eq = √(V*² + V_t,eq²)",
            ],
            "substitution": [
                f"V_t,eq = {results.Vt_eq_kN:.1f} kN",
                f"V_eq = √(V*² + V_t,eq²) = {results.V_eq:.1f} kN",
            ],
            "equations": [
                f"V_t,eq = {results.Vt_eq_kN:.1f} kN",
                f"V_eq = √(V*² + V_t,eq²) = {results.V_eq:.1f} kN",
            ],
            "result": f"V_eq = {results.V_eq:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Effective web section",
            "clause": "AS 3600:2018 Cl. 8.2.4",
            "formula": [
                "b_v = b - k_d·Σduct",
                "d_v = max(0.72D, 0.9d)",
            ],
            "substitution": [
                f"b_v = {results.b_v:.1f} mm",
                f"d_v = max(0.72D, 0.9d) = {results.d_v:.1f} mm",
            ],
            "equations": [
                f"b_v = {results.b_v:.1f} mm",
                f"d_v = max(0.72D, 0.9d) = {results.d_v:.1f} mm",
            ],
            "result": f"b_v={results.b_v:.1f} mm, d_v={results.d_v:.1f} mm",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Longitudinal strain εx",
            "clause": "AS 3600:2018 Cl. 8.2.4",
            "formula": [
                "εx = (|M*|/d_v + √(V'² + T'²) + N* - A_pt f_po) / (2(EsAst + EpApt) ...)",
            ],
            "substitution": [
                f"term_M = |M*|/d_v = {results.term_M:.3e}",
                f"√(V'² + T'²) = {results.sqrt_inner:.3e}",
                f"εx = {results.eps_x:.6f}",
            ],
            "equations": [
                f"term_M = |M*|/d_v = {results.term_M:.3e}",
                f"√(V'² + T'²) = {results.sqrt_inner:.3e}",
                f"εx = {results.eps_x:.6f}",
            ],
            "result": f"εx = {results.eps_x:.6f}",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "MCFT parameters (k_v, θ_v)",
            "clause": "AS 3600:2018 Cl. 8.2.4",
            "formula": [
                "k_v = f(εx, d_v, aggregate size)",
                "θ_v = f(εx)",
            ],
            "substitution": [
                f"k_v = {results.k_v:.3f}",
                f"θ_v = {results.theta_v_deg:.1f}°",
            ],
            "equations": [
                f"k_v = {results.k_v:.3f}",
                f"θ_v = {results.theta_v_deg:.1f}°",
            ],
            "result": f"k_v={results.k_v:.3f}, θ_v={results.theta_v_deg:.1f}°",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Concrete shear capacity V_uc",
            "clause": "AS 3600:2018 Cl. 8.2.4.1",
            "formula": [
                "V_uc = k_v · b_v · d_v · min(√f'c, 8)",
                "φV_uc = φ · V_uc",
            ],
            "substitution": [
                f"= {results.k_v:.3f} · {results.b_v:.0f} · {results.d_v:.0f} · min(√{inp.fc:.1f}, 8)",
                f"= {results.Vuc_kN:.1f} kN",
            ],
            "equations": [
                f"V_uc = {results.Vuc_kN:.1f} kN",
            ],
            "result": f"V_uc = {results.Vuc_kN:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Steel shear capacity V_us",
            "clause": "AS 3600:2018 Cl. 8.2.7",
            "formula": [
                "V_us = (A_sv · f_syv · d_v / s) · cotθ_v",
            ],
            "substitution": [
                f"Effective spacing s in V_us = {_s_used_for_vus:.0f} mm "
                f"(provided input s_lig = {float(inp.s_lig):.0f} mm)",
                f"= ({results.Asv:.1f} · {results.f_syv:.0f} · {results.d_v:.0f} / {_s_used_for_vus:.0f}) · cot{results.theta_v_deg:.1f}°",
                f"= {results.Vus_kN:.1f} kN",
            ],
            "equations": [
                f"V_us = {results.Vus_kN:.1f} kN",
            ],
            "result": f"V_us = {results.Vus_kN:.1f} kN",
            "notes": [],
            "status": "info",
            "diagram": None,
        },
        {
            "title": "Total shear capacity & utilisation",
            "clause": "AS 3600:2018 Cl. 8.2",
            "formula": [
                "V_u = V_uc + V_us + P_v",
                "φV_u = φ · V_u",
                "Util = V_eq/(φV_u)",
            ],
            "substitution": [
                f"V_u = {results.Vu_total_kN:.1f} kN",
                f"φV_u = {results.phi_Vu:.1f} kN",
                f"Util = {results.V_eq:.1f}/{results.phi_Vu:.1f} = "
                f"{(results.V_eq/results.phi_Vu if results.phi_Vu>0 else 0):.2f}",
            ],
            "equations": [
                f"V_u = V_uc + V_us + P_v = {results.Vu_total_kN:.1f} kN",
                f"φV_u = {results.phi_Vu:.1f} kN",
                f"Util = V_eq/(φV_u) = {results.V_eq:.1f}/{results.phi_Vu:.1f} = "
                f"{(results.V_eq/results.phi_Vu if results.phi_Vu>0 else 0):.2f}",
            ],
            "result": f"φV_u = {results.phi_Vu:.1f} kN",
            "notes": [("PASS" if results.shear_ok else "FAIL")],
            "status": ("pass" if results.shear_ok else "fail"),
            "diagram": None,
        },
        {
            "title": "Web crushing check",
            "clause": "AS 3600:2018 Cl. 8.2.5",
            "formula": [
                "V_u,max = 0.55 f'c b_v d_v (cotθ_v + cotθ_1) / (1 + cot²θ_v) + P_v",
                "Check: LHS ≤ RHS",
            ],
            "substitution": [
                f"V_u,max = {results.Vu_max_kN:.1f} kN",
                f"LHS = {results.LHS:.3e}, RHS = {results.RHS:.3e}",
            ],
            "equations": [
                f"V_u,max = {results.Vu_max_kN:.1f} kN",
                f"LHS = {results.LHS:.3e}, RHS = {results.RHS:.3e}",
            ],
            "result": f"V_u,max = {results.Vu_max_kN:.1f} kN",
            "notes": [("PASS" if results.web_ok else "FAIL")],
            "status": ("pass" if results.web_ok else "fail"),
            "diagram": None,
        },
    ]
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.build_shear_steps",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )

    # Keep the engineering steps payload, but lazily build the heavy diagram/report
    # tree only when a report/detail consumer explicitly asks for it.
    shear_report = {}


    def _resample_y_on_new_x(old_x: list[float], old_y: list[float], new_x: list[float]) -> list[float]:
        if len(old_x) < 2 or len(new_x) < 2 or len(old_y) != len(old_x):
            return list(old_y)
        if len(old_x) == len(new_x) and max(abs(old_x[i] - new_x[i]) for i in range(len(old_x))) < 1e-9:
            return list(old_y)
        try:
            return [
                float(v)
                for v in np.interp(
                    np.asarray(new_x, dtype=float),
                    np.asarray(old_x, dtype=float),
                    np.asarray(old_y, dtype=float),
                ).tolist()
            ]
        except Exception:
            return list(old_y)

    _sx_new = [float(v) for v in ((shear_zone_payload or {}).get("shear_x", []) or [])]
    _sx_prev = [float(v) for v in (st.session_state.get("shear_x", []) or [])]
    _m_sls_prev = [float(v) for v in (st.session_state.get("shear_M_sls_kNm") or [])]
    _m_uls_prev = [float(v) for v in (st.session_state.get("shear_M_uls_kNm") or [])]
    _m_sls_resampled = _resample_y_on_new_x(_sx_prev, _m_sls_prev, _sx_new)
    _m_uls_resampled = _resample_y_on_new_x(_sx_prev, _m_uls_prev, _sx_new)

    # Update session state — final published shear status/spacing truth from canonical contract
    _prov_in = float(inp.s_lig)
    _required_mm = float(_s_eff_mm) if _s_eff_mm is not None and float(_s_eff_mm) > 0.0 else None
    _effective_mm = float(_s_used_for_vus)
    _spacing_truth = resolve_shear_spacing_truth(
        provided_spacing_mm=_prov_in,
        required_spacing_mm=_required_mm,
        effective_spacing_mm=_effective_mm,
    )
    _gov_src = str(_spacing_truth.get("governing_spacing_source") or "")

    _section_t0 = time.perf_counter()
    _canonical_pub: dict | None = None
    _canonical_truth_payload = _resolve_canonical_shear_truth(
        sectional_ok=bool(getattr(results, "shear_ok", False)),
        envelope_ok=None,
        governing_util=None,
        governing_reason="canonical_truth_not_computed",
        governing_source="pre_publish_default",
        s_eff_mm=_effective_mm,
        s_req_mm=_required_mm,
        provided_spacing_mm=_prov_in,
    )
    _final_shear_status_source = "sectional_zone_or_invalid_skip"
    _final_shear_truth_resolved = False
    _final_shear_truth_failure_reason: str | None = None
    _shear_util_governing_out: float | None = None

    if shear_design_status_out == "AUTO-DESIGNED":
        _final_shear_status_source = "auto_designed_reserved"
        _final_shear_truth_resolved = False
        _final_shear_truth_failure_reason = "canonical_skipped_auto_designed_reserved"
    elif (
        shear_design_status_out is not None
        and str(shear_design_status_out).strip().upper() != "INVALID"
        and shear_design_status_out != "no_reo"
        and _legs_i >= 2
    ):
        try:
            _canonical_pub = compute_canonical_shear_truth(
                dict(st.session_state),
                zone_payload=shear_zone_payload if isinstance(shear_zone_payload, dict) else None,
                provided_spacing_mm=_prov_in,
                required_spacing_mm=_required_mm,
                effective_spacing_mm=_effective_mm,
            )
            _spacing_truth = dict(_canonical_pub.get("shear_spacing_truth") or _spacing_truth)
            _gov_src = str(_spacing_truth.get("governing_spacing_source") or _gov_src)
            _truth_st = str(_canonical_pub.get("shear_truth_status") or "").strip()
            try:
                _ur_g = _canonical_pub.get("shear_governing_util")
                if _ur_g is None:
                    _ur_g = _canonical_pub.get("shear_util_governing")
                _fv_g = float(_ur_g) if _ur_g is not None else float("nan")
                _shear_util_governing_out = (
                    None if (math.isnan(_fv_g) or math.isinf(_fv_g)) else float(_fv_g)
                )
            except (TypeError, ValueError):
                _shear_util_governing_out = None

            _canonical_truth_payload = _resolve_canonical_shear_truth(
                sectional_ok=bool(getattr(results, "shear_ok", False)),
                envelope_ok=(str((shear_zone_payload or {}).get("shear_envelope_status") or "").strip().upper() == "PASS"),
                governing_util=_shear_util_governing_out,
                governing_reason=str(
                    _canonical_pub.get("shear_governing_reason")
                    or _canonical_pub.get("shear_truth_reason")
                    or ""
                ),
                governing_source=str(
                    _canonical_pub.get("shear_governing_source")
                    or _canonical_pub.get("shear_truth_governing_source")
                    or _truth_st
                    or "canonical_shear_truth"
                ),
                s_eff_mm=_effective_mm,
                s_req_mm=_required_mm,
                provided_spacing_mm=_prov_in,
            )
            shear_design_status_out = str(_canonical_truth_payload.get("canonical_shear_status") or "FAIL")
            _final_shear_status_source = str(
                _canonical_truth_payload.get("canonical_shear_source") or "canonical_shear_truth"
            )
            _final_shear_truth_resolved = bool(
                _canonical_truth_payload.get("canonical_shear_resolved")
            )
            _final_shear_truth_failure_reason = (
                None if _final_shear_truth_resolved else str(_canonical_truth_payload.get("canonical_shear_reason") or "canonical_truth_unresolved_status")
            )
        except Exception:
            _canonical_pub = None
            _shear_util_governing_out = None
            _canonical_truth_payload = _resolve_canonical_shear_truth(
                sectional_ok=bool(getattr(results, "shear_ok", False)),
                envelope_ok=(str((shear_zone_payload or {}).get("shear_envelope_status") or "").strip().upper() == "PASS"),
                governing_util=None,
                governing_reason="canonical_truth_exception",
                governing_source="canonical_shear_truth_error_nonpass_fallback",
                s_eff_mm=_effective_mm,
                s_req_mm=_required_mm,
                provided_spacing_mm=_prov_in,
            )
            _final_shear_status_source = "canonical_shear_truth_error_nonpass_fallback"
            shear_design_status_out = "FAIL"
            _final_shear_truth_failure_reason = "canonical_truth_exception"
            _final_shear_truth_resolved = False

    _nf = _normalise_final_shear_publication(
        shear_design_status_out=shear_design_status_out,
        final_shear_status_source=_final_shear_status_source,
        final_shear_truth_resolved=_final_shear_truth_resolved,
        final_shear_truth_failure_reason=_final_shear_truth_failure_reason,
        shear_util_governing_out=_shear_util_governing_out,
        canonical_pub=_canonical_pub,
        zone_payload=shear_zone_payload if isinstance(shear_zone_payload, dict) else None,
        session_state=st.session_state,
        provided_mm=_prov_in,
        required_mm=_required_mm,
        effective_mm=_effective_mm,
        governing_spacing_source=_gov_src,
    )
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.canonical_truth_and_publication_normalization",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="compute",
    )
    shear_design_status_out = _nf["shear_design_status_out"]
    _final_shear_status_source = _nf["final_shear_status_source"]
    _final_shear_truth_resolved = _nf["final_shear_truth_resolved"]
    _final_shear_truth_failure_reason = _nf["final_shear_truth_failure_reason"]
    _published_result_spacing_mm = _nf["published_result_spacing_mm"]
    _published_result_spacing_meaning = _nf["published_result_spacing_meaning"]
    _final_shear_spacing_reason = _nf["final_shear_spacing_reason"]
    _canonical_shear_status = str(_canonical_truth_payload.get("canonical_shear_status") or shear_design_status_out or "FAIL")
    _canonical_shear_util = _canonical_truth_payload.get("canonical_shear_util")
    _canonical_shear_reason = str(_canonical_truth_payload.get("canonical_shear_reason") or _final_shear_truth_failure_reason or "")
    _canonical_shear_source = str(_canonical_truth_payload.get("canonical_shear_source") or _final_shear_status_source or "")
    _shear_governing_check_name = str((_canonical_pub or {}).get("shear_governing_check_name") or "")
    _shear_governing_demand_kN = (_canonical_pub or {}).get("shear_governing_demand_kN")
    _shear_governing_capacity_kN = (_canonical_pub or {}).get("shear_governing_capacity_kN")
    _shear_governing_status = str((_canonical_pub or {}).get("shear_governing_status") or _canonical_shear_status or "")
    _shear_governing_reason = str((_canonical_pub or {}).get("shear_governing_reason") or _canonical_shear_reason or "")
    _shear_governing_source = str((_canonical_pub or {}).get("shear_governing_source") or _canonical_shear_source or "")
    _shear_governing_util = (_canonical_pub or {}).get("shear_governing_util")
    if _shear_governing_util is None:
        _shear_governing_util = _canonical_shear_util
    _canonical_shear_spacing_override_active = bool(
        (_canonical_pub or {}).get("canonical_shear_spacing_override_active")
    )
    _canonical_shear_spacing_override_reason = str(
        (_canonical_pub or {}).get("canonical_shear_spacing_override_reason") or ""
    )
    _shear_truth_contradiction_detected = False
    _shear_truth_contradiction_reason = ""
    try:
        if _canonical_shear_util is not None:
            if _canonical_shear_status == "PASS" and float(_canonical_shear_util) > 1.0 + SHEAR_TRUTH_EPS:
                _shear_truth_contradiction_detected = True
                _shear_truth_contradiction_reason = "published_pass_with_governing_util_gt_1"
            elif _canonical_shear_status == "FAIL" and float(_canonical_shear_util) <= 1.0 + SHEAR_TRUTH_EPS:
                _shear_truth_contradiction_detected = True
                _shear_truth_contradiction_reason = "published_fail_with_governing_util_lte_1"
    except (TypeError, ValueError):
        pass

    if isinstance(shear_zone_payload, dict):
        _zp_merge = {
            **shear_zone_payload,
            "raw_shear_envelope_status": shear_zone_payload.get("shear_envelope_status"),
            "raw_shear_util_min": shear_zone_payload.get("shear_util_min"),
            "provided_spacing_mm": _prov_in,
            "required_spacing_mm": _required_mm,
            "effective_spacing_mm": _effective_mm,
            "governing_spacing_source": _gov_src,
            "final_shear_status_source": _final_shear_status_source,
            "final_shear_truth_resolved": _final_shear_truth_resolved,
            "final_shear_truth_failure_reason": _final_shear_truth_failure_reason,
            "published_result_spacing_mm": _published_result_spacing_mm,
            "published_result_spacing_meaning": _published_result_spacing_meaning,
            "final_shear_spacing_reason": _final_shear_spacing_reason,
            "canonical_shear_status": _canonical_shear_status,
            "canonical_shear_util": _canonical_shear_util,
            "canonical_shear_reason": _canonical_shear_reason,
            "canonical_shear_source": _canonical_shear_source,
            "canonical_shear_spacing_override_active": _canonical_shear_spacing_override_active,
            "canonical_shear_spacing_override_reason": _canonical_shear_spacing_override_reason,
            "shear_governing_check_name": _shear_governing_check_name,
            "shear_governing_demand_kN": _shear_governing_demand_kN,
            "shear_governing_capacity_kN": _shear_governing_capacity_kN,
            "shear_governing_util": _shear_governing_util,
            "shear_governing_status": _shear_governing_status,
            "shear_governing_reason": _shear_governing_reason,
            "shear_governing_source": _shear_governing_source,
        }
        if _canonical_pub:
            _zp_merge.update(
                {
                    "shear_truth_status": _canonical_pub.get("shear_truth_status"),
                    "shear_truth_reason": _canonical_pub.get("shear_truth_reason"),
                    "shear_truth_inconsistent_status_override": _canonical_pub.get(
                        "shear_truth_inconsistent_status_override"
                    ),
                    "shear_truth_util_governing": _canonical_pub.get("shear_util_governing"),
                    "shear_truth_web_util_governing": _canonical_pub.get("web_util_governing"),
                    "shear_util_governing": _shear_util_governing_out,
                },
            )
        elif _shear_util_governing_out is not None:
            _zp_merge["shear_util_governing"] = _shear_util_governing_out
        shear_zone_payload = _zp_merge
    _section_t0 = time.perf_counter()
    update_results(
        phi_Vu_cap=results.phi_Vu,
        Vu_utilisation=shear_util if not math.isnan(shear_util) else 0.0,
        Vu_max_kN=results.Vu_max_kN,
        phi_Vu_max_kN=phi_Vu_max,
        V_eq_kN=results.V_eq,
        Vuc_utilisation=Vuc_util if not math.isnan(Vuc_util) else None,
        shear_longitudinal_tension_increment=float(shear_longitudinal_tension_increment),
        shear_Ast_required_tension_envelope=float(shear_Ast_required_tension_envelope),
        shear_Ast_available_anchored_active=float(shear_Ast_available_anchored_active),
        shear_Ast_available_anchored_web=float(shear_Ast_available_anchored_web),
        shear_Ast_available_anchored_flange=float(shear_Ast_available_anchored_flange),
        shear_flange_bars_participating=bool(shear_flange_bars_participating),
        shear_longitudinal_detailing_ok=bool(shear_longitudinal_detailing_ok),
        active_tension_face=active_tension_face,
        active_tension_Ast_mm2=float(A_st or 0.0),
        active_tension_width_mm=float(active_tension_width_mm),
        active_tension_flange_participating=bool(shear_flange_bars_participating),
        active_tension_warning=active_tension_warning,
        flange_transverse_reo_present_top=bool(flange_transverse_reo_present_top),
        flange_transverse_reo_present_bottom=bool(flange_transverse_reo_present_bottom),
        flange_transverse_spacing_top=float(flange_transverse_spacing_top),
        flange_transverse_spacing_bottom=float(flange_transverse_spacing_bottom),
        flange_transverse_detailing_note=flange_transverse_detailing_note,
        shear_steps=shear_steps,
        shear_report=shear_report,
        shear_zone_results=shear_zone_payload,
        shear_design_error=None,
        shear_x=(shear_zone_payload or {}).get("shear_x", []),
        shear_V=(shear_zone_payload or {}).get("shear_V", []),
        V_max=float((shear_zone_payload or {}).get("V_max", 0.0) or 0.0),
        req_asv_s=(shear_zone_payload or {}).get("req_asv_s", []),
        prov_asv_s=(shear_zone_payload or {}).get("prov_asv_s", []),
        shear_util_min=_canonical_shear_util,
        shear_util_x=(shear_zone_payload or {}).get("shear_util_x", None),
        shear_envelope_status=_canonical_shear_status,
        shear_k_v=float(results.k_v),
        shear_theta_v_deg=float(results.theta_v_deg),
        shear_theta_v_rad=float(results.theta_v_rad),
        shear_Vuc_kN=float(results.Vuc_kN),
        shear_Vus_kN=float(results.Vus_kN),
        shear_Vu_total_kN=float(results.Vu_total_kN),
        shear_spacing_end_mm=float((shear_zone_payload or {}).get("shear_spacing_end_mm", 0.0) or 0.0),
        shear_spacing_mid_mm=float((shear_zone_payload or {}).get("shear_spacing_mid_mm", 0.0) or 0.0),
        shear_spacing_governing=(shear_zone_payload or {}).get("shear_spacing_governing"),
        shear_spacing_profile_min=(shear_zone_payload or {}).get("shear_spacing_profile_min"),
        shear_spacing_profile_max=(shear_zone_payload or {}).get("shear_spacing_profile_max"),
        shear_s_end=float((shear_zone_payload or {}).get("shear_s_end", 0.0) or 0.0),
        shear_s_mid=float((shear_zone_payload or {}).get("shear_s_mid", 0.0) or 0.0),
        shear_mid_spacing_calc_mm=float((shear_zone_payload or {}).get("shear_mid_spacing_calc_mm", 0.0) or 0.0),
        shear_mid_spacing_mode=str((shear_zone_payload or {}).get("shear_mid_spacing_mode") or ""),
        V_mid_kN=float((shear_zone_payload or {}).get("V_mid_kN", 0.0) or 0.0),
        shear_provided_input_spacing_mm=_prov_in,
        shear_input_spacing_mm=_prov_in,
        shear_sectional_check_spacing_mm=_effective_mm,
        shear_required_spacing_mm=_required_mm,
        shear_effective_spacing_mm=_effective_mm,
        shear_debug_s_eff_mm=float(_s_eff_mm) if _s_eff_mm is not None else _effective_mm,
        shear_governing_spacing_source=_gov_src,
        canonical_shear_status=_canonical_shear_status,
        canonical_shear_ok=bool(_canonical_truth_payload.get("canonical_shear_ok")),
        canonical_shear_util=_canonical_shear_util,
        canonical_shear_reason=_canonical_shear_reason,
        canonical_shear_source=_canonical_shear_source,
        canonical_shear_effective_spacing_mm=_canonical_truth_payload.get("canonical_shear_effective_spacing_mm"),
        canonical_shear_required_spacing_mm=_canonical_truth_payload.get("canonical_shear_required_spacing_mm"),
        canonical_shear_provided_spacing_mm=_canonical_truth_payload.get("canonical_shear_provided_spacing_mm"),
        canonical_shear_spacing_override_active=_canonical_shear_spacing_override_active,
        canonical_shear_spacing_override_reason=_canonical_shear_spacing_override_reason,
        shear_governing_check_name=_shear_governing_check_name,
        shear_governing_demand_kN=_shear_governing_demand_kN,
        shear_governing_capacity_kN=_shear_governing_capacity_kN,
        shear_governing_util=_shear_governing_util,
        shear_governing_status=_shear_governing_status,
        shear_governing_reason=_shear_governing_reason,
        shear_governing_source=_shear_governing_source,
        shear_design_status=shear_design_status_out,
        shear_truth_status=(_canonical_pub or {}).get("shear_truth_status"),
        shear_truth_reason=(_canonical_pub or {}).get("shear_truth_reason"),
        shear_truth_inconsistent_status_override=(_canonical_pub or {}).get(
            "shear_truth_inconsistent_status_override"
        ),
        shear_truth_util_governing=(_canonical_pub or {}).get("shear_util_governing"),
        shear_truth_web_util_governing=(_canonical_pub or {}).get("web_util_governing"),
        shear_util_governing=_shear_util_governing_out,
        final_shear_status_source=_final_shear_status_source,
        final_shear_truth_resolved=_final_shear_truth_resolved,
        final_shear_truth_failure_reason=_final_shear_truth_failure_reason,
        published_result_spacing_mm=_published_result_spacing_mm,
        published_result_spacing_meaning=_published_result_spacing_meaning,
        final_shear_spacing_reason=_final_shear_spacing_reason,
        final_shear_truth_bundle_complete=True,
        summary_shear_truth_consume_reason="explicit_final_truth_bundle",
        shear_truth_contradiction_detected=_shear_truth_contradiction_detected,
        shear_truth_contradiction_reason=_shear_truth_contradiction_reason,
        shear_auto_selected_lig_d_mm=sel_lig_d_mm,
        shear_auto_selected_legs=sel_legs_f,
        shear_M_uls_kNm=_m_uls_resampled,
        shear_M_sls_kNm=_m_sls_resampled,
        moment_x=_sx_new,
        moment_values=_m_sls_resampled,
        crack_bmd_cache_fingerprint=str(st.session_state.get("crack_bmd_cache_fingerprint") or ""),
        bmd_support_positions_m=list(st.session_state.get("bmd_support_positions_m") or []),
        bmd_support_types=list(st.session_state.get("bmd_support_types") or []),
    )
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.update_results",
        (time.perf_counter() - _section_t0) * 1000.0,
        category="state_mutation",
    )
    speed_profile_record(
        "derived_result_computation.shear_capacity._compute_shear_capacity.total",
        (time.perf_counter() - _compute_shear_capacity_t0) * 1000.0,
        category="compute",
    )


    return {
        "phi_Vu_cap": results.phi_Vu,
        "Vu_utilisation": shear_util,
        "V_eq": results.V_eq,
        "Vuc_kN": results.Vuc_kN,
        "Vus_kN": results.Vus_kN,
        "shear_ok": results.shear_ok,
    }
