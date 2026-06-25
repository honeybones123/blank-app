"""Proof snapshot for the COMBINED_OVERDESIGN_GOVERNS merge runtime."""

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
    combined_overdesign_candidate_state_hash,
)
from design_brain.families.bending_and_shear_overdesign_govern.runtime import (  # noqa: E402
    run_combined_overdesign_governs_runtime,
)


FORBIDDEN_RUNTIME_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "button_contract",
    "publication",
    "build_design_guide_apply_button_contract",
    "family_chooser",
    "classify_governing_state",
    "run_bending_overdesign_governs_runtime",
    "run_shear_overdesign_governs_runtime",
    "contracted_optimisation_ladder_specs",
}


def _inputs() -> CombinedOverdesignInputs:
    return CombinedOverdesignInputs(
        selected_family_id="COMBINED_OVERDESIGN_GOVERNS",
        base_state={"b": 300.0, "D": 500.0, "As": 2260.0, "As_min": 950.0, "Vstar": 0.0},
        bending_overdesign_candidates=(
            {
                "source_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "candidate_id": "bend_good",
                "updates": {"bot1_count": 4, "db_bot_1": 20},
            },
            {
                "source_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "candidate_id": "bend_underdesign",
                "updates": {"bot1_count": 2, "db_bot_1": 16},
            },
        ),
        shear_overdesign_candidates=(
            {
                "source_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "candidate_id": "shear_spacing",
                "updates": {"s_lig": 300.0},
            },
            {
                "source_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "candidate_id": "remove_links",
                "updates": {"lig_d": 0, "lig_legs": 0},
            },
        ),
    )


def _evaluation(
    inputs: CombinedOverdesignInputs,
    candidate: CombinedOverdesignMergedCandidate,
) -> CombinedOverdesignCandidateEvaluation:
    updates = dict(candidate.updates)
    creates_bending = updates.get("bot1_count") == 2
    zero_removal = updates.get("lig_d") == 0 and updates.get("lig_legs") == 0
    bending_after = 1.06 if creates_bending else 0.91
    shear_after = 0.0 if zero_removal else 0.88
    valid = not creates_bending
    reasons = ("candidate creates bending underdesign",) if creates_bending else ()
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
        bending_moves_toward_target=not creates_bending,
        shear_moves_toward_target=True,
        bending_compliant=not creates_bending,
        shear_compliant=True,
        bending_inside_target_band=0.85 <= bending_after <= 1.0,
        shear_inside_target_band=0.85 <= shear_after <= 1.0,
        creates_bending_underdesign=creates_bending,
        creates_shear_underdesign=False,
        minimum_reinforcement_status={
            "As": 1256.0,
            "As_min": 950.0,
            "As_greater_than_or_equal_to_As_min": True,
            "status": "PASS",
        },
        zero_shear_status={
            "zero_shear": True,
            "ligature_removal_preferred": zero_removal,
            "ligature_removal_compliant": zero_removal,
        },
        geometry_interaction_status={
            "geometry_changed": candidate.interaction_flags["geometry_changed"],
            "rechecked": ["bending", "shear", "minimum reinforcement", "geometry limits", "constructability"],
        },
        reinforcement_interaction_status={
            "bending_reinforcement_changed": candidate.interaction_flags["bending_reinforcement_changed"],
            "shear_reinforcement_changed": candidate.interaction_flags["shear_reinforcement_changed"],
        },
        code_compliance_status={"status": "PASS" if valid else "FAIL"},
        detailing_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"after": 0.0 if zero_removal else 2.0},
        beam_volume={"after": 150000.0},
        cost_proxy={"after": 0.0 if zero_removal else 0.72},
        rejection_reasons=reasons,
        engineering_status={"candidate_valid": valid},
    ).with_evaluation_hash()


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_governs_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_OVERDESIGN_GOVERNS Runtime Snapshot",
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
    inputs = _inputs()
    result = run_combined_overdesign_governs_runtime(inputs=inputs, evaluate_candidate=_evaluation)
    repeat = run_combined_overdesign_governs_runtime(inputs=inputs, evaluate_candidate=_evaluation)
    runtime_source = (ROOT / "design_brain" / "families" / "bending_and_shear_overdesign_govern" / "runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden_hits = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    selected = dict(result.selected_recommendation or {})
    checks = {
        "runtime_selected_candidate": result.status == "SELECTED" and bool(selected),
        "runtime_hash_stable": bool(result.runtime_hash) and result.runtime_hash == repeat.runtime_hash,
        "source_merge_candidates_created": result.candidate_source_proof.get("merged_candidate_count") == 4,
        "source_contract_does_not_duplicate_ladders": result.candidate_source_proof.get("must_not_duplicate_ladders") is True,
        "only_overdesign_sources_used": all(
            set(row.get("source_family_ids") or ())
            <= {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"}
            for row in result.combined_merge_trace
        ),
        "underdesign_candidate_rejected": any(
            "candidate creates bending underdesign" in tuple(row.get("rejection_reasons") or ())
            for row in result.rejected_candidate_evidence
        ),
        "zero_shear_removal_preferred_by_ranking": selected.get("candidate_id") == "bend_good+remove_links",
        "ranking_evidence_present": tuple(result.ranking_evidence.get("criteria") or ()),
        "exact_stop_proof_present": bool(result.exact_stop_proof.get("allowed_when")),
        "exhausted_proof_specific_blocker_surface": "specific blocker exists" in result.exhausted_proof.get("requires", []),
        "ownership_proof_excludes_ladders": result.ownership_proof.get("combined_owns_bending_ladder") is False
        and result.ownership_proof.get("combined_owns_shear_ladder") is False,
        "runtime_source_clean": not forbidden_hits,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if forbidden_hits:
        failures.append(f"forbidden_runtime_terms:{forbidden_hits}")
    snapshot = {
        "schema": "combined_overdesign_governs_runtime.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "runtime_hash": result.runtime_hash,
        "selected_recommendation": result.selected_recommendation,
        "candidate_source_proof": result.candidate_source_proof,
        "ranking_evidence": result.ranking_evidence,
        "ownership_proof": result.ownership_proof,
        "trace": result.combined_merge_trace,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_OVERDESIGN_GOVERNS runtime FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_OVERDESIGN_GOVERNS runtime PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
