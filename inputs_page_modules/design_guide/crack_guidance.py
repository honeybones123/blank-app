"""Crack-control guidance item coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_CRACK_GUIDANCE_DEPENDENCIES: tuple[str, ...] = (
    "REO_SPACINGS",
    "_describe_guidance_step",
    "_evaluate_crack_with_state",
    "_guidance_bucket",
    "_guidance_item",
    "_merge_guidance_state",
    "_overall_status_from_rows",
    "_parse_util_value",
    "_pick_crack_ladder_first_improvement",
)


def bind_crack_guidance_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CRACK_GUIDANCE_DEPENDENCIES
            if name in namespace
        }
    )


def _crack_guidance_item(state: dict, pack: dict) -> dict | None:
    rows = pack.get("rows") or []
    util_candidates = [_parse_util_value(r.get("util")) for r in rows]
    util_values = [u for u in util_candidates if u is not None]
    util = max(util_values) if util_values else None
    status, _ = _overall_status_from_rows(rows)
    bucket = _guidance_bucket(status, util)
    if bucket not in ("fail", "warn"):
        return None
    base = _evaluate_crack_with_state(state)
    if not base:
        return None
    base_u = float(base.get("util", 0.0) or 0.0)
    picked = _pick_crack_ladder_first_improvement(state, base_util=base_u)
    if not picked:
        return None
    u_after = float(picked.get("util_after", 0.0) or 0.0)
    kind = str(picked.get("kind") or "")
    is_fail = bucket == "fail"
    title = "Crack control is failing" if is_fail else "Crack control is close to the limit"
    secondary = "Alternative: review cover and exposure inputs on the Crack page."
    levers = "Key levers: bar spacing, bar count, layout, cover, b, D"
    if kind == "geometry":
        reasoning = (
            f"Why: crack ladder — reinforcement and layout first, then best geometry trial (utilisation {util:.2f} → {u_after:.2f})."
            if util is not None
            else f"Why: geometry trial improves crack utilisation to {u_after:.2f}."
        )
        return _guidance_item(
            "crack",
            title,
            str(picked.get("label") or "Increase section size"),
            secondary,
            reasoning,
            levers,
            str(picked.get("action_type") or "increase_depth"),
            dict(picked.get("payload") or {}),
            status=status,
            util=util,
            guidance_before_after=str(picked.get("before_after") or "") or None,
        )
    updates = dict(picked.get("updates") or {})
    after_st = _merge_guidance_state(state, updates)
    ba = _describe_guidance_step(state, after_st, "reduce_bar_spacing", updates)
    reasoning = (
        f"Why: crack ladder — spacing, bar count, then crack-efficient layout before geometry ({util:.2f} → {u_after:.2f})."
        if util is not None
        else f"Why: crack-control ladder step ({u_after:.2f})."
    )
    return _guidance_item(
        "crack",
        title,
        str(picked.get("label") or "Adjust bottom reinforcement"),
        secondary,
        reasoning,
        levers,
        "reduce_bar_spacing",
        {"updates": updates, "delta_mm": 25.0, "minimum_spacing": float(min(REO_SPACINGS))},
        status=status,
        util=util,
        guidance_before_after=ba or None,
    )
