"""Browser/live transient blank-gap ownership snapshot.

Proof-only. Samples the Inputs page rapidly around a reload/rerun transition to
classify the owner of large temporary blank gaps. It does not change layout,
rendering, publication, CTA/apply, family runtimes, visible wording, or
engineering behaviour.
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


def _sample_layout(page, *, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
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
                return {
                  exists: true,
                  visible: visible(el),
                  text: clean(el.innerText || el.textContent).slice(0, 220),
                  tag: String(el.tagName || "").toLowerCase(),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 160),
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
              const all = Array.from(document.querySelectorAll("body *")).filter(visible);
              const shortest = (regex, reject = null) => {
                const matches = all.filter((el) => {
                  const text = clean(el.innerText || el.textContent);
                  return regex.test(text) && !(reject && reject.test(text));
                }).sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  const ah = ar.height * ar.width;
                  const bh = br.height * br.width;
                  return ah - bh || ar.top - br.top;
                });
                return matches[0] || null;
              };
              const topNav = shortest(/Inputs\s+Design\s+Bending\s+Shear/i);
              const inputsHeading = shortest(/^Inputs$/i);
              const batchHeading = shortest(/^Batch design$/i);
              const designGuideHeading = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                if (text !== "Design Guide") return false;
                const parent = clean(el.parentElement ? el.parentElement.innerText || "" : "");
                return !/Design Guide Debug|Debug session state/i.test(parent);
              }).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0] || null;
              const summaryCards = all.filter((el) => /Bending\s+[-—]\s+ULS|Shear\s+[-—]\s+ULS|Crack control|Deflection/i.test(clean(el.innerText || el.textContent))).slice(0, 12);
              const batchCard = all.find((el) => {
                const text = clean(el.innerText || el.textContent);
                return /Active set|Active beam|Add\s+Duplicate|Reset workspace|Show Manager|Hide Manager/i.test(text);
              }) || null;
              const designGuideCard = all.find((el) => {
                const text = clean(el.innerText || el.textContent);
                const testid = el.getAttribute ? String(el.getAttribute("data-testid") || "") : "";
                const cls = String(el.className || "");
                return /design-guide-card/i.test(testid)
                  || /fast-guidance-item|dg-card/i.test(cls)
                  || /Design is efficient|Strengthening required|Repair required|blocked|Apply recommendation|Run one-click/i.test(text);
              }) || null;
              const running = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                const testid = el.getAttribute ? String(el.getAttribute("data-testid") || "") : "";
                return /stStatusWidgetRunning|Running|Stop/i.test(testid + " " + text);
              }).slice(0, 8);
              const plotly = all.filter((el) => /js-plotly-plot|plotly/i.test(String(el.className || ""))).slice(0, 8);
              const gap = (from, to) => {
                if (!from || !to) return null;
                const a = from.getBoundingClientRect();
                const b = to.getBoundingClientRect();
                return Math.round(b.top - a.bottom);
              };
              const rects = {
                top_nav: payload(topNav),
                inputs_heading: payload(inputsHeading),
                first_summary_card: payload(summaryCards[0] || null),
                batch_heading: payload(batchHeading),
                batch_card: payload(batchCard),
                design_guide_heading: payload(designGuideHeading),
                design_guide_card: payload(designGuideCard)
              };
              return {
                label,
                timestamp_ms: Date.now(),
                scroll_y: Math.round(window.scrollY || 0),
                viewport_height: Math.round(window.innerHeight || 0),
                body_height: Math.round(document.body ? document.body.scrollHeight : 0),
                running_indicator_count: running.length,
                plotly_visible_count: plotly.length,
                summary_card_count: summaryCards.length,
                rects,
                gaps: {
                  nav_to_inputs: gap(topNav, inputsHeading),
                  inputs_to_summary: gap(inputsHeading, summaryCards[0] || null),
                  summary_to_batch: gap(summaryCards[summaryCards.length - 1] || null, batchHeading),
                  batch_heading_to_card: gap(batchHeading, batchCard),
                  batch_card_to_design_guide: gap(batchCard, designGuideHeading),
                  design_guide_heading_to_card: gap(designGuideHeading, designGuideCard)
                }
              };
            }
            """,
            label,
        )
        or {}
    )


