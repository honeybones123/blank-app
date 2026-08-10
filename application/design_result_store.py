"""Session-owned authoritative Design Brain result store.

This module intentionally accepts a mutable mapping instead of importing
Streamlit. In production that mapping can be ``st.session_state``; in tests it
can be a plain dict. The store owns only result identity and reuse decisions.
It does not calculate, publish, render, mutate inputs, or execute Apply.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, MutableMapping

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    coerce_authoritative_design_result,
)
from application.contracts.design_branch import DesignBranch
from inputs_application.design_branch_store import BeamDesignBranchStore


AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY = "authoritative_design_result"
AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY = "_authoritative_design_result_last_decision"
AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY = "_authoritative_design_result_input_revision"
AUTHORITATIVE_DESIGN_RESULT_LRU_KEY = "_authoritative_design_result_lru_v1"
AUTHORITATIVE_DESIGN_RESULT_LRU_MAX_ENTRIES = 8
AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY = "_authoritative_design_result_by_branch_v2"
AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY = (
    "_authoritative_design_result_input_revision_by_branch_v2"
)
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
        beam_id: str | None = None,
        design_branch: DesignBranch | str | None = None,
    ) -> None:
        self._session_state = session_state
        self._result_key = str(result_key)
        self._decision_key = str(decision_key)
        self._lru_key = str(lru_key)
        self._lru_max_entries = max(1, int(lru_max_entries))
        self._bound_beam_id = str(beam_id or "").strip()
        self._bound_design_branch = (
            DesignBranch(design_branch) if design_branch is not None else None
        )

    @property
    def result_key(self) -> str:
        return self._result_key

    @property
    def decision_key(self) -> str:
        return self._decision_key

    def _identity(self) -> tuple[str, DesignBranch]:
        if self._bound_beam_id and self._bound_design_branch is not None:
            return self._bound_beam_id, self._bound_design_branch
        beam_id = str(self._session_state.get("active_beam_id") or "").strip()
        if not beam_id:
            return "", DesignBranch.BEAM_INPUTS
        branch = BeamDesignBranchStore(self._session_state).active_context(
            beam_id,
            page_slug=str(
                self._session_state.get("_active_page_slug")
                or self._session_state.get("page_slug")
                or "inputs"
            ),
        )
        return beam_id, branch

    @staticmethod
    def _branch_key(beam_id: str, branch: DesignBranch) -> str:
        return f"{beam_id}:{branch.value}"

    def _is_projected_identity(self, beam_id: str, branch: DesignBranch) -> bool:
        active_beam_id = str(
            self._session_state.get("active_beam_id") or ""
        ).strip()
        if active_beam_id != beam_id:
            return False
        projected_branch = BeamDesignBranchStore(self._session_state).active_context(
            active_beam_id,
            page_slug=str(
                self._session_state.get("_active_page_slug")
                or self._session_state.get("page_slug")
                or "inputs"
            ),
        )
        return projected_branch is branch

    def current(self) -> AuthoritativeDesignResult | None:
        beam_id, branch = self._identity()
        by_branch = self._session_state.get(AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY)
        if isinstance(by_branch, dict):
            # Once branch storage exists, a missing branch result is genuinely
            # missing. Falling back to the last projected single result here
            # leaked the other branch's engineering result after navigation.
            result = (
                by_branch.get(self._branch_key(beam_id, branch))
                if beam_id
                else None
            )
        else:
            # One-time pre-cutover compatibility read. ``store`` immediately
            # moves a subsequently produced result into the branch map.
            result = self._session_state.get(self._result_key)
        normalized = coerce_authoritative_design_result(result)
        if normalized is not None and normalized is not result:
            if beam_id:
                normalized_map = dict(by_branch or {})
                normalized_map[self._branch_key(beam_id, branch)] = normalized
                self._session_state[AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY] = normalized_map
            self._session_state[self._result_key] = normalized
        return normalized

    def project_current_branch(self) -> AuthoritativeDesignResult | None:
        """Project the selected branch into the retired single-result key.

        The key remains a read-only compatibility view for unmigrated display
        consumers. It is never used as a fallback when the branch map exists.
        """

        result = self.current()
        if result is None:
            self._session_state.pop(self._result_key, None)
            self._session_state.pop(AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY, None)
            return None
        self._session_state[self._result_key] = result
        revision = self.source_input_revision()
        if revision is not None:
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY] = revision
        return result

    def store(
        self,
        result: AuthoritativeDesignResult,
        *,
        source_input_revision: int | None = None,
    ) -> AuthoritativeDesignResult:
        normalized = coerce_authoritative_design_result(result)
        if normalized is None:
            raise TypeError("result must be an AuthoritativeDesignResult")
        beam_id, branch = self._identity()
        if beam_id:
            by_branch = dict(
                self._session_state.get(AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY) or {}
            )
            by_branch[self._branch_key(beam_id, branch)] = normalized
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY] = by_branch
        if not beam_id or self._is_projected_identity(beam_id, branch):
            self._session_state[self._result_key] = normalized
        if source_input_revision is not None:
            if not beam_id or self._is_projected_identity(beam_id, branch):
                self._session_state[AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY] = int(
                    source_input_revision
                )
            if beam_id:
                revisions = dict(
                    self._session_state.get(
                        AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY
                    )
                    or {}
                )
                revisions[self._branch_key(beam_id, branch)] = int(source_input_revision)
                self._session_state[
                    AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY
                ] = revisions
        self._remember(normalized)
        return normalized

    def source_input_revision(self) -> int | None:
        beam_id, branch = self._identity()
        revisions = self._session_state.get(
            AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY
        )
        if isinstance(revisions, dict) and beam_id:
            value = revisions.get(self._branch_key(beam_id, branch))
            if value is not None:
                return int(value)
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
        beam_id, branch = self._identity()
        if not beam_id or self._is_projected_identity(beam_id, branch):
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY] = int(
                source_input_revision
            )
        if beam_id:
            revisions = dict(
                self._session_state.get(
                    AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY
                )
                or {}
            )
            revisions[self._branch_key(beam_id, branch)] = int(source_input_revision)
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY] = revisions

    def clear(self) -> None:
        beam_id, branch = self._identity()
        if beam_id:
            key = self._branch_key(beam_id, branch)
            by_branch = dict(
                self._session_state.get(AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY) or {}
            )
            by_branch.pop(key, None)
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY] = by_branch
            revisions = dict(
                self._session_state.get(
                    AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY
                )
                or {}
            )
            revisions.pop(key, None)
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY] = revisions
        if not beam_id or self._is_projected_identity(beam_id, branch):
            self._session_state.pop(self._result_key, None)
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
                self._restore_cached_result(cached)
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
                self._restore_cached_result(cached)
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
            result = coerce_authoritative_design_result(value)
            if result is not None and str(key).endswith(
                f":{result.engineering_hash}"
            ):
                normalized[str(key)] = result
        return normalized

    def _remember(self, result: AuthoritativeDesignResult) -> None:
        cache = self._cache()
        beam_id, branch = self._identity()
        cache_key = f"{self._branch_key(beam_id, branch)}:{result.engineering_hash}"
        cache.pop(cache_key, None)
        cache[cache_key] = result
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
        beam_id, branch = self._identity()
        cache_key = f"{self._branch_key(beam_id, branch)}:{requested_hash}"
        result = cache.pop(cache_key, None)
        if result is None:
            return None
        cache[cache_key] = result
        self._session_state[self._lru_key] = cache
        return result

    def _restore_cached_result(self, result: AuthoritativeDesignResult) -> None:
        """Restore an LRU hit into the branch owner and its display projection."""

        beam_id, branch = self._identity()
        if beam_id:
            by_branch = dict(
                self._session_state.get(AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY)
                or {}
            )
            by_branch[self._branch_key(beam_id, branch)] = result
            self._session_state[AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY] = by_branch
        if not beam_id or self._is_projected_identity(beam_id, branch):
            self._session_state[self._result_key] = result

    def _record_decision(self, decision: DesignResultReuseDecision) -> DesignResultReuseDecision:
        self._session_state[self._decision_key] = decision.to_dict()
        return decision


# Transitional import compatibility only. The legacy name is an alias, not a
# second store or a second session key.
AuthoritativeDesignResultStore = EngineeringResultStore


__all__ = [
    "AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_BY_BRANCH_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_REVISION_BY_BRANCH_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_LRU_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_REVISION_KEY",
    "AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY",
    "AuthoritativeDesignResultStore",
    "DesignResultReuseDecision",
    "EngineeringResultStore",
]
