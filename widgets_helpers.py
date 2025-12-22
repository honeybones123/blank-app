import streamlit as st


def apply_global_widget_css():
    """Global styling for every page (remove +/- etc.)."""
    st.markdown(
        """
        <style>
        /* Hide browser spinner */
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button {
            -webkit-appearance: none !important;
            margin: 0 !important;
        }
        input[type=number] { -moz-appearance: textfield !important; }

        /* Hide Streamlit +/- buttons */
        div[data-testid="stNumberInput"] button {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            opacity: 0 !important;
        }

        /* Make input smaller */
        div[data-testid="stNumberInput"] input[type=number] {
            padding-top: 2px !important;
            padding-bottom: 2px !important;
            height: 2rem !important;
            font-size: 0.9rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
#  🔵 Calcbox – Global Blue Calculation Box Styling
# ------------------------------------------------------------
def apply_calcbox_css():
    """Apply global CSS for the blue calculation boxes (blockquote styling)."""
    st.markdown(
        """
<style>
/* Style blockquotes as blue calc boxes */
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 6px 6px 0 !important;
  color: #1a1a1a !important;
}
blockquote p, blockquote * {
  color: #1a1a1a !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def calcbox(md: str):
    """
    Render a blue calculation box with proper LaTeX support.
    """
    # Convert \[...\] to $$...$$ for display math
    converted = md.replace("\\[", "$$").replace("\\]", "$$")
    # Convert \(...\) to $...$ for inline math  
    converted = converted.replace("\\(", "$").replace("\\)", "$")
    
    # Convert to blockquote format - prefix each line with >
    lines = converted.strip().split("\n")
    blockquote = "\n".join("> " + line for line in lines)
    st.markdown(blockquote)



def number_row(label, key, step, sync_callbacks, *, width_ratio=(1.5, 1), help_text=None):
    """
    Renders: [ label ]  [ number input ]
    in a single row.

    - label: text on the left (Markdown)
    - key: widget key (must exist in TAB_KEYS)
    - step: number_input step
    - sync_callbacks: dict from get_sync_callbacks()
    - help_text: optional tooltip (shows as ? icon)
    """
    col_label, col_widget = st.columns(width_ratio)

    with col_label:
        st.markdown(label)

    with col_widget:
        st.number_input(
            "",
            key=key,
            step=step,
            label_visibility="collapsed",
            on_change=sync_callbacks[key],
            help=help_text,
        )


# ============================================================
# UNIVERSAL REINFORCEMENT MESSAGES
# ============================================================

def show_reo_message(
    message_type: str,
    *,
    layer: str = "Layer 1",
    s_min: float = None,
    show_extended: bool = False,
    **kwargs
):
    """
    Display standardized reinforcement layout messages across all pages.
    
    Args:
        message_type: One of:
            - "auto_layer2": Auto-layout triggered (Layer 1 doesn't fit → Layer 2 formed)
            - "layer2_overwritten": Layer 2 auto-updated due to Layer 1 changes
            - "spacing_clamped": Spacing was increased to meet minimum
            - "layout_invalid": Layout cannot fit even with multiple rows
            - "layer2_inactive": Layer 2 is empty (user cleared it)
            - "tight_spacing": Spacing barely meets minimum (teaching hint)
        layer: Which layer the message refers to ("Layer 1", "Layer 2", "Bottom Layer 1", etc.)
        s_min: Minimum spacing value (for spacing_clamped message)
        show_extended: If True, show extended message in expander/popover
        **kwargs: Additional parameters for message formatting
    
    Returns:
        None (displays message directly)
    """
    import streamlit as st
    
    messages = {
        "auto_layer2": {
            "level": "info",
            "widget": lambda layer_val: (
                f"**Auto layout:** Not all {layer_val} bars fit in a single row with minimum spacing. "
                f"Extra bars have been automatically moved to Layer 2."
            ),
            "extended": {
                "title": "Automatic Second Layer Created",
                "body": lambda layer_val: (
                    f"{layer_val} cannot fit across the beam width while maintaining the minimum clear spacing. "
                    f"The app has automatically placed the overflow bars into Layer 2.\n\n"
                    f"You may edit Layer 2 manually, but if {layer_val} changes in a way that forces "
                    f"another auto-layout, Layer 2 will be updated again."
                ),
            },
        },
        "layer2_overwritten": {
            "level": "info",
            "widget": lambda layer_val: (
                f"**Layer 2 has been updated automatically** based on the overflow from {layer_val}. "
                f"Your manual edits may be overwritten if {layer_val} reshuffles again."
            ),
            "extended": {
                "title": "Layer 2 Auto-Updated",
                "body": lambda layer_val: (
                    f"Changes to {layer_val} caused a new automatic layout. "
                    f"Layer 2 has been regenerated so the reinforcement remains physically consistent "
                    f"with minimum spacing rules and beam width."
                ),
            },
        },
        "spacing_clamped": {
            "level": "warning",
            "widget": lambda s_min_val: (
                f"**Adjusted spacing:** Entered spacing is less than the minimum allowed. "
                f"Using {s_min_val:.1f} mm for layout and calculations."
            ),
            "extended": {
                "title": "Minimum Spacing Applied",
                "body": lambda s_min_val: (
                    f"The entered spacing is smaller than the minimum clear spacing permitted by the "
                    f"bar diameter, cover and detailing rules.\n\n"
                    f"The app has increased the spacing to {s_min_val:.1f} mm to maintain a valid layout."
                ),
            },
        },
        "layout_invalid": {
            "level": "error",
            "widget": (
                f"**Invalid layout:** Reinforcement cannot fit within the beam width with minimum "
                f"spacing, even with multiple rows. Reduce bar size/count or increase beam width."
            ),
            "extended": {
                "title": "Reinforcement Layout Invalid",
                "body": (
                    f"The requested bars cannot be arranged within the available beam width while "
                    f"respecting minimum clear spacing and concrete cover.\n\n"
                    f"**Solutions:**\n"
                    f"- Increase beam width\n"
                    f"- Use fewer bars\n"
                    f"- Select smaller bar diameters\n\n"
                    f"Diagrams and calculations are not representative until the layout is valid."
                ),
            },
        },
        "layer2_inactive": {
            "level": "info",
            "widget": lambda layer_val: (
                f"**Layer 2 inactive:** No bars specified. Only {layer_val} contributes to reinforcement."
            ),
            "extended": None,
        },
        "tight_spacing": {
            "level": "info",
            "widget": (
                f"**Bars fit with spacing just above the minimum.** Check congestion and detailing."
            ),
            "extended": None,
        },
    }
    
    if message_type not in messages:
        st.warning(f"Unknown message type: {message_type}")
        return
    
    msg_config = messages[message_type]
    level = msg_config["level"]
    widget_text_raw = msg_config["widget"]
    extended = msg_config.get("extended")
    
    # Handle widget text - may be a string or a callable (for messages that need parameters)
    if callable(widget_text_raw):
        # For spacing_clamped, we need s_min
        if message_type == "spacing_clamped":
            if s_min is None:
                s_min = 25.0  # Default fallback
            widget_text = widget_text_raw(s_min)
        # For messages that need layer, pass layer parameter
        elif message_type in ["auto_layer2", "layer2_overwritten", "layer2_inactive"]:
            widget_text = widget_text_raw(layer)
        else:
            widget_text = widget_text_raw()
    else:
        widget_text = widget_text_raw
    
    # Display widget-level message
    if level == "info":
        st.info(widget_text)
    elif level == "warning":
        st.warning(widget_text)
    elif level == "error":
        st.error(widget_text)
    else:
        st.markdown(widget_text)
    
    # Display extended message if requested and available
    if show_extended and extended:
        title = extended.get("title", "Details")
        body_raw = extended.get("body")
        
        # Handle body - may be a string or a callable
        if callable(body_raw):
            if message_type == "spacing_clamped":
                if s_min is None:
                    s_min = 25.0  # Default fallback
                body = body_raw(s_min)
            elif message_type in ["auto_layer2", "layer2_overwritten"]:
                body = body_raw(layer)
            else:
                body = body_raw()
        else:
            body = body_raw
        
        if body:
            with st.expander(f"ℹ️ {title}", expanded=False):
                st.markdown(body)
