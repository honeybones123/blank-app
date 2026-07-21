"""Bending guidance item coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any


_BENDING_GUIDANCE_DEPENDENCIES: tuple[str, ...] = (
    "_bending_item_from_geometry_trial",
    "_bending_near_limit_specific_title",
    "_design_optimisation_goal",
    "_guidance_action_updates",
    "_guidance_bucket",
    "_guidance_change_lines_for_updates",
    "_guidance_item",
    "_overall_status_from_rows",
    "_parse_util_value",
    "_reinforcement_options_remain",
)


def bind_bending_guidance_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _BENDING_GUIDANCE_DEPENDENCIES
            if name in namespace
        }
    )


def _bending_guidance_item(state: dict, pack: dict) -> dict | None:
    goal = _design_optimisation_goal(state)
    bottom_recommendation_available = (
        _reinforcement_options_remain(state)
        if goal in ("balanced", "shallower_beam")
        else False
    )
    rows = pack.get("rows") or []
    util = _parse_util_value(pack.get("summary_util"))
    status, _ = _overall_status_from_rows(rows)
    flexural_row = next((row for row in rows if str(row.get("title")) == "Flexural strength capacity"), None)
    ductility_row = next((row for row in rows if str(row.get("title")) == "Ductility limit"), None)
    flexural_status = str((flexural_row or {}).get("status") or "")
    ductility_status = str((ductility_row or {}).get("status") or "")
    flexural_util = _parse_util_value((flexural_row or {}).get("util"))
    ductility_util = _parse_util_value((ductility_row or {}).get("util"))
    bucket = _guidance_bucket(status, util)
    ductility_bucket = _guidance_bucket(ductility_status, ductility_util)
    flexural_bucket = _guidance_bucket(flexural_status, flexural_util)
    if ductility_bucket == "fail" and flexural_bucket != "fail":
        if bottom_recommendation_available:
            return _guidance_item(
                "bending",
                "Ductility limit governs",
                "Preferred fix: reduce bottom tensile ratio",
                "Alternative: increase beam width b",
                "Why: a lighter or cleaner bottom layout reduces neutral axis ratio before resorting to heavier geometry.",
                "Key levers: bottom reinforcement ratio, row layout, b, D",
                "apply_bottom_recommendation",
                {},
                status=ductility_status or status,
                util=ductility_util,
            )
        geo_item = _bending_item_from_geometry_trial(
            state,
            title="Ductility limit governs",
            status=ductility_status or status,
            util=ductility_util,
            bending_mode="ductility",
            secondary="Alternative: reduce bottom tensile steel if the layout allows",
            levers="Key levers: b, D, tensile reinforcement ratio",
        )
        if geo_item:
            return geo_item
        return _guidance_item(
            "bending",
            "Ductility limit governs",
            "Preferred fix: increase beam width b",
            "Fallback fix: increase depth D",
            "Why: width improves section balance more gently than inflating depth first when ductility governs.",
            "Key levers: b, D, tensile reinforcement ratio",
            "increase_width",
            {"delta_mm": 50},
            status=ductility_status or status,
            util=ductility_util,
        )
    if ductility_bucket == "warn" and flexural_bucket == "pass":
        if bottom_recommendation_available:
            return _guidance_item(
                "bending",
                "Ductility limit is close to the limit",
                "Preferred fix: reduce bottom tensile ratio slightly",
                "Alternative: increase beam width b",
                "Why: a lighter bottom layout usually adds ductility reserve more efficiently than growing depth.",
                "Key levers: bottom reinforcement ratio, row layout, b, D",
                "apply_bottom_recommendation",
                {},
                status=ductility_status or status,
                util=ductility_util,
            )
        geo_item = _bending_item_from_geometry_trial(
            state,
            title="Ductility limit is close to the limit",
            status=ductility_status or status,
            util=ductility_util,
            bending_mode="ductility",
            secondary="Alternative: reduce bottom tensile steel slightly if practical",
            levers="Key levers: b, D, tensile reinforcement ratio",
        )
        if geo_item:
            return geo_item
        return _guidance_item(
            "bending",
            "Ductility limit is close to the limit",
            "Preferred fix: increase beam width b",
            "Fallback fix: increase depth D",
            "Why: width is the gentler geometry lever for improving section balance when ductility is near the limit.",
            "Key levers: b, D, tensile reinforcement ratio",
            "increase_width",
            {"delta_mm": 50},
            status=ductility_status or status,
            util=ductility_util,
        )
    if bucket == "fail":
        if goal == "shallower_beam":
            if bottom_recommendation_available:
                return _guidance_item(
                    "bending",
                    "Increase bottom reinforcement",
                    "Add bottom reinforcement",
                    "Alternative: widen the section, then increase depth if needed",
                    "Why: flexural demand exceeds capacity. Adding bottom steel raises bending capacity while keeping depth unchanged.",
                    "Key levers: bottom reinforcement, b, D",
                    "apply_bottom_recommendation",
                    {},
                    status=status,
                    util=util,
                )
            geo_item = _bending_item_from_geometry_trial(
                state,
                title="Adjust section width or depth",
                status=status,
                util=util,
                bending_mode="governing",
                secondary="Alternative: add bottom reinforcement if not yet tried",
                levers="Key levers: b, D, bottom reinforcement",
            )
            if geo_item:
                return geo_item
            return _guidance_item(
                "bending",
                "Increase section width",
                "Increase beam width by ~50 mm",
                "Alternative: increase depth D by ~50–100 mm",
                "Why: bottom reinforcement cannot be increased practically; widening is usually the shallower lever before depth.",
                "Key levers: b, D, bottom reinforcement",
                "increase_width",
                {"delta_mm": 50},
                status=status,
                util=util,
            )
        if goal == "less_longitudinal_reinforcement":
            geo_item = _bending_item_from_geometry_trial(
                state,
                title="Increase depth or width for bending",
                status=status,
                util=util,
                bending_mode="governing",
                secondary="Alternative: increase depth first to cut bottom steel demand before widening",
                levers="Key levers: D, b, bottom reinforcement",
            )
            if geo_item:
                return geo_item
            return _guidance_item(
                "bending",
                "Increase depth to reduce steel demand",
                "Increase depth D by ~50-100 mm",
                "Alternative: increase beam width b",
                "Why: a deeper section increases lever arm and reduces required bottom steel for the same moment.",
                "Key levers: D, b, bottom reinforcement",
                "increase_depth",
                {"delta_mm": 100},
                status=status,
                util=util,
            )
        if bottom_recommendation_available:
            return _guidance_item(
                "bending",
                "Increase bottom reinforcement",
                "Add bottom reinforcement",
                "Alternative: increase depth D by ~50-100 mm",
                "Why: flexural demand exceeds capacity. Use practical reinforcement increases before enlarging the section.",
                "Key levers: bottom reinforcement, row layout, D",
                "apply_bottom_recommendation",
                {},
                status=status,
                util=util,
            )
        geo_item = _bending_item_from_geometry_trial(
            state,
            title="Increase depth or width for bending",
            status=status,
            util=util,
            bending_mode="governing",
            secondary="Alternative: add bottom reinforcement if practical",
            levers="Key levers: D, b, bottom reinforcement",
        )
        if geo_item:
            return geo_item
        return _guidance_item(
            "bending",
            "Increase depth",
            "Increase depth D by ~50-100 mm",
            "Alternative: increase beam width b",
            "Why: reinforcement cannot be increased practically, so section depth is the next lever.",
            "Key levers: D, b, bottom reinforcement",
            "increase_depth",
            {"delta_mm": 100},
            status=status,
            util=util,
        )
    if bucket == "warn":
        if goal == "shallower_beam":
            if bottom_recommendation_available:
                primary = "Add bottom reinforcement"
                secondary = "Alternative: widen the section, then increase depth if needed"
                reasoning = "Why: bending is near its limit. A small steel increase adds capacity before changing depth."
                levers = "Key levers: bottom reinforcement, b, D"
                action_type = "apply_bottom_recommendation"
                action_payload = {}
            else:
                primary = "Increase beam width by ~50 mm"
                secondary = "Alternative: increase depth D by ~25–50 mm"
                reasoning = "Why: bottom steel cannot be increased practically; width is usually the shallower lever than depth."
                levers = "Key levers: b, D, bottom reinforcement"
                action_type = "increase_width"
                action_payload = {"delta_mm": 50}
        elif goal == "less_longitudinal_reinforcement":
            primary = "Increase depth D by ~25-50 mm"
            secondary = "Alternative: increase beam width b"
            reasoning = "Why: a slightly deeper section adds reserve and usually cuts required bottom steel."
            levers = "Key levers: D, b, bottom reinforcement"
            action_type = "increase_depth"
            action_payload = {"delta_mm": 50}
        else:
            if bottom_recommendation_available:
                primary = "Tune bottom reinforcement"
                secondary = "Alternative: increase depth D by ~25-50 mm"
                reasoning = "Why: try a small layout or bar change before enlarging the section."
                levers = "Key levers: bottom reinforcement, row layout, D"
                action_type = "apply_bottom_recommendation"
                action_payload = {}
            else:
                primary = "Increase depth D by ~25-50 mm"
                secondary = "Alternative: increase beam width b"
                reasoning = "Why: reinforcement is already constrained; a modest depth increase is the next reserve lever."
                levers = "Key levers: D, b, bottom reinforcement"
                action_type = "increase_depth"
                action_payload = {"delta_mm": 50}
        use_title = _bending_near_limit_specific_title(goal, action_type) or "Bending is close to the limit"
        _upd = _guidance_action_updates(action_type, action_payload, state=state)
        _cl = _guidance_change_lines_for_updates(state, _upd or {})
        return _guidance_item(
            "bending",
            use_title,
            primary,
            secondary,
            reasoning,
            levers,
            action_type,
            action_payload,
            status=status,
            util=util,
            guidance_change_lines=_cl or None,
        )
    return None


__all__ = [
    "bind_bending_guidance_dependencies",
    "_bending_guidance_item",
]
