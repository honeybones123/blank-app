import inspect
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from inputs_application.action_source_control import (
    INPUTS_ACTION_SOURCE_TOGGLE_KEY,
    LOAD_ANALYSIS_ACTIONS_SOURCE,
    LOAD_ANALYSIS_ACTION_SOURCE_TOGGLE_KEY,
    MANUAL_ACTIONS_SOURCE,
    authoritative_action_source_projection,
    commit_action_source_toggle,
    load_analysis_action_projection,
    migrate_missing_manual_action_owners,
    seed_action_source_toggle,
    synchronize_load_analysis_actions_for_inputs,
    uses_load_analysis_actions,
)
from calculations.design_actions import resolve_design_actions_from_state
from calculations.design_actions import derive_design_action_session_updates
from inputs_application.state_projection import build_guidance_state_snapshot
from inputs_application.summary_state_runtime import (
    SUMMARY_OVERLAY_SKIP_SHARED_KEYS,
    summary_overlay_skip_shared_keys,
)
from inputs_page_modules.session import build_inputs_summary_source_shaping_snapshot
from inputs_page_modules.widgets.design_action_sync import (
    design_action_widget_specs,
    hydrate_design_action_widgets_from_shared,
    sync_design_action_widget_to_shared,
)
from inputs_page_modules.widgets.render_coordinators import (
    render_inputs_design_actions_section,
)
from inputs_application.page_runtime.setup import (
    _engineering_transaction_widget_keys,
    _project_selected_action_source_current_coordinator,
    project_committed_action_source_for_result_page,
)
from inputs_application.page_runtime import setup as _setup_runtime_module


def test_streamlit_toggle_commits_canonical_action_source() -> None:
    app = AppTest.from_file(
        str(Path(__file__).with_name("streamlit_action_source_harness.py"))
    )
    app.run()

    assert not app.toggle[0].value

    app.toggle[0].set_value(True).run()

    assert app.toggle[0].value
    assert app.session_state["actions_mode"] == "design"
    assert app.session_state["actions_source"] == LOAD_ANALYSIS_ACTIONS_SOURCE


def test_manual_uls_widgets_enter_the_canonical_input_transaction() -> None:
    mapping = _engineering_transaction_widget_keys(
        design_governing=False,
        loads_edit_mode="ULS",
    )

    assert mapping["uls_Mstar_pos_manual"] == "inputs_load_Mstar_pos_proxy"
    assert mapping["uls_Mstar_neg_manual"] == "inputs_load_Mstar_neg_proxy"
    assert mapping["manual_uls_Vstar"] == "inputs_load_Vstar_proxy"
    assert mapping["manual_uls_Nstar"] == "inputs_load_Nstar_proxy"


def test_manual_sls_widgets_enter_only_the_sls_input_transaction() -> None:
    mapping = _engineering_transaction_widget_keys(
        design_governing=False,
        loads_edit_mode="SLS",
    )

    assert mapping["sls_Mstar_pos_manual"] == "inputs_load_Mstar_pos_proxy"
    assert mapping["manual_sls_Vstar"] == "inputs_load_Vstar_proxy"
    assert "uls_Mstar_pos_manual" not in mapping


def test_load_analysis_controls_do_not_overwrite_manual_action_owners() -> None:
    mapping = _engineering_transaction_widget_keys(
        design_governing=True,
        loads_edit_mode="ULS",
    )

    assert "uls_Mstar_pos_manual" not in mapping
    assert "uls_Vstar" not in mapping


def test_result_page_projection_uses_committed_source_pointer(
    monkeypatch,
) -> None:
    """A stale route flag cannot replace selected Load Analysis actions."""

    monkeypatch.setattr(
        _setup_runtime_module,
        "st",
        SimpleNamespace(
            session_state={
                # Simulate the transient result-page session projection that
                # previously made Bending recalculate at zero.
                "actions_mode": "manual",
                "actions_source": MANUAL_ACTIONS_SOURCE,
                "sfd_Mmax_abs_kNm": 180.0,
                "sfd_Vmax_abs_kN": 90.0,
            }
        ),
    )
    committed = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
    }

    projected = _project_selected_action_source_current_coordinator(committed)

    assert projected["actions_mode"] == "design"
    assert projected["actions_source"] == LOAD_ANALYSIS_ACTIONS_SOURCE
    assert projected["sfd_Mmax_abs_kNm"] == 180.0
    assert projected["sfd_Vmax_abs_kN"] == 90.0


