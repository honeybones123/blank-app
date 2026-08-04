"""Smoke checks for extracted 3D bending diagram builder."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.disable(logging.WARNING)

from bending_page import _build_beam_3d_figure_pure_impl  # noqa: E402
from ui.diagrams.bending_3d_diagram import build_beam_3d_figure_pure  # noqa: E402


def _sample_kwargs() -> dict:
    return {
        "b": 450.0,
        "D": 750.0,
        "L": 3000.0,
        "Mu_star": 220.0,
        "phi_Mu_cap": 300.0,
        "c": 180.0,
        "strain_state": "ULS",
        "reo_layout": {
            "bottom": [{"x": [120.0, 210.0, 300.0, 390.0], "y": 690.0, "db": 20.0}],
            "top": [{"x": [160.0, 290.0], "y": 60.0, "db": 16.0}],
        },
        "cover_bot": 50.0,
        "cover_top": 40.0,
        "cover_side": 45.0,
        "rowgap_bot": 60.0,
        "rowgap_top": 60.0,
        "lig_d": 10.0,
        "lig_legs": 3,
        "s_lig": 180.0,
        "debug_bust": "smoke",
    }


def _trace_names(fig) -> list[str]:
    return [str(getattr(trace, "name", "") or "") for trace in fig.data]


def _figure_signature(fig) -> tuple[int, int, str, str, str, str, bool]:
    scene = fig.layout.scene
    return (
        len(fig.data),
        int(fig.layout.height or 0),
        str(scene.xaxis.title.text),
        str(scene.yaxis.title.text),
        str(scene.zaxis.title.text),
        str(scene.zaxis.autorange),
        bool(fig.layout.showlegend),
    )


def _check_fig(fig, *, prefix: str) -> list[str]:
    failures: list[str] = []
    names = _trace_names(fig)
    signature = _figure_signature(fig)

    if signature[1] != 350:
        failures.append(f"{prefix}_height_changed")
    if signature[2] != "Length (mm)":
        failures.append(f"{prefix}_x_axis_title_changed")
    if signature[3] != "Width (mm)":
        failures.append(f"{prefix}_y_axis_title_changed")
    if signature[4] != "Depth from top (mm)":
        failures.append(f"{prefix}_z_axis_title_changed")
    if signature[5] != "reversed":
        failures.append(f"{prefix}_z_autorange_changed")
    if signature[6] is not False:
        failures.append(f"{prefix}_showlegend_changed")
    if "Concrete" not in names:
        failures.append(f"{prefix}_concrete_trace_missing")
    if "NA" not in names:
        failures.append(f"{prefix}_neutral_axis_trace_missing")
    if names.count("Reo") < 6:
        failures.append(f"{prefix}_reo_traces_missing")
    if not any(trace.type == "scatter3d" and getattr(trace, "mode", "") == "lines" for trace in fig.data):
        failures.append(f"{prefix}_stirrup_traces_missing")
    return failures


def main() -> int:
    kwargs = _sample_kwargs()
    module_fig = build_beam_3d_figure_pure(**kwargs)
    legacy_fig = _build_beam_3d_figure_pure_impl(**kwargs)
    failures: list[str] = []

    if module_fig is None:
        failures.append("module_figure_missing")
    else:
        failures.extend(_check_fig(module_fig, prefix="module"))

    if legacy_fig is None:
        failures.append("legacy_figure_missing")
    else:
        failures.extend(_check_fig(legacy_fig, prefix="legacy"))

    if module_fig is not None and legacy_fig is not None:
        if _figure_signature(module_fig) != _figure_signature(legacy_fig):
            failures.append("legacy_module_signature_mismatch")
        if _trace_names(module_fig) != _trace_names(legacy_fig):
            failures.append("legacy_module_trace_order_mismatch")

    invalid_kwargs = dict(kwargs)
    invalid_kwargs["phi_Mu_cap"] = 0.0
    if build_beam_3d_figure_pure(**invalid_kwargs) is not None:
        failures.append("module_invalid_capacity_not_rejected")
    if _build_beam_3d_figure_pure_impl(**invalid_kwargs) is not None:
        failures.append("legacy_invalid_capacity_not_rejected")

    if failures:
        print("DIAGRAM_BENDING_3D_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_BENDING_3D_SMOKE PASS")
    print("- shared 3D bending builder and legacy wrapper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
