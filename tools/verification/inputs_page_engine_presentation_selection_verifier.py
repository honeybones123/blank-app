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
    json_path = ARTIFACT_DIR / f"inputs_page_engine_presentation_selection_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_engine_presentation_selection_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    previous_engine_decision = st.session_state.get("_design_guide_engine_decision")
    original_acceptance_matches = inputs_page._local_cleanup_post_apply_acceptance_matches
    try:
        engine_decision = {
            "presentation": {"headline": "Engine headline", "theme": "engine"},
            "card": {"title": "Engine card"},
        }

        st.session_state["_design_guide_engine_decision"] = dict(engine_decision)
        inputs_page._local_cleanup_post_apply_acceptance_matches = lambda state: False
        (
            decision,
            presentation,
            guidance_debug,
        ) = inputs_page.render_design_guide_engine_presentation_selection(
            guidance_items=[{"guidance_intent": "required_fix"}],
            guidance_debug={},
            guidance_disp_state={"depth_mm": 450},
            terminal_state="needs_action",
            dg_presentation={"headline": "Old headline"},
        )
        cases.append(
            {
                "name": "adopts_engine_presentation",
                "decision": decision,
                "presentation": presentation,
                "debug": guidance_debug,
            }
        )
        if decision != engine_decision:
            failures.append(f"engine_decision_mismatch:{decision}")
        if presentation != engine_decision["presentation"]:
            failures.append(f"engine_presentation_not_adopted:{presentation}")
        if guidance_debug.get("design_guide_engine_decision") != engine_decision:
            failures.append(f"engine_decision_not_debugged:{guidance_debug}")

        st.session_state["_design_guide_engine_decision"] = dict(engine_decision)
        (
            decision,
            presentation,
            guidance_debug,
        ) = inputs_page.render_design_guide_engine_presentation_selection(
            guidance_items=[{"direct_target_band_proof_unresolved": True}],
            guidance_debug={},
            guidance_disp_state={},
            terminal_state="needs_action",
            dg_presentation={"headline": "Existing"},
        )
        cases.append(
            {
                "name": "direct_target_band_proof_keeps_existing_presentation",
                "presentation": presentation,
                "debug": guidance_debug,
            }
        )
        if presentation != {"headline": "Existing"}:
            failures.append(f"direct_target_blocker_presentation_changed:{presentation}")

        st.session_state["_design_guide_engine_decision"] = dict(engine_decision)
        (
            decision,
            presentation,
            guidance_debug,
        ) = inputs_page.render_design_guide_engine_presentation_selection(
            guidance_items=[
                {
                    "family": "bending",
                    "action_type": "apply_resolved_candidate",
                    "candidate_search_evidence": {"search_scope": "design_guide_bending_only_cleanup"},
                }
            ],
            guidance_debug={"overview": {"utils": {"bending": 0.48}}},
            guidance_disp_state={},
            terminal_state="needs_action",
            dg_presentation={"headline": "Low bending repair"},
        )
        cases.append(
            {
                "name": "low_bending_cleanup_keeps_existing_presentation",
                "presentation": presentation,
                "debug": guidance_debug,
            }
        )
        if presentation != {"headline": "Low bending repair"}:
            failures.append(f"low_bending_cleanup_presentation_changed:{presentation}")

        st.session_state["_design_guide_engine_decision"] = dict(engine_decision)
        inputs_page._local_cleanup_post_apply_acceptance_matches = lambda state: True
        (
            decision,
            presentation,
            guidance_debug,
        ) = inputs_page.render_design_guide_engine_presentation_selection(
            guidance_items=[{"guidance_intent": "required_fix"}],
            guidance_debug={},
            guidance_disp_state={"post_apply": True},
            terminal_state="optimal",
            dg_presentation={"headline": "Existing"},
        )
        cases.append(
            {
                "name": "accepted_post_apply_terminal_state_clears_engine_decision",
                "decision": decision,
                "presentation": presentation,
                "session_decision": st.session_state.get("_design_guide_engine_decision"),
                "debug": guidance_debug,
            }
        )
        if decision != {}:
            failures.append(f"engine_decision_not_cleared:{decision}")
        if st.session_state.get("_design_guide_engine_decision") != {}:
            failures.append(
                f"engine_decision_session_not_cleared:{st.session_state.get('_design_guide_engine_decision')}"
            )
        if presentation != {"headline": "Existing"}:
            failures.append(f"cleared_engine_presentation_changed:{presentation}")
        if "design_guide_engine_decision" in guidance_debug:
            failures.append(f"cleared_engine_decision_debugged_unexpectedly:{guidance_debug}")
    finally:
        inputs_page._local_cleanup_post_apply_acceptance_matches = original_acceptance_matches
        st.session_state.pop("_design_guide_engine_decision", None)
        if isinstance(previous_engine_decision, dict):
            st.session_state["_design_guide_engine_decision"] = previous_engine_decision

    payload_out = {
        "verifier": "inputs_page_engine_presentation_selection_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Engine Presentation Selection Verifier",
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
