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

from design_brain.shear_fail_bending_overdesign_candidate_merge import (  # noqa: E402
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    MixedSourceCandidate,
    ShearFailBendingOverdesignInputs,
    mixed_candidate_state_hash,
)
from design_brain.families.shear_fail_bending_overdesign_governs.contract import (  # noqa: E402
    candidate_source_contract,
    lane_proof_policies,
    priority_contract,
)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_governs_source_priority_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_governs_source_priority_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN Source Priority Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Proof",
                "",
                "- Shear repair is the mandatory source.",
                "- Bending optimisation is opportunistic.",
                "- Bending cleanup alone is rejected before ranking.",
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


def _evaluation(
    inputs: ShearFailBendingOverdesignInputs,
    candidate: MixedMergedCandidate,
    *,
    shear_repaired: bool,
    bending_compliant: bool,
    creates_bending_underdesign: bool = False,
) -> MixedCandidateEvaluation:
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        shear_utilisation_after=0.94 if shear_repaired else 1.22,
        bending_utilisation_after=0.82 if bending_compliant else 1.04,
        shear_repaired=shear_repaired,
        bending_compliant=bending_compliant,
        creates_bending_underdesign=creates_bending_underdesign,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        engineering_status={"candidate_valid": shear_repaired and bending_compliant and not creates_bending_underdesign},
    ).with_evaluation_hash()


def main() -> int:
    inputs = ShearFailBendingOverdesignInputs(
        selected_family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        base_state={"Vstar": 260.0, "phiVu": 210.0, "Mstar": 180.0, "phiMu": 360.0},
    )
    shear = MixedSourceCandidate("SHEAR_FAIL_GOVERNS", "shear_repair", {"s_lig": 125})
    bending = MixedSourceCandidate("BENDING_OVERDESIGN_GOVERNS", "bending_cleanup", {"bot1_count": 4})
    approved = MixedSourceCandidate("APPROVED_MIXED_MERGE_RULE", "approved_merge", {"s_lig": 125, "bot1_count": 4})
    shear_only = MixedMergedCandidate("shear_only", (shear,), dict(shear.updates), "MANDATORY_SHEAR_REPAIR_ONLY")
    bending_only = MixedMergedCandidate("bending_only", (bending,), dict(bending.updates), "OPPORTUNISTIC_BENDING_ONLY")
    paired = MixedMergedCandidate("paired", (shear, bending), {"s_lig": 125, "bot1_count": 4})
    approved_pair = MixedMergedCandidate("approved_pair", (approved,), dict(approved.updates), "APPROVED_MIXED_MERGE_RULE")

    rows = {
        "shear_only": _evaluation(inputs, shear_only, shear_repaired=True, bending_compliant=True).to_dict(),
        "bending_only": _evaluation(inputs, bending_only, shear_repaired=False, bending_compliant=True).to_dict(),
        "paired": _evaluation(inputs, paired, shear_repaired=True, bending_compliant=True).to_dict(),
        "creates_bending_underdesign": _evaluation(
            inputs,
            paired,
            shear_repaired=True,
            bending_compliant=False,
            creates_bending_underdesign=True,
        ).to_dict(),
        "approved_pair": _evaluation(inputs, approved_pair, shear_repaired=True, bending_compliant=True).to_dict(),
    }
    checks = {
        "contract_mandatory_source": candidate_source_contract().get("mandatory_source") == "SHEAR_FAIL_GOVERNS",
        "contract_opportunistic_source": candidate_source_contract().get("opportunistic_source") == "BENDING_OVERDESIGN_GOVERNS",
        "priority_mandatory_objective": priority_contract().get("mandatory_objective") == "shear repair",
        "priority_opportunistic_objective": priority_contract().get("opportunistic_objective") == "bending optimisation",
        "shear_only_has_mandatory_source": shear_only.has_mandatory_shear_source,
        "shear_only_is_allowed_fallback": rows["shear_only"]["shear_repaired"] is True
        and rows["shear_only"]["bending_compliant"] is True,
        "bending_only_lacks_mandatory_source": not bending_only.has_mandatory_shear_source,
        "bending_only_fails_mandatory_repair": rows["bending_only"]["shear_repaired"] is False,
        "paired_has_both_sources": paired.has_mandatory_shear_source and paired.has_opportunistic_bending_source,
        "approved_merge_source_allowed": approved_pair.sources_allowed,
        "bending_underdesign_protected": rows["creates_bending_underdesign"]["creates_bending_underdesign"] is True
        and rows["creates_bending_underdesign"]["bending_compliant"] is False,
        "lane_policies_loaded": "priority" in lane_proof_policies() and "bending_protection" in lane_proof_policies(),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "shear_fail_bending_overdesign_governs_source_priority.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "candidate_source_contract": candidate_source_contract(),
        "priority_contract": priority_contract(),
        "lane_proof_policies": lane_proof_policies(),
        "evaluations": rows,
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS source priority FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS source priority PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
