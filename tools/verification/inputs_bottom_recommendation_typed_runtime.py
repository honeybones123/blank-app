"""Verify the bounded typed runtime for bottom recommendation compute."""

from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
COMPUTE = ROOT / "inputs_page_modules" / "recommendation_compute.py"
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.recipes.one_click_recipe_defs import (
    build_state,
    find_named_case,
)


EXPECTED = {
    "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02": {
        "b": 320.0,
        "db_bot_2": 16,
        "bot_row_1_spacing": 0.0,
        "bot_row_2_spacing": 0.0,
    },
    "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01": {
        "D": 520.0,
        "bot1_count": 6,
        "db_bot_1": 28,
        "db_bot_2": 28,
        "bot_row_1_bars": 6,
        "bot_row_1_spacing": 0.0,
        "bot_row_1_dia": 28,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": 28,
    },
    "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01": {
        "b": 320.0,
        "db_bot_2": 16,
        "bot_row_1_spacing": 0.0,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": 16,
    },
}


def _function(source: str, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def main() -> int:
    compute_source = COMPUTE.read_text(encoding="utf-8")
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    public_body = ast.get_source_segment(
        compute_source,
        _function(compute_source, "compute_bottom_reo_recommendation"),
    ) or ""
    bridge_body = ast.get_source_segment(
        bridge_source,
        _function(bridge_source, "_compute_bottom_reo_recommendation"),
    ) or ""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge

        outputs = {}
        for recipe, expected in EXPECTED.items():
            state = build_state(find_named_case(recipe)["changes"])
            result = bridge._compute_bottom_reo_recommendation(state) or {}
            outputs[recipe] = (
                dict(result.get("updates") or {}) == expected
            )
    checks = {
        "runtime_is_frozen_dataclass": (
            "@dataclass(frozen=True)\nclass BottomRecommendationRuntime"
            in compute_source
        ),
        "public_compute_requires_runtime_not_provider": (
            "runtime: BottomRecommendationRuntime" in public_body
            and "legacy_page" not in public_body
            and "_bind_named_recommendation_globals" not in public_body
        ),
        "bridge_constructs_explicit_runtime": (
            "BottomRecommendationRuntime(" in bridge_body
            and "_BRIDGE_PROVIDER" not in bridge_body
        ),
        "bottom_dependency_inventory_is_runtime_bounded": (
            "_BOTTOM_RECOMMENDATION_NAMES: tuple[str, ...] = tuple("
            in compute_source
            and "BottomRecommendationRuntime.__dataclass_fields__"
            in compute_source
        ),
        "application_ranker_is_direct_owner": (
            "rank_geometry_candidates as _keep_top_candidates"
            in compute_source
        ),
        "all_frozen_outputs_match": all(outputs.values()),
    }
    result = {
        "contract_version": "inputs_bottom_recommendation_typed_runtime.v1",
        "checks": checks,
        "outputs": outputs,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