def _capture(base_url: str, *, recipe: str, headed: bool, sample_count: int, interval_ms: int) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3000)
        samples: list[dict[str, Any]] = [_sample_layout(page, label="settled_before_reload")]
        page.reload(wait_until="domcontentloaded", timeout=90_000)
        for index in range(max(1, sample_count)):
            samples.append(_sample_layout(page, label=f"reload_sample_{index:02d}"))
            page.wait_for_timeout(max(50, interval_ms))
        page.wait_for_timeout(1500)
        samples.append(_sample_layout(page, label="settled_after_reload"))
        browser.close()
    return {"url": url, "recipe": recipe, "samples": samples}


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    samples = list(capture.get("samples") or [])
    gap_rows: list[dict[str, Any]] = []
    for sample in samples:
        gaps = dict(sample.get("gaps") or {})
        for name, value in gaps.items():
            if isinstance(value, (int, float)):
                gap_rows.append(
                    {
                        "sample": sample.get("label"),
                        "gap": name,
                        "px": int(value),
                        "running_indicator_count": int(sample.get("running_indicator_count") or 0),
                        "plotly_visible_count": int(sample.get("plotly_visible_count") or 0),
                        "scroll_y": sample.get("scroll_y"),
                    }
                )
    largest = max(gap_rows, key=lambda row: row["px"], default={})
    large_rows = [row for row in gap_rows if int(row.get("px") or 0) >= 300]
    running_large = [row for row in large_rows if int(row.get("running_indicator_count") or 0) > 0]
    plotly_large = [row for row in large_rows if int(row.get("plotly_visible_count") or 0) > 0]
    if running_large:
        diagnosis = "TRANSIENT_GAP_WITH_STREAMLIT_RUNNING_INDICATOR"
        next_slice = "Audit rerun/status-widget shell ownership before changing layout."
    elif plotly_large:
        diagnosis = "TRANSIENT_GAP_WITH_MODEL_PLOTLY_REDRAW"
        next_slice = "Audit fast model/Plotly redraw deferral or stable-height reservation."
    elif large_rows:
        diagnosis = "TRANSIENT_LARGE_GAP_OWNER_UNCLEAR"
        next_slice = "Add finer page-slot and placeholder trace markers around the largest gap."
    else:
        diagnosis = "NO_TRANSIENT_HUGE_BLANK_GAP_REPRODUCED"
        next_slice = "Use a user-reported live URL/session or interaction trigger to reproduce the huge blank gap."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "largest_gap": largest,
        "large_gap_count": len(large_rows),
        "running_large_gap_count": len(running_large),
        "plotly_large_gap_count": len(plotly_large),
        "sample_count": len(samples),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Transient Blank Gap Ownership Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Largest gap: `{cls.get('largest_gap')}`",
        f"- Large gap count (>=300 px): `{cls.get('large_gap_count')}`",
        f"- Running-indicator large gaps: `{cls.get('running_large_gap_count')}`",
        f"- Plotly large gaps: `{cls.get('plotly_large_gap_count')}`",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
        "## Samples",
        "",
        "```json",
        json.dumps(payload.get("samples") or [], indent=2, sort_keys=True, default=str)[:12000],
        "```",
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_transient_blank_gap_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_transient_blank_gap_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8623)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_TRANSIENT_GAP_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--sample-count", type=int, default=24)
    parser.add_argument("--interval-ms", type=int, default=180)
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
            _wait_for_http(base_url, timeout_s=70.0)
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            headed=bool(args.headed),
            sample_count=int(args.sample_count),
            interval_ms=int(args.interval_ms),
        )
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_transient_blank_gap_ownership.v1",
            "created_at": created_at,
            "status": classification["status"],
            "classification": classification,
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
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(json.dumps({"status": payload["status"], **classification}, indent=2, sort_keys=True))
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
