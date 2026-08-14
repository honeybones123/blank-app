"""Section-shape helpers invoked by an already selected family.

These strategies translate family-requested geometry moves into complete
typed section updates.  They do not select families, generate unrequested
moves, rank candidates, publish decisions, or authorise Apply.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol, TypeVar

from inputs_v2.application.input_commands import UpdateFirstSlice
from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.domain.section_geometry import (
    RectSectionGeometry,
    SectionGeometry,
    SymmetricISectionGeometry,
    TSectionGeometry,
)


ProposalT = TypeVar("ProposalT", bound=UpdateFirstSlice)


class FamilySectionStrategy(Protocol):
    """Geometry translation owned by the family that invokes it."""

    shape: str

    def revise(
        self,
        proposal: ProposalT,
        *,
        web_or_rect_width_mm: float | None = None,
        depth_mm: float | None = None,
        flange_width_mm: float | None = None,
        flange_thickness_mm: float | None = None,
    ) -> ProposalT: ...

    def geometry(self, proposal: UpdateFirstSlice) -> SectionGeometry: ...


class RectangularSectionStrategy:
    shape = "RECT"

    def revise(
        self,
        proposal: ProposalT,
        *,
        web_or_rect_width_mm: float | None = None,
        depth_mm: float | None = None,
        flange_width_mm: float | None = None,
        flange_thickness_mm: float | None = None,
    ) -> ProposalT:
        if flange_width_mm is not None or flange_thickness_mm is not None:
            raise ValueError("Rectangular families cannot change flange geometry.")
        return replace(
            proposal,
            width_mm=(
                proposal.width_mm
                if web_or_rect_width_mm is None
                else float(web_or_rect_width_mm)
            ),
            depth_mm=proposal.depth_mm if depth_mm is None else float(depth_mm),
        )

    def geometry(self, proposal: UpdateFirstSlice) -> RectSectionGeometry:
        return RectSectionGeometry(proposal.width_mm, proposal.depth_mm).validated()


class TSectionStrategy:
    shape = "T"

    def revise(
        self,
        proposal: ProposalT,
        *,
        web_or_rect_width_mm: float | None = None,
        depth_mm: float | None = None,
        flange_width_mm: float | None = None,
        flange_thickness_mm: float | None = None,
    ) -> ProposalT:
        web = proposal.web_width_mm if web_or_rect_width_mm is None else float(web_or_rect_width_mm)
        flange = proposal.flange_width_mm if flange_width_mm is None else float(flange_width_mm)
        thickness = (
            proposal.flange_thickness_mm
            if flange_thickness_mm is None
            else float(flange_thickness_mm)
        )
        if web is None or flange is None or thickness is None:
            raise ValueError("T-section candidates require complete flange and web geometry.")
        # Translate the selected family's generic web/depth move into the
        # nearest valid T geometry. The strategy does not invent a new move:
        # it merely prevents the requested web from overtaking its flange and
        # preserves a positive web below the flange.
        web = min(float(web), float(flange))
        revised_depth = proposal.depth_mm if depth_mm is None else float(depth_mm)
        revised_depth = max(200.0, float(revised_depth), float(thickness) + 25.0)
        revised = replace(
            proposal,
            # ``width_mm`` remains a compatibility mirror until all legacy
            # policy inputs migrate. The authoritative T width is ``web``.
            width_mm=float(web),
            web_width_mm=float(web),
            depth_mm=revised_depth,
            flange_width_mm=float(flange),
            flange_thickness_mm=float(thickness),
        )
        # Validate the T envelope here explicitly. Symmetric-I adds its second
        # flange constraint in its override after applying this translation.
        TSectionStrategy.geometry(self, revised)
        return revised

    def geometry(self, proposal: UpdateFirstSlice) -> TSectionGeometry:
        if (
            proposal.web_width_mm is None
            or proposal.flange_width_mm is None
            or proposal.flange_thickness_mm is None
        ):
            raise ValueError("T-section candidates require complete flange and web geometry.")
        return TSectionGeometry(
            web_width_mm=proposal.web_width_mm,
            depth_mm=proposal.depth_mm,
            flange_width_mm=proposal.flange_width_mm,
            flange_thickness_mm=proposal.flange_thickness_mm,
        ).validated()


class SymmetricISectionStrategy(TSectionStrategy):
    shape = "I"

    def revise(
        self,
        proposal: ProposalT,
        *,
        web_or_rect_width_mm: float | None = None,
        depth_mm: float | None = None,
        flange_width_mm: float | None = None,
        flange_thickness_mm: float | None = None,
    ) -> ProposalT:
        revised = super().revise(
            proposal,
            web_or_rect_width_mm=web_or_rect_width_mm,
            depth_mm=depth_mm,
            flange_width_mm=flange_width_mm,
            flange_thickness_mm=flange_thickness_mm,
        )
        assert revised.flange_thickness_mm is not None
        minimum_depth = 2.0 * float(revised.flange_thickness_mm) + 25.0
        if float(revised.depth_mm) < minimum_depth:
            revised = replace(revised, depth_mm=minimum_depth)
        self.geometry(revised)
        return revised

    def geometry(self, proposal: UpdateFirstSlice) -> SymmetricISectionGeometry:
        if (
            proposal.web_width_mm is None
            or proposal.flange_width_mm is None
            or proposal.flange_thickness_mm is None
        ):
            raise ValueError("I-section candidates require complete flange and web geometry.")
        return SymmetricISectionGeometry(
            web_width_mm=proposal.web_width_mm,
            depth_mm=proposal.depth_mm,
            flange_width_mm=proposal.flange_width_mm,
            flange_thickness_mm=proposal.flange_thickness_mm,
        ).validated()


_STRATEGIES: dict[str, FamilySectionStrategy] = {
    "RECT": RectangularSectionStrategy(),
    "T": TSectionStrategy(),
    "I": SymmetricISectionStrategy(),
}


def section_strategy_for(current: BeamInputs | UpdateFirstSlice) -> FamilySectionStrategy:
    """Resolve geometry translation after a family has already been selected."""

    try:
        return _STRATEGIES[str(current.section_shape).upper()]
    except KeyError as exc:
        raise ValueError("Section shape is not supported by the selected family.") from exc


def revise_family_geometry(
    current: BeamInputs,
    proposal: ProposalT,
    *,
    width_mm: float | None = None,
    depth_mm: float | None = None,
    flange_width_mm: float | None = None,
    flange_thickness_mm: float | None = None,
) -> ProposalT:
    """Apply only the geometry move requested by the selected family."""

    return section_strategy_for(current).revise(
        proposal,
        web_or_rect_width_mm=width_mm,
        depth_mm=depth_mm,
        flange_width_mm=flange_width_mm,
        flange_thickness_mm=flange_thickness_mm,
    )


def proposal_concrete_area_mm2(proposal: UpdateFirstSlice) -> float:
    """Return actual section area for family-owned ranking evidence."""

    return section_strategy_for(proposal).geometry(proposal).concrete_area_mm2
