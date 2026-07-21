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
    if matches:
        size, start, end = max(matches, key=lambda item: item[0])
        lines = source.splitlines()
        return "\n".join(lines[start - 1 : end]), size
    return "", 0


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_dev_audit_sidebar_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_dev_audit_sidebar_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_dev_audit_and_sidebar_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("dev_audit_sidebar_coordinator_missing")
    if coordinator_size > 70:
        failures.append(f"dev_audit_sidebar_coordinator_too_large:{coordinator_size}")
    for required in [
        "Inputs dev render audit (end of render_inputs)",
        "STATE CHANGED DURING RENDER",
        "WARNING: DIRECT SHARED WRITE",
        "design_guide_page.render_debug_sidebar",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
        if required in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{required}")

    call_index = render_inputs_source.find("render_inputs_dev_audit_and_sidebar_coordinator(")
    auto_design_index = render_inputs_source.find("handle_auto_design()")
    mark_end_index = render_inputs_source.rfind('_mark("end")')
    if call_index < 0:
        failures.append("render_inputs_missing_dev_audit_sidebar_call")
    if not (auto_design_index >= 0 and auto_design_index < call_index < mark_end_index):
        failures.append(
            "dev_audit_sidebar_call_order_changed:"
            f"auto_design={auto_design_index}:call={call_index}:mark_end={mark_end_index}"
        )

    payload = {
        "verifier": "inputs_page_dev_audit_sidebar_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Dev Audit Sidebar Coordinator Verifier",
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
