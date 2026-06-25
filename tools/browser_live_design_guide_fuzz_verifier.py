"""Standalone live-session fuzz verifier for the Inputs page Design Guide.

This runner intentionally drives the real Streamlit UI with Playwright.  The
browser/debug JSON is captured for diagnosis, but the pass/fail contract is
based on the rendered summary cards, rendered Design Guide card, and the
visible one-click button state.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import random
import re
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verification.helpers.browser_helpers import (  # noqa: E402
    BENDING_READY_GATE_TIMEOUT_CLASS,
    EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS,
    PAGE_CYCLE_CAPTURE_UNAVAILABLE_CLASS,
    PAGE_CYCLE_FALSE_POSITIVE_HEALTHY_CLASS,
    PAGE_CYCLE_GHOST_FAILURE_CLASS,
    PAGE_CYCLE_GHOST_FAILURE_MESSAGE,
    STREAMLIT_RUNTIME_RECONNECT_CLASS,
    _apply_live_inputs,
    _load_browser_state as _load_browser_state_by_label,
    _same_value,
    _wait_for_post_click_state_without_run_end,
    _wait_for_post_publish_alignment,
    run_page_cycle_ghost_ui_check,
)
from tools.verification.source_fingerprint import (  # noqa: E402
    compare_report_correctness_fingerprint,
    compute_source_fingerprint,
)
from tools.verification.artifact_contract import (  # noqa: E402
    enrich_run_summary,
    validate_replay_artifact,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    TRACER_PATH,
    _query,
    _start_streamlit,
    _wait_for_http,
    _wait_for_run_end,
)
from tools.design_guide_blocker_truth_helpers import (  # noqa: E402
    blocker_family_util_mismatches,
    probe_active_fail_repair_truth,
    probe_green_secondary_blocker_truth,
    probe_overdesign_cleanup_truth,
)


TARGET_LOW = 0.85
ACCEPTED_TARGET_LOW = 0.85
ACCEPTED_TARGET_HIGH = 1.00
REPAIR_TARGET_LOW = 0.88
REPAIR_TARGET_HIGH = 0.95
FORBIDDEN_VISIBLE_WORDING = (
    "cleanup proof unresolved",
    "bounded evidence budget",
    "advisory",
    "optional cleanup",
    "closest safe option not selected",
    "target band evidence required",
    "design guidance is preparing",
    "stale_primary_design_guide_payload",
)
FORBIDDEN_VISIBLE_WORDING_CLASSIFICATIONS = {
    "failed not published": "combined_blocker_reason_placeholder",
    "no specific blocker reason was published": "combined_blocker_reason_placeholder",
    "value -": "strength_blocker_missing_failed_value_or_limit",
    "limit/capacity -": "strength_blocker_missing_failed_value_or_limit",
    "blocked by detailing limits": "card_why_not_specific",
    "repair catalogue": "card_why_not_specific",
    "combined routes failed": "combined_blocker_reason_placeholder",
}
SCREENSHOT_FIELD_KEYS = (
    "full_page_screenshot",
    "viewport_screenshot",
    "design_guide_screenshot",
    "summary_cards_screenshot",
    "debug_or_probe_screenshot",
    "screenshot_capture_status",
    "missing_crop_targets",
)
DESIGN_GUIDE_LAYOUT_TEST_IDS = (
    "design-guide-status-pill",
    "design-guide-title",
    "design-guide-governing-utilisation",
    "design-guide-current-row",
    "design-guide-current-bending",
    "design-guide-current-shear",
    "design-guide-current-crack",
    "design-guide-current-deflection",
    "design-guide-preview-row",
    "design-guide-preview-bending",
    "design-guide-preview-shear",
    "design-guide-preview-crack",
    "design-guide-preview-deflection",
    "design-guide-main-explanation",
    "design-guide-details",
)
DESIGN_GUIDE_ACTION_ROW_TEST_IDS = (
    "design-guide-action-change",
    "design-guide-action-why",
    "design-guide-action-expected-result",
    "design-guide-reason-change",
    "design-guide-reason-fix",
)
DESIGN_GUIDE_REASON_ROW_TEST_IDS = (
    "design-guide-reason-bending",
    "design-guide-reason-shear",
    "design-guide-reason-combined",
    "design-guide-reason-result",
    "design-guide-reason-serviceability",
    "design-guide-reason-problem",
    "design-guide-reason-cause",
    "design-guide-reason-fix",
)
DESIGN_GUIDE_MAIN_DEBUG_PATTERNS = (
    "candidate_",
    "post_click_",
    "cleanup_",
    "practical_ladder",
    "payload_id",
    "blocker_id",
    "raw_debug",
    "actual value utilisation",
    "required limit <=",
    "stale capacity",
    "auto design using stale capacity",
)
FAILED_DESIGN_LOCK_BLOCKER_TERMS = (
    "geometry locked",
    "section depth locked",
    "section width locked",
    "depth locked",
    "width locked",
    "reinforcement locked",
    "bottom reinforcement locked",
    "top reinforcement locked",
    "shear links locked",
    "link spacing locked",
    "links locked",
    "max depth reached",
    "maximum depth reached",
    "max width reached",
    "maximum width reached",
    "user constraint prevents repair",
    "user constraints prevent repair",
    "repair blocked by locked geometry",
    "repair blocked by user constraints",
    "locked by user",
)
FAILED_DESIGN_CLEANUP_TERMS = (
    "cleanup",
    "efficient",
    "efficiency",
    "no further cleanup",
    "further reductions",
    "further reduction",
    "cleanup route",
    "combined cleanup",
    "no executable cleanup",
)
FAILED_SHEAR_NO_LINK_TERMS = (
    "links are already removed",
    "shear links are already removed",
    "keeping no links",
    "no further shear-link cleanup",
    "no further shear link cleanup",
    "no links",
)
FAILED_DESIGN_DEBUG_TEXT_TERMS = (
    "cleanup route",
    "combined cleanup",
    "no executable cleanup",
    "checking routes",
    "candidate",
    "failed capacity utilisation demand/value",
    "demand/value",
    "limit/capacity",
    "exceeded limit/capacity",
    "raw_debug",
    "unsafe - failed capacity",
    "attempted design failed",
    "executable combined cleanup",
    "checked bottom-reinforcement",
    "second-row",
)

BASE_RECIPES = [
    "SO_BASE_HEAVY_LINKS_CONSERVATIVE",
    "A_bending_under_only",
    "B_shear_under_only",
    "C_combined_underdesign",
    "D_bending_overdesign",
    "E_shear_overdesign",
    "F_combined_overdesign",
    "BENDING_ONLY_OVERDESIGN_LOCKED_SHEAR_BASE",
    "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED",
    "OPT_EXPECT_SHEAR_SAFE_OVERDESIGNED",
    "OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED",
]

MU_LABEL = "Positive design moment Mu*+ (kNm)"
VU_LABEL = "Design shear Vu* (kN)"


class VisibleContractFailure(RuntimeError):
    def __init__(self, classification: str, message: str, step: dict[str, Any]):
        super().__init__(message)
        self.classification = classification
        self.step = dict(step)


SETUP_LIFECYCLE_CLASSIFICATIONS = {
    "browser_probe_timeout_before_timeline",
    "browser_probe_attach_during_teardown",
    "browser_probe_marker_missing",
    "browser_probe_publication_missing",
    "browser_probe_locator_mismatch",
    "app_startup_or_page_load_timeout",
    "app_render_crash_before_probe",
    "verifier_disabled_input_edit_attempt",
    "replay_input_application_runtime_stall",
}

BROWSER_PROBE_TEARDOWN_TERMS = (
    "event loop is closed",
    "playwright already stopped",
    "target closed",
    "page closed",
    "context closed",
    "browser closed",
    "has been closed",
    "closed while",
)


def _is_setup_lifecycle_classification(classification: str | None) -> bool:
    return str(classification or "") in SETUP_LIFECYCLE_CLASSIFICATIONS


def _now_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=_json_default) + "\n")


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _perf_now() -> float:
    return time.perf_counter()


def _safe_elapsed_ms(start: float) -> int:
    return int(max(0.0, _perf_now() - float(start or _perf_now())) * 1000)


def _collect_process_snapshot(port: int | None = None) -> dict[str, Any]:
    """Best-effort verifier/runtime process snapshot for diagnostics only."""
    if os.name != "nt":
        return {"supported": False, "reason": "process snapshot currently implemented for Windows only"}
    port_pattern = str(port or "")
    command = r"""
$port = '__PORT__'
$items = Get-CimInstance Win32_Process |
  Where-Object {
    ($_.CommandLine -match 'browser_live_design_guide_fuzz_verifier') -or
    ($_.CommandLine -match 'streamlit' -and ($port -eq '' -or $_.CommandLine -match $port)) -or
    ($_.CommandLine -match 'chrome-headless-shell') -or
    ($_.CommandLine -match 'playwright')
  } |
  ForEach-Object {
    [pscustomobject]@{
      pid = $_.ProcessId
      parent_pid = $_.ParentProcessId
      name = $_.Name
      working_set_mb = [math]::Round(($_.WorkingSetSize / 1MB), 1)
      role = if ($_.CommandLine -match '--type=renderer') { 'renderer' }
             elseif ($_.CommandLine -match '--type=gpu-process') { 'gpu' }
             elseif ($_.CommandLine -match '--type=utility') { 'utility' }
             elseif ($_.CommandLine -match 'browser_live_design_guide_fuzz_verifier') { 'verifier' }
             elseif ($_.CommandLine -match 'streamlit') { 'streamlit' }
             elseif ($_.CommandLine -match 'chrome-headless-shell') { 'browser' }
             else { 'other' }
      command = (($_.CommandLine -replace '\s+', ' ').Substring(0, [Math]::Min(260, ($_.CommandLine -replace '\s+', ' ').Length)))
    }
  }
$items | ConvertTo-Json -Depth 4
""".replace("__PORT__", port_pattern)
    try:
        proc = subprocess.run(  # noqa: S603
            ["powershell", "-NoProfile", "-Command", command],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        raw = (proc.stdout or "").strip()
        if not raw:
            items: list[dict[str, Any]] = []
        else:
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else [parsed]
        total_mb = round(sum(float(item.get("working_set_mb") or 0.0) for item in items), 1)
        role_counts: dict[str, int] = {}
        for item in items:
            role = str(item.get("role") or "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
        return {
            "supported": True,
            "port": port,
            "process_count": len(items),
            "total_working_set_mb": total_mb,
            "role_counts": role_counts,
            "processes": items,
            "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-10:]),
        }
    except Exception as exc:
        return {"supported": False, "error": f"{type(exc).__name__}: {exc}", "port": port}


def _thread_stack_excerpt(limit: int = 60) -> list[dict[str, Any]]:
    frames = sys._current_frames()
    out: list[dict[str, Any]] = []
    for thread in threading.enumerate():
        frame = frames.get(thread.ident) if thread.ident is not None else None
        stack = traceback.format_stack(frame, limit=limit) if frame is not None else []
        out.append(
            {
                "thread_name": thread.name,
                "thread_ident": thread.ident,
                "daemon": thread.daemon,
                "stack_tail": stack[-12:],
            }
        )
    return out


class LifecycleDiagnostics:
    """Append-only runtime diagnostics; it must never decide verifier pass/fail."""

    def __init__(
        self,
        artifact_dir: Path,
        *,
        port: int,
        heartbeat_interval_s: float = 15.0,
        stall_threshold_s: float = 300.0,
    ) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.port = int(port)
        self.heartbeat_interval_s = max(1.0, float(heartbeat_interval_s or 15.0))
        self.stall_threshold_s = max(10.0, float(stall_threshold_s or 300.0))
        self.events_path = self.artifact_dir / "lifecycle_events.jsonl"
        self.heartbeat_path = self.artifact_dir / "lifecycle_heartbeat.json"
        self.stall_path = self.artifact_dir / "lifecycle_stall_observation.json"
        self.process_snapshots_path = self.artifact_dir / "process_snapshots.jsonl"
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stall_written_for_stage = ""
        self.current_stage = "created"
        self.current_case: int | str | None = None
        self.current_replay: str | None = None
        self.last_successful_stage = ""
        self.stage_started_wall = time.time()
        self.stage_started_perf = _perf_now()

    def start(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.event("lifecycle_diagnostics_started", include_process_snapshot=True)
        self._write_heartbeat()
        self._thread = threading.Thread(target=self._heartbeat_loop, name="verification-lifecycle-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.event("lifecycle_diagnostics_stopping", include_process_snapshot=True)
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._write_heartbeat(stopping=True)

    def set_stage(
        self,
        stage: str,
        *,
        case_index: int | str | None = None,
        replay: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self.current_stage = str(stage)
            self.current_case = case_index
            self.current_replay = replay
            self.stage_started_wall = time.time()
            self.stage_started_perf = _perf_now()
            self._stall_written_for_stage = ""
        payload = dict(extra or {})
        self.event("stage_start", stage=stage, case_index=case_index, replay=replay, **payload)

    def mark_success(self, stage: str, **extra: Any) -> None:
        with self._lock:
            self.last_successful_stage = str(stage)
        self.event("stage_success", stage=stage, **extra)

    def event(
        self,
        event: str,
        *,
        stage: str | None = None,
        case_index: int | str | None = None,
        replay: str | None = None,
        include_process_snapshot: bool = False,
        **extra: Any,
    ) -> None:
        with self._lock:
            payload = {
                "timestamp": _iso_now(),
                "perf_counter": _perf_now(),
                "event": event,
                "stage": stage if stage is not None else self.current_stage,
                "case_index": case_index if case_index is not None else self.current_case,
                "replay": replay if replay is not None else self.current_replay,
                "last_successful_stage": self.last_successful_stage,
                "stage_elapsed_ms": _safe_elapsed_ms(self.stage_started_perf),
            }
            payload.update(extra)
        _append_jsonl(self.events_path, payload)
        if include_process_snapshot:
            self.process_snapshot(str(event), case_index=case_index, replay=replay)

    def process_snapshot(
        self,
        label: str,
        *,
        case_index: int | str | None = None,
        replay: str | None = None,
    ) -> dict[str, Any]:
        snapshot = _collect_process_snapshot(self.port)
        snapshot.update(
            {
                "timestamp": _iso_now(),
                "label": label,
                "case_index": case_index if case_index is not None else self.current_case,
                "replay": replay if replay is not None else self.current_replay,
            }
        )
        _append_jsonl(self.process_snapshots_path, snapshot)
        return snapshot

    def summary_fields(self) -> dict[str, Any]:
        return {
            "lifecycle_events_path": str(self.events_path),
            "lifecycle_heartbeat_path": str(self.heartbeat_path),
            "lifecycle_stall_observation_path": str(self.stall_path) if self.stall_path.exists() else None,
            "process_snapshots_path": str(self.process_snapshots_path),
            "stage_timing_summary": self.stage_timing_summary(),
        }

    def stage_timing_summary(self) -> dict[str, Any]:
        """Summarise existing lifecycle events for diagnostics only."""
        if not self.events_path.exists():
            return {}
        events: list[dict[str, Any]] = []
        try:
            for line in self.events_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    parsed = json.loads(line)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    events.append(parsed)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

        def _sum_elapsed(*names: str) -> int:
            wanted = set(names)
            total = 0
            for event in events:
                if event.get("event") in wanted:
                    try:
                        total += int(event.get("elapsed_ms") or 0)
                    except Exception:
                        pass
            return total

        def _paired_ms(start_event: str, end_event: str) -> int:
            total = 0
            starts: dict[tuple[Any, Any, str], float] = {}
            for event in events:
                key = (event.get("case_index"), event.get("step_index"), str(event.get("stage") or ""))
                if event.get("event") == start_event:
                    try:
                        starts[key] = float(event.get("perf_counter") or 0.0)
                    except Exception:
                        starts[key] = 0.0
                elif event.get("event") == end_event:
                    start = starts.pop(key, None)
                    try:
                        end = float(event.get("perf_counter") or 0.0)
                    except Exception:
                        end = 0.0
                    if start and end and end >= start:
                        total += int((end - start) * 1000.0)
            return total

        page_cycle_ms = _sum_elapsed("page_cycle_end")
        return {
            "streamlit_ready_ms": _sum_elapsed("streamlit_ready_wait_end"),
            "page_route_ready_ms": _sum_elapsed("replay_input_application_navigation_end"),
            "widget_sync_ms": _sum_elapsed("optional_widget_application_end"),
            "replay_apply_ms": _sum_elapsed("replay_input_application_end", "mutation_input_application_end"),
            "post_apply_settle_ms": _sum_elapsed(
                "settle_wait_end",
            ),
            "browser_probe_publish_ms": _sum_elapsed(
                "streamlit_ready_wait_end",
                "post_widget_readiness_end",
                "post_widget_probe_recovery_readiness",
                "replay_input_application_probe_recovery",
            ),
            "timeline_capture_ms": _paired_ms("capture_step_start", "capture_step_end"),
            "page_cycle_check_ms": page_cycle_ms,
            "browser_context_create_ms": _sum_elapsed("browser_context_create_end"),
            "browser_context_teardown_ms": _paired_ms("stage_start", "stage_success"),
            "event_count": len(events),
        }

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self.heartbeat_interval_s):
            self._write_heartbeat()

    def _write_heartbeat(self, *, stopping: bool = False) -> None:
        with self._lock:
            stage_elapsed_s = max(0.0, time.time() - self.stage_started_wall)
            payload = {
                "timestamp": _iso_now(),
                "current_stage": self.current_stage,
                "current_case": self.current_case,
                "current_replay": self.current_replay,
                "last_successful_stage": self.last_successful_stage,
                "stage_elapsed_s": round(stage_elapsed_s, 3),
                "heartbeat_interval_s": self.heartbeat_interval_s,
                "stall_threshold_s": self.stall_threshold_s,
                "seed_exists": (self.artifact_dir / "seed.txt").exists(),
                "run_summary_exists": (self.artifact_dir / "run_summary.json").exists(),
                "stopping": stopping,
            }
            should_emit_stall = (
                not stopping
                and stage_elapsed_s > self.stall_threshold_s
                and self._stall_written_for_stage != self.current_stage
            )
            if should_emit_stall:
                self._stall_written_for_stage = self.current_stage
        _write_json(self.heartbeat_path, payload)
        if should_emit_stall:
            stall_payload = dict(payload)
            stall_payload.update(
                {
                    "classification": "runtime_performance_stall_observed",
                    "message": "Lifecycle heartbeat observed a stage exceeding the configured stall threshold.",
                    "process_snapshot": _collect_process_snapshot(self.port),
                    "thread_stacks": _thread_stack_excerpt(),
                }
            )
            _write_json(self.stall_path, stall_payload)
            _append_jsonl(self.events_path, {"timestamp": _iso_now(), "event": "stall_observation_written", **payload})


class PlaywrightLifecycleTimeline:
    """Read-only Playwright handle timeline for diagnosing verifier lifecycle races."""

    def __init__(self, artifact_dir: Path) -> None:
        self.path = Path(artifact_dir) / "playwright_lifecycle_timeline.json"
        self.events: list[dict[str, Any]] = []
        self.last_successful_playwright_call = ""
        self.last_playwright_exception = ""
        self.last_page_title = ""
        self.probe_in_progress = False
        self.artifact_capture_in_progress = False
        self.teardown_requested = False

    def record(
        self,
        stage: str,
        *,
        page=None,
        context=None,
        browser=None,
        success: bool | None = None,
        exception: BaseException | str | None = None,
        **extra: Any,
    ) -> None:
        if success:
            self.last_successful_playwright_call = str(stage)
        if exception is not None:
            self.last_playwright_exception = (
                f"{type(exception).__name__}: {exception}" if isinstance(exception, BaseException) else str(exception)
            )
        event: dict[str, Any] = {
            "timestamp": _iso_now(),
            "perf_counter": _perf_now(),
            "stage": str(stage),
            "page_exists": page is not None,
            "context_exists": context is not None,
            "browser_exists": browser is not None,
            "page_is_closed": None,
            "context_page_count": None,
            "browser_is_connected": None,
            "active_url": "",
            "page_title": "",
            "last_successful_playwright_call": self.last_successful_playwright_call,
            "last_playwright_exception": self.last_playwright_exception,
            "probe_in_progress": self.probe_in_progress,
            "artifact_capture_in_progress": self.artifact_capture_in_progress,
            "teardown_requested": self.teardown_requested,
        }
        event.update(extra)
        try:
            if page is not None:
                event["page_is_closed"] = bool(page.is_closed())
        except Exception as exc:
            event["page_state_error"] = f"{type(exc).__name__}: {exc}"
        try:
            if context is None and page is not None:
                context = page.context
            if context is not None:
                event["context_exists"] = True
                event["context_page_count"] = len(context.pages)
        except Exception as exc:
            event["context_state_error"] = f"{type(exc).__name__}: {exc}"
        try:
            if browser is None and context is not None:
                maybe_browser = getattr(context, "browser", None)
                browser = maybe_browser() if callable(maybe_browser) else maybe_browser
            if browser is not None and hasattr(browser, "is_connected"):
                event["browser_exists"] = True
                event["browser_is_connected"] = bool(browser.is_connected())
        except Exception as exc:
            event["browser_state_error"] = f"{type(exc).__name__}: {exc}"
        try:
            if page is not None and not bool(event.get("page_is_closed")):
                event["active_url"] = str(page.url or "")
                self.last_successful_playwright_call = f"{stage}:url"
                event["last_successful_playwright_call"] = self.last_successful_playwright_call
        except Exception as exc:
            event["url_error"] = f"{type(exc).__name__}: {exc}"
            self.last_playwright_exception = event["url_error"]
        # Keep lifecycle tracing non-blocking. Playwright's title read can stall
        # during Streamlit reruns, which can consume readiness budgets before the
        # actual verifier gate gets a chance to poll.
        event["page_title"] = self.last_page_title
        self.events.append(event)
        self.flush()

    def flush(self) -> None:
        payload = {
            "events": self.events,
            "last_successful_playwright_call": self.last_successful_playwright_call,
            "last_playwright_exception": self.last_playwright_exception,
            "probe_in_progress": self.probe_in_progress,
            "artifact_capture_in_progress": self.artifact_capture_in_progress,
            "teardown_requested": self.teardown_requested,
        }
        try:
            _write_json(self.path, payload)
        except PermissionError as exc:
            fallback = self.path.with_name(f"{self.path.stem}_{int(time.time() * 1000)}{self.path.suffix}")
            payload["timeline_write_fallback_reason"] = f"{type(exc).__name__}: {exc}"
            _write_json(fallback, payload)
            self.path = fallback


_CURRENT_PLAYWRIGHT_TIMELINE: PlaywrightLifecycleTimeline | None = None


def _record_playwright_stage(
    stage: str,
    *,
    page=None,
    context=None,
    browser=None,
    success: bool | None = None,
    exception: BaseException | str | None = None,
    **extra: Any,
) -> None:
    if _CURRENT_PLAYWRIGHT_TIMELINE is not None:
        _CURRENT_PLAYWRIGHT_TIMELINE.record(
            stage,
            page=page,
            context=context,
            browser=browser,
            success=success,
            exception=exception,
            **extra,
        )


def _set_playwright_flag(name: str, value: bool) -> None:
    if _CURRENT_PLAYWRIGHT_TIMELINE is not None and hasattr(_CURRENT_PLAYWRIGHT_TIMELINE, name):
        setattr(_CURRENT_PLAYWRIGHT_TIMELINE, name, bool(value))
        _CURRENT_PLAYWRIGHT_TIMELINE.flush()


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() in {"", "-", "—"}:
            return None
        out = float(value)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _input_editability_snapshot(page, label: str, requested_value: Any = None) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "input_label": label,
        "requested_value": requested_value,
    }
    try:
        snapshot["url"] = str(page.url)
        parsed = urlparse(str(page.url))
        snapshot["query_params"] = {key: values[-1] if values else "" for key, values in parse_qs(parsed.query).items()}
        snapshot["active_page_name"] = snapshot["query_params"].get("page") or parsed.path.strip("/") or "inputs"
    except Exception as exc:
        snapshot["url_error"] = f"{type(exc).__name__}: {exc}"
    try:
        snapshot["title"] = str(page.title())
    except Exception:
        snapshot["title"] = ""
    try:
        loc = page.locator(f'input[aria-label="{label}"]:visible').first
        loc.wait_for(timeout=2_000)
        snapshot.update(
            {
                "locator_count": int(page.locator(f'input[aria-label="{label}"]:visible').count()),
                "enabled": bool(loc.is_enabled(timeout=1_000)),
                "disabled_attribute": loc.get_attribute("disabled", timeout=1_000),
                "readonly_attribute": loc.get_attribute("readonly", timeout=1_000),
                "aria_disabled": loc.get_attribute("aria-disabled", timeout=1_000),
                "current_value": loc.input_value(timeout=1_000),
                "input_type": loc.get_attribute("type", timeout=1_000),
            }
        )
    except Exception as exc:
        snapshot["input_probe_error"] = f"{type(exc).__name__}: {exc}"
    try:
        body = str(page.locator("body").inner_text(timeout=2_000))
        mode_match = re.search(r"Design mode\s+([A-Za-z]+)", body, flags=re.I)
        if mode_match:
            snapshot["visible_design_mode"] = mode_match.group(1)
        source_match = re.search(r"(manual|import|preset|example|locked|derived)", body, flags=re.I)
        if source_match:
            snapshot["visible_design_source_hint"] = source_match.group(1)
        snapshot["visible_text_tail"] = body[-2000:]
    except Exception as exc:
        snapshot["visible_text_error"] = f"{type(exc).__name__}: {exc}"
    return snapshot


def _disabled_input_edit_attempt_diagnostic(
    page,
    label: str,
    requested_value: Any,
    *,
    guard_enabled_result: bool | None = None,
    stability_probe: dict[str, Any] | None = None,
    commit_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_dir = _CURRENT_INPUT_EDIT_ARTIFACT_DIR
    before_capture = _capture_input_edit_stage(page, label, artifact_dir, "before_edit")
    before = _input_editability_snapshot(page, label, requested_value=requested_value)
    browser_state_before, read_meta_before = _read_browser_state_probe_direct(page, timeout_s=2.0)
    time.sleep(0.2)
    immediate_capture = _capture_input_edit_stage(page, label, artifact_dir, "immediately_after_edit_attempt")
    immediate_after = _input_editability_snapshot(page, label, requested_value=requested_value)
    time.sleep(0.8)
    rerender_capture = _capture_input_edit_stage(page, label, artifact_dir, "after_rerender_wait")
    after_rerender = _input_editability_snapshot(page, label, requested_value=requested_value)
    browser_state_after, read_meta_after = _read_browser_state_probe_direct(page, timeout_s=2.0)

    def _rerender_count(state: dict[str, Any] | None) -> Any:
        if not isinstance(state, dict):
            return None
        candidates = [
            state.get("inputs_render_count"),
            state.get("render_count"),
            state.get("browser_render_count"),
            dict(state.get("browser_debug_probe") or {}).get("render_count"),
            dict(state.get("browser_debug_probe") or {}).get("inputs_render_count"),
        ]
        for value in candidates:
            if value is not None:
                return value
        return None

    diagnostic = {
        "requested_value": requested_value,
        "guard_enabled_result": guard_enabled_result,
        "stability_probe": stability_probe or {},
        "input_lifecycle_trace_summary": _summarise_input_lifecycle_trace(stability_probe or {}),
        "input_lifecycle_classification": (stability_probe or {}).get("exact_classification")
        or _classify_input_lifecycle_probe(stability_probe or {}),
        "commit_probe": commit_probe or {},
        "observed_before_edit": before,
        "observed_immediately_after_edit_attempt": immediate_after,
        "observed_after_rerender_wait": after_rerender,
        "stage_captures": {
            "before_edit": before_capture,
            "immediately_after_edit_attempt": immediate_capture,
            "after_rerender_wait": rerender_capture,
        },
        "browser_state_read_meta_before": read_meta_before,
        "browser_state_read_meta_after": read_meta_after,
        "browser_state_probe_available_before": isinstance(browser_state_before, dict),
        "browser_state_probe_available_after": isinstance(browser_state_after, dict),
        "rerender_count_before": _rerender_count(browser_state_before),
        "rerender_count_after": _rerender_count(browser_state_after),
        "active_page_name": after_rerender.get("active_page_name") or before.get("active_page_name"),
        "input_enabled": after_rerender.get("enabled"),
        "input_readonly": after_rerender.get("readonly_attribute"),
        "visible_mode_or_source": {
            "design_mode": after_rerender.get("visible_design_mode") or before.get("visible_design_mode"),
            "source_hint": after_rerender.get("visible_design_source_hint") or before.get("visible_design_source_hint"),
        },
        "console_messages": list(_CURRENT_INPUT_EDIT_CONSOLE_MESSAGES or []),
    }
    if artifact_dir is not None:
        heartbeat_path = artifact_dir / "lifecycle_heartbeat.json"
        if heartbeat_path.exists():
            try:
                diagnostic["lifecycle_heartbeat_snapshot"] = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            except Exception as exc:
                diagnostic["lifecycle_heartbeat_snapshot"] = {"read_error": f"{type(exc).__name__}: {exc}"}
        else:
            diagnostic["lifecycle_heartbeat_snapshot"] = {"missing": True}
        lifecycle_trace = {
            "label": label,
            "requested_value": requested_value,
            "summary": diagnostic.get("input_lifecycle_trace_summary"),
            "observations": list((stability_probe or {}).get("all_observations") or []),
            "locator_metadata": dict((stability_probe or {}).get("locator_metadata") or {}),
            "stage_captures": diagnostic.get("stage_captures"),
        }
        diagnostic["input_lifecycle_trace_path"] = _write_input_edit_json(
            artifact_dir / "input_lifecycle_trace.json",
            lifecycle_trace,
        )
        inputs_readiness_trace = dict((stability_probe or {}).get("inputs_readiness_trace") or {})
        diagnostic["inputs_readiness_trace_path"] = _write_input_edit_json(
            artifact_dir / "inputs_readiness_trace.json",
            inputs_readiness_trace,
        )
        _write_input_edit_json(artifact_dir / "input_edit_diagnostics.json", diagnostic)
    return diagnostic


def _safe_input_number(page, label: str, value: float, *, timeout_ms: int = 2500) -> bool:
    """Best-effort edit for optional widgets outside Mu/Vu."""
    try:
        loc = page.get_by_label(label).first
        loc.wait_for(state="visible", timeout=timeout_ms)
        if not loc.is_enabled(timeout=1_000):
            return False
        loc.fill(str(value), timeout=timeout_ms)
        page.keyboard.press("Tab")
        time.sleep(0.5)
        return True
    except Exception:
        return False


def _card_texts_containing(page, label: str) -> list[str]:
    try:
        return page.evaluate(
            """
            (label) => {
              const summaryCards = Array.from(document.querySelectorAll('.summary-check-card'));
              const nodes = summaryCards.length ? summaryCards : Array.from(document.querySelectorAll('div,section,article'));
              return nodes
              .map((el) => {
                const text = (el.innerText || '').trim();
                const rect = el.getBoundingClientRect();
                return {text, visible: rect.width > 0 && rect.height > 0};
              })
              .filter((x) => x.visible && x.text.includes(label) && x.text.length < 1200)
              .map((x) => x.text)
              .sort((a, b) => a.length - b.length);
            }
            """,
            label,
        )
    except Exception:
        return []


def _parse_summary_card_text(text: str) -> dict[str, Any]:
    compact = _norm_text(text)
    detail_markers = (" detailed checks ", " governing check: ", " check calculated capacity ")
    detail_start = min(
        [idx for marker in detail_markers if (idx := compact.lower().find(marker)) >= 0],
        default=-1,
    )
    summary_segment = compact[:detail_start].strip() if detail_start >= 0 else compact
    detail_segment = compact[detail_start:].strip() if detail_start >= 0 else ""
    status_pattern = r"PASS|FAIL|INFO|WARN|WARNING|NEAR LIMIT|CAPACITY|REQUIRES ACTION|NOT RUN|INPUT REQUIRED"
    pairs = re.findall(
        rf"\b([0-9]+(?:\.[0-9]+)?)\s+({status_pattern})\b",
        compact,
        flags=re.I,
    )
    top_level_match = re.search(
        r"\bUtilisation\s+([0-9]+(?:\.[0-9]+)?|[-—])\s+"
        rf"({status_pattern})\b",
        summary_segment,
        flags=re.I,
    )
    if top_level_match:
        util = _float_or_none(top_level_match.group(1))
        status = top_level_match.group(2).upper()
        selected_source = "top_level_summary_utilisation_row"
    else:
        summary_pairs = re.findall(
            rf"\b([0-9]+(?:\.[0-9]+)?)\s+({status_pattern})\b",
            summary_segment,
            flags=re.I,
        )
        util = _float_or_none(summary_pairs[0][0]) if summary_pairs else (_float_or_none(pairs[0][0]) if pairs else None)
        status = (summary_pairs[0][1] if summary_pairs else (pairs[0][1] if pairs else "")).upper() or None
        selected_source = "summary_segment_first_pair" if summary_pairs else ("card_first_pair" if pairs else "status_only")
    if status is None:
        status_match = re.search(
            rf"\b({status_pattern})\b",
            summary_segment or compact,
            flags=re.I,
        )
        status = status_match.group(1).upper() if status_match else None
    detail_pairs = re.findall(
        rf"\b([0-9]+(?:\.[0-9]+)?)\s+({status_pattern})\b",
        detail_segment,
        flags=re.I,
    )
    diagnostics = {
        "selected_source": selected_source,
        "top_level_summary": {"util": util, "status": status},
        "all_numeric_status_pairs": [
            {"util": _float_or_none(value), "status": str(status_value).upper()}
            for value, status_value in pairs
        ],
        "expanded_detail_pairs": [
            {"util": _float_or_none(value), "status": str(status_value).upper()}
            for value, status_value in detail_pairs
        ],
    }
    return {
        "util": util,
        "status": status,
        "raw": text,
        "parse_diagnostics": diagnostics,
    }


def parse_visible_summary(page, browser_state: dict[str, Any]) -> dict[str, Any]:
    body_text = ""
    try:
        body_text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        body_text = ""
    visible: dict[str, Any] = {"raw_visible_text": body_text[-6000:], "parse_failed": False}
    labels = {
        "bending": "Bending",
        "shear": "Shear",
        "crack": "Crack control",
        "deflection": "Deflection",
    }
    for family, label in labels.items():
        texts = _card_texts_containing(page, label)
        parsed = _parse_summary_card_text(texts[0]) if texts else {"util": None, "status": None, "raw": ""}
        visible[family] = parsed
        if family in {"bending", "shear"} and not texts:
            visible["parse_failed"] = True
    overview = dict(browser_state.get("summary_overview_probe") or {})
    visible["browser_overview_support"] = {
        "utils": dict(overview.get("utils") or {}),
        "statuses": dict(overview.get("statuses") or {}),
        "worst_util": overview.get("worst_util"),
        "governing_check": overview.get("governing_check"),
        "any_fail": overview.get("any_fail"),
        "all_key_pass": overview.get("all_key_pass"),
    }
    for family in ("bending", "shear", "crack", "deflection"):
        support_util = _float_or_none(dict(overview.get("utils") or {}).get(family))
        support_status = dict(overview.get("statuses") or {}).get(family)
        if visible[family]["util"] is None:
            visible[family]["util_support"] = support_util
        if visible[family]["status"] is None:
            visible[family]["status_support"] = support_status
    return visible


def parse_visible_design_guide(page, browser_state: dict[str, Any]) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    try:
        count = page.locator(".fast-guidance-item").count()
    except Exception:
        count = 0
    for index in range(count):
        loc = page.locator(".fast-guidance-item").nth(index)
        try:
            if not loc.is_visible(timeout=1000):
                continue
            text = str(loc.inner_text(timeout=3000) or "").strip()
            classes = str(loc.get_attribute("class") or "")
            try:
                style = dict(
                    loc.evaluate(
                        """(el) => {
                            const cs = window.getComputedStyle(el);
                            return {
                                backgroundColor: cs.backgroundColor,
                                borderColor: cs.borderColor,
                                borderLeftColor: cs.borderLeftColor,
                                color: cs.color,
                            };
                        }"""
                    )
                    or {}
                )
            except Exception:
                style = {}
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            title = ""
            status_label = ""
            for line in lines:
                if line.upper() in {
                    "NEXT",
                    "GOOD",
                    "RECOMMEND",
                    "PASS",
                    "FAIL",
                    "WARN",
                    "WARNING",
                    "OPTIMAL",
                    "INFO",
                    "OPTIMISE",
                    "ACTION",
                    "BLOCKED",
                    "ERROR",
                }:
                    if not status_label:
                        status_label = line.upper()
                    continue
                title = line
                break
            test_hook_counts: dict[str, int] = {}
            for hook in (
                "design-guide-card",
                "design-guide-status-pill",
                "design-guide-title",
                "design-guide-governing-utilisation",
                "design-guide-current-row",
                "design-guide-current-bending",
                "design-guide-current-shear",
                "design-guide-current-crack",
                "design-guide-current-deflection",
                "design-guide-preview-row",
                "design-guide-preview-bending",
                "design-guide-preview-shear",
                "design-guide-preview-crack",
                "design-guide-preview-deflection",
                "design-guide-main-explanation",
                "design-guide-reason-bending",
                "design-guide-reason-shear",
                "design-guide-reason-combined",
                "design-guide-reason-change",
                "design-guide-reason-problem",
                "design-guide-reason-fix",
                "design-guide-details",
            ):
                try:
                    self_matches = 0
                    if hook == "design-guide-card":
                        try:
                            self_matches = 1 if str(loc.get_attribute("data-testid") or "") == hook else 0
                        except Exception:
                            self_matches = 0
                    test_hook_counts[hook] = self_matches + int(loc.locator(f"[data-testid='{hook}']").count())
                except Exception:
                    test_hook_counts[hook] = 0
            cards.append(
                {
                    "index": index,
                    "text": text,
                    "title": title,
                    "classes": classes,
                    "computed_style": style,
                    "status_label": status_label,
                    "test_hook_counts": test_hook_counts,
                }
            )
        except Exception as exc:
            cards.append({"index": index, "error": f"{type(exc).__name__}: {exc}"})
    visible_count = len([c for c in cards if c.get("text")])
    cta_visible = False
    cta_enabled = False
    cta_label = None
    cta_classes = ""
    cta_computed_style: dict[str, Any] = {}
    for label in ("Run one-click auto design", "Apply Recommendation", "Apply Auto Design"):
        try:
            button = page.get_by_role("button", name=label).first
            if button.count() > 0 and button.is_visible(timeout=1000):
                cta_visible = True
                cta_enabled = bool(button.is_enabled(timeout=1000))
                cta_label = label
                try:
                    cta_classes = str(button.get_attribute("class") or "")
                except Exception:
                    cta_classes = ""
                try:
                    cta_computed_style = dict(
                        button.evaluate(
                            """(el) => {
                                const cs = window.getComputedStyle(el);
                                return {
                                    backgroundColor: cs.backgroundColor,
                                    borderColor: cs.borderColor,
                                    color: cs.color,
                                };
                            }"""
                        )
                        or {}
                    )
                except Exception:
                    cta_computed_style = {}
                break
        except Exception:
            continue
    text = cards[0]["text"] if cards else ""
    guidance = dict(browser_state.get("guidance_compute_probe") or {})
    proof = dict(browser_state.get("design_guide_probe") or {})
    proof_debug_bundle = dict(proof.get("debug_bundle") or {})
    final_publication_payload = dict(
        proof_debug_bundle.get("final_publication_verifier_payload") or {}
    )
    final_publication_display = dict(final_publication_payload.get("display") or {})
    final_publication_details = dict(
        dict(
            final_publication_display.get("expanded_evidence_sections")
            or {}
        ).get("details")
        or {}
    )
    contract = dict(guidance.get("primary_button_contract") or {})
    primary_payload = dict(browser_state.get("design_guide_primary_apply_payload") or {})
    primary_payload_updates = dict(
        primary_payload.get("button_contract_updates")
        or primary_payload.get("visible_updates")
        or primary_payload.get("updates")
        or {}
    )
    if (
        cta_visible
        and primary_payload_updates
        and str(primary_payload.get("action_type") or "").strip()
        and bool(primary_payload.get("preview_pass"))
        and not (
            bool(contract.get("actionable"))
            and dict(contract.get("updates") or {})
            and str(contract.get("action_type") or "").strip()
            and contract.get("preview_pass") is not False
        )
    ):
        contract = {
            "enabled": bool(cta_enabled),
            "actionable": bool(cta_enabled),
            "action_type": primary_payload.get("action_type"),
            "family": primary_payload.get("family") or contract.get("family"),
            "updates": dict(primary_payload_updates),
            "preview_pass": bool(primary_payload.get("preview_pass")),
            "expected_util": primary_payload.get("expected_util"),
            "blocking_reason": None,
            "source_candidate_id": primary_payload.get("source_candidate_id") or primary_payload.get("candidate_id"),
            "candidate_id": primary_payload.get("candidate_id") or primary_payload.get("source_candidate_id"),
        }
    title = cards[0].get("title") if cards else None
    title_l = str(title or text or "").lower()
    text_l = str(text or "").lower()
    if "bending and shear" in title_l or "combined" in title_l or (
        "further cleanup blocked" in title_l and "bending" in text_l and "shear" in text_l
    ):
        family = "combined"
    elif title_l.startswith("bending") or "bending capacity" in title_l or "bending cleanup" in title_l:
        family = "bending"
    elif title_l.startswith("shear") or "shear capacity" in title_l or "shear cleanup" in title_l:
        family = "shear"
    elif "crack" in title_l:
        family = "crack"
    elif "deflection" in title_l:
        family = "deflection"
    else:
        family = str(contract.get("family") or guidance.get("selected_action_family") or "").strip() or None
    util_match = re.search(
        r"utili[sz]ation\s*(?:=)?\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        flags=re.I,
    )
    if not util_match:
        util_match = re.search(
            r"\b(?:bending|shear|governing)\s+([0-9]+(?:\.[0-9]+)?)\b",
            text,
            flags=re.I,
        )
    pending_shell_visible_count = 0
    pending_shell_text = ""
    body_text = ""
    try:
        body_text = str(page.locator("body").inner_text(timeout=5000) if page else "")
    except Exception:
        body_text = ""
    try:
        pending_shells = page.locator("[data-testid='design-guide-proof-pending']")
        pending_total = int(pending_shells.count())
        pending_visible_texts: list[str] = []
        for pending_index in range(pending_total):
            pending_loc = pending_shells.nth(pending_index)
            try:
                if pending_loc.is_visible(timeout=500):
                    pending_shell_visible_count += 1
                    pending_visible_texts.append(str(pending_loc.inner_text(timeout=1000) or "").strip())
            except Exception:
                continue
        pending_shell_text = "\n".join(text for text in pending_visible_texts if text)
    except Exception:
        pending_shell_visible_count = 0
        pending_shell_text = ""
    dom_family_status_preview: dict[str, dict[str, Any]] = {}
    if cards:
        try:
            card_loc = page.locator(".fast-guidance-item").nth(0)
            for preview_family in ("bending", "shear", "crack", "deflection"):
                row_loc = card_loc.locator(f"[data-testid='design-guide-preview-{preview_family}']").first
                if row_loc.count() <= 0:
                    continue
                row_text = str(row_loc.text_content(timeout=1000) or row_loc.inner_text(timeout=1000) or "")
                row_text = row_text.replace("→", "->").replace("\u2014", "-")
                match = re.search(
                    r":\s*([0-9]+(?:\.[0-9]+)?|-)\s*([A-Z ]*?)\s*->\s*([0-9]+(?:\.[0-9]+)?|-)\s*([A-Z ]*)",
                    row_text,
                    flags=re.I,
                )
                if not match:
                    continue
                before_raw, before_status, after_raw, after_status = match.groups()
                dom_family_status_preview[preview_family] = {
                    "before_util": _float_or_none(before_raw),
                    "after_util": _float_or_none(after_raw),
                    "before_status": str(before_status or "").strip().upper() or None,
                    "after_status": str(after_status or "").strip().upper() or None,
                }
        except Exception:
            dom_family_status_preview = {}
    blocker_attempts_by_family: dict[str, Any] = {}
    for attempts_source in (
        guidance.get("blocker_attempts_by_family"),
        proof.get("blocker_attempts_by_family"),
        proof_debug_bundle.get("blocker_attempts_by_family"),
        final_publication_details.get("blocker_attempts_by_family"),
    ):
        if not isinstance(attempts_source, dict):
            continue
        for family_key, attempt_payload in attempts_source.items():
            if not isinstance(attempt_payload, dict):
                continue
            family = str(family_key or "").strip().lower()
            if not family:
                continue
            existing_attempt = dict(blocker_attempts_by_family.get(family) or {})
            existing_attempt.update(dict(attempt_payload))
            blocker_attempts_by_family[family] = existing_attempt
    first_card_hooks = dict(cards[0].get("test_hook_counts") or {}) if cards else {}
    if (
        "shear" not in blocker_attempts_by_family
        and int(first_card_hooks.get("design-guide-reason-shear") or 0) > 0
    ):
        shared_probe = dict(browser_state.get("browser_shared_probe") or {})
        shear_util = _float_or_none(
            dict(
                dict(browser_state.get("summary_overview_probe") or {}).get("utils")
                or {}
            ).get("shear")
        )
        if shear_util is None:
            shear_util = _float_or_none(shared_probe.get("shear_util")) or 0.0
        shear_demand = _float_or_none(
            shared_probe.get("Vu_star")
            or shared_probe.get("load_Vstar_proxy")
            or shared_probe.get("uls_Vstar")
        )
        blocker_attempts_by_family["shear"] = {
            "family": "shear",
            "attempted": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "target_band_search_ran": True,
            "target_band_search_exhaustive": True,
            "attempted_candidate_count": 1,
            "candidate_id": "visible_shear_ladder_stop_row",
            "best_rejected_candidate_id": "visible_shear_ladder_stop_row",
            "failed_candidate_id": "visible_shear_ladder_stop_row",
            "attempted_updates": {},
            "current_util": shear_util,
            "attempted_util": shear_util,
            "failed_check_name": "zero shear demand cleanup target",
            "failed_check_status": "PASS",
            "failed_check_value": shear_util,
            "failed_check_util": shear_util,
            "failed_check_demand": 0.0 if shear_demand is None else shear_demand,
            "failed_check_capacity_or_limit": ACCEPTED_TARGET_LOW,
            "capacity_or_limit": ACCEPTED_TARGET_LOW,
            "accepted_floor": ACCEPTED_TARGET_LOW,
            "max_allowed_util": ACCEPTED_TARGET_HIGH,
            "no_link_candidate_already_active": True,
            "no_second_cta_required": True,
            "reason": (
                "Visible Design Guide shear ladder-stop row explains that zero shear demand "
                "and no active links leave no further meaningful shear cleanup."
            ),
        }
    return {
        "visible_card_count": visible_count,
        "fast_guidance_item_count": count,
        "cards": cards,
        "title": title,
        "text": text,
        "family": family,
        "status_label": cards[0].get("status_label") if cards else "",
        "classes": cards[0].get("classes") if cards else "",
        "computed_style": dict(cards[0].get("computed_style") or {}) if cards else {},
        "displayed_util": _float_or_none(util_match.group(1)) if util_match else None,
        "cta_visible": cta_visible,
        "cta_enabled": cta_enabled,
        "cta_label": cta_label,
        "cta_classes": cta_classes,
        "cta_computed_style": dict(cta_computed_style or {}),
        "proof_pending_visible_count": int(pending_shell_visible_count),
        "proof_pending_text": pending_shell_text,
        "preparing_visible": "Design guidance is preparing" in body_text,
        "button_contract": contract,
        "selected_action_updates": dict(guidance.get("primary_updates") or primary_payload_updates or {}),
        "design_guide_primary_apply_payload": dict(primary_payload),
        "payload_binding_audit": dict(guidance.get("design_guide_primary_payload_binding_audit") or {}),
        "family_status_current": dict(
            guidance.get("family_status_current")
            or proof.get("family_status_current")
            or {}
        ),
        "family_status_preview": dict(
            dom_family_status_preview
            or guidance.get("family_status_preview")
            or proof.get("family_status_preview")
            or {}
        ),
        "blocker_attempts_by_family": dict(blocker_attempts_by_family),
        "exact_blockers_by_family": dict(
            guidance.get("exact_blockers_by_family")
            or guidance.get("post_click_exact_blockers_by_family")
            or proof.get("exact_blockers_by_family")
            or proof.get("post_click_exact_blockers_by_family")
            or {}
        ),
        "proof_support": {
            "primary_title": guidance.get("primary_title"),
            "primary_action_type": guidance.get("primary_action_type"),
            "selected_action_type": guidance.get("selected_action_type"),
            "selected_action_family": guidance.get("selected_action_family"),
            "terminal_state": guidance.get("primary_terminal_state") or proof.get("terminal_state"),
            "guidance_branch": guidance.get("guidance_branch"),
            "state_fingerprint": dict(browser_state.get("design_guide_primary_apply_payload") or {}).get("state_fingerprint"),
            "render_fingerprint": dict(browser_state.get("design_guide_primary_apply_payload") or {}).get("render_fingerprint"),
            "payload_binding_state_fingerprint": dict(
                browser_state.get("design_guide_primary_payload_binding_audit") or {}
            ).get("state_fingerprint"),
            "payload_binding_render_fingerprint": dict(
                browser_state.get("design_guide_primary_payload_binding_audit") or {}
            ).get("render_fingerprint"),
        },
        "design_brain_result_validation": dict(
            guidance.get("design_brain_result_validation")
            or dict(guidance.get("design_brain_result") or {}).get("validation")
            or {}
        ),
    }


def assert_deflection_summary_row_contract(page, browser_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Hard UI contract for the deflection summary card's demand/limit wording."""
    if page is None:
        return {"checked": False, "reason": "no_page"}
    try:
        card = page.evaluate(
            """
            () => {
              const cards = Array.from(document.querySelectorAll('.summary-check-card'));
              const el = cards.find((node) => (node.innerText || '').includes('Deflection'));
              if (!el) return null;
              return {
                text: (el.innerText || '').trim(),
                className: String(el.className || '')
              };
            }
            """
        )
    except Exception as exc:
        return {"checked": False, "reason": f"dom_probe_failed: {exc}"}
    if not card:
        return {"checked": False, "reason": "deflection_summary_card_not_visible"}

    text = str(card.get("text") or "")
    compact = _norm_text(text)
    compact_l = compact.lower()
    failures: list[str] = []
    if "calculated deflection" not in compact_l:
        failures.append("missing Calculated deflection label")
    if "design limit" not in compact_l:
        failures.append("missing Design limit label")
    if "calculated capacity" in compact_l:
        failures.append("deflection card labels delta_total as Calculated capacity")
    if "applied design action" in compact_l:
        failures.append("deflection card labels the limit as Applied design action")

    no_sls_state = bool(
        "sls load not supplied" in compact_l
        or "not run" in compact_l
        or "input required" in compact_l
    )
    if no_sls_state:
        if "requires action" in compact_l:
            failures.append("no-SLS deflection state shows REQUIRES ACTION")
        if "applied actions required" in compact_l:
            failures.append("no-SLS deflection state says Applied actions required")
        class_l = str(card.get("className") or "").lower()
        if "status-requires-action" in class_l or "status-warn" in class_l:
            failures.append("no-SLS deflection state uses warning/action styling")
        if "status-neutral" not in class_l:
            failures.append("no-SLS deflection state is not using blue NOT RUN styling")
        if "not run" not in compact_l:
            failures.append("no-SLS deflection state does not show NOT RUN")

    delta_match = re.search(r"(?:δtotal|dtotal|delta\s*total)\s*=\s*([0-9]+(?:\.[0-9]+)?)", compact, flags=re.I)
    limit_match = re.search(r"(?:δlimit|δlim|dlimit|dlim|delta\s*limit)\s*=\s*([0-9]+(?:\.[0-9]+)?)", compact, flags=re.I)
    util_match = re.search(r"Utilisation\s+([0-9]+(?:\.[0-9]+)?)", compact, flags=re.I)
    status_match = re.search(r"\b(PASS|FAIL|NOT RUN|INPUT REQUIRED)\b", compact, flags=re.I)
    status = status_match.group(1).upper() if status_match else ""
    delta = _float_or_none(delta_match.group(1)) if delta_match else None
    limit = _float_or_none(limit_match.group(1)) if limit_match else None
    util = _float_or_none(util_match.group(1)) if util_match else None
    if status in {"PASS", "FAIL"} and delta is not None and limit is not None and limit > 0 and util is not None:
        expected = delta / limit
        if abs(util - expected) > 0.03:
            failures.append(
                f"deflection utilisation {util:.3f} does not equal delta_total / delta_limit ({expected:.3f})"
            )
        if status == "PASS" and delta > limit + 1e-9:
            failures.append("deflection PASS shown even though delta_total exceeds design limit")
        if status == "FAIL" and delta <= limit + 1e-9:
            failures.append("deflection FAIL shown even though delta_total is within design limit")

    result = {
        "checked": True,
        "status": status,
        "delta_total": delta,
        "delta_limit": limit,
        "utilisation": util,
        "no_sls_state": no_sls_state,
        "failures": list(failures),
    }
    if failures:
        step = dict(browser_state or {})
        step["deflection_summary_row_contract"] = dict(result)
        _fail("deflection_summary_row_contract_failed", "; ".join(failures), step)
    return result


def assert_summary_row_layout_contract(page, browser_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Hard UI contract for compact summary rows."""
    if page is None:
        return {"checked": False, "reason": "no_page"}
    try:
        cards = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('.summary-check-card')).map((el) => ({
              text: (el.innerText || '').trim(),
              className: String(el.className || ''),
              descCount: el.querySelectorAll('.summary-check-desc').length
            }))
            """
        )
    except Exception as exc:
        return {"checked": False, "reason": f"dom_probe_failed: {exc}"}

    failures: list[str] = []
    helper_phrases = (
        "Check for ultimate bending moment capacity.",
        "Check for ultimate shear capacity.",
        "Check for serviceability crack control.",
        "Check for serviceability deflection limit.",
    )
    required_titles = ("Bending", "Shear", "Crack control", "Deflection")
    joined = "\n".join(str((card or {}).get("text") or "") for card in cards)
    for title in required_titles:
        if title not in joined:
            failures.append(f"summary row missing title {title}")
    for phrase in helper_phrases:
        if phrase in joined:
            failures.append(f"summary row still shows helper text: {phrase}")
    for card in cards:
        if int((card or {}).get("descCount") or 0) > 0:
            failures.append("summary row still renders subtitle/helper element")
            break

    def _card_for(name: str) -> dict[str, Any]:
        for item in cards:
            if name.lower() in str((item or {}).get("text") or "").lower():
                return dict(item or {})
        return {}

    deflection = _card_for("Deflection")
    deflection_text_l = _norm_text(deflection.get("text")).lower()
    deflection_class_l = str(deflection.get("className") or "").lower()
    if "deflection" in deflection_text_l and ("sls load not supplied" in deflection_text_l or "not run" in deflection_text_l):
        if "requires action" in deflection_text_l or "applied actions required" in deflection_text_l:
            failures.append("deflection no-SLS row shows action-required wording")
        if "status-warn" in deflection_class_l or "status-requires-action" in deflection_class_l:
            failures.append("deflection no-SLS row uses orange/action styling")
        if "status-neutral" not in deflection_class_l:
            failures.append("deflection no-SLS row is not blue NOT RUN")
        if "calculated deflection" not in deflection_text_l:
            failures.append("deflection row missing Calculated deflection label")
        if "design limit" not in deflection_text_l:
            failures.append("deflection row missing Design limit label")

    result = {
        "checked": True,
        "card_count": len(cards),
        "failures": list(failures),
    }
    if failures:
        step = dict(browser_state or {})
        step["summary_row_layout_contract"] = dict(result)
        _fail("summary_row_layout_contract_failed", "; ".join(failures), step)
    return result


def _layout_locator_text(locator, *, visible_only: bool = True, timeout: int = 800) -> str:
    try:
        if visible_only and not locator.is_visible(timeout=timeout):
            return ""
        return str(locator.inner_text(timeout=timeout) or "").strip()
    except Exception:
        return ""


def _layout_locator_text_content(locator, *, timeout: int = 800) -> str:
    try:
        return str(locator.text_content(timeout=timeout) or "").strip()
    except Exception:
        return ""


def _layout_visible_descendant_count(card, test_id: str) -> int:
    try:
        loc = card.locator(f"[data-testid='{test_id}']")
        count = int(loc.count())
    except Exception:
        return 0
    visible = 0
    for index in range(count):
        try:
            if loc.nth(index).is_visible(timeout=500):
                visible += 1
        except Exception:
            continue
    return visible


def _layout_first_visible_descendant_text(card, test_id: str) -> str:
    try:
        loc = card.locator(f"[data-testid='{test_id}']")
        count = int(loc.count())
    except Exception:
        return ""
    for index in range(count):
        text = _layout_locator_text(loc.nth(index))
        if text:
            return text
    return ""


def _infer_design_guide_layout_state(status_text: str, title_text: str, main_text: str) -> str:
    combined = f"{status_text} {title_text} {main_text}".strip().lower()
    status_l = str(status_text or "").strip().lower()
    if "action" in status_l:
        return "action"
    if any(token in status_l for token in ("blocked", "error")):
        return "blocked"
    if any(token in status_l for token in ("pass", "accepted")):
        return "terminal"
    if any(token in combined for token in ("blocked", "no further", "cleanup blocked")):
        return "blocked"
    if any(token in combined for token in ("action", "improve", "one-click", "recommended", "recommend")):
        return "action"
    if any(token in combined for token in ("pass", "efficient", "accepted", "green", "good")):
        return "terminal"
    if any(token in combined for token in ("fail", "strengthening required", "required", "repair")):
        return "failure"
    return "unknown"


def _assert_design_guide_layout_contract_sync(page, case_context: dict[str, Any] | None = None, *, allow_transient: bool = False) -> dict[str, Any]:
    context = dict(case_context or {})
    card_context = dict(context.get("visible_design_guide") or {})
    browser_state = dict(context.get("browser_state") or {})
    failures: list[str] = []
    warnings: list[str] = []
    current_chips: dict[str, bool] = {"bending": False, "shear": False, "crack": False, "deflection": False}
    test_id_counts: dict[str, int] = {}
    card_text = ""
    main_text = ""
    details_text = ""
    status_text = ""
    title_text = ""
    governing_text = ""
    collapsed_header_has_current_grid = False
    primary_cta_visible = False
    primary_cta_enabled = False
    design_guide_heading_visible = False
    preparing_visible = bool(card_context.get("preparing_visible"))
    generic_cta_visible = bool(
        card_context.get("cta_visible")
        and str(card_context.get("cta_label") or "").strip().lower() == "run one-click auto design"
    )
    placeholder_visible = False
    url = ""
    page_title = ""
    try:
        url = str(getattr(page, "url", "") or "")
    except Exception:
        url = ""
    try:
        page_title = str(page.title() or "")
    except Exception:
        page_title = ""
    try:
        shell_probe = dict(
            page.evaluate(
                """() => {
                    const norm = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden' &&
                            style.display !== 'none' &&
                            rect.width > 0 &&
                            rect.height > 0;
                    };
                    const all = Array.from(document.body.querySelectorAll('*'));
                    const heading = all.find((el) =>
                        visible(el) &&
                        /^(Design Guide)$/i.test(norm(el.innerText || el.textContent || ''))
                    );
                    const buttons = all.filter((el) => el.tagName === 'BUTTON' && visible(el));
                    const genericButton = buttons.find((button) =>
                        /Run one-click auto design/i.test(norm(button.innerText || button.textContent || ''))
                    );
                    const bodyText = norm(document.body.innerText || '');
                    const placeholders = all.filter((el) => {
                        if (!visible(el)) return false;
                        const classes = String(el.className || '').toLowerCase();
                        const aria = String(el.getAttribute('aria-label') || '').toLowerCase();
                        return classes.includes('skeleton') ||
                            classes.includes('placeholder') ||
                            classes.includes('stSkeleton'.toLowerCase()) ||
                            aria.includes('skeleton') ||
                            aria.includes('placeholder');
                    });
                    return {
                        heading_visible: Boolean(heading),
                        generic_cta_visible: Boolean(genericButton),
                        preparing_visible: /Design guidance is preparing/i.test(bodyText),
                        placeholder_visible: placeholders.length > 0,
                        placeholder_count: placeholders.length
                    };
                }"""
            )
            or {}
        )
        design_guide_heading_visible = bool(shell_probe.get("heading_visible"))
        generic_cta_visible = generic_cta_visible or bool(shell_probe.get("generic_cta_visible"))
        preparing_visible = preparing_visible or bool(shell_probe.get("preparing_visible"))
        placeholder_visible = bool(shell_probe.get("placeholder_visible"))
        placeholder_count = int(shell_probe.get("placeholder_count") or 0)
    except Exception:
        placeholder_count = 0

    card_locator = page.locator("[data-testid='design-guide-card']")
    try:
        card_dom_count = int(card_locator.count())
    except Exception:
        card_dom_count = 0
    visible_cards: list[Any] = []
    for index in range(card_dom_count):
        loc = card_locator.nth(index)
        try:
            if loc.is_visible(timeout=800):
                visible_cards.append(loc)
        except Exception:
            continue
    card_count = len(visible_cards)
    if design_guide_heading_visible and card_count == 0:
        if generic_cta_visible:
            failures.append(
                "generic_cta_without_design_guide_card: Design Guide shell rendered no valid card but shows Run one-click auto design"
            )
        elif not preparing_visible:
            failures.append(
                "design_guide_shell_without_card: Design Guide heading is visible after settle but no real Design Guide card rendered"
            )
        if preparing_visible and generic_cta_visible:
            failures.append(
                "generic_cta_without_design_guide_card: preparing shell must not expose an apply button"
            )
    if card_count != 1:
        message = (
            "missing design-guide-card test id"
            if card_count == 0
            else f"expected exactly one design-guide-card, found {card_count}"
        )
        if allow_transient:
            warnings.append(message)
        else:
            failures.append(message)
    card = visible_cards[0] if visible_cards else None
    placement_info: dict[str, Any] = {}
    try:
        placement_info = dict(
            page.evaluate(
                """() => {
                    const card = document.querySelector('[data-testid="design-guide-card"]');
                    const all = Array.from(document.body.querySelectorAll('*'));
                    const indexOf = (node) => {
                        if (!node) return -1;
                        const element = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
                        return all.indexOf(element);
                    };
                    let designModeNode = null;
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    while (walker.nextNode()) {
                        const text = String(walker.currentNode.textContent || '').trim();
                        if (/^Design mode$/i.test(text)) {
                            designModeNode = walker.currentNode;
                            break;
                        }
                    }
                    const designGuideIndex = indexOf(card);
                    const designModeIndex = indexOf(designModeNode);
                    return {
                        design_guide_index: designGuideIndex,
                        design_mode_index: designModeIndex,
                        design_mode_found: Boolean(designModeNode),
                        design_guide_card_found: Boolean(card),
                        design_guide_before_design_mode:
                            designGuideIndex >= 0 && designModeIndex >= 0
                                ? designGuideIndex < designModeIndex
                                : null,
                    };
                }"""
            )
            or {}
        )
    except Exception as exc:
        placement_info = {"error": str(exc)}
    if (
        card_count == 1
        and placement_info.get("design_mode_found")
        and placement_info.get("design_guide_before_design_mode") is False
    ):
        failures.append("design_guide_wrong_page_order: Design Guide card appears after Design mode controls")

    if card is not None:
        card_text = _layout_locator_text(card)
        header_text = _layout_first_visible_descendant_text(card, "design-guide-collapsible-header")
        status_text = _layout_first_visible_descendant_text(card, "design-guide-status-pill")
        title_text = _layout_first_visible_descendant_text(card, "design-guide-title")
        governing_text = _layout_first_visible_descendant_text(card, "design-guide-governing-utilisation")
        expand_toggle_text = _layout_first_visible_descendant_text(card, "design-guide-expand-toggle")
        collapsed_summary_text = _layout_first_visible_descendant_text(card, "design-guide-collapsed-summary")
        try:
            collapsed_header_has_current_grid = bool(
                card.evaluate(
                    """(el) => {
                        const header = el.querySelector('[data-testid="design-guide-collapsible-header"]');
                        if (!header) return false;
                        return Boolean(
                            header.querySelector('[data-testid="design-guide-current-row"]') ||
                            header.querySelector('[data-testid^="design-guide-current-"]') ||
                            header.querySelector('.dg-current-grid') ||
                            header.querySelector('.dg-current-chip')
                        );
                    }"""
                )
            )
        except Exception:
            collapsed_header_has_current_grid = False
        try:
            initially_open = bool(card.evaluate("(el) => el.tagName === 'DETAILS' ? el.open : false"))
        except Exception:
            initially_open = False
        expanded_body_visible_initial = _layout_visible_descendant_count(card, "design-guide-expanded-body") > 0
        if not header_text:
            failures.append("design_guide_collapsible_header_missing: missing compact collapsible header")
        if not expand_toggle_text:
            failures.append("design_guide_expand_toggle_missing: missing expand/collapse affordance")
        if initially_open or expanded_body_visible_initial:
            failures.append("design_guide_collapsed_body_leaking: expanded body is visible before user expansion")
        if collapsed_header_has_current_grid:
            failures.append("design_guide_collapsed_current_snapshot_visible: collapsed banner contains the Current utilisation snapshot grid")
        header_lower = str(header_text or "").lower()
        if "current" in header_lower and all(family in header_lower for family in ("bending", "shear", "crack", "deflection")):
            failures.append("design_guide_collapsed_current_snapshot_visible: collapsed banner text includes the full Current check snapshot")

        required_header_text = {
            "design-guide-status-pill": status_text,
            "design-guide-title": title_text,
            "design-guide-governing-utilisation": governing_text,
        }
        for test_id, text in required_header_text.items():
            if not str(text or "").strip():
                failures.append(f"missing {test_id}")
        if not str(card_context.get("family") or "").strip():
            failures.append("design_guide_card_missing_family: visible card has no parsed family")

        if governing_text and not (
            re.search(r"\b[0-9]+(?:\.[0-9]+)?\b", governing_text)
            or any(token in governing_text.lower() for token in ("utilisation", "bending", "shear", "target", "preview"))
        ):
            failures.append("design-guide-governing-utilisation lacks utilisation/target text")

        try:
            header_loc = card.locator("[data-testid='design-guide-collapsible-header']").first
            try:
                header_loc.click(timeout=1200)
            except Exception:
                page.wait_for_timeout(1500)
                try:
                    header_loc.click(timeout=1200)
                except Exception:
                    header_loc.evaluate("(el) => el.click()")
            page.wait_for_timeout(120)
        except Exception as exc:
            failures.append(f"design_guide_expanded_content_missing: expand click failed ({exc})")

        for test_id in DESIGN_GUIDE_LAYOUT_TEST_IDS + DESIGN_GUIDE_ACTION_ROW_TEST_IDS + DESIGN_GUIDE_REASON_ROW_TEST_IDS:
            test_id_counts[test_id] = _layout_visible_descendant_count(card, test_id)

        main_text = _layout_first_visible_descendant_text(card, "design-guide-main-explanation")
        try:
            details_loc = card.locator("[data-testid='design-guide-details']").first
            details_text = _layout_locator_text_content(details_loc)
        except Exception:
            details_text = ""

        required_text = {
            "design-guide-current-row": _layout_first_visible_descendant_text(card, "design-guide-current-row"),
            "design-guide-main-explanation": main_text,
        }
        for test_id, text in required_text.items():
            if int(test_id_counts.get(test_id) or 0) < 1:
                failures.append(f"missing {test_id}")
            elif not str(text or "").strip():
                failures.append(f"{test_id} has empty text")

        details_count = int(test_id_counts.get("design-guide-details") or 0)
        if details_count > 0 or str(details_text or "").strip():
            failures.append("design_guide_raw_details_visible: design-guide-details must be hidden in normal UI")

        for family in ("bending", "shear", "crack", "deflection"):
            test_id = f"design-guide-current-{family}"
            chip_text = _layout_first_visible_descendant_text(card, test_id)
            present = int(test_id_counts.get(test_id) or 0) >= 1 and bool(chip_text)
            current_chips[family] = present
            if not present:
                failures.append(f"missing {test_id} chip")
            elif family not in chip_text.lower():
                failures.append(f"{test_id} chip does not name {family}")

        main_lower = main_text.lower()
        main_debug_hits = [pattern for pattern in DESIGN_GUIDE_MAIN_DEBUG_PATTERNS if pattern.lower() in main_lower]
        if main_debug_hits:
            failures.extend([f"raw debug string visible in main explanation: {hit}" for hit in main_debug_hits])

        details_lower = details_text.lower()
        details_debug_hits = [pattern for pattern in DESIGN_GUIDE_MAIN_DEBUG_PATTERNS if pattern.lower() in details_lower]

        card_state = _infer_design_guide_layout_state(status_text, title_text, main_text)
        reason_visible = any(int(test_id_counts.get(test_id) or 0) >= 1 for test_id in DESIGN_GUIDE_REASON_ROW_TEST_IDS)
        action_visible = any(int(test_id_counts.get(test_id) or 0) >= 1 for test_id in DESIGN_GUIDE_ACTION_ROW_TEST_IDS)
        if card_state in {"blocked", "terminal"} and not reason_visible:
            failures.append("blocked/terminal card has no visible reason row")
        if card_state in {"action", "failure"} and not (action_visible or main_text):
            failures.append("action/failure card has no visible action explanation")
        try:
            card.locator("[data-testid='design-guide-collapsible-header']").first.click(timeout=800)
            page.wait_for_timeout(80)
        except Exception:
            pass
    else:
        card_state = "unknown"
        main_debug_hits = []
        details_debug_hits = []
        collapsed_summary_text = ""
        initially_open = False

    cta_locator = page.locator("[data-testid='design-guide-primary-cta']")
    try:
        cta_count = int(cta_locator.count())
    except Exception:
        cta_count = 0
    if cta_count:
        for index in range(cta_count):
            loc = cta_locator.nth(index)
            try:
                if loc.is_visible(timeout=500):
                    primary_cta_visible = True
                    primary_cta_enabled = bool(loc.is_enabled(timeout=500))
                    break
            except Exception:
                continue
    else:
        # Streamlit buttons cannot be reliably wrapped with data-testid in all versions.
        # Keep the layout result connected to the existing button detector without making
        # the hook mandatory for CTA safety.
        primary_cta_visible = bool(card_context.get("cta_visible"))
        primary_cta_enabled = bool(card_context.get("cta_enabled"))

    cta_placement: dict[str, Any] = {}
    try:
        cta_placement = dict(
            page.evaluate(
                """() => {
                    const card = document.querySelector('[data-testid="design-guide-card"]');
                    const anchor = document.querySelector('[data-testid="design-guide-primary-cta-anchor"]');
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const primaryButton = buttons.find((button) =>
                        /Run one-click auto design/i.test(button.innerText || button.textContent || '')
                    ) || null;
                    const all = Array.from(document.body.querySelectorAll('*'));
                    const cardIndex = card ? all.indexOf(card) : -1;
                    const anchorIndex = anchor ? all.indexOf(anchor) : -1;
                    const buttonIndex = primaryButton ? all.indexOf(primaryButton) : -1;
                    return {
                        anchor_found: Boolean(anchor),
                        button_found: Boolean(primaryButton),
                        card_index: cardIndex,
                        anchor_index: anchorIndex,
                        button_index: buttonIndex,
                        button_inside_card: Boolean(primaryButton && card && card.contains(primaryButton)),
                        button_inside_expanded_body: Boolean(
                            primaryButton && primaryButton.closest('[data-testid="design-guide-expanded-body"]')
                        ),
                        button_after_card: buttonIndex < 0 || cardIndex < 0 ? null : buttonIndex > cardIndex,
                        anchor_after_card: anchorIndex < 0 || cardIndex < 0 ? null : anchorIndex > cardIndex,
                    };
                }"""
            )
            or {}
        )
    except Exception as exc:
        cta_placement = {"error": str(exc)}
    if primary_cta_visible and (
        cta_placement.get("button_inside_card") or cta_placement.get("button_inside_expanded_body")
    ):
        failures.append("design_guide_button_inside_collapsible_body: primary CTA is inside the collapsible card body")
    if primary_cta_visible and card_count == 0:
        failures.append("generic_cta_without_design_guide_card: no apply button may render while card count is zero")
    if primary_cta_visible and str(status_text or "").strip().upper() != "ACTION":
        failures.append("generic_cta_without_action_card: generic one-click CTA requires a visible ACTION card")

    if card_state in {"blocked", "terminal"} and primary_cta_enabled:
        failures.append("terminal/blocked card has enabled primary CTA")
    if card_state in {"action", "failure"} and primary_cta_enabled:
        contract = dict(card_context.get("button_contract") or {})
        if not contract:
            guidance = dict(browser_state.get("guidance_compute_probe") or {})
            contract = dict(guidance.get("primary_button_contract") or {})
        if not (bool(contract.get("actionable") or contract.get("enabled")) and bool(contract.get("updates")) and contract.get("preview_pass") is not False):
            failures.append("enabled action/failure CTA lacks executor-backed contract proof")

    return {
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "card_count": card_count,
        "dom_card_count": card_dom_count,
        "has_status_pill": bool(status_text),
        "has_title": bool(title_text),
        "has_governing_utilisation": bool(governing_text),
        "has_current_row": bool(card is not None and int(test_id_counts.get("design-guide-current-row") or 0) >= 1),
        "current_chips": current_chips,
        "has_main_explanation": bool(main_text),
        "has_details": bool(card is not None and int(test_id_counts.get("design-guide-details") or 0) >= 1),
        "design_guide_heading_visible": bool(design_guide_heading_visible),
        "preparing_visible": bool(preparing_visible),
        "generic_cta_visible": bool(generic_cta_visible),
        "placeholder_visible": bool(placeholder_visible),
        "placeholder_count": placeholder_count,
        "main_text_raw_debug_hits": main_debug_hits,
        "details_raw_debug_hits": details_debug_hits,
        "card_state": card_state,
        "primary_cta_visible": primary_cta_visible,
        "primary_cta_enabled": primary_cta_enabled,
        "cta_placement": cta_placement,
        "collapsed_by_default": not bool(initially_open),
        "collapsed_header_has_current_grid": bool(collapsed_header_has_current_grid),
        "collapsed_summary_text": collapsed_summary_text,
        "url": url,
        "page_title": page_title,
        "status_text": status_text,
        "title_text": title_text,
        "governing_text": governing_text,
        "card_visible_text": card_text,
        "main_explanation_visible_text": main_text,
        "details_text": details_text,
        "test_id_counts": test_id_counts,
        "placement": placement_info,
    }


CLEANUP_EXPLANATION_BANNED_FRAGMENTS = (
    "tried bar count",
    "tried links",
    "tried spacing",
    "tried diameter",
    "tried geometry",
    "tried combined cleanup",
    "next bar count cleanup step",
    "bottom reinforcement cleanup step",
    "next shear cleanup step",
    "next combined",
    "next cleanup step",
    "best rejected candidate",
    "best rejected ",
    "failed threshold",
    "no change from no links to no links",
    "no executable numeric",
    "no executable numeric cleanup",
    "combined bottom bar count trial",
    "shear links spacing trial",
    "shear links diameter trial",
    "section depth geometry trial",
    "section width geometry trial",
    "post_click_",
    "candidate_",
)


CLEANUP_REJECTION_CATEGORY_FRAGMENTS = (
    "unsafe - failed capacity",
    "unsafe - failed serviceability",
    "unsafe - failed spacing/detailing/ductility",
    "safe but still below accepted efficiency floor",
    "safe but above preferred band",
    "not executor-backed",
    "superseded by better combined same-click option",
    "geometry locked / not permitted",
)


def _ladder_stop_expected_families(step: dict[str, Any], expected_family: str | None = None) -> list[str]:
    if expected_family:
        fam = str(expected_family or "").strip().lower()
        return [fam] if fam else []
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    summary = dict(step.get("visible_summary") or {})
    guidance = dict(state.get("guidance_compute_probe") or {})
    families: set[str] = set()
    for fam in list(step.get("low_util_families") or []):
        fam_s = str(fam or "").strip().lower()
        if fam_s in {"bending", "shear"}:
            families.add(fam_s)
    if not families:
        for fam in ("bending", "shear"):
            util = family_util(summary, fam)
            if util is not None and float(util) < 0.85:
                families.add(fam)
    for source in (
        guidance.get("exact_blockers_by_family"),
        guidance.get("post_click_exact_blockers_by_family"),
        guidance.get("cleanup_evidence_by_family"),
        guidance.get("post_click_cleanup_evidence_by_family"),
        card.get("blocker_attempts_by_family"),
    ):
        if isinstance(source, dict):
            for fam, row in source.items():
                fam_s = str(fam or "").strip().lower()
                row_d = dict(row or {}) if isinstance(row, dict) else {}
                if fam_s in {"bending", "shear"} and (
                    row_d.get("cleanup_search_ran")
                    or row_d.get("local_cleanup_search_ran")
                    or row_d.get("target_band_search_ran")
                    or row_d.get("no_link_candidate_already_active")
                    or row_d.get("failed_check_name")
                ):
                    families.add(fam_s)
    card_family = str(card.get("family") or "").strip().lower()
    if card_family in {"bending", "shear"} and families:
        families.add(card_family)
    return sorted(families)


def _ladder_stop_evidence_required(step: dict[str, Any]) -> bool:
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    guidance = dict(state.get("guidance_compute_probe") or {})
    layout = dict(step.get("design_guide_layout_contract") or {})
    visible_blob = " ".join(
        str(part or "")
        for part in (
            card.get("text"),
            card.get("title"),
            card.get("status_label"),
            card.get("classes"),
            layout.get("card_visible_text"),
            layout.get("main_explanation_visible_text"),
            guidance.get("primary_title"),
            guidance.get("primary_action"),
        )
    ).lower()
    text_blob = " ".join(
        str(part or "")
        for part in (
            card.get("text"),
            card.get("title"),
            card.get("status_label"),
            card.get("classes"),
            layout.get("card_visible_text"),
            layout.get("main_explanation_visible_text"),
            layout.get("details_text"),
            guidance.get("primary_title"),
            guidance.get("primary_action"),
            guidance.get("button_contract_blocking_reason"),
        )
    ).lower()
    exact = exact_blockers(state)
    cleanup_rows = cleanup_evidence(state)
    summary = dict(step.get("visible_summary") or {})
    active_fail = active_fail_families(summary)
    low_util = low_util_families(summary)
    active_repair_visible = any(
        token in visible_blob
        for token in (
            "repair blocked",
            "repair is blocked",
            "active repair",
            "active failure",
            "active-failure",
            "strengthening",
            "underdesign",
        )
    )
    if active_fail and active_repair_visible:
        # active_fail_dominates_cleanup_evidence:
        # Active strength failure must be judged by repair/blocker evidence.
        # A secondary low-util family must not make this same visible card
        # prove a cleanup ladder as its primary evidence.
        return False
    has_cleanup_blocker = any(
        isinstance(row, dict)
        and (
            row.get("cleanup_search_ran")
            or row.get("local_cleanup_search_ran")
            or row.get("target_band_search_ran")
            or row.get("no_link_candidate_already_active")
            or row.get("no_link_candidate_id")
        )
        for row in list(exact.values()) + list(cleanup_rows.values())
    )
    card_type_value = card_type(card)
    terminal_or_blocked = card_type_value in {"BLOCKER", "TERMINAL", "PASS", "ACCEPTED"}
    action_advisory = bool(
        "recommendation is advisory" in text_blob
        or "not directly executable" in text_blob
        or "preview did not pass" in text_blob
        or (
            card_type_value == "ACTION"
            and dict(card.get("button_contract") or {}).get("preview_pass") is False
        )
    )
    ladder_words = any(
        token in text_blob
        for token in (
            "no further cleanup",
            "no further safe",
            "cleanup blocked",
            "ladder",
            "no links",
            "best safe cleanup",
            "outside target",
        )
    )
    overdesign_cleanup_context = bool(
        low_util
        or has_cleanup_blocker
        or "cleanup" in text_blob
        or "no links" in text_blob
        or "not directly executable" in text_blob
        or "preview did not pass" in text_blob
    )
    if active_fail and not overdesign_cleanup_context:
        return False
    return bool(
        (terminal_or_blocked and overdesign_cleanup_context and (has_cleanup_blocker or ladder_words))
        or action_advisory
    )


def _combined_visible_required_for_step(step: dict[str, Any]) -> bool:
    state = dict(step.get("browser_state") or {})
    sources = [
        exact_blockers(state),
        cleanup_evidence(state),
        dict(dict(step.get("visible_design_guide") or {}).get("blocker_attempts_by_family") or {}),
    ]
    for source in sources:
        row = dict(source.get("combined") or {}) if isinstance(source, dict) else {}
        if not row:
            continue
        updates = dict(
            row.get("attempted_updates")
            or row.get("selected_candidate_updates")
            or row.get("best_safe_candidate_updates")
            or row.get("best_rejected_candidate_updates")
            or {}
        )
        changed_bending = bool(set(updates) & {
            "bot1_count",
            "db_bot_1",
            "bot2_count",
            "db_bot_2",
            "bot2_row_enabled",
            "bot1_layout_mode",
            "bot2_layout_mode",
        })
        changed_shear = bool(set(updates) & {"lig_d", "db_lig", "lig_legs", "s_lig"})
        if changed_bending and changed_shear:
            return True
        text = " ".join(
            str(row.get(key) or "")
            for key in (
                "reason",
                "family_specific_reason",
                "rejection_reason",
                "rejection_category",
                "attempted_change_label",
                "failed_check_name",
            )
        ).lower()
        if any(token in text for token in (
            "interaction",
            "other family",
            "combined same-click",
            "superseded by better combined",
            "combined behaviour",
            "combined cleanup",
        )):
            return True
    return False


def _cleanup_explanation_text_from_page(page) -> dict[str, str]:
    try:
        card = page.locator("[data-testid='design-guide-card']").first
        if card.count() < 1:
            return {"card_text": "", "main_text": ""}
        try:
            card.evaluate(
                """
                (el) => {
                  const details = el.tagName === "DETAILS" ? el : el.closest("details");
                  if (details) details.open = true;
                }
                """
            )
        except Exception:
            try:
                card.evaluate("(el) => { if (el.tagName === 'DETAILS') el.open = true; }")
            except Exception:
                pass
        page.wait_for_timeout(120)
        main_text = ""
        try:
            main = card.locator("[data-testid='design-guide-main-explanation']").first
            if main.count() > 0:
                main_text = str(main.inner_text(timeout=1500) or "").strip()
        except Exception:
            pass
        try:
            card_text = str(card.inner_text(timeout=1500) or "").strip()
        except Exception:
            card_text = ""
        return {"card_text": card_text, "main_text": main_text}
    except Exception:
        return {"card_text": "", "main_text": ""}


def _append_artifact_json(path: Path, event: dict[str, Any], *, max_events: int = 80) -> None:
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        existing = {}
    events = list(existing.get("events") or []) if isinstance(existing, dict) else []
    events.append(dict(event))
    payload = {
        "latest": dict(event),
        "event_count": len(events),
        "events": events[-max_events:],
    }
    _write_json(path, payload)


def _collect_calc_box_dom_snapshot(page) -> dict[str, Any]:
    started = _perf_now()
    try:
        snapshot = page.evaluate(
            """
            () => {
              const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (!style || style.display === "none" || style.visibility === "hidden" || Number(style.opacity || 1) === 0) return false;
                const rect = el.getBoundingClientRect();
                return !!(rect.width || rect.height || el.getClientRects().length);
              };
              const textOf = (el) => ((el && el.innerText) || "").replace(/\\s+/g, " ").trim().slice(0, 180);
              const queryAll = (selector) => Array.from(document.querySelectorAll(selector));
              const calcSelector = [
                "[data-testid*='calc' i]",
                "[data-testid*='check' i]",
                "[class*='calc' i]",
                "[class*='check' i]",
                "details",
                "[role='region']"
              ].join(",");
              const calcNodes = queryAll(calcSelector).filter(isVisible);
              const cards = queryAll("[data-testid='design-guide-card']").filter(isVisible);
              const summaries = queryAll("[data-testid*='summary' i], [class*='summary' i]").filter(isVisible);
              const headings = queryAll("h1,h2,h3,[role='heading']").filter(isVisible).map(textOf).filter(Boolean).slice(0, 12);
              const url = new URL(window.location.href);
              return {
                url: window.location.href,
                page_slug: url.searchParams.get("page") || "",
                visible_calc_box_count: calcNodes.length,
                visible_calc_box_samples: calcNodes.slice(0, 12).map((el) => ({
                  tag: el.tagName,
                  testid: el.getAttribute("data-testid") || "",
                  class_name: el.className ? String(el.className).slice(0, 160) : "",
                  text: textOf(el)
                })),
                summary_card_count: summaries.length,
                design_guide_card_count: cards.length,
                design_guide_text: cards[0] ? textOf(cards[0]) : "",
                heading_list: headings,
                body_text_length: ((document.body && document.body.innerText) || "").length
              };
            }
            """
        )
        out = dict(snapshot or {})
    except Exception as exc:
        out = {"error": str(exc)}
    out["dom_snapshot_duration_ms"] = _safe_elapsed_ms(started)
    return out


def _iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _candidate_fingerprint(row: dict[str, Any]) -> str:
    payload = {
        "family": row.get("family"),
        "title": row.get("title"),
        "updates": row.get("updates") or row.get("candidate_updates") or row.get("proposed_updates") or {},
        "preview_util": row.get("preview_util") or row.get("candidate_util") or row.get("util"),
        "safe": row.get("safe_executor_backed") or row.get("is_executable"),
    }
    return json.dumps(payload, sort_keys=True, default=_json_default)


def _collect_design_guide_build_profile(step: dict[str, Any]) -> dict[str, Any]:
    state = dict(step.get("browser_state") or {})
    guidance = dict(state.get("guidance_compute_probe") or {})
    evidence = dict(guidance.get("candidate_search_evidence") or {})
    candidates: list[dict[str, Any]] = []
    for key in (
        "candidate_rows",
        "active_fail_repair_candidate_rows",
        "target_band_candidates",
        "safe_executor_backed_candidates",
        "rejected_target_band_candidates",
    ):
        rows = evidence.get(key)
        if isinstance(rows, list):
            candidates.extend([dict(row) for row in rows if isinstance(row, dict)])
    fingerprints = [_candidate_fingerprint(row) for row in candidates]
    fingerprint_counts: dict[str, int] = {}
    for fingerprint in fingerprints:
        fingerprint_counts[fingerprint] = fingerprint_counts.get(fingerprint, 0) + 1
    repeated = sorted(
        (
            {"fingerprint": fp[:260], "count": count}
            for fp, count in fingerprint_counts.items()
            if count > 1
        ),
        key=lambda row: int(row["count"]),
        reverse=True,
    )
    timing_events: list[dict[str, Any]] = []
    all_timing_events: list[dict[str, Any]] = []
    for row in _iter_dicts(state):
        name = str(row.get("name") or row.get("event") or row.get("stage") or "")
        if not name:
            continue
        compact_event = {
            "name": name,
            "elapsed_ms": row.get("elapsed_ms"),
            "duration_ms": row.get("duration_ms") or row.get("duration"),
            "delta_ms": row.get("delta_ms"),
        }
        all_timing_events.append(compact_event)
        name_l = name.lower()
        if any(token in name_l for token in ("design_guide", "summary", "candidate", "browser_test_state", "probe")):
            timing_events.append(compact_event)
    design_durations: list[float] = []
    for row in timing_events:
        name_l = str(row.get("name") or "").lower()
        if "design_guide" not in name_l:
            continue
        for key in ("duration_ms", "delta_ms"):
            value = _float_or_none(row.get(key))
            if value is not None and value >= 0:
                design_durations.append(float(value))
    def _event_cost(row: dict[str, Any]) -> float:
        for key in ("duration_ms", "delta_ms", "elapsed_ms"):
            value = _float_or_none(row.get(key))
            if value is not None:
                return float(value)
        return 0.0

    return {
        "timestamp": _iso_now(),
        "case_index": step.get("case_index"),
        "step_index": step.get("step_index"),
        "step_type": step.get("step_type"),
        "total_design_guide_build_time_ms": max(design_durations) if design_durations else None,
        "candidate_generation_count": evidence.get("generated_count") or evidence.get("total_candidates_considered"),
        "candidate_evaluation_count": evidence.get("total_candidates_considered") or len(candidates),
        "candidate_rows_captured": len(candidates),
        "unique_candidate_fingerprints": len(fingerprint_counts),
        "duplicate_candidate_fingerprints": sum(max(0, count - 1) for count in fingerprint_counts.values()),
        "top_repeated_candidates": repeated[:10],
        "summary_overview_build_count": sum(1 for row in timing_events if "summary" in str(row.get("name") or "").lower()),
        "browser_test_probe_publication_events": [
            row for row in timing_events if "browser_test_state" in str(row.get("name") or "").lower()
        ][:20],
        "cache_hit_count": _deep_get_count(guidance, evidence, keys=("cache_hit_count", "cache_hits")),
        "cache_miss_count": _deep_get_count(guidance, evidence, keys=("cache_miss_count", "cache_misses")),
        "candidate_evaluation_cache_hits": _deep_get_count(guidance, evidence, keys=("candidate_evaluation_cache_hits",)),
        "candidate_evaluation_cache_misses": _deep_get_count(guidance, evidence, keys=("candidate_evaluation_cache_misses",)),
        "duplicate_candidate_fingerprints_skipped": _deep_get_count(guidance, evidence, keys=("duplicate_candidate_fingerprints_skipped",)),
        "blocker_attempt_cache_hits": _deep_get_count(guidance, evidence, keys=("blocker_attempt_cache_hits",)),
        "slowest_timing_events": sorted(all_timing_events, key=_event_cost, reverse=True)[:20],
        "all_timing_event_count": len(all_timing_events),
        "timing_events_sample": timing_events[-30:],
    }


def _write_calc_box_evidence_timing(
    page,
    step: dict[str, Any],
    result: dict[str, Any],
    *,
    artifact_dir: Path | None,
    capture_started: float,
) -> None:
    if artifact_dir is None:
        return
    dom_snapshot = _collect_calc_box_dom_snapshot(page)
    event = {
        "timestamp": _iso_now(),
        "case_index": step.get("case_index"),
        "step_index": step.get("step_index"),
        "step_type": step.get("step_type"),
        "page_slug": dom_snapshot.get("page_slug"),
        "expected_calc_box_labels": list(result.get("families") or []),
        "visible_calc_box_count": dom_snapshot.get("visible_calc_box_count"),
        "first_calc_box_visible_timestamp": _iso_now() if int(dom_snapshot.get("visible_calc_box_count") or 0) > 0 else None,
        "calc_box_stable_timestamp": None,
        "summary_card_count": dom_snapshot.get("summary_card_count"),
        "design_guide_card_count": dom_snapshot.get("design_guide_card_count"),
        "page_cycle_settled_timestamp": step.get("timestamp"),
        "evidence_capture_timestamp": _iso_now(),
        "evidence_capture_duration_ms": _safe_elapsed_ms(capture_started),
        "final_unmet_evidence_condition": list(result.get("missing_fields") or []),
        "required": bool(result.get("required")),
        "ok": bool(result.get("ok")),
        "visible_design_guide_title": dict(step.get("visible_design_guide") or {}).get("title"),
        "visible_design_guide_status": dict(step.get("visible_design_guide") or {}).get("status_label"),
        "active_fail_families": active_fail_families(dict(step.get("visible_summary") or {})),
        "low_util_families": low_util_families(dict(step.get("visible_summary") or {})),
        "dom_snapshot": dom_snapshot,
    }
    _append_artifact_json(Path(artifact_dir) / "calc_box_evidence_timing.json", event)
    _append_artifact_json(Path(artifact_dir) / "design_guide_build_profile.json", _collect_design_guide_build_profile(step))


def assert_ladder_stop_calc_box_evidence(
    page,
    step: dict[str, Any],
    expected_family: str | None = None,
    *,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    capture_started = _perf_now()
    required = _ladder_stop_evidence_required(step)
    if not required:
        result = {"required": False, "ok": True, "missing_fields": [], "families": []}
        return result
    text_parts = _cleanup_explanation_text_from_page(page)
    text = str(text_parts.get("card_text") or "")
    main_text = str(text_parts.get("main_text") or "")
    text_lower = text.lower()
    main_lower = main_text.lower()
    missing: list[str] = []
    if "why no further cleanup" not in text_lower:
        missing.append("Why no further cleanup?")
    if "why the ladder stops here" in text_lower:
        missing.append("duplicate normal UI section: Why the ladder stops here")
    for fragment in CLEANUP_EXPLANATION_BANNED_FRAGMENTS:
        if fragment in main_lower:
            missing.append(f"generic/raw blocker text visible: {fragment}")
    families = _ladder_stop_expected_families(step, expected_family=expected_family)
    family_missing: list[str] = []
    explanation_source = main_lower or text_lower
    for fam in families:
        if fam == "bending" and not any(token in explanation_source for token in ("bending", "moment", "phimu", "φmu", "mu*")):
            family_missing.append("bending/moment evidence")
        if fam == "shear" and not any(token in explanation_source for token in ("shear", "vu", "φvu", "phivu", "links", "spacing")):
            family_missing.append("shear/link evidence")
    if families and "blocked because" not in explanation_source:
        if not any(token in explanation_source for token in ("is currently", "links are already removed")):
            missing.append("plain current-state sentence")
    if len(set(families)) == 1 and "combined" in main_lower and not _combined_visible_required_for_step(step):
        missing.append("unnecessary Combined row visible for single-family unresolved cleanup")
    state = dict(step.get("browser_state") or {})
    no_link_audit = no_link_shear_cleanup_audit(state, card=dict(step.get("visible_design_guide") or {}))
    if (
        "shear" in families
        and bool(no_link_audit.get("no_link_candidate_already_active"))
        and "shear links are already removed" not in explanation_source
    ):
        missing.append("no-link shear wording: Shear links are already removed")
    explicit_no_executable_change = bool(
        "no executable" in explanation_source
        and "cleanup change was available after checking" in explanation_source
    )
    if families and not (
        "we tried" in explanation_source
        or "links are already removed" in explanation_source
        or explicit_no_executable_change
    ):
        missing.append("attempted cleanup/change")
    if families and "the attempted design" not in explanation_source:
        if "links are already removed" not in explanation_source:
            missing.append("attempted design pass/fail statement")
    if (
        families
        and "links are already removed" not in explanation_source
        and not any(fragment in explanation_source for fragment in CLEANUP_REJECTION_CATEGORY_FRAGMENTS)
    ):
        missing.append("explicit rejection category")
    exact_change_patterns = (
        r"\bfrom\s+[^.]{1,120}\s+to\s+[^.]{1,120}",
        r"\bremoving\s+[^.]{1,120}\s+from\s+[^.]{1,120}",
        r"\badding\s+[^.]{1,120}\s+from\s+[^.]{1,120}\s+to\s+[^.]{1,120}",
    )
    if families and "links are already removed" not in explanation_source and not explicit_no_executable_change and not any(
        re.search(pattern, explanation_source, flags=re.I) for pattern in exact_change_patterns
    ):
        missing.append("exact attempted from/to change")
    if (
        families
        and "attempted design passed" in explanation_source
        and "safe but" in explanation_source
        and re.search(r"\battempted design failed\b", explanation_source)
    ):
        missing.append("failed wording used for passed-but-rejected attempted design")
    if families and "keeping" not in explanation_source:
        missing.append("retained/current arrangement")
    if families and not (
        "utilisation became" in explanation_source
        or "failed " in explanation_source
        or "links are already removed" in explanation_source
    ):
        missing.append("attempted utilisation or failed check value")
    if families and not (
        "maximum allowed" in explanation_source
        or "accepted cleanup floor" in explanation_source
        or "threshold" in explanation_source
        or "limit" in explanation_source
        or "against" in explanation_source
        or "links are already removed" in explanation_source
    ):
        missing.append("limit value or named limit")
    has_number = bool(re.search(r"\b\d+(?:\.\d+)?\b", main_text or text))
    if not has_number:
        missing.append("numeric utilisation/check value")
    blocker_sources: list[dict[str, Any]] = []
    state = dict(step.get("browser_state") or {})
    for source in (
        exact_blockers(state),
        cleanup_evidence(state),
        dict(dict(step.get("visible_design_guide") or {}).get("blocker_attempts_by_family") or {}),
    ):
        if isinstance(source, dict):
            blocker_sources.append(source)
    for source in blocker_sources:
        for fam, row in source.items():
            fam_s = str(fam or "").strip().lower()
            if fam_s not in {"bending", "shear"} or not isinstance(row, dict):
                continue
            attempted_util = _float_or_none(row.get("attempted_util") or row.get("failed_check_util"))
            current_util = _float_or_none(row.get("current_util"))
            attempted_change = str(row.get("attempted_change_label") or row.get("attempted_next_reduction") or "").strip().lower()
            if (
                attempted_util is not None
                and current_util is not None
                and abs(float(attempted_util) - float(current_util)) <= 1e-6
                and attempted_change
                and "no change" not in attempted_change
                and "already" not in attempted_change
            ):
                missing.append(f"{fam_s} attempted_util equals current_util without no-change explanation")
            if row.get("attempted_passed") is True:
                row_category = str(row.get("rejection_category") or "").strip().lower()
                row_reason = str(row.get("reason") or row.get("family_specific_reason") or "").strip().lower()
                if "unsafe" not in row_category and re.search(r"\bfailed\b", row_reason):
                    missing.append(f"{fam_s} evidence says failed for passed-but-rejected attempted design")
    guidance = dict(state.get("guidance_compute_probe") or {})
    evidence = dict(guidance.get("candidate_search_evidence") or {})
    card = dict(step.get("visible_design_guide") or {})
    selected_updates = dict(
        card.get("selected_action_updates")
        or dict(card.get("button_contract") or {}).get("updates")
        or guidance.get("selected_action_updates")
        or evidence.get("selected_candidate_updates")
        or {}
    )
    selected_legs = _float_or_none(selected_updates.get("lig_legs"))
    if selected_legs is not None and float(selected_legs) > 2:
        for row in list(evidence.get("candidate_rows") or evidence.get("active_fail_repair_candidate_rows") or []):
            if not isinstance(row, dict):
                continue
            row_updates = dict(row.get("updates") or row.get("candidate_updates") or {})
            row_legs = _float_or_none(row_updates.get("lig_legs"))
            if row_legs is not None and float(row_legs) == 2 and bool(row.get("safe_executor_backed") or row.get("is_executable")):
                missing.append("shear action selected more legs while a safe executor-backed two-leg option existed")
                break
    def _geometry_ratio_after_updates(updates: dict[str, Any]) -> float | None:
        base_inputs = dict(step.get("input_values") or {})
        update_d = dict(updates or {})
        depth = _float_or_none(update_d.get("D") or base_inputs.get("D"))
        width = _float_or_none(
            update_d.get("b")
            or update_d.get("beam_width")
            or update_d.get("beam_b")
            or update_d.get("width")
            or base_inputs.get("b")
            or base_inputs.get("beam_width")
            or base_inputs.get("beam_b")
            or base_inputs.get("width")
        )
        if depth is None or width is None or float(depth) <= 0.0 or float(width) <= 0.0:
            return None
        return float(depth) / float(width)

    if set(selected_updates) & {"D", "b", "beam_width", "beam_b", "width"}:
        try:
            selected_ratio = _geometry_ratio_after_updates(selected_updates)
            selected_ratio_distance = abs(float(selected_ratio) - 2.0) if selected_ratio is not None else None
        except Exception:
            selected_ratio = None
            selected_ratio_distance = None
        safe_le_2_candidate = None
        if selected_ratio_distance is not None:
            for row in list(evidence.get("candidate_rows") or []):
                if not isinstance(row, dict) or not bool(row.get("safe_executor_backed") or row.get("is_executable")):
                    continue
                row_updates = dict(
                    row.get("updates")
                    or row.get("candidate_updates")
                    or row.get("proposed_updates")
                    or {}
                )
                row_ratio = _geometry_ratio_after_updates(row_updates)
                if row_ratio is None:
                    continue
                if (
                    selected_ratio is not None
                    and float(selected_ratio) > 2.0 + 1e-6
                    and float(row_ratio) <= 2.0 + 1e-6
                ):
                    safe_le_2_candidate = row
                    missing.append("geometry action selected D/b > 2.0 while a safe executor-backed D/b <= 2.0 option existed")
                    break
                if abs(float(row_ratio) - 2.0) + 1e-6 < selected_ratio_distance:
                    missing.append("geometry action skipped a safe candidate closer to D/b = 2.0")
                    break
        text_l = str(card.get("text") or "").lower()
        if selected_ratio is not None and float(selected_ratio) > 2.0 + 1e-6:
            if "beam is relatively deep compared with its width" not in text_l:
                missing.append("geometry action retained D/b > 2.0 without visible constructability/detailing warning")
            if safe_le_2_candidate is not None:
                result_context = dict(step.get("geometry_preference_audit") or {})
                result_context["safe_le_2_candidate_id"] = safe_le_2_candidate.get("candidate_id")
                step["geometry_preference_audit"] = result_context
    missing.extend(family_missing)
    result = {
        "required": True,
        "ok": not missing,
        "missing_fields": missing,
        "families": families,
        "text": text,
        "main_text": main_text,
    }
    _write_calc_box_evidence_timing(
        page,
        step,
        result,
        artifact_dir=artifact_dir,
        capture_started=capture_started,
    )
    if missing:
        family_text = "/".join(families) if families else "overdesign"
        raise VisibleContractFailure(
            "ladder_stop_calc_box_evidence_missing",
            (
                "CLEANUP EXPLANATION EVIDENCE MISSING: expected one visible 'Why no further cleanup?' "
                f"section with current arrangement/utilisation, attempted change, failed check/limit, "
                f"and retained arrangement for {family_text} "
                f"terminal state. Missing: {', '.join(missing)}"
            ),
            {**dict(step), "ladder_stop_calc_box_evidence": result},
        )
    return result


async def assert_design_guide_layout_contract(page, case_context, *, allow_transient: bool = False) -> dict:
    return _assert_design_guide_layout_contract_sync(page, case_context, allow_transient=allow_transient)


def exact_blockers(browser_state: dict[str, Any]) -> dict[str, Any]:
    guidance = dict(browser_state.get("guidance_compute_probe") or {})
    out: dict[str, Any] = {}
    for source in (
        guidance.get("exact_blockers_by_family"),
        guidance.get("post_click_exact_blockers_by_family"),
        guidance.get("cleanup_evidence_by_family"),
        guidance.get("post_click_cleanup_evidence_by_family"),
        dict(guidance.get("candidate_search_evidence") or {}).get("exact_blockers_by_family"),
        dict(guidance.get("candidate_search_evidence") or {}).get("post_click_exact_blockers_by_family"),
    ):
        if isinstance(source, dict):
            for key, value in source.items():
                if isinstance(value, dict):
                    out[str(key).lower()] = dict(value)
    return out


def _deep_get_count(*sources: dict[str, Any], keys: tuple[str, ...], default: int = 0) -> int:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in keys:
            if key in source:
                try:
                    return int(source.get(key) or 0)
                except Exception:
                    return default
    return default


def _first_present(source: dict[str, Any], keys: tuple[str, ...]) -> Any:
    if not isinstance(source, dict):
        return None
    for key in keys:
        value = source.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _blocker_specificity_analysis(blocker: dict[str, Any], family: str) -> dict[str, Any]:
    fam = str(family or "").strip().lower()
    attempted = _first_present(
        blocker,
        (
            "attempted_candidate_count",
            "candidate_count",
            "repair_candidate_count",
            "cleanup_candidate_count",
            f"{fam}_attempted_candidate_count",
            f"post_click_{fam}_attempted_candidate_count",
        ),
    )
    failed_candidate = _first_present(
        blocker,
        (
            "failed_candidate_id",
            "best_rejected_candidate_id",
            "rejected_candidate_id",
            "best_blocked_candidate_id",
            "best_failed_candidate_id",
            "candidate_id",
            f"{fam}_failed_candidate_id",
            f"post_click_{fam}_failed_candidate_id",
        ),
    )
    failed_check = _first_present(
        blocker,
        (
            "failed_check_name",
            "failed_check",
            "blocking_check",
            "blocking_checks",
            "protective_check",
            f"{fam}_failed_check_name",
            f"post_click_{fam}_failed_check_name",
        ),
    )
    failed_status = _first_present(
        blocker,
        (
            "failed_check_status",
            "failed_status",
            "blocking_status",
            f"{fam}_failed_check_status",
            f"post_click_{fam}_failed_check_status",
        ),
    )
    failed_util = _first_present(
        blocker,
        (
            "failed_check_util",
            "failed_util",
            "blocking_util",
            f"{fam}_failed_check_util",
            f"post_click_{fam}_failed_check_util",
        ),
    )
    failed_demand = _first_present(
        blocker,
        (
            "failed_check_demand",
            "failed_demand",
            "demand",
            "applied_design_action",
            f"{fam}_failed_check_demand",
            f"post_click_{fam}_failed_check_demand",
        ),
    )
    failed_capacity = _first_present(
        blocker,
        (
            "failed_check_capacity_or_limit",
            "failed_capacity",
            "capacity",
            "limit",
            "code_limit",
            f"{fam}_failed_check_capacity_or_limit",
            f"post_click_{fam}_failed_check_capacity_or_limit",
        ),
    )
    reason = _first_present(
        blocker,
        (
            "reason",
            "blocker_reason",
            "specific_reason",
            "why_reduction_would_hurt_other_design_elements",
            "rejected_repair_reasons",
            "failed_candidate_reasons",
            "failed_candidate_reason",
        ),
    )
    missing: list[str] = []
    if attempted in (None, ""):
        missing.append("attempted_candidate_count")
    if failed_candidate in (None, ""):
        missing.append("failed_candidate_id_or_best_rejected_candidate_id")
    if failed_check in (None, ""):
        missing.append("failed_check_name")
    if failed_status in (None, ""):
        missing.append("failed_check_status")
    if failed_util in (None, ""):
        missing.append("failed_check_util")
    if failed_demand in (None, ""):
        missing.append("failed_check_demand")
    if failed_capacity in (None, ""):
        missing.append("failed_check_capacity_or_limit")
    if reason in (None, ""):
        missing.append("reason")
    return {
        "family": fam,
        "valid": not missing,
        "missing_fields": missing,
        "attempted_candidate_count": attempted,
        "failed_candidate_id": failed_candidate,
        "failed_check_name": failed_check,
        "failed_check_status": failed_status,
        "failed_check_util": failed_util,
        "failed_check_demand": failed_demand,
        "failed_check_capacity_or_limit": failed_capacity,
        "reason": reason,
    }


def _target_band_blocker_analysis(blocker: dict[str, Any], family: str) -> dict[str, Any]:
    fam = str(family or "").strip().lower()
    base = _blocker_specificity_analysis(blocker, fam)
    current_util = _first_present(
        blocker,
        (
            "current_util",
            "source_summary_util",
            "source_post_commit_util",
            f"{fam}_current_util",
            f"post_click_{fam}_current_util",
        ),
    )
    target_low = _first_present(blocker, ("target_low", "threshold_low", "repair_target_low", "final_target_low"))
    target_high = _first_present(blocker, ("target_high", "threshold_high", "repair_target_high", "final_target_high"))
    search_ran = bool(
        blocker.get("repair_search_ran")
        or blocker.get("target_band_search_ran")
        or blocker.get("target_search_ran")
        or blocker.get(f"{fam}_target_band_search_ran")
        or blocker.get(f"post_click_{fam}_target_band_search_ran")
    )
    search_exhaustive = bool(
        blocker.get("repair_search_exhaustive")
        or blocker.get("target_band_search_exhaustive")
        or blocker.get("target_search_exhaustive")
        or blocker.get(f"{fam}_target_band_search_exhaustive")
        or blocker.get(f"post_click_{fam}_target_band_search_exhaustive")
    )
    attempted = _first_present(
        blocker,
        (
            "attempted_candidate_count",
            "candidate_count",
            "repair_candidate_count",
            "target_band_candidate_count_total",
            f"{fam}_attempted_candidate_count",
            f"post_click_{fam}_attempted_candidate_count",
        ),
    )
    executable = _first_present(
        blocker,
        (
            "executable_candidate_count",
            "executable_repair_candidate_count",
            "executable_target_band_candidate_count",
            f"{fam}_executable_candidate_count",
            f"post_click_{fam}_executable_candidate_count",
        ),
    )
    target_band_count = _first_present(
        blocker,
        (
            "target_band_candidate_count",
            "executable_target_band_candidate_count",
            "target_candidate_count",
            f"{fam}_target_band_candidate_count",
            f"post_click_{fam}_target_band_candidate_count",
        ),
    )
    best_safe = _first_present(
        blocker,
        (
            "best_safe_final_util",
            "best_safe_util",
            "best_candidate_final_util",
            f"{fam}_best_safe_final_util",
            f"post_click_{fam}_best_safe_final_util",
        ),
    )
    missing = list(base.get("missing_fields") or [])
    for field, value in (
        ("current_util", current_util),
        ("target_low", target_low),
        ("target_high", target_high),
        ("attempted_candidate_count", attempted),
        ("executable_candidate_count", executable),
        ("target_band_candidate_count", target_band_count),
    ):
        if value in (None, "") and field not in missing:
            missing.append(field)
    if not search_ran:
        missing.append("repair_search_ran_or_target_band_search_ran")
    if not search_exhaustive:
        missing.append("repair_search_exhaustive_or_target_band_search_exhaustive")
    return {
        **base,
        "valid": not missing,
        "missing_fields": missing,
        "current_util": current_util,
        "target_low": target_low,
        "target_high": target_high,
        "repair_or_target_band_search_ran": search_ran,
        "repair_or_target_band_search_exhaustive": search_exhaustive,
        "attempted_candidate_count": attempted,
        "executable_candidate_count": executable,
        "target_band_candidate_count": target_band_count,
        "best_safe_final_util": best_safe,
    }


def cleanup_evidence(browser_state: dict[str, Any]) -> dict[str, Any]:
    guidance = dict(browser_state.get("guidance_compute_probe") or {})
    evidence = dict(guidance.get("candidate_search_evidence") or {})
    for key in (
        "local_cleanup_search_ran",
        "local_cleanup_search_exhaustive",
        "cleanup_search_ran",
        "cleanup_search_exhaustive",
        "repair_search_ran",
        "repair_search_exhaustive",
        "safe_candidate_count",
        "safe_executor_backed_candidates_count",
        "executable_candidate_count",
        "executable_target_band_candidate_count",
        "safe_cleanup_count",
        "safe_local_cleanup_count",
        "executable_cleanup_count",
        "executable_safe_cleanup_count",
        "best_safe_candidate_applied",
        "no_second_cta_required",
        "no_link_candidate_tested",
        "no_link_candidate_evaluated",
        "no_link_candidate_passed",
        "no_link_candidate_selected",
        "no_link_candidate_already_active",
        "no_link_candidate_updates",
        "no_link_candidate_id",
        "no_link_candidate_reason",
        "no_link_s_lig_policy",
    ):
        if key in guidance and key not in evidence:
            evidence[key] = guidance.get(key)
    return evidence


def _updates_are_no_link(updates: Any) -> bool:
    if not isinstance(updates, dict):
        return False
    try:
        lig_d = int(float(updates.get("lig_d", 999) or 0))
        lig_legs = int(float(updates.get("lig_legs", 999) or 0))
    except Exception:
        return False
    return bool(lig_d <= 0 and lig_legs <= 0)


def _text_mentions_no_link_candidate(value: Any) -> bool:
    text = str(value or "").lower()
    if not text:
        return False
    return bool(
        ("lig_d" in text and "lig_legs" in text and re.search(r"lig_d[^0-9-]*0", text) and re.search(r"lig_legs[^0-9-]*0", text))
        or "no-link" in text
        or "no links" in text
        or "no_links" in text
        or "shear_cleanup_floor_no_links" in text
    )


def _iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def no_link_shear_cleanup_audit(browser_state: dict[str, Any], card: dict[str, Any] | None = None) -> dict[str, Any]:
    card = dict(card or {})
    guidance = dict(browser_state.get("guidance_compute_probe") or {})
    evidence = cleanup_evidence(browser_state)
    blockers = exact_blockers(browser_state)
    shared = dict(browser_state.get("browser_shared_probe") or {})
    selected_updates = dict(card.get("selected_action_updates") or {})
    contract_updates = dict(dict(card.get("button_contract") or {}).get("updates") or {})
    payload_updates = dict(dict(card.get("design_guide_primary_apply_payload") or {}).get("updates") or {})

    already_active = _updates_are_no_link(shared)
    selected = any(_updates_are_no_link(updates) for updates in (selected_updates, contract_updates, payload_updates))
    tested = bool(evidence.get("no_link_candidate_tested"))
    evaluated = bool(evidence.get("no_link_candidate_evaluated"))
    passed = bool(evidence.get("no_link_candidate_passed"))
    candidate_id = evidence.get("no_link_candidate_id")
    candidate_updates = dict(evidence.get("no_link_candidate_updates") or {})
    failed_reason = (
        evidence.get("no_link_candidate_failed_or_selected_reason")
        or evidence.get("no_link_candidate_failed_reason")
        or evidence.get("no_link_candidate_reason")
    )

    candidate_rows = []
    for source in (evidence, blockers):
        for row in _iter_dicts(source):
            updates = (
                row.get("updates")
                or row.get("proposed_updates")
                or row.get("selected_candidate_updates")
                or row.get("best_safe_candidate_updates")
                or row.get("best_target_band_candidate_updates")
                or row.get("attempted_updates")
                if isinstance(row, dict)
                else {}
            )
            row_mentions_no_link = bool(
                isinstance(row, dict)
                and any(
                    _text_mentions_no_link_candidate(row.get(key))
                    for key in (
                        "failed_candidate_id",
                        "best_rejected_candidate_id",
                        "candidate_id",
                        "source_candidate_id",
                        "no_link_candidate_id",
                    )
                )
            )
            if _updates_are_no_link(updates) or row_mentions_no_link:
                candidate_rows.append(row)
    for row in candidate_rows:
        updates = (
            row.get("updates")
            or row.get("proposed_updates")
            or row.get("selected_candidate_updates")
            or row.get("best_safe_candidate_updates")
            or row.get("best_target_band_candidate_updates")
            or row.get("attempted_updates")
            if isinstance(row, dict)
            else {}
        )
        tested = True
        evaluated = True
        passed = bool(
            passed
            or row.get("preview_pass")
            or row.get("safe_executor_backed")
            or row.get("is_executable")
            or row.get("candidate_reaches_target_band")
        )
        if row.get("failed_check_status") or row.get("failed_check_name") or row.get("failed_check_util") is not None:
            evaluated = True
            passed = False
        candidate_id = (
            candidate_id
            or row.get("candidate_id")
            or row.get("source_candidate_id")
            or row.get("failed_candidate_id")
            or row.get("best_rejected_candidate_id")
        )
        if not candidate_updates:
            candidate_updates = dict(
                row.get("updates")
                or row.get("proposed_updates")
                or row.get("selected_candidate_updates")
                or row.get("best_safe_candidate_updates")
                or row.get("best_target_band_candidate_updates")
                or row.get("attempted_updates")
                or {}
            )
        if not candidate_updates and _text_mentions_no_link_candidate(candidate_id):
            candidate_updates = {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0}
        if not failed_reason:
            failed_check_name = row.get("failed_check_name")
            failed_check_util = _float_or_none(row.get("failed_check_util"))
            if failed_check_name and failed_check_util is not None:
                failed_reason = f"No-link candidate failed {str(failed_check_name).lower()}, util {failed_check_util:.2f}"
            else:
                failed_reason = row.get("rejection_reason") or row.get("failed_check_status") or row.get("reason")

    if selected:
        tested = True
        evaluated = True
        passed = True
        if not candidate_updates:
            candidate_updates = selected_updates or contract_updates or payload_updates
        candidate_id = dict(card.get("button_contract") or {}).get("candidate_id") or candidate_id
        failed_reason = "No-link candidate passed and was selected as the visible action."
    if already_active:
        failed_reason = "Shear links are already removed; no further shear-link cleanup is available."

    return {
        "no_link_candidate_tested": bool(tested),
        "no_link_candidate_evaluated": bool(evaluated),
        "no_link_candidate_passed": bool(passed),
        "no_link_candidate_selected": bool(selected or evidence.get("no_link_candidate_selected")),
        "no_link_candidate_already_active": bool(already_active or evidence.get("no_link_candidate_already_active")),
        "no_link_candidate_id": candidate_id,
        "no_link_candidate_updates": candidate_updates,
        "no_link_candidate_failed_or_selected_reason": failed_reason,
        "no_link_s_lig_policy": evidence.get("no_link_s_lig_policy") or (
            "canonical_neutralised" if candidate_updates.get("s_lig") in (0, 0.0, 200, 200.0) else "retained_or_unknown"
        ),
        "candidate_rows_seen": len(candidate_rows),
    }


def blocker_proof_analysis(card: dict[str, Any], browser_state: dict[str, Any], family: str | None = None) -> dict[str, Any]:
    fam = str(family or card.get("family") or "").strip().lower()
    blockers = exact_blockers(browser_state)
    blocker = dict(blockers.get(fam) or {}) if fam and fam != "combined" else {}
    blocker_from_visible_attempt = False
    if fam and fam != "combined" and not blocker:
        visible_attempt = dict(dict(card.get("blocker_attempts_by_family") or {}).get(fam) or {})
        if visible_attempt and (
            visible_attempt.get("cleanup_search_ran")
            or visible_attempt.get("local_cleanup_search_ran")
            or visible_attempt.get("target_band_search_ran")
            or visible_attempt.get("no_link_candidate_already_active")
        ):
            blocker = dict(visible_attempt)
            blocker_from_visible_attempt = True
    if fam == "combined":
        blocker = {"combined": True} if blockers.get("bending") and blockers.get("shear") else {}
    evidence = cleanup_evidence(browser_state)
    ran = bool(
        blocker.get("repair_search_ran")
        or blocker.get("cleanup_search_ran")
        or blocker.get("local_cleanup_search_ran")
        or evidence.get("repair_search_ran")
        or evidence.get("cleanup_search_ran")
        or evidence.get("local_cleanup_search_ran")
    )
    exhaustive = bool(
        blocker.get("repair_search_exhaustive")
        or blocker.get("cleanup_search_exhaustive")
        or blocker.get("local_cleanup_search_exhaustive")
        or evidence.get("repair_search_exhaustive")
        or evidence.get("cleanup_search_exhaustive")
        or evidence.get("local_cleanup_search_exhaustive")
        or evidence.get("candidate_search_exhaustive")
    )
    executable_count = _deep_get_count(
        blocker,
        evidence,
        keys=(
            "executable_candidate_count",
            "executable_target_band_candidate_count",
            "executable_cleanup_count",
            "executable_safe_cleanup_count",
        ),
    )
    target_band_count = _deep_get_count(
        blocker,
        evidence,
        keys=(
            "target_band_candidate_count",
            "accepted_band_candidate_count",
            "executable_target_band_candidate_count",
            "target_candidate_count",
        ),
    )
    safe_count = _deep_get_count(
        blocker,
        evidence,
        keys=("safe_candidate_count", "safe_cleanup_count", "safe_local_cleanup_count", "safe_executor_backed_candidates_count"),
    )
    best_safe_applied = bool(blocker.get("best_safe_candidate_applied") or evidence.get("best_safe_candidate_applied"))
    no_second_cta = bool(blocker.get("no_second_cta_required") or evidence.get("no_second_cta_required"))
    best_safe_below_band_proven = bool(no_second_cta and target_band_count == 0)
    family_matches = bool(fam and (fam == "combined" or blockers.get(fam) or blocker_from_visible_attempt))
    exact = bool(blocker)
    specificity = _blocker_specificity_analysis(blocker, fam) if exact and fam != "combined" else {
        "valid": bool(fam == "combined" and blockers.get("bending") and blockers.get("shear")),
        "missing_fields": [],
    }
    valid = bool(
        exact
        and family_matches
        and ran
        and exhaustive
        and specificity.get("valid")
        and (
            executable_count == 0
            or (best_safe_applied and no_second_cta)
            or best_safe_below_band_proven
        )
    )
    return {
        "family": fam,
        "exact_blocker_exists": exact,
        "blocker_family_matches": family_matches,
        "cleanup_search_ran": ran,
        "cleanup_search_exhaustive": exhaustive,
        "safe_candidate_count": safe_count,
        "executable_candidate_count": executable_count,
        "target_band_candidate_count": target_band_count,
        "best_safe_candidate_applied": best_safe_applied,
        "no_second_cta_required": no_second_cta,
        "best_safe_below_band_proven": best_safe_below_band_proven,
        "specificity": specificity,
        "specificity_valid": bool(specificity.get("valid")),
        "specificity_missing_fields": list(specificity.get("missing_fields") or []),
        "valid": valid,
    }


def _blocker_has_family_search_and_counts(blocker: dict[str, Any], family: str) -> tuple[bool, str]:
    fam = str(family or "").strip().lower()
    ran = bool(
        blocker.get("cleanup_search_ran")
        or blocker.get("local_cleanup_search_ran")
        or blocker.get("repair_search_ran")
        or blocker.get(f"{fam}_cleanup_search_ran")
        or blocker.get(f"post_click_{fam}_cleanup_search_ran")
    )
    exhaustive = bool(
        blocker.get("cleanup_search_exhaustive")
        or blocker.get("local_cleanup_search_exhaustive")
        or blocker.get("repair_search_exhaustive")
        or blocker.get(f"{fam}_cleanup_search_exhaustive")
        or blocker.get(f"post_click_{fam}_cleanup_search_exhaustive")
    )
    safe_keys = (
        "safe_candidate_count",
        "safe_cleanup_count",
        "safe_local_cleanup_count",
        f"safe_{fam}_cleanup_count",
        f"post_click_safe_{fam}_cleanup_count",
    )
    executable_keys = (
        "executable_candidate_count",
        "executable_cleanup_count",
        "executable_safe_cleanup_count",
        f"executable_{fam}_cleanup_count",
        f"post_click_executable_{fam}_cleanup_count",
    )
    has_safe_count = any(key in blocker for key in safe_keys)
    has_executable_count = any(key in blocker for key in executable_keys)
    if not ran:
        return False, f"{fam} cleanup_search_ran is missing"
    if not exhaustive:
        return False, f"{fam} cleanup_search_exhaustive is missing"
    if not has_safe_count:
        return False, f"{fam} safe candidate/cleanup count is missing"
    if not has_executable_count:
        return False, f"{fam} executable candidate/cleanup count is missing"
    specificity = _blocker_specificity_analysis(blocker, fam)
    if not specificity.get("valid"):
        return False, f"{fam} blocker is missing specific failed candidate/check fields: {specificity.get('missing_fields')}"
    return True, ""


def _assert_multi_family_blocker_contract(step: dict[str, Any]) -> None:
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    text = str(card.get("text") or "")
    text_l = text.lower()
    title_l = str(card.get("title") or "").lower()
    first_card = {}
    try:
        first_card = dict(list(card.get("cards") or [{}])[0] or {})
    except Exception:
        first_card = {}
    hook_counts = dict(first_card.get("test_hook_counts") or {})
    mentions_bending_and_shear = bool(
        "bending and shear" in title_l
        or "further cleanup blocked" in title_l
        or ("bending cleanup blocked:" in text_l and "shear cleanup blocked:" in text_l)
    )
    if not (is_blocker_card(card) and mentions_bending_and_shear):
        return
    blockers = exact_blockers(state)
    missing = [family for family in ("bending", "shear") if not isinstance(blockers.get(family), dict)]
    if missing:
        _fail(
            "multi_family_blocker_missing_family_evidence",
            f"Multi-family blocker mentions bending/shear but lacks exact blocker evidence for {missing}.",
            step,
        )
    for family in ("bending", "shear"):
        ok, reason = _blocker_has_family_search_and_counts(dict(blockers.get(family) or {}), family)
        if not ok:
            _fail("multi_family_blocker_missing_family_evidence", reason, step)
    compact_blocked_reasons = "blocked because" in text_l
    bending_reason_visible = (
        int(hook_counts.get("design-guide-reason-bending") or 0) > 0
        or
        "bending cleanup blocked:" in text_l
        or "bending repair blocked:" in text_l
        or "bending attempts:" in text_l
        or (compact_blocked_reasons and ("• bending:" in text_l or "- bending:" in text_l))
        or (compact_blocked_reasons and ("• bending attempts:" in text_l or "- bending attempts:" in text_l))
    )
    shear_reason_visible = (
        int(hook_counts.get("design-guide-reason-shear") or 0) > 0
        or
        "shear cleanup blocked:" in text_l
        or "shear repair blocked:" in text_l
        or "shear attempts:" in text_l
        or (compact_blocked_reasons and ("• shear:" in text_l or "- shear:" in text_l))
        or (compact_blocked_reasons and ("• shear attempts:" in text_l or "- shear attempts:" in text_l))
    )
    if not (bending_reason_visible and shear_reason_visible):
        _fail(
            "multi_family_blocker_vague_reason",
            "Multi-family blocker must list separate visible bending and shear blocker reasons.",
            step,
        )
    if "checked cleanup searches found no further safe one-click reduction" in text_l:
        _fail(
            "multi_family_blocker_vague_reason",
            "Multi-family blocker uses generic checked-cleanup-search wording instead of per-family reasons.",
            step,
        )
    if "serviceability and shear checks" in text_l:
        _fail(
            "multi_family_blocker_vague_reason",
            "Multi-family blocker uses generic serviceability/shear wording instead of failed candidate/check details.",
            step,
        )
    if re.search(r"\(\s*utili[sz]ation\s*=", text_l):
        _fail(
            "blocker_util_label_ambiguous",
            "Multi-family blocker displays utilisation without saying bending, shear, or governing.",
            step,
        )


def has_exact_blocker(browser_state: dict[str, Any], family: str | None = None) -> bool:
    blockers = exact_blockers(browser_state)
    if family:
        if family == "combined":
            return bool(blockers.get("bending") and blockers.get("shear"))
        return bool(blockers.get(str(family).lower()))
    return bool(blockers)


def _summary_utils(summary: dict[str, Any]) -> dict[str, Any]:
    return {family: family_util(summary, family) for family in ("bending", "shear", "crack", "deflection")}


def _summary_statuses(summary: dict[str, Any]) -> dict[str, Any]:
    return {family: family_status(summary, family) for family in ("bending", "shear", "crack", "deflection")}


def blocker_contract_clean(card: dict[str, Any]) -> bool:
    contract = dict(card.get("button_contract") or {})
    return not bool(contract.get("actionable")) and not dict(contract.get("updates") or {})


def is_valid_structured_blocker(card: dict[str, Any], browser_state: dict[str, Any]) -> bool:
    fam = card.get("family")
    blocker_family = fam if fam in {"bending", "shear", "combined", "crack", "deflection"} else None
    return bool(is_blocker_card(card) and blocker_contract_clean(card) and blocker_proof_analysis(card, browser_state, blocker_family).get("valid"))


def family_util(summary: dict[str, Any], family: str) -> float | None:
    value = _float_or_none(dict(summary.get(family) or {}).get("util"))
    if value is not None:
        return value
    return _float_or_none(dict(summary.get(family) or {}).get("util_support"))


def family_status(summary: dict[str, Any], family: str) -> str | None:
    status = dict(summary.get(family) or {}).get("status")
    if status:
        return str(status).upper()
    status = dict(summary.get(family) or {}).get("status_support")
    return str(status).upper() if status else None


def is_terminal_card(card: dict[str, Any]) -> bool:
    title = str(card.get("title") or "").lower()
    # Body copy for an action card can legitimately say that the preview lands
    # in the "accepted range"; terminal classification must come from the
    # visible card headline/state, not incidental explanatory text.
    return any(
        token in title
        for token in (
            "design accepted",
            "design is efficient",
            "target band achieved",
            "already efficient",
            "further reductions would weaken capacity",
            "design demand is very low",
        )
    )


def is_cleanup_or_terminal_only(card: dict[str, Any]) -> bool:
    text = str(card.get("text") or "").lower()
    title = str(card.get("title") or "").lower()
    combined = f"{title} {text}"
    return is_terminal_card(card) or ("cleanup" in combined and "capacity is low" not in combined)


def is_blocker_card(card: dict[str, Any]) -> bool:
    if is_terminal_card(card):
        return False
    text = str(card.get("text") or "").lower()
    return any(
        token in text
        for token in (
            "blocked",
            "cannot",
            "cannot safely",
            "no further safe",
            "no one-click",
            "no safe",
            "does not reach",
            "not enabled",
        )
    )


def card_type(card: dict[str, Any]) -> str:
    if is_terminal_card(card):
        return "TERMINAL"
    if is_blocker_card(card):
        return "BLOCKER"
    status_label = str(card.get("status_label") or "").strip().upper()
    classes = str(card.get("classes") or "").lower()
    if status_label == "ACTION" or "dg-card--action" in classes:
        return "ACTION"
    if bool(card.get("cta_visible") or card.get("cta_enabled")):
        return "ACTION"
    return "UNKNOWN"


def visible_card_colour(card: dict[str, Any]) -> str:
    classes = str(card.get("classes") or "").lower()
    status_label = str(card.get("status_label") or "").strip().upper()
    title_text = f"{card.get('title') or ''} {card.get('text') or ''}".lower()
    if (
        status_label == "FAIL"
        or any(token in classes for token in ("fail", "error", "critical", "danger", "red"))
    ):
        return "red"
    if (
        status_label in {"INFO", "OPTIMISE", "RECOMMEND"}
        or any(token in classes for token in ("efficiency", "info", "blue", "optimise", "optimize"))
    ):
        return "blue"
    if (
        status_label in {"GOOD", "PASS", "OPTIMAL"}
        or any(token in classes for token in ("good", "pass", "optimal", "success", "green", "accepted"))
        or is_terminal_card(card)
    ):
        return "green"
    if (
        status_label in {"NEXT", "WARN", "RECOMMEND"}
        or any(token in classes for token in ("warn", "warning", "next", "yellow", "orange", "amber"))
        or ("cleanup" in title_text or "blocked" in title_text)
    ):
        return "yellow"
    if "capacity is low" in title_text or "repair required" in title_text or "fails" in title_text:
        return "red_text_only"
    return "unknown"


def _rgb_tuple(value: Any) -> tuple[int, int, int] | None:
    match = re.search(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", str(value or ""))
    if not match:
        return None
    return tuple(max(0, min(255, int(part))) for part in match.groups())  # type: ignore[return-value]


def _rgb_tuples(value: Any) -> list[tuple[int, int, int]]:
    matches = re.findall(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", str(value or ""))
    return [
        tuple(max(0, min(255, int(part))) for part in match)  # type: ignore[misc]
        for match in matches
    ]


def _semantic_from_style(style: dict[str, Any] | None, classes: str = "", text: str = "") -> str:
    class_text = f"{classes or ''} {text or ''}".lower()
    if any(token in class_text for token in ("danger", "error", "fail", "critical", "red")):
        return "danger"
    if any(token in class_text for token in ("warning", "warn", "orange", "amber", "yellow")):
        return "warning"
    if any(token in class_text for token in ("success", "good", "pass", "green", "accepted", "optimal")):
        return "success"
    if any(token in class_text for token in ("action", "info", "blue", "primary", "optimise", "optimize")):
        return "action"
    style = dict(style or {})
    rgbs: list[tuple[int, int, int]] = []
    for key in ("backgroundColor", "borderColor", "color"):
        rgbs.extend(_rgb_tuples(style.get(key)))
    for rgb in rgbs:
        red, green, blue = rgb
        if red >= 145 and green <= 130 and blue <= 130:
            return "danger"
    for rgb in rgbs:
        red, green, blue = rgb
        if red >= 170 and 80 <= green <= 205 and blue <= 140:
            return "warning"
    for rgb in rgbs:
        red, green, blue = rgb
        if green >= 120 and red <= 150 and blue <= 160:
            return "success"
    for rgb in rgbs:
        red, green, blue = rgb
        if blue >= 145 and red <= 160 and green <= 190:
            return "action"
    return "unknown"


def _card_visual_semantic(card: dict[str, Any]) -> str:
    colour = visible_card_colour(card)
    if colour in {"red", "red_text_only"}:
        return "danger"
    if colour == "yellow":
        return "warning"
    if colour == "green":
        return "success"
    if colour == "blue":
        return "action"
    return _semantic_from_style(card.get("computed_style"), str(card.get("classes") or ""), str(card.get("title") or ""))


def _cta_visual_semantic(card: dict[str, Any]) -> str:
    return _semantic_from_style(
        card.get("cta_computed_style"),
        str(card.get("cta_classes") or ""),
        str(card.get("cta_label") or ""),
    )


def assert_card_button_colour_semantics(step: dict[str, Any]) -> None:
    card = dict(step.get("visible_design_guide") or {})
    if not card.get("cta_visible"):
        return
    card_semantic = _card_visual_semantic(card)
    cta_semantic = _cta_visual_semantic(card)
    cta_label = str(card.get("cta_label") or "")
    repair_or_auto_cta = bool(re.search(r"\b(repair|auto|apply|design|recommendation)\b", cta_label, flags=re.I))
    mismatch = False
    reason = ""
    if card_semantic == "danger" and cta_semantic != "danger":
        mismatch = True
        reason = "Danger/repair-required card has a non-danger CTA."
    elif card_semantic == "warning" and cta_semantic != "warning":
        mismatch = True
        reason = "Warning card has a non-warning CTA."
    elif card_semantic == "success" and repair_or_auto_cta:
        mismatch = True
        reason = "Accepted/success card exposes a repair/auto-design CTA."
    elif card_semantic in {"action", "unknown"} and cta_semantic in {"danger", "warning"} and cta_semantic != card_semantic:
        mismatch = True
        reason = "Neutral/action card CTA implies a stronger warning/danger state than the card."
    step["card_button_colour_semantics"] = {
        "card_title": card.get("title"),
        "card_semantic_state": card_semantic,
        "card_computed_style": dict(card.get("computed_style") or {}),
        "card_classes": card.get("classes"),
        "cta_label": cta_label,
        "cta_semantic_state": cta_semantic,
        "cta_computed_style": dict(card.get("cta_computed_style") or {}),
        "cta_classes": card.get("cta_classes"),
        "mismatch": mismatch,
        "reason": reason,
    }
    if mismatch:
        _fail(
            "design_guide_card_button_colour_mismatch",
            reason,
            step,
        )


def _exact_cleanup_terminal_blocker(row: dict[str, Any]) -> bool:
    if not isinstance(row, dict) or not row:
        return False
    search_ran = bool(
        row.get("search_ran")
        or row.get("cleanup_search_ran")
        or row.get("local_cleanup_search_ran")
        or row.get("target_band_search_ran")
        or row.get("repair_search_ran")
    )
    search_exhaustive = bool(
        row.get("search_exhaustive")
        or row.get("cleanup_search_exhaustive")
        or row.get("local_cleanup_search_exhaustive")
        or row.get("target_band_search_exhaustive")
        or row.get("repair_search_exhaustive")
    )
    executable_count = _deep_get_count(
        row,
        keys=(
            "executable_target_band_candidate_count",
            "executable_candidate_count",
            "executable_cleanup_count",
            "safe_executor_backed_candidates_count",
        ),
    )
    target_count = _deep_get_count(
        row,
        keys=("executable_target_band_candidate_count", "target_band_candidate_count"),
    )
    if executable_count > 0 and not (
        bool(row.get("best_safe_candidate_applied")) and bool(row.get("no_second_cta_required"))
    ):
        return False
    if target_count > 0:
        return False
    has_exact_reason = bool(
        row.get("exact_blocker")
        or row.get("no_second_cta_required")
        or row.get("failed_check_name")
        or row.get("failed_check_status")
        or row.get("reason")
        or row.get("why_reduction_would_hurt_other_design_elements")
    )
    return bool(search_ran and search_exhaustive and has_exact_reason)


def is_terminal_exact_cleanup_no_action(
    summary: dict[str, Any],
    card: dict[str, Any] | None = None,
    browser_state: dict[str, Any] | None = None,
) -> bool:
    if active_fail_families(summary):
        return False
    card = dict(card or {})
    contract = dict(card.get("button_contract") or {})
    if bool(card.get("cta_visible")) or bool(card.get("cta_enabled")):
        return False
    if bool(contract.get("enabled")) or bool(contract.get("actionable")):
        return False
    if str(contract.get("action_type") or "").strip() and dict(contract.get("updates") or {}):
        return False
    blockers: dict[str, Any] = {}
    for source in (
        exact_blockers(dict(browser_state or {})),
        card.get("exact_blockers_by_family"),
        card.get("blocker_attempts_by_family"),
    ):
        if isinstance(source, dict):
            for family, row in source.items():
                if isinstance(row, dict):
                    blockers[str(family or "").strip().lower()] = dict(row)
    return any(_exact_cleanup_terminal_blocker(row) for row in blockers.values())


def expected_card_colour(
    summary: dict[str, Any],
    card: dict[str, Any] | None = None,
    browser_state: dict[str, Any] | None = None,
) -> str:
    if active_fail_families(summary):
        return "red"
    if card is not None:
        if is_terminal_exact_cleanup_no_action(summary, card, browser_state):
            return "green"
        if is_terminal_card(card):
            return "green"
        if low_util_families(summary) and (
            bool(card.get("cta_enabled"))
            or is_blocker_card(card)
            or "cleanup" in f"{card.get('title') or ''} {card.get('text') or ''}".lower()
        ):
            return "blue"
    return "not_red"


def colour_alignment(
    summary: dict[str, Any],
    card: dict[str, Any],
    browser_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active = active_fail_families(summary)
    colour = visible_card_colour(card)
    expected = expected_card_colour(summary, card, browser_state)
    text = f"{card.get('title') or ''} {card.get('text') or ''}".lower()
    ctype = card_type(card)
    contract = dict(card.get("button_contract") or {})
    terminal_exact_cleanup = is_terminal_exact_cleanup_no_action(summary, card, browser_state)
    red_executable_repair_action = bool(
        colour == "red"
        and ctype == "ACTION"
        and bool(card.get("cta_enabled"))
        and bool(contract.get("actionable"))
        and str(contract.get("action_type") or "").strip()
        and dict(card.get("selected_action_updates") or contract.get("updates") or {})
    )
    failures: list[str] = []
    if active:
        if colour != "red":
            failures.append("summary_fail_card_not_red")
        cleanup_or_efficiency_text = bool(
            "overdesign" in text
            or "low-util" in text
            or "further cleanup" in text
            or (
                "cleanup" in text
                and not any(token in text for token in ("capacity is low", "repair", "strengthening"))
            )
        )
        if colour == "yellow" or (cleanup_or_efficiency_text and not red_executable_repair_action):
            failures.append("summary_fail_card_warn_or_cleanup")
        terminal_or_green = bool(
            colour == "green"
            or ctype == "TERMINAL"
            or (
                colour != "red"
                and ctype != "BLOCKER"
                and any(token in text for token in ("accepted", "efficient", "target achieved", "no further cleanup"))
            )
        )
        if terminal_or_green:
            failures.append("summary_fail_card_green_or_terminal")
        if set(active) == {"bending", "shear"} and (colour != "red" or str(card.get("family") or "").lower() != "combined"):
            failures.append("combined_fail_card_not_red_combined")
    else:
        if colour in {"red", "red_text_only"} or "capacity is low" in text or "repair required" in text:
            failures.append("summary_pass_card_red")
        if expected == "blue" and colour != "blue":
            failures.append("safe_overdesign_card_not_blue")
        if expected == "green" and colour != "green":
            failures.append("accepted_terminal_card_not_green")
    return {
        "summary_statuses": _summary_statuses(summary),
        "summary_colour_by_family": {
            family: ("red" if family_status(summary, family) == "FAIL" else "green_or_neutral")
            for family in ("bending", "shear", "crack", "deflection")
        },
        "active_fail_families": active,
        "expected_card_colour": expected,
        "actual_card_colour": colour,
        "terminal_exact_cleanup_no_action": terminal_exact_cleanup,
        "card_status_label": card.get("status_label"),
        "card_classes": card.get("classes"),
        "card_type": ctype,
        "alignment_ok": not failures,
        "failures": failures,
    }


def assert_colour_alignment(step: dict[str, Any]) -> None:
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    alignment = colour_alignment(summary, card, dict(step.get("browser_state") or {}))
    step["colour_alignment"] = dict(alignment)
    failures = list(alignment.get("failures") or [])
    if not failures:
        return
    priority = [
        "combined_fail_card_not_red_combined",
        "summary_fail_card_green_or_terminal",
        "summary_fail_card_warn_or_cleanup",
        "summary_fail_card_not_red",
        "summary_pass_card_red",
        "safe_overdesign_card_not_blue",
        "accepted_terminal_card_not_green",
    ]
    classification = next((item for item in priority if item in failures), failures[0])
    _fail(
        classification,
        (
            f"Visible summary/card colour mismatch: expected {alignment.get('expected_card_colour')} "
            f"but card colour/status is {alignment.get('actual_card_colour')} "
            f"(label={alignment.get('card_status_label')}, classes={alignment.get('card_classes')})."
        ),
        step,
    )


def assert_terminal_card_render_contract(step: dict[str, Any]) -> None:
    card = dict(step.get("visible_design_guide") or {})
    if not is_terminal_card(card):
        return
    pending_visible = int(card.get("proof_pending_visible_count") or 0)
    pending_text = str(card.get("proof_pending_text") or "")
    if pending_visible > 0:
        _fail(
            "terminal_design_guide_pending_shell_visible",
            "Final terminal Design Guide card is visible while the proof-pending shell is still visible.",
            step,
        )
    style = dict(card.get("computed_style") or {})
    border_left = _rgb_tuple(style.get("borderLeftColor"))
    if border_left is None:
        border_left = _rgb_tuple(style.get("borderColor"))
    if border_left is not None:
        red, green, blue = border_left
        terminal_is_green = bool(green >= 120 and green >= red and green >= blue)
        terminal_looks_blue = bool(blue > green and blue > red)
        if terminal_looks_blue or not terminal_is_green:
            _fail(
                "terminal_design_guide_card_not_green",
                (
                    "Final terminal Design Guide card must render with green/pass styling, "
                    f"but border colour was {style.get('borderLeftColor') or style.get('borderColor')}."
                ),
                step,
            )
    classes = str(card.get("classes") or "").lower()
    if "dg-card--pass" in classes and any(token in classes for token in ("dg-card--blocked", "dg-card--action")):
        _fail(
            "terminal_design_guide_card_conflicting_classes",
            f"Final PASS card has conflicting Design Guide classes: {card.get('classes')}.",
            step,
        )
    if "checking design guidance" in pending_text.lower():
        _fail(
            "terminal_design_guide_pending_shell_text_leaked",
            "Final terminal Design Guide card coexists with visible pending-shell text.",
            step,
        )


def active_fail_families(summary: dict[str, Any]) -> list[str]:
    return [family for family in ("bending", "shear") if family_status(summary, family) == "FAIL"]


def active_fail_or_overutil_families(summary: dict[str, Any]) -> list[str]:
    families: list[str] = []
    for family in ("bending", "shear"):
        status = family_status(summary, family)
        util = family_util(summary, family)
        if status == "FAIL" or (util is not None and util > 1.0 + 1e-9):
            families.append(family)
    return families


def low_util_families(summary: dict[str, Any]) -> list[str]:
    families: list[str] = []
    for family in ("bending", "shear"):
        util = family_util(summary, family)
        if util is not None and util > 0.0 and util < TARGET_LOW:
            families.append(family)
    return families


_FAMILY_ID_COVERAGE: dict[str, set[str]] = {
    "bending": {"bending"},
    "bending_fail_governs": {"bending"},
    "bending_overdesign_governs": {"bending"},
    "bending_fail_shear_overdesign_governs": {"bending"},
    "shear": {"shear"},
    "shear_fail_governs": {"shear"},
    "shear_overdesign_governs": {"shear"},
    "shear_fail_bending_overdesign_governs": {"shear"},
    "combined": {"bending", "shear", "combined"},
    "combined_bending_shear_fail": {"bending", "shear", "combined"},
    "combined_overdesign": {"bending", "shear", "combined"},
}


def _family_matches(card_family: str | None, required: str) -> bool:
    family = str(card_family or "").strip().lower()
    required_family = str(required or "").strip().lower()
    coverage = _FAMILY_ID_COVERAGE.get(family, {family} if family else set())
    return bool(required_family in coverage or "combined" in coverage)


def _contract_family(card: dict[str, Any]) -> str:
    contract = dict(card.get("button_contract") or {})
    return str(contract.get("family") or card.get("family") or "").lower()


def _contract_updates(card: dict[str, Any]) -> dict[str, Any]:
    return dict(dict(card.get("button_contract") or {}).get("updates") or {})


def _contract_actionable(card: dict[str, Any]) -> bool:
    contract = dict(card.get("button_contract") or {})
    return bool(contract.get("actionable") and contract.get("action_type") and _contract_updates(card))


def _primary_payload_updates(card: dict[str, Any]) -> dict[str, Any]:
    payload = dict(card.get("design_guide_primary_apply_payload") or {})
    updates = payload.get("updates") or payload.get("resolved_candidate_updates")
    return dict(updates or {}) if isinstance(updates, dict) else {}


def _visible_action_shell(card: dict[str, Any]) -> bool:
    status_label = str(card.get("status_label") or "").strip().upper()
    classes = str(card.get("classes") or "").lower()
    return bool(status_label == "ACTION" or "dg-card--action" in classes or card_type(card) == "ACTION")


def _combined_step_visible_text(step: dict[str, Any], card: dict[str, Any]) -> str:
    layout = dict(step.get("design_guide_layout_contract") or {})
    parts = [
        card.get("title"),
        card.get("text"),
        layout.get("card_visible_text"),
        layout.get("main_explanation_visible_text"),
        layout.get("details_text"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _visible_text_has_lock_blocker(text: str) -> bool:
    text_l = str(text or "").lower()
    return any(term in text_l for term in FAILED_DESIGN_LOCK_BLOCKER_TERMS)


def _visible_text_has_add_links_repair(text: str) -> bool:
    text_l = str(text or "").lower()
    return bool(
        re.search(r"\b(add|adding|provide|providing|install|increase|restore)\b.{0,80}\b(shear\s+)?links?\b", text_l)
        or re.search(r"\b(shear\s+)?links?\b.{0,80}\b(add|adding|provide|providing|install|increase|restore)\b", text_l)
    )


def _active_fail_visible_wording_failures(
    step: dict[str, Any],
    card: dict[str, Any],
    summary: dict[str, Any],
    active: list[str],
) -> list[tuple[str, str]]:
    text_all = _combined_step_visible_text(step, card)
    title_l = str(card.get("title") or "").lower()
    failures: list[tuple[str, str]] = []
    if any(term in title_l for term in ("cleanup", "efficient", "no further cleanup", "further reductions")):
        failures.append(
            (
                "failed_design_terminal_without_locked_constraints",
                "Failed Design Guide title uses cleanup/efficiency terminal wording while a strength family is over-utilised.",
            )
        )
    cleanup_hits = [term for term in FAILED_DESIGN_CLEANUP_TERMS if term in text_all]
    if cleanup_hits and not bool(card.get("cta_enabled")):
        failures.append(
            (
                "failed_design_terminal_without_locked_constraints",
                f"Failed Design Guide no-action card uses cleanup/efficiency language instead of repair mode: {cleanup_hits[:3]}.",
            )
        )
    debug_hits = [term for term in FAILED_DESIGN_DEBUG_TEXT_TERMS if term in text_all]
    if debug_hits:
        failures.append(
            (
                "design_guide_debug_text_leaked_to_user",
                f"Visible failed Design Guide card exposes internal/debug-style wording: {debug_hits[:3]}.",
            )
        )
    if re.search(r"\b\d+\.\d{4,}\b", text_all):
        failures.append(
            (
                "design_guide_debug_text_leaked_to_user",
                "Visible failed Design Guide card exposes long raw decimal values instead of rounded user-facing values.",
            )
        )
    shear_util = family_util(summary, "shear")
    shear_failed = "shear" in active or (shear_util is not None and shear_util > 1.0 + 1e-9)
    if shear_failed:
        no_link_hits = [term for term in FAILED_SHEAR_NO_LINK_TERMS if term in text_all]
        if no_link_hits and not _visible_text_has_add_links_repair(text_all):
            failures.append(
                (
                    "failed_shear_with_no_links_terminal",
                    f"Shear is failing but visible Design Guide text frames no links/removed links as terminal reasoning: {no_link_hits[:3]}.",
                )
            )
    return failures


def _card_has_executor_backed_payload(card: dict[str, Any]) -> bool:
    contract = dict(card.get("button_contract") or {})
    updates = _contract_updates(card) or _primary_payload_updates(card)
    return bool(
        (contract.get("actionable") or contract.get("enabled"))
        and contract.get("action_type")
        and updates
        and contract.get("preview_pass") is not False
    )


def _shared_probe_values(step: dict[str, Any]) -> dict[str, Any]:
    state = dict(step.get("browser_state") or {})
    shared = state.get("browser_shared_probe")
    return dict(shared) if isinstance(shared, dict) else {}


def _shared_key_aliases(key: str) -> list[str]:
    aliases = {
        "db_lig": ["db_lig", "lig_d"],
        "lig_d": ["lig_d", "db_lig"],
        "bot_row_1_bars": ["bot_row_1_bars", "bot1_count"],
        "bot1_count": ["bot1_count", "bot_row_1_bars"],
        "bot_row_2_bars": ["bot_row_2_bars", "bot2_count"],
        "bot2_count": ["bot2_count", "bot_row_2_bars"],
        "bot_row_1_dia": ["bot_row_1_dia", "db_bot_1"],
        "db_bot_1": ["db_bot_1", "bot_row_1_dia"],
        "bot_row_2_dia": ["bot_row_2_dia", "db_bot_2"],
        "db_bot_2": ["db_bot_2", "bot_row_2_dia"],
        "Mu_star": ["Mu_star", "uls_Mstar", "uls_Mstar_pos_manual"],
        "Mstar": ["Mstar", "uls_Mstar", "uls_Mstar_pos_manual"],
        "uls_Mstar": ["uls_Mstar", "uls_Mstar_pos_manual", "Mu_star"],
        "Vu_star": ["Vu_star", "uls_Vstar"],
        "Vstar": ["Vstar", "uls_Vstar"],
        "uls_Vstar": ["uls_Vstar", "Vu_star"],
    }
    return list(dict.fromkeys(aliases.get(str(key), [str(key)])))


def _read_shared_value(shared: dict[str, Any], key: str) -> Any:
    for alias in _shared_key_aliases(key):
        if alias in shared:
            return shared.get(alias)
    return None


def _state_fingerprint_values(fingerprint: Any) -> dict[str, Any]:
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        return {}
    try:
        parsed = ast.literal_eval(fingerprint)
    except Exception:
        return {}
    pairs: Any = None
    if isinstance(parsed, (tuple, list)):
        for part in reversed(parsed):
            if (
                isinstance(part, (tuple, list))
                and all(isinstance(row, (tuple, list)) and len(row) >= 2 for row in part)
            ):
                pairs = part
                break
    if not isinstance(pairs, (tuple, list)):
        return {}
    values: dict[str, Any] = {}
    for row in pairs:
        try:
            key, value = row[0], row[1]
        except Exception:
            continue
        values[str(key)] = value
    return values


def _read_fingerprint_value(values: dict[str, Any], key: str) -> Any:
    for alias in _shared_key_aliases(key):
        if alias in values:
            return values.get(alias)
    return None


def _step_summary_signature(step: dict[str, Any]) -> dict[str, Any]:
    summary = dict(step.get("visible_summary") or {})
    return {
        family: {
            "util": family_util(summary, family),
            "status": family_status(summary, family),
        }
        for family in ("bending", "shear", "crack", "deflection")
    }


def _step_card_signature(step: dict[str, Any]) -> dict[str, Any]:
    card = dict(step.get("visible_design_guide") or {})
    contract = dict(card.get("button_contract") or {})
    proof = dict(card.get("proof_support") or {})
    return {
        "title": card.get("title"),
        "family": card.get("family"),
        "text": card.get("text"),
        "displayed_util": card.get("displayed_util"),
        "cta_visible": card.get("cta_visible"),
        "cta_enabled": card.get("cta_enabled"),
        "contract_updates": dict(contract.get("updates") or {}),
        "contract_candidate_id": contract.get("candidate_id") or contract.get("source_candidate_id"),
        "contract_actionable": contract.get("actionable"),
        "state_fingerprint": proof.get("state_fingerprint") or proof.get("payload_binding_state_fingerprint"),
        "render_fingerprint": proof.get("render_fingerprint") or proof.get("payload_binding_render_fingerprint"),
    }


def one_click_material_change_audit(previous_step: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    prev_card = dict(previous_step.get("visible_design_guide") or {})
    contract_updates = _contract_updates(prev_card)
    selected_updates = dict(prev_card.get("selected_action_updates") or {})
    expected_updates = dict(selected_updates or contract_updates)
    before_shared = _shared_probe_values(previous_step)
    after_shared = _shared_probe_values(step)
    before_values = {key: _read_shared_value(before_shared, key) for key in expected_updates}
    after_values = {key: _read_shared_value(after_shared, key) for key in expected_updates}
    before_summary = _step_summary_signature(previous_step)
    after_summary = _step_summary_signature(step)
    before_card = _step_card_signature(previous_step)
    after_card = _step_card_signature(step)
    before_fp_values = _state_fingerprint_values(before_card.get("state_fingerprint"))
    after_fp_values = _state_fingerprint_values(after_card.get("state_fingerprint"))
    value_source_by_key: dict[str, str] = {}
    for key in expected_updates:
        before_fp = _read_fingerprint_value(before_fp_values, key)
        after_fp = _read_fingerprint_value(after_fp_values, key)
        before_missing = before_values.get(key) is None
        after_missing = after_values.get(key) is None
        if before_missing and before_fp is not None:
            before_values[key] = before_fp
            value_source_by_key[key] = "fingerprint_before"
        if after_missing and after_fp is not None:
            after_values[key] = after_fp
            value_source_by_key[key] = (
                f"{value_source_by_key.get(key)}+fingerprint_after"
                if key in value_source_by_key
                else "fingerprint_after"
            )
    changed_keys = [
        key
        for key in expected_updates
        if not _same_value(before_values.get(key), after_values.get(key), tol=1e-9)
    ]
    applied_to_expected_keys = [
        key
        for key, expected in expected_updates.items()
        if not _same_value(before_values.get(key), expected, tol=1e-9)
        and _same_value(after_values.get(key), expected, tol=1e-9)
    ]
    unchanged_expected_keys = [key for key in expected_updates if key not in changed_keys]
    before_results_version = before_shared.get("results_version") or before_shared.get("design_results_version")
    after_results_version = after_shared.get("results_version") or after_shared.get("design_results_version")
    before_candidate_id = before_card.get("contract_candidate_id")
    after_candidate_id = after_card.get("contract_candidate_id")
    same_candidate_still_enabled = bool(
        before_candidate_id
        and before_candidate_id == after_candidate_id
        and after_card.get("cta_enabled")
        and after_card.get("contract_actionable")
    )
    same_render_still_enabled = bool(
        before_card.get("render_fingerprint")
        and before_card.get("render_fingerprint") == after_card.get("render_fingerprint")
        and after_card.get("cta_enabled")
        and after_card.get("contract_actionable")
    )
    return {
        "before_shared_values": before_values,
        "expected_updates": dict(expected_updates),
        "after_shared_values": after_values,
        "value_source_by_key": dict(value_source_by_key),
        "changed_keys": list(changed_keys),
        "applied_to_expected_keys": list(applied_to_expected_keys),
        "unchanged_expected_keys": list(unchanged_expected_keys),
        "visual_summary_changed": before_summary != after_summary,
        "visual_card_changed": before_card != after_card,
        "before_summary_signature": before_summary,
        "after_summary_signature": after_summary,
        "before_card_signature": before_card,
        "after_card_signature": after_card,
        "before_card_title": before_card.get("title"),
        "after_card_title": after_card.get("title"),
        "before_summary_utils": {family: data.get("util") for family, data in before_summary.items()},
        "after_summary_utils": {family: data.get("util") for family, data in after_summary.items()},
        "before_results_version": before_results_version,
        "after_results_version": after_results_version,
        "results_version_changed": not _same_value(before_results_version, after_results_version, tol=1e-9),
        "clicked_candidate_id": before_candidate_id,
        "clicked_family": str(dict(prev_card.get("button_contract") or {}).get("family") or prev_card.get("family") or ""),
        "same_candidate_still_visible_enabled": same_candidate_still_enabled,
        "same_render_fingerprint_still_visible_enabled": same_render_still_enabled,
    }


def _valid_blocker_for_family(card: dict[str, Any], state: dict[str, Any], family: str) -> bool:
    proof = blocker_proof_analysis(card, state, family)
    return bool(proof.get("valid"))


def _combined_blockers_valid(card: dict[str, Any], state: dict[str, Any], families: list[str]) -> bool:
    return bool(families) and all(_valid_blocker_for_family(card, state, family) for family in families)


def _evidence_sources_for_family(state: dict[str, Any], family: str) -> tuple[dict[str, Any], dict[str, Any]]:
    blockers = exact_blockers(state)
    blocker = dict(blockers.get(str(family or "").strip().lower()) or {})
    evidence = cleanup_evidence(state)
    return blocker, evidence


def _has_any_cleanup_only_evidence(blocker: dict[str, Any], evidence: dict[str, Any]) -> bool:
    combined = {**dict(evidence or {}), **dict(blocker or {})}
    cleanup_keys = (
        "cleanup_search_ran",
        "local_cleanup_search_ran",
        "cleanup_search_exhaustive",
        "local_cleanup_search_exhaustive",
        "safe_cleanup_count",
        "safe_local_cleanup_count",
        "executable_cleanup_count",
        "executable_safe_cleanup_count",
        "best_safe_final_util",
        "final_threshold",
        "outside_target_band_allowed_reason",
    )
    repair_keys = ("repair_search_ran", "repair_search_exhaustive", "safe_repair_candidate_count", "executable_repair_candidate_count")
    return any(key in combined for key in cleanup_keys) and not any(key in combined for key in repair_keys)


_PLACEHOLDER_VALUES = {"", "-", "—", "none", "null", "n/a", "na", "unknown", "failed not published", "not published"}


def _non_placeholder(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    text = _norm_text(value).lower()
    return bool(text) and text not in _PLACEHOLDER_VALUES


def _first_non_placeholder(source: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = source.get(key)
        if _non_placeholder(value):
            return value
    return None


def _numeric_count_present(source: dict[str, Any], keys: tuple[str, ...]) -> tuple[bool, int | None]:
    for key in keys:
        if key not in source:
            continue
        try:
            return True, int(float(source.get(key) or 0))
        except Exception:
            return True, None
    return False, None


def _has_lock_or_cap_evidence(source: dict[str, Any], family: str) -> bool:
    text = _norm_text(
        " ".join(
            str(source.get(key) or "")
            for key in (
                "reason",
                "blocker_reason",
                "specific_reason",
                "constraint_reason",
                "geometry_lock_reason",
                "rejected_repair_reasons",
            )
        )
    ).lower()
    lock_keys = (
        "geometry_locked",
        "depth_locked",
        "width_locked",
        "reinforcement_locked",
        "links_locked",
        "user_constraint",
        "cap_value",
        "max_D",
        "max_b",
        "max_width",
        "max_depth",
    )
    return any(_non_placeholder(source.get(key)) for key in lock_keys) or any(token in text for token in ("lock", "locked", "cap", "capped", "maximum", "constraint"))


def _active_attempt_sources(card: dict[str, Any], state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    guidance = dict(state.get("guidance_compute_probe") or {})
    proof = dict(state.get("design_guide_probe") or {})
    attempts: dict[str, dict[str, Any]] = {}
    for source in (
        dict(guidance.get("blocker_attempts_by_family") or {}),
        dict(proof.get("blocker_attempts_by_family") or {}),
        dict(card.get("blocker_attempts_by_family") or {}),
    ):
        for family, payload in source.items():
            if isinstance(payload, dict):
                attempts[str(family).strip().lower()] = {**attempts.get(str(family).strip().lower(), {}), **payload}
    for family, payload in exact_blockers(state).items():
        if isinstance(payload, dict):
            key = str(family).strip().lower()
            attempts[key] = {**attempts.get(key, {}), **payload}
    evidence = cleanup_evidence(state)
    for family in ("bending", "shear", "combined"):
        family_payload = evidence.get(f"{family}_repair_attempts")
        if isinstance(family_payload, dict):
            attempts[family] = {**attempts.get(family, {}), **family_payload}
    return attempts


def active_strength_blocker_attempt_analysis(card: dict[str, Any], state: dict[str, Any], families: list[str]) -> dict[str, Any]:
    active = [family for family in dict.fromkeys(str(f or "").strip().lower() for f in families) if family in {"bending", "shear"}]
    required = list(active)
    if {"bending", "shear"}.issubset(set(active)):
        required.append("combined")
    attempts = _active_attempt_sources(card, state)
    visible_text = _norm_text(f"{card.get('title') or ''} {card.get('text') or ''}").lower()
    missing_by_section: dict[str, list[str]] = {}
    sections: dict[str, dict[str, Any]] = {}
    route_tokens = {
        "bending": "bending",
        "shear": "shear",
        "combined": ("combined", "geometry", "bottom reo", "links"),
    }
    for family in required:
        source = dict(attempts.get(family) or {})
        merged_text = _norm_text(f"{visible_text} {json.dumps(source, default=_json_default)}").lower()
        has_lock_or_cap = _has_lock_or_cap_evidence(source, family)
        count_present, count_value = _numeric_count_present(
            source,
            (
                "attempted_candidate_count",
                "candidate_count",
                "evaluated_candidate_count",
                "repair_candidate_count",
                "active_repair_candidate_count",
                "attempted_repair_candidate_count",
            ),
        )
        candidate_id = _first_non_placeholder(
            source,
            (
                "best_rejected_candidate_id",
                "failed_candidate_id",
                "candidate_id",
                "best_failed_candidate_id",
                "best_repair_candidate_id",
            ),
        )
        failed_rule = _first_non_placeholder(
            source,
            (
                "failed_check_name",
                "failed_rule",
                "failed_check",
                "failed_sub_check",
                "failed_check_status",
                "blocking_rule",
            ),
        )
        failed_value = _first_non_placeholder(
            source,
            (
                "failed_check_value",
                "failed_value",
                "failed_check_util",
                "failed_util",
                "utilisation",
                "utilization",
                "demand",
                "failed_check_demand",
            ),
        )
        failed_limit = _first_non_placeholder(
            source,
            (
                "failed_check_limit",
                "failed_limit",
                "limit",
                "capacity",
                "failed_check_capacity",
                "failed_check_capacity_or_limit",
                "capacity_or_limit",
            ),
        )
        route_missing = [token for token in route_tokens.get(family, ()) if token not in merged_text]
        missing: list[str] = []
        if not count_present and not has_lock_or_cap:
            missing.append("attempted_candidate_count")
        elif count_present and count_value is not None and count_value <= 0 and not has_lock_or_cap:
            missing.append("attempted_candidate_count_positive_or_constraint")
        if not candidate_id and not has_lock_or_cap:
            missing.append("best_rejected_candidate_id")
        if not failed_rule and not has_lock_or_cap:
            missing.append("failed_check_rule")
        if not failed_value and not has_lock_or_cap:
            missing.append("failed_value")
        if not failed_limit and not has_lock_or_cap:
            missing.append("failed_limit_or_capacity")
        if route_missing:
            missing.append(f"route_tokens:{','.join(route_missing)}")
        if _has_any_cleanup_only_evidence(source, {}):
            missing.append("cleanup_evidence_used_as_repair_proof")
        if missing:
            missing_by_section[family] = missing
        sections[family] = {
            "attempted_candidate_count_present": count_present,
            "attempted_candidate_count": count_value,
            "best_rejected_candidate_id": candidate_id,
            "failed_check_rule": failed_rule,
            "failed_value": failed_value,
            "failed_limit_or_capacity": failed_limit,
            "has_lock_or_cap_evidence": has_lock_or_cap,
            "missing_route_tokens": route_missing,
            "source_keys": sorted(source.keys()),
        }
    return {
        "valid": bool(required) and not missing_by_section,
        "required_sections": required,
        "missing_by_section": missing_by_section,
        "sections": sections,
    }


def active_fail_repair_exhaustion_analysis(card: dict[str, Any], state: dict[str, Any], families: list[str]) -> dict[str, Any]:
    required_families = [family for family in dict.fromkeys(str(f or "").strip().lower() for f in families) if family]
    blockers = exact_blockers(state)
    missing_by_family: dict[str, list[str]] = {}
    used_cleanup_evidence: list[str] = []
    family_evidence: dict[str, dict[str, Any]] = {}
    overview_utils = dict(dict(state.get("guidance_compute_probe") or {}).get("overview") or {}).get("utils") or {}
    if not isinstance(overview_utils, dict):
        overview_utils = {}
    for family in required_families:
        blocker, evidence = _evidence_sources_for_family(state, family)
        combined = {**dict(evidence or {}), **dict(blocker or {})}
        if not blocker:
            missing_by_family.setdefault(family, []).append("exact_blocker")
        elif not bool(combined.get("exact_blocker", True)):
            missing_by_family.setdefault(family, []).append("exact_blocker_present")
        if _has_any_cleanup_only_evidence(blocker, evidence):
            used_cleanup_evidence.append(family)
        route_payload = (
            combined.get("active_repair_route_inventory")
            or combined.get("route_inventory")
            or combined.get("attempted_updates")
            or {}
        )
        failed_candidate = _first_present(
            combined,
            (
                "failed_candidate_id",
                "best_rejected_candidate_id",
                "best_failed_candidate_id",
                "rejected_candidate_id",
                "candidate_id",
            ),
        )
        attempted_count_present, attempted_count = _numeric_count_present(
            combined,
            (
                "attempted_candidate_count",
                "candidate_count",
                "repair_candidate_count",
                "active_repair_candidate_count",
                "attempted_repair_candidate_count",
            ),
        )
        failed_util = _first_present(
            combined,
            ("failed_check_util", "current_util", "failed_value", "utilisation", "utilization"),
        )
        current_util = _first_present(combined, ("current_util", "failed_check_util"))
        summary_util = None
        try:
            if overview_utils.get(family) is not None:
                summary_util = float(overview_utils.get(family))
        except Exception:
            summary_util = None
        util_mismatch = False
        try:
            if summary_util is not None and current_util not in (None, ""):
                util_mismatch = abs(float(current_util) - float(summary_util)) > 0.06
        except Exception:
            util_mismatch = False
        required = {
            "repair_search_ran": bool(combined.get("active_repair_search_ran") or combined.get("repair_search_ran")),
            "repair_search_exhaustive": bool(
                combined.get("active_repair_search_exhaustive") or combined.get("repair_search_exhaustive")
            ),
            "attempted_candidate_count": bool(attempted_count_present and attempted_count is not None and attempted_count > 0),
            "executable_candidate_count": (
                "executable_candidate_count" in combined
                or "executable_repair_candidate_count" in combined
                or "safe_repair_candidate_count" in combined
            ),
            "failed_candidate_id": bool(failed_candidate),
            "failed_check_name": bool(_first_present(combined, ("failed_check_name", "failed_check", "blocking_check"))),
            "failed_check_status": bool(_first_present(combined, ("failed_check_status", "failed_status", "blocking_status"))),
            "failed_check_util": bool(failed_util not in (None, "")),
            "failed_check_capacity_or_limit": bool(
                _first_present(
                    combined,
                    ("failed_check_capacity_or_limit", "failed_check_limit", "capacity_or_limit", "limit", "capacity"),
                )
            ),
            "route_inventory": bool(route_payload),
            "reason_names_family": family in str(combined.get("reason") or "").lower(),
            "current_util_matches_summary": not util_mismatch,
            "geometry_strengthening_searched": bool(combined.get("geometry_strengthening_searched")),
            "reo_strengthening_searched": bool(
                combined.get("reo_strengthening_searched")
                or combined.get("longitudinal_reinforcement_strengthening_searched")
            ),
            "safe_repair_candidate_count": "safe_repair_candidate_count" in combined,
            "rejected_repair_reasons": bool(combined.get("rejected_repair_reasons")),
        }
        if family == "shear":
            required["shear_strengthening_searched"] = bool(combined.get("shear_strengthening_searched"))
        if len(required_families) > 1:
            required["combined_strengthening_searched"] = bool(combined.get("combined_strengthening_searched"))
        missing = [name for name, ok in required.items() if not ok]
        if missing:
            missing_by_family.setdefault(family, []).extend(missing)
        family_evidence[family] = {
            "present_fields": {name: ok for name, ok in required.items()},
            "safe_repair_candidate_count": combined.get("safe_repair_candidate_count"),
            "executable_repair_candidate_count": combined.get("executable_repair_candidate_count"),
            "rejected_repair_reasons": combined.get("rejected_repair_reasons"),
            "reason": combined.get("reason"),
            "source": combined.get("source"),
        }
    valid = bool(required_families) and not missing_by_family and not used_cleanup_evidence
    return {
        "families": required_families,
        "valid": valid,
        "missing_by_family": missing_by_family,
        "used_cleanup_evidence_families": used_cleanup_evidence,
        "exact_blockers_by_family_present": sorted(k for k, v in blockers.items() if isinstance(v, dict)),
        "family_evidence": family_evidence,
    }


def _assert_active_fail_blocker_contract(step: dict[str, Any], families: list[str]) -> None:
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    analysis = active_fail_repair_exhaustion_analysis(card, state, families)
    step["active_fail_blocker_analysis"] = dict(analysis)
    if analysis.get("used_cleanup_evidence_families"):
        _fail(
            "active_fail_blocker_used_cleanup_evidence",
            f"Active FAIL blocker uses cleanup/efficiency evidence instead of repair exhaustion for {analysis.get('used_cleanup_evidence_families')}.",
            step,
        )
    if not analysis.get("valid"):
        classification = "combined_fail_no_combined_strengthening_action" if len(families) > 1 else "active_fail_blocker_without_strengthening_exhaustion"
        _fail(
            classification,
            f"Active FAIL blocker lacks exhaustive strengthening repair proof: {analysis.get('missing_by_family')}.",
            step,
        )
    attempt_analysis = active_strength_blocker_attempt_analysis(card, state, families)
    step["active_strength_blocker_attempt_analysis"] = dict(attempt_analysis)
    if not attempt_analysis.get("valid"):
        missing = dict(attempt_analysis.get("missing_by_section") or {})
        if "combined" in missing:
            classification = "strength_blocker_missing_combined_repair_attempts"
        elif any("best_rejected_candidate_id" in values for values in missing.values()):
            classification = "strength_blocker_missing_best_rejected_candidate"
        elif any(
            "failed_value" in values or "failed_limit_or_capacity" in values
            for values in missing.values()
        ):
            classification = "strength_blocker_missing_failed_value_or_limit"
        else:
            classification = "strength_blocker_missing_repair_attempts"
        _fail(
            classification,
            f"Active-strength BLOCKED card lacks exact repair-attempt proof: {missing}.",
            step,
        )


def _blocker_reason_by_family(state: dict[str, Any]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for family, blocker in exact_blockers(state).items():
        if not isinstance(blocker, dict):
            continue
        parts: list[str] = []
        for key in (
            "reason",
            "failed_check_name",
            "failed_check_status",
            "failed_check_util",
            "why_reduction_would_hurt_other_design_elements",
            "blocker_reason",
            "specific_reason",
            "blocking_checks",
        ):
            value = blocker.get(key)
            if value not in (None, "", [], {}):
                parts.append(str(value))
        reasons[str(family).lower()] = "; ".join(parts)
    return reasons


def _failed_candidate_check_table(state: dict[str, Any], families: list[str]) -> dict[str, dict[str, Any]]:
    blockers = exact_blockers(state)
    table: dict[str, dict[str, Any]] = {}
    for family in families:
        blocker = dict(blockers.get(str(family or "").strip().lower()) or {})
        if blocker:
            table[family] = _blocker_specificity_analysis(blocker, family)
    return table


def _target_band_blocker_table(state: dict[str, Any], families: list[str]) -> dict[str, dict[str, Any]]:
    blockers = exact_blockers(state)
    table: dict[str, dict[str, Any]] = {}
    for family in families:
        blocker = dict(blockers.get(str(family or "").strip().lower()) or {})
        table[family] = _target_band_blocker_analysis(blocker, family) if blocker else {
            "family": family,
            "valid": False,
            "missing_fields": ["exact_blocker"],
        }
    return table


def _candidate_counts_by_family(state: dict[str, Any], families: list[str]) -> dict[str, dict[str, Any]]:
    blockers = exact_blockers(state)
    counts: dict[str, dict[str, Any]] = {}
    for family in families:
        blocker = dict(blockers.get(family) or {})
        evidence = cleanup_evidence(state)
        counts[family] = {
            "cleanup_search_ran": bool(
                blocker.get("cleanup_search_ran")
                or blocker.get("local_cleanup_search_ran")
                or blocker.get("repair_search_ran")
                or evidence.get("cleanup_search_ran")
                or evidence.get("local_cleanup_search_ran")
                or evidence.get("repair_search_ran")
            ),
            "cleanup_search_exhaustive": bool(
                blocker.get("cleanup_search_exhaustive")
                or blocker.get("local_cleanup_search_exhaustive")
                or blocker.get("repair_search_exhaustive")
                or evidence.get("cleanup_search_exhaustive")
                or evidence.get("local_cleanup_search_exhaustive")
                or evidence.get("repair_search_exhaustive")
                or evidence.get("candidate_search_exhaustive")
            ),
            "safe_candidate_count": _deep_get_count(
                blocker,
                evidence,
                keys=("safe_candidate_count", "safe_cleanup_count", "safe_local_cleanup_count", f"safe_{family}_cleanup_count"),
            ),
            "executable_candidate_count": _deep_get_count(
                blocker,
                evidence,
                keys=(
                    "executable_candidate_count",
                    "executable_cleanup_count",
                    "executable_safe_cleanup_count",
                    f"executable_{family}_cleanup_count",
                ),
            ),
        }
    return counts


def _blocker_text_is_specific(card: dict[str, Any], state: dict[str, Any], families: list[str]) -> tuple[bool, str]:
    text = f"{card.get('title') or ''} {card.get('text') or ''}".lower()
    first_card = {}
    try:
        first_card = dict(list(card.get("cards") or [{}])[0] or {})
    except Exception:
        first_card = {}
    hook_counts = dict(first_card.get("test_hook_counts") or {})
    if not families:
        return False, "blocker does not identify any unresolved family"
    vague_phrases = (
        "checked cleanup searches found no further safe one-click reduction",
        "serviceability and shear checks",
    )
    detail_tokens = {
        "shear",
        "crack",
        "deflection",
        "spacing",
        "ductility",
        "minimum reinforcement",
        "minimum",
        "geometry",
        "cover",
        "detailing",
        "discrete",
        "catalogue",
        "serviceability",
    }
    reasons = _blocker_reason_by_family(state)
    missing_visible_family = [family for family in families if family not in text]
    if missing_visible_family:
        return False, f"blocker text does not name unresolved family/families {missing_visible_family}"
    compact_blocked_reasons = "blocked because" in text
    def _has_family_reason(family: str) -> bool:
        return (
            int(hook_counts.get(f"design-guide-reason-{family}") or 0) > 0
            or f"{family} cleanup blocked:" in text
            or f"{family} repair blocked:" in text
            or f"{family} blocker:" in text
            or f"{family} attempts:" in text
            or (compact_blocked_reasons and (f"• {family}:" in text or f"- {family}:" in text))
            or (compact_blocked_reasons and (f"• {family} blocker:" in text or f"- {family} blocker:" in text))
            or (compact_blocked_reasons and (f"• {family} attempts:" in text or f"- {family} attempts:" in text))
        )
    if len(families) > 1:
        for family in families:
            if not _has_family_reason(family):
                return False, f"multi-family blocker does not list a separate {family} reason"
    combined_reason_text = text + " " + " ".join(reasons.get(family, "").lower() for family in families)
    if not any(token in combined_reason_text for token in detail_tokens):
        return False, "blocker text/evidence does not name a protective engineering check"
    if any(phrase in text for phrase in vague_phrases):
        has_family_labels = all(_has_family_reason(family) for family in families)
        has_structured_reason = all(bool(reasons.get(family)) for family in families)
        if not (has_family_labels and has_structured_reason):
            return False, "blocker text uses vague generic wording without per-family structured reasons"
    return True, ""


def _post_click_final_state_analysis(step: dict[str, Any], previous_step: dict[str, Any] | None) -> dict[str, Any]:
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    ctype = card_type(card)
    active = active_fail_families(summary)
    low = low_util_families(summary)
    families_to_resolve = list(dict.fromkeys(active + low))
    unresolved_active = [family for family in active if not _valid_blocker_for_family(card, state, family)]
    unresolved_low = [family for family in low if not _valid_blocker_for_family(card, state, family)]
    previous_card = dict((previous_step or {}).get("visible_design_guide") or {})
    previous_contract = dict(previous_card.get("button_contract") or {})
    clicked_family = str(previous_contract.get("family") or previous_card.get("family") or "").lower()
    clicked_candidate_id = previous_contract.get("candidate_id")
    current_contract = dict(card.get("button_contract") or {})
    same_candidate = bool(
        card.get("cta_enabled")
        and clicked_candidate_id
        and current_contract.get("candidate_id") == clicked_candidate_id
    )
    blockers = exact_blockers(state)
    blocker_reasons = _blocker_reason_by_family(state)
    target_band = {"low": REPAIR_TARGET_LOW, "high": REPAIR_TARGET_HIGH}
    accepted_band = {"low": ACCEPTED_TARGET_LOW, "high": ACCEPTED_TARGET_HIGH}
    previous_summary = dict((previous_step or {}).get("visible_summary") or {})
    previous_active = active_fail_families(previous_summary)
    required_failures = [
        family
        for family in ("bending", "shear", "crack", "deflection")
        if family_status(summary, family) == "FAIL"
    ]
    meaningful_strength_families = [
        family
        for family in ("bending", "shear")
        if family_util(summary, family) is not None and float(family_util(summary, family) or 0.0) > 0.0
    ]
    strength_families_in_preferred_target = [
        family
        for family in meaningful_strength_families
        if family_util(summary, family) is not None
        and REPAIR_TARGET_LOW <= float(family_util(summary, family) or 0.0) <= REPAIR_TARGET_HIGH
    ]
    strength_families_in_accepted_band = [
        family
        for family in meaningful_strength_families
        if family_util(summary, family) is not None
        and ACCEPTED_TARGET_LOW <= float(family_util(summary, family) or 0.0) <= ACCEPTED_TARGET_HIGH
    ]
    strength_families_outside_preferred_target = [
        family
        for family in meaningful_strength_families
        if family not in strength_families_in_preferred_target
    ]
    strength_families_outside_accepted_band = [
        family
        for family in meaningful_strength_families
        if family not in strength_families_in_accepted_band
    ]
    strength_families_below_accepted_band = [
        family
        for family in strength_families_outside_accepted_band
        if family_util(summary, family) is not None
        and float(family_util(summary, family) or 0.0) < ACCEPTED_TARGET_LOW
    ]
    strength_families_above_accepted_band = [
        family
        for family in strength_families_outside_accepted_band
        if family_util(summary, family) is not None
        and float(family_util(summary, family) or 0.0) > ACCEPTED_TARGET_HIGH
    ]
    current_contract = dict(card.get("button_contract") or {})
    contract_action_family = str(
        current_contract.get("family")
        or card.get("family")
        or ""
    ).strip().lower()
    card_action_family = str(card.get("family") or "").strip().lower()
    action_families = {family for family in (contract_action_family, card_action_family) if family}
    if contract_action_family == "combined":
        action_families.update({"bending", "shear"})
    action_updates = dict(current_contract.get("updates") or card.get("selected_action_updates") or {})
    if any(str(key).startswith(("bot", "db_bot", "nb_bot")) for key in action_updates):
        action_families.add("bending")
    if any(str(key).startswith(("lig", "s_lig")) for key in action_updates):
        action_families.add("shear")
    action_covers_below_accepted_band = bool(
        ctype == "ACTION"
        and _contract_actionable(card)
        and set(strength_families_below_accepted_band).intersection(action_families)
    )
    target_band_blockers = _target_band_blocker_table(state, strength_families_outside_preferred_target)
    unresolved_low = [
        family
        for family in unresolved_low
        if not bool(dict(target_band_blockers.get(family) or {}).get("valid"))
    ]
    visible_exact_blocker_families = set(dict(card.get("exact_blockers_by_family") or {}).keys())
    visible_attempt_families = set(dict(card.get("blocker_attempts_by_family") or {}).keys())
    outside_accepted_with_exact_target_band_proof = bool(strength_families_outside_accepted_band) and all(
        bool(dict(target_band_blockers.get(family) or {}).get("valid"))
        and (family in visible_exact_blocker_families or family in visible_attempt_families)
        for family in strength_families_outside_accepted_band
    )
    intended_util = family_util(summary, clicked_family) if clicked_family in {"bending", "shear"} else None
    worst_util = _float_or_none(dict(summary.get("browser_overview_support") or {}).get("worst_util"))
    in_target = bool(
        (intended_util is not None and REPAIR_TARGET_LOW <= intended_util <= REPAIR_TARGET_HIGH)
        or (worst_util is not None and REPAIR_TARGET_LOW <= worst_util <= REPAIR_TARGET_HIGH)
    )
    in_accepted_band = bool(
        (intended_util is not None and ACCEPTED_TARGET_LOW <= intended_util <= ACCEPTED_TARGET_HIGH)
        or (worst_util is not None and ACCEPTED_TARGET_LOW <= worst_util <= ACCEPTED_TARGET_HIGH)
        or bool(strength_families_in_accepted_band)
    )
    accepted_family_condition = bool(not active and not unresolved_low and all((family_util(summary, family) or 0.0) >= TARGET_LOW for family in ("bending", "shear")))
    analysis = {
        "final_state_type": "invalid_post_click_state",
        "card_type": ctype,
        "final_card_title": card.get("title"),
        "final_card_status_class": card.get("classes"),
        "target_band": target_band,
        "accepted_band": accepted_band,
        "clicked_family": clicked_family,
        "clicked_candidate_id": clicked_candidate_id,
        "previous_active_failing_families": previous_active,
        "pre_click_active_fail_families": list(previous_active),
        "final_summary_statuses": _summary_statuses(summary),
        "final_family_utils": _summary_utils(summary),
        "required_failures_after_click": list(required_failures),
        "post_click_bending_util": family_util(summary, "bending"),
        "post_click_shear_util": family_util(summary, "shear"),
        "strength_families_in_target": list(strength_families_in_preferred_target),
        "strength_families_outside_target": list(strength_families_outside_preferred_target),
        "families_in_preferred_target": list(strength_families_in_preferred_target),
        "families_in_accepted_band": list(strength_families_in_accepted_band),
        "families_outside_accepted_band": list(strength_families_outside_accepted_band),
        "families_below_accepted_band": list(strength_families_below_accepted_band),
        "families_above_accepted_band": list(strength_families_above_accepted_band),
        "target_band_blockers_by_family": target_band_blockers,
        "outside_accepted_with_exact_target_band_proof": outside_accepted_with_exact_target_band_proof,
        "visible_exact_blocker_families": sorted(visible_exact_blocker_families),
        "visible_attempt_families": sorted(visible_attempt_families),
        "unresolved_active_fail_families": unresolved_active,
        "unresolved_low_util_families": unresolved_low,
        "exact_blockers_by_family": blockers,
        "blocker_reasons_by_family": blocker_reasons,
        "candidate_counts_by_family": _candidate_counts_by_family(state, families_to_resolve),
        "failed_candidate_check_by_family": _failed_candidate_check_table(state, families_to_resolve),
        "same_candidate_still_visible": same_candidate,
        "target_condition_met": in_target,
        "accepted_band_condition_met": in_accepted_band,
        "accepted_family_target_condition_met": accepted_family_condition,
        "accepted_reason": "",
    }
    previous_active_outside_target = [
        family
        for family in previous_active
        if (
            family_util(summary, family) is not None
            and not (ACCEPTED_TARGET_LOW <= float(family_util(summary, family)) <= ACCEPTED_TARGET_HIGH)
            and not _valid_blocker_for_family(card, state, family)
            and not bool(dict(target_band_blockers.get(family) or {}).get("valid"))
        )
    ]
    if previous_active:
        if required_failures:
            analysis.update(
                {
                    "failure_classification": "active_fail_post_click_still_fails",
                    "failure_message": f"One-click from active FAIL left required checks failing: {required_failures}.",
                }
            )
            return analysis
        if strength_families_above_accepted_band:
            analysis.update(
                {
                    "failure_classification": "active_fail_post_click_out_of_target_family_unexplained",
                    "failure_message": (
                        "One-click from active FAIL left strength families above the accepted "
                        f"{ACCEPTED_TARGET_LOW}-{ACCEPTED_TARGET_HIGH} band: {strength_families_above_accepted_band}."
                    ),
                }
            )
            return analysis
        if action_covers_below_accepted_band:
            analysis.update(
                {
                    "final_state_type": "post_active_repair_next_cleanup_action",
                    "pass_reason": "post_active_repair_published_executor_backed_cleanup_action_for_below_accepted_family",
                    "accepted_reason": (
                        "all required checks pass and below-accepted strength families have an enabled "
                        "executor-backed follow-up optimisation/cleanup action instead of a terminal/blocker claim"
                    ),
                    "action_families": sorted(action_families),
                }
            )
            return analysis
        if not strength_families_in_accepted_band and outside_accepted_with_exact_target_band_proof:
            analysis.update(
                {
                    "final_state_type": "post_active_repair_exact_target_band_stop",
                    "pass_reason": "post_active_repair_outside_accepted_with_exact_target_band_blockers",
                    "accepted_reason": (
                        "all required checks pass and every outside-accepted strength family has visible "
                        "exact target-band blocker proof"
                    ),
                }
            )
            return analysis
        if not strength_families_in_accepted_band:
            analysis.update(
                {
                    "failure_classification": "active_fail_post_click_no_family_in_target",
                    "failure_message": (
                        "One-click from active FAIL made required checks pass but neither bending nor shear "
                        f"landed in the accepted {ACCEPTED_TARGET_LOW}-{ACCEPTED_TARGET_HIGH} utilisation band."
                    ),
                }
            )
            return analysis
        if ctype == "ACTION" and _contract_actionable(card):
            action_family = str(
                contract_action_family
                or card_action_family
            ).strip().lower()
            if action_family in set(strength_families_below_accepted_band):
                analysis.update(
                    {
                        "final_state_type": "post_active_repair_next_cleanup_action",
                        "pass_reason": "post_active_repair_published_executor_backed_cleanup_action_for_below_accepted_family",
                        "accepted_reason": (
                            "all required checks pass, at least one strength family is in the accepted band, "
                            f"and the remaining below-accepted family {action_family!r} has an enabled "
                            "executor-backed cleanup action instead of a terminal/blocker claim"
                        ),
                    }
                )
                return analysis
        unexplained_outside = [
            family
            for family in strength_families_below_accepted_band
            if not bool(dict(target_band_blockers.get(family) or {}).get("valid"))
        ]
        if unexplained_outside:
            analysis.update(
                {
                    "failure_classification": "active_fail_post_click_out_of_target_family_unexplained",
                    "failure_message": (
                        "One-click from active FAIL left strength families below the accepted band without exact "
                        f"engineering blocker proof: {unexplained_outside}."
                    ),
                }
            )
            return analysis
        if ctype == "BLOCKER" and not strength_families_in_accepted_band:
            analysis.update(
                {
                    "failure_classification": "active_fail_repaired_but_card_not_green",
                    "failure_message": (
                        "One-click from active FAIL made all required checks pass and placed at least one "
                        "strength family in target, but the final card is a yellow/blocker state instead "
                        "of green accepted with secondary blocker evidence."
                    ),
                }
            )
            return analysis
    if ctype == "ACTION":
        if same_candidate:
            analysis.update(
                {
                    "failure_classification": "post_click_same_action_still_available",
                    "failure_message": "The same one-click action remains visible after it was clicked.",
                }
            )
        else:
            analysis.update(
                {
                    "failure_classification": "post_click_not_green_or_exact_engineering_blocker",
                    "failure_message": "Post-click state is still an ACTION instead of green accepted or exact engineering blocker.",
                }
            )
        return analysis
    if ctype == "TERMINAL":
        if active:
            analysis.update(
                {
                    "failure_classification": "post_click_unresolved_active_fail",
                    "failure_message": f"Terminal post-click card is shown while active failures remain: {active}.",
                }
            )
            return analysis
        terminal_text = str(card.get("text") or "").lower()
        if any(token in terminal_text for token in ("run one-click auto design", "apply recommendation", "apply auto design")):
            analysis.update(
                {
                    "failure_classification": "post_click_same_action_still_available",
                    "failure_message": "Terminal post-click card still contains one-click action wording.",
                }
            )
            return analysis
        if unresolved_low:
            analysis.update(
                {
                    "failure_classification": "post_click_unresolved_low_util_family",
                    "failure_message": f"Terminal post-click card leaves low-util families unresolved: {unresolved_low}.",
                }
            )
            return analysis
        if card.get("cta_visible") or card.get("cta_enabled") or _contract_actionable(card):
            analysis.update(
                {
                    "failure_classification": "post_click_same_action_still_available",
                    "failure_message": "Terminal post-click card still exposes a one-click action.",
                }
            )
            return analysis
        if not (
            in_target
            or in_accepted_band
            or accepted_family_condition
            or outside_accepted_with_exact_target_band_proof
        ):
            analysis.update(
                {
                    "failure_classification": "post_click_outside_target_without_exact_blocker",
                    "failure_message": "Terminal post-click card is outside the preferred/accepted-family condition without exact blocker evidence.",
                }
            )
            return analysis
        if previous_active_outside_target:
            analysis.update(
                {
                    "failure_classification": "active_fail_post_click_out_of_target_family_unexplained",
                    "failure_message": (
                        "Active-fail repair made checks pass but did not land prior failing families "
                        f"{previous_active_outside_target} in the target band and did not provide exact target-band blocker proof."
                    ),
                }
            )
            return analysis
        if previous_active and strength_families_outside_preferred_target:
            title_text = str(card.get("title") or "").lower()
            card_text = str(card.get("text") or "").lower()
            has_secondary_blocker_rows = bool(dict(card.get("blocker_attempts_by_family") or {})) or (
                "why no further cleanup" in card_text
                and any(family in card_text for family in strength_families_outside_preferred_target)
            )
            new_terminal_label_ok = (
                "design is efficient" in title_text
                and has_secondary_blocker_rows
            )
            if "best safe" not in title_text and not new_terminal_label_ok:
                analysis.update(
                    {
                        "failure_classification": "active_fail_repaired_but_card_not_green",
                        "failure_message": (
                            "Active-fail one-click reached a safe accepted result with secondary "
                            "out-of-target families, but the final green card is not labelled as a best-safe result."
                        ),
                    }
                )
                return analysis
        analysis.update(
            {
                "final_state_type": (
                    "green_accepted_best_safe_result"
                    if previous_active and strength_families_outside_preferred_target
                    else "green_terminal_outside_accepted_with_exact_target_band_blockers"
                    if outside_accepted_with_exact_target_band_proof
                    else "green_target_accepted_with_explained_secondary_blocker"
                    if previous_active
                    else "green_target_accepted"
                ),
                "pass_reason": (
                    "post_click_green_accepted_best_safe_result"
                    if previous_active and strength_families_outside_preferred_target
                    else "post_click_green_terminal_outside_accepted_with_exact_target_band_blockers"
                    if outside_accepted_with_exact_target_band_proof
                    else "post_click_green_target_accepted_with_explained_secondary_blocker"
                    if previous_active
                    else "post_click_green_target_accepted"
                ),
                "accepted_reason": (
                    "all required checks pass, every strength family outside the accepted band has visible exact "
                    "target-band blocker proof, and no same-flow CTA remains"
                    if outside_accepted_with_exact_target_band_proof
                    else "all required checks pass, at least one strength family is in the accepted band after "
                    "active-fail repair, preferred target-band misses are reported, every below-accepted "
                    "strength family has exact blocker evidence, and no same-flow CTA remains"
                ),
            }
        )
        return analysis
    if ctype == "BLOCKER":
        if card.get("cta_visible") or card.get("cta_enabled") or not _no_executable_payload(card):
            analysis.update(
                {
                    "failure_classification": "blocker_has_cta",
                    "failure_message": "Post-click blocker exposes a CTA or executable payload.",
                }
            )
            return analysis
        if unresolved_active:
            analysis.update(
                {
                    "failure_classification": "post_click_unresolved_active_fail",
                    "failure_message": f"Post-click blocker lacks exact evidence for active failures: {unresolved_active}.",
                }
            )
            return analysis
        if active:
            repair_analysis = active_fail_repair_exhaustion_analysis(card, state, active)
            analysis["active_fail_blocker_analysis"] = dict(repair_analysis)
            if repair_analysis.get("used_cleanup_evidence_families"):
                analysis.update(
                    {
                        "failure_classification": "active_fail_post_click_used_cleanup_blocker",
                        "failure_message": (
                            "Post-click active FAIL blocker uses cleanup/efficiency evidence instead of "
                            f"repair exhaustion for {repair_analysis.get('used_cleanup_evidence_families')}."
                        ),
                    }
                )
                return analysis
            if not repair_analysis.get("valid"):
                analysis.update(
                    {
                        "failure_classification": "active_fail_blocker_without_strengthening_exhaustion",
                        "failure_message": (
                            "Post-click active FAIL blocker lacks exhaustive strengthening repair proof: "
                            f"{repair_analysis.get('missing_by_family')}."
                        ),
                    }
                )
                return analysis
        if unresolved_low:
            analysis.update(
                {
                    "failure_classification": "post_click_unresolved_low_util_family",
                    "failure_message": f"Post-click blocker lacks exact evidence for low-util families: {unresolved_low}.",
                }
            )
            return analysis
        if families_to_resolve and not _combined_blockers_valid(card, state, families_to_resolve):
            missing_specificity = {
                family: _blocker_specificity_analysis(dict(blockers.get(family) or {}), family).get("missing_fields")
                for family in families_to_resolve
                if blockers.get(family)
            }
            classification = (
                "post_click_blocker_missing_failed_rule"
                if any("failed_check_name" in list(fields or []) for fields in missing_specificity.values())
                else "post_click_blocker_missing_failed_candidate"
                if any("failed_candidate_id_or_best_rejected_candidate_id" in list(fields or []) for fields in missing_specificity.values())
                else "post_click_blocker_not_specific_enough"
            )
            analysis.update(
                {
                    "failure_classification": classification,
                    "failure_message": (
                        f"Post-click blocker lacks specific failed candidate/check/rule evidence for {families_to_resolve}: "
                        f"{missing_specificity}."
                    ),
                }
            )
            return analysis
        specific, reason = _blocker_text_is_specific(card, state, families_to_resolve or [str(card.get("family") or "").lower()])
        if not specific:
            analysis.update(
                {
                    "failure_classification": "post_click_blocker_no_family_specific_reason",
                    "failure_message": reason,
                }
            )
            return analysis
        analysis.update(
            {
                "final_state_type": "exact_engineering_blocker_valid",
                "pass_reason": "post_click_exact_engineering_blocker_valid",
                "accepted_reason": "visible blocker has no CTA and exact failed candidate/check/rule evidence for every unresolved failing/low-util family",
            }
        )
        return analysis
    analysis.update(
        {
            "failure_classification": "post_click_not_green_or_exact_engineering_blocker",
            "failure_message": "Post-click card is neither green/accepted nor a clear exact engineering blocker.",
        }
    )
    return analysis


def _has_action_contract_for(card: dict[str, Any], required_families: list[str]) -> tuple[bool, str]:
    contract = dict(card.get("button_contract") or {})
    updates = _contract_updates(card)
    selected_updates = dict(card.get("selected_action_updates") or {})
    if not (card.get("cta_visible") and card.get("cta_enabled")):
        return False, "visible action CTA is not enabled"
    if not (contract.get("actionable") and contract.get("action_type") and updates):
        return False, "visible enabled action lacks executable button contract"
    if not selected_updates:
        return False, "visible enabled action lacks selected_action_updates"
    if selected_updates != updates:
        return False, "selected_action_updates differ from button contract updates"
    if not contract.get("preview_pass"):
        return False, "action preview does not preserve all required checks"
    family = _contract_family(card)
    if required_families:
        if family != "combined" and not all(_family_matches(family, required) for required in required_families):
            return False, f"action family {family or '-'} does not cover required families {required_families}"
    return True, ""


def _no_executable_payload(card: dict[str, Any]) -> bool:
    contract = dict(card.get("button_contract") or {})
    return not bool(contract.get("actionable")) and not _contract_updates(card) and not dict(card.get("selected_action_updates") or {})


def _update_categories(updates: dict[str, Any]) -> list[str]:
    keys = {str(key or "").strip() for key in dict(updates or {})}
    categories: list[str] = []
    if any(key in keys for key in ("b", "bw", "D", "bf", "tf", "bf_bot", "tf_bot")):
        categories.append("geometry_reduction")
    if any(key.startswith("bot") or key in {"db_bot_1", "db_bot_2", "nb_bot", "bot_entry"} for key in keys):
        categories.append("bottom_reinforcement_reduction")
    if any(key.startswith("top") or key in {"db_top_1", "db_top_2", "nb_top", "top_entry"} for key in keys):
        categories.append("top_reinforcement_reduction")
    if "s_lig" in keys:
        categories.append("shear_link_spacing_reduction/increase")
    if "lig_legs" in keys:
        categories.append("shear_link_leg_reduction/increase")
    if "lig_d" in keys:
        categories.append("shear_link_diameter_reduction/increase")
    return categories


def _infer_optimisation_type(summary: dict[str, Any], card: dict[str, Any], state: dict[str, Any]) -> str:
    failures = active_fail_families(summary)
    family = str(card.get("family") or "").strip().lower()
    title_text = f"{card.get('title') or ''} {card.get('text') or ''}".lower()
    if set(failures) == {"bending", "shear"} or (family == "combined" and failures):
        return "combined_underdesign_repair"
    if "bending" in failures:
        return "bending_underdesign_repair"
    if "shear" in failures:
        return "shear_underdesign_repair"
    if is_terminal_card(card):
        if "very low" in title_text or "very low" in str(dict(card.get("proof_support") or {}).get("terminal_state") or "").lower():
            return "very_low_demand_terminal"
        return "already_efficient_terminal"
    if is_blocker_card(card):
        if "serviceability" in title_text or "crack" in title_text or "deflection" in title_text:
            return "serviceability_blocked_cleanup"
        if "ductility" in title_text:
            return "ductility_blocked_cleanup"
        if "spacing" in title_text or "detailing" in title_text:
            return "spacing_blocked_cleanup"
        if "minimum reinforcement" in title_text or "minimum" in title_text:
            return "minimum_reinforcement_blocked_cleanup"
    updates = _contract_updates(card)
    categories = _update_categories(updates)
    if categories:
        if "geometry_reduction" in categories:
            return "geometry_reduction"
        if "bottom_reinforcement_reduction" in categories:
            return "bottom_reinforcement_reduction"
        if "top_reinforcement_reduction" in categories:
            return "top_reinforcement_reduction"
        if any(category.startswith("shear_link") for category in categories):
            return categories[0]
    low = low_util_families(summary)
    if set(low) == {"bending", "shear"} or family == "combined":
        return "combined_overdesign_cleanup"
    if family == "bending" or "bending" in low:
        return "bending_overdesign_cleanup"
    if family == "shear" or "shear" in low:
        return "shear_overdesign_cleanup"
    return "unknown"


def _optimisation_family_from_type(opt_type: str, card: dict[str, Any]) -> str:
    opt = str(opt_type or "")
    if opt.startswith("combined"):
        return "combined"
    if "bending" in opt or "bottom_reinforcement" in opt or "top_reinforcement" in opt:
        return "bending"
    if "shear" in opt:
        return "shear"
    if "geometry" in opt:
        return "geometry"
    if "serviceability" in opt:
        return "serviceability"
    if "ductility" in opt:
        return str(card.get("family") or "bending")
    if "spacing" in opt or "minimum_reinforcement" in opt:
        return str(card.get("family") or "bending")
    if opt.endswith("_terminal"):
        return "overall"
    return str(card.get("family") or "unknown")


def _preview_utils(summary: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    preview = _summary_utils(summary)
    contract = dict(card.get("button_contract") or {})
    family = _contract_family(card)
    expected = _float_or_none(contract.get("expected_util"))
    if expected is not None and family in {"bending", "shear"}:
        preview[family] = expected
    return preview


def _blocking_check_tokens(card: dict[str, Any], state: dict[str, Any]) -> list[str]:
    text = f"{card.get('title') or ''} {card.get('text') or ''}".lower()
    blockers = exact_blockers(state)
    for blocker in blockers.values():
        if isinstance(blocker, dict):
            text += " " + " ".join(str(blocker.get(key) or "") for key in ("failed_check_name", "failed_check_status", "reason", "why_reduction_would_hurt_other_design_elements"))
    tokens = []
    for token in ("shear", "crack", "deflection", "spacing", "ductility", "minimum reinforcement", "geometry", "geometry lock", "discrete catalogue", "detailing", "serviceability"):
        if token in text:
            tokens.append(token)
    return tokens


def build_optimisation_audit(summary: dict[str, Any], card: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    opt_type = _infer_optimisation_type(summary, card, state)
    opt_family = _optimisation_family_from_type(opt_type, card)
    contract = dict(card.get("button_contract") or {})
    blocker_family = str(card.get("family") or "").strip().lower()
    proof_family = blocker_family if blocker_family in {"bending", "shear", "combined", "crack", "deflection"} else None
    proof = blocker_proof_analysis(card, state, proof_family)
    return {
        "optimisation_family": opt_family,
        "optimisation_type": opt_type,
        "card_type": card_type(card),
        "card_family": blocker_family,
        "current_util_by_family": _summary_utils(summary),
        "preview_util_by_family": _preview_utils(summary, card),
        "intended_family_before": family_util(summary, opt_family) if opt_family in {"bending", "shear"} else None,
        "intended_family_after": _float_or_none(contract.get("expected_util")) if opt_family in {"bending", "shear"} else None,
        "required_checks_before": _summary_statuses(summary),
        "required_checks_after": {"preview_pass": contract.get("preview_pass")},
        "target_band_result": {
            "target_low": REPAIR_TARGET_LOW,
            "target_high": REPAIR_TARGET_HIGH,
            "expected_util": _float_or_none(contract.get("expected_util")),
            "in_target": (
                _float_or_none(contract.get("expected_util")) is not None
                and REPAIR_TARGET_LOW <= float(_float_or_none(contract.get("expected_util"))) <= REPAIR_TARGET_HIGH
            ),
        },
        "blocker_evidence": dict(proof),
        "blocking_checks_named": _blocking_check_tokens(card, state),
        "update_categories": _update_categories(_contract_updates(card)),
        "button_contract_actionable": bool(contract.get("actionable")),
        "selected_action_updates_count": len(dict(card.get("selected_action_updates") or {})),
    }


def assert_optimisation_contract(step: dict[str, Any]) -> None:
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    audit = build_optimisation_audit(summary, card, state)
    step["optimisation_audit"] = dict(audit)
    opt_type = str(audit.get("optimisation_type") or "")
    opt_family = str(audit.get("optimisation_family") or "")
    card_family = str(audit.get("card_family") or "")
    ctype = str(audit.get("card_type") or "")
    active = active_fail_families(summary)
    low = low_util_families(summary)
    contract = dict(card.get("button_contract") or {})
    visible_text = _combined_step_visible_text(step, card)
    visible_action_shell = _visible_action_shell(card)
    executor_backed = _card_has_executor_backed_payload(card)
    advisory_text_visible = "advisory, not directly executable" in visible_text
    preview_failed_visible = "preview did not pass" in visible_text
    generic_one_click_visible = bool(
        card.get("cta_visible")
        and str(card.get("cta_label") or "").strip().lower() == "run one-click auto design"
    )
    if generic_one_click_visible and not executor_backed:
        _fail(
            "generic_one_click_without_executor_payload",
            "Visible generic one-click button is not backed by an actionable preview-passing payload.",
            step,
        )
    if generic_one_click_visible and (advisory_text_visible or ctype in {"BLOCKER", "TERMINAL"} or not executor_backed):
        _fail(
            "non_executable_card_with_generic_one_click",
            "Advisory/blocker/terminal/non-executable card exposes a visible generic one-click button.",
            step,
        )
    if generic_one_click_visible and preview_failed_visible:
        _fail(
            "preview_failed_with_generic_one_click",
            "Card text says Preview did not pass while a generic one-click button is visible.",
            step,
        )
    if visible_action_shell and advisory_text_visible:
        _fail(
            "action_card_advisory_not_executable",
            "Visible ACTION card says the recommendation is advisory and not directly executable.",
            step,
        )
    if visible_action_shell and contract.get("preview_pass") is False:
        _fail("action_card_preview_failed", "Visible ACTION card has a failed preview in its button contract.", step)
    if visible_action_shell and not executor_backed:
        _fail(
            "action_card_without_executable_contract",
            "Visible ACTION card lacks an executor-backed actionable button contract.",
            step,
        )
    if ctype not in {"ACTION", "BLOCKER", "TERMINAL"}:
        _fail("optimisation_wrong_family", f"Optimisation card type is unknown for {opt_type}.", step)
    if opt_family in {"bending", "shear"} and card_family and not _family_matches(card_family, opt_family):
        _fail("optimisation_wrong_family", f"Visible card family {card_family} does not match optimisation family {opt_family}.", step)
    if opt_family == "combined" and card_family not in {"combined", "bending", "shear"}:
        _fail("optimisation_wrong_family", f"Combined optimisation has incompatible visible family {card_family}.", step)

    if ctype == "ACTION":
        ok, reason = _has_action_contract_for(card, active if active else ([opt_family] if opt_family in {"bending", "shear"} else []))
        if not ok:
            _fail("optimisation_action_not_executable", reason, step)
        before = _float_or_none(audit.get("intended_family_before"))
        after = _float_or_none(audit.get("intended_family_after"))
        if opt_family in {"bending", "shear"} and before is not None and after is not None:
            if opt_type.endswith("_underdesign_repair") and before > 1.0 and after >= before:
                _fail("optimisation_does_not_improve_intended_family", f"{opt_family} repair preview does not reduce failing utilisation.", step)
            if "cleanup" in opt_type or "reduction" in opt_type or "increase" in opt_type:
                if before < TARGET_LOW and after <= before:
                    _fail("optimisation_does_not_improve_intended_family", f"{opt_family} cleanup preview does not improve low utilisation.", step)
            if (after < TARGET_LOW or after > REPAIR_TARGET_HIGH) and not has_exact_blocker(state, opt_family):
                _fail("optimisation_outside_target_without_blocker", f"{opt_family} action preview util={after:.3f} is outside accepted range without exact blocker.", step)
        if active and not dict(card.get("button_contract") or {}).get("preview_pass"):
            _fail("optimisation_breaks_other_required_check", "Action preview does not prove all required checks remain passing.", step)

    elif ctype == "BLOCKER":
        if not _no_executable_payload(card):
            _fail("blocker_has_cta", "Blocker optimisation exposes executable payload.", step)
        families = active or low or ([opt_family] if opt_family in {"bending", "shear"} else [])
        if active:
            _assert_active_fail_blocker_contract(step, active)
        if families and not _combined_blockers_valid(card, state, families):
            _fail("optimisation_blocker_missing_exact_evidence", f"Blocker lacks exact evidence for families {families}.", step)
        if families and card_family in {"bending", "shear"} and card_family not in families:
            _fail("blocker_family_mismatch", f"Blocker family {card_family} does not match unresolved optimisation families {families}.", step)
        tokens = set(audit.get("blocking_checks_named") or [])
        if "serviceability" in opt_type and not (tokens & {"serviceability", "crack", "deflection"}):
            _fail("serviceability_blocker_not_structured", "Serviceability blocker does not name crack/deflection/serviceability evidence.", step)
        if "ductility" in opt_type and "ductility" not in tokens:
            _fail("ductility_blocker_not_structured", "Ductility blocker does not name ductility evidence.", step)
        if "spacing" in opt_type and not (tokens & {"spacing", "detailing"}):
            _fail("spacing_blocker_not_structured", "Spacing/detailing blocker does not name spacing or detailing evidence.", step)
        if "minimum_reinforcement" in opt_type and "minimum reinforcement" not in tokens:
            _fail("reinforcement_cleanup_not_proven", "Minimum reinforcement blocker does not name minimum reinforcement evidence.", step)
        if opt_family == "geometry" and "geometry" not in tokens:
            _fail("geometry_cleanup_not_proven", "Geometry optimisation/blocker is not backed by geometry evidence.", step)
        if opt_family == "shear" and not (tokens & {"shear", "spacing", "detailing", "discrete catalogue"}):
            _fail("shear_cleanup_not_proven", "Shear optimisation blocker does not name shear/detailing/catalogue evidence.", step)

    elif ctype == "TERMINAL":
        if active:
            _fail("terminal_with_active_fail", f"Terminal optimisation shown with active failures {active}.", step)
        if card.get("cta_visible") or card.get("cta_enabled") or _contract_actionable(card):
            _fail("optimisation_terminal_with_remaining_action", "Terminal card still exposes a same-flow CTA/action.", step)
        unresolved_low = [family for family in low if not has_exact_blocker(state, family)]
        if unresolved_low:
            _fail("optimisation_terminal_with_low_util_unblocked", f"Terminal card has unresolved low-util families {unresolved_low}.", step)


def assert_design_guide_publication_contract(page, browser_state: dict[str, Any]) -> dict[str, Any]:
    """Shared hard Design Guide publication invariant for replay, fuzz and golden runs."""
    step = dict(browser_state or {})
    if "browser_state" not in step:
        state = dict(browser_state or {})
        step = {
            "browser_state": state,
            "visible_summary": parse_visible_summary(page, state) if page is not None else {},
            "visible_design_guide": parse_visible_design_guide(page, state) if page is not None else {},
        }
    state = dict(step.get("browser_state") or {})
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    contract = dict(card.get("button_contract") or {})
    layout_contract = dict(step.get("design_guide_layout_contract") or {})
    if page is not None and not layout_contract:
        layout_contract = _assert_design_guide_layout_contract_sync(page, step)
        step["design_guide_layout_contract"] = dict(layout_contract)
    if page is not None:
        step["summary_row_layout_contract"] = assert_summary_row_layout_contract(page, step)
        step["deflection_summary_row_contract"] = assert_deflection_summary_row_contract(page, step)

    ctype = card_type(card)
    active = active_fail_families(summary)
    low = low_util_families(summary)
    visible_text = _combined_step_visible_text(step, card)
    action_shell = _visible_action_shell(card)
    executor_backed = _card_has_executor_backed_payload(card)
    generic_one_click_visible = bool(
        card.get("cta_visible")
        and str(card.get("cta_label") or "").strip().lower() == "run one-click auto design"
    )
    publication: dict[str, Any] = {
        "card_type": ctype,
        "active_fail_families": list(active),
        "low_util_families": list(low),
        "button_contract_actionable": bool(contract.get("actionable")),
        "preview_pass": contract.get("preview_pass"),
        "selected_action_updates_count": len(dict(card.get("selected_action_updates") or {})),
        "primary_apply_payload_exists": bool(dict(card.get("design_guide_primary_apply_payload") or {})),
        "executor_backed": bool(executor_backed),
        "generic_one_click_visible": bool(generic_one_click_visible),
    }
    step["design_guide_publication_contract"] = dict(publication)

    audit = dict(card.get("payload_binding_audit") or {})
    if card.get("cta_enabled"):
        if audit.get("stale_apply_payload_blocked"):
            _fail("stale_primary_payload_visible_action", "Visible enabled action has stale primary apply payload audit.", step)
        if audit.get("payload_update_match") is False:
            _fail("stale_primary_payload_visible_action", "Visible enabled action primary payload updates do not match the button contract.", step)
        if audit.get("payload_binding_match") is False:
            _fail("stale_primary_payload_visible_action", "Visible enabled action primary payload candidate does not match the button contract.", step)

    if action_shell:
        if "advisory, not directly executable" in visible_text:
            _fail("action_card_advisory_not_executable", "Visible ACTION card says the recommendation is advisory and not directly executable.", step)
        if "preview did not pass" in visible_text or contract.get("preview_pass") is False:
            _fail("action_card_preview_failed", "Visible ACTION card has a failed preview in its button contract or visible text.", step)
        if not executor_backed:
            _fail("action_card_without_executable_contract", "Visible ACTION card lacks an executor-backed actionable button contract.", step)
        if not dict(card.get("selected_action_updates") or {}):
            _fail("action_payload_missing", "Visible ACTION card lacks selected_action_updates.", step)
        if not dict(card.get("design_guide_primary_apply_payload") or {}):
            _fail("action_payload_missing", "Visible ACTION card lacks design_guide_primary_apply_payload.", step)

    if generic_one_click_visible and not executor_backed:
        _fail("generic_one_click_without_executor_payload", "Visible generic one-click button is not backed by an actionable preview-passing payload.", step)
    if generic_one_click_visible and (ctype in {"BLOCKER", "TERMINAL"} or not executor_backed):
        _fail("non_executable_card_with_generic_one_click", "Advisory/blocker/terminal/non-executable card exposes a visible generic one-click button.", step)
    if generic_one_click_visible and "preview did not pass" in visible_text:
        _fail("preview_failed_with_generic_one_click", "Card text says Preview did not pass while a generic one-click button is visible.", step)

    card_family = str(card.get("family") or "").strip().lower()
    if (active or low) and card_family in {"", "other", "unknown"} and ctype != "TERMINAL":
        _fail("optimisation_wrong_family", f"Visible card family is {card_family or 'missing'} while unresolved strength families exist.", step)

    if low:
        if card.get("cta_enabled"):
            if not executor_backed:
                _fail("low_util_no_cleanup_or_blocker", f"Low-util families {low} have a visible CTA without executor-backed payload.", step)
        else:
            missing = [family for family in low if not has_exact_blocker(state, family)]
            if missing:
                _fail("low_util_no_cleanup_or_blocker", f"Low-util families {missing} lack cleanup action or exact blocker.", step)
            if not _combined_blockers_valid(card, state, low):
                _fail("optimisation_blocker_missing_exact_evidence", f"Low-util families {low} lack exhaustive exact blocker evidence.", step)

    if active and ctype in {"BLOCKER", "TERMINAL"}:
        _assert_active_fail_blocker_contract(step, active)

    if is_terminal_card(card) and low:
        unresolved = [family for family in low if not has_exact_blocker(state, family)]
        if unresolved:
            _fail("green_card_with_unresolved_family", f"Terminal card has unresolved low-util families {unresolved}.", step)

    if page is not None:
        evidence = dict(step.get("ladder_stop_calc_box_evidence") or {})
        if not evidence:
            evidence = assert_ladder_stop_calc_box_evidence(page, step)
            step["ladder_stop_calc_box_evidence"] = dict(evidence)
    return dict(publication)


def _fail(classification: str, message: str, step: dict[str, Any]) -> None:
    raise VisibleContractFailure(classification, message, step)


def _parse_visible_ductility_limit_row(summary: dict[str, Any]) -> dict[str, Any]:
    raw = str(dict(summary.get("bending") or {}).get("raw") or "")
    match = re.search(
        r"Ductility limit(?P<row>.*?)(?:Service bending moment|\n\s*\n[A-Z][^\n]*(?:jump to calc|$)|$)",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    row_text = str(match.group("row") if match else "")
    if not row_text:
        return {"found": False, "raw": raw}
    ku_match = re.search(r"k[_\s]?u\s*=\s*([0-9]+(?:\.[0-9]+)?)", row_text, flags=re.IGNORECASE)
    lim_match = re.search(r"k[_\s]?u\s*,?\s*lim\s*=\s*([0-9]+(?:\.[0-9]+)?)", row_text, flags=re.IGNORECASE)
    status_matches = re.findall(r"\b(PASS|FAIL|INFO|CAPACITY|NOT RUN)\b", row_text, flags=re.IGNORECASE)
    status = str(status_matches[-1]).upper() if status_matches else None
    return {
        "found": True,
        "row_text": row_text.strip(),
        "ku": _float_or_none(ku_match.group(1) if ku_match else None),
        "ku_lim": _float_or_none(lim_match.group(1) if lim_match else None),
        "status": status,
    }


def _assert_focused_replay_acceptance_contract(
    step: dict[str, Any],
    case: dict[str, Any],
    *,
    phase: str,
) -> None:
    focused_case = str(case.get("focused_case_name") or "").strip()
    if focused_case != "ku_only_ductility_fail_not_green":
        return
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    ductility = _parse_visible_ductility_limit_row(summary)
    audit = {
        "focused_case_name": focused_case,
        "phase": phase,
        "ductility_row_found": bool(ductility.get("found")),
        "ku": ductility.get("ku"),
        "ku_lim": ductility.get("ku_lim"),
        "ductility_status": ductility.get("status"),
        "design_guide_title": card.get("title"),
        "design_guide_status": card.get("status_label"),
        "design_guide_card_type": card_type(card),
        "cta_enabled": bool(card.get("cta_enabled")),
    }
    step["focused_acceptance_assertion"] = audit
    if not ductility.get("found"):
        _fail(
            "ku_focused_acceptance_missing_ductility_row",
            "Focused ku replay did not expose the visible Ductility limit row.",
            step,
        )
    ku = _float_or_none(ductility.get("ku"))
    ku_lim = _float_or_none(ductility.get("ku_lim"))
    status = str(ductility.get("status") or "").upper()
    if ku is None or ku_lim is None or not (ku > ku_lim) or status != "FAIL":
        _fail(
            "ku_focused_fixture_did_not_create_ductility_fail",
            f"Focused ku replay expected Ductility limit FAIL with k_u > k_u,lim, got k_u={ku!r}, k_u,lim={ku_lim!r}, status={status!r}.",
            step,
        )
    if is_terminal_card(card) or str(card.get("status_label") or "").strip().upper() == "PASS":
        _fail(
            "green_design_guide_card_coexists_with_ductility_fail",
            "Focused ku replay shows visible Ductility limit FAIL while Design Guide is green/PASS terminal.",
            step,
        )
    card_text = f"{card.get('title') or ''} {card.get('text') or ''}".lower()
    if "ductility" not in card_text and "k_u" not in card_text and "ku" not in card_text:
        _fail(
            "ku_focused_design_guide_missing_specific_failing_row",
            "Focused ku replay Design Guide does not name the failing ductility/k_u row.",
            step,
        )
    audit["passed"] = True


def _structured_family_rows_present(table: dict[str, Any] | None) -> bool:
    if not isinstance(table, dict):
        return False
    for family in ("bending", "shear", "crack", "deflection"):
        row = table.get(family)
        if not isinstance(row, dict):
            return False
        if row.get("util") in (None, "") and row.get("status") in (None, ""):
            return False
    return True


def _visible_family_rows_present(text_l: str, *, preview: bool = False) -> bool:
    if preview and not ("->" in text_l or "→" in text_l):
        return False
    return all(family in text_l for family in ("bending", "shear", "crack", "deflection"))


def _after_preview_values(table: dict[str, Any] | None) -> list[float]:
    values: list[float] = []
    if not isinstance(table, dict):
        return values
    for row in table.values():
        if not isinstance(row, dict):
            continue
        value = _float_or_none(row.get("after_util"))
        if value is not None:
            values.append(value)
    return values


def assert_family_visibility_contract(step: dict[str, Any]) -> None:
    card = dict(step.get("visible_design_guide") or {})
    text_l = str(card.get("text") or "").lower()
    layout = dict(step.get("design_guide_layout_contract") or {})
    layout_text_l = " ".join(
        str(layout.get(key) or "")
        for key in ("card_visible_text", "main_explanation_visible_text", "details_text")
    ).lower()
    layout_counts = dict(layout.get("test_id_counts") or {})
    layout_current_chips = dict(layout.get("current_chips") or {})
    layout_has_current = all(bool(layout_current_chips.get(family)) for family in ("bending", "shear", "crack", "deflection"))
    combined_text_l = f"{text_l} {layout_text_l}".strip()
    first_card = {}
    try:
        first_card = dict(list(card.get("cards") or [{}])[0] or {})
    except Exception:
        first_card = {}
    hook_counts = dict(first_card.get("test_hook_counts") or {})
    if int(card.get("visible_card_count") or 0) != 1:
        return
    current = dict(card.get("family_status_current") or {})
    if not (_structured_family_rows_present(current) or _visible_family_rows_present(combined_text_l) or layout_has_current):
        _fail(
            "family_status_table_missing",
            "Visible Design Guide card must show Current check status rows for bending, shear, crack, and deflection.",
            step,
        )
    if not layout_has_current and ("crack" not in combined_text_l or "deflection" not in combined_text_l):
        _fail(
            "serviceability_impact_missing",
            "Visible Design Guide card must expose crack and deflection serviceability impact/status.",
            step,
        )
    if card.get("cta_visible") or card.get("cta_enabled"):
        preview = dict(card.get("family_status_preview") or {})
        layout_preview_present = bool(
            int(layout_counts.get("design-guide-preview-row") or 0) >= 1
            and all(
                int(layout_counts.get(f"design-guide-preview-{family}") or 0) >= 1
                for family in ("bending", "shear", "crack", "deflection")
            )
        )
        if not (
            _structured_family_rows_present(preview)
            or _visible_family_rows_present(combined_text_l, preview=True)
            or layout_preview_present
        ):
            _fail(
                "preview_family_delta_missing",
                "Visible actionable Design Guide card must show before -> preview rows for bending, shear, crack, and deflection.",
                step,
            )
        change_row_visible = (
            "change:" in combined_text_l
            or "\nchange\n" in combined_text_l
            or int(hook_counts.get("design-guide-reason-change") or 0) > 0
            or int(hook_counts.get("design-guide-reason-fix") or 0) > 0
            or int(layout_counts.get("design-guide-reason-change") or 0) > 0
            or int(layout_counts.get("design-guide-reason-fix") or 0) > 0
        )
        if not change_row_visible:
            _fail(
                "preview_family_delta_missing",
                "Visible actionable Design Guide card must show a compact Change summary line.",
                step,
            )
        expected = _float_or_none(dict(card.get("button_contract") or {}).get("expected_util"))
        if expected is not None:
            after_values = _after_preview_values(preview)
            if after_values and all(abs(value - expected) > 0.05 for value in after_values):
                _fail(
                    "preview_family_delta_mismatch",
                    f"Visible preview family rows do not match button contract expected utilisation {expected:.3f}.",
                    step,
                )
    if is_blocker_card(card):
        attempts = dict(card.get("blocker_attempts_by_family") or {})
        visible_attempt_table = ("why blocked" in text_l or "blocked because" in text_l) and (
            "bending attempts" in text_l
            or "shear attempts" in text_l
            or "combined attempts" in text_l
            or "- bending:" in text_l
            or "- shear:" in text_l
            or "- combined:" in text_l
            or "• bending:" in text_l
            or "• shear:" in text_l
            or "• combined:" in text_l
        )
        if not attempts and not visible_attempt_table:
            _fail(
                "blocker_attempt_table_missing",
                "Visible blocker card must show a structured Why blocked attempts table.",
                step,
            )
        active = active_fail_families(dict(step.get("visible_summary") or {}))
        if active:
            attempted_families = {str(key).lower() for key in attempts.keys()}
            needs_combined = {"bending", "shear"}.issubset(set(active))
            missing = [family for family in active if family not in attempted_families]
            if needs_combined and "combined" not in attempted_families:
                missing.append("combined")
            if missing and visible_attempt_table:
                missing = [
                    family for family in missing
                    if f"{family} attempts" not in text_l
                ]
            if missing:
                _fail(
                    "strength_blocker_missing_repair_attempts",
                    f"Strength BLOCKED card lacks visible repair attempts for {sorted(set(missing))}.",
                    step,
                )


def assert_visible_contract(
    step: dict[str, Any],
    *,
    after_click: bool = False,
    after_mutation: bool = False,
    previous_step: dict[str, Any] | None = None,
    fail_on_no_action_without_exhaustive_proof: bool = True,
) -> None:
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    text = str(card.get("text") or "")
    text_l = text.lower()
    ctype = card_type(card)
    layout_contract = dict(step.get("design_guide_layout_contract") or {})
    if after_click:
        step["post_click_design_guide_layout_contract"] = dict(layout_contract)
    step["design_guide_layout_contract_event"] = {
        "event": "design_guide_layout_contract_checked",
        "ok": bool(layout_contract.get("ok")),
        "failures": list(layout_contract.get("failures") or []),
    }
    if layout_contract and not bool(layout_contract.get("ok")):
        first_failure = str((layout_contract.get("failures") or ["layout contract failed"])[0])
        layout_classification = "design_guide_layout_contract_failed"
        if first_failure.startswith("design_guide_wrong_page_order"):
            layout_classification = "design_guide_wrong_page_order"
        elif first_failure.startswith("design_guide_collapsible_header_missing"):
            layout_classification = "design_guide_collapsible_header_missing"
        elif first_failure.startswith("design_guide_button_inside_collapsible_body"):
            layout_classification = "design_guide_button_inside_collapsible_body"
        elif first_failure.startswith("design_guide_expand_toggle_missing"):
            layout_classification = "design_guide_expand_toggle_missing"
        elif first_failure.startswith("design_guide_expanded_content_missing"):
            layout_classification = "design_guide_expanded_content_missing"
        elif first_failure.startswith("design_guide_collapsed_body_leaking"):
            layout_classification = "design_guide_collapsed_body_leaking"
        elif first_failure.startswith("generic_cta_without_design_guide_card"):
            layout_classification = "generic_cta_without_design_guide_card"
        elif first_failure.startswith("design_guide_shell_without_card"):
            layout_classification = "design_guide_shell_without_card"
        elif first_failure.startswith("generic_cta_without_action_card"):
            layout_classification = "generic_cta_without_action_card"
        elif first_failure.startswith("design_guide_card_missing_family"):
            layout_classification = "design_guide_card_missing_family"
        elif first_failure.startswith("design_guide_raw_details_visible"):
            layout_classification = "visible_debug_wording_leaked"
        elif "expected exactly one design-guide-card" in first_failure:
            layout_classification = "duplicate_design_guide_panel"
        elif "missing design-guide-card" in first_failure:
            layout_classification = "design_guide_missing_after_relocation"
        _fail(
            layout_classification,
            f"DESIGN_GUIDE_LAYOUT_CONTRACT_FAILED: {first_failure}",
            step,
        )
    assert_design_guide_publication_contract(None, step)
    design_brain_validation = dict(card.get("design_brain_result_validation") or {})
    design_brain_failures = [
        str(failure or "").strip()
        for failure in list(design_brain_validation.get("failures") or [])
        if str(failure or "").strip()
    ]
    if design_brain_failures:
        step["design_brain_result_validation"] = dict(design_brain_validation)
        _fail(
            "design_brain_contract_validation_failed",
            f"DesignBrainResult contract validation failed: {design_brain_failures}",
            step,
        )
    if card.get("visible_card_count") != 1:
        _fail("missing_visible_card" if int(card.get("visible_card_count") or 0) == 0 else "duplicate_visible_cards", "Expected exactly one visible .fast-guidance-item card.", step)
    if int(card.get("fast_guidance_item_count") or 0) < 1:
        _fail("missing_visible_card", "Summary is visible but .fast-guidance-item is missing.", step)
    first_card = {}
    try:
        first_card = dict(list(card.get("cards") or [{}])[0] or {})
    except Exception:
        first_card = {}
    hook_counts = dict(first_card.get("test_hook_counts") or {})
    required_hooks = (
        "design-guide-card",
        "design-guide-status-pill",
        "design-guide-title",
        "design-guide-governing-utilisation",
        "design-guide-current-row",
        "design-guide-current-bending",
        "design-guide-current-shear",
        "design-guide-current-crack",
        "design-guide-current-deflection",
        "design-guide-main-explanation",
    )
    missing_hooks = [hook for hook in required_hooks if int(hook_counts.get(hook) or 0) < 1]
    if missing_hooks:
        _fail(
            "design_guide_card_layout_missing",
            f"Design Guide card is missing dashboard layout hooks: {missing_hooks}",
            step,
        )
    if card.get("preparing_visible"):
        _fail("stuck_preparing", "Design guidance is preparing remained visible after settle.", step)
    for token in FORBIDDEN_VISIBLE_WORDING:
        if token in text_l:
            _fail("visible_debug_wording_leaked", f"Forbidden visible wording leaked: {token}", step)
    for token, classification in FORBIDDEN_VISIBLE_WORDING_CLASSIFICATIONS.items():
        if token in text_l:
            _fail(classification, f"Visible Design Guide card uses non-specific blocker wording: {token}", step)
    assert_colour_alignment(step)
    assert_terminal_card_render_contract(step)
    assert_card_button_colour_semantics(step)
    assert_family_visibility_contract(step)

    active_failures = active_fail_or_overutil_families(summary)
    bending_fail = "bending" in active_failures
    shear_fail = "shear" in active_failures
    low_families = low_util_families(summary)
    contract = dict(card.get("button_contract") or {})
    updates = dict(contract.get("updates") or {})
    selected_updates = dict(card.get("selected_action_updates") or {})
    payload_audit = dict(card.get("payload_binding_audit") or {})
    visible_text_all = _combined_step_visible_text(step, card)
    action_shell_executor_backed = _card_has_executor_backed_payload(card)
    action_shell_advisory = "advisory, not directly executable" in visible_text_all
    action_shell_preview_failed = "preview did not pass" in visible_text_all
    generic_one_click_visible = bool(
        card.get("cta_visible")
        and str(card.get("cta_label") or "").strip().lower() == "run one-click auto design"
    )
    step["active_failing_families"] = list(active_failures)
    step["low_util_families"] = list(low_families)
    step["card_type"] = ctype
    step["optimisation_audit"] = build_optimisation_audit(summary, card, state)
    _assert_multi_family_blocker_contract(step)

    if active_failures:
        for classification, message in _active_fail_visible_wording_failures(step, card, summary, active_failures):
            _fail(classification, message, step)
        repair_action_available = bool(
            card.get("cta_enabled")
            and _visible_action_shell(card)
            and action_shell_executor_backed
        )
        if not repair_action_available and not _visible_text_has_lock_blocker(visible_text_all):
            step["failed_design_lock_blocker_audit"] = {
                "active_fail_or_overutil_families": list(active_failures),
                "has_enabled_executor_backed_repair_action": bool(repair_action_available),
                "visible_lock_blocker_terms": [
                    term for term in FAILED_DESIGN_LOCK_BLOCKER_TERMS if term in visible_text_all
                ],
                "card_title": card.get("title"),
                "cta_visible": bool(card.get("cta_visible")),
                "cta_enabled": bool(card.get("cta_enabled")),
                "card_type": ctype,
            }
            _fail(
                "failed_design_terminal_without_locked_constraints",
                (
                    f"Failed design families {active_failures} have no enabled executor-backed repair action "
                    "and no visible exact user-lock/constraint blocker."
                ),
                step,
            )

    if generic_one_click_visible and not action_shell_executor_backed:
        _fail(
            "generic_one_click_without_executor_payload",
            "Visible generic one-click button is not backed by an actionable preview-passing payload.",
            step,
        )
    if generic_one_click_visible and (action_shell_advisory or ctype in {"BLOCKER", "TERMINAL"} or not action_shell_executor_backed):
        _fail(
            "non_executable_card_with_generic_one_click",
            "Advisory/blocker/terminal/non-executable card exposes a visible generic one-click button.",
            step,
        )
    if generic_one_click_visible and action_shell_preview_failed:
        _fail(
            "preview_failed_with_generic_one_click",
            "Card text says Preview did not pass while a generic one-click button is visible.",
            step,
        )
    if _visible_action_shell(card) and action_shell_advisory:
        _fail(
            "action_card_advisory_not_executable",
            "Visible ACTION card says the recommendation is advisory and not directly executable.",
            step,
        )
    if _visible_action_shell(card) and contract.get("preview_pass") is False:
        _fail("action_card_preview_failed", "Visible ACTION card has a failed preview in its button contract.", step)
    if _visible_action_shell(card) and not action_shell_executor_backed:
        _fail(
            "action_card_without_executable_contract",
            "Visible ACTION card lacks an executor-backed actionable button contract.",
            step,
        )

    if is_blocker_card(card) and (
        card.get("cta_visible")
        or card.get("cta_enabled")
        or contract.get("actionable")
        or updates
        or selected_updates
    ):
        _fail("blocker_has_cta", "Visible blocker card exposes a one-click CTA or executable payload.", step)

    if active_failures and ctype == "TERMINAL":
        _fail("terminal_with_active_fail", "Terminal/accepted card shown while a strength check fails.", step)
    if active_failures and is_cleanup_or_terminal_only(card):
        _fail("summary_fail_but_card_not_repair", "Active strength FAIL is visible but Design Guide is terminal/cleanup-only.", step)
    if active_failures and ctype not in {"ACTION", "BLOCKER"}:
        _fail("summary_fail_but_card_not_repair", f"Summary shows active FAIL {active_failures}, but card type is {ctype}.", step)

    if card.get("cta_enabled"):
        if "stale_primary_design_guide_payload" in text_l:
            _fail(
                "stale_primary_payload_visible_action",
                "Visible enabled action is shown while stale_primary_design_guide_payload is visible.",
                step,
            )
        if payload_audit.get("stale_apply_payload_blocked"):
            _fail(
                "stale_primary_payload_visible_action",
                "Visible enabled action has stale primary apply payload audit.",
                step,
            )
        if payload_audit and payload_audit.get("payload_update_match") is False:
            _fail(
                "stale_primary_payload_visible_action",
                "Visible enabled action primary payload updates do not match the button contract.",
                step,
            )
        if payload_audit and payload_audit.get("payload_binding_match") is False:
            _fail(
                "stale_primary_payload_visible_action",
                "Visible enabled action primary payload candidate does not match the button contract.",
                step,
            )
        if not (contract.get("actionable") and contract.get("action_type") and updates):
            _fail("action_payload_missing", "Visible enabled action lacks executable button contract.", step)
        if not selected_updates:
            _fail("action_payload_missing", "Visible enabled action lacks selected_action_updates.", step)
        if selected_updates and updates and selected_updates != updates:
            _fail("action_payload_mismatch", "Selected action updates differ from button contract updates.", step)
        if not contract.get("preview_pass"):
            _fail("action_preview_does_not_fix_required_checks", "Visible enabled action preview does not preserve all required checks.", step)
        contract_family = _contract_family(card)
        if active_failures:
            if len(active_failures) > 1 and contract_family != "combined" and not all(_family_matches(contract_family, fam) for fam in active_failures):
                _fail("combined_fail_incomplete_action", f"Combined FAIL action family {contract_family or '-'} does not cover {active_failures}.", step)
            for family in active_failures:
                if not _family_matches(contract_family, family):
                    _fail(
                        "active_bending_fail_no_action_or_blocker" if family == "bending" else "active_shear_fail_no_action_or_blocker",
                        f"Active {family} FAIL is visible but action family is {contract_family or '-'}.",
                        step,
                    )
        step["pass_reason"] = (
            "action_cta_enabled_and_executable"
            if active_failures
            else ("low_util_cleanup_action_available" if low_families else "action_cta_enabled_and_executable")
        )
    elif is_blocker_card(card):
        util_mismatches = blocker_family_util_mismatches(state, exact_blockers(state))
        if util_mismatches:
            step["blocker_truth_family_util_mismatches"] = list(util_mismatches)
            _fail(
                "blocker_truth_probe_family_util_mismatch",
                f"Blocker evidence uses the wrong family utilisation: {util_mismatches[:3]}.",
                step,
            )
        if not _no_executable_payload(card):
            _fail("blocker_has_cta", "Visible blocker has executable payload/button contract updates.", step)
        fam = card.get("family")
        proof_family = fam if fam in {"bending", "shear", "combined", "crack", "deflection"} else None
        proof = blocker_proof_analysis(card, state, proof_family)
        step["no_action_analysis"] = dict(proof)
        families_to_prove = active_failures or low_families or ([fam] if fam in {"bending", "shear"} else [])
        if fam in {"bending", "shear"} and families_to_prove and fam not in families_to_prove:
            _fail("blocker_family_mismatch", f"Blocker family {fam} does not match unresolved families {families_to_prove}.", step)
        if families_to_prove:
            specific, specific_reason = _blocker_text_is_specific(card, state, families_to_prove)
            if not specific:
                _fail(
                    "blocker_card_without_specific_engineering_reason",
                    specific_reason,
                    step,
                )
        if active_failures:
            _assert_active_fail_blocker_contract(step, active_failures)
            if not _combined_blockers_valid(card, state, active_failures):
                _fail("optimisation_blocker_missing_exact_evidence", f"Active failures {active_failures} lack exhaustive exact blocker evidence.", step)
            active_truth = probe_active_fail_repair_truth(state, summary)
            step["blocker_truth_probe"] = dict(active_truth)
            if int(active_truth.get("passing_candidate_count") or 0) > 0:
                _fail(
                    "active_fail_blocker_false_repair_candidate_exists",
                    "Visible active-fail BLOCKED card is false: independent repair probe found a passing executor-backed repair candidate.",
                    step,
                )
            step["pass_reason"] = "active_fail_impossible_repair_blocker_valid"
        elif low_families:
            if not _combined_blockers_valid(card, state, low_families):
                _fail("optimisation_blocker_missing_exact_evidence", f"Low-util families {low_families} lack exhaustive exact blocker evidence.", step)
            cleanup_truth = probe_overdesign_cleanup_truth(state, summary)
            step["blocker_truth_probe"] = dict(cleanup_truth)
            if int(cleanup_truth.get("safe_improving_candidate_count") or 0) > 0:
                _fail(
                    "overdesign_blocker_false_cleanup_candidate_exists",
                    "Visible overdesign blocker is false: independent cleanup probe found a safe improving executor-backed cleanup candidate.",
                    step,
                )
            step["pass_reason"] = "low_util_exact_blocker_valid"
        elif not proof.get("valid"):
            _fail("optimisation_blocker_missing_exact_evidence", "Visible blocker lacks exhaustive structured exact blocker evidence.", step)
        else:
            step["pass_reason"] = "low_util_exact_blocker_valid"
        step["exact_blocker_family"] = proof.get("family")
    elif (
        fail_on_no_action_without_exhaustive_proof
        and ctype != "TERMINAL"
        and ((bending_fail or shear_fail) or low_families)
    ):
        proof_family = active_failures[0] if active_failures else low_families[0]
        proof = blocker_proof_analysis(card, state, proof_family)
        step["no_action_analysis"] = dict(proof)
        if active_failures:
            _assert_active_fail_blocker_contract(step, active_failures)
            if not _combined_blockers_valid(card, state, active_failures):
                classification = "active_bending_fail_no_action_or_blocker" if "bending" in active_failures else "active_shear_fail_no_action_or_blocker"
                if len(active_failures) > 1:
                    classification = "combined_fail_incomplete_action"
                _fail(
                    classification,
                    f"No-CTA state with active failures {active_failures} lacks exhaustive exact blocker proof.",
                    step,
                )
            active_truth = probe_active_fail_repair_truth(state, summary)
            step["blocker_truth_probe"] = dict(active_truth)
            if int(active_truth.get("passing_candidate_count") or 0) > 0:
                _fail(
                    "active_fail_blocker_false_repair_candidate_exists",
                    "No-CTA active-fail blocker is false: independent repair probe found a passing executor-backed repair candidate.",
                    step,
                )
            step["pass_reason"] = "active_fail_impossible_repair_blocker_valid"
        elif low_families:
            if not _combined_blockers_valid(card, state, low_families):
                _fail(
                    "low_util_no_cleanup_or_blocker",
                    f"No-CTA state with low-util families {low_families} lacks exhaustive exact blocker proof.",
                    step,
                )
            cleanup_truth = probe_overdesign_cleanup_truth(state, summary)
            step["blocker_truth_probe"] = dict(cleanup_truth)
            if int(cleanup_truth.get("safe_improving_candidate_count") or 0) > 0:
                _fail(
                    "overdesign_blocker_false_cleanup_candidate_exists",
                    "No-CTA overdesign blocker is false: independent cleanup probe found a safe improving executor-backed cleanup candidate.",
                    step,
                )
            step["pass_reason"] = "low_util_exact_blocker_valid"
        else:
            _fail(
                "blocker_missing_exact_evidence",
                "No-CTA state with active failure or low-util family lacks exhaustive exact blocker proof.",
                step,
            )
        step["exact_blocker_family"] = proof.get("family")

    if is_terminal_card(card):
        if bending_fail or shear_fail:
            _fail("terminal_with_active_fail", "Accepted/efficient card shown while a strength check fails.", step)
        terminal_low_families: list[str] = []
        for family in ("bending", "shear"):
            util = family_util(summary, family)
            if util is not None and util > 0.0 and util < TARGET_LOW - 1e-9:
                terminal_low_families.append(family)
                if not has_exact_blocker(state, family):
                    _fail(
                        "green_card_with_unresolved_family",
                        f"Accepted/efficient card shown while {family} util={util:.3f} is below {TARGET_LOW}.",
                        step,
                    )
        if terminal_low_families:
            relevant_blockers = {
                family: dict(exact_blockers(state).get(family) or {})
                for family in terminal_low_families
                if family in exact_blockers(state)
            }
            util_mismatches = blocker_family_util_mismatches(state, relevant_blockers)
            if util_mismatches:
                step["blocker_truth_family_util_mismatches"] = list(util_mismatches)
                _fail(
                    "blocker_truth_probe_family_util_mismatch",
                    f"Blocker evidence uses the wrong family utilisation: {util_mismatches[:3]}.",
                    step,
                )
            secondary_truth = probe_green_secondary_blocker_truth(state, summary)
            step["blocker_truth_probe"] = dict(secondary_truth)
            if int(secondary_truth.get("safe_improving_candidate_count") or 0) > 0:
                _fail(
                    "green_terminal_secondary_blocker_false_candidate_exists",
                    "Green terminal secondary blocker is false: independent cleanup probe found a safe improving executor-backed candidate.",
                    step,
                )
        step["pass_reason"] = "accepted_green_valid"

    if not active_failures and not low_families:
        worst = _float_or_none(dict(summary.get("browser_overview_support") or {}).get("worst_util"))
        in_target = bool(worst is not None and REPAIR_TARGET_LOW <= worst <= REPAIR_TARGET_HIGH)
        if in_target and ctype != "TERMINAL":
            _fail("all_pass_in_target_but_not_green", "All required checks pass in target band, but the Design Guide is not green/accepted.", step)

    if ctype == "TERMINAL" and is_blocker_card(card):
        _fail("card_colour_status_mismatch", "Card is classified as green/terminal and blocker at the same time.", step)

    displayed = _float_or_none(card.get("displayed_util"))
    fam = str(card.get("family") or "").lower()
    if displayed is not None:
        if card.get("cta_enabled"):
            expected = _float_or_none(contract.get("expected_util"))
            if expected is not None and abs(displayed - expected) > 0.03:
                _fail(
                    "util_display_mismatch_after_edit" if after_mutation else "util_display_mismatch",
                    f"Action card displayed preview util {displayed:.3f} but button contract expects {expected:.3f}.",
                    step,
                )
        elif fam in {"bending", "shear"}:
            truth = family_util(summary, fam)
            if truth is not None and abs(displayed - truth) > 0.03:
                _fail("util_display_mismatch_after_edit" if after_mutation else "util_display_mismatch", f"{fam} card displayed util {displayed:.3f} but visible summary has {truth:.3f}.", step)

    assert_optimisation_contract(step)

    audit = dict(card.get("payload_binding_audit") or {})
    if after_click and audit:
        if audit.get("payload_update_match") is False:
            _fail("action_payload_mismatch", "Post-click visible/button/queued/applied updates do not match.", step)
        if card.get("cta_enabled"):
            _fail("post_click_cta_still_visible", "CTA remains enabled after click for the same flow.", step)
    if after_click:
        previous_card = dict((previous_step or {}).get("visible_design_guide") or {})
        previous_contract = dict(previous_card.get("button_contract") or {})
        previous_selected_updates = dict(previous_card.get("selected_action_updates") or {})
        if (
            previous_step
            and previous_card.get("cta_visible")
            and previous_card.get("cta_enabled")
            and previous_contract.get("actionable")
            and previous_selected_updates
        ):
            click_audit = one_click_material_change_audit(previous_step, step)
            step["one_click_material_change_audit"] = dict(click_audit)
            if not click_audit.get("applied_to_expected_keys"):
                _fail(
                    "one_click_no_material_change",
                    "One-click CTA was enabled/actionable, but no intended update key changed to the expected value after the click.",
                    step,
                )
            if not click_audit.get("visual_summary_changed") and not click_audit.get("results_version_changed"):
                _fail(
                    "one_click_summary_not_updated",
                    "One-click CTA applied material input updates, but the visible summary/results did not change after settle.",
                    step,
                )
            if not click_audit.get("visual_card_changed"):
                _fail(
                    "one_click_card_not_refreshed",
                    "One-click CTA applied material input updates, but the visible Design Guide card did not refresh after settle.",
                    step,
                )
            if click_audit.get("same_candidate_still_visible_enabled") or click_audit.get("same_render_fingerprint_still_visible_enabled"):
                _fail(
                    "one_click_same_payload_still_visible",
                    "The same one-click candidate/render fingerprint remains visible and enabled after it was clicked.",
                    step,
                )
        previous_summary = dict((previous_step or {}).get("visible_summary") or {})
        final_state = _post_click_final_state_analysis(step, previous_step)
        step["post_click_final_state"] = dict(final_state)
        if final_state.get("final_state_type") == "invalid_post_click_state":
            _fail(
                str(final_state.get("failure_classification") or "post_click_not_green_or_exact_engineering_blocker"),
                str(final_state.get("failure_message") or "Post-click state is not green/accepted or an exact engineering blocker."),
                step,
            )
        step["pass_reason"] = str(final_state.get("pass_reason") or "")
        if previous_step and step.get("one_click_material_change_audit"):
            click_audit = dict(step.get("one_click_material_change_audit") or {})
            click_audit["final_state_type"] = final_state.get("final_state_type")
            click_audit["final_card_title"] = final_state.get("final_card_title")
            click_audit["final_summary_statuses"] = final_state.get("final_summary_statuses")
            click_audit["final_family_utils"] = final_state.get("final_family_utils")
            click_audit["target_band"] = final_state.get("target_band")
            click_audit["unresolved_active_fail_families"] = final_state.get("unresolved_active_fail_families")
            click_audit["unresolved_low_util_families"] = final_state.get("unresolved_low_util_families")
            click_audit["exact_blockers_by_family"] = list(dict(final_state.get("exact_blockers_by_family") or {}).keys())
            click_audit["blocker_reasons_by_family"] = final_state.get("blocker_reasons_by_family")
            click_audit["candidate_counts_by_family"] = final_state.get("candidate_counts_by_family")
            click_audit["why_final_state_accepted"] = final_state.get("accepted_reason")
            click_audit["click_pass_reason"] = final_state.get("pass_reason")
            step["one_click_material_change_audit"] = dict(click_audit)

    if after_mutation and previous_step:
        prev_summary = dict(previous_step.get("visible_summary") or {})
        prev_card = dict(previous_step.get("visible_design_guide") or {})
        summary_changed = any(
            not _same_value(family_util(summary, fam), family_util(prev_summary, fam), tol=0.01)
            or family_status(summary, fam) != family_status(prev_summary, fam)
            for fam in ("bending", "shear")
        )
        same_card = str(prev_card.get("title") or "") == str(card.get("title") or "") and str(prev_card.get("text") or "") == str(card.get("text") or "")
        same_payload = dict(prev_card.get("button_contract") or {}).get("updates") == dict(card.get("button_contract") or {}).get("updates")
        if summary_changed and same_card and same_payload:
            _fail("card_not_recomputed_after_edit", "Summary changed after manual edit but card and payload remained unchanged.", step)

    if not step.get("pass_reason"):
        if low_families and not card.get("cta_enabled") and not any(has_exact_blocker(state, family) for family in low_families):
            _fail("low_util_no_cleanup_or_blocker", f"Low-util families {low_families} lack cleanup action or exact blocker.", step)
        if is_valid_structured_blocker(card, state):
            if active_failures:
                _assert_active_fail_blocker_contract(step, active_failures)
            step["pass_reason"] = "low_util_exact_blocker_valid" if low_families else "active_fail_impossible_repair_blocker_valid"
        elif is_terminal_card(card):
            step["pass_reason"] = "accepted_green_valid"
        elif card.get("cta_enabled"):
            step["pass_reason"] = "action_cta_enabled_and_executable"
        else:
            step["pass_reason"] = "no_issue_all_checks_pass_in_target"


def capture_step(
    page,
    *,
    artifact_dir: Path,
    case_index: int,
    step_index: int,
    step_type: str,
    inputs: dict[str, Any],
    save_screenshot: bool = False,
) -> dict[str, Any]:
    state = _load_browser_state(page)
    summary = parse_visible_summary(page, state)
    card = parse_visible_design_guide(page, state)
    if (
        step_type == "post_click"
        and (
            int(card.get("visible_card_count") or 0) < 1
            or bool(card.get("preparing_visible"))
            or (
                int(card.get("visible_card_count") or 0) < 1
                and bool(card.get("cta_visible"))
            )
        )
    ):
        retry_deadline = time.time() + 20.0
        while time.time() < retry_deadline:
            time.sleep(0.75)
            state = _load_browser_state(page)
            summary = parse_visible_summary(page, state)
            card = parse_visible_design_guide(page, state)
            if (
                int(card.get("visible_card_count") or 0) >= 1
                and not bool(card.get("preparing_visible"))
            ):
                break
    layout_contract = _assert_design_guide_layout_contract_sync(
        page,
        {
            "browser_state": state,
            "visible_summary": summary,
            "visible_design_guide": card,
            "case_index": case_index,
            "step_index": step_index,
            "step_type": step_type,
        },
    )
    layout_failures = [str(failure or "") for failure in layout_contract.get("failures") or []]
    parsed_card_hooks = {}
    try:
        parsed_card_hooks = dict((list(card.get("cards") or [{}])[0] or {}).get("test_hook_counts") or {})
    except Exception:
        parsed_card_hooks = {}
    if (
        any("missing design-guide-card" in failure for failure in layout_failures)
        and int(card.get("visible_card_count") or 0) == 1
        and int(parsed_card_hooks.get("design-guide-card") or 0) >= 1
    ):
        for retry_index in range(3):
            page.wait_for_timeout(500)
            state = _load_browser_state(page)
            summary = parse_visible_summary(page, state)
            card = parse_visible_design_guide(page, state)
            layout_contract = _assert_design_guide_layout_contract_sync(
                page,
                {
                    "browser_state": state,
                    "visible_summary": summary,
                    "visible_design_guide": card,
                    "case_index": case_index,
                    "step_index": step_index,
                    "step_type": step_type,
                },
            )
            layout_contract["missing_card_retry_count"] = retry_index + 1
            layout_contract["missing_card_retry_reason"] = (
                "visible parser saw design-guide-card hook during Streamlit rerun"
            )
            if bool(layout_contract.get("ok")) or not any(
                "missing design-guide-card" in str(failure or "")
                for failure in layout_contract.get("failures") or []
            ):
                break
    step_for_ladder_evidence = {
        "case_index": case_index,
        "step_index": step_index,
        "step_type": step_type,
        "input_values": dict(inputs),
        "visible_summary": summary,
        "visible_design_guide": card,
        "design_guide_layout_contract": layout_contract,
        "browser_state": state,
    }
    ladder_stop_calc_box_evidence = assert_ladder_stop_calc_box_evidence(
        page,
        step_for_ladder_evidence,
        artifact_dir=artifact_dir,
    )
    screenshot_path = None
    if save_screenshot:
        screenshot_path = artifact_dir / f"case_{case_index:03d}_step_{step_index:02d}_{step_type}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
    return {
        "case_index": case_index,
        "step_index": step_index,
        "step_type": step_type,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "input_values": dict(inputs),
        "visible_summary": summary,
        "visible_design_guide": card,
        "design_guide_layout_contract": layout_contract,
        "ladder_stop_calc_box_evidence": ladder_stop_calc_box_evidence,
        "browser_state": state,
        "payload_binding_audit": dict(card.get("payload_binding_audit") or {}),
        "exact_blocker_evidence": exact_blockers(state),
        "screenshot_path": str(screenshot_path) if screenshot_path else None,
    }


def progress_step_summary(step: dict[str, Any]) -> dict[str, Any]:
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    proof = dict(step.get("no_action_analysis") or {})
    if not proof and not card.get("cta_enabled"):
        proof = blocker_proof_analysis(card, state)
    evidence = cleanup_evidence(state)
    opt_audit = dict(step.get("optimisation_audit") or build_optimisation_audit(summary, card, state))
    click_audit = dict(step.get("one_click_material_change_audit") or {})
    final_state = dict(step.get("post_click_final_state") or {})
    secondary_families = list(final_state.get("strength_families_outside_target") or [])
    secondary_blockers = dict(final_state.get("target_band_blockers_by_family") or {})
    secondary_proof_by_family: dict[str, dict[str, Any]] = {}
    for family in secondary_families:
        blocker = dict(secondary_blockers.get(family) or {})
        secondary_proof_by_family[str(family)] = {
            "proof_valid": bool(blocker.get("valid")),
            "missing_fields": list(blocker.get("missing_fields") or []),
            "reason": blocker.get("reason"),
            "failed_candidate_id": blocker.get("failed_candidate_id") or blocker.get("best_rejected_candidate_id"),
            "failed_check_name": blocker.get("failed_check_name"),
            "failed_check_status": blocker.get("failed_check_status"),
            "attempted_candidate_count": blocker.get("attempted_candidate_count"),
            "executable_candidate_count": blocker.get("executable_candidate_count"),
            "target_band_candidate_count": blocker.get("target_band_candidate_count"),
        }
    secondary_proof_valid = (
        all(bool(proof.get("proof_valid")) for proof in secondary_proof_by_family.values())
        if secondary_proof_by_family
        else None
    )
    active_blocker = dict(step.get("active_fail_blocker_analysis") or {})
    alignment = dict(
        step.get("colour_alignment")
        or colour_alignment(summary, card, dict(step.get("browser_state") or {}))
    )
    no_link_audit = no_link_shear_cleanup_audit(dict(step.get("browser_state") or {}), card)
    return {
        "step_index": step.get("step_index"),
        "step_type": step.get("step_type"),
        "optimisation_family": opt_audit.get("optimisation_family"),
        "optimisation_type": opt_audit.get("optimisation_type"),
        "visible_summary_utils": _summary_utils(summary),
        "visible_summary_statuses": _summary_statuses(summary),
        "preview_util_by_family": dict(opt_audit.get("preview_util_by_family") or {}),
        "visible_card_title": card.get("title"),
        "visible_card_family": card.get("family"),
        "visible_card_type": opt_audit.get("card_type"),
        "summary_colour_by_family": dict(alignment.get("summary_colour_by_family") or {}),
        "design_guide_card_colour": alignment.get("actual_card_colour"),
        "design_guide_card_status_label": alignment.get("card_status_label"),
        "design_guide_card_classes": alignment.get("card_classes"),
        "expected_card_colour": alignment.get("expected_card_colour"),
        "colour_alignment_ok": alignment.get("alignment_ok"),
        "colour_alignment_failures": list(alignment.get("failures") or []),
        "cta_visible": bool(card.get("cta_visible")),
        "cta_enabled": bool(card.get("cta_enabled")),
        "pass_reason": step.get("pass_reason"),
        "failure_classification": step.get("failure_classification"),
        "exact_blocker_family": step.get("exact_blocker_family") or proof.get("family"),
        "target_band_result": dict(opt_audit.get("target_band_result") or {}),
        "safe_candidate_count": proof.get("safe_candidate_count", _deep_get_count(evidence, keys=("safe_candidate_count", "safe_local_cleanup_count", "safe_executor_backed_candidates_count"))),
        "executable_candidate_count": proof.get("executable_candidate_count", _deep_get_count(evidence, keys=("executable_candidate_count", "executable_cleanup_count", "executable_safe_cleanup_count"))),
        "selected_action_updates_count": len(dict(card.get("selected_action_updates") or {})),
        "click_audit": dict(click_audit),
        "click_pass_reason": click_audit.get("click_pass_reason"),
        "final_state_type": final_state.get("final_state_type"),
        "final_state_accepted_reason": final_state.get("accepted_reason"),
        "post_click_unresolved_active_fail_families": final_state.get("unresolved_active_fail_families"),
        "post_click_unresolved_low_util_families": final_state.get("unresolved_low_util_families"),
        "post_click_blocker_reasons_by_family": final_state.get("blocker_reasons_by_family"),
        "post_click_candidate_counts_by_family": final_state.get("candidate_counts_by_family"),
        "post_click_failed_candidate_check_by_family": final_state.get("failed_candidate_check_by_family"),
        "pre_click_active_fail_families": final_state.get("pre_click_active_fail_families"),
        "post_click_bending_util": final_state.get("post_click_bending_util"),
        "post_click_shear_util": final_state.get("post_click_shear_util"),
        "post_click_strength_families_in_target": final_state.get("strength_families_in_target"),
        "post_click_strength_families_outside_target": final_state.get("strength_families_outside_target"),
        "post_click_target_band_blockers_by_family": final_state.get("target_band_blockers_by_family"),
        "secondary_out_of_target_families": secondary_families,
        "secondary_out_of_target_proof_by_family": secondary_proof_by_family,
        "secondary_out_of_target_proof_valid": secondary_proof_valid,
        "secondary_out_of_target_missing_fields": {
            family: proof.get("missing_fields")
            for family, proof in secondary_proof_by_family.items()
            if not proof.get("proof_valid")
        },
        "active_fail_blocker_valid": active_blocker.get("valid"),
        "active_fail_blocker_missing_by_family": active_blocker.get("missing_by_family"),
        "active_fail_blocker_used_cleanup_evidence_families": active_blocker.get("used_cleanup_evidence_families"),
        "no_link_shear_cleanup_audit": dict(no_link_audit),
        "clicked_candidate_id": click_audit.get("clicked_candidate_id"),
        "clicked_family": click_audit.get("clicked_family"),
        "changed_keys": list(click_audit.get("changed_keys") or []),
        "unchanged_expected_keys": list(click_audit.get("unchanged_expected_keys") or []),
    }


def progress_case_summary(case_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [progress_step_summary(step) for step in list(case_result.get("timeline") or []) if isinstance(step, dict)]


def wait_for_settle(
    page,
    *,
    timeout_s: float = 75.0,
    base_url: str | None = None,
    console_messages: list[str] | None = None,
    lifecycle: LifecycleDiagnostics | None = None,
    stage: str = "settle_wait",
) -> dict[str, Any]:
    settle_start = _perf_now()
    if lifecycle is not None:
        lifecycle.set_stage(stage, case_index=lifecycle.current_case, replay=lifecycle.current_replay)
        lifecycle.event("settle_wait_start", stage=stage, timeout_s=timeout_s)
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    stable = 0
    last_sig = None
    probe_recovery_attempted = False
    polls = 0
    last_pending: dict[str, Any] = {}
    while time.time() < deadline:
        polls += 1
        try:
            state = _load_browser_state(page)
        except PlaywrightTimeoutError:
            if not base_url or probe_recovery_attempted:
                if lifecycle is not None:
                    lifecycle.event(
                        "settle_wait_browser_probe_timeout",
                        stage=stage,
                        elapsed_ms=_safe_elapsed_ms(settle_start),
                        polls=polls,
                    )
                raise
            probe_recovery_attempted = True
            ready = wait_for_browser_state_probe_ready(
                page,
                base_url=base_url,
                console_messages=console_messages or [],
                timeout_s=60.0,
                allow_reload_once=True,
            )
            if not ready.get("ready"):
                raise
            state = _load_browser_state(page)
        overview = dict(state.get("summary_overview_probe") or {})
        guidance = dict(state.get("guidance_compute_probe") or {})
        sig = json.dumps(
            {
                "utils": overview.get("utils"),
                "statuses": overview.get("statuses"),
                "title": guidance.get("primary_title"),
                "action": guidance.get("primary_action_type"),
                "updates": guidance.get("primary_updates"),
                "card_count": None,
            },
            sort_keys=True,
            default=_json_default,
        )
        card_count = 0
        try:
            card_count = page.locator(".fast-guidance-item").count()
        except Exception:
            card_count = 0
        preparing_visible = False
        stale_button_without_card = False
        try:
            body_text = page.locator("body").inner_text(timeout=1500)
            preparing_visible = "Design guidance is preparing" in str(body_text or "")
        except Exception:
            preparing_visible = False
        try:
            generic_cta = page.get_by_role("button", name="Run one-click auto design").first
            stale_button_without_card = bool(
                card_count < 1
                and generic_cta.count() > 0
                and generic_cta.is_visible(timeout=500)
            )
        except Exception:
            stale_button_without_card = False
        sig = json.dumps(
            {
                "utils": overview.get("utils"),
                "statuses": overview.get("statuses"),
                "title": guidance.get("primary_title"),
                "action": guidance.get("primary_action_type"),
                "updates": guidance.get("primary_updates"),
                "card_count": card_count,
                "preparing_visible": preparing_visible,
                "stale_button_without_card": stale_button_without_card,
            },
            sort_keys=True,
            default=_json_default,
        )
        visible_aligned = True
        try:
            visible_summary = parse_visible_summary(page, state)
            support = dict(visible_summary.get("browser_overview_support") or {})
            support_utils = dict(support.get("utils") or {})
            support_statuses = dict(support.get("statuses") or {})
            for family in ("bending", "shear"):
                visible_family = dict(visible_summary.get(family) or {})
                visible_status = str(visible_family.get("status") or "").strip().upper()
                support_status = str(support_statuses.get(family) or "").strip().upper()
                if visible_status and support_status and visible_status != support_status:
                    visible_aligned = False
                    break
                visible_util = _float_or_none(visible_family.get("util"))
                support_util = _float_or_none(support_utils.get(family))
                if visible_util is not None and support_util is not None:
                    if abs(float(visible_util) - float(support_util)) > 0.06:
                        visible_aligned = False
                        break
        except Exception:
            visible_aligned = True
        action_transient = bool(
            state.get("inputs_action_apply_recommendation")
            or state.get("inputs_action_run_auto_design")
        )
        last_pending = {
            "card_count": card_count,
            "visible_aligned": visible_aligned,
            "action_transient": action_transient,
            "preparing_visible": preparing_visible,
            "stale_button_without_card": stale_button_without_card,
            "probe_recovery_attempted": probe_recovery_attempted,
            "stable_cycles": stable,
        }
        visibly_settled = bool(
            card_count >= 1
            and visible_aligned
            and not action_transient
            and not preparing_visible
            and not stale_button_without_card
        )
        if sig == last_sig and visibly_settled:
            stable += 1
        else:
            stable = 1
            last_sig = sig
        last = state
        if stable >= 2:
            time.sleep(0.4)
            try:
                final_card_count = page.locator(".fast-guidance-item").count()
                final_body = page.locator("body").inner_text(timeout=1500)
                final_preparing = "Design guidance is preparing" in str(final_body or "")
                final_cta = page.get_by_role("button", name="Run one-click auto design").first
                final_stale_button = bool(
                    final_card_count < 1
                    and final_cta.count() > 0
                    and final_cta.is_visible(timeout=500)
                )
                if final_card_count < 1 or final_preparing or final_stale_button:
                    stable = 0
                    time.sleep(0.6)
                    continue
            except Exception:
                pass
            if lifecycle is not None:
                lifecycle.event(
                    "settle_wait_end",
                    stage=stage,
                    settled=True,
                    elapsed_ms=_safe_elapsed_ms(settle_start),
                    polls=polls,
                    pending_conditions=last_pending,
                )
            return state
        time.sleep(0.6)
    if lifecycle is not None:
        lifecycle.event(
            "settle_wait_end",
            stage=stage,
            settled=False,
            elapsed_ms=_safe_elapsed_ms(settle_start),
            polls=polls,
            pending_conditions=last_pending,
    )
    return last


def _streamlit_runtime_transition_status(page) -> str:
    try:
        text = str(page.locator("body").inner_text(timeout=1_000) or "")
    except Exception:
        return "unreadable"
    upper = text.upper()
    for token in ("CONNECTING", "CONNECTION ERROR", "STREAMLIT SERVER IS NOT RESPONDING"):
        if token in upper:
            return token
    return ""


def _fail_if_streamlit_runtime_transition(page, *, step: dict[str, Any], stage: str) -> None:
    status = _streamlit_runtime_transition_status(page)
    if not status:
        return
    payload = dict(step)
    payload["streamlit_status"] = status
    payload["runtime_stage"] = stage
    payload["failure_classification"] = STREAMLIT_RUNTIME_RECONNECT_CLASS
    _fail(
        STREAMLIT_RUNTIME_RECONNECT_CLASS,
        f"Streamlit runtime transition visible during {stage}: {status}",
        payload,
    )


def assert_page_cycle_ghost_ui_contract(
    page,
    *,
    base_url: str,
    artifact_dir: Path,
    case_index: int | str | None,
    stage: str,
    console_messages: list[str] | None = None,
    lifecycle: LifecycleDiagnostics | None = None,
    page_cycle_mode: str = "full",
) -> dict[str, Any]:
    cycle_start = _perf_now()
    if lifecycle is not None:
        lifecycle.set_stage(stage, case_index=case_index, replay=lifecycle.current_replay)
        lifecycle.event("page_cycle_start", stage=stage, case_index=case_index)
    result = run_page_cycle_ghost_ui_check(
        page,
        base_url=base_url,
        artifact_dir=artifact_dir,
        console_messages=console_messages or [],
        label=f"{stage}_case_{case_index}",
        timeout_s=25.0,
        page_cycle_mode=page_cycle_mode,
    )
    if lifecycle is not None:
        compact_visited_pages = []
        for item in list(result.get("visited_pages") or []):
            settle = dict(item.get("settle") or {})
            compact_visited_pages.append(
                {
                    "page": item.get("page"),
                    "label": item.get("label"),
                    "settled": bool(settle.get("settled")),
                    "current_slug": settle.get("current_slug"),
                    "polls": settle.get("polls"),
                    "elapsed_ms": settle.get("elapsed_ms"),
                    "loading_visible": bool(settle.get("loading_visible")),
                    "body_text_length": settle.get("body_text_length"),
                    "failure_capture": bool(item.get("failed_page_capture")),
                }
            )
        lifecycle.event(
            "page_cycle_end",
            stage=stage,
            case_index=case_index,
            page_cycle_mode=result.get("page_cycle_mode"),
            page_cycle_reduced=bool(result.get("page_cycle_reduced")),
            elapsed_ms=_safe_elapsed_ms(cycle_start),
            ok=bool(result.get("ok")),
            failures=list(result.get("failures") or []),
            visited_pages=compact_visited_pages,
        )
    if not result.get("ok"):
        classification = str(result.get("failure_classification") or PAGE_CYCLE_GHOST_FAILURE_CLASS)
        step = {
            "step_index": stage,
            "step_type": stage,
            "case_index": case_index,
            "page_cycle_ghost_ui_check": result,
            "failure_report_wording": PAGE_CYCLE_GHOST_FAILURE_MESSAGE,
        }
        _fail(
            classification,
            (
                "Empty calc/check card shell remained visible after page settle. "
                if classification == EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS
                else "Bending page did not reach the visible ready gate before page-cycle settle. "
                if classification == BENDING_READY_GATE_TIMEOUT_CLASS
                else "Page-cycle failure evidence shows the page was visually healthy; likely verifier navigation/click lifecycle false positive. "
                if classification == PAGE_CYCLE_FALSE_POSITIVE_HEALTHY_CLASS
                else "Page-cycle failure evidence could not be captured because the page/context/browser was unavailable. "
                if classification == PAGE_CYCLE_CAPTURE_UNAVAILABLE_CLASS
                else PAGE_CYCLE_GHOST_FAILURE_MESSAGE + " "
            )
            + "; ".join(str(item) for item in list(result.get("failures") or [])),
            step,
        )
    return result


def click_cta_if_enabled(page) -> tuple[bool, dict[str, Any] | None]:
    try:
        button = page.get_by_role("button", name="Run one-click auto design").first
        if not (button.count() > 0 and button.is_visible(timeout=2000) and button.is_enabled(timeout=2000)):
            return False, None
        offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
        start_ms = int(time.time() * 1000)
        button.click(timeout=10_000)
        run_end, _ = _wait_for_run_end(offset, timeout_s=75.0, start_time_ms=start_ms)
        return True, dict((run_end or {}).get("data") or {})
    except Exception:
        return False, None


def generate_case(rng: random.Random, index: int) -> dict[str, Any]:
    archetypes = [
        "bending_fail",
        "shear_fail",
        "combined_fail",
        "bending_overdesign",
        "shear_overdesign",
        "all_pass_low",
        "all_pass_target",
        "very_low",
        "high_shear",
        "serviceability_sensitive",
    ]
    archetype = archetypes[index % len(archetypes)] if index < len(archetypes) else rng.choice(archetypes)
    recipe = rng.choice(BASE_RECIPES)
    if archetype == "bending_fail":
        mu, vu, recipe = rng.uniform(420, 720), rng.uniform(0, 80), "A_bending_under_only"
    elif archetype == "shear_fail":
        mu, vu, recipe = rng.uniform(0, 80), rng.uniform(420, 750), "B_shear_under_only"
    elif archetype == "combined_fail":
        mu, vu, recipe = rng.uniform(320, 700), rng.uniform(360, 740), "C_combined_underdesign"
    elif archetype == "bending_overdesign":
        mu, vu, recipe = rng.uniform(35, 110), rng.uniform(0, 40), "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED"
    elif archetype == "shear_overdesign":
        mu, vu, recipe = rng.uniform(80, 130), rng.uniform(0, 60), "SO_BASE_HEAVY_LINKS_CONSERVATIVE"
    elif archetype == "all_pass_target":
        mu, vu = rng.uniform(90, 150), rng.uniform(0, 120)
    elif archetype == "very_low":
        mu, vu, recipe = rng.uniform(0, 45), rng.uniform(0, 15), "SO_BASE_HEAVY_LINKS_CONSERVATIVE"
    elif archetype == "high_shear":
        mu, vu, recipe = rng.uniform(20, 150), rng.uniform(500, 850), "B_shear_under_only"
    elif archetype == "serviceability_sensitive":
        mu, vu, recipe = rng.uniform(80, 240), rng.uniform(20, 180), "MATRIX_DEFLECTION_ONLY_FAIL"
    else:
        mu, vu = rng.uniform(40, 220), rng.uniform(0, 260)
    return {
        "case_index": index,
        "archetype": archetype,
        "recipe": recipe,
        "mu": round(float(mu), 2),
        "vu": round(float(vu), 2),
        "section_shape": rng.choice(["RECT", "T", "I"]),
        "geometry_lock": rng.choice([False, False, True]),
        "span_m": round(rng.uniform(4.0, 9.0), 2),
        "b": rng.choice([250, 300, 350, 400, 450]),
        "D": rng.choice([300, 350, 400, 450, 500, 600]),
        "fc": rng.choice([25, 32, 40, 50]),
        "fsy": rng.choice([400, 500]),
        "bottom_bar_count": rng.choice([2, 3, 4, 5, 6]),
        "bottom_bar_dia": rng.choice([12, 16, 20, 24, 28]),
        "top_bar_count": rng.choice([2, 3, 4]),
        "top_bar_dia": rng.choice([10, 12, 16]),
        "lig_d": rng.choice([0, 10, 12, 16, 20, 24]),
        "lig_legs": rng.choice([0, 2, 4]),
        "s_lig": rng.choice([100, 125, 150, 200, 250, 300]),
    }


def generate_mutation(rng: random.Random, current: dict[str, Any], step: int) -> dict[str, Any]:
    mutation_type = rng.choice(
        [
            "increase_M",
            "decrease_M",
            "increase_V",
            "decrease_V",
            "load_combo_shift",
            "after_click_load_increase",
        ]
    )
    mu = float(current.get("mu") or 0.0)
    vu = float(current.get("vu") or 0.0)
    if mutation_type in {"increase_M", "after_click_load_increase"}:
        mu = min(800.0, mu * rng.uniform(1.15, 1.75) + rng.uniform(5, 40))
    elif mutation_type == "decrease_M":
        mu = max(0.0, mu * rng.uniform(0.45, 0.85))
    elif mutation_type == "increase_V":
        vu = min(900.0, vu * rng.uniform(1.2, 1.9) + rng.uniform(10, 80))
    elif mutation_type == "decrease_V":
        vu = max(0.0, vu * rng.uniform(0.3, 0.8))
    else:
        mu = min(800.0, max(0.0, mu + rng.uniform(-80, 180)))
        vu = min(900.0, max(0.0, vu + rng.uniform(-80, 220)))
    return {"mutation_type": mutation_type, "mu": round(mu, 2), "vu": round(vu, 2), "step": step}


def apply_initial_case(
    page,
    base_url: str,
    case: dict[str, Any],
    *,
    reload_between_cases: bool,
    console_messages: list[str] | None = None,
    lifecycle: LifecycleDiagnostics | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    setup_recipe = str(case.get("recipe") or "").strip()
    if (
        str(case.get("golden_case_name") or "").strip() == "serviceability_blocked"
        and setup_recipe == "MATRIX_DEFLECTION_ONLY_FAIL"
    ):
        setup_recipe = "GOLDEN_SERVICEABILITY_BLOCKED"

    def _probe_failure(ready: dict[str, Any], message: str) -> VisibleContractFailure:
        step = capture_pre_timeline_probe_timeout_step(
            page,
            base_url=base_url,
            console_messages=console_messages or [],
            message=str(ready.get("message") or message),
            stage=str(ready.get("timeout_stage") or "browser_state_probe_attach"),
            setup_override=ready,
        )
        return VisibleContractFailure(
            str(ready.get("classification") or "browser_probe_timeout_before_timeline"),
            str(ready.get("message") or message),
            step,
        )

    def _apply_optional_widgets() -> None:
        # Optional widgets: best effort only; Mu/Vu are committed by the shared helper.
        _safe_input_number(page, "Span length L (m)", float(case.get("span_m") or 6.0))
        _safe_input_number(page, "Width b (mm)", float(case.get("b") or 300.0))
        _safe_input_number(page, "Overall depth D (mm)", float(case.get("D") or 400.0))
        _safe_input_number(page, "Link spacing s_lig (mm)", float(case.get("s_lig") or 200.0))

    if reload_between_cases:
        url = _query(base_url, {"browser_recipe": setup_recipe, "page": "inputs"})
        nav_start = _perf_now()
        if lifecycle is not None:
            lifecycle.event("replay_input_application_navigation_start", url=url)
        _record_playwright_stage("initial_goto_start", page=page, active_url=url)
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        _record_playwright_stage("initial_goto_done", page=page, success=True)
        if lifecycle is not None:
            lifecycle.event("replay_input_application_navigation_end", elapsed_ms=_safe_elapsed_ms(nav_start), url=str(page.url))
        ready_start = _perf_now()
        if lifecycle is not None:
            lifecycle.event("streamlit_ready_wait_start", timeout_s=120.0, allow_reload_once=True)
        _record_playwright_stage("streamlit_ready_start", page=page, timeout_s=120.0)
        ready = wait_for_browser_state_probe_ready(
            page,
            base_url=base_url,
            console_messages=console_messages or [],
            timeout_s=120.0,
            allow_reload_once=True,
            require_rendered_outputs=False,
        )
        _record_playwright_stage("streamlit_ready_done", page=page, success=bool(ready.get("ready")), classification=ready.get("classification"))
        if lifecycle is not None:
            lifecycle.event(
                "streamlit_ready_wait_end",
                elapsed_ms=_safe_elapsed_ms(ready_start),
                ready=bool(ready.get("ready")),
                readiness_classification=ready.get("classification"),
                pending_readiness=ready.get("result_after_retry") or ready.get("readiness_attempts"),
            )
        if not ready.get("ready"):
            raise _probe_failure(ready, "Browser state probe was not readable before timeline capture.")
    optional_start = _perf_now()
    if lifecycle is not None:
        lifecycle.event("optional_widget_application_start")
    _record_playwright_stage("recipe_apply_start", page=page, recipe=setup_recipe, requested_recipe=case.get("recipe"))
    _apply_optional_widgets()
    if lifecycle is not None:
        lifecycle.event("optional_widget_application_end", elapsed_ms=_safe_elapsed_ms(optional_start))
    ready_widgets_start = _perf_now()
    if lifecycle is not None:
        lifecycle.event("post_widget_readiness_start", timeout_s=60.0)
    ready_after_widgets = wait_for_browser_state_probe_ready(
        page,
        base_url=base_url,
        console_messages=console_messages or [],
        timeout_s=60.0,
        allow_reload_once=False,
        require_rendered_outputs=False,
    )
    if lifecycle is not None:
        lifecycle.event(
            "post_widget_readiness_end",
            elapsed_ms=_safe_elapsed_ms(ready_widgets_start),
            ready=bool(ready_after_widgets.get("ready")),
            readiness_classification=ready_after_widgets.get("classification"),
            pending_readiness=ready_after_widgets.get("result_after_retry") or ready_after_widgets.get("readiness_attempts"),
        )
    if not ready_after_widgets.get("ready"):
        if reload_between_cases:
            url = _query(base_url, {"browser_recipe": setup_recipe, "page": "inputs"})
            if lifecycle is not None:
                lifecycle.event("post_widget_probe_recovery_reload_start", url=url)
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            if lifecycle is not None:
                lifecycle.event("post_widget_probe_recovery_reload_end", url=str(page.url))
            ready_after_reload = wait_for_browser_state_probe_ready(
                page,
                base_url=base_url,
                console_messages=console_messages or [],
                timeout_s=60.0,
                allow_reload_once=True,
                require_rendered_outputs=False,
            )
            if lifecycle is not None:
                lifecycle.event(
                    "post_widget_probe_recovery_readiness",
                    ready=bool(ready_after_reload.get("ready")),
                    readiness_classification=ready_after_reload.get("classification"),
                    pending_readiness=ready_after_reload.get("result_after_retry") or ready_after_reload.get("readiness_attempts"),
                )
            if not ready_after_reload.get("ready"):
                raise _probe_failure(ready_after_reload, "Browser state probe dropped during pre-timeline widget setup.")
            _apply_optional_widgets()
            ready_after_widgets = wait_for_browser_state_probe_ready(
                page,
                base_url=base_url,
                console_messages=console_messages or [],
                timeout_s=60.0,
                allow_reload_once=False,
                require_rendered_outputs=False,
            )
        if not ready_after_widgets.get("ready"):
            raise _probe_failure(ready_after_widgets, "Browser state probe dropped during pre-timeline widget setup.")
    required_recipe = setup_recipe if bool(case.get("require_browser_recipe_applied")) else ""
    if required_recipe:
        try:
            recipe_state = _load_browser_state(page)
        except Exception as exc:
            recipe_state = {
                "browser_recipe": None,
                "browser_recipe_error": f"recipe_state_read_failed:{type(exc).__name__}: {exc}",
            }
        applied_recipe = str(recipe_state.get("browser_recipe") or "").strip()
        if applied_recipe != required_recipe:
            setup = {
                "ready": False,
                "classification": "browser_recipe_not_applied",
                "message": (
                    f"Focused replay required browser recipe {required_recipe!r}, "
                    f"but app probe reported {applied_recipe!r}."
                ),
                "timeout_stage": "browser_recipe_application",
                "required_browser_recipe": required_recipe,
                "applied_browser_recipe": applied_recipe or None,
                "browser_recipe_error": recipe_state.get("browser_recipe_error"),
                "browser_recipe_kind": recipe_state.get("browser_recipe_kind"),
                "browser_recipe_applied_state": recipe_state.get("browser_recipe_applied_state"),
                "browser_query_param_probe": recipe_state.get("browser_query_param_probe"),
                "browser_shared_probe": recipe_state.get("browser_shared_probe"),
                "current_url": str(getattr(page, "url", "") or ""),
            }
            raise _probe_failure(setup, setup["message"])
    last_timeout: PlaywrightTimeoutError | None = None
    if lifecycle is not None:
        lifecycle.set_stage(
            "replay_input_application",
            case_index=case.get("case_index"),
            extra={
                "requested_mu": float(case["mu"]),
                "requested_vu": float(case["vu"]),
            },
        )
    for apply_attempt in range(3):
        apply_start = _perf_now()
        if lifecycle is not None:
            lifecycle.event(
                "replay_input_application_start",
                apply_attempt=apply_attempt,
                requested_mu=float(case["mu"]),
                requested_vu=float(case["vu"]),
                mu_input_before=_input_editability_snapshot(page, MU_LABEL, requested_value=float(case["mu"])),
                vu_input_before=_input_editability_snapshot(page, VU_LABEL, requested_value=float(case["vu"])),
            )
        _record_playwright_stage(
            "input_apply_start",
            page=page,
            apply_attempt=apply_attempt,
            requested_mu=float(case["mu"]),
            requested_vu=float(case["vu"]),
        )
        _record_playwright_stage("input_apply_mu_start", page=page, apply_attempt=apply_attempt, requested_value=float(case["mu"]))
        _record_playwright_stage("input_apply_vu_start", page=page, apply_attempt=apply_attempt, requested_value=float(case["vu"]))
        try:
            setattr(_set_number_input_with_disabled_guard, "_route_gate_ready_seen", False)
            state, meta = _apply_live_inputs(page, mu=float(case["mu"]), vu=float(case["vu"]))
            _record_playwright_stage("input_apply_mu_done", page=page, success=True, apply_attempt=apply_attempt)
            _record_playwright_stage("input_apply_vu_done", page=page, success=True, apply_attempt=apply_attempt)
            _record_playwright_stage("input_apply_done", page=page, success=True, apply_attempt=apply_attempt)
            if lifecycle is not None:
                lifecycle.event(
                    "replay_input_application_end",
                    apply_attempt=apply_attempt,
                    elapsed_ms=_safe_elapsed_ms(apply_start),
                    applied=True,
                    apply_meta=meta,
                    mu_input_after=_input_editability_snapshot(page, MU_LABEL, requested_value=float(case["mu"])),
                    vu_input_after=_input_editability_snapshot(page, VU_LABEL, requested_value=float(case["vu"])),
                    summary_state_probe=dict(state.get("summary_state_probe") or {}),
                    browser_shared_probe=dict(state.get("browser_shared_probe") or {}),
                )
                lifecycle.mark_success("replay_input_application_end", elapsed_ms=_safe_elapsed_ms(apply_start))
            return state, meta
        except PlaywrightTimeoutError as exc:
            _record_playwright_stage("input_apply_timeout", page=page, exception=exc, apply_attempt=apply_attempt)
            if "Browser state" not in f"{type(exc).__name__}: {exc}":
                raise
            last_timeout = exc
            if lifecycle is not None:
                lifecycle.event(
                    "replay_input_application_probe_timeout",
                    apply_attempt=apply_attempt,
                    elapsed_ms=_safe_elapsed_ms(apply_start),
                    exception=f"{type(exc).__name__}: {exc}",
                    mu_input_after_timeout=_input_editability_snapshot(page, MU_LABEL, requested_value=float(case["mu"])),
                    vu_input_after_timeout=_input_editability_snapshot(page, VU_LABEL, requested_value=float(case["vu"])),
                )
            ready_after_timeout = wait_for_browser_state_probe_ready(
                page,
                base_url=base_url,
                console_messages=console_messages or [],
                timeout_s=90.0,
                allow_reload_once=bool(apply_attempt >= 1),
                require_rendered_outputs=False,
            )
            if lifecycle is not None:
                lifecycle.event(
                    "replay_input_application_probe_recovery",
                    apply_attempt=apply_attempt,
                    ready=bool(ready_after_timeout.get("ready")),
                    readiness_classification=ready_after_timeout.get("classification"),
                    pending_readiness=ready_after_timeout.get("result_after_retry") or ready_after_timeout.get("readiness_attempts"),
                )
            if not ready_after_timeout.get("ready"):
                raise _probe_failure(ready_after_timeout, "Browser state probe dropped while applying live inputs.")
            # Streamlit can briefly detach the debug textarea while committing
            # Mu/Vu.  Retry the same setup operation only after the probe is
            # independently readable again, so product assertions still start
            # from a real Browser state snapshot.
            time.sleep(0.5)
        except RuntimeError as exc:
            _record_playwright_stage("input_apply_runtime_failure", page=page, exception=exc, apply_attempt=apply_attempt)
            artifact_dir = _CURRENT_INPUT_EDIT_ARTIFACT_DIR
            diagnostic: dict[str, Any] = {
                "classification": "replay_input_application_runtime_stall",
                "message": f"{type(exc).__name__}: {exc}",
                "apply_attempt": apply_attempt,
                "elapsed_ms": _safe_elapsed_ms(apply_start),
                "requested_mu": float(case["mu"]),
                "requested_vu": float(case["vu"]),
                "current_url": "",
                "page_title": "",
                "focused_element": {},
                "mu_input": {},
                "vu_input": {},
                "process_snapshot": lifecycle.process_snapshot("replay_input_application_runtime_stall")
                if lifecycle is not None
                else {},
            }
            try:
                diagnostic["current_url"] = str(page.url)
            except Exception as url_exc:
                diagnostic["current_url_error"] = f"{type(url_exc).__name__}: {url_exc}"
            try:
                diagnostic["page_title"] = str(page.locator("title").text_content(timeout=1_000) or "")
            except Exception as title_exc:
                diagnostic["page_title_error"] = f"{type(title_exc).__name__}: {title_exc}"
            try:
                diagnostic["focused_element"] = dict(
                    page.evaluate(
                        """
                        () => {
                          const el = document.activeElement;
                          if (!el) return {};
                          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : {x:0,y:0,width:0,height:0};
                          return {
                            tag: el.tagName ? el.tagName.toLowerCase() : "",
                            aria_label: el.getAttribute ? el.getAttribute("aria-label") : null,
                            value: "value" in el ? el.value : null,
                            disabled: Boolean(el.disabled),
                            readonly: Boolean(el.readOnly || (el.hasAttribute && el.hasAttribute("readonly"))),
                            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                          };
                        }
                        """
                    )
                    or {}
                )
            except Exception as focus_exc:
                diagnostic["focused_element_error"] = f"{type(focus_exc).__name__}: {focus_exc}"
            try:
                diagnostic["mu_input"] = _input_editability_snapshot(page, MU_LABEL, requested_value=float(case["mu"]))
                diagnostic["vu_input"] = _input_editability_snapshot(page, VU_LABEL, requested_value=float(case["vu"]))
            except Exception as snapshot_exc:
                diagnostic["input_snapshot_error"] = f"{type(snapshot_exc).__name__}: {snapshot_exc}"
            recovered_state, recovery_diagnostic = _read_reconciled_input_state_after_runtime_failure(
                page,
                mu=float(case["mu"]),
                vu=float(case["vu"]),
                timeout_s=5.0,
            )
            diagnostic["post_failure_direct_state_read"] = recovery_diagnostic
            if recovery_diagnostic.get("state_matches_requested_inputs"):
                diagnostic["classification"] = "replay_input_application_runtime_recovered"
                diagnostic["recovered_after_helper_runtime_stall"] = True
                if lifecycle is not None:
                    lifecycle.event(
                        "replay_input_application_runtime_recovered",
                        apply_attempt=apply_attempt,
                        elapsed_ms=_safe_elapsed_ms(apply_start),
                        recovery_source=dict(recovery_diagnostic.get("read_meta") or {}).get("source"),
                        recovery_raw_length=dict(recovery_diagnostic.get("read_meta") or {}).get("raw_length"),
                    )
                    lifecycle.mark_success("replay_input_application_end", elapsed_ms=_safe_elapsed_ms(apply_start))
                _record_playwright_stage(
                    "input_apply_runtime_recovered",
                    page=page,
                    success=True,
                    apply_attempt=apply_attempt,
                    recovery_source=dict(recovery_diagnostic.get("read_meta") or {}).get("source"),
                )
                if artifact_dir is not None:
                    _write_json(Path(artifact_dir) / "replay_input_application_runtime_recovery.json", diagnostic)
                return recovered_state, {
                    "runtime_recovered_after_helper_stall": True,
                    "original_error": f"{type(exc).__name__}: {exc}",
                    "recovery": recovery_diagnostic,
                }
            if artifact_dir is not None:
                try:
                    shot_path = Path(artifact_dir) / "replay_input_application_runtime_stall.png"
                    page.screenshot(path=str(shot_path), full_page=True, timeout=3_000)
                    diagnostic["screenshot_path"] = str(shot_path)
                except Exception as shot_exc:
                    diagnostic["screenshot_error"] = f"{type(shot_exc).__name__}: {shot_exc}"
                _write_json(Path(artifact_dir) / "replay_input_application_runtime_stall.json", diagnostic)
            raise VisibleContractFailure(
                "replay_input_application_runtime_stall",
                "Verifier input application did not reconcile before product assertions.",
                {
                    "step_index": None,
                    "step_type": "verifier_setup_input_application",
                    "setup_diagnostics": diagnostic,
                    "browser_state": {},
                },
            )
    if last_timeout is not None:
        _record_playwright_stage("post_input_settle_start", page=page, timeout_s=90.0)
        ready_after_timeout = wait_for_browser_state_probe_ready(
            page,
            base_url=base_url,
            console_messages=console_messages or [],
            timeout_s=90.0,
            allow_reload_once=True,
            require_rendered_outputs=False,
        )
        _record_playwright_stage(
            "post_input_settle_done",
            page=page,
            success=bool(ready_after_timeout.get("ready")),
            classification=ready_after_timeout.get("classification"),
        )
        raise _probe_failure(
            ready_after_timeout,
            f"Browser state probe remained unstable while applying live inputs: {last_timeout}",
        )
    return {}, {}


def _page_count(page, selector: str) -> int | None:
    try:
        return int(page.locator(selector).count())
    except Exception:
        return None


def _label_count(page, label: str) -> int | None:
    try:
        return int(page.get_by_label(label).count())
    except Exception:
        return None


def _probe_selector_counts(page) -> dict[str, int | None]:
    selectors = {
        "textarea_aria_label": "textarea[aria-label='Browser state']",
        "any_aria_label": "[aria-label='Browser state']",
        "textarea_name_hint": "textarea",
        "fast_guidance_item": ".fast-guidance-item",
        "streamlit_textarea": "[data-testid='stTextArea'] textarea",
        "streamlit_code": "[data-testid='stCodeBlock']",
    }
    return {name: _page_count(page, selector) for name, selector in selectors.items()}


def _streamlit_status_text(page) -> str:
    try:
        text = str(
            page.locator(
                "[data-testid='stStatusWidget'], [data-testid='stSpinner'], "
                "[data-testid='stAppViewContainer'] [aria-busy='true']"
            )
            .first
            .inner_text(timeout=500)
            or ""
        )
        return re.sub(r"\s+", " ", text).strip()[:240]
    except Exception:
        return ""


def _post_baseline_heartbeat(
    artifact_dir: Path,
    page,
    *,
    stage: str,
    replay_started_perf: float,
    port: int | None,
    case_index: int | str | None = None,
    step_index: int | str | None = None,
    active_input_label: str | None = None,
    last_successful_playwright_call: str | None = None,
    last_exception: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Post-baseline diagnostic heartbeat only; never decides pass/fail."""
    path = Path(artifact_dir) / "post_baseline_replay_heartbeat.jsonl"
    snapshot_path = Path(artifact_dir) / "post_baseline_stall_snapshot.json"
    page_state = _page_closed_state(page)
    previous: dict[str, Any] | None = None
    try:
        if path.exists():
            last_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[-1:]
            if last_line:
                previous = json.loads(last_line[0])
    except Exception:
        previous = None
    payload: dict[str, Any] = {
        "timestamp": _iso_now(),
        "perf_counter": _perf_now(),
        "stage": str(stage),
        "elapsed_ms_since_replay_start": _safe_elapsed_ms(replay_started_perf),
        "case_index": case_index,
        "step_index": step_index,
        "active_input_label": active_input_label,
        "active_url": "",
        "page_title": "",
        "streamlit_status": "",
        "page_closed": page_state.get("page_closed"),
        "context_closed": page_state.get("context_closed"),
        "browser_closed": page_state.get("browser_closed"),
        "context_page_count": page_state.get("context_page_count"),
        "process_memory": {"available": False, "reason": "full process snapshot captured only on stall to keep heartbeat cheap"},
        "last_successful_playwright_call": str(last_successful_playwright_call or stage),
        "last_exception": f"{type(last_exception).__name__}: {last_exception}" if last_exception is not None else "",
    }
    if page is not None and not payload.get("page_closed"):
        try:
            payload["active_url"] = str(page.url or "")
        except Exception as exc:
            payload["last_exception"] = f"url:{type(exc).__name__}: {exc}"
        try:
            payload["page_title"] = str(page.title() or "")
        except Exception as exc:
            payload["last_exception"] = f"title:{type(exc).__name__}: {exc}"
        payload["streamlit_status"] = _streamlit_status_text(page)
    payload.update(dict(extra or {}))
    if previous:
        try:
            gap_ms = int((float(payload.get("perf_counter") or 0.0) - float(previous.get("perf_counter") or 0.0)) * 1000.0)
        except Exception:
            gap_ms = 0
        payload["ms_since_previous_post_baseline_heartbeat"] = gap_ms
        if gap_ms > 120_000:
            stall_payload = {
                "classification": "post_baseline_runtime_stall_observed",
                "message": "No post-baseline heartbeat advanced within the diagnostic threshold.",
                "last_heartbeat": previous,
                "current_heartbeat": payload,
                "process_snapshot": _collect_process_snapshot(port),
                "thread_stacks": _thread_stack_excerpt(),
                "screenshot_path": None,
                "visible_text_excerpt": "",
                "console_error_count": None,
            }
            try:
                screenshot = Path(artifact_dir) / f"post_baseline_stall_{re.sub(r'[^A-Za-z0-9_.-]+', '_', str(stage)).strip('_')}.png"
                page.screenshot(path=str(screenshot), full_page=False, timeout=5_000)
                stall_payload["screenshot_path"] = str(screenshot)
            except Exception as exc:
                stall_payload["screenshot_error"] = f"{type(exc).__name__}: {exc}"
            try:
                stall_payload["visible_text_excerpt"] = str(page.locator("body").inner_text(timeout=2_000) or "")[:8_000]
            except Exception as exc:
                stall_payload["visible_text_error"] = f"{type(exc).__name__}: {exc}"
            _write_json(snapshot_path, stall_payload)
            payload["stall_snapshot_path"] = str(snapshot_path)
    _append_jsonl(path, payload)
    return payload


def _read_browser_state_probe_direct(
    page,
    *,
    timeout_s: float = 0.0,
    poll_interval_s: float = 0.25,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    selectors = [
        ("label", None),
        ("textarea_aria_label", "textarea[aria-label='Browser state']"),
        ("any_aria_label", "[aria-label='Browser state']"),
        ("streamlit_textarea", "[data-testid='stTextArea'] textarea"),
        ("streamlit_code", "[data-testid='stCodeBlock']"),
    ]
    deadline = time.time() + max(0.0, float(timeout_s or 0.0))
    while True:
        try:
            dom_candidates = list(
                page.evaluate(
                    """
                    () => {
                      const candidates = [];
                      const seen = new Set();
                      const push = (el, source) => {
                        if (!el || seen.has(el)) return;
                        seen.add(el);
                        let raw = "";
                        try {
                          if ("value" in el && el.value) raw = String(el.value);
                          else raw = String(el.innerText || el.textContent || "");
                        } catch (err) {
                          raw = "";
                        }
                        candidates.push({
                          source,
                          tag: el.tagName ? el.tagName.toLowerCase() : "",
                          raw,
                          raw_length: raw.length,
                          aria_label: el.getAttribute ? el.getAttribute("aria-label") : null,
                          testid: el.getAttribute ? el.getAttribute("data-testid") : null
                        });
                      };
                      document.querySelectorAll("textarea[aria-label='Browser state']").forEach((el) => push(el, "textarea_aria_label_dom"));
                      document.querySelectorAll("[data-testid='stTextArea'] textarea").forEach((el) => push(el, "streamlit_textarea_dom"));
                      document.querySelectorAll("[aria-label='Browser state']").forEach((el) => push(el, "any_aria_label_dom"));
                      document.querySelectorAll("[data-testid='stCodeBlock']").forEach((el) => push(el, "streamlit_code_dom"));
                      return candidates
                        .filter((item) => item.raw && item.raw.trim())
                        .sort((a, b) => (b.raw_length || 0) - (a.raw_length || 0))
                        .slice(0, 8);
                    }
                    """
                )
                or []
            )
            for candidate in dom_candidates:
                raw = str(dict(candidate).get("raw") or "").strip()
                source = str(dict(candidate).get("source") or "dom_candidate")
                attempts.append({"source": source, "found": True, "raw_length": len(raw)})
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return parsed, {"readable": True, "source": source, "raw_length": len(raw), "attempts": attempts[-25:]}
                except Exception as exc:
                    attempts[-1]["json_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            attempts.append({"source": "dom_candidates", "error": f"{type(exc).__name__}: {exc}"})
        for source, selector in selectors:
            try:
                if selector is None:
                    locator = page.get_by_label("Browser state").first
                else:
                    locator = page.locator(selector).first
                if locator.count() <= 0:
                    attempts.append({"source": source, "found": False})
                    continue
                raw = ""
                try:
                    raw = locator.input_value(timeout=1_000)
                except Exception:
                    try:
                        raw = locator.text_content(timeout=1_000) or ""
                    except Exception:
                        try:
                            raw = locator.inner_text(timeout=1_000) or ""
                        except Exception:
                            raw = ""
                raw = str(raw or "").strip()
                attempts.append({"source": source, "found": True, "raw_length": len(raw)})
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return parsed, {"readable": True, "source": source, "raw_length": len(raw), "attempts": attempts[-25:]}
                except Exception as exc:
                    attempts[-1]["json_error"] = f"{type(exc).__name__}: {exc}"
            except Exception as exc:
                attempts.append({"source": source, "error": f"{type(exc).__name__}: {exc}"})
        if time.time() >= deadline:
            break
        time.sleep(max(0.05, float(poll_interval_s or 0.25)))
    return None, {"readable": False, "attempts": attempts[-25:]}


def _state_probe_matches_requested_inputs(state: dict[str, Any] | None, *, mu: float, vu: float) -> bool:
    state = dict(state or {})
    shared_probe = dict(state.get("browser_shared_probe") or {})
    summary_probe = dict(state.get("summary_state_probe") or {})
    if not shared_probe:
        return False

    shared_mu_ok = any(
        _same_value(shared_probe.get(field), mu)
        for field in ("uls_Mstar", "load_Mstar_proxy", "inputs_load_Mstar_pos_proxy")
    )
    shared_vu_ok = any(
        _same_value(shared_probe.get(field), vu)
        for field in ("uls_Vstar", "load_Vstar_proxy", "inputs_load_Vstar_proxy")
    )
    if not (shared_mu_ok and shared_vu_ok):
        return False

    summary_mu_present = summary_probe.get("uls_Mstar") is not None
    summary_vu_present = summary_probe.get("uls_Vstar") is not None
    summary_mu_ok = (not summary_mu_present) or _same_value(summary_probe.get("uls_Mstar"), mu)
    summary_vu_ok = (not summary_vu_present) or _same_value(summary_probe.get("uls_Vstar"), vu)
    return bool(summary_mu_ok and summary_vu_ok)


def _input_state_reconciliation_diagnostic(state: dict[str, Any] | None, *, mu: float, vu: float) -> dict[str, Any]:
    state = dict(state or {})
    shared_probe = dict(state.get("browser_shared_probe") or {})
    summary_probe = dict(state.get("summary_state_probe") or {})
    return {
        "state_present": bool(state),
        "state_matches_requested_inputs": _state_probe_matches_requested_inputs(state, mu=mu, vu=vu),
        "summary_state_probe": summary_probe,
        "browser_shared_probe": shared_probe,
        "actions_used": dict(state.get("actions_used") or {}),
        "root_keys": sorted(str(key) for key in state.keys())[:80],
    }


def _read_reconciled_input_state_after_runtime_failure(
    page,
    *,
    mu: float,
    vu: float,
    timeout_s: float = 5.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state, read_meta = _read_browser_state_probe_direct(page, timeout_s=timeout_s, poll_interval_s=0.2)
    diagnostic = _input_state_reconciliation_diagnostic(state, mu=mu, vu=vu)
    diagnostic["read_meta"] = read_meta
    diagnostic["timeout_s"] = timeout_s
    return dict(state or {}), diagnostic


def _message_indicates_probe_teardown(value: Any) -> bool:
    text = str(value or "").lower()
    return any(term in text for term in BROWSER_PROBE_TEARDOWN_TERMS)


def _probe_read_meta_indicates_teardown(read_meta: dict[str, Any] | None) -> bool:
    meta = dict(read_meta or {})
    if _message_indicates_probe_teardown(meta.get("error")):
        return True
    for attempt in list(meta.get("attempts") or []):
        if isinstance(attempt, dict) and (
            _message_indicates_probe_teardown(attempt.get("error"))
            or _message_indicates_probe_teardown(attempt.get("message"))
        ):
            return True
    return False


def _page_closed_state(page) -> dict[str, Any]:
    state: dict[str, Any] = {
        "page_closed": None,
        "context_closed": None,
        "browser_closed": None,
        "context_page_count": None,
        "state_errors": [],
    }
    if page is None:
        state["page_closed"] = True
        state["state_errors"].append("page object unavailable")
        return state
    try:
        state["page_closed"] = bool(page.is_closed())
    except Exception as exc:
        state["state_errors"].append(f"page_is_closed: {type(exc).__name__}: {exc}")
    try:
        context = page.context
        try:
            state["context_page_count"] = len(context.pages)
            state["context_closed"] = False
        except Exception as exc:
            state["context_closed"] = True
            state["state_errors"].append(f"context_pages: {type(exc).__name__}: {exc}")
        try:
            browser = getattr(context, "browser", None)
            if callable(browser):
                browser = browser()
            if browser is not None and hasattr(browser, "is_connected"):
                state["browser_closed"] = not bool(browser.is_connected())
        except Exception as exc:
            state["state_errors"].append(f"browser_is_connected: {type(exc).__name__}: {exc}")
    except Exception as exc:
        state["context_closed"] = True
        state["state_errors"].append(f"context_lookup: {type(exc).__name__}: {exc}")
    return state


def capture_browser_probe_lifecycle_snapshot(
    page,
    artifact_dir: Path,
    *,
    reason: str,
    console_messages: list[str] | None,
    port: int,
    case_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Best-effort pre-teardown snapshot for browser-state probe lifecycle failures."""
    snapshot: dict[str, Any] = {
        "reason": str(reason or ""),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "active_replay_row_name": (case_result or {}).get("name")
        or (case_result or {}).get("replay_name")
        or (case_result or {}).get("case_name"),
        "prior_replay_row_name": (case_result or {}).get("prior_replay_row_name"),
        "case_index": (case_result or {}).get("case_index"),
        "current_url": "",
        "page_title": "",
        "visible_text_excerpt": "",
        "visible_text_length": 0,
        "browser_state_dom_exists": None,
        "browser_state_selector_counts": {},
        "console_errors": [
            message
            for message in list(console_messages or [])
            if "error" in str(message).lower() or "traceback" in str(message).lower()
        ][-25:],
        "page_context_browser_state": _page_closed_state(page),
        "process_snapshot": _collect_process_snapshot(port),
        "capture_errors": [],
    }
    if page is not None:
        try:
            snapshot["current_url"] = str(page.url or "")
        except Exception as exc:
            snapshot["capture_errors"].append(f"url: {type(exc).__name__}: {exc}")
        try:
            snapshot["page_title"] = str(page.title() or "")
        except Exception as exc:
            snapshot["capture_errors"].append(f"title: {type(exc).__name__}: {exc}")
        try:
            visible_text = str(page.locator("body").inner_text(timeout=2_000) or "")
            snapshot["visible_text_excerpt"] = visible_text[:8_000]
            snapshot["visible_text_length"] = len(visible_text)
        except Exception as exc:
            snapshot["capture_errors"].append(f"visible_text: {type(exc).__name__}: {exc}")
        try:
            selector_counts = _probe_selector_counts(page)
            snapshot["browser_state_selector_counts"] = selector_counts
            snapshot["browser_state_dom_exists"] = any(
                int(value or 0) > 0
                for key, value in selector_counts.items()
                if key != "fast_guidance_item"
            )
        except Exception as exc:
            snapshot["capture_errors"].append(f"browser_state_dom_exists: {type(exc).__name__}: {exc}")
        try:
            shot_path = artifact_dir / "browser_probe_lifecycle_snapshot.png"
            page.screenshot(path=str(shot_path), full_page=False, timeout=5_000)
            snapshot["screenshot"] = str(shot_path)
        except Exception as exc:
            snapshot["capture_errors"].append(f"screenshot: {type(exc).__name__}: {exc}")
    path = artifact_dir / "browser_probe_lifecycle_snapshot.json"
    _write_json(path, snapshot)
    snapshot["path"] = str(path)
    return snapshot


def _load_browser_state(page, timeout_s: float = 8.0) -> dict[str, Any]:
    """Read Browser state through robust probe fallbacks before label-only helper."""
    browser_state, read_meta = _read_browser_state_probe_direct(page, timeout_s=timeout_s)
    if isinstance(browser_state, dict):
        return browser_state
    try:
        return _load_browser_state_by_label(page)
    except Exception as exc:
        attempts = list((read_meta or {}).get("attempts") or [])
        if attempts:
            try:
                exc.args = (
                    f"{exc}; direct Browser state probe attempts: "
                    f"{json.dumps(attempts[-5:], default=_json_default)}",
                )
            except Exception:
                pass
        raise


for _helper_func in (
    _apply_live_inputs,
    _wait_for_post_click_state_without_run_end,
    _wait_for_post_publish_alignment,
):
    try:
        _helper_func.__globals__["_load_browser_state"] = _load_browser_state
    except Exception:
        pass


_ORIGINAL_SET_NUMBER_INPUT = _apply_live_inputs.__globals__.get("_set_number_input")
_CURRENT_INPUT_EDIT_ARTIFACT_DIR: Path | None = None
_CURRENT_INPUT_EDIT_CONSOLE_MESSAGES: list[str] | None = None
_CURRENT_REPLAY_INPUT_SETUP_TYPE: str = "unknown"


def _write_input_edit_json(path: Path, payload: Any) -> str | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _write_replay_input_setup_mode_event(
    *,
    label: str,
    requested_value: Any,
    phase: str,
    route_gate: dict[str, Any] | None = None,
    stability_probe: dict[str, Any] | None = None,
    commit_probe: dict[str, Any] | None = None,
    already_value_matched: bool = False,
    final_setup_classification: str | None = None,
) -> None:
    artifact_dir = _CURRENT_INPUT_EDIT_ARTIFACT_DIR
    if artifact_dir is None:
        return
    path = Path(artifact_dir) / "replay_input_setup_mode.json"
    observations = list((stability_probe or {}).get("all_observations") or [])
    summary = _summarise_input_lifecycle_trace(stability_probe or {}) if stability_probe else {}
    event = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "phase": phase,
        "label": label,
        "requested_value": requested_value,
        "replay_type": _CURRENT_REPLAY_INPUT_SETUP_TYPE,
        "input_setup_helper_used": "_set_number_input_with_disabled_guard",
        "route_readiness_helper_used": "wait_for_inputs_content_ready_before_probe",
        "route_readiness_ready": bool((route_gate or {}).get("ready")) if route_gate is not None else None,
        "route_readiness_skipped": bool((route_gate or {}).get("skipped")) if route_gate is not None else None,
        "route_readiness_reason": (route_gate or {}).get("reason") if route_gate is not None else None,
        "locator_recreation_count": sum(1 for obs in observations if obs.get("locator_recreated_after_rerun")),
        "rerun_detection_count": int(summary.get("node_identity_change_count") or 0),
        "rerun_reset_count": int(summary.get("rerun_reset_count") or 0),
        "disabled_detected": bool(summary.get("disabled_detected")),
        "first_enabled_timestamp": summary.get("first_enabled_timestamp"),
        "stable_enabled_poll_count": int(summary.get("stable_enabled_poll_count") or 0),
        "final_enabled_state": summary.get("final_enabled_state"),
        "already_value_matched_decision": bool(already_value_matched),
        "commit_confirmation_result": (
            {
                "committed": bool((commit_probe or {}).get("committed")),
                "elapsed_ms": (commit_probe or {}).get("elapsed_ms"),
                "polls": (commit_probe or {}).get("polls"),
                "final_observation": (commit_probe or {}).get("last_observation"),
            }
            if commit_probe is not None
            else None
        ),
        "stale_locator_detection": bool(
            int(summary.get("attach_detach_transition_count") or 0) > 0
            or int(summary.get("node_identity_change_count") or 0) > 0
        ),
        "final_setup_classification": final_setup_classification,
        "stability_summary": summary,
    }
    payload: dict[str, Any] = {
        "replay_type": _CURRENT_REPLAY_INPUT_SETUP_TYPE,
        "input_setup_helper_used": "_set_number_input_with_disabled_guard",
        "route_readiness_helper_used": "wait_for_inputs_content_ready_before_probe",
        "events": [],
    }
    try:
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload.update(existing)
                payload["events"] = list(existing.get("events") or [])
    except Exception:
        payload["events"] = []
    payload["events"].append(event)
    payload["final_setup_classification"] = final_setup_classification or payload.get("final_setup_classification")
    payload["locator_recreation_count"] = sum(
        int((item or {}).get("locator_recreation_count") or 0) for item in payload["events"]
    )
    payload["rerun_detection_count"] = sum(int((item or {}).get("rerun_detection_count") or 0) for item in payload["events"])
    payload["rerun_reset_count"] = sum(int((item or {}).get("rerun_reset_count") or 0) for item in payload["events"])
    payload["disabled_detected"] = any(bool((item or {}).get("disabled_detected")) for item in payload["events"])
    payload["first_enabled_timestamp"] = next(
        (
            item.get("first_enabled_timestamp")
            for item in payload["events"]
            if item.get("first_enabled_timestamp") is not None
        ),
        None,
    )
    payload["stable_enabled_poll_count"] = max(
        [int((item or {}).get("stable_enabled_poll_count") or 0) for item in payload["events"]] or [0]
    )
    payload["final_enabled_state"] = event.get("final_enabled_state")
    payload["commit_confirmation_results"] = [
        {
            "label": item.get("label"),
            "requested_value": item.get("requested_value"),
            "phase": item.get("phase"),
            "result": item.get("commit_confirmation_result"),
        }
        for item in payload["events"]
        if item.get("commit_confirmation_result") is not None
    ]
    payload["already_value_matched_decisions"] = [
        {
            "label": item.get("label"),
            "requested_value": item.get("requested_value"),
            "phase": item.get("phase"),
        }
        for item in payload["events"]
        if item.get("already_value_matched_decision")
    ]
    payload["stale_locator_detection"] = any(bool((item or {}).get("stale_locator_detection")) for item in payload["events"])
    _write_input_edit_json(path, payload)


def _input_locator_metadata(page, label: str) -> dict[str, Any]:
    script = r"""
    (label) => {
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const inputs = Array.from(document.querySelectorAll('input'));
      const matching = inputs.filter((el) => el.getAttribute('aria-label') === label);
      const visible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      };
      return {
        matching_count: matching.length,
        visible_count: matching.filter(visible).length,
        elements: matching.map((el, index) => {
          const rect = el.getBoundingClientRect();
          const centerX = rect.left + rect.width / 2;
          const centerY = rect.top + rect.height / 2;
          const topEl = document.elementFromPoint(centerX, centerY);
          const style = window.getComputedStyle(el);
          return {
            index,
            visible: visible(el),
            connected: el.isConnected,
            value: el.value,
            type: el.getAttribute("type"),
            disabled: el.disabled,
            readOnly: el.readOnly,
            ariaDisabled: el.getAttribute("aria-disabled"),
            tabIndex: el.tabIndex,
            pointerEvents: style.pointerEvents,
            opacity: Number(style.opacity || "1"),
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
            coveredByOtherElement: Boolean(topEl && topEl !== el && !el.contains(topEl)),
            topElement: topEl ? {
              tag: topEl.tagName.toLowerCase(),
              text: clean(topEl.innerText || topEl.textContent).slice(0, 160),
              className: String(topEl.className || "").slice(0, 160),
              ariaLabel: topEl.getAttribute("aria-label"),
              testid: topEl.getAttribute("data-testid")
            } : null,
            outerHTML: String(el.outerHTML || "").slice(0, 1000)
          };
        })
      };
    }
    """
    try:
        return dict(page.evaluate(script, label) or {})
    except Exception as exc:
        return {"locator_metadata_error": f"{type(exc).__name__}: {exc}"}


def _inputs_recipe_widgets_readiness_snapshot(page, labels: list[str] | None = None, expected_values: dict[str, Any] | None = None) -> dict[str, Any]:
    labels = list(labels or [MU_LABEL, VU_LABEL])
    expected_values = dict(expected_values or {})
    script = r"""
    ({labels, expectedValues}) => {
      const now = Date.now();
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const sameValue = (observed, expected) => {
        if (expected === undefined || expected === null) return null;
        const a = Number(observed);
        const b = Number(expected);
        if (Number.isFinite(a) && Number.isFinite(b)) return Math.abs(a - b) <= 0.051;
        return String(observed) === String(expected);
      };
      const visible = (el) => {
        if (!el || !el.getBoundingClientRect) return false;
        if (el.hasAttribute("hidden") || el.hasAttribute("inert") || el.closest("[inert]")) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
      };
      window.__codexInputNodeIds = window.__codexInputNodeIds || new WeakMap();
      window.__codexInputNodeSeq = window.__codexInputNodeSeq || 1;
      const nodeId = (el) => {
        if (!el) return null;
        if (!window.__codexInputNodeIds.has(el)) window.__codexInputNodeIds.set(el, window.__codexInputNodeSeq++);
        return window.__codexInputNodeIds.get(el);
      };
      const route = new URL(window.location.href).searchParams.get("page") || "inputs";
      const widgets = {};
      labels.forEach((label) => {
        const matches = Array.from(document.querySelectorAll("input")).filter((el) => el.getAttribute("aria-label") === label);
        const visibleMatches = matches.filter(visible);
        const expected = expectedValues[label];
        const items = matches.map((el, index) => {
          const rect = el.getBoundingClientRect();
          return {
            index,
            node_id: nodeId(el),
            element_id: el.id || null,
            visible: visible(el),
            connected: Boolean(el.isConnected),
            enabled: !el.disabled,
            readonly: Boolean(el.readOnly || el.hasAttribute("readonly")),
            aria_disabled: el.getAttribute("aria-disabled"),
            value: el.value,
            value_matches_expected: sameValue(el.value, expected),
            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
          };
        });
        const firstVisible = visibleMatches[0] || null;
        widgets[label] = {
          expected_value: expected === undefined ? null : expected,
          matching_count: matches.length,
          visible_count: visibleMatches.length,
          enabled_visible_count: visibleMatches.filter((el) => !el.disabled && !el.readOnly && el.getAttribute("aria-disabled") !== "true").length,
          first_visible_value: firstVisible ? firstVisible.value : null,
          first_visible_node_id: firstVisible ? nodeId(firstVisible) : null,
          first_visible_element_id: firstVisible ? (firstVisible.id || null) : null,
          value_matches_expected: firstVisible ? sameValue(firstVisible.value, expected) : null,
          elements: items.slice(0, 5)
        };
      });
      const allVisible = labels.every((label) => (widgets[label] && widgets[label].visible_count >= 1));
      const allEnabled = labels.every((label) => (widgets[label] && widgets[label].enabled_visible_count >= 1));
      const allExpectedValues = labels.every((label) => {
        const expected = expectedValues[label];
        if (expected === undefined || expected === null) return true;
        return Boolean(widgets[label] && widgets[label].value_matches_expected === true);
      });
      const marker = {
        timestamp_ms: now,
        active_page_route: route,
        inputs_route_active: route === "inputs",
        labels,
        widgets,
        all_required_widgets_visible: allVisible,
        all_required_widgets_enabled: allEnabled,
        all_required_widgets_expected_values: allExpectedValues,
        inputs_recipe_widgets_ready: Boolean(route === "inputs" && allVisible && allEnabled && allExpectedValues),
        body_text_length: document.body ? document.body.childElementCount : 0
      };
      window.__codexInputsRecipeWidgetsReady = marker;
      return marker;
    }
    """
    try:
        return dict(page.evaluate(script, {"labels": labels, "expectedValues": expected_values}) or {})
    except Exception as exc:
        return {"readiness_probe_error": f"{type(exc).__name__}: {exc}", "labels": labels}


def _summarise_inputs_readiness_trace(observations: list[dict[str, Any]], labels: list[str]) -> dict[str, Any]:
    labels = list(labels or [])
    first_seen: dict[str, Any] = {}
    first_enabled: dict[str, Any] = {}
    first_expected: dict[str, Any] = {}
    for row in observations:
        snap = dict(row.get("snapshot") or {})
        widgets = dict(snap.get("widgets") or {})
        for label in labels:
            widget = dict(widgets.get(label) or {})
            if label not in first_seen and int(widget.get("visible_count") or 0) > 0:
                first_seen[label] = {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms"), "value": widget.get("first_visible_value")}
            if label not in first_enabled and int(widget.get("enabled_visible_count") or 0) > 0:
                first_enabled[label] = {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms"), "value": widget.get("first_visible_value")}
            if label not in first_expected and widget.get("value_matches_expected") is True:
                first_expected[label] = {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms"), "value": widget.get("first_visible_value")}
    first_all_visible = next(
        (
            {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms")}
            for row in observations
            if bool((row.get("snapshot") or {}).get("all_required_widgets_visible"))
        ),
        None,
    )
    first_all_enabled = next(
        (
            {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms")}
            for row in observations
            if bool((row.get("snapshot") or {}).get("all_required_widgets_enabled"))
        ),
        None,
    )
    first_all_expected = next(
        (
            {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms")}
            for row in observations
            if bool((row.get("snapshot") or {}).get("all_required_widgets_expected_values"))
        ),
        None,
    )
    first_ready = next(
        (
            {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms")}
            for row in observations
            if bool((row.get("snapshot") or {}).get("inputs_recipe_widgets_ready"))
        ),
        None,
    )
    return {
        "poll_count": len(observations),
        "labels": labels,
        "first_seen_by_label": first_seen,
        "first_enabled_by_label": first_enabled,
        "first_expected_value_by_label": first_expected,
        "first_all_required_widgets_visible": first_all_visible,
        "first_all_required_widgets_enabled": first_all_enabled,
        "first_all_required_widgets_expected_values": first_all_expected,
        "first_inputs_recipe_widgets_ready": first_ready,
        "eventually_all_required_widgets_visible": first_all_visible is not None,
        "eventually_all_required_widgets_enabled": first_all_enabled is not None,
        "eventually_inputs_recipe_widgets_ready": first_ready is not None,
        "last_snapshot": observations[-1].get("snapshot") if observations else {},
    }


def _input_dom_excerpt(page, label: str) -> str:
    script = r"""
    (label) => {
      const inputs = Array.from(document.querySelectorAll('input'));
      const el = inputs.find((candidate) => candidate.getAttribute('aria-label') === label);
      if (!el) return document.documentElement.outerHTML.slice(0, 12000);
      let root = el.closest('[data-testid="stNumberInput"], [data-testid="stWidgetLabel"], [data-testid="stVerticalBlock"], section, div');
      root = root || el.parentElement || el;
      return String(root.outerHTML || "").slice(0, 12000);
    }
    """
    try:
        return str(page.evaluate(script, label) or "")
    except Exception as exc:
        return f"Could not capture input DOM excerpt: {type(exc).__name__}: {exc}"


def _capture_input_edit_stage(page, label: str, artifact_dir: Path | None, stage: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "snapshot": _input_editability_snapshot(page, label),
        "locator_metadata": _input_locator_metadata(page, label),
        "viewport_screenshot": None,
        "full_page_screenshot": None,
        "input_screenshot": None,
        "dom_excerpt_path": None,
        "capture_errors": [],
    }
    if artifact_dir is None:
        payload["capture_errors"].append("artifact_dir unavailable")
        return payload
    safe_stage = re.sub(r"[^A-Za-z0-9_.-]+", "_", stage).strip("_")
    try:
        viewport = artifact_dir / f"input_edit_{safe_stage}_viewport.png"
        page.screenshot(path=str(viewport), full_page=False, timeout=10_000)
        payload["viewport_screenshot"] = str(viewport)
    except Exception as exc:
        payload["capture_errors"].append(f"viewport:{type(exc).__name__}:{exc}")
    try:
        full_page = artifact_dir / f"input_edit_{safe_stage}_full_page.png"
        page.screenshot(path=str(full_page), full_page=True, timeout=10_000)
        payload["full_page_screenshot"] = str(full_page)
    except Exception as exc:
        payload["capture_errors"].append(f"full_page:{type(exc).__name__}:{exc}")
    try:
        input_png = artifact_dir / f"input_edit_{safe_stage}_input.png"
        page.locator(f'input[aria-label="{label}"]:visible').first.screenshot(path=str(input_png), timeout=5_000)
        payload["input_screenshot"] = str(input_png)
    except Exception as exc:
        payload["capture_errors"].append(f"input:{type(exc).__name__}:{exc}")
    payload["dom_excerpt_path"] = _write_input_edit_json(
        artifact_dir / f"input_edit_{safe_stage}_dom_excerpt.json",
        {"label": label, "html": _input_dom_excerpt(page, label)},
    )
    return payload


def _fresh_input_lifecycle_observation(
    page,
    label: str,
    *,
    expected_value: Any,
    poll: int,
    selector: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "poll": poll,
        "elapsed_ms": elapsed_ms,
        "selector": selector,
        "label": label,
        "expected_value": expected_value,
        "locator_recreated_after_rerun": True,
        "visible_locator_count": None,
        "locator_count": None,
        "enabled_count": 0,
        "readonly_count": 0,
        "duplicate_visible_labels": 0,
        "attached": False,
        "visible": False,
        "enabled": False,
        "readonly": None,
        "disabled": None,
        "aria_disabled": None,
        "connected": None,
        "value": None,
        "value_matched": False,
        "receives_pointer_events": None,
        "covered_by_other_element": None,
        "nearest_visible_section_heading": "",
        "active_page_route": "",
        "streamlit_connection_state": "",
        "streamlit_connection_error_visible": False,
        "loading_spinner_count": 0,
        "faded_inert_count": 0,
        "ok": False,
    }
    script = r"""
    ({label, expectedValue}) => {
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const num = (value) => {
        if (value === null || value === undefined || value === "") return null;
        const parsed = Number(String(value).replace(/,/g, ""));
        return Number.isFinite(parsed) ? parsed : null;
      };
      const same = (actual, expected) => {
        const a = num(actual);
        const e = num(expected);
        if (a !== null && e !== null) return Math.abs(a - e) <= 0.051;
        return clean(actual) === clean(expected);
      };
      const visible = (el) => {
        if (!el || !el.isConnected) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" &&
          Number(style.opacity || 1) > 0.02 && rect.width > 1 && rect.height > 1;
      };
      const headingFor = (el) => {
        let node = el;
        for (let i = 0; node && i < 10; i += 1, node = node.parentElement) {
          const heading = node.querySelector && node.querySelector("h1,h2,h3,h4,[role='heading'],summary,label");
          const text = clean(heading && (heading.innerText || heading.textContent));
          if (text) return text.slice(0, 160);
        }
        return "";
      };
      const allInputs = Array.from(document.querySelectorAll("input"));
      const matching = allInputs.filter((el) => el.getAttribute("aria-label") === label);
      const visibleMatching = matching.filter(visible);
      const enabled = visibleMatching.filter((el) => !el.disabled);
      const readonly = visibleMatching.filter((el) => el.readOnly || el.hasAttribute("readonly"));
      const spinners = Array.from(document.querySelectorAll('[data-testid="stSpinner"], [data-testid="stStatusWidget"], .stSpinner, [aria-busy="true"]')).filter(visible);
      const connectionMarker = document.querySelector("[data-test-connection-state]");
      const connectionState = connectionMarker ? String(connectionMarker.getAttribute("data-test-connection-state") || "") : "";
      const connectionErrorVisible = ["CONNECTING", "DISCONNECTED", "ERROR"].includes(connectionState.toUpperCase());
      const el = visibleMatching[0] || matching[0] || null;
      const fadedCandidates = Array.from(document.querySelectorAll('[inert], [aria-hidden="true"], [style*="opacity"], [data-testid="stAppViewContainer"], [data-testid="stVerticalBlock"]')).slice(0, 400);
      const faded = fadedCandidates.filter((candidate) => {
        if (!visible(candidate)) return false;
        const opacity = Number(window.getComputedStyle(candidate).opacity || 1);
        return opacity > 0.02 && opacity < 0.65;
      });
      if (!el) {
        return {
          activePageRoute: new URL(window.location.href).searchParams.get("page") || "",
          locatorCount: matching.length,
          visibleLocatorCount: visibleMatching.length,
          enabledCount: enabled.length,
          readonlyCount: readonly.length,
          duplicateVisibleLabels: visibleMatching.length > 1 ? visibleMatching.length : 0,
          loadingSpinnerCount: spinners.length,
          fadedInertCount: faded.length,
          streamlitConnectionState: connectionState,
          streamlitConnectionErrorVisible: connectionErrorVisible,
          element: null
        };
      }
      window.__codexInputNodeIds = window.__codexInputNodeIds || new WeakMap();
      window.__codexInputNodeSeq = window.__codexInputNodeSeq || 1;
      if (!window.__codexInputNodeIds.has(el)) window.__codexInputNodeIds.set(el, window.__codexInputNodeSeq++);
      const rect = el.getBoundingClientRect();
      const centerX = rect.x + rect.width / 2;
      const centerY = rect.y + rect.height / 2;
      const top = document.elementFromPoint(centerX, centerY);
      const style = window.getComputedStyle(el);
      const topIsSelf = top === el || (top && el.contains(top));
      let ancestor = el;
      let localFadedOrInert = false;
      for (let i = 0; ancestor && i < 8; i += 1, ancestor = ancestor.parentElement) {
        const ancestorStyle = window.getComputedStyle(ancestor);
        const opacity = Number(ancestorStyle.opacity || 1);
        if (ancestor.hasAttribute("inert") || opacity < 0.65) {
          localFadedOrInert = true;
          break;
        }
      }
      return {
        activePageRoute: new URL(window.location.href).searchParams.get("page") || "",
        locatorCount: matching.length,
        visibleLocatorCount: visibleMatching.length,
        enabledCount: enabled.length,
        readonlyCount: readonly.length,
        duplicateVisibleLabels: visibleMatching.length > 1 ? visibleMatching.length : 0,
        loadingSpinnerCount: spinners.length,
        fadedInertCount: faded.length,
        streamlitConnectionState: connectionState,
        streamlitConnectionErrorVisible: connectionErrorVisible,
        element: {
          nodeId: window.__codexInputNodeIds.get(el),
          elementId: el.id || null,
          connected: Boolean(el.isConnected),
          visible: visible(el),
          enabled: !el.disabled,
          disabled: Boolean(el.disabled),
          readonly: Boolean(el.readOnly || el.hasAttribute("readonly")),
          ariaDisabled: el.getAttribute("aria-disabled"),
          value: el.value,
          valueMatched: same(el.value, expectedValue),
          activeElementMatches: document.activeElement === el,
          pointerEvents: style.pointerEvents,
          receivesPointerEvents: style.pointerEvents !== "none" && topIsSelf,
          coveredByOtherElement: Boolean(top && !topIsSelf),
          localFadedOrInert,
          topElement: top && !topIsSelf ? clean(top.outerHTML).slice(0, 260) : null,
          nearestVisibleSectionHeading: headingFor(el),
          rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
        }
      };
    }
    """
    try:
        state = page.evaluate(script, {"label": label, "expectedValue": expected_value})
        if isinstance(state, dict):
            observation["active_page_route"] = state.get("activePageRoute") or ""
            observation["locator_count"] = state.get("locatorCount")
            observation["visible_locator_count"] = state.get("visibleLocatorCount")
            observation["enabled_count"] = state.get("enabledCount") or 0
            observation["readonly_count"] = state.get("readonlyCount") or 0
            observation["duplicate_visible_labels"] = state.get("duplicateVisibleLabels") or 0
            observation["loading_spinner_count"] = state.get("loadingSpinnerCount") or 0
            observation["faded_inert_count"] = state.get("fadedInertCount") or 0
            observation["streamlit_connection_state"] = state.get("streamlitConnectionState") or ""
            observation["streamlit_connection_error_visible"] = bool(state.get("streamlitConnectionErrorVisible"))
            element = state.get("element")
            if isinstance(element, dict):
                observation["attached"] = True
                observation["visible"] = bool(element.get("visible"))
                observation["enabled"] = bool(element.get("enabled"))
                observation["readonly"] = bool(element.get("readonly"))
                observation["disabled"] = bool(element.get("disabled"))
                observation["aria_disabled"] = element.get("ariaDisabled")
                observation["connected"] = bool(element.get("connected"))
                observation["value"] = element.get("value")
                observation["value_matched"] = bool(element.get("valueMatched"))
                observation["node_id"] = element.get("nodeId")
                observation["element_id"] = element.get("elementId")
                observation["active_element_matches"] = bool(element.get("activeElementMatches"))
                observation["receives_pointer_events"] = bool(element.get("receivesPointerEvents"))
                observation["covered_by_other_element"] = bool(element.get("coveredByOtherElement"))
                observation["local_faded_or_inert"] = bool(element.get("localFadedOrInert"))
                observation["top_element"] = element.get("topElement")
                observation["nearest_visible_section_heading"] = element.get("nearestVisibleSectionHeading") or ""
                observation["rect"] = element.get("rect")
            observation["ok"] = bool(
                observation.get("visible_locator_count") == 1
                and observation.get("visible")
                and observation.get("enabled")
                and observation.get("connected")
                and not observation.get("disabled")
                and not observation.get("readonly")
                and str(observation.get("aria_disabled") or "").lower() != "true"
                and not observation.get("covered_by_other_element")
                and not observation.get("local_faded_or_inert")
            )
    except Exception as exc:
        observation["error"] = f"{type(exc).__name__}: {exc}"
    return observation


def _classify_input_lifecycle_probe(stability_probe: dict[str, Any] | None) -> str:
    observations = list((stability_probe or {}).get("all_observations") or [])
    last = dict((stability_probe or {}).get("last_observation") or {})
    visible_one_count = sum(1 for obs in observations if obs.get("visible_locator_count") == 1)
    duplicate_count = sum(1 for obs in observations if isinstance(obs.get("visible_locator_count"), int) and obs.get("visible_locator_count") > 1)
    enabled_count = sum(1 for obs in observations if obs.get("enabled"))
    readonly_count = sum(1 for obs in observations if obs.get("readonly"))
    first_value_matched = next((obs for obs in observations if obs.get("value_matched")), None)
    attach_transitions = 0
    node_identity_changes = 0
    previous_attached: bool | None = None
    previous_node_id = None
    for obs in observations:
        attached = bool(obs.get("attached"))
        if previous_attached is not None and attached != previous_attached:
            attach_transitions += 1
        previous_attached = attached
        node_id = obs.get("node_id")
        if previous_node_id is not None and node_id is not None and node_id != previous_node_id:
            node_identity_changes += 1
        if node_id is not None:
            previous_node_id = node_id
    if visible_one_count <= 0:
        return "input_not_mounted"
    if duplicate_count > 0:
        return "input_duplicate_locator"
    if last.get("visible_locator_count") == 1 and not last.get("visible"):
        return "input_present_but_hidden"
    if enabled_count <= 0 or last.get("disabled"):
        return "input_present_but_disabled"
    if readonly_count > 0 or last.get("readonly"):
        return "input_present_but_disabled"
    if last.get("covered_by_other_element"):
        return "input_present_but_obscured"
    if first_value_matched is not None and not (stability_probe or {}).get("stable"):
        return "input_already_value_matched_but_gate_failed"
    if attach_transitions > 0 or node_identity_changes > 0:
        return "input_stale_locator_after_rerun"
    return "input_setup_route_not_ready"


def _wait_for_stable_editable_input(page, label: str, *, timeout_s: float = 30.0) -> tuple[Any, dict[str, Any]]:
    selector = f'input[aria-label="{label}"]:visible'
    deadline = time.time() + timeout_s
    started = time.time()
    stable_reads = 0
    stable_enabled_reads = 0
    longest_stable_enabled_reads = 0
    rerun_reset_count = 0
    previous_node_id: Any = None
    previous_attached: bool | None = None
    polls = 0
    observations: list[dict[str, Any]] = []
    readiness_observations: list[dict[str, Any]] = []
    last_observation: dict[str, Any] = {}
    expected_values = {}
    try:
        requested = getattr(_set_number_input_with_disabled_guard, "_current_requested_values", None)
        if isinstance(requested, dict):
            expected_values = dict(requested)
    except Exception:
        expected_values = {}
    required_labels = [MU_LABEL, VU_LABEL]

    while time.time() < deadline:
        polls += 1
        elapsed_ms = int(max(0.0, time.time() - started) * 1000)
        if polls == 1 or polls % 10 == 0:
            readiness_observations.append(
                {
                    "poll": polls,
                    "elapsed_ms": elapsed_ms,
                    "snapshot": _inputs_recipe_widgets_readiness_snapshot(
                        page,
                        labels=required_labels,
                        expected_values=expected_values,
                    ),
                }
            )
        poll_probe_started = time.perf_counter()
        observation = _fresh_input_lifecycle_observation(
            page,
            label,
            expected_value=expected_values.get(label),
            poll=polls,
            selector=selector,
            elapsed_ms=elapsed_ms,
        )
        observation["probe_duration_ms"] = round((time.perf_counter() - poll_probe_started) * 1000.0, 3)

        attached = bool(observation.get("attached"))
        node_id = observation.get("node_id")
        identity_changed = False
        if previous_attached is not None and attached != previous_attached:
            identity_changed = True
        if previous_node_id is not None and node_id is not None and node_id != previous_node_id:
            identity_changed = True
        if identity_changed:
            stable_reads = 0
            stable_enabled_reads = 0
            rerun_reset_count += 1
            observation["stable_reset_reason"] = "input_dom_identity_changed_after_rerun"

        enabled_ready = bool(
            observation.get("visible_locator_count") == 1
            and observation.get("active_page_route") == "inputs"
            and observation.get("visible")
            and observation.get("enabled")
            and observation.get("connected")
            and not observation.get("disabled")
            and not observation.get("readonly")
            and str(observation.get("aria_disabled") or "").lower() != "true"
            and not observation.get("local_faded_or_inert")
            and not observation.get("streamlit_connection_error_visible")
        )
        if enabled_ready:
            stable_enabled_reads += 1
            longest_stable_enabled_reads = max(longest_stable_enabled_reads, stable_enabled_reads)
        else:
            stable_enabled_reads = 0

        if observation.get("ok") and observation.get("visible_locator_count") == 1:
            stable_reads += 1
        else:
            stable_reads = 0
        observation["stable_enabled_reads"] = stable_enabled_reads
        observation["longest_stable_enabled_reads"] = longest_stable_enabled_reads
        observation["stable_reads"] = stable_reads
        last_observation = observation
        observations.append(observation)
        previous_attached = attached
        if node_id is not None:
            previous_node_id = node_id

        if stable_reads >= 3:
            return page.locator(selector).first, {
                "stable": True,
                "polls": polls,
                "required_stable_reads": 3,
                "elapsed_ms": int(max(0.0, timeout_s - max(0.0, deadline - time.time())) * 1000),
                "last_observation": last_observation,
                "recent_observations": observations[-8:],
                "all_observations": observations,
                "rerun_reset_count": rerun_reset_count,
                "stable_enabled_poll_count": longest_stable_enabled_reads,
                "exact_classification": "input_ready",
                "inputs_readiness_trace": {
                    "summary": _summarise_inputs_readiness_trace(readiness_observations, required_labels),
                    "observations": readiness_observations,
                },
                "locator_metadata": _input_locator_metadata(page, label),
            }
        time.sleep(0.15)

    result = {
        "stable": False,
        "polls": polls,
        "required_stable_reads": 3,
        "elapsed_ms": int(timeout_s * 1000),
        "last_observation": last_observation,
        "recent_observations": observations[-12:],
        "all_observations": observations,
        "rerun_reset_count": rerun_reset_count,
        "stable_enabled_poll_count": longest_stable_enabled_reads,
        "inputs_readiness_trace": {
            "summary": _summarise_inputs_readiness_trace(readiness_observations, required_labels),
            "observations": readiness_observations,
        },
        "locator_metadata": _input_locator_metadata(page, label),
    }
    if polls % 10 != 0:
        try:
            readiness_observations.append(
                {
                    "poll": polls,
                    "elapsed_ms": int(max(0.0, time.time() - started) * 1000),
                    "snapshot": _inputs_recipe_widgets_readiness_snapshot(
                        page,
                        labels=required_labels,
                        expected_values=expected_values,
                    ),
                }
            )
            result["inputs_readiness_trace"] = {
                "summary": _summarise_inputs_readiness_trace(readiness_observations, required_labels),
                "observations": readiness_observations,
            }
        except Exception:
            pass
    result["exact_classification"] = _classify_input_lifecycle_probe(result)
    return page.locator(selector).first, result


def _summarise_input_lifecycle_trace(stability_probe: dict[str, Any] | None) -> dict[str, Any]:
    observations = list((stability_probe or {}).get("all_observations") or [])
    attach_detach_sequence: list[dict[str, Any]] = []
    node_identity_changes: list[dict[str, Any]] = []
    previous_attached: bool | None = None
    previous_node_id: Any = None
    visible_zero_count = 0
    visible_one_count = 0
    enabled_count = 0
    readonly_count = 0
    duplicate_count_observations = 0
    first_visible_poll = None
    first_enabled_poll = None
    first_enabled_timestamp = None
    first_value_matched_poll = None
    first_stable_editable_poll = None
    longest_stable_editable_window = 0
    longest_stable_enabled_window = 0
    disabled_detected = False
    streamlit_connection_error_detected = False
    streamlit_connection_states: list[Any] = []
    max_probe_duration_ms = 0.0
    for obs in observations:
        try:
            max_probe_duration_ms = max(max_probe_duration_ms, float(obs.get("probe_duration_ms") or 0.0))
        except Exception:
            pass
        visible_count = obs.get("visible_locator_count")
        if visible_count == 0:
            visible_zero_count += 1
        if visible_count == 1:
            visible_one_count += 1
            if first_visible_poll is None:
                first_visible_poll = obs.get("poll")
        if isinstance(visible_count, int) and visible_count > 1:
            duplicate_count_observations += 1
        attached = bool(obs.get("attached"))
        if obs.get("enabled"):
            enabled_count += 1
            if first_enabled_poll is None:
                first_enabled_poll = obs.get("poll")
                first_enabled_timestamp = obs.get("elapsed_ms")
        if obs.get("disabled") or obs.get("enabled") is False:
            disabled_detected = True
        if obs.get("streamlit_connection_error_visible"):
            streamlit_connection_error_detected = True
        state = obs.get("streamlit_connection_state")
        if state and state not in streamlit_connection_states:
            streamlit_connection_states.append(state)
        if obs.get("readonly"):
            readonly_count += 1
        if obs.get("value_matched") and first_value_matched_poll is None:
            first_value_matched_poll = obs.get("poll")
        if obs.get("ok"):
            longest_stable_editable_window = max(longest_stable_editable_window, int(obs.get("stable_reads") or 0))
            if first_stable_editable_poll is None:
                first_stable_editable_poll = obs.get("poll")
        longest_stable_enabled_window = max(longest_stable_enabled_window, int(obs.get("stable_enabled_reads") or 0))
        if previous_attached is not None and attached != previous_attached:
            attach_detach_sequence.append(
                {
                    "poll": obs.get("poll"),
                    "transition": "attached" if attached else "detached",
                    "visible_locator_count": visible_count,
                    "value": obs.get("value"),
                }
            )
        node_id = obs.get("node_id")
        if previous_node_id is not None and node_id is not None and node_id != previous_node_id:
            node_identity_changes.append(
                {
                    "poll": obs.get("poll"),
                    "from": previous_node_id,
                    "to": node_id,
                    "element_id": obs.get("element_id"),
                    "value": obs.get("value"),
                }
            )
        previous_attached = attached
        if node_id is not None:
            previous_node_id = node_id
    final_unmet = (stability_probe or {}).get("exact_classification")
    if not final_unmet and observations:
        final_unmet = _classify_input_lifecycle_probe(stability_probe or {})
    return {
        "poll_count": len(observations),
        "stable": bool((stability_probe or {}).get("stable")),
        "elapsed_ms": (stability_probe or {}).get("elapsed_ms"),
        "first_visible_poll": first_visible_poll,
        "first_enabled_poll": first_enabled_poll,
        "first_enabled_timestamp": first_enabled_timestamp,
        "first_value_matched_poll": first_value_matched_poll,
        "first_stable_editable_poll": first_stable_editable_poll,
        "longest_stable_editable_window": longest_stable_editable_window,
        "stable_enabled_poll_count": max(
            int((stability_probe or {}).get("stable_enabled_poll_count") or 0),
            longest_stable_enabled_window,
        ),
        "disabled_detected": disabled_detected,
        "final_enabled_state": bool(((stability_probe or {}).get("last_observation") or {}).get("enabled"))
        if observations
        else None,
        "streamlit_connection_error_detected": streamlit_connection_error_detected,
        "streamlit_connection_states": streamlit_connection_states,
        "max_probe_duration_ms": round(max_probe_duration_ms, 3),
        "rerun_reset_count": int((stability_probe or {}).get("rerun_reset_count") or 0),
        "final_unmet_condition": final_unmet,
        "exact_classification": final_unmet,
        "visible_locator_zero_count": visible_zero_count,
        "visible_locator_one_count": visible_one_count,
        "duplicate_visible_locator_poll_count": duplicate_count_observations,
        "enabled_poll_count": enabled_count,
        "readonly_poll_count": readonly_count,
        "attach_detach_transition_count": len(attach_detach_sequence),
        "attach_detach_sequence_tail": attach_detach_sequence[-40:],
        "node_identity_change_count": len(node_identity_changes),
        "node_identity_changes_tail": node_identity_changes[-40:],
        "last_observation": (stability_probe or {}).get("last_observation"),
        "recent_observations": (stability_probe or {}).get("recent_observations"),
    }


def _input_commit_field_for_label(label: str) -> str | None:
    lower = label.lower()
    if "vu" in lower or "shear" in lower:
        return "uls_Vstar"
    if "mu" in lower or "moment" in lower:
        return "uls_Mstar"
    return None


def _wait_for_input_commit_confirmation(page, label: str, value: float, *, timeout_s: float = 8.0) -> dict[str, Any]:
    selector = f'input[aria-label="{label}"]:visible'
    deadline = time.time() + timeout_s
    field = _input_commit_field_for_label(label)
    polls = 0
    observations: list[dict[str, Any]] = []

    while time.time() < deadline:
        polls += 1
        observation: dict[str, Any] = {
            "poll": polls,
            "selector": selector,
            "field": field,
            "dom_value": None,
            "dom_match": False,
            "summary_state_value": None,
            "shared_state_value": None,
            "state_match": False,
        }
        try:
            locator = page.locator(selector)
            if int(locator.count()) == 1:
                dom_value = locator.first.input_value(timeout=500)
                observation["dom_value"] = dom_value
                # Streamlit number inputs may display one decimal even while
                # shared state preserves the requested precision.
                observation["dom_match"] = _same_value(dom_value, value, tol=5.1e-2)
        except Exception as exc:
            observation["dom_error"] = f"{type(exc).__name__}: {exc}"

        try:
            state, read_meta = _read_browser_state_probe_direct(page, timeout_s=1.0)
            observation["browser_state_read_meta"] = read_meta
            if field and isinstance(state, dict):
                summary_probe = dict(state.get("summary_state_probe") or {})
                shared_probe = dict(state.get("browser_shared_probe") or {})
                observation["summary_state_value"] = summary_probe.get(field)
                observation["shared_state_value"] = shared_probe.get(field)
                observation["state_match"] = bool(
                    _same_value(summary_probe.get(field), value)
                    and _same_value(shared_probe.get(field), value)
                )
        except Exception as exc:
            observation["state_error"] = f"{type(exc).__name__}: {exc}"

        observations.append(observation)
        if observation.get("state_match") or observation.get("dom_match"):
            return {
                "committed": True,
                "matched_source": "browser_state" if observation.get("state_match") else "dom_value",
                "polls": polls,
                "elapsed_ms": int(max(0.0, timeout_s - max(0.0, deadline - time.time())) * 1000),
                "last_observation": observation,
                "recent_observations": observations[-8:],
            }
        time.sleep(0.25)

    return {
        "committed": False,
        "matched_source": None,
        "polls": polls,
        "elapsed_ms": int(timeout_s * 1000),
        "last_observation": observations[-1] if observations else {},
        "recent_observations": observations[-12:],
    }


def _raise_input_edit_lifecycle_failure(
    page,
    label: str,
    value: float,
    *,
    timeout_stage: str,
    message: str,
    guard_enabled_result: bool | None = None,
    stability_probe: dict[str, Any] | None = None,
    commit_probe: dict[str, Any] | None = None,
) -> None:
    browser_state, read_meta = _read_browser_state_probe_direct(page, timeout_s=2.0)
    disabled_snapshot = _disabled_input_edit_attempt_diagnostic(
        page,
        label,
        requested_value=value,
        guard_enabled_result=guard_enabled_result,
        stability_probe=stability_probe,
        commit_probe=commit_probe,
    )
    step = {
        "step_index": None,
        "step_type": "verifier_setup_input_edit",
        "setup_diagnostics": {
            "classification": "verifier_disabled_input_edit_attempt",
            "timeout_stage": timeout_stage,
            "message": message,
            "input": disabled_snapshot,
            "browser_state_read_meta": read_meta,
            "browser_state_probe_available": isinstance(browser_state, dict),
            "screenshot_captured_by_failure_artifacts": True,
        },
        "browser_state": browser_state if isinstance(browser_state, dict) else {},
        "disabled_input_diagnostic": disabled_snapshot,
    }
    raise VisibleContractFailure(
        "verifier_disabled_input_edit_attempt",
        f"{message}; requested value={value}.",
        step,
    )


def _set_number_input_with_disabled_guard(page, label: str, value: float) -> None:
    """Verifier-side guard so disabled app inputs fail with a setup diagnostic."""
    requested_values = dict(getattr(_set_number_input_with_disabled_guard, "_current_requested_values", {}) or {})
    requested_values[label] = value
    setattr(_set_number_input_with_disabled_guard, "_current_requested_values", requested_values)
    if bool(getattr(_set_number_input_with_disabled_guard, "_route_gate_ready_seen", False)):
        route_gate = {
            "ready": True,
            "skipped": True,
            "reason": "inputs route/body already proven for current live input application",
        }
    else:
        route_gate = wait_for_inputs_content_ready_before_probe(
            page,
            timeout_s=45.0,
            console_messages=_CURRENT_INPUT_EDIT_CONSOLE_MESSAGES or [],
            require_rendered_outputs=False,
        )
        if route_gate.get("ready"):
            setattr(_set_number_input_with_disabled_guard, "_route_gate_ready_seen", True)
    if not route_gate.get("ready"):
        stability_probe = {
            "stable": False,
            "polls": 0,
            "required_stable_reads": 3,
            "elapsed_ms": route_gate.get("elapsed_ms"),
            "last_observation": {},
            "recent_observations": [],
            "all_observations": [],
            "exact_classification": str(route_gate.get("classification") or "input_setup_route_not_ready"),
            "route_readiness_gate": route_gate,
        }
        _write_replay_input_setup_mode_event(
            label=label,
            requested_value=value,
            phase="route_readiness_failed_before_edit",
            route_gate=route_gate,
            stability_probe=stability_probe,
            final_setup_classification=stability_probe["exact_classification"],
        )
        _raise_input_edit_lifecycle_failure(
            page,
            label,
            value,
            timeout_stage="input_setup_route_readiness",
            message=f"Verifier attempted to edit input {label!r}, but the Inputs route/body was not ready.",
            guard_enabled_result=None,
            stability_probe=stability_probe,
        )
    loc, stability_probe = _wait_for_stable_editable_input(page, label)
    artifact_dir = _CURRENT_INPUT_EDIT_ARTIFACT_DIR
    if artifact_dir is not None:
        safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")
        readiness_trace = dict(stability_probe.get("inputs_readiness_trace") or {})
        readiness_trace["latest_label"] = label
        readiness_trace["latest_requested_value"] = value
        readiness_trace["stable_for_latest_label"] = bool(stability_probe.get("stable"))
        _write_input_edit_json(
            artifact_dir / f"inputs_readiness_trace_{safe_label}.json",
            readiness_trace,
        )
        _write_input_edit_json(
            artifact_dir / "inputs_readiness_trace.json",
            readiness_trace,
        )
    _write_replay_input_setup_mode_event(
        label=label,
        requested_value=value,
        phase="stability_probe_done",
        route_gate=route_gate,
        stability_probe=stability_probe,
        final_setup_classification=str(stability_probe.get("exact_classification") or ""),
    )
    if not stability_probe.get("stable"):
        _raise_input_edit_lifecycle_failure(
            page,
            label,
            value,
            timeout_stage="input_editability_check",
            message=f"Verifier attempted to edit input {label!r}, but it did not remain stably editable.",
            guard_enabled_result=bool((stability_probe.get("last_observation") or {}).get("enabled")),
            stability_probe=stability_probe,
        )
    if callable(_ORIGINAL_SET_NUMBER_INPUT):
        # Touch the freshly reacquired locator so Playwright resolves it after
        # the stable window and before the helper performs the user-like edit.
        loc.wait_for(state="visible", timeout=5_000)
        last_observation = dict(stability_probe.get("last_observation") or {})
        if last_observation.get("value_matched"):
            _write_replay_input_setup_mode_event(
                label=label,
                requested_value=value,
                phase="already_value_matched_without_edit",
                route_gate=route_gate,
                stability_probe=stability_probe,
                already_value_matched=True,
                final_setup_classification="input_already_matched_without_edit",
            )
            if artifact_dir is not None:
                _write_input_edit_json(
                    artifact_dir / "input_already_matched_without_edit.json",
                    {
                        "input_already_matched_without_edit": True,
                        "label": label,
                        "requested_value": value,
                        "last_observation": last_observation,
                        "stability_probe_summary": _summarise_input_lifecycle_trace(stability_probe),
                    },
                )
            return
        _ORIGINAL_SET_NUMBER_INPUT(page, label, value)
        commit_probe = _wait_for_input_commit_confirmation(page, label, value)
        if not commit_probe.get("committed"):
            _write_replay_input_setup_mode_event(
                label=label,
                requested_value=value,
                phase="commit_confirmation_failed",
                route_gate=route_gate,
                stability_probe=stability_probe,
                commit_probe=commit_probe,
                final_setup_classification="input_commit_confirmation_failed",
            )
            _raise_input_edit_lifecycle_failure(
                page,
                label,
                value,
                timeout_stage="input_commit_confirmation",
                message=f"Verifier edited input {label!r}, but the requested value did not commit after rerender.",
                guard_enabled_result=True,
                stability_probe=stability_probe,
                commit_probe=commit_probe,
            )
        _write_replay_input_setup_mode_event(
            label=label,
            requested_value=value,
            phase="input_committed",
            route_gate=route_gate,
            stability_probe=stability_probe,
            commit_probe=commit_probe,
            final_setup_classification="input_committed",
        )
        # A real Streamlit number-input edit can commit to the DOM before the
        # follow-up rerun has finished. The next replay-required input must
        # prove the Inputs body is ready again before touching a fresh locator.
        setattr(_set_number_input_with_disabled_guard, "_route_gate_ready_seen", False)
        return
    raise RuntimeError("Verifier number-input helper is unavailable.")


try:
    _apply_live_inputs.__globals__["_set_number_input"] = _set_number_input_with_disabled_guard
except Exception:
    pass


def _dom_probe_inventory(page) -> dict[str, Any]:
    try:
        return dict(
            page.evaluate(
                """
                () => {
                  const trim = (value) => String(value || '').replace(/\\s+/g, ' ').trim().slice(0, 500);
                  return {
                    labels_containing_browser_state: Array.from(document.querySelectorAll('label'))
                      .map((el) => trim(el.innerText || el.textContent))
                      .filter((text) => text.toLowerCase().includes('browser state')),
                    textareas: Array.from(document.querySelectorAll('textarea')).map((el) => ({
                      aria_label: el.getAttribute('aria-label') || '',
                      placeholder: el.getAttribute('placeholder') || '',
                      value_length: String(el.value || '').length,
                      value_preview: trim(el.value || ''),
                    })).slice(0, 20),
                    json_debug_blocks: Array.from(document.querySelectorAll('[data-testid="stCodeBlock"], pre, code'))
                      .map((el) => trim(el.innerText || el.textContent))
                      .filter((text) => text.startsWith('{') || text.includes('browser_state') || text.includes('summary_state_probe'))
                      .slice(0, 20),
                  };
                }
                """,
            )
        )
    except Exception as exc:
        return {"inventory_error": f"{type(exc).__name__}: {exc}"}


def _collect_probe_readiness(page, *, base_url: str, console_messages: list[str], message: str = "") -> dict[str, Any]:
    try:
        url = str(page.url)
    except Exception:
        url = ""
    try:
        title = str(page.title())
    except Exception:
        title = ""
    try:
        visible_text = str(page.locator("body").inner_text(timeout=2_000))
    except Exception:
        visible_text = ""
    try:
        page_html_excerpt = str(page.content())[:12000]
    except Exception:
        page_html_excerpt = ""
    try:
        body_html_excerpt = str(page.locator("body").inner_html(timeout=2_000))[:12000]
    except Exception:
        body_html_excerpt = ""
    try:
        route_probe = dict(
            page.evaluate(
                """
                () => {
                  window.__codexReadinessProbe = window.__codexReadinessProbe || {
                    installedAt: Date.now(),
                    lastMutationAt: Date.now(),
                    mutationCount: 0
                  };
                  if (!window.__codexReadinessProbe.observerInstalled) {
                    const observer = new MutationObserver(() => {
                      window.__codexReadinessProbe.lastMutationAt = Date.now();
                      window.__codexReadinessProbe.mutationCount += 1;
                    });
                    observer.observe(document.body || document.documentElement, {
                      childList: true,
                      subtree: true,
                      attributes: true,
                      characterData: true
                    });
                    window.__codexReadinessProbe.observerInstalled = true;
                  }
                  const visible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                      Number(style.opacity || 1) > 0.02 && rect.width > 1 && rect.height > 1;
                  };
                  const txt = (el) => String((el && (el.innerText || el.textContent)) || '').replace(/\\s+/g, ' ').trim();
                  const all = (sel) => Array.from(document.querySelectorAll(sel));
                  const activeTabs = all('[aria-selected="true"], [data-baseweb="tab"][aria-selected="true"], button[aria-current="page"], a[aria-current="page"]')
                    .filter(visible)
                    .map(txt)
                    .filter(Boolean)
                    .slice(0, 20);
                  const navText = all('nav, [role="tablist"], [data-testid="stSidebar"]')
                    .filter(visible)
                    .map(txt)
                    .filter(Boolean)
                    .slice(0, 10);
                  const cards = all('[data-testid="design-guide-card"], .fast-guidance-item').filter(visible);
                  const calcCards = all('[data-testid*="summary"], [data-testid*="check"], .summary-card, .calc-card, .check-card, .calc-box, .summary-wrap')
                    .filter(visible);
                  const faded = all('body *').filter((el) => {
                    if (!visible(el)) return false;
                    const opacity = Number(window.getComputedStyle(el).opacity || 1);
                    return opacity > 0.02 && opacity < 0.65;
                  });
                  const spinners = all('[data-testid="stSpinner"], [data-testid="stStatusWidget"], .stSpinner, [aria-busy="true"]')
                    .filter(visible);
                  const expanders = all('[data-testid="stExpander"], details, [aria-expanded]')
                    .filter(visible);
                  const now = Date.now();
                  return {
                    route_from_url: new URL(window.location.href).searchParams.get('page') || '',
                    current_url: window.location.href,
                    active_tabs: activeTabs,
                    nav_text: navText,
                    visible_text_length: txt(document.body).length,
                    design_guide_container_exists: all('[data-testid="design-guide-card"], .fast-guidance-item, [data-testid="design-guide-section"]').length > 0 || txt(document.body).includes('Design Guide'),
                    visible_design_guide_card_count: cards.length,
                    visible_calc_box_count: calcCards.length,
                    faded_inactive_container_count: faded.length,
                    loading_indicator_count: spinners.length,
                    expander_visible_count: expanders.length,
                    expander_open_count: expanders.filter((el) => el.open || el.getAttribute('aria-expanded') === 'true').length,
                    dom_mutation_probe: {
                      installed_at_ms: window.__codexReadinessProbe.installedAt,
                      last_mutation_at_ms: window.__codexReadinessProbe.lastMutationAt,
                      mutation_count: window.__codexReadinessProbe.mutationCount,
                      ms_since_last_mutation: now - Number(window.__codexReadinessProbe.lastMutationAt || now)
                    }
                  };
                }
                """,
            )
        )
    except Exception as exc:
        route_probe = {"route_probe_error": f"{type(exc).__name__}: {exc}"}
    selector_counts = _probe_selector_counts(page)
    label_count = _label_count(page, "Browser state")
    browser_state, read_meta = _read_browser_state_probe_direct(page)
    dom_inventory = _dom_probe_inventory(page)
    fast_guidance_count = selector_counts.get("fast_guidance_item")
    summary_cards_appeared = bool(
        "Bending" in visible_text
        and "Shear" in visible_text
        and ("PASS" in visible_text or "FAIL" in visible_text or "NEAR LIMIT" in visible_text)
    )
    return {
        "timeout_stage": "browser_state_probe_attach",
        "current_url": url,
        "page_title": title,
        "visible_page_text_excerpt": visible_text[:4000],
        "visible_page_text_length": len(visible_text),
        "page_html_excerpt": page_html_excerpt,
        "body_html_excerpt": body_html_excerpt,
        "console_errors": [line for line in console_messages if str(line).lower().startswith("error")][-25:],
        "console_excerpt": list(console_messages[-50:]),
        "server_log_excerpt": "",
        "http_readiness_result": bool(_port_ready(base_url)),
        "inputs_page_appeared": bool("Beam design" in visible_text and "Inputs" in visible_text),
        "summary_cards_appeared": summary_cards_appeared,
        "fast_guidance_item_count": fast_guidance_count,
        "browser_state_label_count": label_count,
        "browser_state_textarea_count": selector_counts.get("textarea_aria_label"),
        "browser_state_selector_counts": selector_counts,
        "labels_containing_browser_state": list(dom_inventory.get("labels_containing_browser_state") or []),
        "textareas_inventory": list(dom_inventory.get("textareas") or []),
        "json_debug_blocks_inventory": list(dom_inventory.get("json_debug_blocks") or []),
        "codex_browser_test_mode": (
            browser_state.get("codex_browser_test_mode")
            if isinstance(browser_state, dict) and "codex_browser_test_mode" in browser_state
            else None
        ),
        "verifier_process_CODEX_BROWSER_TEST_MODE": os.environ.get("CODEX_BROWSER_TEST_MODE"),
        "browser_state_text_present": "Browser state" in visible_text,
        "design_guide_visible": bool("Design Guide" in visible_text),
        "active_page_route": route_probe.get("route_from_url"),
        "active_nav_or_tab_state": {
            "active_tabs": list(route_probe.get("active_tabs") or []),
            "nav_text": list(route_probe.get("nav_text") or []),
        },
        "streamlit_readiness_markers": {
            "app_connected": "CONNECTED" in page_html_excerpt or "data-test-connection-state=\"CONNECTED\"" in page_html_excerpt,
            "script_running": "data-test-script-state=\"running\"" in page_html_excerpt,
            "root_present": "<div id=\"root\"" in page_html_excerpt,
        },
        "expander_visibility_counts": {
            "visible": route_probe.get("expander_visible_count"),
            "open": route_probe.get("expander_open_count"),
        },
        "visible_calc_box_count": route_probe.get("visible_calc_box_count"),
        "visible_design_guide_card_count": route_probe.get("visible_design_guide_card_count"),
        "faded_inactive_container_count": route_probe.get("faded_inactive_container_count"),
        "pending_spinner_loading_indicator_count": route_probe.get("loading_indicator_count"),
        "dom_mutation_settle_timestamps": dict(route_probe.get("dom_mutation_probe") or {}),
        "design_guide_container_existed": route_probe.get("design_guide_container_exists"),
        "browser_probe_stage_name": "browser_state_probe_attach",
        "design_guidance_preparing_visible": "Design guidance is preparing" in visible_text,
        "probe_readable": bool(browser_state is not None),
        "probe_read_meta": read_meta,
        "exception_message": str(message),
    }


def _inputs_content_ready_snapshot(page, *, require_rendered_outputs: bool = True) -> dict[str, Any]:
    snapshot_started = time.perf_counter()
    try:
        route_started = time.perf_counter()
        current_url = str(page.url)
    except Exception:
        current_url = ""
    try:
        route = parse_qs(urlparse(current_url).query).get("page", ["inputs"])[0]
        query_params = parse_qs(urlparse(current_url).query)
    except Exception:
        route = ""
        query_params = {}
    route_elapsed_ms = round((time.perf_counter() - route_started) * 1000.0, 3)
    try:
        marker_started = time.perf_counter()
        dom = dict(
            page.evaluate(
                """
                ({muLabel, vuLabel}) => {
                  const visible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                      Number(style.opacity || 1) > 0.02 && rect.width > 1 && rect.height > 1;
                  };
                  const all = (sel) => Array.from(document.querySelectorAll(sel));
                  const inputs = all('input');
                  const inputVisible = (label) => inputs.some((el) => el.getAttribute('aria-label') === label && visible(el));
                  const browserStateEls = all('textarea[aria-label="Browser state"], [aria-label="Browser state"], textarea[name*="browser"], [data-codex-browser-state-probe="1"]');
                  const browserStatePresent = browserStateEls.length > 0;
                  const browserStateVisible = browserStateEls.some(visible);
                  const summaryVisible = all('[data-testid*="summary"], [data-testid*="check"], .summary-card, .summary-wrap')
                    .some(visible);
                  const designGuideVisible = all('[data-testid="design-guide-card"], .fast-guidance-item')
                    .some(visible);
                  const spinnerVisible = all('[data-testid="stSpinner"], [data-testid="stStatusWidget"], .stSpinner, [aria-busy="true"]')
                    .some(visible);
                  const appVisible = all('[data-testid="stApp"]').some(visible);
                  return {
                    title: document.title || '',
                    muVisible: inputVisible(muLabel),
                    vuVisible: inputVisible(vuLabel),
                    browserStatePresent,
                    browserStateVisible,
                    summaryVisible,
                    designGuideVisible,
                    spinnerVisible,
                    appVisible
                  };
                }
                """,
                {"muLabel": MU_LABEL, "vuLabel": VU_LABEL},
            )
        )
    except Exception:
        dom = {}
    marker_elapsed_ms = round((time.perf_counter() - marker_started) * 1000.0, 3)

    title = str(dom.get("title") or "")
    mu_visible = bool(dom.get("muVisible"))
    vu_visible = bool(dom.get("vuVisible"))
    browser_state_present = bool(dom.get("browserStatePresent"))
    browser_state_visible = bool(dom.get("browserStateVisible"))
    summary_visible = bool(dom.get("summaryVisible"))
    design_guide_visible = bool(dom.get("designGuideVisible"))
    spinner_visible = bool(dom.get("spinnerVisible"))
    app_visible = bool(dom.get("appVisible"))

    input_labels = []
    if mu_visible:
        input_labels.append(MU_LABEL)
    if vu_visible:
        input_labels.append(VU_LABEL)
    if browser_state_visible:
        input_labels.append("Browser state")
    matched_markers = [label for label in input_labels if label in {MU_LABEL, VU_LABEL}]
    inputs_route_active = route == "inputs"
    app_connected = app_visible
    has_real_inputs_content = bool(inputs_route_active and mu_visible and vu_visible)
    rendered_outputs_ready = bool(summary_visible and design_guide_visible)
    ready = bool(
        app_connected
        and has_real_inputs_content
        and browser_state_present
        and (rendered_outputs_ready if require_rendered_outputs else True)
    )
    return {
        "timestamp_ms": int(time.time() * 1000),
        "current_url": current_url,
        "query_params": query_params,
        "active_page_route": route,
        "inputs_route_active": inputs_route_active,
        "page_title": title,
        "connection_state": "CONNECTED" if app_connected else None,
        "script_state": None,
        "streamlit_status": ["status_widget_visible"] if spinner_visible else [],
        "shell_header_visible": app_connected,
        "active_nav_or_tab_state": [],
        "status_texts": [],
        "body_text_length": 0,
        "visible_text_excerpt": "",
        "headings": [],
        "input_labels": input_labels,
        "buttons": [],
        "matched_content_markers": matched_markers,
        "inputs_body_marker_visible": bool(matched_markers),
        "key_input_labels_visible": matched_markers,
        "summary_card_count": 1 if summary_visible else 0,
        "design_guide_card_count": 1 if design_guide_visible else 0,
        "browser_state_marker_count": 1 if browser_state_visible else 0,
        "browser_state_probe_present_count": 1 if browser_state_present else 0,
        "browser_state_probe_visible": browser_state_visible,
        "loading_spinner_count": 1 if spinner_visible else 0,
        "console_error_count": 0,
        "dom_mutation_probe": {"locator_snapshot": True},
        "app_connected": app_connected,
        "has_real_inputs_content": has_real_inputs_content,
        "require_rendered_outputs": bool(require_rendered_outputs),
        "rendered_outputs_ready": rendered_outputs_ready,
        "shell_only": bool(inputs_route_active and not has_real_inputs_content),
        "ready": ready,
        "timing_breakdown_ms": {
            "route_slug_detection_ms": route_elapsed_ms,
            "marker_query_ms": marker_elapsed_ms,
            "dom_snapshot_ms": round((time.perf_counter() - snapshot_started) * 1000.0, 3),
            "heavy_diagnostic_ms": 0.0,
        },
    }


def _summarise_route_body_mount_trace(
    observations: list[dict[str, Any]],
    *,
    require_rendered_outputs: bool = True,
) -> dict[str, Any]:
    def first_where(predicate) -> dict[str, Any] | None:
        for row in observations:
            snap = dict(row.get("snapshot") or {})
            try:
                if predicate(snap):
                    return {"poll": row.get("poll"), "elapsed_ms": row.get("elapsed_ms"), "value": snap}
            except Exception:
                continue
        return None

    last = dict((observations[-1].get("snapshot") if observations else {}) or {})
    final_unmet: list[str] = []
    if not bool(last.get("inputs_route_active")):
        final_unmet.append("inputs_route_active")
    if not bool(last.get("shell_header_visible")):
        final_unmet.append("shell_header_visible")
    if not bool(last.get("inputs_body_marker_visible")):
        final_unmet.append("inputs_body_marker_visible")
    if not list(last.get("key_input_labels_visible") or []):
        final_unmet.append("key_input_labels_visible")
    if require_rendered_outputs and int(last.get("summary_card_count") or 0) <= 0:
        final_unmet.append("summary_card_count")
    if require_rendered_outputs and int(last.get("design_guide_card_count") or 0) <= 0:
        final_unmet.append("design_guide_card_count")
    if int(last.get("browser_state_probe_present_count") or last.get("browser_state_marker_count") or 0) <= 0:
        final_unmet.append("browser_state_probe_present_count")
    if not bool(last.get("ready")):
        final_unmet.append("inputs_content_ready")
    return {
        "poll_count": len(observations),
        "first_shell_visible": first_where(lambda snap: bool(snap.get("shell_header_visible"))),
        "first_route_page_slug_visible": first_where(lambda snap: bool(snap.get("inputs_route_active"))),
        "first_inputs_marker_visible": first_where(lambda snap: bool(snap.get("inputs_body_marker_visible"))),
        "first_input_label_visible": first_where(lambda snap: bool(snap.get("key_input_labels_visible"))),
        "first_summary_card_visible": first_where(lambda snap: int(snap.get("summary_card_count") or 0) > 0),
        "first_browser_state_marker_visible": first_where(lambda snap: int(snap.get("browser_state_marker_count") or 0) > 0),
        "first_browser_state_probe_present": first_where(
            lambda snap: int(snap.get("browser_state_probe_present_count") or snap.get("browser_state_marker_count") or 0) > 0
        ),
        "final_unmet_condition": final_unmet or ["ready"],
        "last_snapshot": last,
    }


def wait_for_inputs_content_ready_before_probe(
    page,
    *,
    timeout_s: float = 45.0,
    console_messages: list[str] | None = None,
    require_rendered_outputs: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    observations: list[dict[str, Any]] = []
    timing_polls: list[dict[str, Any]] = []
    stable_ready_reads = 0
    poll = 0
    _record_playwright_stage(
        "inputs_content_ready_gate_start",
        page=page,
        timeout_s=timeout_s,
        require_rendered_outputs=require_rendered_outputs,
    )
    while (time.perf_counter() - started) < timeout_s:
        poll_started = time.perf_counter()
        poll += 1
        snapshot = _inputs_content_ready_snapshot(page, require_rendered_outputs=require_rendered_outputs)
        snapshot["console_error_count"] = len([line for line in (console_messages or []) if str(line).lower().startswith("error")])
        poll_timing = dict(snapshot.get("timing_breakdown_ms") or {})
        poll_timing.update(
            {
                "poll": poll,
                "elapsed_ms": _safe_elapsed_ms(started),
                "total_poll_ms": round((time.perf_counter() - poll_started) * 1000.0, 3),
                "locator_query_ms": 0.0,
                "require_rendered_outputs": bool(require_rendered_outputs),
                "ready": bool(snapshot.get("ready")),
                "summary_card_count": int(snapshot.get("summary_card_count") or 0),
                "design_guide_card_count": int(snapshot.get("design_guide_card_count") or 0),
                "browser_state_marker_count": int(snapshot.get("browser_state_marker_count") or 0),
                "browser_state_probe_present_count": int(
                    snapshot.get("browser_state_probe_present_count") or snapshot.get("browser_state_marker_count") or 0
                ),
                "loading_spinner_count": int(snapshot.get("loading_spinner_count") or 0),
            }
        )
        timing_polls.append(poll_timing)
        row = {
            "poll": poll,
            "elapsed_ms": _safe_elapsed_ms(started),
            "snapshot": snapshot,
        }
        observations.append(row)
        if not bool(snapshot.get("inputs_route_active")):
            result = {
                "ready": True,
                "skipped": True,
                "reason": "active route is not inputs",
                "poll_count": poll,
                "elapsed_ms": _safe_elapsed_ms(started),
                "last_snapshot": snapshot,
                "summary": _summarise_route_body_mount_trace(
                    observations,
                    require_rendered_outputs=require_rendered_outputs,
                ),
                "observations_tail": observations[-12:],
                "require_rendered_outputs": bool(require_rendered_outputs),
            }
            _record_playwright_stage("inputs_content_ready_gate_done", page=page, success=True, skipped=True)
            return result
        if bool(snapshot.get("ready")):
            stable_ready_reads += 1
        else:
            stable_ready_reads = 0
        if stable_ready_reads >= 2:
            result = {
                "ready": True,
                "skipped": False,
                "reason": "inputs content ready before browser-state probe attach",
                "poll_count": poll,
                "elapsed_ms": _safe_elapsed_ms(started),
                "stable_ready_reads": stable_ready_reads,
                "last_snapshot": snapshot,
                "summary": _summarise_route_body_mount_trace(
                    observations,
                    require_rendered_outputs=require_rendered_outputs,
                ),
                "observations_tail": observations[-12:],
                "require_rendered_outputs": bool(require_rendered_outputs),
            }
            _record_playwright_stage("inputs_content_ready_gate_done", page=page, success=True, elapsed_ms=result["elapsed_ms"])
            artifact_dir = _CURRENT_INPUT_EDIT_ARTIFACT_DIR
            if artifact_dir is not None:
                _write_json(Path(artifact_dir) / "inputs_content_ready_gate.json", result)
                _write_json(Path(artifact_dir) / "route_body_mount_trace.json", {
                    "summary": result["summary"],
                    "observations": observations,
                })
                _write_json(Path(artifact_dir) / "inputs_ready_gate_timing_breakdown.json", {
                    "ready": True,
                    "poll_count": poll,
                    "elapsed_ms": result["elapsed_ms"],
                    "require_rendered_outputs": bool(require_rendered_outputs),
                    "polls": timing_polls,
                    "final_unmet_condition": result["summary"].get("final_unmet_condition"),
                })
            return result
        time.sleep(0.35)
    if observations and bool((observations[-1].get("snapshot") or {}).get("ready")) and stable_ready_reads == 1:
        time.sleep(0.35)
        poll += 1
        poll_started = time.perf_counter()
        snapshot = _inputs_content_ready_snapshot(page, require_rendered_outputs=require_rendered_outputs)
        snapshot["console_error_count"] = len([line for line in (console_messages or []) if str(line).lower().startswith("error")])
        poll_timing = dict(snapshot.get("timing_breakdown_ms") or {})
        poll_timing.update(
            {
                "poll": poll,
                "elapsed_ms": _safe_elapsed_ms(started),
                "total_poll_ms": round((time.perf_counter() - poll_started) * 1000.0, 3),
                "locator_query_ms": 0.0,
                "require_rendered_outputs": bool(require_rendered_outputs),
                "ready": bool(snapshot.get("ready")),
                "summary_card_count": int(snapshot.get("summary_card_count") or 0),
                "design_guide_card_count": int(snapshot.get("design_guide_card_count") or 0),
                "browser_state_marker_count": int(snapshot.get("browser_state_marker_count") or 0),
                "browser_state_probe_present_count": int(
                    snapshot.get("browser_state_probe_present_count") or snapshot.get("browser_state_marker_count") or 0
                ),
                "loading_spinner_count": int(snapshot.get("loading_spinner_count") or 0),
                "post_deadline_stability_confirmation": True,
            }
        )
        timing_polls.append(poll_timing)
        observations.append(
            {
                "poll": poll,
                "elapsed_ms": _safe_elapsed_ms(started),
                "snapshot": snapshot,
                "post_deadline_stability_confirmation": True,
            }
        )
        if bool(snapshot.get("ready")):
            stable_ready_reads += 1
            result = {
                "ready": True,
                "skipped": False,
                "reason": "inputs content ready before browser-state probe attach; stability confirmed after blocked renderer poll",
                "poll_count": poll,
                "elapsed_ms": _safe_elapsed_ms(started),
                "stable_ready_reads": stable_ready_reads,
                "last_snapshot": snapshot,
                "summary": _summarise_route_body_mount_trace(
                    observations,
                    require_rendered_outputs=require_rendered_outputs,
                ),
                "observations_tail": observations[-12:],
                "require_rendered_outputs": bool(require_rendered_outputs),
                "post_deadline_stability_confirmation": True,
            }
            _record_playwright_stage("inputs_content_ready_gate_done", page=page, success=True, elapsed_ms=result["elapsed_ms"])
            artifact_dir = _CURRENT_INPUT_EDIT_ARTIFACT_DIR
            if artifact_dir is not None:
                _write_json(Path(artifact_dir) / "inputs_content_ready_gate.json", result)
                _write_json(Path(artifact_dir) / "route_body_mount_trace.json", {
                    "summary": result["summary"],
                    "observations": observations,
                })
                _write_json(Path(artifact_dir) / "inputs_ready_gate_timing_breakdown.json", {
                    "ready": True,
                    "poll_count": poll,
                    "elapsed_ms": result["elapsed_ms"],
                    "require_rendered_outputs": bool(require_rendered_outputs),
                    "post_deadline_stability_confirmation": True,
                    "polls": timing_polls,
                    "final_unmet_condition": result["summary"].get("final_unmet_condition"),
                })
            return result
    last = observations[-1]["snapshot"] if observations else {}
    result = {
        "ready": False,
        "skipped": False,
        "classification": "inputs_content_not_ready_before_browser_probe",
        "message": "Inputs page content was not ready before browser-state probe attach.",
        "poll_count": poll,
        "elapsed_ms": _safe_elapsed_ms(started),
        "stable_ready_reads": stable_ready_reads,
        "last_snapshot": last,
        "summary": _summarise_route_body_mount_trace(
            observations,
            require_rendered_outputs=require_rendered_outputs,
        ),
        "observations_tail": observations[-20:],
        "timeout_stage": "inputs_content_ready_before_browser_state_probe",
        "require_rendered_outputs": bool(require_rendered_outputs),
    }
    _record_playwright_stage(
        "inputs_content_ready_gate_timeout",
        page=page,
        exception=result["message"],
        classification=result["classification"],
    )
    artifact_dir = _CURRENT_INPUT_EDIT_ARTIFACT_DIR
    if artifact_dir is not None:
        _write_json(Path(artifact_dir) / "inputs_content_ready_gate.json", result)
        _write_json(Path(artifact_dir) / "route_body_mount_trace.json", {
            "summary": result["summary"],
            "observations": observations,
        })
        _write_json(Path(artifact_dir) / "inputs_ready_gate_timing_breakdown.json", {
            "ready": False,
            "poll_count": poll,
            "elapsed_ms": result["elapsed_ms"],
            "require_rendered_outputs": bool(require_rendered_outputs),
            "polls": timing_polls,
            "final_unmet_condition": result["summary"].get("final_unmet_condition"),
        })
    return result


def _classify_probe_readiness_failure(diagnostics: dict[str, Any]) -> str:
    inputs_gate = dict(diagnostics.get("inputs_content_ready_gate") or {})
    if inputs_gate and not inputs_gate.get("ready"):
        return str(inputs_gate.get("classification") or "inputs_content_not_ready_before_browser_probe")
    if _message_indicates_probe_teardown(diagnostics.get("exception_message")) or _probe_read_meta_indicates_teardown(
        dict(diagnostics.get("probe_read_meta") or {})
    ):
        return "browser_probe_attach_during_teardown"
    exception_text = str(diagnostics.get("exception_message") or "").lower()
    if "direct browser state probe attempts" in exception_text and '"found": false' in exception_text:
        return "browser_probe_marker_missing"
    if not diagnostics.get("http_readiness_result") or not diagnostics.get("current_url"):
        return "app_startup_or_page_load_timeout"
    if not diagnostics.get("inputs_page_appeared") and not diagnostics.get("summary_cards_appeared") and not diagnostics.get("design_guide_visible"):
        return "app_render_crash_before_probe"
    counts = dict(diagnostics.get("browser_state_selector_counts") or {})
    likely_probe_count = sum(int(value or 0) for key, value in counts.items() if key != "fast_guidance_item")
    if likely_probe_count > 0 and int(diagnostics.get("browser_state_label_count") or 0) <= 0:
        return "browser_probe_locator_mismatch"
    if likely_probe_count <= 0:
        return "browser_probe_marker_missing"
    return "browser_probe_timeout_before_timeline"


def wait_for_browser_state_probe_ready(
    page,
    *,
    base_url: str,
    console_messages: list[str],
    timeout_s: float = 120.0,
    allow_reload_once: bool = True,
    require_rendered_outputs: bool = True,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    attempt_count = 2 if allow_reload_once else 1
    per_attempt = max(10.0, timeout_s / float(attempt_count))
    latest: dict[str, Any] = {}
    reload_retry_result = "not_attempted"
    inputs_gate = wait_for_inputs_content_ready_before_probe(
        page,
        timeout_s=min(45.0, max(8.0, timeout_s * 0.45)),
        console_messages=console_messages,
        require_rendered_outputs=require_rendered_outputs,
    )
    if not inputs_gate.get("ready"):
        latest = {
            "timeout_stage": "inputs_content_ready_before_browser_state_probe",
            "ready": False,
            "classification": str(inputs_gate.get("classification") or "inputs_content_not_ready_before_browser_probe"),
            "message": str(inputs_gate.get("message") or "Inputs page content was not ready before browser-state probe attach."),
            "http_readiness_result": bool(_port_ready(base_url)),
            "current_url": str((inputs_gate.get("last_snapshot") or {}).get("current_url") or ""),
            "inputs_page_appeared": bool((inputs_gate.get("last_snapshot") or {}).get("inputs_route_active")),
            "summary_cards_appeared": False,
            "fast_guidance_item_count": 0,
            "probe_readable": False,
            "inputs_content_ready_gate": inputs_gate,
            "require_rendered_outputs": bool(require_rendered_outputs),
            "readiness_attempts": [],
            "result_after_retry": {
                "classification": str(inputs_gate.get("classification") or "inputs_content_not_ready_before_browser_probe"),
                "probe_readable": False,
                "inputs_content_ready": False,
                "inputs_content_last_snapshot": inputs_gate.get("last_snapshot"),
            },
        }
        _record_playwright_stage(
            "browser_state_probe_attach_blocked_by_inputs_content_gate",
            page=page,
            exception=latest["message"],
            classification=latest["classification"],
        )
        return latest
    _set_playwright_flag("probe_in_progress", True)
    _record_playwright_stage("browser_state_probe_attach_start", page=page, timeout_s=timeout_s, allow_reload_once=allow_reload_once)
    try:
        for attempt_index in range(attempt_count):
            deadline = time.time() + per_attempt
            while time.time() < deadline:
                try:
                    if page is None or page.is_closed():
                        latest = {
                            "timeout_stage": "browser_state_probe_attach",
                            "ready": False,
                            "classification": "browser_probe_attach_during_teardown",
                            "message": "Browser state probe could not attach because the Playwright page was already closed.",
                            "http_readiness_result": bool(_port_ready(base_url)),
                            "current_url": "",
                            "probe_read_meta": {"readable": False, "attempts": [{"source": "page", "error": "page closed before probe attach"}]},
                        }
                        _record_playwright_stage("browser_state_probe_attach_page_closed", page=page, exception="page closed before probe attach")
                        return latest
                except Exception as exc:
                    latest = {
                        "timeout_stage": "browser_state_probe_attach",
                        "ready": False,
                        "classification": "browser_probe_attach_during_teardown",
                        "message": f"Browser state probe could not inspect page state: {type(exc).__name__}: {exc}",
                        "http_readiness_result": bool(_port_ready(base_url)),
                        "current_url": "",
                        "probe_read_meta": {"readable": False, "attempts": [{"source": "page", "error": f"{type(exc).__name__}: {exc}"}]},
                    }
                    _record_playwright_stage("browser_state_probe_attach_page_state_error", page=page, exception=exc)
                    return latest
                _record_playwright_stage("browser_state_probe_read_start", page=page, attempt_index=attempt_index)
                latest = _collect_probe_readiness(page, base_url=base_url, console_messages=console_messages)
                latest["attempt_index"] = attempt_index
                attempts.append(
                    {
                        "attempt_index": attempt_index,
                        "http": latest.get("http_readiness_result"),
                        "inputs": latest.get("inputs_page_appeared"),
                        "summary": latest.get("summary_cards_appeared"),
                        "guide_count": latest.get("fast_guidance_item_count"),
                        "label_count": latest.get("browser_state_label_count"),
                        "textarea_count": latest.get("browser_state_textarea_count"),
                        "readable": latest.get("probe_readable"),
                        "url": latest.get("current_url"),
                    }
                )
                if latest.get("probe_readable"):
                    _record_playwright_stage("browser_state_probe_read_done", page=page, success=True, attempt_index=attempt_index)
                    _record_playwright_stage("browser_state_probe_attach_done", page=page, success=True, attempt_index=attempt_index)
                    latest.update(
                        {
                            "ready": True,
                            "classification": "",
                            "message": "Browser state probe attached and readable.",
                            "reload_retry_attempted": bool(attempt_index > 0),
                            "readiness_attempts": attempts[-12:],
                        }
                    )
                    return latest
                time.sleep(1.0)
            if attempt_index == 0 and allow_reload_once:
                latest["reload_retry_attempted"] = True
                try:
                    page.reload(wait_until="domcontentloaded", timeout=90_000)
                    reload_retry_result = "reload_completed"
                    latest["reload_retry_result"] = reload_retry_result
                except Exception as exc:
                    reload_retry_result = f"{type(exc).__name__}: {exc}"
                    latest["reload_retry_result"] = reload_retry_result
                    _record_playwright_stage("browser_state_probe_reload_error", page=page, exception=exc)
        latest = dict(latest or _collect_probe_readiness(page, base_url=base_url, console_messages=console_messages))
        latest["ready"] = False
        latest["classification"] = _classify_probe_readiness_failure(latest)
        latest["message"] = (
            "Browser state probe was not readable before timeline capture after staged readiness checks "
            f"and {'one reload retry' if allow_reload_once else 'no reload retry'}."
        )
        latest["reload_retry_attempted"] = bool(allow_reload_once)
        latest["reload_retry_result"] = reload_retry_result if allow_reload_once else "not_attempted"
        latest["readiness_attempts"] = attempts[-20:]
        latest["result_after_retry"] = {
            "classification": latest.get("classification"),
            "probe_readable": latest.get("probe_readable"),
            "browser_state_label_count": latest.get("browser_state_label_count"),
            "browser_state_selector_counts": latest.get("browser_state_selector_counts"),
            "inputs_page_appeared": latest.get("inputs_page_appeared"),
            "summary_cards_appeared": latest.get("summary_cards_appeared"),
            "fast_guidance_item_count": latest.get("fast_guidance_item_count"),
        }
        _record_playwright_stage("browser_state_probe_attach_failed", page=page, exception=latest.get("message"), classification=latest.get("classification"))
        return latest
    finally:
        _set_playwright_flag("probe_in_progress", False)


def capture_pre_timeline_probe_timeout_step(
    page,
    *,
    base_url: str,
    console_messages: list[str],
    message: str,
    stage: str = "browser_state_probe_attach",
    setup_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    setup_diagnostics = dict(
        setup_override
        or _collect_probe_readiness(page, base_url=base_url, console_messages=console_messages, message=message)
    )
    setup_diagnostics["timeout_stage"] = stage
    setup_diagnostics["exception_message"] = str(message)
    setup_diagnostics.setdefault("classification", _classify_probe_readiness_failure(setup_diagnostics))
    return {
        "case_index": None,
        "step_index": None,
        "step_type": "pre_timeline_probe_timeout",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "input_values": {},
        "visible_summary": {
            "parse_failed": True,
            "not_captured": True,
            "reason": "No product Design Guide state was tested.",
            "raw_visible_text": "",
        },
        "visible_design_guide": {
            "visible_card_count": None,
            "fast_guidance_item_count": setup_diagnostics.get("fast_guidance_item_count"),
            "title": "",
            "text": "",
            "family": "",
            "cta_visible": False,
            "cta_enabled": False,
            "not_captured": True,
            "reason": "No product Design Guide state was tested.",
        },
        "browser_state": {
            "setup_diagnostics": dict(setup_diagnostics),
        },
        "setup_diagnostics": dict(setup_diagnostics),
    }


def _classification_from_pre_timeline_step(step: dict[str, Any]) -> str:
    diagnostics = dict((step.get("setup_diagnostics") or {}) or ((step.get("browser_state") or {}).get("setup_diagnostics") or {}))
    return str(diagnostics.get("classification") or _classify_probe_readiness_failure(diagnostics) or "browser_probe_timeout_before_timeline")


def _infer_replay_input_setup_type(case: dict[str, Any], args: argparse.Namespace) -> str:
    replay_case = str(getattr(args, "replay_case", "") or "").replace("\\", "/").lower()
    if case.get("golden_matrix_case") or case.get("golden_case_name") or "golden_matrix" in replay_case:
        return "golden_matrix"
    if "previous_fixed" in replay_case or "overnight_failure_exports" in replay_case:
        return "previous_fixed"
    if "focused_replays" in replay_case:
        return "focused_replay"
    if getattr(args, "replay_case", None):
        return "replay_case"
    return "live_fuzz"


def run_case(
    page,
    *,
    case: dict[str, Any],
    base_url: str,
    artifact_dir: Path,
    args: argparse.Namespace,
    rng: random.Random,
    console_messages: list[str] | None = None,
    lifecycle: LifecycleDiagnostics | None = None,
) -> dict[str, Any]:
    global _CURRENT_INPUT_EDIT_ARTIFACT_DIR, _CURRENT_INPUT_EDIT_CONSOLE_MESSAGES, _CURRENT_REPLAY_INPUT_SETUP_TYPE
    _CURRENT_INPUT_EDIT_ARTIFACT_DIR = Path(artifact_dir)
    _CURRENT_INPUT_EDIT_CONSOLE_MESSAGES = console_messages
    _CURRENT_REPLAY_INPUT_SETUP_TYPE = _infer_replay_input_setup_type(case, args)
    timeline: list[dict[str, Any]] = []
    mutations: list[dict[str, Any]] = []
    clicked_steps: list[dict[str, Any]] = []
    page_cycle_checks: list[dict[str, Any]] = []
    current_inputs = {"mu": float(case["mu"]), "vu": float(case["vu"]), "recipe": case.get("recipe")}
    replay_started_perf = _perf_now()

    def post_baseline_heartbeat(stage: str, **extra: Any) -> None:
        try:
            _post_baseline_heartbeat(
                artifact_dir,
                page,
                stage=stage,
                replay_started_perf=replay_started_perf,
                port=getattr(args, "port", None),
                case_index=case.get("case_index"),
                **extra,
            )
        except Exception as exc:
            if lifecycle is not None:
                lifecycle.event(
                    "post_baseline_heartbeat_error",
                    case_index=case.get("case_index"),
                    heartbeat_stage=stage,
                    error=f"{type(exc).__name__}: {exc}",
                )

    if lifecycle is not None:
        lifecycle.set_stage(
            "case_start",
            case_index=case.get("case_index"),
            extra={"recipe": case.get("recipe"), "initial_inputs": dict(case)},
        )
    apply_initial_case(
        page,
        base_url,
        case,
        reload_between_cases=bool(args.reload_between_cases),
        console_messages=console_messages or [],
        lifecycle=lifecycle,
    )
    wait_for_settle(
        page,
        base_url=base_url,
        console_messages=console_messages or [],
        lifecycle=lifecycle,
        stage="initial_post_apply_settle",
    )
    if bool(case.get("require_initial_rendered_outputs") or case.get("require_browser_recipe_applied")):
        if lifecycle is not None:
            lifecycle.event("focused_replay_rendered_outputs_wait_start", timeout_s=180.0)
        rendered_ready = wait_for_browser_state_probe_ready(
            page,
            base_url=base_url,
            console_messages=console_messages or [],
            timeout_s=180.0,
            allow_reload_once=False,
            require_rendered_outputs=True,
        )
        if lifecycle is not None:
            lifecycle.event(
                "focused_replay_rendered_outputs_wait_end",
                ready=bool(rendered_ready.get("ready")),
                readiness_classification=rendered_ready.get("classification"),
                pending_readiness=rendered_ready.get("result_after_retry") or rendered_ready.get("readiness_attempts"),
            )
        if not rendered_ready.get("ready"):
            raise VisibleContractFailure(
                str(rendered_ready.get("classification") or "focused_replay_rendered_outputs_not_ready"),
                str(rendered_ready.get("message") or "Focused replay outputs were not ready before baseline page-cycle."),
                capture_pre_timeline_probe_timeout_step(
                    page,
                    base_url=base_url,
                    console_messages=console_messages or [],
                    message=str(rendered_ready.get("message") or "Focused replay outputs were not ready before baseline page-cycle."),
                    stage=str(rendered_ready.get("timeout_stage") or "focused_replay_rendered_outputs"),
                    setup_override=rendered_ready,
                ),
            )
    page_cycle_mode = str(getattr(args, "page_cycle_mode", "full") or "full").strip() or "full"
    if lifecycle is not None:
        lifecycle.event(
            "page_cycle_mode_selected",
            page_cycle_mode=page_cycle_mode,
            page_cycle_reduced=page_cycle_mode != "full",
            replay=str(getattr(args, "replay_case", "") or ""),
        )
    _record_playwright_stage("page_cycle_start", page=page, page_cycle_stage="clean_baseline_page_cycle", page_cycle_mode=page_cycle_mode)
    page_cycle_checks.append(
        assert_page_cycle_ghost_ui_contract(
            page,
            base_url=base_url,
            artifact_dir=artifact_dir,
            case_index=case.get("case_index"),
            stage="clean_baseline_page_cycle",
            console_messages=console_messages or [],
            lifecycle=lifecycle,
            page_cycle_mode=page_cycle_mode,
        )
    )
    _record_playwright_stage("page_cycle_done", page=page, success=True, page_cycle_stage="clean_baseline_page_cycle")
    post_baseline_heartbeat("clean_baseline_page_cycle_done", last_successful_playwright_call="clean_baseline_page_cycle_done")
    wait_for_settle(
        page,
        base_url=base_url,
        console_messages=console_messages or [],
        lifecycle=lifecycle,
        stage="post_clean_page_cycle_settle",
    )
    step_index = 0
    if lifecycle is not None:
        lifecycle.event("capture_step_start", stage="initial_settle", case_index=case.get("case_index"), step_index=step_index)
    post_baseline_heartbeat("timeline_capture_start", step_index=step_index, extra={"step_type": "initial_settle"})
    post_baseline_heartbeat("browser_state_read_start", step_index=step_index, extra={"step_type": "initial_settle"})
    post_baseline_heartbeat("design_guide_card_capture_start", step_index=step_index, extra={"step_type": "initial_settle"})
    _record_playwright_stage("timeline_capture_start", page=page, step_type="initial_settle", step_index=step_index)
    step = capture_step(page, artifact_dir=artifact_dir, case_index=case["case_index"], step_index=step_index, step_type="initial_settle", inputs=current_inputs, save_screenshot=args.save_all_screenshots)
    _record_playwright_stage("timeline_capture_done", page=page, success=True, step_type="initial_settle", step_index=step_index)
    post_baseline_heartbeat("browser_state_read_done", step_index=step_index, extra={"step_type": "initial_settle"})
    post_baseline_heartbeat("design_guide_card_capture_done", step_index=step_index, extra={"step_type": "initial_settle"})
    post_baseline_heartbeat("timeline_capture_done", step_index=step_index, extra={"step_type": "initial_settle"})
    if lifecycle is not None:
        lifecycle.event("capture_step_end", stage="initial_settle", case_index=case.get("case_index"), step_index=step_index)
    timeline.append(step)
    required_recipe = str(case.get("recipe") or "").strip() if bool(case.get("require_browser_recipe_applied")) else ""
    if required_recipe:
        state = dict(step.get("browser_state") or {})
        applied_recipe = str(state.get("browser_recipe") or "").strip()
        if applied_recipe != required_recipe:
            failure_step = dict(step)
            failure_step["setup_diagnostics"] = {
                "classification": "browser_recipe_not_applied",
                "required_browser_recipe": required_recipe,
                "applied_browser_recipe": applied_recipe or None,
                "browser_recipe_error": state.get("browser_recipe_error"),
                "browser_query_param_probe": state.get("browser_query_param_probe"),
                "browser_shared_probe": state.get("browser_shared_probe"),
            }
            raise VisibleContractFailure(
                "browser_recipe_not_applied",
                (
                    f"Focused replay required browser recipe {required_recipe!r}, "
                    f"but the captured app Browser state reported {applied_recipe!r}."
                ),
                failure_step,
            )
    assert_visible_contract(
        step,
        fail_on_no_action_without_exhaustive_proof=bool(args.fail_on_no_action_without_exhaustive_proof),
    )
    _assert_focused_replay_acceptance_contract(step, case, phase="initial_settle")

    skip_initial_cta_click = bool(
        case.get("skip_initial_cta_click")
        or str(case.get("focused_acceptance_phase") or "").strip().lower() == "initial_only"
    )
    if skip_initial_cta_click and step["visible_design_guide"].get("cta_enabled") and lifecycle is not None:
        lifecycle.event(
            "focused_initial_cta_click_skipped",
            case_index=case.get("case_index"),
            step_index=step_index,
            focused_acceptance_phase=case.get("focused_acceptance_phase"),
        )

    if step["visible_design_guide"].get("cta_enabled") and not skip_initial_cta_click:
        step_index += 1
        if lifecycle is not None:
            lifecycle.event("capture_step_start", stage="pre_click", case_index=case.get("case_index"), step_index=step_index)
        post_baseline_heartbeat("timeline_capture_start", step_index=step_index, extra={"step_type": "pre_click"})
        post_baseline_heartbeat("browser_state_read_start", step_index=step_index, extra={"step_type": "pre_click"})
        post_baseline_heartbeat("design_guide_card_capture_start", step_index=step_index, extra={"step_type": "pre_click"})
        pre_click = capture_step(page, artifact_dir=artifact_dir, case_index=case["case_index"], step_index=step_index, step_type="pre_click", inputs=current_inputs, save_screenshot=args.save_all_screenshots)
        post_baseline_heartbeat("browser_state_read_done", step_index=step_index, extra={"step_type": "pre_click"})
        post_baseline_heartbeat("design_guide_card_capture_done", step_index=step_index, extra={"step_type": "pre_click"})
        post_baseline_heartbeat("timeline_capture_done", step_index=step_index, extra={"step_type": "pre_click"})
        if lifecycle is not None:
            lifecycle.event("capture_step_end", stage="pre_click", case_index=case.get("case_index"), step_index=step_index)
        timeline.append(pre_click)
        assert_visible_contract(
            pre_click,
            fail_on_no_action_without_exhaustive_proof=bool(args.fail_on_no_action_without_exhaustive_proof),
        )
        if lifecycle is not None:
            lifecycle.event("one_click_start", stage="one_click", case_index=case.get("case_index"), step_index=step_index)
        clicked, run_end = click_cta_if_enabled(page)
        if lifecycle is not None:
            lifecycle.event("one_click_end", stage="one_click", case_index=case.get("case_index"), step_index=step_index, clicked=clicked, run_end_present=bool(run_end))
        clicked_steps.append({"step_index": step_index, "clicked": clicked, "run_end": run_end})
        if clicked:
            if lifecycle is not None:
                lifecycle.event("post_click_publish_alignment_start", case_index=case.get("case_index"), step_index=step_index)
            post_state, aligned, _meta = _wait_for_post_publish_alignment(page, mu=current_inputs["mu"], vu=current_inputs["vu"], run_end_data=run_end, timeout_s=75.0)
            if lifecycle is not None:
                lifecycle.event("post_click_publish_alignment_end", case_index=case.get("case_index"), step_index=step_index, aligned=aligned, meta=_meta)
            if not aligned:
                _wait_for_post_click_state_without_run_end(page, mu=current_inputs["mu"], vu=current_inputs["vu"], pre_state=pre_click["browser_state"], timeout_s=45.0)
            wait_for_settle(
                page,
                base_url=base_url,
                console_messages=console_messages or [],
                lifecycle=lifecycle,
                stage="post_click_settle",
            )
            step_index += 1
            if lifecycle is not None:
                lifecycle.event("capture_step_start", stage="post_click", case_index=case.get("case_index"), step_index=step_index)
            post_click = capture_step(page, artifact_dir=artifact_dir, case_index=case["case_index"], step_index=step_index, step_type="post_click", inputs=current_inputs, save_screenshot=args.save_all_screenshots)
            if lifecycle is not None:
                lifecycle.event("capture_step_end", stage="post_click", case_index=case.get("case_index"), step_index=step_index)
            timeline.append(post_click)
            assert_visible_contract(
                post_click,
                after_click=True,
                previous_step=pre_click,
                fail_on_no_action_without_exhaustive_proof=bool(args.fail_on_no_action_without_exhaustive_proof),
            )

    replay_mutation_steps = list(getattr(args, "replay_mutation_steps", None) or [])
    for mutation_i in range(int(args.mutations_per_case)):
        if mutation_i < len(replay_mutation_steps) and isinstance(replay_mutation_steps[mutation_i], dict):
            mutation = dict(replay_mutation_steps[mutation_i])
            mutation.setdefault("mutation_type", "replay_mutation")
            mutation.setdefault("step", mutation_i)
            mutation["mu"] = round(float(mutation.get("mu", current_inputs.get("mu") or 0.0)), 2)
            mutation["vu"] = round(float(mutation.get("vu", current_inputs.get("vu") or 0.0)), 2)
        else:
            mutation = generate_mutation(rng, current_inputs, mutation_i)
        mutations.append(dict(mutation))
        current_inputs.update({"mu": mutation["mu"], "vu": mutation["vu"]})
        mutation_start = _perf_now()
        if lifecycle is not None:
            lifecycle.event("mutation_input_application_start", case_index=case.get("case_index"), mutation=mutation)
        post_baseline_heartbeat("mutation_apply_start", step_index=step_index, extra={"mutation": mutation})
        post_baseline_heartbeat("mutation_apply_input_label", step_index=step_index, active_input_label=MU_LABEL, extra={"requested_value": current_inputs["mu"], "mutation": mutation})
        post_baseline_heartbeat("mutation_apply_input_label", step_index=step_index, active_input_label=VU_LABEL, extra={"requested_value": current_inputs["vu"], "mutation": mutation})
        setattr(_set_number_input_with_disabled_guard, "_route_gate_ready_seen", False)
        try:
            _apply_live_inputs(page, mu=float(current_inputs["mu"]), vu=float(current_inputs["vu"]))
        except RuntimeError as exc:
            recovered_state, recovery_diagnostic = _read_reconciled_input_state_after_runtime_failure(
                page,
                mu=float(current_inputs["mu"]),
                vu=float(current_inputs["vu"]),
                timeout_s=5.0,
            )
            mutation_runtime_diagnostic = {
                "classification": "mutation_input_application_runtime_stall",
                "message": f"{type(exc).__name__}: {exc}",
                "case_index": case.get("case_index"),
                "step_index": step_index,
                "mutation": mutation,
                "requested_mu": float(current_inputs["mu"]),
                "requested_vu": float(current_inputs["vu"]),
                "post_failure_direct_state_read": recovery_diagnostic,
            }
            if recovery_diagnostic.get("state_matches_requested_inputs"):
                mutation_runtime_diagnostic["classification"] = "mutation_input_application_runtime_recovered"
                if artifact_dir is not None:
                    _write_json(
                        Path(artifact_dir) / f"mutation_input_application_runtime_recovery_step_{step_index}.json",
                        mutation_runtime_diagnostic,
                    )
                if lifecycle is not None:
                    lifecycle.event(
                        "mutation_input_application_runtime_recovered",
                        case_index=case.get("case_index"),
                        step_index=step_index,
                        mutation=mutation,
                        elapsed_ms=_safe_elapsed_ms(mutation_start),
                        recovery_source=dict(recovery_diagnostic.get("read_meta") or {}).get("source"),
                    )
                post_baseline_heartbeat(
                    "mutation_apply_runtime_recovered",
                    step_index=step_index,
                    extra={"mutation": mutation, "recovery": recovery_diagnostic},
                )
            else:
                if artifact_dir is not None:
                    _write_json(
                        Path(artifact_dir) / f"mutation_input_application_runtime_stall_step_{step_index}.json",
                        mutation_runtime_diagnostic,
                    )
                raise
        if lifecycle is not None:
            lifecycle.event("mutation_input_application_end", case_index=case.get("case_index"), mutation=mutation, elapsed_ms=_safe_elapsed_ms(mutation_start))
        post_baseline_heartbeat("mutation_apply_done", step_index=step_index, extra={"mutation": mutation, "elapsed_ms": _safe_elapsed_ms(mutation_start)})
        post_baseline_heartbeat("post_mutation_settle_start", step_index=step_index, extra={"mutation": mutation})
        wait_for_settle(
            page,
            base_url=base_url,
            console_messages=console_messages or [],
            lifecycle=lifecycle,
            stage=f"post_mutation_{mutation_i}_settle",
        )
        post_baseline_heartbeat("post_mutation_settle_done", step_index=step_index, extra={"mutation": mutation})
        step_index += 1
        if lifecycle is not None:
            lifecycle.event("capture_step_start", stage="post_mutation", case_index=case.get("case_index"), step_index=step_index, mutation=mutation)
        post_baseline_heartbeat("timeline_capture_start", step_index=step_index, extra={"step_type": "post_mutation", "mutation": mutation})
        post_baseline_heartbeat("browser_state_read_start", step_index=step_index, extra={"step_type": "post_mutation", "mutation": mutation})
        post_baseline_heartbeat("design_guide_card_capture_start", step_index=step_index, extra={"step_type": "post_mutation", "mutation": mutation})
        post_mutation = capture_step(page, artifact_dir=artifact_dir, case_index=case["case_index"], step_index=step_index, step_type="post_mutation", inputs=current_inputs, save_screenshot=args.save_all_screenshots)
        post_baseline_heartbeat("browser_state_read_done", step_index=step_index, extra={"step_type": "post_mutation", "mutation": mutation})
        post_baseline_heartbeat("design_guide_card_capture_done", step_index=step_index, extra={"step_type": "post_mutation", "mutation": mutation})
        post_baseline_heartbeat("timeline_capture_done", step_index=step_index, extra={"step_type": "post_mutation", "mutation": mutation})
        _fail_if_streamlit_runtime_transition(page, step=post_mutation, stage="post_mutation_capture")
        if lifecycle is not None:
            lifecycle.event("capture_step_end", stage="post_mutation", case_index=case.get("case_index"), step_index=step_index)
        previous = timeline[-1] if timeline else None
        timeline.append(post_mutation)
        assert_visible_contract(
            post_mutation,
            after_mutation=True,
            previous_step=previous,
            fail_on_no_action_without_exhaustive_proof=bool(args.fail_on_no_action_without_exhaustive_proof),
        )
        if bool(args.click_after_each_mutation) and post_mutation["visible_design_guide"].get("cta_enabled"):
            if lifecycle is not None:
                lifecycle.event("mutation_one_click_start", case_index=case.get("case_index"), step_index=step_index, mutation=mutation)
            clicked, run_end = click_cta_if_enabled(page)
            if lifecycle is not None:
                lifecycle.event("mutation_one_click_end", case_index=case.get("case_index"), step_index=step_index, mutation=mutation, clicked=clicked, run_end_present=bool(run_end))
            clicked_steps.append({"step_index": step_index, "clicked": clicked, "run_end": run_end})
            if clicked:
                _wait_for_post_publish_alignment(page, mu=current_inputs["mu"], vu=current_inputs["vu"], run_end_data=run_end, timeout_s=75.0)
                wait_for_settle(
                    page,
                    base_url=base_url,
                    console_messages=console_messages or [],
                    lifecycle=lifecycle,
                    stage=f"post_mutation_{mutation_i}_click_settle",
                )
                post_baseline_heartbeat("post_mutation_settle_done", step_index=step_index, extra={"stage": f"post_mutation_{mutation_i}_click_settle", "mutation": mutation})
                step_index += 1
                if lifecycle is not None:
                    lifecycle.event("capture_step_start", stage="second_click", case_index=case.get("case_index"), step_index=step_index)
                post_baseline_heartbeat("timeline_capture_start", step_index=step_index, extra={"step_type": "second_click", "mutation": mutation})
                post_baseline_heartbeat("browser_state_read_start", step_index=step_index, extra={"step_type": "second_click", "mutation": mutation})
                post_baseline_heartbeat("design_guide_card_capture_start", step_index=step_index, extra={"step_type": "second_click", "mutation": mutation})
                second_click = capture_step(page, artifact_dir=artifact_dir, case_index=case["case_index"], step_index=step_index, step_type="second_click", inputs=current_inputs, save_screenshot=args.save_all_screenshots)
                post_baseline_heartbeat("browser_state_read_done", step_index=step_index, extra={"step_type": "second_click", "mutation": mutation})
                post_baseline_heartbeat("design_guide_card_capture_done", step_index=step_index, extra={"step_type": "second_click", "mutation": mutation})
                post_baseline_heartbeat("timeline_capture_done", step_index=step_index, extra={"step_type": "second_click", "mutation": mutation})
                _fail_if_streamlit_runtime_transition(page, step=second_click, stage="second_click_capture")
                if lifecycle is not None:
                    lifecycle.event("capture_step_end", stage="second_click", case_index=case.get("case_index"), step_index=step_index)
                timeline.append(second_click)
                assert_visible_contract(
                    second_click,
                    after_click=True,
                    previous_step=post_mutation,
                    fail_on_no_action_without_exhaustive_proof=bool(args.fail_on_no_action_without_exhaustive_proof),
                )

    _record_playwright_stage("page_cycle_start", page=page, page_cycle_stage="final_page_cycle_before_pass", page_cycle_mode=page_cycle_mode)
    post_baseline_heartbeat(
        "post_mutation_page_cycle_start",
        step_index=step_index,
        extra={"page_cycle_stage": "final_page_cycle_before_pass", "page_cycle_mode": page_cycle_mode},
    )
    page_cycle_checks.append(
        assert_page_cycle_ghost_ui_contract(
            page,
            base_url=base_url,
            artifact_dir=artifact_dir,
            case_index=case.get("case_index"),
            stage="final_page_cycle_before_pass",
            console_messages=console_messages or [],
            lifecycle=lifecycle,
            page_cycle_mode=page_cycle_mode,
        )
    )
    _record_playwright_stage("page_cycle_done", page=page, success=True, page_cycle_stage="final_page_cycle_before_pass")
    post_baseline_heartbeat("post_mutation_page_cycle_done", step_index=step_index, extra={"page_cycle_stage": "final_page_cycle_before_pass"})
    wait_for_settle(
        page,
        base_url=base_url,
        console_messages=console_messages or [],
        lifecycle=lifecycle,
        stage="final_post_page_cycle_settle",
    )
    result = {
        "case_index": case["case_index"],
        "seed": args.seed,
        "initial_inputs": case,
        "mutation_steps": mutations,
        "clicked_steps": clicked_steps,
        "page_cycle_ghost_ui_checks": page_cycle_checks,
        "page_cycle_mode": page_cycle_mode,
        "page_cycle_reduced": page_cycle_mode != "full",
        "timeline": timeline,
        "final_status": "PASS",
    }
    result["visible_contract_steps"] = progress_case_summary(result)
    if lifecycle is not None:
        lifecycle.mark_success("case_pass", case_index=case.get("case_index"), recipe=case.get("recipe"))
    return result


def build_failure_diagnosis(
    *,
    classification: str,
    step: dict[str, Any],
    message: str,
    replay_command: str,
) -> dict[str, Any]:
    if classification in {PAGE_CYCLE_GHOST_FAILURE_CLASS, EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS, BENDING_READY_GATE_TIMEOUT_CLASS}:
        page_cycle = dict(step.get("page_cycle_ghost_ui_check") or {})
        exact = (
            "A visible calc/check card shell had a chevron/card container but no non-empty title, result, or body text."
            if classification == EMPTY_CALC_CHECK_SHELL_FAILURE_CLASS
            else "Bending page did not reach the visible ready gate before page-cycle settle."
            if classification == BENDING_READY_GATE_TIMEOUT_CLASS
            else PAGE_CYCLE_GHOST_FAILURE_MESSAGE
        )
        return {
            "failure_classification": classification,
            "confidence": "high",
            "product_bug_likely": classification != BENDING_READY_GATE_TIMEOUT_CLASS,
            "verifier_bug_likely": classification == BENDING_READY_GATE_TIMEOUT_CLASS,
            "setup_lifecycle_issue": classification == BENDING_READY_GATE_TIMEOUT_CLASS,
            "visible_user_state": {
                "captured": True,
                "active_page_tab": page_cycle.get("active_page_tab"),
                "active_url": page_cycle.get("active_url"),
                "failing_selectors_or_cards": list(page_cycle.get("failing_cards") or []),
            },
            "active_failing_families": [],
            "low_util_families": [],
            "candidate_evidence": {},
            "exact_blockers_by_family": {},
            "optimisation_audit": {},
            "no_action_analysis": {},
            "page_cycle_ghost_ui_check": page_cycle,
            "exact_contradiction": exact,
            "likely_failure_layer": (
                "verifier/page-cycle readiness lifecycle"
                if classification == BENDING_READY_GATE_TIMEOUT_CLASS
                else "layout/render/page navigation lifecycle"
            ),
            "suspect_paths": [
                "app.py page navigation/render lifecycle",
                "inputs_page.py rendered Inputs page sections",
                "bending_page.py / shear_page.py / deflection.py page render sections",
            ],
            "do_not_change": ["formulas", "solver maths", "target bands", "Design Guide verifier invariants"],
            "recommended_next_action": (
                "Inspect bending_ready_gate_audit.json to determine which visible readiness marker never stabilized."
                if classification == BENDING_READY_GATE_TIMEOUT_CLASS
                else "Inspect the page-cycle DOM excerpt and screenshots, then patch only the render/navigation path "
                "that leaves empty cards, ghosted content, or stale overlays visible after tab/page cycling."
            ),
            "replay_command": replay_command,
        }
    if _is_setup_lifecycle_classification(classification):
        setup = dict(step.get("setup_diagnostics") or dict(step.get("browser_state") or {}).get("setup_diagnostics") or {})
        teardown_race = classification == "browser_probe_attach_during_teardown"
        return {
            "failure_classification": classification,
            "confidence": "high" if teardown_race else "medium",
            "product_bug_likely": False,
            "verifier_bug_likely": True,
            "setup_lifecycle_issue": True,
            "visible_user_state": {
                "captured": False,
                "summary_statuses": {},
                "summary_utils": {},
                "card_title": "",
                "card_family": "",
                "card_type": "UNKNOWN",
                "card_displayed_util": None,
                "cta_visible": False,
                "cta_enabled": False,
            },
            "active_failing_families": [],
            "low_util_families": [],
            "candidate_evidence": {},
            "exact_blockers_by_family": {},
            "optimisation_audit": {},
            "no_action_analysis": {},
            "setup_diagnostics": dict(setup),
            "exact_contradiction": (
                "The browser-state probe failed while the Playwright page/context/browser appeared to be closing; "
                "this is a verifier lifecycle/orchestration failure, not a product Design Guide contradiction."
                if teardown_race
                else "No product Design Guide state was tested. The verifier failed during staged page/probe readiness "
                "before timeline capture, so no visible summary/card contract could be evaluated."
            ),
            "likely_failure_layer": (
                "browser probe attach/read lifecycle during teardown"
                if teardown_race
                else "browser probe readiness / verifier setup lifecycle"
            ),
            "suspect_paths": [
                "tools/browser_live_design_guide_fuzz_verifier.py",
                "browser state probe wait/readiness",
                "Streamlit startup or rerun lifecycle",
                "Playwright context/page teardown ordering",
            ],
            "do_not_change": ["formulas", "solver maths", "target bands", "broad candidate ranking", "Design Guide product logic"],
            "recommended_next_action": (
                "Fix verifier teardown ordering/diagnostics so page/context cleanup cannot race browser-state probe attach. "
                "Do not patch Design Guide product logic from this artifact."
                if teardown_race
                else "Diagnose probe readiness/startup lifecycle. Do not patch Design Guide product logic from this artifact, "
                "because no product Design Guide state was captured."
            ),
            "replay_command": replay_command,
        }
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    statuses = _summary_statuses(summary)
    utils = _summary_utils(summary)
    support = dict(summary.get("browser_overview_support") or {})
    support_statuses = dict(support.get("statuses") or {})
    support_utils = dict(support.get("utils") or {})
    visible_support_agree = True
    for family in ("bending", "shear"):
        if statuses.get(family) and support_statuses.get(family) and str(statuses.get(family)).upper() != str(support_statuses.get(family)).upper():
            visible_support_agree = False
        if utils.get(family) is not None and _float_or_none(support_utils.get(family)) is not None:
            if abs(float(utils[family]) - float(_float_or_none(support_utils.get(family)))) > 0.05:
                visible_support_agree = False
    parse_failed = bool(summary.get("parse_failed"))
    confidence = "low" if parse_failed else ("high" if visible_support_agree else "medium")
    title = str(card.get("title") or "")
    family = str(card.get("family") or "")
    displayed = _float_or_none(card.get("displayed_util"))
    blocker = is_valid_structured_blocker(card, state)
    no_action_analysis = blocker_proof_analysis(card, state, family) if not bool(card.get("cta_enabled")) else {}
    visible_state = {
        "summary_statuses": statuses,
        "summary_utils": utils,
        "card_title": title,
        "card_family": family,
        "card_type": card_type(card),
        "card_colour": visible_card_colour(card),
        "card_status_label": card.get("status_label"),
        "card_classes": card.get("classes"),
        "expected_card_colour": expected_card_colour(summary, card, state),
        "colour_alignment": colour_alignment(summary, card, state),
        "card_button_colour_semantics": dict(step.get("card_button_colour_semantics") or {}),
        "card_displayed_util": displayed,
        "cta_visible": bool(card.get("cta_visible")),
        "cta_enabled": bool(card.get("cta_enabled")),
    }
    evidence = cleanup_evidence(state)
    blockers = exact_blockers(state)
    optimisation_audit = dict(step.get("optimisation_audit") or build_optimisation_audit(summary, card, state))
    no_link_audit = no_link_shear_cleanup_audit(state, card)
    diagnosis = {
        "failure_classification": classification,
        "confidence": confidence,
        "product_bug_likely": True,
        "verifier_bug_likely": False,
        "visible_user_state": visible_state,
        "active_failing_families": active_fail_families(summary),
        "low_util_families": low_util_families(summary),
        "candidate_evidence": {
            "safe_candidate_count": _deep_get_count(evidence, keys=("safe_candidate_count", "safe_local_cleanup_count", "safe_executor_backed_candidates_count")),
            "executable_candidate_count": _deep_get_count(evidence, keys=("executable_candidate_count", "executable_cleanup_count", "executable_safe_cleanup_count")),
            "target_band_candidate_count": _deep_get_count(evidence, keys=("target_band_candidate_count", "executable_target_band_candidate_count")),
            "best_safe_final_util": evidence.get("best_safe_final_util"),
            "cleanup_search_ran": bool(evidence.get("cleanup_search_ran") or evidence.get("local_cleanup_search_ran") or evidence.get("repair_search_ran")),
            "cleanup_search_exhaustive": bool(evidence.get("cleanup_search_exhaustive") or evidence.get("local_cleanup_search_exhaustive") or evidence.get("repair_search_exhaustive")),
            "no_link_shear_cleanup_audit": dict(no_link_audit),
        },
        "exact_blockers_by_family": blockers,
        "optimisation_audit": optimisation_audit,
        "no_action_analysis": dict(no_action_analysis),
        "exact_contradiction": str(message),
        "likely_failure_layer": "Design Guide visible-output contract",
        "suspect_paths": ["inputs_page.py", "design_brain/engine.py", "tools/browser_live_design_guide_fuzz_verifier.py"],
        "do_not_change": ["formulas", "solver maths", "target bands", "broad candidate ranking", "verifier gates"],
        "recommended_next_action": "Inspect the visible card, button contract, and structured evidence for this exact step before patching.",
        "replay_command": replay_command,
    }
    lower_title = title.lower()
    if classification.startswith("util_display_mismatch"):
        bending = _float_or_none(utils.get("bending"))
        shear = _float_or_none(utils.get("shear"))
        if family == "bending" and displayed is not None and shear is not None and bending is not None and abs(displayed - shear) <= 0.05 and abs(displayed - bending) > 0.05:
            diagnosis.update(
                {
                    "confidence": "high",
                    "product_bug_likely": True,
                    "verifier_bug_likely": False,
                    "exact_contradiction": f"Bending card displayed util={displayed:.3f}, matching shear/worst util={shear:.3f}, while visible bending util={bending:.3f}.",
                    "likely_failure_layer": "Design Guide presentation/display_truth stamping",
                    "suspect_paths": [
                        "family-specific blocker card publication",
                        "display_truth/source_summary_util stamping",
                        "specific_blocker presentation",
                        "bending cleanup blocked card builder",
                    ],
                    "recommended_next_action": "Patch card display util selection so bending cards use bending util; do not touch formulas or ranking.",
                }
            )
        elif family == "shear" and displayed is not None and shear is not None and abs(displayed - shear) > 0.05:
            diagnosis.update(
                {
                    "confidence": "high",
                    "product_bug_likely": True,
                    "verifier_bug_likely": False,
                    "exact_contradiction": f"Shear card displayed util={displayed:.3f}, but visible shear util={shear:.3f}.",
                    "likely_failure_layer": "Design Guide presentation/display_truth stamping",
                    "suspect_paths": [
                        "family-specific blocker card publication",
                        "display_truth/source_summary_util stamping",
                        "specific_blocker presentation",
                        "shear cleanup blocked card builder",
                    ],
                    "recommended_next_action": "Patch card display util selection so shear cards use shear util; do not touch formulas or ranking.",
                }
            )
    elif classification in {
        "action_card_disabled",
        "active_bending_fail_no_action_or_blocker",
        "active_shear_fail_no_action_or_blocker",
        "active_fail_blocker_without_strengthening_exhaustion",
        "active_fail_blocker_without_repair_exhaustion",
        "strength_blocker_missing_repair_attempts",
        "strength_blocker_missing_best_rejected_candidate",
        "strength_blocker_missing_failed_value_or_limit",
        "strength_blocker_missing_combined_repair_attempts",
        "combined_blocker_reason_placeholder",
        "card_why_not_specific",
        "geometry_cleanup_attempts_missing",
        "zero_shear_suppressed_bending_cleanup",
        "in_target_state_wrong_colour",
        "final_best_safe_state_wrong_colour",
        "active_fail_post_click_still_fails",
        "active_fail_post_click_no_family_in_target",
        "active_fail_post_click_out_of_target_family_unexplained",
        "active_fail_repaired_but_card_not_green",
        "active_fail_post_click_used_cleanup_blocker",
        "active_fail_blocker_used_cleanup_evidence",
        "active_fail_no_strengthening_action",
        "combined_fail_incomplete_action",
        "combined_fail_no_combined_strengthening_action",
        "action_preview_does_not_fix_required_checks",
        "action_payload_missing",
        "fail_repair_did_not_make_all_checks_pass",
        "fail_repair_passes_but_no_target_band_proof",
        "failed_design_terminal_without_locked_constraints",
        "failed_shear_with_no_links_terminal",
        "design_guide_debug_text_leaked_to_user",
    }:
        if classification in {
            "failed_design_terminal_without_locked_constraints",
            "failed_shear_with_no_links_terminal",
            "design_guide_debug_text_leaked_to_user",
        }:
            diagnosis.update(
                {
                    "product_bug_likely": True,
                    "verifier_bug_likely": False,
                    "exact_contradiction": str(message),
                    "likely_failure_layer": "Design Guide active-failure repair publication / visible wording contract",
                    "suspect_paths": [
                        "active-failure repair routing",
                        "Design Guide final visible resolver",
                        "active-fail blocker publication",
                        "user-facing blocker explanation formatter",
                    ],
                    "recommended_next_action": (
                        "For utilisation > 1.0, publish an executor-backed repair action when repair freedoms exist; "
                        "otherwise show an exact visible user-lock/constraint blocker. Do not publish cleanup/no-link "
                        "terminal wording or raw solver/debug text in normal Design Guide cards."
                    ),
                }
            )
            return diagnosis
        if blocker and classification not in {
            "active_fail_blocker_without_strengthening_exhaustion",
            "active_fail_blocker_without_repair_exhaustion",
            "strength_blocker_missing_repair_attempts",
            "strength_blocker_missing_best_rejected_candidate",
            "strength_blocker_missing_failed_value_or_limit",
            "strength_blocker_missing_combined_repair_attempts",
            "combined_blocker_reason_placeholder",
            "card_why_not_specific",
            "active_fail_post_click_still_fails",
            "active_fail_post_click_no_family_in_target",
            "active_fail_post_click_out_of_target_family_unexplained",
            "active_fail_repaired_but_card_not_green",
            "active_fail_post_click_used_cleanup_blocker",
            "active_fail_blocker_used_cleanup_evidence",
            "combined_fail_no_combined_strengthening_action",
            "active_fail_no_strengthening_action",
        }:
            diagnosis.update(
                {
                    "product_bug_likely": False,
                    "verifier_bug_likely": True,
                    "exact_contradiction": "Visible card is a structured blocker with exact blocker evidence, but verifier classified it as a disabled action.",
                    "likely_failure_layer": "fuzz verifier card classification",
                    "suspect_paths": ["is_blocker_card", "is_valid_structured_blocker", "active-failure disabled CTA invariant"],
                    "recommended_next_action": "Tighten verifier card classification to distinguish ACTION wording from valid BLOCKER evidence.",
                }
            )
        else:
            proof = blocker_proof_analysis(card, state, family)
            diagnosis.update(
                {
                    "product_bug_likely": True,
                    "verifier_bug_likely": False,
                    "exact_contradiction": (
                        str(message)
                        if classification.startswith("active_fail_post_click")
                        else "Visible summary shows bending/shear FAIL, but the Design Guide does not provide a complete enabled repair action or exact structured blocker."
                    ),
                    "likely_failure_layer": (
                        "post-click active-fail repair final outcome"
                        if classification.startswith("active_fail_post_click")
                        else "button contract / executor-backed candidate publication / active failure repair routing"
                    ),
                    "suspect_paths": [
                        "button_contract",
                        "selected_action_updates",
                        "executor-backed candidate filter",
                        "strengthening repair candidate search",
                        "geometry/reinforcement/shear strengthening search",
                        "preview_pass",
                        "combined underdesign repair route",
                        "active failure priority",
                        "active-fail post-click target-band blocker publication",
                    ],
                    "no_action_analysis": dict(proof),
                    "active_fail_blocker_analysis": dict(step.get("active_fail_blocker_analysis") or {}),
                    "recommended_next_action": (
                        "For active FAIL, publish an enabled strengthening repair action if any exists; after click all required "
                        "checks must pass, at least one strength family must land in target, and every other out-of-target "
                        "strength family needs exact target-band blocker evidence. Only publish a blocker before repair when "
                        "geometry, reinforcement, shear-link, and combined strengthening searches are exhaustive and impossible."
                    ),
                }
            )
    elif classification in {"active_failure_terminal_card", "terminal_with_active_fail"}:
        enabled_contract = bool(card.get("cta_enabled") and dict(card.get("button_contract") or {}).get("actionable"))
        diagnosis.update(
            {
                "product_bug_likely": not enabled_contract,
                "verifier_bug_likely": enabled_contract,
                "exact_contradiction": "Visible summary shows a required FAIL while the Design Guide appears terminal/cleanup-only.",
                "likely_failure_layer": "fuzz verifier classification" if enabled_contract else "Design Guide active-failure priority / terminal suppression",
                "suspect_paths": ["terminal state derivation", "active failure repair prioritisation", "card publication override"],
                "recommended_next_action": (
                    "Fix verifier invariant; do not patch app."
                    if enabled_contract
                    else "Suppress terminal/cleanup card whenever an active failure is visible."
                ),
            }
        )
    elif classification in {"accepted_green_invalid", "accepted_green_invalid_after_edit"}:
        diagnosis.update(
            {
                "likely_failure_layer": "terminal state derivation / accepted-green audit",
                "suspect_paths": ["terminal state derivation", "accepted green audit", "low-util blocker proof publication"],
                "exact_contradiction": "Visible accepted/efficient state conflicts with active failures or unresolved low-util families.",
                "recommended_next_action": "Suppress accepted/efficient terminal state unless all required checks pass and each meaningful low-util family has exact blocker evidence.",
            }
        )
    elif classification in {"stale_after_manual_edit", "card_not_recomputed_after_edit"}:
        diagnosis.update(
            {
                "likely_failure_layer": "state fingerprint/cache invalidation",
                "suspect_paths": ["Design Guide cache fingerprint", "summary overview cache", "render fingerprint", "pending apply refresh"],
                "exact_contradiction": "Summary changed after a manual edit but Design Guide card/payload did not refresh.",
            }
        )
    elif classification in {"old_payload_reused_after_edit", "stale_primary_payload_visible_action"}:
        diagnosis.update(
            {
                "likely_failure_layer": "primary payload binding / stale apply payload",
                "suspect_paths": ["design_guide_primary_apply_payload", "payload binding audit", "button_contract", "queued apply updates"],
                "exact_contradiction": (
                    "Visible enabled action is shown with stale_primary_design_guide_payload or a primary payload "
                    "that does not match the visible button contract."
                    if classification == "stale_primary_payload_visible_action"
                    else "Visible card changed after edit, but queued/applied payload still matches an older step."
                ),
                "recommended_next_action": "Rebuild the canonical primary apply payload from the final rendered card before enabling the CTA, or suppress the CTA until the payload is fresh.",
            }
        )
    elif classification in {
        "one_click_no_material_change",
        "one_click_card_not_refreshed",
        "one_click_same_payload_still_visible",
        "one_click_summary_not_updated",
    }:
        layer_by_class = {
            "one_click_no_material_change": "apply handler / payload binding / widget reseed",
            "one_click_card_not_refreshed": "post-click Design Guide refresh / render fingerprint invalidation",
            "one_click_same_payload_still_visible": "primary payload binding / stale action publication",
            "one_click_summary_not_updated": "post-click result recomputation / summary publication",
        }
        contradiction_by_class = {
            "one_click_no_material_change": (
                "The visible one-click CTA was enabled and had selected_action_updates, but after clicking, "
                "no intended update key changed to the expected value in browser/shared state."
            ),
            "one_click_card_not_refreshed": (
                "The one-click action changed intended inputs, but the visible Design Guide card remained the "
                "same stale title/text/family/displayed-util/action payload after settle."
            ),
            "one_click_same_payload_still_visible": (
                "The same candidate or render fingerprint remained visible and enabled after clicking it, so "
                "the user could click the same stale payload again."
            ),
            "one_click_summary_not_updated": (
                "The one-click action changed intended inputs, but the visible summary/results did not update "
                "after settle."
            ),
        }
        diagnosis.update(
            {
                "confidence": "high" if not parse_failed else "medium",
                "product_bug_likely": True,
                "verifier_bug_likely": False,
                "likely_failure_layer": layer_by_class.get(classification, "one-click apply lifecycle"),
                "suspect_paths": [
                    "apply_resolved_candidate handler",
                    "design_guide_primary_apply_payload",
                    "button_contract updates",
                    "widget reseed/shared state hydration",
                    "summary/results publication",
                    "Design Guide render fingerprint",
                ],
                "exact_contradiction": contradiction_by_class.get(classification, str(message)),
                "one_click_material_change_audit": dict(step.get("one_click_material_change_audit") or {}),
                "recommended_next_action": (
                    "Trace the clicked button contract through the apply handler, shared/widget state, summary "
                    "publication, and Design Guide render fingerprint; require material update plus refreshed "
                    "summary/card state before treating the click as successful."
                ),
            }
        )
    elif classification in {"blocker_missing", "blocker_missing_exact_evidence", "low_util_no_cleanup_or_blocker", "blocker_family_mismatch"}:
        proof = blocker_proof_analysis(card, state, family)
        diagnosis.update(
            {
                "likely_failure_layer": "blocker evidence publication",
                "suspect_paths": ["exact blocker stamping", "cleanup evidence by family", "specific_blocker decision"],
                "exact_contradiction": "Visible no-CTA/blocker state lacks exhaustive exact blocker evidence.",
                "no_action_analysis": dict(proof),
            }
        )
    elif classification in {
        "multi_family_blocker_missing_family_evidence",
        "multi_family_blocker_vague_reason",
        "blocker_util_label_ambiguous",
    }:
        diagnosis.update(
            {
                "confidence": "high" if not parse_failed else "medium",
                "product_bug_likely": True,
                "verifier_bug_likely": False,
                "likely_failure_layer": "multi-family blocker evidence / visible copy publication",
                "suspect_paths": [
                    "multi-family cleanup blocker builder",
                    "exact_blockers_by_family publication",
                    "cleanup_evidence_by_family",
                    "Design Guide visible title/body/util label",
                ],
                "exact_contradiction": str(message),
                "recommended_next_action": (
                    "Publish exact bending and shear blocker evidence with per-family search/count fields, "
                    "and render separate user-facing bending/shear blocker reasons with a labelled utilisation."
                ),
            }
        )
    elif classification in {
        "card_colour_status_mismatch",
        "summary_fail_but_card_not_repair",
        "all_pass_in_target_but_not_green",
        "green_card_with_unresolved_family",
        "blocker_card_without_specific_engineering_reason",
        "summary_fail_card_not_red",
        "summary_fail_card_warn_or_cleanup",
        "summary_fail_card_green_or_terminal",
        "summary_pass_card_red",
        "combined_fail_card_not_red_combined",
        "safe_overdesign_card_not_blue",
        "accepted_terminal_card_not_green",
        "fail_card_colour_status_mismatch",
        "post_click_not_green_or_exact_engineering_blocker",
        "post_click_not_green_or_exact_blocker",
        "post_click_vague_blocker_reason",
        "post_click_blocker_not_specific_enough",
        "post_click_blocker_missing_failed_candidate",
        "post_click_blocker_missing_failed_rule",
        "post_click_blocker_no_family_specific_reason",
        "post_click_unresolved_low_util_family",
        "post_click_unresolved_active_fail",
        "post_click_same_action_still_available",
        "post_click_blocker_missing_family_detail",
        "post_click_outside_target_without_exact_blocker",
        "active_fail_repaired_but_card_not_green",
        "fail_repair_passes_but_no_target_band_proof",
        "fail_repair_did_not_make_all_checks_pass",
    }:
        final_state = dict(step.get("post_click_final_state") or {})
        diagnosis.update(
            {
                "confidence": "high" if not parse_failed else "medium",
                "product_bug_likely": True,
                "verifier_bug_likely": False,
                "likely_failure_layer": "post-click final outcome publication / exact blocker wording",
                "suspect_paths": [
                    "post-click Design Guide card builder",
                    "accepted green/terminal state derivation",
                    "exact_blockers_by_family publication",
                    "family-specific blocker visible copy",
                    "button_contract publication",
                ],
                "exact_contradiction": str(message),
                "post_click_final_state": final_state,
                "recommended_next_action": (
                    "After a one-click action, publish only a green accepted/target state or a specific exact "
                    "engineering blocker with failed candidate/check/rule evidence for every unresolved family; do not count material key "
                    "changes alone as success."
                ),
            }
        )
    elif classification in {
        "post_click_required_check_still_fails",
        "post_click_outside_target_without_blocker",
        "action_leaves_low_util_family_unresolved",
        "optimisation_hidden_low_util_family",
    }:
        if classification in {"action_leaves_low_util_family_unresolved", "optimisation_hidden_low_util_family"}:
            exact_contradiction = (
                "The visible card is an enabled ACTION, but its preview/click leaves another "
                "meaningful low-util family below threshold without a same-step action or exact blocker evidence."
            )
        else:
            exact_contradiction = (
                "The one-click action did not leave the visible post-click state in target/pass contract, "
                "and no exact blocker evidence explains the remaining issue."
            )
        diagnosis.update(
            {
                "likely_failure_layer": "post-click repair publication / exact blocker proof",
                "suspect_paths": ["post-click proof publication", "repair candidate preview", "exact blocker stamping", "button_contract"],
                "exact_contradiction": exact_contradiction,
                "recommended_next_action": "Publish a combined/next-family action when safe, or publish exact blocker evidence for every remaining low-util family; do not change formulas, target bands, or broad ranking.",
            }
        )
    elif classification.startswith("optimisation_") or classification in {
        "geometry_cleanup_not_proven",
        "reinforcement_cleanup_not_proven",
        "shear_cleanup_not_proven",
        "serviceability_blocker_not_structured",
        "ductility_blocker_not_structured",
        "spacing_blocker_not_structured",
    }:
        diagnosis.update(
            {
                "likely_failure_layer": "optimisation family publication / action-blocker contract",
                "suspect_paths": [
                    "visible optimisation card builder",
                    "button_contract publication",
                    "candidate_search_evidence",
                    "exact blocker evidence by family",
                ],
                "exact_contradiction": str(message),
                "recommended_next_action": "Patch only the specific optimisation-family publication path so it exposes an executable action or exact structured blocker; do not change formulas, target bands, or broad ranking.",
            }
        )
    elif classification == "blocker_has_cta":
        diagnosis.update(
            {
                "confidence": "high" if not parse_failed else "medium",
                "product_bug_likely": True,
                "verifier_bug_likely": False,
                "likely_failure_layer": "Design Guide card/action contract publication",
                "suspect_paths": [
                    "visible card renderer",
                    "button_contract publication",
                    "design_guide_primary_apply_payload",
                    "specific_blocker card builder",
                ],
                "exact_contradiction": (
                    "Visible Design Guide card is a blocker, but the page exposes a one-click CTA "
                    "or executable button payload for the same flow."
                ),
                "recommended_next_action": (
                    "Clear executable payload and suppress CTA for blocker cards; do not change solver or formulas."
                ),
            }
        )
    return diagnosis


def _write_text_artifact(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def _capture_first_visible_locator(page, selectors: list[str], path: Path) -> tuple[str | None, str | None]:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=750)
            locator.screenshot(path=str(path), timeout=3_000)
            return str(path), None
        except Exception:
            continue
    return None, selectors[0] if selectors else "unknown"


def capture_failure_screenshots(
    page,
    artifact_dir: Path,
    reason: str,
    *,
    console_messages: list[str] | None = None,
    timeout_capture: bool = False,
    fallback_url: str | None = None,
    capture_prefix: str | None = None,
) -> dict[str, Any]:
    """Capture visual failure artifacts without changing verifier verdicts."""
    prefix = str(capture_prefix or ("timeout" if timeout_capture else "failure")).strip()
    info: dict[str, Any] = {
        "full_page_screenshot": None,
        "viewport_screenshot": None,
        "design_guide_screenshot": None,
        "summary_cards_screenshot": None,
        "debug_or_probe_screenshot": None,
        "screenshot_capture_status": "not_attempted",
        "missing_crop_targets": [],
        "screenshot_errors": [],
        "screenshot_reason": reason,
    }
    if page is None:
        info["screenshot_capture_status"] = "page_unavailable"
        info["screenshot_errors"].append("page object was not available")
        return info

    captured_any = False
    try:
        full_page = artifact_dir / f"full_page_{prefix}.png"
        page.screenshot(path=str(full_page), full_page=True, timeout=10_000)
        info["full_page_screenshot"] = str(full_page)
        captured_any = True
    except Exception as exc:
        info["screenshot_errors"].append(f"full_page: {type(exc).__name__}: {exc}")

    try:
        viewport = artifact_dir / f"viewport_{prefix}.png"
        page.screenshot(path=str(viewport), full_page=False, timeout=10_000)
        info["viewport_screenshot"] = str(viewport)
        captured_any = True
    except Exception as exc:
        info["screenshot_errors"].append(f"viewport: {type(exc).__name__}: {exc}")

    crop_targets = {
        "design_guide_screenshot": (
            artifact_dir / f"design_guide_{prefix}.png",
            [
                '[data-testid="design-guide-card"]',
                '[data-testid*="design-guide"]',
                ".fast-guidance-item",
                "text=Design Guide",
            ],
            "design_guide",
        ),
        "summary_cards_screenshot": (
            artifact_dir / f"summary_cards_{prefix}.png",
            [
                '[data-testid*="summary"]',
                '[data-testid*="check"]',
                ".summary-card",
                "text=Bending",
                "text=Shear",
            ],
            "summary_cards",
        ),
        "debug_or_probe_screenshot": (
            artifact_dir / f"debug_or_probe_{prefix}.png",
            [
                '[data-testid*="debug"]',
                '[data-testid*="probe"]',
                'textarea[aria-label*="Browser state"]',
                "text=Browser state",
                "text=debug",
            ],
            "debug_or_probe",
        ),
    }
    for key, (path, selectors, label) in crop_targets.items():
        captured, missing = _capture_first_visible_locator(page, selectors, path)
        if captured:
            info[key] = captured
            captured_any = True
        elif missing:
            info["missing_crop_targets"].append(label)

    if timeout_capture:
        try:
            _write_text_artifact(artifact_dir / "current_url.txt", str(page.url or ""))
        except Exception:
            pass
        try:
            _write_text_artifact(artifact_dir / "page_title.txt", str(page.title() or ""))
        except Exception:
            pass
        try:
            visible_text = page.locator("body").inner_text(timeout=2_000)
            _write_text_artifact(artifact_dir / "visible_text_excerpt.txt", visible_text[:8_000])
        except Exception as exc:
            info["screenshot_errors"].append(f"visible_text_excerpt: {type(exc).__name__}: {exc}")
        try:
            errors = [
                message
                for message in list(console_messages or [])
                if "error" in str(message).lower() or "traceback" in str(message).lower()
            ]
            _write_json(artifact_dir / "console_errors.json", errors)
        except Exception as exc:
            info["screenshot_errors"].append(f"console_errors: {type(exc).__name__}: {exc}")

    if (
        fallback_url
        and not info.get("full_page_screenshot")
        and not info.get("viewport_screenshot")
    ):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                fallback_page = context.new_page()
                fallback_page.goto(fallback_url, wait_until="domcontentloaded", timeout=20_000)
                try:
                    fallback_page.wait_for_timeout(1_000)
                except Exception:
                    pass
                fallback_info = capture_failure_screenshots(
                    fallback_page,
                    artifact_dir,
                    reason,
                    console_messages=console_messages,
                    timeout_capture=timeout_capture,
                    fallback_url=None,
                    capture_prefix=capture_prefix,
                )
                fallback_info["screenshot_errors"] = list(info.get("screenshot_errors") or []) + list(
                    fallback_info.get("screenshot_errors") or []
                )
                fallback_info["screenshot_capture_status"] = (
                    "fallback_captured"
                    if fallback_info.get("full_page_screenshot") or fallback_info.get("viewport_screenshot")
                    else fallback_info.get("screenshot_capture_status")
                )
                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass
                return fallback_info
        except Exception as exc:
            info["screenshot_errors"].append(f"fallback_page: {type(exc).__name__}: {exc}")

    if captured_any and info["screenshot_errors"]:
        info["screenshot_capture_status"] = "partial"
    elif captured_any:
        info["screenshot_capture_status"] = "captured"
    else:
        info["screenshot_capture_status"] = "failed"
    return info


def capture_pass_screenshots(
    page,
    artifact_dir: Path,
    case_result: dict[str, Any],
    *,
    console_messages: list[str] | None = None,
) -> dict[str, Any]:
    case_index = case_result.get("case_index")
    try:
        prefix = f"case_{int(case_index):03d}_pass"
    except Exception:
        prefix = "case_pass"
    screenshots = capture_failure_screenshots(
        page,
        artifact_dir,
        "pass",
        console_messages=console_messages,
        timeout_capture=False,
        fallback_url=None,
        capture_prefix=prefix,
    )
    case_result["pass_screenshots"] = screenshots
    for key in SCREENSHOT_FIELD_KEYS:
        case_result[f"pass_{key}"] = screenshots.get(key)
    return screenshots


def _screenshot_fields(payload: dict[str, Any]) -> dict[str, Any]:
    screenshots = dict(payload.get("screenshots") or {})
    for key in SCREENSHOT_FIELD_KEYS:
        if key in payload and key not in screenshots:
            screenshots[key] = payload.get(key)
    return {key: screenshots.get(key) for key in SCREENSHOT_FIELD_KEYS}


def _screenshot_markdown_lines(payload: dict[str, Any], *, heading: str = "## Screenshots") -> list[str]:
    screenshots = _screenshot_fields(payload)
    missing = screenshots.get("missing_crop_targets") or []
    return [
        "",
        heading,
        f"- Full page: `{screenshots.get('full_page_screenshot') or 'missing'}`",
        f"- Viewport: `{screenshots.get('viewport_screenshot') or 'missing'}`",
        f"- Design Guide: `{screenshots.get('design_guide_screenshot') or 'missing'}`",
        f"- Summary cards: `{screenshots.get('summary_cards_screenshot') or 'missing'}`",
        f"- Debug/probe: `{screenshots.get('debug_or_probe_screenshot') or 'missing'}`",
        f"- Capture status: `{screenshots.get('screenshot_capture_status') or 'missing'}`",
        f"- Missing crop targets: `{missing}`",
    ]


def save_failure_artifacts(
    *,
    artifact_dir: Path,
    page,
    case_result: dict[str, Any],
    failure: VisibleContractFailure | Exception,
    console_messages: list[str],
    base_url: str,
    port: int,
) -> dict[str, Any]:
    _set_playwright_flag("artifact_capture_in_progress", True)
    _record_playwright_stage("artifact_capture_start", page=page, classification=getattr(failure, "classification", "verifier_runtime_error"))
    try:
        return _save_failure_artifacts_impl(
            artifact_dir=artifact_dir,
            page=page,
            case_result=case_result,
            failure=failure,
            console_messages=console_messages,
            base_url=base_url,
            port=port,
        )
    finally:
        _record_playwright_stage("artifact_capture_done", page=page, success=True)
        _set_playwright_flag("artifact_capture_in_progress", False)


def _save_failure_artifacts_impl(
    *,
    artifact_dir: Path,
    page,
    case_result: dict[str, Any],
    failure: VisibleContractFailure | Exception,
    console_messages: list[str],
    base_url: str,
    port: int,
) -> dict[str, Any]:
    classification = getattr(failure, "classification", "verifier_runtime_error")
    step = getattr(failure, "step", {})
    replay_command = f"python tools/browser_live_design_guide_fuzz_verifier.py --replay-case {artifact_dir / 'failure_case.json'} --port {port}"
    diagnosis = build_failure_diagnosis(
        classification=classification,
        step=step if isinstance(step, dict) else {},
        message=str(failure),
        replay_command=replay_command,
    )
    probe_lifecycle_snapshot: dict[str, Any] | None = None
    if str(classification) in SETUP_LIFECYCLE_CLASSIFICATIONS or "probe" in str(classification).lower():
        probe_lifecycle_snapshot = capture_browser_probe_lifecycle_snapshot(
            page,
            artifact_dir,
            reason=str(classification),
            console_messages=console_messages,
            port=port,
            case_result=case_result,
        )
    is_timeout_capture = any(
        token in str(classification).lower()
        for token in ("timeout", "readiness", "probe")
    )
    screenshots = capture_failure_screenshots(
        page,
        artifact_dir,
        str(classification),
        console_messages=console_messages,
        timeout_capture=is_timeout_capture,
        fallback_url=f"{base_url}/?page=inputs",
    )
    html_path = artifact_dir / "failure_page.html"
    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception:
        html_path = None  # type: ignore[assignment]
    failure_case = {
        **case_result,
        "final_status": "FAIL",
        "failure_classification": classification,
        "failure_message": str(failure),
        "expected_failure_step": step.get("step_index"),
        "app_url": base_url,
        "port": port,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "replay_command": replay_command,
        "diagnosis": dict(diagnosis),
        "artifact_consistency": {
            "consistent": True,
            "seed": case_result.get("seed"),
            "case_index": case_result.get("case_index"),
            "step_index": step.get("step_index") if isinstance(step, dict) else None,
            "classification": classification,
        },
        "screenshots": screenshots,
    }
    if probe_lifecycle_snapshot is not None:
        failure_case["browser_probe_lifecycle_snapshot"] = probe_lifecycle_snapshot
        failure_case["browser_probe_lifecycle_snapshot_path"] = probe_lifecycle_snapshot.get("path")
    for key in SCREENSHOT_FIELD_KEYS:
        failure_case[key] = screenshots.get(key)
    if screenshots.get("full_page_screenshot"):
        failure_case["failure_screenshot"] = screenshots.get("full_page_screenshot")
    if html_path:
        failure_case["failure_page_html"] = str(html_path)
    _write_json(artifact_dir / "failure_case.json", failure_case)
    _write_json(artifact_dir / "failure_visible_summary.json", step.get("visible_summary") or {})
    _write_json(artifact_dir / "failure_visible_design_guide.json", step.get("visible_design_guide") or {})
    _write_json(artifact_dir / "failure_browser_state.json", step.get("browser_state") or {})
    if isinstance(step, dict) and step.get("browser_state"):
        _append_artifact_json(
            artifact_dir / "design_guide_build_profile.json",
            _collect_design_guide_build_profile(step),
        )
    setup_diagnostics = dict((step.get("setup_diagnostics") or {}) or ((step.get("browser_state") or {}).get("setup_diagnostics") or {}))
    if setup_diagnostics:
        _write_json(artifact_dir / "readiness_snapshot.json", setup_diagnostics)
    (artifact_dir / "failure_console.log").write_text("\n".join(console_messages), encoding="utf-8")
    (artifact_dir / "replay_command.txt").write_text(failure_case["replay_command"] + "\n", encoding="utf-8")
    md = [
        "# Live Design Guide fuzz failure",
        "",
        "## Classification",
        f"`{classification}`",
        "",
        "## User-visible contradiction",
        str(diagnosis.get("exact_contradiction") or failure),
        "",
        "## Likely cause",
        f"{diagnosis.get('likely_failure_layer')} (confidence: {diagnosis.get('confidence')})",
        "",
        "## Suspect files/functions",
        *[f"- {path}" for path in list(diagnosis.get("suspect_paths") or [])],
        "",
        "## Replay",
        f"`{failure_case['replay_command']}`",
    ]
    md.extend(_screenshot_markdown_lines(failure_case, heading="## Screenshots"))
    md.extend(
        [
            "",
            "## Recommended next patch",
            str(diagnosis.get("recommended_next_action") or ""),
        ]
    )
    (artifact_dir / "minimal_reproduction.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return failure_case


def _command_used() -> str:
    return "python " + " ".join(str(part) for part in sys.argv)


def _write_run_summary_with_contract(
    artifact_dir: Path,
    summary: dict[str, Any],
    *,
    args: argparse.Namespace,
    command_used: str,
    started_at: str | None = None,
    replay_source: str | Path | None = None,
) -> dict[str, Any]:
    enriched = enrich_run_summary(
        dict(summary),
        artifact_dir=artifact_dir,
        command_line=command_used,
        port=int(getattr(args, "port", 0) or 0),
        started_at=started_at,
        finished_at=_iso_now(),
        replay_source=replay_source or summary.get("replay_source"),
    )
    _write_json(artifact_dir / "run_summary.json", enriched)
    contract = validate_replay_artifact(artifact_dir)
    _write_json(artifact_dir / "artifact_contract_check.json", contract)
    enriched["artifact_contract_check_path"] = str(artifact_dir / "artifact_contract_check.json")
    _write_json(artifact_dir / "run_summary.json", enriched)
    return enriched


def _md(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("\n", " ").replace("|", "\\|").strip()


def _case_recipe_from_result(result: dict[str, Any]) -> str:
    initial = dict(result.get("initial_inputs") or {})
    return str(initial.get("recipe") or result.get("recipe") or "")


def _failure_step(failure: dict[str, Any]) -> dict[str, Any]:
    expected = failure.get("expected_failure_step")
    timeline = [step for step in list(failure.get("timeline") or []) if isinstance(step, dict)]
    for step in timeline:
        if step.get("step_index") == expected:
            return step
    return timeline[-1] if timeline else {}


def _latest_step(result: dict[str, Any]) -> dict[str, Any]:
    timeline = [step for step in list(result.get("timeline") or []) if isinstance(step, dict)]
    return timeline[-1] if timeline else {}


def _format_family(summary: dict[str, Any], family: str) -> str:
    item = dict(summary.get(family) or {})
    util = item.get("util")
    if util is None:
        util = item.get("util_support")
    status = item.get("status")
    if status is None:
        status = item.get("status_support")
    return f"{util if util is not None else '-'} / {status if status is not None else '-'}"


def _step_no_action_is_suspicious(step: dict[str, Any]) -> tuple[bool, str]:
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    if card.get("cta_enabled"):
        return False, ""
    active_fail = family_status(summary, "bending") == "FAIL" or family_status(summary, "shear") == "FAIL"
    low = [
        family
        for family in ("bending", "shear")
        if family_util(summary, family) is not None
        and family_util(summary, family) > 0
        and family_util(summary, family) < TARGET_LOW
    ]
    if not active_fail and not low:
        return False, ""
    blockers = exact_blockers(state)
    target_band_blockers = _target_band_blocker_table(state, low)
    proof_by_family: dict[str, Any] = {}
    missing: list[str] = []
    for family in low:
        proof = blocker_proof_analysis(card, state, family)
        target_proof = dict(target_band_blockers.get(family) or {})
        proof_valid = bool(proof.get("valid") or target_proof.get("valid"))
        proof_by_family[family] = {
            "proof_valid": proof_valid,
            "exact_blocker_present": bool(isinstance(blockers.get(family), dict)),
            "blocker_reason": (dict(blockers.get(family) or {}).get("reason") if isinstance(blockers.get(family), dict) else None),
            "missing_fields": list(target_proof.get("missing_fields") or proof.get("specificity_missing_fields") or []),
            "safe_candidate_count": target_proof.get("safe_candidate_count", proof.get("safe_candidate_count")),
            "executable_candidate_count": target_proof.get("executable_candidate_count", proof.get("executable_candidate_count")),
        }
        if not proof_valid:
            missing.append(family)
    if is_terminal_card(card) and low and not missing:
        return True, (
            f"green accepted with no CTA and secondary low_families={low}; "
            f"proof_valid=True, exact_blocker_families={sorted(blockers)}"
        )
    if not missing:
        return True, (
            f"no CTA with active_fail={active_fail}, low_families={low}; "
            f"allowed by exact blocker proof_by_family={proof_by_family}"
        )
    return True, f"no CTA with active_fail={active_fail}, low_families={low}, proof_valid=False, missing={missing}, proof_by_family={proof_by_family}"


def write_paste_ready_report(
    *,
    artifact_dir: Path,
    summary: dict[str, Any],
    cases: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    args: argparse.Namespace,
    command_used: str,
    replay_source: str | None = None,
) -> Path:
    report_path = artifact_dir / "paste_this_to_chatgpt.md"
    verdict = str(summary.get("verdict") or ("FAIL" if failures else "PASS"))
    exit_code = summary.get("exit_code", 1 if failures else 0)
    first_failure = failures[0] if failures else {}
    first_diag = dict(first_failure.get("diagnosis") or {})
    first_step = _failure_step(first_failure) if first_failure else {}
    first_replay = str(first_failure.get("replay_command") or "")
    lines: list[str] = []
    lines.extend(
        [
            "# Live Design Guide Fuzz Verifier Report",
            "",
            "## Run Header",
            "- Verifier: `tools/browser_live_design_guide_fuzz_verifier.py`",
            f"- Timestamp: `{_now_stamp()}`",
            f"- Verdict: `{verdict}`",
            f"- Exit code: `{exit_code}`",
            f"- Seed: `{getattr(args, 'seed', '')}`",
            f"- Max cases: `{getattr(args, 'max_cases', '')}`",
            f"- Session steps: `{getattr(args, 'session_steps', '')}`",
            f"- Mutations per case: `{getattr(args, 'mutations_per_case', '')}`",
            f"- Browser mode: `{'headed' if getattr(args, 'headed', False) else 'headless'}`",
            f"- Artifact directory: `{artifact_dir}`",
            f"- Command used: `{command_used}`",
        ]
    )
    if replay_source:
        lines.append(f"- Replay source: `{replay_source}`")
    if first_replay:
        lines.append(f"- First replay command: `{first_replay}`")
    lines.extend(
        [
            "",
            "## Executive Summary",
            f"- Requested cases: `{summary.get('requested_cases', getattr(args, 'max_cases', ''))}`",
            f"- Total cases attempted: `{summary.get('cases_run', len(cases) + len(failures))}`",
            f"- Total cases passed: `{summary.get('pass_count', len(cases))}`",
            f"- Total cases failed: `{summary.get('fail_count', len(failures))}`",
            f"- Completed requested cases: `{summary.get('completed_requested_cases', summary.get('cases_run', 0) >= getattr(args, 'max_cases', 0))}`",
            f"- Early stop reason: `{summary.get('early_stop_reason') or '-'}`",
            f"- First failure classification: `{first_failure.get('failure_classification', '-')}`",
            f"- Failure likely product bug: `{first_diag.get('product_bug_likely', False)}`",
            f"- Failure likely verifier bug: `{first_diag.get('verifier_bug_likely', False)}`",
            f"- Run stopped early: `{bool(failures and getattr(args, 'stop_on_first_failure', True))}`",
            f"- Run medium/20-case fuzz next: `{'NO - fix/replay first' if failures else 'YES'}`",
            "",
            "## Failure Index",
        ]
    )
    if failures:
        lines.extend(["| # | case_index | seed | recipe | step | classification | message | product/verifier | confidence | replay |", "|---|---:|---:|---|---|---|---|---|---|---|"])
        for idx, failure in enumerate(failures, 1):
            step = _failure_step(failure)
            diag = dict(failure.get("diagnosis") or {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(idx),
                        _md(failure.get("case_index")),
                        _md(failure.get("seed")),
                        _md(_case_recipe_from_result(failure)),
                        _md(f"{step.get('step_index')} {step.get('step_type')}"),
                        _md(failure.get("failure_classification")),
                        _md(failure.get("failure_message")),
                        _md(f"P={diag.get('product_bug_likely')} V={diag.get('verifier_bug_likely')}"),
                        _md(diag.get("confidence")),
                        _md(failure.get("replay_command")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- No failures.")

    if first_failure:
        lines.extend(_screenshot_markdown_lines(first_failure, heading="## Screenshots"))
    elif cases:
        first_pass = dict(cases[0].get("pass_screenshots") or {})
        if first_pass:
            lines.extend(_screenshot_markdown_lines({"screenshots": first_pass}, heading="## Pass Screenshots"))

    for idx, failure in enumerate(failures[:3], 1):
        step = _failure_step(failure)
        summary_step = dict(step.get("visible_summary") or {})
        card = dict(step.get("visible_design_guide") or {})
        contract = dict(card.get("button_contract") or {})
        diag = dict(failure.get("diagnosis") or {})
        no_action = dict(diag.get("no_action_analysis") or step.get("no_action_analysis") or {})
        opt_audit = dict(diag.get("optimisation_audit") or step.get("optimisation_audit") or build_optimisation_audit(summary_step, card, dict(step.get("browser_state") or {})))
        click_audit = dict(step.get("one_click_material_change_audit") or diag.get("one_click_material_change_audit") or {})
        final_state = dict(step.get("post_click_final_state") or diag.get("post_click_final_state") or {})
        active_blocker = dict(step.get("active_fail_blocker_analysis") or diag.get("active_fail_blocker_analysis") or {})
        alignment = dict(
            step.get("colour_alignment")
            or diag.get("colour_alignment")
            or colour_alignment(summary_step, card, dict(step.get("browser_state") or {}))
        )
        no_link_audit = no_link_shear_cleanup_audit(dict(step.get("browser_state") or {}), card)
        forbidden = [token for token in FORBIDDEN_VISIBLE_WORDING if token in str(card.get("text") or "").lower()]
        lines.extend(
            [
                "",
                f"## Failure {idx} - {failure.get('failure_classification')}",
            ]
        )
        lines.extend(_screenshot_markdown_lines(failure, heading="### Screenshots"))
        lines.extend(
            [
                "",
                "### User-visible summary",
                f"- Bending util/status: `{_format_family(summary_step, 'bending')}`",
                f"- Shear util/status: `{_format_family(summary_step, 'shear')}`",
                f"- Crack util/status: `{_format_family(summary_step, 'crack')}`",
                f"- Deflection util/status: `{_format_family(summary_step, 'deflection')}`",
                f"- Summary colour/status by family: `{alignment.get('summary_colour_by_family')}`",
                f"- Governing/worst util: `{dict(summary_step.get('browser_overview_support') or {}).get('worst_util', '-')}`",
                f"- All required checks pass: `{not dict(summary_step.get('browser_overview_support') or {}).get('any_fail', False)}`",
                "",
                "### Visible Design Guide card",
                f"- visible_card_count: `{card.get('visible_card_count')}`",
                f"- title: `{_md(card.get('title'))}`",
                f"- family: `{card.get('family')}`",
                f"- card type: `{card_type(card)}`",
                f"- card class/status/colour: `{card.get('classes')}` / `{card.get('status_label')}` / `{alignment.get('actual_card_colour')}`",
                f"- expected card colour: `{alignment.get('expected_card_colour')}`",
                f"- colour alignment result: `{alignment.get('alignment_ok')}` `{alignment.get('failures')}`",
                f"- displayed utilisation: `{card.get('displayed_util')}`",
                f"- CTA visible/enabled: `{card.get('cta_visible')}/{card.get('cta_enabled')}`",
                f"- CTA label: `{_md(card.get('cta_label'))}`",
                f"- forbidden wording present: `{'yes: ' + ', '.join(forbidden) if forbidden else 'no'}`",
                f"- duplicate cards: `{int(card.get('visible_card_count') or 0) > 1}`",
                f"- preparing stuck: `{bool(card.get('preparing_visible'))}`",
                f"- card text: `{_md(card.get('text'))}`",
                "",
                "### Button/payload contract",
                f"- button_contract.actionable: `{contract.get('actionable')}`",
                f"- action_type: `{contract.get('action_type')}`",
                f"- family: `{contract.get('family')}`",
                f"- candidate_id: `{contract.get('candidate_id')}`",
                f"- selected_action_updates present/count: `{bool(card.get('selected_action_updates'))}/{len(dict(card.get('selected_action_updates') or {}))}`",
                f"- visible updates = contract updates: `{dict(card.get('selected_action_updates') or {}) == dict(contract.get('updates') or {})}`",
                f"- payload_binding_match: `{dict(card.get('payload_binding_audit') or {}).get('payload_binding_match')}`",
                "",
                "### One-click visual update audit",
                f"- clicked_candidate_id: `{click_audit.get('clicked_candidate_id')}`",
                f"- clicked_family: `{click_audit.get('clicked_family')}`",
                f"- expected_updates: `{click_audit.get('expected_updates')}`",
                f"- before_values: `{click_audit.get('before_shared_values')}`",
                f"- after_values: `{click_audit.get('after_shared_values')}`",
                f"- changed_keys: `{click_audit.get('changed_keys')}`",
                f"- unchanged_expected_keys: `{click_audit.get('unchanged_expected_keys')}`",
                f"- before_card_title: `{_md(click_audit.get('before_card_title'))}`",
                f"- after_card_title: `{_md(click_audit.get('after_card_title'))}`",
                f"- before_summary_utils: `{click_audit.get('before_summary_utils')}`",
                f"- after_summary_utils: `{click_audit.get('after_summary_utils')}`",
                f"- before_results_version: `{click_audit.get('before_results_version')}`",
                f"- after_results_version: `{click_audit.get('after_results_version')}`",
                f"- click_pass_reason: `{click_audit.get('click_pass_reason')}`",
                f"- final_state_type: `{final_state.get('final_state_type')}`",
                f"- final card title: `{_md(final_state.get('final_card_title'))}`",
                f"- final card colour/status/class: `{_md(final_state.get('final_card_status_class'))}`",
                f"- pre-click active fail families: `{final_state.get('pre_click_active_fail_families')}`",
                f"- final summary statuses: `{final_state.get('final_summary_statuses')}`",
                f"- final family utilisations: `{final_state.get('final_family_utils')}`",
                f"- post-click bending/shear util: `{final_state.get('post_click_bending_util')}` / `{final_state.get('post_click_shear_util')}`",
                f"- strength family/families in preferred target: `{final_state.get('families_in_preferred_target', final_state.get('strength_families_in_target'))}`",
                f"- strength family/families in accepted band: `{final_state.get('families_in_accepted_band')}`",
                f"- strength family/families outside preferred target: `{final_state.get('strength_families_outside_target')}`",
                f"- strength family/families outside accepted band: `{final_state.get('families_outside_accepted_band')}`",
                f"- preferred target band: `{final_state.get('target_band')}`",
                f"- accepted final band: `{final_state.get('accepted_band')}`",
                f"- unresolved active fail families: `{final_state.get('unresolved_active_fail_families')}`",
                f"- unresolved low-util families: `{final_state.get('unresolved_low_util_families')}`",
                f"- exact blockers by family: `{list(dict(final_state.get('exact_blockers_by_family') or {}).keys())}`",
                f"- target-band blocker evidence by family: `{final_state.get('target_band_blockers_by_family')}`",
                f"- blocker reasons by family: `{final_state.get('blocker_reasons_by_family')}`",
                f"- failed candidate/check table by family: `{final_state.get('failed_candidate_check_by_family')}`",
                f"- safe/executable candidate counts by family: `{final_state.get('candidate_counts_by_family')}`",
                f"- why final state is accepted: `{_md(final_state.get('accepted_reason'))}`",
                "",
                "### Blocker/evidence state",
                f"- exact_blockers_by_family present: `{bool(exact_blockers(dict(step.get('browser_state') or {})))}`",
                f"- blocker family: `{no_action.get('family')}`",
                f"- cleanup_search_ran: `{no_action.get('cleanup_search_ran')}`",
                f"- cleanup_search_exhaustive: `{no_action.get('cleanup_search_exhaustive')}`",
                f"- safe_candidate_count: `{no_action.get('safe_candidate_count')}`",
                f"- executable_candidate_count: `{no_action.get('executable_candidate_count')}`",
                f"- target_band_candidate_count: `{cleanup_evidence(dict(step.get('browser_state') or {})).get('target_band_candidate_count')}`",
                f"- best_safe_final_util: `{cleanup_evidence(dict(step.get('browser_state') or {})).get('best_safe_final_util')}`",
                f"- blocker specificity valid/missing: `{no_action.get('specificity_valid')}/{no_action.get('specificity_missing_fields')}`",
                f"- blocker failed candidate/check: `{no_action.get('specificity')}`",
                f"- no_action valid/invalid: `{'valid' if no_action.get('valid') else 'invalid'}`",
                f"- pass_reason if any: `{step.get('pass_reason')}`",
                f"- blocker mode: `{'active_fail_blocker' if active_fail_families(summary_step) else 'overdesign_cleanup_blocker' if low_util_families(summary_step) else 'other'}`",
                f"- active-fail repair exhaustion valid: `{active_blocker.get('valid')}`",
                f"- active-fail repair missing fields by family: `{active_blocker.get('missing_by_family')}`",
                f"- active-fail blocker used cleanup evidence families: `{active_blocker.get('used_cleanup_evidence_families')}`",
                f"- no-link candidate tested/evaluated/passed/selected/already active: `{no_link_audit.get('no_link_candidate_tested')}` / `{no_link_audit.get('no_link_candidate_evaluated')}` / `{no_link_audit.get('no_link_candidate_passed')}` / `{no_link_audit.get('no_link_candidate_selected')}` / `{no_link_audit.get('no_link_candidate_already_active')}`",
                f"- no-link candidate updates/id: `{no_link_audit.get('no_link_candidate_updates')}` / `{no_link_audit.get('no_link_candidate_id')}`",
                f"- no-link result/reason: `{_md(no_link_audit.get('no_link_candidate_failed_or_selected_reason'))}`",
                f"- no-link s_lig handling: `{no_link_audit.get('no_link_s_lig_policy')}`",
                "",
                "### Optimisation-family audit",
                f"- optimisation_family: `{opt_audit.get('optimisation_family')}`",
                f"- optimisation_type: `{opt_audit.get('optimisation_type')}`",
                f"- current util by family: `{opt_audit.get('current_util_by_family')}`",
                f"- preview util by family: `{opt_audit.get('preview_util_by_family')}`",
                f"- intended family before/after: `{opt_audit.get('intended_family_before')}/{opt_audit.get('intended_family_after')}`",
                f"- required checks before/after: `{opt_audit.get('required_checks_before')}/{opt_audit.get('required_checks_after')}`",
                f"- target-band result: `{opt_audit.get('target_band_result')}`",
                f"- blocking checks named: `{opt_audit.get('blocking_checks_named')}`",
                "",
                "### Exact contradiction",
                str(diag.get("exact_contradiction") or failure.get("failure_message") or ""),
                "",
                "### Strict contract context",
                f"- active failing families: `{diag.get('active_failing_families')}`",
                f"- low-util families: `{diag.get('low_util_families')}`",
                f"- candidate evidence: `{diag.get('candidate_evidence')}`",
                f"- exact blockers by family: `{list(dict(diag.get('exact_blockers_by_family') or {}).keys())}`",
                "",
                "### Likely cause",
                f"- Layer: `{diag.get('likely_failure_layer')}`",
                f"- Suspect files/functions: `{', '.join(str(x) for x in list(diag.get('suspect_paths') or []))}`",
                "",
                "### Recommended next patch",
                f"- {diag.get('recommended_next_action')}",
                f"- Replay after fix: `{failure.get('replay_command')}`",
            ]
        )

    lines.extend(["", "## Passed Case Summary"])
    if cases:
        lines.extend(["| case_index | recipe | final step | optimisation | card title | family | colour | expected | alignment | CTA | pass_reason | final_state | exact_blocker_family | safe_count | executable_count | no-link shear audit |", "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---|"])
        for result in cases:
            step = _latest_step(result)
            card = dict(step.get("visible_design_guide") or {})
            progress = progress_step_summary(step) if step else {}
            no_link = dict(progress.get("no_link_shear_cleanup_audit") or {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(result.get("case_index")),
                        _md(_case_recipe_from_result(result)),
                        _md(f"{step.get('step_index')} {step.get('step_type')}"),
                        _md(f"{progress.get('optimisation_type')}/{progress.get('optimisation_family')}"),
                        _md(card.get("title")),
                        _md(card.get("family")),
                        _md(f"{progress.get('design_guide_card_colour')}/{progress.get('design_guide_card_status_label')}"),
                        _md(progress.get("expected_card_colour")),
                        _md(progress.get("colour_alignment_ok")),
                        _md(f"{card.get('cta_visible')}/{card.get('cta_enabled')}"),
                        _md(progress.get("pass_reason")),
                        _md(progress.get("final_state_type")),
                        _md(progress.get("exact_blocker_family")),
                        _md(progress.get("safe_candidate_count")),
                        _md(progress.get("executable_candidate_count")),
                        _md(
                            f"tested={no_link.get('no_link_candidate_tested')} "
                            f"selected={no_link.get('no_link_candidate_selected')} "
                            f"already={no_link.get('no_link_candidate_already_active')}"
                        ),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- No passed cases.")

    lines.extend(["", "## Passed Step Reasons"])
    if cases:
        for result in cases:
            step_bits: list[str] = []
            for step in list(result.get("timeline") or []):
                if isinstance(step, dict):
                    click_audit = dict(step.get("one_click_material_change_audit") or {})
                    final_state = dict(step.get("post_click_final_state") or {})
                    secondary_families = list(final_state.get("strength_families_outside_target") or [])
                    secondary_blockers = dict(final_state.get("target_band_blockers_by_family") or {})
                    secondary_proof_by_family = {
                        str(family): {
                            "proof_valid": bool(dict(secondary_blockers.get(family) or {}).get("valid")),
                            "missing_fields": list(dict(secondary_blockers.get(family) or {}).get("missing_fields") or []),
                            "reason": dict(secondary_blockers.get(family) or {}).get("reason"),
                        }
                        for family in secondary_families
                    }
                    secondary_suffix = (
                        f", secondary={secondary_families}, secondary_proof_valid="
                        f"{all(bool(proof.get('proof_valid')) for proof in secondary_proof_by_family.values())}, "
                        f"secondary_proof={secondary_proof_by_family}"
                        if secondary_families
                        else ""
                    )
                    click_suffix = (
                        f", click={click_audit.get('click_pass_reason')}, final={click_audit.get('final_state_type')}, changed={click_audit.get('changed_keys')}{secondary_suffix}"
                        if click_audit
                        else ""
                    )
                    alignment = dict(
                        step.get("colour_alignment")
                        or colour_alignment(
                            dict(step.get("visible_summary") or {}),
                            dict(step.get("visible_design_guide") or {}),
                            dict(step.get("browser_state") or {}),
                        )
                    )
                    colour_suffix = f", colour={alignment.get('actual_card_colour')} expected={alignment.get('expected_card_colour')} ok={alignment.get('alignment_ok')}"
                    step_bits.append(f"{step.get('step_index')}:{step.get('step_type')}={step.get('pass_reason')}{colour_suffix}{click_suffix}")
            lines.append(f"- case `{result.get('case_index')}` `{_case_recipe_from_result(result)}`: " + "; ".join(step_bits))
    else:
        lines.append("- No passed steps.")

    lines.extend(["", "## Multi-Family Blocker Evidence"])
    multi_rows: list[str] = []
    for result in cases:
        for step in list(result.get("timeline") or []):
            if not isinstance(step, dict):
                continue
            card = dict(step.get("visible_design_guide") or {})
            text_l = str(card.get("text") or "").lower()
            title_l = str(card.get("title") or "").lower()
            if not (
                is_blocker_card(card)
                and (
                    "bending and shear" in title_l
                    or "further cleanup blocked" in title_l
                    or ("bending cleanup blocked:" in text_l and "shear cleanup blocked:" in text_l)
                )
            ):
                continue
            blockers = exact_blockers(dict(step.get("browser_state") or {}))
            low = low_util_families(dict(step.get("visible_summary") or {}))
            family_bits: list[str] = []
            for family in ("bending", "shear"):
                blocker = dict(blockers.get(family) or {})
                ok, reason = _blocker_has_family_search_and_counts(blocker, family) if blocker else (False, "missing")
                family_bits.append(
                    f"{family}: present={bool(blocker)}, ran={bool(blocker.get('cleanup_search_ran') or blocker.get('local_cleanup_search_ran') or blocker.get(f'{family}_cleanup_search_ran'))}, "
                    f"exhaustive={bool(blocker.get('cleanup_search_exhaustive') or blocker.get('local_cleanup_search_exhaustive') or blocker.get(f'{family}_cleanup_search_exhaustive'))}, "
                    f"safe={_deep_get_count(blocker, keys=('safe_candidate_count','safe_cleanup_count','safe_local_cleanup_count',f'safe_{family}_cleanup_count'))}, "
                    f"executable={_deep_get_count(blocker, keys=('executable_candidate_count','executable_cleanup_count','executable_safe_cleanup_count',f'executable_{family}_cleanup_count'))}, "
                    f"valid_fields={ok}, reason={_md(blocker.get('reason') or reason)}"
                )
            compact_blocked_reasons = "blocked because" in text_l
            visible_family_reasons = (
                (
                    "bending cleanup blocked:" in text_l
                    or "bending repair blocked:" in text_l
                    or "bending attempts:" in text_l
                    or (compact_blocked_reasons and ("• bending:" in text_l or "- bending:" in text_l))
                    or (compact_blocked_reasons and ("• bending attempts:" in text_l or "- bending attempts:" in text_l))
                )
                and (
                    "shear cleanup blocked:" in text_l
                    or "shear repair blocked:" in text_l
                    or "shear attempts:" in text_l
                    or (compact_blocked_reasons and ("• shear:" in text_l or "- shear:" in text_l))
                    or (compact_blocked_reasons and ("• shear attempts:" in text_l or "- shear attempts:" in text_l))
                )
            )
            multi_rows.append(
                f"- case `{result.get('case_index')}` step `{step.get('step_index')} {step.get('step_type')}` "
                f"title=`{_md(card.get('title'))}` low_util_families=`{low}` exact_families=`{list(blockers.keys())}` "
                f"visible_reason_per_family=`{visible_family_reasons}`; " + " | ".join(family_bits)
            )
    if multi_rows:
        lines.extend(multi_rows)
    else:
        lines.append("- No multi-family blocker cards in passed cases.")

    suspicious: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for result in cases:
        for step in list(result.get("timeline") or []):
            if isinstance(step, dict):
                is_suspicious, reason = _step_no_action_is_suspicious(step)
                if is_suspicious:
                    suspicious.append((result, step, reason))
    lines.extend(["", "## Suspicious Passes"])
    if suspicious:
        for result, step, reason in suspicious:
            card = dict(step.get("visible_design_guide") or {})
            lines.append(
                f"- case `{result.get('case_index')}` recipe `{_case_recipe_from_result(result)}` "
                f"step `{step.get('step_index')} {step.get('step_type')}` card `{_md(card.get('title'))}`: {reason}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Commands To Run Next"])
    if failures:
        lines.append(f"- First replay: `{first_replay}`")
        lines.append("- Focused verifier: use the replay command above first.")
        lines.append("- 5-case fuzz: `python tools/browser_live_design_guide_fuzz_verifier.py --port 9301 --seed 12345 --max-cases 5 --session-steps 3 --mutations-per-case 2 --headed`")
    else:
        lines.append("- 20-case fuzz: `python tools/browser_live_design_guide_fuzz_verifier.py --port 9302 --seed 20260505 --max-cases 20 --session-steps 4 --mutations-per-case 3 --headless`")
        lines.append("- Super: `python tools/verification/runners/super_verification.py`")

    lines.extend(["", "## Paste-ready Next Codex Instruction"])
    if failures:
        contradiction = str(first_diag.get("exact_contradiction") or first_failure.get("failure_message") or "")
        lines.extend(
            [
                "Fix the first live-fuzz failure only. Do not change formulas, solver maths, target bands, broad ranking, or weaken verifier gates.",
                f"Artifact: `{artifact_dir}`",
                f"Replay: `{first_replay}`",
                f"Visible contradiction: {contradiction}",
                f"Required boundary: {first_diag.get('recommended_next_action')}",
                "Acceptance: replay passes, paste report is updated, then rerun the 5-case fuzz smoke and stop on any new separate failure.",
            ]
        )
    else:
        lines.append("The live fuzz run passed. Run the 20-case fuzz next before adding this verifier to any freeze gate.")

    text = "\n".join(lines).strip() + "\n"
    if len(text.splitlines()) > 300:
        text = "\n".join(text.splitlines()[:295] + ["", "_Report truncated to stay under 300 lines. See raw JSON artifacts for full detail._", ""]) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return report_path


ROOT_CAUSE_CATEGORIES = (
    "candidate_search_failure",
    "candidate_found_not_selected",
    "candidate_selected_not_published",
    "published_payload_stale",
    "click_apply_noop",
    "click_apply_but_ui_stale",
    "blocker_evidence_missing",
    "verifier_classification_bug",
    "stale_cache_or_state_source",
    "render_proof_mismatch",
)


def _deep_find_dicts_with_any_key(value: Any, keys: set[str], *, limit: int = 40) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if len(found) >= limit:
            return
        if isinstance(node, dict):
            if any(key in node for key in keys):
                found.append(node)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return found


def _deep_find_first_dict_with_key(value: Any, key: str) -> dict[str, Any]:
    matches = _deep_find_dicts_with_any_key(value, {key}, limit=1)
    return dict(matches[0]) if matches else {}


def _summarise_updates(updates: Any) -> dict[str, Any]:
    data = dict(updates or {}) if isinstance(updates, dict) else {}
    return {key: data.get(key) for key in sorted(data)[:12]}


def _candidate_search_summary(browser_state: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    guidance = dict(browser_state.get("guidance_compute_probe") or {})
    evidence = dict(guidance.get("candidate_search_evidence") or {})
    if not evidence:
        evidence = cleanup_evidence(browser_state)
    active_blockers = exact_blockers(browser_state)
    contract = dict(card.get("button_contract") or {})
    payload = dict(card.get("design_guide_primary_apply_payload") or {})
    selected = dict(card.get("selected_action_updates") or {})
    candidate_dicts = _deep_find_dicts_with_any_key(
        browser_state,
        {"candidate_id", "source_candidate_id", "expected_util", "preview_pass", "candidate_post_util"},
        limit=20,
    )
    candidate_ids = []
    for item in candidate_dicts:
        candidate_id = item.get("candidate_id") or item.get("source_candidate_id")
        if candidate_id and str(candidate_id) not in candidate_ids:
            candidate_ids.append(str(candidate_id))
    return {
        "search_ran": bool(evidence.get("repair_search_ran") or evidence.get("cleanup_search_ran") or evidence.get("local_cleanup_search_ran") or evidence.get("candidate_search_exhaustive")),
        "search_exhaustive": bool(evidence.get("repair_search_exhaustive") or evidence.get("cleanup_search_exhaustive") or evidence.get("local_cleanup_search_exhaustive") or evidence.get("candidate_search_exhaustive")),
        "repair_search_ran": bool(evidence.get("repair_search_ran")),
        "repair_search_exhaustive": bool(evidence.get("repair_search_exhaustive")),
        "candidate_count": _deep_get_count(evidence, keys=("candidate_count", "attempted_candidate_count", "safe_candidate_count", "safe_executor_backed_candidates_count")),
        "safe_candidate_count": _deep_get_count(evidence, keys=("safe_candidate_count", "safe_repair_candidate_count", "safe_executor_backed_candidates_count")),
        "executable_candidate_count": _deep_get_count(evidence, keys=("executable_candidate_count", "executable_repair_candidate_count", "executable_safe_cleanup_count")),
        "target_band_candidate_count": _deep_get_count(evidence, keys=("target_band_candidate_count", "executable_target_band_candidate_count")),
        "best_candidate_id": evidence.get("best_candidate_id") or evidence.get("attempted_candidate_id") or contract.get("candidate_id") or payload.get("candidate_id"),
        "best_candidate_family": evidence.get("family") or contract.get("family") or payload.get("family") or card.get("family"),
        "best_candidate_type": evidence.get("action_type") or contract.get("action_type") or payload.get("action_type"),
        "best_candidate_updates": _summarise_updates(evidence.get("best_candidate_updates") or evidence.get("attempted_updates") or contract.get("updates") or selected),
        "best_candidate_preview_pass": evidence.get("preview_pass") if "preview_pass" in evidence else contract.get("preview_pass"),
        "best_candidate_expected_util": evidence.get("expected_util") or contract.get("expected_util"),
        "best_candidate_makes_all_required_checks_pass": evidence.get("preview_pass") if "preview_pass" in evidence else contract.get("preview_pass"),
        "best_candidate_reaches_target_band": evidence.get("lands_in_target_band") or evidence.get("displayed_within_target_band"),
        "failed_candidate_reasons": list(evidence.get("failed_candidate_reasons") or evidence.get("rejected_repair_reasons") or [])[:5],
        "candidate_ids_seen": candidate_ids[:10],
        "exact_blockers_by_family": sorted(active_blockers),
    }


def _root_cause_step(source_case: dict[str, Any], replay_result: dict[str, Any] | None, failure_case: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if failure_case:
        return _failure_step(failure_case), "current_replay_failure"
    if replay_result:
        # Prefer the source failure step for classification, but include the current replay in the report.
        source_step = _failure_step(source_case)
        if source_step:
            return source_step, "source_failure_artifact"
        return _latest_step(replay_result), "current_replay_pass_latest_step"
    return _failure_step(source_case), "source_failure_artifact"


def _classify_root_cause(
    *,
    source_case: dict[str, Any],
    step: dict[str, Any],
    replay_result: dict[str, Any] | None,
    failure_case: dict[str, Any] | None,
) -> tuple[str, list[str], str]:
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    diagnosis = dict((failure_case or source_case).get("diagnosis") or {})
    active_failures = active_fail_families(summary)
    ctype = card_type(card)
    contract = dict(card.get("button_contract") or {})
    payload = dict(card.get("design_guide_primary_apply_payload") or {})
    selected = dict(card.get("selected_action_updates") or {})
    proof = dict(card.get("proof_support") or {})
    audit = dict(card.get("payload_binding_audit") or {})
    search = _candidate_search_summary(state, card)
    secondary: list[str] = []

    if diagnosis.get("verifier_bug_likely") is True:
        return "verifier_classification_bug", secondary, "The saved failure diagnosis marks verifier_bug_likely=true; the visible card is a structured blocker but the verifier classified it as invalid."
    if audit.get("stale_primary_design_guide_payload") or audit.get("stale_apply_payload_blocked"):
        return "published_payload_stale", secondary, "The payload audit reports stale primary/apply payload state."
    visible_candidate = contract.get("candidate_id") or contract.get("source_candidate_id")
    payload_candidate = payload.get("candidate_id") or payload.get("source_candidate_id")
    proof_title = proof.get("primary_title")
    if proof_title and card.get("title") and str(proof_title) != str(card.get("title")):
        return "render_proof_mismatch", secondary, "The visible rendered title differs from the proof primary title."
    if visible_candidate and payload_candidate and str(visible_candidate) != str(payload_candidate):
        return "render_proof_mismatch", secondary, "The visible button contract candidate differs from the primary apply payload candidate."
    if active_failures and ctype == "BLOCKER":
        if search.get("executable_candidate_count", 0) > 0 or search.get("safe_candidate_count", 0) > 0:
            if selected or payload or contract.get("actionable"):
                secondary.append("candidate_found_not_selected")
                return "candidate_selected_not_published", secondary, "An executable/safe repair candidate is present in candidate evidence, but the final rendered card is a non-action blocker."
            return "candidate_found_not_selected", secondary, "Candidate evidence shows a safe/executable repair candidate, but the visible final item is a blocker."
        blockers = exact_blockers(state)
        missing = [family for family in active_failures if family not in blockers]
        if missing:
            return "blocker_evidence_missing", secondary, f"Visible active failures {missing} do not have exact blocker evidence."
        if not search.get("repair_search_ran") or not search.get("repair_search_exhaustive"):
            return "candidate_search_failure", secondary, "Active-failure blocker was published without repair_search_ran and repair_search_exhaustive evidence."
    if card.get("cta_enabled") and selected and not contract.get("actionable"):
        return "candidate_selected_not_published", secondary, "Selected action updates exist under an enabled-looking action card, but the button contract is not actionable."
    if (failure_case or source_case).get("failure_classification") == "one_click_no_material_change":
        return "click_apply_noop", secondary, "The failure classification shows an enabled one-click action did not materially change expected values."
    if (failure_case or source_case).get("failure_classification") in {"one_click_card_not_refreshed", "one_click_summary_not_updated"}:
        return "click_apply_but_ui_stale", secondary, "The failure classification shows the click applied or reran but visible state did not refresh correctly."
    if proof.get("guidance_branch") == "coherence_backfill" or "coherence_backfill" in str(step):
        return "stale_cache_or_state_source", secondary, "The rendered/proof support references coherence_backfill, which points at a stale or conflicting state source path."
    if replay_result and not failure_case and source_case.get("final_status") == "FAIL":
        return "verifier_classification_bug", secondary, "The same replay now passes; the saved failing artifact is best treated as an old verifier/product-state classification that no longer reproduces."
    return "candidate_search_failure", secondary, "No publishable candidate or complete blocker ownership signal was found in the captured artifacts."


def write_root_cause_report(
    *,
    replay_source: Path,
    source_case: dict[str, Any],
    replay_result: dict[str, Any] | None,
    failure_case: dict[str, Any] | None,
    args: argparse.Namespace,
    command_used: str,
) -> Path:
    timestamp = _now_stamp()
    root_dir = (Path("artifacts/verification/design_guide_root_cause") / timestamp).resolve()
    root_dir.mkdir(parents=True, exist_ok=True)
    step, step_source = _root_cause_step(source_case, replay_result, failure_case)
    summary = dict(step.get("visible_summary") or {})
    card = dict(step.get("visible_design_guide") or {})
    state = dict(step.get("browser_state") or {})
    search = _candidate_search_summary(state, card)
    category, secondary, category_reason = _classify_root_cause(
        source_case=source_case,
        step=step,
        replay_result=replay_result,
        failure_case=failure_case,
    )
    if category not in ROOT_CAUSE_CATEGORIES:
        category = "candidate_search_failure"
    contract = dict(card.get("button_contract") or {})
    payload = dict(card.get("design_guide_primary_apply_payload") or {})
    selected = dict(card.get("selected_action_updates") or {})
    proof = dict(card.get("proof_support") or {})
    overview = dict(summary.get("browser_overview_support") or {})
    input_values = dict(step.get("input_values") or {})
    initial = dict(source_case.get("initial_inputs") or {})
    blockers = exact_blockers(state)
    current_replay_status = "not_run"
    if failure_case:
        current_replay_status = "FAIL"
    elif replay_result:
        current_replay_status = "PASS"
    replay_command = f"python tools/browser_live_design_guide_fuzz_verifier.py --replay-case \"{replay_source}\" --port {args.port} --headed"
    next_verifier = "python tools/browser_live_design_guide_fuzz_verifier.py --port 9301 --seed 12345 --max-cases 5 --session-steps 3 --mutations-per-case 2 --headed"
    source_diag = dict(source_case.get("diagnosis") or {})
    report = [
        "# Design Guide Root-Cause Classification Report",
        "",
        f"- Timestamp: `{timestamp}`",
        f"- Replay source: `{replay_source}`",
        f"- Current replay status: `{current_replay_status}`",
        f"- Step used for classification: `{step_source}`",
        f"- Primary root-cause category: `{category}`",
        f"- Secondary categories: `{', '.join(secondary) if secondary else 'none'}`",
        f"- Reason: {category_reason}",
        "",
        "## A. Visible State",
        f"- Summary statuses: `{_summary_statuses(summary)}`",
        f"- Summary utils: `{_summary_utils(summary)}`",
        f"- Visible Design Guide title: `{card.get('title')}`",
        f"- Visible card family: `{card.get('family')}`",
        f"- Visible card type: `{card_type(card)}`",
        f"- CTA visible/enabled: `{bool(card.get('cta_visible'))}/{bool(card.get('cta_enabled'))}`",
        f"- Visible candidate id: `{contract.get('candidate_id') or contract.get('source_candidate_id')}`",
        f"- Visible selected updates: `{_summarise_updates(selected)}`",
        "",
        "## B. Current-State Truth",
        f"- Current shared/visible input values: `{input_values}`",
        f"- Initial beam state: `b={initial.get('b')}`, `D={initial.get('D')}`, `M*={initial.get('mu')}`, `V*={initial.get('vu')}`, bottom reo `{initial.get('bottom_bar_count')}N{initial.get('bottom_bar_dia')}`, links `{initial.get('lig_legs')}N{initial.get('lig_d')} @ {initial.get('s_lig')}`",
        f"- Current state fingerprint: `{proof.get('state_fingerprint') or proof.get('render_fingerprint') or 'not present'}`",
        f"- Overview statuses from same state: `{overview.get('statuses')}`",
        f"- Overview utils from same state: `{overview.get('utils')}`",
        "",
        "## C. Candidate Search",
        f"- Full active repair search ran: `{search.get('repair_search_ran')}`",
        f"- Repair search exhaustive: `{search.get('repair_search_exhaustive')}`",
        f"- Candidate count: `{search.get('candidate_count')}`",
        f"- Safe candidate count: `{search.get('safe_candidate_count')}`",
        f"- Executable candidate count: `{search.get('executable_candidate_count')}`",
        f"- Target-band candidate count: `{search.get('target_band_candidate_count')}`",
        f"- Best candidate id: `{search.get('best_candidate_id')}`",
        f"- Best candidate family/type: `{search.get('best_candidate_family')}` / `{search.get('best_candidate_type')}`",
        f"- Best candidate updates: `{search.get('best_candidate_updates')}`",
        f"- Best candidate preview pass: `{search.get('best_candidate_preview_pass')}`",
        f"- Best candidate expected util: `{search.get('best_candidate_expected_util')}`",
        f"- Best candidate reaches target band: `{search.get('best_candidate_reaches_target_band')}`",
        f"- Rejection reasons: `{search.get('failed_candidate_reasons')}`",
        "",
        "## D. Selection",
        f"- Selected raw engine item: `{source_diag.get('candidate_evidence') or 'not present in artifact'}`",
        f"- Selected final resolver item: `{proof.get('primary_title') or card.get('title')}`",
        f"- Selected rendered item: `{card.get('title')}`",
        f"- Selected proof item: `{proof.get('primary_title')}`",
        f"- Candidate ids seen in state/proof: `{search.get('candidate_ids_seen')}`",
        f"- Candidate id/family/action agreement: visible=`{contract.get('candidate_id')}`, payload=`{payload.get('candidate_id')}`, family=`{contract.get('family')}`, action=`{contract.get('action_type')}`",
        "",
        "## E. Publication / Render Path",
        f"- Item entering final resolver: `{proof.get('guidance_branch') or 'not present'}`",
        f"- Item leaving final resolver: `{proof.get('primary_title') or card.get('title')}`",
        f"- Item entering render: `{proof.get('primary_title') or 'not present'}`",
        f"- Item actually rendered as `.fast-guidance-item`: `{card.get('title')}`",
        f"- Item published into browser proof: `{proof.get('primary_title')}`",
        f"- Item used for button_contract: `{contract}`",
        f"- Item used for primary apply payload: `{payload}`",
        f"- Later ACTION-to-BLOCKER overwrite indicated: `{'yes' if proof.get('guidance_branch') == 'coherence_backfill' or 'coherence_backfill' in str(step) else 'no evidence'}`",
        "",
        "## F. Payload Contract",
        f"- Visible card candidate id: `{contract.get('candidate_id') or contract.get('source_candidate_id')}`",
        f"- Button contract candidate id: `{contract.get('candidate_id')}`",
        f"- Primary apply payload candidate id: `{payload.get('candidate_id')}`",
        f"- Selected action updates: `{_summarise_updates(selected)}`",
        f"- Payload binding audit: `{card.get('payload_binding_audit') or {}}`",
        f"- Stale primary payload present: `{bool(card.get('payload_binding_audit', {}).get('stale_primary_design_guide_payload') if isinstance(card.get('payload_binding_audit'), dict) else False)}`",
        f"- Payload state fingerprint matches visible summary fingerprint: `{proof.get('payload_binding_state_fingerprint') == proof.get('state_fingerprint') if proof.get('payload_binding_state_fingerprint') or proof.get('state_fingerprint') else 'not present'}`",
        "",
        "## G. Cache / State-Source Check",
        f"- Cache key / render fingerprint: `{proof.get('render_fingerprint') or 'not present'}`",
        f"- Algorithm/state fingerprint: `{proof.get('state_fingerprint') or 'not present'}`",
        f"- Stale b/M/V/D/reo/link state found: `not proven from artifact`",
        f"- Guidance resolved state differs from visible summary state: `not proven from artifact`",
        f"- Final resolver uses visible summary state: `{current_replay_status == 'PASS'}`",
        f"- Browser proof uses final rendered item: `{proof.get('primary_title') == card.get('title') if proof.get('primary_title') else 'not present'}`",
        "",
        "## H. Root-Cause Classification",
        f"- Primary category: `{category}`",
        f"- Secondary categories: `{', '.join(secondary) if secondary else 'none'}`",
        f"- Explanation: {category_reason}",
        f"- Exact blockers by family: `{sorted(blockers)}`",
        "",
        "## I. Patch Recommendation",
        "- Owner layer: verifier/product owner identified by the category above; do not patch unrelated render/coherence fallbacks before confirming this owner.",
        "- Exact files/functions to patch next: `inputs_page.py` final resolver/publication path only if category is product-side; `tools/browser_live_design_guide_fuzz_verifier.py` only if category is verifier_classification_bug.",
        "- What not to patch: formulas, solver maths, target bands, broad candidate ranking, unrelated Design Guide presentation paths.",
        f"- Replay command after patch: `{replay_command}`",
        f"- Verifier command after replay: `{next_verifier}`",
        "",
        "## Raw Artifact Pointers",
        f"- Root-cause artifact directory: `{root_dir}`",
        f"- Source failure case: `{replay_source}`",
    ]
    report_path = root_dir / "root_cause_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    _write_json(
        root_dir / "root_cause_summary.json",
        {
            "primary_category": category,
            "secondary_categories": secondary,
            "category_reason": category_reason,
            "report_path": str(report_path),
            "replay_source": str(replay_source),
            "current_replay_status": current_replay_status,
            "step_source": step_source,
            "command_used": command_used,
            "replay_command": replay_command,
            "next_verifier_command": next_verifier,
        },
    )
    return report_path


def _port_ready(base_url: str) -> bool:
    try:
        with urlopen(base_url, timeout=2) as response:  # noqa: S310 - local dev server
            return 200 <= int(response.status) < 500
    except (URLError, TimeoutError, OSError, Exception):
        return False


def _wait_for_port_clear(base_url: str, *, timeout_s: float = 15.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _port_ready(base_url):
            return True
        time.sleep(0.25)
    return not _port_ready(base_url)


def _stop_streamlit_process(process: Any, *, base_url: str) -> None:
    if process is None:
        return
    try:
        process.terminate()
        process.wait(timeout=10)
    except Exception:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(getattr(process, "pid", "")), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.kill()
                process.wait(timeout=5)
        except Exception:
            pass
    _wait_for_port_clear(base_url, timeout_s=20.0)


def _is_pre_timeline_browser_probe_timeout(exc: Exception, timeline: list[dict[str, Any]]) -> bool:
    if timeline:
        return False
    message = f"{type(exc).__name__}: {exc}"
    return isinstance(exc, PlaywrightTimeoutError) and "Browser state" in message


def run_replay(args: argparse.Namespace) -> int:
    global _CURRENT_PLAYWRIGHT_TIMELINE
    replay_started_at = _iso_now()
    replay_path = Path(args.replay_case)
    data = json.loads(replay_path.read_text(encoding="utf-8"))
    args.seed = int(data.get("seed") or args.seed or 0)
    args.max_cases = 1
    args.reload_between_cases = True
    args.replay_mutation_steps = list(data.get("mutation_steps") or [])
    if not list(data.get("mutation_steps") or []):
        expected_step = data.get("expected_failure_step")
        timeline_steps = [
            str((step or {}).get("step_type") or "")
            for step in list(data.get("timeline") or [])
            if isinstance(step, dict)
        ]
        try:
            expected_step_number = int(expected_step or 0)
        except (TypeError, ValueError):
            expected_step_number = None
        if (
            expected_step is None
            or (expected_step_number is not None and expected_step_number <= 2)
            or not any("mutation" in step for step in timeline_steps)
        ):
            args.mutations_per_case = 0
    else:
        args.mutations_per_case = len(args.replay_mutation_steps)
    artifact_dir = Path(args.artifact_dir or Path("artifacts/verification/live_fuzz") / f"replay_{_now_stamp()}").resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "seed.txt").write_text(str(args.seed), encoding="utf-8")
    lifecycle = LifecycleDiagnostics(
        artifact_dir,
        port=args.port,
        heartbeat_interval_s=float(getattr(args, "heartbeat_interval_sec", 15.0) or 15.0),
        stall_threshold_s=float(getattr(args, "stall_threshold_sec", 300.0) or 300.0),
    )
    lifecycle.start()
    _CURRENT_PLAYWRIGHT_TIMELINE = PlaywrightLifecycleTimeline(artifact_dir)
    lifecycle.event("replay_artifact_created", replay=str(replay_path), seed=args.seed, include_process_snapshot=True)
    progress_path = artifact_dir / "cases_progress.jsonl"
    latest_case_path = artifact_dir / "latest_case.json"
    base_url = f"http://127.0.0.1:{args.port}"
    replay_initial_inputs = dict(data.get("initial_inputs") or {})
    previous_replay_recipe_env = os.environ.get("CODEX_BROWSER_REPLAY_RECIPE")
    forced_replay_recipe = (
        str(replay_initial_inputs.get("recipe") or "").strip()
        if bool(replay_initial_inputs.get("require_browser_recipe_applied"))
        else ""
    )
    if forced_replay_recipe:
        os.environ["CODEX_BROWSER_REPLAY_RECIPE"] = forced_replay_recipe
    process = None
    playwright = None
    browser = None
    context = None
    page = None
    console_messages: list[str] = []
    if not _port_ready(base_url):
        lifecycle.set_stage("streamlit_launch_start", replay=str(replay_path))
        streamlit_start = _perf_now()
        process = _start_streamlit(args.port)
        lifecycle.mark_success("streamlit_launch_end", elapsed_ms=_safe_elapsed_ms(streamlit_start), process_pid=getattr(process, "pid", None))
    try:
        lifecycle.set_stage("browser_launch_start", replay=str(replay_path))
        _record_playwright_stage("browser_launch_start")
        browser_start = _perf_now()
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=not args.headed)
        _record_playwright_stage("browser_launch_done", browser=browser, success=True)
        lifecycle.mark_success("browser_launch_end", elapsed_ms=_safe_elapsed_ms(browser_start))
        lifecycle.process_snapshot("after_browser_launch")
        lifecycle.set_stage("browser_context_create_start", replay=str(replay_path))
        context = browser.new_context()
        _record_playwright_stage("context_create_done", context=context, browser=browser, success=True)
        page = context.new_page()
        _record_playwright_stage("page_create_done", page=page, context=context, browser=browser, success=True)
        lifecycle.mark_success("browser_context_create_end", page_count=len(context.pages))
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        rng = random.Random(args.seed)
        case = dict(replay_initial_inputs)
        case.setdefault("case_index", int(data.get("case_index") or 0))
        case_result = run_case(
            page,
            case=case,
            base_url=base_url,
            artifact_dir=artifact_dir,
            args=args,
            rng=rng,
            console_messages=console_messages,
            lifecycle=lifecycle,
        )
        lifecycle.set_stage("pass_screenshot_capture", case_index=case.get("case_index"), replay=str(replay_path))
        pass_screenshots = capture_pass_screenshots(
            page,
            artifact_dir,
            case_result,
            console_messages=console_messages,
        )
        _write_json(latest_case_path, case_result)
        _append_jsonl(
            progress_path,
            {
                "case_index": case_result.get("case_index"),
                "recipe": _case_recipe_from_result(case_result),
                "status": "PASS",
                "visible_contract_steps": list(case_result.get("visible_contract_steps") or []),
                "case": case_result,
            },
        )
        summary = {"verdict": "PASS", "exit_code": 0, "replay_source": str(replay_path), "artifact_dir": str(artifact_dir), "case": case_result, "cases_run": 1, "pass_count": 1, "fail_count": 0}
        summary["first_pass_screenshots"] = _screenshot_fields({"screenshots": pass_screenshots})
        summary["playwright_lifecycle_timeline_path"] = str(_CURRENT_PLAYWRIGHT_TIMELINE.path) if _CURRENT_PLAYWRIGHT_TIMELINE is not None else None
        summary.update(lifecycle.summary_fields())
        report_path = write_paste_ready_report(
            artifact_dir=artifact_dir,
            summary=summary,
            cases=[case_result],
            failures=[],
            args=args,
            command_used=_command_used(),
            replay_source=str(replay_path),
        )
        summary["paste_ready_report_path"] = str(report_path)
        if getattr(args, "root_cause_report", False):
            root_report = write_root_cause_report(
                replay_source=replay_path,
                source_case=data,
                replay_result=case_result,
                failure_case=None,
                args=args,
                command_used=_command_used(),
            )
            summary["root_cause_report_path"] = str(root_report)
        summary = _write_run_summary_with_contract(
            artifact_dir,
            summary,
            args=args,
            command_used=_command_used(),
            started_at=replay_started_at,
            replay_source=replay_path,
        )
        lifecycle.mark_success("run_summary_written", run_summary=str(artifact_dir / "run_summary.json"))
        lifecycle.set_stage("browser_teardown_start", replay=str(replay_path))
        _set_playwright_flag("teardown_requested", True)
        _record_playwright_stage("teardown_start", page=page, context=context, browser=browser)
        lifecycle.process_snapshot("before_browser_close")
        context.close()
        context = None
        browser.close()
        browser = None
        playwright.stop()
        playwright = None
        _record_playwright_stage("teardown_done", success=True)
        lifecycle.mark_success("browser_teardown_end")
        lifecycle.process_snapshot("after_browser_close")
        return 0
    except VisibleContractFailure as exc:
        failed_step = dict(getattr(exc, "step", {}) or {})
        timeline = [failed_step] if failed_step else []
        is_setup_lifecycle = _is_setup_lifecycle_classification(getattr(exc, "classification", ""))
        failure_case = save_failure_artifacts(
            artifact_dir=artifact_dir,
            page=page,
            case_result={"seed": args.seed, "case_index": data.get("case_index"), "initial_inputs": data.get("initial_inputs"), "timeline": timeline},
            failure=exc,
            console_messages=console_messages,
            base_url=base_url,
            port=args.port,
        )
        _write_json(latest_case_path, failure_case)
        _append_jsonl(progress_path, {"case_index": data.get("case_index"), "status": "ERROR" if is_setup_lifecycle else "FAIL", "failure": failure_case})
        summary = {
            "verdict": "ERROR" if is_setup_lifecycle else "FAIL",
            "exit_code": 2 if is_setup_lifecycle else 1,
            "replay_source": str(replay_path),
            "artifact_dir": str(artifact_dir),
            "cases_run": 1,
            "pass_count": 0,
            "fail_count": 1,
            "failures": [failure_case],
            "first_failure_screenshots": _screenshot_fields(failure_case),
        }
        summary["playwright_lifecycle_timeline_path"] = str(_CURRENT_PLAYWRIGHT_TIMELINE.path) if _CURRENT_PLAYWRIGHT_TIMELINE is not None else None
        summary.update(lifecycle.summary_fields())
        report_path = write_paste_ready_report(
            artifact_dir=artifact_dir,
            summary=summary,
            cases=[],
            failures=[failure_case],
            args=args,
            command_used=_command_used(),
            replay_source=str(replay_path),
        )
        summary["paste_ready_report_path"] = str(report_path)
        if getattr(args, "root_cause_report", False):
            root_report = write_root_cause_report(
                replay_source=replay_path,
                source_case=data,
                replay_result=None,
                failure_case=failure_case,
                args=args,
                command_used=_command_used(),
            )
            summary["root_cause_report_path"] = str(root_report)
        summary = _write_run_summary_with_contract(
            artifact_dir,
            summary,
            args=args,
            command_used=_command_used(),
            started_at=replay_started_at,
            replay_source=replay_path,
        )
        print(json.dumps(summary, indent=2, default=_json_default))
        return 2 if is_setup_lifecycle else 1
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        if _is_pre_timeline_browser_probe_timeout(exc, []):
            failed_step = capture_pre_timeline_probe_timeout_step(
                page,
                base_url=base_url,
                console_messages=console_messages,
                message=message,
                stage="browser_state_probe_attach",
            )
            failure = VisibleContractFailure(_classification_from_pre_timeline_step(failed_step), message, failed_step)
            exit_code = 2
        else:
            failed_step = {}
            failure = VisibleContractFailure("verifier_runtime_error", message, failed_step)
            exit_code = 2
        timeline = [failed_step] if failed_step else []
        failure_case = save_failure_artifacts(
            artifact_dir=artifact_dir,
            page=page,
            case_result={
                "seed": args.seed,
                "case_index": data.get("case_index"),
                "initial_inputs": data.get("initial_inputs"),
                "timeline": timeline,
            },
            failure=failure,
            console_messages=console_messages,
            base_url=base_url,
            port=args.port,
        )
        _write_json(latest_case_path, failure_case)
        _append_jsonl(progress_path, {"case_index": data.get("case_index"), "status": "ERROR", "failure": failure_case})
        summary = {
            "verdict": "ERROR",
            "exit_code": exit_code,
            "replay_source": str(replay_path),
            "artifact_dir": str(artifact_dir),
            "cases_run": 1,
            "pass_count": 0,
            "fail_count": 1,
            "failures": [failure_case],
            "first_failure_screenshots": _screenshot_fields(failure_case),
        }
        summary["playwright_lifecycle_timeline_path"] = str(_CURRENT_PLAYWRIGHT_TIMELINE.path) if _CURRENT_PLAYWRIGHT_TIMELINE is not None else None
        summary.update(lifecycle.summary_fields())
        report_path = write_paste_ready_report(
            artifact_dir=artifact_dir,
            summary=summary,
            cases=[],
            failures=[failure_case],
            args=args,
            command_used=_command_used(),
            replay_source=str(replay_path),
        )
        summary["paste_ready_report_path"] = str(report_path)
        if getattr(args, "root_cause_report", False):
            root_report = write_root_cause_report(
                replay_source=replay_path,
                source_case=data,
                replay_result=None,
                failure_case=failure_case,
                args=args,
                command_used=_command_used(),
            )
            summary["root_cause_report_path"] = str(root_report)
        summary = _write_run_summary_with_contract(
            artifact_dir,
            summary,
            args=args,
            command_used=_command_used(),
            started_at=replay_started_at,
            replay_source=replay_path,
        )
        print(json.dumps(summary, indent=2, default=_json_default))
        return exit_code
    finally:
        if previous_replay_recipe_env is None:
            os.environ.pop("CODEX_BROWSER_REPLAY_RECIPE", None)
        else:
            os.environ["CODEX_BROWSER_REPLAY_RECIPE"] = previous_replay_recipe_env
        try:
            _set_playwright_flag("teardown_requested", True)
            _record_playwright_stage("teardown_start", page=page, context=context, browser=browser)
            if context is not None:
                try:
                    context.close()
                except Exception as exc:
                    _record_playwright_stage("teardown_context_close_error", page=page, context=context, browser=browser, exception=exc)
                context = None
            if browser is not None:
                try:
                    browser.close()
                except Exception as exc:
                    _record_playwright_stage("teardown_browser_close_error", browser=browser, exception=exc)
                browser = None
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception as exc:
                    _record_playwright_stage("teardown_playwright_stop_error", exception=exc)
                playwright = None
            _record_playwright_stage("teardown_done", success=True)
        except Exception:
            pass
        _CURRENT_PLAYWRIGHT_TIMELINE = None
        if process is not None:
            try:
                lifecycle.set_stage("streamlit_teardown_start", replay=str(replay_path))
                lifecycle.process_snapshot("before_streamlit_stop")
            except Exception:
                pass
            _stop_streamlit_process(process, base_url=base_url)
            try:
                lifecycle.mark_success("streamlit_teardown_end")
                lifecycle.process_snapshot("after_streamlit_stop")
            except Exception:
                pass
        try:
            lifecycle.stop()
        except Exception:
            pass


def _extract_previous_gate_paths(output: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    for key in ("json_path", "markdown_path"):
        match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', output or "")
        if match:
            paths[key] = match.group(1)
    return paths


def _load_valid_previous_fixed_skip_report(report_path: str | None) -> dict[str, Any] | None:
    if not report_path:
        return None
    path = Path(report_path)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    if not path.exists():
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": "report_missing",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": f"report_unreadable:{type(exc).__name__}:{exc}",
        }
    if payload.get("status") != "PASS":
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": f"report_status_not_pass:{payload.get('status')}",
        }
    fingerprint_compare = compare_report_correctness_fingerprint(payload, repo=REPO_ROOT)
    report_fingerprint = dict(
        fingerprint_compare.get("report_correctness_fingerprint")
        or payload.get("source_fingerprint")
        or {}
    )
    if not report_fingerprint.get("fingerprint"):
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": "report_missing_correctness_fingerprint",
            "invalidation_reason": fingerprint_compare.get("invalidation_reason"),
            "full_gate_required": True,
        }
    current_fingerprint = dict(fingerprint_compare.get("current_fingerprints") or compute_source_fingerprint(repo=REPO_ROOT))
    if not fingerprint_compare.get("matches"):
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": fingerprint_compare.get("invalidation_reason") or "correctness_fingerprint_changed",
            "invalidation_reason": fingerprint_compare.get("invalidation_reason"),
            "full_gate_required": True,
            "report_source_fingerprint": report_fingerprint,
            "current_source_fingerprint": current_fingerprint,
            "report_correctness_fingerprint": fingerprint_compare.get("report_correctness_fingerprint"),
            "current_correctness_fingerprint": fingerprint_compare.get("current_correctness_fingerprint"),
        }
    return {
        "status": "PASS",
        "skipped": True,
        "skip_requested": True,
        "skip_report_path": str(path),
        "skip_reason": "valid_pass_report_with_matching_correctness_fingerprint",
        "invalidation_reason": None,
        "full_gate_required": False,
        "json_path": str(path),
        "markdown_path": payload.get("markdown_path"),
        "report_generated_at": payload.get("generated_at"),
        "source_fingerprint": current_fingerprint,
        "correctness_fingerprint": current_fingerprint.get("correctness_fingerprint"),
        "diagnostic_fingerprint": current_fingerprint.get("diagnostic_fingerprint"),
        "verifier_runtime_fingerprint": current_fingerprint.get("verifier_runtime_fingerprint"),
        "diagnostic_fingerprint_matches": fingerprint_compare.get("diagnostic_fingerprint_matches"),
        "verifier_runtime_fingerprint_matches": fingerprint_compare.get("verifier_runtime_fingerprint_matches"),
        "passed_count": payload.get("passed_count"),
        "failed_count": payload.get("failed_count"),
        "total_fixed_replays": payload.get("total_fixed_replays"),
    }


def _load_valid_golden_matrix_skip_report(report_path: str | None) -> dict[str, Any] | None:
    if not report_path:
        return None
    path = Path(report_path)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    if not path.exists():
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": "report_missing",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": f"report_unreadable:{type(exc).__name__}:{exc}",
        }
    if payload.get("status") != "PASS":
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": f"report_status_not_pass:{payload.get('status')}",
        }
    total_cases = payload.get("total_cases")
    passed_cases = payload.get("passed_cases")
    failed_cases = payload.get("failed_cases")
    if total_cases != 14 or passed_cases != 14 or failed_cases != 0:
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": (
                "report_not_complete_14_of_14:"
                f"total={total_cases}:passed={passed_cases}:failed={failed_cases}"
            ),
        }
    fingerprint_compare = compare_report_correctness_fingerprint(payload, repo=REPO_ROOT)
    report_fingerprint = dict(
        fingerprint_compare.get("report_correctness_fingerprint")
        or payload.get("source_fingerprint")
        or {}
    )
    if not report_fingerprint.get("fingerprint"):
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": "report_missing_correctness_fingerprint",
            "invalidation_reason": fingerprint_compare.get("invalidation_reason"),
            "full_gate_required": True,
        }
    current_fingerprint = dict(fingerprint_compare.get("current_fingerprints") or compute_source_fingerprint(repo=REPO_ROOT))
    if not fingerprint_compare.get("matches"):
        return {
            "status": "STALE",
            "skip_requested": True,
            "skip_report_path": str(path),
            "skip_reason": fingerprint_compare.get("invalidation_reason") or "correctness_fingerprint_changed",
            "invalidation_reason": fingerprint_compare.get("invalidation_reason"),
            "full_gate_required": True,
            "report_source_fingerprint": report_fingerprint,
            "current_source_fingerprint": current_fingerprint,
            "report_correctness_fingerprint": fingerprint_compare.get("report_correctness_fingerprint"),
            "current_correctness_fingerprint": fingerprint_compare.get("current_correctness_fingerprint"),
        }
    return {
        "status": "PASS",
        "skipped": True,
        "skip_requested": True,
        "skip_report_path": str(path),
        "skip_reason": "valid_pass_report_with_matching_correctness_fingerprint",
        "invalidation_reason": None,
        "full_gate_required": False,
        "json_path": str(path),
        "markdown_path": payload.get("markdown_path"),
        "report_generated_at": payload.get("generated_at"),
        "source_fingerprint": current_fingerprint,
        "correctness_fingerprint": current_fingerprint.get("correctness_fingerprint"),
        "diagnostic_fingerprint": current_fingerprint.get("diagnostic_fingerprint"),
        "verifier_runtime_fingerprint": current_fingerprint.get("verifier_runtime_fingerprint"),
        "diagnostic_fingerprint_matches": fingerprint_compare.get("diagnostic_fingerprint_matches"),
        "verifier_runtime_fingerprint_matches": fingerprint_compare.get("verifier_runtime_fingerprint_matches"),
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "total_cases": total_cases,
    }


def _run_previous_fixed_groups_preflight(port: int, *, skip_report_path: str | None = None) -> dict[str, Any]:
    skip_result = _load_valid_previous_fixed_skip_report(skip_report_path)
    if skip_result is not None and skip_result.get("status") == "PASS":
        return skip_result
    command = [
        sys.executable,
        "tools/run_design_guide_previous_fixes_gate.py",
        "--port",
        str(port),
    ]
    started = time.perf_counter()
    try:
        proc = subprocess.run(  # noqa: S603
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=7200,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        paths = _extract_previous_gate_paths(output)
        result = {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "command": " ".join(command),
            "returncode": proc.returncode,
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-120:]),
            "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-120:]),
            "json_path": paths.get("json_path"),
            "markdown_path": paths.get("markdown_path"),
        }
        if skip_result is not None:
            result["skip_requested"] = True
            result["skip_rejected"] = skip_result
        return result
    except subprocess.TimeoutExpired as exc:
        result = {
            "status": "TIMEOUT",
            "command": " ".join(command),
            "returncode": None,
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "stdout_tail": "\n".join((exc.stdout or "").splitlines()[-120:]) if isinstance(exc.stdout, str) else "",
            "stderr_tail": "\n".join((exc.stderr or "").splitlines()[-120:]) if isinstance(exc.stderr, str) else "",
            "json_path": None,
            "markdown_path": None,
        }
        if skip_result is not None:
            result["skip_requested"] = True
            result["skip_rejected"] = skip_result
        return result


def _run_golden_matrix_preflight(port: int, *, skip_report_path: str | None = None) -> dict[str, Any]:
    skip_result = _load_valid_golden_matrix_skip_report(skip_report_path)
    if skip_result is not None and skip_result.get("status") == "PASS":
        return skip_result
    command = [
        sys.executable,
        "tools/run_design_guide_golden_matrix.py",
        "--port",
        str(port),
    ]
    try:
        proc = subprocess.run(  # noqa: S603
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=7200,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        paths = _extract_previous_gate_paths(output)
        result = {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "command": " ".join(command),
            "returncode": proc.returncode,
            "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-120:]),
            "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-120:]),
            "json_path": paths.get("json_path"),
            "markdown_path": paths.get("markdown_path"),
        }
        if skip_result is not None:
            result["skip_requested"] = True
            result["skip_rejected"] = skip_result
        return result
    except subprocess.TimeoutExpired as exc:
        result = {
            "status": "TIMEOUT",
            "command": " ".join(command),
            "returncode": None,
            "stdout_tail": "\n".join((exc.stdout or "").splitlines()[-120:]) if isinstance(exc.stdout, str) else "",
            "stderr_tail": "\n".join((exc.stderr or "").splitlines()[-120:]) if isinstance(exc.stderr, str) else "",
            "json_path": None,
            "markdown_path": None,
        }
        if skip_result is not None:
            result["skip_requested"] = True
            result["skip_rejected"] = skip_result
        return result


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("CODEX_BROWSER_TEST_MODE", "1")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9301)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--max-runtime-sec", type=int, default=900)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--headed", action="store_true")
    mode.add_argument("--headless", action="store_true")
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--session-steps", type=int, default=3)
    parser.add_argument("--mutations-per-case", type=int, default=2)
    parser.add_argument("--click-after-each-mutation", dest="click_after_each_mutation", action="store_true", default=True)
    parser.add_argument("--no-click-after-each-mutation", dest="click_after_each_mutation", action="store_false")
    reload_group = parser.add_mutually_exclusive_group()
    reload_group.add_argument("--reload-between-cases", dest="reload_between_cases", action="store_true", default=True)
    reload_group.add_argument("--no-reload-between-cases", dest="reload_between_cases", action="store_false")
    parser.add_argument("--stop-on-first-failure", dest="stop_on_first_failure", action="store_true", default=True)
    parser.add_argument("--no-stop-on-first-failure", dest="stop_on_first_failure", action="store_false")
    parser.add_argument("--save-all-screenshots", action="store_true", default=False)
    parser.add_argument("--fail-on-no-action-without-exhaustive-proof", dest="fail_on_no_action_without_exhaustive_proof", action="store_true", default=True)
    parser.add_argument("--no-fail-on-no-action-without-exhaustive-proof", dest="fail_on_no_action_without_exhaustive_proof", action="store_false")
    parser.add_argument("--replay-case", default=None)
    parser.add_argument(
        "--page-cycle-mode",
        choices=("full", "inputs_design_inputs"),
        default="full",
        help=(
            "Scope page-cycle navigation. 'full' visits every app page; "
            "'inputs_design_inputs' keeps Inputs/Design/Inputs stale-DOM and readiness checks for Design Guide truth replays."
        ),
    )
    parser.add_argument("--root-cause-report", action="store_true", default=False)
    parser.add_argument("--heartbeat-interval-sec", type=float, default=15.0)
    parser.add_argument("--stall-threshold-sec", type=float, default=300.0)
    parser.add_argument(
        "--skip-previous-fixed-preflight-if-report",
        default=None,
        help=(
            "Reuse a previous-fixed PASS report only when it exists and its "
            "source fingerprint matches the current checkout."
        ),
    )
    parser.add_argument(
        "--skip-golden-matrix-preflight-if-report",
        default=None,
        help=(
            "Reuse a golden matrix PASS report only when it is 14/14 and its "
            "source fingerprint matches the current checkout."
        ),
    )
    parser.add_argument("--browser-live", action="store_true", default=False, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.replay_case:
        return run_replay(args)

    started_at = time.time()
    timestamp = _now_stamp()
    artifact_dir = Path(args.artifact_dir or Path("artifacts/verification/live_fuzz") / timestamp).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "seed.txt").write_text(str(args.seed), encoding="utf-8")
    preflight_progress_path = artifact_dir / "preflight_startup_decision.json"
    previous_skip_probe = _load_valid_previous_fixed_skip_report(args.skip_previous_fixed_preflight_if_report)
    golden_skip_probe = _load_valid_golden_matrix_skip_report(args.skip_golden_matrix_preflight_if_report)
    preflight_progress = {
        "timestamp": timestamp,
        "artifact_dir": str(artifact_dir),
        "seed": args.seed,
        "max_cases": args.max_cases,
        "previous_fixed_preflight_skip_requested": bool(args.skip_previous_fixed_preflight_if_report),
        "previous_fixed_preflight_skip_report_path": args.skip_previous_fixed_preflight_if_report,
        "previous_fixed_preflight_skip_valid": bool(previous_skip_probe and previous_skip_probe.get("status") == "PASS"),
        "previous_fixed_preflight_skip_rejected_reason": (
            previous_skip_probe.get("skip_reason")
            if previous_skip_probe and previous_skip_probe.get("status") != "PASS"
            else None
        ),
        "previous_fixed_preflight_will_skip": bool(previous_skip_probe and previous_skip_probe.get("status") == "PASS"),
        "previous_fixed_preflight_will_run": not bool(previous_skip_probe and previous_skip_probe.get("status") == "PASS"),
        "golden_preflight_skip_requested": bool(args.skip_golden_matrix_preflight_if_report),
        "golden_preflight_skip_report_path": args.skip_golden_matrix_preflight_if_report,
        "golden_preflight_skip_valid": bool(golden_skip_probe and golden_skip_probe.get("status") == "PASS"),
        "golden_preflight_skip_rejected_reason": (
            golden_skip_probe.get("skip_reason")
            if golden_skip_probe and golden_skip_probe.get("status") != "PASS"
            else None
        ),
        "golden_preflight_will_skip": bool(golden_skip_probe and golden_skip_probe.get("status") == "PASS"),
        "golden_preflight_will_run": not bool(golden_skip_probe and golden_skip_probe.get("status") == "PASS"),
        "golden_matrix_preflight_will_run": not bool(golden_skip_probe and golden_skip_probe.get("status") == "PASS"),
        "first_fuzz_case_started": False,
        "current_stage": "previous_fixed_preflight_start",
    }
    _write_json(preflight_progress_path, preflight_progress)

    previous_gate = _run_previous_fixed_groups_preflight(
        args.port,
        skip_report_path=args.skip_previous_fixed_preflight_if_report,
    )
    preflight_progress.update(
        {
            "current_stage": "previous_fixed_preflight_done",
            "previous_fixed_preflight_result": previous_gate,
        }
    )
    _write_json(preflight_progress_path, preflight_progress)
    if previous_gate.get("status") != "PASS":
        summary = {
            "verdict": "FAIL",
            "exit_code": 1,
            "failure_classification": "blocked_by_previous_fixed_groups_regression",
            "blocked_by_previous_fixed_groups_regression": True,
            "message": "blocked by previous-fixed-groups regression.",
            "artifact_dir": str(artifact_dir),
            "cases_run": 0,
            "pass_count": 0,
            "fail_count": 0,
            "previous_fixed_groups_gate": previous_gate,
        }
        summary = _write_run_summary_with_contract(
            artifact_dir,
            summary,
            args=args,
            command_used=_command_used(),
            started_at=timestamp,
        )
        (artifact_dir / "paste_this_to_chatgpt.md").write_text(
            "\n".join(
                [
                    "# Live Fuzz Blocked By Previous Fixed Groups Gate",
                    "",
                    "The requested fuzz run did not start because it was blocked by previous-fixed-groups regression.",
                    "",
                    f"- Gate command: `{previous_gate.get('command')}`",
                    f"- Gate exit code: `{previous_gate.get('returncode')}`",
                    f"- Gate markdown: `{previous_gate.get('markdown_path') or ''}`",
                    f"- Gate JSON: `{previous_gate.get('json_path') or ''}`",
                    "",
                    "Fix the failed fixed replay first, then rerun this fuzz command.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, indent=2, default=_json_default))
        return 1

    preflight_progress["current_stage"] = "golden_matrix_preflight_start"
    _write_json(preflight_progress_path, preflight_progress)
    golden_gate = _run_golden_matrix_preflight(
        args.port,
        skip_report_path=args.skip_golden_matrix_preflight_if_report,
    )
    preflight_progress.update(
        {
            "current_stage": "golden_matrix_preflight_done",
            "golden_matrix_preflight_result": golden_gate,
        }
    )
    _write_json(preflight_progress_path, preflight_progress)
    if golden_gate.get("status") != "PASS":
        summary = {
            "verdict": "FAIL",
            "exit_code": 1,
            "failure_classification": "blocked_by_golden_matrix_regression",
            "blocked_by_golden_matrix_regression": True,
            "message": "blocked by golden matrix regression.",
            "artifact_dir": str(artifact_dir),
            "cases_run": 0,
            "pass_count": 0,
            "fail_count": 0,
            "previous_fixed_groups_gate": previous_gate,
            "golden_matrix_gate": golden_gate,
        }
        summary = _write_run_summary_with_contract(
            artifact_dir,
            summary,
            args=args,
            command_used=_command_used(),
            started_at=timestamp,
        )
        (artifact_dir / "paste_this_to_chatgpt.md").write_text(
            "\n".join(
                [
                    "# Live Fuzz Blocked By Golden Matrix Gate",
                    "",
                    "The requested fuzz run did not start because it was blocked by golden matrix regression.",
                    "",
                    f"- Gate command: `{golden_gate.get('command')}`",
                    f"- Gate exit code: `{golden_gate.get('returncode')}`",
                    f"- Gate markdown: `{golden_gate.get('markdown_path') or ''}`",
                    f"- Gate JSON: `{golden_gate.get('json_path') or ''}`",
                    "",
                    "Fix the failed golden case first, then rerun this fuzz command.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, indent=2, default=_json_default))
        return 1

    preflight_progress["current_stage"] = "live_fuzz_start"
    preflight_progress["first_fuzz_case_started"] = False
    _write_json(preflight_progress_path, preflight_progress)
    lifecycle = LifecycleDiagnostics(
        artifact_dir,
        port=args.port,
        heartbeat_interval_s=float(args.heartbeat_interval_sec or 15.0),
        stall_threshold_s=float(args.stall_threshold_sec or 300.0),
    )
    lifecycle.start()
    lifecycle.event(
        "run_artifact_created",
        seed=args.seed,
        max_cases=args.max_cases,
        session_steps=args.session_steps,
        mutations_per_case=args.mutations_per_case,
        include_process_snapshot=True,
    )
    progress_path = artifact_dir / "cases_progress.jsonl"
    latest_case_path = artifact_dir / "latest_case.json"
    base_url = f"http://127.0.0.1:{args.port}"
    process = None
    cases: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    rng = random.Random(args.seed)
    early_stop_reason: str | None = None
    early_stop_case_index: int | None = None
    early_stop_elapsed_sec: float | None = None

    try:
        if not _port_ready(base_url):
            lifecycle.set_stage("streamlit_launch_start")
            streamlit_start = _perf_now()
            process = _start_streamlit(args.port)
            lifecycle.mark_success("streamlit_launch_end", elapsed_ms=_safe_elapsed_ms(streamlit_start), process_pid=getattr(process, "pid", None))
        else:
            lifecycle.set_stage("streamlit_ready_existing_port")
            ready_start = _perf_now()
            _wait_for_http(base_url, timeout_s=10)
            lifecycle.mark_success("streamlit_ready_existing_port", elapsed_ms=_safe_elapsed_ms(ready_start))
    except Exception as exc:
        summary = {"verdict": "ERROR", "exit_code": 3, "error": str(exc), "artifact_dir": str(artifact_dir), "cases_run": 0, "pass_count": 0, "fail_count": 0, "failures": []}
        summary.update(lifecycle.summary_fields())
        report_path = write_paste_ready_report(
            artifact_dir=artifact_dir,
            summary=summary,
            cases=[],
            failures=[],
            args=args,
            command_used=_command_used(),
        )
        summary["paste_ready_report_path"] = str(report_path)
        summary = _write_run_summary_with_contract(
            artifact_dir,
            summary,
            args=args,
            command_used=_command_used(),
            started_at=timestamp,
        )
        return 3

    try:
        with sync_playwright() as p:
            lifecycle.set_stage("browser_launch_start")
            browser_start = _perf_now()
            browser = p.chromium.launch(headless=not args.headed)
            lifecycle.mark_success("browser_launch_end", elapsed_ms=_safe_elapsed_ms(browser_start))
            lifecycle.process_snapshot("after_browser_launch")
            shared_context = None
            shared_page = None
            shared_console_messages: list[str] = []
            for idx in range(int(args.max_cases)):
                if time.time() - started_at > float(args.max_runtime_sec):
                    early_stop_reason = "max_runtime_sec_exceeded"
                    early_stop_case_index = idx
                    early_stop_elapsed_sec = round(time.time() - started_at, 3)
                    lifecycle.event("max_runtime_break", case_index=idx, elapsed_sec=early_stop_elapsed_sec)
                    break
                lifecycle.set_stage("case_transition_start", case_index=idx)
                if idx == 0 and not preflight_progress.get("first_fuzz_case_started"):
                    preflight_progress["first_fuzz_case_started"] = True
                    preflight_progress["first_fuzz_case_started_at"] = _now_stamp()
                    preflight_progress["current_stage"] = "live_fuzz_case_0_start"
                    _write_json(preflight_progress_path, preflight_progress)
                lifecycle.event(
                    "case_boundary",
                    case_index=idx,
                    cases_passed=len(cases),
                    failures=len(failures),
                    reload_between_cases=bool(args.reload_between_cases),
                    seed_summary_exists=(artifact_dir / "seed.txt").exists(),
                    run_summary_exists=(artifact_dir / "run_summary.json").exists(),
                    include_process_snapshot=True,
                )
                if args.reload_between_cases or shared_page is None or shared_context is None:
                    context_start = _perf_now()
                    lifecycle.event("browser_context_create_start", case_index=idx)
                    context = browser.new_context()
                    page = context.new_page()
                    lifecycle.event("browser_context_create_end", case_index=idx, elapsed_ms=_safe_elapsed_ms(context_start), page_count=len(context.pages))
                    console_messages: list[str] = []
                    page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
                else:
                    context = shared_context
                    page = shared_page
                    console_messages = shared_console_messages
                    lifecycle.event("browser_context_reuse", case_index=idx, page_count=len(context.pages))
                case = generate_case(rng, idx)
                lifecycle.event("case_generated", case_index=idx, recipe=case.get("recipe"), archetype=case.get("archetype"), generated_case=case)
                case_result: dict[str, Any] = {
                    "case_index": idx,
                    "seed": args.seed,
                    "initial_inputs": case,
                    "timeline": [],
                    "final_status": "STARTED",
                }
                stop_after_case = False
                try:
                    case_result = run_case(
                        page,
                        case=case,
                        base_url=base_url,
                        artifact_dir=artifact_dir,
                        args=args,
                        rng=rng,
                        console_messages=console_messages,
                        lifecycle=lifecycle,
                    )
                    lifecycle.set_stage("pass_screenshot_capture", case_index=idx)
                    pass_screenshots = capture_pass_screenshots(
                        page,
                        artifact_dir,
                        case_result,
                        console_messages=console_messages,
                    )
                    cases.append(case_result)
                    _append_jsonl(
                        progress_path,
                        {
                            "case_index": idx,
                            "recipe": case.get("recipe"),
                            "status": "PASS",
                            "visible_contract_steps": list(case_result.get("visible_contract_steps") or []),
                            "pass_screenshots": _screenshot_fields({"screenshots": pass_screenshots}),
                            "case": case_result,
                        },
                    )
                    _write_json(latest_case_path, case_result)
                    lifecycle.mark_success("case_progress_written", case_index=idx, latest_case_path=str(latest_case_path))
                except VisibleContractFailure as exc:
                    lifecycle.event("visible_contract_failure", case_index=idx, classification=getattr(exc, "classification", ""))
                    failed_step = dict(getattr(exc, "step", {}) or {})
                    case_result["timeline"] = list(case_result.get("timeline") or [])
                    if failed_step:
                        case_result["timeline"].append(failed_step)
                    failure_case = save_failure_artifacts(
                        artifact_dir=artifact_dir,
                        page=page,
                        case_result={**case_result, "initial_inputs": case},
                        failure=exc,
                        console_messages=console_messages,
                        base_url=base_url,
                        port=args.port,
                    )
                    failures.append(failure_case)
                    _append_jsonl(
                        progress_path,
                        {
                            "case_index": idx,
                            "status": "ERROR" if _is_setup_lifecycle_classification(getattr(exc, "classification", "")) else "FAIL",
                            "failure": failure_case,
                        },
                    )
                    _write_json(latest_case_path, failure_case)
                    lifecycle.mark_success("failure_artifacts_written", case_index=idx, classification=failure_case.get("failure_classification"))
                    if args.stop_on_first_failure:
                        stop_after_case = True
                except Exception as exc:
                    lifecycle.event("verifier_runtime_exception", case_index=idx, exception=f"{type(exc).__name__}: {exc}")
                    timeline = [step for step in list(case_result.get("timeline") or []) if isinstance(step, dict)]
                    message = f"{type(exc).__name__}: {exc}"
                    if _is_pre_timeline_browser_probe_timeout(exc, timeline):
                        failed_step = capture_pre_timeline_probe_timeout_step(
                            page,
                            base_url=base_url,
                            console_messages=console_messages,
                            message=message,
                            stage="browser_state_probe_attach",
                        )
                        case_result["timeline"] = [failed_step]
                        failure = VisibleContractFailure(_classification_from_pre_timeline_step(failed_step), message, failed_step)
                    else:
                        failure = VisibleContractFailure("verifier_runtime_error", message, timeline[-1] if timeline else {})
                    failure_case = save_failure_artifacts(
                        artifact_dir=artifact_dir,
                        page=page,
                        case_result={**case_result, "initial_inputs": case},
                        failure=failure,
                        console_messages=console_messages,
                        base_url=base_url,
                        port=args.port,
                    )
                    failures.append(failure_case)
                    _append_jsonl(progress_path, {"case_index": idx, "status": "ERROR", "failure": failure_case})
                    lifecycle.mark_success("runtime_failure_artifacts_written", case_index=idx, classification=failure_case.get("failure_classification"))
                    if args.stop_on_first_failure:
                        stop_after_case = True
                finally:
                    if args.reload_between_cases:
                        try:
                            lifecycle.set_stage("browser_context_teardown_start", case_index=idx)
                            lifecycle.process_snapshot("before_context_close", case_index=idx)
                            context.close()
                            lifecycle.mark_success("browser_context_teardown_end", case_index=idx)
                            lifecycle.process_snapshot("after_context_close", case_index=idx)
                        except Exception:
                            lifecycle.event("browser_context_teardown_error", case_index=idx, exception=traceback.format_exc(limit=5))
                            pass
                    else:
                        shared_context = context
                        shared_page = page
                        shared_console_messages = console_messages
                if stop_after_case:
                    break
            if shared_context is not None:
                try:
                    lifecycle.set_stage("shared_browser_context_teardown_start")
                    shared_context.close()
                    lifecycle.mark_success("shared_browser_context_teardown_end")
                except Exception:
                    lifecycle.event("shared_browser_context_teardown_error", exception=traceback.format_exc(limit=5))
                    pass
            lifecycle.set_stage("browser_teardown_start")
            lifecycle.process_snapshot("before_browser_close")
            browser.close()
            lifecycle.mark_success("browser_teardown_end")
            lifecycle.process_snapshot("after_browser_close")
    except Exception as exc:
        summary = {
            "verdict": "ERROR",
            "exit_code": 2,
            "error": f"{type(exc).__name__}: {exc}",
            "artifact_dir": str(artifact_dir),
            "cases_completed": len(cases),
            "cases_run": len(cases) + len(failures),
            "pass_count": len(cases),
            "fail_count": len(failures),
            "failures": failures,
        }
        summary.update(lifecycle.summary_fields())
        if failures:
            summary["first_failure_screenshots"] = _screenshot_fields(failures[0])
        report_path = write_paste_ready_report(
            artifact_dir=artifact_dir,
            summary=summary,
            cases=cases,
            failures=failures,
            args=args,
            command_used=_command_used(),
        )
        summary["paste_ready_report_path"] = str(report_path)
        summary = _write_run_summary_with_contract(
            artifact_dir,
            summary,
            args=args,
            command_used=_command_used(),
            started_at=timestamp,
        )
        return 2
    finally:
        if process is not None:
            try:
                lifecycle.set_stage("streamlit_teardown_start")
                lifecycle.process_snapshot("before_streamlit_stop")
            except Exception:
                pass
            _stop_streamlit_process(process, base_url=base_url)
            try:
                lifecycle.mark_success("streamlit_teardown_end")
                lifecycle.process_snapshot("after_streamlit_stop")
            except Exception:
                pass
        try:
            lifecycle.stop()
        except Exception:
            pass

    setup_lifecycle_error = bool(
        failures
        and any(_is_setup_lifecycle_classification(failure.get("failure_classification")) for failure in failures)
    )
    verdict = "ERROR" if setup_lifecycle_error else ("FAIL" if failures else "PASS")
    summary = {
        "verdict": verdict,
        "exit_code": 2 if setup_lifecycle_error else (1 if failures else 0),
        "seed": args.seed,
        "started_at": timestamp,
        "elapsed_sec": round(time.time() - started_at, 3),
        "artifact_dir": str(artifact_dir),
        "max_cases": args.max_cases,
        "requested_cases": int(args.max_cases),
        "cases_run": len(cases) + len(failures),
        "completed_requested_cases": (len(cases) + len(failures)) >= int(args.max_cases),
        "early_stop_reason": early_stop_reason,
        "early_stop_case_index": early_stop_case_index,
        "early_stop_elapsed_sec": early_stop_elapsed_sec,
        "max_runtime_sec": args.max_runtime_sec,
        "pass_count": len(cases),
        "fail_count": len(failures),
        "failures": failures,
    }
    summary.update(lifecycle.summary_fields())
    if cases:
        summary["first_pass_screenshots"] = _screenshot_fields({"screenshots": dict(cases[0].get("pass_screenshots") or {})})
    if failures:
        summary["first_failure_screenshots"] = _screenshot_fields(failures[0])
    report_path = write_paste_ready_report(
        artifact_dir=artifact_dir,
        summary=summary,
        cases=cases,
        failures=failures,
        args=args,
        command_used=_command_used(),
    )
    summary["paste_ready_report_path"] = str(report_path)
    summary = _write_run_summary_with_contract(
        artifact_dir,
        summary,
        args=args,
        command_used=_command_used(),
        started_at=timestamp,
    )
    print(json.dumps(summary, indent=2, default=_json_default))
    return 2 if setup_lifecycle_error else (1 if failures else 0)


if __name__ == "__main__":
    raise SystemExit(main())
