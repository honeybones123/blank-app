"""Explicit Inputs workspace context.

Streamlit session state remains the storage adapter.  This object is the
application boundary passed through the page regions so they do not each
reconstruct service handles or read raw session keys independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from inputs_application.engineering_input_store import InputSnapshotState
from inputs_application.session_services import InputsSessionServices


@dataclass(frozen=True)
class InputsWorkspaceContext:
    """One read boundary for a single Inputs-page render."""

    services: InputsSessionServices
    active_beam_id: str | None
    input_state: InputSnapshotState
    input_revision: int
    engineering_result: Any | None
    publication: Any

    @classmethod
    def from_session(
        cls,
        session_storage: MutableMapping[str, Any],
        *,
        active_beam_id: str | None = None,
    ) -> "InputsWorkspaceContext":
        services = InputsSessionServices.from_mapping(session_storage)
        beam_id = active_beam_id or session_storage.get("active_beam_id")
        input_state = (
            services.input_snapshots.current_for_beam(str(beam_id))
            if beam_id
            else InputSnapshotState()
        )
        result = services.engineering_results.current()
        return cls(
            services=services,
            active_beam_id=str(beam_id) if beam_id else None,
            input_state=input_state,
            input_revision=int(input_state.revision or 0),
            engineering_result=result,
            publication=services.publications.current(),
        )

    def with_current_results(self) -> "InputsWorkspaceContext":
        """Refresh only published result handles without rereading raw keys."""

        return InputsWorkspaceContext(
            services=self.services,
            active_beam_id=self.active_beam_id,
            input_state=self.input_state,
            input_revision=self.input_revision,
            engineering_result=self.services.engineering_results.current(),
            publication=self.services.publications.current(),
        )

    def current_input_state(self) -> InputSnapshotState:
        """Read the latest committed state for this context's beam.

        Fragment reruns may happen after a widget callback commits a newer
        revision.  Refreshing through the store keeps diagrams current without
        rebuilding the page context or touching raw session keys.
        """

        if self.active_beam_id:
            return self.services.input_snapshots.current_for_beam(
                self.active_beam_id
            )
        return InputSnapshotState()


__all__ = ["InputsWorkspaceContext"]
