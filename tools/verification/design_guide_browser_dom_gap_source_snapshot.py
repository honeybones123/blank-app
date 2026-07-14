"""Browser/live DOM gap source snapshot for Inputs + Design Guide.

Proof-only. Measures exact DOM element paths and rectangles for the summary card
stack, Batch design, and Design Guide surfaces so layout fixes target the real
gap source instead of text-selector artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
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


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_") or "snapshot"


def _attach_screenshot(page, snapshot: dict[str, Any], *, screenshot_dir: Path | None, label: str) -> dict[str, Any]:
    if screenshot_dir is None:
        return snapshot
    try:
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = screenshot_dir / f"{_safe_name(label)}.png"
        page.screenshot(path=str(path), full_page=False)
        snapshot["screenshot_path"] = str(path)
    except Exception as exc:
        snapshot["screenshot_error"] = f"{type(exc).__name__}: {exc}"
    return snapshot


def _install_layout_probe(page) -> None:
    page.add_init_script(
        r"""
        (() => {
          if (window.__dgDomGapProbe) return;
          const probe = { layoutShiftTotal: 0, layoutShiftEntries: [] };
          window.__dgDomGapProbe = probe;
          try {
            const observer = new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                if (entry.hadRecentInput) continue;
                probe.layoutShiftTotal += Number(entry.value || 0);
                probe.layoutShiftEntries.push({
                  value: Number(entry.value || 0),
                  startTime: Number(entry.startTime || 0)
                });
              }
            });
            observer.observe({type: "layout-shift", buffered: true});
          } catch (_) {}
        })();
        """
    )


def _dom_snapshot(page, *, label: str) -> dict[str, Any]:
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
                const style = window.getComputedStyle(el);
                const ancestors = [];
                let node = el;
                for (let i = 0; i < 6 && node; i += 1) {
                  ancestors.push({
                    tag: String(node.tagName || "").toLowerCase(),
                    cls: String(node.className || "").slice(0, 120),
                    testid: node.getAttribute ? node.getAttribute("data-testid") : null,
                    text: clean(node.innerText || node.textContent).slice(0, 80)
                  });
                  node = node.parentElement;
                }
                return {
                  exists: true,
                  visible: visible(el),
                  tag: String(el.tagName || "").toLowerCase(),
                  cls: String(el.className || "").slice(0, 160),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
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
                    paddingTop: style.paddingTop,
                    paddingBottom: style.paddingBottom,
                    minHeight: style.minHeight,
                    height: style.height,
                    display: style.display
                  },
                  ancestors
                };
              };
              const all = Array.from(document.querySelectorAll("body *")).filter(visible);
              const bodyText = clean(document.body ? document.body.innerText : "");
              const visibleBlocks = all.map((el) => {
                const rect = el.getBoundingClientRect();
                return {
                  tag: String(el.tagName || "").toLowerCase(),
                  cls: String(el.className || "").slice(0, 120),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  text: clean(el.innerText || el.textContent).slice(0, 160),
                  rect: {
                    top: Math.round(rect.top),
                    bottom: Math.round(rect.bottom),
                    height: Math.round(rect.height)
                  }
                };
              }).filter((row) => row.text).sort((a, b) => a.rect.top - b.rect.top || b.rect.height - a.rect.height);
              const shortestText = (regex, rejectRegex = null) => {
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
              const closestBlock = (el) => el ? (el.closest('[data-testid="stVerticalBlock"]') || el) : null;
              const summaryStack = document.querySelector(".summary-card-stack");
              const firstPaintShell = document.querySelector(".inputs-first-paint-shell");
              const batchHeading = shortestText(/^Batch design$/i);
              const batchBlock = closestBlock(batchHeading);
              const dgHeading = shortestText(/^Design Guide$/i, /Design Guide Debug|Debug session state/i);
              const dgBlock = closestBlock(dgHeading);
              const dgCard = shortestText(/Design is efficient|Strengthening required|repair is blocked|cleanup required|capacity is low|family contract violation|repair proof incomplete|Run one-click auto design|Apply recommendation/i, /Design Guide Debug|Debug session state/i);
              const proofPending = document.querySelector(".dg-proof-pending-card");
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
                return all.filter((el) => {
                  if (el === upper || el === lower) return false;
                  if (upper.contains(el) || lower.contains(el)) return false;
                  const rect = el.getBoundingClientRect();
                  return rect.top >= up.bottom - 2 && rect.bottom <= lo.top + 2 && rect.height > 2;
                }).sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.height - br.height;
                }).slice(0, 24).map(payload);
              };
              const textContext = (needle) => {
                const index = bodyText.toLowerCase().indexOf(String(needle || "").toLowerCase());
                if (index < 0) return null;
                return bodyText.slice(Math.max(0, index - 120), Math.min(bodyText.length, index + 360));
              };
              return {
                label,
                performance_now_ms: Math.round(performance.now()),
                layout_shift_total: Number((window.__dgDomGapProbe || {}).layoutShiftTotal || 0),
                body_text_length: bodyText.length,
                document_metrics: {
                  scroll_y: Math.round(window.scrollY || 0),
                  viewport_height: Math.round(window.innerHeight || 0),
                  document_height: Math.round((document.scrollingElement || document.documentElement || {}).scrollHeight || 0)
                },
                page_markers: {
                  has_inputs_heading: /(^|\n)\s*Inputs\s*(\n|$)/i.test(bodyText),
                  has_batch_design_text: /Batch design/i.test(bodyText),
                  has_design_guide_text: /Design Guide/i.test(bodyText),
                  has_checking_guidance_text: /Checking design guidance/i.test(bodyText),
                  has_streamlit_error_text: /Traceback|Exception|NameError|UnboundLocalError|RuntimeError/i.test(bodyText),
                  has_rerun_text: /Rerun|Always rerun|File change/i.test(bodyText),
                  has_summary_status_text: /Bending|Shear|Crack control|Deflection/i.test(bodyText),
                  has_publication_card_text: /Design is efficient|Strengthening required|repair is blocked|cleanup required|capacity is low|family contract violation|repair proof incomplete|Run one-click auto design|Apply recommendation/i.test(bodyText)
                },
                text_contexts: {
                  inputs: textContext("Inputs"),
                  batch_design: textContext("Batch design"),
                  design_guide: textContext("Design Guide"),
                  design_mode: textContext("Design mode")
                },
                visible_text_samples: visibleBlocks.slice(0, 30),
                elements: {
                  summary_stack: payload(summaryStack),
                  first_paint_shell: payload(firstPaintShell),
                  batch_heading: payload(batchHeading),
                  batch_block: payload(batchBlock),
                  design_guide_heading: payload(dgHeading),
                  design_guide_block: payload(dgBlock),
                  design_guide_card: payload(dgCard),
                  proof_pending_placeholder: payload(proofPending)
                },
                gaps: {
                  summary_stack_to_batch_heading: gap(summaryStack, batchHeading),
                  summary_stack_to_batch_block: gap(summaryStack, batchBlock),
                  summary_stack_to_design_guide_heading: gap(summaryStack, dgHeading),
                  summary_stack_to_design_guide_block: gap(summaryStack, dgBlock),
                  batch_heading_to_design_guide_heading: gap(batchHeading, dgHeading),
                  batch_block_to_design_guide_heading: gap(batchBlock, dgHeading),
                  batch_block_to_design_guide_block: gap(batchBlock, dgBlock),
                  design_guide_heading_to_card: gap(dgHeading, dgCard)
                },
                interstitial: {
                  summary_stack_to_design_guide_heading: between(summaryStack, dgHeading),
                  summary_stack_to_design_guide_block: between(summaryStack, dgBlock)
                }
              };
            }
            """,
            label,
        )
        or {}
    )


