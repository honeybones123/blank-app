"""Regression contract for the shared Beam Setup / Load Analysis handover."""

from __future__ import annotations

from pathlib import Path

from application.contracts.design_actions import (
    DESIGN_ACTIONS_SNAPSHOT_SCHEMA_VERSION,
    DesignActionsSnapshot,
)
from application.design_actions_adapters import (
    BeamSetupDesignActionsAdapter,
    LoadAnalysisDesignActionsAdapter,
)
from application.design_brain_comparison import compare_design_brain_actions
from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)
from inputs_application.design_brain_composition import (
    calculate_v2_authoritative_result,
)
from inputs_page_modules.summaries.source_from_design_result import (
    build_summary_source_from_design_result,
)


def _assert_close(actual: float, expected: float) -> None:
    assert abs(float(actual) - float(expected)) < 1e-9, (actual, expected)


def verify_manual_adapter() -> None:
    state = {
        "actions_mode": "manual",
        "actions_source": "Manual design actions (inputs below)",
        "uls_Mstar": -80.0,
        "uls_Mstar_pos_manual": 120.0,
        "uls_Mstar_neg_manual": 80.0,
        "uls_Vstar": 45.0,
        "uls_Nstar": 7.0,
        "sls_Mstar_pos_manual": 72.0,
        "sls_Mstar_neg_manual": 48.0,
        "sls_Vstar": 27.0,
        "sls_Nstar": 4.0,
        "w_sls_kNm_per_m": 12.5,
    }
    actions = BeamSetupDesignActionsAdapter.from_state(state)
    assert isinstance(actions, DesignActionsSnapshot)
    _assert_close(actions.mu, 120.0)
    _assert_close(actions.mu_signed, 40.0)
    _assert_close(actions.mu_pos, 120.0)
    _assert_close(actions.mu_neg, 80.0)
    _assert_close(actions.vu, 45.0)
    _assert_close(actions.sls_m, 72.0)
    _assert_close(actions.sls_m_signed, 24.0)
    _assert_close(actions.sls_v, 27.0)
    assert actions.source == "manual_uls"
    assert actions.has_sagging_case and actions.has_hogging_case


def verify_load_analysis_max_adapter() -> None:
    state = {
        "actions_mode": "design",
        "design_actions_source": "max",
        "M_pos_max_uls_kNm": 150.0,
        "M_neg_min_uls_kNm": -90.0,
        "sfd_Mmax_abs_kNm": 150.0,
        "sfd_Vmax_abs_kN": 55.0,
        "M_pos_max_sls_kNm": 92.0,
        "M_neg_min_sls_kNm": -61.0,
        "sfd_Msls_max_kNm": 92.0,
        "sfd_Vsls_max_kN": 34.0,
    }
    actions = LoadAnalysisDesignActionsAdapter.from_state(state)
    _assert_close(actions.mu, 150.0)
    _assert_close(actions.mu_signed, 150.0)
    _assert_close(actions.mu_pos, 150.0)
    _assert_close(actions.mu_neg, 90.0)
    _assert_close(actions.vu, 55.0)
    _assert_close(actions.sls_m, 92.0)
    _assert_close(actions.sls_m_pos, 92.0)
    _assert_close(actions.sls_m_neg, 61.0)
    _assert_close(actions.sls_v, 34.0)
    assert actions.source == "design"
    assert actions.design_actions_source == "max"


def verify_zero_load_analysis_does_not_fall_back_to_manual_actions() -> None:
    state = {
        "actions_mode": "design",
        "actions_source": "Teaching SFD/BMD page (|M|max, |V|max)",
        "design_actions_source": "max",
        "sfd_Mmax_abs_kNm": 0.0,
        "sfd_Vmax_abs_kN": 0.0,
        "sfd_Msls_max_kNm": 0.0,
        "sfd_Vsls_max_kN": 0.0,
        "M_pos_max_uls_kNm": 0.0,
        "M_neg_min_uls_kNm": 0.0,
        "M_pos_max_sls_kNm": 0.0,
        "M_neg_min_sls_kNm": 0.0,
        # These belong to Beam Inputs and must not become Load Analysis output.
        "uls_Mstar_pos_manual": 200.0,
        "uls_Mstar_neg_manual": 0.0,
        "Mu_star_pos_manual": 200.0,
        "Mu_star_neg_manual": 0.0,
        "sls_Mstar_pos_manual": 0.0,
        "sls_Mstar_neg_manual": 0.0,
    }
    actions = LoadAnalysisDesignActionsAdapter.from_state(state)
    _assert_close(actions.mu, 0.0)
    _assert_close(actions.vu, 0.0)
    _assert_close(actions.sls_m, 0.0)
    _assert_close(actions.sls_v, 0.0)


