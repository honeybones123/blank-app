"""Browser/live timeline for summary shell-to-card replacement.

Proof-only. This verifier samples the Inputs summary placeholder and final
summary-card stack through first paint so smoothness work can distinguish
between height reservation, placeholder replacement gaps, and final-card
content settling. It does not change product behaviour.
"""

from __future__ import annotations

import argparse
from datetime import datetime
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

from tools.verification.design_guide_rerun_trigger_source_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _query,
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


INIT_SCRIPT = r"""
(() => {
  window.__dgSummaryReplacementTimeline = {
    samples: [],
    layoutShifts: [],
    errors: []
  };
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
  const rectPayload = (el) => {
    if (!el || !el.getBoundingClientRect) return {exists: false, visible: false};
    const rect = el.getBoundingClientRect();
    return {
      exists: true,
      visible: visible(el),
      top: Math.round(rect.top),
      bottom: Math.round(rect.bottom),
      height: Math.round(rect.height),
      width: Math.round(rect.width),
      text: clean(el.innerText || el.textContent).slice(0, 180),
      cls: String(el.className || "").slice(0, 160),
      testid: el.getAttribute ? String(el.getAttribute("data-testid") || "") : ""
    };
  };
  const cardEnvelope = (cards) => {
    const rects = cards.map(rectPayload).filter((row) => row && row.visible);
    if (!rects.length) return {exists: false, visible: false, count: 0};
    const top = Math.min(...rects.map((row) => row.top));
    const bottom = Math.max(...rects.map((row) => row.bottom));
    return {exists: true, visible: true, count: rects.length, top, bottom, height: Math.max(0, bottom - top)};
  };
  const sample = () => {
    try {
      const shell = document.querySelector(".inputs-first-paint-shell");
      const stack = document.querySelector(".summary-card-stack");
      const cards = Array.from(document.querySelectorAll(".summary-check-card"));
      const openDetails = cards.filter((card) => {
        const details = card.querySelector("details");
        return details && details.open;
      }).length;
      const title = Array.from(document.querySelectorAll("h1,h2,h3,[role='heading']"))
        .find((el) => /^Inputs$/i.test(clean(el.innerText || el.textContent)));
      window.__dgSummaryReplacementTimeline.samples.push({
        at: Math.round(performance.now()),
        title: rectPayload(title),
        shell: rectPayload(shell),
        stack: rectPayload(stack),
        cardEnvelope: cardEnvelope(cards),
        cardCount: cards.filter(visible).length,
        openDetails,
        bodyHeight: Math.round(document.body ? document.body.scrollHeight : 0)
      });
    } catch (err) {
      window.__dgSummaryReplacementTimeline.errors.push(String(err && err.message || err));
    }
  };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        const sources = Array.from(entry.sources || []).map((source) => {
          const node = source.node && source.node.nodeType === 1 ? source.node : source.node && source.node.parentElement;
          return rectPayload(node);
        });
        window.__dgSummaryReplacementTimeline.layoutShifts.push({
          at: Math.round(entry.startTime || 0),
          value: Number(entry.value || 0),
          sourceCount: sources.length,
          sources
        });
      }
    }).observe({type: "layout-shift", buffered: true});
  } catch (err) {
    window.__dgSummaryReplacementTimeline.errors.push("layout_shift_observer:" + String(err && err.message || err));
  }
  sample();
  const timer = setInterval(sample, 50);
  setTimeout(() => clearInterval(timer), 7500);
})();
"""


def _capture(base_url: str, *, recipe: str, headed: bool, wait_ms: int) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        context.add_init_script(INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe, "batch_design_open": "0"})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(max(2000, wait_ms))
        capture = dict(page.evaluate("() => window.__dgSummaryReplacementTimeline || {}") or {})
        browser.close()
    capture["requested_url"] = url
    capture["recipe"] = recipe
    return capture


def _first_at(samples: list[dict[str, Any]], predicate) -> int | None:
    for row in samples:
        try:
            if predicate(row):
                return int(row.get("at") or 0)
        except Exception:
            continue
    return None


def _last_at(samples: list[dict[str, Any]], predicate) -> int | None:
    found: int | None = None
    for row in samples:
        try:
            if predicate(row):
                found = int(row.get("at") or 0)
        except Exception:
            continue
    return found


