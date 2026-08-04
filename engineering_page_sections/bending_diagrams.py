"""Bending diagram section helpers."""

from __future__ import annotations

def bind_runtime(namespace: dict) -> None:
    globals().update({key: value for key, value in namespace.items() if not key.startswith("__")})

def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)

def _get_build_beam_3d_figure_pure():
    """Get the cached or uncached version of _build_beam_3d_figure_pure based on debug mode."""
    try:
        from src.debug.cache_control import cache_enabled
        if cache_enabled():
            # Caching enabled: use cache
            return st.cache_resource(show_spinner=False)(_build_beam_3d_figure_pure_impl)
        else:
            # Cache bypass enabled: return unwrapped function
            return _build_beam_3d_figure_pure_impl
    except ImportError:
        # Debug module not available: use cache
        return st.cache_resource(show_spinner=False)(_build_beam_3d_figure_pure_impl)

def _build_beam_3d_figure_pure_impl(
    b,
    D,
    L,
    Mu_star,
    phi_Mu_cap,
    c,
    strain_state,
    reo_layout,
    cover_bot,
    cover_top,
    cover_side,
    rowgap_bot,
    rowgap_top,
    lig_d,
    lig_legs,
    s_lig,
    debug_bust=None,
):
    """Compatibility wrapper for the shared 3D bending diagram builder."""
    return _shared_build_beam_3d_figure_pure(
        b,
        D,
        L,
        Mu_star,
        phi_Mu_cap,
        c,
        strain_state,
        reo_layout,
        cover_bot,
        cover_top,
        cover_side,
        rowgap_bot,
        rowgap_top,
        lig_d,
        lig_legs,
        s_lig,
        debug_bust=debug_bust,
    )

def _build_beam_3d_figure(b, D, L, Mu_star, phi_Mu_cap, c, strain_state: str = "ULS", layout=None):
    """
    Wrapper function that reads from session state and calls the cached pure function.
    
    Args:
        layout: Optional pre-computed section layout dict. If None, will compute from session state.
    """
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
    
    # If layout is provided, extract reo_layout from it
    if layout is not None:
        reo_layout = layout.get("reo_layout")
        if reo_layout is None:
            # Fallback to computing from session state using results
            from section_layout import compute_longitudinal_reo_layout
            reo_layout = compute_longitudinal_reo_layout(
                b=results.get("b", b), D=results.get("D", D),
                cover_bot=results.get("cover_bot", 40.0), cover_top=results.get("cover_top", 40.0), cover_side=results.get("cover_side", 40.0),
                nb_or_s_bot_1=results.get("nb_or_s_bot_1", 4.0), db_bot_1=results.get("db_bot_1", 20.0),
                nb_or_s_bot_2=results.get("nb_or_s_bot_2", 0.0), db_bot_2=results.get("db_bot_2", 20.0),
                nb_or_s_top_1=results.get("nb_or_s_top_1", 2.0), db_top_1=results.get("db_top_1", 16.0),
                nb_or_s_top_2=results.get("nb_or_s_top_2", 0.0), db_top_2=results.get("db_top_2", 16.0),
                rowgap_bot=results.get("rowgap_bot", 60.0), rowgap_top=results.get("rowgap_top", 60.0),
            )
    else:
        # Compute from session state using results
        from section_layout import compute_longitudinal_reo_layout
        reo_layout = compute_longitudinal_reo_layout(
            b=results.get("b", b), D=results.get("D", D),
            cover_bot=results.get("cover_bot", 40.0), cover_top=results.get("cover_top", 40.0), cover_side=results.get("cover_side", 40.0),
            nb_or_s_bot_1=results.get("nb_or_s_bot_1", 4.0), db_bot_1=results.get("db_bot_1", 20.0),
            nb_or_s_bot_2=results.get("nb_or_s_bot_2", 0.0), db_bot_2=results.get("db_bot_2", 20.0),
            nb_or_s_top_1=results.get("nb_or_s_top_1", 2.0), db_top_1=results.get("db_top_1", 16.0),
            nb_or_s_top_2=results.get("nb_or_s_top_2", 0.0), db_top_2=results.get("db_top_2", 16.0),
            rowgap_bot=results.get("rowgap_bot", 60.0), rowgap_top=results.get("rowgap_top", 60.0),
        )
    
    # Get ligature spacing from results
    s_lig = results.get("s_lig", get_param("s_lig", 200.0))
    s_lig = float(s_lig) if s_lig is not None else 200.0
    
    # Cache-busting for debug mode
    debug_bust = None
    try:
        from src.debug.debug_flags import is_debug_enabled
        import hashlib
        import json
        if is_debug_enabled():
            # Create a signature from all dimension inputs
            dim_sig = {
                "b": results.get("b", b),
                "D": results.get("D", D),
                "L": results.get("L", L),
                "d": results.get("d", get_param("d", 560.0)),
                "cover_bot": results.get("cover_bot", 40.0),
                "cover_top": results.get("cover_top", 40.0),
                "cover_side": results.get("cover_side", 40.0),
            }
            debug_bust = hashlib.sha1(json.dumps(dim_sig, sort_keys=True).encode()).hexdigest()[:8]
    except ImportError:
        pass

    # Get cached or uncached version based on debug mode
    _build_fn = _get_build_beam_3d_figure_pure()
    return _build_fn(
        b, D, L, Mu_star, phi_Mu_cap, c, strain_state,
        reo_layout, results.get("cover_bot", 40.0), results.get("cover_top", 40.0),
        results.get("cover_side", 40.0), results.get("rowgap_bot", 60.0), results.get("rowgap_top", 60.0), 
        results.get("lig_d", 10.0), results.get("lig_legs", 2), s_lig, debug_bust=debug_bust
    )

