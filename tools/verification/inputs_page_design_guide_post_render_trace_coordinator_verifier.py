from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_post_render_trace_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_post_render_trace_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patch_names = [
        "st",
        "_record_inputs_stable_render_reuse_trace",
        "_design_guide_sidebar_debug_enabled",
        "render_timing_mark",
        "_dg_speed_diag_summary",
    ]
    originals: dict[str, Any] = {name: getattr(inputs_page, name) for name in patch_names}
    failures: list[str] = []
    reuse_calls: list[dict[str, Any]] = []
    timing_calls: list[dict[str, Any]] = []
    latency_calls: list[dict[str, Any]] = []
    mark_calls: list[str] = []
    phase_calls: list[dict[str, Any]] = []

    fake_st = FakeStreamlit()
    fake_st.session_state.update(
        {
            "results_version": 42,
            "_pending_inputs_apply_refresh": True,
            inputs_page.DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY: True,
            inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY: {"updates": {"b": 500}},
            inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY: {
                "final_publication_verifier_payload": {
                    "publication_hash": "pub-hash",
                    "final_publication_display_hash": "display-hash",
                    "final_publication_cta_hash": "cta-hash",
                },
                "displayed_primary_button_contract": {
                    "action_type": "apply_resolved_candidate",
                    "updates": {"D": 450},
                },
            },
        }
    )

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def record_reuse_trace(**kwargs):
        reuse_calls.append(dict(kwargs))

    def render_timing_mark(name, **kwargs):
        timing_calls.append({"name": name, **dict(kwargs)})

    def update_latency(**kwargs):
        latency_calls.append(dict(kwargs))

    def mark(label: str) -> None:
        mark_calls.append(label)

    def phase(label: str, started: float, **kwargs) -> None:
        phase_calls.append({"label": label, "started": started, **dict(kwargs)})

    try:
        inputs_page.st = fake_st
        inputs_page._record_inputs_stable_render_reuse_trace = record_reuse_trace
        inputs_page._design_guide_sidebar_debug_enabled = lambda: True
        inputs_page.render_timing_mark = render_timing_mark
        inputs_page._dg_speed_diag_summary = lambda: {"diag": "ok"}

        started = time.perf_counter() - 0.05
        trace_started = time.perf_counter() - 0.1
        inputs_page.render_inputs_design_guide_post_render_trace_coordinator(
            design_guide_render_started=started,
            render_trace_started=trace_started,
            show_design_guide_for_current_inputs=True,
            inputs_elapsed_ms_fn=lambda: 123.456,
            update_user_latency_metrics_fn=update_latency,
            mark_fn=mark,
            phase5c_render_trace_fn=phase,
        )
    finally:
        _restore()

    if inputs_page.DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY in fake_st.session_state:
        failures.append("apply_in_flight_key_not_cleared")
    if len(reuse_calls) != 1:
        failures.append(f"reuse_trace_call_count_mismatch:{len(reuse_calls)}")
    else:
        reuse_call = reuse_calls[0]
        fingerprint = dict(reuse_call.get("fingerprint_payload") or {})
        if reuse_call.get("surface") != "design_guide_panel":
            failures.append(f"surface_mismatch:{reuse_call}")
        if reuse_call.get("debug_mode") is not True:
            failures.append(f"debug_mode_mismatch:{reuse_call}")
        if reuse_call.get("apply_in_flight") is not False:
            failures.append(f"apply_in_flight_mismatch:{reuse_call}")
        if reuse_call.get("pending_apply_refresh") is not True:
            failures.append(f"pending_apply_refresh_mismatch:{reuse_call}")
        for key, expected in {
            "results_version": 42,
            "final_publication_hash": "pub-hash",
            "final_publication_display_hash": "display-hash",
            "final_publication_cta_hash": "cta-hash",
            "show_design_guide_for_current_inputs": True,
        }.items():
            if fingerprint.get(key) != expected:
                failures.append(f"fingerprint_{key}_mismatch:{fingerprint}")
        required_keys = tuple(reuse_call.get("required_fingerprint_keys") or ())
        for key in (
            "results_version",
            "final_publication_hash",
            "final_publication_display_hash",
            "final_publication_cta_hash",
            "button_contract_hash",
            "apply_payload_hash",
        ):
            if key not in required_keys:
                failures.append(f"required_fingerprint_key_missing:{key}")
    if not timing_calls or timing_calls[0].get("name") != "inputs_page.design_guide_build.end":
        failures.append(f"timing_mark_missing:{timing_calls}")
    if not latency_calls or latency_calls[0].get("design_guide_visible_ms") != 123.456:
        failures.append(f"latency_call_mismatch:{latency_calls}")
    if mark_calls != ["render_design_guide"]:
        failures.append(f"mark_calls_mismatch:{mark_calls}")
    if not phase_calls or phase_calls[0].get("label") != "design_guide_build_complete":
        failures.append(f"phase_call_missing:{phase_calls}")
    elif phase_calls[0].get("browser_enabled_contract_shell") is not False:
        failures.append(f"phase_browser_flag_mismatch:{phase_calls}")

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    if "def render_inputs_design_guide_post_render_trace_coordinator" not in source:
        failures.append("post_render_trace_coordinator_missing")
    fresh_panel = source[
        source.find("def _render_fresh_design_guide_panel") : source.find("    # --- 5. RENDER UI ---")
    ]
    for stale_name in [
        "_post_render_dg_bundle_for_reuse",
        "_post_render_publication_payload",
        "_post_render_button_contract_for_reuse",
    ]:
        if stale_name in fresh_panel:
            failures.append(f"fresh_panel_still_owns_{stale_name}")

    payload = {
        "verifier": "inputs_page_design_guide_post_render_trace_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "reuse_trace_call_count": len(reuse_calls),
        "timing_call_count": len(timing_calls),
        "latency_call_count": len(latency_calls),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Post-Render Trace Coordinator Verifier",
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
