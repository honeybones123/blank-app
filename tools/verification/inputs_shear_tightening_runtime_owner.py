"""Prove typed permanent ownership and exact parity for shear tightening."""

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


def _walk_callbacks(value):
    if dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            yield from _walk_callbacks(getattr(value, field.name))
    elif isinstance(value, functools.partial):
        yield value.func
        for item in value.args:
            yield from _walk_callbacks(item)
        for item in (value.keywords or {}).values():
            yield from _walk_callbacks(item)
    elif callable(value):
        yield value


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules.design_guide.shear_tightening import (
            ShearTighteningRuntime,
            _compute_shear_tightening_recommendation,
        )
        from inputs_page_modules.guidance_compute import (
            _application_shear_no_demand_cleanup_guidance_item_if_needed,
            build_guidance_compute_runtime,
        )
        from inputs_application.recommendation_evaluation import (
            try_shear_no_demand_cleanup_recommendation,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_compute_runtime(bridge)
    callbacks = (
        guidance.guidance_action_updates.compute_shear_tightening,
        guidance.shear_local_cleanup.compute_shear_tightening_recommendation,
        (
            guidance.efficiency_tightening_state
            .compute_shear_tightening_recommendation
        ),
    )
    assert callbacks[0] is callbacks[1] is callbacks[2]
    compute = callbacks[0]
    assert isinstance(compute, functools.partial)
    assert compute.func is _compute_shear_tightening_recommendation
    runtime = compute.keywords.get("runtime")
    assert isinstance(runtime, ShearTighteningRuntime)
    assert all(
        getattr(callback, "__module__", "")
        != "inputs_page_app_contract_bridge"
        for callback in _walk_callbacks(runtime)
    )
    no_demand_recommendation = (
        guidance.compound_guidance
        .try_shear_no_demand_cleanup_recommendation
    )
    no_demand_guidance_item = (
        guidance.shear_guidance
        .shear_no_demand_cleanup_guidance_item_if_needed
    )
    assert isinstance(no_demand_recommendation, functools.partial)
    assert (
        no_demand_recommendation.func
        is try_shear_no_demand_cleanup_recommendation
    )
    assert isinstance(no_demand_guidance_item, functools.partial)
    assert (
        no_demand_guidance_item.func
        is _application_shear_no_demand_cleanup_guidance_item_if_needed
    )

    states = [
        {},
        {
            "lig_legs": 0,
            "lig_d": 0,
            "s_lig": 150.0,
            "final_shear_truth_resolved": True,
        },
        {
            "lig_legs": 2,
            "lig_d": 10,
            "s_lig": 300.0,
            "Vu_star": 0.0,
            "Tu_star": 0.0,
            "final_shear_truth_resolved": True,
        },
    ]
    for recipe_id in (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
    ):
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        states.append(build_state(recipe["changes"]))

    for state in states:
        owned_debug: dict = {}
        bridge_debug: dict = {}
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            owned = compute(
                deepcopy(state),
                out_debug=owned_debug,
            )
            compatibility = bridge._compute_shear_tightening_recommendation(
                deepcopy(state),
                out_debug=bridge_debug,
            )
        assert owned == compatibility
        assert owned_debug == bridge_debug

        design_context = runtime.build_design_actions_context(
            deepcopy(state)
        )
        overview = runtime.collect_design_overview(
            deepcopy(state),
            context=deepcopy(design_context),
        )
        actions = design_context.get("actions") or {}
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            assert no_demand_recommendation(
                deepcopy(state),
                deepcopy(overview),
                deepcopy(actions),
            ) == bridge._try_shear_no_demand_cleanup_recommendation(
                deepcopy(state),
                deepcopy(overview),
                deepcopy(actions),
            )
            assert no_demand_guidance_item(
                deepcopy(state)
            ) == bridge._shear_no_demand_cleanup_guidance_item_if_needed(
                deepcopy(state)
            )

    print(
        "PASS: all 3 shear-tightening runtime slots share one frozen "
        "permanent runtime with exact 6/6 recommendation/debug and "
        "6/6 no-demand recommendation/guidance parity"
    )


if __name__ == "__main__":
    main()
