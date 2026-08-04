"""Typed rerun classification and bounded telemetry for the Inputs workspace."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import time
from typing import Any, MutableMapping


class InputsWidgetRerunClass(StrEnum):
    DISPLAY_LOCAL = "display_local"
    ENGINEERING_WORKSPACE = "engineering_workspace"
    EXPLICIT_ACTION = "explicit_action"
    APP_NAVIGATION = "app_navigation"


DISPLAY_LOCAL_WIDGET_KEYS = frozenset(
    {
        "inputs_detailed_mode_toggle",
        "inputs_fast_mode_show_3d_toggle",
        "inputs_loads_edit_toggle",
    }
)

EXPLICIT_ACTION_WIDGET_KEYS = frozenset(
    {
        "inputs_apply_beam_reo_load_edits",
        "inputs_one_click_auto_design",
        "inputs_reset_workspace",
    }
)


@dataclass(frozen=True)
class InputsWorkspaceRefresh:
    widget_key: str
    rerun_class: InputsWidgetRerunClass
    revision: int
    requested_at_ns: int
    source: str = "inputs_widget_callback"


class InputsWorkspaceStore:
    """Typed boundary for the workspace refresh state kept in the session.

    The session remains the cross-page persistence mechanism, but callers no
    longer need to know the private key names used by the workspace protocol.
    """

    REVISION_KEY = "_inputs_workspace_revision"
    REFRESH_KEY = "_inputs_workspace_refresh"
    EVENTS_KEY = "_inputs_workspace_rerun_events"

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def current_revision(self) -> int:
        return int(self._state.get(self.REVISION_KEY, 0) or 0)

    def record_refresh(self, request: InputsWorkspaceRefresh) -> None:
        payload = asdict(request)
        payload["rerun_class"] = request.rerun_class.value
        self._state[self.REVISION_KEY] = int(request.revision)
        self._state[self.REFRESH_KEY] = payload
        events = list(self._state.get(self.EVENTS_KEY) or [])
        events.append(payload)
        self._state[self.EVENTS_KEY] = events[-100:]

    def latest_refresh(self) -> dict[str, Any] | None:
        value = self._state.get(self.REFRESH_KEY)
        return dict(value) if isinstance(value, dict) else None


def classify_inputs_widget(widget_key: str) -> InputsWidgetRerunClass:
    key = str(widget_key or "").strip()
    if key in DISPLAY_LOCAL_WIDGET_KEYS:
        return InputsWidgetRerunClass.DISPLAY_LOCAL
    if key in EXPLICIT_ACTION_WIDGET_KEYS:
        return InputsWidgetRerunClass.EXPLICIT_ACTION
    if key.startswith("inputs_"):
        return InputsWidgetRerunClass.ENGINEERING_WORKSPACE
    return InputsWidgetRerunClass.APP_NAVIGATION


def request_inputs_workspace_refresh(
    session_state: MutableMapping[str, Any],
    widget_key: str,
    *,
    revision: int | None = None,
) -> InputsWorkspaceRefresh | None:
    rerun_class = classify_inputs_widget(widget_key)
    if rerun_class is InputsWidgetRerunClass.DISPLAY_LOCAL:
        return None
    store = InputsWorkspaceStore(session_state)
    resolved_revision = (
        max(0, int(revision))
        if revision is not None
        else store.current_revision() + 1
    )
    request = InputsWorkspaceRefresh(
        widget_key=str(widget_key),
        rerun_class=rerun_class,
        revision=resolved_revision,
        requested_at_ns=time.perf_counter_ns(),
    )
    store.record_refresh(request)
    return request


__all__ = [
    "DISPLAY_LOCAL_WIDGET_KEYS",
    "EXPLICIT_ACTION_WIDGET_KEYS",
    "InputsWidgetRerunClass",
    "InputsWorkspaceStore",
    "InputsWorkspaceRefresh",
    "classify_inputs_widget",
    "request_inputs_workspace_refresh",
]
