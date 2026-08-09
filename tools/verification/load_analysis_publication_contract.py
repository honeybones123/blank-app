"""Runtime contract for opt-in Load Analysis design-action publication."""

from __future__ import annotations

from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from calculations.design_actions import (  # noqa: E402
    derive_design_action_session_updates,
    resolve_design_actions_from_state,
)


def verify_mode_is_the_single_behavioral_authority() -> None:
    state = {
        "actions_mode": "design",
        # Simulate the stale compatibility label observed during navigation.
        "actions_source": "Manual design actions (inputs below)",
        "design_actions_source": "max",
        "uls_Mstar_pos_manual": 200.0,
        "uls_Mstar_neg_manual": 0.0,
        "M_pos_max_uls_kNm": 50.0,
        "M_neg_min_uls_kNm": 0.0,
        "sfd_Mmax_abs_kNm": 50.0,
        "sfd_Vmax_abs_kN": 20.0,
        "M_pos_max_sls_kNm": 35.0,
        "M_neg_min_sls_kNm": 0.0,
        "sfd_Msls_max_kNm": 35.0,
        "sfd_Vsls_max_kN": 14.0,
    }
    actions = resolve_design_actions_from_state(state)
    assert actions["source"] == "design"
    assert actions["Mu"] == 50.0
    assert actions["Vu"] == 20.0

    updates = derive_design_action_session_updates(state)
    assert updates["Mu_star"] == 50.0
    assert updates["Vu_star"] == 20.0
    assert "uls_Mstar_pos_manual" not in updates
    assert "Mu_star_pos_manual" not in updates


def _open_load_analysis_from_manual_mu(mu: float) -> AppTest:
    app = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=120)
    app.run(timeout=120)
    app.radio[0].set_value("Beam Inputs").run(timeout=120)
    app.number_input(key="inputs_load_Mstar_pos_proxy").set_value(mu).run(
        timeout=120
    )
    app.radio[0].set_value("Load Analysis").run(timeout=120)
    assert not app.exception, [item.message for item in app.exception]
    return app


def _enable_publication(app: AppTest) -> None:
    app.toggle(key="inputs_use_calculated_actions").set_value(True).run(
        timeout=120
    )
    assert not app.exception, [item.message for item in app.exception]


def verify_zero_load_publication_is_explicit_and_safe() -> None:
    app = _open_load_analysis_from_manual_mu(200.0)
    assert app.session_state["uls_Mstar_pos_manual"] == 200.0

    _enable_publication(app)

    assert app.session_state["actions_mode"] == "design"
    comparison = dict(
        app.session_state["_load_analysis_design_brain_comparison"] or {}
    )
    assert comparison.get("matches") is True, comparison
    expected = dict(comparison.get("expected") or {})
    assert expected.get("Mu") == 0.0
    assert expected.get("Vu") == 0.0
    assert expected.get("SLS_M") == 0.0
    assert expected.get("SLS_V") == 0.0
    app.toggle(key="inputs_use_calculated_actions").set_value(False).run(
        timeout=120
    )
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["actions_mode"] == "manual"
    assert app.session_state["uls_Mstar_pos_manual"] == 200.0


def verify_nonzero_load_publication_uses_solved_actions() -> None:
    app = _open_load_analysis_from_manual_mu(200.0)
    app.number_input(key="load_g_udl").set_value(10.0).run(timeout=120)
    app.number_input(key="load_q_udl").set_value(5.0).run(timeout=120)
    assert not app.exception, [item.message for item in app.exception]

    _enable_publication(app)

    comparison = dict(
        app.session_state["_load_analysis_design_brain_comparison"] or {}
    )
    assert comparison.get("matches") is True, comparison
    expected = dict(comparison.get("expected") or {})
    assert float(expected.get("Mu") or 0.0) > 0.0
    assert float(expected.get("Vu") or 0.0) > 0.0
    assert float(expected.get("SLS_M") or 0.0) > 0.0
    assert float(expected.get("SLS_V") or 0.0) > 0.0
    app.toggle(key="inputs_use_calculated_actions").set_value(False).run(
        timeout=120
    )
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["actions_mode"] == "manual"
    assert app.session_state["uls_Mstar_pos_manual"] == 200.0


def verify_publication_is_isolated_per_beam() -> None:
    app = _open_load_analysis_from_manual_mu(200.0)
    app.radio[0].set_value("Beam Inputs").run(timeout=120)
    if "beam_manager_add_button" not in {button.key for button in app.button}:
        app.button(key="batch_design_workspace_toggle_caret").click().run(
            timeout=120
        )
    app.button(key="beam_manager_add_button").click().run(timeout=120)
    assert not app.exception, [item.message for item in app.exception]
    second_beam_id = str(app.session_state["active_beam_id"])
    assert second_beam_id != "beam_1"

    app.number_input(key="inputs_load_Mstar_pos_proxy").set_value(75.0).run(
        timeout=120
    )
    app.radio[0].set_value("Load Analysis").run(timeout=120)
    _enable_publication(app)
    assert app.session_state["actions_mode"] == "design"

    app.radio[0].set_value("Beam Inputs").run(timeout=120)
    if "beam_manager_active_selector" not in {
        selectbox.key for selectbox in app.selectbox
    }:
        app.button(key="batch_design_workspace_toggle_caret").click().run(
            timeout=120
        )
    app.selectbox(key="beam_manager_active_selector").set_value("beam_1").run(
        timeout=120
    )
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["active_beam_id"] == "beam_1"
    assert app.session_state["actions_mode"] == "manual"
    assert app.session_state["uls_Mstar_pos_manual"] == 200.0

    app.selectbox(key="beam_manager_active_selector").set_value(
        second_beam_id
    ).run(timeout=120)
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["active_beam_id"] == second_beam_id
    assert app.session_state["actions_mode"] == "design"
    app.radio[0].set_value("Load Analysis").run(timeout=120)
    app.toggle(key="inputs_use_calculated_actions").set_value(False).run(
        timeout=120
    )
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["uls_Mstar_pos_manual"] == 75.0


def main() -> None:
    verify_mode_is_the_single_behavioral_authority()
    verify_zero_load_publication_is_explicit_and_safe()
    verify_nonzero_load_publication_uses_solved_actions()
    verify_publication_is_isolated_per_beam()
    print("load analysis publication contract: PASS")


if __name__ == "__main__":
    main()
