"""Model reinforcement widget mirror overlay execution."""

from __future__ import annotations

from typing import Any, Callable


def overlay_inputs_reo_widget_mirrors_for_model(
    *,
    state: dict,
    page_slug: str,
    summary_debug: dict | None,
    widget_state: dict,
    overlay_plan_fn: Callable[..., Any],
    build_legacy_longitudinal_mirrors_from_rows_fn: Callable[[dict], dict],
    build_canonical_design_state_pack_fn: Callable[[dict], dict],
) -> tuple[dict, dict]:
    plan = overlay_plan_fn(
        page_slug=page_slug,
        state=state,
        summary_debug=summary_debug,
        widget_state=widget_state,
    )
    working = dict(plan.working_state)
    debug_payload = dict(plan.debug_payload)
    overlay_keys = list(plan.overlay_keys)
    if overlay_keys:
        working.update(build_legacy_longitudinal_mirrors_from_rows_fn(working))
        pack_failed = False
        try:
            canonical_pack = build_canonical_design_state_pack_fn(working)
            if isinstance(canonical_pack, dict):
                working.update(canonical_pack)
        except Exception:
            pack_failed = True
            debug_payload["fast_model_reo_widget_overlay_pack_failed"] = True
        working.update(build_legacy_longitudinal_mirrors_from_rows_fn(working))
        for section, legacy_prefix in (("bot", "bot"), ("top", "top")):
            for row_index in (1, 2):
                bars_key = f"{section}_row_{row_index}_bars"
                dia_key = f"{section}_row_{row_index}_dia"
                working[f"{legacy_prefix}{row_index}_count"] = max(
                    0,
                    int(
                        float(
                            working.get(
                                bars_key,
                                working.get(f"{legacy_prefix}{row_index}_count", 0),
                            )
                            or 0
                        )
                    ),
                )
                working[f"db_{legacy_prefix}_{row_index}"] = max(
                    0.0,
                    float(
                        working.get(
                            dia_key,
                            working.get(f"db_{legacy_prefix}_{row_index}", 0.0),
                        )
                        or 0.0
                    ),
                )
        if pack_failed and any(
            str(key).startswith("bot_row_") or key == "bot_bar_coords_stale"
            for key in overlay_keys
        ):
            working["bot_bar_coords"] = []
        if pack_failed and any(
            str(key).startswith("top_row_") or key == "top_bar_coords_stale"
            for key in overlay_keys
        ):
            working["top_bar_coords"] = []
        debug_payload["fast_model_reo_widget_overlay_applied"] = True
        debug_payload["fast_model_reo_widget_overlay_count"] = len(set(overlay_keys))
        debug_payload["fast_model_reo_widget_overlay_keys"] = sorted(set(overlay_keys))
    return working, debug_payload


__all__ = ["overlay_inputs_reo_widget_mirrors_for_model"]
