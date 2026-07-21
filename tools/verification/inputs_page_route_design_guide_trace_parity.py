from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


@contextmanager
def _patched_env(values: dict[str, str | None]):
    originals = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in originals.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _normalised_trace_row(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1:
        raise AssertionError(f"expected one trace row in {path}, got {len(rows)}")
    row = rows[0]
    return {
        "run_id": row.get("run_id"),
        "event": row.get("event"),
        "source": row.get("source"),
        "data": row.get("data"),
        "timestamp_present": bool(row.get("timestamp")),
        "timestamp_ms_type": type(row.get("timestamp_ms")).__name__,
    }


def _run_append(module: Any, path: Path) -> dict[str, Any]:
    debug_calls: list[tuple[Any, ...]] = []
    original_debug = getattr(module, "_agent_debug_log", None)
    try:
        if original_debug is not None:
            module._agent_debug_log = lambda *args, **kwargs: debug_calls.append((args, kwargs))
        with _patched_env({"DESIGN_GUIDE_TRACE_PATH": str(path), "DESIGN_GUIDE_TRACER_VERBOSE": None}):
            if hasattr(module, "_append_design_guide_trace"):
                module._append_design_guide_trace(
                    "trace_event",
                    {"value": 3, "nested": {"ok": True}},
                    run_id="run-1",
                    source="trace_parity",
                )
            else:
                module.append_design_guide_trace(
                    "trace_event",
                    {"value": 3, "nested": {"ok": True}},
                    run_id="run-1",
                    source="trace_parity",
                )
        return {"row": _normalised_trace_row(path), "debug_calls": debug_calls}
    finally:
        if original_debug is not None:
            module._agent_debug_log = original_debug


def _run_bad_path(module: Any, bad_path: Path) -> dict[str, Any]:
    debug_calls: list[tuple[Any, ...]] = []
    original_debug = getattr(module, "_agent_debug_log", None)
    try:
        if original_debug is not None:
            module._agent_debug_log = lambda *args, **kwargs: debug_calls.append((args, kwargs))
        with _patched_env({"DESIGN_GUIDE_TRACE_PATH": str(bad_path), "DESIGN_GUIDE_TRACER_VERBOSE": "1"}):
            if hasattr(module, "_append_design_guide_trace"):
                module._append_design_guide_trace(
                    "bad_path_event",
                    {"value": "x"},
                    run_id="run-bad",
                    source="trace_parity",
                )
            else:
                module.append_design_guide_trace(
                    "bad_path_event",
                    {"value": "x"},
                    run_id="run-bad",
                    source="trace_parity",
                    agent_debug_log_fn=lambda *args, **kwargs: debug_calls.append((args, kwargs)),
                )
        return {
            "raised": False,
            "debug_messages": [str(call[0][0]) if call and call[0] else "" for call in debug_calls],
            "debug_count": len(debug_calls),
        }
    except Exception as exc:
        return {"raised": True, "exception": repr(exc), "debug_count": len(debug_calls)}
    finally:
        if original_debug is not None:
            module._agent_debug_log = original_debug


def main() -> int:
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_route_design_guide_trace_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_route_design_guide_trace_parity_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    import inputs_page_route_coordinators as route
    from inputs_page_modules.design_guide import trace as trace_module

    failures: list[str] = []
    comparisons: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as td:
        temp_root = Path(td)
        override_path = temp_root / "override.jsonl"
        with _patched_env({"DESIGN_GUIDE_TRACE_PATH": str(override_path)}):
            comparisons["path_override"] = {
                "module": trace_module.design_guide_tracer_path(),
                "route": route._design_guide_tracer_path(),
            }
        if comparisons["path_override"]["module"] != comparisons["path_override"]["route"]:
            failures.append("path_override_changed")

        for value in (None, "1", "true", "yes", "on", "0", "false"):
            with _patched_env({"DESIGN_GUIDE_TRACER_VERBOSE": value}):
                comparisons[f"verbose_{value}"] = {
                    "module": trace_module.design_guide_tracer_verbose_log(),
                    "route": route._design_guide_tracer_verbose_log(),
                }
            if comparisons[f"verbose_{value}"]["module"] != comparisons[f"verbose_{value}"]["route"]:
                failures.append(f"verbose_changed_{value}")

        legacy_append = _run_append(trace_module, temp_root / "module" / "trace.jsonl")
        route_append = _run_append(route, temp_root / "route" / "trace.jsonl")
        comparisons["append"] = {"module": legacy_append, "route": route_append}
        if legacy_append != route_append:
            failures.append("append_row_changed")

        blocker = temp_root / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        legacy_bad = _run_bad_path(trace_module, blocker / "trace.jsonl")
        route_bad = _run_bad_path(route, blocker / "trace.jsonl")
        comparisons["bad_path"] = {"module": legacy_bad, "route": route_bad}
        if bool(legacy_bad.get("raised")) or bool(route_bad.get("raised")):
            failures.append("bad_path_raised")
        if legacy_bad.get("debug_messages") != route_bad.get("debug_messages"):
            failures.append("bad_path_debug_messages_changed")

    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    module_source = (
        ROOT / "inputs_page_modules" / "design_guide" / "trace.py"
    ).read_text(encoding="utf-8", errors="ignore")
    if "append_design_guide_trace_module(" not in route_source:
        failures.append("route_append_trace_missing_module_delegate")
    if "design_guide_tracer_path_module()" not in route_source:
        failures.append("route_tracer_path_missing_module_delegate")
    for forbidden in ("import streamlit", "from streamlit", "import inputs_page", "from inputs_page", "st."):
        if forbidden in module_source:
            failures.append(f"module_forbidden_{forbidden}")

    payload = {
        "verifier": "inputs_page_route_design_guide_trace_parity",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "comparisons": comparisons,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Route Design Guide Trace Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Failures: `{len(failures)}`",
                "",
                "## Cases",
                "",
                *(f"- `{name}`" for name in comparisons),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
