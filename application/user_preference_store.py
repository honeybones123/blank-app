"""Account-scoped preference persistence through existing Supabase auth metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auth_bridge import get_supabase_admin


@dataclass(frozen=True)
class PreferenceWriteResult:
    saved: bool
    error: str | None = None


def _user_and_metadata(user_id: str) -> tuple[Any | None, dict[str, Any]]:
    resolved_user_id = str(user_id or "").strip()
    if not resolved_user_id:
        return None, {}
    client = get_supabase_admin()
    if client is None:
        return None, {}
    response = client.auth.admin.get_user_by_id(resolved_user_id)
    user = getattr(response, "user", None)
    if user is None and isinstance(response, dict):
        user = response.get("user")
    metadata = getattr(user, "user_metadata", None)
    if metadata is None and isinstance(user, dict):
        metadata = user.get("user_metadata")
    return client, dict(metadata or {})


def load_account_preference(user_id: str, key: str) -> Any:
    try:
        _, metadata = _user_and_metadata(user_id)
        return metadata.get(str(key))
    except Exception:
        return None


def save_account_preference(user_id: str, key: str, value: Any) -> PreferenceWriteResult:
    try:
        client, metadata = _user_and_metadata(user_id)
        if client is None:
            return PreferenceWriteResult(False, "Account preference storage is unavailable.")
        metadata[str(key)] = value
        client.auth.admin.update_user_by_id(
            str(user_id),
            {"user_metadata": metadata},
        )
        return PreferenceWriteResult(True)
    except Exception as exc:
        return PreferenceWriteResult(False, str(exc))


def clear_account_preference(user_id: str, key: str) -> PreferenceWriteResult:
    try:
        client, metadata = _user_and_metadata(user_id)
        if client is None:
            return PreferenceWriteResult(False, "Account preference storage is unavailable.")
        metadata.pop(str(key), None)
        client.auth.admin.update_user_by_id(
            str(user_id),
            {"user_metadata": metadata},
        )
        return PreferenceWriteResult(True)
    except Exception as exc:
        return PreferenceWriteResult(False, str(exc))


__all__ = [
    "PreferenceWriteResult",
    "clear_account_preference",
    "load_account_preference",
    "save_account_preference",
]
