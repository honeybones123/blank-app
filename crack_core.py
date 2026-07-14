# crack_core.py
# Core compute function for crack control (no Streamlit UI)

import math
from state_and_helpers import get_param, update_results, resolve_design_actions
from calculations.crack_control import (
    compute_crack_control_values,
    table_sigma_max_A,
    table_sigma_max_B,
    calc_eps_diff,
    calc_sr_max,
)


def compute_crack_results(publish: bool = True) -> dict:
    """
    Compute crack control results using current session state values.
    Reads all inputs from get_param(), performs calculations, and updates results.
    No Streamlit UI - pure computation.
    """
    import streamlit as st
    
    # Read geometry
    b = get_param("b_crack", get_param("b", 300.0))
    D = get_param("D", 600.0)
    cover_bot = get_param("cover_bot", 40.0)
    db_bot = get_param("db_bot", 20.0)
    s_bar_bot = get_param("s_bar_bot", 200.0)
    Ast = get_param("Ast_bot", 0.0)
    
    # Read materials
    fc = get_param("fc", 32.0)
    Ec = get_param("Ec", 30000.0)
    Es = get_param("Es", 200000.0)
    fsy = get_param("fsy", 500.0)
    
    # Read crack control settings
    exposure_class = get_param("exposure_class", "B1")
    wmax_choice = get_param("wmax_char_limit", 0.3)
    member_type = get_param("crack_member_type", "Primarily flexure")
    
    # Read linked SLS values
    sigma_sr = get_param("sigma_sr", None)
    if sigma_sr is None:
        sigma_sr = get_param("bending_sls_fs_outer", 0.0)
    phi_ce = get_param("phi_cc_t", 2.0)
    eps_cs_micro = get_param("eps_cs_total_micro", 300.0)
    eps_cs = eps_cs_micro * 1e-6
    
    # k1 and k2 from widgets
    k1 = get_param("crack_k1", 0.8)
    k2 = get_param("crack_k2", get_param("crk_k2", 0.5))
    
    # Resolve active tension reinforcement from canonical geometry (T/I aware).
    sec_shape = str(get_param("sec_shape", "RECT") or "RECT")
    active_tension_warning = ""
    crack_tension_face = "bottom"
    crack_active_bar_count = 0
    crack_active_bar_dias = []
    crack_active_bar_spacing_mm = []
    crack_tension_width_mm = float(b)
    crack_Ast_active_mm2 = float(Ast)
    crack_flange_participation_used = False
    crack_web_participation_used = True
    actions = resolve_design_actions()
    sls_m_signed = float(actions.get("SLS_M_signed", actions.get("Mu_signed", 0.0)) or 0.0)
    moment_sign = "negative" if sls_m_signed < 0.0 else "positive"
    if sec_shape in ("T", "I"):
        try:
            from section_layout import compute_section_layout
            from section_props.reo_layout import (
                resolve_longitudinal_bars_from_layout,
                resolve_active_tension_reinforcement,
                resolve_crack_tension_width,
            )

            layout = compute_section_layout()
            shape_name = str(layout.get("shape_name", sec_shape))
            dims = dict(layout.get("dims", {}) or {})
            # Canonical reinforcement source of truth: recalc_derived_values publishes
            # resolved_longitudinal_bars; only fall back to local resolve if missing.
            bars = list(st.session_state.get("resolved_longitudinal_bars", []) or [])
            if not bars:
                reo_layout = dict(layout.get("reo_layout", {}) or {})
                bars = resolve_longitudinal_bars_from_layout(
                    shape_name=shape_name,
                    dims=dims,
                    reo_layout=reo_layout,
                )
            active = resolve_active_tension_reinforcement(
                dims,
                bars,
                moment_sign,
            )
            crack_width = resolve_crack_tension_width(
                sec_shape,
                dims,
                moment_sign,
                active.get("active_bars", []),
            )
            crack_tension_face = str(active.get("tension_face", "bottom"))
            crack_active_bar_count = int(len(active.get("active_bars", [])))
            crack_active_bar_dias = sorted({int(round(float(bar.get("dia_mm", 0.0)))) for bar in active.get("active_bars", []) if float(bar.get("dia_mm", 0.0) or 0.0) > 0.0})
            crack_active_bar_spacing_mm = list((active.get("bar_spacing_summary") or {}).get("values_mm", []))
            crack_tension_width_mm = float(crack_width.get("crack_tension_width_mm", b) or b)
            crack_Ast_active_mm2 = float(active.get("Ast_active_mm2", 0.0) or 0.0)
            crack_flange_participation_used = bool(crack_width.get("crack_flange_participation_used", False))
            crack_web_participation_used = bool(crack_width.get("crack_web_participation_used", False))
            if (
                sec_shape in ("T", "I")
                and crack_tension_face == "top"
                and float(dims.get("bf", 0.0) or 0.0) > 1.6 * max(float(dims.get("bw", dims.get("tw", 0.0)) or 0.0), 1.0)
                and not crack_flange_participation_used
            ):
                active_tension_warning = (
                    "Top tension reinforcement is concentrated in the web. For wide flanges under hogging, "
                    "distributed flange bars may be required for realistic crack control and detailing."
                )
            Ast = crack_Ast_active_mm2
            b = crack_tension_width_mm if crack_tension_width_mm > 0 else b
            if active.get("active_bars"):
                if crack_tension_face == "bottom":
                    c = min(max(0.0, D - (float(bar["y_mm"]) + float(bar["dia_mm"]) / 2.0)) for bar in active["active_bars"])
                else:
                    c = min(max(0.0, float(bar["y_mm"]) - float(bar["dia_mm"]) / 2.0) for bar in active["active_bars"])
                db = max(float(bar["dia_mm"]) for bar in active["active_bars"])
                if crack_active_bar_spacing_mm:
                    s_bar_bot = sum(crack_active_bar_spacing_mm) / len(crack_active_bar_spacing_mm)
                else:
                    s_bar_bot = max(float(b), 1.0)
        except Exception:
            pass

    # Effective area in tension
    c = max(float(cover_bot if crack_tension_face == "bottom" else get_param("cover_top", cover_bot)), 1.0) if sec_shape == "RECT" else max(float(locals().get("c", cover_bot)), 1.0)
    db = float(locals().get("db", db_bot) or db_bot)
    spacing = s_bar_bot
    crack_values = compute_crack_control_values(
        b=b,
        D=D,
        c=c,
        db=db,
        spacing=spacing,
        Ast=Ast,
        fc=fc,
        Ec=Ec,
        Es=Es,
        fsy=fsy,
        wmax_choice=wmax_choice,
        member_type=member_type,
        sigma_sr=sigma_sr,
        phi_ce=phi_ce,
        eps_cs=eps_cs,
        k1=k1,
        k2=k2,
        crack_tension_face=crack_tension_face,
    )
    Aceff = crack_values["Aceff"]
    rho_eff = crack_values["rho_eff"]
    fct_eff = crack_values["fct_eff"]
    ne = crack_values["ne"]
    sigma_table_A = crack_values["sigma_table_A"]
    sigma_table_B = crack_values["sigma_table_B"]
    sigma_table_combined = crack_values["sigma_table_combined"]
    sigma_08fsy = crack_values["sigma_08fsy"]
    sigma_allow_table = crack_values["sigma_allow_table"]
    utilisation_table = crack_values["utilisation_table"]
    passes_table = crack_values["passes_table"]
    eps_diff = crack_values["eps_diff"]
    sr_max = crack_values["sr_max"]
    w_calc = crack_values["w_calc"]
    utilisation_w = crack_values["utilisation_w"]
    passes_w = crack_values["passes_w"]
    
    out = {
        "sigma_sr": sigma_sr,
        "sigma_allow_table": sigma_allow_table,
        "w_calc": w_calc,
        "wmax_char": wmax_choice,
        "passes_table": passes_table,
        "passes_w": passes_w,
        "crack_width": w_calc,
        "crack_sr_max_mm": float(sr_max),
        "crack_utilisation": utilisation_w,
        "crack_tension_face": crack_tension_face,
        "crack_active_bar_count": float(crack_active_bar_count),
        "crack_active_bar_dias": crack_active_bar_dias,
        "crack_active_bar_spacing_mm": crack_active_bar_spacing_mm,
        "crack_tension_width_mm": float(crack_tension_width_mm),
        "crack_Ast_active_mm2": float(crack_Ast_active_mm2),
        "crack_flange_participation_used": bool(crack_flange_participation_used),
        "crack_web_participation_used": bool(crack_web_participation_used),
        "crack_detailing_warning": active_tension_warning,
        "active_tension_face": crack_tension_face,
        "active_tension_Ast_mm2": float(crack_Ast_active_mm2),
        "active_tension_width_mm": float(crack_tension_width_mm),
        "active_tension_flange_participating": bool(crack_flange_participation_used),
        "active_tension_warning": active_tension_warning,
    }
    
    # Build report if publishing
    if publish:
        params = {
            "b": b, "D": D, "c": c, "db": db, "spacing": spacing, "Ast": Ast,
            "fc": fc, "Ec": Ec, "Es": Es, "fsy": fsy,
            "wmax_choice": wmax_choice, "member_type": member_type,
            "sigma_sr": sigma_sr, "phi_ce": phi_ce, "eps_cs": eps_cs,
            "k1": k1, "k2": k2,
            "Aceff": Aceff, "rho_eff": rho_eff, "fct_eff": fct_eff, "ne": ne,
            "sigma_table_A": sigma_table_A, "sigma_table_B": sigma_table_B,
            "sigma_table_combined": sigma_table_combined, "sigma_08fsy": sigma_08fsy,
            "sigma_allow_table": sigma_allow_table, "utilisation_table": utilisation_table,
            "passes_table": passes_table,
            "eps_diff": eps_diff, "sr_max": sr_max, "w_calc": w_calc,
            "utilisation_w": utilisation_w, "passes_w": passes_w,
        }
        try:
            report = build_crack_report(params)
            if "results" not in st.session_state:
                st.session_state["results"] = {}
            st.session_state["results"]["crack_report"] = report
        except Exception as e:
            if "results" not in st.session_state:
                st.session_state["results"] = {}
            st.session_state["results"]["crack_report_error"] = str(e)
    
    update_results(**out)
    return out


