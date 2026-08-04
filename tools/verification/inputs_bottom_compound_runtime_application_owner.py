"""Verify permanent bottom compound runtime assembly against compatibility helpers."""

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
        from inputs_application.bottom_compound_runtime import (
            build_bottom_compound_runtime,
        )
        from inputs_page_modules.recommendation_compute import (
            BottomRecommendationRuntime,
        )

    runtime = build_bottom_compound_runtime(
        evaluate_candidate_fast=bridge._evaluate_candidate_fast
    )
    rows = []
    for recipe in RECIPES:
        state = build_state(find_named_case(recipe)["changes"])
        mode = bridge._design_mode_config(state.get("design_optimisation_goal"))
        compatibility_arrangements = bridge._generate_local_bottom_arrangements(
            copy.deepcopy(state),
            copy.deepcopy(mode),
            band=0,
            context={},
            limit=6,
        )
        application_arrangements = runtime.generate_bottom_arrangements(
            copy.deepcopy(state),
            copy.deepcopy(mode),
            band=0,
            context={},
            limit=6,
        )
        arrangement = (
            copy.deepcopy(compatibility_arrangements[0])
            if compatibility_arrangements
            else {"bot1_count": 3, "bot2_count": 0, "db_bot_1": 16}
        )
        compound_state = dict(state)
        compound_state.update(
            runtime.bottom_arrangement_updates(copy.deepcopy(arrangement))
        )
        compound_state["D"] = float(state.get("D", 600.0) or 600.0) + 50.0
        geometry_candidates = [
            {
                "recommendation_geometry_trial": True,
                "updates": {"D": compound_state["D"]},
                "overview": {"utils": {"bending": 0.9}},
            },
            {
                "recommendation_geometry_trial": True,
                "updates": {"D": compound_state["D"] + 50.0},
                "overview": {"utils": {"bending": 0.95}},
            },
        ]
        rows.append(
            {
                "recipe": recipe,
                "arrangements_match": (
                    compatibility_arrangements == application_arrangements
                ),
                "layout_fit_matches": (
                    bridge._arrangement_fits_state(
                        copy.deepcopy(state),
                        copy.deepcopy(arrangement),
                        layout_cache={},
                    )
                    == runtime.arrangement_fits_state(
                        copy.deepcopy(state),
                        copy.deepcopy(arrangement),
                        layout_cache={},
                    )
                ),
                "signature_matches": (
                    bridge._bottom_recommendation_compound_effective_signature(
                        copy.deepcopy(state),
                        copy.deepcopy(compound_state),
                    )
                    == runtime.compound_effective_signature(
                        copy.deepcopy(state),
                        copy.deepcopy(compound_state),
                    )
                ),
                "preview_matches": (
                    bridge._compound_merged_signature_preview(
                        copy.deepcopy(state),
                        copy.deepcopy(compound_state),
                    )
                    == runtime.compound_signature_preview(
                        copy.deepcopy(state),
                        copy.deepcopy(compound_state),
                    )
                ),
                "seed_selection_matches": (
                    bridge._select_top_geometry_seeds_for_compound(
                        copy.deepcopy(geometry_candidates),
                        copy.deepcopy(state),
                        "depth",
                        limit=2,
                    )
                    == runtime.select_geometry_seeds(
                        copy.deepcopy(geometry_candidates),
                        copy.deepcopy(state),
                        "depth",
                        limit=2,
                    )
                ),
                "titles_match": all(
                    bridge._bottom_recommendation_compound_title(axis, "trial")
                    == runtime.compound_title(axis, "trial")
                    for axis in ("width", "depth", "other")
                ),
            }
        )
    runtime_fields = set(BottomRecommendationRuntime.__dataclass_fields__)
    checks = {
        "three_recipe_dependency_sets_match": all(
            all(value for key, value in row.items() if key != "recipe")
            for row in rows
        ),
        "bridge_callback_replaced_by_typed_compound_service": (
            "_append_geometry_bottom_compound_candidates" not in runtime_fields
            and "compound" in runtime_fields
        ),
        "application_owner_imports_no_bridge": (
            "inputs_page_app_contract_bridge"
            not in (
                ROOT
                / "inputs_application"
                / "bottom_compound_runtime.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_bottom_compound_runtime_application_owner.v1",
        "checks": checks,
        "recipes": rows,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
