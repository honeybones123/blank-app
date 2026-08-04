"""Application-owned Design Guide history planning contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuidanceStepHistoryResetPlan:
    """Pure decision describing whether the step history must be reset."""

    current_anchor: tuple[Any, ...]
    reset_history: bool
    display_hash: str


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_guidance_step_history_reset_plan(
    *,
    current_anchor: tuple[Any, ...] | list[Any],
    previous_anchor: Any,
) -> GuidanceStepHistoryResetPlan:
    """Plan history reset semantics from explicit anchors."""

    anchor = tuple(current_anchor or ())
    reset_history = previous_anchor is not None and previous_anchor != anchor
    return GuidanceStepHistoryResetPlan(
        current_anchor=anchor,
        reset_history=reset_history,
        display_hash=_stable_hash(
            {"current_anchor": anchor, "reset_history": reset_history}
        ),
    )


__all__ = ["GuidanceStepHistoryResetPlan", "build_guidance_step_history_reset_plan"]
