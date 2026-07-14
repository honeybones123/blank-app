"""Final lock verifier for BENDING_OVERDESIGN_GOVERNS."""

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

from design_brain.bending_overdesign_candidate_evaluation import (  # noqa: E402
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    build_bending_overdesign_candidate_state_hash,
)
from design_brain.families.bending_cleanup import BendingCleanupFamily  # noqa: E402
from design_brain.families.bending_overdesign_governs import evaluate_bending_overdesign_governs  # noqa: E402
from design_brain.families.bending_overdesign_governs.contract import (  # noqa: E402
    family_identity,
    geometry_rules,
    lane_proof_policies,
    load_bending_overdesign_governs_contract,
    minimum_reinforcement_geometry_relief_rules,
    minimum_reinforcement_rules,
    ranking_criteria,
)
from design_brain.families.bending_overdesign_governs.runtime import (  # noqa: E402
    bending_overdesign_contract_lane_order,
    run_bending_overdesign_governs_runtime,
)


PROOF_CHAIN = [
    ("contract_check", "tools/verification/families/bending_overdesign_governs_contract_check.py"),
    ("candidate_boundary", "tools/verification/bending_overdesign_candidate_evaluation_boundary_snapshot.py"),
    ("bottom_reinforcement_lane", "tools/verification/families/bending_overdesign_governs_bottom_reinforcement_lane_snapshot.py"),
    ("layer_reduction_lane", "tools/verification/families/bending_overdesign_governs_layer_reduction_lane_snapshot.py"),
    ("width_reduction_lane", "tools/verification/families/bending_overdesign_governs_width_reduction_lane_snapshot.py"),
    ("depth_reduction_lane", "tools/verification/families/bending_overdesign_governs_depth_reduction_lane_snapshot.py"),
    ("minimum_reinforcement_lane", "tools/verification/families/bending_overdesign_governs_minimum_reinforcement_lane_snapshot.py"),
    ("geometry_compliance_lane", "tools/verification/families/bending_overdesign_governs_geometry_compliance_lane_snapshot.py"),
    ("terminal_lane", "tools/verification/families/bending_overdesign_governs_terminal_lane_snapshot.py"),
    ("runtime", "tools/verification/families/bending_overdesign_governs_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/bending_overdesign_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/bending_overdesign_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/bending_overdesign_governs_cutover_implementation.py"),
    ("publication_regression", "tools/verification/families/bending_overdesign_governs_publication_regression.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
]

EXPECTED_ORDER = (
    "BOTTOM_REINFORCEMENT_REDUCTION",
    "LAYER_REDUCTION",
    "WIDTH_REDUCTION",
    "DEPTH_REDUCTION",
    "EXACT_STOP",
    "EXHAUSTED",
)
FORBIDDEN_RUNTIME_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "publication",
    "button_contract",
    "visible_wording",
}


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 500.0,
        "Mstar": 220.0,
        "phiMu": 330.0,
        "bending_utilisation": 0.67,
        "As": 2260.0,
        "As_min": 950.0,
        "bot1_count": 5,
        "db_bot_1": 24,
        "bot_row_count": 1,
    }


