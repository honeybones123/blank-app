"""Verify final shear selector result, mutation, and rejection-trace parity."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _candidate(
    *,
    label: str,
    updates: dict,
    shear_util,
    score: float,
) -> dict:
    return {
        "label": label,
        "updates": updates,
        "state": {
            "design_optimisation_goal": "balanced",
            "lig_d": updates.get("lig_d", 10),
            "lig_legs": updates.get("lig_legs", 2),
            "s_lig": updates.get("s_lig", 200.0),
            "D": 600.0,
            "b": 300.0,
        },
        "overview": {
            "utils": {"shear": shear_util},
            "statuses": {
                "bending": "PASS",
                "shear": "PASS",
                "crack": "PASS",
                "deflection": "PASS",
            },
        },
        "is_compliant": True,
        "score": score,
        "worst_util": shear_util,
        "candidate_post_util": shear_util,
        "target_domain_for_band": "shear",
    }


def _run_case(bridge, owned, case: dict, mode_config: dict) -> dict:
    compatibility_candidates = copy.deepcopy(case["candidates"])
    application_candidates = copy.deepcopy(case["candidates"])
    compatibility_log = []
    application_log = []
    original_logger = bridge._log_design_reco_candidate_rank
    try:
        bridge._log_design_reco_candidate_rank = (
            lambda **kwargs: compatibility_log.append(copy.deepcopy(kwargs))
        )
        compatibility = bridge._pick_best_shear_recommendation_by_selector(
            compatibility_candidates,
            state=copy.deepcopy(case["state"]),
            seed_candidate=copy.deepcopy(case["seed"]),
            mode_config=copy.deepcopy(mode_config),
            conservative=case["conservative"],
            baseline_su=case["baseline"],
        )
    finally:
        bridge._log_design_reco_candidate_rank = original_logger
    application = owned(
        application_candidates,
        state=copy.deepcopy(case["state"]),
        seed_candidate=copy.deepcopy(case["seed"]),
        mode_config=copy.deepcopy(mode_config),
        conservative=case["conservative"],
        baseline_su=case["baseline"],
        log_candidate_rank=lambda **kwargs: application_log.append(
            copy.deepcopy(kwargs)
        ),
    )
    return {
        "case": case["name"],
        "result_match": compatibility == application,
        "candidate_mutations_match": (
            compatibility_candidates == application_candidates
        ),
        "trace_match": compatibility_log == application_log,
        "compatibility_label": (compatibility or {}).get("label"),
        "application_label": (application or {}).get("label"),
    }


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.shear_recommendation_selector import (
            pick_best_shear_recommendation,
        )
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    state = {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0}
    seed = {"state": dict(state)}
    accepted = _candidate(
        label="accepted",
        updates={"s_lig": 150.0},
        shear_util=0.92,
        score=1.0,
    )
    cases = [
        {
            "name": "noop_rejected_then_accept",
            "state": state,
            "seed": seed,
            "candidates": [
                _candidate(
                    label="noop",
                    updates={"s_lig": 200.0},
                    shear_util=0.90,
                    score=0.5,
                ),
                accepted,
            ],
            "conservative": False,
            "baseline": 1.2,
        },
        {
            "name": "missing_util_rejected_then_accept",
            "state": state,
            "seed": seed,
            "candidates": [
                _candidate(
                    label="missing",
                    updates={"lig_legs": 4},
                    shear_util=None,
                    score=0.5,
                ),
                accepted,
            ],
            "conservative": False,
            "baseline": 1.2,
        },
        {
            "name": "non_improving_rejected_then_accept",
            "state": state,
            "seed": seed,
            "candidates": [
                _candidate(
                    label="not-improved",
                    updates={"lig_legs": 4},
                    shear_util=1.25,
                    score=0.5,
                ),
                accepted,
            ],
            "conservative": False,
            "baseline": 1.2,
        },
        {
            "name": "conservative_accepts_without_baseline_improvement",
            "state": state,
            "seed": seed,
            "candidates": [
                _candidate(
                    label="conservative",
                    updates={"lig_legs": 4},
                    shear_util=1.25,
                    score=0.5,
                )
            ],
            "conservative": True,
            "baseline": None,
        },
    ]
    mode_config = bridge._design_mode_config("balanced")
    rows = [
        _run_case(
            bridge,
            pick_best_shear_recommendation,
            case,
            mode_config,
        )
        for case in cases
    ]
    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "four_selector_branches_match": all(
            row["result_match"]
            and row["candidate_mutations_match"]
            and row["trace_match"]
            for row in rows
        ),
        "bridge_selector_removed_from_typed_runtime": (
            "_pick_best_shear_recommendation_by_selector" not in runtime_fields
        ),
        "application_owner_imports_no_bridge": (
            "inputs_page_app_contract_bridge"
            not in (
                ROOT
                / "inputs_application"
                / "shear_recommendation_selector.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_shear_final_selector_application_owner.v1",
        "checks": checks,
        "cases": rows,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
