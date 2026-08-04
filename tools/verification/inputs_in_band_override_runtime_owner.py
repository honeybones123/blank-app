"""Prove permanent typed ownership of the in-band override policy."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import functools
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _candidate(*, depth: float, width: float, ast: float) -> dict:
    return {
        "state": {
            "D": depth,
            "b": width,
            "bot1_count": 4,
            "bot2_count": 0,
            "db_bot_1": 20,
        },
        "depth": depth,
        "width": width,
        "Ast_bot": ast,
    }


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.in_band_override_policy import (
            InBandOverridePolicy,
            should_override_target_band_done_state,
        )
        from inputs_page_modules.guidance_compute import (
            build_guidance_compute_runtime,
        )

    runtime = build_guidance_compute_runtime(bridge)
    callback = (
        runtime.actionable_target_band_winner
        .should_override_target_band_done_state
    )
    assert isinstance(callback, functools.partial)
    assert callback.func is should_override_target_band_done_state
    assert isinstance(callback.keywords.get("policy"), InBandOverridePolicy)
    assert callback.func.__module__ != "inputs_page_app_contract_bridge"

    base_state = {"D": 600.0, "b": 400.0}
    overview = {"worst_util": 0.88}
    seed = _candidate(depth=600.0, width=400.0, ast=1800.0)
    improved = _candidate(depth=550.0, width=350.0, ast=1300.0)
    cases = (
        (
            {"updates": {}, "delta_b_mm": 0.0, "delta_D_mm": 0.0},
            "balanced",
            {},
            seed,
            improved,
        ),
        (
            {
                "updates": {"D": 570.0},
                "delta_D_mm": 30.0,
                "delta_b_mm": 0.0,
                "delta_Ast_bot": 0.0,
            },
            "balanced",
            {"search_strategy": "balanced"},
            seed,
            improved,
        ),
        (
            {
                "updates": {"D": 550.0},
                "delta_D_mm": 50.0,
                "delta_b_mm": 0.0,
                "delta_Ast_bot": 0.0,
            },
            "balanced",
            {"search_strategy": "balanced"},
            None,
            None,
        ),
        (
            {
                "updates": {"D": 550.0},
                "delta_D_mm": 50.0,
                "delta_b_mm": 0.0,
                "delta_Ast_bot": 0.0,
            },
            "balanced",
            {"search_strategy": "balanced"},
            seed,
            deepcopy(seed),
        ),
        (
            {
                "updates": {"D": 550.0, "bot1_count": 3},
                "delta_D_mm": 50.0,
                "delta_b_mm": 50.0,
                "delta_Ast_bot": 500.0,
                "recommendation_compound": True,
            },
            "balanced",
            {"search_strategy": "balanced"},
            seed,
            improved,
        ),
        (
            {
                "updates": {"D": 650.0},
                "delta_D_mm": 50.0,
                "delta_b_mm": 0.0,
                "delta_Ast_bot": 150.0,
            },
            "shallower_beam",
            {"search_strategy": "shallow"},
            seed,
            _candidate(depth=650.0, width=400.0, ast=1650.0),
        ),
    )
    for recommendation, goal, mode_config, seed_candidate, trial_candidate in cases:
        owned_debug: dict = {}
        bridge_debug: dict = {}
        args = (
            deepcopy(recommendation),
            deepcopy(base_state),
            deepcopy(overview),
            goal,
            deepcopy(mode_config),
            deepcopy(seed_candidate),
            deepcopy(trial_candidate),
        )
        owned = callback(*args, debug_extra=owned_debug)
        compatibility = bridge._should_override_target_band_done_state(
            *deepcopy(args),
            debug_extra=bridge_debug,
        )
        assert owned == compatibility
        assert owned_debug == bridge_debug

    print(
        "PASS: in-band override policy has a frozen permanent owner with "
        "exact 6/6 decision and debug parity"
    )


if __name__ == "__main__":
    main()
