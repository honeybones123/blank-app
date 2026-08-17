from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bending_main_figure_cache_is_session_local_and_dependency_keyed() -> None:
    source = (ROOT / "bending_diagrams.py").read_text(encoding="utf-8")

    assert '_BENDING_MAIN_FIGURE_CACHE_KEY = "_bending_main_stress_strain_figure_cache"' in source
    assert "st.session_state.get(_BENDING_MAIN_FIGURE_CACHE_KEY)" in source
    assert "st.session_state[_BENDING_MAIN_FIGURE_CACHE_KEY]" in source
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
    assert "single-entry" in source
