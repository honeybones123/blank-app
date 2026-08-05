"""Compatibility adapter for the Design Brain-owned family ladder runtime.

The implementation belongs to :mod:`design_brain.family_ladder_runtime`.
This module preserves historical imports while callers migrate to the owner.
"""

from inputs_application.design_brain_composition import (
    selected_compatibility_namespace,
)


_owner = selected_compatibility_namespace()
FamilyLadderGuidanceRuntime = _owner.FamilyLadderGuidanceRuntime
_family_ladder_guidance_item = _owner._family_ladder_guidance_item
bind_family_ladder_guidance_dependencies = _owner.bind_family_ladder_guidance_dependencies


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
