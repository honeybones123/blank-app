"""Design Guide JSONL trace coordination."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable


def design_guide_tracer_path() -> str:
    override = os.environ.get("DESIGN_GUIDE_TRACE_PATH")
    if override:
        return str(override)
    configured_outputs = os.environ.get("BEAM_OUTPUTS_DIR")
    if configured_outputs:
        outputs_root = Path(configured_outputs).expanduser().resolve()
    else:
        runtime_root = Path(__file__).resolve().parents[2]
        canonical_outputs = runtime_root.parent / "complete-app - Outputs"
        if canonical_outputs.is_dir():
            outputs_root = canonical_outputs
        else:
            local_app_data = os.environ.get("LOCALAPPDATA")
            outputs_root = (
                Path(local_app_data) / "BeamApp"
                if local_app_data
                else Path.cwd() / ".beam_app_data"
            )
    return str(
        outputs_root
        / "artifacts"
        / "debug"
        / "design_guide"
        / "design_guide_trace.jsonl"
    )


def design_guide_tracer_verbose_log() -> bool:
    return str(os.environ.get("DESIGN_GUIDE_TRACER_VERBOSE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def append_design_guide_trace(
    event: str,
    data: dict,
    *,
    run_id: str,
    source: str,
    tracer_path_fn: Callable[[], str] = design_guide_tracer_path,
    tracer_verbose_log_fn: Callable[[], bool] = design_guide_tracer_verbose_log,
    agent_debug_log_fn: Callable[..., None] | None = None,
    append_failure_location: str = "inputs_application.page_runtime.common:_append_design_guide_trace",
) -> None:
    """Append one JSON line; never raises."""
    path = tracer_path_fn()
    print(
        "DG TRACE APPEND\n"
        f"event={event}\n"
        f"run_id={run_id}\n"
        f"resolved_path={path}\n",
        file=sys.stderr,
        end="",
        flush=True,
    )
    ts_ms = int(time.time() * 1000)
    row = {
        "run_id": str(run_id),
        "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "timestamp_ms": ts_ms,
        "event": str(event),
        "source": str(source),
        "data": dict(data or {}),
    }
    try:
        ddir = os.path.dirname(path)
        if ddir and not os.path.isdir(ddir):
            os.makedirs(ddir, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception as exc:
        recovered = False
        if isinstance(exc, OSError):
            try:
                backup = f"{path}.append_failed_{ts_ms}.bak"
                if os.path.exists(path):
                    os.replace(path, backup)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                recovered = True
            except Exception as recovery_exc:
                if tracer_verbose_log_fn():
                    try:
                        print(
                            "[design_guide_tracer] append recovery failed "
                            f"path={path!r} event={event!r} {repr(recovery_exc)}",
                            file=sys.stderr,
                        )
                    except Exception:
                        pass
        if recovered:
            return
        if tracer_verbose_log_fn():
            try:
                if agent_debug_log_fn is not None:
                    agent_debug_log_fn(
                        "design_guide_tracer_append_failed",
                        {
                            "tracer_path": path,
                            "event": str(event),
                            "exception_repr": repr(exc),
                        },
                        location=append_failure_location,
                        hypothesis_id="H_DG_TRACER_APPEND",
                    )
                print(
                    f"[design_guide_tracer] append failed path={path!r} event={event!r} {repr(exc)}",
                    file=sys.stderr,
                )
            except Exception:
                pass


__all__ = [
    "append_design_guide_trace",
    "design_guide_tracer_path",
    "design_guide_tracer_verbose_log",
]
