from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

import bending_layer_semantics
import bending_core
import bending_checks_helpers
import bending_page
import state_and_helpers
from calculations import bending
from calculations import materials


SLS_INPUTS = {
    "b": 450.0,
    "D": 750.0,
    "d": 690.0,
    "Ast": 1809.5573684677208,
    "Ec": 30000.0,
    "Es": 200000.0,
    "Mu_star": 50.0,
    "nb_bot": 4,
    "db_bot": 24.0,
    "cover_bot": 40.0,
    "rowgap_bot": 40.0,
    "nb_top": 2,
    "db_top": 20.0,
    "cover_top": 40.0,
}


def _near(actual: float, expected: float, tol: float = 1e-12) -> None:
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def test_sls_bending_pure_contract() -> None:
    result = bending.compute_sls_bending_values(**SLS_INPUTS)
    assert result is not None
    _near(result["dn_sls"], 167.39286974249853)
    _near(result["Icr"], 3998382086.929091)
    _near(result["kappa"], 4.16835267473582e-07)
    _near(result["eps_top"], -6.977525163228485e-05)
    _near(result["fs_outer"], 43.56821658489734)
    _near(result["eps_s_outer"], 0.00021784108292448673)
    _near(result["y_outer"], 690.0)

    report = bending.sls_report_display_values(
        Ms_kNm=SLS_INPUTS["Mu_star"],
        Ec=SLS_INPUTS["Ec"],
        Es=SLS_INPUTS["Es"],
        d=SLS_INPUTS["d"],
        dn_sls=result["dn_sls"],
        kappa_sls=result["kappa"],
        eps_top_sls=None,
    )
    _near(report["n_sls"], 6.666666666666667)
    _near(report["Icr"], 3998382086.929091)
    _near(report["eps_top"], -6.977525163228485e-05)
    _near(report["eps_s"], 0.00021784108292448673)
    _near(report["fs"], 43.56821658489734)

    assert bending.compute_sls_bending_values(**{**SLS_INPUTS, "Ast": 0.0}) is None


def test_bending_summary_check_values_contract() -> None:
    result = bending.bending_summary_check_values(
        Ast=1809.5573684677208,
        As_min=420.0,
        Mu_star_kNm=50.0,
        phi_Mu_cap_kNm=474.9627766224587,
        Mu_util=0.10527140272923814,
        Mcr_kNm=43.0,
        ku=0.155,
    )
    _near(result["Mu_min"], 51.6)
    assert result["As_ok"] is True
    assert result["Mu_ok"] is True
    assert result["Mu_min_ok"] is True
    _near(result["Mu_min_util"], 51.6 / 474.9627766224587)
    assert result["ku_limit"] == 0.36
    assert result["ku_val"] == 0.155
    assert result["ku_ok"] is True
    assert result["Mu_util"] == 0.10527140272923814

    invalid = bending.bending_summary_check_values(
        Ast=None,
        As_min=float("nan"),
        Mu_star_kNm=None,
        phi_Mu_cap_kNm=0.0,
        Mu_util=None,
        Mcr_kNm=float("nan"),
        ku=float("nan"),
    )
    assert math.isnan(invalid["Mu_min"])
    assert invalid["As_ok"] is None
    assert invalid["Mu_ok"] is None
    assert invalid["Mu_min_ok"] is None
    assert invalid["Mu_min_util"] is None
    assert invalid["ku_val"] is None
    assert invalid["ku_ok"] is False


def _clear_sls_session_keys() -> None:
    for key in (
        "bending_sls_dn",
        "bending_sls_kappa",
        "bending_sls_eps_top",
        "bending_sls_fs_outer",
        "bending_sls_eps_s_outer",
        "bending_sls_y_tension_outer",
        "bending_sls_eps_bot",
        "bending_sls_y_bot",
    ):
        st.session_state.pop(key, None)


def _assert_sls_side_effect_contract(fs_outer: float | None, updates: dict[str, float]) -> None:
    _near(fs_outer, 43.56821658489734)
    _near(st.session_state["bending_sls_dn"], 167.39286974249853)
    _near(st.session_state["bending_sls_kappa"], 4.16835267473582e-07)
    _near(st.session_state["bending_sls_eps_top"], -6.977525163228485e-05)
    _near(st.session_state["bending_sls_fs_outer"], 43.56821658489734)
    _near(st.session_state["bending_sls_eps_s_outer"], 0.00021784108292448673)
    _near(st.session_state["bending_sls_y_tension_outer"], 690.0)
    _near(st.session_state["bending_sls_eps_bot"], 0.00021784108292448673)
    _near(st.session_state["bending_sls_y_bot"], 690.0)
    _near(updates["sigma_s_sls"], 43.56821658489734)
    _near(updates["bending_sls_fs_outer"], 43.56821658489734)
    _near(updates["bending_sls_dn_mm"], 167.39286974249853)


