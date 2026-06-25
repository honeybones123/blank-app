"""Focused snapshot for the post-core low-bending terminal resolution patch.

This verifier is coverage-only. It forces a valid post-core state where all
required checks pass but bending utilisation is below the final accepted floor,
then observes the real ``_compute_design_guidance_items`` wrapper lane that
suppresses the core output and publishes a low-bending terminal item.
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
        "uls_Mstar": 35.0,
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
        "utils": {"bending": 0.82, "shear": 0.91, "crack": 0.42, "deflection": 0.39},
        "any_fail": False,
        "any_warn": False,
        "all_key_pass": True,
        "worst_util": 0.91,
        "governing_util": 0.91,
        "actions_used": {},
        "packs": {},
    }


def _core_item() -> dict[str, Any]:
    return {
        "id": "synthetic_core_green_low_bending_input",
        "candidate_id": "synthetic_core_green_low_bending_input",
        "source_candidate_id": "synthetic_core_green_low_bending_input",
        "family": "general",
        "check_key": "general",
        "title_main": "Synthetic core pass before low-bending patch",
        "title": "Synthetic core pass before low-bending patch",
        "status": "PASS",
        "util": 0.91,
        "guidance_intent": "already_efficient",
        "primary_card_actionable": False,
        "action_type": None,
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": "general",
            "updates": {},
            "preview_pass": False,
            "expected_util": None,
            "blocking_reason": None,
            "source_candidate_id": None,
            "candidate_id": None,
        },
    }


def _low_bending_item() -> dict[str, Any]:
    updates = {"bot1_count": 3, "db_bot_1": 16}
    evidence = {
        "family": "bending",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "published_family_id": "BENDING_FAIL_GOVERNS",
        "cta_family_id": "BENDING_FAIL_GOVERNS",
        "search_scope": "synthetic_post_core_low_bending_terminal_resolution",
        "target_low": 0.85,
        "target_high": 1.0,
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "selected_candidate_id": "synthetic_low_bending_terminal_candidate",
        "best_safe_candidate_id": "synthetic_low_bending_terminal_candidate",
        "selected_candidate_updates": dict(updates),
        "best_safe_candidate_updates": dict(updates),
        "selected_candidate_util": 0.88,
        "best_safe_final_util": 0.88,
        "safe_candidate_count": 1,
        "safe_executor_backed_candidates_count": 1,
        "target_band_candidate_count": 1,
        "accepted_band_candidate_count": 1,
        "one_click_target_reaching_candidate_exists": True,
    }
    contract = {
        "enabled": True,
        "actionable": True,
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": dict(updates),
        "preview_pass": True,
        "expected_util": 0.88,
        "blocking_reason": None,
        "source_candidate_id": "synthetic_low_bending_terminal_candidate",
        "candidate_id": "synthetic_low_bending_terminal_candidate",
    }
    action_payload = {
        "action_type": "apply_resolved_candidate",
        "source_candidate_id": "synthetic_low_bending_terminal_candidate",
        "candidate_id": "synthetic_low_bending_terminal_candidate",
        "family": "bending",
        "updates": dict(updates),
        "preview_pass": True,
        "expected_util": 0.88,
        "candidate_search_evidence": dict(evidence),
    }
    return {
        "id": "synthetic_low_bending_terminal_resolution",
        "candidate_id": "synthetic_low_bending_terminal_candidate",
        "source_candidate_id": "synthetic_low_bending_terminal_candidate",
        "family": "bending",
        "check_key": "bending",
        "selected_action_family": "bending",
        "selected_family": "BENDING_FAIL_GOVERNS",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "published_family_id": "BENDING_FAIL_GOVERNS",
        "cta_family_id": "BENDING_FAIL_GOVERNS",
        "title_main": "Bending below final accepted threshold",
        "title": "Bending below final accepted threshold",
        "primary_action": "Apply bending cleanup",
        "secondary_action": "Review bending utilisation",
        "reasoning": "Why: bending remains below the final accepted threshold.",
        "status": "WARN",
        "util": 0.82,
        "guidance_intent": "efficiency_tightening",
        "primary_card_actionable": True,
        "final_state_class": "action",
        "action_type": "apply_resolved_candidate",
        "updates": dict(updates),
        "candidate_search_evidence": dict(evidence),
        "action_payload": dict(action_payload),
        "resolved_candidate": {
            "candidate_id": "synthetic_low_bending_terminal_candidate",
            "source_candidate_id": "synthetic_low_bending_terminal_candidate",
            "family": "bending",
            "updates": dict(updates),
            "candidate_post_util": 0.88,
            "candidate_search_evidence": dict(evidence),
        },
        "button_contract": dict(contract),
        "display_truth": {
            "display_truth_source": "candidate_preview",
            "displayed_util": 0.88,
            "displayed_status": "PASS",
            "target_low": 0.85,
            "target_high": 1.0,
            "displayed_within_target_band": True,
            "source_candidate_util": 0.88,
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


def _run_scenario(module: Any, observations: list[dict[str, Any]]) -> dict[str, Any]:
    state = _base_state()
    core_primary = _core_item()

    def _core(_state: dict, *, debug_sink: dict | None = None, **_: Any) -> list[dict[str, Any]]:
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_core_green_low_bending",
                    "overview": _overview(),
                    "guidance_resolved_state": dict(_state or {}),
                    "selected_action_type": core_primary.get("action_type"),
                    "selected_action_family": core_primary.get("family"),
                    "selected_title": core_primary.get("title_main"),
                }
            )
        return [dict(core_primary)]

    def _post_click_low_bending_resolution_item(*args: Any, **kwargs: Any) -> dict[str, Any]:
        item = _low_bending_item()
        debug_sink = kwargs.get("debug_sink")
        if isinstance(debug_sink, dict):
            debug_sink.update(
                {
                    "guidance_branch": "synthetic_low_bending_terminal_resolution",
                    "selected_action_type": item.get("action_type"),
                    "selected_title": item.get("title_main"),
                    "selected_action_family": item.get("family"),
                }
            )
        observations.append(
            {
                "function": "_post_click_low_bending_resolution_item",
                "output": _item_summary(item),
                "debug_keys": sorted(str(k) for k in (debug_sink or {}).keys())[:80]
                if isinstance(debug_sink, dict)
                else [],
            }
        )
        return dict(item)

    def _bending_only_target_band_cleanup_item(*args: Any, **kwargs: Any) -> None:
        observations.append(
            {
                "function": "_bending_only_target_band_cleanup_item",
                "output": None,
            }
        )
        return None

    original_button_contract = module._design_guide_button_contract

    def _design_guide_button_contract(item: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        if isinstance(item, dict) and item.get("id") == "synthetic_low_bending_terminal_resolution":
            contract = dict(item.get("button_contract") or {})
            observations.append(
                {
                    "function": "_design_guide_button_contract",
                    "input": _item_summary(item),
                    "output_hash": _stable_hash(contract),
                    "enabled": contract.get("enabled"),
                    "actionable": contract.get("actionable"),
                }
            )
            return contract
        return original_button_contract(item, *args, **kwargs)

    def _orchestrate_compute_post_core_publication_handoff(
        *,
        state: dict,
        state_coherence: dict,
        canonical_state: dict,
        guidance_items: list[dict[str, Any]],
        debug_trace: dict,
        request_kind_norm: str,
    ) -> dict[str, Any]:
        observations.append(
            {
                "function": "_orchestrate_compute_post_core_publication_handoff",
                "input": [_item_summary(item) for item in list(guidance_items or [])],
                "debug_hash": _stable_hash(debug_trace or {}),
                "request_kind_norm": request_kind_norm,
            }
        )
        return {
            "collapsed_guidance_items": list(guidance_items or []),
            "debug_trace": dict(debug_trace or {}),
            "disp": dict(state or {}),
            "recommendation_result": None,
            "terminal_state": None,
            "terminal_state_source": None,
        }

    replacements: dict[str, Any] = {
        "get_rerun_pure_cache": lambda *args, **kwargs: None,
        "set_rerun_pure_cache": lambda *args, **kwargs: None,
        "_design_guide_lightweight_guidance_state": lambda incoming: dict(incoming or {}),
        "_build_canonical_design_state_pack": lambda incoming: {
            **dict(incoming or {}),
            "canonical_pack_built": True,
            "canonical_pack_valid": True,
            "canonical_pack_source": "synthetic_post_core_low_bending_terminal_fixture",
        },
        "_canonical_pack_is_valid": lambda pack: True,
        "_design_state_coherence_check": lambda pack: {"coherence_should_block": False},
        "_resolve_compute_design_guidance_family_early_dispatch": lambda **kwargs: None,
        "_compute_design_guidance_items_core": _core,
        "_collect_design_overview": lambda *args, **kwargs: _overview(),
        "_overview_required_checks_acceptable": lambda overview: True,
        "_post_click_low_bending_resolution_item": _post_click_low_bending_resolution_item,
        "_bending_only_target_band_cleanup_item": _bending_only_target_band_cleanup_item,
        "_design_guide_button_contract": _design_guide_button_contract,
        "_orchestrate_compute_post_core_publication_handoff": _orchestrate_compute_post_core_publication_handoff,
        "_attach_design_brain_result_boundary": lambda out, **kwargs: dict(out or {}),
    }
    with _patched(module, replacements):
        return module._compute_design_guidance_items(
            dict(state),
            debug_enabled=True,
            request_kind="design_guide",
        )


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"compute_post_core_low_bending_terminal_trace_{stamp}.jsonl"
    output_path = ARTIFACT_DIR / f"compute_post_core_low_bending_terminal_snapshot_{stamp}.json"
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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "COMPUTE_POST_CORE_LOW_BENDING_TERMINAL"
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
    overview = _overview()
    bending_util = overview["utils"]["bending"]
    threshold = float(getattr(module, "FINAL_ACCEPTED_MIN_FAMILY_UTIL", 0.85))
    branch_condition = {
        "request_kind_is_design_guide": True,
        "bending_util": bending_util,
        "threshold": threshold,
        "bending_below_threshold": float(bending_util) < threshold - 1e-9,
        "overview_required_checks_acceptable": True,
        "overview_any_fail": bool(overview.get("any_fail")),
    }
    late_events = {
        event: _route_count(trace_rows, event)
        for event in (
            "late_evidence_lane_enter",
            "late_evidence_contract_rebound_applied",
            "late_evidence_lane_exit",
        )
    }

    failures: list[str] = []
    if not all(
        (
            branch_condition["request_kind_is_design_guide"],
            branch_condition["bending_below_threshold"],
            branch_condition["overview_required_checks_acceptable"],
            not branch_condition["overview_any_fail"],
        )
    ):
        failures.append("low_bending_terminal_condition_not_satisfied")
    if not any(row.get("function") == "_post_click_low_bending_resolution_item" for row in observations):
        failures.append("post_click_low_bending_resolution_not_called")
    if not any(row.get("function") == "_orchestrate_compute_post_core_publication_handoff" for row in observations):
        failures.append("post_core_handoff_not_observed")
    if not debug_trace.get("terminal_green_low_bending_core_suppressed"):
        failures.append("terminal_green_low_bending_core_not_suppressed")
    if str(debug_trace.get("guidance_branch") or "") not in {
        "synthetic_low_bending_terminal_resolution",
        "bending_below_target_multi_family_resolution",
    }:
        failures.append(f"unexpected_guidance_branch:{debug_trace.get('guidance_branch')}")
    if len(output_items) != 1:
        failures.append(f"guidance_items_count:{len(output_items)}")
    if primary.get("id") != "synthetic_low_bending_terminal_resolution":
        failures.append(f"final_item_id:{primary.get('id')}")
    if primary.get("family") != "bending":
        failures.append("final_family_not_bending")
    if primary.get("action_type") != "apply_resolved_candidate":
        failures.append("final_action_not_apply_resolved_candidate")
    if not (contract.get("enabled") and contract.get("actionable")):
        failures.append("button_contract_not_actionable")
    if not evidence:
        failures.append("candidate_search_evidence_missing")
    if late_events.get("late_evidence_contract_rebound_applied"):
        failures.append("unexpected_contract_rebound")

    snapshot = {
        "schema": "compute_post_core_low_bending_terminal_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "trace_path": str(trace_path),
        "input_item": _item_summary(_core_item()),
        "low_bending_terminal_condition": branch_condition,
        "before_after_item_fields": {
            "before": _item_summary(_core_item()),
            "after": _item_summary(primary),
            "item_changed": _stable_hash(_core_item()) != _stable_hash(primary),
        },
        "family_status_fields": {
            "before_family": _core_item().get("family"),
            "after_family": primary.get("family"),
            "before_status": _core_item().get("status"),
            "after_status": primary.get("status"),
            "guidance_branch": debug_trace.get("guidance_branch"),
            "terminal_green_low_bending_core_suppressed": debug_trace.get(
                "terminal_green_low_bending_core_suppressed"
            ),
        },
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
        "publication_handoff_fields": {
            "handoff_observed": any(
                row.get("function") == "_orchestrate_compute_post_core_publication_handoff"
                for row in observations
            ),
            "selected_family_id": primary.get("selected_family_id"),
            "published_family_id": primary.get("published_family_id"),
            "cta_family_id": primary.get("cta_family_id"),
            "primary_card_title": debug_trace.get("primary_card_title"),
            "selected_title": debug_trace.get("selected_title"),
            "selected_action_family": debug_trace.get("selected_action_family"),
            "display_truth_hash": _stable_hash(primary.get("display_truth") or {}),
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
        "debug_trace_fields": {
            "debug_hash": _stable_hash(debug_trace),
            "debug_keys": sorted(str(k) for k in debug_trace.keys())[:160],
            "candidate_search_evidence_hash": _stable_hash(debug_trace.get("candidate_search_evidence") or {}),
            "primary_button_contract_hash": _stable_hash(debug_trace.get("primary_button_contract") or {}),
            "primary_display_truth_hash": _stable_hash(debug_trace.get("primary_display_truth") or {}),
        },
        "observations": observations,
        "event_counts": late_events,
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
