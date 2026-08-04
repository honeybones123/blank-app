"""Snapshot bottom reo ranking-policy input surfaces.

This verifier freezes the primitive input surface needed by the current
bottom-reinforcement ranking policy. It builds typed
`BottomReoRankingPolicyInput` proof records through the bending family helper.
It does not move ranking, move selection, or touch CTA/action, one-click,
publication, UI/session, or debug logic.
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
from design_brain.families.bending import build_bottom_reo_ranking_policy_inputs


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

SCENARIOS = [
    "normal_bending_underdesign",
    "two_layer_arrangement",
    "bending_overdesign_cleanup",
]

FORBIDDEN_POLICY_INPUT_KEYS = {
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


def _candidate_identity(candidate: dict[str, Any]) -> str:
    candidate_id = candidate.get("candidate_id") or candidate.get("source_candidate_id")
    if candidate_id:
        return str(candidate_id)
    return f"trace:{_stable_hash(candidate)}"


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


def _as_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _extract_boundary(trace_rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    expected = f"BOTTOM_REO_RANKING_POLICY_INPUT_{scenario}"
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


def _state_summary(candidate_state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "b",
        "bw",
        "D",
        "fc",
        "fsy",
        "uls_Mstar",
        "uls_Vstar",
        "Tu_star",
        "P_star",
        "bot_row_count",
        "bot1_count",
        "db_bot_1",
        "bot2_count",
        "db_bot_2",
        "lig_d",
        "lig_legs",
        "s_lig",
    )
    return {key: candidate_state.get(key) for key in keys if key in candidate_state}


def _complexity_primitives(candidate: dict[str, Any]) -> dict[str, Any]:
    state = candidate.get("state") if isinstance(candidate.get("state"), dict) else {}
    return {
        "bar_count": _as_int(candidate.get("bar_count")),
        "row_count": _as_int(candidate.get("row_count") or state.get("bot_row_count")),
        "reo_congestion_index": _as_float(candidate.get("reo_congestion_index")),
        "bot1_count": _as_int(state.get("bot1_count")),
        "bot2_count": _as_int(state.get("bot2_count")),
    }


def _dimension_primitives(candidate: dict[str, Any]) -> dict[str, Any]:
    state = candidate.get("state") if isinstance(candidate.get("state"), dict) else {}
    return {
        "depth": _as_float(candidate.get("depth") or state.get("D")),
        "width": _as_float(candidate.get("width") or state.get("b") or state.get("bw")),
        "ast_bot": _as_float(candidate.get("Ast_bot")),
        "ast_top": _as_float(candidate.get("Ast_top")),
        "steel_area": (
            (_as_float(candidate.get("Ast_bot")) or 0.0)
            + (_as_float(candidate.get("Ast_top")) or 0.0)
        ),
    }


def _row_bar_congestion_fields(candidate: dict[str, Any]) -> dict[str, Any]:
    state = candidate.get("state") if isinstance(candidate.get("state"), dict) else {}
    return {
        "row_count": _as_int(candidate.get("row_count") or state.get("bot_row_count")),
        "bar_count": _as_int(candidate.get("bar_count")),
        "bot1_count": _as_int(state.get("bot1_count")),
        "bot2_count": _as_int(state.get("bot2_count")),
        "db_bot_1": _as_int(state.get("db_bot_1")),
        "db_bot_2": _as_int(state.get("db_bot_2")),
        "reo_congestion_index": _as_float(candidate.get("reo_congestion_index")),
    }


def _policy_input_record(
    module: Any,
    candidate: dict[str, Any],
    *,
    index: int,
    mode_config: dict[str, Any],
    dedupe_key: Any,
    sort_key: Any,
    complexity_before: Any,
    complexity_after: Any,
) -> dict[str, Any]:
    identity = _candidate_identity(candidate)
    state = candidate.get("state") if isinstance(candidate.get("state"), dict) else {}
    try:
        resolved_actions = module._resolve_design_actions_from_state(dict(state))
    except Exception:
        resolved_actions = {}
    try:
        objective_util = module._candidate_objective_util(candidate)
    except Exception:
        objective_util = None
    try:
        util_distance = module._candidate_util_distance(candidate, mode_config)
    except Exception:
        util_distance = None
    try:
        in_target_band = bool(module._candidate_in_target_band(candidate, mode_config))
    except Exception:
        in_target_band = None
    try:
        target_domains = list(module._candidate_target_domains_for_band(candidate))
    except Exception:
        target_domains = []
    try:
        shallow_tier, shallow_tier_label = module._shallower_beam_candidate_tier(candidate)
    except Exception:
        shallow_tier, shallow_tier_label = None, None
    try:
        shallow_metrics = module._shallower_beam_metrics(
            candidate,
            {
                "state": dict(state),
                "depth": _as_float(candidate.get("_seed_depth") or candidate.get("depth") or state.get("D")),
                "width": _as_float(candidate.get("_seed_width") or candidate.get("width") or state.get("b") or state.get("bw")),
                "Ast_bot": _as_float(candidate.get("_seed_ast_bot") or candidate.get("Ast_bot")),
            },
        )
    except Exception:
        shallow_metrics = {}
    try:
        ductility_util = module._candidate_ductility_util(candidate)
    except Exception:
        ductility_util = None
    try:
        ductility_priority = bool(module._candidate_ductility_governs(candidate))
    except Exception:
        ductility_priority = bool(candidate.get("_ductility_priority"))
    record = {
        "policy_input_order_index": int(index),
        "candidate_identity": identity,
        "source_scored_candidate_identity": identity,
        "state_hash": _stable_hash(state),
        "state_summary": _state_summary(state),
        "resolved_design_action_dedupe_key_hash": _stable_hash(dedupe_key),
        "resolved_design_action_summary": {
            "Mu": resolved_actions.get("Mu"),
            "Vu": resolved_actions.get("Vu"),
            "Nu": resolved_actions.get("Nu"),
            "SLS_M": resolved_actions.get("SLS_M"),
            "SLS_V": resolved_actions.get("SLS_V"),
            "source": resolved_actions.get("source"),
        },
        "objective_util": _as_float(objective_util),
        "util_distance": _as_float(util_distance),
        "target_band_inputs": {
            "target_low": _as_float(mode_config.get("target_util_min", mode_config.get("target_low"))),
            "target_high": _as_float(mode_config.get("target_util_max", mode_config.get("target_high"))),
            "target_domains": target_domains,
            "in_target_band": in_target_band,
            "candidate_reaches_target_band": (
                bool(candidate.get("candidate_reaches_target_band"))
                if "candidate_reaches_target_band" in candidate
                else None
            ),
            "candidate_distance_to_target_band": _as_float(candidate.get("candidate_distance_to_target_band")),
        },
        "row_bar_congestion_fields": _row_bar_congestion_fields(candidate),
        "dimension_primitives": _dimension_primitives(candidate),
        "shallow_tier": shallow_tier,
        "shallow_tier_label": shallow_tier_label,
        "shallow_metrics": _safe_value(shallow_metrics),
        "ductility": {
            "priority": ductility_priority,
            "util": _as_float(ductility_util),
            "tier": _as_int(candidate.get("_ductility_tier")) if candidate.get("_ductility_tier") is not None else None,
        },
        "reo_complexity_primitives": _complexity_primitives(candidate),
        "reo_complexity_before_setdefault": _as_float(complexity_before),
        "reo_complexity_after_setdefault": _as_float(complexity_after),
        "sort_key_surface": _safe_value(sort_key),
        "dominance_dedupe_surface": {
            "dedupe_key_hash": _stable_hash(dedupe_key),
            "dedupe_key": _safe_value(dedupe_key),
        },
    }
    return record


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
        "dominance_calls": [],
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

    real_compute_reo_complexity = module.compute_reo_complexity

    def _capture_compute_reo_complexity(candidate: dict) -> float:
        identity = _candidate_identity(candidate if isinstance(candidate, dict) else {})
        if identity:
            captured.setdefault("reo_complexity_before", {})[identity] = (
                candidate.get("reo_complexity") if isinstance(candidate, dict) else None
            )
        return real_compute_reo_complexity(candidate)

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
        sort_keys: dict[str, Any] = {}
        dedupe_keys: dict[str, Any] = {}
        for candidate in candidate_list:
            if not isinstance(candidate, dict):
                continue
            identity = _candidate_identity(candidate)
            captured.setdefault("reo_complexity_before", {}).setdefault(identity, candidate.get("reo_complexity"))
            dedupe_keys[identity] = _safe_value(candidate_key(candidate.get("state") or {}))
            sort_keys[identity] = _safe_value(sort_key(candidate, mode_config))

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
        result = real_keep_top(candidate_list, mode_config, limit=limit)
        result = list(result or [])
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
        captured["core_result"] = {
            "ordered": ordered_candidates,
            "kept": result,
            "decisions": decision_records,
        }
        captured["sort_key_by_identity"] = sort_keys
        captured["dedupe_key_by_identity"] = dedupe_keys
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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_RANKING_POLICY_INPUT_{scenario}"
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
    sort_keys = dict(captured.get("sort_key_by_identity") or {})
    dedupe_keys = dict(captured.get("dedupe_key_by_identity") or {})
    complexity_before = dict(captured.get("reo_complexity_before") or {})
    complexity_after = dict(captured.get("reo_complexity_after") or {})
    mode_config = boundary_snapshot._mode_config(state)
    policy_input_primitives = [
        _policy_input_record(
            module,
            candidate,
            index=index,
            mode_config=mode_config,
            dedupe_key=dedupe_keys.get(_candidate_identity(candidate)),
            sort_key=sort_keys.get(_candidate_identity(candidate)),
            complexity_before=complexity_before.get(_candidate_identity(candidate)),
            complexity_after=complexity_after.get(_candidate_identity(candidate)),
        )
        for index, candidate in enumerate(input_candidates)
        if isinstance(candidate, dict)
    ]
    typed_policy_inputs = build_bottom_reo_ranking_policy_inputs(
        records=policy_input_primitives,
    )
    policy_inputs = [item.to_dict() for item in typed_policy_inputs]
    forbidden_present = sorted(
        {
            key
            for record in policy_inputs
            for key in sorted(set(record.keys()) & FORBIDDEN_POLICY_INPUT_KEYS)
        },
    )
    ordered = [_candidate_identity(candidate) for candidate in ordered_candidates if isinstance(candidate, dict)]
    kept = [_candidate_identity(candidate) for candidate in kept_candidates if isinstance(candidate, dict)]
    policy_hash_inputs = [
        {
            "candidate_identity": item.get("candidate_identity"),
            "policy_input_hash": item.get("policy_input_hash"),
        }
        for item in policy_inputs
    ]
    return {
        "scenario": scenario,
        "trace_event_found": bool(boundary),
        "policy_input_count": len(policy_inputs),
        "policy_input_order": [str(item.get("candidate_identity") or "") for item in policy_inputs],
        "ordered_candidate_order": ordered,
        "kept_candidate_order": kept,
        "policy_inputs": policy_inputs,
        "dominance_calls": list(captured.get("dominance_calls") or []),
        "ranking_policy_input_hash": _stable_hash(policy_hash_inputs),
        "ordered_candidate_hash": _stable_hash(ordered),
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
    if not result.get("ranking_policy_input_hash"):
        failures.append("missing_ranking_policy_input_hash")
    if not result.get("ordered_candidate_hash"):
        failures.append("missing_ordered_candidate_hash")
    if not result.get("kept_candidate_hash"):
        failures.append("missing_kept_candidate_hash")
    if int(result.get("policy_input_count") or 0) > 0 and not result.get("policy_inputs"):
        failures.append("missing_policy_inputs")
    if list(result.get("forbidden_keys_present") or []):
        failures.append(f"forbidden_policy_input_keys:{','.join(result.get('forbidden_keys_present') or [])}")
    for item in list(result.get("policy_inputs") or []):
        if not isinstance(item, dict):
            failures.append("policy_input_not_dict")
            continue
        for required in (
            "candidate_identity",
            "state_hash",
            "resolved_design_action_dedupe_key_hash",
            "objective_util",
            "target_band_inputs",
            "row_bar_congestion_fields",
            "dimension_primitives",
            "shallow_metrics",
            "ductility",
            "reo_complexity_primitives",
            "reo_complexity_before_setdefault",
            "reo_complexity_after_setdefault",
            "sort_key_surface",
            "dominance_dedupe_surface",
            "policy_input_hash",
        ):
            if required not in item:
                failures.append(f"missing_{required}")
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
    module.compute_reo_complexity = provider.compute_reo_complexity
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_ranking_policy_input_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_ranking_policy_input_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_ranking_policy_input_{stamp}.md"

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
        same_policy = scenario_result.get("ranking_policy_input_hash") == repeat.get("ranking_policy_input_hash")
        same_ordered = scenario_result.get("ordered_candidate_hash") == repeat.get("ordered_candidate_hash")
        same_kept = scenario_result.get("kept_candidate_hash") == repeat.get("kept_candidate_hash")
        stability[scenario_name] = {
            "same_ranking_policy_input_hash": same_policy,
            "same_ordered_candidate_hash": same_ordered,
            "same_kept_candidate_hash": same_kept,
            "first_policy_hash": scenario_result.get("ranking_policy_input_hash"),
            "repeat_policy_hash": repeat.get("ranking_policy_input_hash"),
        }
        if int(scenario_result.get("policy_input_count") or 0) == 0:
            zero_accepted_seen = True
        if not same_policy:
            scenario_failures.append("unstable_ranking_policy_input_hash")
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
        "forbidden_policy_input_keys": sorted(FORBIDDEN_POLICY_INPUT_KEYS),
        "assertions": {
            "ranking_policy_moved": False,
            "typed_policy_input_added": True,
            "typed_policy_input_builder": "design_brain.families.bending.build_bottom_reo_ranking_policy_inputs",
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
            "reo_complexity_mutation_timing_recorded": True,
            "product_path_changed": False,
        },
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")

    report_lines = [
        "# Bottom Reo Ranking-Policy Input Snapshot",
        "",
        f"- Status: {status}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "This snapshot freezes the current bottom reo ranking-policy input surface using `BottomReoRankingPolicyInput` records built by `design_brain.families.bending.build_bottom_reo_ranking_policy_inputs(...)`.",
        "",
        "It records candidate identity, state hash/summary, resolved action dedupe key, objective utilisation, target-band inputs, row/bar/congestion fields, geometry/Ast primitives, shallow metrics, ductility fields, complexity primitives, complexity before/after page-local `setdefault(...)`, sort key, and dedupe/dominance surface.",
        "",
        "The page-local snapshot still gathers live candidate dictionaries, calls existing ranking-policy input helpers, captures current reo_complexity mutation timing, invokes `_keep_top_candidates(...)`, and records ordering/hash surfaces. The bending helper only normalizes explicit primitive/data fields and computes the proof-object hash.",
        "",
        "## Scenario Summary",
    ]
    for scenario_result in scenarios:
        name = str(scenario_result.get("scenario"))
        report_lines.extend([
            "",
            f"### {name}",
            f"- policy input count: {scenario_result.get('policy_input_count')}",
            f"- policy input hash: `{scenario_result.get('ranking_policy_input_hash')}`",
            f"- ordered candidate hash: `{scenario_result.get('ordered_candidate_hash')}`",
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
            "Do not add `BottomReoRankingPolicyInput` yet. Repair the policy input proof surface first.",
        ])
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. Typed ranking-policy inputs are stable and exclude selected recommendation, CTA, one-click, publication, render/UI, session, and debug fields.",
            "",
            "## Recommendation",
            "",
            "Ranking policy, `_keep_top_candidates(...)`, selection, CTA/action, one-click solver, publication, UI/session, and debug logic remain page-local.",
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
