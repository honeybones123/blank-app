"""Final lock verifier for SHEAR_OVERDESIGN_GOVERNS."""

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

from design_brain.families.shear_cleanup import ShearCleanupFamily, _default_runtime_evaluator  # noqa: E402
from design_brain.families.shear_overdesign_governs.contract import (  # noqa: E402
    family_identity,
    geometry_restrictions,
    lane_proof_policies,
    load_shear_overdesign_governs_contract,
    ranking_criteria,
    zero_shear_override,
)
from design_brain.families.shear_overdesign_governs.runtime import (  # noqa: E402
    run_shear_overdesign_governs_runtime,
    shear_overdesign_contract_lane_order,
)
from design_brain.shear_overdesign_candidate_evaluation import (  # noqa: E402
    ShearOverdesignCandidateEvaluation,
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
    build_shear_overdesign_candidate_state_hash,
)


PROOF_CHAIN = [
    ("contract_check", "tools/verification/families/shear_overdesign_governs_contract_check.py"),
    ("candidate_boundary", "tools/verification/shear_overdesign_candidate_evaluation_boundary_snapshot.py"),
    ("spacing_lane", "tools/verification/families/shear_overdesign_governs_spacing_lane_snapshot.py"),
    ("bar_size_lane", "tools/verification/families/shear_overdesign_governs_bar_size_lane_snapshot.py"),
    ("leg_count_lane", "tools/verification/families/shear_overdesign_governs_leg_count_lane_snapshot.py"),
    ("ligature_removal_lane", "tools/verification/families/shear_overdesign_governs_ligature_removal_lane_snapshot.py"),
    ("width_reduction_lane", "tools/verification/families/shear_overdesign_governs_width_reduction_lane_snapshot.py"),
    ("terminal_lane", "tools/verification/families/shear_overdesign_governs_terminal_lane_snapshot.py"),
    ("zero_shear_lane", "tools/verification/families/shear_overdesign_governs_zero_shear_lane_snapshot.py"),
    ("geometry_restriction", "tools/verification/families/shear_overdesign_governs_geometry_restriction_snapshot.py"),
    ("runtime", "tools/verification/families/shear_overdesign_governs_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/shear_overdesign_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/shear_overdesign_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/shear_overdesign_governs_cutover_implementation.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
]

EXPECTED_ORDER = (
    "SPACING_INCREASE",
    "BAR_SIZE_REDUCTION",
    "LEG_COUNT_REDUCTION",
    "LIGATURE_REMOVAL",
    "WIDTH_REDUCTION",
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
        "Vu": 0.0,
        "design_actions_present": True,
        "s_lig": 100.0,
        "lig_d": 16,
        "lig_legs": 6,
        "shear_utilisation": 0.0,
        "bending_utilisation": 0.2,
        "minimum_shear_reinforcement_required": False,
    }


def _evaluation(
    candidate_input: ShearOverdesignCandidateInput,
    candidate_update: ShearOverdesignCandidateUpdate,
) -> ShearOverdesignCandidateEvaluation:
    updates = dict(candidate_update.updates)
    removes_ligatures = updates.get("lig_legs") == 0 and updates.get("lig_d") == 0
    width_after = updates.get("b") or candidate_input.base_state.get("b")
    try:
        width_after_value = float(width_after)
    except (TypeError, ValueError):
        width_after_value = None
    width_candidate = candidate_update.width_reduction_attempted
    inside_band = updates.get("s_lig") == 300 and not removes_ligatures
    if width_candidate:
        inside_band = bool(width_after_value is not None and 250.0 <= width_after_value <= 650.0)
    return ShearOverdesignCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_shear_overdesign_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        shear_utilisation=0.0 if removes_ligatures else (0.9 if inside_band else 0.42),
        previous_shear_utilisation=0.0,
        target_band_status={"inside_target_band": inside_band},
        utilisation_moves_toward_target=True,
        shear_remains_compliant=True,
        constructability_status={"status": "PASS"},
        mandatory_detailing_status={"status": "PASS", "minimum_shear_reinforcement_required": False},
        shear_detailing_update_status={
            "shear_detailing_only": candidate_update.shear_detailing_only,
            "contract_update_allowed": candidate_update.contract_allowed_update,
            "update_keys": candidate_update.update_keys,
        },
        geometry_restriction_status={
            "geometry_reduction_attempted": candidate_update.geometry_reduction_attempted,
            "depth_reduction_prohibited": True,
            "width_reduction_allowed": True,
        },
        width_reduction_status={
            "width_before": candidate_input.base_state.get("b"),
            "width_after": width_after_value,
            "width_reduction_attempted": width_candidate,
            "width_locked": False,
        },
        bending_utilisation=0.92 if width_candidate and inside_band else 0.2,
        previous_bending_utilisation=float(candidate_input.base_state.get("bending_utilisation") or 0.0),
        reinforcement_fit_status={"status": "PASS", "rearrangement_search_attempted": True},
        serviceability_status={"status": "PASS"},
        crack_control_status={"status": "PASS"},
        zero_shear_status={
            "zero_or_negligible_shear": True,
            "must_not_terminate_for_zero_utilisation": True,
        },
        ligature_removal_status={"no_unnecessary_ligatures_remain": removes_ligatures},
        reinforcement_quantity={"after": 0.0 if removes_ligatures else 1.0},
        cost_proxy={"after": 0.0 if removes_ligatures else 1.0},
        capacity_summary={"fixture": "lock_verifier"},
        failure_flags={"underdesign_created": False},
        engineering_status={"candidate_valid": True, "result": "ACCEPTED"},
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
    json_path = ARTIFACT_DIR / f"shear_overdesign_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_lock_verifier_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Lock Verifier",
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


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _read_inputs_composition_surface() -> str:
    return "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_page_modules/guidance_compute.py",
            "inputs_page_modules/apply_routing.py",
            "inputs_page_modules/design_guide/family_ladder_guidance.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
            "inputs_page_modules/design_guide/primary_button_queue.py",
            "design_brain/design_guide_controller.py",
        )
    )


