"""Final lock verifier for COMBINED_BENDING_SHEAR_FAIL_GOVERNS."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.combined_bending_shear_candidate_merge import CombinedBendingShearFailInputs  # noqa: E402
from design_brain.families.bending_and_shear_fail_govern.contract import (  # noqa: E402
    candidate_source_contract,
    contract_hash,
    family_identity,
    load_bending_and_shear_fail_govern_contract,
    ranking_criteria,
)
from design_brain.families.bending_and_shear_fail_govern import run_combined_bending_shear_fail_runtime  # noqa: E402
from design_brain.families.combined_bending_shear_fail import CombinedBendingShearFailFamily  # noqa: E402
from design_brain.families.combined_bending_shear_fail import _default_runtime_evaluator  # noqa: E402


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _read_inputs_composition_surface() -> str:
    return "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_page_route_coordinators.py",
            "inputs_page_app_contract_bridge.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
        )
    )


PROOF_CHAIN = [
    ("contract_check", "tools/verification/families/bending_and_shear_fail_govern_contract_check.py"),
    ("candidate_merge_boundary", "tools/verification/combined_bending_shear_candidate_merge_boundary_snapshot.py"),
    ("source_rules", "tools/verification/families/combined_bending_shear_fail_governs_source_rules_snapshot.py"),
    ("partial_repair", "tools/verification/families/combined_bending_shear_fail_governs_partial_repair_snapshot.py"),
    ("geometry_interaction", "tools/verification/families/combined_bending_shear_fail_governs_geometry_interaction_snapshot.py"),
    ("reinforcement_interaction", "tools/verification/families/combined_bending_shear_fail_governs_reinforcement_interaction_snapshot.py"),
    ("terminal", "tools/verification/families/combined_bending_shear_fail_governs_terminal_snapshot.py"),
    ("runtime", "tools/verification/families/combined_bending_shear_fail_governs_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/combined_bending_shear_fail_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/combined_bending_shear_fail_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/combined_bending_shear_fail_governs_cutover_implementation.py"),
    ("publication_regression", "tools/verification/families/combined_bending_shear_fail_publication_regression.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
]


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, script], cwd=ROOT, text=True, capture_output=True, timeout=300)
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def _source_candidates() -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    return (
        ({"source_family_id": "BENDING_FAIL_GOVERNS", "candidate_id": "bend_depth", "updates": {"D": 550.0}},),
        ({"source_family_id": "SHEAR_FAIL_GOVERNS", "candidate_id": "shear_links", "updates": {"lig_d": 12}},),
    )


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_governs_lock_verifier_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_BENDING_SHEAR_FAIL_GOVERNS Lock Verifier",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Proof Chain",
                "",
                *[f"- `{entry['name']}`: `{entry['passed']}`" for entry in snapshot["proof_chain"]],
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
    proof_chain = [{"name": name, **_run(script)} for name, script in PROOF_CHAIN]
    proof_chain_pass = all(entry["passed"] for entry in proof_chain)
    bending, shear = _source_candidates()
    family = CombinedBendingShearFailFamily()
    ladder = family.contracted_repair_ladder_specs(
        {"selected_family_id": "COMBINED_BENDING_SHEAR_FAIL"},
        bending_fail_candidates=bending,
        shear_fail_candidates=shear,
    )
    runtime_result = run_combined_bending_shear_fail_runtime(
        inputs=CombinedBendingShearFailInputs(
            selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
            base_state={"selected_family_id": "COMBINED_BENDING_SHEAR_FAIL"},
            geometry={},
            reinforcement={},
            material_properties={},
            actions={},
            constraints={},
            bending_fail_candidates=bending,
            shear_fail_candidates=shear,
            approved_combined_merge_candidates=(),
        ),
        evaluate_candidate=_default_runtime_evaluator,
    )
    runtime_source = (ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "runtime.py").read_text(encoding="utf-8", errors="replace")
    family_source = (ROOT / "design_brain" / "families" / "combined_bending_shear_fail.py").read_text(encoding="utf-8", errors="replace")
    inputs_source = _read_inputs_composition_surface()
    shared_source = _read("design_brain/publication.py")
    forbidden_runtime_terms = [
        term
        for term in ("inputs_page", "streamlit", "st.session_state", "family_chooser", "DEFAULT_DEPTH_STEPS_MM", "DEFAULT_WIDTH_STEPS_MM")
        if term in runtime_source
    ]
    source_contract = candidate_source_contract()
    checks = {
        "proof_chain_pass": proof_chain_pass,
        "contract_loads": bool(load_bending_and_shear_fail_govern_contract()),
        "family_identity_locked": family_identity().get("family_id") == "COMBINED_BENDING_SHEAR_FAIL_GOVERNS"
        and family_identity().get("runtime_family_id") == "COMBINED_BENDING_SHEAR_FAIL",
        "contract_hash_present": bool(contract_hash()),
        "runtime_authority": ladder.get("contract_runtime_authority") == "run_combined_bending_shear_fail_runtime",
        "family_shell_runtime_driven": ladder.get("contract_runtime_driven") is True,
        "package_runtime_export_matches_family_shell": runtime_result.runtime_hash == ladder.get("runtime_hash"),
        "source_rules_locked": set(source_contract.get("allowed_sources") or [])
        == {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"}
        and source_contract.get("must_not_duplicate_ladders") is True,
        "ranking_contract_locked": tuple(ranking_criteria())
        == tuple((ladder.get("ranking_evidence") or {}).get("criteria") or ()),
        "legacy_internal_ladder_removed": "DEFAULT_DEPTH_STEPS_MM" not in family_source
        and "DEFAULT_WIDTH_STEPS_MM" not in family_source,
        "runtime_has_no_page_chooser_or_ladder_imports": not forbidden_runtime_terms,
        "shared_surfaces_remain_outside": "combined_fail_contract_ladder" in inputs_source
        and "_route_combined_fail_family_publication" in shared_source
        and "shared_system_owned_outside_family" in family_source,
        "no_locked_source_family_files_touched_by_runtime": "from design_brain.families.bending_fail" not in runtime_source
        and "from design_brain.families.shear_fail" not in runtime_source
        and "run_bending_fail_governs" not in runtime_source
        and "run_shear_fail_governs" not in runtime_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    failed_chain = [entry for entry in proof_chain if not entry["passed"]]
    if failed_chain:
        failures.append(f"failed_proof_chain:{[entry['name'] for entry in failed_chain]}")
    if forbidden_runtime_terms:
        failures.append(f"forbidden_runtime_terms:{forbidden_runtime_terms}")
    snapshot = {
        "schema": "combined_bending_shear_fail_governs_lock_verifier.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "family_ladder": {
            "runtime_hash": ladder.get("runtime_hash"),
            "spec_count": len(list(ladder.get("specs") or [])),
        },
        "runtime_result": runtime_result.to_dict(),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS lock verifier PASS")
    print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS lock complete")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
