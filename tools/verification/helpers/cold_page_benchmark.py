"""Measure isolated cold calculation-page opens with server-side phase evidence.

Cold page means the Streamlit server is reachable, but the browser session,
target page module and page presentation caches are fresh. Server boot is
reported separately and excluded from the page-open acceptance value.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any
from uuid import uuid4

from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from streamlit.proto.BackMsg_pb2 import BackMsg
from urllib.parse import urlencode
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


PAGES = ("bending", "shear", "creep", "shrinkage", "crack", "deflection")
PAGE_TITLES = {
    "bending": "Bending capacity",
    "shear": "Shear & Torsion",
    "creep": "Creep",
    "shrinkage": "Shrinkage",
    "crack": "Crack width",
    "deflection": "Beam Deflection",
}
PAGE_NAV_LABELS = {
    "bending": "Bending",
    "shear": "Shear",
    "creep": "Creep",
    "shrinkage": "Shrinkage",
    "crack": "Crack Control",
    "deflection": "Deflection",
}


def _wait_for_http(url: str, timeout_s: float = 60.0) -> None:
    deadline = time.perf_counter() + timeout_s
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            with urlopen(url) as response:  # noqa: S310 - local verifier only
                if int(response.status) < 500:
                    return
        except Exception as exc:  # pragma: no cover - environment dependent
            last_error = exc
        time.sleep(0.05)
    raise RuntimeError(f"server did not become ready at {url}: {last_error}")


def _trace_events(output_root: Path) -> list[dict[str, Any]]:
    paths = sorted((output_root / "performance").glob("product_render_timing_*.jsonl"))
    events: list[dict[str, Any]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events


def _wait_for_dispatch_end(
    output_root: Path,
    slug: str,
    *,
    timeout_s: float = 60.0,
) -> list[dict[str, Any]]:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        events = _trace_events(output_root)
        matching = [
            event
            for event in events
            if event.get("name") == "app.page_dispatch.end"
            and (
                str(event.get("page_slug") or "").strip().lower() == slug
                or str((event.get("meta") or {}).get("selected_slug") or "").strip().lower()
                == slug
            )
        ]
        if matching:
            rerun_seq = matching[-1].get("rerun_seq")
            return [event for event in events if event.get("rerun_seq") == rerun_seq]
        time.sleep(0.02)
    raise RuntimeError(f"timed out waiting for {slug} dispatch trace")


def _event_elapsed(events: list[dict[str, Any]], name: str) -> float | None:
    matches = [event for event in events if event.get("name") == name]
    return float(matches[-1].get("elapsed_ms")) if matches else None


def _elapsed_ms(started: float, completed: float | None) -> float | None:
    if completed is None:
        return None
    return round((float(completed) - float(started)) * 1000.0, 3)


def _event_duration(
    events: list[dict[str, Any]],
    start_name: str,
    end_name: str,
) -> float | None:
    start = _event_elapsed(events, start_name)
    end = _event_elapsed(events, end_name)
    return round(end - start, 3) if start is not None and end is not None else None


def _renderer_meta(events: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [event for event in events if event.get("name") == "app.result_page.renderer.end"]
    return dict(matches[-1].get("meta") or {}) if matches else {}


def _top_trace_deltas(events: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    ranked = sorted(
        events,
        key=lambda event: float(event.get("delta_ms") or 0.0),
        reverse=True,
    )
    return [
        {
            "name": str(event.get("name") or ""),
            "delta_ms": round(float(event.get("delta_ms") or 0.0), 3),
            "elapsed_ms": round(float(event.get("elapsed_ms") or 0.0), 3),
            **(
                {"meta": dict(event.get("meta") or {})}
                if event.get("meta")
                else {}
            ),
        }
        for event in ranked[:limit]
    ]


def _measurement_validity(
    message_types: dict[str, int],
    page_profiles: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    # Streamlit can deliver the initial session envelope after recording has
    # begun, even though the navigation still owns one script transaction.
    # Page profiles are the authoritative transaction count.
    if len(page_profiles) != 1:
        return False, "multiple_script_transactions"
    return True, None


def _terminate(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        # Streamlit can leave its Windows watcher child alive after the
        # launcher has exited.  Killing only the launcher makes later samples
        # compete with orphaned servers and invalidates cold timing evidence.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
            process.kill()
            process.wait(timeout=5)
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
        process.kill()
        process.wait(timeout=5)


def _single_run(
    root: Path,
    slug: str,
    port: int,
    run_index: int,
    *,
    mode: str,
    trace_enabled: bool,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"runtime-cold-{slug}-") as output_dir:
        output_root = Path(output_dir)
        environment = dict(os.environ)
        environment.update(
            {
                "BEAM_OUTPUTS_DIR": str(output_root),
                "CODEX_DISABLE_CALC_PAGE_WARMUP": "1",
            }
        )
        if trace_enabled:
            environment["CODEX_RENDER_TIMING_TRACE"] = "1"
        else:
            environment.pop("CODEX_RENDER_TIMING_TRACE", None)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.headless=true",
                "--server.fileWatcherType=none",
                f"--server.port={port}",
            ],
            cwd=root,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            boot_started = time.perf_counter()
            _wait_for_http(base_url)
            boot_ms = (time.perf_counter() - boot_started) * 1000.0
            with sync_playwright() as playwright:
                visible_tab_args = [
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ]
                try:
                    browser = playwright.chromium.launch(
                        headless=True,
                        args=visible_tab_args,
                    )
                except Exception:
                    browser = playwright.chromium.launch(
                        headless=True,
                        channel="msedge",
                        args=visible_tab_args,
                    )
                context = browser.new_context()
                page = context.new_page()
                cdp = context.new_cdp_session(page)
                cdp.send("Network.enable")
                websocket_traffic = {
                    "recording": False,
                    "last_observed_script_finished_at": None,
                    "first_recorded_frame_at": None,
                    "navigation_request_at": None,
                    "last_frame_at": time.perf_counter(),
                    "script_finished_at": None,
                    "received_bytes": 0,
                    "received_frames": 0,
                    "frame_sizes": [],
                    "opcodes": {},
                    "message_types": {},
                    "element_types": {},
                    "component_names": {},
                    "markdown_bodies": [],
                    "sent_message_types": {},
                    "rerun_requests": [],
                    "page_profiles": [],
                }

                def _record_websocket_frame(event: dict[str, Any]) -> None:
                    websocket_traffic["last_frame_at"] = time.perf_counter()
                    if not websocket_traffic["recording"]:
                        # Track completion of the shell transaction even while
                        # target-page traffic is intentionally not recorded.
                        # Streamlit may emit its profile after an otherwise
                        # quiet interval; waiting for script_finished prevents
                        # that delayed shell frame being counted as a second
                        # target-page transaction.
                        response = event.get("response") or {}
                        payload = str(response.get("payloadData") or "")
                        if str(response.get("opcode") or "") == "2" and payload:
                            try:
                                message = ForwardMsg()
                                message.ParseFromString(base64.b64decode(payload))
                                if str(message.WhichOneof("type") or "") == "script_finished":
                                    websocket_traffic["last_observed_script_finished_at"] = time.perf_counter()
                            except Exception:
                                pass
                        return
                    if websocket_traffic["first_recorded_frame_at"] is None:
                        websocket_traffic["first_recorded_frame_at"] = time.perf_counter()
                    response = event.get("response") or {}
                    payload = str(response.get("payloadData") or "")
                    payload_size = len(payload.encode("utf-8"))
                    websocket_traffic["received_bytes"] += payload_size
                    websocket_traffic["received_frames"] += 1
                    websocket_traffic["frame_sizes"].append(payload_size)
                    opcode = str(response.get("opcode") or "unknown")
                    opcodes = websocket_traffic["opcodes"]
                    opcodes[opcode] = int(opcodes.get(opcode, 0)) + 1
                    if opcode == "2" and payload:
                        try:
                            message = ForwardMsg()
                            message.ParseFromString(base64.b64decode(payload))
                            message_type = str(message.WhichOneof("type") or "unknown")
                            if message_type == "script_finished":
                                websocket_traffic["script_finished_at"] = time.perf_counter()
                            message_types = websocket_traffic["message_types"]
                            message_types[message_type] = int(message_types.get(message_type, 0)) + 1
                            if message_type == "page_profile":
                                websocket_traffic["page_profiles"].append(
                                    {
                                        "elapsed_ms": round(
                                            (time.perf_counter() - page_started) * 1000.0,
                                            3,
                                        ),
                                        "exec_time_s": round(
                                            float(message.page_profile.exec_time or 0.0),
                                            6,
                                        ),
                                        "prep_time_s": round(
                                            float(message.page_profile.prep_time or 0.0),
                                            6,
                                        ),
                                        "is_fragment_run": bool(
                                            message.page_profile.is_fragment_run
                                        ),
                                    }
                                )
                            if message_type == "delta":
                                delta_type = str(message.delta.WhichOneof("type") or "unknown")
                                element_type = delta_type
                                if delta_type == "new_element":
                                    element_type = str(message.delta.new_element.WhichOneof("type") or "unknown")
                                    if element_type == "markdown":
                                        websocket_traffic["markdown_bodies"].append(
                                            str(message.delta.new_element.markdown.body or "")
                                        )
                                    elif element_type == "component_instance":
                                        component_name = str(
                                            message.delta.new_element.component_instance.component_name
                                            or "unknown"
                                        )
                                        component_names = websocket_traffic["component_names"]
                                        component_names[component_name] = int(
                                            component_names.get(component_name, 0)
                                        ) + 1
                                element_types = websocket_traffic["element_types"]
                                element_types[element_type] = int(element_types.get(element_type, 0)) + 1
                        except Exception:
                            pass

                cdp.on("Network.webSocketFrameReceived", _record_websocket_frame)

                def _record_websocket_frame_sent(event: dict[str, Any]) -> None:
                    if not websocket_traffic["recording"]:
                        return
                    response = event.get("response") or {}
                    payload = str(response.get("payloadData") or "")
                    if str(response.get("opcode") or "") != "2" or not payload:
                        return
                    try:
                        message = BackMsg()
                        message.ParseFromString(base64.b64decode(payload))
                        message_type = str(message.WhichOneof("type") or "unknown")
                        sent_types = websocket_traffic["sent_message_types"]
                        sent_types[message_type] = int(sent_types.get(message_type, 0)) + 1
                        if message_type == "rerun_script":
                            if websocket_traffic["navigation_request_at"] is None:
                                websocket_traffic["navigation_request_at"] = time.perf_counter()
                            rerun = message.rerun_script
                            websocket_traffic["rerun_requests"].append(
                                {
                                    "elapsed_ms": round(
                                        (time.perf_counter() - page_started) * 1000.0,
                                        3,
                                    ),
                                    "query_string": str(rerun.query_string or ""),
                                    "widget_ids": [
                                        str(widget.id)
                                        for widget in rerun.widget_states.widgets
                                    ],
                                }
                            )
                    except Exception:
                        pass

                cdp.on("Network.webSocketFrameSent", _record_websocket_frame_sent)
                initial_slug = "start" if mode == "navigation" else slug
                # A repeated benchmark must never reopen project/session state
                # left by an earlier invocation.  The run number alone is not
                # unique across invocations, so give every isolated browser +
                # server pair its own project identity.
                cold_cid = f"cold-{slug}-{run_index}-{uuid4().hex}"
                url = f"{base_url}/?{urlencode({'page': initial_slug, 'fresh': '1', 'cid': cold_cid})}"
                if mode == "direct":
                    page_started = time.perf_counter()
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                if mode == "navigation":
                    page.get_by_role(
                        "heading",
                        name="Start your beam design",
                        exact=False,
                    ).first.wait_for(state="visible", timeout=60_000)
                    shell_finish_deadline = time.perf_counter() + 60.0
                    while (
                        websocket_traffic["last_observed_script_finished_at"] is None
                        and time.perf_counter() < shell_finish_deadline
                    ):
                        page.wait_for_timeout(10)
                    if websocket_traffic["last_observed_script_finished_at"] is None:
                        raise RuntimeError("timed out waiting for initial shell completion")
                    if trace_enabled:
                        _wait_for_dispatch_end(output_root, "start")
                    # The Start route contains independent fragments whose
                    # final deltas can arrive after the app-level dispatch
                    # marker.  Let the established shell finish painting
                    # before starting the target-page clock, otherwise those
                    # unrelated frames compete with and contaminate the cold
                    # navigation measurement.
                    page.evaluate(
                        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
                    )
                    shell_quiet_deadline = time.perf_counter() + 3.0
                    while time.perf_counter() < shell_quiet_deadline:
                        if time.perf_counter() - float(websocket_traffic["last_frame_at"]) >= 0.35:
                            break
                        page.wait_for_timeout(50)
                    page_started = time.perf_counter()
                    websocket_traffic["script_finished_at"] = None
                    websocket_traffic["page_profiles"] = []
                    websocket_traffic["recording"] = True
                    # Scope the click to the authoritative navigation control.
                    # Start-page content may contain the same exact page name;
                    # clicking the first document-wide text match measures an
                    # unrelated card/client delay rather than route latency.
                    page.get_by_role(
                        "radiogroup",
                        name="Navigation",
                    ).get_by_text(
                        PAGE_NAV_LABELS[slug],
                        exact=True,
                    ).click(timeout=30_000, force=True)
                title = PAGE_TITLES[slug]
                if mode == "direct":
                    websocket_traffic["recording"] = True
                page.get_by_role("heading", name=title, exact=False).first.wait_for(
                    state="visible",
                    timeout=60_000,
                )
                if trace_enabled:
                    events = _wait_for_dispatch_end(output_root, slug)
                else:
                    events = []
                    finish_deadline = time.perf_counter() + 60.0
                    while (
                        websocket_traffic["script_finished_at"] is None
                        and time.perf_counter() < finish_deadline
                    ):
                        page.wait_for_timeout(10)
                    if websocket_traffic["script_finished_at"] is None:
                        raise RuntimeError(
                            f"timed out waiting for {slug} script completion"
                        )
                paint_wait_started = time.perf_counter()
                page.evaluate(
                    "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
                )
                paint_wait_ms = (time.perf_counter() - paint_wait_started) * 1000.0
                navigation_started = (
                    websocket_traffic["navigation_request_at"] or page_started
                )
                page_open_ms = (time.perf_counter() - navigation_started) * 1000.0
                visibility_state = page.evaluate("() => document.visibilityState")
                websocket_traffic["recording"] = False
                error_count = page.locator("[data-testid='stException']").count()
                context.close()
                browser.close()
            renderer_meta = _renderer_meta(events)
            dispatch_start_elapsed = _event_elapsed(events, "app.page_dispatch.start")
            dispatch_end_elapsed = _event_elapsed(events, "app.page_dispatch.end")
            measurement_valid, measurement_invalid_reason = _measurement_validity(
                websocket_traffic["message_types"],
                websocket_traffic["page_profiles"],
            )
            return {
                "run": run_index,
                "mode": mode,
                "server_boot_ms": round(boot_ms, 3),
                "page_open_ms": round(page_open_ms, 3),
                "interaction_to_request_ms": _elapsed_ms(
                    page_started,
                    websocket_traffic["navigation_request_at"],
                ),
                "first_websocket_frame_ms": _elapsed_ms(
                    navigation_started,
                    websocket_traffic["first_recorded_frame_at"],
                ),
                "last_websocket_frame_ms": _elapsed_ms(
                    navigation_started,
                    websocket_traffic["last_frame_at"],
                ),
                "script_finished_frame_ms": _elapsed_ms(
                    navigation_started,
                    websocket_traffic["script_finished_at"],
                ),
                "post_dispatch_paint_wait_ms": round(paint_wait_ms, 3),
                "document_visibility_state": str(visibility_state),
                "dispatch_ms": _event_duration(
                    events,
                    "app.page_dispatch.start",
                    "app.page_dispatch.end",
                ),
                "rerun_to_dispatch_start_ms": dispatch_start_elapsed,
                "rerun_to_dispatch_end_ms": dispatch_end_elapsed,
                "workspace_ms": _event_duration(
                    events,
                    "app.result_page.workspace.start",
                    "app.result_page.workspace.end",
                ),
                "publication_ms": _event_duration(
                    events,
                    "app.result_page.publication.start",
                    "app.result_page.publication.end",
                ),
                "renderer_boundary_ms": _event_duration(
                    events,
                    "app.result_page.renderer.start",
                    "app.result_page.renderer.end",
                ),
                "module_import_ms": renderer_meta.get("import_ms"),
                "page_renderer_ms": renderer_meta.get("render_ms"),
                "module_was_loaded": renderer_meta.get("module_was_loaded"),
                "exception_count": int(error_count),
                "websocket_received_bytes": int(websocket_traffic["received_bytes"]),
                "websocket_received_frames": int(websocket_traffic["received_frames"]),
                "websocket_frame_size_p50": int(statistics.median(websocket_traffic["frame_sizes"])) if websocket_traffic["frame_sizes"] else 0,
                "websocket_frame_size_max": int(max(websocket_traffic["frame_sizes"])) if websocket_traffic["frame_sizes"] else 0,
                "websocket_opcodes": dict(websocket_traffic["opcodes"]),
                "websocket_message_types": dict(websocket_traffic["message_types"]),
                "websocket_element_types": dict(websocket_traffic["element_types"]),
                "websocket_component_names": dict(websocket_traffic["component_names"]),
                "websocket_sent_message_types": dict(
                    websocket_traffic["sent_message_types"]
                ),
                "websocket_rerun_requests": list(websocket_traffic["rerun_requests"]),
                "websocket_page_profiles": list(websocket_traffic["page_profiles"]),
                # A navigation measurement owns exactly one Streamlit script
                # transaction. Multiple page profiles mean another script
                # completed while the clock was running. Keep that
                # infrastructure event visible, but do not misreport it as
                # calculation-page execution time.
                "measurement_valid": measurement_valid,
                "measurement_invalid_reason": measurement_invalid_reason,
                "markdown_total_chars": sum(
                    len(body) for body in websocket_traffic["markdown_bodies"]
                ),
                "markdown_unique_bodies": len(set(websocket_traffic["markdown_bodies"])),
                "markdown_duplicate_count": len(websocket_traffic["markdown_bodies"])
                - len(set(websocket_traffic["markdown_bodies"])),
                "duplicate_markdown_bodies": [
                    {
                        "count": count,
                        "chars": len(body),
                        "prefix": " ".join(body[:160].split()),
                    }
                    for body, count in Counter(
                        websocket_traffic["markdown_bodies"]
                    ).most_common()
                    if count > 1
                ],
                "largest_markdown_bodies": [
                    {
                        "chars": len(body),
                        "prefix": " ".join(body[:120].split()),
                    }
                    for body in sorted(
                        set(websocket_traffic["markdown_bodies"]),
                        key=len,
                        reverse=True,
                    )[:10]
                ],
                "top_trace_deltas": _top_trace_deltas(events),
            }
        finally:
            _terminate(process)


def _summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(run["page_open_ms"]) for run in runs]
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(round(0.95 * len(ordered) + 0.5)) - 1))
    return {
        "median_page_open_ms": round(statistics.median(values), 3),
        "p95_page_open_ms": round(ordered[p95_index], 3),
        "worst_page_open_ms": round(max(values), 3),
        "all_under_1000_ms": all(value < 1000.0 for value in values),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--page", action="append", choices=PAGES)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument(
        "--mode",
        choices=("navigation", "direct"),
        default="navigation",
        help="navigation warms only the shared shell before clicking a cold page; direct includes first browser-session setup",
    )
    parser.add_argument("--starting-port", type=int, default=8600)
    parser.add_argument(
        "--max-invalid-attempts",
        type=int,
        default=10,
        help="maximum websocket/session reconnect samples retried per page",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="measure the production path without diagnostic timing instrumentation",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.max_invalid_attempts < 0:
        parser.error("--max-invalid-attempts cannot be negative")

    root = args.root.resolve()
    pages = tuple(args.page or PAGES)
    report: dict[str, Any] = {
        "definition": (
            "fresh server and browser; shared shell established before click; target page unvisited, page caches cold and background page warm-up disabled"
            if args.mode == "navigation"
            else "fresh server process and browser session; server ready before direct page timer; target module and page caches cold"
        ),
        "mode": args.mode,
        "root": str(root),
        "pages": {},
    }
    port = int(args.starting_port)
    for slug in pages:
        runs: list[dict[str, Any]] = []
        invalid_attempts: list[dict[str, Any]] = []
        attempt_index = 0
        while len(runs) < int(args.runs):
            attempt_index += 1
            try:
                sample = _single_run(
                    root,
                    slug,
                    port,
                    attempt_index,
                    mode=args.mode,
                    trace_enabled=not args.no_trace,
                )
            except Exception as exc:
                sample = {
                    "run": attempt_index,
                    "mode": args.mode,
                    "measurement_valid": False,
                    "measurement_invalid_reason": "browser_or_server_setup_failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            port += 1
            if bool(sample.get("measurement_valid", True)):
                sample["run"] = len(runs) + 1
                sample["attempt"] = attempt_index
                runs.append(sample)
                continue
            invalid_attempts.append(sample)
            if len(invalid_attempts) > int(args.max_invalid_attempts):
                raise RuntimeError(
                    f"{slug} exceeded --max-invalid-attempts while collecting "
                    f"{args.runs} valid cold measurements"
                )
        report["pages"][slug] = {
            "runs": runs,
            "invalid_attempts": invalid_attempts,
            "summary": {
                **_summary(runs),
                "valid_runs": len(runs),
                "invalid_attempt_count": len(invalid_attempts),
            },
        }

    encoded = json.dumps(report, indent=2)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
