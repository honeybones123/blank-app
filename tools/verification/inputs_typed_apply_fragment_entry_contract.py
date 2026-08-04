"""Prove queued CTA intent is executed outside its Streamlit callback."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.apply_routing import handle_inputs_apply_buttons


class _RerunRequested(RuntimeError):
    pass


class _FakeStreamlit:
    def __init__(self, state: dict) -> None:
        self.session_state = state
        self.rerun_scopes: list[str | None] = []

    def rerun(self, *, scope: str | None = None) -> None:
        self.rerun_scopes.append(scope)
        raise _RerunRequested(scope)


def main() -> int:
    recommendation = {
        "recommendation_id": "candidate_020",
        "label": "Apply recommendation",
        "updates": {"lig_legs": 6, "s_lig": 100.0},
    }
    state = {
        "_inputs_action_apply_recommendation": True,
        "_inputs_action_apply_recommendation_payload": recommendation,
        "pending_recommendation": recommendation,
        "_design_guide_last_apply_route": {
            "applied_updates": {"lig_legs": 6, "s_lig": 100.0},
        },
    }
    fake = _FakeStreamlit(state)
    applied: list[dict] = []
    run_ends: list[dict] = []
    rerun_events: list[tuple[str, dict]] = []
    try:
        handle_inputs_apply_buttons(
            st_module=fake,
            stderr=StringIO(),
            design_guide_apply_trace_run_id_key="_trace_run_id",
            set_live_breadcrumb_fn=lambda *args, **kwargs: None,
            begin_apply_trace_fn=lambda **kwargs: state.__setitem__(
                "_trace_run_id",
                "run_1",
            ),
            apply_recommendation_result_fn=lambda rec: (
                applied.append(dict(rec))
                or "rerun_required"
            ),
            recommendation_blocked_reason_fn=lambda rec: None,
            emit_apply_trace_run_end_fn=lambda **kwargs: run_ends.append(
                dict(kwargs)
            ),
            record_rerun_trigger_fn=lambda event, meta=None: rerun_events.append(
                (event, dict(meta or {}))
            ),
        )
    except _RerunRequested:
        pass

    assert applied == [recommendation]
    assert run_ends == [
        {
            "stop_reason": "typed_apply_committed",
            "final_updates": {"lig_legs": 6, "s_lig": 100.0},
            "winner_label": "Apply recommendation",
        }
    ]
    assert fake.rerun_scopes == ["app"]
    assert rerun_events == [
        (
            "apply_triggered_rerun",
            {"path": "handle_apply_buttons_committed_fallback"},
        )
    ]
    assert "_inputs_action_apply_recommendation" not in state
    assert "_inputs_action_apply_recommendation_payload" not in state
    assert state["pending_recommendation"] is None
    print("inputs typed Apply fragment-entry contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
