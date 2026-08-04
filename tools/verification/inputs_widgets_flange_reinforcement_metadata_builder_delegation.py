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


EXPECTED_BASE_SHARED_KEYS: tuple[str, ...] = (
    "top_flange_reo_enabled",
    "top_flange_mirror_lr",
    "top_flange_left_count",
    "top_flange_left_dia",
    "top_flange_left_rows",
    "top_flange_left_row_spacing",
    "top_flange_left_clear_spacing_mode",
    "bot_flange_reo_enabled",
    "bot_flange_mirror_lr",
    "bot_flange_left_count",
    "bot_flange_left_dia",
    "bot_flange_left_rows",
    "bot_flange_left_row_spacing",
    "bot_flange_left_clear_spacing_mode",
)

EXPECTED_RIGHT_SHARED_KEYS: tuple[str, ...] = (
    "top_flange_right_count",
    "top_flange_right_dia",
    "top_flange_right_rows",
    "top_flange_right_row_spacing",
    "top_flange_right_clear_spacing_mode",
    "bot_flange_right_count",
    "bot_flange_right_dia",
    "bot_flange_right_rows",
    "bot_flange_right_row_spacing",
    "bot_flange_right_clear_spacing_mode",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _sample_builder_kwargs(*, top_mirror: bool, bottom_mirror: bool) -> dict[str, Any]:
    return {
        "reo_bar_diameters": [10, 12, 16, 20],
        "top_enabled_value": True,
        "top_mirror_value": top_mirror,
        "top_left_count_value": 2.0,
        "top_left_diameter_value": 16,
        "top_left_rows_value": 1.0,
        "top_left_row_spacing_value": 60.0,
        "top_left_clear_spacing_mode_value": "count",
        "top_right_count_value": 3.0,
        "top_right_diameter_value": 20,
        "top_right_rows_value": 2.0,
        "top_right_row_spacing_value": 75.0,
        "top_right_clear_spacing_mode_value": "spacing",
        "bottom_enabled_value": False,
        "bottom_mirror_value": bottom_mirror,
        "bottom_left_count_value": 1.0,
        "bottom_left_diameter_value": 20,
        "bottom_left_rows_value": 1.0,
        "bottom_left_row_spacing_value": 60.0,
        "bottom_left_clear_spacing_mode_value": "count",
        "bottom_right_count_value": 4.0,
        "bottom_right_diameter_value": 16,
        "bottom_right_rows_value": 2.0,
        "bottom_right_row_spacing_value": 90.0,
        "bottom_right_clear_spacing_mode_value": "spacing",
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Flange Reinforcement Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only the flange reinforcement widget metadata payload construction moved behind `inputs_page_modules.widgets`. It does not move Streamlit rendering, widget keys, callbacks, session hydration, or engineering behaviour.",
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
            "- `inputs_page.py` still renders flange reinforcement controls and owns callbacks.",
            "- `inputs_page_modules.widgets` builds only plain metadata payload dictionaries.",
            "- Mirror-dependent right-side payload inclusion is module-owned.",
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
    builder_body = builders.split("def build_flange_reinforcement_basic_widget_payloads(", 1)[-1]
    builder_body = builder_body.split("\ndef build_flange_transverse_basic_widget_payloads(", 1)[0]
    flange_payload_marker = (
        "_flange_widget_payloads = "
        if "_flange_widget_payloads = " in page
        else "flange_widget_payloads = "
    )
    flange_transverse_payload_marker = (
        "_flange_transverse_payloads = "
        if "_flange_transverse_payloads = " in page
        else "flange_transverse_payloads = "
    )
    page_window = page.split(flange_payload_marker, 1)[-1].split(
        flange_transverse_payload_marker,
        1,
    )[0]
    render_window = page.split("Flange reinforcement", 1)[-1].split(
        flange_payload_marker,
        1,
    )[0]
    trace_window = page.split(flange_payload_marker, 1)[-1].split(
        "st.session_state[\"_inputs_widget_metadata_trace\"] = dict(",
        1,
    )[0]
    import_window = page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0]

    from inputs_page_modules.widgets import build_flange_reinforcement_basic_widget_payloads

    mirror_on_payloads = build_flange_reinforcement_basic_widget_payloads(
        **_sample_builder_kwargs(top_mirror=True, bottom_mirror=True)
    )
    mirror_off_payloads = build_flange_reinforcement_basic_widget_payloads(
        **_sample_builder_kwargs(top_mirror=False, bottom_mirror=False)
    )
    mirror_on_keys = tuple(str(row.get("shared_key") or "") for row in mirror_on_payloads)
    mirror_off_keys = tuple(str(row.get("shared_key") or "") for row in mirror_off_payloads)
    checks = {
        "builder_function_exists": "def build_flange_reinforcement_basic_widget_payloads(" in builders,
        "builder_exported": "build_flange_reinforcement_basic_widget_payloads" in init,
        "page_imports_flange_reinforcement_builder": "build_flange_reinforcement_basic_widget_payloads" in import_window,
        "page_calls_flange_reinforcement_builder": (
            "_flange_widget_payloads = build_flange_reinforcement_basic_widget_payloads(" in page
            or "flange_widget_payloads = build_flange_reinforcement_basic_widget_payloads(" in page
        ),
        "page_still_renders_top_enable": '"Enable top flange bars"' in render_window,
        "page_still_renders_bottom_enable": '"Enable bottom flange bars"' in render_window,
        "page_still_renders_mirror_controls": '"Mirror top left/right"' in render_window
        and '"Mirror bottom left/right"' in render_window,
        "page_still_reads_flange_state": "st.session_state" in page_window,
        "page_still_passes_sync_callbacks": "sync_callbacks" in render_window,
        "page_keeps_flange_group_vm": 'group_id="flange_reinforcement_basic"' in trace_window,
        "page_keeps_flange_trace_hash": '"flange_reinforcement_basic_widget_metadata_hash"' in trace_window,
        "page_inline_flange_payload_removed": '"shared_key": "top_flange_reo_enabled"' not in page_window
        and '"shared_key": "top_flange_right_count"' not in page_window
        and '"shared_key": "bot_flange_right_count"' not in page_window,
        "builder_base_keys_match": mirror_on_keys == EXPECTED_BASE_SHARED_KEYS,
        "builder_mirror_off_adds_right_keys": mirror_off_keys
        == EXPECTED_BASE_SHARED_KEYS + EXPECTED_RIGHT_SHARED_KEYS,
        "builder_uses_reo_bar_diameters_from_page": "reo_bar_diameters" in builder_body
        and "diameters = list(reo_bar_diameters or ())" in builder_body,
        "builder_owns_mirror_dependent_payload_inclusion": "if not bool(top_mirror_value):" in builder_body
        and "if not bool(bottom_mirror_value):" in builder_body,
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "FLANGE_REINFORCEMENT_WIDGET_METADATA_BUILDER_DELEGATED"
        if not failures
        else "FLANGE_REINFORCEMENT_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_widgets_flange_reinforcement_metadata_builder_delegation",
        "timestamp": timestamp,
        "decision": decision,
        "mirror_on_payload_count": len(mirror_on_payloads),
        "mirror_off_payload_count": len(mirror_off_payloads),
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
    json_path = VERIFICATION_DIR / f"inputs_widgets_flange_reinforcement_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_flange_reinforcement_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        "inputs_widgets_flange_reinforcement_metadata_builder_delegation",
        "PASS" if not failures else "FAIL",
    )
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
