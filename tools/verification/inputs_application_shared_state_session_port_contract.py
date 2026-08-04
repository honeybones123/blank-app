"""Contract checks for committing typed Apply mutations to shared state."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application import InputsSessionMutation, SharedStateSessionPort


def main() -> int:
    session = {
        "D": 600.0,
        "inputs_D": 600.0,
        "_cached_inputs_D": 600.0,
        "_hydrated_from_shared_map": {"inputs_D": True},
        "_auto_design_last_fingerprint": "old",
        "_inputs_action_apply_recommendation_payload": {"old": True},
    }
    writes: list[tuple[str, object, str]] = []
    finalizes: list[dict] = []
    transaction_order: list[str] = []

    def set_shared(key, value, *, source=""):
        writes.append((key, value, source))
        session[key] = value

    def finalize_publish(**kwargs):
        transaction_order.append("finalize")
        finalizes.append(dict(kwargs))
        session["run_design_clicked"] = True
        return kwargs

    def persist_active_beam():
        transaction_order.append("persist")
        assert session["D"] == 650.0
        session["persisted_active_beam_D"] = session["D"]

    port = SharedStateSessionPort(
        session_state=session,
        set_shared=set_shared,
        finalize_publish=finalize_publish,
        persist_active_beam=persist_active_beam,
    )
    mutation = InputsSessionMutation(
        updates={"D": 650.0, "not_shared": "ignored"},
        removals=(
            "_auto_design_last_fingerprint",
            "_inputs_action_apply_recommendation_payload",
        ),
        status="rerun_required",
        rerun_required=True,
    )
    port.commit(mutation)
    assert writes == [("D", 650.0, "guidance:typed_inputs_application")]
    assert session["D"] == 650.0
    assert "inputs_D" not in session
    assert "_cached_inputs_D" not in session
    assert "inputs_D" not in session["_hydrated_from_shared_map"]
    assert session["persisted_active_beam_D"] == 650.0
    assert transaction_order == ["finalize", "persist"]
    assert session["_design_guide_post_cleanup_acceptance_enabled"] is True
    assert session["_design_guide_post_cleanup_acceptance_fp"]
    assert "_auto_design_last_fingerprint" not in session
    assert "_inputs_action_apply_recommendation_payload" not in session
    assert finalizes == [
        {
            "updated_keys": ["D"],
            "source": "guidance:typed_inputs_application",
            "focus_section": "model",
            "set_run_design_clicked": True,
        }
    ]
    assert port.committed == [mutation]
    commit_probe = dict(session.get("_typed_apply_state_commit_probe") or {})
    assert "inputs_D" in commit_probe["cleared_widget_keys"]
    assert commit_probe["all_requested_updates_committed"] is True

    failed = InputsSessionMutation(
        updates={"D": 700.0},
        status="failed",
        reason="blocked",
    )
    port.commit(failed)
    assert session["D"] == 650.0
    assert writes == [("D", 650.0, "guidance:typed_inputs_application")]
    assert len(finalizes) == 1
    assert transaction_order == ["finalize", "persist"]
    print("inputs_application shared-state session port contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
