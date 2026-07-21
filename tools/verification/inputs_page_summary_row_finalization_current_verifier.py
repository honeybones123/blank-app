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
    json_path = ARTIFACT_DIR / f"inputs_page_summary_row_finalization_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_row_finalization_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_summary_row_finalization_current_coordinator",
    )
    render_inputs_source, render_inputs_size = _function_source(source, "render_inputs")
    summary_pipeline_source, _ = _function_source(
        source,
        "render_inputs_summary_pipeline_current_coordinator",
    )
    summary_owner_source = summary_pipeline_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_row_finalization_coordinator_missing")
    if coordinator_size > 65:
        failures.append(f"summary_row_finalization_coordinator_too_large:{coordinator_size}")

    for required in [
        "def _status_to_ok(status_str):",
        "_ = _status_to_ok",
        "for rows, route in (",
        '(BENDING_ROWS, "bending")',
        '(SHEAR_ROWS, "shear")',
        '(CRACK_ROWS, "crack")',
        '(DEFLECTION_ROWS, "deflection")',
        "r.get(\"is_informational\")",
        'str(r.get("status", "")).upper() == "INFO"',
        'status = r.get("status", "—")',
        'r["ok"] = True if status == "PASS" else False if status in ("FAIL", "NG", "NEAR LIMIT") else None',
        'r.setdefault("route_page", route)',
        "BENDING_ROW_UID_TO_TAB",
        "SHEAR_ROW_UID_TO_TAB",
        "if not skip_active_beam_record_write:",
        "update_active_beam_summary_from_results(",
        "bending_rows=BENDING_ROWS",
        "shear_rows=SHEAR_ROWS",
        "crack_rows=CRACK_ROWS",
        "deflection_rows=DEFLECTION_ROWS",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_inputs_summary_row_finalization_current_coordinator("
    if call_text not in summary_owner_source:
        failures.append("render_inputs_missing_summary_row_finalization_call")

    for stale in [
        "def _status_to_ok(status_str):",
        "for rows, route in (",
        "BENDING_ROW_UID_TO_TAB",
        "SHEAR_ROW_UID_TO_TAB",
        "update_active_beam_summary_from_results(",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    guidance_index = summary_owner_source.find("render_inputs_summary_guidance_cache_current_coordinator(")
    html_helper_index = summary_owner_source.find("render_inputs_summary_row_finalization_current_coordinator(")
    finalization_index = summary_owner_source.find(call_text)
    summary_render_index = summary_owner_source.find("render_inputs_summary_container_current_coordinator(")
    if not (0 <= guidance_index < finalization_index < summary_render_index):
        failures.append(
            "summary_row_finalization_call_order_changed:"
            f"guidance={guidance_index}:html_helper={html_helper_index}:"
            f"finalization={finalization_index}:summary_render={summary_render_index}"
        )

    payload = {
        "verifier": "inputs_page_summary_row_finalization_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Row Finalization Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Render inputs size: `{render_inputs_size}`",
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
