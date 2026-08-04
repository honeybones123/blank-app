"""Contracts for Inputs-page widget metadata.

This module documents existing widget metadata only. It must not render
Streamlit widgets, mutate session state, route Apply actions, or change widget
keys/callbacks.
"""

ALLOWED_WIDGET_GROUPS: tuple[str, ...] = (
    "top_level_design_mode",
    "design_actions_mode",
    "design_action_numbers",
    "geometry_basic",
    "materials_basic",
    "shear_reinforcement_basic",
    "bottom_longitudinal_reinforcement",
    "top_longitudinal_reinforcement",
    "serviceability_environment_basic",
    "support_deflection_basic",
    "shear_section_parameters_basic",
    "time_dependent_basic",
    "ducts_prestress_voids_basic",
    "crack_control_inputs_basic",
    "flange_reinforcement_basic",
    "flange_transverse_basic",
)

ALLOWED_WIDGET_KINDS: tuple[str, ...] = (
    "radio",
    "toggle",
    "number_input",
    "selectbox",
    "checkbox",
)

WIDGET_DISPLAY_HASH_FIELDS: tuple[str, ...] = (
    "widget_id",
    "group_id",
    "kind",
    "label",
    "widget_key",
    "shared_key",
    "callback_key",
    "help_text",
    "default",
    "options",
    "disabled",
)

OWNERSHIP_RULES: tuple[str, ...] = (
    "metadata_only",
    "do_not_import_streamlit",
    "do_not_mutate_session_state",
    "do_not_change_widget_keys",
    "do_not_execute_callbacks",
    "do_not_route_apply",
)
