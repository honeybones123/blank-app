# bending_page_runtime.py
# ============================
# BENDING PAGE
# ============================

import math
import streamlit as st

from state_and_helpers import (
    get_sync_callbacks,
    get_param,
    update_results,
    debug_print,
    get_widget_key_for_shared,
    load_proxies_from_active_set,
    save_proxies_to_active_set,
    recalc_derived_values,
    resolve_design_actions,
    render_timing_mark,
)
from widgets_helpers import (
    apply_result_page_css,
    number_row,
    select_row,
    show_reo_message,
    apply_step_expander_css,
    apply_step_summary_expander_css,
    info_i_button,
    page_divider,
    render_lazy_expander,
    render_page_explainer_expander,
    render_section_title,
    render_result_page_title,
    render_longitudinal_reo_rows,
    render_longitudinal_reo_row_config_controls,
    main_longitudinal_reo_pair_labels,
    normalized_sec_shape_ui,
    render_plotly_diagram,
    render_pyplot_diagram,
)
from bending_core import (
    _fmt,
    _compute_bending_capacity,
    _stress_strain_state,
    compute_sls_bending_values_from_state,
    hogging_tension_effective_depth_mm,
    solve_bending_capacity,
)
from bending_checks_helpers import build_bending_check_rows_from_state
from inputs_application.authoritative_check_packs import current_authoritative_family
from calculations.bending import (
    bar_area_mm2,
    bottom_tension_effective_depth_fallback_mm,
    compression_block_lever_arm_values,
    minimum_moment_capacity_kNm,
    nominal_capacity_from_phi_capacity_kNm,
    sls_report_display_values,
    stress_block_factors,
    uls_bending_report_values,
)
from engineering_check_ui import (
    ENGINEERING_CHECK_COLUMNS,
    resolve_jump_target_id,
)
from ui.summary_rows import (
    build_bending_clickable_summary_rows,
)
from ui_seamless_steps import (
    inject_seamless_steps_css,
    render_clickable_summary_table,
    bind_summary_clicks,
    step_card,
)
from engineering_page_sections.compact_check_inputs import (
    CheckInputCategory,
    CheckInputPanelConfig,
    InputSource,
    compact_check_input_regions,
    format_dimensions,
    format_number,
    join_summary,
)
from engineering_page_sections.stable_tabs import (
    render_stable_tabs,
)
from inputs_application.action_source_control import uses_load_analysis_actions


def _plot_stress_strain_profiles(*args, **kwargs):
    from bending_diagrams import _plot_stress_strain_profiles as renderer

    return renderer(*args, **kwargs)


def _plot_material_stress_strain_curves(*args, **kwargs):
    from bending_diagrams import _plot_material_stress_strain_curves as renderer

    return renderer(*args, **kwargs)


def _shared_build_beam_3d_figure_pure(*args, **kwargs):
    from ui.diagrams.bending_3d_diagram import build_beam_3d_figure_pure as builder

    return builder(*args, **kwargs)


def figure_bmd_from_state(*args, **kwargs):
    from ui.diagrams.moment_shear_diagram import figure_bmd_from_state as builder

    return builder(*args, **kwargs)

# Safe option lists for reinforcement inputs
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
REO_COUNTS_0_12 = list(range(0, 13))
REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_LAYOUT_MODE = ["Count", "Spacing"]


def _overlay_authoritative_bending_result(target, bending, ductility, default_depth):
    """Project the published V2 result into the existing detail-renderer shape."""

    if not bending:
        return
    target.update({
        "_authoritative_uls": True,
        "phi_Mu_cap": float(bending.get("phi_Mu_kNm", 0.0) or 0.0),
        "phi_Mu_kNm": float(bending.get("phi_Mu_kNm", 0.0) or 0.0),
        "Mu_util": float(bending.get("util", 0.0) or 0.0),
        "util": float(bending.get("util", 0.0) or 0.0),
        "Mu_nom": float(bending.get("Mu_nom_kNm", 0.0) or 0.0),
        "Mu_nom_kNm": float(bending.get("Mu_nom_kNm", 0.0) or 0.0),
        "phi": float(bending.get("phi", 0.65) or 0.65),
        "ku": float(bending.get("ku", 0.0) or 0.0),
        "c": float(bending.get("dn_mm", 0.0) or 0.0),
        "dn_mm": float(bending.get("dn_mm", 0.0) or 0.0),
        "a": float(bending.get("block_depth_mm", 0.0) or 0.0),
        "z": float(bending.get("resultant_lever_arm_mm", 0.0) or 0.0),
        "d": float(bending.get("d_mm", default_depth) or default_depth),
        "d_mm": float(bending.get("d_mm", default_depth) or default_depth),
        "alpha2": float(bending.get("alpha2", 0.0) or 0.0),
        "gamma": float(bending.get("gamma", 0.0) or 0.0),
        "section_shape": str(bending.get("section_shape", "RECT") or "RECT"),
        "T_N": float(bending.get("tension_force_n", 0.0) or 0.0),
        "C_concrete_N": float(bending.get("concrete_force_n", 0.0) or 0.0),
        "C_steel_N": float(bending.get("compression_steel_force_n", 0.0) or 0.0),
        "compression_concrete_area_mm2": float(bending.get("compression_concrete_area_mm2", 0.0) or 0.0),
        "concrete_centroid_mm": float(bending.get("concrete_centroid_mm", 0.0) or 0.0),
        "equilibrium_residual_n": float(bending.get("equilibrium_residual_n", 0.0) or 0.0),
        "neutral_axis_iteration_trace": tuple(bending.get("neutral_axis_iteration_trace", ()) or ()),
        "steel_layer_stresses_mpa": tuple(bending.get("steel_layer_stresses_mpa", ()) or ()),
        "steel_layer_areas_mm2": tuple(bending.get("steel_layer_areas_mm2", ()) or ()),
        "steel_layer_labels": tuple(bending.get("steel_layer_labels", ()) or ()),
        "steel_layer_faces": tuple(bending.get("steel_layer_faces", ()) or ()),
        "steel_layer_forces_n": tuple(bending.get("steel_layer_forces_n", ()) or ()),
        # Preserve the authoritative reinforcement coordinates as well as the
        # forces/stresses.  The detail cards must not relabel effective depth
        # ``d`` as the steel-layer coordinate ``y_s``.
        "steel_layer_depths_mm": tuple(bending.get("steel_layer_depths_mm", ()) or ()),
    })
    if ductility:
        target.update({
            "ductility_status": str(ductility.get("status", "NOT RUN")),
            "ductility_limit": float(ductility.get("limit", 0.36) or 0.36),
            "clause_815_triggered": bool(ductility.get("conditional_triggered", False)),
            "clause_815_satisfied": bool(ductility.get("conditional_requirements_satisfied", False)),
            "clause_815_failed_requirements": tuple(ductility.get("failed_requirements", ()) or ()),
        })


from engineering_page_sections import bending_diagrams as _bending_diagrams_section
_coalesce_num = _bending_diagrams_section._coalesce_num
_get_build_beam_3d_figure_pure = _bending_diagrams_section._get_build_beam_3d_figure_pure
_build_beam_3d_figure_pure_impl = _bending_diagrams_section._build_beam_3d_figure_pure_impl
_build_beam_3d_figure = _bending_diagrams_section._build_beam_3d_figure
_bending_diagrams_section.bind_runtime(globals())
_render_bending_state_panel = st.fragment(
    _bending_diagrams_section.render_bending_state_panel
)
_render_bending_secondary_state_cache = st.fragment(
    _bending_diagrams_section.render_bending_secondary_state_cache
)


# Conditional caching: bypass in debug mode, cache in production




