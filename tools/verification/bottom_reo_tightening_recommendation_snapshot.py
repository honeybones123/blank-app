"""Focused proof snapshot for bottom reo tightening recommendations.

This verifier exercises the live `_compute_bottom_reo_tightening_recommendation(...)`
entry point with deterministic synthetic evaluator inputs. It records the
tightening candidate/filter/selection surface only; final CTA rendering, shared
CTA source precedence, publication, one-click fallback, visible wording, UI, and
session/debug fields are intentionally excluded.
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

from design_brain.families.bending import build_bottom_reo_tightening_recommendation_proof

ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"

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
    "nb_bot",
    "bot_entry",
}

FORBIDDEN_KEYS = {
    "button_label",
    "button_contract",
    "displayed_primary_button_contract",
    "primary_button_contract",
    "source_precedence",
    "selected_family_publication_gate",
    "publication",
    "published_item",
    "render",
    "rendered",
    "html",
    "visible_wording",
    "visible_blocked_wording",
    "one_click",
    "one_click_fallback",
    "session",
    "session_state",
    "debug",
    "debug_trace",
    "ui",
}


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
        "uls_Mstar": 120.0,
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


def _overview(util: float = 0.72) -> dict[str, Any]:
    return {
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": util, "shear": min(util, 0.72), "crack": 0.42, "deflection": 0.39},
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


def _arrangement_from_state(state: dict[str, Any]) -> dict[str, Any]:
    row1 = int(state.get("bot1_count", state.get("bot_row_1_bars", 0)) or 0)
    row2 = int(state.get("bot2_count", state.get("bot_row_2_bars", 0)) or 0)
    dia1 = int(state.get("db_bot_1", state.get("bot_row_1_dia", 16)) or 16)
    dia2 = int(state.get("db_bot_2", state.get("bot_row_2_dia", dia1)) or dia1)
    return {
        "bot1_count": row1,
        "bot2_count": row2,
        "db_bot_1": dia1,
        "db_bot_2": dia2,
        "row_count": 2 if row2 > 0 else 1,
        "bar_count": row1 + row2,
    }


def _ast_for(arrangement: dict[str, Any]) -> float:
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    return round(count_1 * 3.14159 * dia_1 * dia_1 / 4.0 + count_2 * 3.14159 * dia_2 * dia_2 / 4.0, 3)


def _arrangement_to_updates(arrangement: dict[str, Any]) -> dict[str, Any]:
    row1 = int(arrangement.get("bot1_count", 0) or 0)
    row2 = int(arrangement.get("bot2_count", 0) or 0)
    dia1 = int(arrangement.get("db_bot_1", 16) or 16)
    dia2 = int(arrangement.get("db_bot_2", dia1) or dia1)
    return {
        "bot1_count": row1,
        "bot2_count": row2,
        "db_bot_1": dia1,
        "db_bot_2": dia2,
        "bot_row_count": 2 if row2 > 0 else 1,
        "bot_row_1_bars": row1,
        "bot_row_1_dia": dia1,
        "bot_row_1_mode": "Count",
        "bot_row_1_spacing": 0.0,
        "bot_row_2_bars": row2,
        "bot_row_2_dia": dia2,
        "bot_row_2_mode": "Count",
        "bot_row_2_spacing": 0.0,
        "bot1_layout_mode": "Count",
        "bot2_layout_mode": "Count",
        "nb_bot": row1 + row2,
        "bot_entry": float(row1 + row2),
    }


def _candidate_id(source: str, arrangement: dict[str, Any]) -> str:
    return (
        f"{source}_{int(arrangement.get('bot1_count') or 0)}_"
        f"{int(arrangement.get('bot2_count') or 0)}_"
        f"{int(arrangement.get('db_bot_1') or 0)}_"
        f"{int(arrangement.get('db_bot_2') or 0)}"
    )


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
    arrangement = _arrangement_from_state(candidate_state)
    updates = {
        key: value
        for key, value in candidate_state.items()
        if key in BOTTOM_UPDATE_KEYS and seed_state.get(key) != value
    }
    candidate_id = _candidate_id(source, arrangement)
    ast = _ast_for(arrangement)
    return {
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
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
        "candidate_post_util": util,
        "candidate_reaches_target_band": 0.85 <= util <= 1.0,
        "candidate_distance_to_target_band": 0.0 if 0.85 <= util <= 1.0 else min(abs(util - 0.85), abs(util - 1.0)),
    }


def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    arrangement = dict(candidate.get("arrangement") or {})
    updates = dict(candidate.get("updates") or {})
    return {
        "candidate_id": candidate.get("candidate_id"),
        "label": candidate.get("label"),
        "arrangement_signature": {
            "bot1_count": arrangement.get("bot1_count"),
            "bot2_count": arrangement.get("bot2_count"),
            "db_bot_1": arrangement.get("db_bot_1"),
            "db_bot_2": arrangement.get("db_bot_2"),
            "row_count": arrangement.get("row_count"),
        },
        "updates_hash": _stable_hash(updates),
        "update_keys": sorted(str(key) for key in updates),
        "utilisation": {
            "bending": candidate.get("candidate_post_util"),
            "worst": candidate.get("worst_util"),
            "score": candidate.get("score"),
            "actual_ast": candidate.get("actual_ast"),
            "reaches_target_band": bool(candidate.get("candidate_reaches_target_band")),
        },
    }


def _walk_forbidden(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_forbidden(child))
    return found


def _scenario_arrangements(scenario: str, band: int) -> list[dict[str, Any]]:
    if scenario == "tightening_selected":
        return [
            {"bot1_count": 3, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 3},
            {"bot1_count": 2, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 2},
        ] if band == 0 else []
    if scenario == "no_tightening_no_options":
        return []
    if scenario == "spacing_blocked":
        return [
            {"bot1_count": 3, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 3},
            {"bot1_count": 2, "bot2_count": 0, "db_bot_1": 16, "db_bot_2": 16, "row_count": 1, "bar_count": 2},
        ] if band == 0 else []
    return []


def _run_scenario(module: Any, scenario: str, trace_path: Path) -> dict[str, Any]:
    state = _base_state()
    seed_state = dict(state)
    current_ast = _ast_for(_arrangement_from_state(seed_state))
    generated_options: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []

    def _seed_candidate(incoming: dict, *, source: str = "", **_: Any) -> dict[str, Any] | None:
        return _candidate_from_state(
            dict(incoming or {}),
            seed_state=dict(incoming or {}),
            source=f"{scenario}_{source}",
            label=f"seed:{source}",
            action_type="seed",
            util=0.72,
            score=100.0,
            compliant=True,
        )

    def _generate_arrangements(_state: dict, _mode_config: dict, *, band: int = 0, **_: Any) -> list[dict[str, Any]]:
        arrangements = _scenario_arrangements(scenario, band)
        for index, arrangement in enumerate(arrangements):
            generated_options.append(
                {
                    "band": band,
                    "index": index,
                    "arrangement_signature": dict(arrangement),
                    "arrangement_hash": _stable_hash(arrangement),
                    "update_hash": _stable_hash(_arrangement_to_updates(arrangement)),
                }
            )
        return [dict(item) for item in arrangements]

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
        if scenario == "spacing_blocked":
            rejected.append(
                {
                    "arrangement_signature": dict(arrangement),
                    "reason": "spacing_or_detailing_blocked",
                    "evaluator_returned": "non_compliant_candidate",
                }
            )
            return _candidate_from_state(
                dict(candidate_state or {}),
                seed_state=dict(seed_state or {}),
                source=f"{scenario}_{source}",
                label=label,
                action_type=action_type,
                util=0.90,
                score=50.0,
                compliant=False,
            )
        util_by_key = {
            (3, 0, 16): 0.89,
            (2, 0, 16): 0.70,
        }
        score_by_key = {
            (3, 0, 16): 10.0,
            (2, 0, 16): 40.0,
        }
        if key not in util_by_key:
            rejected.append(
                {
                    "arrangement_signature": dict(arrangement),
                    "reason": "evaluator_returned_none",
                    "evaluator_returned": None,
                }
            )
            return None
        candidate = _candidate_from_state(
            dict(candidate_state or {}),
            seed_state=dict(seed_state or {}),
            source=f"{scenario}_{source}",
            label=label,
            action_type=action_type,
            util=util_by_key[key],
            score=score_by_key[key],
            compliant=True,
        )
        if float(candidate.get("actual_ast") or 0.0) >= current_ast - 1e-6:
            rejected.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "arrangement_signature": dict(arrangement),
                    "reason": "not_tightening_current_ast",
                    "actual_ast": candidate.get("actual_ast"),
                    "current_ast": current_ast,
                }
            )
        else:
            accepted.append(_candidate_summary(candidate))
        return candidate

    def _updates_match_state(incoming: dict, updates: dict) -> bool:
        updates_d = dict(updates or {})
        return bool(updates_d) and all((incoming or {}).get(key) == value for key, value in updates_d.items())

    replacements = {
        "_guidance_state_snapshot": lambda incoming=None: dict(incoming or {}),
        "_design_optimisation_goal": lambda incoming=None: "balanced",
        "_design_mode_config": lambda goal=None: dict(_mode_config()),
        "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (0.85, 1.0, False),
        "_effective_bottom_design_state": lambda incoming: {"Ast_bot": current_ast},
        "evaluate_candidate_full": _seed_candidate,
        "_build_auto_design_context": lambda seed, mode_config, **kwargs: {
            "state": dict(seed or {}),
            "mode_config": dict(mode_config or {}),
        },
        "_generate_local_bottom_arrangements": _generate_arrangements,
        "_evaluate_candidate_fast": _evaluate_fast,
        "_bottom_arrangement_to_shared_updates": lambda arrangement: _arrangement_to_updates(dict(arrangement or {})),
        "_candidate_debug_summary": lambda candidate: _candidate_summary(dict(candidate or {})),
        "_practical_bottom_reo_label": lambda count_1, count_2, dia: (
            f"{int(count_1)} N{int(dia)}"
            if int(count_2 or 0) <= 0
            else f"{int(count_1)}+{int(count_2)} N{int(dia)}"
        ),
        "_updates_match_state": _updates_match_state,
        "_agent_debug_log": lambda *args, **kwargs: None,
        "_log_design_reco_candidate_rank": lambda *args, **kwargs: None,
        "_merge_design_guide_rank_trace": lambda payload: None,
    }

    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"BOTTOM_REO_TIGHTENING_{scenario}"
    with _patched(module, replacements):
        result = module._compute_bottom_reo_tightening_recommendation(dict(state))

    result_d = dict(result or {}) if isinstance(result, dict) else {}
    updates = dict(result_d.get("updates") or {})
    selected_candidate = dict(result_d.get("candidate_summary") or {})
    selected_identity = {
        "label": result_d.get("label"),
        "candidate_type": result_d.get("candidate_type"),
        "arrangement_hash": _stable_hash(result_d.get("arrangement") or {}),
        "updates_hash": _stable_hash(updates),
        "update_keys": sorted(str(key) for key in updates),
        "score": result_d.get("score"),
        "util": result_d.get("util"),
        "actual_ast": result_d.get("actual_ast"),
    } if result_d else None
    return_reason = "selected" if result_d else (
        "no_options_generated" if not generated_options else "no_valid_candidates"
    )
    proof = build_bottom_reo_tightening_recommendation_proof(
        input_design_reo_state={
            "state_hash": _stable_hash(state),
            "bottom_layout": {
                "bot1_count": state.get("bot1_count"),
                "bot2_count": state.get("bot2_count"),
                "db_bot_1": state.get("db_bot_1"),
                "db_bot_2": state.get("db_bot_2"),
                "bot_row_count": state.get("bot_row_count"),
                "current_ast": current_ast,
            },
            "target_band": {"low": 0.85, "high": 1.0},
        },
        tightening_candidate_options=list(generated_options),
        rejected_candidate_reasons=list(rejected),
        accepted_candidate_count=len(accepted),
        accepted_candidate_identities=list(accepted),
        selected_tightening_recommendation=selected_identity,
        selected_candidate_summary=selected_candidate if selected_candidate else None,
        no_recommendation_reason=None if result_d else return_reason,
        update_action_payload_identity={
            "action_kind_source": "bottom_reo_tightening_recommendation",
            "updates_hash": _stable_hash(updates),
            "update_keys": sorted(str(key) for key in updates),
            "payload_hash": _stable_hash({"updates": updates, "label": result_d.get("label")}),
        },
        utilisation_target_band_surface={
            "selected_util": result_d.get("util") if result_d else None,
            "selected_score": result_d.get("score") if result_d else None,
            "target_low": 0.85,
            "target_high": 1.0,
            "selected_reaches_target_band": (
                bool(0.85 <= float(result_d.get("util") or 0.0) <= 1.0)
                if result_d
                else False
            ),
        },
        repair_blocked_reason_source_surface={
            "reason_kind": "selected_tightening_source" if result_d else "trace_proof_only_no_tightening",
            "selected_label": result_d.get("label") if result_d else None,
            "no_recommendation_reason": None if result_d else return_reason,
            "visible_wording_materialized": False,
        },
        cta_action_intent_source_surface={
            "intent_kind": "apply_bottom_reo_tightening_updates" if result_d else "no_action",
            "action_payload_updates_hash": _stable_hash(updates),
            "final_cta_rendering_materialized": False,
            "shared_source_precedence_materialized": False,
        },
    )
    proof_surface = proof.proof_surface()
    forbidden = sorted(set(proof.forbidden_fields_present) | (_walk_forbidden(proof_surface) & FORBIDDEN_KEYS))
    proof_hash = proof.tightening_recommendation_hash
    trace_rows = [
        row
        for row in _load_jsonl(trace_path)
        if row.get("scenario") == f"BOTTOM_REO_TIGHTENING_{scenario}"
    ]
    return {
        "scenario": scenario,
        "status": "selected" if result_d else "no_result",
        "return_reason": return_reason,
        "proof_surface": proof_surface,
        "family_proof": proof.to_dict(),
        "tightening_recommendation_hash": proof_hash,
        "trace_event_count": len(trace_rows),
        "trace_events": [row.get("event") for row in trace_rows],
        "forbidden_fields_present": forbidden,
    }


def _assert_scenario(result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    scenario = str(result.get("scenario") or "")
    surface = dict(result.get("proof_surface") or {})
    if result.get("forbidden_fields_present"):
        failures.append("forbidden_fields_present:" + ",".join(result.get("forbidden_fields_present") or []))
    if not result.get("tightening_recommendation_hash"):
        failures.append("missing_tightening_recommendation_hash")
    if not result.get("trace_event_count"):
        failures.append("missing_trace_events")
    if scenario == "tightening_selected":
        if result.get("status") != "selected":
            failures.append("expected_selected_tightening")
        if not surface.get("selected_tightening_recommendation"):
            failures.append("missing_selected_tightening_recommendation")
        if not surface.get("accepted_candidate_identities"):
            failures.append("missing_accepted_candidates")
    if scenario in {"no_tightening_no_options", "spacing_blocked"}:
        if result.get("status") != "no_result":
            failures.append("expected_no_result")
        if not surface.get("no_recommendation_reason"):
            failures.append("missing_no_recommendation_reason")
    if scenario == "spacing_blocked" and not surface.get("rejected_candidate_reasons"):
        failures.append("missing_spacing_blocked_reject_reasons")
    return failures


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Bottom Reo Tightening Recommendation Snapshot",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        f"- Trace artifact: `{snapshot.get('trace_path')}`",
        "",
        "## Scope",
        "",
        "Coverage/proof only for `_compute_bottom_reo_tightening_recommendation(...)`.",
        "No product behaviour, extraction, refactor, deletion, CTA rendering, shared CTA source precedence, publication, one-click fallback, visible wording, UI/session/debug, or apply routing is changed.",
        "",
        "## Scenario Summary",
        "",
    ]
    for result in snapshot.get("scenarios") or []:
        surface = dict(result.get("proof_surface") or {})
        selected = surface.get("selected_tightening_recommendation")
        lines.extend(
            [
                f"### {result.get('scenario')}",
                "",
                f"- status: `{result.get('status')}` / `{result.get('return_reason')}`",
                f"- generated options: `{len(surface.get('tightening_candidate_options') or [])}`",
                f"- accepted count: `{surface.get('accepted_candidate_count')}`",
                f"- selected: `{selected}`",
                f"- no recommendation reason: `{surface.get('no_recommendation_reason')}`",
                f"- recommendation hash: `{result.get('tightening_recommendation_hash')}`",
                f"- forbidden fields: `{result.get('forbidden_fields_present')}`",
                f"- stability: `{(snapshot.get('stability') or {}).get(str(result.get('scenario')), {})}`",
                "",
            ]
        )
    if snapshot.get("failures"):
        lines.extend(["## Failures", ""])
        for scenario, failures in (snapshot.get("failures") or {}).items():
            lines.append(f"- {scenario}: {', '.join(failures)}")
    else:
        lines.extend(
            [
                "## Result",
                "",
                "PASS. Tightening recommendation proof surfaces are stable across repeat runs and exclude final CTA rendering, shared CTA source precedence, selected-family publication gate output, visible wording/output rendering, one-click fallback routing, UI/session/debug-only fields, and apply-routing side effects.",
                "",
                "## Recommendation",
                "",
                "Next safe move is a family-owned proof object for bottom reo tightening recommendation intent, or an audit of whether `select_bottom_reo_tightening_recommendation_result(...)` should be included in the BENDING bottom reo lock verifier.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"bottom_reo_tightening_recommendation_{stamp}.json"
    report_path = AUDIT_DIR / f"bottom_reo_tightening_recommendation_{stamp}.md"
    trace_path = TRACE_DIR / f"bottom_reo_tightening_recommendation_trace_{stamp}.jsonl"

    scenarios = ["tightening_selected", "no_tightening_no_options", "spacing_blocked"]
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
        results = [_run_scenario(module, scenario, trace_path) for scenario in scenarios]
        repeat_results = [_run_scenario(module, scenario, trace_path) for scenario in scenarios]
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    repeats = {str(item.get("scenario")): item for item in repeat_results}
    failures: dict[str, list[str]] = {}
    stability: dict[str, dict[str, Any]] = {}
    for result in results:
        scenario = str(result.get("scenario") or "")
        scenario_failures = _assert_scenario(result)
        repeat = repeats.get(scenario, {})
        same_hash = result.get("tightening_recommendation_hash") == repeat.get("tightening_recommendation_hash")
        stability[scenario] = {
            "same_tightening_recommendation_hash": same_hash,
            "first_hash": result.get("tightening_recommendation_hash"),
            "repeat_hash": repeat.get("tightening_recommendation_hash"),
        }
        if not same_hash:
            scenario_failures.append("unstable_tightening_recommendation_hash")
        if scenario_failures:
            failures[scenario] = sorted(set(scenario_failures))

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "status": status,
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "trace_path": str(trace_path),
        "schema": "bottom_reo_tightening_recommendation_snapshot.v1",
        "scope": "coverage_only_bottom_reo_tightening_recommendation",
        "coverage": {
            "overdesigned_tightening_recommendation_exists": "covered",
            "no_tightening_recommendation_exists": "covered",
            "geometry_detailing_spacing_blocks_tightening": "covered",
        },
        "scenarios": results,
        "stability": stability,
        "forbidden_keys": sorted(FORBIDDEN_KEYS),
        "assertions": {
            "product_behavior_changed": False,
            "final_cta_rendering_absent": not failures,
            "shared_cta_source_precedence_absent": not failures,
            "selected_family_publication_gate_absent": not failures,
            "visible_wording_output_rendering_absent": not failures,
            "one_click_fallback_absent": not failures,
            "ui_session_debug_only_fields_absent": not failures,
        },
        "failures": failures,
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(
        json.dumps(
            {
                "status": status,
                "artifact": str(artifact_path),
                "report": str(report_path),
                "trace": str(trace_path),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
