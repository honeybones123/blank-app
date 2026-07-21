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
            matches.append((node.end_lineno - node.lineno + 1, node.end_lineno))
    if not matches:
        return "", 0
    size, end = max(matches, key=lambda item: item[0])
    start = end - size + 1
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_pre_widget_gate_setup_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_pre_widget_gate_setup_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_guide_pre_widget_gate_setup_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_guide_pre_widget_gate_setup_coordinator_missing")
    if coordinator_size > 45:
        failures.append(f"design_guide_pre_widget_gate_setup_coordinator_too_large:{coordinator_size}")
    for required in [
        "inputs_has_design_actions_or_loads()",
        "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
        "_design_guide_pre_slot_publication_eligibility_probe",
        "should_render_design_guide_slot_from_publication_eligibility",
        "browser_test_mode=bool(browser_test_mode_for_latency)",
        'dg_render_gate_decision.get("should_render_design_guide_slot")',
        "design_guide_slot = None",
        "dg_final_panel_rendered_pre_widgets = False",
        "dg_defer_final_panel_until_fresh_render = True",
        "defer_design_guide_slot_until_after_widgets = False",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for returned in [
        "inputs_has_design_actions_or_loads_for_dg",
        "dg_render_gate_bundle",
        "dg_pre_slot_publication_probe",
        "dg_render_gate_decision",
        "show_design_guide_for_current_inputs",
        "design_guide_slot",
        "dg_final_panel_rendered_pre_widgets",
        "dg_defer_final_panel_until_fresh_render",
        "defer_design_guide_slot_until_after_widgets",
    ]:
        if returned not in coordinator_source:
            failures.append(f"coordinator_return_missing_{returned}")
    if "render_inputs_design_guide_pre_widget_gate_setup_coordinator(" not in render_inputs_source:
        failures.append("render_inputs_missing_design_guide_pre_widget_gate_setup_call")
    for stale in [
        "_dg_render_gate_debug =",
        "_design_guide_pre_slot_publication_eligibility_probe(",
        "should_render_design_guide_slot_from_publication_eligibility(",
        "_dg_defer_final_panel_until_fresh_render = True",
        "_defer_design_guide_slot_until_after_widgets = False",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_pre_widget_gate_setup_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Pre-Widget Gate Setup Coordinator Verifier",
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
