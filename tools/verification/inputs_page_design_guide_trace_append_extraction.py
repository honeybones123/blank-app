"""Verify Design Guide trace append extraction from the app bridge."""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "trace.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "_append_design_guide_trace")
    module_node = _function_node(module_source, "append_design_guide_trace")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""

    from inputs_page_modules.design_guide import trace as trace_module
    import inputs_page_app_contract_bridge as bridge

    with tempfile.TemporaryDirectory() as tmp:
        trace_path = Path(tmp) / "trace.jsonl"
        trace_module.append_design_guide_trace(
            "event_a",
            {"value": 3},
            run_id="run_a",
            source="unit",
            tracer_path_fn=lambda: str(trace_path),
        )
        rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

        original = bridge._append_design_guide_trace_extracted
        delegate_call: dict[str, Any] = {}

        def _fake_extracted(event: str, data: dict, **kwargs: Any) -> None:
            delegate_call.update(
                {
                    "event": event,
                    "data": dict(data),
                    "run_id": kwargs.get("run_id"),
                    "source": kwargs.get("source"),
                    "path_matches": kwargs.get("tracer_path_fn") is bridge._design_guide_tracer_path,
                    "verbose_matches": kwargs.get("tracer_verbose_log_fn") is bridge._design_guide_tracer_verbose_log,
                    "debug_matches": kwargs.get("agent_debug_log_fn") is bridge._agent_debug_log,
                    "append_failure_location": kwargs.get("append_failure_location"),
                }
            )

        try:
            bridge._append_design_guide_trace_extracted = _fake_extracted
            bridge._append_design_guide_trace(
                "bridge_event",
                {"bridge": True},
                run_id="bridge_run",
                source="bridge_source",
            )
        finally:
            bridge._append_design_guide_trace_extracted = original

        failure_parent = Path(tmp) / "not_a_directory"
        failure_parent.write_text("blocker", encoding="utf-8")
        failure_path = failure_parent / "trace.jsonl"
        debug_calls: list[dict[str, Any]] = []

        def _debug_log(message: str, data: dict | None = None, **kwargs: Any) -> None:
            debug_calls.append(
                {
                    "message": message,
                    "data": dict(data or {}),
                    "location": kwargs.get("location"),
                    "hypothesis_id": kwargs.get("hypothesis_id"),
                }
            )

        trace_module.append_design_guide_trace(
            "failure_event",
            {"failure": True},
            run_id="failure_run",
            source="unit",
            tracer_path_fn=lambda: str(failure_path),
            tracer_verbose_log_fn=lambda: True,
            agent_debug_log_fn=_debug_log,
            append_failure_location="inputs_page.py:_append_design_guide_trace",
        )

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 18,
        "bridge_delegates_to_trace_module": "_append_design_guide_trace_extracted" in bridge_body,
        "bridge_preserves_legacy_callbacks": all(
            delegate_call.get(key) is True
            for key in ("path_matches", "verbose_matches", "debug_matches")
        ),
        "bridge_preserves_legacy_debug_location": delegate_call.get("append_failure_location")
        == "inputs_page.py:_append_design_guide_trace",
        "bridge_delegates_arguments": delegate_call.get("event") == "bridge_event"
        and delegate_call.get("data") == {"bridge": True}
        and delegate_call.get("run_id") == "bridge_run"
        and delegate_call.get("source") == "bridge_source",
        "module_contains_recovery_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 75,
        "module_keeps_append_failure_location_parameter": "append_failure_location" in module_source,
        "module_append_writes_jsonl": len(rows) == 1
        and rows[0]["run_id"] == "run_a"
        and rows[0]["event"] == "event_a"
        and rows[0]["source"] == "unit"
        and rows[0]["data"] == {"value": 3}
        and isinstance(rows[0].get("timestamp_ms"), int),
        "module_failure_debug_uses_injected_location": bool(debug_calls)
        and debug_calls[-1].get("location") == "inputs_page.py:_append_design_guide_trace"
        and debug_calls[-1].get("hypothesis_id") == "H_DG_TRACER_APPEND",
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_design_guide_trace_append_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_design_guide_trace_append_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Trace Append Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {check}: {'PASS' if passed else 'FAIL'}" for check, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
