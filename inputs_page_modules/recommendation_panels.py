"""Render coordinators for Inputs recommendation popover panels."""

from __future__ import annotations

from typing import Any, Callable


def render_recommendation_apply_button(
    *,
    st_module: Any,
    button_label: str,
    button_key: str,
    compact: bool,
    applied: bool,
) -> bool:
    return st_module.button(
        "Applied" if applied else button_label,
        key=button_key,
        type="secondary",
        use_container_width=not compact,
        disabled=applied,
    )


def render_geometry_recommendation_panel(
    *,
    st_module: Any,
    button_key: str,
    source: str,
    compact: bool,
    shared_state_snapshot_fn: Callable[[], dict[str, Any]],
    resolve_popover_recommendation_fn: Callable[..., dict[str, Any] | None],
    compute_geometry_recommendation_fn: Callable[..., Any],
    updates_match_state_fn: Callable[[dict[str, Any], dict[str, Any]], bool],
    design_optimisation_goal_label_fn: Callable[[dict[str, Any]], str],
    resolve_geometry_width_context_fn: Callable[[dict[str, Any]], tuple[str, str, float]],
    float_from_state_fn: Callable[..., float],
    evaluate_bending_with_bottom_state_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
    evaluate_shear_with_state_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
    apply_geometry_recommendation_fn: Callable[..., Any],
) -> None:
    current_state = shared_state_snapshot_fn()
    recommendation = resolve_popover_recommendation_fn(
        cache_name="geometry",
        state=current_state,
        button_key=button_key,
        compute_fn=compute_geometry_recommendation_fn,
        empty_message="Generate a geometry recommendation on demand for the current beam state.",
    )
    if not recommendation:
        return
    geometry_applied = updates_match_state_fn(current_state, recommendation["updates"])
    goal_label = design_optimisation_goal_label_fn(current_state)
    _width_key, width_label, current_width = resolve_geometry_width_context_fn(current_state)
    current_depth = float_from_state_fn(current_state, "D", 600.0)
    _ = current_depth
    current_bending = evaluate_bending_with_bottom_state_fn(current_state) or {}
    current_shear = evaluate_shear_with_state_fn(current_state) or {}
    current_bending_util = float(current_bending.get("Mu_util", 0.0) or 0.0)
    current_shear_util = float(current_shear.get("util", 0.0) or 0.0)
    st_module.markdown(f"**Key idea**  \n{goal_label} still works through geometry first, and depth usually gives the biggest gain because it improves both lever arm and effective shear depth.")
    st_module.markdown("**Design impact**")
    st_module.markdown("- Larger `D` usually reduces bending and shear utilisation together.")
    st_module.markdown(f"- Width changes are secondary here: current `{width_label}` is {current_width:.0f} mm and the trial value is {recommendation['width']:.0f} mm.")
    st_module.markdown(f"- This trial moves bending from {current_bending_util:.2f} to {recommendation['bending_util']:.2f} and shear from {current_shear_util:.2f} to {recommendation['shear_util']:.2f}.")
    st_module.markdown("**Typical action**")
    st_module.markdown(f"- Test `{width_label} = {recommendation['width']:.0f} mm` with `D = {recommendation['depth']:.0f} mm` when several checks need relief at once.")
    st_module.caption(f"Web crushing utilisation would become {recommendation['web_util']:.2f}.")
    if render_recommendation_apply_button(
        st_module=st_module,
        button_label="Apply suggested geometry",
        button_key=button_key,
        compact=compact,
        applied=geometry_applied,
    ):
        apply_geometry_recommendation_fn(recommendation=recommendation, source=source)


