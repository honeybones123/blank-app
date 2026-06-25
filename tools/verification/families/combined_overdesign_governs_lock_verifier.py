"""Final lock verifier for COMBINED_OVERDESIGN_GOVERNS."""

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

from design_brain.families.bending_and_shear_overdesign_govern import (  # noqa: E402
    evaluate_bending_and_shear_overdesign_govern,
)
from design_brain.families.bending_and_shear_overdesign_govern.contract import (  # noqa: E402
    candidate_source_contract,
    contract_hash,
    family_identity,
    load_bending_and_shear_overdesign_govern_contract,
    ranking_criteria,
)
from design_brain.families.combined_cleanup import CombinedCleanupFamily  # noqa: E402


PROOF_CHAIN = [
    ("contract_check", "tools/verification/families/bending_and_shear_overdesign_govern_contract_check.py"),
    ("candidate_merge_boundary", "tools/verification/combined_overdesign_candidate_merge_boundary_snapshot.py"),
    ("source_interaction", "tools/verification/families/combined_overdesign_governs_source_interaction_snapshot.py"),
    ("runtime", "tools/verification/families/combined_overdesign_governs_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/combined_overdesign_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/combined_overdesign_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/combined_overdesign_governs_cutover_implementation.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
]


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def _sources() -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    return (
        (
            {
                "source_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "candidate_id": "bend_cleanup",
                "updates": {"bot1_count": 4, "db_bot_1": 20},
            },
        ),
        (
            {
                "source_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "candidate_id": "remove_links",
                "updates": {"lig_d": 0, "lig_legs": 0},
            },
        ),
    )


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_lock_verifier_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_OVERDESIGN_GOVERNS Lock Verifier",
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
    bending, shear = _sources()
    family = CombinedCleanupFamily()
    ladder = family.contracted_optimisation_ladder_specs(
        {"b": 300.0, "D": 500.0, "As": 2260.0, "As_min": 950.0, "Vstar": 0.0},
        bending_overdesign_candidates=bending,
        shear_overdesign_candidates=shear,
    )
    api_result = evaluate_bending_and_shear_overdesign_govern(
        {
            "state": {"b": 300.0, "D": 500.0, "As": 2260.0, "As_min": 950.0, "Vstar": 0.0},
            "bending_overdesign_candidates": bending,
            "shear_overdesign_candidates": shear,
        }
    )
    runtime_source = _read("design_brain/families/bending_and_shear_overdesign_govern/runtime.py")
    shell_source = _read("design_brain/families/combined_cleanup.py")
    inputs_source = _read("inputs_page.py")
    forbidden_runtime_terms = [
        term
        for term in (
            "inputs_page",
            "streamlit",
            "st.session_state",
            "session_state",
            "button_contract",
            "publication",
            "family_chooser",
            "run_bending_overdesign_governs_runtime",
            "run_shear_overdesign_governs_runtime",
            "contracted_optimisation_ladder_specs",
        )
        if term in runtime_source
    ]
    source_contract = candidate_source_contract()
    checks = {
        "proof_chain_pass": proof_chain_pass,
        "contract_loads": bool(load_bending_and_shear_overdesign_govern_contract()),
        "family_identity_locked": family_identity().get("family_id") == "COMBINED_OVERDESIGN_GOVERNS"
        and family_identity().get("runtime_family_id") == "COMBINED_OVERDESIGN",
        "contract_hash_present": bool(contract_hash()),
        "source_rules_lock_overdesign_sources": set(source_contract.get("allowed_sources") or [])
        == {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "APPROVED_COMBINED_MERGE_RULE"}
        and source_contract.get("must_not_duplicate_ladders") is True,
        "ranking_contract_present": tuple(ranking_criteria())
        == tuple((ladder.get("ranking_evidence") or {}).get("criteria") or ()),
        "family_shell_runtime_driven": ladder.get("contract_runtime_driven") is True
        and ladder.get("contract_runtime_authority") == "run_combined_overdesign_governs_runtime",
        "api_identifies_runtime_authority": api_result.lock_proof.get("runtime_authority")
        == "run_combined_overdesign_governs_runtime",
        "api_does_not_publish_or_generate_cta": api_result.publication == {} and api_result.cta_contract == {},
        "runtime_has_no_page_shared_or_source_ladder_calls": not forbidden_runtime_terms,
        "shell_does_not_call_source_runtimes": "run_bending_overdesign_governs_runtime" not in shell_source
        and "run_shear_overdesign_governs_runtime" not in shell_source,
        "inputs_page_still_owns_shared_surfaces": "record_design_guide_publication_snapshot" in inputs_source
        and "build_design_guide_apply_button_contract" in inputs_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    failed_chain = [entry["name"] for entry in proof_chain if not entry["passed"]]
    if failed_chain:
        failures.append(f"failed_proof_chain:{failed_chain}")
    if forbidden_runtime_terms:
        failures.append(f"forbidden_runtime_terms:{forbidden_runtime_terms}")
    snapshot = {
        "schema": "combined_overdesign_governs_lock_verifier.v1",
        "result": "PASS" if not failures else "FAIL",
        "lock_status": "COMBINED_OVERDESIGN_GOVERNS lock complete" if not failures else "COMBINED_OVERDESIGN_GOVERNS lock incomplete",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "family_ladder": {
            "runtime_hash": ladder.get("runtime_hash"),
            "spec_count": len(list(ladder.get("specs") or [])),
        },
        "api_lock_proof": dict(api_result.lock_proof),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_OVERDESIGN_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_OVERDESIGN_GOVERNS lock verifier PASS")
    print("COMBINED_OVERDESIGN_GOVERNS lock complete")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
