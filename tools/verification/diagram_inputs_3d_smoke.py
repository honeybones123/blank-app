"""Smoke checks for extracted Inputs-page 3D beam diagram builder."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.diagrams.inputs_3d_diagram import build_inputs_beam_3d_figure  # noqa: E402


def _sample_kwargs() -> dict:
    return {
        "shape_name": "Rectangle (b - D)",
        "shape_key": "RECT",
        "outline_points": [(0.0, 0.0), (450.0, 0.0), (450.0, 750.0), (0.0, 750.0), (0.0, 0.0)],
        "b_box": 450.0,
        "D": 750.0,
        "L_plot": 1200.0,
        "fallback_width": 450.0,
        "cover_bot": 50.0,
        "cover_top": 40.0,
        "cover_side": 45.0,
        "lig_d": 10.0,
        "lig_legs": 3,
        "s_lig": 200.0,
        "reo_layout": {
            "bottom": [{"x": [120.0, 210.0, 300.0, 390.0], "y": 690.0, "db": 20.0}],
            "top": [{"x": [160.0, 290.0], "y": 60.0, "db": 16.0}],
        },
        "cage": {"x0": 45.0, "x1": 405.0, "y0": 45.0, "y1": 695.0},
    }


def main() -> int:
    fig = build_inputs_beam_3d_figure(**_sample_kwargs())
    failures: list[str] = []
    trace_types = [str(getattr(trace, "type", "") or "") for trace in fig.data]
    trace_names = [str(getattr(trace, "name", "") or "") for trace in fig.data]

    if "mesh3d" not in trace_types:
        failures.append("concrete_mesh_missing")
    if trace_names.count("Reo") < 6:
        failures.append("reo_traces_missing")
    if trace_types.count("scatter3d") < 12:
        failures.append("outline_or_stirrup_traces_missing")
    if int(fig.layout.scene.xaxis.range[1]) != 1200:
        failures.append("x_range_not_preserved")
    if int(fig.layout.scene.yaxis.range[1]) != 450:
        failures.append("y_range_not_preserved")
    if list(fig.layout.scene.zaxis.range) != [750.0, 0.0]:
        failures.append("z_depth_axis_not_reversed")
    if fig.layout.scene.xaxis.visible is not False:
        failures.append("x_axis_visible")
    if fig.layout.scene.yaxis.visible is not False:
        failures.append("y_axis_visible")
    if fig.layout.scene.zaxis.visible is not False:
        failures.append("z_axis_visible")
    if fig.layout.scene.bgcolor != "rgba(0,0,0,0)":
        failures.append("scene_background_not_transparent")
    if fig.layout.showlegend is not False:
        failures.append("showlegend_changed")

    if failures:
        print("DIAGRAM_INPUTS_3D_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_INPUTS_3D_SMOKE PASS")
    print("- Inputs 3D module builder verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