def _capture(
    base_url: str,
    *,
    recipe: str,
    timeout_s: float,
    headed: bool,
    exact_url: str | None = None,
    scroll_scan: bool = True,
    screenshot_dir: Path | None = None,
) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        _install_layout_probe(page)
        url = str(exact_url) if exact_url else _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        snapshots: list[dict[str, Any]] = []
        for delay_ms in (1500, 6000, int(timeout_s * 1000)):
            page.wait_for_timeout(delay_ms if not snapshots else max(0, delay_ms - int(snapshots[-1].get("performance_now_ms") or 0)))
            label = f"t_{delay_ms}ms"
            snapshots.append(
                _attach_screenshot(
                    page,
                    _dom_snapshot(page, label=label),
                    screenshot_dir=screenshot_dir,
                    label=label,
                )
            )
        if scroll_scan:
            for label, scroll_expr in (
                ("scroll_mid", "Math.round((document.scrollingElement || document.documentElement).scrollHeight * 0.45)"),
                ("scroll_bottom", "(document.scrollingElement || document.documentElement).scrollHeight"),
                ("scroll_top_return", "0"),
            ):
                page.evaluate(
                    f"""
                    () => {{
                      const scroller = document.scrollingElement || document.documentElement;
                      scroller.scrollTop = {scroll_expr};
                    }}
                    """
                )
                page.wait_for_timeout(900)
                snapshots.append(
                    _attach_screenshot(
                        page,
                        _dom_snapshot(page, label=label),
                        screenshot_dir=screenshot_dir,
                        label=label,
                    )
                )
        browser.close()
        return {
            "url": url,
            "recipe": recipe,
            "exact_url_mode": bool(exact_url),
            "scroll_scan_enabled": bool(scroll_scan),
            "screenshots_enabled": screenshot_dir is not None,
            "screenshot_dir": str(screenshot_dir) if screenshot_dir is not None else None,
            "snapshots": snapshots,
        }


