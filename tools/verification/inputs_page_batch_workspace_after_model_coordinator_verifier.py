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
    json_path = ARTIFACT_DIR / f"inputs_page_batch_workspace_after_model_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_batch_workspace_after_model_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "render_timing_mark": inputs_page.render_timing_mark,
        "render_batch_design_page": inputs_page.render_batch_design_page,
        "_apply_canonical_convenience_resync_to_shared": inputs_page._apply_canonical_convenience_resync_to_shared,
        "persist_active_beam_from_shared": inputs_page.persist_active_beam_from_shared,
        "st": inputs_page.st,
        "session_state_final_log": sys.modules.get("session_state_final_log"),
    }
    failures: list[str] = []
    timing_calls: list[dict[str, Any]] = []
    latency_calls: list[dict[str, Any]] = []
    render_contexts: list[Any] = []
    resync_calls: list[dict[str, Any]] = []
    persist_calls: list[str] = []
    rerun_log_calls: list[dict[str, Any]] = []

    def _restore() -> None:
        inputs_page.render_timing_mark = originals["render_timing_mark"]
        inputs_page.render_batch_design_page = originals["render_batch_design_page"]
        inputs_page._apply_canonical_convenience_resync_to_shared = originals[
            "_apply_canonical_convenience_resync_to_shared"
        ]
        inputs_page.persist_active_beam_from_shared = originals["persist_active_beam_from_shared"]
        inputs_page.st = originals["st"]
        if originals["session_state_final_log"] is None:
            sys.modules.pop("session_state_final_log", None)
        else:
            sys.modules["session_state_final_log"] = originals["session_state_final_log"]

    def timing_mark(label: str, **payload) -> None:
        timing_calls.append({"label": label, "payload": dict(payload)})

    def update_latency(**payload) -> None:
        latency_calls.append(dict(payload))

    def render_batch(context) -> None:
        render_contexts.append(context)

    def resync(**payload) -> None:
        resync_calls.append(dict(payload))

    def persist() -> None:
        persist_calls.append("persist")

    fake_ssl = SimpleNamespace(
        append_session_state_final_log=lambda label, payload: rerun_log_calls.append(
            {"event": "append", "label": label, "payload": dict(payload)}
        ),
        ssl_record_rerun_trigger=lambda label: rerun_log_calls.append(
            {"event": "record", "label": label}
        ),
    )

    try:
        inputs_page.render_timing_mark = timing_mark
        inputs_page.render_batch_design_page = render_batch
        inputs_page._apply_canonical_convenience_resync_to_shared = resync
        inputs_page.persist_active_beam_from_shared = persist
        inputs_page.st = SimpleNamespace(session_state={"_beam_skip_auto_persist_once": True})
        sys.modules["session_state_final_log"] = fake_ssl

        inputs_page.render_inputs_batch_design_workspace_after_model_coordinator(
            ss={"session": "state"},
            inputs_elapsed_ms_fn=lambda: 12.345,
            update_user_latency_metrics_fn=update_latency,
            beam_order=("beam-1", "beam-2"),
            active_beam_id="beam-2",
            beam_labels={"beam-1": "A", "beam-2": "B"},
            set_active_beam=lambda value: value,
            add_new_beam_record_fn=lambda: "add",
            duplicate_active_beam_record_fn=lambda: "duplicate",
            delete_beam_record_fn=lambda beam_id: beam_id,
            reset_app_to_clean_starter_workspace_fn=lambda: "reset",
            force_inputs_apply_refresh_cycle_fn=lambda reason: reason,
        )
        if render_contexts:
            context = render_contexts[0]
            context.log_rerun("unit_reason")
            context.save_active_to_table()
    finally:
        _restore()

    if timing_calls[:2] != [
        {
            "label": "inputs_page.first_body_marker_emitted",
            "payload": {"marker": "Batch design", "elapsed_ms": 12.345},
        },
        {
            "label": "inputs_page.widget_section_render_start",
            "payload": {"section": "batch_design"},
        },
    ]:
        failures.append(f"timing_calls_mismatch:{timing_calls}")
    if latency_calls != [{"first_visible_batch_design_marker_ms": 12.345}]:
        failures.append(f"latency_calls_mismatch:{latency_calls}")
    if len(render_contexts) != 1:
        failures.append(f"render_context_count_mismatch:{len(render_contexts)}")
    else:
        context = render_contexts[0]
        if context.session_state != {"session": "state"}:
            failures.append("context_session_state_mismatch")
        if context.beam_order != ["beam-1", "beam-2"]:
            failures.append(f"context_beam_order_mismatch:{context.beam_order}")
        if context.active_beam_id != "beam-2":
            failures.append("context_active_beam_mismatch")
        if not callable(getattr(context.design_brain_adapter, "run_case", None)):
            failures.append("context_design_brain_adapter_missing_run_case")
    if rerun_log_calls != [
        {
            "event": "append",
            "label": "beam_load_triggered_rerun",
            "payload": {"reason": "unit_reason", "hydration_layer": "render_inputs"},
        },
        {"event": "record", "label": "beam_load_triggered_rerun"},
    ]:
        failures.append(f"rerun_log_calls_mismatch:{rerun_log_calls}")
    if resync_calls != [{"source": "beam_manager:save_active_to_table"}]:
        failures.append(f"resync_calls_mismatch:{resync_calls}")
    if persist_calls != ["persist"]:
        failures.append(f"persist_calls_mismatch:{persist_calls}")

    payload = {
        "verifier": "inputs_page_batch_workspace_after_model_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "timing_calls": timing_calls,
        "latency_calls": latency_calls,
        "rerun_log_calls": rerun_log_calls,
        "resync_calls": resync_calls,
        "persist_calls": persist_calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Batch Workspace After Model Coordinator Verifier",
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
