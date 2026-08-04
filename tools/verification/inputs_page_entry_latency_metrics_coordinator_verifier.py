from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    matches: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            size = node.end_lineno - node.lineno + 1
            matches.append((size, node.lineno, node.end_lineno))
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_entry_latency_metrics_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_entry_latency_metrics_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_entry_latency_metrics_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("entry_latency_metrics_coordinator_missing")
    if coordinator_size > 55:
        failures.append(f"entry_latency_metrics_coordinator_too_large:{coordinator_size}")
    for required in [
        "selected_page_slug",
        "render_started_timestamp_ms",
        "page_dispatch_to_inputs_entry_ms",
        "browser_test_mode",
        "_bending_fail_valid_repair_cta_published",
        "render_inputs.enter",
        "inputs_page.entry",
        "return bool(browser_test_mode_for_latency)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for stale in [
        "_page_dispatch_started_perf",
        'render_timing_mark("inputs_page.entry")',
        '_inputs_pre_widget_trace("render_inputs.enter")',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    call_index = render_inputs_source.find(
        "_browser_test_mode_for_latency = render_inputs_entry_latency_metrics_coordinator("
    )
    init_index = render_inputs_source.find("init_shared_session_state()")
    update_fn_index = render_inputs_source.find("def _update_user_latency_metrics")
    if call_index < 0:
        failures.append("render_inputs_missing_entry_latency_metrics_call")
    if not (update_fn_index >= 0 and update_fn_index < call_index < init_index):
        failures.append(
            "entry_latency_metrics_call_order_changed:"
            f"update_fn={update_fn_index}:call={call_index}:init={init_index}"
        )

    payload = {
        "verifier": "inputs_page_entry_latency_metrics_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Entry Latency Metrics Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
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
