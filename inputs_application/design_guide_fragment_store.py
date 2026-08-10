"""Session-owned lifecycle for the Inputs Design Guide fragment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, MutableMapping

from application.contracts.design_brain import AuthoritativeDesignResult
from application.contracts.design_branch import DesignBranch
from inputs_application.design_branch_store import BeamDesignBranchStore


DESIGN_GUIDE_FRAGMENT_STATE_KEY = "_inputs_design_guide_fragment_state_v1"
DESIGN_GUIDE_FRAGMENT_BY_BRANCH_STATE_KEY = "_inputs_design_guide_fragment_by_branch_v2"


@dataclass(frozen=True)
class DesignGuideFragmentState:
    """Last authoritative publication plus the current refresh state."""

    status: str = "empty"
    active_engineering_hash: str | None = None
    active_publication_authority_hash: str | None = None
    active_publication: dict[str, Any] = field(default_factory=dict)
    active_workspace_revision: int | None = None
    pending_workspace_revision: int | None = None
    last_error: str | None = None
    beam_id: str | None = None
    design_branch: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PublicationStore:
    """Keep publication replacement atomic across workspace refreshes."""

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def _identity(
        self,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> tuple[str, DesignBranch]:
        resolved_beam_id = str(
            beam_id or self._state.get("active_beam_id") or ""
        ).strip()
        if not resolved_beam_id:
            return "", DesignBranch.BEAM_INPUTS
        store = BeamDesignBranchStore(self._state)
        branch = (
            DesignBranch(design_branch)
            if design_branch is not None
            else store.active_context(
                resolved_beam_id,
                page_slug=str(
                    self._state.get("_active_page_slug")
                    or self._state.get("page_slug")
                    or "inputs"
                ),
            )
        )
        return resolved_beam_id, branch

    @staticmethod
    def _key(beam_id: str, branch: DesignBranch) -> str:
        return f"{beam_id}:{branch.value}"

    def _is_projected_identity(self, beam_id: str, branch: DesignBranch) -> bool:
        active_beam_id = str(self._state.get("active_beam_id") or "").strip()
        if active_beam_id != beam_id:
            return False
        projected = BeamDesignBranchStore(self._state).active_context(
            active_beam_id,
            page_slug=str(
                self._state.get("_active_page_slug")
                or self._state.get("page_slug")
                or "inputs"
            ),
        )
        return projected is branch

    def current(
        self,
        *,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> DesignGuideFragmentState:
        resolved_beam_id, branch = self._identity(beam_id, design_branch)
        by_branch = self._state.get(DESIGN_GUIDE_FRAGMENT_BY_BRANCH_STATE_KEY)
        if isinstance(by_branch, dict):
            # A missing entry must stay missing. Reusing the single projection
            # would show the previous branch's recommendation and enable a
            # stale Apply action after a branch switch.
            value = (
                by_branch.get(self._key(resolved_beam_id, branch))
                if resolved_beam_id
                else None
            )
        else:
            value = self._state.get(DESIGN_GUIDE_FRAGMENT_STATE_KEY)
        if isinstance(value, DesignGuideFragmentState):
            return value
        return DesignGuideFragmentState()

    def project_current_branch(
        self,
        *,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> DesignGuideFragmentState:
        """Refresh the retired single key as a display-only projection."""

        current = self.current(beam_id=beam_id, design_branch=design_branch)
        self._state[DESIGN_GUIDE_FRAGMENT_STATE_KEY] = current
        return current

    def _store(
        self,
        publication: DesignGuideFragmentState,
        *,
        beam_id: str,
        design_branch: DesignBranch,
    ) -> DesignGuideFragmentState:
        bound = DesignGuideFragmentState(
            **{
                **publication.to_dict(),
                "beam_id": beam_id or None,
                "design_branch": design_branch.value,
            }
        )
        by_branch = dict(
            self._state.get(DESIGN_GUIDE_FRAGMENT_BY_BRANCH_STATE_KEY) or {}
        )
        if beam_id:
            by_branch[self._key(beam_id, design_branch)] = bound
            self._state[DESIGN_GUIDE_FRAGMENT_BY_BRANCH_STATE_KEY] = by_branch
        # Keep the established key as a display projection only. Publishing
        # background work for the hidden branch cannot replace the visible
        # branch card.
        if not beam_id or self._is_projected_identity(beam_id, design_branch):
            self._state[DESIGN_GUIDE_FRAGMENT_STATE_KEY] = bound
        return bound

    def begin_refresh(
        self,
        *,
        workspace_revision: int,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> DesignGuideFragmentState:
        resolved_beam_id, branch = self._identity(beam_id, design_branch)
        current = self.current(beam_id=resolved_beam_id, design_branch=branch)
        newest_known_revision = max(
            int(current.active_workspace_revision or 0),
            int(current.pending_workspace_revision or 0),
        )
        if int(workspace_revision) < newest_known_revision:
            raise ValueError("cannot refresh a superseded Design Guide revision")
        refreshing = DesignGuideFragmentState(
            status="refreshing",
            active_engineering_hash=current.active_engineering_hash,
            active_publication_authority_hash=(
                current.active_publication_authority_hash
            ),
            active_publication=dict(current.active_publication),
            active_workspace_revision=current.active_workspace_revision,
            pending_workspace_revision=int(workspace_revision),
            last_error=None,
        )
        return self._store(
            refreshing,
            beam_id=resolved_beam_id,
            design_branch=branch,
        )

    def publish(
        self,
        result: AuthoritativeDesignResult,
        *,
        workspace_revision: int | None = None,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> DesignGuideFragmentState:
        if not isinstance(result, AuthoritativeDesignResult):
            raise TypeError("result must be an AuthoritativeDesignResult")
        resolved_beam_id, branch = self._identity(beam_id, design_branch)
        current = self.current(beam_id=resolved_beam_id, design_branch=branch)
        resolved_revision = (
            int(workspace_revision)
            if workspace_revision is not None
            else current.pending_workspace_revision
        )
        if resolved_revision is None:
            raise ValueError("workspace_revision is required for publication")
        if (
            current.pending_workspace_revision is not None
            and int(current.pending_workspace_revision) != int(resolved_revision)
        ):
            raise ValueError("cannot publish a superseded Design Guide revision")
        ready = DesignGuideFragmentState(
            status="ready",
            active_engineering_hash=result.engineering_hash,
            active_publication_authority_hash=(
                result.publication_authority_hash
            ),
            active_publication=dict(result.final_publication or {}),
            active_workspace_revision=int(resolved_revision),
            pending_workspace_revision=None,
            last_error=None,
        )
        return self._store(ready, beam_id=resolved_beam_id, design_branch=branch)

    def fail_refresh(
        self,
        error: BaseException | str,
        *,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> DesignGuideFragmentState:
        resolved_beam_id, branch = self._identity(beam_id, design_branch)
        current = self.current(beam_id=resolved_beam_id, design_branch=branch)
        failed = DesignGuideFragmentState(
            status=(
                "ready_stale"
                if current.active_publication
                else "failed"
            ),
            active_engineering_hash=current.active_engineering_hash,
            active_publication_authority_hash=(
                current.active_publication_authority_hash
            ),
            active_publication=dict(current.active_publication),
            active_workspace_revision=current.active_workspace_revision,
            pending_workspace_revision=None,
            last_error=(
                str(error)
                if isinstance(error, str)
                else f"{type(error).__name__}: {error}"
            ),
        )
        return self._store(failed, beam_id=resolved_beam_id, design_branch=branch)

    def is_current(
        self,
        *,
        workspace_revision: int,
        engineering_hash: str | None,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> bool:
        current = self.current(beam_id=beam_id, design_branch=design_branch)
        return bool(
            current.status == "ready"
            and current.active_workspace_revision == int(workspace_revision)
            and current.active_engineering_hash == str(engineering_hash or "")
            and current.active_publication_authority_hash
        )

    def clear(
        self,
        *,
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> DesignGuideFragmentState:
        resolved_beam_id, branch = self._identity(beam_id, design_branch)
        empty = DesignGuideFragmentState()
        return self._store(empty, beam_id=resolved_beam_id, design_branch=branch)


# Transitional import compatibility only. Both names resolve to one owner and
# one namespaced session record.
DesignGuideFragmentStore = PublicationStore


__all__ = [
    "DESIGN_GUIDE_FRAGMENT_STATE_KEY",
    "DESIGN_GUIDE_FRAGMENT_BY_BRANCH_STATE_KEY",
    "DesignGuideFragmentState",
    "DesignGuideFragmentStore",
    "PublicationStore",
]
