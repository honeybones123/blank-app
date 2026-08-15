"""Compare settled cold and warm calculation-page pixels without UI masking."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright


PAGES = ("bending", "shear", "creep", "shrinkage", "crack", "deflection")
HEADINGS = {
    "bending": "Bending capacity",
    "shear": "Shear & Torsion",
    "creep": "Creep",
    "shrinkage": "Shrinkage",
    "crack": "Crack",
    "deflection": "Deflection",
}


def _settle(page, slug: str) -> None:
    page.get_by_role("heading", name=HEADINGS[slug], exact=False).last.wait_for(
        state="visible", timeout=20_000
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        running = page.locator("[data-testid='stStatusWidget'] img[alt='Running...']")
        if running.count() == 0 or not running.first.is_visible():
            # Plotly's SVG is structurally ready before Chromium has completed
            # its final compositing pass. Compare settled pixels, not a partial
            # paint captured while the summary is already usable above it.
            page.wait_for_timeout(3000)
            return
        page.wait_for_timeout(80)
    raise AssertionError(f"{slug} did not settle")


def _difference(left_path: Path, right_path: Path) -> tuple[float, bool]:
    with Image.open(left_path).convert("RGB") as left, Image.open(right_path).convert("RGB") as right:
        if left.size != right.size:
            return 1.0, False
        diff = ImageChops.difference(left, right)
        pixels = left.size[0] * left.size[1]
        changed = sum(
            1 for pixel in diff.get_flattened_data() if pixel != (0, 0, 0)
        )
        return changed / max(pixels, 1), True


def main() -> int:
    output_dir = Path("tmp") / "cold-warm-visual-equivalence"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            for slug in PAGES:
                cid = f"visual-{slug}-{uuid.uuid4().hex}"
                url = f"http://127.0.0.1:8522/?page={slug}&fresh=1&cid={cid}"
                page.goto(url, wait_until="domcontentloaded")
                _settle(page, slug)
                page.mouse.move(0, 0)
                cold = output_dir / f"{slug}-cold.png"
                page.screenshot(path=str(cold), full_page=True)

                page.goto(
                    f"http://127.0.0.1:8522/?page=start&cid={cid}",
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(500)
                page.goto(
                    f"http://127.0.0.1:8522/?page={slug}&cid={cid}",
                    wait_until="domcontentloaded",
                )
                _settle(page, slug)
                page.mouse.move(0, 0)
                warm = output_dir / f"{slug}-warm.png"
                page.screenshot(path=str(warm), full_page=True)
                ratio, same_size = _difference(cold, warm)
                report[slug] = {
                    "same_size": same_size,
                    "changed_pixel_ratio": round(ratio, 8),
                    # Text anti-aliasing and Plotly canvas timing can alter a
                    # tiny number of pixels; structural drift is materially
                    # larger.  Keep the tolerance below one tenth of one per cent.
                    "equivalent": same_size and ratio <= 0.001,
                }
            browser.close()
        ok = all(item["equivalent"] for item in report.values())
        payload = {"ok": ok, "pages": report}
    except Exception as exc:
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "pages": report}
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
