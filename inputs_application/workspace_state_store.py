"""Typed session boundary for Inputs workspace authority and render telemetry."""

from __future__ import annotations

import time
from typing import Any, MutableMapping

from inputs_application.engineering_input_store import TRANSACTION_META_KEY


class InputsWorkspaceStateStore:
    PRE_AUTHORITY_RECONCILED_KEYS = "_inputs_workspace_pre_authority_reconciled_keys"
    AUTHORITY_PRESENT = "_inputs_workspace_authoritative_result_present"
    AUTHORITY_HASH = "_inputs_workspace_authoritative_result_hash"
    AUTHORITY_REVISION = "_inputs_workspace_authoritative_revision"
    FRAGMENT_RENDER_COUNT = "_inputs_workspace_fragment_render_count"
    SECTION_TIMINGS = "_inputs_workspace_section_timings_ms"
    LAST_RENDERED_REVISION = "_inputs_workspace_last_rendered_revision"
    LAST_RENDERED_AT_NS = "_inputs_workspace_last_rendered_at_ns"
    CALCULATION_STATUS = "_inputs_workspace_calculation_status"
    CALCULATION_REVISION = "_inputs_workspace_calculation_revision"
    CALCULATION_HASH = "_inputs_workspace_calculation_hash"
    CALCULATION_ERROR = "_inputs_workspace_calculation_error"

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def workspace_revision(self) -> int:
        transaction = self._state.get(TRANSACTION_META_KEY)
        if isinstance(transaction, dict) and transaction.get("revision") is not None:
            return int(transaction.get("revision", 0) or 0)
        return int(self._state.get("_inputs_workspace_revision", 0) or 0)

    def align_workspace_revision(self, revision: int) -> int:
        """Compatibility projection; the input transaction owns the revision."""
        resolved = max(0, int(revision))
        current = self.workspace_revision()
        if current and current != resolved:
            raise ValueError(
                "workspace revision cannot diverge from the committed input transaction"
            )
        self._state["_inputs_workspace_revision"] = current or resolved
        return current or resolved

    def set_reconciled_keys(self, keys: list[str]) -> None:
        self._state[self.PRE_AUTHORITY_RECONCILED_KEYS] = list(keys)

    def publish_authoritative_result(self, *, revision: int, result: Any | None) -> None:
        self._state[self.AUTHORITY_PRESENT] = result is not None
        self._state[self.AUTHORITY_HASH] = (
            result.engineering_hash if result is not None else None
        )
        self._state[self.AUTHORITY_REVISION] = int(revision)

    def begin_calculation(self, *, revision: int) -> None:
        self._state[self.CALCULATION_STATUS] = "pending"
        self._state[self.CALCULATION_REVISION] = int(revision)
        self._state[self.CALCULATION_HASH] = None
        self._state[self.CALCULATION_ERROR] = None

    def publish_calculation(self, *, revision: int, engineering_hash: Any | None) -> None:
        self._state[self.CALCULATION_STATUS] = "ready"
        self._state[self.CALCULATION_REVISION] = int(revision)
        self._state[self.CALCULATION_HASH] = (
            str(engineering_hash) if engineering_hash is not None else None
        )
        self._state[self.CALCULATION_ERROR] = None

    def await_calculation_inputs(self, *, revision: int) -> None:
        """Record that this revision intentionally has nothing to calculate."""

        self._state[self.CALCULATION_STATUS] = "awaiting_inputs"
        self._state[self.CALCULATION_REVISION] = int(revision)
        self._state[self.CALCULATION_HASH] = None
        self._state[self.CALCULATION_ERROR] = None

    def fail_calculation(self, *, revision: int, error: BaseException | str) -> None:
        self._state[self.CALCULATION_STATUS] = "failed"
        self._state[self.CALCULATION_REVISION] = int(revision)
        self._state[self.CALCULATION_ERROR] = (
            str(error)
            if isinstance(error, str)
            else f"{type(error).__name__}: {error}"
        )

    def calculation_status(self) -> dict[str, Any]:
        return {
            "status": str(self._state.get(self.CALCULATION_STATUS, "empty")),
            "revision": int(self._state.get(self.CALCULATION_REVISION, 0) or 0),
            "engineering_hash": self._state.get(self.CALCULATION_HASH),
            "error": self._state.get(self.CALCULATION_ERROR),
        }

    def authoritative_revision(self) -> int:
        return int(self._state.get(self.AUTHORITY_REVISION, 0) or 0)

    def authoritative_result_present(self) -> bool:
        return bool(self._state.get(self.AUTHORITY_PRESENT))

    def authoritative_hash(self) -> Any | None:
        return self._state.get(self.AUTHORITY_HASH)

    def record_fragment_render(self) -> int:
        count = int(self._state.get(self.FRAGMENT_RENDER_COUNT, 0) or 0) + 1
        self._state[self.FRAGMENT_RENDER_COUNT] = count
        return count

    def record_render_completion(
        self, *, revision: int, section_timings_ms: dict[str, float]
    ) -> None:
        self._state[self.SECTION_TIMINGS] = dict(section_timings_ms)
        self._state[self.LAST_RENDERED_REVISION] = int(revision)
        self._state[self.LAST_RENDERED_AT_NS] = time.perf_counter_ns()

    def fragment_render_count(self) -> int:
        return int(self._state.get(self.FRAGMENT_RENDER_COUNT, 0) or 0)

    def section_timings(self) -> dict[str, Any]:
        value = self._state.get(self.SECTION_TIMINGS)
        return dict(value) if isinstance(value, dict) else {}

    def last_rendered_revision(self) -> int:
        return int(self._state.get(self.LAST_RENDERED_REVISION, 0) or 0)


__all__ = ["InputsWorkspaceStateStore"]
