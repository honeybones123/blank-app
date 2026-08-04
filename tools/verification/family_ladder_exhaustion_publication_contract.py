"""Focused contract for publishing a family-owned exhausted repair ladder."""

from __future__ import annotations

import json
import inspect
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.guidance_compute import (
    _family_ladder_exhaustion_blocker_item,
)
from application.guidance_result_adapter import (
    build_authoritative_design_result_from_guidance_payload,
)
from design_brain.authority import EngineeringInputSnapshot
from design_brain import final_publication


def main() -> int:
    family_id = "SHEAR_FAIL_GOVERNS"
    reason = (
        "No safe one-click repair was found after the SHEAR_FAIL_GOVERNS "
        "family ladder checked 12 executor-backed candidates."
    )
    exact_blocker = {
        "shear": {
            "family": "shear",
            "reason": reason,
            "repair_search_ran": True,
            "repair_search_exhaustive": True,
            "safe_candidate_count": 0,
            "safe_executor_backed_candidates_count": 0,
            "exact_stop_proven": True,
            "family_ladder_exhausted": True,
        }
    }
    family_result = {
        "family_ladder_exhausted": True,
        "selected_family": family_id,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "apply_payload_family_id": family_id,
        "candidate_family_id": family_id,
        "card_family_id": family_id,
        "active_failures": ["shear"],
        "raw_state_flags": {
            "bending_fail": False,
            "shear_fail": True,
        },
        "matched_family_ids": [family_id],
        "rejected_families": {
            "BENDING_FAIL_GOVERNS": "bending_fail is false",
            "COMBINED_BENDING_SHEAR_FAIL": "bending_fail is false",
        },
        "classification_passed": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "safe_candidate_count": 0,
        "safe_executor_backed_candidates_count": 0,
        "family_ladder_attempts": 12,
        "family_ladder_candidate_count": 12,
        "blocking_reason": reason,
        "exact_blockers_by_family": exact_blocker,
        "post_click_exact_blockers_by_family": exact_blocker,
        "legacy_fallback_allowed": False,
        "generic_one_click_solver_skipped": True,
        "generic_target_band_search_skipped": True,
        "generic_publication_fallback_skipped": True,
    }
    item = _family_ladder_exhaustion_blocker_item(
        family_result,
        {
            "statuses": {"bending": "PASS", "shear": "FAIL"},
            "utils": {"bending": 0.72, "shear": 2.47},
        },
        [
            {
                "check_key": "shear",
                "title_main": "Shear capacity is low",
                "status": "FAIL",
                "util": 2.47,
            }
        ],
    )
    button = dict(item.get("button_contract") or {})
    evidence = dict(item.get("candidate_search_evidence") or {})
    stale_shell = dict(item)
    stale_shell["title_main"] = "Design Guide family contract violation"
    stale_shell["title"] = "Design Guide family contract violation"
    stale_shell["summary_line"] = "Publication blocked by family contract."
    publication = final_publication.build_final_design_guide_publication(
        item=stale_shell,
        debug={
            "selected_family_id": "TARGET_BAND_REACHED",
            "published_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
            "card_family_id": "TARGET_BAND_REACHED",
            "matched_family_ids": ["TARGET_BAND_REACHED"],
            "family_match_passed": True,
            "active_failures": [],
        },
        publication_reason="family_ladder_exhaustion_contract",
    )
    authoritative_result = build_authoritative_design_result_from_guidance_payload(
        engineering_snapshot=EngineeringInputSnapshot(),
        guidance_payload={
            "guidance_items": [item],
            "debug_trace": {
                **family_result,
                "candidate_search_evidence": family_result,
                # Reproduce the stale terminal signal that previously replaced
                # a current family-owned exhausted ladder.
                "design_guide_terminal_state": "target_band_reached",
                "overview": {
                    "statuses": {"bending": "PASS", "shear": "FAIL"},
                    "utils": {"bending": 0.72, "shear": 2.47},
                },
            },
        },
    )
    authoritative_publication = dict(
        dict(authoritative_result.final_publication or {}).get(
            "final_design_guide_publication"
        )
        or {}
    )
    checks = {
        "blocked_outcome": item.get("outcome_state") == "BLOCKED",
        "family_identity_preserved": all(
            item.get(key) == family_id
            for key in (
                "selected_family_id",
                "published_family_id",
                "cta_family_id",
                "apply_payload_family_id",
                "candidate_family_id",
                "card_family_id",
            )
        ),
        "cta_disabled": (
            button.get("enabled") is False
            and button.get("actionable") is False
            and not button.get("updates")
        ),
        "family_payload_identity": str(
            item.get("render_cta_payload_id") or ""
        ).startswith(f"{family_id}:"),
        "exhaustive_zero_safe_proof": (
            evidence.get("repair_search_ran") is True
            and evidence.get("repair_search_exhaustive") is True
            and evidence.get("safe_candidate_count") == 0
            and evidence.get("safe_executor_backed_candidates_count") == 0
        ),
        "exact_blocker_preserved": bool(
            dict(item.get("exact_blockers_by_family") or {}).get("shear")
        ),
        "generic_searches_skipped": (
            evidence.get("legacy_fallback_allowed") is False
            and evidence.get("generic_one_click_solver_skipped") is True
            and evidence.get("generic_target_band_search_skipped") is True
            and evidence.get("generic_publication_fallback_skipped") is True
        ),
        "family_match_proven": item.get("family_match_passed") is True,
        "stale_contract_recovery_cannot_override_exact_blocker": all(
            marker
            in inspect.getsource(
                final_publication.normalise_stale_family_contract_violation_item
            )
            for marker in (
                "exact_blockers",
                "specific_blocker",
                "return item_d",
            )
        ),
        "publication_remains_family_blocked_despite_stale_target_signal": (
            publication.selected_family == family_id
            and publication.outcome_state == "BLOCKED"
            and publication.cta.enabled is False
        ),
        "authoritative_adapter_preserves_family_owned_ladder_stop": (
            authoritative_result.governing_family == family_id
            and authoritative_publication.get("selected_family") == family_id
            and authoritative_publication.get("outcome_state") == "BLOCKED"
            and dict(authoritative_publication.get("cta") or {}).get("enabled")
            is False
        ),
    }
    payload = {
        "schema": "family_ladder_exhaustion_publication_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
