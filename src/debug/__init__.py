"""
Debug harness for Streamlit concrete app.

Developer-only debugging tools to identify and prevent session-state → derived → diagram desync.
Must not change engineering formulas, UI layout (except optional dev panel), or widget behavior.
"""

from .debug_flags import is_debug_enabled, show_debug_toggle
from .state_debug import (
    snapshot_state,
    diff_snapshots,
    guard_session_writes,
    assert_invariants,
)
from .debug_panel import render_state_inspector

__all__ = [
    "is_debug_enabled",
    "show_debug_toggle",
    "snapshot_state",
    "diff_snapshots",
    "guard_session_writes",
    "assert_invariants",
    "render_state_inspector",
]
