"""Smoke checks for extracted torsion prism diagram builders."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torsion_diagrams  # noqa: E402
from ui.diagrams import torsion_prism_diagram  # noqa: E402


def _check_fig(fig, *, prefix: str) -> list[str]:
    failures: list[str] = []
    try:
        if len(fig.axes) != 1:
            failures.append(f"{prefix}_axes_count_changed")
            return failures
        ax = fig.axes[0]
        if not hasattr(ax, "get_zlim"):
            failures.append(f"{prefix}_axis_not_3d")
        if len(ax.collections) < 1:
            failures.append(f"{prefix}_prism_collection_missing")
        if len(ax.lines) < 2:
            failures.append(f"{prefix}_crack_lines_missing")
        if ax.get_xlabel() != "Length (mm)":
            failures.append(f"{prefix}_x_label_changed")
        if ax.get_ylabel() != "Breadth (mm)":
            failures.append(f"{prefix}_y_label_changed")
        if ax.get_zlabel() != "Depth (mm)":
            failures.append(f"{prefix}_z_label_changed")
    finally:
        plt.close(fig)
    return failures


def main() -> int:
    failures: list[str] = []
    if torsion_diagrams.plot_torsion_prism_3d is not torsion_prism_diagram.plot_torsion_prism_3d:
        failures.append("legacy_plot_import_not_shared")
    if torsion_diagrams.draw_face_label_debug is not torsion_prism_diagram.draw_face_label_debug:
        failures.append("legacy_debug_import_not_shared")

    fig = torsion_diagrams.plot_torsion_prism_3d(
        L=3000.0,
        B=450.0,
        D=750.0,
        n_cracks=2,
        theta_multiplier=0.8,
    )
    failures.extend(_check_fig(fig, prefix="legacy"))

    fig_no_cracks = torsion_prism_diagram.plot_torsion_prism_3d(
        L=3000.0,
        B=450.0,
        D=750.0,
        show_cracks=False,
        show_corners=False,
    )
    try:
        if len(fig_no_cracks.axes) != 1:
            failures.append("module_no_cracks_axes_count_changed")
        elif len(fig_no_cracks.axes[0].lines) != 0:
            failures.append("module_no_cracks_lines_present")
    finally:
        plt.close(fig_no_cracks)

    if failures:
        print("DIAGRAM_TORSION_PRISM_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_TORSION_PRISM_SMOKE PASS")
    print("- torsion prism module builder and legacy wrappers verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
