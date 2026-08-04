"""Verify bottom recommendation geometry-trial updates against compatibility."""

from __future__ import annotations

import contextlib
import copy
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
        from inputs_application.bottom_geometry_trials import (
            bottom_recommendation_geometry_trial_updates,
        )
        from inputs_page_modules.recommendation_compute import (
            BottomRecommendationRuntime,
        )

    rows = []
    for recipe in RECIPES:
        state = build_state(find_named_case(recipe)["changes"])
        for action_type in ("increase_width", "increase_depth"):
            for delta in (25.0, 50.0):
                payload = {"delta_mm": delta}
                compatibility = bridge._guidance_action_updates(
                    action_type,
                    copy.deepcopy(payload),
                    state=copy.deepcopy(state),
                )
                application = bottom_recommendation_geometry_trial_updates(
                    action_type,
                    copy.deepcopy(payload),
                    state=copy.deepcopy(state),
                )
                rows.append(
                    {
                        "recipe": recipe,
                        "action_type": action_type,
                        "delta_mm": delta,
                        "exact_updates_match": compatibility == application,
                    }
                )
    runtime_fields = set(BottomRecommendationRuntime.__dataclass_fields__)
    checks = {
        "twelve_geometry_trials_match_exactly": (
            len(rows) == 12 and all(row["exact_updates_match"] for row in rows)
        ),
        "broad_action_resolver_removed_from_runtime": (
            "_guidance_action_updates" not in runtime_fields
        ),
        "application_owner_imports_no_bridge": (
            "inputs_page_app_contract_bridge"
            not in (
                ROOT / "inputs_application" / "bottom_geometry_trials.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_bottom_geometry_trials_application_owner.v1",
        "checks": checks,
        "cases": rows,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
