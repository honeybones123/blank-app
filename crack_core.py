# crack_core.py
# Core compute function for crack control (no Streamlit UI)

import math
from state_and_helpers import get_param, update_results
from crack_page import (
    table_sigma_max_A,
    table_sigma_max_B,
    calc_eps_diff,
    calc_sr_max,
)


def _compute_crack_results():
    """
    Compute crack control results using current session state values.
    Reads all inputs from get_param(), performs calculations, and updates results.
    No Streamlit UI - pure computation.
    """
    # Read geometry
    b = get_param("b", 300.0)
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
    wmax_choice = 0.3  # Default, can be made configurable
    member_type = "Primarily flexure"  # Default
    
    # Read linked SLS values
    sigma_sr = get_param("sigma_s_sls", 200.0)
    phi_ce = get_param("phi_cc_t", 2.0)
    eps_cs_micro = get_param("eps_cs_total_micro", 300.0)
    eps_cs = eps_cs_micro * 1e-6
    
    # Effective area in tension
    c = cover_bot
    db = db_bot
    d_eff = D - c - db / 2.0
    height_eff = min(2.5 * c, max(D - d_eff, 0.0), D / 2.0)
    Aceff = b * max(height_eff, 1.0)
    rho_eff = Ast / Aceff if Aceff > 0 else 0.0
    
    # Table method (8.6.2.2)
    spacing = s_bar_bot
    sigma_table_A = table_sigma_max_A(db, wmax_choice)
    sigma_table_B = table_sigma_max_B(spacing, wmax_choice)
    
    if member_type == "Primarily tension":
        sigma_table_combined = sigma_table_A
    else:
        sigma_table_combined = max(sigma_table_A, sigma_table_B)
    
    sigma_08fsy = 0.8 * fsy
    sigma_allow_table = min(sigma_table_combined, sigma_08fsy)
    utilisation_table = sigma_sr / sigma_allow_table if sigma_allow_table > 0 else 0.0
    passes_table = utilisation_table <= 1.0
    
    # Direct calculation (8.6.2.3)
    fct_eff = 0.6 * math.sqrt(max(fc, 1.0))
    ne = (1.0 + phi_ce) * Es / Ec if Ec > 0 else 0.0
    k1 = 0.8  # Deformed bars (default)
    k2 = 0.5  # Flexure (default)
    
    eps_diff = calc_eps_diff(
        sigma_sr=sigma_sr,
        Es=Es,
        fct_eff=fct_eff,
        rho_eff=rho_eff,
        ne=ne,
        eps_cs=eps_cs,
    )
    
    sr_max = calc_sr_max(c_mm=c, db_mm=db, rho_eff=rho_eff, k1=k1, k2=k2)
    w_calc = sr_max * eps_diff
    utilisation_w = w_calc / wmax_choice if wmax_choice > 0 else 0.0
    passes_w = utilisation_w <= 1.0
    
    # Update session state
    update_results(
        sigma_sr=sigma_sr,
        sigma_allow_table=sigma_allow_table,
        w_calc=w_calc,
        wmax_char=wmax_choice,
        passes_table=passes_table,
        passes_w=passes_w,
    )
    
    return {
        "sigma_sr": sigma_sr,
        "sigma_allow_table": sigma_allow_table,
        "w_calc": w_calc,
        "wmax_char": wmax_choice,
        "passes_table": passes_table,
        "passes_w": passes_w,
    }