def _run_sls_state_adapter(adapter) -> tuple[float | None, dict[str, float]]:
    updates: dict[str, float] = {}
    original_get_param = bending_core.get_param
    original_update_results = bending_core.update_results

    def fake_get_param(name: str, default=None):
        values = {
            "b": SLS_INPUTS["b"],
            "D": SLS_INPUTS["D"],
            "d": SLS_INPUTS["d"],
            "Ast_bot": SLS_INPUTS["Ast"],
            "Ec": SLS_INPUTS["Ec"],
            "Es": SLS_INPUTS["Es"],
            "sls_Mstar": SLS_INPUTS["Mu_star"],
            "nb_bot": SLS_INPUTS["nb_bot"],
            "db_bot": SLS_INPUTS["db_bot"],
            "cover_bot": SLS_INPUTS["cover_bot"],
            "rowgap_bot": SLS_INPUTS["rowgap_bot"],
            "nb_top": SLS_INPUTS["nb_top"],
            "db_top": SLS_INPUTS["db_top"],
            "cover_top": SLS_INPUTS["cover_top"],
        }
        return values.get(name, default)

    def fake_update_results(**kwargs) -> None:
        updates.update(kwargs)

    try:
        bending_core.get_param = fake_get_param
        bending_core.update_results = fake_update_results

        _clear_sls_session_keys()

        fs_outer = adapter()
    finally:
        bending_core.get_param = original_get_param
        bending_core.update_results = original_update_results

    return fs_outer, updates


def test_bending_core_state_adapter_preserves_state_and_publication_contract() -> None:
    fs_outer, updates = _run_sls_state_adapter(
        lambda: bending_core.compute_sls_bending_values_from_state(publish=True)
    )
    _assert_sls_side_effect_contract(fs_outer, updates)


