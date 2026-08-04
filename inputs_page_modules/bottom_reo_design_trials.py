"""Bottom reinforcement design-trial enumeration for Inputs coordinators."""

from __future__ import annotations

from typing import Any


_BOTTOM_REO_DESIGN_TRIAL_DEPENDENCIES: tuple[str, ...] = (
    "_arrangement_fits_state",
    "_bottom_arrangement_to_shared_updates",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_generate_local_bottom_arrangements",
    "_normalise_bottom_layer_order",
    "_practical_bottom_reo_label",
)


def bind_bottom_reo_design_trial_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _BOTTOM_REO_DESIGN_TRIAL_DEPENDENCIES
            if name in namespace
        }
    )


def _enumerate_bottom_reo_design_trials(state: dict, *, mode_config: dict | None = None) -> list[dict]:
    if not isinstance(state, dict):
        return []
    cfg = dict(mode_config or _design_mode_config(_design_optimisation_goal(state)))
    layout_cache: dict = {}
    arrangements = _generate_local_bottom_arrangements(
        state,
        cfg,
        band=2,
        context={"layout_fit_cache": layout_cache},
        limit=12,
    )
    # Include a bounded set of stronger practical layouts so severe starter
    # states (e.g. 200x300 with light reo) can still discover one-click winners.
    stronger_specs = [
        (2, 2, 20),
        (2, 2, 24),
        (2, 2, 28),
        (3, 3, 20),
        (3, 3, 24),
        (3, 3, 28),
        (4, 4, 24),
        (4, 4, 28),
        (6, 0, 24),
        (8, 0, 24),
        (6, 0, 28),
        (8, 0, 28),
    ]
    seen_signatures = {
        (
            int((a or {}).get("bot1_count", 0) or 0),
            int((a or {}).get("bot2_count", 0) or 0),
            int((a or {}).get("db_bot_1", 0) or 0),
        )
        for a in arrangements
    }
    for c1, c2, dia in stronger_specs:
        arr = _normalise_bottom_layer_order(
            {
                "bot1_layout_mode": "Count",
                "bot1_count": int(c1),
                "db_bot_1": int(dia),
                "bot2_layout_mode": "Count",
                "bot2_count": int(c2),
                "db_bot_2": int(dia),
            },
        )
        sig = (
            int(arr.get("bot1_count", 0) or 0),
            int(arr.get("bot2_count", 0) or 0),
            int(arr.get("db_bot_1", 0) or 0),
        )
        if sig in seen_signatures:
            continue
        if not _arrangement_fits_state(state, arr, layout_cache=layout_cache):
            continue
        arrangements.append(arr)
        seen_signatures.add(sig)
    out: list[dict] = []
    for arrangement in arrangements:
        arr = dict(arrangement or {})
        updates = _bottom_arrangement_to_shared_updates(arr)
        if not isinstance(updates, dict):
            continue
        out.append(
            {
                "label": _practical_bottom_reo_label(
                    int(arr.get("bot1_count", 0) or 0),
                    int(arr.get("bot2_count", 0) or 0),
                    int(arr.get("db_bot_1", 0) or 0),
                ),
                "updates": updates,
                "arrangement": arr,
            },
        )
    return out


__all__ = [
    "bind_bottom_reo_design_trial_dependencies",
    "_enumerate_bottom_reo_design_trials",
]