def build_crack_report(params: dict) -> dict:
    """
    Build the crack control report structure (tabs + calc boxes) from computed values.
    
    Args:
        params: Dict with all computed crack control values
    
    Returns:
        dict with module_title, summary, and tabs structure
    """
    from reporting.report_content import make_calc_box, make_tab
    import math
    
    # Extract parameters
    wmax_choice = params.get("wmax_choice", 0.3)
    sigma_sr = params.get("sigma_sr", 200.0)
    sigma_allow_table = params.get("sigma_allow_table", 0.0)
    utilisation_table = params.get("utilisation_table", 0.0)
    passes_table = params.get("passes_table", False)
    w_calc = params.get("w_calc", 0.0)
    utilisation_w = params.get("utilisation_w", 0.0)
    passes_w = params.get("passes_w", False)
    
    # Extract calculation details
    Aceff = params.get("Aceff", 0.0)
    rho_eff = params.get("rho_eff", 0.0)
    Ast = params.get("Ast", 0.0)
    fct_eff = params.get("fct_eff", 0.0)
    ne = params.get("ne", 0.0)
    eps_diff = params.get("eps_diff", 0.0)
    sr_max = params.get("sr_max", 0.0)
    c = params.get("c", 40.0)
    db = params.get("db", 20.0)
    k1 = params.get("k1", 0.8)
    k2 = params.get("k2", 0.5)
    Es = params.get("Es", 200000.0)
    Ec = params.get("Ec", 30000.0)
    phi_ce = params.get("phi_ce", 2.0)
    Eceff = (Ec / (1.0 + phi_ce)) if (Ec and (1.0 + phi_ce) > 0.0) else 0.0
    eps_cs_micro = params.get("eps_cs", 0.0) * 1e6
    sigma_table_A = params.get("sigma_table_A", 0.0)
    sigma_table_B = params.get("sigma_table_B", 0.0)
    sigma_table_combined = params.get("sigma_table_combined", 0.0)
    sigma_08fsy = params.get("sigma_08fsy", 0.0)
    member_type = params.get("member_type", "Primarily flexure")
    
    # Build summary
    overall_pass = passes_table and passes_w
    outcome = "PASS" if overall_pass else "FAIL"
    summary = [
        ("Demand (w)", f"{w_calc:.3f} mm"),
        ("Capacity (w_max)", f"{wmax_choice:.3f} mm"),
        ("Utilisation", f"{max(utilisation_table, utilisation_w):.2f}"),
        ("Outcome", outcome),
    ]
    
    # SLS tab calculations
    sls_boxes = []
    
    # Check 1: Inputs & limits
    sls_boxes.append(make_calc_box(
        "3.1",
        "Inputs & crack limits",
        "info",
        f"w'_max = {wmax_choice:.3f} mm, {member_type}",
        "",
        [
            {"label": "Crack width limit", "eq": "w'_max", "sub": f"= {wmax_choice:.3f} mm"},
            {"label": "Member type", "eq": "Resultant action", "sub": f"= {member_type}"},
        ],
    ))
    
    # Check 2: Table method
    sls_boxes.append(make_calc_box(
        "3.2",
        "Table method — max steel stress σ_sr",
        "pass" if passes_table else "fail",
        f"σ_sr = {sigma_sr:.1f} MPa vs {sigma_allow_table:.1f} MPa",
        "",
        [
            {"label": "Table 8.6.2.2(A)", "eq": "σ_max,A = f(d_b, w'_max)", "sub": f"= {sigma_table_A:.1f} MPa"},
            {"label": "Table 8.6.2.2(B)", "eq": "σ_max,B = f(s, w'_max)", "sub": f"= {sigma_table_B:.1f} MPa"},
            {"label": "Combined table limit", "eq": "σ_table = max(σ_max,A, σ_max,B)", "sub": f"= {sigma_table_combined:.1f} MPa"},
            {"label": "0.8*f_sy limit", "eq": "0.8*f_sy", "sub": f"= {sigma_08fsy:.1f} MPa"},
            {"label": "Allowable stress", "eq": "σ_allow = min(σ_table, 0.8*f_sy)", "sub": f"= {sigma_allow_table:.1f} MPa"},
            {"label": "Utilisation", "eq": "σ_sr / σ_allow", "sub": f"= {sigma_sr:.1f} / {sigma_allow_table:.1f} = {utilisation_table:.2f}"},
        ],
    ))
    
    # Check 3: Direct crack width calculation
    # Sub-step 3.1: Effective reinforcement ratio
    sls_boxes.append(make_calc_box(
        "3.3",
        "Effective reinforcement ratio ρ_eff",
        "info",
        f"ρ_eff = {rho_eff:.4f}",
        "",
        [
            {"label": "Effective area", "eq": "A_c,eff = b*h_eff", "sub": f"= {Aceff:.0f} mm^2"},
            {"label": "Reinforcement ratio", "eq": "ρ_eff = A_s,t / A_c,eff", "sub": f"= {Ast:.0f} / {Aceff:.0f} = {rho_eff:.4f}"},
        ],
    ))
    
    # Sub-step 3.2: Difference in mean strain
    sls_boxes.append(make_calc_box(
        "3.4",
        "Difference in mean strain ε_sm - ε_cm",
        "info",
        f"ε_sm - ε_cm = {eps_diff:.3e}",
        "",
        [
            {"label": "Effective tensile strength", "eq": "f_ct,eff = 0.6*sqrt(f'c)", "sub": f"= {fct_eff:.2f} MPa"},
            {"label": "Concrete modulus (derived)", "eq": "E_c = 4700*sqrt(f'_c)", "sub": f"= 4700*sqrt({fc:.1f}) = {Ec:.0f} MPa"},
            {"label": "Effective modulus (derived)", "eq": "E_c,eff = E_c/(1+φ_ce)", "sub": f"= {Ec:.0f}/(1+{phi_ce:.2f}) = {Eceff:.0f} MPa"},
            {"label": "Modular ratio", "eq": "n_e = (1 + φ_ce)*E_s/E_c", "sub": f"= (1 + {phi_ce:.2f})*{Es:.0f}/{Ec:.0f} = {ne:.2f}"},
            {"label": "Strain difference", "eq": "ε_sm - ε_cm = σ_sr/E_s - 0.6*f_ct,eff/(E_s*ρ_eff)*(1+n_e*ρ_eff) + ε_cs", "sub": f"= {eps_diff:.3e}"},
        ],
    ))
    
    # Sub-step 3.3: Maximum crack spacing
    sls_boxes.append(make_calc_box(
        "3.5",
        "Maximum crack spacing s_r,max",
        "info",
        f"s_r,max = {sr_max:.1f} mm",
        "",
        [
            {"label": "Crack spacing", "eq": "s_r,max = 3.4*c + 0.3*k_1*k_2*d_b/ρ_eff", "sub": f"= 3.4*{c:.1f} + 0.3*{k1:.2f}*{k2:.2f}*{db:.1f}/{rho_eff:.4f} = {sr_max:.1f} mm"},
        ],
    ))
    
    # Sub-step 3.4: Crack width
    sls_boxes.append(make_calc_box(
        "3.6",
        "Direct crack width w",
        "pass" if passes_w else "fail",
        f"w = {w_calc:.3f} mm",
        "",
        [
            {"label": "Crack width", "eq": "w = s_r,max*(ε_sm - ε_cm)", "sub": f"= {sr_max:.1f}*{eps_diff:.3e} = {w_calc:.3f} mm"},
            {"label": "Check", "eq": "w <= w'_max", "sub": f"{w_calc:.3f} <= {wmax_choice:.3f} = {passes_w}"},
            {"label": "Utilisation", "eq": "w / w'_max", "sub": f"= {w_calc:.3f} / {wmax_choice:.3f} = {utilisation_w:.2f}"},
        ],
    ))
    
    # Create SLS tab
    sls_tab = make_tab("SLS Checks", sls_boxes)
    return {
        "module_title": "Crack Control (SLS)",
        "summary": summary,
        "tabs": [sls_tab],
    }


# Backward compatibility alias
_compute_crack_results = compute_crack_results











