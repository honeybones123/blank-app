"""Regression contract for the Inputs Design Brain Apply rerun boundary."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import inputs_page_modules.apply_routing as routing
from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.workspace_context import InputsWorkspaceContext


class _ApplyStoreStub:
    def __init__(self, session_state):
        self.session_state = session_state

    def consume_request(self, _trace_key):
        return True

    def recommendation(self):
        return {
            "recommendation_id": "cold-mu-200",
            "title": "Apply recommendation",
            "updates": {"D": 500.0},
        }

    def mark_dispatched(self, recommendation_id):
        self.session_state["marked_dispatched"] = recommendation_id

    def mark_committed(self, recommendation_id):
        self.session_state["marked_committed"] = recommendation_id

    def clear_payload(self):
        self.session_state["cleared"] = True


def verify_committed_apply_uses_fragment_when_active() -> None:
    calls: list[tuple[str, object]] = []
    state = {
        "uls_Mstar": 200.0,
        "uls_Mstar_pos_manual": 200.0,
        "uls_Vstar": 0.0,
        "_inputs_fragment_ids_v1": {"engineering_workspace": "cold-fragment"},
    }

    class _StreamlitStub:
        session_state = state

        @staticmethod
        def rerun(*, scope):
            calls.append(("rerun", scope))

    original_store = routing.ApplyTransactionStore
    original_active = routing.active_inputs_fragment_id
    original_scoped_rerun = routing.rerun_inputs_current_scope
    routing.ApplyTransactionStore = _ApplyStoreStub
    routing.active_inputs_fragment_id = lambda: "cold-fragment"
    routing.rerun_inputs_current_scope = lambda st_module: calls.append(
        ("rerun", "fragment")
    )
    try:
        routing.handle_inputs_apply_buttons(
            st_module=_StreamlitStub(),
            stderr=None,
            design_guide_apply_trace_run_id_key="trace_id",
            set_live_breadcrumb_fn=lambda *args, **kwargs: None,
            begin_apply_trace_fn=lambda **kwargs: None,
            apply_recommendation_result_fn=lambda recommendation: "committed",
            recommendation_blocked_reason_fn=lambda recommendation: None,
            emit_apply_trace_run_end_fn=lambda **kwargs: None,
            record_rerun_trigger_fn=lambda event, meta: calls.append(
                (event, dict(meta))
            ),
        )
    finally:
        routing.ApplyTransactionStore = original_store
        routing.active_inputs_fragment_id = original_active
        routing.rerun_inputs_current_scope = original_scoped_rerun

    assert state["marked_committed"] == "cold-mu-200"
    assert state["uls_Mstar"] == 200.0
    assert state["uls_Mstar_pos_manual"] == 200.0
    assert state["uls_Vstar"] == 0.0
    assert calls == [
        (
            "apply_triggered_rerun",
            {"path": "handle_apply_buttons_committed_fragment"},
        ),
        ("rerun", "fragment"),
    ]


def verify_page_level_apply_falls_back_to_app_rerun() -> None:
    calls: list[tuple[str, object]] = []
    state = {}

    class _StreamlitStub:
        session_state = state

        @staticmethod
        def rerun(*, scope):
            calls.append(("rerun", scope))

    original_store = routing.ApplyTransactionStore
    original_active = routing.active_inputs_fragment_id
    routing.ApplyTransactionStore = _ApplyStoreStub
    routing.active_inputs_fragment_id = lambda: None
    try:
        routing.handle_inputs_apply_buttons(
            st_module=_StreamlitStub(),
            stderr=None,
            design_guide_apply_trace_run_id_key="trace_id",
            set_live_breadcrumb_fn=lambda *args, **kwargs: None,
            begin_apply_trace_fn=lambda **kwargs: None,
            apply_recommendation_result_fn=lambda recommendation: "committed",
            recommendation_blocked_reason_fn=lambda recommendation: None,
            emit_apply_trace_run_end_fn=lambda **kwargs: None,
            record_rerun_trigger_fn=lambda event, meta: calls.append(
                (event, dict(meta))
            ),
        )
    finally:
        routing.ApplyTransactionStore = original_store
        routing.active_inputs_fragment_id = original_active

    assert calls == [
        (
            "apply_triggered_rerun",
            {"path": "handle_apply_buttons_committed_app_fallback"},
        ),
        ("rerun", "app"),
    ]


def verify_fragment_context_can_refresh_to_post_apply_revision() -> None:
    state = {"active_beam_id": "beam-1"}
    store = InputSnapshotStore(state)
    before = store.commit_for_beam(
        "beam-1",
        {"uls_Mstar": 200.0, "D": 450.0},
        source="cold_first_render",
    )
    frozen_context = InputsWorkspaceContext.from_session(
        state, active_beam_id="beam-1"
    )
    after = store.commit_for_beam(
        "beam-1",
        {"uls_Mstar": 200.0, "D": 500.0},
        changed_keys=("D",),
        source="design_brain_apply",
    )
    refreshed_context = InputsWorkspaceContext.from_session(
        state, active_beam_id="beam-1"
    )

    assert before.revision == frozen_context.input_revision
    assert after.revision > frozen_context.input_revision
    assert refreshed_context.input_revision == after.revision
    assert refreshed_context.input_state.snapshot["uls_Mstar"] == 200.0
    assert refreshed_context.input_state.snapshot["D"] == 500.0


def main() -> None:
    verify_committed_apply_uses_fragment_when_active()
    verify_page_level_apply_falls_back_to_app_rerun()
    verify_fragment_context_can_refresh_to_post_apply_revision()
    print("inputs apply rerun contract: PASS")


if __name__ == "__main__":
    main()
