"""Coverage and executor-safety gates for Design Guide candidates."""

from design_brain.engine import (
    _button_enabled,
    _candidate_has_bad_update_keys,
    _candidate_preview_pass,
    _candidate_rejection_category,
    _candidate_required_preview_fails,
    _has_required_failure,
    _normalise_button_contract,
)

__all__ = [
    "_button_enabled",
    "_candidate_has_bad_update_keys",
    "_candidate_preview_pass",
    "_candidate_rejection_category",
    "_candidate_required_preview_fails",
    "_has_required_failure",
    "_normalise_button_contract",
]
