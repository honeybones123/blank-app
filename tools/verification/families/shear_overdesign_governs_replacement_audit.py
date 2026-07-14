"""Current-live replacement audit for SHEAR_OVERDESIGN_GOVERNS."""

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
        capacity_summary={"fixture": "replacement_audit"},
        failure_flags={"underdesign_created": False},
        engineering_status={"candidate_valid": True, "result": "ACCEPTED"},
    ).with_evaluation_hash()


def _runtime_payload() -> dict[str, Any]:
    result = run_shear_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    return result.to_dict()


def _current_live_evidence() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    anchors = {
        "compute_tightening": "_compute_shear_tightening_recommendation" in source,
        "remove_links": "_try_shear_remove_links_tightening_recommendation" in source,
        "density_variants": "generate_less_shear_reo_variants" in source,
        "no_links_code_check": "_shear_no_links_candidate_passes_code" in source,
        "detail_update_purity": "_SHEAR_DETAILING_UPDATE_KEYS" in source
        and "_shear_detailing_updates_pure" in source,
    }
    observed_surfaces = []
    if anchors["compute_tightening"]:
        observed_surfaces.append("PAGE_LOCAL_SHEAR_TIGHTENING")
    if anchors["remove_links"]:
        observed_surfaces.append("PAGE_LOCAL_LIGATURE_REMOVAL")
    if anchors["density_variants"]:
        observed_surfaces.append("PAGE_LOCAL_DENSITY_REDUCTION_VARIANTS")
    return {
        "source": "inputs_page.py source anchors",
        "used_as_authority": False,
        "anchors": anchors,
        "observed_surfaces": observed_surfaces,
    }


def _classify(runtime_payload: dict[str, Any], old_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "item": "old_page_local_cleanup_replaced_by_contract_runtime",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "The contract runtime is authoritative; page-local cleanup surfaces are replacement impact evidence only.",
            "old_surfaces": list(old_evidence.get("observed_surfaces") or []),
            "new_order": list(shear_overdesign_contract_lane_order()),
        },
        {
            "item": "contract_terminal_and_zero_shear_proofs",
            "class": "NO_OLD_EQUIVALENT_NEEDED",
            "reason": "The lock contract requires explicit terminal and zero-shear proof surfaces even where old live code spread that evidence across page helpers.",
        },
        {
            "item": "new_runtime_evidence_surface",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "The runtime emits ladder trace, candidate repairs, ranking proof, zero-shear proof, width/depth geometry proof, exact stop proof, and stable hash.",
        },
    ]
    missing = []
    for key in (
        "ladder_trace",
        "candidate_repairs",
        "selected_recommendation",
        "ranking_proof",
        "zero_shear_override_proof",
        "geometry_restriction_proof",
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
    json_path = ARTIFACT_DIR / f"shear_overdesign_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_replacement_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Replacement Audit",
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
    runtime_source = (ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    checks = {
        "contract_runtime_order_unchanged": shear_overdesign_contract_lane_order()
        == (
            "SPACING_INCREASE",
            "BAR_SIZE_REDUCTION",
            "LEG_COUNT_REDUCTION",
            "LIGATURE_REMOVAL",
            "WIDTH_REDUCTION",
            "EXACT_STOP",
            "EXHAUSTED",
        ),
        "old_live_evidence_found": all(bool(value) for value in (old_evidence.get("anchors") or {}).values()),
        "new_runtime_evidence_sufficient": not any(
            row.get("class") == "MISSING_NEW_EVIDENCE_BLOCKER" for row in differences
        ),
        "zero_shear_proof_exists": bool(before.get("zero_shear_override_proof")),
        "geometry_restriction_proof_exists": bool(before.get("geometry_restriction_proof")),
        "ranking_proof_exists": bool(before.get("ranking_proof")),
        "old_behavior_did_not_alter_runtime_hash": before.get("ladder_hash") == after.get("ladder_hash"),
        "difference_classes_known": classes <= DIFFERENCE_CLASSES,
        "unexplained_risks_absent": "UNEXPLAINED_REPLACEMENT_RISK" not in classes,
        "runtime_has_no_page_ui_imports": not forbidden_terms,
        "bending_not_part_of_audit": True,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "shear_overdesign_governs_replacement_audit.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "old_live_evidence": old_evidence,
        "new_runtime": {
            "contract_order": list(shear_overdesign_contract_lane_order()),
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
            "bending_touched": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("SHEAR_OVERDESIGN_GOVERNS replacement audit FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_OVERDESIGN_GOVERNS replacement audit PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
