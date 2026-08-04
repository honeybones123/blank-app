"""Crack-control input and presentation helper ownership."""

from __future__ import annotations

def bind_runtime(namespace: dict) -> None:
    globals().update({key: value for key, value in namespace.items() if not key.startswith("__")})

def _seed_from_param(name: str, fallback: float) -> float:
    """Seed default widget values from shared state, with safe fallback."""
    try:
        v = get_param(name)
    except TypeError:
        v = None

    try:
        if v is None:
            return float(fallback)
        v = float(v)
        if math.isnan(v):
            return float(fallback)
        return v
    except Exception:
        return float(fallback)

def _get_bottom_bar_diameter():
    """
    Get bottom bar diameter from session state.
    Prefer Layer 1, fall back to Layer 2 if Layer 1 is absent.
    Returns None if no bottom reinforcement is defined.
    """
    # Prefer Layer 1
    if st.session_state.get("nb_or_s_bot_1", 0.0) > 0:
        return float(st.session_state.get("db_bot_1", 20.0))
    # Fall back to Layer 2
    if st.session_state.get("nb_or_s_bot_2", 0.0) > 0:
        return float(st.session_state.get("db_bot_2", 20.0))
    # Fall back to derived db_bot
    db_bot = st.session_state.get("db_bot")
    if db_bot is not None and db_bot > 0:
        return float(db_bot)
    return None

def _get_bottom_bar_count():
    """
    Get total bottom bar count from session state.
    Returns None if no bottom reinforcement is defined.
    """
    nb_bot = st.session_state.get("nb_bot")
    if nb_bot is not None and nb_bot > 0:
        return int(nb_bot)
    return None

def _get_bottom_spacing():
    """
    Get bottom bar spacing from session state (derived from layout).
    Returns None if spacing is not available (e.g., single bar).
    """
    s_bot = st.session_state.get("s_bot")
    if s_bot is not None and s_bot > 0:
        return float(s_bot)
    return None

def _col_heading(text: str):
    """Consistent column heading style."""
    render_section_title(text)

def _inject_calcbox_css():
    """Style markdown blockquotes & readonly chips (same feel as shear/deflection)."""
    st.markdown(
        """
<style>
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 0.35rem 0.35rem 0 !important;
  color: #1a1a1a !important;
  opacity: 1 !important;
  font-size: 0.9rem !important;
  line-height: 1.35 !important;
}
blockquote * {
  color: #1a1a1a !important;
  opacity: 1 !important;
}
blockquote p {
  margin-bottom: 0.5rem !important;
}
blockquote p:last-child {
  margin-bottom: 0 !important;
}

/* Read-only linked-parameter chips */
.readonly-param {
  border-left: 4px solid #6c757d;
  background-color: rgba(108, 117, 125, 0.08);
  padding: 0.4rem 0.6rem;
  margin-bottom: 0.4rem;
  border-radius: 0 0.35rem 0.35rem 0;
  font-size: 0.85rem;
}
.readonly-param-title {
  font-weight: 600;
}
.readonly-param-value {
  font-weight: 500;
}
.readonly-param-source {
  font-size: 0.78rem;
  opacity: 0.8;
}
</style>
""",
        unsafe_allow_html=True,
    )