def render_bottom_recommendation_panel(
    *,
    st_module: Any,
    button_key: str,
    source: str,
    compact: bool,
    shared_state_snapshot_fn: Callable[[], dict[str, Any]],
    resolve_popover_recommendation_fn: Callable[..., dict[str, Any] | None],
    compute_bottom_reo_recommendation_fn: Callable[..., Any],
    updates_match_state_fn: Callable[[dict[str, Any], dict[str, Any]], bool],
    design_optimisation_goal_label_fn: Callable[[dict[str, Any]], str],
    bottom_reo_state_label_fn: Callable[[dict[str, Any]], str],
    evaluate_bending_with_bottom_state_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
    effective_bottom_design_state_fn: Callable[[dict[str, Any]], dict[str, Any]],
    apply_bottom_reo_recommendation_fn: Callable[..., Any],
) -> None:
    current_state = shared_state_snapshot_fn()
    recommendation = resolve_popover_recommendation_fn(
        cache_name="bottom_reo",
        state=current_state,
        button_key=button_key,
        compute_fn=compute_bottom_reo_recommendation_fn,
        empty_message="Generate a bottom reinforcement recommendation on demand for the current beam state.",
    )
    if not recommendation:
        return
    bottom_applied = updates_match_state_fn(current_state, recommendation["arrangement"])
    goal_label = design_optimisation_goal_label_fn(current_state)
    current_label = bottom_reo_state_label_fn(current_state)
    current_bending = evaluate_bending_with_bottom_state_fn(current_state) or {}
    current_util = float(current_bending.get("Mu_util", 0.0) or 0.0)
    current_ast = effective_bottom_design_state_fn(current_state)["Ast_bot"]
    st_module.markdown("**What this controls**")
    st_module.markdown("- Bottom steel carries the main tension force after flexural cracking, so it mostly changes bending behaviour.")
    st_module.markdown(f"- Your current preference is `{goal_label}`, so the steel trial aims for a practical amount rather than just adding reserve.")
    st_module.markdown("**When to change it**")
    st_module.markdown("- More bars usually spread steel better; larger bars add area faster; extra layers add capacity but can reduce effective depth.")
    st_module.markdown(f"- This trial changes bending utilisation from {current_util:.2f} to {recommendation['util']:.2f}.")
    st_module.markdown("**What to avoid**")
    st_module.markdown("- Do not chase steel area alone if congestion or extra layers start making the section less efficient.")
    st_module.caption(
        f"Current: {current_label} ({current_ast:.0f} mm^2). "
        f"If applied: {recommendation['label']} ({recommendation['actual_ast']:.0f} mm^2, required {recommendation['required_ast']:.0f} mm^2)."
    )
    if render_recommendation_apply_button(
        st_module=st_module,
        button_label="Apply suggested bottom reo",
        button_key=button_key,
        compact=compact,
        applied=bottom_applied,
    ):
        apply_bottom_reo_recommendation_fn(recommendation=recommendation, source=source)


