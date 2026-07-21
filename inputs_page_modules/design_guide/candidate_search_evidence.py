"""Candidate-search evidence packaging for the Inputs Design Guide."""

from __future__ import annotations

import math
from typing import Any


_CANDIDATE_SEARCH_EVIDENCE_DEPENDENCIES: tuple[str, ...] = (
    "EFFICIENCY_TARGET_UTIL_MAX",
    "EFFICIENCY_TARGET_UTIL_MIN",
)


def bind_candidate_search_evidence_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CANDIDATE_SEARCH_EVIDENCE_DEPENDENCIES
            if name in namespace
        }
    )


def _candidate_search_distance_to_band(util: object, target_low: float, target_high: float) -> float | None:
    try:
        u = float(util)
    except (TypeError, ValueError):
        return None
    if math.isnan(u) or math.isinf(u):
        return None
    if u < float(target_low):
        return float(target_low) - u
    if u > float(target_high):
        return u - float(target_high)
    return 0.0


def _candidate_search_summary_row(
    candidate: dict | None,
    *,
    index: int,
    target_low: float,
    target_high: float,
    fallback_title: str | None = None,
) -> dict:
    cand = dict(candidate or {})
    item = dict(cand.get("item") or {})
    payload = dict(item.get("action_payload") or cand.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or cand.get("resolved_candidate") or {})
    updates = dict(
        cand.get("updates")
        or cand.get("resolved_candidate_updates")
        or payload.get("resolved_candidate_updates")
        or payload.get("updates")
        or resolved.get("updates")
        or {}
    )
    util = cand.get("candidate_post_util", cand.get("trial_worst_util", cand.get("worst_util")))
    if util is None:
        util = payload.get("resolved_candidate_post_util")
    try:
        util = float(util) if util is not None else None
    except (TypeError, ValueError):
        util = None
    candidate_id = str(
        cand.get("candidate_id")
        or cand.get("source_candidate_id")
        or payload.get("source_candidate_id")
        or payload.get("resolved_candidate_id")
        or resolved.get("candidate_id")
        or resolved.get("source_candidate_id")
        or f"candidate_{index:03d}"
    ).strip()
    title = str(
        cand.get("label")
        or cand.get("title")
        or item.get("title_main")
        or payload.get("resolved_candidate_label")
        or fallback_title
        or candidate_id
    ).strip()
    statuses = dict((cand.get("overview") or {}).get("statuses") or cand.get("statuses") or {})
    failed_family = None
    failed_status = None
    failed_util = None
    utils = dict((cand.get("overview") or {}).get("utils") or cand.get("utils") or {})
    for key, value in statuses.items():
        if str(value or "").upper() == "FAIL":
            failed_family = str(key)
            failed_status = str(value)
            try:
                failed_util = float(utils.get(key)) if utils.get(key) is not None else None
            except (TypeError, ValueError):
                failed_util = None
            break
    safe = bool(
        updates
        and bool(cand.get("is_compliant", cand.get("all_key_pass", False)))
        and util is not None
    )
    row = {
        "candidate_id": candidate_id,
        "title": title,
        "proposed_updates": dict(updates),
        "preview_util": util,
        "distance_to_band": _candidate_search_distance_to_band(util, target_low, target_high),
        "safe_executor_backed": bool(safe),
        "preview_pass": bool(cand.get("is_compliant", cand.get("all_key_pass", False))),
        "reaches_target_band": bool(util is not None and float(target_low) <= float(util) <= float(target_high)),
        "rejection_reason": None,
        "failed_check_family": failed_family,
        "failed_check_status": failed_status,
        "failed_check_util": failed_util,
        "candidate_complexity_score": cand.get("candidate_complexity_score"),
        "net_efficiency_delta": cand.get("net_efficiency_delta"),
        "material_proxy_before": cand.get("material_proxy_before"),
        "material_proxy_after": cand.get("material_proxy_after"),
        "material_proxy_delta": cand.get("material_proxy_delta"),
        "is_executable": bool(cand.get("is_executable", safe)),
        "advisory_only": bool(cand.get("advisory_only", not safe)),
        "affected_family": cand.get("affected_family") or cand.get("family") or cand.get("recommendation_family_tag"),
    }
    if not updates:
        row["rejection_reason"] = "empty_updates"
    elif util is None:
        row["rejection_reason"] = "preview_failed"
    elif not bool(cand.get("is_compliant", cand.get("all_key_pass", False))):
        row["rejection_reason"] = f"{failed_family or 'preview'}_would_fail"
    return row