def test_bending_page_wrapper_delegates_to_core_state_adapter() -> None:
    fs_outer, updates = _run_sls_state_adapter(bending_page._compute_sls_bending_values)
    _assert_sls_side_effect_contract(fs_outer, updates)
    assert bending_page.bar_area_mm2 is bending.bar_area_mm2
    assert (
        bending_page.bottom_tension_effective_depth_fallback_mm
        is bending.bottom_tension_effective_depth_fallback_mm
    )
    assert bending_page.compression_block_lever_arm_values is bending.compression_block_lever_arm_values
    assert bending_page.minimum_moment_capacity_kNm is bending.minimum_moment_capacity_kNm
    assert (
        bending_page.nominal_capacity_from_phi_capacity_kNm
        is bending.nominal_capacity_from_phi_capacity_kNm
    )
    assert bending_page.stress_block_factors is bending.stress_block_factors
    assert bending_page.uls_bending_report_values is bending.uls_bending_report_values
    page_source = Path(bending_page.__file__).read_text(encoding="utf-8")
    assert "bar_area_mm2(nb_bot_local, db_bot_local)" in page_source
    assert "bottom_tension_effective_depth_fallback_mm(" in page_source
    assert "minimum_moment_capacity_kNm(Mcr_as)" in page_source
    assert "summary_check_values = bending_summary_check_values(" in page_source
    assert "minimum_moment_capacity_kNm(Mcr_top)" not in page_source
    assert "minimum_moment_capacity_kNm(Mcr)" in page_source
    assert "Mu_nom_report = nominal_capacity_from_phi_capacity_kNm(phi_Mu_cap, phi)" in page_source
    assert "active_lever_arm = compression_block_lever_arm_values(" in page_source
    assert "uls_report_values = uls_bending_report_values(" in page_source
    assert "nb_bot_local * math.pi * db_bot_local**2 / 4.0" not in page_source
    assert "D_local - cover_bot_local - 0.5 * db_bot_local" not in page_source
    assert "1.2 * Mcr" not in page_source
    assert "As_ok = Ast >= As_min_top" not in page_source
    assert "Mu_ok = Mu_star <= phi_Mu_cap_top" not in page_source
    assert "Mu_min_ok = phi_Mu_cap_top >= Mu_min_top" not in page_source
    assert "Mu_min_util = Mu_min_top / phi_Mu_cap_top" not in page_source
    assert "ku_val = ku_top if" not in page_source
    assert "phi_Mu_cap / phi if phi and phi > 0 else" not in page_source
    assert "a_active = gamma_active * dn" not in page_source
    assert "z_active = d_calc - 0.5 * a_active" not in page_source
    report_source = page_source.split("def build_bending_report", 1)[1].split(
        "def _get_compute_bending_capacity_pure",
        1,
    )[0]
    assert "T = Ast * fsy" not in report_source
    assert "denom_uls = alpha2_uls * fc * b * gamma_uls" not in report_source
    assert "dn = T / denom_uls if denom_uls > 0 else" not in report_source
    assert "a_uls = gamma_uls * dn" not in report_source
    assert "z_uls = d - 0.5 * a_uls" not in report_source
    assert "Mu_nom_uls = T * z_uls / 1e6" not in report_source
    assert "phi_Mu_cap_uls = phi * Mu_nom_uls" not in report_source
    assert "C_N = alpha2_uls * fc * b * a_uls" not in report_source
    assert "eps_s_rep = eps_cu_rep * (d - dn) / dn" not in report_source
    assert "eps_sy_rep = fsy / Es if Es and Es > 1e-9 else" not in report_source
    assert "ku = dn / d if d else" not in report_source
    assert "Mu_util_val = Mu_star / phi_Mu_cap_uls if phi_Mu_cap_uls > 0 else" not in report_source
    assert "stress_block_factors(fc)" not in report_source
    assert "n_sls = Es / Ec if Ec > 0 else 0.0" not in report_source
    assert "Ms_Nmm = Ms * 1e6" not in report_source
    assert "Icr = Ms_Nmm / (Ec * kappa_sls)" not in report_source
    assert "eps_top_computed = kappa_sls * (0.0 - dn_sls)" not in report_source
    assert "eps_s_computed = kappa_sls * (d - dn_sls)" not in report_source
    assert "fs_computed = Es * eps_s_computed" not in report_source
    assert "sls_report_display_values(" in report_source
    assert "stress_block_factors(fc_local)" in page_source
    assert "alpha2_raw = 0.85 - 0.0015" not in page_source
    assert "gamma_raw = 0.97 - 0.0025" not in page_source


def test_bending_core_uses_calculation_module_not_page_helper() -> None:
    assert bending_core.compute_sls_bending_values is bending.compute_sls_bending_values
    assert bending_core.derive_concrete_modulus_from_fc is materials.derive_concrete_modulus_from_fc
    assert bending_core.hogging_tension_effective_depth_mm is bending.hogging_tension_effective_depth_mm
    assert bending_core.minimum_moment_capacity_kNm is bending.minimum_moment_capacity_kNm
    assert bending_core._layout_bars_in_rows is bending.layout_bars_in_rows
    assert state_and_helpers.effective_depth_with_links_mm is bending.effective_depth_with_links_mm
    assert state_and_helpers._decode_bars_or_spacing is bending.decode_bars_or_spacing
    assert bending_core.solve_bending_capacity is bending.solve_bending_capacity
    assert bending_core.resolve_bending_faces is bending.resolve_bending_faces
    assert (
        bending_checks_helpers.compute_bending_capacity_from_state_values
        is bending.compute_bending_capacity_from_state_values
    )
    assert bending_layer_semantics.resolve_bending_faces is bending.resolve_bending_faces
    assert (
        bending_layer_semantics.resolve_bending_layer_geometry
        is bending.resolve_bending_layer_geometry
    )
    core_source = Path(bending_core.__file__).read_text(encoding="utf-8")
    state_source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8")
    calc_source = Path(bending.__file__).read_text(encoding="utf-8")
    assert "def compression_block_lever_arm_values(" in calc_source
    assert "def nominal_capacity_from_phi_capacity_kNm(" in calc_source
    assert "def uls_bending_report_values(" in calc_source
    assert "lever_arm = compression_block_lever_arm_values(" in calc_source
    assert "from bending_page import _compute_sls_bending_values" not in core_source
    assert "Ec = 4700 * math.sqrt(fc)" not in core_source
    assert "derive_concrete_modulus_from_fc(fc)" in core_source
    assert "minimum_moment_capacity_kNm(Mcr)" in core_source
    assert "Mx_min_req = 1.2 * Mcr" not in core_source
    assert "from bending_page import _compute_sls_bending_values" not in state_source
    assert "def effective_depth_with_links_mm(" not in state_source
    assert "def _decode_bars_or_spacing(" not in state_source
    assert "from bending_layer_semantics import" not in calc_source
    assert "from state_and_helpers import" not in calc_source
    assert "from bending_core import compute_sls_bending_values_from_state" in state_source
    checks_source = Path(bending_checks_helpers.__file__).read_text(encoding="utf-8")
    assert "def compute_bending_capacity_from_state(" in checks_source
    assert "return compute_bending_capacity_from_state_values(" in checks_source
    assert "_compute_bending_capacity_pure_impl(" not in checks_source


