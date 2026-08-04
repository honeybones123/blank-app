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
    json_path = ARTIFACT_DIR / f"inputs_page_first_paint_summary_shell_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_first_paint_summary_shell_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_first_paint_summary_shell_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("first_paint_summary_shell_coordinator_missing")
    if coordinator_size > 160:
        failures.append(f"first_paint_summary_shell_coordinator_too_large:{coordinator_size}")
    for required in [
        "inputs_show_landing_dashboard()",
        "summary_container = st.empty()",
        "st.title(\"Inputs\")",
        "render_inputs_cached_summary_html_for_first_paint_coordinator",
        "\"summary.first_paint_cached_html_reuse\"",
        "data-testid=\"inputs-first-paint-cached-summary\"",
        "Preparing current summary...",
        "\"inputs_page.first_visible_inputs_marker_emitted\"",
        "update_user_latency_metrics_fn(first_visible_inputs_marker_ms=first_inputs_marker_ms)",
        "return summary_container",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "summary_container = render_inputs_first_paint_summary_shell_coordinator("
    if call_text not in render_inputs_source:
        failures.append("render_inputs_missing_first_paint_summary_shell_call")
    call_index = render_inputs_source.find(call_text)
    batch_index = render_inputs_source.find("render_inputs_batch_design_context_coordinator(ss=ss)")
    if not (0 <= call_index < batch_index):
        failures.append(f"first_paint_call_order_changed:call={call_index}:batch={batch_index}")
    for stale in [
        "_first_paint_landing_expected",
        "_first_paint_shell_html",
        "_first_inputs_marker_ms",
        "\"summary.first_paint_cached_html_reuse\"",
        "Preparing current summary...",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_first_paint_summary_shell_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page First-Paint Summary Shell Coordinator Verifier",
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
