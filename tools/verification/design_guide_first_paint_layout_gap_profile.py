"""Browser/live first-paint layout gap profile for the Inputs page.

Measurement-only. This focuses on the visible gaps around Inputs heading,
navigation, result/check bands, Batch design, and Design Guide. It does not
change layout, rendering, publication, CTA, apply routing, or engineering logic.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_RECIPE = "A_bending_under_only"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _query(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({key: value for key, value in params.items() if value is not None})}"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "passed": payload.get("status") == "PASS",
        "snapshot_hash": payload.get("snapshot_hash") or payload.get("profile_hash"),
    }


def _install_layout_probe(context) -> None:
    context.add_init_script(
        r"""
        (() => {
          window.__dgGapProbe = window.__dgGapProbe || {
            installedAt: Date.now(),
            layoutShiftTotal: 0,
            layoutShiftEntries: []
          };
          const probe = window.__dgGapProbe;
          try {
            const po = new PerformanceObserver((list) => {
              for (const entry of list.getEntries()) {
                if (entry.hadRecentInput) continue;
                probe.layoutShiftTotal += Number(entry.value || 0);
                probe.layoutShiftEntries.push({
                  value: Number(entry.value || 0),
                  startTime: Number(entry.startTime || 0)
                });
              }
              if (probe.layoutShiftEntries.length > 200) {
                probe.layoutShiftEntries = probe.layoutShiftEntries.slice(-200);
              }
            });
            po.observe({type: "layout-shift", buffered: true});
          } catch (_err) {}
        })();
        """
    )


def _measure_layout(page, label: str) -> dict[str, Any]:
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
                  && rect.height > 2
                  && rect.right > 0
                  && rect.left < window.innerWidth
                  && rect.bottom > 0
                  && rect.top < Math.max(window.innerHeight * 4, 1600);
              };
              const rectPayload = (el) => {
                if (!el || !el.getBoundingClientRect || !visible(el)) return null;
                const rect = el.getBoundingClientRect();
                return {
                  x: Math.round(rect.x),
                  y: Math.round(rect.y),
                  top: Math.round(rect.top),
                  bottom: Math.round(rect.bottom),
                  width: Math.round(rect.width),
                  height: Math.round(rect.height),
                  text: clean(el.innerText || el.textContent).slice(0, 180),
                  tag: String(el.tagName || "").toLowerCase(),
                  cls: String(el.className || "").slice(0, 140),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null
                };
              };
              const compactAncestor = (el, {minWidthRatio = 0.55, maxHeight = 180} = {}) => {
                if (!el) return null;
                let current = el;
                let best = el;
                while (current && current !== document.body && current.getBoundingClientRect) {
                  const rect = current.getBoundingClientRect();
                  if (visible(current) && rect.width >= window.innerWidth * minWidthRatio && rect.height <= maxHeight) {
                    best = current;
                  }
                  if (rect.height > maxHeight * 2.5 && rect.width >= window.innerWidth * minWidthRatio) {
                    break;
                  }
                  current = current.parentElement;
                }
                return best;
              };
              const allVisible = (selector) => {
                try { return Array.from(document.querySelectorAll(selector)).filter(visible); }
                catch (_err) { return []; }
              };
              const findText = (pattern, selectors) => {
                const regex = new RegExp(pattern, "i");
                const candidates = [];
                for (const selector of selectors) candidates.push(...allVisible(selector));
                return candidates.find((el) => regex.test(clean(el.innerText || el.textContent))) || null;
              };
              const findHeading = (text) => findText(`^${text}$|${text}`, [
                "h1", "h2", "h3", "[role='heading']", "[data-testid='stMarkdownContainer']"
              ]);
              const union = (items) => {
                const rects = items.map(rectPayload).filter(Boolean);
                if (!rects.length) return null;
                const left = Math.min(...rects.map((item) => item.x));
                const top = Math.min(...rects.map((item) => item.top));
                const right = Math.max(...rects.map((item) => item.x + item.width));
                const bottom = Math.max(...rects.map((item) => item.bottom));
                return {
                  x: Math.round(left),
                  y: Math.round(top),
                  top: Math.round(top),
                  bottom: Math.round(bottom),
                  width: Math.round(right - left),
                  height: Math.round(bottom - top),
                  item_count: rects.length,
                  text: rects.map((item) => item.text).join(" | ").slice(0, 240)
                };
              };
              const inputsHeading = findHeading("Inputs");
              const navTabs = union(allVisible("[role='tab']").filter((el) => {
                const text = clean(el.innerText || el.textContent || el.getAttribute("aria-label"));
                return /^(Inputs|Bending|Shear|Deflection|Crack|Creep|Shrinkage|Batch)/i.test(text);
              }).slice(0, 24));
              const resultBand = union(allVisible(".summary-check-card, .summary-card-stack, [data-testid='stExpander']").filter((el) => {
                const text = clean(el.innerText || el.textContent);
                const rect = el.getBoundingClientRect();
                return /(Bending|Shear|Crack|Deflection|SLS|ULS|PASS|FAIL|NOT RUN)/i.test(text)
                  && rect.top < 1200
                  && rect.height < 260;
              }).slice(0, 12));
              const deflectionText = Array.from(document.querySelectorAll(".summary-check-card"))
                .filter(visible)
                .find((el) => /Deflection/i.test(clean(el.innerText || el.textContent)))
                || findText("Deflection|SLS", [
                  "[data-testid='stExpander']",
                  "section",
                  "div"
                ]);
              const deflectionBand = compactAncestor(deflectionText, {minWidthRatio: 0.55, maxHeight: 150});
              const batchHeading = findHeading("Batch design");
              const designGuideHeading = findHeading("Design Guide");
              const designGuideCard = findText("Design is|Design Guide blocker|Why no further cleanup|Why repair is blocked|Preview after proposed change", [
                "[data-testid='design-guide-card']",
                ".fast-guidance-item",
                "[data-testid='stMarkdownContainer']",
                "section",
                "div"
              ]);
              const regions = {
                inputs_heading: rectPayload(inputsHeading),
                nav_tabs: navTabs,
                result_band: resultBand,
                deflection_band: rectPayload(deflectionBand),
                batch_design_heading: rectPayload(batchHeading),
                design_guide_heading: rectPayload(designGuideHeading),
                design_guide_card: rectPayload(designGuideCard)
              };
              const gap = (fromName, toName) => {
                const from = regions[fromName];
                const to = regions[toName];
                if (!from || !to) return {measured: false, from: fromName, to: toName, reason: "missing_region"};
                const value = Math.round(to.top - from.bottom);
                const midpointTop = Math.min(from.bottom, to.top);
                const midpointBottom = Math.max(from.bottom, to.top);
                const separators = allVisible("hr, [role='separator']").filter((el) => {
                  const rect = el.getBoundingClientRect();
                  return rect.top >= midpointTop - 4 && rect.bottom <= midpointBottom + 4;
                });
                const contentElements = allVisible("[data-testid='stMarkdownContainer'], [data-testid='stExpander'], button, input, label, select, textarea").filter((el) => {
                  const rect = el.getBoundingClientRect();
                  const text = clean(el.innerText || el.textContent || el.getAttribute("aria-label"));
                  return rect.top >= midpointTop - 2
                    && rect.bottom <= midpointBottom + 2
                    && rect.height > 8
                    && text;
                }).slice(0, 20);
                const contentHeightTotal = contentElements.reduce((total, el) => {
                  const rect = el.getBoundingClientRect();
                  return total + Math.max(0, Math.round(rect.height || 0));
                }, 0);
                const blankElements = allVisible("div, section, [data-testid]").filter((el) => {
                  const rect = el.getBoundingClientRect();
                  const text = clean(el.innerText || el.textContent);
                  return rect.top >= midpointTop - 2
                    && rect.bottom <= midpointBottom + 2
                    && rect.height > 8
                    && !text;
                }).slice(0, 12);
                return {
                  measured: true,
                  from: fromName,
                  to: toName,
                  px: value,
                  from_bottom: from.bottom,
                  to_top: to.top,
                  separator_count: separators.length,
                  blank_element_count: blankElements.length,
                  content_element_count: contentElements.length,
                  content_height_total_px: contentHeightTotal,
                  sample_content_elements: contentElements.map(rectPayload).filter(Boolean).slice(0, 5),
                  sample_blank_elements: blankElements.map(rectPayload).filter(Boolean).slice(0, 5)
                };
              };
              const gaps = {
                inputs_heading_to_nav_tabs: gap("inputs_heading", "nav_tabs"),
                nav_tabs_to_result_band: gap("nav_tabs", "result_band"),
                result_band_to_batch_design: gap("result_band", "batch_design_heading"),
                deflection_band_to_batch_design: gap("deflection_band", "batch_design_heading"),
                batch_design_to_design_guide: gap("batch_design_heading", "design_guide_heading"),
                design_guide_heading_to_card: gap("design_guide_heading", "design_guide_card")
              };
              const probe = window.__dgGapProbe || {};
              return {
                label,
                captured_at_ms: Date.now(),
                performance_now_ms: Math.round(performance.now()),
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scroll_y: Math.round(window.scrollY || 0),
                regions,
                gaps,
                max_positive_gap_px: Math.max(
                  ...Object.values(gaps).filter((item) => item.measured).map((item) => item.px),
                  0
                ),
                layout_shift_total: Number(probe.layoutShiftTotal || 0),
                layout_shift_entries_tail: Array.from(probe.layoutShiftEntries || []).slice(-20),
                body_text_length: clean(document.body ? document.body.innerText : "").length
              };
            }
            """,
            label,
        )
        or {}
    )


