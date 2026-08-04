"""Application-owned normalized shear-truth overlay contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedShearTruthOverlay:
    merged_state: dict[str, Any]
    session_overlay: dict[str, Any]
    normalized_overlay: dict[str, Any]
    display_hash: str


def build_normalized_shear_truth_overlay(
    *,
    base_state: Mapping[str, Any] | None,
    session_shear_truth_values: Mapping[str, Any] | None,
    normalized_shear_truth_values: Mapping[str, Any] | None,
) -> NormalizedShearTruthOverlay:
    merged = dict(base_state or {})
    session_overlay = dict(session_shear_truth_values or {})
    normalized_overlay = dict(normalized_shear_truth_values or {})
    merged.update(session_overlay)
    merged.update(normalized_overlay)
    payload = {
        "merged_state": merged,
        "session_overlay": session_overlay,
        "normalized_overlay": normalized_overlay,
    }
    encoded = json.dumps(
        payload,
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return NormalizedShearTruthOverlay(
        merged_state=merged,
        session_overlay=session_overlay,
        normalized_overlay=normalized_overlay,
        display_hash=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    )


__all__ = ["NormalizedShearTruthOverlay", "build_normalized_shear_truth_overlay"]
