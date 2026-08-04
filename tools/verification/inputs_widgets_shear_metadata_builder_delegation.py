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


EXPECTED_SHEAR_SNIPPETS: tuple[str, ...] = (
    '"group_id": "shear_reinforcement_basic"',
    '"shared_key": "lig_d"',
    '"shared_key": "lig_legs"',
    '"shared_key": "s_lig"',
    '"label": "No. of legs"',
    '"label": "Link spacing (mm)"',
    '"help_text": "Nominal diameter of shear reinforcement links (mm)."',
    '"help_text": "Number of legs per shear link. Use 0 for no links; 2 or more for active shear reinforcement."',
    '"help_text": "Centre-to-centre spacing of shear links along the member (mm)."',
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Shear Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only the Shear reinforcement widget metadata payload construction moved behind `inputs_page_modules.widgets`. It does not move Streamlit rendering, widget keys, callbacks, session hydration, or engineering behaviour.",
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
            "- `inputs_page.py` still renders shear controls and owns callbacks.",
            "- `inputs_page_modules.widgets` builds only plain metadata payload dictionaries.",
            "- The 0-leg option remains represented in metadata and the live widget remains page-rendered.",
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
    builder_body = builders.split("def build_shear_reinforcement_basic_widget_payloads(", 1)[-1]
    page_window = page.split("_shear_widget_metadata_trace = dict(", 1)[-1].split(
        "st.session_state[\"_inputs_widget_metadata_trace\"] = dict(_shear_widget_metadata_trace)",
        1,
    )[0]
    render_window = page.split("# Get widget keys from TAB_KEYS", 1)[-1].split(
        "_shear_widget_metadata_trace = dict(",
        1,
    )[0]
    checks = {
        "builder_function_exists": "def build_shear_reinforcement_basic_widget_payloads(" in builders,
        "builder_exported": "build_shear_reinforcement_basic_widget_payloads" in init,
        "page_imports_shear_builder": "build_shear_reinforcement_basic_widget_payloads" in page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0],
        "page_calls_shear_builder": "_shear_widget_payloads = build_shear_reinforcement_basic_widget_payloads(" in page,
        "page_still_renders_link_diameter": str('"Nominal diameter of shear reinforcement links (mm)."') in render_window,
        "page_still_renders_link_legs": '"No. of legs"' in render_window,
        "page_still_renders_link_spacing": '"Link spacing (mm)"' in render_window,
        "page_still_allows_zero_leg_render_option": "[0] + list(range(2, 13))" in render_window,
        "page_still_reads_shear_state": "st.session_state" in render_window,
        "page_still_passes_sync_callbacks": "sync_callbacks" in render_window,
        "page_keeps_shear_group_vm": 'group_id="shear_reinforcement_basic"' in page_window,
        "page_keeps_shear_trace_hash": '"shear_widget_metadata_hash"' in page_window,
        "page_inline_shear_payload_removed": '"shared_key": "lig_d"' not in page_window and '"shared_key": "s_lig"' not in page_window,
        "builder_preserves_shear_payload_literals": all(snippet in builder_body for snippet in EXPECTED_SHEAR_SNIPPETS),
        "builder_preserves_zero_off_option": '{0: "0 (off)"}' in builder_body,
        "builder_preserves_zero_leg_options": "[0] + list(range(2, 13))" in builder_body,
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SHEAR_WIDGET_METADATA_BUILDER_DELEGATED" if not failures else "SHEAR_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_shear_metadata_builder_delegation",
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
    json_path = VERIFICATION_DIR / f"inputs_widgets_shear_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_shear_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_shear_metadata_builder_delegation", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
