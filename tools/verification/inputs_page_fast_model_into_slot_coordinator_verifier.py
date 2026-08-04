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


class FakeContext:
    def __init__(self, label: str, calls: list[dict[str, Any]]) -> None:
        self.label = label
        self.calls = calls

    def __enter__(self):
        self.calls.append({"event": "enter", "label": self.label})
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.calls.append({"event": "exit", "label": self.label})
        return False


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_fast_model_into_slot_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_fast_model_into_slot_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "time": inputs_page.time,
        "st": inputs_page.st,
        "_resolved_inputs_model_state": inputs_page._resolved_inputs_model_state,
        "_inputs_pre_widget_trace": inputs_page._inputs_pre_widget_trace,
        "_render_fast_model_block": inputs_page._render_fast_model_block,
        "render_timing_mark": inputs_page.render_timing_mark,
    }
    failures: list[str] = []
    context_calls: list[dict[str, Any]] = []
    phase_calls: list[dict[str, Any]] = []
    pre_widget_calls: list[dict[str, Any]] = []
    render_block_calls: list[dict[str, Any]] = []
    timing_calls: list[dict[str, Any]] = []
    latency_calls: list[dict[str, Any]] = []
    perf_values = iter([100.0, 100.012, 100.02, 100.08])

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def perf_counter() -> float:
        return next(perf_values)

    def phase_trace(label: str, *args, **payload) -> None:
        phase_calls.append({"label": label, "args": list(args), "payload": dict(payload)})

    def update_latency(**payload) -> None:
        latency_calls.append(dict(payload))

    def resolved_model_state():
        return (
            {
                "bot_bar_coords": [(1, 2), (3, 4)],
                "top_bar_coords": [(5, 6)],
                "bot_row_1_bars": 3,
                "bot1_count": 3,
                "top_row_1_bars": 2,
                "top1_count": 2,
                "lig_d": 12,
                "lig_legs": 4,
                "shear_truth_governing_check_name": "Vuc",
                "shear_truth_governing_reason": "unit_reason",
            },
            {
                "model_overlay_lig_d": 12,
                "model_overlay_lig_legs": 4,
                "model_overlay_s_lig": 180,
                "fast_model_reo_widget_overlay_applied": True,
                "fast_model_reo_widget_overlay_suppressed": False,
                "fast_model_reo_widget_overlay_reason": "unit_overlay",
                "fast_model_reo_widget_overlay_keys": ["lig_d", "lig_legs"],
            },
        )

    def pre_widget_trace(label: str, **payload) -> None:
        pre_widget_calls.append({"label": label, "payload": dict(payload)})

    def render_fast_model_block(sync_callbacks, *, model_state) -> None:
        render_block_calls.append(
            {"sync_callbacks": dict(sync_callbacks), "model_state": dict(model_state)}
        )

    def timing_mark(label: str, **payload) -> None:
        timing_calls.append({"label": label, "payload": dict(payload)})

    fake_st = SimpleNamespace(
        session_state={
            "bot_row_1_bars": 3,
            "inputs_bot_row_1_bars": 3,
            "top_row_1_bars": 2,
            "inputs_top_row_1_bars": 2,
            "lig_d": 12,
            "inputs_lig_d": 12,
            "lig_legs": 4,
            "inputs_lig_legs": 4,
        },
        container=lambda: FakeContext("container", context_calls),
        markdown=lambda body, **payload: context_calls.append(
            {"event": "markdown", "body": body, "payload": dict(payload)}
        ),
    )

    try:
        inputs_page.time = SimpleNamespace(perf_counter=perf_counter)
        inputs_page.st = fake_st
        inputs_page._resolved_inputs_model_state = resolved_model_state
        inputs_page._inputs_pre_widget_trace = pre_widget_trace
        inputs_page._render_fast_model_block = render_fast_model_block
        inputs_page.render_timing_mark = timing_mark

        no_op_render_state = {"rendered": False}
        inputs_page.render_inputs_fast_model_into_slot_coordinator(
            model_slot=None,
            render_order="no_op",
            render_trace_started=99.0,
            phase5c_render_trace_fn=phase_trace,
            update_user_latency_metrics_fn=update_latency,
            sync_callbacks={"sync": "callback"},
            fast_model_render_state=no_op_render_state,
        )
        if no_op_render_state != {"rendered": False}:
            failures.append("no_op_render_state_changed")
        if phase_calls or pre_widget_calls or render_block_calls or timing_calls or latency_calls:
            failures.append("no_op_emitted_calls")

        render_state = {"rendered": False}
        inputs_page.render_inputs_fast_model_into_slot_coordinator(
            model_slot=FakeContext("model_slot", context_calls),
            render_order="unit_render_order",
            render_trace_started=99.5,
            phase5c_render_trace_fn=phase_trace,
            update_user_latency_metrics_fn=update_latency,
            sync_callbacks={"sync": "callback"},
            fast_model_render_state=render_state,
        )
    finally:
        _restore()

    phase_labels = [call["label"] for call in phase_calls]
    if phase_labels != [
        "fast_model_state_prepare_start",
        "fast_model_state_prepare_complete",
        "fast_model_render_complete",
    ]:
        failures.append(f"phase_labels_mismatch:{phase_labels}")
    if not phase_calls or phase_calls[1]["payload"] != {
        "model_bot_bar_coord_count": 2,
        "model_top_bar_coord_count": 1,
    }:
        failures.append(f"state_prepare_payload_mismatch:{phase_calls}")
    session_debug = fake_st.session_state.get("_inputs_fast_model_state_debug")
    if session_debug != {
        "model_overlay_lig_d": 12,
        "model_overlay_lig_legs": 4,
        "model_overlay_s_lig": 180,
        "fast_model_reo_widget_overlay_applied": True,
        "fast_model_reo_widget_overlay_suppressed": False,
        "fast_model_reo_widget_overlay_reason": "unit_overlay",
        "fast_model_reo_widget_overlay_keys": ["lig_d", "lig_legs"],
        "summary_governing_check_name": "Vuc",
        "summary_governing_reason": "unit_reason",
        "fast_model_uses_overlay_state": True,
        "fast_model_overlay_lig_d": 12,
        "fast_model_overlay_lig_legs": 4,
        "fast_model_overlay_s_lig": 180,
        "fast_model_fingerprint_includes_shear": True,
        "fast_model_render_order": "unit_render_order",
    }:
        failures.append(f"session_debug_mismatch:{session_debug}")
    if len(pre_widget_calls) != 1:
        failures.append(f"pre_widget_call_count_mismatch:{len(pre_widget_calls)}")
    elif pre_widget_calls[0]["label"] != "render_inputs.fast_model_state":
        failures.append(f"pre_widget_label_mismatch:{pre_widget_calls[0]}")
    else:
        payload = pre_widget_calls[0]["payload"]
        expected_subset = {
            "elapsed_ms": 512.0,
            "shared_bot_row_1_bars": 3,
            "widget_inputs_bot_row_1_bars": 3,
            "model_bot_row_1_bars": 3,
            "model_bot1_count": 3,
            "model_bot_bar_coord_count": 2,
            "shared_top_row_1_bars": 2,
            "widget_inputs_top_row_1_bars": 2,
            "model_top_row_1_bars": 2,
            "model_top1_count": 2,
            "model_top_bar_coord_count": 1,
            "shared_lig_d": 12,
            "widget_inputs_lig_d": 12,
            "model_lig_d": 12,
            "shared_lig_legs": 4,
            "widget_inputs_lig_legs": 4,
            "model_lig_legs": 4,
            "overlay_applied": True,
            "overlay_suppressed": False,
            "overlay_reason": "unit_overlay",
            "overlay_keys": ["lig_d", "lig_legs"],
        }
        if payload != expected_subset:
            failures.append(f"pre_widget_payload_mismatch:{payload}")
    if len(render_block_calls) != 1:
        failures.append(f"render_block_call_count_mismatch:{len(render_block_calls)}")
    elif render_block_calls[0]["sync_callbacks"] != {"sync": "callback"}:
        failures.append(f"render_block_sync_callbacks_mismatch:{render_block_calls}")
    if timing_calls != [
        {
            "label": "inputs_page.diagram_render.end",
            "payload": {
                "duration_ms": 80.0,
                "mode": "fast",
                "deferred": False,
                "render_order": "unit_render_order",
            },
        }
    ]:
        failures.append(f"timing_calls_mismatch:{timing_calls}")
    if latency_calls != [
        {
            "diagram_render_ms": 80.0,
            "diagram_render_mode": "fast",
            "fast_mode_diagram_deferred": False,
        }
    ]:
        failures.append(f"latency_calls_mismatch:{latency_calls}")
    if render_state != {"rendered": True}:
        failures.append(f"render_state_mismatch:{render_state}")
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def _render_fast_model_into_slot" in source:
        failures.append("nested_fast_model_helper_still_present")

    payload = {
        "verifier": "inputs_page_fast_model_into_slot_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "phase_calls": phase_calls,
        "pre_widget_calls": pre_widget_calls,
        "render_block_calls": render_block_calls,
        "timing_calls": timing_calls,
        "latency_calls": latency_calls,
        "context_calls": context_calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Fast Model Into Slot Coordinator Verifier",
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
