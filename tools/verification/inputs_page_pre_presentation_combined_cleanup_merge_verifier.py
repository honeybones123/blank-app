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
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_combined_cleanup_merge_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_combined_cleanup_merge_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_overview_has_active_failure": inputs_page._overview_has_active_failure,
        "_design_guide_button_contract": inputs_page._design_guide_button_contract,
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_run_design_guide_combined_low_util_orchestration": inputs_page._run_design_guide_combined_low_util_orchestration,
        "normalise_final_visible_design_guide_item": inputs_page.normalise_final_visible_design_guide_item,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_COMPOUND_SHEAR_UPDATE_KEYS": inputs_page._COMPOUND_SHEAR_UPDATE_KEYS,
        "_COMPOUND_BOTTOM_UPDATE_KEYS": inputs_page._COMPOUND_BOTTOM_UPDATE_KEYS,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install_common(*, active_failure: bool = False, contract: dict | None = None, updates: dict | None = None):
        inputs_page._overview_has_active_failure = lambda overview: bool(active_failure)
        inputs_page._design_guide_button_contract = lambda item, *, state: dict(contract or {})
        inputs_page._resolve_recommendation_updates = lambda item, *, state: dict(updates or {})
        inputs_page._design_guide_button_contract_enabled = lambda contract_arg: bool(contract_arg.get("enabled"))
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"
        inputs_page._COMPOUND_SHEAR_UPDATE_KEYS = {"shear_links", "shear_diameter"}
        inputs_page._COMPOUND_BOTTOM_UPDATE_KEYS = {"bottom_bars"}
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85

    original_items: list = []
    recommendation = {"existing": True}
    debug: dict[str, Any] = {}
    try:
        _install_common()
        result = inputs_page.render_design_guide_pre_presentation_combined_cleanup_merge(
            guidance_items=original_items,
            recommendation_result=recommendation,
            guidance_disp_state={"depth": 500},
            dg_overview={"any_fail": False},
            guidance_debug=debug,
        )
    finally:
        _restore()
    cases.append({"name": "empty_items_noop", "result": result, "debug": dict(debug)})
    if result != (original_items, recommendation):
        failures.append(f"empty_items_noop_mismatch:{result}")
    if debug:
        failures.append(f"empty_items_debug_changed:{debug}")

    original_items = [{"title_main": "Primary", "action_type": "apply_resolved_candidate"}]
    recommendation = {"existing": True}
    debug = {}
    orchestration_calls: list[dict[str, Any]] = []
    try:
        _install_common(active_failure=True, contract={"enabled": True, "updates": {"shear_links": "reduce"}})
        inputs_page._run_design_guide_combined_low_util_orchestration = lambda **kwargs: orchestration_calls.append(kwargs) or {}
        result = inputs_page.render_design_guide_pre_presentation_combined_cleanup_merge(
            guidance_items=original_items,
            recommendation_result=recommendation,
            guidance_disp_state={"depth": 500},
            dg_overview={"any_fail": True},
            guidance_debug=debug,
        )
    finally:
        _restore()
    cases.append({"name": "active_failure_suppresses_merge", "result": result, "debug": dict(debug)})
    if result != (original_items, recommendation):
        failures.append(f"active_failure_result_mismatch:{result}")
    if orchestration_calls:
        failures.append(f"active_failure_orchestration_called:{orchestration_calls}")

    primary_item = {"title_main": "Shear primary", "action_type": "apply_resolved_candidate"}
    combined_item = {"title_main": "Combined cleanup", "raw": True}
    normalised_item = {"title_main": "Combined cleanup normalised", "normalised": True}
    recommendation_result = {"recommendation": True}
    debug = {"overview": {"any_fail": False, "utils": {"shear": 0.4}}}
    orchestration_calls = []

    def _orchestration(**kwargs):
        orchestration_calls.append(kwargs)
        return {"debug_update": {"orchestration_debug": True}, "item": dict(combined_item)}

    try:
        _install_common(contract={"enabled": True, "action_type": "apply_resolved_candidate", "updates": {"shear_links": "reduce"}})
        inputs_page._run_design_guide_combined_low_util_orchestration = _orchestration
        inputs_page.normalise_final_visible_design_guide_item = lambda item: dict(normalised_item)
        inputs_page._recommendation_result_for_primary_guidance_card = (
            lambda items, state, *, branch, request_kind: {
                **recommendation_result,
                "items": list(items),
                "state": dict(state),
                "branch": branch,
                "request_kind": request_kind,
            }
        )
        result = inputs_page.render_design_guide_pre_presentation_combined_cleanup_merge(
            guidance_items=[primary_item],
            recommendation_result={"existing": True},
            guidance_disp_state={"depth": 500},
            dg_overview={"any_fail": False},
            guidance_debug=debug,
        )
    finally:
        _restore()
    cases.append(
        {
            "name": "combined_cleanup_promoted",
            "result": result,
            "debug": dict(debug),
            "orchestration_call_count": len(orchestration_calls),
        }
    )
    if result[0] != [normalised_item]:
        failures.append(f"promotion_items_mismatch:{result[0]}")
    if result[1].get("branch") != "combined_shear_bending_cleanup_pre_presentation":
        failures.append(f"promotion_recommendation_branch_mismatch:{result[1]}")
    if debug.get("combined_cleanup_pre_presentation_promoted") is not True:
        failures.append(f"promotion_debug_flag_missing:{debug}")
    if debug.get("guidance_branch") != "combined_shear_bending_cleanup_pre_presentation":
        failures.append(f"promotion_guidance_branch_mismatch:{debug}")
    if debug.get("selected_title") != normalised_item["title_main"]:
        failures.append(f"promotion_selected_title_mismatch:{debug}")
    if debug.get("selected_action_family") != "combined":
        failures.append(f"promotion_selected_family_mismatch:{debug}")
    if not orchestration_calls:
        failures.append("promotion_orchestration_not_called")
    else:
        call = orchestration_calls[0]
        if call.get("shear_item") != primary_item:
            failures.append(f"promotion_shear_item_mismatch:{call.get('shear_item')}")
        if call.get("compound_shear_update_keys") != {"shear_links", "shear_diameter"}:
            failures.append(f"promotion_shear_keys_mismatch:{call.get('compound_shear_update_keys')}")
        if call.get("final_accepted_min_family_util") != 0.85:
            failures.append(f"promotion_threshold_mismatch:{call.get('final_accepted_min_family_util')}")

    debug = {}
    original_items = [{"title_main": "Primary", "action_type": "apply_resolved_candidate"}]
    try:
        _install_common(contract={"enabled": True, "updates": {"shear_links": "reduce"}})
        inputs_page._run_design_guide_combined_low_util_orchestration = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
        result = inputs_page.render_design_guide_pre_presentation_combined_cleanup_merge(
            guidance_items=original_items,
            recommendation_result={"existing": True},
            guidance_disp_state={"depth": 500},
            dg_overview={"any_fail": False},
            guidance_debug=debug,
        )
    finally:
        _restore()
    cases.append({"name": "orchestration_exception_noop", "result": result, "debug": dict(debug)})
    if result != (original_items, {"existing": True}):
        failures.append(f"exception_result_mismatch:{result}")
    if debug.get("combined_cleanup_pre_presentation_promoted"):
        failures.append(f"exception_promoted_debug_set:{debug}")

    payload = {
        "verifier": "inputs_page_pre_presentation_combined_cleanup_merge_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Combined Cleanup Merge Verifier",
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