def test_result_page_boundary_publishes_committed_selected_actions(
    monkeypatch,
) -> None:
    session = {
        "active_beam_id": "B1",
        "actions_mode": "manual",
        "actions_source": MANUAL_ACTIONS_SOURCE,
        "sfd_Mmax_abs_kNm": 180.0,
        "sfd_Vmax_abs_kN": 90.0,
    }
    committed = SimpleNamespace(
        snapshot={
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        }
    )
    services = SimpleNamespace(
        input_snapshots=SimpleNamespace(
            current_for_beam=lambda beam_id: committed
        )
    )
    monkeypatch.setattr(
        _setup_runtime_module,
        "st",
        SimpleNamespace(session_state=session),
    )
    monkeypatch.setattr(
        _setup_runtime_module.InputsSessionServices,
        "from_mapping",
        lambda state: services,
    )

    projection = project_committed_action_source_for_result_page()

    assert projection["actions_mode"] == "design"
    assert session["actions_source"] == LOAD_ANALYSIS_ACTIONS_SOURCE
    assert session["sfd_Mmax_abs_kNm"] == 180.0
    assert session["sfd_Vmax_abs_kN"] == 90.0


def test_result_page_boundary_reads_beam_owned_load_analysis_results(
    monkeypatch,
) -> None:
    beam_id = "beam-load-analysis"
    session = {
        "active_beam_id": beam_id,
        "_load_analysis_drafts_by_beam_v1": {
            beam_id: {"design_actions_source_selector": "max"}
        },
        "_load_analysis_results_by_beam_v1": {
            beam_id: {
                "sfd_Mmax_abs_kNm": 275.0,
                "sfd_Vmax_abs_kN": 135.0,
                "sfd_Msls_max_kNm": 165.0,
                "sfd_Vsls_max_kN": 81.0,
                "M_pos_max_uls_kNm": 275.0,
                "M_neg_min_uls_kNm": -40.0,
                "M_pos_max_sls_kNm": 165.0,
                "M_neg_min_sls_kNm": -24.0,
            }
        },
    }
    committed = SimpleNamespace(
        snapshot={
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        }
    )
    services = SimpleNamespace(
        input_snapshots=SimpleNamespace(
            current_for_beam=lambda current_beam_id: committed
        )
    )
    monkeypatch.setattr(
        _setup_runtime_module,
        "st",
        SimpleNamespace(session_state=session),
    )
    monkeypatch.setattr(
        _setup_runtime_module.InputsSessionServices,
        "from_mapping",
        lambda state: services,
    )

    projection = project_committed_action_source_for_result_page()

    assert projection["sfd_Mmax_abs_kNm"] == 275.0
    assert projection["sfd_Vmax_abs_kN"] == 135.0
    assert projection["sfd_Msls_max_kNm"] == 165.0
    assert projection["sfd_Vsls_max_kN"] == 81.0
    assert session["M_pos_max_uls_kNm"] == 275.0
    assert session["M_neg_min_uls_kNm"] == -40.0


def test_inputs_toggle_selects_load_analysis_and_synchronizes_both_pages() -> None:
    state = {
        "actions_mode": "manual",
        "actions_source": MANUAL_ACTIONS_SOURCE,
        INPUTS_ACTION_SOURCE_TOGGLE_KEY: True,
    }

    assert commit_action_source_toggle(state, INPUTS_ACTION_SOURCE_TOGGLE_KEY)
    assert state["actions_mode"] == "design"
    assert state["actions_source"] == LOAD_ANALYSIS_ACTIONS_SOURCE
    assert state[LOAD_ANALYSIS_ACTION_SOURCE_TOGGLE_KEY] is True
    assert state["inputs_use_calculated_actions"] is True
    assert uses_load_analysis_actions(state)


def test_load_analysis_toggle_selects_inputs_and_synchronizes_both_pages() -> None:
    state = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        LOAD_ANALYSIS_ACTION_SOURCE_TOGGLE_KEY: False,
    }

    assert commit_action_source_toggle(
        state, LOAD_ANALYSIS_ACTION_SOURCE_TOGGLE_KEY
    )
    assert state["actions_mode"] == "manual"
    assert state["actions_source"] == MANUAL_ACTIONS_SOURCE
    assert state[INPUTS_ACTION_SOURCE_TOGGLE_KEY] is False
    assert state["inputs_use_calculated_actions"] is False
    assert not uses_load_analysis_actions(state)


