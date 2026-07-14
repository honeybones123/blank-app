"""Smoke checks for extracted creep/shrinkage schematic builders."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shear_visuals import (  # noqa: E402
    build_creep_schematic_plotly as legacy_build_creep_schematic_plotly,
    build_shrinkage_schematic_plotly as legacy_build_shrinkage_schematic_plotly,
)
from ui.diagrams.creep_shrinkage_diagram import (  # noqa: E402
    build_creep_schematic_plotly,
    build_shrinkage_schematic_plotly,
)
import shrinkage  # noqa: E402


def _signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _check_shrinkage() -> list[str]:
    module_fig = build_shrinkage_schematic_plotly(width_px=880, height_px=360)
    legacy_fig = legacy_build_shrinkage_schematic_plotly(width_px=880, height_px=360)
    failures: list[str] = []
    annotations = _annotation_text(module_fig)
    for expected in ("Water loss", "Plastic", "Dry Thin", "Drying Shrinkage"):
        if not any(expected in text for text in annotations):
            failures.append(f"shrinkage_annotation_missing_{expected.replace(' ', '_')}")
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("shrinkage_legacy_signature_changed")
    if int(module_fig.layout.width or 0) != 880:
        failures.append("shrinkage_width_not_preserved")
    if int(module_fig.layout.height or 0) != 360:
        failures.append("shrinkage_height_not_preserved")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("shrinkage_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("shrinkage_y_axis_visible")
    return failures


def _check_creep() -> list[str]:
    module_fig = build_creep_schematic_plotly(width_px=880, height_px=360)
    legacy_fig = legacy_build_creep_schematic_plotly(width_px=880, height_px=360)
    failures: list[str] = []
    annotations = _annotation_text(module_fig)
    for expected in ("Sustained", "elastic strain", "creep strain", "Time-dependent"):
        if not any(expected in text for text in annotations):
            failures.append(f"creep_annotation_missing_{expected.replace(' ', '_')}")
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("creep_legacy_signature_changed")
    if int(module_fig.layout.width or 0) != 880:
        failures.append("creep_width_not_preserved")
    if int(module_fig.layout.height or 0) != 360:
        failures.append("creep_height_not_preserved")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("creep_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("creep_y_axis_visible")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_shrinkage())
    failures.extend(_check_creep())
    if shrinkage.build_shrinkage_schematic_plotly is not build_shrinkage_schematic_plotly:
        failures.append("shrinkage_page_not_using_shared_schematic_builder")

    if failures:
        print("DIAGRAM_CREEP_SHRINKAGE_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_CREEP_SHRINKAGE_SMOKE PASS")
    print("- shrinkage schematic module builder and legacy wrapper verified")
    print("- creep schematic module builder and legacy wrapper verified")
    print("- shrinkage page imports shared schematic builder directly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
