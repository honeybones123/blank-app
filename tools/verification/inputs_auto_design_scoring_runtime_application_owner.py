"""Verify permanent scoring-runtime assembly against compatibility assembly."""

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
        from inputs_application.auto_design_scoring_runtime import (
            build_auto_design_scoring_runtime,
        )
        from inputs_page_modules.design_guide.auto_design_scoring import (
            _score_auto_design_candidate_components,
            candidate_materially_worsens,
        )
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    rows = []
    original_logger = bridge._agent_debug_log
    try:
        for recipe in RECIPES:
            state = build_state(find_named_case(recipe)["changes"])
            with contextlib.redirect_stdout(
                io.StringIO()
            ), contextlib.redirect_stderr(io.StringIO()):
                seed = bridge.evaluate_candidate_full(
                    bridge._guidance_state_snapshot(state),
                    source="scoring_runtime_parity_seed",
                )
            if not seed:
                rows.append({"recipe": recipe, "seed_available": False})
                continue
            candidate = copy.deepcopy(seed)
            candidate["score"] = float(candidate.get("score", 0.0) or 0.0)
            mode_config = bridge._design_mode_config(
                state.get("design_optimisation_goal")
            )
            compatibility_log = []
            application_log = []
            bridge._agent_debug_log = (
                lambda *args, **kwargs: compatibility_log.append(
                    (copy.deepcopy(args), copy.deepcopy(kwargs))
                )
            )
            compatibility_runtime = bridge._build_auto_design_scoring_runtime()
            application_runtime = build_auto_design_scoring_runtime(
                agent_debug_log=lambda *args, **kwargs: application_log.append(
                    (copy.deepcopy(args), copy.deepcopy(kwargs))
                )
            )
            compatibility_components = _score_auto_design_candidate_components(
                copy.deepcopy(candidate),
                copy.deepcopy(mode_config),
                copy.deepcopy(seed),
                runtime=compatibility_runtime,
            )
            application_components = _score_auto_design_candidate_components(
                copy.deepcopy(candidate),
                copy.deepcopy(mode_config),
                copy.deepcopy(seed),
                runtime=application_runtime,
            )
            compatibility_worsens = candidate_materially_worsens(
                copy.deepcopy(candidate),
                copy.deepcopy(seed),
                copy.deepcopy(mode_config),
                phase="runtime_parity",
                runtime=compatibility_runtime,
            )
            application_worsens = candidate_materially_worsens(
                copy.deepcopy(candidate),
                copy.deepcopy(seed),
                copy.deepcopy(mode_config),
                phase="runtime_parity",
                runtime=application_runtime,
            )
            rows.append(
                {
                    "recipe": recipe,
                    "seed_available": True,
                    "components_match": (
                        compatibility_components == application_components
                    ),
                    "material_worsening_match": (
                        compatibility_worsens == application_worsens
                    ),
                    "debug_trace_match": compatibility_log == application_log,
                }
            )
    finally:
        bridge._agent_debug_log = original_logger

    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "three_governing_recipe_seeds_available": (
            len(rows) == 3 and all(row["seed_available"] for row in rows)
        ),
        "scoring_components_and_worsening_match": all(
            row.get("components_match")
            and row.get("material_worsening_match")
            and row.get("debug_trace_match")
            for row in rows
        ),
        "separate_scoring_callbacks_removed": (
            "_score_auto_design_candidate" not in runtime_fields
            and "candidate_materially_worsens" not in runtime_fields
            and "scoring" in runtime_fields
        ),
        "application_owner_imports_no_bridge": (
            "inputs_page_app_contract_bridge"
            not in (
                ROOT
                / "inputs_application"
                / "auto_design_scoring_runtime.py"
            ).read_text(encoding="utf-8")
        ),
    }
    payload = {
        "contract_version": "inputs_auto_design_scoring_runtime_application_owner.v1",
        "checks": checks,
        "recipes": rows,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
