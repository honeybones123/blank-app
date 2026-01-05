import streamlit as st

from state_and_helpers import (
    init_shared_session_state,
    sync_shared_from_widgets_once_per_run,
    recalc_derived_values,
    assert_shared_state_alive,
)

# 🔁 Import modules, not individual functions
import inputs_page
import bending_page
import shear_page
import creep
import shrinkage
import deflection
import crack_page
import sfd_bmd_page

# ---- page registry ----
PAGES = {
    "inputs": ("Inputs", inputs_page.render_inputs),
    "bending": ("Bending", bending_page.render_bending),
    "shear": ("Shear", shear_page.render_shear),
    "creep": ("Creep", creep.render_creep),
    "shrinkage": ("Shrinkage", shrinkage.render_shrinkage),
    "crack": ("Crack Control", crack_page.render_crack_control),
    "design": ("Design", sfd_bmd_page.render_sfd_bmd_page),
    "deflection": ("Deflection", deflection.render_deflection),
}

SLUGS = list(PAGES.keys())
LABELS = [PAGES[s][0] for s in SLUGS]

NAV_KEY = "nav_page_slug"  # stores the slug, e.g. "shear"
LAST_QP_KEY = "last_qp_page_seen"   # local-only UI state


def set_query_params_merge(**updates):
    """Update query params without clearing (avoids session/connection resets)."""
    # Apply updates
    for k, v in updates.items():
        if v is None:
            # remove if present
            try:
                del st.query_params[k]
            except Exception:
                pass
        else:
            st.query_params[k] = v


