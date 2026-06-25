"""Report-only reachability check for compute serviceability blocker materialization.

The target branch currently sits after the active-under-capacity blocker lane.
This verifier attempts crack and deflection serviceability shapes through the
real late-evidence lane and records whether valid compute flow reaches the
serviceability materializer or is preempted by an earlier blocker lane.
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
        "uls_Vstar": 60.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }


def _overview(check_key: str) -> dict[str, Any]:
    statuses = {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"}
    statuses[check_key] = "FAIL"
    packs = {
        check_key: {
            "rows": [
                {
                    "title": f"{check_key} limit",
                    "status": "FAIL",
                    "calculated": f"{check_key} demand",
                    "requirement": f"{check_key} limit",
                }
            ]
        }
    }
    return {
        "statuses": statuses,
        "utils": {"bending": 0.82, "shear": 0.74, "crack": 1.18 if check_key == "crack" else 0.42, "deflection": 1.14 if check_key == "deflection" else 0.39},
        "packs": packs,
        "any_fail": True,
        "all_key_pass": False,
        "worst_util": 1.18 if check_key == "crack" else 1.14,
        "governing_util": 1.18 if check_key == "crack" else 1.14,
    }


def _serviceability_item(check_key: str) -> dict[str, Any]:
    evidence = {
        "family": check_key,
        "search_scope": f"synthetic_{check_key}_serviceability_probe",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "selected_candidate_id": f"synthetic_{check_key}_blocked_candidate",
        "failed_candidate_reasons": [f"synthetic {check_key} serviceability repair remains blocked"],
        "active_failures": [check_key],
        "safe_candidate_count": 0,
    }
    return {
        "id": f"synthetic_{check_key}_serviceability_primary",
        "candidate_id": f"synthetic_{check_key}_blocked_candidate",
        "source_candidate_id": f"synthetic_{check_key}_blocked_candidate",
        "family": check_key,
        "check_key": check_key,
        "title_main": f"Serviceability limit remains outside checked range",
        "title": f"Serviceability limit remains outside checked range",
        "primary_action": f"No one-click {check_key} serviceability repair is available",
        "secondary_action": "Try a different section or loading strategy",
        "reasoning": f"Why: synthetic {check_key} serviceability search exhausted the practical lane.",
        "status": "FAIL",
        "guidance_intent": "specific_blocker",
        "primary_card_actionable": False,
        "action_type": None,
        "updates": {},
        "candidate_search_evidence": dict(evidence),
        "action_payload": {
            "action_type": None,
            "source_candidate_id": f"synthetic_{check_key}_blocked_candidate",
            "updates": {},
            "candidate_search_evidence": dict(evidence),
        },
        "resolved_candidate": {
            "candidate_id": f"synthetic_{check_key}_blocked_candidate",
            "source_candidate_id": f"synthetic_{check_key}_blocked_candidate",
            "updates": {},
            "candidate_search_evidence": dict(evidence),
        },
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": check_key,
            "updates": {},
            "preview_pass": False,
            "expected_util": None,
            "blocking_reason": f"synthetic {check_key} serviceability repair remains blocked",
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


def _run_scenario(module: Any, *, check_key: str) -> dict[str, Any]:
    state = _base_state()
    primary = _serviceability_item(check_key)
    overview = _overview(check_key)

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": f"synthetic_{check_key}_serviceability_blocker_probe",
                    "overview": dict(overview),
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
            "canonical_pack_source": "synthetic_serviceability_blocker_fixture",
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
        "_collect_design_overview": lambda *args, **kwargs: dict(overview),
        "_overview_active_failure_keys": lambda overview_payload: {check_key},
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


def _run_probe(module: Any, *, check_key: str, stamp: str) -> dict[str, Any]:
    trace_path = TRACE_DIR / f"compute_serviceability_blocker_{check_key}_trace_{stamp}.jsonl"
    record_path = TRACE_DIR / f"compute_serviceability_blocker_{check_key}_result_{stamp}.jsonl"
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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"COMPUTE_SERVICEABILITY_BLOCKER_{check_key.upper()}"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    os.environ["DESIGN_GUIDE_COMPUTE_LATE_EVIDENCE_SYNC_RESULT_PATH"] = str(record_path)
    try:
        output = _run_scenario(module, check_key=check_key)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    trace_rows = _load_jsonl(trace_path)
    record_rows = _load_jsonl(record_path)
    active_rows = _route_rows(trace_rows, "late_evidence_active_under_capacity_blocker_materialized")
    serviceability_rows = [
        row
        for row in trace_rows
        if row.get("event") == "compute_guidance_route"
        and str(row.get("route_event") or "").startswith("late_evidence_serviceability")
    ]
    typed_rows = _typed_results(record_rows)
    output_items = list(output.get("guidance_items") or []) if isinstance(output, dict) else []
    primary = output_items[0] if output_items and isinstance(output_items[0], dict) else {}
    evidence = dict(
        primary.get("candidate_search_evidence")
        or (primary.get("action_payload") or {}).get("candidate_search_evidence")
        or (primary.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    contract = dict(primary.get("button_contract") or {})
    return {
        "check_key": check_key,
        "trace_path": str(trace_path),
        "record_path": str(record_path),
        "active_under_capacity_event_count": len(active_rows),
        "serviceability_event_count": len(serviceability_rows),
        "typed_sync_record_count": len(typed_rows),
        "preempted_by_active_under_capacity": bool(active_rows) and not bool(serviceability_rows),
        "output_hashes": {
            "primary": _stable_hash(primary),
            "evidence": _stable_hash(evidence),
            "action_payload": _stable_hash(primary.get("action_payload") or {}),
            "resolved_candidate": _stable_hash(primary.get("resolved_candidate") or {}),
            "button_contract": _stable_hash(contract),
        },
        "output_fields": {
            "family": primary.get("family"),
            "check_key": primary.get("check_key"),
            "title": primary.get("title"),
            "title_main": primary.get("title_main"),
            "status": primary.get("status"),
            "action_type": primary.get("action_type"),
            "primary_card_actionable": primary.get("primary_card_actionable"),
            "button_contract_enabled": contract.get("enabled"),
            "button_contract_actionable": contract.get("actionable"),
            "button_contract_reason": contract.get("blocking_reason"),
            "active_under_capacity_blocker": evidence.get("active_under_capacity_blocker"),
            "active_under_capacity_blocker_family": evidence.get("active_under_capacity_blocker_family"),
            "active_under_capacity_blocker_reason": evidence.get("active_under_capacity_blocker_reason"),
        },
        "evidence_keys": sorted(str(k) for k in evidence.keys())[:90],
    }


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    probes = [_run_probe(module, check_key=check_key, stamp=stamp) for check_key in ("crack", "deflection")]
    reached = [probe for probe in probes if probe["serviceability_event_count"]]
    preempted = [probe for probe in probes if probe["preempted_by_active_under_capacity"]]
    status = "NOT_PROVEN" if not reached and preempted else "PASS" if reached else "FAIL"
    failures: list[str] = []
    if status == "FAIL":
        failures.append("serviceability_branch_not_reached_and_preemption_not_proven")
    output_path = ARTIFACT_DIR / f"compute_serviceability_blocker_snapshot_{stamp}.json"
    snapshot = {
        "schema": "compute_serviceability_blocker_snapshot.v1",
        "status": status,
        "failures": failures,
        "target_branch": "serviceability crack/deflection blocker materialization",
        "target_lines": "inputs_page.py:80005-80099",
        "decision": (
            "not_proven_preempted_by_active_under_capacity"
            if status == "NOT_PROVEN"
            else "proven"
            if status == "PASS"
            else "failed"
        ),
        "probes": probes,
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{status}: {output_path}")
    for probe in probes:
        print(
            f"{probe['check_key']}: serviceability={probe['serviceability_event_count']} "
            f"active_under_capacity={probe['active_under_capacity_event_count']} "
            f"trace={probe['trace_path']}"
        )
    for failure in failures:
        print(f"- {failure}")
    return 0 if status in {"PASS", "NOT_PROVEN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
