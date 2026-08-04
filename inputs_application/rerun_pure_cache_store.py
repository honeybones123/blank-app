"""Typed session boundary for rerun-scoped pure evaluation caches."""

from __future__ import annotations

import copy
from typing import Any, MutableMapping


class RerunPureCacheStore:
    KEY = "_rerun_pure_cache"

    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def reset(self) -> None:
        self._state[self.KEY] = {}

    def get(self, namespace: str, fingerprint: Any) -> Any:
        cache = self._state.get(self.KEY)
        scoped = cache.get(namespace) if isinstance(cache, dict) else None
        if not isinstance(scoped, dict):
            return None
        return copy.deepcopy(scoped.get(fingerprint))

    def set(self, namespace: str, fingerprint: Any, value: Any) -> None:
        cache = dict(self._state.get(self.KEY) or {})
        scoped = dict(cache.get(namespace) or {})
        scoped[fingerprint] = copy.deepcopy(value)
        cache[namespace] = scoped
        self._state[self.KEY] = cache


__all__ = ["RerunPureCacheStore"]
