"""Contract checks for fingerprint-bound post-Apply state handoff."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.post_apply_state import (
    POST_CLEANUP_ACCEPTANCE_ENABLED_KEY,
    POST_CLEANUP_ACCEPTANCE_FP_KEY,
    TYPED_POST_APPLY_ACCEPTANCE_FP_KEY,
    rehydrate_typed_post_apply_acceptance,
    store_typed_post_apply_acceptance,
)


def main() -> int:
    session = {}
    state = {"b": 350.0, "D": 470.0, "bot1_count": 2, "db_bot_1": 28}
    fingerprint = store_typed_post_apply_acceptance(session, state)
    session.pop(POST_CLEANUP_ACCEPTANCE_ENABLED_KEY)
    session.pop(POST_CLEANUP_ACCEPTANCE_FP_KEY)
    assert rehydrate_typed_post_apply_acceptance(session, state) is True
    assert session[POST_CLEANUP_ACCEPTANCE_ENABLED_KEY] is True
    assert session[POST_CLEANUP_ACCEPTANCE_FP_KEY] == fingerprint

    changed = {**state, "D": 480.0}
    session.pop(POST_CLEANUP_ACCEPTANCE_ENABLED_KEY)
    session.pop(POST_CLEANUP_ACCEPTANCE_FP_KEY)
    assert rehydrate_typed_post_apply_acceptance(session, changed) is False
    assert TYPED_POST_APPLY_ACCEPTANCE_FP_KEY in session
    assert session[POST_CLEANUP_ACCEPTANCE_ENABLED_KEY] is True
    assert session[POST_CLEANUP_ACCEPTANCE_FP_KEY] == fingerprint
    for _ in range(4):
        assert rehydrate_typed_post_apply_acceptance(session, changed) is False
    assert TYPED_POST_APPLY_ACCEPTANCE_FP_KEY in session
    print("inputs_application post-Apply state contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