def main():
    # --- ARCHITECTURE LOCK: dev mode flag ---
    st.session_state.setdefault("_dev_mode", True)
    
    st.set_page_config(
        page_title="Concrete Beam Design",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # --- CSS styling for top navigation (make radio look like Streamlit tabs) ---
    st.markdown("""
<style>
/* ==========================================================
   TOP PAGE NAV ONLY (matches Streamlit st.tabs style)
   Scoped to the container that contains #page-nav-anchor
   ========================================================== */

div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"]{
  display:flex !important;
  align-items:center !important;
  gap:18px !important;
  border-bottom: 1px solid rgba(49,51,63,0.20) !important;
  padding-bottom: 6px !important;
  margin-bottom: 1rem !important;
}

/* tab label */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label{
  margin:0 !important;
  padding: 6px 2px !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  cursor: pointer !important;
  font-weight: 500 !important;
}

/* remove the radio circle/control (robust across Streamlit builds) */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label svg,
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label [role="img"],
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label input[type="radio"],
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label > div:first-child,
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label > span:first-child{
  display:none !important;
}

/* active underline (tab selected) */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label:has(input:checked),
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label[aria-checked="true"]{
  border-bottom: 2px solid #ff4b4b !important;
  font-weight: 600 !important;
}

/* prevent "button hover" feel */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label:hover{
  background: transparent !important;
}

/* tighten inner wrappers */
div[data-testid="stVerticalBlock"]:has(#page-nav-anchor) div[role="radiogroup"] > label *{
  margin:0 !important;
  padding:0 !important;
}
</style>
""", unsafe_allow_html=True)

    # Initialise shared state according to the contract
    init_shared_session_state()
    
    # Debug mode toggle (only shown if env var is set)
    try:
        from src.debug.debug_flags import show_debug_toggle
        show_debug_toggle()
        
        # Cache control (only shown when debug mode enabled)
        from src.debug.cache_control import show_cache_control
        show_cache_control()
    except ImportError:
        # Debug module not available, skip
        pass
    
    # Debug checkpoints (track state changes)
    try:
        from src.debug.state_debug import snapshot_state, diff_snapshots, is_debug_enabled
        from state_and_helpers import DERIVED_KEYS, RESULT_KEYS
        if is_debug_enabled():
            # Checkpoint: after init_shared_session_state
            if "_debug_last_checkpoint" not in st.session_state:
                st.session_state["_debug_last_checkpoint"] = {}
            checkpoint_keys = list(DERIVED_KEYS | RESULT_KEYS)[:20]  # Limit to first 20 keys
            current_snapshot = snapshot_state("after_init", checkpoint_keys)
            if st.session_state["_debug_last_checkpoint"]:
                diff = diff_snapshots(st.session_state["_debug_last_checkpoint"], current_snapshot)
                if diff:
                    if "_debug_checkpoints" not in st.session_state:
                        st.session_state["_debug_checkpoints"] = []
                    st.session_state["_debug_checkpoints"].append({
                        "label": "After init_shared_session_state",
                        "diff": diff,
                    })
            st.session_state["_debug_last_checkpoint"] = current_snapshot
    except (ImportError, NameError):
        # Debug module not available, skip
        pass
    
    # Sync widget values to shared keys (ensures shared state persists across page navigation)
    sync_shared_from_widgets_once_per_run()
    
    # Recalculate derived values (d, Ast_bot, etc.) from current inputs
    # Wrap with debug guard in debug mode
    try:
        from src.debug.state_debug import guard_session_writes, is_debug_enabled
        from state_and_helpers import DERIVED_KEYS
        if is_debug_enabled():
            with guard_session_writes(allowed_keys=DERIVED_KEYS, context="recalc_derived_values"):
                recalc_derived_values()
        else:
            recalc_derived_values()
    except (ImportError, NameError):
        # Debug module not available or DERIVED_KEYS not defined, use normal path
        recalc_derived_values()

    # --- 1) Read URL param (page) and pre-set nav state BEFORE widget renders
    qp_page = st.query_params.get("page")
    if isinstance(qp_page, list):
        qp_page = qp_page[0] if qp_page else None

    # ✅ Only adopt URL -> nav when the URL page actually changes
    if qp_page in PAGES and st.session_state.get(LAST_QP_KEY) != qp_page:
        st.session_state[NAV_KEY] = qp_page
        st.session_state[LAST_QP_KEY] = qp_page

    # ✅ If no valid page in URL, still ensure defaults exist
    if NAV_KEY not in st.session_state:
        st.session_state[NAV_KEY] = "inputs"

    # --- 2) TOP "tabs" (same logic, just container + anchor for CSS targeting)
    nav_container = st.container()
    with nav_container:
        st.markdown('<div id="page-nav-anchor"></div>', unsafe_allow_html=True)

        selected_slug = st.radio(
            "",
            options=SLUGS,
            horizontal=True,
            key=NAV_KEY,
            format_func=lambda s: PAGES[s][0],  # Display label but store slug
            label_visibility="collapsed",
        )

    # --- 3) Sync URL ONLY if it differs (prevents "stuck on bending" loops)
    # ✅ If a jump is present, DO NOT touch query params at all.
    if "jump" not in st.query_params:
        if st.query_params.get("page") != selected_slug:
            set_query_params_merge(page=selected_slug)
            st.session_state[LAST_QP_KEY] = selected_slug

    # Sidebar info
    st.sidebar.title("Session state")
    st.sidebar.markdown(
        "- Shared params via `init_shared_session_state()`\n"
        "- Widgets use TAB_KEYS + sync callbacks\n"
        "- Creep & shrinkage feed Deflection / Crack via `st.session_state`"
    )
    
    # Debug State Inspector panel (only shown if debug mode is enabled)
    try:
        from src.debug.debug_panel import render_state_inspector
        render_state_inspector()
    except ImportError:
        # Debug module not available, skip
        pass

    # --- 4) Regression tripwire: verify shared state is alive
    assert_shared_state_alive()
    
    # Debug: run invariant checks
    try:
        from src.debug.state_debug import assert_invariants
        assert_invariants()
    except ImportError:
        # Debug module not available, skip
        pass
    
    # --- 5) Render selected page
    PAGES[selected_slug][1]()


if __name__ == "__main__":
    main()
