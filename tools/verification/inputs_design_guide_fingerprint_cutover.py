"""Verify route fingerprint ownership and exact legacy parity."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import inputs_page_app_contract_bridge as bridge
from inputs_application.design_guide_fingerprint import design_guide_fingerprint
from tools.one_click_recipe_defs import build_state, find_named_case


def main() -> None:
    route_text = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    owner_text = (
        ROOT / "inputs_application" / "design_guide_fingerprint.py"
    ).read_text(encoding="utf-8")
    assert "_get_design_guide_fp" not in route_text
    assert "design_guide_fp_fn=design_guide_fingerprint" in route_text
    assert "inputs_page_app_contract_bridge" not in owner_text
    for recipe_id in (
        "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
        "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
        "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
    ):
        recipe = find_named_case(recipe_id)
        assert recipe is not None, recipe_id
        state = build_state(recipe.get("changes"))
        assert design_guide_fingerprint(state) == bridge._get_design_guide_fp(state)
    print("PASS: Design Guide fingerprint route dependency retired")


if __name__ == "__main__":
    main()
