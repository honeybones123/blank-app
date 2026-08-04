"""Prove the bottom recommendation route no longer reaches the legacy bridge."""

from __future__ import annotations

import contextlib
import copy
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    route = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8"
    )
    runtime = (
        ROOT / "inputs_page_modules" / "recommendation_runtime.py"
    ).read_text(encoding="utf-8")
    assert "_legacy_inputs_page._compute_bottom_reo_recommendation" not in route
    assert "compute_bottom_recommendation_for_page(" in route
    assert "inputs_page_app_contract_bridge" not in runtime
    assert "inputs_page_route_coordinators" not in runtime
    assert "BottomRecommendationRuntime(" in runtime
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules.recommendation_runtime import (
            compute_bottom_recommendation_for_page,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    session_state = dict(bridge.st.session_state)
    for recipe_id in (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
    ):
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe["changes"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            compatibility = bridge._compute_bottom_reo_recommendation(
                copy.deepcopy(state)
            )
            replacement = compute_bottom_recommendation_for_page(
                copy.deepcopy(state),
                session_state=session_state,
            )
        assert replacement == compatibility, recipe_id
    print(
        "PASS: bottom route uses trace/compound/evaluation/scoring/selector "
        "typed services with exact 3/3 payload parity"
    )


if __name__ == "__main__":
    main()
