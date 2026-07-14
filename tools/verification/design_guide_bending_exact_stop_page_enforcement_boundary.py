from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write_artifacts(payload: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_bending_exact_stop_page_enforcement_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_exact_stop_page_enforcement_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Design Guide bending exact-stop page enforcement boundary",
        "",
        f"Result: {'PASS' if payload['passed'] else 'FAIL'}",
        "",
        "## Checks",
    ]
    for name, value in payload["checks"].items():
        report.append(f"- {name}: {'PASS' if value else 'FAIL'}")
    report.extend(
        [
            "",
            "## Boundary",
            "- Design Brain owns exact-stop proof-chain construction.",
            "- inputs_page.py may pass evaluator callbacks and render/stamp returned proof fields.",
            "- inputs_page.py must not reconstruct reo-first, As_min relief, width/depth relief, or restart-after-geometry proof logic.",
        ]
    )
    if payload.get("violations"):
        report.extend(["", "## Violations"])
        report.extend(f"- {violation}" for violation in payload["violations"])
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    inputs_source = _read("inputs_page.py")
    proof_source = _read("design_brain/families/bending_overdesign_governs/exact_stop.py")

    forbidden_inputs_patterns = {
        "page_local_builder_definition": "def _build_bending_cleanup_exact_stop_contract_proof(",
        "page_local_reo_first_decision": "reo_attempted_first =",
        "page_local_every_path_exhaustion_decision": "every_valid_cleanup_path_exhausted =",
        "page_local_lighter_as_min_decision": "lighter_trials_blocked_only_by_as_min =",
        "page_local_width_relief_requirement": "width_relief_required =",
        "page_local_depth_relief_requirement": "depth_relief_required =",
        "page_local_trial_loop": "for index, updates in enumerate(list(update_trials",
        "page_local_selected_pack_eval": "selected_pack = _evaluate_bending_with_bottom_state",
    }
    violations = [
        f"{name}: {pattern}"
        for name, pattern in forbidden_inputs_patterns.items()
        if pattern in inputs_source
    ]

    checks = {
        "design_brain_proof_module_exists": bool(proof_source),
        "design_brain_builder_defined": "def build_bending_cleanup_exact_stop_contract_proof(" in proof_source,
        "design_brain_builder_has_reo_first_rule": "reo_attempted_first =" in proof_source,
        "design_brain_builder_has_width_depth_relief_rules": (
            "width_relief_required =" in proof_source and "depth_relief_required =" in proof_source
        ),
        "design_brain_builder_has_restart_after_geometry_rules": (
            "width_restart_bottom_count" in proof_source and "depth_restart_bottom_count" in proof_source
        ),
        "design_brain_module_does_not_import_inputs_page": "inputs_page" not in proof_source,
        "design_brain_module_does_not_import_streamlit": "streamlit" not in proof_source and "st." not in proof_source,
        "inputs_page_imports_design_brain_builder": (
            "from design_brain.families.bending_overdesign_governs.exact_stop import" in inputs_source
            and "build_bending_cleanup_exact_stop_contract_proof as _build_bending_cleanup_exact_stop_contract_proof"
            in inputs_source
        ),
        "inputs_page_passes_existing_evaluator_callbacks": (
            "evaluate_bending_with_bottom_state=_evaluate_bending_with_bottom_state" in inputs_source
            and "candidate_bottom_updates=_candidate_bottom_updates" in inputs_source
        ),
        "inputs_page_has_no_page_local_exact_stop_proof_construction": not violations,
    }
    payload = {
        "schema": "design_guide_bending_exact_stop_page_enforcement_boundary.v1",
        "passed": all(checks.values()),
        "checks": checks,
        "violations": violations,
        "owned_by_design_brain": {
            "proof_builder": "design_brain/families/bending_overdesign_governs/exact_stop.py",
            "contract": "design_brain/families/bending_overdesign_governs/contract.json",
        },
        "page_role": "inputs_page.py passes evaluator callbacks and consumes returned proof fields only",
    }
    json_path, report_path = _write_artifacts(payload)
    print(("PASS" if payload["passed"] else "FAIL") + f": {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
