"""Design Guide display-truth coordination."""

from __future__ import annotations

from typing import Any

from inputs_application.engineering_predicates import parse_util_value as _parse_util_value
from inputs_application.geometry_search_policy import (
    design_mode_config as _design_mode_config,
    design_optimisation_goal as _design_optimisation_goal,
    resolved_efficiency_target_band as _resolved_efficiency_target_band,
)

DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES = frozenset(
    {
        "published_summary",
        "candidate_preview",
        "post_commit_truth",
    }
)


_DISPLAY_TRUTH_DEPENDENCIES: tuple[str, ...] = ()


def bind_display_truth_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _DISPLAY_TRUTH_DEPENDENCIES
            if name in namespace
        }
    )


def _design_guide_status_from_overview(overview: dict | None) -> str | None:
    ov = overview if isinstance(overview, dict) else {}
    if bool(ov.get("any_fail")):
        return "FAIL"
    if bool(ov.get("any_warn")):
        return "NEAR LIMIT"
    if bool(ov.get("all_key_pass")):
        return "PASS"
    statuses = dict(ov.get("statuses") or {})
    values = [
        str(value or "").strip().upper()
        for value in statuses.values()
        if str(value or "").strip()
    ]
    if any(value == "FAIL" for value in values):
        return "FAIL"
    if any(value == "NEAR LIMIT" for value in values):
        return "NEAR LIMIT"
    if values and all(value == "PASS" for value in values):
        return "PASS"
    return None


def _guidance_item_expected_util(item: dict | None) -> float | None:
    if not isinstance(item, dict):
        return None
    payload = item.get("action_payload")
    payload = dict(payload) if isinstance(payload, dict) else {}
    value = payload.get("expected_governing_util")
    if value is None:
        value = payload.get("resolved_candidate_post_util")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _design_guide_target_band_for_state(state: dict | None, mode_config: dict | None = None) -> tuple[float, float]:
    cfg = mode_config if isinstance(mode_config, dict) else _design_mode_config(_design_optimisation_goal(state or {}))
    lo, hi, _ = _resolved_efficiency_target_band(cfg, goal=_design_optimisation_goal(state or {}))
    return float(lo), float(hi)


def _design_guide_summary_util(overview: dict | None) -> float | None:
    ov = overview if isinstance(overview, dict) else {}
    return _parse_util_value(ov.get("worst_util") or ov.get("governing_util"))


