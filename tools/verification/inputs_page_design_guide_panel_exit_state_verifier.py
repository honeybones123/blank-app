from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_panel_exit_state_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_panel_exit_state_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_st = inputs_page.st
    original_trace = inputs_page._phase5c_latency_trace
    original_enabled = inputs_page._design_guide_button_contract_enabled
    original_banner = inputs_page._render_design_guide_post_apply_banner
    original_perf_counter = inputs_page.time.perf_counter

    session_state = {
        inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY: {
            "selected_family_id": "bending",
            "displayed_primary_button_contract": {
                "enabled": True,
                "family": "shear",
                "updates": {"a": 1, "b": 2},
            },
        },
        inputs_page.DESIGN_GUIDE_NEEDS_REFRESH_KEY: True,
    }

    def trace(event_name, **kwargs):
        calls.append({"event": "trace", "event_name": event_name, "kwargs": dict(kwargs)})

    def enabled(contract):
        calls.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool((contract or {}).get("enabled"))

    def banner(section):
        calls.append({"event": "banner", "section": section})

    try:
        inputs_page.st = SimpleNamespace(session_state=session_state)
        inputs_page._phase5c_latency_trace = trace
        inputs_page._design_guide_button_contract_enabled = enabled
        inputs_page._render_design_guide_post_apply_banner = banner
        inputs_page.time.perf_counter = lambda: 12.34567

        inputs_page.render_design_guide_panel_exit_state(
            render_post_apply_banner=True,
            fast_focus_section="focus-section",
            fingerprint="fingerprint-1",
            panel_trace_started=10.0,
        )
    finally:
        inputs_page.st = original_st
        inputs_page._phase5c_latency_trace = original_trace
        inputs_page._design_guide_button_contract_enabled = original_enabled
        inputs_page._render_design_guide_post_apply_banner = original_banner
        inputs_page.time.perf_counter = original_perf_counter

    trace_calls = [call for call in calls if call["event"] == "trace"]
    expect(
        "banner_first",
        calls and calls[0] == {"event": "banner", "section": "focus-section"},
        f"calls={calls}",
    )
    expect(
        "final_outcome_trace",
        trace_calls[:1]
        == [
            {
                "event": "trace",
                "event_name": "final_visible_outcome_ready",
                "kwargs": {
                    "selected_family": "bending",
                    "button_contract_enabled": True,
                    "update_count": 2,
                },
            }
        ],
        f"trace_calls={trace_calls}",
    )
    expect(
        "exit_trace_duration",
        trace_calls[1:2]
        == [
            {
                "event": "trace",
                "event_name": "design_guide_panel_exit",
                "kwargs": {"duration_ms": 2345.67},
            }
        ],
        f"trace_calls={trace_calls}",
    )
    expect(
        "fingerprints_and_refresh",
        session_state.get(inputs_page.DESIGN_GUIDE_PANEL_BASELINE_FP_KEY) == "fingerprint-1"
        and session_state.get(inputs_page.DESIGN_GUIDE_PUBLICATION_FP_KEY) == "fingerprint-1"
        and inputs_page.DESIGN_GUIDE_NEEDS_REFRESH_KEY not in session_state,
        f"session_state={session_state}",
    )
    expect(
        "contract_enabled_call",
        {"event": "contract_enabled", "contract": {"enabled": True, "family": "shear", "updates": {"a": 1, "b": 2}}}
        in calls,
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "session_state": session_state,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Panel Exit State Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
