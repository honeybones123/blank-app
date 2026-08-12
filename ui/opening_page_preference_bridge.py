"""Streamlit bridge for guest opening-page preference persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

from application.opening_page_preferences import (
    ALLOWED_OPENING_PAGES,
    GUEST_STORAGE_KEY,
    normalise_opening_page,
)


_COMPONENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "streamlit_components"
    / "opening_page_preference"
)
_guest_preference_component = components.declare_component(
    "opening_page_preference",
    path=str(_COMPONENT_PATH),
)


def render_guest_preference_bootstrap() -> dict[str, Any] | None:
    value = _guest_preference_component(
        storage_key=GUEST_STORAGE_KEY,
        allowed=list(ALLOWED_OPENING_PAGES),
        key="guest_opening_page_preference_bridge",
        default=None,
    )
    return dict(value) if isinstance(value, dict) else None


def render_pending_guest_preference_write(session_state: Any) -> None:
    action = session_state.pop("_opening_page_guest_storage_action", None)
    if not isinstance(action, dict):
        return
    storage_key = json.dumps(GUEST_STORAGE_KEY)
    action_name = str(action.get("action") or "")
    if action_name == "write":
        value = json.dumps(normalise_opening_page(action.get("value")))
        statement = (
            f"parentWindow.localStorage.setItem({storage_key}, {value});"
            f"const url = new URL(parentWindow.location.href);"
            f"url.searchParams.set('opening_page_pref', {value});"
            f"parentWindow.history.replaceState({{}}, '', url.toString());"
        )
    else:
        statement = (
            f"parentWindow.localStorage.removeItem({storage_key});"
            f"const url = new URL(parentWindow.location.href);"
            f"url.searchParams.delete('opening_page_pref');"
            f"parentWindow.history.replaceState({{}}, '', url.toString());"
        )
    components.html(
        f"""
<script>
(() => {{
  try {{
    const parentWindow = window.parent;
    {statement}
  }} catch (error) {{}}
}})();
</script>
""",
        height=0,
    )


__all__ = [
    "render_guest_preference_bootstrap",
    "render_pending_guest_preference_write",
]
