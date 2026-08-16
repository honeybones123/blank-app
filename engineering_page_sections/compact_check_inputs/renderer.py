"""Streamlit renderer for the shared compact calculation-page input panel."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from .contract import CheckInputPanelConfig


class _MountedExpander:
    """Expose an already-mounted body while delegating visual expansion.

    Calculation-page input cards are small, stable widget groups. Mounting
    their bodies in the owning page fragment lets browser-side expansion stay
    instantaneous and prevents one card click from rerunning every summary,
    diagram and calculation card on the page.
    """

    open = True

    def __init__(self, expander: Any) -> None:
        self._expander = expander

    def __enter__(self):
        return self._expander.__enter__()

    def __exit__(self, *args):
        return self._expander.__exit__(*args)

    def __getattr__(self, name: str):
        return getattr(self._expander, name)


def _inject_styles(st_module: Any) -> None:
    """Render scoped CSS without adding any session-state identity."""
    st_module.markdown(
        """
<style>
.compact-check-inputs-heading {
  color: #10234a;
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.25;
  margin: 0;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] {
  margin: 0.55rem 0 !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] > details {
  border: 1px solid #D4DAE1 !important;
  border-radius: 8px !important;
  overflow: hidden !important;
  background: #E9EDF1 !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] summary {
  min-height: 58px !important;
  box-sizing: border-box !important;
  padding: 0.45rem 0.65rem !important;
  background: #E9EDF1 !important;
  border: 0 !important;
  color: #10234A !important;
  font-size: 16px !important;
  line-height: 1.6 !important;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] summary p {
  color: #10234a;
  font-size: 16px !important;
  line-height: 1.6 !important;
}
/* Every shared input card uses the same two-column widget rhythm.  Existing
   widget rows remain intact; this only arranges those rows into pairs. */
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"]
  > div[data-testid="stVerticalBlock"] {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 1rem;
  row-gap: .45rem;
}
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"]
  > div[data-testid="stVerticalBlock"] > :has(.section-title),
[class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"]
  > div[data-testid="stVerticalBlock"] > [class*="st-key-compact_check_inputs_full_span_"] {
  grid-column: 1 / -1;
}
@media (max-width: 700px) {
  .compact-check-inputs-heading { font-size: 1.15rem; }
  [class*="st-key-compact_check_inputs_"] div[data-testid="stExpander"] summary { min-height: 3rem; }
  [class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"]
    > div[data-testid="stVerticalBlock"] { grid-template-columns: minmax(0, 1fr); }
}
</style>
""",
        unsafe_allow_html=True,
    )


@contextmanager
def compact_check_input_regions(st_module: Any, config: CheckInputPanelConfig):
    """Yield stable category regions for existing inline widget renderers.

    This adapter lets a page move its current widgets without rewriting their
    implementation. Stateful expanders let callers avoid executing a visually
    closed body while keeping the exact existing expander presentation.
    """

    _inject_styles(st_module)
    st_module.markdown(
        '<div class="compact-check-inputs-anchor"></div>',
        unsafe_allow_html=True,
    )
    st_module.markdown(
        '<div class="compact-check-inputs-heading">Inputs used for this check</div>',
        unsafe_allow_html=True,
    )

    with st_module.container(
        border=False,
        key=f"compact_check_inputs_{config.page_slug}",
    ):
        regions = []
        for category in config.categories:
            warning = f"  ⚠ {category.warning}" if category.warning else ""
            icon = f"{category.icon}  " if category.icon else ""
            label = f"{icon}{category.label}    {category.summary}{warning}".strip()
            expander = st_module.expander(
                    label,
                    expanded=False,
                    key=(
                        f"compact_check_inputs_{config.page_slug}_"
                        f"{category.category_id}"
                    ),
                    type="compact",
                    on_change=(
                        "ignore" if config.mount_closed_bodies else "rerun"
                    ),
                )
            regions.append(
                _MountedExpander(expander)
                if config.mount_closed_bodies
                else expander
            )
        yield tuple(regions)


def render_compact_check_inputs(st_module: Any, config: CheckInputPanelConfig) -> None:
    """Render one compact panel without owning engineering state.

    Closed bodies are not executed. Widgets rendered by the shared wrappers use
    Streamlit's session persistence, so closing a category cannot clean up or
    roll back its established value.
    """

    with compact_check_input_regions(st_module, config) as regions:
        for region, category in zip(regions, config.categories):
            if region.open:
                with region:
                    category.render_body()


def compact_check_input_columns(st_module: Any, config: CheckInputPanelConfig):
    """Return stable regions for legacy pages that already render by column.

    This is a migration adapter only. It creates the shared shell, then returns
    its child containers so the page can keep its existing widget statements,
    keys, callbacks, help text and validation unchanged.
    """

    with compact_check_input_regions(st_module, config) as regions:
        return regions


__all__ = [
    "compact_check_input_columns",
    "compact_check_input_regions",
    "render_compact_check_inputs",
]
