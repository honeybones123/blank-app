"""Browser/live corrected transient gap anchor snapshot.

The earlier Summary-to-Batch gap owner audit intentionally used broad text
anchors. This snapshot tightens those anchors so top navigation labels such as
"Crack Control" are not mistaken for check-summary cards. It records the real
transient gaps during reload/rerun before any additional layout guard is added.
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


def _sample(page, *, label: str) -> dict[str, Any]:
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
                  && rect.right >= 0
                  && rect.left <= window.innerWidth
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
                  text: clean(el.innerText || el.textContent).slice(0, 220),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 160),
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
              const textOf = (el) => clean(el.innerText || el.textContent);
              const byShortestText = (regex) => all
                .filter((el) => regex.test(textOf(el)))
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return (ar.height * ar.width) - (br.height * br.width) || ar.top - br.top;
                })[0] || null;
              const byTopText = (regex) => all
                .filter((el) => regex.test(textOf(el)))
                .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0] || null;
              const byBottomText = (regex) => all
                .filter((el) => regex.test(textOf(el)))
                .sort((a, b) => b.getBoundingClientRect().bottom - a.getBoundingClientRect().bottom)[0] || null;
              const actualSummaryRows = all.filter((el) => {
                const text = textOf(el);
                const testid = el.getAttribute ? String(el.getAttribute("data-testid") || "") : "";
                const rect = el.getBoundingClientRect();
                const hasCheckTitle = /(Bending\s+[—-]\s+ULS|Shear\s+[—-]\s+ULS|Crack control\s+[—-]\s+SLS|Deflection\s+[—-]\s+SLS)/i.test(text);
                const hasEngineeringColumns = /(Applied|Capacity|Utilisation|Calculated deflection|Design limit|Limit)/i.test(text);
                return hasCheckTitle && hasEngineeringColumns && rect.height >= 35 && rect.width > 400 && !/stRadio/i.test(testid);
              }).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
              const nav = byShortestText(/^Inputs Design Bending Shear Creep Shrinkage Crack Control Deflection$/i);
              const inputsHeading = byShortestText(/^Inputs$/i);
              const firstSummary = actualSummaryRows[0] || null;
              const lastSummary = actualSummaryRows[actualSummaryRows.length - 1] || null;
              const batchHeading = byShortestText(/^Batch design$/i);
              const designGuideHeading = byShortestText(/^Design Guide$/i);
              const gap = (from, to, name) => {
                const fromRect = from ? from.getBoundingClientRect() : null;
                const toRect = to ? to.getBoundingClientRect() : null;
                return {
                  name,
                  px: fromRect && toRect ? Math.round(toRect.top - fromRect.bottom) : null,
                  top: fromRect ? Math.round(fromRect.bottom) : null,
                  bottom: toRect ? Math.round(toRect.top) : null,
                  from: payload(from),
                  to: payload(to)
                };
              };
              const bodyText = clean(document.body ? document.body.innerText : "");
              const running = all.filter((el) => {
                const text = textOf(el);
                const testid = el.getAttribute ? String(el.getAttribute("data-testid") || "") : "";
                return /stStatusWidgetRunning|Running|Stop/i.test(testid + " " + text);
              });
              const gaps = [
                gap(nav, inputsHeading, "nav_to_inputs_heading"),
                gap(inputsHeading, firstSummary, "inputs_heading_to_first_summary"),
                gap(lastSummary, batchHeading, "strict_summary_to_batch"),
                gap(batchHeading, designGuideHeading, "batch_to_design_guide")
              ];
              return {
                label,
                timestamp_ms: Date.now(),
                scroll_y: Math.round(window.scrollY || 0),
                viewport_height: Math.round(window.innerHeight || 0),
                actual_summary_row_count: actualSummaryRows.length,
                actual_summary_rows: actualSummaryRows.slice(0, 8).map(payload),
                gaps,
                largest_gap: gaps
                  .filter((row) => typeof row.px === "number")
                  .sort((a, b) => b.px - a.px)[0] || null,
                running_indicator_count: running.length,
                start_your_design_present: /Start Your Design/i.test(bodyText),
                stable_rerun_shell_present: /Inputs page stable rerun shell/i.test(bodyText),
                design_guide_visible: !!designGuideHeading
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
            samples.append(_sample(page, label=f"reload_sample_{index:02d}"))
            page.wait_for_timeout(max(50, interval_ms))
        page.wait_for_timeout(1000)
        samples.append(_sample(page, label="settled_after_reload"))
        browser.close()
    return {"url": url, "recipe": recipe, "samples": samples}


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    samples = list(capture.get("samples") or [])
    largest = max(
        samples,
        key=lambda row: int(((row.get("largest_gap") or {}).get("px") or -10_000)),
        default={},
    )
    largest_gap = dict(largest.get("largest_gap") or {})
    largest_px = int(largest_gap.get("px") or 0)
    false_nav_anchor_avoided = all(
        all(
            str((summary_row or {}).get("text") or "").strip() != "Crack Control"
            for summary_row in (row.get("actual_summary_rows") or [])
        )
        for row in samples
    )
    start_present = bool(largest.get("start_your_design_present"))
    running_count = int(largest.get("running_indicator_count") or 0)
    if largest_px >= 300 and start_present:
        diagnosis = "CORRECTED_LARGE_GAP_STILL_HAS_LANDING_FLASH"
        next_slice = "Revisit the landing flash guard before adding status-wrapper guards."
    elif largest_px >= 300 and running_count:
        diagnosis = "CORRECTED_LARGE_GAP_STATUS_WRAPPER_OR_SHELL"
        next_slice = "Add a focused status-wrapper/stable-shell guard readiness proof."
    elif largest_px >= 300:
        diagnosis = "CORRECTED_LARGE_GAP_OWNER_UNCLEAR"
        next_slice = "Add lower-level wrapper probes around the largest corrected gap."
    else:
        diagnosis = "NO_CORRECTED_LARGE_TRANSIENT_GAP_REPRODUCED"
        next_slice = "Do not add a layout guard from the old broad-anchor gap number."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "largest_gap_px": largest_px,
        "largest_gap_name": largest_gap.get("name"),
        "largest_gap_sample": largest.get("label"),
        "actual_summary_row_count_at_largest_gap": largest.get("actual_summary_row_count"),
        "running_indicator_count_at_largest_gap": running_count,
        "start_your_design_present_at_largest_gap": start_present,
        "stable_rerun_shell_present_at_largest_gap": bool(largest.get("stable_rerun_shell_present")),
        "false_nav_anchor_avoided": bool(false_nav_anchor_avoided),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    largest = max(
        list(payload.get("samples") or []),
        key=lambda row: int(((row.get("largest_gap") or {}).get("px") or -10_000)),
        default={},
    )
    return "\n".join(
        [
            "# Design Guide Corrected Transient Gap Anchor Snapshot",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Diagnosis: `{cls.get('diagnosis')}`",
            f"- Largest corrected gap px: `{cls.get('largest_gap_px')}`",
            f"- Largest corrected gap name: `{cls.get('largest_gap_name')}`",
            f"- Largest sample: `{cls.get('largest_gap_sample')}`",
            f"- Actual summary rows at largest gap: `{cls.get('actual_summary_row_count_at_largest_gap')}`",
            f"- Running indicators at largest gap: `{cls.get('running_indicator_count_at_largest_gap')}`",
            f"- Start Your Design at largest gap: `{cls.get('start_your_design_present_at_largest_gap')}`",
            f"- Stable rerun shell at largest gap: `{cls.get('stable_rerun_shell_present_at_largest_gap')}`",
            "",
            "## Largest Sample",
            "",
            "```json",
            json.dumps(largest, indent=2, sort_keys=True, default=str)[:14000],
            "```",
            "",
            "## Next Safe Slice",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_corrected_transient_gap_anchor_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_corrected_transient_gap_anchor_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8626)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_CORRECTED_GAP_URL"))
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
        payload: dict[str, Any] = {
            "schema": "design_guide_corrected_transient_gap_anchor.v1",
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
