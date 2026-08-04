"""Session-owned lifecycle for the Inputs Design Guide fragment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, MutableMapping

from design_brain.authority import AuthoritativeDesignResult


DESIGN_GUIDE_FRAGMENT_STATE_KEY = "_inputs_design_guide_fragment_state_v1"


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PublicationStore:
    """Keep publication replacement atomic across workspace refreshes."""

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def current(self) -> DesignGuideFragmentState:
        value = self._state.get(DESIGN_GUIDE_FRAGMENT_STATE_KEY)
        if isinstance(value, DesignGuideFragmentState):
            return value
        return DesignGuideFragmentState()

    def begin_refresh(
        self,
        *,
        workspace_revision: int,
    ) -> DesignGuideFragmentState:
        current = self.current()
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
        self._state[DESIGN_GUIDE_FRAGMENT_STATE_KEY] = refreshing
        return refreshing

    def publish(
        self,
        result: AuthoritativeDesignResult,
        *,
        workspace_revision: int | None = None,
    ) -> DesignGuideFragmentState:
        if not isinstance(result, AuthoritativeDesignResult):
            raise TypeError("result must be an AuthoritativeDesignResult")
        current = self.current()
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
        self._state[DESIGN_GUIDE_FRAGMENT_STATE_KEY] = ready
        return ready

    def fail_refresh(self, error: BaseException | str) -> DesignGuideFragmentState:
        current = self.current()
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
        self._state[DESIGN_GUIDE_FRAGMENT_STATE_KEY] = failed
        return failed

    def is_current(
        self,
        *,
        workspace_revision: int,
        engineering_hash: str | None,
    ) -> bool:
        current = self.current()
        return bool(
            current.status == "ready"
            and current.active_workspace_revision == int(workspace_revision)
            and current.active_engineering_hash == str(engineering_hash or "")
            and current.active_publication_authority_hash
        )

    def clear(self) -> DesignGuideFragmentState:
        empty = DesignGuideFragmentState()
        self._state[DESIGN_GUIDE_FRAGMENT_STATE_KEY] = empty
        return empty


# Transitional import compatibility only. Both names resolve to one owner and
# one namespaced session record.
DesignGuideFragmentStore = PublicationStore


__all__ = [
    "DESIGN_GUIDE_FRAGMENT_STATE_KEY",
    "DesignGuideFragmentState",
    "DesignGuideFragmentStore",
    "PublicationStore",
]
