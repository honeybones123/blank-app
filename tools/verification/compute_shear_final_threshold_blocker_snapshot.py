"""Focused snapshot for shear final-threshold blocker materialization.

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
BRANCH_EVENT = "late_evidence_shear_final_threshold_blocker_materialized"
REQUIRED_TITLE = "Shear cleanup blocked by final efficiency threshold"
REQUIRED_REASON_PHRASE = "final accepted-family shear threshold"


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
        "uls_Vstar": 60.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }


def _overview() -> dict[str, Any]:
    return {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.88, "shear": 0.74, "crack": 0.42, "deflection": 0.39},
        "any_fail": False,
        "all_key_pass": True,
        "worst_util": 0.74,
        "governing_util": 0.74,
    }


def _shear_final_threshold_item() -> dict[str, Any]:
    updates = {"s_lig": 180.0, "lig_legs": 3}
    evidence = {
        "family": "shear",
        "search_scope": "synthetic_shear_final_threshold_blocker",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "selected_candidate_id": "synthetic_shear_final_threshold_candidate",
        "best_safe_candidate_id": "synthetic_shear_final_threshold_candidate",
        "selected_candidate_updates": dict(updates),
        "best_safe_candidate_updates": dict(updates),
        "selected_candidate_util": 0.74,
        "best_safe_final_util": 0.74,
        "safe_candidate_count": 1,
        "safe_cleanup_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "target_band_candidate_count": 0,
        "accepted_band_candidate_count": 0,
        "executable_candidate_count": 1,
        "executable_cleanup_count": 1,
        "one_click_target_reaching_candidate_exists": False,
        "exact_blockers_by_family": {
            "shear": {
                "family": "shear",
                "current_util": 0.74,
                "reason": "stale synthetic final-threshold blocker",
            }
        },
        "post_click_exact_blockers_by_family": {
            "shear": {
                "family": "shear",
                "current_util": 0.74,
                "reason": "stale synthetic final-threshold blocker",
            }
        },
        "cleanup_evidence_by_family": {"shear": {"candidate_id": "synthetic_shear_final_threshold_candidate"}},
        "post_click_cleanup_evidence_by_family": {
            "shear": {"candidate_id": "synthetic_shear_final_threshold_candidate"}
        },
    }
    action_payload = {
        "action_type": "apply_resolved_candidate",
        "source_candidate_id": "synthetic_shear_final_threshold_candidate",
        "candidate_id": "synthetic_shear_final_threshold_candidate",
        "updates": dict(updates),
        "preview_pass": False,
        "preview_status": "BLOCKED",
        "expected_util": 0.74,
        "candidate_search_evidence": dict(evidence),
    }
    resolved_candidate = {
        "candidate_id": "synthetic_shear_final_threshold_candidate",
        "source_candidate_id": "synthetic_shear_final_threshold_candidate",
        "updates": dict(updates),
        "candidate_post_util": 0.74,
        "candidate_search_evidence": dict(evidence),
    }
    return {
        "id": "synthetic_shear_final_threshold_primary",
        "candidate_id": "synthetic_shear_final_threshold_candidate",
        "source_candidate_id": "synthetic_shear_final_threshold_candidate",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "selected_family": "SHEAR_FAIL_GOVERNS",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "title_main": REQUIRED_TITLE,
        "title": REQUIRED_TITLE,
        "primary_action": "Apply safe shear cleanup",
        "secondary_action": "Review shear detailing",
        "reasoning": "Why: synthetic cleanup remains below the final shear acceptance threshold.",
        "status": "FAIL",
        "guidance_intent": "efficiency_tightening",
        "primary_card_actionable": True,
        "action_type": "apply_resolved_candidate",
        "updates": dict(updates),
        "candidate_search_evidence": dict(evidence),
        "action_payload": action_payload,
        "resolved_candidate": resolved_candidate,
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": dict(updates),
            "preview_pass": False,
            "expected_util": 0.74,
            "blocking_reason": None,
            "source_candidate_id": "synthetic_shear_final_threshold_candidate",
            "candidate_id": "synthetic_shear_final_threshold_candidate",
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
    primary = _shear_final_threshold_item()

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_shear_final_threshold_blocker",
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
            "canonical_pack_source": "synthetic_shear_final_threshold_fixture",
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
        "_overview_active_failure_keys": lambda overview: set(),
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
    trace_path = TRACE_DIR / f"compute_shear_final_threshold_blocker_trace_{stamp}.jsonl"
    record_path = TRACE_DIR / f"compute_shear_final_threshold_blocker_result_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_shear_final_threshold_blocker_snapshot_{stamp}.json"

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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_SHEAR_FINAL_THRESHOLD_BLOCKER"
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
    branch_rows = _route_rows(trace_rows, BRANCH_EVENT)
    enter_rows = _route_rows(trace_rows, "late_evidence_lane_enter")
    exit_rows = _route_rows(trace_rows, "late_evidence_lane_exit")
    safe_cleanup_rows = _route_rows(trace_rows, "late_evidence_safe_cleanup_rehydrated")
    rebound_rows = _route_rows(trace_rows, "late_evidence_contract_rebound_applied")
    active_under_capacity_rows = _route_rows(trace_rows, "late_evidence_active_under_capacity_blocker_materialized")
    typed_rows = _typed_results(record_rows)
    typed = typed_rows[-1] if typed_rows else {}
    parity = typed.get("parity_checks") if isinstance(typed.get("parity_checks"), dict) else {}

    output_items = list(output.get("guidance_items") or []) if isinstance(output, dict) else []
    primary = output_items[0] if output_items and isinstance(output_items[0], dict) else {}
    action_payload = dict(primary.get("action_payload") or {})
    resolved_candidate = dict(primary.get("resolved_candidate") or {})
    evidence = dict(
        primary.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved_candidate.get("candidate_search_evidence")
        or {}
    )
    contract = dict(primary.get("button_contract") or {})
    exact_blockers = dict(
        primary.get("exact_blockers_by_family")
        or evidence.get("exact_blockers_by_family")
        or {}
    )
    branch_payload = branch_rows[-1].get("payload") if branch_rows else {}
    enter_payload = enter_rows[-1].get("payload") if enter_rows else {}
    exit_payload = exit_rows[-1].get("payload") if exit_rows else {}

    failures: list[str] = []
    if len(enter_rows) != 1:
        failures.append(f"late_evidence_enter_count:{len(enter_rows)}")
    if len(branch_rows) != 1:
        failures.append(f"shear_final_threshold_branch_count:{len(branch_rows)}")
    if rebound_rows:
        failures.append(f"unexpected_contract_rebound_count:{len(rebound_rows)}")
    if not typed_rows:
        failures.append("typed_sync_record_missing")
    if parity and any(value is not True for value in parity.values()):
        failures.append("typed_sync_parity_failed")
    reason = str(evidence.get("active_under_capacity_blocker_reason") or contract.get("blocking_reason") or "")
    if REQUIRED_REASON_PHRASE not in reason:
        failures.append("final_threshold_reason_missing")
    if evidence.get("active_under_capacity_blocker") is not True:
        failures.append("active_under_capacity_blocker_missing")
    if evidence.get("active_under_capacity_blocker_family") != "shear":
        failures.append("active_under_capacity_blocker_family_not_shear")
    if not exact_blockers.get("shear"):
        failures.append("shear_exact_blocker_missing")
    if contract.get("enabled") is not False or contract.get("actionable") is not False:
        failures.append("button_contract_not_disabled")
    if contract.get("updates") not in ({}, None):
        failures.append("disabled_contract_updates_not_empty")
    if action_payload and action_payload.get("updates") not in ({}, None):
        failures.append("action_payload_updates_not_empty_after_blocker")
    if primary.get("family") != "shear" or primary.get("check_key") != "shear":
        failures.append("primary_family_not_shear")
    if str(primary.get("displayed_status") or "").upper() != "BLOCKED":
        failures.append("displayed_status_not_blocked")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "compute_shear_final_threshold_blocker_snapshot.v1",
        "status": status,
        "failures": failures,
        "scenario": "synthetic_shear_final_threshold_blocker",
        "trace_path": str(trace_path),
        "record_path": str(record_path),
        "branch_event": BRANCH_EVENT,
        "branch_event_count": len(branch_rows),
        "safe_cleanup_rehydration_count": len(safe_cleanup_rows),
        "active_under_capacity_event_count": len(active_under_capacity_rows),
        "contract_rebound_event_count": len(rebound_rows),
        "late_evidence_enter_count": len(enter_rows),
        "late_evidence_exit_count": len(exit_rows),
        "typed_sync_record_count": len(typed_rows),
        "input_context": {
            "primary_summary": enter_payload.get("primary") if isinstance(enter_payload, dict) else None,
            "existing_evidence_keys": list(
                (enter_payload.get("existing_evidence_keys") or []) if isinstance(enter_payload, dict) else []
            ),
        },
        "branch_probe": branch_payload,
        "final_threshold_blocker": {
            "reason": reason,
            "failed_check_name": evidence.get("failed_check_name"),
            "failed_check_status": evidence.get("failed_check_status"),
            "failed_check_util": evidence.get("failed_check_util"),
            "failed_check_capacity_or_limit": evidence.get("failed_check_capacity_or_limit"),
            "attempted_updates": dict(evidence.get("attempted_updates") or {}),
            "exact_blocker": dict(exact_blockers.get("shear") or {}),
        },
        "generated_item_fields": {
            "id": primary.get("id"),
            "title": primary.get("title"),
            "title_main": primary.get("title_main"),
            "family": primary.get("family"),
            "check_key": primary.get("check_key"),
            "guidance_intent": primary.get("guidance_intent"),
            "primary_card_actionable": primary.get("primary_card_actionable"),
            "status": primary.get("status"),
            "displayed_status": primary.get("displayed_status"),
            "displayed_util": primary.get("displayed_util"),
            "title_util": primary.get("title_util"),
        },
        "publication_handoff_fields": {
            "selected_family": primary.get("selected_family"),
            "selected_family_id": primary.get("selected_family_id"),
            "published_family_id": primary.get("published_family_id"),
            "cta_family_id": primary.get("cta_family_id"),
            "selected_action_family": primary.get("selected_action_family"),
            "action_type": primary.get("action_type"),
            "final_state_class": primary.get("final_state_class"),
        },
        "mutation_map": {
            "input_item_hash": ((enter_payload.get("primary") or {}).get("hash") if isinstance(enter_payload, dict) else None),
            "branch_evidence_hash": branch_payload.get("evidence_hash") if isinstance(branch_payload, dict) else None,
            "branch_exact_blockers_hash": branch_payload.get("exact_blockers_hash") if isinstance(branch_payload, dict) else None,
            "exit_item_hash": ((exit_payload.get("primary") or {}).get("hash") if isinstance(exit_payload, dict) else None),
            "output_item_hash": _stable_hash(primary),
            "evidence_hash": _stable_hash(evidence),
            "evidence_keys": sorted(str(k) for k in evidence.keys())[:100],
            "proof_fields": {
                "candidate_search_exhaustive": evidence.get("candidate_search_exhaustive"),
                "outside_target_band_allowed": evidence.get("outside_target_band_allowed"),
                "outside_target_band_allowed_category": evidence.get("outside_target_band_allowed_category"),
                "one_click_target_reaching_candidate_exists": evidence.get("one_click_target_reaching_candidate_exists"),
                "local_cleanup_search_ran": evidence.get("local_cleanup_search_ran"),
                "local_cleanup_search_exhaustive": evidence.get("local_cleanup_search_exhaustive"),
                "local_cleanup_blocked_reasons": list(evidence.get("local_cleanup_blocked_reasons") or []),
            },
            "action_payload_hash": _stable_hash(action_payload),
            "action_payload_fields": {
                "action_type": action_payload.get("action_type"),
                "candidate_id": action_payload.get("candidate_id"),
                "source_candidate_id": action_payload.get("source_candidate_id"),
                "updates": dict(action_payload.get("updates") or {}),
                "preview_pass": action_payload.get("preview_pass"),
                "expected_util": action_payload.get("expected_util"),
            },
            "resolved_candidate_hash": _stable_hash(resolved_candidate),
            "button_contract_hash": _stable_hash(contract),
            "button_contract_state": {
                "enabled": contract.get("enabled"),
                "actionable": contract.get("actionable"),
                "action_type": contract.get("action_type"),
                "family": contract.get("family"),
                "updates": dict(contract.get("updates") or {}),
                "preview_pass": contract.get("preview_pass"),
                "expected_util": contract.get("expected_util"),
                "blocking_reason": contract.get("blocking_reason"),
                "source_candidate_id": contract.get("source_candidate_id"),
                "candidate_id": contract.get("candidate_id"),
            },
            "typed_sync_changed_fields": list(typed.get("changed_fields") or []),
            "typed_sync_parity_checks": dict(parity),
        },
        "output": {
            "guidance_items_count": len(output_items),
            "primary_hash": _stable_hash(primary),
            "debug_trace_hash": _stable_hash((output or {}).get("debug_trace") or {}),
            "final_selected_item_identity": {
                "id": primary.get("id"),
                "candidate_id": primary.get("candidate_id"),
                "source_candidate_id": primary.get("source_candidate_id"),
                "family": primary.get("family"),
                "check_key": primary.get("check_key"),
            },
        },
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{status}: {output_path}")
    print(f"trace: {trace_path}")
    print(f"typed-result: {record_path}")
    print(f"branch-event-count: {len(branch_rows)}")
    print(f"contract-rebound-count: {len(rebound_rows)}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
