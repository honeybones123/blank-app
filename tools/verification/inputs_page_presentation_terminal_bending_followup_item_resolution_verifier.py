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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_terminal_bending_followup_item_resolution_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_terminal_bending_followup_item_resolution_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_bending_only_target_band_cleanup_item",
        "_design_mode_config",
        "_design_optimisation_goal",
        "_design_guide_button_contract_enabled",
        "_design_guide_button_contract",
        "_resolve_design_guide_controller_terminalisation_followup_updates",
        "_updates_match_state",
        "_evaluate_bending_only_target_band_prebuilt_candidate_with_service",
        "_guidance_state_snapshot",
        "_overview_required_checks_acceptable",
        "_candidate_preview_statuses_have_explicit_fail",
        "_resolve_design_guide_controller_terminalisation_trial_acceptance",
        "_guidance_cleanup_candidate_id",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}

    failures: list[str] = []
    cases: list[dict] = []
    calls: list[str] = []
    case_config: dict = {}

    def run_case(
        name: str,
        *,
        followup_allowed: bool = True,
        followup_item: dict | None = None,
        contract_enabled: bool = True,
        fallback_contract_enabled: bool = True,
        resolution: dict | None = None,
        updates_match_state: bool = False,
        trial_candidate: dict | None = None,
        trial_acceptance: dict | None = None,
        expected_updates: dict,
        expected_expected_util,
        expected_subfamilies: list,
        expected_candidate_id,
        expected_evidence_keys: dict | None = None,
        expected_debug_keys: dict | None = None,
        expected_call_contains: list[str] | None = None,
        unexpected_call_contains: list[str] | None = None,
    ) -> None:
        calls.clear()
        case_config.clear()
        case_config.update(
            {
                "followup_item": dict(followup_item or {"candidate_id": "followup", "button_contract": {"enabled": True}}),
                "contract_enabled": contract_enabled,
                "fallback_contract_enabled": fallback_contract_enabled,
                "resolution": dict(resolution or {"action_type": "apply_resolved_candidate", "updates": {"bottom_bar_dia": 16}}),
                "updates_match_state": updates_match_state,
                "trial_candidate": trial_candidate,
                "trial_acceptance": dict(trial_acceptance or {"accepted": True}),
            }
        )
        evidence = {"target_band_candidate_count": 0, "before": True}
        debug = {"before": True}
        result = inputs_page.render_design_guide_presentation_terminal_bending_followup_item_resolution(
            presentation_followup_allowed=followup_allowed,
            presentation_terminal_state={"D": 500, "bottom_bar_dia": 20},
            presentation_terminal_overview={"utils": {"bending": 0.7}},
            guidance_disp_state={"D": 500, "bottom_bar_dia": 20},
            presentation_bending_updates={"bottom_bar_dia": 18},
            presentation_bending_expected_for_contract=0.70,
            presentation_bending_subfamilies=["geometry"],
            presentation_bending_candidate_id="initial",
            presentation_bending_evidence=evidence,
            guidance_debug=debug,
        )
        actual_updates, actual_util, actual_subfamilies, actual_id, actual_evidence, actual_debug = result
        case_record = {
            "name": name,
            "updates": actual_updates,
            "expected_util": actual_util,
            "subfamilies": actual_subfamilies,
            "candidate_id": actual_id,
            "calls": list(calls),
        }
        cases.append(case_record)
        if actual_updates != expected_updates:
            failures.append(f"{name}:updates:expected={expected_updates}:actual={actual_updates}")
        if actual_util != expected_expected_util:
            failures.append(f"{name}:expected_util:expected={expected_expected_util}:actual={actual_util}")
        if actual_subfamilies != expected_subfamilies:
            failures.append(f"{name}:subfamilies:expected={expected_subfamilies}:actual={actual_subfamilies}")
        if actual_id != expected_candidate_id:
            failures.append(f"{name}:candidate_id:expected={expected_candidate_id}:actual={actual_id}")
        for key, expected in dict(expected_evidence_keys or {}).items():
            if actual_evidence.get(key) != expected:
                failures.append(f"{name}:evidence[{key}]:expected={expected}:actual={actual_evidence.get(key)}")
        for key, expected in dict(expected_debug_keys or {}).items():
            if actual_debug.get(key) != expected:
                failures.append(f"{name}:debug[{key}]:expected={expected}:actual={actual_debug.get(key)}")
        for expected_call in list(expected_call_contains or []):
            if expected_call not in calls:
                failures.append(f"{name}:missing_call:{expected_call}:calls={calls}")
        for unexpected_call in list(unexpected_call_contains or []):
            if unexpected_call in calls:
                failures.append(f"{name}:unexpected_call:{unexpected_call}:calls={calls}")

    def fake_followup_item(*args, **kwargs):
        calls.append("followup_item")
        return dict(case_config["followup_item"])

    def fake_design_mode_config(goal):
        calls.append("design_mode_config")
        return {"goal": goal}

    def fake_design_goal(state):
        calls.append("design_goal")
        return "balanced"

    def fake_contract_enabled(contract):
        calls.append("contract_enabled")
        if contract.get("fallback"):
            return bool(case_config["fallback_contract_enabled"])
        return bool(case_config["contract_enabled"])

    def fake_button_contract(item, *, state):
        calls.append("button_contract")
        return {"enabled": True, "fallback": True}

    def fake_followup_resolution(*, item, button_contract):
        calls.append("resolve_followup")
        return dict(case_config["resolution"])

    def fake_updates_match_state(state, updates):
        calls.append("updates_match_state")
        return bool(case_config["updates_match_state"])

    def fake_evaluate(snapshot, *, source, updates):
        calls.append("evaluate_trial")
        return case_config["trial_candidate"]

    def fake_snapshot(state):
        calls.append("snapshot")
        return dict(state or {})

    def fake_required_checks_acceptable(overview):
        calls.append("required_checks")
        return True

    def fake_statuses_have_fail(statuses):
        calls.append("statuses_have_fail")
        return False

    def fake_trial_acceptance(**kwargs):
        calls.append("trial_acceptance")
        return dict(case_config["trial_acceptance"])

    def fake_cleanup_candidate_id(family, updates):
        calls.append("candidate_id")
        return f"{family}:{','.join(sorted(dict(updates or {}).keys()))}"

    try:
        inputs_page._bending_only_target_band_cleanup_item = fake_followup_item
        inputs_page._design_mode_config = fake_design_mode_config
        inputs_page._design_optimisation_goal = fake_design_goal
        inputs_page._design_guide_button_contract_enabled = fake_contract_enabled
        inputs_page._design_guide_button_contract = fake_button_contract
        inputs_page._resolve_design_guide_controller_terminalisation_followup_updates = fake_followup_resolution
        inputs_page._updates_match_state = fake_updates_match_state
        inputs_page._evaluate_bending_only_target_band_prebuilt_candidate_with_service = fake_evaluate
        inputs_page._guidance_state_snapshot = fake_snapshot
        inputs_page._overview_required_checks_acceptable = fake_required_checks_acceptable
        inputs_page._candidate_preview_statuses_have_explicit_fail = fake_statuses_have_fail
        inputs_page._resolve_design_guide_controller_terminalisation_trial_acceptance = fake_trial_acceptance
        inputs_page._guidance_cleanup_candidate_id = fake_cleanup_candidate_id

        run_case(
            "gate_off_returns_originals_without_work",
            followup_allowed=False,
            expected_updates={"bottom_bar_dia": 18},
            expected_expected_util=0.70,
            expected_subfamilies=["geometry"],
            expected_candidate_id="initial",
            expected_evidence_keys={"before": True},
            expected_debug_keys={"before": True},
            unexpected_call_contains=["followup_item", "evaluate_trial"],
        )
        run_case(
            "accepted_followup_folds_trial_updates",
            trial_candidate={"overview": {"utils": {"bending": 0.90}, "any_fail": False, "statuses": {}}},
            resolution={"action_type": "apply_resolved_candidate", "updates": {"bottom_bar_dia": 16}},
            followup_item={"candidate_id": "followup-16", "button_contract": {"enabled": True}},
            expected_updates={"bottom_bar_dia": 16},
            expected_expected_util=0.90,
            expected_subfamilies=["geometry", "bottom_reinforcement"],
            expected_candidate_id="bending:bottom_bar_dia",
            expected_evidence_keys={
                "terminal_candidate_status": "TERMINAL_TARGET_BAND",
                "same_click_terminalisation_fold": True,
                "same_click_presentation_bending_folded_residual_bending": True,
                "selected_candidate_util": 0.90,
                "no_second_cta_required": True,
            },
            expected_debug_keys={"same_click_presentation_bending_folded_residual_bending": True},
            expected_call_contains=["followup_item", "resolve_followup", "evaluate_trial", "trial_acceptance", "candidate_id"],
        )
        run_case(
            "fallback_contract_path_can_resolve_without_evaluation",
            contract_enabled=False,
            resolution={"action_type": "noop", "updates": {"bottom_bar_dia": 16}},
            expected_updates={"bottom_bar_dia": 18},
            expected_expected_util=0.70,
            expected_subfamilies=["geometry"],
            expected_candidate_id="initial",
            expected_call_contains=["button_contract", "resolve_followup"],
            unexpected_call_contains=["evaluate_trial"],
        )
        run_case(
            "matching_state_blocks_trial_evaluation",
            updates_match_state=True,
            resolution={"action_type": "apply_resolved_candidate", "updates": {"bottom_bar_dia": 16}},
            expected_updates={"bottom_bar_dia": 18},
            expected_expected_util=0.70,
            expected_subfamilies=["geometry"],
            expected_candidate_id="initial",
            expected_call_contains=["updates_match_state"],
            unexpected_call_contains=["evaluate_trial"],
        )
        run_case(
            "rejected_trial_preserves_originals",
            trial_candidate={"overview": {"utils": {"bending": 0.90}, "any_fail": False, "statuses": {}}},
            trial_acceptance={"accepted": False},
            expected_updates={"bottom_bar_dia": 18},
            expected_expected_util=0.70,
            expected_subfamilies=["geometry"],
            expected_candidate_id="initial",
            expected_call_contains=["evaluate_trial", "trial_acceptance"],
            unexpected_call_contains=["candidate_id"],
        )
        run_case(
            "accepted_controller_low_util_preserves_originals",
            trial_candidate={"overview": {"utils": {"bending": 0.70}, "any_fail": False, "statuses": {}}},
            trial_acceptance={"accepted": True},
            expected_updates={"bottom_bar_dia": 18},
            expected_expected_util=0.70,
            expected_subfamilies=["geometry"],
            expected_candidate_id="initial",
            expected_call_contains=["evaluate_trial", "trial_acceptance"],
            unexpected_call_contains=["candidate_id"],
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    payload_out = {
        "verifier": "inputs_page_presentation_terminal_bending_followup_item_resolution_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Terminal Bending Followup Item Resolution Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['candidate_id']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
