"""Stable structural slots for the Shrinkage result page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar


_RenderResult = TypeVar("_RenderResult")


@dataclass(frozen=True, slots=True)
class ShrinkagePageSlot:
    placeholder: Any

    def render(self, renderer: Callable[[], _RenderResult]) -> _RenderResult:
        with self.placeholder.container():
            return renderer()


class ShrinkagePageShell:
    @staticmethod
    def reserve_title(st_module) -> ShrinkagePageSlot:
        return ShrinkagePageSlot(st_module.empty())

    @staticmethod
    def reserve_visualisation(st_module) -> ShrinkagePageSlot:
        return ShrinkagePageSlot(st_module.empty())


__all__ = ["ShrinkagePageShell", "ShrinkagePageSlot"]