def _summarise(capture: dict[str, Any]) -> dict[str, Any]:
    samples = [dict(row or {}) for row in list(capture.get("samples") or [])]
    shifts = [dict(row or {}) for row in list(capture.get("layoutShifts") or [])]
    shell_seen_at = _first_at(samples, lambda row: bool((row.get("shell") or {}).get("visible")))
    shell_last_at = _last_at(samples, lambda row: bool((row.get("shell") or {}).get("visible")))
    stack_seen_at = _first_at(samples, lambda row: bool((row.get("stack") or {}).get("visible")))
    cards_seen_at = _first_at(samples, lambda row: int(row.get("cardCount") or 0) > 0)
    max_shell = max(
        [int((row.get("shell") or {}).get("height") or 0) for row in samples if (row.get("shell") or {}).get("visible")]
        or [0]
    )
    stack_heights = [
        int((row.get("stack") or {}).get("height") or 0)
        for row in samples
        if (row.get("stack") or {}).get("visible")
    ]
    envelope_heights = [
        int((row.get("cardEnvelope") or {}).get("height") or 0)
        for row in samples
        if (row.get("cardEnvelope") or {}).get("visible")
    ]
    final_stack = stack_heights[-1] if stack_heights else 0
    final_envelope = envelope_heights[-1] if envelope_heights else 0
    max_stack = max(stack_heights or [0])
    max_envelope = max(envelope_heights or [0])
    min_stack_after_seen = min(stack_heights or [0])
    open_details_max = max([int(row.get("openDetails") or 0) for row in samples] or [0])
    replacement_gap_ms = None
    if shell_last_at is not None and cards_seen_at is not None:
        replacement_gap_ms = int(cards_seen_at) - int(shell_last_at)
    shift_total = round(sum(float(row.get("value") or 0.0) for row in shifts), 6)
    shell_shortfall = max(0, max(final_stack, final_envelope) - max_shell)
    stack_growth_after_seen = max(0, max_stack - min_stack_after_seen)
    shift_after_cards = round(
        sum(float(row.get("value") or 0.0) for row in shifts if cards_seen_at is not None and int(row.get("at") or 0) >= cards_seen_at),
        6,
    )

    if replacement_gap_ms is not None and replacement_gap_ms > 120:
        decision = "REPLACEMENT_GAP_DOMINATES"
        next_slice = "Create readiness for persistent summary container/min-height across st.empty replacement."
    elif stack_growth_after_seen > 80:
        decision = "FINAL_CARD_CONTENT_SETTLING_DOMINATES"
        next_slice = "Create readiness for summary-card internal stable min-height or font/icon settling guard."
    elif shell_shortfall > 80:
        decision = "SHELL_HEIGHT_STILL_SHORT"
        next_slice = "Tune shell reservation only if source-node proof still points to summary cards."
    else:
        decision = "SUMMARY_REPLACEMENT_BOUNDED"
        next_slice = "Do not further tune summary shell; inspect Streamlit wrapper width settling or model/Plotly remount."

    return {
        "status": "PASS",
        "decision": decision,
        "sample_count": len(samples),
        "layout_shift_total": shift_total,
        "layout_shift_after_cards_seen": shift_after_cards,
        "shell_seen_at_ms": shell_seen_at,
        "shell_last_at_ms": shell_last_at,
        "stack_seen_at_ms": stack_seen_at,
        "cards_seen_at_ms": cards_seen_at,
        "replacement_gap_ms": replacement_gap_ms,
        "max_shell_height_px": max_shell,
        "final_stack_height_px": final_stack,
        "max_stack_height_px": max_stack,
        "min_stack_height_after_seen_px": min_stack_after_seen,
        "final_card_envelope_height_px": final_envelope,
        "max_card_envelope_height_px": max_envelope,
        "shell_shortfall_px": shell_shortfall,
        "stack_growth_after_seen_px": stack_growth_after_seen,
        "open_details_max": open_details_max,
        "recommended_next_slice": next_slice,
        "observer_errors": list(capture.get("errors") or []),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_summary_replacement_timeline_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_summary_replacement_timeline_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary = dict(payload.get("summary") or {})
    lines = [
        "# Design Guide Summary Replacement Timeline Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{summary.get('decision')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Layout shift total: `{summary.get('layout_shift_total')}`",
        f"- Replacement gap: `{summary.get('replacement_gap_ms')}` ms",
        f"- Shell shortfall: `{summary.get('shell_shortfall_px')}` px",
        f"- Stack growth after seen: `{summary.get('stack_growth_after_seen_px')}` px",
        f"- Recommended next slice: `{summary.get('recommended_next_slice')}`",
        "",
        "## Summary Evidence",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Rules",
        "- Snapshot-only.",
        "- No engineering behaviour, visible wording, CTA/apply, publication, render ownership, or family runtime changed.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8670)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_SUMMARY_REPLACEMENT_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--wait-ms", type=int, default=8000)
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
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
            _wait_for_http(base_url, timeout_s=70.0)
        capture = _capture(base_url, recipe=str(args.recipe), headed=bool(args.headed), wait_ms=int(args.wait_ms))
        summary = _summarise(capture)
        payload = {
            "schema": "design_guide_summary_replacement_timeline.v1",
            "created_at": created_at,
            "status": summary["status"],
            "summary": summary,
            "capture": capture,
            "product_behaviour_changed": False,
            "behaviour_scope": {
                "engineering_behaviour_changed": False,
                "visible_wording_changed": False,
                "cta_apply_changed": False,
                "publication_changed": False,
                "family_runtime_changed": False,
                "render_ownership_changed": False,
            },
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], **summary}, indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
