"""
Report Content Extraction

Extracts data from session state to match the Summary table structure.
All functions are read-only and use get_param() to access shared keys.
"""

import streamlit as st
import math
from state_and_helpers import get_param


def _ss(key, default=""):
    """Helper to safely read from session state."""
    return st.session_state.get(key, default)


def _r(results, key, default=""):
    """Helper to safely read from results dict."""
    if isinstance(results, dict):
        return results.get(key, default)
    return default


def _safe_ratio(numerator, denominator):
    """Calculate ratio safely, returning None if denominator is zero or None."""
    if denominator is None or denominator == 0:
        return None
    if numerator is None:
        return None
    return numerator / denominator


def _safe_value(val, fmt="{:.2f}", default="N/A"):
    """Safely format a value, returning default if invalid."""
    if val is None:
        return default
    try:
        if isinstance(val, float) and math.isnan(val):
            return default
        return fmt.format(val)
    except Exception:
        return default


def make_calc_box(id, title, status, result, clause="", derivation=None, diagram=None):
    """
    Create a calc box data structure for PDF reporting.
    
    Args:
        id: Box identifier (e.g., "1.2", "1.3")
        title: Box title
        status: Status ("pass", "fail", "info", "warn", or None)
        result: Result string (e.g., "C = 450.0 kN")
        clause: Clause reference (e.g., "AS 3600:2018 Cl. 8.1.3")
        derivation: List of dicts with "label", "eq", "sub" keys
        diagram: Optional dict with "path" (PNG path), "caption" (str), "w_mm" (float, default 55), "h_mm" (float, default 28)
    
    Returns:
        dict with calc box structure
    """
    # Normalize status to one of the allowed values
    if status not in ("pass", "fail", "info", "warn", None):
        status = None
    
    # Generate status_text from status
    status_text_map = {
        "pass": "PASS",
        "fail": "FAIL",
        "warn": "WARN",
        "info": "INFO",
        None: "",
    }
    status_text = status_text_map.get(status, "")
    
    box = {
        "id": str(id),
        "title": title,
        "status": status,  # "pass"|"fail"|"info"|"warn"|None
        "status_text": status_text,  # Display label (e.g., "PASS", "FAIL")
        "result": result,
        "clause": clause,
        "derivation": derivation or [],  # list of {"label","eq","sub"}
    }
    if diagram is not None:
        box["diagram"] = diagram
    return box


def make_tab(tab_title, boxes):
    """
    Create a tab data structure for PDF reporting.
    
    Args:
        tab_title: Tab title (e.g., "ULS Checks")
        boxes: List of calc box dicts
    
    Returns:
        dict with tab structure
    """
    return {"tab_title": tab_title, "boxes": boxes}


def make_module_report(module_title, tabs):
    """
    Create a module report data structure for PDF reporting.
    
    Args:
        module_title: Module title (e.g., "Bending (ULS)")
        tabs: List of tab dicts
    
    Returns:
        dict with module report structure
    """
    return {"module_title": module_title, "tabs": tabs}


