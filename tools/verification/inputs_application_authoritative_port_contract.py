from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.authority import build_authoritative_design_result  # noqa: E402
from inputs_application import (  # noqa: E402
    AuthoritativeDesignGuidePort,
    InputsEngineeringResult,
    InputsPageRequest,
    ResolvedStateEngineeringPort,
)


def main() -> int:
    compute_calls: list[str] = []

    def engineering_evaluator(snapshot, force):
        return InputsEngineeringResult(
            engineering_hash=snapshot.engineering_hash,
            overview={"worst_util": 1.1, "any_fail": True},
        )

    engineering_port = ResolvedStateEngineeringPort(evaluator=engineering_evaluator)
    engineering = engineering_port.evaluate({"b": 300.0, "D": 500.0, "fc": 40.0})

    def compute(snapshot):
        compute_calls.append(snapshot.engineering_hash)
        return build_authoritative_design_result(
            engineering_snapshot=snapshot,
            governing_family="BENDING_FAIL_GOVERNS",
            family_outcome="ACTION",
            final_publication={
                "final_design_guide_publication": {
                    "publication_hash": "publication-1",
                    "outcome_state": "ACTION",
                    "selected_family": "BENDING_FAIL_GOVERNS",
                    "cta": {"enabled": True, "candidate_id": "candidate-1"},
                }
            },
            cta_model={"enabled": True, "candidate_id": "candidate-1"},
        )

    session: dict = {}
    port = AuthoritativeDesignGuidePort(session_state=session, compute=compute)
    request = InputsPageRequest(engineering_state={"b": 300.0, "D": 500.0, "fc": 40.0})
    first = port.publish(request, engineering)
    second = port.publish(request, engineering)
    assert first == second
    assert first.publication_hash == "publication-1"
    assert first.outcome == "ACTION"
    assert first.family_id == "BENDING_FAIL_GOVERNS"
    assert first.cta["enabled"] is True
    assert compute_calls == [engineering.engineering_hash]
    print("inputs_application authoritative Design Guide port contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
