"""Verify application-owned shear truth gating, including session overlays."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CASES = (
    {
        "name": "unresolved_failing_blocks",
        "state": {"final_shear_truth_resolved": False},
        "session": {},
        "overview": {"any_fail": True, "all_key_pass": False},
        "classification": None,
    },
    {
        "name": "incomplete_resolved_claim_normalizes_unresolved",
        "state": {"final_shear_truth_resolved": True},
        "session": {},
        "overview": {"any_fail": True, "all_key_pass": False},
        "classification": "failing",
    },
    {
        "name": "all_key_pass_does_not_block",
        "state": {"final_shear_truth_resolved": False},
        "session": {},
        "overview": {"any_fail": False, "all_key_pass": True},
        "classification": None,
    },
    {
        "name": "session_unresolved_overrides_state",
        "state": {"final_shear_truth_resolved": True},
        "session": {
            "final_shear_truth_resolved": False,
            "final_shear_truth_failure_reason": "session_truth_missing",
        },
        "overview": {"any_fail": False, "all_key_pass": False},
        "classification": None,
    },
    {
        "name": "explicit_failing_classification_blocks",
        "state": {
            "final_shear_truth_resolved": False,
            "final_shear_truth_failure_reason": "",
        },
        "session": {},
        "overview": {"any_fail": False, "all_key_pass": True},
        "classification": "failing",
    },
)


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.shear_truth_policy import (
            combined_underdesign_shear_truth_gate,
        )
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    original_st = bridge.st
    rows = []
    try:
        for case in CASES:
            bridge.st = SimpleNamespace(
                session_state=copy.deepcopy(case["session"])
            )
            compatibility = (
                bridge._combined_underdesign_shear_strengthening_truth_gate_payload(
                    copy.deepcopy(case["state"]),
                    overview=copy.deepcopy(case["overview"]),
                    efficiency_classification=case["classification"],
                )
            )
            application = combined_underdesign_shear_truth_gate(
                copy.deepcopy(case["state"]),
                overview=copy.deepcopy(case["overview"]),
                session_state=copy.deepcopy(case["session"]),
                efficiency_classification=case["classification"],
            )
            rows.append(
                {
                    "case": case["name"],
                    "exact_payload_match": compatibility == application,
                    "compatibility": compatibility,
                    "application": application,
                }
            )
    finally:
        bridge.st = original_st

    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "five_state_and_session_cases_match_exactly": all(
            row["exact_payload_match"] for row in rows
        ),
        "bridge_gate_removed_from_shear_runtime": (
            "_combined_underdesign_shear_strengthening_truth_gate_payload"
            not in runtime_fields
        ),
        "application_owner_imports_no_bridge": (
            "inputs_page_app_contract_bridge"
            not in (
                ROOT / "inputs_application" / "shear_truth_policy.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_shear_truth_gate_application_owner.v1",
        "checks": checks,
        "cases": rows,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
