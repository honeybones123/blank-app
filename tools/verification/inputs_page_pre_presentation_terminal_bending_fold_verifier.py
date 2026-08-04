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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_terminal_bending_fold_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_terminal_bending_fold_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_collect_design_overview": inputs_page._collect_design_overview,
        "_guidance_state_snapshot": inputs_page._guidance_state_snapshot,
        "_build_design_actions_context": inputs_page._build_design_actions_context,
        "_bending_only_target_band_cleanup_item": inputs_page._bending_only_target_band_cleanup_item,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_design_guide_button_contract": inputs_page._design_guide_button_contract,
        "_resolve_design_guide_controller_terminalisation_followup_updates": (
            inputs_page._resolve_design_guide_controller_terminalisation_followup_updates
        ),
        "_updates_match_state": inputs_page._updates_match_state,
        "_evaluate_bending_only_target_band_prebuilt_candidate_with_service": (
            inputs_page._evaluate_bending_only_target_band_prebuilt_candidate_with_service
        ),
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "_candidate_preview_statuses_have_explicit_fail": inputs_page._candidate_preview_statuses_have_explicit_fail,
        "_resolve_design_guide_controller_terminalisation_trial_acceptance": (
            inputs_page._resolve_design_guide_controller_terminalisation_trial_acceptance
        ),
        "_guidance_cleanup_candidate_id": inputs_page._guidance_cleanup_candidate_id,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "TARGET_BAND_EPS": inputs_page.TARGET_BAND_EPS,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _call(
        *,
        family: str = "bending",
        updates: dict | None = None,
        util: float | None = 0.7,
        evidence: dict | None = None,
        subfamilies: list | None = None,
        candidate_id: str = "old-id",
        debug: dict | None = None,
    ):
        return inputs_page.render_design_guide_pre_presentation_terminal_bending_fold(
            bending_action_family=family,
            pre_presentation_updates=dict(updates or {"bottom_bars": 4}),
            pre_presentation_util=util,
            pre_presentation_evidence=dict(evidence or {"target_band_candidate_count": 0}),
            bending_action_subfamilies=list(subfamilies or ["bottom_reinforcement"]),
            bending_action_candidate_id=candidate_id,
            guidance_disp_state={"depth": 500, "bottom_bars": 6},
            guidance_debug=debug if debug is not None else {},
        )

    debug: dict[str, Any] = {}
    result = _call(family="combined", debug=debug)
    cases.append({"name": "guard_family_noop", "result": result, "debug": dict(debug)})
    if result != (
        {"bottom_bars": 4},
        0.7,
        {"target_band_candidate_count": 0},
        ["bottom_reinforcement"],
        "old-id",
    ):
        failures.append(f"guard_family_noop_mismatch:{result}")
    if debug:
        failures.append(f"guard_family_debug_changed:{debug}")

    calls: dict[str, list] = {"overview": [], "contract": [], "eval": []}
    debug = {}

    def _install_common(
        *,
        terminal_util: float | None = 0.6,
        followup_contract_enabled: bool = True,
        followup_resolution: dict | None = None,
        updates_match: bool = False,
        trial_overview: dict | None = None,
        trial_acceptance: dict | None = None,
    ) -> None:
        inputs_page._guidance_state_snapshot = lambda state: dict(state)
        inputs_page._build_design_actions_context = lambda state: {"context_state": dict(state)}

        def _overview(snapshot, *, context):
            calls["overview"].append({"snapshot": dict(snapshot), "context": dict(context)})
            return {"utils": {"bending": terminal_util}}

        inputs_page._collect_design_overview = _overview
        inputs_page._bending_only_target_band_cleanup_item = (
            lambda state, overview, mode_config, *, debug_sink, allow_terminalisation_fold: {
                "candidate_id": "followup-id",
                "button_contract": {"enabled": followup_contract_enabled, "updates": {"depth": 475}},
            }
        )
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))

        def _contract(item, *, state):
            calls["contract"].append({"item": dict(item), "state": dict(state)})
            return {"enabled": True, "updates": {"depth": 475}}

        inputs_page._design_guide_button_contract = _contract
        inputs_page._resolve_design_guide_controller_terminalisation_followup_updates = (
            lambda item, button_contract: dict(
                followup_resolution
                if followup_resolution is not None
                else {"action_type": "apply_resolved_candidate", "updates": {"depth": 475}}
            )
        )
        inputs_page._updates_match_state = lambda state, updates: bool(updates_match)

        def _eval(snapshot, *, source, updates):
            calls["eval"].append({"snapshot": dict(snapshot), "source": source, "updates": dict(updates)})
            return {
                "overview": dict(
                    trial_overview
                    if trial_overview is not None
                    else {"any_fail": False, "utils": {"bending": 0.9}, "statuses": {"bending": "pass"}}
                )
            }

        inputs_page._evaluate_bending_only_target_band_prebuilt_candidate_with_service = _eval
        inputs_page._overview_required_checks_acceptable = lambda overview: True
        inputs_page._candidate_preview_statuses_have_explicit_fail = lambda statuses: False
        inputs_page._resolve_design_guide_controller_terminalisation_trial_acceptance = (
            lambda **kwargs: dict(trial_acceptance if trial_acceptance is not None else {"accepted": True})
        )
        inputs_page._guidance_cleanup_candidate_id = lambda family, updates: f"{family}-fold-id"
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
        inputs_page.TARGET_BAND_EPS = 0.0001

    try:
        _install_common()
        result = _call(debug=debug)
    finally:
        _restore()
    cases.append({"name": "accepted_terminal_fold", "result": result, "debug": dict(debug), "calls": calls})
    if result[0] != {"bottom_bars": 4, "depth": 475}:
        failures.append(f"accepted_updates_mismatch:{result[0]}")
    if result[1] != 0.9:
        failures.append(f"accepted_util_mismatch:{result[1]}")
    if result[3] != ["geometry", "bottom_reinforcement"]:
        failures.append(f"accepted_subfamilies_mismatch:{result[3]}")
    if result[4] != "bending-fold-id":
        failures.append(f"accepted_candidate_id_mismatch:{result[4]}")
    accepted_evidence = dict(result[2])
    for key in (
        "terminal_candidate_status",
        "same_click_terminalisation_fold",
        "same_click_bending_cleanup_folded_residual_bending",
        "no_second_cta_required",
    ):
        if key not in accepted_evidence:
            failures.append(f"accepted_evidence_key_missing:{key}:{accepted_evidence}")
    if accepted_evidence.get("terminal_candidate_status") != "TERMINAL_TARGET_BAND":
        failures.append(f"accepted_terminal_status_mismatch:{accepted_evidence}")
    if accepted_evidence.get("folded_candidate_ids") != ["bending-fold-id", "followup-id"]:
        failures.append(f"accepted_folded_ids_mismatch:{accepted_evidence}")
    if debug.get("same_click_bending_cleanup_folded_residual_bending") is not True:
        failures.append(f"accepted_debug_flag_missing:{debug}")
    if debug.get("same_click_bending_cleanup_folded_updates") != {"bottom_bars": 4, "depth": 475}:
        failures.append(f"accepted_debug_updates_mismatch:{debug}")
    if not calls["overview"] or not calls["eval"]:
        failures.append(f"accepted_calls_missing:{calls}")

    calls = {"overview": [], "contract": [], "eval": []}
    debug = {}
    try:
        _install_common(followup_contract_enabled=False)
        result = _call(debug=debug)
    finally:
        _restore()
    cases.append({"name": "disabled_contract_reresolved", "result": result, "debug": dict(debug), "calls": calls})
    if not calls["contract"]:
        failures.append("disabled_contract_not_reresolved")
    if result[4] != "bending-fold-id":
        failures.append(f"disabled_contract_result_mismatch:{result}")

    for case_name, kwargs in (
        ("terminal_util_already_in_band", {"terminal_util": 0.9}),
        ("followup_updates_match_state", {"updates_match": True}),
        (
            "followup_not_apply_action",
            {"followup_resolution": {"action_type": None, "updates": {"depth": 475}}},
        ),
        ("trial_rejected", {"trial_acceptance": {"accepted": False}}),
        (
            "trial_util_out_of_band",
            {"trial_overview": {"any_fail": False, "utils": {"bending": 1.2}, "statuses": {}}},
        ),
    ):
        calls = {"overview": [], "contract": [], "eval": []}
        debug = {}
        try:
            _install_common(**kwargs)
            result = _call(debug=debug)
        finally:
            _restore()
        cases.append({"name": case_name, "result": result, "debug": dict(debug), "calls": calls})
        if result != (
            {"bottom_bars": 4},
            0.7,
            {"target_band_candidate_count": 0},
            ["bottom_reinforcement"],
            "old-id",
        ):
            failures.append(f"{case_name}_result_mismatch:{result}")
        if debug:
            failures.append(f"{case_name}_debug_changed:{debug}")

    payload = {
        "verifier": "inputs_page_pre_presentation_terminal_bending_fold_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Terminal Bending Fold Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
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
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
