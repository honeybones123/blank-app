"""Fragment-scoped mounted card shell for light interactive page content.

This component deliberately does not use ``st.expander``. The body stays
mounted so Streamlit widget identity is preserved, while a fragment-local
header toggles only presentation state. Heavy diagrams/calculations should
remain lazy and must not use this shell.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Callable


def _safe_key(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value))


def _inject_shell_css(
    st_module: Any,
    *,
    shell_key: str,
    body_key: str,
    is_open: bool,
) -> None:
    display = "block" if is_open else "none"
    chevron = "⌃" if is_open else "⌄"
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
  padding: 0.65rem 2.7rem 0.65rem 1rem !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: #F3F5F7 !important;
  color: #10234A !important;
  box-shadow: none !important;
  font-size: 16px !important;
  line-height: 1.6 !important;
  font-weight: 600 !important;
  position: relative !important;
}}
.st-key-{shell_key} div[data-testid="stButton"] > button:hover {{
  background: #EDF1F4 !important;
  color: #10234A !important;
}}
.st-key-{shell_key} div[data-testid="stButton"] > button::after {{
  content: "{chevron}";
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 1rem;
  color: #536274;
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


class MountedCardRegion(AbstractContextManager):
    """Context-manager body for a mounted card.

    ``open`` is intentionally always true from Python's perspective: callers
    must continue executing the body even while it is visually closed so
    Streamlit widget identities remain mounted. Only CSS visibility changes.
    """

    open = True

    def __init__(self, body_container: Any) -> None:
        self._body_container = body_container

    def __enter__(self):
        return self._body_container.__enter__()

    def __exit__(self, *args):
        return self._body_container.__exit__(*args)

    def __getattr__(self, name: str):
        return getattr(self._body_container, name)


def mounted_card_region(
    st_module: Any,
    *,
    label: str,
    key: str,
    initially_open: bool = False,
) -> MountedCardRegion:
    """Create a one-step visual card while leaving its body externally writable.

    The header alone is fragment-scoped. On click, only the header fragment
    reruns and emits new visibility CSS. The sibling body container is not part
    of that fragment, so existing widgets mounted into it are not remounted.
    """

    safe = _safe_key(key)
    open_key = f"{safe}__open"
    shell_key = f"{safe}__shell"
    body_key = f"{safe}__body"

    if open_key not in st_module.session_state:
        st_module.session_state[open_key] = bool(initially_open)

    with st_module.container(key=shell_key, border=False):
        def _header_fragment() -> None:
            is_open = bool(st_module.session_state.get(open_key, False))
            _inject_shell_css(
                st_module,
                shell_key=shell_key,
                body_key=body_key,
                is_open=is_open,
            )
            if st_module.button(
                label,
                key=f"{safe}__toggle",
                use_container_width=True,
            ):
                st_module.session_state[open_key] = not is_open
                st_module.rerun(scope="fragment")

        st_module.fragment(_header_fragment)()
        body = st_module.container(key=body_key, border=False)

    return MountedCardRegion(body)


def render_mounted_card(
    st_module: Any,
    *,
    label: str,
    key: str,
    render_body: Callable[[], None],
    initially_open: bool = False,
) -> None:
    """Render one light card whose body remains mounted while visually closed."""

    region = mounted_card_region(
        st_module,
        label=label,
        key=key,
        initially_open=initially_open,
    )
    with region:
        render_body()


__all__ = ["MountedCardRegion", "mounted_card_region", "render_mounted_card"]
