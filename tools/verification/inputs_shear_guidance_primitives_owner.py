"""Verify application ownership of deterministic shear-guidance primitives."""

from __future__ import annotations

import contextlib
from functools import partial
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_page_modules.guidance_compute import (
            _application_fallback_shear_reinforcement_step_updates,
            _application_geometry_trial_title_for_choice,
            _application_next_tighter_link_spacing_updates,
            _application_shear_spacing_guidance_floor_mm,
            build_guidance_compute_runtime,
        )

    shear = build_guidance_compute_runtime(bridge).shear_guidance
    assert (
        shear.geometry_trial_title_for_choice
        is _application_geometry_trial_title_for_choice
    )
    partial_bindings = (
        (
            shear.fallback_shear_reinforcement_step_updates,
            _application_fallback_shear_reinforcement_step_updates,
        ),
        (
            shear.next_tighter_link_spacing_updates,
            _application_next_tighter_link_spacing_updates,
        ),
        (
            shear.shear_spacing_guidance_floor_mm,
            _application_shear_spacing_guidance_floor_mm,
        ),
    )
    assert all(
        isinstance(callback, partial) and callback.func is owner
        for callback, owner in partial_bindings
    )

    states = (
        {"D": 600.0, "b": 300.0, "s_lig": 200.0, "lig_legs": 2, "lig_d": 10},
        {"D": 600.0, "b": 300.0, "s_lig": 75.0, "lig_legs": 8, "lig_d": 24},
        {"D": 600.0, "b": 300.0, "s_lig": 0.0, "lig_legs": 4, "lig_d": 12},
    )
    for state in states:
        assert shear.next_tighter_link_spacing_updates(
            state
        ) == bridge._next_tighter_link_spacing_updates(state)
        assert shear.fallback_shear_reinforcement_step_updates(
            state
        ) == bridge._fallback_shear_reinforcement_step_updates(state)

    geometry_cases = (
        ({}, "Base"),
        ({"D": 550.0, "b": 350.0}, "Rebalance depth and width for bending"),
        ({"D": 650.0}, "Increase depth for bending"),
        ({"b": 350.0}, "Increase width slightly for bending"),
    )
    state = {"D": 600.0, "b": 300.0}
    for updates, expected in geometry_cases:
        trial = {"updates": updates}
        assert shear.geometry_trial_title_for_choice(
            "Base",
            trial,
            state,
        ) == expected
        assert bridge._geometry_trial_title_for_choice(
            "Base",
            trial,
            state,
        ) == expected

    assert (
        shear.shear_spacing_guidance_floor_mm()
        == bridge._shear_spacing_guidance_floor_mm()
    )
    print(
        "PASS: 4 deterministic shear-guidance bindings are application-owned "
        "with exact geometry, spacing, and reinforcement-step parity"
    )


if __name__ == "__main__":
    main()
