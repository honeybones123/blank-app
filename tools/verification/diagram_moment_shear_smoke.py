"""Smoke checks for extracted moment/shear action diagram builders."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sfd_bmd_page import (  # noqa: E402
    _add_plotly_support_markers_aligned as legacy_add_plotly_support_markers_aligned,
    _figure_bmd_from_state as legacy_figure_bmd_from_state,
    _figure_sfd_from_state as legacy_figure_sfd_from_state,
    plot_load_diagram_plotly as legacy_plot_load_diagram_plotly,
    plot_section_locator_plotly as legacy_plot_section_locator_plotly,
)
from ui.diagrams.moment_shear_diagram import (  # noqa: E402
    _add_plotly_support_markers_aligned,
    figure_bmd_from_state,
    figure_sfd_from_state,
    plot_load_diagram_plotly,
    plot_section_locator_plotly,
)


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _figure_signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _check_load_diagram() -> list[str]:
    kwargs = dict(
        case="Simple beam – UDL over entire span",
        L=6.0,
        params={"w": 12.5},
        preview_x_m=2.0,
        design_x_m=4.0,
        support_condition="Simply supported",
    )
    module_fig = plot_load_diagram_plotly(**kwargs)
    legacy_fig = legacy_plot_load_diagram_plotly(**kwargs)
    annotations = _annotation_text(module_fig)
    failures: list[str] = []
    if _figure_signature(module_fig) != _figure_signature(legacy_fig):
        failures.append("load_legacy_signature_changed")
    if len(module_fig.data) < 3:
        failures.append("load_expected_beam_supports_and_udl_traces")
    if not any("w =" in text for text in annotations):
        failures.append("load_udl_label_missing")
    if module_fig.layout.xaxis.showgrid is not False:
        failures.append("load_x_grid_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("load_y_axis_visible")
    if int(module_fig.layout.height or 0) != 170:
        failures.append("load_height_not_preserved")
    return failures


def _check_section_locator() -> list[str]:
    kwargs = dict(L=6.0, preview_x_m=2.25, design_x_m=4.5)
    module_fig = plot_section_locator_plotly(**kwargs)
    legacy_fig = legacy_plot_section_locator_plotly(**kwargs)
    failures: list[str] = []
    if _figure_signature(module_fig) != _figure_signature(legacy_fig):
        failures.append("locator_legacy_signature_changed")
    if len(module_fig.data) < 2:
        failures.append("locator_line_or_preview_marker_missing")
    marker_text = []
    for trace in module_fig.data:
        marker_text.extend([str(item) for item in (getattr(trace, "text", None) or [])])
    if "2.25" not in marker_text:
        failures.append("locator_preview_text_missing")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("locator_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("locator_y_axis_visible")
    if int(module_fig.layout.height or 0) != 70:
        failures.append("locator_height_not_preserved")
    return failures


def _check_support_markers() -> list[str]:
    kwargs = dict(
        support_positions_plot=[0.0, 6.0],
        support_types_plot=["pinned", "roller"],
        y_min=-50.0,
        y_max=75.0,
        L=6.0,
        support_type_fallback="simply_supported",
    )
    module_fig = go.Figure()
    legacy_fig = go.Figure()
    _add_plotly_support_markers_aligned(module_fig, **kwargs)
    legacy_add_plotly_support_markers_aligned(legacy_fig, **kwargs)
    failures: list[str] = []
    if _figure_signature(module_fig) != _figure_signature(legacy_fig):
        failures.append("support_marker_legacy_signature_changed")
    if len(module_fig.data) < 2:
        failures.append("support_marker_pinned_or_roller_trace_missing")
    marker_symbols = [
        str(getattr(getattr(trace, "marker", None), "symbol", "") or "")
        for trace in module_fig.data
    ]
    if "triangle-up" not in marker_symbols:
        failures.append("support_marker_triangle_missing")
    if "circle" not in marker_symbols:
        failures.append("support_marker_roller_circle_missing")
    return failures


def _sample_sfd_bmd_state() -> dict:
    return {
        "L": 6.0,
        "case": "Simple beam - smoke",
        "x_plot": [0.0, 2.0, 4.0, 6.0],
        "V_plot": [18.0, 6.0, -6.0, -18.0],
        "M_plot": [0.0, 24.0, 24.0, 0.0],
        "support_positions_plot": [0.0, 6.0],
        "support_types_plot": ["pinned", "roller"],
        "preview_x_m": 2.0,
        "design_x_m": 4.0,
        "preview_V": 6.0,
        "preview_M": 24.0,
        "x_pad": 0.48,
        "support_type": "simply_supported",
        "design_mode_active": True,
        "zone_limit_m": 0.35,
        "d_v_mm": 235.0,
        "critical_shear_x": 0.25,
        "critical_shear_V": 17.0,
        "shear_spacing_end_mm": 150.0,
        "shear_spacing_mid_mm": 250.0,
    }


def _check_sfd_bmd_figures() -> list[str]:
    state = _sample_sfd_bmd_state()
    module_sfd = figure_sfd_from_state(state)
    legacy_sfd = legacy_figure_sfd_from_state(state)
    module_bmd = figure_bmd_from_state(state, show_m_peak=True)
    legacy_bmd = legacy_figure_bmd_from_state(state, show_m_peak=True)
    failures: list[str] = []

    if _figure_signature(module_sfd) != _figure_signature(legacy_sfd):
        failures.append("sfd_legacy_signature_changed")
    if _figure_signature(module_bmd) != _figure_signature(legacy_bmd):
        failures.append("bmd_legacy_signature_changed")
    if int(module_sfd.layout.height or 0) != 300:
        failures.append("sfd_height_not_preserved")
    if int(module_bmd.layout.height or 0) != 300:
        failures.append("bmd_height_not_preserved")
    sfd_names = [str(getattr(trace, "name", "") or "") for trace in module_sfd.data]
    bmd_names = [str(getattr(trace, "name", "") or "") for trace in module_bmd.data]
    if "V(x)" not in sfd_names:
        failures.append("sfd_trace_missing")
    if "Critical shear" not in sfd_names:
        failures.append("sfd_critical_shear_trace_missing")
    if "M(x)" not in bmd_names:
        failures.append("bmd_trace_missing")
    if not any("governing s = 150 mm" in text for text in _annotation_text(module_sfd)):
        failures.append("sfd_spacing_annotation_missing")
    bmd_text = []
    for trace in module_bmd.data:
        bmd_text.extend([str(item) for item in (getattr(trace, "text", None) or [])])
    if not any("|M|max" in text for text in bmd_text):
        failures.append("bmd_peak_marker_missing")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_load_diagram())
    failures.extend(_check_section_locator())
    failures.extend(_check_support_markers())
    failures.extend(_check_sfd_bmd_figures())

    if failures:
        print("DIAGRAM_MOMENT_SHEAR_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_MOMENT_SHEAR_SMOKE PASS")
    print("- load diagram module builder and legacy wrapper verified")
    print("- section locator module builder and legacy wrapper verified")
    print("- support marker helper and legacy wrapper verified")
    print("- SFD/BMD prepared-state builders and legacy wrappers verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
