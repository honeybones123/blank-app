"""Pure Creep publication/report projection.

This module owns formatting of already-calculated Creep values for the shared
result/report store.  It never reads Streamlit state and never recalculates an
engineering quantity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


@dataclass(frozen=True, slots=True)
class CreepReportProjection:
    phi_cc_t: float | None
    phi_cc_star_table: float | None
    k2_creep: float | None
    k3_creep: float | None
    k4_creep: float | None
    k5_creep: float | None
    k6_creep: float | None
    eps_cc: float | None = None
    eps_cc_micro: float | None = None

    def result_updates(self, *, include_strain: bool) -> dict[str, float | None]:
        values: dict[str, float | None] = {
            "phi_cc_t": self.phi_cc_t,
            "phi_cc_star_table": self.phi_cc_star_table,
            "k2_creep": self.k2_creep,
            "k3_creep": self.k3_creep,
            "k4_creep": self.k4_creep,
            "k5_creep": self.k5_creep,
            "k6_creep": self.k6_creep,
        }
        if include_strain:
            values.update(
                {
                    "eps_cc": self.eps_cc,
                    "eps_cc_micro": self.eps_cc_micro,
                }
            )
        return values


def build_creep_report_projection(
    values: Mapping[str, Any],
) -> CreepReportProjection:
    """Detach current authoritative/display values into a pure projection."""

    return CreepReportProjection(
        phi_cc_t=_optional_float(values.get("phi_cc_t")),
        phi_cc_star_table=_optional_float(values.get("phi_cc_star_table")),
        k2_creep=_optional_float(values.get("k2_creep")),
        k3_creep=_optional_float(values.get("k3_creep")),
        k4_creep=_optional_float(values.get("k4_creep")),
        k5_creep=_optional_float(values.get("k5_creep")),
        k6_creep=_optional_float(values.get("k6_creep")),
        eps_cc=_optional_float(values.get("eps_cc")),
        eps_cc_micro=_optional_float(values.get("eps_cc_micro")),
    )


__all__ = ["CreepReportProjection", "build_creep_report_projection"]
