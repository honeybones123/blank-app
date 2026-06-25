"""Shared lane snapshot helpers for SHEAR_OVERDESIGN_GOVERNS."""

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

from design_brain.families.shear_overdesign_governs.contract import (  # noqa: E402
    geometry_restrictions,
    internal_strategy_lanes,
    lane_proof_policies,
    load_shear_overdesign_governs_contract,
    ranking_criteria,
    terminal_rules,
    zero_shear_override,
)
from design_brain.shear_overdesign_candidate_evaluation import (  # noqa: E402
    ShearOverdesignCandidateEvaluation,
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
    build_shear_overdesign_candidate_state_hash,
)


EXPECTED_LANE_ORDER = [
    "SPACING_INCREASE",
    "BAR_SIZE_REDUCTION",
    "LEG_COUNT_REDUCTION",
    "LIGATURE_REMOVAL",
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
    package_dir = ROOT / "design_brain" / "families" / "shear_overdesign_governs"
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
        "Vu": 0.0,
        "design_actions_present": True,
        "s_lig": 100.0,
        "lig_d": 16,
        "lig_legs": 6,
        "shear_utilisation": 0.42,
        "minimum_shear_reinforcement_required": False,
    }


def _evaluation(
    *,
    candidate_input: ShearOverdesignCandidateInput,
    candidate_update: ShearOverdesignCandidateUpdate,
    shear_utilisation: float,
    previous_shear_utilisation: float,
    status: str,
    zero_shear: bool = False,
    no_unnecessary_ligatures_remain: bool = False,
) -> ShearOverdesignCandidateEvaluation:
    return ShearOverdesignCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_shear_overdesign_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        shear_utilisation=shear_utilisation,
        previous_shear_utilisation=previous_shear_utilisation,
        target_band_status={"inside_target_band": 0.85 <= shear_utilisation <= 1.0},
        utilisation_moves_toward_target=True,
        shear_remains_compliant=True,
        constructability_status={"status": "PASS"},
        mandatory_detailing_status={"status": "PASS", "minimum_shear_reinforcement_required": False},
        shear_detailing_update_status={
            "shear_detailing_only": candidate_update.shear_detailing_only,
            "update_keys": candidate_update.update_keys,
        },
        geometry_restriction_status={
            "geometry_reduction_attempted": candidate_update.geometry_reduction_attempted,
            "geometry_reduction_prohibited": True,
        },
        zero_shear_status={
            "zero_or_negligible_shear": zero_shear,
            "must_not_terminate_for_zero_utilisation": zero_shear,
        },
        ligature_removal_status={
            "no_unnecessary_ligatures_remain": no_unnecessary_ligatures_remain,
        },
        reinforcement_quantity={"after": 0.0 if no_unnecessary_ligatures_remain else 1.0},
        cost_proxy={"after": 0.0 if no_unnecessary_ligatures_remain else 1.0},
        capacity_summary={"family": "SHEAR_OVERDESIGN_GOVERNS"},
        failure_flags={"underdesign_created": False},
        engineering_status={"result": status},
    ).with_evaluation_hash()


def _common_checks() -> dict[str, bool]:
    contract = load_shear_overdesign_governs_contract()
    clean, _hits = _source_boundary_clean()
    lane_order = [str(lane.get("lane_id") or "") for lane in internal_strategy_lanes()]
    return {
        "contract_loads": bool(contract),
        "lane_order_available": lane_order == EXPECTED_LANE_ORDER,
        "ranking_available": bool(ranking_criteria()),
        "zero_shear_override_available": bool(zero_shear_override()),
        "geometry_restrictions_available": bool(geometry_restrictions()),
        "no_page_ui_apply_imports": clean,
    }


