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
    json_path = ARTIFACT_DIR / f"inputs_page_post_click_invalid_accepted_cleanup_resolution_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_click_invalid_accepted_cleanup_resolution_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_post_click_low_bending_resolution_item": inputs_page._post_click_low_bending_resolution_item,
        "_shear_low_util_active_links_exact_blocker": inputs_page._shear_low_util_active_links_exact_blocker,
        "_post_active_repair_residual_shear_exact_blocker": inputs_page._post_active_repair_residual_shear_exact_blocker,
        "_shear_target_cleanup_action_from_candidate_evidence": inputs_page._shear_target_cleanup_action_from_candidate_evidence,
        "_shear_best_safe_cleanup_item_from_evidence": inputs_page._shear_best_safe_cleanup_item_from_evidence,
        "_design_guide_apply_button_contracts_to_items": inputs_page._design_guide_apply_button_contracts_to_items,
        "_shear_cleanup_exact_blocker_guidance_item": inputs_page._shear_cleanup_exact_blocker_guidance_item,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_stamp_shear_cleanup_exact_blocker_publication": inputs_page._stamp_shear_cleanup_exact_blocker_publication,
        "_parse_util_value": inputs_page._parse_util_value,
        "_guidance_item": inputs_page._guidance_item,
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
        previous_branch_taken: bool = False,
        residual_published: bool = False,
        audit: dict[str, Any] | None = None,
        bending_resolution: dict | None = None,
        shear_blocker: dict | None = None,
        residual_shear_blocker: dict | None = None,
        shear_action: dict | None = None,
        best_safe_item: dict | None = None,
        blocker_item: dict | None = None,
        button_enabled: bool = True,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        debug: dict[str, Any] = {"candidate_search_evidence": {"source": "debug"}}
        state = {"D": 500}
        overview = {"worst_util": "72%", "governing_util": 0.72}
        mode_config = {"mode": "unit"}
        render_audit = dict(
            audit
            if audit is not None
            else {
                "post_click_accepted_green_valid": False,
                "post_click_accepted_green_invalid_reason": "unit_invalid_cleanup",
            }
        )
        stamp_payloads: list[dict[str, Any]] = []

        def _bending(state_arg, overview_arg, mode_arg, audit_arg, **kwargs):
            events.append("bending")
            return bending_resolution

        def _low_shear(state_arg, overview_arg, *, threshold):
            events.append("shear_low_active_links")
            return shear_blocker

        def _residual_shear(state_arg, overview_arg, *, threshold, reason):
            events.append("residual_shear_blocker")
            return residual_shear_blocker

        def _target_action(state_arg, overview_arg, evidence_arg):
            events.append("shear_target_action")
            return shear_action

        def _best_safe(state_arg, overview_arg, evidence_arg, *, title):
            events.append("shear_best_safe")
            return best_safe_item

        def _apply_contracts(items, *, state):
            events.append("apply_contracts")
            return list(items)

        def _blocker_item(blocker_arg, *, state, overview):
            events.append("shear_blocker_item")
            return blocker_item

        def _button_enabled(contract):
            events.append("button_enabled")
            return button_enabled

        def _stamp(debug_arg, item_arg, blocker_arg):
            events.append("stamp_shear_blocker")
            stamp_payloads.append(
                {
                    "item_title": dict(item_arg or {}).get("title_main") or dict(item_arg or {}).get("title"),
                    "blocker": dict(blocker_arg or {}),
                }
            )

        def _parse(value):
            events.append("parse_util")
            return 0.72

        def _guidance_item(*args, **kwargs):
            events.append("guidance_item")
            return {
                "family": args[0],
                "title_main": args[1],
                "status": kwargs.get("status"),
                "util": kwargs.get("util"),
            }

        def _recommend(items, state_arg, *, branch, request_kind):
            events.append("recommend")
            return {
                "branch": branch,
                "request_kind": request_kind,
                "count": len(items),
            }

        try:
            inputs_page._post_click_low_bending_resolution_item = _bending
            inputs_page._shear_low_util_active_links_exact_blocker = _low_shear
            inputs_page._post_active_repair_residual_shear_exact_blocker = _residual_shear
            inputs_page._shear_target_cleanup_action_from_candidate_evidence = _target_action
            inputs_page._shear_best_safe_cleanup_item_from_evidence = _best_safe
            inputs_page._design_guide_apply_button_contracts_to_items = _apply_contracts
            inputs_page._shear_cleanup_exact_blocker_guidance_item = _blocker_item
            inputs_page._design_guide_button_contract_enabled = _button_enabled
            inputs_page._stamp_shear_cleanup_exact_blocker_publication = _stamp
            inputs_page._parse_util_value = _parse
            inputs_page._guidance_item = _guidance_item
            inputs_page._recommendation_result_for_primary_guidance_card = _recommend

            branch_taken, items, out_debug, recommendation = inputs_page.render_design_guide_post_click_invalid_accepted_cleanup_resolution(
                previous_branch_taken=previous_branch_taken,
                residual_width_cleanup_published=residual_published,
                guidance_disp_state=state,
                render_overview=overview,
                render_mode_config=mode_config,
                render_acceptance_audit=render_audit,
                guidance_debug=debug,
                branch_for_recommendation="unit_branch",
                stage=lambda label: stages.append(str(label)),
            )
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "branch_taken": branch_taken,
            "items": items,
            "debug": out_debug,
            "recommendation": recommendation,
            "stamp_payloads": stamp_payloads,
        }
        cases.append(case)
        return case

    false_previous = _run_case(
        "false_gate_previous_branch_taken",
        previous_branch_taken=True,
        bending_resolution={"id": "must_not_call"},
    )
    if false_previous["branch_taken"] or false_previous["events"] or false_previous["stages"]:
        failures.append(f"false_previous_branch_mismatch:{false_previous}")

    bending = _run_case(
        "bending_resolution",
        bending_resolution={"title_main": "Bending exact blocker", "guidance_intent": "specific_blocker"},
    )
    if bending["events"] != ["bending", "recommend"]:
        failures.append(f"bending_events_mismatch:{bending['events']}")
    if bending["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"bending_stage_mismatch:{bending['stages']}")
    if bending["debug"].get("guidance_branch") != "post_apply_low_bending_resolution":
        failures.append(f"bending_branch_mismatch:{bending['debug'].get('guidance_branch')}")
    if bending["debug"].get("post_click_design_guide_state") != "exact_blocker":
        failures.append(f"bending_state_mismatch:{bending['debug'].get('post_click_design_guide_state')}")
    if bending["debug"].get("primary_guidance_intent") != "specific_blocker":
        failures.append(f"bending_intent_mismatch:{bending['debug'].get('primary_guidance_intent')}")
    if bending["recommendation"] != {"branch": "unit_branch", "request_kind": "design_guide", "count": 1}:
        failures.append(f"bending_recommendation_mismatch:{bending['recommendation']}")

    shear_actionable = _run_case(
        "shear_actionable_resolution",
        audit={
            "post_click_accepted_green_valid": False,
            "post_click_accepted_green_invalid_reason": "unit_shear_low",
            "post_click_unresolved_low_util_families": ["shear"],
            "post_click_exact_blockers_by_family": {"shear": {"family": "shear", "reason": "low"}},
        },
        shear_action={
            "title_main": "Shear cleanup action",
            "guidance_intent": "specific_next_action",
            "action_type": "apply_resolved_candidate",
            "button_contract": {
                "updates": {"Av": 240},
                "preview_pass": True,
            },
            "candidate_search_evidence": {"candidate": "safe"},
        },
    )
    if shear_actionable["events"] != ["bending", "shear_target_action", "apply_contracts", "button_enabled", "recommend"]:
        failures.append(f"shear_actionable_events_mismatch:{shear_actionable['events']}")
    expected_action_debug = {
        "guidance_branch": "post_apply_low_shear_action",
        "post_click_design_guide_state": "next_action",
        "selected_action_type": "apply_resolved_candidate",
        "selected_action_family": "shear",
        "button_contract_enabled": True,
        "button_contract_preview_pass": True,
    }
    for key, expected in expected_action_debug.items():
        if shear_actionable["debug"].get(key) != expected:
            failures.append(f"shear_actionable_{key}_mismatch:{shear_actionable['debug'].get(key)}")
    if shear_actionable["debug"].get("button_contract_updates") != {"Av": 240}:
        failures.append(f"shear_actionable_updates_mismatch:{shear_actionable['debug'].get('button_contract_updates')}")

    shear_blocker = _run_case(
        "shear_non_actionable_resolution",
        audit={
            "post_click_accepted_green_valid": False,
            "post_click_accepted_green_invalid_reason": "unit_shear_blocker",
            "post_click_unresolved_low_util_families": ["shear"],
            "post_click_exact_blockers_by_family": {"shear": {"family": "shear", "reason": "low"}},
        },
        best_safe_item={
            "title_main": "Shear exact blocker",
            "guidance_intent": "specific_blocker",
            "exact_blockers_by_family": {"shear": {"family": "shear", "reason": "low"}},
        },
    )
    if shear_blocker["events"] != ["bending", "shear_target_action", "shear_best_safe", "apply_contracts", "stamp_shear_blocker", "recommend"]:
        failures.append(f"shear_blocker_events_mismatch:{shear_blocker['events']}")
    if shear_blocker["debug"].get("guidance_branch") != "post_apply_low_shear_resolution":
        failures.append(f"shear_blocker_branch_mismatch:{shear_blocker['debug'].get('guidance_branch')}")
    if shear_blocker["debug"].get("post_click_design_guide_state") != "exact_blocker":
        failures.append(f"shear_blocker_state_mismatch:{shear_blocker['debug'].get('post_click_design_guide_state')}")
    if len(shear_blocker["stamp_payloads"]) != 1:
        failures.append(f"shear_blocker_stamp_missing:{shear_blocker['stamp_payloads']}")

    missing = _run_case(
        "missing_evidence_blocker",
        audit={
            "post_click_accepted_green_valid": False,
            "post_click_accepted_green_invalid_reason": "unit_missing",
            "post_click_unresolved_low_util_families": ["bending"],
            "post_click_cleanup_evidence_by_family": {"bending": {"searched": True}},
            "post_click_family_utils": {"bending": 0.72},
            "post_click_materially_overprovided_families": ["bending"],
        },
    )
    if missing["events"] != ["bending", "parse_util", "guidance_item", "recommend"]:
        failures.append(f"missing_events_mismatch:{missing['events']}")
    if missing["items"][0].get("title_main") != "Design Guide blocker evidence is missing":
        failures.append(f"missing_title_mismatch:{missing['items']}")
    missing_contract = dict(missing["items"][0].get("button_contract") or {})
    if missing_contract.get("enabled") is not False or missing_contract.get("family") != "other":
        failures.append(f"missing_contract_mismatch:{missing_contract}")
    missing_evidence = dict(missing["items"][0].get("candidate_search_evidence") or {})
    if missing_evidence.get("family_utils") != {"bending": 0.72}:
        failures.append(f"missing_evidence_mismatch:{missing_evidence}")
    if missing["stages"] != ["after_final_recommendation_result"]:
        failures.append(f"missing_stage_mismatch:{missing['stages']}")

    payload = {
        "verifier": "inputs_page_post_click_invalid_accepted_cleanup_resolution_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Click Invalid Accepted Cleanup Resolution Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` events: `{case['events']}`, stages: `{case['stages']}`, branch_taken: `{case['branch_taken']}`"
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
