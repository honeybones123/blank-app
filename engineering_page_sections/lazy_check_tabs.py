"""Shared lazy check-tab selector for detailed engineering result pages.

The selector deliberately owns presentation only.  The calling page retains
all calculation, state, and rendering authority and renders exactly one
selected check group beneath it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def render_lazy_check_tab_selector(
    st_module: Any,
    *,
    labels: Sequence[str],
    key: str,
    aria_label: str,
    anchor_id: str,
) -> str:
    """Render the shared compact tab row and return the selected label."""

    options = tuple(str(label) for label in labels)
    if not options:
        raise ValueError("labels must contain at least one check tab")
    current = str(st_module.session_state.get(key) or options[0])
    if current not in options:
        st_module.session_state[key] = options[0]

    st_module.markdown(
        f"""
<style>
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #{anchor_id}) div[role="radiogroup"] {{
    gap: 1rem !important;
    border-bottom: 1px solid rgba(49, 51, 63, 0.18) !important;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #{anchor_id}) div[role="radiogroup"] > label {{
    background: transparent !important;
    border: 0 !important;
    border-radius: 0 !important;
    padding: 0.3rem 0 0.45rem !important;
    margin: 0 !important;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #{anchor_id}) div[role="radiogroup"] > label:has(input:checked) {{
    color: #ff4b4b !important;
    border-bottom: 2px solid #ff4b4b !important;
    font-weight: 600 !important;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #{anchor_id}) div[role="radiogroup"] > label:hover {{
    background: transparent !important;
}}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] #{anchor_id}) div[role="radiogroup"] > label * {{
    margin: 0 !important;
    padding: 0 !important;
}}
</style>
<div id="{anchor_id}" style="height:0;line-height:0;font-size:0;margin:0;padding:0;" aria-hidden="true"></div>
""",
        unsafe_allow_html=True,
    )
    return str(
        st_module.radio(
            aria_label,
            options=options,
            horizontal=True,
            key=key,
            label_visibility="collapsed",
        )
    )


__all__ = ["render_lazy_check_tab_selector"]