def _wait_for_design_guide_state(page, timeout_s: float = 45.0) -> dict[str, Any]:
    started = time.perf_counter()
    last_state: dict[str, Any] = {}
    while time.perf_counter() - started <= timeout_s:
        try:
            state = _load_browser_state(page, timeout_s=1.0)
            last_state = dict(state or {})
            bundle = dict((dict(last_state.get("design_guide_probe") or {})).get("debug_bundle") or {})
            if bundle.get("final_publication_verifier_payload") or bundle.get("actual_card_render_probe"):
                return last_state
        except Exception:
            pass
        time.sleep(0.35)
    return last_state


def _classify_gaps(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    final = snapshots[-1] if snapshots else {}
    gaps = dict(final.get("gaps") or {})
    measured_rows = [
        {"id": key, **dict(value)}
        for key, value in gaps.items()
        if isinstance(value, dict) and value.get("measured")
    ]
    measured_rows.sort(key=lambda item: int(item.get("px") or 0), reverse=True)
    largest = measured_rows[0] if measured_rows else {}
    excessive = [row for row in measured_rows if int(row.get("px") or 0) > 48]
    blank_excessive = [
        row
        for row in excessive
        if int(row.get("content_element_count") or 0) <= 2
        and int(row.get("content_height_total_px") or 0) < 120
    ]
    content_driven = [
        row
        for row in excessive
        if int(row.get("content_element_count") or 0) > 2
        or int(row.get("content_height_total_px") or 0) >= 120
    ]
    separator_driven = [
        row
        for row in measured_rows
        if int(row.get("separator_count") or 0) >= 1 and int(row.get("px") or 0) > 32
    ]
    return {
        "largest_gap": largest,
        "measured_gap_count": len(measured_rows),
        "excessive_gap_count": len(excessive),
        "blank_excessive_gap_count": len(blank_excessive),
        "content_driven_gap_count": len(content_driven),
        "separator_driven_gap_count": len(separator_driven),
        "excessive_gaps": excessive,
        "blank_excessive_gaps": blank_excessive,
        "content_driven_gaps": content_driven,
        "separator_driven_gaps": separator_driven,
        "recommended_first_fix": (
            "Remove or collapse the extra separator/spacer above Batch design and keep Batch design in a stable white panel."
            if any(row.get("id") in {"result_band_to_batch_design", "deflection_band_to_batch_design"} for row in blank_excessive)
            else (
                "Collapse or lazy-render expanded result/detail content before Batch design; the measured vertical distance contains content, not only blank spacer."
                if any(row.get("id") in {"result_band_to_batch_design", "deflection_band_to_batch_design"} for row in content_driven)
                else (
                    "Reserve a stable Design Guide shell/card height before publication completes."
                    if any(row.get("id") == "design_guide_heading_to_card" for row in excessive)
                    else "No large fixed vertical gap was observed; profile rerun-trigger/layout shift next."
                )
            )
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    classification = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide First-Paint/Layout Gap Profile",
        "",
        f"Status: `{payload['status']}`",
        f"Recipe: `{payload['recipe']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Gap Summary",
        "",
        f"- Largest gap: `{(classification.get('largest_gap') or {}).get('id')}` = `{(classification.get('largest_gap') or {}).get('px')}` px",
        f"- Excessive gaps > 48px: `{classification.get('excessive_gap_count')}`",
        f"- Blank excessive gaps: `{classification.get('blank_excessive_gap_count')}`",
        f"- Content-driven gaps: `{classification.get('content_driven_gap_count')}`",
        f"- Separator-driven gaps: `{classification.get('separator_driven_gap_count')}`",
        "",
        "## Final Snapshot Gaps",
        "",
        "| Gap | px | Separators | Blank elements | Content elements | Content height | Measured |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    final = (payload.get("snapshots") or [{}])[-1]
    for key, row in (final.get("gaps") or {}).items():
        row = dict(row or {})
        lines.append(
            f"| `{key}` | `{row.get('px')}` | `{row.get('separator_count')}` | `{row.get('blank_element_count')}` | `{row.get('content_element_count')}` | `{row.get('content_height_total_px')}` | `{row.get('measured')}` |"
        )
    lines.extend(["", "## Region Rects", "", "| Region | top | bottom | height | text |", "| --- | ---: | ---: | ---: | --- |"])
    for key, row in (final.get("regions") or {}).items():
        row = dict(row or {})
        lines.append(
            f"| `{key}` | `{row.get('top')}` | `{row.get('bottom')}` | `{row.get('height')}` | {_escape_md(str(row.get('text') or '')[:100])} |"
        )
    lines.extend(["", "## Supporting Locks", ""])
    for name, lock in (payload.get("supporting_artifacts") or {}).items():
        lines.append(f"- `{name}`: passed=`{lock.get('passed')}`, path=`{lock.get('path')}`")
    lines.extend(["", "## Recommendation", "", str(classification.get("recommended_first_fix") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    port = int(os.environ.get("DESIGN_GUIDE_GAP_PROFILE_PORT") or "8534")
    recipe = os.environ.get("DESIGN_GUIDE_GAP_PROFILE_RECIPE") or DEFAULT_RECIPE
    base_url = f"http://127.0.0.1:{port}"
    process: subprocess.Popen | None = None
    snapshots: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        env_before = dict(os.environ)
        os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
        os.environ["CODEX_RENDER_TIMING_TRACE"] = "1"
        os.environ["AUTO_DESIGN_SPEED_PROFILE"] = "1"
        try:
            process = _start_streamlit(port)
        finally:
            os.environ.clear()
            os.environ.update(env_before)
        _wait_for_http(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            _install_layout_probe(context)
            page = context.new_page()
            page.set_default_timeout(30_000)
            page.goto(
                _query(base_url, {"page": "inputs", "browser_recipe": recipe}),
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            snapshots.append(_measure_layout(page, "after_domcontentloaded"))
            page.wait_for_timeout(650)
            snapshots.append(_measure_layout(page, "after_first_paint_wait"))
            _wait_for_design_guide_state(page)
            page.wait_for_timeout(500)
            snapshots.append(_measure_layout(page, "after_design_guide_ready"))
            context.close()
            browser.close()
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    supporting_artifacts = {
        "no_input_candidate_search_reuse_live_impact": _latest(
            "design_guide_no_input_candidate_search_reuse_live_impact"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
        "design_guide_independence_lock": _latest("design_guide_independence_lock"),
    }
    classification = _classify_gaps(snapshots)
    failures: list[str] = []
    if not snapshots:
        failures.append("no_browser_layout_snapshots")
    for name, artifact in supporting_artifacts.items():
        if artifact.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    if errors:
        failures.extend(f"browser_error::{error}" for error in errors)

    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_first_paint_layout_gap_profile.v1",
        "status": status,
        "created_at": stamp,
        "recipe": recipe,
        "base_url": base_url,
        "product_behaviour_changed": False,
        "new_bypass_implemented": False,
        "code_deleted": False,
        "snapshots": snapshots,
        "classification": classification,
        "supporting_artifacts": supporting_artifacts,
        "errors": errors,
        "failures": failures,
    }
    payload["profile_hash"] = _stable_hash(
        {
            "recipe": recipe,
            "snapshots": snapshots,
            "classification": classification,
            "errors": errors,
        }
    )
    artifact_path = ARTIFACT_DIR / f"design_guide_first_paint_layout_gap_profile_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_first_paint_layout_gap_profile_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_first_paint_layout_gap_profile {status}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    print(f"largest_gap={json.dumps(classification.get('largest_gap'), sort_keys=True, default=str)}")
    print(f"recommendation={classification.get('recommended_first_fix')}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
