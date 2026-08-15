"""Exercise shared Runtime header and Inputs batch buttons in a fresh session."""

from __future__ import annotations

import json
import time
from urllib.parse import urlencode

from playwright.sync_api import Page, sync_playwright


def _settle(page: Page) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        running = page.locator("[data-testid='stStatusWidget'] img[alt='Running...']")
        if running.count() == 0 or not running.first.is_visible():
            page.wait_for_timeout(350)
            return
        page.wait_for_timeout(80)
    raise AssertionError("page did not settle")


def _healthy(page: Page) -> None:
    if "page=inputs" not in page.url:
        raise AssertionError(f"unexpected route {page.url!r}")
    errors = page.locator("[data-testid='stException']")
    if errors.count():
        raise AssertionError(errors.first.inner_text())


def main() -> int:
    evidence = []
    query = urlencode(
        {
            "page": "inputs",
            "fresh": "1",
            "cid": "shared-button-live-audit",
            "browser_test_mode": "1",
            "browser_recipe": "R1A_M300_V0",
        }
    )
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            page.goto(f"http://127.0.0.1:8522/?{query}", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Beam Inputs", exact=False).wait_for(timeout=20_000)
            _settle(page)
            _healthy(page)

            page.get_by_role("button", name="💾 Save", exact=True).click(force=True)
            _settle(page)
            _healthy(page)
            evidence.append({"button": "Save", "ok": True})

            # The PDF path may download immediately or complete via the
            # browser's download event.  Either way the app must remain healthy.
            page.get_by_role("button", name="📄 PDF Report", exact=True).click(force=True)
            _settle(page)
            _healthy(page)
            evidence.append({"button": "PDF Report", "ok": True})

            for label in (
                "▣ B1 project beam",
                "✓ OK 0 auto designed",
                "♙ AS 0 auto assigned",
                "⇩ D 0 imported actions",
                "⚑ Ready for setup",
                "◇ Constraints: none",
            ):
                button = page.get_by_role("button", name=label, exact=True)
                if not button.count():
                    raise AssertionError(f"missing batch button {label!r}")
                button.click(force=True)
                _settle(page)
                _healthy(page)
                evidence.append({"button": label, "ok": True})
            browser.close()
        report = {"ok": True, "evidence": evidence}
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "evidence": evidence}
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
