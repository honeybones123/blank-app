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
    """Apply global CSS for the blue calculation boxes."""
    st.markdown(
        """
        <style>
        .calcbox {
            border-left: 4px solid #4a90e2;
            background-color: #f7faff;
            padding: 0.75rem 1rem;
            margin: 0.5rem 0 1rem 0;
            border-radius: 4px;
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def calcbox(md: str):
    """Render a blue calculation box using global CSS."""
    st.markdown(f"<div class='calcbox'>{md}</div>", unsafe_allow_html=True)



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
