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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_widget_apply_and_render_setup_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_widget_apply_and_render_setup_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_pre_widget_apply_and_render_setup_coordinator",
    )
    parent_source, _ = _function_source(source, "render_inputs_page_setup_current_coordinator")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("pre_widget_apply_and_render_setup_coordinator_missing")
    if coordinator_size > 75:
        failures.append(f"pre_widget_apply_and_render_setup_coordinator_too_large:{coordinator_size}")
    for required in [
        "_inputs_shear_shared_normalised_this_run",
        "_fast_mode_focus_section",
        "_handle_inputs_apply_buttons_current_coordinator()",
        "_wrap_longitudinal_reo_sync_callbacks(get_sync_callbacks())",
        "_fresh_inputs_render_audit()",
        "apply_inputs_page_css()",
        "apply_global_widget_css()",
        "apply_calcbox_css()",
        "publish_normalized_final_shear_truth_to_session",
        "_debug_d_consistency",
        "return corrected_invalid_shear_state, fast_focus_section, sync_callbacks, inputs_render_audit",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for stale in [
        "_inputs_shear_shared_normalised_this_run",
        "_fast_mode_focus_section",
        "_fresh_inputs_render_audit()",
        "publish_normalized_final_shear_truth_to_session(source=\"render_inputs:pre_summary\")",
    ]:
        if stale in parent_source:
            failures.append(f"page_setup_still_owns_{stale}")

    startup_call_index = parent_source.find("render_inputs_startup_hydration_coordinator(")
    call_index = parent_source.find(
        "render_inputs_pre_widget_apply_and_render_setup_coordinator("
    )
    before_state_index = parent_source.find("before_state = inputs_audit_snapshot_state()")
    tuple_prefix_index = parent_source.find(
        "corrected_invalid_shear_state,"
    )
    if call_index < 0:
        failures.append("render_inputs_missing_pre_widget_apply_and_render_setup_call")
    if tuple_prefix_index < 0 or tuple_prefix_index > call_index:
        failures.append("render_inputs_missing_pre_widget_tuple_assignment")
    if not (startup_call_index >= 0 and startup_call_index < call_index < before_state_index):
        failures.append(
            "pre_widget_apply_and_render_setup_call_order_changed:"
            f"startup={startup_call_index}:call={call_index}:before_state={before_state_index}"
        )

    payload = {
        "verifier": "inputs_page_pre_widget_apply_and_render_setup_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre-Widget Apply And Render Setup Coordinator Verifier",
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
