"""Design Guide terminal-state derivation helpers."""

from __future__ import annotations

from typing import Any


_TERMINAL_STATE_DEPENDENCIES: tuple[str, ...] = (
    "_candidate_cache_key",
    "_design_guide_terminal_state_from_render_artifacts",
    "_first_actionable_guidance_item",
    "_parse_util_value",
)


def bind_terminal_state_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _TERMINAL_STATE_DEPENDENCIES
            if name in namespace
        }
    )


def _derive_design_guide_terminal_state_from_current_overview(
    guidance_debug: dict,
    guidance_disp_state: dict,
    guidance_items: list[dict],
) -> str | None:
    dbg = dict(guidance_debug or {})
    existing = _design_guide_terminal_state_from_render_artifacts(guidance_items, dbg)
    ov = dict(dbg.get("overview") or {})
    statuses = dict(ov.get("statuses") or {})
    utils = dict(ov.get("utils") or {})
    fail_keys = [
        str(key)
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    ]
    numeric_utils = [
        util for util in (_parse_util_value(value) for value in utils.values())
        if util is not None and util > 0.0
    ]
    gov_util = next(
        (
            util for util in (
                _parse_util_value(ov.get("governing_util")),
                _parse_util_value(ov.get("worst_util")),
                _parse_util_value(dbg.get("current_util")),
                max(numeric_utils) if numeric_utils else None,
            )
            if util is not None and util > 0.0
        ),
        None,
    )
    eff = dict(dbg.get("efficiency_tightening_state") or {})
    target_lo = _parse_util_value(eff.get("target_band_lo"))
    target_hi = _parse_util_value(eff.get("target_band_hi"))
    if target_lo is None:
        target_lo = 0.82
    if target_hi is None:
        target_hi = 0.92
    actionable_item = _first_actionable_guidance_item(guidance_items)
    meta = {
        "source": "none",
        "current_fail_keys": list(fail_keys),
        "current_governing_util": gov_util,
        "target_band_lo": target_lo,
        "target_band_hi": target_hi,
        "has_actionable_item": bool(actionable_item),
        "state_fp": _candidate_cache_key(dict(guidance_disp_state or {})),
    }
    if actionable_item and bool((actionable_item or {}).get("allow_in_target_primary_action")):
        meta["source"] = "blocked_by_in_target_primary_refinement"
        meta["actionable_title"] = (actionable_item or {}).get("title_main") or (actionable_item or {}).get("title")
        if isinstance(guidance_debug, dict):
            guidance_debug["_derived_terminal_state_meta"] = dict(meta)
        return None
    if existing in {"optimal", "very_low_demand"}:
        meta["source"] = "explicit_render_artifact"
        if isinstance(guidance_debug, dict):
            guidance_debug["_derived_terminal_state_meta"] = dict(meta)
        return existing
    if not fail_keys:
        in_target_band_now = (
            gov_util is not None
            and gov_util >= float(target_lo)
            and gov_util <= float(target_hi)
        )
        if in_target_band_now and not actionable_item:
            meta["source"] = "derived_current_overview"
            if isinstance(guidance_debug, dict):
                guidance_debug["_derived_terminal_state_meta"] = dict(meta)
            return "optimal"
        if gov_util is not None and gov_util < 0.20 and not actionable_item:
            meta["source"] = "derived_current_overview"
            if isinstance(guidance_debug, dict):
                guidance_debug["_derived_terminal_state_meta"] = dict(meta)
            return "very_low_demand"
        if not actionable_item:
            meta["source"] = "derived_current_overview"
            if isinstance(guidance_debug, dict):
                guidance_debug["_derived_terminal_state_meta"] = dict(meta)
            return "optimal"
    if isinstance(guidance_debug, dict):
        guidance_debug["_derived_terminal_state_meta"] = dict(meta)
    return None


__all__ = [
    "bind_terminal_state_dependencies",
    "_derive_design_guide_terminal_state_from_current_overview",
]
