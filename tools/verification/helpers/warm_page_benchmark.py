"""Measure repeated calculation-page navigation in one established session.

The cold benchmark deliberately starts a new server and browser for every page.
This companion keeps one server and browser alive, visits every calculation page
once, then measures repeated revisits.  Completion is tied to the app's dispatch
trace, so a heading appearing before the page finishes does not produce a false
fast result.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from playwright.sync_api import sync_playwright

from cold_page_benchmark import (
    PAGES,
    PAGE_NAV_LABELS,
    PAGE_TITLES,
    _terminate,
    _trace_events,
    _wait_for_http,
)


def _dispatch_count(output_root: Path, slug: str) -> int:
    return sum(
        1
        for event in _trace_events(output_root)
        if event.get("name") == "app.page_dispatch.end"
        and (
            str(event.get("page_slug") or "").strip().lower() == slug
            or str((event.get("meta") or {}).get("selected_slug") or "")
            .strip()
            .lower()
            == slug
        )
    )


def _wait_for_new_dispatch(
    output_root: Path,
    slug: str,
    previous_count: int,
    timeout_s: float = 60.0,
) -> None:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        if _dispatch_count(output_root, slug) > previous_count:
            return
        time.sleep(0.01)
    raise RuntimeError(f"timed out waiting for a new {slug} dispatch")


def _summary(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999) - 1))
    return {
        "runs": len(values),
        "median_page_open_ms": round(statistics.median(values), 3),
        "p95_page_open_ms": round(ordered[p95_index], 3),
        "worst_page_open_ms": round(max(values), 3),
        "all_under_1000_ms": all(value < 1000.0 for value in values),
    }


def run(root: Path, *, port: int, cycles: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="runtime-warm-pages-") as output_dir:
        output_root = Path(output_dir)
        environment = dict(os.environ)
        environment.update(
            {
                "BEAM_OUTPUTS_DIR": str(output_root),
                "CODEX_DISABLE_CALC_PAGE_WARMUP": "1",
                "CODEX_RENDER_TIMING_TRACE": "1",
            }
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.headless=true",
                f"--server.port={port}",
                "--server.fileWatcherType=none",
            ],
            cwd=root,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            _wait_for_http(base_url)
            with sync_playwright() as playwright:
                launch_args = [
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ]
                try:
                    browser = playwright.chromium.launch(headless=True, args=launch_args)
                except Exception:
                    browser = playwright.chromium.launch(
                        headless=True,
                        channel="msedge",
                        args=launch_args,
                    )
                context = browser.new_context()
                page = context.new_page()
                cid = f"warm-pages-{uuid4().hex}"
                page.goto(
                    f"{base_url}/?{urlencode({'page': 'start', 'fresh': '1', 'cid': cid})}",
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                page.get_by_role(
                    "heading", name="Start your beam design", exact=False
                ).first.wait_for(state="visible", timeout=60_000)

                # Establish every page once without including this first visit in
                # the warm-navigation result.
                for slug in PAGES:
                    before = _dispatch_count(output_root, slug)
                    page.get_by_text(PAGE_NAV_LABELS[slug], exact=True).first.click(
                        timeout=30_000,
                        force=True,
                    )
                    page.get_by_role(
                        "heading", name=PAGE_TITLES[slug], exact=False
                    ).first.wait_for(state="visible", timeout=60_000)
                    _wait_for_new_dispatch(output_root, slug, before)
                    # Do not let the first measured page compete with layout
                    # and paint still queued by the final warm-up page.
                    page.evaluate(
                        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
                    )

                measurements: dict[str, list[dict[str, Any]]] = {
                    slug: [] for slug in PAGES
                }
                for cycle in range(1, cycles + 1):
                    for slug in PAGES:
                        before = _dispatch_count(output_root, slug)
                        started = time.perf_counter()
                        page.get_by_text(PAGE_NAV_LABELS[slug], exact=True).first.click(
                            timeout=30_000,
                            force=True,
                        )
                        page.get_by_role(
                            "heading", name=PAGE_TITLES[slug], exact=False
                        ).first.wait_for(state="visible", timeout=60_000)
                        _wait_for_new_dispatch(output_root, slug, before)
                        page.evaluate(
                            "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
                        )
                        elapsed_ms = (time.perf_counter() - started) * 1000.0
                        measurements[slug].append(
                            {
                                "cycle": cycle,
                                "page_open_ms": round(elapsed_ms, 3),
                                "exception_count": page.locator(
                                    "[data-testid='stException']"
                                ).count(),
                            }
                        )
                context.close()
                browser.close()
        finally:
            _terminate(process)

    return {
        "definition": "one established server/browser/session; every page visited once before measured revisits",
        "cycles": cycles,
        "pages": {
            slug: {
                "runs": runs,
                "summary": _summary([float(item["page_open_ms"]) for item in runs]),
            }
            for slug, runs in measurements.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=9300)
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.root.resolve(), port=args.port, cycles=max(1, args.cycles))
    encoded = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if all(page["summary"]["all_under_1000_ms"] for page in result["pages"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
