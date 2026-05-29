"""Frozen clean-start recipes for one-click optimisation/regression work.

This harness is intentionally narrow:
- It freezes one common base beam plus exact reproduction deltas.
- Each run imports `inputs_page` fresh to avoid cross-run module/session drift.
- It reports seed truth, solver truth, and committed recompute truth separately.

Usage:
    python tools/one_click_recipe_regression.py --list
    python tools/one_click_recipe_regression.py --case R5_combined_underdesign
    python tools/one_click_recipe_regression.py --case R5_combined_underdesign --repeat 2
    python tools/one_click_recipe_regression.py --matrix
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import logging
import math
import os
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verification.recipes.one_click_recipe_defs import (
    BASE_BEAM,
    FROZEN_RECIPES,
    REGRESSION_CASES,
    RUNNABLE_RECIPES,
    TARGET_BAND,
    build_state,
)


EXPECTED_SEED_STATUSES: dict[str, dict[str, str]] = {
    "A_bending_under_only": {"bending": "FAIL", "shear": "PASS"},
    "B_shear_under_only": {"bending": "PASS", "shear": "FAIL"},
    "C_combined_underdesign": {"bending": "FAIL", "shear": "FAIL"},
    "D_bending_overdesign": {"bending": "PASS", "shear": "PASS"},
    "E_shear_overdesign": {"bending": "PASS", "shear": "PASS"},
    "F_combined_overdesign": {"bending": "PASS", "shear": "PASS"},
    "R1A_M300_V0": {"bending": "FAIL", "shear": "PASS"},
    "R1B_M600_V0": {"bending": "FAIL", "shear": "PASS"},
    "R2A_M0_V400": {"bending": "PASS", "shear": "FAIL"},
    "R2B_M0_V600": {"bending": "PASS", "shear": "FAIL"},
    "R3A_M300_V400": {"bending": "FAIL", "shear": "FAIL"},
    "R3B_M600_V600": {"bending": "FAIL", "shear": "FAIL"},
    "R4A_M45_V0": {"bending": "PASS", "shear": "PASS"},
    "R4B_M55_V0": {"bending": "PASS", "shear": "PASS"},
    "R5A_M0_V150": {"bending": "PASS", "shear": "PASS"},
    "R5B_M0_V200": {"bending": "PASS", "shear": "PASS"},
    "R6A_M45_V150": {"bending": "PASS", "shear": "PASS"},
}


ACCEPTABLE_CONSTRAINED_STOP_REASONS = {
    "minimum_geometry_limit",
    "minimum_section_limit",
    "minimum_constructability_limit",
    "minimum_bar_arrangement_limit",
    "minimum_shear_detailing_limit",
    "minimum_shear_reinforcement_limit",
}


def _repo_root() -> Path:
    return REPO_ROOT


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _is_finite_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def _in_target_band(value: Any) -> bool:
    if not _is_finite_number(value):
        return False
    number = float(value)
    return TARGET_BAND["min"] <= number <= TARGET_BAND["max"]


def _import_inputs_page_fresh():
    os.environ.setdefault("STREAMLIT_LOG_LEVEL", "error")
    logging.getLogger("streamlit").setLevel(logging.ERROR)
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    sys.modules.pop("inputs_page", None)
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        return importlib.import_module("inputs_page")


def evaluate_case(changes: dict[str, Any], *, max_steps: int = 6) -> dict[str, Any]:
    inputs_page = _import_inputs_page_fresh()
    seed_state = build_state(changes)
    seed_eval = inputs_page.evaluate_candidate_full(seed_state)
    solver = inputs_page._solve_one_click_to_target(  # noqa: SLF001 - intentional regression harness
        seed_state,
        max_steps=max_steps,
        debug_enabled=False,
        trace_run_id=None,
        trace_source="recipe_regression",
    )

    final_updates = dict(solver.get("final_updates") or {})
    committed_state = build_state(changes)
    committed_state.update(final_updates)
    committed_state = inputs_page._build_canonical_design_state_pack(committed_state)  # noqa: SLF001
    committed_eval = inputs_page.evaluate_candidate_full(committed_state)

    seed_overview = dict((seed_eval or {}).get("overview") or {})
    committed_overview = dict((committed_eval or {}).get("overview") or {})
    solver_debug = dict(solver.get("one_click_solver_debug") or {})
    final_trace = dict(solver_debug.get("final_eval_band_trace") or {})

    return _json_safe(
        {
            "target_band": dict(TARGET_BAND),
            "seed_overview": {
                "worst_util": seed_overview.get("worst_util"),
                "statuses": dict(seed_overview.get("statuses") or {}),
                "utils": dict(seed_overview.get("utils") or {}),
                "all_key_pass": seed_overview.get("all_key_pass"),
            },
            "solver_result": {
                "status": solver.get("status"),
                "stop_reason": solver.get("stop_reason"),
                "step_count": solver.get("step_count"),
                "reached_target_band": solver.get("reached_target_band"),
                "all_key_pass": solver.get("all_key_pass"),
                "final_updates": final_updates,
            },
            "final_trace": final_trace,
            "committed_overview": {
                "worst_util": committed_overview.get("worst_util"),
                "statuses": dict(committed_overview.get("statuses") or {}),
                "utils": dict(committed_overview.get("utils") or {}),
                "all_key_pass": committed_overview.get("all_key_pass"),
            },
        }
    )


def run_case_repeats(changes: dict[str, Any], *, repeat: int, max_steps: int = 6) -> list[dict[str, Any]]:
    return [evaluate_case(changes, max_steps=max_steps) for _ in range(repeat)]


def _verify_single_run(case_name: str, run: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    seed_statuses = dict((run.get("seed_overview") or {}).get("statuses") or {})
    committed = dict(run.get("committed_overview") or {})
    committed_statuses = dict(committed.get("statuses") or {})
    final_trace = dict(run.get("final_trace") or {})
    solver_result = dict(run.get("solver_result") or {})

    expected_seed = EXPECTED_SEED_STATUSES.get(case_name)
    if expected_seed:
        for domain, expected in expected_seed.items():
            actual = str(seed_statuses.get(domain))
            if actual != expected:
                issues.append(f"seed_status[{domain}] expected {expected} got {actual}")

    final_worst = committed.get("worst_util")
    if not _in_target_band(final_worst):
        stop_reason = str(solver_result.get("stop_reason") or "")
        if stop_reason not in ACCEPTABLE_CONSTRAINED_STOP_REASONS:
            issues.append(
                f"final_worst_util out of band ({final_worst}) without acceptable constrained stop "
                f"({stop_reason or 'missing'})"
            )

    if solver_result.get("status") not in {"solved", "blocked"}:
        issues.append(f"unexpected solver status {solver_result.get('status')}")

    if committed.get("all_key_pass") is not True and str(solver_result.get("stop_reason") or "") not in ACCEPTABLE_CONSTRAINED_STOP_REASONS:
        issues.append("final committed overview is not all_key_pass")

    if str(solver_result.get("stop_reason") or "") == "reached_target_band" and solver_result.get("reached_target_band") is not True:
        issues.append("solver stop reason says reached_target_band but solver flag is false")

    if str(solver_result.get("stop_reason") or "") == "reached_target_band" and not _in_target_band(final_worst):
        issues.append("solver stop reason says reached_target_band but committed worst util is out of band")

    trace_max = final_trace.get("domain_max_distance")
    if str(solver_result.get("stop_reason") or "") == "reached_target_band" and _is_finite_number(trace_max) and float(trace_max) > 1e-9:
        issues.append(f"final trace domain_max_distance expected 0 got {trace_max}")

    required_fail_count = final_trace.get("required_fail_count")
    if required_fail_count not in (None, 0):
        issues.append(f"final trace required_fail_count expected 0 got {required_fail_count}")

    required_unsatisfied_count = final_trace.get("required_unsatisfied_count")
    if required_unsatisfied_count not in (None, 0):
        issues.append(f"final trace required_unsatisfied_count expected 0 got {required_unsatisfied_count}")

    for domain in ("bending", "shear"):
        actual = str(committed_statuses.get(domain) or "")
        if actual and actual != "PASS" and str(solver_result.get("stop_reason") or "") not in ACCEPTABLE_CONSTRAINED_STOP_REASONS:
            issues.append(f"committed status for {domain} expected PASS got {actual}")

    return issues


def verify_runs(case_name: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    serialized = [json.dumps(_json_safe(run), sort_keys=True) for run in runs]
    deterministic = len(set(serialized)) <= 1
    run_issues = []
    for index, run in enumerate(runs, start=1):
        issues = _verify_single_run(case_name, run)
        run_issues.append({"run": index, "issues": issues, "ok": not issues})
    return {
        "case": case_name,
        "repeat": len(runs),
        "deterministic": deterministic,
        "ok": deterministic and all(item["ok"] for item in run_issues),
        "runs": run_issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List frozen recipes and regression cases.")
    parser.add_argument("--case", type=str, help="Run a single regression case by name.")
    parser.add_argument("--recipe", type=str, help="Show a frozen recipe definition by name.")
    parser.add_argument("--recipe-run", type=str, help="Run a single frozen recipe/subcase by runnable name.")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--matrix", action="store_true", help="Run the auxiliary six-case regression matrix once.")
    parser.add_argument("--verify-core", action="store_true", help="Run and verify the six core regression cases.")
    parser.add_argument("--verify-recipes", action="store_true", help="Run and verify the frozen recipe family cases.")
    parser.add_argument("--verify-all", action="store_true", help="Run and verify both the core cases and the frozen recipe family cases.")
    args = parser.parse_args(argv)

    runnable_recipes = RUNNABLE_RECIPES

    if args.list:
        print(
            json.dumps(
                {
                    "base_beam": BASE_BEAM,
                    "frozen_recipes": FROZEN_RECIPES,
                    "runnable_recipes": runnable_recipes,
                    "regression_cases": REGRESSION_CASES,
                },
                indent=2,
            )
        )
        return 0

    if args.recipe:
        match = next((r for r in FROZEN_RECIPES if r["name"] == args.recipe), None)
        if match is None:
            raise SystemExit(f"Unknown recipe: {args.recipe}")
        print(json.dumps(match, indent=2))
        return 0

    if args.recipe_run:
        match = next((r for r in runnable_recipes if r["name"] == args.recipe_run), None)
        if match is None:
            raise SystemExit(f"Unknown runnable recipe: {args.recipe_run}")
        print(
            json.dumps(
                {
                    "recipe_run": match["name"],
                    "recipe_name": match["recipe_name"],
                    "runs": run_case_repeats(match["changes"], repeat=args.repeat, max_steps=args.max_steps),
                },
                indent=2,
            )
        )
        return 0

    if args.case:
        match = next((c for c in REGRESSION_CASES if c["name"] == args.case), None)
        if match is None:
            raise SystemExit(f"Unknown case: {args.case}")
        print(json.dumps({"case": match["name"], "runs": run_case_repeats(match["changes"], repeat=args.repeat, max_steps=args.max_steps)}, indent=2))
        return 0

    if args.matrix:
        matrix = {
            case["name"]: run_case_repeats(case["changes"], repeat=args.repeat, max_steps=args.max_steps)
            for case in REGRESSION_CASES
        }
        print(json.dumps(matrix, indent=2))
        return 0

    if args.verify_core or args.verify_recipes or args.verify_all:
        selections: list[tuple[str, dict[str, Any]]] = []
        if args.verify_core or args.verify_all:
            selections.extend((case["name"], case["changes"]) for case in REGRESSION_CASES)
        if args.verify_recipes or args.verify_all:
            selections.extend((recipe["name"], recipe["changes"]) for recipe in runnable_recipes)
        verification = {}
        failed = False
        for name, changes in selections:
            runs = run_case_repeats(changes, repeat=args.repeat, max_steps=args.max_steps)
            verification[name] = {
                "result": verify_runs(name, runs),
                "raw_runs": runs,
            }
            if not verification[name]["result"]["ok"]:
                failed = True
        print(json.dumps(verification, indent=2))
        return 1 if failed else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
