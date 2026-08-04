"""Focused contract for atomic Design Guide fragment publication replacement."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.authority import (
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)
from inputs_application.design_guide_fragment_store import (
    DesignGuideFragmentStore,
)


def _result(*, width: float, title: str):
    snapshot = EngineeringInputSnapshot(geometry={"b": width})
    return build_authoritative_design_result(
        engineering_snapshot=snapshot,
        final_publication={"display": {"title": title}},
    )


def main() -> int:
    session: dict = {}
    store = DesignGuideFragmentStore(session)
    first = store.publish(_result(width=300.0, title="First"))
    refreshing = store.begin_refresh(workspace_revision=2)
    failed = store.fail_refresh(RuntimeError("refresh failed"))
    store.begin_refresh(workspace_revision=3)
    second = store.publish(_result(width=350.0, title="Second"))
    checks = {
        "first_publication_is_ready": first.status == "ready",
        "refresh_preserves_last_publication": (
            refreshing.active_publication == first.active_publication
        ),
        "refresh_records_pending_revision": (
            refreshing.pending_workspace_revision == 2
        ),
        "failure_preserves_last_publication": (
            failed.status == "ready_stale"
            and failed.active_publication == first.active_publication
        ),
        "failure_is_recorded": "refresh failed" in str(failed.last_error),
        "success_atomically_replaces_publication": (
            second.status == "ready"
            and second.active_publication != first.active_publication
            and second.active_engineering_hash != first.active_engineering_hash
        ),
        "ready_state_has_no_pending_revision": (
            second.pending_workspace_revision is None
        ),
    }
    payload = {
        "schema": "inputs_design_guide_fragment_lifecycle_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
