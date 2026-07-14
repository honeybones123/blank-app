"""
Debug flags and environment variable handling.

Controls debug mode via environment variable STRUCTURALBASE_DEBUG=1 or session state.
"""

import os
import streamlit as st


def is_debug_enabled() -> bool:
    """
    Check if debug mode is enabled.
    
    Returns True if:
    - Environment variable STRUCTURALBASE_DEBUG=1 is set, OR
    - st.session_state.get("_debug_enabled") is True
    
    Returns:
        bool: True if debug mode is enabled
    """
    env_debug = os.getenv("STRUCTURALBASE_DEBUG", "").strip() == "1"
    session_debug = st.session_state.get("_debug_enabled", False)
    return env_debug or session_debug


def show_debug_toggle():
    """
    Show debug toggle checkbox in sidebar (only if env var is set).
    
    This allows enabling/disabling debug mode via UI even when env var is set.
    """
    env_debug = os.getenv("STRUCTURALBASE_DEBUG", "").strip() == "1"
    if env_debug:
        st.sidebar.checkbox("Debug mode", key="_debug_enabled", value=True)
