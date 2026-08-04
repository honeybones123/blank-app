"""Proof snapshot for the BENDING_FAIL_GOVERNS contract ladder runtime.

This verifies the new family-owned runtime shape only. It does not prove parity
against the old implementation.
"""

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

from design_brain.candidate_evaluation import (  # noqa: E402
    BeamCandidateEvaluation,
    BeamCandidateInput,
    BeamCandidateUpdate,
    build_candidate_state_hash,
)
from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    internal_strategy_lanes,
    load_bending_fail_governs_contract,
)
from design_brain.families.bending_fail_governs.runtime import (  # noqa: E402
    BendingFailGovernsResult,
    bending_fail_governs_contract_lane_order,
    canonical_bending_fail_governs_lane_id,
    run_bending_fail_governs_ladder_runtime,
)


EXPECTED_CONTRACT_ORDER = (
    "GEOMETRY_SANITY",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "MULTI_LAYER_REO",
    "DEPTH_INCREASE",
    "WIDTH_INCREASE",
    "EXACT_STOP",
    "NO_VALID_STRATEGY",
)

REQUIRED_RESULT_FIELDS = {
    "selected_strategy_lane",
    "ladder_trace",
    "selected_recommendation",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "repair_reason_proof",
    "blocked_reason",
    "terminal_status",
    "repair_blocked",
    "blocked_reason_source",
    "internal_cap_only",
    "hard_blocker_proven",
    "contract_strategy_exhaustion_proven",
    "contract_strategies_checked",
    "contract_strategies_blocked",
    "contract_strategies_remaining",
    "implementation_caps_hit",
    "geometry_locks_used",
    "project_constraints_used",
    "detailing_constraints_used",
    "cta_intent_proof",
    "ladder_hash",
}

FORBIDDEN_PROOF_KEYS = {
    "apply_routing",
    "button_contract",
    "button_label",
    "publication",
    "published_item",
    "rendered_button",
    "rendered_html",
    "session",
    "session_state",
    "source_precedence",
    "ui",
    "visible_wording",
}


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_governs_ladder_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_ladder_runtime_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_GOVERNS Ladder Runtime Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "This proves the contract-order runtime shape only.",
                "It does not prove parity against the old implementation.",
                "",
                "## Checks",
                "",
                f"- contract loads: `{snapshot['checks']['contract_loads']}`",
                f"- runtime order equals contract order: `{snapshot['checks']['runtime_order_equals_contract_order']}`",
                f"- runtime order equals required order: `{snapshot['checks']['runtime_order_equals_required_order']}`",
                f"- required result fields exist: `{snapshot['checks']['required_result_fields_exist']}`",
                f"- ladder hash stable: `{snapshot['checks']['ladder_hash_stable']}`",
                f"- CTA intent proof only: `{snapshot['checks']['cta_intent_proof_only']}`",
                f"- forbidden proof fields absent: `{snapshot['checks']['forbidden_proof_fields_absent']}`",
                "",
                "## Runtime Order",
                "",
                "```text",
                " -> ".join(snapshot["runtime_lane_order"]),
                "```",
                "",
                "## Scenario Hashes",
                "",
                *[
                    f"- `{case['case']}`: `{case['ladder_hash']}`"
                    for case in snapshot["cases"]
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PROOF_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden_keys(child))
    return found


def _base_state() -> dict[str, Any]:
    return {
        "beam": {"depth_mm": 600.0, "width_mm": 300.0, "span_mm": 6000.0},
        "materials": {"fc_mpa": 40.0, "fsy_mpa": 500.0},
        "actions": {"m_star_knm": 920.0, "v_star_kn": 150.0},
        "reinforcement": {"bottom_bar_count": 4, "bottom_bar_diameter_mm": 20},
    }


def _lane_updates() -> dict[str, dict[str, Any]]:
    return {
        "GEOMETRY_SANITY": {},
        "DEPTH_INCREASE": {"beam": {"depth_mm": 625.0}},
        "SINGLE_LAYER_BOTTOM_REO": {"reinforcement": {"bottom_bar_count": 5}},
        "LARGER_BAR": {"reinforcement": {"bottom_bar_diameter_mm": 24}},
        "WIDTH_INCREASE": {"beam": {"width_mm": 350.0}},
        "MULTI_LAYER_REO": {"reinforcement": {"bottom_layer_count": 2}},
        "EXACT_STOP": {},
        "NO_VALID_STRATEGY": {},
    }


