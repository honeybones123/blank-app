from __future__ import annotations

import ast
from pathlib import Path

from calculations.design_actions import resolve_design_actions_from_state
from engineering_page_sections.design_check_summary_policy import (
    load_analysis_action_projection,
)
from inputs_application.load_analysis_state_store import LoadAnalysisStateStore
from ui.summary_sections import build_final_summary_check_card_model


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def test_load_analysis_drafts_and_results_are_beam_owned() -> None:
    state: dict[str, object] = {"active_beam_id": "beam-a", "load_dead_udl_g": 12.5}
    store = LoadAnalysisStateStore(state)
    store.capture_widgets()
    store.publish_results(sfd_Mmax_abs_kNm=42.0)

    state["active_beam_id"] = "beam-b"
    state["load_dead_udl_g"] = 7.0
    store.capture_widgets()
    store.publish_results(sfd_Mmax_abs_kNm=19.0)

    assert store.current("beam-a").to_dict()["load_dead_udl_g"] == 12.5
    assert store.current("beam-b").to_dict()["load_dead_udl_g"] == 7.0
    assert store.results("beam-a")["sfd_Mmax_abs_kNm"] == 42.0
    assert store.results("beam-b")["sfd_Mmax_abs_kNm"] == 19.0


def test_load_analysis_widgets_restore_after_route_navigation() -> None:
    state: dict[str, object] = {"active_beam_id": "beam-a", "load_live_udl_q": 8.0}
    store = LoadAnalysisStateStore(state)
    store.capture_widgets()
    state["load_live_udl_q"] = 0.0

    restored = store.restore_widgets(route_token="route-1")

    assert restored.to_dict()["load_live_udl_q"] == 8.0
    assert state["load_live_udl_q"] == 8.0

    # A fragment rerun on the same route must preserve the new live edit.
    state["load_live_udl_q"] = 9.0
    store.restore_widgets(route_token="route-1")
    assert state["load_live_udl_q"] == 9.0

    # Returning through the router creates a new token and repairs any
    # transient shared hydration before widgets are constructed.
    state["load_live_udl_q"] = 0.0
    store.restore_widgets(route_token="route-2")
    assert state["load_live_udl_q"] == 8.0


def test_load_analysis_page_has_no_inputs_or_design_brain_publication_authority() -> None:
    source_path = RUNTIME_ROOT / "design_page_runtime.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "inputs_application.new_design_brain_adapter" not in source
    assert "inputs_use_calculated_actions" not in source
    assert "set_shared(" not in source
    assert "update_results(" not in source
    assert "calculate_v2_authoritative_result" in imports
    assert "LoadAnalysisStateStore" in imports
    assert "before_commit=load_analysis_store.capture_widgets" in source


def test_runtime_has_no_alternative_design_brain_worker_or_legacy_entrypoint() -> None:
    assert not (
        RUNTIME_ROOT / "inputs_application" / "design_brain_job_worker.py"
    ).exists()
    assert not (
        RUNTIME_ROOT / "inputs_application" / "design_brain_job_service.py"
    ).exists()
    assert not (RUNTIME_ROOT / "inputs_application" / "guidance_entrypoint.py").exists()
    assert not (
        RUNTIME_ROOT / "inputs_application" / "guidance_runtime_contracts.py"
    ).exists()


def test_load_analysis_action_projection_replaces_inputs_action_aliases() -> None:
    state = {
        "M_pos_max_uls_kNm": 100.0,
        "uls_Mstar_pos_manual": 100.0,
        "sfd_Mmax_abs_kNm": 100.0,
    }
    state.update(
        load_analysis_action_projection(
            uls_m_pos=0.0,
            uls_m_neg=0.0,
            uls_v=0.0,
            sls_m_pos=0.0,
            sls_m_neg=0.0,
            sls_v=0.0,
        )
    )

    actions = resolve_design_actions_from_state(state)

    assert actions["Mu"] == 0.0
    assert actions["Vu"] == 0.0
    assert actions["SLS_M"] == 0.0
    assert actions["SLS_V"] == 0.0


def test_load_analysis_summary_always_uses_page_solved_actions() -> None:
    source = (RUNTIME_ROOT / "design_page_runtime.py").read_text(encoding="utf-8")

    assert "load_analysis_action_projection(" in source
    assert "design_state = dict(st.session_state)" in source
    assert "design_state.update(" in source
    assert "This projection does not overwrite manual action inputs." in source


def test_explicit_no_load_summary_utilisation_cannot_fall_through_to_rows() -> None:
    model = build_final_summary_check_card_model(
        family="bending",
        rows=[
            {
                "title": "Positive bending",
                "capacity": "24.8 kNm",
                "action": "100.0 kNm",
                "util": "4.03",
                "status": "FAIL",
                "is_primary": True,
            }
        ],
        action="Mu* = 0.00 kNm",
        capacity="24.8 kNm",
        utilisation="—",
        status="INFO",
    )

    assert model["utilisation"] == "&mdash;"
    assert model["status"] == "INFO"
