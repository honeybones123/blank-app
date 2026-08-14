"""Inputs-page diagram extraction contracts."""

CARDINAL_DIAGRAMS = ("section_2d", "beam_3d")

SECTION_2D_HASH_FIELDS = (
    "shape_name",
    "dims",
    "reo",
    "show_shear",
    "show_dn",
    "dn",
    "tension_face",
    "fallback_cover_side",
    "fallback_cover_top",
    "fallback_cover_bot",
    "validation_errors",
)

BEAM_3D_HASH_FIELDS = (
    "shape_name",
    "shape_key",
    "outline_points",
    "b_box",
    "D",
    "L_plot",
    "fallback_width",
    "cover_bot",
    "cover_top",
    "cover_side",
    "lig_d",
    "lig_legs",
    "s_lig",
    "reo_layout",
    "cage",
    "resolved_bars",
    "validation_errors",
)

OWNERSHIP_RULES = {
    "engineering_calculation": "outside_inputs_page_modules.diagrams",
    "streamlit_rendering": "inputs_page.py",
    "session_state": "inputs_page.py",
    "figure_request_models": "inputs_page_modules.diagrams",
    "plotly_figure_builders": "ui.diagrams and section_props",
}
