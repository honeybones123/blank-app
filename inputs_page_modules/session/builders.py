from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from .contracts import SNAPSHOT_DISPLAY_HASH_FIELDS
from .models import (
    InputsAutoDesignInvokeDebugSnapshot,
    InputsBrowserRecipeActionAppliedDecision,
    InputsDesignActionResultOverlaySnapshot,
    InputsDesignGuideCachedPublicationAvailabilityDecision,
    InputsDesignGuideCachedDebugTrustDecision,
    InputsDesignGuideGuidanceCacheResult,
    InputsDesignGuideGuidanceCacheWritePlan,
    InputsDesignGuideStepHistoryDebugSummary,
    InputsDesignGuideStepHistoryResetPlan,
    InputsDesignGuideApplyStepHistoryEntryPlan,
    InputsDesignGuideApplyTraceRunEndMetaPlan,
    InputsDesignGuideApplyTraceRunEndOutcome,
    InputsDesignGuideRuntimeTraceSessionDiff,
    InputsDesignGuideRuntimeTraceSessionSnapshot,
    InputsDesignGuideSettleGateDefaultState,
    InputsDesignGuideSettleGateDelayDecision,
    InputsDesignGuideSettleGateEnabledDecision,
    InputsDesignGuideSettleGateExpensiveAllowedMark,
    InputsDesignGuideSettleGateFingerprintUpdate,
    InputsDesignGuideSettleGateSnapshotHitDecision,
    InputsDesignGuideSettleGateStabilityDecision,
    InputsDesignGuideSettleGateWaitingMark,
    InputsDesignGuideDirtyMarkPlan,
    InputsDesignGuideTransientUiClearPlan,
    InputsDesignGuideLiveBreadcrumbPayload,
    InputsDesignGuideTracerVerboseLogDecision,
    InputsHasDesignActionsOrLoadsDecision,
    InputsLandingDashboardVisibilityDecision,
    InputsLandingContextSnapshot,
    InputsModelReoWidgetMirrorOverlayPlan,
    InputsModelStateDebugPayloadSnapshot,
    InputsNormalizedShearTruthOverlaySnapshot,
    InputsCandidateSearchReuseDisabledDecision,
    InputsCandidateSearchReuseLookupResult,
    InputsCandidateSearchReuseStorePlan,
    InputsCandidateSearchReuseStaleApplyDecision,
    InputsRerunTriggerRecordPlan,
    InputsSamePageRerunNonLandingDecision,
    InputsShearWidgetMirrorOverlayPlan,
    InputsSessionEntry,
    InputsSessionSourceSnapshot,
    InputsSummaryDebugPayloadSnapshot,
    InputsSummaryStateModeMarkerSnapshot,
    InputsSummarySharedOnlyDecision,
    InputsSummarySourceShapingSnapshot,
    InputsTracerOneClickActionSourceSummary,
)


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    return str(value)


