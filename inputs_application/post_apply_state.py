"""Durable, fingerprint-bound handoff for post-Apply publication policy."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from inputs_application.local_cleanup_acceptance import (
    build_local_cleanup_acceptance_fingerprint,
)
from inputs_application.local_cleanup_acceptance import (
    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS,
)
from inputs_application.post_apply_acceptance_store import PostApplyAcceptanceStore


TYPED_POST_APPLY_ACCEPTANCE_FP_KEY = PostApplyAcceptanceStore.LEASE_KEY
POST_CLEANUP_ACCEPTANCE_FP_KEY = PostApplyAcceptanceStore.FINGERPRINT_KEY
POST_CLEANUP_ACCEPTANCE_ENABLED_KEY = PostApplyAcceptanceStore.ENABLED_KEY


def store_typed_post_apply_acceptance(
    session_state: MutableMapping[str, Any],
    state: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    fingerprint = build_local_cleanup_acceptance_fingerprint(state)
    PostApplyAcceptanceStore(session_state).store(fingerprint)
    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add(fingerprint)
    return fingerprint


def rehydrate_typed_post_apply_acceptance(
    session_state: MutableMapping[str, Any],
    state: Mapping[str, Any],
) -> bool:
    store = PostApplyAcceptanceStore(session_state)
    expected = store.expected()
    current = build_local_cleanup_acceptance_fingerprint(state)
    expected_map = dict(expected or ())
    current_map = dict(current)
    mismatches = {
        key: {"expected": expected_map.get(key), "current": current_map.get(key)}
        for key in sorted(set(expected_map).union(current_map))
        if expected_map.get(key) != current_map.get(key)
    }
    store.record_probe(expected=expected, current=current, mismatches=mismatches)
    if expected is None:
        store.clear_lease()
        return False
    store.enable(expected)
    DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS.add(expected)
    if expected != current:
        return False
    return True


__all__ = [
    "TYPED_POST_APPLY_ACCEPTANCE_FP_KEY",
    "rehydrate_typed_post_apply_acceptance",
    "store_typed_post_apply_acceptance",
]
