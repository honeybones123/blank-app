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
            matches.append((node.end_lineno - node.lineno + 1, node.lineno, node.end_lineno))
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_perf_marker_setup_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_perf_marker_setup_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_modules" / "performance.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_perf_marker_setup_coordinator",
    )
    render_inputs_source, _ = _function_source(route_source, "render_inputs_page_setup_current_coordinator")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("perf_marker_setup_coordinator_missing")
    if coordinator_size > 20:
        failures.append(f"perf_marker_setup_coordinator_too_large:{coordinator_size}")
    for required in [
        "t0 = time.perf_counter()",
        'if "_perf_log" not in ss:',
        'ss["_perf_log"] = []',
        "perf_start = time.perf_counter()",
        "perf_marks = []",
        "sub_marks = []",
        "def mark(label):",
        "def sub_mark(label):",
        "return t0, perf_start, perf_marks, sub_marks, mark, sub_mark",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "_t0, _perf_start, _perf_marks, _sub_marks, _mark, _sub_mark ="
    if call_text not in render_inputs_source:
        failures.append("page_setup_missing_perf_marker_tuple_assignment")
    if "render_inputs_perf_marker_setup_coordinator(ss=ss)" not in render_inputs_source:
        failures.append("page_setup_missing_perf_marker_setup_call")
    for stale in [
        'if "_perf_log" not in ss:',
        "def _mark(label):",
        "def _sub_mark(label):",
    ]:
        if stale in render_inputs_source:
            failures.append(f"page_setup_still_owns_{stale}")
    if "render_inputs_perf_marker_setup_coordinator(" in shell_source:
        failures.append("shell_still_calls_perf_marker_setup_directly")
    route_function_source, _ = _function_source(route_source, "render_inputs_perf_marker_setup_coordinator")
    if route_function_source:
        failures.append("route_still_defines_perf_marker_setup")

    payload = {
        "verifier": "inputs_page_perf_marker_setup_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Perf Marker Setup Coordinator Verifier",
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
