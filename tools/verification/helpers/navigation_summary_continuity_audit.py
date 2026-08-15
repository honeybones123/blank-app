"""Live proof that navigation and action-source changes keep summaries coherent."""

from __future__ import annotations

import argparse
import json
import time
from urllib.parse import urlencode

from playwright.sync_api import Page, sync_playwright


PAGE_HEADINGS = {
    "inputs": "Beam Inputs",
    "design": "Load Analysis",
    "bending": "Bending capacity",
    "shear": "Shear & Torsion",
    "creep": "Creep",
    "shrinkage": "Shrinkage",
    "crack": "Crack",
    "deflection": "Deflection",
}


def _settle(page: Page, slug: str) -> None:
    page.get_by_role("heading", name=PAGE_HEADINGS[slug], exact=False).last.wait_for(
        state="visible", timeout=20_000
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        running = page.locator("[data-testid='stStatusWidget'] img[alt='Running...']")
        if running.count() == 0 or not running.first.is_visible():
            page.wait_for_timeout(350)
            break
        page.wait_for_timeout(80)
    exceptions = page.locator("[data-testid='stException']")
    if exceptions.count():
        raise AssertionError(exceptions.first.inner_text())
    if f"page={slug}" not in page.url:
        raise AssertionError(f"expected {slug!r}, got {page.url!r}")


def _navigate(page: Page, slug: str, label: str) -> None:
    # The top navigation is rendered as a Streamlit radio but its individual
    # inputs intentionally hide their labels.  The visible option text is the
    # stable user-facing target across Streamlit releases.
    page.get_by_text(label, exact=True).first.click(force=True)
    _settle(page, slug)


def _body(page: Page) -> str:
    return page.locator("body").inner_text()


def _assert_manual_moment(page: Page, expected: bool) -> None:
    token = "300.0 kNm"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if (token in _body(page)) == expected:
            return
        page.wait_for_timeout(100)
    raise AssertionError(
        f"manual moment visibility expected={expected}; token={token!r}"
    )


def run(base_url: str, cid: str) -> dict:
    query = urlencode(
        {
            "page": "inputs",
            "cid": cid,
            "browser_test_mode": "1",
            "browser_recipe": "R1A_M300_V0",
        }
    )
    evidence: list[dict] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"{base_url.rstrip('/')}/?{query}", wait_until="domcontentloaded")
        _settle(page, "inputs")
        _assert_manual_moment(page, True)
        evidence.append({"event": "manual_inputs_summary", "ok": True})

        routes = (
            ("bending", "Bending"),
            ("shear", "Shear"),
            ("creep", "Creep"),
            ("shrinkage", "Shrinkage"),
            ("crack", "Crack Control"),
            ("deflection", "Deflection"),
            ("inputs", "Beam Inputs"),
        )
        for slug, label in routes:
            _navigate(page, slug, label)
            evidence.append({"event": f"navigate_{slug}", "ok": True})
        _assert_manual_moment(page, True)
        evidence.append({"event": "manual_summary_survived_navigation", "ok": True})

        toggle_label = "Use Load Analysis actions for Beam Inputs"
        toggle = page.get_by_label(toggle_label, exact=True).first
        if toggle.is_checked():
            raise AssertionError("fresh manual recipe unexpectedly selected Load Analysis")
        toggle.click(force=True)
        _settle(page, "inputs")
        if not page.get_by_label(toggle_label, exact=True).first.is_checked():
            raise AssertionError("Load Analysis action source did not commit")
        _navigate(page, "bending", "Bending")
        _assert_manual_moment(page, False)
        evidence.append({"event": "analysis_source_reached_bending_summary", "ok": True})

        _navigate(page, "inputs", "Beam Inputs")
        page.get_by_label(toggle_label, exact=True).first.click(force=True)
        _settle(page, "inputs")
        if page.get_by_label(toggle_label, exact=True).first.is_checked():
            raise AssertionError("manual action source did not restore")
        _navigate(page, "bending", "Bending")
        _assert_manual_moment(page, True)
        evidence.append({"event": "manual_source_restored_without_stale_summary", "ok": True})
        browser.close()
    return {"ok": True, "cid": cid, "evidence": evidence}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8522")
    parser.add_argument("--cid", default="navigation-summary-continuity")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        report = run(args.base_url, args.cid)
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    payload = json.dumps(report, indent=2)
    print(payload)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
