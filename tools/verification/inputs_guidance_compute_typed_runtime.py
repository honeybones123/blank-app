"""Lock Design Guide compute to its explicit family-first typed runtime."""

from __future__ import annotations

import contextlib
import copy
from dataclasses import is_dataclass
import inspect
import io
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


EXPECTED_RUNTIME_TYPES = {
    "bending_guidance": "BendingGuidanceRuntime",
    "mode_guidance": "ModeGuidanceRuntime",
    "crack_guidance": "CrackGuidanceRuntime",
    "deflection_guidance": "DeflectionGuidanceRuntime",
    "family_ladder_guidance": "FamilyLadderGuidanceRuntime",
    "efficiency_guidance": "EfficiencyGuidanceRuntime",
    "actionable_target_band_winner": "ActionableTargetBandWinnerRuntime",
    "one_click_band_candidate": "OneClickBandCandidateRuntime",
    "guidance_action_updates": "GuidanceActionUpdateRuntime",
    "resolved_candidate_guidance": "ResolvedCandidateGuidanceRuntime",
    "shear_congestion_reshape": "ShearCongestionReshapeRuntime",
    "local_cleanup_promotion": "LocalCleanupPromotionRuntime",
    "accepted_green_audit": "AcceptedGreenAuditRuntime",
    "executor_contract_sanitizer": "ExecutorContractSanitizerRuntime",
    "primary_optimisation_selector": "PrimaryOptimisationSelectorRuntime",
    "shear_guidance": "ShearGuidanceRuntime",
    "shear_local_cleanup": "ShearLocalCleanupRuntime",
    "compound_guidance": "CompoundGuidanceRuntime",
    "efficiency_tightening_state": "EfficiencyTighteningStateRuntime",
    "auto_design_solver": "AutoDesignSolverRuntime",
}


def _compute_for_state(state: dict) -> dict:
    import streamlit as st

    from inputs_application.guidance_runtime_provider import (
        build_guidance_runtime_provider,
    )
    from inputs_page_modules.guidance_compute import (
        build_guidance_compute_runtime,
        compute_design_guidance_items,
    )

    try:
        st.session_state.clear()
    except Exception:
        pass
    runtime = build_guidance_compute_runtime(
        build_guidance_runtime_provider(st)
    )
    return compute_design_guidance_items(
        runtime,
        st,
        os,
        sys,
        copy.deepcopy(state),
        guidance_debug_verbose=False,
        debug_enabled=False,
    )


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from inputs_application.guidance_runtime_provider import (
            build_guidance_runtime_provider,
        )
        from inputs_page_modules.guidance_compute import (
            GuidanceComputeRuntime,
            build_guidance_compute_runtime,
            compute_design_guidance_items,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    source = (
        ROOT / "inputs_page_modules" / "guidance_compute.py"
    ).read_text(encoding="utf-8")
    assert "inputs_page_app_contract_bridge" not in source
    assert "_LEGACY_COMPUTE_NAMES" not in source
    assert "one_click_candidate_solver" not in source
    assert "shear_fallback_candidate" not in source
    assert "direct_target_band_guidance" not in source
    assert "family_ladder_guidance" in source

    assert is_dataclass(GuidanceComputeRuntime)
    assert GuidanceComputeRuntime.__dataclass_params__.frozen
    assert tuple(GuidanceComputeRuntime.__dataclass_fields__) == tuple(
        EXPECTED_RUNTIME_TYPES
    )
    assert (
        "runtime"
        in inspect.signature(compute_design_guidance_items).parameters
    )

    runtime = build_guidance_compute_runtime(
        build_guidance_runtime_provider(st)
    )
    for field_name, expected_type in EXPECTED_RUNTIME_TYPES.items():
        value = getattr(runtime, field_name)
        assert type(value).__name__ == expected_type, (
            field_name,
            type(value).__name__,
            expected_type,
        )
        assert is_dataclass(value), field_name
        assert type(value).__dataclass_params__.frozen, field_name

    for recipe_id in (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
        "MATRIX_DEFLECTION_ONLY_FAIL",
    ):
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe["changes"])
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            first = _compute_for_state(copy.deepcopy(state))
            second = _compute_for_state(copy.deepcopy(state))
        assert first == second, recipe_id
        assert isinstance(first, dict), recipe_id
        assert isinstance(first.get("guidance_items"), list), recipe_id

    print(
        "PASS: guidance compute uses an explicit frozen 20-field family-first "
        "runtime with deterministic 4/4 product recipe output and no legacy "
        "namespace fallback"
    )


if __name__ == "__main__":
    main()
