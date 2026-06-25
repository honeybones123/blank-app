"""Focused snapshot for coherence active-repair republish materialization.

This is synthetic compute-path coverage. The upstream core compute result is
controlled so the verifier enters the real late evidence/coherence lane without
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
BRANCH_EVENT = "late_evidence_coherence_active_repair_republished"
CONTRACT_REBOUND_EVENT = "late_evidence_contract_rebound_applied"
ACTIVE_UNDER_CAPACITY_EVENT = "late_evidence_active_under_capacity_blocker_materialized"
SHEAR_FINAL_THRESHOLD_EVENT = "late_evidence_shear_final_threshold_blocker_materialized"


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
        "utils": {"bending": 0.84, "shear": 1.12, "crack": 0.42, "deflection": 0.39},
        "any_fail": True,
        "all_key_pass": False,
        "worst_util": 1.12,
        "governing_util": 1.12,
    }


def _blocked_primary_item() -> dict[str, Any]:
    evidence = {
        "family": "shear",
        "search_scope": "synthetic_coherence_primary_blocked",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "selected_candidate_id": "synthetic_blocked_primary_candidate",
        "attempted_candidate_id": "synthetic_blocked_primary_candidate",
        "attempted_updates": {"s_lig": "tighten link spacing trial"},
        "failed_candidate_reasons": ["synthetic primary remained blocked before coherence repair"],
        "active_failures": ["shear"],
        "safe_candidate_count": 0,
        "executable_candidate_count": 0,
    }
    return {
        "id": "synthetic_coherence_blocked_primary",
        "candidate_id": "synthetic_blocked_primary_candidate",
        "source_candidate_id": "synthetic_blocked_primary_candidate",
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
        "reasoning": "Why: synthetic primary is blocked until the coherence repair is republished.",
        "status": "FAIL",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "action_type": None,
        "updates": {},
        "candidate_search_evidence": dict(evidence),
        "action_payload": {
            "action_type": None,
            "source_candidate_id": "synthetic_blocked_primary_candidate",
            "updates": {},
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "candidate_id": "synthetic_blocked_primary_candidate",
            "source_candidate_id": "synthetic_blocked_primary_candidate",
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
            "blocking_reason": "synthetic primary remained blocked before coherence repair",
            "source_candidate_id": None,
            "candidate_id": None,
        },
    }


def _coherence_repair_item() -> dict[str, Any]:
    updates = {"s_lig": 125.0, "lig_legs": 3}
    evidence = {
        "family": "shear",
        "search_scope": "synthetic_coherence_active_repair",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "selected_candidate_id": "synthetic_coherence_active_repair_candidate",
        "best_safe_candidate_id": "synthetic_coherence_active_repair_candidate",
        "selected_candidate_updates": dict(updates),
        "best_safe_candidate_updates": dict(updates),
        "selected_candidate_util": 0.92,
        "best_safe_final_util": 0.92,
        "safe_candidate_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "target_band_candidate_count": 1,
        "accepted_band_candidate_count": 1,
        "executable_candidate_count": 1,
        "one_click_target_reaching_candidate_exists": True,
    }
    action_payload = {
        "action_type": "apply_resolved_candidate",
        "source_candidate_id": "synthetic_coherence_active_repair_candidate",
        "candidate_id": "synthetic_coherence_active_repair_candidate",
        "updates": dict(updates),
        "preview_pass": True,
        "preview_status": "PASS",
        "expected_util": 0.92,
        "candidate_search_evidence": dict(evidence),
    }
    resolved_candidate = {
        "candidate_id": "synthetic_coherence_active_repair_candidate",
        "source_candidate_id": "synthetic_coherence_active_repair_candidate",
        "updates": dict(updates),
        "candidate_post_util": 0.92,
        "candidate_search_evidence": dict(evidence),
    }
    return {
        "id": "synthetic_coherence_active_repair",
        "candidate_id": "synthetic_coherence_active_repair_candidate",
        "source_candidate_id": "synthetic_coherence_active_repair_candidate",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "selected_family": "SHEAR_FAIL_GOVERNS",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "title_main": "Apply shear repair",
        "title": "Apply shear repair",
        "primary_action": "Apply shear repair",
        "secondary_action": "Review shear checks",
        "reasoning": "Why: synthetic coherence repair reaches the target band.",
        "status": "FAIL",
        "guidance_intent": "required_fix",
        "primary_card_actionable": True,
        "final_state_class": "action",
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
            "preview_pass": True,
            "expected_util": 0.92,
            "blocking_reason": None,
            "source_candidate_id": "synthetic_coherence_active_repair_candidate",
            "candidate_id": "synthetic_coherence_active_repair_candidate",
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
    primary = _blocked_primary_item()
    repair = _coherence_repair_item()

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_coherence_blocked_primary",
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
            "canonical_pack_source": "synthetic_coherence_active_repair_fixture",
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
        "_resolve_compute_design_guidance_publication_handoff": (
            lambda *, state, collapsed_guidance_items, debug_trace, request_kind_norm: list(
                collapsed_guidance_items or []
            )
        ),
        "_apply_compute_design_guidance_engine_terminal_decision": (
            lambda *, collapsed_guidance_items, debug_trace, disp: list(collapsed_guidance_items or [])
        ),
        "_restore_compute_low_bending_terminal_cleanup": (
            lambda *, collapsed_guidance_items, debug_trace, disp, terminal_state, terminal_state_source: (
                list(collapsed_guidance_items or []),
                terminal_state,
                terminal_state_source,
            )
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
        "_active_fail_near_current_repair_item": lambda *args, **kwargs: dict(repair),
        "_direct_target_band_guidance_item": lambda *args, **kwargs: None,
        "_resolve_recommendation_updates": lambda item, **kwargs: dict(
            (item.get("button_contract") or {}).get("updates") or item.get("updates") or {}
        ),
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
    trace_path = TRACE_DIR / f"compute_coherence_active_repair_republish_trace_{stamp}.jsonl"
    record_path = TRACE_DIR / f"compute_coherence_active_repair_republish_result_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_coherence_active_repair_republish_snapshot_{stamp}.json"

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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_COHERENCE_ACTIVE_REPAIR_REPUBLISH"
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
    rebound_rows = _route_rows(trace_rows, CONTRACT_REBOUND_EVENT)
    active_under_capacity_rows = _route_rows(trace_rows, ACTIVE_UNDER_CAPACITY_EVENT)
    shear_final_threshold_rows = _route_rows(trace_rows, SHEAR_FINAL_THRESHOLD_EVENT)
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
    branch_payload = branch_rows[-1].get("payload") if branch_rows else {}
    enter_payload = enter_rows[-1].get("payload") if enter_rows else {}
    exit_payload = exit_rows[-1].get("payload") if exit_rows else {}
    updates = dict(contract.get("updates") or primary.get("updates") or action_payload.get("updates") or {})

    failures: list[str] = []
    if len(enter_rows) != 1:
        failures.append(f"late_evidence_enter_count:{len(enter_rows)}")
    if len(branch_rows) != 1:
        failures.append(f"coherence_active_repair_branch_count:{len(branch_rows)}")
    if rebound_rows:
        failures.append(f"unexpected_contract_rebound_count:{len(rebound_rows)}")
    if active_under_capacity_rows:
        failures.append(f"unexpected_active_under_capacity_count:{len(active_under_capacity_rows)}")
    if shear_final_threshold_rows:
        failures.append(f"unexpected_shear_final_threshold_count:{len(shear_final_threshold_rows)}")
    if not typed_rows:
        failures.append("typed_sync_record_missing")
    if parity and any(value is not True for value in parity.values()):
        failures.append("typed_sync_parity_failed")
    if primary.get("id") != "synthetic_coherence_active_repair":
        failures.append("primary_not_republished_repair_item")
    if primary.get("title_main") != "Shear capacity is low":
        failures.append("republished_title_not_normalized")
    if primary.get("family") != "shear" or primary.get("check_key") != "shear":
        failures.append("republished_family_not_shear")
    if primary.get("action_type") != "apply_resolved_candidate":
        failures.append("republished_action_type_missing")
    if contract.get("enabled") is not True or contract.get("actionable") is not True:
        failures.append("button_contract_not_enabled")
    if contract.get("preview_pass") is not True:
        failures.append("button_contract_preview_not_pass")
    if not updates:
        failures.append("republished_updates_missing")
    if evidence.get("selected_family_id") != "SHEAR_FAIL_GOVERNS":
        failures.append("selected_family_evidence_not_shear_fail_governs")
    if evidence.get("generic_target_band_search_skipped") is not True:
        failures.append("generic_target_band_skip_evidence_missing")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "compute_coherence_active_repair_republish_snapshot.v1",
        "status": status,
        "failures": failures,
        "scenario": "synthetic_coherence_active_repair_republish",
        "trace_path": str(trace_path),
        "record_path": str(record_path),
        "branch_event": BRANCH_EVENT,
        "branch_event_count": len(branch_rows),
        "contract_rebound_event_count": len(rebound_rows),
        "active_under_capacity_event_count": len(active_under_capacity_rows),
        "shear_final_threshold_event_count": len(shear_final_threshold_rows),
        "late_evidence_enter_count": len(enter_rows),
        "late_evidence_exit_count": len(exit_rows),
        "typed_sync_record_count": len(typed_rows),
        "input_context": {
            "primary_before": enter_payload.get("primary") if isinstance(enter_payload, dict) else None,
            "existing_evidence_keys": list(
                (enter_payload.get("existing_evidence_keys") or []) if isinstance(enter_payload, dict) else []
            ),
        },
        "branch_probe": branch_payload,
        "republished_repair_candidate": {
            "id": primary.get("id"),
            "candidate_id": primary.get("candidate_id"),
            "source_candidate_id": primary.get("source_candidate_id"),
            "family": primary.get("family"),
            "check_key": primary.get("check_key"),
            "expected_util": contract.get("expected_util") or action_payload.get("expected_util"),
            "updates": dict(updates),
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
            "final_state_class": primary.get("final_state_class"),
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
            "input_item_hash": (
                (enter_payload.get("primary") or {}).get("hash") if isinstance(enter_payload, dict) else None
            ),
            "branch_item_hash": (
                (branch_payload.get("primary") or {}).get("hash") if isinstance(branch_payload, dict) else None
            ),
            "branch_evidence_hash": branch_payload.get("evidence_hash") if isinstance(branch_payload, dict) else None,
            "branch_contract_hash": branch_payload.get("contract_hash") if isinstance(branch_payload, dict) else None,
            "branch_updates_hash": branch_payload.get("updates_hash") if isinstance(branch_payload, dict) else None,
            "exit_item_hash": (
                (exit_payload.get("primary") or {}).get("hash") if isinstance(exit_payload, dict) else None
            ),
            "output_item_hash": _stable_hash(primary),
            "evidence_hash": _stable_hash(evidence),
            "evidence_keys": sorted(str(k) for k in evidence.keys())[:100],
            "proof_fields": {
                "candidate_search_exhaustive": evidence.get("candidate_search_exhaustive"),
                "repair_search_ran": evidence.get("repair_search_ran"),
                "repair_search_exhaustive": evidence.get("repair_search_exhaustive"),
                "safe_candidate_count": evidence.get("safe_candidate_count"),
                "target_band_candidate_count": evidence.get("target_band_candidate_count"),
                "one_click_target_reaching_candidate_exists": evidence.get(
                    "one_click_target_reaching_candidate_exists"
                ),
                "generic_target_band_search_skipped": evidence.get("generic_target_band_search_skipped"),
                "generic_target_band_search_skipped_reason": evidence.get(
                    "generic_target_band_search_skipped_reason"
                ),
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
            "resolved_candidate_fields": {
                "candidate_id": resolved_candidate.get("candidate_id"),
                "source_candidate_id": resolved_candidate.get("source_candidate_id"),
                "updates": dict(resolved_candidate.get("updates") or {}),
                "candidate_post_util": resolved_candidate.get("candidate_post_util"),
            },
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
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
