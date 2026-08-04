"""Prove exact tightening and target-band next-hop runtime ownership."""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RECIPE_IDS = (
    "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
    "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
    "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
)


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st
        import inputs_page_app_contract_bridge as legacy

        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
        )
        from inputs_application.one_click_runtime_provider import (
            build_partial_one_click_runtime_provider,
            missing_one_click_runtime_dependencies,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_entrypoint_runtime(
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    provider = build_partial_one_click_runtime_provider(
        st_module=st,
        guidance_runtime=guidance,
    )
    assert missing_one_click_runtime_dependencies(provider) == ()

    checked = 0
    for recipe_id in RECIPE_IDS:
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe["changes"])
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            mode = legacy._design_mode_config(
                legacy._design_optimisation_goal(state)
            )
            current_eval = legacy._evaluate_auto_design_candidate(
                state,
                source="final_runtime_owner_verifier",
            )
            expected_tightening = (
                legacy._generate_tightening_candidates_for_governing_domain(
                    state,
                    current_eval,
                    mode,
                )
            )
            actual_tightening = (
                provider
                ._generate_tightening_candidates_for_governing_domain(
                    state,
                    current_eval,
                    mode,
                )
            )
            expected_next = (
                legacy._one_click_best_next_hop_improving_candidate(
                    current_eval,
                    mode,
                )
            )
            actual_next = (
                provider._one_click_best_next_hop_improving_candidate(
                    current_eval,
                    mode,
                )
            )
            expected_budget = (
                legacy._one_click_budget_stop_has_better_next_hop(
                    current_eval,
                    mode,
                )
            )
            actual_budget = (
                provider._one_click_budget_stop_has_better_next_hop(
                    current_eval,
                    mode,
                )
            )
        assert actual_tightening == expected_tightening, recipe_id
        assert actual_next == expected_next, recipe_id
        assert actual_budget == expected_budget, recipe_id
        checked += 1

    print(
        "PASS: final one-click tightening, next-hop, and budget-stop "
        f"owners have exact {checked}/{len(RECIPE_IDS)} recipe parity"
    )


if __name__ == "__main__":
    main()
