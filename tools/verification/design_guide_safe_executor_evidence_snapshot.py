"""Synthetic snapshot for safe-executor evidence row recounting."""

from __future__ import annotations

import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


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


def _synthetic_update_resolution_boundary() -> dict[str, Any]:
    return {
        "source": "synthetic_button_contract_double",
        "scenario": "safe_executor_evidence_recount",
        "production_button_contract_exercised": False,
        "button_contract_update_resolution_applicable": False,
        "reason": "synthetic monkeypatch bypasses production _design_guide_button_contract",
        "future_kwargs_tolerated": True,
    }


def _button_contract_for(
    item: dict | None,
    *,
    state: dict,
    blocking_reason_override: str | None = None,
    **_ignored_kwargs: Any,
) -> dict[str, Any]:
    return {
        "action_type": "apply_resolved_candidate",
        "family": "shear",
        "updates": {},
        "expected_util": None,
        "actionable": False,
        "preview_pass": False,
        "blocking_reason": blocking_reason_override
        or "candidate_preview_not_in_target_band_after_active_failure",
        "candidate_id": "safe_executor_contract_before",
        "source_candidate_id": "safe_executor_contract_before",
    }


def _input_item() -> dict[str, Any]:
    return {
        "id": "safe_executor_recount_input",
        "candidate_id": "safe_executor_recount_before",
        "source_candidate_id": "safe_executor_recount_before",
        "title_main": "Shear capacity is low",
        "title": "Shear capacity is low",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "guidance_intent": "required_fix",
        "action_type": "apply_resolved_candidate",
        "updates": {},
        "candidate_search_evidence": {
            "evidence_id": "safe_executor_recount_evidence",
            "target_band_candidate_count": 0,
            "safe_executor_backed_candidates_count": 0,
            "active_failures": ["shear"],
            "candidate_rows": [
                {
                    "candidate_id": "safe_executor_row_after",
                    "safe_executor_backed": True,
                    "is_executable": True,
                    "preview_pass": True,
                    "proposed_updates": {"s_lig": 125.0},
                    "preview_util": 1.04,
                    "title": "Safe shear repair",
                    "distance_to_band": 0.14,
                    "preview_statuses": {"shear": "PASS"},
                },
                {
                    "candidate_id": "unsafe_row_ignored",
                    "safe_executor_backed": False,
                    "is_executable": True,
                    "preview_pass": True,
                    "proposed_updates": {"s_lig": 200.0},
                    "preview_util": 1.2,
                    "preview_statuses": {"shear": "PASS"},
                },
            ],
        },
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


def main() -> int:
    import inputs_page

    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    runtime_path = ARTIFACT_DIR / f"design_guide_safe_executor_evidence_runtime_{timestamp}.jsonl"
    output_path = ARTIFACT_DIR / f"design_guide_safe_executor_evidence_snapshot_{timestamp}.json"
    if runtime_path.exists():
        runtime_path.unlink()

    restore: list[tuple[str, object]] = []
    _patch_attr(inputs_page, "_design_guide_button_contract", _button_contract_for, restore)
    _patch_attr(inputs_page, "_guidance_item_as_advisory", _advisory_item, restore)
    _patch_attr(inputs_page, "_design_mode_config", lambda goal: {"goal": goal}, restore)
    _patch_attr(inputs_page, "_design_optimisation_goal", lambda state: "balanced", restore)
    _patch_attr(inputs_page, "_resolved_efficiency_target_band", lambda mode_cfg, goal=None: (0.75, 0.9, 0.825), restore)
    _patch_attr(inputs_page, "_format_guidance_title", lambda title, util=None: f"{title} ({util})", restore)
    _patch_attr(inputs_page, "_design_guide_primary_apply_state_fingerprint", lambda state=None: "synthetic_safe_executor_fingerprint", restore)

    old_env = os.environ.get("DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH")
    os.environ["DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH"] = str(runtime_path)
    input_item = _input_item()
    input_item_before_hash = inputs_page._publication_snapshot_hash(input_item)
    input_evidence_before_hash = inputs_page._publication_snapshot_hash(input_item.get("candidate_search_evidence") or {})
    try:
        output_items = inputs_page._design_guide_apply_button_contracts_to_items(
            [copy.deepcopy(input_item)],
            state={"synthetic_safe_executor_recount": True},
            primary_blocking_reason="candidate_preview_not_in_target_band_after_active_failure",
        )
    finally:
        if old_env is None:
            os.environ.pop("DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH", None)
        else:
            os.environ["DESIGN_GUIDE_APPLY_BUTTON_CONTRACT_SNAPSHOT_PATH"] = old_env
        for name, value in reversed(restore):
            setattr(inputs_page, name, value)

    rows = _load_rows(runtime_path)
    selected = rows[-1] if rows else {}
    evidence_rows = selected.get("safe_executor_evidence_rows") if isinstance(selected, dict) else []
    typed = selected.get("typed_binding_result") if isinstance(selected, dict) else {}
    typed_evidence_rows = typed.get("safe_executor_evidence_rows") if isinstance(typed, dict) else []
    output_item = dict(output_items[0] if output_items else {})
    output_evidence = dict(output_item.get("candidate_search_evidence") or {})
    record = dict(evidence_rows[0]) if isinstance(evidence_rows, list) and evidence_rows else {}
    failures: list[str] = []
    if not rows:
        failures.append("runtime_snapshot_missing")
    if not record:
        failures.append("safe_executor_evidence_record_missing")
    if record and int(record.get("input_row_count") or 0) != 2:
        failures.append("input_row_count_mismatch")
    if record and int(record.get("counted_safe_executor_rows") or 0) != 1:
        failures.append("counted_safe_executor_rows_mismatch")
    if record and bool(record.get("evidence_object_reused")):
        failures.append("evidence_object_reused")
    if record and not bool(record.get("evidence_object_copied")):
        failures.append("evidence_object_not_copied")
    if "safe_executor_backed_candidates_count" not in output_evidence:
        failures.append("safe_executor_count_not_written")
    if output_evidence.get("closest_safe_candidate_id") != "safe_executor_row_after":
        failures.append("closest_safe_candidate_id_mismatch")
    if inputs_page._publication_snapshot_hash(input_item) != input_item_before_hash:
        failures.append("input_item_mutated")
    if inputs_page._publication_snapshot_hash(input_item.get("candidate_search_evidence") or {}) != input_evidence_before_hash:
        failures.append("input_evidence_mutated")
    if isinstance(typed_evidence_rows, list) and isinstance(evidence_rows, list):
        if len(typed_evidence_rows) != len(evidence_rows):
            failures.append("typed_evidence_record_count_mismatch")
    update_resolution_boundary = _synthetic_update_resolution_boundary()
    if bool(update_resolution_boundary.get("production_button_contract_exercised")):
        failures.append("synthetic_boundary_claims_production_contract")
    if bool(update_resolution_boundary.get("button_contract_update_resolution_applicable")):
        failures.append("synthetic_boundary_claims_update_resolution_applicable")

    report = {
        "schema": "design_guide_safe_executor_evidence_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "production_button_contract_exercised": False,
        "button_contract_update_resolution_applicable": False,
        "button_contract_update_resolution_boundary": update_resolution_boundary,
        "runtime_snapshot_path": str(runtime_path),
        "runtime_row_count": len(rows),
        "input_item_hash_before": input_item_before_hash,
        "input_evidence_hash_before": input_evidence_before_hash,
        "input_item_hash_after": inputs_page._publication_snapshot_hash(input_item),
        "input_evidence_hash_after": inputs_page._publication_snapshot_hash(input_item.get("candidate_search_evidence") or {}),
        "output_evidence_hash": inputs_page._publication_snapshot_hash(output_evidence),
        "safe_executor_evidence_rows": evidence_rows,
        "typed_safe_executor_evidence_rows": typed_evidence_rows,
        "output_evidence": output_evidence,
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    if failures:
        print(f"FAIL: {output_path}")
        return 1
    print(f"PASS: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
