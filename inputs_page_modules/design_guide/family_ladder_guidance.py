"""Compatibility adapter for the Design Brain-owned family ladder runtime.

The implementation belongs to :mod:`design_brain.family_ladder_runtime`.
This module preserves historical imports while callers migrate to the owner.
"""

from inputs_application import legacy_design_brain_adapter as _owner
from inputs_application.legacy_design_brain_adapter import (
    FamilyLadderGuidanceRuntime,
    _family_ladder_guidance_item,
    bind_family_ladder_guidance_dependencies,
)


def __getattr__(name: str):
    """Forward historical private helper imports during the staged cutover."""

    return getattr(_owner, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_owner)))

__all__ = [
    "FamilyLadderGuidanceRuntime",
    "bind_family_ladder_guidance_dependencies",
    "_family_ladder_guidance_item",
]
