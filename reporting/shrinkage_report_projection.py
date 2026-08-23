"""Pure Shrinkage publication/report projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


@dataclass(frozen=True, slots=True)
class ShrinkageReportProjection:
    eps_cs_total: float | None
    eps_cs_total_micro: float | None
    eps_cse: float | None
    eps_csd_t: float | None
    th_shrinkage: float | None
    k1_shrinkage: float | None
    method: str
    reference: str
    warnings: tuple[str, ...]

    def result_updates(self) -> dict[str, float | None]:
        return {
            "eps_cs_total": self.eps_cs_total,
            "eps_cs_total_micro": self.eps_cs_total_micro,
            "eps_cse": self.eps_cse,
            "eps_csd_t": self.eps_csd_t,
            "th_shrinkage": self.th_shrinkage,
            "k1_shrinkage": self.k1_shrinkage,
        }

    def method_update(self) -> dict[str, object]:
        return {
            "method": self.method,
            "reference": self.reference,
            "warnings": list(self.warnings),
        }


def build_shrinkage_report_projection(
    values: Mapping[str, Any],
    *,
    method: str,
    reference: str,
    warnings: tuple[str, ...] | list[str] = (),
) -> ShrinkageReportProjection:
    return ShrinkageReportProjection(
        eps_cs_total=_optional_float(values.get("eps_cs_total")),
        eps_cs_total_micro=_optional_float(values.get("eps_cs_total_micro")),
        eps_cse=_optional_float(values.get("eps_cse")),
        eps_csd_t=_optional_float(values.get("eps_csd_t")),
        th_shrinkage=_optional_float(values.get("th_shrinkage")),
        k1_shrinkage=_optional_float(values.get("k1_shrinkage")),
        method=str(method),
        reference=str(reference),
        warnings=tuple(str(value) for value in warnings),
    )


__all__ = ["ShrinkageReportProjection", "build_shrinkage_report_projection"]
