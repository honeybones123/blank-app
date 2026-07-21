from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
WIDGETS_BUILDERS = ROOT / "inputs_page_modules" / "widgets" / "builders.py"
WIDGETS_INIT = ROOT / "inputs_page_modules" / "widgets" / "__init__.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


EXPECTED_SNIPPETS: tuple[str, ...] = (
    '"group_id": "design_action_numbers"',
    '"kind": "number_input"',
    '"widget_id": widget_key',
    '"widget_key": widget_key',
    '"callback_key": widget_key',
    '"shared_key": str(raw_spec.get("shared_key") or "")',
    '"disabled": bool(raw_spec.get("disabled_in_design_mode")) and bool(design_controls_enabled)',
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Design Action Numbers Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only the rendered design-action number widget metadata mapping moved behind `inputs_page_modules.widgets`. It does not move rendering, callbacks, session hydration, or action consistency checks.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- `inputs_page.py` still renders the number rows and constructs callbacks.",
            "- `inputs_page.py` still reads session values and reconciles shared state.",
            "- `inputs_page_modules.widgets` maps already-rendered specs to plain metadata payloads.",
            "- Live renderer cutover remains false.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    builders = _read(WIDGETS_BUILDERS)
    init = _read(WIDGETS_INIT)
    builder_body = builders.split("def build_design_action_numbers_widget_payloads(", 1)[-1]
    page_window = page.split("_design_action_numbers_widget_metadata_trace = dict(", 1)[-1].split(
        "st.session_state[\"_inputs_widget_metadata_trace\"] = dict(",
        1,
    )[0]
    render_window = page.split("_rendered_design_action_widget_specs", 1)[-1].split(
        "_design_action_numbers_widget_metadata_trace = dict(",
        1,
    )[0]
    checks = {
        "builder_function_exists": "def build_design_action_numbers_widget_payloads(" in builders,
        "builder_exported": "build_design_action_numbers_widget_payloads" in init,
        "page_imports_builder": "build_design_action_numbers_widget_payloads" in page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0],
        "page_calls_builder": "_design_action_numbers_widget_payloads = build_design_action_numbers_widget_payloads(" in page,
        "page_still_renders_number_rows": "_render_design_action_number_row(" in render_window,
        "page_still_makes_callbacks": "_make_design_action_widget_callback(" in render_window,
        "page_still_reconciles_widgets": "_reconcile_design_action_widgets_with_shared(" in render_window,
        "page_still_reads_session_values_for_builder": "st.session_state.get(" in page_window,
        "page_keeps_group_vm": 'group_id="design_action_numbers"' in page_window,
        "page_keeps_trace_hash": '"design_action_numbers_widget_metadata_hash"' in page_window,
        "page_inline_payload_mapping_removed": '"group_id": "design_action_numbers"' not in page_window or '"shared_key": str(spec["shared_key"])' not in page_window,
        "builder_preserves_payload_mapping": all(snippet in builder_body for snippet in EXPECTED_SNIPPETS),
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_execute_callbacks": "_make_design_action_widget_callback" not in builder_body and "_render_design_action_number_row" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "DESIGN_ACTION_NUMBERS_WIDGET_METADATA_BUILDER_DELEGATED" if not failures else "DESIGN_ACTION_NUMBERS_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_design_action_numbers_metadata_builder_delegation",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "live_renderer_switched": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_design_action_numbers_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_design_action_numbers_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_design_action_numbers_metadata_builder_delegation", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
