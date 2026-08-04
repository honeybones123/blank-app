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
    json_path = ARTIFACT_DIR / (
        f"inputs_page_render_stage_intent_contract_rebind_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_render_stage_intent_contract_rebind_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
        "_build_final_visible_render_stage_intent_contract_rebind_result": (
            inputs_page._build_final_visible_render_stage_intent_contract_rebind_result
        ),
        "_record_rendered_design_guide_primary_apply_payload": (
            inputs_page._record_rendered_design_guide_primary_apply_payload
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []
    enabled_response = False
    builder_response: dict | Exception = {}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def contract_enabled(contract):
        events.append({"event": "contract_enabled", "contract": dict(contract or {})})
        return bool(enabled_response)

    def build_rebind_result(*, item, contract, guidance_debug):
        events.append(
            {
                "event": "build_rebind_result",
                "item": dict(item or {}),
                "contract": dict(contract or {}),
                "guidance_debug": dict(guidance_debug or {}),
            }
        )
        if isinstance(builder_response, Exception):
            raise builder_response
        return dict(builder_response or {})

    def record_payload(*, item, rec, button_contract, state):
        events.append(
            {
                "event": "record_payload",
                "item": dict(item or {}),
                "rec": dict(rec or {}),
                "button_contract": dict(button_contract or {}),
                "state": dict(state or {}),
            }
        )

    def run_case(
        name: str,
        *,
        item: dict,
        contract: dict,
        debug: dict | None = None,
        state: dict | None = None,
        enabled: bool = False,
        proof: dict | Exception | None = None,
    ) -> dict:
        nonlocal events, enabled_response, builder_response
        events = []
        enabled_response = bool(enabled)
        builder_response = proof if proof is not None else {}
        guidance_debug = dict(debug or {})
        result_item, result_contract = (
            inputs_page.render_design_guide_render_stage_intent_contract_rebind(
                final_visible_item=dict(item or {}),
                final_visible_contract=dict(contract or {}),
                guidance_debug=guidance_debug,
                guidance_disp_state=dict(state or {}),
            )
        )
        case = {
            "name": name,
            "item": result_item,
            "contract": result_contract,
            "debug": guidance_debug,
            "events": list(events),
        }
        cases.append(case)
        return case

    try:
        inputs_page._design_guide_button_contract_enabled = contract_enabled
        inputs_page._build_final_visible_render_stage_intent_contract_rebind_result = (
            build_rebind_result
        )
        inputs_page._record_rendered_design_guide_primary_apply_payload = record_payload

        case = run_case(
            "enabled_contract_noop",
            item={"title_main": "Enabled item"},
            contract={"enabled": True, "updates": {"D": 600}},
            debug={"seed": True},
            enabled=True,
            proof={
                "proof_hash": "should-not-run",
                "result": {"applies": True},
            },
        )
        expect(
            "enabled_contract_noop",
            case["item"] == {"title_main": "Enabled item"}
            and case["contract"] == {"enabled": True, "updates": {"D": 600}}
            and case["debug"] == {"seed": True}
            and [event["event"] for event in case["events"]] == ["contract_enabled"],
            f"case={case}",
        )

        case = run_case(
            "underdesign_boundary_noop",
            item={"title_main": "Boundary item"},
            contract={"enabled": False},
            debug={"contract_boundary_checked": True, "contract_boundary_passed": False},
            enabled=False,
            proof={"proof_hash": "should-not-run"},
        )
        expect(
            "underdesign_boundary_noop",
            case["item"] == {"title_main": "Boundary item"}
            and case["contract"] == {"enabled": False}
            and case["events"] == [],
            f"case={case}",
        )

        proof = {
            "proof_hash": "proof-a",
            "result_hash": "result-a",
            "result": {
                "applies": True,
                "contract_effect": {
                    "enabled": True,
                    "family": "bending",
                    "updates": {"D": 650},
                },
                "item_effect": {
                    "title_main": "Rebound item",
                    "action_type": "apply_resolved_candidate",
                },
            },
        }
        case = run_case(
            "rebind_applies_and_records_payload",
            item={"title_main": "Original"},
            contract={"enabled": False, "updates": {}},
            debug={"intent": "bending"},
            state={"D": 500},
            enabled=False,
            proof=proof,
        )
        event_names = [event["event"] for event in case["events"]]
        expect(
            "rebind_applies_and_records_payload",
            case["item"]["title_main"] == "Rebound item"
            and case["item"]["button_contract"] == {
                "enabled": True,
                "family": "bending",
                "updates": {"D": 650},
            }
            and case["contract"] == {
                "enabled": True,
                "family": "bending",
                "updates": {"D": 650},
            }
            and case["debug"]["render_stage_intent_contract_rebind_proof_hash"] == "proof-a"
            and case["debug"]["render_stage_intent_contract_rebind_result_hash"] == "result-a"
            and case["debug"]["render_stage_intent_contract_rebind_trace_wired"] is True
            and case["debug"]["render_stage_intent_contract_rebind_product_driving"] is False
            and case["debug"]["render_stage_intent_contract_rebind_cutover_applied"] is True
            and case["debug"]["render_stage_intent_contract_rebind_ready_for_live_cutover"] is True
            and event_names == ["contract_enabled", "build_rebind_result", "record_payload"]
            and case["events"][-1]["button_contract"]["updates"] == {"D": 650}
            and case["events"][-1]["state"] == {"D": 500},
            f"case={case}",
        )

        case = run_case(
            "builder_exception_fallback",
            item={"title_main": "Original"},
            contract={"enabled": False},
            debug={},
            enabled=False,
            proof=RuntimeError("boom"),
        )
        expect(
            "builder_exception_fallback",
            case["item"] == {"title_main": "Original"}
            and case["contract"] == {"enabled": False}
            and case["debug"]["render_stage_intent_contract_rebind_proof"]["trace_error"] == "boom"
            and case["debug"]["render_stage_intent_contract_rebind_trace_wired"] is True
            and "record_payload" not in [event["event"] for event in case["events"]],
            f"case={case}",
        )
    finally:
        inputs_page._design_guide_button_contract_enabled = originals[
            "_design_guide_button_contract_enabled"
        ]
        inputs_page._build_final_visible_render_stage_intent_contract_rebind_result = originals[
            "_build_final_visible_render_stage_intent_contract_rebind_result"
        ]
        inputs_page._record_rendered_design_guide_primary_apply_payload = originals[
            "_record_rendered_design_guide_primary_apply_payload"
        ]

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Render Stage Intent Contract Rebind Verifier",
                "",
                f"Status: {payload['status']}",
                "",
                "## Cases",
                "",
                *[
                    f"- {case['name']}: {len(case['events'])} events"
                    for case in cases
                ],
                "",
                "## Artifacts",
                "",
                f"- JSON: `{json_path.relative_to(ROOT)}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print("RENDER_STAGE_INTENT_CONTRACT_REBIND_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("RENDER_STAGE_INTENT_CONTRACT_REBIND_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
