"""Prove the route canonical design pack is independently assembled."""

from __future__ import annotations

import contextlib
import copy
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    route_source = (ROOT / "inputs_page_route_coordinators.py").read_text(
        encoding="utf-8"
    )
    owner_source = (
        ROOT
        / "inputs_page_modules"
        / "app_bridge"
        / "canonical_design_state_pack.py"
    ).read_text(encoding="utf-8")
    bridge_import = next(
        line
        for line in route_source.splitlines()
        if line.startswith("from inputs_page_app_contract_bridge import ")
    )
    assert "_build_canonical_design_state_pack_for_app_bridge" not in bridge_import
    assert "@dataclass(frozen=True)\nclass CanonicalDesignStatePackRuntime:" in owner_source
    assert "_compute_section_layout_owned" in owner_source
    assert "_resolve_longitudinal_bars_owned" in owner_source
    assert "_effective_depth_with_links_owned" in owner_source

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        import inputs_page_route_coordinators as route
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    for recipe_id in (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
    ):
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe["changes"])
        expected = bridge._build_canonical_design_state_pack_for_app_bridge(
            copy.deepcopy(state)
        )
        actual = route._build_canonical_design_state_pack(copy.deepcopy(state))
        assert actual == expected, recipe_id
    print(
        "PASS: canonical design-state pack is independently assembled with "
        "exact 3/3 full-pack parity"
    )


if __name__ == "__main__":
    main()
