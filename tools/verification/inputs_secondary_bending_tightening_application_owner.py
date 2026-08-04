"""Verify application ownership and recipe parity for secondary bending tightening."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.recipes.one_click_recipe_defs import build_state, find_named_case


RECIPES = (
    "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
    "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
    "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
)


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.secondary_bending_tightening import (
            generate_secondary_bending_tightening_states,
        )
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    rows = []
    for recipe in RECIPES:
        state = build_state(find_named_case(recipe)["changes"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            candidate = bridge.evaluate_candidate_full(
                bridge._guidance_state_snapshot(state),
                source="secondary_bending_tightening_parity_seed",
            )
            compatibility = bridge._generate_secondary_bending_tightening_states(
                candidate or {},
                limit=3,
            )
            application = generate_secondary_bending_tightening_states(
                candidate or {},
                limit=3,
            )
        rows.append(
            {
                "recipe": recipe,
                "exact_state_list_match": compatibility == application,
                "compatibility_count": len(compatibility),
                "application_count": len(application),
            }
        )

    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "three_governing_recipes_match_exactly": all(
            row["exact_state_list_match"] for row in rows
        ),
        "bridge_callback_removed_from_typed_runtime": (
            "_generate_secondary_bending_tightening_states" not in runtime_fields
        ),
        "application_owner_imports_no_bridge": (
            "inputs_page_app_contract_bridge"
            not in (
                ROOT
                / "inputs_application"
                / "secondary_bending_tightening.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_secondary_bending_tightening_application_owner.v1",
        "checks": checks,
        "recipes": rows,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
