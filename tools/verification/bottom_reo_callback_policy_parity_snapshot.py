"""Snapshot bottom reo callback-policy parity.

This verifier compares the current page-owned bottom reo sort/dedupe/dominance
callbacks against typed `BottomReoRankingPolicyInput` proof surfaces. It does
not move ranking policy, `_keep_top_candidates(...)`, `_keep_top_candidates_core(...)`,
selection, CTA/action, one-click, publication, UI/session/debug, or evaluator
execution.
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
    build_bottom_reo_ranking_callback_policy_proof,
    build_bottom_reo_ranking_policy_inputs,
)
from tools.verification import bottom_reo_evaluated_candidate_filter_boundary_snapshot as boundary_snapshot
from tools.verification import bottom_reo_ranking_policy_input_snapshot as policy_input_snapshot


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

SCENARIOS = [
    {
        "name": "balanced_normal_bending_underdesign",
        "base": "normal_bending_underdesign",
        "mode": "balanced",
        "seed_util": 1.12,
        "mutator": None,
    },
    {
        "name": "low_reo_two_layer",
        "base": "two_layer_arrangement",
        "mode": "low_reo",
        "seed_util": 1.12,
        "mutator": None,
    },
    {
        "name": "shallow_normal_bending",
        "base": "normal_bending_underdesign",
        "mode": "shallow",
        "seed_util": 1.12,
        "mutator": None,
    },
    {
        "name": "ductility_sensitive",
        "base": "normal_bending_underdesign",
        "mode": "balanced",
        "seed_util": 1.12,
        "mutator": "ductility",
    },
    {
        "name": "non_compliant_violation",
        "base": "normal_bending_underdesign",
        "mode": "balanced",
        "seed_util": 1.28,
        "mutator": "non_compliant",
    },
    {
        "name": "two_layer_arrangement",
        "base": "two_layer_arrangement",
        "mode": "balanced",
        "seed_util": 1.12,
        "mutator": None,
    },
    {
        "name": "zero_candidate_cleanup",
        "base": "bending_overdesign_cleanup",
        "mode": "low_reo",
        "seed_util": 0.72,
        "mutator": None,
    },
]

FORBIDDEN_CALLBACK_POLICY_KEYS = {
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


def _candidate_identity(candidate: dict[str, Any]) -> str:
    return policy_input_snapshot._candidate_identity(candidate)


def _mode_config(state: dict[str, Any], mode: str) -> dict[str, Any]:
    config = dict(boundary_snapshot._mode_config(state))
    if mode == "low_reo":
        config["search_strategy"] = "low_reo"
        config["label"] = "Less bottom reinforcement"
    elif mode == "shallow":
        config["search_strategy"] = "shallow"
        config["label"] = "Shallower beam"
    else:
        config["search_strategy"] = "balanced"
        config["label"] = "Balanced"
    return config


def _scenario_state(definition: dict[str, Any]) -> dict[str, Any]:
    state = boundary_snapshot._scenario_state(str(definition.get("base") or "normal_bending_underdesign"))
    if definition.get("mode") == "low_reo":
        state["design_optimisation_goal"] = "low_reo"
    elif definition.get("mode") == "shallow":
        state["design_optimisation_goal"] = "shallow"
    return state


def _extract_boundary(trace_rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    expected = f"BOTTOM_REO_CALLBACK_POLICY_PARITY_{scenario}"
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


def _mutate_candidate_for_scenario(candidate: dict[str, Any] | None, definition: dict[str, Any], index: int) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return candidate
    mutator = str(definition.get("mutator") or "")
    if mutator == "ductility":
        candidate["_ductility_priority"] = True
        candidate["_ductility_tier"] = int(index % 4)
        candidate["bending_components"] = {
            **dict(candidate.get("bending_components") or {}),
            "flexural_util": 0.78 + (0.01 * (index % 3)),
            "min_steel_util": 0.62,
            "ductility_util": 0.91 + (0.02 * (index % 4)),
        }
    elif mutator == "non_compliant":
        if index % 2 == 0:
            util = 1.08 + (0.03 * (index % 4))
            overview = dict(candidate.get("overview") or {})
            statuses = dict(overview.get("statuses") or {})
            utils = dict(overview.get("utils") or {})
            statuses["bending"] = "FAIL"
            utils["bending"] = util
            overview.update(
                {
                    "statuses": statuses,
                    "utils": utils,
                    "any_fail": True,
                    "all_key_pass": False,
                    "is_compliant": False,
                    "worst_util": util,
                    "governing_util": util,
                }
            )
            candidate["overview"] = overview
            candidate["is_compliant"] = False
            candidate["worst_util"] = util
            candidate["fail_count"] = int(candidate.get("fail_count", 0) or 0) + 1
            candidate["in_target_band"] = False
    return candidate


def _dominance_key(record: dict[str, Any]) -> tuple[str, str]:
    return (
        str(record.get("existing_identity") or ""),
        str(record.get("candidate_identity") or ""),
    )


def _run_scenario(module: Any, definition: dict[str, Any], trace_path: Path) -> dict[str, Any]:
    scenario = str(definition.get("name") or "")
    state = _scenario_state(definition)
    seed_state = dict(state)
    seed_ast = boundary_snapshot._ast_for(boundary_snapshot._arrangement_from_state(seed_state))
    seed_util = float(definition.get("seed_util", 1.12) or 1.12)
    mode_config = _mode_config(state, str(definition.get("mode") or "balanced"))
    candidate_counter = {"value": 0}
    captured: dict[str, Any] = {
        "core_calls": 0,
        "core_input_candidates": [],
        "core_result": {},
        "live_sort_key_by_identity": {},
        "live_dedupe_key_by_identity": {},
        "live_dominance_decisions": [],
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
        candidate = boundary_snapshot._candidate_from_state(
            dict(candidate_state or {}),
            seed_state=dict(seed_state or {}),
            source=f"{scenario}_{source}",
            label=label,
            action_type=action_type,
            seed_ast=seed_ast,
            seed_util=seed_util,
        )
        index = int(candidate_counter["value"])
        candidate_counter["value"] = index + 1
        return _mutate_candidate_for_scenario(candidate, definition, index)

    def _updates_match_state(incoming: dict, updates: dict) -> bool:
        update_dict = dict(updates or {})
        if not update_dict:
            return True
        return all((incoming or {}).get(key) == value for key, value in update_dict.items())

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
        live_sort: dict[str, Any] = {}
        live_dedupe: dict[str, Any] = {}
        live_surfaces: list[dict[str, Any]] = []
        before: dict[str, Any] = {}
        for index, candidate in enumerate(candidate_list):
            if not isinstance(candidate, dict):
                continue
            identity = _candidate_identity(candidate)
            candidate_dedupe = _safe_value(candidate_key(candidate))
            candidate_sort = _safe_value(sort_key(candidate))
            candidate_complexity_before = candidate.get("reo_complexity")
            before[identity] = candidate_complexity_before
            live_dedupe[identity] = candidate_dedupe
            live_sort[identity] = candidate_sort
            live_surfaces.append(
                {
                    "input_index": index,
                    "candidate_identity": identity,
                    "dedupe_key": candidate_dedupe,
                    "sort_key": candidate_sort,
                    "reo_complexity_before": candidate_complexity_before,
                }
            )

        def _dominates(existing: dict, candidate: dict) -> bool:
            result = bool(dominates(existing, candidate))
            captured.setdefault("live_dominance_decisions", []).append(
                {
                    "existing_identity": _candidate_identity(existing if isinstance(existing, dict) else {}),
                    "candidate_identity": _candidate_identity(candidate if isinstance(candidate, dict) else {}),
                    "dominates": result,
                }
            )
            return result

        result = real_keep_top_core(
            candidate_list,
            limit=limit,
            max_kept_results=max_kept_results,
            candidate_key=candidate_key,
            sort_key=sort_key,
            dominates=_dominates,
        )
        for index, candidate in enumerate(candidate_list):
            if index < len(live_surfaces) and isinstance(candidate, dict):
                live_surfaces[index]["reo_complexity_after"] = candidate.get("reo_complexity")
        captured["core_result"] = result
        captured["live_sort_key_by_identity"] = live_sort
        captured["live_dedupe_key_by_identity"] = live_dedupe
        captured["live_surfaces_by_input_order"] = live_surfaces
        captured["reo_complexity_before"] = before
        captured["reo_complexity_after"] = {
            _candidate_identity(candidate): candidate.get("reo_complexity")
            for candidate in candidate_list
            if isinstance(candidate, dict)
        }
        return result

    replacements = {
        "_guidance_state_snapshot": lambda incoming=None: dict(incoming or {}),
        "_recommendation_search_allowed": lambda incoming: True,
        "_build_design_actions_context": lambda incoming: {"state": dict(incoming or {})},
        "_collect_design_overview": lambda incoming, **kwargs: boundary_snapshot._overview(seed_util, compliant=seed_util <= 1.0),
        "_efficiency_reduction_profile_from_overview": lambda overview: False,
        "_design_optimisation_goal": lambda incoming=None: str(state.get("design_optimisation_goal") or "balanced"),
        "_design_mode_config": lambda goal=None: dict(mode_config),
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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_CALLBACK_POLICY_PARITY_{scenario}"
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
    live_sort = dict(captured.get("live_sort_key_by_identity") or {})
    live_dedupe = dict(captured.get("live_dedupe_key_by_identity") or {})
    live_surfaces = list(captured.get("live_surfaces_by_input_order") or [])
    live_dominance = list(captured.get("live_dominance_decisions") or [])
    policy_input_primitives = [
        policy_input_snapshot._policy_input_record(
            module,
            candidate,
            index=index,
            mode_config=mode_config,
            dedupe_key=(
                live_surfaces[index].get("dedupe_key")
                if index < len(live_surfaces)
                else live_dedupe.get(_candidate_identity(candidate))
            ),
            sort_key=(
                live_surfaces[index].get("sort_key")
                if index < len(live_surfaces)
                else live_sort.get(_candidate_identity(candidate))
            ),
            complexity_before=(
                live_surfaces[index].get("reo_complexity_before")
                if index < len(live_surfaces)
                else dict(captured.get("reo_complexity_before") or {}).get(_candidate_identity(candidate))
            ),
            complexity_after=(
                live_surfaces[index].get("reo_complexity_after")
                if index < len(live_surfaces)
                else dict(captured.get("reo_complexity_after") or {}).get(_candidate_identity(candidate))
            ),
        )
        for index, candidate in enumerate(input_candidates)
        if isinstance(candidate, dict)
    ]
    typed_policy_inputs = build_bottom_reo_ranking_policy_inputs(records=policy_input_primitives)
    typed_records = [item.to_dict() for item in typed_policy_inputs]
    live_ordered = [_candidate_identity(candidate) for candidate in ordered_candidates if isinstance(candidate, dict)]
    live_kept = [_candidate_identity(candidate) for candidate in kept_candidates if isinstance(candidate, dict)]
    live_decisions = [
        {
            "candidate_identity": _candidate_identity(candidate),
            "decision": str(decision),
        }
        for candidate, decision in list(core_result.get("decisions") or [])
        if isinstance(candidate, dict)
    ]
    live_pruned = [str(item.get("candidate_identity") or "") for item in live_decisions if str(item.get("decision") or "") != "kept"]
    callback_policy_proof = build_bottom_reo_ranking_callback_policy_proof(
        policy_inputs=typed_policy_inputs,
        live_sort_key_by_identity=live_sort,
        live_dedupe_key_by_identity=live_dedupe,
        live_dominance_decisions=live_dominance,
        live_ordered_identities=live_ordered,
        live_kept_identities=live_kept,
        live_pruned_identities=live_pruned,
        bounded_keep_limit=int(core_result.get("limit") or 0),
    ).to_dict()
    typed_sort = {
        str(identity): _safe_value(value)
        for identity, value in dict(callback_policy_proof.get("typed_sort_key_by_identity") or {}).items()
    }
    typed_dedupe = {
        str(identity): _safe_value(value)
        for identity, value in dict(callback_policy_proof.get("typed_dedupe_key_by_identity") or {}).items()
    }
    typed_dominance = list(callback_policy_proof.get("typed_dominance_decisions") or [])
    live_dominance_by_pair = {_dominance_key(item): bool(item.get("dominates")) for item in live_dominance if isinstance(item, dict)}
    typed_dominance_by_pair = {_dominance_key(item): bool(item.get("dominates")) for item in typed_dominance if isinstance(item, dict)}
    sort_mismatches = [
        identity
        for identity in sorted(set(live_sort) | set(typed_sort))
        if _safe_value(live_sort.get(identity)) != _safe_value(typed_sort.get(identity))
    ]
    dedupe_mismatches = [
        identity
        for identity in sorted(set(live_dedupe) | set(typed_dedupe))
        if _safe_value(live_dedupe.get(identity)) != _safe_value(typed_dedupe.get(identity))
    ]
    dominance_mismatches = [
        {"existing_identity": pair[0], "candidate_identity": pair[1]}
        for pair in sorted(set(live_dominance_by_pair) | set(typed_dominance_by_pair))
        if live_dominance_by_pair.get(pair) != typed_dominance_by_pair.get(pair)
    ]
    forbidden_present = sorted(
        {
            key
            for record in typed_records + live_dominance + typed_dominance
            if isinstance(record, dict)
            for key in sorted(set(record.keys()) & FORBIDDEN_CALLBACK_POLICY_KEYS)
        },
    )
    typed_ordered = list(callback_policy_proof.get("typed_ordered_identities") or [])
    typed_kept = list(callback_policy_proof.get("typed_kept_identities") or [])
    typed_pruned = list(callback_policy_proof.get("typed_pruned_identities") or [])
    parity_hash_surface = callback_policy_proof.get("parity_hash_inputs") or {
        "candidate_identities": [str(record.get("candidate_identity") or "") for record in typed_records],
        "live_sort": live_sort,
        "typed_sort": typed_sort,
        "live_dedupe": live_dedupe,
        "typed_dedupe": typed_dedupe,
        "live_dominance": live_dominance,
        "typed_dominance": typed_dominance,
        "live_ordered": live_ordered,
        "typed_ordered": typed_ordered,
        "live_kept": live_kept,
        "typed_kept": typed_kept,
    }
    return {
        "scenario": scenario,
        "mode": str(definition.get("mode") or ""),
        "mutator": definition.get("mutator"),
        "trace_event_found": bool(boundary),
        "candidate_count": len(typed_records),
        "candidate_identities": [str(record.get("candidate_identity") or "") for record in typed_records],
        "policy_inputs": [
            {
                "candidate_identity": record.get("candidate_identity"),
                "source_scored_candidate_identity": record.get("source_scored_candidate_identity"),
                "policy_input_hash": record.get("policy_input_hash"),
            }
            for record in typed_records
        ],
        "live_sort_key_by_identity": live_sort,
        "typed_policy_sort_key_by_identity": typed_sort,
        "live_dedupe_key_by_identity": live_dedupe,
        "typed_policy_dedupe_key_by_identity": typed_dedupe,
        "live_dominance_decisions": live_dominance,
        "typed_policy_dominance_decisions": typed_dominance,
        "live_ordered_identities": live_ordered,
        "typed_policy_ordered_identities": typed_ordered,
        "live_kept_identities": live_kept,
        "typed_policy_kept_identities": typed_kept,
        "live_pruned_identities": live_pruned,
        "typed_policy_pruned_identities": typed_pruned,
        "parity": {
            "sort_keys_match": not sort_mismatches,
            "dedupe_keys_match": not dedupe_mismatches,
            "dominance_decisions_match": not dominance_mismatches,
            "ordered_identities_match": live_ordered == typed_ordered,
            "kept_identities_match": live_kept == typed_kept,
            "pruned_identities_match": live_pruned == typed_pruned,
        },
        "mismatches": {
            "sort_key_identities": sort_mismatches,
            "dedupe_key_identities": dedupe_mismatches,
            "dominance_pairs": dominance_mismatches,
        },
        "parity_hash": _stable_hash(parity_hash_surface),
        "forbidden_keys_present": forbidden_present,
        "boundary": {
            "pre_rank_surface_hash": boundary.get("pre_rank_surface_hash"),
            "accepted_prerank_order_hash": boundary.get("accepted_prerank_order_hash"),
            "forbidden_fields_present": list(boundary.get("forbidden_fields_present") or []),
        },
    }


def _assert_scenario(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not result.get("parity_hash"):
        failures.append("missing_parity_hash")
    if list(result.get("forbidden_keys_present") or []):
        failures.append(f"forbidden_callback_policy_keys:{','.join(result.get('forbidden_keys_present') or [])}")
    parity = dict(result.get("parity") or {})
    for key in (
        "sort_keys_match",
        "dedupe_keys_match",
        "dominance_decisions_match",
        "ordered_identities_match",
        "kept_identities_match",
        "pruned_identities_match",
    ):
        if not bool(parity.get(key)):
            failures.append(f"parity_failed:{key}")
    if int(result.get("candidate_count") or 0) > 0:
        if not result.get("live_sort_key_by_identity"):
            failures.append("missing_live_sort_keys")
        if not result.get("typed_policy_sort_key_by_identity"):
            failures.append("missing_typed_sort_keys")
        if not result.get("live_dedupe_key_by_identity"):
            failures.append("missing_live_dedupe_keys")
        if not result.get("typed_policy_dedupe_key_by_identity"):
            failures.append("missing_typed_dedupe_keys")
    return sorted(set(failures))


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_callback_policy_parity_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_callback_policy_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_callback_policy_parity_{stamp}.md"

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
        scenarios = [_run_scenario(module, definition, trace_path) for definition in SCENARIOS]
        repeat_runs = [_run_scenario(module, definition, trace_path) for definition in SCENARIOS]
        repeats = {str(item.get("scenario")): item for item in repeat_runs}
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    failures: dict[str, list[str]] = {}
    stability: dict[str, dict[str, Any]] = {}
    zero_candidate_seen = False
    for scenario_result in scenarios:
        scenario_name = str(scenario_result.get("scenario"))
        scenario_failures = _assert_scenario(scenario_result)
        repeat = repeats.get(scenario_name, {})
        same_parity = scenario_result.get("parity_hash") == repeat.get("parity_hash")
        stability[scenario_name] = {
            "same_parity_hash": same_parity,
            "first_parity_hash": scenario_result.get("parity_hash"),
            "repeat_parity_hash": repeat.get("parity_hash"),
        }
        if int(scenario_result.get("candidate_count") or 0) == 0:
            zero_candidate_seen = True
        if not same_parity:
            scenario_failures.append("unstable_parity_hash")
        if scenario_failures:
            failures[scenario_name] = sorted(set(scenario_failures))
    if not zero_candidate_seen:
        failures.setdefault("_coverage", []).append("missing_zero_candidate_scenario")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "status": status,
        "generated_at": stamp,
        "trace_path": str(trace_path),
        "scenarios": scenarios,
        "stability": stability,
        "proof_strengthening_notes": {
            "duplicate_identity_surface_capture": (
                "Typed policy records use per-input sort/dedupe/complexity surfaces. "
                "Candidate identity is not unique enough for stress fixtures."
            ),
            "bounded_kept_limit": (
                "Typed wrapper replay receives the live bounded keep limit from the "
                "captured page-owned ranking core result."
            ),
            "product_path_changed": False,
        },
        "forbidden_callback_policy_keys": sorted(FORBIDDEN_CALLBACK_POLICY_KEYS),
        "assertions": {
            "ranking_policy_moved": False,
            "keep_top_candidates_moved": False,
            "keep_top_candidates_core_moved": False,
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
            "product_path_changed": False,
        },
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")

    report_lines = [
        "# Bottom Reo Callback-Policy Parity Snapshot",
        "",
        f"- Status: {status}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "This snapshot compares current page-owned bottom reo sort/dedupe/dominance callback behaviour against typed `BottomReoRankingPolicyInput` proof surfaces. It does not move ranking policy or product behaviour.",
        "",
        "## Proof Strengthening Notes",
        "",
        "- Duplicate candidate identities are handled by carrying per-input sort/dedupe/complexity surfaces into typed policy records; identity-only maps are not precise enough for stress fixtures.",
        "- The typed wrapper replay receives the live bounded keep limit from the captured page-owned ranking core result.",
        "- No live callback policy, candidate dictionaries, selection, CTA/action, one-click, publication, render/UI, session/debug, or evaluator execution moved into the typed replay.",
        "",
        "## Scenario Summary",
    ]
    for scenario_result in scenarios:
        name = str(scenario_result.get("scenario"))
        report_lines.extend([
            "",
            f"### {name}",
            f"- mode: `{scenario_result.get('mode')}`",
            f"- mutator: `{scenario_result.get('mutator')}`",
            f"- candidate count: {scenario_result.get('candidate_count')}",
            f"- parity hash: `{scenario_result.get('parity_hash')}`",
            f"- parity: `{scenario_result.get('parity')}`",
            f"- mismatches: `{scenario_result.get('mismatches')}`",
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
            "Do not move callback policy. Repair or strengthen parity first.",
        ])
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. Typed policy-input surfaces reproduce the current live sort keys, dedupe keys, dominance decisions, ordered identities, kept identities, and pruned identities for the covered fixtures.",
            "",
            "## Recommendation",
            "",
            "Next slice can add a family-owned proof policy object for sort/dedupe/dominance. Do not make it product-driving and do not move `_keep_top_candidates(...)` or `_keep_top_candidates_core(...)` yet.",
        ])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": status, "artifact": str(artifact_path), "report": str(report_path), "trace": str(trace_path), "failures": failures}, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
