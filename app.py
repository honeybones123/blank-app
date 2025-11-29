import streamlit as st

from state_and_helpers import init_shared_session_state

# 🔁 Import modules, not individual functions
import inputs_page
import bending_page
import shear_page
import creep
import shrinkage
import deflection
import crack_page


def main():
    st.set_page_config(
        page_title="Concrete Beam Design",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Initialise shared state according to the contract
    init_shared_session_state()

    # Sidebar just for info now
    st.sidebar.title("Session state")
    st.sidebar.markdown(
        "- Shared params via `init_shared_session_state()`\n"
        "- Widgets use TAB_KEYS + sync callbacks\n"
        "- Creep & shrinkage feed Deflection / Crack via `st.session_state`"
    )

    # ---------------------------
    # Top navigation tabs
    # ---------------------------
    tab_labels = [
        "Inputs",
        "Bending",
        "Shear",
        "Creep",
        "Shrinkage",
        "Deflection",
        "Crack Control",
    ]

    tabs = st.tabs(tab_labels)

    for tab, label in zip(tabs, tab_labels):
        with tab:
            if label == "Inputs":
                inputs_page.render_inputs()
            elif label == "Bending":
                bending_page.render_bending()
            elif label == "Shear":
                shear_page.render_shear()
            elif label == "Creep":
                creep.render_creep()
            elif label == "Shrinkage":
                shrinkage.render_shrinkage()
            elif label == "Deflection":
                deflection.render_deflection()
            elif label == "Crack Control":
                crack_page.render_crack_control()


if __name__ == "__main__":
    main()
