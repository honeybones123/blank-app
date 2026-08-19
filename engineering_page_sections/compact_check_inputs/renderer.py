"""Streamlit renderer for the shared compact calculation-page input panel."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from .contract import CheckInputPanelConfig
from ..mounted_card_shell import mounted_card_region


def _inject_styles(st_module: Any) -> None:
    """Render scoped CSS without adding any session-state identity."""
    st_module.markdown(
        """
<style>
.compact-check-inputs-heading {
  color: #10234a;
  font-size: 17.6px;
  font-weight: 600;
  line-height: 1.35;
  margin: 0 0 0.75rem;
}

/* Existing lazy-expander presentation. */
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] {
  margin: 0.55rem 0 !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] > details {
  border: 1px solid #D4DAE1 !important;
  border-radius: 8px !important;
  overflow: hidden !important;
  background: #F3F5F7 !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] summary {
  min-height: 58px !important;
  box-sizing: border-box !important;
  padding: 0.65rem 1rem !important;
  background: #F3F5F7 !important;
  border: 0 !important;
  color: #10234A !important;
  font-size: 16px !important;
  line-height: 1.6 !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] {
  padding: 0.9rem 1rem 1rem !important;
  box-sizing: border-box !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] summary p {
  color: #10234a;
  font-size: 16px !important;
  line-height: 1.6 !important;
}

/* Shared white widget surfaces for both lazy expanders and mounted shells. */
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-baseweb="input"],
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-baseweb="base-input"],
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-baseweb="select"] > div,
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-testid="stNumberInput"] > div,
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-testid="stTextInput"] > div,
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] textarea,
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] input,
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-baseweb="input"],
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-baseweb="base-input"],
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-baseweb="select"] > div,
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-testid="stNumberInput"] > div,
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-testid="stTextInput"] > div,
[class*="st-key-compact_check_inputs_"][class*="__body"] textarea,
[class*="st-key-compact_check_inputs_"][class*="__body"] input {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-baseweb="input"] > input,
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-baseweb="base-input"] > input,
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] div[data-baseweb="select"] *,
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-baseweb="input"] > input,
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-baseweb="base-input"] > input,
[class*="st-key-compact_check_inputs_"][class*="__body"] div[data-baseweb="select"] * {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
}

/* Two-column rhythm for both rendering paths. */
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] > div[data-testid="stVerticalBlock"],
[class*="st-key-compact_check_inputs_"][class*="__body"] > div[data-testid="stVerticalBlock"] {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 1rem;
  row-gap: .45rem;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] > div[data-testid="stVerticalBlock"] > :has(.section-title),
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] > div[data-testid="stVerticalBlock"] > [class*="st-key-compact_check_inputs_full_span_"],
[class*="st-key-compact_check_inputs_"][class*="__body"] > div[data-testid="stVerticalBlock"] > :has(.section-title),
[class*="st-key-compact_check_inputs_"][class*="__body"] > div[data-testid="stVerticalBlock"] > [class*="st-key-compact_check_inputs_full_span_"] {
  grid-column: 1 / -1;
}

