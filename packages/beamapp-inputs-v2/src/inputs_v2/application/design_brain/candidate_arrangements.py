"""Neutral enumeration of practical reinforcement arrangements.

This module does not accept, reject or rank candidates.  A family owner must
explicitly request these variants and pass every variant through the shared
calculation and validation gateway.
"""

from __future__ import annotations

from dataclasses import replace

from inputs_v2.application.design_brain_apply import Candidate
from inputs_v2.engineering.reinforcement_fit import practical_row_counts


def with_practical_bottom_rows(candidate: Candidate) -> tuple[Candidate, ...]:
    """Return one-row then balanced two-row variants for the proposed bars."""

    variants: list[Candidate] = []
    for rows in practical_row_counts(candidate.proposal.bottom_bars):
        suffix = "-rows" + "-".join(str(count) for count in rows)
        variants.append(
            replace(candidate, candidate_id=candidate.candidate_id + suffix, row_counts=rows)
        )
    return tuple(variants)


__all__ = ["with_practical_bottom_rows"]
