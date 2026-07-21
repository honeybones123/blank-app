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
    "member_faces_exposed",
    "shrinkage_env",
    "env_option",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Serviceability Environment Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only the serviceability environment widget metadata payload construction moved behind `inputs_page_modules.widgets`. It does not move Streamlit rendering, widget keys, callbacks, session hydration, or engineering behaviour.",
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
            "- `inputs_page.py` still renders serviceability environment controls and owns callbacks.",
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
    builder_body = builders.split("def build_serviceability_environment_basic_widget_payloads(", 1)[-1]
    builder_body = builder_body.split("\ndef ", 1)[0]
    page_window = page.split('"serviceability_environment_basic": ', 1)[-1].split(
        '"support_deflection_basic":',
        1,
    )[0]
    render_window = page.split("Serviceability", 1)[-1].split(
        "_detailed_widget_metadata_trace = dict(",
        1,
    )[0]
    trace_window = page.split("_detailed_widget_groups = {", 1)[-1].split(
        "for _group_id, _payloads in _detailed_widget_groups.items():",
        1,
    )[0]
    import_window = page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0]

    from inputs_page_modules.widgets import build_serviceability_environment_basic_widget_payloads

    payloads = build_serviceability_environment_basic_widget_payloads(
        member_faces_widget_key="inputs_member_faces_exposed",
        member_faces_value="2 faces",
        member_faces_options=["1 face", "2 faces"],
        shrinkage_environment_widget_key="inputs_shrinkage_env",
        shrinkage_environment_value="Interior",
        shrinkage_environment_options=["Interior", "Exterior"],
        creep_environment_widget_key="inputs_env_option",
        creep_environment_value="A1",
        creep_environment_options=["A1", "A2"],
    )
    shared_keys = tuple(str(row.get("shared_key") or "") for row in payloads)
    checks = {
        "builder_function_exists": "def build_serviceability_environment_basic_widget_payloads(" in builders,
        "builder_exported": "build_serviceability_environment_basic_widget_payloads" in init,
        "page_imports_serviceability_builder": "build_serviceability_environment_basic_widget_payloads" in import_window,
        "page_calls_serviceability_builder": '"serviceability_environment_basic": build_serviceability_environment_basic_widget_payloads(' in page,
        "page_still_renders_member_faces": '"Member / faces exposed"' in render_window,
        "page_still_renders_shrinkage_environment": '"Shrinkage environment (Table 3.1.7.2)"' in render_window,
        "page_still_renders_creep_environment": '"Creep environment (Tables 3.1.8.2 & 3.1.8.3)"' in render_window,
        "page_still_reads_serviceability_state": "st.session_state" in render_window,
        "page_still_passes_sync_callbacks": "sync_callbacks" in render_window,
        "page_keeps_serviceability_group_vm": '"serviceability_environment_basic"' in trace_window
        and "for _group_id, _payloads in _detailed_widget_groups.items():" in page
        and "build_inputs_widget_group_view_model(" in page
        and "group_id=_group_id" in page,
        "page_keeps_serviceability_trace_hash": '_detailed_widget_metadata_trace[f"{_group_id}_widget_metadata_hash"]' in page
        and "_previous_group_hashes[_group_id] = _group_vm.display_hash" in page,
        "page_inline_serviceability_payload_removed": '"shared_key": "member_faces_exposed"' not in page_window
        and '"shared_key": "shrinkage_env"' not in page_window
        and '"shared_key": "env_option"' not in page_window,
        "builder_payload_keys_match": shared_keys == EXPECTED_SHARED_KEYS,
        "builder_uses_page_widget_keys": "member_faces_widget_key" in builder_body
        and "shrinkage_environment_widget_key" in builder_body
        and "creep_environment_widget_key" in builder_body,
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "SERVICEABILITY_ENVIRONMENT_WIDGET_METADATA_BUILDER_DELEGATED"
        if not failures
        else "SERVICEABILITY_ENVIRONMENT_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_widgets_serviceability_environment_metadata_builder_delegation",
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
        "live_renderer_switched": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_serviceability_environment_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_serviceability_environment_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        "inputs_widgets_serviceability_environment_metadata_builder_delegation",
        "PASS" if not failures else "FAIL",
    )
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