/* Illustrated icon tiles for the mounted-card headers. */
[class*="st-key-compact_check_inputs_"][class*="__shell"] div[data-testid="stButton"] > button {
  justify-content: flex-start !important;
  align-items: center !important;
  text-align: left !important;
}
[class*="st-key-compact_check_inputs_"][class*="__shell"] div[data-testid="stButton"] > button > div,
[class*="st-key-compact_check_inputs_"][class*="__shell"] div[data-testid="stButton"] > button p {
  justify-content: flex-start !important;
  text-align: left !important;
  width: 100% !important;
}
[class*="st-key-compact_check_inputs_"][class*="__shell"] div[data-testid="stButton"] > button::before {
  display: none;
}
[class*="st-key-compact_check_inputs_"][class*="_design_actions"][class*="__shell"] div[data-testid="stButton"] > button::before {
  background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMTAyMzRhIiBzdHJva2Utd2lkdGg9IjEuOCIgc3Ryb2tlLWxpbmVjY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTE2IDV2MjFNNSA4aDIyTTQgOWw0IDlIMmwyLTlabTI0IDAgNCA5aC02bDItOVpNNyA4bC0zIDFtMjEtMSAzIDFNMTAgMjdIMTIiLz48L3N2Zz4=");
}
[class*="st-key-compact_check_inputs_"][class*="_section_material"][class*="__shell"] div[data-testid="stButton"] > button::before {
  background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMTAyMzRhIiBzdHJva2Utd2lkdGg9IjEuOCI+PHJlY3QgeD0iNSIgeT0iNSIgd2lkdGg9IjIyIiBoZWlnaHQ9IjIyIiByeD0iMSIvPjxyZWN0IHg9IjkiIHk9IjkiIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIvPjxjaXJjbGUgY3g9IjExIiBjeT0iMTEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjxjaXJjbGUgY3g9IjIxIiBjeT0iMTEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjxjaXJjbGUgY3g9IjExIiBjeT0iMjEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjxjaXJjbGUgY3g9IjIxIiBjeT0iMjEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjwvc3ZnPg==");
}
[class*="st-key-compact_check_inputs_"][class*="_reinforcement"][class*="__shell"] div[data-testid="stButton"] > button::before {
  background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMTAyMzRhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjY2FwPSJyb3VuZCI+PHBhdGggZD0iTTggNXYyMk0xNiA1djIyTTI0IDV2MjJNNyA4aDIyTTUgMTZoMjJNNSAyNGgyMiIvPjwvc3ZnPg==");
}
:is(
  [class*="st-key-compact_check_inputs_"][class*="_design_actions"][class*="__shell"],
  [class*="st-key-compact_check_inputs_"][class*="_section_material"][class*="__shell"],
  [class*="st-key-compact_check_inputs_"][class*="_reinforcement"][class*="__shell"]
) div[data-testid="stButton"] > button::before {
  display: block;
  content: "";
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  margin-right: 12px;
  border-radius: 8px;
  background-color: #E3E8ED;
  background-position: center;
  background-repeat: no-repeat;
  background-size: 27px 27px;
}

@media (max-width: 700px) {
  .compact-check-inputs-heading { font-size: 17.6px; }
  [class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] summary { min-height: 3rem; }
  [class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"] > div[data-testid="stVerticalBlock"],
  [class*="st-key-compact_check_inputs_"][class*="__body"] > div[data-testid="stVerticalBlock"] {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_compact_section_heading(st_module: Any, text: str) -> None:
    """Render the canonical heading used immediately after a page divider."""
    import html

    st_module.markdown(
        f'<div class="compact-check-inputs-heading">{html.escape(str(text))}</div>',
        unsafe_allow_html=True,
    )


@contextmanager
def compact_check_input_regions(st_module: Any, config: CheckInputPanelConfig):
    """Yield stable category regions for existing inline widget renderers.

    Mounted/light panels use a one-step visual shell whose body remains mounted
    so widget identity and values persist. Heavy/lazy panels retain Streamlit's
    expander path so closed bodies are not constructed on cold render.
    """

    _inject_styles(st_module)
    st_module.markdown(
        '<div class="compact-check-inputs-anchor"></div>',
        unsafe_allow_html=True,
    )
    render_compact_section_heading(st_module, "Inputs used for this check")

    with st_module.container(
        border=False,
        key=f"compact_check_inputs_{config.page_slug}",
    ):
        regions = []
        for category in config.categories:
            warning = f"  ⚠ {category.warning}" if category.warning else ""
            icon = "" if category.category_id in {
                "design_actions", "section_material", "reinforcement"
            } else (f"{category.icon}  " if category.icon else "")
            label = f"{icon}{category.label}    {category.summary}{warning}".strip()
            card_key = (
                f"compact_check_inputs_{config.page_slug}_"
                f"{category.category_id}"
            )

            if config.mount_closed_bodies:
                regions.append(
                    mounted_card_region(
                        st_module,
                        label=label,
                        key=card_key,
                        initially_open=False,
                    )
                )
                continue

            regions.append(
                st_module.expander(
                    label,
                    expanded=False,
                    key=card_key,
                    type="compact",
                    on_change="rerun",
                )
            )

        yield tuple(regions)


def render_compact_check_inputs(st_module: Any, config: CheckInputPanelConfig) -> None:
    """Render one compact panel without owning engineering state."""

    with compact_check_input_regions(st_module, config) as regions:
        for region, category in zip(regions, config.categories):
            if region.open:
                with region:
                    category.render_body()


def compact_check_input_columns(st_module: Any, config: CheckInputPanelConfig):
    """Return stable regions for legacy pages that already render by column."""

    with compact_check_input_regions(st_module, config) as regions:
        return regions


__all__ = [
    "compact_check_input_columns",
    "compact_check_input_regions",
    "render_compact_check_inputs",
]