def test_page_widget_is_always_seeded_from_canonical_source() -> None:
    state = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        INPUTS_ACTION_SOURCE_TOGGLE_KEY: False,
    }

    assert seed_action_source_toggle(state, INPUTS_ACTION_SOURCE_TOGGLE_KEY)
    assert state[INPUTS_ACTION_SOURCE_TOGGLE_KEY] is True


def test_missing_action_source_defaults_to_beam_inputs_not_stale_analysis() -> None:
    actions = resolve_design_actions_from_state(
        {
            "uls_Mstar_pos_manual": 0.0,
            "uls_Mstar_neg_manual": 0.0,
            "uls_Vstar": 0.0,
            "sfd_Mmax_abs_kNm": 200.0,
            "sfd_Vmax_abs_kN": 300.0,
        }
    )

    assert actions["Mu"] == 0.0
    assert actions["Vu"] == 0.0
    assert actions["source"] == "manual_uls"


def test_manual_shear_and_axial_owners_override_compatibility_projections() -> None:
    actions = resolve_design_actions_from_state(
        {
            "actions_mode": "manual",
            "actions_source": MANUAL_ACTIONS_SOURCE,
            "manual_uls_Vstar": 80.0,
            "manual_uls_Nstar": 12.0,
            "manual_sls_Vstar": 53.0,
            "uls_Vstar": 0.0,
            "uls_Nstar": 0.0,
            "sls_Vstar": 0.0,
        }
    )

    assert actions["Vu"] == 80.0
    assert actions["Nu"] == 12.0
    assert actions["SLS_V"] == 53.0


def test_load_analysis_projection_supplies_uls_and_sls_without_overwriting_manual_actions() -> None:
    state = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        "uls_Mstar_pos_manual": 17.0,
        "uls_Vstar": 8.0,
        "sls_Mstar_pos_manual": 11.0,
        "sls_Vstar": 5.0,
    }
    results = {
        "sfd_Mmax_abs_kNm": 135.0,
        "sfd_Vmax_abs_kN": 270.0,
        "sfd_Msls_max_kNm": 104.0,
        "sfd_Vsls_max_kN": 208.0,
        "M_pos_max_uls_kNm": 135.0,
        "M_neg_min_uls_kNm": -20.0,
        "M_pos_max_sls_kNm": 104.0,
        "M_neg_min_sls_kNm": -12.0,
    }

    changed = synchronize_load_analysis_actions_for_inputs(
        state,
        draft={"design_actions_source_selector": "max"},
        results=results,
    )
    actions = resolve_design_actions_from_state(state)

    assert "sfd_Mmax_abs_kNm" in changed
    assert actions["Mu"] == 135.0
    assert actions["Vu"] == 270.0
    assert actions["SLS_M"] == 104.0
    assert actions["SLS_V"] == 208.0
    assert state["uls_Mstar_pos_manual"] == 17.0
    assert state["uls_Vstar"] == 8.0
    assert state["sls_Mstar_pos_manual"] == 11.0
    assert state["sls_Vstar"] == 5.0


def test_guidance_projection_preserves_selected_load_analysis_uls_and_sls() -> None:
    state = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
    }
    synchronize_load_analysis_actions_for_inputs(
        state,
        draft={"design_actions_source_selector": "max"},
        results={
            "sfd_Mmax_abs_kNm": 135.0,
            "sfd_Vmax_abs_kN": 270.0,
            "sfd_Msls_max_kNm": 104.0,
            "sfd_Vsls_max_kN": 208.0,
            "M_pos_max_uls_kNm": 135.0,
            "M_neg_min_uls_kNm": -20.0,
            "M_pos_max_sls_kNm": 104.0,
            "M_neg_min_sls_kNm": -12.0,
        },
    )

    snapshot = build_guidance_state_snapshot(
        state,
        result_keys={
            "actions_source",
            "sfd_Mmax_abs_kNm",
            "sfd_Vmax_abs_kN",
            "sfd_Msls_max_kNm",
            "sfd_Vsls_max_kN",
            "M_pos_max_uls_kNm",
            "M_neg_min_uls_kNm",
            "M_pos_max_sls_kNm",
            "M_neg_min_sls_kNm",
        },
        shared_defaults={
            "actions_mode": "manual",
            "actions_source": MANUAL_ACTIONS_SOURCE,
        },
    )
    actions = resolve_design_actions_from_state(snapshot)

    assert snapshot["actions_source"] == LOAD_ANALYSIS_ACTIONS_SOURCE
    assert actions["Mu"] == 135.0
    assert actions["Vu"] == 270.0
    assert actions["SLS_M"] == 104.0
    assert actions["SLS_V"] == 208.0


