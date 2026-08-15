import streamlit as st

from inputs_application.action_source_control import (
    INPUTS_ACTION_SOURCE_TOGGLE_KEY,
    render_action_source_toggle,
)


render_action_source_toggle(
    st,
    widget_key=INPUTS_ACTION_SOURCE_TOGGLE_KEY,
)
