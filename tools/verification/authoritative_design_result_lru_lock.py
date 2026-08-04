"""Lock bounded cross-fingerprint reuse of authoritative Design Brain results."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from application.design_result_store import (
        AUTHORITATIVE_DESIGN_RESULT_LRU_KEY,
        AuthoritativeDesignResultStore,
    )
    from application.design_run_coordinator import ensure_design_result
    from design_brain.authority import (
        EngineeringInputSnapshot,
        build_authoritative_design_result,
    )

    session: dict = {}
    calls: list[str] = []

    def compute(snapshot: EngineeringInputSnapshot):
        calls.append(snapshot.engineering_hash)
        return build_authoritative_design_result(
            engineering_snapshot=snapshot,
            governing_family="test",
            family_outcome="PASS",
        )

    snapshot_a = EngineeringInputSnapshot(geometry={"b": 300})
    snapshot_b = EngineeringInputSnapshot(geometry={"b": 310})
    result_a = ensure_design_result(
        session_state=session,
        snapshot=snapshot_a,
        compute_fn=compute,
    )
    result_b = ensure_design_result(
        session_state=session,
        snapshot=snapshot_b,
        compute_fn=compute,
    )
    revisited_a = ensure_design_result(
        session_state=session,
        snapshot=snapshot_a,
        compute_fn=compute,
    )
    assert calls == [
        snapshot_a.engineering_hash,
        snapshot_b.engineering_hash,
    ]
    assert revisited_a is result_a
    assert revisited_a is not result_b
    decision = session[
        AuthoritativeDesignResultStore(session).decision_key
    ]
    assert decision["reused"] is True
    assert decision["reason"] == "engineering_hash_lru_hit"
    assert len(session[AUTHORITATIVE_DESIGN_RESULT_LRU_KEY]) == 2

    forced_a = ensure_design_result(
        session_state=session,
        snapshot=snapshot_a,
        compute_fn=compute,
        force=True,
    )
    assert len(calls) == 3
    assert forced_a is not revisited_a

    small_session: dict = {}
    small_store = AuthoritativeDesignResultStore(
        small_session,
        lru_max_entries=2,
    )
    for width in (300, 310, 320):
        snapshot = EngineeringInputSnapshot(geometry={"b": width})
        small_store.store(
            build_authoritative_design_result(
                engineering_snapshot=snapshot,
            )
        )
    cache = small_session[AUTHORITATIVE_DESIGN_RESULT_LRU_KEY]
    assert len(cache) == 2
    assert snapshot_a.engineering_hash not in cache
    print(
        "PASS: authoritative results reuse identical historical engineering "
        "hashes, forced runs recompute, and the LRU remains bounded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