def verify_load_analysis_section_adapter() -> None:
    state = {
        "actions_mode": "design",
        "design_actions_source": "section",
        "design_M_uls_kNm_signed": -64.0,
        "design_V_uls_kN": -22.0,
        "design_M_sls_kNm_signed": -39.0,
        "design_V_sls_kN": -13.0,
        "design_section_x_m": 1.75,
        "input_revision": 9,
    }
    actions = LoadAnalysisDesignActionsAdapter.from_state(state)
    _assert_close(actions.mu, 64.0)
    _assert_close(actions.mu_signed, -64.0)
    _assert_close(actions.mu_pos, 0.0)
    _assert_close(actions.mu_neg, 64.0)
    _assert_close(actions.vu, -22.0)
    _assert_close(actions.sls_m, 39.0)
    _assert_close(actions.sls_m_signed, -39.0)
    _assert_close(actions.sls_m_neg, 39.0)
    _assert_close(actions.sls_v, -13.0)
    assert not actions.has_sagging_case and actions.has_hogging_case
    assert actions.design_actions_source == "section"
    _assert_close(actions.design_section_x_m, 1.75)
    assert actions.input_revision == 9


def verify_snapshot_identity_uses_shared_contract() -> None:
    state = {
        "actions_mode": "manual",
        "uls_Mstar_pos_manual": 50.0,
        "uls_Mstar_neg_manual": 0.0,
        "uls_Vstar": 20.0,
        "sls_Mstar_pos_manual": 30.0,
        "sls_Vstar": 12.0,
        "b": 300.0,
        "D": 500.0,
    }
    snapshot = build_engineering_input_snapshot_from_resolved_state(state)
    assert snapshot.design_actions["schema_version"] == DESIGN_ACTIONS_SNAPSHOT_SCHEMA_VERSION
    assert snapshot.design_actions["resolved"]["Mu"] == 50.0
    assert snapshot.design_actions["resolved"]["SLS_M"] == 30.0
    assert len(snapshot.engineering_hash) == 64


def verify_same_actions_produce_same_design_calculations() -> None:
    section = {
        "b": 300.0,
        "D": 500.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "bot_row_1_bars": 4,
        "bot_row_1_dia": 20,
        "cover_bot": 40.0,
        "top_row_1_bars": 2,
        "top_row_1_dia": 16,
        "cover_top": 40.0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
    }
    manual = {
        **section,
        "actions_mode": "manual",
        "uls_Mstar_pos_manual": 120.0,
        "uls_Mstar_neg_manual": 0.0,
        "uls_Vstar": 45.0,
        "sls_Mstar_pos_manual": 72.0,
        "sls_Mstar_neg_manual": 0.0,
        "sls_Vstar": 27.0,
    }
    analysed = {
        **section,
        "actions_mode": "design",
        "design_actions_source": "max",
        "M_pos_max_uls_kNm": 120.0,
        "M_neg_min_uls_kNm": 0.0,
        "sfd_Mmax_abs_kNm": 120.0,
        "sfd_Vmax_abs_kN": 45.0,
        "M_pos_max_sls_kNm": 72.0,
        "M_neg_min_sls_kNm": 0.0,
        "sfd_Msls_max_kNm": 72.0,
        "sfd_Vsls_max_kN": 27.0,
    }
    manual_result = calculate_v2_authoritative_result(
        engineering_snapshot=build_engineering_input_snapshot_from_resolved_state(manual),
        resolved_inputs=manual,
        input_revision=11,
    )
    analysed_result = calculate_v2_authoritative_result(
        engineering_snapshot=build_engineering_input_snapshot_from_resolved_state(analysed),
        resolved_inputs=analysed,
        input_revision=11,
    )
    manual_calcs = dict(manual_result.current_calculations)
    analysed_calcs = dict(analysed_result.current_calculations)
    assert manual_calcs["actions_used"] == analysed_calcs["actions_used"]
    assert manual_calcs["families"] == analysed_calcs["families"]
    assert manual_calcs["packs"] == analysed_calcs["packs"]
    st_stub = type("StreamlitStub", (), {"session_state": {}})()
    manual_projection = build_summary_source_from_design_result(
        result=manual_result,
        actions=BeamSetupDesignActionsAdapter.from_state(manual),
        st_module=st_stub,
        scenario_id="manual",
        scenario_label="manual",
    )
    analysed_projection = build_summary_source_from_design_result(
        result=analysed_result,
        actions=LoadAnalysisDesignActionsAdapter.from_state(analysed),
        st_module=st_stub,
        scenario_id="analysed",
        scenario_label="analysed",
    )
    for family in ("bending", "shear", "crack", "deflection"):
        manual_card = getattr(manual_projection.source, family)
        analysed_card = getattr(analysed_projection.source, family)
        assert manual_card.capacity == analysed_card.capacity
        assert manual_card.action == analysed_card.action
        assert manual_card.utilisation == analysed_card.utilisation
        assert manual_card.status == analysed_card.status
        assert manual_card.rows == analysed_card.rows
    comparison = compare_design_brain_actions(
        LoadAnalysisDesignActionsAdapter.from_state(analysed),
        analysed_calcs["actions_used"],
    )
    assert comparison.matches, comparison.to_dict()


