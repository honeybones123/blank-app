"""
Session State Final Log

Consolidated session-state diagnostic log (JSONL). Uses canonical helpers from
``state_and_helpers`` so shear spacing logging matches the SHEAR SPACING CONTRACT truth.

Enable with any of:
  _session_state_final_log_enabled == True
  _dev_mode == True
  _inputs_hydration_trace == True

Output: session_state_final_log.jsonl in the application root (this file's directory).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import streamlit as st

LOG_BASENAME = "session_state_final_log.jsonl"

_COUNTERS_KEY = "_ssl_counters"
_RUN_NONCE_KEY = "_ssl_run_nonce"
_RERUN_TRIGGERS_KEY = "_ssl_rerun_triggers"


def _log_file_path() -> str:
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, LOG_BASENAME)


def is_session_state_final_log_enabled() -> bool:
    try:
        if bool(st.session_state.get("_session_state_final_log_enabled")):
            return True
        if bool(st.session_state.get("_dev_mode")):
            return True
        if bool(st.session_state.get("_inputs_hydration_trace")):
            return True
    except Exception:
        return False
    return False


def _default_counters() -> dict[str, Any]:
    return {
        "router_hydrate_count": 0,
        "render_forced_hydrate_beam_load": 0,
        "render_forced_hydrate_pending_refresh": 0,
        "queue_inputs_refresh_count": 0,
        "rerun_event_count": 0,
        "pending_inputs_apply_refresh_consumed": False,
        "force_inputs_widget_reseed_cleared_count": 0,
        "force_inputs_widget_reseed_set_count": 0,
        "recommendation_engine_compute_invoked": False,
        "render_time_shear_normalisation": False,
        "direct_auto_design_solver_ui_detected": False,
    }


def get_ssl_counters() -> dict[str, Any]:
    c = st.session_state.get(_COUNTERS_KEY)
    if not isinstance(c, dict):
        c = _default_counters()
        st.session_state[_COUNTERS_KEY] = c
    else:
        for k, v in _default_counters().items():
            c.setdefault(k, v)
    return c


def reset_session_state_final_log_run() -> None:
    """Call once at the start of each Streamlit script run (app main), after init_shared_session_state."""
    if not is_session_state_final_log_enabled():
        return
    try:
        st.session_state[_RUN_NONCE_KEY] = uuid.uuid4().hex[:12]
        st.session_state[_COUNTERS_KEY] = _default_counters()
        st.session_state[_RERUN_TRIGGERS_KEY] = []
    except Exception:
        pass


def ssl_increment(counter_key: str, delta: int = 1) -> None:
    if not is_session_state_final_log_enabled():
        return
    try:
        c = get_ssl_counters()
        c[counter_key] = int(c.get(counter_key, 0) or 0) + int(delta)
    except Exception:
        pass


def ssl_set_flag(flag_key: str, value: Any) -> None:
    if not is_session_state_final_log_enabled():
        return
    try:
        get_ssl_counters()[flag_key] = value
    except Exception:
        pass


def ssl_mark_recommendation_engine_invoked() -> None:
    ssl_set_flag("recommendation_engine_compute_invoked", True)


def ssl_record_rerun_trigger(event_name: str) -> None:
    if not is_session_state_final_log_enabled():
        return
    try:
        ssl_increment("rerun_event_count", 1)
        lst = st.session_state.get(_RERUN_TRIGGERS_KEY)
        if not isinstance(lst, list):
            lst = []
            st.session_state[_RERUN_TRIGGERS_KEY] = lst
        lst.append({"event": event_name, "ts": time.time()})
    except Exception:
        pass


def append_session_state_final_log(event: str, data: dict | None = None) -> None:
    """
    Append one JSON object per line. Best-effort: never raises to callers.
    """
    if not is_session_state_final_log_enabled():
        return
    try:
        payload = dict(data or {})
        rec: dict[str, Any] = {
            "ts": time.time(),
            "iso_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            "page_slug": st.session_state.get("page_slug"),
            "active_beam_id": st.session_state.get("active_beam_id"),
            "run_nonce": st.session_state.get(_RUN_NONCE_KEY),
            **payload,
        }
        path = _log_file_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass


def _float_or_none(x: Any) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def build_shear_spacing_alignment_snapshot(state: dict | None = None) -> dict[str, Any]:
    """
    Compact shear-spacing snapshot aligned with the SHEAR SPACING CONTRACT (canonical helpers).

    Safe fallback: on any failure, returns ``error`` plus best-effort ``shared_s_lig`` from ``s_lig``.
    For the full diagnostic snapshot (verdicts, envelope fields, etc.), use
    ``build_shear_spacing_alignment_snapshot_detailed``.
    """
    ss = dict(st.session_state) if state is None else dict(state)
    try:
        from state_and_helpers import (
            canonical_s_lig_raw,
            get_active_s_lig_widget_value,
            get_canonical_s_lig,
        )

        shared_raw = canonical_s_lig_raw(ss)
        shared = get_canonical_s_lig(ss)
        widget_key, widget_val = get_active_s_lig_widget_value(ss)
        tol = 0.51
        inactive_mirror_drift = False
        if widget_val is not None and shared is not None:
            try:
                inactive_mirror_drift = abs(float(widget_val) - float(shared)) > tol
            except Exception:
                inactive_mirror_drift = True

        return {
            "shared_s_lig_raw": shared_raw,
            "shared_s_lig": shared,
            "provided_spacing_mm": shared,
            "required_spacing_mm": ss.get("shear_required_spacing_mm"),
            "effective_spacing_mm": ss.get("shear_effective_spacing_mm"),
            "governing_spacing_source": ss.get("shear_governing_spacing_source"),
            "active_widget_key": widget_key,
            "active_widget_value": widget_val,
            "inactive_mirror_drift": inactive_mirror_drift,
        }
    except Exception as e:
        return {
            "error": str(e),
            "shared_s_lig": ss.get("s_lig"),
        }


def build_shear_spacing_alignment_snapshot_detailed(state: dict | None = None) -> dict[str, Any]:
    """
    Diagnostic snapshot: provided (shared/widget) vs published governing / effective spacings.

    Pass ``state`` to snapshot a specific mapping (e.g. tests); default uses live
    ``st.session_state``. Canonical s_lig reads use ``state_and_helpers`` helpers.

    A difference between provided input and envelope-governed spacing is expected when demand
    governs — not automatic broken state. Widget/shared drift remains suspicious.
    """
    from state_and_helpers import (
        canonical_s_lig_raw,
        get_active_s_lig_widget_value,
        get_canonical_s_lig,
    )
    from shear_checks_helpers import session_final_shear_truth_bundle_complete

    ss = dict(st.session_state) if state is None else dict(state)
    state_dict = ss
    tol = 0.51
    result_s_end = _float_or_none(ss.get("shear_spacing_end_mm"))
    result_s_mid = _float_or_none(ss.get("shear_spacing_mid_mm"))
    # Canonical provided spacing: shared s_lig only (see SHEAR_SPACING_CONTRACT_DOC).
    ref = canonical_s_lig_raw(state_dict)
    provided_spacing_mm = float(get_canonical_s_lig(state_dict))
    shared_s_lig = provided_spacing_mm
    input_spacing_mm = provided_spacing_mm
    slug = str(ss.get("page_slug") or "")
    active_key, active_val = get_active_s_lig_widget_value(state_dict)
    w_in = _float_or_none(ss.get("inputs_s_lig"))
    w_sh = _float_or_none(ss.get("shear_s_lig"))
    sectional_s = _float_or_none(ss.get("shear_sectional_check_spacing_mm"))

    szr = ss.get("shear_zone_results")
    payload_s_end = None
    payload_s_mid = None
    if isinstance(szr, dict):
        payload_s_end = _float_or_none(szr.get("shear_spacing_end_mm"))
        payload_s_mid = _float_or_none(szr.get("shear_spacing_mid_mm"))

    s_eff_mm = _float_or_none(ss.get("shear_debug_s_eff_mm"))
    effective_spacing_mm = _float_or_none(ss.get("shear_effective_spacing_mm"))
    if effective_spacing_mm is None:
        effective_spacing_mm = sectional_s
    if effective_spacing_mm is None:
        effective_spacing_mm = s_eff_mm

    required_spacing_mm = _float_or_none(ss.get("shear_required_spacing_mm"))
    _bundle_ok = session_final_shear_truth_bundle_complete(ss)
    if required_spacing_mm is None and _bundle_ok:
        required_spacing_mm = result_s_end

    governing_spacing_source = str(ss.get("shear_governing_spacing_source") or "").strip().lower()

    widget_diffs: list[str] = []
    inactive_mirror_drift_flags: list[str] = []
    if ref is not None:
        if slug == "inputs" and w_sh is not None and abs(float(w_sh) - float(ref)) > tol:
            inactive_mirror_drift_flags.append("shear_s_lig_stale_off_page")
        if slug == "shear" and w_in is not None and abs(float(w_in) - float(ref)) > tol:
            inactive_mirror_drift_flags.append("inputs_s_lig_stale_off_page")

    if slug in ("inputs", "shear") and ref is not None:
        if active_val is None:
            spacing_truth_ok = False
            widget_diffs.append("active_mirror_unset")
        else:
            spacing_truth_ok = abs(float(active_val) - float(ref)) <= tol
            if not spacing_truth_ok:
                widget_diffs.append(
                    f"active_{active_key}_vs_shared" if active_key else "active_widget_vs_shared"
                )
    else:
        spacing_truth_ok = ref is not None

    provided_vs_required_differs = (
        provided_spacing_mm is not None
        and required_spacing_mm is not None
        and abs(float(required_spacing_mm) - float(provided_spacing_mm)) > tol
    )

    published_result_spacing_mm = _float_or_none(ss.get("published_result_spacing_mm"))
    published_result_spacing_mm_legacy_diagnostic = result_s_end
    governing_spacing_mm = published_result_spacing_mm
    if governing_spacing_mm is None:
        governing_spacing_mm = result_s_end if _bundle_ok else None

    if ref is None:
        reason = "missing_shared_s_lig"
    elif not spacing_truth_ok:
        reason = "active_widget_differs_from_shared_input"
    elif provided_vs_required_differs:
        reason = "provided_vs_required_spacing_differ_expected_when_envelope_governs"
    else:
        reason = "all_aligned"

    snap: dict[str, Any] = {
        "provided_spacing_mm": provided_spacing_mm,
        "required_spacing_mm": required_spacing_mm,
        "governing_spacing_source": governing_spacing_source or None,
        "canonical_s_lig_mm": ref,
        "input_spacing_mm": input_spacing_mm,
        "governing_spacing_mm": governing_spacing_mm,
        "governing_spacing_end_mm": result_s_end,
        "governing_spacing_mid_mm": result_s_mid,
        "published_result_spacing_mm": published_result_spacing_mm,
        "published_result_spacing_mm_legacy_diagnostic": published_result_spacing_mm_legacy_diagnostic,
        "published_result_spacing_meaning": (str(ss.get("published_result_spacing_meaning") or "").strip() or None),
        "final_shear_spacing_reason": (str(ss.get("final_shear_spacing_reason") or "").strip() or None),
        "final_shear_truth_bundle_complete": bool(_bundle_ok),
        "summary_shear_truth_consume_reason": (
            "explicit_final_truth_bundle" if _bundle_ok else "missing_final_truth_bundle_nonpass"
        ),
        "sectional_check_spacing_mm": sectional_s,
        "effective_spacing_mm": effective_spacing_mm,
        "s_eff_mm": s_eff_mm,
        "payload_s_end": payload_s_end,
        "payload_s_mid": payload_s_mid,
        "result_s_end": result_s_end,
        "result_s_mid": result_s_mid,
        "shared_s_lig": shared_s_lig,
        "active_page_slug": slug,
        "active_s_lig_mirror_key": active_key,
        "active_s_lig_mirror_value": active_val,
        "widget_inputs_s_lig": w_in,
        "widget_shear_s_lig": w_sh,
        "inactive_mirror_drift_flags": inactive_mirror_drift_flags,
        "spacing_truth_enforced": (
            "active_widget_vs_canonical_shared_s_lig"
            if slug in ("inputs", "shear")
            else "canonical_shared_only_no_active_mirror"
        ),
        "auto_mode": bool(ss.get("shear_auto_design")),
        "auto_design_active": bool(ss.get("auto_design_active")),
        "shear_design_status": ss.get("shear_design_status"),
        "shear_envelope_status": ss.get("shear_envelope_status"),
        "shared_s_lig_raw": ref,
        "spacing_truth_ok": bool(spacing_truth_ok),
        "provided_vs_required_spacing_differs": bool(provided_vs_required_differs),
        "governing_differs_from_provided_input": bool(provided_vs_required_differs),
        "derived_vs_input_note": (
            "required_envelope_spacing_can_differ_from_provided_input_without_error"
            if provided_vs_required_differs
            else "same_or_within_tolerance"
        ),
        "spacing_alignment_ok": bool(spacing_truth_ok),
        "spacing_alignment_reason": reason,
        "spacing_alignment_diffs": widget_diffs,
        "tolerance_mm": tol,
    }
    snap.update(compute_shear_spacing_truth_verdict(snap))
    return snap


def build_session_state_final_log(state: dict | None = None) -> dict[str, Any]:
    """Small contract-aligned bundle: compact shear alignment + session key list."""
    ss = dict(st.session_state) if state is None else dict(state)
    try:
        keys = list(ss.keys())
    except Exception:
        keys = []
    return {
        "shear_alignment": build_shear_spacing_alignment_snapshot(ss),
        "state_keys": keys,
    }


def compute_shear_spacing_truth_verdict(snap: dict[str, Any]) -> dict[str, Any]:
    """
    Classify shear spacing using the explicit provided / required / effective / governing-source model.

    A difference between provided input and required envelope spacing is normal and not treated as an error.
    """
    from shear_checks_helpers import resolve_shear_spacing_truth

    tol = float(snap.get("tolerance_mm") or 0.51)
    provided = _float_or_none(snap.get("provided_spacing_mm"))
    required = _float_or_none(snap.get("required_spacing_mm"))
    if required is None:
        required = _float_or_none(snap.get("published_result_spacing_mm"))
    effective = _float_or_none(snap.get("effective_spacing_mm"))
    if effective is None:
        effective = _float_or_none(snap.get("sectional_check_spacing_mm"))
    canon = _float_or_none(snap.get("canonical_s_lig_mm"))
    gov_in = str(snap.get("governing_spacing_source") or "").strip().lower()

    truth = resolve_shear_spacing_truth(
        provided_spacing_mm=provided,
        required_spacing_mm=required,
        effective_spacing_mm=effective,
        tolerance_mm=tol,
    )
    gov = str(truth.get("governing_spacing_source") or "").strip().lower() or gov_in

    suspicious: list[str] = []
    notes: list[str] = []

    if not snap.get("spacing_truth_ok", True):
        suspicious.append("widget_differs_from_shared_input")

    if (
        canon is not None
        and provided is not None
        and abs(float(provided) - float(canon)) > tol
    ):
        suspicious.append("shared_differs_from_provided_input")

    if snap.get("provided_vs_required_spacing_differs") and not suspicious:
        notes.append("required_envelope_spacing_differs_from_provided_input_expected")

    status = "safe_two_truth_model"
    model_status = "unknown"
    reason = "provided, required, and effective spacings are explicitly tracked; shared s_lig is not writeback from envelope"

    if canon is None and abs(float(provided or 0.0)) < 1e-9:
        status = "ambiguous_result_labeling"
        model_status = "unknown"
        reason = "missing provided spacing in session — cannot verify spacing model"
    elif suspicious:
        status = "suspicious_state_misalignment"
        model_status = "unknown"
        reason = "; ".join(suspicious)
    elif gov == "provided":
        model_status = "provided_spacing_governs"
        reason = "effective spacing matches provided input; sectional check governed by provided s_lig"
    elif gov == "required":
        model_status = "required_spacing_governs"
        reason = (
            "effective spacing matches required envelope spacing; sectional φV_u check uses "
            "code/demand layout spacing (e.g. Apply auto spacing)"
        )
    elif notes:
        reason = reason + " — " + "; ".join(notes)

    return {
        "shear_spacing_truth_status": status,
        "shear_spacing_truth_reason": reason,
        "shear_spacing_model_status": model_status,
        "shear_spacing_suspicious_flags": suspicious,
        "shear_spacing_expected_notes": notes,
    }


def append_shear_spacing_alignment_snapshot() -> None:
    if not is_session_state_final_log_enabled():
        return
    snap = build_shear_spacing_alignment_snapshot_detailed()
    append_session_state_final_log("shear_spacing_alignment_snapshot", snap)


def append_session_state_final_summary() -> None:
    """End-of-run consolidated summary for the current Streamlit script execution."""
    if not is_session_state_final_log_enabled():
        return
    try:
        c = get_ssl_counters()
        shear = build_shear_spacing_alignment_snapshot_detailed()
        summary = {
            "inputs_hydration": {
                "router_hydrate_count": c.get("router_hydrate_count", 0),
                "render_forced_hydrate_beam_load": c.get("render_forced_hydrate_beam_load", 0),
                "render_forced_hydrate_pending_refresh": c.get("render_forced_hydrate_pending_refresh", 0),
                "queue_inputs_refresh_count": c.get("queue_inputs_refresh_count", 0),
                "pending_inputs_apply_refresh_consumed": bool(
                    c.get("pending_inputs_apply_refresh_consumed", False),
                ),
                "force_inputs_widget_reseed_set_count": c.get("force_inputs_widget_reseed_set_count", 0),
                "force_inputs_widget_reseed_cleared_count": c.get("force_inputs_widget_reseed_cleared_count", 0),
                "rerun_event_count": c.get("rerun_event_count", 0),
                "rerun_triggers": list(st.session_state.get(_RERUN_TRIGGERS_KEY) or [])[-24:],
            },
            "shear_spacing": {
                "provided_spacing_mm": shear.get("provided_spacing_mm"),
                "required_spacing_mm": shear.get("required_spacing_mm"),
                "effective_spacing_mm": shear.get("effective_spacing_mm"),
                "governing_spacing_source": shear.get("governing_spacing_source"),
                "published_result_spacing_mm": shear.get("published_result_spacing_mm"),
                "published_result_spacing_meaning": shear.get("published_result_spacing_meaning"),
                "final_shear_spacing_reason": shear.get("final_shear_spacing_reason"),
                "governing_spacing_mm": shear.get("governing_spacing_mm"),
                "sectional_check_spacing_mm": shear.get("sectional_check_spacing_mm"),
                "shared_s_lig": shear.get("shared_s_lig"),
                "widget_inputs_s_lig": shear.get("widget_inputs_s_lig"),
                "widget_shear_s_lig": shear.get("widget_shear_s_lig"),
                "last_input_spacing_mm": shear.get("input_spacing_mm"),
                "last_effective_spacing_mm": shear.get("effective_spacing_mm"),
                "last_governing_end_mm": shear.get("governing_spacing_end_mm"),
                "last_sectional_check_spacing_mm": shear.get("sectional_check_spacing_mm"),
                "last_published_result_spacing_mm": shear.get("published_result_spacing_mm"),
                "last_result_s_end": shear.get("result_s_end"),
                "last_result_s_mid": shear.get("result_s_mid"),
                "last_shared_s_lig": shear.get("shared_s_lig"),
                "last_widget_inputs_s_lig": shear.get("widget_inputs_s_lig"),
                "last_widget_shear_s_lig": shear.get("widget_shear_s_lig"),
                "widgets_match_shared": shear.get("spacing_truth_ok"),
                "governing_differs_from_input": shear.get("governing_differs_from_provided_input"),
                "derived_vs_input_note": shear.get("derived_vs_input_note"),
                "aligned": shear.get("spacing_truth_ok"),
                "interpretation_reason": shear.get("spacing_alignment_reason"),
                "shear_spacing_truth_status": shear.get("shear_spacing_truth_status"),
                "shear_spacing_truth_reason": shear.get("shear_spacing_truth_reason"),
                "shear_spacing_model_status": shear.get("shear_spacing_model_status"),
                "shear_spacing_suspicious_flags": shear.get("shear_spacing_suspicious_flags"),
                "shear_spacing_expected_notes": shear.get("shear_spacing_expected_notes"),
                "published_result_spacing_mm_legacy_diagnostic": shear.get(
                    "published_result_spacing_mm_legacy_diagnostic",
                ),
                "final_shear_truth_bundle_complete": shear.get("final_shear_truth_bundle_complete"),
                "summary_shear_truth_consume_reason": shear.get("summary_shear_truth_consume_reason"),
            },
            "architecture_safety": {
                "recommendation_engine_compute_invoked": bool(
                    c.get("recommendation_engine_compute_invoked", False),
                ),
                "direct_non_engine_auto_design_ui": bool(
                    c.get("direct_auto_design_solver_ui_detected", False),
                ),
                "render_time_shear_normalisation": bool(c.get("render_time_shear_normalisation", False)),
            },
        }
        # Flatten key shear truth fields onto the summary record for quick inspection (JSONL one-liners).
        flat_truth = {
            "provided_spacing_mm": shear.get("provided_spacing_mm"),
            "required_spacing_mm": shear.get("required_spacing_mm"),
            "effective_spacing_mm": shear.get("effective_spacing_mm"),
            "governing_spacing_source": shear.get("governing_spacing_source"),
            "published_result_spacing_mm": shear.get("published_result_spacing_mm"),
            "published_result_spacing_meaning": shear.get("published_result_spacing_meaning"),
            "final_shear_spacing_reason": shear.get("final_shear_spacing_reason"),
            "shared_s_lig": shear.get("shared_s_lig"),
            "widget_inputs_s_lig": shear.get("widget_inputs_s_lig"),
            "widget_shear_s_lig": shear.get("widget_shear_s_lig"),
            "shear_spacing_truth_status": shear.get("shear_spacing_truth_status"),
            "shear_spacing_truth_reason": shear.get("shear_spacing_truth_reason"),
            "shear_spacing_model_status": shear.get("shear_spacing_model_status"),
            "final_shear_truth_bundle_complete": shear.get("final_shear_truth_bundle_complete"),
            "summary_shear_truth_consume_reason": shear.get("summary_shear_truth_consume_reason"),
            "published_result_spacing_mm_legacy_diagnostic": shear.get(
                "published_result_spacing_mm_legacy_diagnostic",
            ),
        }
        append_session_state_final_log("session_state_final_summary", {**flat_truth, **summary})
    except Exception:
        pass
