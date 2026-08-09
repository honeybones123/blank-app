"""Explicit, isolated rollout controls for V2 shadow-to-production switching."""

from __future__ import annotations

import os


def calculation_mode() -> str:
    value = os.environ.get("INPUTS_V2_CALCULATION_MODE", "fixture").strip().lower()
    return value if value in {"fixture", "shadow"} else "fixture"


def shadow_results_enabled() -> bool:
    return calculation_mode() == "shadow"

