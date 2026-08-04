from __future__ import annotations

import ast
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
RUNTIME_PATH = ROOT / "design_brain" / "families" / "bending_fail_shear_overdesign_governs" / "runtime.py"

from design_brain.bending_fail_shear_overdesign_candidate_merge import (  # noqa: E402
    BendingFailShearOverdesignInputs,
    MixedCandidateEvaluation,
    MixedMergedCandidate,
    mixed_candidate_state_hash,
    stable_bending_fail_shear_overdesign_hash,
)
from design_brain.families.bending_fail_shear_overdesign_governs.contract import (  # noqa: E402
    candidate_source_contract,
    ranking_criteria,
)
from design_brain.families.bending_fail_shear_overdesign_governs.runtime import (  # noqa: E402
    run_bending_fail_shear_overdesign_runtime,
)


FORBIDDEN_IMPORT_PREFIXES = {
    "inputs_page",
    "streamlit",
    "design_brain.families.bending_fail_governs",
    "design_brain.families.shear_overdesign_governs",
    "design_brain.publication",
    "design_brain.cta_contracts",
}
FORBIDDEN_SOURCE_TERMS = {"session_state", "button_contract", "publication", "apply_routing", "one_click"}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _inputs() -> BendingFailShearOverdesignInputs:
    return BendingFailShearOverdesignInputs(
        selected_family_id="BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        base_state={"D": 500.0, "b": 300.0, "s_lig": 150},
        bending_fail_candidates=(
            {"source_family_id": "BENDING_FAIL_GOVERNS", "candidate_id": "bend_repair", "updates": {"D": 550.0}},
        ),
        shear_overdesign_candidates=(
            {"source_family_id": "SHEAR_OVERDESIGN_GOVERNS", "candidate_id": "shear_cleanup", "updates": {"s_lig": 250}},
        ),
    )


def _eval(
    inputs: BendingFailShearOverdesignInputs,
    candidate: MixedMergedCandidate,
    *,
    force_reject: bool = False,
) -> MixedCandidateEvaluation:
    has_bending = candidate.has_mandatory_bending_source
    has_shear = candidate.has_opportunistic_shear_source
    valid = has_bending and not force_reject
    return MixedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=mixed_candidate_state_hash(inputs.base_state, candidate.updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.18,
        shear_utilisation_before=0.52,
        bending_utilisation_after=0.94 if has_bending else 1.08,
        shear_utilisation_after=0.82 if has_shear else 0.52,
        bending_repaired=has_bending and not force_reject,
        shear_compliant=not force_reject,
        shear_moves_toward_target=has_shear and not force_reject,
        creates_shear_underdesign=force_reject,
        code_compliance_status={"status": "PASS"},
        constructability_status={"status": "PASS"},
        reinforcement_quantity={"increase": 10.0 if has_shear else 20.0},
        beam_volume={"geometry_increase": 25.0 if has_bending else 0.0},
        cost_proxy={"after": 100.0 if has_shear else 120.0},
        engineering_status={"candidate_valid": valid},
    ).with_evaluation_hash()


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN Runtime Snapshot",
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
    imports = _imports(RUNTIME_PATH)
    source = RUNTIME_PATH.read_text(encoding="utf-8", errors="ignore").lower()
    forbidden_imports = [
        item for item in imports if any(item == prefix or item.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    ]
    forbidden_terms = sorted(term for term in FORBIDDEN_SOURCE_TERMS if term.lower() in source)
    inputs = _inputs()
    selected = run_bending_fail_shear_overdesign_runtime(inputs=inputs, evaluate_candidate=_eval)
    repeat = run_bending_fail_shear_overdesign_runtime(inputs=inputs, evaluate_candidate=_eval)

    def rejecting_evaluator(runtime_inputs: BendingFailShearOverdesignInputs, candidate: MixedMergedCandidate) -> MixedCandidateEvaluation:
        return _eval(runtime_inputs, candidate, force_reject=True)

    exhausted = run_bending_fail_shear_overdesign_runtime(inputs=inputs, evaluate_candidate=rejecting_evaluator)
    checks = {
        "allowed_sources_proven": set(candidate_source_contract().get("allowed_sources") or ())
        == {"BENDING_FAIL_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "APPROVED_MIXED_MERGE_RULE"},
        "runtime_uses_no_source_ladder_calls": not forbidden_imports and not forbidden_terms,
        "selected_candidate_repairs_bending": selected.selected_recommendation is not None
        and selected.selected_recommendation.get("bending_repaired") is True,
        "selected_candidate_maintains_shear": selected.selected_recommendation is not None
        and selected.selected_recommendation.get("shear_compliant") is True,
        "ranking_criteria_match_contract": tuple(selected.ranking_evidence.get("criteria") or ()) == tuple(ranking_criteria()),
        "bending_only_fallback_is_available": any(
            row.get("merge_rule_id") == "MANDATORY_BENDING_REPAIR_ONLY" for row in selected.mixed_merge_trace
        ),
        "shear_only_not_generated": all("BENDING_FAIL_GOVERNS" in row.get("source_family_ids", ()) for row in selected.mixed_merge_trace),
        "exhausted_requires_specific_blocker": exhausted.status == "EXHAUSTED" and bool(exhausted.exhausted_reason),
        "ownership_excludes_source_ladders": selected.ownership_proof.get("mixed_owns_bending_repair_ladder") is False
        and selected.ownership_proof.get("mixed_owns_shear_optimisation_ladder") is False,
        "runtime_hash_stable": selected.runtime_hash == repeat.runtime_hash,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_runtime_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "forbidden_imports": forbidden_imports,
        "forbidden_source_terms": forbidden_terms,
        "selected": selected.to_family_result_payload(),
        "exhausted": exhausted.to_family_result_payload(),
        "snapshot_hash": stable_bending_fail_shear_overdesign_hash(
            {
                "selected_hash": selected.runtime_hash,
                "exhausted_hash": exhausted.runtime_hash,
                "checks": checks,
            }
        ),
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("BENDING_FAIL_SHEAR_OVERDESIGN runtime snapshot FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_FAIL_SHEAR_OVERDESIGN runtime snapshot PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
