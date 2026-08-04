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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_pre_widget_terminal_context_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_pre_widget_terminal_context_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_guide_pre_widget_terminal_context_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_guide_pre_widget_terminal_context_coordinator_missing")
    if coordinator_size > 30:
        failures.append(f"design_guide_pre_widget_terminal_context_coordinator_too_large:{coordinator_size}")
    for required in [
        "pre_widget_terminal_rendered_from_apply_route = False",
        "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
        "_shared_state_snapshot()",
        'st.session_state.get("_solver_result")',
        "_post_apply_combined_terminal_solver_result_ready()",
        "_post_apply_combined_chained_terminal_recent_refresh_ready(",
        "pre_widget_terminal_should_render = bool(",
        "return (",
        "pre_widget_terminal_should_render",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_design_guide_pre_widget_terminal_context_coordinator()",
        "_pre_widget_terminal_should_render",
        "if _pre_widget_terminal_should_render:",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        "_pre_widget_terminal_rendered_from_apply_route = False",
        "_pre_widget_terminal_solver_ready =",
        "_post_apply_combined_chained_terminal_recent_refresh_ready(",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_pre_widget_terminal_context_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Pre-Widget Terminal Context Coordinator Verifier",
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