def test_legacy_bending_capacity_module_contract() -> None:
    _near(
        bending.bottom_tension_effective_depth_fallback_mm(750.0, 40.0, 24.0),
        698.0,
    )
    _near(
        bending.bottom_tension_effective_depth_fallback_mm(30.0, 40.0, 20.0),
        -20.0,
    )
    _near(bending.effective_depth_with_links_mm(750.0, 40.0, 10.0, 24.0), 688.0)
    _near(
        bending.effective_depth_centroid_mm(
            450.0,
            750.0,
            4,
            24.0,
            40.0,
            40.0,
            10.0,
        ),
        688.0,
    )
    assert (
        bending.effective_depth_centroid_mm(
            450.0,
            None,
            4,
            24.0,
            40.0,
            40.0,
            10.0,
        )
        is None
    )

    kwargs = dict(
        b=450.0,
        D=750.0,
        fc=40.0,
        fsy=500.0,
        Ast=1809.5573684677208,
        Mu_star=50.0,
        phi=0.8,
        d_input=690.0,
        cover_bot=40.0,
        db_bot=24.0,
        nb_bot=4,
        rowgap_bot=40.0,
        lig_diameter_mm=10.0,
    )
    result = bending.compute_bending_capacity_legacy(**kwargs)
    wrapper_result = bending_core._compute_bending_capacity_pure_impl(**kwargs)
    assert wrapper_result == result
    _near(result["phi_Mu_cap"], 474.9627766224587)
    _near(result["Mu_util"], 0.10527140748914794)
    _near(result["c"], 73.13470457942194)
    _near(result["a"], 63.627192984097086)
    _near(result["z"], 656.1864035079515)
    _near(result["ku"], 0.10630044270264816)
    _near(result["fctf"], 3.794733192202055)
    _near(result["I_gross"], 15820312500.0)
    _near(result["Z_gross"], 42187500.0)
    _near(result["Mcr"], 160.0903065460242)
    _near(result["As_min"], 939.8795170446051)
    _near(result["d"], 688.0)

    missing = bending.compute_bending_capacity_legacy(
        **{**kwargs, "D": None},
    )
    assert missing["phi_Mu_cap"] == 0.0
    assert missing["phi"] == 0.8
    assert missing["d"] == 690.0

    bad_denom = bending.compute_bending_capacity_legacy(
        **{**kwargs, "fc": 0.0},
    )
    assert bad_denom["phi_Mu_cap"] == 0.0
    assert bad_denom["alpha2"] == 0.85
    assert bad_denom["gamma"] == 0.97


