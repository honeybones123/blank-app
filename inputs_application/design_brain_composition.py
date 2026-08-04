"""Single composition point for the currently selected Design Brain."""

from __future__ import annotations

from application.design_brain_service import DesignBrainService
from inputs_application.legacy_design_brain_adapter import (
    LegacyDesignBrainAdapter,
    LegacyGuidanceProvider,
)


def build_design_brain_service(
    guidance_provider: LegacyGuidanceProvider,
) -> DesignBrainService:
    """Bind the current implementation without exposing it to consumers."""

    return DesignBrainService(LegacyDesignBrainAdapter(guidance_provider))


__all__ = ["build_design_brain_service"]
