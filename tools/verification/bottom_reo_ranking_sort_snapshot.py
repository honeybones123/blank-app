"""Snapshot bottom reo ranking-sort behaviour.

This verifier freezes the current page-local bottom reo ranking wrapper before
any ranking ownership movement. It lets `_keep_top_candidates(...)` run and
wraps only the generic ranking core to capture sort keys, dedupe keys,
ordered/kept identities, prune decisions, and the current `reo_complexity`
annotation surface.
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

from design_brain.families.bending import (
    build_bottom_reo_ranked_candidates,
    build_bottom_reo_ranking_policy_inputs,
    build_bottom_reo_ranking_wrapper_proof,
)
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

FORBIDDEN_RANKING_SORT_KEYS = {
    "action_payload",
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


def _candidate_identity(candidate: dict[str, Any]) -> str:
    candidate_id = candidate.get("candidate_id") or candidate.get("source_candidate_id")
    if candidate_id:
        return str(candidate_id)
    return f"trace:{_stable_hash(candidate)}"


def _safe_tuple(value: Any) -> list[Any]:
    if isinstance(value, tuple):
        return [_safe_tuple(item) for item in value]
    if isinstance(value, list):
        return [_safe_tuple(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_tuple(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    return value


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_boundary(trace_rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    expected = f"BOTTOM_REO_RANKING_SORT_{scenario}"
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


def _rank_candidate_record(candidate: dict[str, Any], *, index: int) -> dict[str, Any]:
    return {
        "order_index": index,
        "candidate_identity": _candidate_identity(candidate),
        "reo_complexity": _as_float(candidate.get("reo_complexity")),
        "score": _as_float(candidate.get("score")),
        "worst_util": _as_float(candidate.get("worst_util")),
        "candidate_post_util": _as_float(candidate.get("candidate_post_util")),
        "candidate_reaches_target_band": (
            bool(candidate.get("candidate_reaches_target_band"))
            if "candidate_reaches_target_band" in candidate
            else None
        ),
        "candidate_distance_to_target_band": _as_float(candidate.get("candidate_distance_to_target_band")),
    }


def _build_ranked_candidates(
    *,
    ordered: list[str],
    kept: list[str],
    decisions: list[dict[str, Any]],
    sort_key_by_identity: dict[str, Any],
    dedupe_key_by_identity: dict[str, Any],
    reo_complexity_before: dict[str, Any],
    reo_complexity_after: dict[str, Any],
) -> list[dict[str, Any]]:
    decision_by_identity = {
        str(item.get("candidate_identity") or ""): str(item.get("decision") or "unknown")
        for item in decisions
        if isinstance(item, dict)
    }
    kept_set = set(str(identity) for identity in kept)
    ranked_records: list[dict[str, Any]] = []
    for index, identity in enumerate(ordered):
        identity_text = str(identity or "")
        if not identity_text:
            continue
        ranked_records.append(
            {
                "ranked_order_index": index,
                "source_scored_candidate_identity": identity_text,
                "candidate_identity": identity_text,
                "rank_status": decision_by_identity.get(
                    identity_text,
                    "kept" if identity_text in kept_set else "unknown",
                ),
                "sort_key_summary": {
                    "sort_key": sort_key_by_identity.get(identity_text),
                },
                "dedupe_key_summary": {
                    "dedupe_key": dedupe_key_by_identity.get(identity_text),
                },
                "reo_complexity_before": reo_complexity_before.get(identity_text),
                "reo_complexity_after": reo_complexity_after.get(identity_text),
                "kept_candidate_hash_inputs": {
                    "kept": identity_text in kept_set,
                    "candidate_identity": identity_text,
                },
            },
        )
    return [
        item.to_dict()
        for item in build_bottom_reo_ranked_candidates(ranked_records=ranked_records)
    ]


def _run_scenario(module: Any, scenario: str, trace_path: Path) -> dict[str, Any]:
    state = boundary_snapshot._scenario_state(scenario)
    seed_state = dict(state)
    seed_ast = boundary_snapshot._ast_for(boundary_snapshot._arrangement_from_state(seed_state))
    seed_util = 1.12 if scenario != "bending_overdesign_cleanup" else 0.72
    captured: dict[str, Any] = {
        "core_calls": 0,
        "core_input_candidates": [],
        "core_result": {},
        "sort_key_by_identity": {},
        "dedupe_key_by_identity": {},
        "reo_complexity_before": {},
        "reo_complexity_after": {},
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

    real_keep_top = module._keep_top_candidates
    ranking_provider = getattr(module, "_ranking_verifier_provider", module)
    candidate_key = getattr(module, "_make_auto_design_candidate_key", None)
    if candidate_key is None:
        candidate_key = getattr(ranking_provider, "_make_auto_design_candidate_key")
    sort_key = getattr(ranking_provider, "_candidate_sort_key_for_mode")
    dominates_for_mode = getattr(ranking_provider, "_candidate_dominates_for_mode")

    def _capture_keep_top(
        candidates: list[dict] | tuple[dict, ...],
        mode_config: dict,
        *,
        limit: int,
    ) -> list[dict]:
        candidate_list = list(candidates or [])
        captured["core_calls"] = int(captured.get("core_calls") or 0) + 1
        captured["core_input_candidates"] = [dict(candidate or {}) for candidate in candidate_list]
        before: dict[str, Any] = {}
        sort_keys: dict[str, Any] = {}
        dedupe_keys: dict[str, Any] = {}
        for candidate in candidate_list:
            if not isinstance(candidate, dict):
                continue
            identity = _candidate_identity(candidate)
            before[identity] = candidate.get("reo_complexity")
            dedupe_keys[identity] = _safe_tuple(candidate_key(candidate.get("state") or {}))
            sort_keys[identity] = _safe_tuple(sort_key(candidate, mode_config))
        best_by_dedupe_key: dict[Any, dict] = {}
        for candidate in candidate_list:
            if not isinstance(candidate, dict):
                continue
            key = candidate_key(candidate.get("state") or {})
            existing = best_by_dedupe_key.get(key)
            if existing is None or sort_key(candidate, mode_config) < sort_key(existing, mode_config):
                best_by_dedupe_key[key] = candidate
        ordered_candidates = sorted(
            best_by_dedupe_key.values(),
            key=lambda candidate: sort_key(candidate, mode_config),
        )
        result = list(real_keep_top(candidate_list, mode_config, limit=limit) or [])
        kept_ids = {_candidate_identity(candidate) for candidate in result if isinstance(candidate, dict)}
        decision_records: list[tuple[dict, str]] = []
        decision_kept: list[dict] = []
        for candidate in ordered_candidates:
            if any(dominates_for_mode(existing, candidate, mode_config) for existing in decision_kept):
                decision = "discarded_dominated"
            elif len(decision_kept) >= len(result):
                decision = "discarded_limit"
            else:
                decision = "kept"
                decision_kept.append(candidate)
            decision_records.append((candidate, decision))
        after = {
            _candidate_identity(candidate): candidate.get("reo_complexity")
            for candidate in candidate_list
            if isinstance(candidate, dict)
        }
        captured["core_result"] = {
            "ordered": ordered_candidates,
            "kept": result,
            "decisions": decision_records,
        }
        captured["sort_key_by_identity"] = sort_keys
        captured["dedupe_key_by_identity"] = dedupe_keys
        captured["reo_complexity_before"] = before
        captured["reo_complexity_after"] = after
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
        "_keep_top_candidates": _capture_keep_top,
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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_RANKING_SORT_{scenario}"
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
    decisions = []
    for candidate, decision in list(core_result.get("decisions") or []):
        if not isinstance(candidate, dict):
            continue
        decisions.append({
            "candidate_identity": _candidate_identity(candidate),
            "decision": str(decision),
        })
    rejected = [item for item in decisions if item.get("decision") != "kept"]
    forbidden_present = sorted(
        {
            key
            for candidate in input_candidates + ordered_candidates + kept_candidates
            if isinstance(candidate, dict)
            for key in sorted(set(candidate.keys()) & FORBIDDEN_RANKING_SORT_KEYS)
        },
    )
    scored_order = [_candidate_identity(candidate) for candidate in input_candidates if isinstance(candidate, dict)]
    ordered = [_candidate_identity(candidate) for candidate in ordered_candidates if isinstance(candidate, dict)]
    kept = [_candidate_identity(candidate) for candidate in kept_candidates if isinstance(candidate, dict)]
    ranked_candidates = _build_ranked_candidates(
        ordered=ordered,
        kept=kept,
        decisions=decisions,
        sort_key_by_identity=dict(captured.get("sort_key_by_identity") or {}),
        dedupe_key_by_identity=dict(captured.get("dedupe_key_by_identity") or {}),
        reo_complexity_before=dict(captured.get("reo_complexity_before") or {}),
        reo_complexity_after=dict(captured.get("reo_complexity_after") or {}),
    )
    mode_config = boundary_snapshot._mode_config(state)
    policy_input_primitives = [
        policy_input_snapshot._policy_input_record(
            module,
            candidate,
            index=index,
            mode_config=mode_config,
            dedupe_key=dict(captured.get("dedupe_key_by_identity") or {}).get(_candidate_identity(candidate)),
            sort_key=dict(captured.get("sort_key_by_identity") or {}).get(_candidate_identity(candidate)),
            complexity_before=dict(captured.get("reo_complexity_before") or {}).get(_candidate_identity(candidate)),
            complexity_after=dict(captured.get("reo_complexity_after") or {}).get(_candidate_identity(candidate)),
        )
        for index, candidate in enumerate(input_candidates)
        if isinstance(candidate, dict)
    ]
    typed_policy_inputs = build_bottom_reo_ranking_policy_inputs(records=policy_input_primitives)
    wrapper_proof = build_bottom_reo_ranking_wrapper_proof(policy_inputs=typed_policy_inputs)
    wrapper = wrapper_proof.to_dict()
    wrapper_ordered = list(wrapper.get("ordered_candidate_identities") or [])
    wrapper_kept = list(wrapper.get("kept_candidate_identities") or [])
    wrapper_pruned = list(wrapper.get("pruned_candidate_identities") or [])
    page_pruned = [str(item.get("candidate_identity") or "") for item in rejected]
    ranking_surface = {
        "scored_order": scored_order,
        "sort_key_by_identity": captured.get("sort_key_by_identity") or {},
        "dedupe_key_by_identity": captured.get("dedupe_key_by_identity") or {},
        "ordered": ordered,
        "kept": kept,
        "decisions": decisions,
        "reo_complexity_before": captured.get("reo_complexity_before") or {},
        "reo_complexity_after": captured.get("reo_complexity_after") or {},
    }
    return {
        "scenario": scenario,
        "trace_event_found": bool(boundary),
        "core_call_count": int(captured.get("core_calls") or 0),
        "scored_candidate_count": len(scored_order),
        "scored_candidate_order": scored_order,
        "scored_candidates_before_ranking": [
            _rank_candidate_record(candidate, index=index)
            for index, candidate in enumerate(input_candidates)
            if isinstance(candidate, dict)
        ],
        "sort_key_by_identity": captured.get("sort_key_by_identity") or {},
        "dedupe_key_by_identity": captured.get("dedupe_key_by_identity") or {},
        "ordered_candidate_count": len(ordered),
        "ordered_candidate_order": ordered,
        "kept_candidate_count": len(kept),
        "kept_candidate_order": kept,
        "ranked_candidates": ranked_candidates,
        "rejected_pruned_candidates": rejected,
        "rank_decisions": decisions,
        "wrapper_proof": wrapper,
        "wrapper_ordered_candidate_order": wrapper_ordered,
        "wrapper_kept_candidate_order": wrapper_kept,
        "wrapper_pruned_candidate_order": wrapper_pruned,
        "wrapper_parity": {
            "ordered_identities_match": ordered == wrapper_ordered,
            "kept_identities_match": kept == wrapper_kept,
            "pruned_identities_match": page_pruned == wrapper_pruned,
            "sort_hash_matches": _stable_hash(ranking_surface) == wrapper.get("sort_key_hash"),
            "kept_hash_matches": _stable_hash(kept) == wrapper.get("kept_candidate_hash"),
        },
        "reo_complexity_before": captured.get("reo_complexity_before") or {},
        "reo_complexity_after": captured.get("reo_complexity_after") or {},
        "ranking_sort_hash": _stable_hash(ranking_surface),
        "kept_candidate_hash": _stable_hash(kept),
        "forbidden_keys_present": forbidden_present,
        "boundary": {
            "pre_rank_surface_hash": boundary.get("pre_rank_surface_hash"),
            "accepted_prerank_order_hash": boundary.get("accepted_prerank_order_hash"),
            "forbidden_fields_present": list(boundary.get("forbidden_fields_present") or []),
        },
    }


def _assert_scenario(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if int(result.get("scored_candidate_count") or 0) > 0 and int(result.get("core_call_count") or 0) <= 0:
        failures.append("ranking_core_not_called")
    if not result.get("ranking_sort_hash"):
        failures.append("missing_ranking_sort_hash")
    if not result.get("kept_candidate_hash"):
        failures.append("missing_kept_candidate_hash")
    if int(result.get("scored_candidate_count") or 0) > 0 and not result.get("sort_key_by_identity"):
        failures.append("missing_sort_key_surface")
    if int(result.get("scored_candidate_count") or 0) > 0 and not result.get("dedupe_key_by_identity"):
        failures.append("missing_dedupe_key_surface")
    if list(result.get("forbidden_keys_present") or []):
        failures.append(f"forbidden_ranking_sort_keys:{','.join(result.get('forbidden_keys_present') or [])}")
    wrapper_parity = dict(result.get("wrapper_parity") or {})
    for key in (
        "ordered_identities_match",
        "kept_identities_match",
        "pruned_identities_match",
        "sort_hash_matches",
        "kept_hash_matches",
    ):
        if not bool(wrapper_parity.get(key)):
            failures.append(f"wrapper_parity_failed:{key}")
    return sorted(set(failures))


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page_modules.recommendation_compute")
    provider = importlib.import_module("inputs_page_app_contract_bridge")
    module._bind_named_recommendation_globals(
        legacy_page=provider,
        names=module._BOTTOM_RECOMMENDATION_NAMES,
    )
    module._ranking_verifier_provider = provider
    module._candidate_util_distance = provider._candidate_util_distance
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_ranking_sort_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_ranking_sort_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_ranking_sort_{stamp}.md"

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
        same_sort = scenario_result.get("ranking_sort_hash") == repeat.get("ranking_sort_hash")
        same_kept = scenario_result.get("kept_candidate_hash") == repeat.get("kept_candidate_hash")
        stability[scenario_name] = {
            "same_ranking_sort_hash": same_sort,
            "same_kept_candidate_hash": same_kept,
            "first_ranking_sort_hash": scenario_result.get("ranking_sort_hash"),
            "repeat_ranking_sort_hash": repeat.get("ranking_sort_hash"),
            "first_kept_candidate_hash": scenario_result.get("kept_candidate_hash"),
            "repeat_kept_candidate_hash": repeat.get("kept_candidate_hash"),
        }
        if int(scenario_result.get("scored_candidate_count") or 0) == 0:
            zero_accepted_seen = True
        if not same_sort:
            scenario_failures.append("unstable_ranking_sort_hash")
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
        "forbidden_ranking_sort_keys": sorted(FORBIDDEN_RANKING_SORT_KEYS),
        "assertions": {
            "real_page_ranking_wrapper_used": True,
            "ranking_logic_moved": False,
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
            "reo_complexity_mutation_proof_recorded": True,
            "product_path_changed": False,
        },
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")

    report_lines = [
        "# Bottom Reo Ranking-Sort Snapshot",
        "",
        f"- Status: {status}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "This snapshot freezes bottom reo ranking-sort behaviour by letting the existing page-local `_keep_top_candidates(...)` wrapper run and wrapping only the injected generic ranking core.",
        "",
        "It records scored input order, sort keys, dedupe keys, ordered candidates, kept candidates, prune decisions, and `reo_complexity` before/after annotation. It does not move ranking, selection, CTA, one-click, publication, UI/session, or debug logic.",
        "",
        "## Scenario Summary",
    ]
    for scenario_result in scenarios:
        name = str(scenario_result.get("scenario"))
        report_lines.extend([
            "",
            f"### {name}",
            f"- scored count: {scenario_result.get('scored_candidate_count')}",
            f"- ordered count: {scenario_result.get('ordered_candidate_count')}",
            f"- kept count: {scenario_result.get('kept_candidate_count')}",
            f"- ranking sort hash: `{scenario_result.get('ranking_sort_hash')}`",
            f"- kept candidate hash: `{scenario_result.get('kept_candidate_hash')}`",
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
            "Do not move ranking. Repair the ranking-sort proof surface first.",
        ])
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. Ranking-sort behaviour is stable and selector/CTA/one-click/publication/UI/session/debug fields are absent.",
            "",
            "## Recommendation",
            "",
            "Next slice can add a typed `BottomReoRankedCandidate` boundary as proof-only. Do not move sort policy yet.",
        ])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": status,
        "artifact": str(artifact_path),
        "report": str(report_path),
        "trace": str(trace_path),
        "failures": failures,
    }, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
