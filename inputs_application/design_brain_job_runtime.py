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


_MANAGERS: dict[str, DesignBrainJobManager] = {}
_PAYLOADS_KEY = "_inputs_design_brain_job_payloads_v1"


def _session_id(session_state: MutableMapping[str, Any]) -> str:
    """Return a stable owner key without storing Streamlit objects in jobs."""

    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            get_script_run_ctx,
        )

        context = get_script_run_ctx(suppress_warning=True)
        session_id = str(getattr(context, "session_id", "") or "").strip()
        if session_id:
            return session_id
    except (ImportError, AttributeError, RuntimeError, TypeError):
        pass
    # Unit tests and non-Streamlit callers still need isolation. The mapping
    # identity is stable for the lifetime of the supplied session state.
    return f"state_{id(session_state)}"


def _manager(session_state: MutableMapping[str, Any]) -> DesignBrainJobManager:
    owner = _session_id(session_state)
    manager = _MANAGERS.get(owner)
    if manager is None:
        service = build_new_design_brain_service()
        manager = DesignBrainJobManager(service.run)
        _MANAGERS[owner] = manager
    return manager


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
    return _manager(session_state).submit(job)


def get_design_brain_job(
    *, session_state: MutableMapping[str, Any], input_revision: int, engineering_hash: str
) -> DesignBrainJobResult | None:
    return _manager(session_state).get(
        input_revision=int(input_revision),
        engineering_hash=str(engineering_hash),
    )


__all__ = [
    "enqueue_design_brain_job",
    "get_design_brain_job",
    "remember_design_brain_job_input",
]
