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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_bending_cleanup_publication_debug_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_bending_cleanup_publication_debug_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_recommendation = inputs_page._recommendation_result_for_primary_guidance_card
    original_contract_enabled = inputs_page._design_guide_button_contract_enabled

    failures: list[str] = []
    cases: list[dict] = []
    calls: list[dict] = []

    def fake_recommendation(items, state, *, branch, request_kind):
        calls.append(
            {
                "fn": "recommendation",
                "item_count": len(items),
                "state": dict(state or {}),
                "branch": branch,
                "request_kind": request_kind,
            }
        )
        return {
            "branch": branch,
            "request_kind": request_kind,
            "item_title": dict(items[0] if items else {}).get("title"),
        }

    def fake_contract_enabled(contract):
        calls.append({"fn": "contract_enabled", "contract": dict(contract or {})})
        return bool(dict(contract or {}).get("enabled"))

    def run_case(name: str, *, target_proven: bool, contract_enabled: bool) -> None:
        calls.clear()
        item = {"title": "Reduce bottom steel", "display_truth": {"visible": True}}
        contract = {"enabled": contract_enabled, "expected_util": 0.91}
        guidance_debug = {"before": True}
        (
            guidance_items,
            dg_presentation,
            presentation_headline,
            presentation_subtext,
            recommendation_result,
            updated_debug,
        ) = inputs_page.render_design_guide_presentation_bending_cleanup_publication_debug_setup(
            presentation_bending_item=item,
            presentation_bending_title="Reduce bottom steel",
            presentation_bending_family="bending",
            presentation_bending_contract=contract,
            presentation_bending_target_proven=target_proven,
            guidance_disp_state={"D": 500},
            guidance_debug=guidance_debug,
        )
        cases.append(
            {
                "name": name,
                "target_proven": target_proven,
                "contract_enabled": contract_enabled,
                "recommendation_result": recommendation_result,
                "calls": list(calls),
            }
        )
        if guidance_items != [item]:
            failures.append(f"{name}:guidance_items_mismatch:{guidance_items}")
        if dg_presentation != {} or presentation_headline != "" or presentation_subtext != "":
            failures.append(
                f"{name}:presentation_defaults_mismatch:{dg_presentation}:{presentation_headline}:{presentation_subtext}"
            )
        if recommendation_result.get("branch") != "bending_below_target_bending_only_cleanup":
            failures.append(f"{name}:recommendation_branch_mismatch:{recommendation_result}")
        if recommendation_result.get("request_kind") != "design_guide":
            failures.append(f"{name}:recommendation_request_kind_mismatch:{recommendation_result}")
        if updated_debug.get("terminal_green_low_bending_presentation_suppressed") is not True:
            failures.append(f"{name}:terminal_green_suppression_missing")
        if updated_debug.get("guidance_branch") != "bending_below_target_bending_only_cleanup":
            failures.append(f"{name}:guidance_branch_mismatch:{updated_debug}")
        expected_action_type = "apply_resolved_candidate" if target_proven else None
        if updated_debug.get("selected_action_type") != expected_action_type:
            failures.append(f"{name}:selected_action_type_mismatch:{updated_debug}")
        expected_family = "bending" if target_proven else None
        if updated_debug.get("selected_action_family") != expected_family:
            failures.append(f"{name}:selected_action_family_mismatch:{updated_debug}")
        expected_intent = "efficiency_tightening" if target_proven else "specific_blocker"
        if updated_debug.get("primary_guidance_intent") != expected_intent:
            failures.append(f"{name}:primary_guidance_intent_mismatch:{updated_debug}")
        if updated_debug.get("primary_button_contract") != contract:
            failures.append(f"{name}:primary_button_contract_mismatch:{updated_debug}")
        if updated_debug.get("button_contract") != contract:
            failures.append(f"{name}:button_contract_mismatch:{updated_debug}")
        if updated_debug.get("button_contract_enabled") is not contract_enabled:
            failures.append(f"{name}:button_contract_enabled_mismatch:{updated_debug}")
        if updated_debug.get("primary_display_truth") != {"visible": True}:
            failures.append(f"{name}:primary_display_truth_mismatch:{updated_debug}")
        if updated_debug.get("design_guide_terminal_state") is not None:
            failures.append(f"{name}:terminal_state_not_cleared:{updated_debug}")
        if not any(call.get("fn") == "recommendation" for call in calls):
            failures.append(f"{name}:missing_recommendation_call")
        if not any(call.get("fn") == "contract_enabled" for call in calls):
            failures.append(f"{name}:missing_contract_enabled_call")

    try:
        inputs_page._recommendation_result_for_primary_guidance_card = fake_recommendation
        inputs_page._design_guide_button_contract_enabled = fake_contract_enabled
        run_case("target_proven_stamps_actionable_debug", target_proven=True, contract_enabled=True)
        run_case("target_not_proven_stamps_specific_blocker_debug", target_proven=False, contract_enabled=False)
    finally:
        inputs_page._recommendation_result_for_primary_guidance_card = original_recommendation
        inputs_page._design_guide_button_contract_enabled = original_contract_enabled

    payload_out = {
        "verifier": "inputs_page_presentation_bending_cleanup_publication_debug_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Bending Cleanup Publication Debug Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['target_proven']}`" for case in cases),
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
