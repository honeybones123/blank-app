"""Prove typed ownership and exact local-cleanup evaluator parity."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import dataclasses
import functools
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _has_bridge_callback(value) -> bool:
    if dataclasses.is_dataclass(value):
        return any(
            _has_bridge_callback(getattr(value, field.name))
            for field in dataclasses.fields(value)
        )
    if isinstance(value, functools.partial):
        return (
            _has_bridge_callback(value.func)
            or any(_has_bridge_callback(item) for item in value.args)
            or any(
                _has_bridge_callback(item)
                for item in (value.keywords or {}).values()
            )
        )
    return bool(
        callable(value)
        and getattr(value, "__module__", "")
        == "inputs_page_app_contract_bridge"
    )


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules.design_guide.local_cleanup_guidance_evaluator import (
            LocalCleanupGuidanceEvaluatorRuntime,
            _evaluate_local_cleanup_guidance_item,
        )
        from inputs_page_modules.guidance_compute import (
            build_guidance_compute_runtime,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_compute_runtime(bridge)
    evaluator = (
        guidance.local_cleanup_promotion.evaluate_local_cleanup_guidance_item
    )
    assert isinstance(evaluator, functools.partial)
    assert evaluator.func is _evaluate_local_cleanup_guidance_item
    runtime = evaluator.keywords.get("runtime")
    assert isinstance(runtime, LocalCleanupGuidanceEvaluatorRuntime)
    assert not _has_bridge_callback(runtime)

    recipe = find_named_case("R4A_M45_V0")
    assert recipe is not None
    state = build_state(recipe["changes"])
    overview = bridge._collect_design_overview(state)
    mode_config = bridge._design_mode_config(
        bridge._design_optimisation_goal(state)
    )
    items = (
        None,
        {},
        {"title_main": "No action"},
        {
            "title_main": "No-op depth",
            "action_type": "increase_depth",
            "action_payload": {"updates": {"D": state["D"]}},
        },
        {
            "bucket": "efficiency",
            "title_main": "Reduce depth",
            "action_type": "apply_resolved_candidate",
            "action_payload": {
                "updates": {"D": float(state["D"]) - 50.0},
                "resolved_candidate_updates": {
                    "D": float(state["D"]) - 50.0
                },
            },
        },
    )
    checked = 0
    for item in items:
        compatibility = bridge._evaluate_local_cleanup_guidance_item(
            deepcopy(item),
            state=deepcopy(state),
            overview=deepcopy(overview),
            mode_config=deepcopy(mode_config),
            source="local_cleanup_exact_parity",
        )
        owned = evaluator(
            deepcopy(item),
            state=deepcopy(state),
            overview=deepcopy(overview),
            mode_config=deepcopy(mode_config),
            source="local_cleanup_exact_parity",
        )
        assert owned == compatibility, (item, owned, compatibility)
        if isinstance(item, dict) and item.get("bucket") == "efficiency":
            assert owned[1].get("candidate_id"), owned
            assert owned[1].get("blocked_reason") != (
                "cleanup_no_material_update"
            ), owned
        checked += 1

    print(
        "PASS: local-cleanup evaluation has one frozen permanent runtime "
        f"with exact {checked}/{len(items)} payload and diagnostic parity"
    )


if __name__ == "__main__":
    main()
