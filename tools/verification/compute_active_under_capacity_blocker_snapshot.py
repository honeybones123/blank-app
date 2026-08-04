"""Focused snapshot for compute active-under-capacity blocker materialization.

This is synthetic compute-path coverage. The upstream core compute result is
controlled so the verifier can enter the real late evidence/proof lane without
changing product logic or bypassing the target branch body.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ARTIFACT_DIR = REPO / "artifacts" / "verification"
TRACE_DIR = REPO / "artifacts" / "traces"


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 600.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 90.0,
        "uls_Vstar": 220.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }


def _overview() -> dict[str, Any]:
    return {
        "statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.82, "shear": 1.18, "crack": 0.42, "deflection": 0.39},
        "any_fail": True,
        "all_key_pass": False,
        "worst_util": 1.18,
        "governing_util": 1.18,
    }


def _active_under_capacity_item() -> dict[str, Any]:
    evidence = {
        "family": "shear",
        "search_scope": "synthetic_shear_active_failure_practical_ladder",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "selected_candidate_id": "synthetic_blocked_shear_repair_candidate",
        "attempted_candidate_id": "synthetic_blocked_shear_repair_candidate",
        "attempted_updates": {
            "s_lig": "tighten link spacing trial",
            "db_lig": "increase link diameter trial",
            "lig_legs": "increase link legs trial",
        },
        "failed_candidate_reasons": ["synthetic shear repair remains blocked by detailing limits"],
        "active_failures": ["shear"],
        "total_candidates_considered": 3,
        "safe_candidate_count": 0,
        "executable_candidate_count": 0,
    }
    return {
        "id": "synthetic_active_under_capacity_primary",
        "candidate_id": "synthetic_blocked_shear_repair_candidate",
        "source_candidate_id": "synthetic_blocked_shear_repair_candidate",
        "family": "shear",
        "check_key": "shear",
        "selected_family": "SHEAR_FAIL_GOVERNS",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "title_main": "Shear repair blocked by detailing limits",
        "title": "Shear repair blocked by detailing limits",
        "primary_action": "No one-click shear repair is available",
        "secondary_action": "Try wider section or lower shear demand",
        "reasoning": "Why: synthetic shear repair search exhausted the practical ladder.",
        "status": "FAIL",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "action_type": None,
        "updates": {},
        "candidate_search_evidence": dict(evidence),
        "action_payload": {
            "action_type": None,
            "source_candidate_id": "synthetic_blocked_shear_repair_candidate",
            "updates": {},
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "candidate_id": "synthetic_blocked_shear_repair_candidate",
            "source_candidate_id": "synthetic_blocked_shear_repair_candidate",
            "updates": {},
            "candidate_search_evidence": dict(evidence),
        },
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "shear",
            "updates": {},
            "preview_pass": False,
            "expected_util": None,
            "blocking_reason": "synthetic shear repair remains blocked by detailing limits",
            "source_candidate_id": None,
            "candidate_id": None,
        },
    }


@contextmanager
def _patched(module: Any, replacements: dict[str, Any]):
    old_values: dict[str, Any] = {}
    missing: set[str] = set()
    for name, value in replacements.items():
        if hasattr(module, name):
            old_values[name] = getattr(module, name)
        else:
            missing.add(name)
        setattr(module, name, value)
    try:
        yield
    finally:
        for name in replacements:
            if name in old_values:
                setattr(module, name, old_values[name])
            elif name in missing:
                delattr(module, name)


def _run_scenario(module: Any) -> dict[str, Any]:
    state = _base_state()
    primary = _active_under_capacity_item()

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_active_under_capacity_blocker",
                    "overview": _overview(),
                    "guidance_resolved_state": dict(_state or {}),
                    "selected_action_type": primary.get("action_type"),
                    "selected_action_family": primary.get("family"),
                    "selected_title": primary.get("title_main"),
                    "candidate_search_evidence": dict(primary.get("candidate_search_evidence") or {}),
                }
            )
        return [dict(primary)]

    replacements = {
        "get_rerun_pure_cache": lambda *args, **kwargs: None,
        "set_rerun_pure_cache": lambda *args, **kwargs: None,
        "_design_guide_lightweight_guidance_state": lambda incoming: dict(incoming or {}),
        "_build_canonical_design_state_pack": lambda incoming: {
            **dict(incoming or {}),
            "canonical_pack_built": True,
            "canonical_pack_valid": True,
            "canonical_pack_source": "synthetic_active_under_capacity_fixture",
        },
        "_canonical_pack_is_valid": lambda pack: True,
        "_design_state_coherence_check": lambda pack: {"coherence_should_block": False},
        "_resolve_compute_design_guidance_family_early_dispatch": lambda **kwargs: None,
        "_compute_design_guidance_items_core": _core,
        "_ensure_design_guide_debug_trace_coherent": lambda *, state, guidance_items, debug_trace: (
            dict(debug_trace or {}),
            [],
        ),
        "_dedupe_guidance_items_for_display": lambda items, state: (list(items or []), {}),
        "_collapse_to_single_primary_guidance_item": lambda items, state: (list(items or []), {"collapsed": False}),
        "_sanitize_guidance_items_for_executor_contract": lambda items, **kwargs: list(items or []),
        "_maybe_promote_safe_local_cleanup_primary": lambda items, **kwargs: (list(items or []), {}),
        "_prefer_target_band_guidance_item_order": lambda items, **kwargs: list(items or []),
        "_align_guidance_items_to_candidate_search_evidence": lambda items: list(items or []),
        "_design_guide_apply_copy_model_to_items": lambda items, **kwargs: list(items or []),
        "_design_guide_apply_button_contracts_to_items": lambda items, **kwargs: list(items or []),
        "_design_guide_apply_display_truth_to_items": lambda items, **kwargs: list(items or []),
        "_attach_exact_low_util_evidence_to_visible_item": lambda item, debug_trace: dict(item or {}),
        "_resolve_compute_design_guidance_publication_handoff": lambda *, state, collapsed_guidance_items, debug_trace, request_kind_norm: list(collapsed_guidance_items or []),
        "_apply_compute_design_guidance_engine_terminal_decision": lambda *, collapsed_guidance_items, debug_trace, disp: list(collapsed_guidance_items or []),
        "_restore_compute_low_bending_terminal_cleanup": lambda *, collapsed_guidance_items, debug_trace, disp, terminal_state, terminal_state_source: (
            list(collapsed_guidance_items or []),
            terminal_state,
            terminal_state_source,
        ),
        "_recommendation_result_for_primary_guidance_card": lambda items, state, **kwargs: None,
        "_design_guide_terminal_state_from_render_artifacts": lambda items, debug_trace: None,
        "_derive_design_guide_terminal_state_from_current_overview": lambda debug_trace, state, items: None,
        "_design_optimisation_goal": lambda state: "balanced",
        "_design_mode_config": lambda goal: {"target_low": 0.85, "target_high": 1.0},
        "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (0.85, 1.0, "synthetic"),
        "_shared_state_snapshot": lambda: {},
        "_collect_design_overview": lambda *args, **kwargs: _overview(),
        "_overview_active_failure_keys": lambda overview: {"shear"},
        "_active_fail_near_current_repair_item": lambda *args, **kwargs: None,
        "_direct_target_band_guidance_item": lambda *args, **kwargs: None,
        "_attach_design_brain_result_boundary": lambda out, **kwargs: dict(out or {}),
    }
    with _patched(module, replacements):
        return module._compute_design_guidance_items(
            dict(state),
            debug_enabled=True,
            request_kind="design_guide",
        )


def _route_rows(trace_rows: list[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    return [
        row
        for row in trace_rows
        if row.get("event") == "compute_guidance_route"
        and row.get("route_event") == event
    ]


def _typed_results(record_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in record_rows:
        if row.get("event") != "compute_late_evidence_sync_typed_result":
            continue
        typed = row.get("typed_result")
        if isinstance(typed, dict):
            results.append(dict(typed))
    return results


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"compute_active_under_capacity_blocker_trace_{stamp}.jsonl"
    record_path = TRACE_DIR / f"compute_active_under_capacity_blocker_result_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_active_under_capacity_blocker_snapshot_{stamp}.json"

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
            "DESIGN_GUIDE_COMPUTE_LATE_EVIDENCE_SYNC_RESULT_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_ACTIVE_UNDER_CAPACITY_BLOCKER"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    os.environ["DESIGN_GUIDE_COMPUTE_LATE_EVIDENCE_SYNC_RESULT_PATH"] = str(record_path)
    try:
        output = _run_scenario(module)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    trace_rows = _load_jsonl(trace_path)
    record_rows = _load_jsonl(record_path)
    branch_rows = _route_rows(trace_rows, "late_evidence_active_under_capacity_blocker_materialized")
    enter_rows = _route_rows(trace_rows, "late_evidence_lane_enter")
    exit_rows = _route_rows(trace_rows, "late_evidence_lane_exit")
    forbidden_rows = _route_rows(trace_rows, "late_evidence_contract_rebound_applied")
    typed_rows = _typed_results(record_rows)
    typed = typed_rows[-1] if typed_rows else {}
    parity = typed.get("parity_checks") if isinstance(typed.get("parity_checks"), dict) else {}

    output_items = list(output.get("guidance_items") or []) if isinstance(output, dict) else []
    primary = output_items[0] if output_items and isinstance(output_items[0], dict) else {}
    evidence = dict(
        primary.get("candidate_search_evidence")
        or (primary.get("action_payload") or {}).get("candidate_search_evidence")
        or (primary.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    contract = dict(primary.get("button_contract") or {})
    exact_blockers = dict(
        primary.get("exact_blockers_by_family")
        or evidence.get("exact_blockers_by_family")
        or {}
    )

    failures: list[str] = []
    if len(enter_rows) != 1:
        failures.append(f"late_evidence_enter_count:{len(enter_rows)}")
    if len(branch_rows) != 1:
        failures.append(f"active_under_capacity_branch_count:{len(branch_rows)}")
    if forbidden_rows:
        failures.append(f"unexpected_contract_rebound_count:{len(forbidden_rows)}")
    if not typed_rows:
        failures.append("typed_sync_record_missing")
    if parity and any(value is not True for value in parity.values()):
        failures.append("typed_sync_parity_failed")
    if not evidence.get("active_under_capacity_blocker"):
        failures.append("active_under_capacity_blocker_missing")
    if evidence.get("active_under_capacity_blocker_family") != "shear":
        failures.append("active_under_capacity_blocker_family_not_shear")
    if not evidence.get("active_under_capacity_blocker_reason"):
        failures.append("active_under_capacity_blocker_reason_missing")
    if not exact_blockers.get("shear"):
        failures.append("shear_exact_blocker_missing")
    if contract.get("actionable") is not False or contract.get("enabled") is not False:
        failures.append("disabled_contract_not_preserved")
    if contract.get("blocking_reason") != evidence.get("active_under_capacity_blocker_reason"):
        failures.append("blocking_reason_mismatch")

    status = "PASS" if not failures else "FAIL"
    branch_payload = branch_rows[-1].get("payload") if branch_rows else {}
    enter_payload = enter_rows[-1].get("payload") if enter_rows else {}
    exit_payload = exit_rows[-1].get("payload") if exit_rows else {}
    snapshot = {
        "schema": "compute_active_under_capacity_blocker_snapshot.v1",
        "status": status,
        "failures": failures,
        "scenario": "synthetic_shear_active_under_capacity_blocker",
        "trace_path": str(trace_path),
        "record_path": str(record_path),
        "branch_event": "late_evidence_active_under_capacity_blocker_materialized",
        "branch_event_count": len(branch_rows),
        "late_evidence_enter_count": len(enter_rows),
        "late_evidence_exit_count": len(exit_rows),
        "typed_sync_record_count": len(typed_rows),
        "input_context": {
            "primary_summary": enter_payload.get("primary") if isinstance(enter_payload, dict) else None,
            "existing_evidence_keys": list((enter_payload.get("existing_evidence_keys") or []) if isinstance(enter_payload, dict) else []),
        },
        "branch_probe": branch_payload,
        "publication_handoff_fields": {
            "selected_family": primary.get("selected_family"),
            "selected_family_id": primary.get("selected_family_id"),
            "published_family_id": primary.get("published_family_id"),
            "cta_family_id": primary.get("cta_family_id"),
            "family": primary.get("family"),
            "check_key": primary.get("check_key"),
            "title": primary.get("title"),
            "title_main": primary.get("title_main"),
            "status": primary.get("status"),
            "action_type": primary.get("action_type"),
            "primary_card_actionable": primary.get("primary_card_actionable"),
            "final_state_class": primary.get("final_state_class"),
        },
        "mutation_map": {
            "input_item_hash": ((enter_payload.get("primary") or {}).get("hash") if isinstance(enter_payload, dict) else None),
            "branch_evidence_hash": branch_payload.get("evidence_hash") if isinstance(branch_payload, dict) else None,
            "exit_item_hash": ((exit_payload.get("primary") or {}).get("hash") if isinstance(exit_payload, dict) else None),
            "output_item_hash": _stable_hash(primary),
            "evidence_hash": _stable_hash(evidence),
            "evidence_keys": sorted(str(k) for k in evidence.keys())[:90],
            "active_under_capacity_blocker_reason": evidence.get("active_under_capacity_blocker_reason"),
            "attempted_updates": dict(evidence.get("attempted_updates") or {}),
            "exact_blockers_by_family": exact_blockers,
            "action_payload_hash": _stable_hash(primary.get("action_payload") or {}),
            "resolved_candidate_hash": _stable_hash(primary.get("resolved_candidate") or {}),
            "button_contract_hash": _stable_hash(contract),
            "button_contract_state": {
                "enabled": contract.get("enabled"),
                "actionable": contract.get("actionable"),
                "action_type": contract.get("action_type"),
                "family": contract.get("family"),
                "updates": dict(contract.get("updates") or {}),
                "preview_pass": contract.get("preview_pass"),
                "blocking_reason": contract.get("blocking_reason"),
                "source_candidate_id": contract.get("source_candidate_id"),
                "candidate_id": contract.get("candidate_id"),
            },
            "typed_sync_changed_fields": list(typed.get("changed_fields") or []),
            "typed_sync_parity_checks": dict(parity),
            "typed_sync_active_under_capacity_blocker": bool(typed.get("active_under_capacity_blocker")),
            "typed_sync_exact_blockers_present": bool(typed.get("exact_blockers_present")),
        },
        "output": {
            "guidance_items_count": len(output_items),
            "primary_hash": _stable_hash(primary),
            "debug_trace_hash": _stable_hash((output or {}).get("debug_trace") or {}),
            "final_selected_item_identity": {
                "id": primary.get("id"),
                "candidate_id": primary.get("candidate_id"),
                "source_candidate_id": primary.get("source_candidate_id"),
            },
        },
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{status}: {output_path}")
    print(f"trace: {trace_path}")
    print(f"typed-result: {record_path}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
