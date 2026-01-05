"""
Debug panel UI for State Inspector.

Shows canonical inputs, derived keys, results keys, conflicting keys,
and debug checkpoints. Only visible when debug mode is enabled.
"""

import json
import streamlit as st
from typing import Dict, Any, List

from .debug_flags import is_debug_enabled


def render_state_inspector():
    """
    Render the State Inspector panel (debug mode only).
    
    Shows:
    - Canonical inputs (geometry, cover, bar counts, bar dia, layers, spacing mode)
    - Derived keys (DERIVED_KEYS)
    - Results keys (RESULT_KEYS)
    - Conflicting keys view (groups related keys together)
    - Debug violations (if any)
    - Debug checkpoints (if any)
    - Copy debug JSON button
    - Hard fail checkbox
    """
    if not is_debug_enabled():
        return
    
    with st.expander("🔧 Debug: State Inspector", expanded=False):
        try:
            from state_and_helpers import (
                SHARED_DEFAULTS,
                DERIVED_KEYS,
                RESULT_KEYS,
                TAB_KEYS,
            )
        except ImportError:
            st.error("Cannot import state constants for debug panel")
            return
        
        # Canonical inputs section
        st.markdown("### Canonical Inputs")
        canonical_keys = [
            "b", "D", "L",
            "cover_bot", "cover_top", "cover_side",
            "nb_or_s_bot_1", "db_bot_1", "nb_or_s_bot_2", "db_bot_2",
            "nb_or_s_top_1", "db_top_1", "nb_or_s_top_2", "db_top_2",
            "rowgap_bot", "rowgap_top",
        ]
        inputs_data = {}
        for key in canonical_keys:
            if key in st.session_state:
                inputs_data[key] = st.session_state[key]
            else:
                inputs_data[key] = "<MISSING>"
        
        st.json(inputs_data)
        
        # Derived keys section
        st.markdown("### Derived Keys")
        derived_data = {}
        for key in sorted(DERIVED_KEYS):
            if key in st.session_state:
                derived_data[key] = st.session_state[key]
            else:
                derived_data[key] = "<MISSING>"
        st.json(derived_data)
        
        # Results keys section
        st.markdown("### Results Keys")
        results_data = {}
        for key in sorted(RESULT_KEYS):
            if key in st.session_state:
                results_data[key] = st.session_state[key]
            else:
                results_data[key] = "<MISSING>"
        st.json(results_data)
        
        # Conflicting keys view (group related keys)
        st.markdown("### Conflicting Keys View")
        conflicting_groups = {
            "Top Reinforcement": [
                "nb_or_s_top_1", "nb_or_s_top_2", "nb_top", "db_top_1", "db_top_2", "db_top", "Ast_top"
            ],
            "Bottom Reinforcement": [
                "nb_or_s_bot_1", "nb_or_s_bot_2", "nb_bot", "db_bot_1", "db_bot_2", "db_bot", "Ast_bot"
            ],
            "Cover": [
                "cover_bot", "cover_top", "cover_side", "side_cover_bot", "side_cover_top"
            ],
        }
        
        for group_name, keys in conflicting_groups.items():
            with st.expander(f"{group_name}", expanded=False):
                group_data = {}
                for key in keys:
                    if key in st.session_state:
                        group_data[key] = st.session_state[key]
                    else:
                        group_data[key] = "<MISSING>"
                st.json(group_data)
        
        # Debug violations
        violations = st.session_state.get("_debug_violations", [])
        if violations:
            st.markdown("### ⚠️ Debug Violations")
            st.error(f"Found {len(violations)} violation(s)")
            for violation in violations[-10:]:  # Show last 10
                st.text(f"Key: {violation.get('key')}, Type: {violation.get('type')}, Context: {violation.get('context')}, Callsite: {violation.get('callsite')}")
        
        # Invariant violations
        invariant_violations = st.session_state.get("_debug_invariant_violations", [])
        if invariant_violations:
            st.markdown("### ⚠️ Invariant Violations")
            st.error(f"Found {len(invariant_violations)} invariant violation(s)")
            for violation in invariant_violations[-10:]:  # Show last 10
                st.text(violation)
        
        # Debug checkpoints
        checkpoints = st.session_state.get("_debug_checkpoints", [])
        if checkpoints:
            st.markdown("### Debug Checkpoints")
            for checkpoint in checkpoints[-10:]:  # Show last 10
                st.text(f"{checkpoint.get('label', 'Unknown')}: {checkpoint.get('diff', {})}")
        
        # Buttons and controls
        st.markdown("---")
        
        # Hard fail checkbox
        st.checkbox(
            "Hard fail on invariant violation",
            key="_debug_hard_fail",
            help="If enabled, raises AssertionError on invariant violations"
        )
        
        # Copy debug JSON button
        if st.button("📋 Copy Debug JSON"):
            debug_data = {
                "inputs": inputs_data,
                "derived": derived_data,
                "results": results_data,
                "violations": violations,
                "invariant_violations": invariant_violations,
                "checkpoints": checkpoints,
            }
            json_str = json.dumps(debug_data, indent=2, default=str)
            st.code(json_str, language="json")
            
            # Also copy to clipboard (Streamlit doesn't have native clipboard, so just show code)
            st.info("JSON data shown above. Copy manually from code block.")
