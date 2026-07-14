"""Smoke checks for extracted crack-page moment diagram builder."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.disable(logging.WARNING)

from crack_side_view_diagram import (  # noqa: E402
    build_crack_moment_diagram_figure as legacy_build_crack_moment_diagram_figure,
)
from ui.diagrams.crack_moment_diagram import build_crack_moment_diagram_figure  # noqa: E402


def _figure_signature(fig) -> tuple[int, int, int, int, str]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
        int(fig.layout.height or 0),
        str(fig.layout.uirevision),
    )


def _sample_kwargs() -> dict:
    return {
        "x_values": [0.0, 1.5, 3.0, 4.5, 6.0],
        "moment_values": [0.4, 18.0, 25.0, 16.0, -0.3],
        "L": 6.0,
        "support_positions": [0.0, 6.0],
        "support_types": ["pinned", "roller"],
        "support_type_fallback": "simply_supported",
    }


def main() -> int:
    kwargs = _sample_kwargs()
    module_fig = build_crack_moment_diagram_figure(**kwargs)
    legacy_fig = legacy_build_crack_moment_diagram_figure(**kwargs)
    failures: list[str] = []

    if _figure_signature(module_fig) != _figure_signature(legacy_fig):
        failures.append("legacy_module_signature_mismatch")
    if int(module_fig.layout.height or 0) != 260:
        failures.append("height_not_preserved")
    if str(module_fig.layout.uirevision) != "crack_diagram_suite_v2":
        failures.append("uirevision_not_preserved")
    if module_fig.layout.xaxis.title.text != "x (m)":
        failures.append("x_axis_title_changed")
    if module_fig.layout.xaxis.zeroline is not False:
        failures.append("x_axis_zeroline_visible")
    if module_fig.layout.yaxis.zeroline is not False:
        failures.append("y_axis_zeroline_visible")

    names = [str(getattr(trace, "name", "") or "") for trace in module_fig.data]
    if len(module_fig.data) < 5:
        failures.append("baseline_moment_peak_or_support_traces_missing")
    moment_trace = module_fig.data[1]
    moment_y = [float(v) for v in list(moment_trace.y)]
    moment_custom = [float(v) for v in list(moment_trace.customdata)]
    if moment_y[2] >= 0.0:
        failures.append("sagging_not_drawn_below_baseline")
    if abs(moment_custom[0]) > 1e-9 or abs(moment_custom[-1]) > 1e-9:
        failures.append("small_end_moments_not_cleaned_to_zero")
    peak_trace = module_fig.data[2]
    if "Peak |M|" not in str(getattr(peak_trace, "hovertemplate", "") or ""):
        failures.append("peak_hover_missing")
    marker_symbols = [
        str(getattr(getattr(trace, "marker", None), "symbol", "") or "")
        for trace in module_fig.data
    ]
    if "triangle-up" not in marker_symbols:
        failures.append("support_triangle_missing")
    if "circle" not in marker_symbols:
        failures.append("support_roller_missing")
    if names != [str(getattr(trace, "name", "") or "") for trace in legacy_fig.data]:
        failures.append("trace_name_order_mismatch")

    if failures:
        print("DIAGRAM_CRACK_MOMENT_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_CRACK_MOMENT_SMOKE PASS")
    print("- crack moment module builder and legacy wrapper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
