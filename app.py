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
    st.set_page_config(
        page_title="Concrete Beam Design",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # --- CSS styling for top navigation (make radio look like tabs) ---
    st.markdown(
        """
<style>
/* --- Make horizontal radio look like tabs --- */
div[role="radiogroup"]{
  gap: 0.35rem !important;
}

/* hide the circle icons */
div[role="radiogroup"] > label > div:first-child{
  display: none !important;
}

/* style each option like a tab */
div[role="radiogroup"] > label{
  border: 1px solid rgba(49,51,63,0.18);
  border-bottom: 2px solid transparent;
  border-radius: 10px 10px 10px 10px;
  padding: 0.35rem 0.7rem;
  margin: 0 !important;
  background: rgba(255,255,255,0.6);
}

/* hover */
div[role="radiogroup"] > label:hover{
  border-color: rgba(49,51,63,0.35);
  background: rgba(255,255,255,0.9);
}

/* selected tab: Streamlit adds aria-checked on the input element */
div[role="radiogroup"] > label:has(input[aria-checked="true"]){
  background: rgba(255,255,255,1);
  border-color: rgba(49,51,63,0.35);
  border-bottom-color: rgba(255,75,75,0.95); /* accent underline */
}

/* make text look tabby */
div[role="radiogroup"] > label *{
  font-weight: 600;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # Initialise shared state according to the contract
    init_shared_session_state()
    
    # Sync widget values to shared keys (ensures shared state persists across page navigation)
    sync_shared_from_widgets_once_per_run()
    
    # Recalculate derived values (d, Ast_bot, etc.) from current inputs
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

    # --- 2) TOP "tabs" (use radio with slugs, display labels)
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

    # --- 4) Regression tripwire: verify shared state is alive
    assert_shared_state_alive()
    
    # --- 5) Render selected page
    PAGES[selected_slug][1]()


if __name__ == "__main__":
    main()