def _evaluation(
    *,
    candidate_input: BeamCandidateInput,
    candidate_update: BeamCandidateUpdate,
    lane: str,
    accepted: bool,
    reason: str,
    bending_utilisation: float,
    terminal_status: str | None = None,
    hard_blocker_proven: bool = False,
    contract_strategy_exhaustion_proven: bool = False,
    internal_cap_only: bool = False,
) -> BeamCandidateEvaluation:
    status = {
        "accepted": accepted,
        "lane_result": reason,
    }
    if terminal_status:
        status["terminal_status"] = terminal_status
    if lane == "NO_VALID_STRATEGY":
        status["blocked_reason"] = reason
        status["hard_blocker_proven"] = bool(hard_blocker_proven)
        status["contract_strategy_exhaustion_proven"] = bool(contract_strategy_exhaustion_proven)
        status["internal_cap_only"] = bool(internal_cap_only)
        if hard_blocker_proven:
            status["geometry_locks_used"] = ["geometry_locked"]
        if contract_strategy_exhaustion_proven:
            status["contract_strategies_checked"] = list(EXPECTED_CONTRACT_ORDER[:-2])
            status["contract_strategies_blocked"] = ["MULTI_LAYER_REO"]
        if internal_cap_only:
            status["implementation_caps_hit"] = ["candidate cap reached"]
    return BeamCandidateEvaluation(
        input_hash=candidate_input.state_hash,
        candidate_state_hash=build_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        update_hash=candidate_update.update_hash,
        bending_utilisation=bending_utilisation,
        shear_utilisation=0.72,
        serviceability_status={"deflection": "PASS", "crack": "PASS"},
        geometry_status={"status": "CHECKED"},
        detailing_status={"status": "CHECKED"},
        spacing_status={"status": "CHECKED"},
        capacity_summary={"source": "synthetic_evaluator_shape"},
        failure_flags={"bending_fail": bending_utilisation > 1.0},
        engineering_status=status,
    ).with_evaluation_hash()


def _run_case(
    *,
    name: str,
    accept_lane: str,
    terminal_no_valid: bool = False,
    cap_only_no_valid: bool = False,
) -> dict[str, Any]:
    order = list(EXPECTED_CONTRACT_ORDER)
    calls: list[str] = []

    def evaluator(candidate_input: BeamCandidateInput, candidate_update: BeamCandidateUpdate) -> BeamCandidateEvaluation:
        lane = order[len(calls)]
        calls.append(lane)
        if (terminal_no_valid or cap_only_no_valid) and lane == "NO_VALID_STRATEGY":
            return _evaluation(
                candidate_input=candidate_input,
                candidate_update=candidate_update,
                lane=lane,
                accepted=True,
                reason="candidate cap reached" if cap_only_no_valid else "NO_VALID_STRATEGY",
                bending_utilisation=1.18,
                terminal_status="NO_VALID_STRATEGY",
                hard_blocker_proven=terminal_no_valid,
                contract_strategy_exhaustion_proven=terminal_no_valid,
                internal_cap_only=cap_only_no_valid,
            )
        accepted = lane == accept_lane
        terminal_status = "EXACT_STOP" if lane == "EXACT_STOP" and accepted else None
        return _evaluation(
            candidate_input=candidate_input,
            candidate_update=candidate_update,
            lane=lane,
            accepted=accepted,
            reason="ACCEPTED" if accepted else "REJECTED",
            bending_utilisation=0.94 if accepted else 1.18,
            terminal_status=terminal_status,
        )

    result = run_bending_fail_governs_ladder_runtime(
        base_state=_base_state(),
        lane_candidate_updates=_lane_updates(),
        evaluate_candidate=evaluator,
    )
    repeat_calls: list[str] = []

    def repeat_evaluator(candidate_input: BeamCandidateInput, candidate_update: BeamCandidateUpdate) -> BeamCandidateEvaluation:
        lane = order[len(repeat_calls)]
        repeat_calls.append(lane)
        if (terminal_no_valid or cap_only_no_valid) and lane == "NO_VALID_STRATEGY":
            return _evaluation(
                candidate_input=candidate_input,
                candidate_update=candidate_update,
                lane=lane,
                accepted=True,
                reason="candidate cap reached" if cap_only_no_valid else "NO_VALID_STRATEGY",
                bending_utilisation=1.18,
                terminal_status="NO_VALID_STRATEGY",
                hard_blocker_proven=terminal_no_valid,
                contract_strategy_exhaustion_proven=terminal_no_valid,
                internal_cap_only=cap_only_no_valid,
            )
        accepted = lane == accept_lane
        terminal_status = "EXACT_STOP" if lane == "EXACT_STOP" and accepted else None
        return _evaluation(
            candidate_input=candidate_input,
            candidate_update=candidate_update,
            lane=lane,
            accepted=accepted,
            reason="ACCEPTED" if accepted else "REJECTED",
            bending_utilisation=0.94 if accepted else 1.18,
            terminal_status=terminal_status,
        )

    repeat = run_bending_fail_governs_ladder_runtime(
        base_state=_base_state(),
        lane_candidate_updates=_lane_updates(),
        evaluate_candidate=repeat_evaluator,
    )
    payload = result.to_dict()
    return {
        "case": name,
        "selected_strategy_lane": result.selected_strategy_lane,
        "called_lanes": calls,
        "trace_lanes": [row.get("lane_id") for row in result.ladder_trace],
        "accepted_lane_evidence": list(result.accepted_lane_evidence),
        "rejected_lane_evidence": list(result.rejected_lane_evidence),
        "selected_recommendation": result.selected_recommendation,
        "repair_reason_proof": result.repair_reason_proof,
        "cta_intent_proof": result.cta_intent_proof,
        "blocked_reason": result.blocked_reason,
        "terminal_status": result.terminal_status,
        "repair_blocked": result.repair_blocked,
        "blocked_reason_source": result.blocked_reason_source,
        "internal_cap_only": result.internal_cap_only,
        "hard_blocker_proven": result.hard_blocker_proven,
        "contract_strategy_exhaustion_proven": result.contract_strategy_exhaustion_proven,
        "contract_strategies_checked": list(result.contract_strategies_checked),
        "contract_strategies_blocked": list(result.contract_strategies_blocked),
        "contract_strategies_remaining": list(result.contract_strategies_remaining),
        "implementation_caps_hit": list(result.implementation_caps_hit),
        "geometry_locks_used": list(result.geometry_locks_used),
        "project_constraints_used": list(result.project_constraints_used),
        "detailing_constraints_used": list(result.detailing_constraints_used),
        "ladder_hash": result.ladder_hash,
        "repeat_ladder_hash": repeat.ladder_hash,
        "ladder_hash_stable": result.ladder_hash == repeat.ladder_hash,
        "forbidden_keys": sorted(_walk_forbidden_keys(payload)),
    }