def render_shear_recommendation_panel(
    *,
    st_module: Any,
    button_key: str,
    source: str,
    compact: bool,
    shared_state_snapshot_fn: Callable[[], dict[str, Any]],
    guidance_state_snapshot_fn: Callable[[dict[str, Any]], dict[str, Any]],
    build_shear_check_rows_from_state_fn: Callable[[dict[str, Any]], dict[str, Any] | None],
    resolve_popover_recommendation_fn: Callable[..., dict[str, Any] | None],
    compute_shear_recommendation_fn: Callable[..., Any],
    design_optimisation_goal_label_fn: Callable[[dict[str, Any]], str],
    shear_state_label_fn: Callable[[dict[str, Any]], str],
    parse_util_value_fn: Callable[[Any], float | None],
    shear_severity_band_fn: Callable[[float | None], Any],
    updates_match_state_fn: Callable[[dict[str, Any], dict[str, Any]], bool],
    severe_shear_failure_fn: Callable[[float | None], bool],
    apply_shear_recommendation_fn: Callable[..., Any],
) -> None:
    current_state = guidance_state_snapshot_fn(shared_state_snapshot_fn())
    live_pack = build_shear_check_rows_from_state_fn(current_state) or {}
    recommendation = resolve_popover_recommendation_fn(
        cache_name="shear_reo",
        state=current_state,
        button_key=button_key,
        compute_fn=compute_shear_recommendation_fn,
        empty_message="Generate a shear reinforcement recommendation on demand for the current beam state.",
    )
    goal_label = design_optimisation_goal_label_fn(current_state)
    current_shear_label = shear_state_label_fn(current_state)
    current_shear_util = parse_util_value_fn(live_pack.get("summary_util"))
    current_phi_vu = float(live_pack.get("summary_governing_capacity_kN", live_pack.get("summary_phiVu_kN", 0.0)) or 0.0)
    current_veq = float(live_pack.get("summary_governing_demand_kN", live_pack.get("summary_Veq_kN", 0.0)) or 0.0)
    severity_band = shear_severity_band_fn(current_shear_util)
    _ = severity_band
    shear_applied = bool(recommendation and updates_match_state_fn(current_state, recommendation["updates"]))
    if not recommendation:
        st_module.markdown("**Why it matters**")
        st_module.markdown("- Shear is less forgiving than flexure, so links are there to control diagonal cracking and provide brittle-failure reserve.")
        st_module.markdown(f"- The current optimisation goal is `{goal_label}`, so the trial balances safety with link efficiency.")
        st_module.markdown("**Design impact**")
        st_module.markdown("- Tighter spacing usually lifts shear capacity fastest.")
        st_module.markdown("- More legs help when spacing is already practical and another direct spacing cut would be too aggressive.")
        st_module.markdown("- If the current links are already the best practical passing option, no tighter recommendation is shown.")
        st_module.markdown("**Typical move**")
        st_module.markdown("- Compare the live links with the proposed trial before applying, especially when web crushing reserve is also important.")
        st_module.caption(
            f"Current: {current_shear_label} | Ï†Vu = {current_phi_vu:.1f} kN | "
            f"V*eq = {current_veq:.1f} kN | utilisation {current_shear_util:.2f}."
        )
        return
    st_module.markdown("**Why it matters**")
    st_module.markdown("- Shear is less forgiving than flexure, so links are there to control diagonal cracking and provide brittle-failure reserve.")
    st_module.markdown(f"- The current optimisation goal is `{goal_label}`, so the trial balances safety with link efficiency.")
    st_module.markdown("**Design impact**")
    if severe_shear_failure_fn(current_shear_util):
        rec_type = str(recommendation.get("candidate_type") or "")
        if rec_type == "combined":
            st_module.markdown("- Combined geometry and link changes are being considered because the current shear failure is severe.")
        elif rec_type in {"depth increase", "width increase"}:
            st_module.markdown("- Geometry is competing with link changes because the current shear failure is too large for a minor ligature tweak.")
        elif rec_type in {"more legs", "larger dia"}:
            st_module.markdown("- The trial escalates shear reinforcement significantly because spacing-only changes were too weak for this failure level.")
        else:
            st_module.markdown("- Spacing-only remained selected because it removes a large share of the current shear failure despite the severe demand.")
    else:
        st_module.markdown("- Tighter spacing usually lifts shear capacity fastest.")
        st_module.markdown("- More legs help when spacing is already practical and another direct spacing cut would be too aggressive.")
    st_module.markdown(f"- This trial changes utilisation from {current_shear_util:.2f} to {recommendation['util']:.2f}.")
    st_module.markdown("**Typical move**")
    st_module.markdown("- Compare the live links with the proposed trial before applying, especially when web crushing reserve is also important.")
    st_module.caption(
        f"Current: {current_shear_label} | Ï†Vu = {current_phi_vu:.1f} kN | V*eq = {current_veq:.1f} kN. "
        f"If applied: {recommendation['label']} | Ï†Vu = {recommendation['phi_vu']:.1f} kN | "
        f"V*eq = {recommendation['veq']:.1f} kN | web crushing utilisation {recommendation['web_util']:.2f}."
    )
    if render_recommendation_apply_button(
        st_module=st_module,
        button_label="Apply suggested shear reo",
        button_key=button_key,
        compact=compact,
        applied=shear_applied,
    ):
        apply_shear_recommendation_fn(recommendation=recommendation, source=source)
