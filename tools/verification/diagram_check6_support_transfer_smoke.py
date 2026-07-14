"""Smoke checks for the extracted Check 6 support-transfer diagram builder."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shear_diagrams import (  # noqa: E402
    build_shear_check6_support_transfer_diagram as legacy_build_shear_check6_support_transfer_diagram,
)
from ui.diagrams.check6_support_transfer_diagram import (  # noqa: E402
    build_shear_check6_support_transfer_diagram,
)


def _rect_layout() -> dict:
    return {
        "shape_name": "Rectangle (b x D)",
        "dims": {"b": 450.0, "D": 750.0},
        "reo": {
            "cover_top": 40.0,
            "cover_bot": 50.0,
            "cover_side": 45.0,
            "nb_top": 2,
            "db_top": 16.0,
            "nb_bot": 4,
            "db_bot": 20.0,
            "min_clear_spacing": 20.0,
            "rowgap_top": 60.0,
            "rowgap_bot": 60.0,
            "lig_d": 10.0,
            "lig_legs": 3,
        },
        "reo_points": [
            {"x": 120.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 210.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 300.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 390.0, "y": 690.0, "db": 20.0, "layer": "bottom"},
            {"x": 160.0, "y": 60.0, "db": 16.0, "layer": "top"},
            {"x": 290.0, "y": 60.0, "db": 16.0, "layer": "top"},
        ],
    }


def _base_kwargs() -> dict:
    return {
        "layout": _rect_layout(),
        "D_mm": 750.0,
        "d_mm": 690.0,
        "moment_sign": "positive",
        "support_draw_kind": "pinned",
        "critical_support_side": "left",
        "s_lig_mm": 180.0,
        "lig_legs": 3,
        "lig_d_mm": 10.0,
        "asv_mm2": 240.0,
        "height": 320,
        "fc_mpa": 40.0,
        "fsy_mpa": 500.0,
        "theta_v_deg": 35.0,
        "d_v_mm": 690.0,
    }


def _figure_signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _check_variant(
    name: str,
    overrides: dict | None = None,
    expected_annotations: tuple[str, ...] = ("Ast", "D-region"),
) -> list[str]:
    kwargs = _base_kwargs()
    kwargs.update(overrides or {})
    module_fig = build_shear_check6_support_transfer_diagram(**kwargs)
    legacy_fig = legacy_build_shear_check6_support_transfer_diagram(**kwargs)
    failures: list[str] = []
    if _figure_signature(module_fig) != _figure_signature(legacy_fig):
        failures.append(f"{name}_legacy_signature_changed")
    if len(module_fig.layout.shapes or []) < 10:
        failures.append(f"{name}_expected_shapes_missing")
    if int(module_fig.layout.height or 0) != int(kwargs["height"]):
        failures.append(f"{name}_height_not_preserved")
    if module_fig.layout.xaxis.visible is not False:
        failures.append(f"{name}_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append(f"{name}_y_axis_visible")
    annotations = _annotation_text(module_fig)
    for expected in expected_annotations:
        if not any(expected in text for text in annotations):
            failures.append(f"{name}_annotation_missing_{expected}")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_variant("mcft"))
    failures.extend(
        _check_variant(
            "teaching",
            {
                "height": 360,
                "show_shear_teaching_overlay": True,
                "show_mcft_mechanism_labels": True,
            },
        )
    )
    failures.extend(
        _check_variant(
            "web_crushing",
            {
                "web_crushing_stm": True,
                "show_mean_crack_guideline": False,
                "show_mean_green_flow_pulse": False,
                "show_mean_green_flow_arrows": False,
            },
            expected_annotations=("Ast", "web-crushing limit"),
        )
    )

    if failures:
        print("DIAGRAM_CHECK6_SUPPORT_TRANSFER_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_CHECK6_SUPPORT_TRANSFER_SMOKE PASS")
    print("- MCFT support-transfer diagram wrapper verified")
    print("- teaching-overlay and web-crushing variants verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
