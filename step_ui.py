"""
Shared step UI rendering module.
Provides expandable step rendering with session state management.

This file centralises layout only. Do not embed design logic or page-specific thresholds here.
Coloring, status mapping, and calcbox formatting should use existing shared helpers from widgets_helpers.
"""
import streamlit as st
from widgets_helpers import (
    apply_step_summary_expander_css,
    calcbox,
    status_to_class,
)


def init_step_ui_state(page_key: str):
    """Initialize session state for step expansion tracking.
    This is a no-op placeholder for compatibility. Actual state is managed via step_open_{step_id} keys.
    """
    pass  # State is managed per-step via step_open_{step_id} keys (matches step_expander_calcbox pattern)


def toggle_step(page_key: str, step_id: str):
    """Toggle the expansion state of a step.
    Uses the same key pattern as step_expander_calcbox: step_open_{step_id}
    """
    open_key = f"step_open_{step_id}"
    current = st.session_state.get(open_key, False)
    st.session_state[open_key] = not current


def is_expanded(page_key: str, step_id: str) -> bool:
    """Check if a step is currently expanded.
    Uses the same key pattern as step_expander_calcbox: step_open_{step_id}
    """
    open_key = f"step_open_{step_id}"
    return st.session_state.get(open_key, False)


def render_expandable_step(
    *,
    page_key: str,
    step_id: str,
    title: str,
    summary_md: str,
    status_label: str = "",
    status_kind: str | None = None,  # "pass"|"warn"|"fail"|None -> maps to step-pass/step-fail/step-neutral
    util: float | None = None,
    calc_md: str | None = None,
    diagram_render_fn=None,
    table_render_fn=None,
    info_render_fn=None,
    cols_ratio=(0.62, 0.38),
    tight=True,
    anchor_id: str | None = None,  # Optional anchor ID to add before calcbox
):
    """
    Render an expandable step with calcbox formatting.
    Matches the behavior of step_expander_calcbox from widgets_helpers.
    
    Args:
        page_key: Unique key for the page (e.g., "shear")
        step_id: Unique identifier for this step (e.g., "step1")
        title: Step title (not used in label, kept for compatibility)
        summary_md: Summary text shown in collapsed header (formatted as expander label)
        status_label: Status text (e.g., "PASS", "FAIL", "OK", "Check") - for display only
        status_kind: Status type ("pass", "fail", "warn", or None) - determines color
        util: Utilisation ratio (optional, for display)
        calc_md: Markdown for the calcbox content (rendered when expanded)
        diagram_render_fn: Callable to render diagram (rendered when expanded, on right)
        table_render_fn: Callable to render table (rendered when expanded, below calc)
        info_render_fn: Callable to render additional info (rendered when expanded, before calc)
        cols_ratio: Ratio for calc/diagram columns (default 0.62/0.38, matches bending's 2.0/1.0)
        tight: If True, minimize spacing between collapsed steps
    """
    apply_step_summary_expander_css()
    
    # Anchor for scrolling with deterministic marker
    st.markdown(f"<div id='calc_{step_id}'></div>", unsafe_allow_html=True)
    # Marker that JS uses to find the next expander
    st.markdown(f"<div data-calc-uid='{step_id}'></div>", unsafe_allow_html=True)
    
    # Use session state key pattern: step_open_{step_id} (matches step_expander_calcbox)
    open_key = f"step_open_{step_id}"
    is_expanded_state = st.session_state.get(open_key, False)
    
    # Determine status class
    status_class = status_to_class(status_kind)
    
    # Build expander label
    info_tip = ""
    if info_render_fn:
        info_tip = " ℹ️"
    
    # Format summary line - support both string and list/tuple for 2-line summaries
    if isinstance(summary_md, (list, tuple)):
        # Multiple lines: join with line breaks
        formatted_summary = "  \n".join(str(line) for line in summary_md)
    else:
        # Single string: replace " | " with line break if present (backward compatible)
        formatted_summary = summary_md.replace(" | ", "  \n", 1)
    label = f"{formatted_summary}{info_tip}".strip()
    
    with st.expander(label, expanded=is_expanded_state):
        # Inner target for flash highlight
        st.markdown(f"<div id='inner_{step_id}'>", unsafe_allow_html=True)
        st.markdown(f"<span class='{status_class}'></span>", unsafe_allow_html=True)
        
        # Info render function (if provided, e.g., popover) - rendered before calc
        if info_render_fn:
            info_render_fn()
        
        # Render content (always render, but Streamlit will collapse/expand based on expander state)
        if diagram_render_fn and calc_md:
            # Two-column layout: calc left, diagram right (matches step_expander_calcbox pattern)
            col_calc, col_fig = st.columns([2.0, 1.0], gap="large")
            with col_calc:
                # Add anchor before calcbox if provided
                if anchor_id:
                    st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
                calcbox(calc_md, status=status_kind, uid=f"{step_id}__details")
                # Table below calc (if provided)
                if table_render_fn:
                    table_render_fn()
            with col_fig:
                pad, plot = st.columns([0.10, 0.90], gap="small")
                with plot:
                    diagram_render_fn()
        elif calc_md:
            # Single column: calc only
            # Add anchor before calcbox if provided
            if anchor_id:
                st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
            calcbox(calc_md, status=status_kind, uid=f"{step_id}__details")
            if table_render_fn:
                table_render_fn()
        elif diagram_render_fn:
            # Diagram only (unusual but supported)
            diagram_render_fn()
            if table_render_fn:
                table_render_fn()
        
        # Close inner div for flash highlight
        st.markdown("</div>", unsafe_allow_html=True)

