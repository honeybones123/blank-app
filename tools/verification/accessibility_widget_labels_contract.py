"""Inventory every Runtime route for empty interactive widget labels."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[2]
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
WIDGET_TYPES = (
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


def _empty_labels(app: AppTest) -> list[tuple[str, str, str]]:
    failures: list[tuple[str, str, str]] = []
    for widget_type in WIDGET_TYPES:
        widgets = getattr(app, widget_type)
        for widget in widgets:
            label = getattr(widget, "label", None)
            if label is not None and not str(label).strip():
                failures.append(
                    (
                        widget_type,
                        str(getattr(widget, "key", "") or "<no-key>"),
                        repr(label),
                    )
                )
    return failures


def verify_all_routes_have_accessible_widget_labels() -> None:
    failures: dict[str, list[tuple[str, str, str]]] = {}
    for route in ROUTES:
        app = AppTest.from_file(
            str(REPO_ROOT / "app.py"),
            default_timeout=120,
        )
        app.run(timeout=120)
        if route != "Start":
            app.radio[0].set_value(route).run(timeout=120)
        assert not app.exception, [item.message for item in app.exception]
        route_failures = _empty_labels(app)
        if route_failures:
            failures[route] = route_failures
    assert not failures, failures


def main() -> None:
    verify_all_routes_have_accessible_widget_labels()
    print("accessibility widget-label contract: PASS")


if __name__ == "__main__":
    main()
