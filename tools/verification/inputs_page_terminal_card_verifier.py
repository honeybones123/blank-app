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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_card_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_card_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_guidance_item = inputs_page._guidance_item
    original_arrangement = inputs_page._design_guide_cleanup_arrangement_label
    original_blockers = inputs_page._design_guide_blocker_attempts_table
    original_render = inputs_page._render_guidance_secondary_items

    def guidance_item(bucket, title, body, action, why, checks, updates, payload, **kwargs):
        calls.append(
            {
                "event": "guidance_item",
                "bucket": bucket,
                "title": title,
                "body": body,
                "why": why,
                "checks": checks,
                "kwargs": kwargs,
            }
        )
        return {
            "bucket": bucket,
            "title_main": title,
            "body": body,
            "why": why,
            "checks": checks,
            "status": kwargs.get("status"),
            "util": kwargs.get("util"),
        }

    def arrangement(family, state):
        calls.append({"event": "arrangement", "family": family, "state": dict(state or {})})
        return "R10-300"

    def blocker_attempts(item):
        calls.append({"event": "blocker_attempts", "item": dict(item or {})})
        return {"shear": {"attempted": True, "from_table": True}}

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
        inputs_page._guidance_item = guidance_item
        inputs_page._design_guide_cleanup_arrangement_label = arrangement
        inputs_page._design_guide_blocker_attempts_table = blocker_attempts
        inputs_page._render_guidance_secondary_items = render_secondary

        optimal_item = inputs_page.render_design_guide_terminal_card(
            terminal_state="optimal",
            dg_presentation={
                "display_truth_source": "published_summary",
                "displayed_within_target_band": True,
            },
            dg_overview={"worst_util": 0.91},
            terminal_zero_shear_demand_accepted=False,
            terminal_current_state_for_shear={"s_lig": 300},
            terminal_shear_util=0.72,
            terminal_shear_evidence_for_card={},
            guidance_disp_state={"state": "visible"},
            inputs_render_audit={"audit": 1},
            stage_fn=stage,
        )

        zero_shear_item = inputs_page.render_design_guide_terminal_card(
            terminal_state="optimal",
            dg_presentation={},
            dg_overview={"governing_util": 0.88},
            terminal_zero_shear_demand_accepted=True,
            terminal_current_state_for_shear={"s_lig": 300},
            terminal_shear_util=0.0,
            terminal_shear_evidence_for_card={},
            guidance_disp_state={"state": "zero"},
            inputs_render_audit={"audit": 2},
            stage_fn=stage,
        )

        exact_item = inputs_page.render_design_guide_terminal_card(
            terminal_state="very_low_demand",
            dg_presentation={},
            dg_overview={"worst_util": 0.2},
            terminal_zero_shear_demand_accepted=False,
            terminal_current_state_for_shear={"s_lig": 300},
            terminal_shear_util=0.2,
            terminal_shear_evidence_for_card={"reason": "residual shear below floor"},
            guidance_disp_state={"state": "exact"},
            inputs_render_audit={"audit": 3},
            stage_fn=stage,
        )
    finally:
        inputs_page._guidance_item = original_guidance_item
        inputs_page._design_guide_cleanup_arrangement_label = original_arrangement
        inputs_page._design_guide_blocker_attempts_table = original_blockers
        inputs_page._render_guidance_secondary_items = original_render

    render_calls = [call for call in calls if call["event"] == "render_secondary"]
    stage_calls = [call for call in calls if call["event"] == "stage"]

    expect(
        "optimal_published_summary_card",
        optimal_item.get("title_main")
        == "Design is efficient - further reductions would weaken capacity"
        and optimal_item.get("body")
        == "The current section is within the target utilisation range; further reductions would lower reserve capacity or stiffness."
        and optimal_item.get("guidance_intent") == "already_efficient"
        and optimal_item.get("design_guide_terminal_state") == "optimal"
        and optimal_item.get("util") == 0.91,
        f"optimal_item={optimal_item}",
    )
    expect(
        "zero_shear_ladder_stop",
        zero_shear_item.get("blocker_attempts_by_family", {}).get("shear", {}).get("attempted") is True
        and zero_shear_item.get("blocker_attempts_by_family", {}).get("shear", {}).get("current_arrangement_label")
        == "R10-300"
        and zero_shear_item.get("candidate_search_evidence", {}).get("blocker_attempts_by_family")
        == zero_shear_item.get("blocker_attempts_by_family")
        and zero_shear_item.get("util") == 0.88,
        f"zero_shear_item={zero_shear_item}",
    )
    expect(
        "exact_shear_evidence",
        exact_item.get("title_main") == "Design demand is very low"
        and exact_item.get("exact_blockers_by_family") == {"shear": {"reason": "residual shear below floor"}}
        and exact_item.get("post_click_exact_blockers_by_family")
        == {"shear": {"reason": "residual shear below floor"}}
        and exact_item.get("cleanup_evidence_by_family")
        == {"shear": {"reason": "residual shear below floor"}}
        and exact_item.get("candidate_search_evidence", {}).get("post_click_cleanup_evidence_by_family")
        == {"shear": {"reason": "residual shear below floor"}}
        and exact_item.get("blocker_attempts_by_family") == {"shear": {"attempted": True, "from_table": True}},
        f"exact_item={exact_item}",
    )
    expect(
        "render_and_stage",
        len(render_calls) == 3
        and len(stage_calls) == 3
        and all(call.get("name") == "post_plan.after_render_terminal_card" for call in stage_calls)
        and render_calls[0].get("kwargs", {}).get("guidance_disp_state") == {"state": "visible"}
        and render_calls[1].get("kwargs", {}).get("current_overview") == {"governing_util": 0.88}
        and render_calls[2].get("kwargs", {}).get("inputs_render_audit") == {"audit": 3},
        f"render_calls={render_calls} stage_calls={stage_calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "optimal_item": optimal_item,
        "zero_shear_item": zero_shear_item,
        "exact_item": exact_item,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Card Verifier",
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
