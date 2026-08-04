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
    json_path = ARTIFACT_DIR / f"inputs_page_fresh_design_guide_start_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_fresh_design_guide_start_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "time",
        "st",
        "render_timing_mark",
        "_record_inputs_stable_render_reuse_trace",
        "_stable_final_publication_hash",
        "_design_guide_sidebar_debug_enabled",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    timing_calls: list[dict[str, Any]] = []
    reuse_trace_calls: list[dict[str, Any]] = []
    mark_calls: list[str] = []
    phase_calls: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def timing_mark(label: str, **payload) -> None:
        timing_calls.append({"label": label, "payload": dict(payload)})

    def reuse_trace(**payload) -> None:
        reuse_trace_calls.append(dict(payload))

    def phase_trace(label: str, *args, **payload) -> None:
        phase_calls.append({"label": label, "args": list(args), "payload": dict(payload)})

    def mark(label: str) -> None:
        mark_calls.append(label)

    try:
        perf_values = iter([50.25])
        inputs_page.time = SimpleNamespace(perf_counter=lambda: next(perf_values))
        inputs_page.render_timing_mark = timing_mark
        inputs_page._record_inputs_stable_render_reuse_trace = reuse_trace
        inputs_page._stable_final_publication_hash = lambda value: f"hash:{sorted(value) if isinstance(value, dict) else value}"
        inputs_page._design_guide_sidebar_debug_enabled = lambda: False
        inputs_page.st = SimpleNamespace(session_state={})
        result = inputs_page.render_inputs_fresh_design_guide_start_coordinator(
            show_design_guide_for_current_inputs=False,
            design_guide_slot=object(),
            render_trace_started=50.0,
            mark_fn=mark,
            phase5c_render_trace_fn=phase_trace,
        )
        if result is not None:
            failures.append(f"skip_result_not_none:{result}")
        if timing_calls != [
            {
                "label": "inputs_page.design_guide_build.skipped_until_actions_or_loads",
                "payload": {"elapsed_ms": 250.0},
            }
        ]:
            failures.append(f"skip_timing_calls_mismatch:{timing_calls}")
        if mark_calls != ["render_design_guide_skipped"]:
            failures.append(f"skip_mark_calls_mismatch:{mark_calls}")
        if reuse_trace_calls or phase_calls:
            failures.append("skip_path_emitted_start_or_reuse_trace")

        timing_calls.clear()
        reuse_trace_calls.clear()
        mark_calls.clear()
        phase_calls.clear()

        perf_values = iter([100.0, 100.125])
        inputs_page.time = SimpleNamespace(perf_counter=lambda: next(perf_values))
        inputs_page.st = SimpleNamespace(
            session_state={
                "results_version": 8,
                inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY: {"apply": "payload"},
                inputs_page.DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY: True,
                "_pending_inputs_apply_refresh": True,
                inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY: {
                    "final_publication_verifier_payload": {
                        "publication_hash": "pub_hash",
                        "final_publication_display_hash": "display_hash",
                        "final_publication_cta_hash": "cta_hash",
                    },
                    "displayed_primary_button_contract": {"enabled": True},
                },
            }
        )
        result = inputs_page.render_inputs_fresh_design_guide_start_coordinator(
            show_design_guide_for_current_inputs=True,
            design_guide_slot=object(),
            render_trace_started=99.5,
            mark_fn=mark,
            phase5c_render_trace_fn=phase_trace,
        )
    finally:
        _restore()

    if result != 100.0:
        failures.append(f"start_result_mismatch:{result}")
    if reuse_trace_calls != [
        {
            "surface": "design_guide_panel",
            "fingerprint_payload": {
                "results_version": 8,
                "final_publication_hash": "pub_hash",
                "final_publication_display_hash": "display_hash",
                "final_publication_cta_hash": "cta_hash",
                "button_contract_hash": "hash:['enabled']",
                "apply_payload_hash": "hash:['apply']",
                "show_design_guide_for_current_inputs": True,
            },
            "debug_mode": False,
            "apply_in_flight": True,
            "pending_apply_refresh": True,
            "required_fingerprint_keys": (
                "results_version",
                "final_publication_hash",
                "final_publication_display_hash",
                "final_publication_cta_hash",
                "button_contract_hash",
                "apply_payload_hash",
            ),
            "store_trace": False,
        }
    ]:
        failures.append(f"start_reuse_trace_calls_mismatch:{reuse_trace_calls}")
    if phase_calls != [{"label": "design_guide_build_start", "args": [], "payload": {}}]:
        failures.append(f"start_phase_calls_mismatch:{phase_calls}")
    if timing_calls != [
        {
            "label": "inputs_page.design_guide_build.start",
            "payload": {"elapsed_ms": 625.0},
        }
    ]:
        failures.append(f"start_timing_calls_mismatch:{timing_calls}")
    if mark_calls:
        failures.append(f"start_mark_calls_unexpected:{mark_calls}")
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_fresh_design_guide_start_coordinator" not in source:
        failures.append("fresh_design_guide_start_coordinator_missing")
    if "_dg_render_debug =" in source[source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")]:
        failures.append("fresh_panel_still_owns_initial_reuse_trace_debug_setup")

    payload = {
        "verifier": "inputs_page_fresh_design_guide_start_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "timing_calls": timing_calls,
        "reuse_trace_calls": reuse_trace_calls,
        "phase_calls": phase_calls,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Fresh Design Guide Start Coordinator Verifier",
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