def test_bending_layer_semantics_contract() -> None:
    assert bending.resolve_bending_faces("positive") == ("bottom", "top", False)
    assert bending.resolve_bending_faces("negative") == ("top", "bottom", True)
    assert bending.resolve_bending_faces("") == ("bottom", "top", False)

    layout = {
        "reo_points": [
            {"layer": "top", "y": 60.0, "As": 500.0},
            {"layer": "bottom", "y": 690.0, "As": 900.0},
            {"layer": "bottom", "y": 640.0, "As": 900.0},
        ]
    }
    sagging = bending.resolve_bending_layer_geometry(
        layout,
        moment_sign="positive",
        D=750.0,
        fallback_y_tension=680.0,
    )
    assert sagging["tension_face"] == "bottom"
    assert sagging["compression_face"] == "top"
    assert sagging["is_hogging"] is False
    _near(sagging["y_tension_centroid"], 690.0)
    _near(sagging["y_compression_steel_centroid"], 60.0)
    _near(sagging["d_value"], 690.0)
    _near(sagging["d_prime_value"], 60.0)
    assert len(sagging["tension_layer_coords"]) == 2
    assert len(sagging["compression_layer_coords"]) == 1

    hogging = bending.resolve_bending_layer_geometry(
        layout,
        moment_sign="negative",
        D=750.0,
        fallback_y_tension=70.0,
    )
    assert hogging["tension_face"] == "top"
    assert hogging["compression_face"] == "bottom"
    assert hogging["is_hogging"] is True
    _near(hogging["y_tension_centroid"], 60.0)
    _near(hogging["y_compression_steel_centroid"], 665.0)
    _near(hogging["d_value"], 690.0)
    _near(hogging["d_prime_value"], 85.0)
    assert len(hogging["tension_layer_coords"]) == 1
    assert len(hogging["compression_layer_coords"]) == 2

    fallback = bending.resolve_bending_layer_geometry(
        None,
        moment_sign="negative",
        D=750.0,
        fallback_y_tension=80.0,
    )
    _near(fallback["d_value"], 670.0)
    assert fallback["d_prime_value"] is None


def test_bar_row_layout_contract() -> None:
    _near(bending.bar_area_mm2(4, 24.0), 1809.5573684677208)
    _near(bending.bar_area_mm2(2, 16.0), 402.1238596594935)
    assert bending.bar_area_mm2(None, 24.0) == 0.0
    assert bending.stress_block_factors(40.0) == (0.79, 0.87)
    assert bending.stress_block_factors(200.0) == (0.67, 0.67)
    _near(bending.minimum_moment_capacity_kNm(42.0), 50.4)
    assert math.isnan(bending.minimum_moment_capacity_kNm(None))
    assert math.isnan(bending.minimum_moment_capacity_kNm(float("nan")))
    _near(bending.nominal_capacity_from_phi_capacity_kNm(212.5, 0.85), 250.0)
    assert math.isnan(bending.nominal_capacity_from_phi_capacity_kNm(212.5, 0.0))
    assert math.isnan(bending.nominal_capacity_from_phi_capacity_kNm(212.5, None))
    lever_arm = bending.compression_block_lever_arm_values(
        dn_mm=120.0,
        gamma=0.87,
        d_mm=690.0,
    )
    _near(lever_arm["a"], 104.4)
    _near(lever_arm["z"], 637.8)
    uls_report = bending.uls_bending_report_values(
        b=450.0,
        d=690.0,
        fc=40.0,
        fsy=500.0,
        Ast=1809.5573684677208,
        phi=0.8,
        Mu_star=50.0,
        Es=200000.0,
    )
    expected_uls_report = {
        "alpha2": 0.79,
        "gamma": 0.87,
        "T_N": 904778.6842338605,
        "T_kN": 904.7786842338604,
        "denom": 12371.4,
        "dn": 73.13470457942194,
        "a": 63.627192984097086,
        "z": 658.1864035079515,
        "Mu_nom": 595.5130281465412,
        "phi_Mu_cap": 476.410422517233,
        "C_N": 904778.6842338606,
        "C_kN": 904.7786842338605,
        "eps_cu": 0.003,
        "eps_s": 0.025303936030151686,
        "eps_sy": 0.0025,
        "ku": 0.1059923254774231,
        "ku_limit": 0.36,
        "ku_ok": True,
        "Mu_ok": True,
        "Mu_util": 0.10495152422529415,
    }
    assert uls_report.keys() == expected_uls_report.keys()
    for key, expected_value in expected_uls_report.items():
        if isinstance(expected_value, bool):
            assert uls_report[key] is expected_value
        else:
            _near(uls_report[key], expected_value)

    assert bending.layout_bars_in_rows(None, 450.0, 40.0, 20.0, 60.0) == []
    assert bending.layout_bars_in_rows(0, 450.0, 40.0, 20.0, 60.0) == []
    assert bending.layout_bars_in_rows(1, 450.0, 40.0, 20.0, 60.0) == [
        (225.0, 0)
    ]
    one_row = bending.layout_bars_in_rows(3, 450.0, 40.0, 20.0, 60.0)
    assert one_row == [(40.0, 0), (225.0, 0), (410.0, 0)]

    split_rows = bending.layout_bars_in_rows(6, 260.0, 45.0, 20.0, 80.0)
    assert split_rows == [
        (45.0, 0),
        (130.0, 0),
        (215.0, 0),
        (45.0, 1),
        (130.0, 1),
        (215.0, 1),
    ]

    forced_one_row = bending.layout_bars_in_rows(
        6,
        260.0,
        45.0,
        20.0,
        80.0,
        n_rows_max=1,
    )
    assert forced_one_row == [
        (45.0, 0),
        (125.0, 0),
        (205.0, 0),
        (285.0, 0),
        (365.0, 0),
        (445.0, 0),
    ]


