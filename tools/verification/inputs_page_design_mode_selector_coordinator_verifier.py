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
    json_path = ARTIFACT_DIR / f"inputs_page_design_mode_selector_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_mode_selector_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_mode_selector_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_mode_selector_coordinator_missing")
    if coordinator_size > 35:
        failures.append(f"design_mode_selector_coordinator_too_large:{coordinator_size}")
    for required in [
        "st.columns([8, 1], gap=\"small\", vertical_alignment=\"top\")",
        "seed_widget_from_shared(\"inputs_detailed_mode_toggle\", \"inputs_detailed_mode\", False)",
        "v2_radio(",
        "key=\"inputs_detailed_mode_toggle\"",
        "_shared_state_snapshot()",
        "info_i_button(",
        "_render_design_optimisation_inputs(sync_callbacks)",
        "return bool(inputs_detailed_mode)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "inputs_detailed_mode = render_inputs_design_mode_selector_coordinator("
    if call_text not in render_inputs_source:
        failures.append("render_inputs_missing_design_mode_selector_call")
    for stale in [
        "top_dm_l, top_dm_r = st.columns([8, 1], gap=\"small\", vertical_alignment=\"top\")",
        "seed_widget_from_shared(\"inputs_detailed_mode_toggle\", \"inputs_detailed_mode\", False)",
        "key=\"inputs_detailed_mode_toggle\"",
        "_render_design_optimisation_inputs(sync_callbacks)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    beam_mark_index = render_inputs_source.find('_mark("beam_manager")')
    call_index = render_inputs_source.find(call_text)
    top_section_index = render_inputs_source.find("# 1. Top section layout")
    if not (0 <= beam_mark_index < call_index < top_section_index):
        failures.append(
            "design_mode_selector_call_order_changed:"
            f"beam_mark={beam_mark_index}:call={call_index}:top_section={top_section_index}"
        )

    payload = {
        "verifier": "inputs_page_design_mode_selector_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Mode Selector Coordinator Verifier",
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
