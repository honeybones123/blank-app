"""Source-specific adapters into the shared Design Actions contract."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from application.contracts.design_actions import DesignActionsSnapshot
from calculations.design_actions import resolve_design_actions_contract_from_state


def _working_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(state or {})


def _with_handover_metadata(
    actions: DesignActionsSnapshot,
    state: Mapping[str, Any],
) -> DesignActionsSnapshot:
    section_x = state.get("design_section_x_m")
    revision = state.get("input_revision", state.get("_input_revision"))
    return replace(
        actions,
        design_section_x_m=(float(section_x) if section_x not in (None, "") else None),
        input_revision=(int(revision) if revision not in (None, "") else None),
    )


@dataclass(frozen=True)
class BeamSetupDesignActionsAdapter:
    """Adapt manually entered Beam Setup actions without recalculating them."""

    @staticmethod
    def from_state(state: Mapping[str, Any] | None) -> DesignActionsSnapshot:
        working = _working_state(state)
        working["actions_mode"] = "manual"
        return _with_handover_metadata(
            resolve_design_actions_contract_from_state(working),
            working,
        )


@dataclass(frozen=True)
class LoadAnalysisDesignActionsAdapter:
    """Adapt actions solved by Load Analysis into the same brain contract."""

    @staticmethod
    def from_state(state: Mapping[str, Any] | None) -> DesignActionsSnapshot:
        working = _working_state(state)
        working["actions_mode"] = "design"
        working.setdefault("design_actions_source", "max")
        return _with_handover_metadata(
            resolve_design_actions_contract_from_state(working),
            working,
        )


def adapt_design_actions_from_state(
    state: Mapping[str, Any] | None,
) -> DesignActionsSnapshot:
    """Select only the source adapter; engineering evaluation remains shared."""

    working = _working_state(state)
    mode = str(working.get("actions_mode") or "manual").strip().lower()
    if mode == "design":
        return LoadAnalysisDesignActionsAdapter.from_state(working)
    return BeamSetupDesignActionsAdapter.from_state(working)


__all__ = [
    "BeamSetupDesignActionsAdapter",
    "LoadAnalysisDesignActionsAdapter",
    "adapt_design_actions_from_state",
]