def test_decode_bars_or_spacing_contract() -> None:
    assert bending.decode_bars_or_spacing("bad", 450.0, 40.0, 20.0) == ("N", 0, 0.0)
    assert bending.decode_bars_or_spacing(0.0, 450.0, 40.0, 20.0) == ("N", 0, 0.0)
    assert bending.decode_bars_or_spacing(4.0, 450.0, 40.0, 20.0) == (
        "N",
        4,
        123.33333333333333,
    )
    assert bending.decode_bars_or_spacing(1.0, 450.0, 40.0, 20.0) == (
        "N",
        1,
        370.0,
    )
    assert bending.decode_bars_or_spacing(100.0, 450.0, 40.0, 20.0) == (
        "S",
        4,
        100.0,
    )
    assert bending.decode_bars_or_spacing(500.0, 450.0, 40.0, 20.0) == (
        "S",
        1,
        500.0,
    )
    assert bending.decode_bars_or_spacing(4.0, 60.0, 40.0, 20.0) == ("N", 0, 0.0)
    assert state_and_helpers._decode_bars_or_spacing(
        100.0,
        450.0,
        40.0,
        20.0,
    ) == bending.decode_bars_or_spacing(100.0, 450.0, 40.0, 20.0)


def test_signed_bending_capacity_contract() -> None:
    inputs = {
        "b": 450.0,
        "D": 750.0,
        "fc": 40.0,
        "fsy": 500.0,
        "phi_bend": 0.8,
        "Ast_bot": 1809.5573684677208,
        "Ast_top": 942.4777960769379,
        "d": 690.0,
        "do": 690.0,
    }
    assert bending.hogging_tension_effective_depth_mm(750.0, 60.0) == 690.0
    assert bending.hogging_tension_effective_depth_mm(750.0, 690.0) == 690.0
    assert bending.hogging_tension_effective_depth_mm(0.0, 50.0) == 50.0

    positive = bending.solve_bending_capacity("positive", 50.0, inputs)
    _near(positive["phi_Mu_kNm"], 476.410422517233)
    _near(positive["Mu_nom_kNm"], 595.5130281465412)
    _near(positive["util"], 0.10495152422529415)
    _near(positive["dn_mm"], 73.13470457942194)
    _near(positive["ku"], 0.1059923254774231)
    assert positive["status"] == "PASS"
    assert positive["tension_face"] == "bottom"
    assert positive["compression_face"] == "top"
    assert positive["tension_steel_label"] == "Bottom reinforcement"

    negative = bending.solve_bending_capacity("negative", 80.0, inputs)
    _near(negative["phi_Mu_kNm"], 253.87728665325426)
    _near(negative["Mu_nom_kNm"], 317.3466083165678)
    _near(negative["util"], 0.3151128683254916)
    _near(negative["dn_mm"], 38.09099196844892)
    _near(negative["ku"], 0.05520433618615785)
    assert negative["status"] == "PASS"
    assert negative["tension_face"] == "top"
    assert negative["compression_face"] == "bottom"
    assert negative["tension_steel_label"] == "Top reinforcement"


