"""Prove resolved summary state no longer reaches the legacy bridge."""

from __future__ import annotations

import contextlib
import copy
import io
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8"
    )
    owner_source = (
        ROOT / "inputs_application" / "summary_state_runtime.py"
    ).read_text(encoding="utf-8")
    bridge_import = next(
        line
        for line in route_source.splitlines()
        if line.startswith("from inputs_page_app_contract_bridge import ")
    )
    assert "_resolved_inputs_summary_state" not in bridge_import
    assert "@dataclass(frozen=True)\nclass InputsSummaryStateRuntime:" in owner_source
    assert "inputs_page_app_contract_bridge" not in owner_source
    assert "inputs_page_route_coordinators" not in owner_source

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        import inputs_page_route_coordinators as route
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    original_bridge_st = bridge.st
    original_route_st = route.st
    original_bridge_shared = bridge._shared_state_snapshot_for_summary_bridge
    original_route_shared = route._shared_state_snapshot
    try:
        for recipe_id in (
            "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
            "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
            "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
        ):
            recipe = find_named_case(recipe_id)
            assert recipe is not None, recipe_id
            state = build_state(recipe["changes"])
            session = {
                "page_slug": "inputs",
                "inputs_lig_d": state.get("lig_d"),
                "inputs_lig_legs": state.get("lig_legs"),
                "inputs_s_lig": state.get("s_lig"),
            }
            bridge.st = SimpleNamespace(session_state=copy.deepcopy(session))
            route.st = SimpleNamespace(session_state=copy.deepcopy(session))
            bridge._shared_state_snapshot_for_summary_bridge = (
                lambda source=state: copy.deepcopy(source)
            )
            route._shared_state_snapshot = (
                lambda source=state: copy.deepcopy(source)
            )
            with contextlib.redirect_stdout(
                io.StringIO()
            ), contextlib.redirect_stderr(io.StringIO()):
                expected = bridge._resolved_inputs_summary_state()
                actual = route._resolved_inputs_summary_state()
            assert actual == expected, recipe_id
    finally:
        bridge.st = original_bridge_st
        route.st = original_route_st
        bridge._shared_state_snapshot_for_summary_bridge = original_bridge_shared
        route._shared_state_snapshot = original_route_shared
    print(
        "PASS: resolved summary state is application-owned with exact 3/3 "
        "state/debug transaction parity"
    )


if __name__ == "__main__":
    main()
