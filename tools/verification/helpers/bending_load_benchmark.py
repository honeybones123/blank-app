"""Compare Bending summary and diagram-ready timing across app URLs."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from uuid import uuid4

from playwright.async_api import async_playwright


async def _run_once(playwright, base_url: str, run: int) -> dict:
    try:
        browser = await playwright.chromium.launch(headless=True)
    except Exception:
        browser = await playwright.chromium.launch(headless=True, channel="msedge")
    context = await browser.new_context(viewport={"width": 1365, "height": 768})
    page = await context.new_page()
    started = time.perf_counter()
    await page.goto(
        f"{base_url.rstrip('/')}?page=bending&cid=load-{run}-{uuid4()}",
        wait_until="domcontentloaded",
    )
    await page.get_by_role("heading", name="Bending capacity").wait_for(
        state="visible", timeout=30_000
    )
    summary_ms = (time.perf_counter() - started) * 1_000
    await page.locator("[data-bending-diagram-ready]").wait_for(
        state="attached", timeout=45_000
    )
    diagram_ms = (time.perf_counter() - started) * 1_000
    await context.close()
    await browser.close()
    return {"summary_ms": summary_ms, "diagram_ms": diagram_ms}


async def benchmark(urls: list[str], runs: int) -> dict:
    async with async_playwright() as playwright:
        result = {}
        for base_url in urls:
            samples = [
                await _run_once(playwright, base_url, run)
                for run in range(runs)
            ]
            result[base_url] = {
                "runs": samples,
                "summary": {
                    metric: {
                        "median": statistics.median(sample[metric] for sample in samples),
                        "worst": max(sample[metric] for sample in samples),
                    }
                    for metric in ("summary_ms", "diagram_ms")
                },
            }
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(benchmark(args.urls, args.runs)), indent=2))


if __name__ == "__main__":
    main()
