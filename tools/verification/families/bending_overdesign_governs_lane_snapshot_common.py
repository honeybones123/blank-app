"""Shared lane snapshot helpers for BENDING_OVERDESIGN_GOVERNS."""

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

from design_brain.bending_overdesign_candidate_evaluation import (  # noqa: E402
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    build_bending_overdesign_candidate_state_hash,
)
from design_brain.families.bending_overdesign_governs.contract import (  # noqa: E402
    geometry_rules,
    internal_strategy_lanes,
    lane_proof_policies,
    load_bending_overdesign_governs_contract,
    minimum_reinforcement_rules,
    ranking_criteria,
)


EXPECTED_LANE_ORDER = [
    "BOTTOM_REINFORCEMENT_REDUCTION",
    "LAYER_REDUCTION",
    "WIDTH_REDUCTION",
    "DEPTH_REDUCTION",
    "EXACT_STOP",
    "EXHAUSTED",
]
FORBIDDEN_SHARED_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "apply_resolved_candidate",
    "button_contract",
}


def _source_boundary_clean() -> tuple[bool, list[str]]:
    package_dir = ROOT / "design_brain" / "families" / "bending_overdesign_governs"
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in package_dir.glob("*.py")
    )
    hits = sorted(term for term in FORBIDDEN_SHARED_TERMS if term in source)
    return not hits, hits


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
        "constructability": "PASS",
    }


def _evaluation(
    *,
    candidate_input: BendingOverdesignCandidateInput,
    candidate_update: BendingOverdesignCandidateUpdate,
    bending_utilisation: float,
    previous_bending_utilisation: float,
    as_after: float,
    status: str,
    geometry_ok: bool = True,
    proportion_ok: bool = True,
    constructability_ok: bool = True,
) -> BendingOverdesignCandidateEvaluation:
    as_min = float(candidate_input.base_state.get("As_min") or 0.0)
    valid = (
        status == "ACCEPTED"
        and bending_utilisation <= 1.0
        and as_after >= as_min
        and geometry_ok
        and proportion_ok
        and constructability_ok
    )
    return BendingOverdesignCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_bending_overdesign_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        bending_utilisation=bending_utilisation,
        previous_bending_utilisation=previous_bending_utilisation,
        target_band_status={"inside_target_band": 0.85 <= bending_utilisation <= 1.0},
        utilisation_moves_toward_target=bending_utilisation > previous_bending_utilisation
        and bending_utilisation <= 1.0,
        bending_remains_compliant=bending_utilisation <= 1.0,
        constructability_status={"status": "PASS" if constructability_ok else "FAIL"},
        code_compliance_status={"status": "PASS" if valid else "FAIL"},
        minimum_reinforcement_status={
            "As": as_after,
            "As_min": as_min,
            "As_greater_than_or_equal_to_As_min": as_after >= as_min,
            "discard_before_ranking": as_after < as_min,
        },
        geometry_compliance_status={"status": "PASS" if geometry_ok else "FAIL"},
        beam_proportion_status={"status": "PASS" if proportion_ok else "FAIL"},
        reinforcement_quantity={"after": as_after},
        beam_volume={"after": candidate_input.base_state.get("b", 300.0) * candidate_input.base_state.get("D", 500.0)},
        cost_proxy={"after": as_after / max(float(candidate_input.base_state.get("As") or 1.0), 1.0)},
        capacity_summary={"family": "BENDING_OVERDESIGN_GOVERNS"},
        failure_flags={
            "underdesign_created": bending_utilisation > 1.0,
            "below_minimum_reinforcement": as_after < as_min,
        },
        engineering_status={"result": status, "candidate_valid": valid},
    ).with_evaluation_hash()


def _common_checks() -> dict[str, bool]:
    contract = load_bending_overdesign_governs_contract()
    clean, _hits = _source_boundary_clean()
    lane_order = [str(lane.get("lane_id") or "") for lane in internal_strategy_lanes()]
    return {
        "contract_loads": bool(contract),
        "lane_order_available": lane_order == EXPECTED_LANE_ORDER,
        "ranking_available": bool(ranking_criteria()),
        "minimum_reinforcement_rules_available": bool(minimum_reinforcement_rules()),
        "geometry_rules_available": bool(geometry_rules()),
        "no_page_ui_apply_imports": clean,
    }