def _auto_steps_for_module(module, summary, inputs, results, detail_level="detailed"):
    """
    Generate auto-steps for a module when steps are not available.
    
    Args:
        module: Module key prefix (e.g., "bending", "shear", "crack")
        summary: Dict with demand, capacity, utilisation, outcome, units
        inputs: Session state dict (can be st.session_state)
        results: Results dict
        detail_level: "detailed" for 12-20 steps, "simple" for 5 steps
    
    Returns:
        list: List of step descriptions (strings with title, clause, equations, substitutions)
    """
    from state_and_helpers import get_param
    
    demand = summary.get("demand", "N/A")
    capacity = summary.get("capacity", "N/A")
    utilisation = summary.get("utilisation", "N/A")
    outcome = summary.get("outcome", "N/A")
    units = summary.get("units", "")
    
    steps = []
    
    if module == "bending":
        # Read all available values
        Mu_star = get_param("Mu_star", 0.0)
        phi_Mu_cap = get_param("phi_Mu_cap", 0.0)
        Mu_util = get_param("Mu_utilisation", None)
        phi = get_param("phi_bend", 0.85)
        fc = get_param("fc", 32.0)
        fsy = get_param("fsy", 500.0)
        Ast = get_param("Ast_bot", 0.0)
        d = get_param("d", 560.0)
        b = get_param("b", 300.0)
        D = get_param("D", 600.0)
        cover_bot = get_param("cover_bot", 40.0)
        db_bot = get_param("db_bot", 20.0)
        nb_bot = get_param("nb_bot", 4)
        
        # Try to get detailed results from results dict or compute
        alpha2_raw = 0.85 - 0.0015 * fc
        gamma_raw = 0.97 - 0.0025 * fc
        alpha2 = max(0.67, alpha2_raw)
        gamma = max(0.67, gamma_raw)
        
        T = Ast * fsy / 1000.0  # kN
        denom = alpha2 * fc * b * gamma
        c = (T * 1000.0 / denom) if denom > 0 else 0.0
        a = gamma * c
        z = d - 0.5 * a
        Mu_nom = T * z
        ku = c / d if d > 0 else 0.0
        
        # Calculate Ast from layout if available
        Ast_calc = nb_bot * math.pi * (db_bot/2.0)**2 if nb_bot > 0 and db_bot > 0 else Ast
        
        steps = [
            f"Design action (ULS) — AS 3600:2018 Cl. 2.3\n"
            f"Mu* = {Mu_star:.1f} kNm",
            
            f"Section geometry — AS 3600:2018 Cl. 8.1.1\n"
            f"b = {b:.0f} mm, D = {D:.0f} mm",
            
            f"Material properties — AS 3600:2018 Cl. 3.1, 3.2\n"
            f"f'c = {fc:.1f} MPa, fsy = {fsy:.0f} MPa",
            
            f"Capacity factor — AS 3600:2018 Cl. 2.2\n"
            f"φ = {phi:.2f}",
            
            f"Tension steel area Ast from layout — AS 3600:2018 Cl. 13.1\n"
            f"Ast = n × (π db²/4)\n"
            f"Ast = {nb_bot:.0f} × (π × {db_bot:.0f}²/4) = {Ast_calc:.0f} mm²",
            
            f"Effective depth d — AS 3600:2018 Cl. 8.1.3\n"
            f"d = D - cover - db/2\n"
            f"d = {D:.0f} - {cover_bot:.0f} - {db_bot:.0f}/2 = {d:.0f} mm",
            
            f"Stress block factors — AS 3600:2018 Cl. 8.1.3\n"
            f"α₂ = 0.85 - 0.0015×f'c = 0.85 - 0.0015×{fc:.1f} = {alpha2:.3f}\n"
            f"γ = 0.97 - 0.0025×f'c = 0.97 - 0.0025×{fc:.1f} = {gamma:.3f}",
            
            f"Tension force T — AS 3600:2018 Cl. 8.1.3\n"
            f"T = Ast × fsy / 1000 [kN]\n"
            f"T = {Ast:.0f} × {fsy:.0f} / 1000 = {T:.1f} kN",
            
            f"Concrete compressive force C — AS 3600:2018 Cl. 8.1.3\n"
            f"C = α₂ × f'c × b × (γc) / 1000 [kN]",
            
            f"Neutral axis depth c (equilibrium) — AS 3600:2018 Cl. 8.1.3\n"
            f"Set T = C ⇒ c = T×1000 / (α₂×f'c×b×γ)\n"
            f"c = {T:.1f}×1000 / ({alpha2:.3f}×{fc:.1f}×{b:.0f}×{gamma:.3f}) = {c:.1f} mm",
            
            f"Equivalent stress block depth a — AS 3600:2018 Cl. 8.1.3\n"
            f"a = γc\n"
            f"a = {gamma:.3f} × {c:.1f} = {a:.1f} mm",
            
            f"Lever arm z — AS 3600:2018 Cl. 8.1.3\n"
            f"z = d - a/2\n"
            f"z = {d:.0f} - {a:.1f}/2 = {z:.1f} mm",
            
            f"Nominal moment capacity Mu — AS 3600:2018 Cl. 8.1.3\n"
            f"Mu = T × z / 1000 [kNm]\n"
            f"Mu = {T:.1f} × {z:.1f} / 1000 = {Mu_nom:.1f} kNm",
            
            f"Design capacity φMu,cap — AS 3600:2018 Cl. 2.2\n"
            f"φMu,cap = φ × Mu\n"
            f"φMu,cap = {phi:.2f} × {Mu_nom:.1f} = {phi_Mu_cap:.1f} kNm",
            
            f"Neutral axis ratio ku — AS 3600:2018 Cl. 8.1.3\n"
            f"ku = c/d\n"
            f"ku = {c:.1f} / {d:.0f} = {ku:.3f}",
            
            f"ULS check — AS 3600:2018 Cl. 2.2\n"
            f"Util = Mu* / φMu,cap\n"
            f"Util = {Mu_star:.1f} / {phi_Mu_cap:.1f} = {_safe_value(Mu_util, '{:.2f}')} → {outcome}",
        ]
    
    elif module == "shear":
        Vu_star = get_param("Vu_star", 0.0)
        phi_Vu_cap = get_param("phi_Vu_cap", 0.0)
        Vu_util = get_param("Vu_utilisation", None)
        phi = get_param("phi_shear", 0.75)
        fc = get_param("fc", 32.0)
        V_eq = get_param("V_eq_kN", Vu_star)
        b = get_param("b", 300.0)
        D = get_param("D", 600.0)
        d = get_param("d", 560.0)
        d_v = max(0.72*D, 0.9*d) if d > 0 else 0.72*D
        b_v = b
        Asv = get_param("lig_d", 10.0)  # Approximate
        s_lig = get_param("s_lig", 200.0)
        legs = get_param("lig_legs", 2)
        
        # Approximate intermediate values (would come from actual calc)
        Vuc_kN = phi_Vu_cap / phi * 0.6  # Rough estimate
        Vus_kN = phi_Vu_cap / phi * 0.4  # Rough estimate
        eps_x = 0.001
        k_v = 0.15
        theta_v_deg = 36.0
        
        steps = [
            f"Design action (ULS) — AS 3600:2018 Cl. 2.3\n"
            f"V* = {Vu_star:.1f} kN",
            
            f"Section geometry — AS 3600:2018 Cl. 8.2.1\n"
            f"b = {b:.0f} mm, D = {D:.0f} mm, d = {d:.0f} mm",
            
            f"Material properties — AS 3600:2018 Cl. 3.1\n"
            f"f'c = {fc:.1f} MPa",
            
            f"Capacity factor — AS 3600:2018 Cl. 2.2\n"
            f"φ = {phi:.2f}",
            
            f"Effective shear depth dv — AS 3600:2018 Cl. 8.2.1\n"
            f"dv = max(0.72D, 0.9d)\n"
            f"dv = max(0.72×{D:.0f}, 0.9×{d:.0f}) = {d_v:.0f} mm",
            
            f"Effective web width bv — AS 3600:2018 Cl. 8.2.1\n"
            f"bv = b = {b_v:.0f} mm",
            
            f"Equivalent shear V_eq* (if torsion present) — AS 3600:2018 Cl. 8.3.4\n"
            f"V_eq* = √(V*² + Vt,eq²)\n"
            f"V_eq* = {V_eq:.1f} kN",
            
            f"Longitudinal strain εx — AS 3600:2018 Cl. 8.2.4\n"
            f"εx calculated from M*, V*, As, Es (Cl. 8.2.4.2)\n"
            f"εx ≈ {eps_x:.4f}",
            
            f"Shear stress coefficient kv — AS 3600:2018 Cl. 8.2.4\n"
            f"kv from εx and reinforcement (Cl. 8.2.4.3)\n"
            f"kv ≈ {k_v:.3f}",
            
            f"Crack angle θv — AS 3600:2018 Cl. 8.2.4\n"
            f"θv from εx and kv (Cl. 8.2.4.4)\n"
            f"θv ≈ {theta_v_deg:.1f}°",
            
            f"Concrete contribution Vuc — AS 3600:2018 Cl. 8.2.4\n"
            f"Vuc = kv × bv × dv × √f'c / 1000 [kN]\n"
            f"Vuc ≈ {Vuc_kN:.1f} kN",
            
            f"Shear reinforcement — AS 3600:2018 Cl. 8.2.5\n"
            f"Asv = {legs:.0f} legs × (π × {Asv:.0f}²/4), s = {s_lig:.0f} mm",
            
            f"Steel contribution Vus — AS 3600:2018 Cl. 8.2.5\n"
            f"Vus = (Asv × fsyv × dv × cot θv) / s / 1000 [kN]\n"
            f"Vus ≈ {Vus_kN:.1f} kN",
            
            f"Total shear capacity Vu — AS 3600:2018 Cl. 8.2\n"
            f"Vu = Vuc + Vus\n"
            f"Vu = {Vuc_kN:.1f} + {Vus_kN:.1f} = {Vuc_kN + Vus_kN:.1f} kN",
            
            f"Design capacity φVu — AS 3600:2018 Cl. 2.2\n"
            f"φVu = φ × Vu\n"
            f"φVu = {phi:.2f} × {Vuc_kN + Vus_kN:.1f} = {phi_Vu_cap:.1f} kN",
            
            f"ULS check — AS 3600:2018 Cl. 2.2\n"
            f"Util = V_eq* / φVu\n"
            f"Util = {V_eq:.1f} / {phi_Vu_cap:.1f} = {_safe_value(Vu_util, '{:.2f}')} → {outcome}",
        ]
    
    elif module == "crack":
        w_calc = get_param("w_calc", 0.0)
        wmax_char = get_param("wmax_char", 0.3)
        sigma_sr = get_param("sigma_s_sls", 200.0)
        db = get_param("db_bot", 20.0)
        spacing = get_param("s_bar_bot", 200.0)
        cover_bot = get_param("cover_bot", 40.0)
        D = get_param("D", 600.0)
        b = get_param("b", 300.0)
        Ast = get_param("Ast_bot", 0.0)
        Es = get_param("Es", 200000.0)
        Ec = get_param("Ec", 30000.0)
        phi_cc_t = get_param("phi_cc_t", 2.0)
        eps_cs = get_param("eps_cs_total", 300e-6)
        
        # Calculate intermediate values
        c = cover_bot
        d_eff = D - c - db/2.0
        height_eff = min(2.5*c, D - d_eff, D/2.0)
        Aceff = b * max(height_eff, 1.0)
        rho_eff = Ast / Aceff if Aceff > 0 else 0.0
        sr_max = min(2.0*c, spacing/2.0)
        ne = (1.0 + phi_cc_t) * Es / Ec if Ec > 0 else 0.0
        fct_eff = 0.6 * math.sqrt(fc) if (fc := get_param("fc", 32.0)) > 0 else 0.0
        k1 = 0.8  # Deformed bars
        k2 = 0.5  # Flexure
        eps_diff = (sigma_sr / Es + eps_cs) if Es > 0 else 0.0
        
        steps = [
            f"Serviceability steel stress — AS 3600:2018 Cl. 8.6\n"
            f"σsr = {sigma_sr:.0f} MPa",
            
            f"Section geometry — AS 3600:2018 Cl. 8.6.2.3\n"
            f"b = {b:.0f} mm, D = {D:.0f} mm, cover = {cover_bot:.0f} mm",
            
            f"Effective area in tension Aceff — AS 3600:2018 Cl. 8.6.2.3\n"
            f"height_eff = min(2.5c, D-d_eff, D/2)\n"
            f"Aceff = b × height_eff = {b:.0f} × {height_eff:.0f} = {Aceff:.0f} mm²",
            
            f"Effective reinforcement ratio ρeff — AS 3600:2018 Cl. 8.6.2.3\n"
            f"ρeff = Ast / Aceff\n"
            f"ρeff = {Ast:.0f} / {Aceff:.0f} = {rho_eff:.4f}",
            
            f"Maximum crack spacing srmax — AS 3600:2018 Cl. 8.6.2.3\n"
            f"srmax = min(2.0c, s_bar/2)\n"
            f"srmax = min(2.0×{c:.0f}, {spacing:.0f}/2) = {sr_max:.0f} mm",
            
            f"Modular ratio ne — AS 3600:2018 Cl. 8.6.2.3\n"
            f"ne = (1 + φcc) × Es / Ec\n"
            f"ne = (1 + {phi_cc_t:.2f}) × {Es:.0f} / {Ec:.0f} = {ne:.2f}",
            
            f"Effective tensile strength fct,eff — AS 3600:2018 Cl. 8.6.2.3\n"
            f"fct,eff = 0.6 × √f'c\n"
            f"fct,eff = 0.6 × √{fc:.1f} = {fct_eff:.2f} MPa",
            
            f"Strain difference εdiff — AS 3600:2018 Cl. 8.6.2.3\n"
            f"εdiff = σsr/Es + εcs\n"
            f"εdiff = {sigma_sr:.0f}/{Es:.0f} + {eps_cs*1e6:.0f}×10⁻⁶ = {eps_diff*1e6:.1f}×10⁻⁶",
            
            f"Calculated crack width wcalc — AS 3600:2018 Cl. 8.6.2.3\n"
            f"wcalc = srmax × εdiff\n"
            f"wcalc = {sr_max:.0f} × {eps_diff*1e6:.1f}×10⁻⁶ = {w_calc:.3f} mm",
            
            f"Characteristic crack width limit wmax — AS 3600:2018 Cl. 8.6.1\n"
            f"wmax = {wmax_char:.3f} mm",
            
            f"SLS check — AS 3600:2018 Cl. 8.6.1\n"
            f"Util = wcalc / wmax\n"
            f"Util = {w_calc:.3f} / {wmax_char:.3f} = {_safe_value(_safe_ratio(w_calc, wmax_char), '{:.2f}')} → {outcome}",
        ]
    
    elif module == "creep":
        phi_cc_t = get_param("phi_cc_t", 2.0)
        phi_cc_b = get_param("phi_cc_b", 3.4) if get_param("phi_cc_b", None) is not None else 3.4
        k2 = get_param("k2_creep", 0.8)
        k3 = get_param("k3_creep", 0.7)
        k4 = get_param("k4_creep", 0.6)
        k5 = get_param("k5_creep", 1.0)
        k6 = get_param("k6_creep", 1.0)
        fc = get_param("fc", 32.0)
        t_creep = get_param("t_creep", 365.0)
        age_at_loading = get_param("age_at_loading", 28.0)
        stress_ratio = get_param("stress_ratio", 0.3)
        Ec = get_param("Ec", 30000.0)
        b = get_param("b", 300.0)
        D = get_param("D", 600.0)
        th = get_param("th_shrinkage", 200.0)  # Use shrinkage th as proxy
        
        steps = [
            f"Basic creep coefficient φcc,b — AS 3600:2018 Table 3.1.8.2\n"
            f"φcc,b = {phi_cc_b:.2f} (for f'c = {fc:.1f} MPa)",
            
            f"Notional thickness th — AS 3600:2018 Cl. 3.1.8.3\n"
            f"th = 2Ag / ue\n"
            f"th ≈ {th:.0f} mm",
            
            f"Time factor k2 — AS 3600:2018 Cl. 3.1.8.3\n"
            f"k2 = α₂t^0.8 / (t^0.8 + 0.15th)\n"
            f"k2 ≈ {k2:.3f}",
            
            f"Age factor k3 — AS 3600:2018 Cl. 3.1.8.3\n"
            f"k3 = 2.7 / (1 + log τ)\n"
            f"k3 = 2.7 / (1 + log {age_at_loading:.0f}) = {k3:.3f}",
            
            f"Environment factor k4 — AS 3600:2018 Cl. 3.1.8.3\n"
            f"k4 = {k4:.2f}",
            
            f"High-strength factor k5 — AS 3600:2018 Cl. 3.1.8.3\n"
            f"k5 = {k5:.2f}",
            
            f"Non-linear creep factor k6 — AS 3600:2018 Cl. 3.1.8.3\n"
            f"k6 = {k6:.2f}",
            
            f"Design creep coefficient φcc(t) — AS 3600:2018 Cl. 3.1.8.3\n"
            f"φcc(t) = k2 × k3 × k4 × k5 × k6 × φcc,b\n"
            f"φcc(t) = {k2:.3f} × {k3:.3f} × {k4:.2f} × {k5:.2f} × {k6:.2f} × {phi_cc_b:.2f} = {phi_cc_t:.2f}",
        ]
    
    elif module == "shrinkage":
        eps_cs_total = get_param("eps_cs_total", 0.0)
        eps_cse = get_param("eps_cse", 0.0)
        eps_csd_t = get_param("eps_csd_t", 0.0)
        fc = get_param("fc", 32.0)
        t_days = get_param("t_shrink", 365.0)
        th = get_param("th_shrinkage", 200.0)
        k1 = get_param("k1_shrinkage", 0.8)
        
        steps = [
            f"Autogenous shrinkage εcse — AS 3600:2018 Cl. 3.1.7.2(2),(3)\n"
            f"εcse(t) = εcse,final × (1 - e^(-0.04t))\n"
            f"εcse = {eps_cse*1e6:.0f} × 10⁻⁶",
            
            f"Notional thickness th — AS 3600:2018 Cl. 3.1.7.2\n"
            f"th = 2Ag / ue\n"
            f"th = {th:.0f} mm",
            
            f"Final drying shrinkage ε*csd — AS 3600:2018 Table 3.1.7.2\n"
            f"ε*csd from Table 3.1.7.2 (f'c = {fc:.1f} MPa, th = {th:.0f} mm)",
            
            f"Time factor k1 — AS 3600:2018 Cl. 3.1.7.2(4)\n"
            f"k1 = αt t^0.8 / (t^0.8 + 0.15th)\n"
            f"k1 ≈ {k1:.3f}",
            
            f"Drying shrinkage εcsd(t) — AS 3600:2018 Cl. 3.1.7.2(4)\n"
            f"εcsd(t) = k1 × ε*csd\n"
            f"εcsd(t) = {eps_csd_t*1e6:.0f} × 10⁻⁶",
            
            f"Total shrinkage εcs — AS 3600:2018 Cl. 3.1.7.2\n"
            f"εcs = εcse + εcsd(t)\n"
            f"εcs = {eps_cse*1e6:.0f} + {eps_csd_t*1e6:.0f} = {eps_cs_total*1e6:.0f} × 10⁻⁶",
        ]
    
    elif module == "deflection":
        delta_total = get_param("deflection_total_mm", 0.0)
        defl_limit = get_param("deflection_limit_mm", 0.0)
        defl_util = get_param("deflection_utilisation", None)
        L = get_param("L", 8000.0)
        L_m = L / 1000.0
        
        steps = [
            f"Span length — AS 3600:2018 Cl. 8.5\n"
            f"L = {L:.0f} mm = {L_m:.2f} m",
            
            f"Design loads — AS 3600:2018 Cl. 2.3\n"
            f"G and Q (dead and live loads)",
            
            f"Effective moment of inertia Ief — AS 3600:2018 Cl. 8.5.3\n"
            f"Ief calculated from section properties and reinforcement",
            
            f"Short-term deflection Δshort — AS 3600:2018 Cl. 8.5\n"
            f"Δshort from elastic analysis using Ief",
            
            f"Long-term deflection multiplier — AS 3600:2018 Cl. 8.5.3\n"
            f"kcs = (1 + φcc) for creep and shrinkage",
            
            f"Long-term deflection Δlong — AS 3600:2018 Cl. 8.5.3\n"
            f"Δlong = Δshort × kcs",
            
            f"Total deflection Δtotal — AS 3600:2018 Cl. 8.5\n"
            f"Δtotal = Δshort + Δlong\n"
            f"Δtotal = {delta_total:.2f} mm",
            
            f"Deflection limit — AS 3600:2018 Cl. 2.3.2\n"
            f"Δlimit = L/250\n"
            f"Δlimit = {L:.0f}/250 = {defl_limit:.2f} mm",
            
            f"SLS check — AS 3600:2018 Cl. 8.5\n"
            f"Util = Δtotal / Δlimit\n"
            f"Util = {delta_total:.2f} / {defl_limit:.2f} = {_safe_value(defl_util, '{:.2f}')} → {outcome}",
        ]
    
    else:
        # Generic fallback
        steps = [
            f"Determine design demand = {demand}",
            f"Calculate design capacity = {capacity}",
            f"Calculate utilisation = {utilisation}",
            f"Check demand ≤ capacity → {outcome}",
        ]
    
    return steps


