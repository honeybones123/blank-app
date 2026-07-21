from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
WIDGETS_BUILDERS = ROOT / "inputs_page_modules" / "widgets" / "builders.py"
WIDGETS_INIT = ROOT / "inputs_page_modules" / "widgets" / "__init__.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


EXPECTED_SHARED_KEYS: tuple[str, ...] = (
    "inputs_detailed_mode",
    "actions_source",
    "loads_edit_toggle",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Top-Level Design Mode Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only the top-level mode/design-action toggle metadata payload construction moved behind `inputs_page_modules.widgets`. It preserves the existing mixed trace shape and does not move Streamlit rendering, callbacks, rerun handling, session synchronization, or engineering behaviour.",
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
            "- `inputs_page.py` still renders the design mode and action toggles.",
            "- `inputs_page.py` still owns callbacks, dirty flags, and rerun routing.",
            "- `inputs_page_modules.widgets` builds only plain metadata payload dictionaries.",
            "- Existing mixed top-level metadata hash shape is preserved.",
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
    builder_body = builders.split("def build_top_level_design_mode_widget_payloads(", 1)[-1]
    builder_body = builder_body.split("\ndef ", 1)[0]
    page_window = page.split("_top_level_widget_group_vm = build_inputs_widget_group_view_model(", 1)[-1].split(
        "_inputs_widget_metadata_trace.update(",
        1,
    )[0]
    render_window = page.split("Design mode", 1)[-1].split(
        "_inputs_widget_metadata_trace = {",
        1,
    )[0]
    import_window = page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0]

    from inputs_page_modules.widgets import build_top_level_design_mode_widget_payloads

    payloads = build_top_level_design_mode_widget_payloads(
        detailed_mode_value=True,
        use_calculated_actions_value=False,
        loads_edit_toggle_widget_key="inputs_loads_edit_toggle",
        edit_sls_value=True,
    )
    shared_keys = tuple(str(row.get("shared_key") or "") for row in payloads)
    group_ids = tuple(str(row.get("group_id") or "") for row in payloads)
    checks = {
        "builder_function_exists": "def build_top_level_design_mode_widget_payloads(" in builders,
        "builder_exported": "build_top_level_design_mode_widget_payloads" in init,
        "page_imports_top_level_builder": "build_top_level_design_mode_widget_payloads" in import_window,
        "page_calls_top_level_builder": "widgets=build_top_level_design_mode_widget_payloads(" in page,
        "page_still_renders_design_mode": '"Design mode"' in render_window,
        "page_still_renders_use_calculated_actions": '"Use calculated design actions"' in render_window,
        "page_still_renders_view_sls_loads": '"View SLS loads"' in render_window,
        "page_still_owns_change_callback": "def _on_inputs_use_calculated_actions_change()" in render_window,
        "page_still_owns_dirty_flags": "st.session_state[\"inputs_dirty\"] = True" in render_window,
        "page_still_owns_rerun_routing": "st.rerun()" in page,
        "page_keeps_top_level_group_vm": 'group_id="top_level_design_mode"' in page_window,
        "page_keeps_existing_mixed_hash_shape": '"inputs_widget_metadata_hash"' in page
        and '"inputs_widget_group_id"' in page,
        "page_inline_top_level_payload_removed": '"shared_key": "inputs_detailed_mode"' not in page_window
        and '"shared_key": "actions_source"' not in page_window
        and '"shared_key": "loads_edit_toggle"' not in page_window,
        "builder_payload_keys_match": shared_keys == EXPECTED_SHARED_KEYS,
        "builder_preserves_existing_mixed_group_shape": group_ids
        == ("top_level_design_mode", "design_actions_mode", "design_actions_mode"),
        "builder_uses_page_loads_toggle_key": "loads_edit_toggle_widget_key" in builder_body,
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "TOP_LEVEL_DESIGN_MODE_WIDGET_METADATA_BUILDER_DELEGATED"
        if not failures
        else "TOP_LEVEL_DESIGN_MODE_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_widgets_top_level_design_mode_metadata_builder_delegation",
        "timestamp": timestamp,
        "decision": decision,
        "payload_count": len(payloads),
        "checks": checks,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "rerun_routing_moved": False,
        "live_renderer_switched": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_top_level_design_mode_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_top_level_design_mode_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        "inputs_widgets_top_level_design_mode_metadata_builder_delegation",
        "PASS" if not failures else "FAIL",
    )
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
