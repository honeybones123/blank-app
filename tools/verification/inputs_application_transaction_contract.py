from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application import (
    InputsApplicationPorts,
    InputsApplyCommand,
    InputsEngineeringResult,
    InputsPageRequest,
    InputsPublicationResult,
    InputsSessionMutation,
    run_inputs_transaction,
)


@dataclass
class FakeEngineering:
    calls: list[bool] = field(default_factory=list)

    def evaluate(self, engineering_state, *, force_recompute=False):
        self.calls.append(bool(force_recompute))
        util = float(engineering_state.get("util", 1.2))
        return InputsEngineeringResult(
            engineering_hash=f"util:{util}",
            overview={"worst_util": util, "any_fail": util > 1.0},
        )


@dataclass
class FakeDesignGuide:
    outcomes: list[str] = field(default_factory=list)

    def publish(self, request, engineering):
        util = float(engineering.overview["worst_util"])
        outcome = "ACTION" if util > 1.0 else "PASS"
        self.outcomes.append(outcome)
        return InputsPublicationResult(
            publication_hash=f"{engineering.engineering_hash}:{outcome}",
            outcome=outcome,
            family_id="BENDING_FAIL_GOVERNS" if outcome == "ACTION" else None,
            cta={"enabled": outcome == "ACTION"},
        )


class FakeApply:
    def execute(self, command, *, publication):
        assert publication.outcome == "ACTION"
        return InputsSessionMutation(updates={"util": 0.9}, rerun_required=True)


class FakeFailedApply:
    def execute(self, command, *, publication):
        return InputsSessionMutation(status="failed", reason="blocked")


@dataclass
class FakeSession:
    commits: list[InputsSessionMutation] = field(default_factory=list)

    def commit(self, mutation):
        self.commits.append(mutation)


def main() -> int:
    engineering = FakeEngineering()
    design_guide = FakeDesignGuide()
    session = FakeSession()
    result = run_inputs_transaction(
        InputsPageRequest(
            engineering_state={"util": 1.2},
            apply_command=InputsApplyCommand(
                recommendation_id="candidate-1",
                payload={"updates": {"util": 0.9}},
            ),
        ),
        ports=InputsApplicationPorts(
            engineering=engineering,
            design_guide=design_guide,
            apply=FakeApply(),
            session=session,
        ),
    )
    assert result.engineering.engineering_hash == "util:0.9"
    assert result.publication.outcome == "PASS"
    assert result.publication.cta["enabled"] is False
    assert result.apply_status == "rerun_required"
    assert engineering.calls == [False, True]
    assert design_guide.outcomes == ["ACTION", "PASS"]
    assert len(session.commits) == 1
    assert result.transaction_trace == (
        "engineering.evaluate",
        "design_guide.publish",
        "apply.execute",
        "session.commit",
        "engineering.evaluate_post_apply",
        "design_guide.publish_post_apply",
    )
    failed_engineering = FakeEngineering()
    failed_design_guide = FakeDesignGuide()
    failed_session = FakeSession()
    failed = run_inputs_transaction(
        InputsPageRequest(
            engineering_state={"util": 1.2},
            apply_command=InputsApplyCommand(recommendation_id="blocked-1"),
        ),
        ports=InputsApplicationPorts(
            engineering=failed_engineering,
            design_guide=failed_design_guide,
            apply=FakeFailedApply(),
            session=failed_session,
        ),
    )
    assert failed.apply_status == "failed"
    assert failed_engineering.calls == [False]
    assert failed_design_guide.outcomes == ["ACTION"]
    assert len(failed_session.commits) == 1
    assert failed.transaction_trace == (
        "engineering.evaluate",
        "design_guide.publish",
        "apply.execute",
        "session.commit",
    )
    print("inputs_application transaction contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
