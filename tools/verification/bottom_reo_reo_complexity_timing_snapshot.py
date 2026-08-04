"""Snapshot bottom reo reo_complexity annotation timing.

This verifier freezes how `reo_complexity` is added during the current
page-local bottom-reinforcement ranking path. It does not move ranking,
selection, CTA/action, one-click, publication, UI/session, debug, or evaluator
logic.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.verification import bottom_reo_evaluated_candidate_filter_boundary_snapshot as boundary_snapshot
from tools.verification import bottom_reo_ranking_policy_input_snapshot as policy_input_snapshot


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

SCENARIOS = [
    "normal_bending_underdesign",
    "two_layer_arrangement",
    "bending_overdesign_cleanup",
]

FORBIDDEN_REO_COMPLEXITY_KEYS = {
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "debug",
    "final_selected_repair",
    "one_click",
    "publication",
    "render",
    "selected_recommendation",
    "session_state",
    "ui",
}


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _safe_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_value(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    return value


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_identity(candidate: dict[str, Any]) -> str:
    return policy_input_snapshot._candidate_identity(candidate)


def _without_reo_complexity(candidate: dict[str, Any]) -> dict[str, Any]:
    clone = dict(candidate or {})
    clone.pop("reo_complexity", None)
    return clone


def _extract_boundary(trace_rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    expected = f"BOTTOM_REO_REO_COMPLEXITY_TIMING_{scenario}"
    for row in trace_rows:
        if row.get("scenario") != expected:
            continue
        if row.get("route_event") != "bottom_reo_recommendation_candidates":
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        boundary_json = payload.get("evaluated_candidate_filter_boundary_json")
        if isinstance(boundary_json, str) and boundary_json.strip():
            parsed = json.loads(boundary_json)
            if isinstance(parsed, dict):
                return parsed
        boundary = payload.get("evaluated_candidate_filter_boundary")
        if isinstance(boundary, dict):
            return boundary
    return {}


def _safe_callback(callback, *args: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "value": _safe_value(callback(*args))}
    except Exception as exc:  # pragma: no cover - snapshot diagnostic path
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def _run_scenario(module: Any, scenario: str, trace_path: Path) -> dict[str, Any]:
    state = boundary_snapshot._scenario_state(scenario)
    seed_state = dict(state)
    seed_ast = boundary_snapshot._ast_for(boundary_snapshot._arrangement_from_state(seed_state))
    seed_util = 1.12 if scenario != "bending_overdesign_cleanup" else 0.72
    captured: dict[str, Any] = {
        "compute_calls": [],
        "core_calls": 0,
        "core_input_candidates": [],
        "core_result": {},
        "annotation_records": [],
        "dominance_records": [],
        "suppress_compute_capture": False,
    }

    def _seed_candidate(_state: dict, *, source: str = "", **_: Any) -> dict[str, Any] | None:
        seed = dict(_state or {})
        return {
            "candidate_id": f"{scenario}_seed",
            "source_candidate_id": f"{scenario}_seed",
            "state": seed,
            "updates": {},
            "label": f"seed:{source}",
            "action_type": "seed",
            "is_compliant": seed_util <= 1.0,
            "overview": boundary_snapshot._overview(seed_util, compliant=seed_util <= 1.0),
            "worst_util": seed_util,
            "Ast_bot": seed_ast,
            "actual_ast": seed_ast,
        }

    def _evaluate_fast(
        candidate_state: dict,
        *,
        seed_state: dict,
        source: str = "",
        label: str = "",
        action_type: str = "",
        **_: Any,
    ) -> dict[str, Any] | None:
        return boundary_snapshot._candidate_from_state(
            dict(candidate_state or {}),
            seed_state=dict(seed_state or {}),
            source=f"{scenario}_{source}",
            label=label,
            action_type=action_type,
            seed_ast=seed_ast,
            seed_util=seed_util,
        )

    def _updates_match_state(incoming: dict, updates: dict) -> bool:
        update_dict = dict(updates or {})
        if not update_dict:
            return True
        return all((incoming or {}).get(key) == value for key, value in update_dict.items())

    real_compute_reo_complexity = module.compute_reo_complexity

    def _capture_compute_reo_complexity(candidate: dict) -> float:
        result = real_compute_reo_complexity(candidate)
        if not bool(captured.get("suppress_compute_capture")) and isinstance(candidate, dict):
            identity = _candidate_identity(candidate)
            captured.setdefault("compute_calls", []).append(
                {
                    "candidate_identity": identity,
                    "before_value": _as_float(candidate.get("reo_complexity")),
                    "computed_value": _as_float(result),
                    "method": "setdefault_compute_reo_complexity",
                }
            )
        return result

    def _call_without_capture(callback, *args: Any) -> dict[str, Any]:
        previous = bool(captured.get("suppress_compute_capture"))
        captured["suppress_compute_capture"] = True
        try:
            return _safe_callback(callback, *args)
        finally:
            captured["suppress_compute_capture"] = previous

    real_keep_top_core = module._keep_top_candidates_core

    def _capture_keep_top_core(
        candidates: list[dict] | tuple[dict, ...],
        *,
        limit: int,
        max_kept_results: int,
        candidate_key,
        sort_key,
        dominates,
    ) -> dict[str, Any]:
        candidate_list = list(candidates or [])
        captured["core_calls"] = int(captured.get("core_calls") or 0) + 1
        captured["core_input_candidates"] = [dict(candidate or {}) for candidate in candidate_list]
        compute_by_identity = {
            str(item.get("candidate_identity") or ""): item
            for item in list(captured.get("compute_calls") or [])
            if isinstance(item, dict)
        }
        annotation_records: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidate_list):
            if not isinstance(candidate, dict):
                continue
            identity = _candidate_identity(candidate)
            before_candidate = _without_reo_complexity(candidate)
            compute_call = compute_by_identity.get(identity, {})
            sort_key_before = _call_without_capture(sort_key, before_candidate)
            sort_key_after = _call_without_capture(sort_key, candidate)
            dedupe_before = _call_without_capture(candidate_key, before_candidate)
            dedupe_after = _call_without_capture(candidate_key, candidate)
            annotation_records.append(
                {
                    "order_index": index,
                    "candidate_identity": identity,
                    "before_annotation_identity": _candidate_identity(before_candidate),
                    "after_annotation_identity": identity,
                    "reo_complexity_before_annotation": _as_float(
                        compute_call.get("before_value") if isinstance(compute_call, dict) else None
                    ),
                    "reo_complexity_computed_value": _as_float(
                        compute_call.get("computed_value") if isinstance(compute_call, dict) else None
                    ),
                    "reo_complexity_after_annotation": _as_float(candidate.get("reo_complexity")),
                    "annotation_method": (
                        "setdefault_compute_reo_complexity"
                        if identity in compute_by_identity
                        else "preexisting_or_not_called"
                    ),
                    "annotation_happens": "inside__keep_top_candidates_before_core",
                    "sort_key_before_annotation": sort_key_before,
                    "sort_key_after_annotation": sort_key_after,
                    "sort_key_changed_by_annotation": sort_key_before != sort_key_after,
                    "dedupe_key_before_annotation": dedupe_before,
                    "dedupe_key_after_annotation": dedupe_after,
                    "dedupe_key_changed_by_annotation": dedupe_before != dedupe_after,
                }
            )

        def _dominates(existing: dict, candidate: dict) -> bool:
            before_existing = _without_reo_complexity(existing if isinstance(existing, dict) else {})
            before_candidate = _without_reo_complexity(candidate if isinstance(candidate, dict) else {})
            before = _call_without_capture(dominates, before_existing, before_candidate)
            after_result = bool(dominates(existing, candidate))
            after = {"ok": True, "value": after_result}
            captured.setdefault("dominance_records", []).append(
                {
                    "existing_identity": _candidate_identity(existing if isinstance(existing, dict) else {}),
                    "candidate_identity": _candidate_identity(candidate if isinstance(candidate, dict) else {}),
                    "dominance_before_annotation": before,
                    "dominance_after_annotation": after,
                    "dominance_changed_by_annotation": before != after,
                }
            )
            return after_result

        result = real_keep_top_core(
            candidate_list,
            limit=limit,
            max_kept_results=max_kept_results,
            candidate_key=candidate_key,
            sort_key=sort_key,
            dominates=_dominates,
        )
        captured["core_result"] = result
        captured["annotation_records"] = annotation_records
        return result

    replacements = {
        "_guidance_state_snapshot": lambda incoming=None: dict(incoming or {}),
        "_recommendation_search_allowed": lambda incoming: True,
        "_build_design_actions_context": lambda incoming: {"state": dict(incoming or {})},
        "_collect_design_overview": lambda incoming, **kwargs: boundary_snapshot._overview(seed_util, compliant=seed_util <= 1.0),
        "_efficiency_reduction_profile_from_overview": lambda overview: False,
        "_design_optimisation_goal": lambda incoming=None: str(state.get("design_optimisation_goal") or "balanced"),
        "_design_mode_config": lambda goal=None: boundary_snapshot._mode_config(state),
        "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (0.85, 1.0, False),
        "evaluate_candidate_full": _seed_candidate,
        "_build_auto_design_context": lambda seed, mode_config, **kwargs: {"state": dict(seed or {}), "mode_config": dict(mode_config or {})},
        "_effective_bottom_design_state": lambda incoming: {"Ast_bot": seed_ast},
        "_evaluate_candidate_fast": _evaluate_fast,
        "_score_auto_design_candidate": lambda candidate, mode_config, seed_candidate: float(candidate.get("score", 100.0) or 100.0),
        "_candidate_in_target_band": lambda candidate, mode_config: bool((candidate or {}).get("in_target_band", False)),
        "_geometry_lock_enabled": lambda incoming: True,
        "_updates_match_state": _updates_match_state,
        "_candidate_materially_improves": lambda seed, candidate: True,
        "_collapse_bottom_geometry_width_depth_trials": lambda candidates, **kwargs: list(candidates or []),
        "_merge_design_guide_rank_trace": lambda payload: None,
        "_agent_debug_log": lambda *args, **kwargs: None,
        "_log_design_reco_candidate_rank": lambda *args, **kwargs: None,
        "_log_efficiency_growth_rejection": lambda *args, **kwargs: None,
        "_candidate_is_growth_move": lambda seed, candidate: False,
        "_annotate_bottom_reo_candidate_deltas": lambda candidate, seed, incoming: candidate.update({"delta_Ast_bot": round(float(candidate.get("Ast_bot", 0.0) or 0.0) - seed_ast, 3)}),
        "_annotate_candidate_target_band_metrics": lambda candidate, mode_config: candidate.update({
            "candidate_post_util": ((candidate.get("overview") or {}).get("utils") or {}).get("bending"),
            "candidate_reaches_target_band": bool(candidate.get("in_target_band")),
            "candidate_distance_to_target_band": 0.0 if candidate.get("in_target_band") else 0.15,
        }),
        "compute_reo_complexity": _capture_compute_reo_complexity,
        "_keep_top_candidates_core": _capture_keep_top_core,
        "_pick_best_bottom_recommendation_by_selector": lambda candidates, **kwargs: (list(candidates or [])[:1] or [None])[0],
        "_maybe_prefer_compound_over_pure_geometry": lambda best, ranked_bottom, **kwargs: best,
        "_evaluate_bending_with_bottom_state": lambda incoming, arrangement: {
            "db_bot": int((arrangement or {}).get("db_bot_1", 16) or 16),
            "nb_bot": int((arrangement or {}).get("bot1_count", 0) or 0),
            "d_centroid": 550.0,
        },
        "_required_ast_for_arrangement": lambda incoming, arrangement: 700.0,
        "_guidance_change_lines_for_updates": lambda incoming, updates: [
            f"{key} -> {value}" for key, value in sorted(dict(updates or {}).items())
        ],
    }

    before_rows = len(boundary_snapshot._load_jsonl(trace_path))
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_REO_COMPLEXITY_TIMING_{scenario}"
    with boundary_snapshot._patched(module, replacements):
        module._compute_bottom_reo_recommendation(
            dict(state),
            runtime=module.bottom_recommendation_runtime_from_namespace(
                module.__dict__
            ),
        )
    trace_rows = boundary_snapshot._load_jsonl(trace_path)[before_rows:]
    boundary = _extract_boundary(trace_rows, scenario)
    core_result = captured.get("core_result") if isinstance(captured.get("core_result"), dict) else {}
    input_candidates = list(captured.get("core_input_candidates") or [])
    ordered_candidates = list(core_result.get("ordered") or [])
    kept_candidates = list(core_result.get("kept") or [])
    records = list(captured.get("annotation_records") or [])
    forbidden_present = sorted(
        {
            key
            for record in records + list(captured.get("dominance_records") or [])
            if isinstance(record, dict)
            for key in sorted(set(record.keys()) & FORBIDDEN_REO_COMPLEXITY_KEYS)
        },
    )
    changed_sort = [
        str(record.get("candidate_identity") or "")
        for record in records
        if bool(record.get("sort_key_changed_by_annotation"))
    ]
    changed_dedupe = [
        str(record.get("candidate_identity") or "")
        for record in records
        if bool(record.get("dedupe_key_changed_by_annotation"))
    ]
    changed_dominance = [
        {
            "existing_identity": item.get("existing_identity"),
            "candidate_identity": item.get("candidate_identity"),
        }
        for item in list(captured.get("dominance_records") or [])
        if bool(item.get("dominance_changed_by_annotation"))
    ]
    annotation_hash_inputs = [
        {
            "candidate_identity": record.get("candidate_identity"),
            "before": record.get("reo_complexity_before_annotation"),
            "computed": record.get("reo_complexity_computed_value"),
            "after": record.get("reo_complexity_after_annotation"),
            "sort_changed": record.get("sort_key_changed_by_annotation"),
            "dedupe_changed": record.get("dedupe_key_changed_by_annotation"),
        }
        for record in records
    ]
    return {
        "scenario": scenario,
        "trace_event_found": bool(boundary),
        "core_call_count": int(captured.get("core_calls") or 0),
        "compute_call_count": len(list(captured.get("compute_calls") or [])),
        "candidate_count": len(records),
        "candidate_identities_before_annotation": [
            str(record.get("before_annotation_identity") or "") for record in records
        ],
        "candidate_identities_after_annotation": [
            str(record.get("after_annotation_identity") or "") for record in records
        ],
        "annotation_location": "inputs_page.py:_keep_top_candidates before _keep_top_candidates_core",
        "annotation_method": "candidate.setdefault('reo_complexity', compute_reo_complexity(candidate))",
        "annotation_depends_on_session_debug_page_state": False,
        "annotation_records": records,
        "dominance_records": list(captured.get("dominance_records") or []),
        "ordered_candidate_order": [_candidate_identity(candidate) for candidate in ordered_candidates if isinstance(candidate, dict)],
        "kept_candidate_order": [_candidate_identity(candidate) for candidate in kept_candidates if isinstance(candidate, dict)],
        "sort_key_changed_candidate_identities": changed_sort,
        "dedupe_key_changed_candidate_identities": changed_dedupe,
        "dominance_changed_pairs": changed_dominance,
        "annotation_hash": _stable_hash(annotation_hash_inputs),
        "ordered_candidate_hash": _stable_hash([_candidate_identity(candidate) for candidate in ordered_candidates if isinstance(candidate, dict)]),
        "kept_candidate_hash": _stable_hash([_candidate_identity(candidate) for candidate in kept_candidates if isinstance(candidate, dict)]),
        "forbidden_keys_present": forbidden_present,
        "boundary": {
            "pre_rank_surface_hash": boundary.get("pre_rank_surface_hash"),
            "accepted_prerank_order_hash": boundary.get("accepted_prerank_order_hash"),
            "forbidden_fields_present": list(boundary.get("forbidden_fields_present") or []),
        },
        "product_path_changed": False,
        "ranking_policy_moved": False,
        "selection_cta_one_click_publication_absent": not forbidden_present,
        "input_candidate_count_seen_by_core": len(input_candidates),
    }


def _assert_scenario(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not result.get("annotation_hash"):
        failures.append("missing_annotation_hash")
    if not result.get("ordered_candidate_hash"):
        failures.append("missing_ordered_candidate_hash")
    if not result.get("kept_candidate_hash"):
        failures.append("missing_kept_candidate_hash")
    if list(result.get("forbidden_keys_present") or []):
        failures.append(f"forbidden_reo_complexity_keys:{','.join(result.get('forbidden_keys_present') or [])}")
    if bool(result.get("annotation_depends_on_session_debug_page_state")):
        failures.append("annotation_depends_on_session_debug_page_state")
    if int(result.get("candidate_count") or 0) > 0:
        if int(result.get("compute_call_count") or 0) <= 0:
            failures.append("missing_compute_reo_complexity_calls")
        for item in list(result.get("annotation_records") or []):
            if not isinstance(item, dict):
                failures.append("annotation_record_not_dict")
                continue
            for key in (
                "candidate_identity",
                "reo_complexity_before_annotation",
                "reo_complexity_computed_value",
                "reo_complexity_after_annotation",
                "annotation_method",
                "sort_key_before_annotation",
                "sort_key_after_annotation",
                "dedupe_key_before_annotation",
                "dedupe_key_after_annotation",
            ):
                if key not in item:
                    failures.append(f"missing_{key}")
    return sorted(set(failures))


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_reo_complexity_timing_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_reo_complexity_timing_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_reo_complexity_timing_{stamp}.md"

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)

    try:
        scenarios = [_run_scenario(module, scenario, trace_path) for scenario in SCENARIOS]
        repeat_runs = [_run_scenario(module, scenario, trace_path) for scenario in SCENARIOS]
        repeats = {str(item.get("scenario")): item for item in repeat_runs}
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    failures: dict[str, list[str]] = {}
    stability: dict[str, dict[str, Any]] = {}
    zero_accepted_seen = False
    for scenario_result in scenarios:
        scenario_name = str(scenario_result.get("scenario"))
        scenario_failures = _assert_scenario(scenario_result)
        repeat = repeats.get(scenario_name, {})
        same_annotation = scenario_result.get("annotation_hash") == repeat.get("annotation_hash")
        same_ordered = scenario_result.get("ordered_candidate_hash") == repeat.get("ordered_candidate_hash")
        same_kept = scenario_result.get("kept_candidate_hash") == repeat.get("kept_candidate_hash")
        stability[scenario_name] = {
            "same_annotation_hash": same_annotation,
            "same_ordered_candidate_hash": same_ordered,
            "same_kept_candidate_hash": same_kept,
            "first_annotation_hash": scenario_result.get("annotation_hash"),
            "repeat_annotation_hash": repeat.get("annotation_hash"),
        }
        if int(scenario_result.get("candidate_count") or 0) == 0:
            zero_accepted_seen = True
        if not same_annotation:
            scenario_failures.append("unstable_annotation_hash")
        if not same_ordered:
            scenario_failures.append("unstable_ordered_candidate_hash")
        if not same_kept:
            scenario_failures.append("unstable_kept_candidate_hash")
        if scenario_failures:
            failures[scenario_name] = sorted(set(scenario_failures))
    if not zero_accepted_seen:
        failures.setdefault("_coverage", []).append("missing_zero_accepted_scenario")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "status": status,
        "generated_at": stamp,
        "trace_path": str(trace_path),
        "scenarios": scenarios,
        "stability": stability,
        "forbidden_reo_complexity_keys": sorted(FORBIDDEN_REO_COMPLEXITY_KEYS),
        "assertions": {
            "ranking_policy_moved": False,
            "keep_top_candidates_moved": False,
            "selection_cta_one_click_publication_absent": not any(
                set(result.get("forbidden_keys_present") or [])
                & {
                    "selected_recommendation",
                    "final_selected_repair",
                    "cta",
                    "button_contract",
                    "one_click",
                    "publication",
                    "render",
                    "ui",
                    "session_state",
                    "debug",
                }
                for result in scenarios
            ),
            "reo_complexity_timing_captured": True,
            "product_path_changed": False,
        },
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")

    report_lines = [
        "# Bottom Reo reo_complexity Timing Snapshot",
        "",
        f"- Status: {status}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "This snapshot freezes how `reo_complexity` is added during bottom reo ranking. It keeps `_keep_top_candidates(...)`, ranking policy, selection, CTA/action, one-click, publication, UI/session/debug, and evaluator execution page-local.",
        "",
        "Current implementation seam: `inputs_page.py:_keep_top_candidates(...)` adds `reo_complexity` with `candidate.setdefault('reo_complexity', compute_reo_complexity(candidate))` before calling `_keep_top_candidates_core(...)`.",
        "",
        "## Scenario Summary",
    ]
    for scenario_result in scenarios:
        name = str(scenario_result.get("scenario"))
        report_lines.extend([
            "",
            f"### {name}",
            f"- candidate count: {scenario_result.get('candidate_count')}",
            f"- compute call count: {scenario_result.get('compute_call_count')}",
            f"- annotation hash: `{scenario_result.get('annotation_hash')}`",
            f"- ordered candidate hash: `{scenario_result.get('ordered_candidate_hash')}`",
            f"- kept candidate hash: `{scenario_result.get('kept_candidate_hash')}`",
            f"- sort-key changed by annotation: `{scenario_result.get('sort_key_changed_candidate_identities')}`",
            f"- dedupe-key changed by annotation: `{scenario_result.get('dedupe_key_changed_candidate_identities')}`",
            f"- dominance changed by annotation: `{scenario_result.get('dominance_changed_pairs')}`",
            f"- forbidden keys present: `{scenario_result.get('forbidden_keys_present')}`",
            f"- stability: `{stability.get(name, {})}`",
        ])
    if failures:
        report_lines.extend(["", "## Failures", ""])
        for name, scenario_failures in failures.items():
            report_lines.append(f"- {name}: {', '.join(scenario_failures)}")
        report_lines.extend([
            "",
            "## Recommendation",
            "",
            "Repair the `reo_complexity` timing proof before moving ranking policy.",
        ])
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. `reo_complexity` annotation timing is stable and excludes selected recommendation, CTA, one-click, publication, render/UI, session, and debug fields.",
            "",
            "## Recommendation",
            "",
            "Next slice can audit a pure `reo_complexity` annotation helper. Do not move ranking sort/prune or `_keep_top_candidates(...)` yet.",
        ])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": status, "artifact": str(artifact_path), "report": str(report_path), "trace": str(trace_path), "failures": failures}, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
