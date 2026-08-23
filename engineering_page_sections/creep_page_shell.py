"""Stable structural slots for the Creep result page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar


_RenderResult = TypeVar("_RenderResult")


@dataclass(frozen=True, slots=True)
class CreepPageSlot:
    """One reserved Streamlit position populated later in the same render."""

    placeholder: Any

    def render(self, renderer: Callable[[], _RenderResult]) -> _RenderResult:
        with self.placeholder.container():
            return renderer()


class CreepPageShell:
    """Own the two established deferred positions without changing DOM order."""

    @staticmethod
    def reserve_title(st_module) -> CreepPageSlot:
        return CreepPageSlot(st_module.empty())

    @staticmethod
    def reserve_visualisation(st_module) -> CreepPageSlot:
        return CreepPageSlot(st_module.empty())


__all__ = ["CreepPageShell", "CreepPageSlot"]
