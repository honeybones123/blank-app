"""Single layout owner for the Bending calculation-check section."""

from __future__ import annotations

from collections.abc import Callable

from engineering_page_sections.bending_checks_context import BendingChecksSnapshot
from engineering_page_sections.bending_minimum_strength_checks_view import (
    render_bending_minimum_strength_checks,
)
from engineering_page_sections.bending_sls_checks_view_with_icr import (
    render_bending_sls_checks,
)
from engineering_page_sections.bending_uls_checks_view_with_yi import (
    render_bending_uls_checks,
)
from engineering_page_sections.stable_tabs import render_stable_tabs
from state_and_helpers import render_timing_mark
from widgets_helpers import (
    apply_step_summary_expander_css,
    page_divider,
    reset_bending_calc_card_parent_render_state,
)


def render_bending_checks(
    *,
    st_module,
    checks: BendingChecksSnapshot,
    render_uls: Callable = render_bending_uls_checks,
    render_sls: Callable = render_bending_sls_checks,
    render_minimum_strength: Callable = render_bending_minimum_strength_checks,
) -> None:
    """Render the established heading and three native check tabs."""

    render_timing_mark("bending_page.runtime.checks.start")
    # Parent renders (cold navigation, beam/revision changes, and other page
    # reruns) must start with header-only calculation cards.  Individual card
    # fragment reruns do not execute this reset, allowing only cards opened on
    # the settled page to stay mounted for instant subsequent toggles.
    requested_open_uid = (
        st_module.session_state.get("bending_pending_scroll_uid")
        or st_module.session_state.get("jump_to")
    )
    reset_bending_calc_card_parent_render_state(
        st_module.session_state,
        preserve_open_uid=str(requested_open_uid) if requested_open_uid else None,
    )
    apply_step_summary_expander_css()
    page_divider()
    st_module.markdown(
        """
        <div class="bending-checks-heading-block" style="padding-top:28px;margin:0 0 0.75rem;">
          <div style="color:#10234a;font-size:17.6px;font-weight:600;line-height:1.35;margin:0;">
            Bending design checks
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uls_tab, sls_tab, minimum_tab = render_stable_tabs(
        st_module,
        labels=("ULS Checks", "SLS Checks", "Minimum strength checks"),
        scope_id="bending-calculation-checks",
    )
    with uls_tab:
        render_uls(checks.uls)
    with sls_tab:
        render_sls(checks.sls)
    with minimum_tab:
        render_minimum_strength(checks.minimum_strength)

    pending_scroll_uid = st_module.session_state.get("bending_pending_scroll_uid")
    if pending_scroll_uid:
        from jump_nav import scroll_to_jump_after_render

        st_module.session_state["jump_to"] = pending_scroll_uid
        scroll_to_jump_after_render()
        del st_module.session_state["bending_pending_scroll_uid"]

    st_module.markdown(
        '<span data-testid="bending-calculation-ready" '
        'aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    render_timing_mark("bending_page.runtime.checks.end")


__all__ = ["render_bending_checks"]
