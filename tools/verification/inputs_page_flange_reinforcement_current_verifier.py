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
    json_path = ARTIFACT_DIR / f"inputs_page_flange_reinforcement_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_flange_reinforcement_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    widget_module_source = (
        ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        widget_module_source,
        "render_inputs_flange_reinforcement",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    widget_owner_source, _ = _function_source(widget_module_source, "render_inputs_widget_sections")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("flange_reinforcement_coordinator_missing")
    if coordinator_size > 135:
        failures.append(f"flange_reinforcement_coordinator_too_large:{coordinator_size}")

    for required in [
        "sec_shape_for_flange",
        'sec_shape_for_flange in ("T", "I")',
        "### Flange reinforcement",
        "Only used for T and I sections",
        "inputs_top_flange_reo_enabled",
        "inputs_top_flange_mirror_lr",
        "inputs_top_flange_left_count",
        "inputs_top_flange_right_count",
        "inputs_bot_flange_reo_enabled",
        "inputs_bot_flange_mirror_lr",
        "inputs_bot_flange_left_count",
        "inputs_bot_flange_right_count",
        "#### Flange transverse detailing (optional)",
        "inputs_top_flange_transverse_enabled",
        "inputs_bot_flange_transverse_enabled",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "flange_reinforcement_fn("
    if call_text not in widget_owner_source:
        failures.append("render_inputs_missing_flange_reinforcement_call")

    for stale in [
        "sec_shape_for_flange",
        "### Flange reinforcement",
        "inputs_top_flange_reo_enabled",
        "inputs_bot_flange_reo_enabled",
        "#### Flange transverse detailing (optional)",
        "inputs_top_flange_transverse_enabled",
        "inputs_bot_flange_transverse_enabled",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    shear_index = widget_owner_source.find("shear_reinforcement_column_fn(")
    flange_index = widget_owner_source.find(call_text)
    detailed_index = widget_owner_source.find("detailed_support_lower_row_fn(")
    if not (0 <= shear_index < flange_index < detailed_index):
        failures.append(
            "flange_reinforcement_call_order_changed:"
            f"shear={shear_index}:flange={flange_index}:detailed={detailed_index}"
        )

    payload = {
        "verifier": "inputs_page_flange_reinforcement_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Flange Reinforcement Current Verifier",
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
