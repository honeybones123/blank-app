"""Streamlit-facing adapter for the session-independent Design Brain worker."""

from __future__ import annotations

from typing import Any, MutableMapping

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
)
from application.design_brain_jobs import (
    DesignBrainJobInput,
    DesignBrainJobManager,
    DesignBrainJobResult,
)
from inputs_application.design_brain_composition import build_new_design_brain_service


_MANAGER: DesignBrainJobManager | None = None
_PAYLOADS_KEY = "_inputs_design_brain_job_payloads_v1"


def _manager() -> DesignBrainJobManager:
    global _MANAGER
    if _MANAGER is None:
        service = build_new_design_brain_service()
        _MANAGER = DesignBrainJobManager(service.run)
    return _MANAGER


def remember_design_brain_job_input(
    session_state: MutableMapping[str, Any],
    *,
    snapshot: EngineeringInputSnapshot,
    resolved_inputs: dict[str, Any],
    engineering_calculations: dict[str, Any],
    input_revision: int,
    family_hint: str | None = None,
    debug_enabled: bool = False,
) -> None:
    payloads = dict(session_state.get(_PAYLOADS_KEY) or {})
    payloads[str(int(input_revision))] = {
        "snapshot": snapshot.to_dict(),
        "resolved_inputs": dict(resolved_inputs),
        "engineering_calculations": dict(engineering_calculations),
        "family_hint": family_hint,
        "debug_enabled": bool(debug_enabled),
        "engineering_hash": snapshot.engineering_hash,
    }
    session_state[_PAYLOADS_KEY] = payloads


def enqueue_design_brain_job(
    session_state: MutableMapping[str, Any],
    *,
    result: AuthoritativeDesignResult,
    input_revision: int,
) -> DesignBrainJobResult | None:
    payload = dict(
        dict(session_state.get(_PAYLOADS_KEY) or {}).get(str(int(input_revision)))
        or {}
    )
    snapshot_payload = payload.get("snapshot")
    if not isinstance(snapshot_payload, dict):
        return None
    snapshot = EngineeringInputSnapshot(**snapshot_payload)
    if snapshot.engineering_hash != result.engineering_hash:
        return None
    job = DesignBrainJobInput(
        input_revision=int(input_revision),
        engineering_hash=str(result.engineering_hash),
        engineering_snapshot=snapshot,
        resolved_inputs=dict(payload.get("resolved_inputs") or {}),
        engineering_calculations=dict(result.current_calculations or {}),
        family_hint=payload.get("family_hint"),
        debug_enabled=bool(payload.get("debug_enabled", False)),
    )
    return _manager().submit(job)


def get_design_brain_job(
    *, input_revision: int, engineering_hash: str
) -> DesignBrainJobResult | None:
    return _manager().get(
        input_revision=int(input_revision),
        engineering_hash=str(engineering_hash),
    )


__all__ = [
    "enqueue_design_brain_job",
    "get_design_brain_job",
    "remember_design_brain_job_input",
]
