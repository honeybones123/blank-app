"""
State debugging utilities: snapshots, diffs, invariant checks, and write guards.

These utilities help identify session-state → derived → diagram desync issues
without changing any engineering formulas or widget behavior.
"""

import json
import inspect
from typing import Dict, Any, List, Set, Optional
import streamlit as st

from .debug_flags import is_debug_enabled


def _safe_json_value(value: Any) -> Any:
    """
    Convert a value to a JSON-safe representation.
    
    Handles numpy types, dataclasses, etc. by converting to basic Python types.
    """
    import numpy as np
    
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (np.integer, np.floating)):
        return float(value) if isinstance(value, np.floating) else int(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _safe_json_value(v) for k, v in value.items()}
    # Try to convert dataclass or other objects to dict
    if hasattr(value, "__dict__"):
        return _safe_json_value(value.__dict__)
    # Fallback: convert to string
    try:
        return str(value)
    except Exception:
        return "<UNSERIALIZABLE>"


def snapshot_state(label: str, keys: List[str]) -> Dict[str, Any]:
    """
    Take a snapshot of specified session state keys.
    
    Args:
        label: Label for this snapshot (for logging/debugging)
        keys: List of session state keys to snapshot
    
    Returns:
        dict: {key: value} for the requested keys, with "<MISSING>" for missing keys
    """
    snapshot = {}
    for key in keys:
        if key in st.session_state:
            snapshot[key] = _safe_json_value(st.session_state[key])
        else:
            snapshot[key] = "<MISSING>"
    return snapshot


