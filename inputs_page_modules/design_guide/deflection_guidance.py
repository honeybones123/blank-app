"""Typed deflection guidance coordination for the Inputs Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class DeflectionGuidanceRuntime:
    evaluate_deflection_with_state: Callable[..., Any]
    guidance_bucket: Callable[..., Any]
    guidance_item: Callable[..., Any]
    overall_status_from_rows: Callable[..., Any]
    parse_util_value: Callable[..., Any]
    pick_deflection_ladder_first_improvement: Callable[..., Any]


def deflection_guidance_item(
    state: dict,
    pack: dict,
    *,
    runtime: DeflectionGuidanceRuntime,
) -> dict | None:
    rows = pack.get("rows") or []
    util = runtime.parse_util_value(pack.get("summary_util_total"))
    status, _ = runtime.overall_status_from_rows(rows)
    bucket = runtime.guidance_bucket(status, util)
    if bucket not in ("fail", "warn"):
        return None
    base = runtime.evaluate_deflection_with_state(state)
    if not base or base.get("util") is None:
        return None
    base_util = float(base["util"])
    picked = runtime.pick_deflection_ladder_first_improvement(
        state,
        base_util=base_util,
    )
    if not picked:
        return None
    util_after = float(picked.get("util_after", 0.0) or 0.0)
    kind = str(picked.get("kind") or "")
    span_note = (
        " Advisory only: a shorter effective span L_eff also reduces "
        "deflection (not applied automatically)."
    )
    is_fail = bucket == "fail"
    title = (
        "Deflection is high"
        if is_fail
        else "Deflection is close to the limit"
    )
    levers = "Key levers: D, b, sustained loads, span (advisory)"
    secondary = (
        "Alternative: review deflection inputs on the Deflection page."
        + span_note
    )
    if kind == "sustained_load":
        reasoning = (
            "Why: deflection ladder — depth and width trials first; then "
            f"one small sustained-load step ({util:.2f} → {util_after:.2f})."
            if util is not None
            else f"Why: sustained-load adjustment ({util_after:.2f})."
        )
        return runtime.guidance_item(
            "deflection",
            title,
            str(picked.get("label") or "Reduce sustained load slightly"),
            secondary,
            reasoning,
            levers,
            "deflection_reduce_sustained_load",
            {"updates": dict(picked.get("updates") or {})},
            status=status,
            util=util,
            guidance_before_after=(
                str(picked.get("before_after") or "") or None
            ),
        )
    reasoning = (
        "Why: deflection ladder — depth, then width if it helps stiffness, "
        f"before load tweaks ({util:.2f} → {util_after:.2f})."
        if util is not None
        else f"Why: geometry step ({util_after:.2f})."
    )
    return runtime.guidance_item(
        "deflection",
        title,
        str(picked.get("label") or "Increase depth"),
        secondary,
        reasoning + span_note,
        levers,
        str(picked.get("action_type") or "increase_depth"),
        dict(picked.get("payload") or {}),
        status=status,
        util=util,
        guidance_before_after=(
            str(picked.get("before_after") or "") or None
        ),
    )


__all__ = [
    "DeflectionGuidanceRuntime",
    "deflection_guidance_item",
]
