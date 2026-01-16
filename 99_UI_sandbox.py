# 99_UI_sandbox.py
# ============================
# UI SANDBOX - Testing step expander behavior
# ============================

import streamlit as st
import plotly.graph_objects as go
from widgets_helpers import render_step, apply_step_expander_css

st.set_page_config(page_title="UI Sandbox", layout="wide")

st.title("UI Sandbox - Step Expander Test")

# Apply CSS for compact collapsed steps
apply_step_expander_css()

# Summary mode toggle
summary_mode = st.checkbox(
    "Summary mode (collapse all steps)", value=False, key="ui_sandbox__summary_mode"
)

st.markdown("---")

# Test step 1: With diagram
def render_step1_body():
    """Body function for step 1 - includes calcbox and diagram."""
    col_calc, col_fig = st.columns([2, 1])
    
    with col_calc:
        st.markdown("**Calculation:**")
        st.info("This is a test calculation box. In summary mode, this should be hidden.")
        st.markdown("""
        $$\\alpha_2 = 0.85 - 0.0015 f'_c$$
        
        Result: $\\alpha_2 = 0.790$
        """)
    
    with col_fig:
        # Simple test diagram
        fig = go.Figure()
        fig.add_bar(x=['A', 'B', 'C'], y=[1, 3, 2])
        fig.update_layout(height=300, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

render_step(
    step_id="sandbox_step1",
    title="Step 1.1 - Stress-block parameters (α₂ and γ)",
    summary_md="Result: α₂ = 0.790, γ = 0.850",
    body_fn=render_step1_body,
    summary_mode=summary_mode,
)

st.markdown("---")

# Test step 2: Without diagram
def render_step2_body():
    """Body function for step 2 - calcbox only."""
    st.markdown("**Calculation:**")
    st.info("This step has no diagram. It should still collapse properly in summary mode.")
    st.markdown("""
    $$C = \\alpha_2 f'_c b a$$
    
    Result: $C = 450.5$ kN
    """)

render_step(
    step_id="sandbox_step2",
    title="Step 1.2 - Concrete compressive force C",
    summary_md="Result: C = 450.5 kN",
    body_fn=render_step2_body,
    summary_mode=summary_mode,
)

