"""Typed presentation inputs for the three Shear calculation-check families.

The existing shear calculation/publication pipeline remains authoritative. This
module only detaches the already-resolved calculation bundle and supplies one
revision-matched, read-only input to every check renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from engineering_page_sections.shear_page_context import ShearPageSnapshot


def _readonly_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def _result_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return _readonly_mapping(value)
    try:
        return _readonly_mapping(vars(value))
    except TypeError:
        return _readonly_mapping({})


@dataclass(frozen=True, slots=True)
class ShearCheckFamilyInput:
    """Common authoritative evidence consumed by one visible check family."""

    live_state: Mapping[str, Any]
    actions: Mapping[str, Any]
    results: Mapping[str, Any]
    published_results: Mapping[str, Any]
    phi: float
    duct_factor: float
    use_general_kv: bool
    method: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "live_state", _readonly_mapping(self.live_state))
        object.__setattr__(self, "actions", _readonly_mapping(self.actions))
        object.__setattr__(self, "results", _readonly_mapping(self.results))
        object.__setattr__(
            self,
            "published_results",
            _readonly_mapping(self.published_results),
        )

    def mutable_results(self) -> dict[str, Any]:
        """Return a detached copy for legacy presentation helpers."""

        return dict(self.results)


@dataclass(frozen=True, slots=True)
class ShearChecksSnapshot:
    """One revision-matched input for all three Shear calculation tabs."""

    torsion_dimensions: ShearCheckFamilyInput
    mcft_strength: ShearCheckFamilyInput
    reinforcement: ShearCheckFamilyInput


def build_shear_checks_snapshot(
    *,
    page_snapshot: ShearPageSnapshot,
    calc_bundle: Mapping[str, Any],
    method: str,
) -> ShearChecksSnapshot:
    """Project a resolved calculation bundle without rerunning engineering."""

    common = dict(
        live_state=_readonly_mapping(calc_bundle.get("live_state")),
        actions=_readonly_mapping(calc_bundle.get("actions_used")),
        results=_result_mapping(calc_bundle.get("results")),
        published_results=page_snapshot.published_results,
        phi=float(calc_bundle.get("phi", 0.0) or 0.0),
        duct_factor=float(calc_bundle.get("k_d", 0.0) or 0.0),
        use_general_kv=bool(calc_bundle.get("use_general_kv", False)),
        method=str(method),
    )
    return ShearChecksSnapshot(
        torsion_dimensions=ShearCheckFamilyInput(**common),
        mcft_strength=ShearCheckFamilyInput(**common),
        reinforcement=ShearCheckFamilyInput(**common),
    )


__all__ = [
    "ShearCheckFamilyInput",
    "ShearChecksSnapshot",
    "build_shear_checks_snapshot",
]