def _evaluation(
    candidate_input: BendingOverdesignCandidateInput,
    candidate_update: BendingOverdesignCandidateUpdate,
) -> BendingOverdesignCandidateEvaluation:
    updates = dict(candidate_update.updates)
    bot_count = int(updates.get("bot1_count") or updates.get("bot_row_1_bars") or 0)
    bot_dia = int(updates.get("db_bot_1") or updates.get("bot_row_1_dia") or 0)
    if updates.get("b") == 275.0 and bot_count == 4 and bot_dia == 20:
        utilisation, as_after, compliant, cost = 0.82, 1256.0, True, 0.58
    elif updates.get("b") == 275.0 and updates.get("bot_row_count") == 1 and updates.get("bot2_count") == 0:
        utilisation, as_after, compliant, cost = 0.81, 1608.0, True, 0.68
    elif bot_count == 4 and bot_dia == 20 and "b" not in updates and "D" not in updates:
        utilisation, as_after, compliant, cost = 0.96, 1256.0, True, 0.61
    elif bot_count == 3 and bot_dia == 20 and "b" not in updates and "D" not in updates:
        utilisation, as_after, compliant, cost = 1.04, 942.0, False, 0.48
    elif updates.get("bot_row_count") == 1 and updates.get("bot2_count") == 0:
        utilisation, as_after, compliant, cost = 0.90, 1608.0, True, 0.72
    elif updates.get("b") == 275.0:
        utilisation, as_after, compliant, cost = 0.88, 2260.0, True, 0.94
    elif updates.get("D") == 475.0:
        utilisation, as_after, compliant, cost = 0.93, 2260.0, True, 0.95
    else:
        utilisation, as_after, compliant, cost = 0.86, 1809.6, True, 0.82
    as_min = float(candidate_input.base_state.get("As_min") or 0.0)
    beam_width = float(updates.get("b") or candidate_input.base_state.get("b") or 300.0)
    beam_depth = float(updates.get("D") or candidate_input.base_state.get("D") or 500.0)
    valid = compliant and as_after >= as_min
    return BendingOverdesignCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_bending_overdesign_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        bending_utilisation=utilisation,
        previous_bending_utilisation=0.67,
        target_band_status={"inside_target_band": 0.85 <= utilisation <= 1.0},
        utilisation_moves_toward_target=utilisation > 0.67 and utilisation <= 1.0,
        bending_remains_compliant=compliant,
        constructability_status={"status": "PASS"},
        code_compliance_status={"status": "PASS" if valid else "FAIL"},
        minimum_reinforcement_status={
            "As": as_after,
            "As_min": as_min,
            "As_greater_than_or_equal_to_As_min": as_after >= as_min,
            "discard_before_ranking": as_after < as_min,
        },
        geometry_compliance_status={"status": "PASS"},
        beam_proportion_status={"status": "PASS"},
        reinforcement_quantity={"after": as_after},
        beam_volume={"after": beam_width * beam_depth},
        cost_proxy={"after": cost},
        capacity_summary={"fixture": "lock_verifier"},
        failure_flags={"underdesign_created": not compliant, "below_minimum_reinforcement": as_after < as_min},
        engineering_status={"candidate_valid": valid, "result": "ACCEPTED" if valid else "REJECTED"},
    ).with_evaluation_hash()


