"""Permanent provider used to assemble the Inputs guidance runtime."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from inputs_application.legacy_design_brain_adapter import (
    resolve_design_guide_controller_guidance_action_generated_updates,
    resolve_design_guide_controller_guidance_action_payload_updates,
)
from inputs_application import guidance_runtime_config as config
from inputs_application.local_cleanup_acceptance import (
    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
)


def build_guidance_runtime_provider(st_module: Any) -> SimpleNamespace:
    values = {
        name: getattr(config, name)
        for name in dir(config)
        if name.isupper() and not name.startswith("__")
    }
    values.update(
        {
            "st": st_module,
            "_COMPOUND_BOTTOM_UPDATE_KEYS": (
                config.COMPOUND_BOTTOM_UPDATE_KEYS
            ),
            "_COMPOUND_GEOMETRY_UPDATE_KEYS": (
                config.COMPOUND_GEOMETRY_UPDATE_KEYS
            ),
            "_DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS": (
                DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS
            ),
            (
                "_resolve_design_guide_controller_"
                "guidance_action_generated_updates"
            ): resolve_design_guide_controller_guidance_action_generated_updates,
            (
                "_resolve_design_guide_controller_"
                "guidance_action_payload_updates"
            ): resolve_design_guide_controller_guidance_action_payload_updates,
        }
    )
    return SimpleNamespace(**values)


__all__ = ["build_guidance_runtime_provider"]
