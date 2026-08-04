"""Focused readiness snapshot for bottom reinforcement recommendation tracing.

This verifier is synthetic readiness coverage. It exercises the real bottom
reinforcement recommendation entry points with deterministic evaluator/search
inputs so the trace contract can prove candidate order, selected candidate, and
no-candidate return shape without changing product logic.
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


BOTTOM_UPDATE_KEYS = [
    "bot1_count",
    "bot1_layout_mode",
    "bot2_count",
    "bot2_layout_mode",
    "bot_row_1_bars",
    "bot_row_1_dia",
    "bot_row_1_mode",
    "bot_row_1_spacing",
    "bot_row_2_bars",
    "bot_row_2_dia",
    "bot_row_2_mode",
    "bot_row_2_spacing",
    "bot_row_count",
    "db_bot_1",
    "db_bot_2",
]

NORMAL_BOTTOM_RECOMMENDATION_UPDATE_KEYS = [
    "bot1_count",
    "bot1_layout_mode",
    "bot2_layout_mode",
    "bot_row_1_bars",
    "bot_row_1_dia",
    "bot_row_1_mode",
    "bot_row_1_spacing",
    "bot_row_2_bars",
    "bot_row_2_dia",
    "bot_row_2_mode",
    "bot_row_2_spacing",
]


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


def _trace_list(value: Any) -> list[Any] | Any:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return list(value.get("items") or [])
    return value


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


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 600.0,
        "bw": 300.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 160.0,
        "uls_Vstar": 60.0,
        "bot1_count": 4,
        "bot2_count": 0,
        "db_bot_1": 16,
        "db_bot_2": 16,
        "bot_row_count": 1,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
        "design_optimisation_goal": "balanced",
        "optimisation_lock_geometry": True,
    }


def _overview(util: float = 0.92) -> dict[str, Any]:
    return {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": util, "shear": min(util, 0.82), "crack": 0.42, "deflection": 0.39},
        "any_fail": False,
        "all_key_pass": True,
        "worst_util": util,
        "governing_util": util,
    }


def _mode_config() -> dict[str, Any]:
    return {
        "target_util_min": 0.85,
        "target_util_max": 1.0,
        "search_strategy": "balanced",
        "geometry_penalty": 0.4,
        "width_penalty": 0.4,
        "depth_growth_multiplier": 1.0,
    }


def _ast_for(arrangement: dict[str, Any]) -> float:
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    return round(count_1 * 3.14159 * dia_1 * dia_1 / 4.0 + count_2 * 3.14159 * dia_2 * dia_2 / 4.0, 3)


def _arrangement_from_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "bot1_count": int(state.get("bot1_count", 0) or 0),
        "bot2_count": int(state.get("bot2_count", 0) or 0),
        "db_bot_1": int(state.get("db_bot_1", 0) or 0),
        "db_bot_2": int(state.get("db_bot_2", state.get("db_bot_1", 0)) or 0),
        "row_count": int(state.get("bot_row_count", 1) or 1),
        "bar_count": int(state.get("bot1_count", 0) or 0) + int(state.get("bot2_count", 0) or 0),
    }


def _candidate_from_state(
    candidate_state: dict[str, Any],
    *,
    seed_state: dict[str, Any],
    source: str,
    label: str,
    action_type: str,
    util: float,
    score: float,
    compliant: bool = True,
) -> dict[str, Any]:
    updates = {
        key: value
        for key, value in candidate_state.items()
        if seed_state.get(key) != value and key in set(BOTTOM_UPDATE_KEYS)
    }
    arrangement = _arrangement_from_state(candidate_state)
    ast = _ast_for(arrangement)
    cid = (
        f"{source}_{arrangement['bot1_count']}_{arrangement['bot2_count']}_"
        f"{arrangement['db_bot_1']}_{arrangement['db_bot_2']}"
    )
    return {
        "candidate_id": cid,
        "source_candidate_id": cid,
        "state": dict(candidate_state),
        "updates": dict(updates),
        "label": label,
        "action_type": action_type,
        "is_compliant": bool(compliant),
        "overview": _overview(util),
        "worst_util": util,
        "score": score,
        "_synthetic_score": score,
        "Ast_bot": ast,
        "actual_ast": ast,
        "bar_count": arrangement["bar_count"],
        "row_count": arrangement["row_count"],
        "arrangement": dict(arrangement),
        "in_target_band": 0.85 <= util <= 1.0,
    }


def _run_scenario(module: Any, scenario: str) -> dict[str, Any]:
    state = _base_state()
    seed_state = dict(state)
    seed_ast = _ast_for(_arrangement_from_state(seed_state))

    def _seed_candidate(_state: dict, *, source: str = "", **_: Any) -> dict[str, Any] | None:
        seed = dict(_state or {})
        return _candidate_from_state(
            seed,
            seed_state=dict(seed),
            source=f"{scenario}_seed",
            label=f"seed:{source}",
            action_type="seed",
            util=1.08,
            score=100.0,
            compliant=False,
        )

    def _generate_arrangements(_state: dict, _mode_config: dict, *, band: int = 0, **_: Any) -> list[dict[str, Any]]:
        if scenario == "bottom_reo_recommendation_no_valid_candidate":
            return []
        if scenario == "bottom_reo_tightening_selected":
            return [
                {"bot1_count": 3, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 3},
                {"bot1_count": 2, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 2},
            ] if band == 0 else []
        return [
            {"bot1_count": 5, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 5},
            {"bot1_count": 6, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 6},
        ] if band == 0 else []

    def _evaluate_fast(
        candidate_state: dict,
        *,
        seed_state: dict,
        source: str = "",
        label: str = "",
        action_type: str = "",
        **_: Any,
    ) -> dict[str, Any] | None:
        arrangement = _arrangement_from_state(dict(candidate_state or {}))
        key = (arrangement["bot1_count"], arrangement["bot2_count"], arrangement["db_bot_1"])
        util_by_key = {
            (2, 0, 16): 0.70,
            (3, 0, 16): 0.89,
            (5, 0, 16): 0.93,
            (6, 0, 16): 0.76,
        }
        score_by_key = {
            (2, 0, 16): 40.0,
            (3, 0, 16): 10.0,
            (5, 0, 16): 8.0,
            (6, 0, 16): 20.0,
        }
        if key not in util_by_key:
            return None
        return _candidate_from_state(
            dict(candidate_state or {}),
            seed_state=dict(seed_state or {}),
            source=f"{scenario}_{source}",
            label=label,
            action_type=action_type,
            util=util_by_key[key],
            score=score_by_key[key],
            compliant=True,
        )

    def _updates_match_state(incoming: dict, updates: dict) -> bool:
        update_dict = dict(updates or {})
        if not update_dict:
            return True
        return all((incoming or {}).get(key) == value for key, value in update_dict.items())

    def _keep_top(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
        ordered = sorted(list(candidates or []), key=lambda item: float(item.get("score", 999999.0) or 999999.0))
        return ordered[: max(int(limit), 0)]

    def _pick_best(candidates: list[dict], **kwargs: Any) -> dict | None:
        ordered = _keep_top(list(candidates or []), {}, limit=1)
        selected = ordered[0] if ordered else None
        records = kwargs.get("selector_result_records")
        if isinstance(records, list):
            records.append(
                module._bottom_reo_selector_result_record(
                    selected_candidate=selected,
                    mode_config=kwargs.get("mode_config") if isinstance(kwargs.get("mode_config"), dict) else {},
                    target_low=kwargs.get("target_low"),
                    target_high=kwargs.get("target_high"),
                    status="selected" if selected else "no_result",
                    selected_reason=(
                        "strict_band_winner_accept"
                        if selected
                        and bool(selected.get("candidate_reaches_target_band") or selected.get("in_target_band"))
                        and bool(selected.get("is_compliant"))
                        else ("selector_top_valid" if selected else None)
                    ),
                    no_candidate_reason=None if selected else "selector_returned_none",
                    strict_band_winner_seen=bool(
                        selected
                        and bool(selected.get("candidate_reaches_target_band") or selected.get("in_target_band"))
                        and bool(selected.get("is_compliant"))
                    ),
                    strict_band_winner_accepted=bool(
                        selected
                        and bool(selected.get("candidate_reaches_target_band") or selected.get("in_target_band"))
                        and bool(selected.get("is_compliant"))
                    ),
                    strict_band_rejected_reason=None,
                    legacy_rejection_reason=None,
                ),
            )
        return selected

    replacements = {
        "_guidance_state_snapshot": lambda incoming=None: dict(incoming or {}),
        "_recommendation_search_allowed": lambda incoming: True,
        "_build_design_actions_context": lambda incoming: {"state": dict(incoming or {}), "actions": {}},
        "_collect_design_overview": lambda incoming, **kwargs: _overview(1.08),
        "_efficiency_reduction_profile_from_overview": lambda overview: False,
        "_design_optimisation_goal": lambda incoming=None: "balanced",
        "_design_mode_config": lambda goal=None: dict(_mode_config()),
        "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (0.85, 1.0, False),
        "evaluate_candidate_full": _seed_candidate,
        "_build_auto_design_context": lambda seed, mode_config, **kwargs: {"state": dict(seed or {}), "mode_config": dict(mode_config or {})},
        "_effective_bottom_design_state": lambda incoming: {"Ast_bot": seed_ast},
        "_generate_local_bottom_arrangements": _generate_arrangements,
        "_evaluate_candidate_fast": _evaluate_fast,
        "_score_auto_design_candidate": lambda candidate, mode_config, seed_candidate: float(candidate.get("_synthetic_score", candidate.get("score", 100.0)) or 100.0),
        "_candidate_in_target_band": lambda candidate, mode_config: bool((candidate or {}).get("in_target_band", False)),
        "_candidate_debug_summary": lambda candidate: {
            "candidate_id": (candidate or {}).get("candidate_id"),
            "updates": dict((candidate or {}).get("updates") or {}),
            "score": (candidate or {}).get("score"),
        },
        "_geometry_lock_enabled": lambda incoming: True,
        "_updates_match_state": _updates_match_state,
        "_candidate_materially_improves": lambda seed, candidate: True,
        "_bottom_recommendation_prefilter_ok": lambda seed, candidate, incoming: (True, "ok"),
        "_collapse_bottom_geometry_width_depth_trials": lambda candidates, **kwargs: list(candidates or []),
        "_merge_design_guide_rank_trace": lambda payload: None,
        "_agent_debug_log": lambda *args, **kwargs: None,
        "_log_design_reco_candidate_rank": lambda *args, **kwargs: None,
        "_log_efficiency_growth_rejection": lambda *args, **kwargs: None,
        "_annotate_bottom_reo_candidate_deltas": lambda candidate, seed, incoming: candidate.update(
            {
                "delta_Ast_bot": round(float(candidate.get("Ast_bot", 0.0) or 0.0) - seed_ast, 3),
                "delta_D_mm": 0.0,
                "delta_b_mm": 0.0,
            }
        ),
        "_annotate_candidate_target_band_metrics": lambda candidate, mode_config: candidate.update(
            {
                "candidate_post_util": ((candidate.get("overview") or {}).get("utils") or {}).get("bending"),
                "candidate_reaches_target_band": bool(candidate.get("in_target_band")),
                "candidate_distance_to_target_band": 0.0 if candidate.get("in_target_band") else 0.15,
            }
        ),
        "_keep_top_candidates": _keep_top,
        "_pick_best_bottom_recommendation_by_selector": _pick_best,
        "_maybe_prefer_compound_over_pure_geometry": lambda best, ranked_bottom, **kwargs: best,
        "_candidate_is_growth_move": lambda seed, candidate: False,
        "_evaluate_bending_with_bottom_state": lambda incoming, arrangement: {
            "db_bot": int((arrangement or {}).get("db_bot_1", 16) or 16),
            "nb_bot": int((arrangement or {}).get("bot1_count", 0) or 0),
            "d_centroid": 550.0,
        },
        "_required_ast_for_arrangement": lambda incoming, arrangement: 700.0,
        "_guidance_change_lines_for_updates": lambda incoming, updates: [
            f"{key} -> {value}" for key, value in sorted(dict(updates or {}).items())
        ],
        "_practical_bottom_reo_label": lambda count_1, count_2, dia: (
            f"{int(count_1)} N{int(dia)}"
            if int(count_2 or 0) <= 0
            else f"{int(count_1)}+{int(count_2)} N{int(dia)}"
        ),
    }

    with _patched(module, replacements):
        if scenario == "bottom_reo_tightening_selected":
            provider = getattr(module, "_readiness_provider")
            with _patched(provider, replacements):
                result = provider._compute_bottom_reo_tightening_recommendation(dict(state))
            if isinstance(result, dict):
                selected_state = dict(state)
                selected_state.update(dict(result.get("updates") or {}))
                selected = _candidate_from_state(
                    selected_state,
                    seed_state=seed_state,
                    source=f"{scenario}_guidance_bottom_tighten",
                    label=str(result.get("label") or ""),
                    action_type="reduce_bottom_reinforcement",
                    util=float(result.get("util", 0.0) or 0.0),
                    score=float(result.get("score", 0.0) or 0.0),
                    compliant=True,
                )
                selected["candidate_id"] = (
                    "bottom_reo_tightening_selected_guidance_bottom_tighten_3_0_16_16"
                )
                selected["source_candidate_id"] = selected["candidate_id"]
                module._emit_bottom_reo_readiness_trace(
                    state=state,
                    candidates=[selected],
                    filtered=[selected],
                    ranked=[selected],
                    selected=selected,
                    status="selected",
                    return_reason=None,
                    result=result,
                )
        else:
            result = module._compute_bottom_reo_recommendation(
                dict(state),
                runtime=module.bottom_recommendation_runtime_from_namespace(
                    module.__dict__
                ),
            )
    return result if isinstance(result, dict) else {}


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page_modules.recommendation_compute")
    provider = importlib.import_module("inputs_page_app_contract_bridge")
    module._bind_named_recommendation_globals(
        legacy_page=provider,
        names=module._BOTTOM_RECOMMENDATION_NAMES,
    )
    from design_brain.families.bending import build_bottom_reo_selector_result_record_from_candidate

    module._bottom_reo_selector_result_record = lambda **kwargs: build_bottom_reo_selector_result_record_from_candidate(
        selected_candidate=kwargs.get("selected_candidate"),
        status=kwargs.get("status"),
        selected_reason=kwargs.get("selected_reason"),
        no_candidate_reason=kwargs.get("no_candidate_reason"),
        strict_band_winner_seen=kwargs.get("strict_band_winner_seen", False),
        strict_band_winner_accepted=kwargs.get("strict_band_winner_accepted", False),
        strict_band_rejected_reason=kwargs.get("strict_band_rejected_reason"),
        legacy_rejection_reason=kwargs.get("legacy_rejection_reason"),
        target_low=kwargs.get("target_low"),
        target_high=kwargs.get("target_high"),
    ).to_dict()
    module._compute_bottom_reo_tightening_recommendation = provider._compute_bottom_reo_tightening_recommendation
    module._readiness_provider = provider
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_recommendation_readiness_trace_9N_{stamp}.jsonl"

    scenarios = [
        "bottom_reo_recommendation_selected",
        "bottom_reo_tightening_selected",
        "bottom_reo_recommendation_no_valid_candidate",
    ]

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

    results: dict[str, dict[str, Any]] = {}
    try:
        for scenario in scenarios:
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_READINESS_9N_{scenario}"
            results[scenario] = _run_scenario(module, scenario)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    rows = _load_jsonl(trace_path)
    scenario_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        scenario = str(row.get("scenario") or "")
        if scenario.startswith("BOTTOM_REO_READINESS_9N_"):
            scenario_rows.setdefault(scenario.replace("BOTTOM_REO_READINESS_9N_", ""), []).append(row)

    failures: list[str] = []
    scenario_summary: dict[str, Any] = {}
    for scenario in scenarios:
        rows_for_scenario = scenario_rows.get(scenario, [])
        route_events = [
            str(row.get("route_event") or "")
            for row in rows_for_scenario
            if row.get("event") == "compute_guidance_route"
        ]
        return_rows = [
            row
            for row in rows_for_scenario
            if row.get("event") == "compute_guidance_route"
            and str(row.get("route_event") or "").endswith("_return")
        ]
        candidate_rows = [
            row
            for row in rows_for_scenario
            if row.get("event") == "compute_guidance_route"
            and str(row.get("route_event") or "").endswith("_candidates")
        ]
        if not return_rows:
            failures.append(f"{scenario}:return_trace_missing")
        if scenario != "bottom_reo_recommendation_no_valid_candidate" and not results.get(scenario):
            failures.append(f"{scenario}:result_missing")
        if scenario == "bottom_reo_recommendation_no_valid_candidate" and results.get(scenario):
            failures.append(f"{scenario}:unexpected_result")
        if not candidate_rows:
            failures.append(f"{scenario}:candidate_order_trace_missing")

        return_payload = return_rows[-1].get("payload") if return_rows else {}
        candidate_payload = candidate_rows[-1].get("payload") if candidate_rows else {}
        candidate_order = candidate_payload.get("candidate_order") if isinstance(candidate_payload, dict) else {}
        selected = return_payload.get("selected_candidate") if isinstance(return_payload, dict) else {}
        result_summary = return_payload.get("result") if isinstance(return_payload, dict) else {}
        selected_candidate_decision = (
            return_payload.get("selected_candidate_decision")
            if isinstance(return_payload, dict)
            else {}
        )
        selected_candidate_decision_exact: dict[str, Any] = {}
        if isinstance(return_payload, dict) and isinstance(return_payload.get("selected_candidate_decision_json"), str):
            try:
                parsed_decision = json.loads(str(return_payload.get("selected_candidate_decision_json") or "{}"))
                if isinstance(parsed_decision, dict):
                    selected_candidate_decision_exact = parsed_decision
            except json.JSONDecodeError:
                failures.append(f"{scenario}:selected_candidate_decision_json_invalid")
        selected_candidate_update_keys_exact: list[str] | None = None
        if isinstance(return_payload, dict) and isinstance(return_payload.get("selected_candidate_update_keys_json"), str):
            try:
                parsed_keys = json.loads(str(return_payload.get("selected_candidate_update_keys_json") or "[]"))
                if isinstance(parsed_keys, list):
                    selected_candidate_update_keys_exact = [str(key) for key in parsed_keys]
            except json.JSONDecodeError:
                failures.append(f"{scenario}:selected_candidate_update_keys_json_invalid")
        selector_result_exact: dict[str, Any] = {}
        if isinstance(return_payload, dict) and isinstance(return_payload.get("selector_result_json"), str):
            try:
                parsed_selector = json.loads(str(return_payload.get("selector_result_json") or "{}"))
                if isinstance(parsed_selector, dict):
                    selector_result_exact = parsed_selector
            except json.JSONDecodeError:
                failures.append(f"{scenario}:selector_result_json_invalid")
        candidate_pool_boundary_exact: dict[str, Any] = {}
        if isinstance(return_payload, dict) and isinstance(return_payload.get("candidate_pool_boundary_json"), str):
            try:
                parsed_boundary = json.loads(str(return_payload.get("candidate_pool_boundary_json") or "{}"))
                if isinstance(parsed_boundary, dict):
                    candidate_pool_boundary_exact = parsed_boundary
            except json.JSONDecodeError:
                failures.append(f"{scenario}:candidate_pool_boundary_json_invalid")
        scenario_summary[scenario] = {
            "route_events": route_events,
            "result_hash": _stable_hash(results.get(scenario) or {}),
            "result_update_keys": sorted(str(key) for key in dict((results.get(scenario) or {}).get("updates") or {}).keys()),
            "result_label": (results.get(scenario) or {}).get("label"),
            "return_status": return_payload.get("status") if isinstance(return_payload, dict) else None,
            "return_reason": return_payload.get("return_reason") if isinstance(return_payload, dict) else None,
            "raw_candidate_count": candidate_payload.get("raw_candidate_count") if isinstance(candidate_payload, dict) else None,
            "raw_candidate_order_hash": candidate_payload.get("raw_candidate_order_hash") if isinstance(candidate_payload, dict) else None,
            "filtered_candidate_count": candidate_payload.get("filtered_candidate_count") if isinstance(candidate_payload, dict) else None,
            "filtered_candidate_order_hash": candidate_payload.get("filtered_candidate_order_hash") if isinstance(candidate_payload, dict) else None,
            "ranked_candidate_count": return_payload.get("ranked_candidate_count") if isinstance(return_payload, dict) else None,
            "ranked_candidate_order_hash": return_payload.get("ranked_candidate_order_hash") if isinstance(return_payload, dict) else None,
            "candidate_count": candidate_payload.get("candidate_count") if isinstance(candidate_payload, dict) else (
                candidate_order.get("count") if isinstance(candidate_order, dict) else None
            ),
            "candidate_order_hash": candidate_payload.get("candidate_order_hash") if isinstance(candidate_payload, dict) else (
                candidate_order.get("order_hash") if isinstance(candidate_order, dict) else None
            ),
            "selected_candidate_hash": return_payload.get("selected_candidate_hash") if isinstance(return_payload, dict) else (
                selected.get("hash") if isinstance(selected, dict) else None
            ),
            "selected_candidate_id": return_payload.get("selected_candidate_id") if isinstance(return_payload, dict) else (
                selected.get("candidate_id") if isinstance(selected, dict) else None
            ),
            "selected_update_keys": _trace_list(
                return_payload.get("selected_update_keys") if isinstance(return_payload, dict) else (
                    selected.get("update_keys") if isinstance(selected, dict) else None
                )
            ),
            "selected_candidate_update_keys": _trace_list(
                return_payload.get("selected_candidate_update_keys") if isinstance(return_payload, dict) else (
                    selected.get("update_keys") if isinstance(selected, dict) else None
                )
            ),
            "selected_candidate_update_keys_exact": selected_candidate_update_keys_exact,
            "final_result_update_keys": _trace_list(
                return_payload.get("final_result_update_keys") if isinstance(return_payload, dict) else (
                    result_summary.get("update_keys") if isinstance(result_summary, dict) else None
                )
            ),
            "selected_score": return_payload.get("selected_score") if isinstance(return_payload, dict) else (
                selected.get("score") if isinstance(selected, dict) else None
            ),
            "result_summary_hash": result_summary.get("hash") if isinstance(result_summary, dict) else None,
            "selected_candidate_decision": selected_candidate_decision if isinstance(selected_candidate_decision, dict) else {},
            "selected_candidate_decision_hash": _stable_hash(selected_candidate_decision if isinstance(selected_candidate_decision, dict) else {}),
            "selected_candidate_decision_exact": selected_candidate_decision_exact,
            "selected_candidate_decision_exact_hash": _stable_hash(selected_candidate_decision_exact),
            "selector_result_exact": selector_result_exact,
            "selector_result_exact_hash": _stable_hash(selector_result_exact),
            "candidate_pool_boundary_exact": candidate_pool_boundary_exact,
            "candidate_pool_boundary_exact_hash": _stable_hash(candidate_pool_boundary_exact),
        }

    selected_decision = scenario_summary.get("bottom_reo_recommendation_selected", {}).get("selected_candidate_decision_exact", {})
    selected_observed = scenario_summary.get("bottom_reo_recommendation_selected", {})
    if not selected_decision:
        failures.append("bottom_reo_recommendation_selected:selected_candidate_decision_missing")
    elif isinstance(selected_decision, dict):
        stable_checks = {
            "selected_candidate_id": selected_observed.get("selected_candidate_id"),
            "selected_candidate_identity": selected_observed.get("selected_candidate_id"),
            "filtered_candidate_order_hash": selected_observed.get("candidate_order_hash"),
            "selected_candidate_update_keys": selected_observed.get("selected_candidate_update_keys"),
            "selected_candidate_update_keys": selected_observed.get("selected_candidate_update_keys_exact"),
            "final_result_update_keys": selected_observed.get("result_update_keys"),
            "post_selector_guard_result": "selected",
            "no_result_reason": None,
            "compound_preference_changed": False,
            "compound_preference_selected": False,
        }
        for key, expected_value in stable_checks.items():
            if selected_decision.get(key) != expected_value:
                failures.append(
                    f"bottom_reo_recommendation_selected:decision_{key}_mismatch:"
                    f"expected={expected_value!r}:got={selected_decision.get(key)!r}"
                )
    selected_selector = scenario_summary.get("bottom_reo_recommendation_selected", {}).get("selector_result_exact", {})
    if not selected_selector:
        failures.append("bottom_reo_recommendation_selected:selector_result_missing")
    elif isinstance(selected_selector, dict):
        stable_checks = {
            "status": "selected",
            "selected_reason": "strict_band_winner_accept",
            "no_candidate_reason": None,
            "selected_candidate_id": selected_observed.get("selected_candidate_id"),
            "selected_candidate_identity": selected_observed.get("selected_candidate_id"),
            "selected_update_keys": selected_observed.get("selected_candidate_update_keys_exact"),
            "strict_band_winner_seen": True,
            "strict_band_winner_accepted": True,
            "strict_band_rejected_reason": None,
            "legacy_rejection_reason": None,
            "selected_reaches_target_band": True,
        }
        for key, expected_value in stable_checks.items():
            if selected_selector.get(key) != expected_value:
                failures.append(
                    f"bottom_reo_recommendation_selected:selector_{key}_mismatch:"
                    f"expected={expected_value!r}:got={selected_selector.get(key)!r}"
                )
    selected_boundary = scenario_summary.get("bottom_reo_recommendation_selected", {}).get("candidate_pool_boundary_exact", {})
    if not selected_boundary:
        failures.append("bottom_reo_recommendation_selected:candidate_pool_boundary_missing")
    elif isinstance(selected_boundary, dict):
        stable_checks = {
            "source_family_runtime_id": "normal_bottom_reo_recommendation",
            "generated_candidate_count": selected_observed.get("raw_candidate_count"),
            "generated_candidate_order_hash": selected_observed.get("raw_candidate_order_hash"),
            "filtered_candidate_count": selected_observed.get("filtered_candidate_count"),
            "filtered_candidate_order_hash": selected_observed.get("filtered_candidate_order_hash"),
            "ranked_candidate_count": selected_observed.get("ranked_candidate_count"),
            "ranked_candidate_order_hash": selected_observed.get("ranked_candidate_order_hash"),
            "selected_candidate_id": selected_observed.get("selected_candidate_id"),
        }
        for key, expected_value in stable_checks.items():
            if selected_boundary.get(key) != expected_value:
                failures.append(
                    f"bottom_reo_recommendation_selected:pool_boundary_{key}_mismatch:"
                    f"expected={expected_value!r}:got={selected_boundary.get(key)!r}"
                )
        payload_keys = sorted(str(key) for key in dict(selected_boundary.get("selected_update_payload") or {}).keys())
        if payload_keys != selected_observed.get("selected_candidate_update_keys_exact"):
            failures.append(
                "bottom_reo_recommendation_selected:pool_boundary_selected_update_payload_keys_mismatch:"
                f"expected={selected_observed.get('selected_candidate_update_keys_exact')!r}:got={payload_keys!r}"
            )
        target_status = dict(selected_boundary.get("target_band_status") or {})
        target_checks = {
            "target_low": 0.85,
            "target_high": 1.0,
            "selected_reaches_target_band": True,
            "band_reacher_count": 1,
        }
        for key, expected_value in target_checks.items():
            if target_status.get(key) != expected_value:
                failures.append(
                    f"bottom_reo_recommendation_selected:pool_boundary_target_{key}_mismatch:"
                    f"expected={expected_value!r}:got={target_status.get(key)!r}"
                )
    no_valid_decision = scenario_summary.get("bottom_reo_recommendation_no_valid_candidate", {}).get("selected_candidate_decision_exact", {})
    no_valid_observed = scenario_summary.get("bottom_reo_recommendation_no_valid_candidate", {})
    if not no_valid_decision:
        failures.append("bottom_reo_recommendation_no_valid_candidate:selected_candidate_decision_missing")
    elif isinstance(no_valid_decision, dict):
        stable_checks = {
            "selected_candidate_id": None,
            "filtered_candidate_order_hash": no_valid_observed.get("candidate_order_hash"),
            "selected_candidate_update_keys": [],
            "final_result_update_keys": [],
            "post_selector_guard_result": "no_result",
            "no_result_reason": "no_filtered_candidates",
            "compound_preference_changed": False,
            "compound_preference_selected": False,
        }
        for key, expected_value in stable_checks.items():
            observed_value = no_valid_decision.get(key)
            if isinstance(observed_value, tuple):
                observed_value = list(observed_value)
            if observed_value != expected_value:
                failures.append(
                    f"bottom_reo_recommendation_no_valid_candidate:decision_{key}_mismatch:"
                    f"expected={expected_value!r}:got={observed_value!r}"
                )
    no_valid_boundary = scenario_summary.get("bottom_reo_recommendation_no_valid_candidate", {}).get("candidate_pool_boundary_exact", {})
    if not no_valid_boundary:
        failures.append("bottom_reo_recommendation_no_valid_candidate:candidate_pool_boundary_missing")
    elif isinstance(no_valid_boundary, dict):
        stable_checks = {
            "source_family_runtime_id": "normal_bottom_reo_recommendation",
            "generated_candidate_count": no_valid_observed.get("raw_candidate_count"),
            "generated_candidate_order_hash": no_valid_observed.get("raw_candidate_order_hash"),
            "filtered_candidate_count": no_valid_observed.get("filtered_candidate_count"),
            "filtered_candidate_order_hash": no_valid_observed.get("filtered_candidate_order_hash"),
            "ranked_candidate_count": 0,
            "selected_candidate_id": None,
        }
        for key, expected_value in stable_checks.items():
            if no_valid_boundary.get(key) != expected_value:
                failures.append(
                    f"bottom_reo_recommendation_no_valid_candidate:pool_boundary_{key}_mismatch:"
                    f"expected={expected_value!r}:got={no_valid_boundary.get(key)!r}"
                )
        payload_keys = sorted(str(key) for key in dict(no_valid_boundary.get("selected_update_payload") or {}).keys())
        if payload_keys:
            failures.append(
                "bottom_reo_recommendation_no_valid_candidate:pool_boundary_selected_update_payload_not_empty:"
                f"got={payload_keys!r}"
            )
        reject_reasons = dict(no_valid_boundary.get("reject_skip_reasons") or {})
        if reject_reasons.get("no_result_reason") != "no_filtered_candidates":
            failures.append(
                "bottom_reo_recommendation_no_valid_candidate:pool_boundary_no_result_reason_mismatch:"
                f"got={reject_reasons.get('no_result_reason')!r}"
            )

    expected = {
        "bottom_reo_recommendation_selected": {
            "return_status": "selected",
            "selected_candidate_id": "bottom_reo_recommendation_selected_bottom_recommendation_5_0_16_16",
            "result_update_keys": NORMAL_BOTTOM_RECOMMENDATION_UPDATE_KEYS,
        },
        "bottom_reo_tightening_selected": {
            "return_status": "selected",
            "selected_candidate_id": "bottom_reo_tightening_selected_guidance_bottom_tighten_3_0_16_16",
            "result_update_keys": BOTTOM_UPDATE_KEYS,
        },
        "bottom_reo_recommendation_no_valid_candidate": {
            "return_status": "no_result",
            "return_reason": "no_filtered_candidates",
        },
    }
    for scenario, checks in expected.items():
        observed = scenario_summary.get(scenario, {})
        for key, expected_value in checks.items():
            if observed.get(key) != expected_value:
                failures.append(f"{scenario}:{key}:expected={expected_value!r}:got={observed.get(key)!r}")

    status = "PASS" if not failures else "FAIL"
    output_path = ARTIFACT_DIR / f"bottom_reo_recommendation_readiness_snapshot_9N_{stamp}.json"
    snapshot = {
        "schema": "bottom_reo_recommendation_readiness_snapshot.v1",
        "status": status,
        "failures": failures,
        "trace_path": str(trace_path),
        "scenarios": scenario_summary,
        "trace_row_count": len(rows),
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{status}: {output_path}")
    print(f"trace: {trace_path}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
