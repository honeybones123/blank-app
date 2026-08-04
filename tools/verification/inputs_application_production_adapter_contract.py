from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application import (  # noqa: E402
    InputsEngineeringResult,
    InputsSessionMutation,
    MappingSessionPort,
    ResolvedStateEngineeringPort,
)


def main() -> int:
    calls: list[tuple[str, bool]] = []

    def evaluator(snapshot, force):
        calls.append((snapshot.engineering_hash, force))
        return InputsEngineeringResult(
            engineering_hash=snapshot.engineering_hash,
            overview={"worst_util": 0.91, "any_fail": False},
            checks={"bending": "PASS", "shear": "PASS"},
        )

    port = ResolvedStateEngineeringPort(
        evaluator=evaluator,
        contract_versions={"inputs_application": "v1"},
    )
    state = {"b": 300.0, "D": 500.0, "fc": 40.0, "uls_Mstar": 200.0}
    first = port.evaluate(state)
    second = port.evaluate({**state, "expanded_panels": ["summary"]}, force_recompute=True)
    assert first.engineering_hash == second.engineering_hash
    assert calls == [
        (first.engineering_hash, False),
        (first.engineering_hash, True),
    ]

    session = {"remove_me": 1, "keep_me": 2}
    session_port = MappingSessionPort(session)
    mutation = InputsSessionMutation(
        updates={"b": 350.0},
        removals=("remove_me",),
        rerun_required=True,
    )
    session_port.commit(mutation)
    assert session == {"keep_me": 2, "b": 350.0}
    assert session_port.committed == [mutation]
    print("inputs_application production adapter contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
