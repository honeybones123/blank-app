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
    import streamlit as st

    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_debug_bundle_engine_update_stamping_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_debug_bundle_engine_update_stamping_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    debug_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    previous_debug_bundle = st.session_state.get(debug_key)
    try:
        stage_labels: list[str] = []
        st.session_state[debug_key] = {
            "displayed_primary_button_contract": {
                "enabled": False,
                "updates": {"depth_mm": 999},
                "preview_pass": False,
                "blocking_reason": "disabled display contract",
            }
        }
        guidance_debug = {
            "primary_button_contract": {
                "enabled": True,
                "updates": {"depth_mm": 475},
                "preview_pass": True,
                "blocking_reason": None,
            },
            "candidate_search_evidence": {"existing": True},
            "family_utils": {"bending": 1.14},
            "materially_overprovided_families": ["bending"],
            "post_click_family_utils": {"bending": 0.94},
            "post_click_materially_overprovided_families": [],
            "post_click_unresolved_overprovided_families": [],
            "local_cleanup_search_ran": False,
            "local_cleanup_search_exhaustive": True,
            "safe_local_cleanup_count": 3,
            "executable_safe_cleanup_count": 2,
            "advisory_cleanup_count": 1,
            "primary_guidance_intent": "required_fix",
            "primary_display_truth": {"displayed_status": "PASS"},
        }
        stamped_debug = inputs_page.render_design_guide_debug_bundle_engine_update_stamping(
            dg_engine_decision={
                "family_utils": {"shear": 0.88},
                "materially_overprovided_families": ["shear"],
                "safe_local_cleanup_count": 5,
                "local_cleanup_candidates": [{"id": "safe-1"}],
                "local_cleanup_candidate_inventory": [{"id": "inv-1"}],
                "terminal_state_reason": "engine terminal reason",
                "terminal_state_blocked_by_local_cleanup": True,
            },
            engine_card={
                "title": "Engine card",
                "intent": "required_fix",
                "displayed_util": 0.91,
                "display_truth_source": "candidate_preview",
                "target_low": 0.85,
                "target_high": 1.0,
                "local_cleanup_search_ran": True,
                "local_cleanup_search_exhaustive": False,
            },
            engine_outcome={
                "preview_util": 0.91,
                "current_util": 1.23,
                "lands_in_target_band": True,
                "allowed_blocker": None,
            },
            engine_trace={
                "decision_reason": "controller selected card",
                "suppressed_count": 2,
                "suppressed_reasons": ["lower rank", "duplicate"],
            },
            engine_candidate_search_evidence={
                "family": "combined",
                "selected_candidate_updates": {"depth_mm": 500},
                "cleanup_search_ran": True,
            },
            engine_exact_blockers_for_update={"bending": {"reason": "blocked"}},
            engine_cleanup_evidence_for_update={"bending": {"cleanup": "blocked"}},
            engine_post_click_exact_for_update={"bending": {"post": "exact"}},
            engine_post_click_cleanup_for_update={"bending": {"post": "cleanup"}},
            guidance_debug=guidance_debug,
            guidance_disp_state={"depth_mm": 450},
            stage=stage_labels.append,
        )
        bundle = dict(st.session_state.get(debug_key) or {})
        probes = dict(
            stamped_debug.get(
                "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probes"
            )
            or {}
        )
        probe = dict(probes.get("engine_evidence_rebind_bridge") or {})
        cases.append(
            {
                "name": "fallback_to_primary_contract_and_stamp_bundle",
                "bundle": bundle,
                "probe": probe,
                "stages": list(stage_labels),
            }
        )
        if bundle.get("primary_card_title") != "Engine card":
            failures.append(f"primary_card_title_mismatch:{bundle}")
        if bundle.get("button_contract_updates") != {"depth_mm": 475}:
            failures.append(f"primary_contract_fallback_mismatch:{bundle}")
        if bundle.get("button_contract_enabled") is not False:
            failures.append(f"button_contract_enabled_mismatch:{bundle}")
        if bundle.get("candidate_search_evidence") != {
            "family": "combined",
            "selected_candidate_updates": {"depth_mm": 500},
            "cleanup_search_ran": True,
        }:
            failures.append(f"candidate_search_evidence_mismatch:{bundle}")
        if bundle.get("exact_blockers_by_family") != {"bending": {"reason": "blocked"}}:
            failures.append(f"exact_blockers_mismatch:{bundle}")
        if bundle.get("post_click_cleanup_evidence_by_family") != {"bending": {"post": "cleanup"}}:
            failures.append(f"post_click_cleanup_mismatch:{bundle}")
        if bundle.get("local_cleanup_search_ran") is not True:
            failures.append(f"prefer_true_local_cleanup_search_mismatch:{bundle}")
        if bundle.get("local_cleanup_search_exhaustive") is not True:
            failures.append(f"prefer_true_local_cleanup_exhaustive_mismatch:{bundle}")
        if bundle.get("safe_local_cleanup_count") != 3:
            failures.append(f"first_non_none_safe_count_mismatch:{bundle}")
        if bundle.get("terminal_state_reason") != "engine terminal reason":
            failures.append(f"terminal_state_reason_mismatch:{bundle}")
        if bundle.get("terminal_state_blocked_by_local_cleanup") is not True:
            failures.append(f"terminal_state_blocked_mismatch:{bundle}")
        expected_predicates = {
            "engine_evidence_family_is_combined": True,
            "engine_evidence_updates_present": True,
            "engine_contract_updates_differ": True,
            "updates_not_already_applied": True,
            "cleanup_search_evidence_present": True,
        }
        if probe.get("predicates") != expected_predicates or probe.get("all_predicates_true") is not True:
            failures.append(f"predicate_probe_mismatch:{probe}")
        if "post_plan.after_debug_bundle_engine_update" not in stage_labels:
            failures.append(f"stage_not_called:{stage_labels}")

    finally:
        st.session_state.pop(debug_key, None)
        if isinstance(previous_debug_bundle, dict):
            st.session_state[debug_key] = previous_debug_bundle

    payload_out = {
        "verifier": "inputs_page_debug_bundle_engine_update_stamping_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Debug Bundle Engine Update Stamping Verifier",
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
