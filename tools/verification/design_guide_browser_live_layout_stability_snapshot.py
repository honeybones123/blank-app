"""Browser/live layout stability snapshot for Inputs + Design Guide.

This is proof-only. It measures first-paint/transition gaps and scroll movement
around the Inputs heading, page navigation, summary cards, Batch design, and
Design Guide slot/card. It does not change layout, publication, CTA/apply,
family runtime, wording, or engineering behaviour.
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


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _install_layout_probe(page) -> None:
    page.add_init_script(
        r"""
        (() => {
          if (window.__dgLayoutStabilityProbe) return;
          const probe = {
            layoutShiftTotal: 0,
            layoutShiftEntries: [],
            observerErrors: [],
            installedAt: Date.now()
          };
          window.__dgLayoutStabilityProbe = probe;
          try {
            const observer = new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                if (entry.hadRecentInput) continue;
                probe.layoutShiftTotal += Number(entry.value || 0);
                probe.layoutShiftEntries.push({
                  value: Number(entry.value || 0),
                  startTime: Number(entry.startTime || 0),
                  sources: Array.from(entry.sources || []).slice(0, 5).map((source) => ({
                    node: source.node ? String(source.node.tagName || "").toLowerCase() : null,
                    text: source.node ? String(source.node.innerText || source.node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120) : null
                  }))
                });
              }
            });
            observer.observe({type: "layout-shift", buffered: true});
            probe.layoutShiftObserverInstalled = true;
          } catch (err) {
            probe.observerErrors.push(String(err && err.message ? err.message : err));
          }
        })();
        """
    )


def _layout_snapshot(page, *, label: str) -> dict[str, Any]:
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
                  tag: String(el.tagName || "").toLowerCase(),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 140),
                  text: clean(el.innerText || el.textContent).slice(0, 180),
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
              const shortestMatch = (regex, rejectRegex = null) => {
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
              const largestScrollable = Array.from(document.querySelectorAll("body, body *")).filter((el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return (el.scrollHeight || 0) > (el.clientHeight || 0) + 8
                  && (/(auto|scroll|overlay)/i.test(String(style.overflowY || style.overflow || "")) || rect.height >= window.innerHeight * 0.45);
              }).sort((a, b) => ((b.scrollHeight || 0) - (b.clientHeight || 0)) - ((a.scrollHeight || 0) - (a.clientHeight || 0)))[0]
                || document.scrollingElement
                || document.documentElement;
              const elements = {
                beam_heading: payload(shortestMatch(/^Beam design$/i)),
                nav_tabs: payload(shortestMatch(/Inputs\s+Design\s+Bending\s+Shear/i)),
                inputs_heading: payload(shortestMatch(/^Inputs$/i)),
                summary_band: payload(shortestMatch(/Bending\s+.\s+ULS|Shear\s+.\s+ULS|Crack control\s+.\s+SLS|Deflection\s+.\s+SLS/i)),
                batch_design: payload(shortestMatch(/^Batch design$/i)),
                design_guide_heading: payload(shortestMatch(/^Design Guide$/i, /Design Guide Debug|Debug session state/i)),
                design_guide_card: payload(shortestMatch(/Design is efficient|Strengthening required|repair is blocked|cleanup required|Run one-click auto design|Apply recommendation/i, /Design Guide Debug|Debug session state/i))
              };
              const gap = (upper, lower) => {
                if (!upper || !lower || !upper.exists || !lower.exists) return null;
                return Math.round((lower.rect.top || 0) - (upper.rect.bottom || 0));
              };
              const probe = window.__dgLayoutStabilityProbe || {};
              return {
                label,
                timestamp_ms: Date.now(),
                performance_now_ms: Math.round(performance.now()),
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scroll: {
                  top: Math.round(largestScrollable.scrollTop || 0),
                  height: Math.round(largestScrollable.scrollHeight || 0),
                  clientHeight: Math.round(largestScrollable.clientHeight || 0),
                  targetTag: String(largestScrollable.tagName || "").toLowerCase(),
                  targetTestid: largestScrollable.getAttribute ? largestScrollable.getAttribute("data-testid") : null,
                  targetClass: String(largestScrollable.className || "").slice(0, 140)
                },
                elements,
                gaps: {
                  nav_to_inputs: gap(elements.nav_tabs, elements.inputs_heading),
                  inputs_to_summary: gap(elements.inputs_heading, elements.summary_band),
                  summary_to_batch: gap(elements.summary_band, elements.batch_design),
                  batch_to_design_guide: gap(elements.batch_design, elements.design_guide_heading),
                  design_guide_heading_to_card: gap(elements.design_guide_heading, elements.design_guide_card)
                },
                spinners: all.filter((el) => /stSpinner|stSkeleton|progressbar/i.test(`${el.getAttribute ? el.getAttribute("data-testid") || "" : ""} ${el.getAttribute ? el.getAttribute("role") || "" : ""}`)).length,
                body_text_length: clean(document.body ? document.body.innerText : "").length,
                layout_shift_total: Number(probe.layoutShiftTotal || 0),
                layout_shift_entries: Array.from(probe.layoutShiftEntries || []).slice(-20),
                observer_errors: Array.from(probe.observerErrors || [])
              };
            }
            """,
            label,
        )
        or {}
    )