def test_guidance_projection_still_removes_stale_actions_in_manual_mode() -> None:
    snapshot = build_guidance_state_snapshot(
        {
            "actions_mode": "manual",
            "actions_source": MANUAL_ACTIONS_SOURCE,
            "sfd_Mmax_abs_kNm": 135.0,
        },
        result_keys={"actions_source", "sfd_Mmax_abs_kNm"},
        shared_defaults={
            "actions_mode": "manual",
            "actions_source": MANUAL_ACTIONS_SOURCE,
        },
    )

    assert snapshot["actions_source"] == MANUAL_ACTIONS_SOURCE
    assert "sfd_Mmax_abs_kNm" not in snapshot


def test_summary_shaping_cannot_restore_stale_manual_action_source_widget() -> None:
    shaped = build_inputs_summary_source_shaping_snapshot(
        base_state={
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
            "design_actions_source": "max",
            "sfd_Mmax_abs_kNm": 135.0,
        },
        source_state={
            "inputs_actions_source": MANUAL_ACTIONS_SOURCE,
            "design_actions_source_selector": "section",
        },
        input_tab_keys={
            "actions_source": "inputs_actions_source",
            "design_actions_source": "design_actions_source_selector",
        },
        skip_shared_keys=SUMMARY_OVERLAY_SKIP_SHARED_KEYS,
        skip_longitudinal_keys=(),
        skip_prefixes=(),
        deferred_overlay_keys=(),
        shared_only_mode=False,
        shared_only_reason="",
    )

    assert shaped.working_state["actions_source"] == LOAD_ANALYSIS_ACTIONS_SOURCE
    assert shaped.working_state["design_actions_source"] == "max"
    assert shaped.overlay_applied == {}


def test_design_governed_summary_cannot_overlay_stale_manual_action_widgets() -> None:
    session = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        "inputs_load_Mstar_pos_proxy": 200.0,
        "inputs_load_Mstar_neg_proxy": 0.0,
        "inputs_load_Vstar_proxy": 80.0,
    }
    skipped = summary_overlay_skip_shared_keys(session)
    shaped = build_inputs_summary_source_shaping_snapshot(
        base_state={
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
            "design_actions_source": "max",
            "sfd_Mmax_abs_kNm": 9.75,
            "sfd_Vmax_abs_kN": 19.5,
            "M_pos_max_uls_kNm": 9.75,
            "M_neg_min_uls_kNm": 0.0,
            "uls_Mstar_pos_manual": 200.0,
            "manual_uls_Vstar": 80.0,
        },
        source_state=session,
        input_tab_keys={
            "uls_Mstar_pos_manual": "inputs_load_Mstar_pos_proxy",
            "uls_Mstar_neg_manual": "inputs_load_Mstar_neg_proxy",
            "manual_uls_Vstar": "inputs_load_Vstar_proxy",
        },
        skip_shared_keys=skipped,
        skip_longitudinal_keys=(),
        skip_prefixes=(),
        deferred_overlay_keys=(),
        shared_only_mode=False,
        shared_only_reason="",
    )
    actions = resolve_design_actions_from_state(shaped.working_state)

    assert actions["Mu"] == 9.75
    assert actions["Vu"] == 19.5
    assert shaped.overlay_applied == {}


def test_authoritative_snapshot_projection_includes_load_analysis_results() -> None:
    projection = authoritative_action_source_projection(
        {
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
            "design_actions_source": "max",
            "sfd_Mmax_abs_kNm": 135.0,
            "sfd_Vmax_abs_kN": 270.0,
            "sfd_Msls_max_kNm": 104.0,
            "sfd_Vsls_max_kN": 208.0,
        }
    )

    assert projection["sfd_Mmax_abs_kNm"] == 135.0
    assert projection["sfd_Vmax_abs_kN"] == 270.0
    assert projection["sfd_Msls_max_kNm"] == 104.0
    assert projection["sfd_Vsls_max_kN"] == 208.0


