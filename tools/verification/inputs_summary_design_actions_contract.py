from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page
from bending_checks_helpers import build_bending_check_rows_from_state
from calculations.design_actions import resolve_design_actions_from_state
from shear_checks_helpers import build_shear_check_rows_from_state


def _base_summary_state() -> dict:
    return {
        "actions_mode": "design",
        "actions_source": "Teaching SFD/BMD page (|M|max, |V|max)",
        "design_actions_source": "max",
        "uls_Mstar": 0.0,
        "uls_Mstar_pos_manual": 0.0,
        "uls_Mstar_neg_manual": 0.0,
        "uls_Vstar": 0.0,
        "uls_Nstar": 0.0,
        "sls_Mstar": 0.0,
        "sls_Mstar_pos_manual": 0.0,
        "sls_Mstar_neg_manual": 0.0,
        "sls_Vstar": 0.0,
        "b": 450.0,
        "D": 750.0,
        "fc": 40.0,
        "fsy": 500.0,
        "phi_bend": 0.8,
        "phi_shear": 0.7,
        "Ast_bot": 1256.0,
        "Ast_top": 628.0,
        "d": 690.0,
        "do": 60.0,
        "cover_bot": 40.0,
        "db_bot": 20.0,
        "nb_bot": 4.0,
        "rowgap_bot": 0.0,
        "lig_d": 10.0,
        "lig_legs": 2.0,
        "s_lig": 200.0,
    }


def test_design_result_overlay_feeds_summary_actions() -> None:
    working = _base_summary_state()
    overlay_audit: dict[str, dict] = {}
    overlaid = inputs_page._overlay_current_design_action_results_for_summary(
        working,
        overlay_audit,
        source_state={
            "actions_mode": "design",
            "actions_source": "Teaching SFD/BMD page (|M|max, |V|max)",
            "Mu_star": 72.0,
            "Mu_star_kNm": 72.0,
            "Mu_star_kNm_signed": 72.0,
            "Vu_star": 144.0,
            "sfd_Mmax_abs_kNm": 72.0,
            "sfd_Vmax_abs_kN": 144.0,
            "M_pos_max_uls_kNm": 72.0,
            "M_neg_min_uls_kNm": 0.0,
            "M_pos_max_sls_kNm": 38.0,
            "M_neg_min_sls_kNm": 0.0,
            "sfd_Msls_max_kNm": 38.0,
            "sfd_Vsls_max_kN": 70.0,
        },
    )

    assert overlaid["Mu_star"]["to"] == 72.0
    assert overlaid["Vu_star"]["to"] == 144.0
    assert overlay_audit["sfd_Mmax_abs_kNm"]["source"] == "design_action_result"

    actions = resolve_design_actions_from_state(working)
    assert actions["source"] == "design"
    assert actions["Mu"] == 72.0
    assert actions["Mu_pos"] == 72.0
    assert actions["Mu_neg"] == 0.0
    assert actions["Vu"] == 144.0
    assert actions["SLS_M"] == 38.0
    assert actions["SLS_V"] == 70.0

    bending_pack = build_bending_check_rows_from_state(working)
    bending_primary = next(row for row in bending_pack["rows"] if row.get("is_primary"))
    assert bending_primary["action"] == "Mu*(+) = 72.0 kNm"
    assert bending_pack["summary_Mu_star_kNm"] == 72.0

    shear_pack = build_shear_check_rows_from_state(working)
    assert shear_pack["summary_Vstar_kN"] == 144.0
    assert shear_pack["actions_used"]["Vu"] == 144.0


def test_manual_summary_actions_ignore_app_result_overlay() -> None:
    working = {
        "actions_mode": "manual",
        "actions_source": "Manual design actions (inputs below)",
        "uls_Mstar": 11.0,
        "uls_Mstar_pos_manual": 11.0,
        "uls_Mstar_neg_manual": 0.0,
        "uls_Vstar": 22.0,
        "uls_Nstar": 3.0,
        "sls_Mstar": 8.0,
        "sls_Mstar_pos_manual": 8.0,
        "sls_Mstar_neg_manual": 0.0,
        "sls_Vstar": 4.0,
    }
    overlaid = inputs_page._overlay_current_design_action_results_for_summary(
        working,
        {},
        source_state={
            "actions_mode": "manual",
            "Mu_star": 999.0,
            "Vu_star": 888.0,
            "sfd_Mmax_abs_kNm": 777.0,
            "sfd_Vmax_abs_kN": 666.0,
        },
    )

    assert overlaid == {}
    actions = resolve_design_actions_from_state(working)
    assert actions["source"] == "manual_uls"
    assert actions["Mu"] == 11.0
    assert actions["Vu"] == 22.0


def test_inputs_summary_source_uses_resolved_action_contract() -> None:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    assert "_SUMMARY_DESIGN_ACTION_RESULT_KEYS" in source
    assert "_overlay_current_design_action_results_for_summary(" in source
    assert "summary_design_action_result_overlay_count" in source
    assert "_summary_resolved_action_fp = (" in source
    assert 'summary_resolved_actions.get("Mu_pos"' in source
    assert 'summary_resolved_actions.get("Mu_neg"' in source
    assert 'summary_resolved_actions.get("Vu"' in source


def main() -> int:
    test_design_result_overlay_feeds_summary_actions()
    test_manual_summary_actions_ignore_app_result_overlay()
    test_inputs_summary_source_uses_resolved_action_contract()
    print("inputs_summary_design_actions_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
