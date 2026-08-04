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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_pre_widget_terminal_seed_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_pre_widget_terminal_seed_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_design_guide_pre_widget_terminal_seed_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_guide_pre_widget_terminal_seed_coordinator_missing")
    if coordinator_size > 85:
        failures.append(f"design_guide_pre_widget_terminal_seed_coordinator_too_large:{coordinator_size}")
    for required in [
        'pre_widget_terminal_family_id = "TARGET_BAND_REACHED"',
        '"selected_family_id": pre_widget_terminal_family_id',
        '"published_family_id": pre_widget_terminal_family_id',
        '"cta_family_id": pre_widget_terminal_family_id',
        '"apply_payload_family_id": pre_widget_terminal_family_id',
        '"family_route_owner": "family_runtime"',
        '"render_gate_condition": "post_apply_required_checks_pass_pre_widget_direct"',
        '"enabled": False',
        '"actionable": False',
        '"intent": None',
        '"Design is efficient"',
        '"status": "PASS"',
        '"outcome_state": "PASS"',
        '"display_state": "PASS"',
        '"badge": "GOOD"',
        '"guidance_branch": "post_apply_required_checks_pass_pre_widget_direct"',
        '"selected_action_family": "combined"',
        '"primary_card_intent": "already_efficient"',
        '"button_contract_enabled": False',
        '"post_active_repair_green_acceptance_published": True',
        '"design_guide_terminal_state": "optimal"',
        '"design_guide_has_actionable_recommendation": False',
        "return pre_widget_terminal_family_id, pre_widget_terminal_cta_payload, pre_widget_terminal_display_payload",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_design_guide_pre_widget_terminal_seed_coordinator(",
        "pre_widget_terminal_item=_pre_widget_terminal_item",
        "pre_widget_terminal_debug=_pre_widget_terminal_debug",
        "pre_widget_terminal_overview=_pre_widget_terminal_overview",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        '_pre_widget_terminal_family_id = "TARGET_BAND_REACHED"',
        '"post_active_repair_green_acceptance_published": True',
        '"design_guide_terminal_state": "optimal"',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_pre_widget_terminal_seed_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Pre-Widget Terminal Seed Coordinator Verifier",
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
