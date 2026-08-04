"""Pure session store for fingerprinted recommendation cache entries."""

from __future__ import annotations

from typing import Any, MutableMapping


class RecommendationStore:
    PREFIX = "_recommendation_cache_"
    EVALUATION_CACHE_KEY = "_global_eval_cache"
    EVALUATION_CACHE_FP_KEY = "_global_eval_cache_fp"

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    @classmethod
    def key_for(cls, cache_name: str) -> str:
        return f"{cls.PREFIX}{cache_name}"

    def get(self, cache_name: str, *, fingerprint: str) -> dict[str, Any] | None:
        entry = self._state.get(self.key_for(cache_name))
        if isinstance(entry, dict) and entry.get("fingerprint") == fingerprint:
            return dict(entry)
        return None

    def put(
        self,
        cache_name: str,
        *,
        fingerprint: str,
        recommendation: dict[str, Any] | None,
    ) -> None:
        self._state[self.key_for(cache_name)] = {
            "fingerprint": fingerprint,
            "recommendation": recommendation,
        }

    def clear_all(self) -> list[str]:
        removed: list[str] = []
        for key in list(self._state.keys()):
            if str(key).startswith(self.PREFIX):
                removed.append(str(key))
                self._state.pop(key, None)
        return removed

    def evaluation_cache(self, *, enabled: bool) -> dict[str, Any]:
        if not enabled:
            return {}
        value = self._state.get(self.EVALUATION_CACHE_KEY)
        return value if isinstance(value, dict) else {}

    def reset_evaluation_cache(self, *, fingerprint: str) -> None:
        if self._state.get(self.EVALUATION_CACHE_FP_KEY) != fingerprint:
            self._state[self.EVALUATION_CACHE_KEY] = {}
            self._state[self.EVALUATION_CACHE_FP_KEY] = fingerprint


__all__ = ["RecommendationStore"]