def build_bending_report(top_results: dict, params: dict) -> dict:
    """
    Build the bending report structure (tabs + calc boxes) from computed values.

    This function replicates the calc box structure from render_uls_tab,
    render_min_strength_tab, and render_sls_tab, but without UI rendering.

    Args:
        top_results: Dict from _compute_bending_capacity() with all calculated values
        params: Dict with inputs: b, D, fc, fsy, Ast, d, phi, Mu_star, Ec, Es, etc.

    Returns:
        dict with module_title, summary, and tabs structure
    """
    from reporting.report_content import make_calc_box, make_tab, make_module_report
    import math

    # Extract parameters
    b = params.get("b", 400.0)
    D = params.get("D", 600.0)
    fc = params.get("fc", 32.0)
    fsy = params.get("fsy", 500.0)
    Ast = params.get("Ast", 0.0)
    d = params.get("d", 560.0)
    phi = params.get("phi", 0.85)
    Mu_star = params.get("Mu_star_uls", params.get("Mu_star", 0.0))
    Mu_star_sls = params.get("Mu_star_sls", None)
    Ec = params.get("Ec", 30000.0)
    Es = params.get("Es", 200000.0)
    report_moment_sign = str(params.get("moment_sign", "positive") or "positive").strip().lower()

    # Extract results
    phi_Mu_cap = top_results.get("phi_Mu_cap", 0.0)
    Mu_util = top_results.get("Mu_util", 0.0)

    # Build summary
    outcome = "PASS" if (Mu_util is not None and Mu_util <= 1.0) else "FAIL" if Mu_util is not None else "N/A"
    summary = [
        ("Demand", f"{Mu_star:.1f} kNm"),
        ("Capacity", f"{phi_Mu_cap:.1f} kNm"),
        ("Utilisation", f"{Mu_util:.2f}" if Mu_util is not None and not math.isnan(Mu_util) else "N/A"),
        ("Outcome", outcome),
    ]

    # ULS tab calculations (matching render_uls_tab logic)
    uls_boxes = []
    if phi_Mu_cap > 0 and d and Ast:
        uls_report_values = uls_bending_report_values(
            b=b,
            d=d,
            fc=fc,
            fsy=fsy,
            Ast=Ast,
            phi=phi,
            Mu_star=Mu_star,
            Es=Es,
        )
        alpha2_uls = uls_report_values["alpha2"]
        gamma_uls = uls_report_values["gamma"]
        T = uls_report_values["T_N"]
        T_kN = uls_report_values["T_kN"]
        dn = uls_report_values["dn"]
        a_uls = uls_report_values["a"]
        z_uls = uls_report_values["z"]
        Mu_nom_uls = uls_report_values["Mu_nom"]
        phi_Mu_cap_uls = uls_report_values["phi_Mu_cap"]
        C_N = uls_report_values["C_N"]
        C_kN = uls_report_values["C_kN"]

        # 1.1 Stress-block parameters
        # Create diagram callable for box 1.1
        def diagram_1_1_fn():
            from bending_diagrams import _make_uls_stress_block_figure
            return _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=False,
                show_alpha_label=True,
                show_C=False,
                C_N=None,
                variant="11",
                moment_sign=report_moment_sign,
            )

        uls_boxes.append(make_calc_box(
            "1.1",
            "Stress-block parameters (alpha2 and gamma)",
            "info",
            f"alpha2 = {alpha2_uls:.3f}, gamma = {gamma_uls:.3f}",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Stress block factor alpha2", "eq": "alpha2 = 0.85 - 0.0015*f'c (>= 0.67)", "sub": f"= 0.85 - 0.0015*{fc:.1f} = {alpha2_uls:.3f}"},
                {"label": "Stress block factor gamma", "eq": "gamma = 0.97 - 0.0025*f'c (>= 0.67)", "sub": f"= 0.97 - 0.0025*{fc:.1f} = {gamma_uls:.3f}"},
            ],
            diagram=diagram_1_1_fn,  # Store callable for later export
        ))

        # 1.2 Concrete compressive force C
        uls_boxes.append(make_calc_box(
            "1.2",
            "Concrete compressive force C",
            "info",
            f"C = {C_kN:.1f} kN",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Compression force", "eq": "C = alpha2*f'c*b*a/1000", "sub": f"= {alpha2_uls:.3f}*{fc:.1f}*{b:.0f}*{a_uls:.1f}/1000 = {C_kN:.1f} kN"},
            ],
        ))

        # 1.3 Steel area and tension force T
        uls_boxes.append(make_calc_box(
            "1.3",
            "Steel area and tension force T",
            "info",
            f"T = {T_kN:.1f} kN",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Tension force", "eq": "T = Ast*fsy/1000", "sub": f"= {Ast:.0f}*{fsy:.0f}/1000 = {T_kN:.1f} kN"},
            ],
        ))

        # 1.4 Neutral axis depth d_n and block depth a
        def diagram_1_4_fn():
            from bending_diagrams import _make_uls_stress_block_figure
            return _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=True,
                show_alpha_label=False,
                show_C=True,
                C_N=C_N,
                variant="13",
                moment_sign=report_moment_sign,
            )

        uls_boxes.append(make_calc_box(
            "1.4",
            "Neutral axis depth d_n and block depth a",
            "info",
            f"d_n = {dn:.1f} mm, a = {a_uls:.1f} mm",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Equilibrium", "eq": "T = alpha2*f'c*b*gamma*c/1000", "sub": "Rearrange for c"},
                {"label": "Neutral axis", "eq": "c = T*1000/(alpha2*f'c*b*gamma)", "sub": f"= {T_kN:.1f}*1000/({alpha2_uls:.3f}*{fc:.1f}*{b:.0f}*{gamma_uls:.3f}) = {dn:.1f} mm"},
                {"label": "Block depth", "eq": "a = gamma*c", "sub": f"= {gamma_uls:.3f}*{dn:.1f} = {a_uls:.1f} mm"},
            ],
            diagram=diagram_1_4_fn,
        ))

        # 1.4A Strain compatibility (εcu and εs) — same formula as ULS tab calc card
        eps_cu_rep = uls_report_values["eps_cu"]
        eps_s_rep = uls_report_values["eps_s"]
        eps_sy_rep = uls_report_values["eps_sy"]
        yield_note = ""
        if not math.isnan(eps_s_rep) and not math.isnan(eps_sy_rep):
            yield_note = f"; ε_sy = {eps_sy_rep:.5f} → {'ε_s ≥ ε_sy' if eps_s_rep >= eps_sy_rep else 'ε_s < ε_sy'}"

        uls_boxes.append(make_calc_box(
            "1.4A",
            "Strain compatibility (εcu and εs)",
            "info",
            f"ε_s = {eps_s_rep:.5f}{yield_note}" if not math.isnan(eps_s_rep) else "ε_s = —",
            "AS 3600:2018 — strain compatibility (diagram support)",
            [
                {"label": "Assumption", "eq": "εcu = 0.003 at extreme compression fibre", "sub": "ULS concrete strain limit"},
                {"label": "Compatibility", "eq": "εs = εcu * (d - d_n) / d_n", "sub": f"= {eps_cu_rep:.3f} * ({d:.1f} - {dn:.1f}) / {dn:.1f}" + (f" = {eps_s_rep:.5f}" if not math.isnan(eps_s_rep) else "")},
            ],
        ))

        # 1.5 Neutral axis ratio k_u
        ku = uls_report_values["ku"]
        ku_lim = uls_report_values["ku_limit"]
        ku_ok = uls_report_values["ku_ok"]
        ku_status = "pass" if ku_ok is True else "fail" if ku_ok is False else "info"
        uls_boxes.append(make_calc_box(
            "1.5",
            "Neutral axis ratio k_u",
            ku_status,
            f"k_u = {ku:.3f} vs k_u,lim = {ku_lim:.2f} → {'PASS' if ku_ok else 'FAIL' if ku_ok is False else '—'}",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Ratio", "eq": "k_u = c/d", "sub": f"= {dn:.1f}/{d:.1f} = {ku:.3f}"},
            ],
        ))

        # 1.6 Lever arm z and moment capacity
        def diagram_1_6_fn():
            from bending_diagrams import _make_uls_force_model_figure
            from reporting.fig_export import call_with_supported_kwargs
            # Use signature-safe call - function expects D_mm, d_mm, a_mm, C_N, T_N
            return call_with_supported_kwargs(
                _make_uls_force_model_figure,
                D_mm=D or 0.0,
                d_mm=d,
                a_mm=a_uls,
                C_N=C_N,
                T_N=T,
                moment_sign=report_moment_sign,
                dn_mm=dn,
                # Also pass aliases in case function accepts different names
                b_mm=b or 0.0,
                b=b or 0.0,
                z_mm=z_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
            )

        uls_boxes.append(make_calc_box(
            "1.6",
            "Lever arm z and moment capacity",
            "info",
            f"phiM_u,cap = {phi_Mu_cap_uls:.2f} kNm",
            "AS 3600:2018 Cl. 8.1.3, 2.2",
            [
                {"label": "Lever arm", "eq": "z = d - a/2", "sub": f"= {d:.1f} - {a_uls:.1f}/2 = {z_uls:.1f} mm"},
                {"label": "Nominal", "eq": "M_u = T*z/1000/1000", "sub": f"= {T_kN:.1f}*{z_uls:.1f}/1000 = {Mu_nom_uls:.2f} kNm"},
                {"label": "Design", "eq": "phiM_u = phi*M_u", "sub": f"= {phi:.2f}*{Mu_nom_uls:.2f} = {phi_Mu_cap_uls:.2f} kNm"},
            ],
            diagram=diagram_1_6_fn,
        ))

        # 1.7 Flexural capacity check
        Mu_ok = uls_report_values["Mu_ok"]
        Mu_status = "pass" if Mu_ok is True else "fail" if Mu_ok is False else "info"
        Mu_util_val = uls_report_values["Mu_util"]
        uls_boxes.append(make_calc_box(
            "1.7",
            "Flexural capacity check",
            Mu_status,
            f"M_u* = {Mu_star:.2f} kNm vs phiM_u,cap = {phi_Mu_cap_uls:.2f} kNm → {'PASS' if Mu_ok else 'FAIL' if Mu_ok is False else 'N/A'}",
            "AS 3600:2018 Cl. 2.2",
            [
                {"label": "Utilisation", "eq": "Util = M_u*/phiM_u,cap", "sub": f"= {Mu_star:.2f}/{phi_Mu_cap_uls:.2f} = {Mu_util_val:.2f}"},
            ],
        ))

    # Minimum strength tab (matching render_min_strength_tab logic)
    min_boxes = []
    if phi_Mu_cap > 0:
        fctf = top_results.get("fctf", 0.0)
        Z_gross = top_results.get("Z_gross", 0.0)
        Mcr = top_results.get("Mcr", 0.0)
        As_min = top_results.get("As_min", 0.0)

        fctf_as = fctf
        Zg = Z_gross
        Mcr_as = Mcr
        Mu_min_as = minimum_moment_capacity_kNm(Mcr_as)
        Ast_min_as = As_min

        # 2.1 f_ct,f
        min_boxes.append(make_calc_box(
            "2.1",
            "Concrete flexural tensile strength f_ct,f",
            "info",
            f"f_ct,f = {fctf_as:.3f} MPa",
            "AS 3600:2018 (simplified)",
            [
                {"label": "Tensile strength", "eq": "f_ct,f = 0.6*sqrt(f'c)", "sub": f"= 0.6*sqrt({fc:.1f}) = {fctf_as:.3f} MPa"},
            ],
        ))

        # 2.2 Z_g
        min_boxes.append(make_calc_box(
            "2.2",
            "Gross section modulus Z_g",
            "info",
            f"Z_g = {Zg:.3e} mm³",
            "AS 3600:2018",
            [
                {"label": "Section modulus", "eq": "Z_g = b*D^2/6", "sub": f"= {b:.0f}*{D:.0f}^2/6 = {Zg:.3e} mm³"},
            ],
        ))

        # 2.3 M_cr
        min_boxes.append(make_calc_box(
            "2.3",
            "Cracking moment M_cr",
            "info",
            f"M_cr = {Mcr_as:.2f} kNm",
            "AS 3600:2018",
            [
                {"label": "Cracking moment", "eq": "M_cr = f_ct,f*Z_g/10^6", "sub": f"= {fctf_as:.3f}*{Zg:.3e}/10^6 = {Mcr_as:.2f} kNm"},
            ],
        ))

        # 2.4 Minimum required capacity
        Mu_min_ok = phi_Mu_cap >= Mu_min_as if (phi_Mu_cap > 0 and Mu_min_as > 0) else None
        Mu_min_status = "pass" if Mu_min_ok is True else "fail" if Mu_min_ok is False else "info"
        min_boxes.append(make_calc_box(
            "2.4",
            "Minimum required design capacity (M_u,cap)_min",
            Mu_min_status,
            f"phiM_u,cap = {phi_Mu_cap:.2f} kNm vs (M_u,cap)_min = {Mu_min_as:.2f} kNm → {'PASS' if Mu_min_ok else 'FAIL' if Mu_min_ok is False else 'N/A'}",
            "AS 3600:2018 (teaching)",
            [
                {"label": "Minimum capacity", "eq": "(M_u,cap)_min = 1.2*M_cr", "sub": f"= 1.2*{Mcr_as:.2f} = {Mu_min_as:.2f} kNm"},
            ],
        ))

        # 2.5 Minimum tensile reinforcement
        As_ok = Ast >= Ast_min_as if (Ast is not None and Ast_min_as is not None and not math.isnan(Ast_min_as)) else None
        As_status = "pass" if As_ok is True else "fail" if As_ok is False else "info"
        min_boxes.append(make_calc_box(
            "2.5",
            "Minimum tensile reinforcement A_st,min",
            As_status,
            f"A_st = {Ast:.1f} mm² vs A_st,min = {Ast_min_as:.1f} mm² → {'PASS' if As_ok else 'FAIL' if As_ok is False else 'N/A'}",
            "AS 3600:2018 (simplified)",
            [
                {"label": "Minimum steel", "eq": "A_st,min = 0.4*(f_ct,f/f_sy)*b*d", "sub": f"= 0.4*({fctf_as:.3f}/{fsy:.0f})*{b:.0f}*{d:.0f} = {Ast_min_as:.1f} mm²"},
            ],
        ))

    # SLS tab - read from session_state if available (computed by render_sls_tab)
    sls_boxes = []
    Ms = params.get("Mu_star_sls", Mu_star)  # service moment (kNm)
    if Mu_star_sls is not None:
        try:
            debug_print(f"[BENDING_REPORT_ACTIONS] uls_M={Mu_star} sls_M={Mu_star_sls}")
        except Exception:
            pass

    # Try to read SLS values from session_state (if SLS tab has been run)
    try:
        dn_sls = st.session_state.get("bending_sls_dn", None)
        kappa_sls = st.session_state.get("bending_sls_kappa", None)
        eps_top_sls = st.session_state.get("bending_sls_eps_top", None)
        fs_outer = st.session_state.get("bending_sls_fs_outer", None)
    except Exception:
        dn_sls = None
        kappa_sls = None
        eps_top_sls = None
        fs_outer = None

    if dn_sls is not None and kappa_sls is not None and Ec > 0 and Es > 0 and b > 0 and Ast > 0 and d > 0:
        # SLS values are available - build calc boxes
        sls_report_values = sls_report_display_values(
            Ms_kNm=Ms,
            Ec=Ec,
            Es=Es,
            d=d,
            dn_sls=dn_sls,
            kappa_sls=kappa_sls,
            eps_top_sls=eps_top_sls,
        )
        n_sls = sls_report_values["n_sls"]

        # 3.1 Modular ratio
        sls_boxes.append(make_calc_box(
            "3.1",
            "Modular ratio n = E_s / E_c",
            "info",
            f"n = {n_sls:.2f}",
            "AS 3600:2018 SLS",
            [
                {"label": "Modular ratio", "eq": "n = E_s / E_c", "sub": f"= {Es:.0f} / {Ec:.0f} = {n_sls:.2f}"},
            ],
        ))

        # 3.2 Neutral axis depth d_n
        def diagram_3_2_fn():
            from bending_diagrams import _make_sls_stress_block_figure
            from reporting.fig_export import call_with_supported_kwargs
            # Get bar layout info for diagram
            nb_top = st.session_state.get("nb_top", 0) or 0
            db_top = st.session_state.get("db_top", 0.0) or 0.0
            cover_top = st.session_state.get("cover_top", 0.0) or 0.0
            include_comp = (nb_top > 0)
            d_comp = cover_top + db_top/2.0 if (nb_top > 0 and db_top > 0) else None
            # Use signature-safe call
            return call_with_supported_kwargs(
                _make_sls_stress_block_figure,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn_sls,
                include_comp=include_comp,
                d_comp_mm=d_comp,
                moment_sign=st.session_state.get("bending_detail_view", "positive"),
                # Also pass aliases
                D=D or 0.0,
                d=d,
                dn=dn_sls,
            )

        sls_boxes.append(make_calc_box(
            "3.2",
            "Neutral axis depth d_n (cracked section)",
            "info",
            f"d_n = {dn_sls:.1f} mm",
            "AS 3600:2018 SLS",
            [
                {"label": "Cracked section", "eq": "Equilibrium: C = T (transformed areas)", "sub": "Solved numerically"},
                {"label": "Result", "eq": "d_n", "sub": f"= {dn_sls:.1f} mm"},
            ],
            diagram=diagram_3_2_fn,
        ))

        # 3.3 Cracked moment of inertia I_cr
        Icr = sls_report_values["Icr"]

        sls_boxes.append(make_calc_box(
            "3.3",
            "Cracked moment of inertia I_cr",
            "info",
            f"I_cr = {Icr:,.2f} mm⁴",
            "AS 3600:2018 SLS",
            [
                {"label": "Formula", "eq": "I_cr = b*d_n^3/3 + Σ(n*A_s*(d_i - d_n)^2)", "sub": "Includes all steel layers"},
                {"label": "Result", "eq": "I_cr", "sub": f"= {Icr:,.2f} mm⁴"},
            ],
        ))

        # 3.4 Curvature
        sls_boxes.append(make_calc_box(
            "3.4",
            "Curvature at service moment",
            "info",
            f"κ = {kappa_sls:.3e} mm⁻¹",
            "AS 3600:2018 SLS",
            [
                {"label": "Curvature", "eq": "κ = M_s / (E_c * I_cr)", "sub": f"= {Ms:.2f}*10^6 / ({Ec:.0f} * {Icr:,.2f}) = {kappa_sls:.3e} mm⁻¹"},
            ],
        ))

        # 3.5 Strain distribution (top fibre)
        if eps_top_sls is not None:
            sls_boxes.append(make_calc_box(
                "3.5",
                "Strain distribution ε(y) = κ(y − d_n)",
                "info",
                f"ε_top = {eps_top_sls:.5f}",
                "AS 3600:2018 SLS",
                [
                    {"label": "Top fibre strain", "eq": "ε_top = κ*(0 - d_n)", "sub": f"= {kappa_sls:.3e}*({-dn_sls:.1f}) = {eps_top_sls:.5f}"},
                ],
            ))
        else:
            eps_top_computed = sls_report_values["eps_top"]
            sls_boxes.append(make_calc_box(
                "3.5",
                "Strain distribution ε(y) = κ(y − d_n)",
                "info",
                f"ε_top = {eps_top_computed:.5f}",
                "AS 3600:2018 SLS",
                [
                    {"label": "Top fibre strain", "eq": "ε_top = κ*(0 - d_n)", "sub": f"= {kappa_sls:.3e}*({-dn_sls:.1f}) = {eps_top_computed:.5f}"},
                ],
            ))

        # 3.6 Steel stresses (outermost tension layer if available)
        if fs_outer is not None:
            sls_boxes.append(make_calc_box(
                "3.6",
                "Steel stresses at SLS",
                "info",
                f"f_s,outer = {fs_outer:.1f} MPa",
                "AS 3600:2018 SLS",
                [
                    {"label": "Outermost tension layer", "eq": "f_s = E_s * ε_s", "sub": f"= {fs_outer:.1f} MPa"},
                ],
            ))
        else:
            eps_s_computed = sls_report_values["eps_s"]
            fs_computed = sls_report_values["fs"]
            sls_boxes.append(make_calc_box(
                "3.6",
                "Steel stresses at SLS",
                "info",
                f"f_s ≈ {fs_computed:.1f} MPa",
                "AS 3600:2018 SLS",
                [
                    {"label": "Steel strain", "eq": "ε_s = κ*(d - d_n)", "sub": f"= {kappa_sls:.3e}*({d:.1f} - {dn_sls:.1f}) = {eps_s_computed:.5f}"},
                    {"label": "Steel stress", "eq": "f_s = E_s * ε_s", "sub": f"= {Es:.0f} * {eps_s_computed:.5f} = {fs_computed:.1f} MPa"},
                ],
            ))
    else:
        # SLS values not available - show warning box
        sls_boxes.append(make_calc_box(
            "SLS",
            "SLS checks not available",
            "warn",
            "Run SLS checks (or Run all checks) before exporting.",
            "",
            [
                {"label": "Note", "eq": "", "sub": "SLS cracked-section analysis requires running the SLS tab in the app."},
            ],
        ))

    # Build tabs
    tabs = [
        make_tab("ULS Checks", uls_boxes),
        make_tab("SLS Checks", sls_boxes),
        make_tab("Minimum strength checks", min_boxes),
    ]

    # Build module report
    report = make_module_report("Bending (ULS)", tabs)
    report["summary"] = summary  # Add summary to report
    return report


