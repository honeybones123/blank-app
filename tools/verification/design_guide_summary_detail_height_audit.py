"""Proof-only audit for summary/check detail height before Batch design.

This verifier measures the Inputs summary card stack and the area immediately
before the Batch design panel. It does not change UI layout, rendering,
publication, CTA, apply routing, session state, or engineering logic.
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


def _measure_summary_detail_height(page, label: str) -> dict[str, Any]:
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
                  text: clean(el.innerText || el.textContent).slice(0, 220),
                  tag: String(el.tagName || "").toLowerCase(),
                  cls: String(el.className || "").slice(0, 160),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null
                };
              };
              const findText = (pattern, selectors) => {
                const regex = new RegExp(pattern, "i");
                for (const selector of selectors) {
                  try {
                    const match = Array.from(document.querySelectorAll(selector))
                      .filter(visible)
                      .find((el) => regex.test(clean(el.innerText || el.textContent)));
                    if (match) return match;
                  } catch (_err) {}
                }
                return null;
              };
              const stack = Array.from(document.querySelectorAll(".summary-card-stack")).filter(visible)[0] || null;
              const batchHeading = findText("Batch design", [
                "h1", "h2", "h3", "[role='heading']", "[data-testid='stMarkdownContainer']"
              ]);
              const cards = stack ? Array.from(stack.querySelectorAll(".summary-check-card")).filter(visible) : [];
              const cardRows = cards.map((card, index) => {
                const details = card.querySelector("details");
                const summary = card.querySelector("summary");
                const detailShell = card.querySelector(".summary-detail-shell");
                const detailTable = card.querySelector(".summary-detail-table");
                const title = clean((card.querySelector(".summary-check-title") || {}).innerText || "");
                const rect = rectPayload(card) || {};
                const summaryRect = rectPayload(summary) || {};
                const detailRect = rectPayload(detailShell) || {};
                const tableRect = rectPayload(detailTable) || {};
                return {
                  index,
                  title,
                  status_class: String(card.className || ""),
                  details_open: !!(details && details.open),
                  card_height_px: rect.height || 0,
                  summary_height_px: summaryRect.height || 0,
                  detail_shell_height_px: detailRect.height || 0,
                  detail_table_height_px: tableRect.height || 0,
                  detail_row_count: detailTable ? detailTable.querySelectorAll("tbody tr, tr.summary-detail-row").length : 0,
                  top: rect.top,
                  bottom: rect.bottom,
                  text_sample: clean(card.innerText || card.textContent).slice(0, 240)
                };
              });
              const stackRect = rectPayload(stack);
              const batchRect = rectPayload(batchHeading);
              const betweenTop = stackRect && batchRect ? stackRect.bottom : 0;
              const betweenBottom = stackRect && batchRect ? batchRect.top : 0;
              const betweenElements = [];
              if (stackRect && batchRect) {
                for (const el of Array.from(document.querySelectorAll("div, section, [data-testid], hr, [role='separator']"))) {
                  if (!visible(el)) continue;
                  const rect = el.getBoundingClientRect();
                  const text = clean(el.innerText || el.textContent);
                  if (rect.top >= betweenTop - 2 && rect.bottom <= betweenBottom + 2 && rect.height > 4) {
                    betweenElements.push({
                      top: Math.round(rect.top),
                      bottom: Math.round(rect.bottom),
                      height: Math.round(rect.height),
                      tag: String(el.tagName || "").toLowerCase(),
                      cls: String(el.className || "").slice(0, 120),
                      testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                      text: text.slice(0, 140)
                    });
                  }
                }
              }
              return {
                label,
                captured_at_ms: Date.now(),
                performance_now_ms: Math.round(performance.now()),
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scroll_y: Math.round(window.scrollY || 0),
                stack: stackRect,
                batch_design_heading: batchRect,
                card_rows: cardRows,
                open_card_count: cardRows.filter((row) => row.details_open).length,
                total_card_height_px: cardRows.reduce((total, row) => total + Number(row.card_height_px || 0), 0),
                total_open_detail_height_px: cardRows.reduce((total, row) => total + Number(row.detail_shell_height_px || 0), 0),
                stack_to_batch_gap_px: stackRect && batchRect ? Math.round(batchRect.top - stackRect.bottom) : null,
                between_stack_and_batch_elements: betweenElements.slice(0, 40),
                body_text_length: clean(document.body ? document.body.innerText : "").length
              };
            }
            """,
            label,
        )
        or {}
    )