def main() -> int:
    proof_chain = [{"name": name, **_run_script(script)} for name, script in PROOF_CHAIN]
    proof_chain_pass = all(entry["passed"] for entry in proof_chain)
    result = run_shear_overdesign_governs_runtime(
        base_state=_base_state(),
        evaluate_candidate=_default_runtime_evaluator,
    )
    repeat = run_shear_overdesign_governs_runtime(
        base_state=_base_state(),
        evaluate_candidate=_default_runtime_evaluator,
    )
    family = ShearCleanupFamily()
    ladder = family.contracted_optimisation_ladder_specs(_base_state())
    runtime_source = (ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    package_source = (ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "__init__.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    cleanup_source = (ROOT / "design_brain" / "families" / "shear_cleanup.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    inputs_source = _read_inputs_composition_surface()
    forbidden_runtime_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    all_updates = [
        dict(spec.get("updates") or {})
        for spec in list(ladder.get("specs") or [])
        if isinstance(spec, dict)
    ]
    prohibited_geometry_keys = {"D", "beam_depth", "beam_depth_mm"}
    width_keys = {"b", "bw", "beam_width", "beam_width_mm"}
    checks = {
        "proof_chain_pass": proof_chain_pass,
        "contract_loads": bool(load_shear_overdesign_governs_contract()),
        "family_id": family_identity().get("family_id") == "SHEAR_OVERDESIGN_GOVERNS",
        "contract_lane_order_exact": shear_overdesign_contract_lane_order() == EXPECTED_ORDER,
        "runtime_reads_contract_order": tuple(result.repair_reason_proof.get("contract_lane_order") or ())
        == EXPECTED_ORDER,
        "runtime_hash_stable": result.ladder_hash == repeat.ladder_hash,
        "zero_shear_override_protected": (zero_shear_override().get("requires") or {}).get("ligatures_exist") is True
        and result.zero_shear_override_proof.get("must_not_terminate_for_zero_utilisation") is True
        and any(row.get("lane_id") == "LIGATURE_REMOVAL" for row in result.candidate_repairs),
        "width_reduction_required_and_attempted": geometry_restrictions().get("width_reduction_required_when_unlocked") is True
        and result.geometry_restriction_proof.get("width_reduction_attempted") is True
        and any(set(update) & width_keys for update in all_updates),
        "depth_reduction_prohibited": geometry_restrictions().get("depth_reduction_prohibited") is True
        and result.geometry_restriction_proof.get("candidate_updates_touch_prohibited_geometry") is False
        and not any(set(update) & prohibited_geometry_keys for update in all_updates),
        "smallest_safe_width_selected": result.ranking_proof.get("smallest_safe_width_selected") is True
        and result.exact_stop_proof.get("width_reduction_attempted") is True,
        "ranking_contract_proven": tuple(ranking_criteria()) == tuple(result.ranking_proof.get("criteria") or ()),
        "lane_policies_present": bool(lane_proof_policies()),
        "family_shell_runtime_driven": ladder.get("contract_runtime_driven") is True
        and ladder.get("contract_runtime_authority") == "run_shear_overdesign_governs_runtime",
        "package_runtime_export_matches_family_shell": result.ladder_hash == ladder.get("ladder_hash"),
        "runtime_has_no_page_ui_imports": not forbidden_runtime_terms,
        "shared_systems_remain_shared": "from design_brain.final_publication import" in inputs_source
        and "build_final_design_guide_publication" in inputs_source
        and "handle_inputs_apply_buttons" in inputs_source
        and "def _queue_primary_design_guide_button_action(" in inputs_source
        and "shared_system_owned_outside_family" not in runtime_source,
        "no_bending_or_shear_fail_coupling": "bending_fail_governs" not in runtime_source
        and "BENDING_FAIL_GOVERNS" not in runtime_source
        and "shear_fail_governs" not in runtime_source
        and "bending_fail_governs" not in package_source
        and "shear_fail_governs" not in package_source
        and "bending_fail_governs" not in cleanup_source
        and "shear_fail_governs" not in cleanup_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if forbidden_runtime_terms:
        failures.append(f"forbidden_runtime_terms:{forbidden_runtime_terms}")
    failed_chain = [entry for entry in proof_chain if not entry["passed"]]
    if failed_chain:
        failures.append(f"failed_proof_chain:{[entry['name'] for entry in failed_chain]}")
    snapshot = {
        "schema": "shear_overdesign_governs_lock_verifier.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "proof_chain": proof_chain,
        "contract_lane_order": list(shear_overdesign_contract_lane_order()),
        "runtime": {
            "selected_strategy_lane": result.selected_strategy_lane,
            "ladder_hash": result.ladder_hash,
            "repeat_ladder_hash": repeat.ladder_hash,
            "candidate_count": len(result.candidate_repairs),
            "smallest_safe_width": result.geometry_restriction_proof.get("smallest_safe_width"),
        },
        "family_ladder": {
            "contract_runtime_driven": ladder.get("contract_runtime_driven"),
            "ladder_hash": ladder.get("ladder_hash"),
            "spec_count": len(list(ladder.get("specs") or [])),
        },
        "scope_limits": {
            "moves_publication": False,
            "moves_cta": False,
            "moves_apply_routing": False,
            "moves_ui_session_debug": False,
            "allows_width_reduction": True,
            "allows_depth_reduction": False,
            "touches_bending": False,
            "touches_shear_fail": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("SHEAR_OVERDESIGN_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_OVERDESIGN_GOVERNS lock verifier PASS")
    print("SHEAR_OVERDESIGN_GOVERNS lock complete")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
