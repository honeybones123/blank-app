"""Focused regression for blocked failed-preview Design Guide rendering.

The browser ladder owns full end-to-end coverage. This fast check locks the
specific escape where a BLOCKED publication could still render as a NEXT card
with an advisory failed-preview button contract.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.runners.real_user_design_guide_ladder import (
    _check_card_sanity_before,
)


def _blocked_failed_preview_state() -> dict[str, Any]:
    return {
        "final_publication_verifier_payload": {
            "outcome_state": "BLOCKED",
            "status": "BLOCKED",
            "display": {
                "badge": "BLOCKED",
                "status": "BLOCKED",
                "display_state": "BLOCKED",
            },
            "cta": {
                "enabled": False,
                "actionable": False,
                "disabled_reason": "candidate_preview_has_fail_status",
            },
        },
        "guidance_compute_probe": {
            "candidate_search_evidence": {
                "candidate_search_exhaustive": True,
                "repair_search_ran": True,
                "repair_search_exhaustive": True,
                "safe_executor_backed_candidates_count": 0,
                "safe_candidate_count": 0,
                "attempted_updates": {"D": "increase section depth trial"},
                "failed_check_name": "bending capacity repair catalogue",
                "failed_check_status": "FAIL",
                "active_under_capacity_blocker_reason": (
                    "Bending repair is blocked by reinforcement and detailing limits."
                ),
                "exact_blockers_by_family": {
                    "bending": {
                        "reason": "Bending repair is blocked by reinforcement and detailing limits.",
                        "attempted_updates": {"D": "increase section depth trial"},
                        "failed_check_name": "bending capacity repair catalogue",
                        "failed_check_status": "FAIL",
                    }
                },
            },
            "primary_button_contract": {
                "actionable": False,
                "action_type": "apply_resolved_candidate",
                "updates": {"D": 450.0},
                "preview_pass": False,
                "blocking_reason": "candidate_preview_has_fail_status",
            }
        },
    }


def _raw_failed_preview_state_without_blocker() -> dict[str, Any]:
    return {
        "guidance_compute_probe": {
            "candidate_search_evidence": {
                "candidate_search_exhaustive": True,
                "safe_executor_backed_candidates_count": 0,
                "target_band_candidate_count": 0,
            },
            "primary_button_contract": {
                "actionable": False,
                "action_type": "apply_resolved_candidate",
                "updates": {"D": 450.0},
                "preview_pass": False,
                "blocking_reason": "candidate_preview_has_fail_status",
            },
        },
    }


def main() -> int:
    bad_snapshot = {
        "design_guide_visible_text": (
            "NEXT\n"
            "Bending capacity is low\n"
            "Recommendation is advisory, not directly executable\n"
            "Button contract: candidate_preview_has_fail_status. Preview did not pass."
        ),
        "visible_card_count": 1,
        "visible_card_badges": ["NEXT"],
        "one_click_button_enabled": False,
        "one_click_button_enabled_count": 0,
    }
    good_snapshot = {
        "design_guide_visible_text": (
            "BLOCKED\n"
            "Bending capacity is low\n"
            "No validated one-click update is available for this state; "
            "the preview still fails a required check.\n"
            "Family-owned blocker proof: bending family; repair search exhausted; "
            "safe executable candidates: 0; attempted moves: D, db_bot_1"
        ),
        "body_text": (
            "BLOCKED\n"
            "Bending capacity is low\n"
            "No validated one-click update is available for this state; "
            "the preview still fails a required check.\n"
            "Family-owned blocker proof: bending family; repair search exhausted; "
            "safe executable candidates: 0; attempted moves: D, db_bot_1"
        ),
        "visible_card_count": 1,
        "visible_card_badges": ["BLOCKED"],
        "one_click_button_enabled": False,
        "one_click_button_enabled_count": 0,
    }
    duplicate_blocked_snapshot = dict(good_snapshot)
    duplicate_blocked_snapshot["body_text"] = (
        "BLOCKED\n"
        "Bending capacity is low\n"
        "No validated one-click update is available for this state; "
        "the preview still fails a required check.\n"
        "Family-owned blocker proof: bending family; repair search exhausted; "
        "safe executable candidates: 0; attempted moves: D, db_bot_1\n"
        "No one-click update is available for this state\n"
        "No validated one-click update is available for this state; "
        "the preview still fails a required check."
    )
    proofless_blocked_snapshot = dict(good_snapshot)
    proofless_blocked_snapshot["design_guide_visible_text"] = (
        "BLOCKED\n"
        "Bending capacity is low\n"
        "No validated one-click update is available for this state; "
        "the preview still fails a required check."
    )
    proofless_blocked_snapshot["body_text"] = proofless_blocked_snapshot["design_guide_visible_text"]
    state = _blocked_failed_preview_state()

    bad_failures = _check_card_sanity_before(bad_snapshot, state, {})
    good_failures = _check_card_sanity_before(good_snapshot, state, {})
    duplicate_blocked_failures = _check_card_sanity_before(duplicate_blocked_snapshot, state, {})
    proofless_blocked_failures = _check_card_sanity_before(proofless_blocked_snapshot, state, {})
    raw_bad_failure_sets: list[list[str]] = []
    for title in (
        "Bending capacity is low",
        "Shear capacity is low",
        "Bending and shear capacity are low",
    ):
        raw_bad_snapshot = dict(bad_snapshot)
        raw_bad_snapshot["design_guide_visible_text"] = (
            f"NEXT\n{title} (preview utilisation = 7.96)\n"
            "Active capacity is failing; this one-click repair is executor-backed "
            "and keeps all required checks acceptable.\n"
            "Recommendation is advisory, not directly executable\n"
            "Button contract: candidate_preview_has_fail_status. Preview did not pass."
        )
        raw_bad_failure_sets.append(
            _check_card_sanity_before(
                raw_bad_snapshot,
                _raw_failed_preview_state_without_blocker(),
                {},
            )
        )
    expected_bad = {
        "blocked_publication_visible_badge_mismatch:NEXT",
        "blocked_publication_visible_as_advisory_failed_preview",
        "blocked_publication_leaks_failed_preview_contract_reason",
        "active_under_capacity_failed_preview_visible_badge_not_blocked:NEXT",
        "active_under_capacity_failed_preview_visible_as_advisory_contract",
        "active_under_capacity_failed_preview_contract_reason_visible",
    }
    missing = sorted(expected_bad.difference(bad_failures))
    if missing:
        print(
            "design_guide_blocked_failed_preview_visible_contract: FAIL "
            f"missing_bad_failures={missing} actual={bad_failures}",
            file=sys.stderr,
        )
        return 1
    expected_raw_bad = {
        "active_under_capacity_failed_preview_visible_badge_not_blocked:NEXT",
        "active_under_capacity_failed_preview_visible_as_advisory_contract",
        "active_under_capacity_failed_preview_contract_reason_visible",
        "active_under_capacity_failed_preview_without_real_engineering_blocker",
    }
    for index, raw_bad_failures in enumerate(raw_bad_failure_sets):
        raw_missing = sorted(expected_raw_bad.difference(raw_bad_failures))
        if raw_missing:
            print(
                "design_guide_blocked_failed_preview_visible_contract: FAIL "
                f"variant={index} missing_raw_bad_failures={raw_missing} actual={raw_bad_failures}",
                file=sys.stderr,
            )
            return 1
    if good_failures:
        print(
            "design_guide_blocked_failed_preview_visible_contract: FAIL "
            f"good_snapshot_failures={good_failures}",
            file=sys.stderr,
        )
        return 1
    if "blocked_publication_duplicate_visible_blocked_explanation:2" not in duplicate_blocked_failures:
        print(
            "design_guide_blocked_failed_preview_visible_contract: FAIL "
            f"duplicate_blocked_failures={duplicate_blocked_failures}",
            file=sys.stderr,
        )
        return 1
    proofless_required = {
        "blocked_publication_failed_preview_proof_not_visible",
        "blocked_publication_failed_preview_exhaustion_not_visible",
    }
    proofless_missing = sorted(proofless_required.difference(proofless_blocked_failures))
    if proofless_missing:
        print(
            "design_guide_blocked_failed_preview_visible_contract: FAIL "
            f"proofless_missing={proofless_missing} actual={proofless_blocked_failures}",
            file=sys.stderr,
        )
        return 1
    print("design_guide_blocked_failed_preview_visible_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
