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
    json_path = ARTIFACT_DIR / f"inputs_page_shear_reinforcement_column_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_shear_reinforcement_column_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    widget_module_source = (
        ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        widget_module_source,
        "render_inputs_shear_reinforcement_column",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    widget_owner_source, _ = _function_source(widget_module_source, "render_inputs_widget_sections")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("shear_reinforcement_column_coordinator_missing")
    if coordinator_size > 175:
        failures.append(f"shear_reinforcement_column_coordinator_too_large:{coordinator_size}")

    for required in [
        "with col_shear_mat:",
        "Next step: confirm or auto-design the shear reinforcement below.",
        "fast_mode:shear_recommendation",
        "detailed_mode:shear_recommendation",
        "inputs_lig_d",
        "inputs_lig_legs",
        "inputs_s_lig",
        "render_inputs:shared_no_links_widget_stale",
        "render_inputs:corrected_invalid_shear_state",
        "_pending_shear_widget_seed_from_shared",
        "_inputs_shear_seed_consume_audit",
        "_inputs_shear_truth_audit",
        "H_SHEAR_WIDGET",
        "Link spacing (mm)",
        "No. of legs",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "shear_reinforcement_column_fn("
    if call_text not in widget_owner_source:
        failures.append("render_inputs_missing_shear_reinforcement_column_call")

    for stale in [
        "with col_shear_mat:",
        "fast_mode:shear_recommendation",
        "_pending_shear_widget_seed_from_shared",
        "_inputs_shear_seed_consume_audit",
        "_inputs_shear_truth_audit",
        "H_SHEAR_WIDGET",
        "Link spacing (mm)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    top_index = widget_owner_source.find("top_reinforcement_column_fn(")
    shear_index = widget_owner_source.find(call_text)
    flange_index = widget_owner_source.find("flange_reinforcement_fn(")
    if not (0 <= top_index < shear_index < flange_index):
        failures.append(
            "shear_reinforcement_call_order_changed:"
            f"top={top_index}:shear={shear_index}:flange={flange_index}"
        )

    payload = {
        "verifier": "inputs_page_shear_reinforcement_column_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Shear Reinforcement Column Current Verifier",
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
