"""Design Brain optimisation evidence/proof helpers.

This module owns pure optimisation proof shaping and optimisation action
descriptors. It does not search for candidates, evaluate formulas, rank
candidates, apply updates, or render UI.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from design_brain.candidates import normalise_candidate_row
from design_brain.evidence import candidate_rows_from_evidence


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


_OPTIMISATION_FAMILY_DESCRIPTOR_ROWS: tuple[dict[str, object], ...] = (
    {
        "family": "bending_cleanup",
        "domain": "bending",
        "candidate_type": "reinforcement_cleanup",
        "intent": "reduce unnecessary bending reinforcement while preserving required checks",
        "proof_family": "bending",
    },
    {
        "family": "shear_cleanup",
        "domain": "shear",
        "candidate_type": "shear_reinforcement_cleanup",
        "intent": "reduce unnecessary shear reinforcement while preserving required checks",
        "proof_family": "shear",
    },
    {
        "family": "geometry_cleanup",
        "domain": "geometry",
        "candidate_type": "geometry_cleanup",
        "intent": "reduce section geometry where permitted while preserving required checks",
        "proof_family": "combined",
    },
    {
        "family": "reinforcement_cleanup",
        "domain": "reinforcement",
        "candidate_type": "reinforcement_cleanup",
        "intent": "reduce unnecessary reinforcement where permitted",
        "proof_family": "combined",
    },
    {
        "family": "combined_cleanup",
        "domain": "combined",
        "candidate_type": "combined_cleanup",
        "intent": "combine safe shear, bending, and geometry cleanup when one family alone is insufficient",
        "proof_family": "combined",
    },
    {
        "family": "zero_demand_bending_cleanup",
        "domain": "bending",
        "candidate_type": "zero_demand_exclusion",
        "intent": "mark zero or non-meaningful bending demand as non-governing for cleanup proof",
        "proof_family": "bending",
    },
    {
        "family": "target_band_cleanup",
        "domain": "target_band",
        "candidate_type": "target_band_cleanup",
        "intent": "prefer a safe cleanup candidate in the accepted utilisation band where practical",
        "proof_family": "combined",
    },
    {
        "family": "exact_stop_cleanup",
        "domain": "exact_stop",
        "candidate_type": "exact_stop_cleanup",
        "intent": "publish engineering proof when no safe target-band cleanup remains",
        "proof_family": "combined",
    },
)

_CLEANUP_OPTION_DESCRIPTOR_ROWS: tuple[dict[str, object], ...] = (
    {
        "spec_id": "reduce_bottom_reinforcement",
        "family": "bending_cleanup",
        "candidate_family": "bending",
        "candidate_type": "reinforcement_cleanup",
        "update_family": "bottom_reinforcement",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "simplify_bottom_layout",
        "family": "bending_cleanup",
        "candidate_family": "bending",
        "candidate_type": "layout_cleanup",
        "update_family": "bottom_reinforcement_layout",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "reduce_top_reinforcement",
        "family": "bending_cleanup",
        "candidate_family": "bending",
        "candidate_type": "top_reinforcement_cleanup",
        "update_family": "top_reinforcement",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "increase_shear_spacing",
        "family": "shear_cleanup",
        "candidate_family": "shear",
        "candidate_type": "shear_spacing_cleanup",
        "update_family": "shear_spacing",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "reduce_shear_legs",
        "family": "shear_cleanup",
        "candidate_family": "shear",
        "candidate_type": "shear_leg_cleanup",
        "update_family": "shear_legs",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "reduce_shear_diameter",
        "family": "shear_cleanup",
        "candidate_family": "shear",
        "candidate_type": "shear_diameter_cleanup",
        "update_family": "shear_diameter",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "remove_zero_demand_shear_links",
        "family": "shear_cleanup",
        "candidate_family": "shear",
        "candidate_type": "zero_link_cleanup",
        "update_family": "shear_links",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "reduce_depth",
        "family": "geometry_cleanup",
        "candidate_family": "geometry",
        "candidate_type": "depth_cleanup",
        "update_family": "section_depth",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "reduce_width",
        "family": "geometry_cleanup",
        "candidate_family": "geometry",
        "candidate_type": "width_cleanup",
        "update_family": "section_width",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "combined_shear_bending_cleanup",
        "family": "combined_cleanup",
        "candidate_family": "combined",
        "candidate_type": "combined_cleanup",
        "update_family": "combined_reinforcement",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "combined_geometry_reinforcement_cleanup",
        "family": "combined_cleanup",
        "candidate_family": "combined",
        "candidate_type": "combined_geometry_cleanup",
        "update_family": "combined_geometry_reinforcement",
        "target_band_role": "cleanup_candidate",
        "exact_stop_role": "attempted_reduction",
    },
    {
        "spec_id": "zero_demand_bending_exclusion",
        "family": "zero_demand_bending_cleanup",
        "candidate_family": "bending",
        "candidate_type": "zero_demand_exclusion",
        "update_family": "none",
        "target_band_role": "not_optimisation_governing",
        "exact_stop_role": "cleanup_proof_not_required",
    },
)

_TARGET_BAND_CANDIDATE_DESCRIPTOR_ROWS: tuple[dict[str, object], ...] = (
    {
        "spec_id": "bending_target_band_cleanup",
        "family": "target_band_cleanup",
        "candidate_family": "bending",
        "candidate_type": "target_band_cleanup",
        "target_band_role": "bring_bending_into_band",
        "exact_stop_role": "not_exact_stop",
    },
    {
        "spec_id": "shear_target_band_cleanup",
        "family": "target_band_cleanup",
        "candidate_family": "shear",
        "candidate_type": "target_band_cleanup",
        "target_band_role": "bring_shear_into_band",
        "exact_stop_role": "not_exact_stop",
    },
    {
        "spec_id": "combined_target_band_cleanup",
        "family": "target_band_cleanup",
        "candidate_family": "combined",
        "candidate_type": "target_band_cleanup",
        "target_band_role": "bring_any_major_family_into_band",
        "exact_stop_role": "not_exact_stop",
    },
)

_EXACT_STOP_CANDIDATE_DESCRIPTOR_ROWS: tuple[dict[str, object], ...] = (
    {
        "spec_id": "bending_cleanup_exact_stop",
        "family": "exact_stop_cleanup",
        "candidate_family": "bending",
        "candidate_type": "exact_stop_cleanup",
        "target_band_role": "target_not_reachable",
        "exact_stop_role": "bending_cleanup_exhausted",
    },
    {
        "spec_id": "shear_cleanup_exact_stop",
        "family": "exact_stop_cleanup",
        "candidate_family": "shear",
        "candidate_type": "exact_stop_cleanup",
        "target_band_role": "target_not_reachable",
        "exact_stop_role": "shear_cleanup_exhausted",
    },
    {
        "spec_id": "geometry_cleanup_exact_stop",
        "family": "exact_stop_cleanup",
        "candidate_family": "geometry",
        "candidate_type": "exact_stop_cleanup",
        "target_band_role": "target_not_reachable",
        "exact_stop_role": "geometry_cleanup_exhausted",
    },
    {
        "spec_id": "combined_cleanup_exact_stop",
        "family": "exact_stop_cleanup",
        "candidate_family": "combined",
        "candidate_type": "exact_stop_cleanup",
        "target_band_role": "target_not_reachable",
        "exact_stop_role": "combined_cleanup_exhausted",
    },
)


def _copy_descriptor_rows(rows: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    return [dict(row) for row in rows]


def build_optimisation_family_descriptors() -> list[dict[str, object]]:
    """Return stable optimisation family descriptors without generating candidates."""
    return _copy_descriptor_rows(_OPTIMISATION_FAMILY_DESCRIPTOR_ROWS)


def build_cleanup_option_descriptors() -> list[dict[str, object]]:
    """Return static cleanup option descriptors without live state or evaluation."""
    return _copy_descriptor_rows(_CLEANUP_OPTION_DESCRIPTOR_ROWS)


def build_target_band_candidate_descriptors() -> list[dict[str, object]]:
    """Return static target-band cleanup descriptors without searching."""
    return _copy_descriptor_rows(_TARGET_BAND_CANDIDATE_DESCRIPTOR_ROWS)


def build_exact_stop_candidate_descriptors() -> list[dict[str, object]]:
    """Return static exact-stop cleanup descriptors without proving blockers."""
    return _copy_descriptor_rows(_EXACT_STOP_CANDIDATE_DESCRIPTOR_ROWS)


def build_optimisation_candidate_blueprints() -> list[dict[str, object]]:
    """Return all static optimisation candidate blueprint descriptors."""
    return (
        build_cleanup_option_descriptors()
        + build_target_band_candidate_descriptors()
        + build_exact_stop_candidate_descriptors()
    )


def build_optimisation_spec_catalog() -> dict[str, object]:
    """Return the static optimisation descriptor catalog and descriptor counts."""
    families = build_optimisation_family_descriptors()
    cleanup_options = build_cleanup_option_descriptors()
    target_band_candidates = build_target_band_candidate_descriptors()
    exact_stop_candidates = build_exact_stop_candidate_descriptors()
    return {
        "families": families,
        "cleanup_options": cleanup_options,
        "target_band_candidates": target_band_candidates,
        "exact_stop_candidates": exact_stop_candidates,
        "descriptor_counts": {
            "families": len(families),
            "cleanup_options": len(cleanup_options),
            "target_band_candidates": len(target_band_candidates),
            "exact_stop_candidates": len(exact_stop_candidates),
            "candidate_blueprints": len(cleanup_options) + len(target_band_candidates) + len(exact_stop_candidates),
        },
    }


def _candidate_item_payload_resolved(candidate: dict | None) -> tuple[dict, dict, dict]:
    cand = dict(candidate or {})
    item = dict(cand.get("item") or {})
    payload = dict(item.get("action_payload") or cand.get("action_payload") or {})
    resolved = dict(item.get("resolved_candidate") or cand.get("resolved_candidate") or {})
    return item, payload, resolved


def optimisation_cleanup_candidate_id(
    family: str,
    updates: dict,
    *,
    fingerprint_payload: Callable[[dict], object] | None = None,
) -> str:
    """Build the stable local cleanup candidate ID without generating candidates."""
    try:
        if fingerprint_payload is None:
            raise ValueError("fingerprint_payload_missing")
        fp = fingerprint_payload({"family": family, "updates": dict(updates or {})})
        return f"local_cleanup:{family}:{fp}"
    except Exception:
        updates_map = dict(updates or {})
        sig = ",".join(f"{key}={updates_map[key]}" for key in sorted(updates_map))
        return f"local_cleanup:{family}:{sig}"


def optimisation_candidate_updates(candidate: dict | None) -> dict:
    """Extract optimisation candidate updates using the existing fallback order."""
    cand = dict(candidate or {})
    _item, payload, resolved = _candidate_item_payload_resolved(cand)
    return dict(
        cand.get("updates")
        or cand.get("resolved_candidate_updates")
        or payload.get("resolved_candidate_updates")
        or payload.get("updates")
        or resolved.get("updates")
        or {}
    )


def optimisation_candidate_id(candidate: dict | None, *, index: int) -> str:
    """Extract optimisation candidate ID using the existing fallback order."""
    cand = dict(candidate or {})
    _item, payload, resolved = _candidate_item_payload_resolved(cand)
    return str(
        cand.get("candidate_id")
        or cand.get("source_candidate_id")
        or payload.get("source_candidate_id")
        or payload.get("resolved_candidate_id")
        or resolved.get("candidate_id")
        or resolved.get("source_candidate_id")
        or f"candidate_{int(index):03d}"
    ).strip()


def optimisation_candidate_label(
    candidate: dict | None,
    *,
    candidate_id: str,
    fallback_title: str | None = None,
) -> str:
    """Extract optimisation candidate label using the existing fallback order."""
    cand = dict(candidate or {})
    item, payload, _resolved = _candidate_item_payload_resolved(cand)
    return str(
        cand.get("label")
        or cand.get("title")
        or item.get("title_main")
        or payload.get("resolved_candidate_label")
        or fallback_title
        or candidate_id
    ).strip()


def optimisation_candidate_preview_util(candidate: dict | None) -> float | None:
    """Extract the preview/post util used by optimisation candidate metadata."""
    cand = dict(candidate or {})
    _item, payload, _resolved = _candidate_item_payload_resolved(cand)
    util = cand.get("candidate_post_util", cand.get("trial_worst_util", cand.get("worst_util")))
    if util is None:
        util = payload.get("resolved_candidate_post_util")
    try:
        return float(util) if util is not None else None
    except (TypeError, ValueError):
        return None


def optimisation_candidate_preview_pass(candidate: dict | None) -> bool:
    cand = dict(candidate or {})
    return bool(cand.get("is_compliant", cand.get("all_key_pass", False)))


def optimisation_candidate_safe_executor_backed(
    candidate: dict | None,
    *,
    updates: dict | None = None,
    preview_util: float | None = None,
) -> bool:
    """Return existing safe/executor-backed metadata without deciding outcomes."""
    return bool(
        dict(updates or {})
        and optimisation_candidate_preview_pass(candidate)
        and preview_util is not None
    )


def optimisation_candidate_is_executable(candidate: dict | None, *, safe_executor_backed: bool) -> bool:
    cand = dict(candidate or {})
    return bool(cand.get("is_executable", safe_executor_backed))


def optimisation_candidate_advisory_only(candidate: dict | None, *, safe_executor_backed: bool) -> bool:
    cand = dict(candidate or {})
    return bool(cand.get("advisory_only", not safe_executor_backed))


def optimisation_candidate_family(candidate: dict | None) -> Any:
    cand = dict(candidate or {})
    return cand.get("affected_family") or cand.get("family") or cand.get("recommendation_family_tag")


def optimisation_candidate_type(candidate: dict | None) -> Any:
    cand = dict(candidate or {})
    return (
        cand.get("candidate_type")
        or cand.get("cleanup_type")
        or cand.get("optimisation_type")
        or cand.get("action_type")
    )


def optimisation_candidate_metadata(
    candidate: dict | None,
    *,
    index: int,
    fallback_title: str | None = None,
) -> dict[str, Any]:
    """Normalise pure optimisation metadata over an already-built candidate."""
    candidate_id = optimisation_candidate_id(candidate, index=index)
    updates = optimisation_candidate_updates(candidate)
    preview_util = optimisation_candidate_preview_util(candidate)
    safe = optimisation_candidate_safe_executor_backed(candidate, updates=updates, preview_util=preview_util)
    return {
        "candidate_id": candidate_id,
        "label": optimisation_candidate_label(candidate, candidate_id=candidate_id, fallback_title=fallback_title),
        "updates": dict(updates),
        "preview_util": preview_util,
        "preview_pass": optimisation_candidate_preview_pass(candidate),
        "safe_executor_backed": safe,
        "is_executable": optimisation_candidate_is_executable(candidate, safe_executor_backed=safe),
        "advisory_only": optimisation_candidate_advisory_only(candidate, safe_executor_backed=safe),
        "family": optimisation_candidate_family(candidate),
        "candidate_type": optimisation_candidate_type(candidate),
    }


def optimisation_descriptor_for_family(family: str) -> dict[str, object]:
    target = str(family or "").strip().lower()
    for row in _OPTIMISATION_FAMILY_DESCRIPTOR_ROWS:
        if str(row.get("family") or "").strip().lower() == target:
            return dict(row)
    return {}


def optimisation_descriptor_for_spec(spec_id: str) -> dict[str, object]:
    target = str(spec_id or "").strip().lower()
    for row in (
        _CLEANUP_OPTION_DESCRIPTOR_ROWS
        + _TARGET_BAND_CANDIDATE_DESCRIPTOR_ROWS
        + _EXACT_STOP_CANDIDATE_DESCRIPTOR_ROWS
    ):
        if str(row.get("spec_id") or "").strip().lower() == target:
            return dict(row)
    return {}


def optimisation_candidate_search_distance_to_band(
    util: object,
    target_low: float,
    target_high: float,
) -> float | None:
    """Return the verifier-row distance to target band without searching."""
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


def optimisation_candidate_search_summary_row(
    candidate: dict | None,
    *,
    index: int,
    target_low: float,
    target_high: float,
    fallback_title: str | None = None,
    parse_util: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    """Shape one already-built optimisation candidate into a verifier row."""
    cand = dict(candidate or {})
    metadata = optimisation_candidate_metadata(
        cand,
        index=index,
        fallback_title=fallback_title,
    )
    updates = dict(metadata.get("updates") or {})
    util = metadata.get("preview_util")
    candidate_id = str(metadata.get("candidate_id") or "").strip()
    title = str(metadata.get("label") or "").strip()
    statuses = dict((cand.get("overview") or {}).get("statuses") or cand.get("statuses") or {})
    failed_family = None
    failed_status = None
    failed_util = None
    utils = dict((cand.get("overview") or {}).get("utils") or cand.get("utils") or {})
    util_parser = parse_util or _as_float
    preview_bending_util = util_parser(utils.get("bending"))
    preview_shear_util = util_parser(utils.get("shear"))
    for key, value in statuses.items():
        if str(value or "").upper() == "FAIL":
            failed_family = str(key)
            failed_status = str(value)
            try:
                failed_util = float(utils.get(key)) if utils.get(key) is not None else None
            except (TypeError, ValueError):
                failed_util = None
            break
    safe = bool(metadata.get("safe_executor_backed"))
    row = {
        "candidate_id": candidate_id,
        "title": title,
        "proposed_updates": dict(updates),
        "preview_util": util,
        "preview_bending_util": preview_bending_util,
        "preview_shear_util": preview_shear_util,
        "preview_statuses": dict(statuses),
        "distance_to_band": optimisation_candidate_search_distance_to_band(util, target_low, target_high),
        "safe_executor_backed": bool(safe),
        "preview_pass": bool(metadata.get("preview_pass")),
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
        "is_executable": bool(metadata.get("is_executable")),
        "advisory_only": bool(metadata.get("advisory_only")),
        "affected_family": metadata.get("family"),
    }
    if not updates:
        row["rejection_reason"] = "empty_updates"
    elif util is None:
        row["rejection_reason"] = "preview_failed"
    elif not bool(cand.get("is_compliant", cand.get("all_key_pass", False))):
        row["rejection_reason"] = f"{failed_family or 'preview'}_would_fail"
    return row


def optimisation_safe_executor_backed_rows(rows: list[dict] | tuple[dict, ...]) -> list[dict]:
    """Return safe executor-backed rows, preserving input order and row objects."""
    return [row for row in list(rows or []) if bool(row.get("safe_executor_backed"))]


def optimisation_target_band_rows(
    rows: list[dict] | tuple[dict, ...],
    *,
    target_low: float,
    target_high: float,
) -> list[dict]:
    """Return safe rows inside the target band, preserving input order."""
    return [
        row
        for row in list(rows or [])
        if row.get("preview_util") is not None
        and float(target_low) <= float(row.get("preview_util")) <= float(target_high)
    ]


def optimisation_rejected_target_band_rows(rows: list[dict] | tuple[dict, ...]) -> list[dict]:
    """Return rows that reach target band but are not safe executor-backed."""
    return [
        row
        for row in list(rows or [])
        if bool(row.get("reaches_target_band")) and not bool(row.get("safe_executor_backed"))
    ]


def optimisation_copy_row_slice(rows: list[dict] | tuple[dict, ...], limit: int) -> list[dict]:
    """Copy a bounded row slice without changing order or row values."""
    return [dict(row) for row in list(rows or [])[: int(limit)]]


def optimisation_candidate_search_count_statistics(
    *,
    all_candidates: list[dict] | tuple[dict, ...] | None,
    rows: list[dict] | tuple[dict, ...],
    safe_rows: list[dict] | tuple[dict, ...],
    target_rows: list[dict] | tuple[dict, ...],
) -> dict[str, int]:
    """Return verifier-visible candidate-search count fields without changing keys."""
    row_count = int(len(rows or []))
    return {
        "generated_count": int(len(all_candidates or [])),
        "deduped_count": row_count,
        "preview_count": row_count,
        "total_candidates_considered": row_count,
        "safe_executor_backed_candidates_count": int(len(safe_rows or [])),
        "target_band_candidate_count": int(len(target_rows or [])),
    }


def optimisation_selected_candidate_fields(
    selected_row: dict | None,
    selected_row_index: int | None,
) -> dict[str, Any]:
    """Copy verifier-visible selected-candidate fields from an already-resolved row."""
    row = selected_row if isinstance(selected_row, dict) else None
    return {
        "selected_rank": None if selected_row_index is None else int(selected_row_index) + 1,
        "selected_candidate_id": None if row is None else row.get("candidate_id"),
        "selected_candidate_title": None if row is None else row.get("title"),
        "selected_candidate_util": None if row is None else row.get("preview_util"),
        "selected_candidate_distance_to_band": None if row is None else row.get("distance_to_band"),
        "selected_candidate_updates": {} if row is None else dict(row.get("proposed_updates") or {}),
    }


def optimisation_closest_safe_candidate_fields(closest_row: dict | None) -> dict[str, Any]:
    """Copy verifier-visible closest-safe fields from an already-resolved row."""
    row = closest_row if isinstance(closest_row, dict) else None
    return {
        "closest_safe_candidate_id": None if row is None else row.get("candidate_id"),
        "closest_safe_candidate_title": None if row is None else row.get("title"),
        "closest_safe_candidate_util": None if row is None else row.get("preview_util"),
        "closest_safe_candidate_distance_to_band": None if row is None else row.get("distance_to_band"),
        "closest_safe_candidate_updates": {} if row is None else dict(row.get("proposed_updates") or {}),
    }


def optimisation_best_target_band_candidate_fields(best_target: dict | None) -> dict[str, Any]:
    """Copy verifier-visible best-target fields from an already-resolved row."""
    row = best_target if isinstance(best_target, dict) else None
    return {
        "best_target_band_candidate_id": None if row is None else row.get("candidate_id"),
        "best_target_band_candidate_title": None if row is None else row.get("title"),
        "best_target_band_candidate_util": None if row is None else row.get("preview_util"),
        "best_target_band_candidate_updates": {} if row is None else dict(row.get("proposed_updates") or {}),
    }


def safe_combined_cleanup_proof(
    evidence: dict,
    primary: dict,
    contract: dict,
    *,
    contract_enabled: Callable[[dict], bool],
) -> dict:
    target_id = "combined_best_safe_shear_plus_bending_cleanup"
    proof: dict[str, Any] = {
        "safe_cleanup_candidate_found": False,
        "candidate_id": None,
        "candidate_family": None,
        "executor_backed": False,
        "preview_pass": None,
        "expected_utilisation": None,
        "updates": {},
        "label": None,
        "final_published_outcome": None,
        "final_cta_enabled": bool(contract_enabled(contract)),
        "blocker_reason": contract.get("blocking_reason") or primary.get("reason") or primary.get("reasoning"),
    }
    rows = candidate_rows_from_evidence(evidence)
    matching_rows = []
    for row in rows:
        row_id = str(row.get("candidate_id") or row.get("id") or "")
        row_title = str(row.get("title") or row.get("label") or "")
        if target_id not in row_id and target_id not in row_title:
            continue
        matching_rows.append(dict(row))
    matching_rows.sort(
        key=lambda row: (
            row.get("preview_pass") is True,
            bool(row.get("safe_executor_backed") or row.get("executor_backed") or row.get("is_executable")),
            bool(
                row.get("updates")
                or row.get("proposed_updates")
                or row.get("selected_candidate_updates")
                or row.get("best_safe_candidate_updates")
            ),
        ),
        reverse=True,
    )
    for row in matching_rows:
        candidate = normalise_candidate_row(row, fallback_id=target_id)
        proof.update(
            {
                "safe_cleanup_candidate_found": True,
                "candidate_id": candidate.get("candidate_id") or target_id,
                "candidate_family": candidate.get("family") or "combined",
                "executor_backed": bool(candidate.get("executor_backed")),
                "preview_pass": candidate.get("preview_pass"),
                "expected_utilisation": candidate.get("expected_utilisation"),
                "updates": dict(candidate.get("updates") or {}),
                "label": candidate.get("label"),
            }
        )
        break
    if not proof["safe_cleanup_candidate_found"] and str(evidence.get("selected_candidate_id") or "") == target_id:
        proof.update(
            {
                "safe_cleanup_candidate_found": True,
                "candidate_id": target_id,
                "candidate_family": "combined",
                "executor_backed": bool(evidence.get("selected_candidate_updates")),
                "expected_utilisation": _as_float(evidence.get("selected_candidate_util")),
                "updates": _as_dict(evidence.get("selected_candidate_updates")),
                "label": evidence.get("selected_candidate_title"),
            }
        )
    return proof


def exact_stop_evidence_by_family(evidence: dict) -> dict:
    merged: dict[str, dict] = {}
    for source in (
        evidence.get("exact_blockers_by_family"),
        evidence.get("post_click_exact_blockers_by_family"),
        evidence.get("cleanup_evidence_by_family"),
        evidence.get("post_click_cleanup_evidence_by_family"),
        evidence.get("blocker_attempts_by_family"),
    ):
        if not isinstance(source, dict):
            continue
        for family, row in source.items():
            if str(family or "").strip() and isinstance(row, dict):
                merged[str(family).strip().lower()] = dict(row)
    return merged


def optimisation_search_exhaustive(evidence: dict) -> bool:
    return bool(
        evidence.get("cleanup_search_exhaustive")
        or evidence.get("local_cleanup_search_exhaustive")
        or evidence.get("optimisation_search_exhaustive")
        or evidence.get("target_band_search_exhaustive")
        or evidence.get("repair_or_target_band_search_exhaustive")
    )


def clean_safe_combined_evidence(
    evidence: dict,
    *,
    candidate_id: str,
    updates: dict,
    label: str | None,
    expected: Any,
) -> dict:
    cleaned = dict(evidence or {})
    for stale_key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    ):
        cleaned.pop(stale_key, None)
    cleaned.update(
        {
            "family": "combined",
            "selected_candidate_id": candidate_id,
            "best_safe_candidate_id": candidate_id,
            "closest_safe_candidate_id": candidate_id,
            "selected_candidate_updates": dict(updates),
            "best_safe_candidate_updates": dict(updates),
            "closest_safe_candidate_updates": dict(updates),
            "selected_candidate_title": label or "Shear and bending cleanup - one-click optimisation",
            "safe_cleanup_candidate_found": True,
            "safe_candidate_count": max(1, int(cleaned.get("safe_candidate_count") or 0)),
            "safe_cleanup_count": max(1, int(cleaned.get("safe_cleanup_count") or 0)),
            "executable_candidate_count": max(1, int(cleaned.get("executable_candidate_count") or 0)),
            "executable_cleanup_count": max(1, int(cleaned.get("executable_cleanup_count") or 0)),
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "best_safe_candidate_applied": False,
            "best_safe_partial_cleanup": True,
            "no_second_cta_required": False,
            "outside_target_band_allowed": False,
        }
    )
    expected_value = _as_float(expected)
    if expected_value is not None:
        cleaned["selected_candidate_util"] = expected_value
        cleaned["best_safe_final_util"] = expected_value
        cleaned["closest_safe_candidate_util"] = expected_value
    return cleaned


__all__ = [
    "build_cleanup_option_descriptors",
    "build_exact_stop_candidate_descriptors",
    "build_optimisation_candidate_blueprints",
    "build_optimisation_family_descriptors",
    "build_optimisation_spec_catalog",
    "build_target_band_candidate_descriptors",
    "clean_safe_combined_evidence",
    "exact_stop_evidence_by_family",
    "optimisation_best_target_band_candidate_fields",
    "optimisation_candidate_advisory_only",
    "optimisation_candidate_family",
    "optimisation_candidate_id",
    "optimisation_candidate_is_executable",
    "optimisation_candidate_label",
    "optimisation_candidate_metadata",
    "optimisation_candidate_preview_pass",
    "optimisation_candidate_preview_util",
    "optimisation_candidate_search_count_statistics",
    "optimisation_candidate_search_distance_to_band",
    "optimisation_candidate_search_summary_row",
    "optimisation_candidate_safe_executor_backed",
    "optimisation_candidate_type",
    "optimisation_candidate_updates",
    "optimisation_cleanup_candidate_id",
    "optimisation_closest_safe_candidate_fields",
    "optimisation_copy_row_slice",
    "optimisation_descriptor_for_family",
    "optimisation_descriptor_for_spec",
    "optimisation_rejected_target_band_rows",
    "optimisation_safe_executor_backed_rows",
    "optimisation_search_exhaustive",
    "optimisation_selected_candidate_fields",
    "optimisation_target_band_rows",
    "safe_combined_cleanup_proof",
]