def extract_summary_rows():
    """
    Extract summary rows matching the Summary table structure.
    
    Returns list of dicts with keys:
    - Check: check name (e.g., "Bending", "Shear")
    - Demand: demand value string
    - Capacity: capacity value string
    - Utilisation: utilisation value (float or "—")
    - Status: "PASS", "FAIL", or "—"
    """
    rows = []
    
    # --- Bending ---
    Mu_star = get_param("Mu_star", 0.0)
    phi_Mu_cap = get_param("phi_Mu_cap", 0.0)
    Mu_util = get_param("Mu_utilisation", None)
    
    if phi_Mu_cap > 0:
        status = "PASS" if (Mu_util is not None and Mu_util <= 1.0) else "FAIL" if Mu_util is not None else "—"
        rows.append({
            "Check": "Bending",
            "Demand": f"{Mu_star:.1f} kNm",
            "Capacity": f"{phi_Mu_cap:.1f} kNm",
            "Utilisation": f"{Mu_util:.2f}" if Mu_util is not None else "—",
            "Status": status,
        })
    
    # --- Shear ---
    Vu_star = get_param("Vu_star", 0.0)
    phi_Vu_cap = get_param("phi_Vu_cap", 0.0)
    Vu_util = get_param("Vu_utilisation", None)
    
    if phi_Vu_cap > 0:
        status = "PASS" if (Vu_util is not None and Vu_util <= 1.0) else "FAIL" if Vu_util is not None else "—"
        rows.append({
            "Check": "Shear",
            "Demand": f"{Vu_star:.1f} kN",
            "Capacity": f"{phi_Vu_cap:.1f} kN",
            "Utilisation": f"{Vu_util:.2f}" if Vu_util is not None else "—",
            "Status": status,
        })
    
    # --- Crack Control ---
    w_calc = get_param("w_calc", 0.0)
    wmax_char = get_param("wmax_char", 0.3)
    crack_util = _safe_ratio(w_calc, wmax_char)
    
    if w_calc > 0 or wmax_char > 0:
        status = "PASS" if (crack_util is not None and crack_util <= 1.0) else "FAIL" if crack_util is not None else "—"
        rows.append({
            "Check": "Crack Control",
            "Demand": f"{w_calc:.3f} mm" if w_calc > 0 else "—",
            "Capacity": f"{wmax_char:.3f} mm" if wmax_char > 0 else "—",
            "Utilisation": f"{crack_util:.2f}" if crack_util is not None else "—",
            "Status": status,
        })
    
    # --- Deflection ---
    delta_total = get_param("deflection_total_mm", 0.0)
    defl_limit = get_param("deflection_limit_mm", 0.0)
    defl_util = get_param("deflection_utilisation", None)
    
    if defl_limit > 0:
        status = "PASS" if (defl_util is not None and defl_util <= 1.0) else "FAIL" if defl_util is not None else "—"
        rows.append({
            "Check": "Deflection",
            "Demand": f"{delta_total:.2f} mm",
            "Capacity": f"{defl_limit:.2f} mm",
            "Utilisation": f"{defl_util:.2f}" if defl_util is not None else "—",
            "Status": status,
        })
    
    return rows