def test_authoritative_projection_does_not_claim_manual_action_ownership() -> None:
    projection = authoritative_action_source_projection(
        {
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
            "uls_Mstar": 9.75,
            "uls_Mstar_pos_manual": 9.75,
            "uls_Mstar_neg_manual": 0.0,
            "uls_Vstar": 19.5,
            "sls_Mstar": 7.5,
            "sls_Mstar_pos_manual": 7.5,
            "sls_Mstar_neg_manual": 0.0,
            "sls_Vstar": 15.0,
        }
    )

    assert "uls_Mstar" not in projection
    assert "uls_Vstar" not in projection
    assert "sls_Mstar" not in projection
    assert "sls_Vstar" not in projection


def test_design_action_resolution_never_falls_back_to_manual_compatibility_values() -> None:
    actions = resolve_design_actions_from_state(
        {
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
            "design_actions_source": "max",
            "uls_Mstar_pos_manual": 9.75,
            "uls_Mstar_neg_manual": 0.0,
            "uls_Vstar": 19.5,
            "sls_Mstar": 7.5,
            "sls_Vstar": 15.0,
        }
    )

    assert actions["Mu"] == 0.0
    assert actions["Vu"] == 0.0
    assert actions["SLS_M"] == 0.0
    assert actions["SLS_V"] == 0.0


def test_absolute_only_load_analysis_moment_is_resolved_as_derived_sagging() -> None:
    actions = resolve_design_actions_from_state(
        {
            "actions_mode": "design",
            "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
            "design_actions_source": "max",
            "sfd_Mmax_abs_kNm": 9.75,
            "sfd_Vmax_abs_kN": 19.5,
            "sfd_Msls_max_kNm": 7.5,
            "sfd_Vsls_max_kN": 15.0,
            "uls_Mstar_pos_manual": 200.0,
            "sls_Mstar_pos_manual": 120.0,
        }
    )

    assert actions["Mu"] == 9.75
    assert actions["Mu_pos"] == 9.75
    assert actions["Mu_signed"] == 9.75
    assert actions["Vu"] == 19.5
    assert actions["SLS_M"] == 7.5
    assert actions["SLS_M_pos"] == 7.5
    assert actions["SLS_V"] == 15.0


def test_manual_source_never_imports_load_analysis_actions() -> None:
    state = {
        "actions_mode": "manual",
        "actions_source": MANUAL_ACTIONS_SOURCE,
        "uls_Mstar_pos_manual": 17.0,
    }

    changed = synchronize_load_analysis_actions_for_inputs(
        state,
        draft={},
        results={"sfd_Mmax_abs_kNm": 135.0},
    )

    assert changed == ()
    assert "sfd_Mmax_abs_kNm" not in state
    assert state["uls_Mstar_pos_manual"] == 17.0


def test_design_action_derivation_preserves_manual_moment_owners() -> None:
    state = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        "design_actions_source": "max",
        "M_pos_max_uls_kNm": 9.75,
        "M_neg_min_uls_kNm": 0.0,
        "sfd_Vmax_abs_kN": 19.5,
        "M_pos_max_sls_kNm": 7.5,
        "M_neg_min_sls_kNm": 0.0,
        "sfd_Vsls_max_kN": 15.0,
        "uls_Mstar_pos_manual": 200.0,
        "uls_Mstar_neg_manual": 0.0,
        "sls_Mstar_pos_manual": 120.0,
        "sls_Mstar_neg_manual": 0.0,
    }

    updates = derive_design_action_session_updates(state)

    assert updates["uls_Mstar"] == 9.75
    assert updates["sls_Mstar"] == 7.5
    assert "uls_Mstar_pos_manual" not in updates
    assert "uls_Mstar_neg_manual" not in updates
    assert "sls_Mstar_pos_manual" not in updates
    assert "sls_Mstar_neg_manual" not in updates
    assert state["uls_Mstar_pos_manual"] == 200.0
    assert state["sls_Mstar_pos_manual"] == 120.0


