"""Snapshot the bottom reo accepted-candidate-to-ranking input boundary.

This verifier is proof-only. It captures the exact candidate surface handed to
the existing page-local `_keep_top_candidates(...)` call, then compares it with
the family-owned accepted-candidate records derived from evaluated/filter
boundary records.

The snapshot intentionally fails if ranking input cannot be separated from
ranking score, selection, CTA, one-click, publication, render/UI, mutation,
session, or debug-only fields.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
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

from design_brain.families.bending import build_bottom_reo_accepted_candidates
from tools.verification import bottom_reo_evaluated_candidate_filter_boundary_snapshot as boundary_snapshot


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

SCENARIOS = [
    "normal_bending_underdesign",
    "bending_overdesign_cleanup",
    "spacing_limited_arrangement",
    "two_layer_arrangement",
    "geometry_constrained_arrangement",
]

FORBIDDEN_RANKING_INPUT_KEYS = {
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
    "score",
    "selected_recommendation",
    "session_state",
    "ui",
}


@dataclass(frozen=True)
class BottomReoRankingInputCandidate:
    """Typed proof record for the pre-ranking input surface.

    This record is intentionally verifier-local until the boundary is proven
    score-free and independent from live candidate dictionaries.
    """

    ranking_input_order_index: int
    source_accepted_candidate_index: int | None
    candidate_identity: str
    update_keys: tuple[str, ...]
    update_payload_hash: str | None
    arrangement_signature: str | None
    utilisation_summary: dict[str, Any]
    target_band_inputs: dict[str, Any]
    least_change_inputs: dict[str, Any]
    forbidden_keys_present: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _candidate_identity(candidate: dict[str, Any]) -> str:
    candidate_id = candidate.get("candidate_id") or candidate.get("source_candidate_id")
    if candidate_id:
        return str(candidate_id)
    return f"trace:{_stable_hash(candidate)}"


def _update_keys(updates: Any) -> tuple[str, ...]:
    if not isinstance(updates, dict):
        return ()
    return tuple(sorted(str(key) for key in updates.keys()))


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _utilisation_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    overview = candidate.get("overview") if isinstance(candidate.get("overview"), dict) else {}
    utils = overview.get("utils") if isinstance(overview.get("utils"), dict) else {}
    return {
        "bending_util": _as_float(utils.get("bending")),
        "worst_util": _as_float(candidate.get("worst_util") or overview.get("worst_util")),
        "candidate_post_util": _as_float(candidate.get("candidate_post_util")),
        "is_compliant": bool(candidate.get("is_compliant")),
    }


def _target_band_inputs(candidate: dict[str, Any], mode_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_low": _as_float(mode_config.get("target_util_min", mode_config.get("target_low"))),
        "target_high": _as_float(mode_config.get("target_util_max", mode_config.get("target_high"))),
        "candidate_reaches_target_band": (
            bool(candidate.get("candidate_reaches_target_band"))
            if "candidate_reaches_target_band" in candidate
            else None
        ),
        "candidate_distance_to_target_band": _as_float(candidate.get("candidate_distance_to_target_band")),
    }


def _least_change_inputs(candidate: dict[str, Any]) -> dict[str, Any]:
    arrangement = candidate.get("arrangement") if isinstance(candidate.get("arrangement"), dict) else {}
    return {
        "delta_Ast_bot": _as_float(candidate.get("delta_Ast_bot")),
        "delta_D_mm": _as_float(candidate.get("delta_D_mm")),
        "delta_b_mm": _as_float(candidate.get("delta_b_mm")),
        "bot1_count": arrangement.get("bot1_count"),
        "bot2_count": arrangement.get("bot2_count"),
        "db_bot_1": arrangement.get("db_bot_1"),
        "db_bot_2": arrangement.get("db_bot_2"),
        "bot_row_count": arrangement.get("bot_row_count"),
    }


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


def _build_ranking_input_candidates(
    *,
    ranking_input_candidates: list[dict[str, Any]],
    accepted_candidates: list[dict[str, Any]],
    mode_config: dict[str, Any],
) -> list[dict[str, Any]]:
    accepted_index_by_identity = {
        str(item.get("candidate_identity") or ""): int(item.get("accepted_order_index"))
        for item in accepted_candidates
        if isinstance(item, dict)
    }
    records: list[dict[str, Any]] = []
    for index, candidate in enumerate(ranking_input_candidates):
        if not isinstance(candidate, dict):
            continue
        identity = _candidate_identity(candidate)
        updates = candidate.get("updates") if isinstance(candidate.get("updates"), dict) else {}
        forbidden = tuple(sorted(set(candidate.keys()) & FORBIDDEN_RANKING_INPUT_KEYS))
        records.append(
            BottomReoRankingInputCandidate(
                ranking_input_order_index=index,
                source_accepted_candidate_index=accepted_index_by_identity.get(identity),
                candidate_identity=identity,
                update_keys=_update_keys(updates),
                update_payload_hash=_stable_hash(updates),
                arrangement_signature=_arrangement_signature(candidate),
                utilisation_summary=_utilisation_summary(candidate),
                target_band_inputs=_target_band_inputs(candidate, mode_config),
                least_change_inputs=_least_change_inputs(candidate),
                forbidden_keys_present=forbidden,
            ).to_dict(),
        )
    return records


def _extract_boundary(trace_rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    expected = f"BOTTOM_REO_RANKING_INPUT_{scenario}"
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
    state = boundary_snapshot._scenario_state(scenario)
    seed_state = dict(state)
    seed_ast = boundary_snapshot._ast_for(boundary_snapshot._arrangement_from_state(seed_state))
    seed_util = 1.12 if scenario != "bending_overdesign_cleanup" else 0.72
    captured: dict[str, Any] = {
        "ranking_input_candidates": [],
        "mode_config": boundary_snapshot._mode_config(state),
        "limit": None,
        "calls": 0,
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

    def _capture_keep_top(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
        captured["calls"] = int(captured.get("calls") or 0) + 1
        captured["ranking_input_candidates"] = [dict(candidate or {}) for candidate in list(candidates or [])]
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
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_RANKING_INPUT_{scenario}"
    with boundary_snapshot._patched(module, replacements):
        module._compute_bottom_reo_recommendation(
            dict(state),
            runtime=module.bottom_recommendation_runtime_from_namespace(
                module.__dict__
            ),
        )
    trace_rows = boundary_snapshot._load_jsonl(trace_path)[before_rows:]
    boundary = _extract_boundary(trace_rows, scenario)
    accepted = [item.to_dict() for item in build_bottom_reo_accepted_candidates(boundary=boundary)]
    ranking_inputs = _build_ranking_input_candidates(
        ranking_input_candidates=list(captured.get("ranking_input_candidates") or []),
        accepted_candidates=accepted,
        mode_config=dict(captured.get("mode_config") or {}),
    )
    forbidden_present = sorted(
        {
            key
            for record in ranking_inputs
            for key in list(record.get("forbidden_keys_present") or [])
        },
    )
    return {
        "scenario": scenario,
        "trace_event_found": bool(boundary),
        "accepted_candidate_count": len(accepted),
        "accepted_candidate_order": [str(item.get("candidate_identity") or "") for item in accepted],
        "ranking_input_count": len(ranking_inputs),
        "ranking_input_order": [str(item.get("candidate_identity") or "") for item in ranking_inputs],
        "ranking_input_hash": _stable_hash(ranking_inputs),
        "ranking_limit": captured.get("limit"),
        "ranking_call_count": captured.get("calls"),
        "ranking_inputs": ranking_inputs,
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
    if result.get("accepted_candidate_order") != result.get("ranking_input_order"):
        failures.append("accepted_to_ranking_order_mismatch")
    if result.get("accepted_candidate_count") != result.get("ranking_input_count"):
        failures.append("accepted_to_ranking_count_mismatch")
    if result.get("ranking_input_count") and not result.get("ranking_input_hash"):
        failures.append("missing_ranking_input_hash")
    if int(result.get("ranking_call_count") or 0) <= 0 and int(result.get("accepted_candidate_count") or 0) > 0:
        failures.append("ranking_not_called_for_accepted_candidates")
    forbidden = list(result.get("forbidden_keys_present") or [])
    if forbidden:
        failures.append(f"forbidden_ranking_input_keys:{','.join(forbidden)}")
    for item in list(result.get("ranking_inputs") or []):
        if not isinstance(item, dict):
            failures.append("ranking_input_not_dict")
            continue
        if item.get("source_accepted_candidate_index") is None:
            failures.append("missing_source_accepted_candidate_index")
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
    trace_path = TRACE_DIR / f"bottom_reo_ranking_input_boundary_{stamp}.jsonl"
    artifact_path = ARTIFACT_DIR / f"bottom_reo_ranking_input_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_ranking_input_boundary_{stamp}.md"

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
        repeats = {_run["scenario"]: _run for _run in [_run_scenario(module, scenario, trace_path) for scenario in SCENARIOS]}
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    failures: dict[str, list[str]] = {}
    stability: dict[str, dict[str, Any]] = {}
    for scenario_result in scenarios:
        scenario_name = str(scenario_result.get("scenario"))
        scenario_failures = _assert_scenario(scenario_result)
        repeat = repeats.get(scenario_name, {})
        same_order = scenario_result.get("ranking_input_order") == repeat.get("ranking_input_order")
        same_hash = scenario_result.get("ranking_input_hash") == repeat.get("ranking_input_hash")
        stability[scenario_name] = {
            "same_ranking_input_order": same_order,
            "same_ranking_input_hash": same_hash,
            "first_hash": scenario_result.get("ranking_input_hash"),
            "repeat_hash": repeat.get("ranking_input_hash"),
        }
        if not same_order:
            scenario_failures.append("unstable_ranking_input_order")
        if not same_hash:
            scenario_failures.append("unstable_ranking_input_hash")
        if scenario_failures:
            failures[scenario_name] = sorted(set(scenario_failures))

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "status": status,
        "generated_at": stamp,
        "trace_path": str(trace_path),
        "scenarios": scenarios,
        "stability": stability,
        "forbidden_ranking_input_keys": sorted(FORBIDDEN_RANKING_INPUT_KEYS),
        "failures": failures,
        "assertions": {
            "accepted_candidate_order_recorded": True,
            "ranking_input_candidate_identity_recorded": True,
            "ranking_input_hash_recorded": True,
            "ranking_score_absent": not any(
                "score" in list(result.get("forbidden_keys_present") or [])
                for result in scenarios
            ),
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
        "# Bottom Reo Accepted-Candidate to Ranking Input Boundary Snapshot",
        "",
        f"- Status: {status}",
        f"- JSON artifact: `{artifact_path}`",
        f"- Trace artifact: `{trace_path}`",
        "",
        "## Audit",
        "",
        "Accepted bottom reo candidates enter ranking in `_compute_bottom_reo_recommendation(...)` after page-local annotation of candidate deltas, score, and target-band metrics.",
        "",
        "The ranking call is `_keep_top_candidates(filtered, mode_config, limit=min(16, len(filtered)))`.",
        "",
        "Extra fields observed before ranking include target-band metadata and least-change inputs. The live candidate dictionaries also include `score`, which means the exact live ranking input cannot currently be represented as a score-free boundary.",
        "",
        "## Scenario Summary",
    ]
    for scenario_result in scenarios:
        name = str(scenario_result.get("scenario"))
        report_lines.extend([
            "",
            f"### {name}",
            f"- accepted count: {scenario_result.get('accepted_candidate_count')}",
            f"- ranking input count: {scenario_result.get('ranking_input_count')}",
            f"- ranking input hash: `{scenario_result.get('ranking_input_hash')}`",
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
            "Do not move ranking yet. Add a ranking-score/source snapshot next, or split score calculation into an explicit pre-ranking score boundary before attempting ranking ownership transfer.",
        ])
    else:
        report_lines.extend([
            "",
            "## Result",
            "",
            "PASS. The ranking input boundary is stable and score-free.",
            "",
            "## Recommendation",
            "",
            "A family-owned ranking-input boundary can be added next without moving ranking itself.",
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
