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
    json_path = ARTIFACT_DIR / f"inputs_page_displayed_primary_safe_combined_promotion_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_displayed_primary_safe_combined_promotion_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_visible_safe_combined_cleanup_action_from_evidence": inputs_page._visible_safe_combined_cleanup_action_from_evidence,
        "_build_final_design_guide_displayed_primary_safe_combined_promotion_result": (
            inputs_page._build_final_design_guide_displayed_primary_safe_combined_promotion_result
        ),
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        initial_contract: dict,
        evidence_item: dict | None,
        proof: dict | None,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _contract_enabled(contract):
            events.append({"event": "contract_enabled", "contract": dict(contract or {})})
            return bool(dict(contract or {}).get("enabled"))

        def _evidence(item, overview, state, *, debug_sink):
            events.append(
                {
                    "event": "evidence",
                    "item": dict(item or {}),
                    "overview": dict(overview or {}),
                    "state": dict(state or {}),
                }
            )
            if isinstance(debug_sink, dict):
                debug_sink["evidence_called"] = True
            return None if evidence_item is None else dict(evidence_item)

        def _proof(**kwargs):
            events.append(
                {
                    "event": "proof",
                    "item": dict(kwargs.get("item") or {}),
                    "existing_button_contract": dict(kwargs.get("existing_button_contract") or {}),
                }
            )
            return {} if proof is None else dict(proof)

        try:
            inputs_page._design_guide_button_contract_enabled = _contract_enabled
            inputs_page._visible_safe_combined_cleanup_action_from_evidence = _evidence
            inputs_page._build_final_design_guide_displayed_primary_safe_combined_promotion_result = _proof
            result = inputs_page.render_design_guide_displayed_primary_safe_combined_promotion(
                displayed_primary_item={
                    "id": "initial",
                    "action_payload": {"initial_payload": True},
                    "resolved_candidate": {"initial_resolved": True},
                    "candidate_search_evidence": {"initial_evidence": True},
                },
                displayed_primary_payload={"initial_payload": True},
                displayed_primary_resolved={"initial_resolved": True},
                displayed_primary_candidate_search_evidence={"initial_evidence": True},
                displayed_primary_button_contract=dict(initial_contract),
                overview={"worst_util": 1.2},
                guidance_disp_state={"state": True},
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
            displayed_primary_button_contract,
        ) = result
        case = {
            "name": name,
            "events": events,
            "guidance_debug": guidance_debug,
            "displayed_primary_item": displayed_primary_item,
            "displayed_primary_payload": displayed_primary_payload,
            "displayed_primary_resolved": displayed_primary_resolved,
            "displayed_primary_candidate_search_evidence": displayed_primary_candidate_search_evidence,
            "displayed_primary_button_contract": displayed_primary_button_contract,
        }
        cases.append(case)
        return case

    noop = _run_case(
        "contract_enabled_noop",
        initial_contract={"enabled": True, "family": "bending"},
        evidence_item={"id": "should_not_apply"},
        proof={"result": {"applies": True}},
    )
    if [event["event"] for event in noop["events"]] != ["contract_enabled"]:
        failures.append(f"noop_events_mismatch:{noop['events']}")
    if noop["displayed_primary_item"].get("id") != "initial":
        failures.append(f"noop_item_changed:{noop['displayed_primary_item']}")

    evidence = _run_case(
        "evidence_item_promoted",
        initial_contract={"enabled": False},
        evidence_item={
            "id": "evidence",
            "title_main": "Evidence primary",
            "action_payload": {"payload": True, "candidate_search_evidence": {"payload_evidence": True}},
            "resolved_candidate": {"resolved": True},
            "button_contract": {"enabled": False, "family": "combined"},
        },
        proof={"result": {"applies": False}, "proof_hash": "proof-noop", "result_hash": "result-noop"},
    )
    if evidence["displayed_primary_item"].get("id") != "evidence":
        failures.append(f"evidence_item_not_promoted:{evidence['displayed_primary_item']}")
    if evidence["displayed_primary_payload"] != {"payload": True, "candidate_search_evidence": {"payload_evidence": True}}:
        failures.append(f"evidence_payload_mismatch:{evidence['displayed_primary_payload']}")
    if evidence["displayed_primary_candidate_search_evidence"] != {"payload_evidence": True}:
        failures.append(f"evidence_search_mismatch:{evidence['displayed_primary_candidate_search_evidence']}")
    if evidence["guidance_debug"].get("displayed_primary_promoted_from_safe_combined_evidence") is not True:
        failures.append(f"evidence_debug_missing:{evidence['guidance_debug']}")
    if evidence["guidance_debug"].get("primary_card_intent") != "efficiency_tightening":
        failures.append(f"evidence_intent_mismatch:{evidence['guidance_debug']}")

    proof_case = _run_case(
        "proof_result_applied",
        initial_contract={"enabled": False},
        evidence_item=None,
        proof={
            "proof_hash": "proof-1",
            "result_hash": "result-1",
            "result": {
                "applies": True,
                "button_contract_effect": {"enabled": True, "family": "combined"},
                "item_effect": {"id": "proof", "title_main": "Proof primary"},
                "action_payload_effect": {"proof_payload": True},
                "resolved_candidate_effect": {"proof_resolved": True},
            },
        },
    )
    if proof_case["displayed_primary_button_contract"] != {"enabled": True, "family": "combined"}:
        failures.append(f"proof_contract_mismatch:{proof_case['displayed_primary_button_contract']}")
    if proof_case["displayed_primary_item"].get("id") != "proof":
        failures.append(f"proof_item_mismatch:{proof_case['displayed_primary_item']}")
    if proof_case["displayed_primary_payload"].get("proof_payload") is not True:
        failures.append(f"proof_payload_mismatch:{proof_case['displayed_primary_payload']}")
    if proof_case["displayed_primary_resolved"].get("proof_resolved") is not True:
        failures.append(f"proof_resolved_mismatch:{proof_case['displayed_primary_resolved']}")
    if proof_case["guidance_debug"].get("displayed_primary_safe_combined_promotion_proof_hash") != "proof-1":
        failures.append(f"proof_hash_mismatch:{proof_case['guidance_debug']}")
    if proof_case["guidance_debug"].get("displayed_primary_safe_combined_promotion_result_hash") != "result-1":
        failures.append(f"result_hash_mismatch:{proof_case['guidance_debug']}")

    payload = {
        "verifier": "inputs_page_displayed_primary_safe_combined_promotion_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Displayed Primary Safe Combined Promotion Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` item: `{(case['displayed_primary_item'] or {}).get('id')}`, contract: `{case['displayed_primary_button_contract']}`"
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
