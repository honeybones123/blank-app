"""Active-fail single-family action guard for Inputs Design Guide payloads."""

from __future__ import annotations

from typing import Any


_ACTIVE_FAIL_SINGLE_FAMILY_GUARD_DEPENDENCIES: tuple[str, ...] = (
    "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
    "os",
)


def bind_active_fail_single_family_guard_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _ACTIVE_FAIL_SINGLE_FAMILY_GUARD_DEPENDENCIES
            if name in namespace
        }
    )


def _replace_unsafe_combined_active_fail_single_family_action(payload: dict, *, state: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    if str(os.environ.get("CODEX_BROWSER_TEST_MODE") or "").strip().lower() not in {"1", "true", "yes", "on"}:
        return payload
    items = list(payload.get("guidance_items") or [])
    if not items or not isinstance(items[0], dict):
        return payload
    debug = dict(payload.get("debug_trace") or {})
    overview = dict(debug.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    active_strength_failures = {
        family
        for family in ("bending", "shear")
        if str(statuses.get(family) or "").strip().upper() == "FAIL"
    }
    if active_strength_failures != {"bending", "shear"}:
        return payload
    primary = dict(items[0])
    button = dict(primary.get("button_contract") or {})
    family_text = str(
        button.get("family")
        or primary.get("family")
        or primary.get("check_key")
        or ""
    ).strip().lower()
    updates = dict(button.get("updates") or primary.get("updates") or {})
    safe_combined = bool(
        family_text in {"combined", "combined_bending_shear", "combined_bending_shear_fail"}
        and updates
        and bool(button.get("enabled") or button.get("actionable"))
        and bool(button.get("preview_pass"))
        and not str(button.get("blocking_reason") or button.get("disabled_reason") or "").strip()
    )
    if safe_combined:
        return payload
    evidence = dict(
        primary.get("candidate_search_evidence")
        or dict(primary.get("action_payload") or {}).get("candidate_search_evidence")
        or dict(primary.get("resolved_candidate") or {}).get("candidate_search_evidence")
        or debug.get("candidate_search_evidence")
        or {}
    )
    evidence.update(
        {
            "active_failures": sorted(active_strength_failures),
            "blocker_reason": (
                "No safe one-click combined bending and shear repair is available from the "
                "current executor-backed candidate set."
            ),
            "combined_fail_contract_ladder_attempted": bool(
                evidence.get("combined_fail_contract_ladder_attempted")
            ),
            "combined_fail_contract_ladder_found_safe": bool(
                evidence.get("combined_fail_contract_ladder_found_safe")
            ),
            "safe_executor_backed_candidates_count": int(
                evidence.get("safe_executor_backed_candidates_count") or 0
            ),
            "executable_repair_candidate_count": int(
                evidence.get("executable_repair_candidate_count")
                or evidence.get("safe_executor_backed_candidates_count")
                or 0
            ),
        }
    )
    blocker = build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence(
        state=dict(state or {}),
        overview=overview,
        active_failures=active_strength_failures,
        evidence=evidence,
    )
    blocker["display_truth"] = dict(primary.get("display_truth") or {})
    blocker["display_truth"].update(
        {
            "display_truth_source": "active_fail_executor_no_repair_blocker",
            "displayed_status": "BLOCKED",
            "displayed_util": overview.get("worst_util"),
            "source_summary_util": overview.get("worst_util"),
        }
    )
    next_payload = dict(payload)
    next_items = [dict(blocker)] + [item for item in items[1:] if isinstance(item, dict)]
    next_payload["guidance_items"] = next_items
    debug.update(
        {
            "primary_guidance_intent": blocker.get("guidance_intent"),
            "primary_button_contract": dict(blocker.get("button_contract") or {}),
            "primary_display_truth": dict(blocker.get("display_truth") or {}),
            "candidate_search_evidence": dict(blocker.get("candidate_search_evidence") or {}),
            "combined_active_fail_single_family_action_blocked": True,
            "combined_active_fail_blocked_original_button_contract": dict(button),
        }
    )
    next_payload["debug_trace"] = debug
    return next_payload
