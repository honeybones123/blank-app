from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_and_shear_fail_govern.runtime import (  # noqa: E402
    CombinedCandidateEvaluation,
    run_combined_bending_shear_fail_runtime,
)
from design_brain.families.combined_bending_shear_fail import (  # noqa: E402
    CombinedBendingShearFailFamily,
    _inputs_from_state,
)


def _inputs() -> dict[str, Any]:
    return {
        "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
    }


def _bending() -> tuple[dict[str, Any], ...]:
    return (
        {
            "source_family_id": "BENDING_FAIL_GOVERNS",
            "candidate_id": "bend_depth",
            "updates": {"D": 550.0, "bot_row_1_bars": 5, "bot_row_1_dia": 20},
        },
    )


def _shear() -> tuple[dict[str, Any], ...]:
    return (
        {
            "source_family_id": "SHEAR_FAIL_GOVERNS",
            "candidate_id": "shear_links",
            "updates": {"lig_d": 12, "s_lig": 150.0},
        },
    )


def _evaluate(inputs, candidate) -> CombinedCandidateEvaluation:
    updates = dict(candidate.updates)
    repairs_both = updates.get("D") == 550.0 and updates.get("lig_d") == 12
    return CombinedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=candidate.update_hash,
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.22,
        shear_utilisation_before=1.18,
        bending_utilisation_after=0.93 if repairs_both else 1.08,
        shear_utilisation_after=0.91 if repairs_both else 1.12,
        bending_improves=repairs_both,
        shear_improves=repairs_both,
        bending_compliant=repairs_both,
        shear_compliant=repairs_both,
        bending_inside_target_band=repairs_both,
        shear_inside_target_band=repairs_both,
        both_failures_repaired=repairs_both,
        geometry_interaction_status={"geometry_changed": "D" in updates, "rechecked": ["bending", "shear"]},
        reinforcement_interaction_status={"bending_reinforcement_rechecked": True, "shear_reinforcement_rechecked": True},
        code_compliance_status={"status": "PASS" if repairs_both else "FAIL"},
        detailing_status={"status": "PASS" if repairs_both else "FAIL"},
        constructability_status={"status": "PASS"},
        geometry_increase={"total_mm": 50.0 if "D" in updates else 0.0},
        reinforcement_increase={"total": 2.0},
        cost_proxy={"after": 1.2 if repairs_both else 1.0},
        rejection_reasons=() if repairs_both else ("partial repair",),
        engineering_status={"candidate_valid": repairs_both},
    ).with_evaluation_hash()


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_combined_candidate_projection_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_combined_candidate_projection_parity_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Brain Combined Candidate Projection Parity",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    family = CombinedBendingShearFailFamily()
    ladder = family.contracted_repair_ladder_specs(
        _inputs(),
        bending_fail_candidates=_bending(),
        shear_fail_candidates=_shear(),
        evaluate_candidate=_evaluate,
    )
    runtime = run_combined_bending_shear_fail_runtime(
        inputs=_inputs_from_state(_inputs(), bending_fail_candidates=_bending(), shear_fail_candidates=_shear()),
        evaluate_candidate=_evaluate,
    )

    runtime_rows = list(runtime.candidate_repairs)
    family_rows = [dict(row) for row in list(ladder.get("candidate_repairs") or []) if isinstance(row, dict)]
    checks = {
        "candidate_count_match": len(runtime_rows) == len(family_rows),
        "family_rows_equal_runtime_rows": runtime_rows == family_rows,
        "selected_recommendation_updates_match_runtime": dict((ladder.get("selected_recommendation") or {}).get("updates") or {})
        == dict((runtime.selected_recommendation or {}).get("updates") or {}),
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "design_brain_combined_candidate_projection_parity_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "runtime_rows": runtime_rows,
        "family_rows": family_rows,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("design_brain_combined_candidate_projection_parity_snapshot FAIL")
        print(f"json={json_path}")
        print(f"report={report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("design_brain_combined_candidate_projection_parity_snapshot PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
