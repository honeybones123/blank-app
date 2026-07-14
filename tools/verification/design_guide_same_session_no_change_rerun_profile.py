"""Browser/live same-session no-change rerun profile.

Measurement-only verifier. It uses Streamlit's own visible Rerun control to
trigger a same-browser-session rerun without changing input values, then
compares browser state probes before/after. This fills the evidence gap left by
reload-based profiles, which lose session render fingerprints.
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
import time
import traceback
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_smoothness_profile import (  # noqa: E402
    _debug_bundle,
    _extract_counter_metrics,
    _extract_latest_design_guide_timing,
)
from tools.verification.helpers.browser_helpers import (  # noqa: E402
    _browser_state_raw_candidates,
    _load_browser_state,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "A_bending_under_only"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({key: value for key, value in params.items() if value is not None})}"


def _load_browser_state_prefer_final_debug(page, timeout_s: float = 30.0) -> dict[str, Any]:
    best = None
    for raw in _browser_state_raw_candidates(page, timeout_ms=max(500, int(min(timeout_s, 3.0) * 1000))):
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        bundle = _debug_bundle(parsed)
        payload = dict(bundle.get("final_publication_verifier_payload") or {})
        if payload.get("publication_hash"):
            return parsed
        if not parsed.get("pre_page_render_lightweight"):
            best = parsed
    if best is not None:
        return best
    return dict(_load_browser_state(page, timeout_s=timeout_s))


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


def _visible_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
              };
              const nodes = Array.from(document.querySelectorAll("button,a,[role='button']"));
              const rerunControls = nodes
                .filter(visible)
                .map((el, index) => ({
                  index,
                  text: clean(el.innerText || el.textContent),
                  aria: el.getAttribute ? (el.getAttribute("aria-label") || "") : "",
                  testid: el.getAttribute ? (el.getAttribute("data-testid") || "") : "",
                }))
                .filter((row) => /(^|\b)Rerun(\b|$)/i.test(row.text + " " + row.aria));
              const text = clean(document.body ? document.body.innerText : "");
              return {
                body_text_hash: Array.from(text.slice(0, 2500)).reduce((h, ch) => ((h * 31 + ch.charCodeAt(0)) >>> 0), 0).toString(16),
                has_design_guide: /Design Guide/i.test(text),
                has_summary: /Bending|Shear|Crack|Deflection/i.test(text),
                rerun_control_candidates: rerunControls.slice(0, 8),
              };
            }
            """
        )
        or {}
    )


def _click_streamlit_rerun(page) -> dict[str, Any]:
    script = r"""
    () => {
      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const visible = (el) => {
        if (!el || !el.getBoundingClientRect) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden"
          && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
      };
      const candidates = Array.from(document.querySelectorAll("button,a,[role='button']"))
        .filter(visible)
        .map((el, index) => ({
          el,
          index,
          text: clean(el.innerText || el.textContent),
          aria: el.getAttribute ? (el.getAttribute("aria-label") || "") : "",
          testid: el.getAttribute ? (el.getAttribute("data-testid") || "") : "",
        }))
        .filter((row) => {
          const haystack = `${row.text} ${row.aria} ${row.testid}`;
          return /(^|\b)Rerun(\b|$)/i.test(haystack) && !/Always rerun/i.test(haystack);
        });
      const exact = candidates.find((row) => /^Rerun$/i.test(row.text) || /^Rerun$/i.test(row.aria));
      const target = exact || candidates[0];
      if (!target) {
        return {clicked: false, reason: "rerun_control_not_found", candidate_count: 0};
      }
      target.el.click();
      return {
        clicked: true,
        reason: "clicked_streamlit_rerun_control",
        candidate_count: candidates.length,
        clicked_text: target.text,
        clicked_aria: target.aria,
        clicked_testid: target.testid,
      };
    }
    """
    try:
        first = dict(page.evaluate(script) or {})
        if first.get("clicked"):
            return first
        # Some Streamlit versions tuck Rerun behind the main menu. Open it and
        # try the same DOM search once more.
        menu = page.locator("[data-testid='stMainMenuButton']").first
        try:
            menu.click(timeout=2_000)
            page.wait_for_timeout(350)
        except Exception:
            pass
        second = dict(page.evaluate(script) or {})
        if second.get("clicked"):
            second["opened_main_menu_first"] = True
            return second
        second["first_attempt"] = first
        return second
    except Exception as exc:
        return {"clicked": False, "reason": f"{type(exc).__name__}: {exc}", "candidate_count": 0}


