from __future__ import annotations

from pathlib import Path

from application.apply_command import execute_apply_command
from application.contracts.design_brain import AuthoritativeDesignResult
from inputs_application.apply_transaction_store import ApplyTransactionStore
from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.live_apply import execute_typed_apply


ROOT = Path(__file__).resolve().parents[1]


def _action_result() -> AuthoritativeDesignResult:
    updates = {"beam_width": 300.0, "bot_bar_count": 4}
    payload = {
        "candidate_id": "candidate-7",
        "source_candidate_id": "candidate-7",
        "family": "BENDING_OVERDESIGN_GOVERNS",
        "resolved_candidate_family_tag": "BENDING_OVERDESIGN_GOVERNS",
        "action_type": "apply_resolved_candidate",
        "resolved_candidate_action_type": "apply_resolved_candidate",
        "updates": updates,
        "resolved_candidate_updates": updates,
    }
    cta = {
        "enabled": True,
        "actionable": True,
        "apply_allowed": True,
        "action_type": "apply_resolved_candidate",
    }
    return AuthoritativeDesignResult(
        engineering_hash="engineering-1",
        governing_family="BENDING_OVERDESIGN_GOVERNS",
        family_outcome="ACTION",
        selected_updates=updates,
        final_publication={"outcome_state": "ACTION", "cta": cta},
        cta_model=cta,
        apply_payload=payload,
        publication_authority_hash="publication-1",
    )


def test_exact_published_action_dispatches_once() -> None:
    calls: list[dict] = []
    result = _action_result()

    command = execute_apply_command(
        current_result=result,
        recommendation=result.apply_payload,
        apply_fn=lambda payload: calls.append(payload) or "dispatch_ok",
    )

    assert command.status == "dispatch_ok"
    assert command.reason == "authoritative_executor_dispatched_once"
    assert len(calls) == 1


def test_apply_rejects_candidate_family_and_update_substitution() -> None:
    result = _action_result()
    for field, value, expected_reason in (
        ("candidate_id", "different", "stale_authoritative_apply_candidate"),
        ("family", "SHEAR_FAIL_GOVERNS", "stale_authoritative_apply_family"),
        (
            "resolved_candidate_updates",
            {"beam_width": 325.0},
            "stale_authoritative_apply_updates",
        ),
    ):
        payload = dict(result.apply_payload)
        payload[field] = value
        if field == "candidate_id":
            payload["source_candidate_id"] = value
        if field == "family":
            payload["resolved_candidate_family_tag"] = value
        if field == "resolved_candidate_updates":
            payload["updates"] = value
        calls: list[dict] = []

        command = execute_apply_command(
            current_result=result,
            recommendation=payload,
            apply_fn=lambda candidate: calls.append(candidate) or "dispatch_ok",
        )

        assert command.status == "failed"
        assert command.reason == expected_reason
        assert calls == []


def test_apply_cannot_reconstruct_action_authority_from_non_action_result() -> None:
    action = _action_result()
    blocked = AuthoritativeDesignResult(
        engineering_hash=action.engineering_hash,
        governing_family=action.governing_family,
        family_outcome="BLOCKED",
        final_publication={
            "outcome_state": "BLOCKED",
            "cta": {"enabled": False, "actionable": False, "apply_allowed": False},
        },
        apply_payload=action.apply_payload,
    )
    calls: list[dict] = []

    command = execute_apply_command(
        current_result=blocked,
        recommendation=action.apply_payload,
        apply_fn=lambda candidate: calls.append(candidate) or "dispatch_ok",
    )

    assert command.status == "failed"
    assert command.reason == "authoritative_result_not_action"
    assert calls == []


def test_apply_revision_evidence_is_mandatory_and_exact() -> None:
    store = ApplyTransactionStore({})
    valid, reason = store.validate_revision_expectation(
        {},
        input_revision=4,
        publication_revision=4,
        engineering_hash="engineering-1",
        publication_authority_hash="publication-1",
    )
    assert valid is False
    assert reason == "incomplete_apply_revision_expectation"

    payload = store.attach_revision_expectation(
        {},
        input_revision=4,
        publication_revision=4,
        engineering_hash="engineering-1",
        publication_authority_hash="publication-1",
    )
    valid, reason = store.validate_revision_expectation(
        payload,
        input_revision=4,
        publication_revision=4,
        engineering_hash="engineering-1",
        publication_authority_hash="publication-1",
    )
    assert valid is True
    assert reason == "apply_revision_expectation_match"


def test_apply_authority_has_no_ui_or_unrevisioned_fallback_path() -> None:
    live_apply = (ROOT / "inputs_application" / "live_apply.py").read_text(
        encoding="utf-8"
    )
    transaction_store = (
        ROOT / "inputs_application" / "apply_transaction_store.py"
    ).read_text(encoding="utf-8")

    forbidden_live_apply_authority = (
        "design_guide_primary_button_contract_enabled",
        'outcome="ACTION"',
        '"outcome": "ACTION"',
    )
    for forbidden in forbidden_live_apply_authority:
        assert forbidden not in live_apply

    assert "unrevisioned_compatibility_payload" not in transaction_store


def test_typed_apply_rejects_publication_from_previous_input_snapshot() -> None:
    session: dict = {}
    snapshots = InputSnapshotStore(session)
    snapshots.capture_draft({"beam_width": 250.0}, source="initial")
    first = snapshots.commit_draft(source="initial")
    snapshots.capture_draft({"beam_width": 300.0}, source="edited")
    second = snapshots.commit_draft(source="edited")
    assert second.revision > first.revision

    result = _action_result()
    stale_payload = {
        **dict(result.apply_payload),
        "source_input_revision": first.revision,
        "source_engineering_hash": result.engineering_hash,
    }
    stale_result = AuthoritativeDesignResult(
        **{
            **result.to_dict(),
            "apply_payload": dict(stale_payload),
        }
    )

    execution = execute_typed_apply(
        session_state=session,
        current_result=stale_result,
        recommendation=stale_payload,
        set_shared=lambda *args, **kwargs: None,
        finalize_publish=lambda *args, **kwargs: None,
        persist_active_beam=lambda: None,
    )

    assert execution.command.status == "failed"
    assert execution.command.reason == "stale_apply_candidate_source_revision"
    assert execution.mutation is None
