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
        if (
            str(working.get("design_actions_source") or "max") == "max"
            and all(
                key in working
                for key in (
                    "M_pos_max_uls_kNm",
                    "M_neg_min_uls_kNm",
                    "M_pos_max_sls_kNm",
                    "M_neg_min_sls_kNm",
                )
            )
        ):
            # Explicit solved extrema, including an all-zero no-load result,
            # are authoritative for this adapter.  The shared resolver keeps
            # manual aliases as a legacy fallback, so neutralise only its local
            # copy to prevent Beam Inputs actions leaking into Load Analysis.
            for key in (
                "uls_Mstar_pos_manual",
                "uls_Mstar_neg_manual",
                "Mu_star_pos_manual",
                "Mu_star_neg_manual",
                "sls_Mstar_pos_manual",
                "sls_Mstar_neg_manual",
            ):
                working[key] = 0.0
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
