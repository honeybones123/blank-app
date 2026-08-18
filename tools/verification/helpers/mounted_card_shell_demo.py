from __future__ import annotations

import streamlit as st

from engineering_page_sections.mounted_card_shell import render_mounted_card

st.set_page_config(layout="wide")
st.title("Mounted card shell probe")


def body() -> None:
    st.number_input("Width", min_value=100, max_value=2000, value=300, key="probe_width")
    st.number_input("Depth", min_value=100, max_value=3000, value=600, key="probe_depth")
    st.selectbox("Concrete", [32, 40, 50], key="probe_concrete")


render_mounted_card(
    st,
    label="Section & material    300 × 600 mm · 40 MPa",
    key="probe_section_material",
    render_body=body,
)
