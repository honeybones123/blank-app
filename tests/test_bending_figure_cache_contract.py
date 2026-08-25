from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import bending_diagrams


ROOT = Path(__file__).resolve().parents[1]


def test_bending_main_figure_cache_is_session_local_bounded_and_dependency_keyed() -> None:
    source = (ROOT / "bending_diagrams.py").read_text(encoding="utf-8")

    assert '_BENDING_MAIN_FIGURE_CACHE_KEY = "_bending_main_stress_strain_figure_cache"' in source
    assert "_BENDING_MAIN_FIGURE_CACHE_LIMIT = 6" in source
    assert "st.session_state.get(_BENDING_MAIN_FIGURE_CACHE_KEY)" in source
    assert "st.session_state[_BENDING_MAIN_FIGURE_CACHE_KEY]" in source
    assert 'cached.get("entries")' in source
    assert "while len(order) > _BENDING_MAIN_FIGURE_CACHE_LIMIT" in source
    assert "hashlib.sha256" in source
    assert '"state_dict": state_dict' in source
    assert '"layout": layout' in source
    assert '"state_label": state_label' in source
    assert '"moment_sign": str(moment_sign or "positive")' in source

    for key in (
        "shape_name",
        "sec_shape",
        "section_shape",
        "geometry_section_shape",
        "bending_sls_dn",
        "bending_sls_eps_top",
        "bending_sls_eps_bot",
        "bending_sls_kappa",
        "bending_sls_eps_s_outer",
        "eps_s_sls_bot",
        "eps_s_sls_bottom",
        "eps_s_bottom_sls",
    ):
        assert f'"{key}"' in source

    for key in ("d", "sigma_s_sls", "Ec", "fsy", "Es"):
        assert f'"{key}"' in source


def test_bending_main_figure_cache_cannot_override_debug_or_engineering_resolution() -> None:
    source = (ROOT / "bending_diagrams.py").read_text(encoding="utf-8")

    assert 'st.session_state.get("_dev_mode", False)' in source
    assert "_stress_diagram_plot_stress_strain_profiles(" in source
    assert "engineering result" in source
    assert "session-local and bounded" in source


def test_bending_main_figure_cache_reuses_a_previously_opened_state(monkeypatch) -> None:
    session_state = {}
    calls = []

    monkeypatch.setattr(bending_diagrams, "st", SimpleNamespace(session_state=session_state))
    monkeypatch.setattr(bending_diagrams, "get_param", lambda key, default=None: default)

    def build(*args, **kwargs):
        figure = object()
        calls.append((kwargs.get("state_label"), figure))
        return figure

    monkeypatch.setattr(
        bending_diagrams,
        "_stress_diagram_plot_stress_strain_profiles",
        build,
    )
    state = {"b": 250.0, "D": 300.0, "d": 255.0}
    layout = {"shape_name": "RECT"}

    uls_first = bending_diagrams._plot_stress_strain_profiles(
        state, state_label="uls – rectangular", layout=layout
    )
    bending_diagrams._plot_stress_strain_profiles(
        state, state_label="sls – linear", layout=layout
    )
    uls_again = bending_diagrams._plot_stress_strain_profiles(
        state, state_label="uls – rectangular", layout=layout
    )

    assert len(calls) == 2
    assert uls_again is uls_first


def test_bending_main_figure_cache_is_bounded(monkeypatch) -> None:
    session_state = {}
    monkeypatch.setattr(bending_diagrams, "st", SimpleNamespace(session_state=session_state))
    monkeypatch.setattr(bending_diagrams, "get_param", lambda key, default=None: default)
    monkeypatch.setattr(
        bending_diagrams,
        "_stress_diagram_plot_stress_strain_profiles",
        lambda *args, **kwargs: object(),
    )

    for index in range(9):
        bending_diagrams._plot_stress_strain_profiles(
            {"b": 250.0, "D": 300.0, "d": 255.0},
            state_label=f"uls – rectangular – {index}",
            layout={"shape_name": "RECT"},
        )

    cached = session_state[bending_diagrams._BENDING_MAIN_FIGURE_CACHE_KEY]
    assert len(cached["entries"]) == bending_diagrams._BENDING_MAIN_FIGURE_CACHE_LIMIT
    assert len(cached["order"]) == bending_diagrams._BENDING_MAIN_FIGURE_CACHE_LIMIT
