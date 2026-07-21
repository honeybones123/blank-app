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
    json_path = ARTIFACT_DIR / f"inputs_page_guidance_secondary_apply_action_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_guidance_secondary_apply_action_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    render_source = (ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_guidance_secondary_apply_action_current_coordinator",
    )
    renderer_source, renderer_size = _function_source(render_source, "render_guidance_secondary_items")
    cta_renderer_source, cta_renderer_size = _function_source(render_source, "render_design_guide_component_cta")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("guidance_secondary_apply_action_coordinator_missing")
    if coordinator_size > 150:
        failures.append(f"guidance_secondary_apply_action_coordinator_too_large:{coordinator_size}")
    if renderer_size > 220:
        failures.append(f"guidance_secondary_renderer_not_reduced:{renderer_size}")
    for required in [
        "_build_pending_recommendation(item, guidance_disp_state)",
        "st.session_state[\"pending_recommendation\"] = rec",
        "st.success(\"Design is efficient - further reductions would weaken capacity\")",
        "return {\"continue_item\": True}",
        "_recommendation_commit_eligible(rec)",
        "_recommendation_blocked_reason(rec)",
        "No single one-click fix currently covers all failing checks",
        "primary_route_target = (",
        "_record_rendered_design_guide_primary_apply_payload(",
        "render_design_guide_component_cta(",
        "queue_primary_button_action_fn=_queue_primary_design_guide_button_action",
        "st.session_state[\"_inputs_design_guide_primary_button_pressed\"] = True",
        "Button contract: {html.escape(reason)}. Preview {html.escape(preview_text)}.",
        "return {\"continue_item\": False}",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_apply_action_fn(",
        "item=item",
        "guidance_disp_state=guidance_disp_state",
        "primary_card_presentation=primary_card_presentation",
        "button_contract=button_contract",
        "anchor_class=anchor_class",
        "is_primary_guidance_card=is_primary_guidance_card",
        "_pres_show_apply=pres_show_apply",
        "_suppress_one_click_cta=suppress_one_click_cta",
        "if bool(apply_action_result.get(\"continue_item\")):",
        "continue",
    ]:
        if required not in renderer_source:
            failures.append(f"renderer_missing_{required}")
    for stale in [
        "_build_pending_recommendation(item, guidance_disp_state)",
        "_record_rendered_design_guide_primary_apply_payload(",
        "st.button(",
        "on_click=_queue_primary_design_guide_button_action",
        "Button contract: {html.escape(reason)}. Preview {html.escape(preview_text)}.",
        "No single one-click fix currently covers all failing checks",
    ]:
        if stale in renderer_source:
            failures.append(f"renderer_still_owns_{stale}")
    if "def _render_guidance_secondary_items(" in source:
        failures.append("page_local_guidance_secondary_items_still_present")
    if "def _render_design_guide_component_cta(" in source:
        failures.append("page_local_design_guide_component_cta_still_present")
    for required in [
        "st_module.button(",
        "key=\"apply_design_guide\"",
        "on_click=queue_primary_button_action_fn",
        "dict(button_contract)",
    ]:
        if required not in cta_renderer_source:
            failures.append(f"cta_renderer_missing_{required}")

    payload = {
        "verifier": "inputs_page_guidance_secondary_apply_action_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "renderer_size": renderer_size,
        "cta_renderer_size": cta_renderer_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Secondary Apply Action Current Verifier",
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
