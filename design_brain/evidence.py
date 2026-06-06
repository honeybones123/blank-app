"""Design Brain evidence/proof mapping helpers.

This module shapes verifier-readable evidence payloads. It does not search for
candidates, evaluate formulas, apply updates, or render UI.
"""

from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def candidate_search_evidence_from_payload(payload: dict, primary: dict, debug: dict) -> dict:
    evidence = _as_dict(
        debug.get("candidate_search_evidence")
        or debug.get("local_cleanup_candidate_search_evidence")
        or primary.get("candidate_search_evidence")
        or _as_dict(primary.get("action_payload")).get("candidate_search_evidence")
        or _as_dict(primary.get("resolved_candidate")).get("candidate_search_evidence")
    )
    for key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    ):
        merged = {}
        for source in (
            evidence.get(key),
            debug.get(key),
            primary.get(key),
            _as_dict(primary.get("action_payload")).get(key),
            _as_dict(primary.get("resolved_candidate")).get(key),
        ):
            if isinstance(source, dict):
                merged.update({str(k).strip().lower(): dict(v) for k, v in source.items() if isinstance(v, dict)})
        if merged:
            evidence[key] = dict(merged)
    if "overview" not in evidence and isinstance(debug.get("overview"), dict):
        evidence["overview"] = dict(debug.get("overview") or {})
    if "family_status_current" not in evidence and isinstance(debug.get("family_status_current"), dict):
        evidence["family_status_current"] = dict(debug.get("family_status_current") or {})
    return evidence


def active_failures_from_evidence(summary: dict, evidence: dict, debug: dict) -> list[str]:
    raw = evidence.get("active_failures") or debug.get("active_failures")
    if isinstance(raw, (list, tuple, set)):
        return sorted({str(item or "").strip().lower() for item in raw if str(item or "").strip()})
    statuses = _as_dict(summary.get("statuses"))
    return sorted(
        str(family or "").strip().lower()
        for family, status in statuses.items()
        if str(status or "").strip().upper() == "FAIL" and str(family or "").strip()
    )


def candidate_rows_from_evidence(evidence: dict) -> list[dict]:
    rows = []
    for key in (
        "candidate_rows",
        "active_fail_repair_candidate_rows",
        "local_cleanup_candidates",
        "local_cleanup_candidate_inventory",
    ):
        raw = evidence.get(key)
        if isinstance(raw, list):
            rows.extend(dict(item) for item in raw if isinstance(item, dict))
    selected_id = evidence.get("selected_candidate_id")
    selected_updates = _as_dict(evidence.get("selected_candidate_updates"))
    if selected_id or selected_updates:
        rows.insert(
            0,
            {
                "candidate_id": selected_id,
                "title": evidence.get("selected_candidate_title"),
                "updates": selected_updates,
                "preview_util": evidence.get("selected_candidate_util"),
                "expected_util": evidence.get("selected_candidate_util"),
                "safe_executor_backed": bool(selected_updates),
                "preview_pass": None,
            },
        )
    return rows


def repair_search_exhaustive(evidence: dict) -> bool:
    return bool(
        evidence.get("repair_search_exhaustive")
        or evidence.get("active_repair_search_exhaustive")
        or evidence.get("repair_or_target_band_search_exhaustive")
        or evidence.get("target_band_search_exhaustive")
    )
