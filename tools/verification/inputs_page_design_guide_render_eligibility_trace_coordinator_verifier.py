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
    json_path = ARTIFACT_DIR / (
        f"inputs_page_design_guide_render_eligibility_trace_coordinator_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_design_guide_render_eligibility_trace_coordinator_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_guide_render_eligibility_trace_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_guide_render_eligibility_trace_coordinator_missing")
    if coordinator_size > 170:
        failures.append(
            f"design_guide_render_eligibility_trace_coordinator_too_large:{coordinator_size}"
        )
    for required in [
        'dg_render_gate_bundle.get("final_publication_verifier_payload")',
        'dg_render_gate_bundle.get("current_overview")',
        "_overview_active_failure_keys(",
        'dg_render_gate_bundle.get("active_failures")',
        'dg_render_gate_bundle.get("active_failure_keys")',
        'dg_render_gate_verifier.get("active_failures")',
        '"GEOMETRY_DETAILING_GOVERNS"',
        '"LOCKED_NO_REPAIR"',
        '"design_guide_render_eligibility_trace.v1"',
        '"trace_only": True',
        '"product_behaviour_changed": False',
        '"pre_slot_publication_eligibility_probe"',
        '"pre_slot_publication_eligibility_probe_used"',
        '"slot_eligibility_adapter_evaluated_trace_only": True',
        '"slot_eligibility_adapter_product_driving": True',
        '"render_eligibility_classification"',
        '"classification_labels"',
        'st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY]',
        'st.session_state["_design_guide_render_eligibility_trace_last"]',
        "return dg_render_gate_bundle",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_design_guide_render_eligibility_trace_coordinator(",
        "dg_render_gate_bundle=_dg_render_gate_bundle",
        "dg_render_gate_decision=_dg_render_gate_decision",
        "dg_pre_slot_publication_probe=_dg_pre_slot_publication_probe",
        "inputs_has_design_actions_or_loads_for_dg=_inputs_has_design_actions_or_loads_for_dg",
        "show_design_guide_for_current_inputs=show_design_guide_for_current_inputs",
        "browser_test_mode_for_latency=bool(_browser_test_mode_for_latency)",
        "design_guide_slot=design_guide_slot",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        "_dg_render_gate_verifier = dict(",
        "_dg_render_gate_active_failures: set[str] = set()",
        "_dg_render_gate_selected_family = str(",
        "_dg_render_gate_outcome_state = str(",
        "_dg_render_eligibility_trace = {",
        '_dg_render_gate_bundle["design_guide_render_eligibility_trace"]',
        'st.session_state["_design_guide_render_eligibility_trace_last"] = dict(_dg_render_eligibility_trace)',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_render_eligibility_trace_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Render Eligibility Trace Coordinator Verifier",
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
