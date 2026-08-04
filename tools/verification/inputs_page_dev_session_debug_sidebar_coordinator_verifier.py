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
    json_path = ARTIFACT_DIR / f"inputs_page_dev_session_debug_sidebar_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_dev_session_debug_sidebar_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    module_source = (
        ROOT / "inputs_page_modules" / "session" / "dev_debug_sidebar.py"
    ).read_text(encoding="utf-8", errors="ignore")
    source = inputs_source + "\n" + route_source
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_dev_session_debug_sidebar_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs_page_setup_current_coordinator")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("dev_session_debug_sidebar_coordinator_missing")
    if coordinator_size > 90:
        failures.append(f"dev_session_debug_sidebar_coordinator_too_large:{coordinator_size}")
    if "render_inputs_dev_session_debug_sidebar_module(" not in coordinator_source:
        failures.append("dev_session_debug_sidebar_coordinator_not_delegating_to_session_module")
    for required in [
        "Design Guide Debug",
        "Debug session state",
        "Inputs summary state debug",
    ]:
        if required not in module_source:
            failures.append(f"session_module_missing_{required}")
        if required in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{required}")

    before_state_index = render_inputs_source.find("before_state = inputs_audit_snapshot_state()")
    call_index = render_inputs_source.find("render_inputs_dev_session_debug_sidebar_coordinator(")
    summary_container_index = render_inputs_source.find("summary_container = create_summary_container()")
    if call_index < 0:
        failures.append("render_inputs_missing_dev_session_debug_sidebar_call")
    if not (before_state_index >= 0 and before_state_index < call_index < summary_container_index):
        failures.append(
            "dev_session_debug_sidebar_call_order_changed:"
            f"before_state={before_state_index}:call={call_index}:summary_container={summary_container_index}"
        )

    payload = {
        "verifier": "inputs_page_dev_session_debug_sidebar_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Dev Session Debug Sidebar Coordinator Verifier",
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
