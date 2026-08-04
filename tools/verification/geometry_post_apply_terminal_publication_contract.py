"""Prove accepted geometry Apply cannot inherit a stale pre-Apply blocker."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import build_final_design_guide_publication


def main() -> int:
    publication = build_final_design_guide_publication(
        item={
            "family": "GEOMETRY_DETAILING_GOVERNS",
            "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
            "published_family_id": "GEOMETRY_DETAILING_GOVERNS",
            "cta_family_id": "GEOMETRY_DETAILING_GOVERNS",
            "status": "PASS",
            "title_main": "Geometry correction applied",
            "guidance_intent": "already_efficient",
            "design_guide_terminal_state": "optimal",
            "post_apply_accepted_terminal": True,
            "candidate_search_evidence": {
                "selected_family_id": "GEOMETRY_DETAILING_GOVERNS",
                "published_family_id": "GEOMETRY_DETAILING_GOVERNS",
            },
        },
        debug={
            "blocked_publication_type": "no_safe_repair",
            "candidate_search_evidence": {
                "exact_blockers_by_family": {
                    "geometry": {
                        "reason": "stale_pre_apply_geometry_blocker",
                    }
                }
            },
        },
        publication_reason="geometry_post_apply_terminal_contract",
    )
    assert publication.outcome_state == "PASS"
    assert publication.blocker_reason in (None, "")
    assert publication.cta.enabled is False
    assert publication.cta.actionable is False
    assert publication.display.title == "Geometry correction applied"
    print("geometry post-Apply terminal publication contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
