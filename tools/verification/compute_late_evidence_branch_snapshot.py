"""Focused branch snapshot for compute late-evidence proof lanes.

This verifier is synthetic branch-level coverage. It forces one controlled
primary guidance item through the real ``_compute_design_guidance_items`` late
evidence lane, with upstream compute/display helpers monkeypatched so the
target branch is reached without changing product logic.
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


def _missing_evidence_item() -> dict[str, Any]:
    updates = {"b": 280.0, "D": 580.0}
    return {
        "id": "synthetic_missing_evidence_primary",
        "candidate_id": "synthetic_missing_evidence_primary",
        "source_candidate_id": "synthetic_missing_evidence_primary",
        "family": "combined",
        "check_key": "combined",
        "title_main": "Synthetic cleanup candidate missing evidence",
        "title": "Synthetic cleanup candidate missing evidence",
        "status": "ACTION",
        "guidance_intent": "efficiency_tightening",
        "primary_card_actionable": True,
        "action_type": "apply_resolved_candidate",
        "updates": dict(updates),
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": dict(updates),
            "preview_pass": True,
            "expected_util": 0.89,
            "blocking_reason": None,
            "source_candidate_id": "synthetic_missing_evidence_primary",
            "candidate_id": "synthetic_missing_evidence_primary",
        },
        "display_truth": {
            "display_truth_source": "candidate_preview",
            "displayed_util": 0.89,
            "displayed_status": "PASS",
            "target_low": 0.85,
            "target_high": 1.0,
            "displayed_within_target_band": True,
            "source_candidate_util": 0.89,
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "source_candidate_id": "synthetic_missing_evidence_primary",
            "updates": dict(updates),
        },
        "resolved_candidate": {
            "candidate_id": "synthetic_missing_evidence_primary",
            "source_candidate_id": "synthetic_missing_evidence_primary",
            "updates": dict(updates),
            "candidate_post_util": 0.89,
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


def _run_late_evidence_scenario(module: Any, *, primary: dict[str, Any], guidance_branch: str) -> dict[str, Any]:
    state = _base_state()

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": guidance_branch,
                    "overview": _overview(),
                    "guidance_resolved_state": dict(_state or {}),
                    "selected_action_type": primary.get("action_type"),
                    "selected_action_family": primary.get("family"),
                    "selected_title": primary.get("title_main"),
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
            "canonical_pack_source": "synthetic_branch_fixture",
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
        "_attach_design_brain_result_boundary": lambda out, **kwargs: dict(out or {}),
    }
    with _patched(module, replacements):
        return module._compute_design_guidance_items(
            dict(state),
            debug_enabled=True,
            request_kind="design_guide",
        )


def _scenario_config(name: str) -> dict[str, Any]:
    if name == "missing_candidate_search_evidence":
        return {
            "primary": _missing_evidence_item(),
            "guidance_branch": "synthetic_missing_candidate_search_evidence",
            "branch_event": "late_evidence_built_missing_candidate_search_evidence",
            "enter_event": "late_evidence_missing_candidate_search_evidence_enter",
            "expected_changed_fields": {"item", "action_payload", "resolved_candidate", "debug_candidate_search_evidence"},
        }
    raise ValueError(f"unknown scenario: {name}")


def main() -> int:
    import importlib

    scenario = "missing_candidate_search_evidence"
    config = _scenario_config(scenario)

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"compute_late_evidence_branch_trace_8L_{stamp}.jsonl"
    record_path = TRACE_DIR / f"compute_late_evidence_branch_result_8L_{stamp}.jsonl"

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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_LATE_MISSING_CANDIDATE_SEARCH_EVIDENCE_8L"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    os.environ["DESIGN_GUIDE_COMPUTE_LATE_EVIDENCE_SYNC_RESULT_PATH"] = str(record_path)
    try:
        output = _run_late_evidence_scenario(
            module,
            primary=dict(config["primary"]),
            guidance_branch=str(config["guidance_branch"]),
        )
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    trace_rows = _load_jsonl(trace_path)
    record_rows = _load_jsonl(record_path)
    branch_rows = [
        row
        for row in trace_rows
        if row.get("event") == "compute_guidance_route"
        and row.get("route_event") == config["branch_event"]
    ]
    branch_enter_rows: list[dict[str, Any]] = []
    if config["enter_event"]:
        branch_enter_rows = [
            row
            for row in trace_rows
            if row.get("event") == "compute_guidance_route"
            and row.get("route_event") == config["enter_event"]
        ]
    sync_rows = [
        row
        for row in record_rows
        if row.get("event") == "compute_late_evidence_sync_typed_result"
    ]

    typed = sync_rows[-1].get("typed_result") if sync_rows and isinstance(sync_rows[-1], dict) else {}
    if not isinstance(typed, dict):
        typed = {}
    parity = typed.get("parity_checks") if isinstance(typed.get("parity_checks"), dict) else {}
    output_items = list(output.get("guidance_items") or []) if isinstance(output, dict) else []
    primary = output_items[0] if output_items and isinstance(output_items[0], dict) else {}
    evidence = dict(
        primary.get("candidate_search_evidence")
        or (primary.get("action_payload") or {}).get("candidate_search_evidence")
        or (primary.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )

    failures: list[str] = []
    if config["enter_event"] and len(branch_enter_rows) != 1:
        failures.append(f"missing_evidence_enter_count:{len(branch_enter_rows)}")
    if len(branch_rows) != 1:
        failures.append(f"missing_evidence_branch_count:{len(branch_rows)}")
    if not sync_rows:
        failures.append("typed_sync_record_missing")
    if any(value is not True for value in parity.values()):
        failures.append("typed_sync_parity_failed")
    if not evidence:
        failures.append("output_candidate_search_evidence_missing")
    if not evidence.get("selected_candidate_id"):
        failures.append("selected_candidate_id_missing")
    if not set(config["expected_changed_fields"]).issubset(set(typed.get("changed_fields") or [])):
        failures.append("expected_mutation_fields_missing")

    status = "PASS" if not failures else "FAIL"
    branch_payload = branch_rows[-1].get("payload") if branch_rows else {}
    enter_payload = branch_enter_rows[-1].get("payload") if branch_enter_rows else {}
    output_path = ARTIFACT_DIR / f"compute_late_evidence_branch_snapshot_8L_{stamp}.json"
    snapshot = {
        "schema": "compute_late_evidence_branch_snapshot.v1",
        "status": status,
        "failures": failures,
        "scenario": scenario,
        "branch_event": config["branch_event"],
        "trace_path": str(trace_path),
        "record_path": str(record_path),
        "branch_enter_count": len(branch_enter_rows),
        "branch_event_count": len(branch_rows),
        "typed_sync_record_count": len(sync_rows),
        "input_probe": enter_payload,
        "branch_probe": branch_payload,
        "mutation_map": {
            "input_item_hash": ((enter_payload.get("primary") or {}).get("hash") if isinstance(enter_payload, dict) else None),
            "output_item_hash": primary.get("hash") or _stable_hash(primary),
            "candidate_search_evidence_hash": _stable_hash(evidence),
            "candidate_search_evidence_keys": sorted(str(k) for k in evidence.keys())[:80],
            "selected_candidate_id": evidence.get("selected_candidate_id"),
            "action_payload_hash_before": typed.get("action_payload_hash_before"),
            "action_payload_hash_after": typed.get("action_payload_hash_after"),
            "resolved_candidate_hash_before": typed.get("resolved_candidate_hash_before"),
            "resolved_candidate_hash_after": typed.get("resolved_candidate_hash_after"),
            "button_contract_hash_before": typed.get("button_contract_hash_before"),
            "button_contract_hash_after": typed.get("button_contract_hash_after"),
            "debug_candidate_search_evidence_hash": typed.get("debug_candidate_search_evidence_hash"),
            "changed_fields": list(typed.get("changed_fields") or []),
            "parity_checks": dict(parity),
        },
        "output": {
            "guidance_items_count": len(output_items),
            "primary_hash": _stable_hash(primary),
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
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
