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
    mixed_candidate_state_hash,
)
from design_brain.families.bending_fail_shear_overdesign_governs import (  # noqa: E402
    evaluate_bending_fail_shear_overdesign_governs,
)


def _inputs() -> BendingFailShearOverdesignInputs:
    return BendingFailShearOverdesignInputs(
        selected_family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        base_state={"D": 500.0, "b": 300.0},
        bending_fail_candidates=(
            {"source_family_id": "BENDING_FAIL_GOVERNS", "candidate_id": "bend_repair", "updates": {"D": 550.0}},
        ),
        shear_overdesign_candidates=(
            {"source_family_id": "SHEAR_OVERDESIGN_GOVERNS", "candidate_id": "shear_cleanup", "updates": {"s_lig": 250}},
        ),
    )


def _evaluation(inputs: BendingFailShearOverdesignInputs, candidate: MixedMergedCandidate) -> MixedCandidateEvaluation:
    has_bending = candidate.has_mandatory_bending_source
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.18,
        shear_utilisation_before=0.52,
        bending_utilisation_after=0.94 if has_bending else 1.1,
        shear_utilisation_after=0.78,
        bending_repaired=has_bending,
        shear_compliant=True,
        shear_moves_toward_target=candidate.has_opportunistic_shear_source,
        creates_shear_underdesign=False,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"increase": 10.0},
        beam_volume={"geometry_increase": 25.0},
        cost_proxy={"after": 100.0},
        engineering_status={"candidate_valid": has_bending},
    ).with_evaluation_hash()


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_cutover_implementation_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN Cutover Implementation",
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
    result = evaluate_bending_fail_shear_overdesign_governs({"inputs": _inputs(), "evaluate_candidate": _evaluation})
    runtime_result = dict((result.evidence or {}).get("runtime_result") or {})
    lock_proof = dict(result.lock_proof or {})
    checks = {
        "api_returns_family_result": result.family_id == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS"
        and result.status == "SELECTED",
        "api_identifies_runtime_authority": result.evidence.get("contract_runtime_authority") == "run_bending_fail_shear_overdesign_runtime"
        and lock_proof.get("runtime_authority") == "run_bending_fail_shear_overdesign_runtime",
        "selected_recommendation_present": bool(result.selected_candidate) and bool(result.updates),
        "runtime_result_embedded": bool(runtime_result.get("runtime_hash"))
        and bool(runtime_result.get("selected_recommendation")),
        "no_publication_or_cta_generated": result.publication == {} and result.cta_contract == {},
        "no_source_ladder_duplication_claimed": lock_proof.get("mixed_generates_no_bending_repair_ladder") is True
        and lock_proof.get("mixed_generates_no_shear_optimisation_ladder") is True,
        "mandatory_opportunistic_declared": lock_proof.get("mandatory_objective") == "bending repair"
        and lock_proof.get("opportunistic_objective") == "shear optimisation",
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_cutover_implementation.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "family_result": {
            "family_id": result.family_id,
            "status": result.status,
            "selected_candidate": result.selected_candidate,
            "updates": result.updates,
            "lock_proof": lock_proof,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("BENDING_FAIL_SHEAR_OVERDESIGN cutover implementation FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_FAIL_SHEAR_OVERDESIGN cutover implementation PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
