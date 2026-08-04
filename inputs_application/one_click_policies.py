"""Pure policy helpers used by the Inputs one-click transaction."""

from __future__ import annotations

import math
from collections.abc import Callable


def stage3_remaining_issue_class_from_overview_state(
    state: dict | None,
    overview: dict | None,
) -> str | None:
    if not isinstance(overview, dict):
        return None
    source = dict(state or {})
    shear_status = str(
        ((overview.get("statuses") or {}).get("shear") or "")
    ).strip().upper()
    design_status = str(
        source.get("shear_design_status") or ""
    ).strip().upper()
    truth_resolved = source.get("final_shear_truth_resolved")
    failure_reason = str(
        source.get("final_shear_truth_failure_reason") or ""
    ).strip()
    truth_status = str(
        source.get("shear_truth_status") or ""
    ).strip()
    if design_status == "INVALID" and shear_status == "PASS":
        return "truth"
    if (
        truth_resolved is False
        and bool(failure_reason or truth_status)
        and shear_status == "PASS"
    ):
        return "truth"
    return None


def one_click_has_unresolved_spacing_envelope_fail(
    eval_obj: dict | None,
) -> bool:
    if not isinstance(eval_obj, dict):
        return False
    overview = dict(eval_obj.get("overview") or {})
    shear_pack = ((overview.get("packs") or {}).get("shear") or {})
    source = str(
        shear_pack.get("summary_governing_source")
        or shear_pack.get("summary_governing_check_source")
        or ""
    ).strip()
    status = str(
        shear_pack.get("summary_governing_status")
        or shear_pack.get("summary_status")
        or ""
    ).strip().upper()
    reason = str(
        shear_pack.get("summary_governing_reason")
        or shear_pack.get("summary_reason")
        or ""
    ).strip()
    if source == "spacing_envelope" and status == "FAIL":
        return True
    return "spacing_envelope" in reason and status == "FAIL"


def one_click_directional_tie_key(
    old_util: float,
    new_util: float,
    mode_config: dict,
    *,
    default_target_min: float,
    default_target_max: float,
) -> float:
    low = float(
        mode_config.get("target_util_min", default_target_min)
        or default_target_min
    )
    high = float(
        mode_config.get("target_util_max", default_target_max)
        or default_target_max
    )
    if not math.isfinite(old_util) or not math.isfinite(new_util):
        return float("inf")
    if old_util < low:
        return -(new_util - old_util)
    if old_util > high:
        return -(old_util - new_util)
    return abs(new_util - old_util)


def rescue_bootstrap_partial_commit_allowed(
    *,
    solve: dict | None,
    current_fail_keys: list[str] | None,
    candidate_for_commit: dict | None,
    candidate_commit_meta: dict | None,
    solver_final_updates: dict | None,
    seed_eval: dict | None,
) -> bool:
    debug = dict(((solve or {}).get("one_click_solver_debug") or {}))
    if not bool(debug.get("rescue_mode_entered")):
        return False
    if not bool(debug.get("rescue_mode_effective_seed_found")):
        return False
    if (
        str((candidate_commit_meta or {}).get("reason") or "")
        != "candidate_preview_has_fail_status"
    ):
        return False
    fail_keys = sorted(
        str(key or "").strip().lower()
        for key in (current_fail_keys or [])
        if str(key or "").strip()
    )
    if "bending" not in fail_keys or "shear" not in fail_keys:
        return False
    if not isinstance(candidate_for_commit, dict) or not bool(
        solver_final_updates
    ):
        return False
    covered = sorted(
        str(key or "").strip().lower()
        for key in list(
            (candidate_commit_meta or {}).get("covered_fail_keys") or []
        )
        if str(key or "").strip()
    )
    remaining = sorted(
        str(key or "").strip().lower()
        for key in list(
            (candidate_commit_meta or {}).get("remaining_fail_keys") or []
        )
        if str(key or "").strip()
    )
    if not covered or len(remaining) >= len(fail_keys):
        return False
    _ = seed_eval
    return True


def one_click_exhaustion_next_hop_allowed(
    current_eval: dict | None,
    next_hop_payload: dict | None,
    mode_config: dict,
    *,
    resolver: Callable[..., bool],
    default_target_min: float,
    default_target_max: float,
    fail_status: str,
    optimisation_goal_resolver: Callable[..., str],
) -> bool:
    return bool(
        resolver(
            current_eval,
            next_hop_payload,
            mode_config,
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
    )


__all__ = [
    "one_click_directional_tie_key",
    "one_click_exhaustion_next_hop_allowed",
    "one_click_has_unresolved_spacing_envelope_fail",
    "rescue_bootstrap_partial_commit_allowed",
    "stage3_remaining_issue_class_from_overview_state",
]