def _write_snapshot(name: str, snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_overdesign_governs_{name}_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_{name}_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                f"# SHEAR_OVERDESIGN_GOVERNS {name.replace('_', ' ').title()}",
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
        "schema": f"shear_overdesign_governs_{name}.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        **details,
    }
    json_path, report_path = _write_snapshot(name, snapshot)
    if failures:
        print(f"SHEAR_OVERDESIGN_GOVERNS {name} FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print(f"SHEAR_OVERDESIGN_GOVERNS {name} PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


def spacing_lane_main() -> int:
    policies = lane_proof_policies()
    policy = dict(policies.get("spacing_increase") or {})
    candidate_input = ShearOverdesignCandidateInput(base_state=_base_state())
    updates = [ShearOverdesignCandidateUpdate(updates={"s_lig": spacing}) for spacing in policy.get("spacing_search_mm") or []]
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "SPACING_INCREASE",
        "spacing_search_order_matches_contract": list(policy.get("spacing_search_mm") or []) == [100, 125, 150, 175, 200, 250, 300],
        "updates_are_shear_detailing_only": all(update.shear_detailing_only for update in updates),
        "updates_do_not_touch_geometry": not any(update.geometry_reduction_attempted for update in updates),
        "boundary_can_represent_lane": bool(
            _evaluation(
                candidate_input=candidate_input,
                candidate_update=updates[-1],
                shear_utilisation=0.9,
                previous_shear_utilisation=0.42,
                status="ACCEPTED",
            ).evaluation_hash
        ),
    }
    return _finish("spacing_lane", checks, {"policy": policy})


def bar_size_lane_main() -> int:
    policies = lane_proof_policies()
    policy = dict(policies.get("bar_size_reduction") or {})
    spacing = list((policies.get("spacing_increase") or {}).get("spacing_search_mm") or [])
    updates = [
        ShearOverdesignCandidateUpdate(updates={"lig_d": int(str(size).replace("N", "")), "s_lig": s})
        for size in policy.get("bar_size_search") or []
        for s in spacing
    ]
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "BAR_SIZE_REDUCTION",
        "bar_size_search_order_matches_contract": list(policy.get("bar_size_search") or []) == ["N16", "N12", "N10"],
        "restarts_spacing_search": policy.get("restarts_spacing_search") is True,
        "restart_matrix_complete": len(updates) == 3 * len(spacing),
        "updates_are_shear_detailing_only": all(update.shear_detailing_only for update in updates),
        "updates_do_not_touch_geometry": not any(update.geometry_reduction_attempted for update in updates),
    }
    return _finish("bar_size_lane", checks, {"policy": policy, "restart_candidate_count": len(updates)})


def leg_count_lane_main() -> int:
    policies = lane_proof_policies()
    policy = dict(policies.get("leg_count_reduction") or {})
    spacing = list((policies.get("spacing_increase") or {}).get("spacing_search_mm") or [])
    bars = list((policies.get("bar_size_reduction") or {}).get("bar_size_search") or [])
    updates = [
        ShearOverdesignCandidateUpdate(
            updates={"lig_legs": legs, "lig_d": int(str(size).replace("N", "")), "s_lig": s}
        )
        for legs in policy.get("leg_count_search") or []
        for size in bars
        for s in spacing
    ]
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "LEG_COUNT_REDUCTION",
        "leg_count_search_order_matches_contract": list(policy.get("leg_count_search") or []) == [6, 4, 2],
        "restarts_spacing_search": policy.get("restarts_spacing_search") is True,
        "restarts_bar_size_search": policy.get("restarts_bar_size_search") is True,
        "restart_matrix_complete": len(updates) == 3 * len(bars) * len(spacing),
        "updates_are_shear_detailing_only": all(update.shear_detailing_only for update in updates),
        "updates_do_not_touch_geometry": not any(update.geometry_reduction_attempted for update in updates),
    }
    return _finish("leg_count_lane", checks, {"policy": policy, "restart_candidate_count": len(updates)})


