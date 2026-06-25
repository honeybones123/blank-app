"""Current-live replacement audit for BENDING_OVERDESIGN_GOVERNS."""

from __future__ import annotations

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
INPUTS_PAGE = ROOT / "inputs_page.py"

from design_brain.bending_overdesign_candidate_evaluation import (  # noqa: E402
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    build_bending_overdesign_candidate_state_hash,
)
from design_brain.families.bending_overdesign_governs.runtime import (  # noqa: E402
    bending_overdesign_contract_lane_order,
    run_bending_overdesign_governs_runtime,
)


DIFFERENCE_CLASSES = {
    "EXPECTED_CONTRACT_REPLACEMENT",
    "MISSING_NEW_EVIDENCE_BLOCKER",
    "UNEXPLAINED_REPLACEMENT_RISK",
    "NO_OLD_EQUIVALENT_NEEDED",
}

FORBIDDEN_RUNTIME_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "publication",
    "apply_resolved_candidate",
    "button_contract",
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
    if updates == {"bot1_count": 4, "db_bot_1": 20}:
        utilisation, as_after, compliant, cost = 0.96, 1256.0, True, 0.61
    elif updates == {"bot1_count": 3, "db_bot_1": 20}:
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
        capacity_summary={"fixture": "replacement_audit"},
        failure_flags={"underdesign_created": not compliant, "below_minimum_reinforcement": as_after < as_min},
        engineering_status={"candidate_valid": valid, "result": "ACCEPTED" if valid else "REJECTED"},
    ).with_evaluation_hash()


def _runtime_payload() -> dict[str, Any]:
    result = run_bending_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    return result.to_dict()


def _current_live_evidence() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    anchors = {
        "bending_only_target_band_cleanup_item": "_bending_only_target_band_cleanup_item" in source,
        "secondary_bending_tightening_states": "_generate_secondary_bending_tightening_states" in source,
        "bending_cleanup_evidence": "bending_cleanup_evidence" in source,
        "page_evaluator_for_cleanup": "bending_cleanup_candidate_eval = evaluate_candidate_full" in source,
        "button_contract_wiring": "_design_guide_button_contract(bending_cleanup_item" in source,
    }
    observed_surfaces = []
    if anchors["bending_only_target_band_cleanup_item"]:
        observed_surfaces.append("PAGE_LOCAL_BENDING_TARGET_BAND_CLEANUP")
    if anchors["secondary_bending_tightening_states"]:
        observed_surfaces.append("PAGE_LOCAL_SECONDARY_BENDING_TIGHTENING")
    if anchors["page_evaluator_for_cleanup"]:
        observed_surfaces.append("PAGE_LOCAL_EVALUATOR_CALL")
    if anchors["button_contract_wiring"]:
        observed_surfaces.append("PAGE_LOCAL_CTA_BUTTON_CONTRACT")
    return {
        "source": "inputs_page.py source anchors",
        "used_as_authority": False,
        "anchors": anchors,
        "observed_surfaces": observed_surfaces,
    }


def _classify(runtime_payload: dict[str, Any], old_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "item": "old_page_local_bending_cleanup_replaced_by_contract_runtime",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "The contract runtime is authoritative; page-local bending cleanup surfaces are replacement impact evidence only.",
            "old_surfaces": list(old_evidence.get("observed_surfaces") or []),
            "new_order": list(bending_overdesign_contract_lane_order()),
        },
        {
            "item": "minimum_reinforcement_and_geometry_restart_proofs",
            "class": "NO_OLD_EQUIVALENT_NEEDED",
            "reason": "The lock contract requires explicit As_min, geometry compliance, and restart proof surfaces even where old live code spread that evidence across page helpers.",
        },
        {
            "item": "new_runtime_evidence_surface",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "The runtime emits ladder trace, candidate repairs, ranking proof, minimum reinforcement proof, geometry proof, restart proof, exact stop proof, and stable hash.",
        },
    ]
    missing = []
    for key in (
        "ladder_trace",
        "candidate_repairs",
        "selected_recommendation",
        "ranking_proof",
        "minimum_reinforcement_proof",
        "geometry_compliance_proof",
        "restart_proof",
        "exact_stop_proof",
        "ladder_hash",
    ):
        if not runtime_payload.get(key):
            missing.append(key)
    if missing:
        rows.append(
            {
                "item": "new_runtime_missing_required_evidence",
                "class": "MISSING_NEW_EVIDENCE_BLOCKER",
                "missing": missing,
                "reason": "Cutover cannot proceed until required proof surfaces exist.",
            }
        )
    return rows


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_overdesign_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_governs_replacement_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_OVERDESIGN_GOVERNS Replacement Audit",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "Authority rule: contract runtime is authoritative; old live behavior is replacement-impact evidence only.",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Classification",
                "",
                *[
                    f"- `{row['item']}`: `{row['class']}` - {row['reason']}"
                    for row in snapshot["difference_classification"]
                ],
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    before = _runtime_payload()
    old_evidence = _current_live_evidence()
    after = _runtime_payload()
    differences = _classify(before, old_evidence)
    classes = {str(row.get("class")) for row in differences}
    runtime_source = (ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    checks = {
        "contract_runtime_order_unchanged": bending_overdesign_contract_lane_order()
        == (
            "BOTTOM_REINFORCEMENT_REDUCTION",
            "LAYER_REDUCTION",
            "WIDTH_REDUCTION",
            "DEPTH_REDUCTION",
            "EXACT_STOP",
            "EXHAUSTED",
        ),
        "old_live_evidence_found": all(bool(value) for value in (old_evidence.get("anchors") or {}).values()),
        "new_runtime_evidence_sufficient": not any(
            row.get("class") == "MISSING_NEW_EVIDENCE_BLOCKER" for row in differences
        ),
        "minimum_reinforcement_proof_exists": bool(before.get("minimum_reinforcement_proof")),
        "geometry_compliance_proof_exists": bool(before.get("geometry_compliance_proof")),
        "restart_proof_exists": bool(before.get("restart_proof")),
        "ranking_proof_exists": bool(before.get("ranking_proof")),
        "old_behavior_did_not_alter_runtime_hash": before.get("ladder_hash") == after.get("ladder_hash"),
        "difference_classes_known": classes <= DIFFERENCE_CLASSES,
        "unexplained_risks_absent": "UNEXPLAINED_REPLACEMENT_RISK" not in classes,
        "runtime_has_no_page_ui_imports": not forbidden_terms,
        "other_locked_families_not_part_of_audit": True,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "bending_overdesign_governs_replacement_audit.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "old_live_evidence": old_evidence,
        "new_runtime": {
            "contract_order": list(bending_overdesign_contract_lane_order()),
            "selected_strategy_lane": before.get("selected_strategy_lane"),
            "ladder_hash": before.get("ladder_hash"),
            "candidate_count": len(before.get("candidate_repairs") or []),
        },
        "difference_classification": differences,
        "forbidden_runtime_terms": forbidden_terms,
        "scope_limits": {
            "cutover_enabled": False,
            "old_implementation_used_as_oracle": False,
            "cta_publication_apply_ui_moved": False,
            "other_locked_families_touched": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("BENDING_OVERDESIGN_GOVERNS replacement audit FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_OVERDESIGN_GOVERNS replacement audit PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
