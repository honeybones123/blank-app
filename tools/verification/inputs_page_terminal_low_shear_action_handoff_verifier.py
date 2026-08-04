from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_low_shear_action_handoff_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_low_shear_action_handoff_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_stamp = inputs_page._stamp_zero_bending_demand_exclusion
    original_render = inputs_page._render_guidance_secondary_items

    def stamp(debug, state, utils):
        calls.append({"event": "stamp", "debug": dict(debug), "state": dict(state), "utils": dict(utils)})
        debug["zero_bending_exclusion_stamped"] = True

    def render_secondary(items, **kwargs):
        calls.append(
            {
                "event": "render_secondary",
                "items": [dict(item) for item in items],
                "kwargs": kwargs,
            }
        )

    def stage(name):
        calls.append({"event": "stage", "name": name})

    try:
        inputs_page._stamp_zero_bending_demand_exclusion = stamp
        inputs_page._render_guidance_secondary_items = render_secondary
        guidance_debug, presentation, terminal_state = (
            inputs_page.render_design_guide_terminal_low_shear_action_handoff(
                terminal_low_shear_action={
                    "title_main": "Tighten shear links",
                    "button_contract": {
                        "enabled": True,
                        "updates": {"s_lig": 250},
                    },
                    "candidate_search_evidence": {"source": "terminal_low_shear"},
                },
                guidance_debug={"existing": "debug"},
                terminal_current_state_for_shear={"s_lig": 300},
                terminal_current_overview={"utils": {"shear": 0.62, "bending": 0.9}},
                dg_overview={"worst_util": 0.9},
                inputs_render_audit={"audit": True},
                stage_fn=stage,
            )
        )
    finally:
        inputs_page._stamp_zero_bending_demand_exclusion = original_stamp
        inputs_page._render_guidance_secondary_items = original_render

    stamp_call = next((call for call in calls if call["event"] == "stamp"), {})
    render_call = next((call for call in calls if call["event"] == "render_secondary"), {})
    stage_call = next((call for call in calls if call["event"] == "stage"), {})

    expect(
        "debug_payload",
        guidance_debug.get("existing") == "debug"
        and guidance_debug.get("guidance_branch")
        == "post_active_repair_residual_shear_best_safe_action"
        and guidance_debug.get("selected_title") == "Tighten shear links"
        and guidance_debug.get("selected_action_type") == "apply_resolved_candidate"
        and guidance_debug.get("selected_action_family") == "shear"
        and guidance_debug.get("primary_card_intent") == "efficiency_tightening"
        and guidance_debug.get("button_contract_enabled") is True
        and guidance_debug.get("button_contract_updates") == {"s_lig": 250}
        and guidance_debug.get("candidate_search_evidence") == {"source": "terminal_low_shear"}
        and guidance_debug.get("design_guide_terminal_state") is None
        and guidance_debug.get("design_guide_terminal_positive") is False
        and guidance_debug.get("design_guide_has_actionable_recommendation") is True
        and guidance_debug.get("zero_bending_exclusion_stamped") is True,
        f"guidance_debug={guidance_debug}",
    )
    expect(
        "render_and_stage",
        presentation == {}
        and terminal_state is None
        and stamp_call.get("state") == {"s_lig": 300}
        and stamp_call.get("utils") == {"shear": 0.62, "bending": 0.9}
        and render_call.get("items", [{}])[0].get("title_main") == "Tighten shear links"
        and render_call.get("kwargs", {}).get("guidance_disp_state") == {"s_lig": 300}
        and render_call.get("kwargs", {}).get("current_overview") == {"worst_util": 0.9}
        and render_call.get("kwargs", {}).get("inputs_render_audit") == {"audit": True}
        and render_call.get("kwargs", {}).get("start_index") == 0
        and render_call.get("kwargs", {}).get("primary_card_presentation") == {}
        and stage_call.get("name") == "post_plan.after_render_terminal_low_shear_action",
        (
            f"presentation={presentation} terminal_state={terminal_state} "
            f"stamp_call={stamp_call} render_call={render_call} stage_call={stage_call}"
        ),
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "guidance_debug": guidance_debug,
        "presentation": presentation,
        "terminal_state": terminal_state,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Low Shear Action Handoff Verifier",
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
