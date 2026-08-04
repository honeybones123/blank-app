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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_pending_apply_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_pending_apply_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_record = inputs_page._record_rendered_design_guide_primary_apply_payload
    original_pending = inputs_page.st.session_state.get("pending_recommendation")

    failures: list[str] = []
    cases: list[dict] = []
    record_calls: list[dict] = []

    def fake_record(*, item, rec, button_contract, state):
        call = {
            "item": dict(item or {}),
            "rec": dict(rec or {}),
            "button_contract": dict(button_contract or {}),
            "state": dict(state or {}),
        }
        record_calls.append(call)
        return {"payload": "recorded", "call_index": len(record_calls)}

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    try:
        inputs_page._record_rendered_design_guide_primary_apply_payload = fake_record
        inputs_page.st.session_state["pending_recommendation"] = {"old": "value"}

        action = {
            "title_main": "Tighten shear spacing",
            "updates": {"s_lig": 150},
            "action_payload": {"payload_key": "payload_value"},
            "resolved_candidate": {"resolved_key": "resolved_value"},
        }
        contract = {
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": {"s_lig": 150},
        }
        state = {"D": 500, "B": 300}
        rec, payload = inputs_page.render_design_guide_post_cleanup_early_shear_pending_apply_setup(
            early_shear_cleanup_action=action,
            early_shear_cleanup_seed_contract=contract,
            early_shear_cleanup_seed_updates={"s_lig": 150},
            early_shear_cleanup_label="Tighten shear spacing",
            early_shear_cleanup_state=state,
        )
        cases.append(
            {
                "name": "pending_apply_setup",
                "rec": rec,
                "payload": payload,
                "record_calls": list(record_calls),
            }
        )
        expected_rec = {
            "title": "Tighten shear spacing",
            "summary": "Run one-click auto design",
            "updates": {"s_lig": 150},
            "action_type": "apply_resolved_candidate",
            "action_payload": {"payload_key": "payload_value"},
            "resolved_candidate": {"resolved_key": "resolved_value"},
            "_source": "early_shear_overdesign_safe_cleanup_action",
        }
        expect("pending_apply_setup", rec == expected_rec, f"rec={rec}")
        expect(
            "pending_apply_setup",
            inputs_page.st.session_state.get("pending_recommendation") == expected_rec,
            f"session_pending={inputs_page.st.session_state.get('pending_recommendation')}",
        )
        expect("pending_apply_setup", payload == {"payload": "recorded", "call_index": 1}, f"payload={payload}")
        expect("pending_apply_setup", len(record_calls) == 1, f"record_call_count={len(record_calls)}")
        if record_calls:
            call = record_calls[0]
            expect("pending_apply_setup", call["item"] == action, f"record_item={call['item']}")
            expect("pending_apply_setup", call["rec"] == expected_rec, f"record_rec={call['rec']}")
            expect("pending_apply_setup", call["button_contract"] == contract, f"record_contract={call['button_contract']}")
            expect("pending_apply_setup", call["state"] == state, f"record_state={call['state']}")

        action["action_payload"]["payload_key"] = "mutated_after"
        action["resolved_candidate"]["resolved_key"] = "mutated_after"
        contract["updates"]["s_lig"] = 999
        state["D"] = 999
        expect(
            "pending_apply_setup",
            inputs_page.st.session_state.get("pending_recommendation") == expected_rec,
            "session_pending_not_copied",
        )
        expect("pending_apply_setup", record_calls[0]["rec"] == expected_rec, "record_rec_not_copied")
    finally:
        inputs_page._record_rendered_design_guide_primary_apply_payload = original_record
        if original_pending is None:
            inputs_page.st.session_state.pop("pending_recommendation", None)
        else:
            inputs_page.st.session_state["pending_recommendation"] = original_pending

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_pending_apply_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Pending Apply Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
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
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
