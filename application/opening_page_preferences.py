"""Preference ownership for the page used when a new beam design opens."""

from __future__ import annotations

from typing import Any

from application.user_preference_store import (
    clear_account_preference,
    load_account_preference,
    save_account_preference,
)


OPENING_PAGE_PREFERENCE_KEY = "beam_default_opening_page"
GUEST_STORAGE_KEY = "structuralbase.beam.defaultOpeningPage.v1"
ALLOWED_OPENING_PAGES = ("start", "inputs", "design")


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


__all__ = [
    "ALLOWED_OPENING_PAGES",
    "GUEST_STORAGE_KEY",
    "OPENING_PAGE_PREFERENCE_KEY",
    "clear_opening_page_preference",
    "load_opening_page_preference",
    "normalise_opening_page",
    "save_opening_page_preference",
]
