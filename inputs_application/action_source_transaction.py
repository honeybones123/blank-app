"""Application-owned Inputs action-source transaction.

The Inputs page shell composes the engineering workspace; it must not own the
ordering rules that switch between editable Beam Inputs actions and the derived
Load Analysis projection.  This module keeps that ordering in one application
boundary so page composition cannot accidentally create a second action owner.
"""

from __future__ import annotations

from typing import Any, Callable

from inputs_application.action_source_control import (
    ACTION_SOURCE_COMMIT_KEYS,
    INPUTS_ACTION_SOURCE_TOGGLE_KEY,
    authoritative_action_source_projection,
    render_action_source_toggle,
    synchronize_load_analysis_actions_for_inputs,
    uses_load_analysis_actions,
)
from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.load_analysis_state_store import LoadAnalysisStateStore


CommitRequest = Callable[..., Any]
HydrateActions = Callable[..., None]


def render_inputs_action_source_transaction(
    *,
    st_module: Any,
    runtime: Any,
    request_commit: CommitRequest,
    hydrate_actions: HydrateActions,
) -> None:
    """Render and settle the selected action source as one ordered transaction.

    Required ordering is deliberately explicit:

    1. preserve editable manual controls when leaving Beam Inputs;
    2. move the single action-source pointer;
    3. project the selected Load Analysis result when applicable;
    4. commit any changed projected action identity;
    5. hydrate the shared visible controls from the selected owner;
    6. reconcile/commit manual controls only when Beam Inputs owns them.

    The function is content-idempotent.  It does not calculate engineering
    results or render the engineering workspace.
    """

    state = st_module.session_state
    load_analysis_store = LoadAnalysisStateStore(state)

    def _commit_manual_actions_before_source_change() -> None:
        # Streamlit updates the toggle value before invoking this callback. A
        # true value therefore means the user is leaving Beam Inputs and the
        # currently visible editable controls still belong to the manual owner.
        if bool(state.get(INPUTS_ACTION_SOURCE_TOGGLE_KEY, False)):
            runtime.reconcile_design_actions()

    def _commit_selected_action_source(_selected: bool) -> None:
        projected_keys = synchronize_load_analysis_actions_for_inputs(
            state,
            draft=load_analysis_store.current().to_dict(),
            results=load_analysis_store.results(),
        )
        request_commit(
            INPUTS_ACTION_SOURCE_TOGGLE_KEY,
            changed_keys=tuple(
                sorted(
                    {
                        "actions_mode",
                        "actions_source",
                        *ACTION_SOURCE_COMMIT_KEYS,
                        *projected_keys,
                    }
                )
            ),
            # The toggle callback already causes the owning workspace fragment
            # to rerun. A second wake can overlap and truncate the render.
            wake_fragments=False,
        )

    render_action_source_toggle(
        st_module,
        widget_key=INPUTS_ACTION_SOURCE_TOGGLE_KEY,
        before_commit=_commit_manual_actions_before_source_change,
        after_commit=_commit_selected_action_source,
    )

    # Re-apply the selected Load Analysis projection idempotently. This catches
    # a newer solve completed before the user navigates back to Beam Inputs.
    projected_keys = synchronize_load_analysis_actions_for_inputs(
        state,
        draft=load_analysis_store.current().to_dict(),
        results=load_analysis_store.results(),
    )

    active_beam_id = str(state.get("active_beam_id") or "").strip()
    committed_actions = (
        InputSnapshotStore(state).current_for_beam(active_beam_id).to_dict()
        if active_beam_id
        else {}
    )
    action_projection = authoritative_action_source_projection(state)
    projection_commit_keys = (
        tuple(
            sorted(
                key
                for key, value in action_projection.items()
                if committed_actions.get(key) != value
            )
        )
        if uses_load_analysis_actions(state)
        else ()
    )
    action_commit_keys = tuple(sorted({*projected_keys, *projection_commit_keys}))
    if action_commit_keys:
        request_commit(
            INPUTS_ACTION_SOURCE_TOGGLE_KEY,
            changed_keys=action_commit_keys,
            wake_fragments=False,
        )

    # The visible action widgets are projections, not authorities. Project the
    # newly selected owner before any manual reconciliation is allowed.
    hydrate_actions(force=True)

    if uses_load_analysis_actions(state):
        return

    runtime.reconcile_design_actions()
    selected_prefix = (
        "sls"
        if str(state.get("loads_edit_mode", "ULS") or "ULS").strip().upper()
        == "SLS"
        else "uls"
    )
    request_commit(
        "inputs_load_Mstar_pos_proxy",
        changed_keys=(
            f"{selected_prefix}_Mstar",
            f"{selected_prefix}_Mstar_pos_manual",
            f"{selected_prefix}_Mstar_neg_manual",
            f"{selected_prefix}_Vstar",
            f"{selected_prefix}_Nstar",
        ),
        wake_fragments=False,
    )


__all__ = ["render_inputs_action_source_transaction"]