def stable_inputs_session_json(payload: Any) -> str:
    return json.dumps(
        payload,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_inputs_session_hash(payload: Any) -> str:
    return hashlib.sha256(stable_inputs_session_json(payload).encode("utf-8")).hexdigest()


def _mapping_keys(source: Mapping[str, Any] | Any) -> tuple[Any, ...]:
    try:
        return tuple(source.keys())
    except Exception:
        return ()


def _mapping_get(source: Mapping[str, Any] | Any, key: Any) -> Any:
    try:
        return source.get(key)
    except Exception:
        return "<unreadable>"


def _float_from_mapping(source: Mapping[str, Any], key: str, default: float) -> float:
    value = source.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _int_from_mapping(source: Mapping[str, Any], key: str, default: int) -> int:
    value = source.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def build_inputs_browser_recipe_action_applied_decision(
    *,
    pending_recommendation_applied: Any,
    inputs_action_apply_recommendation: Any,
    last_apply_route: Any,
) -> InputsBrowserRecipeActionAppliedDecision:
    """Resolve whether browser recipe reseeding should stop after an action.

    The page owns all session reads. This helper owns only the pure precedence
    decision once those values are supplied explicitly.
    """
    if bool(pending_recommendation_applied):
        reason = "pending_recommendation_applied_id"
    elif bool(inputs_action_apply_recommendation):
        reason = "_inputs_action_apply_recommendation"
    elif bool(last_apply_route):
        reason = "last_apply_route"
    else:
        reason = "no_action_applied"
    applied = reason != "no_action_applied"
    payload = {
        "pending_recommendation_applied": bool(pending_recommendation_applied),
        "inputs_action_apply_recommendation": bool(inputs_action_apply_recommendation),
        "last_apply_route": bool(last_apply_route),
        "action_already_applied": applied,
        "reason": reason,
    }
    return InputsBrowserRecipeActionAppliedDecision(
        action_already_applied=applied,
        reason=reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_auto_design_invoke_debug_snapshot(
    *,
    force_auto_redesign: Any,
    auto_design_auto_invoke: Any,
    auto_design_request_source: Any,
    auto_design_requested_at_ts: Any,
    auto_design_invoke_pending: Any,
) -> InputsAutoDesignInvokeDebugSnapshot:
    """Build compact auto-design invoke diagnostics from explicit values."""
    payload = {
        "force_auto_redesign": None if force_auto_redesign is None else bool(force_auto_redesign),
        "auto_design_auto_invoke": None if auto_design_auto_invoke is None else bool(auto_design_auto_invoke),
        "auto_design_request_source": auto_design_request_source,
        "auto_design_requested_at_ts": auto_design_requested_at_ts,
        "auto_design_invoke_pending": None if auto_design_invoke_pending is None else bool(auto_design_invoke_pending),
    }
    return InputsAutoDesignInvokeDebugSnapshot(
        debug_payload=payload,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_tracer_one_click_action_source_summary(
    *,
    trigger_fingerprint: Any,
    force_auto_redesign: Any,
    auto_design_auto_invoke: Any,
    auto_design_request_source: Any,
    auto_design_requested_at_ts: Any,
    auto_design_invoke_pending: Any,
) -> InputsTracerOneClickActionSourceSummary:
    """Build cheap one-click action source diagnostics from explicit values."""
    auto_design_snapshot = build_inputs_auto_design_invoke_debug_snapshot(
        force_auto_redesign=force_auto_redesign,
        auto_design_auto_invoke=auto_design_auto_invoke,
        auto_design_request_source=auto_design_request_source,
        auto_design_requested_at_ts=auto_design_requested_at_ts,
        auto_design_invoke_pending=auto_design_invoke_pending,
    )
    payload = {
        "trigger_fingerprint": None if trigger_fingerprint is None else str(trigger_fingerprint),
        **auto_design_snapshot.debug_payload,
    }
    return InputsTracerOneClickActionSourceSummary(
        summary_payload=payload,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_apply_trace_run_end_meta_plan(
    *,
    run_id: Any,
    meta: Mapping[str, Any] | None,
    recovered_run_id: Any,
    winner_label: Any,
) -> InputsDesignGuideApplyTraceRunEndMetaPlan:
    """Build recovered/default run-end trace metadata from explicit page-owned inputs."""
    meta_d = dict(meta or {})
    recovered = not bool(run_id)
    final_run_id = recovered_run_id if recovered else run_id
    if recovered:
        meta_d.setdefault("source", "design_guide_apply_trace_recovered")
        meta_d.setdefault("action_type", "apply_recommendation")
        meta_d.setdefault("title", winner_label or "Apply recommendation")
        meta_d.setdefault("starting_worst_util", None)
    payload = {
        "run_id": str(final_run_id or ""),
        "meta": meta_d,
        "recovered": bool(recovered),
    }
    return InputsDesignGuideApplyTraceRunEndMetaPlan(
        run_id=str(final_run_id or ""),
        meta=meta_d,
        recovered=bool(recovered),
        display_hash=stable_inputs_session_hash(payload),
    )



def build_inputs_design_guide_apply_trace_run_end_outcome(
    *,
    current_overview: Mapping[str, Any] | None,
    final_util_override: Any,
    final_statuses_override: Mapping[str, Any] | None,
) -> InputsDesignGuideApplyTraceRunEndOutcome:
    """Resolve run-end final util/status payload from overview and explicit overrides."""
    overview = dict(current_overview or {})
    final_util = overview.get("worst_util")
    if final_util_override is not None:
        try:
            final_util = float(final_util_override)
        except Exception:
            pass
    statuses = dict(overview.get("statuses") or {})
    if not statuses and isinstance(final_statuses_override, Mapping) and final_statuses_override:
        statuses = dict(final_statuses_override)
    payload = {
        "final_util": final_util,
        "statuses": statuses,
        "override_supplied": final_util_override is not None,
        "fallback_statuses_supplied": bool(final_statuses_override),
    }
    return InputsDesignGuideApplyTraceRunEndOutcome(
        final_util=final_util,
        statuses=statuses,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_tracer_verbose_log_decision(
    *,
    dev_mode: Any,
    tracer_debug_env: Any,
) -> InputsDesignGuideTracerVerboseLogDecision:
    """Resolve Design Guide tracer verbosity from explicit flags."""
    env_value = str(tracer_debug_env or "").strip().lower()
    env_enabled = env_value in ("1", "true", "yes", "on")
    if bool(dev_mode):
        reason = "dev_mode"
        verbose = True
    elif env_enabled:
        reason = "design_guide_tracer_debug_env"
        verbose = True
    else:
        reason = "disabled"
        verbose = False
    payload = {
        "dev_mode": bool(dev_mode),
        "tracer_debug_env": env_value,
        "verbose_log": verbose,
        "reason": reason,
    }
    return InputsDesignGuideTracerVerboseLogDecision(
        verbose_log=verbose,
        reason=reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_transient_ui_clear_plan(
    *,
    base_transient_keys: tuple[str, ...] | list[str],
    apply_banner_key: str,
    always_clear_keys: tuple[str, ...] | list[str],
    history_keys: tuple[str, ...] | list[str],
    clear_history: bool,
    preserve_apply_banner: bool,
) -> InputsDesignGuideTransientUiClearPlan:
    """Build the Design Guide transient session-key clear plan.

    The page owns the actual Streamlit session mutation. This helper owns only
    the pure key-set/default planning from explicit key names.
    """
    transient = tuple(str(key) for key in (base_transient_keys or ()))
    if not bool(preserve_apply_banner):
        transient = (*transient, str(apply_banner_key))
    always = tuple(str(key) for key in (always_clear_keys or ()))
    history = tuple(str(key) for key in (history_keys or ())) if bool(clear_history) else ()
    all_keys = (*transient, *always, *history)
    payload = {
        "transient_keys": transient,
        "always_clear_keys": always,
        "history_keys": history,
        "clear_history": bool(clear_history),
        "preserve_apply_banner": bool(preserve_apply_banner),
    }
    return InputsDesignGuideTransientUiClearPlan(
        transient_keys=transient,
        always_clear_keys=always,
        history_keys=history,
        all_keys=all_keys,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_dirty_mark_plan(
    *,
    refresh_key: str,
    clear_history: bool = False,
    preserve_apply_banner: bool = False,
) -> InputsDesignGuideDirtyMarkPlan:
    """Build the page-owned Design Guide dirty mark/clear parameters."""
    payload = {
        "refresh_key": str(refresh_key or ""),
        "refresh_value": True,
        "clear_history": bool(clear_history),
        "preserve_apply_banner": bool(preserve_apply_banner),
    }
    return InputsDesignGuideDirtyMarkPlan(
        refresh_key=str(refresh_key or ""),
        refresh_value=True,
        clear_history=bool(clear_history),
        preserve_apply_banner=bool(preserve_apply_banner),
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_cached_publication_availability_decision(
    *,
    fingerprint: Any,
    simple_cached_fp: Any,
    simple_cached_items_present: bool,
    simple_debug_complete: bool,
    cached_fp: Any,
    cached_items_present: bool,
    cached_debug_complete: bool,
) -> InputsDesignGuideCachedPublicationAvailabilityDecision:
    """Resolve whether an already-built Design Guide publication can satisfy settle-gate readiness."""
    fp_text = str(fingerprint)
    if simple_cached_fp == fingerprint and bool(simple_cached_items_present) and bool(simple_debug_complete):
        available = True
        source = "simple_guidance_cache"
    elif cached_fp == fingerprint and bool(cached_items_present) and bool(cached_debug_complete):
        available = True
        source = "guidance_cache"
    else:
        available = False
        source = "miss"
    payload = {
        "fingerprint": fp_text,
        "simple_cached_fp": str(simple_cached_fp),
        "simple_cached_items_present": bool(simple_cached_items_present),
        "simple_debug_complete": bool(simple_debug_complete),
        "cached_fp": str(cached_fp),
        "cached_items_present": bool(cached_items_present),
        "cached_debug_complete": bool(cached_debug_complete),
        "available": available,
        "source": source,
    }
    return InputsDesignGuideCachedPublicationAvailabilityDecision(
        available=available,
        source=source,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_cached_debug_trust_decision(
    *,
    bundle_complete: bool,
    debug_publication_fingerprint: Any,
    requested_fingerprint: Any,
) -> InputsDesignGuideCachedDebugTrustDecision:
    """Resolve whether a cached Design Guide debug bundle can be trusted for a request."""
    requested_text = str(requested_fingerprint)
    debug_fp = debug_publication_fingerprint
    if not bool(bundle_complete):
        trustworthy = False
        reason = "incomplete_debug_bundle"
    elif debug_fp in (None, "", requested_text):
        trustworthy = True
        reason = "complete_matching_or_unscoped_debug_bundle"
    else:
        trustworthy = False
        reason = "publication_fingerprint_mismatch"
    payload = {
        "bundle_complete": bool(bundle_complete),
        "debug_publication_fingerprint": debug_fp,
        "requested_fingerprint": requested_text,
        "trustworthy": trustworthy,
        "reason": reason,
    }
    return InputsDesignGuideCachedDebugTrustDecision(
        trustworthy=trustworthy,
        reason=reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_settle_gate_default_state(
    *,
    version: str = "2026-06-09.1",
) -> InputsDesignGuideSettleGateDefaultState:
    """Build the default Design Guide settle-gate state payload."""
    gate_state = {
        "version": str(version or "2026-06-09.1"),
        "panel_pass_count": 0,
        "expensive_publication_count": 0,
        "skipped_expensive_publication_count": 0,
        "fingerprint_changes_seen": 0,
        "first_stable_publication_timestamp": None,
    }
    return InputsDesignGuideSettleGateDefaultState(
        gate_state=gate_state,
        display_hash=stable_inputs_session_hash(gate_state),
    )


def build_inputs_design_guide_settle_gate_fingerprint_update(
    *,
    gate_state: Mapping[str, Any],
    fingerprint: Any,
    current_perf: float,
    current_timestamp: Any,
) -> InputsDesignGuideSettleGateFingerprintUpdate:
    """Build the settle-gate state transition for a newly observed fingerprint."""
    gate = dict(gate_state or {})
    fp_text = str(fingerprint)
    previous_fp = str(gate.get("current_fingerprint") or "")
    fingerprint_changed = previous_fp != fp_text
    invalidated_previous_fingerprint = bool(previous_fp and fingerprint_changed)
    if invalidated_previous_fingerprint:
        gate["fingerprint_changes_seen"] = int(gate.get("fingerprint_changes_seen", 0) or 0) + 1
    if fingerprint_changed:
        gate["current_fingerprint"] = fp_text
        gate["first_seen_perf"] = float(current_perf)
        gate["first_seen_timestamp"] = str(current_timestamp or "")
        gate["last_seen_perf"] = float(current_perf)
        gate["last_seen_timestamp"] = str(current_timestamp or "")
        gate["stable_for_fingerprint"] = False
        gate["expensive_publication_allowed_for_fingerprint"] = False
    else:
        gate["last_seen_perf"] = float(current_perf)
        gate["last_seen_timestamp"] = str(current_timestamp or "")
    fingerprint_changes_seen = int(gate.get("fingerprint_changes_seen", 0) or 0)
    payload = {
        "gate_state": gate,
        "previous_fingerprint": previous_fp,
        "current_fingerprint": fp_text,
        "fingerprint_changed": bool(fingerprint_changed),
        "invalidated_previous_fingerprint": bool(invalidated_previous_fingerprint),
        "fingerprint_changes_seen": fingerprint_changes_seen,
    }
    return InputsDesignGuideSettleGateFingerprintUpdate(
        gate_state=gate,
        previous_fingerprint=previous_fp,
        current_fingerprint=fp_text,
        fingerprint_changed=bool(fingerprint_changed),
        invalidated_previous_fingerprint=bool(invalidated_previous_fingerprint),
        fingerprint_changes_seen=fingerprint_changes_seen,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_settle_gate_stability_decision(
    *,
    gate_state: Mapping[str, Any],
    current_perf: float,
    delay_ms: int,
    snapshot_hit: bool,
    contract: str,
    contract_file: str,
) -> InputsDesignGuideSettleGateStabilityDecision:
    """Build the settle-gate stability decision from explicit timing and hit inputs."""
    gate = dict(gate_state or {})
    gate["panel_pass_count"] = int(gate.get("panel_pass_count", 0) or 0) + 1
    first_seen = float(gate.get("first_seen_perf") or float(current_perf))
    elapsed_ms = max(0.0, (float(current_perf) - first_seen) * 1000.0)
    stable = bool(snapshot_hit or elapsed_ms >= float(delay_ms))
    gate["stable_for_fingerprint"] = stable
    decision = {
        "contract_boundary_checked": True,
        "contract": str(contract or ""),
        "contract_file": str(contract_file or ""),
        "fingerprint": str(gate.get("current_fingerprint") or ""),
        "fingerprint_first_seen_timestamp": gate.get("first_seen_timestamp"),
        "fingerprint_elapsed_ms": round(elapsed_ms, 3),
        "required_settle_ms": int(delay_ms),
        "stable": stable,
        "snapshot_hit": bool(snapshot_hit),
        "expensive_publication_allowed": stable,
        "panel_pass_count": int(gate.get("panel_pass_count", 0) or 0),
        "expensive_publication_count": int(gate.get("expensive_publication_count", 0) or 0),
        "skipped_expensive_publication_count": int(
            gate.get("skipped_expensive_publication_count", 0) or 0
        ),
        "fingerprint_changes_seen": int(gate.get("fingerprint_changes_seen", 0) or 0),
        "first_stable_publication_timestamp": gate.get("first_stable_publication_timestamp"),
    }
    payload = {
        "gate_state": gate,
        "decision": decision,
        "stable": stable,
        "elapsed_ms": round(elapsed_ms, 3),
        "panel_pass_count": decision["panel_pass_count"],
    }
    return InputsDesignGuideSettleGateStabilityDecision(
        gate_state=gate,
        decision=decision,
        stable=stable,
        elapsed_ms=round(elapsed_ms, 3),
        panel_pass_count=decision["panel_pass_count"],
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_settle_gate_waiting_mark(
    *,
    gate_state: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> InputsDesignGuideSettleGateWaitingMark:
    """Build the updated settle-gate state/decision after an expensive publication wait."""
    gate = dict(gate_state or {})
    next_count = int(gate.get("skipped_expensive_publication_count", 0) or 0) + 1
    gate["skipped_expensive_publication_count"] = next_count
    next_decision = dict(decision or {})
    next_decision["skipped_expensive_publication_count"] = next_count
    payload = {
        "gate_state": gate,
        "decision": next_decision,
        "skipped_expensive_publication_count": next_count,
    }
    return InputsDesignGuideSettleGateWaitingMark(
        gate_state=gate,
        decision=next_decision,
        skipped_expensive_publication_count=next_count,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_settle_gate_expensive_allowed_mark(
    *,
    gate_state: Mapping[str, Any],
    decision: Mapping[str, Any],
    current_timestamp: Any,
) -> InputsDesignGuideSettleGateExpensiveAllowedMark:
    """Build the updated settle-gate state/decision after expensive publication is allowed."""
    gate = dict(gate_state or {})
    next_count = int(gate.get("expensive_publication_count", 0) or 0) + 1
    gate["expensive_publication_count"] = next_count
    if not gate.get("first_stable_publication_timestamp"):
        gate["first_stable_publication_timestamp"] = str(current_timestamp or "")
    gate["expensive_publication_allowed_for_fingerprint"] = True
    next_decision = dict(decision or {})
    next_decision["expensive_publication_count"] = next_count
    next_decision["first_stable_publication_timestamp"] = gate.get("first_stable_publication_timestamp")
    payload = {
        "gate_state": gate,
        "decision": next_decision,
        "expensive_publication_count": next_count,
        "first_stable_publication_timestamp": gate.get("first_stable_publication_timestamp"),
    }
    return InputsDesignGuideSettleGateExpensiveAllowedMark(
        gate_state=gate,
        decision=next_decision,
        expensive_publication_count=next_count,
        first_stable_publication_timestamp=gate.get("first_stable_publication_timestamp"),
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_settle_gate_snapshot_hit_decision(
    *,
    cached_publication_available: bool,
    snapshot_state_fingerprint: Any,
    current_state_fingerprint: Any,
) -> InputsDesignGuideSettleGateSnapshotHitDecision:
    """Resolve settle-gate snapshot hit from explicit cached/snapshot fingerprints."""
    if bool(cached_publication_available):
        hit = True
        source = "cached_publication"
    elif str(snapshot_state_fingerprint or "") and str(snapshot_state_fingerprint or "") == str(
        current_state_fingerprint or ""
    ):
        hit = True
        source = "bending_fail_publication_snapshot"
    else:
        hit = False
        source = "miss"
    payload = {
        "cached_publication_available": bool(cached_publication_available),
        "snapshot_state_fingerprint": str(snapshot_state_fingerprint or ""),
        "current_state_fingerprint": str(current_state_fingerprint or ""),
        "snapshot_hit": hit,
        "source": source,
    }
    return InputsDesignGuideSettleGateSnapshotHitDecision(
        snapshot_hit=hit,
        source=source,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_guidance_cache_result(
    *,
    fingerprint: Any,
    simple_cached_fp: Any,
    simple_cached_items: Any,
    simple_debug: Mapping[str, Any] | None,
    simple_debug_trustworthy: bool,
    cached_fp: Any,
    cached_items: Any,
    cached_debug: Mapping[str, Any] | None,
    cached_debug_trustworthy: bool,
) -> InputsDesignGuideGuidanceCacheResult:
    """Resolve the Design Guide guidance cache result from explicit cache reads."""
    if simple_cached_fp == fingerprint and simple_cached_items is not None:
        if not bool(simple_debug_trustworthy):
            items: list[dict[str, Any]] = []
            debug: dict[str, Any] = {}
            cache_hit = False
            source = "simple_cache_untrusted_debug"
        else:
            items = list(simple_cached_items or [])
            debug = dict(simple_debug or {})
            cache_hit = True
            source = "simple_guidance_cache"
    elif cached_fp != fingerprint:
        items = []
        debug = {}
        cache_hit = False
        source = "fingerprint_miss"
    elif not bool(cached_debug_trustworthy):
        items = []
        debug = {}
        cache_hit = False
        source = "guidance_cache_untrusted_debug"
    else:
        items = list(cached_items or [])
        debug = dict(cached_debug or {})
        cache_hit = True
        source = "guidance_cache"

    payload = {
        "fingerprint": str(fingerprint),
        "simple_cached_fp": str(simple_cached_fp),
        "simple_cached_items_present": simple_cached_items is not None,
        "simple_debug_trustworthy": bool(simple_debug_trustworthy),
        "cached_fp": str(cached_fp),
        "cached_items_present": cached_items is not None,
        "cached_debug_trustworthy": bool(cached_debug_trustworthy),
        "items_count": len(items),
        "cache_hit": bool(cache_hit),
        "source": source,
    }
    return InputsDesignGuideGuidanceCacheResult(
        items=items,
        debug=debug,
        cache_hit=bool(cache_hit),
        source=source,
        display_hash=stable_inputs_session_hash(payload),
    )


def _runtime_trace_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _runtime_trace_item_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": type(item).__name__}
    contract = dict(item.get("button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    resolved_candidate = dict(item.get("resolved_candidate") or {})
    evidence = dict(
        item.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved_candidate.get("candidate_search_evidence")
        or {}
    )
    return {
        "type": "dict",
        "hash": _runtime_trace_hash(item),
        "keys": sorted(str(k) for k in item.keys())[:40],
        "id": item.get("id") or item.get("candidate_id") or item.get("source_candidate_id"),
        "family": item.get("family") or item.get("check_key"),
        "selected_action_family": item.get("selected_action_family"),
        "status": item.get("status"),
        "terminal_status": item.get("terminal_status"),
        "guidance_intent": item.get("guidance_intent"),
        "action_type": item.get("action_type") or contract.get("action_type"),
        "cta_label": item.get("primary_action") or item.get("cta_label") or contract.get("label"),
        "button_contract_enabled": bool(contract.get("enabled") or contract.get("actionable")),
        "button_contract_reason": contract.get("disabled_reason") or contract.get("blocking_reason"),
        "button_contract_hash": _runtime_trace_hash(contract) if contract else None,
        "updates_hash": _runtime_trace_hash(item.get("updates") or contract.get("updates") or {}),
        "action_payload_hash": _runtime_trace_hash(action_payload) if action_payload else None,
        "resolved_candidate_hash": _runtime_trace_hash(resolved_candidate) if resolved_candidate else None,
        "candidate_search_evidence_hash": _runtime_trace_hash(evidence) if evidence else None,
        "candidate_search_evidence_keys": sorted(str(k) for k in evidence.keys())[:40],
    }


def _runtime_trace_compact_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 1:
        return {"type": type(value).__name__, "hash": _runtime_trace_hash(value)}
    if isinstance(value, dict):
        if any(k in value for k in ("button_contract", "action_payload", "resolved_candidate", "guidance_intent")):
            return _runtime_trace_item_summary(value)
        return {
            "type": "dict",
            "hash": _runtime_trace_hash(value),
            "keys": sorted(str(k) for k in value.keys())[:60],
            "family": value.get("family") or value.get("selected_family") or value.get("published_family"),
            "status": value.get("status") or value.get("terminal_status"),
            "render_reason": value.get("render_reason"),
            "action_type": value.get("action_type"),
            "enabled": value.get("enabled"),
            "actionable": value.get("actionable"),
            "blocking_reason": value.get("blocking_reason") or value.get("disabled_reason"),
            "item": _runtime_trace_item_summary(value.get("item")) if isinstance(value.get("item"), dict) else None,
            "items_count": len(value.get("items") or value.get("guidance_items") or [])
            if isinstance(value.get("items") or value.get("guidance_items"), list)
            else None,
        }
    if isinstance(value, (list, tuple)):
        return {
            "type": type(value).__name__,
            "count": len(value),
            "hash": _runtime_trace_hash(value),
            "items": [_runtime_trace_compact_value(v, depth=depth + 1) for v in list(value)[:3]],
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return {"type": type(value).__name__, "repr": repr(value)[:200]}


def _is_design_guide_runtime_trace_key(key: Any) -> bool:
    key_l = str(key).lower()
    return (
        "design_guide" in key_l
        or "_dg_" in key_l
        or "pending_recommendation" in key_l
        or "auto_design" in key_l
    )


def build_inputs_design_guide_runtime_trace_session_snapshot(
    *,
    session_entries: Mapping[Any, Any] | Any,
) -> InputsDesignGuideRuntimeTraceSessionSnapshot:
    """Build compact Design Guide runtime trace session data from explicit entries."""
    snapshot: dict[str, Any] = {}
    for key in _mapping_keys(session_entries):
        if not _is_design_guide_runtime_trace_key(key):
            continue
        snapshot[str(key)] = _runtime_trace_compact_value(_mapping_get(session_entries, key))
    return InputsDesignGuideRuntimeTraceSessionSnapshot(
        snapshot=snapshot,
        display_hash=stable_inputs_session_hash(snapshot),
    )


def build_inputs_design_guide_runtime_trace_session_diff(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> InputsDesignGuideRuntimeTraceSessionDiff:
    """Build a compact diff for two Design Guide runtime trace snapshots."""
    before_d = dict(before or {})
    after_d = dict(after or {})
    before_keys = set(before_d)
    after_keys = set(after_d)
    changed = []
    for key in sorted(before_keys & after_keys):
        if _runtime_trace_hash(before_d[key]) != _runtime_trace_hash(after_d[key]):
            changed.append(
                {
                    "key": key,
                    "before": before_d[key],
                    "after": after_d[key],
                }
            )
    diff = {
        "added": {key: after_d[key] for key in sorted(after_keys - before_keys)},
        "removed": {key: before_d[key] for key in sorted(before_keys - after_keys)},
        "changed": changed,
    }
    return InputsDesignGuideRuntimeTraceSessionDiff(
        diff=diff,
        display_hash=stable_inputs_session_hash(diff),
    )


def build_inputs_design_guide_live_breadcrumb_payload(
    *,
    label: Any,
    extra: Mapping[str, Any] | None,
    timestamp_iso: Any,
) -> InputsDesignGuideLiveBreadcrumbPayload:
    """Build the Design Guide live breadcrumb payload from explicit values."""
    payload = {
        "label": str(label),
        "extra": dict(extra or {}),
        "ts": timestamp_iso,
    }
    return InputsDesignGuideLiveBreadcrumbPayload(
        payload=payload,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_settle_gate_delay_decision(
    *,
    delay_env: Any,
    default_delay_ms: int,
) -> InputsDesignGuideSettleGateDelayDecision:
    """Resolve the Design Guide settle-gate delay from explicit values."""
    raw = str(delay_env or "").strip()
    reason = "default"
    delay_ms = int(default_delay_ms)
    if raw:
        try:
            delay_ms = max(250, min(8000, int(float(raw))))
            reason = "env"
        except Exception:
            delay_ms = int(default_delay_ms)
            reason = "invalid_env_default"
    payload = {"delay_env": raw, "default_delay_ms": int(default_delay_ms), "delay_ms": delay_ms, "reason": reason}
    return InputsDesignGuideSettleGateDelayDecision(
        delay_ms=delay_ms,
        reason=reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_settle_gate_enabled_decision(
    *,
    browser_test_mode_env: Any,
    settle_gate_enabled_env: Any,
) -> InputsDesignGuideSettleGateEnabledDecision:
    """Resolve whether the Design Guide settle gate is enabled from env flags."""
    browser_mode = str(browser_test_mode_env or "").strip().lower()
    enabled_raw = str(settle_gate_enabled_env or "").strip().lower()
    truthy = {"1", "true", "yes", "on"}
    if browser_mode in truthy:
        enabled = False
        reason = "browser_test_mode_disabled"
    elif enabled_raw in truthy:
        enabled = True
        reason = "env_enabled"
    else:
        enabled = False
        reason = "env_disabled"
    payload = {
        "browser_test_mode_env": browser_mode,
        "settle_gate_enabled_env": enabled_raw,
        "enabled": enabled,
        "reason": reason,
    }
    return InputsDesignGuideSettleGateEnabledDecision(
        enabled=enabled,
        reason=reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def _copy_session_value(value: Any) -> Any:
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def build_inputs_session_source_snapshot(
    source: Mapping[str, Any] | Any,
) -> InputsSessionSourceSnapshot:
    """Build a read-only typed snapshot from a session-like mapping.

    This mirrors the current `_inputs_audit_snapshot_state` copy semantics:
    iterate over a stable key list, deep-copy values where possible, and fall
    back to the original value when copying fails.
    """
    entries = tuple(
        InputsSessionEntry(key=str(key), value=_copy_session_value(_mapping_get(source, key)))
        for key in _mapping_keys(source)
    )
    hash_payload = tuple(
        {
            "key": entry.key,
            "value": entry.value,
        }
        for entry in entries
    )
    return InputsSessionSourceSnapshot(
        entries=entries,
        display_hash=stable_inputs_session_hash(
            tuple(
                {field: row.get(field) for field in SNAPSHOT_DISPLAY_HASH_FIELDS}
                for row in hash_payload
            )
        ),
    )


def build_inputs_summary_source_shaping_snapshot(
    *,
    base_state: Mapping[str, Any],
    source_state: Mapping[str, Any] | Any,
    input_tab_keys: Mapping[str, str],
    skip_shared_keys: set[str] | frozenset[str] | tuple[str, ...],
    skip_longitudinal_keys: set[str] | frozenset[str] | tuple[str, ...],
    skip_prefixes: tuple[str, ...],
    deferred_overlay_keys: set[str] | frozenset[str] | tuple[str, ...],
    shared_only_mode: bool,
    shared_only_reason: str,
) -> InputsSummarySourceShapingSnapshot:
    """Build the pure scalar widget-overlay source snapshot for summary state.

    This deliberately stops before page-owned shear mirror overlay, derived
    recompute, normalized shear truth overlay, UX probes, and session writes.
    """
    working = dict(base_state or {})
    overlay_applied: dict[str, dict[str, Any]] = {}
    skip_shared = set(skip_shared_keys or ())
    skip_longitudinal = set(skip_longitudinal_keys or ())
    deferred = set(deferred_overlay_keys or ())
    if not bool(shared_only_mode):
        source_keys = set(str(key) for key in _mapping_keys(source_state))
        for shared_key, widget_key in dict(input_tab_keys or {}).items():
            sk = str(shared_key or "")
            wk = str(widget_key or "")
            if not sk or not wk.startswith("inputs_"):
                continue
            if (
                sk.startswith("_")
                or sk in skip_shared
                or sk in skip_longitudinal
                or sk.startswith(tuple(skip_prefixes or ()))
            ):
                continue
            if sk in deferred:
                continue
            if wk not in source_keys:
                continue
            wval = _mapping_get(source_state, wk)
            if isinstance(wval, (dict, list, tuple, set)):
                continue
            bval = working.get(sk)
            if bval != wval:
                overlay_applied[sk] = {"from": bval, "to": wval, "widget_key": wk}
            working[sk] = wval
    hash_payload = {
        "working_state": working,
        "overlay_applied": overlay_applied,
        "shared_only_mode": bool(shared_only_mode),
        "shared_only_reason": str(shared_only_reason or ""),
    }
    return InputsSummarySourceShapingSnapshot(
        working_state=working,
        overlay_applied=overlay_applied,
        shared_only_mode=bool(shared_only_mode),
        shared_only_reason=str(shared_only_reason or ""),
        display_hash=stable_inputs_session_hash(hash_payload),
    )


def build_inputs_shear_widget_mirror_overlay_plan(
    *,
    page_slug: str,
    base_state: Mapping[str, Any],
    working_state: Mapping[str, Any],
    overlay_applied: Mapping[str, dict[str, Any]],
    widget_state: Mapping[str, Any] | Any,
) -> InputsShearWidgetMirrorOverlayPlan:
    """Plan the active-page shear widget mirror overlay from explicit inputs.

    The page remains responsible for reading Streamlit/session state. This
    helper owns only the pure overlay mutation plan and matching debug payload.
    """
    slug = str(page_slug or "")
    base = dict(base_state or {})
    working = dict(working_state or {})
    overlay = {
        str(key): dict(value)
        for key, value in dict(overlay_applied or {}).items()
        if isinstance(value, dict)
    }
    dbg: dict[str, Any] = {
        "shear_widget_overlay_applied": False,
        "shear_widget_overlay_source": "shared_only",
        "overlay_s_lig": None,
        "overlay_lig_d": None,
        "overlay_lig_legs": None,
    }
    if slug == "inputs":
        pairs = (
            ("s_lig", "inputs_s_lig"),
            ("lig_d", "inputs_lig_d"),
            ("lig_legs", "inputs_lig_legs"),
        )
        dbg["shear_widget_overlay_source"] = "inputs"
    elif slug == "shear":
        pairs = (
            ("s_lig", "shear_s_lig"),
            ("lig_d", "shear_lig_d"),
            ("lig_legs", "shear_lig_legs"),
        )
        dbg["shear_widget_overlay_source"] = "shear"
    else:
        for sk in ("s_lig", "lig_d", "lig_legs"):
            working[sk] = base.get(sk)
        dbg["overlay_s_lig"] = working.get("s_lig")
        dbg["overlay_lig_d"] = working.get("lig_d")
        dbg["overlay_lig_legs"] = working.get("lig_legs")
        return InputsShearWidgetMirrorOverlayPlan(
            working_state=working,
            overlay_applied=overlay,
            debug_payload=dbg,
            display_hash=stable_inputs_session_hash(
                {"working_state": working, "overlay_applied": overlay, "debug_payload": dbg}
            ),
        )

    source_keys = set(str(key) for key in _mapping_keys(widget_state))
    read_any = False
    for sk, wk in pairs:
        if wk not in source_keys:
            continue
        wval = _mapping_get(widget_state, wk)
        if isinstance(wval, (dict, list, tuple, set)):
            continue
        read_any = True
        bval = base.get(sk)
        working[sk] = wval
        if bval != wval:
            overlay[sk] = {"from": bval, "to": wval, "widget_key": wk}

    try:
        base_no_links = _int_from_mapping(base, "lig_legs", 0) <= 0 and _int_from_mapping(base, "lig_d", 0) <= 0
        candidate_lig_legs = _int_from_mapping(working, "lig_legs", 0)
        candidate_lig_d = _int_from_mapping(working, "lig_d", 0)
        if (
            slug == "inputs"
            and read_any
            and base_no_links
            and (
                candidate_lig_legs > 0
                or candidate_lig_d > 0
                or float(_float_from_mapping(working, "s_lig", 0.0) or 0.0) > 0.0
            )
        ):
            for sk in ("s_lig", "lig_d", "lig_legs"):
                working[sk] = base.get(sk)
                overlay.pop(sk, None)
            dbg["shear_widget_overlay_applied"] = False
            dbg["shear_widget_overlay_source"] = "inputs_stale_shear_overlay_suppressed_shared_no_links"
            dbg["overlay_s_lig"] = working.get("s_lig")
            dbg["overlay_lig_d"] = working.get("lig_d")
            dbg["overlay_lig_legs"] = working.get("lig_legs")
            return InputsShearWidgetMirrorOverlayPlan(
                working_state=working,
                overlay_applied=overlay,
                debug_payload=dbg,
                display_hash=stable_inputs_session_hash(
                    {"working_state": working, "overlay_applied": overlay, "debug_payload": dbg}
                ),
            )
    except Exception:
        pass

    dbg["shear_widget_overlay_applied"] = bool(read_any)
    dbg["overlay_s_lig"] = working.get("s_lig")
    dbg["overlay_lig_d"] = working.get("lig_d")
    dbg["overlay_lig_legs"] = working.get("lig_legs")
    return InputsShearWidgetMirrorOverlayPlan(
        working_state=working,
        overlay_applied=overlay,
        debug_payload=dbg,
        display_hash=stable_inputs_session_hash(
            {"working_state": working, "overlay_applied": overlay, "debug_payload": dbg}
        ),
    )


def build_inputs_model_reo_widget_mirror_overlay_plan(
    *,
    page_slug: str,
    state: Mapping[str, Any],
    summary_debug: Mapping[str, Any] | None,
    widget_state: Mapping[str, Any] | Any,
) -> InputsModelReoWidgetMirrorOverlayPlan:
    """Plan fast-model reinforcement widget mirrors from explicit inputs.

    This stops before canonical design-state pack execution. The page remains
    responsible for session reads and any canonical pack/mirror rebuild calls.
    """
    working = dict(state or {})
    debug: dict[str, Any] = {
        "fast_model_reo_widget_overlay_applied": False,
        "fast_model_reo_widget_overlay_count": 0,
        "fast_model_reo_widget_overlay_keys": [],
        "fast_model_reo_widget_overlay_suppressed": False,
    }
    if str(page_slug or "") != "inputs":
        debug["fast_model_reo_widget_overlay_suppressed"] = True
        debug["fast_model_reo_widget_overlay_reason"] = "not_inputs_page"
        return InputsModelReoWidgetMirrorOverlayPlan(
            working_state=working,
            overlay_keys=(),
            debug_payload=debug,
            suppressed=True,
            display_hash=stable_inputs_session_hash(
                {"working_state": working, "overlay_keys": (), "debug_payload": debug, "suppressed": True}
            ),
        )

    summary = dict(summary_debug or {})
    summary_shared_only_reason = str(summary.get("summary_shared_only_reason") or "")
    if bool(summary.get("summary_shared_only_mode")) and summary_shared_only_reason != "post_force_refresh_this_run":
        debug["fast_model_reo_widget_overlay_suppressed"] = True
        debug["fast_model_reo_widget_overlay_reason"] = summary_shared_only_reason or "summary_shared_only_mode"
        return InputsModelReoWidgetMirrorOverlayPlan(
            working_state=working,
            overlay_keys=(),
            debug_payload=debug,
            suppressed=True,
            display_hash=stable_inputs_session_hash(
                {"working_state": working, "overlay_keys": (), "debug_payload": debug, "suppressed": True}
            ),
        )

    source_keys = set(str(key) for key in _mapping_keys(widget_state))
    overlay_keys: list[str] = []

    def _overlay_scalar(shared_key: str, widget_key: str, coerce) -> None:
        if widget_key not in source_keys:
            return
        raw_value = _mapping_get(widget_state, widget_key)
        if isinstance(raw_value, (dict, list, tuple, set)):
            return
        try:
            value = coerce(raw_value)
        except Exception:
            return
        if working.get(shared_key) != value:
            overlay_keys.append(shared_key)
        working[shared_key] = value

    for section in ("bot", "top"):
        _overlay_scalar(
            f"{section}_row_count",
            f"inputs_{section}_row_count",
            lambda value: max(0, int(float(value or 0))),
        )
        for row_index in range(1, 5):
            prefix = f"{section}_row_{row_index}"
            widget_prefix = f"inputs_{section}_row_{row_index}"
            _overlay_scalar(f"{prefix}_mode", f"{widget_prefix}_mode", lambda value: str(value or "Count"))
            _overlay_scalar(f"{prefix}_bars", f"{widget_prefix}_bars", lambda value: max(0, int(float(value or 0))))
            _overlay_scalar(f"{prefix}_spacing", f"{widget_prefix}_spacing", lambda value: max(0.0, float(value or 0.0)))
            _overlay_scalar(f"{prefix}_dia", f"{widget_prefix}_dia", lambda value: max(0.0, float(value or 0.0)))

    def _coords_stale_for(section: str, legacy_prefix: str) -> bool:
        coord_key = "bot_bar_coords" if section == "bot" else "top_bar_coords"
        coords = working.get(coord_key)
        if not isinstance(coords, list):
            coords = []
        try:
            b_current = max(0.0, float(working.get("b", 0.0) or 0.0))
            d_current = max(0.0, float(working.get("D", 0.0) or 0.0))
        except Exception:
            b_current = 0.0
            d_current = 0.0
        row_count = max(0, int(float(working.get(f"{section}_row_count", 1) or 0)))
        expected_total = 0
        expected_dias: set[float] = set()
        for row_index in range(1, min(row_count, 4) + 1):
            count = max(
                0,
                int(
                    float(
                        working.get(
                            f"{section}_row_{row_index}_bars",
                            working.get(f"{legacy_prefix}{row_index}_count", 0),
                        )
                        or 0
                    )
                ),
            )
            expected_total += count
            if count > 0:
                try:
                    expected_dias.add(
                        float(
                            working.get(
                                f"{section}_row_{row_index}_dia",
                                working.get(f"db_{legacy_prefix}_{row_index}", 0.0),
                            )
                            or 0.0
                        )
                    )
                except Exception:
                    pass
        if expected_total > 0 and len(coords) != expected_total:
            return True
        if expected_dias and coords:
            coord_dias = {
                float((coord or {}).get("db", 0.0) or 0.0)
                for coord in coords
                if isinstance(coord, dict)
            }
            if coord_dias and not coord_dias.issubset(expected_dias):
                return True
        for coord in coords:
            if not isinstance(coord, dict):
                continue
            try:
                x = float(coord.get("x", 0.0) or 0.0)
                y = float(coord.get("y", 0.0) or 0.0)
                db = max(0.0, float(coord.get("db", 0.0) or 0.0))
            except Exception:
                return True
            if (
                x - db / 2.0 < -1e-6
                or x + db / 2.0 > b_current + 1e-6
                or y - db / 2.0 < -1e-6
                or y + db / 2.0 > d_current + 1e-6
            ):
                return True
        return False

    coord_stale_keys: list[str] = []
    if _coords_stale_for("bot", "bot"):
        coord_stale_keys.append("bot_bar_coords_stale")
    if _coords_stale_for("top", "top"):
        coord_stale_keys.append("top_bar_coords_stale")
    overlay_keys.extend(coord_stale_keys)
    overlay_key_tuple = tuple(overlay_keys)
    return InputsModelReoWidgetMirrorOverlayPlan(
        working_state=working,
        overlay_keys=overlay_key_tuple,
        debug_payload=debug,
        suppressed=False,
        display_hash=stable_inputs_session_hash(
            {
                "working_state": working,
                "overlay_keys": overlay_key_tuple,
                "debug_payload": debug,
                "suppressed": False,
            }
        ),
    )


def build_inputs_model_state_debug_payload_snapshot(
    *,
    summary_debug: Mapping[str, Any] | None,
    model_widget_debug: Mapping[str, Any] | None,
) -> InputsModelStateDebugPayloadSnapshot:
    """Build compact debug metadata for `_resolved_inputs_model_state`."""
    summary = dict(summary_debug or {})
    widget = dict(model_widget_debug or {})
    payload = {
        "model_state_source": "resolved_inputs_model_state",
        "model_overlay_s_lig": summary.get("summary_overlay_s_lig"),
        "model_overlay_lig_d": summary.get("summary_overlay_lig_d"),
        "model_overlay_lig_legs": summary.get("summary_overlay_lig_legs"),
        "model_shared_only_mode": bool(summary.get("summary_shared_only_mode")),
        "model_shared_only_reason": summary.get("summary_shared_only_reason"),
        "fast_model_uses_overlay_state": True,
        "fast_model_overlay_lig_d": summary.get("summary_overlay_lig_d"),
        "fast_model_overlay_lig_legs": summary.get("summary_overlay_lig_legs"),
        "fast_model_overlay_s_lig": summary.get("summary_overlay_s_lig"),
        "fast_model_fingerprint_includes_shear": True,
        **widget,
    }
    return InputsModelStateDebugPayloadSnapshot(
        debug_payload=payload,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_summary_shared_only_decision(
    *,
    applying_auto_design: bool,
    force_inputs_widget_reseed_once: bool,
    pending_inputs_apply_refresh: bool,
    inputs_longitudinal_reo_force_refresh_processed_this_run: bool,
) -> InputsSummarySharedOnlyDecision:
    """Resolve the summary shared-only mode from explicit page/session flags."""
    if bool(applying_auto_design):
        mode, reason = True, "applying_auto_design"
    elif bool(force_inputs_widget_reseed_once):
        mode, reason = True, "force_inputs_widget_reseed_once"
    elif bool(pending_inputs_apply_refresh):
        mode, reason = True, "pending_inputs_apply_refresh"
    elif bool(inputs_longitudinal_reo_force_refresh_processed_this_run):
        mode, reason = True, "post_force_refresh_this_run"
    else:
        mode, reason = False, "normal_overlay"
    return InputsSummarySharedOnlyDecision(
        shared_only_mode=mode,
        reason=reason,
        display_hash=stable_inputs_session_hash(
            {
                "shared_only_mode": mode,
                "reason": reason,
                "applying_auto_design": bool(applying_auto_design),
                "force_inputs_widget_reseed_once": bool(force_inputs_widget_reseed_once),
                "pending_inputs_apply_refresh": bool(pending_inputs_apply_refresh),
                "inputs_longitudinal_reo_force_refresh_processed_this_run": bool(
                    inputs_longitudinal_reo_force_refresh_processed_this_run
                ),
            }
        ),
    )


def build_inputs_normalized_shear_truth_overlay_snapshot(
    *,
    base_state: Mapping[str, Any] | None,
    session_shear_truth_values: Mapping[str, Any] | None,
    normalized_shear_truth_values: Mapping[str, Any] | None,
) -> InputsNormalizedShearTruthOverlaySnapshot:
    """Build merged current shear truth state from explicit page/session inputs."""
    merged = dict(base_state or {})
    session_overlay = dict(session_shear_truth_values or {})
    normalized_overlay = dict(normalized_shear_truth_values or {})
    merged.update(session_overlay)
    merged.update(normalized_overlay)
    return InputsNormalizedShearTruthOverlaySnapshot(
        merged_state=merged,
        session_overlay=session_overlay,
        normalized_overlay=normalized_overlay,
        display_hash=stable_inputs_session_hash(
            {
                "merged_state": merged,
                "session_overlay": session_overlay,
                "normalized_overlay": normalized_overlay,
            }
        ),
    )


def build_inputs_same_page_rerun_non_landing_decision(
    *,
    dispatch_state: Any,
    cached_results: Mapping[str, Any] | None,
    debug_bundle: Mapping[str, Any] | None,
) -> InputsSamePageRerunNonLandingDecision:
    """Resolve whether a same-page rerun should suppress the empty landing card."""
    bundle = dict(debug_bundle or {})
    cached = dict(cached_results or {}) if isinstance(cached_results, Mapping) else {}
    reason = "no_dispatch"
    suppress = False
    if dispatch_state:
        if cached:
            suppress = True
            reason = "cached_results"
        elif isinstance(debug_bundle, Mapping):
            verifier = dict(bundle.get("final_publication_verifier_payload") or {})
            render_trace = dict(bundle.get("design_guide_render_eligibility_trace") or {})
            overview = dict(bundle.get("current_overview") or bundle.get("overview") or {})
            indicators = (
                verifier.get("publication_hash"),
                verifier.get("selected_family_id"),
                verifier.get("outcome_state"),
                render_trace.get("contract_required_design_brain_eligibility"),
                overview.get("all_key_pass"),
                overview.get("any_fail"),
                bundle.get("active_failures"),
                bundle.get("active_failure_keys"),
            )
            suppress = any(bool(value) for value in indicators)
            reason = "debug_bundle_indicator" if suppress else "no_non_landing_state"
        else:
            reason = "no_non_landing_state"
    return InputsSamePageRerunNonLandingDecision(
        should_suppress_landing=bool(suppress),
        reason=reason,
        display_hash=stable_inputs_session_hash(
            {
                "dispatch_state": bool(dispatch_state),
                "cached_results_present": bool(cached),
                "debug_bundle_present": isinstance(debug_bundle, Mapping),
                "should_suppress_landing": bool(suppress),
                "reason": reason,
            }
        ),
    )


def build_inputs_has_design_actions_or_loads_decision(
    *,
    action_values: Mapping[str, Any] | None,
    tolerance: float = 1e-15,
) -> InputsHasDesignActionsOrLoadsDecision:
    """Resolve whether action/load inputs contain any non-zero design value."""
    nonzero: list[str] = []
    tol = float(tolerance)
    for key, value in dict(action_values or {}).items():
        try:
            numeric = float(value or 0.0)
        except Exception:
            numeric = 0.0
        if abs(numeric) >= tol:
            nonzero.append(str(key))
    nonzero_keys = tuple(nonzero)
    return InputsHasDesignActionsOrLoadsDecision(
        has_design_actions_or_loads=bool(nonzero_keys),
        nonzero_keys=nonzero_keys,
        display_hash=stable_inputs_session_hash(
            {
                "has_design_actions_or_loads": bool(nonzero_keys),
                "nonzero_keys": nonzero_keys,
                "tolerance": tol,
            }
        ),
    )


def build_inputs_landing_dashboard_visibility_decision(
    *,
    same_page_rerun_has_non_landing_state: bool,
    design_action_values: Mapping[str, Any] | None,
    load_values: Mapping[str, Any] | None,
    capacity_context_matches: bool,
    tolerance: float = 1e-15,
) -> InputsLandingDashboardVisibilityDecision:
    """Resolve whether the Inputs landing dashboard should be visible."""

    def _num(value: Any) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    tol = float(tolerance)
    no_design_actions = all(
        abs(_num(value)) < tol
        for value in dict(design_action_values or {}).values()
    )
    no_loads = all(
        abs(_num(value)) < tol
        for value in dict(load_values or {}).values()
    )
    if bool(same_page_rerun_has_non_landing_state):
        show, reason = False, "same_page_rerun_has_non_landing_state"
    elif no_design_actions and no_loads:
        show = not bool(capacity_context_matches)
        reason = "empty_inputs" if show else "capacity_context_matches"
    else:
        show, reason = False, "actions_or_loads_present"
    return InputsLandingDashboardVisibilityDecision(
        show_landing_dashboard=bool(show),
        no_design_actions=bool(no_design_actions),
        no_loads=bool(no_loads),
        reason=reason,
        display_hash=stable_inputs_session_hash(
            {
                "show_landing_dashboard": bool(show),
                "no_design_actions": bool(no_design_actions),
                "no_loads": bool(no_loads),
                "same_page_rerun_has_non_landing_state": bool(same_page_rerun_has_non_landing_state),
                "capacity_context_matches": bool(capacity_context_matches),
                "reason": reason,
                "tolerance": tol,
            }
        ),
    )


def build_inputs_landing_context_snapshot(
    *,
    client_id: Any,
    active_project_id: Any,
    active_beam_id: Any,
) -> InputsLandingContextSnapshot:
    """Build the local landing-card context key from explicit page/session values."""
    context = "|".join(
        [
            str(client_id or ""),
            str(active_project_id or ""),
            str(active_beam_id or ""),
        ]
    )
    return InputsLandingContextSnapshot(
        context=context,
        display_hash=stable_inputs_session_hash(
            {
                "context": context,
                "client_id": str(client_id or ""),
                "active_project_id": str(active_project_id or ""),
                "active_beam_id": str(active_beam_id or ""),
            }
        ),
    )


def build_inputs_rerun_trigger_record_plan(
    *,
    reason: Any,
    meta: Mapping[str, Any] | None,
    existing_triggers: Any,
    timestamp: float,
    max_events: int = 24,
) -> InputsRerunTriggerRecordPlan:
    """Build trace-only rerun trigger payloads from plain inputs.

    The page owns session writes and final-log calls. This helper owns only the
    stable event/log payload shape and capped event-list materialization.
    """
    reason_text = str(reason or "unknown")
    meta_payload = {str(key): value for key, value in dict(meta or {}).items()}

    trigger_payload = {"event": reason_text, "ts": timestamp}
    trigger_payload.update(meta_payload)

    triggers = list(existing_triggers) if isinstance(existing_triggers, list) else []
    triggers.append(dict(trigger_payload))
    try:
        cap = max(int(max_events), 0)
    except Exception:
        cap = 24
    stored_triggers = triggers[-cap:] if cap else []

    log_payload = {"reason": reason_text}
    log_payload.update(meta_payload)
    ssl_trigger_reason = str(reason or "inputs_page_rerun")

    payload = {
        "trigger_payload": trigger_payload,
        "stored_triggers": stored_triggers,
        "log_payload": log_payload,
        "ssl_trigger_reason": ssl_trigger_reason,
    }
    return InputsRerunTriggerRecordPlan(
        trigger_payload=trigger_payload,
        stored_triggers=stored_triggers,
        log_payload=log_payload,
        ssl_trigger_reason=ssl_trigger_reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_guidance_cache_write_plan(
    *,
    fingerprint: Any,
    guidance_items: list[dict[str, Any]] | None,
    guidance_debug: Mapping[str, Any] | None,
    non_cache_debug_keys: set[str] | frozenset[str] | tuple[str, ...] | list[str],
) -> InputsDesignGuideGuidanceCacheWritePlan:
    """Build reusable guidance-cache values without mutating session state."""
    blocked_keys = {str(key) for key in non_cache_debug_keys or ()}
    cache_debug: dict[str, Any] = {}
    if isinstance(guidance_debug, Mapping):
        for key, value in guidance_debug.items():
            if str(key) in blocked_keys:
                continue
            try:
                cache_debug[key] = copy.deepcopy(value)
            except Exception:
                cache_debug[key] = value
    items = list(guidance_items or [])
    payload = {
        "fingerprint": fingerprint,
        "guidance_items": items,
        "cache_debug": cache_debug,
    }
    return InputsDesignGuideGuidanceCacheWritePlan(
        fingerprint=fingerprint,
        guidance_items=items,
        cache_debug=cache_debug,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_step_history_reset_plan(
    *,
    current_anchor: tuple[Any, ...] | list[Any],
    previous_anchor: Any,
) -> InputsDesignGuideStepHistoryResetPlan:
    """Plan history reset semantics from explicit anchors."""
    anchor = tuple(current_anchor or ())
    reset_history = previous_anchor is not None and previous_anchor != anchor
    payload = {"current_anchor": anchor, "reset_history": reset_history}
    return InputsDesignGuideStepHistoryResetPlan(
        current_anchor=anchor,
        reset_history=reset_history,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_step_history_debug_summary(
    *,
    history: Any,
    first_target_band_step: Any,
) -> InputsDesignGuideStepHistoryDebugSummary:
    """Build the non-authoritative step-history debug projection."""
    hist = list(history or [])
    first = first_target_band_step
    ever = first is not None
    steps_to = int(first) if first is not None else None
    latest = hist[-1] if hist else {}
    tail = hist[-10:] if len(hist) > 10 else list(hist)
    compact = []
    for entry in hist:
        if not isinstance(entry, dict):
            continue
        compact.append(
            {
                "step": entry.get("step_index"),
                "pre": entry.get("pre_apply_worst_util"),
                "post": entry.get("post_apply_worst_util"),
                "entered_band": bool(entry.get("entered_target_band_on_this_step")),
                "title": entry.get("recommendation_title"),
            }
        )
    payload = {
        "design_guide_step_history_count": len(hist),
        "design_guide_step_history_tail": tail,
        "first_target_band_step": first,
        "current_step_index": len(hist),
        "ever_entered_target_band": ever,
        "steps_to_first_target_band": steps_to,
        "latest_step_pre_util": (latest or {}).get("pre_apply_worst_util"),
        "latest_step_post_util": (latest or {}).get("post_apply_worst_util"),
        "latest_step_title": (latest or {}).get("recommendation_title"),
        "latest_step_used_resolved_payload": bool((latest or {}).get("used_resolved_payload")),
        "converged_in_one_click": bool(steps_to == 1),
        "design_guide_step_history_compact": compact,
    }
    return InputsDesignGuideStepHistoryDebugSummary(
        payload=payload,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_design_guide_apply_step_history_entry_plan(
    *,
    context: Mapping[str, Any],
    pre_overview: Mapping[str, Any] | None,
    post_overview: Mapping[str, Any] | None,
    pre_in_target_band: bool,
    post_in_target_band: bool,
    existing_step_count: int,
    first_target_band_step: Any,
    applied_at: str,
    recommendation_title: str,
    recommendation_family_tag: Any,
    recommendation_subfamilies: list[Any] | None,
    pre_apply_signature: Mapping[str, Any],
    post_apply_signature: Mapping[str, Any],
    target_util_min: float,
    target_util_max: float,
    applied_change_lines: list[str] | tuple[str, ...],
    action_type: str,
) -> InputsDesignGuideApplyStepHistoryEntryPlan:
    """Build one Design Guide Apply step-history entry from resolved page inputs."""
    pre = dict(pre_overview or {})
    post = dict(post_overview or {})
    ctx = dict(context or {})
    try:
        pre_wu = float(pre.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        pre_wu = 0.0
    try:
        post_wu = float(post.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        post_wu = 0.0
    step_index = int(existing_step_count or 0) + 1
    entered = bool(not pre_in_target_band and post_in_target_band)
    set_first = bool(entered and first_target_band_step is None)
    first_after = step_index if set_first else (int(first_target_band_step) if first_target_band_step is not None else None)
    entry = {
        "step_index": step_index,
        "applied_at": str(applied_at),
        "guidance_branch_before": ctx.get("guidance_branch_before"),
        "recommendation_title": str(recommendation_title),
        "recommendation_family_tag": recommendation_family_tag,
        "recommendation_subfamilies": recommendation_subfamilies,
        "pre_apply_worst_util": pre_wu,
        "post_apply_worst_util": post_wu,
        "pre_apply_statuses": dict(pre.get("statuses") or {}),
        "post_apply_statuses": dict(post.get("statuses") or {}),
        "pre_apply_signature": dict(pre_apply_signature or {}),
        "post_apply_signature": dict(post_apply_signature or {}),
        "pre_apply_target_band": [float(target_util_min), float(target_util_max)],
        "entered_target_band_on_this_step": entered,
        "first_target_band_step_after_apply": first_after,
        "applied_change_lines": list(applied_change_lines or []),
        "action_type": str(action_type or ""),
        "recommendation_label_at_step_start": ctx.get("recommendation_label_at_step_start"),
        "recommendation_action_type_at_step_start": ctx.get("recommendation_action_type_at_step_start"),
        "used_resolved_payload": bool(ctx.get("used_resolved_payload")),
        "one_click_candidate_available_at_step_start": bool(ctx.get("one_click_candidate_available_at_step_start")),
        "one_click_candidate_label_at_step_start": ctx.get("one_click_candidate_label_at_step_start"),
    }
    return InputsDesignGuideApplyStepHistoryEntryPlan(
        entry=entry,
        set_first_target_band_step=set_first,
        first_target_band_step_after_apply=first_after,
        display_hash=stable_inputs_session_hash(entry),
    )


def build_inputs_candidate_search_reuse_stale_apply_decision(
    *,
    expected_state_fingerprint: Any,
    current_state_fingerprint: Any,
) -> InputsCandidateSearchReuseStaleApplyDecision:
    """Resolve whether an existing Apply payload is stale from plain fingerprints."""
    expected = str(expected_state_fingerprint or "")
    current = str(current_state_fingerprint or "")
    stale = bool(expected and current and expected != current)
    reason = "stale_apply_payload_or_state_fingerprint_mismatch" if stale else None
    payload = {"stale": stale, "reason": reason, "expected": expected, "current": current}
    return InputsCandidateSearchReuseStaleApplyDecision(
        stale=stale,
        reason=reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_candidate_search_reuse_disabled_decision(
    *,
    guidance_runtime_fingerprint: Any,
    debug_enabled: bool = False,
    guidance_debug_verbose: bool | None = None,
    apply_in_flight: bool = False,
    cleanup_acceptance_enabled: bool = False,
    cleanup_acceptance_fingerprint: Any = None,
    stale_apply_reason: str | None = None,
) -> InputsCandidateSearchReuseDisabledDecision:
    """Resolve candidate-search reuse eligibility without reading page/session state."""
    reason: str | None = None
    if not guidance_runtime_fingerprint:
        reason = "missing_runtime_fingerprint"
    elif bool(debug_enabled) or bool(guidance_debug_verbose):
        reason = "debug_mode_enabled"
    elif bool(apply_in_flight):
        reason = "post_click_apply_in_flight"
    elif bool(cleanup_acceptance_enabled):
        reason = "post_click_cleanup_acceptance_enabled"
    elif cleanup_acceptance_fingerprint:
        reason = "post_click_cleanup_acceptance_fingerprint_present"
    elif stale_apply_reason:
        reason = str(stale_apply_reason)
    payload = {"disabled": bool(reason), "reason": reason}
    return InputsCandidateSearchReuseDisabledDecision(
        disabled=bool(reason),
        reason=reason,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_candidate_search_reuse_key_hash(guidance_runtime_fingerprint: Any) -> str:
    """Preserve the existing candidate-search cache-key hash format."""
    try:
        raw = json.dumps(guidance_runtime_fingerprint, sort_keys=True, default=str)
    except Exception:
        raw = repr(guidance_runtime_fingerprint)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def build_inputs_candidate_search_reuse_lookup_result(
    *,
    cache: Mapping[str, Any] | None,
    key_hash: str,
) -> InputsCandidateSearchReuseLookupResult:
    """Project a cached candidate-search payload without reading session state."""
    cache_map = dict(cache or {})
    row = dict(cache_map.get(str(key_hash or "")) or {})
    cached_payload = row.get("payload")
    if isinstance(cached_payload, dict):
        out = copy.deepcopy(cached_payload)
        debug_trace = dict(out.get("debug_trace") or {})
        debug_trace["candidate_search_reuse_decision"] = {
            "decision": "REUSE_HIT",
            "reason": "stable_no_input_reuse_key_unchanged",
            "key_hash": str(key_hash or ""),
            "source": "design_guide_candidate_search_reuse_cache",
        }
        debug_trace["candidate_search_reuse_cache_hit"] = True
        out["debug_trace"] = debug_trace
        return InputsCandidateSearchReuseLookupResult(
            payload=out,
            cache_hit=True,
            decision="REUSE_HIT",
            reason="stable_no_input_reuse_key_unchanged",
            display_hash=stable_inputs_session_hash(out),
        )
    miss = {"decision": "MISS", "reason": "missing_cached_candidate_search_result", "key_hash": str(key_hash or "")}
    return InputsCandidateSearchReuseLookupResult(
        payload=None,
        cache_hit=False,
        decision="MISS",
        reason="missing_cached_candidate_search_result",
        display_hash=stable_inputs_session_hash(miss),
    )


def build_inputs_candidate_search_reuse_store_plan(
    *,
    cache: Mapping[str, Any] | None,
    key_hash: str,
    payload: Mapping[str, Any] | None,
    recorded_at: float,
    cache_limit: int,
) -> InputsCandidateSearchReuseStorePlan:
    """Build the bounded candidate-search cache update from plain values."""
    cache_map = dict(cache or {})
    if not isinstance(payload, Mapping):
        return InputsCandidateSearchReuseStorePlan(
            cache=cache_map,
            stored=False,
            key_hash=str(key_hash or ""),
            display_hash=stable_inputs_session_hash(cache_map),
        )
    store_payload = copy.deepcopy(dict(payload))
    debug_trace = dict(store_payload.get("debug_trace") or {})
    debug_trace["candidate_search_reuse_recorded"] = True
    debug_trace["candidate_search_reuse_key_hash"] = str(key_hash or "")
    debug_trace["candidate_search_reuse_policy"] = "stable_no_input_same_key_only"
    store_payload["debug_trace"] = debug_trace
    cache_map[str(key_hash or "")] = {
        "payload": store_payload,
        "recorded_at": recorded_at,
        "policy": "stable_no_input_same_key_only",
    }
    try:
        limit = max(int(cache_limit), 0)
    except Exception:
        limit = 0
    if len(cache_map) > limit:
        ordered = sorted(
            cache_map.items(),
            key=lambda item: float(dict(item[1] or {}).get("recorded_at") or 0.0),
        )
        cache_map = dict(ordered[-limit:]) if limit else {}
    return InputsCandidateSearchReuseStorePlan(
        cache=cache_map,
        stored=True,
        key_hash=str(key_hash or ""),
        display_hash=stable_inputs_session_hash(cache_map),
    )


def build_inputs_design_action_result_overlay_snapshot(
    *,
    working_state: Mapping[str, Any],
    source_state: Mapping[str, Any] | Any,
    result_keys: tuple[str, ...] | list[str] | set[str] | frozenset[str],
    overlay_applied: Mapping[str, dict[str, Any]] | None = None,
) -> InputsDesignActionResultOverlaySnapshot:
    """Plan design-action result overlays for summary state.

    The page owns source selection and session fallback. This helper owns only
    the pure state/update projection once explicit source data is supplied.
    """
    working = dict(working_state or {})
    overlay = {
        str(key): dict(value)
        for key, value in dict(overlay_applied or {}).items()
        if isinstance(value, dict)
    }
    source_mode = str(_mapping_get(source_state, "actions_mode") or working.get("actions_mode", "") or "").strip().lower()
    working_mode = str(working.get("actions_mode", "") or "").strip().lower()
    if source_mode != "design" and working_mode != "design":
        return InputsDesignActionResultOverlaySnapshot(
            working_state=working,
            result_overlay={},
            overlay_applied=overlay,
            display_hash=stable_inputs_session_hash(
                {
                    "working_state": working,
                    "result_overlay": {},
                    "overlay_applied": overlay,
                }
            ),
        )

    result_overlay: dict[str, dict[str, Any]] = {}
    source_keys = set(str(key) for key in _mapping_keys(source_state))
    for raw_key in result_keys or ():
        key = str(raw_key or "")
        if not key or key not in source_keys:
            continue
        value = _mapping_get(source_state, key)
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        previous = working.get(key)
        if previous != value:
            result_overlay[key] = {
                "from": previous,
                "to": value,
                "source": "design_action_result",
            }
            overlay[key] = dict(result_overlay[key])
        working[key] = value

    return InputsDesignActionResultOverlaySnapshot(
        working_state=working,
        result_overlay=result_overlay,
        overlay_applied=overlay,
        display_hash=stable_inputs_session_hash(
            {
                "working_state": working,
                "result_overlay": result_overlay,
                "overlay_applied": overlay,
            }
        ),
    )


def build_inputs_summary_debug_payload_snapshot(
    *,
    base_state: Mapping[str, Any],
    resolved_state: Mapping[str, Any],
    overlay_applied: Mapping[str, dict[str, Any]],
    shear_overlay_debug: Mapping[str, Any],
    design_action_result_overlay: Mapping[str, dict[str, Any]],
    shared_only_mode: bool,
    shared_only_reason: str,
    design_guide_fingerprint: Any,
    subset_keys: tuple[str, ...] | list[str] | set[str] | frozenset[str],
) -> InputsSummaryDebugPayloadSnapshot:
    """Build the compact summary debug payload from already-resolved state."""
    base = dict(base_state or {})
    resolved = dict(resolved_state or {})
    overlay = {
        str(key): dict(value)
        for key, value in dict(overlay_applied or {}).items()
        if isinstance(value, dict)
    }
    compact_diffs: dict[str, dict[str, Any]] = {}
    for raw_key in subset_keys or ():
        key = str(raw_key or "")
        if not key:
            continue
        if key in overlay:
            compact_diffs[key] = dict(overlay[key])
        elif base.get(key) != resolved.get(key):
            compact_diffs[key] = {"from": base.get(key), "to": resolved.get(key), "widget_key": None}

    shear_debug = dict(shear_overlay_debug or {})
    design_action_overlay = dict(design_action_result_overlay or {})
    payload = {
        "summary_uses_resolved_inputs_state": True,
        "summary_state_source": "shared_only_canonical_state" if bool(shared_only_mode) else "shared_plus_inputs_widget_overlay",
        "summary_render_state_source": "lightweight_overlay_state",
        "summary_cache_fp_source": "resolved_inputs_summary_state",
        "summary_shared_vs_widget_diffs": compact_diffs,
        "overlay_count": len(overlay),
        "summary_shared_only_mode": bool(shared_only_mode),
        "summary_shared_only_reason": shared_only_reason,
        "summary_overlay_suppressed": bool(shared_only_mode),
        "shear_widget_overlay_applied": shear_debug.get("shear_widget_overlay_applied"),
        "shear_widget_overlay_source": shear_debug.get("shear_widget_overlay_source"),
        "overlay_s_lig": shear_debug.get("overlay_s_lig"),
        "overlay_lig_d": shear_debug.get("overlay_lig_d"),
        "overlay_lig_legs": shear_debug.get("overlay_lig_legs"),
        "summary_shear_widget_overlay_applied": shear_debug.get("shear_widget_overlay_applied"),
        "summary_overlay_s_lig": shear_debug.get("overlay_s_lig"),
        "summary_overlay_lig_d": shear_debug.get("overlay_lig_d"),
        "summary_overlay_lig_legs": shear_debug.get("overlay_lig_legs"),
        "summary_design_action_result_overlay_count": len(design_action_overlay),
        "summary_design_action_result_overlay_keys": list(design_action_overlay.keys()),
        "summary_pack_cache_design_guide_fp": design_guide_fingerprint,
        "longitudinal_reo_truth_source": resolved.get("longitudinal_reo_truth_source"),
    }
    return InputsSummaryDebugPayloadSnapshot(
        debug_payload=payload,
        compact_diffs=compact_diffs,
        display_hash=stable_inputs_session_hash(payload),
    )


def build_inputs_summary_state_mode_marker_snapshot(
    *,
    base_state: Mapping[str, Any],
    widget_shear_state: Mapping[str, Any],
    shared_only_mode: bool,
    shared_only_reason: str,
    overlay_count: int,
) -> InputsSummaryStateModeMarkerSnapshot:
    """Build the `_inputs_summary_state_mode` marker payload from plain inputs."""
    base = dict(base_state or {})
    widget_shear = dict(widget_shear_state or {})
    payload = {
        "shared_only_mode": bool(shared_only_mode),
        "reason": shared_only_reason,
        "overlay_count": int(overlay_count or 0),
        "shared_shear": {
            "s_lig": base.get("s_lig"),
            "lig_d": base.get("lig_d"),
            "lig_legs": base.get("lig_legs"),
        },
        "widget_shear": {
            "inputs_s_lig": widget_shear.get("inputs_s_lig"),
            "inputs_lig_d": widget_shear.get("inputs_lig_d"),
            "inputs_lig_legs": widget_shear.get("inputs_lig_legs"),
        },
    }
    return InputsSummaryStateModeMarkerSnapshot(
        marker_payload=payload,
        display_hash=stable_inputs_session_hash(payload),
    )
