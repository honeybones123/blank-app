from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]

RAILS = {
    "bending": {"key": "bending_input_scroll", "columns": 4},
    "shear": {"key": "shear_input_scroll", "columns": 4},
    "deflection": {"key": "deflection_primary_inputs", "columns": 3},
    "crack": {"key": "crack_primary_inputs", "columns": 3},
}


def _wait_for_server(base_url: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url, timeout=2.0) as response:
                if response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Streamlit server did not become ready at {base_url}: {last_error}")


def _start_streamlit(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("CODEX_BROWSER_TEST_MODE", "1")
    env.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _rail_snapshot(page, rail_key: str) -> dict:
    return page.evaluate(
        """
        (railKey) => {
          const outer = document.querySelector(`.st-key-${railKey}_outer`);
          const inner = document.querySelector(`.st-key-${railKey}_inner`);
          const doc = document.documentElement;
          const body = document.body;
          if (!outer || !inner) {
            return {found: false, railKey};
          }
          const outerRect = outer.getBoundingClientRect();
          const innerRect = inner.getBoundingClientRect();
          const horizontalBlock = inner.querySelector('[data-testid="stHorizontalBlock"]');
          const columns = horizontalBlock
            ? Array.from(horizontalBlock.children).map((element) => {
                const rect = element.getBoundingClientRect();
                return {
                  left: rect.left,
                  right: rect.right,
                  width: rect.width,
                  visibleWidth: Math.max(0, Math.min(rect.right, outerRect.right) - Math.max(rect.left, outerRect.left)),
                };
              })
            : [];
          return {
            found: true,
            railKey,
            outerClientWidth: outer.clientWidth,
            outerScrollWidth: outer.scrollWidth,
            innerClientWidth: inner.clientWidth,
            outerRectLeft: outerRect.left,
            outerRectRight: outerRect.right,
            outerRectWidth: outerRect.width,
            innerRectWidth: innerRect.width,
            documentClientWidth: doc.clientWidth,
            documentScrollWidth: doc.scrollWidth,
            bodyClientWidth: body.clientWidth,
            bodyScrollWidth: body.scrollWidth,
            outerOverflowX: getComputedStyle(outer).overflowX,
            outerOverflowY: getComputedStyle(outer).overflowY,
            columns,
          };
        }
        """,
        rail_key,
    )


def _assert_rail(page, slug: str, rail_key: str, column_count: int) -> dict:
    selector = f".st-key-{rail_key}_outer"
    page.wait_for_selector(selector, timeout=90_000)
    page.wait_for_timeout(500)
    snap = _rail_snapshot(page, rail_key)
    desired_visible_count = min(3, column_count)
    expected_ratio = max(1.0, float(column_count) / float(desired_visible_count))
    observed_ratio = float(snap["innerRectWidth"]) / max(float(snap["outerRectWidth"]), 1.0)
    page_overflow_px = max(
        float(snap["documentScrollWidth"]) - float(snap["documentClientWidth"]),
        float(snap["bodyScrollWidth"]) - float(snap["bodyClientWidth"]),
    )

    failures: list[str] = []
    columns = list(snap.get("columns") or [])
    visible_columns = [item for item in columns if float(item.get("visibleWidth") or 0.0) > 4.0]
    if not snap.get("found"):
        failures.append("rail_not_found")
    if str(snap.get("outerOverflowX")) not in {"auto", "scroll"}:
        failures.append(f"outer_overflow_x_{snap.get('outerOverflowX')}")
    if len(visible_columns) != desired_visible_count:
        failures.append(f"visible_column_count_{len(visible_columns)}")
    if len(columns) >= desired_visible_count:
        last_visible_right = float(columns[desired_visible_count - 1].get("right") or 0.0)
        outer_right = float(snap["outerRectLeft"]) + float(snap["outerClientWidth"])
        if abs(last_visible_right - outer_right) > 8.0:
            failures.append(f"last_visible_column_edge_gap_{abs(last_visible_right - outer_right):.1f}px")
    if len(columns) > desired_visible_count:
        next_visible_width = float(columns[desired_visible_count].get("visibleWidth") or 0.0)
        if next_visible_width > 4.0:
            failures.append(f"next_column_visible_{next_visible_width:.1f}px")
    if column_count > desired_visible_count and float(snap["outerScrollWidth"]) <= float(snap["outerClientWidth"]) + 4.0:
        failures.append("rail_does_not_scroll_horizontally")
    if page_overflow_px > 4.0:
        failures.append(f"page_horizontal_overflow_{page_overflow_px:.1f}px")

    snap.update(
        {
            "slug": slug,
            "expectedInnerOuterRatio": expected_ratio,
            "observedInnerOuterRatio": observed_ratio,
            "pageOverflowPx": page_overflow_px,
            "ok": not failures,
            "failures": failures,
        }
    )
    return snap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9317)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--skip-start-server", action="store_true")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/") or f"http://127.0.0.1:{args.port}"
    proc: subprocess.Popen | None = None
    if not args.skip_start_server:
        proc = _start_streamlit(args.port)

    try:
        _wait_for_server(base_url, timeout_s=90.0)
        results: list[dict] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            for slug, spec in RAILS.items():
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                try:
                    page.goto(f"{base_url}/?page={slug}", wait_until="commit", timeout=30_000)
                    results.append(_assert_rail(page, slug, str(spec["key"]), int(spec["columns"])))
                except PlaywrightTimeoutError:
                    results.append(
                        {
                            "slug": slug,
                            "railKey": spec["key"],
                            "ok": False,
                            "failures": ["navigation_or_rail_selector_timeout"],
                        }
                    )
                finally:
                    page.close()
            browser.close()

        failed = [item for item in results if not item.get("ok")]
        if failed:
            print("SPECIALIZED_WIDGET_RAIL browser smoke FAIL")
            for item in failed:
                print(f"- {item['slug']} ({item['railKey']}): {', '.join(item.get('failures') or [])}")
            return 1

        print("SPECIALIZED_WIDGET_RAIL browser smoke PASS")
        for item in results:
            print(
                f"- {item['slug']}: ratio {item['observedInnerOuterRatio']:.2f}, "
                f"rail scroll {item['outerScrollWidth']}>{item['outerClientWidth']}, "
                f"page overflow {item['pageOverflowPx']:.1f}px"
            )
        return 0
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
