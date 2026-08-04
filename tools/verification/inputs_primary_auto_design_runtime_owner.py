"""Prove permanent typed ownership and exact primary-search result parity."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import dataclasses
import functools
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _has_bridge_callback(value) -> bool:
    if dataclasses.is_dataclass(value):
        return any(
            _has_bridge_callback(getattr(value, field.name))
            for field in dataclasses.fields(value)
        )
    if isinstance(value, functools.partial):
        return (
            _has_bridge_callback(value.func)
            or any(_has_bridge_callback(item) for item in value.args)
            or any(
                _has_bridge_callback(item)
                for item in (value.keywords or {}).values()
            )
        )
    return bool(
        callable(value)
        and getattr(value, "__module__", "")
        == "inputs_page_app_contract_bridge"
    )


def _metrics(seed: dict) -> dict:
    return {
        "generated_count": 0,
        "unique_eval_count": 0,
        "cache_hits": 0,
        "fast_eval_total_ms": 0.0,
        "candidate_generation_ms": 0.0,
        "pruning_total_ms": 0.0,
        "solve_reo_total_ms": 0.0,
        "kept_count": 0,
        "cap_hit": False,
        "_reference_overview": deepcopy(seed.get("overview") or {}),
    }


def _stable_metrics(metrics: dict) -> dict:
    return {
        key: value
        for key, value in metrics.items()
        if not key.endswith("_ms")
    }


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.primary_auto_design import (
            PrimaryAutoDesignRuntime,
            run_primary_auto_design,
        )
        from inputs_page_modules.guidance_compute import (
            build_guidance_compute_runtime,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_compute_runtime(bridge)
    owned = guidance.auto_design_solver.run_primary_auto_design
    assert isinstance(owned, functools.partial)
    assert owned.func is run_primary_auto_design
    runtime = owned.keywords.get("runtime")
    assert isinstance(runtime, PrimaryAutoDesignRuntime)
    assert not _has_bridge_callback(runtime)

    cases = (
        ("R1A_M300_V0", "balanced"),
        ("R2A_M0_V400", "shallower_beam"),
        ("R4A_M45_V0", "low_reinforcement"),
    )
    checked = 0
    for recipe_name, goal in cases:
        recipe = find_named_case(recipe_name)
        assert recipe is not None, recipe_name
        state = build_state(
            {
                **recipe["changes"],
                "design_optimisation_goal": goal,
            }
        )
        mode_config = bridge._design_mode_config(goal)
        seed = bridge._evaluate_auto_design_candidate(
            deepcopy(state),
            source=f"primary_parity_seed_{recipe_name}",
        )
        assert isinstance(seed, dict), recipe_name
        compatibility_metrics = _metrics(seed)
        owned_metrics = _metrics(seed)
        compatibility = bridge.run_primary_auto_design(
            deepcopy(seed),
            deepcopy(mode_config),
            {},
            compatibility_metrics,
            is_first_hop=True,
        )
        result = owned(
            deepcopy(seed),
            deepcopy(mode_config),
            {},
            owned_metrics,
            is_first_hop=True,
        )
        assert result == compatibility, (
            recipe_name,
            result,
            compatibility,
        )
        assert _stable_metrics(owned_metrics) == _stable_metrics(
            compatibility_metrics
        ), (
            recipe_name,
            _stable_metrics(owned_metrics),
            _stable_metrics(compatibility_metrics),
        )
        checked += 1

    print(
        "PASS: primary auto-design search has one frozen permanent runtime "
        f"with exact {checked}/{len(cases)} result and stable-metrics parity"
    )


if __name__ == "__main__":
    main()
