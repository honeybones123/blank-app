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
    json_path = ARTIFACT_DIR / f"inputs_page_active_strength_repair_item_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_strength_repair_item_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    stale_keys = {
        "exact_blockers_by_family": {"bending": "stale"},
        "post_click_exact_blockers_by_family": {"bending": "stale"},
        "cleanup_evidence_by_family": {"bending": "stale"},
        "post_click_cleanup_evidence_by_family": {"bending": "stale"},
        "local_cleanup_blocked_reasons": ["stale"],
        "local_cleanup_blocked_reasons_by_family": {"bending": ["stale"]},
        "exact_blocker_reasons_by_family": {"bending": ["stale"]},
        "blocker_reasons_by_family": {"bending": ["stale"]},
        "active_under_capacity_blocker": True,
        "active_under_capacity_blocker_reason": "stale",
        "active_under_capacity_blocker_family": "bending",
    }
    source_item = {
        **stale_keys,
        "title_main": "Old",
        "title": "Old",
        "family": "old",
        "check_key": "old",
        "selected_action_family": "old",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "final_state_class": "blocker",
        "button_contract": {
            "family": "old",
            "family_id": "OLD",
            "cta_family_id": "OLD",
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "preview_pass": False,
            "blocking_reason": "stale",
            "updates": {"depth": 500},
        },
    }
    item, contract = inputs_page.render_design_guide_active_strength_repair_item_setup(
        source_item=source_item,
        active_repair_family="shear",
        active_repair_title="Shear capacity is low",
        active_selected_family_id="SHEAR_FAIL_GOVERNS",
    )
    cases.append({"name": "restamps_action_item_and_contract", "item": item, "contract": contract})
    for key in stale_keys:
        if key in item:
            failures.append(f"stale_key_not_removed:{key}:{item.get(key)}")
    expected_item_values = {
        "title_main": "Shear capacity is low",
        "title": "Shear capacity is low",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "guidance_intent": "required_fix",
        "primary_card_actionable": True,
        "final_state_class": "action",
    }
    for key, expected in expected_item_values.items():
        if item.get(key) != expected:
            failures.append(f"item_value_mismatch:{key}:{item.get(key)}")
    expected_contract_values = {
        "family": "shear",
        "family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "preview_pass": True,
        "blocking_reason": None,
    }
    for key, expected in expected_contract_values.items():
        if contract.get(key) != expected:
            failures.append(f"contract_value_mismatch:{key}:{contract.get(key)}")
    if contract.get("updates") != {"depth": 500}:
        failures.append(f"contract_updates_changed:{contract}")
    if source_item.get("title_main") != "Old" or source_item.get("button_contract", {}).get("enabled") is not False:
        failures.append("source_item_mutated")

    item, contract = inputs_page.render_design_guide_active_strength_repair_item_setup(
        source_item={"title_main": "Old"},
        active_repair_family="bending",
        active_repair_title="Bending capacity is low",
        active_selected_family_id="",
    )
    cases.append({"name": "empty_contract_stays_empty", "item": item, "contract": contract})
    if contract != {}:
        failures.append(f"empty_contract_mismatch:{contract}")
    if item.get("primary_card_actionable") is not True or item.get("final_state_class") != "action":
        failures.append(f"empty_contract_item_shape_mismatch:{item}")

    payload = {
        "verifier": "inputs_page_active_strength_repair_item_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Strength Repair Item Setup Verifier",
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
