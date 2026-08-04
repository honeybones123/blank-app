"""Prove one-click session operations preserve outputs and mutations."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import os
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    import inputs_page_app_contract_bridge as bridge
    import state_and_helpers
    from inputs_application.guidance_entrypoint import (
        build_guidance_entrypoint_runtime,
    )
    from inputs_application.one_click_runtime_provider import (
        build_partial_one_click_runtime_provider,
    )
    from inputs_application.one_click_session import (
        clear_auto_design_runtime_latches,
        consume_auto_design_invoke_after_solver_entry_confirmed,
        set_one_click_run_feedback,
        should_run_auto_design,
        pop_inputs_widget_keys_for_shared_updates,
        record_one_click_shear_publish_audit,
    )
    from inputs_application.one_click_tracing import (
        auto_design_invoke_debug_snapshot,
        tracer_one_click_action_source_summary,
    )

    initial = {
        "_solver_running": True,
        "_compute_in_progress": True,
        "auto_design_latch_owner": "one_click",
        "auto_design_invoke_consumed": True,
        "_auto_design_auto_invoke": True,
        "_auto_design_requested_at_ts": 123.0,
        "_auto_design_request_source": "button",
        "auto_design_request_source": "button",
        "auto_design_invoke_pending": True,
        "_auto_design_idle_reason": "waiting",
    }
    original_st = bridge.st
    original_state_helpers_st = state_and_helpers.st
    guidance = build_guidance_entrypoint_runtime(
        st_module=original_st,
        os_module=os,
        sys_module=sys,
    )
    checked = 0
    try:
        owned_state = deepcopy(initial)
        bridge_state = deepcopy(initial)
        owned_result = clear_auto_design_runtime_latches(
            "parity",
            session_state=owned_state,
        )
        bridge.st = SimpleNamespace(session_state=bridge_state)
        bridge_result = bridge._clear_auto_design_runtime_latches("parity")
        assert owned_result == bridge_result
        assert owned_state == bridge_state
        checked += 1

        cache_state = {
            "_recommendation_cache_a": {"value": 1},
            "_recommendation_cache_b": {"value": 2},
            "unrelated": "keep",
        }
        owned_state = deepcopy(cache_state)
        bridge_state = deepcopy(cache_state)
        owned_st = SimpleNamespace(session_state=owned_state)
        owned_provider = build_partial_one_click_runtime_provider(
            st_module=owned_st,
            guidance_runtime=guidance,
        )
        owned_removed = owned_provider._invalidate_design_guide_caches(
            reason="parity",
            updated_keys=["D"],
        )
        bridge.st = SimpleNamespace(session_state=bridge_state)
        bridge_removed = bridge._invalidate_design_guide_caches(
            reason="parity",
            updated_keys=["D"],
        )
        assert owned_removed == bridge_removed
        assert owned_state == bridge_state
        checked += 1

        owned_state = {}
        bridge_state = {}
        owned_st = SimpleNamespace(session_state=owned_state)
        owned_provider = build_partial_one_click_runtime_provider(
            st_module=owned_st,
            guidance_runtime=guidance,
        )
        owned_provider._set_design_guide_live_breadcrumb(
            "DG TRACE ENTRY",
            {"source": "parity"},
        )
        bridge.st = SimpleNamespace(session_state=bridge_state)
        bridge._set_design_guide_live_breadcrumb(
            "DG TRACE ENTRY",
            {"source": "parity"},
        )
        assert (
            owned_state["_dg_live_breadcrumb"]["label"]
            == bridge_state["_dg_live_breadcrumb"]["label"]
        )
        assert (
            owned_state["_dg_live_breadcrumb"]["extra"]
            == bridge_state["_dg_live_breadcrumb"]["extra"]
        )
        assert len(owned_state["_dg_live_breadcrumb"]["ts"]) == len(
            bridge_state["_dg_live_breadcrumb"]["ts"]
        )
        checked += 1

        snapshot = {
            key: deepcopy(value)
            for key, value in bridge.SHARED_DEFAULTS.items()
        }
        snapshot.update(
            {
                "b": 350.0,
                "D": 600.0,
                "lig_legs": 0,
                "lig_d": 0,
                "s_lig": 200.0,
            }
        )
        owned_state = {}
        owned_st = SimpleNamespace(session_state=owned_state)
        state_and_helpers.st = owned_st
        owned_provider = build_partial_one_click_runtime_provider(
            st_module=owned_st,
            guidance_runtime=guidance,
        )
        owned_provider._restore_shared_state_snapshot(
            deepcopy(snapshot),
            source="parity_restore",
        )

        bridge_state = {}
        bridge_st = SimpleNamespace(session_state=bridge_state)
        bridge.st = bridge_st
        state_and_helpers.st = bridge_st
        bridge._restore_shared_state_snapshot(
            deepcopy(snapshot),
            source="parity_restore",
        )
        for key in bridge.SHARED_DEFAULTS:
            assert owned_state.get(key) == bridge_state.get(key), key
        for key in (
            "_pending_shear_widget_seed_from_shared",
            "inputs_shear_widget_seed_requested",
            "inputs_shear_widget_seed_reason",
            "_inputs_shear_widget_seed_latest",
            "canonical_convenience_resync_valid",
            "canonical_convenience_resync_applied",
        ):
            assert owned_state.get(key) == bridge_state.get(key), key
        checked += 1

        initial_shared = deepcopy(snapshot)
        owned_state = deepcopy(initial_shared)
        owned_st = SimpleNamespace(session_state=owned_state)
        state_and_helpers.st = owned_st
        owned_provider = build_partial_one_click_runtime_provider(
            st_module=owned_st,
            guidance_runtime=guidance,
        )
        updates = {
            "D": 650.0,
            "lig_legs": 2,
            "lig_d": 12,
            "s_lig": 175.0,
            "_private": "drop",
            "not_shared": "drop",
        }
        owned_provider._set_shared_updates(
            deepcopy(updates),
            source="parity_set_shared",
        )

        bridge_state = deepcopy(initial_shared)
        bridge_st = SimpleNamespace(session_state=bridge_state)
        bridge.st = bridge_st
        state_and_helpers.st = bridge_st
        bridge._set_shared_updates(
            deepcopy(updates),
            source="parity_set_shared",
        )
        for key in bridge.SHARED_DEFAULTS:
            assert owned_state.get(key) == bridge_state.get(key), key
        for key in (
            "_last_shared_update_sanitize_meta",
            "_nonshared_update_drop_audit",
            "_pending_shear_widget_seed_from_shared",
            "inputs_shear_widget_seed_requested",
            "inputs_shear_widget_seed_reason",
            "canonical_convenience_resync_valid",
            "canonical_convenience_resync_applied",
        ):
            assert owned_state.get(key) == bridge_state.get(key), key
        checked += 1

        owned_state = deepcopy(initial)
        bridge_state = deepcopy(initial)
        consume_auto_design_invoke_after_solver_entry_confirmed(
            session_state=owned_state,
            auto_invoke_key="_auto_design_auto_invoke",
            request_timestamp_key="_auto_design_requested_at_ts",
            request_source_key="_auto_design_request_source",
        )
        bridge.st = SimpleNamespace(session_state=bridge_state)
        bridge._consume_auto_design_invoke_after_solver_entry_confirmed()
        assert owned_state == bridge_state
        checked += 1

        owned_state = {}
        bridge_state = {}
        owned_debug: dict = {}
        bridge_debug: dict = {}
        kwargs = {
            "status": "committed",
            "reason": "target_band",
            "winning_label": "Increase depth",
            "winning_action_type": "geometry",
            "pre_commit_worst_util": 1.05,
            "extra_payload": {"step_count": 2},
        }
        set_one_click_run_feedback(
            session_state=owned_state,
            debug_target=owned_debug,
            **kwargs,
        )
        bridge.st = SimpleNamespace(session_state=bridge_state)
        bridge._set_one_click_run_feedback(
            debug_target=bridge_debug,
            **kwargs,
        )
        assert owned_state == bridge_state
        assert owned_debug == bridge_debug
        checked += 1

        for state in (
            {},
            {"_force_auto_redesign": True},
            {"_auto_design_auto_invoke": True},
        ):
            bridge.st = SimpleNamespace(session_state=deepcopy(state))
            owned = should_run_auto_design(
                session_state=deepcopy(state),
                auto_invoke_key="_auto_design_auto_invoke",
            )
            assert owned == bridge._should_run_auto_design()
            checked += 1

        bridge.st = SimpleNamespace(session_state=deepcopy(initial))
        owned_snapshot = auto_design_invoke_debug_snapshot(
            session_state=deepcopy(initial),
            auto_invoke_key="_auto_design_auto_invoke",
            request_source_key="_auto_design_request_source",
            request_timestamp_key="_auto_design_requested_at_ts",
        )
        assert owned_snapshot == bridge._auto_design_invoke_debug_snapshot()
        checked += 1

        bridge.st = SimpleNamespace(session_state=deepcopy(initial))
        owned_source = tracer_one_click_action_source_summary(
            ("button", 1),
            session_state=deepcopy(initial),
            auto_invoke_key="_auto_design_auto_invoke",
            request_source_key="_auto_design_request_source",
            request_timestamp_key="_auto_design_requested_at_ts",
        )
        assert owned_source == bridge._tracer_one_click_action_source_summary(
            ("button", 1)
        )
        checked += 1

        widget_initial = {
            "inputs_lig_d": 12,
            "_cached_inputs_lig_d": 12,
            "inputs_lig_legs": 2,
            "_cached_inputs_lig_legs": 2,
            "inputs_s_lig": 200.0,
            "_cached_inputs_s_lig": 200.0,
            "_hydrated_from_shared_map": {
                "inputs_lig_d": 12,
                "inputs_lig_legs": 2,
                "inputs_s_lig": 200.0,
            },
        }
        owned_state = deepcopy(widget_initial)
        bridge_state = deepcopy(widget_initial)
        owned_cleared = pop_inputs_widget_keys_for_shared_updates(
            {"lig_d": 16},
            session_state=owned_state,
        )
        bridge.st = SimpleNamespace(session_state=bridge_state)
        bridge_cleared = bridge._pop_inputs_widget_keys_for_shared_updates(
            {"lig_d": 16}
        )
        assert owned_cleared == bridge_cleared
        assert owned_state == bridge_state
        checked += 1

        audit_kwargs = {
            "stage": "post_commit",
            "source": "parity",
            "candidate_updates": {
                "lig_d": 12,
                "lig_legs": 2,
                "s_lig": 200.0,
            },
            "publish_attempted": True,
            "publish_blocked": False,
        }
        owned_state = {"lig_d": 10, "lig_legs": 2, "s_lig": 250.0}
        bridge_state = deepcopy(owned_state)
        record_one_click_shear_publish_audit(
            session_state=owned_state,
            **deepcopy(audit_kwargs),
        )
        bridge.st = SimpleNamespace(session_state=bridge_state)
        bridge._record_one_click_shear_publish_audit(
            **deepcopy(audit_kwargs)
        )
        assert owned_state == bridge_state
        checked += 1
    finally:
        bridge.st = original_st
        state_and_helpers.st = original_state_helpers_st

    print(
        "PASS: permanent one-click session runtime has exact "
        f"{checked}/14 output, mutation, cache, shared-write, rollback, widget, publication, and trace parity"
    )


if __name__ == "__main__":
    main()
