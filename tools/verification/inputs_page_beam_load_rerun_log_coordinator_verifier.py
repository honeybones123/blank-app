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
    json_path = ARTIFACT_DIR / f"inputs_page_beam_load_rerun_log_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_beam_load_rerun_log_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_beam_load_triggered_rerun_log_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("beam_load_rerun_log_coordinator_missing")
    if coordinator_size > 15:
        failures.append(f"beam_load_rerun_log_coordinator_too_large:{coordinator_size}")
    for required in [
        "session_state_final_log",
        "append_session_state_final_log",
        "beam_load_triggered_rerun",
        '"hydration_layer": "render_inputs"',
        "ssl_record_rerun_trigger",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    if "def _log_beam_load_triggered_rerun" in render_inputs_source:
        failures.append("render_inputs_still_defines_nested_beam_load_logger")
    call_count = render_inputs_source.count("render_inputs_beam_load_triggered_rerun_log_coordinator(")
    if call_count < 6:
        failures.append(f"render_inputs_beam_load_logger_call_count_low:{call_count}")

    context_index = render_inputs_source.find("beam_labels = _beam_option_labels()")
    first_call_index = render_inputs_source.find("render_inputs_beam_load_triggered_rerun_log_coordinator(")
    if not (0 <= context_index < first_call_index):
        failures.append(
            "beam_load_logger_call_order_changed:"
            f"context={context_index}:first_call={first_call_index}"
        )

    payload = {
        "verifier": "inputs_page_beam_load_rerun_log_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "call_count": call_count,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Beam Load Rerun Log Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Call count: `{call_count}`",
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