def test_projection_supports_selected_section_uls_and_sls() -> None:
    projection = load_analysis_action_projection(
        draft={"design_actions_source_selector": "section"},
        results={
            "design_M_uls_kNm": 75.0,
            "design_M_uls_kNm_signed": -75.0,
            "design_V_uls_kN": 42.0,
            "design_M_sls_kNm": 55.0,
            "design_M_sls_kNm_signed": -55.0,
            "design_V_sls_kN": 31.0,
        },
    )

    assert projection["design_actions_source"] == "section"
    assert projection["design_M_uls_kNm_signed"] == -75.0
    assert projection["design_M_sls_kNm_signed"] == -55.0


def test_source_round_trip_never_mutates_distinct_manual_uls_and_sls_owners() -> None:
    state = {
        "actions_mode": "manual",
        "actions_source": MANUAL_ACTIONS_SOURCE,
        "uls_Vstar": 80.0,
        "uls_Nstar": 12.0,
        "sls_Vstar": 53.0,
        "sls_Nstar": 7.0,
        "manual_uls_Vstar": 80.0,
        "manual_uls_Nstar": 12.0,
        "manual_sls_Vstar": 53.0,
        "manual_sls_Nstar": 7.0,
        "loads_edit_mode": "ULS",
        "inputs_load_Vstar_proxy": 81.0,
        INPUTS_ACTION_SOURCE_TOGGLE_KEY: True,
    }

    assert commit_action_source_toggle(
        state, INPUTS_ACTION_SOURCE_TOGGLE_KEY
    ) is True
    state.update(
        load_analysis_action_projection(
            draft={},
            results={
                "sfd_Vmax_abs_kN": 240.0,
                "sfd_Vsls_max_kN": 150.0,
            },
        )
    )

    state[INPUTS_ACTION_SOURCE_TOGGLE_KEY] = False
    assert commit_action_source_toggle(
        state, INPUTS_ACTION_SOURCE_TOGGLE_KEY
    ) is True
    assert state["manual_uls_Vstar"] == 80.0
    assert state["manual_uls_Nstar"] == 12.0
    assert state["manual_sls_Vstar"] == 53.0
    assert state["manual_sls_Nstar"] == 7.0


def test_manual_owner_migration_never_claims_load_analysis_projection() -> None:
    state = {
        "actions_mode": "design",
        "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
        "uls_Vstar": 19.5,
        "manual_uls_Vstar": 0.0,
    }

    assert migrate_missing_manual_action_owners(state) == ()
    assert state["manual_uls_Vstar"] == 0.0

    state[INPUTS_ACTION_SOURCE_TOGGLE_KEY] = False
    commit_action_source_toggle(state, INPUTS_ACTION_SOURCE_TOGGLE_KEY)
    assert migrate_missing_manual_action_owners(state) == ()
    assert state["manual_uls_Vstar"] == 0.0


def test_manual_owner_migration_is_absence_only() -> None:
    state = {
        "actions_mode": "manual",
        "actions_source": MANUAL_ACTIONS_SOURCE,
        "uls_Vstar": 80.0,
    }

    assert migrate_missing_manual_action_owners(state) == ("manual_uls_Vstar",)
    assert state["manual_uls_Vstar"] == 80.0


def test_design_mode_widgets_display_resolved_uls_and_sls_projection() -> None:
    class _FakeStreamlit:
        def __init__(self) -> None:
            self.session_state = {
                "actions_mode": "design",
                "actions_source": LOAD_ANALYSIS_ACTIONS_SOURCE,
                "design_actions_source": "max",
                "M_pos_max_uls_kNm": 135.0,
                "M_neg_min_uls_kNm": -20.0,
                "sfd_Mmax_abs_kNm": 135.0,
                "sfd_Vmax_abs_kN": 270.0,
                "M_pos_max_sls_kNm": 104.0,
                "M_neg_min_sls_kNm": -12.0,
                "sfd_Msls_max_kNm": 104.0,
                "sfd_Vsls_max_kN": 208.0,
            }

    fake = _FakeStreamlit()

    def _get_param(key: str, default=0.0):
        return fake.session_state.get(key, default)

    hydrate_design_action_widgets_from_shared(
        "uls",
        st_module=fake,
        get_param_fn=_get_param,
        state_hc_log_fn=lambda *args, **kwargs: None,
        design_action_widget_specs_fn=design_action_widget_specs,
        design_controls=True,
    )
    assert fake.session_state["inputs_load_Mstar_pos_proxy"] == 135.0
    assert fake.session_state["inputs_load_Mstar_neg_proxy"] == 20.0
    assert fake.session_state["inputs_load_Vstar_proxy"] == 270.0

    hydrate_design_action_widgets_from_shared(
        "sls",
        st_module=fake,
        get_param_fn=_get_param,
        state_hc_log_fn=lambda *args, **kwargs: None,
        design_action_widget_specs_fn=design_action_widget_specs,
        design_controls=True,
    )
    assert fake.session_state["inputs_load_Mstar_pos_proxy"] == 104.0
    assert fake.session_state["inputs_load_Mstar_neg_proxy"] == 12.0
    assert fake.session_state["inputs_load_Vstar_proxy"] == 208.0


