"""Prove that switching 2D/3D is presentation state, not beam input state."""

from __future__ import annotations

from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.workspace_rerun_policy import (
    InputsWidgetRerunClass,
    classify_inputs_widget,
    request_inputs_workspace_refresh,
)
from state_and_helpers import (
    BEAM_PROJECT_PARAM_KEYS,
    SHARED_DEFAULTS,
    TAB_KEYS,
    UI_STATE_DEFAULTS,
)


WIDGET_KEY = "inputs_fast_mode_show_3d_toggle"
DISPLAY_KEY = "fast_mode_show_3d"


def verify_diagram_choice_is_ui_only() -> None:
    assert WIDGET_KEY not in TAB_KEYS
    assert UI_STATE_DEFAULTS[DISPLAY_KEY] is False
    assert DISPLAY_KEY not in SHARED_DEFAULTS
    assert DISPLAY_KEY not in BEAM_PROJECT_PARAM_KEYS
    assert classify_inputs_widget(WIDGET_KEY) is InputsWidgetRerunClass.DISPLAY_LOCAL


def verify_diagram_choice_does_not_advance_input_revision() -> None:
    state = {"active_beam_id": "beam-1", DISPLAY_KEY: False}
    store = InputSnapshotStore(state)
    before = store.commit_active_beam(
        {"b": 250.0, "D": 300.0, "uls_Mstar": 200.0},
        changed_keys=("uls_Mstar",),
        source="engineering_input",
    )

    state[DISPLAY_KEY] = True
    refresh = request_inputs_workspace_refresh(
        state,
        WIDGET_KEY,
        revision=before.revision + 1,
    )
    after = store.current_for_beam("beam-1")

    assert refresh is None
    assert after.revision == before.revision
    assert after.engineering_hash == before.engineering_hash
    assert after.snapshot == before.snapshot
    assert state[DISPLAY_KEY] is True


def main() -> None:
    verify_diagram_choice_is_ui_only()
    verify_diagram_choice_does_not_advance_input_revision()
    print("diagram display state contract: PASS")


if __name__ == "__main__":
    main()