from engineering_page_sections import bending_calculations as _bending_calculations_section
_compute_sls_bending_values = _bending_calculations_section._compute_sls_bending_values
compute_bending_results = _bending_calculations_section.compute_bending_results
_get_bending_inputs_from_shared_state = _bending_calculations_section._get_bending_inputs_from_shared_state
make_bending_sig_from_shared_state = _bending_calculations_section.make_bending_sig_from_shared_state
get_bending_inputs_from_shared_state = _bending_calculations_section.get_bending_inputs_from_shared_state
_bending_calculations_section.bind_runtime(globals())









def render_bending():
    # Reserve the page-top result container before invisible CSS/style elements
    # so its heading aligns with the other engineering pages.
    top_container = st.container()
    render_timing_mark("bending_page.runtime.start")
    # NOTE: init_shared_session_state() is called by app.py router before this function runs.
    # Pages must NOT call init/hydrate themselves - the router owns the lifecycle.

    from state_and_helpers import _write_sync_trace_line
    _write_sync_trace_line("\n=== PAGE RENDER: bending ===")
    # Widget callbacks update the live row-model keys before this rerun. Recompute
    # derived summaries here so the top summary and diagrams use the current reo layout
    # even when the global structural recompute is not running.
    recalc_derived_values()

    # Handle cross-page navigation from Inputs page
    from jump_nav import JUMP_NAV_TAB_KEY, get_jump_uid

    get_jump_uid()
    # Optional canonical row uid (?jump_row=) disambiguates pos/neg rows that share one calc id.
    _jr = st.query_params.get("jump_row")
    if isinstance(_jr, list):
        _jr = _jr[0] if _jr else None
    if _jr:
        _jrs = str(_jr).strip()
        if _jrs == "bend_strength_pos":
            st.session_state["bending_detail_view"] = "positive"
        elif _jrs == "bend_strength_neg":
            st.session_state["bending_detail_view"] = "negative"
        try:
            del st.query_params["jump_row"]
        except Exception:
            pass
    _jt = st.session_state.get("jump_to")
    if _jt:
        _sid = str(_jt)
        if _sid.startswith("bending_sls_"):
            st.session_state[JUMP_NAV_TAB_KEY] = "SLS Checks"
            st.session_state["bending_check_tab"] = "SLS Checks"
        elif _sid.startswith("bending_min_"):
            st.session_state[JUMP_NAV_TAB_KEY] = "Minimum strength checks"
            st.session_state["bending_check_tab"] = "Minimum strength checks"
        else:
            st.session_state[JUMP_NAV_TAB_KEY] = "ULS Checks"
            st.session_state["bending_check_tab"] = "ULS Checks"

    sync_callbacks = get_sync_callbacks()
    apply_result_page_css()

    # Inject seamless steps CSS (for summary table + calc details)
    inject_seamless_steps_css()


    # Initialize page-local active mode state (UI-only, not in shared state)
    if "bending_active_mode" not in st.session_state:
        st.session_state["bending_active_mode"] = "ULS"


    # Remove green background from inline math (Streamlit wraps math in code tags)
    # But preserve katex rendering by only targeting background, not font styling
    st.markdown(
        """
<style>
/* Remove green background from code elements in markdown paragraphs (these contain math) */
/* But don't override font-family so katex can render properly */
.stMarkdown p code {
    background-color: transparent !important;
    border: none !important;
    padding: 0 !important;
}
/* Ensure katex elements render properly */
.stMarkdown p code .katex,
.stMarkdown p .katex {
    font-family: KaTeX_Main, "Times New Roman", serif !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


    # ---------------- Sidebar glossary ----------------
    with st.sidebar.expander("📘 Glossary – Bending terms", expanded=False):
        st.markdown(
            """
            **Mu*** – Factored design bending moment at the critical section (kNm).
            **b** – Beam/web width (mm).
            **D** – Overall section depth (mm).
            **d** – Effective depth to **centroid of tension steel** (mm).
            **Ast,bot** – Area of bottom (tension) reinforcement (mm²).
            **As_min** – Minimum required tensile steel for ductile behaviour.
            **f'c** – Concrete cylinder strength (MPa).
            **fsy** – Steel yield strength (MPa).
            **Ec, Es** – Elastic moduli of concrete and steel (MPa).

            **c** – Neutral axis depth from the top fibre (mm).
            **a = γc** – Equivalent rectangular stress block depth (mm).
            **kᵤ = c/d** – Neutral axis depth ratio (ductility indicator).
            **α₂, γ** – AS 3600-style stress block factors.
            **ϕ** – Strength reduction factor for bending.

            **M_cr** – Cracking moment (kNm) based on f_ct,f and gross section.
            **M_u** – Nominal flexural capacity (kNm).
            **ϕM_u,cap** – Design flexural capacity (kNm).
            **Utilisation** – M_u* / ϕM_u,cap → should be ≤ 1.0.
            """
        )

    # Sync ULS load to Mu_star (contract-compliant via update_results)
    # Skip in design-driven mode to avoid overwriting SFD/BMD actions.
    if get_param("actions_mode", "manual") != "design":
        Mu_star_uls_val = get_param("uls_Mstar")
        if Mu_star_uls_val is not None:
            update_results(
                Mu_star=float(abs(Mu_star_uls_val)),
                Mu_star_kNm=float(abs(Mu_star_uls_val)),
                Mu_star_kNm_signed=float(Mu_star_uls_val),
            )

    render_timing_mark("bending_page.runtime.summary_compute.start")
    # ---------------- Top result summary (+ shared 3D NA view data) ----------------
    top_results = _compute_bending_capacity()
    Ast = get_param("Ast_bot")
    Mu_star = get_param("Mu_star")
    Mu_star_sls = float(get_param("sls_Mstar") or 0.0)

    # Compute SLS values before summary / tabs (publishes sigma_s_sls, bending_sls_fs_outer, etc.)
    _compute_sls_bending_values()

    actions_signed = resolve_design_actions()
    has_sagging_case = bool(actions_signed.get("has_sagging_case", False))
    has_hogging_case = bool(actions_signed.get("has_hogging_case", False))
    Mu_pos_star = float(actions_signed.get("Mu_pos", 0.0) or 0.0)
    Mu_neg_star = float(actions_signed.get("Mu_neg", 0.0) or 0.0)
    Ms_pos_star = float(actions_signed.get("SLS_M_pos", 0.0) or 0.0)
    Ms_neg_star = float(actions_signed.get("SLS_M_neg", 0.0) or 0.0)

    D_val = float(get_param("D") or 0.0)
    do_val = float(get_param("do") or 0.0)
    d_pos_val = float(get_param("d") or 0.0)
    d_neg_val = hogging_tension_effective_depth_mm(D_val, do_val)
    common_bending_inputs = {
        "b": get_param("b"),
        "D": get_param("D"),
        "fc": get_param("fc"),
        "fsy": get_param("fsy"),
        "phi_bend": get_param("phi_bend"),
        "Ast_bot": get_param("Ast_bot"),
        "Ast_top": get_param("Ast_top"),
        "d": d_pos_val,
        "do": do_val,
    }
    top_results_pos = solve_bending_capacity("positive", Mu_pos_star, common_bending_inputs)
    top_results_neg = solve_bending_capacity("negative", Mu_neg_star, common_bending_inputs)
    authoritative_bending = current_authoritative_family(st.session_state, "bending")
    authoritative_ductility = current_authoritative_family(st.session_state, "ductility")
    _overlay_authoritative_bending_result(
        top_results_pos,
        authoritative_bending,
        authoritative_ductility,
        d_pos_val,
    )

    phi_Mu_cap_top = top_results["phi_Mu_cap"]

    # ============================================================
    # COMPUTE CACHED LAYOUT ONCE - reuse for all diagrams
    # ============================================================
    from section_layout import compute_section_layout_cached

    # Get all inputs from results (matches shear pattern)
    results = st.session_state.get("results", {})

    # --- ARCHITECTURE LOCK: bending diagrams must use results (with fallback to shared) ---
    # Note: Geometry values (b, D, d) are not in results - they're in shared state.
    # The guard ensures results dict exists and diagrams use the fallback pattern correctly.
    if st.session_state.get("_dev_mode", False):
        if "results" not in st.session_state:
            raise RuntimeError(
                "[ARCHITECTURE VIOLATION] Bending diagrams require results dict to exist. "
                "Call update_results() or run compute functions first."
            )

    # Filter signature to only include parameters that compute_section_layout_cached accepts
    layout_sig = {
        "b": get_param("b", results.get("b", 400.0)),
        "D": get_param("D", results.get("D", 600.0)),
        "cover_bot": get_param("cover_bot", results.get("cover_bot", 40.0)),
        "cover_top": get_param("cover_top", results.get("cover_top", 40.0)),
        "cover_side": get_param("cover_side", results.get("cover_side", 40.0)),
        "nb_or_s_bot_1": get_param("nb_or_s_bot_1", results.get("nb_or_s_bot_1", 4.0)),
        "db_bot_1": get_param("db_bot_1", results.get("db_bot_1", 20.0)),
        "nb_or_s_bot_2": get_param("nb_or_s_bot_2", results.get("nb_or_s_bot_2", 0.0)),
        "db_bot_2": get_param("db_bot_2", results.get("db_bot_2", 20.0)),
        "nb_or_s_top_1": get_param("nb_or_s_top_1", results.get("nb_or_s_top_1", 2.0)),
        "db_top_1": get_param("db_top_1", results.get("db_top_1", 16.0)),
        "nb_or_s_top_2": get_param("nb_or_s_top_2", results.get("nb_or_s_top_2", 0.0)),
        "db_top_2": get_param("db_top_2", results.get("db_top_2", 16.0)),
        "rowgap_bot": get_param("rowgap_bot", results.get("rowgap_bot", 60.0)),
        "rowgap_top": get_param("rowgap_top", results.get("rowgap_top", 60.0)),
        "lig_legs": get_param("lig_legs", results.get("lig_legs", 2)),
        "lig_d": get_param("lig_d", results.get("lig_d", 10.0)),
    }

    # Compute cached layout once using filtered signature
    from section_layout import compute_section_layout_cached
    cached_layout = compute_section_layout_cached(**layout_sig)
    c_top = top_results["c"]

    # Canonical bending state shared by 3D & bottom radios (ULS / SLS / Uncracked)
    state_options = ["ULS", "SLS (cracked)", "Uncracked"]
    canonical_state = st.session_state.get("bending_state", "ULS")
    if canonical_state not in state_options:
        canonical_state = "ULS"

    bend_pack = build_bending_check_rows_from_state(st.session_state)
    if not top_results_pos.get("_authoritative_uls"):
        _overlay_authoritative_bending_result(
            top_results_pos,
            bend_pack.get("authoritative_family") or {},
            bend_pack.get("authoritative_ductility_family") or {},
            d_pos_val,
        )
    has_sagging_case = bool(bend_pack.get("has_sagging_case", has_sagging_case))
    has_hogging_case = bool(bend_pack.get("has_hogging_case", has_hogging_case))
    has_positive_bending_case = has_sagging_case
    has_negative_bending_case = has_hogging_case
    _valid_bending_views = [
        v
        for v, ok in (
            ("positive", has_positive_bending_case),
            ("negative", has_negative_bending_case),
        )
        if ok
    ]
    if not st.session_state.get("_bending_detail_view_seeded"):
        st.session_state["_bending_detail_view_seeded"] = True
        if has_negative_bending_case and not has_positive_bending_case:
            st.session_state["bending_detail_view"] = "negative"
        elif has_positive_bending_case and not has_negative_bending_case:
            st.session_state["bending_detail_view"] = "positive"
        elif has_positive_bending_case and has_negative_bending_case:
            u_p = float(top_results_pos.get("util", 0.0) or 0.0)
            u_n = float(top_results_neg.get("util", 0.0) or 0.0)
            st.session_state["bending_detail_view"] = (
                "negative" if u_n > u_p else "positive"
            )
    _bdv = st.session_state.get("bending_detail_view", "positive")
    if _bdv not in _valid_bending_views and _valid_bending_views:
        st.session_state["bending_detail_view"] = _valid_bending_views[0]

    render_timing_mark("bending_page.runtime.summary_compute.end")

    render_timing_mark("bending_page.runtime.presentation.start")
    # ---------------- TOP CONTAINER – Title + summary + explainer ----------------
    with top_container:
        def _on_bending_sign_change():
            v = st.session_state.get("_bending_sign_radio")
            st.session_state["bending_detail_view"] = (
                "negative" if v == "Hogging" else "positive"
            )

        if len(_valid_bending_views) == 2:
            _lab = (
                "Hogging"
                if st.session_state.get("bending_detail_view") == "negative"
                else "Sagging"
            )
            _opts = ["Sagging", "Hogging"]
            st.radio(
                "Bending check (detail)",
                _opts,
                horizontal=True,
                index=_opts.index(_lab) if _lab in _opts else 0,
                key="_bending_sign_radio",
                on_change=_on_bending_sign_change,
            )
        elif len(_valid_bending_views) == 1:
            st.session_state["bending_detail_view"] = _valid_bending_views[0]

        selected_bending_sign = st.session_state.get("bending_detail_view", "positive")
        if (
            selected_bending_sign not in _valid_bending_views
            and _valid_bending_views
        ):
            selected_bending_sign = _valid_bending_views[0]
        st.session_state["_bending_page_selected_sign"] = selected_bending_sign

        if has_sagging_case and has_hogging_case:
            _bend_page_title = (
                "Hogging bending capacity"
                if selected_bending_sign == "negative"
                else "Sagging bending capacity"
            )
        elif has_hogging_case:
            _bend_page_title = "Hogging bending capacity"
        elif has_sagging_case:
            _bend_page_title = "Sagging bending capacity"
        else:
            _bend_page_title = "Bending capacity"
        # The app shell owns the active page heading. Keep this fallback only
        # for direct renderer use, otherwise the shell and page would both
        # render the same title on every rerun.
        if not st.session_state.get("_shared_page_title_owned_by_shell", False):
            render_result_page_title(_bend_page_title)

        def _render_bending_explainer() -> None:
            render_timing_mark("bending_page.runtime.explainer.body.start")
            top_left, top_right = st.columns([0.58, 0.42])
            sign = st.session_state.get("_bending_page_selected_sign", "positive")
            hog = sign == "negative"

            with top_left:
                mode = "hogging (negative)" if hog else "sagging (positive)"
                st.markdown(
                    f"""
This page computes **ultimate flexural capacity**, **strain compatibility**, and
**service-stress outputs** in accordance with **AS 3600:2018 Clause 8**, including:

**Detail view:** **{mode}** bending — compression and tension zones match this selection.
"""
                )

                st.markdown(r"""
- **Ultimate moment capacity** (Cl. 8.1.3)
    $$\phi M_{u,\mathrm{cap}} = \phi\,T\,(d - 0.5\,\gamma x_u)$$

- **Steel stress at serviceability**, used in crack-width and deflection checks.
    $$f_{s,\mathrm{ser}} = E_s\,\varepsilon_s$$
""")

            with top_right:
                st.markdown("")

                from curved_beam_diagram import render_curved_beam_fig

                try:
                    inputs = get_bending_inputs_from_shared_state()
                    L_m = inputs["L"] / 1000.0
                    D_mm = float(inputs["D"])
                    D_m = D_mm / 1000.0
                    b_m = inputs["b"] / 1000.0
                    if hog:
                        c_mm = float(top_results_neg.get("dn_mm", float("nan")))
                        if c_mm == c_mm and not math.isnan(c_mm) and D_mm > 0:
                            dn_uls_m = max(0.0, (D_mm - c_mm) / 1000.0)
                        else:
                            dn_uls_m = 0.21 * D_m
                        curv = -0.4
                    else:
                        c_mm = float(
                            top_results_pos.get("dn_mm", c_top or float("nan"))
                        )
                        if c_mm == c_mm and not math.isnan(c_mm):
                            dn_uls_m = float(c_mm) / 1000.0
                        elif c_top is not None and not (
                            isinstance(c_top, float) and math.isnan(c_top)
                        ):
                            dn_uls_m = float(c_top) / 1000.0
                        else:
                            dn_uls_m = 0.21 * D_m
                        curv = 0.4

                    if D_m > 0 and L_m > 0 and dn_uls_m > 0:
                        fig_beam = render_curved_beam_fig(
                            L=L_m,
                            D=D_m,
                            b=b_m,
                            dn_uls=dn_uls_m,
                            ts_centroid_y=None,
                            curvature=curv,
                            title=None,
                        )
                        render_pyplot_diagram(
                            fig_beam,
                            key="bending_curved_beam_diagram",
                            title="Curved beam view",
                            clear_figure=True,
                        )
                    else:
                        st.info(
                            "Curved beam view will appear once geometry and moment capacity are defined."
                        )
                except Exception:
                    st.warning(
                        "3D view failed to render (browser/graphics). Try refreshing the page."
                    )
            render_timing_mark("bending_page.runtime.explainer.body.end")

        debug_mode = st.sidebar.checkbox(
            "Debug session state",
            key=f"debug_state_toggle_{st.session_state.get('page_slug','page')}"
        )
        if debug_mode:
            st.sidebar.markdown("### Debug session state")

            debug_keys = [
                "page_slug",
                "actions_source",
                "inputs_actions_source",
                "loads_edit_mode",

                # load proxies
                "load_Mstar_proxy",
                "load_Vstar_proxy",
                "load_Nstar_proxy",

                # shared actions
                "uls_Mstar",
                "uls_Vstar",
                "uls_Nstar",

                # bending derived
                "Mu_star",
                "Mu_star_kNm",

                # shear derived
                "Vu_star",

                # SFD/BMD outputs
                "sfd_Mmax_abs_kNm",
                "sfd_Vmax_abs_kN",
            ]

            st.sidebar.json({
                k: st.session_state.get(k)
                for k in debug_keys
            })

        # Build ROWS from canonical bend_pack rows (stable uids); jump targets via resolve_jump_target_id / data-jump-target.
        ROWS = build_bending_clickable_summary_rows(bend_pack.get("rows") or [])

        update_results("bending", {"rows": ROWS})

        # Render the engineering summary before lower-priority explanatory content.
        # This table is the user's primary first-view result and must be emitted
        # before the technical-basis expander, inputs, diagrams, or detailed checks.
        clicked_uid = render_clickable_summary_table(
            ROWS, key_prefix="bend_summary", columns=ENGINEERING_CHECK_COLUMNS
        )
        render_timing_mark("bending_page.runtime.summary_table.rendered")

        # Reserve the explainer's exact page position, but defer its collapsed
        # widget payload until after the two visible loading regions stream.
        explainer_placeholder = st.empty()

        # Handle clicked summary row: set mode, expand step, set pending scroll
        if clicked_uid:
            # Map calc step id to mode (use resolved jump target, not canonical row uid)
            def uid_to_mode(step_id: str):
                """Map a step UID to its mode (ULS, SLS, or MIN)."""
                if step_id.startswith("bending_uls_"):
                    return "ULS"
                elif step_id.startswith("bending_sls_"):
                    return "SLS"
                elif step_id.startswith("bending_min_"):
                    return "MIN"
                else:
                    return "ULS"  # Default to ULS for unknown UIDs

            clicked_row = next((row for row in ROWS if row.get("uid") == clicked_uid), None)
            target_uid = (
                resolve_jump_target_id(clicked_row)
                if clicked_row
                else str(clicked_uid)
            )
            target_mode = uid_to_mode(target_uid)
            st.session_state["bending_active_mode"] = target_mode
            st.session_state["bending_check_tab"] = {
                "ULS": "ULS Checks",
                "SLS": "SLS Checks",
                "MIN": "Minimum strength checks",
            }.get(target_mode, "ULS Checks")

            clicked_sign = (clicked_row or {}).get("moment_sign")
            if clicked_sign in {"positive", "negative"}:
                st.session_state["bending_detail_view"] = clicked_sign

            open_key = f"step_open_{target_uid}"
            st.session_state[open_key] = True

            st.session_state["bending_pending_scroll_uid"] = target_uid

        diagram_shell_generation = int(
            st.session_state.get("_bending_diagram_shell_generation", 0) or 0
        ) + 1
        st.session_state["_bending_diagram_shell_generation"] = diagram_shell_generation
        diagram_frame_container = st.container(key="bending_diagram_frame")
        with diagram_frame_container:
            diagram_options_placeholder = st.empty()
            diagram_section_placeholder = st.empty()
            diagram_secondary_cache_placeholder = st.empty()
        inputs_placeholder = st.empty()
        # The detailed tab body is interactive.  Keep a stable multi-element
        # container for it instead of replacing an ``st.empty`` slot on every
        # tab click; replacement remounts the whole calculation subtree and
        # makes the browser lose its scroll position.
        calc_blocks_container = st.container()
        # Both target containers already have their final page positions.
        # Publish their contents back-to-back only after those positions are
        # allocated so the intervening placeholders cannot split the visible
        # shell across two browser paint windows.
        _bending_diagrams_section.render_bending_calculation_loading_shell(
            calc_blocks_container
        )
        with diagram_options_placeholder.container():
            if "concrete_stress_model" not in st.session_state:
                st.session_state["concrete_stress_model"] = "rectangular"
            _, col_info = st.columns([0.95, 0.05])
            with col_info:
                with info_i_button(help_text="Concrete stress model options"):
                    st.markdown("**Concrete stress model**")
                    use_parabolic = st.checkbox(
                        "Use parabolic (non-linear) stress block",
                        value=(
                            st.session_state["concrete_stress_model"] == "parabolic"
                        ),
                        key="bending_parabolic_toggle",
                    )
                    st.session_state["concrete_stress_model"] = (
                        "parabolic" if use_parabolic else "rectangular"
                    )
                    st.markdown(
                        """
                        **Rectangular (AS 3600):** Standard simplified stress
                        block used in AS 3600 design.

                        **Parabolic (non-linear):** More accurate concrete
                        stress distribution for presentation.
                        """
                    )

        initial_detail_view = st.session_state.get("bending_detail_view", "positive")
        initial_showing_negative = (
            initial_detail_view == "negative" and has_hogging_case
        )
        initial_mu_uls = (
            Mu_neg_star
            if initial_showing_negative
            else (Mu_pos_star if has_sagging_case else 0.0)
        )
        with diagram_section_placeholder.container():
            _render_bending_state_panel(
                cached_layout=cached_layout,
                mu_uls_active=initial_mu_uls,
                diagram_shell_generation=diagram_shell_generation,
            )
        with diagram_secondary_cache_placeholder.container():
            _render_bending_secondary_state_cache(
                cached_layout=cached_layout,
                diagram_shell_generation=diagram_shell_generation,
            )
        with explainer_placeholder:
            render_timing_mark("bending_page.runtime.explainer.start")
            render_page_explainer_expander(_render_bending_explainer)
            render_timing_mark("bending_page.runtime.explainer.end")
        # Browser-only summary navigation does not participate in the first
        # visible Bending shell. Install it after both reserved regions have
        # streamed so its component iframe cannot delay those milestones.
        bind_summary_clicks()

        # Keep the Bending page on one spacing rhythm across major headings,
        # tabs, diagrams, and the calculation-card stack.
        st.markdown(
            """
            <style>
            /* Stable-tab scroll hooks are zero-height iframes; remove their
               Streamlit element-wrapper contribution to vertical spacing. */
            div[data-testid="stElementContainer"]:has(iframe[height="0"]),
            div[data-testid="stElementContainer"]:has(iframe[style*="height: 0px"]) {
                display: none !important;
                height: 0 !important;
                min-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            /* The deferred Bending summary binder must execute, so keep its
               iframe mounted while cancelling only the flex-row gap that its
               zero-height wrapper would otherwise add at the page tail. */
            div[data-testid="stElementContainer"]:has(
                iframe[srcdoc*="Try to find Streamlit tabs"]
            ) {
                height: 0 !important;
                min-height: 0 !important;
                margin: 0 0 -10.328125px !important;
                padding: 0 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        render_timing_mark("bending_page.runtime.presentation.summary.end")

    # Persist canonical bending state for the rest of the page (and next rerun)
    st.session_state["bending_state"] = canonical_state

    # Persist canonical bending state for the rest of the page (and next rerun)
    st.session_state["bending_state"] = canonical_state

    # values for later
    phi_Mu_cap = top_results["phi_Mu_cap"]
    c = top_results["c"]
    a = top_results["a"]
    z = top_results["z"]
    ku = top_results["ku"]
    alpha2 = top_results["alpha2"]
    gamma = top_results["gamma"]
    phi = top_results["phi"]
    fctf = top_results["fctf"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]
    d = top_results["d"]

    # shared values
    b = get_param("b")
    D = get_param("D")
    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")
    Mu_star = get_param("Mu_star")
    L_shared = get_param("L")
    nb_bot = get_param("nb_bot")
    db_bot = get_param("db_bot")
    cover_bot = get_param("cover_bot")
    nb_top = get_param("nb_top")
    db_top = get_param("db_top")
    cover_top = get_param("cover_top")

    # local copies for table
    fc_local = fc if fc is not None else 40.0
    cover_bot_local = cover_bot if cover_bot is not None else 40.0
    db_bot_local = db_bot if db_bot is not None else 20.0
    nb_bot_local = int(nb_bot) if nb_bot is not None else 4
    D_local = D if D is not None else 600.0

    d_eff = d
    if d_eff is None or (isinstance(d_eff, float) and math.isnan(d_eff)):
        d_eff = bottom_tension_effective_depth_fallback_mm(
            D_local,
            cover_bot_local,
            db_bot_local,
        )

    Ast_bot = Ast
    if Ast_bot is None or (isinstance(Ast_bot, float) and math.isnan(Ast_bot)):
        Ast_bot = bar_area_mm2(nb_bot_local, db_bot_local)

    alpha2_sb, gamma_sb = stress_block_factors(fc_local)
    phi_b = get_param("phi_bend", 0.85)
    ku_sb = ku if ku is not None else float("nan")

    Mu_min = (
        minimum_moment_capacity_kNm(Mcr)
        if (Mcr is not None and not (isinstance(Mcr, float) and math.isnan(Mcr)))
        else float("nan")
    )
    Mu_nom_report = nominal_capacity_from_phi_capacity_kNm(phi_Mu_cap, phi)

    with inputs_placeholder.container():
        page_divider()

        _bend_shape_summary = str(get_param("sec_shape", "RECT") or "RECT")
        _bend_b_summary = float(get_param("b", 0.0) or 0.0)
        _bend_D_summary = float(get_param("D", 0.0) or 0.0)
        _bend_fc_summary = float(get_param("fc", 0.0) or 0.0)
        _bend_m_summary = max(abs(Mu_pos_star), abs(Mu_neg_star))
        _bend_n_summary = float(get_param("P_star", 0.0) or 0.0)
        _bend_bot_count = int(get_param("nb_or_s_bot_1", get_param("nb_bot", 0)) or 0)
        _bend_bot_dia = float(get_param("db_bot_1", get_param("db_bot", 0.0)) or 0.0)
        _bend_top_count = int(get_param("nb_or_s_top_1", get_param("nb_top", 0)) or 0)
        _bend_top_dia = float(get_param("db_top_1", get_param("db_top", 0.0)) or 0.0)
        _bending_input_config = CheckInputPanelConfig(
            page_slug="bending",
            mount_closed_bodies=True,
            categories=(
                CheckInputCategory(
                    "design_actions", "Design actions",
                    join_summary(
                        f"M* {format_number(_bend_m_summary, 'kNm', decimals=1)}",
                        f"N* {format_number(_bend_n_summary, 'kN', decimals=1)}",
                    ),
                    lambda: None,
                    source=(
                        InputSource.LOAD_ANALYSIS
                        if uses_load_analysis_actions(st.session_state)
                        else InputSource.BEAM_INPUTS
                    ),
                    icon="↧",
                ),
                CheckInputCategory(
                    "section_material", "Section & material",
                    join_summary(
                        format_dimensions(_bend_b_summary, _bend_D_summary),
                        _bend_shape_summary,
                        f"f'c {format_number(_bend_fc_summary, 'MPa')}",
                    ),
                    lambda: None, icon="▣",
                ),
                CheckInputCategory(
                    "reinforcement", "Reinforcement",
                    join_summary(
                        f"Bottom {_bend_bot_count}-N{_bend_bot_dia:.0f}",
                        f"Top {_bend_top_count}-N{_bend_top_dia:.0f}",
                    ),
                    lambda: None, icon="●",
                ),
            ),
        )
        render_timing_mark("bending_page.runtime.summary_table.end")
        with compact_check_input_regions(st, _bending_input_config) as (
            col_actions,
            col_geom_mat,
            col_bend_reo,
        ):
            with col_bend_reo:
                with st.container(
                    border=False,
                    key="compact_check_inputs_full_span_bending_reinforcement",
                ):
                    col_bend_bot, col_bend_top = st.columns(2, gap="medium")
            with st.container():
                with col_actions:
                    if col_actions.open:
                        actions_mode = get_param("actions_mode", "manual")
                        is_design_driven = actions_mode == "design"
                        prev_mode = st.session_state.get("loads_edit_mode", "ULS")
                        toggle_widget_key = get_widget_key_for_shared("loads_edit_toggle", prefix="inputs_") or "inputs_loads_edit_toggle"

                        # Heading row with info popover for source of design actions
                        col_title, col_info = st.columns([0.92, 0.08], gap="small")
                        with col_title:
                            render_section_title("Design Actions")
                        with col_info:
                            with info_i_button(help_text="Source of design actions (M*, V*)"):
                                st.markdown("Source: Inputs page selection", unsafe_allow_html=True)
                                edit_sls = st.toggle(
                                    "View SLS loads",
                                    key=toggle_widget_key,
                                    persist_state="session",
                                    help="Toggle which load set is shown below. ULS drives bending/shear; SLS drives crack/deflection.",
                                )

                                selected_mode_preview = "SLS" if edit_sls else "ULS"
                                action_verb_preview = "viewing" if is_design_driven else "editing"

                                if not is_design_driven:
                                    st.caption("Design actions: Manual")
                                else:
                                    st.caption("Design actions: From SFD/BMD")
                                st.caption(f"Currently {action_verb_preview}: **{selected_mode_preview}** loads")

                        new_mode = "SLS" if edit_sls else "ULS"

                        if new_mode != prev_mode:
                            st.session_state["loads_edit_mode"] = prev_mode
                            save_proxies_to_active_set()
                            st.session_state["loads_edit_mode"] = new_mode
                            load_proxies_from_active_set()
                            st.session_state["inputs_load_Mstar_pos_proxy"] = st.session_state.get("load_Mstar_pos_proxy", 0.0)
                            st.session_state["inputs_load_Mstar_neg_proxy"] = st.session_state.get("load_Mstar_neg_proxy", 0.0)
                            st.session_state["inputs_load_Nstar_proxy"] = st.session_state.get("load_Nstar_proxy", 0.0)
                            recalc_derived_values()
                            update_results()
                        else:
                            st.session_state["loads_edit_mode"] = new_mode
                        selected_mode = st.session_state.get("loads_edit_mode", "ULS")
                        selected_prefix = "sls" if selected_mode == "SLS" else "uls"

                        if is_design_driven:
                            st.info("Design actions are currently driven by the Design / Teaching page and are read-only here.")

                        m_pos_proxy_widget_key = get_widget_key_for_shared("load_Mstar_pos_proxy", prefix="inputs_") or "inputs_load_Mstar_pos_proxy"
                        m_neg_proxy_widget_key = get_widget_key_for_shared("load_Mstar_neg_proxy", prefix="inputs_") or "inputs_load_Mstar_neg_proxy"
                        n_proxy_widget_key = get_widget_key_for_shared("load_Nstar_proxy", prefix="inputs_") or "inputs_load_Nstar_proxy"

                        display_Mu_pos = get_param(f"{selected_prefix}_Mstar_pos_manual", max(0.0, get_param(f"{selected_prefix}_Mstar", 0.0)))
                        display_Mu_neg = get_param(f"{selected_prefix}_Mstar_neg_manual", max(0.0, -get_param(f"{selected_prefix}_Mstar", 0.0)))
                        display_N = get_param(f"{selected_prefix}_Nstar", 0.0)
                        display_P = get_param("P_star", 0.0)

                        if is_design_driven:
                            if st.session_state.get(m_pos_proxy_widget_key) != display_Mu_pos:
                                st.session_state[m_pos_proxy_widget_key] = display_Mu_pos
                            if st.session_state.get(m_neg_proxy_widget_key) != display_Mu_neg:
                                st.session_state[m_neg_proxy_widget_key] = display_Mu_neg
                            if st.session_state.get(n_proxy_widget_key) != display_N:
                                st.session_state[n_proxy_widget_key] = display_N
                            if st.session_state.get("bending_P_star") != display_P:
                                st.session_state["bending_P_star"] = display_P

                        Mu_star_pos_val = max(0.0, _coalesce_num(display_Mu_pos, 0.0))
                        Mu_star_neg_val = max(0.0, _coalesce_num(display_Mu_neg, 0.0))
                        N_star_val = _coalesce_num(display_N, 0.0)
                        P_star_val = _coalesce_num(display_P, 0.0)
                        phi_b_val = _coalesce_num(st.session_state.get("bending_phi_b", get_param("phi_bend", 0.85)), 0.85)

                        number_row(
                            "Positive design moment Mu*+ (kNm)",
                            m_pos_proxy_widget_key,
                            Mu_star_pos_val,
                            sync_callbacks,
                            disabled=is_design_driven,
                            help_text=(
                                "Sagging bending demand magnitude. Positive bending corresponds to top compression and bottom tension."
                            ),
                        )
                        number_row(
                            "Negative design moment Mu*- (kNm)",
                            m_neg_proxy_widget_key,
                            Mu_star_neg_val,
                            sync_callbacks,
                            disabled=is_design_driven,
                            help_text=(
                                "Hogging bending demand magnitude. Enter as positive magnitude for top tension / bottom compression."
                            ),
                        )
                        number_row(
                            "Axial force N* (kN)",
                            n_proxy_widget_key,
                            N_star_val,
                            sync_callbacks,
                            disabled=is_design_driven,
                            help_text=(
                                "Axial force acting with bending. Compression (negative in many "
                                "conventions) can reduce tension in the steel; tension increases demand."
                            ),
                        )
                        number_row(
                            "Prestress force P* (kN)",
                            "bending_P_star",
                            P_star_val,
                            sync_callbacks,
                            disabled=is_design_driven,
                            help_text=(
                                "Prestress / pre-compression in the section. Increasing P* typically "
                                "reduces tensile demand in the bottom reinforcement."
                            ),
                        )
                        number_row(
                            "Maximum bending strength factor phi_b,max",
                            "bending_phi_b",
                            phi_b_val,
                            sync_callbacks,
                            help_text=(
                                "Upper limit for the AS 3600 bending strength factor. The "
                                "authoritative calculation derives phi from the calculated k_u "
                                "and applies this value only as a maximum."
                            ),
                        )

                with col_geom_mat:
                    if col_geom_mat.open:
                        render_section_title("Geometry & Materials")
                        shape_options = ["RECT", "T", "I"]
                        sec_shape_current = st.session_state.get("sec_shape", "RECT")
                        if sec_shape_current not in shape_options:
                            sec_shape_current = "RECT"

                        select_row(
                            "Section shape",
                            "bending_sec_shape",
                            shape_options,
                            sec_shape_current,
                            sync_callbacks,
                            help_text="Matches Inputs page. Controls which geometry fields are shown.",
                        )

                        # Get current values (widget key takes precedence if exists, otherwise use shared key)
                        D_val = _coalesce_num(st.session_state.get("bending_D", get_param("D", 600.0)), 600.0)
                        L_val = _coalesce_num(st.session_state.get("bending_L", get_param("L", 3000.0)), 3000.0)

                        sec_shape = st.session_state.get("bending_sec_shape", st.session_state.get("sec_shape", "RECT"))

                        if sec_shape == "RECT":
                            b_val = _coalesce_num(st.session_state.get("bending_b", get_param("b", 400.0)), 400.0)
                            number_row(
                                "Width b (mm)",
                                "bending_b",
                                b_val,
                                sync_callbacks,
                                help_text=(
                                    "Section width. Increasing b increases compression block area and "
                                    "reduces required tensile steel for a given Mu*."
                                ),
                            )

                        elif sec_shape == "T":
                            bf_val = _coalesce_num(st.session_state.get("bending_bf", get_param("bf", 600.0)), 600.0)
                            tf_val = _coalesce_num(st.session_state.get("bending_tf", get_param("tf", 120.0)), 120.0)
                            bw_val = _coalesce_num(st.session_state.get("bending_bw", get_param("bw", 300.0)), 300.0)

                            number_row("Flange width bf (mm)", "bending_bf", bf_val, sync_callbacks)
                            number_row("Flange thickness tf (mm)", "bending_tf", tf_val, sync_callbacks)
                            number_row("Web width bw (mm)", "bending_bw", bw_val, sync_callbacks)

                        elif sec_shape == "I":
                            bf_val = _coalesce_num(st.session_state.get("bending_bf", get_param("bf", 600.0)), 600.0)
                            tf_val = _coalesce_num(st.session_state.get("bending_tf", get_param("tf", 120.0)), 120.0)
                            tw_val = _coalesce_num(st.session_state.get("bending_tw", get_param("tw", 200.0)), 200.0)

                            number_row("Top flange width bf (mm)", "bending_bf", bf_val, sync_callbacks)
                            number_row("Top flange thickness tf (mm)", "bending_tf", tf_val, sync_callbacks)
                            number_row("Web thickness tw (mm)", "bending_tw", tw_val, sync_callbacks)
                        number_row(
                            "Depth D (mm)",
                            "bending_D",
                            D_val,
                            sync_callbacks,
                            help_text=(
                                "Overall section depth. Larger D increases lever arm (d) and "
                                "typically increases bending capacity."
                            ),
                        )
                        number_row(
                            "Span L (mm)",
                            "bending_L",
                            L_val,
                            sync_callbacks,
                            help_text=(
                                "Member span. Used mainly for serviceability checks and linking to "
                                "deflection; not directly in φMu,cap here."
                            ),
                        )

                        # Get current values (widget key takes precedence if exists, otherwise use shared key)
                        fc_val = _coalesce_num(st.session_state.get("bending_fc", get_param("fc", 40.0)), 40.0)
                        fsy_val = _coalesce_num(st.session_state.get("bending_fsy", get_param("fsy", 500.0)), 500.0)

                        number_row(
                            "Concrete strength f'c (MPa)",
                            "bending_fc",
                            fc_val,
                            sync_callbacks,
                            help_text=(
                                "Concrete compressive strength. Higher f'c increases compression "
                                "capacity and may reduce required steel, but also changes ductility limits."
                            ),
                        )
                        number_row(
                            "Steel yield fsy (MPa)",
                            "bending_fsy",
                            fsy_val,
                            sync_callbacks,
                            help_text=(
                                "Yield strength of reinforcing steel. Higher fsy increases the "
                                "force carried by a given area of steel."
                            ),
                        )

                    _bend_sec_shape_ui = str(
                        st.session_state.get("bending_sec_shape")
                        or st.session_state.get("sec_shape")
                        or get_param("sec_shape", "RECT")
                        or "RECT"
                    )
                    _bend_is_ti = normalized_sec_shape_ui(_bend_sec_shape_ui) in ("T", "I")
                    _bend_bot_title, _bend_top_title = main_longitudinal_reo_pair_labels(
                        _bend_sec_shape_ui, variant="bending"
                    )

                with col_bend_bot:
                    if col_bend_reo.open:
                        _bend_bot_title_col, _bend_bot_info_col = st.columns([0.92, 0.08], vertical_alignment="center")
                        with _bend_bot_title_col:
                            render_section_title(_bend_bot_title)
                        rowgap_bot_val = float(st.session_state.get("bending_rowgap_bot", get_param("rowgap_bot", 60.0)))
                        with _bend_bot_info_col:
                            with info_i_button(help_text="Row count and vertical gap between reinforcement layers."):
                                render_longitudinal_reo_row_config_controls(
                                    page_prefix="bending",
                                    section="bot",
                                    sync_callbacks=sync_callbacks,
                                    rowgap_widget_key="bending_rowgap_bot",
                                    rowgap_default=rowgap_bot_val,
                                    rowgap_help_text="Clear vertical gap between reinforcement rows (mm).",
                                    sec_shape=_bend_sec_shape_ui,
                                )

                        st.markdown('<div class="compact-reo">', unsafe_allow_html=True)

                        if st.session_state.get("_reo_msg_bot_auto_layer2", False):
                            show_reo_message("auto_layer2", layer="Bottom Layer 1")
                            st.session_state["_reo_msg_bot_auto_layer2"] = False

                        if st.session_state.get("_reo_msg_bot_layer2_overwritten", False):
                            show_reo_message("layer2_overwritten", layer="Bottom Layer 1")
                            st.session_state["_reo_msg_bot_layer2_overwritten"] = False

                        if st.session_state.get("_reo_error_bot_1", False):
                            show_reo_message("layout_invalid", layer="Bottom Layer 1")
                            st.session_state["_reo_error_bot_1"] = False

                        warning_bot_1 = st.session_state.get("_reo_warning_bot_1")
                        if warning_bot_1:
                            s_min_val = st.session_state.get("_reo_s_min_bot_1", 25.0)
                            show_reo_message("spacing_clamped", layer="Bottom Layer 1", s_min=s_min_val)
                            st.session_state["_reo_warning_bot_1"] = None
                            st.session_state["_reo_s_min_bot_1"] = None

                        render_longitudinal_reo_rows(
                            page_prefix="bending",
                            section="bot",
                            sync_callbacks=sync_callbacks,
                            layout_modes=REO_LAYOUT_MODE,
                            count_options=REO_COUNTS_0_12,
                            spacing_options=REO_SPACINGS,
                            dia_options=REO_BAR_DIAS,
                            single_column=True,
                            sec_shape=_bend_sec_shape_ui,
                        )

                        cover_bot_val = _coalesce_num(st.session_state.get("bending_cover_bot", get_param("cover_bot", 40.0)), 40.0)

                        number_row(
                            "Bottom cover (mm)",
                            "bending_cover_bot",
                            cover_bot_val,
                            sync_callbacks,
                            help_text=(
                                "Concrete cover to bottom web reinforcement (T/I: stem/web, not flange). Increasing cover reduces "
                                "effective depth d and reduces φMu,cap, but may be required for durability."
                                if _bend_is_ti
                                else (
                                    "Concrete cover to bottom reinforcement. Increasing cover reduces "
                                    "effective depth d and reduces φMu,cap, but may be required for durability."
                                )
                            ),
                        )


                        st.markdown("</div>", unsafe_allow_html=True)

                with col_bend_top:
                    if col_bend_reo.open:
                        _bend_top_title_col, _bend_top_info_col = st.columns([0.92, 0.08], vertical_alignment="center")
                        with _bend_top_title_col:
                            render_section_title(_bend_top_title)
                        rowgap_top_val = float(st.session_state.get("bending_rowgap_top", get_param("rowgap_top", 60.0)))
                        with _bend_top_info_col:
                            with info_i_button(help_text="Row count and vertical gap between reinforcement layers."):
                                render_longitudinal_reo_row_config_controls(
                                    page_prefix="bending",
                                    section="top",
                                    sync_callbacks=sync_callbacks,
                                    rowgap_widget_key="bending_rowgap_top",
                                    rowgap_default=rowgap_top_val,
                                    rowgap_help_text="Clear vertical gap between reinforcement rows (mm).",
                                    sec_shape=_bend_sec_shape_ui,
                                )

                        st.markdown('<div class="compact-reo">', unsafe_allow_html=True)

                        if st.session_state.get("_reo_msg_top_auto_layer2", False):
                            show_reo_message("auto_layer2", layer="Top Layer 1")
                            st.session_state["_reo_msg_top_auto_layer2"] = False

                        if st.session_state.get("_reo_msg_top_layer2_overwritten", False):
                            show_reo_message("layer2_overwritten", layer="Top Layer 1")
                            st.session_state["_reo_msg_top_layer2_overwritten"] = False

                        if st.session_state.get("_reo_error_top_1", False):
                            show_reo_message("layout_invalid", layer="Top Layer 1")
                            st.session_state["_reo_error_top_1"] = False

                        warning_top_1 = st.session_state.get("_reo_warning_top_1")
                        if warning_top_1:
                            s_min_val = st.session_state.get("_reo_s_min_top_1", 25.0)
                            show_reo_message("spacing_clamped", layer="Top Layer 1", s_min=s_min_val)
                            st.session_state["_reo_warning_top_1"] = None
                            st.session_state["_reo_s_min_top_1"] = None

                        render_longitudinal_reo_rows(
                            page_prefix="bending",
                            section="top",
                            sync_callbacks=sync_callbacks,
                            layout_modes=REO_LAYOUT_MODE,
                            count_options=REO_COUNTS_0_12,
                            spacing_options=REO_SPACINGS,
                            dia_options=REO_BAR_DIAS,
                            single_column=True,
                            sec_shape=_bend_sec_shape_ui,
                        )

                        cover_top_val = _coalesce_num(
                            st.session_state.get("bending_cover_top", get_param("cover_top", 40.0)),
                            40.0,
                        )

                        number_row(
                            "Top cover (mm)",
                            "bending_cover_top",
                            cover_top_val,
                            sync_callbacks,
                            help_text=(
                                "Concrete cover to top web reinforcement (T/I: stem/web, not flange). Affects effective depth to "
                                "compression reinforcement and durability."
                                if _bend_is_ti
                                else (
                                    "Concrete cover to top reinforcement. Affects effective depth to "
                                    "compression reinforcement and durability."
                                )
                            ),
                        )


                        st.markdown("</div>", unsafe_allow_html=True)
    render_timing_mark("bending_page.runtime.presentation.inputs.end")

    with st.container(key="bending_post_inputs_calculation_stage"):
        with st.container():
            # Resolve the active bending case before either presentation block
            # renders.  Both the diagrams and the cards consume this same
            # revision-matched publication; neither presentation owns it.
            detail_view = st.session_state.get("bending_detail_view", "positive")
            if detail_view not in _valid_bending_views and _valid_bending_views:
                detail_view = _valid_bending_views[0]
            showing_negative = detail_view == "negative" and has_hogging_case
            top_results_active = dict(top_results)
            Ast_active = Ast_bot
            d_active = d_eff
            Mu_uls_active = Mu_pos_star if has_sagging_case else 0.0
            Mu_sls_active = Ms_pos_star if has_sagging_case else 0.0
            if showing_negative:
                dn = float(top_results_neg.get("dn_mm", 0.0) or 0.0)
                gamma_active = float(
                    top_results_neg.get("gamma", top_results.get("gamma", 0.0))
                    or 0.0
                )
                d_calc = float(top_results_neg.get("d_mm", d_neg_val) or d_neg_val)
                active_lever_arm = compression_block_lever_arm_values(
                    dn_mm=dn,
                    gamma=gamma_active,
                    d_mm=d_calc,
                )
                a_active = active_lever_arm["a"]
                z_active = active_lever_arm["z"]
                top_results_active.update({
                    "phi_Mu_cap": float(top_results_neg.get("phi_Mu_kNm", 0.0) or 0.0),
                    "Mu_util": float(top_results_neg.get("util", 0.0) or 0.0),
                    "ku": float(top_results_neg.get("ku", 0.0) or 0.0),
                    "c": dn,
                    "a": a_active,
                    "z": z_active,
                    "d": d_calc,
                })
                Ast_active = float(get_param("Ast_top", 0.0) or 0.0)
                d_active = d_calc
                Mu_uls_active = Mu_neg_star
                Mu_sls_active = Ms_neg_star
            else:
                top_results_active.update(top_results_pos)
                top_results_active.update({
                    "phi_Mu_cap": float(top_results_pos.get("phi_Mu_kNm", top_results.get("phi_Mu_cap", 0.0)) or 0.0),
                    "Mu_util": float(top_results_pos.get("util", top_results.get("Mu_util", 0.0)) or 0.0),
                    "ku": float(top_results_pos.get("ku", top_results.get("ku", 0.0)) or 0.0),
                    "c": float(top_results_pos.get("dn_mm", top_results.get("c", 0.0)) or 0.0),
                    "d": float(top_results_pos.get("d_mm", d_eff) or d_eff),
                })

            with calc_blocks_container:
                render_timing_mark("bending_page.runtime.checks.start")
                from bending_tabs import (
                    render_min_strength_tab,
                    render_sls_tab,
                    render_uls_tab,
                )

                # ---------------- Step-by-step tabs ----------------
                apply_step_summary_expander_css()
                page_divider()
                # Put all extra rhythm above the heading; keep no subheading
                # or additional gap between the title and calculation tabs.
                st.markdown(
                    f"""
                    <div class="bending-checks-heading-block" style="padding-top:28px;margin:0 0 0.75rem;">
                      <div style="color:#10234a;font-size:17.6px;font-weight:600;line-height:1.35;margin:0;">
                        Bending design checks
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Bending calculation tabs are client-side Streamlit tabs.
                # Unlike a radio selector, changing one does not rerun this
                # result-page fragment or reset the main page scroller.
                uls_checks_tab, sls_checks_tab, minimum_checks_tab = render_stable_tabs(
                    st,
                    labels=("ULS Checks", "SLS Checks", "Minimum strength checks"),
                    scope_id="bending-calculation-checks",
                )
                with uls_checks_tab:
                    render_uls_tab(
                        top_results_active,
                        b,
                        D,
                        fc,
                        fsy,
                        Ast_active,
                        d_active,
                        summary_mode=False,
                        Mu_star_override=Mu_uls_active,
                        moment_sign=detail_view,
                    )
                with sls_checks_tab:
                    render_sls_tab(
                        top_results_active,
                        b,
                        D,
                        d_active,
                        Ast_active,
                        Ec,
                        Es,
                        Mu_sls_active,
                        summary_mode=False,
                        moment_sign=detail_view,
                    )
                with minimum_checks_tab:
                    render_min_strength_tab(
                        top_results_active, b, D, fc, fsy, Ast_active,
                        summary_mode=False,
                    )

                # Keep the authoritative calculation sequence pedagogical:
                # neutral-axis solution must precede strain compatibility.
                # Reorder the complete rendered cards, including their mounted
                # bodies, rather than duplicating either calculation.
                import streamlit.components.v1 as components
                components.html(
                    """
                    <script>
                    (() => {
                      const doc = window.parent.document;
                      const cards = [...doc.querySelectorAll('[data-testid="stExpander"]')];
                      const find = (prefix) => cards.find((card) => {
                        const text = (card.innerText || '').replace(/\\s+/g, ' ').trim();
                        return text.startsWith(prefix);
                      });
                      const strain = find('Check 2 — Strain compatibility') || find('Check 2 - Strain compatibility');
                      const neutral = find('Check 3 — Neutral-axis') || find('Check 3 - Neutral-axis');
                      if (!strain || !neutral) return;
                      const strainBlock = strain.closest('[data-testid="stLayoutWrapper"]') || strain.parentElement;
                      const neutralBlock = neutral.closest('[data-testid="stLayoutWrapper"]') || neutral.parentElement;
                      if (strainBlock && neutralBlock && strainBlock.parentElement === neutralBlock.parentElement) {
                        neutralBlock.parentElement.insertBefore(neutralBlock, strainBlock);
                      }
                    })();
                    </script>
                    """,
                    height=0,
                )

                # Handle pending scroll after content has rendered
                pending_scroll_uid = st.session_state.get("bending_pending_scroll_uid")
                if pending_scroll_uid:
                    # Import jump_nav functions
                    from jump_nav import scroll_to_jump_after_render

                    # Set jump_to for scroll function
                    st.session_state["jump_to"] = pending_scroll_uid

                    # Scroll after content has rendered
                    scroll_to_jump_after_render()

                    # Clear pending scroll
                    del st.session_state["bending_pending_scroll_uid"]
                st.markdown(
                    '<span data-testid="bending-calculation-ready" '
                    'aria-hidden="true" style="display:none"></span>',
                    unsafe_allow_html=True,
                )
                render_timing_mark("bending_page.runtime.checks.end")

            # --------------------------------------------------
            # Material stress–strain curves (concrete + steel), rendered below
            # the section diagrams together with the state selector.
            # --------------------------------------------------

    # Handle scroll after all content is rendered (for cross-page navigation from Inputs)
    from jump_nav import scroll_to_jump_after_render
    scroll_to_jump_after_render()

# ============================
# MAIN GUARD
# ============================
if __name__ == "__main__":
    render_bending()
