"""Fragment-scoped mounted card shell for light interactive page content.

This component deliberately does not use ``st.expander``.  Its body stays
mounted so Streamlit widget identity is preserved, while a fragment-local
button toggles only presentation state.  It is intended for small, stable
interactive card bodies; heavy diagrams/calculations should remain lazy.
"""

from __future__ import annotations

from typing import Any, Callable


def _safe_key(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value))


def _inject_shell_css(st_module: Any, *, shell_key: str, body_key: str, is_open: bool) -> None:
    display = "block" if is_open else "none"
    st_module.markdown(
        f"""
<style>
.st-key-{shell_key} {{
  margin: 0.55rem 0 !important;
  border: 1px solid #D4DAE1 !important;
  border-radius: 8px !important;
  overflow: hidden !important;
  background: #F3F5F7 !important;
}}
.st-key-{shell_key} div[data-testid="stButton"] {{ margin: 0 !important; }}
.st-key-{shell_key} div[data-testid="stButton"] > button {{
  width: 100% !important;
  min-height: 58px !important;
  justify-content: flex-start !important;
  text-align: left !important;
  padding: 0.65rem 1rem !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: #F3F5F7 !important;
  color: #10234A !important;
  box-shadow: none !important;
  font-size: 16px !important;
  line-height: 1.6 !important;
  font-weight: 600 !important;
}}
.st-key-{shell_key} div[data-testid="stButton"] > button:hover {{
  background: #EDF1F4 !important;
  color: #10234A !important;
}}
.st-key-{body_key} {{
  display: {display} !important;
  padding: 0.9rem 1rem 1rem !important;
  box-sizing: border-box !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def render_mounted_card(
    st_module: Any,
    *,
    label: str,
    key: str,
    render_body: Callable[[], None],
    initially_open: bool = False,
) -> None:
    """Render one light card whose body remains mounted while visually closed.

    The toggle is fragment-scoped.  Clicking it reruns only this card fragment,
    not the calculation page.  The body callback is always executed so widget
    keys remain mounted and cannot be cleaned up merely because the card closes.
    """

    safe = _safe_key(key)
    open_key = f"{safe}__open"
    shell_key = f"{safe}__shell"
    body_key = f"{safe}__body"

    if open_key not in st_module.session_state:
        st_module.session_state[open_key] = bool(initially_open)

    def _card_fragment() -> None:
        is_open = bool(st_module.session_state.get(open_key, False))
        _inject_shell_css(
            st_module,
            shell_key=shell_key,
            body_key=body_key,
            is_open=is_open,
        )
        with st_module.container(key=shell_key, border=False):
            if st_module.button(
                label,
                key=f"{safe}__toggle",
                use_container_width=True,
            ):
                st_module.session_state[open_key] = not is_open
                st_module.rerun(scope="fragment")
            with st_module.container(key=body_key, border=False):
                render_body()

    st_module.fragment(_card_fragment)()


__all__ = ["render_mounted_card"]
