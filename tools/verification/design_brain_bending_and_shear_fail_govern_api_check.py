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
PACKAGE_INIT = ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "__init__.py"


def _source_contains(path: Path, needle: str) -> bool:
    return needle in path.read_text(encoding="utf-8", errors="replace")


def _line_hits(path: Path, needle: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if needle in line:
            hits.append({"line": idx, "text": line.strip()[:240]})
    return hits


def main() -> int:
    failures: list[str] = []
    if not PACKAGE_INIT.exists():
        failures.append("missing_bending_and_shear_fail_govern_package_init")

    source = PACKAGE_INIT.read_text(encoding="utf-8", errors="replace") if PACKAGE_INIT.exists() else ""
    if "inputs_page" in source:
        failures.append("bending_and_shear_fail_govern_imports_inputs_page")
    if "def evaluate_bending_and_shear_fail_govern" in source:
        failures.append("legacy_wrapper_still_present")
    if "run_combined_bending_shear_fail_runtime" not in source:
        failures.append("missing_runtime_export")

    engine_hits = _line_hits(ROOT / "design_brain" / "engine.py", "evaluate_bending_and_shear_fail_govern")
    inputs_hits = _line_hits(ROOT / "inputs_page.py", "evaluate_bending_and_shear_fail_govern")
    if engine_hits:
        failures.append("engine_calls_new_bending_and_shear_fail_govern_api")
    if inputs_hits:
        failures.append("inputs_page_calls_new_bending_and_shear_fail_govern_api")

    result_summary: dict[str, Any] = {}
    if not failures:
        from design_brain.combined_bending_shear_candidate_merge import (
            CombinedBendingShearFailInputs,
            CombinedCandidateEvaluation,
        )
        from design_brain.families.bending_and_shear_fail_govern import (
            FAMILY_ID,
            RUNTIME_FAMILY_ID,
            run_combined_bending_shear_fail_runtime,
        )

        def _evaluation(
            inputs: CombinedBendingShearFailInputs,
            _candidate: Any,
        ) -> CombinedCandidateEvaluation:
            return CombinedCandidateEvaluation(
                input_hash=inputs.input_hash,
                update_hash="synthetic-update",
                candidate_state_hash="synthetic-state",
                source_family_ids=("BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"),
                source_candidates=("bend", "shear"),
                bending_utilisation_before=1.12,
                shear_utilisation_before=1.18,
                bending_utilisation_after=0.93,
                shear_utilisation_after=0.91,
                bending_improves=True,
                shear_improves=True,
                bending_compliant=True,
                shear_compliant=True,
                bending_inside_target_band=True,
                shear_inside_target_band=True,
                both_failures_repaired=True,
                geometry_interaction_status={"rechecked": ["bending", "shear"]},
                reinforcement_interaction_status={"bending_reinforcement_rechecked": True, "shear_reinforcement_rechecked": True},
                code_compliance_status={"status": "PASS"},
                detailing_status={"status": "PASS"},
                constructability_status={"status": "PASS"},
                geometry_increase={"total_mm": 25.0},
                reinforcement_increase={"total": 2.0},
                cost_proxy={"after": 1.0},
                rejection_reasons=(),
                engineering_status={"candidate_valid": True},
            ).with_evaluation_hash()

        result = run_combined_bending_shear_fail_runtime(
            inputs=CombinedBendingShearFailInputs(
                selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
                base_state={},
                geometry={},
                reinforcement={},
                material_properties={},
                actions={},
                constraints={},
                bending_fail_candidates=(
                    {"source_family_id": "BENDING_FAIL_GOVERNS", "candidate_id": "bend", "updates": {"D": 420.0}},
                ),
                shear_fail_candidates=(
                    {"source_family_id": "SHEAR_FAIL_GOVERNS", "candidate_id": "shear", "updates": {"lig_d": 12}},
                ),
                approved_combined_merge_candidates=(),
            ),
            evaluate_candidate=_evaluation,
        )
        result_summary = {
            "family_id": FAMILY_ID,
            "runtime_family_id": RUNTIME_FAMILY_ID,
            "status": result.status,
            "selected_strategy_lane": result.selected_strategy_lane,
            "candidate_count": len(result.candidate_repairs),
            "selected_recommendation_present": isinstance(result.selected_recommendation, dict),
            "runtime_hash": result.runtime_hash,
            "contract_hash": result.contract_hash,
        }
        if result_summary.get("family_id") != "COMBINED_BENDING_SHEAR_FAIL_GOVERNS":
            failures.append("family_id_mismatch")
        if result_summary.get("runtime_family_id") != "COMBINED_BENDING_SHEAR_FAIL":
            failures.append("legacy_runtime_family_id_mismatch")
        if result_summary.get("status") != "EXACT_STOP":
            failures.append("synthetic_runtime_context_not_exact_stop")

    status = "PASS" if not failures else "FAIL"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    output = {
        "schema": "design_brain_bending_and_shear_fail_govern_api_check.v2",
        "status": status,
        "package": str(PACKAGE_INIT.relative_to(ROOT)),
        "imports_inputs_page": _source_contains(PACKAGE_INIT, "inputs_page") if PACKAGE_INIT.exists() else None,
        "engine_call_hits": engine_hits,
        "inputs_page_call_hits": inputs_hits,
        "api_result_summary": result_summary,
        "failures": failures,
    }
    output_path = ARTIFACT_DIR / f"design_brain_bending_and_shear_fail_govern_api_check_{stamp}.json"
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    report_path = AUDIT_DIR / f"design_brain_bending_and_shear_fail_govern_api_check_{stamp}.md"
    report_lines = [
        "# Design Brain BENDING_AND_SHEAR_FAIL_GOVERN Runtime Export Check",
        "",
        f"Status: {status}",
        "",
        "## Result Summary",
        "",
        f"- family_id: `{result_summary.get('family_id')}`",
        f"- runtime_family_id: `{result_summary.get('runtime_family_id')}`",
        f"- selected_strategy_lane: `{result_summary.get('selected_strategy_lane')}`",
        f"- candidate_count: `{result_summary.get('candidate_count')}`",
        f"- runtime_hash: `{result_summary.get('runtime_hash')}`",
        "",
        "## Failures",
        "",
    ]
    report_lines.extend([f"- {failure}" for failure in failures] or ["- none"])
    report_lines.extend(["", "## Output", "", f"- `{output_path}`"])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"{status}: {output_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
