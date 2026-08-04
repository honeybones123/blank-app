"""Prove permanent typed ownership and exact geometry-trial selection parity."""

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


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules.design_guide.geometry_trial_selector import (
            GeometryTrialSelectorRuntime,
            _choose_geometry_trial_for_metric,
        )
        from inputs_page_modules.guidance_compute import (
            build_guidance_compute_runtime,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_compute_runtime(bridge)
    owned = guidance.shear_guidance.choose_geometry_trial_for_metric
    assert isinstance(owned, functools.partial)
    assert owned.func is _choose_geometry_trial_for_metric
    runtime = owned.keywords.get("runtime")
    assert isinstance(runtime, GeometryTrialSelectorRuntime)
    assert not _has_bridge_callback(runtime)
    bending_item = (
        guidance.bending_guidance.bending_item_from_geometry_trial
    )
    assert isinstance(bending_item, functools.partial)
    assert not _has_bridge_callback(
        bending_item.keywords.get("runtime")
    )
    crack_picker = (
        guidance.crack_guidance.pick_crack_ladder_first_improvement
    )
    assert isinstance(crack_picker, functools.partial)
    assert not _has_bridge_callback(crack_picker.keywords.get("runtime"))

    cases = (
        ("R1A_M300_V0", "bending", "governing"),
        ("R2A_M0_V400", "shear", "governing"),
        ("R3A_M300_V400", "bending", "ductility"),
        ("R4A_M45_V0", "crack", "governing"),
        ("R6A_M45_V150", "deflection", "governing"),
    )
    checked = 0
    for recipe_name, metric, bending_mode in cases:
        recipe = find_named_case(recipe_name)
        assert recipe is not None, recipe_name
        state = build_state(recipe["changes"])
        compatibility = bridge._choose_geometry_trial_for_metric(
            deepcopy(state),
            metric=metric,
            bending_mode=bending_mode,
            ladder_name=f"parity_{recipe_name}_{metric}",
        )
        result = owned(
            deepcopy(state),
            metric=metric,
            bending_mode=bending_mode,
            ladder_name=f"parity_{recipe_name}_{metric}",
        )
        assert result == compatibility, (
            recipe_name,
            metric,
            result,
            compatibility,
        )
        compatibility_item = bridge._bending_item_from_geometry_trial(
            deepcopy(state),
            title="Bending trial",
            status="FAIL",
            util=1.2,
            bending_mode=bending_mode,
            secondary="Alternative",
            levers="Key levers",
            ladder_name=f"bending_parity_{recipe_name}",
        )
        owned_item = bending_item(
            deepcopy(state),
            title="Bending trial",
            status="FAIL",
            util=1.2,
            bending_mode=bending_mode,
            secondary="Alternative",
            levers="Key levers",
            ladder_name=f"bending_parity_{recipe_name}",
        )
        assert owned_item == compatibility_item, (
            recipe_name,
            owned_item,
            compatibility_item,
        )
        crack = bridge._evaluate_crack_with_state(deepcopy(state)) or {}
        crack_util = float(crack.get("util", 0.0) or 0.0)
        compatibility_crack = (
            bridge._pick_crack_ladder_first_improvement(
                deepcopy(state),
                base_util=crack_util,
            )
        )
        owned_crack = crack_picker(
            deepcopy(state),
            base_util=crack_util,
        )
        assert owned_crack == compatibility_crack, (
            recipe_name,
            owned_crack,
            compatibility_crack,
        )
        checked += 1

    print(
        "PASS: geometry trial selection has one frozen permanent runtime "
        f"with exact {checked}/{len(cases)} selector, bending-item, "
        "and crack-ladder parity"
    )


if __name__ == "__main__":
    main()
