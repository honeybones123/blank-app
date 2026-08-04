"""Prove shared guidance dependencies use permanent application owners."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        from calculations.design_actions import (
            resolve_design_actions_from_state,
        )
        from design_brain.candidate_evaluation import (
            resolve_distance_to_target_band,
        )
        from inputs_application.candidate_metrics import (
            candidate_bottom_updates,
        )
        from inputs_application.geometry_search_policy import (
            geometry_lock_enabled,
            geometry_state_with_updates,
        )
        from inputs_application.guidance_runtime_provider import (
            build_guidance_runtime_provider,
        )
        from inputs_application.recommendation_evaluation import (
            effective_bottom_design_state,
        )
        from inputs_application.recommendation_primitives import (
            bottom_arrangement_to_shared_updates,
            candidate_is_growth_move,
        )
        from inputs_application.recommendation_support import (
            design_width_value,
        )
        from inputs_page_modules.design_guide.guidance_item_dedupe import (
            _family_tag_from_compound_updates,
        )
        from inputs_page_modules.guidance_compute import (
            _application_distance_to_target_band,
            _bottom_arrangement_to_shared_updates_owned,
            _candidate_bottom_updates_owned,
            _candidate_is_growth_move_owned,
            _design_width_value_owned,
            _effective_bottom_design_state_owned,
            _family_tag_from_compound_updates_owned,
            _geometry_lock_enabled_owned,
            _geometry_state_with_updates_owned,
            _mode_recommendation_search_allowed,
            _resolve_design_actions_from_state,
            build_guidance_compute_runtime,
            evaluate_candidate_full,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    runtime = build_guidance_compute_runtime(
        build_guidance_runtime_provider(SimpleNamespace(session_state={}))
    )

    identity_groups = (
        (
            _bottom_arrangement_to_shared_updates_owned,
            runtime.guidance_action_updates.bottom_arrangement_to_shared_updates,
            runtime.compound_guidance.bottom_arrangement_to_shared_updates,
            runtime.auto_design_solver._bottom_arrangement_to_shared_updates,
        ),
        (
            _effective_bottom_design_state_owned,
            runtime.shear_congestion_reshape.effective_bottom_design_state,
            runtime.efficiency_tightening_state.effective_bottom_design_state,
        ),
        (
            _geometry_lock_enabled_owned,
            runtime.efficiency_guidance.geometry_lock_enabled,
            runtime.shear_congestion_reshape.geometry_lock_enabled,
            runtime.compound_guidance.geometry_lock_enabled,
            runtime.efficiency_tightening_state.geometry_lock_enabled,
            runtime.auto_design_solver._geometry_lock_enabled,
        ),
        (
            _resolve_design_actions_from_state,
            runtime.family_ladder_guidance.resolve_design_actions_from_state,
            runtime.efficiency_guidance.resolve_design_actions_from_state,
            runtime.local_cleanup_promotion.resolve_design_actions_from_state,
            runtime.shear_local_cleanup.resolve_design_actions_from_state,
            runtime.efficiency_tightening_state.resolve_design_actions_from_state,
        ),
        (
            evaluate_candidate_full,
            runtime.actionable_target_band_winner.evaluate_candidate_full,
            runtime.one_click_band_candidate.evaluate_candidate_full,
            runtime.compound_guidance.evaluate_candidate_full,
            runtime.efficiency_tightening_state.evaluate_candidate_full,
            runtime.auto_design_solver.evaluate_candidate_full,
        ),
        (
            _design_width_value_owned,
            runtime.family_ladder_guidance.design_width_value,
            runtime.auto_design_solver._design_width_value,
        ),
        (
            _application_distance_to_target_band,
            runtime.family_ladder_guidance.distance_to_target_band,
            runtime.shear_congestion_reshape.distance_to_target_band,
            runtime.primary_optimisation_selector.distance_to_target_band,
            runtime.shear_local_cleanup.distance_to_target_band,
        ),
        (
            _family_tag_from_compound_updates_owned,
            runtime.family_ladder_guidance.family_tag_from_compound_updates,
        ),
        (
            _candidate_is_growth_move_owned,
            runtime.compound_guidance.candidate_is_growth_move,
            runtime.efficiency_tightening_state.candidate_is_growth_move,
        ),
        (
            _mode_recommendation_search_allowed,
            runtime.actionable_target_band_winner.recommendation_search_allowed,
            runtime.compound_guidance.recommendation_search_allowed,
        ),
    )
    assert all(
        callback is owner
        for owner, *callbacks in identity_groups
        for callback in callbacks
    )

    arrangements = (
        {"bot1_count": 4, "db_bot_1": 20},
        {
            "bot1_count": 3,
            "db_bot_1": 24,
            "bot2_count": 2,
            "db_bot_2": 20,
        },
        {},
    )
    for arrangement in arrangements:
        assert _bottom_arrangement_to_shared_updates_owned(
            arrangement
        ) == bottom_arrangement_to_shared_updates(arrangement)
        assert _candidate_bottom_updates_owned(
            arrangement
        ) == candidate_bottom_updates(arrangement)

    for shape_state in (
        {"sec_shape": "RECT", "b": 350.0},
        {"sec_shape": "T", "bw": 280.0, "b": 900.0},
        {"sec_shape": "I", "tw": 240.0, "b": 850.0},
    ):
        assert _design_width_value_owned(
            shape_state
        ) == design_width_value(shape_state)
        for depth, width in ((None, None), (650.0, None), (None, 420.0)):
            assert _geometry_state_with_updates_owned(
                shape_state,
                depth=depth,
                width=width,
            ) == geometry_state_with_updates(
                shape_state,
                depth=depth,
                width=width,
            )

    for values in (
        (0.4, 0.6, 0.9),
        (0.75, 0.6, 0.9),
        (1.1, 0.6, 0.9),
        ("bad", 0.6, 0.9),
    ):
        assert _application_distance_to_target_band(
            *values
        ) == resolve_distance_to_target_band(*values)

    recipe_ids = (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "MATRIX_DEFLECTION_ONLY_FAIL",
    )
    for recipe_id in recipe_ids:
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe)
        assert _effective_bottom_design_state_owned(
            state
        ) == effective_bottom_design_state(state)
        assert _geometry_lock_enabled_owned(
            state
        ) == geometry_lock_enabled(state)
        assert _resolve_design_actions_from_state(
            state
        ) == resolve_design_actions_from_state(state)

    baseline = {"D": 600.0, "b": 300.0, "Ast_bot": 1500.0}
    for candidate in (
        {"state": {"D": 600.0, "b": 300.0, "Ast_bot": 1500.0}},
        {"state": {"D": 650.0, "b": 300.0, "Ast_bot": 1500.0}},
        {"state": {"D": 600.0, "b": 300.0, "Ast_bot": 1700.0}},
    ):
        seed = {"state": baseline}
        assert _candidate_is_growth_move_owned(
            seed,
            candidate,
        ) == candidate_is_growth_move(seed, candidate)

    for updates in (
        {"D": 650.0, "bot1_count": 5},
        {"b": 350.0, "bot1_count": 5},
        {"s_lig": 150.0, "bot1_count": 5},
        {"D": 650.0, "s_lig": 150.0},
    ):
        assert _family_tag_from_compound_updates_owned(
            updates,
            baseline,
        ) == _family_tag_from_compound_updates(updates, baseline)

    print(
        "PASS: guidance runtime bindings use permanent shared owners with "
        "exact arrangement, width, distance, bottom-state, geometry-lock, "
        "and action-resolution parity"
    )


if __name__ == "__main__":
    main()