def test_manual_widget_is_not_repainted_by_a_stale_signature_change() -> None:
    class _FakeStreamlit:
        def __init__(self) -> None:
            self.session_state = {
                "inputs_load_Mstar_pos_proxy": 75.0,
                "uls_Mstar_pos_manual": 50.0,
                "uls_Mstar_neg_manual": 0.0,
                "uls_Mstar": 50.0,
                "uls_Vstar": 0.0,
                "uls_Nstar": 0.0,
                "P_star": 0.0,
                "Tu_star": 0.0,
                "_design_action_widget_signature": ("uls", False, (50.0,)),
            }

    fake = _FakeStreamlit()

    hydrate_design_action_widgets_from_shared(
        "uls",
        st_module=fake,
        get_param_fn=lambda key, default=0.0: fake.session_state.get(key, default),
        state_hc_log_fn=lambda *args, **kwargs: None,
        design_action_widget_specs_fn=design_action_widget_specs,
        design_controls=False,
    )

    assert fake.session_state["inputs_load_Mstar_pos_proxy"] == 75.0


def test_forced_manual_hydration_projects_authoritative_value() -> None:
    class _FakeStreamlit:
        def __init__(self) -> None:
            self.session_state = {
                "inputs_load_Mstar_pos_proxy": 75.0,
                "uls_Mstar_pos_manual": 50.0,
                "uls_Mstar_neg_manual": 0.0,
                "uls_Mstar": 50.0,
                "uls_Vstar": 0.0,
                "uls_Nstar": 0.0,
                "P_star": 0.0,
                "Tu_star": 0.0,
            }

    fake = _FakeStreamlit()

    hydrate_design_action_widgets_from_shared(
        "uls",
        st_module=fake,
        get_param_fn=lambda key, default=0.0: fake.session_state.get(key, default),
        state_hc_log_fn=lambda *args, **kwargs: None,
        design_action_widget_specs_fn=design_action_widget_specs,
        design_controls=False,
        force=True,
    )

    assert fake.session_state["inputs_load_Mstar_pos_proxy"] == 50.0


def test_forced_manual_hydration_uses_dedicated_shear_owner() -> None:
    class _FakeStreamlit:
        def __init__(self) -> None:
            self.session_state = {
                "manual_uls_Vstar": 80.0,
                "uls_Vstar": 0.0,
                "uls_Mstar_pos_manual": 0.0,
                "uls_Mstar_neg_manual": 0.0,
                "uls_Nstar": 0.0,
                "P_star": 0.0,
                "Tu_star": 0.0,
            }

    fake = _FakeStreamlit()
    hydrate_design_action_widgets_from_shared(
        "uls",
        st_module=fake,
        get_param_fn=lambda key, default=0.0: fake.session_state.get(key, default),
        state_hc_log_fn=lambda *args, **kwargs: None,
        design_action_widget_specs_fn=design_action_widget_specs,
        design_controls=False,
        force=True,
    )

    assert fake.session_state["inputs_load_Vstar_proxy"] == 80.0


def test_design_actions_renderer_has_no_action_source_or_rerun_authority() -> None:
    source = inspect.getsource(render_inputs_design_actions_section)

    assert 'session_state["actions_mode"] =' not in source
    assert 'session_state["actions_source"] =' not in source
    assert "rerun_inputs_current_scope" not in source
    assert "_rerun_inputs_fragment_or_app" not in source


def test_design_action_callback_does_not_bypass_canonical_input_transaction() -> None:
    source = inspect.getsource(sync_design_action_widget_to_shared)

    assert "persist_active_beam_from_shared_fn()" not in source
    assert "persist_state_snapshot_fn()" not in source
