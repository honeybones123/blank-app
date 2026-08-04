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


EXPECTED_TRANSVERSE_SNIPPETS: tuple[str, ...] = (
    '"group_id": "flange_transverse_basic"',
    '"shared_key": "top_flange_transverse_enabled"',
    '"shared_key": "top_flange_transverse_dia"',
    '"shared_key": "top_flange_transverse_spacing"',
    '"shared_key": "top_flange_transverse_legs"',
    '"shared_key": "bot_flange_transverse_enabled"',
    '"shared_key": "bot_flange_transverse_dia"',
    '"shared_key": "bot_flange_transverse_spacing"',
    '"shared_key": "bot_flange_transverse_legs"',
    '"label": "Enable top flange transverse"',
    '"label": "Top flange transverse dia (mm)"',
    '"label": "Top flange transverse spacing (mm)"',
    '"label": "Top flange transverse legs"',
    '"label": "Enable bottom flange transverse"',
    '"label": "Bottom flange transverse dia (mm)"',
    '"label": "Bottom flange transverse spacing (mm)"',
    '"label": "Bottom flange transverse legs"',
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Flange Transverse Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only the flange transverse widget metadata payload construction moved behind `inputs_page_modules.widgets`. It does not move Streamlit rendering, widget keys, callbacks, session hydration, or engineering behaviour.",
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
            "- `inputs_page.py` still renders flange transverse controls and owns callbacks.",
            "- `inputs_page_modules.widgets` builds only plain metadata payload dictionaries.",
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
    builder_body = builders.split("def build_flange_transverse_basic_widget_payloads(", 1)[-1]
    builder_body = builder_body.split("\ndef ", 1)[0]
    flange_transverse_payload_marker = (
        "_flange_transverse_payloads = "
        if "_flange_transverse_payloads = " in page
        else "flange_transverse_payloads = "
    )
    flange_group_vm_marker = (
        "_flange_group_vm = build_inputs_widget_group_view_model("
        if "_flange_group_vm = build_inputs_widget_group_view_model(" in page
        else "flange_group_vm = build_inputs_widget_group_view_model("
    )
    page_window = page.split(flange_transverse_payload_marker, 1)[-1].split(
        flange_group_vm_marker,
        1,
    )[0]
    trace_window = page.split(flange_transverse_payload_marker, 1)[-1].split(
        "st.session_state[\"_inputs_widget_metadata_trace\"] = dict(",
        1,
    )[0]
    render_window = page.split("Flange transverse reinforcement", 1)[-1].split(
        flange_transverse_payload_marker,
        1,
    )[0]
    import_window = page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0]
    checks = {
        "builder_function_exists": "def build_flange_transverse_basic_widget_payloads(" in builders,
        "builder_exported": "build_flange_transverse_basic_widget_payloads" in init,
        "page_imports_flange_transverse_builder": "build_flange_transverse_basic_widget_payloads" in import_window,
        "page_calls_flange_transverse_builder": (
            "_flange_transverse_payloads = build_flange_transverse_basic_widget_payloads(" in page
            or "flange_transverse_payloads = build_flange_transverse_basic_widget_payloads(" in page
        ),
        "page_still_renders_top_enable": '"Enable top flange transverse"' in render_window,
        "page_still_renders_top_diameter": '"Top flange transverse dia (mm)"' in render_window,
        "page_still_renders_top_spacing": '"Top flange transverse spacing (mm)"' in render_window,
        "page_still_renders_top_legs": '"Top flange transverse legs"' in render_window,
        "page_still_renders_bottom_enable": '"Enable bottom flange transverse"' in render_window,
        "page_still_renders_bottom_diameter": '"Bottom flange transverse dia (mm)"' in render_window,
        "page_still_renders_bottom_spacing": '"Bottom flange transverse spacing (mm)"' in render_window,
        "page_still_renders_bottom_legs": '"Bottom flange transverse legs"' in render_window,
        "page_still_reads_transverse_state": "st.session_state" in page_window,
        "page_still_passes_sync_callbacks": "sync_callbacks" in render_window,
        "page_keeps_transverse_group_vm": 'group_id="flange_transverse_basic"' in trace_window,
        "page_keeps_transverse_trace_hash": '"flange_transverse_basic_widget_metadata_hash"' in trace_window,
        "page_inline_transverse_payload_removed": all(
            snippet not in page_window for snippet in EXPECTED_TRANSVERSE_SNIPPETS
        ),
        "builder_preserves_transverse_payload_literals": all(
            snippet in builder_body for snippet in EXPECTED_TRANSVERSE_SNIPPETS
        ),
        "builder_accepts_reo_bar_diameters_from_page": "reo_bar_diameters" in builder_body
        and "diameters = list(reo_bar_diameters or ())" in builder_body,
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "FLANGE_TRANSVERSE_WIDGET_METADATA_BUILDER_DELEGATED"
        if not failures
        else "FLANGE_TRANSVERSE_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_widgets_flange_transverse_metadata_builder_delegation",
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
    json_path = VERIFICATION_DIR / f"inputs_widgets_flange_transverse_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_flange_transverse_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        "inputs_widgets_flange_transverse_metadata_builder_delegation",
        "PASS" if not failures else "FAIL",
    )
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
