"""Pure safety predicates used by Design Guide and Apply validation."""

from __future__ import annotations

from typing import Any


def requires_full_coverage_for_primary_one_click(
    overview: dict | None,
) -> tuple[bool, list[str]]:
    """Require a primary action to cover every active failure when there are several."""

    statuses = dict((overview or {}).get("statuses") or {})
    fail_keys = sorted(
        key
        for key, value in statuses.items()
        if str(value or "").upper() == "FAIL"
    )
    return (len(fail_keys) >= 2, fail_keys)


def candidate_preview_statuses_have_explicit_fail(
    preview_statuses: dict | None,
    *,
    fail_status_value: Any = "FAIL",
) -> bool:
    """Return whether candidate preview statuses contain an explicit failure."""

    if not isinstance(preview_statuses, dict):
        return False
    return any(
        value == fail_status_value
        or str(value or "").strip().upper() == "FAIL"
        for value in preview_statuses.values()
    )


__all__ = [
    "candidate_preview_statuses_have_explicit_fail",
    "requires_full_coverage_for_primary_one_click",
]
