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
    json_path = ARTIFACT_DIR / f"inputs_page_residual_width_cleanup_publication_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_residual_width_cleanup_publication_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_updates_match_state": inputs_page._updates_match_state,
        "_canonical_overdesign_family_from_updates": inputs_page._canonical_overdesign_family_from_updates,
        "_design_guide_apply_button_contracts_to_items": inputs_page._design_guide_apply_button_contracts_to_items,
        "_design_guide_apply_display_truth_to_items": inputs_page._design_guide_apply_display_truth_to_items,
        "_recommendation_result_for_primary_guidance_card": inputs_page._recommendation_result_for_primary_guidance_card,
    }

    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _install(events: list[str], owner: str):
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(
            isinstance(contract, dict) and contract.get("enabled")
        )
        inputs_page._updates_match_state = lambda current, updates: dict(current or {}) == dict(updates or {})
        inputs_page._canonical_overdesign_family_from_updates = lambda family, updates: owner

        def _buttons(items, *, state):
            events.append("buttons")
            out = [dict(item) for item in list(items or [])]
            for item in out:
                item["buttons_applied"] = True
            return out

        def _display(items, *, state, overview, mode_config):
            events.append("display")
            out = [dict(item) for item in list(items or [])]
            for item in out:
                item["display_applied"] = True
                item["display_overview"] = dict(overview or {})
                item["display_mode"] = dict(mode_config or {})
            return out

        def _recommend(items, state, *, branch, request_kind):
            events.append("recommend")
            return {
                "branch": branch,
                "request_kind": request_kind,
                "count": len(items),
            }

        inputs_page._design_guide_apply_button_contracts_to_items = _buttons
        inputs_page._design_guide_apply_display_truth_to_items = _display
        inputs_page._recommendation_result_for_primary_guidance_card = _recommend

    try:
        false_events: list[str] = []
        _install(false_events, "SHEAR_OVERDESIGN_GOVERNS")
        false_debug: dict[str, Any] = {"existing": True}
        published, items, debug, recommendation = inputs_page.render_design_guide_residual_width_cleanup_publication(
            residual_width_cleanup_item={"id": "inactive"},
            residual_width_cleanup_contract={"enabled": False, "family": "shear"},
            residual_width_cleanup_updates={"D": 550},
            residual_width_match_state={"D": 500},
            guidance_disp_state={"D": 500},
            render_acceptance_overview={"accepted": True},
            render_overview={"render": True},
            render_mode_config={"mode": "unit"},
            guidance_debug=false_debug,
        )
        false_case = {
            "name": "false_gate",
            "events": false_events,
            "published": published,
            "items": items,
            "debug": debug,
            "recommendation": recommendation,
        }
        cases.append(false_case)
        if published or items or recommendation is not None or false_events:
            failures.append(f"false_gate_mismatch:{false_case}")

        true_events: list[str] = []
        _install(true_events, "COMBINED_OVERDESIGN_GOVERNS")
        true_debug: dict[str, Any] = {}
        published, items, debug, recommendation = inputs_page.render_design_guide_residual_width_cleanup_publication(
            residual_width_cleanup_item={"id": "cleanup", "family": "shear"},
            residual_width_cleanup_contract={
                "enabled": True,
                "family": "shear",
                "action_type": "apply_resolved_candidate",
            },
            residual_width_cleanup_updates={"D": 550, "bw": 300},
            residual_width_match_state={"D": 500},
            guidance_disp_state={"D": 500},
            render_acceptance_overview={"accepted": True},
            render_overview={"render": True},
            render_mode_config={"mode": "unit"},
            guidance_debug=true_debug,
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    true_case = {
        "name": "true_gate_combined_owner",
        "events": true_events,
        "published": published,
        "items": items,
        "debug": debug,
        "recommendation": recommendation,
    }
    cases.append(true_case)
    if true_events != ["buttons", "display", "recommend"]:
        failures.append(f"true_event_order_mismatch:{true_events}")
    if not published or len(items) != 1:
        failures.append(f"true_publish_mismatch:{true_case}")
    else:
        item = items[0]
        contract = dict(item.get("button_contract") or {})
        if item.get("selected_family_id") != "COMBINED_OVERDESIGN":
            failures.append(f"selected_family_mismatch:{item.get('selected_family_id')}")
        if item.get("selected_action_family") != "combined":
            failures.append(f"selected_action_family_mismatch:{item.get('selected_action_family')}")
        if contract.get("family") != "COMBINED_OVERDESIGN":
            failures.append(f"contract_family_mismatch:{contract}")
        if item.get("source") != "render_stage_shear_overdesign_residual_width_cleanup_before_accepted_green":
            failures.append(f"source_mismatch:{item.get('source')}")
        if item.get("updates") != {"D": 550, "bw": 300}:
            failures.append(f"updates_mismatch:{item.get('updates')}")
    if debug.get("guidance_branch") != "render_stage_shear_overdesign_residual_width_cleanup_before_accepted_green":
        failures.append("guidance_branch_missing")
    if debug.get("terminal_green_residual_width_cleanup_updates") != {"D": 550, "bw": 300}:
        failures.append("debug_updates_missing")
    if recommendation != {
        "branch": "render_stage_shear_overdesign_residual_width_cleanup_before_accepted_green",
        "request_kind": "design_guide",
        "count": 1,
    }:
        failures.append(f"recommendation_mismatch:{recommendation}")

    payload = {
        "verifier": "inputs_page_residual_width_cleanup_publication_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Residual Width Cleanup Publication Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` events: `{case['events']}`, published: `{case['published']}`" for case in cases),
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
