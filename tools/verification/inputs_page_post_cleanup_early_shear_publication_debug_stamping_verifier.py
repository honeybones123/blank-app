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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_publication_debug_stamping_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_publication_debug_stamping_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []
    session_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    original_session_value = inputs_page.st.session_state.get(session_key)

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    try:
        inputs_page.st.session_state[session_key] = {
            "local_cleanup_candidate_search_evidence": {"preserved": True},
            "design_brain_result": {"from_session": True},
            "pre_existing": "kept",
        }
        action = {
            "candidate_search_evidence": {
                "keep": "yes",
                "exact_blockers_by_family": {"shear": {}},
                "post_click_exact_blockers_by_family": {"shear": {}},
                "cleanup_evidence_by_family": {"shear": {}},
                "post_click_cleanup_evidence_by_family": {"shear": {}},
            }
        }
        contract = {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": {"s_lig": 150},
            "preview_pass": True,
            "expected_util": 0.91,
            "source_candidate_id": "candidate-1",
            "candidate_id": "candidate-1",
        }
        guidance_debug = {"existing_debug": "kept"}
        returned_action, evidence, returned_debug = (
            inputs_page.render_design_guide_post_cleanup_early_shear_publication_debug_stamping(
                early_shear_cleanup_action=action,
                early_shear_cleanup_seed_contract=contract,
                early_shear_cleanup_label="Tighten shear spacing",
                guidance_debug=guidance_debug,
            )
        )
        cases.append(
            {
                "name": "proof_positive_stamping",
                "evidence": evidence,
                "debug_keys": sorted(returned_debug),
                "session_debug": dict(inputs_page.st.session_state.get(session_key) or {}),
            }
        )
        expect("proof_positive_stamping", returned_action is action, "returned_action_not_same_object")
        expect("proof_positive_stamping", returned_debug is guidance_debug, "returned_debug_not_same_object")
        expect("proof_positive_stamping", action.get("button_contract") == contract, "button_contract_not_stamped")
        expect("proof_positive_stamping", evidence == {"keep": "yes"}, f"stale_evidence_not_removed:{evidence}")
        expect(
            "proof_positive_stamping",
            action.get("candidate_search_evidence") == {"keep": "yes"},
            f"action_evidence_not_clean:{action.get('candidate_search_evidence')}",
        )
        expected_debug = {
            "guidance_branch": "early_shear_overdesign_safe_cleanup_action",
            "selected_title": "Tighten shear spacing",
            "selected_action_type": "apply_resolved_candidate",
            "selected_action_family": "shear",
            "primary_card_title": "Tighten shear spacing",
            "primary_card_intent": "efficiency_tightening",
            "primary_guidance_intent": "efficiency_tightening",
            "displayed_primary_button_contract": contract,
            "primary_button_contract": contract,
            "button_contract": contract,
            "button_contract_enabled": True,
            "button_contract_updates": {"s_lig": 150},
            "button_contract_preview_pass": True,
            "candidate_search_evidence": {"keep": "yes"},
            "design_guide_terminal_state": None,
            "design_guide_terminal_positive": False,
            "design_guide_has_actionable_recommendation": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "early_shear_overdesign_direct_action_shell_deleted": True,
            "early_shear_overdesign_direct_action_shell_deleted_reason": (
                "FinalDesignGuidePublication render panel owns live card and CTA"
            ),
        }
        for key, expected in expected_debug.items():
            expect(
                "proof_positive_stamping",
                guidance_debug.get(key) == expected,
                f"debug:{key}:expected={expected}:actual={guidance_debug.get(key)}",
            )
        probe = dict(guidance_debug.get("actual_card_render_probe") or {})
        expect("proof_positive_stamping", probe.get("item_title") == "Tighten shear spacing", "probe_title_wrong")
        expect(
            "proof_positive_stamping",
            probe.get("render_button_contract_enabled") is False,
            "probe_render_button_contract_enabled_changed",
        )
        expect(
            "proof_positive_stamping",
            guidance_debug.get("local_cleanup_candidate_search_evidence") == {"preserved": True},
            "session_candidate_search_evidence_not_rehydrated",
        )
        expect(
            "proof_positive_stamping",
            guidance_debug.get("design_brain_result") == {"from_session": True},
            "session_design_brain_result_not_rehydrated",
        )
        session_debug = dict(inputs_page.st.session_state.get(session_key) or {})
        expect("proof_positive_stamping", session_debug.get("pre_existing") == "kept", "session_pre_existing_lost")
        expect(
            "proof_positive_stamping",
            session_debug.get("button_contract") == contract,
            "session_button_contract_not_updated",
        )

        inputs_page.st.session_state.pop(session_key, None)
        action_without_existing_session = {"candidate_search_evidence": {}}
        guidance_debug_without_existing_session: dict = {}
        _, evidence_without_existing_session, debug_without_existing_session = (
            inputs_page.render_design_guide_post_cleanup_early_shear_publication_debug_stamping(
                early_shear_cleanup_action=action_without_existing_session,
                early_shear_cleanup_seed_contract=contract,
                early_shear_cleanup_label="Fallback label",
                guidance_debug=guidance_debug_without_existing_session,
            )
        )
        cases.append(
            {
                "name": "creates_session_bundle",
                "evidence": evidence_without_existing_session,
                "debug_keys": sorted(debug_without_existing_session),
            }
        )
        expect(
            "creates_session_bundle",
            isinstance(inputs_page.st.session_state.get(session_key), dict),
            "session_bundle_not_created",
        )
        expect(
            "creates_session_bundle",
            inputs_page.st.session_state[session_key].get("selected_title") == "Fallback label",
            "session_bundle_selected_title_wrong",
        )
    finally:
        if original_session_value is None:
            inputs_page.st.session_state.pop(session_key, None)
        else:
            inputs_page.st.session_state[session_key] = original_session_value

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_publication_debug_stamping_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Publication Debug Stamping Verifier",
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
