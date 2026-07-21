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
    json_path = ARTIFACT_DIR / f"inputs_page_guidance_secondary_button_contract_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_guidance_secondary_button_contract_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    render_source = (ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_guidance_secondary_button_contract_current_coordinator",
    )
    renderer_source, renderer_size = _function_source(render_source, "render_guidance_secondary_items")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("guidance_secondary_button_contract_coordinator_missing")
    if coordinator_size > 110:
        failures.append(f"guidance_secondary_button_contract_coordinator_too_large:{coordinator_size}")
    if renderer_size > 325:
        failures.append(f"guidance_secondary_renderer_not_reduced:{renderer_size}")
    for required in [
        "_design_guide_button_contract(",
        "blocking_reason_override=contract_block_override",
        "_COMPOUND_SHEAR_UPDATE_KEYS",
        "source=\"design_guide_render_shear_family_threshold_probe\"",
        "\"blocked_shear_cleanup_does_not_reach_final_family_threshold\"",
        "_design_guide_display_truth_for_item(",
        "st.session_state[\"design_guide_primary_button_contract\"]",
        "st.session_state[\"design_guide_primary_display_truth\"]",
        "st.session_state.pop(DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY, None)",
        "_set_design_guide_primary_payload_binding_audit(",
        "\"_pres_show_apply\": bool(_pres_show_apply)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_button_contract_fn(",
        "item=item",
        "guidance_disp_state=guidance_disp_state",
        "current_overview=current_overview",
        "is_primary_guidance_card=is_primary_guidance_card",
        "contract_block_override=contract_block_override",
        "_pres_show_apply_raw=pres_show_apply_raw",
        "button_contract = dict(button_contract_state[\"button_contract\"] or {})",
        "_ = dict(button_contract_state[\"refreshed_truth\"] or {})",
        "pres_show_apply = bool(button_contract_state[\"_pres_show_apply\"])",
    ]:
        if required not in renderer_source:
            failures.append(f"renderer_missing_{required}")
    for stale in [
        "button_contract = _design_guide_button_contract(",
        "source=\"design_guide_render_shear_family_threshold_probe\"",
        "item[\"button_contract\"] = dict(button_contract)",
        "refreshed_truth = _design_guide_display_truth_for_item(",
        "st.session_state[\"design_guide_primary_button_contract\"]",
        "_set_design_guide_primary_payload_binding_audit(",
        "_pres_show_apply = bool(\n            _pres_show_apply_raw",
    ]:
        if stale in renderer_source:
            failures.append(f"renderer_still_owns_{stale}")
    if "def _render_guidance_secondary_items(" in source:
        failures.append("page_local_guidance_secondary_items_still_present")

    payload = {
        "verifier": "inputs_page_guidance_secondary_button_contract_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "renderer_size": renderer_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Secondary Button Contract Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Renderer size: `{renderer_size}`",
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
