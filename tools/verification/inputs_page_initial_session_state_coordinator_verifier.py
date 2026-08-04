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
    json_path = ARTIFACT_DIR / f"inputs_page_initial_session_state_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_initial_session_state_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_initial_session_state_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")
    setup_source, _ = _function_source(source, "render_inputs_page_setup_current_coordinator")
    setup_owner_source = setup_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("initial_session_state_coordinator_missing")
    if coordinator_size > 25:
        failures.append(f"initial_session_state_coordinator_too_large:{coordinator_size}")
    for required in [
        "init_shared_session_state()",
        "RESULT_CACHE_KEY",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for stale in [
        "init_shared_session_state()",
        "if RESULT_CACHE_KEY not in ss:",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    init_call_index = setup_owner_source.find("render_inputs_initial_session_state_coordinator(")
    hydrate_trace_index = setup_owner_source.find('_inputs_hydration_trace_log("render_inputs_entry"')
    params_index = setup_owner_source.find("PARAMS, fast_get_param = render_inputs_param_snapshot_coordinator()")
    if init_call_index < 0:
        failures.append("render_inputs_missing_initial_session_state_call")
    if not (0 <= init_call_index < hydrate_trace_index < params_index):
        failures.append(
            "initial_session_state_call_order_changed:"
            f"init={init_call_index}:hydrate={hydrate_trace_index}:params={params_index}"
        )

    payload = {
        "verifier": "inputs_page_initial_session_state_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Initial Session State Coordinator Verifier",
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
