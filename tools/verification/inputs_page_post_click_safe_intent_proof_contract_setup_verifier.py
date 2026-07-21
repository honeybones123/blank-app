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
    json_path = ARTIFACT_DIR / f"inputs_page_post_click_safe_intent_proof_contract_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_click_safe_intent_proof_contract_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_build_final_design_guide_post_click_safe_intent_allowed_gate_result": (
            inputs_page._build_final_design_guide_post_click_safe_intent_allowed_gate_result
        ),
        "_build_final_design_guide_post_click_proof_intent_contract_result": (
            inputs_page._build_final_design_guide_post_click_proof_intent_contract_result
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
        session_state: dict[str, Any],
        gate_allowed: bool,
        contract_applies: bool,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        displayed_item = {"family": "bending", "title": "before"}
        displayed_contract = {"family": "displayed", "updates": {"D": 500}}
        proof_contract = {"family": "proof", "updates": {"D": 525}}
        guidance_debug: dict[str, Any] = {"initial": True}

        def _gate(**kwargs):
            events.append(
                {
                    "event": "gate",
                    "post_click_apply_context": bool(kwargs.get("post_click_apply_context")),
                    "state": dict(kwargs.get("state") or {}),
                }
            )
            return {"result": {"allowed": bool(gate_allowed)}, "proof_hash": f"gate-{gate_allowed}"}

        def _contract(**kwargs):
            events.append(
                {
                    "event": "contract",
                    "item": dict(kwargs.get("item") or {}),
                    "debug_keys": sorted(dict(kwargs.get("guidance_debug") or {}).keys()),
                }
            )
            return {
                "result": {
                    "applies": bool(contract_applies),
                    "proof_action_contract_effect": {"family": "effect", "updates": {"D": 600}},
                    "displayed_primary_button_contract_effect": {
                        "family": "displayed_effect",
                        "updates": {"D": 600},
                    },
                    "item_effect": {"title": "after", "effect_applied": True},
                    "debug_effect": {"debug_effect_applied": True},
                },
                "proof_hash": f"contract-{contract_applies}",
            }

        try:
            inputs_page.st = _FakeStreamlit(session_state)
            inputs_page._build_final_design_guide_post_click_safe_intent_allowed_gate_result = _gate
            inputs_page._build_final_design_guide_post_click_proof_intent_contract_result = _contract
            result_displayed_contract, result_proof_contract = (
                inputs_page.render_design_guide_post_click_safe_intent_and_proof_contract_setup(
                    displayed_primary_item=displayed_item,
                    displayed_primary_button_contract=dict(displayed_contract),
                    proof_action_contract_for_evidence=dict(proof_contract),
                    guidance_disp_state={"D": 500},
                    guidance_debug=guidance_debug,
                )
            )
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "displayed_item": displayed_item,
            "guidance_debug": guidance_debug,
            "result_displayed_contract": result_displayed_contract,
            "result_proof_contract": result_proof_contract,
        }
        cases.append(case)
        return case

    normal = _run_case(
        "no_post_click_context_applies_contract",
        session_state={},
        gate_allowed=False,
        contract_applies=True,
    )
    if [event["event"] for event in normal["events"]] != ["contract"]:
        failures.append(f"normal_event_sequence_mismatch:{normal['events']}")
    if normal["result_proof_contract"].get("family") != "effect":
        failures.append(f"normal_proof_contract_mismatch:{normal['result_proof_contract']}")
    if normal["result_displayed_contract"].get("family") != "displayed_effect":
        failures.append(f"normal_displayed_contract_mismatch:{normal['result_displayed_contract']}")
    if normal["displayed_item"].get("title") != "after":
        failures.append(f"normal_item_effect_missing:{normal['displayed_item']}")
    if normal["guidance_debug"].get("post_click_proof_intent_contract_proof_hash") != "contract-True":
        failures.append(f"normal_debug_proof_hash_missing:{normal['guidance_debug']}")

    blocked = _run_case(
        "post_click_context_gate_blocks_contract",
        session_state={
            inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY: {
                "apply_used_resolved_candidate_payload": True,
                "applied_updates": {"D": 500},
            }
        },
        gate_allowed=False,
        contract_applies=True,
    )
    if [event["event"] for event in blocked["events"]] != ["gate"]:
        failures.append(f"blocked_event_sequence_mismatch:{blocked['events']}")
    if blocked["result_proof_contract"].get("family") != "proof":
        failures.append(f"blocked_proof_contract_changed:{blocked['result_proof_contract']}")
    if blocked["result_displayed_contract"].get("family") != "displayed":
        failures.append(f"blocked_displayed_contract_changed:{blocked['result_displayed_contract']}")
    if blocked["guidance_debug"].get("post_click_safe_intent_allowed_gate_proof_hash") != "gate-False":
        failures.append(f"blocked_gate_hash_missing:{blocked['guidance_debug']}")
    if "post_click_proof_intent_contract_cutover_applied" in blocked["guidance_debug"]:
        failures.append(f"blocked_contract_debug_unexpected:{blocked['guidance_debug']}")

    allowed_no_apply = _run_case(
        "post_click_context_gate_allows_no_contract_effect",
        session_state={
            inputs_page.DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY: {
                "apply_used_resolved_candidate_payload": True,
                "applied_updates": {"D": 500},
            }
        },
        gate_allowed=True,
        contract_applies=False,
    )
    if [event["event"] for event in allowed_no_apply["events"]] != ["gate", "contract"]:
        failures.append(f"allowed_no_apply_event_sequence_mismatch:{allowed_no_apply['events']}")
    if allowed_no_apply["result_proof_contract"].get("family") != "proof":
        failures.append(f"allowed_no_apply_proof_contract_changed:{allowed_no_apply['result_proof_contract']}")
    if allowed_no_apply["result_displayed_contract"].get("family") != "displayed":
        failures.append(
            f"allowed_no_apply_displayed_contract_changed:{allowed_no_apply['result_displayed_contract']}"
        )
    if allowed_no_apply["guidance_debug"].get("post_click_safe_intent_allowed_gate_proof_hash") != "gate-True":
        failures.append(f"allowed_no_apply_gate_hash_missing:{allowed_no_apply['guidance_debug']}")

    payload = {
        "verifier": "inputs_page_post_click_safe_intent_proof_contract_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Click Safe Intent Proof Contract Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` events: `{','.join(event['event'] for event in case['events'])}`"
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
