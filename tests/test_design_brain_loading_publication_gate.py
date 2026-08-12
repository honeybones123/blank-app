from types import SimpleNamespace

from inputs_application.design_guide_fragment_store import DesignGuideFragmentState
from inputs_application.engineering_workspace import (
    _hold_interim_no_actions_publication,
    _result_has_no_design_actions,
    _settle_apply_publication_transition,
)


def _result(*, no_actions: bool, family: str = "BENDING_FAIL_GOVERNS"):
    return SimpleNamespace(
        governing_family=("NO_DESIGN_ACTIONS" if no_actions else family),
        display_model={"v2_no_design_actions": no_actions},
    )


def _active_fragment() -> DesignGuideFragmentState:
    return DesignGuideFragmentState(
        status="refreshing",
        active_publication={"selected_family": "BENDING_FAIL_GOVERNS"},
        active_workspace_revision=4,
        pending_workspace_revision=5,
    )


def test_no_actions_detection_uses_typed_display_or_family() -> None:
    assert _result_has_no_design_actions(_result(no_actions=True))
    assert _result_has_no_design_actions(
        SimpleNamespace(governing_family="NO_DESIGN_ACTIONS", display_model={})
    )
    assert not _result_has_no_design_actions(_result(no_actions=False))


def test_apply_transition_holds_only_the_interim_no_actions_result() -> None:
    state = {"_typed_inputs_apply_probe": {"status": "dispatch_ok"}}

    assert _hold_interim_no_actions_publication(
        session_state=state,
        candidate_result=_result(no_actions=True),
        fragment_state=_active_fragment(),
    )
    assert not _hold_interim_no_actions_publication(
        session_state=state,
        candidate_result=_result(no_actions=False),
        fragment_state=_active_fragment(),
    )


def test_normal_no_actions_state_is_publishable_without_apply_transition() -> None:
    assert not _hold_interim_no_actions_publication(
        session_state={},
        candidate_result=_result(no_actions=True),
        fragment_state=_active_fragment(),
    )


def test_settled_apply_does_not_block_later_intentional_no_actions() -> None:
    state = {
        "_typed_inputs_apply_probe": {
            "status": "rerun_required",
            "reason": "verified_candidate",
        }
    }
    _settle_apply_publication_transition(state)

    assert state["_typed_inputs_apply_probe"]["status"] == "settled"
    assert not _hold_interim_no_actions_publication(
        session_state=state,
        candidate_result=_result(no_actions=True),
        fragment_state=_active_fragment(),
    )


def test_empty_first_session_can_publish_real_no_actions_state() -> None:
    state = {"_typed_inputs_apply_probe": {"status": "dispatch_ok"}}
    empty_fragment = DesignGuideFragmentState(
        status="refreshing",
        pending_workspace_revision=1,
    )

    assert not _hold_interim_no_actions_publication(
        session_state=state,
        candidate_result=_result(no_actions=True),
        fragment_state=empty_fragment,
    )
