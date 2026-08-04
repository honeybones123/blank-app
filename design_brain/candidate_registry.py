"""Run-scoped candidate evaluation registry.

The registry owns only immutable-keyed evaluation results for one design run.
It deliberately has no Streamlit or session-state dependency and remains
dict-compatible for the transitional solver call graph.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any, Callable, TypeVar


T = TypeVar("T")


class CandidateEvaluationRegistry(MutableMapping[str, Any]):
    """Deduplicate candidate evaluations within one run only."""

    def __init__(self) -> None:
        self._results: dict[str, Any] = {}
        self._compute_count = 0
        self._cache_hit_count = 0

    def __getitem__(self, key: str) -> Any:
        return self._results[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self._results:
            self._compute_count += 1
        self._results[key] = value

    def __delitem__(self, key: str) -> None:
        del self._results[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._results)

    def __len__(self) -> int:
        return len(self._results)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._results:
            self._cache_hit_count += 1
            return self._results[key]
        return default

    def get_or_compute(self, key: str, compute: Callable[[], T]) -> T:
        """Return one result for ``key`` and compute it at most once."""

        if key in self._results:
            self._cache_hit_count += 1
            return self._results[key]
        value = compute()
        self[key] = value
        return value

    @property
    def compute_count(self) -> int:
        return self._compute_count

    @property
    def cache_hit_count(self) -> int:
        return self._cache_hit_count

    def snapshot(self) -> dict[str, Any]:
        """Return scalar registry evidence without exposing live candidates."""

        return {
            "unique_evaluations": len(self._results),
            "compute_count": self._compute_count,
            "cache_hit_count": self._cache_hit_count,
        }


__all__ = ["CandidateEvaluationRegistry"]
