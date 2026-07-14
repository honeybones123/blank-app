"""Smoke checks for extracted torsion diagram builders."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shear_diagrams import (  # noqa: E402
    build_torsion_plotly_figure as legacy_build_torsion_plotly_figure,
    clamp_inside as legacy_clamp_inside,
    plot_shear_step1_theta_cracks_3d as legacy_plot_shear_step1_theta_cracks_3d,
    proj as legacy_proj,
)
from ui.diagrams.torsion_diagram import (  # noqa: E402
    build_torsion_plotly_figure,
    clamp_inside,
    plot_shear_step1_theta_cracks_3d,
    proj,
)


def _plotly_signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _check_utilities() -> list[str]:
    failures: list[str] = []
    point = np.array([1.0, 2.0, 3.0], dtype=float)
    if not np.allclose(proj(point), legacy_proj(point)):
        failures.append("proj_legacy_value_changed")
    if clamp_inside(0.0, 0.0, 1.0) != legacy_clamp_inside(0.0, 0.0, 1.0):
        failures.append("clamp_scalar_legacy_value_changed")
    clamped = clamp_inside(np.array([-1.0, 0.5, 2.0]), 0.0, 1.0)
    legacy_clamped = legacy_clamp_inside(np.array([-1.0, 0.5, 2.0]), 0.0, 1.0)
    if not np.allclose(clamped, legacy_clamped):
        failures.append("clamp_array_legacy_value_changed")
    return failures


def _check_plotly_torsion(required: bool) -> list[str]:
    kwargs = dict(
        torsion_design_required=required,
        L_mm=8000.0,
        b_mm=450.0,
        D_mm=750.0,
        theta_crack_deg=42.0,
    )
    module_fig = build_torsion_plotly_figure(**kwargs)
    legacy_fig = legacy_build_torsion_plotly_figure(**kwargs)
    failures: list[str] = []
    prefix = "plotly_required" if required else "plotly_not_required"
    if _plotly_signature(module_fig) != _plotly_signature(legacy_fig):
        failures.append(f"{prefix}_legacy_signature_changed")
    if len(module_fig.data) < (15 if required else 13):
        failures.append(f"{prefix}_expected_schematic_traces_missing")
    if "T" not in _annotation_text(module_fig):
        failures.append(f"{prefix}_torsion_annotation_missing")
    theta_trace_text = [
        item
        for trace in module_fig.data
        for item in (getattr(trace, "text", None) or [])
    ]
    if required and not any(str(item) == "\N{GREEK SMALL LETTER THETA}" for item in theta_trace_text):
        failures.append("plotly_required_theta_marker_missing")
    if module_fig.layout.xaxis.visible is not False:
        failures.append(f"{prefix}_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append(f"{prefix}_y_axis_visible")
    if module_fig.layout.hovermode is not False:
        failures.append(f"{prefix}_hovermode_changed")
    return failures


def _check_matplotlib_cracks() -> list[str]:
    kwargs = dict(
        L_mm=3000.0,
        b_mm=450.0,
        D_mm=750.0,
        theta_deg=35.0,
        n_cracks=2,
        start_t_span=0.05,
        show_cracks=True,
    )
    module_fig = plot_shear_step1_theta_cracks_3d(**kwargs)
    legacy_fig = legacy_plot_shear_step1_theta_cracks_3d(**kwargs)
    failures: list[str] = []
    try:
        if len(module_fig.axes) != len(legacy_fig.axes):
            failures.append("matplotlib_axes_count_changed")
        elif module_fig.axes:
            module_ax = module_fig.axes[0]
            legacy_ax = legacy_fig.axes[0]
            if len(module_ax.lines) != len(legacy_ax.lines):
                failures.append("matplotlib_line_count_changed")
            if len(module_ax.patches) != len(legacy_ax.patches):
                failures.append("matplotlib_patch_count_changed")
            if module_ax.get_aspect() != legacy_ax.get_aspect():
                failures.append("matplotlib_aspect_changed")
    finally:
        plt.close(module_fig)
        plt.close(legacy_fig)
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_utilities())
    failures.extend(_check_plotly_torsion(required=True))
    failures.extend(_check_plotly_torsion(required=False))
    failures.extend(_check_matplotlib_cracks())

    if failures:
        print("DIAGRAM_TORSION_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_TORSION_SMOKE PASS")
    print("- torsion Plotly builder and legacy wrapper verified")
    print("- theta-crack Matplotlib builder and legacy wrapper verified")
    print("- projection and clamp utility wrappers verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
