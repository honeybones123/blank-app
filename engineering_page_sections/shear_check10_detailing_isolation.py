"""Presentation-only isolation for Shear Check 10 detailing advice.

Check 10 is intentionally not an engineering-result authority.  It may read the
already-resolved shear zoning/layout publication and use that to teach/show a
more economical link arrangement in the Shear side-view diagram, but it must
not mutate shared link spacing, alter the canonical shear result, publish a
summary row, or feed Design Brain.
"""

from __future__ import annotations

from typing import Any


def install_shear_check10_detailing_isolation() -> None:
    """Keep Check 10 local to its card and the Shear side-view diagram only."""

    from engineering_page_sections import shear_reinforcement_checks as check10_module
    from ui.diagrams import side_view_diagram

    if getattr(check10_module, "_check10_detailing_isolation_installed", False):
        return

    # ------------------------------------------------------------------
    # 1. Side-view projection
    # ------------------------------------------------------------------
    # Use the already-calculated zoning publication for the diagram whether or
    # not Design Brain / auto-design is enabled.  This is display-only: s_lig is
    # never overwritten and no capacity/result publication is changed.
    original_spacing_pair = side_view_diagram.shear_spacing_used_mm_pair

    def detailing_spacing_pair(
        shear_zone_results: dict[str, Any] | None,
    ) -> tuple[float, float]:
        sz = shear_zone_results if isinstance(shear_zone_results, dict) else {}
        s_in = max(side_view_diagram._safe_float(side_view_diagram.get_param("s_lig", 0.0), 0.0), 0.0)

        s_mid = side_view_diagram._safe_float(
            sz.get("shear_mid_spacing_calc_mm")
            or sz.get("shear_spacing_mid_mm")
            or 0.0,
            0.0,
        )
        s_end = side_view_diagram._safe_float(
            sz.get("shear_spacing_end_mm") or 0.0,
            0.0,
        )

        # Never make the support/end-zone diagram looser than the user's
        # provided link spacing.  Midspan may be shown looser only where the
        # existing Check 10 zoning calculation explicitly allows it.
        end_used = s_in
        if s_end > 0.0 and s_in <= 0.0:
            end_used = s_end

        mid_used = s_in
        if s_mid > 0.0:
            mid_used = s_mid

        return (
            mid_used if mid_used > 0.0 else s_in,
            end_used if end_used > 0.0 else s_in,
        )

    side_view_diagram.shear_spacing_used_mm_pair = detailing_spacing_pair

    # ------------------------------------------------------------------
    # 2. Check 10 card isolation
    # ------------------------------------------------------------------
    # The existing Check 10 renderer already performs no writes.  Wrap only its
    # presentation boundary so its local PASS/FAIL cannot masquerade as a main
    # page/global result, and so it shows the calculated zoning even when
    # shear_auto_design is off.
    original_render_check10 = check10_module.render_shear_reinforcement_checks
    original_get_param = check10_module.get_param
    original_render_step = check10_module.render_expandable_step

    def local_get_param(key: str, default: Any = None):
        if key == "shear_auto_design":
            # Presentation-only: causes the Check 10 card to display its own
            # calculated end/mid zoning rather than the globally provided
            # uniform spacing.  Session state remains untouched.
            return True
        return original_get_param(key, default)

    def local_render_step(*args: Any, **kwargs: Any):
        if str(kwargs.get("step_id", "")) == "shear_check10":
            revised = dict(kwargs)
            revised["status_kind"] = None
            summary = str(revised.get("summary_md", "") or "")
            if summary and "Advisory" not in summary:
                summary = summary.replace(
                    "Check 10 — Shear reinforcement (spacing + minimum check) |",
                    "Check 10 — Shear detailing advisory |",
                )
            revised["summary_md"] = summary
            return original_render_step(*args, **revised)
        return original_render_step(*args, **kwargs)

    def isolated_render(view: Any) -> None:
        previous_get_param = check10_module.get_param
        previous_render_step = check10_module.render_expandable_step
        try:
            check10_module.get_param = local_get_param
            check10_module.render_expandable_step = local_render_step
            original_render_check10(view)
        finally:
            check10_module.get_param = previous_get_param
            check10_module.render_expandable_step = previous_render_step

    check10_module.render_shear_reinforcement_checks = isolated_render
    check10_module._check10_detailing_isolation_installed = True
    check10_module._check10_original_spacing_pair = original_spacing_pair


__all__ = ["install_shear_check10_detailing_isolation"]
