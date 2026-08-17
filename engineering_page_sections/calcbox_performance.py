"""Hybrid calculation-card rendering for heavy engineering pages.

Light calculation cards are cheap text/equation surfaces.  Keeping their body
mounted makes expansion browser-only.  Diagram-bearing cards remain lazy nested
fragments so page navigation does not pay Plotly/Matplotlib construction cost
for content the user may never open.

This module owns presentation performance only.  It never reads or mutates the
engineering snapshot, revision, publication, or Design Brain state.
"""

from __future__ import annotations

import re
from typing import Any, Callable

import streamlit as st

import widgets_helpers as _widgets


StepRenderer = Callable[..., Any]


def _bold_first_summary_line(line: str) -> str:
    text = str(line or "").strip()
    if not text:
        return text
    if text.startswith("**") and text.endswith("**"):
        return text
    return f"**{text}**"


def _normalise_summary(summary_line: str) -> str:
    summary = str(summary_line or "")
    if not re.match(
        r"^\s*Check\s+\d+(?:\.\d+)?\s+—",
        summary,
        flags=re.IGNORECASE,
    ):
        match = re.match(r"^\s*(\d+(?:\.\d+)?)\s+(.+)$", summary)
        if match:
            summary = f"Check {match.group(1)} — {match.group(2).strip()}"
    if " | " in summary:
        first, rest = summary.split(" | ", 1)
        return f"{_bold_first_summary_line(first)}  \n{rest}"
    return _bold_first_summary_line(summary)


@st.fragment
def _render_eager_light_calcbox(
    *,
    uid: str,
    summary_line: str,
    details_md: str,
    status: Any = None,
    content_before: Callable[[], None] | None = None,
    content_after: Callable[[], None] | None = None,
    expanded: bool | None = None,
    jump_uid: str | None = None,
    accent: str | None = None,
) -> None:
    """Pre-mount a non-diagram calculation card for browser-only expansion."""

    _ = jump_uid  # presentation identity is already carried by uid/open_key.
    _widgets.apply_step_summary_expander_css()
    st.markdown(
        f"<div id='calc_{uid}' data-calc-uid='{uid}'></div>",
        unsafe_allow_html=True,
    )

    is_expanded = (
        bool(expanded)
        if expanded is not None
        else bool(st.session_state.get(f"step_open_{uid}", False))
    )
    status_class = _widgets.status_to_class(status)
    accent_key = _widgets._normalize_calc_accent(accent)
    accent_html = (
        f"<span class='step-accent-{accent_key}'></span>" if accent_key else ""
    )

    formatted_summary = _normalise_summary(summary_line)
    info_tip = " ℹ️" if content_before else ""
    label = f"{formatted_summary}{info_tip}".strip()
    has_body_content = bool(
        _widgets._has_non_empty_card_text(details_md)
        or content_before
        or content_after
    )
    if not _widgets._has_non_empty_card_text(label):
        if not has_body_content:
            return
        label = "**Calculation details**"

    open_key = f"step_open_{uid}"
    if open_key not in st.session_state:
        st.session_state[open_key] = is_expanded

    expander = st.expander(
        label,
        expanded=is_expanded,
        key=open_key,
        # Body is already mounted. Expansion is therefore browser presentation
        # only and must not trigger a Python/engineering rerun.
        on_change="ignore",
    )
    with expander:
        st.markdown(
            f"<div id='inner_{uid}'><span class='{status_class}'></span>{accent_html}</div>",
            unsafe_allow_html=True,
        )
        if content_before:
            content_before()
        _widgets.calcbox(
            details_md,
            status=status,
            uid=f"{uid}__details",
            accent=accent_key,
        )
        if content_after:
            content_after()


def build_hybrid_step_renderer(lazy_renderer: StepRenderer) -> StepRenderer:
    """Return one renderer that eagerly mounts light cards and lazies diagrams."""

    def _hybrid(
        uid: str,
        summary_line: str,
        details_md: str,
        status: Any = None,
        diagram_fn: Callable[[], None] | None = None,
        content_before: Callable[[], None] | None = None,
        content_after: Callable[[], None] | None = None,
        expanded: bool | None = None,
        jump_uid: str | None = None,
        accent: str | None = None,
    ) -> Any:
        if diagram_fn is not None:
            return lazy_renderer(
                uid=uid,
                summary_line=summary_line,
                details_md=details_md,
                status=status,
                diagram_fn=diagram_fn,
                content_before=content_before,
                content_after=content_after,
                expanded=expanded,
                jump_uid=jump_uid,
                accent=accent,
            )
        return _render_eager_light_calcbox(
            uid=uid,
            summary_line=summary_line,
            details_md=details_md,
            status=status,
            content_before=content_before,
            content_after=content_after,
            expanded=expanded,
            jump_uid=jump_uid,
            accent=accent,
        )

    _hybrid.__name__ = "hybrid_step_expander_calcbox"
    return _hybrid


def install_bending_hybrid_calcbox_runtime(bending_tabs_module: Any) -> None:
    """Install the policy on Bending's existing module-global step renderer.

    Bending imports the shared renderer into its module namespace.  Rebinding
    that one presentation dependency avoids changing the engineering runtime or
    duplicating calculation-page logic.  Installation is idempotent.
    """

    if bool(getattr(bending_tabs_module, "_HYBRID_CALCBOX_POLICY_INSTALLED", False)):
        return
    current = getattr(bending_tabs_module, "step_expander_calcbox", None)
    if not callable(current):
        raise AttributeError("bending_tabs.step_expander_calcbox is required")
    bending_tabs_module.step_expander_calcbox = build_hybrid_step_renderer(current)
    bending_tabs_module._HYBRID_CALCBOX_POLICY_INSTALLED = True


__all__ = [
    "build_hybrid_step_renderer",
    "install_bending_hybrid_calcbox_runtime",
]
