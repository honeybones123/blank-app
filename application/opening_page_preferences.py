"""Preference ownership for the page used when a new beam design opens."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components
import streamlit as st

from ui.streamlit_iframe import render_trusted_iframe

from application.user_preference_store import (
    clear_account_preference,
    load_account_preference,
    save_account_preference,
)


OPENING_PAGE_PREFERENCE_KEY = "beam_default_opening_page"
GUEST_STORAGE_KEY = "structuralbase.beam.defaultOpeningPage.v1"
ALLOWED_OPENING_PAGES = ("start", "inputs", "design")
_COMPONENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "streamlit_components"
    / "opening_page_preference"
)
_guest_preference_component = components.declare_component(
    "opening_page_preference",
    path=str(_COMPONENT_PATH),
)


def normalise_opening_page(value: Any) -> str:
    resolved = str(value or "").strip().lower()
    return resolved if resolved in ALLOWED_OPENING_PAGES else "start"


def load_opening_page_preference(*, user_id: str, session_state: Any) -> str:
    cached = session_state.get("_opening_page_account_preference")
    if cached in ALLOWED_OPENING_PAGES:
        return str(cached)
    value = normalise_opening_page(
        load_account_preference(user_id, OPENING_PAGE_PREFERENCE_KEY)
    )
    session_state["_opening_page_account_preference"] = value
    return value


def save_opening_page_preference(
    *,
    user_id: str,
    value: Any,
    remember: bool,
    session_state: Any,
):
    resolved = normalise_opening_page(value)
    session_state["_opening_page_preference"] = resolved
    if not remember:
        return None
    if str(user_id or "").strip():
        result = save_account_preference(
            str(user_id),
            OPENING_PAGE_PREFERENCE_KEY,
            resolved,
        )
        if result.saved:
            session_state["_opening_page_account_preference"] = resolved
        return result
    session_state["_opening_page_guest_storage_action"] = {
        "action": "write",
        "value": resolved,
    }
    return None


def clear_opening_page_preference(*, user_id: str, session_state: Any):
    session_state["_opening_page_preference"] = "start"
    session_state["start_default_opening_page_choice"] = "start"
    session_state.pop("_opening_page_account_preference", None)
    if str(user_id or "").strip():
        return clear_account_preference(str(user_id), OPENING_PAGE_PREFERENCE_KEY)
    session_state["_opening_page_guest_storage_action"] = {"action": "clear"}
    return None


def render_guest_preference_bootstrap() -> dict[str, Any] | None:
    """Read the guest preference into Streamlit without reloading the app."""
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
    render_trusted_iframe(st,
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
    "ALLOWED_OPENING_PAGES",
    "GUEST_STORAGE_KEY",
    "OPENING_PAGE_PREFERENCE_KEY",
    "clear_opening_page_preference",
    "load_opening_page_preference",
    "normalise_opening_page",
    "render_guest_preference_bootstrap",
    "render_pending_guest_preference_write",
    "save_opening_page_preference",
]
