"""Import smoke for shared diagram modules and legacy diagram wrappers."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.disable(logging.WARNING)

UI_DIAGRAMS_DIR = ROOT / "ui" / "diagrams"

LEGACY_WRAPPER_MODULES = [
    "bending_diagrams",
    "bending_side_view_diagram",
    "crack_side_view_diagram",
    "curved_beam_diagram",
    "deflection",
    "sfd_bmd_page",
    "shear_diagrams",
    "shear_visuals",
    "torsion_diagrams",
]

PAGE_RENDER_TOKENS = (
    "st.plotly_chart",
    "st.pyplot",
    "st.columns",
    "st.tabs",
    "components.html",
)


def _ui_diagram_module_names() -> list[str]:
    names: list[str] = []
    for path in sorted(UI_DIAGRAMS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        names.append(f"ui.diagrams.{path.stem}")
    return names


def _check_ui_diagram_imports() -> list[str]:
    failures: list[str] = []
    for module_name in _ui_diagram_module_names():
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"ui_diagram_import_failed:{module_name}:{type(exc).__name__}:{exc}")
    return failures


def _check_legacy_wrapper_imports() -> list[str]:
    failures: list[str] = []
    for module_name in LEGACY_WRAPPER_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"legacy_wrapper_import_failed:{module_name}:{type(exc).__name__}:{exc}")
    return failures


def _check_no_page_render_calls_in_ui_diagrams() -> list[str]:
    failures: list[str] = []
    for path in sorted(UI_DIAGRAMS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        for token in PAGE_RENDER_TOKENS:
            if token in text:
                failures.append(f"ui_diagram_page_render_token:{path.name}:{token}")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_ui_diagram_imports())
    failures.extend(_check_legacy_wrapper_imports())
    failures.extend(_check_no_page_render_calls_in_ui_diagrams())

    if failures:
        print("DIAGRAM_ALL_IMPORTS_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_ALL_IMPORTS_SMOKE PASS")
    print(f"- ui.diagrams modules imported: {len(_ui_diagram_module_names())}")
    print(f"- legacy diagram wrappers imported: {len(LEGACY_WRAPPER_MODULES)}")
    print("- shared diagram modules remain free of page render calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
