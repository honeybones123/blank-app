"""Lock browser validation to the canonical family-prefixed blocker schema."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.browser_live_design_guide_fuzz_verifier import (  # noqa: E402
    _combined_blockers_valid,
    assert_optimisation_contract,
    blocker_proof_analysis,
    build_optimisation_audit,
    expected_card_colour,
    is_terminal_exact_cleanup_no_action,
)


def _blocker(family: str) -> dict:
    return {
        "family": family,
        "attempted_candidate_count": 1,
        "best_rejected_candidate_id": f"{family}_cleanup_exhausted",
        "failed_check_name": "governing detailing limit",
        "failed_check_status": "BLOCKED",
        "failed_check_util": 0.89,
        "failed_check_demand": 95.0,
        "failed_check_capacity_or_limit": 106.9,
        f"{family}_cleanup_search_ran": True,
        f"{family}_cleanup_search_exhaustive": True,
        f"safe_{family}_cleanup_count": 0,
        f"executable_{family}_cleanup_count": 0,
        f"post_click_{family}_cleanup_search_ran": True,
        f"post_click_{family}_cleanup_search_exhaustive": True,
        f"post_click_safe_{family}_cleanup_count": 0,
        f"post_click_executable_{family}_cleanup_count": 0,
        "reason": "The exhaustive family cleanup ladder found no safe executor-backed candidate.",
    }


def main() -> int:
    for family in ("bending", "shear"):
        row = _blocker(family)
        state = {
            "guidance_compute_probe": {
                "exact_blockers_by_family": {family: row},
            }
        }
        card = {
            "family": "TARGET_BAND_REACHED",
            "blocker_attempts_by_family": {family: row},
        }
        proof = blocker_proof_analysis(card, state, family)
        assert proof["cleanup_search_ran"] is True
        assert proof["cleanup_search_exhaustive"] is True
        assert proof["safe_candidate_count"] == 0
        assert proof["executable_candidate_count"] == 0
        assert proof["specificity_valid"] is True
        assert proof["valid"] is True
        assert _combined_blockers_valid(card, state, [family]) is True
        terminal_card = {
            **card,
            "title": "Design guidance",
            "text": row["reason"],
            "cta_visible": False,
            "cta_enabled": False,
            "button_contract": {
                "actionable": False,
                "enabled": False,
                "action_type": None,
                "updates": {},
            },
        }
        summary = {
            "bending": {
                "status": "PASS",
                "util": 0.61 if family == "bending" else 0.89,
            },
            "shear": {
                "status": "PASS",
                "util": 0.61 if family == "shear" else 0.89,
            },
        }
        assert is_terminal_exact_cleanup_no_action(summary, terminal_card, state) is True
        assert expected_card_colour(summary, terminal_card, state) == "green"
        audit = build_optimisation_audit(summary, terminal_card, state)
        assert audit["card_type"] == "TERMINAL"
        assert audit["optimisation_family"] == family
        assert audit["blocker_evidence"]["valid"] is True
        step = {
            "visible_summary": summary,
            "visible_design_guide": terminal_card,
            "browser_state": state,
        }
        assert_optimisation_contract(step)
        assert step["optimisation_audit"]["card_type"] == "TERMINAL"
    print(
        "PASS: browser exact-blocker validation accepts complete canonical "
        "family-prefixed bending and shear evidence"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
