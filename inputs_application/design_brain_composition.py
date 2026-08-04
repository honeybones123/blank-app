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


__all__ = [
    "build_design_brain_service",
    "build_replacement_design_brain_service",
]