def _align_guidance_items_to_candidate_search_evidence(
    guidance_items: list[dict] | None,
) -> list[dict]:
    """Keep displayed/apply payloads tied to the evidence-selected candidate."""
    out: list[dict] = []
    for item in list(guidance_items or []):
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        payload = dict(next_item.get("action_payload") or {})
        resolved = dict(next_item.get("resolved_candidate") or {})
        evidence = dict(
            next_item.get("candidate_search_evidence")
            or payload.get("candidate_search_evidence")
            or resolved.get("candidate_search_evidence")
            or {}
        )
        selected_updates = dict(evidence.get("selected_candidate_updates") or {})
        if not selected_updates:
            selected_id = str(evidence.get("selected_candidate_id") or "").strip()
            for row in list(evidence.get("target_band_candidates") or []) + list(
                evidence.get("rejected_target_band_candidates") or []
            ):
                row_dict = dict(row or {})
                if selected_id and str(row_dict.get("candidate_id") or "").strip() == selected_id:
                    selected_updates = dict(row_dict.get("proposed_updates") or {})
                    break
        if not selected_updates:
            out.append(next_item)
            continue

        selected_util = evidence.get("selected_candidate_util")
        selected_title = str(evidence.get("selected_candidate_title") or "").strip()
        selected_id = str(evidence.get("selected_candidate_id") or "").strip()
        payload["updates"] = dict(selected_updates)
        payload["resolved_candidate_updates"] = dict(selected_updates)
        if selected_util is not None:
            payload["resolved_candidate_post_util"] = selected_util
            payload["expected_governing_util"] = selected_util
            payload["resolved_candidate_reaches_target_band"] = bool(
                _candidate_search_distance_to_band(
                    selected_util,
                    float(evidence.get("target_low", EFFICIENCY_TARGET_UTIL_MIN) or EFFICIENCY_TARGET_UTIL_MIN),
                    float(evidence.get("target_high", EFFICIENCY_TARGET_UTIL_MAX) or EFFICIENCY_TARGET_UTIL_MAX),
                )
                == 0.0
            )
        payload["candidate_search_evidence"] = dict(evidence)
        if selected_id:
            payload["source_candidate_id"] = selected_id
            payload["resolved_candidate_id"] = selected_id
            next_item["candidate_id"] = selected_id
            next_item["source_candidate_id"] = selected_id
        next_item["action_payload"] = payload
        next_item["resolved_candidate_updates"] = dict(selected_updates)
        next_item["candidate_search_evidence"] = dict(evidence)
        if selected_title:
            next_item["resolved_candidate_label"] = selected_title
        resolved["updates"] = dict(selected_updates)
        if selected_util is not None:
            resolved["candidate_post_util"] = selected_util
            resolved["worst_util"] = selected_util
            resolved["candidate_reaches_target_band"] = bool(payload.get("resolved_candidate_reaches_target_band"))
        resolved["candidate_search_evidence"] = dict(evidence)
        if selected_id:
            resolved["candidate_id"] = selected_id
            resolved["source_candidate_id"] = selected_id
        next_item["resolved_candidate"] = resolved
        next_item["action_type"] = "apply_resolved_candidate"
        out.append(next_item)
    return out


def _build_candidate_search_evidence(
    *,
    selected_candidate: dict | None,
    all_candidates: list[dict],
    target_low: float,
    target_high: float,
    exhaustive: bool,
    search_scope: str,
    selected_title: str | None = None,
) -> dict:
    rows: list[dict] = []
    selected_obj = selected_candidate if isinstance(selected_candidate, dict) else {}
    selected_row_index = None
    for idx, cand in enumerate(list(all_candidates or []), start=1):
        row = _candidate_search_summary_row(
            cand,
            index=idx,
            target_low=target_low,
            target_high=target_high,
        )
        rows.append(row)
        if selected_obj and cand is selected_obj:
            selected_row_index = len(rows) - 1
    if selected_obj and selected_row_index is None:
        rows.insert(
            0,
            _candidate_search_summary_row(
                selected_obj,
                index=0,
                target_low=target_low,
                target_high=target_high,
                fallback_title=selected_title,
            ),
        )
        selected_row_index = 0
    safe_rows = [row for row in rows if bool(row.get("safe_executor_backed"))]
    target_rows = [
        row
        for row in safe_rows
        if row.get("preview_util") is not None
        and float(target_low) <= float(row.get("preview_util")) <= float(target_high)
    ]
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
    outside_allowed = bool(
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
    rejected_target_rows = [
        row
        for row in rows
        if bool(row.get("reaches_target_band")) and not bool(row.get("safe_executor_backed"))
    ]
    evidence = {
        "candidate_search_exhaustive": bool(exhaustive),
        "search_scope": str(search_scope or ""),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "total_candidates_considered": int(len(rows)),
        "safe_executor_backed_candidates_count": int(len(safe_rows)),
        "target_band_candidate_count": int(len(target_rows)),
        "selected_candidate_id": None if selected_row is None else selected_row.get("candidate_id"),
        "selected_candidate_title": None if selected_row is None else selected_row.get("title"),
        "selected_candidate_util": selected_util,
        "selected_candidate_distance_to_band": selected_distance,
        "selected_candidate_updates": (
            {}
            if selected_row is None
            else dict(selected_row.get("proposed_updates") or {})
        ),
        "closest_safe_candidate_id": None if closest_row is None else closest_row.get("candidate_id"),
        "closest_safe_candidate_title": None if closest_row is None else closest_row.get("title"),
        "closest_safe_candidate_util": None if closest_row is None else closest_row.get("preview_util"),
        "closest_safe_candidate_distance_to_band": closest_distance,
        "closest_safe_candidate_updates": (
            {}
            if closest_row is None
            else dict(closest_row.get("proposed_updates") or {})
        ),
        "best_target_band_candidate_id": None if best_target is None else best_target.get("candidate_id"),
        "best_target_band_candidate_title": None if best_target is None else best_target.get("title"),
        "best_target_band_candidate_util": None if best_target is None else best_target.get("preview_util"),
        "best_target_band_candidate_updates": (
            {}
            if best_target is None
            else dict(best_target.get("proposed_updates") or {})
        ),
        "target_band_candidates": [dict(row) for row in target_rows[:20]],
        "safe_executor_backed_candidates": [dict(row) for row in safe_rows[:40]],
        "rejected_target_band_candidates": [dict(row) for row in rejected_target_rows[:20]],
        "rejected_target_band_candidate_reasons": [
            str(row.get("rejection_reason") or "preview_failed")
            for row in rejected_target_rows[:20]
        ],
        "outside_target_band_allowed": bool(outside_allowed),
        "outside_target_band_allowed_reason": reason,
        "outside_target_band_allowed_category": category,
    }
    return evidence
