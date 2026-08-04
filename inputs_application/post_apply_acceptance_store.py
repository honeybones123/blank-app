"""Typed session boundary for post-Apply acceptance handoff metadata."""

from __future__ import annotations

from typing import Any, MutableMapping


class PostApplyAcceptanceStore:
    LEASE_KEY = "_typed_inputs_post_apply_acceptance_fp"
    FINGERPRINT_KEY = "_design_guide_post_cleanup_acceptance_fp"
    ENABLED_KEY = "_design_guide_post_cleanup_acceptance_enabled"
    PROBE_KEY = "_typed_post_apply_rehydrate_probe"

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def store(self, fingerprint: tuple[tuple[str, str], ...]) -> None:
        self._state[self.LEASE_KEY] = {"fingerprint": fingerprint}
        self._state[self.FINGERPRINT_KEY] = fingerprint
        self._state[self.ENABLED_KEY] = True

    def expected(self) -> Any:
        lease = self._state.get(self.LEASE_KEY)
        return lease.get("fingerprint") if isinstance(lease, dict) else lease

    def record_probe(self, *, expected: Any, current: Any, mismatches: dict) -> None:
        self._state[self.PROBE_KEY] = {
            "expected_present": expected is not None,
            "matched": bool(expected is not None and expected == current),
            "mismatches": mismatches,
        }

    def clear_lease(self) -> None:
        self._state.pop(self.LEASE_KEY, None)

    def enable(self, fingerprint: Any = None) -> None:
        if fingerprint is not None:
            self._state[self.FINGERPRINT_KEY] = fingerprint
        self._state[self.ENABLED_KEY] = True


__all__ = ["PostApplyAcceptanceStore"]
