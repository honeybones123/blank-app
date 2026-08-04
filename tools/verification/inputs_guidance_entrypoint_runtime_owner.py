"""Prove the permanent guidance entrypoint is bridge-independent."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import dataclasses
import functools
import io
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _has_retired_callback(value) -> bool:
    if dataclasses.is_dataclass(value):
        return any(
            _has_retired_callback(getattr(value, field.name))
            for field in dataclasses.fields(value)
        )
    if isinstance(value, functools.partial):
        return (
            _has_retired_callback(value.func)
            or any(_has_retired_callback(item) for item in value.args)
            or any(
                _has_retired_callback(item)
                for item in (value.keywords or {}).values()
            )
        )
    module = str(getattr(value, "__module__", "") or "")
    return bool(
        callable(value)
        and (
            module == "inputs_page_app_contract_bridge"
            or module.endswith("active_fail_single_family_guard")
        )
    )


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from inputs_application.guidance_entrypoint import (
            GuidanceEntrypointRuntime,
            build_guidance_entrypoint_runtime,
            compute_inputs_guidance,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    runtime = build_guidance_entrypoint_runtime(
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    assert isinstance(runtime, GuidanceEntrypointRuntime)
    assert not _has_retired_callback(runtime)
    assert "active_fail_guard" not in {
        field.name for field in dataclasses.fields(GuidanceEntrypointRuntime)
    }

    cases = (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
        "MATRIX_DEFLECTION_ONLY_FAIL",
    )
    checked = 0
    for recipe_name in cases:
        recipe = find_named_case(recipe_name)
        assert recipe is not None, recipe_name
        state = build_state(recipe["changes"])
        with contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(io.StringIO()):
            payload = compute_inputs_guidance(
                runtime,
                deepcopy(state),
                guidance_debug_verbose=False,
                debug_enabled=False,
            )
        assert isinstance(payload, dict), recipe_name
        assert isinstance(payload.get("guidance_items"), list), recipe_name
        debug = dict(payload.get("debug_trace") or {})
        assert not debug.get(
            "combined_active_fail_single_family_action_blocked"
        ), recipe_name
        checked += 1

    print(
        "PASS: permanent guidance entrypoint has no retired bridge/guard "
        f"callback and returns {checked}/{len(cases)} current product payloads"
    )


if __name__ == "__main__":
    main()
