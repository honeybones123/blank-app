"""Shared typed diagram input models.

Diagram modules own figure construction only. Page files own widget layout,
session state, and rendering. Engineering calculations remain outside diagram
modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SectionDiagramResult:
    """Result for section diagram builders that may need page-owned messaging."""

    figure: Any | None
    error_message: str | None = None
