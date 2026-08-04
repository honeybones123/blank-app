from __future__ import annotations

import json
import streamlit as st

from section_props.schema import SHAPES, get_default_dims
from section_props.validate import validate_dims
from section_props.shapes import compute_section_properties
from section_props.plot import plot_shape
from widgets_helpers import render_plotly_diagram


st.set_page_config(page_title="Section Properties Playground", layout="wide")

st.title("Section Properties Playground")
st.caption("Standalone sandbox for generic section properties. Build here first, then integrate into StructuralBase.")

colL, colR = st.columns([0.45, 0.55], gap="large")

with colL:
    st.subheader("Inputs")

    shape_name = st.selectbox("Shape", list(SHAPES.keys()))

    # init / reset defaults for shape
    if "dims" not in st.session_state or st.session_state.get("shape_name") != shape_name:
        st.session_state.shape_name = shape_name
        st.session_state.dims = get_default_dims(shape_name)

    dims = dict(st.session_state.dims)

    # dynamic dimension widgets
    for dim in SHAPES[shape_name]:
        dims[dim.key] = st.number_input(
            dim.label + f" ({dim.unit})",
            min_value=float(dim.min_value),
            value=float(dims.get(dim.key, dim.default)),
            step=1.0,
            help=dim.help,
            key=f"dim_{shape_name}_{dim.key}",
        )

    st.session_state.dims = dims

    st.divider()
    st.subheader("Reo overlay (match app rules)")

    show_reo = st.checkbox("Show reo layout on diagram", value=False)
    reo = None

    if show_reo:
        r1, r2, r3 = st.columns(3, gap="medium")
        with r1:
            cover_top = st.number_input("Cover top (mm)", min_value=0.0, value=40.0, step=1.0)
            cover_bot = st.number_input("Cover bot (mm)", min_value=0.0, value=40.0, step=1.0)
            cover_side = st.number_input("Cover side (mm)", min_value=0.0, value=40.0, step=1.0)
        with r2:
            n_top = st.number_input("Top bars n_top", min_value=0, value=2, step=1)
            db_top = st.number_input("Top bar dia db_top (mm)", min_value=1.0, value=16.0, step=1.0)
            n_bot = st.number_input("Bottom bars n_bot", min_value=0, value=4, step=1)
            db_bot = st.number_input("Bottom bar dia db_bot (mm)", min_value=1.0, value=20.0, step=1.0)
            lig_d = st.number_input("Link Ø lig_d (mm)", min_value=0.0, value=10.0, step=1.0)
            lig_legs = st.number_input("No. of legs lig_legs", min_value=0, value=2, step=1)
        with r3:
            s_min = st.number_input("Min clear spacing (mm)", min_value=0.0, value=20.0, step=1.0)
            rowgap_top = st.number_input("Row gap top (mm)", min_value=0.0, value=60.0, step=1.0)
            rowgap_bot = st.number_input("Row gap bot (mm)", min_value=0.0, value=60.0, step=1.0)

        reo = {
            "cover_top": cover_top,
            "cover_bot": cover_bot,
            "cover_side": cover_side,
            "n_top": int(n_top),
            "db_top": float(db_top),
            "n_bot": int(n_bot),
            "db_bot": float(db_bot),
            "lig_d": float(lig_d),
            "lig_legs": int(lig_legs),
            "s_min": float(s_min),
            "rowgap_top": float(rowgap_top),
            "rowgap_bot": float(rowgap_bot),
        }

    ok, errors = validate_dims(shape_name, dims)
    if not ok:
        st.error("Fix inputs:\n\n- " + "\n- ".join(errors))

    st.divider()
    st.subheader("Export")
    export_obj = {"shape": shape_name, "dims_mm": dims}
    export_json = json.dumps(export_obj, indent=2)
    st.code(export_json, language="json")
    st.download_button(
        "Download JSON",
        data=export_json.encode("utf-8"),
        file_name="section_inputs.json",
        mime="application/json",
        disabled=not ok,
    )

with colR:
    st.subheader("Diagram + Properties")

    fig = plot_shape(shape_name, dims, reo=reo)
    render_plotly_diagram(
        fig,
        key="section_props_playground_diagram",
        title="Section properties diagram",
        config={"displayModeBar": False},
    )

    if ok:
        props = compute_section_properties(shape_name, dims)

        # Display nicely
        st.markdown("### Section properties (about centroid, strong axis Ixx)")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.metric("Area A (mm²)", f"{props['A']:,.0f}")
            st.metric("Centroid ȳ from top (mm)", f"{props['ybar_top']:,.1f}")
        with c2:
            st.metric("Ixx (mm⁴)", f"{props['Ixx']:,.0f}")
            st.metric("Ztop (mm³)", f"{props['Ztop']:,.0f}")

        st.metric("Zbot (mm³)", f"{props['Zbot']:,.0f}")

        st.divider()
        st.subheader("Properties JSON (for later integration)")
        out_obj = {"shape": shape_name, "dims_mm": dims, "props_mm": props}
        out_json = json.dumps(out_obj, indent=2)
        st.code(out_json, language="json")
        st.download_button(
            "Download properties JSON",
            data=out_json.encode("utf-8"),
            file_name="section_properties.json",
            mime="application/json",
        )
    else:
        st.info("Enter valid dimensions to compute properties.")
