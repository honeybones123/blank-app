"""Inputs page tail render/audit coordinators."""

from __future__ import annotations

from typing import Any, Callable


def render_inputs_post_summary_actions_and_dev_audit(
    *,
    st_module: Any,
    inputs_render_audit: dict[str, str],
    apply_buttons_fn: Callable[[], None],
    auto_design_fn: Callable[[], None],
    agent_debug_log_fn: Callable[..., None],
) -> None:
    # Apply and auto-design callbacks remain behavior-critical; the route
    # dispatchers are extracted while solver/apply dependencies stay injected.
    apply_buttons_fn()
    auto_design_fn()

    if bool(st_module.session_state.get("_dev_mode")):
        agent_debug_log_fn(
            "Inputs dev render audit (end of render_inputs)",
            {
                "old_auto_design_panel_rendered": inputs_render_audit["old_auto_design_panel_rendered"],
                "design_guide_rendered": inputs_render_audit["design_guide_rendered"],
                "current_design_summary_rendered": inputs_render_audit["current_design_summary_rendered"],
                "next_mode_recommendation_rendered": inputs_render_audit["next_mode_recommendation_rendered"],
                "bottom_tightening_rendered": inputs_render_audit["bottom_tightening_rendered"],
                "geometry_tightening_rendered": inputs_render_audit["geometry_tightening_rendered"],
                "shear_tightening_rendered": inputs_render_audit["shear_tightening_rendered"],
            },
            location="inputs_page.py:render_inputs:dev_render_audit_end",
            hypothesis_id="H_INPUTS_DEV_RENDER_AUDIT",
        )


def render_inputs_debug_audit(
    *,
    inputs_debug_audit: bool,
    before_state,
    st_module: Any,
    input_page_tab_keys: dict,
    shared_defaults: dict,
    log_debug_fn: Callable[..., None],
) -> None:
    if inputs_debug_audit and before_state is not None:
        after_widgets_state = st_module.session_state
        for key in before_state:
            if before_state[key] != after_widgets_state.get(key):
                log_debug_fn(
                    f"STATE CHANGED DURING RENDER - {key}",
                    f"{before_state[key]} -> {after_widgets_state.get(key)}",
                )
        tab_keys = list(input_page_tab_keys.values())
        for key in shared_defaults.keys():
            if key not in tab_keys:
                if before_state.get(key) != after_widgets_state.get(key):
                    log_debug_fn(
                        f"WARNING: DIRECT SHARED WRITE - {key}",
                        f"{before_state.get(key)} -> {after_widgets_state.get(key)}",
                    )
        log_debug_fn("---- INPUTS PAGE LOAD END ----")


def render_inputs_tail(
    *,
    inputs_render_audit: dict[str, str],
    before_state,
    mark: Callable[[str], None],
    perf_start,
    perf_marks,
    sub_marks,
    t0,
    post_summary_actions_fn: Callable[..., None],
    debug_audit_fn: Callable[..., None],
    design_guide_debug_sidebar_fn: Callable[[], None],
    perf_finalization_fn: Callable[..., None],
) -> None:
    post_summary_actions_fn(
        inputs_render_audit=inputs_render_audit,
    )
    debug_audit_fn(before_state=before_state)

    design_guide_debug_sidebar_fn()
    mark("end")

    perf_finalization_fn(
        perf_start=perf_start,
        perf_marks=perf_marks,
        sub_marks=sub_marks,
        t0=t0,
    )


__all__ = [
    "render_inputs_debug_audit",
    "render_inputs_post_summary_actions_and_dev_audit",
    "render_inputs_tail",
]
