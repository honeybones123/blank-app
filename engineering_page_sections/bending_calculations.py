"""Bending calculation and shared-state section helpers."""

from __future__ import annotations

def bind_runtime(namespace: dict) -> None:
    globals().update({key: value for key, value in namespace.items() if not key.startswith("__")})

def _compute_sls_bending_values():
    """
    Compute SLS bending values (cracked section analysis) without UI rendering.
    Compatibility wrapper for the non-page bending_core adapter.
    """
    return compute_sls_bending_values_from_state(publish=True)

def compute_bending_results(publish: bool = True) -> dict:
    """
    Compute bending results without UI rendering.
    Includes ULS, SLS, and minimum strength checks.
    
    Args:
        publish: If True, update results via update_results(). Always True for now.
    
    Returns:
        dict with computed results
    """
    import streamlit as st
    from state_and_helpers import recalc_derived_values, get_param
    recalc_derived_values()
    
    # Call existing compute function (which already calls update_results)
    results = _compute_bending_capacity()
    
    # Compute SLS values (ensures they're available for report building)
    _compute_sls_bending_values()
    
    # Pull shared values for calculations (matches shear pattern)
    inputs = _get_bending_inputs_from_shared_state()
    params = {
        "b": inputs["b"],
        "D": inputs["D"],
        "fc": inputs["fc"],
        "fsy": inputs["fsy"],
        "Ast": inputs["Ast_bot"],
        "d": inputs["d"],
        "phi": inputs["phi"],
        "Mu_star_uls": inputs["Mu_star_uls"],
        "Mu_star_sls": inputs["Mu_star_sls"],
        "Ec": inputs["Ec"],
        "Es": inputs["Es"],
        "moment_sign": st.session_state.get("bending_detail_view", "positive"),
    }
    
    # Build and store report
    report = build_bending_report(results, params)
    
    # Store report in results dict
    if "results" not in st.session_state:
        st.session_state["results"] = {}
    st.session_state["results"]["bending_report"] = report
    
    return {
        "phi_Mu_cap": results.get("phi_Mu_cap", 0.0),
        "Mu_utilisation": results.get("Mu_util", 0.0),
    }

def _get_bending_inputs_from_shared_state():
    """
    Read all bending inputs from shared canonical keys only.
    Matches shear's pattern: reads directly from shared state, no defaults, no fallbacks.
    """
    from state_and_helpers import get_param
    
    return {
        "b": get_param("b"),
        "D": get_param("D"),
        "L": get_param("L"),
        "d": get_param("d"),
        "cover_bot": get_param("cover_bot"),
        "cover_top": get_param("cover_top"),
        "cover_side": get_param("cover_side"),
        "fc": get_param("fc"),
        "fsy": get_param("fsy"),
        "Ec": get_param("Ec"),
        "Es": get_param("Es"),
        "phi": get_param("phi_bend"),
        "Mu_star_uls": get_param("Mu_star"),
        "Mu_star_sls": get_param("sls_Mstar"),
        "Ast_bot": get_param("Ast_bot"),
        "nb_or_s_bot_1": get_param("nb_or_s_bot_1"),
        "db_bot_1": get_param("db_bot_1"),
        "nb_or_s_bot_2": get_param("nb_or_s_bot_2"),
        "db_bot_2": get_param("db_bot_2"),
        "nb_or_s_top_1": get_param("nb_or_s_top_1"),
        "db_top_1": get_param("db_top_1"),
        "nb_or_s_top_2": get_param("nb_or_s_top_2"),
        "db_top_2": get_param("db_top_2"),
        "rowgap_bot": get_param("rowgap_bot"),
        "rowgap_top": get_param("rowgap_top"),
        "lig_legs": get_param("lig_legs"),
        "lig_d": get_param("lig_d"),
        "s_lig": get_param("s_lig"),
        "nb_bot": get_param("nb_bot"),
        "db_bot": get_param("db_bot"),
        "nb_top": get_param("nb_top"),
        "db_top": get_param("db_top"),
    }

def make_bending_sig_from_shared_state() -> dict:
    """
    Build a complete signature dict from shared state for cache keys.
    Includes all inputs that affect bending calculations and diagrams.
    """
    return _get_bending_inputs_from_shared_state()

def get_bending_inputs_from_shared_state():
    """
    Read all bending inputs from shared canonical keys only.
    Returns a dict with all dimensions and material properties.
    Treats 0 as valid - only uses defaults if value is None.
    """
    return make_bending_sig_from_shared_state()

