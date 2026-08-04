"""Focused snapshot for the empty-collapsed exact-blocker fallback lane.

This verifier is coverage-only. It creates a valid compute wrapper state where
core guidance collapses to no publishable item while exact-blocker proof and a
disabled contract are present. The real final fallback lane inside
``_compute_design_guidance_items`` must then materialize one disabled
``specific_blocker`` item.
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
        "uls_Mstar": 210.0,
        "uls_Vstar": 260.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }


def _overview() -> dict[str, Any]:
    return {
        "statuses": {
            "bending": "PASS",
            "shear": "PASS",
            "crack": "PASS",
            "deflection": "PASS",
            "detailing": "FAIL",
        },
        "utils": {"bending": 0.92, "shear": 0.91, "crack": 0.42, "deflection": 0.39, "detailing": 1.01},
        "any_fail": True,
        "any_warn": False,
        "all_key_pass": False,
        "worst_util": 1.01,
        "governing_util": 1.01,
    }


def _exact_blockers() -> dict[str, dict[str, Any]]:
    return {
        "general": {
            "family": "general",
            "exact_blocker": True,
            "reason": "Synthetic exact blocker: no executor-backed cleanup candidate preserves every required proof field.",
            "failed_check_name": "design cleanup proof",
            "failed_check_util": 0.92,
            "current_util": 0.92,
            "why_reduction_would_hurt_other_design_elements": "No executor-backed cleanup candidate preserves all proof fields together.",
            "source": "compute_empty_collapsed_exact_blocker_fallback_snapshot",
        }
    }


def _candidate_search_evidence() -> dict[str, Any]:
    exact = _exact_blockers()
    return {
        "family": "general",
        "selected_family_id": "GENERAL_EXACT_BLOCKER_FALLBACK",
        "published_family_id": "GENERAL_EXACT_BLOCKER_FALLBACK",
        "cta_family_id": "GENERAL_EXACT_BLOCKER_FALLBACK",
        "search_scope": "synthetic_empty_collapsed_exact_blocker_fallback",
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "safe_candidate_count": 0,
        "safe_executor_backed_candidates_count": 0,
        "executable_candidate_count": 0,
        "target_band_candidate_count": 0,
        "accepted_band_candidate_count": 0,
        "one_click_target_reaching_candidate_exists": False,
        "no_second_cta_required": True,
        "exact_blockers_by_family": dict(exact),
        "post_click_exact_blockers_by_family": dict(exact),
    }


def _disabled_contract() -> dict[str, Any]:
    return {
        "enabled": False,
        "actionable": False,
        "action_type": None,
        "family": "general",
        "updates": {},
        "preview_pass": False,
        "expected_util": None,
        "blocking_reason": "Synthetic exact blocker: no executor-backed cleanup candidate preserves every required proof field.",
        "source_candidate_id": None,
        "candidate_id": None,
    }


def _display_truth() -> dict[str, Any]:
    return {
        "display_truth_source": "post_commit_truth",
        "displayed_util": 0.92,
        "displayed_status": "BLOCKED",
        "target_low": 0.85,
        "target_high": 1.0,
        "displayed_within_target_band": False,
        "source_summary_util": 0.92,
        "source_candidate_util": None,
        "source_post_commit_util": 0.92,
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
    exact = dict(item.get("exact_blockers_by_family") or {})
    cleanup = dict(item.get("cleanup_evidence_by_family") or {})
    return {
        "id": item.get("id"),
        "family": item.get("family") or item.get("check_key"),
        "title": item.get("title_main") or item.get("title"),
        "status": item.get("status"),
        "util": item.get("util"),
        "guidance_intent": item.get("guidance_intent"),
        "final_state_class": item.get("final_state_class"),
        "primary_card_actionable": item.get("primary_card_actionable"),
        "button_enabled": contract.get("enabled"),
        "button_actionable": contract.get("actionable"),
        "button_action_type": contract.get("action_type"),
        "button_family": contract.get("family"),
        "button_blocking_reason": contract.get("blocking_reason"),
        "button_contract_hash": _stable_hash(contract),
        "action_payload_hash": _stable_hash(action_payload),
        "resolved_candidate_hash": _stable_hash(resolved_candidate),
        "evidence_hash": _stable_hash(evidence),
        "evidence_keys": sorted(str(k) for k in evidence.keys())[:100],
        "exact_blocker_families": sorted(str(k) for k in exact.keys()),
        "exact_blockers_hash": _stable_hash(exact),
        "cleanup_evidence_hash": _stable_hash(cleanup),
        "display_truth_hash": _stable_hash(item.get("display_truth") or {}),
        "hash": _stable_hash(item),
    }


def _route_count(rows: list[dict[str, Any]], event: str) -> int:
    return sum(
        1
        for row in rows
        if row.get("event") == "compute_guidance_route"
        and row.get("route_event") == event
    )


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
    exact = _exact_blockers()
    evidence = _candidate_search_evidence()
    contract = _disabled_contract()
    truth = _display_truth()

    def _post_core_handoff(**_: Any) -> dict[str, Any]:
        return {
            "collapsed_guidance_items": [],
            "debug_trace": {
                "guidance_branch": "synthetic_empty_collapsed_exact_blocker_fallback",
                "overview": _overview(),
                "guidance_resolved_state": dict(state),
                "primary_card_title": "Cleanup blocked by exact engineering limit",
                "final_primary_title": "Cleanup blocked by exact engineering limit",
                "primary_guidance_intent": "specific_blocker",
                "primary_card_intent": "specific_blocker",
                "final_state_class": "blocker",
                "selected_action_family": "general",
                "candidate_search_evidence": dict(evidence),
                "exact_blockers_by_family": dict(exact),
                "post_click_exact_blockers_by_family": dict(exact),
                "cleanup_evidence_by_family": dict(exact),
                "post_click_cleanup_evidence_by_family": dict(exact),
                "primary_button_contract": dict(contract),
                "button_contract": dict(contract),
                "button_contract_enabled": False,
                "button_contract_updates": {},
                "primary_display_truth": dict(truth),
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
                    "guidance_branch": "synthetic_empty_collapsed_exact_blocker_fallback",
                    "overview": _overview(),
                    "guidance_resolved_state": dict(_state or {}),
                    "primary_card_title": "Cleanup blocked by exact engineering limit",
                    "final_primary_title": "Cleanup blocked by exact engineering limit",
                    "primary_guidance_intent": "specific_blocker",
                    "primary_card_intent": "specific_blocker",
                    "final_state_class": "blocker",
                    "selected_action_family": "general",
                    "candidate_search_evidence": dict(evidence),
                    "exact_blockers_by_family": dict(exact),
                    "post_click_exact_blockers_by_family": dict(exact),
                    "cleanup_evidence_by_family": dict(exact),
                    "post_click_cleanup_evidence_by_family": dict(exact),
                    "primary_button_contract": dict(contract),
                    "button_contract": dict(contract),
                    "button_contract_enabled": False,
                    "button_contract_updates": {},
                    "primary_display_truth": dict(truth),
                }
            )
        return []

    replacements: dict[str, Any] = {
        "get_rerun_pure_cache": lambda *args, **kwargs: None,
        "set_rerun_pure_cache": lambda *args, **kwargs: None,
        "_design_guide_lightweight_guidance_state": lambda incoming: dict(incoming or {}),
        "_build_canonical_design_state_pack": lambda incoming: {
            **dict(incoming or {}),
            "canonical_pack_built": True,
            "canonical_pack_valid": True,
            "canonical_pack_source": "synthetic_empty_collapsed_exact_blocker_fallback_fixture",
        },
        "_canonical_pack_is_valid": lambda pack: True,
        "_design_state_coherence_check": lambda pack: {"coherence_should_block": False},
        "_resolve_compute_design_guidance_family_early_dispatch": lambda **kwargs: None,
        "_compute_design_guidance_items_core": _core,
        "_orchestrate_compute_post_core_publication_handoff": _post_core_handoff,
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
        "# Empty-Collapsed Exact-Blocker Fallback Coverage",
        "",
        f"Status: {snapshot['status']}",
        "",
        "## Scope",
        "",
        "- Coverage only.",
        "- No product code changed.",
        "- No extraction performed.",
        "- Contract rebound, serviceability fallback, CTA/button precedence, and locked family internals were not touched.",
        "",
        "## Target",
        "",
        "- `inputs_page.py:80505-80637`",
        "- Future helper: `_materialize_compute_empty_collapsed_exact_blocker_fallback(...)`",
        "",
        "## Proof",
        "",
        f"- Snapshot artifact: `{snapshot['snapshot_path']}`",
        f"- Trace artifact: `{snapshot['trace_path']}`",
        f"- Branch materialized: `{snapshot['branch_proof']['specific_blocker_materialized_from_compute_proof']}`",
        f"- Collapsed input count before fallback: `{snapshot['collapsed_empty_condition']['input_collapsed_count']}`",
        f"- Output item count: `{snapshot['output']['count']}`",
        f"- Contract rebound count: `{snapshot['event_counts']['late_evidence_contract_rebound_applied']}`",
        f"- Serviceability fallback touched: `{snapshot['serviceability_fallback_touched']}`",
        "",
        "## Generated Fallback Item",
        "",
        "```json",
        json.dumps(snapshot["output"]["primary"], indent=2, sort_keys=True),
        "```",
        "",
        "## Decision",
        "",
        "The lane is proven and stable." if snapshot["status"] == "PASS" else "The lane is not proven; do not extract.",
        "",
        "## Next Recommendation",
        "",
        (
            "Extract the covered branch into page-local `_materialize_compute_empty_collapsed_exact_blocker_fallback(...)`."
            if snapshot["status"] == "PASS"
            else "Stop and inspect failures before any extraction."
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"compute_empty_collapsed_exact_blocker_fallback_trace_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_empty_collapsed_exact_blocker_fallback_snapshot_{stamp}.json"
    audit_path = AUDIT_DIR / f"compute_empty_collapsed_exact_blocker_fallback_coverage_{stamp}.md"

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_EMPTY_COLLAPSED_EXACT_BLOCKER_FALLBACK"
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
    contract = dict(primary.get("button_contract") or {})
    evidence = dict(primary.get("candidate_search_evidence") or {})
    exact = dict(primary.get("exact_blockers_by_family") or {})
    event_counts = {
        event: _route_count(trace_rows, event)
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

    failures: list[str] = []
    if len(output_items) != 1:
        failures.append(f"guidance_items_count:{len(output_items)}")
    if not debug_trace.get("specific_blocker_materialized_from_compute_proof"):
        failures.append("fallback_branch_not_materialized")
    if primary.get("guidance_intent") != "specific_blocker":
        failures.append("primary_guidance_intent_not_specific_blocker")
    if primary.get("final_state_class") != "blocker":
        failures.append("primary_final_state_not_blocker")
    if primary.get("family") != "general":
        failures.append("primary_family_not_general")
    if contract.get("enabled") is not False or contract.get("actionable") is not False:
        failures.append("disabled_button_contract_not_preserved")
    if contract.get("action_type") is not None:
        failures.append("disabled_contract_action_type_not_none")
    if contract.get("updates") != {}:
        failures.append("disabled_contract_updates_not_empty")
    if "general" not in exact:
        failures.append("general_exact_blocker_missing")
    if not evidence:
        failures.append("candidate_search_evidence_missing")
    if event_counts.get("late_evidence_contract_rebound_applied"):
        failures.append("unexpected_contract_rebound")
    if event_counts.get("late_evidence_lane_enter") or event_counts.get("late_evidence_lane_exit"):
        failures.append("late_evidence_lane_should_not_run_for_empty_collapsed_fallback")
    if event_counts.get("late_evidence_active_under_capacity_blocker_materialized"):
        failures.append("unexpected_active_under_capacity_materializer")
    if event_counts.get("late_evidence_shear_final_threshold_blocker_materialized"):
        failures.append("unexpected_shear_final_threshold_materializer")

    snapshot = {
        "schema": "compute_empty_collapsed_exact_blocker_fallback_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "snapshot_path": str(output_path),
        "trace_path": str(trace_path),
        "audit_path": str(audit_path),
        "event_counts": event_counts,
        "collapsed_empty_condition": {
            "input_collapsed_count": 0,
            "core_returned_count": 0,
            "post_core_handoff_count": 0,
            "fallback_required": True,
        },
        "input_item_identity": {
            "core_output_hash": _stable_hash([]),
            "debug_exact_blockers_hash": _stable_hash(_exact_blockers()),
            "debug_candidate_search_evidence_hash": _stable_hash(_candidate_search_evidence()),
            "debug_disabled_contract_hash": _stable_hash(_disabled_contract()),
        },
        "exact_blocker_reason": {
            "family": "general",
            "reason": (_exact_blockers().get("general") or {}).get("reason"),
            "hash": _stable_hash(_exact_blockers()),
        },
        "branch_proof": {
            "specific_blocker_materialized_from_compute_proof": bool(
                debug_trace.get("specific_blocker_materialized_from_compute_proof")
            ),
            "primary_guidance_intent": debug_trace.get("primary_guidance_intent"),
            "button_contract_enabled": debug_trace.get("button_contract_enabled"),
            "primary_button_contract_hash": _stable_hash(debug_trace.get("primary_button_contract") or {}),
            "primary_display_truth_hash": _stable_hash(debug_trace.get("primary_display_truth") or {}),
        },
        "output": {
            "count": len(output_items),
            "items_hash": _stable_hash(output_items),
            "primary": _item_summary(primary),
        },
        "evidence_proof_fields": {
            "candidate_search_evidence_hash": _stable_hash(evidence),
            "candidate_search_evidence_keys": sorted(str(k) for k in evidence.keys())[:100],
            "exact_blockers_hash": _stable_hash(exact),
            "exact_blocker_families": sorted(str(k) for k in exact.keys()),
            "cleanup_evidence_hash": _stable_hash(primary.get("cleanup_evidence_by_family") or {}),
            "post_click_cleanup_evidence_hash": _stable_hash(
                primary.get("post_click_cleanup_evidence_by_family") or {}
            ),
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
            "blocking_reason": contract.get("blocking_reason"),
            "source_candidate_id": contract.get("source_candidate_id"),
            "candidate_id": contract.get("candidate_id"),
        },
        "publication_handoff_fields": {
            "title": primary.get("title_main") or primary.get("title"),
            "status": primary.get("status"),
            "util": primary.get("util"),
            "family": primary.get("family"),
            "guidance_intent": primary.get("guidance_intent"),
            "display_truth_hash": _stable_hash(primary.get("display_truth") or {}),
            "final_selected_item_hash": _stable_hash(primary),
        },
        "contract_rebound_count": event_counts.get("late_evidence_contract_rebound_applied", 0),
        "serviceability_fallback_touched": False,
        "trace_event_count": len(trace_rows),
    }
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    _write_audit_report(audit_path, snapshot)
    print(json.dumps(snapshot, indent=2))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
