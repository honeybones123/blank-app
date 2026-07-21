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
    json_path = ARTIFACT_DIR / f"inputs_page_engine_rebind_outer_probe_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_engine_rebind_outer_probe_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    debug_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    previous_debug_bundle = st.session_state.get(debug_key)
    try:
        engine_decision = {
            "card": {"title": "Engine card"},
            "debug": {"decision_reason": "controller"},
        }
        st.session_state[debug_key] = {"existing": True}
        guidance_debug = {
            "candidate_search_evidence": {"family": "Combined"},
        }
        stamped_debug = inputs_page.render_design_guide_engine_rebind_outer_probe(
            dg_engine_decision=engine_decision,
            guidance_debug=guidance_debug,
        )
        probe = dict(stamped_debug.get("controller_final_visible_rebind_effects_engine_outer_probe") or {})
        session_bundle = dict(st.session_state.get(debug_key) or {})
        session_probe = dict(session_bundle.get("controller_final_visible_rebind_effects_engine_outer_probe") or {})
        cases.append(
            {
                "name": "stamps_probe_and_debug_bundle",
                "debug": stamped_debug,
                "probe": probe,
                "session_bundle": session_bundle,
            }
        )
        expected_probe = {
            "callsite_id": "engine_evidence_rebind_bridge",
            "debug_bundle_exists": True,
            "engine_decision_present": True,
            "engine_card_present": True,
            "engine_trace_present": True,
            "guidance_candidate_search_evidence_present": True,
            "guidance_candidate_search_family": "combined",
            "trace_only": True,
            "product_driving": False,
            "render_driving": False,
            "apply_driving": False,
            "session_driving": False,
        }
        for key, value in expected_probe.items():
            if probe.get(key) != value:
                failures.append(f"probe_{key}_mismatch:{probe}")
        if not probe.get("probe_hash"):
            failures.append(f"probe_hash_missing:{probe}")
        if stamped_debug.get("design_guide_engine_decision") != engine_decision:
            failures.append(f"engine_decision_not_debugged:{stamped_debug}")
        if stamped_debug.get("controller_final_visible_rebind_effects_engine_outer_probe_hash") != probe.get("probe_hash"):
            failures.append(f"debug_probe_hash_mismatch:{stamped_debug}")
        if session_probe != probe:
            failures.append(f"session_probe_mismatch:{session_probe}:{probe}")
        if session_bundle.get("controller_final_visible_rebind_effects_engine_outer_probe_hash") != probe.get("probe_hash"):
            failures.append(f"session_probe_hash_mismatch:{session_bundle}")
        if session_bundle.get("existing") is not True:
            failures.append(f"session_existing_key_lost:{session_bundle}")

        st.session_state.pop(debug_key, None)
        stamped_debug = inputs_page.render_design_guide_engine_rebind_outer_probe(
            dg_engine_decision={},
            guidance_debug={},
        )
        probe = dict(stamped_debug.get("controller_final_visible_rebind_effects_engine_outer_probe") or {})
        cases.append(
            {
                "name": "no_debug_bundle_still_stamps_guidance_debug",
                "debug": stamped_debug,
                "probe": probe,
                "session_has_bundle": debug_key in st.session_state,
            }
        )
        if probe.get("debug_bundle_exists") is not False:
            failures.append(f"absent_bundle_probe_flag_mismatch:{probe}")
        if probe.get("engine_decision_present") is not False:
            failures.append(f"absent_engine_decision_probe_flag_mismatch:{probe}")
        if stamped_debug.get("design_guide_engine_decision") != {}:
            failures.append(f"empty_engine_decision_not_debugged:{stamped_debug}")
        if debug_key in st.session_state:
            failures.append(f"debug_bundle_created_unexpectedly:{dict(st.session_state.get(debug_key) or {})}")
    finally:
        st.session_state.pop(debug_key, None)
        if isinstance(previous_debug_bundle, dict):
            st.session_state[debug_key] = previous_debug_bundle

    payload_out = {
        "verifier": "inputs_page_engine_rebind_outer_probe_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Engine Rebind Outer Probe Verifier",
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
