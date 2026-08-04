"""Focused contract for the explicit Inputs draft-to-commit boundary."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.engineering_input_store import (
    COMMITTED_STATE_KEY,
    DRAFT_STATE_KEY,
    EngineeringInputStore,
)


def main() -> int:
    session: dict = {}
    store = EngineeringInputStore(session)
    draft = store.capture_draft(
        {"b": 300.0, "D": 600.0, "fc": 32.0},
        changed_keys=("D",),
        source="contract",
    )
    first = store.commit_draft(source="contract")
    second = store.commit_draft(source="contract_reuse")
    store.capture_draft(
        {**draft, "D": 625.0},
        changed_keys=("D",),
        source="contract_edit",
    )
    third = store.commit_draft(source="contract_edit")
    checks = {
        "draft_record_is_explicit": DRAFT_STATE_KEY in session,
        "committed_record_is_explicit": COMMITTED_STATE_KEY in session,
        "draft_and_committed_are_distinct_objects": (
            session[DRAFT_STATE_KEY] is not session[COMMITTED_STATE_KEY]
        ),
        "draft_hash_matches_committed_hash": (
            first.draft_hash == first.committed_hash
        ),
        "unchanged_commit_reuses_revision": second.revision == first.revision,
        "changed_commit_advances_revision_once": third.revision == first.revision + 1,
        "changed_key_is_recorded": third.changed_keys == ("D",),
        "committed_state_is_latest": store.committed()["D"] == 625.0,
    }
    payload = {
        "schema": "inputs_engineering_draft_commit_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
