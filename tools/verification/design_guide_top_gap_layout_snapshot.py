"""Browser/live top-gap layout snapshot for the Inputs page.

Audit-only. This verifier measures the vertical gap between the page heading/nav
and the first real Inputs content while the Design Guide/summary shells load. It
does not change product behaviour, contracts, publication, CTA/apply routing, or
visible wording.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_URL = "http://localhost:8504/?page=inputs"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _timestamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _wait_for_live_url(url: str, *, timeout_s: float = 30.0) -> None:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(base) as response:  # noqa: S310 - local verifier only
                if 200 <= int(response.status) < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.35)
    raise RuntimeError(f"Timed out waiting for live app at {base}: {last_error}")


def _snapshot(page, *, label: str) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            (label) => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const rectPayload = (rect) => ({
                top: Math.round(rect.top),
                bottom: Math.round(rect.bottom),
                height: Math.round(rect.height),
                width: Math.round(rect.width),
                left: Math.round(rect.left),
                right: Math.round(rect.right)
              });
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.01
                  && rect.width > 2
                  && rect.height > 2;
              };
              const findByText = (selector, needle) => {
                const target = String(needle || "").toLowerCase();
                return Array.from(document.querySelectorAll(selector)).find((el) =>
                  clean(el.innerText || el.textContent).toLowerCase().includes(target)
                ) || null;
              };
              const payload = (name, el) => {
                if (!el) return {name, exists: false, visible: false, rect: null, text: ""};
                const rect = el.getBoundingClientRect();
                return {
                  name,
                  exists: true,
                  visible: visible(el),
                  rect: rectPayload(rect),
                  text: clean(el.innerText || el.textContent).slice(0, 240),
                  cls: String(el.className || "").slice(0, 160),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null
                };
              };

              const beamHeading = findByText("h1, h2, h3, [role='heading']", "Beam design");
              const inputsHeading = findByText("h1, h2, h3, [role='heading']", "Inputs");
              const batchHeading = findByText("h1, h2, h3, [role='heading']", "Batch design");
              const designGuideHeading = findByText("h1, h2, h3, [role='heading']", "Design Guide");
              const summaryCard = findByText("body *", "Bending — ULS")
                || findByText("body *", "Bending - ULS");
              const firstPaintShell = document.querySelector(".inputs-first-paint-shell");
              const settleWaitShell = document.querySelector("[data-testid='design-guide-settle-wait']");
              const proofPendingShell = document.querySelector("[data-testid='design-guide-proof-pending']");
              const stableShell = findByText("body *", "Inputs page stable rerun shell");
              const preparingSummary = findByText("body *", "Preparing current summary");

              const elements = [
                payload("beam_heading", beamHeading),
                payload("inputs_heading", inputsHeading),
                payload("summary_card", summaryCard),
                payload("batch_heading", batchHeading),
                payload("design_guide_heading", designGuideHeading),
                payload("inputs_first_paint_shell", firstPaintShell),
                payload("design_guide_settle_wait_shell", settleWaitShell),
                payload("design_guide_proof_pending_shell", proofPendingShell),
                payload("stable_rerun_shell", stableShell),
                payload("preparing_summary_text", preparingSummary)
              ];

              const visibleElements = elements.filter((item) => item.visible && item.rect);
              const beamBottom = beamHeading ? beamHeading.getBoundingClientRect().bottom : null;
              const inputsTop = inputsHeading ? inputsHeading.getBoundingClientRect().top : null;
              const summaryTop = summaryCard ? summaryCard.getBoundingClientRect().top : null;
              const batchTop = batchHeading ? batchHeading.getBoundingClientRect().top : null;
              const firstRealTop = Math.min(
                ...[inputsTop, summaryTop, batchTop]
                  .filter((value) => typeof value === "number" && Number.isFinite(value))
              );
              const topGapPx = (typeof beamBottom === "number" && Number.isFinite(firstRealTop))
                ? Math.max(0, Math.round(firstRealTop - beamBottom))
                : null;

              const largeVisibleBlocks = Array.from(document.querySelectorAll("body *"))
                .map((el) => {
                  try {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return {
                      tag: String(el.tagName || "").toLowerCase(),
                      cls: String(el.className || "").slice(0, 140),
                      testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                      text: clean(el.innerText || el.textContent).slice(0, 180),
                      rect: rectPayload(rect),
                      display: style.display,
                      visibility: style.visibility,
                      opacity: style.opacity,
                      visible: visible(el)
                    };
                  } catch (_err) {
                    return null;
                  }
                })
                .filter((item) => item && item.visible && item.rect.height >= 140 && item.rect.bottom > 0 && item.rect.top < window.innerHeight * 1.8)
                .sort((a, b) => b.rect.height - a.rect.height)
                .slice(0, 12);

              const bodyText = clean(document.body ? document.body.innerText : "");
              return {
                label,
                url: window.location.href,
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scroll: {
                  x: Math.round(window.scrollX || 0),
                  y: Math.round(window.scrollY || 0),
                  docHeight: Math.round(document.documentElement.scrollHeight || document.body.scrollHeight || 0)
                },
                bodyTextSignals: {
                  preparingCurrentSummary: bodyText.includes("Preparing current summary"),
                  checkingDesignGuidance: bodyText.includes("Checking design guidance"),
                  stableRerunShell: bodyText.includes("Inputs page stable rerun shell"),
                  startYourDesign: bodyText.includes("Start Your Design")
                },
                topGapPx,
                elements,
                largeVisibleBlocks
              };
            }
            """,
            label,
        )
    )


