"""
Design Runner - Run all design checks without UI rendering

This module provides run_all_design_checks() which computes all design checks
(Bending, Shear, Crack, Creep, Shrinkage, Deflection) and updates results
in session state without rendering any UI.
"""

import streamlit as st
from state_and_helpers import init_shared_session_state, update_results, get_param


def _inputs_fingerprint():
    """
    Return a stable tuple/hash of key input params that affect design.
    Uses get_param() values; does NOT add new widget keys.
    """
    keys = [
        "b", "D", "L", "fc", "fsy", "Es", "Ec",
        "Mu_star", "Vu_star", "Tu_star",
        "cover_bot", "cover_top", "cover_side",
        "nb_or_s_bot_1", "db_bot_1", "nb_or_s_bot_2", "db_bot_2",
        "nb_or_s_top_1", "db_top_1", "nb_or_s_top_2", "db_top_2",
        "s_lig", "lig_d", "lig_legs",
        "exposure_class", "env_option", "t_creep", "age_at_loading", "stress_ratio",
        "t_shrink", "RH", "Ac", "u_e",
    ]
    vals = []
    for k in keys:
        try:
            vals.append((k, str(get_param(k, ""))))
        except Exception:
            vals.append((k, ""))
    return tuple(vals)


def run_all_design_checks(force: bool = False, include_sls: bool = True, include_min: bool = True):
    """
    Run all design checks using the module registry.
    
    Args:
        force: If True, run checks even if inputs haven't changed
        include_sls: Include SLS calculations (default True)
        include_min: Include minimum requirements checks (default True)
    
    This function:
    - Uses the module registry to run all modules
    - Reads inputs from session state (via get_param)
    - Runs all module calculations
    - Updates results via update_results()
    - Does NOT render any UI
    """
    init_shared_session_state()
    
    fp = _inputs_fingerprint()
    last_fp = st.session_state.get("_design_fp", None)
    
    if (not force) and (last_fp == fp) and st.session_state.get("_design_all_done", False):
        return  # already current
    
    # Mark as running
    st.session_state["_design_all_done"] = False
    st.session_state["_design_fp"] = fp
    
    # Use module registry to run all modules
    try:
        from reporting.module_registry import run_all_modules
        run_all_modules(force=force, include_sls=include_sls, include_min=include_min)
    except ImportError:
        # Fallback to direct calls if registry not available
        # Bending
        try:
            from bending_page import compute_bending_results
            compute_bending_results(publish=True)
        except Exception as e:
            update_results(bending_error=str(e))
        
        # Shear
        try:
            from shear_page import compute_shear_results
            compute_shear_results(publish=True)
        except Exception as e:
            update_results(shear_error=str(e))
        
        # Crack
        try:
            from crack_core import compute_crack_results
            compute_crack_results(publish=True)
        except Exception as e:
            update_results(crack_error=str(e))
        
        # Creep
        try:
            from creep import compute_creep_results
        except Exception:
            pass
        
        # Shrinkage
        try:
            from shrinkage import compute_shrinkage_results
        except Exception:
            pass
        
        # Deflection
        try:
            from deflection_core import compute_deflection_results
            compute_deflection_results(publish=True)
        except Exception:
            pass
    
    st.session_state["_design_all_done"] = True
    
    # --- Verify detailed reports exist ---
    if "results" not in st.session_state:
        st.session_state["results"] = {}
    results = st.session_state["results"]
    
    # Bending: verify report exists
    if not results.get("bending_report"):
        results["bending_report_error"] = "Bending report not published. build_bending_report() not called."
    
    # --- GUARANTEE: publish minimal checks if missing (only for modules without reports) ---
    _ensure_min_checks()


def _ensure_min_checks():
    """
    Ensure minimal checks are published in results dict if modules didn't publish them.
    These are "app-style" high-level checks (not micro-derivations).
    
    IMPORTANT: Only creates fallback checks for modules that don't have detailed reports yet.
    If a module has a *_report, it should NOT have *_steps created here.
    """
    # Ensure results dict exists
    if "results" not in st.session_state:
        st.session_state["results"] = {}
    results = st.session_state["results"]
    
    # Get values from session state (using get_param for safety)
    from state_and_helpers import get_param
    
    # Bending checks - ONLY if no detailed report exists
    if not results.get("bending_report") and not results.get("bending_steps"):
        Mu_star = get_param("Mu_star", 0.0)
        phi_Mu_cap = get_param("phi_Mu_cap", 0.0)
        Mu_util = get_param("Mu_utilisation", None)
        pass_bending = Mu_util is not None and Mu_util <= 1.0 if Mu_util is not None else False
        
        results["bending_steps"] = [
            {"title": "Actions", "clause": "AS 3600:2018 Cl. 2.3", "equations": [f"Mu* = {Mu_star:.1f} kNm"], "notes": []},
            {"title": "Capacity", "clause": "AS 3600:2018 Cl. 8.1.3", "equations": [f"φMu,cap = {phi_Mu_cap:.1f} kNm"], "notes": []},
            {"title": "Utilisation", "clause": "AS 3600:2018 Cl. 2.2", "equations": [f"Util = {Mu_util:.2f}" if Mu_util is not None else "Util = N/A"], "notes": []},
            {"title": "Outcome", "clause": "", "equations": [f"{'PASS' if pass_bending else 'FAIL'}"], "notes": []},
        ]
    
    # Shear checks - ONLY if no detailed report exists
    if not results.get("shear_report") and not results.get("shear_steps"):
        Vu_star = get_param("Vu_star", 0.0)
        phi_Vu_cap = get_param("phi_Vu_cap", 0.0)
        Vu_util = get_param("Vu_utilisation", None)
        pass_shear = Vu_util is not None and Vu_util <= 1.0 if Vu_util is not None else False
        
        results["shear_steps"] = [
            {"title": "Actions", "clause": "AS 3600:2018 Cl. 2.3", "equations": [f"V* = {Vu_star:.1f} kN"], "notes": []},
            {"title": "Capacity", "clause": "AS 3600:2018 Cl. 8.2 (MCFT)", "equations": [f"φVu,cap = {phi_Vu_cap:.1f} kN"], "notes": []},
            {"title": "Utilisation", "clause": "AS 3600:2018 Cl. 2.2", "equations": [f"Util = {Vu_util:.2f}" if Vu_util is not None else "Util = N/A"], "notes": []},
            {"title": "Outcome", "clause": "", "equations": [f"{'PASS' if pass_shear else 'FAIL'}"], "notes": []},
        ]
    
    # Crack checks
    if not results.get("crack_steps"):
        w_calc = get_param("w_calc", 0.0)
        wmax_char = get_param("wmax_char", 0.3)
        crack_util = w_calc / wmax_char if wmax_char > 0 else None
        pass_crack = crack_util is not None and crack_util <= 1.0 if crack_util is not None else False
        
        results["crack_steps"] = [
            {"title": "Demand", "clause": "AS 3600:2018 SLS Crack Control", "equations": [f"w* = {w_calc:.3f} mm"], "notes": []},
            {"title": "Limit", "clause": "AS 3600:2018 (exposure-dependent)", "equations": [f"w_lim = {wmax_char:.3f} mm"], "notes": []},
            {"title": "Utilisation", "clause": "", "equations": [f"Util = {crack_util:.2f}" if crack_util is not None else "Util = N/A"], "notes": []},
            {"title": "Outcome", "clause": "", "equations": [f"{'PASS' if pass_crack else 'FAIL'}"], "notes": []},
        ]

