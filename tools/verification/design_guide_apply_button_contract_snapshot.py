"""Snapshot Design Guide apply-button contract binding for product scenarios."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"

SCENARIOS = {
    "SHEAR": {
        "name": "scenario_c1_pure_shear_underdesign_repair",
        "expected_family": "SHEAR_FAIL_GOVERNS",
        "expected_apply_family": "shear",
        "env": {"DESIGN_BRAIN_SHEAR_FAIL_FAMILY_ROUTING": "1"},
    },
    "COMBINED": {
        "name": "scenario_c2_combined_bending_shear_underdesign_repair",
        "expected_family": "COMBINED_BENDING_SHEAR_FAIL",
        "expected_apply_family": "combined",
        "env": {"DESIGN_BRAIN_COMBINED_FAIL_FAMILY_ROUTING": "1"},
    },
    "BENDING": {
        "name": "scenario_c3_pure_bending_underdesign_repair",
        "expected_family": "BENDING_FAIL_GOVERNS",
        "expected_apply_family": "bending",
        "env": {"DESIGN_BRAIN_BENDING_FAIL_FAMILY_ROUTING": "1"},
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _report_path_from_stdout(stdout: str) -> Path | None:
    for line in str(stdout or "").splitlines():
        match = re.match(r"^Report:\s*(.+\.json)\s*$", line.strip())
        if match:
            return Path(match.group(1))
    return None


def _scenario_result(gate_report: dict[str, Any], scenario_name: str) -> dict[str, Any]:
    for result in gate_report.get("results") or []:
        if isinstance(result, dict) and result.get("name") == scenario_name:
            return dict(result)
    return {}


def _read_rows(path: Path) -> list[dict[str, Any]]:
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


def _row_family_values(row: dict[str, Any]) -> set[str]:
    values = {
        row.get("selected_family"),
        row.get("published_family"),
        row.get("apply_family"),
    }
    for item in list(row.get("items_after") or []):
        if isinstance(item, dict):
            values.update(
                {
                    item.get("selected_family"),
                    item.get("published_family"),
                    item.get("apply_family"),
                }
            )
    return {str(value or "").strip().lower() for value in values if str(value or "").strip()}


def _selected_row(rows: list[dict[str, Any]], expected_apply_family: str) -> dict[str, Any]:
    expected = str(expected_apply_family or "").strip().lower()
    for row in reversed(rows):
        if expected and expected in _row_family_values(row):
            return row
    for row in reversed(rows):
        if int(row.get("output_item_count") or 0) > 0:
            return row
    return rows[-1] if rows else {}


def _binding_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": row.get("source"),
        "input_item_count": row.get("input_item_count"),
        "output_item_count": row.get("output_item_count"),
        "input_item_identities": row.get("input_item_identities"),
        "output_item_identities": row.get("output_item_identities"),
        "item_ids_before": row.get("item_ids_before"),
        "item_ids_after": row.get("item_ids_after"),
        "selected_family": row.get("selected_family"),
        "published_family": row.get("published_family"),
        "apply_family": row.get("apply_family"),
        "cta_label": row.get("cta_label"),
        "cta_enabled": row.get("cta_enabled"),
        "cta_reason": row.get("cta_reason"),
        "button_contract_enabled": row.get("button_contract_enabled"),
        "disabled_reason": row.get("disabled_reason"),
        "state_fingerprint": row.get("state_fingerprint"),
        "apply_payload_identity": row.get("apply_payload_identity"),
        "apply_payload_hash": row.get("apply_payload_hash"),
        "candidate_payload_identity": row.get("candidate_payload_identity"),
        "candidate_payload_hash": row.get("candidate_payload_hash"),
        "input_items_mutated_in_place": row.get("input_items_mutated_in_place"),
        "output_reuses_input_object": row.get("output_reuses_input_object"),
        "same_object_indices": row.get("same_object_indices"),
        "contract_debug_data_added_to_items": row.get("contract_debug_data_added_to_items"),
        "button_contract_inputs": row.get("button_contract_inputs"),
        "button_contract_results": row.get("button_contract_results"),
        "button_contract_scalars": row.get("button_contract_scalars"),
        "button_contract_actionability_probe_inputs": row.get("button_contract_actionability_probe_inputs"),
        "button_contract_actionability_probe_outputs": row.get("button_contract_actionability_probe_outputs"),
        "button_contract_actionability_resolutions": row.get("button_contract_actionability_resolutions"),
        "button_contract_actionability_helper_outputs": row.get("button_contract_actionability_helper_outputs"),
        "button_contract_actionability_inputs": row.get("button_contract_actionability_inputs"),
        "button_contract_actionability_predicates": row.get("button_contract_actionability_predicates"),
        "button_contract_actionability_applications": row.get("button_contract_actionability_applications"),
        "button_contract_actionability_decisions": row.get("button_contract_actionability_decisions"),
        "button_contract_update_resolution_inputs": row.get("button_contract_update_resolution_inputs"),
        "button_contract_update_resolution_decisions": row.get("button_contract_update_resolution_decisions"),
        "button_contract_update_resolutions": row.get("button_contract_update_resolutions"),
        "button_contract_work_mutations": row.get("button_contract_work_mutations"),
        "promotion_decisions": row.get("promotion_decisions"),
        "safe_executor_evidence_rows": row.get("safe_executor_evidence_rows"),
        "typed_binding_result": row.get("typed_binding_result"),
        "items_before": row.get("items_before"),
        "items_after": row.get("items_after"),
    }


def _run_scenario(label: str, *, base_port: int, index: int, timestamp: str) -> dict[str, Any]:
    spec = SCENARIOS[label]
    scenario_name = str(spec["name"])
    expected_family = str(spec["expected_family"])
    expected_apply_family = str(spec["expected_apply_family"])
    runtime_path = ARTIFACT_DIR / f"design_guide_apply_button_contract_runtime_{timestamp}_{label.lower()}.jsonl"
    if runtime_path.exists():
        runtime_path.unlink()
    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env.update(dict(spec.get("env") or {}))
    env["DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH"] = str(runtime_path)
    command = [
        sys.executable,
        "tools/verification/design_guide_product_path_gate.py",
        "--port",
        str(base_port + index),
        "--scenario",
        scenario_name,
    ]
    completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
    gate_path = _report_path_from_stdout(completed.stdout)
    gate_report = _load_json(gate_path) if gate_path is not None else {}
    scenario = _scenario_result(gate_report, scenario_name)
    evidence = dict(scenario.get("evidence") or {})
    rows = _read_rows(runtime_path)
    selected = _selected_row(rows, expected_apply_family)
    snapshot = _binding_snapshot(selected)
    failures: list[str] = []
    if completed.returncode != 0:
        failures.append(f"gate_returncode:{completed.returncode}")
    if scenario.get("status") != "PASS":
        failures.append("scenario_not_pass")
    if not rows:
        failures.append("apply_button_contract_snapshot_missing")
    if not selected:
        failures.append("apply_button_contract_selected_row_missing")
    if selected and bool(selected.get("input_items_mutated_in_place")):
        failures.append("input_items_mutated_in_place")
    typed_result = selected.get("typed_binding_result") if isinstance(selected, dict) else {}
    if not isinstance(typed_result, dict) or not typed_result:
        failures.append("typed_binding_result_missing")
    if isinstance(typed_result, dict) and int(typed_result.get("output_item_count") or 0) != int(
        selected.get("output_item_count") or 0
    ):
        failures.append("typed_binding_result_output_count_mismatch")
    promotion_decisions = selected.get("promotion_decisions") if isinstance(selected, dict) else []
    if not isinstance(promotion_decisions, list):
        failures.append("promotion_decisions_not_list")
    elif selected and len(promotion_decisions) != int(selected.get("output_item_count") or 0):
        failures.append("promotion_decisions_output_count_mismatch")
    typed_promotion_decisions = typed_result.get("promotion_decisions") if isinstance(typed_result, dict) else []
    if isinstance(typed_promotion_decisions, list) and isinstance(promotion_decisions, list):
        if len(typed_promotion_decisions) != len(promotion_decisions):
            failures.append("typed_promotion_decisions_count_mismatch")
    safe_executor_rows = selected.get("safe_executor_evidence_rows") if isinstance(selected, dict) else []
    typed_safe_executor_rows = typed_result.get("safe_executor_evidence_rows") if isinstance(typed_result, dict) else []
    if safe_executor_rows is not None and not isinstance(safe_executor_rows, list):
        failures.append("safe_executor_evidence_rows_not_list")
    if isinstance(safe_executor_rows, list) and isinstance(typed_safe_executor_rows, list):
        if len(safe_executor_rows) != len(typed_safe_executor_rows):
            failures.append("typed_safe_executor_evidence_rows_count_mismatch")
    button_contract_inputs = selected.get("button_contract_inputs") if isinstance(selected, dict) else []
    button_contract_results = selected.get("button_contract_results") if isinstance(selected, dict) else []
    button_contract_scalars = selected.get("button_contract_scalars") if isinstance(selected, dict) else []
    button_contract_actionability_probe_inputs = (
        selected.get("button_contract_actionability_probe_inputs") if isinstance(selected, dict) else []
    )
    button_contract_actionability_probe_outputs = (
        selected.get("button_contract_actionability_probe_outputs") if isinstance(selected, dict) else []
    )
    button_contract_actionability_resolutions = (
        selected.get("button_contract_actionability_resolutions") if isinstance(selected, dict) else []
    )
    button_contract_actionability_helper_outputs = (
        selected.get("button_contract_actionability_helper_outputs") if isinstance(selected, dict) else []
    )
    button_contract_actionability_inputs = (
        selected.get("button_contract_actionability_inputs") if isinstance(selected, dict) else []
    )
    button_contract_actionability_predicates = (
        selected.get("button_contract_actionability_predicates") if isinstance(selected, dict) else []
    )
    button_contract_actionability_applications = (
        selected.get("button_contract_actionability_applications") if isinstance(selected, dict) else []
    )
    button_contract_actionability_decisions = (
        selected.get("button_contract_actionability_decisions") if isinstance(selected, dict) else []
    )
    button_contract_update_resolutions = (
        selected.get("button_contract_update_resolutions") if isinstance(selected, dict) else []
    )
    button_contract_update_resolution_inputs = (
        selected.get("button_contract_update_resolution_inputs") if isinstance(selected, dict) else []
    )
    button_contract_update_resolution_decisions = (
        selected.get("button_contract_update_resolution_decisions") if isinstance(selected, dict) else []
    )
    typed_button_contract_inputs = typed_result.get("button_contract_inputs") if isinstance(typed_result, dict) else []
    typed_button_contract_results = typed_result.get("button_contract_results") if isinstance(typed_result, dict) else []
    typed_button_contract_scalars = typed_result.get("button_contract_scalars") if isinstance(typed_result, dict) else []
    typed_button_contract_actionability_probe_inputs = (
        typed_result.get("button_contract_actionability_probe_inputs") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_actionability_probe_outputs = (
        typed_result.get("button_contract_actionability_probe_outputs") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_actionability_resolutions = (
        typed_result.get("button_contract_actionability_resolutions") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_actionability_helper_outputs = (
        typed_result.get("button_contract_actionability_helper_outputs") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_actionability_inputs = (
        typed_result.get("button_contract_actionability_inputs") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_actionability_predicates = (
        typed_result.get("button_contract_actionability_predicates") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_actionability_applications = (
        typed_result.get("button_contract_actionability_applications") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_actionability_decisions = (
        typed_result.get("button_contract_actionability_decisions") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_update_resolutions = (
        typed_result.get("button_contract_update_resolutions") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_update_resolution_inputs = (
        typed_result.get("button_contract_update_resolution_inputs") if isinstance(typed_result, dict) else []
    )
    typed_button_contract_update_resolution_decisions = (
        typed_result.get("button_contract_update_resolution_decisions") if isinstance(typed_result, dict) else []
    )
    button_contract_work_mutations = selected.get("button_contract_work_mutations") if isinstance(selected, dict) else []
    typed_button_contract_work_mutations = (
        typed_result.get("button_contract_work_mutations") if isinstance(typed_result, dict) else []
    )
    if not isinstance(button_contract_inputs, list):
        failures.append("button_contract_inputs_not_list")
    elif selected and len(button_contract_inputs) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_inputs_output_count_mismatch")
    if not isinstance(button_contract_results, list):
        failures.append("button_contract_results_not_list")
    elif selected and len(button_contract_results) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_results_output_count_mismatch")
    if isinstance(button_contract_inputs, list) and isinstance(typed_button_contract_inputs, list):
        if len(button_contract_inputs) != len(typed_button_contract_inputs):
            failures.append("typed_button_contract_inputs_count_mismatch")
    if isinstance(button_contract_results, list) and isinstance(typed_button_contract_results, list):
        if len(button_contract_results) != len(typed_button_contract_results):
            failures.append("typed_button_contract_results_count_mismatch")
    if not isinstance(button_contract_scalars, list):
        failures.append("button_contract_scalars_not_list")
    elif selected and len(button_contract_scalars) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_scalars_output_count_mismatch")
    if isinstance(button_contract_scalars, list):
        for index, record in enumerate(button_contract_scalars):
            if not isinstance(record, dict):
                failures.append(f"button_contract_scalar_not_dict:{index}")
                continue
            if record.get("final_enabled") is None:
                failures.append(f"button_contract_scalar_enabled_missing:{index}")
            if not record.get("final_contract_hash"):
                failures.append(f"button_contract_scalar_contract_hash_missing:{index}")
            if record.get("final_contract_updates_hash") is None:
                failures.append(f"button_contract_scalar_updates_hash_missing:{index}")
            if isinstance(button_contract_results, list) and index < len(button_contract_results):
                result_record = button_contract_results[index]
                if isinstance(result_record, dict) and record.get("final_contract_hash") != result_record.get("contract_hash"):
                    failures.append(f"button_contract_scalar_hash_mismatch:{index}")
    if isinstance(button_contract_scalars, list) and isinstance(typed_button_contract_scalars, list):
        if len(button_contract_scalars) != len(typed_button_contract_scalars):
            failures.append("typed_button_contract_scalars_count_mismatch")
    if not isinstance(button_contract_actionability_probe_inputs, list):
        failures.append("button_contract_actionability_probe_inputs_not_list")
    elif selected and len(button_contract_actionability_probe_inputs) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_probe_inputs_output_count_mismatch")
    if isinstance(button_contract_actionability_probe_inputs, list):
        for index, record in enumerate(button_contract_actionability_probe_inputs):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_probe_input_not_dict:{index}")
                continue
            if not record.get("probe_input_hash"):
                failures.append(f"button_contract_actionability_probe_input_hash_missing:{index}")
            if record.get("target_band_eps") is None:
                failures.append(f"button_contract_actionability_probe_input_target_band_eps_missing:{index}")
            if record.get("final_accepted_min_family_util") is None:
                failures.append(f"button_contract_actionability_probe_input_final_min_missing:{index}")
            if not isinstance(record.get("compound_shear_update_keys"), list):
                failures.append(f"button_contract_actionability_probe_input_shear_keys_not_list:{index}")
            if not isinstance(record.get("compound_bottom_update_keys"), list):
                failures.append(f"button_contract_actionability_probe_input_bottom_keys_not_list:{index}")
            if isinstance(button_contract_actionability_resolutions, list) and index < len(button_contract_actionability_resolutions):
                resolution = button_contract_actionability_resolutions[index]
                if isinstance(resolution, dict):
                    if record.get("blocking_reason_before_probe") != resolution.get("blocking_reason_before"):
                        failures.append(f"button_contract_actionability_probe_input_resolution_reason_mismatch:{index}")
                    if record.get("executor_allowed_before_probe") != resolution.get("executor_allowed_before"):
                        failures.append(f"button_contract_actionability_probe_input_resolution_executor_mismatch:{index}")
                    if record.get("preview_pass_before_probe") != resolution.get("preview_pass_before"):
                        failures.append(f"button_contract_actionability_probe_input_resolution_preview_mismatch:{index}")
                    if record.get("family_before_probe") != resolution.get("family_before"):
                        failures.append(f"button_contract_actionability_probe_input_resolution_family_mismatch:{index}")
    if (
        isinstance(button_contract_actionability_probe_inputs, list)
        and isinstance(typed_button_contract_actionability_probe_inputs, list)
    ):
        if len(button_contract_actionability_probe_inputs) != len(typed_button_contract_actionability_probe_inputs):
            failures.append("typed_button_contract_actionability_probe_inputs_count_mismatch")
    if not isinstance(button_contract_actionability_probe_outputs, list):
        failures.append("button_contract_actionability_probe_outputs_not_list")
    elif selected and len(button_contract_actionability_probe_outputs) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_probe_outputs_output_count_mismatch")
    if isinstance(button_contract_actionability_probe_outputs, list):
        for index, record in enumerate(button_contract_actionability_probe_outputs):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_probe_output_not_dict:{index}")
                continue
            if not record.get("probe_output_hash"):
                failures.append(f"button_contract_actionability_probe_output_hash_missing:{index}")
            if not record.get("executor_probe_hash"):
                failures.append(f"button_contract_actionability_probe_executor_hash_missing:{index}")
            if not record.get("preview_probe_hash"):
                failures.append(f"button_contract_actionability_probe_preview_hash_missing:{index}")
            if not record.get("final_probe_hash"):
                failures.append(f"button_contract_actionability_probe_final_hash_missing:{index}")
            if isinstance(button_contract_actionability_helper_outputs, list) and index < len(button_contract_actionability_helper_outputs):
                helper = button_contract_actionability_helper_outputs[index]
                if isinstance(helper, dict):
                    if record.get("final_blocking_reason") != helper.get("final_blocking_reason"):
                        failures.append(f"button_contract_actionability_probe_helper_reason_mismatch:{index}")
                    if record.get("final_executor_allowed") != helper.get("final_executor_allowed"):
                        failures.append(f"button_contract_actionability_probe_helper_executor_mismatch:{index}")
                    if record.get("final_preview_pass") != helper.get("final_preview_pass"):
                        failures.append(f"button_contract_actionability_probe_helper_preview_mismatch:{index}")
    if (
        isinstance(button_contract_actionability_probe_outputs, list)
        and isinstance(typed_button_contract_actionability_probe_outputs, list)
    ):
        if len(button_contract_actionability_probe_outputs) != len(typed_button_contract_actionability_probe_outputs):
            failures.append("typed_button_contract_actionability_probe_outputs_count_mismatch")
    if not isinstance(button_contract_actionability_resolutions, list):
        failures.append("button_contract_actionability_resolutions_not_list")
    elif selected and len(button_contract_actionability_resolutions) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_resolutions_output_count_mismatch")
    if isinstance(button_contract_actionability_resolutions, list):
        for index, record in enumerate(button_contract_actionability_resolutions):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_resolution_not_dict:{index}")
                continue
            if not record.get("resolution_hash"):
                failures.append(f"button_contract_actionability_resolution_hash_missing:{index}")
            if not record.get("final_contract_hash"):
                failures.append(f"button_contract_actionability_resolution_contract_hash_missing:{index}")
            if "actionable_after" not in record:
                failures.append(f"button_contract_actionability_resolution_actionable_missing:{index}")
            if "enabled_after" not in record:
                failures.append(f"button_contract_actionability_resolution_enabled_missing:{index}")
            if isinstance(button_contract_results, list) and index < len(button_contract_results):
                result_record = button_contract_results[index]
                if isinstance(result_record, dict) and record.get("final_contract_hash") != result_record.get("contract_hash"):
                    failures.append(f"button_contract_actionability_resolution_contract_hash_mismatch:{index}")
            if isinstance(button_contract_actionability_decisions, list) and index < len(button_contract_actionability_decisions):
                decision = button_contract_actionability_decisions[index]
                if isinstance(decision, dict):
                    if record.get("actionable_after") != decision.get("final_actionable"):
                        failures.append(f"button_contract_actionability_resolution_decision_actionable_mismatch:{index}")
                    if record.get("enabled_after") != decision.get("final_enabled"):
                        failures.append(f"button_contract_actionability_resolution_decision_enabled_mismatch:{index}")
                    if record.get("reason_after") != decision.get("final_reason"):
                        failures.append(f"button_contract_actionability_resolution_decision_reason_mismatch:{index}")
    if (
        isinstance(button_contract_actionability_resolutions, list)
        and isinstance(typed_button_contract_actionability_resolutions, list)
    ):
        if len(button_contract_actionability_resolutions) != len(typed_button_contract_actionability_resolutions):
            failures.append("typed_button_contract_actionability_resolutions_count_mismatch")
    if not isinstance(button_contract_actionability_helper_outputs, list):
        failures.append("button_contract_actionability_helper_outputs_not_list")
    elif selected and len(button_contract_actionability_helper_outputs) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_helper_outputs_output_count_mismatch")
    if isinstance(button_contract_actionability_helper_outputs, list):
        for index, record in enumerate(button_contract_actionability_helper_outputs):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_helper_output_not_dict:{index}")
                continue
            if not record.get("helper_output_hash"):
                failures.append(f"button_contract_actionability_helper_output_hash_missing:{index}")
            if record.get("executor_contract_evaluated") is None:
                failures.append(f"button_contract_actionability_helper_executor_eval_missing:{index}")
            if record.get("preview_evaluated") is None:
                failures.append(f"button_contract_actionability_helper_preview_eval_missing:{index}")
    if (
        isinstance(button_contract_actionability_helper_outputs, list)
        and isinstance(typed_button_contract_actionability_helper_outputs, list)
    ):
        if len(button_contract_actionability_helper_outputs) != len(typed_button_contract_actionability_helper_outputs):
            failures.append("typed_button_contract_actionability_helper_outputs_count_mismatch")
    if not isinstance(button_contract_actionability_inputs, list):
        failures.append("button_contract_actionability_inputs_not_list")
    elif selected and len(button_contract_actionability_inputs) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_inputs_output_count_mismatch")
    if not isinstance(button_contract_actionability_decisions, list):
        failures.append("button_contract_actionability_decisions_not_list")
    elif selected and len(button_contract_actionability_decisions) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_decisions_output_count_mismatch")
    if isinstance(button_contract_actionability_inputs, list):
        for index, record in enumerate(button_contract_actionability_inputs):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_input_not_dict:{index}")
                continue
            if not record.get("resolved_work_hash"):
                failures.append(f"button_contract_actionability_input_work_hash_missing:{index}")
            if record.get("executor_allowed") is None:
                failures.append(f"button_contract_actionability_input_executor_allowed_missing:{index}")
    if not isinstance(button_contract_actionability_predicates, list):
        failures.append("button_contract_actionability_predicates_not_list")
    elif selected and len(button_contract_actionability_predicates) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_predicates_output_count_mismatch")
    if isinstance(button_contract_actionability_predicates, list):
        for index, record in enumerate(button_contract_actionability_predicates):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_predicate_not_dict:{index}")
                continue
            if not record.get("predicate_hash"):
                failures.append(f"button_contract_actionability_predicate_hash_missing:{index}")
            if record.get("final_actionable_predicate") is None:
                failures.append(f"button_contract_actionability_predicate_final_missing:{index}")
            if isinstance(button_contract_actionability_decisions, list) and index < len(button_contract_actionability_decisions):
                decision = button_contract_actionability_decisions[index]
                if isinstance(decision, dict) and bool(record.get("final_actionable_predicate")) != bool(decision.get("final_actionable")):
                    failures.append(f"button_contract_actionability_predicate_decision_mismatch:{index}")
    if not isinstance(button_contract_actionability_applications, list):
        failures.append("button_contract_actionability_applications_not_list")
    elif selected and len(button_contract_actionability_applications) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_actionability_applications_output_count_mismatch")
    if isinstance(button_contract_actionability_applications, list):
        for index, record in enumerate(button_contract_actionability_applications):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_application_not_dict:{index}")
                continue
            if not record.get("application_hash"):
                failures.append(f"button_contract_actionability_application_hash_missing:{index}")
            if not record.get("final_contract_hash"):
                failures.append(f"button_contract_actionability_application_contract_hash_missing:{index}")
            if record.get("final_actionable") is None:
                failures.append(f"button_contract_actionability_application_actionable_missing:{index}")
            if isinstance(button_contract_results, list) and index < len(button_contract_results):
                result_record = button_contract_results[index]
                if isinstance(result_record, dict) and record.get("final_contract_hash") != result_record.get("contract_hash"):
                    failures.append(f"button_contract_actionability_application_contract_hash_mismatch:{index}")
            if isinstance(button_contract_actionability_decisions, list) and index < len(button_contract_actionability_decisions):
                decision = button_contract_actionability_decisions[index]
                if isinstance(decision, dict):
                    if bool(record.get("final_actionable")) != bool(decision.get("final_actionable")):
                        failures.append(f"button_contract_actionability_application_decision_actionable_mismatch:{index}")
                    if record.get("final_blocking_reason") != decision.get("final_reason"):
                        failures.append(f"button_contract_actionability_application_decision_reason_mismatch:{index}")
            if isinstance(button_contract_actionability_predicates, list) and index < len(button_contract_actionability_predicates):
                predicate = button_contract_actionability_predicates[index]
                if isinstance(predicate, dict) and record.get("predicate_hash") != predicate.get("predicate_hash"):
                    failures.append(f"button_contract_actionability_application_predicate_hash_mismatch:{index}")
    if isinstance(button_contract_actionability_decisions, list):
        for index, record in enumerate(button_contract_actionability_decisions):
            if not isinstance(record, dict):
                failures.append(f"button_contract_actionability_decision_not_dict:{index}")
                continue
            if record.get("final_actionable") is None:
                failures.append(f"button_contract_actionability_decision_actionable_missing:{index}")
            if record.get("final_enabled") is None:
                failures.append(f"button_contract_actionability_decision_enabled_missing:{index}")
            if not record.get("final_contract_hash"):
                failures.append(f"button_contract_actionability_decision_contract_hash_missing:{index}")
            if isinstance(button_contract_results, list) and index < len(button_contract_results):
                result_record = button_contract_results[index]
                if isinstance(result_record, dict) and record.get("final_contract_hash") != result_record.get("contract_hash"):
                    failures.append(f"button_contract_actionability_decision_hash_mismatch:{index}")
    if isinstance(button_contract_actionability_inputs, list) and isinstance(typed_button_contract_actionability_inputs, list):
        if len(button_contract_actionability_inputs) != len(typed_button_contract_actionability_inputs):
            failures.append("typed_button_contract_actionability_inputs_count_mismatch")
    if isinstance(button_contract_actionability_predicates, list) and isinstance(typed_button_contract_actionability_predicates, list):
        if len(button_contract_actionability_predicates) != len(typed_button_contract_actionability_predicates):
            failures.append("typed_button_contract_actionability_predicates_count_mismatch")
    if isinstance(button_contract_actionability_applications, list) and isinstance(typed_button_contract_actionability_applications, list):
        if len(button_contract_actionability_applications) != len(typed_button_contract_actionability_applications):
            failures.append("typed_button_contract_actionability_applications_count_mismatch")
    if isinstance(button_contract_actionability_decisions, list) and isinstance(typed_button_contract_actionability_decisions, list):
        if len(button_contract_actionability_decisions) != len(typed_button_contract_actionability_decisions):
            failures.append("typed_button_contract_actionability_decisions_count_mismatch")
    if not isinstance(button_contract_update_resolutions, list):
        failures.append("button_contract_update_resolutions_not_list")
    elif selected and len(button_contract_update_resolutions) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_update_resolutions_output_count_mismatch")
    if isinstance(button_contract_update_resolutions, list):
        for index, record in enumerate(button_contract_update_resolutions):
            if not isinstance(record, dict):
                failures.append(f"button_contract_update_resolution_not_dict:{index}")
                continue
            if not bool(record.get("production_button_contract_exercised")):
                failures.append(f"button_contract_update_resolution_not_production:{index}")
            if record.get("button_contract_update_resolution_applicable") is None:
                failures.append(f"button_contract_update_resolution_applicability_missing:{index}")
            if not record.get("final_contract_hash"):
                failures.append(f"button_contract_update_resolution_contract_hash_missing:{index}")
            if not record.get("resolved_updates_hash"):
                failures.append(f"button_contract_update_resolution_updates_hash_missing:{index}")
    if (
        isinstance(button_contract_update_resolutions, list)
        and isinstance(typed_button_contract_update_resolutions, list)
        and len(button_contract_update_resolutions) != len(typed_button_contract_update_resolutions)
    ):
        failures.append("typed_button_contract_update_resolutions_count_mismatch")
    if not isinstance(button_contract_update_resolution_inputs, list):
        failures.append("button_contract_update_resolution_inputs_not_list")
    elif selected and len(button_contract_update_resolution_inputs) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_update_resolution_inputs_output_count_mismatch")
    if not isinstance(button_contract_update_resolution_decisions, list):
        failures.append("button_contract_update_resolution_decisions_not_list")
    elif selected and len(button_contract_update_resolution_decisions) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_update_resolution_decisions_output_count_mismatch")
    if isinstance(button_contract_update_resolution_inputs, list):
        for index, record in enumerate(button_contract_update_resolution_inputs):
            if not isinstance(record, dict):
                failures.append(f"button_contract_update_resolution_input_not_dict:{index}")
                continue
            if record.get("update_resolution_applicable") is None:
                failures.append(f"button_contract_update_resolution_input_applicability_missing:{index}")
            if not record.get("work_hash_before"):
                failures.append(f"button_contract_update_resolution_input_work_hash_missing:{index}")
    if isinstance(button_contract_update_resolution_decisions, list):
        for index, record in enumerate(button_contract_update_resolution_decisions):
            if not isinstance(record, dict):
                failures.append(f"button_contract_update_resolution_decision_not_dict:{index}")
                continue
            if record.get("update_resolution_applicable") is None:
                failures.append(f"button_contract_update_resolution_decision_applicability_missing:{index}")
            if not record.get("final_contract_hash"):
                failures.append(f"button_contract_update_resolution_decision_contract_hash_missing:{index}")
            if not record.get("resolved_updates_hash"):
                failures.append(f"button_contract_update_resolution_decision_updates_hash_missing:{index}")
    if (
        isinstance(button_contract_update_resolution_inputs, list)
        and isinstance(typed_button_contract_update_resolution_inputs, list)
        and len(button_contract_update_resolution_inputs) != len(typed_button_contract_update_resolution_inputs)
    ):
        failures.append("typed_button_contract_update_resolution_inputs_count_mismatch")
    if (
        isinstance(button_contract_update_resolution_decisions, list)
        and isinstance(typed_button_contract_update_resolution_decisions, list)
        and len(button_contract_update_resolution_decisions) != len(typed_button_contract_update_resolution_decisions)
    ):
        failures.append("typed_button_contract_update_resolution_decisions_count_mismatch")
    if not isinstance(button_contract_work_mutations, list):
        failures.append("button_contract_work_mutations_not_list")
    elif selected and len(button_contract_work_mutations) != int(selected.get("output_item_count") or 0):
        failures.append("button_contract_work_mutations_output_count_mismatch")
    if isinstance(button_contract_work_mutations, list):
        for index, record in enumerate(button_contract_work_mutations):
            if not isinstance(record, dict):
                failures.append(f"button_contract_work_mutation_not_dict:{index}")
                continue
            if not record.get("input_work_hash"):
                failures.append(f"button_contract_work_mutation_input_hash_missing:{index}")
            if not record.get("output_work_hash"):
                failures.append(f"button_contract_work_mutation_output_hash_missing:{index}")
            if record.get("selected_update_source") is None:
                failures.append(f"button_contract_work_mutation_source_missing:{index}")
            if record.get("selected_updates_hash") is None:
                failures.append(f"button_contract_work_mutation_updates_hash_missing:{index}")
    if (
        isinstance(button_contract_work_mutations, list)
        and isinstance(typed_button_contract_work_mutations, list)
        and len(button_contract_work_mutations) != len(typed_button_contract_work_mutations)
    ):
        failures.append("typed_button_contract_work_mutations_count_mismatch")
    return {
        "label": label,
        "scenario": scenario_name,
        "expected_family": expected_family,
        "expected_apply_family": expected_apply_family,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
        "gate_report": str(gate_path) if gate_path else None,
        "runtime_snapshot_path": str(runtime_path),
        "runtime_row_count": len(rows),
        "selected_runtime_source": selected.get("source"),
        "selected_binding": snapshot,
        "gate_evidence": {
            "selected_family_id": evidence.get("selected_family_id"),
            "published_family_id": evidence.get("published_family_id"),
            "cta_family_id": evidence.get("cta_family_id"),
            "apply_payload_family_id": evidence.get("apply_payload_family_id"),
            "render_cta_payload_id": evidence.get("render_cta_payload_id"),
            "visible_cta_buttons": evidence.get("visible_cta_buttons"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=11401)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIOS),
        help="Scenario label to run. May be repeated. Defaults to SHEAR, BENDING, COMBINED.",
    )
    args = parser.parse_args(argv)

    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    labels = args.scenario or ["SHEAR", "BENDING", "COMBINED"]
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        _run_scenario(label, base_port=args.port, index=index, timestamp=timestamp)
        for index, label in enumerate(labels)
    ]
    status = "PASS" if results and all(result.get("status") == "PASS" for result in results) else "FAIL"
    report = {
        "schema": "design_guide_apply_button_contract_snapshot.v1",
        "status": status,
        "results": results,
    }
    output = ARTIFACT_DIR / f"design_guide_apply_button_contract_snapshot_{timestamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
