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
    json_path = ARTIFACT_DIR / f"inputs_page_fast_model_slot_coordinator_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_fast_model_slot_coordinator_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_fast_model_slot_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("fast_model_slot_coordinator_missing")
    if coordinator_size > 25:
        failures.append(f"fast_model_slot_coordinator_too_large:{coordinator_size}")
    for required in [
        "_resolved_inputs_model_state()",
        "_inputs_fast_model_state_debug",
        "summary_governing_check_name",
        "fast_model_fingerprint_includes_shear",
        "with model_slot:",
        "_render_fast_model_block(sync_callbacks, model_state=model_state)",
        "inputs-diagram-materials-group",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_inputs_fast_model_slot_coordinator("
    if call_text not in render_inputs_source:
        failures.append("render_inputs_missing_fast_model_slot_call")
    for stale in [
        "model_state, model_state_debug = _resolved_inputs_model_state()",
        'st.session_state["_inputs_fast_model_state_debug"] =',
        "_render_fast_model_block(sync_callbacks, model_state=model_state)",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    materials_mark_index = render_inputs_source.find('_sub_mark("materials")')
    call_index = render_inputs_source.find(call_text)
    if not (0 <= call_index < materials_mark_index):
        failures.append(
            "fast_model_slot_call_order_changed:"
            f"call={call_index}:materials={materials_mark_index}"
        )

    payload = {
        "verifier": "inputs_page_fast_model_slot_coordinator_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Fast Model Slot Coordinator Current Verifier",
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
