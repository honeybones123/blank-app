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


def _candidate_identity_matches(
    authoritative_payload: Mapping[str, Any],
    incoming_payload: Mapping[str, Any],
) -> bool:
    authoritative_ids = _candidate_identity_values(authoritative_payload)
    incoming_ids = _candidate_identity_values(incoming_payload)
    if not authoritative_ids or not incoming_ids:
        return True
    if set(authoritative_ids).intersection(incoming_ids):
        return True
    # The transitional authority adapter stores the source candidate token,
    # while the rendered CTA may carry the family-qualified canonical token.
    # Accept that representation only when the family tag also agrees.
    authoritative_family = str(
        authoritative_payload.get("family")
        or authoritative_payload.get("resolved_candidate_family_tag")
        or (authoritative_payload.get("resolved_candidate") or {}).get("family")
        or ""
    ).strip().upper()
    incoming_family = str(
        incoming_payload.get("family")
        or incoming_payload.get("resolved_candidate_family_tag")
        or (incoming_payload.get("resolved_candidate") or {}).get("family")
        or ""
    ).strip().upper()
    if authoritative_family and incoming_family and authoritative_family != incoming_family:
        return False
    return any(
        auth_id.rsplit(":", 1)[-1] == incoming_id.rsplit(":", 1)[-1]
        for auth_id in authoritative_ids
        for incoming_id in incoming_ids
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

    if current_result is not None:
        authoritative_payload = _mapping(current_result.apply_payload)
        if not _candidate_identity_matches(authoritative_payload, payload):
            incoming_ids = _candidate_identity_values(payload)
            return ApplyCommandResult(
                status="failed",
                reason="stale_authoritative_apply_payload",
                recommendation_id=incoming_ids[0] if incoming_ids else None,
            )

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
        reason="legacy_executor_dispatched_once",
        recommendation_id=recommendation_id,
        executor_result=executor_result,
    )


__all__ = ["ApplyCommandResult", "execute_apply_command"]
