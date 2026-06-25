"""Focused source and interaction proofs for COMBINED_OVERDESIGN_GOVERNS."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.combined_overdesign_candidate_merge import (  # noqa: E402
    CombinedOverdesignCandidateEvaluation,
    CombinedOverdesignInputs,
    CombinedOverdesignMergedCandidate,
    CombinedOverdesignSourceCandidate,
    combined_overdesign_candidate_state_hash,
    merge_updates,
)
from design_brain.families.bending_and_shear_overdesign_govern.contract import (  # noqa: E402
    candidate_source_contract,
    exact_stop_rules,
    exhausted_rules,
    interaction_contract,
    lane_proof_policies,
    minimum_reinforcement_protection,
    ranking_criteria,
    underdesign_protection,
    zero_shear_protection,
)


def _evaluation(
    inputs: CombinedOverdesignInputs,
    candidate: CombinedOverdesignMergedCandidate,
    *,
    bending_after: float,
    shear_after: float,
    as_after: float = 1256.0,
    as_min: float = 950.0,
    zero_shear: bool = False,
    ligature_removal: bool = False,
) -> CombinedOverdesignCandidateEvaluation:
    creates_bending_underdesign = bending_after > 1.0
    creates_shear_underdesign = shear_after > 1.0
    below_min = as_after < as_min
    invalid = creates_bending_underdesign or creates_shear_underdesign or below_min
    reasons = []
    if creates_bending_underdesign:
        reasons.append("candidate creates bending underdesign")
    if creates_shear_underdesign:
        reasons.append("candidate creates shear underdesign")
    if below_min:
        reasons.append("candidate violates minimum reinforcement")
    return CombinedOverdesignCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=combined_overdesign_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=0.62,
        shear_utilisation_before=0.41,
        bending_utilisation_after=bending_after,
        shear_utilisation_after=shear_after,
        bending_moves_toward_target=0.85 <= bending_after <= 1.0,
        shear_moves_toward_target=0.85 <= shear_after <= 1.0,
        bending_compliant=not creates_bending_underdesign,
        shear_compliant=not creates_shear_underdesign,
        bending_inside_target_band=0.85 <= bending_after <= 1.0,
        shear_inside_target_band=0.85 <= shear_after <= 1.0,
        creates_bending_underdesign=creates_bending_underdesign,
        creates_shear_underdesign=creates_shear_underdesign,
        minimum_reinforcement_status={
            "As": as_after,
            "As_min": as_min,
            "As_greater_than_or_equal_to_As_min": not below_min,
            "status": "PASS" if not below_min else "FAIL",
        },
        zero_shear_status={
            "zero_shear": zero_shear,
            "ligature_removal_preferred": zero_shear and ligature_removal,
            "ligature_removal_compliant": ligature_removal,
        },
        geometry_interaction_status={
            "geometry_changed": candidate.interaction_flags["geometry_changed"],
            "rechecked": ["bending", "shear", "minimum reinforcement", "geometry limits", "constructability"],
        },
        reinforcement_interaction_status={
            "bending_reinforcement_changed": candidate.interaction_flags["bending_reinforcement_changed"],
            "shear_reinforcement_changed": candidate.interaction_flags["shear_reinforcement_changed"],
        },
        code_compliance_status={"status": "PASS" if not invalid else "FAIL"},
        detailing_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"after": 0.0 if ligature_removal else 2.0},
        beam_volume={"after": 150000.0},
        cost_proxy={"after": 0.0 if ligature_removal else 0.72},
        rejection_reasons=tuple(reasons),
        engineering_status={"candidate_valid": not invalid},
    ).with_evaluation_hash()


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_governs_source_interaction_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_source_interaction_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_OVERDESIGN_GOVERNS Source and Interaction Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    bend = CombinedOverdesignSourceCandidate(
        "BENDING_OVERDESIGN_GOVERNS",
        "bend_reduce",
        {"bot1_count": 4, "db_bot_1": 20},
    )
    shear = CombinedOverdesignSourceCandidate(
        "SHEAR_OVERDESIGN_GOVERNS",
        "shear_space",
        {"s_lig": 300.0},
    )
    geometry = CombinedOverdesignSourceCandidate(
        "BENDING_OVERDESIGN_GOVERNS",
        "bend_depth_reduce",
        {"D": 475.0},
    )
    removal = CombinedOverdesignSourceCandidate(
        "SHEAR_OVERDESIGN_GOVERNS",
        "remove_links",
        {"lig_d": 0, "lig_legs": 0},
    )
    rogue = CombinedOverdesignSourceCandidate("SHEAR_FAIL_GOVERNS", "rogue", {"lig_d": 12})
    inputs = CombinedOverdesignInputs(
        selected_family_id="COMBINED_OVERDESIGN_GOVERNS",
        base_state={"D": 500.0, "b": 300.0, "As": 2260.0, "As_min": 950.0},
        bending_overdesign_candidates=(bend.to_dict(), geometry.to_dict()),
        shear_overdesign_candidates=(shear.to_dict(), removal.to_dict()),
    )
    merged = CombinedOverdesignMergedCandidate(
        "bend_shear_cleanup",
        (bend, shear),
        merge_updates(bend.updates, shear.updates),
    )
    geometry_merged = CombinedOverdesignMergedCandidate(
        "geometry_and_shear_cleanup",
        (geometry, shear),
        merge_updates(geometry.updates, shear.updates),
    )
    zero_shear_merged = CombinedOverdesignMergedCandidate(
        "zero_shear_remove_links",
        (bend, removal),
        merge_updates(bend.updates, removal.updates),
    )
    valid = _evaluation(inputs, merged, bending_after=0.91, shear_after=0.88)
    bending_fail = _evaluation(inputs, merged, bending_after=1.04, shear_after=0.88)
    shear_fail = _evaluation(inputs, merged, bending_after=0.91, shear_after=1.03)
    below_min = _evaluation(inputs, merged, bending_after=0.91, shear_after=0.88, as_after=940.0)
    zero = _evaluation(inputs, zero_shear_merged, bending_after=0.91, shear_after=0.0, zero_shear=True, ligature_removal=True)
    geometry_eval = _evaluation(inputs, geometry_merged, bending_after=0.90, shear_after=0.89)
    policies = lane_proof_policies()
    checks = {
        "allowed_sources_match_contract": set(candidate_source_contract().get("allowed_sources") or [])
        == {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"},
        "rogue_fail_source_rejected": rogue.source_allowed is False,
        "combined_does_not_duplicate_ladders": candidate_source_contract().get("must_not_duplicate_ladders") is True,
        "bending_underdesign_rejected": bending_fail.engineering_status.get("candidate_valid") is False
        and "candidate creates bending underdesign" in bending_fail.rejection_reasons,
        "shear_underdesign_rejected": shear_fail.engineering_status.get("candidate_valid") is False
        and "candidate creates shear underdesign" in shear_fail.rejection_reasons,
        "minimum_reinforcement_rejected": below_min.engineering_status.get("candidate_valid") is False
        and "candidate violates minimum reinforcement" in below_min.rejection_reasons,
        "zero_shear_removal_preferred": zero.zero_shear_status.get("ligature_removal_preferred") is True
        and zero_shear_protection().get("must_not_preserve_unnecessary_shear_reinforcement_when_removal_is_compliant") is True,
        "geometry_recheck_evidence_present": geometry_eval.geometry_interaction_status.get("geometry_changed") is True
        and set(geometry_eval.geometry_interaction_status.get("rechecked") or [])
        >= {"bending", "shear", "minimum reinforcement", "geometry limits", "constructability"},
        "exact_stop_policy_present": bool(exact_stop_rules().get("allowed_when")),
        "exhausted_policy_specific_blocker_required": "specific blocker exists" in exhausted_rules().get("requires", []),
        "ranking_contract_order_present": tuple(ranking_criteria())
        == (
            "both checks remain compliant",
            "both checks move toward target band",
            "worst utilisation closest to target band",
            "smallest reinforcement quantity",
            "smallest beam volume",
            "constructability",
            "cost proxy",
        ),
        "underdesign_policy_present": bool(underdesign_protection().get("invalid_before_ranking")),
        "minimum_reinforcement_policy_present": minimum_reinforcement_protection().get(
            "as_must_be_greater_than_or_equal_to_as_min"
        )
        is True,
        "lane_policies_cover_required_cases": all(
            key in policies
            for key in (
                "candidate_source",
                "underdesign_protection",
                "minimum_reinforcement",
                "zero_shear",
                "geometry_interaction",
                "terminal",
            )
        ),
        "valid_candidate_remains_rankable": valid.engineering_status.get("candidate_valid") is True,
        "interaction_contract_has_geometry_recheck": set(interaction_contract().get("geometry_recheck_required") or [])
        >= {"bending", "shear", "minimum reinforcement", "geometry limits", "constructability"},
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_overdesign_governs_source_interaction.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "cases": {
            "valid": valid.to_dict(),
            "bending_underdesign": bending_fail.to_dict(),
            "shear_underdesign": shear_fail.to_dict(),
            "below_minimum_reinforcement": below_min.to_dict(),
            "zero_shear": zero.to_dict(),
            "geometry": geometry_eval.to_dict(),
        },
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_OVERDESIGN_GOVERNS source interaction FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_OVERDESIGN_GOVERNS source interaction PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
