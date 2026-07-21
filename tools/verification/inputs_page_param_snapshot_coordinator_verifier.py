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
    json_path = ARTIFACT_DIR / f"inputs_page_param_snapshot_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_param_snapshot_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_param_snapshot_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")
    setup_source, _ = _function_source(source, "render_inputs_page_setup_current_coordinator")
    setup_owner_source = setup_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("param_snapshot_coordinator_missing")
    if coordinator_size > 12:
        failures.append(f"param_snapshot_coordinator_too_large:{coordinator_size}")
    for required in [
        "params = {k: st.session_state.get(k) for k in st.session_state.keys()}",
        "def fast_get_param(key, default=None):",
        "return params.get(key, default)",
        "return params, fast_get_param",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "PARAMS, fast_get_param = render_inputs_param_snapshot_coordinator()"
    if call_text not in setup_owner_source:
        failures.append("render_inputs_missing_param_snapshot_call")
    for stale in [
        "PARAMS = {k: st.session_state.get(k) for k in st.session_state.keys()}",
        "def fast_get_param(key, default=None):",
        "return PARAMS.get(key, default)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    hydrate_trace_index = setup_owner_source.find('_inputs_hydration_trace_log("render_inputs_entry"')
    params_call_index = setup_owner_source.find(call_text)
    perf_call_index = setup_owner_source.find("render_inputs_perf_marker_setup_coordinator(ss=ss)")
    if not (0 <= hydrate_trace_index < params_call_index < perf_call_index):
        failures.append(
            "param_snapshot_call_order_changed:"
            f"hydrate={hydrate_trace_index}:params={params_call_index}:perf={perf_call_index}"
        )

    payload = {
        "verifier": "inputs_page_param_snapshot_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Param Snapshot Coordinator Verifier",
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
