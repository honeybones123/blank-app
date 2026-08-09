"""Exercise every discoverable Runtime control in an isolated route session."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
ROUTES = (
    "Start",
    "Beam Inputs",
    "Load Analysis",
    "Bending",
    "Shear",
    "Creep",
    "Shrinkage",
    "Crack Control",
    "Deflection",
)
CONTROL_TYPES = (
    "button",
    "number_input",
    "selectbox",
    "radio",
    "checkbox",
    "toggle",
    "text_input",
    "text_area",
    "multiselect",
    "date_input",
    "time_input",
    "slider",
)


@dataclass(frozen=True, slots=True)
class Control:
    route: str
    kind: str
    index: int
    key: str | None
    disabled: bool


def _open(route: str) -> AppTest:
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    app.run(timeout=120)
    if route != "Start":
        app.radio[0].set_value(route).run(timeout=120)
    assert not app.exception, [item.message for item in app.exception]
    return app


def _disabled(widget: Any) -> bool:
    return bool(getattr(getattr(widget, "proto", None), "disabled", False))


def _inventory(route: str) -> list[Control]:
    app = _open(route)
    controls: list[Control] = []
    for kind in CONTROL_TYPES:
        for index, widget in enumerate(getattr(app, kind)):
            controls.append(
                Control(
                    route=route,
                    kind=kind,
                    index=index,
                    key=getattr(widget, "key", None),
                    disabled=_disabled(widget),
                )
            )
    return controls


def _locate(app: AppTest, control: Control):
    widgets = getattr(app, control.kind)
    if control.key is not None:
        matches = [widget for widget in widgets if getattr(widget, "key", None) == control.key]
        assert len(matches) == 1, f"{control.route}/{control.kind}/{control.key}: missing or duplicate"
        return matches[0]
    assert control.index < len(widgets), f"{control.route}/{control.kind}[{control.index}]: missing"
    return widgets[control.index]


def _alternate_option(widget: Any) -> Any:
    options = list(widget.options)
    assert options
    current = widget.value
    current_index = getattr(widget, "index", None)
    if isinstance(current_index, int):
        return options[(current_index + 1) % len(options)]
    for option in options:
        if option != current:
            return option
    return options[0]


def _exercise(widget: Any, kind: str) -> None:
    if kind == "button":
        widget.click().run(timeout=120)
    elif kind == "number_input":
        current = float(widget.value)
        protocol = widget.proto
        step = float(getattr(protocol, "step", 1.0) or 1.0)
        maximum = float(getattr(protocol, "max", float("inf")))
        minimum = float(getattr(protocol, "min", float("-inf")))
        candidate = current + step if current + step <= maximum else current - step
        candidate = max(minimum, min(maximum, candidate))
        widget.set_value(candidate).run(timeout=120)
    elif kind == "selectbox":
        widget.select(_alternate_option(widget)).run(timeout=120)
    elif kind == "radio":
        if widget.key == "nav_page_slug":
            return
        widget.set_value(_alternate_option(widget)).run(timeout=120)
    elif kind in {"checkbox", "toggle"}:
        widget.set_value(not bool(widget.value)).run(timeout=120)
    elif kind in {"text_input", "text_area"}:
        widget.set_value(f"{widget.value or ''} audit".strip()).run(timeout=120)
    elif kind == "multiselect":
        options = list(widget.options)
        current = list(widget.value or [])
        candidate = [] if current else options[:1]
        widget.set_value(candidate).run(timeout=120)
    elif kind in {"date_input", "time_input"}:
        widget.set_value(widget.value).run(timeout=120)
    elif kind == "slider":
        widget.set_value(widget.value).run(timeout=120)
    else:
        raise AssertionError(f"unsupported control type {kind}")


def verify_runtime_control_sweep() -> Counter[str]:
    inventories = {route: _inventory(route) for route in ROUTES}
    counts: Counter[str] = Counter()
    failures: list[str] = []

    for route, controls in inventories.items():
        for control in controls:
            if control.disabled:
                counts[f"{control.kind}:disabled"] += 1
                continue
            if control.kind == "radio" and control.key == "nav_page_slug":
                counts["radio:navigation"] += 1
                continue
            try:
                app = _open(route)
                widget = _locate(app, control)
                _exercise(widget, control.kind)
                if app.exception:
                    raise AssertionError([item.message for item in app.exception])
            except Exception as exc:
                failures.append(
                    f"{route}/{control.kind}/{control.key or control.index}: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                counts[f"{control.kind}:exercised"] += 1

    assert not failures, "\n".join(failures)
    assert sum(counts.values()) == sum(len(items) for items in inventories.values())
    assert counts["button:exercised"] > 0
    assert counts["number_input:exercised"] > 0
    assert counts["selectbox:exercised"] > 0
    return counts


def main() -> None:
    counts = verify_runtime_control_sweep()
    details = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    print(f"Runtime control sweep contract: PASS ({sum(counts.values())} controls; {details})")


if __name__ == "__main__":
    main()
