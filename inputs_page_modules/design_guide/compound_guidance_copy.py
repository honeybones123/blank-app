"""Compound Design Guide title and reasoning copy."""

from __future__ import annotations

from typing import Any


_COMPOUND_GUIDANCE_COPY_DEPENDENCIES: tuple[str, ...] = (
    "_design_width_value",
    "_float_from_state",
    "_guidance_state_snapshot",
    "_resolve_geometry_width_context",
)


def bind_compound_guidance_copy_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _COMPOUND_GUIDANCE_COPY_DEPENDENCIES
            if name in namespace
        }
    )


def _compound_geometry_deltas(state: dict, updates: dict) -> tuple[float, float, float, float]:
    """Returns (d0, d1, w0, w1) for width key resolved from state."""
    s0 = _guidance_state_snapshot(state)
    s1 = dict(s0)
    s1.update(updates)
    d0 = float(_float_from_state(s0, "D", 0.0) or 0.0)
    d1 = float(_float_from_state(s1, "D", d0) or d0)
    wkey, _, w0f = _resolve_geometry_width_context(s0)
    w0 = float(w0f or 0.0)
    w1 = float(_design_width_value(s1) or w0)
    return d0, d1, w0, w1


def _compound_guidance_title_reasoning_why(
    state: dict,
    updates: dict,
    subfamilies: list[str],
    *,
    strengthening: bool,
) -> tuple[str, str, str]:
    """Returns (title_main, reasoning_with_why_prefix, guidance_why_plain)."""
    sf = set(subfamilies)
    eps = 0.5
    d0, d1, w0, w1 = _compound_geometry_deltas(state, updates) if updates else (0.0, 0.0, 0.0, 0.0)
    grow_d = d1 > d0 + eps
    grow_w = w1 > w0 + eps

    if strengthening:
        if sf >= {"geometry", "bottom_reo", "shear"}:
            title = "Increase section size, bottom reinforcement, and shear reinforcement"
            why = (
                "Flexure and shear both need attention. Updating section geometry, bottom steel, "
                "and shear reinforcement together gives the cleanest one-step strengthening move."
            )
            return (title, f"Why: {why}", why)
        if sf >= {"geometry", "bottom_reo"}:
            if grow_d and grow_w:
                title = "Increase depth, width, and bottom reinforcement"
            elif grow_d and not grow_w:
                title = "Increase depth and bottom reinforcement"
            elif grow_w and not grow_d:
                title = "Increase width and bottom reinforcement"
            else:
                title = "Adjust section and bottom reinforcement"
            why = (
                "Bending demand is above capacity. Changing the section together with bottom steel is the most direct "
                "way to bring capacity in line with the applied actions."
            )
            return (
                title,
                f"Why: {why}",
                why,
            )
        if sf >= {"shear", "bottom_reo"}:
            title = "Reduce shear links and adjust bottom reinforcement"
            why = (
                "Shear links look heavier than needed for the applied shear. Reducing links and rebalancing longitudinal "
                "steel keeps detailing consistent with demand."
            )
            return (title, f"Why: {why}", why)
        if sf >= {"geometry", "shear"}:
            title = "Adjust section geometry and shear reinforcement"
            why = (
                "Flexure and shear both need attention. Updating geometry and shear reinforcement together avoids fixing "
                "one check while leaving the other marginal."
            )
            return (title, f"Why: {why}", why)
        why = "Several inputs need to move together to reach a compliant, coherent design."
        return (
            "Apply combined strengthening update",
            f"Why: {why}",
            why,
        )
    if sf >= {"geometry", "bottom_reo"}:
        title = "Reduce section size and rebalance bottom reinforcement"
        why = (
            "Utilisation is below the target band. A small section trim with a light steel rebalance moves the design "
            "toward efficient use without large jumps."
        )
        return (title, f"Why: {why}", why)
    if sf >= {"shear", "bottom_reo"}:
        title = "Reduce shear links and trim bottom reinforcement"
        why = (
            "The section is conservative on shear and steel. Relaxing links and trimming bottom steel tightens the design "
            "without increasing member size."
        )
        return (title, f"Why: {why}", why)
    if sf >= {"geometry", "shear"}:
        title = "Tighten geometry and shear reinforcement"
        why = (
            "Reserve is available on both flexure-related geometry and shear. Coordinated reductions keep detailing "
            "consistent while lifting utilisation toward the target band."
        )
        return (title, f"Why: {why}", why)
    why = "Combined adjustments move several checks together toward the target utilisation band."
    return (
        "Apply coordinated efficiency update",
        f"Why: {why}",
        why,
    )
