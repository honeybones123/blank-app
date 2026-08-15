"""Inventory every visible button on each Runtime engineering route."""

from __future__ import annotations

import json
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


PAGES = ("inputs", "design", "bending", "shear", "creep", "shrinkage", "crack", "deflection")


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel="msedge")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        report = {}
        for slug in PAGES:
            query = urlencode({"page": slug, "fresh": "1", "cid": "button-inventory"})
            page.goto(f"http://127.0.0.1:8522/?{query}", wait_until="domcontentloaded")
            page.wait_for_timeout(1800)
            buttons = page.get_by_role("button")
            rows = buttons.evaluate_all(
                "els => els.filter(el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length))"
                ".map(el => (el.getAttribute('aria-label') || el.innerText || '').trim())"
            )
            report[slug] = list(dict.fromkeys(value for value in rows if value))
        browser.close()
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
