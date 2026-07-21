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
        f"inputs_page_design_guide_before_inputs_form_panel_coordinator_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_design_guide_before_inputs_form_panel_coordinator_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_guide_before_inputs_form_panel_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("before_inputs_form_panel_coordinator_missing")
    if coordinator_size > 150:
        failures.append(f"before_inputs_form_panel_coordinator_too_large:{coordinator_size}")
    for required in [
        "defer_design_guide_publication_payload_until_after_inputs_form = False",
        "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)",
        '"browser_enabled_contract_pre_render_shell_deleted"',
        '"fallback_enabled_contract_shell_deleted"',
        '"early_shear_overdesign_direct_action_shell_deleted"',
        '"early_final_publication_payload_render"',
        '"post_apply_required_checks_pass_pre_widget_direct"',
        '"primary_design_guide_apply_button_rendered"',
        '"render_final_panel_missing_card_clean_recovery"',
        'source="after_design_mode_before_inputs_form"',
        "render_design_guide_panel_orchestration_coordinator(",
        "fast_focus_section=fast_focus_section",
        '"design_guide_final_panel_rendered_before_inputs_form"',
        'source="after_mid_form_panel_publication_payload_recovery"',
        '"design_guide_final_panel_before_inputs_form_error"',
        '"design_guide_final_panel_before_inputs_form_failed"',
        "inputs_pre_widget_trace_fn(",
        "return bool(dg_final_panel_rendered_pre_widgets)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_design_guide_before_inputs_form_panel_coordinator(",
        "inputs_detailed_mode=bool(inputs_detailed_mode)",
        "dg_final_panel_rendered_pre_widgets=_dg_final_panel_rendered_pre_widgets",
        "dg_defer_final_panel_until_fresh_render=_dg_defer_final_panel_until_fresh_render",
        "show_design_guide_for_current_inputs=show_design_guide_for_current_inputs",
        "design_guide_slot=design_guide_slot",
        "inputs_render_audit=inputs_render_audit",
        "fast_focus_section=fast_focus_section",
        "render_design_guide_slot_from_final_publication_payload_fn=(",
        "_render_design_guide_slot_from_final_publication_payload",
        "inputs_pre_widget_trace_fn=_inputs_pre_widget_trace",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        "_defer_design_guide_publication_payload_until_after_inputs_form = False",
        "_dg_before_form_bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)",
        "_dg_before_form_actual_card_rendered = bool(",
        "_dg_mid_form_render_bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)",
        "_dg_mid_form_card_rendered = bool(",
        '"design_guide_final_panel_before_inputs_form_error"',
        '"design_guide_final_panel_before_inputs_form_failed"',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_before_inputs_form_panel_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Before Inputs Form Panel Coordinator Verifier",
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
