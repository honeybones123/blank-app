"""Prove permanent typed ownership for crack and deflection evaluation."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import functools
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules.guidance_compute import (
            _application_pick_deflection_ladder_first_improvement,
            _bind_guidance_compute_runtime,
            build_guidance_compute_runtime,
        )
        from inputs_application.crack_evaluation import (
            _evaluate_crack_with_state_for_app_bridge,
        )
        from inputs_application.deflection_evaluation import (
            _evaluate_deflection_with_state,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_compute_runtime(bridge)
    _bind_guidance_compute_runtime(
        runtime=guidance,
        st_module=bridge.st,
        os_module=bridge.os,
        sys_module=bridge.sys,
    )
    crack = guidance.crack_guidance.evaluate_crack_with_state
    deflection = guidance.deflection_guidance.evaluate_deflection_with_state
    assert isinstance(crack, functools.partial)
    assert crack.func is _evaluate_crack_with_state_for_app_bridge
    assert isinstance(deflection, functools.partial)
    assert deflection.func is _evaluate_deflection_with_state
    assert crack.func.__module__ != "inputs_page_app_contract_bridge"
    assert deflection.func.__module__ != "inputs_page_app_contract_bridge"
    deflection_picker = (
        guidance.deflection_guidance
        .pick_deflection_ladder_first_improvement
    )
    assert isinstance(deflection_picker, functools.partial)
    assert (
        deflection_picker.func
        is _application_pick_deflection_ladder_first_improvement
    )

    checks = 0
    for recipe_id in (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
    ):
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe["changes"])
        for bottom_updates in (
            None,
            {"bot1_count": 4, "db_bot_1": 20, "bot2_count": 0},
        ):
            with contextlib.redirect_stdout(
                io.StringIO()
            ), contextlib.redirect_stderr(io.StringIO()):
                assert crack(
                    deepcopy(state),
                    bottom_updates=deepcopy(bottom_updates),
                ) == bridge._evaluate_crack_with_state(
                    deepcopy(state),
                    bottom_updates=deepcopy(bottom_updates),
                )
                assert deflection(
                    deepcopy(state),
                    bottom_updates=deepcopy(bottom_updates),
                ) == bridge._evaluate_deflection_with_state(
                    deepcopy(state),
                    bottom_updates=deepcopy(bottom_updates),
                )
            checks += 2

        base_eval = bridge._evaluate_deflection_with_state(
            deepcopy(state)
        )
        base_util = float((base_eval or {}).get("util", 1.20) or 1.20)
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            assert deflection_picker(
                deepcopy(state),
                base_util=base_util,
            ) == bridge._pick_deflection_ladder_first_improvement(
                deepcopy(state),
                base_util=base_util,
            )
        checks += 1

    print(
        "PASS: crack/deflection evaluation and deflection ladder have permanent typed owners "
        f"with exact {checks}/{checks} parity"
    )


if __name__ == "__main__":
    main()