def verify_comparison_mode_detects_mismatch() -> None:
    actions = LoadAnalysisDesignActionsAdapter.from_state(
        {
            "design_actions_source": "max",
            "M_pos_max_uls_kNm": 100.0,
            "sfd_Mmax_abs_kNm": 100.0,
            "sfd_Vmax_abs_kN": 40.0,
            "M_pos_max_sls_kNm": 60.0,
            "sfd_Msls_max_kNm": 60.0,
            "sfd_Vsls_max_kN": 24.0,
        }
    )
    comparison = compare_design_brain_actions(
        actions,
        {"Mu": 100.0, "Vu": 41.0, "Nu": 0.0, "SLS_M": 60.0, "SLS_V": 24.0},
    )
    assert not comparison.matches
    assert set(comparison.differences) == {"Vu"}

    revision_actions = LoadAnalysisDesignActionsAdapter.from_state(
        {
            "input_revision": 7,
            "M_pos_max_uls_kNm": 0.0,
        }
    )
    revision_comparison = compare_design_brain_actions(
        revision_actions,
        {"Mu": 0.0, "Vu": 0.0, "Nu": 0.0, "SLS_M": 0.0, "SLS_V": 0.0},
        actual_revision=6,
    )
    assert not revision_comparison.matches
    assert not revision_comparison.revision_matches


def verify_production_pages_share_one_composition_and_projection() -> None:
    root = Path(__file__).resolve().parents[2]
    load_analysis = (root / "design_page_runtime.py").read_text(encoding="utf-8")
    beam_setup = (
        root / "inputs_application" / "page_runtime" / "setup.py"
    ).read_text(encoding="utf-8")
    shared_import = (
        "from inputs_application.design_brain_composition import"
    )
    assert shared_import in load_analysis
    assert shared_import in beam_setup
    assert "from inputs_application.new_design_brain_adapter import calculate_v2_authoritative_result" not in load_analysis
    assert "build_summary_source_from_design_result" in load_analysis
    beam_setup_summary = (
        root / "inputs_page_modules" / "summaries" / "render_coordinators.py"
    ).read_text(encoding="utf-8")
    assert "build_summary_source_from_design_result" in beam_setup_summary
    assert "legacy_projection_fallback" not in beam_setup_summary
    assert not (root / "inputs_page_modules" / "summaries" / "display_state.py").exists()


def main() -> None:
    verify_manual_adapter()
    verify_load_analysis_max_adapter()
    verify_zero_load_analysis_does_not_fall_back_to_manual_actions()
    verify_load_analysis_section_adapter()
    verify_snapshot_identity_uses_shared_contract()
    verify_same_actions_produce_same_design_calculations()
    verify_comparison_mode_detects_mismatch()
    verify_production_pages_share_one_composition_and_projection()
    print("shared design actions contract: PASS")


if __name__ == "__main__":
    main()
