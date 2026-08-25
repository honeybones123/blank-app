"""Immutable, process-local Design Brain jobs.

The worker boundary is deliberately independent of Streamlit.  Jobs carry a
defensive immutable request and return an immutable lifecycle record; page
code owns persistence and publication when it observes the completed result.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import StrEnum
import threading
import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
)
from application.design_brain_port import DesignBrainExecution, DesignBrainRequest


class DesignBrainJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


@dataclass(frozen=True)
class DesignBrainJobInput:
    input_revision: int
    engineering_hash: str
    engineering_snapshot: EngineeringInputSnapshot
    resolved_inputs: Mapping[str, Any]
    engineering_calculations: Mapping[str, Any]
    family_hint: str | None = None
    debug_enabled: bool = False
    request_id: str = ""

    def request(self) -> DesignBrainRequest:
        return DesignBrainRequest(
            engineering_snapshot=self.engineering_snapshot,
            resolved_inputs=dict(self.resolved_inputs),
            engineering_calculations=dict(self.engineering_calculations),
            family_hint=self.family_hint,
            debug_enabled=self.debug_enabled,
            input_revision=int(self.input_revision),
        )


@dataclass(frozen=True)
class DesignBrainJobResult:
    request_id: str
    input_revision: int
    engineering_hash: str
    status: DesignBrainJobStatus
    execution: DesignBrainExecution | None = None
    error: str | None = None
    queued_at_ns: int = 0
    started_at_ns: int | None = None
    finished_at_ns: int | None = None


Runner = Callable[[DesignBrainRequest], DesignBrainExecution]


@dataclass
class _JobRecord:
    job: DesignBrainJobInput
    result: DesignBrainJobResult
    future: Future[DesignBrainExecution] | None = None


class DesignBrainJobManager:
    """Single-worker manager that never imports or mutates Streamlit state."""

    def __init__(self, runner: Runner, *, max_workers: int = 1) -> None:
        if not callable(runner):
            raise TypeError("runner must be callable")
        if int(max_workers) != 1:
            raise ValueError("Design Brain uses exactly one worker")
        self._runner = runner
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="design-brain",
        )
        self._lock = threading.RLock()
        self._records: dict[tuple[int, str], _JobRecord] = {}
        self._latest_key: tuple[int, str] | None = None

    def submit(self, job: DesignBrainJobInput) -> DesignBrainJobResult:
        if not job.request_id:
            job = replace(job, request_id=f"dbg_{uuid4().hex}")
        key = (int(job.input_revision), str(job.engineering_hash))
        now = time.perf_counter_ns()
        with self._lock:
            existing = self._records.get(key)
            if existing is not None and existing.result.status in {
                DesignBrainJobStatus.PENDING,
                DesignBrainJobStatus.RUNNING,
                DesignBrainJobStatus.READY,
            }:
                return existing.result
            self._mark_older_jobs_stale_locked(key)
            result = DesignBrainJobResult(
                request_id=job.request_id,
                input_revision=int(job.input_revision),
                engineering_hash=str(job.engineering_hash),
                status=DesignBrainJobStatus.PENDING,
                queued_at_ns=now,
            )
            record = _JobRecord(job=job, result=result)
            self._records[key] = record
            self._latest_key = key
            record.future = self._executor.submit(self._run, key)
            return result

    def get(self, *, input_revision: int, engineering_hash: str) -> DesignBrainJobResult | None:
        key = (int(input_revision), str(engineering_hash))
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return None
            self._reconcile_locked(key, record)
            return record.result

    def latest(self) -> DesignBrainJobResult | None:
        with self._lock:
            if self._latest_key is None:
                return None
            record = self._records.get(self._latest_key)
            if record is None:
                return None
            self._reconcile_locked(self._latest_key, record)
            return record.result

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, key: tuple[int, str]) -> DesignBrainExecution:
        with self._lock:
            record = self._records[key]
            record.result = replace(
                record.result,
                status=DesignBrainJobStatus.RUNNING,
                started_at_ns=time.perf_counter_ns(),
            )
            job = record.job
        return self._runner(job.request())

    def _reconcile_locked(self, key: tuple[int, str], record: _JobRecord) -> None:
        future = record.future
        if future is None or not future.done():
            return
        if record.result.status in {
            DesignBrainJobStatus.READY,
            DesignBrainJobStatus.STALE,
            DesignBrainJobStatus.FAILED,
        }:
            return
        finished = time.perf_counter_ns()
        try:
            execution = future.result()
            status = (
                DesignBrainJobStatus.READY
                if key == self._latest_key
                else DesignBrainJobStatus.STALE
            )
            record.result = replace(
                record.result,
                status=status,
                execution=execution if status is DesignBrainJobStatus.READY else None,
                finished_at_ns=finished,
            )
        except Exception as exc:  # noqa: BLE001 - lifecycle stores worker failures
            record.result = replace(
                record.result,
                status=DesignBrainJobStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
                finished_at_ns=finished,
            )

    def _mark_older_jobs_stale_locked(self, newest_key: tuple[int, str]) -> None:
        for key, record in self._records.items():
            if key == newest_key:
                continue
            if key[0] < newest_key[0] and record.result.status in {
                DesignBrainJobStatus.PENDING,
                DesignBrainJobStatus.RUNNING,
            }:
                record.result = replace(
                    record.result,
                    status=DesignBrainJobStatus.STALE,
                    finished_at_ns=time.perf_counter_ns(),
                )


__all__ = [
    "DesignBrainJobInput",
    "DesignBrainJobManager",
    "DesignBrainJobResult",
    "DesignBrainJobStatus",
]

