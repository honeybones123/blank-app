"""V2-owned time-dependent concrete calculation components."""

from __future__ import annotations

import math
from dataclasses import dataclass

from inputs_v2.engineering.time_dependent_concrete import *  # noqa: F403


@dataclass(frozen=True)
class LoadingAgeFactorInput:
    """Input contract for the AS 3600 loading-age creep factor."""

    age_at_loading_days: float


@dataclass(frozen=True)
class LoadingAgeFactorResult:
    """Result contract for the AS 3600 loading-age creep factor."""

    k3: float
    effective_age_days: float


def calculate_loading_age_factor(
    values: LoadingAgeFactorInput,
) -> LoadingAgeFactorResult:
    """Calculate k3 using AS 3600:2018 Cl. 3.1.8.3."""

    age = float(values.age_at_loading_days)
    if not math.isfinite(age):
        raise ValueError("age_at_loading_days must be finite")
    effective_age = max(age, 1.0)
    return LoadingAgeFactorResult(
        k3=2.7 / (1.0 + math.log(effective_age)),
        effective_age_days=effective_age,
    )


__all__ = [
    "LoadingAgeFactorInput",
    "LoadingAgeFactorResult",
    "calculate_loading_age_factor",
]
