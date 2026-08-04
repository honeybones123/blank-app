"""Parity lock for pending recommendation envelope interpretation."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page_app_contract_bridge as legacy
from inputs_application.recommendation_envelope import (
    effective_apply_mode_and_payload,
    recommendation_blocked_reason,
    recommendation_commit_eligible,
    recommendation_envelope,
    recommendation_updates,
)


def main() -> int:
    cases = (
        None,
        {},
        {"updates": {"D": 650.0}},
        {"resolved_candidate": {"updates": {"b": 450.0}}},
        {"action_payload": {"resolved_candidate_updates": {"s_lig": 175.0}}},
        {"status": "failed"},
        {"meta": {"status": "blocked", "reason": "solver_exhausted"}},
        {
            "recommendation_envelope": {
                "status": "rejected",
                "commit_eligible": False,
                "blocked_reason": None,
            }
        },
    )
    for case in cases:
        assert recommendation_updates(case) == legacy._recommendation_updates_for_envelope(case)
        assert recommendation_envelope(case) == legacy._recommendation_envelope_from_pending(case)
        assert recommendation_blocked_reason(case) == legacy._recommendation_blocked_reason(case)
        assert recommendation_commit_eligible(case) == legacy._recommendation_commit_eligible(case)
        assert effective_apply_mode_and_payload(case) == legacy._effective_apply_mode_and_payload_from_pending(case)
    print("PASS: Inputs recommendation envelope behavior matches the frozen legacy behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
