"""Pure projection of the current Inputs widget snapshot into engineering state."""

from __future__ import annotations

from typing import Any, Mapping


def merge_current_engineering_widget_state(
    resolved_state: Mapping[str, Any] | None,
    widget_state: Mapping[str, Any] | None,
    input_tab_keys: Mapping[str, str],
    *,
    shared_only_mode: bool = False,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Return a state snapshot aligned with the current widget edit.

    Normal reruns use widget values because Streamlit callbacks and the shared
    state write can be separated by the fragment/page boundary.  Apply and
    reseed reruns pass ``shared_only_mode=True`` so a stale widget cannot
    overwrite the newly committed engineering state.
    """
    result = dict(resolved_state or {})
    if shared_only_mode:
        return result, ()

    widgets = widget_state or {}
    applied: list[str] = []
    for shared_key, widget_key in dict(input_tab_keys or {}).items():
        if shared_key not in result or widget_key not in widgets:
            continue
        value = widgets.get(widget_key)
        if value is None:
            continue
        if result.get(shared_key) != value:
            result[shared_key] = value
            applied.append(str(shared_key))
    return result, tuple(sorted(applied))


__all__ = ["merge_current_engineering_widget_state"]
