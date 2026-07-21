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
    json_path = ARTIFACT_DIR / f"inputs_page_post_apply_exact_low_util_blocker_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_apply_exact_low_util_blocker_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_post_click_low_bending_resolution_item": inputs_page._post_click_low_bending_resolution_item,
        "_parse_util_value": inputs_page._parse_util_value,
        "_guidance_item": inputs_page._guidance_item,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _run_case(
        name: str,
        *,
        previous_branch_taken: bool = False,
        residual_published: bool = False,
        accepted_valid: bool = True,
        low_families: list[str] | None = None,
        exact_blockers: dict | None = None,
        bending_resolution: dict | None = None,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        debug: dict[str, Any] = {"existing": True}

        def _bending(*args, **kwargs):
            events.append("bending_resolution")
            return bending_resolution

        def _guidance_item(*args, **kwargs):
            events.append("guidance_item")
            return {
                "family": args[0],
                "title_main": args[1],
                "body": args[2],
                "status": kwargs.get("status"),
                "util": kwargs.get("util"),
            }

        def _recommend(items, state, *, branch, request_kind):
            events.append("recommend")
            return {
                "branch": branch,
                "request_kind": request_kind,
                "count": len(items),
            }

        try:
            inputs_page._post_click_low_bending_resolution_item = _bending
            inputs_page._parse_util_value = lambda value: float(value)
            inputs_page._guidance_item = _guidance_item
            inputs_page._recommendation_result_for_primary_guidance_card = _recommend

            branch_taken, items, out_debug, recommendation = inputs_page.render_design_guide_post_apply_exact_low_util_blocker(
                previous_branch_taken=previous_branch_taken,
                residual_width_cleanup_published=residual_published,
                guidance_disp_state={"D": 500},
                render_overview={"worst_util": 0.90, "governing_util": 0.89},
                render_mode_config={"mode": "unit"},
                render_acceptance_audit={
                    "post_click_accepted_green_valid": accepted_valid,
                    "post_click_families_below_final_threshold": list(
                        low_families if low_families is not None else ["shear"]
                    ),
                    "post_click_exact_blockers_by_family": dict(
                        exact_blockers
                        if exact_blockers is not None
                        else {"shear": {"reason": "links govern", "current_util": 0.82}}
                    ),
                    "terminal_state_reason": "terminal reason",
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

    false_previous = _run_case(
        "false_gate_previous_branch_taken",
        previous_branch_taken=True,
        bending_resolution={"guidance_intent": "specific_blocker"},
    )
    if false_previous["branch_taken"] or false_previous["events"] or false_previous["stages"]:
        failures.append(f"false_previous_branch_mismatch:{false_previous}")

    false_no_low = _run_case(
        "false_gate_no_low_families",
        low_families=[],
        bending_resolution={"guidance_intent": "specific_blocker"},
    )
    if false_no_low["branch_taken"] or false_no_low["events"] or false_no_low["stages"]:
        failures.append(f"false_no_low_mismatch:{false_no_low}")

    bending = _run_case(
        "bending_resolution_item",
        exact_blockers={"bending": {"reason": "bar limit", "current_util": 0.81}},
        bending_resolution={"guidance_intent": "specific_blocker", "title_main": "Bending blocker"},
    )
    if bending["events"] != ["bending_resolution", "recommend"]:
        failures.append(f"bending_events_mismatch:{bending['events']}")
    if bending["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"bending_stage_mismatch:{bending['stages']}")
    if not bending["branch_taken"] or len(bending["items"]) != 1:
        failures.append(f"bending_branch_mismatch:{bending}")
    if bending["debug"].get("guidance_branch") != "post_apply_exact_low_bending_blocker":
        failures.append("bending_guidance_branch_missing")
    if bending["debug"].get("primary_guidance_intent") != "specific_blocker":
        failures.append("bending_primary_intent_missing")

    synthesized = _run_case(
        "synthesized_exact_blocker",
        exact_blockers={"shear": {"reason": "links govern", "current_util": 0.82}},
        bending_resolution=None,
    )
    if synthesized["events"] != ["bending_resolution", "guidance_item", "recommend"]:
        failures.append(f"synth_events_mismatch:{synthesized['events']}")
    if synthesized["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"synth_stage_mismatch:{synthesized['stages']}")
    if not synthesized["branch_taken"] or len(synthesized["items"]) != 1:
        failures.append(f"synth_branch_mismatch:{synthesized}")
    else:
        item = synthesized["items"][0]
        if item.get("guidance_intent") != "specific_blocker":
            failures.append(f"synth_item_intent_mismatch:{item}")
        if item.get("final_state_class") != "blocker":
            failures.append(f"synth_final_state_mismatch:{item}")
        if item.get("primary_card_actionable") is not False:
            failures.append(f"synth_actionable_mismatch:{item}")
        contract = dict(item.get("button_contract") or {})
        if contract.get("enabled") is not False or contract.get("family") != "shear":
            failures.append(f"synth_contract_mismatch:{contract}")
        if item.get("safe_local_cleanup_count") != 0 or item.get("executable_safe_cleanup_count") != 0:
            failures.append(f"synth_cleanup_count_mismatch:{item}")
    if synthesized["debug"].get("guidance_branch") != "post_apply_exact_low_family_blocker":
        failures.append("synth_guidance_branch_missing")
    if synthesized["debug"].get("terminal_state_blocked_reason") != "terminal reason":
        failures.append("terminal_blocked_reason_missing")

    payload = {
        "verifier": "inputs_page_post_apply_exact_low_util_blocker_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Apply Exact Low Util Blocker Verifier",
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