def _run_script(script: str) -> dict[str, Any]:
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


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_overdesign_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_governs_lock_verifier_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_OVERDESIGN_GOVERNS Lock Verifier",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Proof Chain",
                "",
                *[
                    f"- `{entry['name']}`: `{entry['passed']}`"
                    for entry in snapshot["proof_chain"]
                ],
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
    proof_chain = [{"name": name, **_run_script(script)} for name, script in PROOF_CHAIN]
    proof_chain_pass = all(entry["passed"] for entry in proof_chain)
    result = run_bending_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    repeat = run_bending_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    family = BendingCleanupFamily()
    ladder = family.contracted_optimisation_ladder_specs(_base_state())
    api_result = evaluate_bending_overdesign_governs({"state": _base_state()})
    runtime_source = (ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    package_source = (ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "__init__.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    cleanup_source = (ROOT / "design_brain" / "families" / "bending_cleanup.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="replace")
    forbidden_runtime_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    all_updates = [
        dict(spec.get("updates") or {})
        for spec in list(ladder.get("specs") or [])
        if isinstance(spec, dict)
    ]
    checks = {
        "proof_chain_pass": proof_chain_pass,
        "contract_loads": bool(load_bending_overdesign_governs_contract()),
        "family_id": family_identity().get("family_id") == "BENDING_OVERDESIGN_GOVERNS",
        "contract_lane_order_exact": bending_overdesign_contract_lane_order() == EXPECTED_ORDER,
        "runtime_reads_contract_order": tuple(result.repair_reason_proof.get("contract_lane_order") or ())
        == EXPECTED_ORDER,
        "runtime_hash_stable": result.ladder_hash == repeat.ladder_hash,
        "minimum_reinforcement_boundary_protected": minimum_reinforcement_rules().get("hard_boundary") is True
        and result.minimum_reinforcement_proof.get("below_minimum_rejection_count", 0) >= 1
        and result.minimum_reinforcement_proof.get("below_minimum_candidates_ranked") is False,
        "minimum_reinforcement_width_relief_contract_backed": bool(minimum_reinforcement_geometry_relief_rules())
        and (lane_proof_policies().get("width_reduction") or {}).get("minimum_reinforcement_relief") is True,
        "minimum_reinforcement_width_relief_runtime_proven": result.minimum_reinforcement_proof.get(
            "minimum_reinforcement_geometry_relief_checked"
        )
        is True
        and result.restart_proof.get("width_reduction_restarted_reinforcement_candidate_count", 0) >= 2
        and result.geometry_compliance_proof.get("width_plus_reinforcement_restart_candidate_count", 0) >= 2,
        "controlled_geometry_reduction_protected": geometry_rules().get("geometry_reduction_allowed") is True
        and result.geometry_compliance_proof.get("width_increment_mm") == -25
        and result.geometry_compliance_proof.get("depth_increment_mm") == -25
        and result.restart_proof.get("all_geometry_reductions_restart_bottom_reinforcement_search") is True
        and result.restart_proof.get("all_geometry_reductions_restart_layer_search") is True,
        "ranking_contract_proven": tuple(ranking_criteria()) == tuple(result.ranking_proof.get("criteria") or ()),
        "lane_policies_present": bool(lane_proof_policies()),
        "family_shell_runtime_driven": ladder.get("contract_runtime_driven") is True
        and ladder.get("contract_runtime_authority") == "run_bending_overdesign_governs_runtime",
        "api_identifies_runtime_authority": api_result.lock_proof.get("runtime_authority")
        == "run_bending_overdesign_governs_runtime",
        "runtime_has_no_page_ui_imports": not forbidden_runtime_terms,
        "shared_systems_remain_shared": "from design_brain.cta_contracts import" in inputs_source
        and "from design_brain.publication import" in inputs_source
        and "build_design_guide_apply_button_contract" in inputs_source
        and api_result.publication == {}
        and api_result.cta_contract == {},
        "contract_updates_cover_reinforcement_and_geometry": any(
            ({"bot1_count", "db_bot_1"} <= set(update) or {"bot_row_1_bars", "bot_row_1_dia"} <= set(update))
            and ({"b", "bw"} & set(update) or "D" in update)
            for update in all_updates
        ),
        "contract_updates_cover_width_plus_reinforcement_relief": any(
            {"b", "bot1_count", "db_bot_1"} <= set(update)
            or {"b", "bot_row_1_bars", "bot_row_1_dia"} <= set(update)
            for update in all_updates
        ),
        "no_other_locked_family_coupling": "bending_fail_governs" not in runtime_source
        and "BENDING_FAIL_GOVERNS" not in runtime_source
        and "shear_fail_governs" not in runtime_source
        and "shear_overdesign_governs" not in runtime_source
        and "bending_fail_governs" not in package_source
        and "shear_fail_governs" not in package_source
        and "shear_overdesign_governs" not in package_source
        and "bending_fail_governs" not in cleanup_source
        and "shear_fail_governs" not in cleanup_source
        and "shear_overdesign_governs" not in cleanup_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if forbidden_runtime_terms:
        failures.append(f"forbidden_runtime_terms:{forbidden_runtime_terms}")
    failed_chain = [entry for entry in proof_chain if not entry["passed"]]
    if failed_chain:
        failures.append(f"failed_proof_chain:{[entry['name'] for entry in failed_chain]}")
    snapshot = {
        "schema": "bending_overdesign_governs_lock_verifier.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "contract_lane_order": list(bending_overdesign_contract_lane_order()),
        "runtime": {
            "selected_strategy_lane": result.selected_strategy_lane,
            "ladder_hash": result.ladder_hash,
            "repeat_ladder_hash": repeat.ladder_hash,
            "candidate_count": len(result.candidate_repairs),
        },
        "family_ladder": {
            "contract_runtime_driven": ladder.get("contract_runtime_driven"),
            "ladder_hash": ladder.get("ladder_hash"),
            "spec_count": len(list(ladder.get("specs") or [])),
        },
        "api_lock_proof": dict(api_result.lock_proof),
        "scope_limits": {
            "moves_publication": False,
            "moves_cta": False,
            "moves_apply_routing": False,
            "moves_ui_session_debug": False,
            "allows_controlled_geometry_reduction": True,
            "touches_bending_fail": False,
            "touches_shear": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("BENDING_OVERDESIGN_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_OVERDESIGN_GOVERNS lock verifier PASS")
    print("BENDING_OVERDESIGN_GOVERNS lock complete")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
