"""Inputs startup hydration coordination."""

from __future__ import annotations

from typing import Callable


def render_inputs_startup_hydration(
    *,
    ss: dict,
    mark: Callable[[str], None],
    load_active_beam_into_shared_fn: Callable[[], bool],
    apply_canonical_convenience_resync_to_shared_fn: Callable[..., None],
    inputs_hydration_trace_log_fn: Callable[..., None],
    force_inputs_apply_refresh_cycle_fn: Callable[[str], None],
    agent_debug_log_fn: Callable[..., None],
    final_log_append_fn: Callable[..., None],
    final_log_increment_fn: Callable[..., None],
    final_log_set_flag_fn: Callable[..., None],
) -> None:
    inputs_startup_debug: dict[str, object] = {
        "explicit_beam_hydrate": False,
        "pending_refresh_happened": False,
        "ordinary_rerun_only": True,
    }
    ss["_inputs_longitudinal_reo_force_refresh_processed_this_run"] = False
    ss["_inputs_shear_force_refresh_processed_this_run"] = False
    pending_refresh_present_before_pop = bool(ss.get("_pending_inputs_apply_refresh"))
    ss["_inputs_pending_refresh_present_before_pop"] = pending_refresh_present_before_pop

    explicit_beam_hydrate = bool(load_active_beam_into_shared_fn())
    mark("load_active_beam")
    inputs_startup_debug["explicit_beam_hydrate"] = explicit_beam_hydrate
    if explicit_beam_hydrate:
        apply_canonical_convenience_resync_to_shared_fn(
            source="beam_load_active_into_shared"
        )
        inputs_startup_debug["ordinary_rerun_only"] = False
        inputs_hydration_trace_log_fn("render_inputs_hydrate", reason="explicit_beam_load", force=True)
        try:
            final_log_append_fn(
                "render_inputs_forced_hydrate_beam_load",
                {"hydration_layer": "render_inputs", "force_on_page_change": True},
            )
            final_log_increment_fn("render_forced_hydrate_beam_load", 1)
        except Exception:
            pass
        ss["_force_inputs_widget_reseed_once"] = False
        ss["_force_inputs_shear_widget_reseed_once"] = False
        force_inputs_apply_refresh_cycle_fn("explicit_beam_load")

    pending_refresh = ss.pop("_pending_inputs_apply_refresh", None)
    if pending_refresh:
        inputs_startup_debug["pending_refresh_happened"] = True
        inputs_startup_debug["ordinary_rerun_only"] = False
        pending_refresh_source = str((pending_refresh or {}).get("source") or "")
        inputs_hydration_trace_log_fn(
            "render_inputs_hydrate",
            reason="pending_inputs_apply_refresh",
            source=pending_refresh_source,
            force=True,
        )
        try:
            final_log_set_flag_fn("pending_inputs_apply_refresh_consumed", True)
            final_log_append_fn(
                "render_inputs_forced_hydrate_pending_refresh",
                {
                    "hydration_layer": "render_inputs",
                    "refresh_source": pending_refresh_source,
                    "force_on_page_change": True,
                },
            )
            final_log_increment_fn("render_forced_hydrate_pending_refresh", 1)
        except Exception:
            pass
        ss["_force_inputs_widget_reseed_once"] = False
        ss["_force_inputs_shear_widget_reseed_once"] = False
        if pending_refresh_source == "design_action_widget_sync":
            try:
                final_log_append_fn(
                    "render_inputs_pending_refresh_skip_force_cycle",
                    {
                        "refresh_source": pending_refresh_source,
                        "reason": "current_inputs_widgets_already_match_user_edit",
                    },
                )
            except Exception:
                pass
        else:
            force_inputs_apply_refresh_cycle_fn(
                f"pending_inputs_apply_refresh:{pending_refresh_source or 'unknown'}"
            )
    force_inputs_row_reseed_once = bool(ss.get("_force_inputs_widget_reseed_once"))
    force_inputs_shear_reseed_once = bool(ss.get("_force_inputs_shear_widget_reseed_once"))
    if force_inputs_row_reseed_once or force_inputs_shear_reseed_once:
        inputs_startup_debug["ordinary_rerun_only"] = False
        ss["_force_inputs_widget_reseed_once"] = False
        ss["_force_inputs_shear_widget_reseed_once"] = False
        if force_inputs_row_reseed_once and force_inputs_shear_reseed_once:
            force_inputs_apply_refresh_cycle_fn("force_inputs_widget_and_shear_widget_reseed_once")
        elif force_inputs_shear_reseed_once:
            force_inputs_apply_refresh_cycle_fn("force_inputs_shear_widget_reseed_once")
        else:
            force_inputs_apply_refresh_cycle_fn("force_inputs_widget_reseed_once")
    mark("hydrate_widgets")

    agent_debug_log_fn(
        "Inputs beam-module startup trace",
        inputs_startup_debug,
        location="inputs_page.py:render_inputs:beam_startup",
        hypothesis_id="H_BEAM_MODULE_STARTUP",
    )


__all__ = ["render_inputs_startup_hydration"]