def _diagnose(samples: list[dict[str, Any]]) -> dict[str, Any]:
    gaps = [sample.get("topGapPx") for sample in samples if isinstance(sample.get("topGapPx"), int)]
    max_gap = max(gaps) if gaps else None
    last = samples[-1] if samples else {}
    signals = dict(last.get("bodyTextSignals") or {})
    largest_blocks = list(last.get("largeVisibleBlocks") or [])
    first_paint_visible = any(
        item.get("name") == "inputs_first_paint_shell" and item.get("visible")
        for item in last.get("elements") or []
    )
    proof_shell_visible = any(
        item.get("name") == "design_guide_proof_pending_shell" and item.get("visible")
        for item in last.get("elements") or []
    )
    if max_gap is not None and max_gap >= 280:
        status = "PARTIAL"
    else:
        status = "PASS"
    likely_causes: list[str] = []
    if first_paint_visible or signals.get("preparingCurrentSummary"):
        likely_causes.append("inputs_first_paint_summary_shell_visible")
    if proof_shell_visible or signals.get("checkingDesignGuidance"):
        likely_causes.append("design_guide_pending_shell_visible")
    if signals.get("stableRerunShell"):
        likely_causes.append("stable_rerun_shell_visible")
    if max_gap is not None and max_gap >= 280 and not likely_causes:
        likely_causes.append("large_top_gap_without_known_shell_signal")
    return {
        "status": status,
        "max_top_gap_px": max_gap,
        "final_top_gap_px": last.get("topGapPx"),
        "likely_causes": likely_causes,
        "largest_visible_blocks": largest_blocks[:5],
    }


def _write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"design_guide_top_gap_layout_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_top_gap_layout_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    diagnosis = dict(payload.get("diagnosis") or {})
    lines = [
        "# Design Guide Top-Gap Layout Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Summary",
        f"- URL: `{payload.get('url')}`",
        f"- Samples: `{len(payload.get('samples') or [])}`",
        f"- Max top gap: `{diagnosis.get('max_top_gap_px')}` px",
        f"- Final top gap: `{diagnosis.get('final_top_gap_px')}` px",
        f"- Likely causes: `{', '.join(diagnosis.get('likely_causes') or []) or 'none'}`",
        "",
        "## Largest Visible Blocks",
    ]
    for block in diagnosis.get("largest_visible_blocks") or []:
        rect = block.get("rect") or {}
        lines.append(
            f"- `{block.get('tag')}` h={rect.get('height')} top={rect.get('top')} "
            f"text=`{str(block.get('text') or '')[:100]}`"
        )
    lines.extend(
        [
            "",
            "## Rules",
            "- Audit-only.",
            "- No family runtime, contract, CTA/publication/apply, render wording, or UI behaviour changed.",
            "",
            f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--interval-ms", type=int, default=750)
    parser.add_argument("--wait-timeout-s", type=float, default=30.0)
    args = parser.parse_args()

    _wait_for_live_url(args.url, timeout_s=args.wait_timeout_s)
    samples: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1610, "height": 900})
        page.goto(args.url, wait_until="domcontentloaded", timeout=int(args.wait_timeout_s * 1000))
        for index in range(max(1, args.samples)):
            page.wait_for_timeout(max(0, args.interval_ms))
            samples.append(_snapshot(page, label=f"sample_{index + 1}"))
        browser.close()

    diagnosis = _diagnose(samples)
    payload = {
        "status": diagnosis["status"],
        "timestamp": _timestamp(),
        "url": args.url,
        "sample_count": len(samples),
        "diagnosis": diagnosis,
        "samples": samples,
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "url": payload["url"],
            "sample_count": payload["sample_count"],
            "diagnosis": payload["diagnosis"],
        }
    )
    json_path, md_path = _write_artifacts(payload)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
