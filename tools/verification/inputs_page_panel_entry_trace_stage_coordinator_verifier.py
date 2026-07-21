from __future__ import annotations

import json
import os
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
    json_path = ARTIFACT_DIR / f"inputs_page_panel_entry_trace_stage_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_panel_entry_trace_stage_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "time": inputs_page.time,
        "_inputs_pre_widget_trace": inputs_page._inputs_pre_widget_trace,
        "_phase5c_latency_trace": inputs_page._phase5c_latency_trace,
        "stage_debug_env": os.environ.get("CODEX_DG_STAGE_DEBUG"),
    }
    failures: list[str] = []
    trace_calls: list[dict[str, Any]] = []
    latency_calls: list[dict[str, Any]] = []

    def _restore() -> None:
        inputs_page.st = originals["st"]
        inputs_page.time = originals["time"]
        inputs_page._inputs_pre_widget_trace = originals["_inputs_pre_widget_trace"]
        inputs_page._phase5c_latency_trace = originals["_phase5c_latency_trace"]
        if originals["stage_debug_env"] is None:
            os.environ.pop("CODEX_DG_STAGE_DEBUG", None)
        else:
            os.environ["CODEX_DG_STAGE_DEBUG"] = str(originals["stage_debug_env"])

    perf_values = iter([100.0, 100.1234])

    def fake_perf_counter() -> float:
        return next(perf_values)

    def fake_trace(label: str, **payload) -> None:
        trace_calls.append({"label": label, "payload": dict(payload)})

    def fake_latency(label: str, **payload) -> None:
        latency_calls.append({"label": label, "payload": dict(payload)})

    scope = {
        "guidance_items_raw": [{"raw": 1}, {"raw": 2}],
        "guidance_items": [{"item": 1}],
        "collapsed_guidance_items": [1, 2, 3],
        "render_plan": {"visible_guidance_items": [1, 2, 3, 4]},
        "_primary_render_items": [1, 2, 3, 4, 5],
    }

    try:
        os.environ.pop("CODEX_DG_STAGE_DEBUG", None)
        inputs_page.st = SimpleNamespace(
            session_state={
                inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY: {
                    "family": "BENDING",
                    "updates": {"a": 1, "b": 2},
                }
            }
        )
        inputs_page.time = SimpleNamespace(perf_counter=fake_perf_counter)
        inputs_page._inputs_pre_widget_trace = fake_trace
        inputs_page._phase5c_latency_trace = fake_latency

        panel_trace_started, stage = inputs_page.render_design_guide_panel_entry_trace_and_stage_coordinator(
            scope_getter=lambda: scope,
        )
        stage("after_compute")
    finally:
        _restore()

    if panel_trace_started != 100.0:
        failures.append(f"panel_trace_started_mismatch:{panel_trace_started}")

    expected_latency = [
        {
            "label": "design_guide_panel_enter",
            "payload": {
                "existing_primary_apply_payload": True,
                "existing_payload_family": "BENDING",
            },
        },
        {
            "label": "post_cta_panel_reentry",
            "payload": {
                "existing_payload_family": "BENDING",
                "existing_update_count": 2,
            },
        },
    ]
    if latency_calls != expected_latency:
        failures.append(f"latency_calls_mismatch:{latency_calls}")

    if not trace_calls or trace_calls[0] != {"label": "_render_fast_design_guidance_panel.enter", "payload": {}}:
        failures.append(f"entry_trace_mismatch:{trace_calls[:1]}")
    expected_stage_payload = {
        "elapsed_ms": 123.4,
        "guidance_items_raw_count": 2,
        "guidance_items_count": 1,
        "collapsed_guidance_items_count": 3,
        "render_plan_visible_count": 4,
        "primary_render_items_count": 5,
    }
    if len(trace_calls) < 2 or trace_calls[1] != {
        "label": "_render_fast_design_guidance_panel.stage.after_compute",
        "payload": expected_stage_payload,
    }:
        failures.append(f"stage_trace_mismatch:{trace_calls[1:]}")

    payload = {
        "verifier": "inputs_page_panel_entry_trace_stage_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "trace_calls": trace_calls,
        "latency_calls": latency_calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Panel Entry Trace Stage Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Trace Calls",
                "",
                *(f"- `{call['label']}` {call['payload']}" for call in trace_calls),
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
