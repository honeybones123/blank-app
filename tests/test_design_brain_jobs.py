from __future__ import annotations

import time

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
)
from application.design_brain_jobs import (
    DesignBrainJobInput,
    DesignBrainJobManager,
    DesignBrainJobStatus,
)
from application.design_brain_port import DesignBrainExecution


def _job(revision: int, value: float = 1.0) -> DesignBrainJobInput:
    snapshot = EngineeringInputSnapshot(
        design_actions={"Mu*": value},
        geometry={"b": 250.0, "D": 300.0},
    )
    return DesignBrainJobInput(
        input_revision=revision,
        engineering_hash=snapshot.engineering_hash,
        engineering_snapshot=snapshot,
        resolved_inputs={"Mu*": value},
        engineering_calculations={"packs": {}},
    )


def _execution(request):
    return DesignBrainExecution(
        result=AuthoritativeDesignResult(
            engineering_hash=request.engineering_snapshot.engineering_hash,
            final_publication={"outcome_state": "ACTION"},
        ),
        input_revision=request.input_revision,
    )


def _wait(manager, job):
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        result = manager.get(
            input_revision=job.input_revision,
            engineering_hash=job.engineering_hash,
        )
        if result and result.status in {
            DesignBrainJobStatus.READY,
            DesignBrainJobStatus.FAILED,
            DesignBrainJobStatus.STALE,
        }:
            return result
        time.sleep(0.01)
    raise AssertionError("Design Brain job did not settle")


def test_manager_runs_immutable_revision_bound_job() -> None:
    manager = DesignBrainJobManager(_execution)
    try:
        job = _job(42)
        queued = manager.submit(job)
        result = _wait(manager, job)
        assert queued.status in {DesignBrainJobStatus.PENDING, DesignBrainJobStatus.RUNNING}
        assert result.status is DesignBrainJobStatus.READY
        assert result.execution is not None
        assert result.execution.input_revision == 42
        assert result.execution.result.engineering_hash == job.engineering_hash
    finally:
        manager.close()


def test_newer_revision_stales_older_running_job() -> None:
    started = []

    def slow_runner(request):
        started.append(request.input_revision)
        time.sleep(0.05)
        return _execution(request)

    manager = DesignBrainJobManager(slow_runner)
    try:
        old = _job(41)
        new = _job(42, value=2.0)
        manager.submit(old)
        manager.submit(new)
        old_result = manager.get(
            input_revision=old.input_revision,
            engineering_hash=old.engineering_hash,
        )
        assert old_result is not None
        assert old_result.status is DesignBrainJobStatus.STALE
        new_result = _wait(manager, new)
        assert new_result.status is DesignBrainJobStatus.READY
        assert started
    finally:
        manager.close()


def test_failed_job_isolated_from_streamlit_and_reported() -> None:
    def failing_runner(request):
        raise RuntimeError("brain failed")

    manager = DesignBrainJobManager(failing_runner)
    try:
        job = _job(7)
        manager.submit(job)
        result = _wait(manager, job)
        assert result.status is DesignBrainJobStatus.FAILED
        assert result.error and "brain failed" in result.error
    finally:
        manager.close()
