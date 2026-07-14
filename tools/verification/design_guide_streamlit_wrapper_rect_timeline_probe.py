"""Browser/live rect timeline probe for Streamlit wrapper first-paint shifts.

Proof-only. Captures repeated measurements of Streamlit's main layout wrappers
from document start through settle, plus layout-shift sources, so a future
layout patch can target a proven selector. It does not change product code.
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


INIT_SCRIPT = r"""
(() => {
  window.__dgWrapperRectTimeline = {
    samples: [],
    layoutShifts: [],
    errors: [],
    startedAt: Date.now()
  };
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const rectOf = (selector) => {
    try {
      const el = document.querySelector(selector);
      if (!el || !el.getBoundingClientRect) return {exists: false, selector};
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return {
        exists: true,
        selector,
        tag: String(el.tagName || "").toLowerCase(),
        testid: el.getAttribute ? String(el.getAttribute("data-testid") || "") : "",
        cls: String(el.className || "").slice(0, 180),
        text: clean(el.innerText || el.textContent).slice(0, 120),
        display: style.display,
        visibility: style.visibility,
        position: style.position,
        boxSizing: style.boxSizing,
        maxWidth: style.maxWidth,
        widthStyle: style.width,
        marginLeft: style.marginLeft,
        marginRight: style.marginRight,
        paddingLeft: style.paddingLeft,
        paddingRight: style.paddingRight,
        rect: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          top: Math.round(rect.top),
          bottom: Math.round(rect.bottom),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        }
      };
    } catch (err) {
      window.__dgWrapperRectTimeline.errors.push(String(err && err.message || err));
      return {exists: false, selector, error: String(err && err.message || err)};
    }
  };
  const sample = (label) => {
    try {
      window.__dgWrapperRectTimeline.samples.push({
        label,
        at: Date.now(),
        performanceNow: Math.round(performance.now()),
        viewport: {
          width: Math.round(window.innerWidth || 0),
          height: Math.round(window.innerHeight || 0)
        },
        body: {
          width: Math.round(document.body ? document.body.getBoundingClientRect().width : 0),
          height: Math.round(document.body ? document.body.getBoundingClientRect().height : 0),
          scrollHeight: Math.round(document.body ? document.body.scrollHeight : 0)
        },
        wrappers: {
          main: rectOf("main"),
          stMain: rectOf("[data-testid='stMain']"),
          stAppViewContainer: rectOf("[data-testid='stAppViewContainer']"),
          stMainBlockContainer: rectOf("[data-testid='stMainBlockContainer']"),
          blockContainer: rectOf(".block-container"),
          firstVerticalBlock: rectOf("[data-testid='stVerticalBlock']"),
          firstLayoutWrapper: rectOf("[data-testid='stLayoutWrapper']")
        }
      });
    } catch (err) {
      window.__dgWrapperRectTimeline.errors.push("sample:" + String(err && err.message || err));
    }
  };
  window.__dgWrapperRectTimelineSample = sample;
  sample("init");
  [0, 25, 50, 100, 175, 275, 425, 650, 950, 1400, 2100, 3200, 5000].forEach((ms) => {
    setTimeout(() => sample("t+" + ms), ms);
  });
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        window.__dgWrapperRectTimeline.layoutShifts.push({
          value: Number(entry.value || 0),
          startTime: Number(entry.startTime || 0),
          sources: Array.from(entry.sources || []).map((source) => {
            const node = source.node && source.node.nodeType === 1 ? source.node : source.node && source.node.parentElement;
            return {
              tag: node ? String(node.tagName || "").toLowerCase() : "",
              testid: node && node.getAttribute ? String(node.getAttribute("data-testid") || "") : "",
              cls: node ? String(node.className || "").slice(0, 180) : "",
              text: node ? clean(node.innerText || node.textContent).slice(0, 160) : "",
              previousRect: source.previousRect || null,
              currentRect: source.currentRect || null
            };
          })
        });
      }
    }).observe({type: "layout-shift", buffered: true});
  } catch (err) {
    window.__dgWrapperRectTimeline.errors.push("layout_shift_observer:" + String(err && err.message || err));
  }
})();
"""


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _capture(base_url: str, *, recipe: str, wait_ms: int, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.add_init_script(INIT_SCRIPT)
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(max(5200, int(wait_ms)))
        page.evaluate("() => window.__dgWrapperRectTimelineSample && window.__dgWrapperRectTimelineSample('final')")
        payload = dict(page.evaluate("() => window.__dgWrapperRectTimeline || {}") or {})
        browser.close()
    return {"url": url, "timeline": payload}


def _values_for_selector(samples: list[dict[str, Any]], wrapper_key: str, rect_key: str) -> list[int]:
    values: list[int] = []
    for sample in samples:
        wrappers = dict(sample.get("wrappers") or {})
        wrapper = dict(wrappers.get(wrapper_key) or {})
        rect = dict(wrapper.get("rect") or {})
        value = rect.get(rect_key)
        if isinstance(value, (int, float)):
            values.append(int(round(value)))
    return values


def _range(values: list[int]) -> int:
    return max(values) - min(values) if values else 0


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    timeline = dict(capture.get("timeline") or {})
    samples = [dict(row) for row in list(timeline.get("samples") or []) if isinstance(row, dict)]
    shifts = list(timeline.get("layoutShifts") or [])
    wrapper_ranges: dict[str, dict[str, Any]] = {}
    for wrapper_key in (
        "main",
        "stMain",
        "stAppViewContainer",
        "stMainBlockContainer",
        "blockContainer",
        "firstVerticalBlock",
        "firstLayoutWrapper",
    ):
        widths = _values_for_selector(samples, wrapper_key, "width")
        lefts = _values_for_selector(samples, wrapper_key, "left")
        tops = _values_for_selector(samples, wrapper_key, "top")
        heights = _values_for_selector(samples, wrapper_key, "height")
        wrapper_ranges[wrapper_key] = {
            "widths": widths,
            "lefts": lefts,
            "tops": tops,
            "heights": heights,
            "width_range": _range(widths),
            "left_range": _range(lefts),
            "top_range": _range(tops),
            "height_range": _range(heights),
            "exists_count": len(widths),
        }
    shift_total = round(sum(float(row.get("value") or 0.0) for row in shifts), 6)
    top_width_owner = max(wrapper_ranges, key=lambda key: wrapper_ranges[key]["width_range"], default="")
    top_left_owner = max(wrapper_ranges, key=lambda key: wrapper_ranges[key]["left_range"], default="")
    top_top_owner = max(wrapper_ranges, key=lambda key: wrapper_ranges[key]["top_range"], default="")
    material_width_shift = bool(wrapper_ranges.get(top_width_owner, {}).get("width_range", 0) >= 120)
    material_left_shift = bool(wrapper_ranges.get(top_left_owner, {}).get("left_range", 0) >= 80)
    material_top_shift = bool(wrapper_ranges.get(top_top_owner, {}).get("top_range", 0) >= 80)
    if material_width_shift and top_width_owner in {"stMainBlockContainer", "blockContainer"}:
        decision = "SCOPED_MAIN_BLOCK_WIDTH_STABILISATION_CANDIDATE"
        next_slice = "Create a guarded CSS impact experiment for stMainBlockContainer/block-container width stabilisation."
    elif material_left_shift and top_left_owner in {"stMainBlockContainer", "blockContainer"}:
        decision = "SCOPED_MAIN_BLOCK_HORIZONTAL_STABILISATION_CANDIDATE"
        next_slice = "Create a guarded CSS impact experiment for stMainBlockContainer/block-container horizontal positioning."
    elif material_top_shift:
        decision = "VERTICAL_OFFSET_SHIFT_NEEDS_TARGETED_PROOF"
        next_slice = "Audit top-offset contributors before changing layout."
    else:
        decision = "NO_SCOPED_WRAPPER_PATCH_JUSTIFIED"
        next_slice = "Do not patch layout from this sample; continue profiling user-specific huge-gap reproduction."
    return {
        "status": "PASS",
        "decision": decision,
        "layout_shift_total": shift_total,
        "layout_shift_count": len(shifts),
        "sample_count": len(samples),
        "wrapper_ranges": wrapper_ranges,
        "top_width_owner": top_width_owner,
        "top_left_owner": top_left_owner,
        "top_top_owner": top_top_owner,
        "material_width_shift": material_width_shift,
        "material_left_shift": material_left_shift,
        "material_top_shift": material_top_shift,
        "observer_errors": list(timeline.get("errors") or []),
        "recommended_next_slice": next_slice,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_streamlit_wrapper_rect_timeline_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_streamlit_wrapper_rect_timeline_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Streamlit Wrapper Rect Timeline Probe",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{cls.get('decision')}`",
        f"- Layout shift total: `{cls.get('layout_shift_total')}`",
        f"- Sample count: `{cls.get('sample_count')}`",
        f"- Top width owner: `{cls.get('top_width_owner')}`",
        f"- Top left owner: `{cls.get('top_left_owner')}`",
        f"- Top top owner: `{cls.get('top_top_owner')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Wrapper Ranges",
        "",
        "```json",
        json.dumps(cls.get("wrapper_ranges") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Recommendation",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8706)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_WRAPPER_RECT_TIMELINE_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--wait-ms", type=int, default=6500)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    if not args.base_url:
        process = _start_streamlit(args.port)
        _wait_for_http(base_url, timeout_s=60)
    try:
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            wait_ms=int(args.wait_ms),
            headed=bool(args.headed),
        )
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_streamlit_wrapper_rect_timeline_probe.v1",
            "created_at": _stamp(),
            "status": classification["status"],
            "classification": classification,
            "capture": capture,
            "product_behaviour_changed": False,
        }
        json_path, md_path = _write(payload)
        print(json.dumps({"status": payload["status"], "decision": classification["decision"], "json": str(json_path), "report": str(md_path)}, indent=2))
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
