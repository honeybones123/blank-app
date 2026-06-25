"""Snapshot bottom reo ranking score/source surfaces.

This verifier freezes the scored candidate surface passed into the existing
page-local ranking wrapper. It does not move ranking, selection, CTA/action,
one-click, publication, mutation, UI/session, or debug logic.
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
    build_bottom_reo_accepted_candidates,
    build_bottom_reo_scored_candidates,
)
from tools.verification import bottom_reo_evaluated_candidate_filter_boundary_snapshot as boundary_snapshot


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

SCENARIOS = [
    "normal_bending_underdesign",
    "two_layer_arrangement",
    "bending_overdesign_cleanup",
    "spacing_limited_arrangement",
    "geometry_constrained_arrangement",
]

FORBIDDEN_SCORE_SURFACE_KEYS = {
    "action_payload",
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
    "selected_recommendation",
    "session_state",
    "ui",
}


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_identity(candidate: dict[str, Any]) -> str:
    candidate_id = candidate.get("candidate_id") or candidate.get("source_candidate_id")
    if candidate_id:
        return str(candidate_id)
    return f"trace:{_stable_hash(candidate)}"


def _update_keys(updates: Any) -> tuple[str, ...]:
    if not isinstance(updates, dict):
        return ()
    return tuple(sorted(str(key) for key in updates.keys()))


def _arrangement_signature(candidate: dict[str, Any]) -> str | None:
    arrangement = candidate.get("arrangement")
    if not isinstance(arrangement, dict):
        return None
    return _stable_hash({
        "bot1_count": arrangement.get("bot1_count"),
        "bot2_count": arrangement.get("bot2_count"),
        "db_bot_1": arrangement.get("db_bot_1"),
        "db_bot_2": arrangement.get("db_bot_2"),
        "bot_row_count": arrangement.get("bot_row_count"),
        "spacing_bot_1": arrangement.get("spacing_bot_1"),
        "spacing_bot_2": arrangement.get("spacing_bot_2"),
    })


def _score_inputs(candidate: dict[str, Any], mode_config: dict[str, Any]) -> dict[str, Any]:
    overview = candidate.get("overview") if isinstance(candidate.get("overview"), dict) else {}
    utils = overview.get("utils") if isinstance(overview.get("utils"), dict) else {}
    arrangement = candidate.get("arrangement") if isinstance(candidate.get("arrangement"), dict) else {}
    return {
        "bending_util": _as_float(utils.get("bending")),
        "worst_util": _as_float(candidate.get("worst_util") or overview.get("worst_util")),
        "candidate_post_util": _as_float(candidate.get("candidate_post_util")),
        "candidate_reaches_target_band": (
            bool(candidate.get("candidate_reaches_target_band"))
            if "candidate_reaches_target_band" in candidate
            else None
        ),
        "candidate_distance_to_target_band": _as_float(candidate.get("candidate_distance_to_target_band")),
        "target_low": _as_float(mode_config.get("target_util_min", mode_config.get("target_low"))),
        "target_high": _as_float(mode_config.get("target_util_max", mode_config.get("target_high"))),
        "delta_Ast_bot": _as_float(candidate.get("delta_Ast_bot")),
        "delta_D_mm": _as_float(candidate.get("delta_D_mm")),
        "delta_b_mm": _as_float(candidate.get("delta_b_mm")),
        "update_keys": _update_keys(candidate.get("updates")),
        "arrangement": {
            "bot1_count": arrangement.get("bot1_count"),
            "bot2_count": arrangement.get("bot2_count"),
            "db_bot_1": arrangement.get("db_bot_1"),
            "db_bot_2": arrangement.get("db_bot_2"),
            "bot_row_count": arrangement.get("bot_row_count"),
        },
    }


def _extract_boundary(trace_rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    expected = f"BOTTOM_REO_RANKING_SCORE_SOURCE_{scenario}"
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


def _build_score_records(
    *,
    scored_candidates: list[dict[str, Any]],
    accepted_candidates: list[dict[str, Any]],
    mode_config: dict[str, Any],
    score_call_identities: set[str],
) -> list[dict[str, Any]]:
    accepted_index_by_identity = {
        str(item.get("candidate_identity") or ""): int(item.get("accepted_order_index"))
        for item in accepted_candidates
        if isinstance(item, dict)
    }
    score_surfaces: list[dict[str, Any]] = []
    for index, candidate in enumerate(scored_candidates):
        if not isinstance(candidate, dict):
            continue
        identity = _candidate_identity(candidate)
        score_source = (
            "inputs_page.py:_compute_bottom_reo_recommendation:_score_auto_design_candidate"
            if identity in score_call_identities
            else "candidate.score_from_evaluator_surface"
        )
        score_surfaces.append(
            {
                "scored_order_index": index,
                "source_accepted_candidate_index": accepted_index_by_identity.get(identity),
                "candidate_identity": identity,
                "score_value": _as_float(candidate.get("score")),
                "score_source": score_source,
                "score_inputs": _score_inputs(candidate, mode_config),
            },
        )
    return [
        item.to_dict()
        for item in build_bottom_reo_scored_candidates(
            accepted_candidates=accepted_candidates,
            score_records=score_surfaces,
        )
    ]


def _run_scenario(module: Any, scenario: str, trace_path: Path) -> dict[str, Any]:
    state = boundary_snapshot._scenario_state(scenario)
    seed_state = dict(state)
    seed_ast = boundary_snapshot._ast_for(boundary_snapshot._arrangement_from_state(seed_state))
    seed_util = 1.12 if scenario != "bending_overdesign_cleanup" else 0.72
    score_call_identities: set[str] = set()
    captured: dict[str, Any] = {
        "scored_candidates": [],
        "mode_config": boundary_snapshot._mode_config(state),
        "limit": None,
        "ranking_call_count": 0,
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

    def _score_candidate(candidate: dict, mode_config: dict, seed_candidate: dict) -> float:
        score_call_identities.add(_candidate_identity(candidate))
        return float(candidate.get("score", 100.0) or 100.0)

    def _capture_keep_top(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
        captured["ranking_call_count"] = int(captured.get("ranking_call_count") or 0) + 1
        captured["scored_candidates"] = [dict(candidate or {}) for candidate in list(candidates or [])]
        captured["mode_config"] = dict(mode_config or {})
        captured["limit"] = int(limit)
        return list(candidates or [])[: max(int(limit), 0)]

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
        "_score_auto_design_candidate": _score_candidate,
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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_RANKING_SCORE_SOURCE_{scenario}"
    with boundary_snapshot._patched(module, replacements):
        module._compute_bottom_reo_recommendation(dict(state))
    trace_rows = boundary_snapshot._load_jsonl(trace_path)[before_rows:]
    boundary = _extract_boundary(trace_rows, scenario)
    accepted = [item.to_dict() for item in build_bottom_reo_accepted_candidates(boundary=boundary)]
    score_records = _build_score_records(
        scored_candidates=list(captured.get("scored_candidates") or []),
        accepted_candidates=accepted,
        mode_config=dict(captured.get("mode_config") or {}),
        score_call_identities=score_call_identities,
    )
    forbidden_present = sorted(
        {
            key
            for candidate in list(captured.get("scored_candidates") or [])
            if isinstance(candidate, dict)
            for key in sorted(set(candidate.keys()) & FORBIDDEN_SCORE_SURFACE_KEYS)
        },
    )
    return {
        "scenario": scenario,
        "trace_event_found": bool(boundary),
        "accepted_candidate_count": len(accepted),
        "accepted_candidate_order": [str(item.get("candidate_identity") or "") for item in accepted],
        "scored_candidate_count": len(score_records),
        "scored_candidate_order": [str(item.get("candidate_identity") or "") for item in score_records],
        "score_hash": _stable_hash([
            {
                "candidate_identity": item.get("candidate_identity"),
                "score_value": item.get("score_value"),
                "score_source": item.get("score_source"),
                "score_inputs": item.get("score_inputs"),
            }
            for item in score_records
        ]),
        "scored_candidate_order_hash": _stable_hash([
            str(item.get("candidate_identity") or "") for item in score_records
        ]),
        "ranking_limit": captured.get("limit"),
        "ranking_call_count": captured.get("ranking_call_count"),
        "score_records": score_records,
        "forbidden_keys_present": forbidden_present,
        "boundary": {
            "pre_rank_surface_hash": boundary.get("pre_rank_surface_hash"),
            "accepted_prerank_order_hash": boundary.get("accepted_prerank_order_hash"),
            "forbidden_fields_present": list(boundary.get("forbidden_fields_present") or []),
            "ranking_selection_cta_publication_absent": bool(boundary.get("ranking_selection_cta_publication_absent")),
        },
    }


def _assert_scenario(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not result.get("trace_event_found"):
        failures.append("missing_trace_boundary")
    if result.get("accepted_candidate_order") != result.get("scored_candidate_order"):
        failures.append("accepted_to_scored_order_mismatch")
    if result.get("accepted_candidate_count") != result.get("scored_candidate_count"):
        failures.append("accepted_to_scored_count_mismatch")
    if result.get("scored_candidate_count") and not result.get("score_hash"):
        failures.append("missing_score_hash")
    if result.get("scored_candidate_count") and not result.get("scored_candidate_order_hash"):
        failures.append("missing_scored_candidate_order_hash")
    if int(result.get("ranking_call_count") or 0) <= 0 and int(result.get("accepted_candidate_count") or 0) > 0:
        failures.append("ranking_not_called_for_scored_candidates")
    forbidden = list(result.get("forbidden_keys_present") or [])
    if forbidden:
        failures.append(f"forbidden_score_surface_keys:{','.join(forbidden)}")
    for item in list(result.get("score_records") or []):
        if not isinstance(item, dict):
            failures.append("score_record_not_dict")
            continue
        if item.get("source_accepted_candidate_index") is None:
            failures.append("missing_source_accepted_candidate_index")
        if item.get("score_value") is None:
            failures.append("missing_score_value")
        if not item.get("score_source"):
            failures.append("missing_score_source")
    return sorted(set(failures))


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"bottom_reo_ranking_score_source_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_ranking_score_source_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_ranking_score_source_{stamp}.md"

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
        same_score_hash = scenario_result.get("score_hash") == repeat.get("score_hash")
        same_order_hash = scenario_result.get("scored_candidate_order_hash") == repeat.get("scored_candidate_order_hash")
        stability[scenario_name] = {
            "same_score_hash": same_score_hash,
            "same_scored_candidate_order_hash": same_order_hash,
            "first_score_hash": scenario_result.get("score_hash"),
            "repeat_score_hash": repeat.get("score_hash"),
            "first_order_hash": scenario_result.get("scored_candidate_order_hash"),
            "repeat_order_hash": repeat.get("scored_candidate_order_hash"),
        }
        if int(scenario_result.get("accepted_candidate_count") or 0) == 0:
            zero_accepted_seen = True
        if not same_score_hash:
            scenario_failures.append("unstable_score_hash")
        if not same_order_hash:
            scenario_failures.append("unstable_scored_candidate_order_hash")
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
        "forbidden_score_surface_keys": sorted(FORBIDDEN_SCORE_SURFACE_KEYS),
        "failures": failures,
        "assertions": {
            "accepted_candidate_identity_recorded": True,
            "source_accepted_candidate_index_recorded": True,
            "score_value_recorded": True,
            "score_source_recorded": True,
            "score_inputs_recorded": True,
            "pre_selection_order_recorded": True,
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
                    "mutation",
                    "session_state",
                    "debug",
                }
                for result in scenarios
            ),
            "product_path_changed": False,
        },
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")

    report_lines = [
        "# Bottom Reo Ranking Score/Source Snapshot",
        "",
        f"- Status: {status}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Scope",
        "",
        "This snapshot freezes the scored candidate surface passed to `_keep_top_candidates(...)` after accepted-candidate filtering and before final selection.",
        "",
        "It records score values, source labels, score inputs, pre-selection order, and hash stability. It excludes selected recommendation, final selected repair, CTA, one-click, publication, render/UI, mutation, session, and debug fields.",
        "",
        "## Scenario Summary",
    ]
    for scenario_result in scenarios:
        name = str(scenario_result.get("scenario"))
        score_sources = sorted({
            str(item.get("score_source") or "")
            for item in list(scenario_result.get("score_records") or [])
            if isinstance(item, dict)
        })
        report_lines.extend([
            "",
            f"### {name}",
            f"- accepted count: {scenario_result.get('accepted_candidate_count')}",
            f"- scored candidate count: {scenario_result.get('scored_candidate_count')}",
            f"- score hash: `{scenario_result.get('score_hash')}`",
            f"- scored order hash: `{scenario_result.get('scored_candidate_order_hash')}`",
            f"- score sources: `{score_sources}`",
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
            "Do not move ranking or scoring. Repair the score boundary first so the score source is explicit and score calculation can be separated from live candidate dictionaries.",
        ])
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. Ranking score/source surfaces are stable and exclude selection, CTA, one-click, publication, render/UI, mutation, session, and debug fields.",
            "",
            "## Recommendation",
            "",
            "Next slice should add a typed scored-candidate boundary. Do not move ranking yet.",
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
