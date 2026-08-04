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
    json_path = ARTIFACT_DIR / f"inputs_page_debug_bundle_publication_payload_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_debug_bundle_publication_payload_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "st": inputs_page.st,
        "_recommendation_cache_fingerprint": inputs_page._recommendation_cache_fingerprint,
        "_guidance_state_snapshot": inputs_page._guidance_state_snapshot,
        "_auto_design_governing_fingerprint": inputs_page._auto_design_governing_fingerprint,
        "_resolve_design_actions_from_state": inputs_page._resolve_design_actions_from_state,
        "_proposed_change_lines_for_guidance_item": inputs_page._proposed_change_lines_for_guidance_item,
        "_resolve_final_design_guide_why_body": inputs_page._resolve_final_design_guide_why_body,
        "_design_guide_candidate_family": inputs_page._design_guide_candidate_family,
        "_design_guide_step_history_debug_summary": inputs_page._design_guide_step_history_debug_summary,
    }
    failures: list[str] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    try:
        session_state = {
            inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY: {
                "design_guide_render_eligibility_trace": {"kept": True},
                "discarded": True,
            },
            "actions_source": "manual",
            "inputs_actions_source": "inputs",
            "actions_mode": "uls",
            "uls_Mstar": 111,
            "uls_Vstar": 222,
            "uls_Nstar": 333,
            inputs_page.DESIGN_GUIDE_REFERENCE_B_KEY: 350,
            inputs_page.DESIGN_GUIDE_SESSION_ANCHOR_D_KEY: 600,
            inputs_page.DESIGN_GUIDE_LAST_USER_GEOM_KEY: {"D": 500},
            inputs_page.DESIGN_GUIDE_LAST_AUTO_GEOM_KEY: {"D": 550},
        }
        inputs_page.st = _FakeStreamlit(session_state)
        inputs_page._recommendation_cache_fingerprint = lambda payload: f"fp:{payload.get('D')}"
        inputs_page._guidance_state_snapshot = lambda state: dict(state or {})
        inputs_page._auto_design_governing_fingerprint = lambda state: "auto-fp"
        inputs_page._resolve_design_actions_from_state = lambda state: {"signature": ("sig-a", "sig-b")}
        inputs_page._proposed_change_lines_for_guidance_item = lambda item, state: ["change-line"]
        inputs_page._resolve_final_design_guide_why_body = lambda why, reasoning: f"why:{why}:{reasoning}"
        inputs_page._design_guide_candidate_family = lambda item: item.get("family", "unknown")
        inputs_page._design_guide_step_history_debug_summary = lambda: {"step_history_key": "step-history"}

        payload = inputs_page.render_design_guide_debug_bundle_publication_payload(
            current_state={"D": 500},
            guidance_disp_state={"D": 550},
            guidance_debug={
                "one_click_solver_expanded": True,
                "overview": {"statuses": {"bending": "PASS"}},
                "design_brain_result": {"validation": {"ok": True}},
                "guidance_branch": "branch",
                "selected_action_type": "apply_resolved_candidate",
                "selected_title": "Selected",
                "post_click_exact_blockers_by_family": {"shear": {"family": "shear"}},
                "rank_trace": [{"rank": 1}],
                "design_guide_presentation": {"headline": "Headline"},
            },
            guidance_compute_ms=12.5,
            guidance_cache_hit=True,
            overview={
                "utils": {"bending": 0.9},
                "governing_action": "bending",
                "design_guide_shear_truth_source": "overview",
                "stage3_shear_truth_debug": {"stage": 3},
                "stage3_remaining_issue_class": "none",
            },
            resolved_guidance_actions={"Mu": 1, "Vu": 2, "Nu": 3},
            live_design_summary={"summary": True},
            mode_mt={"mode": "mt"},
            bottom_bt={"bottom": "bt"},
            recommendation_result={"winner_id": "win-1"},
            guidance_dedupe_meta={"dedupe_key": "dedupe"},
            guidance_items_summary=[{"title": "summary"}],
            displayed_primary_source="source",
            displayed_primary_action_type="action",
            displayed_primary_update_families=["bending"],
            displayed_primary_governing_action="governing",
            final_primary_contract_for_bundle={"family": "bending", "updates": {"D": 550}, "preview_pass": True},
            displayed_primary_truth={
                "displayed_util": 0.9,
                "displayed_status": "PASS",
                "display_truth_source": "truth",
                "target_low": 0.85,
                "target_high": 0.95,
                "displayed_within_target_band": True,
            },
            final_primary_payload_for_bundle={"payload": True},
            engine_card_debug={"title": "card", "intent": "intent", "displayed_util": 0.9},
            engine_outcome_debug={"preview_util": 0.91, "lands_in_target_band": True},
            final_primary_contract_enabled=True,
            engine_decision_debug={
                "family_utils": {"bending": 0.9},
                "local_cleanup_search_ran": True,
                "safe_local_cleanup_count": 2,
            },
            engine_trace_debug={"decision_reason": "reason", "suppressed_count": 1, "suppressed_reasons": ["x"]},
            engine_candidate_search_evidence={
                "exact_blockers_by_family": {"bending": {"family": "bending"}},
                "candidate": True,
            },
            bundle_exact_blockers={"bending": {"family": "bending"}},
            displayed_primary_candidate_search_evidence={},
            optimisation_normalized_link_state={"lig_d": 10},
            banner_generic_only=True,
            fast_focus_section="model",
            primary_item={
                "title_main": "Primary",
                "family": "bending",
                "action_type": "apply_resolved_candidate",
                "guidance_why": "why",
                "reasoning": "reasoning",
            },
            primary_payload={"resolved_candidate_updates": {"D": 550}, "resolved_candidate_label": "label"},
            primary_card_is_resolved_one_click=True,
            primary_card_expected_util_value=0.9,
            primary_card_expected_util_rendered="0.90",
            last_apply_route={
                "apply_used_resolved_candidate_payload": True,
                "apply_fallback_reason": "none",
                "expected_post_util": 0.9,
                "post_apply_resolved_candidate_attempted": True,
                "resolved_candidate_label": "resolved",
            },
            trial_geom={
                "correction_candidate_considered": True,
                "reference_D": 500,
                "current_D": 550,
            },
            post_apply_live_worst=0.9,
            post_apply_live_in_target_band=True,
            post_apply_display_truth={"truth": True},
            post_apply_matches=True,
        )
    finally:
        _restore()

    session_payload = session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY)
    if payload != session_payload:
        failures.append("payload_not_written_to_session")
    if payload.get("design_guide_render_eligibility_trace") != {"kept": True}:
        failures.append(f"eligibility_trace_not_preserved:{payload.get('design_guide_render_eligibility_trace')}")
    if "discarded" in payload:
        failures.append("old_bundle_key_leaked")
    if payload.get("guidance_compute_ms") != 12.5 or payload.get("guidance_cache_hit") is not True:
        failures.append(f"basic_compute_fields_mismatch:{payload}")
    if payload.get("manual_resolver_lock_check", {}).get("resolved_Mu") != 1:
        failures.append(f"manual_resolver_lock_missing:{payload.get('manual_resolver_lock_check')}")
    if payload.get("session_actions", {}).get("actions_source") != "manual":
        failures.append(f"session_actions_missing:{payload.get('session_actions')}")
    if payload.get("fingerprints", {}).get("guidance_fingerprint") != "fp:500":
        failures.append(f"fingerprint_mismatch:{payload.get('fingerprints')}")
    if payload.get("fingerprints", {}).get("auto_design_action_signature") != ("sig-a", "sig-b"):
        failures.append(f"signature_mismatch:{payload.get('fingerprints')}")
    if payload.get("recommendation_change_lines") != ["change-line"]:
        failures.append(f"change_lines_mismatch:{payload.get('recommendation_change_lines')}")
    if payload.get("recommendation_why_text") != "why:why:reasoning":
        failures.append(f"why_text_mismatch:{payload.get('recommendation_why_text')}")
    if payload.get("current_candidate_family") != "bending":
        failures.append(f"candidate_family_mismatch:{payload.get('current_candidate_family')}")
    if payload.get("cleanup_evidence_by_family") != {"bending": {"family": "bending"}}:
        failures.append(f"cleanup_evidence_fallback_mismatch:{payload.get('cleanup_evidence_by_family')}")
    if payload.get("post_click_exact_blockers_by_family") != {"shear": {"family": "shear"}}:
        failures.append(f"post_click_exact_mismatch:{payload.get('post_click_exact_blockers_by_family')}")
    if payload.get("design_guide_blue_banner_generic_text_only") is not True:
        failures.append("blue_banner_flag_mismatch")
    if payload.get("step_history_key") != "step-history":
        failures.append("step_history_summary_missing")
    if payload.get("dedupe_key") != "dedupe":
        failures.append("dedupe_meta_missing")
    if payload.get("recommendation_result_winner_id") != "win-1":
        failures.append(f"winner_id_mismatch:{payload.get('recommendation_result_winner_id')}")

    verifier_payload = {
        "verifier": "inputs_page_debug_bundle_publication_payload_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "sample_keys": sorted(payload.keys())[:40],
        "key_count": len(payload),
    }
    json_path.write_text(json.dumps(verifier_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Debug Bundle Publication Payload Verifier",
                "",
                f"Status: `{verifier_payload['status']}`",
                "",
                f"Key count: `{verifier_payload['key_count']}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(verifier_payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
