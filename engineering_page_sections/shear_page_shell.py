"""Stable structural shell for the Shear result page.

The current Shear DOM order is unusual but intentional: the visualisation
position is reserved immediately after the summary, the input rail renders
next, and the diagram is populated only after the calculation bundle is
available.  This module owns that placement boundary without reading
engineering state or changing the established browser structure.

Additional page sections can move behind this shell as they are extracted.
Until then, reserving only the visualisation position is safer than inserting
new placeholder wrappers around the existing inputs and checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from engineering_page_sections.shear_mcft_check4_padding import (
    install_mcft_check4_vertical_padding,
)
from engineering_page_sections.shear_ui_layout_refinements import (
    install_shear_ui_layout_refinements,
)


# Install presentation-only wrappers before shear_page_runtime imports the
# individual check renderers. Engineering calculation ownership is unchanged.
install_shear_ui_layout_refinements()
install_mcft_check4_vertical_padding()


_RenderResult = TypeVar("_RenderResult")


@dataclass(frozen=True, slots=True)
class ShearPageShell:
    """Own the deferred visualisation position in the Shear page sequence."""

    visualisation: Any

    @classmethod
    def reserve_after_summary(
        cls,
        st_module,
        *,
        before_first_divider: Callable[[], Any] | None = None,
        render_first_divider: Callable[[], Any],
    ) -> "ShearPageShell":
        """Reserve the existing diagram position, then emit the input divider.

        The call order deliberately mirrors the pre-extraction runtime:
        ``st.empty()`` first and the page divider second.  The input rail can
        therefore render in its current DOM position while the heavy diagram
        work remains deferred.
        """

        visualisation = st_module.empty()
        if before_first_divider is not None:
            before_first_divider()
        render_first_divider()
        return cls(visualisation=visualisation)

    def render_visualisation(
        self,
        renderer: Callable[[], _RenderResult],
    ) -> _RenderResult:
        """Populate the reserved visualisation position in place."""

        with self.visualisation.container():
            return renderer()


__all__ = ["ShearPageShell"]
