"""Verify the bounded typed runtime for shear recommendation compute."""

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


RECIPES = (
    "LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02",
    "LIVE_FUZZ_SHEAR_FAIL_GOVERNS_01",
    "LIVE_FUZZ_SHEAR_OVERDESIGN_GOVERNS_01",
)


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
        _function(compute_source, "compute_shear_recommendation"),
    ) or ""
    bridge_body = ast.get_source_segment(
        bridge_source,
        _function(bridge_source, "_compute_shear_recommendation"),
    ) or ""
    builder_body = ast.get_source_segment(
        bridge_source,
        _function(bridge_source, "_build_shear_recommendation_runtime"),
    ) or ""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules import recommendation_compute

        runtime = bridge._build_shear_recommendation_runtime()
        outputs = {}
        for recipe in RECIPES:
            state = build_state(find_named_case(recipe)["changes"])
            outputs[recipe] = dict(
                (
                    bridge._compute_shear_recommendation(state) or {}
                ).get("updates")
                or {}
            )
    runtime_fields = set(runtime.__dataclass_fields__)
    inventory = set(recommendation_compute._SHEAR_RECOMMENDATION_NAMES)
    checks = {
        "runtime_is_frozen_dataclass": (
            "@dataclass(frozen=True)\nclass ShearRecommendationRuntime"
            in compute_source
        ),
        "public_compute_requires_runtime_not_provider": (
            "runtime: ShearRecommendationRuntime" in public_body
            and "legacy_page" not in public_body
            and "_bind_named_recommendation_globals" not in public_body
        ),
        "bridge_uses_bounded_runtime_builder": (
            "_build_shear_recommendation_runtime()" in bridge_body
            and "_BRIDGE_PROVIDER" not in bridge_body
            and "_bind_named_recommendation_globals" not in bridge_body
        ),
        "builder_constructs_fields_explicitly": (
            "ShearRecommendationRuntime(" in builder_body
            and "_BRIDGE_PROVIDER" not in builder_body
            and "globals()" not in builder_body
        ),
        "inventory_exactly_matches_runtime": inventory == runtime_fields,
        "application_ranker_is_not_a_runtime_port": (
            "_keep_top_candidates" not in runtime_fields
            and "rank_geometry_candidates as _keep_top_candidates"
            in compute_source
        ),
        "representative_recipes_execute": set(outputs) == set(RECIPES),
    }
    result = {
        "contract_version": "inputs_shear_recommendation_typed_runtime.v1",
        "checks": checks,
        "outputs": outputs,
        "runtime_field_count": len(runtime_fields),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
