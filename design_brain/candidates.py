"""Design Brain candidate normalisation helpers.

This module owns pure candidate metadata/proof shaping. It does not generate
candidates, rank candidates, search, evaluate formulas, apply updates, or
render UI.
"""

from __future__ import annotations

from typing import Any

from design_brain.interface import DesignBrainCandidate


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def candidate_id_from_item(primary: dict, contract: dict, evidence: dict) -> str | None:
    value = (
        contract.get("candidate_id")
        or contract.get("source_candidate_id")
        or evidence.get("selected_candidate_id")
        or primary.get("candidate_id")
        or primary.get("source_candidate_id")
    )
    return str(value) if value is not None and str(value).strip() else None


def candidate_label_from_item(primary: dict, evidence: dict) -> str | None:
    value = (
        evidence.get("selected_candidate_title")
        or primary.get("title_main")
        or primary.get("title")
        or primary.get("label")
    )
    return str(value) if value is not None and str(value).strip() else None


def candidate_updates_from_row(row: dict) -> dict:
    return _as_dict(
        row.get("updates")
        or row.get("proposed_updates")
        or row.get("selected_candidate_updates")
        or row.get("best_safe_candidate_updates")
        or row.get("closest_safe_candidate_updates")
    )


def candidate_preview_pass_from_row(row: dict) -> bool | None:
    preview_pass = row.get("preview_pass")
    if preview_pass is None and row.get("preview_statuses"):
        statuses = _as_dict(row.get("preview_statuses"))
        preview_pass = not any(str(v or "").strip().upper() == "FAIL" for v in statuses.values())
    return preview_pass if isinstance(preview_pass, bool) else None


def candidate_family_from_row(row: dict) -> str | None:
    value = str(row.get("family") or row.get("recommendation_family_tag") or "").strip().lower()
    return value or None


def candidate_is_executable(candidate: dict) -> bool:
    if not isinstance(candidate, dict):
        return False
    return bool(
        candidate.get("executor_backed")
        and candidate.get("preview_pass") is not False
        and _as_dict(candidate.get("updates"))
    )


def normalise_candidate_row(row: dict, *, fallback_id: str | None = None) -> dict:
    if not isinstance(row, dict):
        return {}
    candidate_id = row.get("candidate_id") or row.get("id") or fallback_id
    updates = candidate_updates_from_row(row)
    preview_pass = candidate_preview_pass_from_row(row)
    return DesignBrainCandidate(
        candidate_id=str(candidate_id) if candidate_id else None,
        label=str(row.get("title") or row.get("label") or row.get("selected_candidate_title") or "")
        or None,
        family=candidate_family_from_row(row),
        executor_backed=bool(
            row.get("safe_executor_backed")
            or row.get("executor_backed")
            or row.get("is_executable")
        ),
        preview_pass=preview_pass,
        expected_utilisation=_as_float(
            row.get("expected_util")
            if row.get("expected_util") is not None
            else row.get("candidate_post_util", row.get("preview_util"))
        ),
        updates=updates,
        raw=dict(row),
    ).to_dict() if hasattr(DesignBrainCandidate, "to_dict") else {
        "candidate_id": str(candidate_id) if candidate_id else None,
        "label": row.get("title") or row.get("label") or row.get("selected_candidate_title"),
        "family": row.get("family") or row.get("recommendation_family_tag"),
        "executor_backed": bool(row.get("safe_executor_backed") or row.get("executor_backed") or row.get("is_executable")),
        "preview_pass": preview_pass,
        "expected_utilisation": _as_float(row.get("expected_util") if row.get("expected_util") is not None else row.get("candidate_post_util", row.get("preview_util"))),
        "updates": updates,
        "raw": dict(row),
    }
