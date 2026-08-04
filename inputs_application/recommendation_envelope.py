"""Canonical interpretation of pending Inputs recommendations."""

from __future__ import annotations

from typing import Any


NON_COMMIT_STATUSES = frozenset(
    {"blocked", "failed", "no_action", "no_actionable_full_coverage_candidate", "rejected"}
)


def recommendation_updates(recommendation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(recommendation, dict):
        return {}
    updates = recommendation.get("updates")
    if isinstance(updates, dict) and updates:
        return dict(updates)
    resolved = recommendation.get("resolved_candidate")
    if isinstance(resolved, dict) and isinstance(resolved.get("updates"), dict) and resolved.get("updates"):
        return dict(resolved["updates"])
    payload = recommendation.get("action_payload")
    if isinstance(payload, dict):
        payload_updates = payload.get("resolved_candidate_updates") or payload.get("updates")
        if isinstance(payload_updates, dict) and payload_updates:
            return dict(payload_updates)
    return {}


def build_recommendation_envelope(
    *,
    updates: dict[str, Any] | None = None,
    source: str = "",
    status: str = "",
    blocked_reason: str | None = None,
    commit_eligible: bool | None = None,
    preview: dict[str, Any] | None = None,
    audit: dict[str, Any] | None = None,
    required_domains: list | tuple | set | None = None,
) -> dict[str, Any]:
    updates_d = dict(updates or {}) if isinstance(updates, dict) else {}
    status_norm = str(status or "").strip()
    reason_norm = str(blocked_reason or "").strip()
    if commit_eligible is None:
        commit_eligible = bool(updates_d) and not reason_norm and status_norm not in NON_COMMIT_STATUSES
    domains_iter = (
        [required_domains]
        if isinstance(required_domains, str)
        else (
            required_domains
            if isinstance(required_domains, (list, tuple, set))
            else ()
        )
    )
    return {
        "version": 1,
        "source": str(source or "").strip() or None,
        "status": status_norm or ("ready" if commit_eligible else "blocked" if reason_norm else "advisory"),
        "updates": updates_d,
        "commit_eligible": bool(commit_eligible),
        "blocked_reason": reason_norm or None,
        "required_domains": [
            str(domain or "").strip().lower()
            for domain in domains_iter
            if str(domain or "").strip()
        ],
        "preview": dict(preview or {}) if isinstance(preview, dict) else {},
        "audit": dict(audit or {}) if isinstance(audit, dict) else {},
    }


def attach_recommendation_envelope(
    recommendation: dict[str, Any] | None,
    *,
    source: str,
    status: str = "ready",
    blocked_reason: str | None = None,
    commit_eligible: bool | None = None,
    preview: dict[str, Any] | None = None,
    audit: dict[str, Any] | None = None,
    required_domains: list | tuple | set | None = None,
) -> dict[str, Any] | None:
    if not isinstance(recommendation, dict):
        return None
    out = dict(recommendation)
    envelope = build_recommendation_envelope(
        updates=recommendation_updates(out),
        source=source,
        status=status,
        blocked_reason=blocked_reason,
        commit_eligible=commit_eligible,
        preview=preview,
        audit=audit,
        required_domains=required_domains,
    )
    out["recommendation_envelope"] = envelope
    out["commit_eligible"] = bool(envelope.get("commit_eligible"))
    out["blocked_reason"] = envelope.get("blocked_reason")
    return out


def recommendation_envelope(recommendation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(recommendation, dict):
        return {}
    existing = recommendation.get("recommendation_envelope")
    if isinstance(existing, dict):
        return dict(existing)
    meta = dict(recommendation.get("meta") or {})
    status = str(meta.get("status") or recommendation.get("status") or "").strip()
    reason = str(
        recommendation.get("blocked_reason")
        or meta.get("blocked_reason")
        or meta.get("reason")
        or ""
    ).strip()
    return build_recommendation_envelope(
        updates=recommendation_updates(recommendation),
        source=str(recommendation.get("_source") or recommendation.get("source") or "legacy_pending"),
        status=status,
        blocked_reason=reason or None,
    )


def recommendation_blocked_reason(recommendation: dict[str, Any] | None) -> str | None:
    envelope = recommendation_envelope(recommendation)
    reason = str(envelope.get("blocked_reason") or "").strip()
    if reason:
        return reason
    if isinstance(recommendation, dict) and not bool(envelope.get("commit_eligible")):
        status = str(envelope.get("status") or "").strip()
        if status in NON_COMMIT_STATUSES:
            return status
    return None


def recommendation_commit_eligible(recommendation: dict[str, Any] | None) -> bool:
    return bool(recommendation_envelope(recommendation).get("commit_eligible"))


def effective_apply_mode_and_payload(
    recommendation: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any]]:
    if not isinstance(recommendation, dict):
        return None, {}
    apply_obj = recommendation.get("apply")
    if isinstance(apply_obj, dict):
        mode = str(apply_obj.get("mode") or "").strip()
        payload = dict(apply_obj.get("payload") or {})
        if mode:
            return mode, payload
    action_type = str(recommendation.get("action_type") or "").strip()
    payload = dict(recommendation.get("action_payload") or {})
    resolved_candidate = recommendation.get("resolved_candidate")
    if isinstance(resolved_candidate, dict):
        resolved_updates = resolved_candidate.get("updates")
        if isinstance(resolved_updates, dict) and resolved_updates:
            payload["resolved_candidate_updates"] = dict(resolved_updates)
            payload.setdefault(
                "resolved_candidate_label",
                str(
                    resolved_candidate.get("label")
                    or recommendation.get("title")
                    or "Apply recommendation"
                ).strip(),
            )
            payload.setdefault(
                "resolved_candidate_action_type",
                str(
                    resolved_candidate.get("action_type")
                    or action_type
                    or "apply_compound_guidance"
                ).strip(),
            )
            payload.setdefault("updates", dict(resolved_updates))
            action_type = "apply_resolved_candidate"
    if action_type and payload:
        return action_type, payload
    return None, {}


__all__ = [
    "NON_COMMIT_STATUSES",
    "attach_recommendation_envelope",
    "build_recommendation_envelope",
    "effective_apply_mode_and_payload",
    "recommendation_blocked_reason",
    "recommendation_commit_eligible",
    "recommendation_envelope",
    "recommendation_updates",
]
