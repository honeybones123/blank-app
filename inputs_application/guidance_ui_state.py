"""Session preparation for Design Guide rendering without the legacy bridge."""

from __future__ import annotations

from typing import Any, Callable, Mapping, MutableMapping

from application.contracts.design_policy import (
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_optimisation_goal,
)
from inputs_application.guidance_ui_state_store import GuidanceUiStateStore
from inputs_application.guidance_history import build_guidance_step_history_reset_plan
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import guidance_state_snapshot
from state_and_helpers import SHARED_DEFAULTS, resolve_design_actions


def prepare_guidance_ui_state(
    session_state: MutableMapping[str, Any],
    current_state: Mapping[str, Any],
    *,
    preserve_apply_banner: bool,
    clear_transient: Callable[..., Any],
) -> dict[str, Any]:
    ui_store = GuidanceUiStateStore(session_state)
    guidance_state = guidance_state_snapshot(current_state)
    beam_id = ui_store.active_beam_id()
    previous_beam_id = ui_store.reference_beam_id()
    depth = float(guidance_state.get("D", SHARED_DEFAULTS.get("D", 600.0)) or 0.0)
    _, _, width = resolve_geometry_width_context(guidance_state)
    if beam_id and beam_id != previous_beam_id:
        ui_store.set_beam_reference(beam_id, depth=depth, width=float(width or 0.0))
    if ui_store.session_anchor_depth() is None:
        ui_store.set_session_anchor_depth(depth)

    anchor = (
        str(
            resolve_design_optimisation_goal(
                guidance_state,
                goal_labels=DESIGN_OPTIMISATION_GOAL_LABELS,
            )
        ),
        ui_store.reference_beam_id(),
        tuple(resolve_design_actions(guidance_state).get("signature", ())),
    )
    reset_plan = build_guidance_step_history_reset_plan(
        current_anchor=anchor,
        previous_anchor=ui_store.history_anchor(),
    )
    ui_store.apply_history_reset(
        reset_history=reset_plan.reset_history,
        current_anchor=reset_plan.current_anchor,
    )
    clear_transient(
        clear_history=False,
        preserve_apply_banner=preserve_apply_banner,
    )
    return {"guidance_state": guidance_state, "guidance_cache_fp": None}


__all__ = ["GuidanceUiStateStore", "prepare_guidance_ui_state"]
