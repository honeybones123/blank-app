"""Browser/live loading gap and scroll interaction snapshot.

Proof-only. This verifier targets the user-reported huge blank gap between the
Beam design heading/navigation and the Inputs content, plus the feeling that
scrolling up is locked while Design Brain/Design Guide loading is underway.

It samples the top-level Inputs page geometry at high frequency during first
load and makes early scroll attempts while content is still settling. It does
not change product behaviour, engineering logic, publication, CTA/apply
semantics, visible wording, or family runtimes.
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

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _query,
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


INIT_SCRIPT = r"""
(() => {
  if (window.__dgLoadingGapScrollProbe) return;
  const probe = {
    samples: [],
    scrollAttempts: [],
    layoutShifts: [],
    errors: []
  };
  window.__dgLoadingGapScrollProbe = probe;
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    if (!el || !el.getBoundingClientRect) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== "none"
      && style.visibility !== "hidden"
      && Number(style.opacity || "1") > 0.02
      && rect.width > 2
      && rect.height > 2;
  };
  const payload = (el) => {
    if (!el) return {exists: false, visible: false};
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return {
      exists: true,
      visible: visible(el),
      tag: String(el.tagName || "").toLowerCase(),
      testid: el.getAttribute ? String(el.getAttribute("data-testid") || "") : null,
      cls: String(el.className || "").slice(0, 160),
      text: clean(el.innerText || el.textContent).slice(0, 220),
      rect: {
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      },
      style: {
        marginTop: style.marginTop,
        marginBottom: style.marginBottom,
        minHeight: style.minHeight,
        height: style.height,
        display: style.display,
        overflowY: style.overflowY
      }
    };
  };
  const shortestText = (regex, rejectRegex = null, selector = "body *") => {
    const all = Array.from(document.querySelectorAll(selector)).filter(visible);
    const matches = all.filter((el) => {
      const text = clean(el.innerText || el.textContent);
      if (!regex.test(text)) return false;
      if (rejectRegex && rejectRegex.test(text)) return false;
      return true;
    }).sort((a, b) => {
      const at = clean(a.innerText || a.textContent);
      const bt = clean(b.innerText || b.textContent);
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      return at.length - bt.length || ar.top - br.top || ar.height - br.height;
    });
    return matches[0] || null;
  };
  const pageScroller = () => document.scrollingElement || document.documentElement;
  const largestScrollable = () => {
    const doc = pageScroller();
    if (doc && (doc.scrollHeight || 0) > (doc.clientHeight || 0) + 8) {
      return doc;
    }
    return Array.from(document.querySelectorAll("body, body *")).filter((el) => {
    if (!el || !el.getBoundingClientRect) return false;
    const marker = `${el.getAttribute ? el.getAttribute("data-testid") || "" : ""} ${String(el.className || "")}`;
    if (/stSidebar/i.test(marker)) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return (el.scrollHeight || 0) > (el.clientHeight || 0) + 8
      && (/(auto|scroll|overlay)/i.test(String(style.overflowY || style.overflow || "")) || rect.height >= window.innerHeight * 0.45);
  }).sort((a, b) => ((b.scrollHeight || 0) - (b.clientHeight || 0)) - ((a.scrollHeight || 0) - (a.clientHeight || 0)))[0]
    || doc;
  };
  const gap = (upper, lower) => {
    const up = payload(upper);
    const lo = payload(lower);
    if (!up.exists || !lo.exists) return null;
    return Math.round((lo.rect.top || 0) - (up.rect.bottom || 0));
  };
  const between = (upper, lower) => {
    if (!upper || !lower) return [];
    const up = upper.getBoundingClientRect();
    const lo = lower.getBoundingClientRect();
    return Array.from(document.querySelectorAll("body *")).filter((el) => {
      if (!visible(el)) return false;
      if (el === upper || el === lower || upper.contains(el) || lower.contains(el)) return false;
      const rect = el.getBoundingClientRect();
      return rect.top >= up.bottom - 2 && rect.bottom <= lo.top + 2 && rect.height > 2;
    }).sort((a, b) => {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      return ar.top - br.top || ar.height - br.height;
    }).slice(0, 18).map(payload);
  };
  const sample = (label) => {
    try {
      const beamHeading = shortestText(/^Beam design$/i, null, "h1, h2, h3, [role='heading']");
      const inputsHeading = shortestText(/^Inputs$/i, null, "h1, h2, h3, [role='heading']");
      const navTabs = shortestText(/Inputs\s+Design\s+Bending\s+Shear/i);
      const summary = document.querySelector(".summary-card-stack")
        || shortestText(/Bending\s+[-â€”]\s+ULS|Shear\s+[-â€”]\s+ULS|Crack control\s+[-â€”]\s+SLS/i);
      const batch = shortestText(/^Batch design$/i);
      const dgHeading = shortestText(/^Design Guide$/i, /Design Guide Debug|Debug session state/i);
      const loading = document.querySelector(".dg-proof-pending-card")
        || shortestText(/Checking design guidance|Reviewing strength, detailing, serviceability/i);
      const scroller = largestScrollable();
      probe.samples.push({
        label,
        at: Math.round(performance.now()),
        viewport: {width: window.innerWidth, height: window.innerHeight},
        scroll: {
          top: Math.round(scroller.scrollTop || 0),
          height: Math.round(scroller.scrollHeight || 0),
          clientHeight: Math.round(scroller.clientHeight || 0),
          tag: String(scroller.tagName || "").toLowerCase(),
          testid: scroller.getAttribute ? scroller.getAttribute("data-testid") : null,
          cls: String(scroller.className || "").slice(0, 140)
        },
        elements: {
          beam_heading: payload(beamHeading),
          nav_tabs: payload(navTabs),
          inputs_heading: payload(inputsHeading),
          summary_stack: payload(summary),
          batch_design: payload(batch),
          design_guide_heading: payload(dgHeading),
          loading_shell: payload(loading)
        },
        gaps: {
          beam_to_nav: gap(beamHeading, navTabs),
          beam_to_inputs: gap(beamHeading, inputsHeading),
          nav_to_inputs: gap(navTabs, inputsHeading),
          inputs_to_summary: gap(inputsHeading, summary),
          summary_to_batch: gap(summary, batch),
          batch_to_design_guide: gap(batch, dgHeading)
        },
        interstitial: {
          inputs_to_summary: between(inputsHeading, summary)
        },
        bodyTextLen: clean(document.body ? document.body.innerText : "").length
      });
    } catch (err) {
      probe.errors.push("sample:" + String(err && err.message || err));
    }
  };
  const attemptScroll = (label) => {
    try {
      const scroller = largestScrollable();
      const before = {
        top: Math.round(scroller.scrollTop || 0),
        height: Math.round(scroller.scrollHeight || 0),
        clientHeight: Math.round(scroller.clientHeight || 0)
      };
      scroller.scrollTop = Math.min(before.height, before.top + Math.max(550, Math.round(window.innerHeight * 0.55)));
      const down = {
        top: Math.round(scroller.scrollTop || 0),
        height: Math.round(scroller.scrollHeight || 0),
        clientHeight: Math.round(scroller.clientHeight || 0)
      };
      scroller.scrollTop = Math.max(0, down.top - Math.max(550, Math.round(window.innerHeight * 0.55)));
      const up = {
        top: Math.round(scroller.scrollTop || 0),
        height: Math.round(scroller.scrollHeight || 0),
        clientHeight: Math.round(scroller.clientHeight || 0)
      };
      probe.scrollAttempts.push({
        label,
        at: Math.round(performance.now()),
        target: {
          tag: String(scroller.tagName || "").toLowerCase(),
          testid: scroller.getAttribute ? scroller.getAttribute("data-testid") : null,
          cls: String(scroller.className || "").slice(0, 140)
        },
        before,
        down,
        up,
        can_scroll_down: down.top > before.top,
        can_scroll_back_up: up.top < down.top,
        locked_while_scrollable: (before.height > before.clientHeight + 8) && !(down.top > before.top)
      });
    } catch (err) {
      probe.errors.push("scroll:" + String(err && err.message || err));
    }
  };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        probe.layoutShifts.push({
          at: Math.round(entry.startTime || 0),
          value: Number(entry.value || 0),
          sourceCount: (entry.sources || []).length
        });
      }
    }).observe({type: "layout-shift", buffered: true});
  } catch (err) {
    probe.errors.push("layout_shift:" + String(err && err.message || err));
  }
  sample("init");
  const timer = setInterval(() => sample("interval"), 80);
  [250, 650, 1100, 1800, 2800, 4200].forEach((delay, index) => {
    setTimeout(() => attemptScroll(`early_scroll_${index + 1}`), delay);
  });
  setTimeout(() => clearInterval(timer), 6500);
})();
"""


def _capture(base_url: str, *, recipe: str, wait_ms: int, headed: bool, exact_url: str | None = None) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        context.add_init_script(INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(30_000)
        url = str(exact_url) if exact_url else _query(base_url, {"page": "inputs", "browser_recipe": recipe, "batch_design_open": "0"})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(max(2500, wait_ms))
        capture = dict(page.evaluate("() => window.__dgLoadingGapScrollProbe || {}") or {})
        capture["final_url"] = page.url
        browser.close()
    capture["requested_url"] = url
    capture["exact_url_mode"] = bool(exact_url)
    capture["recipe"] = recipe
    return capture


def _max_gap(samples: list[dict[str, Any]], key: str) -> int:
    values: list[int] = []
    for sample in samples:
        value = (sample.get("gaps") or {}).get(key)
        if value is not None:
            values.append(int(value))
    return max(values or [0])


def _sample_for_max_gap(samples: list[dict[str, Any]], key: str) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_value = -10_000
    for sample in samples:
        value = (sample.get("gaps") or {}).get(key)
        if value is not None and int(value) > best_value:
            best_value = int(value)
            best = sample
    return best


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    samples = [dict(row or {}) for row in list(capture.get("samples") or [])]
    scroll_attempts = [dict(row or {}) for row in list(capture.get("scrollAttempts") or [])]
    layout_shift_total = round(sum(float(row.get("value") or 0.0) for row in list(capture.get("layoutShifts") or [])), 6)
    max_beam_inputs = _max_gap(samples, "beam_to_inputs")
    max_nav_inputs = _max_gap(samples, "nav_to_inputs")
    max_inputs_summary = _max_gap(samples, "inputs_to_summary")
    max_summary_batch = _max_gap(samples, "summary_to_batch")
    max_batch_dg = _max_gap(samples, "batch_to_design_guide")
    scroll_locked_attempts = [row for row in scroll_attempts if row.get("locked_while_scrollable")]
    risks: list[str] = []
    if max_beam_inputs > 380 or max_nav_inputs > 280:
      risks.append("huge_top_inputs_gap_reproduced")
    if max_inputs_summary > 180:
      risks.append("large_inputs_to_summary_gap")
    if max_summary_batch > 180:
      risks.append("large_summary_to_batch_gap")
    if max_batch_dg > 220:
      risks.append("large_batch_to_design_guide_gap")
    if scroll_locked_attempts:
      risks.append("scroll_locked_during_loading")
    if layout_shift_total > 0.2:
      risks.append("high_loading_layout_shift")

    if "huge_top_inputs_gap_reproduced" in risks:
        decision = "REPRODUCED_TOP_CONTENT_GAP"
        next_slice = "Measure the exact ancestor/style of the max-gap sample, then patch only that owner."
    elif "scroll_locked_during_loading" in risks:
        decision = "REPRODUCED_SCROLL_LOCK_DURING_LOADING"
        next_slice = "Trace the locked scroll container and loading shell that owns the scroll target."
    elif risks == ["high_loading_layout_shift"]:
        decision = "LOADING_LAYOUT_SHIFT_REPRODUCED_WITHOUT_HUGE_GAP"
        next_slice = "Use source-node layout shift proof for the remaining CLS owner; do not patch top-gap spacing from this recipe."
    elif risks:
        decision = "LOADING_LAYOUT_RISK_REPRODUCED"
        next_slice = "Patch the measured gap owner only after a readiness snapshot."
    else:
        decision = "USER_SPECIFIC_GAP_NOT_REPRODUCED_IN_AUTOMATED_RECIPE"
        next_slice = "Run this verifier against the user's existing live URL/session or capture a headed reproduction recipe."

    return {
        "status": "PASS",
        "decision": decision,
        "risks": risks,
        "sample_count": len(samples),
        "scroll_attempt_count": len(scroll_attempts),
        "layout_shift_total": layout_shift_total,
        "max_gaps": {
            "beam_to_inputs": max_beam_inputs,
            "nav_to_inputs": max_nav_inputs,
            "inputs_to_summary": max_inputs_summary,
            "summary_to_batch": max_summary_batch,
            "batch_to_design_guide": max_batch_dg,
        },
        "max_gap_samples": {
            "beam_to_inputs": _sample_for_max_gap(samples, "beam_to_inputs"),
            "nav_to_inputs": _sample_for_max_gap(samples, "nav_to_inputs"),
            "inputs_to_summary": _sample_for_max_gap(samples, "inputs_to_summary"),
        },
        "scroll_locked_attempts": scroll_locked_attempts,
        "observer_errors": list(capture.get("errors") or []),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    classification = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Loading Gap And Scroll Interaction Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{classification.get('decision')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Risks: `{', '.join(classification.get('risks') or []) or '-'}`",
        f"- Layout shift total: `{classification.get('layout_shift_total')}`",
        "",
        "## Max Gaps",
        "",
    ]
    for key, value in (classification.get("max_gaps") or {}).items():
        lines.append(f"- {key}: `{value}` px")
    lines.extend(
        [
            "",
            "## Scroll",
            "",
            f"- Attempts: `{classification.get('scroll_attempt_count')}`",
            f"- Locked attempts: `{len(classification.get('scroll_locked_attempts') or [])}`",
            "",
            "## Recommendation",
            "",
            str(classification.get("recommended_next_slice") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_loading_gap_scroll_interaction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_loading_gap_scroll_interaction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8677)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_LOADING_GAP_SCROLL_URL"))
    parser.add_argument("--url", default=os.environ.get("DESIGN_GUIDE_LOADING_GAP_SCROLL_EXACT_URL"))
    parser.add_argument("--recipe", default="A_bending_under_only")
    parser.add_argument("--wait-ms", type=int, default=7500)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url and not args.url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["PERF_TRACE_INPUTS"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=60.0)
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            wait_ms=int(args.wait_ms),
            headed=bool(args.headed),
            exact_url=str(args.url) if args.url else None,
        )
        classification = _classify(capture)
        payload = {
            "created_at": created_at,
            "status": classification.get("status"),
            "product_behaviour_changed": False,
            "base_url": base_url,
            "recipe": args.recipe,
            "capture_hash": _stable_hash(capture),
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            "classification": classification,
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], "decision": classification.get("decision")}, indent=2))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
