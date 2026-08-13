import math
import uuid
import time
import os
import json
import hashlib
import copy
import traceback
import json
import os
import inspect
import traceback
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
import streamlit as st

from application.beam_summary_policy import (
    _safe_summary_float,
    _sanitize_beam_summary,
    classify_beam_check_rows,
    get_beam_overall_status,
    make_not_run_beam_summary,
    normalize_beam_status,
)
from application.longitudinal_row_policy import (
    LONGITUDINAL_REO_MAX_ROWS,
    _build_longitudinal_row_defaults,
    _build_longitudinal_row_updates_from_legacy,
    _longitudinal_row_key,
    _longitudinal_row_param_keys,
    _longitudinal_row_tab_keys,
    _safe_float,
    _safe_int,
    migrate_longitudinal_reo_snapshot,
)

from inputs_application.rerun_pure_cache_store import RerunPureCacheStore
from calculations.bending import (
    decode_bars_or_spacing as _decode_bars_or_spacing,
    effective_depth_with_links_mm,
)
from calculations.deflection import (
    DEFLECTION_LIMIT_DEFAULT_LABEL,
    DEFLECTION_LIMIT_DEFAULT_RATIO,
    DEFLECTION_LIMIT_HELP_TEXT,
    DEFLECTION_LIMIT_OPTIONS,
    derive_concrete_modulus_from_fc,
    derive_effective_concrete_modulus,
    derive_sustained_stress_ratio,
    get_deflection_limit_label_from_ratio,
    get_deflection_limit_ratio,
    get_deflection_limit_ratio_from_label,
)
from calculations.design_actions import (
    derive_design_action_session_updates,
    resolve_design_actions_from_state,
)

# Shared-session helpers: treat only None/missing as missing (not falsy)
_MISSING = object()

def is_missing(v) -> bool:
    # Only treat "not provided" as missing — NOT falsy values like 0, 0.0, "", False
    return v is None or v is _MISSING

def ss_get(key: str, default=_MISSING):
    return st.session_state.get(key, default)



# ============================================================
#  SESSION STATE CONTRACT  (READ THIS BEFORE EDITING ANYTHING)
# ============================================================

# ------------------------------------------------------------
# SHEAR SPACING CONTRACT (canonical s_lig vs mirrors vs derived)
# ------------------------------------------------------------
SHEAR_SPACING_CONTRACT_DOC = """
SHEAR SPACING CONTRACT

- s_lig is the canonical user-provided shear link spacing in shared state.
- inputs_s_lig and shear_s_lig are page-local widget mirrors only.
- Off-page widget mirrors may lag until hydration and must not be treated as canonical truth.
- effective/governing spacing used in checks is derived only.
- Derived spacing must never overwrite s_lig during normal compute.
- Contracts should hard-fail only when the active page widget disagrees with shared state.
"""

# Debug output directory (for sync trace files)
DEBUG_OUT_DIR = Path(".")  # app root; same place your other audits are being written

# Global debug toggle
DEBUG_MODE = False  # set True only when debugging


def debug_print(*args, **kwargs):
    """Central debug logger. Use this instead of print()."""
    return


def _debug_docs_dir() -> str:
    """User Documents folder (macOS-friendly)."""
    return os.path.expanduser("~/Documents")


def _debug_log_path() -> str:
    return os.path.join(_debug_docs_dir(), "blank_app_state_tripwire.log")

# Provide a module-level debug log path so any debug blocks can safely reference it
log_path = _debug_log_path()


_SPEED_PROFILE_ENV = "AUTO_DESIGN_SPEED_PROFILE"
_SPEED_PROFILE_STATS_KEY = "_speed_profile_stats"
_SPEED_PROFILE_LAST_RUN_KEY = "_speed_profile_last_run"
_RERUN_PURE_CACHE_KEY = "_rerun_pure_cache"
_UX_LATENCY_PROBE_KEY = "_ux_latency_probe"
_UX_LATENCY_PROBE_ENV = "CODEX_BROWSER_TEST_MODE"
_RENDER_TIMING_EVENTS_KEY = "_render_timing_events"
_RENDER_TIMING_STATE_KEY = "_render_timing_state"
_RENDER_TIMING_TRACE_PATH_KEY = "_render_timing_trace_path"
_RENDER_TIMING_ENV = "CODEX_RENDER_TIMING_TRACE"


def speed_profile_enabled() -> bool:
    return os.environ.get(_SPEED_PROFILE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def ux_latency_probe_enabled() -> bool:
    raw = os.environ.get(_UX_LATENCY_PROBE_ENV, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _ux_fingerprint_key(fingerprint) -> str:
    if fingerprint is None:
        return ""
    try:
        return json.dumps(fingerprint, sort_keys=True, default=str)
    except Exception:
        return repr(fingerprint)


def ux_probe_begin_rerun(*, page_slug: str | None = None) -> None:
    if not ux_latency_probe_enabled():
        return
    prev = dict(st.session_state.get(_UX_LATENCY_PROBE_KEY) or {})
    rerun_seq = int(prev.get("rerun_seq") or 0) + 1
    st.session_state[_UX_LATENCY_PROBE_KEY] = {
        "rerun_seq": rerun_seq,
        "rerun_started_ms": int(time.time() * 1000),
        "page_slug": page_slug,
        "counts": {},
    }


def ux_probe_set_page_slug(page_slug: str | None) -> None:
    if not ux_latency_probe_enabled():
        return
    probe = dict(st.session_state.get(_UX_LATENCY_PROBE_KEY) or {})
    if not probe:
        ux_probe_begin_rerun(page_slug=page_slug)
        return
    probe["page_slug"] = page_slug
    st.session_state[_UX_LATENCY_PROBE_KEY] = probe


def ux_probe_record(name: str, *, fingerprint=None, cache_hit: bool | None = None, meta: dict | None = None) -> None:
    if not ux_latency_probe_enabled():
        return
    key = str(name or "").strip()
    if not key:
        return
    probe = dict(st.session_state.get(_UX_LATENCY_PROBE_KEY) or {})
    if not probe:
        ux_probe_begin_rerun()
        probe = dict(st.session_state.get(_UX_LATENCY_PROBE_KEY) or {})
    counts = dict(probe.get("counts") or {})
    entry = dict(counts.get(key) or {})
    entry["count"] = int(entry.get("count") or 0) + 1
    if cache_hit is True:
        entry["cache_hit_count"] = int(entry.get("cache_hit_count") or 0) + 1
    fps = dict(entry.get("fingerprints") or {})
    fp_key = _ux_fingerprint_key(fingerprint)
    if fp_key:
        fp_entry = dict(fps.get(fp_key) or {})
        fp_entry["count"] = int(fp_entry.get("count") or 0) + 1
        if cache_hit is True:
            fp_entry["cache_hit_count"] = int(fp_entry.get("cache_hit_count") or 0) + 1
        if meta:
            try:
                elapsed_ms = float(dict(meta).get("elapsed_ms") or 0.0)
            except Exception:
                elapsed_ms = 0.0
            if elapsed_ms > 0.0:
                fp_entry["total_ms"] = float(fp_entry.get("total_ms") or 0.0) + elapsed_ms
                fp_entry["worst_ms"] = max(float(fp_entry.get("worst_ms") or 0.0), elapsed_ms)
            fp_entry["last_meta"] = dict(meta)
        fps[fp_key] = fp_entry
    if meta:
        entry["last_meta"] = dict(meta)
        try:
            elapsed_ms = float(dict(meta).get("elapsed_ms") or 0.0)
        except Exception:
            elapsed_ms = 0.0
        if elapsed_ms > 0.0:
            entry["total_ms"] = float(entry.get("total_ms") or 0.0) + elapsed_ms
            entry["worst_ms"] = max(float(entry.get("worst_ms") or 0.0), elapsed_ms)
    entry["fingerprints"] = fps
    counts[key] = entry
    probe["counts"] = counts
    events = list(probe.get("recent_events") or [])
    event_payload = {
        "timestamp_ms": int(time.time() * 1000),
        "name": key,
        "cache_hit": cache_hit,
        "fingerprint_sha1": (
            hashlib.sha1(str(fp_key).encode("utf-8", errors="replace")).hexdigest()[:16]
            if fp_key else None
        ),
        "meta": dict(meta or {}),
    }
    events.append(event_payload)
    probe["recent_events"] = events[-200:]
    st.session_state[_UX_LATENCY_PROBE_KEY] = probe


def get_ux_latency_probe_summary() -> dict:
    probe = dict(st.session_state.get(_UX_LATENCY_PROBE_KEY) or {})
    counts_out = {}
    for name, payload in dict(probe.get("counts") or {}).items():
        fp_payload = dict(payload.get("fingerprints") or {})
        fp_counts = [int(dict(v or {}).get("count") or 0) for v in fp_payload.values()]
        duplicate_count = sum(max(0, c - 1) for c in fp_counts)
        top_fingerprints = []
        for fp_key, fp_value in fp_payload.items():
            fp_dict = dict(fp_value or {})
            count = int(fp_dict.get("count") or 0)
            total_ms = float(fp_dict.get("total_ms") or 0.0)
            duplicate_eval_count = max(0, count - 1)
            top_fingerprints.append(
                {
                    "fingerprint_sha1": hashlib.sha1(str(fp_key).encode("utf-8", errors="replace")).hexdigest()[:16],
                    "count": count,
                    "cache_hit_count": int(fp_dict.get("cache_hit_count") or 0),
                    "duplicate_count": duplicate_eval_count,
                    "total_ms": round(total_ms, 3),
                    "avg_ms": round(total_ms / count, 3) if count else 0.0,
                    "worst_ms": round(float(fp_dict.get("worst_ms") or 0.0), 3),
                    "last_meta": dict(fp_dict.get("last_meta") or {}),
                }
            )
        top_fingerprints.sort(
            key=lambda item: (
                -int(item.get("duplicate_count") or 0),
                -int(item.get("count") or 0),
                -float(item.get("total_ms") or 0.0),
            )
        )
        total_ms = float(payload.get("total_ms") or 0.0)
        counts_out[name] = {
            "count": int(payload.get("count") or 0),
            "cache_hit_count": int(payload.get("cache_hit_count") or 0),
            "unique_fingerprint_count": len(fp_payload),
            "duplicate_count": duplicate_count,
            "total_ms": round(total_ms, 3),
            "avg_ms": round(total_ms / int(payload.get("count") or 1), 3) if int(payload.get("count") or 0) else 0.0,
            "worst_ms": round(float(payload.get("worst_ms") or 0.0), 3),
            "top_repeated_fingerprints": top_fingerprints[:10],
            "last_meta": dict(payload.get("last_meta") or {}),
        }
    return {
        "enabled": ux_latency_probe_enabled(),
        "rerun_seq": probe.get("rerun_seq"),
        "rerun_started_ms": probe.get("rerun_started_ms"),
        "page_slug": probe.get("page_slug"),
        "counts": counts_out,
        "recent_events": list(probe.get("recent_events") or [])[-80:],
    }


def render_timing_trace_enabled() -> bool:
    return (
        os.environ.get(_RENDER_TIMING_ENV, "").strip().lower() in ("1", "true", "yes", "on")
        or os.environ.get("CODEX_BROWSER_TEST_MODE", "").strip().lower() in ("1", "true", "yes", "on")
    )


def _render_timing_trace_path() -> str | None:
    if not render_timing_trace_enabled():
        return None
    try:
        path = st.session_state.get(_RENDER_TIMING_TRACE_PATH_KEY)
        if not path:
            configured_outputs = str(os.environ.get("BEAM_OUTPUTS_DIR") or "").strip()
            performance_dir = (
                os.path.join(
                    os.path.abspath(os.path.expanduser(configured_outputs)),
                    "performance",
                )
                if configured_outputs
                else os.path.join("artifacts", "performance")
            )
            os.makedirs(performance_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            path = os.path.join(
                performance_dir,
                f"product_render_timing_{stamp}.jsonl",
            )
            st.session_state[_RENDER_TIMING_TRACE_PATH_KEY] = path
        return str(path)
    except Exception:
        return None


def render_timing_begin_rerun(**meta) -> None:
    now_perf = time.perf_counter()
    rerun_seq = int(st.session_state.get("_render_timing_rerun_seq") or 0) + 1
    st.session_state["_render_timing_rerun_seq"] = rerun_seq
    st.session_state[_RENDER_TIMING_STATE_KEY] = {
        "rerun_seq": rerun_seq,
        "started_perf": now_perf,
        "last_perf": now_perf,
        "started_at_ms": int(time.time() * 1000),
        "meta": dict(meta or {}),
    }
    st.session_state[_RENDER_TIMING_EVENTS_KEY] = []
    render_timing_mark("render.rerun_start", **meta)


def render_timing_mark(name: str, **meta) -> None:
    label = str(name or "").strip()
    if not label:
        return
    try:
        state = dict(st.session_state.get(_RENDER_TIMING_STATE_KEY) or {})
        if not state:
            now_perf = time.perf_counter()
            state = {
                "rerun_seq": int(st.session_state.get("_render_timing_rerun_seq") or 0),
                "started_perf": now_perf,
                "last_perf": now_perf,
                "started_at_ms": int(time.time() * 1000),
                "meta": {},
            }
        now_perf = time.perf_counter()
        started_perf = float(state.get("started_perf") or now_perf)
        last_perf = float(state.get("last_perf") or started_perf)
        elapsed_ms = (now_perf - started_perf) * 1000.0
        delta_ms = (now_perf - last_perf) * 1000.0
        state["last_perf"] = now_perf
        st.session_state[_RENDER_TIMING_STATE_KEY] = state
        event = {
            "timestamp_ms": int(time.time() * 1000),
            "rerun_seq": state.get("rerun_seq"),
            "name": label,
            "elapsed_ms": round(elapsed_ms, 3),
            "delta_ms": round(delta_ms, 3),
            "page_slug": st.session_state.get("page_slug") or st.session_state.get("_active_page_slug"),
            "meta": dict(meta or {}),
        }
        events = list(st.session_state.get(_RENDER_TIMING_EVENTS_KEY) or [])
        events.append(event)
        st.session_state[_RENDER_TIMING_EVENTS_KEY] = events[-300:]
        path = _render_timing_trace_path()
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str) + "\n")
    except Exception:
        pass


def get_render_timing_summary(*, long_block_threshold_ms: float = 1000.0) -> dict:
    state = dict(st.session_state.get(_RENDER_TIMING_STATE_KEY) or {})
    events = list(st.session_state.get(_RENDER_TIMING_EVENTS_KEY) or [])
    threshold = max(0.0, float(long_block_threshold_ms or 0.0))
    long_blocks = [
        dict(event)
        for event in events
        if float(dict(event).get("delta_ms") or 0.0) >= threshold
    ]
    first_input_index = None
    for idx, event in enumerate(events):
        if str(dict(event).get("name") or "").startswith("inputs_page.first_visible_input."):
            first_input_index = idx
            break
    before_first_input_long_blocks = []
    if first_input_index is not None:
        before_first_input_long_blocks = [
            dict(event)
            for event in events[: first_input_index + 1]
            if float(dict(event).get("delta_ms") or 0.0) >= threshold
        ]
    return {
        "enabled": render_timing_trace_enabled(),
        "rerun_seq": state.get("rerun_seq"),
        "started_at_ms": state.get("started_at_ms"),
        "trace_path": st.session_state.get(_RENDER_TIMING_TRACE_PATH_KEY),
        "event_count": len(events),
        "events": events[-120:],
        "long_block_threshold_ms": threshold,
        "long_blocks": long_blocks[-40:],
        "before_first_visible_input_long_blocks": before_first_input_long_blocks[-20:],
    }


def _speed_profile_update_bucket(bucket: dict, elapsed_ms: float, category: str) -> dict:
    out = dict(bucket or {})
    out["category"] = str(out.get("category") or category or "compute")
    out["count"] = int(out.get("count") or 0) + 1
    out["total_ms"] = float(out.get("total_ms") or 0.0) + float(elapsed_ms)
    out["worst_ms"] = max(float(out.get("worst_ms") or 0.0), float(elapsed_ms))
    return out


def reset_speed_profile_last_run() -> None:
    if not speed_profile_enabled():
        return
    st.session_state[_SPEED_PROFILE_LAST_RUN_KEY] = {
        "started_at_ms": int(time.time() * 1000),
        "sections": {},
    }


def speed_profile_record(name: str, elapsed_ms: float, category: str = "compute") -> None:
    if not speed_profile_enabled():
        return
    section = str(name or "").strip()
    if not section:
        return
    elapsed = max(0.0, float(elapsed_ms or 0.0))
    stats = dict(st.session_state.get(_SPEED_PROFILE_STATS_KEY) or {})
    stats[section] = _speed_profile_update_bucket(stats.get(section) or {}, elapsed, category)
    st.session_state[_SPEED_PROFILE_STATS_KEY] = stats

    last_run = dict(st.session_state.get(_SPEED_PROFILE_LAST_RUN_KEY) or {})
    last_sections = dict(last_run.get("sections") or {})
    last_sections[section] = _speed_profile_update_bucket(last_sections.get(section) or {}, elapsed, category)
    last_run["sections"] = last_sections
    st.session_state[_SPEED_PROFILE_LAST_RUN_KEY] = last_run


@contextmanager
def speed_profile_section(name: str, category: str = "compute"):
    if not speed_profile_enabled():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        speed_profile_record(name, (time.perf_counter() - t0) * 1000.0, category=category)


def speed_profiled(name: str, category: str = "compute"):
    def _decorator(fn):
        def _wrapped(*args, **kwargs):
            with speed_profile_section(name, category=category):
                return fn(*args, **kwargs)
        _wrapped.__name__ = getattr(fn, "__name__", "_wrapped")
        _wrapped.__doc__ = getattr(fn, "__doc__", None)
        _wrapped.__qualname__ = getattr(fn, "__qualname__", _wrapped.__name__)
        return _wrapped
    return _decorator


def get_speed_profile_summary(*, top_n: int | None = None) -> dict:
    stats = dict(st.session_state.get(_SPEED_PROFILE_STATS_KEY) or {})
    sections = []
    for name, payload in stats.items():
        total_ms = float(payload.get("total_ms") or 0.0)
        count = int(payload.get("count") or 0)
        sections.append(
            {
                "name": name,
                "category": str(payload.get("category") or "compute"),
                "count": count,
                "total_ms": round(total_ms, 3),
                "avg_ms": round(total_ms / count, 3) if count else 0.0,
                "worst_ms": round(float(payload.get("worst_ms") or 0.0), 3),
            }
        )
    sections.sort(key=lambda item: (-float(item.get("total_ms") or 0.0), -float(item.get("worst_ms") or 0.0), item.get("name") or ""))
    if top_n is not None:
        sections = sections[: max(0, int(top_n))]

    last_run = dict(st.session_state.get(_SPEED_PROFILE_LAST_RUN_KEY) or {})
    last_sections_out = []
    for name, payload in dict(last_run.get("sections") or {}).items():
        total_ms = float(payload.get("total_ms") or 0.0)
        count = int(payload.get("count") or 0)
        last_sections_out.append(
            {
                "name": name,
                "category": str(payload.get("category") or "compute"),
                "count": count,
                "total_ms": round(total_ms, 3),
                "avg_ms": round(total_ms / count, 3) if count else 0.0,
                "worst_ms": round(float(payload.get("worst_ms") or 0.0), 3),
            }
        )
    last_sections_out.sort(key=lambda item: (-float(item.get("total_ms") or 0.0), -float(item.get("worst_ms") or 0.0), item.get("name") or ""))

    return {
        "enabled": speed_profile_enabled(),
        "sections": sections,
        "last_run_started_at_ms": last_run.get("started_at_ms"),
        "last_run_sections": last_sections_out,
    }


def reset_rerun_pure_caches() -> None:
    RerunPureCacheStore(st.session_state).reset()


def get_rerun_pure_cache(namespace: str, fingerprint) -> object | None:
    return RerunPureCacheStore(st.session_state).get(namespace, fingerprint)


def set_rerun_pure_cache(namespace: str, fingerprint, value) -> None:
    RerunPureCacheStore(st.session_state).set(namespace, fingerprint, value)


def stable_fingerprint_for_payload(payload: dict | None) -> tuple:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def _debug_snapshot_path() -> str:
    return os.path.join(_debug_docs_dir(), "blank_app_shared_snapshot.json")


def _append_debug_log(line: str) -> None:
    return


def _write_debug_ndjson_line(payload: dict) -> None:
    """
    Best-effort debug writer used by temporary beam-manager trace points.
    Never raises so debug instrumentation cannot break the app.
    """
    try:
        runtime_dir = os.path.expanduser("~/Documents/GitHub/.blank_app_runtime")
        os.makedirs(runtime_dir, exist_ok=True)
        debug_path = os.path.join(runtime_dir, "beam_manager_debug.ndjson")
        with open(debug_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def write_final_session_state_check(path: str = "final_session_state_check.json") -> str:
    """
    Writes a JSON snapshot to a visible location so it can be uploaded for debugging.
    Never raises (fails silently but tries hard).
    Returns the output path (best effort).
    """
    return ""


def mark_dirty(reason: str = ""):
    st.session_state["_dirty"] = True
    if reason:
        st.session_state["_dirty_reason"] = reason


WATCH_SHARED_KEYS = [
    "sfd_case",
    "defl_support_type",
    "crack_k1",
    "crack_member_type",
]


def _short_stack(skip: int = 0, limit: int = 8) -> list[str]:
    try:
        stack = traceback.format_stack()
        # Remove last frames in this helper + logger itself
        stack = stack[: -(2 + skip)] if len(stack) > (2 + skip) else stack
        return [ln.strip("\n") for ln in stack[-limit:]]
    except Exception:
        return []


def watch_shared_key_writes(tag: str = "", page: str | None = None) -> None:
    """
    Debug-only: detects changes in selected shared keys and logs stack trace.
    Does not block writes.
    """
    if not st.session_state.get("_debug_state_tripwire", False):
        return

    # Init last-values store
    if st.session_state.get("_debug_last_watch") is None:
        st.session_state["_debug_last_watch"] = {}

    last = st.session_state["_debug_last_watch"]
    for k in WATCH_SHARED_KEYS:
        cur = st.session_state.get(k, None)
        prev = last.get(k, None)

        # First time: just seed baseline
        if k not in last:
            last[k] = cur
            continue

        # Change detected
        if cur != prev:
            payload = {
                "event": "WATCH_CHANGE",
                "key": k,
                "from": prev,
                "to": cur,
                "tag": tag,
                "page": page or st.session_state.get("active_page", ""),
                "boot": st.session_state.get("_boot_id", ""),
                "stack": _short_stack(limit=10),
            }
            _append_debug_log(json.dumps(payload, default=str)[:8000])
            last[k] = cur


# These are normal internal keys in your app; do not treat as rogue.
ALLOWED_SESSION_PREFIXES = (
    "_",               # allow all private/internal keys
)

# Results / derived keys should NOT be treated as rogue.
# (You can add to this later if needed; keep minimal now.)
ALLOWED_EXPLICIT_NONCONTRACT_KEYS = {
    "results",
    "passes_table",
    "passes_w",
    "crack_tension_face",
    "crack_active_bar_count",
    "crack_active_bar_dias",
    "crack_active_bar_spacing_mm",
    "crack_tension_width_mm",
    "crack_Ast_active_mm2",
    "crack_flange_participation_used",
    "crack_web_participation_used",
    "crack_detailing_warning",
    "phi_Mu_cap",
    "phi_Vu_cap",
    "phi_Tu_cap",
    "deflection_total_mm",
    "deflection_limit_mm",
    "deflection_utilisation",
    # Load actions by module (derived wiring)
    "actions_bending",
    "actions_shear",
    "actions_crack",
    "actions_deflection",
    "actions_uls",
    "actions_sls",
    "crack_width",
    "crack_utilisation",
}
#
#  RULE 1 – SINGLE SOURCE OF TRUTH
#  --------------------------------
#  • All shared design values (geometry, materials, actions,
#    reo, covers, crack inputs, results) MUST be defined here
#    in SHARED_DEFAULTS.
#  • No other file is allowed to invent new shared keys like
#      st.session_state["b_new"] = ...
#    without first adding them to SHARED_DEFAULTS.
#
#  RULE 2 – WIDGET KEYS VS SHARED KEYS
#  -----------------------------------
#  • Pages use widget keys like "inputs_b", "bending_b",
#    "shear_b", "crack_b".
#  • Each widget key MUST be mapped to a shared key using TAB_KEYS:
#      TAB_KEYS["inputs_b"] = "b"
#  • Pages must NOT write directly to shared keys.
#    They only:
#      - define widgets with key="<page>_<name>"
#      - use on_change=sync_callbacks["<page>_<name>"]
#
#  RULE 3 – DERIVED VALUES
#  ------------------------
#  • Derived values (d, do, Ast_bot, Ast_top, etc.) are ONLY
#    recalculated inside recalc_derived_values().
#  • Pages must NEVER manually modify these, only read them via:
#        get_param("d"), get_param("Ast_bot"), etc.
#
#  RULE 4 – RESULTS / CAPACITIES
#  ------------------------------
#  • Bending, Shear, Crack pages must write design results using
#    update_results(), NOT raw st.session_state assignments.
#  • Allowed result keys are listed in RESULT_KEYS. If you try
#    to write anything else, update_results() raises an error.
#
#  RULE 5 – ADDING NEW SHARED THINGS
#  ----------------------------------
#  If you add a new shared quantity:
#    (1) Add default to SHARED_DEFAULTS.
#    (2) If it has widgets, add widget→shared mapping into TAB_KEYS.
#    (3) If it is derived, update recalc_derived_values().
#    (4) If it is a result, add to RESULT_KEYS and use update_results().
#
#  If any of these rules are broken, _validate_contract() will raise.
#
# ============================================================
#
# ============================================================
#
#  PAGE FILE RULES (router-owned lifecycle)
#  =======================================
#  IMPORTANT: app.py owns the lifecycle:
#    1) init_shared_session_state()
#    2) set st.session_state["page_slug"]
#    3) hydrate_active_page_widgets_from_shared(active_slug)
#    4) begin_render_cycle()
#    5) render page function
#    6) persist_state_snapshot()
#
#  Therefore, every page render function MUST:
#    1) NOT call init_shared_session_state() (router already did)
#    2) NOT call hydrate_active_page_widgets_from_shared() (router already did)
#    3) NEVER write directly to shared keys (b, D, fc, etc.)
#    4) Only update shared keys via on_change sync callbacks:
#         key="<page>_<name>"
#         on_change=sync_callbacks["<page>_<name>"]
#    5) Never clear query params globally
#
#  Example:
#      def render_mypage():
#          sync_callbacks = get_sync_callbacks()
#          st.number_input("b (mm)", key="bending_b", on_change=sync_callbacks["bending_b"])
#          # ... rest of page code ...
#
# ============================================================


# ============================================
# 1. SHARED DEFAULTS (session_state values)
# ============================================



def _sync_longitudinal_row_model_from_legacy_state() -> None:
    updates = _build_longitudinal_row_updates_from_legacy(st.session_state)
    for key, value in updates.items():
        if key not in st.session_state or st.session_state.get(key) is None:
            st.session_state[key] = value


def get_longitudinal_row_inputs(section: str, source: dict | None = None) -> list[dict]:
    source = source if isinstance(source, dict) else st.session_state
    section = "top" if section == "top" else "bot"
    default_bars = 2 if section == "top" else 4
    default_dia = 16.0 if section == "top" else 20.0
    row_count = max(0, min(LONGITUDINAL_REO_MAX_ROWS, _safe_int(source.get(f"{section}_row_count", 1), 1)))
    rows: list[dict] = []
    for row_index in range(1, LONGITUDINAL_REO_MAX_ROWS + 1):
        mode = str(source.get(_longitudinal_row_key(section, row_index, "mode"), "Count") or "Count")
        if mode not in ("Count", "Spacing"):
            mode = "Count"
        bars = max(0, _safe_int(source.get(_longitudinal_row_key(section, row_index, "bars"), default_bars if row_index == 1 else 0), default_bars if row_index == 1 else 0))
        spacing = max(0.0, _safe_float(source.get(_longitudinal_row_key(section, row_index, "spacing"), 200.0), 200.0))
        dia = max(0.0, _safe_float(source.get(_longitudinal_row_key(section, row_index, "dia"), default_dia), default_dia))
        visible = row_index <= row_count
        active = visible and dia > 0.0 and ((mode == "Count" and bars > 0) or (mode == "Spacing" and spacing > 0.0))
        rows.append({
            "row_index": row_index,
            "mode": mode,
            "bars": bars,
            "spacing": spacing,
            "dia": dia,
            "nb_or_s": float(spacing if mode == "Spacing" else bars),
            "visible": visible,
            "active": active,
        })
    return rows


def summarize_longitudinal_rows(section: str, source: dict | None = None) -> str:
    rows = [row for row in get_longitudinal_row_inputs(section, source=source) if row.get("active")]
    if not rows:
        return "-"

    def _row_text(row: dict, multi_row: bool) -> str:
        dia = int(round(float(row.get("dia", 0.0) or 0.0)))
        if dia <= 0:
            return ""
        prefix = f"R{int(row.get('row_index', 1))}: " if multi_row else ""
        if row.get("mode") == "Spacing":
            spacing = int(round(float(row.get("spacing", 0.0) or 0.0)))
            return f"{prefix}N{dia} @ {spacing}"
        bars = int(round(float(row.get("bars", 0) or 0)))
        if bars <= 0:
            return ""
        return f"{prefix}{bars}N{dia}"

    parts = [_row_text(row, multi_row=len(rows) > 1) for row in rows]
    parts = [part for part in parts if part]
    return "; ".join(parts) if parts else "-"


def build_legacy_longitudinal_mirrors_from_rows(source: dict | None = None) -> dict:
    """
    Derive legacy longitudinal reinforcement mirrors from the row-model only.

    This is one-way compatibility state for older summary/bending/guidance paths:
    row-model fields are authoritative; stale legacy ``bot1_count`` / ``Ast_bot``-style
    fields are never pushed back into the row model.
    """
    src = source if isinstance(source, dict) else st.session_state
    bot_rows_all = get_longitudinal_row_inputs("bot", source=src)
    top_rows_all = get_longitudinal_row_inputs("top", source=src)
    bot_rows = [row for row in bot_rows_all if row.get("active")]
    top_rows = [row for row in top_rows_all if row.get("active")]

    def _row_at(rows: list[dict], idx: int) -> dict | None:
        return rows[idx] if idx < len(rows) else None

    def _bars(row: dict | None) -> int:
        if not row or not row.get("active"):
            return 0
        return max(0, _safe_int((row or {}).get("bars"), 0))

    def _dia(row: dict | None) -> float:
        if not row or not row.get("active"):
            return 0.0
        return max(0.0, _safe_float((row or {}).get("dia"), 0.0))

    def _spacing(row: dict | None) -> float:
        if not row or not row.get("active"):
            return 0.0
        return max(0.0, _safe_float((row or {}).get("spacing"), 0.0))

    def _entry(row: dict | None) -> float:
        if not row or not row.get("active"):
            return 0.0
        if str((row or {}).get("mode", "Count") or "Count") == "Spacing":
            return _spacing(row)
        return float(_bars(row))

    def _area(rows: list[dict]) -> float:
        total = 0.0
        for row in rows:
            total += float(_bars(row)) * math.pi * float(_dia(row)) ** 2 / 4.0
        return float(total)

    bot_1 = _row_at(bot_rows, 0)
    bot_2 = _row_at(bot_rows, 1)
    top_1 = _row_at(top_rows, 0)
    top_2 = _row_at(top_rows, 1)

    # The row model is authoritative, but a number of established calculation
    # and diagram paths still read the compact legacy layer representation.
    # Keep those aliases in the *same* commit as the row edit.  Previously the
    # mirror contained ``bot1_count`` but omitted ``nb_or_s_bot_1`` (and the
    # layout-mode/spacing aliases), so a widget edit could produce the
    # impossible state ``bot_row_1_bars=5`` alongside ``nb_or_s_bot_1=4``.
    # Consumers then quite correctly rendered four bars from the stale alias.
    bot_1_all = _row_at(bot_rows_all, 0)
    bot_2_all = _row_at(bot_rows_all, 1)
    top_1_all = _row_at(top_rows_all, 0)
    top_2_all = _row_at(top_rows_all, 1)

    def _layout_mode(row: dict | None) -> str:
        mode = str((row or {}).get("mode", "Count") or "Count")
        return mode if mode in {"Count", "Spacing"} else "Count"

    def _layout_count(row: dict | None) -> int:
        return max(0, _safe_int((row or {}).get("bars"), 0))

    def _layout_spacing(row: dict | None) -> float:
        return max(0.0, _safe_float((row or {}).get("spacing"), 200.0))

    def _legacy_entry(row: dict | None) -> float:
        if not row or not row.get("active"):
            return 0.0
        return (
            _layout_spacing(row)
            if _layout_mode(row) == "Spacing"
            else float(_layout_count(row))
        )

    mirrors = {
        "bot1_count": _bars(bot_1),
        "bot2_count": _bars(bot_2),
        "top1_count": _bars(top_1),
        "top2_count": _bars(top_2),
        "nb_bot": int(sum(_bars(row) for row in bot_rows)),
        "nb_top": int(sum(_bars(row) for row in top_rows)),
        "db_bot_1": _dia(bot_1),
        "db_bot_2": _dia(bot_2),
        "db_top_1": _dia(top_1),
        "db_top_2": _dia(top_2),
        "db_bot": _dia(bot_1),
        "db_top": _dia(top_1),
        "bot_entry": _entry(bot_1),
        "top_entry": _entry(top_1),
        "s_bot": _spacing(bot_1),
        "s_top": _spacing(top_1),
        "total_bot_bars": int(sum(_bars(row) for row in bot_rows)),
        "total_top_bars": int(sum(_bars(row) for row in top_rows)),
        "Ast_bot": _area(bot_rows),
        "Ast_top": _area(top_rows),
        # Compact layer aliases consumed by legacy calculation/diagram paths.
        "bot1_layout_mode": _layout_mode(bot_1_all),
        "bot1_count": _layout_count(bot_1_all),
        "bot1_spacing": _layout_spacing(bot_1_all),
        "bot2_layout_mode": _layout_mode(bot_2_all),
        "bot2_count": _layout_count(bot_2_all),
        "bot2_spacing": _layout_spacing(bot_2_all),
        "top1_layout_mode": _layout_mode(top_1_all),
        "top1_count": _layout_count(top_1_all),
        "top1_spacing": _layout_spacing(top_1_all),
        "top2_layout_mode": _layout_mode(top_2_all),
        "top2_count": _layout_count(top_2_all),
        "top2_spacing": _layout_spacing(top_2_all),
        "nb_or_s_bot_1": _legacy_entry(bot_1_all),
        "nb_or_s_bot_2": _legacy_entry(bot_2_all),
        "nb_or_s_top_1": _legacy_entry(top_1_all),
        "nb_or_s_top_2": _legacy_entry(top_2_all),
    }

    def _differs(key: str, value) -> bool:
        cur = src.get(key)
        if isinstance(value, float):
            try:
                return abs(float(cur) - float(value)) > 1e-6
            except (TypeError, ValueError):
                return cur != value
        return cur != value

    mirrors["longitudinal_reo_truth_source"] = "row_model"
    mirrors["row_model_legacy_sync_applied"] = True
    mirrors["row_model_legacy_sync_diff_keys"] = [
        str(key) for key, value in mirrors.items() if key not in {
            "longitudinal_reo_truth_source",
            "row_model_legacy_sync_applied",
            "row_model_legacy_sync_diff_keys",
        } and _differs(key, value)
    ]
    return mirrors

def _audit(event: str, shared_key: str, widget_key: str = "", old=None, new=None, extra: dict | None = None):
    """Tiny audit trail for state writes (debug only)."""
    rec = {
        "ts_ms": int(time.time() * 1000),
        "event": event,
        "shared_key": shared_key,
        "widget_key": widget_key,
        "old": old,
        "new": new,
        "page_slug": st.session_state.get("page_slug"),
        "boot_id": st.session_state.get("_boot_id"),
        "wipe_mode": st.session_state.get("_wipe_recovery_mode"),
    }
    if extra:
        rec.update(extra)
    st.session_state["_audit_tail"] = (st.session_state.get("_audit_tail") or [])[-200:] + [rec]


def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)


# Manual design-action keys: 0 is a valid user value, but a *stale* widget 0 (navigation,
# duplicate page widgets) must not overwrite cache, hydration, or snapshots while shared
# remains non-zero. Legitimate 0 stays valid once shared has been updated (shared 0).
MANUAL_DESIGN_ACTION_STALE_ZERO_GUARD_KEYS: frozenset[str] = frozenset(
    {
        "uls_Mstar",
        "uls_Vstar",
        "uls_Nstar",
        "uls_Mstar_pos_manual",
        "uls_Mstar_neg_manual",
        "sls_Mstar",
        "sls_Vstar",
        "sls_Nstar",
        "sls_Mstar_pos_manual",
        "sls_Mstar_neg_manual",
        "Mu_star_manual",
        "Mu_star_pos_manual",
        "Mu_star_neg_manual",
    }
)


def _is_zero_like(v) -> bool:
    if v is None or v == "":
        return True
    try:
        return float(v) == 0.0
    except (TypeError, ValueError):
        return False


def _float_nonzero(v) -> bool:
    if v is None or v == "":
        return False
    try:
        return float(v) != 0.0
    except (TypeError, ValueError):
        return v not in (0, 0.0, False)


def _manual_action_stale_widget_zero(*, widget_val, shared_val, shared_key: str) -> bool:
    if shared_key not in MANUAL_DESIGN_ACTION_STALE_ZERO_GUARD_KEYS:
        return False
    if not _is_zero_like(widget_val):
        return False
    return _float_nonzero(shared_val)


def _set_shared_is_user_intent_source(source: object) -> bool:
    """True when set_shared was triggered by widget callback / sync (not seed/restore/merge)."""
    if not isinstance(source, str):
        return False
    if source in ("seed_defaults", "restore_snapshot", "wipe_recovery", "beam_project_hydrate", "uls_mirror"):
        return False
    if source.startswith("persist_snapshot_merge"):
        return False
    if source.startswith("callback:"):
        return True
    return source in ("sync_update", "sync_init", "design_action_widget_sync")


def _get_hydrated_map() -> dict:
    m = st.session_state.get("_hydrated_from_shared_map")
    if not isinstance(m, dict):
        m = {}
        st.session_state["_hydrated_from_shared_map"] = m
    return m

def safe_hydrate(widget_key: str, shared_key: str, value, *, force: bool = False) -> None:
    """Seed widget from shared using sticky hydration rules."""
    hydrated_map = _get_hydrated_map()

    if force:
        st.session_state[widget_key] = value
        hydrated_map[widget_key] = value
        return

    if widget_key not in st.session_state:
        st.session_state[widget_key] = value
        hydrated_map[widget_key] = value
        return

    # If shared has a meaningful action value but widget is stale zero/None, rehydrate.
    action_keys = {
        "Tu_star",
        "N_star",
        "P_star",
        "load_Mstar_proxy",
        "load_Mstar_pos_proxy",
        "load_Mstar_neg_proxy",
        "load_Vstar_proxy",
        "load_Nstar_proxy",
    } | set(MANUAL_DESIGN_ACTION_STALE_ZERO_GUARD_KEYS)
    if shared_key in action_keys:
        cur = st.session_state.get(widget_key)
        shared_val = st.session_state.get(shared_key)
        if shared_val not in (None, "", 0, 0.0) and cur in (None, "", 0, 0.0):
            st.session_state[widget_key] = shared_val
            hydrated_map[widget_key] = shared_val
            return

    last_h = hydrated_map.get(widget_key, "__NOHYDRATE__")
    cur = st.session_state.get(widget_key)
    if last_h != "__NOHYDRATE__" and cur == last_h:
        st.session_state[widget_key] = value
        hydrated_map[widget_key] = value
        return

    try:
        _write_sync_trace_line(
            f"SAFE_HYDRATE widget={widget_key} shared={shared_key}"
        )
    except Exception:
        pass


def _shared_zero_tripwire(tag: str, keys: list[str] | None = None):
    """
    Tripwire: detect when shared keys get zeroed (debug only).
    Stores result in st.session_state["_tripwire_last"] for display in sidebar.
    """
    keys = keys or [k for k in st.session_state.keys() if k in SHARED_DEFAULTS]
    # Count how many shared keys are now 0/None
    bad = []
    for k in keys:
        if k not in SHARED_DEFAULTS:
            continue
        v = st.session_state.get(k)
        if v is None:
            if k in ("top2_count", "bot2_count"):
                try:
                    _write_sync_trace_line(f"TRIPWIRE_ZERO key={k} val={v} tag={tag}")
                except Exception:
                    pass
            bad.append((k, v))
        elif isinstance(v, (int, float)) and float(v) == 0.0 and (not zero_allowed(k)):
            if k in ("top2_count", "bot2_count"):
                try:
                    _write_sync_trace_line(f"TRIPWIRE_ZERO key={k} val={v} tag={tag}")
                except Exception:
                    pass
            bad.append((k, v))
    st.session_state["_tripwire_last"] = {"tag": tag, "bad_count": len(bad), "sample": bad[:25]}


def tripwire_no_falsy_defaulting():
    """
    Debug guard: catches the exact bug where a legitimate 0 gets overwritten.
    Call this once per run after init/hydration.
    """
    watch = [
        "nb_or_s_top_2",
        "nb_or_s_bot_2",
        "Tu_star",
        "uls_Vstar",
        "uls_Mstar",
        "N_star",
        "P_star",
        "lig_legs",
        "n_ducts",
    ]
    defaults = []
    for k in watch:
        if k in st.session_state and st.session_state[k] == 0:
            default = SHARED_DEFAULTS.get(k, None)
            defaults.append({"key": k, "default": default})
    st.session_state["_tripwire_falsy_defaults"] = defaults

SHARED_DEFAULTS = {
    # Geometry — baseline matches NEW_BEAM_STARTER_DEFAULTS (seed / resumed session).
    "b": 250.0,     # beam width (mm)
    "D": 300.0,     # overall depth (mm)
    "L": 2000.0,    # span/effective length (mm)
    "sec_shape": "RECT",
    "bf": 600.0,
    "tf": 120.0,
    "bw": 300.0,
    "tw": 200.0,
    "bf_bot": 600.0,
    "tf_bot": 120.0,
    # Derived geometry (shape-aware) — RECT b×D consistent with b, D above
    "A_g": 250.0 * 300.0,          # mm^2
    "ybar_top_g": 150.0,           # mm (D/2 for symmetric RECT)
    "Ixx_g": (250.0 * 300.0**3) / 12.0,  # mm^4
    "Ztop_g": 0.0,                 # mm^3
    "Zbot_g": 0.0,                 # mm^3
    "b_web": 250.0,                # mm (RECT=b, T=bw, I=tw)
    "b_crack": 250.0,              # mm (width used by crack calcs)
    "A_ct_default": 250.0 * 300.0 / 2.0,  # mm^2 (for shear)
    "sustained_Mstar_kNm": 0.0,           # governing sustained SLS moment magnitude
    "sustained_sigma_cs_mpa": 0.0,        # sustained concrete compressive stress
    "sustained_section_modulus_mm3": 0.0, # section modulus used for sigma_cs
    "sustained_compression_fibre": "top", # top for sagging, bottom for hogging
    "defl_dims_user_override": False,
    "inputs_detailed_mode": False,
    "auto_geometry": False,
    "auto_bottom_reo": False,
    "auto_shear": False,
    "fast_mode_show_3d": False,
    "design_optimisation_goal": "balanced",
    "optimisation_lock_geometry": False,
    "optimisation_lock_width": False,
    "optimisation_lock_depth": False,

    # Materials
    "fc": 40.0,     # MPa
    "fsy": 500.0,   # MPa
    "Ec": 30000.0,  # MPa (derived from fc in recalc_derived_values)
    "Eceff": 10000.0,  # MPa (derived from Ec and phi_cc_t in recalc_derived_values)
    "Es": 200000.0, # MPa
    "phi_bend": 0.85,  # ← strength reduction factor for bending

    # Shear & torsion strength reduction factors
    "phi_shear": 0.75,
    "phi_torsion": 0.75,
    # 3-zone shear layout (Check 10): enable/disable; results in shear_zone_results via update_results only
    "shear_zone_enabled": True,
    # Optional auto-design of shear links (Check 10); trial sizes never written to lig_d/legs inputs
    "shear_auto_design": False,
    # Tracks whether reinforcement values were most recently applied by auto design.
    "auto_design_active": False,
    # Optional detailing optimisation: relax spacing while keeping envelope utilisation >= 1.0
    "shear_optimize_reinforcement": False,
    # Check 10 published outputs (shear_zone_results, shear_design_status, auto-selection floats) live in
    # RESULT_KEYS / RESULT_DEFAULTS and are written only via update_results() — not listed here as shared inputs.

    # Actions (manual inputs - these are the user-controlled shared inputs)
    # NOTE: Mu_star/Mu_star_kNm/Vu_star are RESULTS (computed outputs), not shared inputs.
    # They are written by update_results() and should NOT be in SHARED_DEFAULTS.

    "Tu_star": 0.0,    # kNm
    "P_star": 0.0,     # kN (prestress or axial in bending/shear)
    "N_star": 0.0,     # kN (legacy ULS axial)
    "actions_source": "Manual design actions (inputs below)",  # Source of design actions
    "actions_mode": "manual",
    "design_beam_system_mode": "Single span",
    "design_support_condition": "Simply supported",
    "design_support_type_1": "Pinned",
    "design_support_type_2": "Pinned",
    "design_support_type_3": "Pinned",
    "design_support_type_4": "Pinned",
    "design_support_type_5": "Pinned",
    "design_support_type_6": "Pinned",
    "design_span_count": 2.0,
    "design_span_len_1": 4.0,
    "design_span_len_2": 4.0,
    "design_span_len_3": 4.0,
    "design_span_len_4": 4.0,
    "design_span_len_5": 4.0,
    "design_ms_point_count": 2.0,
    "design_ms_udl_count": 1.0,
    "design_ms_G_1": 30.0,
    "design_ms_G_2": 30.0,
    "design_ms_G_3": 30.0,
    "design_ms_G_4": 30.0,
    "design_ms_G_5": 30.0,
    "design_ms_G_6": 30.0,
    "design_ms_G_7": 30.0,
    "design_ms_G_8": 30.0,
    "design_ms_Q_1": 20.0,
    "design_ms_Q_2": 20.0,
    "design_ms_Q_3": 20.0,
    "design_ms_Q_4": 20.0,
    "design_ms_Q_5": 20.0,
    "design_ms_Q_6": 20.0,
    "design_ms_Q_7": 20.0,
    "design_ms_Q_8": 20.0,
    "design_ms_x_1": 1.0,
    "design_ms_x_2": 2.0,
    "design_ms_x_3": 3.0,
    "design_ms_x_4": 4.0,
    "design_ms_x_5": 5.0,
    "design_ms_x_6": 6.0,
    "design_ms_x_7": 7.0,
    "design_ms_x_8": 8.0,
    "design_ms_g_1": 5.0,
    "design_ms_g_2": 5.0,
    "design_ms_g_3": 5.0,
    "design_ms_g_4": 5.0,
    "design_ms_g_5": 5.0,
    "design_ms_g_6": 5.0,
    "design_ms_g_7": 5.0,
    "design_ms_g_8": 5.0,
    "design_ms_q_1": 3.0,
    "design_ms_q_2": 3.0,
    "design_ms_q_3": 3.0,
    "design_ms_q_4": 3.0,
    "design_ms_q_5": 3.0,
    "design_ms_q_6": 3.0,
    "design_ms_q_7": 3.0,
    "design_ms_q_8": 3.0,
    "design_ms_x0_1": 0.0,
    "design_ms_x0_2": 0.0,
    "design_ms_x0_3": 0.0,
    "design_ms_x0_4": 0.0,
    "design_ms_x0_5": 0.0,
    "design_ms_x0_6": 0.0,
    "design_ms_x0_7": 0.0,
    "design_ms_x0_8": 0.0,
    "design_ms_x1_1": 3.0,
    "design_ms_x1_2": 3.0,
    "design_ms_x1_3": 3.0,
    "design_ms_x1_4": 3.0,
    "design_ms_x1_5": 3.0,
    "design_ms_x1_6": 3.0,
    "design_ms_x1_7": 3.0,
    "design_ms_x1_8": 3.0,

    # --- Load inputs (store both ULS and SLS separately) ---
    "uls_Mstar": 0.0,
    "uls_Mstar_pos_manual": 0.0,
    "uls_Mstar_neg_manual": 0.0,
    "uls_Vstar": 0.0,
    "uls_Nstar": 0.0,
    "manual_uls_Vstar": 0.0,
    "manual_uls_Nstar": 0.0,

    "sls_Mstar": 0.0,
    "sls_Mstar_pos_manual": 0.0,
    "sls_Mstar_neg_manual": 0.0,
    "sls_Vstar": 0.0,
    "sls_Nstar": 0.0,
    "manual_sls_Vstar": 0.0,
    "manual_sls_Nstar": 0.0,
    # Canonical signed manual moment pair (ULS)
    "Mu_star_manual": 0.0,  # legacy single signed manual moment
    "Mu_star_pos_manual": 0.0,
    "Mu_star_neg_manual": 0.0,

    # Which set the Inputs-page load widgets are currently editing
    "loads_edit_mode": "ULS",  # "ULS" or "SLS"
    "loads_edit_toggle": False,  # False=ULS, True=SLS
    "design_actions_source": "max",  # "max" or "section"
    "section_cursor_x_m": 0.0,
    "design_section_x_m": 0.0,
    "design_section_committed": False,


    # Proxies used ONLY by the widgets (never used by calculations)
    "load_Mstar_proxy": 0.0,
    "load_Mstar_pos_proxy": 0.0,
    "load_Mstar_neg_proxy": 0.0,
    "load_Vstar_proxy": 0.0,
    "load_Nstar_proxy": 0.0,

    # Longitudinal reinforcement - 2-layer system (aligned with new-beam starter)
    # Bottom Layer 1
    "nb_or_s_bot_1": 3.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_bot_1": 10.0,       # mm
    # Bottom Layer 2
    "nb_or_s_bot_2": 0.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_bot_2": 10.0,       # mm
    "rowgap_bot": 60.0,     # vertical gap between bottom rows (mm)
    
    # Top Layer 1
    "nb_or_s_top_1": 2.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_top_1": 10.0,       # mm
    # Top Layer 2
    "nb_or_s_top_2": 0.0,   # bars or spacing (≤30 = bars, ≥30 = spacing in mm)
    "db_top_2": 10.0,       # mm
    "rowgap_top": 60.0,     # vertical gap between top rows (mm)
    
    # Legacy parameters (derived from layers, kept for backward compatibility)
    "nb_bot": 3,            # bottom bars (derived)
    "db_bot": 10.0,         # mm (derived from layer 1)
    "nb_top": 2,            # top bars (derived)
    "db_top": 10.0,         # mm (derived from layer 1)
    
    # Legacy "bars or spacing" entries (kept for migration)
    "bot_entry": 3.0,       # bottom layer: bar count (maps to nb_or_s_bot_1)
    "top_entry": 2.0,       # top layer: bar count (maps to nb_or_s_top_1)
    
    # Optional derived spacing (you can store these here or in a derived dict)
    "s_bot": 200.0,         # effective bottom spacing (mm)
    "s_top": 200.0,         # effective top spacing (mm)

    # Cover (including side cover shared values)
    "cover_bot": 40.0,
    "cover_top": 40.0,
    "side_cover_bot": 40.0,
    "side_cover_top": 40.0,
    "cover_side": 40.0,  # Geometry – side cover (to centroid or clear, whichever convention you use)

    # Duct inputs (prestress / voids)
    "n_ducts": 0.0,     # number of ducts crossing the web
    "duct_dia": 0.0,    # nominal duct diameter (mm)

    # Shear section parameters (AS 3600)
    "d_g": 20.0,          # maximum aggregate size (mm)
    "k_d_option": "None (no ducts in web)",  # dropdown string
    "k_v_method": "General εx-based (Cl. 8.2.4.2)",  # dropdown string

    # --- Time-dependent inputs (realistic defaults) ---
    "t_creep": 365,          # days after loading
    "age_at_loading": 28,    # days
    "stress_ratio": 0.0,     # Derived sustained stress ratio: sigma_cs / f'c
    "t_shrink": 365,         # days since drying

    # Bottom layer 1 (explicit layout mode)
    "bot1_layout_mode": "Count",
    "bot1_count": 3,
    "bot1_spacing": 200,

    # Bottom layer 2 (explicit layout mode)
    "bot2_layout_mode": "Count",
    "bot2_count": 0,
    "bot2_spacing": 200,

    # Top layer 1 (explicit layout mode)
    "top1_layout_mode": "Count",
    "top1_count": 2,
    "top1_spacing": 200,

    # Top layer 2 (explicit layout mode)
    "top2_layout_mode": "Count",
    "top2_count": 0,
    "top2_spacing": 200,

    # T/I explicit flange longitudinal reinforcement groups
    "top_flange_reo_enabled": False,
    "bot_flange_reo_enabled": False,
    "top_flange_mirror_lr": True,
    "bot_flange_mirror_lr": True,
    "top_flange_left_count": 0,
    "top_flange_left_dia": 16.0,
    "top_flange_left_rows": 1,
    "top_flange_left_row_spacing": 60.0,
    "top_flange_left_clear_spacing_mode": "count",
    "top_flange_right_count": 0,
    "top_flange_right_dia": 16.0,
    "top_flange_right_rows": 1,
    "top_flange_right_row_spacing": 60.0,
    "top_flange_right_clear_spacing_mode": "count",
    "bot_flange_left_count": 0,
    "bot_flange_left_dia": 20.0,
    "bot_flange_left_rows": 1,
    "bot_flange_left_row_spacing": 60.0,
    "bot_flange_left_clear_spacing_mode": "count",
    "bot_flange_right_count": 0,
    "bot_flange_right_dia": 20.0,
    "bot_flange_right_rows": 1,
    "bot_flange_right_row_spacing": 60.0,
    "bot_flange_right_clear_spacing_mode": "count",
    # Optional flange transverse detailing/distribution reinforcement (not primary shear links)
    "top_flange_transverse_enabled": False,
    "bot_flange_transverse_enabled": False,
    "top_flange_transverse_dia": 10.0,
    "bot_flange_transverse_dia": 10.0,
    "top_flange_transverse_spacing": 200.0,
    "bot_flange_transverse_spacing": 200.0,
    "top_flange_transverse_legs": 2,
    "bot_flange_transverse_legs": 2,

    # Canonical dynamic longitudinal reinforcement rows
    **_build_longitudinal_row_defaults("bot"),
    **_build_longitudinal_row_defaults("top"),

    # Shear reinforcement (starter: no shear reo)
    "lig_d": 0.0,      # lig/stirrup diameter (mm)
    "lig_legs": 0,     # legs per stirrup (<2 treated as no shear reo in calcs)
    "s_lig": 200.0,    # spacing (mm)

    # Crack control inputs
    "exposure_class": "B1",
    "s_bar_bot": 200.0,  # bottom bar spacing for crack calc (mm)
    
    # Crack criteria (inputs)
    "wmax_char_limit": 0.3,                 # mm (user-selected limit)
    "crack_member_type": "Primarily flexure",
    "crack_k1": 0.8,                        # deformed bars
    "crack_k2": 0.5,                        # default for flexure
    "crack_diagram_panel": "Crack Diagram",  # Crack page diagram view (shared with TAB_KEYS)
    "crack_control_method": "existing_as3600",
    "crack_wall_thickness_mm": 600.0,
    "crack_wall_in_base_zone": False,
    "crack_wall_horizontal_area_per_face": 2750.0,
    "crack_wall_vertical_spacing_mm": 150.0,
    "crack_c766_restraint_type": "continuous_edge",
    "crack_c766_t1_c": 46.1,
    "crack_c766_t2_c": 20.0,
    "crack_c766_alpha_micro_per_c": 12.0,
    "crack_c766_restraint_early": 0.676,
    "crack_c766_restraint_medium": 0.644,
    "crack_c766_restraint_long": 0.644,
    "crack_c766_tensile_capacity_micro": 70.0,
    "crack_c766_autogenous_early_micro": 0.0,
    "crack_c766_autogenous_long_micro": 75.0,
    "crack_c766_effective_reinforcement_ratio": 0.01,
    "crack_c766_bar_diameter_mm": 20.0,
    "crack_c766_cover_mm": 45.0,
    "crack_c766_modular_ratio": 7.0,
    "crack_c766_non_uniform_k": 0.65,
    "crack_c766_stress_distribution_kc": 1.0,
    "crack_c766_characteristic_tensile_mpa": 2.0,
    "crack_c766_total_reinforcement_ratio": 0.01,

    # Crack / torsion sketch control
    "crack_theta_deg": 45.0,  # physical crack angle (degrees)

    # Derived (will be recalculated; set initial values) — RECT 250×300, 3N10 bot / 2N10 top
    "d": 300.0 - 40.0 - 10.0 / 2.0,
    "do": 300.0 - 40.0 - 10.0 / 2.0,
    "Ast_bot": 3 * math.pi * 10.0**2 / 4.0,
    "Ast_top": 2 * math.pi * 10.0**2 / 4.0,
    "bot_rows_resolved": [],
    "top_rows_resolved": [],
    "bot_bar_coords": [],
    "top_bar_coords": [],
    "resolved_longitudinal_bars": [],
    "resolved_longitudinal_warnings": [],
    # Compatibility summaries derived from canonical resolved_longitudinal_bars
    "Ast_top_web": 0.0,
    "Ast_top_flange": 0.0,
    "Ast_bottom_web": 0.0,
    "Ast_bottom_flange": 0.0,
    "total_bot_bars": 3,
    "total_top_bars": 2,

    # Deflection page inputs (never None — None causes Streamlit widget + calc crashes)
    "defl_beff": 250.0,   # mm
    "defl_bw": 250.0,     # mm (derived from b; no direct widget)
    "defl_L_eff": 2.0,    # m  (default from L=2000mm)
    "defl_support_type": "Simply supported",  # Support condition for k₂ coefficient
    "defl_limit_ratio": 250.0,  # Deflection limit ratio (L/Δ, e.g. 250 for L/250)
    "defl_Fdef": 12.0,  # Effective design load (kN/m) for span/depth check
    "defl_use_simplified_ief": True,  # Use simplified I_ef calculation (checkbox)
    "defl_Ief_user": 1.0e11,  # mm^4, used when simplified I_ef is disabled
    
    # Shrinkage page inputs
    "member_faces_exposed": "Beam – three faces exposed",  # Member / faces exposed for shrinkage
    "shrinkage_env": "Temperate inland environment",  # Shrinkage environment (Table 3.1.7.2)
    "shrinkage_method": "existing_as3600",
    "shrinkage_relative_humidity_percent": 51.0,
    "shrinkage_cement_class": "S",
    "shrinkage_drying_start_age_days": 7.0,
    
    # Creep page inputs
    "env_option": "Temperate inland environment",  # Creep environment (Tables 3.1.8.2 & 3.1.8.3)
    
    # Unified beam loading (single source of truth on SFD/BMD page)
    # Note: load_case is a widget key (st.selectbox), so it's managed by Streamlit, not stored here
    "span_L_m": 6.0,  # Span length (m) - default must be >= 0.1 for widget constraint
    
    # UDL loads (defaults zero — no implicit service loads until the user or SFD sets them)
    "g_udl_kNm_per_m": 0.0,  # Dead UDL (kN/m)
    "q_udl_kNm_per_m": 0.0,  # Live UDL (kN/m)
    "psi_udl": 0.4,  # Sustained factor for UDL
    "w_sls_kNm_per_m": 0.0,  # SLS UDL (kN/m); align with g+q / teaching page when used
    "w_uls_kNm_per_m": 0.0,  # ULS UDL (kN/m)
    
    # Point loads
    "G_point_kN": 50.0,  # Dead point load (kN)
    "Q_point_kN": 30.0,  # Live point load (kN)
    "psi_point": 0.4,  # Sustained factor for point load
    "P_sls_kN": 62.0,  # SLS point load: G + psi_s * Q (kN)
    "P_uls_kN": 105.0,  # ULS point load: γ_G * G + γ_Q * Q (kN)
    "a_m": 0.0,  # Distance a from left support for point loads (m) - user input, 0 is valid
    "a_udl_m": 0.0,  # Partial UDL length a (m)
    "a_cant_m": 0.0,  # Cantilever point load distance a (m)
    "a_overhang_m": 0.0,  # Overhang length a (m)
    "design_point_G_1": 50.0,
    "design_point_G_2": 50.0,
    "design_point_G_3": 50.0,
    "design_point_G_4": 50.0,
    "design_point_G_5": 50.0,
    "design_point_G_6": 50.0,
    "design_point_Q_1": 30.0,
    "design_point_Q_2": 30.0,
    "design_point_Q_3": 30.0,
    "design_point_Q_4": 30.0,
    "design_point_Q_5": 30.0,
    "design_point_Q_6": 30.0,
    "design_point_x_1": 1.0,
    "design_point_x_2": 2.0,
    "design_point_x_3": 3.0,
    "design_point_x_4": 4.0,
    "design_point_x_5": 5.0,
    "design_point_x_6": 6.0,
    # Number of point loads is an editable Design/SFD input, not a page-local
    # display value.  Keep it in the shared defaults so navigation, beam
    # persistence, and calculation invalidation all see the same value.
    "sfd_point_load_count": 2.0,
    
    # SFD/BMD inputs (kept as inputs, not results)
    "sfd_span_L_m": 6.0,  # Span length for SFD/deflection pages (m)
    "sfd_case": "Simple beam – UDL over entire span",  # Current teaching case
}

# UI-only session state defaults (not shared, not synced)
UI_STATE_DEFAULTS = {
    "_reo_msg_top_auto_layer2": "",
    "_reo_msg_top_layer2_overwritten": "",
    "_reo_error_top_1": "",
    "_reo_warning_top_1": "",
    "_reo_s_min_top_1": "",
    "bending_detail_view": "positive",
}

# When True, Inputs page must not apply the one-time new-module starter payload.
# Set after explicit beam/project actions so starter never clobbers loaded beams.
BEAM_MODULE_STARTER_SEED_DONE_KEY = "_beam_module_starter_seed_done"
BEAM_STARTER_META_SENTINEL_KEY = "starter_seed_applied"

# Dedicated template for brand-new beams/modules.
# This is intentionally separate from SHARED_DEFAULTS.
# Only canonical shared input keys belong here (no derived/result keys).
NEW_BEAM_STARTER_DEFAULTS = {
    # Geometry
    "sec_shape": "RECT",
    "b": 250.0,
    "D": 300.0,
    "L": 2000.0,
    "cover_side": 40.0,
    # Bottom longitudinal reinforcement
    "bot1_layout_mode": "Count",
    "bot1_count": 3,
    "db_bot_1": 10,
    "cover_bot": 40.0,
    # Top longitudinal reinforcement
    "top1_layout_mode": "Count",
    "top1_count": 2,
    "db_top_1": 10,
    "cover_top": 40.0,
    # Shear reinforcement (brand-new beam starts with no ligs)
    "lig_d": 0,
    "lig_legs": 0,
    "s_lig": 200.0,
    # Support / serviceability
    "member_faces_exposed": "Slab – one face exposed",
    "shrinkage_env": "Arid environment",
    "env_option": "Arid environment",
    "defl_support_type": "Simply supported",
    "defl_limit_ratio": 250,
    # Materials
    "fsy": 500.0,
    "fc": 40.0,
    # Shear section parameters
    "d_g": 20.0,
    "k_v_method": "General εx-based (Cl. 8.2.4.2)",
    # Time-dependent inputs
    "t_shrink": 365.0,
    "t_creep": 365.0,
    "age_at_loading": 28.0,
    # Ducts / prestress voids
    "n_ducts": 0.0,
    "duct_dia": 0.0,
    "k_d_option": "None (no ducts in web)",
    # Crack control inputs
    "exposure_class": "B1",
    "crack_member_type": "Primarily flexure",
    "crack_k1": 0.8,
    "crack_k2": 0.5,
    "crack_diagram_panel": "Crack Diagram",
    # Design actions (manual/shared source of truth) - NEW beams must start at zero
    "actions_source": "Manual design actions (inputs below)",
    "actions_mode": "manual",
    "loads_edit_mode": "ULS",
    "loads_edit_toggle": False,
    "design_actions_source": "max",
    "design_section_x_m": 0.0,
    "section_cursor_x_m": 0.0,
    "design_section_committed": False,
    "Tu_star": 0.0,
    "P_star": 0.0,
    "N_star": 0.0,
    "uls_Mstar": 0.0,
    "uls_Mstar_pos_manual": 0.0,
    "uls_Mstar_neg_manual": 0.0,
    "uls_Vstar": 0.0,
    "uls_Nstar": 0.0,
    "manual_uls_Vstar": 0.0,
    "manual_uls_Nstar": 0.0,
    "sls_Mstar": 0.0,
    "sls_Mstar_pos_manual": 0.0,
    "sls_Mstar_neg_manual": 0.0,
    "sls_Vstar": 0.0,
    "sls_Nstar": 0.0,
    "manual_sls_Vstar": 0.0,
    "manual_sls_Nstar": 0.0,
    "Mu_star_manual": 0.0,
    "Mu_star_pos_manual": 0.0,
    "Mu_star_neg_manual": 0.0,
    "load_Mstar_proxy": 0.0,
    "load_Mstar_pos_proxy": 0.0,
    "load_Mstar_neg_proxy": 0.0,
    "load_Vstar_proxy": 0.0,
    "load_Nstar_proxy": 0.0,
}

NEW_BEAM_ACTION_SHARED_KEYS = {
    "actions_source",
    "actions_mode",
    "loads_edit_mode",
    "loads_edit_toggle",
    "design_actions_source",
    "design_section_x_m",
    "section_cursor_x_m",
    "design_section_committed",
    "Tu_star",
    "P_star",
    "N_star",
    "uls_Mstar",
    "uls_Mstar_pos_manual",
    "uls_Mstar_neg_manual",
    "uls_Vstar",
    "uls_Nstar",
    "manual_uls_Vstar",
    "manual_uls_Nstar",
    "sls_Mstar",
    "sls_Mstar_pos_manual",
    "sls_Mstar_neg_manual",
    "sls_Vstar",
    "sls_Nstar",
    "manual_sls_Vstar",
    "manual_sls_Nstar",
    "Mu_star_manual",
    "Mu_star_pos_manual",
    "Mu_star_neg_manual",
    "load_Mstar_proxy",
    "load_Mstar_pos_proxy",
    "load_Mstar_neg_proxy",
    "load_Vstar_proxy",
    "load_Nstar_proxy",
}

# Workspace / file origin (explicit product rule: new vs loaded vs session resume)
WORKSPACE_ORIGIN_KEY = "_workspace_origin"
WORKSPACE_ORIGIN_NEW_FILE = "new_file"
WORKSPACE_ORIGIN_LOADED_FILE = "loaded_file"
WORKSPACE_ORIGIN_RESUMED_SESSION = "resumed_session"
# Opaque id for new_file workspaces; loaded/resumed identities are computed in get_workspace_identity_for_persist().
WORKSPACE_IDENTITY_KEY = "_workspace_identity"
SNAPSHOT_FILE_SCHEMA_V2 = 2

BEAM_PROJECT_SESSION_KEYS = {
    "beam_project_enabled",
    "beam_project_show_manager",
    "beam_records",
    "beam_order",
    "active_beam_id",
    "beam_last_hydrated_id",
    "beam_manager_initialized",
}
ALLOWED_EXPLICIT_NONCONTRACT_KEYS |= BEAM_PROJECT_SESSION_KEYS
ALLOWED_EXPLICIT_NONCONTRACT_KEYS |= {WORKSPACE_ORIGIN_KEY, WORKSPACE_IDENTITY_KEY}

BEAM_STATUS_PASS = "PASS"
BEAM_STATUS_FAIL = "FAIL"
BEAM_STATUS_WARN = "WARN"
BEAM_STATUS_NOT_RUN = "NOT_RUN"

# Canonical Stage 1 beam snapshot: shared input keys only.
BEAM_PROJECT_PARAM_KEYS = [
    # Geometry
    "b",
    "D",
    "L",
    "sec_shape",
    "bf",
    "tf",
    "bw",
    "tw",
    "bf_bot",
    "tf_bot",
    # Materials / design factors
    "fc",
    "fsy",
    "Ec",
    "Es",
    "phi_bend",
    "phi_shear",
    "phi_torsion",
    # Active-beam actions / load intent
    "Tu_star",
    "P_star",
    "N_star",
    "actions_source",
    "actions_mode",
    "uls_Mstar",
    "uls_Mstar_pos_manual",
    "uls_Mstar_neg_manual",
    "uls_Vstar",
    "uls_Nstar",
    "manual_uls_Vstar",
    "manual_uls_Nstar",
    "sls_Mstar",
    "sls_Mstar_pos_manual",
    "sls_Mstar_neg_manual",
    "sls_Vstar",
    "sls_Nstar",
    "manual_sls_Vstar",
    "manual_sls_Nstar",
    "Mu_star_manual",
    "Mu_star_pos_manual",
    "Mu_star_neg_manual",
    "design_actions_source",
    "inputs_detailed_mode",
    "auto_geometry",
    "auto_bottom_reo",
    "auto_shear",
    "fast_mode_show_3d",
    # Design/optimisation controls are engineering inputs, not page-local UI.
    # They must travel with the active beam so a change made on another page
    # advances the same authoritative input revision as an Inputs edit.
    "design_optimisation_goal",
    "optimisation_lock_geometry",
    "optimisation_lock_width",
    "optimisation_lock_depth",
    # Reinforcement / cover
    "nb_or_s_bot_1",
    "db_bot_1",
    "nb_or_s_bot_2",
    "db_bot_2",
    "rowgap_bot",
    "nb_or_s_top_1",
    "db_top_1",
    "nb_or_s_top_2",
    "db_top_2",
    "rowgap_top",
    "cover_bot",
    "cover_top",
    "side_cover_bot",
    "side_cover_top",
    "cover_side",
    "bot1_layout_mode",
    "bot1_count",
    "bot1_spacing",
    "bot2_layout_mode",
    "bot2_count",
    "bot2_spacing",
    "top1_layout_mode",
    "top1_count",
    "top1_spacing",
    "top2_layout_mode",
    "top2_count",
    "top2_spacing",
    "top_flange_reo_enabled",
    "bot_flange_reo_enabled",
    "top_flange_mirror_lr",
    "bot_flange_mirror_lr",
    "top_flange_left_count",
    "top_flange_left_dia",
    "top_flange_left_rows",
    "top_flange_left_row_spacing",
    "top_flange_left_clear_spacing_mode",
    "top_flange_right_count",
    "top_flange_right_dia",
    "top_flange_right_rows",
    "top_flange_right_row_spacing",
    "top_flange_right_clear_spacing_mode",
    "bot_flange_left_count",
    "bot_flange_left_dia",
    "bot_flange_left_rows",
    "bot_flange_left_row_spacing",
    "bot_flange_left_clear_spacing_mode",
    "bot_flange_right_count",
    "bot_flange_right_dia",
    "bot_flange_right_rows",
    "bot_flange_right_row_spacing",
    "bot_flange_right_clear_spacing_mode",
    "top_flange_transverse_enabled",
    "bot_flange_transverse_enabled",
    "top_flange_transverse_dia",
    "bot_flange_transverse_dia",
    "top_flange_transverse_spacing",
    "bot_flange_transverse_spacing",
    "top_flange_transverse_legs",
    "bot_flange_transverse_legs",
    *_longitudinal_row_param_keys("bot"),
    *_longitudinal_row_param_keys("top"),
    "lig_d",
    "lig_legs",
    "s_lig",
    # Ducts / shear / crack / deflection inputs
    "n_ducts",
    "duct_dia",
    "d_g",
    "k_d_option",
    "k_v_method",
    "exposure_class",
    "wmax_char_limit",
    "crack_member_type",
    "crack_k1",
    "crack_k2",
    "crack_diagram_panel",
    "crack_control_method",
    "crack_wall_thickness_mm",
    "crack_wall_in_base_zone",
    "crack_wall_horizontal_area_per_face",
    "crack_wall_vertical_spacing_mm",
    "crack_c766_restraint_type",
    "crack_c766_t1_c",
    "crack_c766_t2_c",
    "crack_c766_alpha_micro_per_c",
    "crack_c766_restraint_early",
    "crack_c766_restraint_medium",
    "crack_c766_restraint_long",
    "crack_c766_tensile_capacity_micro",
    "crack_c766_autogenous_early_micro",
    "crack_c766_autogenous_long_micro",
    "crack_c766_effective_reinforcement_ratio",
    "crack_c766_bar_diameter_mm",
    "crack_c766_cover_mm",
    "crack_c766_modular_ratio",
    "crack_c766_non_uniform_k",
    "crack_c766_stress_distribution_kc",
    "crack_c766_characteristic_tensile_mpa",
    "crack_c766_total_reinforcement_ratio",
    "crack_theta_deg",
    "defl_beff",
    "defl_support_type",
    "defl_limit_ratio",
    "defl_Fdef",
    "defl_use_simplified_ief",
    "defl_Ief_user",
    "member_faces_exposed",
    "shrinkage_env",
    "shrinkage_method",
    "shrinkage_relative_humidity_percent",
    "shrinkage_cement_class",
    "shrinkage_drying_start_age_days",
    "env_option",
    "s_bar_bot",
    "shear_auto_design",
    "shear_optimize_reinforcement",
    "t_creep",
    "age_at_loading",
    "t_shrink",
    # SFD/BMD system and moving-load inputs.  These are edited on the Design
    # page but feed the same beam actions used by the result pages.
    "design_beam_system_mode",
    "design_support_condition",
    "design_support_type_1",
    "design_support_type_2",
    "design_support_type_3",
    "design_support_type_4",
    "design_support_type_5",
    "design_support_type_6",
    "design_span_count",
    "design_span_len_1",
    "design_span_len_2",
    "design_span_len_3",
    "design_span_len_4",
    "design_span_len_5",
    "design_ms_point_count",
    "design_ms_udl_count",
    *[f"design_ms_{kind}_{index}" for kind in ("G", "Q", "g", "q", "x0", "x1", "x") for index in range(1, 9)],
    # SFD/BMD beam-definition inputs
    "span_L_m",
    "g_udl_kNm_per_m",
    "q_udl_kNm_per_m",
    "psi_udl",
    "G_point_kN",
    "Q_point_kN",
    "psi_point",
    "a_m",
    "a_udl_m",
    "a_cant_m",
    "a_overhang_m",
    "design_point_G_1",
    "design_point_G_2",
    "design_point_G_3",
    "design_point_G_4",
    "design_point_G_5",
    "design_point_G_6",
    "design_point_Q_1",
    "design_point_Q_2",
    "design_point_Q_3",
    "design_point_Q_4",
    "design_point_Q_5",
    "design_point_Q_6",
    "design_point_x_1",
    "design_point_x_2",
    "design_point_x_3",
    "design_point_x_4",
    "design_point_x_5",
    "design_point_x_6",
    "sfd_point_load_count",
    "sfd_span_L_m",
    "sfd_case",
]


def _beam_project_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")




def _sanitize_beam_record(beam_id: str, record) -> dict:
    record = record if isinstance(record, dict) else {}
    params_in = record.get("params") if isinstance(record.get("params"), dict) else {}
    params = {
        key: copy.deepcopy(params_in.get(key, SHARED_DEFAULTS.get(key)))
        for key in BEAM_PROJECT_PARAM_KEYS
    }
    meta = copy.deepcopy(record.get("meta")) if isinstance(record.get("meta"), dict) else {}
    beam_label = str(record.get("beam_label") or beam_id).strip() or beam_id
    return {
        "beam_id": beam_id,
        "beam_label": beam_label,
        "params": params,
        "meta": meta,
        "summary": _sanitize_beam_summary(record.get("summary")),
    }


def validate_beam_project_payload(payload) -> dict:
    issues = []
    payload = payload if isinstance(payload, dict) else {}
    beam_records = payload.get("beam_records")
    beam_order = payload.get("beam_order")
    active_beam_id = payload.get("active_beam_id")

    if not isinstance(beam_records, dict):
        issues.append("beam_records_missing_or_invalid")
        beam_records = {}
    if not isinstance(beam_order, list):
        issues.append("beam_order_missing_or_invalid")
        beam_order = []
    if active_beam_id is not None and active_beam_id not in beam_records:
        issues.append("active_beam_id_invalid")

    for beam_id in beam_order:
        if beam_id not in beam_records:
            issues.append(f"beam_order_missing_record:{beam_id}")

    for beam_id, record in beam_records.items():
        if not isinstance(record, dict):
            issues.append(f"beam_record_invalid:{beam_id}")
            continue
        if not isinstance(record.get("params"), dict):
            issues.append(f"beam_params_invalid:{beam_id}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


def repair_beam_project_payload(payload) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    raw_records = payload.get("beam_records") if isinstance(payload.get("beam_records"), dict) else {}

    repaired_records = {}
    for candidate_id, record in raw_records.items():
        beam_id = str((record or {}).get("beam_id") or candidate_id).strip() or str(candidate_id)
        repaired_records[beam_id] = _sanitize_beam_record(beam_id, record)

    raw_order = payload.get("beam_order") if isinstance(payload.get("beam_order"), list) else []
    repaired_order = []
    for beam_id in raw_order:
        if beam_id in repaired_records and beam_id not in repaired_order:
            repaired_order.append(beam_id)
    for beam_id in repaired_records.keys():
        if beam_id not in repaired_order:
            repaired_order.append(beam_id)

    active_beam_id = payload.get("active_beam_id")
    if active_beam_id not in repaired_records:
        active_beam_id = repaired_order[0] if repaired_order else None

    return {
        "beam_order": repaired_order,
        "active_beam_id": active_beam_id,
        "beam_records": repaired_records,
    }


def build_beam_project_payload() -> dict:
    """Return the canonical serializable multi-beam project payload."""
    ensure_beam_project_initialized()
    payload = repair_beam_project_payload(
        {
            "beam_order": copy.deepcopy(st.session_state.get("beam_order") or []),
            "active_beam_id": st.session_state.get("active_beam_id"),
            "beam_records": copy.deepcopy(st.session_state.get("beam_records") or {}),
        }
    )
    return payload


def reset_beam_project_to_single_default_if_missing() -> dict:
    """
    Legacy/backward-compatible fallback: build a one-beam project from current shared state.
    Call this after shared inputs have been loaded when no beam-project payload exists.
    """
    st.session_state["beam_project_enabled"] = True
    st.session_state["beam_project_show_manager"] = False
    st.session_state["beam_records"] = {}
    st.session_state["beam_order"] = []
    st.session_state["active_beam_id"] = None
    st.session_state["beam_last_hydrated_id"] = None
    st.session_state["beam_manager_initialized"] = False
    ensure_beam_project_initialized()
    persist_active_beam_from_shared()
    return build_beam_project_payload()


def load_beam_project_payload(payload) -> dict:
    """
    Restore the stored beam project structure, then hydrate only the active beam into shared state.
    Repairs partial payloads conservatively instead of failing hard.
    """
    repaired = repair_beam_project_payload(payload)
    if not repaired.get("beam_records"):
        return reset_beam_project_to_single_default_if_missing()

    st.session_state["beam_project_enabled"] = True
    st.session_state["beam_project_show_manager"] = False
    st.session_state["beam_records"] = copy.deepcopy(repaired["beam_records"])
    st.session_state["beam_order"] = list(repaired["beam_order"])
    st.session_state["active_beam_id"] = repaired["active_beam_id"]
    st.session_state["beam_last_hydrated_id"] = None
    st.session_state["beam_manager_initialized"] = True

    load_active_beam_into_shared(force=True)
    st.session_state[BEAM_MODULE_STARTER_SEED_DONE_KEY] = True
    return repaired


def build_beam_schedule_rows() -> list[dict]:
    """
    Report/export-ready beam schedule rows built from stored params + cached summaries only.
    No beam recalculation happens here.
    """
    payload = build_beam_project_payload()
    rows = []
    for beam_id in payload["beam_order"]:
        record = payload["beam_records"].get(beam_id, {})
        params = migrate_longitudinal_reo_snapshot(record.get("params", {}))
        summary = _sanitize_beam_summary(record.get("summary"))
        rows.append(
            {
                "active": beam_id == payload.get("active_beam_id"),
                "beam_id": beam_id,
                "beam_label": record.get("beam_label", beam_id),
                "use_for_auto_design": bool(
                    (record.get("meta") if isinstance(record.get("meta"), dict) else {}).get(
                        "use_for_auto_design", False
                    )
                ),
                "sec_shape": params.get("sec_shape"),
                "b": params.get("b"),
                "bf": params.get("bf"),
                "tf": params.get("tf"),
                "bw": params.get("bw"),
                "tw": params.get("tw"),
                "D": params.get("D"),
                "L": params.get("L"),
                "cover_top": params.get("cover_top"),
                "cover_bot": params.get("cover_bot"),
                "cover_side": params.get("cover_side"),
                "fc": params.get("fc"),
                "fsy": params.get("fsy"),
                "bot_rows": get_longitudinal_row_inputs("bot", source=params),
                "top_rows": get_longitudinal_row_inputs("top", source=params),
                "bottom_reo": summarize_longitudinal_rows("bot", source=params),
                "top_reo": summarize_longitudinal_rows("top", source=params),
                "bot1_count": params.get("bot1_count"),
                "db_bot_1": params.get("db_bot_1"),
                "top1_count": params.get("top1_count"),
                "db_top_1": params.get("db_top_1"),
                "lig_d": params.get("lig_d"),
                "lig_legs": params.get("lig_legs"),
                "s_lig": params.get("s_lig"),
                # Keep the project schedule connected to the beam's own
                # committed action/result snapshot.  These are the values
                # shown in the Batch Design editor when no imported action
                # row has explicitly replaced them.
                "n_star": params.get("uls_Nstar", params.get("N_star")),
                "vy_star": (
                    summary.get("Vu_star")
                    if summary.get("Vu_star") is not None
                    else params.get("uls_Vstar")
                ),
                "vz_star": None,
                "mx_star": params.get("Tu_star"),
                "my_star": None,
                "mz_star": (
                    summary.get("Mu_star")
                    if summary.get("Mu_star") is not None
                    else params.get("uls_Mstar")
                ),
                "design_utilisation": max(
                    (
                        value
                        for value in (
                            summary.get("Mu_utilisation"),
                            summary.get("Vu_utilisation"),
                            summary.get("crack_utilisation"),
                            summary.get("deflection_utilisation"),
                            summary.get("batch_design_utilisation"),
                        )
                        if value is not None
                    ),
                    default=None,
                ),
                # Individual values are retained for Batch Design's read-only
                # check columns. Rendering this schedule never recalculates.
                "Mu_utilisation": summary.get("Mu_utilisation"),
                "Vu_utilisation": summary.get("Vu_utilisation"),
                "crack_utilisation": summary.get("crack_utilisation"),
                "deflection_utilisation": summary.get("deflection_utilisation"),
                "overall_status": summary.get("overall_status", BEAM_STATUS_NOT_RUN),
                "strength_status": summary.get("strength_status", BEAM_STATUS_NOT_RUN),
                "detailing_status": summary.get("detailing_status", BEAM_STATUS_NOT_RUN),
                "bending_status": summary.get("bending_status", BEAM_STATUS_NOT_RUN),
                "shear_status": summary.get("shear_status", BEAM_STATUS_NOT_RUN),
                "crack_status": summary.get("crack_status", BEAM_STATUS_NOT_RUN),
                "deflection_status": summary.get("deflection_status", BEAM_STATUS_NOT_RUN),
                "last_checked_at": summary.get("last_checked_at"),
            }
        )
    return rows


def get_active_beam_record() -> dict | None:
    """Return the sanitized stored record for the current active beam."""
    payload = build_beam_project_payload()
    active_beam_id = payload.get("active_beam_id")
    if not active_beam_id:
        return None
    record = payload["beam_records"].get(active_beam_id)
    return copy.deepcopy(record) if isinstance(record, dict) else None


def get_active_beam_summary() -> dict:
    record = get_active_beam_record()
    return _sanitize_beam_summary((record or {}).get("summary"))


def _beam_records_dict() -> dict:
    records = st.session_state.get("beam_records")
    if not isinstance(records, dict):
        records = {}
        st.session_state["beam_records"] = records
    return records


def _beam_order_list() -> list[str]:
    order = st.session_state.get("beam_order")
    if not isinstance(order, list):
        order = []
        st.session_state["beam_order"] = order
    return order


def _next_beam_index() -> int:
    existing_ids = list(_beam_records_dict().keys()) + list(_beam_order_list())
    next_idx = 1
    for beam_id in existing_ids:
        if not isinstance(beam_id, str) or not beam_id.startswith("beam_"):
            continue
        try:
            next_idx = max(next_idx, int(beam_id.split("_")[-1]) + 1)
        except Exception:
            continue
    return next_idx


def _make_unique_beam_id() -> str:
    records = _beam_records_dict()
    while True:
        beam_id = f"beam_{_next_beam_index()}"
        if beam_id not in records:
            return beam_id


def _make_unique_beam_label(base_label: str) -> str:
    labels = {
        str((record or {}).get("beam_label") or "").strip()
        for record in _beam_records_dict().values()
    }
    if base_label not in labels:
        return base_label

    i = 2
    while True:
        candidate = f"{base_label} {i}"
        if candidate not in labels:
            return candidate
        i += 1


def get_beam_project_param_snapshot() -> dict:
    """Capture only the canonical active-beam shared inputs."""
    _sync_longitudinal_row_model_from_legacy_state()
    snapshot = {}
    for key in BEAM_PROJECT_PARAM_KEYS:
        snapshot[key] = copy.deepcopy(st.session_state.get(key, SHARED_DEFAULTS.get(key)))
    return snapshot


def apply_beam_project_param_snapshot(snapshot) -> None:
    """Apply a stored beam snapshot back into shared state."""
    snapshot = migrate_longitudinal_reo_snapshot(snapshot)
    # One-time compatibility migration for snapshots saved before shear and
    # axial actions gained permanent manual owners.  New snapshots always
    # contain the owner keys, so a deliberate zero is never mistaken for a
    # missing value or reseeded on a later render.
    snapshot = dict(snapshot or {})
    for canonical_key, owner_key in {
        "uls_Vstar": "manual_uls_Vstar",
        "uls_Nstar": "manual_uls_Nstar",
        "sls_Vstar": "manual_sls_Vstar",
        "sls_Nstar": "manual_sls_Nstar",
    }.items():
        owner_missing = owner_key not in snapshot
        owner_defaulted_while_legacy_value_exists = (
            float(snapshot.get(owner_key, 0.0) or 0.0) == 0.0
            and float(snapshot.get(canonical_key, 0.0) or 0.0) != 0.0
        )
        if (owner_missing or owner_defaulted_while_legacy_value_exists) and canonical_key in snapshot:
            snapshot[owner_key] = copy.deepcopy(snapshot[canonical_key])
    for key in BEAM_PROJECT_PARAM_KEYS:
        value = copy.deepcopy(snapshot.get(key, SHARED_DEFAULTS.get(key)))
        set_shared(key, value, source="beam_project_hydrate")

    # Load proxies are widget-only views of the active ULS/SLS set.
    load_proxies_from_active_set()
    recalc_derived_values()


def make_default_beam_record(beam_id, beam_label=None) -> dict:
    label = beam_label or f"Beam {_next_beam_index()}"
    now = _beam_project_now()
    return {
        "beam_id": beam_id,
        "beam_label": label,
        "params": get_beam_project_param_snapshot(),
        "meta": {
            "created_at": now,
            "updated_at": now,
        },
        "summary": make_not_run_beam_summary(),
    }


def _build_new_beam_starter_param_snapshot() -> dict:
    """Build a full canonical params snapshot for a brand-new beam."""
    snapshot: dict[str, object] = {}
    for key in BEAM_PROJECT_PARAM_KEYS:
        if key in NEW_BEAM_STARTER_DEFAULTS:
            snapshot[key] = copy.deepcopy(NEW_BEAM_STARTER_DEFAULTS[key])
        else:
            snapshot[key] = copy.deepcopy(SHARED_DEFAULTS.get(key))
    return migrate_longitudinal_reo_snapshot(snapshot)


def _apply_new_beam_starter_defaults_to_shared() -> None:
    """Seed shared state with NEW_BEAM_STARTER_DEFAULTS only."""
    for key, value in NEW_BEAM_STARTER_DEFAULTS.items():
        set_shared(str(key), copy.deepcopy(value), source="new_beam_starter_seed")

    # Keep widgets/caches for starter-controlled keys in sync on the next hydrate.
    hydrated_map = st.session_state.get("_hydrated_from_shared_map")
    for shared_key in NEW_BEAM_STARTER_DEFAULTS.keys():
        for widget_key, mapped_shared_key in TAB_KEYS.items():
            if mapped_shared_key != shared_key:
                continue
            # For action keys, clear all mapped page widget keys to prevent stale bleed.
            # For non-action keys, keep cleanup narrow to canonical Inputs widgets.
            if (shared_key not in NEW_BEAM_ACTION_SHARED_KEYS) and (not widget_key.startswith("inputs_")):
                continue
            st.session_state.pop(widget_key, None)
            st.session_state.pop(f"_cached_{widget_key}", None)
            if isinstance(hydrated_map, dict):
                hydrated_map.pop(widget_key, None)

    st.session_state["_force_inputs_widget_reseed_once"] = True


def ensure_beam_project_initialized():
    """Ensure the Stage 1 beam-project session structure exists exactly once."""
    defaults = {
        "beam_project_enabled": True,
        "beam_project_show_manager": False,
        "beam_records": {},
        "beam_order": [],
        "active_beam_id": None,
        "beam_last_hydrated_id": None,
        "beam_manager_initialized": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)

    records = _beam_records_dict()
    for beam_id, record in list(records.items()):
        if not isinstance(record, dict):
            records[beam_id] = make_default_beam_record(beam_id)
            continue
        if not isinstance(record.get("summary"), dict):
            record["summary"] = make_not_run_beam_summary()
    order = [beam_id for beam_id in _beam_order_list() if beam_id in records]
    if len(order) != len(_beam_order_list()):
        st.session_state["beam_order"] = order

    if not order and records:
        st.session_state["beam_order"] = list(records.keys())
        order = st.session_state["beam_order"]

    if not order:
        first_beam_id = _make_unique_beam_id()
        first_record = make_default_beam_record(
            first_beam_id,
            beam_label=_make_unique_beam_label("Beam 1"),
        )
        records[first_beam_id] = first_record
        st.session_state["beam_order"] = [first_beam_id]
        st.session_state["active_beam_id"] = first_beam_id
        st.session_state["beam_last_hydrated_id"] = None

    active_beam_id = st.session_state.get("active_beam_id")
    if active_beam_id not in records:
        st.session_state["active_beam_id"] = st.session_state["beam_order"][0]
        st.session_state["beam_last_hydrated_id"] = None

    st.session_state["beam_project_enabled"] = True
    st.session_state["beam_manager_initialized"] = True
    return st.session_state["active_beam_id"]


def persist_active_beam_from_shared():
    """Persist the live shared active-beam inputs back into its stored record."""
    ensure_beam_project_initialized()
    active_beam_id = st.session_state.get("active_beam_id")
    if not active_beam_id:
        return None

    records = _beam_records_dict()
    record = records.get(active_beam_id)
    if not isinstance(record, dict):
        record = make_default_beam_record(active_beam_id)

    record["beam_id"] = active_beam_id
    record["beam_label"] = str(record.get("beam_label") or active_beam_id)
    record["params"] = get_beam_project_param_snapshot()
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    meta["updated_at"] = _beam_project_now()
    record["meta"] = meta
    if not isinstance(record.get("summary"), dict):
        record["summary"] = make_not_run_beam_summary()
    records[active_beam_id] = record
    return record


def load_active_beam_into_shared(force=False):
    """
    Hydrate the selected stored beam into shared state once per explicit beam load.
    The guard prevents stored data from overwriting live shared state on every rerun.
    """
    ensure_beam_project_initialized()
    active_beam_id = st.session_state.get("active_beam_id")
    if not active_beam_id:
        return False

    if (not force) and st.session_state.get("beam_last_hydrated_id") == active_beam_id:
        return False

    record = _beam_records_dict().get(active_beam_id)
    if not isinstance(record, dict):
        return False

    apply_beam_project_param_snapshot(record.get("params") or {})
    st.session_state["beam_last_hydrated_id"] = active_beam_id
    # One-shot: force tab widgets to match shared after beam record applied (any page).
    st.session_state["_force_hydrate_widgets_after_beam_load"] = True
    st.session_state["inputs_dirty"] = True
    st.session_state["_inputs_dirty"] = True
    return True


def set_active_beam(beam_id):
    """
    Auto-save the current active beam before switching, then hydrate the next one.
    This is an internal beam-manager persistence step only, not the explicit project save.
    """
    _write_debug_ndjson_line(
        {
            "id": f"log_{int(time.time() * 1000)}_H22",
            "timestamp": int(time.time() * 1000),
            "location": "state_and_helpers.py:set_active_beam:entry",
            "message": "Entered set_active_beam",
            "data": {
                "requested_beam_id": str(beam_id or ""),
                "current_beam_id": str(st.session_state.get("active_beam_id") or ""),
                "selector_state": str(st.session_state.get("beam_manager_active_selector") or ""),
                "beam_order": [str(item) for item in st.session_state.get("beam_order", [])],
            },
            "runId": "auto_design_debug",
            "hypothesisId": "H22",
        }
    )
    ensure_beam_project_initialized()
    records = _beam_records_dict()
    if beam_id not in records:
        return False

    current_beam_id = st.session_state.get("active_beam_id")
    if beam_id == current_beam_id:
        return False

    if current_beam_id in records:
        persist_active_beam_from_shared()
    st.session_state["active_beam_id"] = beam_id
    st.session_state["beam_last_hydrated_id"] = None
    load_active_beam_into_shared(force=True)
    st.session_state[BEAM_MODULE_STARTER_SEED_DONE_KEY] = True
    _write_debug_ndjson_line(
        {
            "id": f"log_{int(time.time() * 1000)}_H22",
            "timestamp": int(time.time() * 1000),
            "location": "state_and_helpers.py:set_active_beam:exit",
            "message": "Completed set_active_beam",
            "data": {
                "active_beam_id": str(st.session_state.get("active_beam_id") or ""),
                "beam_last_hydrated_id": str(st.session_state.get("beam_last_hydrated_id") or ""),
                "selector_state": str(st.session_state.get("beam_manager_active_selector") or ""),
            },
            "runId": "auto_design_debug",
            "hypothesisId": "H22",
        }
    )
    return True


def add_new_beam_record():
    """Add a brand-new beam seeded from NEW_BEAM_STARTER_DEFAULTS."""
    ensure_beam_project_initialized()
    persist_active_beam_from_shared()

    beam_id = _make_unique_beam_id()
    beam_label = _make_unique_beam_label(f"Beam {_next_beam_index()}")
    record = make_default_beam_record(beam_id, beam_label=beam_label)
    record["params"] = _build_new_beam_starter_param_snapshot()
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    meta[BEAM_STARTER_META_SENTINEL_KEY] = True
    meta["starter_seeded_at"] = _beam_project_now()
    record["meta"] = meta
    record["summary"] = make_not_run_beam_summary()

    records = _beam_records_dict()
    records[beam_id] = record
    _beam_order_list().append(beam_id)
    set_active_beam(beam_id)
    _apply_new_beam_starter_defaults_to_shared()
    recalc_derived_values()
    update_results()
    persist_active_beam_from_shared()
    st.session_state[WORKSPACE_ORIGIN_KEY] = WORKSPACE_ORIGIN_NEW_FILE
    st.session_state[WORKSPACE_IDENTITY_KEY] = uuid.uuid4().hex
    st.session_state["_new_beam_created_this_run"] = True
    return beam_id


def reset_app_to_clean_starter_workspace() -> None:
    """
    Explicit "new clean workspace": one brand-new beam from NEW_BEAM_STARTER_DEFAULTS,
    all canonical design actions zeroed, file + in-memory snapshots replaced so cold
    reopen does not rehydrate stale actions.

    Does not clone the previous beam. Duplicate / project load / Add beam are unchanged.
    """
    st.session_state[DISABLE_SNAPSHOT_RESTORE_KEY] = True

    for key in (
        "_snapshot_restore_complete",
        "_restored_from_snapshot",
        "_restore_guard_active",
        "_restore_guard_ts",
    ):
        st.session_state.pop(key, None)

    st.session_state.pop("jump_to", None)
    clear_cached_and_widget_restore_keys()

    hm = st.session_state.get("_hydrated_from_shared_map")
    if isinstance(hm, dict):
        hm.clear()

    # Replace beam project with exactly one new beam (starter params — not a clone).
    st.session_state["beam_records"] = {}
    st.session_state["beam_order"] = []
    st.session_state["active_beam_id"] = None
    st.session_state["beam_last_hydrated_id"] = None
    st.session_state["beam_manager_initialized"] = False

    beam_id = _make_unique_beam_id()
    beam_label = _make_unique_beam_label("Beam 1")
    record = make_default_beam_record(beam_id, beam_label=beam_label)
    record["params"] = _build_new_beam_starter_param_snapshot()
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    meta[BEAM_STARTER_META_SENTINEL_KEY] = True
    meta["starter_seeded_at"] = _beam_project_now()
    record["meta"] = meta
    record["summary"] = make_not_run_beam_summary()

    records = _beam_records_dict()
    records[beam_id] = record
    st.session_state["beam_order"] = [beam_id]
    st.session_state["active_beam_id"] = beam_id
    st.session_state["beam_manager_initialized"] = True

    # Full starter snapshot into shared (all BEAM_PROJECT_PARAM_KEYS + canonical zeros for actions)
    apply_beam_project_param_snapshot(record["params"])
    # Clear mapped widget keys / caches so Inputs does not show pre-reset values
    _apply_new_beam_starter_defaults_to_shared()

    st.session_state[BEAM_MODULE_STARTER_SEED_DONE_KEY] = True
    st.session_state["_user_has_edited_anything"] = False
    st.session_state["beam_last_hydrated_id"] = beam_id
    st.session_state[WORKSPACE_ORIGIN_KEY] = WORKSPACE_ORIGIN_NEW_FILE
    st.session_state[WORKSPACE_IDENTITY_KEY] = uuid.uuid4().hex

    reset_results_state()
    recalc_derived_values()
    update_results()
    persist_active_beam_from_shared()
    st.session_state["cached_results"] = copy.deepcopy(st.session_state.get("results"))
    st.session_state["inputs_dirty"] = False

    shared_out: dict = {}
    for k in SHARED_DEFAULTS.keys():
        if k in st.session_state:
            shared_out[k] = st.session_state[k]
    save_shared_snapshot(shared_out, workspace_origin=WORKSPACE_ORIGIN_NEW_FILE)
    cid = get_client_id()
    _persistent_store()[cid] = {
        "shared": shared_out,
        "widgets": {},
        "workspace_origin": WORKSPACE_ORIGIN_NEW_FILE,
        "workspace_identity": get_workspace_identity_for_persist(),
    }

    st.session_state[DISABLE_SNAPSHOT_RESTORE_KEY] = False
    st.rerun()


def duplicate_active_beam_record():
    """Duplicate the current active beam into a new stored beam."""
    ensure_beam_project_initialized()
    persist_active_beam_from_shared()

    active_beam_id = st.session_state.get("active_beam_id")
    active_record = _beam_records_dict().get(active_beam_id, {})
    base_label = str(active_record.get("beam_label") or "Beam").strip() or "Beam"

    beam_id = _make_unique_beam_id()
    beam_label = _make_unique_beam_label(f"{base_label} Copy")
    record = make_default_beam_record(beam_id, beam_label=beam_label)
    record["params"] = copy.deepcopy((active_record or {}).get("params") or get_beam_project_param_snapshot())
    # Duplicates start as unverified until this beam becomes the active checked beam.
    record["summary"] = make_not_run_beam_summary()

    records = _beam_records_dict()
    records[beam_id] = record
    _beam_order_list().append(beam_id)
    set_active_beam(beam_id)
    return beam_id


def delete_beam_record(beam_id):
    """Delete a stored beam without ever leaving the project empty."""
    ensure_beam_project_initialized()
    order = _beam_order_list()
    if beam_id not in _beam_records_dict() or len(order) <= 1:
        return False

    records = _beam_records_dict()
    was_active = beam_id == st.session_state.get("active_beam_id")

    records.pop(beam_id, None)
    st.session_state["beam_order"] = [item for item in order if item != beam_id]

    if not was_active:
        return True

    fallback_beam_id = st.session_state["beam_order"][0]
    st.session_state["active_beam_id"] = fallback_beam_id
    st.session_state["beam_last_hydrated_id"] = None
    load_active_beam_into_shared(force=True)
    st.session_state[BEAM_MODULE_STARTER_SEED_DONE_KEY] = True
    return True


def update_active_beam_summary_from_results(
    *,
    bending_rows: list[dict] | None = None,
    shear_rows: list[dict] | None = None,
    crack_rows: list[dict] | None = None,
    deflection_rows: list[dict] | None = None,
):
    """
    Cache a lightweight summary for the active beam using already-available result keys.
    Never computes other beams, and falls back to NOT_RUN when results are not trustworthy yet.
    """
    ensure_beam_project_initialized()
    active_beam_id = st.session_state.get("active_beam_id")
    records = _beam_records_dict()
    if active_beam_id not in records:
        return None

    record = records[active_beam_id]
    if st.session_state.get("_dirty", False):
        # Save/load may call this before the active beam's latest edits have been recomputed.
        existing_summary = record.get("summary")
        return existing_summary if isinstance(existing_summary, dict) else make_not_run_beam_summary()

    summary = make_not_run_beam_summary()

    phi_Mu_cap = _safe_summary_float(st.session_state.get("phi_Mu_cap"))
    Mu_utilisation = _safe_summary_float(st.session_state.get("Mu_utilisation"))
    phi_Vu_cap = _safe_summary_float(st.session_state.get("phi_Vu_cap"))
    Vu_utilisation = _safe_summary_float(st.session_state.get("Vu_utilisation"))
    crack_utilisation = _safe_summary_float(st.session_state.get("crack_utilisation"))
    deflection_utilisation = _safe_summary_float(st.session_state.get("deflection_utilisation"))
    sigma_allow_table = _safe_summary_float(st.session_state.get("sigma_allow_table"))
    wmax_char = _safe_summary_float(st.session_state.get("wmax_char"))
    deflection_limit_mm = _safe_summary_float(st.session_state.get("deflection_limit_mm"))

    if (phi_Mu_cap is not None and phi_Mu_cap > 0.0) or (Mu_utilisation is not None and Mu_utilisation > 0.0):
        summary["bending_status"] = normalize_beam_status(utilisation=Mu_utilisation)

    if (phi_Vu_cap is not None and phi_Vu_cap > 0.0) or (Vu_utilisation is not None and Vu_utilisation > 0.0):
        summary["shear_status"] = normalize_beam_status(utilisation=Vu_utilisation)

    if ((sigma_allow_table is not None and sigma_allow_table > 0.0) or (wmax_char is not None and wmax_char > 0.0)):
        crack_pass = None
        if "passes_table" in st.session_state and "passes_w" in st.session_state:
            crack_pass = bool(st.session_state.get("passes_table")) and bool(st.session_state.get("passes_w"))
        summary["crack_status"] = normalize_beam_status(utilisation=crack_utilisation, pass_flag=crack_pass)

    if (deflection_limit_mm is not None and deflection_limit_mm > 0.0):
        summary["deflection_status"] = normalize_beam_status(utilisation=deflection_utilisation)

    if any(rows is not None for rows in (bending_rows, shear_rows, crack_rows, deflection_rows)):
        classified = classify_beam_check_rows(
            bending_rows=bending_rows,
            shear_rows=shear_rows,
            crack_rows=crack_rows,
            deflection_rows=deflection_rows,
        )
        summary["strength_status"] = classified["strength_status"]
        summary["detailing_status"] = classified["detailing_status"]
        summary["overall_status"] = classified["overall_status"]
    else:
        existing_summary = _sanitize_beam_summary(record.get("summary"))
        summary["strength_status"] = existing_summary.get("strength_status", BEAM_STATUS_NOT_RUN)
        summary["detailing_status"] = existing_summary.get("detailing_status", BEAM_STATUS_NOT_RUN)
        summary["overall_status"] = get_beam_overall_status(summary)

    actions = resolve_design_actions()
    summary["last_checked_at"] = _beam_project_now()
    summary["Mu_star"] = _safe_summary_float(actions.get("Mu"))
    summary["phi_Mu_cap"] = phi_Mu_cap
    summary["Mu_utilisation"] = Mu_utilisation
    summary["Vu_star"] = _safe_summary_float(actions.get("Vu"))
    summary["phi_Vu_cap"] = phi_Vu_cap
    summary["Vu_utilisation"] = Vu_utilisation
    summary["crack_utilisation"] = crack_utilisation
    summary["deflection_utilisation"] = deflection_utilisation

    if summary["overall_status"] == BEAM_STATUS_NOT_RUN:
        # Keep the existing cached summary if current results are still not trustworthy.
        existing_summary = record.get("summary")
        return existing_summary if isinstance(existing_summary, dict) else summary

    record["summary"] = summary
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    meta["summary_updated_at"] = summary["last_checked_at"]
    record["meta"] = meta
    records[active_beam_id] = record
    return summary


def _active_load_prefix() -> str:
    mode = st.session_state.get("loads_edit_mode", "ULS")
    return "uls" if mode == "ULS" else "sls"


def sync_load_edit_mode_from_toggle(active_slug: str | None = None) -> str:
    """Keep the SLS/ULS mode string aligned with the shared toggle boolean."""
    toggle_keys = {
        "inputs": "inputs_loads_edit_toggle",
        "design": "design_loads_edit_toggle",
    }
    selected_widget_key = ""
    last_widget = str(st.session_state.get("_last_user_widget_key") or "")
    if last_widget in set(toggle_keys.values()):
        selected_widget_key = last_widget
    else:
        slug = str(active_slug or st.session_state.get("page_slug") or "").strip().lower()
        candidate = toggle_keys.get(slug, "")
        if candidate and candidate in st.session_state:
            selected_widget_key = candidate

    if selected_widget_key and selected_widget_key in st.session_state:
        use_sls = bool(st.session_state.get(selected_widget_key))
    else:
        use_sls = bool(st.session_state.get("loads_edit_toggle", False))

    mode = "SLS" if use_sls else "ULS"
    st.session_state["loads_edit_toggle"] = use_sls
    st.session_state["loads_edit_mode"] = mode
    # Do not let the Inputs route's default/shared projection overwrite the
    # Load Analysis-owned SLS mode while navigating.  Each route restores its
    # own widget from its owner; only the active route's key is authoritative.
    active_slug = str(active_slug or st.session_state.get("page_slug") or "").strip().lower()
    active_key = toggle_keys.get(active_slug)
    if active_key and active_key in st.session_state:
        st.session_state[active_key] = use_sls
    return mode


def is_design_governing() -> bool:
    return st.session_state.get("actions_mode", "manual") == "design"


def resolve_design_actions(state: dict | None = None) -> dict:
    source_state = state if isinstance(state, dict) else st.session_state
    return resolve_design_actions_from_state(source_state)


def load_proxies_from_active_set():
    with speed_profile_section("shared_state_hydration.load_proxies_from_active_set", category="state_mutation"):
        actions_mode = get_param("actions_mode", "manual")
        design_mode = actions_mode == "design"
        # When design actions drive the app we must NOT restore manual proxies
        if design_mode:
            return
        p = _active_load_prefix()
        signed_m = float(st.session_state.get(f"{p}_Mstar", 0.0) or 0.0)
        m_pos = float(st.session_state.get(f"{p}_Mstar_pos_manual", max(0.0, signed_m)) or 0.0)
        m_neg = float(st.session_state.get(f"{p}_Mstar_neg_manual", max(0.0, -signed_m)) or 0.0)
        st.session_state["load_Nstar_proxy"] = float(st.session_state.get(f"manual_{p}_Nstar", 0.0) or 0.0)
        st.session_state["load_Vstar_proxy"] = float(st.session_state.get(f"manual_{p}_Vstar", 0.0) or 0.0)
        st.session_state["load_Mstar_pos_proxy"] = float(max(0.0, m_pos))
        st.session_state["load_Mstar_neg_proxy"] = float(max(0.0, m_neg))
        # Legacy compatibility proxy (signed)
        st.session_state["load_Mstar_proxy"] = float(m_pos - m_neg)
        if p == "uls":
            st.session_state["Mu_star_pos_manual"] = float(max(0.0, m_pos))
            st.session_state["Mu_star_neg_manual"] = float(max(0.0, m_neg))
            st.session_state["Mu_star_manual"] = float(m_pos - m_neg)


def save_proxies_to_active_set():
    actions_mode = get_param("actions_mode", "manual")
    design_mode = actions_mode == "design"
    if design_mode:
        return
    p = _active_load_prefix()
    other = "sls" if p == "uls" else "uls"
    before_other = (
        st.session_state.get(f"{other}_Nstar"),
        st.session_state.get(f"{other}_Vstar"),
        st.session_state.get(f"{other}_Mstar"),
    )

    st.session_state[f"manual_{p}_Nstar"] = float(st.session_state.get("load_Nstar_proxy", 0.0) or 0.0)
    st.session_state[f"manual_{p}_Vstar"] = float(st.session_state.get("load_Vstar_proxy", 0.0) or 0.0)
    # Compatibility projections remain readable by legacy report consumers,
    # but they are no longer the owner selected by widgets or the resolver.
    st.session_state[f"{p}_Nstar"] = st.session_state[f"manual_{p}_Nstar"]
    st.session_state[f"{p}_Vstar"] = st.session_state[f"manual_{p}_Vstar"]
    m_pos = float(st.session_state.get("load_Mstar_pos_proxy", max(0.0, st.session_state.get("load_Mstar_proxy", 0.0) or 0.0)) or 0.0)
    m_neg = float(st.session_state.get("load_Mstar_neg_proxy", max(0.0, -(st.session_state.get("load_Mstar_proxy", 0.0) or 0.0))) or 0.0)
    st.session_state[f"{p}_Mstar_pos_manual"] = float(max(0.0, m_pos))
    st.session_state[f"{p}_Mstar_neg_manual"] = float(max(0.0, m_neg))
    st.session_state[f"{p}_Mstar"] = float(max(0.0, m_pos) - max(0.0, m_neg))
    # Legacy compatibility proxy (signed)
    st.session_state["load_Mstar_proxy"] = float(st.session_state[f"{p}_Mstar"])
    if p == "uls":
        st.session_state["Mu_star_pos_manual"] = float(st.session_state[f"{p}_Mstar_pos_manual"])
        st.session_state["Mu_star_neg_manual"] = float(st.session_state[f"{p}_Mstar_neg_manual"])
        st.session_state["Mu_star_manual"] = float(st.session_state[f"{p}_Mstar"])

    # Keep shared/report action keys in sync with the active load set
    # (Report tables read Mu_star/Vu_star/N_star; widgets edit uls/sls *_Mstar keys)
    st.session_state["N_star"] = st.session_state[f"{p}_Nstar"]
    st.session_state["Vu_star"] = st.session_state[f"{p}_Vstar"]
    st.session_state["Mu_star"] = st.session_state[f"{p}_Mstar"]

    after_other = (
        st.session_state.get(f"{other}_Nstar"),
        st.session_state.get(f"{other}_Vstar"),
        st.session_state.get(f"{other}_Mstar"),
    )

    if before_other != after_other:
        debug_print("[TRIPWIRE] Cross-write detected! save_proxies_to_active_set modified BOTH ULS and SLS.")


_MANUAL_DESIGN_ACTION_PROXY_KEYS = frozenset(
    {
        "load_Mstar_proxy",
        "load_Mstar_pos_proxy",
        "load_Mstar_neg_proxy",
        "load_Vstar_proxy",
        "load_Nstar_proxy",
    }
)


def _synchronize_manual_design_action_proxy_for_commit(shared_key: str) -> tuple[str, ...]:
    """Promote one edited action proxy before the beam snapshot is captured.

    Result pages reuse the Inputs action widget keys, so their generic widget
    callback receives a proxy key rather than a canonical ULS/SLS field.  The
    proxy and canonical action set must be promoted on the same callback and
    committed as one revision; otherwise route hydration can restore the older
    canonical action over the value the user just entered.
    """

    resolved_shared_key = str(shared_key or "").strip()
    if resolved_shared_key not in _MANUAL_DESIGN_ACTION_PROXY_KEYS:
        return (resolved_shared_key,) if resolved_shared_key else ()
    if str(get_param("actions_mode", "manual") or "manual").strip().lower() == "design":
        return (resolved_shared_key,)

    active_prefix = _active_load_prefix()
    save_proxies_to_active_set()

    # Rebuild report/calculation aliases from the canonical action sets.  This
    # is especially important while viewing SLS: editing SLS must not make an
    # SLS value masquerade as the ULS reporting action.
    derived_updates = derive_design_action_session_updates(st.session_state)
    for key, value in derived_updates.items():
        st.session_state[key] = value

    canonical_keys = {
        resolved_shared_key,
        f"{active_prefix}_Mstar",
        f"{active_prefix}_Mstar_pos_manual",
        f"{active_prefix}_Mstar_neg_manual",
        f"{active_prefix}_Vstar",
        f"{active_prefix}_Nstar",
        f"manual_{active_prefix}_Vstar",
        f"manual_{active_prefix}_Nstar",
        "load_Mstar_proxy",
        "load_Mstar_pos_proxy",
        "load_Mstar_neg_proxy",
        "load_Vstar_proxy",
        "load_Nstar_proxy",
        *derived_updates.keys(),
    }
    return tuple(sorted(str(key) for key in canonical_keys if str(key)))


def derive_design_actions():
    """
    Single source of truth for Mu*, Vu*, N*.

    Called every render cycle.
    """
    with speed_profile_section("shared_state_hydration.derive_design_actions", category="state_mutation"):
        for key, value in derive_design_action_session_updates(st.session_state).items():
            st.session_state[key] = value


def _allowed_shared_keys() -> set[str]:
    return set(SHARED_DEFAULTS.keys())


def _allowed_widget_keys() -> set[str]:
    # TAB_KEYS maps widget_key -> shared_key
    return set(TAB_KEYS.keys())


def _allowed_ui_keys() -> set[str]:
    try:
        return set(UI_STATE_DEFAULTS.keys())
    except Exception:
        return set()


def allowed_session_state_keys() -> set[str]:
    # Keys we consider "contract-approved"
    return _allowed_shared_keys() | _allowed_widget_keys() | _allowed_ui_keys()


def audit_session_state_keys(tag: str = "", page: str | None = None) -> dict:
    """
    Debug tripwire: detect rogue keys and likely collisions.
    Does NOT raise; returns dict and optionally logs.
    """
    allowed = allowed_session_state_keys()
    current = set(st.session_state.keys())

    def _is_allowed_noncontract_key(k: str) -> bool:
        if k in ALLOWED_EXPLICIT_NONCONTRACT_KEYS:
            return True
        return any(k.startswith(p) for p in ALLOWED_SESSION_PREFIXES)

    rogue = sorted(
        k for k in current
        if (k not in allowed)
        and (not _is_allowed_noncontract_key(k))
    )

    # Widget/shared collision risk: any widget key equals a shared key
    shared = _allowed_shared_keys()
    widget = _allowed_widget_keys()
    collisions = sorted(shared.intersection(widget))

    info = {
        "tag": tag,
        "page": page or st.session_state.get("active_page", ""),
        "rogue_count": len(rogue),
        "rogue_keys": rogue[:50],
        "collisions_count": len(collisions),
        "collisions": collisions[:50],
    }
    return info


def _shared_state_payload() -> dict:
    """Return current shared state values only (safe serializable snapshot)."""
    payload = {}
    for k in SHARED_DEFAULTS.keys():
        payload[k] = st.session_state.get(k, None)
    return payload


def snapshot_shared_state(tag: str = "", page: str | None = None) -> dict:
    """
    Capture SHARED_DEFAULTS values into a snapshot file.
    Returns snapshot dict.
    """
    snap = {
        "tag": tag,
        "page": page or st.session_state.get("active_page", ""),
        "t": time.time(),
        "shared": _shared_state_payload(),
    }
    try:
        with open(_debug_snapshot_path(), "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, default=str)
    except Exception:
        pass
    return snap


def diff_shared_state(prev: dict | None, curr: dict | None) -> list[dict]:
    """
    Compare two snapshots and return list of changes for shared keys.
    """
    if not prev or not curr:
        return []
    prev_shared = prev.get("shared", {}) if isinstance(prev, dict) else {}
    curr_shared = curr.get("shared", {}) if isinstance(curr, dict) else {}

    changes = []
    for k in SHARED_DEFAULTS.keys():
        a = prev_shared.get(k, None)
        b = curr_shared.get(k, None)
        if a != b:
            changes.append({"key": k, "from": a, "to": b})
    return changes


def load_last_snapshot() -> dict | None:
    try:
        with open(_debug_snapshot_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def debug_tripwire_hook(tag: str = "", page: str | None = None) -> None:
    """
    Debug hook: log only SHARED changes + DEFAULT resets.
    Writes to ~/Documents/blank_app_state_tripwire.log and snapshot json.
    """
    if not st.session_state.get("_debug_state_tripwire", False):
        return

    try:
        prev = load_last_snapshot()

        curr = {
            "tag": tag,
            "page": page or st.session_state.get("page_slug", st.session_state.get("active_page", "")),
            "t": time.time(),
            "shared": _shared_state_payload(),
        }

        changes = diff_shared_state(prev, curr)

        # Log all shared changes (optional but useful)
        if changes:
            _append_debug_log(
                f"SHARED_CHANGED tag={tag} page={curr.get('page','')} changes={json.dumps(changes, default=str)[:5000]}"
            )

        # Log default resets ONLY (this is the key signal)
        default_resets = []
        for ch in changes:
            k = ch["key"]
            default = SHARED_DEFAULTS.get(k, None)
            if default is not None and ch["to"] == default and ch["from"] != default:
                default_resets.append({"key": k, "from": ch["from"], "to": ch["to"], "default": default})

            if default_resets and st.session_state.get("_wipe_recovery_mode", False):
                _append_debug_log(
                    f"DEFAULT_RESET tag={tag} page={curr.get('page','')} resets={json.dumps(default_resets, default=str)[:5000]}"
                )

        # Update snapshot for next run
        try:
            with open(_debug_snapshot_path(), "w", encoding="utf-8") as f:
                json.dump(curr, f, indent=2, default=str)
        except Exception:
            pass

    except Exception:
        _append_debug_log("TRIPWIRE_EXCEPTION " + traceback.format_exc())

# Explicit set of result keys (for RULE 4 checks)
RESULT_KEYS = {
    "phi_Mu_cap",
    "Mu_utilisation",
    "phi_Vu_cap",
    "Vu_utilisation",
    "phi_Tu_cap",
    "Tu_utilisation",
    "crack_width",
    "crack_sr_max_mm",
    "crack_utilisation",
    # Shrinkage
    "eps_cs_total",
    "eps_cs_total_micro",
    "eps_cse",
    "eps_csd_t",
    "th_shrinkage",
    "k1_shrinkage",
    # Creep
    "phi_cc_t",
    "phi_cc_star_table",
    "eps_cc",
    "eps_cc_micro",
    "k2_creep",
    "k3_creep",
    "k4_creep",
    "k5_creep",
    "k6_creep",
    # Crack control summary
    "sigma_sr",
    "sigma_allow_table",
    "w_calc",
    "wmax_char",
    "passes_table",
    "passes_w",
    # Crack control (active tension reinforcement participation)
    "crack_tension_face",
    "crack_active_bar_count",
    "crack_active_bar_dias",
    "crack_active_bar_spacing_mm",
    "crack_tension_width_mm",
    "crack_Ast_active_mm2",
    "crack_flange_participation_used",
    "crack_web_participation_used",
    "crack_detailing_warning",
    # Bending SLS → crack link
    "sigma_s_sls",
    "bending_sls_dn_mm",
    "bending_sls_y_tension_outer",
    "bending_sls_eps_s_outer",
    "bending_sls_fs_outer",
    "bending_has_positive_case",
    "bending_has_negative_case",
    # SFD/BMD computed results
    "sfd_Msls_max_kNm",
    "sfd_Vsls_max_kN",
    "sfd_Mmax_abs_kNm",
    "sfd_Vmax_abs_kN",
    "preview_M_uls_kNm",
    "preview_V_uls_kN",
    "preview_M_sls_kNm",
    "preview_V_sls_kN",
    "design_M_uls_kNm",
    "design_M_uls_kNm_signed",
    "design_V_uls_kN",
    "design_M_sls_kNm",
    "design_M_sls_kNm_signed",
    "design_V_sls_kN",
    "M_pos_max_uls_kNm",
    "M_neg_min_uls_kNm",
    "M_pos_max_sls_kNm",
    "M_neg_min_sls_kNm",
    "sfd_span_L_m",  # Span length for SFD/deflection pages (m)
    "sfd_case",  # Current teaching case (string)
    # SFD/BMD loading results (computed from UDL inputs)
    "g_udl_kNm_per_m",
    "q_udl_kNm_per_m",
    "psi_udl",
    "w_sls_kNm_per_m",
    "w_uls_kNm_per_m",
    # SFD/BMD point load results (computed from point load inputs)
    "G_point_kN",
    "Q_point_kN",
    "psi_point",
    "P_sls_kN",
    "P_uls_kN",
    # Deflection computed results
    "deflection_total_mm",
    "deflection_limit_mm",
    "deflection_utilisation",
    "delta_short_total",
    "delta_long_add",
    "delta_total",
    # Load actions by module (derived wiring)
    "actions_bending",
    "actions_shear",
    "actions_crack",
    "actions_deflection",
    # Other computed results
    "Vu_max_kN",
    "phi_Vu_max_kN",
    "V_eq_kN",
    "Vuc_utilisation",
    "shear_longitudinal_tension_increment",
    "shear_Ast_required_tension_envelope",
    "shear_Ast_available_anchored_active",
    "shear_Ast_available_anchored_web",
    "shear_Ast_available_anchored_flange",
    "shear_flange_bars_participating",
    "shear_longitudinal_detailing_ok",
    # Optional flange transverse detailing/distribution reporting
    "flange_transverse_reo_present_top",
    "flange_transverse_reo_present_bottom",
    "flange_transverse_spacing_top",
    "flange_transverse_spacing_bottom",
    "flange_transverse_detailing_note",
    "active_tension_face",
    "active_tension_Ast_mm2",
    "active_tension_width_mm",
    "active_tension_flange_participating",
    "active_tension_warning",
    # Shear report outputs (PDF)
    "shear_steps",
    "shear_report",
    "shear_zone_results",
    "shear_design_status",
    "shear_design_error",
    "shear_auto_selected_lig_d_mm",
    "shear_auto_selected_legs",
    "shear_x",
    "shear_V",
    "shear_V_signed",
    "shear_M_uls_kNm",
    "shear_M_sls_kNm",
    "moment_x",
    "moment_values",
    "crack_bmd_cache_fingerprint",
    "bmd_support_positions_m",
    "bmd_support_types",
    "V_max",
    "req_asv_s",
    "prov_asv_s",
    "shear_util_min",
    "shear_util_x",
    "shear_envelope_status",
    "support_type",
    "critical_shear_x",
    "critical_shear_V",
    "shear_k_v",
    "shear_theta_v_deg",
    "shear_theta_v_rad",
    "shear_Vuc_kN",
    "shear_Vus_kN",
    "shear_Vu_total_kN",
    "shear_spacing_end_mm",
    "shear_spacing_mid_mm",
    # Provided link spacing (user input) vs governing envelope — see shear_core / update_results
    "shear_provided_input_spacing_mm",
    "shear_input_spacing_mm",
    "shear_sectional_check_spacing_mm",
    "shear_required_spacing_mm",
    "shear_effective_spacing_mm",
    "shear_governing_spacing_source",
    "canonical_shear_status",
    "canonical_shear_ok",
    "canonical_shear_util",
    "canonical_shear_reason",
    "canonical_shear_source",
    "canonical_shear_effective_spacing_mm",
    "canonical_shear_required_spacing_mm",
    "canonical_shear_provided_spacing_mm",
    "canonical_shear_spacing_override_active",
    "canonical_shear_spacing_override_reason",
    "shear_governing_check_name",
    "shear_governing_demand_kN",
    "shear_governing_capacity_kN",
    "shear_governing_util",
    "shear_governing_status",
    "shear_governing_reason",
    "shear_governing_source",
    "shear_truth_status",
    "shear_truth_reason",
    "shear_truth_inconsistent_status_override",
    "shear_truth_util_governing",
    "shear_truth_web_util_governing",
    "shear_truth_util_source",
    "shear_truth_web_util_source",
    "shear_truth_governing_check_name",
    "shear_truth_governing_reason",
    "shear_truth_governing_source",
    "shear_util_governing",
    "final_shear_status_source",
    "final_shear_truth_resolved",
    "final_shear_truth_failure_reason",
    "published_result_spacing_mm",
    "published_result_spacing_meaning",
    "final_shear_spacing_reason",
    "final_shear_publication_path",
    "final_shear_truth_bundle_complete",
    "summary_shear_truth_consume_reason",
    "shear_truth_contradiction_detected",
    "shear_truth_contradiction_reason",
    "shear_debug_s_eff_mm",
    "shear_spacing_governing",
    "shear_spacing_profile_min",
    "shear_spacing_profile_max",
    "shear_s_end",
    "shear_s_mid",
    "shear_mid_spacing_calc_mm",
    "shear_mid_spacing_mode",
    "V_mid_kN",
    # Selected / final design actions (chosen from manual or SFD/BMD page)
    "actions_source",
    "Mu_star",
    "Mu_star_kNm",
    "Mu_star_kNm_signed",
    "Vu_star",
    "phi_Mu_pos_kNm",
    "phi_Mu_neg_kNm",
    "Mu_nom_pos_kNm",
    "Mu_nom_neg_kNm",
    "bending_util_pos",
    "bending_util_neg",
    "bending_status_pos",
    "bending_status_neg",
    "bending_has_sagging_case",
    "bending_has_hogging_case",
    "bending_governing_case",
    "bending_util_governing",
    # ULS stress block (positive / sagging) for diagrams — c = neutral axis depth, γ = block factor
    "bending_uls_c_pos_mm",
    "bending_uls_gamma_pos",
    # Bending min requirements / neutral axis checks
    "Mx_min_req",
    "As_min_req",
    "k_u",
    "k_u_lim",
    # Duct totals (computed from n_ducts + duct_dia)
    "A_duct_total",
    "sum_duct",
    # SFD/BMD span length (computed result)
    "span_L_m",
    # Deflection: computed effective design load (from V, L, support type)
    "fd_ef_calc_kNm",
    # Inputs-page assistant outputs
    "auto_design_steps",
    "auto_design_status",
}

# ---- REQUIRED RESULT KEYS (actions selection) ----
# These are derived outputs written via update_results() from Inputs/Bending.
_RESULT_KEYS_REQUIRED = {
    "actions_source",
    "Mu_star",
    "Mu_star_kNm",
    "Vu_star",
}
RESULT_KEYS |= _RESULT_KEYS_REQUIRED

# Safety check (fail fast if something later overwrites RESULT_KEYS)
_missing = _RESULT_KEYS_REQUIRED - RESULT_KEYS
if _missing:
    raise KeyError(f"[SESSION STATE CONTRACT] RESULT_KEYS missing required keys: {_missing}")

# Defaults for derived outputs (results). These are NOT user inputs.
RESULT_DEFAULTS = {k: 0.0 for k in RESULT_KEYS}
# If any results are non-numeric, set them explicitly:
RESULT_DEFAULTS.update({
    "passes_table": False,
    "passes_w": False,
    "crack_tension_face": "",
    "crack_active_bar_count": 0.0,
    "crack_active_bar_dias": [],
    "crack_active_bar_spacing_mm": [],
    "crack_tension_width_mm": 0.0,
    "crack_Ast_active_mm2": 0.0,
    "crack_flange_participation_used": False,
    "crack_web_participation_used": False,
    "crack_detailing_warning": "",
    "Vuc_utilisation": None,  # Can be None
    "shear_longitudinal_tension_increment": 0.0,
    "shear_Ast_required_tension_envelope": 0.0,
    "shear_Ast_available_anchored_active": 0.0,
    "shear_Ast_available_anchored_web": 0.0,
    "shear_Ast_available_anchored_flange": 0.0,
    "shear_flange_bars_participating": False,
    "shear_longitudinal_detailing_ok": False,
    "flange_transverse_reo_present_top": False,
    "flange_transverse_reo_present_bottom": False,
    "flange_transverse_spacing_top": 0.0,
    "flange_transverse_spacing_bottom": 0.0,
    "flange_transverse_detailing_note": "",
    "active_tension_face": "",
    "active_tension_Ast_mm2": 0.0,
    "active_tension_width_mm": 0.0,
    "active_tension_flange_participating": False,
    "active_tension_warning": "",
    # Shear report outputs (PDF)
    "shear_steps": [],
    "shear_report": {},
    "shear_zone_results": None,
    "shear_design_status": None,
    "shear_design_error": None,
    "shear_auto_selected_lig_d_mm": None,
    "shear_auto_selected_legs": None,
    "shear_x": [],
    "shear_V": [],
    "shear_V_signed": [],
    "shear_M_uls_kNm": [],
    "shear_M_sls_kNm": [],
    "moment_x": [],
    "moment_values": [],
    "crack_bmd_cache_fingerprint": "",
    "bmd_support_positions_m": [],
    "bmd_support_types": [],
    "V_max": 0.0,
    "req_asv_s": [],
    "prov_asv_s": [],
    "shear_util_min": None,
    "shear_util_x": None,
    "shear_envelope_status": None,
    "support_type": None,
    "critical_shear_x": None,
    "critical_shear_V": None,
    "shear_spacing_governing": None,
    "shear_provided_input_spacing_mm": 0.0,
    "shear_input_spacing_mm": 0.0,
    "shear_sectional_check_spacing_mm": 0.0,
    "shear_required_spacing_mm": None,
    "shear_effective_spacing_mm": None,
    "shear_governing_spacing_source": "",
    "canonical_shear_status": None,
    "canonical_shear_ok": False,
    "canonical_shear_util": None,
    "canonical_shear_reason": "",
    "canonical_shear_source": "",
    "canonical_shear_effective_spacing_mm": None,
    "canonical_shear_required_spacing_mm": None,
    "canonical_shear_provided_spacing_mm": None,
    "canonical_shear_spacing_override_active": False,
    "canonical_shear_spacing_override_reason": "",
    "shear_governing_check_name": "",
    "shear_governing_demand_kN": None,
    "shear_governing_capacity_kN": None,
    "shear_governing_util": None,
    "shear_governing_status": None,
    "shear_governing_reason": "",
    "shear_governing_source": "",
    "shear_truth_status": None,
    "shear_truth_reason": "",
    "shear_truth_inconsistent_status_override": None,
    "shear_truth_util_governing": None,
    "shear_truth_web_util_governing": None,
    "shear_truth_util_source": "",
    "shear_truth_web_util_source": "",
    "shear_truth_governing_check_name": "",
    "shear_truth_governing_reason": "",
    "shear_truth_governing_source": "",
    "shear_util_governing": None,
    "final_shear_status_source": "",
    "final_shear_truth_resolved": False,
    "final_shear_truth_failure_reason": None,
    "published_result_spacing_mm": None,
    "published_result_spacing_meaning": "",
    "final_shear_spacing_reason": "",
    "final_shear_publication_path": "",
    "final_shear_truth_bundle_complete": False,
    "summary_shear_truth_consume_reason": "",
    "shear_truth_contradiction_detected": False,
    "shear_truth_contradiction_reason": "",
    "shear_debug_s_eff_mm": None,
    "shear_spacing_profile_min": 0.0,
    "shear_spacing_profile_max": 0.0,
    "shear_mid_spacing_mode": "",
    # Action result keys
    "actions_source": "",
    "Mu_star": 0.0,
    "Mu_star_kNm": 0.0,
    "Mu_star_kNm_signed": 0.0,
    "Vu_star": 0.0,
    # Load actions by module (derived wiring)
    "actions_bending": {},
    "actions_shear": {},
    "actions_crack": {},
    "actions_deflection": {},
    # SFD/BMD result keys
    "sfd_case": "",  # Current teaching case (string)
    "sfd_span_L_m": 0.0,  # Span length for SFD/deflection pages (m)
    "preview_M_uls_kNm": 0.0,
    "preview_V_uls_kN": 0.0,
    "preview_M_sls_kNm": 0.0,
    "preview_V_sls_kN": 0.0,
    "design_M_uls_kNm": 0.0,
    "design_M_uls_kNm_signed": 0.0,
    "design_V_uls_kN": 0.0,
    "design_M_sls_kNm": 0.0,
    "design_M_sls_kNm_signed": 0.0,
    "design_V_sls_kN": 0.0,
    "M_pos_max_uls_kNm": 0.0,
    "M_neg_min_uls_kNm": 0.0,
    "M_pos_max_sls_kNm": 0.0,
    "M_neg_min_sls_kNm": 0.0,
    "phi_Mu_pos_kNm": 0.0,
    "phi_Mu_neg_kNm": 0.0,
    "Mu_nom_pos_kNm": 0.0,
    "Mu_nom_neg_kNm": 0.0,
    "bending_util_pos": 0.0,
    "bending_util_neg": 0.0,
    "bending_status_pos": "",
    "bending_status_neg": "",
    "bending_has_sagging_case": False,
    "bending_has_hogging_case": False,
    "bending_has_positive_case": False,
    "bending_has_negative_case": False,
    "bending_governing_case": "",
    "bending_util_governing": 0.0,
    # Bending min requirements / neutral axis checks
    "Mx_min_req": 0.0,
    "As_min_req": 0.0,
    "k_u": 0.0,
    "k_u_lim": 0.0,
    # Duct totals (computed from n_ducts + duct_dia)
    "A_duct_total": 0.0,
    "sum_duct": 0.0,
    # SFD/BMD span length (computed result)
    "span_L_m": 0.0,
    # Deflection: computed effective design load
    "fd_ef_calc_kNm": 0.0,
    # Inputs-page assistant outputs
    "auto_design_steps": [],
    "auto_design_status": "",
})

# Explicit set of derived keys (for RULE 3 checks and debug guards)
# These are keys written ONLY inside recalc_derived_values()
DERIVED_KEYS = {
    "d", "do",
    "Ast_bot", "Ast_top",
    "nb_bot", "nb_top",
    "db_bot", "db_top",
    "s_bot", "s_top",
    "bot_rows_resolved", "top_rows_resolved",
    "bot_bar_coords", "top_bar_coords",
    "resolved_longitudinal_bars", "resolved_longitudinal_warnings",
    "Ast_top_web", "Ast_top_flange", "Ast_bottom_web", "Ast_bottom_flange",
    "total_bot_bars", "total_top_bars",
    "bot_entry", "top_entry",
    "t_creep", "age_at_loading", "stress_ratio", "t_shrink",
    "sustained_Mstar_kNm", "sustained_sigma_cs_mpa",
    "sustained_section_modulus_mm3", "sustained_compression_fibre",
    "Ec", "Eceff",
    # Layer 2 keys (may be auto-updated by recalc_derived_values)
    "nb_or_s_bot_2", "db_bot_2",
    "nb_or_s_top_2", "db_top_2",
}

# Keys that are logically required to be > 0 and must NOT be overwritten by stale widget zeros.
# IMPORTANT: Reinforcement COUNTS/SPACINGS CAN be 0 (e.g. top layer absent), so they must NOT live here.
# NOTE: Do NOT add reinforcement COUNT/OPTIONAL keys (e.g. nb_or_s_*) to stale-zero protection.
# 0 is a valid design state for these keys. Use ZERO_ALLOWED_SHARED_KEYS instead.
NONZERO_REQUIRED_SHARED_KEYS = {
    # Geometry (cannot be 0)
    "b", "D", "L",

    # Materials (cannot be 0)
    "fc", "fsy", "Ec", "Es",

    # Covers (cannot be 0)
    "cover_bot", "cover_top", "cover_side",
    "side_cover_bot", "side_cover_top",
    
    # Reinforcement spacings / layout inputs (must not be clobbered to 0)
    "s_bar_bot",
    "s_bar_top",
    "s_lig",
    "rowgap_bot",
    "rowgap_top",

    # Time inputs (must not be clobbered to 0)
    "t_creep",
    "t_shrink",
    "age_at_loading",
    
    # NOTE: Reinforcement keys (bar diameters, counts, legs) are NOT in this set
    # because 0 is a valid user intent (e.g., no layer, no shear links).
    # Use zero_allowed() to check if 0 is allowed for a given key.
}

# Keys where 0 is a legitimate user input (must NOT be treated as missing/stale/corrupt)
ZERO_ALLOWED_SHARED_KEYS = {
    "nb_or_s_bot_1", "nb_or_s_bot_2",
    "nb_or_s_top_1", "nb_or_s_top_2",
    # Explicit layout-mode count inputs (0 is valid = layer disabled)
    "bot1_count", "bot2_count",
    "top1_count", "top2_count",
    "bot_row_count", "top_row_count",
    "top_flange_left_count", "top_flange_right_count",
    "bot_flange_left_count", "bot_flange_right_count",
    # ULS design actions can be legitimately 0
    "uls_Mstar",
    "uls_Mstar_pos_manual",
    "uls_Mstar_neg_manual",
    "uls_Vstar",
    "uls_Nstar",
    "sls_Mstar",
    "sls_Mstar_pos_manual",
    "sls_Mstar_neg_manual",
    "sls_Vstar",
    "sls_Nstar",
    "Mu_star_manual",
    "Mu_star_pos_manual",
    "Mu_star_neg_manual",
    # Manual action proxies can also legitimately be 0
    "load_Mstar_proxy",
    "load_Mstar_pos_proxy",
    "load_Mstar_neg_proxy",
    "load_Vstar_proxy",
    "load_Nstar_proxy",
}

def zero_allowed(shared_key: str) -> bool:
    """Keys where 0 is a legitimate user value (e.g. no layer, no shear links)."""
    # Explicit allow-list
    if shared_key in ZERO_ALLOWED_SHARED_KEYS:
        return True

    # Point load distance can be 0 (load at support)
    if shared_key == "a_m":
        return True

    k = shared_key.lower()
    if k.startswith("design_point_"):
        return True

    # Reinforcement diameter / detailing keys can be 0 (meaning "not used")
    if k.startswith("db_") or k.startswith("lig_"):
        return True
    
    # Also include diameter patterns if they exist in naming
    if k.startswith("d_") or "diam" in k or k.endswith("_dia"):
        return True
    
    # Explicitly allow the three keys shown in tripwire (safety check)
    if shared_key in {"db_top_2", "db_bot_2", "lig_d"}:
        return True

    # Reinforcement patterns where 0 is legitimately "not used"
    # NOTE: DO NOT blanket-allow s_* (spacing keys like s_bar_bot must not become 0 by accident)
    if any(k.startswith(p) for p in ("nb_", "n_", "as_", "ast_", "top_", "bot_", "bottom_")):
        return True

    # Token-based allow. Exclude "spacing" to avoid allowing s_bar_bot/s_lig etc.
    if any(token in k for token in ("reo", "link", "leg", "layer", "stirrup", "bar", "dia", "diam")):
        return True

    # Actions: loads can be 0
    if k.endswith("_star") or k in ("p_star", "n_star", "tu_star", "mu_star", "vu_star"):
        return True

    # NOTE: rowgap_bot and rowgap_top are in NONZERO_REQUIRED_SHARED_KEYS, so they are NOT zero_allowed
    # (removed the rowgap_* check to prevent conflict)

    return False

# Aliases for backward compatibility
ALLOW_ZERO_SHARED_KEYS = ZERO_ALLOWED_SHARED_KEYS
ZERO_VALID_SHARED_KEYS = ZERO_ALLOWED_SHARED_KEYS


def validate_session_state_contract(context: str = "") -> None:
    """
    Debug-only validator for session-state contract.
    Raises fast with a clear message (prevents silent drift).
    Does not modify UI/diagrams.
    """
    import streamlit as st

    missing_shared = [k for k in SHARED_DEFAULTS.keys() if k not in st.session_state]
    if missing_shared:
        raise RuntimeError(
            f"[SessionStateContract] Missing shared keys ({context}): {missing_shared}"
        )

    # Ensure every widget key in TAB_KEYS exists (so sync can safely operate)
    missing_widget_keys = []
    for widget_key, shared_key in TAB_KEYS.items():
        if widget_key not in st.session_state:
            missing_widget_keys.append((widget_key, shared_key))

    if missing_widget_keys:
        # Keep message compact but actionable
        preview = missing_widget_keys[:10]
        raise RuntimeError(
            "[SessionStateContract] Missing widget keys ({ctx}). "
            "Example missing (widget_key, shared_key): {preview} "
            "(first 10 shown; ensure init_shared_session_state initializes TAB_KEYS widget keys)."
            .format(ctx=context, preview=preview)
        )

    # Optional: sanity check for None where defaults exist (None often causes cascades)
    none_shared = [k for k, v in SHARED_DEFAULTS.items() if st.session_state.get(k) is None and v is not None]
    if none_shared:
        raise RuntimeError(
            f"[SessionStateContract] Shared keys became None unexpectedly ({context}): {none_shared}"
        )

# =====================================================
# 2. MAPPING: widget keys → shared session_state keys
# =====================================================

TAB_KEYS = {
    # ----------------- INPUTS PAGE -----------------
    "inputs_b": "b",
    "inputs_D": "D",
    "inputs_L": "L",
    "inputs_sec_shape": "sec_shape",
    "inputs_bf": "bf",
    "inputs_tf": "tf",
    "inputs_bw": "bw",
    "inputs_tw": "tw",
    "inputs_bf_bot": "bf_bot",
    "inputs_tf_bot": "tf_bot",
    "inputs_detailed_mode_toggle": "inputs_detailed_mode",
    "inputs_auto_geometry_toggle": "auto_geometry",
    "inputs_auto_bottom_reo_toggle": "auto_bottom_reo",
    "inputs_auto_shear_toggle": "auto_shear",
    "inputs_fast_mode_show_3d_toggle": "fast_mode_show_3d",
    "inputs_design_optimisation_goal": "design_optimisation_goal",
    "inputs_optimisation_lock_geometry": "optimisation_lock_geometry",
    "inputs_optimisation_lock_width": "optimisation_lock_width",
    "inputs_optimisation_lock_depth": "optimisation_lock_depth",

    # ----------------- BENDING PAGE -----------------
    "bending_sec_shape": "sec_shape",
    "bending_b": "b",
    "bending_D": "D",
    "bending_L": "L",
    "bending_bf": "bf",
    "bending_tf": "tf",
    "bending_bw": "bw",
    "bending_tw": "tw",

    # ----------------- SHEAR PAGE -----------------
    "shear_sec_shape": "sec_shape",
    "shear_b": "b",
    "shear_D": "D",
    "shear_L": "L",
    "shear_bf": "bf",
    "shear_tf": "tf",
    "shear_bw": "bw",
    "shear_tw": "tw",

    # ----------------- CRACK PAGE -----------------
    "crack_sec_shape": "sec_shape",
    "crack_b": "b",
    "crack_D": "D",
    "crack_L": "L",
    "crack_bf": "bf",
    "crack_tf": "tf",
    "crack_bw": "bw",
    "crack_tw": "tw",

    # ----------------- DEFLECTION PAGE -----------------
    "deflection_sec_shape": "sec_shape",
    "deflection_b": "b",
    "deflection_D": "D",
    "deflection_L": "L",
    "deflection_bf": "bf",
    "deflection_tf": "tf",
    "deflection_bw": "bw",
    "deflection_tw": "tw",

    "inputs_fc": "fc",
    "inputs_fsy": "fsy",

    "inputs_Mu_star": "uls_Mstar",
    "inputs_Mu_star_pos_manual": "Mu_star_pos_manual",
    "inputs_Mu_star_neg_manual": "Mu_star_neg_manual",
    "inputs_Vu_star": "uls_Vstar",
    "inputs_Tu_star": "Tu_star",
    "inputs_P_star": "P_star",
    "inputs_N_star": "uls_Nstar",
    "inputs_load_Mstar_proxy": "load_Mstar_proxy",
    "inputs_load_Mstar_pos_proxy": "load_Mstar_pos_proxy",
    "inputs_load_Mstar_neg_proxy": "load_Mstar_neg_proxy",
    "inputs_load_Vstar_proxy": "load_Vstar_proxy",
    "inputs_load_Nstar_proxy": "load_Nstar_proxy",
    "inputs_loads_edit_mode": "loads_edit_mode",
    "inputs_loads_edit_toggle": "loads_edit_toggle",
    "design_loads_edit_toggle": "loads_edit_toggle",

    # ----------------- ACTIONS ALIASES (V* vs Vu*, T* vs Tu*) -----------------
    # Treat any page's alternate naming as the same underlying shared parameters.
    "inputs_V_star": "uls_Vstar",
    "shear_V_star": "uls_Vstar",
    "shear_Vu_star": "uls_Vstar",
    "actions_V_star": "uls_Vstar",
    "actions_Vu_star": "uls_Vstar",

    "inputs_T_star": "Tu_star",
    "shear_T_star": "Tu_star",
    "shear_Tu_star": "Tu_star",
    "actions_T_star": "Tu_star",
    "actions_Tu_star": "Tu_star",

    "shear_N_star": "N_star",
    "actions_N_star": "N_star",

    "shear_P_star": "P_star",
    "actions_P_star": "P_star",

    # strength reduction factors commonly edited near action inputs
    "shear_phi_shear": "phi_shear",
    "actions_phi_shear": "phi_shear",
    "shear_phi_torsion": "phi_torsion",
    "actions_phi_torsion": "phi_torsion",

    "inputs_rowgap_bot": "rowgap_bot",
    "inputs_rowgap_top": "rowgap_top",

    "inputs_cover_bot": "cover_bot",
    "inputs_cover_top": "cover_top",
    "inputs_side_cover_bot": "side_cover_bot",
    "inputs_side_cover_top": "side_cover_top",
    "inputs_cover_side": "cover_side",  # Geometry – side cover (now a proper shared param)

    # Reo: 2-layer bars/spacing entries
    "inputs_nb_or_s_bot_1": "nb_or_s_bot_1",
    "inputs_db_bot_1": "db_bot_1",
    "inputs_nb_or_s_bot_2": "nb_or_s_bot_2",
    "inputs_db_bot_2": "db_bot_2",
    "inputs_nb_or_s_top_1": "nb_or_s_top_1",
    "inputs_db_top_1": "db_top_1",
    "inputs_nb_or_s_top_2": "nb_or_s_top_2",
    "inputs_db_top_2": "db_top_2",
    
    # Bottom layer 1 (explicit layout mode)
    "inputs_bot1_layout_mode": "bot1_layout_mode",
    "inputs_bot1_count": "bot1_count",
    "inputs_bot1_spacing": "bot1_spacing",
    
    # Bottom layer 2 (explicit layout mode)
    "inputs_bot2_layout_mode": "bot2_layout_mode",
    "inputs_bot2_count": "bot2_count",
    "inputs_bot2_spacing": "bot2_spacing",
    
    # Top layer 1 (explicit layout mode)
    "inputs_top1_layout_mode": "top1_layout_mode",
    "inputs_top1_count": "top1_count",
    "inputs_top1_spacing": "top1_spacing",
    
    # Top layer 2 (explicit layout mode)
    "inputs_top2_layout_mode": "top2_layout_mode",
    "inputs_top2_count": "top2_count",
    "inputs_top2_spacing": "top2_spacing",

    # V2 row-model widgets.  These are the visible Inputs controls used by
    # the current renderer; keeping them in the same widget→shared map as the
    # legacy layer aliases makes Apply, navigation hydration, and callbacks
    # observe one canonical row transaction.
    "inputs_bot_row_count": "bot_row_count",
    "inputs_bot_row_1_mode": "bot_row_1_mode",
    "inputs_bot_row_1_bars": "bot_row_1_bars",
    "inputs_bot_row_1_spacing": "bot_row_1_spacing",
    "inputs_bot_row_1_dia": "bot_row_1_dia",
    "inputs_bot_row_2_mode": "bot_row_2_mode",
    "inputs_bot_row_2_bars": "bot_row_2_bars",
    "inputs_bot_row_2_spacing": "bot_row_2_spacing",
    "inputs_bot_row_2_dia": "bot_row_2_dia",
    "inputs_bot_row_3_mode": "bot_row_3_mode",
    "inputs_bot_row_3_bars": "bot_row_3_bars",
    "inputs_bot_row_3_spacing": "bot_row_3_spacing",
    "inputs_bot_row_3_dia": "bot_row_3_dia",
    "inputs_bot_row_4_mode": "bot_row_4_mode",
    "inputs_bot_row_4_bars": "bot_row_4_bars",
    "inputs_bot_row_4_spacing": "bot_row_4_spacing",
    "inputs_bot_row_4_dia": "bot_row_4_dia",
    "inputs_top_row_count": "top_row_count",
    "inputs_top_row_1_mode": "top_row_1_mode",
    "inputs_top_row_1_bars": "top_row_1_bars",
    "inputs_top_row_1_spacing": "top_row_1_spacing",
    "inputs_top_row_1_dia": "top_row_1_dia",
    "inputs_top_row_2_mode": "top_row_2_mode",
    "inputs_top_row_2_bars": "top_row_2_bars",
    "inputs_top_row_2_spacing": "top_row_2_spacing",
    "inputs_top_row_2_dia": "top_row_2_dia",
    "inputs_top_row_3_mode": "top_row_3_mode",
    "inputs_top_row_3_bars": "top_row_3_bars",
    "inputs_top_row_3_spacing": "top_row_3_spacing",
    "inputs_top_row_3_dia": "top_row_3_dia",
    "inputs_top_row_4_mode": "top_row_4_mode",
    "inputs_top_row_4_bars": "top_row_4_bars",
    "inputs_top_row_4_spacing": "top_row_4_spacing",
    "inputs_top_row_4_dia": "top_row_4_dia",
    "inputs_top_flange_reo_enabled": "top_flange_reo_enabled",
    "inputs_bot_flange_reo_enabled": "bot_flange_reo_enabled",
    "inputs_top_flange_mirror_lr": "top_flange_mirror_lr",
    "inputs_bot_flange_mirror_lr": "bot_flange_mirror_lr",
    "inputs_top_flange_left_count": "top_flange_left_count",
    "inputs_top_flange_left_dia": "top_flange_left_dia",
    "inputs_top_flange_left_rows": "top_flange_left_rows",
    "inputs_top_flange_left_row_spacing": "top_flange_left_row_spacing",
    "inputs_top_flange_left_clear_spacing_mode": "top_flange_left_clear_spacing_mode",
    "inputs_top_flange_right_count": "top_flange_right_count",
    "inputs_top_flange_right_dia": "top_flange_right_dia",
    "inputs_top_flange_right_rows": "top_flange_right_rows",
    "inputs_top_flange_right_row_spacing": "top_flange_right_row_spacing",
    "inputs_top_flange_right_clear_spacing_mode": "top_flange_right_clear_spacing_mode",
    "inputs_bot_flange_left_count": "bot_flange_left_count",
    "inputs_bot_flange_left_dia": "bot_flange_left_dia",
    "inputs_bot_flange_left_rows": "bot_flange_left_rows",
    "inputs_bot_flange_left_row_spacing": "bot_flange_left_row_spacing",
    "inputs_bot_flange_left_clear_spacing_mode": "bot_flange_left_clear_spacing_mode",
    "inputs_bot_flange_right_count": "bot_flange_right_count",
    "inputs_bot_flange_right_dia": "bot_flange_right_dia",
    "inputs_bot_flange_right_rows": "bot_flange_right_rows",
    "inputs_bot_flange_right_row_spacing": "bot_flange_right_row_spacing",
    "inputs_bot_flange_right_clear_spacing_mode": "bot_flange_right_clear_spacing_mode",
    "inputs_top_flange_transverse_enabled": "top_flange_transverse_enabled",
    "inputs_bot_flange_transverse_enabled": "bot_flange_transverse_enabled",
    "inputs_top_flange_transverse_dia": "top_flange_transverse_dia",
    "inputs_bot_flange_transverse_dia": "bot_flange_transverse_dia",
    "inputs_top_flange_transverse_spacing": "top_flange_transverse_spacing",
    "inputs_bot_flange_transverse_spacing": "bot_flange_transverse_spacing",
    "inputs_top_flange_transverse_legs": "top_flange_transverse_legs",
    "inputs_bot_flange_transverse_legs": "bot_flange_transverse_legs",
    **_longitudinal_row_tab_keys("inputs", "bot"),
    **_longitudinal_row_tab_keys("inputs", "top"),
    # Bending page widgets - map to same shared parameters
    "bending_sec_shape": "sec_shape",
    "bending_bf": "bf",
    "bending_tf": "tf",
    "bending_bw": "bw",
    "bending_tw": "tw",
    "bending_bf_bot": "bf_bot",
    "bending_tf_bot": "tf_bot",
    "bending_nb_or_s_bot_1": "nb_or_s_bot_1",
    "bending_db_bot_1": "db_bot_1",
    "bending_nb_or_s_bot_2": "nb_or_s_bot_2",
    "bending_db_bot_2": "db_bot_2",
    "bending_nb_or_s_top_1": "nb_or_s_top_1",
    "bending_db_top_1": "db_top_1",
    "bending_nb_or_s_top_2": "nb_or_s_top_2",
    "bending_db_top_2": "db_top_2",
    "bending_rowgap_bot": "rowgap_bot",
    "bending_rowgap_top": "rowgap_top",
    "bending_cover_bot": "cover_bot",
    "bending_cover_top": "cover_top",
    
    # Legacy entries (for backward compatibility during migration)
    "inputs_bot_entry": "bot_entry",
    "inputs_top_entry": "top_entry",
    "inputs_nb_bot": "nb_bot",
    "inputs_db_bot": "db_bot",
    "inputs_nb_top": "nb_top",
    "inputs_db_top": "db_top",
    # We still keep nb_bot, nb_top etc. as params used by other pages.
    # They will be *derived* from the 2-layer system in recalc_derived_values().

    "inputs_lig_d": "lig_d",
    "inputs_lig_legs": "lig_legs",
    "inputs_s_lig": "s_lig",

    # Ducts
    "inputs_n_ducts": "n_ducts",
    "inputs_duct_dia": "duct_dia",
    
    # Shear section parameters (Inputs)
    "inputs_d_g": "d_g",
    "inputs_k_d_option": "k_d_option",
    "inputs_k_v_method": "k_v_method",

    "inputs_exposure_class": "exposure_class",
    "inputs_env_option": "env_option",
    "inputs_s_bar_bot": "s_bar_bot",
    
    # Crack criteria (Inputs page)
    "inputs_wmax_char_limit": "wmax_char_limit",
    "inputs_crack_member_type": "crack_member_type",
    "inputs_crack_k1": "crack_k1",
    "inputs_crack_k2": "crack_k2",
    "inputs_actions_source": "actions_source",  # Source of design actions (manual vs teaching)
    "crack_method": "crack_control_method",
    "crack_wall_thickness": "crack_wall_thickness_mm",
    "crack_wall_base_zone": "crack_wall_in_base_zone",
    "crack_wall_area": "crack_wall_horizontal_area_per_face",
    "crack_wall_spacing": "crack_wall_vertical_spacing_mm",
    "crack_c766_restraint": "crack_c766_restraint_type",
    "crack_c766_t1": "crack_c766_t1_c",
    "crack_c766_t2": "crack_c766_t2_c",
    "crack_c766_alpha": "crack_c766_alpha_micro_per_c",
    "crack_c766_r1": "crack_c766_restraint_early",
    "crack_c766_r2": "crack_c766_restraint_medium",
    "crack_c766_r3": "crack_c766_restraint_long",
    "crack_c766_ectu": "crack_c766_tensile_capacity_micro",
    "crack_c766_epsca_early": "crack_c766_autogenous_early_micro",
    "crack_c766_epsca_long": "crack_c766_autogenous_long_micro",
    "crack_c766_rho_eff": "crack_c766_effective_reinforcement_ratio",
    "crack_c766_db": "crack_c766_bar_diameter_mm",
    "crack_c766_cover": "crack_c766_cover_mm",
    "crack_c766_alpha_e": "crack_c766_modular_ratio",
    "crack_c766_k": "crack_c766_non_uniform_k",
    "crack_c766_kc": "crack_c766_stress_distribution_kc",
    "crack_c766_fctk": "crack_c766_characteristic_tensile_mpa",
    "crack_c766_rho_total": "crack_c766_total_reinforcement_ratio",

    # Time-dependent inputs
    "inputs_t_creep": "t_creep",
    "inputs_age_at_loading": "age_at_loading",
    "inputs_t_shrink": "t_shrink",

    # ----------------- BENDING PAGE -----------------
    "bending_b": "b",
    "bending_D": "D",
    "bending_L": "L",

    "bending_fc": "fc",
    "bending_fsy": "fsy",
    # Legacy key plus new explicit bending phi widget
    "bending_phi_b": "phi_bend",
    "bending_phi_bend": "phi_bend",

    "bending_Mu_star": "uls_Mstar",
    "bending_Mu_star_pos_manual": "Mu_star_pos_manual",
    "bending_Mu_star_neg_manual": "Mu_star_neg_manual",
    "bending_P_star": "P_star",
    "bending_N_star": "N_star",

    "bending_nb_bot": "nb_bot",
    "bending_db_bot": "db_bot",
    "bending_nb_top": "nb_top",
    "bending_db_top": "db_top",
    "bending_rowgap_bot": "rowgap_bot",
    "bending_rowgap_top": "rowgap_top",

    "bending_cover_bot": "cover_bot",
    "bending_cover_top": "cover_top",
    "bending_side_cover_bot": "side_cover_bot",
    "bending_side_cover_top": "side_cover_top",

    # --- Bending page: explicit reo mode/count/spacing widgets ---
    "bending_bot1_layout_mode": "bot1_layout_mode",
    "bending_bot1_count": "bot1_count",
    "bending_bot1_spacing": "bot1_spacing",

    "bending_bot2_layout_mode": "bot2_layout_mode",
    "bending_bot2_count": "bot2_count",
    "bending_bot2_spacing": "bot2_spacing",

    "bending_top1_layout_mode": "top1_layout_mode",
    "bending_top1_count": "top1_count",
    "bending_top1_spacing": "top1_spacing",

    "bending_top2_layout_mode": "top2_layout_mode",
    "bending_top2_count": "top2_count",
    "bending_top2_spacing": "top2_spacing",
    "bending_top_flange_reo_enabled": "top_flange_reo_enabled",
    "bending_bot_flange_reo_enabled": "bot_flange_reo_enabled",
    "bending_top_flange_mirror_lr": "top_flange_mirror_lr",
    "bending_bot_flange_mirror_lr": "bot_flange_mirror_lr",
    "bending_top_flange_left_count": "top_flange_left_count",
    "bending_top_flange_left_dia": "top_flange_left_dia",
    "bending_top_flange_left_rows": "top_flange_left_rows",
    "bending_top_flange_left_row_spacing": "top_flange_left_row_spacing",
    "bending_top_flange_right_count": "top_flange_right_count",
    "bending_top_flange_right_dia": "top_flange_right_dia",
    "bending_top_flange_right_rows": "top_flange_right_rows",
    "bending_top_flange_right_row_spacing": "top_flange_right_row_spacing",
    "bending_bot_flange_left_count": "bot_flange_left_count",
    "bending_bot_flange_left_dia": "bot_flange_left_dia",
    "bending_bot_flange_left_rows": "bot_flange_left_rows",
    "bending_bot_flange_left_row_spacing": "bot_flange_left_row_spacing",
    "bending_bot_flange_right_count": "bot_flange_right_count",
    "bending_bot_flange_right_dia": "bot_flange_right_dia",
    "bending_bot_flange_right_rows": "bot_flange_right_rows",
    "bending_bot_flange_right_row_spacing": "bot_flange_right_row_spacing",
    "bending_top_flange_transverse_enabled": "top_flange_transverse_enabled",
    "bending_bot_flange_transverse_enabled": "bot_flange_transverse_enabled",
    "bending_top_flange_transverse_dia": "top_flange_transverse_dia",
    "bending_bot_flange_transverse_dia": "bot_flange_transverse_dia",
    "bending_top_flange_transverse_spacing": "top_flange_transverse_spacing",
    "bending_bot_flange_transverse_spacing": "bot_flange_transverse_spacing",
    "bending_top_flange_transverse_legs": "top_flange_transverse_legs",
    "bending_bot_flange_transverse_legs": "bot_flange_transverse_legs",
    **_longitudinal_row_tab_keys("bending", "bot"),
    **_longitudinal_row_tab_keys("bending", "top"),

    # ----------------- SHEAR PAGE -----------------
    "shear_b": "b",
    "shear_D": "D",
    "shear_L": "L",

    "shear_fc": "fc",
    "shear_fsy": "fsy",

    "shear_Vu_star": "uls_Vstar",
    "shear_Tu_star": "Tu_star",
    "shear_P_star": "P_star",
    "shear_N_star": "N_star",
    "shear_defl_support_type": "defl_support_type",

    "shear_phi_v": "phi_shear",
    "shear_phi_shear": "phi_shear",
    "shear_phi_t": "phi_torsion",

    "shear_nb_bot": "nb_bot",
    "shear_db_bot": "db_bot",
    "shear_nb_top": "nb_top",
    "shear_db_top": "db_top",

    "shear_lig_d": "lig_d",
    "shear_lig_legs": "lig_legs",
    "shear_s_lig": "s_lig",
    "shear_auto_design_toggle": "shear_auto_design",
    "shear_auto_design_mode_toggle": "shear_auto_design",
    "shear_optimize_reinforcement_toggle": "shear_optimize_reinforcement",

    # Shear section parameters
    "shear_d_g": "d_g",
    "shear_n_ducts": "n_ducts",
    "shear_duct_dia": "duct_dia",
    "shear_k_d_option": "k_d_option",
    "shear_k_v_method": "k_v_method",

    "shear_cover_bot": "cover_bot",
    "shear_cover_top": "cover_top",
    "shear_top_flange_reo_enabled": "top_flange_reo_enabled",
    "shear_bot_flange_reo_enabled": "bot_flange_reo_enabled",
    "shear_top_flange_transverse_enabled": "top_flange_transverse_enabled",
    "shear_bot_flange_transverse_enabled": "bot_flange_transverse_enabled",
    "shear_top_flange_transverse_dia": "top_flange_transverse_dia",
    "shear_bot_flange_transverse_dia": "bot_flange_transverse_dia",
    "shear_top_flange_transverse_spacing": "top_flange_transverse_spacing",
    "shear_bot_flange_transverse_spacing": "bot_flange_transverse_spacing",
    "shear_top_flange_transverse_legs": "top_flange_transverse_legs",
    "shear_bot_flange_transverse_legs": "bot_flange_transverse_legs",
    **_longitudinal_row_tab_keys("shear", "bot"),
    **_longitudinal_row_tab_keys("shear", "top"),

    # ----------------- TORSION / SKETCH PAGE -----------------
    "torsion_theta_deg": "crack_theta_deg",

    # ----------------- CRACK CONTROL PAGE -----------------
    "crack_b": "b",
    "crack_D": "D",
    "crack_L": "L",

    "crack_fc": "fc",
    "crack_fsy": "fsy",

    "crack_Mu_star": "uls_Mstar",

    "crack_nb_bot": "nb_bot",
    "crack_db_bot": "db_bot",
    "crack_nb_top": "nb_top",
    "crack_db_top": "db_top",

    "crack_exposure_class": "exposure_class",
    "crack_s_bar_bot": "s_bar_bot",
    
    # Crack criteria (Crack page)
    "crack_wmax": "wmax_char_limit",
    "crack_member_type": "crack_member_type",
    "crack_k1": "crack_k1",
    "crack_k2": "crack_k2",
    "crack_diagram_view": "crack_diagram_panel",

    "crack_cover_bot": "cover_bot",
    "crack_cover_top": "cover_top",
    
    # Crack page 2-layer bottom reinforcement (standardized to crack_ prefix)
    "crack_nb_or_s_bot_1": "nb_or_s_bot_1",
    "crack_db_bot_1": "db_bot_1",
    "crack_nb_or_s_bot_2": "nb_or_s_bot_2",
    "crack_db_bot_2": "db_bot_2",
    "crack_rowgap_bot": "rowgap_bot",
    
    # Crack page: Bottom longitudinal reinforcement (explicit mode/count/spacing)
    "crack_bot1_layout_mode": "bot1_layout_mode",
    "crack_bot1_count": "bot1_count",
    "crack_bot1_spacing": "bot1_spacing",
    "crack_bot2_layout_mode": "bot2_layout_mode",
    "crack_bot2_count": "bot2_count",
    "crack_bot2_spacing": "bot2_spacing",
    "crack_top_flange_reo_enabled": "top_flange_reo_enabled",
    "crack_bot_flange_reo_enabled": "bot_flange_reo_enabled",
    "crack_top_flange_transverse_enabled": "top_flange_transverse_enabled",
    "crack_bot_flange_transverse_enabled": "bot_flange_transverse_enabled",
    "crack_top_flange_transverse_dia": "top_flange_transverse_dia",
    "crack_bot_flange_transverse_dia": "bot_flange_transverse_dia",
    "crack_top_flange_transverse_spacing": "top_flange_transverse_spacing",
    "crack_bot_flange_transverse_spacing": "bot_flange_transverse_spacing",
    "crack_top_flange_transverse_legs": "top_flange_transverse_legs",
    "crack_bot_flange_transverse_legs": "bot_flange_transverse_legs",
    **_longitudinal_row_tab_keys("crack", "bot"),
    **_longitudinal_row_tab_keys("crack", "top"),
    
    # ----------------- SFD/BMD PAGE (Unified loading) -----------------
    "load_L": "span_L_m",
    "load_g_udl": "g_udl_kNm_per_m",
    "load_q_udl": "q_udl_kNm_per_m",
    "load_psi_udl": "psi_udl",
    "load_case": "sfd_case",
    "sfd_beam_system_mode": "design_beam_system_mode",
    "sfd_support_condition": "design_support_condition",
    "load_G_point": "G_point_kN",
    "load_Q_point": "Q_point_kN",
    "load_psi_point": "psi_point",
    "load_a_point": "a_m",
    "load_G_point_1": "design_point_G_1",
    "load_G_point_2": "design_point_G_2",
    "load_G_point_3": "design_point_G_3",
    "load_G_point_4": "design_point_G_4",
    "load_G_point_5": "design_point_G_5",
    "load_G_point_6": "design_point_G_6",
    "load_Q_point_1": "design_point_Q_1",
    "load_Q_point_2": "design_point_Q_2",
    "load_Q_point_3": "design_point_Q_3",
    "load_Q_point_4": "design_point_Q_4",
    "load_Q_point_5": "design_point_Q_5",
    "load_Q_point_6": "design_point_Q_6",
    "load_x_point_1": "design_point_x_1",
    "load_x_point_2": "design_point_x_2",
    "load_x_point_3": "design_point_x_3",
    "load_x_point_4": "design_point_x_4",
    "load_x_point_5": "design_point_x_5",
    "load_x_point_6": "design_point_x_6",
    # SFD/BMD widget keys used on the Design page
    "sfd_L_m": "span_L_m",
    "sfd_a_udl": "a_udl_m",
    "sfd_a_cant": "a_cant_m",
    "sfd_a_overhang": "a_overhang_m",
    "sfd_support_type_1": "design_support_type_1",
    "sfd_support_type_2": "design_support_type_2",
    "sfd_support_type_3": "design_support_type_3",
    "sfd_support_type_4": "design_support_type_4",
    "sfd_support_type_5": "design_support_type_5",
    "sfd_support_type_6": "design_support_type_6",
    "sfd_span_count": "design_span_count",
    "sfd_span_len_1": "design_span_len_1",
    "sfd_span_len_2": "design_span_len_2",
    "sfd_span_len_3": "design_span_len_3",
    "sfd_span_len_4": "design_span_len_4",
    "sfd_span_len_5": "design_span_len_5",
    "sfd_ms_point_count": "design_ms_point_count",
    "sfd_ms_udl_count": "design_ms_udl_count",
    "sfd_point_load_count": "sfd_point_load_count",
    "load_ms_G_1": "design_ms_G_1",
    "load_ms_G_2": "design_ms_G_2",
    "load_ms_G_3": "design_ms_G_3",
    "load_ms_G_4": "design_ms_G_4",
    "load_ms_G_5": "design_ms_G_5",
    "load_ms_G_6": "design_ms_G_6",
    "load_ms_G_7": "design_ms_G_7",
    "load_ms_G_8": "design_ms_G_8",
    "load_ms_Q_1": "design_ms_Q_1",
    "load_ms_Q_2": "design_ms_Q_2",
    "load_ms_Q_3": "design_ms_Q_3",
    "load_ms_Q_4": "design_ms_Q_4",
    "load_ms_Q_5": "design_ms_Q_5",
    "load_ms_Q_6": "design_ms_Q_6",
    "load_ms_Q_7": "design_ms_Q_7",
    "load_ms_Q_8": "design_ms_Q_8",
    "load_ms_x_1": "design_ms_x_1",
    "load_ms_x_2": "design_ms_x_2",
    "load_ms_x_3": "design_ms_x_3",
    "load_ms_x_4": "design_ms_x_4",
    "load_ms_x_5": "design_ms_x_5",
    "load_ms_x_6": "design_ms_x_6",
    "load_ms_x_7": "design_ms_x_7",
    "load_ms_x_8": "design_ms_x_8",
    "load_ms_g_1": "design_ms_g_1",
    "load_ms_g_2": "design_ms_g_2",
    "load_ms_g_3": "design_ms_g_3",
    "load_ms_g_4": "design_ms_g_4",
    "load_ms_g_5": "design_ms_g_5",
    "load_ms_g_6": "design_ms_g_6",
    "load_ms_g_7": "design_ms_g_7",
    "load_ms_g_8": "design_ms_g_8",
    "load_ms_q_1": "design_ms_q_1",
    "load_ms_q_2": "design_ms_q_2",
    "load_ms_q_3": "design_ms_q_3",
    "load_ms_q_4": "design_ms_q_4",
    "load_ms_q_5": "design_ms_q_5",
    "load_ms_q_6": "design_ms_q_6",
    "load_ms_q_7": "design_ms_q_7",
    "load_ms_q_8": "design_ms_q_8",
    "load_ms_x0_1": "design_ms_x0_1",
    "load_ms_x0_2": "design_ms_x0_2",
    "load_ms_x0_3": "design_ms_x0_3",
    "load_ms_x0_4": "design_ms_x0_4",
    "load_ms_x0_5": "design_ms_x0_5",
    "load_ms_x0_6": "design_ms_x0_6",
    "load_ms_x0_7": "design_ms_x0_7",
    "load_ms_x0_8": "design_ms_x0_8",
    "load_ms_x1_1": "design_ms_x1_1",
    "load_ms_x1_2": "design_ms_x1_2",
    "load_ms_x1_3": "design_ms_x1_3",
    "load_ms_x1_4": "design_ms_x1_4",
    "load_ms_x1_5": "design_ms_x1_5",
    "load_ms_x1_6": "design_ms_x1_6",
    "load_ms_x1_7": "design_ms_x1_7",
    "load_ms_x1_8": "design_ms_x1_8",
    "design_actions_source_selector": "design_actions_source",
    "design_section_x_slider": "section_cursor_x_m",
    "design_section_x_input": "section_cursor_x_m",
    
    # ----------------- DEFLECTION PAGE -----------------
    "defl_beff": "defl_beff",
    "defl_b": "b",
    "defl_D": "D",
    "defl_L": "L",
    "defl_support_type": "defl_support_type",
    "defl_defl_support_type": "defl_support_type",
    "defl_limit_ratio": "defl_limit_ratio",
    "defl_defl_limit_ratio": "defl_limit_ratio",
    "defl_Fdef": "defl_Fdef",
    "defl_use_simplified_ief": "defl_use_simplified_ief",
    "defl_Ief_user": "defl_Ief_user",
    
    # Deflection page uses the same concrete props as global materials
    "defl_fc": "fc",

    # Deflection page reinforcement (linked to shared layer-1 inputs)
    "defl_bot1_layout_mode": "bot1_layout_mode",
    "defl_bot1_count": "bot1_count",
    "defl_bot1_spacing": "bot1_spacing",
    "defl_db_bot_1": "db_bot_1",
    "defl_bot2_layout_mode": "bot2_layout_mode",
    "defl_bot2_count": "bot2_count",
    "defl_bot2_spacing": "bot2_spacing",
    "defl_db_bot_2": "db_bot_2",
    "defl_top1_layout_mode": "top1_layout_mode",
    "defl_top1_count": "top1_count",
    "defl_top1_spacing": "top1_spacing",
    "defl_db_top_1": "db_top_1",
    "defl_top2_layout_mode": "top2_layout_mode",
    "defl_top2_count": "top2_count",
    "defl_top2_spacing": "top2_spacing",
    "defl_db_top_2": "db_top_2",
    "defl_rowgap_bot": "rowgap_bot",
    "defl_rowgap_top": "rowgap_top",
    "defl_top_flange_reo_enabled": "top_flange_reo_enabled",
    "defl_bot_flange_reo_enabled": "bot_flange_reo_enabled",
    "defl_top_flange_transverse_enabled": "top_flange_transverse_enabled",
    "defl_bot_flange_transverse_enabled": "bot_flange_transverse_enabled",
    "defl_top_flange_transverse_dia": "top_flange_transverse_dia",
    "defl_bot_flange_transverse_dia": "bot_flange_transverse_dia",
    "defl_top_flange_transverse_spacing": "top_flange_transverse_spacing",
    "defl_bot_flange_transverse_spacing": "bot_flange_transverse_spacing",
    "defl_top_flange_transverse_legs": "top_flange_transverse_legs",
    "defl_bot_flange_transverse_legs": "bot_flange_transverse_legs",
    **_longitudinal_row_tab_keys("defl", "bot"),
    **_longitudinal_row_tab_keys("defl", "top"),
    
    # ----------------- INPUTS PAGE: Serviceability + Shrinkage -----------------
    "inputs_defl_support_type": "defl_support_type",
    "inputs_defl_limit_ratio": "defl_limit_ratio",
    "inputs_defl_Fdef": "defl_Fdef",
    "inputs_member_faces_exposed": "member_faces_exposed",
    "inputs_shrinkage_env": "shrinkage_env",
    
    # ----------------- SHRINKAGE PAGE -----------------
    "sh_b": "b",
    "sh_D": "D",
    "sh_faces": "member_faces_exposed",
    "sh_env": "shrinkage_env",
    "sh_t_days": "t_shrink",
    "sh_method": "shrinkage_method",
    "sh_rh": "shrinkage_relative_humidity_percent",
    "sh_cement_class": "shrinkage_cement_class",
    "sh_drying_start": "shrinkage_drying_start_age_days",
    
    # ----------------- CREEP PAGE -----------------
    "cr_b": "b",
    "cr_D": "D",
    "cr_faces": "member_faces_exposed",
    "cr_env": "env_option",
    "cr_t_creep": "t_creep",
    "cr_tau": "age_at_loading",
}

# Page-level TAB_KEYS mapping (derived from TAB_KEYS; does NOT change the contract)
TAB_KEYS_BY_PAGE = {
    "creep": {sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("cr_")},
    "shrinkage": {sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("sh_")},
    "deflection": {sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("defl_")},
    "design": {
        **{sk: wk for wk, sk in TAB_KEYS.items() if wk.startswith("load_") or wk.startswith("sfd_") or wk.startswith("design_")},
    },
}

# =========================
# V2: Canonical key resolver
# =========================

CANONICAL_PREFIX = "inputs_"

# Build: shared_key -> canonical widget key (prefer inputs_*)
_SHARED_TO_CANONICAL_WIDGET: dict[str, str] = {}
for wk, sk in TAB_KEYS.items():
    if wk.startswith(CANONICAL_PREFIX):
        _SHARED_TO_CANONICAL_WIDGET.setdefault(sk, wk)

# Fallback: if a shared key has no inputs_* mapping, pick the first mapping (should be rare)
for wk, sk in TAB_KEYS.items():
    _SHARED_TO_CANONICAL_WIDGET.setdefault(sk, wk)

# Build alias map: any non-canonical widget key that targets a shared key becomes an alias to the canonical key
WIDGET_KEY_ALIASES: dict[str, str] = {}
for wk, sk in TAB_KEYS.items():
    canonical = _SHARED_TO_CANONICAL_WIDGET.get(sk, wk)
    if wk != canonical:
        WIDGET_KEY_ALIASES[wk] = canonical


def resolve_widget_key(widget_key: str) -> str:
    # Keep widget keys distinct across pages (contract rule).
    return widget_key


def get_widget_key_for_shared(shared_key: str, prefix: str = "inputs_") -> str | None:
    """
    Find the widget key that maps to a given shared key (with optional prefix filter).
    Returns None if not found.
    """
    for wk, sk in TAB_KEYS.items():
        if sk == shared_key and wk.startswith(prefix):
            return wk
    return None

# ============================================
# 2b. CONTRACT VALIDATION
# ============================================

def _validate_contract():
    """
    Internal sanity checks to enforce the rules:
    - Every TAB_KEYS target must exist in SHARED_DEFAULTS.
    - No duplicate widget keys.
    - All RESULT_KEYS exist in SHARED_DEFAULTS.
    """
    # Shared keys
    shared_keys = set(SHARED_DEFAULTS.keys())

    # 1) Every widget→shared mapping must point to a defined shared key
    for widget_key, shared_key in TAB_KEYS.items():
        if shared_key not in shared_keys:
            raise KeyError(
                f"[SESSION STATE CONTRACT] TAB_KEYS['{widget_key}'] "
                f"points to unknown shared key '{shared_key}'.\n"
                f"Add it to SHARED_DEFAULTS or fix the mapping."
            )

    # 2) No duplicate widget keys (dict already enforces this,
    #    but we keep this here as a comment-style guard)
    if len(TAB_KEYS) != len(set(TAB_KEYS.keys())):
        raise RuntimeError(
            "[SESSION STATE CONTRACT] Duplicate widget keys detected in TAB_KEYS."
        )

    # 3) RESULT_KEYS are derived outputs and do NOT need to exist in SHARED_DEFAULTS.
    # Validate they have defaults in RESULT_DEFAULTS instead.
    missing_result_defaults = set(RESULT_KEYS) - set(RESULT_DEFAULTS.keys())
    if missing_result_defaults:
        raise KeyError(
            f"[SESSION STATE CONTRACT] RESULT_KEYS missing defaults in RESULT_DEFAULTS: {missing_result_defaults}"
        )

# Run this once at import
_validate_contract()

# ============================================
# 3. INITIALISATION + DERIVED UPDATES
# ============================================

@st.cache_resource
def _persistent_store():
    """
    Server-process persistent dict, survives reruns and accidental session_state wipes.
    Keyed by a stable client id we keep in query params.
    """
    return {}


def get_client_id() -> str:
    """
    Stable per-browser identifier stored in query params (not session_state).
    Prevents losing the key when session_state wipes.
    """
    import uuid
    cid = st.query_params.get("cid")
    if isinstance(cid, list):
        cid = cid[0] if cid else None
    if not cid:
        cid = str(uuid.uuid4())
        st.query_params["cid"] = cid
    return cid


# File-based snapshot (survives server restarts).
# Runtime is source-only: mutable application data belongs in the canonical
# Outputs sibling (or an explicitly configured location), never beside code.
LEGACY_SNAPSHOT_PATH = Path(__file__).resolve().with_name("shared_snapshot.json")


def _resolve_snapshot_path() -> Path:
    configured_path = os.environ.get("BEAM_SHARED_SNAPSHOT_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    configured_outputs = os.environ.get("BEAM_OUTPUTS_DIR")
    if configured_outputs:
        return Path(configured_outputs).expanduser().resolve() / "shared_snapshot.json"

    runtime_root = Path(__file__).resolve().parent
    canonical_outputs = runtime_root.parent / "complete-app - Outputs"
    if canonical_outputs.is_dir():
        return canonical_outputs / "shared_snapshot.json"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "BeamApp" / "shared_snapshot.json"
    return Path.cwd() / ".beam_app_data" / "shared_snapshot.json"


SNAPSHOT_PATH = _resolve_snapshot_path()


def _snapshot_path_for_read() -> Path:
    """Prefer source-external storage, with read-only legacy compatibility."""
    if SNAPSHOT_PATH.is_file():
        return SNAPSHOT_PATH
    if LEGACY_SNAPSHOT_PATH.is_file():
        return LEGACY_SNAPSHOT_PATH
    return SNAPSHOT_PATH


def _read_snapshot_file_raw() -> dict:
    snapshot_path = _snapshot_path_for_read()
    if not snapshot_path.is_file():
        return {}
    try:
        with snapshot_path.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def load_workspace_origin_from_snapshot_file() -> str | None:
    """Return persisted workspace origin from snapshot file (v2 only)."""
    raw = _read_snapshot_file_raw()
    if not isinstance(raw, dict):
        return None
    if raw.get("schema") == SNAPSHOT_FILE_SCHEMA_V2:
        o = raw.get("workspace_origin")
        if o in (
            WORKSPACE_ORIGIN_NEW_FILE,
            WORKSPACE_ORIGIN_LOADED_FILE,
            WORKSPACE_ORIGIN_RESUMED_SESSION,
        ):
            return str(o)
    return None


def load_workspace_identity_from_snapshot_file() -> str | None:
    """Return persisted workspace identity string from snapshot file (v2 only)."""
    raw = _read_snapshot_file_raw()
    if not isinstance(raw, dict) or raw.get("schema") != SNAPSHOT_FILE_SCHEMA_V2:
        return None
    w = raw.get("workspace_identity")
    if isinstance(w, str) and w.strip():
        return w.strip()
    return None


def _read_snapshot_workspace_meta_from_file() -> tuple[str | None, str | None]:
    """v2 snapshot only: (workspace_origin, workspace_identity). Legacy returns (None, None)."""
    raw = _read_snapshot_file_raw()
    if not isinstance(raw, dict) or raw.get("schema") != SNAPSHOT_FILE_SCHEMA_V2:
        return (None, None)
    o = raw.get("workspace_origin")
    oo = (
        str(o)
        if o
        in (
            WORKSPACE_ORIGIN_NEW_FILE,
            WORKSPACE_ORIGIN_LOADED_FILE,
            WORKSPACE_ORIGIN_RESUMED_SESSION,
        )
        else None
    )
    w = raw.get("workspace_identity")
    wid = w.strip() if isinstance(w, str) and w.strip() else None
    return (oo, wid)


def _resumed_session_restore_identity_compatible(snapshot_identity: str) -> bool:
    """
    Cold resume: snapshot id rs:<cid>:<beam> matches this browser and session has not
    pinned a different beam yet (beam init runs after init_shared_session_state).
    """
    if get_workspace_origin() != WORKSPACE_ORIGIN_RESUMED_SESSION:
        return False
    parts = snapshot_identity.split(":", 2)
    if len(parts) != 3 or parts[0] != "rs":
        return False
    scid, sbid = parts[1], parts[2]
    if scid != get_client_id():
        return False
    if sbid in ("", "none"):
        return False
    cur_bid = st.session_state.get("active_beam_id")
    if cur_bid is not None and str(cur_bid) != sbid:
        return False
    return True


def workspace_snapshot_restore_allowed(
    *,
    snapshot_origin: str | None,
    snapshot_identity: str | None,
) -> bool:
    """
    Whether copying snapshot/shared into session is allowed for the current workspace.
    Does not adopt unrelated file/mem state over new_file, loaded_file, or mismatched resume.

    resumed_session: requires v2 snapshot with both workspace_origin=resumed_session and a
    non-empty workspace_identity (legacy flat / unlabeled v2 is skipped; next persist rewrites
    the file with full v2 metadata).
    """
    cur = get_workspace_origin()
    if cur == WORKSPACE_ORIGIN_NEW_FILE:
        return False
    if cur == WORKSPACE_ORIGIN_LOADED_FILE:
        if snapshot_origin != WORKSPACE_ORIGIN_LOADED_FILE:
            return False
        if not snapshot_identity:
            return False
        return snapshot_identity == get_workspace_identity_for_persist()
    # resumed_session (default origin): no unlabeled / legacy restore
    if snapshot_origin != WORKSPACE_ORIGIN_RESUMED_SESSION:
        return False
    if not snapshot_identity:
        return False
    if snapshot_identity == get_workspace_identity_for_persist():
        return True
    return _resumed_session_restore_identity_compatible(snapshot_identity)


def load_shared_snapshot() -> dict:
    """Load shared inputs snapshot from JSON file (legacy flat or schema v2)."""
    raw = _read_snapshot_file_raw()
    if not isinstance(raw, dict):
        return {}
    if raw.get("schema") == SNAPSHOT_FILE_SCHEMA_V2 and isinstance(raw.get("shared"), dict):
        return migrate_longitudinal_reo_snapshot(raw["shared"])
    # Legacy: entire JSON object is the shared map
    if "schema" not in raw and "shared" not in raw:
        return migrate_longitudinal_reo_snapshot(raw)
    return {}


def save_shared_snapshot(
    shared: dict,
    *,
    workspace_origin: str | None = None,
    workspace_identity: str | None = None,
) -> None:
    """
    Save shared inputs + workspace origin to JSON file.
    v2 format prevents stale snapshot merges from hiding which file mode is active.
    """
    origin = workspace_origin or st.session_state.get(WORKSPACE_ORIGIN_KEY) or WORKSPACE_ORIGIN_RESUMED_SESSION
    if origin not in (
        WORKSPACE_ORIGIN_NEW_FILE,
        WORKSPACE_ORIGIN_LOADED_FILE,
        WORKSPACE_ORIGIN_RESUMED_SESSION,
    ):
        origin = WORKSPACE_ORIGIN_RESUMED_SESSION
    identity = workspace_identity if workspace_identity is not None else get_workspace_identity_for_persist()
    payload = {
        "schema": SNAPSHOT_FILE_SCHEMA_V2,
        "workspace_origin": origin,
        "workspace_identity": identity,
        "shared": shared,
    }
    try:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = SNAPSHOT_PATH.with_suffix(SNAPSHOT_PATH.suffix + ".tmp")
        with temporary_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(temporary_path, SNAPSHOT_PATH)
    except Exception:
        pass


def get_workspace_origin() -> str:
    """Current explicit workspace origin; defaults to resumed_session."""
    v = st.session_state.get(WORKSPACE_ORIGIN_KEY)
    if v in (
        WORKSPACE_ORIGIN_NEW_FILE,
        WORKSPACE_ORIGIN_LOADED_FILE,
        WORKSPACE_ORIGIN_RESUMED_SESSION,
    ):
        return str(v)
    return WORKSPACE_ORIGIN_RESUMED_SESSION


def get_workspace_identity_for_persist() -> str:
    """
    Stable string written to shared_snapshot.json for same-workspace checks.
    new_file: opaque uuid in session (set on reset / new beam).
    loaded_file: project id + active beam id.
    resumed_session: client id + active beam id (no cross-beam / cross-tab revive via persist merge).
    """
    origin = get_workspace_origin()
    bid = str(st.session_state.get("active_beam_id") or "none")
    if origin == WORKSPACE_ORIGIN_NEW_FILE:
        wid = st.session_state.get(WORKSPACE_IDENTITY_KEY)
        if not wid:
            wid = uuid.uuid4().hex
            st.session_state[WORKSPACE_IDENTITY_KEY] = wid
        return str(wid)
    if origin == WORKSPACE_ORIGIN_LOADED_FILE:
        pid = str(st.session_state.get("active_project_id") or "none")
        return f"ld:{pid}:{bid}"
    cid = get_client_id()
    return f"rs:{cid}:{bid}"


def snapshot_manual_action_prev_merge_allowed() -> bool:
    """
    Stale-snapshot merge (revive nonzero actions when shared reads as zero) is only
    allowed for a continued session workspace — never for new_file or loaded_file.
    """
    return get_workspace_origin() == WORKSPACE_ORIGIN_RESUMED_SESSION


def snapshot_manual_action_prev_merge_identity_aligned() -> bool:
    """Persist-time stale-action merge only when the on-disk snapshot is for this same workspace."""
    if not snapshot_manual_action_prev_merge_allowed():
        return False
    prev_id = load_workspace_identity_from_snapshot_file()
    if not prev_id:
        return False
    return prev_id == get_workspace_identity_for_persist()


# --- Snapshot/load guards ---
DISABLE_SNAPSHOT_RESTORE_KEY = "_disable_snapshot_restore"


def clear_cached_and_widget_restore_keys() -> None:
    """
    Delete keys that commonly override freshly loaded project payloads.
    We intentionally do NOT delete canonical shared keys here.
    """
    import streamlit as st

    to_delete = []
    for k in list(st.session_state.keys()):
        if k.startswith("inputs_"):
            to_delete.append(k)
        elif k.startswith("beam_manager_"):
            to_delete.append(k)
        elif k.startswith("_cached_"):
            to_delete.append(k)
        elif k in ("_snapshot_restore_complete",):
            to_delete.append(k)

    for k in to_delete:
        try:
            del st.session_state[k]
        except Exception:
            pass


def persist_state_snapshot(*, reset_manual_action_touch_latch: bool = False):
    """
    Persist ALL shared keys + ALL inputs_* widget keys + caches used for restores.
    Uses file-based snapshot (survives server restarts).

    On the final persist each Streamlit run, pass ``reset_manual_action_touch_latch=True``
    so the next run can use ``_shared_keys_touched_this_run`` only for merges within
    the same run (callbacks execute before the script body).
    """
    _sync_longitudinal_row_model_from_legacy_state()
    prev = load_shared_snapshot()
    if not isinstance(prev, dict):
        prev = {}
    touched = st.session_state.get("_shared_keys_touched_this_run")
    if not isinstance(touched, set):
        touched = set()
    # Persist shared inputs only (not results, not derived)
    shared: dict = {}
    for k in SHARED_DEFAULTS.keys():
        if k not in st.session_state:
            continue
        v = st.session_state[k]
        if k in MANUAL_DESIGN_ACTION_STALE_ZERO_GUARD_KEYS and snapshot_manual_action_prev_merge_identity_aligned():
            pv = prev.get(k)
            if (
                _is_zero_like(v)
                and _float_nonzero(pv)
                and k not in touched
            ):
                try:
                    pv_coerced = float(pv)
                except (TypeError, ValueError):
                    pv_coerced = pv
                try:
                    set_shared(k, pv_coerced, source="persist_snapshot_merge")
                except Exception:
                    pass
                v = st.session_state[k]
        shared[k] = v

    # Save to file (survives server restarts)
    save_shared_snapshot(shared, workspace_origin=get_workspace_origin())

    if reset_manual_action_touch_latch:
        st.session_state["_shared_keys_touched_this_run"] = set()
    
    # Also persist to in-memory store (for backward compatibility)
    cid = get_client_id()
    store = _persistent_store()

    # Persist ONLY shared keys. Persisting widget keys causes loaded projects to be overwritten.
    store[cid] = {
        "shared": shared,
        "widgets": {},
        "workspace_origin": get_workspace_origin(),
        "workspace_identity": get_workspace_identity_for_persist(),
    }


def restore_state_snapshot_if_available(force: bool = False) -> bool:
    """
    If session_state wiped, restore from persisted snapshot.
    Returns True if restored anything.
    
    Args:
        force: If True, overwrite existing keys. If False, only restore missing keys.
    """
    SNAPSHOT_RESTORE_EXCLUDE = {
        "actions_source",
        "actions_mode",
    }
    # If a project payload was loaded this run, DO NOT restore cached snapshot/widgets over it.
    if st.session_state.get(DISABLE_SNAPSHOT_RESTORE_KEY):
        return False
    # Never overwrite live session state after user interaction
    if st.session_state.get("_user_has_edited_anything", False):
        return False
    
    # Prevent repeated restore loops
    if st.session_state.get("_snapshot_restore_complete", False):
        return False
    
    # Try file-based snapshot first (survives server restarts)
    snap = migrate_longitudinal_reo_snapshot(load_shared_snapshot())
    restored_any = False
    file_oo, file_wid = _read_snapshot_workspace_meta_from_file()
    file_restore_ok = workspace_snapshot_restore_allowed(
        snapshot_origin=file_oo, snapshot_identity=file_wid
    )

    if snap and file_restore_ok:
        # Restore shared inputs from file snapshot
        for k in SHARED_DEFAULTS.keys():
            if k in snap:
                if k in SNAPSHOT_RESTORE_EXCLUDE:
                    continue
                if k in MANUAL_DESIGN_ACTION_STALE_ZERO_GUARD_KEYS:
                    if _is_zero_like(snap[k]) and k in st.session_state and _float_nonzero(
                        st.session_state.get(k)
                    ):
                        continue
                if force or (k not in st.session_state):
                    set_shared(k, snap[k], source="restore_snapshot")
                    restored_any = True
    
    # Also try in-memory store (for backward compatibility)
    cid = get_client_id()
    store = _persistent_store()
    mem_snap = copy.deepcopy(store.get(cid))
    if isinstance(mem_snap, dict) and isinstance(mem_snap.get("shared"), dict):
        mem_snap["shared"] = migrate_longitudinal_reo_snapshot(mem_snap.get("shared"))
    
    mem_oo = mem_snap.get("workspace_origin") if isinstance(mem_snap, dict) else None
    mem_wid = mem_snap.get("workspace_identity") if isinstance(mem_snap, dict) else None
    if not isinstance(mem_oo, str) or mem_oo not in (
        WORKSPACE_ORIGIN_NEW_FILE,
        WORKSPACE_ORIGIN_LOADED_FILE,
        WORKSPACE_ORIGIN_RESUMED_SESSION,
    ):
        mem_oo = None
    if isinstance(mem_wid, str) and not mem_wid.strip():
        mem_wid = None
    elif not isinstance(mem_wid, str):
        mem_wid = None
    mem_restore_ok = workspace_snapshot_restore_allowed(
        snapshot_origin=mem_oo,
        snapshot_identity=mem_wid,
    )

    if mem_snap and not restored_any and mem_restore_ok:
        # Restore shared first
        for k, v in mem_snap.get("shared", {}).items():
            if k in SHARED_DEFAULTS:  # Only restore shared inputs
                if k in SNAPSHOT_RESTORE_EXCLUDE:
                    continue
                if k in MANUAL_DESIGN_ACTION_STALE_ZERO_GUARD_KEYS:
                    if _is_zero_like(v) and k in st.session_state and _float_nonzero(
                        st.session_state.get(k)
                    ):
                        continue
                if force or (k not in st.session_state):
                    set_shared(k, v, source="restore_snapshot")
                    restored_any = True
        mo = mem_snap.get("workspace_origin")
        if mo in (
            WORKSPACE_ORIGIN_NEW_FILE,
            WORKSPACE_ORIGIN_LOADED_FILE,
            WORKSPACE_ORIGIN_RESUMED_SESSION,
        ):
            st.session_state[WORKSPACE_ORIGIN_KEY] = str(mo)

    if restored_any:
        st.session_state["_snapshot_restore_complete"] = True

    return restored_any


def begin_render_cycle():
    """
    MUST be called once per run (in app.py before rendering any page).
    Ensures rendered widget gating is per-run, not cumulative across runs.
    """
    st.session_state["_rendered_widget_keys"] = set()
    diag_log_widget_vs_shared_high_risk("begin_render_cycle")


def diag_log_widget_vs_shared_high_risk(tag: str = "render") -> None:
    """
    TODO(remove): Dev-only compare canonical shared keys vs page widget keys for drift.
    Enable with st.session_state['_dev_mode'] and st.session_state['_widget_hydration_diag'] = True.
    """
    if not bool(st.session_state.get("_dev_mode")):
        return
    if not bool(st.session_state.get("_widget_hydration_diag")):
        return
    loads = str(st.session_state.get("loads_edit_mode", "ULS") or "ULS").upper()
    prefix = "sls" if loads == "SLS" else "uls"
    pairs = [
        ("inputs_fc", "fc"),
        ("inputs_fsy", "fsy"),
        ("inputs_D", "D"),
        ("inputs_L", "L"),
        ("inputs_b", "b"),
        ("inputs_top1_count", "top1_count"),
        ("inputs_bot1_count", "bot1_count"),
        ("bending_fc", "fc"),
        ("bending_fsy", "fsy"),
        ("shear_b", "b"),
        ("shear_fc", "fc"),
        ("crack_fc", "fc"),
        (f"inputs_load_Mstar_pos_proxy", f"{prefix}_Mstar_pos_manual"),
        (f"inputs_load_Mstar_neg_proxy", f"{prefix}_Mstar_neg_manual"),
        ("inputs_load_Vstar_proxy", f"{prefix}_Vstar"),
    ]
    rows = []
    for wk, sk in pairs:
        rows.append(
            {
                "widget_key": wk,
                "shared_key": sk,
                "widget": st.session_state.get(wk),
                "shared": st.session_state.get(sk),
                "match": st.session_state.get(wk) == st.session_state.get(sk),
            }
        )
    try:
        hc_log(
            f"[widget_shared_diag:{tag}]",
            loads_edit_mode=loads,
            actions_mode=st.session_state.get("actions_mode"),
            rows=rows,
        )
    except Exception:
        pass


def debug_log(tag: str, data: dict):
    """Helper to write debug logs in consistent format."""
    return


def log_shared_diff(tag: str):
    """Log any changes to shared keys since last run."""
    prev = st.session_state.get("_prev_shared_snapshot", {})
    now = {k: st.session_state.get(k) for k in SHARED_DEFAULTS.keys()}

    diffs = {}
    for k, v in now.items():
        if prev.get(k) != v:
            diffs[k] = {"prev": prev.get(k), "now": v}

    st.session_state["_prev_shared_snapshot"] = now

    if diffs:
        debug_log(tag, {"changed_shared": diffs})


def _is_invalid_shared_value(shared_key: str, val) -> bool:
    """Shared is invalid if None, or (==0 and zero is NOT allowed for this key)."""
    if val is None:
        return True
    if isinstance(val, (int, float)) and float(val) == 0.0 and not zero_allowed(shared_key):
        return True
    return False


def repair_inputs_shared_from_widgets():
    """
    Deprecated.
    Shared inputs are the source of truth and must not be reconstructed
    from widgets on other pages.
    """
    return


def force_inputs_to_shared_after_wipe():
    """After wipe restore: treat inputs_* widget values as the only truth."""
    if not st.session_state.get("_wipe_recovery_mode", False):
        return

    repaired = {}
    for widget_key, shared_key in TAB_KEYS.items():
        if not widget_key.startswith("inputs_"):
            continue
        if widget_key not in st.session_state:
            continue

        wv = st.session_state.get(widget_key)
        sv = st.session_state.get(shared_key)

        # Never overwrite crack inputs or deflection support type during wipe recovery
        if shared_key in ("crack_k1", "crack_member_type", "defl_support_type"):
            continue

        # always force (even if nonzero mismatch)
        if sv != wv:
            set_shared(shared_key, wv, source="wipe_recovery")
            repaired[shared_key] = {"from": widget_key, "old": sv, "new": wv}

    if repaired:
        debug_log("WIPE_RECOVERY_FORCED_INPUTS_TO_SHARED", repaired)


def init_shared_session_state():
    """
    Initialise all shared keys and tab-widget keys in st.session_state.
    This must be called before any page renders widgets.
    
    IMPORTANT: This function only sets defaults when keys are missing.
    It NEVER overwrites existing user values.
    
    Always backfills missing widget keys (even after initialization) to prevent
    widgets from resetting when Streamlit drops widget state.
    """
    # Debug boot id: helps detect when the whole session got rebuilt
    if st.session_state.get("_boot_id") is None:
        st.session_state["_boot_id"] = f"boot_{int(time.time())}"

    # Watchdog: log shared key changes at entry
    log_shared_diff("init_entry_shared_diff")
    
    # Detect fresh boot
    if "_boot_id" not in st.session_state:
        st.session_state["_boot_id"] = str(uuid.uuid4())
        st.session_state["_fresh_boot"] = True
    else:
        st.session_state["_fresh_boot"] = False
    
    already_initialized = st.session_state.get("_shared_state_initialized", False)
    
    # Detect wipe recovery mode
    WIPED = not already_initialized
    
    if WIPED:
        st.session_state["_wipe_recovery_mode"] = True
        debug_log("WIPE_RECOVERY_MODE_ENABLED", {})
    else:
        st.session_state["_wipe_recovery_mode"] = False
    
    # Never overwrite live session state after user interaction
    restored = False
    restored_from_snapshot = False

    # Cold server session: recover explicit workspace origin from disk before snapshot merge
    if st.session_state.get("_fresh_boot", False) and WORKSPACE_ORIGIN_KEY not in st.session_state:
        fo = load_workspace_origin_from_snapshot_file()
        if fo:
            st.session_state[WORKSPACE_ORIGIN_KEY] = fo

    if not st.session_state.get("_user_has_edited_anything", False):
        # On fresh boot, restore snapshot BEFORE seeding defaults
        if st.session_state.get("_fresh_boot", False):
            # Prevent repeated restore loops
            if not st.session_state.get("_snapshot_restore_complete", False):
                # Project load sets DISABLE_SNAPSHOT_RESTORE_KEY: do not merge stale file snapshot
                # over the payload already applied in app.main().
                if st.session_state.get(DISABLE_SNAPSHOT_RESTORE_KEY):
                    st.session_state["_snapshot_restore_complete"] = True
                else:
                    snap = migrate_longitudinal_reo_snapshot(load_shared_snapshot())
                    f_oo, f_wid = _read_snapshot_workspace_meta_from_file()
                    file_ok = workspace_snapshot_restore_allowed(
                        snapshot_origin=f_oo, snapshot_identity=f_wid
                    )
                    if snap and file_ok:
                        # Restore only known shared input keys
                        for k in SHARED_DEFAULTS.keys():
                            if k in snap:
                                if k in MANUAL_DESIGN_ACTION_STALE_ZERO_GUARD_KEYS:
                                    if _is_zero_like(snap[k]) and k in st.session_state and _float_nonzero(
                                        st.session_state.get(k)
                                    ):
                                        continue
                                set_shared(k, snap[k], source="wipe_recovery")
                                restored_from_snapshot = True
                        restored = restored_from_snapshot
                    st.session_state["_restored_from_snapshot"] = restored_from_snapshot
                    st.session_state["_snapshot_restore_complete"] = restored_from_snapshot
                    # Set restore guard flags to prevent callbacks from overwriting restored values
                    if restored_from_snapshot:
                        st.session_state["_restore_guard_active"] = True
                        st.session_state["_restore_guard_ts"] = time.time()
                        # After snapshot restore, force one deterministic derived-values pass
                        # This ensures derived values (d, Ast_bot, etc.) are recalculated from restored inputs
                        recalc_derived_values()
    # Session wipe: restore FIRST (force overwrite), then seed anything still missing
    # Skip if we already restored from file snapshot on fresh boot
    # Also skip if user has interacted (never overwrite after user edits)
    if not already_initialized and not restored and not st.session_state.get("_user_has_edited_anything", False):
        # Prevent repeated restore loops
        if not st.session_state.get("_snapshot_restore_complete", False):
            # Force restore: overwrite any defaults that were seeded
            restored = restore_state_snapshot_if_available(force=True)
            
            # Set restore guard flags to prevent callbacks from overwriting restored values
            if restored:
                st.session_state["_restored_from_snapshot"] = True
                st.session_state["_snapshot_restore_complete"] = True
                st.session_state["_restore_guard_active"] = True
                st.session_state["_restore_guard_ts"] = time.time()
                # After snapshot restore, force one deterministic derived-values pass
                # This ensures derived values (d, Ast_bot, etc.) are recalculated from restored inputs
                recalc_derived_values()
        
        # After restoring, recompute the flag (it may have come back via snapshot)
        already_initialized = st.session_state.get("_shared_state_initialized", False)

        # If we restored shared keys, we can safely set initialized now
        if restored and not already_initialized:
            st.session_state["_shared_state_initialized"] = True
            already_initialized = True
    
    # Migrate old time defaults after snapshot restore (before seeding defaults)
    migrate_time_defaults_once()
    
    # NOW seed defaults only for anything still missing (after restore)
    for key, val in SHARED_DEFAULTS.items():
        v = ss_get(key)
        if is_missing(v):
            set_shared(key, val, source="seed_defaults")
    _sync_longitudinal_row_model_from_legacy_state()
    
    # Ensure load proxies match the active edit mode on init
    actions_mode = st.session_state.get("actions_mode", "manual")
    is_design_driven = actions_mode == "design"
    if not is_design_driven:
        load_proxies_from_active_set()

    # Seed UI-only defaults (not shared, not synced)
    for k, v in UI_STATE_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    st.session_state.setdefault(WORKSPACE_ORIGIN_KEY, WORKSPACE_ORIGIN_RESUMED_SESSION)
    
    # Debug: confirm shared keys are fully present after init
    if st.session_state.get("_debug_state_tripwire", False):
        missing_shared = [k for k in SHARED_DEFAULTS.keys() if k not in st.session_state]
        if missing_shared:
            _append_debug_log(
                f"MISSING_SHARED_AFTER_INIT boot={st.session_state.get('_boot_id')} "
                f"count={len(missing_shared)} sample={missing_shared[:25]}"
            )
        else:
            _append_debug_log(
                f"INIT_OK boot={st.session_state.get('_boot_id')} shared_count={len(SHARED_DEFAULTS)}"
            )
    
    # Ensure sentinel exists once we have a valid state
    if not st.session_state.get("_shared_state_initialized", False):
        st.session_state["_shared_state_initialized"] = True
    
    # 1) Shared values: only set if missing (never overwrite)
    # Only run once.
    if not already_initialized:
        for key, val in SHARED_DEFAULTS.items():
            v = ss_get(key)
            if is_missing(v):
                set_shared(key, val, source="seed_defaults")
    
    # Seed result defaults (derived outputs). Do not overwrite if already present.
    for k, v in RESULT_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # 2) Tab-widget keys - ALWAYS ensure widget keys exist (only seed if missing).
    # This prevents "Inputs resets when returning" if widget keys were dropped between pages.
    # CRITICAL: Only restore widget keys if they are TRULY missing (not just None/0).
    # If a widget key exists in session_state (even if value is 0), do NOT overwrite it.
    restored_widgets = []
    for widget_key, shared_key in TAB_KEYS.items():
        widget_exists = widget_key in st.session_state
        shared_exists = shared_key in st.session_state
        widget_value = st.session_state.get(widget_key) if widget_exists else None
        shared_value = st.session_state.get(shared_key) if shared_exists else None
        
        
        # Check if widget key exists but differs from cache.
        # IMPORTANT: if the widget exists, the widget value is authoritative (user input).
        # Cache is ONLY used to restore if Streamlit dropped the widget key.
        cached_key = f"_cached_{widget_key}"
        widget_missing = (widget_key not in st.session_state) or (st.session_state.get(widget_key) is None)

        # ONLY restore from cache if Streamlit dropped the widget key
        # CRITICAL: Always prefer cache over shared state for inputs_* widgets
        # Cache preserves the actual user input, while shared state might be stale
        restored_value = None
        if widget_missing and widget_key.startswith("inputs_") and cached_key in st.session_state:
            cached_value = st.session_state[cached_key]
            default_value = SHARED_DEFAULTS.get(shared_key, None)

            # 0 is a VALID user value for many keys (reo counts, legs, diameters, etc).
            # Only treat cached 0 as "stale" for keys where 0 is NOT allowed — OR for
            # manual design actions when shared is still non-zero (navigation duplicate).
            manual_stale_cache = _manual_action_stale_widget_zero(
                widget_val=cached_value,
                shared_val=st.session_state.get(shared_key),
                shared_key=shared_key,
            )
            cache_is_valid = (not manual_stale_cache) and (
                (cached_value != 0)
                or (
                    cached_value == 0
                    and (default_value == 0 or zero_allowed(shared_key))
                )
            )
            # DEBUG (temporary)
            # st.write("CACHE RESTORE", widget_key, shared_key, cached_value, "valid=", cache_is_valid)
            
            if cache_is_valid:
                restored_value = cached_value
                st.session_state[widget_key] = restored_value
                st.session_state[cached_key] = restored_value
            else:
                # Cache is stale (0 when it shouldn't be) - skip cache restoration, fall through to other sources
                pass

        if widget_missing:
            # When restoring widget keys, prefer inputs_* widget values if they exist
            # (they're the primary source and more likely to be up-to-date)
            # Check in this order:
            # 1) Cached inputs_* widget value (preserved from last sync) - already handled above
            # 2) Existing inputs_* widget in session_state (if not dropped)
            # 3) Shared state value
            # 4) Defaults
            
            # Skip cache restoration (already handled above), check for other sources
            if restored_value is None:
                # Check if there's an inputs_* widget for this shared key that still exists
                inputs_widget_key = None
                for wk, sk in TAB_KEYS.items():
                    if sk == shared_key and wk.startswith("inputs_") and wk in st.session_state:
                        inputs_widget_key = wk
                        break
                
                if inputs_widget_key:
                    # Prefer the inputs_* widget value (it's more authoritative)
                    restored_value = st.session_state[inputs_widget_key]
                    if _manual_action_stale_widget_zero(
                        widget_val=restored_value,
                        shared_val=st.session_state.get(shared_key),
                        shared_key=shared_key,
                    ):
                        restored_value = st.session_state.get(shared_key)
                    st.session_state[widget_key] = restored_value
                    # Update the cache to keep it current with the actual inputs_* widget value
                    cached_inputs_key = f"_cached_{inputs_widget_key}"
                    st.session_state[cached_inputs_key] = restored_value
                elif shared_key in st.session_state:
                    # Fall back to shared value if no inputs_* widget exists
                    shared_value = st.session_state[shared_key]
                    default_value = SHARED_DEFAULTS.get(shared_key, None)
                    
                    # CRITICAL FIX: Don't restore from shared state if shared is 0 and default is not 0
                    # This prevents restoring widgets to 0 when shared state is stale/uninitialized
                    # Only restore if:
                    # 1) Shared value is not 0, OR
                    # 2) Shared value is 0 AND default is also 0 (0 is legitimate)
                    should_restore = (shared_value != 0) or (
                        shared_value == 0 and (
                            default_value == 0 or zero_allowed(shared_key)
                        )
                    )
                    
                    
                    if should_restore:
                        restored_value = shared_value
                        old_widget_value = st.session_state.get(widget_key)
                        st.session_state[widget_key] = restored_value
                        # Log overwrite
                        if old_widget_value != restored_value:
                            pass
                    else:
                        # Skip restoring from shared (stale 0 value) BUT DO NOT write None into the widget.
                        # Instead fall back to the default value immediately.
                        restored_value = SHARED_DEFAULTS.get(shared_key, None)

                        # Only set if we actually have a default; otherwise leave missing
                        if restored_value is not None:
                            old_widget_value = st.session_state.get(widget_key)
                            st.session_state[widget_key] = restored_value
                            # Log overwrite with default
                            if old_widget_value != restored_value:
                                pass
                else:
                    # Final fallback to defaults
                    restored_value = SHARED_DEFAULTS.get(shared_key, None)
                    st.session_state[widget_key] = restored_value
            
            restored_widgets.append((widget_key, shared_key, restored_value))

    # 3) Only run your "snippet defaults" guard / snapshot ONCE
    if not already_initialized:
        if _is_snippet_defaults_state(st.session_state):
            _restore_last_good_inputs()
        else:
            _snapshot_last_good_inputs()

        st.session_state["_shared_state_initialized"] = True
        st.session_state["_shared_inited"] = True  # Keep legacy flag for compatibility
    
    # Keep global snapshot fresh on every run IF values look sane.
    # (No overwrites when we're in a bogus defaults state.)
    if not _is_snippet_defaults_state(st.session_state):
        _snapshot_last_good_inputs()
    
    # ============================
    # SAFE HYDRATION (NO widget→shared here)
    # ============================
    # CRITICAL: Only sync via on_change callbacks, never during init.
    # This prevents stale widget zeros from overwriting shared state on navigation.
    
    # NOTE:
    # Do NOT sync shared <- inputs_* here.
    # Shared must only be updated by on_change callbacks (or explicit sync functions),
    # otherwise stale navigation zeros can overwrite shared state.

    # 2) Hydrate ONLY the active page's widget keys, and only if missing.
    active_slug = st.session_state.get("page_slug") or st.session_state.get("_active_page_slug")
    if active_slug:
        prefix = f"{active_slug}_"
        for widget_key, shared_key in TAB_KEYS.items():
            if not widget_key.startswith(prefix):
                continue
            safe_hydrate(widget_key, shared_key, st.session_state.get(shared_key))
    
    # Keep inputs_* cache current, BUT do not poison it with stale navigation zeros.
    for widget_key, shared_key in TAB_KEYS.items():
        if widget_key.startswith("inputs_") and widget_key in st.session_state:
            widget_val = st.session_state[widget_key]
            cached_key = f"_cached_{widget_key}"

            default_value = SHARED_DEFAULTS.get(shared_key, None)
            shared_val = st.session_state.get(shared_key, None)

            # Detect "stale zero" (navigation glitch) for keys we must never let go stale:
            # - widget is 0
            # - shared has a meaningful non-zero value
            # - default is meaningful non-zero
            # - key is protected (geometry/materials/actions)
            # OR: manual design-action keys (0 allowed, but widget 0 while shared != 0 is stale)
            manual_nav_stale = _manual_action_stale_widget_zero(
                widget_val=widget_val,
                shared_val=shared_val,
                shared_key=shared_key,
            )
            is_stale_zero = manual_nav_stale or (
                (widget_val == 0 or widget_val == 0.0)
                and (shared_key in NONZERO_REQUIRED_SHARED_KEYS)
                and (not zero_allowed(shared_key))
                and (shared_val not in (None, 0, 0.0))
                and (default_value not in (None, 0, 0.0))
            )

            if not is_stale_zero:
                st.session_state[cached_key] = widget_val
            # else: do NOT overwrite cache; keep the last known good value
    
    # Only attempt repair if we did NOT successfully restore from snapshot
    # This prevents "repair" logic from stomping restored state
    # NOTE: repair_inputs_shared_from_widgets() is disabled - shared inputs are the source of truth
    # and must not be reconstructed from widgets on other pages.
    if not restored:
        # repair_inputs_shared_from_widgets()  # DISABLED - see note above
        pass
    
    # Wipe Recovery Mode: force Inputs -> shared after wipe restore
    force_inputs_to_shared_after_wipe()
    
    # After wipe restore, Inputs are the canonical truth
    # This removes any lingering "shared disagrees with inputs" states
    if st.session_state.get("_wipe_recovery_mode", False):
        for widget_key, shared_key in TAB_KEYS.items():
            if widget_key.startswith("inputs_") and widget_key in st.session_state:
                set_shared(shared_key, st.session_state[widget_key], source="wipe_recovery")
    
    # Watchdog: log shared key changes at exit
    log_shared_diff("init_exit_shared_diff")
    
    # Debug-only: validate contract after initialization
    try:
        from src.debug.state_debug import is_debug_enabled
        if is_debug_enabled():
            validate_session_state_contract(context="after init_shared_session_state")
    except (ImportError, NameError):
        # Debug module not available, skip validation
        pass
    
    # Tripwire: detect shared keys that got zeroed during init
    _shared_zero_tripwire("AFTER init_shared_session_state")
    
    # Persist snapshot after init/restore so future wipes recover correctly
    persist_state_snapshot()
    
    if st.session_state.get("_debug_state_tripwire", False):
        _append_debug_log(f"INIT_DONE boot={st.session_state.get('_boot_id')}")


def hydrate_tab_widgets_from_shared(tab_name: str):
    """
    If widget keys are missing, seed them from shared values BEFORE rendering widgets.
    This prevents widgets coming up as 0/default after snapshot restore.
    
    Args:
        tab_name: Tab/page prefix (e.g., "inputs", "bending", "crack", "shear")
    """
    prefix = f"{tab_name}_"
    hydrated_count = 0
    
    for widget_key, shared_key in TAB_KEYS.items():
        if not widget_key.startswith(prefix):
            continue
        
        # Only seed widget key if truly missing
        if widget_key not in st.session_state:
            shared_val = st.session_state.get(shared_key)
            if shared_val is not None:
                st.session_state[widget_key] = shared_val
                hydrated_count += 1
    
    return hydrated_count


def force_hydrate_time_widgets_from_shared():
    """
    Force-hydrate the time-dependent INPUTS widgets from shared if the widgets are still at stale defaults (0/1).
    This prevents sync_callback from clobbering shared values (365/28/365) with widget value 1.
    """
    pairs = [
        ("inputs_t_creep", "t_creep"),
        ("inputs_age_at_loading", "age_at_loading"),
        ("inputs_t_shrink", "t_shrink"),
    ]

    for widget_key, shared_key in pairs:
        # shared value
        sv = st.session_state.get(shared_key, SHARED_DEFAULTS.get(shared_key))
        # widget value
        wv = st.session_state.get(widget_key, None)

        try:
            svf = float(sv) if sv is not None else None
        except Exception:
            svf = None
        try:
            wvf = float(wv) if wv is not None else None
        except Exception:
            wvf = None

        # Only force-hydrate if shared is meaningful (>1) and widget is stale (missing/0/1).
        if svf is not None and svf > 1 and (wvf is None or wvf in (0.0, 1.0)):
            st.session_state[widget_key] = svf


def hydrate_active_page_widgets_from_shared(
    active_slug: str,
    force_on_restore: bool = False,
    force_on_page_change: bool = False,
) -> None:
    """
    Prevent stale page widget keys (often 0) from overwriting shared values on navigation.
    Runs BEFORE rendering the active page so widgets start from shared values.
    Only force-hydrates keys whose shared values should not be clobbered by zeros.
    
    Widget instances are page-local. Cross-page continuity belongs to the
    canonical shared input transaction, not to off-page widget keys.
    
    Args:
        active_slug: Page slug (e.g., "bending", "crack", "inputs")
        force_on_restore: If True and snapshot was restored, force-overwrite stale widget values (0/1)
    """
    if str(active_slug) == "inputs":
        try:
            st.session_state["_contract_inputs_hydrate_invocations"] = int(
                st.session_state.get("_contract_inputs_hydrate_invocations", 0),
            ) + 1
        except Exception:
            pass

    # Build from widget -> shared mappings first.  TAB_KEYS_BY_PAGE is keyed by
    # shared name and therefore cannot represent two legitimate widget aliases
    # for one shared value (for example both Deflection-limit widget keys).
    # Collapsing those aliases leaves an old widget value alive across routes.
    prefix = f"{active_slug}_"
    wmap = {wk: sk for wk, sk in TAB_KEYS.items() if wk.startswith(prefix)}
    page_map = TAB_KEYS_BY_PAGE.get(active_slug)
    if page_map:
        for shared_key, widget_key in page_map.items():
            wmap.setdefault(widget_key, shared_key)

    force_inputs_reseed = False
    if active_slug == "inputs" and bool(st.session_state.get("_force_inputs_widget_reseed_once")):
        force_inputs_reseed = True
        st.session_state["_force_inputs_widget_reseed_once"] = False
        try:
            import session_state_final_log as _ssl

            _ssl.append_session_state_final_log(
                "force_inputs_widget_reseed_cleared",
                {"hydration_layer": "router_or_hydrate", "active_slug": active_slug},
            )
            _ssl.ssl_increment("force_inputs_widget_reseed_cleared_count", 1)
        except Exception:
            pass
        if bool(st.session_state.get("_dev_mode")):
            hc_log("[hydrate] consumed _force_inputs_widget_reseed_once", active_slug=active_slug, force_inputs_reseed=True)

    if not wmap:
        return
    _write_sync_trace_line(f"HYDRATE_ACTIVE_PAGE slug={active_slug} keys={len(wmap)}")

    # Load Analysis owns a beam-local draft until the user explicitly enables
    # publication to Beam Inputs.  On a route return, Streamlit has discarded
    # the page's widget instances and the router must recreate them from that
    # draft—not from the unchanged main-beam shared state.  Hydrating from the
    # shared state here used to make an entered load visibly return to zero.
    load_analysis_draft_snapshot: dict[str, object] = {}
    if active_slug == "design" and (
        not bool(st.session_state.get("inputs_use_calculated_actions", False))
        or bool(
            st.session_state.get(
                "_load_analysis_action_publication_requested", False
            )
        )
    ):
        try:
            from inputs_application.load_analysis_draft import (
                current_load_analysis_draft,
            )

            draft = current_load_analysis_draft(st.session_state)
            if draft is not None:
                load_analysis_draft_snapshot = dict(draft.snapshot or {})
        except (ImportError, RuntimeError, TypeError, ValueError):
            load_analysis_draft_snapshot = {}

    beam_just_loaded = bool(st.session_state.pop("_force_hydrate_widgets_after_beam_load", False))
    in_restore_hydrate_window = bool(
        force_on_restore and st.session_state.get("_restore_guard_active")
    )

    # Seed only missing widget keys for this page
    hydrated_count = 0
    live_action_widget_keys = {
        "inputs_load_Mstar_proxy",
        "inputs_load_Mstar_pos_proxy",
        "inputs_load_Mstar_neg_proxy",
        "inputs_load_Vstar_proxy",
        "inputs_load_Nstar_proxy",
        "inputs_Tu_star",
        "inputs_P_star",
    }
    for widget_key, shared_key in wmap.items():
        if widget_key in live_action_widget_keys and not (
            force_inputs_reseed
            or beam_just_loaded
            or in_restore_hydrate_window
            or bool(force_on_page_change)
        ):
            continue
        # Design page: span widget hydrates from canonical L (mm), not span_L_m.
        # Keep the same sticky behavior as safe_hydrate(): seed only if missing,
        # or force on page change.
        if active_slug == "design" and widget_key == "sfd_L_m":
            force = bool(force_on_page_change) or beam_just_loaded or in_restore_hydrate_window
            L_seed_m = max(
                0.1,
                float(st.session_state.get("L", 3000.0)) / 1000.0,
            )
            safe_hydrate(widget_key, "L", L_seed_m, force=force)
            if widget_key in st.session_state:
                hydrated_count += 1
            continue
        source_has_value = (
            shared_key in load_analysis_draft_snapshot
            or shared_key in st.session_state
        )
        if not source_has_value:
            continue
        widget_before = st.session_state.get(widget_key)
        force = bool(force_on_page_change) or beam_just_loaded or in_restore_hydrate_window
        if active_slug == "inputs" and widget_key.startswith("inputs_") and force_inputs_reseed:
            force = True
        source_value = (
            load_analysis_draft_snapshot[shared_key]
            if shared_key in load_analysis_draft_snapshot
            else st.session_state.get(shared_key)
        )
        safe_hydrate(widget_key, shared_key, source_value, force=force)
        if bool(st.session_state.get("_dev_mode")) and widget_key in {
            "inputs_bot_row_1_dia",
            "inputs_bot_row_1_bars",
            "inputs_bot_row_1_mode",
            "inputs_bot_row_1_spacing",
            "inputs_bot_row_count",
            "inputs_bot1_count",
            "inputs_top_row_1_dia",
        }:
            hc_log(
                f"[hydrate] {widget_key} <- {shared_key}",
                shared_before=st.session_state.get(shared_key),
                widget_before=widget_before,
                widget_after=st.session_state.get(widget_key),
                force=force,
            )
        if widget_key in st.session_state:
            hydrated_count += 1

    if bool(st.session_state.get("_dev_mode")) and force_inputs_reseed:
        tracked_pairs = [
            ("inputs_bot_row_1_dia", "bot_row_1_dia"),
            ("inputs_bot_row_1_bars", "bot_row_1_bars"),
            ("inputs_bot_row_count", "bot_row_count"),
            ("inputs_bot1_count", "bot1_count"),
        ]
        mismatches = []
        for widget_key, shared_key in tracked_pairs:
            if st.session_state.get(widget_key) != st.session_state.get(shared_key):
                mismatches.append({
                    "widget_key": widget_key,
                    "shared_key": shared_key,
                    "widget_value": st.session_state.get(widget_key),
                    "shared_value": st.session_state.get(shared_key),
                })
        if mismatches:
            hc_log("[hydrate] forced inputs reseed mismatch", mismatches=mismatches)

    # Tripwire: detect shared keys that got zeroed during hydrate
    _shared_zero_tripwire("AFTER hydrate_active_page_widgets_from_shared")


def sync_shared_from_widgets_once_per_run():
    """
    App-level sync: Copy widget values to shared keys (one-way: widget → shared).
    
    This ensures that when you navigate away from a page, the widget values
    (which persist in session_state) are copied to shared keys so other
    pages see consistent values.
    
    CRITICAL: Syncs when widget values differ from shared values (recently changed).
    When multiple widgets map to the same shared key, prefers inputs_* widgets.
    This prevents stale widgets from overwriting recently changed values.
    
    Rules (SESSION STATE CONTRACT COMPLIANT):
    - Only syncs INPUT parameters (those in SHARED_DEFAULTS that have widget mappings)
    - Never touches derived values (d, Ast_bot, etc.) - those are handled by recalc_derived_values()
    - Never touches result values (phi_Mu_cap, etc.)
    - Only syncs if widget key exists and widget value differs from shared value
    - When multiple widgets map to same shared key, prefers inputs_* widgets among differing ones
    - Never creates new keys beyond SHARED_DEFAULTS
    - Never modifies widget keys
    - Only writes to shared keys defined in SHARED_DEFAULTS (RULE 1 compliant)
    """
    # Only sync input parameters (not derived, not results)
    # We identify inputs by checking if they're in SHARED_DEFAULTS and have widget mappings
    input_keys = set(SHARED_DEFAULTS.keys())
    
    # Exclude derived values (these are recalculated, not synced from widgets)
    # Use DERIVED_KEYS constant for consistency (defined after RESULT_KEYS)
    derived_keys = DERIVED_KEYS
    
    # Exclude result values (these are computed, not synced from widgets)
    result_keys = RESULT_KEYS
    
    # Only sync input keys (not derived, not results)
    syncable_keys = input_keys - derived_keys - result_keys
    
    # Active page gating:
    # - Always allow inputs_* (global)
    # - Only allow the current active page prefix (e.g. bending_*) to sync shared keys
    active_slug = st.session_state.get("_active_page_slug", "inputs")
    active_prefix = f"{active_slug}_"
    
    sync_operations = []
    try:
        skip_shear_widget_backflow_runs = int(st.session_state.get("_skip_shear_widget_backflow_runs", 0) or 0)
    except Exception:
        skip_shear_widget_backflow_runs = 0
    pending_refresh = st.session_state.get("_pending_inputs_apply_refresh")
    pending_design_guide_shear_refresh = False
    if isinstance(pending_refresh, dict):
        pending_refresh_source = str(pending_refresh.get("source") or "")
        pending_refresh_keys = {
            str(key)
            for key in (pending_refresh.get("keys") or [])
            if str(key)
        }
        pending_design_guide_shear_refresh = bool(
            pending_refresh_source == "guidance:apply_resolved_candidate"
            and pending_refresh_keys.intersection({"lig_d", "lig_legs", "s_lig"})
        )
    skip_shear_widget_backflow_once = bool(
        st.session_state.get("_skip_shear_widget_backflow_once")
        or skip_shear_widget_backflow_runs > 0
        or pending_design_guide_shear_refresh
    )
    
    # Shared keys that must NEVER be overwritten by other pages' defaults.
    # Authority order for these: inputs_* first, then bending_*.
    LOCKED_REO_SHARED_KEYS = {
        "nb_or_s_bot_1", "db_bot_1", "nb_or_s_bot_2", "db_bot_2",
        "nb_or_s_top_1", "db_top_1", "nb_or_s_top_2", "db_top_2",
        "rowgap_bot", "rowgap_top",
        "cover_bot", "cover_top",
        # Shear reinforcement (locked to inputs_* only)
        "lig_d", "lig_legs", "s_lig",
    }
    
    # Shared keys that should NEVER be overwritten with 0 if they have meaningful values
    # This prevents stale widget zeros from clobbering shared state
    PROTECTED_FROM_ZERO_SHARED_KEYS = NONZERO_REQUIRED_SHARED_KEYS
    
    # Group widgets by shared key to handle conflicts
    # V2: Only canonical widget keys rendered THIS RUN are allowed to author shared keys
    widgets_by_shared = {}

    rendered = st.session_state.get("_rendered_widget_keys")
    if not isinstance(rendered, set):
        rendered = set()
    

    for widget_key, shared_key in TAB_KEYS.items():
        if shared_key not in syncable_keys:
            continue
        if (
            (
                st.session_state.get("auto_design_active", False)
                or skip_shear_widget_backflow_once
            )
            and shared_key in {"lig_d", "lig_legs", "s_lig"}
        ):
            # Prevent same-run widget backflow from clobbering auto-designed values.
            continue

        # Only sync widgets that were rendered THIS RUN
        if widget_key not in rendered:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Skipped non-rendered key", "data": {"widget_key": widget_key, "shared_key": shared_key, "rendered_keys_count": len(rendered)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            continue

        # REO LOCK: Only inputs_* is allowed to author reinforcement shared keys
        if shared_key in LOCKED_REO_SHARED_KEYS and not widget_key.startswith("inputs_"):
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Skipped non-inputs widget for locked reo key", "data": {"widget_key": widget_key, "shared_key": shared_key}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "R"}) + "\n")
            except: pass
            # #endregion
            continue

        widget_value = st.session_state.get(widget_key)
        if widget_value is None:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Skipped missing key", "data": {"widget_key": widget_key, "shared_key": shared_key}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
            except: pass
            # #endregion
            continue

        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Adding widget to sync", "data": {"widget_key": widget_key, "shared_key": shared_key, "widget_value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
        except: pass
        # #endregion

        widgets_by_shared.setdefault(shared_key, []).append((widget_key, widget_value))
    
    # For each shared key, sync the "most authoritative" widget value
    # Priority: 
    # 1) Widgets that differ from current shared value (recently changed)
    # 2) Among differing widgets, prefer inputs_* widgets (they're the primary source)
    # 3) If all widgets match shared value, no sync needed
    for shared_key, widget_list in widgets_by_shared.items():
        current_shared = st.session_state.get(shared_key)

        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:742", "message": "Processing shared key", "data": {"shared_key": shared_key, "current_shared": current_shared, "widget_list": widget_list}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
        except: pass
        # #endregion
        
        # Find widgets that differ from current shared value (these are "recently changed")
        differing_widgets = [(wk, wv) for wk, wv in widget_list if current_shared != wv]
        
        # Note: Locked reo keys are already filtered earlier - only inputs_* widgets
        # are allowed to sync for LOCKED_REO_SHARED_KEYS (see REO LOCK check above)
        
        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:750", "message": "Differing widgets found", "data": {"shared_key": shared_key, "differing_widgets": differing_widgets}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
        except: pass
        # #endregion
        
        if current_shared is None:
            # Shared key missing - prefer inputs_* widget if available, otherwise use first
            inputs_widgets = [(wk, wv) for wk, wv in widget_list if wk.startswith("inputs_")]
            if inputs_widgets:
                widget_key, widget_value = inputs_widgets[0]
            else:
                widget_key, widget_value = widget_list[0]
            set_shared(shared_key, widget_value, source="sync_init")
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Initialized shared key", "data": {"widget_key": widget_key, "shared_key": shared_key, "value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
            except: pass
            sync_operations.append((widget_key, shared_key, widget_value, "init", None))
            # #endregion
        elif differing_widgets:
            # At least one widget differs - prefer inputs_* widgets among the differing ones
            inputs_differing = [(wk, wv) for wk, wv in differing_widgets if wk.startswith("inputs_")]
            
            # CRITICAL: Prevent overwriting meaningful shared values with 0
            # If shared key is protected and has a meaningful value, don't allow 0 to overwrite it
            # BUT: allow 0 for zero-allowed keys (where 0 is legitimate)
            if shared_key in PROTECTED_FROM_ZERO_SHARED_KEYS and not zero_allowed(shared_key):
                shared_is_meaningful = current_shared not in (None, "", 0, 0.0)
                if shared_is_meaningful:
                    # Filter out widgets with value 0 - they're stale and shouldn't overwrite meaningful shared values
                    filtered_differing = [(wk, wv) for wk, wv in differing_widgets 
                                         if wv not in (None, "", 0, 0.0)]
                    if filtered_differing:
                        differing_widgets = filtered_differing
                        # Recompute inputs_differing after filtering
                        inputs_differing = [(wk, wv) for wk, wv in differing_widgets if wk.startswith("inputs_")]
                        # #region agent log
                        try:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"location": "state_and_helpers.py:protect_zero", "message": "Filtered out zero widgets from protected key", "data": {"shared_key": shared_key, "current_shared": current_shared, "filtered_count": len(filtered_differing), "original_count": len(differing_widgets)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "L"}) + "\n")
                        except: pass
                        # #endregion
                    else:
                        # All widgets are 0 - skip sync to preserve meaningful shared value
                        # #region agent log
                        try:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"location": "state_and_helpers.py:protect_zero", "message": "Skipped sync - all widgets are zero for protected key", "data": {"shared_key": shared_key, "current_shared": current_shared}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "L"}) + "\n")
                        except: pass
                        # #endregion
                        continue
            
            # Check if there's a cached inputs_* value for this shared key
            # If so, only allow non-inputs_* widgets to sync if they match the cached value
            # This prevents stale widgets from overwriting values set by inputs_* widgets
            # IMPORTANT: Check cache even if inputs_* widget isn't in the current widget list
            # (it might have been dropped by Streamlit)
            cached_inputs_value = None
            for wk, sk in TAB_KEYS.items():
                if sk == shared_key and wk.startswith("inputs_"):
                    cached_key = f"_cached_{wk}"
                    if cached_key in st.session_state:
                        cached_inputs_value = st.session_state[cached_key]
                        # #region agent log
                        try:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"location": "state_and_helpers.py:815", "message": "Found cached inputs value", "data": {"shared_key": shared_key, "cached_key": cached_key, "cached_value": cached_inputs_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
                        except: pass
                        # #endregion
                        break
            
            # Filter out non-inputs_* widgets that would overwrite a cached inputs_* value
            if cached_inputs_value is not None:
                # Only allow non-inputs_* widgets to sync if they match the cached value
                # This prevents stale widgets from overwriting the correct value
                filtered_differing = [(wk, wv) for wk, wv in differing_widgets 
                                     if wk.startswith("inputs_") or wv == cached_inputs_value]
                if filtered_differing != differing_widgets:
                    differing_widgets = filtered_differing
                    # Recompute inputs_differing after filtering
                    inputs_differing = [(wk, wv) for wk, wv in differing_widgets if wk.startswith("inputs_")]
                    
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"location": "state_and_helpers.py:825", "message": "Filtered out stale widgets", "data": {"shared_key": shared_key, "cached_value": cached_inputs_value, "filtered_count": len(filtered_differing), "original_count": len(differing_widgets)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
                    except: pass
                    # #endregion
            
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:768", "message": "Selecting widget to sync", "data": {"shared_key": shared_key, "inputs_differing": inputs_differing, "all_differing": differing_widgets, "cached_inputs_value": cached_inputs_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
            except: pass
            # #endregion
            
            if inputs_differing:
                widget_key, widget_value = inputs_differing[0]
                # Cache inputs_* widget values so we can restore them later if Streamlit drops the widget key
                if widget_key.startswith("inputs_"):
                    st.session_state[f"_cached_{widget_key}"] = widget_value
            elif differing_widgets:
                widget_key, widget_value = differing_widgets[0]
            else:
                # All differing widgets were filtered out - skip sync
                continue
            old_shared_value = current_shared
            # CRITICAL: Log when we're about to overwrite a meaningful shared value with 0
            # BUT allow 0 for zero-allowed keys
            widget_is_zero = widget_value in (0, 0.0)
            shared_is_meaningful = old_shared_value not in (None, "", 0, 0.0)
            if shared_is_meaningful and widget_is_zero and shared_key in PROTECTED_FROM_ZERO_SHARED_KEYS and not zero_allowed(shared_key):
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"location": "state_and_helpers.py:sync_write", "message": "WARNING: About to overwrite meaningful shared with zero", "data": {"widget_key": widget_key, "shared_key": shared_key, "old_shared": old_shared_value, "new_widget_value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "O"}) + "\n")
                except: pass
                # #endregion
            set_shared(shared_key, widget_value, source="sync_update")
            
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "state_and_helpers.py:sync", "message": "Wrote to shared key", "data": {"widget_key": widget_key, "shared_key": shared_key, "old_value": old_shared_value, "new_value": widget_value}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
            except: pass
            # #endregion
            
            # --- MINIMAL FIX: If a bending_* reinforcement widget updates a shared key,
            # also update the cached inputs_* value for the same shared key.
            # Otherwise the cached inputs_* value blocks bending_* changes on the next navigation.
            BENDING_REO_SHARED_KEYS = {
                "nb_or_s_bot_1", "db_bot_1", "nb_or_s_bot_2", "db_bot_2",
                "nb_or_s_top_1", "db_top_1", "nb_or_s_top_2", "db_top_2",
                "rowgap_bot", "rowgap_top", "cover_bot", "cover_top",
            }
            
            if widget_key.startswith("bending_") and shared_key in BENDING_REO_SHARED_KEYS:
                for wk, sk in TAB_KEYS.items():
                    if sk == shared_key and wk.startswith("inputs_"):
                        st.session_state[f"_cached_{wk}"] = widget_value
            
            # #region agent log
            sync_operations.append((widget_key, shared_key, widget_value, "update", old_shared_value))
            # #endregion
        # else: all widgets match shared value, no sync needed
    
    # #region agent log
    if sync_operations:
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "state_and_helpers.py:688", "message": "sync_shared_from_widgets sync operations", "data": {"sync_count": len(sync_operations), "sample_syncs": sync_operations[:5]}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
        except: pass
    
    # Summary log - track widget values after sync completes
    sample_widgets = ["inputs_b", "inputs_D", "inputs_fc", "inputs_fsy", "bending_nb_or_s_bot_1", "shear_lig_d"]
    widget_values_at_sync_end = {k: st.session_state.get(k) for k in sample_widgets if k in st.session_state}
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"location": "state_and_helpers.py:sync_exit", "message": "Sync function exit", "data": {"widget_values": widget_values_at_sync_end, "sync_operations_count": len(sync_operations)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "F"}) + "\n")
    except: pass
    # #endregion
    if skip_shear_widget_backflow_once:
        st.session_state.pop("_skip_shear_widget_backflow_once", None)
        if skip_shear_widget_backflow_runs > 0:
            st.session_state["_skip_shear_widget_backflow_runs"] = max(
                0,
                skip_shear_widget_backflow_runs - 1,
            )


def recalc_derived_values():
    """
    Update derived geometry/reo values in session_state based on the
    current shared inputs (b, D, covers, bar sizes, etc.).
    RULE 3: This is the ONLY place derived values are written.
    
    Now handles 2-layer reinforcement system with auto-splitting.
    """
    from section_layout import compute_bar_layout_pure, compute_section_layout
    _sync_longitudinal_row_model_from_legacy_state()
    
    # Keep legacy layer keys mirrored from the canonical row model for compatibility.
    for section, legacy_prefix, default_dia in (("bot", "bot", 20.0), ("top", "top", 16.0)):
        for row_index in (1, 2):
            row_mode_key = f"{section}_row_{row_index}_mode"
            row_bars_key = f"{section}_row_{row_index}_bars"
            row_spacing_key = f"{section}_row_{row_index}_spacing"
            row_dia_key = f"{section}_row_{row_index}_dia"
            st.session_state[f"{legacy_prefix}{row_index}_layout_mode"] = st.session_state.get(row_mode_key, "Count")
            st.session_state[f"{legacy_prefix}{row_index}_count"] = int(st.session_state.get(row_bars_key, 0) or 0)
            st.session_state[f"{legacy_prefix}{row_index}_spacing"] = float(st.session_state.get(row_spacing_key, 200.0) or 200.0)
            st.session_state[f"db_{legacy_prefix}_{row_index}"] = float(st.session_state.get(row_dia_key, default_dia) or default_dia)

    # Bridge explicit layout mode inputs back to legacy nb_or_s_* keys
    def _mode_value(mode_key, count_key, spacing_key, fallback):
        mode = st.session_state.get(mode_key, "Count")
        if mode == "Spacing":
            return float(st.session_state.get(spacing_key, fallback))
        return float(st.session_state.get(count_key, fallback))
    
    # Bridge into legacy nb_or_s_* keys used elsewhere
    st.session_state["nb_or_s_bot_1"] = _mode_value("bot_row_1_mode", "bot_row_1_bars", "bot_row_1_spacing", 4)
    st.session_state["nb_or_s_bot_2"] = _mode_value("bot_row_2_mode", "bot_row_2_bars", "bot_row_2_spacing", 0)
    st.session_state["nb_or_s_top_1"] = _mode_value("top_row_1_mode", "top_row_1_bars", "top_row_1_spacing", 2)
    st.session_state["nb_or_s_top_2"] = _mode_value("top_row_2_mode", "top_row_2_bars", "top_row_2_spacing", 0)
    
    # Canonical material derivations/defaults.
    fc_val = float(st.session_state.get("fc", 40.0) or 40.0)
    Ec_derived = derive_concrete_modulus_from_fc(fc_val)
    phi_cc_t = float(st.session_state.get("phi_cc_t", 2.0) or 0.0)
    Eceff_derived = derive_effective_concrete_modulus(Ec_derived, phi_cc_t)
    # Steel modulus is treated as an internal default (not user-editable).
    st.session_state["Es"] = 200000.0
    st.session_state["Ec"] = float(Ec_derived)
    st.session_state["Eceff"] = float(Eceff_derived)

    # Retire legacy editable modulus widget keys so they cannot override derived/default values.
    for _legacy_modulus_widget in (
        "inputs_Ec", "bending_Ec", "shear_Ec", "crack_Ec", "defl_Ec",
        "inputs_Es", "bending_Es", "shear_Es", "crack_Es",
        "inputs_stress_ratio", "cr_sigma_ratio",
    ):
        st.session_state.pop(_legacy_modulus_widget, None)
    D = st.session_state["D"]
    cover_bot = st.session_state["cover_bot"]
    cover_top = st.session_state["cover_top"]
    
    # Get cover_side, with fallback to min of cover_top/cover_bot
    cover_side = st.session_state.get("cover_side", min(
        st.session_state.get("cover_top", 40.0),
        st.session_state.get("cover_bot", 40.0),
    ))

    b = st.session_state.get("b", 0.0)
    sec_shape = st.session_state.get("sec_shape", "RECT")
    if sec_shape == "T":
        st.session_state["b"] = float(st.session_state.get("bw", st.session_state.get("b", 400.0)))
        b = st.session_state["b"]
    elif sec_shape == "I":
        st.session_state["b"] = float(st.session_state.get("tw", st.session_state.get("b", 400.0)))
        b = st.session_state["b"]
    rowgap_bot = st.session_state.get("rowgap_bot", 60.0)
    rowgap_top = st.session_state.get("rowgap_top", 60.0)
    # --- Shape-aware derived geometry (shared source of truth) ---
    from section_props.shapes import compute_section_properties

    bf = st.session_state.get("bf", 0.0)
    tf = st.session_state.get("tf", 0.0)
    bw = st.session_state.get("bw", 0.0)
    tw = st.session_state.get("tw", 0.0)

    def _dims_ok(vals):
        try:
            return all(float(v) > 0.0 for v in vals)
        except Exception:
            return False

    shape_name = "Rectangle (b × D)"
    dims = {"b": float(b), "D": float(D)}
    if sec_shape == "T" and _dims_ok([bf, tf, bw, D]):
        shape_name = "T-Section"
        dims = {"bf": float(bf), "tf": float(tf), "bw": float(bw), "D": float(D)}
    elif sec_shape == "I" and _dims_ok([bf, tf, tw, D]):
        shape_name = "I-Section"
        dims = {"bf": float(bf), "tf": float(tf), "tw": float(tw), "D": float(D)}

    # Guard: if any required dims missing/0, fall back to rectangle approximation
    if shape_name != "Rectangle (b × D)" and not _dims_ok(list(dims.values())):
        shape_name = "Rectangle (b × D)"
        dims = {"b": float(b), "D": float(D)}

    try:
        props = compute_section_properties(shape_name, dims)
    except Exception:
        props = compute_section_properties("Rectangle (b × D)", {"b": float(b), "D": float(D)})

    A_g = float(props.get("A", 0.0))
    ybar_top_g = float(props.get("ybar_top", 0.0))
    Ixx_g = float(props.get("Ixx", 0.0))
    Ztop_g = float(props.get("Ztop", 0.0))
    Zbot_g = float(props.get("Zbot", 0.0))

    if sec_shape == "T":
        b_web = float(bw) if bw else float(b)
        defl_beff = float(bf) if bf else float(b)
    elif sec_shape == "I":
        b_web = float(tw) if tw else float(b)
        defl_beff = float(bf) if bf else float(b)
    else:
        b_web = float(b)
        defl_beff = float(b)

    st.session_state["A_g"] = A_g
    st.session_state["ybar_top_g"] = ybar_top_g
    st.session_state["Ixx_g"] = Ixx_g
    st.session_state["Ztop_g"] = Ztop_g
    st.session_state["Zbot_g"] = Zbot_g
    st.session_state["b_web"] = b_web
    st.session_state["b_crack"] = b_web
    st.session_state["A_ct_default"] = 0.5 * A_g

    defl_override = bool(st.session_state.get("defl_dims_user_override", False))
    if not defl_override:
        st.session_state["defl_bw"] = b_web
        st.session_state["defl_beff"] = defl_beff

    # --- Derived: effective span for deflection ---
    L_val = st.session_state.get("L")
    if L_val is not None:
        st.session_state["defl_L_eff"] = float(L_val) / 1000.0
    
    # Minimum spacing (AS 3600 typical: max(bar_dia, 25mm) for clear spacing)
    # We'll use a conservative default
    s_min_default = 25.0  # mm minimum clear spacing
    
    # ---------- 3.1 Process 2-layer system for BOTTOM ----------
    # Get Layer 1 values
    nb_or_s_bot_1 = st.session_state.get("nb_or_s_bot_1", 4.0)
    db_bot_1 = st.session_state.get("db_bot_1", 20.0)
    
    # Get Layer 2 values (may be auto-updated)
    nb_or_s_bot_2 = st.session_state.get("nb_or_s_bot_2", 0.0)
    db_bot_2 = st.session_state.get("db_bot_2", db_bot_1)  # Default to Layer 1 diameter
    
    # Compute layout for Layer 1
    s_min_bot = max(db_bot_1, s_min_default)
    layout_bot_1 = compute_bar_layout_pure(
        b=b, cover_side=cover_side, nb_or_s=nb_or_s_bot_1,
        db=db_bot_1, s_min=s_min_bot, rowgap=rowgap_bot
    )
    
    # Auto-update Layer 2 if Layer 1 doesn't fit in single row
    bot_layer2_was_auto = False
    bot_layer2_was_manual = st.session_state.get("nb_or_s_bot_2", 0.0) > 0
    
    if layout_bot_1["auto_split"] and layout_bot_1["n_row2"] > 0:
        n_spill = layout_bot_1["n_row2"]

        bot_layer2_locked = st.session_state.get("_lock_reo_bot_layer2", False)

        if bot_layer2_locked:
            # User has explicitly controlled Layer 2 (including setting it to 0). Do not overwrite.
            st.session_state["_reo_msg_bot_layer2_overwritten"] = True
        else:
            # Layer 1 forced a split - auto-update Layer 2
            if bot_layer2_was_manual:
                st.session_state["_reo_msg_bot_layer2_overwritten"] = True
            else:
                st.session_state["_reo_msg_bot_auto_layer2"] = True

            st.session_state["nb_or_s_bot_2"] = float(n_spill)
            st.session_state["db_bot_2"] = db_bot_1
            nb_or_s_bot_2 = float(n_spill)
            db_bot_2 = db_bot_1
            bot_layer2_was_auto = True
    # Otherwise, Layer 2 remains as user-defined (or 0)
    
    # Track warnings from layout
    if layout_bot_1.get("warning"):
        st.session_state["_reo_warning_bot_1"] = layout_bot_1["warning"]
    if layout_bot_1.get("warning") and "cannot fit" in layout_bot_1["warning"].lower():
        st.session_state["_reo_error_bot_1"] = True
    
    # Compute layout for Layer 2 (if it has bars)
    layout_bot_2 = None
    if nb_or_s_bot_2 > 0:
        s_min_bot_2 = max(db_bot_2, s_min_default)
        layout_bot_2 = compute_bar_layout_pure(
            b=b, cover_side=cover_side, nb_or_s=nb_or_s_bot_2,
            db=db_bot_2, s_min=s_min_bot_2, rowgap=rowgap_bot
        )
    
    # Total bottom bars = Layer 1 + Layer 2
    n_bot_total = layout_bot_1["n_total"]
    if layout_bot_2:
        n_bot_total += layout_bot_2["n_total"]
    
    # ---------- 3.2 Process 2-layer system for TOP ----------
    # Get Layer 1 values - treat 0 as valid (no falsy fallbacks)
    nb_or_s_top_1_val = st.session_state.get("nb_or_s_top_1")
    nb_or_s_top_1 = float(nb_or_s_top_1_val) if nb_or_s_top_1_val is not None else 2.0
    db_top_1 = st.session_state.get("db_top_1", 16.0)
    
    # Get Layer 2 values (may be auto-updated)
    nb_or_s_top_2 = st.session_state.get("nb_or_s_top_2", 0.0)
    db_top_2 = st.session_state.get("db_top_2", db_top_1)  # Default to Layer 1 diameter
    
    # Compute layout for Layer 1
    s_min_top = max(db_top_1, s_min_default)
    layout_top_1 = compute_bar_layout_pure(
        b=b, cover_side=cover_side, nb_or_s=nb_or_s_top_1,
        db=db_top_1, s_min=s_min_top, rowgap=rowgap_top
    )
    
    # Auto-update Layer 2 if Layer 1 doesn't fit in single row
    top_layer2_was_auto = False
    top_layer2_was_manual = st.session_state.get("nb_or_s_top_2", 0.0) > 0
    
    if layout_top_1["auto_split"] and layout_top_1["n_row2"] > 0:
        n_spill = layout_top_1["n_row2"]

        top_layer2_locked = st.session_state.get("_lock_reo_top_layer2", False)

        if top_layer2_locked:
            # User has explicitly controlled Layer 2 (including setting it to 0). Do not overwrite.
            st.session_state["_reo_msg_top_layer2_overwritten"] = True
        else:
            # Layer 1 forced a split - auto-update Layer 2
            if top_layer2_was_manual:
                st.session_state["_reo_msg_top_layer2_overwritten"] = True
            else:
                st.session_state["_reo_msg_top_auto_layer2"] = True

            st.session_state["nb_or_s_top_2"] = float(n_spill)
            st.session_state["db_top_2"] = db_top_1
            nb_or_s_top_2 = float(n_spill)
            db_top_2 = db_top_1
            top_layer2_was_auto = True
    # Otherwise, Layer 2 remains as user-defined (or 0)
    
    # Track warnings from layout
    if layout_top_1.get("warning"):
        if "cannot fit" in layout_top_1["warning"].lower() or "invalid" in layout_top_1["warning"].lower():
            st.session_state["_reo_error_top_1"] = True
        elif "spacing" in layout_top_1["warning"].lower():
            st.session_state["_reo_warning_top_1"] = layout_top_1["warning"]
            st.session_state["_reo_s_min_top_1"] = layout_top_1.get("s_min", s_min_top)
    
    # Compute layout for Layer 2 (if it has bars)
    layout_top_2 = None
    if nb_or_s_top_2 > 0:
        s_min_top_2 = max(db_top_2, s_min_default)
        layout_top_2 = compute_bar_layout_pure(
            b=b, cover_side=cover_side, nb_or_s=nb_or_s_top_2,
            db=db_top_2, s_min=s_min_top_2, rowgap=rowgap_top
        )
    
    # Total top bars = Layer 1 + Layer 2
    n_top_total = layout_top_1["n_total"]
    if layout_top_2:
        n_top_total += layout_top_2["n_total"]
    
    # ---------- 3.3 Write back legacy derived values (for backward compatibility) ----------
    st.session_state["nb_bot"] = n_bot_total
    st.session_state["nb_top"] = n_top_total
    st.session_state["db_bot"] = db_bot_1  # Use Layer 1 diameter as primary
    st.session_state["db_top"] = db_top_1  # Use Layer 1 diameter as primary
    
    # Legacy spacing values
    st.session_state["s_bot"] = layout_bot_1.get("s_actual", 200.0)
    st.session_state["s_top"] = layout_top_1.get("s_actual", 200.0)
    
    # Legacy bot_entry/top_entry for migration
    st.session_state["bot_entry"] = nb_or_s_bot_1
    st.session_state["top_entry"] = nb_or_s_top_1

    # Store modes in derived (if you have a derived dict, otherwise skip)
    # For now we'll skip since the current code doesn't use a separate derived dict

    # ---------- 3.2 Duct summary (results, not derived) ----------
    n_ducts = _coalesce_num(st.session_state.get("n_ducts", 0.0), 0.0)
    duct_dia = _coalesce_num(st.session_state.get("duct_dia", 0.0), 0.0)

    if n_ducts > 0.0 and duct_dia > 0.0:
        sum_duct = n_ducts * duct_dia               # mm
        A_duct_total = n_ducts * math.pi * duct_dia**2 / 4.0  # mm²
    else:
        sum_duct = 0.0
        A_duct_total = 0.0

    update_results(sum_duct=sum_duct, A_duct_total=A_duct_total)

    # ---------- 3.3 Time-dependent inputs ----------
    t_creep = _coalesce_num(st.session_state.get("t_creep", 365.0), 365.0)
    age_at_loading = _coalesce_num(st.session_state.get("age_at_loading", 28.0), 28.0)
    t_shrink = _coalesce_num(st.session_state.get("t_shrink", 365.0), 365.0)

    st.session_state["t_creep"] = t_creep
    st.session_state["age_at_loading"] = age_at_loading
    st.session_state["t_shrink"] = t_shrink

    # ---------- 3.3 Signed manual moment bridge ----------
    for prefix in ("uls", "sls"):
        signed_key = f"{prefix}_Mstar"
        pos_key = f"{prefix}_Mstar_pos_manual"
        neg_key = f"{prefix}_Mstar_neg_manual"
        signed_val = float(st.session_state.get(signed_key, 0.0) or 0.0)
        pos_val = float(st.session_state.get(pos_key, max(0.0, signed_val)) or 0.0)
        neg_val = float(st.session_state.get(neg_key, max(0.0, -signed_val)) or 0.0)
        pos_val = max(0.0, pos_val)
        neg_val = max(0.0, neg_val)
        # Aggregated widgets (e.g. inputs_Mu_star / bending_Mu_star → uls_Mstar) set net M* via
        # set_shared while pos/neg manual keys can still be 0. Without this, pos/neg collapse net to 0.
        if pos_val == 0.0 and neg_val == 0.0 and abs(signed_val) > 0.0:
            pos_val = max(0.0, signed_val)
            neg_val = max(0.0, -signed_val)
        st.session_state[pos_key] = pos_val
        st.session_state[neg_key] = neg_val
        st.session_state[signed_key] = float(pos_val - neg_val)

    st.session_state["Mu_star_pos_manual"] = float(st.session_state.get("uls_Mstar_pos_manual", 0.0) or 0.0)
    st.session_state["Mu_star_neg_manual"] = float(st.session_state.get("uls_Mstar_neg_manual", 0.0) or 0.0)
    st.session_state["Mu_star_manual"] = float(
        (st.session_state.get("Mu_star_pos_manual", 0.0) or 0.0)
        - (st.session_state.get("Mu_star_neg_manual", 0.0) or 0.0)
    )

    # ---------- 3.4 Actions wiring (ULS vs SLS) ----------
    actions = resolve_design_actions()
    actions_source = st.session_state.get("actions_source", "")
    uls_M = float(actions["Mu"])
    uls_V = float(actions["Vu"])
    uls_N = float(actions["Nu"])

    sls_M = float(actions["SLS_M"])
    sls_V = float(actions["SLS_V"])
    sls_N = float(st.session_state.get("sls_Nstar", 0.0) or 0.0)

    actions_uls = {"N": uls_N, "V": uls_V, "M": uls_M}
    actions_sls = {"N": sls_N, "V": sls_V, "M": sls_M}

    st.session_state["actions_uls"] = dict(actions_uls)
    st.session_state["actions_sls"] = dict(actions_sls)

    sustained = derive_sustained_stress_ratio(
        fc_mpa=float(st.session_state.get("fc", 0.0) or 0.0),
        sls_m_pos_kNm=float(actions.get("SLS_M_pos", 0.0) or 0.0),
        sls_m_neg_kNm=float(actions.get("SLS_M_neg", 0.0) or 0.0),
        z_top_mm3=float(st.session_state.get("Ztop_g", 0.0) or 0.0),
        z_bot_mm3=float(st.session_state.get("Zbot_g", 0.0) or 0.0),
    )
    st.session_state["sustained_Mstar_kNm"] = sustained["M_sust_kNm"]
    st.session_state["sustained_sigma_cs_mpa"] = sustained["sigma_cs_mpa"]
    st.session_state["sustained_section_modulus_mm3"] = sustained["Z_comp_mm3"]
    st.session_state["sustained_compression_fibre"] = sustained["compression_fibre"]
    st.session_state["stress_ratio"] = sustained["stress_ratio"]

    # --- DEBUG: Confirm ULS/SLS separation ---
    debug_print(
        "[DEBUG ACTION KEYS] ULS:",
        st.session_state.get("uls_Nstar"),
        st.session_state.get("uls_Vstar"),
        st.session_state.get("uls_Mstar"),
    )

    debug_print(
        "[DEBUG ACTION KEYS] SLS:",
        st.session_state.get("sls_Nstar"),
        st.session_state.get("sls_Vstar"),
        st.session_state.get("sls_Mstar"),
    )

    debug_print(
        "[DEBUG ACTION IDS]",
        "actions_uls id =", id(st.session_state.get("actions_uls")),
        "| actions_sls id =", id(st.session_state.get("actions_sls")),
    )
    # ----------------------------------------

    update_results(
        actions_bending=actions_uls,
        actions_shear=actions_uls,
        actions_crack=actions_sls,
        actions_deflection=actions_sls,
    )

    try:
        debug_print("[ACTIONS IDS]", id(st.session_state["actions_uls"]), id(st.session_state["actions_sls"]))
        if (
            st.session_state.get("uls_Mstar") == st.session_state.get("sls_Mstar")
            and (
                st.session_state.get("uls_Nstar") != 0
                or st.session_state.get("sls_Nstar") != 0
                or st.session_state.get("uls_Vstar") != 0
                or st.session_state.get("sls_Vstar") != 0
                or st.session_state.get("uls_Mstar") != 0
                or st.session_state.get("sls_Mstar") != 0
            )
        ):
            debug_print("[WARN] ULS and SLS actions are identical. Check mapping if unexpected.")
    except Exception:
        pass

    # Effective depths (canonical d includes cover-to-links + link dia + half bar dia)
    lig_d_for_d = float(st.session_state.get("lig_d", 0.0) or 0.0)
    st.session_state["d"] = effective_depth_with_links_mm(
        D_mm=D,
        cover_to_ligs_mm=cover_bot,
        lig_diameter_mm=lig_d_for_d,
        bar_diameter_mm=db_bot_1,
    )
    st.session_state["do"] = D - cover_top - db_top_1 / 2.0

    # Steel areas - sum both layers
    Ast_bot_1 = layout_bot_1["n_total"] * math.pi * db_bot_1**2 / 4.0
    Ast_bot_2 = layout_bot_2["n_total"] * math.pi * db_bot_2**2 / 4.0 if layout_bot_2 else 0.0
    Ast_bot_total = Ast_bot_1 + Ast_bot_2
    
    Ast_top_1 = layout_top_1["n_total"] * math.pi * db_top_1**2 / 4.0
    Ast_top_2 = layout_top_2["n_total"] * math.pi * db_top_2**2 / 4.0 if layout_top_2 else 0.0
    Ast_top_total = Ast_top_1 + Ast_top_2
    
    st.session_state["Ast_bot"] = Ast_bot_total
    st.session_state["Ast_top"] = Ast_top_total

    # Row-model derived outputs override the legacy 2-layer summary values so
    # downstream consumers can transition gradually without losing compatibility.
    section_layout = compute_section_layout()
    reo_layout = section_layout.get("reo_layout", {}) if isinstance(section_layout, dict) else {}
    try:
        from section_props.reo_layout import (
            resolve_longitudinal_bars_from_layout,
            analyze_resolved_longitudinal_bars,
            resolve_active_tension_reinforcement,
        )
        resolved_longitudinal_bars = resolve_longitudinal_bars_from_layout(
            shape_name=str(section_layout.get("shape_name", st.session_state.get("sec_shape", "RECT"))),
            dims=dict(section_layout.get("dims", {}) or {}),
            reo_layout=reo_layout if isinstance(reo_layout, dict) else {},
        )
    except Exception:
        resolved_longitudinal_bars = []
        analyze_resolved_longitudinal_bars = None
        resolve_active_tension_reinforcement = None
    resolved_longitudinal_warnings = []
    if isinstance(reo_layout, dict):
        resolved_longitudinal_warnings = list(reo_layout.get("warnings", []) or [])

    def _row_y_value(layer_data):
        y_val = layer_data.get("y", 0.0)
        if isinstance(y_val, (list, tuple)):
            return float(y_val[0]) if y_val else 0.0
        return float(y_val or 0.0)

    def _resolved_rows(layer_name: str) -> list[dict]:
        rows = []
        for idx, layer_data in enumerate(reo_layout.get(layer_name, []) or [], start=1):
            xs = [float(x) for x in (layer_data.get("x") or [])]
            db = float(layer_data.get("db", 0.0) or 0.0)
            y = _row_y_value(layer_data)
            spacing_actual = float(layer_data.get("spacing_actual", 0.0) or 0.0)
            row_index = int(layer_data.get("row_index", idx) or idx)
            rows.append({
                "active": len(xs) > 0 and db > 0.0,
                "row_index": row_index,
                "mode": layer_data.get("mode", "Count"),
                "dia": db,
                "bar_count_resolved": len(xs),
                "spacing_resolved": spacing_actual,
                "x_positions": xs,
                "y_position": y,
                "steel_area_row": float(layer_data.get("steel_area", len(xs) * math.pi * db**2 / 4.0) or 0.0),
                "fit_ok": bool(layer_data.get("fit_ok", True)),
                "warning": layer_data.get("warning"),
            })
        return rows

    bot_rows_resolved = _resolved_rows("bottom")
    top_rows_resolved = _resolved_rows("top")
    bot_bar_coords = [
        {"x": x, "y": row["y_position"], "db": row["dia"], "row_index": row["row_index"]}
        for row in bot_rows_resolved
        for x in row["x_positions"]
    ]
    top_bar_coords = [
        {"x": x, "y": row["y_position"], "db": row["dia"], "row_index": row["row_index"]}
        for row in top_rows_resolved
        for x in row["x_positions"]
    ]

    total_bot_bars = sum(row["bar_count_resolved"] for row in bot_rows_resolved)
    total_top_bars = sum(row["bar_count_resolved"] for row in top_rows_resolved)
    primary_bot_row = next((row for row in bot_rows_resolved if row["active"]), None)
    primary_top_row = next((row for row in top_rows_resolved if row["active"]), None)

    st.session_state["bot_rows_resolved"] = bot_rows_resolved
    st.session_state["top_rows_resolved"] = top_rows_resolved
    st.session_state["bot_bar_coords"] = bot_bar_coords
    st.session_state["top_bar_coords"] = top_bar_coords
    st.session_state["resolved_longitudinal_bars"] = resolved_longitudinal_bars
    st.session_state["resolved_longitudinal_warnings"] = resolved_longitudinal_warnings
    st.session_state["total_bot_bars"] = total_bot_bars
    st.session_state["total_top_bars"] = total_top_bars
    st.session_state["nb_bot"] = total_bot_bars
    st.session_state["nb_top"] = total_top_bars
    st.session_state["db_bot"] = float(primary_bot_row["dia"]) if primary_bot_row else 0.0
    st.session_state["db_top"] = float(primary_top_row["dia"]) if primary_top_row else 0.0
    st.session_state["s_bot"] = float(primary_bot_row["spacing_resolved"]) if primary_bot_row else 0.0
    st.session_state["s_top"] = float(primary_top_row["spacing_resolved"]) if primary_top_row else 0.0
    st.session_state["bot_entry"] = float(primary_bot_row["bar_count_resolved"]) if primary_bot_row and primary_bot_row.get("mode") == "Count" else float(primary_bot_row["spacing_resolved"]) if primary_bot_row else 0.0
    st.session_state["top_entry"] = float(primary_top_row["bar_count_resolved"]) if primary_top_row and primary_top_row.get("mode") == "Count" else float(primary_top_row["spacing_resolved"]) if primary_top_row else 0.0
    lig_d_for_d = float(st.session_state.get("lig_d", 0.0) or 0.0)
    primary_bar_dia = (
        float(primary_bot_row["dia"])
        if primary_bot_row
        else float(st.session_state.get("db_bot_1", 0.0) or 0.0)
    )
    # Bending effective depth is measured to the area-weighted centroid of
    # every active tension row.  Using only the outer row made the detailed
    # Bending page overstate capacity whenever a second row was present, while
    # the installed V2 calculator correctly used the complete arrangement.
    bottom_row_area = sum(
        float(row.get("steel_area_row", 0.0) or 0.0)
        for row in bot_rows_resolved
        if row.get("active")
    )
    if bottom_row_area > 0.0:
        bottom_centroid_from_top_face = sum(
            float(row.get("steel_area_row", 0.0) or 0.0)
            * float(row.get("y_position", 0.0) or 0.0)
            for row in bot_rows_resolved
            if row.get("active")
        ) / bottom_row_area
        # Section-layout y coordinates are measured from the top face, which
        # is also the compression-face datum for positive bending.
        st.session_state["d"] = max(0.0, bottom_centroid_from_top_face)
    else:
        st.session_state["d"] = effective_depth_with_links_mm(
            D_mm=D,
            cover_to_ligs_mm=cover_bot,
            lig_diameter_mm=lig_d_for_d,
            bar_diameter_mm=primary_bar_dia,
        )
    st.session_state["do"] = float(primary_top_row["y_position"]) if primary_top_row else D
    if st.session_state.get("_dev_mode", False):
        st.session_state["_debug_d_consistency"] = {
            "formula": "d = D - area_weighted_bottom_reinforcement_centroid",
            "D_mm": float(D),
            "cover_to_ligs_mm": float(cover_bot),
            "lig_diameter_mm": float(lig_d_for_d),
            "bar_diameter_mm": float(primary_bar_dia),
            "ui_display_d_mm": float(st.session_state.get("d", 0.0) or 0.0),
        }
    # Canonical reinforcement summaries must come from resolved_longitudinal_bars.
    # NOTE: Ast_top/Ast_bot are compatibility summaries only; zone-aware checks must
    # consume resolved_longitudinal_bars (crack/shear active participation helpers).
    top_bars = [bar for bar in resolved_longitudinal_bars if str(bar.get("face")) == "top"]
    bottom_bars = [bar for bar in resolved_longitudinal_bars if str(bar.get("face")) == "bottom"]
    top_web_bars = [bar for bar in top_bars if "web" in str(bar.get("zone", ""))]
    top_flange_bars = [bar for bar in top_bars if "flange" in str(bar.get("zone", ""))]
    bottom_web_bars = [bar for bar in bottom_bars if "web" in str(bar.get("zone", ""))]
    bottom_flange_bars = [bar for bar in bottom_bars if "flange" in str(bar.get("zone", ""))]

    st.session_state["Ast_top_web"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in top_web_bars))
    st.session_state["Ast_top_flange"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in top_flange_bars))
    st.session_state["Ast_bottom_web"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in bottom_web_bars))
    st.session_state["Ast_bottom_flange"] = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in bottom_flange_bars))
    st.session_state["Ast_top"] = float(st.session_state["Ast_top_web"] + st.session_state["Ast_top_flange"])
    st.session_state["Ast_bot"] = float(st.session_state["Ast_bottom_web"] + st.session_state["Ast_bottom_flange"])

    # Keep legacy representative diameters based on resolved bars (compatibility only).
    st.session_state["db_top"] = max((float(bar.get("dia_mm", 0.0) or 0.0) for bar in top_bars), default=0.0)
    st.session_state["db_bot"] = max((float(bar.get("dia_mm", 0.0) or 0.0) for bar in bottom_bars), default=0.0)

    def _avg_spacing(bars_list: list[dict]) -> float:
        xs = sorted(float(bar.get("x_mm", 0.0) or 0.0) for bar in bars_list)
        if len(xs) < 2:
            return 0.0
        vals = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        return float(sum(vals) / len(vals)) if vals else 0.0

    st.session_state["s_top"] = _avg_spacing(top_bars)
    st.session_state["s_bot"] = _avg_spacing(bottom_bars)

    if st.session_state.get("_dev_mode", False):
        shape_for_diag = str(section_layout.get("shape_name", st.session_state.get("sec_shape", "RECT")))
        dims_for_diag = dict(section_layout.get("dims", {}) or {})
        diag = {
            "section_shape": shape_for_diag,
            "resolved_bar_count": len(resolved_longitudinal_bars),
            "Ast_top_web": st.session_state["Ast_top_web"],
            "Ast_top_flange": st.session_state["Ast_top_flange"],
            "Ast_bottom_web": st.session_state["Ast_bottom_web"],
            "Ast_bottom_flange": st.session_state["Ast_bottom_flange"],
        }
        if analyze_resolved_longitudinal_bars is not None:
            bar_diag = analyze_resolved_longitudinal_bars(
                shape_name=shape_for_diag,
                dims=dims_for_diag,
                bars=resolved_longitudinal_bars,
            )
            diag["bar_diagnostics"] = bar_diag
            if bar_diag.get("warnings"):
                resolved_longitudinal_warnings.extend(list(bar_diag.get("warnings") or []))
        try:
            actions_now = resolve_design_actions()
            sign = "negative" if float(actions_now.get("Mu_signed", 0.0) or 0.0) < 0.0 else "positive"
            if resolve_active_tension_reinforcement is not None:
                active = resolve_active_tension_reinforcement(
                    dims_for_diag,
                    resolved_longitudinal_bars,
                    sign,
                )
                active_ids = [str(b.get("id")) for b in (active.get("active_bars") or [])]
                active_web_ast = float(sum(float(b.get("area_mm2", 0.0) or 0.0) for b in (active.get("active_web_bars") or [])))
                active_flange_ast = float(sum(float(b.get("area_mm2", 0.0) or 0.0) for b in (active.get("active_flange_bars") or [])))
                diag["crack_active_selection"] = {
                    "moment_sign": sign,
                    "tension_face": active.get("tension_face"),
                    "active_ids": active_ids,
                    "active_web_ast_mm2": active_web_ast,
                    "active_flange_ast_mm2": active_flange_ast,
                }
                diag["shear_active_selection"] = {
                    "available_active_ids": active_ids,
                    "available_web_ast_mm2": active_web_ast,
                    "available_flange_ast_mm2": active_flange_ast,
                }
        except Exception:
            pass
        st.session_state["_debug_reo_resolution"] = diag
    # ---------- 3.4 Compute effective design load F_d,ef from V, L, support type (Manual inputs only) ----------
    actions_source = st.session_state.get("actions_source", "")
    if actions_source == "Manual design actions (inputs below)":
        # Get design shear V (kN)
        V_kN = float(resolve_design_actions().get("Vu", 0.0) or 0.0)
        
        # Get span L (m) - prefer defl_L_eff, fallback to span_L_m
        L_m = st.session_state.get("defl_L_eff", 0.0)
        if L_m is None or L_m <= 0:
            L_m = st.session_state.get("span_L_m", 0.0)
            if L_m is None:
                L_m = 0.0
        
        from deflection_support import get_resolved_deflection_support_type

        support_type = get_resolved_deflection_support_type(st.session_state)

        # Compute equivalent UDL w (kN/m) based on support type
        w_kNm = None
        if L_m > 0 and V_kN > 0:
            if support_type == "Simply supported":
                # For simply supported beam with UDL: V_max = wL/2, so w = 2V/L
                w_kNm = 2.0 * V_kN / L_m
            elif support_type == "Cantilever":
                # For cantilever with UDL: V_max = wL, so w = V/L
                w_kNm = V_kN / L_m
            else:
                # Continuous / fixed-ended / interior: use V/L approximation (matches deflection_core F_d,ef path)
                w_kNm = V_kN / L_m
        
        # Store computed value (use update_results to maintain contract)
        if w_kNm is not None:
            update_results(fd_ef_calc_kNm=w_kNm)
        else:
            update_results(fd_ef_calc_kNm=0.0)
    else:
        # Not in manual mode - clear computed value
        update_results(fd_ef_calc_kNm=0.0)

    # Sectional shear adequacy from last published results (same rule as Check 10 / shear_core: φVu ≥ V*eq).
    # Layout + shear_design_status are pushed via update_results() from shear_core._compute_shear_capacity().
    shear_ok = None
    try:
        _veq = float(st.session_state.get("V_eq_kN", 0.0) or 0.0)
        _pvu = float(st.session_state.get("phi_Vu_cap", 0.0) or 0.0)
        if _veq > 0:
            shear_ok = bool(_pvu + 1e-9 >= _veq)
    except Exception:
        shear_ok = None
    _ = shear_ok  # mirrors φVu ≥ V*eq; authoritative status for UI is shear_design_status via update_results

    # --- Shape audit (debug snapshot, non-spammy) ---
    st.session_state["_shape_audit"] = {
        "sec_shape": st.session_state.get("sec_shape"),
        "A_g": st.session_state.get("A_g"),
        "Ixx_g": st.session_state.get("Ixx_g"),
        "b_web": st.session_state.get("b_web"),
        "defl_bw": st.session_state.get("defl_bw"),
        "defl_beff": st.session_state.get("defl_beff"),
    }


def reset_results_state():
    """Reset derived outputs to defaults (safe, does not touch inputs)."""
    for k, v in RESULT_DEFAULTS.items():
        st.session_state[k] = v


# ============================================
# 4. SYNC CALLBACKS
# ============================================

# Shared keys that must ONLY be written by INPUTS page widgets (inputs_* keys)
# Keep this list *small* and limited to "Inputs owns this" selectors.
# Shared keys that must remain Inputs-owned (avoid accidental overwrite during restore)
# Keep this list SMALL (only mode selectors / time-dependent inputs).
PROTECTED_SHARED_KEYS = {
    "t_creep", "age_at_loading", "t_shrink",
    "actions_source",
    "loads_edit_mode",
}

_SYNC_CALLBACKS = None  # module-global

from inputs_application.workspace_rerun_policy import (
    DISPLAY_LOCAL_WIDGET_KEYS as _INPUTS_FRAGMENT_LOCAL_WIDGET_KEYS,
    InputsWidgetRerunClass as _InputsWidgetRerunClass,
    classify_inputs_widget as _classify_inputs_widget,
    request_inputs_workspace_refresh,
)


def _is_beam_project_widget_commit(widget_key: str, shared_key: str | None = None) -> bool:
    """Return whether a mapped page widget owns a persisted beam input."""

    resolved_widget_key = str(widget_key or "").strip()
    resolved_shared_key = str(
        shared_key if shared_key is not None else TAB_KEYS.get(resolved_widget_key, "")
    ).strip()
    return bool(
        resolved_widget_key
        and resolved_shared_key
        and resolved_shared_key in BEAM_PROJECT_PARAM_KEYS
    )


def _synchronize_beam_input_projections_for_commit() -> tuple[str, ...]:
    """Refresh persisted, read-only projections before one input commit.

    ``BEAM_PROJECT_PARAM_KEYS`` contains a small number of values that are
    derived from editable canonical inputs because explicit calculation view
    models still consume them.  Committing the canonical edit first and
    deriving these values on the following render makes one user edit look
    like two input transactions.  Keep only these inexpensive projections in
    phase with their owners before the snapshot is captured.
    """

    updates: dict[str, object] = {}

    if "Ec" in BEAM_PROJECT_PARAM_KEYS:
        fc_value = float(st.session_state.get("fc", 40.0) or 40.0)
        updates["Ec"] = float(derive_concrete_modulus_from_fc(fc_value))

    if "defl_beff" in BEAM_PROJECT_PARAM_KEYS and not bool(
        st.session_state.get("defl_dims_user_override", False)
    ):
        section_shape = str(
            st.session_state.get("sec_shape", "RECT") or "RECT"
        ).strip().upper()
        section_width = float(st.session_state.get("b", 0.0) or 0.0)
        if section_shape in {"T", "I"}:
            effective_width = float(
                st.session_state.get("bf", section_width) or section_width
            )
        else:
            effective_width = section_width
        updates["defl_beff"] = effective_width

    changed: list[str] = []
    for key, value in updates.items():
        if st.session_state.get(key) != value:
            st.session_state[key] = value
            changed.append(key)
    return tuple(sorted(changed))


def _request_inputs_engineering_commit(
    widget_key: str,
    *,
    changed_keys: tuple[str, ...] | None = None,
    wake_fragments: bool = True,
):
    """Commit one beam-owned input revision for every downstream consumer."""
    commit_started_ns = time.perf_counter_ns()
    commit_timings_ms: dict[str, float] = {}
    explicit_changed_keys = tuple(
        sorted(str(key) for key in (changed_keys or ()) if str(key).strip())
    )
    resolved_widget_key = str(widget_key or "").strip()
    rerun_class = _classify_inputs_widget(resolved_widget_key)
    if rerun_class is _InputsWidgetRerunClass.DISPLAY_LOCAL:
        return None
    if not resolved_widget_key.startswith("inputs_") and not _is_beam_project_widget_commit(
        resolved_widget_key
    ):
        return None
    # An actual engineering edit ends any same-beam route-return lock.  The
    # lock otherwise remains across unchanged reruns so the legacy router
    # cannot re-commit a different baseline after navigation.
    route_guard = dict(
        st.session_state.get("_inputs_same_beam_return_guard") or {}
    )
    for key in (
        "_inputs_same_beam_return_active",
        "_inputs_same_beam_return_restored_keys",
    ):
        st.session_state.pop(key, None)
    resolved_changed_keys = explicit_changed_keys
    if not resolved_changed_keys:
        inferred = (
            str(TAB_KEYS.get(resolved_widget_key) or "").strip()
            or resolved_widget_key.removeprefix("inputs_")
        )
        resolved_changed_keys = (inferred,) if inferred else ()

    # Publish lightweight calculation projections on the same transaction as
    # their canonical owners. Otherwise the next render can manufacture a
    # second revision solely because a read-only projection caught up.
    stage_started_ns = time.perf_counter_ns()
    _synchronize_beam_input_projections_for_commit()
    commit_timings_ms["synchronize_projections"] = (
        time.perf_counter_ns() - stage_started_ns
    ) / 1_000_000

    # The row model is canonical. Publish its inexpensive compatibility aliases
    # before capturing the transaction so diagrams, legacy calculations, beam
    # persistence, and navigation all observe the same values and revision.
    stage_started_ns = time.perf_counter_ns()
    live_snapshot = get_beam_project_param_snapshot()
    legacy_mirrors = build_legacy_longitudinal_mirrors_from_rows(live_snapshot)
    for key, value in legacy_mirrors.items():
        if key in BEAM_PROJECT_PARAM_KEYS:
            st.session_state[key] = copy.deepcopy(value)
            live_snapshot[key] = copy.deepcopy(value)
    commit_timings_ms["build_canonical_snapshot"] = (
        time.perf_counter_ns() - stage_started_ns
    ) / 1_000_000

    # Fragment reruns can revisit a callback path after the canonical value
    # has already been committed.  Reusing the matching beam snapshot avoids
    # another persistence write and another sibling wake for a no-op event;
    # a real widget change still differs here and follows the normal commit
    # path below.  This is deliberately compared after projection/mirror
    # synchronisation so the canonical state remains the sole authority.
    from inputs_application.engineering_input_store import InputSnapshotStore

    active_beam_id = str(st.session_state.get("active_beam_id") or "").strip()
    if not active_beam_id:
        raise RuntimeError("Inputs engineering edit has no active beam")
    existing_snapshot = InputSnapshotStore(st.session_state).current_for_beam(
        active_beam_id
    )
    if (
        existing_snapshot.revision > 0
        and existing_snapshot.snapshot == live_snapshot
    ):
        st.session_state["_inputs_last_commit_timings_ms"] = {
            "revision": int(existing_snapshot.revision),
            "widget_key": resolved_widget_key,
            "no_op": True,
            "stages": {
                "synchronize_projections": round(
                    commit_timings_ms.get("synchronize_projections", 0.0), 3
                ),
                "build_canonical_snapshot": round(
                    commit_timings_ms.get("build_canonical_snapshot", 0.0), 3
                ),
                "total": round(
                    (time.perf_counter_ns() - commit_started_ns) / 1_000_000,
                    3,
                ),
            },
        }
        return existing_snapshot

    stage_started_ns = time.perf_counter_ns()
    persisted_record = persist_active_beam_from_shared()
    commit_timings_ms["persist_active_beam"] = (
        time.perf_counter_ns() - stage_started_ns
    ) / 1_000_000
    if isinstance(persisted_record, dict):
        persisted_params = persisted_record.get("params")
        if isinstance(persisted_params, dict):
            live_snapshot = copy.deepcopy(persisted_params)

    stage_started_ns = time.perf_counter_ns()
    committed = InputSnapshotStore(st.session_state).commit_active_beam(
        live_snapshot,
        changed_keys=resolved_changed_keys,
        source=(
            f"inputs_widget:{resolved_widget_key}"
            if resolved_widget_key.startswith("inputs_")
            else f"beam_widget:{resolved_widget_key}"
        ),
    )
    commit_timings_ms["commit_input_transaction"] = (
        time.perf_counter_ns() - stage_started_ns
    ) / 1_000_000
    # When an engineering result page was opened from Inputs, the router keeps
    # a route-return guard containing the Inputs snapshot from departure time.
    # An off-page edit must advance that guard to this new transaction; merely
    # clearing it is racy with Streamlit's URL-sync rerun and can let the old
    # snapshot be armed again before Inputs renders.
    if str(route_guard.get("beam_id") or "").strip() == active_beam_id:
        # ``InputSnapshotState.snapshot`` is recursively immutable and can
        # contain ``MappingProxyType`` values.  Route guards are a mutable
        # presentation/session boundary, so use the contract's defensive
        # serialization copy instead of trying to deepcopy the immutable
        # mapping (which is not pickleable).
        route_guard["committed_state"] = committed.to_dict()
        route_guard["source_input_revision"] = int(committed.revision)
        route_guard["authoritative_result"] = None
        st.session_state["_inputs_same_beam_return_guard"] = route_guard
    else:
        st.session_state.pop("_inputs_same_beam_return_guard", None)
    st.session_state["_inputs_authoritative_result_snapshot_update_pending"] = True
    st.session_state["_inputs_pending_input_revision"] = int(committed.revision)
    stage_started_ns = time.perf_counter_ns()
    request_inputs_workspace_refresh(
        st.session_state,
        resolved_widget_key,
        revision=committed.revision,
    )
    commit_timings_ms["request_workspace_refresh"] = (
        time.perf_counter_ns() - stage_started_ns
    ) / 1_000_000
    stage_started_ns = time.perf_counter_ns()
    persist_state_snapshot()
    commit_timings_ms["persist_session_snapshot"] = (
        time.perf_counter_ns() - stage_started_ns
    ) / 1_000_000
    commit_timings_ms["total"] = (
        time.perf_counter_ns() - commit_started_ns
    ) / 1_000_000
    st.session_state["_inputs_last_commit_timings_ms"] = {
        "revision": int(committed.revision),
        "widget_key": resolved_widget_key,
        "stages": {
            key: round(value, 3)
            for key, value in commit_timings_ms.items()
        },
    }
    # A widget callback executing inside the unified Inputs fragment already
    # schedules exactly one owning-fragment rerun.  Do not enqueue a second
    # framework wake: that duplicate state machine could render an interim
    # revision and made cold sessions flicker before settling.
    del wake_fragments
    return committed


def _engineering_widget_owner_slug(widget_key: str) -> str | None:
    """Return the page that is allowed to publish this widget callback."""

    key = str(widget_key or "").strip().lower()
    for prefix, owner in (
        ("inputs_", "inputs"),
        ("bending_", "bending"),
        ("shear_", "shear"),
        ("crack_", "crack"),
        ("defl_", "deflection"),
        ("cr_", "creep"),
        ("sh_", "shrinkage"),
        ("design_", "design"),
        ("load_", "design"),
        ("sfd_", "design"),
    ):
        if key.startswith(prefix):
            return owner
    return None


def _compose_sync_callback(widget_key: str, shared_key: str):
    assign_callback = _make_sync_callback(widget_key, shared_key)

    def _callback():
        selected_slug = str(
            st.session_state.get("nav_page_slug") or ""
        ).strip().lower()
        rendered_slug = str(
            st.session_state.get("page_slug")
            or st.session_state.get("_active_page_slug")
            or ""
        ).strip().lower()
        if selected_slug and rendered_slug and selected_slug != rendered_slug:
            # Streamlit runs widget callbacks before the navigation rerun. Old
            # widgets can therefore submit their browser-held values in the
            # same event batch as the page radio. The shell owns this event;
            # it is not an engineering edit and must not create a transaction.
            return
        widget_owner_slug = _engineering_widget_owner_slug(widget_key)
        shared_action_projection_on_result_page = bool(
            str(widget_key or "").startswith("inputs_load_")
            and rendered_slug in {"bending", "shear", "crack", "deflection"}
        )
        if (
            widget_owner_slug
            and rendered_slug
            and widget_owner_slug != rendered_slug
            and not shared_action_projection_on_result_page
        ):
            # Browser widget state can arrive one rerun after route selection.
            # Only the page that rendered the widget may publish its value.
            return
        mark_user_edit(widget_key, shared_key)
        assign_callback()
        # Display-only controls are already inside the Inputs workspace
        # fragment. Streamlit schedules that fragment rerun automatically
        # after the callback returns; explicitly calling st.rerun() here is a
        # no-op in callback context and surfaces a warning in the UI.
        if _classify_inputs_widget(widget_key) is _InputsWidgetRerunClass.DISPLAY_LOCAL:
            return
        commit_changed_keys = _synchronize_manual_design_action_proxy_for_commit(
            str(shared_key or "")
        )
        # Keep every engineering widget on the same commit boundary.  The
        # design-action callbacks already invalidate these caches; geometry,
        # materials, reinforcement, and detailing widgets use this shared
        # callback and must do the same before the next fragment render.
        if (
            _classify_inputs_widget(widget_key)
            is _InputsWidgetRerunClass.ENGINEERING_WORKSPACE
            or _is_beam_project_widget_commit(widget_key, shared_key)
        ):
            _invalidate_inputs_summary_packs(
                source="inputs_widget_sync",
                updated_keys=list(commit_changed_keys),
            )
            st.session_state["cached_results"] = None
            st.session_state["_cached_compute_results"] = None
            st.session_state["_last_compute_fp"] = None
            st.session_state["inputs_dirty"] = True
            st.session_state["_inputs_dirty"] = True
            st.session_state["run_design_clicked"] = True
            st.session_state.pop("pending_recommendation", None)
            st.session_state.pop("pending_recommendation_applied_id", None)
            st.session_state.pop("_solver_result", None)
        _request_inputs_engineering_commit(
            widget_key,
            changed_keys=commit_changed_keys,
        )
        # Streamlit schedules the owning rerun after an on_change callback
        # returns.  V2 commits the model and returns; an explicit st.rerun()
        # here would create a second full-page pass, causing the Inputs shell
        # and Design Brain card to flicker.  The committed transaction above is
        # the only wake-up required for both the direct V2-shaped path and the
        # legacy fragment rollback path.

    return _callback


def _make_sync_callback(widget_key: str, shared_key: str):
    """Minimal callback: widget key writes directly to shared key."""

    def _callback():
        if shared_key is None:
            return
        if widget_key not in st.session_state:
            return
        st.session_state[shared_key] = st.session_state[widget_key]

    return _callback


def get_sync_callbacks():
    """
    Return the dict {widget_key: callback} for use in on_change=...
    Ensures a single shared set of callbacks for the whole app.
    """
    global _SYNC_CALLBACKS

    # Rebuild if not yet created or if TAB_KEYS has changed (e.g. new widget keys added)
    if (
        _SYNC_CALLBACKS is None
        or len(_SYNC_CALLBACKS) != len(TAB_KEYS)
        or any(w_key not in _SYNC_CALLBACKS for w_key in TAB_KEYS.keys())
    ):
        _SYNC_CALLBACKS = {
            w_key: _compose_sync_callback(w_key, sh_key)
            for w_key, sh_key in TAB_KEYS.items()
        }
    
    # Debug-only: validate contract after building callbacks
    try:
        from src.debug.state_debug import is_debug_enabled
        if is_debug_enabled():
            validate_session_state_contract(context="inside get_sync_callbacks")
    except (ImportError, NameError):
        # Debug module not available, skip validation
        pass
    
    return _SYNC_CALLBACKS


def finalize_auto_design_publish(
    *,
    updated_keys: list[str],
    source: str,
    focus_section: str | None = None,
    set_run_design_clicked: bool = True,
) -> dict:
    """
    Central post-commit publication for already-applied shared updates.

    Shared writes must already be done before this helper is called.
    This helper owns:
    - summary/cache invalidation
    - pending Inputs refresh queue
    - one-shot shear widget reseed flag
    - dirty flags
    - standard auto-design invalidation markers
    - optional run_design_clicked
    """
    keys = sorted([str(k) for k in (updated_keys or []) if str(k)])
    shear_keys_updated = [k for k in keys if k in {"lig_d", "lig_legs", "s_lig"}]

    if shear_keys_updated:
        st.session_state["_force_inputs_shear_widget_reseed_once"] = True

    _invalidate_inputs_summary_packs(
        source=str(source or ""),
        updated_keys=keys,
    )
    _queue_inputs_refresh_from_auto_design(
        source=str(source or ""),
        updated_keys=keys,
    )
    # Every committed engineering update must reseed rendered Inputs widgets
    # from shared state on the next rerun.  The previous implementation only
    # reseeded the shear trio, allowing geometry widgets to retain old values
    # after Apply and making the diagram/summary disagree with the commit.
    if any(key in TAB_KEYS.values() for key in keys):
        st.session_state["_force_inputs_widget_reseed_once"] = True
    active_beam_id = st.session_state.get("active_beam_id")
    if active_beam_id:
        # The shared state has just been committed for this active beam. Keep
        # the normal beam-hydration guard from replaying the pre-commit record
        # over the freshly applied values on the immediate rerun.
        st.session_state["beam_last_hydrated_id"] = active_beam_id

    if focus_section:
        st.session_state["_fast_mode_focus_section"] = str(focus_section)

    st.session_state["inputs_dirty"] = True
    st.session_state["_inputs_dirty"] = True
    if set_run_design_clicked:
        st.session_state["run_design_clicked"] = True

    st.session_state["_force_auto_redesign"] = False
    st.session_state["_auto_design_invalidated"] = True
    st.session_state.pop("_auto_design_last_fingerprint", None)

    payload = {
        "source": str(source or ""),
        "updated_keys": keys,
        "shear_keys_updated": list(shear_keys_updated),
        "pending_inputs_apply_refresh": dict(st.session_state.get("_pending_inputs_apply_refresh") or {}),
        "inputs_summary_cache_invalidated": bool(st.session_state.get("_inputs_summary_cache_invalidated")),
        "inputs_summary_cache_invalidated_source": st.session_state.get("_inputs_summary_cache_invalidated_source"),
        "force_inputs_widget_reseed_once": bool(st.session_state.get("_force_inputs_widget_reseed_once")),
        "force_inputs_shear_widget_reseed_once": bool(st.session_state.get("_force_inputs_shear_widget_reseed_once")),
        "fast_mode_focus_section": st.session_state.get("_fast_mode_focus_section"),
        "active_beam_id": active_beam_id,
        "beam_last_hydrated_id": st.session_state.get("beam_last_hydrated_id"),
        "run_design_clicked": bool(st.session_state.get("run_design_clicked")),
        "shared_shear": {
            "s_lig": st.session_state.get("s_lig"),
            "lig_d": st.session_state.get("lig_d"),
            "lig_legs": st.session_state.get("lig_legs"),
        },
    }
    st.session_state["_finalize_auto_design_publish_latest"] = dict(payload)

    try:
        import session_state_final_log as _ssl

        _ssl.append_session_state_final_log("finalize_auto_design_publish", payload)
        _ssl.ssl_increment("finalize_auto_design_publish_count", 1)
    except Exception:
        pass

    return payload


def _invalidate_inputs_summary_packs(*, source: str, updated_keys: list[str] | None = None) -> None:
    payload = {
        "source": str(source or ""),
        "updated_keys": list(updated_keys or []),
    }
    for key in (
        "_bend_pack",
        "_shear_pack",
        "_crack_pack",
        "_defl_pack",
        "_summary_cache_version",
        "_summary_cache_action_fp",
    ):
        st.session_state.pop(key, None)
    st.session_state["_inputs_summary_cache_invalidated"] = True
    st.session_state["_inputs_summary_cache_invalidated_source"] = payload["source"]
    st.session_state["_inputs_summary_cache_invalidated_keys"] = payload["updated_keys"]

    try:
        import session_state_final_log as _ssl

        _ssl.append_session_state_final_log(
            "invalidate_inputs_summary_packs",
            payload,
        )
        _ssl.ssl_increment("invalidate_inputs_summary_packs_count", 1)
    except Exception:
        pass


def _queue_inputs_refresh_from_auto_design(*, source: str, updated_keys: list[str]) -> None:
    st.session_state["_pending_inputs_apply_refresh"] = {
        "source": str(source or "auto_design_apply"),
        "keys": list(updated_keys or []),
    }
    if any(k in {"lig_d", "lig_legs", "s_lig"} for k in (updated_keys or [])):
        st.session_state["_fast_mode_focus_section"] = "shear"

    try:
        import session_state_final_log as _ssl

        _ssl.append_session_state_final_log(
            "queue_inputs_refresh_from_auto_design",
            {
                "source": str(source or "auto_design_apply"),
                "keys": list(updated_keys or []),
            },
        )
        _ssl.ssl_increment("queue_inputs_refresh_from_auto_design_count", 1)
    except Exception:
        pass


# ============================================
# Health check logger (debug file only)
# ============================================

_RUNTIME_DIR = os.path.expanduser("~/Documents/GitHub/.blank_app_runtime")
os.makedirs(_RUNTIME_DIR, exist_ok=True)
_DEBUG_PATH = os.path.join(_RUNTIME_DIR, "health_check.jsonl")


def hc_log(tag: str, **data):
    rec = {"t": time.time(), "tag": tag, **data}
    with open(_DEBUG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def hc_try(tag: str, fn):
    try:
        out = fn()
        hc_log(tag, ok=True)
        return out
    except Exception as e:
        hc_log(tag, ok=False, err_type=type(e).__name__, err=str(e), trace=traceback.format_exc())
        return None


# ============================================
# 5. RESULT UPDATE HELPER (RULE 4)
# ============================================

def update_results(*args, **kwargs):
    """
    Safely update result values (phi_Mu_cap, Mu_utilisation, shrinkage,
    creep, crack summaries, etc.).

    Only accepts keys listed in RESULT_KEYS (computed outputs, not user inputs).
    For updating shared inputs, use widget callbacks or direct session_state writes
    (inputs are managed via TAB_KEYS and sync callbacks).
    """
    if args:
        if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], dict):
            raise TypeError("update_results(bucket: str, data: dict) expects (str, dict)")
        _store_results_bucket(args[0], args[1])
        return

    # Wrap with debug guard in debug mode
    try:
        from src.debug.state_debug import guard_session_writes, is_debug_enabled
        if is_debug_enabled():
            with guard_session_writes(allowed_keys=RESULT_KEYS, context="update_results"):
                _update_results_impl(**kwargs)
        else:
            _update_results_impl(**kwargs)
    except (ImportError, NameError):
        # Debug module not available, use normal path
        _update_results_impl(**kwargs)


def compute_all_results() -> None:
    """
    Compute ALL derived + result outputs in one place.
    This is the single source of truth for results freshness.

    RULES:
    - Derived values ONLY updated via recalc_derived_values()
    - Results ONLY published via update_results() (called inside core compute fns)
    """
    with speed_profile_section("derived_result_computation.compute_all_results", category="compute"):
        _section_t0 = time.perf_counter()
        compute_fp_payload = {
            **_shared_state_payload(),
            "actions_mode": st.session_state.get("actions_mode"),
            "actions_source": st.session_state.get("actions_source"),
            "design_actions_source": st.session_state.get("design_actions_source"),
            "load_Mstar_proxy": st.session_state.get("load_Mstar_proxy"),
            "load_Mstar_pos_proxy": st.session_state.get("load_Mstar_pos_proxy"),
            "load_Mstar_neg_proxy": st.session_state.get("load_Mstar_neg_proxy"),
            "load_Vstar_proxy": st.session_state.get("load_Vstar_proxy"),
            "Mu_star": st.session_state.get("Mu_star"),
            "Vu_star": st.session_state.get("Vu_star"),
            "N_star": st.session_state.get("N_star"),
        }
        compute_fp = stable_fingerprint_for_payload(compute_fp_payload)
        speed_profile_record(
            "derived_result_computation.compute_all_results.fingerprint_build",
            (time.perf_counter() - _section_t0) * 1000.0,
            category="compute",
        )
        _section_t0 = time.perf_counter()
        cached_bundle = get_rerun_pure_cache("compute_all_results_bundle", compute_fp)
        if isinstance(cached_bundle, dict):
            for k, v in dict(cached_bundle.get("derived", {}) or {}).items():
                st.session_state[k] = copy.deepcopy(v)
            for k, v in dict(cached_bundle.get("results", {}) or {}).items():
                st.session_state[k] = copy.deepcopy(v)
            for k, v in dict(cached_bundle.get("debug", {}) or {}).items():
                st.session_state[k] = copy.deepcopy(v)
            speed_profile_record(
                "derived_result_computation.compute_all_results.cache_hit",
                0.0,
                category="compute",
            )
            return
        speed_profile_record(
            "derived_result_computation.compute_all_results.cache_lookup",
            (time.perf_counter() - _section_t0) * 1000.0,
            category="compute",
        )

        # 1) Derived values (d, Ast, layouts, etc.)
        with speed_profile_section("derived_result_computation.recalc_derived_values", category="compute"):
            recalc_derived_values()

        # Beam M(x) / SFD arrays for Crack + design mode (headless; matches Beam Actions page)
        try:
            from beam_diagram_publish import publish_beam_diagram_arrays_from_session_state

            with speed_profile_section("derived_result_computation.publish_beam_diagram_arrays", category="compute"):
                publish_beam_diagram_arrays_from_session_state()
        except Exception:
            pass

        # 2) Core checks (ULS/SLS)
        # Prefer design-core modules (no UI / no render side-effects)
        try:
            from bending_core import _compute_bending_capacity
            with speed_profile_section("derived_result_computation.bending_capacity", category="compute"):
                _compute_bending_capacity()
        except Exception:
            pass

        try:
            from shear_core import _compute_shear_capacity
            with speed_profile_section("derived_result_computation.shear_capacity", category="compute"):
                _compute_shear_capacity()
        except Exception as exc:
            try:
                from shear_checks_helpers import resolve_shear_spacing_truth
                from shear_core import _normalise_final_shear_publication

                _existing_zone_payload = st.session_state.get("shear_zone_results")
                try:
                    _sip = float(st.session_state.get("s_lig") or 200.0)
                except (TypeError, ValueError):
                    _sip = 200.0
                _fail_s_end = (
                    float((_existing_zone_payload or {}).get("shear_spacing_end_mm", 0.0) or 0.0)
                    if isinstance(_existing_zone_payload, dict)
                    else None
                )
                _fail_req_mm = (
                    float(_fail_s_end) if _fail_s_end is not None and float(_fail_s_end) > 0.0 else None
                )
                _fail_eff_mm = float(_sip)
                _fail_truth = resolve_shear_spacing_truth(
                    provided_spacing_mm=float(_sip),
                    required_spacing_mm=_fail_req_mm,
                    effective_spacing_mm=_fail_eff_mm,
                )
                _gov_outer = str(_fail_truth.get("governing_spacing_source") or "")
                _nf_outer = _normalise_final_shear_publication(
                    shear_design_status_out="INVALID",
                    final_shear_status_source="canonical_skipped_global_shear_compute_error",
                    final_shear_truth_resolved=False,
                    final_shear_truth_failure_reason="global_shear_compute_error",
                    shear_util_governing_out=None,
                    canonical_pub=None,
                    zone_payload=_existing_zone_payload if isinstance(_existing_zone_payload, dict) else None,
                    session_state=st.session_state,
                    provided_mm=float(_sip),
                    required_mm=_fail_req_mm,
                    effective_mm=_fail_eff_mm,
                    governing_spacing_source=_gov_outer,
                )
                _outer_spacing_reason = str(_nf_outer.get("final_shear_spacing_reason") or "").strip()
                if not _outer_spacing_reason:
                    _outer_spacing_reason = (
                        "Global compute_all_results shear failure; spacing uses best-available session inputs."
                    )
                _outer_spacing_reason = (
                    f"{_outer_spacing_reason} Publication path: global_outer_invalid (_compute_shear_capacity exception)."
                )
                _nf_outer = {**_nf_outer, "final_shear_spacing_reason": _outer_spacing_reason}
                if isinstance(_existing_zone_payload, dict):
                    _existing_zone_payload = {
                        **_existing_zone_payload,
                        "final_shear_publication_path": "global_outer_invalid",
                        "final_shear_status_source": _nf_outer["final_shear_status_source"],
                        "final_shear_truth_resolved": _nf_outer["final_shear_truth_resolved"],
                        "final_shear_truth_failure_reason": _nf_outer["final_shear_truth_failure_reason"],
                        "published_result_spacing_mm": _nf_outer["published_result_spacing_mm"],
                        "published_result_spacing_meaning": _nf_outer["published_result_spacing_meaning"],
                        "final_shear_spacing_reason": _nf_outer["final_shear_spacing_reason"],
                    }
                _phi_cap = float(st.session_state.get("phi_Vu_cap") or 0.0)
                _veq = float(st.session_state.get("V_eq_kN") or st.session_state.get("V_eq") or 0.0)
                _vu_util = (_veq / _phi_cap) if _phi_cap > 0.0 else float("nan")

                update_results(
                    phi_Vu_cap=_phi_cap,
                    Vu_utilisation=_vu_util if not math.isnan(_vu_util) else 0.0,
                    phi_Vu_max_kN=float(st.session_state.get("phi_Vu_max_kN") or 0.0),
                    V_eq_kN=_veq,
                    shear_zone_results=_existing_zone_payload,
                    shear_design_status=_nf_outer["shear_design_status_out"],
                    shear_design_error=str(exc),
                    shear_x=st.session_state.get("shear_x", []),
                    shear_V=st.session_state.get("shear_V", []),
                    V_max=st.session_state.get("V_max", 0.0),
                    req_asv_s=st.session_state.get("req_asv_s", []),
                    prov_asv_s=st.session_state.get("prov_asv_s", []),
                    shear_util_min=st.session_state.get("shear_util_min", None),
                    shear_util_x=st.session_state.get("shear_util_x", None),
                    shear_envelope_status=st.session_state.get("shear_envelope_status", "FAIL"),
                    shear_k_v=float(st.session_state.get("shear_k_v") or 0.0),
                    shear_theta_v_deg=float(st.session_state.get("shear_theta_v_deg") or 0.0),
                    shear_theta_v_rad=float(st.session_state.get("shear_theta_v_rad") or 0.0),
                    shear_Vuc_kN=float(st.session_state.get("shear_Vuc_kN") or 0.0),
                    shear_Vus_kN=float(st.session_state.get("shear_Vus_kN") or 0.0),
                    shear_Vu_total_kN=float(st.session_state.get("shear_Vu_total_kN") or 0.0),
                    shear_spacing_end_mm=float(st.session_state.get("shear_spacing_end_mm") or 0.0),
                    shear_spacing_mid_mm=float(st.session_state.get("shear_spacing_mid_mm") or 0.0),
                    shear_s_end=float(st.session_state.get("shear_s_end") or 0.0),
                    shear_s_mid=float(st.session_state.get("shear_s_mid") or 0.0),
                    shear_mid_spacing_calc_mm=float(st.session_state.get("shear_mid_spacing_calc_mm") or 0.0),
                    shear_mid_spacing_mode=str(st.session_state.get("shear_mid_spacing_mode") or ""),
                    V_mid_kN=float(st.session_state.get("V_mid_kN") or 0.0),
                    shear_provided_input_spacing_mm=float(_sip),
                    shear_input_spacing_mm=float(_sip),
                    shear_sectional_check_spacing_mm=float(_sip),
                    shear_required_spacing_mm=_fail_req_mm,
                    shear_effective_spacing_mm=_fail_eff_mm,
                    shear_debug_s_eff_mm=_fail_s_end,
                    shear_governing_spacing_source=str(_fail_truth.get("governing_spacing_source") or ""),
                    shear_truth_status=None,
                    shear_truth_reason=f"global_outer_failure: {str(exc)[:400]}",
                    shear_truth_inconsistent_status_override=None,
                    shear_truth_util_governing=None,
                    shear_truth_web_util_governing=None,
                    shear_util_governing=None,
                    final_shear_status_source=_nf_outer["final_shear_status_source"],
                    final_shear_truth_resolved=_nf_outer["final_shear_truth_resolved"],
                    final_shear_truth_failure_reason=_nf_outer["final_shear_truth_failure_reason"],
                    published_result_spacing_mm=_nf_outer["published_result_spacing_mm"],
                    published_result_spacing_meaning=_nf_outer["published_result_spacing_meaning"],
                    final_shear_spacing_reason=_nf_outer["final_shear_spacing_reason"],
                    final_shear_publication_path="global_outer_invalid",
                    final_shear_truth_bundle_complete=True,
                    summary_shear_truth_consume_reason="explicit_final_truth_bundle",
                    shear_auto_selected_lig_d_mm=None,
                    shear_auto_selected_legs=None,
                    shear_M_uls_kNm=list(st.session_state.get("shear_M_uls_kNm") or []),
                    shear_M_sls_kNm=list(st.session_state.get("shear_M_sls_kNm") or []),
                    moment_x=list(st.session_state.get("moment_x") or st.session_state.get("shear_x") or []),
                    moment_values=list(
                        st.session_state.get("moment_values") or st.session_state.get("shear_M_sls_kNm") or []
                    ),
                    crack_bmd_cache_fingerprint=str(st.session_state.get("crack_bmd_cache_fingerprint") or ""),
                    bmd_support_positions_m=list(st.session_state.get("bmd_support_positions_m") or []),
                    bmd_support_types=list(st.session_state.get("bmd_support_types") or []),
                )
                with speed_profile_section("derived_result_computation.final_normalized_shear_truth", category="compute"):
                    publish_normalized_final_shear_truth_to_session(
                        source="compute_all_results:global_outer_invalid",
                    )
            except Exception:
                pass

        # SLS steel stress feeding crack/deflection
        try:
            from bending_core import compute_sls_bending_values_from_state
            with speed_profile_section("derived_result_computation.sls_bending_values", category="compute"):
                compute_sls_bending_values_from_state(publish=True)
        except Exception:
            pass

        # Time-dependent inputs feeding crack/deflection
        try:
            from creep import compute_creep_results
            with speed_profile_section("derived_result_computation.creep_results", category="compute"):
                compute_creep_results(publish=True)
        except Exception:
            pass

        try:
            from shrinkage import compute_shrinkage_results
            with speed_profile_section("derived_result_computation.shrinkage_results", category="compute"):
                compute_shrinkage_results(publish=True)
        except Exception:
            pass

        # Crack + deflection (depend on sigma_s_sls / creep / shrinkage)
        try:
            from crack_core import _compute_crack_results
            with speed_profile_section("derived_result_computation.crack_results", category="compute"):
                _compute_crack_results()
        except Exception:
            pass

        try:
            from deflection_core import _compute_deflection_results
            with speed_profile_section("derived_result_computation.deflection_results", category="compute"):
                _compute_deflection_results()
        except Exception:
            pass

        try:
            with speed_profile_section("derived_result_computation.finalize_normalized_shear_truth", category="compute"):
                publish_normalized_final_shear_truth_to_session(source="compute_all_results:finalize")
        except Exception:
            pass
        _section_t0 = time.perf_counter()
        set_rerun_pure_cache(
            "compute_all_results_bundle",
            compute_fp,
            {
                "derived": {k: st.session_state.get(k) for k in DERIVED_KEYS},
                "results": {k: st.session_state.get(k) for k in RESULT_KEYS},
                "debug": {
                    "_final_shear_truth_normalized_source": st.session_state.get("_final_shear_truth_normalized_source"),
                    "_final_shear_truth_normalized_latest": st.session_state.get("_final_shear_truth_normalized_latest"),
                },
            },
        )
        speed_profile_record(
            "derived_result_computation.compute_all_results.summary_bundle_build_and_cache_store",
            (time.perf_counter() - _section_t0) * 1000.0,
            category="compute",
        )


def normalize_final_published_shear_truth(state: dict | None) -> dict:
    def _valid_float(*values):
        for value in values:
            try:
                out = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(out) or math.isinf(out):
                continue
            return out
        return None

    def _valid_spacing(*values):
        for value in values:
            out = _valid_float(value)
            if out is None:
                continue
            if out <= 0.0:
                continue
            return out
        return None

    def _first_positive_float(*values):
        for value in values:
            out = _valid_float(value)
            if out is None:
                continue
            if out <= 0.0:
                continue
            return out
        return None

    s = dict(state or {})
    sip = _valid_float(
        s.get("s_lig"),
        s.get("shear_input_spacing_mm"),
        s.get("shear_provided_input_spacing_mm"),
        0.0,
    )
    req = _valid_spacing(s.get("shear_required_spacing_mm"))
    eff = _valid_spacing(s.get("shear_effective_spacing_mm"))
    design_status = str(s.get("shear_design_status") or "").strip().upper()
    env_status = str(s.get("shear_envelope_status") or "").strip().upper()
    summary_governing_status = str(s.get("summary_governing_status") or "").strip().upper()
    summary_governing_check_name = str(s.get("summary_governing_check_name") or "").strip()
    summary_governing_reason = str(s.get("summary_governing_reason") or "").strip()
    summary_governing_source = str(s.get("summary_governing_source") or "").strip()
    summary_selection_origin = str(s.get("summary_governing_selection_origin") or "").strip()
    final_resolved_existing = s.get("final_shear_truth_resolved")
    fail_reason_existing = str(s.get("final_shear_truth_failure_reason") or "").strip()
    gov_source = str(s.get("shear_governing_spacing_source") or "").strip()
    truth_reason_existing = str(s.get("shear_truth_reason") or "").strip()
    util_governing = None
    util_source = "missing"
    canonical_governing_status = str(s.get("shear_governing_status") or s.get("canonical_shear_status") or "").strip().upper()
    canonical_governing_check_name = str(s.get("shear_governing_check_name") or "").strip()
    canonical_governing_reason = str(s.get("shear_governing_reason") or s.get("canonical_shear_reason") or "").strip()
    canonical_governing_source = str(s.get("shear_governing_source") or s.get("canonical_shear_source") or "").strip()
    canonical_governing_util = _valid_float(s.get("shear_governing_util"), s.get("canonical_shear_util"))
    canonical_spacing_override_active = bool(s.get("canonical_shear_spacing_override_active"))
    canonical_spacing_override_reason = str(s.get("canonical_shear_spacing_override_reason") or "").strip()
    summary_governing_util = _valid_float(s.get("summary_governing_util"))
    _truth_util_existing = _valid_float(s.get("shear_truth_util_governing"))
    _governing_util_existing = _valid_float(s.get("shear_util_governing"))
    _envelope_min_existing = _valid_float(s.get("shear_util_min"))
    if canonical_governing_util is not None:
        util_governing = canonical_governing_util
        util_source = "explicit_canonical_published_governing_util"
    elif summary_governing_util is not None:
        util_governing = summary_governing_util
        util_source = "explicit_summary_governing_util"
    elif _truth_util_existing is not None:
        util_governing = _truth_util_existing
        util_source = "existing_truth"
    elif _governing_util_existing is not None:
        util_governing = _governing_util_existing
        util_source = "existing_governing"
    elif _envelope_min_existing is not None:
        util_governing = _envelope_min_existing
        util_source = "existing_envelope_min"

    _truth_web_util_existing = _valid_float(s.get("shear_truth_web_util_governing"))
    _legacy_web_util_existing = _valid_float(s.get("Vuc_utilisation"))
    web_util = _truth_web_util_existing
    web_util_source = "existing_truth" if _truth_web_util_existing is not None else "missing"
    if web_util is None and _legacy_web_util_existing is not None:
        web_util = _legacy_web_util_existing
        web_util_source = "existing_governing"

    summary_governing_demand = _first_positive_float(s.get("summary_governing_demand_kN"))
    summary_governing_capacity = _first_positive_float(s.get("summary_governing_capacity_kN"))
    canonical_governing_demand = _first_positive_float(s.get("shear_governing_demand_kN"))
    canonical_governing_capacity = _first_positive_float(s.get("shear_governing_capacity_kN"))
    action_v = _first_positive_float(
        canonical_governing_demand,
        summary_governing_demand,
        s.get("summary_governing_demand_kN"),
        s.get("V_eq_kN"),
        s.get("Vu_star"),
        s.get("uls_Vstar"),
        s.get("load_Vstar_proxy"),
    )
    cap_v = _first_positive_float(
        canonical_governing_capacity,
        summary_governing_capacity,
        s.get("summary_governing_capacity_kN"),
        s.get("shear_Vu_total_kN"),
        s.get("phi_Vu_cap"),
        s.get("phi_Vu_max_kN"),
    )
    if util_governing is None and action_v is not None and cap_v is not None and cap_v > 0.0:
        util_governing = float(action_v) / float(cap_v)
        util_source = "computed_from_action_capacity"

    web_cap = _first_positive_float(
        s.get("phi_Vu_max_kN"),
        s.get("phiVu_max"),
        s.get("phi_vu_max"),
    )
    if web_util is None and action_v is not None and web_cap is not None and web_cap > 0.0:
        web_util = float(action_v) / float(web_cap)
        web_util_source = "computed_from_action_web_capacity"
    result_spacing = _valid_spacing(s.get("published_result_spacing_mm"))
    result_spacing_meaning = str(s.get("published_result_spacing_meaning") or "").strip()
    sectional_spacing = _valid_spacing(
        s.get("shear_sectional_check_spacing_mm"),
        eff,
        sip,
    )
    provided_spacing = _valid_spacing(
        s.get("shear_provided_input_spacing_mm"),
        s.get("shear_input_spacing_mm"),
        s.get("s_lig"),
        sip,
    )
    input_spacing = _valid_spacing(
        s.get("shear_input_spacing_mm"),
        s.get("shear_provided_input_spacing_mm"),
        s.get("s_lig"),
        sip,
    )
    sectional_action_v = _first_positive_float(
        s.get("V_eq_kN"),
        s.get("Vu_star"),
        s.get("uls_Vstar"),
        s.get("load_Vstar_proxy"),
    )
    sectional_cap_v = _first_positive_float(
        s.get("shear_Vu_total_kN"),
        s.get("phi_Vu_cap"),
        s.get("summary_governing_capacity_kN"),
    )

    published_result_spacing_mm = _valid_spacing(result_spacing, eff, provided_spacing, input_spacing)
    published_result_spacing_meaning = (
        result_spacing_meaning
        or (
            "effective_spacing_used_in_final_check"
            if _valid_spacing(eff) is not None
            else "provided_input_spacing"
        )
    )
    governing_spacing_source = gov_source or published_result_spacing_meaning

    governing_required_vu_alignment = False

    final_shear_spacing_reason_existing = str(s.get("final_shear_spacing_reason") or "").strip()
    final_shear_publication_path_existing = str(s.get("final_shear_publication_path") or "").strip()

    chosen_status = ""
    chosen_reason = ""
    chosen_source = ""
    chosen_check_name = ""
    if canonical_governing_status in {"PASS", "FAIL", "INVALID"} or canonical_governing_util is not None:
        chosen_status = canonical_governing_status
        chosen_reason = canonical_governing_reason
        chosen_source = canonical_governing_source or util_source
        chosen_check_name = canonical_governing_check_name
    elif summary_governing_status in {"PASS", "FAIL", "INVALID"} or summary_governing_util is not None:
        chosen_status = summary_governing_status
        chosen_reason = summary_governing_reason
        chosen_source = summary_governing_source or util_source
        chosen_check_name = summary_governing_check_name
    else:
        chosen_status = design_status or env_status
        chosen_reason = truth_reason_existing or fail_reason_existing
        chosen_source = util_source
        chosen_check_name = summary_governing_check_name or canonical_governing_check_name

    explicit_invalid_override = (
        design_status == "INVALID"
        or chosen_status == "INVALID"
    )
    if canonical_spacing_override_active and canonical_spacing_override_reason:
        chosen_reason = (
            f"{chosen_reason}; {canonical_spacing_override_reason}"
            if chosen_reason and canonical_spacing_override_reason not in chosen_reason
            else (chosen_reason or canonical_spacing_override_reason)
        )
    explicit_failure_override = bool(
        not explicit_invalid_override
        and (
            canonical_spacing_override_active
            or (
                util_governing is not None
                and util_governing <= 1.0 + 1e-9
                and chosen_status == "FAIL"
                and not (canonical_governing_util is not None or summary_governing_util is not None)
                and bool(fail_reason_existing)
            )
        )
    )

    if explicit_invalid_override:
        shear_truth_status = "INVALID"
        final_shear_truth_resolved = False
        final_shear_truth_failure_reason = fail_reason_existing or "invalid_shear_state"
        final_shear_status_source = chosen_source or "normalized_from_current_state"
        final_shear_spacing_reason = final_shear_spacing_reason_existing or "invalid_final_truth"
        final_shear_publication_path = final_shear_publication_path_existing or "normalized_invalid"
        shear_truth_reason = (
            chosen_reason
            or truth_reason_existing
            or final_shear_truth_failure_reason
        )
    elif util_governing is not None and util_governing > 1.0 + 1e-9:
        shear_truth_status = "FAIL"
        final_shear_truth_resolved = True
        final_shear_truth_failure_reason = ""
        final_shear_status_source = chosen_source or "normalized_from_util"
        final_shear_spacing_reason = final_shear_spacing_reason_existing or "fail_final_truth"
        final_shear_publication_path = final_shear_publication_path_existing or "normalized_fail"
        shear_truth_reason = (
            chosen_reason
            or truth_reason_existing
            or "governing_shear_util_exceeds_unity"
        )
    elif util_governing is not None and util_governing <= 1.0 + 1e-9 and not explicit_failure_override:
        shear_truth_status = "PASS"
        final_shear_truth_resolved = True
        final_shear_truth_failure_reason = ""
        final_shear_status_source = chosen_source or "normalized_from_util"
        final_shear_spacing_reason = final_shear_spacing_reason_existing or "pass_final_truth"
        final_shear_publication_path = final_shear_publication_path_existing or "normalized_pass"
        shear_truth_reason = chosen_reason or truth_reason_existing or "pass_final_truth"
    elif chosen_status == "FAIL" or design_status == "FAIL" or env_status == "FAIL" or bool(fail_reason_existing):
        shear_truth_status = "FAIL"
        final_shear_truth_resolved = False
        final_shear_truth_failure_reason = (
            canonical_spacing_override_reason
            or fail_reason_existing
            or "normalized_fail_from_current_state"
        )
        final_shear_status_source = chosen_source or "normalized_from_current_state"
        final_shear_spacing_reason = final_shear_spacing_reason_existing or "fail_final_truth"
        final_shear_publication_path = final_shear_publication_path_existing or "normalized_fail"
        shear_truth_reason = chosen_reason or truth_reason_existing or final_shear_truth_failure_reason
    else:
        shear_truth_status = "FAIL"
        final_shear_truth_resolved = False
        final_shear_truth_failure_reason = fail_reason_existing or "missing_normalized_shear_truth"
        final_shear_status_source = chosen_source or "normalized_fallback"
        final_shear_spacing_reason = final_shear_spacing_reason_existing or "fail_final_truth"
        final_shear_publication_path = "normalized_fallback"
        shear_truth_reason = chosen_reason or truth_reason_existing or final_shear_truth_failure_reason

    return {
        "shear_truth_status": shear_truth_status,
        "shear_truth_reason": shear_truth_reason,
        "shear_truth_util_governing": util_governing,
        "shear_truth_web_util_governing": web_util,
        "shear_truth_util_source": util_source,
        "shear_truth_web_util_source": web_util_source,
        "shear_truth_governing_check_name": chosen_check_name or summary_governing_check_name or canonical_governing_check_name,
        "shear_truth_governing_reason": chosen_reason or shear_truth_reason,
        "shear_truth_governing_source": chosen_source or util_source,
        "shear_util_governing": util_governing,
        "final_shear_status_source": final_shear_status_source,
        "final_shear_truth_resolved": bool(final_shear_truth_resolved),
        "final_shear_truth_failure_reason": final_shear_truth_failure_reason,
        "final_shear_spacing_reason": final_shear_spacing_reason,
        "final_shear_publication_path": final_shear_publication_path,
        "final_shear_truth_bundle_complete": True,
        "shear_required_spacing_mm": req,
        "shear_effective_spacing_mm": eff,
        "shear_governing_spacing_source": governing_spacing_source,
        "published_result_spacing_mm": published_result_spacing_mm,
        "published_result_spacing_meaning": published_result_spacing_meaning,
        "shear_provided_input_spacing_mm": provided_spacing,
        "shear_input_spacing_mm": input_spacing,
        "shear_sectional_check_spacing_mm": sectional_spacing,
        "shear_truth_canonical_source_used": chosen_source or util_source,
        "shear_truth_canonical_util_used": util_governing,
        "shear_truth_canonical_status_used": shear_truth_status,
        "shear_truth_canonical_reason_used": chosen_reason or shear_truth_reason,
        "shear_truth_spacing_override_active": bool(canonical_spacing_override_active),
        "shear_truth_spacing_override_reason": canonical_spacing_override_reason,
        "shear_truth_summary_selection_origin": summary_selection_origin,
        "shear_governing_check_name": chosen_check_name or summary_governing_check_name or canonical_governing_check_name,
        "shear_governing_demand_kN": action_v,
        "shear_governing_capacity_kN": cap_v,
        "shear_governing_util": util_governing,
        "shear_governing_status": shear_truth_status,
        "shear_governing_reason": chosen_reason or shear_truth_reason,
        "shear_governing_source": chosen_source or util_source,
    }


def publish_normalized_final_shear_truth_to_session(*, source: str) -> dict:
    bundle = normalize_final_published_shear_truth(dict(st.session_state))
    for key, value in bundle.items():
        st.session_state[key] = value
    st.session_state["_final_shear_truth_normalized_source"] = source
    st.session_state["_final_shear_truth_normalized_latest"] = dict(bundle)
    return bundle


def _update_results_impl(**kwargs):
    """Internal implementation of update_results (separated for debug guard wrapping)."""
    global RESULT_KEYS, RESULT_DEFAULTS
    
    # Backward-compat: fold Vu_star_kN into Vu_star and remove the legacy key
    if "Vu_star_kN" in kwargs:
        if "Vu_star" not in kwargs:
            kwargs["Vu_star"] = kwargs.get("Vu_star_kN")
        del kwargs["Vu_star_kN"]

    # Debug: prove action keys are present at runtime
    st.session_state["_debug_actions_keys_in_RESULT_KEYS"] = all(
        k in RESULT_KEYS for k in ("actions_source", "Mu_star", "Mu_star_kNm", "Vu_star")
    )
    
    allowed = RESULT_KEYS
    unknown = set(kwargs.keys()) - allowed
    if unknown:
        # Auto-register unknown keys in debug mode only (prevents whack-a-mole during development)
        try:
            from src.debug.state_debug import is_debug_enabled
            if is_debug_enabled():
                # Auto-register in debug only
                RESULT_KEYS |= unknown
                for k in unknown:
                    if k not in RESULT_DEFAULTS:
                        RESULT_DEFAULTS[k] = 0.0
                    if k not in st.session_state:
                        st.session_state[k] = RESULT_DEFAULTS[k]
                st.session_state["_debug_auto_registered_results"] = sorted(list(unknown))
                # Log the auto-registration
                import json
                import os
                log_path = os.devnull
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({
                            "location": "state_and_helpers.py:_update_results_impl",
                            "message": "Auto-registered unknown result keys (debug mode)",
                            "data": {"unknown_keys": sorted(list(unknown))},
                            "timestamp": __import__("time").time() * 1000,
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "AUTO_REGISTER"
                        }) + "\n")
                except:
                    pass
            else:
                raise KeyError(
                    f"[SESSION STATE CONTRACT] Tried to update unknown RESULT key(s) {unknown}.\n"
                    f"Add them to RESULT_KEYS/RESULT_DEFAULTS before using update_results()."
                )
        except (ImportError, NameError):
            # Debug module not available, use strict mode
            raise KeyError(
                f"[SESSION STATE CONTRACT] Tried to update unknown RESULT key(s) {unknown}.\n"
                f"Add them to RESULT_KEYS/RESULT_DEFAULTS before using update_results()."
            )
    
    # Update session_state with the provided values
    for k, v in kwargs.items():
        st.session_state[k] = v

    # Cleanup legacy key if present in session state
    if "Vu_star_kN" in st.session_state:
        try:
            del st.session_state["Vu_star_kN"]
        except Exception:
            pass
    
    # --- ARCHITECTURE LOCK: ensure results pipeline exists ---
    _assert_results_pipeline()


# ============================================
# 6. SMALL HELPERS
# ============================================

def _assert_results_pipeline():
    """Dev-only assertion: ensure results dict exists (initialize if needed)."""
    if not st.session_state.get("_dev_mode", False):
        return
    # Initialize results dict if it doesn't exist
    if "results" not in st.session_state:
        st.session_state["results"] = {}


def _store_results_bucket(bucket: str, data: dict) -> None:
    """Store cached results and update metadata timestamp."""
    st.session_state.setdefault("results", {})
    st.session_state.setdefault("results_meta", {})
    st.session_state["results"][bucket] = data
    st.session_state["results_meta"][bucket] = {"updated_at": time.time()}

def get_param(name: str, default=None):
    """
    Safe accessor for shared parameters from session_state.
    Treats None as "not set" and returns the default instead.
    """
    if name in st.session_state:
        value = st.session_state[name]
        # Treat None as "not set" - return default instead
        if value is not None:
            return value
    
    # Key not in session_state, or value is None - check SHARED_DEFAULTS
    shared_default = SHARED_DEFAULTS.get(name, default)
    # If SHARED_DEFAULTS also has None, treat it as "not set" and use the provided default
    if shared_default is not None:
        return shared_default
    return default


def _critical_input_keys():
    """List of critical input keys that must never be overwritten with snippet defaults."""
    return [
        "b", "D", "L",
        "fc", "fsy", "Ec", "Es",

        # Design actions (manual inputs)
        "actions_source",
        "uls_Mstar", "uls_Vstar", "Tu_star",
        "P_star", "N_star",

        # Covers / geometry-related
        "cover_bot", "cover_top", "cover_side",

        # Shear reinforcement inputs
        "lig_d", "lig_legs", "s_lig",

        # Ducts / voids
        "n_ducts", "duct_dia",

        # Time-dependent inputs
        "t_creep", "t_shrink",
    ]


def _is_snippet_defaults_state(ss) -> bool:
    """
    Detect the exact bogus 'snippet defaults' state we keep seeing.
    We use BOTH a signature match and a sanity-range check.
    """
    def f(k, d=0.0):
        try:
            return float(ss.get(k, d))
        except Exception:
            return d

    b  = f("b")
    D  = f("D")
    L  = f("L")
    fc = f("fc")
    fsy = f("fsy")
    Ec = f("Ec")
    Es = f("Es")

    # Exact signature (from your screenshot)
    signature = (
        abs(b - 10.0) < 1e-9 and
        abs(D - 10.0) < 1e-9 and
        abs(L - 100.0) < 1e-9 and
        abs(fc - 2.0) < 1e-9 and
        abs(fsy - 10.0) < 1e-9 and
        abs(Ec - 1000.0) < 1e-9 and
        abs(Es - 10000.0) < 1e-9
    )

    # Sanity check for mm/MPa typical ranges (detect impossible values)
    # Values that are too small to be realistic engineering inputs
    impossible = (b < 50) or (D < 50) or (L < 200) or (fc < 10) or (fsy < 200) or (Ec < 10000) or (Es < 100000)

    # Return True if we match the exact signature OR if values are impossibly small
    return signature or impossible


@st.cache_resource
def _global_state_store() -> dict:
    """
    Server-side singleton store. Survives per-user session resets
    as long as the server process stays alive.
    """
    return {}


def _snapshot_last_good_inputs():
    """Snapshot current input values as 'last good' state (session + global store)."""
    snap = {k: st.session_state.get(k) for k in _critical_input_keys()}
    st.session_state["_last_good_inputs"] = snap
    try:
        _global_state_store()["last_good_inputs"] = snap
    except Exception:
        pass


def _restore_last_good_inputs():
    """Restore shared and widget keys from last known good snapshot (session or global store)."""
    snap = st.session_state.get("_last_good_inputs")
    if not isinstance(snap, dict):
        try:
            snap = _global_state_store().get("last_good_inputs")
        except Exception:
            snap = None
    if not isinstance(snap, dict):
        return

    # Restore shared keys
    for k, v in snap.items():
        if v is not None:
            st.session_state[k] = v

    # Restore ALL widget keys mapped to these shared keys
    for widget_key, shared_key in TAB_KEYS.items():
        if shared_key in snap and snap[shared_key] is not None:
            st.session_state[widget_key] = snap[shared_key]


# ============================================
# SYNC LOCK (prevents mass-zero writes during render)
# ============================================

def is_sync_locked() -> bool:
    """Check if sync callbacks are locked (prevents widget→shared writes during hydration/render)."""
    return bool(st.session_state.get("_sync_lock", False))


# ============================================
# AUDIT TRAIL FOR SHARED INPUT WRITES
# ============================================

def mark_user_edit(*args, **kwargs):
    st.session_state["_inputs_dirty"] = True
    st.session_state["_user_has_edited_anything"] = True


def clear_user_edit_marker_each_run():
    """Clear user edit markers at the start of each rerun (prevents stale exemptions)."""
    st.session_state["_last_user_widget_key"] = None
    st.session_state["_last_user_shared_key"] = None
    st.session_state["_last_user_edit_ts"] = 0.0


def end_of_render_cleanup(active_page: str | None = None) -> None:
    """
    Called once at the end of app.py's render loop.

    Must be SAFE:
    - no shared writes
    - no widget seeding
    - only diagnostics / snapshot persistence if you already do that
    """
    # If you already have snapshot persistence / debug hooks, call them here.
    # Keep this function NO-OP safe for now.
    return


def _safe_repr(v):
    """Safe representation for debug dumps (rounds floats, handles exceptions)."""
    try:
        if isinstance(v, float):
            return round(v, 6)
        return v
    except Exception:
        return str(v)


def dump_session_state_inventory(page_name: str, sync_callbacks: dict | None = None, out_dir: str = "."):
    """
    Debug-only: dump actual session-state and widget/shared mapping consistency.
    Does not write to any shared keys.
    """
    import json
    from pathlib import Path
    from datetime import datetime
    from widgets_helpers import get_rendered_widget_keys

    rendered = get_rendered_widget_keys()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Collect session keys
    sess_keys = sorted(list(st.session_state.keys()))

    # Build widget->shared pairs
    pairs = []
    missing_shared = []
    for wk in rendered:
        sk = TAB_KEYS.get(wk)
        wv = st.session_state.get(wk, None)
        sv = st.session_state.get(sk, None) if sk else None

        pairs.append({
            "widget_key": wk,
            "widget_val": _safe_repr(wv),
            "widget_type": type(wv).__name__,
            "shared_key": sk,
            "shared_val": _safe_repr(sv),
            "shared_type": type(sv).__name__ if sk else None,
        })

        if sk and sk not in st.session_state:
            missing_shared.append(sk)

    # Detect unknown/stray keys
    shared_defaults = set(SHARED_DEFAULTS.keys())
    mapped_shared = set([p["shared_key"] for p in pairs if p["shared_key"]])

    stray_session_keys = [
        k for k in sess_keys
        if k not in shared_defaults
        and k not in rendered
        and k not in mapped_shared
        and not k.startswith("_")  # ignore internal
    ]

    # Text report
    report = {
        "timestamp": now,
        "page": page_name,
        "boot_id": st.session_state.get("_boot_id"),
        "fresh_boot": st.session_state.get("_fresh_boot"),
        "restored_from_snapshot": st.session_state.get("_restored_from_snapshot"),
        "rendered_widget_count": len(rendered),
        "session_key_count": len(sess_keys),
        "missing_shared_for_rendered": sorted(list(set(missing_shared))),
        "stray_session_keys": stray_session_keys[:200],  # cap output
        "pairs": pairs,
    }

    # Write txt + csv-like pairs
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_path = out_dir / f"session_state_inventory_{page_name}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, indent=2, ensure_ascii=False))

    csv_path = out_dir / f"widget_shared_pairs_{page_name}.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("widget_key,widget_val,widget_type,shared_key,shared_val,shared_type\n")
        for p in pairs:
            f.write(
                f"{p['widget_key']},{p['widget_val']},{p['widget_type']},"
                f"{p['shared_key']},{p['shared_val']},{p['shared_type']}\n"
            )

    return str(txt_path), str(csv_path)


def _write_sync_trace_line(line: str, filename: str = "sync_callback_trace.txt") -> None:
    """Append one line to sync trace file (debug only)."""
    if not DEBUG_MODE:
        return
    try:
        path = DEBUG_OUT_DIR / filename
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _sync_trace_file(
    reason: str,
    widget_key: str,
    shared_key: str | None,
    widget_val=None,
    shared_val=None,
):
    """Debug-only: record why a sync callback returned or wrote."""
    if not DEBUG_MODE:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    try:
        widget_type = type(widget_val).__name__ if widget_val is not None else "None"
        shared_type = type(shared_val).__name__ if shared_val is not None else "None"
        line = (
            f"{ts} | {reason} | "
            f"wk={widget_key} | sk={shared_key} | "
            f"wv={repr(widget_val)} ({widget_type}) | "
            f"sv={repr(shared_val)} ({shared_type}) | "
            f"last_user={st.session_state.get('_last_user_widget_key')} | "
            f"sync_lock={bool(st.session_state.get('_sync_lock', False))} | "
            f"restore_guard={bool(st.session_state.get('_restore_guard_active', False))} | "
            f"restored={bool(st.session_state.get('_restored_from_snapshot', False))}"
        )
        _write_sync_trace_line(line)
    except Exception:
        pass


def _sync_trace(reason: str, widget_key: str, shared_key: str | None = None):
    """Debug-only: record why sync callback returned (in-memory version)."""
    try:
        trace = st.session_state.get("_sync_trace", [])
        trace.append({
            "reason": reason,
            "widget_key": widget_key,
            "shared_key": shared_key,
            "sync_lock": bool(st.session_state.get("_sync_lock", False)),
            "restore_guard": bool(st.session_state.get("_restore_guard_active", False)),
            "restored_from_snapshot": bool(st.session_state.get("_restored_from_snapshot", False)),
            "last_user_widget": st.session_state.get("_last_user_widget_key"),
        })
        st.session_state["_sync_trace"] = trace[-200:]  # cap
    except Exception:
        pass


def widget_contract_audit(sync_callbacks: dict | None = None) -> dict:
    """Return audit info: rendered widget keys missing TAB_KEYS or missing callbacks."""
    from widgets_helpers import get_rendered_widget_keys
    
    rendered = get_rendered_widget_keys()

    missing_tab_keys = [k for k in rendered if k not in TAB_KEYS]
    missing_callbacks = []
    if sync_callbacks is not None:
        missing_callbacks = [k for k in rendered if k in TAB_KEYS and k not in sync_callbacks]

    return {
        "rendered_count": len(rendered),
        "missing_tab_keys": missing_tab_keys,
        "missing_callbacks": missing_callbacks,
    }


def write_widget_contract_audit_to_file(sync_callbacks: dict | None = None, filename: str = "widget_contract_audit.txt") -> str:
    """
    Write widget contract audit results to a debug file in the user's Documents folder.
    Returns the file path.
    """
    import os
    from pathlib import Path
    from datetime import datetime
    
    # Get user's Documents folder
    documents_path = Path.home() / "Documents"
    if not documents_path.exists():
        # Fallback: try OneDrive Documents
        documents_path = Path("/Users/jonathonleggo/Library/CloudStorage/OneDrive-Personal/Documents")
    
    audit_file = documents_path / filename
    
    # Get audit results
    audit = widget_contract_audit(sync_callbacks)
    
    # Get all rendered keys for reference
    from widgets_helpers import get_rendered_widget_keys
    rendered = get_rendered_widget_keys()
    
    # Write to file
    with open(audit_file, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("Widget Contract Audit Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Total rendered widgets: {audit['rendered_count']}\n\n")
        
        if audit["missing_tab_keys"]:
            f.write(f"❌ Missing TAB_KEYS mappings: {len(audit['missing_tab_keys'])}\n")
            f.write("Keys:\n")
            for key in audit["missing_tab_keys"]:
                f.write(f"  - {key}\n")
            f.write("\n")
        else:
            f.write("✅ All rendered widget keys are in TAB_KEYS\n\n")
        
        if audit["missing_callbacks"]:
            f.write(f"❌ Missing sync callbacks: {len(audit['missing_callbacks'])}\n")
            f.write("Keys:\n")
            for key in audit["missing_callbacks"]:
                f.write(f"  - {key}\n")
            f.write("\n")
        else:
            f.write("✅ All rendered widgets have sync callbacks\n\n")
        
        # Also list all rendered keys for reference
        if rendered:
            f.write("All rendered widget keys:\n")
            for key in rendered:
                f.write(f"  - {key}\n")
    
    return str(audit_file)


def migrate_time_defaults_once():
    """
    One-time repair for historically-buggy time inputs that get restored as 0/1
    (snippet values) and then overwrite shared state via sync callbacks.

    We intentionally prefer realistic engineering defaults over stale snapshot
    values that were created by the old bug.
    """
    if st.session_state.get("_time_defaults_migrated_once", False):
        return

    # Realistic defaults (match AS3600 practice / typical design assumptions)
    DEFAULTS = {
        "t_creep": 365.0,         # days after loading
        "age_at_loading": 28.0,   # days (28-day strength basis)
        "t_shrink": 365.0,        # days since drying
    }

    # Widget keys used on Inputs page (your TAB_KEYS maps these to shared keys)
    LEGACY_WIDGET_KEYS = {
        # Inputs page (legacy)
        "inputs_t_creep": "t_creep",
        "inputs_age_at_loading": "age_at_loading",
        "inputs_t_shrink": "t_shrink",

        # Creep page widgets
        "cr_t_creep": "t_creep",
        "cr_tau": "age_at_loading",

        # Shrinkage page widget
        "sh_t_days": "t_shrink",
    }

    def _is_stale_snippet(v) -> bool:
        # Old bug commonly restored these as 0 or 1 (or None/NaN)
        try:
            if v is None:
                return True
            fv = float(v)
            if math.isnan(fv):
                return True
            return fv in (0.0, 1.0)
        except Exception:
            return True

    # 1) Repair shared values first
    for sk, dv in DEFAULTS.items():
        if sk not in st.session_state or _is_stale_snippet(st.session_state.get(sk)):
            st.session_state[sk] = float(dv)

    # 2) Repair legacy widget keys if they exist in session_state
    #    (prevents widgets showing 1/0 and then syncing back into shared)
    for wk, sk in LEGACY_WIDGET_KEYS.items():
        if wk in st.session_state and _is_stale_snippet(st.session_state.get(wk)):
            st.session_state[wk] = float(st.session_state[sk])

    # 3) Repair common creep/shrinkage page widgets that sometimes restore as 0
    #    (b, D, fc, Ec) – only if 0 is clearly stale and shared has a real value.
    STICKY_WIDGETS = {
        "cr_b": "b",
        "cr_D": "D",
        "cr_fc": "fc",
        "cr_Ec": "Ec",
        "sh_b": "b",
        "sh_D": "D",
        "sh_fc": "fc",
    }

    for wk, sk in STICKY_WIDGETS.items():
        if wk in st.session_state:
            try:
                wv = st.session_state.get(wk)
                sv = st.session_state.get(sk)
                dv = DEFAULTS.get(sk, SHARED_DEFAULTS.get(sk, None))

                # treat 0/1/None/NaN as stale (same as _is_stale_snippet)
                if _is_stale_snippet(wv):
                    # only overwrite if the shared value is not stale
                    if not _is_stale_snippet(sv):
                        st.session_state[wk] = sv
                    # else fall back to default if available
                    elif dv is not None:
                        st.session_state[wk] = float(dv)
            except Exception:
                pass

    st.session_state["_time_defaults_migrated_once"] = True


def set_shared(key: str, value, *, source: str = "") -> None:
    """
    The only allowed way to write shared inputs (SHARED_DEFAULTS keys).
    All writes are audited for debugging.
    """
    # HARD GUARD: block render-time hydration/merge writes.  A Streamlit
    # widget callback is an explicit user command and may legitimately run
    # while the surrounding fragment still owns the render synchronisation
    # lock.  Silently rejecting that command left the visible action proxy at
    # the edited value while the canonical ULS/SLS owner (and therefore
    # bending/publication) retained its previous value.
    if (
        st.session_state.get("_sync_lock", False)
        and not _set_shared_is_user_intent_source(source)
    ):
        try:
            _write_sync_trace_line(
                f"BLOCKED set_shared (sync_lock) key={key} val={value} source={source}"
            )
        except Exception:
            pass
        return

    if key not in SHARED_DEFAULTS:
        raise KeyError(f"set_shared: '{key}' not in SHARED_DEFAULTS (source={source})")

    old = st.session_state.get(key)
    if old == value:
        return

    # Write the value
    st.session_state[key] = value
    if _set_shared_is_user_intent_source(source):
        tk = st.session_state.setdefault("_shared_keys_touched_this_run", set())
        if not isinstance(tk, set):
            tk = set()
            st.session_state["_shared_keys_touched_this_run"] = tk
        tk.add(key)
    st.session_state["_dirty"] = True
    st.session_state["_last_user_shared_key"] = key
    ts_now = time.time()
    st.session_state["_last_user_edit_ts"] = ts_now
    st.session_state["_last_user_shared_ts"] = ts_now
    try:
        _write_sync_trace_line(
            f"SET_SHARED key={key} old={old} new={value} source={source}"
        )
    except Exception:
        pass
    try:
        debug_log("SET_SHARED", {"shared_key": key, "value": value, "from": st.session_state.get("page_slug")})
    except Exception:
        pass
    try:
        widget_key = None
        if isinstance(source, str) and source.startswith("callback:"):
            widget_key = source.split("callback:", 1)[1]
        log_path = os.path.join(os.path.dirname(__file__), ".blank_app_runtime", "blank_app_debug.log")
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "event": "SET_SHARED",
                "ts": ts_now,
                "shared_key": key,
                "widget_key": widget_key,
                "old": old,
                "new": value,
                "source": source,
                "page": st.session_state.get("page_slug"),
            }) + "\n")
    except Exception:
        pass
    
    # Audit trail (keep last 50)
    tail = st.session_state.get("_shared_write_audit", [])
    caller = inspect.stack()[1]
    tail.append({
        "t": round(time.time(), 3),
        "key": key,
        "val": value,
        "source": source,
        "where": f"{caller.filename.split('/')[-1]}:{caller.lineno} {caller.function}",
    })
    st.session_state["_shared_write_audit"] = tail[-50:]


def set_ui(key: str, value, *, source: str = "") -> None:
    if key not in UI_STATE_DEFAULTS:
        raise KeyError(f"set_ui: '{key}' not in UI_STATE_DEFAULTS (source={source})")
    st.session_state[key] = value


# ============================================
# REGRESSION TRIPWIRE
# ============================================

def assert_shared_state_alive():
    """
    Regression tripwire: checks that critical shared state keys exist.
    If this fails, shared state was lost (bug detection).
    Call this after routing in app.py to catch state loss immediately.
    """
    required = ["b", "D", "L", "fc", "fsy", "Ec", "Es"]
    if any(k not in st.session_state for k in required):
        st.error("Shared session state was lost. This is a bug.")


# ============================================
# RUNTIME CONTRACTS (dev-mode assertions; fail fast on violations)
# ============================================

def canonical_s_lig_raw(state: dict):
    """Canonical shared s_lig if explicitly present and numeric; else None (not defaulted)."""
    if "s_lig" not in state:
        return None
    v = state.get("s_lig")
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def get_canonical_s_lig(state: dict) -> float:
    """Canonical user-provided shear link spacing: shared state key s_lig only, with starter default if absent."""
    r = canonical_s_lig_raw(state)
    if r is None:
        return float(SHARED_DEFAULTS.get("s_lig", 200.0))
    return float(r)


def get_active_s_lig_widget_value(state: dict) -> tuple:
    """
    Page-local mirror for the active tab only.

    Returns (widget_key, value) or (None, None) when the active page has no s_lig mirror.
    """
    slug = str(state.get("page_slug") or "")
    if slug == "inputs":
        key = "inputs_s_lig"
    elif slug == "shear":
        key = "shear_s_lig"
    else:
        return (None, None)
    v = state.get(key)
    if v is None:
        return (key, None)
    try:
        return (key, float(v))
    except Exception:
        return (key, None)


def _shear_maybe_dev_note_inactive_mirror_stale(state: dict) -> None:
    """Dev/debug only: log when the off-page mirror is stale but contract intentionally does not fail."""
    if not (state.get("_dev_mode") or DEBUG_MODE):
        return
    slug = str(state.get("page_slug") or "")
    if slug not in ("inputs", "shear"):
        return
    tol = 0.51
    raw = canonical_s_lig_raw(state)
    if raw is None:
        return
    canon = float(raw)
    _ak, active_val = get_active_s_lig_widget_value(state)
    if active_val is None or abs(active_val - canon) > tol:
        return
    try:
        if slug == "inputs":
            if "shear_s_lig" not in state:
                return
            w_sh = state.get("shear_s_lig")
            if w_sh is None:
                return
            w_sh = float(w_sh)
            if abs(w_sh - canon) <= tol:
                return
            hc_log(
                "shear_contract_inactive_mirror_stale",
                message="SHEAR CONTRACT NOTE: inactive widget mirror stale; no fail",
                active_page_slug=slug,
                inactive_mirror_key="shear_s_lig",
                inactive_mirror_value=w_sh,
                canonical_shared_s_lig=canon,
            )
        else:
            if "inputs_s_lig" not in state:
                return
            w_in = state.get("inputs_s_lig")
            if w_in is None:
                return
            w_in = float(w_in)
            if abs(w_in - canon) <= tol:
                return
            hc_log(
                "shear_contract_inactive_mirror_stale",
                message="SHEAR CONTRACT NOTE: inactive widget mirror stale; no fail",
                active_page_slug=slug,
                inactive_mirror_key="inputs_s_lig",
                inactive_mirror_value=w_in,
                canonical_shared_s_lig=canon,
            )
    except Exception:
        pass


def _s_lig_shared_write_source_is_allowed(source: str) -> bool:
    """Allow-list for audited set_shared('s_lig', ...) sources (user/mirror/hydrate paths only)."""
    s = str(source or "")
    if s == "":
        return True
    if s.startswith("callback:"):
        return True
    if s.startswith("sync_"):
        return True
    if s.startswith("app:"):
        return True
    if ":shear_shared_normalise" in s:
        return True
    if s.startswith("guidance:"):
        return True
    allowed_exact = {
        "auto_design_apply",
        "auto_design_commit",
        "beam_project_hydrate",
        "persist_snapshot_merge",
        "restore_snapshot",
        "wipe_recovery",
        "seed_defaults",
        "project_load",
        "project_load_default",
        "new_beam_starter_seed",
        "design_action_widget_sync",
        "design_action_proxy_mirror",
    }
    if s in allowed_exact:
        return True
    return False


def _contract_assert_shear_spacing_truth_model(state: dict) -> None:
    """
    Narrow invariant: shared s_lig may differ from derived/effective/governing spacings (expected).
    set_shared('s_lig', ...) must only occur via allow-listed sources — never an implicit derived publish.
    """
    audit = state.get("_shared_write_audit")
    if not isinstance(audit, (list, tuple)):
        return
    for row in audit:
        if not isinstance(row, dict):
            continue
        if row.get("key") != "s_lig":
            continue
        src = str(row.get("source") or "")
        if _s_lig_shared_write_source_is_allowed(src):
            continue
        raise AssertionError(
            "SHEAR SPACING TRUTH MODEL VIOLATION: s_lig write with disallowed audited source "
            f"(source={src!r}). Derived/effective spacing must not silently become canonical s_lig."
        )


def _contract_assert_shear_truth(state: dict) -> None:
    """
    CONTRACT: Shear spacing (see SHEAR_SPACING_CONTRACT_DOC).

    Hard-fail only when canonical shared s_lig is missing/invalid where required, the *active*
    page mirror disagrees with shared s_lig, or audited writes violate the spacing truth model.
    Inactive tab mirrors may lag — optional dev note only.
    """
    slug = str(state.get("page_slug") or "")
    if slug not in ("inputs", "shear"):
        return

    tol = 1e-6
    raw = canonical_s_lig_raw(state)
    if raw is None:
        raise AssertionError(
            "SHEAR CONTRACT VIOLATION: canonical shared s_lig missing or non-numeric "
            f"(active_page_slug={slug!r}, inputs_s_lig={state.get('inputs_s_lig')!r}, "
            f"shear_s_lig={state.get('shear_s_lig')!r}, enforced=comparison:shared_s_lig_required)"
        )

    canon = float(raw)
    active_key, active_val = get_active_s_lig_widget_value(state)
    w_in = state.get("inputs_s_lig")
    w_sh = state.get("shear_s_lig")

    if active_val is not None and abs(active_val - canon) > tol:
        raise AssertionError(
            "SHEAR CONTRACT VIOLATION: active page widget mirror disagrees with canonical shared s_lig "
            f"(active_page_slug={slug!r}, canonical_shared_s_lig={canon}, inputs_s_lig={w_in!r}, "
            f"shear_s_lig={w_sh!r}, enforced=comparison:active_"
            f"{active_key or 'unknown'}_vs_shared_s_lig)"
        )

    _shear_maybe_dev_note_inactive_mirror_stale(state)


def _contract_no_compute_writes(context: str) -> None:
    """
    CONTRACT: Layer 2 / Layer 3 must not write to shared session state during pure compute.

    Hook for future integration with write guards or debug tripwires.
    Call sites may pass context in {"shear_compute", "bending_compute", "guidance_compute", ...}.
    """
    # Extend: integrate with guard_session_writes / NDJSON audit if needed.
    _ = context


def _contract_single_hydration_pass(state: dict) -> None:
    """
    CONTRACT: Inputs page hydration must stay bounded per script run.

    Router performs primary hydration; render_inputs may run additional forced hydrates
    (beam load, pending refresh). Counter reset each run in app.py; threshold is configurable.
    """
    if state.get("_inputs_multiple_hydration_detected"):
        raise AssertionError(
            "HYDRATION CONTRACT VIOLATION: Multiple uncontrolled hydrations detected "
            "(_inputs_multiple_hydration_detected is set)",
        )
    n = int(state.get("_contract_inputs_hydrate_invocations") or 0)
    mx = int(state.get("_contract_max_inputs_hydrations_per_run") or 8)
    if n > mx:
        raise AssertionError(
            f"HYDRATION CONTRACT VIOLATION: inputs hydrations in run ({n}) exceeds max ({mx}). "
            "Router + forced paths should stay within budget; raise _contract_max_inputs_hydrations_per_run if intentional.",
        )


def _contract_single_recommendation_engine(state: dict) -> None:
    """
    CONTRACT: Flagged bypass of the unified Recommendation Engine entry (dev tripwire).

    Set _direct_auto_design_solver_called only when instrumentation detects a forbidden path;
    legitimate handle_auto_design UI may use a separate logging flag — do not set this unless violating policy.
    """
    if state.get("_direct_auto_design_solver_called"):
        raise AssertionError(
            "ENGINE CONTRACT VIOLATION: Direct solver call bypassed Recommendation Engine "
            "(_direct_auto_design_solver_called is set)",
        )


def _contract_session_integrity(state: dict) -> None:
    """
    MASTER CONTRACT CHECK (dev mode). Raises AssertionError on violation.
    """
    _contract_assert_shear_spacing_truth_model(state)
    _contract_assert_shear_truth(state)
    _contract_single_hydration_pass(state)
    _contract_single_recommendation_engine(state)


# Register the narrow, cycle-free dependency surface after this module has
# finished defining and validating its state contracts. Existing imports from
# state_and_helpers remain compatible while lower-level consumers import the
# gateway instead of this high-level orchestration module.
from state_runtime_gateway import (
    StateRuntimeBindings,
    configure_state_runtime_gateway,
)


configure_state_runtime_gateway(
    StateRuntimeBindings(
        get_param=get_param,
        update_results=update_results,
        get_longitudinal_row_inputs=get_longitudinal_row_inputs,
        get_sync_callbacks=get_sync_callbacks,
        speed_profile_record=speed_profile_record,
        speed_profile_section=speed_profile_section,
        resolve_widget_key=resolve_widget_key,
        zero_allowed=zero_allowed,
        audit=_audit,
        mark_user_edit=mark_user_edit,
        set_shared=set_shared,
        canonical_s_lig_raw=canonical_s_lig_raw,
        get_canonical_s_lig=get_canonical_s_lig,
        get_active_s_lig_widget_value=get_active_s_lig_widget_value,
    ),
    shared_defaults=SHARED_DEFAULTS,
    result_keys=RESULT_KEYS,
    derived_keys=DERIVED_KEYS,
    tab_keys=TAB_KEYS,
    nonzero_required_shared_keys=NONZERO_REQUIRED_SHARED_KEYS,
)
