"""Detailed owner audit for Streamlit-wrapper layout shifts.

Proof-only. The first-paint owner audit currently classifies the remaining
layout shift as Streamlit wrapper dominated. This verifier captures source-node
ancestor chains for layout-shift entries so a future CSS/layout fix can target
the exact wrapper/panel rather than adding broad spacing.

It does not change layout, rendering, publication, CTA/apply semantics, visible
wording, widget keys, family runtimes, or engineering behaviour.
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
  window.__dgWrapperShiftDetail = {layoutShifts: [], errors: []};
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const nodePayload = (node) => {
    const el = node && node.nodeType === 1 ? node : node && node.parentElement;
    if (!el || !el.getBoundingClientRect) return {exists: false};
    const rect = el.getBoundingClientRect();
    return {
      exists: true,
      tag: String(el.tagName || "").toLowerCase(),
      testid: el.getAttribute ? String(el.getAttribute("data-testid") || "") : "",
      cls: String(el.className || "").slice(0, 240),
      id: String(el.id || ""),
      text: clean(el.innerText || el.textContent).slice(0, 220),
      rect: {
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      }
    };
  };
  const chainFor = (node) => {
    const chain = [];
    let el = node && node.nodeType === 1 ? node : node && node.parentElement;
    for (let i = 0; el && i < 9; i += 1, el = el.parentElement) {
      chain.push(nodePayload(el));
    }
    return chain;
  };
  const ownerForChain = (chain) => {
    const haystack = chain.map((row) => [row.testid, row.cls, row.text].join(" ")).join(" ");
    if (/summary-check-card|summary-card-stack|Bending\s+[-—]\s+ULS|Shear\s+[-—]\s+ULS/i.test(haystack)) return "summary_cards";
    if (/Batch design|Active set|Bulk Beam Manager/i.test(haystack)) return "batch_design_panel";
    if (/js-plotly-plot|plotly|inputs_section_2d_diagram_chart|inputs_section_3d_diagram|Model/i.test(haystack)) return "model_panel";
    if (/design-guide-proof-pending|design-guide-card|fast-guidance-item|Design Guide/i.test(haystack)) return "design_guide_panel";
    if (/stMainBlockContainer|stVerticalBlock|stElementContainer|stLayoutWrapper|stColumn/i.test(haystack)) return "streamlit_layout_wrapper";
    return "unknown";
  };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.hadRecentInput) continue;
        const sources = (entry.sources || []).map((source) => {
          const chain = chainFor(source.node);
          return {
            owner: ownerForChain(chain),
            node: nodePayload(source.node),
            previousRect: source.previousRect || null,
            currentRect: source.currentRect || null,
            chain
          };
        });
        window.__dgWrapperShiftDetail.layoutShifts.push({
          value: Number(entry.value || 0),
          startTime: Number(entry.startTime || 0),
          sourceCount: sources.length,
          sources
        });
      }
    }).observe({type: "layout-shift", buffered: true});
  } catch (err) {
    window.__dgWrapperShiftDetail.errors.push(String(err && err.message || err));
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
        page.wait_for_timeout(max(1000, wait_ms))
        detail = dict(page.evaluate("() => window.__dgWrapperShiftDetail || {}") or {})
        dom = dict(
            page.evaluate(
                r"""
                () => {
                  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
                  const el = document.querySelector('[data-testid="stMainBlockContainer"]')
                    || document.querySelector('.stMainBlockContainer')
                    || document.querySelector('main');
                  const rect = el && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                  return {
                    url: window.location.href,
                    bodyHeight: Math.round(document.body ? document.body.scrollHeight : 0),
                    viewportHeight: Math.round(window.innerHeight || 0),
                    mainText: el ? clean(el.innerText || el.textContent).slice(0, 400) : "",
                    mainRect: rect ? {
                      top: Math.round(rect.top),
                      bottom: Math.round(rect.bottom),
                      height: Math.round(rect.height),
                      width: Math.round(rect.width)
                    } : null
                  };
                }
                """
            )
            or {}
        )
        browser.close()
    return {"url": url, "detail": detail, "dom": dom}


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    shifts = list((capture.get("detail") or {}).get("layoutShifts") or [])
    owner_value: dict[str, float] = {}
    owner_sources: dict[str, int] = {}
    top_rows: list[dict[str, Any]] = []
    for shift in shifts:
        value = float(shift.get("value") or 0.0)
        owners = set()
        for source in list(shift.get("sources") or []):
            owner = str(source.get("owner") or "unknown")
            owners.add(owner)
            owner_sources[owner] = owner_sources.get(owner, 0) + 1
        for owner in owners or {"unknown"}:
            owner_value[owner] = owner_value.get(owner, 0.0) + value
        top_rows.append(
            {
                "value": value,
                "startTime": shift.get("startTime"),
                "owners": sorted(owners),
                "sources": list(shift.get("sources") or [])[:3],
            }
        )
    top_rows.sort(key=lambda row: float(row.get("value") or 0.0), reverse=True)
    top_owner = max(owner_value, key=owner_value.get, default="none")
    total = round(sum(float(row.get("value") or 0.0) for row in shifts), 6)
    if not shifts:
        diagnosis = "NO_LAYOUT_SHIFT_REPRODUCED"
        next_slice = "Do not change layout from this sample; rerun with a reproducing live state."
    elif top_owner == "streamlit_layout_wrapper":
        diagnosis = "STREAMLIT_WRAPPER_CONFIRMED_AS_TOP_SHIFT_OWNER"
        next_slice = "Create a readiness proof for a narrow wrapper containment/stable-min-height experiment."
    elif top_owner == "batch_design_panel":
        diagnosis = "BATCH_PANEL_CONFIRMED_AS_TOP_SHIFT_OWNER"
        next_slice = "Create a Batch panel mount/height reservation readiness proof."
    elif top_owner == "summary_cards":
        diagnosis = "SUMMARY_CARDS_REMAIN_TOP_SHIFT_OWNER"
        next_slice = "Revisit summary first-paint shell/containment with exact source chains."
    else:
        diagnosis = "LAYOUT_SHIFT_OWNER_STILL_MIXED"
        next_slice = "Use the top source chains to pick a narrower owner-specific probe."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "layout_shift_total": total,
        "top_owner": top_owner,
        "owner_value": {key: round(value, 6) for key, value in sorted(owner_value.items())},
        "owner_sources": owner_sources,
        "top_shift_rows": top_rows[:8],
        "observer_errors": list((capture.get("detail") or {}).get("errors") or []),
        "recommended_next_slice": next_slice,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_streamlit_wrapper_shift_detail_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_streamlit_wrapper_shift_detail_{stamp}.md"
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Streamlit Wrapper Shift Detail Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Layout shift total: `{cls.get('layout_shift_total')}`",
        f"- Top owner: `{cls.get('top_owner')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Owner Value",
        "",
        "```json",
        json.dumps(cls.get("owner_value") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Top Shift Rows",
        "",
        "```json",
        json.dumps(cls.get("top_shift_rows") or [], indent=2, sort_keys=True, default=str)[:12000],
        "```",
        "",
        "## Recommendation",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
    ]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8691)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_WRAPPER_SHIFT_DETAIL_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--wait-ms", type=int, default=6500)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://127.0.0.1:{args.port}")
    if not args.base_url:
        process = _start_streamlit(args.port)
        _wait_for_http(base_url, timeout_s=90)
    try:
        capture = _capture(base_url, recipe=args.recipe, wait_ms=args.wait_ms, headed=args.headed)
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_streamlit_wrapper_shift_detail.v1",
            "created_at": _stamp(),
            "status": classification["status"],
            "base_url": base_url,
            "recipe": args.recipe,
            "product_behaviour_changed": False,
            **capture,
            "classification": classification,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], "diagnosis": classification["diagnosis"]}, indent=2))
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
