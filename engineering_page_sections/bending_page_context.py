"""Typed, read-only contracts for the Bending page presentation.

The authoritative calculations remain owned by the existing engineering
publication pipeline.  These contracts only take a revision-matched snapshot
of values that have already been calculated so page sections can be extracted
without reading unrelated ``st.session_state`` keys or rerunning engineering.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence


BENDING_DIAGRAM_STATES = ("ULS", "SLS (cracked)", "Uncracked")
BENDING_DETAIL_VIEWS = ("positive", "negative")


def _readonly_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Detach the mapping identity and expose a read-only top-level view."""

    return MappingProxyType(dict(value or {}))


def resolve_bending_view_state(
    *,
    selected_detail_view: str | None,
    valid_detail_views: Sequence[str],
    selected_diagram_state: str | None,
) -> "BendingViewState":
    """Resolve presentation selections without changing engineering state."""

    valid_views = tuple(
        value for value in BENDING_DETAIL_VIEWS if value in set(valid_detail_views)
    )
    selected_view = str(selected_detail_view or "positive")
    if selected_view not in valid_views:
        selected_view = valid_views[0] if valid_views else "positive"

    diagram_state = str(selected_diagram_state or "ULS")
    if diagram_state not in BENDING_DIAGRAM_STATES:
        diagram_state = "ULS"

    return BendingViewState(
        selected_detail_view=selected_view,
        valid_detail_views=valid_views,
        selected_diagram_state=diagram_state,
    )


@dataclass(frozen=True, slots=True)
class BendingViewState:
    """Presentation-only state owned by the Bending page."""

    selected_detail_view: str
    valid_detail_views: tuple[str, ...]
    selected_diagram_state: str

    @property
    def showing_negative(self) -> bool:
        return self.selected_detail_view == "negative"


@dataclass(frozen=True, slots=True)
class BendingCaseSnapshot:
    """Read-only projection of one already-calculated bending sign case."""

    moment_sign: str
    has_case: bool
    uls_demand_kNm: float
    sls_demand_kNm: float
    reinforcement_area_mm2: float
    effective_depth_mm: float
    results: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.moment_sign not in BENDING_DETAIL_VIEWS:
            raise ValueError(f"Unsupported bending moment sign: {self.moment_sign!r}")
        object.__setattr__(self, "results", _readonly_mapping(self.results))

    def mutable_results(self) -> dict[str, Any]:
        """Return a detached copy for legacy renderers that assemble view data."""

        return dict(self.results)


@dataclass(frozen=True, slots=True)
class BendingPageSnapshot:
    """Single revision-matched input supplied to Bending page sections."""

    engineering_state: Mapping[str, Any]
    check_pack: Mapping[str, Any]
    authoritative_bending: Mapping[str, Any]
    authoritative_ductility: Mapping[str, Any]
    section_layout: Any
    positive_case: BendingCaseSnapshot
    negative_case: BendingCaseSnapshot
    view: BendingViewState

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "engineering_state", _readonly_mapping(self.engineering_state)
        )
        object.__setattr__(self, "check_pack", _readonly_mapping(self.check_pack))
        object.__setattr__(
            self,
            "authoritative_bending",
            _readonly_mapping(self.authoritative_bending),
        )
        object.__setattr__(
            self,
            "authoritative_ductility",
            _readonly_mapping(self.authoritative_ductility),
        )

    @property
    def active_case(self) -> BendingCaseSnapshot:
        return (
            self.negative_case
            if self.view.showing_negative and self.negative_case.has_case
            else self.positive_case
        )


def build_bending_page_snapshot(
    *,
    engineering_state: Mapping[str, Any],
    check_pack: Mapping[str, Any],
    authoritative_bending: Mapping[str, Any] | None,
    authoritative_ductility: Mapping[str, Any] | None,
    section_layout: Any,
    positive_case: BendingCaseSnapshot,
    negative_case: BendingCaseSnapshot,
    selected_detail_view: str | None,
    valid_detail_views: Sequence[str],
    selected_diagram_state: str | None,
) -> BendingPageSnapshot:
    """Build a presentation snapshot without recalculating any result."""

    return BendingPageSnapshot(
        engineering_state=engineering_state,
        check_pack=check_pack,
        authoritative_bending=authoritative_bending or {},
        authoritative_ductility=authoritative_ductility or {},
        section_layout=section_layout,
        positive_case=positive_case,
        negative_case=negative_case,
        view=resolve_bending_view_state(
            selected_detail_view=selected_detail_view,
            valid_detail_views=valid_detail_views,
            selected_diagram_state=selected_diagram_state,
        ),
    )


__all__ = [
    "BENDING_DETAIL_VIEWS",
    "BENDING_DIAGRAM_STATES",
    "BendingCaseSnapshot",
    "BendingPageSnapshot",
    "BendingViewState",
    "build_bending_page_snapshot",
    "resolve_bending_view_state",
]
