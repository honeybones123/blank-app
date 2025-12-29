# deflection_core.py
# Core compute function for deflection (no Streamlit UI)

import math
from state_and_helpers import get_param, update_results
from deflection import (
    calc_ief_simplified,
    calc_deflection_as3600,
)


def _compute_deflection_results():
    """
    Compute deflection results using current session state values.
    Reads all inputs from get_param(), performs calculations, and updates results.
    No Streamlit UI - pure computation.
    """
    # Read geometry
    b = get_param("b", 400.0)
    D = get_param("D", 600.0)
    L = get_param("L", 8000.0)  # mm
    L_m = L / 1000.0  # Convert to meters
    
    # Read materials
    fc = get_param("fc", 32.0)
    Ec = get_param("Ec", 30000.0)
    
    # Read reinforcement
    Ast = get_param("Ast_bot", 0.0)
    Asc = get_param("Ast_top", 0.0)
    d = get_param("d", 560.0)
    
    # Read loads from SFD/BMD page (unified loading system)
    load_case = get_param("load_case", "Simple beam – UDL over entire span")
    
    # For UDL cases, read g and q directly
    g_udl = get_param("g_udl_kNm_per_m", None)
    q_udl = get_param("q_udl_kNm_per_m", None)
    
    # For point load cases, convert to equivalent UDL
    P_sls = get_param("P_sls_kN", None)
    G_point = get_param("G_point_kN", None)
    Q_point = get_param("Q_point_kN", None)
    
    if g_udl is not None and q_udl is not None:
        # UDL case - use actual g and q
        g_equiv = g_udl
        q_equiv = q_udl
    elif G_point is not None and Q_point is not None and L_m > 0:
        # Point load case - convert to equivalent UDL
        # M = PL/4 = wL²/8 => w = 2P/L
        g_equiv = 2.0 * G_point / L_m if L_m > 0 else 0.0
        q_equiv = 2.0 * Q_point / L_m if L_m > 0 else 0.0
    else:
        # Fallback defaults
        g_equiv = 8.0
        q_equiv = 4.0
    
    psi_s = get_param("psi_udl", 0.4)  # Sustained factor (for UDL cases)
    if psi_s is None:
        psi_s = get_param("psi_point", 0.4)  # Fallback to point load psi
    if psi_s is None:
        psi_s = 0.4  # Final fallback
    
    # Read creep/shrinkage from their pages
    phi_creep = get_param("phi_cc_t", 2.0)
    eps_sh_micro = get_param("eps_cs_total_micro", 300.0)
    eps_sh = eps_sh_micro * 1e-6
    
    # Simplified section properties (for I_ef calculation)
    beff = b  # Assume rectangular
    bw = b
    
    # Calculate effective moment of inertia
    ief_data = calc_ief_simplified(fc, beff, bw, d, Ast)
    Ief = ief_data[0]
    
    # Support type (default to simply supported)
    support_type = "Simply supported"
    
    # Calculate deflection
    results = calc_deflection_as3600(
        L_m=L_m,
        Ec=Ec,
        Ief=Ief,
        g_kNm=g_equiv,
        q_kNm=q_equiv,
        psi_s=psi_s,
        support_type=support_type,
        Ast=Ast,
        Asc=Asc,
    )
    
    delta_total = results["delta_total"]
    delta_short_total = results["delta_short_total"]
    delta_long_add = results["delta_long_add"]
    
    # Deflection limit (L/250 for beams)
    defl_limit = L / 250.0 if L > 0 else 0.0
    defl_util = delta_total / defl_limit if defl_limit > 0 else 0.0
    
    # Update session state (using keys expected by inputs_page)
    # Note: deflection page may use different keys, but inputs_page reads these
    update_results(
        deflection_total_mm=delta_total,
        deflection_limit_mm=defl_limit,
        deflection_utilisation=defl_util,
    )
    
    return {
        "delta_total": delta_total,
        "delta_short_total": delta_short_total,
        "delta_long_add": delta_long_add,
        "defl_limit": defl_limit,
        "defl_util": defl_util,
    }

