"""Proof that Inputs-page rerun exits have browser/live cause markers.

Trace-only verifier. It checks source wiring for rerun cause labels used by
smoothness profiling. It does not assert or change rerun behavior.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
APP_PAGE = ROOT / "app.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_MARKERS = (
    "landing_go_design_inputs",
    "landing_open_design_mode",
    "landing_card_go_design_inputs",
    "landing_card_open_design_mode",
    "landing_card_view_capacity",
    "debug_clear_design_guide_ui_state",
    "design_action_widget_callback",
    "apply_guidance_updates",
    "guidance_sequence_step_compliant",
    "guidance_sequence_any_applied",
    "apply_resolved_candidate",
    "apply_best_candidate",
    "design_actions_toggle_hydrate",
    "design_actions_source_or_mode_changed",
    "design_actions_loads_edit_mode_changed",
)

EXISTING_SSL_MARKERS = (
    "apply_triggered_rerun",
    "handle_auto_design_preflight_rerun",
    "handle_auto_design_triggered_rerun",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _nearby_marker_report(lines: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, line in enumerate(lines):
        if "st.rerun()" not in line:
            continue
        window = "\n".join(lines[max(0, index - 8) : index + 1])
        rows.append(
            {
                "line": index + 1,
                "new_marker": "_record_inputs_rerun_trigger(" in window,
                "existing_ssl_marker": "ssl_record_rerun_trigger(" in window,
                "window": window.strip(),
            }
        )
    return rows


def _markdown(payload: dict) -> str:
    lines = [
        "# Design Guide Inputs Rerun Trigger Marker Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Summary",
        "",
        f"- Total rerun exits: `{payload['summary']['total_rerun_exits']}`",
        f"- Marked by new helper: `{payload['summary']['new_marker_count']}`",
        f"- Marked by existing SSL marker: `{payload['summary']['existing_ssl_marker_count']}`",
        f"- Unmarked rerun exits: `{payload['summary']['unmarked_count']}`",
        "",
        "## Failures",
        "",
    ]
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> int:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    app_source = APP_PAGE.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    rerun_rows = _nearby_marker_report(lines)
    missing_required = [marker for marker in REQUIRED_MARKERS if marker not in source]
    missing_existing = [marker for marker in EXISTING_SSL_MARKERS if marker not in source]
    unmarked = [
        row["line"]
        for row in rerun_rows
        if not row["new_marker"] and not row["existing_ssl_marker"]
    ]
    failures: list[str] = []
    if "_record_inputs_rerun_trigger" not in source:
        failures.append("record_inputs_rerun_trigger_helper_missing")
    if "_inputs_rerun_trigger_events" not in source:
        failures.append("local_inputs_rerun_trigger_event_store_missing")
    if "inputs_rerun_trigger_events" not in app_source:
        failures.append("browser_state_inputs_rerun_trigger_events_missing")
    failures.extend(f"required_marker_missing:{marker}" for marker in missing_required)
    failures.extend(f"existing_ssl_marker_missing:{marker}" for marker in missing_existing)
    failures.extend(f"rerun_exit_unmarked:{line}" for line in unmarked)
    payload = {
        "schema": "design_guide_inputs_rerun_trigger_marker_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "product_behaviour_changed": False,
        "publication_truth_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "summary": {
            "total_rerun_exits": len(rerun_rows),
            "new_marker_count": sum(1 for row in rerun_rows if row["new_marker"]),
            "existing_ssl_marker_count": sum(1 for row in rerun_rows if row["existing_ssl_marker"]),
            "unmarked_count": len(unmarked),
        },
        "rerun_rows": rerun_rows,
        "failures": failures,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_inputs_rerun_trigger_marker_snapshot_{payload['created_at']}.json"
    report_path = AUDIT_DIR / f"design_guide_inputs_rerun_trigger_marker_snapshot_{payload['created_at']}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_inputs_rerun_trigger_marker_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
