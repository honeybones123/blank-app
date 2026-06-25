"""Compatibility import for the combined bending plus shear active-fail family."""

from __future__ import annotations

from design_brain.families.combined_bending_shear_fail import CombinedBendingShearFailFamily


class CombinedFailFamily(CombinedBendingShearFailFamily):
    """Backward-compatible class name used by the Phase 1 registry shell."""


__all__ = ["CombinedFailFamily"]
