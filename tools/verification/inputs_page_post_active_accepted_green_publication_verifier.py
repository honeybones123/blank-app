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
    json_path = ARTIFACT_DIR / f"inputs_page_post_active_accepted_green_publication_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_active_accepted_green_publication_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_post_active_repair_target_accepted_item": inputs_page._post_active_repair_target_accepted_item,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _run_case(
        name: str,
        *,
        residual_published: bool = False,
        post_active: bool = True,
        family_speed: bool = False,
        accepted_valid: bool = True,
        any_fail: bool = False,
        combined_ready: bool = False,
        accepted_item: dict | None = None,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        debug: dict[str, Any] = {"existing": True}

        def _accepted(*args, **kwargs):
            events.append("accepted")
            return accepted_item

        def _recommend(items, state, *, branch, request_kind):
            events.append("recommend")
            return {
                "branch": branch,
                "request_kind": request_kind,
                "count": len(items),
            }

        try:
            inputs_page._post_active_repair_target_accepted_item = _accepted
            inputs_page._recommendation_result_for_primary_guidance_card = _recommend
            branch_taken, items, out_debug, recommendation = inputs_page.render_design_guide_post_active_accepted_green_publication(
                residual_width_cleanup_published=residual_published,
                render_post_active_failure_repair=post_active,
                family_speed_isolated_bending_repair=family_speed,
                render_acceptance_audit={
                    "post_click_accepted_green_valid": accepted_valid,
                    "audit": True,
                },
                render_acceptance_overview={"any_fail": any_fail, "overview": "accepted"},
                render_combined_terminal_apply_ready=combined_ready,
                guidance_disp_state={"D": 500},
                render_mode_config={"mode": "unit"},
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

    false_case = _run_case(
        "false_gate_residual_width_already_published",
        residual_published=True,
        accepted_item={"id": "accepted"},
    )
    if false_case["branch_taken"] or false_case["events"] or false_case["stages"]:
        failures.append(f"false_gate_mismatch:{false_case}")

    accepted_case = _run_case(
        "accepted_green_publication",
        accepted_item={"id": "accepted"},
    )
    if accepted_case["events"] != ["accepted", "recommend"]:
        failures.append(f"accepted_events_mismatch:{accepted_case['events']}")
    if accepted_case["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"accepted_stage_mismatch:{accepted_case['stages']}")
    if not accepted_case["branch_taken"] or len(accepted_case["items"]) != 1:
        failures.append(f"accepted_branch_mismatch:{accepted_case}")
    if accepted_case["debug"].get("post_active_repair_green_acceptance_published") is not True:
        failures.append("accepted_debug_published_missing")
    if accepted_case["debug"].get("post_repair_cleanup_promotion_suppressed_reason") != "active_failure_repair_required_checks_pass":
        failures.append("accepted_suppression_reason_missing")
    if accepted_case["recommendation"] != {
        "branch": "unit_branch",
        "request_kind": "design_guide",
        "count": 1,
    }:
        failures.append(f"accepted_recommendation_mismatch:{accepted_case['recommendation']}")

    combined_case = _run_case(
        "combined_terminal_family_stamp",
        combined_ready=True,
        accepted_item={"id": "combined_accepted"},
    )
    combined_item = combined_case["items"][0] if combined_case["items"] else {}
    if combined_item.get("selected_family_id") != "TARGET_BAND_REACHED":
        failures.append(f"combined_selected_family_mismatch:{combined_item}")
    if combined_item.get("render_gate_condition") != "combined_post_apply_required_checks_pass_terminal":
        failures.append(f"combined_gate_condition_mismatch:{combined_item}")
    if combined_item.get("family_match_passed") is not True:
        failures.append(f"combined_family_match_missing:{combined_item}")

    blocked_case = _run_case(
        "accepted_item_blocked",
        accepted_item=None,
    )
    if blocked_case["branch_taken"] is not True:
        failures.append(f"blocked_branch_not_taken:{blocked_case}")
    if blocked_case["items"] or blocked_case["recommendation"] is not None or blocked_case["stages"]:
        failures.append(f"blocked_side_effect_mismatch:{blocked_case}")
    if blocked_case["debug"].get("post_active_repair_green_acceptance_blocked") is not True:
        failures.append("blocked_debug_missing")

    payload = {
        "verifier": "inputs_page_post_active_accepted_green_publication_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Active Accepted Green Publication Verifier",
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
