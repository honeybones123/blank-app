"""Smoke checks for extracted ULS stress-block diagram builders."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.disable(logging.WARNING)

import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from bending_diagrams import (  # noqa: E402
    _inject_figure_into_subplot as legacy_inject_figure_into_subplot,
    _plot_strain_profile as legacy_plot_strain_profile,
    _plot_stress_strain_profiles as legacy_plot_stress_strain_profiles,
    _plot_material_stress_strain_curves as legacy_plot_material_stress_strain_curves,
    _make_uls_force_model_figure as legacy_make_uls_force_model_figure,
    _make_sls_stress_block_figure as legacy_make_sls_stress_block_figure,
    _make_uls_stress_block_figure as legacy_make_uls_stress_block_figure,
)
from ui.diagrams.stress_strain_diagram import (  # noqa: E402
    inject_figure_into_subplot,
    make_material_stress_strain_curves_figure,
    make_sls_32_stress_block_figure,
    make_sls_strain_distribution_figure,
    make_sls_stress_block_figure,
    make_uls_force_model_figure,
    make_uls_stress_block_figure,
    plot_strain_profile,
    plot_stress_strain_profiles,
)


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _figure_signature(fig) -> tuple[int, int, int]:
    shapes = list(fig.layout.shapes or [])
    annotations = list(fig.layout.annotations or [])
    return (len(fig.data), len(shapes), len(annotations))


def _make_injection_child() -> go.Figure:
    child = go.Figure()
    child.add_trace(go.Scatter(x=[0, 1], y=[1, 2], mode="lines", name="child-line"))
    child.add_shape(type="line", x0=0, y0=0, x1=1, y1=1)
    child.add_annotation(x=0.5, y=0.5, text="child-note", showarrow=False)
    return child


def _check_injected_subplot(fig, *, prefix: str, expected_xref: str, expected_yref: str) -> list[str]:
    failures: list[str] = []
    if _figure_signature(fig) != (1, 1, 1):
        failures.append(f"{prefix}_signature_changed")
    shapes = list(fig.layout.shapes or [])
    annotations = list(fig.layout.annotations or [])
    if not shapes or getattr(shapes[0], "xref", "") != expected_xref:
        failures.append(f"{prefix}_shape_xref_changed")
    if not shapes or getattr(shapes[0], "yref", "") != expected_yref:
        failures.append(f"{prefix}_shape_yref_changed")
    if not annotations or getattr(annotations[0], "xref", "") != expected_xref:
        failures.append(f"{prefix}_annotation_xref_changed")
    if not annotations or getattr(annotations[0], "yref", "") != expected_yref:
        failures.append(f"{prefix}_annotation_yref_changed")
    if fig.data and getattr(fig.data[0], "xaxis", "") != expected_xref:
        failures.append(f"{prefix}_trace_xaxis_changed")
    if fig.data and getattr(fig.data[0], "yaxis", "") != expected_yref:
        failures.append(f"{prefix}_trace_yaxis_changed")
    return failures


def _check_subplot_injection() -> list[str]:
    child = _make_injection_child()
    module_parent = make_subplots(rows=1, cols=2)
    legacy_parent = make_subplots(rows=1, cols=2)

    inject_figure_into_subplot(module_parent, child, row=1, col=2, xref="x2", yref="y2")
    legacy_inject_figure_into_subplot(legacy_parent, child, row=1, col=2, xref="x2", yref="y2")

    failures: list[str] = []
    failures.extend(
        _check_injected_subplot(
            module_parent,
            prefix="module_subplot_injection",
            expected_xref="x2",
            expected_yref="y2",
        )
    )
    failures.extend(
        _check_injected_subplot(
            legacy_parent,
            prefix="legacy_subplot_injection",
            expected_xref="x2",
            expected_yref="y2",
        )
    )
    if _figure_signature(module_parent) != _figure_signature(legacy_parent):
        failures.append("subplot_injection_legacy_signature_changed")
    return failures


def _check_stress_block(fig, *, prefix: str) -> list[str]:
    failures: list[str] = []
    shapes = list(fig.layout.shapes or [])
    annotations = _annotation_text(fig)
    rects = [shape for shape in shapes if shape.type == "rect"]
    lines = [shape for shape in shapes if shape.type == "line"]

    if len(rects) < 1:
        failures.append(f"{prefix}_compression_block_missing")
    if len(lines) < 2:
        failures.append(f"{prefix}_axis_or_neutral_axis_lines_missing")
    for expected in ("Stress", "T", "MPa", "mm"):
        if not any(expected in text for text in annotations):
            failures.append(f"{prefix}_annotation_missing_{expected}")
    if int(fig.layout.height or 0) != 540:
        failures.append(f"{prefix}_height_not_preserved")
    if fig.layout.xaxis.visible is not False:
        failures.append(f"{prefix}_x_axis_visible")
    if fig.layout.yaxis.visible is not False:
        failures.append(f"{prefix}_y_axis_visible")
    return failures


def _check_force_model(fig, *, prefix: str) -> list[str]:
    failures: list[str] = []
    annotations = _annotation_text(fig)
    for expected in ("Force model", "C =", "T =", "z ="):
        if not any(expected in text for text in annotations):
            failures.append(f"{prefix}_annotation_missing_{expected.replace(' ', '_')}")
    if int(fig.layout.height or 0) != 540:
        failures.append(f"{prefix}_height_not_preserved")
    if fig.layout.xaxis.visible is not False:
        failures.append(f"{prefix}_x_axis_visible")
    if fig.layout.yaxis.visible is not False:
        failures.append(f"{prefix}_y_axis_visible")
    return failures


def _check_material_curves() -> list[str]:
    kwargs = dict(
        fc=40.0,
        fsy=500.0,
        Ec=30000.0,
        Es=200000.0,
        eps_s_sls=0.0012,
        fs_s_sls=240.0,
        eps_s_uls=0.0035,
        fs_s_uls=500.0,
        eps_c_sls=-0.0007,
    )
    module_fig = make_material_stress_strain_curves_figure(**kwargs)
    legacy_fig = legacy_plot_material_stress_strain_curves()
    failures: list[str] = []
    if _figure_signature(module_fig)[0] != 6:
        failures.append("material_curve_trace_count_changed")
    if _figure_signature(module_fig)[1] != 2:
        failures.append("material_curve_guide_shapes_changed")
    if int(module_fig.layout.height or 0) != 320:
        failures.append("material_curve_height_not_preserved")
    if _figure_signature(legacy_fig)[0] != 6:
        failures.append("legacy_material_curve_trace_count_changed")
    if _figure_signature(legacy_fig)[1] != 2:
        failures.append("legacy_material_curve_guide_shapes_changed")
    trace_names = [str(getattr(trace, "name", "") or "") for trace in module_fig.data]
    for expected in ("Concrete", "Concrete SLS", "Concrete ULS", "Steel", "Steel ULS", "Steel SLS"):
        if expected not in trace_names:
            failures.append(f"material_curve_trace_missing_{expected.replace(' ', '_')}")
    return failures


def _sample_three_panel_state() -> dict:
    return {
        "b": 450.0,
        "D": 750.0,
        "d": 690.0,
        "c": 180.0,
        "eps_c": 0.003,
        "eps_s": 0.0042,
        "gamma": 0.85,
        "fs_t": 500.0,
        "fc": 40.0,
        "alpha2": 0.85,
    }


def _sample_three_panel_layout() -> dict:
    return {
        "shape_name": "Rectangular",
        "b": 450.0,
        "D": 750.0,
        "dims": {"b": 450.0, "D": 750.0},
        "cage": {"x0": 50.0, "y0": 50.0, "x1": 400.0, "y1": 700.0},
        "lig": {"d": 0.0, "legs": 0},
        "reo_layout": {
            "bottom": [{"x": [120.0, 225.0, 330.0], "y": 690.0, "db": 20.0}],
            "top": [{"x": [145.0, 305.0], "y": 60.0, "db": 16.0}],
        },
        "reo": [{"x": 120.0, "y": 690.0, "dia": 20.0}],
        "reo_points": [],
    }


def _check_three_panel_stress_strain_profile() -> list[str]:
    shared_fig = plot_stress_strain_profiles(
        _sample_three_panel_state(),
        state_label="ULS",
        layout=_sample_three_panel_layout(),
        moment_sign="positive",
    )
    legacy_fig = legacy_plot_stress_strain_profiles(
        _sample_three_panel_state(),
        state_label="ULS",
        layout=_sample_three_panel_layout(),
        moment_sign="positive",
    )
    failures: list[str] = []
    if _figure_signature(shared_fig) != (3, 9, 22):
        failures.append("three_panel_signature_changed")
    if _figure_signature(legacy_fig) != _figure_signature(shared_fig):
        failures.append("three_panel_legacy_wrapper_signature_changed")
    if int(shared_fig.layout.height or 0) != 320:
        failures.append("three_panel_height_not_preserved")
    if int(shared_fig.layout.width or 0) != 900:
        failures.append("three_panel_width_not_preserved")
    annotations = _annotation_text(shared_fig)
    for expected in ("Section", "Strain", "Stress", "d =", "180 mm", "0.0030", "-0.0013", "500 MPa", "34 MPa"):
        if not any(expected in text for text in annotations):
            failures.append(f"three_panel_annotation_missing_{expected.replace(' ', '_')}")
    if _annotation_text(legacy_fig) != annotations:
        failures.append("three_panel_legacy_wrapper_annotations_changed")
    if shared_fig.layout.xaxis3.visible is not False:
        failures.append("three_panel_stress_x_axis_visible")
    if shared_fig.layout.yaxis3.visible is not False:
        failures.append("three_panel_stress_y_axis_visible")
    bending_source = (ROOT / "bending_diagrams.py").read_text(encoding="utf-8")
    if "Three-panel Plotly figure:" in bending_source:
        failures.append("three_panel_builder_body_still_in_bending_diagrams")
    return failures


def _check_single_panel_strain_profile() -> list[str]:
    shared_fig = plot_strain_profile(
        _sample_three_panel_state(),
        state_label="ULS",
        layout=_sample_three_panel_layout(),
        moment_sign="positive",
    )
    legacy_fig = legacy_plot_strain_profile(
        _sample_three_panel_state(),
        state_label="ULS",
        layout=_sample_three_panel_layout(),
        moment_sign="positive",
    )
    failures: list[str] = []
    if _figure_signature(shared_fig) != (1, 4, 3):
        failures.append("single_panel_strain_signature_changed")
    if _figure_signature(legacy_fig) != _figure_signature(shared_fig):
        failures.append("single_panel_strain_legacy_wrapper_signature_changed")
    if int(shared_fig.layout.height or 0) != 320:
        failures.append("single_panel_strain_height_not_preserved")
    annotations = _annotation_text(shared_fig)
    for expected in ("Strain", "0.0030", "-0.0013"):
        if not any(expected in text for text in annotations):
            failures.append(f"single_panel_strain_annotation_missing_{expected.replace(' ', '_')}")
    for forbidden in ("Section", "Stress", "500 MPa", "34 MPa"):
        if any(forbidden in text for text in annotations):
            failures.append(f"single_panel_strain_annotation_leaked_{forbidden.replace(' ', '_')}")
    if any(getattr(trace, "xaxis", None) not in (None, "x") for trace in shared_fig.data):
        failures.append("single_panel_strain_trace_not_remapped_to_primary_x")
    if any(getattr(shape, "xref", None) != "x" or getattr(shape, "yref", None) != "y" for shape in shared_fig.layout.shapes or []):
        failures.append("single_panel_strain_shape_not_remapped_to_primary_axes")
    if shared_fig.layout.xaxis.visible is not False:
        failures.append("single_panel_strain_x_axis_visible")
    if shared_fig.layout.yaxis.visible is not False:
        failures.append("single_panel_strain_y_axis_visible")
    return failures


def _matplotlib_signature(fig) -> tuple[int, int, int, int, tuple[str, ...], bool]:
    axes = list(fig.axes)
    if not axes:
        return (0, 0, 0, 0, (), True)
    ax = axes[0]
    text_values = tuple(str(text.get_text() or "") for text in ax.texts)
    return (
        len(axes),
        len(ax.lines),
        len(ax.patches),
        len(ax.texts),
        text_values,
        bool(ax.axison),
    )


def _check_sls_32_matplotlib_stress_block() -> list[str]:
    import bending_tabs  # noqa: WPS433

    layers = [{"name": "T1", "y": 690.0}, {"name": "T2", "y": 620.0}]
    shared_fig = make_sls_32_stress_block_figure(750.0, 690.0, 185.0, layers)
    legacy_fig = bending_tabs._make_sls_stress_block_figure_32(750.0, 690.0, 185.0, layers)
    shared_sig = _matplotlib_signature(shared_fig)
    legacy_sig = _matplotlib_signature(legacy_fig)
    failures: list[str] = []
    if shared_sig != legacy_sig:
        failures.append("sls_32_legacy_wrapper_signature_changed")
    if shared_sig[:4] != (1, 3, 1, 12):
        failures.append("sls_32_matplotlib_signature_changed")
    texts = shared_sig[4]
    for expected in ("$E_c \\varepsilon_c$", "$d_n = 185\\ \\text{mm}$", "T1", "T2", "Stress (MPa)"):
        if expected not in texts:
            failures.append(f"sls_32_text_missing_{expected}")
    if shared_sig[5] is not False:
        failures.append("sls_32_axis_not_hidden")
    bending_tabs_source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")
    if "Triangular compression block" in bending_tabs_source:
        failures.append("sls_32_builder_body_still_in_bending_tabs")
    return failures


def _check_sls_strain_distribution_figure() -> list[str]:
    rows = [
        {"Layer": "top", "Depth y (mm)": 0.0, "Îµ": -0.0005},
        {"Layer": "T1", "Depth y (mm)": 620.0, "Îµ": 0.0011},
        {"Layer": "bottom", "Depth y (mm)": 750.0, "Îµ": 0.0014},
    ]
    fig = make_sls_strain_distribution_figure(rows, 185.0)
    failures: list[str] = []
    if len(fig.axes) != 1:
        failures.append("sls_strain_axes_count_changed")
        return failures
    ax = fig.axes[0]
    if len(ax.lines) != 2:
        failures.append("sls_strain_line_count_changed")
    if ax.get_xlabel() != "Strain ε":
        failures.append("sls_strain_xlabel_changed")
    if ax.get_ylabel() != "Depth from top (mm)":
        failures.append("sls_strain_ylabel_changed")
    if ax.get_title() != "SLS strain distribution":
        failures.append("sls_strain_title_changed")
    y0, y1 = ax.get_ylim()
    if not (float(y0) > float(y1)):
        failures.append("sls_strain_y_axis_not_inverted")
    if not any(line.get_visible() for line in ax.get_xgridlines() + ax.get_ygridlines()):
        failures.append("sls_strain_grid_not_visible")
    bending_tabs_source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")
    if "fig_eps, ax_eps = plt.subplots()" in bending_tabs_source:
        failures.append("sls_strain_builder_body_still_in_bending_tabs")
    return failures


def _check_sls_stress_block() -> list[str]:
    module_fig = make_sls_stress_block_figure(
        D_mm=750.0,
        d_mm=690.0,
        dn_mm=185.0,
        d_comp_mm=62.0,
        D_draw=750.0,
        c=185.0,
        sigma_c_top=18.0,
        tension_layers=[(690.0, "T1", 240.0), (630.0, "T2", 180.0)],
        comp_layer=(62.0, "C_s", -95.0),
        is_hogging=False,
    )
    legacy_fig = legacy_make_sls_stress_block_figure(
        D_mm=750.0,
        d_mm=690.0,
        dn_mm=185.0,
        include_comp=True,
        d_comp_mm=62.0,
        moment_sign="positive",
    )
    failures: list[str] = []
    if _figure_signature(module_fig)[0] != 1:
        failures.append("sls_stress_trace_count_changed")
    if _figure_signature(module_fig)[1] < 2:
        failures.append("sls_stress_axis_or_na_shapes_missing")
    if _figure_signature(module_fig)[2] < 10:
        failures.append("sls_stress_annotations_missing")
    if int(module_fig.layout.height or 0) != 540:
        failures.append("sls_stress_height_not_preserved")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("sls_stress_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("sls_stress_y_axis_visible")
    module_annotations = _annotation_text(module_fig)
    for expected in ("Stress (MPa)", "E_c", "T1", "T2"):
        if not any(expected in text for text in module_annotations):
            failures.append(f"sls_stress_annotation_missing_{expected.replace(' ', '_')}")
    if _figure_signature(legacy_fig)[0] != 1:
        failures.append("legacy_sls_stress_trace_count_changed")
    if _figure_signature(legacy_fig)[1] < 2:
        failures.append("legacy_sls_stress_axis_or_na_shapes_missing")
    if int(legacy_fig.layout.height or 0) != 540:
        failures.append("legacy_sls_stress_height_not_preserved")
    return failures


def main() -> int:
    stress_kwargs = dict(
        b_mm=450.0,
        D_mm=750.0,
        d_mm=690.0,
        dn_mm=180.0,
        a_mm=153.0,
        alpha2=0.85,
        gamma=0.85,
        fc=40.0,
        fsy=500.0,
        show_C=True,
        C_N=300_000.0,
        variant="13",
        moment_sign="positive",
    )
    force_kwargs = dict(
        D_mm=750.0,
        d_mm=690.0,
        a_mm=153.0,
        C_N=300_000.0,
        T_N=300_000.0,
        moment_sign="positive",
        dn_mm=180.0,
    )

    module_stress = make_uls_stress_block_figure(**stress_kwargs)
    legacy_stress = legacy_make_uls_stress_block_figure(**stress_kwargs)
    module_force = make_uls_force_model_figure(**force_kwargs)
    legacy_force = legacy_make_uls_force_model_figure(**force_kwargs)

    failures: list[str] = []
    failures.extend(_check_stress_block(module_stress, prefix="module_stress"))
    failures.extend(_check_stress_block(legacy_stress, prefix="legacy_stress"))
    failures.extend(_check_force_model(module_force, prefix="module_force"))
    failures.extend(_check_force_model(legacy_force, prefix="legacy_force"))
    failures.extend(_check_material_curves())
    failures.extend(_check_three_panel_stress_strain_profile())
    failures.extend(_check_single_panel_strain_profile())
    failures.extend(_check_sls_32_matplotlib_stress_block())
    failures.extend(_check_sls_strain_distribution_figure())
    failures.extend(_check_sls_stress_block())
    failures.extend(_check_subplot_injection())

    if _figure_signature(module_stress) != _figure_signature(legacy_stress):
        failures.append("legacy_stress_signature_changed")
    if _figure_signature(module_force) != _figure_signature(legacy_force):
        failures.append("legacy_force_signature_changed")

    hogging_stress = make_uls_stress_block_figure(**{**stress_kwargs, "moment_sign": "negative"})
    if _figure_signature(hogging_stress)[1] < 3:
        failures.append("hogging_stress_shapes_missing")

    if failures:
        print("DIAGRAM_STRESS_STRAIN_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_STRESS_STRAIN_SMOKE PASS")
    print(f"- stress signature: {_figure_signature(module_stress)}")
    print(f"- force signature: {_figure_signature(module_force)}")
    print("- material curves, 3-panel profile, SLS 3.2 Matplotlib block, SLS strain distribution, SLS stress block, subplot injection, module builders, and legacy wrappers verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
