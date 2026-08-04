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


class _FakeStreamlit:
    def __init__(self, session_state: dict[str, Any]) -> None:
        self.session_state = session_state


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_engine_evidence_rebind_probe_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_engine_evidence_rebind_probe_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_updates_match_state": inputs_page._updates_match_state,
        "_record_controller_pre_helper_rebind_branch_predicate_probe": (
            inputs_page._record_controller_pre_helper_rebind_branch_predicate_probe
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
        session_engine: dict,
        guidance_debug: dict,
        displayed_evidence: dict,
        displayed_contract: dict,
        displayed_item: dict | None,
        updates_match: bool,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _updates_match_state(state, updates):
            events.append({"event": "updates_match", "state": dict(state or {}), "updates": dict(updates or {})})
            return bool(updates_match)

        def _probe(**kwargs):
            events.append(
                {
                    "event": "probe",
                    "callsite_id": kwargs.get("callsite_id"),
                    "predicates": dict(kwargs.get("predicates") or {}),
                    "debug_keys": sorted(dict(kwargs.get("guidance_debug") or {}).keys()),
                }
            )

        try:
            inputs_page.st = _FakeStreamlit({"_design_guide_engine_decision": dict(session_engine)})
            inputs_page._updates_match_state = _updates_match_state
            inputs_page._record_controller_pre_helper_rebind_branch_predicate_probe = _probe
            result = inputs_page.render_design_guide_engine_evidence_and_rebind_probe_setup(
                displayed_primary_item=None if displayed_item is None else dict(displayed_item),
                displayed_primary_candidate_search_evidence=dict(displayed_evidence),
                displayed_primary_button_contract=dict(displayed_contract),
                guidance_disp_state={"D": 500},
                guidance_debug=dict(guidance_debug),
            )
        finally:
            _restore()

        (
            engine_decision_debug,
            engine_card_debug,
            engine_button_debug,
            engine_outcome_debug,
            engine_trace_debug,
            engine_candidate_search_evidence,
            proof_action_contract_for_evidence,
        ) = result
        case = {
            "name": name,
            "events": events,
            "engine_decision_debug": engine_decision_debug,
            "engine_card_debug": engine_card_debug,
            "engine_button_debug": engine_button_debug,
            "engine_outcome_debug": engine_outcome_debug,
            "engine_trace_debug": engine_trace_debug,
            "engine_candidate_search_evidence": engine_candidate_search_evidence,
            "proof_action_contract_for_evidence": proof_action_contract_for_evidence,
        }
        cases.append(case)
        return case

    displayed = _run_case(
        "displayed_evidence_precedence",
        session_engine={
            "card": {"candidate_search_evidence": {"family": "bending"}},
            "button_contract": {"family": "session"},
            "target_band_outcome": {"preview_util": 0.9},
            "debug": {"candidate_search_evidence": {"family": "trace"}},
        },
        guidance_debug={
            "candidate_search_evidence": {"family": "debug"},
            "primary_button_contract": {"family": "debug_contract"},
        },
        displayed_evidence={
            "family": "combined",
            "selected_candidate_updates": {"D": 550},
            "cleanup_search_ran": True,
        },
        displayed_contract={"family": "displayed", "updates": {"D": 500}},
        displayed_item={"id": "primary"},
        updates_match=False,
    )
    if displayed["engine_candidate_search_evidence"].get("family") != "combined":
        failures.append(f"displayed_evidence_precedence_mismatch:{displayed['engine_candidate_search_evidence']}")
    if displayed["proof_action_contract_for_evidence"].get("family") != "displayed":
        failures.append(f"displayed_contract_precedence_mismatch:{displayed['proof_action_contract_for_evidence']}")
    probe_events = [event for event in displayed["events"] if event.get("event") == "probe"]
    if len(probe_events) != 1:
        failures.append(f"displayed_probe_missing:{displayed['events']}")
    else:
        predicates = probe_events[0]["predicates"]
        expected_predicates = {
            "engine_evidence_family_is_combined": True,
            "engine_evidence_updates_present": True,
            "displayed_contract_updates_differ": True,
            "updates_not_already_applied": True,
            "cleanup_search_evidence_present": True,
            "displayed_primary_item_is_dict": True,
        }
        if predicates != expected_predicates:
            failures.append(f"displayed_predicates_mismatch:{predicates}")

    fallback = _run_case(
        "session_engine_fallback",
        session_engine={
            "card": {"candidate_search_evidence": {"family": "card", "best_safe_candidate_updates": {"b": 1}}},
            "button_contract": {"family": "engine_button"},
            "debug": {"candidate_search_evidence": {"family": "trace"}},
        },
        guidance_debug={},
        displayed_evidence={},
        displayed_contract={},
        displayed_item=None,
        updates_match=True,
    )
    if fallback["engine_candidate_search_evidence"].get("family") != "card":
        failures.append(f"fallback_evidence_mismatch:{fallback['engine_candidate_search_evidence']}")
    if fallback["proof_action_contract_for_evidence"].get("family") != "engine_button":
        failures.append(f"fallback_contract_mismatch:{fallback['proof_action_contract_for_evidence']}")
    fallback_probe = [event for event in fallback["events"] if event.get("event") == "probe"][0]
    if fallback_probe["predicates"].get("updates_not_already_applied") is not False:
        failures.append(f"fallback_updates_match_mismatch:{fallback_probe['predicates']}")
    if fallback_probe["predicates"].get("displayed_primary_item_is_dict") is not False:
        failures.append(f"fallback_item_predicate_mismatch:{fallback_probe['predicates']}")

    debug_contract = _run_case(
        "debug_contract_precedence",
        session_engine={"button_contract": {"family": "engine_button"}},
        guidance_debug={"button_contract": {"family": "debug_button"}},
        displayed_evidence={},
        displayed_contract={},
        displayed_item={"id": "primary"},
        updates_match=True,
    )
    if debug_contract["proof_action_contract_for_evidence"].get("family") != "debug_button":
        failures.append(f"debug_contract_mismatch:{debug_contract['proof_action_contract_for_evidence']}")

    payload = {
        "verifier": "inputs_page_engine_evidence_rebind_probe_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Engine Evidence Rebind Probe Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` evidence_family: `{case['engine_candidate_search_evidence'].get('family')}`, proof_family: `{case['proof_action_contract_for_evidence'].get('family')}`"
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
