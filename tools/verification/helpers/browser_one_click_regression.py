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

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verification.helpers.browser_state_overlay import (
    merge_fragment_browser_state_overlay,
    select_browser_state_candidate,
    select_fragment_browser_state_overlay,
)


def _compact_solver_transaction(result: dict[str, Any]) -> dict[str, Any]:
    """Return the stable product transaction contract for A/B comparison."""
    solve = dict(result.get("one_click_solve") or {})
    envelope = dict(result.get("recommendation_envelope") or {})
    stable_envelope = {
        key: envelope.get(key)
        for key in (
            "status",
            "stop_reason",
            "classification",
            "governing_family",
            "target_band",
            "initial_worst_util",
            "final_worst_util",
            "reached_target_band",
            "step_count",
            "final_updates",
        )
        if key in envelope
    }
    return {
        key: value
        for key, value in {
            "status": result.get("status"),
            "stop_reason": result.get("stop_reason"),
            "initial_worst_util": result.get("initial_worst_util"),
            "final_worst_util": result.get("final_worst_util"),
            "reached_target_band": result.get("reached_target_band"),
            "step_count": result.get("step_count"),
            "final_updates": result.get("final_updates"),
            "one_click_solve": {
                key: solve.get(key)
                for key in (
                    "status",
                    "stop_reason",
                    "initial_worst_util",
                    "final_worst_util",
                    "reached_target_band",
                    "step_count",
                    "final_updates",
                )
                if key in solve
            },
            "recommendation_envelope": stable_envelope,
        }.items()
        if value not in ({}, None)
    }
from urllib.request import urlopen
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from tools.verification.recipes.one_click_recipe_defs import REGRESSION_CASES, RUNNABLE_RECIPES


BROWSER_STATE_LABEL = "Browser state"
def _design_guide_trace_path() -> Path:
    """Resolve the same trace file used by the live Design Guide runtime."""
    configured = os.environ.get("DESIGN_GUIDE_TRACE_PATH")
    if configured:
        return Path(configured)
    return REPO_ROOT / "artifacts" / "debug" / "design_guide" / "design_guide_trace.jsonl"


TRACER_PATH = _design_guide_trace_path()


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


def _terminate_process_tree(process: subprocess.Popen | None) -> None:
    """Terminate a verifier-owned app and its child processes reliably."""
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.wait(timeout=10)
            return
        except Exception:
            pass
    try:
        process.terminate()
        process.wait(timeout=10)
    except Exception:
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass


def _browser_state_raw_candidates(page) -> list[str]:
    try:
        values = page.evaluate(
            """
            () => {
              const selectors = [
                "textarea[aria-label='Browser state']",
                "[data-testid='stTextArea'] textarea",
                "[aria-label='Browser state']",
                "[data-testid='stCodeBlock']"
              ];
              const values = [];
              for (const selector of selectors) {
                for (const el of Array.from(document.querySelectorAll(selector))) {
                  const raw = "value" in el ? el.value : (el.textContent || "");
                  if (raw && raw.trim()) {
                    values.push(raw.trim());
                  }
                }
              }
              return values;
            }
            """
        )
        return [str(value or "") for value in (values or []) if str(value or "").strip()]
    except Exception:
        return []


def _browser_state_publishes_updates(
    state: dict[str, Any],
    expected_updates: dict[str, Any],
) -> bool:
    if not expected_updates:
        return False
    sources = [
        value
        for value in (
            state.get("browser_shared_probe"),
            state.get("summary_state_probe"),
        )
        if isinstance(value, dict)
    ]
    for source in sources:
        if all(
            key in source
            and (
                abs(float(source[key]) - float(expected)) <= 1e-6
                if (
                    isinstance(source[key], (int, float))
                    and not isinstance(source[key], bool)
                    and isinstance(expected, (int, float))
                    and not isinstance(expected, bool)
                )
                else source[key] == expected
            )
            for key, expected in expected_updates.items()
        ):
            return True
    return False


