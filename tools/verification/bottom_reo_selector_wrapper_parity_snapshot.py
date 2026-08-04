"""Focused parity snapshot for the proof-only bottom-reo selector wrapper.

This verifier compares the current page-local selected bottom-reo identity
against the family-owned selector wrapper proof output. It exercises
deterministic bottom-reo scenarios through the existing page-local
recommendation path, then passes only primitive trace surfaces into the proof
helper.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from design_brain.families.bending import build_bottom_reo_selector_wrapper_proof
from tools.verification.bottom_reo_recommendation_readiness_snapshot import (
    _arrangement_from_state,
    _ast_for,
    _base_state,
    _candidate_from_state,
    _load_jsonl,
    _mode_config,
    _overview,
    _patched,
    _stable_hash,
)


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

FORBIDDEN_PROOF_KEYS = {
    "action",
    "action_payload",
    "action_type",
    "button_contract",
    "cta",
    "cta_intent",
    "debug",
    "final_selected_repair",
    "mutation",
    "one_click",
    "one_click_action",
    "publication",
    "published",
    "render",
    "session",
    "session_state",
    "ui",
}

LIVE_CANDIDATE_DICT_KEYS = {
    "arrangement",
    "candidate_search_evidence",
    "overview",
    "state",
    "updates",
}


def _candidate(
    candidate_state: dict[str, Any],
    *,
    seed_state: dict[str, Any],
    source: str,
    label: str,
    action_type: str,
    util: float,
    score: float,
) -> dict[str, Any]:
    candidate = _candidate_from_state(
        candidate_state,
        seed_state=seed_state,
        source=source,
        label=label,
        action_type=action_type,
        util=util,
        score=score,
        compliant=True,
    )
    candidate["depth"] = float(candidate_state.get("D", seed_state.get("D", 600.0)) or 600.0)
    candidate["width"] = float(candidate_state.get("b", seed_state.get("b", 300.0)) or 300.0)
    candidate["_synthetic_goal_score"] = float(score)
    return candidate


def _state_with_arrangement(state: dict[str, Any], arrangement: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["bot1_count"] = int(arrangement.get("bot1_count", out.get("bot1_count", 0)) or 0)
    out["bot2_count"] = int(arrangement.get("bot2_count", out.get("bot2_count", 0)) or 0)
    out["db_bot_1"] = int(arrangement.get("db_bot_1", out.get("db_bot_1", 16)) or 16)
    out["db_bot_2"] = int(arrangement.get("db_bot_2", out.get("db_bot_2", out["db_bot_1"])) or out["db_bot_1"])
    out["bot_row_count"] = int(arrangement.get("row_count", 2 if out["bot2_count"] else 1) or 1)
    return out


def _run_scenario(module: Any, scenario: str) -> dict[str, Any]:
    state = _base_state()
    seed_state = dict(state)
    seed_ast = _ast_for(_arrangement_from_state(seed_state))

    def _seed_candidate(_state: dict[str, Any], *, source: str = "", **_: Any) -> dict[str, Any]:
        seed = dict(_state or {})
        return _candidate(
            seed,
            seed_state=dict(seed),
            source=f"{scenario}_seed",
            label=f"seed:{source}",
            action_type="seed",
            util=1.08,
            score=100.0,
        )

    def _generate_arrangements(
        _state: dict[str, Any],
        _mode_config: dict[str, Any],
        *,
        band: int = 0,
        **_: Any,
    ) -> list[dict[str, Any]]:
        if band != 0:
            return []
        if scenario == "normal_bending_underdesign":
            return [
                {"bot1_count": 5, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 5},
                {"bot1_count": 6, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 6},
            ]
        if scenario == "two_layer_arrangement":
            return [
                {"bot1_count": 4, "bot2_count": 2, "db_bot_1": 16, "db_bot_2": 16, "row_count": 2, "bar_count": 6},
                {"bot1_count": 5, "bot2_count": 2, "db_bot_1": 16, "db_bot_2": 16, "row_count": 2, "bar_count": 7},
            ]
        if scenario == "zero_accepted_scenario":
            return [
                {"bot1_count": 5, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 5},
                {"bot1_count": 4, "bot2_count": 2, "db_bot_1": 16, "db_bot_2": 16, "row_count": 2, "bar_count": 6},
            ]
        return []

    def _evaluate_fast(
        candidate_state: dict[str, Any],
        *,
        seed_state: dict[str, Any],
        source: str = "",
        label: str = "",
        action_type: str = "",
        **_: Any,
    ) -> dict[str, Any] | None:
        if scenario == "zero_accepted_scenario":
            return None
        arrangement = _arrangement_from_state(dict(candidate_state or {}))
        key = (
            arrangement["bot1_count"],
            arrangement["bot2_count"],
            arrangement["db_bot_1"],
            arrangement["db_bot_2"],
        )
        util_by_key = {
            (5, 0, 16, 16): 0.93,
            (6, 0, 16, 16): 0.89,
            (4, 2, 16, 16): 0.91,
            (5, 2, 16, 16): 0.88,
        }
        score_by_key = {
            (5, 0, 16, 16): 8.0,
            (6, 0, 16, 16): 20.0,
            (4, 2, 16, 16): 7.0,
            (5, 2, 16, 16): 19.0,
        }
        if key not in util_by_key:
            return None
        return _candidate(
            dict(candidate_state or {}),
            seed_state=dict(seed_state or {}),
            source=f"{scenario}_{source}",
            label=label,
            action_type=action_type,
            util=util_by_key[key],
            score=score_by_key[key],
        )

    def _updates_match_state(incoming: dict[str, Any], updates: dict[str, Any]) -> bool:
        update_dict = dict(updates or {})
        if not update_dict:
            return True
        return all((incoming or {}).get(key) == value for key, value in update_dict.items())

    def _keep_top(candidates: list[dict[str, Any]], mode_config: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        ordered = sorted(
            list(candidates or []),
            key=lambda item: float(item.get("score", 999999.0) or 999999.0),
        )
        return ordered[: max(int(limit), 0)]

    def _pick_best(candidates: list[dict[str, Any]], **_: Any) -> dict[str, Any] | None:
        ordered = _keep_top(list(candidates or []), {}, limit=1)
        return ordered[0] if ordered else None

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
        "_score_band_reaching_candidate_for_goal": lambda candidate, goal, current_state, mode_config: (float(candidate.get("_synthetic_goal_score", candidate.get("score", 100.0)) or 100.0), "synthetic_goal_score"),
        "_candidate_in_target_band": lambda candidate, mode_config: bool((candidate or {}).get("in_target_band", False)),
        "_candidate_debug_summary": lambda candidate: {
            "candidate_id": (candidate or {}).get("candidate_id"),
            "updates": dict((candidate or {}).get("updates") or {}),
            "score": (candidate or {}).get("score"),
        },
        "is_valid_reo_layout": lambda *args, **kwargs: True,
        "_geometry_lock_enabled": lambda incoming: True,
        "_updates_match_state": _updates_match_state,
        "_candidate_materially_improves": lambda seed, candidate: True,
        "_bottom_recommendation_prefilter_ok": lambda seed, candidate, incoming: (True, "ok"),
        "_collapse_bottom_geometry_width_depth_trials": lambda candidates, **kwargs: list(candidates or []),
        "_merge_design_guide_rank_trace": lambda payload: None,
        "_agent_debug_log": lambda *args, **kwargs: None,
        "_log_design_reco_candidate_rank": lambda *args, **kwargs: None,
        "_log_efficiency_growth_rejection": lambda *args, **kwargs: None,
        "_candidate_ductility_governs": lambda candidate: False,
        "_candidate_ductility_util": lambda candidate: None,
        "_is_strictly_rejectable_band_winner": lambda candidate, *, state: (False, ""),
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
        result = module._compute_bottom_reo_recommendation(
            dict(state),
            runtime=module.bottom_recommendation_runtime_from_namespace(
                module.__dict__
            ),
        )
    return result if isinstance(result, dict) else {}


def _return_payload(rows: list[dict[str, Any]], scenario: str) -> dict[str, Any]:
    matching = [
        row
        for row in rows
        if row.get("event") == "compute_guidance_route"
        and row.get("scenario") == f"BOTTOM_REO_SELECTOR_WRAPPER_{scenario}"
        and str(row.get("route_event") or "").endswith("_return")
    ]
    payload = matching[-1].get("payload") if matching else {}
    return payload if isinstance(payload, dict) else {}


def _parse_json_payload(payload: dict[str, Any], key: str, failures: list[str], scenario: str) -> dict[str, Any]:
    raw = payload.get(key)
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        failures.append(f"{scenario}:{key}_invalid")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, val in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PROOF_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden_keys(val))
    elif isinstance(value, list):
        for val in value:
            found.update(_walk_forbidden_keys(val))
    return found


def _walk_live_candidate_dicts(value: Any) -> int:
    if isinstance(value, dict):
        count = 1 if len(LIVE_CANDIDATE_DICT_KEYS & set(value.keys())) >= 2 else 0
        return count + sum(_walk_live_candidate_dicts(val) for val in value.values())
    if isinstance(value, list):
        return sum(_walk_live_candidate_dicts(val) for val in value)
    return 0


def _build_proof_from_trace(payload: dict[str, Any], scenario: str, failures: list[str]) -> dict[str, Any]:
    decision = _parse_json_payload(payload, "selected_candidate_decision_json", failures, scenario)
    selector = _parse_json_payload(payload, "selector_result_json", failures, scenario)
    ranked_identities = [str(value) for value in list(decision.get("ranked_candidate_identities") or [])]
    kept_identities = list(ranked_identities)
    selected_identity = (
        selector.get("selected_candidate_identity")
        or decision.get("selected_candidate_identity")
        or None
    )
    selected_index = (
        kept_identities.index(str(selected_identity))
        if selected_identity is not None and str(selected_identity) in kept_identities
        else None
    )
    reason_summary = {
        "status": selector.get("status") or payload.get("status"),
        "selected_reason": selector.get("selected_reason"),
        "no_candidate_reason": selector.get("no_candidate_reason"),
        "post_selector_guard_result": decision.get("post_selector_guard_result"),
        "no_result_reason": decision.get("no_result_reason"),
        "strict_band_winner_seen": selector.get("strict_band_winner_seen"),
        "strict_band_winner_accepted": selector.get("strict_band_winner_accepted"),
        "strict_band_rejected_reason": selector.get("strict_band_rejected_reason"),
        "legacy_rejection_reason": selector.get("legacy_rejection_reason"),
        "winner_pool_mode": selector.get("winner_pool_mode"),
        "selected_because_band": selector.get("selected_because_band"),
        "selected_reaches_target_band": selector.get("selected_reaches_target_band"),
    }
    input_surface = {
        "ranked_candidate_identities": list(ranked_identities),
        "kept_candidate_identities": list(kept_identities),
        "selected_candidate_identity": selected_identity,
        "selected_source_index": selected_index,
        "selected_source": "page_local_bottom_reo_selector",
        "selected_update_keys": list(selector.get("selected_update_keys") or decision.get("selected_candidate_update_keys") or []),
        "selected_updates_hash": selector.get("selected_updates_hash") or decision.get("selected_candidate_updates_hash"),
        "selected_candidate_trace_hash": selector.get("selected_candidate_trace_hash") or decision.get("selected_candidate_trace_hash"),
        "selection_reason_summary": dict(reason_summary),
    }
    before_hash = _stable_hash(input_surface)
    proof = build_bottom_reo_selector_wrapper_proof(**input_surface)
    after_hash = _stable_hash(input_surface)
    proof_dict = proof.to_dict()
    return {
        "decision": decision,
        "selector": selector,
        "page_local_selected_identity": selected_identity,
        "proof": proof_dict,
        "input_hash_before": before_hash,
        "input_hash_after": after_hash,
        "input_mutated": before_hash != after_hash,
        "forbidden_output_keys": sorted(_walk_forbidden_keys(proof_dict)),
        "live_candidate_dict_count": _walk_live_candidate_dicts(proof_dict),
    }


def _write_audit_report(path: Path, snapshot: dict[str, Any]) -> None:
    scenarios = snapshot.get("scenarios") if isinstance(snapshot.get("scenarios"), dict) else {}
    parity_lines = []
    for name, data in scenarios.items():
        proof = dict((data or {}).get("proof") or {})
        parity_lines.append(
            f"- {name}: identity={proof.get('selected_candidate_identity')!r}, "
            f"parity={proof.get('selected_identity_parity')}, "
            f"zero_accepted={proof.get('zero_accepted_parity')}"
        )
    failure_lines = [f"- {failure}" for failure in snapshot.get("failures", [])] or ["- None"]
    report = "\n".join(
        [
            "# Bottom Reo Selector Wrapper Proof Audit",
            "",
            f"Status: {snapshot.get('status')}",
            "",
            "## 1. Selector Proof Type Added",
            "",
            "`BottomReoSelectorWrapperProof` was added in `design_brain/families/bending.py` as a frozen proof-only family type.",
            "",
            "## 2. Selector Wrapper Helper Added",
            "",
            "`build_bottom_reo_selector_wrapper_proof(...)` was added. It consumes ranked/kept identities, selected identity, selected source/index, selected update/hash surfaces, and a small reason summary only.",
            "",
            "## 3. Selected Identity Parity Result",
            "",
            *(parity_lines or ["- No scenarios recorded."]),
            "",
            "## 4. What Remains Page-Local",
            "",
            "Live candidate dictionaries, live selector execution, CTA/action construction, one-click solver behavior, publication, UI/rendering, session state, and debug trace ownership remain page-local.",
            "",
            "## 5. Unchanged Paths Confirmation",
            "",
            "The wrapper is used only by this verifier. `inputs_page.py` was not wired to call it, so CTA/action/publication/UI/session/debug paths were not moved or changed.",
            "",
            "## 6. Next Recommended Slice",
            "",
            "If this proof remains stable, the next slice should add a page-local callsite that records this proof beside the existing selected-candidate decision trace, still without replacing live selection.",
            "",
            "## Failures",
            "",
            *failure_lines,
            "",
        ]
    )
    path.write_text(report, encoding="utf-8")


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
    trace_path = TRACE_DIR / f"bottom_reo_selector_wrapper_parity_trace_{stamp}.jsonl"

    scenarios = [
        "normal_bending_underdesign",
        "two_layer_arrangement",
        "zero_accepted_scenario",
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
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_SELECTOR_WRAPPER_{scenario}"
            results[scenario] = _run_scenario(module, scenario)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    rows = _load_jsonl(trace_path)
    failures: list[str] = []
    scenario_summary: dict[str, Any] = {}
    for scenario in scenarios:
        payload = _return_payload(rows, scenario)
        if not payload:
            failures.append(f"{scenario}:return_trace_missing")
            continue
        summary = _build_proof_from_trace(payload, scenario, failures)
        proof = dict(summary.get("proof") or {})
        page_identity = summary.get("page_local_selected_identity")
        proof_identity = proof.get("selected_candidate_identity")
        if page_identity != proof_identity:
            failures.append(f"{scenario}:selected_identity_parity_mismatch:page={page_identity!r}:proof={proof_identity!r}")
        if not proof.get("selected_identity_parity"):
            failures.append(f"{scenario}:proof_selected_identity_parity_false:{proof.get('parity_failures')!r}")
        if summary.get("input_mutated"):
            failures.append(f"{scenario}:wrapper_mutated_input_surface")
        if summary.get("forbidden_output_keys"):
            failures.append(f"{scenario}:forbidden_output_keys:{summary.get('forbidden_output_keys')!r}")
        if summary.get("live_candidate_dict_count"):
            failures.append(f"{scenario}:live_candidate_dicts_returned:{summary.get('live_candidate_dict_count')!r}")
        if scenario != "zero_accepted_scenario" and not results.get(scenario):
            failures.append(f"{scenario}:result_missing")
        if scenario == "zero_accepted_scenario":
            if results.get(scenario):
                failures.append(f"{scenario}:unexpected_result")
            if not proof.get("zero_accepted_parity"):
                failures.append(f"{scenario}:zero_accepted_parity_false")
        if scenario == "two_layer_arrangement" and "_2_16_16" not in str(proof_identity or ""):
            failures.append(f"{scenario}:selected_identity_not_two_layer:{proof_identity!r}")
        scenario_summary[scenario] = {
            "return_status": payload.get("status"),
            "return_reason": payload.get("return_reason"),
            "result_hash": _stable_hash(results.get(scenario) or {}),
            **summary,
        }

    status = "PASS" if not failures else "FAIL"
    output_path = ARTIFACT_DIR / f"bottom_reo_selector_wrapper_parity_snapshot_{stamp}.json"
    audit_path = AUDIT_DIR / f"bottom_reo_selector_wrapper_proof_audit_{stamp}.md"
    snapshot = {
        "schema": "bottom_reo_selector_wrapper_parity_snapshot.v1",
        "status": status,
        "failures": failures,
        "trace_path": str(trace_path),
        "audit_path": str(audit_path),
        "scenarios": scenario_summary,
        "trace_row_count": len(rows),
        "proof_absence_checks": {
            "cta_intent": "absent",
            "one_click_action": "absent",
            "publication_fields": "absent",
            "render_ui_fields": "absent",
            "session_debug_only_fields": "absent",
            "mutation_side_effects": "absent",
        },
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_audit_report(audit_path, snapshot)
    print(f"{status}: {output_path}")
    print(f"audit: {audit_path}")
    print(f"trace: {trace_path}")
    for failure in failures:
        print(f"- {failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
