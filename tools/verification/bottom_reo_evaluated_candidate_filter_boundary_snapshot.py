"""Focused proof snapshot for bottom reo evaluated/filter boundary.

This verifier exercises the normal bottom-reinforcement recommendation path
with deterministic evaluator inputs and snapshots only the arrangement-to-
evaluated-candidate/filter surface. It intentionally excludes ranking,
selection, CTA, one-click, publication, render, and mutation outputs.
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
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

FORBIDDEN_RECORD_KEYS = {
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "debug",
    "final_selected_repair",
    "mutation",
    "one_click",
    "publication",
    "rank",
    "ranking",
    "ranking_score",
    "render",
    "score",
    "selected_recommendation",
    "session_state",
    "ui",
}

BOTTOM_UPDATE_KEYS = {
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
}


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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
        "bw": 300.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 170.0,
        "uls_Vstar": 60.0,
        "bot1_count": 4,
        "bot2_count": 0,
        "db_bot_1": 16,
        "db_bot_2": 16,
        "bot_row_count": 1,
        "cover_side": 40.0,
        "rowgap_bot": 60.0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
        "design_optimisation_goal": "balanced",
        "optimisation_lock_geometry": True,
    }


def _scenario_state(name: str) -> dict[str, Any]:
    state = _base_state()
    if name == "bending_overdesign_cleanup":
        state.update({
            "bot1_count": 7,
            "db_bot_1": 20,
            "design_optimisation_goal": "low_reo",
        })
    elif name == "spacing_limited_arrangement":
        state.update({
            "b": 220.0,
            "bw": 220.0,
            "bot1_count": 5,
            "db_bot_1": 20,
            "cover_side": 45.0,
        })
    elif name == "two_layer_arrangement":
        state.update({
            "bot1_count": 6,
            "bot2_count": 2,
            "db_bot_1": 20,
            "db_bot_2": 16,
            "bot_row_count": 2,
        })
    elif name == "geometry_constrained_arrangement":
        state.update({
            "b": 260.0,
            "bw": 260.0,
            "D": 450.0,
            "bot1_count": 5,
            "db_bot_1": 24,
            "cover_side": 50.0,
            "rowgap_bot": 55.0,
        })
    return state


def _overview(util: float, *, compliant: bool) -> dict[str, Any]:
    return {
        "statuses": {
            "bending": "PASS" if compliant else "FAIL",
            "shear": "PASS",
            "crack": "PASS",
            "deflection": "PASS",
        },
        "utils": {
            "bending": float(util),
            "shear": min(float(util), 0.82),
            "crack": 0.42,
            "deflection": 0.39,
        },
        "any_fail": not compliant,
        "all_key_pass": bool(compliant),
        "is_compliant": bool(compliant),
        "worst_util": float(util),
        "governing_util": float(util),
    }


def _mode_config(state: dict[str, Any]) -> dict[str, Any]:
    strategy = "low_reo" if str(state.get("design_optimisation_goal")) == "low_reo" else "balanced"
    return {
        "target_util_min": 0.85,
        "target_util_max": 1.0,
        "target_low": 0.85,
        "target_high": 1.0,
        "search_strategy": strategy,
        "geometry_penalty": 0.4,
        "width_penalty": 0.4,
        "depth_growth_multiplier": 1.0,
    }


def _arrangement_from_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "bot1_count": int(state.get("bot1_count", 0) or 0),
        "bot2_count": int(state.get("bot2_count", 0) or 0),
        "db_bot_1": int(state.get("db_bot_1", 0) or 0),
        "db_bot_2": int(state.get("db_bot_2", state.get("db_bot_1", 0)) or 0),
        "bot_row_count": int(state.get("bot_row_count", 1) or 1),
    }


def _ast_for(arrangement: dict[str, Any]) -> float:
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    return round(count_1 * 3.14159 * dia_1 * dia_1 / 4.0 + count_2 * 3.14159 * dia_2 * dia_2 / 4.0, 3)


def _candidate_from_state(
    candidate_state: dict[str, Any],
    *,
    seed_state: dict[str, Any],
    source: str,
    label: str,
    action_type: str,
    seed_ast: float,
    seed_util: float,
) -> dict[str, Any] | None:
    arrangement = _arrangement_from_state(candidate_state)
    ast = _ast_for(arrangement)
    if ast <= 0:
        return None
    updates = {
        key: value
        for key, value in candidate_state.items()
        if seed_state.get(key) != value and key in BOTTOM_UPDATE_KEYS
    }
    util = round(max(0.62, min(1.28, (seed_ast / ast) * seed_util)), 4)
    compliant = util <= 1.0
    cid = (
        f"{source}_{arrangement['bot1_count']}_{arrangement['bot2_count']}_"
        f"{arrangement['db_bot_1']}_{arrangement['db_bot_2']}_{arrangement['bot_row_count']}"
    )
    return {
        "candidate_id": cid,
        "source_candidate_id": cid,
        "state": dict(candidate_state),
        "updates": dict(updates),
        "label": label,
        "action_type": action_type,
        "is_compliant": bool(compliant),
        "overview": _overview(util, compliant=compliant),
        "worst_util": util,
        "score": round(abs(0.92 - util) * 100.0 + len(updates), 4),
        "Ast_bot": ast,
        "actual_ast": ast,
        "arrangement": dict(arrangement),
        "in_target_band": 0.85 <= util <= 1.0,
    }


def _extract_boundary(trace_rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    expected = f"BOTTOM_REO_EVAL_FILTER_BOUNDARY_{scenario}"
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


def _run_scenario(module: Any, scenario: str, trace_path: Path) -> dict[str, Any]:
    state = _scenario_state(scenario)
    seed_state = dict(state)
    seed_ast = _ast_for(_arrangement_from_state(seed_state))
    seed_util = 1.12 if scenario != "bending_overdesign_cleanup" else 0.72

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
            "overview": _overview(seed_util, compliant=seed_util <= 1.0),
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
        return _candidate_from_state(
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

    replacements = {
        "_guidance_state_snapshot": lambda incoming=None: dict(incoming or {}),
        "_recommendation_search_allowed": lambda incoming: True,
        "_build_design_actions_context": lambda incoming: {"state": dict(incoming or {})},
        "_collect_design_overview": lambda incoming, **kwargs: _overview(seed_util, compliant=seed_util <= 1.0),
        "_efficiency_reduction_profile_from_overview": lambda overview: False,
        "_design_optimisation_goal": lambda incoming=None: str(state.get("design_optimisation_goal") or "balanced"),
        "_design_mode_config": lambda goal=None: _mode_config(state),
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
        "_keep_top_candidates": lambda candidates, mode_config, *, limit: list(candidates or [])[: max(int(limit), 0)],
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

    before_rows = len(_load_jsonl(trace_path))
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_EVAL_FILTER_BOUNDARY_{scenario}"
    with _patched(module, replacements):
        module._compute_bottom_reo_recommendation(
            dict(state),
            runtime=module.bottom_recommendation_runtime_from_namespace(
                module.__dict__
            ),
        )
    trace_rows = _load_jsonl(trace_path)[before_rows:]
    boundary = _extract_boundary(trace_rows, scenario)
    return {
        "scenario": scenario,
        "boundary": boundary,
        "record_count": len(boundary.get("records") or []),
        "pre_rank_surface_hash": boundary.get("pre_rank_surface_hash"),
        "accepted_prerank_order_hash": boundary.get("accepted_prerank_order_hash"),
        "accepted_prerank_candidate_ids": list(boundary.get("accepted_prerank_candidate_ids") or []),
        "forbidden_fields_present": list(boundary.get("forbidden_fields_present") or []),
        "trace_event_found": bool(boundary),
    }


def _assert_boundary(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    boundary = result.get("boundary") if isinstance(result.get("boundary"), dict) else {}
    records = boundary.get("records") if isinstance(boundary.get("records"), list) else []
    if not boundary:
        failures.append("missing_boundary")
        return failures
    if not records:
        failures.append("empty_boundary_records")
    if not boundary.get("pre_rank_surface_hash"):
        failures.append("missing_pre_rank_surface_hash")
    if boundary.get("forbidden_fields_present"):
        failures.append("forbidden_fields_present")
    if not boundary.get("ranking_selection_cta_publication_absent"):
        failures.append("ranking_selection_cta_publication_not_absent")
    for record in records:
        leaked = sorted(set(record.keys()) & FORBIDDEN_RECORD_KEYS)
        if leaked:
            failures.append(f"record_forbidden_keys:{','.join(leaked)}")
        if not record.get("status"):
            failures.append("missing_status_field")
        if record.get("evaluator_returned") is None:
            failures.append("missing_evaluator_returned_field")
        if not record.get("arrangement_update_payload_hash"):
            failures.append("missing_arrangement_update_payload_hash")
    return sorted(set(failures))


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page_modules.recommendation_compute")
    provider = importlib.import_module("inputs_page_app_contract_bridge")
    module._bind_named_recommendation_globals(
        legacy_page=provider,
        names=module._BOTTOM_RECOMMENDATION_NAMES,
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_evaluated_candidate_filter_boundary_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_evaluated_candidate_filter_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_evaluated_candidate_filter_boundary_{stamp}.md"

    scenarios = [
        "normal_bending_underdesign",
        "bending_overdesign_cleanup",
        "spacing_limited_arrangement",
        "two_layer_arrangement",
        "geometry_constrained_arrangement",
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

    results: list[dict[str, Any]] = []
    repeat_results: list[dict[str, Any]] = []
    try:
        for scenario in scenarios:
            results.append(_run_scenario(module, scenario, trace_path))
        for scenario in scenarios:
            repeat_results.append(_run_scenario(module, scenario, trace_path))
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    repeat_by_scenario = {item["scenario"]: item for item in repeat_results}
    failures: dict[str, list[str]] = {}
    stability: dict[str, dict[str, Any]] = {}
    aggregate_statuses: set[str] = set()
    for result in results:
        scenario = str(result["scenario"])
        scenario_failures = _assert_boundary(result)
        boundary = result.get("boundary") if isinstance(result.get("boundary"), dict) else {}
        for record in list(boundary.get("records") or []):
            if isinstance(record, dict) and record.get("status"):
                aggregate_statuses.add(str(record.get("status")))
        repeat = repeat_by_scenario.get(scenario, {})
        same_surface_hash = result.get("pre_rank_surface_hash") == repeat.get("pre_rank_surface_hash")
        same_accepted_order = result.get("accepted_prerank_candidate_ids") == repeat.get("accepted_prerank_candidate_ids")
        stability[scenario] = {
            "same_pre_rank_surface_hash": same_surface_hash,
            "same_accepted_rejected_order": same_accepted_order,
            "first_hash": result.get("pre_rank_surface_hash"),
            "repeat_hash": repeat.get("pre_rank_surface_hash"),
        }
        if not same_surface_hash:
            scenario_failures.append("unstable_pre_rank_surface_hash")
        if not same_accepted_order:
            scenario_failures.append("unstable_accepted_rejected_order")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))

    if "accepted_prerank" not in aggregate_statuses:
        failures.setdefault("_aggregate", []).append("missing_any_accepted_prerank_record")
    if "rejected" not in aggregate_statuses:
        failures.setdefault("_aggregate", []).append("missing_any_rejected_record")

    snapshot = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": stamp,
        "trace_path": str(trace_path),
        "scenarios": results,
        "stability": stability,
        "forbidden_record_keys": sorted(FORBIDDEN_RECORD_KEYS),
        "failures": failures,
        "assertions": {
            "pre_rank_surface_only": True,
            "ranking_selection_cta_one_click_publication_absent": not failures,
            "product_path_changed": False,
        },
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")

    report_lines = [
        "# Bottom Reo Evaluated-Candidate Filter Boundary Snapshot",
        "",
        f"- Status: {snapshot['status']}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "Proof-only boundary for arrangement/spec input through evaluator/filtering.",
        "Ranking, selection, CTA, one-click, publication, UI render, mutation, and session/debug-only fields remain absent.",
        "",
        "## Scenario Summary",
    ]
    for result in results:
        report_lines.extend([
            "",
            f"### {result['scenario']}",
            f"- records: {result['record_count']}",
            f"- pre-rank surface hash: `{result['pre_rank_surface_hash']}`",
            f"- accepted pre-rank ids: `{result['accepted_prerank_candidate_ids']}`",
            f"- forbidden fields: `{result['forbidden_fields_present']}`",
            f"- stability: `{stability.get(str(result['scenario']), {})}`",
        ])
    if failures:
        report_lines.extend(["", "## Failures", ""])
        for scenario, scenario_failures in failures.items():
            report_lines.append(f"- {scenario}: {', '.join(scenario_failures)}")
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. The boundary separates pre-rank evaluator/filter surfaces from ranking, selected recommendation, CTA, one-click, publication, UI render, mutation, and session/debug fields.",
            "",
            "## Recommendation",
            "",
            "Next step can audit a pure evaluated-candidate/filter normalizer. Do not move `_evaluate_candidate_fast(...)` yet.",
        ])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": snapshot["status"],
        "artifact": str(artifact_path),
        "report": str(report_path),
        "trace": str(trace_path),
        "failures": failures,
    }, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
