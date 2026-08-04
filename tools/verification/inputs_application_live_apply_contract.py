"""Contract checks for typed Apply composition with callback-safe authority."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.live_apply import execute_typed_apply
from inputs_page_app_contracts import DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY


def main() -> int:
    session = {
        "D": 420.0,
        "design_guide_primary_button_contract_enabled": True,
        "design_guide_primary_button_contract": {
            "enabled": True,
            "selected_family_id": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        },
    }
    finalized: list[dict] = []
    persisted: list[float] = []

    def set_shared(key, value, *, source=""):
        session[key] = value

    execution = execute_typed_apply(
        session_state=session,
        current_result=None,
        recommendation={
            "recommendation_id": "candidate-479",
            "status": "ready",
            "resolved_candidate": {
                "candidate_id": "candidate-479",
                "updates": {"D": 470.0},
                "expected_util": 0.93,
            },
        },
        set_shared=set_shared,
        finalize_publish=lambda **kwargs: finalized.append(dict(kwargs)),
        persist_active_beam=lambda: persisted.append(float(session["D"])),
    )
    assert execution.command.status == "rerun_required"
    assert execution.mutation is not None
    assert execution.mutation.reason == "canonical_apply_planned:apply_resolved_candidate"
    assert session["D"] == 470.0
    assert finalized and finalized[0]["updated_keys"] == ["D"]
    assert persisted == [470.0]
    route = dict(session.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})
    assert route["post_apply_resolved_candidate_attempted"] is True
    assert route["apply_direct_resolved_candidate"] is True
    assert route["post_apply_required_checks_pass"] is True
    assert route["post_apply_any_fail"] is False
    assert route["payload_binding_match"] is True
    assert route["payload_update_match"] is True
    assert route["resolved_candidate_family_tag"] == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
    assert route["applied_updates"]["D"] == 470.0
    assert route["post_apply_preview_worst_util"] == 0.93

    geometry_session = {
        "b": 200.0,
        "design_guide_primary_button_contract_enabled": True,
        "design_guide_primary_button_contract": {
            "enabled": True,
            "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
        },
    }
    geometry_execution = execute_typed_apply(
        session_state=geometry_session,
        current_result=None,
        recommendation={
            "recommendation_id": "geometry-width-rescue",
            "status": "ready",
            "resolved_candidate_family_tag": "GEOMETRY_DETAILING_GOVERNS",
            "resolved_candidate": {
                "candidate_id": "geometry-width-rescue",
                "updates": {"b": 250.0},
            },
        },
        set_shared=lambda key, value, **kwargs: geometry_session.__setitem__(key, value),
        finalize_publish=lambda **kwargs: None,
        persist_active_beam=lambda: geometry_session.__setitem__(
            "persisted_b", geometry_session["b"]
        ),
    )
    assert geometry_execution.command.status == "rerun_required"
    geometry_route = dict(
        geometry_session.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {}
    )
    assert geometry_session["persisted_b"] == 250.0
    assert geometry_route["resolved_candidate_family_tag"] == "GEOMETRY_DETAILING_GOVERNS"
    assert geometry_route["post_apply_required_checks_pass"] is True
    assert geometry_route["applied_updates"] == {"b": 250.0}

    disabled = execute_typed_apply(
        session_state={
            "design_guide_primary_button_contract_enabled": False,
            "design_guide_primary_button_contract": {"enabled": False},
        },
        current_result=None,
        recommendation={"recommendation_id": "blocked", "updates": {"D": 500.0}},
        set_shared=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("disabled publication must not write")
        ),
        finalize_publish=lambda **kwargs: None,
        persist_active_beam=lambda: (_ for _ in ()).throw(
            AssertionError("disabled publication must not persist")
        ),
    )
    assert disabled.command.status == "failed"
    assert disabled.mutation is not None
    assert disabled.mutation.reason == "authoritative_publication_not_actionable"
    callback_session = {}
    callback = execute_typed_apply(
        session_state=callback_session,
        current_result=None,
        recommendation={
            "_source": "design_guide_primary_apply_payload",
            "family": "BENDING_FAIL_GOVERNS",
            "recommendation_id": "callback-1",
            "recommendation_envelope": {},
            "updates": {"D": 525.0},
        },
        set_shared=lambda key, value, **kwargs: callback_session.__setitem__(key, value),
        finalize_publish=lambda **kwargs: None,
        persist_active_beam=lambda: callback_session.__setitem__(
            "persisted_D", callback_session["D"]
        ),
    )
    assert callback.command.status == "rerun_required"
    assert callback_session["D"] == 525.0
    assert callback_session["persisted_D"] == 525.0

    alias_session = {
        "design_guide_primary_button_contract_enabled": True,
    }
    alias_execution = execute_typed_apply(
        session_state=alias_session,
        current_result=None,
        recommendation={
            "recommendation_id": "bottom-aliases",
            "status": "ready",
            "updates": {
                "bot1_count": 4,
                "db_bot_1": 12,
                "bot2_count": 0,
                "db_bot_2": 12,
            },
        },
        set_shared=lambda key, value, **kwargs: alias_session.__setitem__(key, value),
        finalize_publish=lambda **kwargs: None,
        persist_active_beam=lambda: alias_session.__setitem__(
            "persisted_bottom",
            (
                alias_session["bot1_count"],
                alias_session["bot_row_1_bars"],
                alias_session["db_bot_1"],
                alias_session["bot_row_1_dia"],
            ),
        ),
    )
    assert alias_execution.command.status == "rerun_required"
    assert alias_session["persisted_bottom"] == (4, 4, 12, 12)
    assert alias_session["bot_row_count"] == 1
    print("inputs_application live Apply contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
