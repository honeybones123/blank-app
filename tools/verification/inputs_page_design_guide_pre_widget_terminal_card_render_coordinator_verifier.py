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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_pre_widget_terminal_card_render_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_pre_widget_terminal_card_render_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_guide_pre_widget_terminal_card_render_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_guide_pre_widget_terminal_card_render_coordinator_missing")
    if coordinator_size > 80:
        failures.append(f"design_guide_pre_widget_terminal_card_render_coordinator_too_large:{coordinator_size}")
    for required in [
        "_build_final_design_guide_publication(",
        'publication_reason="post_apply_required_checks_pass_pre_widget_direct"',
        "_build_final_design_guide_card_format(",
        "design_guide_slot.empty()",
        "with design_guide_slot.container():",
        "_render_design_guide_heading_if_needed()",
        "_render_final_design_guide_card_html(pre_widget_terminal_format)",
        'pre_widget_terminal_debug["actual_card_render_probe"]',
        '"marker": "post_apply_required_checks_pass_pre_widget_direct"',
        '"actual_card_rendered": True',
        '"render_button_contract_enabled": False',
        '"publication_hash": pre_widget_terminal_publication.publication_hash',
        '"format_hash": pre_widget_terminal_format.format_hash',
        "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY]",
        'st.session_state["_design_guide_render_plan_debug"]',
        '"render_primary_only": True',
        'st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_KEY, None)',
        'st.session_state.pop(DESIGN_GUIDE_APPLY_BANNER_META_KEY, None)',
        'st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)',
        'st.session_state["_design_guide_banner_generic_only"] = False',
        'st.session_state["design_guide_primary_button_contract_enabled"] = False',
        "st.session_state[DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY] = {}",
        '"_design_guide_combined_terminal_apply_pending_render"',
        "return True, True",
        'dg_render_gate_bundle["pre_widget_terminal_direct_error"]',
        "return False, bool(dg_final_panel_rendered_pre_widgets)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_design_guide_pre_widget_terminal_card_render_coordinator(",
        "design_guide_slot=design_guide_slot",
        "pre_widget_terminal_item=_pre_widget_terminal_item",
        "pre_widget_terminal_debug=_pre_widget_terminal_debug",
        "pre_widget_terminal_payload=_pre_widget_terminal_payload",
        "dg_render_gate_bundle=_dg_render_gate_bundle",
        "dg_final_panel_rendered_pre_widgets=_dg_final_panel_rendered_pre_widgets",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        "_pre_widget_terminal_publication = _build_final_design_guide_publication(",
        "_pre_widget_terminal_format = _build_final_design_guide_card_format(",
        '_pre_widget_terminal_debug["actual_card_render_probe"] = {',
        'st.session_state["_design_guide_render_plan_debug"] = {',
        '_dg_render_gate_bundle["pre_widget_terminal_direct_error"] = str(',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_pre_widget_terminal_card_render_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Pre-Widget Terminal Card Render Coordinator Verifier",
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