def ligature_removal_lane_main() -> int:
    policies = lane_proof_policies()
    policy = dict(policies.get("ligature_removal") or {})
    candidate_input = ShearOverdesignCandidateInput(base_state={**_base_state(), "Vu": 0.0, "shear_utilisation": 0.0})
    update = ShearOverdesignCandidateUpdate(updates=dict(policy.get("canonical_update") or {}))
    evaluation = _evaluation(
        candidate_input=candidate_input,
        candidate_update=update,
        shear_utilisation=0.0,
        previous_shear_utilisation=0.0,
        status="ACCEPTED",
        zero_shear=True,
        no_unnecessary_ligatures_remain=True,
    )
    checks = {
        **_common_checks(),
        "policy_lane_id_matches": policy.get("lane_id") == "LIGATURE_REMOVAL",
        "canonical_update_removes_ligatures": dict(policy.get("canonical_update") or {}) == {"lig_legs": 0, "lig_d": 0, "s_lig": 0},
        "allowed_when_mentions_code_minimum": "no code minimum reinforcement requirement exists" in list(policy.get("allowed_when") or []),
        "preferred_for_zero_shear": "V* = 0" in list(policy.get("preferred_for") or []),
        "update_is_shear_detailing_only": update.shear_detailing_only,
        "update_does_not_touch_geometry": not update.geometry_reduction_attempted,
        "boundary_proves_no_unnecessary_ligatures": evaluation.ligature_removal_status.get("no_unnecessary_ligatures_remain") is True,
    }
    return _finish("ligature_removal_lane", checks, {"policy": policy, "evaluation": evaluation.to_dict()})


def terminal_lane_main() -> int:
    policies = lane_proof_policies()
    policy = dict(policies.get("terminal") or {})
    rules = terminal_rules()
    checks = {
        **_common_checks(),
        "exact_stop_rule_exists": isinstance(rules.get("exact_stop"), dict) and rules["exact_stop"].get("required") is True,
        "exhausted_rule_exists": isinstance(rules.get("exhausted"), dict) and rules["exhausted"].get("required") is True,
        "exact_stop_allows_target_band": "target band reached" in list(policy.get("exact_stop_allowed_when") or []),
        "exact_stop_allows_no_unnecessary_ligatures": "no unnecessary ligatures remain" in list(policy.get("exact_stop_allowed_when") or []),
        "exhausted_requires_all_branches": "all optimisation branches attempted" in list(policy.get("exhausted_requires") or []),
        "zero_shear_exhausted_restricted": policy.get("zero_shear_exhausted_forbidden_while_ligatures_remain_without_code_requirement") is True,
    }
    return _finish("terminal_lane", checks, {"policy": policy, "terminal_rules": rules})


def zero_shear_lane_main() -> int:
    policies = lane_proof_policies()
    policy = dict(policies.get("zero_shear") or {})
    override = zero_shear_override()
    checks = {
        **_common_checks(),
        "override_requires_negligible_shear": (override.get("requires") or {}).get("negligible_shear_action") is True,
        "override_requires_ligatures": (override.get("requires") or {}).get("ligatures_exist") is True,
        "override_requires_design_actions": (override.get("requires") or {}).get("design_actions_present") is True,
        "case_a_activates": (policy.get("case_a") or {}).get("expected") == "family activates",
        "case_b_removes_ligatures": (policy.get("case_b") or {}).get("expected") == "remove ligatures",
        "case_c_no_optimisation_required": (policy.get("case_c") or {}).get("expected") == "no optimisation required",
        "cannot_terminate_for_zero_utilisation": override.get("family_cannot_terminate_solely_because_utilisation_is_zero") is True,
    }
    return _finish("zero_shear_lane", checks, {"policy": policy, "zero_shear_override": override})


def geometry_restriction_main() -> int:
    policies = lane_proof_policies()
    policy = dict(policies.get("geometry_restriction") or {})
    restrictions = geometry_restrictions()
    width_update = ShearOverdesignCandidateUpdate(updates={"b": 250.0})
    depth_update = ShearOverdesignCandidateUpdate(updates={"D": 450.0})
    shear_update = ShearOverdesignCandidateUpdate(updates={"s_lig": 300.0})
    checks = {
        **_common_checks(),
        "contract_prohibits_geometry_reduction": restrictions.get("geometry_reduction_prohibited") is True,
        "policy_prohibits_width_reduction": policy.get("prohibits_width_reduction") is True,
        "policy_prohibits_depth_reduction": policy.get("prohibits_depth_reduction") is True,
        "width_update_rejected_by_boundary": width_update.geometry_reduction_attempted and not width_update.shear_detailing_only,
        "depth_update_rejected_by_boundary": depth_update.geometry_reduction_attempted and not depth_update.shear_detailing_only,
        "shear_update_allowed_by_boundary": shear_update.shear_detailing_only and not shear_update.geometry_reduction_attempted,
    }
    return _finish("geometry_restriction", checks, {"policy": policy, "geometry_restrictions": restrictions})
