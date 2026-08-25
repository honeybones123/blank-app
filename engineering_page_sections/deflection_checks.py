"""Prepared, read-only Deflection calculation-check presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from calculations.deflection import (
    compression_to_tension_steel_ratio,
    deflection_limit_check_values,
    simplified_ief_k1_factor,
    span_depth_display_values,
)
from engineering_page_sections.deflection_checks_context import DeflectionChecksSnapshot
from step_ui import render_expandable_step
from widgets_helpers import v2_checkbox, v2_number_input


@dataclass(frozen=True, slots=True)
class DeflectionCheckPresentation:
    step_id: str
    title: str
    summary_md: str
    calc_md: str
    status_kind: str | None = None
    diagram_render_fn: Callable[[], Any] | None = None
    info_render_fn: Callable[[], Any] | None = None


def render_deflection_check(check: DeflectionCheckPresentation) -> None:
    """Render one prepared check without reading engineering/session state."""

    render_expandable_step(
        page_key="deflection",
        step_id=check.step_id,
        title=check.title,
        summary_md=check.summary_md,
        status_kind=check.status_kind,
        calc_md=check.calc_md,
        diagram_render_fn=check.diagram_render_fn,
        info_render_fn=check.info_render_fn,
    )


def render_deflection_checks(
    snapshot: DeflectionChecksSnapshot,
    *,
    sync_callbacks: dict[str, Callable[..., Any]],
    get_parameter: Callable[[str, Any], Any],
) -> None:
    """Project one immutable serviceability snapshot into the five check cards."""

    get_param = get_parameter
    Asc = snapshot["Asc"]
    Ast = snapshot["Ast"]
    Ec = snapshot["Ec"]
    Ec_short = snapshot["Ec_short"]
    Fdef_kNm = snapshot["Fdef_kNm"]
    Ief_max = snapshot["Ief_max"]
    Ief_selected = snapshot["Ief_selected"]
    L_m_for_fd = snapshot["L_m_for_fd"]
    L_mm = snapshot["L_mm"]
    L_over_d = snapshot["L_over_d"]
    L_over_d_limit = snapshot["L_over_d_limit"]
    L_over_delta_long_add = snapshot["L_over_delta_long_add"]
    L_over_delta_short = snapshot["L_over_delta_short"]
    L_over_delta_total = snapshot["L_over_delta_total"]
    beff = snapshot["beff"]
    beta = snapshot["beta"]
    bw = snapshot["bw"]
    d = snapshot["d"]
    defl_limit_label = snapshot["defl_limit_label"]
    defl_limit_ratio = snapshot["defl_limit_ratio"]
    delta_long_add = snapshot["delta_long_add"]
    delta_short_sust = snapshot["delta_short_sust"]
    delta_short_total = snapshot["delta_short_total"]
    delta_total = snapshot["delta_total"]
    derived = dict(snapshot["derived"])
    fc = snapshot["fc"]
    fd_ef_meta = dict(snapshot["fd_ef_meta"])
    fd_ef_source_branch = snapshot["fd_ef_source_branch"]
    fd_ef_used = snapshot["fd_ef_used"]
    g_used = snapshot["g_used"]
    is_design_driven = snapshot["is_design_driven"]
    k1_from_ief = snapshot["k1_from_ief"]
    k1_span = snapshot["k1_span"]
    k2 = snapshot["k2"]
    k2_span = snapshot["k2_span"]
    kcs = snapshot["kcs"]
    p = snapshot["p"]
    p_lim = snapshot["p_lim"]
    phi_cc_t = snapshot["phi_cc_t"]
    psi_s = snapshot["psi_s"]
    q_used = snapshot["q_used"]
    stress_ratio = snapshot["stress_ratio"]
    support_type = snapshot["support_type"]
    sustained_mstar = snapshot["sustained_mstar"]
    sustained_sigma_cs = snapshot["sustained_sigma_cs"]
    sustained_z_comp = snapshot["sustained_z_comp"]
    use_simplified_ief = snapshot["use_simplified_ief"]
    value_source_text = snapshot["value_source_text"]
    w_source = snapshot["w_source"]
    w_sust = snapshot["w_sust"]
    w_total = snapshot["w_total"]
    use_simplified_ief_checkbox = v2_checkbox(
        label="Use simplified reinforced-member Iₑf (AS 3600 Cl. 8.5.3.1(2),(3))",
        key="defl_use_simplified_ief",
        default=use_simplified_ief,
        on_change=sync_callbacks["defl_use_simplified_ief"],
    )
    
    # Display-only: show the already computed Ief_selected
    if not use_simplified_ief_checkbox:
        Ief_user_display = v2_number_input(
            label="User-specified Iₑf (mm⁴)",
            key="defl_Ief_user",
            default=Ief_selected,
            step=1.0e10,
            format="%.3e",
            on_change=sync_callbacks["defl_Ief_user"],
        )
    
    # Build 2-line summary for Ief step
    ief_method = "Simplified" if use_simplified_ief_checkbox else "User input"
    # Guard against None values for formatting
    Ief_selected_display = Ief_selected if Ief_selected is not None else 1.0e11
    ief_summary = (
        f"**Check 1 — Effective stiffness $I_{{ef}}$**  \n"
        f"$I_{{ef}} = {Ief_selected_display:,.3e}\\,\\mathrm{{mm}}^4$  "
        f"({ief_method.lower()} reinforced-member option)"
    )
    
    # Guard against None values before formatting
    fc_display = fc if fc is not None else 32.0
    bw_display = bw if bw is not None else 300.0
    beff_display = beff if beff is not None else 300.0
    d_display = d if d is not None else 550.0
    Ast_display = Ast if Ast is not None else 2010.0
    beta_display = beta if beta is not None else 1.0
    p_display = p if p is not None else 0.0
    p_lim_display = p_lim if p_lim is not None else 0.0
    Ief_max_display = Ief_max if Ief_max is not None else 1.0e11
    k1_from_ief_display = k1_from_ief if k1_from_ief is not None else 0.0
    use_high_branch = p_display >= p_lim_display
    if use_high_branch:
        ief_branch_label = "p ≥ p_lim"
        k1_expr = simplified_ief_k1_factor(fc_display, beta_display, p_display, p_lim_display)
        k1_expr_md = (
            rf"(5 - 0.04\ \times\ {fc_display:.1f})\ \times\ "
            rf"{p_display:.5f} + 0.002"
        )
    else:
        ief_branch_label = "p < p_lim"
        k1_expr = simplified_ief_k1_factor(fc_display, beta_display, p_display, p_lim_display)
        k1_expr_md = (
            rf"0.055\ \times\ ({fc_display:.1f})^{{1/3}}/({beta_display:.3f})^{{2/3}} "
            rf"- 50\ \times\ {p_display:.5f}"
        )
    
    ief_calc_md = rf"""
    *Purpose: Compute the effective second moment of area $I_{{ef}}$ for a reinforced concrete member using the simplified expressions in AS 3600:2018 Cl. 8.5.3.1(2) and (3). This cracked stiffness is then used in all deflection checks.*
    
    **Inputs:**
    
    - Concrete strength: $f'_c = {fc_display:.1f}\,\text{{MPa}}$
    - Web / stem width (derived): $b_w = {bw_display:.1f}\,\text{{mm}}$
    - Effective flange width (derived): $b_{{ef}} = {beff_display:.1f}\,\text{{mm}}$
    - Effective depth (derived): $d = {d_display:.1f}\,\text{{mm}}$
    - Tension steel area (derived): $A_{{st}} = {Ast_display:.1f}\,\text{{mm}}^2$
    
    Derived section parameters:
    
    - Width ratio:
      $$
      \beta = \dfrac{{b_{{ef}}}}{{b_w}} = \dfrac{{{beff_display:.1f}}}{{{bw_display:.1f}}} = {beta_display:.3f}
      $$
    - Reinforcement ratio:
      $$
      p = \dfrac{{A_{{st}}}}{{b_{{ef}} d}} = \dfrac{{{Ast_display:.1f}}}{{{beff_display:.1f}\times {d_display:.1f}}} = {p_display:.5f}
      $$
    - Limit ratio:
      $$
      p_{{lim}} = 0.001 \dfrac{{(f'_c)^{{1/3}}}}{{\beta^{{2/3}}}}
      = 0.001 \dfrac{{({fc_display:.1f})^{{1/3}}}}{{({beta_display:.3f})^{{2/3}}}}
      = {p_lim_display:.5f}
      $$
    
    ---
    
    **Formula:**
    
    For reinforced members (AS 3600:2018 Cl. 8.5.3.1):
    
    If $p \ge p_{{lim}}$:
    
    $$
    I_{{ef}} = \left[(5 - 0.04 f'_c)\, p + 0.002 \right]\, b_{{ef}} d^3
    $$
    
    If $p < p_{{lim}}$:
    
    $$
    I_{{ef}} = \left[0.055 (f'_c)^{{1/3}} / \beta^{{2/3}} - 50 p \right]\, b_{{ef}} d^3
    $$
    
    Capped by:
    
    $$
    I_{{ef}} \le I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4
    $$
    
    and
    
    $$
    k_1 = \dfrac{{I_{{ef}}}}{{b_{{ef}} d^3}}
    $$
    
    ---
    
    **Substitution:**
    
    Using the current inputs:
    
    - Branch used: {ief_branch_label}
    - Coefficient:
      $$
      k_1 = {k1_expr_md} = {k1_expr:.5f}
      $$
    - Effective stiffness:
      $$
      I_{{ef}} = k_1\, b_{{ef}} d^3 = {k1_expr:.5f}\times {beff_display:.1f}\times ({d_display:.1f})^3
      \approx {Ief_selected_display:,.3e}\,\text{{mm}}^4
      $$
    - Cap check:
      $$
      I_{{ef}} \le I_{{ef,max}} = {Ief_max_display:,.3e}\,\text{{mm}}^4
      $$
    
    ---
    
    **Result:**
    
    - $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$
    - $k_1 = {k1_from_ief:.5f}$
    - (cap) $I_{{ef,max}} = {Ief_max:,.3e}\,\text{{mm}}^4$
    
    _Ref: AS 3600:2018 Cl. 8.5.3.1(2) & (3) – simplified $I_{{ef}}$ for reinforced members._
    """
    
    render_deflection_check(
        DeflectionCheckPresentation(
            step_id="defl_ief",
            title="Effective stiffness ($I_{ef}$) – input choice",
            summary_md=ief_summary,
            status_kind=None,
            calc_md=ief_calc_md,
        )
    )
    
    # Short-term deflection step
    short_limit_check = deflection_limit_check_values(
        delta_short_total,
        L_mm,
        defl_limit_ratio,
    )
    limit_delta_mm = short_limit_check["limit_delta_mm"]
    util_short = short_limit_check["utilisation"]
    short_status = short_limit_check["status"]
    
    _short_res = short_limit_check["result_text"]
    short_summary = (
        f"**Check 2 — Short-term deflection**  \n"
        f"$\\delta_{{st,total}} = {delta_short_total:.2f}\\,\\mathrm{{mm}}$ "
        f"({L_over_delta_short}) | Result: {_short_res}"
    )
    
    # Determine source label for display
    source_label = "Teaching SFD/BMD page" if is_design_driven else "Manual design actions"
    w_from_M = derived.get("w_from_M") if isinstance(derived, dict) else None
    w_from_V = derived.get("w_from_V") if isinstance(derived, dict) else None
    if w_source == "actions" and derived.get("w_kN_per_m") is not None:
        wM_str = f"{w_from_M:.2f}" if w_from_M is not None else "—"
        wV_str = f"{w_from_V:.2f}" if w_from_V is not None else "—"
        load_line = (
            f"- Total service load: $w = {w_total:.2f}\\,\\text{{kN/m}}$ "
            f"(from actions; $w_M={wM_str}$, $w_V={wV_str}$)"
        )
    else:
        load_line = (
            f"- Total service load: $w = g + q = {w_total:.2f}\\,\\text{{kN/m}}$"
        )
    
    short_calc_md = rf"""
    *Purpose: Determine the short-term midspan deflection under total service load $w$ using the effective stiffness $I_{{ef}}$ from the Iₑf step (AS 3600 Cl. 8.5.3.1).*
    
    **Inputs:**
    
    - Actions source: {source_label}
    - Effective span (derived):
      $$
      L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm / 1000.0:.3f}\,\text{{m}} = {L_mm:.0f}\,\text{{mm}}
      $$
    {load_line}
    - Support condition: {support_type}
    - Deflection coefficient (support condition):  
      $k_2 = {k2:.5f}$  
      *(Code-defined coefficient based on support condition per AS 3600 Cl. 8.5.3.1)*
    - Concrete modulus (derived): $E_c = 4700\sqrt{{f'_c}} = {Ec_short:.0f}\,\text{{MPa}}$
    - Effective modulus (derived): $E_{{c,eff}} = \dfrac{{E_c}}{{1+\varphi_{{cc}}(t)}} = {Ec:.0f}\,\text{{MPa}}$
    - Effective second moment: $I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$
    
    ---
    
    **Formula:**
    
    Short-term deflection due to total service load:
    
    $$
    \delta_{{st,total}} = k_2 \dfrac{{w\, L_{{eff}}^4}}{{E_{{c,eff}}\, I_{{ef}}}}
    $$
    
    where $k_2$ is the deflection coefficient determined by support condition (AS 3600 Cl. 8.5.3.1).
    
    ---
    
    **Substitution:**
    
    $$
    \delta_{{st,total}}
    = ({k2:.5f}) \times ({w_total:.2f})\,
      \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
    \approx {delta_short_total:.2f}\,\text{{mm}}
    $$
    
    ---
    
    **Result:**
    
    - Short-term deflection (total load):  
      $\delta_{{st,total}} \approx {delta_short_total:.2f}\,\text{{mm}}$
    - Deflection ratio:  
      $L/\delta_{{st,total}} \approx {L_over_delta_short}$
    {f'- Utilisation: {util_short:.2f} → {"✓ PASS" if short_status == "pass" else "✗ FAIL"}' if util_short is not None else ''}
    
    _Ref: AS 3600:2018 Cl. 8.5.3.1 – deflection using effective stiffness $I_{{ef}}$._
    """
    render_deflection_check(
        DeflectionCheckPresentation(
            step_id="defl_short",
            title="Short-term deflection",
            summary_md=short_summary,
            status_kind=short_status,
            calc_md=short_calc_md,
        )
    )
    
    long_add_limit_check = deflection_limit_check_values(
        delta_long_add,
        L_mm,
        defl_limit_ratio,
    )
    total_limit_check = deflection_limit_check_values(
        delta_total,
        L_mm,
        defl_limit_ratio,
    )
    limit_delta_mm = total_limit_check["limit_delta_mm"]
    util_long = long_add_limit_check["utilisation"]
    util_total = total_limit_check["utilisation"]
    long_status = total_limit_check["status"]
    
    limit_delta_mm_display = total_limit_check["limit_delta_mm_display"]
    util_total_display = total_limit_check["utilisation_display"]
    
    ratio_Asc_Ast = compression_to_tension_steel_ratio(Asc, Ast)
    
    _long_res = total_limit_check["result_text"]
    long_summary = (
        f"**Check 3 — Long-term deflection**  \n"
        f"$\\delta_{{total}} = {delta_total:.2f}\\,\\mathrm{{mm}}$ "
        f"({L_over_delta_total}) | Includes: Long-term deflection with "
        f"$k_{{cs}}$; Result: {_long_res}"
    )
    
    source_label = "Teaching SFD/BMD page" if is_design_driven else "Manual design actions"
    
    long_calc_md = rf"""
    *Purpose: Determine the additional long-term deflection due to sustained loading (creep + shrinkage) and the resulting total deflection to AS 3600 Cl. 8.5.3.2.*
    
    **Inputs:**
    
    - Actions source: {source_label}
    - Effective span (derived):
      $$
      L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm / 1000.0:.3f}\,\text{{m}} = {L_mm:.0f}\,\text{{mm}}
      $$
    - Support condition: {support_type}
    - Sustained load:
      $$
      w_{{sust}} = g + \psi_s q = {g_used:.2f} + {psi_s:.2f}\times {q_used:.2f} = {w_sust:.2f}\,\text{{kN/m}}
      $$
    - Sustained factor: $\psi_s = {psi_s:.2f}$
    - Tension steel: $A_{{st}} = {Ast:.0f}\,\text{{mm}}^2$
    - Compression steel: $A_{{sc}} = {Asc:.0f}\,\text{{mm}}^2$
    - Steel ratio:
      $$
      \dfrac{{A_{{sc}}}}{{A_{{st}}}} = \dfrac{{{Asc:.0f}}}{{{Ast:.0f}}} = {ratio_Asc_Ast:.3f}
      $$
    - Creep/shrinkage multiplier:
      $$
      k_{{cs}} = \max\left[ 2 - 1.2 \left(\dfrac{{A_{{sc}}}}{{A_{{st}}}}\right),\, 0.8 \right]
      = \max\left[ 2 - 1.2 \times {ratio_Asc_Ast:.3f},\, 0.8 \right] = {kcs:.2f}
      $$
    - Sustained concrete stress path (from creep workflow):
      $$
      \sigma_{{cs}} = \dfrac{{M_{{sust}}\times10^6}}{{Z_{{comp}}}}
      = \dfrac{{{sustained_mstar:.2f}\times10^6}}{{{sustained_z_comp:.2e}}}
      \approx {sustained_sigma_cs:.2f}\,\text{{MPa}}
      $$
      $$
      \text{{stress\_ratio}} = \dfrac{{\sigma_{{cs}}}}{{f'_c}}
      = \dfrac{{{sustained_sigma_cs:.2f}}}{{{fc:.1f}}}
      = {stress_ratio:.3f}
      $$
    - Effective modulus path used in deflection:
      $$
      E_{{c,eff}} = \dfrac{{E_c}}{{1+\phi_{{cc}}(t)}}
      = \dfrac{{{Ec_short:.0f}}}{{1+{phi_cc_t:.2f}}}
      = {Ec:.0f}\,\text{{MPa}}
      $$
    - Other parameters as per short-term:
      $k_2 = {k2:.5f},\ L_{{eff}} = {L_mm:.0f}\,\text{{mm}},\
       I_{{ef}} = {Ief_selected:,.3e}\,\text{{mm}}^4$
    
    ---
    
    **Formula:**
    
    Short-term deflection due to **sustained load only**:
    
    $$
    \delta_{{st,sust}} = k_2 \dfrac{{w_{{sust}} L_{{eff}}^4}}{{E_{{c,eff}} I_{{ef}}}}
    $$
    
    Creep/shrinkage multiplier:
    
    $$
    k_{{cs}} = \max\left[ 2 - 1.2 \left(\dfrac{{A_{{sc}}}}{{A_{{st}}}}\right),\, 0.8 \right]
    $$
    
    Additional long-term deflection:
    
    $$
    \delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
    $$
    
    Total deflection:
    
    $$
    \delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
    $$
    
    Adopted limit ratio: **{defl_limit_label}**
    
    Deflection limit:
    
    $$
    \delta_{{limit}} = \dfrac{{L_{{eff}}}}{{(L/\Delta)}} = \dfrac{{{L_mm:.0f}}}{{{defl_limit_ratio:.0f}}}
    $$
    
    ---
    
    **Substitution:**
    
    Short-term sustained:
    
    $$
    \delta_{{st,sust}}
    = ({k2:.5f}) \times ({w_sust:.2f})\,
      \dfrac{{({L_mm:.0f})^4}}{{({Ec:.0f}) \times ({Ief_selected:,.3e})}}
    \approx {delta_short_sust:.2f}\,\text{{mm}}
    $$
    
    Additional long-term:
    
    $$
    \delta_{{LT,add}} = k_{{cs}} \,\delta_{{st,sust}}
    = ({kcs:.2f}) \times ({delta_short_sust:.2f})
    \approx {delta_long_add:.2f}\,\text{{mm}}
    $$
    
    Total:
    
    $$
    \delta_{{total}} = \delta_{{st,total}} + \delta_{{LT,add}}
    = {delta_short_total:.2f} + {delta_long_add:.2f}
    \approx {delta_total:.2f}\,\text{{mm}}
    $$
    
    Adopted limit ratio: **{defl_limit_label}**
    
    Deflection limit and utilisation:
    
    $$
    \delta_{{limit}} = \dfrac{{L_{{eff}}}}{{(L/\Delta)}} = \dfrac{{{L_mm:.0f}}}{{{defl_limit_ratio:.0f}}}
     = {limit_delta_mm_display:.2f}\,\text{{mm}}
    $$
    
    $$
    \text{{Utilisation}} = \dfrac{{\delta_{{total}}}}{{\delta_{{limit}}}}
     = \dfrac{{{delta_total:.2f}}}{{{limit_delta_mm_display:.2f}}} = {util_total_display:.2f}
    $$
    
    ---
    
    **Result:**
    
    - Short-term sustained:  
      $\delta_{{st,sust}} \approx {delta_short_sust:.2f}\,\text{{mm}}$
    - Additional long-term:  
      $\delta_{{LT,add}} \approx {delta_long_add:.2f}\,\text{{mm}}$  
      (ratio $\approx {L_over_delta_long_add}$)
    - Total deflection:  
      $\delta_{{total}} \approx {delta_total:.2f}\,\text{{mm}}$  
      (ratio $\approx {L_over_delta_total}$)
    {f'- Utilisation: {util_total:.2f} → {"✓ PASS" if long_status == "pass" else "✗ FAIL"}' if util_total is not None else ''}
    
    _Ref: AS 3600:2018 Cl. 8.5.3.2 – long-term deflection using $k_{{cs}}$ and sustained loads._
    """
    
    render_deflection_check(
        DeflectionCheckPresentation(
            step_id="defl_long",
            title="Long-term deflection",
            summary_md=long_summary,
            status_kind=long_status,
            calc_md=long_calc_md,
        )
    )
    
    L_m = L_m_for_fd
    if L_m is None or L_m <= 0:
        L_m = float(get_param("span_L_m", 0.0) or 0.0)
    
    support_type_display = support_type
    
    value_source = value_source_text
    fd_ef_meta_used = fd_ef_meta or {}
    
    # Determine loading condition description
    if fd_ef_source_branch in ("manual_actions", "design_actions"):
        if support_type == "Simply supported":
            loading_condition = "Simply supported, UDL over full span"
        elif support_type == "Cantilever":
            loading_condition = "Cantilever, UDL over full span"
        else:
            loading_condition = f"{support_type}, UDL over full span"
    else:
        loading_condition = "Fallback value"
    
    # Build summary
    fd_ef_summary = (
        f"**Check 4 — Effective design load F_d,ef**  \n"
        f"$F_{{d,ef}} = {fd_ef_used:.2f}\\,\\mathrm{{kN/m}}$ | "
        f"Source: {value_source}"
    )
    
    if (
        fd_ef_source_branch in ("manual_actions", "design_actions")
        and fd_ef_meta_used.get("V_kN", 0.0) > 0
        and L_m > 0
    ):
        V_kN = fd_ef_meta_used.get("V_kN", 0.0)
        if support_type == "Simply supported":
            equation_latex = r"V_{\max} = \frac{wL}{2} \quad \Rightarrow \quad w = \frac{2V_{\max}}{L}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{2 \times {V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )
        elif support_type == "Cantilever":
            equation_latex = r"V_{\max} = wL \quad \Rightarrow \quad w = \frac{V_{\max}}{L}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{{V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )
        else:
            equation_latex = r"w = \frac{V_{\max}}{L} \quad \text{(approximate)}"
            substitution_latex = (
                rf"F_{{d,ef}} = \frac{{{V_kN:.1f}}}{{{L_m:.2f}}} = "
                rf"{fd_ef_used:.2f}\,\text{{kN/m}}"
            )
    
        source_label = (
            "Manual inputs"
            if fd_ef_source_branch == "manual_actions"
            else "Teaching SFD/BMD"
        )
    
        fd_ef_calc_md = rf"""
    *Purpose: Determine the equivalent uniform distributed load $F_{{d,ef}}$ used for span-to-depth ratio checks per AS 3600 Cl. 8.5.4. This value is reverse-engineered from the design shear force $V^*$ and span length $L$ based on the support condition and loading pattern.*
    
    **Step 1 – Inputs:**
    
    - Source: {source_label}
    - Design shear: $V^* = {V_kN:.1f}\,\text{{kN}}$
    - Effective span: $L = {L_m:.2f}\,\text{{m}}$
    - Support condition: {support_type_display}
    - Loading condition: {loading_condition}
    
    ---
    
    **Step 2 – Model / equations:**
    
    For {loading_condition}:
    
    $$
    {equation_latex}
    $$
    
    ---
    
    **Step 3 – Substitution:**
    
    $$
    {substitution_latex}
    $$
    
    ---
    
    **Step 4 – Result:**
    
    - Effective design load:
      $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$
    
    *Note: This equivalent UDL is used for serviceability deflection checks and span-to-depth ratio calculations per AS 3600 Cl. 8.5.4.*
    
    _Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits.*
    """
    else:
        fd_ef_calc_md = rf"""
    *Purpose: The effective design load $F_{{d,ef}}$ is used for span-to-depth ratio checks per AS 3600 Cl. 8.5.4. This value represents an equivalent uniform distributed load used in serviceability calculations.*
    
    **Step 1 – Inputs:**
    
    - Effective design load: $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$
    - Effective span: $L = {L_m:.2f}\,\text{{m}}$
    - Support condition: {support_type_display}
    - Source: {value_source}
    
    ---
    
    **Step 2 – Model / equations:**
    
    Derivation inputs were unavailable; using the stored fallback value.
    
    ---
    
    **Step 3 – Substitution:**
    
    $$
    F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}
    $$
    
    ---
    
    **Step 4 – Result:**
    
    - Effective design load:
      $F_{{d,ef}} = {fd_ef_used:.2f}\,\text{{kN/m}}$
    
    *Note: This value is used for span-to-depth ratio calculations per AS 3600 Cl. 8.5.4.*
    
    _Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
    """
    
    render_deflection_check(
        DeflectionCheckPresentation(
            step_id="defl_effective_load",
            title="Effective design load F_d,ef",
            summary_md=fd_ef_summary,
            status_kind=None,
            calc_md=fd_ef_calc_md,
        )
    )
    
    span_depth_display = span_depth_display_values(L_over_d, L_over_d_limit)
    util_span = span_depth_display["util_span"]
    span_defl_status = span_depth_display["span_defl_status"]
    limit_text = span_depth_display["limit_text"]
    
    # Guard against None values before formatting
    L_mm_display = L_mm if L_mm is not None else 6000.0
    d_display_span = d if d is not None else 550.0
    L_over_d_display = L_over_d if L_over_d is not None else 0.0
    k1_span_display = k1_span if k1_span is not None else 0.0
    k2_span_display = k2_span if k2_span is not None else 0.013
    defl_limit_ratio_display = defl_limit_ratio if defl_limit_ratio is not None else 250.0
    Fdef_kNm_display = Fdef_kNm if Fdef_kNm is not None else 12.0
    Ec_display_span = Ec if Ec is not None else 10000.0
    beff_display_span = beff if beff is not None else 300.0
    value_source_text_display = (
        value_source_text or "See Effective design load section above."
    )
    
    _span_res = span_depth_display["result_text"]
    span_summary = (
        f"**Check 5 — Span/depth deemed-to-conform check**  \n"
        f"$L_{{ef}}/d = {L_over_d_display:.1f}$ vs limit = {limit_text} | "
        f"Result: {_span_res}"
    )
    
    span_calc_md = rf"""
    *Purpose: Check whether the span-to-depth ratio $L_{{ef}}/d$ satisfies the deemed-to-conform limit given in AS 3600:2018 Cl. 8.5.4, using the previously calculated $I_{{ef}}$ (via $k_1$).*
    
    **Inputs:**
    
    - Effective span (derived):
      $$
      L_{{eff}} = \dfrac{{L}}{{1000}} = {L_mm_display / 1000.0:.3f}\,\text{{m}} = {L_mm_display:.0f}\,\text{{mm}}
      $$
    - Effective depth (derived): $d = {d_display_span:.1f}\,\text{{mm}}$
      ⇒ current ratio:
      $$
      \dfrac{{L_{{ef}}}}{{d}} = {L_over_d_display:.1f}
      $$
    - Support condition: {support_type}
    - Stiffness factor from Iₑf step: $k_1 = {k1_span_display:.5f}$
    - Deflection constant (support type): $k_2 = {k2_span_display:.5f}$
    - Deflection limit (adopted: {defl_limit_label}):
      $$
      \left(\dfrac{{\Delta}}{{L_{{ef}}}}\right)_{{limit}} = \dfrac{{1}}{{{defl_limit_ratio_display:.0f}}}
      $$
    - Effective design load (derived for span/depth): $F_{{d,ef}} = {Fdef_kNm_display:.2f}\,\text{{kN/m}}$
      *{value_source_text_display}*
    - Concrete modulus (derived): $E_c = 4700\sqrt{{f'_c}} = {Ec_short:.0f}\,\text{{MPa}}$
    - Effective modulus (derived): $E_{{c,eff}} = \dfrac{{E_c}}{{1+\varphi_{{cc}}(t)}} = {Ec_display_span:.0f}\,\text{{MPa}}$
    - Effective flange width: $b_{{ef}} = {beff_display_span:.1f}\,\text{{mm}}$
    
    ---
    
    **Formula:**
    
    Deemed-to-conform span-to-depth limit:
    
    $$
    \frac{{L_{{ef}}}}{{d}} \le
    \left[
    \dfrac{{k_1 \, (\Delta/L_{{ef}}) \, b_{{ef}} E_{{c,eff}}}}{{k_2 F_{{d,ef}}}}
    \right]^{{1/3}}
    $$
    
    ---
    
    **Substitution:**
    """
    if L_over_d_limit is not None:
        span_calc_md += rf"""
    
    Right-hand-side limit:
    
    $$
    \left(\frac{{L_{{ef}}}}{{d}}\right)_{{limit}}
    =
    \left[
    \dfrac{{({k1_span_display:.5f}) \times (1/{defl_limit_ratio_display:.0f}) \times ({beff_display_span:.1f}) \times ({Ec_display_span:.0f})}}
      {{({k2_span_display:.5f}) \times ({Fdef_kNm_display:.2f})}}
    \right]^{{1/3}}
    \approx {L_over_d_limit:.1f}
    $$
    
    ---
    
    **Result:**
    
    - Allowed ratio:
      $$
      \dfrac{{L_{{ef}}}}{{d}} \le {L_over_d_limit:.1f}
      $$
    - Actual ratio:
      $$
      \dfrac{{L_{{ef}}}}{{d}} = {L_over_d:.1f}
      $$
    
    Conclusion: **{"✅ OK – deemed to conform" if span_defl_status == "pass" else "❌ NG – exceeds deemed limit"}**
    """
    else:
        span_calc_md += r"""
    
    No limit could be computed because $F_{d,ef} \le 0$.
    
    ---
    
    **Result:**
    
    - Span/depth deemed-to-conform check not applicable for the current inputs.
    """
    
    span_calc_md += r"""
    
    _Ref: AS 3600:2018 Cl. 8.5.4 – deemed-to-conform span-to-depth limits._
    """
    
    render_deflection_check(
        DeflectionCheckPresentation(
            step_id="defl_span_depth",
            title="Span/depth deemed-to-conform check",
            summary_md=span_summary,
            status_kind=span_defl_status,
            calc_md=span_calc_md,
        )
    )

__all__ = [
    "DeflectionCheckPresentation",
    "render_deflection_check",
    "render_deflection_checks",
]