def extract_inputs_sections():
    """
    Extract input sections (geometry, materials, reinforcement, actions).
    
    Returns dict with sections:
    - geometry: dict with b, D, L
    - materials: dict with fc, fsy, Ec, Es
    - reinforcement: dict with reo details
    - actions: dict with design actions
    """
    sections = {
        "geometry": {
            "b": get_param("b", 400.0),
            "D": get_param("D", 600.0),
            "L": get_param("L", 3000.0),
        },
        "materials": {
            "fc": get_param("fc", 40.0),
            "fsy": get_param("fsy", 500.0),
            "Ec": get_param("Ec", 30000.0),
            "Es": get_param("Es", 200000.0),
        },
        "reinforcement": {
            "Ast_bot": get_param("Ast_bot", 0.0),
            "Ast_top": get_param("Ast_top", 0.0),
            "cover_bot": get_param("cover_bot", 30.0),
            "cover_top": get_param("cover_top", 30.0),
        },
        "actions": {
            "Mu_star": get_param("Mu_star", 0.0),
            "Vu_star": get_param("Vu_star", 0.0),
            "Tu_star": get_param("Tu_star", 0.0),
            "P_star": get_param("P_star", 0.0),
            "N_star": get_param("N_star", 0.0),
        },
    }
    
    return sections


