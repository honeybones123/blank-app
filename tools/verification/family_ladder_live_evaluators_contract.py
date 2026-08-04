"""Focused proof that family ladder adapters use full engineering truth."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.bending_overdesign_candidate_evaluation import (  # noqa: E402
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
)
from design_brain.serviceability_candidate_evaluation import (  # noqa: E402
    ServiceabilityCandidateInput,
    ServiceabilityCandidateUpdate,
)
from design_brain.families.serviceability import ServiceabilityFamily  # noqa: E402
from design_brain.shear_overdesign_candidate_evaluation import (  # noqa: E402
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
)
from design_brain.shear_fail_bending_overdesign_candidate_merge import (  # noqa: E402
    MixedMergedCandidate as ShearMixedCandidate,
    MixedSourceCandidate as ShearMixedSource,
    ShearFailBendingOverdesignInputs,
)
from design_brain.bending_fail_shear_overdesign_candidate_merge import (  # noqa: E402
    BendingFailShearOverdesignInputs,
    MixedMergedCandidate as BendingMixedCandidate,
    MixedSourceCandidate as BendingMixedSource,
)
from design_brain.combined_overdesign_candidate_merge import (  # noqa: E402
    CombinedOverdesignInputs,
    CombinedOverdesignMergedCandidate,
    CombinedOverdesignSourceCandidate,
)
from inputs_application.family_ladder_live_evaluators import (  # noqa: E402
    build_bending_fail_shear_overdesign_live_evaluator,
    build_bending_overdesign_live_evaluator,
    build_combined_overdesign_live_evaluator,
    build_serviceability_live_evaluator,
    build_shear_fail_bending_overdesign_live_evaluator,
    build_shear_overdesign_live_evaluator,
)


def _full(state, **kwargs):
    assert kwargs.get("source")
    return {
        "overview": {
            "all_key_pass": True,
            "any_fail": False,
            "statuses": {
                "bending": "PASS",
                "shear": "PASS",
                "crack": "PASS",
                "deflection": "PASS",
            },
            "utils": {
                "bending": 0.92,
                "shear": 0.91,
                "crack": 0.73,
                "deflection": 0.81,
            },
        },
        "bending": {"Ast_bot": 1256.0, "As_min": 950.0},
        "state": dict(state),
    }


def main() -> int:
    bending = build_bending_overdesign_live_evaluator(_full)(
        BendingOverdesignCandidateInput({"b": 300.0, "D": 500.0, "bending_utilisation": 0.5}),
        BendingOverdesignCandidateUpdate({"bot1_count": 4, "db_bot_1": 20}),
    )
    shear = build_shear_overdesign_live_evaluator(_full)(
        ShearOverdesignCandidateInput({"b": 300.0, "D": 500.0, "shear_utilisation": 0.4}),
        ShearOverdesignCandidateUpdate({"s_lig": 300.0}),
    )
    serviceability = build_serviceability_live_evaluator(_full)(
        ServiceabilityCandidateInput({"b": 300.0, "D": 500.0, "serviceability_utilisation": 1.2}),
        ServiceabilityCandidateUpdate({"D": 525.0}),
    )
    serviceability_runtime = ServiceabilityFamily().contracted_serviceability_ladder_result(
        {
            "b": 300.0,
            "D": 500.0,
            "bottom_bar_count": 3,
            "serviceability_utilisation": 1.2,
        },
        evaluate_candidate=build_serviceability_live_evaluator(_full),
    )
    shear_mixed_source = ShearMixedSource(
        source_family_id="SHEAR_FAIL_GOVERNS",
        candidate_id="shear-1",
        updates={"s_lig": 150.0},
    )
    shear_mixed = build_shear_fail_bending_overdesign_live_evaluator(_full)(
        ShearFailBendingOverdesignInputs(
            selected_family_id="SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            base_state={"bending_utilisation": 0.5, "shear_utilisation": 1.2},
        ),
        ShearMixedCandidate(
            candidate_id="shear-1",
            source_candidates=(shear_mixed_source,),
            updates={"s_lig": 150.0},
        ),
    )
    bending_mixed_source = BendingMixedSource(
        source_family_id="BENDING_FAIL_GOVERNS",
        candidate_id="bending-1",
        updates={"bot1_count": 4},
    )
    bending_mixed = build_bending_fail_shear_overdesign_live_evaluator(_full)(
        BendingFailShearOverdesignInputs(
            selected_family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
            base_state={"bending_utilisation": 1.2, "shear_utilisation": 0.5},
        ),
        BendingMixedCandidate(
            candidate_id="bending-1",
            source_candidates=(bending_mixed_source,),
            updates={"bot1_count": 4},
        ),
    )
    combined_source = CombinedOverdesignSourceCandidate(
        source_family_id="BENDING_OVERDESIGN_GOVERNS",
        candidate_id="combined-1",
        updates={"bot1_count": 4},
    )
    combined = build_combined_overdesign_live_evaluator(_full)(
        CombinedOverdesignInputs(
            selected_family_id="COMBINED_OVERDESIGN_GOVERNS",
            base_state={"bending_utilisation": 0.5, "shear_utilisation": 0.4},
        ),
        CombinedOverdesignMergedCandidate(
            candidate_id="combined-1",
            source_candidates=(combined_source,),
            updates={"bot1_count": 4},
        ),
    )
    checks = {
        "bending_uses_full_overview": bending.bending_utilisation == 0.92,
        "bending_valid": bending.engineering_status.get("candidate_valid") is True,
        "shear_uses_full_overview": shear.shear_utilisation == 0.91,
        "shear_valid": shear.engineering_status.get("candidate_valid") is True,
        "serviceability_uses_full_overview": serviceability.serviceability_utilisation == 0.81,
        "serviceability_valid": serviceability.engineering_status.get("candidate_valid") is True,
        "serviceability_family_accepts_live_evaluator": (
            serviceability_runtime.get("status") == "REPAIRED"
            and bool(serviceability_runtime.get("updates"))
        ),
        "shear_mixed_uses_full_overview": (
            shear_mixed.bending_utilisation_after == 0.92
            and shear_mixed.shear_utilisation_after == 0.91
            and shear_mixed.engineering_status.get("candidate_valid") is True
        ),
        "bending_mixed_uses_full_overview": (
            bending_mixed.bending_utilisation_after == 0.92
            and bending_mixed.shear_utilisation_after == 0.91
            and bending_mixed.engineering_status.get("candidate_valid") is True
        ),
        "combined_overdesign_uses_full_overview": (
            combined.bending_utilisation_after == 0.92
            and combined.shear_utilisation_after == 0.91
            and combined.engineering_status.get("candidate_valid") is True
        ),
        "all_sources_authoritative": all(
            result.engineering_status.get("source") == "evaluate_candidate_full"
            for result in (
                bending,
                shear,
                serviceability,
                shear_mixed,
                bending_mixed,
                combined,
            )
        ),
    }
    if not all(checks.values()):
        print(checks)
        return 1
    print("family_ladder_live_evaluators_contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
