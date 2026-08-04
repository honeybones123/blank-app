"""Design Guide preview contract coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Callable


@dataclass(frozen=True)
class PreviewContractRuntime:
    build_design_actions_context: Callable[[dict], dict]
    collect_design_overview: Callable[..., dict]
    guidance_state_snapshot: Callable[[dict], dict]
    overview_required_checks_acceptable: Callable[[dict], bool]
    parse_util_value: Callable[[Any], float | None]
    evaluate_candidate_full: Callable[..., dict | None]


_PREVIEW_CONTRACT_DEPENDENCIES: tuple[str, ...] = (
    "_build_design_actions_context",
    "_collect_design_overview",
    "_guidance_state_snapshot",
    "_overview_required_checks_acceptable",
    "_parse_util_value",
    "evaluate_candidate_full",
)


def bind_preview_contract_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PREVIEW_CONTRACT_DEPENDENCIES
            if name in namespace
        }
    )


def _design_guide_preview_contract_for_updates(
    state: dict,
    updates: dict,
    *,
    runtime: PreviewContractRuntime | None = None,
) -> tuple[bool, float | None, str | None]:
    if runtime is None:
        namespace = globals()
        runtime = PreviewContractRuntime(
            build_design_actions_context=namespace[
                "_build_design_actions_context"
            ],
            collect_design_overview=namespace["_collect_design_overview"],
            guidance_state_snapshot=namespace["_guidance_state_snapshot"],
            overview_required_checks_acceptable=namespace[
                "_overview_required_checks_acceptable"
            ],
            parse_util_value=namespace["_parse_util_value"],
            evaluate_candidate_full=namespace["evaluate_candidate_full"],
        )
    _build_design_actions_context = runtime.build_design_actions_context
    _collect_design_overview = runtime.collect_design_overview
    _guidance_state_snapshot = runtime.guidance_state_snapshot
    _overview_required_checks_acceptable = (
        runtime.overview_required_checks_acceptable
    )
    _parse_util_value = runtime.parse_util_value
    evaluate_candidate_full = runtime.evaluate_candidate_full
    if not updates:
        return False, None, "missing_updates"
    try:
        current_overview = _collect_design_overview(
            _guidance_state_snapshot(state or {}),
            context=_build_design_actions_context(state or {}),
        )
    except Exception:
        current_overview = {}
    try:
        trial_state = dict(_guidance_state_snapshot(state or {}))
        trial_state.update(dict(updates))
        preview = evaluate_candidate_full(
            _guidance_state_snapshot(trial_state),
            source="design_guide_button_contract_preview",
            updates=dict(updates),
        )
    except Exception:
        return False, None, "preview_exception"
    if not isinstance(preview, dict):
        return False, None, "preview_unavailable"
    overview = dict(preview.get("overview") or {})
    expected_util = _parse_util_value(
        preview.get("worst_util")
        or overview.get("worst_util")
        or overview.get("governing_util")
    )
    statuses = dict(overview.get("statuses") or {})
    fail_statuses = [
        str(key)
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    ]
    current_statuses = dict((current_overview or {}).get("statuses") or {})
    current_fail_statuses = [
        str(key)
        for key, value in current_statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    ]
    new_fail_statuses = sorted(set(fail_statuses) - set(current_fail_statuses))
    if new_fail_statuses:
        return False, expected_util, "candidate_preview_introduces_fail_status"
    if fail_statuses:
        return False, expected_util, "candidate_preview_has_fail_status"
    if not _overview_required_checks_acceptable(overview):
        return False, expected_util, "candidate_preview_not_compliant"
    if not current_fail_statuses:
        preview_pass = True
    else:
        current_util = _parse_util_value(
            (current_overview or {}).get("worst_util")
            or (current_overview or {}).get("governing_util")
        )
        improves_util = bool(
            current_util is not None
            and expected_util is not None
            and float(expected_util) < float(current_util) - 1e-9
        )
        reduces_fail_count = bool(len(fail_statuses) < len(current_fail_statuses))
        preview_pass = bool(improves_util or reduces_fail_count or not current_fail_statuses)
        if not preview_pass:
            return False, expected_util, "candidate_preview_does_not_improve_active_failure"
    return True, expected_util, None


__all__ = [
    "PreviewContractRuntime",
    "bind_preview_contract_dependencies",
    "_design_guide_preview_contract_for_updates",
]
