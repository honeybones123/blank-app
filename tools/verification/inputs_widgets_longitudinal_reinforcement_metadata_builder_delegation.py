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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    return source.split(marker, 1)[1].split("\ndef ", 1)[0]


def _page_longitudinal_helper_window(page: str) -> str:
    marker = "def _record_longitudinal_reinforcement_widget_metadata("
    if marker not in page:
        return ""
    return page.split(marker, 1)[1].split("    # --- Bottom reo", 1)[0]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Longitudinal Reinforcement Metadata Builder Delegation",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves only bottom/top longitudinal reinforcement widget metadata payload construction moved behind `inputs_page_modules.widgets`. The page still owns Streamlit rendering, session reads, callbacks, rerun handling, and trace storage.",
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
            "- `inputs_page.py` still reads row count and widget values from session state.",
            "- `inputs_page_modules.widgets` builds only plain metadata payload dictionaries.",
            "- Count mode still emits bars metadata; spacing mode still emits spacing metadata.",
            "- Bar-count option `1` remains excluded.",
            "- The live widget renderer is not cut over.",
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
    builder_body = _function_body(builders, "build_longitudinal_reinforcement_widget_payloads")
    page_window = _page_longitudinal_helper_window(page)
    import_window = page.split("from inputs_page_modules.widgets import", 1)[-1].split(")", 1)[0]

    from inputs_page_modules.widgets import build_longitudinal_reinforcement_widget_payloads

    bottom_count_payloads = build_longitudinal_reinforcement_widget_payloads(
        section="bot",
        cover_widget_key="inputs_cover_bot",
        cover_shared_key="cover_bot",
        cover_label="Bottom cover (mm)",
        cover_default=40.0,
        cover_help_text="Clear cover to the bottom bars.",
        row_values=[
            {"row_index": 1, "mode": "Count", "bars": 4, "spacing": 200, "diameter": 20},
            {"row_index": 2, "mode": "Spacing", "bars": 0, "spacing": 175, "diameter": 16},
        ],
        layout_mode_options=("Count", "Spacing"),
        count_options=(0, 1, 2, 3, 4, 5),
        spacing_options=(125, 150, 175, 200),
        bar_diameter_options=(12, 16, 20),
        diameter_label="Dia",
    )
    top_count_payloads = build_longitudinal_reinforcement_widget_payloads(
        section="top",
        cover_widget_key="inputs_cover_top",
        cover_shared_key="cover_top",
        cover_label="Top cover (mm)",
        cover_default=40.0,
        cover_help_text="Clear cover to the top bars.",
        row_values=[
            {"row_index": 1, "mode": "Count", "bars": 2, "spacing": 200, "diameter": 16},
        ],
        layout_mode_options=("Count", "Spacing"),
        count_options=(0, 1, 2, 3, 4, 5),
        spacing_options=(125, 150, 175, 200),
        bar_diameter_options=(12, 16, 20),
        diameter_label="Dia",
    )
    bottom_shared_keys = tuple(str(row.get("shared_key") or "") for row in bottom_count_payloads)
    top_group_ids = tuple(str(row.get("group_id") or "") for row in top_count_payloads)
    bottom_group_ids = tuple(str(row.get("group_id") or "") for row in bottom_count_payloads)
    bottom_labels = tuple(str(row.get("label") or "") for row in bottom_count_payloads)
    bars_options = next(
        tuple(row.get("options") or ()) for row in bottom_count_payloads if row.get("shared_key") == "bot_row_1_bars"
    )

    checks = {
        "builder_function_exists": "def build_longitudinal_reinforcement_widget_payloads(" in builders,
        "builder_exported": "build_longitudinal_reinforcement_widget_payloads" in init,
        "page_imports_longitudinal_builder": "build_longitudinal_reinforcement_widget_payloads" in import_window,
        "page_calls_longitudinal_builder": "payloads = build_longitudinal_reinforcement_widget_payloads(" in page_window,
        "page_still_reads_session_row_count": "st.session_state.get(" in page_window
        and "inputs_{section_norm}_row_count" in page_window,
        "page_still_reads_session_row_values": "mode_value = str(" in page_window
        and "mode_key," in page_window
        and "bars_key," in page_window
        and "spacing_key," in page_window
        and "dia_key," in page_window,
        "page_still_builds_group_view_model": "build_inputs_widget_group_view_model(" in page_window
        and "group_id=group_id" in page_window,
        "page_still_records_bottom_top_hashes": 'f"{section_norm}_longitudinal_widget_metadata_hash"' in page_window
        and 'f"{section_norm}_longitudinal_widget_metadata_count"' in page_window
        and 'f"{section_norm}_longitudinal_widget_keys"' in page_window,
        "page_inline_payload_literals_removed": '"widget_id": mode_key' not in page_window
        and '"widget_id": bars_key' not in page_window
        and '"widget_id": spacing_key' not in page_window
        and '"widget_id": dia_key' not in page_window,
        "bottom_group_ids_match": set(bottom_group_ids) == {"bottom_longitudinal_reinforcement"},
        "top_group_ids_match": set(top_group_ids) == {"top_longitudinal_reinforcement"},
        "bottom_payload_shared_keys_match": bottom_shared_keys
        == (
            "cover_bot",
            "bot_row_1_mode",
            "bot_row_1_bars",
            "bot_row_1_dia",
            "bot_row_2_mode",
            "bot_row_2_spacing",
            "bot_row_2_dia",
        ),
        "count_mode_emits_bars_not_spacing": "bot_row_1_bars" in bottom_shared_keys
        and "bot_row_1_spacing" not in bottom_shared_keys,
        "spacing_mode_emits_spacing_not_bars": "bot_row_2_spacing" in bottom_shared_keys
        and "bot_row_2_bars" not in bottom_shared_keys,
        "count_options_exclude_one": 1 not in tuple(int(option) for option in bars_options),
        "labels_preserved": bottom_labels == ("Bottom cover (mm)", "Layout", "Bars", "Dia", "Layout", "Spacing", "Dia"),
        "builder_does_not_import_streamlit": "import streamlit" not in builders and "from streamlit" not in builders,
        "builder_does_not_read_session_state": "session_state" not in builder_body,
        "builder_does_not_route_apply": "route_apply" not in builder_body and "apply_payload" not in builder_body,
        "live_widget_renderer_not_cut_over": '"live_widget_renderer_cutover": False' in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "LONGITUDINAL_REINFORCEMENT_WIDGET_METADATA_BUILDER_DELEGATED"
        if not failures
        else "LONGITUDINAL_REINFORCEMENT_WIDGET_METADATA_DELEGATION_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_widgets_longitudinal_reinforcement_metadata_builder_delegation",
        "timestamp": timestamp,
        "decision": decision,
        "bottom_payload_count": len(bottom_count_payloads),
        "top_payload_count": len(top_count_payloads),
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
    json_path = VERIFICATION_DIR / f"inputs_widgets_longitudinal_reinforcement_metadata_builder_delegation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_longitudinal_reinforcement_metadata_builder_delegation_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        "inputs_widgets_longitudinal_reinforcement_metadata_builder_delegation",
        "PASS" if not failures else "FAIL",
    )
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
