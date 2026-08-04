"""Smoke checks for extracted shear zone spacing strip diagrams."""

from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shear_zone_spacing import (  # noqa: E402
    build_zone_spacing_strip_figure as legacy_build_zone_spacing_strip_figure,
    compute_zoned_shear_spacing,
)
from ui.diagrams.shear_zone_spacing_diagram import build_zone_spacing_strip_figure  # noqa: E402


def _signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def main() -> int:
    design = compute_zoned_shear_spacing(
        L_m=6.0,
        d_mm=690.0,
        D_mm=750.0,
        d_v_mm=650.0,
        b_v_mm=420.0,
        fc_mpa=40.0,
        f_syv_mpa=500.0,
        V_eq_kN=280.0,
        Vuc_kN=120.0,
        theta_v_rad=math.radians(35.0),
        Asv_mm2=240.0,
        lig_d_mm=10.0,
        legs=3,
        is_cantilever=False,
    )
    if design is None:
        print("DIAGRAM_SHEAR_ZONE_SPACING_SMOKE FAIL")
        print("- design_not_computed")
        return 1

    kwargs = dict(beam_depth_m=0.75, title="Spacing zones")
    module_fig = build_zone_spacing_strip_figure(design, **kwargs)
    legacy_fig = legacy_build_zone_spacing_strip_figure(design, **kwargs)

    failures: list[str] = []
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("zone_spacing_legacy_signature_changed")
    if len(module_fig.layout.shapes or []) != len(design.segments):
        failures.append("zone_spacing_segment_shapes_missing")
    if len(module_fig.data) != 1:
        failures.append("zone_spacing_axis_trace_changed")
    if int(module_fig.layout.height or 0) != 140:
        failures.append("zone_spacing_height_not_preserved")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("zone_spacing_y_axis_visible")
    if not any("s =" in text for text in _annotation_text(module_fig)):
        failures.append("zone_spacing_annotation_missing")

    if failures:
        print("DIAGRAM_SHEAR_ZONE_SPACING_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_SHEAR_ZONE_SPACING_SMOKE PASS")
    print("- zone spacing strip module builder and legacy wrapper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
