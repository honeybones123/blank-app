from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import (
    build_inputs_candidate_search_reuse_disabled_decision,
    build_inputs_candidate_search_reuse_stale_apply_decision,
)


def _old_stale(expected, current):
    expected_text = str(expected or "")
    current_text = str(current or "")
    if current_text and expected_text != current_text and expected_text:
        return "stale_apply_payload_or_state_fingerprint_mismatch"
    return None


def _old_disabled(
    runtime_fp,
    *,
    debug_enabled=False,
    verbose=None,
    apply_in_flight=False,
    cleanup_enabled=False,
    cleanup_fp=None,
    stale_reason=None,
):
    if not runtime_fp:
        return "missing_runtime_fingerprint"
    if bool(debug_enabled) or bool(verbose):
        return "debug_mode_enabled"
    if bool(apply_in_flight):
        return "post_click_apply_in_flight"
    if bool(cleanup_enabled):
        return "post_click_cleanup_acceptance_enabled"
    if cleanup_fp:
        return "post_click_cleanup_acceptance_fingerprint_present"
    if stale_reason:
        return stale_reason
    return None


def main() -> int:
    inputs = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    builders = (ROOT / "inputs_page_modules" / "session" / "builders.py").read_text(encoding="utf-8")
    init_text = (ROOT / "inputs_page_modules" / "session" / "__init__.py").read_text(encoding="utf-8")
    scenarios = []
    stale_cases = [("", ""), ("expected", ""), ("expected", "expected"), ("expected", "current")]
    for expected, current in stale_cases:
        decision = build_inputs_candidate_search_reuse_stale_apply_decision(
            expected_state_fingerprint=expected,
            current_state_fingerprint=current,
        )
        scenarios.append(
            {
                "name": f"stale:{expected!r}:{current!r}",
                "match": decision.reason == _old_stale(expected, current),
                "reason": decision.reason,
                "display_hash_present": bool(decision.display_hash),
            }
        )

    disabled_cases = [
        ("missing_runtime", None, {}),
        ("debug", "fp", {"debug_enabled": True}),
        ("verbose", "fp", {"verbose": True}),
        ("apply", "fp", {"apply_in_flight": True}),
        ("cleanup_enabled", "fp", {"cleanup_enabled": True}),
        ("cleanup_fp", "fp", {"cleanup_fp": "accept"}),
        ("stale", "fp", {"stale_reason": "stale_apply_payload_or_state_fingerprint_mismatch"}),
        ("reusable", "fp", {}),
        (
            "precedence",
            None,
            {
                "debug_enabled": True,
                "apply_in_flight": True,
                "stale_reason": "stale_apply_payload_or_state_fingerprint_mismatch",
            },
        ),
    ]
    for name, runtime_fp, values in disabled_cases:
        decision = build_inputs_candidate_search_reuse_disabled_decision(
            guidance_runtime_fingerprint=runtime_fp,
            debug_enabled=values.get("debug_enabled", False),
            guidance_debug_verbose=values.get("verbose"),
            apply_in_flight=values.get("apply_in_flight", False),
            cleanup_acceptance_enabled=values.get("cleanup_enabled", False),
            cleanup_acceptance_fingerprint=values.get("cleanup_fp"),
            stale_apply_reason=values.get("stale_reason"),
        )
        old = _old_disabled(runtime_fp, **values)
        scenarios.append(
            {
                "name": name,
                "match": decision.reason == old and decision.disabled == bool(old),
                "reason": decision.reason,
                "display_hash_present": bool(decision.display_hash),
            }
        )

    failures = []
    if not all(row["match"] and row["display_hash_present"] for row in scenarios):
        failures.append("guard scenario parity failed")
    stale_start = inputs.index("def _design_guide_candidate_search_reuse_stale_apply_reason")
    disabled_start = inputs.index("def _design_guide_candidate_search_reuse_disabled_reason", stale_start)
    get_start = inputs.index("def _design_guide_candidate_search_reuse_get", disabled_start)
    stale_body = inputs[stale_start:disabled_start]
    disabled_body = inputs[disabled_start:get_start]
    if "build_inputs_candidate_search_reuse_stale_apply_decision(" not in stale_body:
        failures.append("stale Apply helper does not delegate to session builder")
    if "build_inputs_candidate_search_reuse_disabled_decision(" not in disabled_body:
        failures.append("disabled-reason helper does not delegate to session builder")
    banned = [
        'return "missing_runtime_fingerprint"',
        'return "debug_mode_enabled"',
        'return "post_click_apply_in_flight"',
        'return "post_click_cleanup_acceptance_enabled"',
        'return "post_click_cleanup_acceptance_fingerprint_present"',
        'return "stale_apply_payload_or_state_fingerprint_mismatch"',
    ]
    for snippet in banned:
        if snippet in stale_body or snippet in disabled_body:
            failures.append(f"page-owned candidate-search guard policy remains: {snippet}")
    if "st.session_state" in builders or "import streamlit" in builders or "import inputs_page" in builders:
        failures.append("session builder imports or reads forbidden page/UI state")
    for name in (
        "build_inputs_candidate_search_reuse_stale_apply_decision",
        "build_inputs_candidate_search_reuse_disabled_decision",
    ):
        if name not in init_text:
            failures.append(f"session builder is not exported: {name}")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_SESSION_CANDIDATE_SEARCH_REUSE_GUARD_LOCKED" if not failures else "FAIL"
    payload = {
        "audit": "inputs_session_candidate_search_reuse_guard_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "session_read_write_ownership_moved": False,
        "scenarios": scenarios,
        "failures": failures,
    }
    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_session_candidate_search_reuse_guard_{timestamp}.json"
    report_path = audit_dir / f"inputs_session_candidate_search_reuse_guard_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Session Candidate Search Reuse Guard Cutover",
                "",
                f"Decision: `{decision}`",
                "",
                f"Scenarios checked: `{len(scenarios)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The session module owns pure stale-fingerprint comparison and rebuild-reason precedence.",
                "`inputs_page.py` still owns session reads and current-state fingerprint construction.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
