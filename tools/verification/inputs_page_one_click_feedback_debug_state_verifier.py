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
    json_path = ARTIFACT_DIR / f"inputs_page_one_click_feedback_debug_state_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_one_click_feedback_debug_state_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    original_feedback_state = inputs_page._one_click_feedback_cta_state
    try:
        feedback_state = {
            "feedback": {"winning_label": "Depth 475"},
            "status": "blocked",
            "reason": "existing feedback blocks one click",
            "feedback_fail_fingerprint": {"bending": "fail"},
            "current_fail_fingerprint": {"bending": "fail"},
            "matches_current_state": True,
            "stale_cleared": False,
        }
        inputs_page._one_click_feedback_cta_state = lambda overview: dict(feedback_state)
        (
            guidance_debug,
            status,
            reason,
            feedback_fp,
            current_fp,
            blocked_matches,
            stale_cleared,
            cta_suppressed,
            oc_feedback,
        ) = inputs_page.render_design_guide_one_click_feedback_debug_state(
            dg_overview={"any_fail": True},
            guidance_debug={"existing": True},
        )
        cases.append(
            {
                "name": "blocked_feedback_stamps_debug_and_returns_state",
                "debug": guidance_debug,
                "status": status,
                "reason": reason,
                "feedback_fp": feedback_fp,
                "current_fp": current_fp,
                "blocked_matches": blocked_matches,
                "stale_cleared": stale_cleared,
                "cta_suppressed": cta_suppressed,
                "feedback": oc_feedback,
            }
        )
        expected_debug = {
            "existing": True,
            "design_guide_feedback_status": "blocked",
            "design_guide_feedback_reason": "existing feedback blocks one click",
            "design_guide_feedback_fail_fingerprint": {"bending": "fail"},
            "design_guide_current_fail_fingerprint": {"bending": "fail"},
            "design_guide_blocked_feedback_matches_current_state": True,
            "design_guide_stale_blocked_feedback_cleared": False,
            "design_guide_stale_blocked_feedback_reason": None,
            "design_guide_one_click_cta_suppressed": True,
            "design_guide_one_click_cta_suppressed_reason": "existing feedback blocks one click",
        }
        for key, value in expected_debug.items():
            if guidance_debug.get(key) != value:
                failures.append(f"blocked_debug_{key}_mismatch:{guidance_debug}")
        if (
            status != "blocked"
            or reason != "existing feedback blocks one click"
            or feedback_fp != {"bending": "fail"}
            or current_fp != {"bending": "fail"}
            or blocked_matches is not True
            or stale_cleared is not False
            or cta_suppressed is not True
            or oc_feedback != {"winning_label": "Depth 475"}
        ):
            failures.append(
                "blocked_return_tuple_mismatch:"
                f"{status}:{reason}:{feedback_fp}:{current_fp}:{blocked_matches}:"
                f"{stale_cleared}:{cta_suppressed}:{oc_feedback}"
            )

        feedback_state = {
            "feedback": {},
            "status": "",
            "reason": "old feedback removed",
            "feedback_fail_fingerprint": {},
            "current_fail_fingerprint": {"shear": "pass"},
            "matches_current_state": False,
            "stale_cleared": True,
        }
        inputs_page._one_click_feedback_cta_state = lambda overview: dict(feedback_state)
        (
            guidance_debug,
            status,
            reason,
            feedback_fp,
            current_fp,
            blocked_matches,
            stale_cleared,
            cta_suppressed,
            oc_feedback,
        ) = inputs_page.render_design_guide_one_click_feedback_debug_state(
            dg_overview={"any_fail": False},
            guidance_debug={},
        )
        cases.append(
            {
                "name": "stale_feedback_cleared_without_cta_suppression",
                "debug": guidance_debug,
                "status": status,
                "reason": reason,
                "feedback_fp": feedback_fp,
                "current_fp": current_fp,
                "blocked_matches": blocked_matches,
                "stale_cleared": stale_cleared,
                "cta_suppressed": cta_suppressed,
                "feedback": oc_feedback,
            }
        )
        if guidance_debug.get("design_guide_feedback_status") is not None:
            failures.append(f"empty_status_not_normalized:{guidance_debug}")
        if guidance_debug.get("design_guide_stale_blocked_feedback_reason") != "fail_fingerprint_changed":
            failures.append(f"stale_reason_missing:{guidance_debug}")
        if guidance_debug.get("design_guide_one_click_cta_suppressed") is not False:
            failures.append(f"cta_suppression_unexpected:{guidance_debug}")
        if guidance_debug.get("design_guide_one_click_cta_suppressed_reason") is not None:
            failures.append(f"cta_suppression_reason_unexpected:{guidance_debug}")
        if stale_cleared is not True or cta_suppressed is not False or oc_feedback != {}:
            failures.append(
                f"stale_return_tuple_mismatch:{stale_cleared}:{cta_suppressed}:{oc_feedback}"
            )
    finally:
        inputs_page._one_click_feedback_cta_state = original_feedback_state

    payload_out = {
        "verifier": "inputs_page_one_click_feedback_debug_state_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page One Click Feedback Debug State Verifier",
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
