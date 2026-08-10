"""Branch-keyed storage for immutable, derived design actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

from application.contracts.design_actions import DesignActionsSnapshot
from application.contracts.design_branch import (
    BranchWorkspaceIdentity,
    DesignBranch,
    canonical_hash,
)


DERIVED_DESIGN_ACTIONS_BY_BRANCH_KEY = "_derived_design_actions_by_branch_v1"


@dataclass(frozen=True)
class DerivedDesignActionsRecord:
    workspace_identity: BranchWorkspaceIdentity
    actions: DesignActionsSnapshot
    actions_hash: str

    def __post_init__(self) -> None:
        expected = canonical_hash(self.actions.to_snapshot_mapping())
        if str(self.actions_hash or "") != expected:
            raise ValueError("derived design-actions hash is invalid")
        if self.workspace_identity.design_actions_hash != expected:
            raise ValueError("workspace and derived action identities differ")

    def to_state_updates(self) -> dict[str, Any]:
        actions = self.actions
        return {
            "actions_mode": actions.actions_mode,
            "actions_source": actions.actions_source,
            "design_actions_source": actions.design_actions_source,
            "design_section_x_m": actions.design_section_x_m,
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


class DerivedDesignActionsStore:
    def __init__(self, storage: MutableMapping[str, Any]) -> None:
        self._state = storage

    @staticmethod
    def _key(beam_id: str, branch: DesignBranch) -> str:
        return f"{str(beam_id)}:{DesignBranch(branch).value}"

    def current(
        self,
        beam_id: str,
        branch: DesignBranch,
    ) -> DerivedDesignActionsRecord | None:
        records = self._state.get(DERIVED_DESIGN_ACTIONS_BY_BRANCH_KEY)
        value = records.get(self._key(beam_id, branch)) if isinstance(records, Mapping) else None
        return value if isinstance(value, DerivedDesignActionsRecord) else None

    def current_for_dependencies(
        self,
        beam_id: str,
        branch: DesignBranch,
        *,
        branch_revision: int,
        branch_hash: str,
        load_analysis_revision: int | None,
        load_analysis_hash: str | None,
    ) -> DerivedDesignActionsRecord | None:
        """Return actions only when every engineering dependency is current."""

        record = self.current(beam_id, branch)
        if record is None:
            return None
        identity = record.workspace_identity
        if (
            identity.branch_revision != int(branch_revision)
            or identity.branch_hash != str(branch_hash or "")
            or identity.load_analysis_revision != load_analysis_revision
            or identity.load_analysis_hash != load_analysis_hash
        ):
            return None
        return record

    def publish(
        self,
        workspace_identity: BranchWorkspaceIdentity,
        actions: DesignActionsSnapshot,
    ) -> DerivedDesignActionsRecord:
        record = DerivedDesignActionsRecord(
            workspace_identity=workspace_identity,
            actions=actions,
            actions_hash=canonical_hash(actions.to_snapshot_mapping()),
        )
        records = dict(self._state.get(DERIVED_DESIGN_ACTIONS_BY_BRANCH_KEY) or {})
        records[
            self._key(workspace_identity.beam_id, workspace_identity.design_branch)
        ] = record
        self._state[DERIVED_DESIGN_ACTIONS_BY_BRANCH_KEY] = records
        return record

    def clear(self, beam_id: str, branch: DesignBranch | None = None) -> None:
        records = dict(self._state.get(DERIVED_DESIGN_ACTIONS_BY_BRANCH_KEY) or {})
        branches = tuple(DesignBranch) if branch is None else (DesignBranch(branch),)
        for selected in branches:
            records.pop(self._key(beam_id, selected), None)
        self._state[DERIVED_DESIGN_ACTIONS_BY_BRANCH_KEY] = records


__all__ = [
    "DERIVED_DESIGN_ACTIONS_BY_BRANCH_KEY",
    "DerivedDesignActionsRecord",
    "DerivedDesignActionsStore",
]
