"""Proof snapshot for the BENDING_OVERDESIGN_GOVERNS contract runtime."""

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
RUNTIME_PATH = ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "runtime.py"

from design_brain.bending_overdesign_candidate_evaluation import (  # noqa: E402
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    build_bending_overdesign_candidate_state_hash,
)
from design_brain.families.bending_overdesign_governs.contract import (  # noqa: E402
    lane_proof_policies,
    minimum_reinforcement_geometry_relief_rules,
    ranking_criteria,
)
from design_brain.families.bending_overdesign_governs.runtime import (  # noqa: E402
    BendingOverdesignGovernsResult,
    bending_overdesign_contract_lane_order,
    run_bending_overdesign_governs_runtime,
)


EXPECTED_CONTRACT_ORDER = (
    "BOTTOM_REINFORCEMENT_REDUCTION",
    "LAYER_REDUCTION",
    "WIDTH_REDUCTION",
    "DEPTH_REDUCTION",
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
    "minimum_reinforcement_proof",
    "geometry_compliance_proof",
    "restart_proof",
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
        "Mstar": 220.0,
        "phiMu": 330.0,
        "bending_utilisation": 0.67,
        "As": 2260.0,
        "As_min": 950.0,
        "bot1_count": 5,
        "db_bot_1": 24,
        "bot_row_count": 1,
    }


def _numbers_for_update(updates: dict[str, Any]) -> tuple[float, float, bool, bool, float]:
    bot_count = int(updates.get("bot1_count") or updates.get("bot_row_1_bars") or 0)
    bot_dia = int(updates.get("db_bot_1") or updates.get("bot_row_1_dia") or 0)
    if updates.get("b") == 275.0 and bot_count == 4 and bot_dia == 20:
        return 0.82, 1256.0, True, True, 0.58
    if updates.get("b") == 275.0 and updates.get("bot_row_count") == 1 and updates.get("bot2_count") == 0:
        return 0.81, 1608.0, True, True, 0.68
    if bot_count == 4 and bot_dia == 24 and "b" not in updates and "D" not in updates:
        return 0.86, 1809.6, True, True, 0.82
    if bot_count == 4 and bot_dia == 20 and "b" not in updates and "D" not in updates:
        return 0.96, 1256.0, True, True, 0.61
    if bot_count == 3 and bot_dia == 24 and "b" not in updates and "D" not in updates:
        return 0.91, 1357.2, True, True, 0.68
    if bot_count == 3 and bot_dia == 20 and "b" not in updates and "D" not in updates:
        return 1.04, 942.0, False, True, 0.48
    if updates.get("bot_row_count") == 1 and updates.get("bot2_count") == 0:
        return 0.90, 1608.0, True, True, 0.72
    if updates.get("b") == 275.0:
        return 0.88, 2260.0, True, True, 0.94
    if updates.get("D") == 475.0:
        return 0.93, 2260.0, True, True, 0.95
    return 0.67, 2260.0, True, True, 1.0


