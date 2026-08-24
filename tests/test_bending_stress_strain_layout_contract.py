from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from ui.diagrams import stress_strain_diagram as diagram


def _rectangular_layout() -> dict:
    points = [
        {"x": x, "y": 255.0, "db": 10.0, "layer": "bottom"}
        for x in (50.0, 125.0, 200.0)
    ] + [
        {"x": x, "y": 45.0, "db": 10.0, "layer": "top"}
        for x in (85.0, 165.0)
    ]
    return {
        "shape_name": "Rectangular",
        "b": 250.0,
        "D": 300.0,
        "cage": {"x0": 35.0, "x1": 215.0, "y0": 35.0, "y1": 265.0},
        "lig": {"d": 0.0, "legs": 0},
        "reo_layout": {
            "bottom": [{"x": [50.0, 125.0, 200.0], "y": 255.0, "db": 10.0}],
            "top": [{"x": [85.0, 165.0], "y": 45.0, "db": 10.0}],
        },
        "reo_points": points,
    }


def _state(*, steel_stress: float, concrete_strain: float) -> dict:
    return {
        "b": 250.0,
        "D": 300.0,
        "d": 255.0,
        "c": 26.6,
        "eps_c": concrete_strain,
        "eps_s": -0.0257,
        "gamma": 0.87,
        "fs_t": steel_stress,
        "fc": 40.0,
        "alpha2": 0.79,
        "Ec": 30000.0,
        "Es": 200000.0,
    }


def _geometry(figure) -> dict:
    layout = figure.layout
    return {
        "width": layout.width,
        "height": layout.height,
        "autosize": layout.autosize,
        "margin": (
            layout.margin.l,
            layout.margin.r,
            layout.margin.t,
            layout.margin.b,
        ),
        "x_domains": tuple(
            tuple(layout[name].domain) for name in ("xaxis", "xaxis2", "xaxis3")
        ),
        "y_domains": tuple(
            tuple(layout[name].domain) for name in ("yaxis", "yaxis2", "yaxis3")
        ),
        "x_ranges": tuple(
            tuple(layout[name].range) for name in ("xaxis", "xaxis2", "xaxis3")
        ),
        "y_ranges": tuple(
            tuple(layout[name].range) for name in ("yaxis", "yaxis2", "yaxis3")
        ),
    }


def test_uls_sls_and_uncracked_share_one_responsive_layout(monkeypatch) -> None:
    session_state = {
        "bending_sls_dn": 92.5,
        "bending_sls_eps_top": -0.0002,
        "bending_sls_eps_bot": 0.0006,
        "bending_sls_eps_s_outer": 0.0006,
        "bending_sls_kappa": 8.0e-6,
    }
    monkeypatch.setattr(diagram, "st", SimpleNamespace(session_state=session_state))
    values = {"fsy": 500.0, "Es": 200000.0, "Ec": 30000.0, "sigma_s_sls": 120.0}
    monkeypatch.setattr(diagram, "get_param", lambda name, default=None: values.get(name, default))

    section_layout = _rectangular_layout()
    state = _state(steel_stress=-500.0, concrete_strain=0.003)
    state_before = deepcopy(state)
    layout_before = deepcopy(section_layout)
    figures = [
        diagram.plot_stress_strain_profiles(
            state,
            state_label=label,
            layout=section_layout,
            moment_sign="positive",
        )
        for label in ("ULS", "SLS (cracked)", "Uncracked")
    ]

    geometries = [_geometry(figure) for figure in figures]
    assert geometries[0] == geometries[1] == geometries[2]
    assert geometries[0]["width"] is None
    assert geometries[0]["autosize"] is True
    assert geometries[0]["x_domains"] == (
        diagram.BENDING_STRESS_STRAIN_LAYOUT.section_domain,
        diagram.BENDING_STRESS_STRAIN_LAYOUT.strain_domain,
        diagram.BENDING_STRESS_STRAIN_LAYOUT.stress_domain,
    )
    assert geometries[0]["x_ranges"][1:] == ((0.0, 1.0), (0.0, 1.0))
    assert state == state_before
    assert section_layout == layout_before


def test_cached_layout_identity_is_versioned() -> None:
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "engineering_page_sections"
        / "bending_diagram_bundle.py"
    ).read_text(encoding="utf-8")
    tokens = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "ui"
        / "design_tokens.py"
    ).read_text(encoding="utf-8")

    assert '"layout_contract"' in source
    assert "BENDING_STRESS_STRAIN_LAYOUT_VERSION" in source
    assert 'BENDING_STRESS_STRAIN_LAYOUT_VERSION = "fixed-responsive-domains-v1"' in tokens
