"""Synthetic branch snapshot for Design Guide apply-button promotion decisions."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _patch_attr(module: object, name: str, value: object, restore: list[tuple[str, object]]) -> None:
    restore.append((name, getattr(module, name)))
    setattr(module, name, value)


def _synthetic_update_resolution_boundary(scenario: str) -> dict[str, Any]:
    return {
        "source": "synthetic_button_contract_double",
        "scenario": scenario,
        "production_button_contract_exercised": False,
        "button_contract_update_resolution_applicable": False,
        "reason": "synthetic monkeypatch bypasses production _design_guide_button_contract",
        "future_kwargs_tolerated": True,
    }


def _scenario_item(scenario: str) -> dict[str, Any]:
    base = {
        "id": f"{scenario}_input",
        "candidate_id": f"{scenario}_candidate_before",
        "source_candidate_id": f"{scenario}_source_before",
        "title_main": "Shear capacity is low",
        "title": "Shear capacity is low",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "guidance_intent": "required_fix",
        "action_type": "apply_resolved_candidate",
        "updates": {},
    }
    if scenario == "target_band_promotion":
        base["candidate_search_evidence"] = {
            "target_band_candidate_count": 1,
            "best_target_band_candidate_id": "target_band_candidate_after",
            "best_target_band_candidate_updates": {"s_lig": 150.0},
            "best_target_band_candidate_util": 0.82,
            "active_failures": ["shear"],
        }
    elif scenario == "safe_strength_promotion":
        base["candidate_search_evidence"] = {
            "target_band_candidate_count": 0,
            "safe_executor_backed_candidates_count": 1,
            "selected_candidate_id": "safe_strength_candidate_after",
            "selected_candidate_updates": {"s_lig": 125.0},
            "selected_candidate_util": 1.04,
            "active_failures": ["shear"],
        }
    elif scenario == "advisory_conversion":
        base["candidate_search_evidence"] = {
            "target_band_candidate_count": 0,
            "safe_executor_backed_candidates_count": 0,
            "active_failures": ["shear"],
        }
    elif scenario == "no_promotion_control":
        base["guidance_intent"] = "suggestion"
        base["candidate_search_evidence"] = {}
    return base


def _button_contract_for(
    item: dict | None,
    *,
    state: dict,
    blocking_reason_override: str | None = None,
    **_ignored_kwargs: Any,
) -> dict[str, Any]:
    scenario = str((item or {}).get("id") or "").replace("_input", "")
    if scenario == "no_promotion_control":
        return {
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": {"s_lig": 175.0},
            "expected_util": 0.9,
            "actionable": True,
            "preview_pass": True,
            "blocking_reason": None,
            "candidate_id": "control_candidate",
            "source_candidate_id": "control_candidate",
        }
    return {
        "action_type": "apply_resolved_candidate",
        "family": "shear",
        "updates": {},
        "expected_util": None,
        "actionable": False,
        "preview_pass": False,
        "blocking_reason": blocking_reason_override
        or "candidate_preview_not_in_target_band_after_active_failure",
        "candidate_id": f"{scenario}_contract_before",
        "source_candidate_id": f"{scenario}_contract_before",
    }


def _advisory_item(item: dict | None, *, blocked_reason: str | None = None) -> dict[str, Any]:
    out = dict(item or {})
    out["guidance_intent"] = "advisory"
    out["is_advisory"] = True
    out["button_contract"] = {
        "action_type": out.get("action_type"),
        "family": out.get("family") or out.get("check_key"),
        "updates": {},
        "actionable": False,
        "preview_pass": False,
        "blocking_reason": blocked_reason or "synthetic_advisory_conversion",
    }
    return out


def _run_case(module: object, scenario: str, timestamp: str) -> dict[str, Any]:
    runtime_path = ARTIFACT_DIR / f"design_guide_apply_button_promotion_branch_runtime_{timestamp}_{scenario}.jsonl"
    if runtime_path.exists():
        runtime_path.unlink()
    old_env = os.environ.get("DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH")
    os.environ["DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH"] = str(runtime_path)
    try:
        input_item = _scenario_item(scenario)
        state = {"synthetic_branch_case": scenario}
        primary_blocking_reason = (
            None
            if scenario == "no_promotion_control"
            else "candidate_preview_not_in_target_band_after_active_failure"
        )
        if scenario == "advisory_conversion":
            primary_blocking_reason = "missing_action_type"
        output_items = module._design_guide_apply_button_contracts_to_items(
            [copy.deepcopy(input_item)],
            state=state,
            primary_blocking_reason=primary_blocking_reason,
        )
    finally:
        if old_env is None:
            os.environ.pop("DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH", None)
        else:
            os.environ["DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH"] = old_env

    rows = _load_rows(runtime_path)
    selected = rows[-1] if rows else {}
    decision = {}
    decisions = selected.get("promotion_decisions") if isinstance(selected, dict) else []
    if isinstance(decisions, list) and decisions:
        decision = dict(decisions[0])
    typed = dict(selected.get("typed_binding_result") or {}) if isinstance(selected, dict) else {}
    typed_decisions = typed.get("promotion_decisions") if isinstance(typed, dict) else []
    typed_decision = dict(typed_decisions[0]) if isinstance(typed_decisions, list) and typed_decisions else {}
    safe_executor_evidence_rows = (
        selected.get("safe_executor_evidence_rows") if isinstance(selected, dict) else []
    )
    typed_safe_executor_evidence_rows = typed.get("safe_executor_evidence_rows") if isinstance(typed, dict) else []
    button_contract_inputs = selected.get("button_contract_inputs") if isinstance(selected, dict) else []
    button_contract_results = selected.get("button_contract_results") if isinstance(selected, dict) else []
    typed_button_contract_inputs = typed.get("button_contract_inputs") if isinstance(typed, dict) else []
    typed_button_contract_results = typed.get("button_contract_results") if isinstance(typed, dict) else []
    output_item = dict(output_items[0] if output_items else {})
    contract = dict(output_item.get("button_contract") or {})
    return {
        "scenario": scenario,
        "branch_level_proof_not_product_path": True,
        "production_button_contract_exercised": False,
        "button_contract_update_resolution_applicable": False,
        "button_contract_update_resolution_boundary": _synthetic_update_resolution_boundary(scenario),
        "runtime_snapshot_path": str(runtime_path),
        "runtime_row_count": len(rows),
        "input": {
            "identity": input_item.get("id") or input_item.get("candidate_id"),
            "family": input_item.get("family") or input_item.get("check_key"),
            "status": input_item.get("status"),
            "action_type": input_item.get("action_type"),
            "apply_payload_identity": (input_item.get("action_payload") or {}).get("id"),
            "apply_payload_hash": module._publication_snapshot_hash(
                input_item.get("action_payload") or input_item.get("updates") or {}
            ),
        },
        "decision": decision,
        "branch_inputs": dict(decision.get("branch_inputs") or {}),
        "branch_predicates": dict(decision.get("branch_predicates") or {}),
        "safe_executor_evidence_rows": safe_executor_evidence_rows,
        "typed_safe_executor_evidence_rows": typed_safe_executor_evidence_rows,
        "button_contract_inputs": button_contract_inputs,
        "button_contract_results": button_contract_results,
        "typed_button_contract_inputs": typed_button_contract_inputs,
        "typed_button_contract_results": typed_button_contract_results,
        "typed_decision": typed_decision,
        "output": {
            "identity": output_item.get("id") or output_item.get("candidate_id"),
            "action_state": decision.get("final_action_state") or {},
            "apply_payload_identity": decision.get("final_apply_payload_identity"),
            "apply_payload_hash": decision.get("final_apply_payload_hash"),
            "button_contract": contract,
            "button_contract_summary": decision.get("final_button_contract_summary") or {},
            "cta_label": decision.get("cta_label"),
            "cta_enabled": decision.get("cta_enabled"),
            "cta_reason": decision.get("cta_reason"),
            "copied_field_rewrites": decision.get("copied_field_rewrites") or [],
        },
        "selected_binding": selected,
    }


def _case_passes(result: dict[str, Any]) -> list[str]:
    scenario = str(result.get("scenario") or "")
    decision = dict(result.get("decision") or {})
    failures: list[str] = []
    if not decision:
        return ["decision_missing"]
    update_resolution_boundary = dict(result.get("button_contract_update_resolution_boundary") or {})
    if not update_resolution_boundary:
        failures.append("update_resolution_boundary_missing")
    else:
        if update_resolution_boundary.get("source") != "synthetic_button_contract_double":
            failures.append("update_resolution_boundary_source_mismatch")
        if update_resolution_boundary.get("scenario") != scenario:
            failures.append("update_resolution_boundary_scenario_mismatch")
        if bool(update_resolution_boundary.get("production_button_contract_exercised")):
            failures.append("synthetic_boundary_claims_production_contract")
        if bool(update_resolution_boundary.get("button_contract_update_resolution_applicable")):
            failures.append("synthetic_boundary_claims_update_resolution_applicable")
    if bool(result.get("production_button_contract_exercised")):
        failures.append("synthetic_result_claims_production_contract")
    if bool(result.get("button_contract_update_resolution_applicable")):
        failures.append("synthetic_result_claims_update_resolution_applicable")
    branch_inputs = dict(decision.get("branch_inputs") or {})
    branch_predicates = dict(decision.get("branch_predicates") or {})
    if not branch_inputs:
        failures.append("branch_inputs_missing")
    if not branch_predicates:
        failures.append("branch_predicates_missing")
    if not bool(decision.get("promotion_branch_evaluated")) and scenario != "no_promotion_control":
        failures.append("branch_not_evaluated")
    if branch_inputs and bool(branch_inputs.get("promotion_branch_evaluated")) != bool(decision.get("promotion_branch_evaluated")):
        failures.append("branch_inputs_evaluation_mismatch")
    if branch_predicates and scenario != "no_promotion_control" and not any(
        bool(branch_predicates.get(key))
        for key in (
            "target_band_promotion",
            "safe_strength_promotion",
            "existing_contract_promotion",
            "advisory_conversion",
        )
    ):
        failures.append("branch_predicates_no_branch")
    if scenario == "target_band_promotion":
        if decision.get("decision_reason") != "promoted_from_target_band_evidence":
            failures.append("target_band_reason_mismatch")
        if not bool(decision.get("repair_promotion_occurred")):
            failures.append("target_band_promotion_missing")
        if branch_inputs and int(branch_inputs.get("target_band_candidate_count") or 0) <= 0:
            failures.append("target_band_inputs_missing")
        if branch_predicates and not bool(branch_predicates.get("target_band_promotion")):
            failures.append("target_band_predicate_missing")
    elif scenario == "safe_strength_promotion":
        if decision.get("decision_reason") != "promoted_from_safe_strength_evidence":
            failures.append("safe_strength_reason_mismatch")
        if not bool(decision.get("repair_promotion_occurred")):
            failures.append("safe_strength_promotion_missing")
        if branch_inputs and int(branch_inputs.get("safe_executor_backed_candidates_count") or 0) <= 0:
            failures.append("safe_strength_inputs_missing")
        if branch_predicates and not bool(branch_predicates.get("safe_strength_promotion")):
            failures.append("safe_strength_predicate_missing")
    elif scenario == "advisory_conversion":
        if decision.get("decision_reason") != "converted_to_advisory":
            failures.append("advisory_reason_mismatch")
        if not bool(decision.get("advisory_conversion_occurred")):
            failures.append("advisory_conversion_missing")
        if branch_inputs and not bool(branch_inputs.get("advisory_conversion_eligible")):
            failures.append("advisory_inputs_missing")
        if branch_predicates and not bool(branch_predicates.get("advisory_conversion")):
            failures.append("advisory_predicate_missing")
    elif scenario == "no_promotion_control":
        if decision.get("decision_reason") != "button_contract_bound_without_promotion":
            failures.append("control_reason_mismatch")
        if bool(decision.get("promotion_branch_evaluated")):
            failures.append("control_branch_evaluated")
        if branch_predicates and any(
            bool(branch_predicates.get(key))
            for key in (
                "target_band_promotion",
                "safe_strength_promotion",
                "existing_contract_promotion",
                "advisory_conversion",
            )
        ):
            failures.append("control_predicate_set")
    typed_decision = dict(result.get("typed_decision") or {})
    if typed_decision and typed_decision != decision:
        failures.append("typed_decision_mismatch")
    safe_executor_rows = result.get("safe_executor_evidence_rows")
    typed_safe_executor_rows = result.get("typed_safe_executor_evidence_rows")
    if safe_executor_rows is not None and not isinstance(safe_executor_rows, list):
        failures.append("safe_executor_evidence_rows_not_list")
    if isinstance(safe_executor_rows, list) and isinstance(typed_safe_executor_rows, list):
        if len(safe_executor_rows) != len(typed_safe_executor_rows):
            failures.append("typed_safe_executor_evidence_rows_count_mismatch")
    button_contract_inputs = result.get("button_contract_inputs")
    button_contract_results = result.get("button_contract_results")
    typed_button_contract_inputs = result.get("typed_button_contract_inputs")
    typed_button_contract_results = result.get("typed_button_contract_results")
    if not isinstance(button_contract_inputs, list) or not button_contract_inputs:
        failures.append("button_contract_inputs_missing")
    if not isinstance(button_contract_results, list) or not button_contract_results:
        failures.append("button_contract_results_missing")
    if isinstance(button_contract_inputs, list) and isinstance(typed_button_contract_inputs, list):
        if len(button_contract_inputs) != len(typed_button_contract_inputs):
            failures.append("typed_button_contract_inputs_count_mismatch")
    if isinstance(button_contract_results, list) and isinstance(typed_button_contract_results, list):
        if len(button_contract_results) != len(typed_button_contract_results):
            failures.append("typed_button_contract_results_count_mismatch")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        action="append",
        choices=[
            "target_band_promotion",
            "safe_strength_promotion",
            "advisory_conversion",
            "no_promotion_control",
        ],
        help="Synthetic branch scenario. May be repeated. Defaults to all.",
    )
    args = parser.parse_args(argv)

    import inputs_page

    restore: list[tuple[str, object]] = []
    _patch_attr(inputs_page, "_design_guide_button_contract", _button_contract_for, restore)
    _patch_attr(inputs_page, "_guidance_item_as_advisory", _advisory_item, restore)
    _patch_attr(inputs_page, "_design_mode_config", lambda goal: {"goal": goal}, restore)
    _patch_attr(inputs_page, "_design_optimisation_goal", lambda state: "balanced", restore)
    _patch_attr(inputs_page, "_resolved_efficiency_target_band", lambda mode_cfg, goal=None: (0.75, 0.9, 0.825), restore)
    _patch_attr(inputs_page, "_format_guidance_title", lambda title, util=None: f"{title} ({util})", restore)
    _patch_attr(inputs_page, "_design_guide_primary_apply_state_fingerprint", lambda state=None: "synthetic_branch_fingerprint", restore)
    try:
        timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        scenarios = args.scenario or [
            "target_band_promotion",
            "safe_strength_promotion",
            "advisory_conversion",
            "no_promotion_control",
        ]
        results = []
        for scenario in scenarios:
            result = _run_case(inputs_page, scenario, timestamp)
            failures = _case_passes(result)
            result["status"] = "PASS" if not failures else "FAIL"
            result["failures"] = failures
            results.append(result)
    finally:
        for name, original in reversed(restore):
            setattr(inputs_page, name, original)

    status = "PASS" if results and all(result.get("status") == "PASS" for result in results) else "FAIL"
    report = {
        "schema": "design_guide_apply_button_promotion_branch_snapshot.v1",
        "status": status,
        "branch_level_proof_not_product_path": True,
        "production_button_contract_exercised": False,
        "button_contract_update_resolution_applicable": False,
        "button_contract_update_resolution_boundary": {
            "source": "synthetic_button_contract_double",
            "production_button_contract_exercised": False,
            "button_contract_update_resolution_applicable": False,
            "reason": "promotion branch scenarios monkeypatch _design_guide_button_contract and do not prove production update-resolution behavior",
        },
        "results": results,
    }
    output = ARTIFACT_DIR / f"design_guide_apply_button_promotion_branch_snapshot_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
