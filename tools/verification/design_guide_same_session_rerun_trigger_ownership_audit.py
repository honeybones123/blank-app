"""Same-session rerun-trigger ownership audit for Inputs smoothness.

Proof-only browser/live verifier. It triggers Streamlit's visible Rerun control
without changing inputs, then compares render timing, rerun markers, stable
authority hashes, pending flags, and visible panel state. It does not change
rendering, publication, CTA/apply, family runtimes, visible wording, or
engineering behaviour.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_smoothness_profile import (  # noqa: E402
    _extract_counter_metrics,
    _extract_latest_design_guide_timing,
)
from tools.verification.design_guide_rerun_trigger_source_profile import (  # noqa: E402
    _dom_snapshot,
    _state_summary,
)
from tools.verification.design_guide_same_session_no_change_rerun_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _click_streamlit_rerun,
    _load_browser_state_prefer_final_debug,
    _wait_for_full_publication_state,
    _wait_for_streamlit_idle,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({key: value for key, value in params.items() if value is not None})}"


def _compact(value: Any, *, depth: int = 4, max_items: int = 20) -> Any:
    if depth <= 0:
        if isinstance(value, (dict, list, tuple, set)):
            return f"<{type(value).__name__}>"
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                out["..."] = f"{len(value) - max_items} more"
                break
            out[str(key)] = _compact(item, depth=depth - 1, max_items=max_items)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [_compact(item, depth=depth - 1, max_items=max_items) for item in seq[:max_items]]
        if len(seq) > max_items:
            out.append(f"... {len(seq) - max_items} more")
        return out
    return value


def _timing_events(state: dict[str, Any]) -> list[dict[str, Any]]:
    probe = dict(state.get("render_timing_probe") or {})
    events = list(probe.get("events") or probe.get("recent_events") or [])
    if not events:
        events = list(probe.get("events_tail") or [])
    rows = []
    for event in events[-80:]:
        if isinstance(event, dict):
            rows.append(dict(event))
    return rows


def _event_key(event: dict[str, Any]) -> str:
    return _stable_hash(
        {
            "name": event.get("name"),
            "rerun_seq": event.get("rerun_seq"),
            "elapsed_ms": event.get("elapsed_ms"),
            "duration_ms": (dict(event.get("meta") or {})).get("duration_ms"),
        }
    )


def _event_delta(before_events: list[dict[str, Any]], after_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {_event_key(event) for event in before_events}
    return [event for event in after_events if _event_key(event) not in seen]


def _summary(state: dict[str, Any], *, recipe: str, label: str) -> dict[str, Any]:
    timing = _extract_latest_design_guide_timing(state)
    counters = _extract_counter_metrics(state)
    source_summary = _state_summary(state, label=label, recipe=recipe)
    return {
        "label": label,
        "rerun_seq": timing.get("rerun_seq"),
        "event_count": timing.get("event_count"),
        "trace_path": timing.get("trace_path"),
        "final_publication_hash": counters.get("final_publication_hash"),
        "final_publication_display_hash": counters.get("final_publication_display_hash"),
        "final_publication_cta_hash": counters.get("final_publication_cta_hash"),
        "button_contract_hash": counters.get("button_contract_hash"),
        "apply_payload_hash": counters.get("apply_payload_hash"),
        "candidate_evaluation": dict(counters.get("candidate_evaluation") or {}),
        "publication_rebuild_count": counters.get("publication_rebuild_count"),
        "card_render_model_rebuild_count": counters.get("card_render_model_rebuild_count"),
        "session_debug_stamp_count": counters.get("session_debug_stamp_count"),
        "stable_render_reuse_trace": dict(counters.get("stable_render_reuse_trace") or {}),
        "rerun_trigger_events": list(counters.get("rerun_trigger_events") or []),
        "pending_flags": dict(source_summary.get("pending_flags") or {}),
        "any_pending_flag": bool(source_summary.get("any_pending_flag")),
        "source_profile_summary": _compact(source_summary, depth=3, max_items=14),
    }


def _capture(base_url: str, *, recipe: str, headed: bool, timeout_s: float) -> dict[str, Any]:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        idle_before = _wait_for_streamlit_idle(page, timeout_s=timeout_s)
        before_state, before_samples = _wait_for_full_publication_state(page, timeout_s=timeout_s)
        before_events = _timing_events(before_state)
        before_summary = _summary(before_state, recipe=recipe, label="before_manual_rerun")
        before_dom = _dom_snapshot(page, label="before_manual_rerun")
        click = _click_streamlit_rerun(page)
        samples: list[dict[str, Any]] = []
        if click.get("clicked"):
            deadline = datetime.now().timestamp() + max(1.0, timeout_s)
            while datetime.now().timestamp() < deadline:
                state = dict(_load_browser_state_prefer_final_debug(page, timeout_s=1.5))
                summary = _summary(state, recipe=recipe, label="after_manual_rerun_sample") if state else {}
                samples.append(
                    {
                        "elapsed_sample_index": len(samples),
                        "summary": summary,
                    }
                )
                if summary.get("rerun_seq") not in (None, before_summary.get("rerun_seq")):
                    break
                page.wait_for_timeout(350)
        page.wait_for_timeout(900)
        after_state = dict(_load_browser_state_prefer_final_debug(page, timeout_s=min(8.0, timeout_s))) if click.get("clicked") else {}
        after_events = _timing_events(after_state)
        after_summary = _summary(after_state, recipe=recipe, label="after_manual_rerun")
        after_dom = _dom_snapshot(page, label="after_manual_rerun")
        idle_after = _wait_for_streamlit_idle(page, timeout_s=min(12.0, timeout_s))
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "idle_before": idle_before,
        "idle_after": idle_after,
        "before": {
            "summary": before_summary,
            "dom": before_dom,
            "timing_events": _compact(before_events, depth=3, max_items=40),
        },
        "click": click,
        "after": {
            "summary": after_summary,
            "dom": after_dom,
            "timing_events": _compact(after_events, depth=3, max_items=40),
            "timing_event_delta": _compact(_event_delta(before_events, after_events), depth=3, max_items=40),
        },
        "before_poll_samples": before_samples,
        "after_poll_samples": samples,
    }


def _stable_authority(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return all(
        before.get(key) == after.get(key)
        for key in (
            "final_publication_hash",
            "final_publication_display_hash",
            "final_publication_cta_hash",
            "button_contract_hash",
            "apply_payload_hash",
        )
        if before.get(key) or after.get(key)
    )


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    before = dict((capture.get("before") or {}).get("summary") or {})
    after = dict((capture.get("after") or {}).get("summary") or {})
    click = dict(capture.get("click") or {})
    event_delta = list(((capture.get("after") or {}).get("timing_event_delta")) or [])
    delta_names = [str(event.get("name") or "") for event in event_delta if isinstance(event, dict)]
    stable_authority = _stable_authority(before, after)
    rerun_changed = before.get("rerun_seq") is not None and after.get("rerun_seq") not in (None, before.get("rerun_seq"))
    trigger_events = list(after.get("rerun_trigger_events") or [])
    pending_after = bool(after.get("any_pending_flag"))
    candidate_count = int((after.get("candidate_evaluation") or {}).get("count") or 0)
    publication_rebuilds = int(after.get("publication_rebuild_count") or 0)
    card_rebuilds = int(after.get("card_render_model_rebuild_count") or 0)
    stable_trace = dict(after.get("stable_render_reuse_trace") or {})
    def _is_one_time_publication_hash_hydration(row: dict[str, Any]) -> bool:
        previous_hash_text = str(row.get("previous_render_fingerprint_hash") or "")
        current_hash_text = str(row.get("render_fingerprint_hash") or "")
        missing_required = list(row.get("missing_required_fingerprint_keys") or [])
        if missing_required:
            return False
        return (
            '"final_publication_hash": ""' in previous_hash_text
            and '"final_publication_display_hash": ""' in previous_hash_text
            and '"final_publication_cta_hash": ""' in previous_hash_text
            and '"final_publication_hash": ""' not in current_hash_text
            and '"final_publication_display_hash": ""' not in current_hash_text
            and '"final_publication_cta_hash": ""' not in current_hash_text
        )

    trace_required = []
    trace_hydration = []
    for surface, row in stable_trace.items():
        if str(surface) == "_diagnostic_probes" or not isinstance(row, dict):
            continue
        if row.get("decision") != "TRACE_RENDER_REQUIRED":
            continue
        if _is_one_time_publication_hash_hydration(row):
            trace_hydration.append(str(surface))
            continue
        trace_required.append(str(surface))
    likely_sources: list[str] = []
    if not click.get("clicked"):
        likely_sources.append("streamlit_rerun_control_not_clicked")
    if rerun_changed and not trigger_events:
        likely_sources.append("manual_streamlit_rerun_unmarked_by_page_trigger")
    if pending_after:
        likely_sources.append("pending_apply_or_action_flag_after_rerun")
    if stable_authority and candidate_count:
        likely_sources.append("candidate_evaluation_after_stable_manual_rerun")
    if stable_authority and publication_rebuilds:
        likely_sources.append("publication_debug_stamp_rebuild_after_stable_manual_rerun")
    if stable_authority and card_rebuilds:
        likely_sources.append("card_render_model_rebuild_after_stable_manual_rerun")
    if stable_authority and trace_required:
        likely_sources.append("stable_render_trace_required_after_manual_rerun")
    if any(name.startswith("app.browser_test_state_emit") for name in delta_names):
        likely_sources.append("browser_probe_payload_rebuilt_after_manual_rerun")
    if not likely_sources and rerun_changed:
        likely_sources.append("manual_rerun_no_product_rebuild_hotspot_detected")
    if not likely_sources:
        likely_sources.append("same_session_rerun_not_proven")

    if "pending_apply_or_action_flag_after_rerun" in likely_sources:
        recommended = "Audit why apply/action pending flags survive the no-change rerun before adding reuse."
    elif "publication_debug_stamp_rebuild_after_stable_manual_rerun" in likely_sources:
        recommended = "Resolve publication debug probe/hash readiness before adding debug-stamp reuse."
    elif "stable_render_trace_required_after_manual_rerun" in likely_sources:
        recommended = "Audit render fingerprint payload drift for trace-required surfaces before adding render reuse."
    elif "browser_probe_payload_rebuilt_after_manual_rerun" in likely_sources:
        recommended = "Separate browser-test probe rebuild cost from product smoothness before optimizing product paths."
    elif "manual_streamlit_rerun_unmarked_by_page_trigger" in likely_sources:
        recommended = "No page-owned rerun trigger was recorded; next profile should target product state writes before/after Apply, not manual Streamlit rerun."
    else:
        recommended = "Re-rank broad smoothness hotspots; this same-session no-change rerun did not prove a safe product bypass target."

    return {
        "status": "PASS" if click.get("clicked") and rerun_changed and stable_authority else "PARTIAL",
        "clicked_rerun": bool(click.get("clicked")),
        "rerun_seq_changed": bool(rerun_changed),
        "stable_authority_hashes": bool(stable_authority),
        "rerun_trigger_events_after": trigger_events,
        "timing_event_delta_names": delta_names,
        "likely_sources": likely_sources,
        "candidate_evaluation_count_after": candidate_count,
        "publication_rebuild_count_after": publication_rebuilds,
        "card_render_model_rebuild_count_after": card_rebuilds,
        "trace_required_surfaces": trace_required,
        "one_time_publication_hash_hydration_surfaces": trace_hydration,
        "pending_flags_after": dict(after.get("pending_flags") or {}),
        "recommended_next_slice": recommended,
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Same-Session Rerun Trigger Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Executive Summary",
        "",
        f"- Clicked rerun: `{cls.get('clicked_rerun')}`",
        f"- Rerun seq changed: `{cls.get('rerun_seq_changed')}`",
        f"- Stable authority hashes: `{cls.get('stable_authority_hashes')}`",
        f"- Likely sources: `{', '.join(cls.get('likely_sources') or [])}`",
        f"- Candidate eval count after: `{cls.get('candidate_evaluation_count_after')}`",
        f"- Publication rebuild count after: `{cls.get('publication_rebuild_count_after')}`",
        f"- Card render-model rebuild count after: `{cls.get('card_render_model_rebuild_count_after')}`",
        "",
        "## Rerun Trigger Events",
        "",
    ]
    events = cls.get("rerun_trigger_events_after") or []
    if events:
        lines.append("```json")
        lines.append(json.dumps(events, indent=2, sort_keys=True, default=str))
        lines.append("```")
    else:
        lines.append("- None recorded")
    lines.extend(
        [
            "",
            "## Timing Delta Names",
            "",
        ]
    )
    for name in cls.get("timing_event_delta_names") or []:
        lines.append(f"- `{name}`")
    lines.extend(["", "## Recommendation", "", str(cls.get("recommended_next_slice") or "")])
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_session_rerun_trigger_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_session_rerun_trigger_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8638)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_SAME_SESSION_RERUN_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=max(30.0, float(args.timeout_s)))
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            headed=bool(args.headed),
            timeout_s=float(args.timeout_s),
        )
        classification = _classify(capture)
        payload: dict[str, Any] = {
            "schema": "design_guide_same_session_rerun_trigger_ownership_audit.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
            "capture": _compact(capture, depth=6, max_items=40),
            "latest": {
                "browser_live_smoothness_profile": _latest("design_guide_browser_live_smoothness_profile"),
                "same_session_no_change_rerun_profile": _latest("design_guide_same_session_no_change_rerun_profile"),
                "same_session_publication_debug_stamp_hash_instability": _latest(
                    "design_guide_same_session_publication_debug_stamp_hash_instability"
                ),
                "independence_lock": _latest("design_guide_independence_lock"),
                "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
                "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
                "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
            },
            "product_behaviour_changed": False,
        }
        json_path, md_path = _write(payload)
        print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