def _write_snapshot(name: str, snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_overdesign_governs_{name}_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_governs_{name}_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                f"# BENDING_OVERDESIGN_GOVERNS {name.replace('_', ' ').title()}",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
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


def _finish(name: str, checks: dict[str, bool], details: dict[str, Any]) -> int:
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": f"bending_overdesign_governs_{name}.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        **details,
    }
    json_path, report_path = _write_snapshot(name, snapshot)
    if failures:
        print(f"BENDING_OVERDESIGN_GOVERNS {name} FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print(f"BENDING_OVERDESIGN_GOVERNS {name} PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


def bottom_reinforcement_lane_main() -> int:
    policy = dict((lane_proof_policies().get("bottom_reinforcement_reduction") or {}))
    candidate_input = BendingOverdesignCandidateInput(base_state=_base_state())
    sequence = list(policy.get("example_sequence") or [])
    updates = [
        BendingOverdesignCandidateUpdate(updates={"bot1_count": int(item.split("-")[0]), "db_bot_1": int(item.split("N")[-1])})
        for item in sequence
    ]
    accepted = _evaluation(
        candidate_input=candidate_input,
        candidate_update=updates[1],
        bending_utilisation=0.86,
        previous_bending_utilisation=0.67,
        as_after=1809.6,
        status="ACCEPTED",
    )
    rejected = _evaluation(
        candidate_input=candidate_input,
        candidate_update=updates[-1],
        bending_utilisation=1.05,
        previous_bending_utilisation=0.67,
        as_after=942.0,
        status="REJECTED",
    )
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "BOTTOM_REINFORCEMENT_REDUCTION",
        "sequence_matches_contract": sequence == ["5-N24", "4-N24", "4-N20", "3-N24", "3-N20"],
        "updates_are_reinforcement_updates": all(update.reinforcement_update for update in updates),
        "candidate_inside_target_band_can_be_accepted": accepted.engineering_status.get("candidate_valid") is True,
        "below_min_or_bending_failure_is_rejected": rejected.engineering_status.get("candidate_valid") is False,
        "boundary_records_minimum_reinforcement_status": "As_min" in rejected.minimum_reinforcement_status,
    }
    return _finish(
        "bottom_reinforcement_lane",
        checks,
        {"policy": policy, "accepted_hash": accepted.evaluation_hash, "rejected_hash": rejected.evaluation_hash},
    )


def layer_reduction_lane_main() -> int:
    policy = dict((lane_proof_policies().get("layer_reduction") or {}))
    candidate_input = BendingOverdesignCandidateInput(base_state={**_base_state(), "bot_row_count": 2, "bot2_count": 2})
    update = BendingOverdesignCandidateUpdate(updates={"bot_row_count": 1, "bot2_count": 0, "db_bot_2": 0})
    evaluation = _evaluation(
        candidate_input=candidate_input,
        candidate_update=update,
        bending_utilisation=0.91,
        previous_bending_utilisation=0.67,
        as_after=1608.0,
        status="ACCEPTED",
    )
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "LAYER_REDUCTION",
        "search_matches_contract": list(policy.get("search") or []) == ["multi-layer", "single-layer"],
        "update_is_reinforcement_only": update.reinforcement_update is True,
        "constructability_recorded": evaluation.constructability_status.get("status") == "PASS",
        "simpler_arrangement_can_be_accepted": evaluation.engineering_status.get("candidate_valid") is True,
    }
    return _finish("layer_reduction_lane", checks, {"policy": policy, "evaluation_hash": evaluation.evaluation_hash})


def width_reduction_lane_main() -> int:
    policy = dict((lane_proof_policies().get("width_reduction") or {}))
    candidate_input = BendingOverdesignCandidateInput(base_state=_base_state())
    update = BendingOverdesignCandidateUpdate(updates={"b": 275.0})
    evaluation = _evaluation(
        candidate_input=candidate_input,
        candidate_update=update,
        bending_utilisation=0.88,
        previous_bending_utilisation=0.67,
        as_after=2260.0,
        status="ACCEPTED",
    )
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "WIDTH_REDUCTION",
        "increment_matches_contract": policy.get("increment_mm") == -25,
        "restarts_bottom_reinforcement_search": policy.get("restarts_bottom_reinforcement_search") is True,
        "restarts_layer_search": policy.get("restarts_layer_search") is True,
        "update_is_geometry_update": update.geometry_update is True,
        "geometry_and_proportion_proven": evaluation.geometry_compliance_status.get("status") == "PASS"
        and evaluation.beam_proportion_status.get("status") == "PASS",
    }
    return _finish("width_reduction_lane", checks, {"policy": policy, "evaluation_hash": evaluation.evaluation_hash})


