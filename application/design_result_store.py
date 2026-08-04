"""Session-owned authoritative Design Brain result store.

This module intentionally accepts a mutable mapping instead of importing
Streamlit. In production that mapping can be ``st.session_state``; in tests it
can be a plain dict. The store owns only result identity and reuse decisions.
It does not calculate, publish, render, mutate inputs, or execute Apply.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, MutableMapping

from design_brain.authority import AuthoritativeDesignResult


AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY = "authoritative_design_result"
AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY = "_authoritative_design_result_last_decision"
AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY = "_authoritative_design_result_input_revision"
AUTHORITATIVE_DESIGN_RESULT_LRU_KEY = "_authoritative_design_result_lru_v1"
AUTHORITATIVE_DESIGN_RESULT_LRU_MAX_ENTRIES = 8
_AUTHORITATIVE_RESULT_FIELD_NAMES = frozenset(
    field_info.name for field_info in fields(AuthoritativeDesignResult)
)


def _coerce_authoritative_design_result(
    value: Any,
) -> AuthoritativeDesignResult | None:
    """Rebind a valid pre-hot-reload result to the current dataclass identity."""

    if isinstance(value, AuthoritativeDesignResult):
        return value
    value_type = type(value)
    if (
        value_type.__module__ != AuthoritativeDesignResult.__module__
        or value_type.__name__ != AuthoritativeDesignResult.__name__
    ):
        return None
    to_dict = getattr(value, "to_dict", None)
    if not callable(to_dict):
        return None
    try:
        payload = to_dict()
        if not isinstance(payload, dict):
            return None
        rebound = AuthoritativeDesignResult(
            **{
                key: payload[key]
                for key in _AUTHORITATIVE_RESULT_FIELD_NAMES
                if key in payload
            }
        )
    except (KeyError, TypeError, ValueError):
        return None
    return rebound


@dataclass(frozen=True)
class DesignResultReuseDecision:
    """Pure decision record for whether a stored result can be reused."""

    reused: bool
    reason: str
    requested_engineering_hash: str
    stored_engineering_hash: str | None = None
    forced: bool = False
    result_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EngineeringResultStore:
    """Session adapter for the immutable engineering/Design Brain result."""

    def __init__(
        self,
        session_state: MutableMapping[str, Any],
        *,
        result_key: str = AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY,
        decision_key: str = AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY,
        lru_key: str = AUTHORITATIVE_DESIGN_RESULT_LRU_KEY,
        lru_max_entries: int = AUTHORITATIVE_DESIGN_RESULT_LRU_MAX_ENTRIES,
    ) -> None:
        self._session_state = session_state
        self._result_key = str(result_key)
        self._decision_key = str(decision_key)
        self._lru_key = str(lru_key)
        self._lru_max_entries = max(1, int(lru_max_entries))

    @property
    def result_key(self) -> str:
        return self._result_key

    @property
    def decision_key(self) -> str:
        return self._decision_key

    def current(self) -> AuthoritativeDesignResult | None:
        result = self._session_state.get(self._result_key)
        normalized = _coerce_authoritative_design_result(result)
        if normalized is not None and normalized is not result:
            self._session_state[self._result_key] = normalized
        return normalized

    def store(
        self,
        result: AuthoritativeDesignResult,
        *,
        source_input_revision: int | None = None,
    ) -> AuthoritativeDesignResult:
        normalized = _coerce_authoritative_design_result(result)
        if normalized is None:
            raise TypeError("result must be an AuthoritativeDesignResult")
        self._session_state[self._result_key] = normalized
        if source_input_revision is not None:
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY] = int(
                source_input_revision
            )
        self._remember(normalized)
        return normalized

    def source_input_revision(self) -> int | None:
        value = self._session_state.get(AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY)
        return int(value) if value is not None else None

    def bind_revision(
        self,
        source_input_revision: int,
        *,
        engineering_hash: str,
    ) -> None:
        current = self.current()
        if current is None or current.engineering_hash != str(engineering_hash or ""):
            raise ValueError("cannot bind an input revision to a different engineering result")
        self._session_state[AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY] = int(
            source_input_revision
        )

    def clear(self) -> None:
        self._session_state.pop(self._result_key, None)
        self._session_state.pop(self._lru_key, None)
        self._session_state.pop(AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY, None)

    def can_reuse(self, engineering_hash: str, *, force: bool = False) -> DesignResultReuseDecision:
        requested_hash = str(engineering_hash or "")
        result = self.current()
        stored_hash = result.engineering_hash if result is not None else None
        if result is not None:
            self._remember(result)
        if force:
            return self._record_decision(
                DesignResultReuseDecision(
                    reused=False,
                    reason="force_recompute",
                    requested_engineering_hash=requested_hash,
                    stored_engineering_hash=stored_hash,
                    forced=True,
                    result_present=result is not None,
                )
            )
        if result is None:
            cached = self._cached_result(requested_hash)
            if cached is not None:
                self._session_state[self._result_key] = cached
                return self._record_decision(
                    DesignResultReuseDecision(
                        reused=True,
                        reason="engineering_hash_lru_hit",
                        requested_engineering_hash=requested_hash,
                        stored_engineering_hash=cached.engineering_hash,
                        result_present=True,
                    )
                )
            return self._record_decision(
                DesignResultReuseDecision(
                    reused=False,
                    reason="missing_authoritative_result",
                    requested_engineering_hash=requested_hash,
                    stored_engineering_hash=None,
                    result_present=False,
                )
            )
        if stored_hash != requested_hash:
            cached = self._cached_result(requested_hash)
            if cached is not None:
                self._session_state[self._result_key] = cached
                return self._record_decision(
                    DesignResultReuseDecision(
                        reused=True,
                        reason="engineering_hash_lru_hit",
                        requested_engineering_hash=requested_hash,
                        stored_engineering_hash=cached.engineering_hash,
                        result_present=True,
                    )
                )
            return self._record_decision(
                DesignResultReuseDecision(
                    reused=False,
                    reason="engineering_hash_changed",
                    requested_engineering_hash=requested_hash,
                    stored_engineering_hash=stored_hash,
                    result_present=True,
                )
            )
        return self._record_decision(
            DesignResultReuseDecision(
                reused=True,
                reason="engineering_hash_match",
                requested_engineering_hash=requested_hash,
                stored_engineering_hash=stored_hash,
                result_present=True,
            )
        )

    def _cache(self) -> dict[str, AuthoritativeDesignResult]:
        raw = self._session_state.get(self._lru_key)
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, AuthoritativeDesignResult] = {}
        for key, value in raw.items():
            result = _coerce_authoritative_design_result(value)
            if result is not None and str(key) == result.engineering_hash:
                normalized[str(key)] = result
        return normalized

    def _remember(self, result: AuthoritativeDesignResult) -> None:
        cache = self._cache()
        cache.pop(result.engineering_hash, None)
        cache[result.engineering_hash] = result
        while len(cache) > self._lru_max_entries:
            oldest = next(iter(cache))
            cache.pop(oldest, None)
        self._session_state[self._lru_key] = cache

    def _cached_result(
        self,
        engineering_hash: str,
    ) -> AuthoritativeDesignResult | None:
        requested_hash = str(engineering_hash or "")
        cache = self._cache()
        result = cache.pop(requested_hash, None)
        if result is None:
            return None
        cache[requested_hash] = result
        self._session_state[self._lru_key] = cache
        return result

    def _record_decision(self, decision: DesignResultReuseDecision) -> DesignResultReuseDecision:
        self._session_state[self._decision_key] = decision.to_dict()
        return decision


# Transitional import compatibility only. The legacy name is an alias, not a
# second store or a second session key.
AuthoritativeDesignResultStore = EngineeringResultStore


__all__ = [
    "AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_LRU_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY",
    "AuthoritativeDesignResultStore",
    "DesignResultReuseDecision",
    "EngineeringResultStore",
]
