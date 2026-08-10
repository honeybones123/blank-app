"""Non-blocking process boundary for revisioned Design Brain jobs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Mapping
from uuid import uuid4

from application.contracts.design_brain import EngineeringInputSnapshot
from inputs_application.design_brain_job_worker import WORKER_SCHEMA


@dataclass(frozen=True)
class DesignBrainJobPoll:
    status: str
    input_revision: int
    engineering_hash: str
    result: dict[str, Any] | None = None
    error: str | None = None
    job_id: str | None = None
    elapsed_ms: float | None = None


@dataclass
class _JobRecord:
    process: subprocess.Popen[Any]
    request: dict[str, Any]
    request_path: Path
    response_path: Path
    log_handle: Any


_JOBS: dict[str, _JobRecord] = {}
_JOBS_LOCK = threading.Lock()


def _job_key(owner_id: str, beam_id: str) -> str:
    return f"{owner_id}:{beam_id or 'draft'}"


def _response(record: _JobRecord) -> dict[str, Any] | None:
    if not record.response_path.is_file():
        return None
    try:
        payload = json.loads(record.response_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


class DesignBrainJobService:
    """Submit at most one process per session/beam and keep only latest truth."""

    def __init__(self, *, outputs_root: Path, app_root: Path) -> None:
        self._outputs_root = Path(outputs_root).resolve()
        self._app_root = Path(app_root).resolve()
        self._jobs_root = self._outputs_root / "design_brain_jobs"

    def poll_or_submit(
        self,
        *,
        owner_id: str,
        beam_id: str,
        input_revision: int,
        engineering_snapshot: EngineeringInputSnapshot,
        engineering_calculations: Mapping[str, Any],
        guidance_context: Mapping[str, Any],
        family_override: str | None,
        guidance_debug_verbose: bool,
        session_seed: Mapping[str, Any],
    ) -> DesignBrainJobPoll:
        revision = int(input_revision)
        engineering_hash = engineering_snapshot.engineering_hash
        key = _job_key(owner_id, beam_id)
        with _JOBS_LOCK:
            record = _JOBS.get(key)
            if record is not None and record.process.poll() is None:
                return DesignBrainJobPoll(
                    status="running",
                    input_revision=revision,
                    engineering_hash=engineering_hash,
                    job_id=str(record.request.get("job_id") or ""),
                )
            if record is not None:
                response = _response(record)
                try:
                    record.log_handle.close()
                except Exception:
                    pass
                _JOBS.pop(key, None)
                if (
                    response is not None
                    and response.get("status") == "ready"
                    and int(response.get("input_revision") or -1) == revision
                    and str(response.get("engineering_hash") or "")
                    == engineering_hash
                    and isinstance(response.get("result"), dict)
                ):
                    return DesignBrainJobPoll(
                        status="ready",
                        input_revision=revision,
                        engineering_hash=engineering_hash,
                        result=dict(response["result"]),
                        job_id=str(response.get("job_id") or ""),
                        elapsed_ms=float(response.get("elapsed_ms") or 0.0),
                    )
                if (
                    response is not None
                    and response.get("status") == "failed"
                    and int(response.get("input_revision") or -1) == revision
                    and str(response.get("engineering_hash") or "")
                    == engineering_hash
                ):
                    return DesignBrainJobPoll(
                        status="failed",
                        input_revision=revision,
                        engineering_hash=engineering_hash,
                        error=str(response.get("error") or "worker_failed"),
                        job_id=str(response.get("job_id") or ""),
                    )
            record = self._spawn(
                owner_id=owner_id,
                beam_id=beam_id,
                input_revision=revision,
                engineering_snapshot=engineering_snapshot,
                engineering_calculations=engineering_calculations,
                guidance_context=guidance_context,
                family_override=family_override,
                guidance_debug_verbose=guidance_debug_verbose,
                session_seed=session_seed,
            )
            _JOBS[key] = record
            return DesignBrainJobPoll(
                status="submitted",
                input_revision=revision,
                engineering_hash=engineering_hash,
                job_id=str(record.request.get("job_id") or ""),
            )

    def _spawn(
        self,
        *,
        owner_id: str,
        beam_id: str,
        input_revision: int,
        engineering_snapshot: EngineeringInputSnapshot,
        engineering_calculations: Mapping[str, Any],
        guidance_context: Mapping[str, Any],
        family_override: str | None,
        guidance_debug_verbose: bool,
        session_seed: Mapping[str, Any],
    ) -> _JobRecord:
        job_id = uuid4().hex
        job_root = self._jobs_root / str(owner_id)
        job_root.mkdir(parents=True, exist_ok=True)
        request_path = job_root / f"{job_id}.request.json"
        response_path = job_root / f"{job_id}.response.json"
        log_path = job_root / f"{job_id}.log"
        request = {
            "schema": WORKER_SCHEMA,
            "job_id": job_id,
            "owner_id": owner_id,
            "beam_id": beam_id,
            "input_revision": int(input_revision),
            "engineering_hash": engineering_snapshot.engineering_hash,
            "engineering_snapshot": engineering_snapshot.to_dict(),
            "engineering_calculations": dict(engineering_calculations),
            "guidance_context": dict(guidance_context),
            "family_override": family_override,
            "guidance_debug_verbose": bool(guidance_debug_verbose),
            "session_seed": dict(session_seed),
            "submitted_at": time.time(),
        }
        request_path.write_text(
            json.dumps(request, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        environment = dict(os.environ)
        environment["BEAM_OUTPUTS_DIR"] = str(self._outputs_root)
        existing_python_path = str(environment.get("PYTHONPATH") or "").strip()
        environment["PYTHONPATH"] = os.pathsep.join(
            value
            for value in (str(self._app_root), existing_python_path)
            if value
        )
        log_handle = log_path.open("w", encoding="utf-8")
        creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "inputs_application.design_brain_job_worker",
                str(request_path),
                str(response_path),
            ],
            cwd=str(self._app_root),
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
        return _JobRecord(
            process=process,
            request=request,
            request_path=request_path,
            response_path=response_path,
            log_handle=log_handle,
        )


__all__ = ["DesignBrainJobPoll", "DesignBrainJobService"]
