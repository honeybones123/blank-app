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

from design_brain.bending_fail_shear_overdesign_candidate_merge import (  # noqa: E402
    BendingFailShearOverdesignInputs,
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    MixedSourceCandidate,
    merge_updates,
    mixed_candidate_state_hash,
    stable_bending_fail_shear_overdesign_hash,
)
from design_brain.families.bending_fail_shear_overdesign_governs.contract import (  # noqa: E402
    candidate_source_contract,
    contract_hash,
    exact_stop_rules,
    exhausted_rules,
    invalid_before_ranking,
    lane_proof_policies,
    priority_contract,
    ranking_criteria,
    shared_exclusions,
)


REQUIRED_SHARED_EXCLUSIONS = {"publication", "CTA rendering", "apply routing", "session state", "UI rendering"}


def _inputs() -> BendingFailShearOverdesignInputs:
    return BendingFailShearOverdesignInputs(
        selected_family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        base_state={"D": 500.0, "b": 300.0, "s_lig": 150},
    )


def _candidate(*sources: MixedSourceCandidate, updates: dict[str, Any] | None = None) -> MixedMergedCandidate:
    return MixedMergedCandidate(
        candidate_id="+".join(source.candidate_id for source in sources),
        source_candidates=tuple(sources),
        updates=updates or merge_updates(*(source.updates for source in sources)),
    )


def _evaluation(
    inputs: BendingFailShearOverdesignInputs,
    candidate: MixedMergedCandidate,
    *,
    bending_repaired: bool,
    shear_compliant: bool,
    shear_moves: bool,
    creates_shear_underdesign: bool = False,
    reasons: tuple[str, ...] = (),
) -> MixedCandidateEvaluation:
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.18,
        shear_utilisation_before=0.52,
        bending_utilisation_after=0.94 if bending_repaired else 1.1,
        shear_utilisation_after=0.78 if shear_compliant else 1.04,
        bending_repaired=bending_repaired,
        shear_compliant=shear_compliant,
        bending_inside_target_band=bending_repaired,
        shear_inside_target_band=False,
        shear_moves_toward_target=shear_moves,
        creates_shear_underdesign=creates_shear_underdesign,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"after": 100.0},
        beam_volume={"after": 1.0},
        cost_proxy={"after": 1.0},
        rejection_reasons=reasons,
        engineering_status={"candidate_valid": bending_repaired and shear_compliant and not creates_shear_underdesign},
    ).with_evaluation_hash()


def _valid(evaluation: MixedCandidateEvaluation, candidate: MixedMergedCandidate) -> bool:
    if not candidate.has_mandatory_bending_source:
        return False
    if not evaluation.bending_repaired:
        return False
    if not evaluation.shear_compliant or evaluation.creates_shear_underdesign:
        return False
    return True


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_source_priority_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_source_priority_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN Source Priority Snapshot",
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
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    inputs = _inputs()
    bend = MixedSourceCandidate("BENDING_FAIL_GOVERNS", "bend_repair", {"D": 550.0})
    shear = MixedSourceCandidate("SHEAR_OVERDESIGN_GOVERNS", "shear_cleanup", {"s_lig": 250})
    shear_only = _candidate(shear)
    mixed_good = _candidate(bend, shear)
    bend_only = _candidate(bend)
    shear_unsafe = _candidate(bend, shear, updates={"D": 550.0, "s_lig": 300})
    evaluations = {
        "case_a_mixed_rankable": _evaluation(inputs, mixed_good, bending_repaired=True, shear_compliant=True, shear_moves=True),
        "case_b_shear_only_rejected": _evaluation(inputs, shear_only, bending_repaired=False, shear_compliant=True, shear_moves=True),
        "case_c_bend_only_rankable": _evaluation(inputs, bend_only, bending_repaired=True, shear_compliant=True, shear_moves=False),
        "case_d_shear_underdesign_rejected": _evaluation(
            inputs,
            shear_unsafe,
            bending_repaired=True,
            shear_compliant=False,
            shear_moves=False,
            creates_shear_underdesign=True,
        ),
    }
    checks = {
        "allowed_sources_exact": set(candidate_source_contract().get("allowed_sources") or ())
        == {"BENDING_FAIL_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "APPROVED_MIXED_MERGE_RULE"},
        "must_not_duplicate_source_ladders": candidate_source_contract().get("must_not_duplicate_ladders") is True,
        "mandatory_and_opportunistic_declared": priority_contract().get("mandatory_objective") == "bending repair"
        and priority_contract().get("opportunistic_objective") == "shear optimisation",
        "ranking_order_has_bending_first": tuple(ranking_criteria())[:2]
        == ("repairs bending failure", "maintains shear compliance"),
        "invalid_before_ranking_blocks_bending_and_shear_failures": {
            "candidate leaves bending underdesign unresolved",
            "candidate creates shear underdesign",
        }.issubset(set(invalid_before_ranking())),
        "case_a_mixed_rankable": _valid(evaluations["case_a_mixed_rankable"], mixed_good),
        "case_b_shear_only_rejected": not _valid(evaluations["case_b_shear_only_rejected"], shear_only),
        "case_c_bend_only_rankable_when_shear_cleanup_unsafe": _valid(evaluations["case_c_bend_only_rankable"], bend_only),
        "case_d_shear_underdesign_rejected": not _valid(evaluations["case_d_shear_underdesign_rejected"], shear_unsafe),
        "terminal_rules_present": bool(exact_stop_rules().get("allowed_when")) and bool(exhausted_rules().get("requires")),
        "lane_policy_sections_present": {"candidate_source", "priority", "shear_protection", "terminal"}.issubset(set(lane_proof_policies())),
        "shared_exclusions_preserved": REQUIRED_SHARED_EXCLUSIONS.issubset(set(shared_exclusions())),
    }
    failures = [key for key, passed in checks.items() if not passed]
    payload = {
        "evaluations": {key: value.to_dict() for key, value in evaluations.items()},
        "checks": checks,
    }
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_source_priority.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_hash": contract_hash(),
        "checks": checks,
        "failures": failures,
        "snapshot_hash": stable_bending_fail_shear_overdesign_hash(payload),
        "payload": payload,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("BENDING_FAIL_SHEAR_OVERDESIGN source priority snapshot FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_FAIL_SHEAR_OVERDESIGN source priority snapshot PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
