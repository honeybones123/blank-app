"""Focused Apply-button routing coordinators for the Inputs page shell."""

from __future__ import annotations

from typing import Any, Callable

from inputs_application.apply_transaction_store import ApplyTransactionStore
def handle_inputs_apply_buttons(
    *,
    st_module: Any,
    stderr: Any,
    design_guide_apply_trace_run_id_key: str,
    set_live_breadcrumb_fn: Callable[..., Any],
    begin_apply_trace_fn: Callable[..., Any],
    apply_recommendation_result_fn: Callable[[dict[str, Any]], str],
    recommendation_blocked_reason_fn: Callable[[dict[str, Any]], str | None],
    emit_apply_trace_run_end_fn: Callable[..., Any],
    record_rerun_trigger_fn: Callable[..., Any],
) -> None:
    """Dispatch a queued Design Guide Apply action without owning Apply logic."""

    session_state = st_module.session_state
    apply_store = ApplyTransactionStore(session_state)
    queued_apply = apply_store.consume_request(design_guide_apply_trace_run_id_key)
    if not queued_apply:
        return
    rec = apply_store.recommendation()
    if not isinstance(rec, dict) or not rec:
        return
    if not session_state.get(design_guide_apply_trace_run_id_key):
        begin_apply_trace_fn(
            recommendation=rec,
            source="handle_apply_buttons",
        )
    outcome = apply_recommendation_result_fn(rec)
    dispatch_only = outcome == "dispatch_ok"
    if dispatch_only:
        apply_store.mark_dispatched(rec.get("recommendation_id"))
    if outcome == "failed":
        failure_reason = (
            recommendation_blocked_reason_fn(rec)
            or str(
                dict(
                    session_state.get("_typed_inputs_apply_probe") or {}
                ).get("reason")
                or "apply_recommendation_failed"
            )
        )
        print(
            f"Inputs Apply rejected: {failure_reason}",
            file=stderr,
        )
        st_module.error(f"Apply could not complete: {failure_reason}")
        emit_apply_trace_run_end_fn(
            stop_reason=failure_reason,
            final_updates={},
            winner_label=str(rec.get("title") or ""),
        )
        apply_store.clear_payload()
        return
    if not dispatch_only:
        apply_store.mark_committed(rec.get("recommendation_id"))
        last_apply_route = dict(
            session_state.get("_design_guide_last_apply_route") or {}
        )
        emit_apply_trace_run_end_fn(
            stop_reason="typed_apply_committed",
            final_updates=dict(
                last_apply_route.get("applied_updates")
                or rec.get("updates")
                or {}
            ),
            winner_label=str(
                rec.get("title")
                or rec.get("label")
                or "Apply recommendation"
            ),
        )
    # The button callback queued this command before Streamlit re-entered the
    # workspace fragment.  The atomic mutation is therefore complete before
    # any workspace region renders.  Return normally and let this same run
    # calculate and paint the committed revision once; an explicit rerun or
    # polling wake would create a second transaction and expose intermediate
    # publications on a cold hosted session.
    record_rerun_trigger_fn(
        "apply_committed_in_current_workspace_transaction",
        meta={
            "path": "button_callback_then_single_workspace_render",
            "revision": session_state.get("_inputs_pending_input_revision"),
        },
    )
