"""Prove typed ownership and parity for efficiency executor promotion."""

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
        from inputs_page_modules.design_guide.efficiency_executor_promotion import (
            EfficiencyExecutorPromotionRuntime,
            _try_promote_efficiency_item_to_executor_backed_candidate,
        )
        from inputs_page_modules.guidance_compute import (
            build_guidance_compute_runtime,
        )
        from tools.verification.recipes.one_click_recipe_defs import (
            build_state,
            find_named_case,
        )

    guidance = build_guidance_compute_runtime(bridge)
    promote = guidance.executor_contract_sanitizer.try_promote_efficiency_item
    assert isinstance(promote, functools.partial)
    assert (
        promote.func
        is _try_promote_efficiency_item_to_executor_backed_candidate
    )
    runtime = promote.keywords.get("runtime")
    assert isinstance(runtime, EfficiencyExecutorPromotionRuntime)
    assert not _has_bridge_callback(runtime)

    recipe = find_named_case("LIVE_FUZZ_BENDING_OVERDESIGN_GOVERNS_02")
    assert recipe is not None
    state = build_state(recipe["changes"])
    items = (
        None,
        {"bucket": "pass", "title_main": "Already fine"},
        {"bucket": "efficiency", "title_main": "Missing update"},
        {
            "bucket": "efficiency",
            "title_main": "Resolved",
            "action_type": "apply_resolved_candidate",
            "action_payload": {
                "resolved_candidate_updates": {"D": 550.0},
                "resolved_candidate_reaches_target_band": True,
            },
        },
        {
            "bucket": "efficiency",
            "title_main": "Reduce section depth",
            "action_type": "increase_depth",
            "action_payload": {"updates": {"D": 550.0}},
        },
    )
    for item in items:
        for blocked_reason in (None, "upstream_block"):
            with contextlib.redirect_stdout(
                io.StringIO()
            ), contextlib.redirect_stderr(io.StringIO()):
                owned = promote(
                    deepcopy(item),
                    state=deepcopy(state),
                    blocked_reason=blocked_reason,
                )
                compatibility = (
                    bridge
                    ._try_promote_efficiency_item_to_executor_backed_candidate(
                        deepcopy(item),
                        state=deepcopy(state),
                        blocked_reason=blocked_reason,
                    )
                )
            assert owned == compatibility, (
                item,
                blocked_reason,
                owned,
                compatibility,
            )

    print(
        "PASS: efficiency executor promotion has one frozen permanent runtime "
        "with exact 10/10 payload and blocker-metadata parity"
    )


if __name__ == "__main__":
    main()
