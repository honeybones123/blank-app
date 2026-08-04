"""Application-owned contracts shared with replaceable implementations."""

from application.contracts.design_brain import (
    AUTHORITATIVE_DESIGN_RESULT_SCHEMA_VERSION,
    ENGINEERING_INPUT_SNAPSHOT_SCHEMA_VERSION,
    PUBLICATION_AUTHORITY_EXCLUDED_FIELDS,
    UI_ONLY_EXCLUDED_FIELDS,
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
    build_authoritative_design_result,
    stable_authority_hash,
)
from application.contracts.design_policy import (
    AUTO_DESIGN_MODE_CONFIG,
    DESIGN_OPTIMISATION_GOAL_LABELS,
    resolve_design_mode_config,
    resolve_design_optimisation_goal,
    resolve_efficiency_target_band,
)

__all__ = [
    "AUTHORITATIVE_DESIGN_RESULT_SCHEMA_VERSION",
    "AuthoritativeDesignResult",
    "ENGINEERING_INPUT_SNAPSHOT_SCHEMA_VERSION",
    "EngineeringInputSnapshot",
    "PUBLICATION_AUTHORITY_EXCLUDED_FIELDS",
    "UI_ONLY_EXCLUDED_FIELDS",
    "build_authoritative_design_result",
    "stable_authority_hash",
    "AUTO_DESIGN_MODE_CONFIG",
    "DESIGN_OPTIMISATION_GOAL_LABELS",
    "resolve_design_mode_config",
    "resolve_design_optimisation_goal",
    "resolve_efficiency_target_band",
]
