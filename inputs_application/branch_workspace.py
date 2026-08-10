"""Pure resolution of one branch into immutable engineering workspace data."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from application.contracts.design_actions import DesignActionsSnapshot
from application.contracts.design_branch import (
    BeamDesignSnapshot,
    BranchWorkspaceIdentity,
    DesignBranch,
    canonical_hash,
    freeze_payload,
    thaw_payload,
)
from application.contracts.load_analysis import LoadAnalysisSnapshot
from application.design_actions_adapters import (
    BeamSetupDesignActionsAdapter,
    LoadAnalysisDesignActionsAdapter,
)


class ActionSource(str, Enum):
    MANUAL = "manual"
    LOAD_ANALYSIS = "load_analysis"


class ActionSelectionPolicy(str, Enum):
    MANUAL = "manual"
    MAXIMUM = "maximum"
    SELECTED_SECTION = "selected_section"


@dataclass(frozen=True)
class EngineeringWorkspaceSnapshot:
    identity: BranchWorkspaceIdentity
    branch_payload: Mapping[str, Any] = field(default_factory=dict)
    load_analysis_payload: Mapping[str, Any] | None = None
    design_actions: DesignActionsSnapshot | None = None
    engineering_hash: str = ""

    def __post_init__(self) -> None:
        branch_payload = freeze_payload(self.branch_payload or {})
        analysis_payload = (
            freeze_payload(self.load_analysis_payload)
            if self.load_analysis_payload is not None
            else None
        )
        expected = canonical_hash(
            {
                "identity": {
                    "beam_id": self.identity.beam_id,
                    "design_branch": self.identity.design_branch.value,
                    "branch_revision": self.identity.branch_revision,
                    "branch_hash": self.identity.branch_hash,
                    "load_analysis_revision": self.identity.load_analysis_revision,
                    "load_analysis_hash": self.identity.load_analysis_hash,
                    "action_source": self.identity.action_source,
                    "action_selection_policy": self.identity.action_selection_policy,
                    "design_actions_hash": self.identity.design_actions_hash,
                    "calculation_version": self.identity.calculation_version,
                },
                "branch_payload": branch_payload,
                "load_analysis_payload": analysis_payload,
            }
        )
        supplied = str(self.engineering_hash or "").strip()
        if supplied and supplied != expected:
            raise ValueError("engineering_hash does not match workspace content")
        object.__setattr__(self, "branch_payload", branch_payload)
        object.__setattr__(self, "load_analysis_payload", analysis_payload)
        object.__setattr__(self, "engineering_hash", supplied or expected)

    def to_mutable_state(self) -> dict[str, Any]:
        state = thaw_payload(self.branch_payload)
        if self.load_analysis_payload is not None:
            state.update(thaw_payload(self.load_analysis_payload))
        if self.design_actions is not None:
            actions = self.design_actions
            state.update(
                {
                    "actions_mode": actions.actions_mode,
                    "actions_source": actions.actions_source,
                    "design_actions_source": actions.design_actions_source,
                    "sfd_Mmax_abs_kNm": actions.mu,
                    "sfd_Vmax_abs_kN": actions.vu,
                    "sfd_Msls_max_kNm": actions.sls_m,
                    "sfd_Vsls_max_kN": actions.sls_v,
                    "M_pos_max_uls_kNm": actions.mu_pos,
                    "M_neg_min_uls_kNm": -actions.mu_neg,
                    "M_pos_max_sls_kNm": actions.sls_m_pos,
                    "M_neg_min_sls_kNm": -actions.sls_m_neg,
                    "uls_Mstar": actions.mu_signed,
                    "uls_Vstar": actions.vu,
                    "uls_Nstar": actions.nu,
                    "sls_Mstar": actions.sls_m_signed,
                    "sls_Vstar": actions.sls_v,
                    "sls_Nstar": actions.sls_n,
                    "Tu_star": actions.tu,
                    "P_star": actions.pu,
                }
            )
        return state


def resolve_branch_workspace(
    branch_snapshot: BeamDesignSnapshot,
    load_analysis_snapshot: LoadAnalysisSnapshot | None,
    action_source: ActionSource | str,
    action_selection_policy: ActionSelectionPolicy | str,
    *,
    derived_design_actions: DesignActionsSnapshot | None = None,
) -> EngineeringWorkspaceSnapshot:
    """Resolve content and provenance only; execute no engineering work."""

    source = ActionSource(action_source)
    policy = ActionSelectionPolicy(action_selection_policy)
    branch = branch_snapshot.design_branch
    needs_analysis = branch is DesignBranch.LOAD_ANALYSIS or source is ActionSource.LOAD_ANALYSIS
    if needs_analysis and load_analysis_snapshot is None:
        raise ValueError("Load Analysis identity is required for calculated actions")
    if load_analysis_snapshot is not None and load_analysis_snapshot.beam_id != branch_snapshot.beam_id:
        raise ValueError("branch and Load Analysis snapshots belong to different beams")
    if branch is DesignBranch.LOAD_ANALYSIS and source is not ActionSource.LOAD_ANALYSIS:
        raise ValueError("LOAD_ANALYSIS always derives actions from Load Analysis")

    state = branch_snapshot.to_payload()
    analysis_payload = None
    if needs_analysis:
        analysis_payload = load_analysis_snapshot.to_mutable_dict()  # type: ignore[union-attr]
        state.update(analysis_payload)
        state["actions_mode"] = "design"
        state["design_actions_source"] = (
            "section" if policy is ActionSelectionPolicy.SELECTED_SECTION else "max"
        )
        # Solved actions are a derived immutable result, not editable analysis
        # state.  Execution owners pass that result explicitly.  The adapter
        # fallback remains useful for pure resolver tests and for persisted
        # analysis snapshots that already contain an authoritative action
        # envelope.
        actions = (
            derived_design_actions
            if derived_design_actions is not None
            else LoadAnalysisDesignActionsAdapter.from_state(state)
        )
    else:
        if derived_design_actions is not None:
            raise ValueError("manual workspaces cannot receive derived Load Analysis actions")
        state["actions_mode"] = "manual"
        actions = BeamSetupDesignActionsAdapter.from_state(state)
    actions_hash = canonical_hash(actions.to_snapshot_mapping())
    identity = BranchWorkspaceIdentity(
        beam_id=branch_snapshot.beam_id,
        design_branch=branch,
        branch_revision=branch_snapshot.revision,
        branch_hash=branch_snapshot.content_hash,
        load_analysis_revision=(load_analysis_snapshot.revision if needs_analysis else None),
        load_analysis_hash=(load_analysis_snapshot.content_hash if needs_analysis else None),
        action_source=source.value,
        action_selection_policy=policy.value,
        design_actions_hash=actions_hash,
        calculation_version=str(state.get("calculation_version") or "runtime.v1"),
    )
    return EngineeringWorkspaceSnapshot(
        identity=identity,
        branch_payload=branch_snapshot.to_payload(),
        load_analysis_payload=analysis_payload,
        design_actions=actions,
    )


__all__ = [
    "ActionSelectionPolicy",
    "ActionSource",
    "EngineeringWorkspaceSnapshot",
    "resolve_branch_workspace",
]
