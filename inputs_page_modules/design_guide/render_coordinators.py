"""Render-only Inputs Design Guide coordinators.

These helpers receive Streamlit/html/session-key dependencies explicitly so
they own render composition only, not Apply routing or Design Guide authority.
"""

from __future__ import annotations

from typing import Any, Callable


def render_guidance_secondary_items(
    guidance_items: list[dict],
    *,
    guidance_disp_state: dict,
    current_overview: dict | None = None,
    inputs_render_audit: dict[str, str] | None = None,
    start_index: int = 0,
    primary_card_presentation: dict | None = None,
    st_module: Any,
    render_card_model_fn: Callable[..., dict],
    render_primary_cta_state_fn: Callable[..., dict],
    render_button_contract_fn: Callable[..., dict],
    render_apply_action_fn: Callable[..., dict],
) -> None:
    """Render Design Guide secondary cards using page-supplied CTA callbacks."""

    for idx, item in enumerate(guidance_items):
        if idx < start_index:
            continue
        primary_cta_state = render_primary_cta_state_fn(
            idx=idx,
            start_index=start_index,
            primary_card_presentation=primary_card_presentation,
            current_overview=current_overview,
            inputs_render_audit=inputs_render_audit,
        )
        pres_show_apply_raw = bool(primary_cta_state["_pres_show_apply_raw"])
        is_primary_guidance_card = bool(primary_cta_state["is_primary_guidance_card"])
        _ = primary_cta_state["_feedback_status"]
        _ = primary_cta_state["_feedback_reason"]
        _ = primary_cta_state["_solver_result_blocked_reason"]
        suppress_one_click_cta = bool(primary_cta_state["_suppress_one_click_cta"])
        contract_block_override = primary_cta_state["contract_block_override"]
        button_contract_state = render_button_contract_fn(
            item=item,
            guidance_disp_state=guidance_disp_state,
            current_overview=current_overview,
            is_primary_guidance_card=is_primary_guidance_card,
            contract_block_override=contract_block_override,
            _pres_show_apply_raw=pres_show_apply_raw,
        )
        button_contract = dict(button_contract_state["button_contract"] or {})
        _ = dict(button_contract_state["refreshed_truth"] or {})
        pres_show_apply = bool(button_contract_state["_pres_show_apply"])
        card_model = render_card_model_fn(
            idx=idx,
            item=item,
            guidance_disp_state=guidance_disp_state,
            current_overview=current_overview,
            inputs_render_audit=inputs_render_audit,
            start_index=start_index,
            primary_card_presentation=primary_card_presentation,
        )
        card_html = str(card_model["card_html"] or "")
        anchor_class = str(card_model["anchor_class"] or "")
        st_module.markdown(card_html, unsafe_allow_html=True)
        apply_action_result = render_apply_action_fn(
            item=item,
            guidance_disp_state=guidance_disp_state,
            primary_card_presentation=primary_card_presentation,
            button_contract=button_contract,
            anchor_class=anchor_class,
            is_primary_guidance_card=is_primary_guidance_card,
            _pres_show_apply=pres_show_apply,
            _suppress_one_click_cta=suppress_one_click_cta,
        )
        if bool(apply_action_result.get("continue_item")):
            continue


def render_design_guide_component_cta(
    *,
    st_module: Any,
    apply_label: str,
    rec: dict,
    primary_route_target: str,
    button_contract: dict,
    queue_primary_button_action_fn: Callable[..., Any],
) -> bool:
    """Render the primary Design Guide CTA with typed callback injection."""

    session_state = getattr(st_module, "session_state", {})
    render_epoch = int(session_state.get("_design_guide_render_epoch", 0) or 0)
    if session_state.get("_design_guide_cta_rendered_epoch") == render_epoch:
        # A second projection can occur during a fragment/session rerun. The
        # first primary CTA remains authoritative; suppressing this duplicate
        # prevents a second Streamlit widget with the same key.
        return False
    session_state["_design_guide_cta_rendered_epoch"] = render_epoch

    return bool(
        st_module.button(
            apply_label,
            key="apply_design_guide",
            type="secondary",
            width="stretch",
            on_click=queue_primary_button_action_fn,
            args=(
                dict(rec),
                primary_route_target,
                apply_label,
                dict(button_contract),
            ),
        )
    )


def render_design_guide_post_apply_banner(
    *,
    st_module: Any,
    html_escape_fn: Callable[[str], str],
    fast_focus_section: str | None,
    apply_banner_key: str,
) -> None:
    if fast_focus_section != "model":
        return
    payload = st_module.session_state.pop(apply_banner_key, None)
    fallback = "Model updated below. Review the live section before continuing."
    if not isinstance(payload, dict):
        return
    title_raw = str(payload.get("recommendation_title") or "Applied recommendation")
    title_esc = html_escape_fn(title_raw)
    post_commit_truth = dict(payload.get("display_truth") or {})
    st_module.session_state["design_guide_post_apply_display_truth"] = dict(post_commit_truth)
    lines = payload.get("change_lines") or []
    usable = [str(item).strip() for item in lines if str(item).strip()]
    if usable:
        body = "<br>".join(html_escape_fn(item) for item in usable)
        inner = (
            f"<div class='fast-auto-design-summary-title'>Applied recommendation: {title_esc}</div>"
            f"<div class='fast-auto-design-summary-step'>{body}</div>"
        )
        st_module.markdown(
            f"<div class='fast-auto-design-summary fast-next-hint--design-guide-follow'>{inner}</div>",
            unsafe_allow_html=True,
        )
        return
    inner = (
        f"<div class='fast-auto-design-summary-title'>Applied recommendation: {title_esc}</div>"
        f"<div class='fast-auto-design-summary-step'>{html_escape_fn(fallback)}</div>"
    )
    st_module.markdown(
        f"<div class='fast-auto-design-summary fast-next-hint--design-guide-follow'>{inner}</div>",
        unsafe_allow_html=True,
    )
