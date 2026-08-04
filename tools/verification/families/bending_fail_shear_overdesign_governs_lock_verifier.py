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

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.families.registry import family_strategy_for  # noqa: E402
from design_brain.families.bending_fail_shear_overdesign_governs import (  # noqa: E402
    evaluate_bending_fail_shear_overdesign_governs,
)
from design_brain.families.bending_fail_shear_overdesign_governs.contract import (  # noqa: E402
    candidate_source_contract,
    contract_hash,
    family_identity,
    load_bending_fail_shear_overdesign_governs_contract,
    priority_contract,
    ranking_criteria,
)
from design_brain.families.bending_fail_shear_overdesign_governs.runtime import (  # noqa: E402
    run_bending_fail_shear_overdesign_runtime,
)


PROOF_CHAIN = (
    ("contract_check", "tools/verification/families/bending_fail_shear_overdesign_governs_contract_check.py"),
    ("candidate_merge_boundary", "tools/verification/bending_fail_shear_overdesign_candidate_merge_boundary_snapshot.py"),
    ("source_priority", "tools/verification/families/bending_fail_shear_overdesign_governs_source_priority_snapshot.py"),
    ("runtime_snapshot", "tools/verification/families/bending_fail_shear_overdesign_governs_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/bending_fail_shear_overdesign_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/bending_fail_shear_overdesign_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/bending_fail_shear_overdesign_governs_cutover_implementation.py"),
    ("publication_regression", "tools/verification/families/bending_fail_shear_overdesign_governs_publication_regression.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _read_inputs_composition_surface() -> str:
    retired = (
        "inputs_page_route_coordinators.py",
        "inputs_page_app_contract_bridge.py",
    )
    if any((ROOT / path).exists() for path in retired):
        raise AssertionError("retired Inputs composition bridges must remain absent")
    return "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_application/candidate_full_evaluation.py",
            "inputs_application/page_runtime/design_guide.py",
            "inputs_application/page_runtime/design_guide_runtime_support.py",
            "inputs_page_modules/guidance_compute.py",
            "inputs_page_modules/apply_routing.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
        )
    )


def _run(script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": str(completed.stdout or "")[-1000:],
        "stderr_tail": str(completed.stderr or "")[-1000:],
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_shear_overdesign_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_shear_overdesign_governs_lock_verifier_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS Lock Verifier",
                "",
                f"Result: `{snapshot['result']}`",
                f"Lock status: `{snapshot['lock_status']}`",
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
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    proof_chain = [{"name": name, **_run(script)} for name, script in PROOF_CHAIN]
    chooser = classify_family_from_raw_flags(
        {
            "bending_fail": True,
            "shear_fail": False,
            "shear_overdesigned": True,
            "legal_repair_exists": True,
        }
    )
    strategy = family_strategy_for("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS")
    api_result = evaluate_bending_fail_shear_overdesign_governs(
        {
            "bending_fail_candidates": (
                {"source_family_id": "BENDING_FAIL_GOVERNS", "candidate_id": "bend_repair", "updates": {"D": 550.0}},
            ),
            "shear_overdesign_candidates": (
                {"source_family_id": "SHEAR_OVERDESIGN_GOVERNS", "candidate_id": "shear_cleanup", "updates": {"s_lig": 250}},
            ),
        }
    )
    runtime_source = _read("design_brain/families/bending_fail_shear_overdesign_governs/runtime.py")
    inputs_source = _read_inputs_composition_surface()
    checks = {
        "proof_chain_pass": all(entry["passed"] for entry in proof_chain),
        "contract_loads": bool(load_bending_fail_shear_overdesign_governs_contract()),
        "contract_family_id": family_identity().get("family_id") == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "contract_hash_present": bool(contract_hash()),
        "candidate_sources_lock_mandatory_and_opportunistic": candidate_source_contract().get("mandatory_source") == "BENDING_FAIL_GOVERNS"
        and candidate_source_contract().get("opportunistic_source") == "SHEAR_OVERDESIGN_GOVERNS",
        "priority_contract_locked": priority_contract().get("mandatory_objective") == "bending repair"
        and priority_contract().get("opportunistic_objective") == "shear optimisation",
        "ranking_bending_first": tuple(ranking_criteria())[:2] == ("repairs bending failure", "maintains shear compliance"),
        "chooser_selects_family": chooser.get("selected_family_id") == "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "registry_reaches_family_shell": type(strategy).__name__ == "BendingFailShearOverdesignFamily",
        "api_identifies_runtime": api_result.evidence.get("contract_runtime_authority") == "run_bending_fail_shear_overdesign_runtime"
        and api_result.lock_proof.get("runtime_authority") == "run_bending_fail_shear_overdesign_runtime",
        "runtime_available": callable(run_bending_fail_shear_overdesign_runtime),
        "runtime_does_not_call_source_ladders": "run_bending_fail_governs_ladder_runtime" not in runtime_source
        and "run_shear_overdesign_governs_runtime" not in runtime_source,
        "runtime_has_no_shared_app_ownership": all(
            term not in runtime_source
            for term in ("inputs_page", "streamlit", "button_contract", "publication", "apply_routing", "one_click")
        ),
        "api_does_not_publish_or_generate_cta": api_result.publication == {} and api_result.cta_contract == {},
        "inputs_page_still_owns_shared_surfaces": "from design_brain.final_publication import" in inputs_source
        and "build_final_design_guide_publication" in inputs_source
        and "handle_inputs_apply_buttons" in inputs_source,
        "retired_inputs_bridges_absent": not (ROOT / "inputs_page_route_coordinators.py").exists()
        and not (ROOT / "inputs_page_app_contract_bridge.py").exists(),
    }
    failures = [key for key, passed in checks.items() if not passed]
    failed_chain = [entry["name"] for entry in proof_chain if not entry["passed"]]
    if failed_chain:
        failures.append(f"failed_proof_chain:{failed_chain}")
    snapshot = {
        "schema": "bending_fail_shear_overdesign_governs_lock_verifier.v1",
        "result": "PASS" if not failures else "FAIL",
        "lock_status": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS lock complete" if not failures else "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS lock incomplete",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "chooser": chooser,
        "api_lock_proof": dict(api_result.lock_proof),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS lock verifier PASS")
    print("BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS lock complete")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
