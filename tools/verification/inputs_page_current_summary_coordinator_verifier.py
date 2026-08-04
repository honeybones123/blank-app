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


class FakeSummaryContainer:
    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self.calls = calls

    def container(self):
        return FakeContext("summary_container", self.calls)


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_current_summary_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_current_summary_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "time",
        "st",
        "_summary_card_css",
        "render_timing_mark",
        "ux_probe_record",
        "inputs_show_landing_dashboard",
        "_record_inputs_stable_render_reuse_trace",
        "_stable_final_publication_hash",
        "_design_guide_sidebar_debug_enabled",
        "render_landing_card",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    context_calls: list[dict[str, Any]] = []
    markdown_calls: list[dict[str, Any]] = []
    timing_calls: list[dict[str, Any]] = []
    probe_calls: list[dict[str, Any]] = []
    stable_reuse_calls: list[dict[str, Any]] = []
    phase_calls: list[dict[str, Any]] = []
    mark_calls: list[str] = []
    latency_calls: list[dict[str, Any]] = []
    summary_render_calls: list[str] = []
    landing_calls: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def timing_mark(label: str, **payload) -> None:
        timing_calls.append({"label": label, "payload": dict(payload)})

    def probe_record(label: str, **payload) -> None:
        probe_calls.append({"label": label, "payload": dict(payload)})

    def stable_reuse_trace(**payload) -> None:
        stable_reuse_calls.append(dict(payload))

    def phase_trace(label: str, *args, **payload) -> None:
        phase_calls.append({"label": label, "args": list(args), "payload": dict(payload)})

    def update_latency(**payload) -> None:
        latency_calls.append(dict(payload))

    def mark(label: str) -> None:
        mark_calls.append(label)

    def render_summary() -> None:
        summary_render_calls.append("summary")

    def render_landing_card(**payload) -> None:
        landing_calls.append(dict(payload))

    try:
        inputs_page._summary_card_css = lambda: "/* summary css */"
        inputs_page.render_timing_mark = timing_mark
        inputs_page.ux_probe_record = probe_record
        inputs_page._record_inputs_stable_render_reuse_trace = stable_reuse_trace
        inputs_page._stable_final_publication_hash = lambda value: "result_hash"
        inputs_page._design_guide_sidebar_debug_enabled = lambda: False
        inputs_page.render_landing_card = render_landing_card

        perf_values = iter([10.0])
        inputs_page.time = SimpleNamespace(perf_counter=lambda: next(perf_values))
        inputs_page.inputs_show_landing_dashboard = lambda: False
        inputs_page.st = SimpleNamespace(
            session_state={
                "_inputs_first_paint_cached_summary_reuse_debug": {
                    "first_paint_cached_summary_reused": True
                }
            },
            markdown=lambda body, **payload: markdown_calls.append(
                {"body": body, "payload": dict(payload)}
            ),
        )
        inputs_page.render_inputs_current_summary_coordinator(
            summary_container=FakeSummaryContainer(context_calls),
            sync_callbacks={"sync": "callback"},
            inputs_elapsed_ms_fn=lambda: 12.345,
            update_user_latency_metrics_fn=update_latency,
            phase5c_render_trace_fn=phase_trace,
            mark_fn=mark,
            render_inputs_summary_expanders_and_tables_fn=render_summary,
        )
        if mark_calls != ["render_summary_reused_first_paint_cache"]:
            failures.append(f"reused_mark_calls_mismatch:{mark_calls}")
        if timing_calls != [
            {
                "label": "inputs_page.summary_render.skipped_first_paint_cache_authoritative",
                "payload": {
                    "elapsed_ms": 12.345,
                    "reason": "first_paint_cached_summary_html_hash_matched",
                },
            }
        ]:
            failures.append(f"reused_timing_calls_mismatch:{timing_calls}")
        if probe_calls != [
            {
                "label": "summary.final_render_skipped_after_first_paint_cache",
                "payload": {
                    "cache_hit": True,
                    "meta": {
                        "summary_final_render_skipped": True,
                        "reason": "first_paint_cached_summary_html_hash_matched",
                        "source": "FinalDesignGuidePublication/result_cache_hash guarded first-paint summary cache",
                        "affects_engineering": False,
                        "affects_design_guide_publication": False,
                        "affects_cta": False,
                        "affects_apply_payload": False,
                        "affects_visible_wording": False,
                        "product_behavior_changed": False,
                    },
                },
            }
        ]:
            failures.append(f"reused_probe_calls_mismatch:{probe_calls}")
        if context_calls or phase_calls or summary_render_calls or latency_calls or landing_calls:
            failures.append("reused_path_rendered_normal_summary")

        context_calls.clear()
        markdown_calls.clear()
        timing_calls.clear()
        probe_calls.clear()
        stable_reuse_calls.clear()
        phase_calls.clear()
        mark_calls.clear()
        latency_calls.clear()
        summary_render_calls.clear()
        landing_calls.clear()

        perf_values = iter([20.0, 20.05, 20.08])
        inputs_page.time = SimpleNamespace(perf_counter=lambda: next(perf_values))
        inputs_page.inputs_show_landing_dashboard = lambda: False
        inputs_page.st = SimpleNamespace(
            session_state={
                "_inputs_first_paint_cached_summary_reuse_debug": {
                    "first_paint_cached_summary_reused": False
                },
                inputs_page.RESULT_CACHE_KEY: {"result": "cache"},
                "results_version": 4,
                inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY: {
                    "final_publication_verifier_payload": {
                        "publication_hash": "pub_hash",
                        "final_publication_display_hash": "display_hash",
                    }
                },
            },
            markdown=lambda body, **payload: markdown_calls.append(
                {"body": body, "payload": dict(payload)}
            ),
        )
        inputs_page.render_inputs_current_summary_coordinator(
            summary_container=FakeSummaryContainer(context_calls),
            sync_callbacks={"sync": "callback"},
            inputs_elapsed_ms_fn=lambda: 22.0,
            update_user_latency_metrics_fn=update_latency,
            phase5c_render_trace_fn=phase_trace,
            mark_fn=mark,
            render_inputs_summary_expanders_and_tables_fn=render_summary,
        )
    finally:
        _restore()

    if stable_reuse_calls != [
        {
            "surface": "inputs_summary_panel",
            "fingerprint_payload": {
                "results_version": 4,
                "result_cache_hash": "result_hash",
                "final_publication_hash": "pub_hash",
                "final_publication_display_hash": "display_hash",
                "show_landing": False,
            },
            "debug_mode": False,
            "apply_in_flight": False,
            "pending_apply_refresh": False,
            "required_fingerprint_keys": ("results_version", "result_cache_hash"),
        }
    ]:
        failures.append(f"normal_stable_reuse_calls_mismatch:{stable_reuse_calls}")
    if [call["label"] for call in phase_calls] != [
        "summary_card_render_start",
        "summary_card_render_complete",
    ]:
        failures.append(f"normal_phase_calls_mismatch:{phase_calls}")
    if timing_calls != [
        {"label": "inputs_page.summary_render.start", "payload": {"elapsed_ms": 22.0}},
        {
            "label": "inputs_page.summary_render.end",
            "payload": {"duration_ms": 50.0, "elapsed_ms": 22.0, "landing": False},
        },
    ]:
        failures.append(f"normal_timing_calls_mismatch:{timing_calls}")
    if latency_calls != [{"summary_render_ms": 80.0, "summary_visible_ms": 22.0}]:
        failures.append(f"normal_latency_calls_mismatch:{latency_calls}")
    if summary_render_calls != ["summary"]:
        failures.append(f"normal_summary_render_calls_mismatch:{summary_render_calls}")
    if landing_calls:
        failures.append(f"normal_landing_calls_unexpected:{landing_calls}")
    if mark_calls != ["render_summary"]:
        failures.append(f"normal_mark_calls_mismatch:{mark_calls}")
    if not any("<h1 class=\"inputs-page-title\">Inputs</h1>" in call["body"] for call in markdown_calls):
        failures.append("normal_inputs_title_markdown_missing")
    if context_calls != [
        {"event": "enter", "label": "summary_container"},
        {"event": "exit", "label": "summary_container"},
    ]:
        failures.append(f"normal_context_calls_mismatch:{context_calls}")
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def _render_current_inputs_summary" in source:
        failures.append("nested_current_summary_helper_still_present")
    if "def render_summary_table" in source:
        failures.append("nested_render_summary_table_helper_still_present")

    payload = {
        "verifier": "inputs_page_current_summary_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "timing_calls": timing_calls,
        "stable_reuse_calls": stable_reuse_calls,
        "phase_calls": phase_calls,
        "latency_calls": latency_calls,
        "summary_render_calls": summary_render_calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Current Summary Coordinator Verifier",
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