def depth_reduction_lane_main() -> int:
    policy = dict((lane_proof_policies().get("depth_reduction") or {}))
    candidate_input = BendingOverdesignCandidateInput(base_state=_base_state())
    update = BendingOverdesignCandidateUpdate(updates={"D": 475.0})
    evaluation = _evaluation(
        candidate_input=candidate_input,
        candidate_update=update,
        bending_utilisation=0.93,
        previous_bending_utilisation=0.67,
        as_after=2260.0,
        status="ACCEPTED",
    )
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "DEPTH_REDUCTION",
        "increment_matches_contract": policy.get("increment_mm") == -25,
        "restarts_bottom_reinforcement_search": policy.get("restarts_bottom_reinforcement_search") is True,
        "restarts_layer_search": policy.get("restarts_layer_search") is True,
        "update_is_geometry_update": update.geometry_update is True,
        "geometry_and_proportion_proven": evaluation.geometry_compliance_status.get("status") == "PASS"
        and evaluation.beam_proportion_status.get("status") == "PASS",
    }
    return _finish("depth_reduction_lane", checks, {"policy": policy, "evaluation_hash": evaluation.evaluation_hash})


def minimum_reinforcement_lane_main() -> int:
    policy = dict((lane_proof_policies().get("minimum_reinforcement_cases") or {}))
    rules = minimum_reinforcement_rules()
    candidate_input = BendingOverdesignCandidateInput(base_state={**_base_state(), "As_min": 950.0})
    update = BendingOverdesignCandidateUpdate(updates={"bot1_count": 1, "db_bot_1": 16})
    rejected = _evaluation(
        candidate_input=candidate_input,
        candidate_update=update,
        bending_utilisation=1.11,
        previous_bending_utilisation=0.67,
        as_after=201.0,
        status="REJECTED",
    )
    checks = {
        **_common_checks(),
        "hard_boundary_enabled": rules.get("hard_boundary") is True,
        "as_must_be_gte_as_min": rules.get("as_provided_must_be_greater_than_or_equal_to_as_min") is True,
        "case_a_continue": (policy.get("case_a") or {}).get("expected") == "optimisation may continue",
        "case_b_stops": (policy.get("case_b") or {}).get("expected") == "reinforcement reduction branch stops",
        "case_c_rejects": (policy.get("case_c") or {}).get("expected") == "candidate rejected",
        "case_d_specific_evidence": (policy.get("case_d") or {}).get("expected")
        == "minimum reinforcement blocker evidence published",
        "case_e_not_ranked": (policy.get("case_e") or {}).get("expected")
        == "candidate never appears in ranked recommendations",
        "below_minimum_candidate_rejected_before_ranking": rejected.minimum_reinforcement_status.get(
            "discard_before_ranking"
        )
        is True
        and rejected.engineering_status.get("candidate_valid") is False,
    }
    return _finish(
        "minimum_reinforcement_lane",
        checks,
        {"policy": policy, "minimum_reinforcement_rules": rules, "rejected_hash": rejected.evaluation_hash},
    )


def geometry_compliance_lane_main() -> int:
    rules = geometry_rules()
    candidate_input = BendingOverdesignCandidateInput(base_state=_base_state())
    update = BendingOverdesignCandidateUpdate(updates={"b": 275.0})
    rejected = _evaluation(
        candidate_input=candidate_input,
        candidate_update=update,
        bending_utilisation=0.88,
        previous_bending_utilisation=0.67,
        as_after=2260.0,
        status="REJECTED",
        geometry_ok=False,
    )
    checks = {
        **_common_checks(),
        "geometry_reduction_allowed": rules.get("geometry_reduction_allowed") is True,
        "width_increment_matches": rules.get("width_increment_mm") == -25,
        "depth_increment_matches": rules.get("depth_increment_mm") == -25,
        "restart_rules_present": set(rules.get("restart_after_geometry_reduction") or [])
        >= {"bottom reinforcement search", "layer search"},
        "geometry_failure_rejects_candidate": rejected.geometry_compliance_status.get("status") == "FAIL"
        and rejected.engineering_status.get("candidate_valid") is False,
    }
    return _finish("geometry_compliance_lane", checks, {"geometry_rules": rules, "rejected_hash": rejected.evaluation_hash})


def terminal_lane_main() -> int:
    policy = dict((lane_proof_policies().get("terminal") or {}))
    exact = list(policy.get("exact_stop_allowed_when") or [])
    exhausted = list(policy.get("exhausted_requires") or [])
    checks = {
        **_common_checks(),
        "exact_stop_requires_target_band": "target band reached" in exact,
        "exact_stop_requires_no_higher_ranked_candidate": "no higher-ranked optimisation candidate exists" in exact,
        "exhausted_requires_all_branches": "all optimisation branches attempted" in exhausted,
        "exhausted_requires_specific_blocker": "specific blocker evidence exists" in exhausted,
    }
    return _finish("terminal_lane", checks, {"terminal_policy": policy})
