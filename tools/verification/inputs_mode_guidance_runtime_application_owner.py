"""Prove mode-guidance support is application-owned with exact legacy parity."""

from __future__ import annotations

import contextlib
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
            _bind_guidance_compute_runtime,
            build_guidance_compute_runtime,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance_runtime = build_guidance_compute_runtime(bridge)
    _bind_guidance_compute_runtime(
        runtime=guidance_runtime,
        st_module=bridge.st,
        os_module=bridge.os,
        sys_module=bridge.sys,
    )
    runtime = guidance_runtime.mode_guidance
    callbacks = (
        runtime.candidate_debug_summary,
        runtime.candidate_objective_util,
        runtime.materialize_full_evaluated_candidate,
        runtime.mode_guidance_focus_from_updates,
        runtime.recommendation_search_allowed,
        runtime.run_full_auto_design,
    )
    assert all(
        getattr(callback, "__module__", "")
        != "inputs_page_app_contract_bridge"
        for callback in callbacks
    )

    focus_cases = (
        ({"D": 700.0}, "geometry"),
        ({"bot1_count": 5}, "bending"),
        ({"s_lig": 150.0}, "shear"),
        ({"fc": 40.0}, "general"),
    )
    for updates, expected in focus_cases:
        assert runtime.mode_guidance_focus_from_updates(updates) == expected
        assert bridge._mode_guidance_focus_from_updates(updates) == expected

    recipe_ids = (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "MATRIX_DEFLECTION_ONLY_FAIL",
    )
    for recipe_id in recipe_ids:
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe)
        candidate = bridge._evaluate_auto_design_candidate(
            state,
            source=f"mode_owner:{recipe_id}",
        )
        assert candidate is not None, recipe_id
        assert runtime.candidate_objective_util(
            candidate
        ) == bridge._candidate_objective_util(candidate)
        assert runtime.candidate_debug_summary(
            candidate
        ) == bridge._candidate_debug_summary(candidate)
        assert runtime.recommendation_search_allowed(
            state
        ) == bridge._recommendation_search_allowed(state)

        source = f"mode_owner_materialized:{recipe_id}"
        expected = bridge._materialize_full_evaluated_candidate(
            candidate,
            source=source,
        )
        actual = runtime.materialize_full_evaluated_candidate(
            candidate,
            source=source,
        )
        assert actual == expected, recipe_id

    print(
        "PASS: all 6 mode-guidance callbacks are application-owned with "
        "exact 4/4 focus and 3/3 evaluated-candidate parity"
    )


if __name__ == "__main__":
    main()
