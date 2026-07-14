"""Audit exact DOM owners inside transient Summary-to-Batch rerun gaps.

Proof-only. Samples during reload/rerun and records visible elements inside the
largest Summary-to-Batch gap. It does not change layout, rendering,
publication, CTA/apply, family runtimes, visible wording, or engineering
behaviour.
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


def _gap_owner_sample(page, *, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const horizontallyInViewport = (rect) => rect.right >= 0 && rect.left <= window.innerWidth;
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && horizontallyInViewport(rect)
                  && rect.width > 2
                  && rect.height > 2;
              };
              const payload = (el) => {
                if (!el) return {exists: false, visible: false};
                const rect = el.getBoundingClientRect();
                return {
                  exists: true,
                  visible: visible(el),
                  tag: String(el.tagName || "").toLowerCase(),
                  text: clean(el.innerText || el.textContent).slice(0, 240),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 180),
                  rect: {
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom),
                    height: Math.round(rect.height),
                    width: Math.round(rect.width),
                    left: Math.round(rect.left),
                    right: Math.round(rect.right)
                  }
                };
              };
              const all = Array.from(document.querySelectorAll("body *")).filter(visible);
              const shortest = (regex) => {
                return all.filter((el) => regex.test(clean(el.innerText || el.textContent))).sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return (ar.height * ar.width) - (br.height * br.width) || ar.top - br.top;
                })[0] || null;
              };
              const summaryCards = all.filter((el) => /Bending\s+[-—]\s+ULS|Shear\s+[-—]\s+ULS|Crack control|Deflection/i.test(clean(el.innerText || el.textContent))).slice(0, 12);
              const batchHeading = shortest(/^Batch design$/i);
              const from = summaryCards[summaryCards.length - 1] || null;
              const to = batchHeading || null;
              const fromRect = from ? from.getBoundingClientRect() : null;
              const toRect = to ? to.getBoundingClientRect() : null;
              const gapTop = fromRect ? fromRect.bottom : null;
              const gapBottom = toRect ? toRect.top : null;
              const gapPx = (gapTop !== null && gapBottom !== null) ? Math.round(gapBottom - gapTop) : null;
              const inGap = all.filter((el) => {
                if (gapTop === null || gapBottom === null) return false;
                const rect = el.getBoundingClientRect();
                return rect.bottom > gapTop && rect.top < gapBottom && horizontallyInViewport(rect);
              }).slice(0, 60);
              const running = all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                const testid = el.getAttribute ? String(el.getAttribute("data-testid") || "") : "";
                return /stStatusWidgetRunning|Running|Stop/i.test(testid + " " + text);
              }).slice(0, 20);
              const owners = {};
              for (const el of inGap) {
                const testid = el.getAttribute ? String(el.getAttribute("data-testid") || "") : "";
                const cls = String(el.className || "");
                let owner = "unknown";
                if (/stStatusWidgetRunning|Running|Stop/i.test(testid + " " + clean(el.innerText || el.textContent))) owner = "streamlit_running_status";
                else if (/plotly|js-plotly/i.test(cls)) owner = "plotly_or_model";
                else if (/stWidget|stSelectbox|stBaseButton|stButton|stMarkdown/i.test(testid + " " + cls)) owner = "batch_or_input_widget";
                else if (/design-guide|dg-card|fast-guidance/i.test(testid + " " + cls)) owner = "design_guide";
                owners[owner] = (owners[owner] || 0) + 1;
              }
              return {
                label,
                timestamp_ms: Date.now(),
                scroll_y: Math.round(window.scrollY || 0),
                viewport_height: Math.round(window.innerHeight || 0),
                gap: {
                  name: "summary_to_batch",
                  px: gapPx,
                  top: gapTop === null ? null : Math.round(gapTop),
                  bottom: gapBottom === null ? null : Math.round(gapBottom)
                },
                from_element: payload(from),
                to_element: payload(to),
                running_indicator_count: running.length,
                running_indicators: running.map(payload),
                elements_in_gap_count: inGap.length,
                owner_counts_in_gap: owners,
                elements_in_gap: inGap.map(payload)
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
        page.reload(wait_until="domcontentloaded", timeout=90_000)
        samples: list[dict[str, Any]] = []
        for index in range(max(1, sample_count)):
            samples.append(_gap_owner_sample(page, label=f"reload_sample_{index:02d}"))
            page.wait_for_timeout(max(50, interval_ms))
        page.wait_for_timeout(1000)
        samples.append(_gap_owner_sample(page, label="settled_after_reload"))
        browser.close()
    return {"url": url, "recipe": recipe, "samples": samples}


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    samples = list(capture.get("samples") or [])
    largest = max(
        samples,
        key=lambda row: int(((row.get("gap") or {}).get("px") or -10_000)),
        default={},
    )
    gap = dict(largest.get("gap") or {})
    owner_counts = dict(largest.get("owner_counts_in_gap") or {})
    running_count = int(largest.get("running_indicator_count") or 0)
    largest_px = int(gap.get("px") or 0)
    if largest_px < 300:
        diagnosis = "NO_LARGE_SUMMARY_TO_BATCH_GAP_REPRODUCED"
        next_slice = "Use a live user-triggered interaction to reproduce the gap before changing layout."
    elif running_count > 0 and not owner_counts:
        diagnosis = "GAP_CORRELATES_WITH_RUNNING_STATUS_BUT_EMPTY_REGION"
        next_slice = "Reserve stable Summary-to-Batch region height during rerun/status-widget activity."
    elif owner_counts.get("streamlit_running_status"):
        diagnosis = "STREAMLIT_RUNNING_STATUS_INSIDE_GAP"
        next_slice = "Audit/status-widget wrapper CSS before adding a stable-height guard."
    elif owner_counts.get("batch_or_input_widget"):
        diagnosis = "BATCH_INPUT_WIDGETS_OCCUPY_TRANSIENT_GAP"
        next_slice = "Audit Batch panel mount order/stable-height reservation."
    else:
        diagnosis = "SUMMARY_TO_BATCH_GAP_OWNER_UNCLEAR"
        next_slice = "Add lower-level page-content-slot trace markers around the gap."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "largest_gap_px": largest_px,
        "largest_gap_sample": largest.get("label"),
        "running_indicator_count_at_largest_gap": running_count,
        "owner_counts_in_largest_gap": owner_counts,
        "elements_in_largest_gap": int(largest.get("elements_in_gap_count") or 0),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    largest = max(
        list(payload.get("samples") or []),
        key=lambda row: int(((row.get("gap") or {}).get("px") or -10_000)),
        default={},
    )
    lines = [
        "# Design Guide Rerun Status-Widget Gap Owner Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Largest gap px: `{cls.get('largest_gap_px')}`",
        f"- Largest gap sample: `{cls.get('largest_gap_sample')}`",
        f"- Running indicators at largest gap: `{cls.get('running_indicator_count_at_largest_gap')}`",
        f"- Owner counts in largest gap: `{cls.get('owner_counts_in_largest_gap')}`",
        "",
        "## Largest Sample",
        "",
        "```json",
        json.dumps(largest, indent=2, sort_keys=True, default=str)[:12000],
        "```",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
    ]
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_rerun_status_widget_gap_owner_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_rerun_status_widget_gap_owner_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8624)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_STATUS_GAP_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--sample-count", type=int, default=26)
    parser.add_argument("--interval-ms", type=int, default=160)
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
            "schema": "design_guide_rerun_status_widget_gap_owner.v1",
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
