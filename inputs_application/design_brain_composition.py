"""Single composition point for the currently selected Design Brain."""

from __future__ import annotations

from application.design_brain_service import DesignBrainService
from inputs_application.replacement_design_brain_adapter import (
    ReplacementDesignBrainAdapter,
    ReplacementResultMapper,
)
from inputs_application.legacy_design_brain_adapter import (
    LegacyDesignBrainAdapter,
    LegacyGuidanceProvider,
    build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
)


def build_design_brain_service(
    guidance_provider: LegacyGuidanceProvider,
) -> DesignBrainService:
    """Bind the current implementation without exposing it to consumers."""

    return DesignBrainService(LegacyDesignBrainAdapter(guidance_provider))


def build_replacement_design_brain_service(
    implementation,
    *,
    result_mapper: ReplacementResultMapper | None = None,
) -> DesignBrainService:
    """Bind a supplied replacement only through the neutral application port."""

    return DesignBrainService(
        ReplacementDesignBrainAdapter(
            implementation,
            result_mapper=result_mapper,
        )
    )


def build_guidance_blocker_builder():
    """Expose the selected implementation's blocker through composition."""

    return build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence


def build_publication_cta_builder():
    """Expose the selected implementation's CTA proof builder by composition."""

    from inputs_application.legacy_design_brain_adapter import (
        build_final_publication_cta_from_current_state,
    )

    return build_final_publication_cta_from_current_state


__all__ = [
    "build_design_brain_service",
    "build_replacement_design_brain_service",
    "build_guidance_blocker_builder",
    "build_publication_cta_builder",
]
