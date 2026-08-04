"""Explicit session mutation for clearing transient Design Guide UI state."""

from __future__ import annotations

from typing import Any, MutableMapping

import inputs_application.policy_constants as inputs_page_app_contracts
from inputs_page_modules.session import build_inputs_design_guide_transient_ui_clear_plan


def clear_design_guide_transient_ui_state(
    session_state: MutableMapping[str, Any],
    *,
    clear_history: bool = False,
    preserve_apply_banner: bool = False,
) -> tuple[str, ...]:
    plan = build_inputs_design_guide_transient_ui_clear_plan(
        base_transient_keys=(
            inputs_page_app_contracts.DESIGN_GUIDE_APPLY_BANNER_META_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
        ),
        apply_banner_key=inputs_page_app_contracts.DESIGN_GUIDE_APPLY_BANNER_KEY,
        always_clear_keys=(
            inputs_page_app_contracts.DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_RECO_TRACE_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_RANK_TRACE_KEY,
        ),
        history_keys=(
            inputs_page_app_contracts.DESIGN_GUIDE_STEP_HISTORY_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY,
            inputs_page_app_contracts.DESIGN_GUIDE_HISTORY_ANCHOR_KEY,
        ),
        clear_history=bool(clear_history),
        preserve_apply_banner=bool(preserve_apply_banner),
    )
    for key in plan.all_keys:
        session_state.pop(key, None)
    return tuple(plan.all_keys)


__all__ = ["clear_design_guide_transient_ui_state"]
