from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import state_and_helpers
from calculations.design_actions import (
    derive_design_action_session_updates,
    resolve_design_actions_from_state,
)


def _assert_same_contract(state: dict, expected: dict) -> None:
    from_adapter = state_and_helpers.resolve_design_actions(dict(state))
    from_module = resolve_design_actions_from_state(dict(state))
    assert from_adapter == from_module
    for key, value in expected.items():
        assert from_module[key] == value, (key, from_module[key], value)


def _assert_updates(state: dict, expected: dict) -> None:
    updates = derive_design_action_session_updates(dict(state))
    assert updates == expected


def test_manual_actions_contract() -> None:
    _assert_same_contract(
        {
            "actions_mode": "manual",
            "actions_source": "Manual design actions (inputs below)",
            "uls_Mstar": -30.0,
            "uls_Mstar_pos_manual": 12.0,
            "uls_Mstar_neg_manual": 55.0,
            "uls_Vstar": 140.0,
            "uls_Nstar": 25.0,
            "sls_Mstar": 22.0,
            "sls_Mstar_pos_manual": 18.0,
            "sls_Mstar_neg_manual": 9.0,
            "sls_Vstar": 70.0,
            "Tu_star": 4.0,
            "P_star": 6.0,
        },
        {
            "Mu": 55.0,
            "Mu_signed": -43.0,
            "Mu_pos": 12.0,
            "Mu_neg": 55.0,
            "has_sagging_case": True,
            "has_hogging_case": True,
            "Vu": 140.0,
            "Nu": 25.0,
            "SLS_M": 18.0,
            "SLS_M_signed": 9.0,
            "SLS_M_pos": 18.0,
            "SLS_M_neg": 9.0,
            "SLS_V": 70.0,
            "Tu": 4.0,
            "Pu": 6.0,
            "source": "manual_uls",
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            "signature": (
                55.0,
                140.0,
                25.0,
                18.0,
                70.0,
                "manual_uls",
                "Manual design actions (inputs below)",
                "manual",
            ),
        },
    )


def test_design_section_actions_contract() -> None:
    _assert_same_contract(
        {
            "actions_mode": "design",
            "actions_source": "Design run",
            "design_actions_source": "section",
            "design_M_uls_kNm_signed": -80.0,
            "design_V_uls_kN": 150.0,
            "design_M_sls_kNm_signed": 35.0,
            "design_V_sls_kN": 65.0,
            "Nu_star": 7.0,
            "Tu_star": 3.0,
            "P_star": 2.0,
        },
        {
            "Mu": 80.0,
            "Mu_signed": -80.0,
            "Mu_pos": 0.0,
            "Mu_neg": 80.0,
            "has_sagging_case": False,
            "has_hogging_case": True,
            "Vu": 150.0,
            "Nu": 7.0,
            "SLS_M": 35.0,
            "SLS_M_signed": 35.0,
            "SLS_M_pos": 35.0,
            "SLS_M_neg": 0.0,
            "SLS_V": 65.0,
            "Tu": 3.0,
            "Pu": 2.0,
            "source": "design",
            "actions_source": "Design run",
            "actions_mode": "design",
            "signature": (
                80.0,
                150.0,
                7.0,
                35.0,
                65.0,
                "design",
                "Design run",
                "design",
            ),
        },
    )


def test_design_max_actions_contract_with_manual_fallbacks() -> None:
    _assert_same_contract(
        {
            "actions_mode": "design",
            "actions_source": "Envelope",
            "design_actions_source": "max",
            "M_pos_max_uls_kNm": 0.0,
            "M_neg_min_uls_kNm": 0.0,
            "uls_Mstar_pos_manual": 42.0,
            "uls_Mstar_neg_manual": 58.0,
            "sfd_Vmax_abs_kN": 190.0,
            "M_pos_max_sls_kNm": 12.0,
            "M_neg_min_sls_kNm": -17.0,
            "sfd_Vsls_max_kN": 88.0,
            "N_star": 11.0,
        },
        {
            "Mu": 58.0,
            "Mu_signed": -58.0,
            "Mu_pos": 42.0,
            "Mu_neg": 58.0,
            "has_sagging_case": True,
            "has_hogging_case": True,
            "Vu": 190.0,
            "Nu": 11.0,
            "SLS_M": 17.0,
            "SLS_M_signed": -17.0,
            "SLS_M_pos": 12.0,
            "SLS_M_neg": 17.0,
            "SLS_V": 88.0,
            "Tu": 0.0,
            "Pu": 0.0,
            "source": "design",
            "actions_source": "Envelope",
            "actions_mode": "design",
            "signature": (
                58.0,
                190.0,
                11.0,
                17.0,
                88.0,
                "design",
                "Envelope",
                "design",
            ),
        },
    )


