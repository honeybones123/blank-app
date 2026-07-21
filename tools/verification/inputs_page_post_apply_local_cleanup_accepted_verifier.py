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
    json_path = ARTIFACT_DIR / f"inputs_page_post_apply_local_cleanup_accepted_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_apply_local_cleanup_accepted_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_local_cleanup_post_apply_acceptance_matches": inputs_page._local_cleanup_post_apply_acceptance_matches,
        "_is_in_target_zone_with_eps": inputs_page._is_in_target_zone_with_eps,
        "_parse_util_value": inputs_page._parse_util_value,
        "_resolved_efficiency_target_band": inputs_page._resolved_efficiency_target_band,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_guidance_item": inputs_page._guidance_item,
        "_stamp_exact_cleanup_blocker_evidence": inputs_page._stamp_exact_cleanup_blocker_evidence,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _run_case(
        name: str,
        *,
        previous_branch_taken: bool = False,
        residual_published: bool = False,
        local_match: bool = True,
        in_target: bool = True,
        accepted_valid: bool = True,
        unresolved: list[str] | None = None,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        debug: dict[str, Any] = {"existing": True}

        def _guidance_item(*args, **kwargs):
            events.append("guidance_item")
            return {
                "family": args[0],
                "title_main": args[1],
                "status": kwargs.get("status"),
                "util": kwargs.get("util"),
            }

        def _stamp(debug_payload, audit, overview, *, accepted_reason):
            events.append("stamp")
            debug_payload["stamped_reason"] = accepted_reason
            debug_payload["stamped_audit"] = dict(audit or {})

        def _recommend(items, state, *, branch, request_kind):
            events.append("recommend")
            return {
                "branch": branch,
                "request_kind": request_kind,
                "count": len(items),
            }

        try:
            inputs_page._local_cleanup_post_apply_acceptance_matches = lambda state: local_match
            inputs_page._is_in_target_zone_with_eps = lambda overview, mode_config, *, eps: in_target
            inputs_page._parse_util_value = lambda value: float(value)
            inputs_page._resolved_efficiency_target_band = lambda mode_config, *, goal: (0.85, 0.95, "unit")
            inputs_page._design_optimisation_goal = lambda state: "balanced"
            inputs_page._guidance_item = _guidance_item
            inputs_page._stamp_exact_cleanup_blocker_evidence = _stamp
            inputs_page._recommendation_result_for_primary_guidance_card = _recommend

            branch_taken, items, out_debug, recommendation = inputs_page.render_design_guide_post_apply_local_cleanup_accepted(
                previous_branch_taken=previous_branch_taken,
                residual_width_cleanup_published=residual_published,
                guidance_disp_state={"D": 500},
                render_overview={"any_fail": False, "worst_util": 0.91, "governing_util": 0.90},
                render_mode_config={"mode": "unit"},
                render_acceptance_audit={
                    "post_click_accepted_green_valid": accepted_valid,
                    "post_click_unresolved_low_util_families": list(unresolved or []),
                },
                guidance_debug=debug,
                branch_for_recommendation="unit_branch",
                stage=lambda label: stages.append(str(label)),
            )
        finally:
            for original_name, original_value in originals.items():
                setattr(inputs_page, original_name, original_value)

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "branch_taken": branch_taken,
            "items": items,
            "debug": out_debug,
            "recommendation": recommendation,
        }
        cases.append(case)
        return case

    false_previous = _run_case("false_gate_previous_branch_taken", previous_branch_taken=True)
    if false_previous["branch_taken"] or false_previous["events"] or false_previous["stages"]:
        failures.append(f"false_previous_branch_mismatch:{false_previous}")

    false_unresolved = _run_case("false_gate_unresolved_low_util", unresolved=["shear"])
    if false_unresolved["branch_taken"] or false_unresolved["events"] or false_unresolved["stages"]:
        failures.append(f"false_unresolved_mismatch:{false_unresolved}")

    accepted = _run_case("accepted_local_cleanup")
    if accepted["events"] != ["guidance_item", "stamp", "recommend"]:
        failures.append(f"accepted_events_mismatch:{accepted['events']}")
    if accepted["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"accepted_stage_mismatch:{accepted['stages']}")
    if not accepted["branch_taken"] or len(accepted["items"]) != 1:
        failures.append(f"accepted_branch_mismatch:{accepted}")
    else:
        item = accepted["items"][0]
        if item.get("guidance_intent") != "already_efficient":
            failures.append(f"item_intent_mismatch:{item}")
        if item.get("design_guide_terminal_state") != "optimal":
            failures.append(f"item_terminal_state_mismatch:{item}")
        display_truth = dict(item.get("display_truth") or {})
        if display_truth.get("displayed_util") != 0.91 or display_truth.get("displayed_within_target_band") is not True:
            failures.append(f"display_truth_mismatch:{display_truth}")
        if display_truth.get("target_low") != 0.85 or display_truth.get("target_high") != 0.95:
            failures.append(f"target_band_mismatch:{display_truth}")
    if accepted["debug"].get("guidance_branch") != "post_apply_local_cleanup_accepted":
        failures.append("guidance_branch_missing")
    if accepted["debug"].get("post_click_design_guide_state") != "accepted_green":
        failures.append("accepted_green_debug_missing")
    if accepted["debug"].get("stamped_reason") != "post_apply_cleanup_state_accepted":
        failures.append("stamp_reason_missing")
    if accepted["recommendation"] != {
        "branch": "unit_branch",
        "request_kind": "design_guide",
        "count": 1,
    }:
        failures.append(f"recommendation_mismatch:{accepted['recommendation']}")

    payload = {
        "verifier": "inputs_page_post_apply_local_cleanup_accepted_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Apply Local Cleanup Accepted Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` events: `{case['events']}`, stages: `{case['stages']}`, branch_taken: `{case['branch_taken']}`" for case in cases),
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
