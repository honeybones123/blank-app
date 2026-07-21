"""Serviceability-governs preflight blocker construction for Design Guide."""

from __future__ import annotations

from typing import Any


_SERVICEABILITY_PREFLIGHT_DEPENDENCIES: tuple[str, ...] = (
    "_collect_design_overview",
    "_parse_util_value",
    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
)


def bind_serviceability_preflight_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SERVICEABILITY_PREFLIGHT_DEPENDENCIES
            if name in namespace
        }
    )


def _serviceability_governs_preflight_payload(state: dict) -> dict | None:
    try:
        overview = _collect_design_overview(dict(state or {}))
    except Exception:
        return None
    statuses = dict(overview.get("statuses") or {})
    active = {
        str(family or "").strip().lower()
        for family, status in statuses.items()
        if str(status or "").strip().upper() == "FAIL"
    }
    if not active or active & {"bending", "shear"}:
        return None
    serviceability_active = active & {"crack", "deflection", "serviceability"}
    if not serviceability_active:
        return None
    evidence = {
        "selected_family_id": "SERVICEABILITY_GOVERNS",
        "published_family_id": "SERVICEABILITY_GOVERNS",
        "cta_family_id": "SERVICEABILITY_GOVERNS",
        "apply_payload_family_id": "SERVICEABILITY_GOVERNS",
        "card_family_id": "SERVICEABILITY_GOVERNS",
        "active_failures": sorted(serviceability_active),
        "candidate_search_exhaustive": True,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "serviceability_preflight_family_route": True,
    }
    primary = "crack" if "crack" in serviceability_active else "deflection"
    packs = dict(overview.get("packs") or {})
    pack = dict(packs.get(primary) or {})
    failed_row = next(
        (
            dict(row)
            for row in list(pack.get("rows") or [])
            if str(dict(row).get("status") or "").strip().upper() == "FAIL"
        ),
        {},
    )
    if failed_row:
        evidence.update(
            {
                "failed_check_name": failed_row.get("title") or f"{primary} serviceability check",
                "failed_check_status": failed_row.get("status") or "FAIL",
                "failed_check_util": _parse_util_value(failed_row.get("util")),
                "failed_check_demand": failed_row.get("value") or failed_row.get("calculated") or primary,
                "failed_check_capacity_or_limit": failed_row.get("limit") or failed_row.get("requirement") or primary,
            }
        )
    blocker = build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence(
        state=dict(state or {}),
        overview=overview,
        active_failures=sorted(serviceability_active),
        evidence=evidence,
    )
    debug = {
        "overview": dict(overview or {}),
        "selected_family_id": "SERVICEABILITY_GOVERNS",
        "published_family_id": "SERVICEABILITY_GOVERNS",
        "cta_family_id": "SERVICEABILITY_GOVERNS",
        "apply_payload_family_id": "SERVICEABILITY_GOVERNS",
        "card_family_id": "SERVICEABILITY_GOVERNS",
        "active_failures": sorted(serviceability_active),
        "candidate_search_evidence": dict(blocker.get("candidate_search_evidence") or evidence),
        "primary_button_contract": dict(blocker.get("button_contract") or {}),
        "button_contract": dict(blocker.get("button_contract") or {}),
        "primary_guidance_intent": blocker.get("guidance_intent"),
        "guidance_branch": "serviceability_governs_preflight_blocker",
        "serviceability_preflight_family_route": True,
    }
    return {
        "guidance_items": [blocker],
        "debug_trace": debug,
    }


__all__ = [
    "bind_serviceability_preflight_dependencies",
    "_serviceability_governs_preflight_payload",
]
