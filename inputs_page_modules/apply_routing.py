"""Focused Apply-button routing coordinators for the Inputs page shell."""

from __future__ import annotations

from typing import Any, Callable

from inputs_page_modules.debug_output import safe_debug_print


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

    set_live_breadcrumb_fn("DG ALT APPLY ENTRY", {"function": "handle_apply_buttons"})
    safe_debug_print(
        "DG ALT APPLY ENTRY\n"
        "function=handle_apply_buttons\n",
        file=stderr,
        end="",
        flush=True,
    )
    session_state = st_module.session_state
    queued_apply = bool(session_state.pop("_inputs_action_apply_recommendation", False))
    if not queued_apply:
        queued_apply = bool(
            session_state.get(design_guide_apply_trace_run_id_key)
            and session_state.get("_inputs_action_apply_recommendation_payload")
        )
    if not queued_apply:
        return
    rec = session_state.get("pending_recommendation")
    if not isinstance(rec, dict) or not rec:
        rec = session_state.get("_inputs_action_apply_recommendation_payload")
    if not isinstance(rec, dict) or not rec:
        return
    if not session_state.get(design_guide_apply_trace_run_id_key):
        begin_apply_trace_fn(
            recommendation=rec,
            source="handle_apply_buttons",
        )
    outcome = apply_recommendation_result_fn(rec)
    if outcome == "dispatch_ok":
        session_state["pending_recommendation_applied_id"] = rec.get("recommendation_id")
        session_state["pending_recommendation"] = None
        session_state.pop("_inputs_action_apply_recommendation_payload", None)
        session_state["_solver_result"] = None
        return
    if outcome == "failed":
        emit_apply_trace_run_end_fn(
            stop_reason=recommendation_blocked_reason_fn(rec) or "apply_recommendation_failed",
            final_updates={},
            winner_label=str(rec.get("title") or ""),
        )
        session_state.pop("_inputs_action_apply_recommendation_payload", None)
        return
    session_state["inputs_dirty"] = True
    session_state["_inputs_dirty"] = True
    session_state["run_design_clicked"] = True
    session_state["pending_recommendation_applied_id"] = rec.get("recommendation_id")
    session_state["_solver_result"] = None
    session_state["pending_recommendation"] = None
    session_state.pop("_inputs_action_apply_recommendation_payload", None)
    record_rerun_trigger_fn(
        "apply_triggered_rerun",
        meta={"path": "handle_apply_buttons_committed_fallback"},
    )
    st_module.rerun()
