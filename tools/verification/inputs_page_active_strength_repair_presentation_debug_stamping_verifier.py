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
    json_path = ARTIFACT_DIR / f"inputs_page_active_strength_repair_presentation_debug_stamping_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_strength_repair_presentation_debug_stamping_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    debug_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    previous_debug_bundle = st.session_state.get(debug_key)
    try:
        st.session_state[debug_key] = {"existing": True}
        active_item = {"title": "Increase depth", "candidate_id": "active-1"}
        active_contract = {
            "enabled": True,
            "updates": {"depth_mm": 475},
            "preview_pass": True,
        }
        evidence = {
            "selected_candidate_id": "active-1",
            "exact_blockers_by_family": {
                "bending": {"reason": "accepted band cleanup blocked"}
            },
            "post_click_exact_blockers_by_family": {
                "bending": {"reason": "accepted band cleanup blocked"}
            },
            "cleanup_evidence_by_family": {
                "bending": {"reason": "accepted band cleanup blocked"}
            },
            "post_click_cleanup_evidence_by_family": {
                "bending": {"reason": "accepted band cleanup blocked"}
            },
        }
        guidance_items = [{"old": True}]
        collapsed_items = [{"old_collapsed": True}]
        guidance_debug = {"overview": {"utils": {"bending": 1.25}}}

        (
            stamped_items,
            presentation,
            stamped_debug,
        ) = inputs_page.render_design_guide_active_strength_repair_presentation_debug_stamping(
            guidance_items=guidance_items,
            collapsed_guidance_items=collapsed_items,
            dg_presentation={"existing_presentation": True},
            active_repair_item=active_item,
            active_repair_contract=active_contract,
            active_repair_family="bending",
            active_repair_title="Increase depth",
            active_repair_evidence=evidence,
            active_repair_expected_util=0.93,
            guidance_debug=guidance_debug,
        )
        session_bundle = dict(st.session_state.get(debug_key) or {})
        cases.append(
            {
                "name": "stamps_visible_presentation_debug_and_session_bundle",
                "items": stamped_items,
                "collapsed": collapsed_items,
                "presentation": presentation,
                "debug": stamped_debug,
                "session_bundle": session_bundle,
            }
        )
        if stamped_items[0] is not active_item:
            failures.append(f"primary_item_not_replaced:{stamped_items}")
        if collapsed_items[0] != active_item or collapsed_items[0] is active_item:
            failures.append(f"collapsed_primary_not_copied:{collapsed_items}")
        expected_presentation = {
            "headline": "Increase depth",
            "guidance_intent": "required_fix",
            "css_bucket": "fail",
            "theme": "fail",
            "show_apply_button": True,
            "use_success_style": False,
            "displayed_util": 0.93,
            "source_candidate_util": 0.93,
            "expected_util": 0.93,
            "display_truth_source": "candidate_preview",
        }
        for key, value in expected_presentation.items():
            if presentation.get(key) != value:
                failures.append(f"presentation_{key}_mismatch:{presentation}")
        if presentation.get("existing_presentation") is not True:
            failures.append(f"presentation_existing_key_lost:{presentation}")
        expected_debug_keys = {
            "selected_action_family": "bending",
            "selected_title": "Increase depth",
            "primary_guidance_intent": "required_fix",
            "primary_button_contract": active_contract,
            "button_contract": active_contract,
            "candidate_search_evidence": evidence,
            "exact_blockers_by_family": evidence["exact_blockers_by_family"],
            "post_click_exact_blockers_by_family": evidence["post_click_exact_blockers_by_family"],
            "cleanup_evidence_by_family": evidence["cleanup_evidence_by_family"],
            "post_click_cleanup_evidence_by_family": evidence["post_click_cleanup_evidence_by_family"],
        }
        for key, value in expected_debug_keys.items():
            if stamped_debug.get(key) != value:
                failures.append(f"debug_{key}_mismatch:{stamped_debug}")
        expected_session_keys = {
            "selected_action_family": "bending",
            "selected_title": "Increase depth",
            "primary_card_title": "Increase depth",
            "primary_guidance_intent": "required_fix",
            "primary_card_intent": "required_fix",
            "primary_button_contract": active_contract,
            "button_contract": active_contract,
            "displayed_primary_button_contract": active_contract,
            "button_contract_enabled": True,
            "button_contract_updates": {"depth_mm": 475},
            "button_contract_preview_pass": True,
            "button_contract_blocking_reason": None,
            "candidate_search_evidence": evidence,
            "source_candidate_util": 0.93,
            "primary_preview_util": 0.93,
        }
        for key, value in expected_session_keys.items():
            if session_bundle.get(key) != value:
                failures.append(f"session_{key}_mismatch:{session_bundle}")
        if session_bundle.get("existing") is not True:
            failures.append(f"session_existing_key_lost:{session_bundle}")

        st.session_state.pop(debug_key, None)
        guidance_items = [{"old": True}]
        guidance_debug = {}
        (
            stamped_items,
            presentation,
            stamped_debug,
        ) = inputs_page.render_design_guide_active_strength_repair_presentation_debug_stamping(
            guidance_items=guidance_items,
            collapsed_guidance_items=None,
            dg_presentation={},
            active_repair_item={"title": "Shear repair"},
            active_repair_contract={},
            active_repair_family="shear",
            active_repair_title="Shear repair",
            active_repair_evidence={},
            active_repair_expected_util=None,
            guidance_debug=guidance_debug,
        )
        cases.append(
            {
                "name": "no_collapsed_no_util_no_session_bundle",
                "items": stamped_items,
                "presentation": presentation,
                "debug": stamped_debug,
                "session_has_bundle": debug_key in st.session_state,
            }
        )
        if any(key in presentation for key in ("displayed_util", "source_candidate_util", "expected_util")):
            failures.append(f"unexpected_util_presentation_keys:{presentation}")
        if debug_key in st.session_state:
            failures.append(f"debug_bundle_created_unexpectedly:{dict(st.session_state.get(debug_key) or {})}")
        if stamped_debug.get("primary_button_contract") != {} or stamped_debug.get("button_contract") != {}:
            failures.append(f"empty_contract_debug_mismatch:{stamped_debug}")
    finally:
        st.session_state.pop(debug_key, None)
        if isinstance(previous_debug_bundle, dict):
            st.session_state[debug_key] = previous_debug_bundle

    payload_out = {
        "verifier": "inputs_page_active_strength_repair_presentation_debug_stamping_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Strength Repair Presentation Debug Stamping Verifier",
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
