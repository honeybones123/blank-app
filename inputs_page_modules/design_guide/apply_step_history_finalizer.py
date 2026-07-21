"""Apply step-history finalization coordination for the Inputs Design Guide."""

from __future__ import annotations

from datetime import datetime
from typing import Any


_APPLY_STEP_HISTORY_FINALIZER_DEPENDENCIES: tuple[str, ...] = (
    "_build_design_actions_context",
    "_collect_design_overview",
    "_compute_bottom_reo_recommendation",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_guidance_apply_change_lines",
    "_guidance_default_banner_title",
    "_shared_state_snapshot",
    "_signature_dict_for_step_history",
    "_worst_util_in_efficiency_target_band",
    "build_inputs_design_guide_apply_step_history_entry_plan",
    "DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY",
    "DESIGN_GUIDE_PENDING_STEP_CTX_KEY",
    "DESIGN_GUIDE_STEP_HISTORY_KEY",
    "EFFICIENCY_TARGET_UTIL_MAX",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "st",
)


def bind_apply_step_history_finalizer_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _APPLY_STEP_HISTORY_FINALIZER_DEPENDENCIES
            if name in namespace
        }
    )


def _finalize_design_guide_apply_step_history(
    *,
    prior_state: dict,
    source: str,
    applied_candidate: dict | None,
) -> None:
    if not str(source).startswith("guidance:"):
        return
    ctx = st.session_state.pop(DESIGN_GUIDE_PENDING_STEP_CTX_KEY, None)
    if not isinstance(ctx, dict):
        return
    post_state = _shared_state_snapshot()
    design_context_post = _build_design_actions_context(post_state)
    post_overview = _collect_design_overview(post_state, context=design_context_post)
    pre_overview = ctx.get("pre_overview") or {}
    action_type = str(ctx.get("action_type") or "")
    payload = dict(ctx.get("payload") or {})
    mode_cfg = _design_mode_config(_design_optimisation_goal(post_state))
    tmin = float(mode_cfg.get("target_util_min", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN)
    tmax = float(mode_cfg.get("target_util_max", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX)
    try:
        pre_wu = float((pre_overview or {}).get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        pre_wu = 0.0
    try:
        post_wu = float((post_overview or {}).get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        post_wu = 0.0
    pre_band = _worst_util_in_efficiency_target_band(pre_overview)
    post_band = _worst_util_in_efficiency_target_band(post_overview)
    entered = bool(not pre_band and post_band)
    first_step = st.session_state.get(DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY)
    step_list = st.session_state.setdefault(DESIGN_GUIDE_STEP_HISTORY_KEY, [])
    step_index = len(step_list) + 1
    if entered and first_step is None:
        st.session_state[DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY] = step_index
        first_after = step_index
    else:
        first_after = int(first_step) if first_step is not None else None
    title = str(ctx.get("recommendation_title") or "").strip()
    if not title:
        title = str(payload.get("guidance_banner_title") or payload.get("label") or _guidance_default_banner_title(action_type))
    rec_ft = None
    rec_sf: list | None = None
    if action_type == "apply_resolved_candidate" and isinstance(applied_candidate, dict):
        rec_ft = applied_candidate.get("recommendation_family_tag")
        rec_sf = (
            list(applied_candidate.get("subfamilies") or [])
            if isinstance(applied_candidate.get("subfamilies"), list)
            else None
        )
    elif action_type == "apply_bottom_recommendation":
        try:
            br = _compute_bottom_reo_recommendation(prior_state)
            if isinstance(br, dict):
                rec_ft = br.get("recommendation_family_tag")
                rec_sf = list(br.get("subfamilies") or []) if isinstance(br.get("subfamilies"), list) else None
        except Exception:
            rec_ft, rec_sf = None, None
    change_lines: list[str] = []
    try:
        change_lines = list(_guidance_apply_change_lines(prior_state, post_state) or [])
    except Exception:
        change_lines = []
    entry = {
        "step_index": step_index,
        "applied_at": datetime.now().isoformat(timespec="seconds"),
        "guidance_branch_before": ctx.get("guidance_branch_before"),
        "recommendation_title": str(title),
        "recommendation_family_tag": rec_ft,
        "recommendation_subfamilies": rec_sf,
        "pre_apply_worst_util": pre_wu,
        "post_apply_worst_util": post_wu,
        "pre_apply_statuses": dict((pre_overview or {}).get("statuses") or {}),
        "post_apply_statuses": dict((post_overview or {}).get("statuses") or {}),
        "pre_apply_signature": _signature_dict_for_step_history(prior_state),
        "post_apply_signature": _signature_dict_for_step_history(post_state),
        "pre_apply_target_band": [tmin, tmax],
        "entered_target_band_on_this_step": entered,
        "first_target_band_step_after_apply": first_after,
        "applied_change_lines": change_lines,
        "action_type": action_type,
        "recommendation_label_at_step_start": ctx.get("recommendation_label_at_step_start"),
        "recommendation_action_type_at_step_start": ctx.get("recommendation_action_type_at_step_start"),
        "used_resolved_payload": bool(ctx.get("used_resolved_payload")),
        "one_click_candidate_available_at_step_start": bool(ctx.get("one_click_candidate_available_at_step_start")),
        "one_click_candidate_label_at_step_start": ctx.get("one_click_candidate_label_at_step_start"),
    }
    entry_plan = build_inputs_design_guide_apply_step_history_entry_plan(
        context=ctx,
        pre_overview=pre_overview,
        post_overview=post_overview,
        pre_in_target_band=pre_band,
        post_in_target_band=post_band,
        existing_step_count=len(step_list),
        first_target_band_step=first_step,
        applied_at=entry["applied_at"],
        recommendation_title=str(title),
        recommendation_family_tag=rec_ft,
        recommendation_subfamilies=rec_sf,
        pre_apply_signature=_signature_dict_for_step_history(prior_state),
        post_apply_signature=_signature_dict_for_step_history(post_state),
        target_util_min=tmin,
        target_util_max=tmax,
        applied_change_lines=change_lines,
        action_type=action_type,
    )
    if entry_plan.set_first_target_band_step:
        st.session_state[DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY] = entry_plan.first_target_band_step_after_apply
    entry = dict(entry_plan.entry)
    step_list.append(entry)
