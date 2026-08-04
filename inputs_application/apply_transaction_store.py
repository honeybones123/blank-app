"""Typed session boundary for Apply transaction route metadata."""

from __future__ import annotations

from typing import Any, MutableMapping

from inputs_application.policy_constants import DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY


class ApplyTransactionStore:
    APPLY_ACTION_KEY = "_inputs_action_apply_recommendation"
    APPLY_PAYLOAD_KEY = "_inputs_action_apply_recommendation_payload"
    PENDING_RECOMMENDATION_KEY = "pending_recommendation"
    APPLIED_RECOMMENDATION_KEY = "pending_recommendation_applied_id"
    SOLVER_RESULT_KEY = "_solver_result"
    EXPECTED_INPUT_REVISION_KEY = "_expected_input_revision"
    EXPECTED_PUBLICATION_REVISION_KEY = "_expected_publication_revision"
    EXPECTED_ENGINEERING_HASH_KEY = "_expected_engineering_hash"
    EXPECTED_PUBLICATION_AUTHORITY_HASH_KEY = (
        "_expected_publication_authority_hash"
    )

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def route(self) -> dict[str, Any]:
        value = self._state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY)
        return dict(value) if isinstance(value, dict) else {}

    def update_route(self, **fields: Any) -> dict[str, Any]:
        route = self.route()
        route.update(fields)
        self._state[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = route
        return route

    def consume_request(self, trace_key: str) -> bool:
        """Consume the one-shot Apply action while preserving queued payload fallback."""
        queued = bool(self._state.pop(self.APPLY_ACTION_KEY, False))
        if queued:
            return True
        return bool(
            self._state.get(trace_key)
            and self._state.get(self.APPLY_PAYLOAD_KEY)
        )

    def recommendation(self) -> dict[str, Any] | None:
        for key in (self.PENDING_RECOMMENDATION_KEY, self.APPLY_PAYLOAD_KEY):
            value = self._state.get(key)
            if isinstance(value, dict) and value:
                return dict(value)
        return None

    def clear_payload(self) -> None:
        self._state.pop(self.APPLY_PAYLOAD_KEY, None)

    def attach_revision_expectation(
        self,
        payload: dict[str, Any],
        *,
        input_revision: int,
        publication_revision: int,
        engineering_hash: str,
        publication_authority_hash: str,
    ) -> dict[str, Any]:
        revisioned = dict(payload)
        revisioned[self.EXPECTED_INPUT_REVISION_KEY] = int(input_revision)
        revisioned[self.EXPECTED_PUBLICATION_REVISION_KEY] = int(
            publication_revision
        )
        revisioned[self.EXPECTED_ENGINEERING_HASH_KEY] = str(engineering_hash)
        revisioned[self.EXPECTED_PUBLICATION_AUTHORITY_HASH_KEY] = str(
            publication_authority_hash
        )
        return revisioned

    def validate_revision_expectation(
        self,
        payload: dict[str, Any],
        *,
        input_revision: int,
        publication_revision: int | None,
        engineering_hash: str | None,
        publication_authority_hash: str | None,
    ) -> tuple[bool, str]:
        expected_keys = (
            self.EXPECTED_INPUT_REVISION_KEY,
            self.EXPECTED_PUBLICATION_REVISION_KEY,
            self.EXPECTED_ENGINEERING_HASH_KEY,
            self.EXPECTED_PUBLICATION_AUTHORITY_HASH_KEY,
        )
        if not any(key in payload for key in expected_keys):
            return True, "unrevisioned_compatibility_payload"
        if not all(key in payload for key in expected_keys):
            return False, "incomplete_apply_revision_expectation"
        if int(payload[self.EXPECTED_INPUT_REVISION_KEY]) != int(input_revision):
            return False, "stale_apply_input_revision"
        if publication_revision is None or int(
            payload[self.EXPECTED_PUBLICATION_REVISION_KEY]
        ) != int(publication_revision):
            return False, "stale_apply_publication_revision"
        if str(payload[self.EXPECTED_ENGINEERING_HASH_KEY]) != str(
            engineering_hash or ""
        ):
            return False, "stale_apply_engineering_hash"
        if str(payload[self.EXPECTED_PUBLICATION_AUTHORITY_HASH_KEY]) != str(
            publication_authority_hash or ""
        ):
            return False, "stale_apply_publication_authority_hash"
        return True, "apply_revision_expectation_match"

    def mark_dispatched(self, recommendation_id: Any) -> None:
        self._state[self.APPLIED_RECOMMENDATION_KEY] = recommendation_id
        self._state[self.PENDING_RECOMMENDATION_KEY] = None
        self.clear_payload()
        self._state[self.SOLVER_RESULT_KEY] = None

    def mark_committed(self, recommendation_id: Any) -> None:
        self._state["inputs_dirty"] = True
        self._state["_inputs_dirty"] = True
        self._state["run_design_clicked"] = True
        self._state[self.APPLIED_RECOMMENDATION_KEY] = recommendation_id
        self._state[self.PENDING_RECOMMENDATION_KEY] = None
        self.clear_payload()
        self._state[self.SOLVER_RESULT_KEY] = None


__all__ = ["ApplyTransactionStore"]
