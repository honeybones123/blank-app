"""Application-layer Apply command boundary.

The existing Apply executor is injected during migration. This module owns the
single validation-and-dispatch decision and remains independent of Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from application.contracts.design_brain import AuthoritativeDesignResult


@dataclass(frozen=True)
class ApplyCommandResult:
    status: str
    reason: str
    recommendation_id: str | None = None
    executor_result: Any = None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _candidate_identity_values(payload: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("recommendation_id", "candidate_id", "source_candidate_id"):
        value = str(payload.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    resolved = payload.get("resolved_candidate")
    if isinstance(resolved, Mapping):
        for key in ("recommendation_id", "candidate_id", "source_candidate_id"):
            value = str(resolved.get(key) or "").strip()
            if value and value not in values:
                values.append(value)
    return tuple(values)


def _candidate_id(payload: Mapping[str, Any]) -> str:
    values = _candidate_identity_values(payload)
    return values[0] if values else ""


def _family_id(payload: Mapping[str, Any]) -> str:
    resolved = payload.get("resolved_candidate")
    resolved_map = resolved if isinstance(resolved, Mapping) else {}
    return str(
        payload.get("family")
        or payload.get("resolved_candidate_family_tag")
        or resolved_map.get("family")
        or ""
    ).strip().upper()


def _updates(payload: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("resolved_candidate_updates", "updates"):
        value = payload.get(key)
        if isinstance(value, Mapping) and value:
            return dict(value)
    action_payload = payload.get("action_payload")
    if isinstance(action_payload, Mapping):
        for key in ("resolved_candidate_updates", "updates"):
            value = action_payload.get(key)
            if isinstance(value, Mapping) and value:
                return dict(value)
    resolved = payload.get("resolved_candidate")
    if isinstance(resolved, Mapping):
        value = resolved.get("updates")
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


def _failed(reason: str, payload: Mapping[str, Any]) -> ApplyCommandResult:
    return ApplyCommandResult(
        status="failed",
        reason=reason,
        recommendation_id=_candidate_id(payload) or None,
    )


def execute_apply_command(
    *,
    current_result: AuthoritativeDesignResult | None,
    recommendation: Mapping[str, Any] | None,
    apply_fn: Callable[[dict[str, Any]], Any],
) -> ApplyCommandResult:
    """Validate and dispatch one recommendation payload exactly once."""

    payload = _mapping(recommendation)
    if not payload:
        return ApplyCommandResult(status="failed", reason="missing_apply_payload")

    if current_result is None:
        return _failed("missing_authoritative_design_result", payload)

    authoritative_payload = _mapping(current_result.apply_payload)
    final_publication = _mapping(current_result.final_publication)
    cta = _mapping(final_publication.get("cta") or current_result.cta_model)
    if str(current_result.family_outcome or "").strip().upper() != "ACTION":
        return _failed("authoritative_result_not_action", payload)
    if str(final_publication.get("outcome_state") or "").strip().upper() != "ACTION":
        return _failed("authoritative_publication_not_action", payload)
    if not all(bool(cta.get(key)) for key in ("enabled", "actionable", "apply_allowed")):
        return _failed("authoritative_cta_not_actionable", payload)

    authoritative_candidate_id = _candidate_id(authoritative_payload)
    incoming_candidate_id = _candidate_id(payload)
    if not authoritative_candidate_id or incoming_candidate_id != authoritative_candidate_id:
        return _failed("stale_authoritative_apply_candidate", payload)
    authoritative_family = _family_id(authoritative_payload)
    incoming_family = _family_id(payload)
    if not authoritative_family or incoming_family != authoritative_family:
        return _failed("stale_authoritative_apply_family", payload)
    if authoritative_family != str(current_result.governing_family or "").strip().upper():
        return _failed("authoritative_apply_family_mismatch", payload)
    if str(authoritative_payload.get("action_type") or "").strip() != "apply_resolved_candidate":
        return _failed("invalid_authoritative_apply_action_type", payload)
    if str(payload.get("action_type") or "").strip() != "apply_resolved_candidate":
        return _failed("invalid_incoming_apply_action_type", payload)
    authoritative_updates = _updates(authoritative_payload)
    if not authoritative_updates or _updates(payload) != authoritative_updates:
        return _failed("stale_authoritative_apply_updates", payload)

    recommendation_id = str(
        payload.get("recommendation_id")
        or payload.get("candidate_id")
        or payload.get("source_candidate_id")
        or ""
    ).strip() or None
    executor_result = apply_fn(dict(payload))
    status = str(executor_result or "").strip() or "rerun_required"
    if status not in {"dispatch_ok", "failed"}:
        status = "rerun_required"
    return ApplyCommandResult(
        status=status,
        reason="authoritative_executor_dispatched_once",
        recommendation_id=recommendation_id,
        executor_result=executor_result,
    )


__all__ = ["ApplyCommandResult", "execute_apply_command"]
