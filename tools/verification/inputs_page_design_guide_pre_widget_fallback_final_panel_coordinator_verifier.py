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
        f"inputs_page_design_guide_pre_widget_fallback_final_panel_coordinator_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_design_guide_pre_widget_fallback_final_panel_coordinator_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_guide_pre_widget_fallback_final_panel_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_guide_pre_widget_fallback_final_panel_coordinator_missing")
    if coordinator_size > 140:
        failures.append(
            f"design_guide_pre_widget_fallback_final_panel_coordinator_too_large:{coordinator_size}"
        )
    for required in [
        "design_guide_page.render_final_panel(",
        "slot=design_guide_slot",
        "sync_callbacks=sync_callbacks",
        "inputs_render_audit=inputs_render_audit",
        "inputs_detailed_mode=pre_widget_inputs_detailed_mode",
        "fast_focus_section=fast_focus_section",
        "render_panel=render_design_guide_panel_orchestration_coordinator",
        "trace=inputs_pre_widget_trace_fn",
        "render_panel_accepts_sync_callbacks=False",
        'DESIGN_GUIDE_DEBUG_BUNDLE_KEY',
        '"design_guide_final_panel_pre_widget_deferred"',
        '"single_final_panel_render_owns_live_card_and_cta"',
        '"design_guide_final_panel_pre_widget_stale_probe_ignored"',
        '"pre_widget_final_panel_deferred_until_current_after_widget_render"',
        '"browser_enabled_contract_pre_render_shell_deleted"',
        '"fallback_enabled_contract_shell_deleted"',
        '"early_shear_overdesign_direct_action_shell_deleted"',
        '"early_final_publication_payload_render"',
        '"post_apply_required_checks_pass_pre_widget_direct"',
        '"primary_design_guide_apply_button_rendered"',
        '"render_final_panel_missing_card_clean_recovery"',
        '"design_guide_final_panel_pre_widget_rendered"',
        '"design_guide_final_panel_pre_widget_probe"',
        '"design_guide_final_panel_rendered_pre_widgets"',
        "phase5c_render_trace_fn(",
        '"design_guide_final_panel_pre_widget_error"',
        '"design_guide_final_panel_pre_widget_render_failed"',
        "inputs_pre_widget_trace_fn(",
        "return bool(dg_final_panel_rendered_pre_widgets), dg_render_gate_bundle",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_design_guide_pre_widget_fallback_final_panel_coordinator(",
        "design_guide_slot=design_guide_slot",
        "sync_callbacks=sync_callbacks",
        "inputs_render_audit=inputs_render_audit",
        "fast_focus_section=fast_focus_section",
        "inputs_pre_widget_trace_fn=_inputs_pre_widget_trace",
        "phase5c_render_trace_fn=_phase5c_render_trace",
        "dg_shell_started=_dg_shell_started",
        "dg_render_gate_bundle=_dg_render_gate_bundle",
        "dg_final_panel_rendered_pre_widgets=_dg_final_panel_rendered_pre_widgets",
        "dg_defer_final_panel_until_fresh_render=_dg_defer_final_panel_until_fresh_render",
        "pre_widget_terminal_rendered_from_apply_route=_pre_widget_terminal_rendered_from_apply_route",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        "_pre_widget_inputs_detailed_mode = bool(",
        "design_guide_page.render_final_panel(",
        '_dg_render_gate_bundle["design_guide_final_panel_pre_widget_deferred"]',
        '_dg_render_gate_bundle["design_guide_final_panel_pre_widget_stale_probe_ignored"]',
        '_pre_widget_actual_deleted_marker = _pre_widget_actual_marker in {',
        '_dg_render_gate_bundle["design_guide_final_panel_pre_widget_error"]',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_pre_widget_fallback_final_panel_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Pre-Widget Fallback Final Panel Coordinator Verifier",
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