def _wait_for_streamlit_idle(page, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.time() + max(1.0, timeout_s)
    last = {}
    while time.time() < deadline:
        try:
            last = dict(
                page.evaluate(
                    r"""
                    () => {
                      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
                      const visible = (el) => {
                        if (!el || !el.getBoundingClientRect) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== "none" && style.visibility !== "hidden"
                          && Number(style.opacity || "1") > 0.02 && rect.width > 2 && rect.height > 2;
                      };
                      const statusText = Array.from(document.querySelectorAll("[data-testid='stStatusWidget'], [data-testid='stStatusWidget'] *"))
                        .filter(visible)
                        .map((el) => clean(el.innerText || el.textContent || el.getAttribute("aria-label") || ""))
                        .join(" ");
                      const visibleButtons = Array.from(document.querySelectorAll("button,a,[role='button']"))
                        .filter(visible)
                        .map((el) => clean(el.innerText || el.textContent || el.getAttribute("aria-label") || ""));
                      const running = /Stop|Running/i.test(statusText) || visibleButtons.some((text) => /^Stop$/i.test(text));
                      return {running, statusText, visibleButtons: visibleButtons.slice(0, 20)};
                    }
                    """
                )
                or {}
            )
        except Exception:
            last = {}
        if last and not last.get("running"):
            return {"idle": True, **last}
        page.wait_for_timeout(400)
    return {"idle": False, **last}


def _summarise_state(state: dict[str, Any]) -> dict[str, Any]:
    timing = _extract_latest_design_guide_timing(state)
    counters = _extract_counter_metrics(state)
    stable_trace = dict(counters.get("stable_render_reuse_trace") or {})
    verifier_payload = dict(_debug_bundle(state).get("final_publication_verifier_payload") or {})
    return {
        "rerun_seq": timing.get("rerun_seq"),
        "event_count": timing.get("event_count"),
        "final_publication_hash": counters.get("final_publication_hash"),
        "final_publication_display_hash": counters.get("final_publication_display_hash"),
        "final_publication_cta_hash": counters.get("final_publication_cta_hash"),
        "final_publication_verifier_publication_hash": verifier_payload.get("publication_hash"),
        "final_publication_verifier_payload_present": bool(verifier_payload.get("publication_hash")),
        "button_contract_hash": counters.get("button_contract_hash"),
        "apply_payload_hash": counters.get("apply_payload_hash"),
        "candidate_evaluation": dict(counters.get("candidate_evaluation") or {}),
        "publication_rebuild_count": counters.get("publication_rebuild_count"),
        "publication_stamp_bypass_count": counters.get("publication_stamp_bypass_count"),
        "publication_stamp_decisions": list(counters.get("publication_stamp_decisions") or []),
        "card_render_model_rebuild_count": counters.get("card_render_model_rebuild_count"),
        "card_render_model_bypass_count": counters.get("card_render_model_bypass_count"),
        "card_render_model_decisions": list(counters.get("card_render_model_decisions") or []),
        "session_debug_stamp_count": counters.get("session_debug_stamp_count"),
        "rerun_trigger_events": list(counters.get("rerun_trigger_events") or []),
        "stable_render_reuse_trace": stable_trace,
        "stable_render_reuse_eligible_surfaces": [
            key for key, row in stable_trace.items() if isinstance(row, dict) and bool(row.get("reuse_eligible"))
        ],
        "stable_render_missing_previous_surfaces": [
            key
            for key, row in stable_trace.items()
            if isinstance(row, dict) and "missing_previous_render_fingerprint_hash" in str(row.get("reason") or "")
        ],
    }


def _wait_for_rerun_seq_change(page, before_seq: Any, *, timeout_s: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.time() + max(1.0, timeout_s)
    samples: list[dict[str, Any]] = []
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            state = dict(_load_browser_state_prefer_final_debug(page, timeout_s=1.5))
        except Exception:
            state = {}
        last_state = state
        summary = _summarise_state(state) if state else {}
        samples.append({"elapsed_ms": int((timeout_s - max(0.0, deadline - time.time())) * 1000), "summary": summary})
        if state and summary.get("rerun_seq") not in (None, before_seq):
            return state, samples
        page.wait_for_timeout(350)
    return last_state, samples


def _wait_for_full_publication_state(page, *, timeout_s: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.time() + max(1.0, timeout_s)
    samples: list[dict[str, Any]] = []
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            state = dict(_load_browser_state_prefer_final_debug(page, timeout_s=1.5))
        except Exception:
            state = {}
        last_state = state
        summary = _summarise_state(state) if state else {}
        samples.append(
            {
                "elapsed_ms": int((timeout_s - max(0.0, deadline - time.time())) * 1000),
                "summary": summary,
            }
        )
        if (
            summary.get("final_publication_hash")
            and summary.get("final_publication_display_hash")
            and summary.get("final_publication_cta_hash")
            and dict(_debug_bundle(state).get("final_publication_verifier_payload") or {}).get("publication_hash")
        ):
            return state, samples
        page.wait_for_timeout(350)
    return last_state, samples


def _capture(base_url: str, *, recipe: str, headed: bool, timeout_s: float) -> dict[str, Any]:
    url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
        idle_before = _wait_for_streamlit_idle(page, timeout_s=timeout_s)
        before_state, before_samples = _wait_for_full_publication_state(page, timeout_s=timeout_s)
        before_summary = _summarise_state(before_state)
        before_visible = _visible_probe(page)
        click = _click_streamlit_rerun(page)
        if click.get("clicked"):
            after_state, samples = _wait_for_rerun_seq_change(
                page,
                before_summary.get("rerun_seq"),
                timeout_s=timeout_s,
            )
        else:
            after_state, samples = {}, []
        page.wait_for_timeout(900)
        final_state = (
            dict(_load_browser_state_prefer_final_debug(page, timeout_s=min(8.0, timeout_s)))
            if click.get("clicked")
            else after_state
        )
        after_summary = _summarise_state(final_state) if final_state else {}
        after_visible = _visible_probe(page)
        idle_after = _wait_for_streamlit_idle(page, timeout_s=min(12.0, timeout_s))
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "idle_before": idle_before,
        "idle_after": idle_after,
        "before": {"state": before_summary, "visible": before_visible},
        "click": click,
        "after": {"state": after_summary, "visible": after_visible},
        "before_poll_samples": before_samples,
        "poll_samples": samples,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    before = dict((capture.get("before") or {}).get("state") or {})
    after = dict((capture.get("after") or {}).get("state") or {})
    click = dict(capture.get("click") or {})
    rerun_changed = before.get("rerun_seq") is not None and after.get("rerun_seq") not in (None, before.get("rerun_seq"))
    stable_authority = all(
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
    eligible = list(after.get("stable_render_reuse_eligible_surfaces") or [])
    missing_previous = list(after.get("stable_render_missing_previous_surfaces") or [])
    candidate_count = int((after.get("candidate_evaluation") or {}).get("count") or 0)
    card_rebuilds = int(after.get("card_render_model_rebuild_count") or 0)
    publication_rebuilds = int(after.get("publication_rebuild_count") or 0)
    before_debug_payload_ready = bool(before.get("final_publication_verifier_payload_present"))
    after_debug_payload_ready = bool(after.get("final_publication_verifier_payload_present"))
    publication_decisions = list(after.get("publication_stamp_decisions") or [])
    publication_debug_rebuilds = [
        row for row in publication_decisions if "debug" in str(row.get("reason") or row.get("reasons") or "").lower()
    ]
    likely_sources: list[str] = []
    if not click.get("clicked"):
        likely_sources.append("streamlit_rerun_control_not_clicked")
    if rerun_changed and stable_authority and eligible:
        likely_sources.append("same_session_stable_render_reuse_eligible_but_rendered")
    if rerun_changed and stable_authority and candidate_count:
        likely_sources.append("same_session_candidate_evaluation_with_stable_authority")
    if rerun_changed and stable_authority and card_rebuilds:
        likely_sources.append("same_session_card_render_model_rebuild_with_stable_authority")
    if rerun_changed and stable_authority and publication_rebuilds and len(publication_debug_rebuilds) < publication_rebuilds:
        if not before_debug_payload_ready:
            likely_sources.append("same_session_publication_debug_probe_not_ready_before_click")
        else:
            likely_sources.append("same_session_publication_stamp_rebuild_with_stable_authority")
    elif rerun_changed and stable_authority and publication_rebuilds:
        likely_sources.append("same_session_publication_stamp_rebuild_debug_guarded")
    if missing_previous:
        likely_sources.append("same_session_missing_previous_render_fingerprint")
    if not likely_sources and rerun_changed:
        likely_sources.append("same_session_rerun_no_major_rebuild_source_detected")
    elif not likely_sources:
        likely_sources.append("same_session_rerun_not_proven")
    if "same_session_stable_render_reuse_eligible_but_rendered" in likely_sources:
        next_slice = "Implement guarded render reuse for same-session eligible surfaces only."
    elif "same_session_candidate_evaluation_with_stable_authority" in likely_sources:
        next_slice = "Audit remaining candidate-evaluation churn in same-session reruns before adding a cache."
    elif "same_session_card_render_model_rebuild_with_stable_authority" in likely_sources:
        next_slice = "Create a same-session card render-model reuse readiness proof."
    elif "same_session_publication_debug_probe_not_ready_before_click" in likely_sources:
        next_slice = "Audit browser-state probe readiness before adding publication/debug stamp reuse."
    elif "same_session_publication_stamp_rebuild_with_stable_authority" in likely_sources:
        next_slice = "Create a same-session publication/debug stamp reuse readiness proof."
    elif not click.get("clicked"):
        next_slice = "Add a test-only same-session rerun trigger or run headed to inspect the Streamlit toolbar."
    else:
        next_slice = "Re-rank the latest broad smoothness profile; no same-session no-change rebuild hotspot was proven."
    status = "PASS" if click.get("clicked") and rerun_changed and stable_authority else "PARTIAL"
    return {
        "status": status,
        "clicked_rerun": bool(click.get("clicked")),
        "rerun_seq_changed": bool(rerun_changed),
        "stable_authority_hashes": bool(stable_authority),
        "likely_sources": likely_sources,
        "same_session_eligible_surfaces": eligible,
        "same_session_missing_previous_surfaces": missing_previous,
        "candidate_evaluation_count_after": candidate_count,
        "card_render_model_rebuild_count_after": card_rebuilds,
        "publication_rebuild_count_after": publication_rebuilds,
        "publication_debug_rebuild_count_after": len(publication_debug_rebuilds),
        "before_debug_payload_ready": before_debug_payload_ready,
        "after_debug_payload_ready": after_debug_payload_ready,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Same-Session No-Change Rerun Profile",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- Clicked rerun: `{cls.get('clicked_rerun')}`",
            f"- Rerun seq changed: `{cls.get('rerun_seq_changed')}`",
            f"- Stable authority hashes: `{cls.get('stable_authority_hashes')}`",
            f"- Likely sources: `{', '.join(cls.get('likely_sources') or [])}`",
            "",
            "## Next Safe Slice",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
            "## Before / After",
            "",
            "```json",
            json.dumps(
                {
                    "before": (payload.get("capture") or {}).get("before", {}).get("state"),
                    "after": (payload.get("capture") or {}).get("after", {}).get("state"),
                    "click": (payload.get("capture") or {}).get("click"),
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_session_no_change_rerun_profile_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_session_no_change_rerun_profile_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8627)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_SAME_SESSION_RERUN_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout-s", type=float, default=75.0)
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
        try:
            capture = _capture(
                base_url,
                recipe=str(args.recipe),
                headed=bool(args.headed),
                timeout_s=float(args.timeout_s),
            )
            classification = _classify(capture)
        except Exception as exc:
            capture = {
                "url": _query(base_url, {"page": "inputs", "browser_recipe": str(args.recipe)}),
                "recipe": str(args.recipe),
                "capture_failed": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=8),
            }
            classification = {
                "status": "PARTIAL",
                "clicked_rerun": False,
                "rerun_seq_changed": False,
                "stable_authority_hashes": False,
                "likely_sources": ["browser_state_probe_empty_or_unavailable"],
                "same_session_eligible_surfaces": [],
                "same_session_missing_previous_surfaces": [],
                "candidate_evaluation_count_after": 0,
                "card_render_model_rebuild_count_after": 0,
                "publication_rebuild_count_after": 0,
                "publication_debug_rebuild_count_after": 0,
                "before_debug_payload_ready": False,
                "after_debug_payload_ready": False,
                "recommended_next_slice": (
                    "Fix or rerun the browser-state probe with a headed/user-specific session before "
                    "implementing any same-session render reuse."
                ),
            }
        latest = {
            "landing_flash_guard_live_impact": _latest("design_guide_same_page_landing_flash_guard_live_impact"),
            "status_layout_guard": _latest("design_guide_same_page_inputs_dispatch_status_layout_guard"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
        }
        payload: dict[str, Any] = {
            "schema": "design_guide_same_session_no_change_rerun_profile.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
            "capture": capture,
            "latest": latest,
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            "product_behaviour_changed": False,
            "behaviour_scope": {
                "layout_changed": False,
                "rendering_changed": False,
                "publication_changed": False,
                "cta_apply_changed": False,
                "family_runtime_changed": False,
                "visible_wording_changed": False,
                "engineering_behaviour_changed": False,
            },
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
