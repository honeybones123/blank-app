"""Application-layer Design Brain run coordinator.

The coordinator decides only whether to reuse the session-owned authoritative
result or call the supplied pure compute function once. The compute function is
injected so this module stays independent of Streamlit and current product
rendering routes during the migration.
"""

from __future__ import annotations

from typing import Callable

from application.design_result_store import EngineeringResultStore
from design_brain.authority import AuthoritativeDesignResult, EngineeringInputSnapshot


DesignBrainComputeFn = Callable[[EngineeringInputSnapshot], AuthoritativeDesignResult]


def ensure_design_result(
    *,
    result_store: EngineeringResultStore,
    snapshot: EngineeringInputSnapshot,
    compute_fn: DesignBrainComputeFn,
    force: bool = False,
    source_input_revision: int | None = None,
) -> AuthoritativeDesignResult:
    """Return the authoritative result for ``snapshot``.

    Same-hash reruns return the exact stored result object. A miss or forced
    run calls ``compute_fn`` once, validates that it produced a result for the
    requested engineering hash, stores it, and returns it.
    """

    if not isinstance(snapshot, EngineeringInputSnapshot):
        raise TypeError("snapshot must be an EngineeringInputSnapshot")
    if not isinstance(result_store, EngineeringResultStore):
        raise TypeError("result_store must be an EngineeringResultStore")
    decision = result_store.can_reuse(snapshot.engineering_hash, force=force)
    if decision.reused:
        current = result_store.current()
        if current is None:
            raise RuntimeError("reuse decision had no stored result")
        if source_input_revision is not None:
            result_store.bind_revision(
                source_input_revision,
                engineering_hash=current.engineering_hash,
            )
        return current

    result = compute_fn(snapshot)
    if not isinstance(result, AuthoritativeDesignResult):
        raise TypeError("compute_fn must return an AuthoritativeDesignResult")
    if result.engineering_hash != snapshot.engineering_hash:
        raise ValueError(
            "computed AuthoritativeDesignResult engineering_hash does not match requested snapshot"
        )
    return result_store.store(
        result,
        source_input_revision=source_input_revision,
    )