def _load_browser_state(
    page,
    *,
    fallback_timeout_ms: int = 30_000,
    preferred_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for raw in _browser_state_raw_candidates(page):
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            candidates.append(payload)
    if not candidates:
        locator = page.get_by_label(BROWSER_STATE_LABEL)
        locator.first.wait_for(state="attached", timeout=max(100, int(fallback_timeout_ms)))
        try:
            count = int(locator.count())
        except Exception:
            count = 1
        for index in range(max(count, 1)):
            try:
                raw = locator.nth(index).input_value(timeout=max(100, min(10_000, int(fallback_timeout_ms)))) or "{}"
            except Exception:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if isinstance(payload, dict):
                candidates.append(payload)

    expected_updates = dict(preferred_updates or {})
    matching_candidates = [
        payload
        for payload in candidates
        if _browser_state_publishes_updates(payload, expected_updates)
    ]
    base_state = select_browser_state_candidate(
        matching_candidates or candidates
    )
    overlay_candidates = candidates
    if expected_updates:
        matching_overlay_candidates = [
            payload
            for payload in candidates
            if isinstance(payload.get("browser_state_overlay"), dict)
            and _browser_state_publishes_updates(
                dict(payload.get("browser_state_overlay") or {}),
                expected_updates,
            )
        ]
        # A known post-Apply transaction must never be overlaid by a fragment
        # that still publishes the pre-Apply engineering values.
        overlay_candidates = matching_overlay_candidates
    fragment_overlay = select_fragment_browser_state_overlay(
        overlay_candidates,
        base_state=base_state,
    )
    return (
        merge_fragment_browser_state_overlay(
            dict(base_state),
            fragment_overlay,
        )
        if fragment_overlay
        else dict(base_state)
    )


def _wait_for_solver_state(page, *, timeout_ms: int = 45_000) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + (timeout_ms / 1000.0)
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last_state = _load_browser_state(page, fallback_timeout_ms=1_000)
        except Exception:
            time.sleep(0.4)
            continue
        solver_result = dict(last_state.get("solver_result") or {})
        feedback = dict(last_state.get("one_click_feedback") or {})
        if solver_result or feedback:
            return last_state, False
        time.sleep(0.4)
    return last_state, True


def _values_match(actual: Any, expected: Any) -> bool:
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(
        expected, (int, float)
    ) and not isinstance(expected, bool):
        return abs(float(actual) - float(expected)) <= 1e-6
    return actual == expected


def _wait_for_product_apply_state(
    page,
    *,
    expected_updates: dict[str, Any],
    timeout_ms: int,
) -> tuple[dict[str, Any], bool]:
    """Wait for the real Apply button to publish its committed input projection."""

    deadline = time.time() + (timeout_ms / 1000.0)
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last_state = _load_browser_state(
                page,
                fallback_timeout_ms=1_000,
                preferred_updates=expected_updates,
            )
        except Exception:
            time.sleep(0.25)
            continue
        feedback = dict(last_state.get("one_click_feedback") or {})
        if feedback.get("error") or feedback.get("status") == "error":
            return last_state, False
        summary = dict(last_state.get("summary_state_probe") or {})
        if expected_updates and all(
            key in summary and _values_match(summary.get(key), expected)
            for key, expected in expected_updates.items()
        ):
            return last_state, False
        time.sleep(0.25)
    return last_state, True


def _wait_for_post_render_state(
    page,
    *,
    timeout_ms: int = 45_000,
) -> tuple[dict[str, Any], bool]:
    deadline = time.time() + (timeout_ms / 1000.0)
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last_state = _load_browser_state(
                page,
                fallback_timeout_ms=1_000,
            )
        except Exception:
            time.sleep(0.25)
            continue
        phase = str(
            last_state.get("browser_probe_phase")
            or last_state.get("probe_phase")
            or ""
        ).strip()
        if (
            phase == "post_page_render"
            and not bool(last_state.get("pre_page_render_lightweight"))
        ):
            return last_state, False
        time.sleep(0.25)
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


def _run_end_contains_expected_updates(
    payload: dict[str, Any],
    expected_updates: dict[str, Any] | None,
) -> bool:
    """Return whether a trace run_end belongs to the clicked Apply payload.

    Parallel family workers append to one shared trace. Run IDs are unique but
    the first run started after a click can belong to another worker, so the
    clicked publication updates are the stable cross-process correlation key.
    """

    expected = dict(expected_updates or {})
    if not expected:
        return True
    data = payload.get("data")
    data = dict(data) if isinstance(data, dict) else {}
    route = data.get("last_apply_route")
    route = dict(route) if isinstance(route, dict) else {}
    actual = route.get("applied_updates") or data.get("final_updates")
    actual = dict(actual) if isinstance(actual, dict) else {}
    if not actual:
        return False

    def _matches(actual_value: Any, expected_value: Any) -> bool:
        if isinstance(actual_value, (int, float)) and isinstance(
            expected_value,
            (int, float),
        ):
            return abs(float(actual_value) - float(expected_value)) <= 1e-9
        return actual_value == expected_value

    return all(
        key in actual and _matches(actual.get(key), expected_value)
        for key, expected_value in expected.items()
    )


def _wait_for_run_end(
    start_offset: int,
    *,
    timeout_s: float = 45.0,
    start_time_ms: int | None = None,
    expected_updates: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, int]:
    deadline = time.time() + timeout_s
    offset = start_offset
    latest: dict[str, Any] | None = None
    expected_run_id: str | None = None
    correlated_updates = dict(expected_updates or {})
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
            if (
                event == "run_start"
                and not correlated_updates
                and not expected_run_id
            ):
                expected_run_id = str(payload.get("run_id") or "").strip() or None
                continue
            if event != "run_end":
                continue
            if correlated_updates:
                if not _run_end_contains_expected_updates(
                    payload,
                    correlated_updates,
                ):
                    continue
            elif expected_run_id is not None:
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
        if (
            event == "run_start"
            and not correlated_updates
            and fallback_run_id is None
        ):
            fallback_run_id = str(payload.get("run_id") or "").strip() or None
            continue
        if event != "run_end":
            continue
        if correlated_updates:
            if not _run_end_contains_expected_updates(
                payload,
                correlated_updates,
            ):
                continue
        elif fallback_run_id is not None:
            if str(payload.get("run_id") or "").strip() != fallback_run_id:
                continue
        fallback_latest = payload
    if fallback_latest is not None:
        return fallback_latest, offset
    return latest, offset


def _start_streamlit(
    port: int,
    *,
    app_script: str = "app.py",
    one_click_implementation: str | None = None,
    auto_invoke: bool = False,
) -> subprocess.Popen:
    env = dict(os.environ)
    env["CODEX_BROWSER_TEST_MODE"] = "1"
    if one_click_implementation:
        env["INPUTS_ONE_CLICK_AB_IMPLEMENTATION"] = (
            one_click_implementation
        )
    if auto_invoke:
        env["INPUTS_ONE_CLICK_AB_AUTO_INVOKE"] = "1"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_script,
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.fileWatcherType",
        "none",
    ]
    log_dir = REPO_ROOT / "artifacts" / "debug" / "verification"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"streamlit_startup_{int(port)}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    process._codex_startup_log_path = str(log_path)  # type: ignore[attr-defined]
    process._codex_startup_log_handle = log_handle  # type: ignore[attr-defined]
    try:
        _wait_for_http(f"http://127.0.0.1:{port}")
    except Exception as exc:
        log_handle.flush()
        try:
            tail = log_path.read_text(encoding="utf-8", errors="ignore")[-4000:]
        except Exception:
            tail = ""
        exit_code = process.poll()
        _terminate_process_tree(process)
        try:
            log_handle.close()
        except Exception:
            pass
        if exit_code is not None:
            raise RuntimeError(
                f"Streamlit startup failed on port {port}; exit_code={exit_code}; "
                f"log={log_path}; tail={tail!r}"
            ) from exc
        raise RuntimeError(
            f"Streamlit startup timed out on port {port}; log={log_path}; tail={tail!r}"
        ) from exc
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
    parser.add_argument(
        "--click-apply",
        action="store_true",
        help="Click the production Apply recommendation button and verify committed updates.",
    )
    parser.add_argument("--headed", action="store_true", help="Run Chromium headed instead of headless.")
    parser.add_argument(
        "--browser-channel",
        default=None,
        help="Optional Playwright browser channel, for example msedge on Windows.",
    )
    parser.add_argument(
        "--app-script",
        default="app.py",
        help="Streamlit entry script to launch.",
    )
    parser.add_argument(
        "--one-click-implementation",
        choices=("legacy", "permanent", "production"),
        default=None,
        help="Implementation selector passed to the A/B Streamlit entry.",
    )
    parser.add_argument(
        "--auto-invoke",
        action="store_true",
        help="Request verifier-only one-click invocation after recipe seed.",
    )
    parser.add_argument(
        "--transaction-timeout-sec",
        type=float,
        default=120.0,
        help="Maximum wait for an auto-invoked solver transaction.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact transaction evidence instead of full browser state.",
    )
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
            process = _start_streamlit(
                args.port,
                app_script=args.app_script,
                one_click_implementation=args.one_click_implementation,
                auto_invoke=bool(args.auto_invoke),
            )
        else:
            _wait_for_http(base_url)

        with sync_playwright() as playwright:
            launch_options = {"headless": not args.headed}
            if args.browser_channel:
                launch_options["channel"] = args.browser_channel
            try:
                browser = playwright.chromium.launch(**launch_options)
            except Exception as exc:
                if args.browser_channel or os.name != "nt":
                    raise
                print(
                    "Bundled Chromium was unavailable; retrying with the installed "
                    f"Microsoft Edge channel ({exc.__class__.__name__}).",
                    file=sys.stderr,
                )
                browser = playwright.chromium.launch(
                    headless=not args.headed,
                    channel="msedge",
                )
            results = {}
            for name in names:
                context = browser.new_context()
                page = context.new_page()
                page.goto(
                    _query(
                        base_url,
                        {
                            "page": "inputs",
                            "browser_recipe": name,
                            "one_click_auto_invoke": (
                                "1" if args.auto_invoke else None
                            ),
                        },
                    ),
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                page.get_by_label(BROWSER_STATE_LABEL).wait_for(
                    state="attached",
                    timeout=max(
                        30_000,
                        int(args.transaction_timeout_sec * 1000),
                    ),
                )
                initial_state, post_render_timeout = (
                    _wait_for_post_render_state(page)
                )
                final_state = initial_state
                button_found = False
                solver_state_timeout = False
                tracer_offset = TRACER_PATH.stat().st_size if TRACER_PATH.exists() else 0
                run_end_event = None
                product_apply_expected_updates: dict[str, Any] = {}
                product_apply_updates_committed = False
                click_started_ms = None
                if args.auto_invoke:
                    click_started_ms = int(time.time() * 1000)
                    final_state, solver_state_timeout = (
                        _wait_for_solver_state(
                            page,
                            timeout_ms=int(
                                max(
                                    args.transaction_timeout_sec,
                                    1.0,
                                )
                                * 1000
                            ),
                        )
                    )
                    if not solver_state_timeout:
                        run_end_event, _ = _wait_for_run_end(
                            tracer_offset,
                            timeout_s=max(
                                args.transaction_timeout_sec,
                                1.0,
                            ),
                            start_time_ms=click_started_ms,
                        )
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
                if args.click_apply:
                    contract = dict(final_state.get("primary_button_contract") or {})
                    expected_updates = dict(contract.get("updates") or {})
                    product_apply_expected_updates = expected_updates
                    button = page.get_by_role("button", name="Apply recommendation")
                    try:
                        button.wait_for(state="visible", timeout=10_000)
                        button_found = True
                        click_started_ms = int(time.time() * 1000)
                        button.click(timeout=10_000)
                        final_state, solver_state_timeout = _wait_for_product_apply_state(
                            page,
                            expected_updates=expected_updates,
                            timeout_ms=int(max(args.transaction_timeout_sec, 1.0) * 1000),
                        )
                        product_apply_updates_committed = not solver_state_timeout
                        run_end_event, _ = _wait_for_run_end(
                            tracer_offset,
                            timeout_s=2.0,
                            start_time_ms=click_started_ms,
                            expected_updates=expected_updates,
                        )
                    except PlaywrightTimeoutError:
                        button_found = False
                visible_button_labels = page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll("button"))
                      .filter((el) => {
                        const r = el.getBoundingClientRect();
                        const s = window.getComputedStyle(el);
                        return r.width > 0 && r.height > 0
                          && s.display !== "none"
                          && s.visibility !== "hidden";
                      })
                      .map((el) => (el.innerText || el.textContent || "").trim())
                      .filter(Boolean)
                    """
                )
                results[name] = {
                    "initial_state": initial_state,
                    "final_state": final_state,
                    "button_found": button_found,
                    "post_render_timeout": post_render_timeout,
                    "solver_state_timeout": solver_state_timeout,
                    "run_end_event": run_end_event,
                    "product_apply_expected_updates": product_apply_expected_updates,
                    "product_apply_updates_committed": product_apply_updates_committed,
                    "visible_button_labels": visible_button_labels,
                }
                context.close()
            browser.close()
            if args.summary_only:
                compact = {}
                for name, result in results.items():
                    final_state = dict(result.get("final_state") or {})
                    solver_result = dict(
                        final_state.get("solver_result") or {}
                    )
                    feedback = dict(
                        final_state.get("one_click_feedback") or {}
                    )
                    compact[name] = {
                        "button_found": result.get("button_found"),
                        "post_render_timeout": result.get(
                            "post_render_timeout"
                        ),
                        "solver_state_timeout": result.get(
                            "solver_state_timeout"
                        ),
                        "product_apply_updates_committed": result.get(
                            "product_apply_updates_committed"
                        ),
                        "product_apply_expected_updates": result.get(
                            "product_apply_expected_updates"
                        ),
                        "solver_result": _compact_solver_transaction(
                            solver_result
                        ),
                        "one_click_feedback": feedback,
                        "run_end_event": result.get("run_end_event"),
                        "visible_button_labels": result.get(
                            "visible_button_labels"
                        ),
                        "requested_browser_recipe": final_state.get(
                            "requested_browser_recipe"
                        ),
                        "applied_browser_recipe": final_state.get(
                            "applied_browser_recipe"
                        ),
                        "implementation": final_state.get(
                            "implementation"
                        ),
                        "recipe": final_state.get("recipe"),
                        "shared_subset": final_state.get(
                            "shared_subset"
                        ),
                        "session_contract": final_state.get(
                            "session_contract"
                        ),
                        "transaction_error": final_state.get(
                            "transaction_error"
                        ),
                        "post_commit_audit": final_state.get(
                            "post_commit_audit"
                        ),
                    }
                print(json.dumps(compact, indent=2))
            else:
                print(json.dumps(results, indent=2))
    finally:
        _terminate_process_tree(process)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
