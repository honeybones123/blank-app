"""Focused snapshot for compute post-core publication handoff.

This verifier is coverage-only. It controls the upstream core compute result,
then observes the real post-core handoff chain inside
``_compute_design_guidance_items`` without changing product routing or product
logic.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ARTIFACT_DIR = REPO / "artifacts" / "verification"
TRACE_DIR = REPO / "artifacts" / "traces"

HANDOFF_FUNCTIONS = (
    "_dedupe_guidance_items_for_display",
    "_collapse_to_single_primary_guidance_item",
    "_sanitize_guidance_items_for_executor_contract",
    "_maybe_promote_safe_local_cleanup_primary",
    "_prefer_target_band_guidance_item_order",
    "_align_guidance_items_to_candidate_search_evidence",
    "_design_guide_apply_copy_model_to_items",
    "_design_guide_apply_button_contracts_to_items",
    "_design_guide_apply_display_truth_to_items",
    "_resolve_compute_design_guidance_publication_handoff",
    "_apply_compute_design_guidance_engine_terminal_decision",
    "_restore_compute_low_bending_terminal_cleanup",
)


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
        "any_warn": False,
        "all_key_pass": False,
        "worst_util": 1.18,
        "governing_util": 1.18,
    }


def _post_core_primary_item() -> dict[str, Any]:
    updates = {"s_lig": 125.0, "lig_legs": 3}
    evidence = {
        "family": "shear",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "search_scope": "synthetic_post_core_publication_handoff",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "selected_candidate_id": "synthetic_post_core_shear_repair_candidate",
        "best_safe_candidate_id": "synthetic_post_core_shear_repair_candidate",
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
        "source_candidate_id": "synthetic_post_core_shear_repair_candidate",
        "candidate_id": "synthetic_post_core_shear_repair_candidate",
        "family": "shear",
        "updates": dict(updates),
        "preview_pass": True,
        "preview_status": "PASS",
        "expected_util": 0.92,
        "candidate_search_evidence": dict(evidence),
    }
    resolved_candidate = {
        "candidate_id": "synthetic_post_core_shear_repair_candidate",
        "source_candidate_id": "synthetic_post_core_shear_repair_candidate",
        "family": "shear",
        "updates": dict(updates),
        "candidate_post_util": 0.92,
        "candidate_search_evidence": dict(evidence),
    }
    button_contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "shear",
        "updates": dict(updates),
        "preview_pass": True,
        "expected_util": 0.92,
        "blocking_reason": None,
        "source_candidate_id": "synthetic_post_core_shear_repair_candidate",
        "candidate_id": "synthetic_post_core_shear_repair_candidate",
    }
    return {
        "id": "synthetic_post_core_publication_primary",
        "candidate_id": "synthetic_post_core_shear_repair_candidate",
        "source_candidate_id": "synthetic_post_core_shear_repair_candidate",
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
        "reasoning": "Why: synthetic post-core repair reaches the target band.",
        "status": "FAIL",
        "util": 1.18,
        "guidance_intent": "required_fix",
        "primary_card_actionable": True,
        "final_state_class": "action",
        "action_type": "apply_resolved_candidate",
        "updates": dict(updates),
        "candidate_search_evidence": dict(evidence),
        "action_payload": action_payload,
        "resolved_candidate": resolved_candidate,
        "button_contract": button_contract,
        "display_truth": {
            "display_truth_source": "candidate_preview",
            "displayed_util": 0.92,
            "displayed_status": "PASS",
            "target_low": 0.85,
            "target_high": 1.0,
            "displayed_within_target_band": True,
            "source_candidate_util": 0.92,
        },
    }


def _item_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": type(item).__name__}
    action_payload = dict(item.get("action_payload") or {})
    resolved_candidate = dict(item.get("resolved_candidate") or {})
    evidence = dict(
        item.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved_candidate.get("candidate_search_evidence")
        or {}
    )
    contract = dict(item.get("button_contract") or {})
    return {
        "id": item.get("id"),
        "candidate_id": item.get("candidate_id") or item.get("source_candidate_id"),
        "family": item.get("family") or item.get("check_key"),
        "selected_family_id": item.get("selected_family_id"),
        "published_family_id": item.get("published_family_id"),
        "cta_family_id": item.get("cta_family_id"),
        "title": item.get("title_main") or item.get("title"),
        "status": item.get("status"),
        "guidance_intent": item.get("guidance_intent"),
        "action_type": item.get("action_type") or action_payload.get("action_type"),
        "updates_hash": _stable_hash(item.get("updates") or action_payload.get("updates") or {}),
        "button_contract_hash": _stable_hash(contract),
        "button_enabled": contract.get("enabled"),
        "button_actionable": contract.get("actionable"),
        "action_payload_hash": _stable_hash(action_payload),
        "resolved_candidate_hash": _stable_hash(resolved_candidate),
        "evidence_hash": _stable_hash(evidence),
        "evidence_keys": sorted(str(k) for k in evidence.keys())[:80],
        "display_truth_hash": _stable_hash(item.get("display_truth") or {}),
        "hash": _stable_hash(item),
    }


def _items_summary(items: Any) -> dict[str, Any]:
    seq = list(items or []) if isinstance(items, (list, tuple)) else []
    primary = seq[0] if seq else {}
    return {
        "count": len(seq),
        "hash": _stable_hash(seq),
        "primary": _item_summary(primary),
    }


def _extract_items_from_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    for key in ("collapsed_guidance_items", "items", "guidance_items", "raw_items"):
        if key in kwargs:
            return kwargs.get(key)
    if args:
        return args[0]
    return []


def _extract_items_from_result(result: Any) -> Any:
    if isinstance(result, tuple) and result:
        return result[0]
    if isinstance(result, list):
        return result
    return []


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


def _wrap_handoff_functions(module: Any, observations: list[dict[str, Any]]) -> dict[str, Callable[..., Any]]:
    wrappers: dict[str, Callable[..., Any]] = {}
    for name in HANDOFF_FUNCTIONS:
        original = getattr(module, name)

        def _make_wrapper(func_name: str, func: Callable[..., Any]) -> Callable[..., Any]:
            def _wrapper(*args: Any, **kwargs: Any) -> Any:
                before_items = _extract_items_from_call(args, kwargs)
                debug_trace = kwargs.get("debug_trace")
                before_debug = dict(debug_trace) if isinstance(debug_trace, dict) else {}
                before = {
                    "function": func_name,
                    "input": _items_summary(before_items),
                    "debug_hash": _stable_hash(before_debug),
                    "debug_keys": sorted(str(k) for k in before_debug.keys())[:80],
                }
                result = func(*args, **kwargs)
                after_items = _extract_items_from_result(result)
                after_debug = dict(debug_trace) if isinstance(debug_trace, dict) else {}
                observations.append(
                    {
                        **before,
                        "output": _items_summary(after_items),
                        "debug_hash_after": _stable_hash(after_debug),
                        "debug_keys_after": sorted(str(k) for k in after_debug.keys())[:80],
                        "debug_keys_added": sorted(set(after_debug) - set(before_debug)),
                        "result_type": type(result).__name__,
                    }
                )
                return result

            return _wrapper

        wrappers[name] = _make_wrapper(name, original)
    return wrappers


def _run_scenario(module: Any, observations: list[dict[str, Any]]) -> dict[str, Any]:
    state = _base_state()
    primary = _post_core_primary_item()

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_post_core_publication_handoff",
                    "overview": _overview(),
                    "guidance_resolved_state": dict(_state or {}),
                    "selected_action_type": primary.get("action_type"),
                    "selected_action_family": primary.get("family"),
                    "selected_title": primary.get("title_main"),
                    "candidate_search_evidence": dict(primary.get("candidate_search_evidence") or {}),
                    "primary_button_contract": dict(primary.get("button_contract") or {}),
                    "primary_display_truth": dict(primary.get("display_truth") or {}),
                }
            )
        return [dict(primary)]

    replacements: dict[str, Any] = {
        "get_rerun_pure_cache": lambda *args, **kwargs: None,
        "set_rerun_pure_cache": lambda *args, **kwargs: None,
        "_design_guide_lightweight_guidance_state": lambda incoming: dict(incoming or {}),
        "_build_canonical_design_state_pack": lambda incoming: {
            **dict(incoming or {}),
            "canonical_pack_built": True,
            "canonical_pack_valid": True,
            "canonical_pack_source": "synthetic_post_core_publication_handoff_fixture",
        },
        "_canonical_pack_is_valid": lambda pack: True,
        "_design_state_coherence_check": lambda pack: {"coherence_should_block": False},
        "_resolve_compute_design_guidance_family_early_dispatch": lambda **kwargs: None,
        "_compute_design_guidance_items_core": _core,
        "_shared_state_snapshot": lambda: {},
        "_collect_design_overview": lambda *args, **kwargs: _overview(),
        "_attach_design_brain_result_boundary": lambda out, **kwargs: dict(out or {}),
    }
    replacements.update(_wrap_handoff_functions(module, observations))
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


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"compute_post_core_publication_handoff_trace_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_post_core_publication_handoff_snapshot_{stamp}.json"
    observations: list[dict[str, Any]] = []

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_POST_CORE_PUBLICATION_HANDOFF"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    try:
        output = _run_scenario(module, observations)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    trace_rows = _load_jsonl(trace_path)
    output_items = list(output.get("guidance_items") or []) if isinstance(output, dict) else []
    primary = output_items[0] if output_items and isinstance(output_items[0], dict) else {}
    debug_trace = dict(output.get("debug_trace") or {}) if isinstance(output, dict) else {}
    contract = dict(primary.get("button_contract") or {})
    action_payload = dict(primary.get("action_payload") or {})
    resolved_candidate = dict(primary.get("resolved_candidate") or {})
    evidence = dict(
        primary.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved_candidate.get("candidate_search_evidence")
        or {}
    )
    late_events = {
        event: len(_route_rows(trace_rows, event))
        for event in (
            "late_evidence_lane_enter",
            "late_evidence_missing_candidate_search_evidence_enter",
            "late_evidence_built_missing_candidate_search_evidence",
            "late_evidence_coherence_active_repair_republished",
            "late_evidence_active_under_capacity_blocker_materialized",
            "late_evidence_shear_final_threshold_blocker_materialized",
            "late_evidence_contract_rebound_applied",
            "late_evidence_lane_exit",
        )
    }
    observed_names = [row.get("function") for row in observations]
    missing_observations = [name for name in HANDOFF_FUNCTIONS if name not in observed_names]

    failures: list[str] = []
    if missing_observations:
        failures.append(f"missing_handoff_observations:{','.join(missing_observations)}")
    if len(output_items) != 1:
        failures.append(f"guidance_items_count:{len(output_items)}")
    if primary.get("family") != "shear":
        failures.append("primary_family_not_shear")
    if primary.get("selected_family_id") != "SHEAR_FAIL_GOVERNS":
        failures.append("selected_family_id_not_shear_fail_governs")
    if primary.get("published_family_id") != "SHEAR_FAIL_GOVERNS":
        failures.append("published_family_id_not_shear_fail_governs")
    if primary.get("cta_family_id") != "SHEAR_FAIL_GOVERNS":
        failures.append("cta_family_id_not_shear_fail_governs")
    if not evidence:
        failures.append("candidate_search_evidence_missing")
    if not isinstance(contract.get("enabled"), bool) or not isinstance(contract.get("actionable"), bool):
        failures.append("button_contract_state_not_materialized")
    if not any(
        row.get("function") == "_resolve_compute_design_guidance_publication_handoff"
        and row.get("debug_keys_added")
        for row in observations
    ):
        failures.append("publication_handoff_debug_mutation_not_observed")
    if not debug_trace.get("final_visible_design_guide_resolver"):
        failures.append("final_visible_resolver_debug_missing")
    if late_events.get("late_evidence_lane_enter") != 1 or late_events.get("late_evidence_lane_exit") != 1:
        failures.append("late_evidence_lane_count_unstable")
    if late_events.get("late_evidence_contract_rebound_applied"):
        failures.append("unexpected_contract_rebound")

    snapshot = {
        "schema": "compute_post_core_publication_handoff_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "trace_path": str(trace_path),
        "input_primary": _item_summary(_post_core_primary_item()),
        "selected_family_result_identity": {
            "input_selected_family_id": "SHEAR_FAIL_GOVERNS",
            "output_selected_family_id": primary.get("selected_family_id"),
            "output_published_family_id": primary.get("published_family_id"),
            "output_cta_family_id": primary.get("cta_family_id"),
            "output_family": primary.get("family") or primary.get("check_key"),
        },
        "publication_item_before_after": observations,
        "evidence_proof_fields": {
            "candidate_search_evidence_hash": _stable_hash(evidence),
            "candidate_search_evidence_keys": sorted(str(k) for k in evidence.keys())[:100],
            "selected_candidate_id": evidence.get("selected_candidate_id"),
            "best_safe_candidate_id": evidence.get("best_safe_candidate_id"),
            "target_low": evidence.get("target_low"),
            "target_high": evidence.get("target_high"),
            "safe_executor_backed_candidates_count": evidence.get("safe_executor_backed_candidates_count"),
            "target_band_candidate_count": evidence.get("target_band_candidate_count"),
        },
        "cta_button_contract_fields": {
            "hash": _stable_hash(contract),
            "enabled": contract.get("enabled"),
            "actionable": contract.get("actionable"),
            "action_type": contract.get("action_type"),
            "family": contract.get("family"),
            "updates": dict(contract.get("updates") or {}),
            "preview_pass": contract.get("preview_pass"),
            "expected_util": contract.get("expected_util"),
            "source_candidate_id": contract.get("source_candidate_id"),
            "candidate_id": contract.get("candidate_id"),
        },
        "action_update_payload_fields": {
            "action_payload_hash": _stable_hash(action_payload),
            "action_type": action_payload.get("action_type"),
            "updates": dict(action_payload.get("updates") or {}),
            "source_candidate_id": action_payload.get("source_candidate_id"),
            "candidate_id": action_payload.get("candidate_id"),
            "resolved_candidate_hash": _stable_hash(resolved_candidate),
        },
        "final_selected_item": _item_summary(primary),
        "debug_fields_written": {
            "debug_hash": _stable_hash(debug_trace),
            "debug_keys": sorted(str(k) for k in debug_trace.keys())[:160],
            "selected_title": debug_trace.get("selected_title"),
            "selected_action_type": debug_trace.get("selected_action_type"),
            "selected_action_family": debug_trace.get("selected_action_family"),
            "guidance_branch": debug_trace.get("guidance_branch"),
            "primary_button_contract_hash": _stable_hash(debug_trace.get("primary_button_contract") or {}),
            "primary_display_truth_hash": _stable_hash(debug_trace.get("primary_display_truth") or {}),
        },
        "late_evidence_helper_outputs_consumed": late_events,
        "output": {
            "guidance_items_count": len(output_items),
            "guidance_items_hash": _stable_hash(output_items),
            "debug_trace_hash": _stable_hash(debug_trace),
            "recommendation_result_hash": _stable_hash(output.get("recommendation_result") if isinstance(output, dict) else None),
            "cache_data_hash": _stable_hash(output.get("cache_data") if isinstance(output, dict) else {}),
        },
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{snapshot['status']}: {output_path}")
    print(f"trace: {trace_path}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
