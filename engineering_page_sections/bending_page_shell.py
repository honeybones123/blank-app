"""Stable structural shell for the Bending result page.

This module owns only page placement.  It deliberately does not read
engineering state, build figures, render calculation content, or mutate
session state.  Keeping the placeholders in one owner prevents later section
extractions from accidentally changing the summary-first DOM order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BendingPageShellContent:
    """Reserved page positions populated by the existing section renderers."""

    diagram_options: Any
    diagram_section: Any
    inputs: Any
    calculations: Any


@dataclass(frozen=True, slots=True)
class BendingPageShell:
    """Own the top-level Bending page container and section order."""

    top: Any

    @classmethod
    def create(cls, st_module) -> "BendingPageShell":
        """Reserve the visible page region before styles or heavy work emit."""

        return cls(top=st_module.container())

    def reserve_content(self, st_module) -> BendingPageShellContent:
        """Reserve the established diagram → inputs → checks page sequence.

        This must be called after the summary is rendered and while ``top`` is
        active.  The returned positions can be populated later without moving
        them in the browser document.
        """

        diagram_frame = st_module.container(key="bending_diagram_frame")
        with diagram_frame:
            diagram_options = st_module.empty()
            diagram_section = st_module.empty()
        inputs = st_module.empty()
        # The calculation body needs a stable multi-element container.  An
        # ``st.empty`` replacement would remount the subtree on tab changes.
        calculations = st_module.container()
        return BendingPageShellContent(
            diagram_options=diagram_options,
            diagram_section=diagram_section,
            inputs=inputs,
            calculations=calculations,
        )


__all__ = ["BendingPageShell", "BendingPageShellContent"]
