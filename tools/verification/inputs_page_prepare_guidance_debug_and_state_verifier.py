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
    json_path = ARTIFACT_DIR / f"inputs_page_prepare_guidance_debug_and_state_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_prepare_guidance_debug_and_state_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_st = inputs_page.st
    original_agent = inputs_page._agent_debug_log
    original_snapshot = inputs_page._guidance_state_snapshot
    original_cache_key = inputs_page._candidate_cache_key
    original_context = inputs_page._build_design_actions_context
    original_overview = inputs_page._collect_design_overview
    original_efficiency = inputs_page.compute_efficiency_tightening_state
    original_perf_counter = inputs_page.time.perf_counter

    session_state = {}
    cache_key_inputs: list[dict] = []

    def agent(message, payload, *, location, hypothesis_id):
        calls.append(
            {
                "event": "agent",
                "message": message,
                "payload": dict(payload or {}),
                "location": location,
                "hypothesis_id": hypothesis_id,
            }
        )

    def snapshot(state):
        state = dict(state or {})
        calls.append({"event": "snapshot", "state": state})
        return {"snap": state.get("id"), "value": state.get("value")}

    def cache_key(snapshot_value):
        snapshot_value = dict(snapshot_value or {})
        cache_key_inputs.append(snapshot_value)
        return f"fp:{snapshot_value.get('snap')}:{snapshot_value.get('value')}"

    def context(state):
        calls.append({"event": "context", "state": dict(state or {})})
        return {"ctx": dict(state or {}).get("id")}

    def overview(state, *, context):
        calls.append({"event": "overview", "state": dict(state or {}), "context": dict(context or {})})
        return {"overview_for": dict(state or {}).get("id")}

    def efficiency(state, *, context):
        calls.append({"event": "efficiency", "state": dict(state or {}), "context": dict(context or {})})
        return {"efficiency_for": dict(state or {}).get("id")}

    stage_events: list[str] = []

    def stage(name: str) -> None:
        stage_events.append(name)
        calls.append({"event": "stage", "name": name})

    try:
        inputs_page.st = SimpleNamespace(session_state=session_state)
        inputs_page._agent_debug_log = agent
        inputs_page._guidance_state_snapshot = snapshot
        inputs_page._candidate_cache_key = cache_key
        inputs_page._build_design_actions_context = context
        inputs_page._collect_design_overview = overview
        inputs_page.compute_efficiency_tightening_state = efficiency
        inputs_page.time.perf_counter = lambda: 12.345

        guidance_debug, guidance_disp_state, guidance_compute_ms = (
            inputs_page.render_design_guide_prepare_guidance_debug_and_state(
                guidance_started_at=10.0,
                guidance_debug={
                    "guidance_resolved_state": {"id": "stale", "value": 2},
                    "one_click_solver": {"one_click_solver_expanded": True},
                    "reco_trace": [{"step": 1}],
                },
                guidance_cache_hit=True,
                cache_hit_initial=True,
                cache_debug_complete_initial=False,
                cache_repair_attempted=True,
                cache_recompute_forced=False,
                cache_recompute_success=True,
                settle_gate_decision={"settled": True},
                fingerprint="fingerprint-1",
                current_state={"id": "current", "value": 1},
                sidebar_debug=True,
                stage_fn=stage,
            )
        )
    finally:
        inputs_page.st = original_st
        inputs_page._agent_debug_log = original_agent
        inputs_page._guidance_state_snapshot = original_snapshot
        inputs_page._candidate_cache_key = original_cache_key
        inputs_page._build_design_actions_context = original_context
        inputs_page._collect_design_overview = original_overview
        inputs_page.compute_efficiency_tightening_state = original_efficiency
        inputs_page.time.perf_counter = original_perf_counter

    expect(
        "stage_and_cache_log",
        stage_events == ["before_guidance_postprocess"]
        and any(
            call["event"] == "agent"
            and call["message"] == "Design guide cache coherence"
            and call["payload"]
            == {
                "cache_hit_initial": True,
                "cache_debug_complete_initial": False,
                "cache_repair_attempted": True,
                "cache_recompute_forced": False,
                "cache_recompute_success": True,
            }
            for call in calls
        ),
        f"stage_events={stage_events} calls={calls}",
    )
    expect(
        "metadata_stamped",
        guidance_debug.get("design_guide_algorithm_version")
        == inputs_page.DESIGN_GUIDE_ALGORITHM_VERSION
        and guidance_debug.get("design_guide_publication_fingerprint") == "fingerprint-1"
        and guidance_debug.get("design_guide_settle_gate") == {"settled": True}
        and guidance_debug.get("design_guide_settle_gate_contract")
        == inputs_page.DESIGN_GUIDE_FAMILY_SETTLE_GATE_CONTRACT
        and guidance_debug.get("design_guide_settle_gate_contract_file")
        == inputs_page.DESIGN_GUIDE_FAMILY_SETTLE_GATE_CONTRACT_FILE
        and guidance_debug.get("design_guide_expensive_publication_allowed") is True,
        f"guidance_debug={guidance_debug}",
    )
    expect(
        "sidebar_debug_stamped",
        guidance_compute_ms == 2345.0
        and guidance_debug.get("guidance_compute_ms") == 2345.0
        and guidance_debug.get("guidance_cache_hit") is True
        and guidance_debug.get("one_click_solver_expanded") is True
        and session_state.get(inputs_page.DESIGN_GUIDE_RECO_TRACE_KEY) == [{"step": 1}],
        f"guidance_compute_ms={guidance_compute_ms} debug={guidance_debug} session={session_state}",
    )
    expect(
        "stale_state_repaired",
        guidance_disp_state == {"snap": "current", "value": 1}
        and guidance_debug.get("guidance_resolved_state") == {"snap": "current", "value": 1}
        and guidance_debug.get("stale_guidance_resolved_state_replaced") is True
        and guidance_debug.get("stale_guidance_resolved_state_fp") == "fp:stale:2"
        and guidance_debug.get("current_guidance_state_fp") == "fp:current:1"
        and guidance_debug.get("overview") == {"overview_for": None}
        and guidance_debug.get("efficiency_tightening_state") == {"efficiency_for": None},
        f"guidance_disp_state={guidance_disp_state} debug={guidance_debug}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "stage_events": stage_events,
        "session_state": session_state,
        "guidance_debug": guidance_debug,
        "guidance_disp_state": guidance_disp_state,
        "guidance_compute_ms": guidance_compute_ms,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Prepare Guidance Debug And State Verifier",
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