def _scroll_probe(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const target = Array.from(document.querySelectorAll("body, body *")).filter((el) => {
                if (!el || !el.getBoundingClientRect) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return (el.scrollHeight || 0) > (el.clientHeight || 0) + 8
                  && (/(auto|scroll|overlay)/i.test(String(style.overflowY || style.overflow || "")) || rect.height >= window.innerHeight * 0.45);
              }).sort((a, b) => ((b.scrollHeight || 0) - (b.clientHeight || 0)) - ((a.scrollHeight || 0) - (a.clientHeight || 0)))[0]
                || document.scrollingElement
                || document.documentElement;
              const before = {
                top: Math.round(target.scrollTop || 0),
                height: Math.round(target.scrollHeight || 0),
                clientHeight: Math.round(target.clientHeight || 0)
              };
              target.scrollTop = Math.min(before.height, before.top + Math.max(700, Math.round(window.innerHeight * 0.8)));
              const down = {
                top: Math.round(target.scrollTop || 0),
                height: Math.round(target.scrollHeight || 0),
                clientHeight: Math.round(target.clientHeight || 0)
              };
              target.scrollTop = Math.max(0, down.top - Math.max(700, Math.round(window.innerHeight * 0.8)));
              const up = {
                top: Math.round(target.scrollTop || 0),
                height: Math.round(target.scrollHeight || 0),
                clientHeight: Math.round(target.clientHeight || 0)
              };
              return {
                target: {
                  tag: String(target.tagName || "").toLowerCase(),
                  testid: target.getAttribute ? target.getAttribute("data-testid") : null,
                  cls: String(target.className || "").slice(0, 140)
                },
                before,
                down,
                up,
                can_scroll_down: down.top > before.top,
                can_scroll_back_up: up.top < down.top,
                locked_while_scrollable: (before.height > before.clientHeight + 8) && !(down.top > before.top)
              };
            }
            """
        )
        or {}
    )


def _classify(snapshots: list[dict[str, Any]], scroll_probe: dict[str, Any]) -> dict[str, Any]:
    max_nav_gap = max(
        [int((snap.get("gaps") or {}).get("nav_to_inputs") or 0) for snap in snapshots],
        default=0,
    )
    max_summary_batch_gap = max(
        [int((snap.get("gaps") or {}).get("summary_to_batch") or 0) for snap in snapshots],
        default=0,
    )
    max_batch_dg_gap = max(
        [int((snap.get("gaps") or {}).get("batch_to_design_guide") or 0) for snap in snapshots],
        default=0,
    )
    max_layout_shift = max(
        [float(snap.get("layout_shift_total") or 0.0) for snap in snapshots],
        default=0.0,
    )
    missing_real_dg = not any(
        ((snap.get("elements") or {}).get("design_guide_heading") or {}).get("exists")
        for snap in snapshots
    )
    risks: list[str] = []
    if max_nav_gap > 260:
        risks.append("large_nav_to_inputs_gap")
    if max_summary_batch_gap > 160:
        risks.append("large_summary_to_batch_gap")
    if max_batch_dg_gap > 180:
        risks.append("large_batch_to_design_guide_gap")
    if max_layout_shift > 0.15:
        risks.append("high_layout_shift")
    if bool(scroll_probe.get("locked_while_scrollable")):
        risks.append("scroll_locked_while_scrollable")
    if missing_real_dg:
        risks.append("design_guide_heading_not_observed")

    return {
        "status": "PASS",
        "audit_result": "RISKS_FOUND" if risks else "NO_MAJOR_LAYOUT_RISK_DETECTED",
        "risks": risks,
        "max_nav_to_inputs_gap_px": max_nav_gap,
        "max_summary_to_batch_gap_px": max_summary_batch_gap,
        "max_batch_to_design_guide_gap_px": max_batch_dg_gap,
        "max_layout_shift_total": max_layout_shift,
        "scroll_probe": scroll_probe,
        "recommended_next_slice": (
            "Reserve or stabilize the page-content-slot/Inputs shell height before summary render."
            if "large_nav_to_inputs_gap" in risks
            else "Create a focused first-paint placeholder height bypass/readiness snapshot."
            if risks
            else "Return to DesignGuideController trace-only live wiring."
        ),
    }


def _capture(base_url: str, *, recipe: str, timeout_s: float, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        _install_layout_probe(page)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        snapshots: list[dict[str, Any]] = []
        for delay_ms in (0, 350, 800, 1500, 3000, 6000, int(timeout_s * 1000)):
            if delay_ms:
                page.wait_for_timeout(delay_ms if not snapshots else max(0, delay_ms - int(snapshots[-1].get("performance_now_ms") or 0)))
            snapshots.append(_layout_snapshot(page, label=f"t_{delay_ms}ms"))
        scroll = _scroll_probe(page)
        final_snapshot = _layout_snapshot(page, label="after_scroll_probe")
        browser.close()
        return {
            "url": url,
            "recipe": recipe,
            "snapshots": snapshots + [final_snapshot],
            "scroll_probe": scroll,
        }


def _markdown(payload: dict[str, Any]) -> str:
    classification = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Browser/Live Layout Stability Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Audit result: `{classification.get('audit_result')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Risks: `{', '.join(classification.get('risks') or []) or '-'}`",
        "",
        "## Max Measurements",
        "",
        f"- Nav to Inputs gap: `{classification.get('max_nav_to_inputs_gap_px')}` px",
        f"- Summary to Batch gap: `{classification.get('max_summary_to_batch_gap_px')}` px",
        f"- Batch to Design Guide gap: `{classification.get('max_batch_to_design_guide_gap_px')}` px",
        f"- Layout shift total: `{classification.get('max_layout_shift_total')}`",
        f"- Scroll locked while scrollable: `{(classification.get('scroll_probe') or {}).get('locked_while_scrollable')}`",
        "",
        "## Recommendation",
        "",
        str(classification.get("recommended_next_slice") or ""),
        "",
        "## Snapshot Labels",
        "",
    ]
    for snap in payload.get("snapshots") or []:
        gaps = dict(snap.get("gaps") or {})
        lines.append(
            f"- `{snap.get('label')}` nav/input `{gaps.get('nav_to_inputs')}`, "
            f"summary/batch `{gaps.get('summary_to_batch')}`, "
            f"batch/DG `{gaps.get('batch_to_design_guide')}`, "
            f"CLS `{snap.get('layout_shift_total')}`"
        )
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_browser_live_layout_stability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_browser_live_layout_stability_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8602)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_LAYOUT_STABILITY_URL"))
    parser.add_argument("--recipe", default="PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS")
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
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
            timeout_s=float(args.timeout_s),
            headed=bool(args.headed),
        )
        classification = _classify(
            list(capture.get("snapshots") or []),
            dict(capture.get("scroll_probe") or {}),
        )
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
        print(json.dumps({"status": payload["status"], "audit_result": classification.get("audit_result")}, indent=2))
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
