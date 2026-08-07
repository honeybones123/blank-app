"""Auto-design callback routing for the Inputs page shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from inputs_page_modules.fragments import rerun_inputs_current_scope


@dataclass(frozen=True)
class AutoDesignRoutingRuntime:
    append_design_guide_trace: Callable[..., Any]
    attach_recommendation_envelope: Callable[..., dict | None]
    clear_auto_design_runtime_latches: Callable[[str], dict]
    reconcile_design_action_widgets_with_shared: Callable[[str], list[str]]
    reconcile_inputs_shear_widgets_with_shared: Callable[[], list[str]]
    resolve_design_actions_from_state: Callable[[dict], dict]
    resolved_inputs_summary_state: Callable[[], tuple[dict, dict]]
    run_one_click_auto_design: Callable[..., dict]
    set_design_guide_live_breadcrumb: Callable[..., Any]
    shared_state_snapshot: Callable[[], dict]


def handle_inputs_auto_design(
    *,
    st_module: Any,
    stderr: Any,
    time_module: Any,
    runtime: AutoDesignRoutingRuntime,
    auto_design_auto_invoke_key: str,
    auto_design_request_source_key: str,
    record_rerun_trigger_fn: Callable[..., Any],
    persist_active_beam_from_shared_fn: Callable[[], Any],
    persist_state_snapshot_fn: Callable[[], Any],
) -> None:
    """Run the Inputs auto-design callback without owning solver logic."""

    runtime.set_design_guide_live_breadcrumb("DG HANDLE AUTO DESIGN ENTRY")
    print(
        "DG HANDLE AUTO DESIGN ENTRY\n",
        file=stderr,
        end="",
        flush=True,
    )
    session_state = st_module.session_state
    clicked = bool(session_state.get("_inputs_action_run_auto_design", False))
    invoke_pending = bool(session_state.get(auto_design_auto_invoke_key, False))
    request_source = str(
        session_state.get("auto_design_request_source")
        or session_state.get(auto_design_request_source_key)
        or ""
    ).strip()
    if not clicked and not invoke_pending:
        try:
            session_state.pop("auto_design_idle_reason", None)
            session_state.pop("_auto_design_idle_reason", None)
        except Exception:
            pass
        return
    if clicked and invoke_pending:
        try:
            session_state.pop("_inputs_action_run_auto_design", None)
            session_state.pop("_one_click_run_feedback", None)
            session_state.pop("auto_design_idle_reason", None)
            session_state.pop("_auto_design_idle_reason", None)
        except Exception:
            pass
        session_state["_solver_result"] = {
            "status": "running",
            "stop_reason": "in_progress",
            "recommendation_envelope": {
                "status": "running",
                "commit_eligible": False,
                "blocked_reason": "in_progress",
            },
        }
        session_state["auto_design_status"] = "running"
        record_rerun_trigger_fn(
            "handle_auto_design_preflight_rerun",
            meta={
                "source": request_source or "unknown",
                "invoke_pending": bool(invoke_pending),
            },
        )
        rerun_inputs_current_scope(st_module)
    selected_mode = str(session_state.get("loads_edit_mode", "ULS") or "ULS").upper()
    selected_prefix = "sls" if selected_mode == "SLS" else "uls"
    entry_trace_id = f"had_{int(time_module.time() * 1000)}"

    def _auto_design_entry_probe(stage: str) -> dict:
        shared_probe = runtime.shared_state_snapshot()
        resolved_actions = runtime.resolve_design_actions_from_state(shared_probe)
        try:
            summary_state_probe, summary_state_debug = runtime.resolved_inputs_summary_state()
        except Exception as exc:
            summary_state_probe = {"_probe_error": f"{type(exc).__name__}: {exc}"}
            summary_state_debug = {"_probe_error": f"{type(exc).__name__}: {exc}"}
        try:
            from state_and_helpers import _beam_records_dict

            active_beam_id = session_state.get("active_beam_id")
            active_beam_record = dict((_beam_records_dict().get(active_beam_id) or {}))
            active_beam_params = dict(active_beam_record.get("params") or {})
        except Exception as exc:
            active_beam_id = session_state.get("active_beam_id")
            active_beam_params = {"_probe_error": f"{type(exc).__name__}: {exc}"}
        return {
            "stage": stage,
            "selected_mode": selected_mode,
            "selected_prefix": selected_prefix,
            "widget": {
                "inputs_load_Mstar_proxy": session_state.get("inputs_load_Mstar_proxy"),
                "inputs_load_Mstar_pos_proxy": session_state.get("inputs_load_Mstar_pos_proxy"),
                "inputs_load_Mstar_neg_proxy": session_state.get("inputs_load_Mstar_neg_proxy"),
                "inputs_load_Vstar_proxy": session_state.get("inputs_load_Vstar_proxy"),
            },
            "shared": {
                "actions_mode": shared_probe.get("actions_mode"),
                "actions_source": shared_probe.get("actions_source"),
                "b": shared_probe.get("b"),
                "D": shared_probe.get("D"),
                "bot1_count": shared_probe.get("bot1_count"),
                "db_bot_1": shared_probe.get("db_bot_1"),
                "lig_d": shared_probe.get("lig_d"),
                "lig_legs": shared_probe.get("lig_legs"),
                "s_lig": shared_probe.get("s_lig"),
                "uls_Mstar": shared_probe.get("uls_Mstar"),
                "uls_Mstar_pos_manual": shared_probe.get("uls_Mstar_pos_manual"),
                "uls_Mstar_neg_manual": shared_probe.get("uls_Mstar_neg_manual"),
                "uls_Vstar": shared_probe.get("uls_Vstar"),
                "load_Mstar_proxy": shared_probe.get("load_Mstar_proxy"),
                "load_Vstar_proxy": shared_probe.get("load_Vstar_proxy"),
            },
            "summary_state": {
                "b": summary_state_probe.get("b"),
                "D": summary_state_probe.get("D"),
                "bot1_count": summary_state_probe.get("bot1_count"),
                "db_bot_1": summary_state_probe.get("db_bot_1"),
                "lig_d": summary_state_probe.get("lig_d"),
                "lig_legs": summary_state_probe.get("lig_legs"),
                "s_lig": summary_state_probe.get("s_lig"),
                "uls_Mstar": summary_state_probe.get("uls_Mstar"),
                "uls_Vstar": summary_state_probe.get("uls_Vstar"),
                "_probe_error": summary_state_probe.get("_probe_error"),
            },
            "summary_state_debug": {
                "summary_state_source": summary_state_debug.get("summary_state_source"),
                "summary_shared_only_mode": summary_state_debug.get("summary_shared_only_mode"),
                "summary_shared_only_reason": summary_state_debug.get("summary_shared_only_reason"),
                "summary_overlay_suppressed": summary_state_debug.get("summary_overlay_suppressed"),
                "summary_shared_vs_widget_diffs": dict(summary_state_debug.get("summary_shared_vs_widget_diffs") or {}),
            },
            "active_beam_record": {
                "active_beam_id": active_beam_id,
                "beam_last_hydrated_id": session_state.get("beam_last_hydrated_id"),
                "b": active_beam_params.get("b"),
                "D": active_beam_params.get("D"),
                "bot1_count": active_beam_params.get("bot1_count"),
                "db_bot_1": active_beam_params.get("db_bot_1"),
                "lig_d": active_beam_params.get("lig_d"),
                "lig_legs": active_beam_params.get("lig_legs"),
                "s_lig": active_beam_params.get("s_lig"),
                "uls_Mstar": active_beam_params.get("uls_Mstar"),
                "uls_Vstar": active_beam_params.get("uls_Vstar"),
                "_probe_error": active_beam_params.get("_probe_error"),
            },
            "resolved_actions": {
                "actions_mode": resolved_actions.get("actions_mode"),
                "actions_source": resolved_actions.get("actions_source"),
                "Mu": resolved_actions.get("Mu"),
                "Vu": resolved_actions.get("Vu"),
                "signature": list(resolved_actions.get("signature") or []),
            },
        }

    session_state["_browser_auto_design_entry_probe_before_reconcile"] = _auto_design_entry_probe(
        "before_reconcile",
    )
    try:
        runtime.append_design_guide_trace(
            "handle_auto_design_before_reconcile",
            dict(session_state.get("_browser_auto_design_entry_probe_before_reconcile") or {}),
            run_id=entry_trace_id,
            source="handle_auto_design",
        )
    except Exception:
        pass
    reconciled_action_keys = runtime.reconcile_design_action_widgets_with_shared(selected_prefix)
    reconciled_shear_keys = runtime.reconcile_inputs_shear_widgets_with_shared()
    reconciled_keys = list(dict.fromkeys(list(reconciled_action_keys or []) + list(reconciled_shear_keys or [])))
    if reconciled_keys:
        try:
            persist_active_beam_from_shared_fn()
        except Exception:
            pass
    session_state["_browser_auto_design_entry_probe_after_reconcile"] = {
        **_auto_design_entry_probe("after_reconcile"),
        "reconciled_action_keys": list(reconciled_action_keys or []),
        "reconciled_shear_keys": list(reconciled_shear_keys or []),
        "reconciled_keys": list(reconciled_keys),
    }
    try:
        runtime.append_design_guide_trace(
            "handle_auto_design_after_reconcile",
            dict(session_state.get("_browser_auto_design_entry_probe_after_reconcile") or {}),
            run_id=entry_trace_id,
            source="handle_auto_design",
        )
    except Exception:
        pass
    if session_state.get("_solver_running", False):
        stale_latch_cleared = False
        stale_latch_reason = ""
        latch_owner = str(session_state.get("auto_design_latch_owner") or "").strip()
        direct_request = request_source in {"primary_apply_button", "run_one_click_auto_design"} or clicked
        if direct_request and not bool(session_state.get("_compute_in_progress", False)):
            if not latch_owner or latch_owner == "handle_auto_design":
                clear_payload = runtime.clear_auto_design_runtime_latches(
                    "handle_auto_design:stale_solver_running_direct_request"
                )
                stale_latch_cleared = True
                stale_latch_reason = str(clear_payload.get("reason") or "")
        session_state["auto_design_stale_latch_cleared_at_entry"] = bool(stale_latch_cleared)
        session_state["auto_design_stale_latch_clear_reason"] = (
            stale_latch_reason if stale_latch_cleared else ""
        )
        if stale_latch_cleared:
            pass
        else:
            try:
                session_state["auto_design_idle_reason"] = "deferred_solver_running"
                session_state["_auto_design_idle_reason"] = "deferred_solver_running"
            except Exception:
                pass
        return
    else:
        try:
            session_state["auto_design_stale_latch_cleared_at_entry"] = False
            session_state["auto_design_stale_latch_clear_reason"] = ""
        except Exception:
            pass
    session_state["_solver_running"] = True
    session_state["auto_design_latch_owner"] = "handle_auto_design"
    try:
        pending_before = session_state.get("pending_recommendation")
        if clicked:
            session_state.pop("_inputs_action_run_auto_design", None)
        runtime.set_design_guide_live_breadcrumb("DG CALLING CANONICAL ONE CLICK")
        print(
            "DG CALLING CANONICAL ONE CLICK\n"
            "next_function=run_one_click_auto_design\n",
            file=stderr,
            end="",
            flush=True,
        )
        result = runtime.run_one_click_auto_design(entry_source="inputs_handle_auto_design")
        session_state["_solver_result"] = result
        session_state["_browser_auto_design_entry_probe_after_run"] = {
            **_auto_design_entry_probe("after_run"),
            "result_status": result.get("status") if isinstance(result, dict) else None,
            "result_stop_reason": result.get("stop_reason") if isinstance(result, dict) else None,
        }
        try:
            runtime.append_design_guide_trace(
                "handle_auto_design_after_run",
                dict(session_state.get("_browser_auto_design_entry_probe_after_run") or {}),
                run_id=entry_trace_id,
                source="handle_auto_design",
            )
        except Exception:
            pass
        if isinstance(result, dict):
            idle_r = result.get("auto_design_idle_reason")
            if idle_r:
                session_state["auto_design_idle_reason"] = idle_r
                session_state["_auto_design_idle_reason"] = idle_r
            else:
                session_state.pop("auto_design_idle_reason", None)
                session_state.pop("_auto_design_idle_reason", None)
            if "auto_design_invoke_consumed" in result:
                session_state["auto_design_invoke_consumed"] = bool(result.get("auto_design_invoke_consumed"))
        if result:
            session_state["auto_design_steps"] = list(result.get("steps") or [])
            session_state["auto_design_status"] = str(result.get("status") or "idle")
            rr = result.get("recommendation_result")
            raw = result.get("recommendation") if isinstance(result.get("recommendation"), dict) else None
            raw_meta = dict((raw or {}).get("meta") or {})
            result_envelope = result.get("recommendation_envelope")
            if not isinstance(result_envelope, dict):
                result_envelope = {}
            preserve_existing_guidance_pending = bool(
                isinstance(pending_before, dict)
                and bool(pending_before)
                and str(result.get("status") or "") == "no_actionable_full_coverage_candidate"
                and str(result.get("stop_reason") or "") == "partial_failure_coverage"
            )
            if isinstance(rr, dict) and isinstance(rr.get("updates"), dict) and rr.get("updates"):
                session_state["pending_recommendation"] = runtime.attach_recommendation_envelope(
                    {
                        **rr,
                        "_source": "auto_design",
                    },
                    source="auto_design",
                    status=str(result.get("status") or "ready"),
                    audit=result.get("one_click_commit_audit") if isinstance(result, dict) else None,
                    required_domains=result_envelope.get("required_domains"),
                )
                session_state["pending_recommendation_applied_id"] = None
            elif raw and str(raw_meta.get("status") or "").strip() == "no_action":
                session_state["pending_recommendation"] = runtime.attach_recommendation_envelope(
                    {
                        "_source": "auto_design",
                        "title": raw.get("title"),
                        "description": raw.get("description"),
                        "meta": raw.get("meta"),
                        "updates": {},
                        "source": "recommendation_engine",
                    },
                    source="auto_design",
                    status="no_action",
                    blocked_reason="no_action",
                    commit_eligible=False,
                    audit=result.get("one_click_commit_audit") if isinstance(result, dict) else None,
                    required_domains=result_envelope.get("required_domains"),
                )
                session_state["pending_recommendation_applied_id"] = None
            elif raw and isinstance(raw.get("updates"), dict) and raw.get("updates"):
                session_state["pending_recommendation"] = runtime.attach_recommendation_envelope(
                    {
                        **raw,
                        "_source": "auto_design",
                    },
                    source="auto_design",
                    status=str(result.get("status") or "ready"),
                    audit=result.get("one_click_commit_audit") if isinstance(result, dict) else None,
                    required_domains=result_envelope.get("required_domains"),
                )
                session_state["pending_recommendation_applied_id"] = None
            elif preserve_existing_guidance_pending:
                preserved = dict(pending_before)
                if not isinstance(preserved.get("recommendation_envelope"), dict):
                    preserved = runtime.attach_recommendation_envelope(
                        preserved,
                        source=str(preserved.get("_source") or "guidance"),
                        status="ready",
                    )
                session_state["pending_recommendation"] = preserved
            else:
                session_state["pending_recommendation"] = None
                session_state["pending_recommendation_applied_id"] = None
    finally:
        session_state["_solver_running"] = False
    try:
        import session_state_final_log as _ssl

        record_rerun_trigger_fn(
            "handle_auto_design_triggered_rerun",
            meta={"source": "handle_auto_design"},
        )
        _ssl.ssl_set_flag("direct_auto_design_solver_ui_detected", True)
    except Exception:
        pass
    try:
        persist_active_beam_from_shared_fn()
    except Exception:
        pass
    try:
        persist_state_snapshot_fn()
    except Exception:
        pass
    session_state["_force_inputs_widget_reseed_once"] = True
    rerun_inputs_current_scope(st_module)
