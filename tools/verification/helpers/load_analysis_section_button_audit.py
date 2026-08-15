"""Live check for the Load Analysis design-section publication button."""

from __future__ import annotations

import json
import time
import uuid

from playwright.sync_api import sync_playwright


def _settle(page) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        running = page.locator("[data-testid='stStatusWidget'] img[alt='Running...']")
        if running.count() == 0 or not running.first.is_visible():
            page.wait_for_timeout(350)
            return
        page.wait_for_timeout(80)
    raise AssertionError("Load Analysis did not settle")


def main() -> int:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            cid = f"section-button-audit-{uuid.uuid4().hex}"
            page.goto(
                f"http://127.0.0.1:8522/?page=design&fresh=1&cid={cid}",
                wait_until="domcontentloaded",
            )
            page.get_by_role("heading", name="Load Analysis", exact=False).last.wait_for(
                timeout=20_000
            )
            _settle(page)
            page.get_by_text("Design section", exact=True).first.click(force=True)
            _settle(page)
            button = page.get_by_role("button", name="Use this section for design", exact=True)
            button.wait_for(state="visible", timeout=20_000)
            button.click(force=True)
            # Allow the fragment rerun to start before testing its status
            # indicator; otherwise an idle frame immediately after pointer-up
            # can be mistaken for completion.
            page.wait_for_timeout(800)
            _settle(page)
            errors = page.locator("[data-testid='stException']")
            if errors.count():
                raise AssertionError(errors.first.inner_text())
            body = page.locator("body").inner_text()
            if "Design actions set from x =" not in body:
                relevant = [
                    line
                    for line in body.splitlines()
                    if "design" in line.lower() or "section" in line.lower()
                ]
                raise AssertionError(
                    "section publication confirmation was not rendered; "
                    f"relevant={relevant[:20]!r}"
                )
            browser.close()
        report = {"ok": True, "button": "Use this section for design"}
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
