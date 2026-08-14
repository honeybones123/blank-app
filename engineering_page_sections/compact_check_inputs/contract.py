"""Presentation-only contracts for calculation-page input summaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class InputSource(str, Enum):
    BEAM_INPUTS = "Beam Inputs"
    LOAD_ANALYSIS = "Load Analysis"
    PROJECT_INPUTS = "Project Inputs"
    CALCULATED = "Calculated"


RenderBody = Callable[[], None]


@dataclass(frozen=True)
class CheckInputCategory:
    """One category rendered by the shared panel.

    ``render_body`` must call the existing widget renderer with its existing
    key and callback.  The shared component owns no engineering mutation.
    """

    category_id: str
    label: str
    summary: str
    render_body: RenderBody
    source: InputSource = InputSource.BEAM_INPUTS
    warning: str | None = None
    icon: str = ""


@dataclass(frozen=True)
class CheckInputPanelConfig:
    page_slug: str
    categories: tuple[CheckInputCategory, ...]

    def __post_init__(self) -> None:
        if not self.page_slug.strip():
            raise ValueError("page_slug is required")
        ids = [category.category_id for category in self.categories]
        if len(ids) != len(set(ids)):
            raise ValueError("category_id values must be unique per page")
