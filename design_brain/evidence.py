"""Design Brain evidence/proof mapping helpers.

This module shapes verifier-readable evidence payloads. It does not search for
candidates, evaluate formulas, apply updates, or render UI.
"""

from __future__ import annotations

from typing import Any, Callable

from design_brain.candidates import candidate_rows_from_evidence


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


def repair_search_exhaustive(evidence: dict) -> bool:
    return bool(
        evidence.get("repair_search_exhaustive")
        or evidence.get("active_repair_search_exhaustive")
        or evidence.get("repair_or_target_band_search_exhaustive")
        or evidence.get("target_band_search_exhaustive")
    )


def candidate_search_summary_row(
    candidate: dict | None,
    *,
    index: int,
    target_low: float,
    target_high: float,
    fallback_title: str | None = None,
    parse_util: Callable[[Any], Any] | None = None,
) -> dict:
    """Shape one candidate-search row with an explicit util parser."""
    from design_brain.optimisation import optimisation_candidate_search_summary_row

    return optimisation_candidate_search_summary_row(
        candidate,
        index=index,
        target_low=target_low,
        target_high=target_high,
        fallback_title=fallback_title,
        parse_util=parse_util,
    )


def build_candidate_search_evidence(
    *,
    selected_candidate: dict | None,
    all_candidates: list[dict],
    target_low: float,
    target_high: float,
    exhaustive: bool,
    search_scope: str,
    selected_title: str | None = None,
    parse_util: Callable[[Any], Any] | None = None,
) -> dict:
    """Build verifier-readable candidate-search evidence without page state."""
    from design_brain.optimisation import (
        optimisation_best_target_band_candidate_fields,
        optimisation_candidate_search_count_statistics,
        optimisation_closest_safe_candidate_fields,
        optimisation_copy_row_slice,
        optimisation_rejected_target_band_rows,
        optimisation_safe_executor_backed_rows,
        optimisation_selected_candidate_fields,
        optimisation_target_band_rows,
    )

    rows: list[dict] = []
    selected_obj = selected_candidate if isinstance(selected_candidate, dict) else {}
    selected_row_index = None
    for idx, cand in enumerate(list(all_candidates or []), start=1):
        row = candidate_search_summary_row(
            cand,
            index=idx,
            target_low=target_low,
            target_high=target_high,
            parse_util=parse_util,
        )
        rows.append(row)
        if selected_obj and cand is selected_obj:
            selected_row_index = len(rows) - 1
    if selected_obj and selected_row_index is None:
        rows.insert(
            0,
            candidate_search_summary_row(
                selected_obj,
                index=0,
                target_low=target_low,
                target_high=target_high,
                fallback_title=selected_title,
                parse_util=parse_util,
            ),
        )
        selected_row_index = 0
    safe_rows = optimisation_safe_executor_backed_rows(rows)
    target_rows = optimisation_target_band_rows(
        safe_rows,
        target_low=target_low,
        target_high=target_high,
    )
    closest_row = None
    if safe_rows:
        closest_row = min(
            safe_rows,
            key=lambda row: (
                float(row.get("distance_to_band") if row.get("distance_to_band") is not None else float("inf")),
                str(row.get("candidate_id") or ""),
            ),
        )
    selected_row = rows[selected_row_index] if selected_row_index is not None and selected_row_index < len(rows) else None
    best_target = target_rows[0] if target_rows else None
    selected_util = None if selected_row is None else selected_row.get("preview_util")
    selected_distance = None if selected_row is None else selected_row.get("distance_to_band")
    closest_distance = None if closest_row is None else closest_row.get("distance_to_band")
    strict_target_scope = str(search_scope or "").strip() in {
        "combined_best_safe_shear_plus_bending_cleanup",
    }
    outside_allowed = bool(
        not strict_target_scope
        and
        selected_util is not None
        and not (float(target_low) <= float(selected_util) <= float(target_high))
        and bool(exhaustive)
        and len(target_rows) == 0
        and bool(safe_rows)
        and selected_row is not None
        and closest_row is not None
        and (
            selected_row.get("candidate_id") == closest_row.get("candidate_id")
            or (
                selected_distance is not None
                and closest_distance is not None
                and abs(float(selected_distance) - float(closest_distance)) <= 1e-9
            )
        )
    )
    reason = None
    category = None
    if outside_allowed:
        reason = (
            "No safe executor-backed target-band candidate was found in the searched catalogue; "
            "the selected candidate is the closest safe available step."
        )
        category = "discrete_increment_limit"
    rejected_target_rows = optimisation_rejected_target_band_rows(rows)
    count_stats = optimisation_candidate_search_count_statistics(
        all_candidates=all_candidates,
        rows=rows,
        safe_rows=safe_rows,
        target_rows=target_rows,
    )
    selected_fields = optimisation_selected_candidate_fields(selected_row, selected_row_index)
    closest_fields = optimisation_closest_safe_candidate_fields(closest_row)
    best_target_fields = optimisation_best_target_band_candidate_fields(best_target)
    return {
        "candidate_search_exhaustive": bool(exhaustive),
        "search_scope": str(search_scope or ""),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "generated_count": count_stats["generated_count"],
        "deduped_count": count_stats["deduped_count"],
        "preview_count": count_stats["preview_count"],
        "total_candidates_considered": count_stats["total_candidates_considered"],
        "candidate_rows": optimisation_copy_row_slice(rows, 80),
        "safe_executor_backed_candidates_count": count_stats["safe_executor_backed_candidates_count"],
        "target_band_candidate_count": count_stats["target_band_candidate_count"],
        "selected_rank": selected_fields["selected_rank"],
        "selected_candidate_id": selected_fields["selected_candidate_id"],
        "selected_candidate_title": selected_fields["selected_candidate_title"],
        "selected_candidate_util": selected_fields["selected_candidate_util"],
        "selected_candidate_distance_to_band": selected_fields["selected_candidate_distance_to_band"],
        "selected_candidate_updates": selected_fields["selected_candidate_updates"],
        "closest_safe_candidate_id": closest_fields["closest_safe_candidate_id"],
        "closest_safe_candidate_title": closest_fields["closest_safe_candidate_title"],
        "closest_safe_candidate_util": closest_fields["closest_safe_candidate_util"],
        "closest_safe_candidate_distance_to_band": closest_fields["closest_safe_candidate_distance_to_band"],
        "closest_safe_candidate_updates": closest_fields["closest_safe_candidate_updates"],
        "best_target_band_candidate_id": best_target_fields["best_target_band_candidate_id"],
        "best_target_band_candidate_title": best_target_fields["best_target_band_candidate_title"],
        "best_target_band_candidate_util": best_target_fields["best_target_band_candidate_util"],
        "best_target_band_candidate_updates": best_target_fields["best_target_band_candidate_updates"],
        "target_band_candidates": optimisation_copy_row_slice(target_rows, 20),
        "safe_executor_backed_candidates": optimisation_copy_row_slice(safe_rows, 40),
        "rejected_target_band_candidates": optimisation_copy_row_slice(rejected_target_rows, 20),
        "rejected_target_band_candidate_reasons": [
            str(row.get("rejection_reason") or "preview_failed")
            for row in rejected_target_rows[:20]
        ],
        "outside_target_band_allowed": bool(outside_allowed),
        "outside_target_band_allowed_reason": reason,
        "outside_target_band_allowed_category": category,
    }
