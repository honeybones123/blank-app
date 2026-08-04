from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_coherence_repair_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_coherence_repair_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_debug_has_coherent_overview": inputs_page._design_guide_debug_has_coherent_overview,
        "_design_guide_debug_has_efficiency_state": inputs_page._design_guide_debug_has_efficiency_state,
        "_ensure_design_guide_debug_trace_coherent": inputs_page._ensure_design_guide_debug_trace_coherent,
        "_agent_debug_log": inputs_page._agent_debug_log,
        "_candidate_cache_key": inputs_page._candidate_cache_key,
        "_guidance_state_snapshot": inputs_page._guidance_state_snapshot,
        "_build_design_actions_context": inputs_page._build_design_actions_context,
        "_collect_design_overview": inputs_page._collect_design_overview,
        "compute_efficiency_tightening_state": inputs_page.compute_efficiency_tightening_state,
        "_design_guide_apply_copy_model_to_items": inputs_page._design_guide_apply_copy_model_to_items,
        "_design_guide_apply_button_contracts_to_items": inputs_page._design_guide_apply_button_contracts_to_items,
        "_design_guide_apply_display_truth_to_items": inputs_page._design_guide_apply_display_truth_to_items,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for original_name, original_value in originals.items():
            setattr(inputs_page, original_name, original_value)

    def _run_case(
        name: str,
        *,
        overview_ok: bool,
        efficiency_ok: bool,
        initial_debug: dict[str, Any],
        merged_debug: dict[str, Any] | None = None,
        repairs: list[str] | None = None,
        current_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        items = [{"id": "primary"}]
        state = {"D": 500}
        current = dict(current_state or state)

        def _overview_ok(debug):
            events.append("overview_ok")
            return overview_ok

        def _efficiency_ok(debug):
            events.append("efficiency_ok")
            return efficiency_ok

        def _ensure(*, state, guidance_items, debug_trace):
            events.append("ensure")
            return dict(merged_debug or {}), list(repairs or [])

        def _log(event_name, payload, *, location, hypothesis_id):
            events.append(f"log:{event_name}")

        def _snapshot(value):
            events.append(f"snapshot:{value.get('D')}")
            return dict(value)

        def _cache_key(value):
            events.append(f"cache:{value.get('D')}")
            return tuple(sorted(dict(value).items()))

        def _context(value):
            events.append(f"context:{value.get('D')}")
            return {"ctx": value.get("D")}

        def _overview(value, *, context):
            events.append(f"collect_overview:{value.get('D')}")
            return {"overview_for": value.get("D"), "ctx": dict(context)}

        def _efficiency(value, *, context):
            events.append(f"collect_efficiency:{value.get('D')}")
            return {"efficiency_for": value.get("D"), "ctx": dict(context)}

        def _copy_model(items_arg, *, state, overview, efficiency_state):
            events.append("copy_model")
            return [dict(item, copy_model=True) for item in items_arg]

        def _button_contracts(items_arg, *, state):
            events.append("button_contracts")
            return [dict(item, button_contracts=True) for item in items_arg]

        def _display_truth(items_arg, *, state, overview, mode_config):
            events.append(f"display_truth:{mode_config.get('goal')}")
            return [dict(item, display_truth=True) for item in items_arg]

        def _goal(state_arg):
            events.append("goal")
            return "unit_goal"

        def _mode_config(goal):
            events.append(f"mode_config:{goal}")
            return {"goal": goal}

        def _recommend(items_arg, state_arg, *, branch, request_kind):
            events.append("recommend")
            return {"branch": branch, "request_kind": request_kind, "count": len(items_arg), "state_D": state_arg.get("D")}

        try:
            inputs_page._design_guide_debug_has_coherent_overview = _overview_ok
            inputs_page._design_guide_debug_has_efficiency_state = _efficiency_ok
            inputs_page._ensure_design_guide_debug_trace_coherent = _ensure
            inputs_page._agent_debug_log = _log
            inputs_page._candidate_cache_key = _cache_key
            inputs_page._guidance_state_snapshot = _snapshot
            inputs_page._build_design_actions_context = _context
            inputs_page._collect_design_overview = _overview
            inputs_page.compute_efficiency_tightening_state = _efficiency
            inputs_page._design_guide_apply_copy_model_to_items = _copy_model
            inputs_page._design_guide_apply_button_contracts_to_items = _button_contracts
            inputs_page._design_guide_apply_display_truth_to_items = _display_truth
            inputs_page._design_optimisation_goal = _goal
            inputs_page._design_mode_config = _mode_config
            inputs_page._recommendation_result_for_primary_guidance_card = _recommend

            out_debug, out_state, out_items, recommendation, needed, out_repairs = inputs_page.render_design_guide_coherence_repair(
                guidance_items=items,
                guidance_disp_state=state,
                current_state=current,
                guidance_debug=dict(initial_debug),
                current_recommendation_result={"existing": True},
                branch_for_recommendation="unit_branch",
                stage=lambda label: stages.append(str(label)),
            )
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "debug": out_debug,
            "state": out_state,
            "items": out_items,
            "recommendation": recommendation,
            "needed": needed,
            "repairs": out_repairs,
        }
        cases.append(case)
        return case

    no_repair = _run_case(
        "no_repair_needed",
        overview_ok=True,
        efficiency_ok=True,
        initial_debug={"guidance_resolved_state": {"D": 500}, "guidance_branch": "ready"},
    )
    if no_repair["events"] != ["overview_ok", "efficiency_ok"]:
        failures.append(f"no_repair_events_mismatch:{no_repair['events']}")
    if no_repair["stages"] or no_repair["needed"] or no_repair["repairs"]:
        failures.append(f"no_repair_side_effect_mismatch:{no_repair}")
    if no_repair["recommendation"] != {"existing": True}:
        failures.append(f"no_repair_recommendation_mismatch:{no_repair['recommendation']}")

    repaired = _run_case(
        "repair_same_state",
        overview_ok=False,
        efficiency_ok=True,
        initial_debug={"guidance_resolved_state": {"D": 500}},
        merged_debug={
            "guidance_resolved_state": {"D": 500},
            "overview": {"ok": True},
            "efficiency_tightening_state": {"ok": True},
            "guidance_branch": "repaired",
        },
        repairs=["overview", "efficiency_tightening_state"],
    )
    expected_repaired_events = [
        "overview_ok",
        "ensure",
        "log:render_debug_trace_fallback_repaired",
        "log:overview_rebuilt_in_render",
        "log:efficiency_state_rebuilt_in_render",
        "snapshot:500",
        "cache:500",
        "snapshot:500",
        "cache:500",
        "copy_model",
        "button_contracts",
        "goal",
        "mode_config:unit_goal",
        "display_truth:unit_goal",
        "recommend",
    ]
    if repaired["events"] != expected_repaired_events:
        failures.append(f"repaired_events_mismatch:{repaired['events']}")
    if repaired["stages"] != ["before_render_coherence_repair", "after_render_coherence_repair", "after_coherence_recommendation_result"]:
        failures.append(f"repaired_stage_mismatch:{repaired['stages']}")
    if repaired["repairs"] != ["overview", "efficiency_tightening_state"]:
        failures.append(f"repaired_repairs_mismatch:{repaired['repairs']}")
    if repaired["recommendation"].get("state_D") != 500 or repaired["recommendation"].get("count") != 1:
        failures.append(f"repaired_recommendation_mismatch:{repaired['recommendation']}")
    if repaired["items"][0].get("copy_model") is not True or repaired["items"][0].get("button_contracts") is not True or repaired["items"][0].get("display_truth") is not True:
        failures.append(f"repaired_items_mismatch:{repaired['items']}")

    stale = _run_case(
        "repair_stale_state_replaced",
        overview_ok=False,
        efficiency_ok=True,
        initial_debug={"guidance_resolved_state": {"D": 500}},
        merged_debug={
            "guidance_resolved_state": {"D": 500},
            "overview": {"old": True},
            "efficiency_tightening_state": {"old": True},
            "guidance_branch": "repaired",
        },
        repairs=["overview"],
        current_state={"D": 600},
    )
    if stale["state"].get("D") != 600:
        failures.append(f"stale_state_not_replaced:{stale['state']}")
    if stale["debug"].get("stale_guidance_resolved_state_replaced_after_coherence") is not True:
        failures.append(f"stale_flag_missing:{stale['debug']}")
    if stale["debug"].get("overview", {}).get("overview_for") != 600:
        failures.append(f"stale_overview_not_rebuilt:{stale['debug'].get('overview')}")
    if stale["debug"].get("efficiency_tightening_state", {}).get("efficiency_for") != 600:
        failures.append(f"stale_efficiency_not_rebuilt:{stale['debug'].get('efficiency_tightening_state')}")
    if "context:600" not in stale["events"] or "collect_overview:600" not in stale["events"] or "collect_efficiency:600" not in stale["events"]:
        failures.append(f"stale_rebuild_events_missing:{stale['events']}")

    payload = {
        "verifier": "inputs_page_coherence_repair_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Coherence Repair Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` needed: `{case['needed']}`, repairs: `{case['repairs']}`, stages: `{case['stages']}`"
                    for case in cases
                ),
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
