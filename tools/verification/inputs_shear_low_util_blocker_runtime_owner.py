"""Prove typed ownership and parity for the active-link low-util blocker."""

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
        from inputs_page_modules.design_guide.shear_low_util_active_links_blocker import (
            ShearLowUtilBlockerRuntime,
            _shear_low_util_active_links_exact_blocker,
        )
        from inputs_page_modules.guidance_compute import (
            build_guidance_compute_runtime,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_compute_runtime(bridge)
    blocker = (
        guidance.local_cleanup_promotion
        .shear_low_util_active_links_exact_blocker
    )
    assert (
        blocker
        is guidance.accepted_green_audit
        .shear_low_util_active_links_exact_blocker
    )
    assert isinstance(blocker, functools.partial)
    assert blocker.func is _shear_low_util_active_links_exact_blocker
    runtime = blocker.keywords.get("runtime")
    assert isinstance(runtime, ShearLowUtilBlockerRuntime)
    assert not _has_bridge_callback(runtime)

    states = [
        {},
        {"lig_legs": 0, "lig_d": 0, "s_lig": 200.0},
        {"lig_legs": 2, "lig_d": 10, "s_lig": 200.0},
    ]
    for recipe_id in (
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
    ):
        recipe = find_named_case(recipe_id)
        assert recipe is not None
        states.append(build_state(recipe["changes"]))

    for state in states:
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            design_context = bridge._build_design_actions_context(
                deepcopy(state)
            )
            overview = bridge._collect_design_overview(
                deepcopy(state),
                context=design_context,
            )
            owned = blocker(deepcopy(state), deepcopy(overview))
            compatibility = bridge._shear_low_util_active_links_exact_blocker(
                deepcopy(state),
                deepcopy(overview),
            )
        assert owned == compatibility

    print(
        "PASS: both low-util active-link blocker slots share one frozen "
        "permanent runtime with exact 5/5 payload parity"
    )


if __name__ == "__main__":
    main()
