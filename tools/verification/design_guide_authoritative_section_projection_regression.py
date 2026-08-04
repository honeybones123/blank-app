"""Focused regression for authoritative final-card display section projection."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_design_guide_formatter import build_final_design_guide_card_format  # noqa: E402
from design_brain.final_publication import build_final_design_guide_publication  # noqa: E402
from ui.final_design_guide_card import (  # noqa: E402
    final_design_guide_action_anchor_bucket,
    render_final_design_guide_card_html,
)


def main() -> int:
    item = {
        "title_main": "Shear capacity is low",
        "status": "FAIL",
        "bucket": "fail",
        "primary_action": "Recommended action: tighten links or increase effective depth.",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "family": "SHEAR_FAIL_GOVERNS",
        "affected_family": "compound_geometry_shear",
        "guidance_why": "The applied shear demand is above the available shear capacity.",
        "guidance_change_lines": [
            "Depth: 400 -> 420 mm",
            "Shear links: N10, 2-leg @150 -> N10, 4-leg @75",
        ],
        "display_truth": {
            "displayed_util": 0.9125350487372554,
            "displayed_status": "PASS",
        },
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Apply recommended changes",
            "action_type": "apply_resolved_candidate",
            "family": "SHEAR_FAIL_GOVERNS",
            "updates": {"D": 420.0, "lig_legs": 4, "s_lig": 75.0},
            "preview_pass": True,
            "expected_util": 0.9125350487372554,
            "source_candidate_id": "candidate_164",
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "family": "SHEAR_FAIL_GOVERNS",
            "updates": {"D": 420.0, "lig_legs": 4, "s_lig": 75.0},
            "candidate_id": "candidate_164",
        },
    }
    debug = {
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "family_utils": {
            "bending": 0.10631580633409207,
            "shear": 2.897076885648019,
            "crack": 0.0,
            "deflection": 0.0,
        },
        "primary_preview_util": 0.9125350487372554,
    }
    publication = build_final_design_guide_publication(item=item, debug=debug)
    card = build_final_design_guide_card_format(publication)
    html = render_final_design_guide_card_html(card)
    sections = {section.title: list(section.rows) for section in card.sections}
    current = sections.get("Current") or []
    preview = sections.get("Preview after proposed change") or []
    reasons = sections.get("Status") or []
    shear_current = next((row for row in current if row.get("family") == "shear"), {})
    shear_preview = next((row for row in preview if row.get("family") == "shear"), {})
    combined_item = {
        **item,
        "title_main": "Reduce section size and rebalance bottom reinforcement",
        "status": "EFFICIENCY",
        "bucket": "efficiency",
        "selected_family_id": "COMBINED_OVERDESIGN",
        "family": "COMBINED_OVERDESIGN",
        "affected_family": "combined",
        "display_truth": {
            "display_truth_source": "candidate_preview",
            "displayed_util": 0.9447602110462244,
            "displayed_status": "PASS",
            "source_summary_util": 0.232371,
            "source_candidate_util": 0.9447602110462244,
        },
        "button_contract": {
            **item["button_contract"],
            "family": "COMBINED_OVERDESIGN",
            "expected_util": 0.9447602110462244,
        },
        "action_payload": {
            **item["action_payload"],
            "family": "COMBINED_OVERDESIGN",
        },
    }
    combined_debug = {
        "selected_family_id": "COMBINED_OVERDESIGN",
        "family_utils": {
            "bending": 0.232371,
            "shear": 0.047,
            "crack": 0.0,
            "deflection": 0.0,
        },
        "primary_preview_util": 0.9447602110462244,
    }
    combined_publication = build_final_design_guide_publication(
        item=combined_item,
        debug=combined_debug,
    )
    combined_card = build_final_design_guide_card_format(combined_publication)
    combined_sections = {
        section.title: list(section.rows) for section in combined_card.sections
    }
    combined_preview = combined_sections.get("Preview after proposed change") or []
    combined_row = next(
        (row for row in combined_preview if row.get("family") == "combined"),
        {},
    )
    exact_blockers = {
        "bending": {
            "reason": "Bending repair catalogue was exhausted.",
            "attempted_updates": {"D": "depth", "b": "width"},
            "repair_search_exhaustive": True,
            "safe_candidate_count": 0,
        },
        "shear": {
            "reason": "Shear repair catalogue was exhausted.",
            "attempted_updates": {"s_lig": "spacing", "lig_legs": "legs"},
            "repair_search_exhaustive": True,
            "safe_candidate_count": 0,
        },
        "combined": {
            "reason": "Combined repair catalogue was exhausted.",
            "attempted_updates": {"D": "depth", "s_lig": "spacing"},
            "repair_search_exhaustive": True,
            "safe_candidate_count": 0,
        },
    }
    blocker_publication = build_final_design_guide_publication(
        item={
            "title_main": "Bending and shear repair blocked",
            "status": "BLOCKED",
            "bucket": "fail",
            "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "family": "COMBINED_BENDING_SHEAR_FAIL",
            "exact_blockers_by_family": exact_blockers,
            "candidate_search_evidence": {
                "exact_blockers_by_family": exact_blockers,
            },
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": "COMBINED_BENDING_SHEAR_FAIL",
            },
        },
        debug={
            "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "family_utils": {
                "bending": 5.78,
                "shear": 1.11,
                "crack": 0.0,
                "deflection": 0.0,
            },
        },
    )
    blocker_sections = dict(
        blocker_publication.display.expanded_evidence_sections or {}
    )
    blocker_card = build_final_design_guide_card_format(blocker_publication)
    blocker_html = render_final_design_guide_card_html(blocker_card)
    checks = {
        "four_current_rows": len(current) == 4,
        "current_shear_is_authoritative_fail": shear_current.get("value") == "2.90"
        and shear_current.get("status") == "FAIL",
        "preview_shear_uses_selected_family": shear_preview.get("after") == "0.91 PASS",
        "governing_label_uses_preview_truth": card.governing_label
        == "Preview utilisation 0.91 PASS",
        "reason_and_change_rows_present": [row.get("label") for row in reasons]
        == ["Why", "Change"],
        "cta_identity_preserved": card.cta.get("source_candidate_id") == "candidate_164"
        and card.cta.get("enabled") is True,
        "canonical_card_hook_present": "data-testid='design-guide-card'" in html,
        "current_row_hook_present": "data-testid='design-guide-current-row'" in html,
        "preview_row_hook_present": "data-testid='design-guide-preview-row'" in html,
        "failed_current_state_keeps_danger_cta_tone": (
            final_design_guide_action_anchor_bucket(card) == "fail"
        ),
        "combined_preview_projects_candidate_truth": (
            combined_row.get("before") == "0.23 PASS"
            and combined_row.get("after") == "0.94 PASS"
        ),
        "combined_governing_label_uses_candidate_truth": (
            combined_card.governing_label == "Preview utilisation 0.94 PASS"
        ),
        "exact_blockers_populate_canonical_attempt_table": (
            dict(blocker_sections.get("blocker_attempts_by_family") or {})
            == exact_blockers
        ),
        "combined_blocker_rows_have_family_test_identity": (
            "data-testid='design-guide-reason-bending'" in blocker_html
            and "data-testid='design-guide-reason-shear'" in blocker_html
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "schema": "design_guide_authoritative_section_projection_regression.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "sections": sections,
        "combined_sections": combined_sections,
        "blocker_sections": blocker_sections,
        "cta": card.cta,
    }
    artifact = (
        ROOT
        / "artifacts"
        / "verification"
        / "design_guide_authoritative_section_projection_regression.json"
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"design_guide_authoritative_section_projection_regression {payload['result']}")
    print(f"Artifact: {artifact}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
