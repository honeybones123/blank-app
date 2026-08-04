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
    json_path = ARTIFACT_DIR / f"inputs_page_displayed_primary_exact_blocker_enrichment_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_displayed_primary_exact_blocker_enrichment_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
        "_design_mode_config": inputs_page._design_mode_config,
        "_resolved_efficiency_target_band": inputs_page._resolved_efficiency_target_band,
        "_design_guide_family_summary_util": inputs_page._design_guide_family_summary_util,
        "_normalise_design_guide_candidate_id": inputs_page._normalise_design_guide_candidate_id,
        "_int_from_state": inputs_page._int_from_state,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        contract: dict,
        item: dict | None,
        evidence: dict,
        state: dict,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _contract_enabled(contract_arg):
            events.append({"event": "contract_enabled", "contract": dict(contract_arg or {})})
            return bool(dict(contract_arg or {}).get("enabled"))

        def _goal(state_arg):
            events.append({"event": "goal", "state": dict(state_arg or {})})
            return "unit_goal"

        def _mode_config(goal):
            events.append({"event": "mode_config", "goal": goal})
            return {"goal": goal}

        def _target_band(mode_config, *, goal):
            events.append({"event": "target_band", "mode_config": dict(mode_config or {}), "goal": goal})
            return 0.80, 0.90, "unit"

        def _family_util(overview, family):
            events.append({"event": "family_util", "family": family})
            return {"bending": 0.42, "shear": 0.44}.get(str(family), 0.5)

        def _candidate_id(*, family, updates):
            events.append({"event": "candidate_id", "family": family, "updates": dict(updates or {})})
            return f"{family}-normalised"

        def _int_from_state(state_arg, key, default=0):
            events.append({"event": "int_from_state", "key": key})
            return int(dict(state_arg or {}).get(key, default) or 0)

        try:
            inputs_page._design_guide_button_contract_enabled = _contract_enabled
            inputs_page._design_optimisation_goal = _goal
            inputs_page._design_mode_config = _mode_config
            inputs_page._resolved_efficiency_target_band = _target_band
            inputs_page._design_guide_family_summary_util = _family_util
            inputs_page._normalise_design_guide_candidate_id = _candidate_id
            inputs_page._int_from_state = _int_from_state
            result = inputs_page.render_design_guide_displayed_primary_exact_blocker_enrichment(
                displayed_primary_item=None if item is None else dict(item),
                displayed_primary_payload=dict((item or {}).get("action_payload") or {}),
                displayed_primary_resolved=dict((item or {}).get("resolved_candidate") or {}),
                displayed_primary_candidate_search_evidence=dict(evidence),
                displayed_primary_button_contract=dict(contract),
                overview={"overview": True},
                guidance_disp_state=dict(state),
                guidance_debug={"existing": True},
            )
        finally:
            _restore()

        (
            guidance_debug,
            displayed_primary_item,
            displayed_primary_payload,
            displayed_primary_resolved,
            displayed_primary_candidate_search_evidence,
        ) = result
        case = {
            "name": name,
            "events": events,
            "guidance_debug": guidance_debug,
            "displayed_primary_item": displayed_primary_item,
            "displayed_primary_payload": displayed_primary_payload,
            "displayed_primary_resolved": displayed_primary_resolved,
            "displayed_primary_candidate_search_evidence": displayed_primary_candidate_search_evidence,
        }
        cases.append(case)
        return case

    bending = _run_case(
        "bending_enriched",
        contract={
            "enabled": True,
            "family": "bending",
            "expected_util": 0.96,
            "updates": {"bot_dia": 20},
        },
        item={"id": "primary", "action_payload": {}, "resolved_candidate": {}},
        evidence={"attempted_candidate_count": 4, "safe_candidate_count": 2},
        state={},
    )
    bending_exact = bending["displayed_primary_candidate_search_evidence"].get("exact_blockers_by_family", {})
    if "bending" not in bending_exact:
        failures.append(f"bending_exact_missing:{bending_exact}")
    else:
        bending_blocker = bending_exact["bending"]
        if bending_blocker.get("best_safe_candidate_id") != "bending-normalised":
            failures.append(f"bending_candidate_id_mismatch:{bending_blocker}")
        if bending_blocker.get("attempted_candidate_count") != 4 or bending_blocker.get("safe_candidate_count") != 2:
            failures.append(f"bending_counts_mismatch:{bending_blocker}")
        if bending_blocker.get("target_high") != 0.90:
            failures.append(f"bending_target_high_mismatch:{bending_blocker}")
    if bending["displayed_primary_payload"].get("candidate_search_evidence", {}).get("exact_blockers_by_family") != bending_exact:
        failures.append(f"bending_payload_evidence_missing:{bending['displayed_primary_payload']}")
    if bending["guidance_debug"].get("exact_blockers_by_family") != bending_exact:
        failures.append(f"bending_debug_maps_mismatch:{bending['guidance_debug']}")

    combined = _run_case(
        "combined_selects_shear_floor",
        contract={
            "enabled": True,
            "family": "combined",
            "expected_util": 0.95,
            "updates": {"lig_d": 0, "lig_legs": 0},
        },
        item={
            "id": "primary",
            "family_status_preview": {
                "bending": {"before_util": 0.40, "after_util": 0.96},
                "shear": {"before_util": 0.41, "after_util": 0.98},
            },
            "action_payload": {},
            "resolved_candidate": {},
        },
        evidence={"candidate_rows": [{"id": 1}]},
        state={"lig_d": 0, "lig_legs": 0},
    )
    combined_exact = combined["displayed_primary_candidate_search_evidence"].get("exact_blockers_by_family", {})
    if "shear" not in combined_exact:
        failures.append(f"combined_shear_exact_missing:{combined_exact}")
    else:
        shear_blocker = combined_exact["shear"]
        if shear_blocker.get("best_safe_final_util") != 0.98:
            failures.append(f"combined_shear_util_mismatch:{shear_blocker}")
        if "shear-link floor" not in str(shear_blocker.get("reason") or ""):
            failures.append(f"combined_shear_floor_reason_missing:{shear_blocker}")

    noop = _run_case(
        "target_band_candidate_present_noop",
        contract={
            "enabled": True,
            "family": "bending",
            "expected_util": 0.96,
            "updates": {"bot_dia": 20},
        },
        item={"id": "primary", "action_payload": {}, "resolved_candidate": {}},
        evidence={"target_band_candidate_count": 1},
        state={},
    )
    if "exact_blockers_by_family" in noop["displayed_primary_candidate_search_evidence"]:
        failures.append(f"noop_enriched_unexpected:{noop['displayed_primary_candidate_search_evidence']}")

    disabled = _run_case(
        "disabled_contract_noop",
        contract={"enabled": False, "family": "bending", "expected_util": 0.96},
        item={"id": "primary", "action_payload": {}, "resolved_candidate": {}},
        evidence={},
        state={},
    )
    if [event.get("event") for event in disabled["events"]] != ["contract_enabled"]:
        failures.append(f"disabled_events_mismatch:{disabled['events']}")
    if "exact_blockers_by_family" in disabled["guidance_debug"]:
        failures.append(f"disabled_debug_enriched_unexpected:{disabled['guidance_debug']}")

    payload = {
        "verifier": "inputs_page_displayed_primary_exact_blocker_enrichment_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Displayed Primary Exact Blocker Enrichment Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` exact families: `{sorted((case['displayed_primary_candidate_search_evidence'].get('exact_blockers_by_family') or {}).keys())}`"
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
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
