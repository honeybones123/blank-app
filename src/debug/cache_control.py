# cache_control.py
"""
Debug-only cache control utilities.

Provides cache bypass functionality for debugging stale cache issues.
"""
import streamlit as st


def cache_enabled() -> bool:
    """
    Returns False when debug bypass is on.
    
    Returns:
        True if caching should be enabled, False if bypassed
    """
    try:
        from src.debug.debug_flags import is_debug_enabled
        if is_debug_enabled():
            # Check if user has enabled cache bypass
            return not st.session_state.get("_debug_bypass_cache", False)
        return True  # Caching enabled in production
    except ImportError:
        return True  # Debug module not available, use cache


def show_cache_control():
    """
    Show cache bypass toggle in sidebar (only when debug mode enabled).
    """
    try:
        from src.debug.debug_flags import is_debug_enabled
        if is_debug_enabled():
            st.sidebar.checkbox(
                "Bypass caches",
                key="_debug_bypass_cache",
                help="Disable all caches to debug stale cache issues. Slower but always fresh."
            )
    except ImportError:
        pass


def bypass_cache_if_enabled(cached_fn):
    """
    Decorator that bypasses cache when debug bypass is enabled.
    
    Usage:
        @bypass_cache_if_enabled
        @st.cache_data
        def my_cached_function(...):
            ...
    """
    def wrapper(*args, **kwargs):
        if not cache_enabled():
            # Bypass cache by calling the unwrapped function
            if hasattr(cached_fn, '__wrapped__'):
                return cached_fn.__wrapped__(*args, **kwargs)
            else:
                # Fallback: try to get the original function
                return cached_fn(*args, **kwargs)
        return cached_fn(*args, **kwargs)
    
    wrapper.__wrapped__ = cached_fn
    return wrapper

