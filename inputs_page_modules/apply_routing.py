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
    defer_scoped_apply_rerun = bool(rec.get("_defer_scoped_apply_rerun"))
    outcome = apply_recommendation_result_fn(rec)
    dispatch_only = outcome == "dispatch_ok"
    if dispatch_only:
        apply_store.mark_dispatched(rec.get("recommendation_id"))
        if not defer_scoped_apply_rerun:
            return
    if outcome == "failed":
        emit_apply_trace_run_end_fn(
            stop_reason=recommendation_blocked_reason_fn(rec) or "apply_recommendation_failed",
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
    # Apply commits a new authoritative input transaction.  Always rebuild the
    # page shell after that boundary so the workspace context, action widgets,
    # summaries, diagrams, and Design Brain all start from the committed
    # revision.  A fragment-only rerun can retain the zero-action context from
    # the first Inputs render and temporarily project zero actions after a
    # successful cold-page Apply.
    record_rerun_trigger_fn(
        "apply_triggered_rerun",
        meta={"path": "handle_apply_buttons_committed_full_app"},
    )
    st_module.rerun(scope="app")
