"""Parity proof for the bridge-free Inputs geometry search policy."""

from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application import geometry_search_policy as policy  # noqa: E402
from inputs_application.geometry_candidate_ranking import (  # noqa: E402
    rank_geometry_candidates,
)
from inputs_application.geometry_recommendation import (  # noqa: E402
    GeometryCandidateRuntime,
    compute_geometry_recommendation,
)
from tools.verification.recipes.one_click_recipe_defs import (  # noqa: E402
    build_state,
    find_named_case,
)


EXPECTED = {
    "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02": {
        "updates": {"b": 250.0, "D": 350.0},
        "width": 250.0,
        "depth": 350.0,
    },
    "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01": {
        "updates": {"D": 520.0},
        "width": 450.0,
        "depth": 520.0,
    },
    "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01": {
        "updates": {"b": 250.0},
        "width": 250.0,
        "depth": 400.0,
    },
}


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import inputs_page_app_contract_bridge as bridge

        output_parity = {}
        policy_parity = {}
        ranking_parity = {}
        for recipe, expected in EXPECTED.items():
            case = find_named_case(recipe)
            state = build_state(case["changes"])
            result = bridge._compute_geometry_recommendation(state) or {}
            output_parity[recipe] = {
                "updates": dict(result.get("updates") or {}) == expected["updates"],
                "width": float(result.get("width") or 0.0) == expected["width"],
                "depth": float(result.get("depth") or 0.0) == expected["depth"],
            }
            seed = bridge.evaluate_candidate_full(
                state,
                source="geometry_search_policy_extraction",
            )
            mode = bridge._design_mode_config(bridge._design_optimisation_goal(state))
            policy_parity[recipe] = {
                "shallower": policy.generate_shallower_or_equal_depths(seed)
                == bridge.generate_shallower_or_equal_depths(seed),
                "deeper": policy.generate_slightly_deeper_depths(seed)
                == bridge.generate_slightly_deeper_depths(seed),
                "same_or_larger": policy.generate_same_or_larger_geometry_options(seed)
                == bridge.generate_same_or_larger_geometry_options(seed),
                "balanced": policy.generate_balanced_geometry_options(seed)
                == bridge._generate_balanced_geometry_options(seed),
                "tightening": policy.geometry_tightening_trial_updates(state)
                == bridge._geometry_tightening_trial_updates(state),
                "context": policy.build_auto_design_context(
                    seed["state"],
                    mode,
                    reference_overview=seed.get("overview"),
                )
                == bridge._build_auto_design_context(
                    seed["state"],
                    mode,
                    reference_overview=seed.get("overview"),
                ),
                "search_allowed": policy.recommendation_search_allowed(
                    state,
                    seed.get("overview"),
                )
                == bridge._recommendation_search_allowed(state),
            }
            ranking_parity[recipe] = {}
            for goal in (
                "balanced",
                "shallower_beam",
                "less_longitudinal_reinforcement",
                "less_shear_reinforcement",
            ):
                goal_state = dict(state)
                goal_state["design_optimisation_goal"] = goal
                captured: list[dict] = []

                def capture_rank(candidates, mode_config, *, limit):
                    captured.extend(copy.deepcopy(candidates))
                    return bridge._keep_top_candidates(
                        candidates,
                        mode_config,
                        limit=limit,
                    )

                typed_result = compute_geometry_recommendation(
                    goal_state,
                    runtime=GeometryCandidateRuntime(
                        evaluate_full=bridge.evaluate_candidate_full,
                        evaluate_fast=bridge._evaluate_candidate_fast,
                        rank=capture_rank,
                        max_stage_candidates=int(
                            bridge.AUTO_DESIGN_MAX_STAGE_CANDIDATES
                        ),
                    ),
                )
                goal_mode = policy.design_mode_config(goal)
                legacy_top = bridge._keep_top_candidates(
                    copy.deepcopy(captured),
                    goal_mode,
                    limit=1,
                )
                clean_top = rank_geometry_candidates(
                    copy.deepcopy(captured),
                    goal_mode,
                    limit=1,
                )
                ranking_parity[recipe][goal] = {
                    "captured_candidates": bool(captured),
                    "same_top_updates": (
                        dict((clean_top or [{}])[0].get("updates") or {})
                        == dict((legacy_top or [{}])[0].get("updates") or {})
                    ),
                    "typed_result_matches_legacy_top": (
                        dict((typed_result or {}).get("updates") or {})
                        == dict((legacy_top or [{}])[0].get("updates") or {})
                    ),
                }

    compute_text = (
        ROOT / "inputs_page_modules/recommendation_compute.py"
    ).read_text(encoding="utf-8")
    policy_text = (
        ROOT / "inputs_application/geometry_search_policy.py"
    ).read_text(encoding="utf-8")
    runtime_text = (
        ROOT / "inputs_application/geometry_recommendation.py"
    ).read_text(encoding="utf-8")
    ranking_text = (
        ROOT / "inputs_application/geometry_candidate_ranking.py"
    ).read_text(encoding="utf-8")
    checks = {
        "all_golden_outputs_match": all(
            all(fields.values()) for fields in output_parity.values()
        ),
        "all_policy_functions_match_legacy": all(
            all(fields.values()) for fields in policy_parity.values()
        ),
        "all_geometry_rankings_match_legacy": all(
            all(all(fields.values()) for fields in goals.values())
            for goals in ranking_parity.values()
        ),
        "geometry_compute_imports_clean_policy": (
            "from inputs_application.geometry_search_policy import" in compute_text
        ),
        "clean_policy_has_no_legacy_import": (
            "inputs_page_app_contract_bridge" not in policy_text
            and "inputs_page_route_coordinators" not in policy_text
        ),
        "typed_geometry_runtime_has_no_legacy_import": (
            "class GeometryCandidateRuntime" in runtime_text
            and "inputs_page_app_contract_bridge" not in runtime_text
            and "inputs_page_route_coordinators" not in runtime_text
        ),
        "clean_ranker_has_no_legacy_import": (
            "inputs_page_app_contract_bridge" not in ranking_text
            and "inputs_page_route_coordinators" not in ranking_text
        ),
        "compatibility_adapter_uses_typed_runtime": (
            "def compute_geometry_recommendation(" in compute_text
            and "runtime: GeometryCandidateRuntime" in compute_text
            and "runtime=runtime" in compute_text
            and "compute_geometry_recommendation_typed(" in compute_text
        ),
    }
    payload = {
        "contract_version": "inputs_geometry_search_policy_extraction.v1",
        "checks": checks,
        "output_parity": output_parity,
        "policy_parity": policy_parity,
        "ranking_parity": ranking_parity,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
