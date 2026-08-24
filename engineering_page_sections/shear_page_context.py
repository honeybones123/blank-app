"""Typed, read-only contracts for the Shear page presentation.

The authoritative calculations remain owned by the existing shear publication
pipeline.  These contracts only detach values that have already been resolved
for the current beam revision so extracted page sections do not need to read
unrelated ``st.session_state`` keys or rerun engineering calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _readonly_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Detach mapping identity and expose a read-only top-level view."""

    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class ShearViewState:
    """Presentation-only selections owned by the Shear page."""

    actions_mode: str

    @property
    def is_design_driven(self) -> bool:
        return self.actions_mode == "design"


@dataclass(frozen=True, slots=True)
class ShearPageSnapshot:
    """Single revision-matched input supplied to Shear page sections."""

    engineering_state: Mapping[str, Any]
    check_pack: Mapping[str, Any]
    published_results: Mapping[str, Any]
    section_layout: Any
    view: ShearViewState

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "engineering_state", _readonly_mapping(self.engineering_state)
        )
        object.__setattr__(self, "check_pack", _readonly_mapping(self.check_pack))
        object.__setattr__(
            self, "published_results", _readonly_mapping(self.published_results)
        )


def build_shear_page_snapshot(
    *,
    engineering_state: Mapping[str, Any],
    check_pack: Mapping[str, Any],
    published_results: Mapping[str, Any] | None,
    section_layout: Any,
    actions_mode: str | None,
) -> ShearPageSnapshot:
    """Build a presentation snapshot without recalculating any result."""

    resolved_actions_mode = str(actions_mode or "manual")
    if resolved_actions_mode not in {"manual", "design"}:
        resolved_actions_mode = "manual"

    return ShearPageSnapshot(
        engineering_state=engineering_state,
        check_pack=check_pack,
        published_results=published_results or {},
        section_layout=section_layout,
        view=ShearViewState(
            actions_mode=resolved_actions_mode,
        ),
    )


__all__ = [
    "ShearPageSnapshot",
    "ShearViewState",
    "build_shear_page_snapshot",
]
