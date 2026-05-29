"""
Shared step UI rendering module.
Provides expandable step rendering with session state management.

This file centralises layout only. Do not embed design logic or page-specific thresholds here.
Coloring, status mapping, and calcbox formatting should use existing shared helpers from widgets_helpers.
"""
import streamlit as st
import re
from widgets_helpers import (
    apply_step_summary_expander_css,
    calcbox,
    status_to_class,
)


def _has_non_empty_card_text(value) -> bool:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"[*_`$\\{}]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text) >= 3


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
    calc_render_fn=None,
    diagram_render_fn=None,
    table_render_fn=None,
    info_render_fn=None,
    cols_ratio=(0.62, 0.38),
    tight=True,
    anchor_id: str | None = None,  # Optional anchor ID to add before calcbox
    diagram_above_calc: bool = False,
    diagram_outside_expander: bool = False,
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
        calc_render_fn: Optional callable; when set, called instead of ``calcbox(calc_md)`` (use with ``calc_md=None``).
        diagram_render_fn: Callable to render diagram (rendered when expanded, on right)
        table_render_fn: Callable to render table (rendered when expanded, below calc)
        info_render_fn: Callable to render additional info (rendered when expanded, before calc)
        cols_ratio: Ratio for calc/diagram columns (default 0.62/0.38, matches bending's 2.0/1.0)
        tight: If True, minimize spacing between collapsed steps
        diagram_above_calc: If True, diagram is full-width directly above calcbox (no side column).
            The info popover, if any, renders after the calcbox so it does not sit between diagram and calc.
        diagram_outside_expander: If True, diagram renders above the entire expander (outside the green
            calc box). Inside the expander: calcbox only (plus info after calc, anchor, table). Incompatible
            with placing the diagram in the right-hand column; use with diagram_above_calc=False or True
            (inside layout uses vertical stack without re-drawing the diagram).
    """
    has_any_content = bool(
        _has_non_empty_card_text(title)
        or _has_non_empty_card_text(summary_md)
        or _has_non_empty_card_text(calc_md)
        or calc_render_fn
        or diagram_render_fn
        or table_render_fn
        or info_render_fn
    )
    if not has_any_content:
        return
    apply_step_summary_expander_css()
    # Anchors in one block (avoids an extra element-container / vertical gap before the expander)
    st.markdown(
        f"<div id='calc_{step_id}' style='height:0;margin:0;padding:0;line-height:0;font-size:0;overflow:hidden;' aria-hidden='true'></div>"
        f"<div data-calc-uid='{step_id}' style='height:0;margin:0;padding:0;line-height:0;font-size:0;overflow:hidden;' aria-hidden='true'></div>",
        unsafe_allow_html=True,
    )
    
    # Use session state key pattern: step_open_{step_id} (matches step_expander_calcbox)
    open_key = f"step_open_{step_id}"
    is_expanded_state = st.session_state.get(open_key, False)
    
    # Determine status class
    status_class = status_to_class(status_kind)
    
    # Build expander label
    info_tip = ""
    if info_render_fn:
        info_tip = " ℹ️"
    
    def _bold_first_summary_line(line: str) -> str:
        txt = str(line or "").strip()
        if not txt:
            return txt
        if txt.startswith("**") and txt.endswith("**"):
            return txt
        return f"**{txt}**"

    # Format summary line - support both string and list/tuple for 2-line summaries
    if isinstance(summary_md, (list, tuple)):
        # Multiple lines: bold only the first (check line), keep the rest unchanged.
        lines = [str(line) for line in summary_md]
        if lines:
            lines[0] = _bold_first_summary_line(lines[0])
        formatted_summary = "  \n".join(lines)
    else:
        # Single string: replace " | " with line break if present (backward compatible)
        single = str(summary_md or "")
        if " | " in single:
            first, rest = single.split(" | ", 1)
            formatted_summary = f"{_bold_first_summary_line(first)}  \n{rest}"
        else:
            formatted_summary = _bold_first_summary_line(single)
    if not _has_non_empty_card_text(formatted_summary):
        formatted_summary = _bold_first_summary_line(title or "Calculation details")
    label = f"{formatted_summary}{info_tip}".strip()

    if diagram_outside_expander and diagram_render_fn:
        diagram_render_fn()
    
    with st.expander(label, expanded=is_expanded_state):
        # Inner target for flash highlight
        st.markdown(f"<div id='inner_{step_id}'>", unsafe_allow_html=True)
        st.markdown(f"<span class='{status_class}'></span>", unsafe_allow_html=True)
        
        # Vertical calc stack: diagram either inside (above calcbox) or already drawn outside expander.
        _has_calc = bool(calc_md or calc_render_fn)
        diagram_full_above_calc = bool(
            diagram_above_calc
            and diagram_render_fn
            and _has_calc
            and not diagram_outside_expander
        )
        diagram_calc_inside_vertical = bool(
            diagram_outside_expander and diagram_render_fn and _has_calc
        )
        if info_render_fn and not diagram_full_above_calc and not diagram_calc_inside_vertical:
            info_render_fn()
        
        # Render content (always render, but Streamlit will collapse/expand based on expander state)
        if diagram_calc_inside_vertical:
            if anchor_id:
                st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
            if calc_render_fn:
                calc_render_fn()
            else:
                calcbox(calc_md, status=status_kind, uid=f"{step_id}__details")
            if table_render_fn:
                table_render_fn()
            if info_render_fn:
                info_render_fn()
        elif diagram_full_above_calc:
            diagram_render_fn()
            if anchor_id:
                st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
            if calc_render_fn:
                calc_render_fn()
            else:
                calcbox(calc_md, status=status_kind, uid=f"{step_id}__details")
            if table_render_fn:
                table_render_fn()
            if info_render_fn:
                info_render_fn()
        elif diagram_render_fn and _has_calc:
            # Two-column layout: calc left, diagram right (matches step_expander_calcbox pattern)
            col_calc, col_fig = st.columns([2.0, 1.0], gap="large")
            with col_calc:
                # Add anchor before calcbox if provided
                if anchor_id:
                    st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
                if calc_render_fn:
                    calc_render_fn()
                else:
                    calcbox(calc_md, status=status_kind, uid=f"{step_id}__details")
                # Table below calc (if provided)
                if table_render_fn:
                    table_render_fn()
            with col_fig:
                pad, plot = st.columns([0.10, 0.90], gap="small")
                with plot:
                    diagram_render_fn()
        elif _has_calc:
            # Single column: calc only
            # Add anchor before calcbox if provided
            if anchor_id:
                st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
            if calc_render_fn:
                calc_render_fn()
            else:
                calcbox(calc_md, status=status_kind, uid=f"{step_id}__details")
            if table_render_fn:
                table_render_fn()
        elif diagram_render_fn and not diagram_outside_expander:
            # Diagram only (unusual but supported)
            diagram_render_fn()
            if table_render_fn:
                table_render_fn()
        
        # Close inner div for flash highlight
        st.markdown("</div>", unsafe_allow_html=True)