def _classify(snapshot: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row or {}) for row in snapshot.get("card_rows") or []]
    open_rows = [row for row in rows if row.get("details_open")]
    tall_open_rows = [row for row in open_rows if int(row.get("detail_shell_height_px") or 0) >= 180]
    stack_to_batch_gap = snapshot.get("stack_to_batch_gap_px")
    between = [dict(row or {}) for row in snapshot.get("between_stack_and_batch_elements") or []]
    blank_between = [row for row in between if not str(row.get("text") or "").strip()]
    safe_candidates: list[dict[str, Any]] = []
    if tall_open_rows:
        safe_candidates.append(
            {
                "candidate": "default-collapse or lazy-render open summary details",
                "reason": "open summary detail rows dominate the pre-Batch height",
                "affected_rows": [row.get("title") for row in tall_open_rows],
                "requires_live_non_test_guard": True,
            }
        )
    if stack_to_batch_gap is not None and int(stack_to_batch_gap or 0) > 48 and blank_between:
        safe_candidates.append(
            {
                "candidate": "tighten blank containers between summary stack and Batch design",
                "reason": "blank elements remain after the summary card stack before the Batch design heading",
                "blank_element_count": len(blank_between),
                "requires_live_visual_guard": True,
            }
        )
    blockers: list[str] = []
    if not rows:
        blockers.append("summary_cards_not_found")
    if snapshot.get("stack") is None:
        blockers.append("summary_stack_not_found")
    if snapshot.get("batch_design_heading") is None:
        blockers.append("batch_design_heading_not_found")
    return {
        "summary_card_count": len(rows),
        "open_card_count": len(open_rows),
        "tall_open_detail_count": len(tall_open_rows),
        "total_card_height_px": snapshot.get("total_card_height_px"),
        "total_open_detail_height_px": snapshot.get("total_open_detail_height_px"),
        "stack_to_batch_gap_px": stack_to_batch_gap,
        "blank_between_stack_and_batch_count": len(blank_between),
        "safe_fix_candidates": safe_candidates,
        "blockers": blockers,
        "recommended_next_step": (
            "Implement a guarded detail-height reduction only after confirming the same row is expanded in the live non-test state."
            if tall_open_rows
            else (
                "Tighten blank style-only containers between the summary stack and Batch design."
                if safe_candidates
                else "No summary/detail height reduction is currently justified by this audit."
            )
        ),
    }


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def _write_report(payload: dict[str, Any], path: Path) -> None:
    classification = dict(payload.get("classification") or {})
    snapshot = dict(payload.get("snapshot") or {})
    lines = [
        "# Design Guide Summary Detail Height Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Recipe: `{payload['recipe']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        f"- Summary cards found: `{classification.get('summary_card_count')}`",
        f"- Open cards: `{classification.get('open_card_count')}`",
        f"- Tall open detail rows: `{classification.get('tall_open_detail_count')}`",
        f"- Total card height: `{classification.get('total_card_height_px')}` px",
        f"- Total open detail height: `{classification.get('total_open_detail_height_px')}` px",
        f"- Stack-to-Batch gap: `{classification.get('stack_to_batch_gap_px')}` px",
        f"- Blank elements between stack and Batch: `{classification.get('blank_between_stack_and_batch_count')}`",
        "",
        "## Card Rows",
        "",
        "| Card | Open | Card height | Detail height | Detail rows | Status class |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in snapshot.get("card_rows") or []:
        row = dict(row or {})
        lines.append(
            f"| {_escape_md(str(row.get('title') or ''))} | `{row.get('details_open')}` | `{row.get('card_height_px')}` | `{row.get('detail_shell_height_px')}` | `{row.get('detail_row_count')}` | `{_escape_md(str(row.get('status_class') or ''))}` |"
        )
    lines.extend(["", "## Safe Fix Candidates", ""])
    for candidate in classification.get("safe_fix_candidates") or []:
        lines.append(f"- `{candidate.get('candidate')}`: {candidate.get('reason')}")
    if not classification.get("safe_fix_candidates"):
        lines.append("- None.")
    lines.extend(["", "## Supporting Locks", ""])
    for name, lock in (payload.get("supporting_artifacts") or {}).items():
        lines.append(f"- `{name}`: passed=`{lock.get('passed')}`, path=`{lock.get('path')}`")
    lines.extend(["", "## Recommendation", "", str(classification.get("recommended_next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    port = int(os.environ.get("DESIGN_GUIDE_SUMMARY_HEIGHT_PORT") or "8541")
    recipe = os.environ.get("DESIGN_GUIDE_SUMMARY_HEIGHT_RECIPE") or DEFAULT_RECIPE
    base_url = f"http://127.0.0.1:{port}"
    process: subprocess.Popen | None = None
    snapshot: dict[str, Any] = {}
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
            page = context.new_page()
            page.set_default_timeout(30_000)
            page.goto(
                _query(base_url, {"page": "inputs", "browser_recipe": recipe}),
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            _wait_for_design_guide_state(page)
            page.wait_for_timeout(500)
            snapshot = _measure_summary_detail_height(page, "after_design_guide_ready")
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
        "first_paint_layout_gap_profile": _latest("design_guide_first_paint_layout_gap_profile"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "design_guide_independence_lock": _latest("design_guide_independence_lock"),
    }
    classification = _classify(snapshot)
    failures: list[str] = []
    for blocker in classification.get("blockers") or []:
        failures.append(str(blocker))
    for name, artifact in supporting_artifacts.items():
        if artifact.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    if errors:
        failures.extend(f"browser_error::{error}" for error in errors)

    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_summary_detail_height_audit.v1",
        "status": status,
        "created_at": stamp,
        "recipe": recipe,
        "base_url": base_url,
        "product_behaviour_changed": False,
        "layout_changed": False,
        "snapshot": snapshot,
        "classification": classification,
        "supporting_artifacts": supporting_artifacts,
        "errors": errors,
        "failures": failures,
    }
    payload["audit_hash"] = _stable_hash(
        {
            "recipe": recipe,
            "snapshot": snapshot,
            "classification": classification,
            "errors": errors,
        }
    )
    artifact_path = ARTIFACT_DIR / f"design_guide_summary_detail_height_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_summary_detail_height_audit_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(json.dumps({"status": status, "artifact": str(artifact_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
