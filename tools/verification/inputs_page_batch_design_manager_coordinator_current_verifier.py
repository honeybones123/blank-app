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
    json_path = ARTIFACT_DIR / f"inputs_page_batch_design_manager_coordinator_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_batch_design_manager_coordinator_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_batch_design_manager_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")
    setup_source, _ = _function_source(source, "render_inputs_page_setup_current_coordinator")
    setup_owner_source = setup_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("batch_design_manager_coordinator_missing")
    if coordinator_size > 45:
        failures.append(f"batch_design_manager_coordinator_too_large:{coordinator_size}")

    for required in [
        "render_batch_design_page(",
        "BatchDesignPageContext(",
        "session_state=ss",
        "beam_order=beam_order",
        "active_beam_id=active_beam_id",
        "beam_labels=beam_labels",
        "set_active_beam=set_active_beam",
        "add_beam=add_new_beam_record",
        "duplicate_beam=duplicate_active_beam_record",
        "delete_beam=delete_beam_record",
        "reset_workspace=reset_app_to_clean_starter_workspace",
        "force_refresh=_force_inputs_apply_refresh_cycle",
        "log_rerun=render_inputs_beam_load_triggered_rerun_log_coordinator",
        "save_active_to_table=save_active_batch_beam_to_table",
        "apply_resync=_apply_canonical_convenience_resync_to_shared",
        "build_schedule_preview_df=build_batch_schedule_preview_df",
        "build_schedule_editor_df=build_batch_beam_schedule_df",
        "sync_schedule_editor_df=sync_batch_beam_records_from_schedule_df",
        "build_schedule_export_df=build_batch_schedule_export_df",
        "get_active_summary=get_active_beam_summary",
        "format_status_badge=format_batch_beam_status_badge",
        "format_last_checked=format_batch_last_checked",
        "make_section_preview_figure=make_summary_cross_section_figure",
        "render_plotly_diagram=st.plotly_chart",
        "design_brain_adapter=BatchDesignGuidanceAdapter(",
        "design_guidance_runner=_compute_design_guidance_items",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_inputs_batch_design_manager_coordinator("
    if call_text not in setup_owner_source:
        failures.append("render_inputs_missing_batch_design_manager_call")

    for stale in [
        "beam_manager_active_selector",
        "beam_manager_add_button",
        "beam_manager_duplicate_button",
        "beam_manager_delete_button",
        "beam_manager_reset_workspace",
        "beam_manager_toggle_button",
        "Bulk Beam Manager",
        "beam_manager_schedule_editor",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    context_index = setup_owner_source.find("render_inputs_batch_design_context_coordinator(")
    manager_index = setup_owner_source.find(call_text)
    divider_index = setup_owner_source.find("page_divider()")
    if not (0 <= context_index < manager_index < divider_index):
        failures.append(
            "batch_design_manager_call_order_changed:"
            f"context={context_index}:manager={manager_index}:divider={divider_index}"
        )

    payload = {
        "verifier": "inputs_page_batch_design_manager_coordinator_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Batch Design Manager Coordinator Current Verifier",
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
