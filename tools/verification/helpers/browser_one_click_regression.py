"""Dev-only browser regression runner for frozen one-click recipes.

This script uses Playwright for Python and the app's dev-only browser recipe
hook to open exact frozen cases in a real browser session.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib.request import urlopen
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verification.recipes.one_click_recipe_defs import REGRESSION_CASES, RUNNABLE_RECIPES


BROWSER_STATE_LABEL = "Browser state"
TRACER_PATH = REPO_ROOT / "design_guide_tracer.jsonl"


def _query(url: str, params: dict[str, Any]) -> str:
    pairs = {key: value for key, value in params.items() if value is not None}
    base = str(url or "").rstrip("/")
    return f"{base}/?{urlencode(pairs)}"


def _wait_for_http(url: str, timeout_s: float = 45.0) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            with urlopen(url) as response:  # noqa: S310 - local dev server only
                if 200 <= int(response.status) < 500:
                    return
        except Exception as exc:  # pragma: no cover - best effort dev utility
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for app at {url}: {last_error}")


def _load_browser_state(page) -> dict[str, Any]:
    raw = page.get_by_label(BROWSER_STATE_LABEL).input_value(timeout=30_000) or "{}"
    return json.loads(raw)


def _wait_for_solver_state(page, *, timeout_ms: int = 45_000) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + (timeout_ms / 1000.0)
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        last_state = _load_browser_state(page)
        solver_result = dict(last_state.get("solver_result") or {})
        feedback = dict(last_state.get("one_click_feedback") or {})
        if solver_result or feedback:
            return last_state, False
        time.sleep(0.4)
    return last_state, True


def _read_tracer_lines_since(offset: int) -> tuple[list[str], int]:
    if not TRACER_PATH.exists():
        return [], offset
    with TRACER_PATH.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.seek(offset)
        data = handle.read()
        new_offset = handle.tell()
    if not data:
        return [], new_offset
    return [line for line in data.splitlines() if line.strip()], new_offset


def _wait_for_run_end(
    start_offset: int,
    *,
    timeout_s: float = 45.0,
    start_time_ms: int | None = None,
) -> tuple[dict[str, Any] | None, int]:
    deadline = time.time() + timeout_s
    offset = start_offset
    latest: dict[str, Any] | None = None
    expected_run_id: str | None = None
    while time.time() < deadline:
        lines, offset = _read_tracer_lines_since(offset)
        for line in lines:
            try:
                payload = json.loads(line)
            except Exception:
                continue
            event = payload.get("event")
            payload_ts = payload.get("timestamp_ms")
            if start_time_ms is not None:
                try:
                    if int(payload_ts) < int(start_time_ms):
                        continue
                except Exception:
                    continue
            if event == "run_start" and not expected_run_id:
                expected_run_id = str(payload.get("run_id") or "").strip() or None
                continue
            if event != "run_end":
                continue
            if expected_run_id is not None:
                if str(payload.get("run_id") or "").strip() != expected_run_id:
                    continue
            latest = payload
        if latest is not None:
            return latest, offset
        time.sleep(0.4)
    # Fallback: if the incremental tail missed the current run, rescan the
    # whole tracer and match run_end to the first run_start after this click.
    lines, offset = _read_tracer_lines_since(0)
    fallback_run_id: str | None = expected_run_id
    fallback_latest: dict[str, Any] | None = None
    for line in lines:
        try:
            payload = json.loads(line)
        except Exception:
            continue
        event = payload.get("event")
        payload_ts = payload.get("timestamp_ms")
        if start_time_ms is not None:
            try:
                if int(payload_ts) < int(start_time_ms):
                    continue
            except Exception:
                continue
        if event == "run_start" and fallback_run_id is None:
            fallback_run_id = str(payload.get("run_id") or "").strip() or None
            continue
        if event != "run_end":
            continue
        if fallback_run_id is not None:
            if str(payload.get("run_id") or "").strip() != fallback_run_id:
                continue
        fallback_latest = payload
    if fallback_latest is not None:
        return fallback_latest, offset
    return latest, offset


def _start_streamlit(port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["CODEX_BROWSER_TEST_MODE"] = "1"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.fileWatcherType",
        "none",
    ]
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_http(f"http://127.0.0.1:{port}")
    return process


def _case_names(args) -> list[str]:
    if args.case:
        return list(args.case)
    if args.all_core:
        return [item["name"] for item in REGRESSION_CASES]
    if args.all_recipes:
        return [item["name"] for item in RUNNABLE_RECIPES]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List available core cases and frozen recipe runs.")
    parser.add_argument("--case", action="append", help="Case or runnable recipe name to open.")
    parser.add_argument("--all-core", action="store_true", help="Open all six core regression cases.")
    parser.add_argument("--all-recipes", action="store_true", help="Open all runnable frozen recipe cases.")
    parser.add_argument("--port", type=int, default=8511, help="Local Streamlit port to use.")
    parser.add_argument("--base-url", default=None, help="Use an already-running app instead of starting Streamlit.")
    parser.add_argument("--click-one-click", action="store_true", help="Click the visible one-click button when present.")
    parser.add_argument("--headed", action="store_true", help="Run Chromium headed instead of headless.")
    args = parser.parse_args(argv)

    if args.list:
        print(
            json.dumps(
                {
                    "core_cases": [item["name"] for item in REGRESSION_CASES],
                    "runnable_recipes": [item["name"] for item in RUNNABLE_RECIPES],
                },
                indent=2,
            )
        )
        return 0

    names = _case_names(args)
    if not names:
        parser.error("Provide --case, --all-core, or --all-recipes.")

    process = None
    base_url = args.base_url or f"http://127.0.0.1:{args.port}"
    try:
        if args.base_url is None:
            process = _start_streamlit(args.port)
        else:
            _wait_for_http(base_url)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            results = {}
            for name in names:
                context = browser.new_context()
                page = context.new_page()
                page.goto(
                    _query(base_url, {"page": "inputs", "browser_recipe": name}),
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                page.get_by_label(BROWSER_STATE_LABEL).wait_for(state="attached", timeout=30_000)
                initial_state = _load_browser_state(page)
                final_state = initial_state
                button_found = False
                solver_state_timeout = False
                tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
                run_end_event = None
                click_started_ms = None
                if args.click_one_click:
                    button = page.get_by_role("button", name="Run one-click auto design")
                    try:
                        button.wait_for(timeout=10_000)
                        if button.is_visible():
                            button_found = True
                            click_started_ms = int(time.time() * 1000)
                            button.click(timeout=10_000)
                            final_state, solver_state_timeout = _wait_for_solver_state(page)
                            run_end_event, _ = _wait_for_run_end(
                                tracer_offset,
                                start_time_ms=click_started_ms,
                            )
                    except PlaywrightTimeoutError:
                        button_found = False
                results[name] = {
                    "initial_state": initial_state,
                    "final_state": final_state,
                    "button_found": button_found,
                    "solver_state_timeout": solver_state_timeout,
                    "run_end_event": run_end_event,
                }
                context.close()
            browser.close()
            print(json.dumps(results, indent=2))
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
