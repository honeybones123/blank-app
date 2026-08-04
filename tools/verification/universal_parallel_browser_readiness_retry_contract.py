"""Deterministic contract for the universal clean serial readiness retry."""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_brain_universal_live_family_lock import (  # noqa: E402
    _parallel_browser_readiness_retry_evidence,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"


def _eligible_row() -> dict:
    return {
        "family_id": "BENDING_FAIL_GOVERNS",
        "passed": False,
        "timed_out": False,
        "returncode": 1,
        "artifact": "parallel-attempt.json",
        "payload_summary": {
            "blocking_failures": [
                {
                    "phase": "D_ui_action_proof",
                    "reason": "all_action_rows_have_visible_enabled_button_and_apply_effect",
                },
                {
                    "phase": "D_ui_action_proof",
                    "reason": "final_design_guide_card_not_ready",
                },
                {
                    "phase": "F_family_lock_gate",
                    "reason": "all_family_phases_pass",
                },
            ],
            "live_audit": {
                "executed": True,
                "status": "FAIL",
                "failed_count": 1,
                "errors": [],
                "rows": [
                    {
                        "scenario_id": "BENDING_FAIL_GOVERNS_FUZZ_10",
                        "failures": ["final_design_guide_card_not_ready"],
                        "browser_recipe_probe": {
                            "requested": "LIVE_FUZZ_BENDING_FAIL_GOVERNS_10",
                            "applied": "LIVE_FUZZ_BENDING_FAIL_GOVERNS_10",
                        },
                        "browser_family_identity_contract": {
                            "passes_contract": True,
                        },
                        "trigger_passed": True,
                        "solver_state_timeout": False,
                        "post_apply_authoritative_settle_proof": {
                            "final_conditions": {
                                "applied_updates_match": True,
                                "applied_updates_published": True,
                                "authoritative_state_advanced": True,
                                "overview_terminal_pass": True,
                                "publication_terminal_pass": True,
                            }
                        },
                        "publication_probe_after": {
                            "outcome_state": "PASS",
                            "cta": {"enabled": False},
                        },
                    }
                ],
            },
        },
    }


def main() -> int:
    cases: dict[str, bool] = {}

    eligible = _eligible_row()
    cases["strict_readiness_only_failure_is_eligible"] = (
        _parallel_browser_readiness_retry_evidence(eligible)["eligible"] is True
    )

    engineering_failure = copy.deepcopy(eligible)
    engineering_failure["payload_summary"]["live_audit"]["rows"][0][
        "post_apply_authoritative_settle_proof"
    ]["final_conditions"]["overview_terminal_pass"] = False
    cases["engineering_failure_is_not_eligible"] = (
        _parallel_browser_readiness_retry_evidence(engineering_failure)["eligible"]
        is False
    )

    recipe_mismatch = copy.deepcopy(eligible)
    recipe_mismatch["payload_summary"]["live_audit"]["rows"][0][
        "browser_recipe_probe"
    ]["applied"] = "FOREIGN_RECIPE"
    cases["recipe_mismatch_is_not_eligible"] = (
        _parallel_browser_readiness_retry_evidence(recipe_mismatch)["eligible"]
        is False
    )

    identity_mismatch = copy.deepcopy(eligible)
    identity_mismatch["payload_summary"]["live_audit"]["rows"][0][
        "browser_family_identity_contract"
    ]["passes_contract"] = False
    cases["family_identity_mismatch_is_not_eligible"] = (
        _parallel_browser_readiness_retry_evidence(identity_mismatch)["eligible"]
        is False
    )

    product_failure = copy.deepcopy(eligible)
    product_failure["payload_summary"]["live_audit"]["rows"][0]["failures"] = [
        "post_apply_outside_target_band_without_engineering_blocker"
    ]
    cases["product_failure_is_not_eligible"] = (
        _parallel_browser_readiness_retry_evidence(product_failure)["eligible"]
        is False
    )

    already_locked = copy.deepcopy(eligible)
    already_locked["passed"] = True
    cases["locked_family_is_not_retried"] = (
        _parallel_browser_readiness_retry_evidence(already_locked)["eligible"]
        is False
    )

    status = "PASS" if all(cases.values()) else "FAIL"
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact = (
        ARTIFACT_DIR
        / f"universal_parallel_browser_readiness_retry_contract_{stamp}.json"
    )
    payload = {
        "schema": "design_brain.universal_parallel_browser_readiness_retry_contract.v1",
        "status": status,
        "generated_at": stamp,
        "checks": cases,
        "artifact": str(artifact),
        "product_behaviour_changed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"universal_parallel_browser_readiness_retry_contract {status}")
    print(f"json={artifact}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
