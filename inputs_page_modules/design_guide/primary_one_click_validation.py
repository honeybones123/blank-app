"""Primary one-click candidate validation for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any


_PRIMARY_ONE_CLICK_VALIDATION_DEPENDENCIES: tuple[str, ...] = (
    "_candidate_preview_statuses_have_explicit_fail",
    "_requires_full_coverage_for_primary_one_click",
    "BEAM_STATUS_FAIL",
)


def bind_primary_one_click_validation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRIMARY_ONE_CLICK_VALIDATION_DEPENDENCIES
            if name in namespace
        }
    )


def _candidate_is_valid_primary_one_click(
    candidate: dict | None,
    overview: dict,
) -> tuple[bool, dict]:
    meta = {
        "valid": False,
        "reason": "missing_candidate",
        "fail_keys": [],
        "covers_all_current_failures": False,
        "covered_fail_keys": [],
        "remaining_fail_keys": [],
        "requires_full_coverage": False,
    }
    if not isinstance(candidate, dict):
        return False, meta

    requires_full_coverage, fail_keys = _requires_full_coverage_for_primary_one_click(overview)
    meta["fail_keys"] = list(fail_keys)
    meta["requires_full_coverage"] = bool(requires_full_coverage)

    payload = dict(candidate.get("action_payload") or {})
    coverage = dict(candidate.get("failure_coverage") or payload.get("failure_coverage") or {})
    covers_all = bool(
        candidate.get("covers_all_current_failures")
        or payload.get("covers_all_current_failures")
        or coverage.get("covers_all_current_failures")
    )
    covered = list(
        candidate.get("covered_fail_keys")
        or payload.get("covered_fail_keys")
        or coverage.get("covered_fail_keys")
        or []
    )
    remaining = list(
        candidate.get("remaining_fail_keys")
        or payload.get("remaining_fail_keys")
        or coverage.get("remaining_fail_keys")
        or []
    )

    if (not covered and not remaining) and fail_keys:
        candidate_overview = dict(candidate.get("overview") or {})
        candidate_fail_keys = sorted(
            [
                key
                for key, val in (candidate_overview.get("statuses") or {}).items()
                if str(val or "").upper() == "FAIL"
            ],
        )
        covered = sorted([key for key in fail_keys if key not in candidate_fail_keys])
        remaining = sorted([key for key in fail_keys if key in candidate_fail_keys])
        covers_all = len(fail_keys) > 0 and len(remaining) == 0

    meta["covers_all_current_failures"] = bool(covers_all)
    meta["covered_fail_keys"] = list(covered)
    meta["remaining_fail_keys"] = list(remaining)

    preview_overview = dict(candidate.get("overview") or {})
    if not preview_overview.get("statuses") and isinstance(candidate.get("resolved_candidate"), dict):
        preview_overview = dict((candidate.get("resolved_candidate") or {}).get("overview") or {})
    preview_statuses = dict(preview_overview.get("statuses") or {})
    preview_resolves_fail_keys_without_fail = bool(
        fail_keys
        and all(k in preview_statuses for k in fail_keys)
        and all(
            str(preview_statuses.get(k) or "").strip().upper() != "FAIL"
            and preview_statuses.get(k) != BEAM_STATUS_FAIL
            for k in fail_keys
        )
    )
    # Explicit gate: any FAIL in candidate preview statuses blocks commit before coverage rules.
    if _candidate_preview_statuses_have_explicit_fail(preview_statuses):
        meta["valid"] = False
        meta["reason"] = "candidate_preview_has_fail_status"
        return False, meta

    preview_has_fail_key = bool(preview_overview.get("any_fail"))
    if (
        not preview_has_fail_key
        and fail_keys
        and not requires_full_coverage
        and not all(k in preview_statuses for k in fail_keys)
    ):
        preview_has_fail_key = True
    # Do not infer preview FAIL from is_compliant alone when preview statuses
    # already show every current fail key as non-FAIL (e.g. FAIL -> NEAR LIMIT).
    if (
        not preview_has_fail_key
        and fail_keys
        and not requires_full_coverage
        and not bool(candidate.get("is_compliant"))
        and not preview_resolves_fail_keys_without_fail
    ):
        preview_has_fail_key = True
    if preview_has_fail_key:
        meta["valid"] = False
        meta["reason"] = "candidate_preview_has_fail_status"
        return False, meta

    if not requires_full_coverage:
        meta["valid"] = True
        meta["reason"] = "single_fail_or_no_fail"
        return True, meta

    if covers_all and not remaining:
        meta["valid"] = True
        meta["reason"] = "full_failure_coverage"
        return True, meta

    meta["valid"] = False
    meta["reason"] = "partial_failure_coverage"
    return False, meta
