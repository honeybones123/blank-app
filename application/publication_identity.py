"""Deterministic publication identities owned by the application layer.

These helpers intentionally operate on plain values only.  They are used for
cache/publication fingerprints and visible candidate IDs; they do not select a
family, run a strategy ladder, or import a Design Brain implementation.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any


def _stable_fingerprint_for_payload(payload: dict | None) -> tuple:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def normalise_design_guide_candidate_id(
    *values: object,
    family: str | None = None,
    updates: dict | None = None,
) -> str:
    """Return a stable visible candidate identifier from plain publication data."""

    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    try:
        fingerprint = _stable_fingerprint_for_payload(
            {"family": str(family or "").strip(), "updates": dict(updates or {})}
        )
        return f"visible_primary:{fingerprint}"
    except Exception:
        return "visible_primary:unidentified"


def stable_final_publication_hash(value: Any) -> str:
    """Return the deterministic hash used for publication identity fields."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "normalise_design_guide_candidate_id",
    "stable_final_publication_hash",
]
