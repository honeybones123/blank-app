"""Browser visual/layout release lock for Inputs and Design Guide.

This verifier checks live rendered layout, not family maths. It exists because
several regressions were visual/shared-path failures: duplicate Design Guide
cards, old yellow/blue notes, moved diagram/model slot, raw summary-card text,
and Streamlit runtime screens.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.browser_red_screen_sentinel import browser_red_screen_findings  # noqa: E402
from tools.verification.design_guide_family_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _wait_for_final_design_guide_card,
)
from tools.verification.helpers.browser_helpers import _load_browser_state  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_BASE_URL = (
    "http://127.0.0.1:8504/"
    "?page=inputs&browser_recipe=R3A_M300_V400&browser_test_mode=1&batch_design_open=0"
)

FORBIDDEN_VISIBLE_TEXT = (
    "Recommendation is advisory, not directly executable",
    "One-click found a candidate, but it was blocked",
    "stale_primary_design_guide_payload",
    "Design Guide family contract violation",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _url_with_browser_test_contract(url: str) -> str:
    parsed = urlparse(str(url or ""))
    query = parse_qs(parsed.query, keep_blank_values=True)
    query.setdefault("page", ["inputs"])
    query["browser_test_mode"] = ["1"]
    query.setdefault("batch_design_open", ["0"])
    return urlunparse(
        parsed._replace(query=urlencode({key: values[-1] for key, values in query.items()}))
    )


def _query_value(url: str, key: str) -> str:
    parsed = urlparse(str(url or ""))
    values = parse_qs(parsed.query, keep_blank_values=True).get(key) or []
    return str(values[-1] if values else "").strip()


def _browser_recipe_from_state(state: dict[str, Any]) -> str:
    shared = dict(state.get("browser_shared_probe") or {})
    summary = dict(state.get("summary_state_probe") or {})
    return str(
        state.get("browser_recipe")
        or shared.get("browser_recipe")
        or summary.get("browser_recipe")
        or ""
    ).strip()


def _browser_recipe_error_from_state(state: dict[str, Any]) -> str:
    shared = dict(state.get("browser_shared_probe") or {})
    summary = dict(state.get("summary_state_probe") or {})
    return str(
        state.get("browser_recipe_error")
        or shared.get("browser_recipe_error")
        or summary.get("browser_recipe_error")
        or ""
    ).strip()


def _browser_snapshot(page) -> dict[str, Any]:
    return dict(
        page.evaluate(
            r"""
            () => {
              const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
              const visible = (el) => {
                if (!el || !el.getBoundingClientRect) return false;
                if (el.hasAttribute && (el.hasAttribute("hidden") || el.closest("[inert]"))) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                  && style.visibility !== "hidden"
                  && Number(style.opacity || "1") > 0.02
                  && rect.width > 2
                  && rect.height > 2;
              };
              const rectPayload = (el) => {
                if (!el) return {exists: false, visible: false, text: "", rect: {}};
                const rect = el.getBoundingClientRect();
                return {
                  exists: true,
                  visible: visible(el),
                  tag: String(el.tagName || "").toLowerCase(),
                  testid: el.getAttribute ? el.getAttribute("data-testid") : null,
                  cls: String(el.className || "").slice(0, 180),
                  text: clean(el.innerText || el.textContent).slice(0, 260),
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
              const byText = (regex, rejectRegex = null) => {
                const rows = all.filter((el) => {
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
                return rows[0] || null;
              };
              const allByText = (regex, rejectRegex = null) => all.filter((el) => {
                const text = clean(el.innerText || el.textContent);
                if (!regex.test(text)) return false;
                if (rejectRegex && rejectRegex.test(text)) return false;
                return true;
              }).map(rectPayload);
              const bodyText = clean(document.body ? document.body.innerText : "");
              const buttons = Array.from(document.querySelectorAll("button")).filter(visible).map(rectPayload);
              const designGuideHeadings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
                .filter(visible)
                .filter((el) => /^Design Guide$/i.test(clean(el.innerText || el.textContent)))
                .map(rectPayload);
              const modelHeading = rectPayload(byText(/^Model$/i));
              const designActionsHeading = rectPayload(byText(/^Design Actions$/i));
              const summaryBending = rectPayload(byText(/Bending\s+[\u2014-]\s+ULS/i));
              const summaryShear = rectPayload(byText(/Shear\s+[\u2014-]\s+ULS/i));
              const batchHeading = rectPayload(byText(/^Batch design$/i));
              const designGuideCard = rectPayload(byText(/Design is efficient|capacity is low|cleanup|repair|blocked|target band|family contract violation/i, /Debug/i));
              const guideCards = Array.from(document.querySelectorAll("[data-testid='design-guide-card'], .fast-guidance-item"))
                .filter(visible)
                .map(rectPayload);
              const summaryLikeRawText = /Bending\s+[\u2014-]\s+ULS\s+Applied\s+.+\s+Capacity\s+.+\s+Utilisation\s+.+\s+(PASS|FAIL|CAPACITY|NOT RUN)/i.test(bodyText)
                && !summaryBending.visible;
              return {
                bodyText,
                bodyTextLength: bodyText.length,
                viewport: {width: window.innerWidth, height: window.innerHeight},
                scrollY: Math.round(window.scrollY || 0),
                elements: {
                  designActionsHeading,
                  modelHeading,
                  summaryBending,
                  summaryShear,
                  batchHeading,
                  designGuideCard
                },
                counts: {
                  designGuideHeadingCount: designGuideHeadings.length,
                  designGuideCardCount: guideCards.length || (designGuideCard.visible ? 1 : 0),
                  buttonCount: buttons.length,
                  actionButtonCount: buttons.filter((item) => /Run one-click|Apply:/i.test(item.text)).length
                },
                designGuideHeadings,
                guideCards,
                buttons,
                summaryLikeRawText,
                layout: {
                  modelTop: modelHeading.rect ? modelHeading.rect.top : null,
                  designActionsTop: designActionsHeading.rect ? designActionsHeading.rect.top : null,
                  batchTop: batchHeading.rect ? batchHeading.rect.top : null,
                  designGuideTop: designGuideCard.rect ? designGuideCard.rect.top : null,
                  modelNearDesignActions: Boolean(modelHeading.visible && designActionsHeading.visible && Math.abs((modelHeading.rect.top || 0) - (designActionsHeading.rect.top || 0)) <= 160),
                  designGuideAfterBatch: Boolean(designGuideCard.visible && batchHeading.visible && (designGuideCard.rect.top || 0) > (batchHeading.rect.top || 0))
                }
              };
            }
            """
        )
        or {}
    )


def _classify_failures(snapshot: dict[str, Any], browser_contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    body_text = str(snapshot.get("bodyText") or "")
    elements = dict(snapshot.get("elements") or {})
    counts = dict(snapshot.get("counts") or {})
    layout = dict(snapshot.get("layout") or {})
    requested_recipe = str(browser_contract.get("requested_recipe") or "").strip()
    applied_recipe = str(browser_contract.get("applied_recipe") or "").strip()
    if not browser_contract.get("browser_state_available"):
        failures.append("browser_state_not_available")
    if browser_contract.get("browser_recipe_error"):
        failures.append(f"browser_recipe_error:{browser_contract.get('browser_recipe_error')}")
    if requested_recipe and applied_recipe != requested_recipe:
        failures.append(f"requested_browser_recipe_mismatch:requested={requested_recipe}:applied={applied_recipe}")
    if not browser_contract.get("final_card_ready"):
        failures.append("final_design_guide_card_not_ready")
    if browser_contract.get("loading_shell_visible"):
        failures.append("final_design_guide_loading_shell_visible")
    if browser_red_screen_findings(snapshot):
        failures.append("red_screen_sentinel_finding")
    if "Inputs page stable rerun shell" in body_text:
        failures.append("inputs_stable_rerun_shell_visible_without_real_content")
    for marker in FORBIDDEN_VISIBLE_TEXT:
        if marker in body_text:
            failures.append(f"forbidden_visible_text:{marker}")
    if int(counts.get("designGuideHeadingCount") or 0) > 1:
        failures.append("duplicate_design_guide_heading")
    if int(counts.get("designGuideCardCount") or 0) > 1:
        failures.append("duplicate_design_guide_card")
    if not dict(elements.get("summaryBending") or {}).get("visible"):
        failures.append("bending_summary_card_not_visible")
    if not dict(elements.get("summaryShear") or {}).get("visible"):
        failures.append("shear_summary_card_not_visible")
    if bool(snapshot.get("summaryLikeRawText")):
        failures.append("summary_cards_rendered_as_raw_text")
    if not dict(elements.get("modelHeading") or {}).get("visible"):
        failures.append("model_heading_not_visible")
    elif not layout.get("modelNearDesignActions"):
        failures.append("model_slot_moved_from_top_section")
    if not dict(elements.get("batchHeading") or {}).get("visible"):
        failures.append("batch_design_heading_not_visible")
    if not dict(elements.get("designGuideCard") or {}).get("visible"):
        failures.append("design_guide_card_not_visible")
    elif not layout.get("designGuideAfterBatch"):
        failures.append("design_guide_card_not_after_batch_section")
    return failures


def _build(base_url: str, *, timeout_ms: int, screenshot: bool) -> dict[str, Any]:
    stamp = _stamp()
    screenshot_path = ARTIFACT_DIR / f"design_guide_browser_visual_layout_lock_{stamp}.png"
    target_url = _url_with_browser_test_contract(base_url)
    browser_contract: dict[str, Any] = {
        "requested_recipe": _query_value(target_url, "browser_recipe"),
        "applied_recipe": "",
        "browser_recipe_error": "",
        "browser_state_available": False,
        "final_card_ready": False,
        "loading_shell_visible": False,
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
        final_card_probe = _wait_for_final_design_guide_card(page, timeout_s=max(8.0, timeout_ms / 1000.0))
        browser_contract["final_card_ready"] = bool(final_card_probe.get("final_card_ready"))
        browser_contract["loading_shell_visible"] = bool(final_card_probe.get("loading_shell_visible"))
        browser_contract["final_card_probe"] = final_card_probe
        try:
            browser_state = _load_browser_state(page, timeout_s=min(12.0, max(3.0, timeout_ms / 1000.0)))
        except Exception as exc:
            browser_state = {}
            browser_contract["browser_state_error"] = f"{type(exc).__name__}: {exc}"
        browser_contract["browser_state_available"] = bool(browser_state)
        browser_contract["applied_recipe"] = _browser_recipe_from_state(browser_state)
        browser_contract["browser_recipe_error"] = _browser_recipe_error_from_state(browser_state)
        page.wait_for_timeout(750)
        snapshot = _browser_snapshot(page)
        if screenshot:
            page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()
    failures = _classify_failures(snapshot, browser_contract)
    return {
        "schema": "design_guide.browser_visual_layout_lock.v1",
        "status": "PASS" if not failures else "FAIL",
        "timestamp": stamp,
        "product_behaviour_changed": False,
        "base_url": target_url,
        "browser_contract": browser_contract,
        "snapshot_hash": _stable_hash(snapshot),
        "screenshot": str(screenshot_path) if screenshot else None,
        "snapshot": {
            key: value for key, value in snapshot.items() if key != "bodyText"
        },
        "body_text_sample": str(snapshot.get("bodyText") or "")[:2000],
        "red_screen_findings": browser_red_screen_findings(snapshot),
        "failures": failures,
        "direct_proof": {
            "no_duplicate_design_guide": "duplicate_design_guide_heading" not in failures
            and "duplicate_design_guide_card" not in failures,
            "summary_cards_visible_and_not_raw_text": "bending_summary_card_not_visible" not in failures
            and "shear_summary_card_not_visible" not in failures
            and "summary_cards_rendered_as_raw_text" not in failures,
            "model_slot_still_in_top_section": "model_slot_moved_from_top_section" not in failures
            and "model_heading_not_visible" not in failures,
            "legacy_visible_surfaces_absent": not any(item.startswith("forbidden_visible_text") for item in failures),
            "red_screen_absent": "red_screen_sentinel_finding" not in failures,
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Browser Visual Layout Lock",
        "",
        f"Status: `{payload['status']}`",
        f"Base URL: `{payload['base_url']}`",
        f"Screenshot: `{payload.get('screenshot')}`",
        "",
        "## Direct Proof",
        "",
    ]
    for key, value in dict(payload["direct_proof"]).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Failures", "", f"`{payload['failures']}`", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-ms", type=int, default=45_000)
    parser.add_argument("--no-screenshot", action="store_true")
    args = parser.parse_args(argv)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build(str(args.base_url), timeout_ms=int(args.timeout_ms), screenshot=not args.no_screenshot)
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"design_guide_browser_visual_layout_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_browser_visual_layout_lock_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_browser_visual_layout_lock {payload['status']}")
    print(f"failures={payload['failures']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
