from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_sources(source: str, name: str) -> list[tuple[str, int, int, int]]:
    tree = ast.parse(source)
    lines = source.splitlines()
    matches: list[tuple[str, int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            matches.append(("\n".join(lines[start - 1 : end]), end - start + 1, start, end))
    return matches


def _largest_function_source(source: str, name: str) -> tuple[str, int, int, int]:
    matches = _function_sources(source, name)
    if not matches:
        return "", 0, 0, 0
    return max(matches, key=lambda item: item[1])


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_tail_perf_debug_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_tail_perf_debug_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_modules" / "performance.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size, coordinator_start, coordinator_end = (
        _largest_function_source(source, "render_inputs_perf_finalization_current_coordinator")
    )
    render_inputs_source, render_inputs_size, _, _ = _largest_function_source(
        route_source,
        "render_inputs_tail_current_coordinator",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("tail_perf_debug_coordinator_missing")
    if coordinator_size > 90:
        failures.append(f"tail_perf_debug_coordinator_too_large:{coordinator_size}")

    for required in [
        "section_times = []",
        "sub_section_times = []",
        "st.session_state[\"_perf_log\"]",
        "\"inputs_render_perf\"",
        "\"Show performance debug\"",
        "st.caption(f\"Inputs render:",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    for forbidden in [
        "render_timingmark_fn(",
        "_update_user_latency_metrics(",
    ]:
        if forbidden in coordinator_source:
            failures.append(f"coordinator_retains_old_local_{forbidden}")

    for required in [
        "render_inputs_perf_finalization_current_coordinator(",
        "inputs_render_audit=inputs_render_audit",
        "before_state=before_state",
        "mark(\"end\")",
        "perf_start=perf_start",
        "perf_marks=perf_marks",
        "sub_marks=sub_marks",
        "t0=t0",
    ]:
        if required not in render_inputs_source:
            failures.append(f"tail_current_call_missing_{required}")

    for stale in [
        "section_times = []",
        "sub_section_times = []",
        "st.session_state[\"_perf_log\"]",
        "\"inputs_render_perf\"",
        "\"Show performance debug\"",
        "st.caption(f\"Inputs render:",
    ]:
        if stale in render_inputs_source:
            failures.append(f"tail_current_still_owns_{stale}")
    if "render_inputs_perf_finalization_current_coordinator(" in shell_source:
        failures.append("shell_still_calls_perf_finalization_directly")
    route_function_source, _, _, _ = _largest_function_source(
        route_source,
        "render_inputs_perf_finalization_current_coordinator",
    )
    if route_function_source:
        failures.append("route_still_defines_perf_finalization")

    payload = {
        "verifier": "inputs_page_tail_perf_debug_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "coordinator_lines": [coordinator_start, coordinator_end],
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Tail Perf Debug Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"`render_inputs` size: `{render_inputs_size}`",
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
