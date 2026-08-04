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
        f"inputs_page_post_click_replacement_final_contract_proofs_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_click_replacement_final_contract_proofs_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals = {
        "_stamp_final_publication_post_click_bending_replacement_audit_result_proof": (
            inputs_page._stamp_final_publication_post_click_bending_replacement_audit_result_proof
        ),
        "_stamp_final_publication_post_click_replacement_decision_proof": (
            inputs_page._stamp_final_publication_post_click_replacement_decision_proof
        ),
        "_stamp_final_publication_post_click_final_contract_adapter_proof": (
            inputs_page._stamp_final_publication_post_click_final_contract_adapter_proof
        ),
        "_stamp_final_publication_post_click_final_contract_adapter_result": (
            inputs_page._stamp_final_publication_post_click_final_contract_adapter_result
        ),
    }
    failures: list[str] = []
    cases: list[dict] = []
    events: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def audit_result_proof(**kwargs):
        events.append({"event": "audit_result_proof", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["audit_result_seen"] = True
        return {"audit_proof": "ok"}

    def replacement_decision_proof(**kwargs):
        events.append({"event": "replacement_decision_proof", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["decision_seen"] = True
        return {
            "decision_proof": "ok",
            "visible_action": kwargs.get("visible_action"),
            "replacement_applied": kwargs.get("replacement_applied"),
        }

    def final_contract_adapter_proof(**kwargs):
        events.append({"event": "final_contract_adapter_proof", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["adapter_seen"] = True
        return {
            "adapter_proof": "ok",
            "replacement_decision_proof": dict(kwargs.get("replacement_decision_proof") or {}),
        }

    def final_contract_adapter_result(**kwargs):
        events.append({"event": "final_contract_adapter_result", "kwargs": dict(kwargs)})
        kwargs["guidance_debug"]["adapter_result_seen"] = True

    try:
        inputs_page._stamp_final_publication_post_click_bending_replacement_audit_result_proof = audit_result_proof
        inputs_page._stamp_final_publication_post_click_replacement_decision_proof = replacement_decision_proof
        inputs_page._stamp_final_publication_post_click_final_contract_adapter_proof = final_contract_adapter_proof
        inputs_page._stamp_final_publication_post_click_final_contract_adapter_result = final_contract_adapter_result

        guidance_debug = {"seed": True}
        result = inputs_page.render_design_guide_post_click_replacement_final_contract_proofs(
            guidance_debug=guidance_debug,
            post_click_bending_audit_sources_for_visible=({"source": "visible"}, {"source": "evidence"}),
            post_click_bending_resolution={"title_main": "Bending resolution"},
            post_click_bending_contract={"enabled": False},
            final_visible_item={"title_main": "Visible"},
            final_visible_resolution={"publication_hash": "hash-x"},
            final_contract_for_post_click={"family": "bending"},
            final_family_for_post_click="bending",
            final_expected_util_for_post_click=0.82,
            final_current_bending_util_for_post_click=0.61,
            post_click_unresolved_families_for_visible={"shear", "bending"},
            post_click_below_floor_families_for_visible={"torsion", "shear"},
            same_flow_cleanup_apply_for_visible=True,
            post_click_bending_exact_blocker_on_visible_item=True,
            post_click_bending_low_requires_exact_blocker=False,
            post_click_bending_low_visible_action=True,
            post_click_bending_audit={"audit": True},
            post_click_bending_replacement_applied=True,
            post_click_contract_check_input_proof={"input": "proof"},
        )
        event_names = [event["event"] for event in events]
        decision_event = next(
            event for event in events if event["event"] == "replacement_decision_proof"
        )
        adapter_event = next(
            event for event in events if event["event"] == "final_contract_adapter_proof"
        )
        result_event = next(
            event for event in events if event["event"] == "final_contract_adapter_result"
        )
        case = {
            "name": "proof_call_order_and_payloads",
            "result": result,
            "guidance_debug": dict(guidance_debug),
            "events": events,
        }
        cases.append(case)
        expect(
            "proof_call_order_and_payloads",
            event_names
            == [
                "audit_result_proof",
                "replacement_decision_proof",
                "final_contract_adapter_proof",
                "final_contract_adapter_result",
            ]
            and result
            == (
                {"audit_proof": "ok"},
                {
                    "decision_proof": "ok",
                    "visible_action": True,
                    "replacement_applied": True,
                },
                {
                    "adapter_proof": "ok",
                    "replacement_decision_proof": {
                        "decision_proof": "ok",
                        "visible_action": True,
                        "replacement_applied": True,
                    },
                },
            )
            and decision_event["kwargs"]["unresolved_families"] == ["bending", "shear"]
            and decision_event["kwargs"]["below_floor_families"] == ["shear", "torsion"]
            and decision_event["kwargs"]["final_expected_util"] == 0.82
            and decision_event["kwargs"]["same_flow_cleanup_apply"] is True
            and adapter_event["kwargs"]["input_proof"] == {"input": "proof"}
            and adapter_event["kwargs"]["replacement_decision_proof"]
            == {
                "decision_proof": "ok",
                "visible_action": True,
                "replacement_applied": True,
            }
            and result_event["kwargs"]["adapter_proof"]
            == {
                "adapter_proof": "ok",
                "replacement_decision_proof": {
                    "decision_proof": "ok",
                    "visible_action": True,
                    "replacement_applied": True,
                },
            }
            and guidance_debug.get("audit_result_seen") is True
            and guidance_debug.get("decision_seen") is True
            and guidance_debug.get("adapter_seen") is True
            and guidance_debug.get("adapter_result_seen") is True,
            f"case={case}",
        )
    finally:
        inputs_page._stamp_final_publication_post_click_bending_replacement_audit_result_proof = originals[
            "_stamp_final_publication_post_click_bending_replacement_audit_result_proof"
        ]
        inputs_page._stamp_final_publication_post_click_replacement_decision_proof = originals[
            "_stamp_final_publication_post_click_replacement_decision_proof"
        ]
        inputs_page._stamp_final_publication_post_click_final_contract_adapter_proof = originals[
            "_stamp_final_publication_post_click_final_contract_adapter_proof"
        ]
        inputs_page._stamp_final_publication_post_click_final_contract_adapter_result = originals[
            "_stamp_final_publication_post_click_final_contract_adapter_result"
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
                "# Inputs Page Post Click Replacement Final Contract Proofs Verifier",
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
        print("POST_CLICK_REPLACEMENT_FINAL_CONTRACT_PROOFS_VERIFIER_FAIL")
        for failure in failures:
            print(f"- {failure}")
        print(f"json={json_path}")
        print(f"report={report_path}")
        return 1
    print("POST_CLICK_REPLACEMENT_FINAL_CONTRACT_PROOFS_VERIFIER_PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
