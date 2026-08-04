"""Compatibility exports for application-owned state projection helpers."""

from inputs_application.state_projection import (
    build_auto_design_governing_fingerprint,
    build_guidance_state_snapshot,
)

__all__ = ["build_auto_design_governing_fingerprint", "build_guidance_state_snapshot"]
