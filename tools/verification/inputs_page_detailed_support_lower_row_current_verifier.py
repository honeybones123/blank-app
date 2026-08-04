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
    json_path = ARTIFACT_DIR / f"inputs_page_detailed_support_lower_row_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_detailed_support_lower_row_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    widget_module_source = (
        ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        widget_module_source,
        "render_inputs_detailed_support_lower_row",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    widget_owner_source, _ = _function_source(widget_module_source, "render_inputs_widget_sections")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("detailed_support_lower_row_coordinator_missing")
    if coordinator_size > 140:
        failures.append(f"detailed_support_lower_row_coordinator_too_large:{coordinator_size}")

    for required in [
        'sub_mark("reinforcement")',
        "materials_and_section_2d_fn(sync_callbacks)",
        'sub_mark("shear_torsion")',
        "time_dependent_inputs_fn(sync_callbacks)",
        "ducts_prestress_voids_inputs_fn(sync_callbacks)",
        "Crack Control Inputs",
        "inputs_exposure_class",
        "Exposure classification to AS 3600 – controls allowable crack width.",
        "inputs_crack_member_type",
        "Affects default k₂ assumption and crack model interpretation.",
        "k₁ (bond coefficient)",
        "Deformed bars (k₁ = 0.8)",
        "inputs_crack_k1",
        "k₂ (strain distribution factor)",
        "inputs_crack_k2",
        'sub_mark("end")',
        'mark("render_inputs_widgets")',
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "detailed_support_lower_row_fn("
    if call_text not in widget_owner_source:
        failures.append("render_inputs_missing_detailed_support_lower_row_call")

    for stale in [
        "_render_materials_and_sectionA_2d(sync_callbacks)",
        "_render_time_dependent_inputs(sync_callbacks)",
        "_render_ducts_prestress_voids_inputs(sync_callbacks)",
        "Crack Control Inputs",
        "inputs_exposure_class",
        "inputs_crack_member_type",
        "inputs_crack_k1",
        "inputs_crack_k2",
        '_mark("render_inputs_widgets")',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    flange_index = widget_owner_source.find("flange_reinforcement_fn(")
    detailed_index = widget_owner_source.find(call_text)
    autopersist_index = widget_owner_source.find("post_widget_autopersist_fn(")
    if not (0 <= flange_index < detailed_index < autopersist_index):
        failures.append(
            "detailed_support_lower_row_call_order_changed:"
            f"flange={flange_index}:detailed={detailed_index}:autopersist={autopersist_index}"
        )

    payload = {
        "verifier": "inputs_page_detailed_support_lower_row_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Detailed Support Lower Row Current Verifier",
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
