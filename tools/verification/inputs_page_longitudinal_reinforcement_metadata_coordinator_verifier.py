from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_longitudinal_reinforcement_metadata_coordinator_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_longitudinal_reinforcement_metadata_coordinator_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "st",
        "build_longitudinal_reinforcement_widget_payloads",
        "build_inputs_widget_group_view_model",
        "_inputs_pre_widget_trace",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    payload_builder_calls: list[dict[str, Any]] = []
    group_builder_calls: list[dict[str, Any]] = []
    trace_calls: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def payload_builder(**payload):
        payload_builder_calls.append(dict(payload))
        return [
            SimpleNamespace(widget_key=f"{payload['section']}_cover"),
            SimpleNamespace(widget_key=f"{payload['section']}_row_1"),
        ]

    def group_builder(*, group_id, widgets):
        group_builder_calls.append(
            {"group_id": group_id, "widget_keys": [widget.widget_key for widget in widgets]}
        )
        return SimpleNamespace(display_hash=f"hash:{group_id}", widgets=list(widgets))

    def pre_widget_trace(label: str, **payload) -> None:
        trace_calls.append({"label": label, "payload": dict(payload)})

    try:
        inputs_page.build_longitudinal_reinforcement_widget_payloads = payload_builder
        inputs_page.build_inputs_widget_group_view_model = group_builder
        inputs_page._inputs_pre_widget_trace = pre_widget_trace
        inputs_page.st = SimpleNamespace(
            session_state={
                "_inputs_widget_metadata_trace": {
                    "inputs_widget_keys": ["existing_key"],
                    "inputs_widget_group_hashes": {"existing_group": "existing_hash"},
                },
                "inputs_bot_row_count": 9,
                "inputs_bot_row_1_mode": "Spacing",
                "inputs_bot_row_1_bars": 5,
                "inputs_bot_row_1_spacing": 150,
                "inputs_bot_row_1_dia": 24,
                "bot_row_2_bars": 6,
                "bot_row_2_spacing": 175,
                "bot_row_2_dia": 20,
            }
        )
        inputs_page.render_inputs_longitudinal_reinforcement_widget_metadata_coordinator(
            section="bot",
            cover_widget_key="inputs_cvr",
            cover_shared_key="cvr",
            cover_label="Cover",
            cover_default=40.0,
            cover_help_text="cover help",
        )

        if len(payload_builder_calls) != 1:
            failures.append(f"payload_builder_call_count_mismatch:{len(payload_builder_calls)}")
        else:
            call = payload_builder_calls[0]
            if call.get("section") != "bot":
                failures.append(f"payload_section_mismatch:{call}")
            if call.get("cover_widget_key") != "inputs_cvr":
                failures.append(f"payload_cover_widget_key_mismatch:{call}")
            row_values = call.get("row_values")
            if row_values != [
                {"row_index": 1, "mode": "Spacing", "bars": 5, "spacing": 150, "diameter": 24},
                {"row_index": 2, "mode": "Count", "bars": 6, "spacing": 175, "diameter": 20},
                {"row_index": 3, "mode": "Count", "bars": 0, "spacing": 200, "diameter": 20},
                {"row_index": 4, "mode": "Count", "bars": 0, "spacing": 200, "diameter": 20},
            ]:
                failures.append(f"row_values_mismatch:{row_values}")
        if group_builder_calls != [
            {
                "group_id": "bottom_longitudinal_reinforcement",
                "widget_keys": ["bot_cover", "bot_row_1"],
            }
        ]:
            failures.append(f"group_builder_calls_mismatch:{group_builder_calls}")
        trace = dict(inputs_page.st.session_state.get("_inputs_widget_metadata_trace") or {})
        expected_keys = ["existing_key", "bot_cover", "bot_row_1"]
        if trace.get("inputs_widget_keys") != expected_keys:
            failures.append(f"trace_widget_keys_mismatch:{trace}")
        if trace.get("inputs_widget_metadata_count") != 3:
            failures.append(f"trace_widget_count_mismatch:{trace}")
        if trace.get("bot_longitudinal_widget_metadata_hash") != (
            "hash:bottom_longitudinal_reinforcement"
        ):
            failures.append(f"trace_hash_mismatch:{trace}")
        if trace.get("inputs_widget_group_ids") != [
            "bottom_longitudinal_reinforcement",
            "existing_group",
        ]:
            failures.append(f"trace_group_ids_mismatch:{trace}")
        if not trace_calls or trace_calls[-1]["label"] != "inputs_widget_metadata_trace":
            failures.append(f"trace_call_missing:{trace_calls}")

        payload_builder_calls.clear()
        group_builder_calls.clear()
        trace_calls.clear()

        def failing_group_builder(*, group_id, widgets):
            raise RuntimeError("unit metadata failure")

        inputs_page.build_inputs_widget_group_view_model = failing_group_builder
        inputs_page.st = SimpleNamespace(session_state={"inputs_top_row_count": 1})
        inputs_page.render_inputs_longitudinal_reinforcement_widget_metadata_coordinator(
            section="top",
            cover_widget_key="inputs_top_cover",
            cover_shared_key="top_cover",
            cover_label="Top cover",
            cover_default=45.0,
            cover_help_text="top cover help",
        )
        error_trace = dict(inputs_page.st.session_state.get("_inputs_widget_metadata_trace") or {})
        if error_trace.get("inputs_widget_metadata_trace_built") is not False:
            failures.append(f"error_trace_built_flag_mismatch:{error_trace}")
        if error_trace.get("top_longitudinal_widget_metadata_trace_error") != (
            "unit metadata failure"
        ):
            failures.append(f"error_trace_message_mismatch:{error_trace}")
        if not trace_calls or trace_calls[-1]["label"] != "inputs_widget_metadata_trace":
            failures.append(f"error_trace_call_missing:{trace_calls}")
    finally:
        _restore()

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def _record_longitudinal_reinforcement_widget_metadata" in source:
        failures.append("nested_longitudinal_metadata_helper_still_present")
    if "render_inputs_longitudinal_reinforcement_widget_metadata_coordinator" not in source:
        failures.append("longitudinal_metadata_coordinator_missing")

    payload = {
        "verifier": "inputs_page_longitudinal_reinforcement_metadata_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "payload_builder_calls": payload_builder_calls,
        "group_builder_calls": group_builder_calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Longitudinal Reinforcement Metadata Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
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