def _element_exists(snapshot: dict[str, Any], key: str) -> bool:
    return bool(((snapshot.get("elements") or {}).get(key) or {}).get("exists"))


def _best_snapshot(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        return {}
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, snapshot in enumerate(snapshots):
        score = 0
        for key in (
            "summary_stack",
            "batch_heading",
            "batch_block",
            "design_guide_heading",
            "design_guide_block",
            "design_guide_card",
        ):
            if _element_exists(snapshot, key):
                score += 1
        scored.append((score, index, snapshot))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return dict(scored[0][2])


def _classify(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    final = _best_snapshot(snapshots)
    gaps = dict(final.get("gaps") or {})
    elements = dict(final.get("elements") or {})
    markers = dict(final.get("page_markers") or {})
    summary_gap = gaps.get("summary_stack_to_batch_heading")
    summary_to_dg_gap = gaps.get("summary_stack_to_design_guide_heading")
    batch_gap = gaps.get("batch_block_to_design_guide_heading")
    risks: list[str] = []
    measurement_gaps: list[str] = []
    diagnostics: list[str] = []
    if markers.get("has_rerun_text") and not markers.get("has_design_guide_text"):
        diagnostics.append("streamlit_file_change_rerun_gate_prevents_downstream_materialization")
    if (
        markers.get("has_summary_status_text")
        and markers.get("has_batch_design_text")
        and not markers.get("has_design_guide_text")
    ):
        diagnostics.append("design_guide_slot_or_card_not_materialized_after_summary")
    if summary_gap is None:
        if summary_to_dg_gap is None:
            measurement_gaps.append("summary_stack_to_downstream_target_not_measured")
        elif int(summary_to_dg_gap) > 160:
            risks.append("real_summary_stack_to_design_guide_gap")
    elif int(summary_gap) > 120:
        risks.append("real_summary_stack_to_batch_gap")
    if batch_gap is None:
        if summary_to_dg_gap is None:
            measurement_gaps.append("batch_to_design_guide_not_measured")
    elif int(batch_gap) > 140:
        risks.append("real_batch_block_to_design_guide_gap")
    if (elements.get("first_paint_shell") or {}).get("exists"):
        risks.append("first_paint_shell_still_visible_after_settle")
    if (elements.get("proof_pending_placeholder") or {}).get("exists"):
        risks.append("proof_pending_placeholder_still_visible_after_settle")
    return {
        "status": "PASS",
        "audit_result": (
            "REAL_DOM_GAP_SOURCE_DETECTED"
            if risks
            else "DOWNSTREAM_DESIGN_GUIDE_NOT_MATERIALIZED"
            if "design_guide_slot_or_card_not_materialized_after_summary" in diagnostics
            else "STREAMLIT_FILE_CHANGE_RERUN_GATE"
            if "streamlit_file_change_rerun_gate_prevents_downstream_materialization" in diagnostics
            else "INSUFFICIENT_DOM_TARGETS_FOR_GAP_MEASUREMENT"
            if measurement_gaps
            else "NO_REAL_DOM_GAP_SOURCE_DETECTED"
        ),
        "risks": risks,
        "measurement_gaps": measurement_gaps,
        "diagnostics": diagnostics,
        "selected_snapshot_label": final.get("label"),
        "final_gaps": gaps,
        "layout_shift_total": final.get("layout_shift_total"),
        "recommended_next_slice": (
            "Create a narrow CSS/layout patch for the measured real gap source."
            if risks
            else "Trace render eligibility/materialization for the missing Design Guide slot/card before patching layout."
            if "design_guide_slot_or_card_not_materialized_after_summary" in diagnostics
            else "Click Streamlit Rerun or reload after file changes, then recapture before patching layout."
            if "streamlit_file_change_rerun_gate_prevents_downstream_materialization" in diagnostics
            else "Rerun against a URL/session where the downstream panels are present before patching layout."
            if measurement_gaps
            else "Return to controller/render trace wiring or browser probe rebuild audit."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    classification = dict(payload.get("classification") or {})
    final = dict((payload.get("snapshots") or [{}])[-1])
    lines = [
        "# Design Guide Browser DOM Gap Source Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Audit result: `{classification.get('audit_result')}`",
        f"- Recipe: `{payload.get('recipe')}`",
        f"- Selected snapshot: `{classification.get('selected_snapshot_label')}`",
        f"- Risks: `{', '.join(classification.get('risks') or []) or '-'}`",
        f"- Diagnostics: `{', '.join(classification.get('diagnostics') or []) or '-'}`",
        f"- Measurement gaps: `{', '.join(classification.get('measurement_gaps') or []) or '-'}`",
        f"- Layout shift total: `{classification.get('layout_shift_total')}`",
        "",
        "## Page Markers",
        "",
    ]
    for key, value in (final.get("page_markers") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Document Metrics",
            "",
        ]
    )
    for key, value in (final.get("document_metrics") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Text Contexts",
            "",
        ]
    )
    for key, value in (final.get("text_contexts") or {}).items():
        lines.append(f"- {key}: `{str(value).replace('|', '\\|') if value else None}`")
    lines.extend(
        [
            "",
            "## Final Gaps",
            "",
        ]
    )
    for key, value in (classification.get("final_gaps") or {}).items():
        lines.append(f"- {key}: `{value}` px")
    lines.extend(["", "## Final Element Rects", ""])
    for name, element in (final.get("elements") or {}).items():
        rect = dict((element or {}).get("rect") or {})
        lines.append(
            f"- {name}: exists `{(element or {}).get('exists')}`, visible `{(element or {}).get('visible')}`, "
            f"top `{rect.get('top')}`, bottom `{rect.get('bottom')}`, height `{rect.get('height')}`"
        )
    lines.extend(["", "## Visible Text Samples", ""])
    for sample in (final.get("visible_text_samples") or [])[:12]:
        rect = dict((sample or {}).get("rect") or {})
        text = str((sample or {}).get("text") or "").replace("|", "\\|")
        lines.append(
            f"- top `{rect.get('top')}`, height `{rect.get('height')}`, "
            f"testid `{(sample or {}).get('testid')}`: {text}"
        )
    lines.extend(["", "## Recommendation", "", str(classification.get("recommended_next_slice") or ""), ""])
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_browser_dom_gap_source_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_browser_dom_gap_source_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8603)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_DOM_GAP_SOURCE_URL"))
    parser.add_argument("--url", default=os.environ.get("DESIGN_GUIDE_DOM_GAP_SOURCE_EXACT_URL"))
    parser.add_argument("--recipe", default="R2A_M0_V400")
    parser.add_argument("--timeout-s", type=float, default=75.0)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--no-scroll-scan", action="store_true")
    parser.add_argument("--screenshots", action="store_true")
    parser.add_argument("--screenshot-dir", default=None)
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
        screenshot_dir = None
        if args.screenshots:
            screenshot_dir = (
                Path(args.screenshot_dir)
                if args.screenshot_dir
                else ROOT / "artifacts" / "screenshots" / f"design_guide_browser_dom_gap_source_{created_at}"
            )
        capture = _capture(
            base_url,
            recipe=str(args.recipe),
            timeout_s=float(args.timeout_s),
            headed=bool(args.headed),
            exact_url=str(args.url) if args.url else None,
            scroll_scan=not bool(args.no_scroll_scan),
            screenshot_dir=screenshot_dir,
        )
        classification = _classify(list(capture.get("snapshots") or []))
        payload = {
            "created_at": created_at,
            "status": classification["status"],
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
