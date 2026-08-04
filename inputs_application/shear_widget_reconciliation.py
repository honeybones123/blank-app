"""Typed shear-widget reconciliation for the Inputs auto-design entry."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, MutableMapping

from inputs_application.shear_state_normalization import (
    CANONICAL_NO_SHEAR_SPACING_MM,
    normalize_invalid_shear_state_updates,
)


@dataclass(frozen=True)
class ShearWidgetReconciliationRuntime:
    append_trace: Callable[..., Any]
    request_widget_seed: Callable[[str], Any]
    set_shared: Callable[..., Any]
    shared_state_snapshot: Callable[[], dict]


def reconcile_shear_widgets_with_shared(
    *,
    session_state: MutableMapping[str, Any],
    runtime: ShearWidgetReconciliationRuntime,
    debug_enabled: bool = False,
) -> list[str]:
    changed: list[str] = []
    probe: list[dict[str, object]] = []
    shared_before = runtime.shared_state_snapshot()
    specs = (
        ("inputs_lig_d", "lig_d", int, 0),
        ("inputs_lig_legs", "lig_legs", int, 0),
        ("inputs_s_lig", "s_lig", float, CANONICAL_NO_SHEAR_SPACING_MM),
    )
    pending: dict[str, object] = {}
    for widget_key, shared_key, caster, default in specs:
        if widget_key not in session_state:
            probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "missing_widget",
                }
            )
            continue
        raw = session_state.get(widget_key)
        try:
            widget_value = caster(raw if raw is not None else default)
        except (TypeError, ValueError):
            probe.append(
                {
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "status": "bad_widget_value",
                    "widget_value_raw": raw,
                }
            )
            continue
        try:
            shared_raw = shared_before.get(shared_key, default)
            shared_value = caster(
                shared_raw if shared_raw is not None else default
            )
        except (TypeError, ValueError):
            shared_value = caster(default)
        diff = float(widget_value) - float(shared_value)
        probe.append(
            {
                "widget_key": widget_key,
                "shared_key": shared_key,
                "widget_value": widget_value,
                "shared_value": shared_value,
                "diff": diff,
                "status": "equal" if abs(diff) <= 1e-9 else "diff",
            }
        )
        if abs(diff) > 1e-9:
            pending[shared_key] = widget_value
    source = "handle_auto_design:inputs_shear_reconcile"
    if pending:
        normalized = normalize_invalid_shear_state_updates(
            shared_before,
            pending,
            source=source,
            dev_mode=bool(session_state.get("_dev_mode")),
        )
        for shared_key, value in normalized.items():
            prior = shared_before.get(shared_key)
            try:
                same = (
                    abs(float(value) - float(prior)) <= 1e-9
                    if isinstance(value, (int, float))
                    and isinstance(prior, (int, float))
                    else value == prior
                )
            except Exception:
                same = value == prior
            if same:
                continue
            runtime.set_shared(shared_key, value, source=source)
            changed.append(shared_key)
        if changed:
            current = runtime.shared_state_snapshot()
            for shared_key, value in normalize_invalid_shear_state_updates(
                current,
                {},
                source=source,
                dev_mode=bool(session_state.get("_dev_mode")),
            ).items():
                runtime.set_shared(shared_key, value, source=source)
            runtime.request_widget_seed(source)
    if debug_enabled:
        try:
            runtime.append_trace(
                "inputs_shear_reconcile",
                {
                    "changed": list(changed),
                    "pending_updates": dict(pending),
                    "probe": probe,
                },
                run_id=f"isr_{int(time.time() * 1000)}",
                source="inputs_shear_reconcile",
            )
        except Exception:
            pass
    return changed


__all__ = [
    "ShearWidgetReconciliationRuntime",
    "reconcile_shear_widgets_with_shared",
]