def test_bending_stress_strain_state_contract() -> None:
    inputs = dict(
        b=450.0,
        D=750.0,
        d_plot=690.0,
        d_f=690.0,
        fc=40.0,
        fsy=500.0,
        As=1809.5573684677208,
        Ec=30000.0,
        Es=200000.0,
    )

    uls = bending.compute_stress_strain_state_values(state="ULS", **inputs)
    assert uls["b"] == 450.0
    assert uls["D"] == 750.0
    assert uls["d"] == 690.0
    _near(uls["c"], 73.13470457942194)
    _near(uls["eps_c"], -0.003)
    _near(uls["eps_s"], 0.025303936030151686)
    _near(uls["gamma"], 0.87)
    _near(uls["fs_t"], 500.0)
    _near(uls["alpha2"], 0.79)

    sls = bending.compute_stress_strain_state_values(state="SLS", **inputs)
    _near(sls["c"], 167.39286974249853)
    _near(sls["eps_c"], -0.0008)
    _near(sls["eps_s"], 0.002497631499174039)
    _near(sls["fs_t"], 499.5262998348078)

    uncracked = bending.compute_stress_strain_state_values(state="Uncracked", **inputs)
    _near(uncracked["c"], 375.0)
    _near(uncracked["eps_c"], -0.0002)
    _near(uncracked["eps_s"], 0.000168)
    _near(uncracked["gamma"], 1.0)
    _near(uncracked["fs_t"], 5.04)

    assert (
        bending_core.compute_stress_strain_state_values
        is bending.compute_stress_strain_state_values
    )
    assert bending_core.bar_area_mm2 is bending.bar_area_mm2
    core_source = Path(bending_core.__file__).read_text(encoding="utf-8")
    adapter_source = core_source.split("def _stress_strain_state", 1)[1]
    assert "compute_stress_strain_state_values(" in adapter_source
    assert "bar_area_mm2(" in adapter_source
    assert "denom = alpha2 * fc * b * gamma" not in adapter_source
    assert "alpha2_raw = 0.85 - 0.0015" not in adapter_source
    assert "gamma_raw = 0.97 - 0.0025" not in adapter_source
    assert "r1 = (-b_coef + math.sqrt(discr))" not in adapter_source
    assert "eps_ext_unc = 0.0002" not in adapter_source
    assert "nb_bot * math.pi * db_bot**2 / 4.0" not in adapter_source
    assert "nb_t * math.pi * db_t**2 / 4.0" not in adapter_source


def test_bending_capacity_from_state_values_contract() -> None:
    state = {
        "actions_mode": "manual",
        "uls_Mstar_pos_manual": 50.0,
        "uls_Mstar_neg_manual": 80.0,
        "sls_Mstar_pos_manual": 25.0,
        "sls_Mstar_neg_manual": 5.0,
        "b": 450.0,
        "D": 750.0,
        "fc": 40.0,
        "fsy": 500.0,
        "phi_bend": 0.8,
        "Ast_bot": 1809.5573684677208,
        "Ast_top": 942.4777960769379,
        "d": 690.0,
        "do": 690.0,
        "cover_bot": 40.0,
        "db_bot": 24.0,
        "nb_bot": 4,
        "rowgap_bot": 40.0,
    }
    result = bending.compute_bending_capacity_from_state_values(
        state,
        lig_diameter_mm=10.0,
    )
    assert result["actions"]["Mu"] == 80.0
    assert result["Mu_pos_star"] == 50.0
    assert result["Mu_neg_star"] == 80.0
    assert result["has_sagging_case"] is True
    assert result["has_hogging_case"] is True
    assert result["governing_case"] == "Negative bending"
    _near(result["governing_util"], 0.3151128683254916)
    _near(result["governing_phi_mu_kNm"], 253.87728665325426)
    _near(result["legacy"]["d"], 688.0)
    _near(result["legacy"]["phi_Mu_cap"], 474.9627766224587)
    _near(result["bending_pos"]["phi_Mu_kNm"], 476.410422517233)
    _near(result["bending_neg"]["phi_Mu_kNm"], 253.87728665325426)

    original_get_param = bending_checks_helpers.get_param
    try:
        bending_checks_helpers.get_param = lambda name, default=None: 10.0 if name == "lig_d" else default
        adapter_result = bending_checks_helpers.compute_bending_capacity_from_state(state)
    finally:
        bending_checks_helpers.get_param = original_get_param
    assert adapter_result == result


def main() -> int:
    test_sls_bending_pure_contract()
    test_bending_summary_check_values_contract()
    test_bending_core_state_adapter_preserves_state_and_publication_contract()
    test_bending_page_wrapper_delegates_to_core_state_adapter()
    test_bending_core_uses_calculation_module_not_page_helper()
    test_legacy_bending_capacity_module_contract()
    test_bending_layer_semantics_contract()
    test_bar_row_layout_contract()
    test_decode_bars_or_spacing_contract()
    test_signed_bending_capacity_contract()
    test_bending_stress_strain_state_contract()
    test_bending_capacity_from_state_values_contract()
    print("bending_calculation_module_parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
