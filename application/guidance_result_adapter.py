"""Read the canonical V2 publication carried by an authoritative result.

Runtime no longer adapts, reclassifies, renames, ranks, or republishes raw
guidance payloads.  The installed V2 Design Brain is the sole decision and
publication authority; this boundary exists only for presentation consumers
that need a defensive copy of its already-authoritative publication.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from application.contracts.design_brain import AuthoritativeDesignResult


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def guidance_payload_from_authoritative_design_result(
    result: AuthoritativeDesignResult | None,
) -> dict[str, Any]:
    """Return a defensive copy without changing family or Apply authority."""

    if not isinstance(result, AuthoritativeDesignResult):
        return {}
    return _mapping(result.final_publication)


__all__ = ["guidance_payload_from_authoritative_design_result"]
