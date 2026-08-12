"""Process-isolated Design Brain computation from an explicit request."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
import traceback
from typing import Any, Mapping

from application.contracts.design_brain import EngineeringInputSnapshot
from application.design_brain_port import DesignBrainRequest
from inputs_application.design_brain_composition import build_design_brain_service


WORKER_SCHEMA = "inputs_design_brain_job.v1"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def compute_design_brain_job(request: Mapping[str, Any]) -> dict[str, Any]:
    """Compute one immutable revision through the sole installed V2 brain."""

    request_payload = _mapping(request)
    if request_payload.get("schema") != WORKER_SCHEMA:
        raise ValueError("unsupported Design Brain job schema")
    snapshot = EngineeringInputSnapshot(
        **_mapping(request_payload.get("engineering_snapshot"))
    )
    expected_hash = str(request_payload.get("engineering_hash") or "")
    if snapshot.engineering_hash != expected_hash:
        raise ValueError("Design Brain job engineering hash mismatch")
    guidance_context = _mapping(request_payload.get("guidance_context"))
    started = time.perf_counter()
    debug_enabled = bool(request_payload.get("guidance_debug_verbose"))
    design_brain_service = build_design_brain_service(adapter_name="v2")
    execution = design_brain_service.run(
        DesignBrainRequest(
            engineering_snapshot=snapshot,
            input_revision=int(request_payload.get("input_revision") or 0),
            family_hint=(
                str(request_payload.get("family_override") or "").strip() or None
            ),
            resolved_inputs=guidance_context,
            engineering_calculations=_mapping(
                request_payload.get("engineering_calculations")
            ),
            debug_enabled=debug_enabled,
        )
    )
    return {
        "schema": WORKER_SCHEMA,
        "status": "ready",
        "job_id": request_payload.get("job_id"),
        "owner_id": request_payload.get("owner_id"),
        "beam_id": request_payload.get("beam_id"),
        "input_revision": int(request_payload.get("input_revision") or 0),
        "engineering_hash": snapshot.engineering_hash,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "stage_trace": list(execution.stage_trace),
        "result": execution.result.to_dict(),
    }


def _write_response(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: design_brain_job_worker REQUEST RESPONSE")
    request_path = Path(args[0]).resolve()
    response_path = Path(args[1]).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    try:
        response = compute_design_brain_job(request)
        exit_code = 0
    except Exception as exc:
        response = {
            "schema": WORKER_SCHEMA,
            "status": "failed",
            "job_id": request.get("job_id"),
            "owner_id": request.get("owner_id"),
            "beam_id": request.get("beam_id"),
            "input_revision": int(request.get("input_revision") or 0),
            "engineering_hash": request.get("engineering_hash"),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        exit_code = 1
    _write_response(response_path, response)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
