"""Proof snapshot for the SHEAR_OVERDESIGN_GOVERNS contract runtime."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
RUNTIME_PATH = ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "runtime.py"

from design_brain.families.shear_overdesign_governs.contract import (  # noqa: E402
    lane_proof_policies,
    ranking_criteria,
)
from design_brain.families.shear_overdesign_governs.runtime import (  # noqa: E402
    ShearOverdesignGovernsResult,
    run_shear_overdesign_governs_runtime,
    shear_overdesign_contract_lane_order,
)
from design_brain.shear_overdesign_candidate_evaluation import (  # noqa: E402
    ShearOverdesignCandidateEvaluation,
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
    build_shear_overdesign_candidate_state_hash,
)


EXPECTED_CONTRACT_ORDER = (
    "SPACING_INCREASE",
    "BAR_SIZE_REDUCTION",
    "LEG_COUNT_REDUCTION",
    "LIGATURE_REMOVAL",
    "WIDTH_REDUCTION",
    "EXACT_STOP",
    "EXHAUSTED",
)

REQUIRED_RESULT_FIELDS = {
    "status",
    "selected_strategy_lane",
    "ladder_trace",
    "candidate_repairs",
    "selected_recommendation",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "ranking_proof",
    "exact_stop_proof",
    "exhausted_reason",
    "zero_shear_override_proof",
    "geometry_restriction_proof",
    "repair_reason_proof",
    "blocked_reason",
    "cta_intent_proof",
    "ladder_hash",
}

FORBIDDEN_RUNTIME_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "publication",
    "apply_resolved_candidate",
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
        ligature_removal_status={
            "no_unnecessary_ligatures_remain": removes_ligatures,
        },
        reinforcement_quantity={"after": 0.0 if removes_ligatures else 1.0},
        cost_proxy={"after": 0.0 if removes_ligatures else 1.0},
        capacity_summary={"fixture": "zero_shear_overdesign"},
        failure_flags={"underdesign_created": False},
        engineering_status={"candidate_valid": True, "result": "ACCEPTED"},
    ).with_evaluation_hash()


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_overdesign_governs_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Runtime Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Selected",
                "",
                f"- status: `{snapshot['runtime']['status']}`",
                f"- selected_strategy_lane: `{snapshot['runtime']['selected_strategy_lane']}`",
                f"- ladder_hash: `{snapshot['runtime']['ladder_hash']}`",
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
    result = run_shear_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    repeat = run_shear_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    payload = result.to_dict()
    fields_present = {field.name for field in fields(ShearOverdesignGovernsResult)}
    policies = lane_proof_policies()
    runtime_source = RUNTIME_PATH.read_text(encoding="utf-8", errors="replace")
    forbidden_hits = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    candidate_updates = [dict(row.get("updates") or {}) for row in payload.get("candidate_repairs") or []]
    checks = {
        "contract_lane_order_exact": shear_overdesign_contract_lane_order() == EXPECTED_CONTRACT_ORDER,
        "required_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(fields_present),
        "spacing_policy_represented": any(update.get("s_lig") == 300 for update in candidate_updates),
        "bar_size_policy_represented": any(update.get("lig_d") == 10 for update in candidate_updates),
        "leg_count_policy_represented": any(update.get("lig_legs") == 2 for update in candidate_updates),
        "ligature_removal_policy_represented": any(
            update.get("lig_legs") == 0 and update.get("lig_d") == 0 for update in candidate_updates
        ),
        "width_reduction_policy_represented": any("b" in update for update in candidate_updates),
        "ranking_criteria_match_contract": tuple(payload["ranking_proof"].get("criteria") or ()) == tuple(ranking_criteria()),
        "smallest_safe_width_selected": payload["ranking_proof"].get("smallest_safe_width_selected") is True,
        "selected_width_reduction_when_width_available": payload.get("selected_strategy_lane") == "WIDTH_REDUCTION",
        "exact_stop_proves_width_attempted": payload["exact_stop_proof"].get("width_reduction_attempted") is True,
        "zero_shear_override_proven": payload["zero_shear_override_proof"].get("zero_shear_candidate_seen") is True
        and payload["zero_shear_override_proof"].get("must_not_terminate_for_zero_utilisation") is True,
        "geometry_policy_proven": payload["geometry_restriction_proof"].get("width_reduction_attempted") is True
        and payload["geometry_restriction_proof"].get("candidate_updates_touch_prohibited_geometry") is False,
        "cta_intent_proof_only": payload["cta_intent_proof"].get("proof_only") is True
        and payload["cta_intent_proof"].get("rendered") is False
        and payload["cta_intent_proof"].get("applied") is False,
        "ladder_hash_stable": result.ladder_hash == repeat.ladder_hash,
        "runtime_has_no_page_ui_imports": not forbidden_hits,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if forbidden_hits:
        failures.append(f"forbidden_runtime_terms:{forbidden_hits}")
    snapshot = {
        "schema": "shear_overdesign_governs_runtime_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "contract_lane_order": list(shear_overdesign_contract_lane_order()),
        "lane_policy_keys": sorted(policies),
        "runtime": {
            "status": result.status,
            "selected_strategy_lane": result.selected_strategy_lane,
            "candidate_count": len(result.candidate_repairs),
            "accepted_count": len(result.accepted_lane_evidence),
            "rejected_count": len(result.rejected_lane_evidence),
            "ladder_hash": result.ladder_hash,
            "repeat_ladder_hash": repeat.ladder_hash,
        },
        "runtime_boundary": {
            "forbidden_runtime_terms": forbidden_hits,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("SHEAR_OVERDESIGN_GOVERNS runtime FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("SHEAR_OVERDESIGN_GOVERNS runtime PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