def _evaluation(
    candidate_input: BendingOverdesignCandidateInput,
    candidate_update: BendingOverdesignCandidateUpdate,
) -> BendingOverdesignCandidateEvaluation:
    updates = dict(candidate_update.updates)
    utilisation, as_after, compliant, geometry_ok, cost = _numbers_for_update(updates)
    as_min = float(candidate_input.base_state.get("As_min") or 0.0)
    beam_width = float(updates.get("b") or candidate_input.base_state.get("b") or 300.0)
    beam_depth = float(updates.get("D") or candidate_input.base_state.get("D") or 500.0)
    valid = compliant and as_after >= as_min and geometry_ok
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
        geometry_compliance_status={"status": "PASS" if geometry_ok else "FAIL"},
        beam_proportion_status={"status": "PASS"},
        reinforcement_quantity={"after": as_after},
        beam_volume={"after": beam_width * beam_depth},
        cost_proxy={"after": cost},
        capacity_summary={"fixture": "bending_overdesign_runtime"},
        failure_flags={"underdesign_created": not compliant, "below_minimum_reinforcement": as_after < as_min},
        engineering_status={"candidate_valid": valid, "result": "ACCEPTED" if valid else "REJECTED"},
    ).with_evaluation_hash()


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_overdesign_governs_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_governs_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_OVERDESIGN_GOVERNS Runtime Snapshot",
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
    result = run_bending_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    repeat = run_bending_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluation)
    payload = result.to_dict()
    fields_present = {field.name for field in fields(BendingOverdesignGovernsResult)}
    policies = lane_proof_policies()
    runtime_source = RUNTIME_PATH.read_text(encoding="utf-8", errors="replace")
    forbidden_hits = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    candidate_updates = [dict(row.get("updates") or {}) for row in payload.get("candidate_repairs") or []]
    rejected_below_min = [
        row
        for row in payload.get("rejected_lane_evidence") or []
        if (row.get("minimum_reinforcement_status") or {}).get("discard_before_ranking") is True
    ]
    checks = {
        "contract_lane_order_exact": bending_overdesign_contract_lane_order() == EXPECTED_CONTRACT_ORDER,
        "required_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(fields_present),
        "bottom_reinforcement_policy_represented": any(
            int(update.get("bot1_count") or update.get("bot_row_1_bars") or 0) == 4
            and int(update.get("db_bot_1") or update.get("bot_row_1_dia") or 0) == 20
            for update in candidate_updates
        ),
        "layer_policy_represented": any(update.get("bot_row_count") == 1 and update.get("bot2_count") == 0 for update in candidate_updates),
        "width_policy_represented": any(update.get("b") == 275.0 for update in candidate_updates),
        "width_min_reinforcement_relief_policy_present": bool(minimum_reinforcement_geometry_relief_rules())
        and (policies.get("width_reduction") or {}).get("minimum_reinforcement_relief") is True,
        "depth_min_reinforcement_relief_policy_present": bool(minimum_reinforcement_geometry_relief_rules())
        and (policies.get("depth_reduction") or {}).get("minimum_reinforcement_relief") is True,
        "width_plus_reinforcement_restart_candidate_represented": any(
            update.get("b") == 275.0 and update.get("bot1_count") == 4 and update.get("db_bot_1") == 20
            for update in candidate_updates
        )
        and any(
            update.get("b") == 275.0 and update.get("bot_row_count") == 1 and update.get("bot2_count") == 0
            for update in candidate_updates
        ),
        "depth_policy_represented": any(update.get("D") == 475.0 for update in candidate_updates),
        "depth_plus_reinforcement_restart_candidate_represented": any(
            update.get("D") == 475.0 and update.get("bot1_count") == 4 and update.get("db_bot_1") == 20
            for update in candidate_updates
        )
        and any(
            update.get("D") == 475.0 and update.get("bot_row_count") == 1 and update.get("bot2_count") == 0
            for update in candidate_updates
        ),
        "ranking_criteria_match_contract": tuple(payload["ranking_proof"].get("criteria") or ()) == tuple(ranking_criteria()),
        "selected_inside_target_band": payload["exact_stop_proof"].get("target_band_selected") is True,
        "selected_bottom_reinforcement_candidate": payload.get("selected_strategy_lane") == "BOTTOM_REINFORCEMENT_REDUCTION",
        "below_minimum_discarded_before_ranking": payload["minimum_reinforcement_proof"].get("below_minimum_rejection_count", 0) >= 1
        and payload["minimum_reinforcement_proof"].get("below_minimum_candidates_ranked") is False
        and bool(rejected_below_min),
        "minimum_reinforcement_geometry_relief_checked": payload["minimum_reinforcement_proof"].get(
            "minimum_reinforcement_geometry_relief_checked"
        )
        is True
        and payload["minimum_reinforcement_proof"].get("width_reduction_relief_candidate_count", 0) >= 2
        and payload["minimum_reinforcement_proof"].get("depth_reduction_relief_candidate_count", 0) >= 2,
        "geometry_reductions_restart_reinforcement_search": payload["restart_proof"].get(
            "all_geometry_reductions_restart_bottom_reinforcement_search"
        )
        is True
        and payload["restart_proof"].get("all_geometry_reductions_restart_layer_search") is True,
        "restart_proof_counts_width_reinforcement_relief": payload["restart_proof"].get(
            "minimum_reinforcement_geometry_relief_checked"
        )
        is True
        and payload["restart_proof"].get("width_reduction_restarted_reinforcement_candidate_count", 0) >= 2
        and payload["restart_proof"].get("depth_reduction_restarted_reinforcement_candidate_count", 0) >= 2,
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
        "schema": "bending_overdesign_governs_runtime_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "contract_lane_order": list(bending_overdesign_contract_lane_order()),
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
        print("BENDING_OVERDESIGN_GOVERNS runtime FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("BENDING_OVERDESIGN_GOVERNS runtime PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
