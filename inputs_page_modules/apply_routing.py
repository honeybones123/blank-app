"""Focused Apply-button routing coordinators for the Inputs page shell."""

from __future__ import annotations

from typing import Any, Callable

from inputs_application.apply_transaction_store import ApplyTransactionStore
from inputs_page_modules.fragments import (
    active_inputs_fragment_id,
    current_inputs_fragment_id,
    request_inputs_fragment_wake,
    rerun_inputs_active_fragment,
)


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
    # The Apply click is handled inside the Design Brain fragment.  Wake the
    # sibling calculation and input/diagram fragments for the same committed
    # revision, then rerun only the current fragment.  If the app is running
    # without fragment support (or the fragment ids are unavailable), retain
    # the safe full-app fallback.
    # The current product path owns all Inputs regions in one unified
    # ``engineering_workspace`` fragment.  Keep the old Design Brain name as
    # a rollback-compatible fallback, but prefer the live unified owner.
    unified_fragment = current_inputs_fragment_id(
        st_module,
        "engineering_workspace",
    )
    legacy_design_fragment = current_inputs_fragment_id(
        st_module,
        "design_brain_workspace",
    )
    current_fragment = unified_fragment or legacy_design_fragment
    active_fragment = active_inputs_fragment_id()
    revision = session_state.get("_inputs_pending_input_revision")
    unified_workspace_active = bool(
        unified_fragment and current_fragment == unified_fragment
    )
    if unified_workspace_active:
        # There are no sibling fragments to wake in the unified path; the
        # current workspace rerun recomputes calculation, summary, diagram,
        # and Design Brain from the committed transaction in one pass.
        woken_fragments: list[str] = []
    else:
        woken_fragments = [
            name
            for name in (
                "engineering_calculation_workspace",
                "engineering_input_workspace",
            )
            if request_inputs_fragment_wake(
                st_module,
                name,
                revision=revision,
            )
        ]
    # A stored fragment id can survive a later full-page rerun.  It is not
    # safe to request scope="fragment" merely because that stale id exists:
    # Streamlit only permits fragment scope while a fragment body is actively
    # executing.  Require the live execution context to match the stored id.
    # The unified V2 workspace owns the Apply dispatcher inside its active
    # fragment.  Keep the command and its rerun in that same fragment so the
    # rest of the page shell does not flicker or rebuild unnecessarily.
    scoped = bool(
        current_fragment
        and active_fragment
        and current_fragment == active_fragment
        and (unified_workspace_active or len(woken_fragments) == 2)
    )
    rerun_meta = (
        {
            "path": "handle_apply_buttons_scoped_fragments",
            "scope": "fragment",
            "woken_fragments": list(woken_fragments),
            "revision": int(revision) if revision is not None else None,
        }
        if scoped
        else {"path": "handle_apply_buttons_committed_fallback"}
    )
    record_rerun_trigger_fn("apply_triggered_rerun", meta=rerun_meta)
    if not scoped:
        # A queued framework wake is the only safe refresh when Apply is
        # dispatched outside the live fragment body.  Never widen this into
        # a full-page rerun: doing so rebuilds the Inputs shell and can
        # rehydrate stale widget values over the committed snapshot.
        request_inputs_fragment_wake(
            st_module,
            "engineering_workspace",
            revision=revision,
        )
        return

    # Apply is a single transaction boundary.  Re-enter the owning page once
    # after the mutation has committed so calculation, summaries, diagram and
    # the Design Brain all resolve the new beam snapshot together.  A scoped
    # fragment rerun can leave the calculation region on the pre-Apply
    # publication (the controls update while the card stays stale); the
    # historical working V2 flow used one authoritative rerun here.
    # Re-enter only the owning workspace fragment so the committed model is
    # recalculated without rebuilding navigation and unrelated page widgets.
    try:
        st_module.rerun(scope="fragment")
    except TypeError:
        # Compatibility for test doubles/older Streamlit versions.
        st_module.rerun()