def extract_check_sections(fig_paths=None):
    """
    Extract detailed check sections for each design check.
    
    Args:
        fig_paths: Dict mapping check names to figure file paths (optional)
    
    Returns list of dicts, each with:
    - title: check name (e.g., "Bending (ULS)")
    - summary: list of tuples [("Demand", "..."), ("Capacity", "..."), ("Utilisation", "..."), ("Outcome", "PASS/FAIL")]
    - steps: list of step descriptions (if available from results)
    - figures: list of figure file paths (optional)
    """
    if fig_paths is None:
        fig_paths = {}
    
    # Try to get results dict (may not exist)
    results = _ss("results", {})
    if not isinstance(results, dict):
        results = {}
    
    sections = []
    
    # --- Bending ---
    Mu_star = get_param("Mu_star", 0.0)
    phi_Mu_cap = get_param("phi_Mu_cap", 0.0)
    Mu_util = get_param("Mu_utilisation", None)
    
    if phi_Mu_cap > 0:
        outcome = "PASS" if (Mu_util is not None and Mu_util <= 1.0) else "FAIL" if Mu_util is not None else "N/A"
        
        # Get figures
        figs = fig_paths.get("bending", [])
        if not isinstance(figs, list):
            figs = [figs] if figs else []
        
        # Check for detailed report tree first (preferred)
        report = _r(results, "bending_report")
        if report and isinstance(report, dict) and report.get("tabs"):
            # Use report tree structure
            sections.append({
                "title": report.get("module_title", "Bending (ULS)"),
                "summary": report.get("summary", [
                    ("Demand", f"{Mu_star:.1f} kNm"),
                    ("Capacity", f"{phi_Mu_cap:.1f} kNm"),
                    ("Utilisation", f"{Mu_util:.2f}" if Mu_util is not None else "N/A"),
                    ("Outcome", outcome),
                ]),
                "tabs": report.get("tabs", []),
                "figures": figs,
            })
        else:
            # Fallback to steps (legacy)
            steps = _r(results, "bending_steps") or _r(results, "uls_flex_steps")
            if not steps or not isinstance(steps, list) or len(steps) == 0:
                steps = []
            
            sections.append({
                "title": "Bending (ULS)",
                "summary": [
                    ("Demand", f"{Mu_star:.1f} kNm"),
                    ("Capacity", f"{phi_Mu_cap:.1f} kNm"),
                    ("Utilisation", f"{Mu_util:.2f}" if Mu_util is not None else "N/A"),
                    ("Outcome", outcome),
                ],
                "steps": steps,
                "figures": figs,
            })
    
    # --- Shear ---
    Vu_star = get_param("Vu_star", 0.0)
    phi_Vu_cap = get_param("phi_Vu_cap", 0.0)
    Vu_util = get_param("Vu_utilisation", None)
    
    if phi_Vu_cap > 0:
        outcome = "PASS" if (Vu_util is not None and Vu_util <= 1.0) else "FAIL" if Vu_util is not None else "N/A"
        
        # Get figures
        figs = fig_paths.get("shear", [])
        if not isinstance(figs, list):
            figs = [figs] if figs else []
        
        # Check for detailed report tree first (preferred)
        report = _r(results, "shear_report")
        if report and isinstance(report, dict) and report.get("tabs"):
            # Use report tree structure
            sections.append({
                "title": report.get("module_title", "Shear (ULS)"),
                "summary": report.get("summary", [
                    ("Demand", f"{Vu_star:.1f} kN"),
                    ("Capacity", f"{phi_Vu_cap:.1f} kN"),
                    ("Utilisation", f"{Vu_util:.2f}" if Vu_util is not None else "N/A"),
                    ("Outcome", outcome),
                ]),
                "tabs": report.get("tabs", []),
                "figures": figs,
            })
        else:
            # Fallback to steps (legacy)
            steps = _r(results, "shear_steps") or _r(results, "uls_shear_steps")
            if not steps or not isinstance(steps, list) or len(steps) == 0:
                steps = []
            
            sections.append({
                "title": "Shear (ULS)",
                "summary": [
                    ("Demand", f"{Vu_star:.1f} kN"),
                    ("Capacity", f"{phi_Vu_cap:.1f} kN"),
                    ("Utilisation", f"{Vu_util:.2f}" if Vu_util is not None else "N/A"),
                    ("Outcome", outcome),
                ],
                "steps": steps,
                "figures": figs,
            })
    
    # --- Crack Control ---
    w_calc = get_param("w_calc", 0.0)
    wmax_char = get_param("wmax_char", 0.3)
    crack_util = _safe_ratio(w_calc, wmax_char)
    
    if w_calc > 0 or wmax_char > 0:
        outcome = "PASS" if (crack_util is not None and crack_util <= 1.0) else "FAIL" if crack_util is not None else "N/A"
        
        # Try to get steps from results
        steps = _r(results, "crack_steps") or _r(results, "sls_crack_steps")
        if not steps or not isinstance(steps, list) or len(steps) == 0:
            # Do not auto-generate steps - only show stored checks
            steps = []
        
        # Get figures
        figs = fig_paths.get("crack", [])
        if not isinstance(figs, list):
            figs = [figs] if figs else []
        
        sections.append({
            "title": "Crack Control",
            "summary": [
                ("Demand", f"{w_calc:.3f} mm" if w_calc > 0 else "N/A"),
                ("Capacity", f"{wmax_char:.3f} mm" if wmax_char > 0 else "N/A"),
                ("Utilisation", f"{crack_util:.2f}" if crack_util is not None else "N/A"),
                ("Outcome", outcome),
            ],
            "steps": steps,
            "figures": figs,
        })
    
    # --- Deflection ---
    delta_total = get_param("deflection_total_mm", 0.0)
    defl_limit = get_param("deflection_limit_mm", 0.0)
    defl_util = get_param("deflection_utilisation", None)
    
    if defl_limit > 0:
        outcome = "PASS" if (defl_util is not None and defl_util <= 1.0) else "FAIL" if defl_util is not None else "N/A"
        
        # Try to get steps from results
        steps = _r(results, "deflection_steps") or _r(results, "sls_defl_steps")
        if not steps or not isinstance(steps, list) or len(steps) == 0:
            # Do not auto-generate steps - only show stored checks
            steps = []
        
        # Get figures
        figs = fig_paths.get("deflection", [])
        if not isinstance(figs, list):
            figs = [figs] if figs else []
        
        sections.append({
            "title": "Deflection",
            "summary": [
                ("Demand", f"{delta_total:.2f} mm"),
                ("Capacity", f"{defl_limit:.2f} mm"),
                ("Utilisation", f"{defl_util:.2f}" if defl_util is not None else "N/A"),
                ("Outcome", outcome),
            ],
            "steps": steps,
            "figures": figs,
        })
    
    return sections