def _design_guide_candidate_overview(item: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    payload = dict(item.get("action_payload") or {})
    resolved = item.get("resolved_candidate")
    if not isinstance(resolved, dict):
        resolved = payload.get("resolved_candidate")
    resolved = dict(resolved or {})
    overview = resolved.get("overview")
    return dict(overview) if isinstance(overview, dict) else {}


def _design_guide_candidate_util(item: dict | None) -> float | None:
    if not isinstance(item, dict):
        return None
    contract = dict(item.get("button_contract") or {})
    value = contract.get("expected_util")
    if value is None:
        value = _guidance_item_expected_util(item)
    if value is None:
        overview = _design_guide_candidate_overview(item)
        value = overview.get("worst_util") or overview.get("governing_util")
    if value is None:
        resolved = dict(item.get("resolved_candidate") or {})
        payload = dict(item.get("action_payload") or {})
        value = (
            resolved.get("candidate_post_util")
            or resolved.get("worst_util")
            or payload.get("resolved_candidate_post_util")
        )
    return _parse_util_value(value)


def _design_guide_post_commit_util(item: dict | None = None, overview: dict | None = None) -> float | None:
    if isinstance(item, dict):
        value = item.get("source_post_commit_util") or item.get("post_commit_util")
        parsed = _parse_util_value(value)
        if parsed is not None:
            return parsed
    return _design_guide_summary_util(overview)


def _design_guide_item_uses_candidate_preview(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("action_type") or "").strip():
        return True
    contract = dict(item.get("button_contract") or {})
    return bool(dict(contract.get("updates") or {}) or contract.get("source_candidate_id"))


def _design_guide_display_truth_for_item(
    item: dict | None,
    *,
    state: dict,
    overview: dict | None,
    mode_config: dict | None = None,
    source_override: str | None = None,
    post_commit_util: float | None = None,
    post_commit_status: str | None = None,
) -> dict:
    source = str(source_override or "").strip()
    if source not in DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES:
        existing_truth = dict((item or {}).get("display_truth") or {}) if isinstance(item, dict) else {}
        existing_source = str(
            existing_truth.get("display_truth_source")
            or ((item or {}).get("display_truth_source") if isinstance(item, dict) else "")
            or ""
        ).strip()
        source = (
            existing_source
            if existing_source in DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES
            else "candidate_preview"
            if _design_guide_item_uses_candidate_preview(item)
            else "published_summary"
        )
    target_low, target_high = _design_guide_target_band_for_state(state, mode_config)
    source_summary_util = _design_guide_summary_util(overview)
    source_candidate_util = _design_guide_candidate_util(item)
    source_post_commit_util = _parse_util_value(post_commit_util)
    if source_post_commit_util is None and source == "post_commit_truth":
        source_post_commit_util = _design_guide_post_commit_util(item, overview)

    summary_status = _design_guide_status_from_overview(overview)
    candidate_overview = _design_guide_candidate_overview(item)
    candidate_status = _design_guide_status_from_overview(candidate_overview)
    if candidate_status is None and isinstance(item, dict):
        contract = dict(item.get("button_contract") or {})
        if contract:
            candidate_status = "PREVIEW_PASS" if bool(contract.get("preview_pass")) else "PREVIEW_BLOCKED"
    if candidate_status is None and isinstance(item, dict):
        candidate_status = str(item.get("status") or "").strip().upper() or None

    if source == "candidate_preview":
        displayed_util = source_candidate_util
        displayed_status = candidate_status
    elif source == "post_commit_truth":
        displayed_util = source_post_commit_util
        displayed_status = str(post_commit_status or "").strip().upper() or summary_status
    else:
        displayed_util = source_summary_util
        displayed_status = summary_status

    displayed_within = bool(
        displayed_util is not None
        and float(target_low) <= float(displayed_util) <= float(target_high)
    )
    return {
        "displayed_util": displayed_util,
        "displayed_status": displayed_status,
        "display_truth_source": source,
        "target_low": target_low,
        "target_high": target_high,
        "displayed_within_target_band": bool(displayed_within),
        "source_summary_util": source_summary_util,
        "source_candidate_util": source_candidate_util,
        "source_post_commit_util": source_post_commit_util,
    }


def _design_guide_apply_display_truth_to_items(
    items: list[dict] | None,
    *,
    state: dict,
    overview: dict | None,
    mode_config: dict | None = None,
) -> list[dict]:
    out: list[dict] = []
    for item in list(items or []):
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        truth = _design_guide_display_truth_for_item(
            next_item,
            state=state,
            overview=overview,
            mode_config=mode_config,
        )
        next_item["display_truth"] = dict(truth)
        next_item.update(truth)
        if (
            str(next_item.get("guidance_intent") or "") == "already_efficient"
            and not (
                str(truth.get("display_truth_source") or "") == "published_summary"
                and bool(truth.get("displayed_within_target_band"))
            )
        ):
            softer = (
                "Further reductions would lower reserve capacity or stiffness; the guide did not select "
                "a material one-click change for the published current state."
            )
            next_item["primary_action"] = softer
            next_item["guidance_why"] = "\n".join(
                [
                    softer,
                    "The solver did not find a smaller practical option that kept the governing checks acceptable.",
                    "Further reductions can reduce bending capacity, shear capacity, and stiffness.",
                ]
            )
            next_item["guidance_why_text_compact"] = next_item["guidance_why"]
        out.append(next_item)
    return out


__all__ = [
    "DESIGN_GUIDE_DISPLAY_TRUTH_SOURCES",
    "bind_display_truth_dependencies",
    "_design_guide_candidate_overview",
    "_design_guide_candidate_util",
    "_design_guide_display_truth_for_item",
    "_design_guide_apply_display_truth_to_items",
    "_design_guide_item_uses_candidate_preview",
    "_design_guide_post_commit_util",
    "_design_guide_summary_util",
    "_design_guide_target_band_for_state",
]
