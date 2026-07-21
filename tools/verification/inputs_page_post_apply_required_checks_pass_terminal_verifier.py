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
    json_path = ARTIFACT_DIR / f"inputs_page_post_apply_required_checks_pass_terminal_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_apply_required_checks_pass_terminal_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "_post_active_repair_target_accepted_item": inputs_page._post_active_repair_target_accepted_item,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _run_case(
        name: str,
        *,
        previous_branch_taken: bool = False,
        residual_published: bool = False,
        accepted_valid: bool = False,
        any_fail: bool = False,
        required_ok: bool = True,
        accepted_item: dict | None = None,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        debug: dict[str, Any] = {"existing": True}
        accepted_payloads: list[dict[str, Any]] = []

        def _accepted(state, overview, mode_config, audit, **kwargs):
            events.append("accepted")
            accepted_payloads.append({"audit": dict(audit or {}), "kwargs": dict(kwargs or {})})
            return accepted_item

        def _recommend(items, state, *, branch, request_kind):
            events.append("recommend")
            return {
                "branch": branch,
                "request_kind": request_kind,
                "count": len(items),
            }

        try:
            inputs_page._overview_required_checks_acceptable = lambda overview: required_ok
            inputs_page._post_active_repair_target_accepted_item = _accepted
            inputs_page._recommendation_result_for_primary_guidance_card = _recommend

            branch_taken, items, out_debug, recommendation = inputs_page.render_design_guide_post_apply_required_checks_pass_terminal(
                previous_branch_taken=previous_branch_taken,
                residual_width_cleanup_published=residual_published,
                guidance_disp_state={"D": 500},
                render_overview={"any_fail": any_fail, "overview": "render"},
                render_mode_config={"mode": "unit"},
                render_acceptance_audit={
                    "post_click_accepted_green_valid": accepted_valid,
                    "original": True,
                },
                guidance_debug=debug,
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
            "accepted_payloads": accepted_payloads,
        }
        cases.append(case)
        return case

    false_previous = _run_case(
        "false_gate_previous_branch_taken",
        previous_branch_taken=True,
        accepted_item={"id": "accepted"},
    )
    if false_previous["branch_taken"] or false_previous["events"] or false_previous["stages"]:
        failures.append(f"false_previous_branch_mismatch:{false_previous}")

    false_required = _run_case(
        "false_gate_required_checks_not_ok",
        required_ok=False,
        accepted_item={"id": "accepted"},
    )
    if false_required["branch_taken"] or false_required["events"] or false_required["stages"]:
        failures.append(f"false_required_mismatch:{false_required}")

    accepted = _run_case(
        "required_checks_terminal",
        accepted_item={"id": "accepted"},
    )
    if accepted["events"] != ["accepted", "recommend"]:
        failures.append(f"accepted_events_mismatch:{accepted['events']}")
    if accepted["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"accepted_stage_mismatch:{accepted['stages']}")
    if not accepted["branch_taken"] or len(accepted["items"]) != 1:
        failures.append(f"accepted_branch_mismatch:{accepted}")
    accepted_audit = dict((accepted["accepted_payloads"] or [{}])[0].get("audit") or {})
    if accepted_audit.get("post_click_accepted_green_valid") is not True:
        failures.append(f"accepted_audit_valid_missing:{accepted_audit}")
    if accepted_audit.get("terminal_state_reason") != "post_apply_required_checks_pass":
        failures.append(f"accepted_audit_reason_missing:{accepted_audit}")
    accepted_kwargs = dict((accepted["accepted_payloads"] or [{}])[0].get("kwargs") or {})
    if accepted_kwargs.get("allow_required_checks_terminal") is not True:
        failures.append(f"accepted_kwargs_missing:{accepted_kwargs}")
    expected_debug = {
        "guidance_branch": "post_apply_required_checks_pass_terminal",
        "primary_guidance_intent": "already_efficient",
        "post_click_design_guide_state": "accepted_green",
        "post_repair_cleanup_promotion_suppressed_reason": "post_apply_required_checks_pass",
    }
    for key, expected in expected_debug.items():
        if accepted["debug"].get(key) != expected:
            failures.append(f"accepted_debug_{key}_mismatch:{accepted['debug'].get(key)}")
    if accepted["debug"].get("post_click_required_checks_accepted_outside_target_band") is not True:
        failures.append("accepted_required_checks_debug_missing")
    if accepted["recommendation"] != {
        "branch": "post_apply_required_checks_pass_terminal",
        "request_kind": "design_guide",
        "count": 1,
    }:
        failures.append(f"accepted_recommendation_mismatch:{accepted['recommendation']}")

    blocked = _run_case(
        "accepted_item_blocked",
        accepted_item=None,
    )
    if blocked["branch_taken"] is not True:
        failures.append(f"blocked_branch_not_taken:{blocked}")
    if blocked["items"] or blocked["recommendation"] is not None or blocked["stages"]:
        failures.append(f"blocked_side_effect_mismatch:{blocked}")
    if blocked["debug"].get("post_apply_required_checks_pass_terminal_blocked") is not True:
        failures.append("blocked_debug_missing")

    payload = {
        "verifier": "inputs_page_post_apply_required_checks_pass_terminal_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Apply Required Checks Pass Terminal Verifier",
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
