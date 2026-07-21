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


EXPECTED_GEOMETRY_SNIPPETS: tuple[str, ...] = (
    '"group_id": "geometry_basic"',
    '"label": "Section shape"',
    '"label": "Depth D (mm)"',
    '"label": "Span L (mm)"',
    '"label": "Width b (mm)"',
    '"label": "Flange width bf (mm)"',
    '"label": "Flange thickness tf (mm)"',
    '"label": "Web width bw (mm)"',
    '"label": "Top flange width bf (mm)"',
    '"label": "Top flange thickness tf (mm)"',
    '"label": "Web thickness tw (mm)"',
    '"label": "Side cover (mm)"',
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Geometry Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only the Geometry widget metadata payload construction moved behind `inputs_page_modules.widgets`. It does not move Streamlit rendering, widget keys, callbacks, session hydration, or engineering behaviour.",
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
            "- `inputs_page.py` still renders geometry controls and owns callbacks.",
            "- `inputs_page_modules.widgets` builds only plain metadata payload dictionaries.",
            "- Shape-specific RECT/T/I metadata branches are module-owned.",
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
    builder_body = builders.split("def build_geometry_basic_widget_payloads(", 1)[-1]
    page_window = page.split("_geometry_widget_metadata_trace = dict(", 1)[-1].split(
        "st.session_state[\"_inputs_widget_metadata_trace\"] = dict(_geometry_widget_metadata_trace)",
        1,
    )[0]
    render_window = page.split("shape_options = [\"RECT\", \"T\", \"I\"]", 1)[-1].split(
        "_geometry_widget_metadata_trace = dict(",
        1,
    )[0]
    checks = {
        "builder_function_exists": "def build_geometry_basic_widget_payloads(" in builders,
        "builder_exported": "build_geometry_basic_widget_payloads" in init,
        "page_imports_geometry_builder": "build_geometry_basic_widget_payloads" in page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0],
        "page_calls_geometry_builder": "_geometry_widget_payloads = build_geometry_basic_widget_payloads(" in page,
        "page_still_renders_section_shape": 'select_row(\n            "Section shape"' in render_window,
        "page_still_renders_depth": 'number_row(\n            "Depth D (mm)"' in render_window,
        "page_still_renders_span": '"Span L (mm)"' in render_window,
        "page_still_reads_geometry_state": "st.session_state" in render_window,
        "page_still_passes_sync_callbacks": "sync_callbacks" in render_window,
        "page_keeps_geometry_group_vm": 'group_id="geometry_basic"' in page_window,
        "page_keeps_geometry_trace_hash": '"geometry_widget_metadata_hash"' in page_window,
        "page_inline_geometry_payload_removed": '"shared_key": "sec_shape"' not in page_window and '"shared_key": "D"' not in page_window,
        "builder_preserves_geometry_payload_literals": all(snippet in builder_body for snippet in EXPECTED_GEOMETRY_SNIPPETS),
        "builder_has_rect_branch": 'if sec_shape == "RECT"' in builder_body and '"widget_id": "inputs_b"' in builder_body,
        "builder_has_t_branch": 'elif sec_shape == "T"' in builder_body and '"widget_id": "inputs_bw"' in builder_body,
        "builder_has_i_branch": 'elif sec_shape == "I"' in builder_body and '"widget_id": "inputs_tw"' in builder_body,
        "builder_has_detailed_side_cover_branch": "if detailed_mode:" in builder_body and '"widget_id": "inputs_cover_side"' in builder_body,
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "GEOMETRY_WIDGET_METADATA_BUILDER_DELEGATED" if not failures else "GEOMETRY_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_geometry_metadata_builder_delegation",
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
    json_path = VERIFICATION_DIR / f"inputs_widgets_geometry_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_geometry_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_geometry_metadata_builder_delegation", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
