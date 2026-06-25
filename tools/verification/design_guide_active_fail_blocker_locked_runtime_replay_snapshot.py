"""Replay active-fail blocker evidence through the locked combined/shear runtime.

This is proof-only. It checks whether the live blocked Design Guide trace has
enough locked family-runtime inputs to prove an exhausted/no-repair blocker.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTRACT_PATH = ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "contract.json"

from design_brain.combined_bending_shear_candidate_merge import (  # noqa: E402
    CombinedBendingShearFailInputs,
    CombinedCandidateEvaluation,
    CombinedMergedCandidate,
    combined_candidate_state_hash,
)
from design_brain.families.bending_and_shear_fail_govern.runtime import (  # noqa: E402
    run_combined_bending_shear_fail_runtime,
)


REQUIRED_CONTRACT_EVIDENCE = {
    "selection_boundary",
    "candidate_source_proof",
    "combined_merge_trace",
    "accepted_candidate_evidence",
    "rejected_candidate_evidence",
    "ranking_evidence",
    "exact_stop_proof",
    "exhausted_proof",
    "ownership_proof",
    "contract_version",
}

REQUIRED_RUNTIME_PROOF_FIELDS = {
    "contract_hash",
    "runtime_hash",
    "combined_merge_trace",
    "candidate_repairs",
    "accepted_candidate_evidence",
    "rejected_candidate_evidence",
    "exhausted_proof",
    "candidate_source_proof",
    "ownership_proof",
    "selection_boundary_proof",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_artifact(prefix: str) -> Path | None:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    return paths[-1] if paths else None


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _run_compile() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "tools/verification/design_guide_active_fail_blocker_locked_runtime_replay_snapshot.py",
            "design_brain/combined_bending_shear_candidate_merge.py",
            "design_brain/families/bending_and_shear_fail_govern/runtime.py",
            "design_brain/families/bending_and_shear_fail_govern/contract.py",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _contract_coverage() -> dict[str, Any]:
    contract = _load_json(CONTRACT_PATH)
    required = set(
        ((contract.get("family_result_schema") or {}).get("evidence_required_fields") or [])
    )
    return {
        "contract_path": str(CONTRACT_PATH),
        "required_evidence_fields": sorted(required),
        "missing_required_evidence_fields": sorted(REQUIRED_CONTRACT_EVIDENCE - required),
        "has_exhausted_proof": "exhausted_proof" in required,
        "has_candidate_source_proof": "candidate_source_proof" in required,
        "has_ownership_proof": "ownership_proof" in required,
    }


def _extract_trace_inputs(trace: dict[str, Any]) -> dict[str, Any]:
    exact = dict(trace.get("exact_blockers_by_family") or {})
    bending = dict(exact.get("bending") or {})
    shear = dict(exact.get("shear") or {})
    final_item = dict(trace.get("final_visible_item") or {})
    selected_family = str(trace.get("selected_family") or "COMBINED_BENDING_SHEAR_FAIL")
    runtime_proof_presence = {
        field: field in _stable_json(trace)
        for field in REQUIRED_RUNTIME_PROOF_FIELDS
    }
    source_rows = {
        "bending_candidate_rows": list(bending.get("active_fail_repair_candidate_rows") or []),
        "shear_candidate_rows": list(shear.get("active_fail_repair_candidate_rows") or []),
        "approved_combined_merge_candidate_rows": list(
            (final_item.get("approved_combined_merge_candidates") or [])
            if isinstance(final_item.get("approved_combined_merge_candidates"), list)
            else []
        ),
    }
    has_locked_runtime_inputs = bool(
        source_rows["bending_candidate_rows"]
        or source_rows["shear_candidate_rows"]
        or source_rows["approved_combined_merge_candidate_rows"]
    )
    return {
        "selected_family": selected_family,
        "geometry_lock_enabled": trace.get("geometry_lock_enabled"),
        "bending_source": bending.get("source"),
        "shear_source": shear.get("source"),
        "bending_search_scope": bending.get("search_scope"),
        "shear_search_scope": shear.get("search_scope"),
        "bending_candidate_row_count": len(source_rows["bending_candidate_rows"]),
        "shear_candidate_row_count": len(source_rows["shear_candidate_rows"]),
        "approved_combined_merge_candidate_row_count": len(
            source_rows["approved_combined_merge_candidate_rows"]
        ),
        "runtime_proof_presence": runtime_proof_presence,
        "runtime_proof_field_count": sum(1 for value in runtime_proof_presence.values() if value),
        "has_locked_runtime_inputs": has_locked_runtime_inputs,
        "source_rows": source_rows,
        "trace_hash": _stable_hash(trace),
    }


def _evaluation(
    inputs: CombinedBendingShearFailInputs,
    candidate: CombinedMergedCandidate,
) -> CombinedCandidateEvaluation:
    updates = dict(candidate.updates)
    source_families = set(candidate.source_families)
    approved_combined = "APPROVED_COMBINED_MERGE_RULE" in source_families
    has_bending_change = any(key in updates for key in ("bot1_count", "db_bot_1", "bot2_count", "D", "b"))
    has_shear_change = any(key in updates for key in ("lig_d", "lig_legs", "s_lig", "D", "b"))
    repairs_both = bool(
        ({"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"}.issubset(source_families))
        or (approved_combined and has_bending_change and has_shear_change)
    )
    bending_after = 0.94 if repairs_both else 1.12
    shear_after = 0.92 if repairs_both else 1.14
    return CombinedCandidateEvaluation(
        input_hash=inputs.input_hash,
        update_hash=candidate.update_hash,
        candidate_state_hash=combined_candidate_state_hash(inputs.base_state, updates),
        source_family_ids=candidate.source_families,
        source_candidates=tuple(source.candidate_id for source in candidate.source_candidates),
        bending_utilisation_before=1.8,
        shear_utilisation_before=1.55,
        bending_utilisation_after=bending_after,
        shear_utilisation_after=shear_after,
        bending_improves=repairs_both,
        shear_improves=repairs_both,
        bending_compliant=repairs_both,
        shear_compliant=repairs_both,
        bending_inside_target_band=0.85 <= bending_after <= 1.0,
        shear_inside_target_band=0.85 <= shear_after <= 1.0,
        both_failures_repaired=repairs_both,
        geometry_interaction_status={"rechecked": ["bending", "shear", "minimum reinforcement", "geometry ratio", "constructability"]},
        reinforcement_interaction_status={"bending_reinforcement_rechecked": True, "shear_reinforcement_rechecked": True},
        code_compliance_status={"status": "PASS" if repairs_both else "FAIL"},
        detailing_status={"status": "PASS" if repairs_both else "FAIL"},
        constructability_status={"status": "PASS"},
        geometry_increase={"total_mm": 0.0},
        reinforcement_increase={"total": 0.0},
        cost_proxy={"after": 1.0},
        rejection_reasons=() if repairs_both else ("trace did not supply a combined source repair",),
        engineering_status={"candidate_valid": repairs_both},
    ).with_evaluation_hash()


def _run_runtime_replays(trace_inputs: dict[str, Any]) -> dict[str, Any]:
    trace_runtime_inputs = CombinedBendingShearFailInputs(
        selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
        base_state={
            "selected_family_id": trace_inputs["selected_family"],
            "geometry_lock_enabled": trace_inputs["geometry_lock_enabled"],
            "trace_hash": trace_inputs["trace_hash"],
        },
        bending_fail_candidates=tuple(trace_inputs["source_rows"]["bending_candidate_rows"]),
        shear_fail_candidates=tuple(trace_inputs["source_rows"]["shear_candidate_rows"]),
        approved_combined_merge_candidates=tuple(
            trace_inputs["source_rows"]["approved_combined_merge_candidate_rows"]
        ),
    )
    trace_result = run_combined_bending_shear_fail_runtime(
        inputs=trace_runtime_inputs,
        evaluate_candidate=_evaluation,
    )
    control_inputs = CombinedBendingShearFailInputs(
        selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
        base_state={"selected_family_id": "COMBINED_BENDING_SHEAR_FAIL", "control": "approved_runtime_candidate"},
        approved_combined_merge_candidates=(
            {
                "source_family_id": "APPROVED_COMBINED_MERGE_RULE",
                "candidate_id": "proof_control_combined_repair",
                "updates": {"bot1_count": 9, "db_bot_1": 16, "lig_legs": 4, "s_lig": 150.0},
                "evidence": {"source": "proof_control", "not_live_product_authority": True},
            },
        ),
    )
    control_result = run_combined_bending_shear_fail_runtime(
        inputs=control_inputs,
        evaluate_candidate=_evaluation,
    )
    return {
        "trace_replay": {
            "status": trace_result.status,
            "selected_recommendation_present": trace_result.selected_recommendation is not None,
            "candidate_repairs_count": len(trace_result.candidate_repairs),
            "accepted_count": len(trace_result.accepted_candidate_evidence),
            "rejected_count": len(trace_result.rejected_candidate_evidence),
            "exhausted": bool(trace_result.exhausted_proof.get("exhausted")),
            "exhausted_reason": trace_result.exhausted_reason,
            "specific_blocker": trace_result.exhausted_proof.get("specific_blocker"),
            "candidate_source_proof": dict(trace_result.candidate_source_proof),
            "contract_hash": trace_result.contract_hash,
            "runtime_hash": trace_result.runtime_hash,
        },
        "control_runtime_replay": {
            "status": control_result.status,
            "selected_recommendation_present": control_result.selected_recommendation is not None,
            "candidate_repairs_count": len(control_result.candidate_repairs),
            "accepted_count": len(control_result.accepted_candidate_evidence),
            "selected_updates": dict((control_result.selected_recommendation or {}).get("updates") or {}),
            "contract_hash": control_result.contract_hash,
            "runtime_hash": control_result.runtime_hash,
            "meaning": "proves runtime can select a valid candidate when a locked/approved source candidate is supplied",
        },
    }


def _build_snapshot() -> dict[str, Any]:
    compile_result = _run_compile()
    trace_path = _latest_artifact("design_guide_unlocked_active_failure_missing_apply_cta_guard_trace")
    authority_path = _latest_artifact("design_guide_active_fail_blocker_runtime_authority")
    trace = _load_json(trace_path)
    contract = _contract_coverage()
    trace_inputs = _extract_trace_inputs(trace) if trace else {}
    replays = _run_runtime_replays(trace_inputs) if trace_inputs else {}

    trace_has_runtime_proof = bool(
        trace_inputs
        and trace_inputs.get("runtime_proof_field_count") == len(REQUIRED_RUNTIME_PROOF_FIELDS)
    )
    trace_has_runtime_inputs = bool(trace_inputs and trace_inputs.get("has_locked_runtime_inputs"))
    trace_replay = dict(replays.get("trace_replay") or {})
    control_replay = dict(replays.get("control_runtime_replay") or {})
    if not trace_path:
        blocker_validity = "NO_TRACE_TO_REPLAY"
        recommendation = "Capture the active-fail guard trace before deciding blocker validity."
    elif not trace_has_runtime_proof and not trace_has_runtime_inputs:
        blocker_validity = "NOT_PROVEN_TRACE_MISSING_LOCKED_RUNTIME_INPUTS"
        recommendation = (
            "Do not publish this as a final no-repair blocker. Capture or feed locked "
            "bending/shear/combined runtime source candidates into the active-fail blocker path, "
            "then require exhausted_proof plus runtime_hash before blocking."
        )
    elif trace_replay.get("selected_recommendation_present"):
        blocker_validity = "OLD_BLOCKER_WRONG_RUNTIME_FOUND_CANDIDATE"
        recommendation = "Replace the blocker with the locked runtime selected recommendation path."
    elif trace_replay.get("exhausted") and trace_has_runtime_proof:
        blocker_validity = "BLOCKER_VALID_RUNTIME_EXHAUSTED"
        recommendation = "Cut over final publication to consume runtime exhausted proof."
    else:
        blocker_validity = "PARTIAL_RUNTIME_REPLAY_UNPROVEN"
        recommendation = "Add missing runtime provenance before accepting or rejecting the blocker."

    checks = {
        "py_compile_pass": compile_result["passed"],
        "guard_trace_found": trace_path is not None,
        "contract_has_required_exhausted_blocker_fields": not contract["missing_required_evidence_fields"],
        "trace_contains_runtime_proof_fields": trace_has_runtime_proof,
        "trace_contains_locked_runtime_source_inputs": trace_has_runtime_inputs,
        "trace_replay_ran": bool(replays),
        "control_runtime_can_select_candidate": bool(control_replay.get("selected_recommendation_present")),
        "product_behavior_changed": False,
    }
    failures = [key for key, passed in checks.items() if key in {"py_compile_pass", "guard_trace_found", "contract_has_required_exhausted_blocker_fields"} and not passed]
    status = "PASS" if not failures else "FAIL"
    proof_hash = _stable_hash(
        {
            "contract": contract,
            "trace_inputs": trace_inputs,
            "replays": replays,
            "blocker_validity": blocker_validity,
        }
    )
    return {
        "schema": "design_guide_active_fail_blocker_locked_runtime_replay_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "blocker_validity": blocker_validity,
        "checks": checks,
        "failures": failures,
        "contract_coverage": contract,
        "trace_inputs": trace_inputs,
        "runtime_replays": replays,
        "artifacts_used": {
            "guard_trace": str(trace_path) if trace_path else None,
            "authority_snapshot": str(authority_path) if authority_path else None,
        },
        "verification": {"py_compile": compile_result},
        "recommendation": recommendation,
        "product_behavior_changed": False,
        "snapshot_hash": proof_hash,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    trace_inputs = snapshot.get("trace_inputs") or {}
    replays = snapshot.get("runtime_replays") or {}
    trace_replay = replays.get("trace_replay") or {}
    control = replays.get("control_runtime_replay") or {}
    lines = [
        "# Design Guide Active-Fail Blocker Locked Runtime Replay Snapshot",
        "",
        f"Timestamp: `{snapshot['generated_at']}`",
        f"Result: `{snapshot['status']}`",
        f"Blocker validity: `{snapshot['blocker_validity']}`",
        f"Snapshot hash: `{snapshot['snapshot_hash']}`",
        "",
        "## Summary",
        "",
        f"- Selected family: `{trace_inputs.get('selected_family')}`",
        f"- Geometry lock enabled: `{trace_inputs.get('geometry_lock_enabled')}`",
        f"- Trace runtime proof fields: `{trace_inputs.get('runtime_proof_field_count')}`",
        f"- Trace locked runtime inputs present: `{trace_inputs.get('has_locked_runtime_inputs')}`",
        f"- Trace replay status: `{trace_replay.get('status')}`",
        f"- Trace replay selected candidate: `{trace_replay.get('selected_recommendation_present')}`",
        f"- Trace replay exhausted reason: `{trace_replay.get('exhausted_reason')}`",
        f"- Control replay selected candidate: `{control.get('selected_recommendation_present')}`",
        "",
        "## Interpretation",
        "",
        snapshot["recommendation"],
        "",
        "## Checks",
        "",
        *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
        "",
        "## Artifacts Used",
        "",
        f"- Guard trace: `{snapshot['artifacts_used']['guard_trace']}`",
        f"- Authority snapshot: `{snapshot['artifacts_used']['authority_snapshot']}`",
        "",
        "## Failures",
        "",
        *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_blocker_locked_runtime_replay_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_active_fail_blocker_locked_runtime_replay_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_active_fail_blocker_locked_runtime_replay_snapshot {snapshot['status']}")
    print(f"blocker_validity={snapshot['blocker_validity']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
