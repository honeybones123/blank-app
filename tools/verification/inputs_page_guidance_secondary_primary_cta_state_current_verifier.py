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
    json_path = ARTIFACT_DIR / f"inputs_page_guidance_secondary_primary_cta_state_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_guidance_secondary_primary_cta_state_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_module_source = (
        ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    render_source = (ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    coordinator_source, coordinator_size = _function_source(
        coordinator_module_source,
        "render_guidance_secondary_primary_cta_state_current_coordinator",
    )
    renderer_source, renderer_size = _function_source(render_source, "render_guidance_secondary_items")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("guidance_secondary_primary_cta_state_coordinator_missing")
    if coordinator_size > 90:
        failures.append(f"guidance_secondary_primary_cta_state_coordinator_too_large:{coordinator_size}")
    if renderer_size > 380:
        failures.append(f"guidance_secondary_renderer_not_reduced:{renderer_size}")
    for required in [
        "_one_click_feedback_cta_state(current_overview)",
        "_latest_solver_result_cta_state(current_overview)",
        "st.session_state[\"design_guide_one_click_cta_suppressed\"]",
        "st.session_state[\"design_guide_feedback_status\"]",
        "st.session_state[\"design_guide_current_fail_fingerprint\"]",
        "inputs_render_audit[\"design_guide_one_click_cta_suppressed\"]",
        "\"contract_block_override\": contract_block_override",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_primary_cta_state_fn(",
        "idx=idx",
        "start_index=start_index",
        "primary_card_presentation=primary_card_presentation",
        "current_overview=current_overview",
        "inputs_render_audit=inputs_render_audit",
        "contract_block_override = primary_cta_state[\"contract_block_override\"]",
        "contract_block_override=contract_block_override",
    ]:
        if required not in renderer_source:
            failures.append(f"renderer_missing_{required}")
    for stale in [
        "_feedback_cta = _one_click_feedback_cta_state(current_overview)",
        "_solver_result_cta = _latest_solver_result_cta_state(current_overview)",
        "st.session_state[\"design_guide_one_click_cta_suppressed\"]",
        "inputs_render_audit[\"design_guide_one_click_cta_suppressed\"]",
        "contract_block_override = (",
    ]:
        if stale in renderer_source:
            failures.append(f"renderer_still_owns_{stale}")
    if "def _render_guidance_secondary_items(" in shell_source:
        failures.append("page_local_guidance_secondary_items_still_present")

    payload = {
        "verifier": "inputs_page_guidance_secondary_primary_cta_state_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "renderer_size": renderer_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Secondary Primary CTA State Current Verifier",
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
