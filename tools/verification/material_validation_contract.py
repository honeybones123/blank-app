"""Runtime contract for supported and rejected material strengths."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from streamlit.testing.v1 import AppTest

from application.engineering_input_validation import EngineeringInputValidationError
from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)
from inputs_application.new_design_brain_adapter import (
    calculate_v2_authoritative_result,
)

SUPPORTED_CONCRETE = (20.0, 25.0, 32.0, 40.0, 50.0, 65.0, 80.0, 100.0)
SUPPORTED_REINFORCEMENT = (500.0,)


def _open_inputs() -> AppTest:
    app = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=120)
    app.run(timeout=120)
    app.radio[0].set_value("Beam Inputs").run(timeout=120)
    assert not app.exception, [item.message for item in app.exception]
    return app


def _assert_ready(app: AppTest) -> None:
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["_inputs_workspace_calculation_status"] in {
        "ready",
        "awaiting_inputs",
    }


def verify_supported_grade_matrix() -> None:
    app = _open_inputs()
    for concrete in SUPPORTED_CONCRETE:
        for reinforcement in SUPPORTED_REINFORCEMENT:
            app.number_input(key="inputs_fc").set_value(concrete).run(
                timeout=120
            )
            app.number_input(key="inputs_fsy").set_value(reinforcement).run(
                timeout=120
            )
            _assert_ready(app)


def _assert_rejected(app: AppTest, expected_message: str) -> None:
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["_inputs_workspace_calculation_status"] == "failed"
    assert app.session_state["_inputs_workspace_authoritative_result_present"] is False
    assert expected_message in app.session_state[
        "_inputs_workspace_calculation_error"
    ]
    assert any(expected_message in str(item.value) for item in app.error)


def verify_unsupported_grades_and_recovery() -> None:
    app = _open_inputs()
    app.number_input(key="inputs_fc").set_value(41.0).run(timeout=120)
    _assert_rejected(app, "Concrete strength is not supported.")

    app.number_input(key="inputs_fc").set_value(40.0).run(timeout=120)
    _assert_ready(app)

    for unsupported in (400.0, 600.0, 501.0):
        app.number_input(key="inputs_fsy").set_value(unsupported).run(timeout=120)
        _assert_rejected(app, "Only 500 MPa reinforcement is supported")
        app.number_input(key="inputs_fsy").set_value(500.0).run(timeout=120)
        _assert_ready(app)


def verify_unsupported_saved_beam_is_migrated_to_validation_state() -> None:
    saved_state = {
        "b": 300.0,
        "D": 500.0,
        "L": 6000.0,
        "fc": 41.0,
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
        "actions_mode": "manual",
        "uls_Mstar_pos_manual": 100.0,
    }
    try:
        calculate_v2_authoritative_result(
            engineering_snapshot=(
                build_engineering_input_snapshot_from_resolved_state(
                    saved_state
                )
            ),
            resolved_inputs=saved_state,
            input_revision=1,
        )
    except EngineeringInputValidationError as exc:
        assert str(exc) == "Concrete strength is not supported."
    else:
        raise AssertionError("unsupported saved input bypassed validation")

    for unsupported in (400.0, 600.0):
        unsupported_steel = {**saved_state, "fc": 40.0, "fsy": unsupported}
        try:
            calculate_v2_authoritative_result(
                engineering_snapshot=(
                    build_engineering_input_snapshot_from_resolved_state(
                        unsupported_steel
                    )
                ),
                resolved_inputs=unsupported_steel,
                input_revision=1,
            )
        except EngineeringInputValidationError as exc:
            assert "Only 500 MPa reinforcement is supported" in str(exc)
        else:
            raise AssertionError(
                f"unsupported saved reinforcement fsy={unsupported} bypassed validation"
            )

def main() -> None:
    verify_supported_grade_matrix()
    verify_unsupported_grades_and_recovery()
    verify_unsupported_saved_beam_is_migrated_to_validation_state()
    print("material validation contract: PASS")


if __name__ == "__main__":
    main()
