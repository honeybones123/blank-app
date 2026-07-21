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
    json_path = ARTIFACT_DIR / f"inputs_page_summary_state_cache_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_state_cache_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    state_cache_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "state_cache.py"
    ).read_text(encoding="utf-8", errors="ignore")
    pipeline_module_source = (
        ROOT / "inputs_page_modules" / "summaries" / "pipeline.py"
    ).read_text(encoding="utf-8", errors="ignore")
    widget_module_source = (
        ROOT / "inputs_page_modules" / "widgets" / "render_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        state_cache_module_source,
        "render_inputs_summary_state_cache",
    )
    route_state_cache_source, _ = _function_source(
        route_source,
        "render_inputs_summary_state_cache_current_coordinator",
    )
    render_inputs_source, _ = _function_source(shell_source, "render_inputs_page")
    summary_pipeline_source, _ = _function_source(
        pipeline_module_source,
        "render_inputs_summary_pipeline",
    )
    widget_sections_source, _ = _function_source(widget_module_source, "render_inputs_widget_sections")
    summary_owner_source = summary_pipeline_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_state_cache_coordinator_missing")
    if coordinator_size > 115:
        failures.append(f"summary_state_cache_coordinator_too_large:{coordinator_size}")

    for required in [
        "resolved_inputs_summary_state_fn()",
        "_inputs_summary_debug_bundle",
        "_inputs_summary_consume_audit",
        "resolve_design_actions_fn(summary_state)",
        "design_guide_fp_fn(summary_state)",
        "summary_action_fp",
        "_summary_cache_version",
        "_summary_cache_action_fp",
        "summary.build_bending_pack",
        "summary.build_shear_pack",
        "summary.build_crack_pack",
        "summary.build_deflection_pack",
        'mark("summary_packs")',
        "return summary_state, summary_state_debug, bend_pack, shear_pack, crack_pack, defl_pack",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "summary_state_cache_fn(ss=ss, mark=mark)"
    if call_text not in summary_owner_source:
        failures.append("render_inputs_missing_summary_state_cache_call")
    if "render_inputs_summary_state_cache_module(" not in route_state_cache_source:
        failures.append("route_summary_state_cache_missing_module_delegate")

    for stale in [
        "summary_state, summary_state_debug = _resolved_inputs_summary_state()",
        "_inputs_summary_debug_bundle",
        "_inputs_summary_consume_audit",
        "summary.build_bending_pack",
        "summary.build_shear_pack",
        "summary.build_crack_pack",
        "summary.build_deflection_pack",
        '_mark("summary_packs")',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    autopersist_index = widget_sections_source.find("post_widget_autopersist_fn(ss=ss)")
    widget_sections_index = render_inputs_source.find("render_inputs_widget_sections_current_coordinator(")
    summary_pipeline_index = render_inputs_source.find("render_inputs_summary_pipeline_current_coordinator(")
    summary_index = summary_owner_source.find(call_text)
    pack_log_index = summary_owner_source.find('hc_log_fn(\n        "summary.pack_meta"')
    rows_index = summary_owner_source.find("summary_rows_from_packs_fn(")
    rows_boundary = "summary_rows_from_packs_call"
    if rows_index < 0:
        rows_index = summary_owner_source.find('BENDING_ROWS = [_normalise_row(r, "bending")')
        rows_boundary = "inline_rows"
    if not (0 <= autopersist_index):
        failures.append(f"summary_state_cache_missing_widget_autopersist:autopersist={autopersist_index}")
    if not (0 <= widget_sections_index < summary_pipeline_index):
        failures.append(
            "summary_pipeline_call_order_changed:"
            f"autopersist={autopersist_index}:widget_sections={widget_sections_index}:"
            f"summary_pipeline={summary_pipeline_index}"
        )
    if not (0 <= summary_index < pack_log_index < rows_index):
        failures.append(
            "summary_state_cache_call_order_changed:"
            f"autopersist={autopersist_index}:summary={summary_index}:pack_log={pack_log_index}:"
            f"rows={rows_index}:{rows_boundary}"
        )

    payload = {
        "verifier": "inputs_page_summary_state_cache_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary State Cache Current Verifier",
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
