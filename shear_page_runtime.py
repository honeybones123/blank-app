import math
import os
import re
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
    recalc_derived_values,
    render_timing_mark,
)
from shear_visuals import (
    build_shear_cross_section_figure,
    build_shear_side_view_figure,
)
from beam_diagram_runtime import plot_sfd_bmd_plotly
# Shared helpers (same contract as Inputs/Bending)
from widgets_helpers import apply_result_page_css, calcbox, apply_step_summary_expander_css, info_i_button, page_divider, render_lazy_expander, render_page_explainer_expander, render_section_title, render_plotly_diagram, render_image_diagram
from engineering_check_ui import SHEAR_ROW_UID_TO_TAB
from ui_seamless_steps import bind_summary_clicks
from shear_checks_helpers import (
    build_live_canonical_shear_state,
    build_shear_calc_bundle_from_state,
    build_shear_check_rows_from_state,
)
from calculations.shear import (
    cotangent as cot,
    effective_shear_depth_mm,
    longitudinal_strain_fallback_values,
    mcft_kv_theta_values,
    shear_capacity_utilisation_values,
    shear_check_display_scalars,
    shear_reinforcement_spacing_check_values,
    stirrup_area_mm2,
    torsion_section_geometry_values,
    web_crushing_fallback_values,
)
from engineering_page_sections.stable_tabs import (
    render_stable_tabs,
)
from engineering_page_sections.shear_page_context import (
    build_shear_page_snapshot,
)
from engineering_page_sections.shear_checks_context import (
    build_shear_checks_snapshot,
)
from engineering_page_sections.shear_summary import (
    render_shear_explainer,
    render_shear_summary,
)
from engineering_page_sections.shear_page_shell import ShearPageShell
from engineering_page_sections.shear_inputs import render_shear_inputs
from engineering_page_sections.shear_torsion_dimensions_checks import (
    ShearTorsionDimensionsView,
    render_shear_torsion_dimensions_checks,
)
from engineering_page_sections.shear_mcft_strength_checks import (
    ShearMcftStrengthView,
    _render_animated_plotly_figure,
    render_shear_mcft_strength_checks,
)
from engineering_page_sections.shear_reinforcement_checks import (
    ShearReinforcementView,
    render_shear_reinforcement_checks,
)
from reporting.shear_report_projection import build_shear_report


from engineering_page_sections.shear_visualisation import (
    ShearVisualisationRuntime,
    _render_centered_shear_plotly,
    render_shear_visualisation_block,
)


def _render_shear_diagram_bundle_panel_impl(
    *,
    runtime: ShearVisualisationRuntime,
    diagram_shell_generation: int,
) -> None:
    render_shear_visualisation_block(
        runtime,
        diagram_shell_generation=diagram_shell_generation,
    )


_render_shear_diagram_bundle_panel = st.fragment(
    _render_shear_diagram_bundle_panel_impl
)

# ------------------------------------------------------------
#  Helper functions for diagrams
# ------------------------------------------------------------

SHEAR_CHECK_TAB_LABELS = (
    "Torsion + dimensions",
    "MCFT and strength checks",
    "Shear reinforcement checks",
)


def _safe_image(path: str, caption: str | None = None, width: int | None = None, use_container_width: bool | None = None):
    """Tiny helper so missing images don't break the app."""
    candidate_paths = [path]
    if not os.path.isabs(path):
        candidate_paths.append(os.path.join(os.path.dirname(__file__), path))

    resolved_path = next((candidate for candidate in candidate_paths if os.path.exists(candidate)), None)
    if not resolved_path:
        st.info(f"Add image file at `{path}` for: {caption or 'shear illustration'}")
        return

    image_key = "shear_reference_" + re.sub(r"[^A-Za-z0-9_]+", "_", str(resolved_path))
    try:
        if width is not None:
            render_image_diagram(
                resolved_path,
                key=image_key,
                title=caption or "Shear reference diagram",
                caption=caption,
                width=width,
            )
        elif use_container_width is not None:
            render_image_diagram(
                resolved_path,
                key=image_key,
                title=caption or "Shear reference diagram",
                caption=caption,
                use_container_width=use_container_width,
            )
        else:
            render_image_diagram(
                resolved_path,
                key=image_key,
                title=caption or "Shear reference diagram",
                caption=caption,
                use_container_width=True,
            )
    except Exception:
        st.info(f"Unable to open image `{path}` right now.")