def main() -> int:
    contract = load_bending_fail_governs_contract()
    contract_lanes = tuple(
        canonical_bending_fail_governs_lane_id(str(lane.get("lane_id") or ""))
        for lane in sorted(internal_strategy_lanes(), key=lambda item: int(item.get("lane_index") or 0))
    )
    runtime_order = bending_fail_governs_contract_lane_order()
    result_fields = {field.name for field in fields(BendingFailGovernsResult)}
    cases = [
        _run_case(name="depth_lane_accepts", accept_lane="DEPTH_INCREASE"),
        _run_case(name="exact_stop_terminal", accept_lane="EXACT_STOP"),
        _run_case(
            name="no_valid_strategy_terminal",
            accept_lane="NO_VALID_STRATEGY",
            terminal_no_valid=True,
        ),
        _run_case(
            name="cap_only_exhaustion_not_repair_blocked",
            accept_lane="NO_VALID_STRATEGY",
            cap_only_no_valid=True,
        ),
    ]

    checks = {
        "contract_loads": isinstance(contract, dict) and bool(contract),
        "runtime_order_equals_contract_order": runtime_order == contract_lanes,
        "runtime_order_equals_required_order": runtime_order == EXPECTED_CONTRACT_ORDER,
        "required_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(result_fields),
        "ladder_hash_stable": all(case["ladder_hash_stable"] for case in cases),
        "cta_intent_proof_only": all(
            case["cta_intent_proof"].get("proof_only") is True
            and case["cta_intent_proof"].get("product_driving") is False
            and case["cta_intent_proof"].get("rendered") is False
            and case["cta_intent_proof"].get("applied") is False
            for case in cases
        ),
        "cap_only_exhaustion_not_repair_blocked": any(
            case["case"] == "cap_only_exhaustion_not_repair_blocked"
            and case["repair_blocked"] is False
            and case["blocked_reason"] is None
            and case["internal_cap_only"] is True
            for case in cases
        ),
        "no_valid_strategy_requires_contract_proof": any(
            case["case"] == "no_valid_strategy_terminal"
            and case["repair_blocked"] is True
            and case["blocked_reason_source"] == "family_contract_blocker_proof"
            and case["hard_blocker_proven"] is True
            and case["contract_strategy_exhaustion_proven"] is True
            for case in cases
        ),
        "forbidden_proof_fields_absent": all(not case["forbidden_keys"] for case in cases),
    }
    snapshot = {
        "schema": "bending_fail_governs_ladder_runtime_snapshot.v1",
        "result": "PASS" if all(checks.values()) else "FAIL",
        "contract_schema": contract.get("schema"),
        "runtime_lane_order": list(runtime_order),
        "contract_lane_order": list(contract_lanes),
        "required_lane_order": list(EXPECTED_CONTRACT_ORDER),
        "required_result_fields": sorted(REQUIRED_RESULT_FIELDS),
        "actual_result_fields": sorted(result_fields),
        "checks": checks,
        "cases": cases,
        "scope_limits": {
            "proves_runtime_shape": True,
            "proves_old_implementation_parity": False,
            "moves_cta_rendering": False,
            "moves_publication": False,
            "moves_apply_routing": False,
            "moves_visible_wording": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)

    if snapshot["result"] != "PASS":
        print("BENDING_FAIL_GOVERNS ladder runtime FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("BENDING_FAIL_GOVERNS ladder runtime PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
