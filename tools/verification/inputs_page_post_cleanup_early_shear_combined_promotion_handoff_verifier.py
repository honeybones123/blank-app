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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_combined_promotion_handoff_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_combined_promotion_handoff_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_promoter = inputs_page._visible_safe_combined_cleanup_action_from_evidence
    session_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    original_session_value = inputs_page.st.session_state.get(session_key)

    failures: list[str] = []
    cases: list[dict] = []
    promoter_result = None
    promoter_calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def fake_promoter(action, overview, state, *, debug_sink):
        promoter_calls.append(
            {
                "action": dict(action or {}),
                "overview": dict(overview or {}),
                "state": dict(state or {}),
                "debug_sink_same": debug_sink is current_guidance_debug[0],
            }
        )
        return promoter_result

    current_guidance_debug: list[dict] = [{}]

    try:
        inputs_page._visible_safe_combined_cleanup_action_from_evidence = fake_promoter

        no_promotion_action = {"title_main": "Shear only"}
        no_promotion_contract = {
            "enabled": True,
            "updates": {"s_lig": 150},
            "source_candidate_id": "shear-id",
        }
        no_promotion_updates = {"s_lig": 150}
        guidance_debug = {"existing": "yes"}
        current_guidance_debug[0] = guidance_debug
        promoter_result = None
        promoter_calls = []
        result = inputs_page.render_design_guide_post_cleanup_early_shear_combined_promotion_handoff(
            early_shear_cleanup_action=no_promotion_action,
            early_shear_cleanup_overview={"utils": {"shear": 0.7}},
            early_shear_cleanup_state={"D": 500},
            early_shear_cleanup_seed_contract=no_promotion_contract,
            early_shear_cleanup_seed_updates=no_promotion_updates,
            early_shear_cleanup_candidate_id="shear-id",
            early_shear_cleanup_label="Shear only",
            guidance_debug=guidance_debug,
        )
        cases.append({"name": "no_promotion", "result": [result[0], result[1], result[2], result[3], result[4], result[5]]})
        expect("no_promotion", result[0] is no_promotion_action, "action_object_changed")
        expect("no_promotion", result[1] == no_promotion_contract, "contract_changed")
        expect("no_promotion", result[2] == no_promotion_updates, "updates_changed")
        expect("no_promotion", result[3] == "shear-id", "candidate_id_changed")
        expect("no_promotion", result[4] == "Shear only", "label_changed")
        expect("no_promotion", result[5] is guidance_debug, "debug_object_changed")
        expect("no_promotion", len(promoter_calls) == 1, f"promoter_calls={len(promoter_calls)}")
        if promoter_calls:
            expect("no_promotion", promoter_calls[0]["debug_sink_same"], "debug_sink_not_forwarded")

        combined_contract = {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": {"s_lig": 150, "lig_legs": 4},
            "preview_pass": True,
            "expected_util": 0.92,
            "source_candidate_id": "combined-source",
            "candidate_id": "combined-candidate",
        }
        promoter_result = {
            "title_main": "Combined cleanup",
            "button_contract": dict(combined_contract),
            "updates": {"ignored": "contract wins"},
            "source_candidate_id": "action-source",
            "candidate_id": "action-candidate",
        }
        guidance_debug = {"existing": "yes"}
        current_guidance_debug[0] = guidance_debug
        promoter_calls = []
        result = inputs_page.render_design_guide_post_cleanup_early_shear_combined_promotion_handoff(
            early_shear_cleanup_action={"title_main": "Shear only"},
            early_shear_cleanup_overview={"utils": {"shear": 0.7, "bending": 0.72}},
            early_shear_cleanup_state={"D": 500},
            early_shear_cleanup_seed_contract={"enabled": True, "updates": {"s_lig": 150}},
            early_shear_cleanup_seed_updates={"s_lig": 150},
            early_shear_cleanup_candidate_id="shear-id",
            early_shear_cleanup_label="Shear only",
            guidance_debug=guidance_debug,
        )
        (
            action,
            contract,
            updates,
            candidate_id,
            label,
            returned_debug,
        ) = result
        cases.append(
            {
                "name": "promotion",
                "action": action,
                "contract": contract,
                "updates": updates,
                "candidate_id": candidate_id,
                "label": label,
                "debug": dict(returned_debug),
            }
        )
        expect("promotion", action == promoter_result, f"action_not_promoted:{action}")
        expect("promotion", action is not promoter_result, "promoted_action_not_copied")
        expect("promotion", contract == combined_contract, f"contract_not_restamped:{contract}")
        expect("promotion", updates == {"s_lig": 150, "lig_legs": 4}, f"updates_not_from_contract:{updates}")
        expect("promotion", candidate_id == "combined-source", f"candidate_id={candidate_id}")
        expect("promotion", label == "Combined cleanup", f"label={label}")
        expect("promotion", returned_debug is guidance_debug, "debug_object_changed")
        expected_debug = {
            "early_shear_overdesign_promoted_to_combined_cleanup": True,
            "selected_title": "Combined cleanup",
            "selected_action_family": "combined",
            "primary_card_title": "Combined cleanup",
            "primary_card_intent": "efficiency_tightening",
            "primary_guidance_intent": "efficiency_tightening",
            "displayed_primary_button_contract": combined_contract,
            "primary_button_contract": combined_contract,
            "button_contract": combined_contract,
            "button_contract_enabled": True,
            "button_contract_updates": {"s_lig": 150, "lig_legs": 4},
            "button_contract_preview_pass": True,
            "button_contract_blocking_reason": None,
        }
        for key, expected in expected_debug.items():
            expect("promotion", guidance_debug.get(key) == expected, f"debug:{key}={guidance_debug.get(key)}")
        probe = dict(guidance_debug.get("actual_card_render_probe") or {})
        expect("promotion", probe.get("marker") == "early_shear_overdesign_promoted_to_combined_cleanup", "probe_marker_wrong")
        expect("promotion", probe.get("item_title") == "Combined cleanup", "probe_title_wrong")
        expect("promotion", probe.get("render_button_contract_enabled") is True, "probe_contract_enabled_wrong")
        expect("promotion", probe.get("button_contract") == combined_contract, "probe_contract_wrong")
        session_debug = dict(inputs_page.st.session_state.get(session_key) or {})
        expect("promotion", session_debug.get("selected_title") == "Combined cleanup", "session_selected_title_wrong")
        expect("promotion", session_debug.get("button_contract") == combined_contract, "session_contract_wrong")

        promoter_result = {
            "title": "Fallback combined title",
            "updates": {"s_lig": 125},
            "candidate_id": "action-candidate-only",
        }
        guidance_debug = {}
        current_guidance_debug[0] = guidance_debug
        result = inputs_page.render_design_guide_post_cleanup_early_shear_combined_promotion_handoff(
            early_shear_cleanup_action={},
            early_shear_cleanup_overview={},
            early_shear_cleanup_state={},
            early_shear_cleanup_seed_contract={"enabled": True},
            early_shear_cleanup_seed_updates={},
            early_shear_cleanup_candidate_id="fallback-id",
            early_shear_cleanup_label="Fallback label",
            guidance_debug=guidance_debug,
        )
        cases.append({"name": "promotion_fallbacks", "candidate_id": result[3], "label": result[4], "updates": result[2]})
        expect("promotion_fallbacks", result[2] == {"s_lig": 125}, f"updates={result[2]}")
        expect("promotion_fallbacks", result[3] == "action-candidate-only", f"candidate_id={result[3]}")
        expect("promotion_fallbacks", result[4] == "Fallback combined title", f"label={result[4]}")
    finally:
        inputs_page._visible_safe_combined_cleanup_action_from_evidence = original_promoter
        if original_session_value is None:
            inputs_page.st.session_state.pop(session_key, None)
        else:
            inputs_page.st.session_state[session_key] = original_session_value

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_combined_promotion_handoff_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Combined Promotion Handoff Verifier",
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
