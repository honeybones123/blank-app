"""Contract checks for the independently owned canonical Apply planner."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application import (
    CanonicalRecommendationApplyPort,
    InputsApplyCommand,
    InputsPublicationResult,
)


def _publication(*, actionable: bool = True) -> InputsPublicationResult:
    return InputsPublicationResult(
        publication_hash="pub-1",
        outcome="ACTION" if actionable else "PASS",
        family_id="BENDING_FAIL_GOVERNS",
        cta={"enabled": actionable},
    )


def main() -> int:
    port = CanonicalRecommendationApplyPort()
    resolved = port.execute(
        InputsApplyCommand(
            recommendation_id="candidate-1",
            payload={
                "status": "ready",
                "resolved_candidate": {
                    "candidate_id": "candidate-1",
                    "updates": {"D": 650.0, "_private": "drop", "not_shared": 1},
                },
            },
        ),
        publication=_publication(),
    )
    assert dict(resolved.updates) == {"D": 650.0}
    assert resolved.status == "rerun_required"
    assert resolved.rerun_required is True
    assert resolved.reason == "canonical_apply_planned:apply_resolved_candidate"

    direct = port.execute(
        InputsApplyCommand(
            recommendation_id="candidate-2",
            payload={"updates": {"lig_d": 12.0, "lig_legs": 4, "s_lig": 175.0}},
        ),
        publication=_publication(),
    )
    assert dict(direct.updates) == {"lig_d": 12.0, "lig_legs": 4, "s_lig": 175.0}

    blocked = port.execute(
        InputsApplyCommand(
            recommendation_id="candidate-3",
            payload={"status": "blocked", "blocked_reason": "solver_exhausted"},
        ),
        publication=_publication(),
    )
    assert blocked.status == "failed"
    assert blocked.reason == "solver_exhausted"

    stale = port.execute(
        InputsApplyCommand(
            recommendation_id="candidate-4",
            payload={"updates": {"D": 700.0}},
        ),
        publication=_publication(actionable=False),
    )
    assert stale.status == "failed"
    assert stale.reason == "authoritative_publication_not_actionable"
    print("inputs_application canonical Apply port contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
