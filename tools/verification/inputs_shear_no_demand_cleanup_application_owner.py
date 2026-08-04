"""Prove the application-owned shear no-demand cleanup matches compatibility behavior."""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_application.recommendation_evaluation as owned
import inputs_page_app_contract_bridge as bridge


def _normalise(value):
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    if isinstance(value, dict):
        return {key: _normalise(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalise(item) for item in value]
    return value


def _run_case(case: dict) -> dict:
    # The recommendation coordinator normalises state before either policy is called.
    state = bridge._guidance_state_snapshot(copy.deepcopy(case["state"]))
    overview = copy.deepcopy(case["overview"])
    actions = copy.deepcopy(case["actions"])
    candidate = copy.deepcopy(case.get("candidate"))
    preview = copy.deepcopy(case.get("preview") or {})

    legacy_trace: list[dict] = []
    owned_trace: list[dict] = []
    legacy_evaluations: list[dict] = []
    owned_evaluations: list[dict] = []

    def _legacy_evaluate(candidate_state, **kwargs):
        legacy_evaluations.append(
            {"state": copy.deepcopy(candidate_state), "kwargs": copy.deepcopy(kwargs)}
        )
        return copy.deepcopy(candidate)

    def _owned_evaluate(candidate_state, **kwargs):
        owned_evaluations.append(
            {"state": copy.deepcopy(candidate_state), "kwargs": copy.deepcopy(kwargs)}
        )
        return copy.deepcopy(candidate)

    originals = {
        "evaluate": bridge.evaluate_candidate_full,
        "merge": bridge._merge_design_guide_rank_trace,
        "preview": bridge._evaluate_shear_with_state,
        "owned_preview": owned.evaluate_shear_with_state,
    }
    try:
        bridge.evaluate_candidate_full = _legacy_evaluate
        bridge._merge_design_guide_rank_trace = lambda payload: legacy_trace.append(
            copy.deepcopy(payload)
        )
        bridge._evaluate_shear_with_state = lambda candidate_state: copy.deepcopy(preview)
        owned.evaluate_shear_with_state = lambda candidate_state: copy.deepcopy(preview)

        legacy_result = bridge._try_shear_no_demand_cleanup_recommendation(
            copy.deepcopy(state),
            copy.deepcopy(overview),
            copy.deepcopy(actions),
        )
        owned_result = owned.try_shear_no_demand_cleanup_recommendation(
            copy.deepcopy(state),
            copy.deepcopy(overview),
            copy.deepcopy(actions),
            evaluate_candidate_full=_owned_evaluate,
            merge_rank_trace=lambda payload: owned_trace.append(copy.deepcopy(payload)),
        )
    finally:
        bridge.evaluate_candidate_full = originals["evaluate"]
        bridge._merge_design_guide_rank_trace = originals["merge"]
        bridge._evaluate_shear_with_state = originals["preview"]
        owned.evaluate_shear_with_state = originals["owned_preview"]

    return {
        "name": case["name"],
        "result_equal": _normalise(legacy_result) == _normalise(owned_result),
        "trace_equal": _normalise(legacy_trace) == _normalise(owned_trace),
        "evaluation_calls_equal": _normalise(legacy_evaluations)
        == _normalise(owned_evaluations),
        "legacy_result": _normalise(legacy_result),
        "owned_result": _normalise(owned_result),
    }


def main() -> int:
    active_state = {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0}
    negligible_actions = {"Vu": 0.0, "Tu": 0.0}
    cases = [
        {
            "name": "non_negligible_actions",
            "state": active_state,
            "overview": {"utils": {"shear": 0.01}},
            "actions": {"Vu": 1.0, "Tu": 0.0},
        },
        {
            "name": "links_already_inactive",
            "state": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            "overview": {"utils": {"shear": 0.01}},
            "actions": negligible_actions,
        },
        {
            "name": "util_above_cleanup_threshold",
            "state": active_state,
            "overview": {"utils": {"shear": 0.081}},
            "actions": negligible_actions,
        },
        {
            "name": "noncompliant_cleanup_candidate",
            "state": active_state,
            "overview": {"utils": {"shear": float("nan")}},
            "actions": negligible_actions,
            "candidate": {"is_compliant": False},
        },
        {
            "name": "accepted_cleanup_candidate",
            "state": active_state,
            "overview": {"utils": {"shear": 0.02}},
            "actions": negligible_actions,
            "candidate": {
                "is_compliant": True,
                "state": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
                "overview": {"utils": {"shear": 0.015}},
            },
            "preview": {"web_util": 0.4, "phi_vu": 123.0, "veq": 49.2},
        },
    ]
    results = [_run_case(case) for case in cases]
    passed = all(
        result["result_equal"]
        and result["trace_equal"]
        and result["evaluation_calls_equal"]
        for result in results
    )
    print(
        json.dumps(
            {
                "status": "PASS" if passed else "FAIL",
                "cases": results,
                "application_owner": "inputs_application.recommendation_evaluation.try_shear_no_demand_cleanup_recommendation",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
