"""Smoke checks for extracted Check 10 shear zone layout strip diagrams."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shear_core import (  # noqa: E402
    build_shear_zone_layout_strip_figure as legacy_build_shear_zone_layout_strip_figure,
)
from ui.diagrams.shear_zone_layout_diagram import build_shear_zone_layout_strip_figure  # noqa: E402


def _payload() -> dict:
    return {
        "beam_length_mm": 6000.0,
        "support_type": "Simply supported",
        "is_cantilever": False,
        "support_positions_mm": [0.0, 6000.0],
        "support_types": ["Pinned", "Roller"],
        "strip_segments_mm": [
            {"x0_mm": 0.0, "x1_mm": 1200.0, "spacing_mm": 100.0, "zone": "1", "color": "rgba(200,45,45,0.55)"},
            {"x0_mm": 1200.0, "x1_mm": 4800.0, "spacing_mm": 175.0, "zone": "2", "color": "rgba(255,152,0,0.50)"},
            {"x0_mm": 4800.0, "x1_mm": 6000.0, "spacing_mm": 100.0, "zone": "1", "color": "rgba(200,45,45,0.55)"},
        ],
    }


def _signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _check_payload() -> list[str]:
    kwargs = dict(beam_depth_m=0.75, title="Check 10 layout", reference_width_px=800.0)
    module_fig = build_shear_zone_layout_strip_figure(_payload(), **kwargs)
    legacy_fig = legacy_build_shear_zone_layout_strip_figure(_payload(), **kwargs)
    failures: list[str] = []
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("zone_layout_legacy_signature_changed")
    if len(module_fig.layout.shapes or []) < 6:
        failures.append("zone_layout_zone_or_stirrup_shapes_missing")
    if len(module_fig.data) != 1:
        failures.append("zone_layout_axis_trace_changed")
    if int(module_fig.layout.height or 0) != 140:
        failures.append("zone_layout_height_not_preserved")
    annotations = _annotation_text(module_fig)
    if not any("req. @" in text for text in annotations):
        failures.append("zone_layout_spacing_annotation_missing")
    if "\u25b2" not in annotations or "\u25cb" not in annotations:
        failures.append("zone_layout_support_annotation_missing")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("zone_layout_y_axis_visible")
    return failures


def _check_empty_payload() -> list[str]:
    payload = {"beam_length_mm": 5000.0, "strip_segments_mm": []}
    module_fig = build_shear_zone_layout_strip_figure(payload)
    legacy_fig = legacy_build_shear_zone_layout_strip_figure(payload)
    failures: list[str] = []
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("empty_zone_layout_legacy_signature_changed")
    if not any("No shear link spacing set" in text for text in _annotation_text(module_fig)):
        failures.append("empty_zone_layout_message_missing")
    if int(module_fig.layout.height or 0) != 140:
        failures.append("empty_zone_layout_height_not_preserved")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_payload())
    failures.extend(_check_empty_payload())

    if failures:
        print("DIAGRAM_SHEAR_ZONE_LAYOUT_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_SHEAR_ZONE_LAYOUT_SMOKE PASS")
    print("- Check 10 zone layout strip module builder and legacy wrapper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