# ------------------------------------------------------------
#  COMPUTE FUNCTION (no UI rendering)
# ------------------------------------------------------------
def compute_shear_results(publish: bool = True) -> dict:
    """
    Compute shear results without UI rendering.

    Args:
        publish: If True, publish to results dict for report export.

    Returns:
        dict with computed results
    """
    from state_and_helpers import recalc_derived_values

    recalc_derived_values()

    shear_bundle = build_shear_calc_bundle_from_state(st.session_state)
    live_shear_state = shear_bundle["live_state"]
    actions = shear_bundle["actions_used"]
    results = shear_bundle["results"]
    phi = float(shear_bundle["phi"])

    # --- Read inputs (shared canonical state) ---
    b = live_shear_state["b"]
    D = live_shear_state["D"]
    d = live_shear_state["d"]
    fc = live_shear_state["fc"]
    fsy = live_shear_state["fsy"]
    Ec = live_shear_state["Ec"]
    Es = live_shear_state["Es"]
    M_star = live_shear_state["Mu"]
    Vu_star = live_shear_state["Vu"]
    Tu_star = live_shear_state["Tu"]
    N_star = live_shear_state["Nu"]
    P_v = live_shear_state["Pu"]

    lig_d = live_shear_state["lig_d"]
    legs = live_shear_state["lig_legs"]
    s_lig = live_shear_state["s_lig"]

    # Derived metrics
    utilisation_values = shear_capacity_utilisation_values(results, phi)
    phi_Vu_cap = utilisation_values["phi_Vu_cap"]
    util = utilisation_values["util"]
    phi_Vu_max = utilisation_values["phi_Vu_max_kN"]
    Vuc_util = utilisation_values["web_util"]

    # Minimum shear reinforcement + spacing checks
    reinforcement_checks = shear_reinforcement_spacing_check_values(
        Asv_mm2=results.Asv,
        s_lig_mm=s_lig,
        fc_mpa=fc,
        b_v_mm=results.b_v,
        f_syv_mpa=results.f_syv,
        D_mm=D,
    )
    Asv_over_s = reinforcement_checks["Asv_over_s"]
    Asv_min_over_s = reinforcement_checks["Asv_min_over_s"]
    min_shear_ok = reinforcement_checks["min_shear_ok"]
    max_spacing = reinforcement_checks["max_spacing"]
    spacing_ok = reinforcement_checks["spacing_ok"]

    shear_report = build_shear_report(
        results=results,
        phi=phi,
        phi_Vu_cap=phi_Vu_cap,
        util=util,
        Vu_star=Vu_star,
        Tu_star=Tu_star,
        s_lig=s_lig,
        Asv_over_s=Asv_over_s,
        Asv_min_over_s=Asv_min_over_s,
        max_spacing=max_spacing,
        min_shear_ok=min_shear_ok,
        spacing_ok=spacing_ok,
    )

    if publish:
        update_results(
            phi_Vu_cap=phi_Vu_cap,
            Vu_utilisation=util if not math.isnan(util) else 0.0,
            Vu_max_kN=results.Vu_max_kN,
            phi_Vu_max_kN=phi_Vu_max,
            V_eq_kN=results.V_eq,
            Vuc_utilisation=Vuc_util if not math.isnan(Vuc_util) else None,
        )

        st.session_state.setdefault("results", {})
        st.session_state["results"]["shear_report"] = shear_report

    return {
        "phi_Vu_cap": phi_Vu_cap,
        "Vu_utilisation": util,
        "V_eq": results.V_eq,
        "Vuc_kN": results.Vuc_kN,
        "Vus_kN": results.Vus_kN,
        "shear_report": shear_report,
    }


