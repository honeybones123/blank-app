"""Focused readiness snapshot for geometry recommendation engine tracing.

This verifier is synthetic readiness coverage. It exercises the real geometry
recommendation entry points with deterministic evaluator/option inputs so the
trace contract can prove candidate order, selected candidate, and no-candidate
return shape without changing product logic.
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
        "uls_Mstar": 90.0,
        "uls_Vstar": 60.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
        "design_optimisation_goal": "balanced",
        "optimisation_lock_geometry": False,
    }


def _overview(util: float = 0.89) -> dict[str, Any]:
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


def _candidate_from_state(
    candidate_state: dict[str, Any],
    *,
    seed_state: dict[str, Any],
    label: str,
    action_type: str,
    compliant: bool = True,
    score: float | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    updates = {
        key: value
        for key, value in candidate_state.items()
        if seed_state.get(key) != value and key in {"b", "bw", "D"}
    }
    width = float(candidate_state.get("b", candidate_state.get("bw", 0.0)) or 0.0)
    depth = float(candidate_state.get("D", 0.0) or 0.0)
    score_value = float(score if score is not None else (width / 100.0 + depth / 100.0))
    cid = candidate_id or f"geom_{int(width)}x{int(depth)}"
    return {
        "candidate_id": cid,
        "source_candidate_id": cid,
        "state": dict(candidate_state),
        "updates": dict(updates),
        "label": label,
        "action_type": action_type,
        "is_compliant": bool(compliant),
        "overview": _overview(0.88 if compliant else 1.08),
        "worst_util": 0.88 if compliant else 1.08,
        "width": width,
        "depth": depth,
        "score": score_value,
        "_synthetic_score": score_value,
        "required_ast": 900.0,
        "Ast_bot": 900.0,
        "bar_count": 4,
        "row_count": 1,
        "in_target_band": bool(compliant),
    }


def _run_scenario(module: Any, scenario: str) -> dict[str, Any]:
    state = _base_state()
    seed_state = dict(state)

    def _seed_candidate(_state: dict, *, source: str = "", **_: Any) -> dict[str, Any] | None:
        compliant = scenario == "geometry_tightening_selected"
        return _candidate_from_state(
            dict(_state or {}),
            seed_state=dict(_state or {}),
            label=f"seed:{source}",
            action_type="seed",
            compliant=compliant,
            score=100.0,
            candidate_id=f"{scenario}_seed",
        )

    def _evaluate_fast(
        candidate_state: dict,
        *,
        seed_state: dict,
        source: str = "",
        label: str = "",
        action_type: str = "",
        **_: Any,
    ) -> dict[str, Any] | None:
        if scenario == "geometry_no_valid_candidate":
            return None
        width = float(candidate_state.get("b", candidate_state.get("bw", 0.0)) or 0.0)
        depth = float(candidate_state.get("D", 0.0) or 0.0)
        scores = {
            (300.0, 550.0): 80.0,
            (280.0, 580.0): 60.0,
            (350.0, 600.0): 30.0,
            (320.0, 620.0): 12.0,
        }
        return _candidate_from_state(
            dict(candidate_state or {}),
            seed_state=dict(seed_state or {}),
            label=label,
            action_type=action_type,
            compliant=True,
            score=scores.get((width, depth), width / 100.0 + depth / 100.0),
            candidate_id=f"{scenario}_{int(width)}x{int(depth)}",
        )

    def _score(candidate: dict, mode_config: dict, seed_candidate: dict) -> float:
        return float(candidate.get("_synthetic_score", candidate.get("score", 100.0)) or 100.0)

    def _keep_top(candidates: list[dict], mode_config: dict, *, limit: int) -> list[dict]:
        ordered = sorted(list(candidates or []), key=lambda item: float(item.get("score", 999999.0) or 999999.0))
        return ordered[: max(int(limit), 0)]

    replacements = {
        "_guidance_state_snapshot": lambda incoming=None: dict(incoming or {}),
        "_geometry_lock_enabled": lambda incoming: False,
        "_recommendation_search_allowed": lambda incoming: True,
        "_design_optimisation_goal": lambda incoming=None: "balanced",
        "_design_mode_config": lambda goal=None: dict(_mode_config()),
        "_resolved_efficiency_target_band": lambda mode_config, **kwargs: (0.85, 1.0, False),
        "_build_auto_design_context": lambda seed, mode_config, **kwargs: {"state": dict(seed or {}), "mode_config": dict(mode_config or {})},
        "evaluate_candidate_full": _seed_candidate,
        "_evaluate_candidate_fast": _evaluate_fast,
        "_score_auto_design_candidate": _score,
        "_candidate_in_target_band": lambda candidate, mode_config: bool((candidate or {}).get("in_target_band", False)),
        "_candidate_debug_summary": lambda candidate: {
            "candidate_id": (candidate or {}).get("candidate_id"),
            "updates": dict((candidate or {}).get("updates") or {}),
            "score": (candidate or {}).get("score"),
        },
        "_geometry_tightening_trial_updates": lambda incoming: [
            {"b": 300.0, "D": 550.0},
            {"b": 280.0, "D": 580.0},
        ],
        "_resolve_geometry_width_context": lambda incoming: ("b", "width", float((incoming or {}).get("b", 300.0) or 300.0)),
        "_design_width_value": lambda incoming: float((incoming or {}).get("b", (incoming or {}).get("bw", 0.0)) or 0.0),
        "_float_from_state": lambda incoming, key, default=0.0: float((incoming or {}).get(key, default) or default),
        "_updates_match_state": lambda incoming, updates: all((incoming or {}).get(key) == value for key, value in dict(updates or {}).items()),
        "_make_auto_design_candidate_key": lambda incoming: (
            float((incoming or {}).get("b", 0.0) or 0.0),
            float((incoming or {}).get("D", 0.0) or 0.0),
        ),
        "_generate_balanced_geometry_options": lambda seed: [
            {**dict(seed.get("state") or {}), "b": 350.0, "D": 600.0},
            {**dict(seed.get("state") or {}), "b": 320.0, "D": 620.0},
        ],
        "generate_shallower_or_equal_depths": lambda seed: [],
        "generate_slightly_deeper_depths": lambda seed: [],
        "generate_same_or_larger_geometry_options": lambda seed: [],
        "_keep_top_candidates": _keep_top,
        "_evaluate_shear_with_state": lambda incoming: {"web_util": 0.52},
    }

    with _patched(module, replacements):
        if scenario == "geometry_tightening_selected":
            result = module._compute_geometry_tightening_recommendation(dict(state))
        else:
            result = module._compute_geometry_recommendation(dict(state))
    return result if isinstance(result, dict) else {}


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    trace_path = TRACE_DIR / f"geometry_recommendation_readiness_trace_9H_{stamp}.jsonl"

    scenarios = [
        "geometry_recommendation_selected",
        "geometry_tightening_selected",
        "geometry_no_valid_candidate",
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
            os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = f"GEOMETRY_READINESS_9H_{scenario}"
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
        if scenario.startswith("GEOMETRY_READINESS_9H_"):
            scenario_rows.setdefault(scenario.replace("GEOMETRY_READINESS_9H_", ""), []).append(row)

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
        if scenario != "geometry_no_valid_candidate" and not results.get(scenario):
            failures.append(f"{scenario}:result_missing")
        if scenario == "geometry_no_valid_candidate" and results.get(scenario):
            failures.append(f"{scenario}:unexpected_result")
        if scenario != "geometry_no_valid_candidate" and not candidate_rows:
            failures.append(f"{scenario}:candidate_order_trace_missing")

        return_payload = return_rows[-1].get("payload") if return_rows else {}
        candidate_payload = candidate_rows[-1].get("payload") if candidate_rows else {}
        candidate_order = candidate_payload.get("candidate_order") if isinstance(candidate_payload, dict) else {}
        selected = return_payload.get("selected_candidate") if isinstance(return_payload, dict) else {}
        scenario_summary[scenario] = {
            "route_events": route_events,
            "result_hash": _stable_hash(results.get(scenario) or {}),
            "result_update_keys": sorted(str(key) for key in dict((results.get(scenario) or {}).get("updates") or {}).keys()),
            "return_status": return_payload.get("status") if isinstance(return_payload, dict) else None,
            "return_reason": return_payload.get("return_reason") if isinstance(return_payload, dict) else None,
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
            "selected_score": return_payload.get("selected_score") if isinstance(return_payload, dict) else (
                selected.get("score") if isinstance(selected, dict) else None
            ),
        }

    expected = {
        "geometry_recommendation_selected": {
            "return_status": "selected",
            "selected_candidate_id": "geometry_recommendation_selected_320x620",
            "selected_update_keys": ["D", "b"],
        },
        "geometry_tightening_selected": {
            "return_status": "selected",
            "selected_candidate_id": "geometry_tightening_selected_280x580",
            "selected_update_keys": ["D", "b"],
        },
        "geometry_no_valid_candidate": {
            "return_status": "no_result",
            "return_reason": "no_selected_candidate",
        },
    }
    for scenario, checks in expected.items():
        observed = scenario_summary.get(scenario, {})
        for key, expected_value in checks.items():
            if observed.get(key) != expected_value:
                failures.append(f"{scenario}:{key}:expected={expected_value!r}:got={observed.get(key)!r}")

    status = "PASS" if not failures else "FAIL"
    output_path = ARTIFACT_DIR / f"geometry_recommendation_readiness_snapshot_9H_{stamp}.json"
    snapshot = {
        "schema": "geometry_recommendation_readiness_snapshot.v1",
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