def diff_snapshots(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Compare two snapshots and return only changed keys.
    
    Args:
        a: First snapshot (before)
        b: Second snapshot (after)
    
    Returns:
        dict: {key: {"from": value_a, "to": value_b}} for changed keys
    """
    diff = {}
    all_keys = set(a.keys()) | set(b.keys())
    for key in all_keys:
        val_a = a.get(key, "<MISSING>")
        val_b = b.get(key, "<MISSING>")
        if val_a != val_b:
            diff[key] = {"from": val_a, "to": val_b}
    return diff


class guard_session_writes:
    """
    Context manager to guard against writes to derived/results keys outside allowed functions.
    
    Usage:
        with guard_session_writes(allowed_keys={"d", "Ast_bot"}, context="recalc_derived_values"):
            # Only writes to allowed_keys are permitted
            st.session_state["d"] = ...
    
    In debug mode, this will detect and report any writes to protected keys
    that are not in the allowed_keys set.
    """
    
    def __init__(self, allowed_keys: Set[str], context: str):
        """
        Initialize the guard.
        
        Args:
            allowed_keys: Set of keys that are allowed to be written
            context: Context string for error reporting (e.g., "recalc_derived_values")
        """
        self.allowed_keys = allowed_keys
        self.context = context
        self.initial_snapshot: Optional[Dict[str, Any]] = None
        self.violations: List[Dict[str, Any]] = []
    
    def __enter__(self):
        """Enter the guard context."""
        if not is_debug_enabled():
            return self
        
        # Import here to avoid circular imports
        from state_and_helpers import DERIVED_KEYS, RESULT_KEYS
        
        # Only track derived/results keys (not all keys)
        protected_keys = DERIVED_KEYS | RESULT_KEYS
        
        # Take snapshot of protected keys only
        self.initial_snapshot = {}
        for key in protected_keys:
            if key in st.session_state:
                self.initial_snapshot[key] = _safe_json_value(st.session_state[key])
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the guard context and check for violations."""
        if not is_debug_enabled():
            return False
        
        if self.initial_snapshot is None:
            return False
        
        # Import here to avoid circular imports
        from state_and_helpers import DERIVED_KEYS, RESULT_KEYS
        protected_keys = DERIVED_KEYS | RESULT_KEYS
        
        # Get final snapshot of protected keys
        final_snapshot = {}
        for key in protected_keys:
            if key in st.session_state:
                final_snapshot[key] = _safe_json_value(st.session_state[key])
        
        # Check for keys that were written but are not allowed
        # Only flag keys that are protected AND were actually written AND are not in allowed_keys
        for key in protected_keys:
            # Skip keys that are allowed
            if key in self.allowed_keys:
                continue
            
            # Check if this key was written (added or changed)
            was_written = False
            if key not in self.initial_snapshot and key in final_snapshot:
                # New key was written
                was_written = True
                self.violations.append({
                    "key": key,
                    "type": "new_key",
                    "value": final_snapshot[key],
                    "context": self.context,
                    "callsite": self._get_callsite(),
                })
            elif key in self.initial_snapshot and key in final_snapshot:
                # Key exists in both - check if value changed
                if self.initial_snapshot[key] != final_snapshot[key]:
                    was_written = True
                    self.violations.append({
                        "key": key,
                        "type": "changed_value",
                        "from": self.initial_snapshot[key],
                        "to": final_snapshot[key],
                        "context": self.context,
                        "callsite": self._get_callsite(),
                    })
        
        # Report violations
        if self.violations:
            self._report_violations()
        
        return False  # Don't suppress exceptions
    
    def _get_callsite(self) -> str:
        """Get the callsite (file:function:line) for the violation."""
        stack = inspect.stack()
        # Skip internal frames (this function, __exit__, etc.)
        for frame in stack[3:]:  # Skip guard_session_writes, __exit__, and the frame that called __exit__
            filename = frame.filename
            func_name = frame.function
            lineno = frame.lineno
            # Skip debug module frames
            if "debug" not in filename.lower() and "state_debug" not in filename:
                return f"{filename}:{func_name}:{lineno}"
        return "<UNKNOWN>"
    
    def _report_violations(self):
        """Report violations to Streamlit (debug mode only)."""
        if not is_debug_enabled():
            return
        
        # Store violations in session state for the debug panel to display
        if "_debug_violations" not in st.session_state:
            st.session_state["_debug_violations"] = []
        st.session_state["_debug_violations"].extend(self.violations)


def assert_invariants() -> List[str]:
    """
    Check session state invariants and return list of violation messages.
    
    Does not crash in production - returns empty list if debug mode is off.
    
    Returns:
        list[str]: List of violation messages (empty if all invariants pass)
    """
    if not is_debug_enabled():
        return []
    
    violations = []
    
    # Import here to avoid circular imports
    from state_and_helpers import SHARED_DEFAULTS, RESULT_KEYS
    
    # Invariant: All keys in SHARED_DEFAULTS exist in st.session_state after initialization
    for key in SHARED_DEFAULTS.keys():
        if key not in st.session_state:
            violations.append(f"Missing SHARED_DEFAULTS key: {key}")
    
    # Invariant: If top reinforcement count is 0, related result keys should be empty/None/0
    nb_top = st.session_state.get("nb_top", 0)
    nb_or_s_top_1 = st.session_state.get("nb_or_s_top_1", 0.0)
    if (nb_top == 0 or nb_or_s_top_1 == 0) and st.session_state.get("Ast_top", 0.0) > 0:
        violations.append(
            f"Top reinforcement count is 0 but Ast_top = {st.session_state.get('Ast_top')}"
        )
    
    # Invariant: If bottom reinforcement count is 0, related result keys should be empty/None/0
    nb_bot = st.session_state.get("nb_bot", 0)
    nb_or_s_bot_1 = st.session_state.get("nb_or_s_bot_1", 0.0)
    if (nb_bot == 0 or nb_or_s_bot_1 == 0) and st.session_state.get("Ast_bot", 0.0) > 0:
        violations.append(
            f"Bottom reinforcement count is 0 but Ast_bot = {st.session_state.get('Ast_bot')}"
        )
    
    # Report violations
    if violations and is_debug_enabled():
        if "_debug_invariant_violations" not in st.session_state:
            st.session_state["_debug_invariant_violations"] = []
        st.session_state["_debug_invariant_violations"].extend(violations)
        
        # Show error if hard fail is enabled
        if st.session_state.get("_debug_hard_fail", False):
            raise AssertionError(f"Invariant violations: {', '.join(violations)}")
    
    return violations
