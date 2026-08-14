from __future__ import annotations

from dataclasses import replace
import copy

from inputs_page_modules.diagrams.builders import build_section_2d_request_view_model
from inputs_page_modules.diagrams.models import InputsDiagramSourceSnapshot
from section_layout import compute_section_layout_pure


def _source(*, width: float, bottom_count: int, bottom_diameter: float) -> InputsDiagramSourceSnapshot:
    calculated = compute_section_layout_pure(
        b=width,
        D=700.0,
        cover_bot=40.0,
        cover_top=40.0,
        cover_side=40.0,
        nb_or_s_bot_1=bottom_count,
        db_bot_1=bottom_diameter,
        nb_or_s_bot_2=0,
        db_bot_2=0.0,
        nb_or_s_top_1=2,
        db_top_1=10.0,
        nb_or_s_top_2=0,
        db_top_2=0.0,
        rowgap_bot=40.0,
        rowgap_top=40.0,
        lig_legs=4,
        lig_d=10.0,
    )
    reo = {
        "cover_side": 40.0,
        "cover_top": 40.0,
        "cover_bot": 40.0,
        "lig_d": 10.0,
        "lig_legs": 4,
        "s_lig": 100.0,
    }
    return InputsDiagramSourceSnapshot(
        layout={
            "shape_name": "Rectangle (b x D)",
            "dims": {"b": width, "D": 700.0},
            "reo": reo,
            "reo_layout": calculated["reo_layout"],
        },
        shared_state=reo,
    )


def test_invalid_longitudinal_spacing_is_exposed_to_diagram_shell() -> None:
    model = build_section_2d_request_view_model(
        _source(width=200.0, bottom_count=4, bottom_diameter=32.0)
    )

    assert any("clear spacing" in reason for reason in model.validation_errors)


def test_valid_reinforcement_keeps_diagram_shell_clear() -> None:
    model = build_section_2d_request_view_model(
        _source(width=450.0, bottom_count=4, bottom_diameter=24.0)
    )

    assert model.validation_errors == ()


def test_saved_per_bar_row_elevations_do_not_crash_diagram_validation() -> None:
    source = _source(width=450.0, bottom_count=4, bottom_diameter=24.0)
    layout = copy.deepcopy(source.layout)
    first = layout["reo_layout"]["bottom"][0]
    first["y"] = [first["y"] for _ in first["x"]]

    model = build_section_2d_request_view_model(replace(source, layout=layout))

    assert model.validation_errors == ()


def _flanged_source(shape: str) -> InputsDiagramSourceSnapshot:
    state = {
        "lig_d": 10.0,
        "lig_legs": 2,
        "s_lig": 300.0,
    }
    web_key = "bw" if shape == "T" else "tw"
    layout = {
        "shape_name": f"{shape}-Section",
        "dims": {"bf": 600.0, "tf": 120.0, web_key: 120.0, "D": 475.0},
        "reo": {
            "cover_bot": 40.0,
            "cover_top": 40.0,
            "cover_side": 40.0,
            **state,
        },
        "reo_layout": {"top": [], "bottom": []},
        "reo_error": (
            "Reo does not fit: 6 bottom web bars require more width than is "
            "available after cover and shear links."
        ),
    }
    return InputsDiagramSourceSnapshot(layout=layout, shared_state=state)


def test_t_section_failed_bar_placement_is_exposed_to_red_diagram_shell() -> None:
    model = build_section_2d_request_view_model(_flanged_source("T"))

    assert model.validation_errors
    assert any("does not fit" in reason.lower() for reason in model.validation_errors)


def test_i_section_failed_bar_placement_is_exposed_to_red_diagram_shell() -> None:
    model = build_section_2d_request_view_model(_flanged_source("I"))

    assert model.validation_errors
    assert any("does not fit" in reason.lower() for reason in model.validation_errors)
