"""Widget reconciliation coordinators for the Inputs page."""

from __future__ import annotations

import time
from typing import Any


_WIDGET_RECONCILIATION_NAMES: tuple[str, ...] = (
    "CANONICAL_NO_SHEAR_SLIG_MM",
    "DEBUG_DESIGN_GUIDANCE_PROBE",
    "_append_design_guide_trace",
    "_design_action_widget_specs",
    "_normalise_invalid_shear_state_in_shared",
    "_normalise_invalid_shear_state_updates",
    "_refresh_canonical_shear_widgets",
    "_shared_state_snapshot",
    "_sync_design_action_widget_to_shared",
    "get_param",
    "set_shared",
)


def _bind_widget_reconciliation_globals(*, legacy_page: Any, st_module: Any) -> None:
    namespace = globals()
    namespace["st"] = st_module
    for name in _WIDGET_RECONCILIATION_NAMES:
        namespace[name] = getattr(legacy_page, name)


def reconcile_design_action_widgets_with_shared(
    legacy_page: Any,
    st_module: Any,
    selected_prefix: str,
) -> list[str]:
    _bind_widget_reconciliation_globals(legacy_page=legacy_page, st_module=st_module)
    return _reconcile_design_action_widgets_with_shared(selected_prefix)


def reconcile_inputs_shear_widgets_with_shared(
    legacy_page: Any,
    st_module: Any,
) -> list[str]:
    _bind_widget_reconciliation_globals(legacy_page=legacy_page, st_module=st_module)
    return _reconcile_inputs_shear_widgets_with_shared()


def _reconcile_design_action_widgets_with_shared(selected_prefix: str) -> list[str]:
    """Fallback sync for live edits when widget state drifted but on_change did not land."""
    changed: list[str] = []
    reconcile_probe: list[dict[str, object]] = []
    for spec in _design_action_widget_specs(selected_prefix):
        widget_key = str(spec["widget_key"])
        shared_key = str(spec["shared_key"])
        if widget_key not in st.session_state:
            reconcile_probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "missing_widget",
                }
            )
            continue
        try:
            widget_value = float(st.session_state.get(widget_key) or 0.0)
        except (TypeError, ValueError):
            reconcile_probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "bad_widget_value",
                    "widget_value_raw": st.session_state.get(widget_key),
                }
            )
            continue
        try:
            shared_value = float(get_param(shared_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            shared_value = 0.0
        reconcile_probe.append(
            {
                "widget_key": widget_key,
                "shared_key": shared_key,
                "widget_value": widget_value,
                "shared_value": shared_value,
                "diff": float(widget_value - shared_value),
                "status": "equal" if abs(widget_value - shared_value) <= 1e-9 else "diff",
            }
        )
        if abs(widget_value - shared_value) <= 1e-9:
            continue
        _sync_design_action_widget_to_shared(
            widget_key,
            shared_key,
            spec.get("proxy_key"),
        )
        changed.append(shared_key)
    if DEBUG_DESIGN_GUIDANCE_PROBE:
        try:
            _append_design_guide_trace(
                "design_action_reconcile",
                {
                    "selected_prefix": str(selected_prefix),
                    "changed": list(changed),
                    "probe": reconcile_probe,
                },
                run_id=f"dar_{int(time.time() * 1000)}",
                source="design_action_reconcile",
            )
        except Exception:
            pass
    return changed


def _reconcile_inputs_shear_widgets_with_shared() -> list[str]:
    """Fallback sync for visible Inputs-page shear widgets before one-click starts."""
    changed: list[str] = []
    reconcile_probe: list[dict[str, object]] = []
    shared_before = _shared_state_snapshot()
    widget_specs = (
        ("inputs_lig_d", "lig_d", int, 0),
        ("inputs_lig_legs", "lig_legs", int, 0),
        ("inputs_s_lig", "s_lig", float, float(CANONICAL_NO_SHEAR_SLIG_MM)),
    )
    pending_updates: dict[str, object] = {}
    for widget_key, shared_key, caster, default in widget_specs:
        if widget_key not in st.session_state:
            reconcile_probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "missing_widget",
                }
            )
            continue
        raw_widget_value = st.session_state.get(widget_key)
        try:
            widget_value = caster(raw_widget_value if raw_widget_value is not None else default)
        except (TypeError, ValueError):
            reconcile_probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "bad_widget_value",
                    "widget_value_raw": raw_widget_value,
                }
            )
            continue
        try:
            shared_value = caster(shared_before.get(shared_key, default) if shared_before.get(shared_key, default) is not None else default)
        except (TypeError, ValueError):
            shared_value = caster(default)
        diff = float(widget_value) - float(shared_value)
        reconcile_probe.append(
            {
                "widget_key": widget_key,
                "shared_key": shared_key,
                "widget_value": widget_value,
                "shared_value": shared_value,
                "diff": diff,
                "status": "equal" if abs(diff) <= 1e-9 else "diff",
            }
        )
        if abs(diff) <= 1e-9:
            continue
        pending_updates[shared_key] = widget_value
    if pending_updates:
        normalized_updates = _normalise_invalid_shear_state_updates(
            shared_before,
            pending_updates,
            source="handle_auto_design:inputs_shear_reconcile",
        )
        for shared_key, value in normalized_updates.items():
            try:
                prior_value = shared_before.get(shared_key)
                value_f = float(value) if isinstance(value, (int, float)) else value
                prior_f = float(prior_value) if isinstance(prior_value, (int, float)) else prior_value
                same = (
                    abs(value_f - prior_f) <= 1e-9
                    if isinstance(value_f, (int, float)) and isinstance(prior_f, (int, float))
                    else value_f == prior_f
                )
            except Exception:
                same = value == shared_before.get(shared_key)
            if same:
                continue
            set_shared(shared_key, value, source="handle_auto_design:inputs_shear_reconcile")
            changed.append(shared_key)
        if changed:
            _normalise_invalid_shear_state_in_shared(source="handle_auto_design:inputs_shear_reconcile")
            _refresh_canonical_shear_widgets(source="handle_auto_design:inputs_shear_reconcile")
    if DEBUG_DESIGN_GUIDANCE_PROBE:
        try:
            _append_design_guide_trace(
                "inputs_shear_reconcile",
                {
                    "changed": list(changed),
                    "pending_updates": dict(pending_updates),
                    "probe": reconcile_probe,
                },
                run_id=f"isr_{int(time.time() * 1000)}",
                source="inputs_shear_reconcile",
            )
        except Exception:
            pass
    return changed
