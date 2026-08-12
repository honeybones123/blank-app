"""Revision-matched presentation values for creep and shrinkage pages.

The general result pages may calculate a local fallback while an Inputs V2
publication is unavailable, but a current authoritative family result must be
the display authority when it exists.  Keeping this merge in one adapter
prevents the page summaries and their detailed calculations from following
different data paths.
"""

from __future__ import annotations

from typing import Any, Mapping

from inputs_application.authoritative_check_packs import (
    current_authoritative_family,
)


def resolve_time_dependent_family_values(
    state: Mapping[str, Any],
    *,
    family: str,
    fallback: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay a current V2 family result onto page-local fallback values.

    Only keys requested by the caller are projected.  This keeps calculation
    ownership in V2 and prevents unrelated diagnostic fields from becoming a
    second page-level contract.  ``None`` values never replace a valid local
    fallback.
    """

    resolved = dict(fallback)
    authoritative = current_authoritative_family(state, family)
    if authoritative is None:
        return resolved

    for key in resolved:
        value = authoritative.get(key)
        if value is not None:
            resolved[key] = value
    return resolved


__all__ = ["resolve_time_dependent_family_values"]
