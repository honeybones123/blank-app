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
    json_path = ARTIFACT_DIR / f"inputs_page_feedback_session_state_persistence_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_feedback_session_state_persistence_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    keys = [
        "design_guide_feedback_status",
        "design_guide_feedback_reason",
        "design_guide_feedback_fail_fingerprint",
        "design_guide_current_fail_fingerprint",
        "design_guide_blocked_feedback_matches_current_state",
        "design_guide_stale_blocked_feedback_cleared",
        "design_guide_stale_blocked_feedback_reason",
    ]
    previous_values = {key: st.session_state.get(key) for key in keys}
    original_warning = inputs_page.st.warning
    original_info = inputs_page.st.info
    messages: list[tuple[str, str]] = []
    try:
        inputs_page.st.warning = lambda message, *args, **kwargs: messages.append(("warning", str(message)))
        inputs_page.st.info = lambda message, *args, **kwargs: messages.append(("info", str(message)))

        inputs_page.render_design_guide_feedback_session_state_persistence(
            guidance_debug={
                "design_guide_feedback_status": "blocked",
                "design_guide_feedback_reason": "candidate rejected by safety gate",
            },
            oc_feedback_status="blocked",
            oc_feedback_reason="candidate rejected by safety gate",
            oc_feedback_fp={"bending": "fail"},
            dg_current_fail_fingerprint={"bending": "fail"},
            blocked_feedback_matches_current_state=True,
            stale_blocked_feedback_cleared=False,
            oc_feedback={"winning_label": "Depth 475"},
        )
        snapshot = {key: st.session_state.get(key) for key in keys}
        cases.append(
            {
                "name": "blocked_feedback_persists_session_and_warns",
                "session": snapshot,
                "messages": list(messages),
            }
        )
        expected_session = {
            "design_guide_feedback_status": "blocked",
            "design_guide_feedback_reason": "candidate rejected by safety gate",
            "design_guide_feedback_fail_fingerprint": {"bending": "fail"},
            "design_guide_current_fail_fingerprint": {"bending": "fail"},
            "design_guide_blocked_feedback_matches_current_state": True,
            "design_guide_stale_blocked_feedback_cleared": False,
            "design_guide_stale_blocked_feedback_reason": None,
        }
        for key, value in expected_session.items():
            if snapshot.get(key) != value:
                failures.append(f"blocked_session_{key}_mismatch:{snapshot}")
        expected_warning = (
            "warning",
            "One-click found a candidate, but it was blocked: candidate rejected by safety gate.",
        )
        if messages != [expected_warning]:
            failures.append(f"blocked_warning_mismatch:{messages}")

        messages.clear()
        inputs_page.render_design_guide_feedback_session_state_persistence(
            guidance_debug={
                "design_guide_feedback_status": "deferred",
                "design_guide_feedback_reason": "review required",
            },
            oc_feedback_status="deferred",
            oc_feedback_reason="review required",
            oc_feedback_fp={},
            dg_current_fail_fingerprint={"shear": "pass"},
            blocked_feedback_matches_current_state=False,
            stale_blocked_feedback_cleared=True,
            oc_feedback={},
        )
        snapshot = {key: st.session_state.get(key) for key in keys}
        cases.append(
            {
                "name": "stale_feedback_persists_without_message",
                "session": snapshot,
                "messages": list(messages),
            }
        )
        if snapshot.get("design_guide_stale_blocked_feedback_reason") != "fail_fingerprint_changed":
            failures.append(f"stale_reason_mismatch:{snapshot}")
        if snapshot.get("design_guide_blocked_feedback_matches_current_state") is not False:
            failures.append(f"stale_matches_flag_mismatch:{snapshot}")
        if messages:
            failures.append(f"unexpected_stale_message:{messages}")

        messages.clear()
        inputs_page.render_design_guide_feedback_session_state_persistence(
            guidance_debug={
                "design_guide_feedback_status": "accepted",
                "design_guide_feedback_reason": "manual review",
            },
            oc_feedback_status="accepted",
            oc_feedback_reason="manual review",
            oc_feedback_fp={},
            dg_current_fail_fingerprint={},
            blocked_feedback_matches_current_state=False,
            stale_blocked_feedback_cleared=False,
            oc_feedback={"winning_label": ""},
        )
        cases.append(
            {
                "name": "non_blocked_feedback_uses_info_without_label",
                "messages": list(messages),
            }
        )
        expected_info = ("info", "No one-click change was applied. Reason: manual review.")
        if messages != [expected_info]:
            failures.append(f"info_message_mismatch:{messages}")
    finally:
        inputs_page.st.warning = original_warning
        inputs_page.st.info = original_info
        for key in keys:
            st.session_state.pop(key, None)
            if previous_values.get(key) is not None:
                st.session_state[key] = previous_values[key]

    payload_out = {
        "verifier": "inputs_page_feedback_session_state_persistence_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Feedback Session State Persistence Verifier",
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
