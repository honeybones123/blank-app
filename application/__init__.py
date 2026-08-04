"""Application-layer orchestration helpers for the Streamlit app.

These modules sit between Streamlit session state and pure Design Brain
compute. They must not render UI or own family/product decisions.
"""

from application.design_result_store import (
    AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY,
    AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY,
    AuthoritativeDesignResultStore,
    DesignResultReuseDecision,
)
from application.design_run_coordinator import ensure_design_result
from application.apply_command import ApplyCommandResult, execute_apply_command
from application.guidance_result_adapter import (
    build_authoritative_design_result_from_guidance_payload,
    guidance_payload_from_authoritative_design_result,
)
from application.engineering_snapshot import (
    DESIGN_ACTION_INPUT_KEYS,
    DESIGN_SETTING_INPUT_KEYS,
    GEOMETRY_INPUT_KEYS,
    MATERIAL_INPUT_KEYS,
    REINFORCEMENT_INPUT_KEYS,
    build_engineering_input_snapshot_from_resolved_state,
)

__all__ = [
    "AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY",
    "AuthoritativeDesignResultStore",
    "DESIGN_ACTION_INPUT_KEYS",
    "DESIGN_SETTING_INPUT_KEYS",
    "DesignResultReuseDecision",
    "GEOMETRY_INPUT_KEYS",
    "MATERIAL_INPUT_KEYS",
    "REINFORCEMENT_INPUT_KEYS",
    "build_engineering_input_snapshot_from_resolved_state",
    "ensure_design_result",
    "ApplyCommandResult",
    "execute_apply_command",
    "build_authoritative_design_result_from_guidance_payload",
    "guidance_payload_from_authoritative_design_result",
]
