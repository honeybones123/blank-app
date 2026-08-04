"""Focused snapshot for late-evidence contract rebound source precedence.

This verifier is coverage-only. It builds a coherent compute wrapper state where
the late evidence lane sees non-empty evidence updates and a disabled primary
button contract. The real contract rebound lane inside
``_compute_design_guidance_items`` must then rebuild an enabled contract and
emit ``late_evidence_contract_rebound_applied``.
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
AUDIT_DIR = REPO / "artifacts" / "audits"

BRANCH_EVENT = "late_evidence_contract_rebound_applied"


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


def _route_rows(rows: list[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("event") == "compute_guidance_route"
        and row.get("route_event") == event
    ]


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 600.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 210.0,
        "uls_Vstar": 260.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 220,
    }


def _rebound_updates() -> dict[str, Any]:
    return {"s_lig": 150}


def _overview() -> dict[str, Any]:
    return {
        "statuses": {
            "bending": "PASS",
            "shear": "PASS",
            "crack": "PASS",
            "deflection": "PASS",
            "detailing": "PASS",
        },
        "utils": {
            "bending": 0.91,
            "shear": 0.88,
            "crack": 0.42,
            "deflection": 0.39,
            "detailing": 0.72,
        },
        "any_fail": False,
        "any_warn": False,
        "all_key_pass": True,
        "worst_util": 0.91,
        "governing_util": 0.91,
    }


def _candidate_search_evidence() -> dict[str, Any]:
    updates = _rebound_updates()
    return {
        "family": "shear",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "cta_family_id": "SHEAR_FAIL_GOVERNS",
        "primary_action_family": "shear",
        "search_scope": "synthetic_late_contract_rebound_source_precedence",
        "candidate_search_exhaustive": True,
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "safe_candidate_count": 1,
        "safe_cleanup_count": 1,
        "executable_candidate_count": 1,
        "executable_cleanup_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "accepted_band_candidate_count": 1,
        "target_band_candidate_count": 0,
        "executable_target_band_candidate_count": 0,
        "one_click_target_reaching_candidate_exists": True,
        "selected_candidate_id": "synthetic_shear_contract_rebound_candidate",
        "best_safe_candidate_id": "synthetic_shear_contract_rebound_candidate",
        "closest_safe_candidate_id": "synthetic_shear_contract_rebound_candidate",
        "selected_candidate_updates": dict(updates),
        "best_safe_candidate_updates": dict(updates),
        "closest_safe_candidate_updates": dict(updates),
        "selected_candidate_util": 0.88,
        "best_safe_final_util": 0.88,
        "closest_safe_candidate_util": 0.88,
        "active_under_capacity_blocker": False,
        "no_second_cta_required": False,
    }


def _disabled_contract() -> dict[str, Any]:
    return {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": "shear",
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": "Synthetic disabled contract before late-evidence rebound.",
        "source_candidate_id": None,
        "candidate_id": None,
    }


def _item(evidence: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "synthetic_contract_rebound_primary",
        "family": "shear",
        "check_key": "shear",
        "title_main": "Shear cleanup - late contract rebound source precedence",
        "title": "Shear cleanup - late contract rebound source precedence",
        "status": "WARN",
        "util": 0.91,
        "expected_util": 0.91,
        "candidate_post_util": 0.91,
        "guidance_intent": "efficiency_tightening",
        "final_state_class": "cleanup",
        "primary_card_actionable": False,
        "candidate_search_evidence": dict(evidence),
        "button_contract": dict(contract),
        "display_truth": {
            "display_truth_source": "published_summary",
            "displayed_util": 0.91,
            "displayed_status": "WARN",
            "target_low": 0.85,
            "target_high": 1.0,
            "displayed_within_target_band": True,
            "source_summary_util": 0.91,
            "source_candidate_util": None,
            "source_post_commit_util": None,
        },
        "resolved_candidate": {
            "candidate_id": "synthetic_shear_contract_rebound_candidate",
            "source_candidate_id": "synthetic_shear_contract_rebound_candidate",
            "family": "shear",
            "updates": dict(_rebound_updates()),
            "candidate_post_util": 0.88,
            "candidate_search_evidence": dict(evidence),
        },
        "action_payload": {
            "candidate_id": "synthetic_shear_contract_rebound_candidate",
            "source_candidate_id": "synthetic_shear_contract_rebound_candidate",
            "candidate_search_evidence": dict(evidence),
        },
    }


def _item_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"type": type(item).__name__}
    contract = dict(item.get("button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    resolved_candidate = dict(item.get("resolved_candidate") or {})
    evidence = dict(
        item.get("candidate_search_evidence")
        or action_payload.get("candidate_search_evidence")
        or resolved_candidate.get("candidate_search_evidence")
        or {}
    )
    return {
        "id": item.get("id"),
        "family": item.get("family") or item.get("check_key"),
        "title": item.get("title_main") or item.get("title"),
        "status": item.get("status"),
        "guidance_intent": item.get("guidance_intent"),
        "final_state_class": item.get("final_state_class"),
        "primary_card_actionable": item.get("primary_card_actionable"),
        "button_enabled": contract.get("enabled"),
        "button_actionable": contract.get("actionable"),
        "button_action_type": contract.get("action_type"),
        "button_family": contract.get("family"),
        "button_updates": dict(contract.get("updates") or {}),
        "button_preview_pass": contract.get("preview_pass"),
        "button_blocking_reason": contract.get("blocking_reason"),
        "button_contract_hash": _stable_hash(contract),
        "action_payload_hash": _stable_hash(action_payload),
        "resolved_candidate_hash": _stable_hash(resolved_candidate),
        "evidence_hash": _stable_hash(evidence),
        "evidence_keys": sorted(str(k) for k in evidence.keys())[:100],
        "hash": _stable_hash(item),
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
    evidence = _candidate_search_evidence()
    contract = _disabled_contract()
    primary = _item(evidence, contract)

    def _post_core_handoff(**_: Any) -> dict[str, Any]:
        return {
            "collapsed_guidance_items": [dict(primary)],
            "debug_trace": {
                "guidance_branch": "synthetic_late_contract_rebound_source_precedence",
                "overview": _overview(),
                "guidance_resolved_state": dict(state),
                "primary_card_title": primary["title_main"],
                "final_primary_title": primary["title_main"],
                "primary_guidance_intent": primary["guidance_intent"],
                "primary_card_intent": primary["guidance_intent"],
                "final_state_class": primary["final_state_class"],
                "selected_action_family": "shear",
                "candidate_search_evidence": dict(evidence),
                "primary_button_contract": dict(contract),
                "button_contract": dict(contract),
                "button_contract_enabled": False,
                "button_contract_updates": {},
                "primary_display_truth": dict(primary.get("display_truth") or {}),
            },
            "disp": dict(state),
            "recommendation_result": None,
            "terminal_state": None,
            "terminal_state_source": "none",
        }

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_late_contract_rebound_source_precedence",
                    "overview": _overview(),
                    "guidance_resolved_state": dict(_state or {}),
                    "candidate_search_evidence": dict(evidence),
                    "primary_button_contract": dict(contract),
                    "button_contract": dict(contract),
                    "button_contract_enabled": False,
                    "button_contract_updates": {},
                }
            )
        return [dict(primary)]

    def _evaluate_candidate(_state: dict, *, updates: dict | None = None, **_: Any) -> dict[str, Any]:
        return {
            "candidate_id": "synthetic_shear_contract_rebound_candidate",
            "source_candidate_id": "synthetic_shear_contract_rebound_candidate",
            "updates": dict(updates or {}),
            "candidate_post_util": 0.88,
            "worst_util": 0.88,
            "overview": _overview(),
        }

    replacements: dict[str, Any] = {
        "get_rerun_pure_cache": lambda *args, **kwargs: None,
        "set_rerun_pure_cache": lambda *args, **kwargs: None,
        "_design_guide_lightweight_guidance_state": lambda incoming: dict(incoming or {}),
        "_build_canonical_design_state_pack": lambda incoming: {
            **dict(incoming or {}),
            "canonical_pack_built": True,
            "canonical_pack_valid": True,
            "canonical_pack_source": "synthetic_late_contract_rebound_source_precedence_fixture",
        },
        "_canonical_pack_is_valid": lambda pack: True,
        "_design_state_coherence_check": lambda pack: {"coherence_should_block": False},
        "_resolve_compute_design_guidance_family_early_dispatch": lambda **kwargs: None,
        "_compute_design_guidance_items_core": _core,
        "_orchestrate_compute_post_core_publication_handoff": _post_core_handoff,
        "_evaluate_auto_design_candidate": _evaluate_candidate,
        "_ensure_design_guide_debug_trace_coherent": lambda *, state, guidance_items, debug_trace: (
            dict(debug_trace or {}),
            [],
        ),
        "_dedupe_guidance_items_for_display": lambda items, state: (list(items or []), {}),
        "_shared_state_snapshot": lambda: {},
        "_collect_design_overview": lambda *args, **kwargs: _overview(),
        "_attach_design_brain_result_boundary": lambda out, **kwargs: dict(out or {}),
    }
    with _patched(module, replacements):
        return module._compute_design_guidance_items(
            dict(state),
            debug_enabled=True,
            request_kind="design_guide",
        )


def _write_audit_report(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Contract Rebound Source-Precedence Coverage",
        "",
        f"Status: {snapshot['status']}",
        "",
        "## Scope",
        "",
        "- Coverage only.",
        "- No product code changed.",
        "- No extraction performed.",
        "- Serviceability fallback, CTA/button precedence outside this snapshot, and locked family internals were not touched.",
        "",
        "## Target",
        "",
        "- Late-evidence contract rebound lane inside `_compute_design_guidance_items(...)`.",
        "- Event: `late_evidence_contract_rebound_applied`.",
        "",
        "## Artifacts",
        "",
        f"- Snapshot artifact: `{snapshot['snapshot_path']}`",
        f"- Trace artifact: `{snapshot['trace_path']}`",
        "",
        "## Predicate Proof",
        "",
        "```json",
        json.dumps(snapshot["predicate_proof"], indent=2, sort_keys=True),
        "```",
        "",
        "## Before / After",
        "",
        "```json",
        json.dumps(snapshot["before_after"], indent=2, sort_keys=True),
        "```",
        "",
        "## Decision",
        "",
        (
            "The lane is proven with a focused synthetic compute fixture and is safe to extract page-local next."
            if snapshot["status"] == "PASS"
            else "The lane is not proven; do not extract."
        ),
        "",
        "## Next Recommendation",
        "",
        (
            "Extract only the covered rebound application into page-local `_apply_compute_late_evidence_contract_rebound(...)`."
            if snapshot["status"] == "PASS"
            else "Stop and inspect failures before any extraction."
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page_app_contract_bridge")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"compute_late_contract_rebound_source_precedence_trace_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_late_contract_rebound_source_precedence_snapshot_{stamp}.json"
    audit_path = AUDIT_DIR / f"compute_late_contract_rebound_source_precedence_{stamp}.md"

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_LATE_CONTRACT_REBOUND_SOURCE_PRECEDENCE"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    try:
        output = _run_scenario(module)
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
    final_contract = dict(primary.get("button_contract") or {})
    final_evidence = dict(primary.get("candidate_search_evidence") or {})
    initial_evidence = _candidate_search_evidence()
    initial_contract = _disabled_contract()
    late_updates = dict(
        initial_evidence.get("selected_candidate_updates")
        or initial_evidence.get("best_safe_candidate_updates")
        or {}
    )
    rebound_rows = _route_rows(trace_rows, BRANCH_EVENT)
    late_enter_rows = _route_rows(trace_rows, "late_evidence_lane_enter")
    late_exit_rows = _route_rows(trace_rows, "late_evidence_lane_exit")
    active_rows = _route_rows(trace_rows, "late_evidence_active_under_capacity_blocker_materialized")
    threshold_rows = _route_rows(trace_rows, "late_evidence_shear_final_threshold_blocker_materialized")
    coherence_rows = _route_rows(trace_rows, "late_evidence_coherence_active_repair_republished")
    missing_rows = _route_rows(trace_rows, "late_evidence_built_missing_candidate_search_evidence")
    serviceability_touched = bool(final_evidence.get("search_scope", "").startswith("serviceability_"))

    disabled_to_enabled = (
        initial_contract.get("enabled") is False
        and final_contract.get("enabled") is True
        and final_contract.get("actionable") is True
    )
    combined_mismatch_condition = bool(
        str(initial_evidence.get("family") or "").strip().lower() == "combined"
        and dict(late_updates) != dict(initial_contract.get("updates") or {})
    )
    pending_source = dict(debug_trace.get("pending_recommendation") or {})
    selected_debug = {
        "selected_action_type": debug_trace.get("selected_action_type"),
        "selected_action_family": debug_trace.get("selected_action_family"),
        "selected_action_updates": dict(debug_trace.get("selected_action_updates") or {}),
        "button_contract_enabled": debug_trace.get("button_contract_enabled"),
        "button_contract_updates": dict(debug_trace.get("button_contract_updates") or {}),
        "late_evidence_cleanup_contract_rebound_attempted": bool(
            debug_trace.get("late_evidence_cleanup_contract_rebound_attempted")
        ),
        "late_evidence_cleanup_contract_rebound": bool(
            debug_trace.get("late_evidence_cleanup_contract_rebound")
        ),
        "late_evidence_cleanup_contract_rebound_updates": dict(
            debug_trace.get("late_evidence_cleanup_contract_rebound_updates") or {}
        ),
    }

    failures: list[str] = []
    if len(output_items) != 1:
        failures.append(f"guidance_items_count:{len(output_items)}")
    if len(rebound_rows) != 1:
        failures.append(f"rebound_event_count:{len(rebound_rows)}")
    if len(late_enter_rows) != 1 or len(late_exit_rows) != 1:
        failures.append(f"late_evidence_enter_exit_count:{len(late_enter_rows)}:{len(late_exit_rows)}")
    if not selected_debug["late_evidence_cleanup_contract_rebound_attempted"]:
        failures.append("rebound_not_attempted")
    if not selected_debug["late_evidence_cleanup_contract_rebound"]:
        failures.append("rebound_not_marked_in_debug")
    if not disabled_to_enabled:
        failures.append("disabled_to_enabled_rebound_not_proven")
    if final_contract.get("action_type") != "apply_resolved_candidate":
        failures.append("final_action_type_not_apply_resolved_candidate")
    if final_contract.get("family") != "shear":
        failures.append(f"final_contract_family:{final_contract.get('family')}")
    if dict(final_contract.get("updates") or {}) != _rebound_updates():
        failures.append("final_contract_updates_drift")
    if dict(debug_trace.get("selected_action_updates") or {}) != _rebound_updates():
        failures.append("selected_action_updates_drift")
    if debug_trace.get("selected_action_type") != "apply_resolved_candidate":
        failures.append("selected_action_type_drift")
    if active_rows:
        failures.append(f"unexpected_active_under_capacity_count:{len(active_rows)}")
    if threshold_rows:
        failures.append(f"unexpected_shear_threshold_count:{len(threshold_rows)}")
    if coherence_rows:
        failures.append(f"unexpected_coherence_republish_count:{len(coherence_rows)}")
    if missing_rows:
        failures.append(f"unexpected_missing_evidence_count:{len(missing_rows)}")
    if serviceability_touched:
        failures.append("serviceability_fallback_touched")

    snapshot = {
        "schema": "compute_late_contract_rebound_source_precedence_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "snapshot_path": str(output_path),
        "trace_path": str(trace_path),
        "audit_path": str(audit_path),
        "event_counts": {
            "late_evidence_lane_enter": len(late_enter_rows),
            "late_evidence_contract_rebound_applied": len(rebound_rows),
            "late_evidence_lane_exit": len(late_exit_rows),
            "late_evidence_built_missing_candidate_search_evidence": len(missing_rows),
            "late_evidence_coherence_active_repair_republished": len(coherence_rows),
            "late_evidence_active_under_capacity_blocker_materialized": len(active_rows),
            "late_evidence_shear_final_threshold_blocker_materialized": len(threshold_rows),
        },
        "predicate_proof": {
            "_late_updates": dict(late_updates),
            "_late_updates_hash": _stable_hash(late_updates),
            "_late_contract": dict(initial_contract),
            "_late_contract_hash": _stable_hash(initial_contract),
            "disabled_to_enabled_rebound_decision": disabled_to_enabled,
            "combined_mismatch_condition": combined_mismatch_condition,
            "active_under_capacity_blocker": bool(initial_evidence.get("active_under_capacity_blocker")),
            "pending_recommendation_source": pending_source,
            "pending_recommendation_hash": _stable_hash(pending_source),
        },
        "before_after": {
            "primary_before": _item_summary(_item(initial_evidence, initial_contract)),
            "primary_after": _item_summary(primary),
            "button_contract_before": dict(initial_contract),
            "button_contract_after": dict(final_contract),
            "button_contract_before_hash": _stable_hash(initial_contract),
            "button_contract_after_hash": _stable_hash(final_contract),
            "primary_before_hash": _stable_hash(_item(initial_evidence, initial_contract)),
            "primary_after_hash": _stable_hash(primary),
            "existing_evidence_before_hash": _stable_hash(initial_evidence),
            "existing_evidence_after_hash": _stable_hash(final_evidence),
        },
        "selected_action_debug_fields": selected_debug,
        "publication_handoff_fields": {
            "final_selected_item_identity_hash": _stable_hash(primary),
            "final_selected_item_id": primary.get("id"),
            "final_selected_item_family": primary.get("family") or primary.get("check_key"),
            "final_selected_item_title": primary.get("title_main") or primary.get("title"),
            "final_selected_item_status": primary.get("status"),
            "final_selected_item_guidance_intent": primary.get("guidance_intent"),
            "final_contract_hash": _stable_hash(final_contract),
            "final_evidence_hash": _stable_hash(final_evidence),
            "action_payload_hash": _stable_hash(primary.get("action_payload") or {}),
            "resolved_candidate_hash": _stable_hash(primary.get("resolved_candidate") or {}),
        },
        "trace_event_count": len(trace_rows),
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_audit_report(audit_path, snapshot)
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