def test_manual_session_update_contract() -> None:
    _assert_updates(
        {
            "actions_mode": "manual",
            "uls_Mstar": -22.0,
            "uls_Mstar_pos_manual": 3.0,
            "uls_Mstar_neg_manual": 22.0,
            "uls_Vstar": 100.0,
            "uls_Nstar": 9.0,
            "sls_Mstar": 14.0,
            "sls_Mstar_pos_manual": 14.0,
            "sls_Mstar_neg_manual": 0.0,
            "sls_Vstar": 40.0,
        },
        {
            "Mu_star_manual": -22.0,
            "Mu_star_pos_manual": 3.0,
            "Mu_star_neg_manual": 22.0,
            "Mu_star": 22.0,
            "Mu_star_kNm": 22.0,
            "Mu_star_kNm_signed": -19.0,
            "Vu_star": 100.0,
            "N_star": 9.0,
        },
    )


def test_design_section_session_update_contract() -> None:
    _assert_updates(
        {
            "actions_mode": "design",
            "actions_source": "Design section",
            "design_actions_source": "section",
            "design_M_uls_kNm_signed": -75.0,
            "design_V_uls_kN": 120.0,
            "design_M_sls_kNm_signed": 25.0,
            "design_V_sls_kN": 45.0,
            "N_star": 8.0,
        },
        {
            "uls_Mstar": -75.0,
            "uls_Mstar_pos_manual": 0.0,
            "uls_Mstar_neg_manual": 75.0,
            "uls_Vstar": 120.0,
            "uls_Nstar": 8.0,
            "sls_Mstar": 25.0,
            "sls_Mstar_pos_manual": 25.0,
            "sls_Mstar_neg_manual": 0.0,
            "sls_Vstar": 45.0,
            "sls_Nstar": 8.0,
            "Mu_star_manual": -75.0,
            "Mu_star_pos_manual": 0.0,
            "Mu_star_neg_manual": 75.0,
            "Mu_star": 75.0,
            "Mu_star_kNm": 75.0,
            "Mu_star_kNm_signed": -75.0,
            "Vu_star": 120.0,
            "N_star": 8.0,
        },
    )


def test_design_max_session_update_contract() -> None:
    _assert_updates(
        {
            "actions_mode": "design",
            "actions_source": "Envelope",
            "design_actions_source": "max",
            "M_pos_max_uls_kNm": 32.0,
            "M_neg_min_uls_kNm": -46.0,
            "sfd_Vmax_abs_kN": 130.0,
            "M_pos_max_sls_kNm": 19.0,
            "M_neg_min_sls_kNm": -8.0,
            "sfd_Vsls_max_kN": 52.0,
            "N_star": 6.0,
        },
        {
            "uls_Mstar": -46.0,
            "uls_Mstar_pos_manual": 32.0,
            "uls_Mstar_neg_manual": 46.0,
            "uls_Vstar": 130.0,
            "uls_Nstar": 6.0,
            "sls_Mstar": 19.0,
            "sls_Mstar_pos_manual": 19.0,
            "sls_Mstar_neg_manual": 8.0,
            "sls_Vstar": 52.0,
            "sls_Nstar": 6.0,
            "Mu_star_manual": -46.0,
            "Mu_star_pos_manual": 32.0,
            "Mu_star_neg_manual": 46.0,
            "Mu_star": 46.0,
            "Mu_star_kNm": 46.0,
            "Mu_star_kNm_signed": -46.0,
            "Vu_star": 130.0,
            "N_star": 6.0,
        },
    )


def test_invalid_mode_session_update_preserves_legacy_resolve_contract() -> None:
    _assert_updates(
        {
            "actions_mode": "unexpected",
            "actions_source": "Not manual",
            "sfd_Mmax_abs_kNm": 99.0,
            "M_pos_max_uls_kNm": 99.0,
            "M_neg_min_uls_kNm": 0.0,
            "sfd_Vmax_abs_kN": 33.0,
            "sfd_Msls_max_kNm": 44.0,
            "M_pos_max_sls_kNm": 44.0,
            "sfd_Vsls_max_kN": 22.0,
            "uls_Mstar": 7.0,
            "uls_Mstar_pos_manual": 7.0,
            "uls_Mstar_neg_manual": 0.0,
            "N_star": 5.0,
        },
        {
            "Mu_star_manual": 7.0,
            "Mu_star_pos_manual": 7.0,
            "Mu_star_neg_manual": 0.0,
            "Mu_star": 99.0,
            "Mu_star_kNm": 99.0,
            "Mu_star_kNm_signed": 99.0,
            "Vu_star": 33.0,
            "N_star": 5.0,
        },
    )


def test_state_helper_is_adapter_only() -> None:
    state_source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8")
    assert "from calculations.design_actions import (" in state_source
    assert "derive_design_action_session_updates" in state_source
    assert "resolve_design_actions_from_state" in state_source
    assert "def resolve_design_actions(state: dict | None = None) -> dict:" in state_source
    assert "return resolve_design_actions_from_state(source_state)" in state_source
    assert "Mu_signed_fallback = float" not in state_source
    assert "uls_M_signed = float" not in state_source


def main() -> int:
    test_manual_actions_contract()
    test_design_section_actions_contract()
    test_design_max_actions_contract_with_manual_fallbacks()
    test_manual_session_update_contract()
    test_design_section_session_update_contract()
    test_design_max_session_update_contract()
    test_invalid_mode_session_update_preserves_legacy_resolve_contract()
    test_state_helper_is_adapter_only()
    print("design_actions_calculation_module_parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
