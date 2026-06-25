"""Report-only trace for safe-cleanup rehydration fixture rewriting.

This verifier is intentionally not branch-pass coverage.  It recreates the
previous synthetic safe-cleanup rehydration attempt and records where earlier
compute lanes alter the item shape before the late evidence branch can run.
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


def _overview() -> dict[str, Any]:
    return {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.88, "shear": 0.74, "crack": 0.42, "deflection": 0.39},
        "any_fail": False,
        "all_key_pass": True,
        "worst_util": 0.74,
        "governing_util": 0.74,
    }


def _safe_cleanup_rehydration_item() -> dict[str, Any]:
    updates = {"s_lig": 180.0, "lig_legs": 3}
    evidence = {
        "family": "shear",
        "search_scope": "synthetic_safe_cleanup_rehydration",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "selected_candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "best_safe_candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "selected_candidate_updates": dict(updates),
        "best_safe_candidate_updates": dict(updates),
        "selected_candidate_util": 0.91,
        "best_safe_final_util": 0.91,
        "safe_candidate_count": 1,
        "safe_cleanup_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "target_band_candidate_count": 1,
        "accepted_band_candidate_count": 1,
        "executable_candidate_count": 1,
        "executable_cleanup_count": 1,
        "one_click_target_reaching_candidate_exists": True,
        "exact_blockers_by_family": {"shear": {"reason": "stale synthetic blocker"}},
        "post_click_exact_blockers_by_family": {"shear": {"reason": "stale synthetic blocker"}},
        "cleanup_evidence_by_family": {"shear": {"candidate_id": "synthetic_safe_cleanup_rehydration_candidate"}},
        "post_click_cleanup_evidence_by_family": {"shear": {"candidate_id": "synthetic_safe_cleanup_rehydration_candidate"}},
    }
    action_payload = {
        "action_type": "apply_resolved_candidate",
        "source_candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "updates": dict(updates),
        "preview_pass": True,
        "preview_status": "PASS",
        "expected_util": 0.91,
        "candidate_search_evidence": dict(evidence),
    }
    resolved_candidate = {
        "candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "source_candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "updates": dict(updates),
        "candidate_post_util": 0.91,
        "candidate_search_evidence": dict(evidence),
    }
    return {
        "id": "synthetic_safe_cleanup_rehydration",
        "candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "source_candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "title_main": "Synthetic safe cleanup rehydration",
        "title": "Synthetic safe cleanup rehydration",
        "primary_action": "Run one-click auto design",
        "secondary_action": "Apply safe shear cleanup",
        "reasoning": "Why: synthetic safe cleanup can rehydrate stale blocker evidence.",
        "status": "FAIL",
        "guidance_intent": "required_fix",
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
            "preview_pass": True,
            "expected_util": 0.91,
            "blocking_reason": None,
            "source_candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
            "candidate_id": "synthetic_safe_cleanup_rehydration_candidate",
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


def _run_rewrite_scenario(module: Any) -> dict[str, Any]:
    state = _base_state()
    primary = _safe_cleanup_rehydration_item()

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_safe_cleanup_rehydration",
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
            "canonical_pack_source": "synthetic_rewrite_fixture",
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
        "_recommendation_result_for_primary_guidance_card": lambda items, state, **kwargs: None,
        "_design_guide_terminal_state_from_render_artifacts": lambda items, debug_trace: None,
        "_derive_design_guide_terminal_state_from_current_overview": lambda debug_trace, state, items: None,
        "_design_optimisation_goal": lambda state: "balanced",
        "_design_mode_config": lambda goal: {"target_low": 0.85, "target_high": 1.0},
        "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (0.85, 1.0, "synthetic"),
        "_attach_design_brain_result_boundary": lambda out, **kwargs: dict(out or {}),
    }
    with _patched(module, replacements):
        return module._compute_design_guidance_items(
            dict(state),
            debug_enabled=True,
            request_kind="design_guide",
        )


def _probe_payloads(trace_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    for row in trace_rows:
        if row.get("event") != "compute_guidance_route":
            continue
        if row.get("route_event") != "late_evidence_rehydration_rewrite_probe":
            continue
        payload = row.get("payload")
        if isinstance(payload, dict):
            probes.append(payload)
    return probes


def _first_blocker(probes: list[dict[str, Any]]) -> dict[str, Any]:
    if not probes:
        return {"label": None, "reason": "no_rewrite_probes_recorded"}
    start = probes[0]
    start_hash = (start.get("primary") or {}).get("hash") if isinstance(start.get("primary"), dict) else None
    for probe in probes:
        label = probe.get("label")
        primary = probe.get("primary") if isinstance(probe.get("primary"), dict) else {}
        if probe.get("title_has_final_threshold") is not True:
            return {"label": label, "reason": "title_predicate_missing", "probe": probe}
        if probe.get("has_shear_update_keys") is not True:
            return {"label": label, "reason": "shear_update_predicate_missing", "probe": probe}
    changed_hash_label = None
    for probe in probes:
        primary = probe.get("primary") if isinstance(probe.get("primary"), dict) else {}
        if start_hash and primary.get("hash") != start_hash:
            changed_hash_label = probe.get("label")
            break
    return {
        "label": probes[-1].get("label"),
        "reason": "no_predicate_blocker_detected",
        "first_item_hash_change_label": changed_hash_label,
        "probe": probes[-1],
    }


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"compute_safe_cleanup_rehydration_rewrite_trace_8N_{stamp}.jsonl"
    record_path = TRACE_DIR / f"compute_safe_cleanup_rehydration_rewrite_result_8N_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_safe_cleanup_rehydration_rewrite_trace_8N_{stamp}.json"

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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_SAFE_CLEANUP_REHYDRATION_REWRITE_8N"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    os.environ["DESIGN_GUIDE_COMPUTE_LATE_EVIDENCE_SYNC_RESULT_PATH"] = str(record_path)
    try:
        output = _run_rewrite_scenario(module)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    trace_rows = _load_jsonl(trace_path)
    record_rows = _load_jsonl(record_path)
    probes = _probe_payloads(trace_rows)
    target_rows = [
        row
        for row in trace_rows
        if row.get("event") == "compute_guidance_route"
        and row.get("route_event") == "late_evidence_safe_cleanup_rehydrated"
    ]
    late_enter_rows = [
        row
        for row in trace_rows
        if row.get("event") == "compute_guidance_route"
        and row.get("route_event") == "late_evidence_lane_enter"
    ]
    first_blocker = _first_blocker(probes)
    output_items = list(output.get("guidance_items") or []) if isinstance(output, dict) else []
    primary = output_items[0] if output_items and isinstance(output_items[0], dict) else {}

    failures: list[str] = []
    if not probes:
        failures.append("rewrite_probes_missing")
    if not late_enter_rows:
        failures.append("late_evidence_lane_enter_missing")
    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "compute_safe_cleanup_rehydration_rewrite_trace.v1",
        "status": status,
        "failures": failures,
        "scenario": "safe_cleanup_rehydration_rewrite_audit",
        "trace_path": str(trace_path),
        "record_path": str(record_path),
        "target_branch_event_count": len(target_rows),
        "late_evidence_lane_enter_count": len(late_enter_rows),
        "typed_result_record_count": len(record_rows),
        "first_blocker": first_blocker,
        "timeline": [
            {
                "label": probe.get("label"),
                "primary_hash": (probe.get("primary") or {}).get("hash") if isinstance(probe.get("primary"), dict) else None,
                "primary_title": probe.get("primary_title"),
                "primary_status": probe.get("primary_status"),
                "primary_intent": probe.get("primary_intent"),
                "primary_action_type": probe.get("primary_action_type"),
                "title_has_final_threshold": probe.get("title_has_final_threshold"),
                "evidence_hash": probe.get("evidence_hash"),
                "evidence_keys": probe.get("evidence_keys"),
                "updates_hash": probe.get("updates_hash"),
                "updates_keys": probe.get("updates_keys"),
                "has_shear_update_keys": probe.get("has_shear_update_keys"),
                "button_contract_hash": probe.get("button_contract_hash"),
                "button_contract_actionable": probe.get("button_contract_actionable"),
                "button_contract_enabled": probe.get("button_contract_enabled"),
                "button_contract_preview_pass": probe.get("button_contract_preview_pass"),
                "action_payload_hash": probe.get("action_payload_hash"),
                "resolved_candidate_hash": probe.get("resolved_candidate_hash"),
                "debug_evidence_hash": probe.get("debug_evidence_hash"),
            }
            for probe in probes
        ],
        "output": {
            "guidance_items_count": len(output_items),
            "primary_hash": _stable_hash(primary),
            "primary_title": primary.get("title_main") or primary.get("title"),
            "primary_status": primary.get("status"),
            "primary_intent": primary.get("guidance_intent"),
            "primary_candidate_search_evidence_hash": _stable_hash(primary.get("candidate_search_evidence") or {}),
            "primary_action_payload_hash": _stable_hash(primary.get("action_payload") or {}),
            "primary_resolved_candidate_hash": _stable_hash(primary.get("resolved_candidate") or {}),
            "primary_button_contract_hash": _stable_hash(primary.get("button_contract") or {}),
            "debug_trace_hash": _stable_hash((output or {}).get("debug_trace") or {}),
        },
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{status}: {output_path}")
    print(f"trace: {trace_path}")
    print(f"typed-result: {record_path}")
    print(f"target-branch-count: {len(target_rows)}")
    print(f"first-blocker: {first_blocker.get('label')} {first_blocker.get('reason')}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