# ------------------------------------------------------------
#  MAIN PAGE RENDER FUNCTION
# ------------------------------------------------------------
def render_shear():
    render_timing_mark("shear_page.runtime.start")
    # Handle cross-page navigation from Inputs page
    from jump_nav import JUMP_NAV_TAB_KEY, get_jump_uid

    st.session_state["shear_page_auto_spacing_ui_removed"] = True
    st.session_state["shear_page_spacing_mode"] = "manual_provided_only"

    get_jump_uid()
    _jt = st.session_state.get("jump_to")
    if _jt:
        _tab = SHEAR_ROW_UID_TO_TAB.get(str(_jt).strip())
        if _tab:
            st.session_state[JUMP_NAV_TAB_KEY] = _tab

    apply_result_page_css()
    apply_step_summary_expander_css()

    # Initialize step UI state (always-summary mode - no checkbox)

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

    sync_callbacks = get_sync_callbacks()

    # Publish the already-calculated authoritative summary before the heavier
    # inputs, diagrams and detailed checks.  This is the first content users
    # see, so it must not wait for the rest of the page to finish rendering.
    render_timing_mark("shear_page.runtime.summary.start")
    shear_pack = build_shear_check_rows_from_state(st.session_state)
    published_results = st.session_state.get("results", {})
    if isinstance(published_results, dict):
        published_results = published_results.get("shear", {})
    if not isinstance(published_results, dict):
        published_results = {}
    shear_page_snapshot = build_shear_page_snapshot(
        engineering_state=build_live_canonical_shear_state(st.session_state),
        check_pack=shear_pack,
        published_results=published_results,
        section_layout=st.session_state.get("section_layout"),
        actions_mode=get_param("actions_mode", "manual"),
    )
    render_shear_summary(
        shear_page_snapshot,
        publish_summary=lambda capacity, utilisation: update_results(
            phi_Vu_cap=capacity,
            Vu_utilisation=utilisation,
        ),
        publish_rows=lambda rows: update_results("shear", {"rows": rows}),
        # Bind after the page's target tabs/anchors exist. Installing this
        # before the heavy Shear body made the retry window race the page
        # render and produced less reliable scrolling than Bending. This does
        # not change the summary, calculation boxes, or their preload path.
        bind_clicks=lambda: None,
        render_explainer_expander=render_page_explainer_expander,
        render_explainer=lambda: render_shear_explainer(
            st,
            safe_image=_safe_image,
            info_button=info_i_button,
            calc_box=calcbox,
        ),
    )
    render_timing_mark("shear_page.runtime.summary.end")

    shear_page_shell = ShearPageShell.reserve_after_summary(
        st,
        before_first_divider=lambda: render_timing_mark("shear_page.runtime.visualisation.start"),
        render_first_divider=page_divider,
    )
    shear_diagram_shell_generation = int(
        st.session_state.get("_shear_diagram_shell_generation", 0) or 0
    ) + 1
    st.session_state[
        "_shear_diagram_shell_generation"
    ] = shear_diagram_shell_generation

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)  — SAME WIDGET CONTRACT
    # =====================================================
    render_timing_mark("shear_page.runtime.inputs.start")
    render_shear_inputs(
        st=st,
        page_snapshot=shear_page_snapshot,
        sync_callbacks=sync_callbacks,
    )

    page_divider()

    # -------------------------------------------------
    # Pull shared values for calculations
    # -------------------------------------------------
    shear_bundle = build_shear_calc_bundle_from_state(st.session_state)
    live_shear_state = shear_bundle["live_state"]
    shear_results = shear_bundle["results"]
    phi = float(shear_bundle["phi"])
    k_d = float(shear_bundle["k_d"])
    use_general_kv = bool(shear_bundle["use_general_kv"])
    method = str(
        get_param(
            "k_v_method",
            "General εₓ-based (Cl. 8.2.4.2)",
        )
        or "General εₓ-based (Cl. 8.2.4.2)"
    )
    shear_checks_snapshot = build_shear_checks_snapshot(
        page_snapshot=shear_page_snapshot,
        calc_bundle=shear_bundle,
        method=method,
    )
    live_shear_state = shear_checks_snapshot.torsion_dimensions.live_state
    phi = shear_checks_snapshot.torsion_dimensions.phi
    k_d = shear_checks_snapshot.torsion_dimensions.duct_factor
    use_general_kv = shear_checks_snapshot.mcft_strength.use_general_kv
    method = shear_checks_snapshot.mcft_strength.method

    b = live_shear_state["b"]
    D = live_shear_state["D"]
    d = live_shear_state["d"]
    fc = live_shear_state["fc"]
    fsy = live_shear_state["fsy"]
    Ec = live_shear_state["Ec"]
    Es = live_shear_state["Es"]
    M_star = live_shear_state["Mu"]
    V_star = live_shear_state["Vu"]
    T_star = live_shear_state["Tu"]
    N_star = live_shear_state["Nu"]
    P_v = live_shear_state["Pu"]
    lig_d = live_shear_state["lig_d"]
    legs = live_shear_state["lig_legs"]
    s_lig = live_shear_state["s_lig"]
    A_st = live_shear_state["A_st"]
    A_pt = live_shear_state["A_pt"]
    f_po = live_shear_state["f_po"]
    A_ct = live_shear_state["A_ct"]
    d_g = live_shear_state["d_g"]
    sigma_cp = live_shear_state["sigma_cp"]
    sum_duct = live_shear_state["sum_duct"]

    if not (b and D and d):
        st.error("Geometry (b, D, d) not fully defined – check Inputs / Bending tab.")
        return

    # =====================================================
    # 2. COMPUTE ALL VALUES (before tabs, so summary table can access them)
    # =====================================================
    # Read θ from shared state (read-only, no widget)
    theta_deg = float(get_param("crack_theta_deg", 45.0))

    # Pull torsion screening directly from shear_core results
    torsion_required = bool(getattr(shear_results, "torsion_required", False))
    torsion_required_limit = float(getattr(shear_results, "torsion_required_limit", 0.0) or 0.0)
    Tcr_kNm = float(getattr(shear_results, "Tcr_kNm", 0.0) or 0.0)

    b_used = float(getattr(shear_results, "b_used", b) or b)
    D_used = float(getattr(shear_results, "D_used", D) or D)
    torsion_geometry_fallback = torsion_section_geometry_values(b_used, D_used)
    A_cp = float(getattr(shear_results, "A_cp", torsion_geometry_fallback["A_cp"]) or 0.0)
    u_c = float(getattr(shear_results, "u_c", torsion_geometry_fallback["u_c"]) or 0.0)
    Ao = float(getattr(shear_results, "Ao", torsion_geometry_fallback["Ao"]) or 0.0)
    uh = float(getattr(shear_results, "uh", torsion_geometry_fallback["uh"]) or 0.0)
    A_oh = float(getattr(shear_results, "A_oh", torsion_geometry_fallback["A_oh"]) or 0.0)

    step1_req = ">" if torsion_required else "\\le"
    step1_text = (
        "required" if torsion_required else "not required (strength check only)"
    )
    torsion_status = "pass" if not torsion_required else "fail"

    # Check 2: Equivalent shear
    torsion_eq_kN = float(getattr(shear_results, "Vt_eq_kN", 0.0) or 0.0)
    V_eq = float(getattr(shear_results, "V_eq", abs(V_star)) or abs(V_star))
    shear_display_scalars = shear_check_display_scalars(
        T_star_kNm=T_star,
        D_mm=D,
        d_mm=d,
        fc_mpa=fc,
        Vuc_kN=float(getattr(shear_results, "Vuc_kN", 0.0) or 0.0),
        Vus_kN=float(getattr(shear_results, "Vus_kN", 0.0) or 0.0),
        P_v_kN=P_v,
        phi=phi,
        V_eq_kN=V_eq,
    )
    T_star_Nmm = shear_display_scalars["T_star_Nmm"]

    # Check 3: Effective section parameters
    lig_d = 10.0 if lig_d is None else float(lig_d)
    legs = 2.0 if legs is None else float(legs)
    s = 200.0 if s_lig is None else float(s_lig)

    Asv = float(getattr(shear_results, "Asv", stirrup_area_mm2(legs, lig_d)) or 0.0)
    f_syv = fsy

    b_v = float(getattr(shear_results, "b_v", b - k_d * sum_duct) or 0.0)
    d_v = float(getattr(shear_results, "d_v", effective_shear_depth_mm(D, d)) or 0.0)

    dv_1 = shear_display_scalars["dv_1"]
    dv_2 = shear_display_scalars["dv_2"]

    # Check 4: Longitudinal strain εx
    strain_fallback = longitudinal_strain_fallback_values(
        M_star_kNm=M_star,
        V_star_kN=V_star,
        T_star_kNm=T_star,
        P_v_kN=P_v,
        N_star_kN=N_star,
        d_v_mm=d_v,
        uh_mm=uh,
        Ao_mm2=Ao,
        Es_mpa=Es,
        Ec_mpa=Ec,
        A_st_mm2=A_st,
        A_pt_mm2=A_pt,
        f_po_mpa=f_po,
        A_ct_mm2=A_ct,
    )
    M_star_Nmm = float(strain_fallback["M_star_Nmm"])
    term_M = float(strain_fallback["term_M"])
    Vprime_kN = float(strain_fallback["Vprime_kN"])
    Vprime_N = float(strain_fallback["Vprime_N"])
    torsion_N = float(strain_fallback["torsion_N"])
    sqrt_inner = float(strain_fallback["sqrt_inner"])
    N_star_N = float(strain_fallback["N_star_N"])
    A_pt_fpo_N = float(strain_fallback["A_pt_fpo_N"])
    numerator_1 = float(strain_fallback["numerator_1"])
    Ep = float(strain_fallback["Ep"])
    denom1 = float(strain_fallback["denom1"])
    eps_x_1 = float(strain_fallback["eps_x_1"])
    V_abs_N = float(strain_fallback["V_abs_N"])
    numerator_2 = float(strain_fallback["numerator_2"])
    denom2 = float(strain_fallback["denom2"])
    eps_x_2 = float(strain_fallback["eps_x_2"])

    if strain_fallback["use_equation_1"]:
        eps_x_raw = float(strain_fallback["eps_x_raw"])
        eq_used = "Equation (1) – mid-depth in tension"
    else:
        eps_x_raw = float(strain_fallback["eps_x_raw"])
        eq_used = "Equation (2) – mid-depth in slight compression"

    eps_x = float(strain_fallback["eps_x"])
    mcft = mcft_kv_theta_values(
        use_general_kv=use_general_kv,
        fc_mpa=fc,
        d_g_mm=d_g,
        eps_x=eps_x,
        Asv_mm2=Asv,
        s_mm=s,
        b_v_mm=b_v,
        f_syv_mpa=f_syv,
        d_v_mm=d_v,
    )

    # Check 5: k_v and θ_v
    if use_general_kv:
        if fc <= 65:
            k_dg = float(mcft["k_dg"])
            k_dg = float(mcft["k_dg"])
            if d_g >= 16:
                k_dg = float(mcft["k_dg"])
        else:
            k_dg = float(mcft["k_dg"])

        Asv_over_s = float(mcft["Asv_over_s"])
        Asv_min_over_s = float(mcft["Asv_min_over_s"])

        if mcft["low_stirrup_ratio"]:
            k_v = float(mcft["k_v"])
            kv_case = "general MCFT with **low stirrup ratio** ($A_{sv}/s < (A_{sv}/s)_{min}$)"
        else:
            k_v = float(mcft["k_v"])
            kv_case = "general MCFT with **adequate stirrup ratio**"

        theta_v_deg = float(mcft["theta_v_deg"])
    else:
        if mcft["low_stirrup_ratio"]:
            k_v = float(mcft["k_v"])
            kv_case = "simplified non-prestressed – **low stirrup ratio**"
        else:
            k_v = float(mcft["k_v"])
            kv_case = "simplified non-prestressed – **minimum stirrups provided**"
        theta_v_deg = float(mcft["theta_v_deg"])
        k_dg = float(mcft["k_dg"])

    eps_x = float(getattr(shear_results, "eps_x", eps_x) or 0.0)
    k_v = float(getattr(shear_results, "k_v", k_v) or 0.0)
    theta_v_deg = float(getattr(shear_results, "theta_v_deg", theta_v_deg) or 0.0)
    theta_v_rad = float(getattr(shear_results, "theta_v_rad", math.radians(theta_v_deg)) or 0.0)

    # The visualisation placeholder is created before the input rail, but the
    # actual diagram work happens here. Keep a separate measured boundary so
    # route timings do not attribute the widget rail to the diagram.
    render_timing_mark("shear_page.runtime.inputs.end")
    render_timing_mark("shear_page.runtime.visualisation.render.start")
    shear_page_shell.render_visualisation(
        lambda: _render_shear_diagram_bundle_panel(
            runtime=ShearVisualisationRuntime(
                st=st,
                get_param=get_param,
                render_timing_mark=render_timing_mark,
                render_plotly_diagram=render_plotly_diagram,
                render_centered_plotly=_render_centered_shear_plotly,
                render_animated_plotly=_render_animated_plotly_figure,
                render_section_title=render_section_title,
                info_button=info_i_button,
                render_lazy_expander=render_lazy_expander,
                render_tabs=render_stable_tabs,
                build_cross_section_figure=build_shear_cross_section_figure,
                build_side_view_figure=build_shear_side_view_figure,
                build_sfd_bmd_figure=plot_sfd_bmd_plotly,
                theta_v_deg=theta_v_deg,
            ),
            diagram_shell_generation=shear_diagram_shell_generation,
        )
    )
    render_timing_mark("shear_page.runtime.visualisation.render.end")

    # Check 6: Concrete shear contribution
    sqrt_fc_limited = float(getattr(shear_results, "sqrt_fc_limited", shear_display_scalars["sqrt_fc_limited"]) or 0.0)
    Vuc_kN = float(getattr(shear_results, "Vuc_kN", 0.0) or 0.0)

    # Check 7: Steel shear contribution
    Vus_kN = float(getattr(shear_results, "Vus_kN", 0.0) or 0.0)

    # Check 8: Combined shear strength
    Vu_total_kN = float(getattr(shear_results, "Vu_total_kN", shear_display_scalars["Vu_total_kN"]) or 0.0)
    phi_Vu = float(getattr(shear_results, "phi_Vu", shear_display_scalars["phi_Vu"]) or 0.0)
    shear_ok = bool(getattr(shear_results, "shear_ok", shear_display_scalars["shear_ok"]))
    shear_status = "pass" if shear_ok else "fail"

    # Check 9: Web crushing
    theta_1_deg = 90.0
    theta_1_rad = math.radians(theta_1_deg)
    cot_theta_v = cot(theta_v_rad)
    cot_theta_1 = cot(theta_1_rad)

    Vu_max_kN = float(getattr(shear_results, "Vu_max_kN", 0.0) or 0.0)
    web_crushing_fallback = web_crushing_fallback_values(
        V_star_kN=V_star,
        T_star_kNm=T_star,
        uh_mm=uh,
        A_oh_mm2=A_oh,
        b_v_mm=b_v,
        d_v_mm=d_v,
        phi=phi,
        Vu_max_kN=Vu_max_kN,
    )
    Vu_max_N = float(web_crushing_fallback["Vu_max_N"])
    V_star_N = float(web_crushing_fallback["V_star_N"])
    term_V = float(web_crushing_fallback["term_V"])
    term_T = float(web_crushing_fallback["term_T"])

    LHS = float(getattr(shear_results, "LHS", web_crushing_fallback["LHS"]) or 0.0)
    RHS = float(getattr(shear_results, "RHS", web_crushing_fallback["RHS"]) or 0.0)

    web_ok = bool(getattr(shear_results, "web_ok", web_crushing_fallback["web_ok"]))
    web_status = "pass" if web_ok else "fail"

    # Check 11: Minimum shear reinforcement (tab 3)
    check11_reinforcement = shear_reinforcement_spacing_check_values(
        Asv_mm2=Asv,
        s_lig_mm=s,
        fc_mpa=fc,
        b_v_mm=b_v,
        f_syv_mpa=f_syv,
        D_mm=D,
    )
    Asv_over_s_check11 = check11_reinforcement["Asv_over_s"]
    Asv_min_over_s_check11 = check11_reinforcement["Asv_min_over_s"]
    min_shear_ok = check11_reinforcement["min_shear_ok"]
    min_shear_status = "pass" if min_shear_ok else "fail"

    # =====================================================
    # 3. SHEAR DESIGN CHECKS UI (organized into tabs)
    # =====================================================
    render_timing_mark("shear_page.runtime.checks.start")
    render_section_title("Shear design checks")


    # Native tabs are a client-side view boundary.  Selecting a tab must not
    # rerun the page or rebuild its authoritative engineering result.
    tab1, tab2, tab3 = render_stable_tabs(
        st,
        labels=SHEAR_CHECK_TAB_LABELS,
        scope_id="shear-calculation-checks",
    )

    # =====================================================
    # TAB 1: Torsion + dimensions
    # =====================================================
    render_timing_mark("shear_page.runtime.checks.tab1.start")
    with tab1:
        render_shear_torsion_dimensions_checks(
            ShearTorsionDimensionsView(
                evidence=shear_checks_snapshot.torsion_dimensions,
                A_cp=A_cp,
                Ao=Ao,
                Asv=Asv,
                D=D,
                D_used=D_used,
                T_star=T_star,
                Tcr_kNm=Tcr_kNm,
                V_eq=V_eq,
                V_star=V_star,
                b=b,
                b_used=b_used,
                b_v=b_v,
                d=d,
                d_v=d_v,
                dv_1=dv_1,
                dv_2=dv_2,
                f_syv=f_syv,
                fc=fc,
                k_d=k_d,
                legs=legs,
                lig_d=lig_d,
                method=method,
                phi=phi,
                s=s,
                sigma_cp=sigma_cp,
                step1_req=step1_req,
                step1_text=step1_text,
                sum_duct=sum_duct,
                theta_deg=theta_deg,
                torsion_eq_kN=torsion_eq_kN,
                torsion_required=torsion_required,
                torsion_required_limit=torsion_required_limit,
                u_c=u_c,
                uh=uh,
            )
        )

    # =====================================================
    render_timing_mark("shear_page.runtime.checks.tab1.end")
    render_timing_mark("shear_page.runtime.checks.tab2.start")
    # TAB 2: MCFT and strength checks
    # =====================================================
    with tab2:
        render_shear_mcft_strength_checks(
            ShearMcftStrengthView(
                evidence=shear_checks_snapshot.mcft_strength,
                A_ct=A_ct,
                A_oh=A_oh,
                A_pt=A_pt,
                A_pt_fpo_N=A_pt_fpo_N,
                A_st=A_st,
                Asv=Asv,
                D=D,
                Ec=Ec,
                Ep=Ep,
                Es=Es,
                LHS=LHS,
                M_star=M_star,
                N_star=N_star,
                N_star_N=N_star_N,
                P_v=P_v,
                RHS=RHS,
                T_star=T_star,
                V_eq=V_eq,
                V_star=V_star,
                Vu_max_kN=Vu_max_kN,
                Vu_total_kN=Vu_total_kN,
                Vuc_kN=Vuc_kN,
                Vus_kN=Vus_kN,
                b_v=b_v,
                d=d,
                d_g=d_g,
                d_v=d_v,
                denom1=denom1,
                denom2=denom2,
                eps_x=eps_x,
                eps_x_1=eps_x_1,
                eps_x_2=eps_x_2,
                eps_x_raw=eps_x_raw,
                eq_used=eq_used,
                f_po=f_po,
                f_syv=f_syv,
                fc=fc,
                fsy=fsy,
                k_dg=k_dg,
                k_v=k_v,
                kv_case=kv_case,
                legs=legs,
                lig_d=lig_d,
                mcft=mcft,
                numerator_1=numerator_1,
                numerator_2=numerator_2,
                phi=phi,
                phi_Vu=phi_Vu,
                s=s,
                shear_ok=shear_ok,
                shear_status=shear_status,
                sqrt_fc_limited=sqrt_fc_limited,
                sqrt_inner=sqrt_inner,
                term_M=term_M,
                theta_1_deg=theta_1_deg,
                theta_v_deg=theta_v_deg,
                uh=uh,
                use_general_kv=use_general_kv,
                web_ok=web_ok,
                web_status=web_status,
            )
        )

    render_timing_mark("shear_page.runtime.checks.tab2.end")
    render_timing_mark("shear_page.runtime.checks.tab3.start")
    # TAB 3: Shear reinforcement checks
    # =====================================================
    with tab3:
        render_shear_reinforcement_checks(
            ShearReinforcementView(
                evidence=shear_checks_snapshot.reinforcement,
                Asv_min_over_s_check11=Asv_min_over_s_check11,
                Asv_over_s_check11=Asv_over_s_check11,
                min_shear_ok=min_shear_ok,
                min_shear_status=min_shear_status,
            )
        )

    render_timing_mark("shear_page.runtime.checks.end")

    render_timing_mark("shear_page.runtime.checks.tab3.end")
    st.markdown(
        '<span data-shear-page-lightweight-ready="'
        f'{shear_diagram_shell_generation}" aria-hidden="true" '
        'style="display:none"></span>',
        unsafe_allow_html=True,
    )

    # Install summary navigation only after all Shear anchors and tabs have
    # mounted, matching the proven Bending ordering.
    bind_summary_clicks()

    # Cross-page jump scroll (Inputs summary → shear/torsion calc anchors)
    from jump_nav import scroll_to_jump_after_render

    scroll_to_jump_after_render()
    render_timing_mark("shear_page.runtime.end")


if __name__ == "__main__":
    render_shear()
