"""Contracts for pure Inputs-page session snapshots, decisions, and plans.

The module may shape plain immutable data describing a future page-owned state
mutation. It must not import Streamlit, mutate session state, route Apply
actions, render widgets, or own callback execution.
"""

OWNERSHIP_RULES: tuple[str, ...] = (
    "pure_snapshot_decision_and_plan_models",
    "do_not_import_streamlit",
    "do_not_mutate_session_state",
    "do_not_route_apply",
    "do_not_execute_callbacks",
    "do_not_render_widgets",
)

SNAPSHOT_DISPLAY_HASH_FIELDS: tuple[str, ...] = (
    "key",
    "value",
)
