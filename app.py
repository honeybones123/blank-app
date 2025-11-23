import streamlit as st

from state_and_helpers import init_shared_session_state

from inputs_page import render_inputs
from bending_page import render_bending
from shear_page import render_shear

from creep import render_creep
from shrinkage import render_shrinkage
from deflection import render_deflection
from crack_page import render_crack_control


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
                render_inputs()
            elif label == "Bending":
                render_bending()
            elif label == "Shear":
                render_shear()
            elif label == "Creep":
                render_creep()
            elif label == "Shrinkage":
                render_shrinkage()
            elif label == "Deflection":
                render_deflection()
            elif label == "Crack Control":
                render_crack_control()


if __name__ == "__main__":
    main()
