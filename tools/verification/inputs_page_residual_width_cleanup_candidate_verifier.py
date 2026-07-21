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


def _item(name: str, *, enabled: bool, updates: dict | None = None) -> dict:
    return {
        "id": name,
        "updates": dict(updates or {}),
        "button_contract": {
            "enabled": enabled,
            "updates": dict(updates or {}),
        },
    }


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_residual_width_cleanup_candidate_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_residual_width_cleanup_candidate_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_shear_low_util_target_cleanup_item": inputs_page._shear_low_util_target_cleanup_item,
        "_shear_overdesign_contract_width_cleanup_item": inputs_page._shear_overdesign_contract_width_cleanup_item,
        "_live_shear_overdesign_contract_width_cleanup_item": inputs_page._live_shear_overdesign_contract_width_cleanup_item,
        "_combined_low_util_orchestration_item_for_publication_dependency": inputs_page._combined_low_util_orchestration_item_for_publication_dependency,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_updates_match_state": inputs_page._updates_match_state,
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_shared_state_snapshot": inputs_page._shared_state_snapshot,
        "_guidance_state_snapshot": inputs_page._guidance_state_snapshot,
    }

    cases: list[dict[str, Any]] = []
    failures: list[str] = []

    def _run_case(name: str, *, low_item: dict | None, over_item: dict | None, live_item: dict | None, combined_item: dict | None):
        events: list[str] = []
        debug: dict[str, Any] = {}
        state = {"D": 500}
        live_state = {"D": 505, "live": True}

        def _low(*args, **kwargs):
            events.append("low")
            return low_item

        def _over(*args, **kwargs):
            events.append("over")
            return over_item

        def _live(*args, **kwargs):
            events.append("live")
            return live_item

        def _combined(*args, **kwargs):
            events.append("combined")
            return combined_item

        try:
            inputs_page._shear_low_util_target_cleanup_item = _low
            inputs_page._shear_overdesign_contract_width_cleanup_item = _over
            inputs_page._live_shear_overdesign_contract_width_cleanup_item = _live
            inputs_page._combined_low_util_orchestration_item_for_publication_dependency = _combined
            inputs_page._design_guide_button_contract_enabled = lambda contract: bool(
                isinstance(contract, dict) and contract.get("enabled")
            )
            inputs_page._updates_match_state = lambda current, updates: dict(current or {}) == dict(updates or {})
            inputs_page._resolve_recommendation_updates = lambda item, state=None: dict(
                (item or {}).get("updates") or {}
            )
            inputs_page._shared_state_snapshot = lambda: dict(live_state)
            inputs_page._guidance_state_snapshot = lambda snapshot=None: dict(snapshot or {})

            item, contract, updates, match_state = inputs_page.render_design_guide_residual_width_cleanup_candidate(
                guidance_disp_state=state,
                render_acceptance_overview={"overview": "accepted"},
                render_overview={"overview": "render"},
                render_mode_config={"mode": "unit"},
                guidance_debug=debug,
            )
        finally:
            for original_name, original_value in originals.items():
                setattr(inputs_page, original_name, original_value)

        case = {
            "name": name,
            "events": events,
            "item_id": item.get("id") if isinstance(item, dict) else None,
            "contract": contract,
            "updates": updates,
            "match_state": match_state,
            "debug": debug,
        }
        cases.append(case)
        return case

    primary = _run_case(
        "primary_actionable",
        low_item=_item("low", enabled=True, updates={"D": 550}),
        over_item=_item("over", enabled=True, updates={"D": 560}),
        live_item=_item("live", enabled=True, updates={"D": 570}),
        combined_item=None,
    )
    if primary["events"] != ["low", "combined"] or primary["item_id"] != "low":
        failures.append(f"primary_branch_mismatch:{primary}")

    fallback = _run_case(
        "overdesign_fallback_actionable",
        low_item=_item("low", enabled=False, updates={}),
        over_item=_item("over", enabled=True, updates={"D": 560}),
        live_item=_item("live", enabled=True, updates={"D": 570}),
        combined_item=None,
    )
    if fallback["events"] != ["low", "over", "combined"] or fallback["item_id"] != "over":
        failures.append(f"fallback_branch_mismatch:{fallback}")

    live = _run_case(
        "live_fallback_snapshot",
        low_item=_item("low", enabled=False, updates={}),
        over_item=_item("over", enabled=False, updates={}),
        live_item=_item("live", enabled=True, updates={"D": 570}),
        combined_item=None,
    )
    if live["events"] != ["low", "over", "live", "combined"] or live["item_id"] != "live":
        failures.append(f"live_branch_mismatch:{live}")
    if live["match_state"] != {"D": 505, "live": True}:
        failures.append(f"live_match_state_mismatch:{live['match_state']}")

    combined = _run_case(
        "combined_promotion",
        low_item=_item("low", enabled=True, updates={"D": 550}),
        over_item=_item("over", enabled=True, updates={"D": 560}),
        live_item=_item("live", enabled=True, updates={"D": 570}),
        combined_item=_item("combined", enabled=True, updates={"D": 580}),
    )
    if combined["events"] != ["low", "combined"] or combined["item_id"] != "combined":
        failures.append(f"combined_promotion_mismatch:{combined}")
    if combined["debug"].get("render_stage_residual_shear_cleanup_promoted_to_combined_owner") is not True:
        failures.append("combined_debug_flag_missing")

    payload = {
        "verifier": "inputs_page_residual_width_cleanup_candidate_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Residual Width Cleanup Candidate Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(f"- `{case['name']}` events: `{case['events']}`, item: `{case['item_id']}`" for case in cases),
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
