"""Typed generation of escalated shear states for one-click family repair."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ShearEscalationRuntime:
    """Only the dependencies used by the live escalated-state generator."""

    reo_bar_dias: tuple[int, ...]
    reo_spacings: tuple[float, ...]
    activation_shear_state: Callable[..., Any]
    float_from_state: Callable[..., Any]
    geometry_lock_enabled: Callable[..., Any]
    int_from_state: Callable[..., Any]
    make_auto_design_candidate_key: Callable[..., Any]
    resolve_geometry_width_context: Callable[..., Any]
    shear_candidate_type: Callable[..., Any]
    shear_reinforcement_is_active: Callable[..., Any]


def generate_escalated_shear_states(
    state: dict,
    *,
    severity_band: str,
    runtime: ShearEscalationRuntime,
) -> list[tuple[str, dict]]:
    """Generate the existing ordered severe-shear state sequence."""

    base_state = (
        runtime.activation_shear_state(state)
        if not runtime.shear_reinforcement_is_active(state)
        else dict(state)
    )
    current_spacing = runtime.int_from_state(base_state, "s_lig", 200)
    current_legs = max(
        runtime.int_from_state(base_state, "lig_legs", 2),
        2,
    )
    current_dia = max(
        runtime.int_from_state(base_state, "lig_d", 10),
        10,
    )
    width_key, _, current_width = runtime.resolve_geometry_width_context(
        base_state
    )
    current_depth = runtime.float_from_state(base_state, "D", 600.0)
    max_legs = 10 if severity_band == "extreme" else 8
    max_dia = 24 if severity_band == "extreme" else 20
    leg_values = sorted(
        {
            current_legs,
            min(current_legs + 2, max_legs),
            min(current_legs + 4, max_legs),
        }
    )
    dia_values = sorted(
        {
            *(
                dia
                for dia in runtime.reo_bar_dias
                if current_dia <= dia <= max_dia
            ),
            current_dia,
        }
    )
    spacing_targets = [
        value
        for value in runtime.reo_spacings
        if value <= current_spacing
    ]
    spacing_values = sorted(
        {*spacing_targets[:3], current_spacing}
    ) or [current_spacing]
    width_steps = [current_width + 50.0, current_width + 100.0]
    depth_steps = [current_depth + 50.0, current_depth + 100.0]
    if severity_band == "extreme":
        width_steps.append(current_width + 150.0)
        depth_steps.append(current_depth + 150.0)

    generated: dict[tuple, tuple[str, dict]] = {}

    def _store(candidate_state: dict) -> None:
        key = runtime.make_auto_design_candidate_key(candidate_state)
        generated[key] = (
            runtime.shear_candidate_type(state, candidate_state),
            candidate_state,
        )

    for spacing in spacing_values:
        for legs in leg_values:
            for dia in dia_values:
                candidate_state = dict(base_state)
                candidate_state.update(
                    {
                        "lig_d": int(dia),
                        "lig_legs": int(legs),
                        "s_lig": float(spacing),
                    }
                )
                _store(candidate_state)

    if not runtime.geometry_lock_enabled(state):
        for width in width_steps:
            candidate_state = dict(base_state)
            candidate_state[width_key] = float(width)
            if width_key != "b":
                candidate_state["b"] = float(width)
            _store(candidate_state)
        for depth in depth_steps:
            candidate_state = dict(base_state)
            candidate_state["D"] = float(depth)
            _store(candidate_state)
        strong_spacing = (
            float(min(spacing_values))
            if spacing_values
            else float(current_spacing)
        )
        strong_legs = int(max(leg_values))
        strong_dia = int(max(dia_values))
        for width in width_steps:
            for depth in depth_steps:
                candidate_state = dict(base_state)
                candidate_state.update(
                    {
                        width_key: float(width),
                        "D": float(depth),
                        "lig_d": strong_dia,
                        "lig_legs": strong_legs,
                        "s_lig": strong_spacing,
                    }
                )
                if width_key != "b":
                    candidate_state["b"] = float(width)
                _store(candidate_state)

    return list(generated.values())


__all__ = [
    "ShearEscalationRuntime",
    "generate_escalated_shear_states",
]
