"""Capture the locked UI geometry contract from a running Beam app.

This is deliberately presentation-only. It records screenshots and computed
browser geometry without changing application or engineering state.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright


PAGES = (
    "start",
    "inputs",
    "design",
    "bending",
    "shear",
    "creep",
    "shrinkage",
    "crack",
    "deflection",
)
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000},
    "narrow": {"width": 768, "height": 1000},
}


async def _wait_until_ready(page) -> None:
    await page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=30_000)
    # The shell may first paint before query-parameter routing dispatches the
    # requested page. Give that rerun a chance to start before checking idle.
    await page.wait_for_timeout(1_500)
    for _ in range(120):
        busy = await page.locator('[data-testid="stStatusWidget"]').count()
        if not busy:
            break
        await page.wait_for_timeout(100)
    await page.wait_for_timeout(750)


async def _measure(page) -> dict:
    return await page.evaluate(
        """
        () => {
          const rect = (node) => {
            if (!node) return null;
            const box = node.getBoundingClientRect();
            return {
              x: Math.round(box.x * 100) / 100,
              y: Math.round(box.y * 100) / 100,
              width: Math.round(box.width * 100) / 100,
              height: Math.round(box.height * 100) / 100,
            };
          };
          const style = (node) => {
            if (!node) return null;
            const css = getComputedStyle(node);
            return {
              color: css.color,
              backgroundColor: css.backgroundColor,
              borderRadius: css.borderRadius,
              fontSize: css.fontSize,
              fontWeight: css.fontWeight,
              marginTop: css.marginTop,
              marginBottom: css.marginBottom,
              padding: css.padding,
            };
          };
          const main = document.querySelector('[data-testid="stMainBlockContainer"]');
          const headings = [...document.querySelectorAll('h1,h2,h3,.result-page-title,.section-title')]
            .filter((node) => node.getBoundingClientRect().height > 0)
            .slice(0, 12)
            .map((node) => ({text: node.textContent.trim(), rect: rect(node), style: style(node)}));
          const cards = [...document.querySelectorAll('[data-testid="stExpander"]')]
            .filter((node) => node.getBoundingClientRect().height > 0)
            .slice(0, 12)
            .map((node) => {
              const summary = node.querySelector('summary');
              return {rect: rect(node), summaryRect: rect(summary), style: style(node), summaryStyle: style(summary)};
            });
          return {
            viewport: {width: window.innerWidth, height: window.innerHeight},
            main: {rect: rect(main), style: style(main)},
            headings,
            cards,
            visibleTabs: [...document.querySelectorAll('[role="tab"]')]
              .filter((node) => node.getBoundingClientRect().height > 0)
              .map((node) => node.textContent.trim()),
            exceptions: [...document.querySelectorAll('[data-testid="stException"]')]
              .map((node) => node.textContent.trim()),
          };
        }
        """
    )


async def capture(base_url: str, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots = output_dir / "screenshots"
    screenshots.mkdir(exist_ok=True)
    result = {"base_url": base_url, "pages": {}}
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
        except Exception:
            # Match the performance benchmark fallback on Windows workstations
            # where Playwright's private Chromium bundle is not installed.
            browser = await playwright.chromium.launch(headless=True, channel="msedge")
        for viewport_name, viewport in VIEWPORTS.items():
            context = await browser.new_context(viewport=viewport)
            for slug in PAGES:
                page = await context.new_page()
                query = urlencode({"page": slug, "ui_contract": viewport_name})
                await page.goto(f"{base_url.rstrip('/')}?{query}", wait_until="domcontentloaded")
                await _wait_until_ready(page)
                key = f"{viewport_name}:{slug}"
                result["pages"][key] = await _measure(page)
                await page.screenshot(
                    path=screenshots / f"{viewport_name}-{slug}.png",
                    full_page=True,
                )
                await page.close()
            await context.close()
        await browser.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8506/")
    parser.add_argument("--output", type=Path, default=Path("work/ui-contract"))
    args = parser.parse_args()
    payload = asyncio.run(capture(args.base_url, args.output))
    output_file = args.output / "geometry.json"
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output_file)


if __name__ == "__main__":
    main()
