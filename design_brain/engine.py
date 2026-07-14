"""Pure Design Guide card resolver.

This module owns the final Design Guide card decision, copy, button contract,
display-truth stamping, and target-band outcome. It intentionally does not
generate candidates or apply updates.
"""

from __future__ import annotations

import os
from typing import Any

from optimisation_config import get_target_utilisation_band, target_band_payload
from design_brain.ranking import distance_to_band, selection_sort_key


ENGINE_INTENTS = frozenset(
    {
        "required_fix",
        "efficiency_tightening",
        "optional_cleanup",
        "already_efficient",
        "specific_blocker",
    }
)

_COMPAT_INTENTS = frozenset(
    {
        "required_fix",
        "efficiency_tightening",
        "optional_cleanup",
        "already_efficient",
        "advisory_warning",
        "specific_blocker",
    }
)

ALLOWED_OUTSIDE_TARGET_CATEGORIES = frozenset(
    {
        "bending_would_fail",
        "shear_would_fail",
        "ductility_would_fail",
        "spacing_or_detailing_would_fail",
        "serviceability_would_fail",
        "crack_would_fail",
        "deflection_would_fail",
        "torsion_would_fail",
        "geometry_lock",
        "reinforcement_lock",
        "shear_lock",
        "empty_updates",
        "not_executor_backed",
        "preview_failed",
        "discrete_increment_limit",
        "practical_limit",
        "no_material_candidate_reached_target",
    }
)

FORBIDDEN_OUTSIDE_TARGET_CATEGORIES = frozenset(
    {
        "under_current_rules",
        "manual_review",
        "no_candidate_attached",
        "move_set_failed",
        "unknown",
    }
)

SHEAR_FAIL_FAMILY_ROUTING_ENV = "DESIGN_BRAIN_SHEAR_FAIL_FAMILY_ROUTING"
COMBINED_FAIL_FAMILY_ROUTING_ENV = "DESIGN_BRAIN_COMBINED_FAIL_FAMILY_ROUTING"


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool:
    return bool(value)


def _item_display_family(item: dict | None) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("family", "selected_action_family", "recommendation_family_tag", "check_key"):
        value = str(item.get(key) or "").strip().lower()
        if value in {"bending", "shear"}:
            return value
        if value == "combined":
            return "combined"
    title_text = " ".join(
        str(item.get(key) or "")
        for key in ("title_main", "title", "label", "primary_action", "guidance_why")
    ).lower()
    mentions_bending = "bending" in title_text
    mentions_shear = "shear" in title_text
    if mentions_bending and not mentions_shear:
        return "bending"
    if mentions_shear and not mentions_bending:
        return "shear"
    if mentions_bending and mentions_shear:
        return "combined"
    return None


def _summary_family_util(summary: dict | None, family: str | None) -> float | None:
    family_key = str(family or "").strip().lower()
    if family_key not in {"bending", "shear"}:
        return None
    ov = _as_dict(summary)
    utils = _as_dict(ov.get("utils"))
    value = utils.get(family_key)
    if value is None:
        value = ov.get(f"{family_key}_util")
    return _as_float(value)


def _target_band(goal: str | None, payload: dict | None) -> dict:
    if isinstance(payload, dict):
        lo = _as_float(payload.get("target_low"))
        hi = _as_float(payload.get("target_high"))
        if lo is not None and hi is not None and lo < hi:
            out = dict(payload)
            out.setdefault("goal", goal or payload.get("goal") or "balanced")
            out.setdefault("source", "canonical_config")
            return out
    return target_band_payload(goal or "balanced")


def _distance_to_band(util: float | None, lo: float, hi: float) -> float | None:
    return distance_to_band(util, lo, hi)


def _candidate_nested_dict(candidate: dict, key: str) -> dict:
    return _as_dict(candidate.get(key))


def _candidate_id(candidate: dict) -> str | None:
    payload = _candidate_nested_dict(candidate, "action_payload")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    contract = _candidate_nested_dict(candidate, "button_contract")
    value = (
        candidate.get("candidate_id")
        or candidate.get("source_candidate_id")
        or candidate.get("id")
        or contract.get("source_candidate_id")
        or contract.get("candidate_id")
        or payload.get("source_candidate_id")
        or payload.get("candidate_id")
        or resolved.get("candidate_id")
        or resolved.get("source_candidate_id")
        or resolved.get("id")
    )
    return None if value is None else str(value)


def _candidate_title(candidate: dict) -> str:
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    payload = _candidate_nested_dict(candidate, "action_payload")
    return str(
        candidate.get("title")
        or candidate.get("title_main")
        or candidate.get("label")
        or candidate.get("canonical_winner_label")
        or payload.get("resolved_candidate_label")
        or resolved.get("label")
        or resolved.get("title")
        or "Design Guide candidate"
    )


def _candidate_family(candidate: dict) -> str | None:
    contract = _candidate_nested_dict(candidate, "button_contract")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    payload = _candidate_nested_dict(candidate, "action_payload")
    value = (
        contract.get("family")
        or candidate.get("family")
        or candidate.get("check_key")
        or candidate.get("_tightening_family")
        or candidate.get("governing_family")
        or payload.get("family")
        or resolved.get("family")
    )
    return None if value is None else str(value)


def _candidate_action_type(candidate: dict) -> str | None:
    contract = _candidate_nested_dict(candidate, "button_contract")
    payload = _candidate_nested_dict(candidate, "action_payload")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    value = (
        contract.get("action_type")
        or candidate.get("action_type")
        or payload.get("resolved_candidate_action_type")
        or payload.get("action_type")
        or resolved.get("action_type")
    )
    return None if value is None else str(value)


def _candidate_updates(candidate: dict) -> dict:
    contract = _candidate_nested_dict(candidate, "button_contract")
    payload = _candidate_nested_dict(candidate, "action_payload")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    return _as_dict(
        contract.get("updates")
        or payload.get("resolved_candidate_updates")
        or payload.get("updates")
        or resolved.get("updates")
        or candidate.get("updates")
        or candidate.get("raw_updates")
        or candidate.get("proposed_updates")
    )


_GEOMETRY_UPDATE_KEYS = frozenset({"b", "bw", "D"})
_BOTTOM_REO_UPDATE_PREFIXES = ("bot", "db_bot")
_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig", "shear_links", "shear_spacing"})


def _candidate_affects_family(family: str, updates: dict) -> bool:
    fam = str(family or "").strip().lower()
    keys = {str(k) for k in dict(updates or {})}
    has_geometry = bool(keys & _GEOMETRY_UPDATE_KEYS)
    has_bottom = any(k.startswith(_BOTTOM_REO_UPDATE_PREFIXES) for k in keys)
    has_shear = bool(keys & _SHEAR_UPDATE_KEYS)
    if fam == "shear":
        return has_shear
    if fam in {"bending", "bottom_reo"}:
        return bool(has_bottom or has_geometry)
    if fam in {"crack", "deflection", "serviceability"}:
        return bool(has_bottom or has_geometry)
    if fam == "geometry":
        return has_geometry
    return False


def _candidate_advisory_only(candidate: dict) -> bool:
    raw = _as_dict(candidate.get("raw")) or candidate
    contract = _candidate_nested_dict(raw, "button_contract")
    for value in (
        raw.get("advisory_only"),
        contract.get("advisory_only"),
        _candidate_nested_dict(raw, "resolved_candidate").get("advisory_only"),
    ):
        if value is not None:
            return bool(value)
    return False


def _candidate_net_efficiency_delta(candidate: dict) -> float | None:
    raw = _as_dict(candidate.get("raw")) or candidate
    for key in ("net_efficiency_delta",):
        parsed = _as_float(candidate.get(key))
        if parsed is not None:
            return parsed
        parsed = _as_float(raw.get(key))
        if parsed is not None:
            return parsed
    material_delta = _as_float(candidate.get("material_proxy_delta"))
    if material_delta is None:
        material_delta = _as_float(raw.get("material_proxy_delta"))
    if material_delta is not None:
        return -float(material_delta)
    return None


def _state_float(state: dict, key: str, default: float = 0.0) -> float:
    parsed = _as_float(_as_dict(state).get(key))
    return float(default if parsed is None else parsed)


def _candidate_material_proxy_from_updates(state: dict, updates: dict) -> tuple[float, float]:
    current = _as_dict(state)
    proposed = {**current, **dict(updates or {})}
    def _proxy(st: dict) -> float:
        width = _state_float(st, "b", _state_float(st, "bw", 0.0))
        depth = _state_float(st, "D", 0.0)
        bot_count = max(_state_float(st, "bot_row_1_bars", _state_float(st, "bot1_count", 0.0)), 0.0)
        bot_dia = max(_state_float(st, "bot_row_1_dia", _state_float(st, "db_bot_1", 0.0)), 0.0)
        bot2_count = max(_state_float(st, "bot_row_2_bars", _state_float(st, "bot2_count", 0.0)), 0.0)
        bot2_dia = max(_state_float(st, "bot_row_2_dia", _state_float(st, "db_bot_2", bot_dia)), 0.0)
        ast_proxy = bot_count * bot_dia * bot_dia + bot2_count * bot2_dia * bot2_dia
        lig_d = max(_state_float(st, "lig_d", 0.0), 0.0)
        lig_legs = max(_state_float(st, "lig_legs", 0.0), 0.0)
        spacing = max(_state_float(st, "s_lig", 1.0), 1.0)
        shear_proxy = lig_legs * lig_d * lig_d / spacing
        return width * depth * 0.001 + ast_proxy * 0.04 + shear_proxy * 20.0
    return _proxy(current), _proxy(proposed)


def _candidate_has_net_material_cleanup(candidate: dict, current_state: dict) -> bool:
    updates = dict(candidate.get("updates") or {})
    explicit = _candidate_net_efficiency_delta(candidate)
    if explicit is not None:
        return bool(float(explicit) > 1e-9)
    if not updates:
        return False
    before, after = _candidate_material_proxy_from_updates(current_state, updates)
    return bool(after < before - 1e-6)


def _candidate_preview_util(candidate: dict) -> float | None:
    contract = _candidate_nested_dict(candidate, "button_contract")
    truth = _candidate_nested_dict(candidate, "display_truth")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    payload = _candidate_nested_dict(candidate, "action_payload")
    for value in (
        contract.get("expected_util"),
        contract.get("preview_util"),
        candidate.get("preview_util"),
        candidate.get("candidate_post_util"),
        candidate.get("worst_util"),
        candidate.get("resolved_candidate_post_util"),
        payload.get("resolved_candidate_post_util"),
        resolved.get("candidate_post_util"),
        resolved.get("worst_util"),
        truth.get("source_candidate_util"),
        truth.get("displayed_util"),
    ):
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return None


def _candidate_blocking_reason(candidate: dict) -> str | None:
    contract = _candidate_nested_dict(candidate, "button_contract")
    value = (
        contract.get("blocking_reason")
        or candidate.get("blocking_reason")
        or candidate.get("executor_contract_blocked_reason")
        or candidate.get("contract_blocked_reason")
        or candidate.get("rejection_reason")
        or candidate.get("failed_reason")
    )
    if value in (None, ""):
        return None
    return str(value)


def _candidate_preview_pass(candidate: dict) -> bool:
    contract = _candidate_nested_dict(candidate, "button_contract")
    overview = _candidate_nested_dict(candidate, "overview")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    for value in (
        contract.get("preview_pass"),
        candidate.get("preview_pass"),
        candidate.get("is_compliant"),
        resolved.get("is_compliant"),
        overview.get("all_key_pass"),
    ):
        if value is not None:
            return bool(value)
    return bool(_candidate_updates(candidate) and _candidate_blocking_reason(candidate) is None)


def _candidate_required_preview_fails(candidate: dict) -> bool:
    overview = _candidate_nested_dict(candidate, "overview")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    for source in (overview, resolved):
        if bool(source.get("any_fail")):
            return True
        statuses = source.get("statuses")
        if isinstance(statuses, dict) and any(str(v or "").strip().upper() == "FAIL" for v in statuses.values()):
            return True
    for key in (
        "failed_check_status",
        "bending_status",
        "shear_status",
        "serviceability_status",
        "ductility_status",
    ):
        if str(candidate.get(key) or "").strip().upper() == "FAIL":
            return True
    return False


def _candidate_rejection_category(candidate: dict, *, executor_backed: bool, preview_pass: bool) -> str | None:
    text = " ".join(
        str(v or "")
        for v in (
            _candidate_blocking_reason(candidate),
            candidate.get("rejection_reason"),
            candidate.get("failed_check_family"),
            candidate.get("failed_check_status"),
            candidate.get("title"),
            candidate.get("title_main"),
        )
    )
    _, category = _blocker_from_text(text)
    if category:
        return category
    if not _candidate_updates(candidate):
        return "empty_updates"
    if not _candidate_action_type(candidate):
        return "not_executor_backed"
    if not preview_pass:
        return "preview_failed"
    if not executor_backed:
        return "not_executor_backed"
    if _candidate_required_preview_fails(candidate):
        return "preview_failed"
    return None


def normalise_design_guide_candidate(candidate: dict, target_low: float, target_high: float) -> dict:
    """Normalise page-generated candidates/items into the engine selection model."""
    raw = dict(candidate) if isinstance(candidate, dict) else {}
    updates = _candidate_updates(raw)
    action_type = _candidate_action_type(raw)
    preview_util = _candidate_preview_util(raw)
    preview_pass = _candidate_preview_pass(raw)
    blocking_reason = _candidate_blocking_reason(raw)
    executor_backed = bool(action_type and updates and preview_pass is True and blocking_reason is None)
    safe = bool(executor_backed and not _candidate_required_preview_fails(raw))
    inside_target = _within_band(preview_util, float(target_low), float(target_high))
    distance = _distance_to_band(preview_util, float(target_low), float(target_high))
    rejection_category = None if safe else _candidate_rejection_category(
        raw,
        executor_backed=executor_backed,
        preview_pass=preview_pass,
    )
    rejection_reason = None if safe else (
        blocking_reason
        or str(raw.get("rejection_reason") or "").strip()
        or rejection_category
    )
    return {
        "candidate_id": _candidate_id(raw),
        "title": _candidate_title(raw),
        "family": _candidate_family(raw),
        "action_type": action_type,
        "updates": dict(updates),
        "preview_util": preview_util,
        "preview_pass": bool(preview_pass),
        "blocking_reason": blocking_reason,
        "executor_backed": bool(executor_backed),
        "safe": bool(safe),
        "inside_target_band": bool(inside_target),
        "distance_to_target_band": distance,
        "rejection_reason": rejection_reason or None,
        "rejection_category": rejection_category,
        "candidate_complexity_score": raw.get("candidate_complexity_score"),
        "net_efficiency_delta": raw.get("net_efficiency_delta"),
        "material_proxy_before": raw.get("material_proxy_before"),
        "material_proxy_after": raw.get("material_proxy_after"),
        "material_proxy_delta": raw.get("material_proxy_delta"),
        "is_executable": bool(raw.get("is_executable", safe)),
        "advisory_only": bool(raw.get("advisory_only", not safe)),
        "affected_family": raw.get("affected_family") or raw.get("family") or raw.get("recommendation_family_tag"),
        "raw": raw,
    }


def _candidate_evidence_from_raw(candidate: dict) -> dict:
    payload = _candidate_nested_dict(candidate, "action_payload")
    resolved = _candidate_nested_dict(candidate, "resolved_candidate")
    return _as_dict(
        candidate.get("candidate_search_evidence")
        or payload.get("candidate_search_evidence")
        or resolved.get("candidate_search_evidence")
    )


def _candidate_evidence_row(candidate: dict) -> dict:
    raw = _as_dict(candidate.get("raw"))
    return {
        "candidate_id": candidate.get("candidate_id"),
        "title": candidate.get("title"),
        "proposed_updates": dict(candidate.get("updates") or {}),
        "preview_util": candidate.get("preview_util"),
        "distance_to_band": candidate.get("distance_to_target_band"),
        "safe_executor_backed": bool(candidate.get("safe")),
        "preview_pass": bool(candidate.get("preview_pass")),
        "reaches_target_band": bool(candidate.get("inside_target_band")),
        "rejection_reason": candidate.get("rejection_reason"),
        "rejection_category": candidate.get("rejection_category"),
        "failed_check_family": raw.get("failed_check_family"),
        "failed_check_status": raw.get("failed_check_status"),
        "failed_check_util": raw.get("failed_check_util"),
        "candidate_complexity_score": candidate.get("candidate_complexity_score"),
        "net_efficiency_delta": candidate.get("net_efficiency_delta"),
        "material_proxy_before": candidate.get("material_proxy_before"),
        "material_proxy_after": candidate.get("material_proxy_after"),
        "material_proxy_delta": candidate.get("material_proxy_delta"),
        "is_executable": bool(candidate.get("is_executable", candidate.get("safe"))),
        "advisory_only": bool(candidate.get("advisory_only", not bool(candidate.get("safe")))),
        "affected_family": candidate.get("affected_family") or candidate.get("family"),
    }


def _candidate_search_exhaustive(raw_candidates: list[dict], context: dict) -> tuple[bool, list[str], list[str], str | None]:
    if "candidate_search_exhaustive" in context:
        return bool(context.get("candidate_search_exhaustive")), list(context.get("searched_families") or []), list(context.get("missing_families") or []), context.get("reason_search_not_exhaustive")
    evidence = _as_dict(context.get("candidate_search_evidence"))
    if "candidate_search_exhaustive" in evidence:
        return bool(evidence.get("candidate_search_exhaustive")), list(evidence.get("searched_families") or []), list(evidence.get("missing_families") or []), evidence.get("reason_search_not_exhaustive")
    for raw in raw_candidates or []:
        existing = _candidate_evidence_from_raw(raw)
        if "candidate_search_exhaustive" in existing:
            return bool(existing.get("candidate_search_exhaustive")), list(existing.get("searched_families") or []), list(existing.get("missing_families") or []), existing.get("reason_search_not_exhaustive")
    searched = sorted({str(_candidate_family(raw) or "").strip() for raw in raw_candidates or [] if str(_candidate_family(raw) or "").strip()})
    return False, searched, [], "candidate source did not prove that all allowed move families were searched"


def _selection_sort_key(candidate: dict, target_low: float, target_high: float) -> tuple:
    return selection_sort_key(candidate, target_low, target_high)


MATERIALLY_OVERPROVIDED_UTIL_THRESHOLD = 0.70


def _summary_family_utils(summary: dict) -> dict[str, float]:
    utils = summary.get("utils")
    out: dict[str, float] = {}
    if isinstance(utils, dict):
        for key, value in utils.items():
            parsed = _as_float(value)
            if parsed is not None:
                out[str(key).strip().lower()] = float(parsed)
    packs = summary.get("packs")
    if isinstance(packs, dict):
        for key, pack in packs.items():
            if not isinstance(pack, dict):
                continue
            family = str(key or "").strip().lower()
            if family == "serviceability":
                family = "deflection"
            for field in ("summary_util", "util", "governing_util", "max_util"):
                parsed = _as_float(pack.get(field))
                if parsed is not None:
                    out.setdefault(family, float(parsed))
                    break
    for key in ("bending", "shear", "crack", "deflection", "serviceability", "ductility"):
        for field in (f"{key}_util", f"{key}_utilisation"):
            parsed = _as_float(summary.get(field))
            if parsed is not None:
                out.setdefault(key, float(parsed))
    return out


def _summary_governing_family(summary: dict, family_utils: dict[str, float]) -> str | None:
    explicit = str(summary.get("governing_family") or "").strip().lower()
    if explicit and explicit not in {"overview_worst_util", "governing", "overall"}:
        return explicit
    check = str(summary.get("governing_check") or "").strip().lower()
    if "shear" in check:
        return "shear"
    if "bend" in check or "moment" in check:
        return "bending"
    if "deflect" in check:
        return "deflection"
    if "crack" in check:
        return "crack"
    if family_utils:
        return max(family_utils.items(), key=lambda item: item[1])[0]
    return None


def _materially_overprovided_families(summary: dict) -> tuple[dict[str, float], list[str], str | None]:
    family_utils = _summary_family_utils(summary)
    governing = _summary_governing_family(summary, family_utils)
    families = [
        family
        for family, util in sorted(family_utils.items())
        if family != governing and float(util) < MATERIALLY_OVERPROVIDED_UTIL_THRESHOLD
    ]
    return family_utils, families, governing


def _candidate_update_families_from_updates(updates: dict) -> set[str]:
    keys = {str(key) for key in dict(updates or {})}
    families: set[str] = set()
    if keys & {"b", "D", "bw", "bf", "tf", "tw"}:
        families.add("geometry")
        families.add("bending")
        families.add("shear")
        families.add("serviceability")
    if keys & {
        "bot1_count",
        "db_bot_1",
        "nb_or_s_bot_1",
        "bot_row_1_bars",
        "bot_row_1_dia",
        "bot_row_count",
        "nb_bot",
        "db_bot",
    }:
        families.add("bending")
    if keys & {"lig_d", "lig_legs", "s_lig", "link_dia", "link_legs", "link_spacing"}:
        families.add("shear")
    return families


def _family_from_evidence_row(row: dict) -> str | None:
    explicit = str(row.get("affected_family") or row.get("family") or row.get("failed_check_family") or "").strip().lower()
    if explicit and explicit not in {"none", "null", "-"}:
        return explicit
    families = _candidate_update_families_from_updates(dict(row.get("proposed_updates") or row.get("updates") or {}))
    if "shear" in families and len(families) == 1:
        return "shear"
    if "bending" in families and "geometry" not in families:
        return "bending"
    if "geometry" in families:
        return "geometry"
    if families:
        return sorted(families)[0]
    return None


def _raw_candidates_from_search_evidence(evidence: dict) -> list[dict]:
    rows: list[dict] = []
    if not isinstance(evidence, dict):
        return rows
    for bucket in (
        "target_band_candidates",
        "safe_executor_backed_candidates",
        "rejected_target_band_candidates",
    ):
        for row in list(evidence.get(bucket) or []):
            if not isinstance(row, dict):
                continue
            updates = dict(row.get("proposed_updates") or row.get("updates") or {})
            candidate_id = row.get("candidate_id")
            if candidate_id and any(str(existing.get("candidate_id") or "") == str(candidate_id) for existing in rows):
                continue
            safe = bool(row.get("safe_executor_backed"))
            family = _family_from_evidence_row(row)
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "title": row.get("title") or row.get("label") or "Local cleanup candidate",
                    "family": family,
                    "action_type": "apply_resolved_candidate" if updates else None,
                    "updates": updates,
                    "candidate_post_util": row.get("preview_util"),
                    "worst_util": row.get("preview_util"),
                    "preview_util": row.get("preview_util"),
                    "preview_pass": bool(row.get("preview_pass") or safe),
                    "is_compliant": bool(safe),
                    "blocking_reason": None if safe else (row.get("rejection_reason") or row.get("rejection_category")),
                    "rejection_reason": row.get("rejection_reason"),
                    "rejection_category": row.get("rejection_category"),
                    "failed_check_family": row.get("failed_check_family"),
                    "failed_check_status": row.get("failed_check_status"),
                    "failed_check_util": row.get("failed_check_util"),
                    "candidate_complexity_score": row.get("candidate_complexity_score"),
                    "net_efficiency_delta": row.get("net_efficiency_delta"),
                    "material_proxy_before": row.get("material_proxy_before"),
                    "material_proxy_after": row.get("material_proxy_after"),
                    "material_proxy_delta": row.get("material_proxy_delta"),
                    "is_executable": row.get("is_executable"),
                    "advisory_only": row.get("advisory_only"),
                    "affected_family": row.get("affected_family"),
                    "local_cleanup_candidate": True,
                    "source": evidence.get("search_scope") or "candidate_search_evidence",
                }
            )
    return rows


def _candidate_affects_material_family(candidate: dict, material_families: list[str]) -> bool:
    if not material_families:
        return False
    material = {str(family or "").strip().lower() for family in material_families}
    family = str(candidate.get("family") or "").strip().lower()
    update_families = _candidate_update_families_from_updates(dict(candidate.get("updates") or {}))
    if family:
        update_families.add(family)
    if material & update_families:
        return True
    if "bending" in material and "geometry" in update_families:
        return True
    if {"crack", "deflection", "serviceability"} & material and (
        "geometry" in update_families or "bending" in update_families
    ):
        return True
    return False


def _candidate_has_bad_update_keys(candidate: dict) -> bool:
    raw = _as_dict(candidate.get("raw"))
    for key in ("internal_bad_update_keys", "partial_failing_final_updates"):
        value = raw.get(key)
        if isinstance(value, (list, tuple, set, dict)) and len(value) > 0:
            return True
        if isinstance(value, bool) and value:
            return True
    return False


def _build_local_cleanup_evidence(
    *,
    raw_candidates: list[dict],
    current_state: dict,
    summary: dict,
    context: dict,
    target_low: float,
    target_high: float,
) -> tuple[dict, dict | None]:
    family_utils, material_families, governing_family = _materially_overprovided_families(summary)
    raw = [dict(c) for c in raw_candidates or [] if isinstance(c, dict)]
    context_candidate_evidence = _as_dict(
        context.get("local_cleanup_candidate_search_evidence")
        or context.get("candidate_search_evidence")
    )
    evidence_candidates = _raw_candidates_from_search_evidence(context_candidate_evidence)
    if evidence_candidates:
        existing_ids = {str(_candidate_id(c) or "") for c in raw if str(_candidate_id(c) or "")}
        for candidate in evidence_candidates:
            candidate_id = str(candidate.get("candidate_id") or "")
            if candidate_id and candidate_id in existing_ids:
                continue
            raw.append(candidate)
            if candidate_id:
                existing_ids.add(candidate_id)
    search_ran = bool(material_families)
    normalised = [normalise_design_guide_candidate(c, target_low, target_high) for c in raw]
    normalised = [
        {**candidate, "candidate_id": candidate.get("candidate_id") or f"local_cleanup_candidate_{idx:03d}"}
        for idx, candidate in enumerate(normalised, start=1)
    ]
    local_candidates = [
        c for c in normalised if _candidate_affects_material_family(c, material_families)
    ]
    safe_local: list[dict] = []
    rejected: list[dict] = []
    executable_safe_count = 0
    advisory_count = 0
    blocked_reasons: list[str] = []
    for candidate in local_candidates:
        preview_util = _as_float(candidate.get("preview_util"))
        bad_keys = _candidate_has_bad_update_keys(candidate)
        advisory_only = _candidate_advisory_only(candidate)
        if advisory_only:
            advisory_count += 1
        net_cleanup = _candidate_has_net_material_cleanup(candidate, current_state)
        safe = bool(
            candidate.get("safe")
            and not bad_keys
            and not advisory_only
            and net_cleanup
            and preview_util is not None
            and preview_util <= 1.0
        )
        if safe:
            safe_local.append(candidate)
            executable_safe_count += 1
        else:
            reason = (
                "internal_bad_update_keys"
                if bad_keys
                else "advisory_only_cleanup"
                if advisory_only
                else "cleanup_no_net_material_efficiency"
                if not net_cleanup
                else str(candidate.get("rejection_category") or candidate.get("rejection_reason") or "preview_failed")
            )
            candidate["safe"] = False
            candidate["rejection_reason"] = reason
            candidate["rejection_category"] = reason
            rejected.append(candidate)
            if reason not in blocked_reasons:
                blocked_reasons.append(reason)
    selected = None
    if safe_local:
        selected = sorted(
            safe_local,
            key=lambda c: (
                0 if bool(c.get("inside_target_band")) else 1,
                _selection_sort_key(c, target_low, target_high),
            ),
        )[0]
    if search_ran and not blocked_reasons and local_candidates and not safe_local:
        blocked_reasons.append("no_safe_local_cleanup_candidate")
    if search_ran and not local_candidates:
        blocked_reasons.append("no_local_cleanup_candidate_for_materially_overprovided_family")
    unsupported_families = list(context.get("unsupported_cleanup_families") or [])
    blocked_by_family = _as_dict(context.get("local_cleanup_blocked_reasons_by_family"))
    if unsupported_families:
        for family in unsupported_families:
            reason = f"unsupported_cleanup_family:{family}"
            if reason not in blocked_reasons:
                blocked_reasons.append(reason)
    if isinstance(blocked_by_family, dict):
        for family, reasons in blocked_by_family.items():
            for reason in list(reasons or []):
                text = f"{family}:{reason}"
                if text not in blocked_reasons:
                    blocked_reasons.append(text)
    real_inventory = [_candidate_evidence_row(c) for c in local_candidates[:80]]
    exhaustive_from_context = context.get("local_cleanup_search_exhaustive")
    if exhaustive_from_context is None and context_candidate_evidence:
        exhaustive_from_context = context_candidate_evidence.get("candidate_search_exhaustive")
    local_exhaustive = bool(search_ran) and bool(exhaustive_from_context if exhaustive_from_context is not None else search_ran)
    if unsupported_families:
        local_exhaustive = False
    evidence = {
        "family_utils": dict(family_utils),
        "materially_overprovided_families": list(material_families),
        "materially_overprovided_threshold": MATERIALLY_OVERPROVIDED_UTIL_THRESHOLD,
        "governing_family": governing_family,
        "local_cleanup_search_ran": bool(search_ran),
        "local_cleanup_search_exhaustive": bool(local_exhaustive),
        "safe_local_cleanup_count": len(safe_local),
        "executable_safe_cleanup_count": int(executable_safe_count),
        "advisory_cleanup_count": int(advisory_count),
        "local_cleanup_candidates": [_candidate_evidence_row(c) for c in safe_local[:20]],
        "local_cleanup_candidate_inventory": real_inventory,
        "local_cleanup_candidate_inventory_count": len(real_inventory),
        "candidate_inventory_count": len(real_inventory),
        "rejected_local_cleanup_count": len(rejected),
        "local_cleanup_blocked_reasons": list(blocked_reasons),
        "local_cleanup_blocked_reasons_by_family": dict(blocked_by_family),
        "unsupported_cleanup_families": list(unsupported_families),
        "terminal_state_reason": (
            "governing_in_target_no_materially_overprovided_family"
            if not material_families
            else (
                "governing_in_target_no_safe_local_cleanup"
                if search_ran and not safe_local
                else None
            )
        ),
        "terminal_state_blocked_by_local_cleanup": bool(safe_local),
    }
    selected_raw = None if selected is None else _as_dict(selected.get("raw"))
    return evidence, selected_raw


def _outside_target_allowance(
    *,
    selected: dict | None,
    target_count: int,
    safe_count: int,
    exhaustive: bool,
    context: dict,
) -> tuple[bool, str | None, str | None]:
    if selected is None or bool(selected.get("inside_target_band")):
        return False, None, None
    existing = _as_dict(context.get("candidate_search_evidence"))
    category = str(existing.get("outside_target_band_allowed_category") or context.get("outside_target_band_allowed_category") or "").strip()
    reason = str(existing.get("outside_target_band_allowed_reason") or context.get("outside_target_band_allowed_reason") or "").strip()
    if not category or category in FORBIDDEN_OUTSIDE_TARGET_CATEGORIES:
        category = "discrete_increment_limit" if exhaustive and target_count == 0 and safe_count > 0 else "no_material_candidate_reached_target"
    if category not in ALLOWED_OUTSIDE_TARGET_CATEGORIES:
        category = "no_material_candidate_reached_target"
    if not reason:
        reason = "No safe executor-backed target-band candidate was found in the searched catalogue; the selected candidate is the closest safe available step."
    allowed = bool(exhaustive and target_count == 0 and safe_count > 0 and category in ALLOWED_OUTSIDE_TARGET_CATEGORIES)
    return allowed, reason if allowed else None, category if allowed else None


def select_target_band_winner(
    *,
    raw_candidates: list[dict],
    current_state: dict,
    summary: dict | None,
    target_band: dict,
    context: dict | None = None,
) -> dict:
    """Select the Design Guide one-click winner and build search evidence.

    This is intentionally pure: page code may still generate candidate rows, but
    target-band priority and outside-target proof live here.
    """
    ctx = _as_dict(context)
    goal = str(ctx.get("goal") or _as_dict(current_state).get("design_optimisation_goal") or "balanced")
    band = _target_band(goal, target_band)
    target_low = float(_as_float(band.get("target_low")) or get_target_utilisation_band(goal)[0])
    target_high = float(_as_float(band.get("target_high")) or get_target_utilisation_band(goal)[1])
    raw = [dict(c) for c in raw_candidates or [] if isinstance(c, dict)]
    normalised = [normalise_design_guide_candidate(c, target_low, target_high) for c in raw]
    normalised = [
        {**candidate, "candidate_id": candidate.get("candidate_id") or f"engine_candidate_{idx:03d}"}
        for idx, candidate in enumerate(normalised, start=1)
    ]
    exhaustive, searched_families, missing_families, not_exhaustive_reason = _candidate_search_exhaustive(raw, ctx)

    safe_candidates = [c for c in normalised if bool(c.get("safe"))]
    target_candidates = [c for c in safe_candidates if bool(c.get("inside_target_band"))]
    selected: dict | None = None
    selection_status = "no_candidates"
    selection_reason = "no candidates were supplied to the engine"
    if target_candidates:
        selected = sorted(target_candidates, key=lambda c: _selection_sort_key(c, target_low, target_high))[0]
        selection_status = "target_band_candidate_selected"
        selection_reason = "selected safe executor-backed candidate inside target band"
    elif safe_candidates:
        selected = sorted(safe_candidates, key=lambda c: _selection_sort_key(c, target_low, target_high))[0]
        selection_status = "closest_safe_candidate_selected"
        selection_reason = "no safe target-band candidate was available; selected closest safe executor-backed candidate"
    elif normalised:
        selection_status = "no_safe_executor_backed_candidate"
        selection_reason = "candidate set did not include a safe executor-backed candidate"

    closest = sorted(safe_candidates, key=lambda c: _selection_sort_key(c, target_low, target_high))[0] if safe_candidates else None
    best_target = sorted(target_candidates, key=lambda c: _selection_sort_key(c, target_low, target_high))[0] if target_candidates else None
    rejected_target = [
        c for c in normalised
        if bool(c.get("inside_target_band")) and not bool(c.get("safe"))
    ]
    outside_allowed, outside_reason, outside_category = _outside_target_allowance(
        selected=selected,
        target_count=len(target_candidates),
        safe_count=len(safe_candidates),
        exhaustive=bool(exhaustive),
        context=ctx,
    )
    if selected is not None and not bool(selected.get("inside_target_band")):
        selected_distance = selected.get("distance_to_target_band")
        closest_distance = None if closest is None else closest.get("distance_to_target_band")
        if closest is None or selected_distance != closest_distance:
            outside_allowed = False
            outside_reason = None
            outside_category = None

    evidence = {
        "candidate_search_exhaustive": bool(exhaustive),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "total_candidates_considered": len(normalised),
        "safe_executor_backed_candidates_count": len(safe_candidates),
        "target_band_candidate_count": len(target_candidates),
        "selected_candidate_id": None if selected is None else selected.get("candidate_id"),
        "selected_candidate_title": None if selected is None else selected.get("title"),
        "selected_candidate_util": None if selected is None else selected.get("preview_util"),
        "selected_candidate_distance_to_band": None if selected is None else selected.get("distance_to_target_band"),
        "selected_candidate_updates": {} if selected is None else dict(selected.get("updates") or {}),
        "closest_safe_candidate_id": None if closest is None else closest.get("candidate_id"),
        "closest_safe_candidate_title": None if closest is None else closest.get("title"),
        "closest_safe_candidate_util": None if closest is None else closest.get("preview_util"),
        "closest_safe_candidate_distance_to_band": None if closest is None else closest.get("distance_to_target_band"),
        "closest_safe_candidate_updates": {} if closest is None else dict(closest.get("updates") or {}),
        "best_target_band_candidate_id": None if best_target is None else best_target.get("candidate_id"),
        "best_target_band_candidate_title": None if best_target is None else best_target.get("title"),
        "best_target_band_candidate_util": None if best_target is None else best_target.get("preview_util"),
        "best_target_band_candidate_updates": {} if best_target is None else dict(best_target.get("updates") or {}),
        "target_band_candidates": [_candidate_evidence_row(c) for c in target_candidates[:20]],
        "safe_executor_backed_candidates": [_candidate_evidence_row(c) for c in safe_candidates[:40]],
        "rejected_target_band_candidates": [_candidate_evidence_row(c) for c in rejected_target[:20]],
        "rejected_target_band_candidate_reasons": [
            str(c.get("rejection_category") or c.get("rejection_reason") or "preview_failed")
            for c in rejected_target[:20]
        ],
        "outside_target_band_allowed": bool(outside_allowed),
        "outside_target_band_allowed_reason": outside_reason,
        "outside_target_band_allowed_category": outside_category,
    }
    if not exhaustive:
        evidence["searched_families"] = list(searched_families)
        evidence["missing_families"] = list(missing_families)
        evidence["reason_search_not_exhaustive"] = not_exhaustive_reason
    selected_candidate = None if selected is None else {k: v for k, v in selected.items() if k != "raw"}
    if selected is not None:
        selected_candidate["raw"] = dict(selected.get("raw") or {})
    return {
        "selected_candidate": selected_candidate,
        "candidate_search_evidence": evidence,
        "selection_reason": selection_reason,
        "selection_status": selection_status,
    }


def _within_band(util: float | None, lo: float, hi: float) -> bool:
    return bool(util is not None and lo <= float(util) <= hi)


def _has_required_failure(overview: dict, context: dict) -> bool:
    if bool(context.get("any_fail") or overview.get("any_fail")):
        return True
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        for value in statuses.values():
            if str(value or "").strip().upper() == "FAIL":
                return True
    for key in ("bending_status", "shear_status", "crack_status", "deflection_status"):
        if str(overview.get(key) or context.get(key) or "").strip().upper() == "FAIL":
            return True
    return False


def _failure_detail_text(overview: dict, context: dict) -> str:
    explicit = str(context.get("failure_detail_text") or "").strip()
    if explicit:
        return explicit
    details = overview.get("failure_details_by_family")
    if not isinstance(details, dict):
        return ""
    lines: list[str] = []
    for family, rows in details.items():
        for row in list(rows or [])[:3]:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text") or row.get("title") or "").strip()
            if text:
                lines.append(f"{str(family).title()}: {text}")
    return "; ".join(lines[:4])


def _low_util_families_without_evidence(overview: dict, context: dict, target_low: float) -> list[str]:
    statuses = overview.get("statuses") if isinstance(overview.get("statuses"), dict) else {}
    utils = overview.get("utils") if isinstance(overview.get("utils"), dict) else {}
    evidence = _as_dict(context.get("candidate_search_evidence"))
    evidence_by_family = _as_dict(
        evidence.get("cleanup_evidence_by_family")
        or evidence.get("post_click_cleanup_evidence_by_family")
        or context.get("cleanup_evidence_by_family")
    )
    blockers_by_family = _as_dict(
        evidence.get("exact_blockers_by_family")
        or evidence.get("post_click_exact_blockers_by_family")
        or context.get("exact_blockers_by_family")
    )
    unresolved: list[str] = []
    for family in ("bending", "shear"):
        status = str(statuses.get(family) or "").strip().upper()
        if status not in {"PASS", "NEAR LIMIT", "WARN"}:
            continue
        util = _as_float(utils.get(family))
        if util is None or util >= float(target_low):
            continue
        family_evidence = _as_dict(evidence_by_family.get(family))
        family_blocker = _as_dict(blockers_by_family.get(family))
        safe_count = int(
            family_evidence.get("safe_candidate_count")
            or family_evidence.get("safe_cleanup_count")
            or evidence.get(f"safe_{family}_cleanup_count")
            or 0
        )
        attempted = bool(
            family_evidence.get("cleanup_search_ran")
            or family_evidence.get("local_cleanup_search_ran")
            or family_evidence.get("target_band_search_ran")
            or family_blocker
        )
        if safe_count <= 0 and not attempted:
            unresolved.append(family)
    return unresolved


def _active_strength_failure_families(overview: dict, context: dict) -> set[str]:
    """Return active bending/shear strength failures from published governing truth."""
    families: set[str] = set()
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        for key, value in statuses.items():
            key_norm = str(key or "").strip().lower()
            if str(value or "").strip().upper() != "FAIL":
                continue
            if key_norm in {"bending", "shear", "combined", "sectional_shear"}:
                families.add("shear" if key_norm == "sectional_shear" else key_norm)
    fail_keys = overview.get("fail_keys") or context.get("fail_keys") or []
    if isinstance(fail_keys, (list, tuple, set)):
        for key in fail_keys:
            key_norm = str(key or "").strip().lower()
            if key_norm in {"bending", "shear", "combined", "sectional_shear"}:
                families.add("shear" if key_norm == "sectional_shear" else key_norm)
    for family in ("bending", "shear"):
        if str(overview.get(f"{family}_status") or context.get(f"{family}_status") or "").strip().upper() == "FAIL":
            families.add(family)
        util = _as_float(
            _as_dict(overview.get("utils")).get(family)
            if isinstance(overview.get("utils"), dict)
            else overview.get(f"{family}_util")
        )
        if util is not None and util > 1.0:
            families.add(family)
    if "combined" in families:
        families.discard("combined")
        families.update({"bending", "shear"})
    return families


def _item_signals_bending_active_failure(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    evidence = _as_dict(item.get("candidate_search_evidence"))
    text = " ".join(
        str(part or "")
        for part in (
            item.get("title"),
            item.get("title_main"),
            item.get("primary_action"),
            item.get("reasoning"),
            item.get("guidance_why"),
            item.get("summary_line"),
            evidence.get("reason"),
            evidence.get("failed_check_name"),
            evidence.get("failed_check"),
        )
    ).lower()
    return any(
        token in text
        for token in (
            "minimum tensile reinforcement fails",
            "minimum tensile reinforcement",
            "bending utilisation moves",
            "bending utilization moves",
            "bending fail",
            "bending capacity fails",
        )
    )


def _button_enabled(contract: dict) -> bool:
    return bool(
        contract.get("actionable") is True
        and bool(contract.get("updates") or {})
        and contract.get("preview_pass") is True
        and contract.get("blocking_reason") is None
    )


def _shear_fail_family_routing_enabled() -> bool:
    value = str(os.environ.get(SHEAR_FAIL_FAMILY_ROUTING_ENV, "0")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _combined_fail_family_routing_enabled() -> bool:
    value = str(os.environ.get(COMBINED_FAIL_FAMILY_ROUTING_ENV, "0")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _stamp_shear_fail_family_route_diagnostics(decision: dict, diagnostics: dict) -> dict:
    if not diagnostics:
        return decision
    stamped = dict(decision)
    debug = _as_dict(stamped.get("debug"))
    debug["shear_fail_family_routing"] = dict(diagnostics)
    stamped["debug"] = debug
    evidence = _as_dict(stamped.get("candidate_search_evidence"))
    evidence.update(
        {
            "governing_family": diagnostics.get("governing_state") or "SHEAR_FAIL_GOVERNS",
            "family_name": diagnostics.get("family_name") or "SHEAR_FAIL_GOVERNS",
            "family_routing_attempted": bool(diagnostics.get("family_routing_attempted")),
            "family_routing_used": bool(diagnostics.get("family_routing_used")),
            "fallback_used": bool(diagnostics.get("fallback_used")),
            "fallback_reason": diagnostics.get("fallback_reason"),
            "adapter_error": diagnostics.get("adapter_error"),
            "product_routing_enabled": bool(diagnostics.get("product_routing_enabled")),
        }
    )
    stamped["candidate_search_evidence"] = evidence
    return stamped


def _stamp_combined_fail_family_route_diagnostics(decision: dict, diagnostics: dict) -> dict:
    if not diagnostics:
        return decision
    stamped = dict(decision)
    debug = _as_dict(stamped.get("debug"))
    debug["combined_fail_family_routing"] = dict(diagnostics)
    stamped["debug"] = debug
    evidence = _as_dict(stamped.get("candidate_search_evidence"))
    evidence.update(
        {
            "governing_family": diagnostics.get("governing_state") or "COMBINED_BENDING_SHEAR_FAIL",
            "family_name": diagnostics.get("family_name") or "COMBINED_BENDING_SHEAR_FAIL",
            "family_routing_attempted": bool(diagnostics.get("family_routing_attempted")),
            "family_routing_used": bool(diagnostics.get("family_routing_used")),
            "fallback_used": bool(diagnostics.get("fallback_used")),
            "fallback_reason": diagnostics.get("fallback_reason"),
            "adapter_error": diagnostics.get("adapter_error"),
            "product_routing_enabled": bool(diagnostics.get("product_routing_enabled")),
        }
    )
    stamped["candidate_search_evidence"] = evidence
    return stamped


def _route_shear_fail_family_decision(
    *,
    decision: dict,
    primary_item: dict,
    overview: dict,
    context: dict,
    evidence: dict,
    active_strength_failures: set[str],
) -> dict:
    active = {str(item or "").strip().lower() for item in set(active_strength_failures or set())}
    base_diagnostics = {
        "family_name": "SHEAR_FAIL_GOVERNS",
        "governing_state": "SHEAR_FAIL_GOVERNS",
        "family_routing_attempted": False,
        "family_routing_used": False,
        "fallback_used": False,
        "fallback_reason": None,
        "adapter_error": None,
        "product_routing_enabled": _shear_fail_family_routing_enabled(),
        "active_strength_failures": sorted(active),
        "routing_flag": SHEAR_FAIL_FAMILY_ROUTING_ENV,
        "routing_boundary": "design_brain.engine.resolve_design_guide_decision",
    }
    if active != {"shear"}:
        return {
            "used": False,
            "decision": dict(decision),
            "primary_item": dict(primary_item),
            "diagnostics": {
                **base_diagnostics,
                "fallback_reason": "not_shear_only_active_strength_failure",
            },
        }
    if not _shear_fail_family_routing_enabled():
        return {
            "used": False,
            "decision": dict(decision),
            "primary_item": dict(primary_item),
            "diagnostics": {
                **base_diagnostics,
                "family_routing_attempted": True,
                "fallback_used": True,
                "fallback_reason": "routing_flag_disabled",
            },
        }
    try:
        from design_brain.families.base import FamilyStrategyContext
        from design_brain.families.registry import family_strategy_for

        strategy = family_strategy_for("SHEAR_FAIL_GOVERNS")
        if strategy is None or not callable(getattr(strategy, "route_existing_decision", None)):
            return {
                "used": False,
                "decision": dict(decision),
                "primary_item": dict(primary_item),
                "diagnostics": {
                    **base_diagnostics,
                    "family_routing_attempted": True,
                    "fallback_used": True,
                    "fallback_reason": "shear_fail_family_route_method_missing",
                },
            }
        family_context = FamilyStrategyContext(
            governing_state="SHEAR_FAIL_GOVERNS",
            payload={
                "guidance_items": [dict(primary_item)],
                "debug_trace": {
                    "overview": dict(overview),
                    "candidate_search_evidence": dict(evidence),
                },
            },
            primary=dict(primary_item),
            summary=dict(overview),
            evidence=dict(evidence),
            debug={
                "overview": dict(overview),
                "candidate_search_evidence": dict(evidence),
                "fail_keys": list(context.get("fail_keys") or overview.get("fail_keys") or []),
            },
            classifier={
                "governing_state": "SHEAR_FAIL_GOVERNS",
                "active_failures": ["shear"],
            },
        )
        routed = strategy.route_existing_decision(
            family_context,
            decision=dict(decision),
            primary_item=dict(primary_item),
            active_strength_failures=set(active),
        )
        diagnostics = {
            **base_diagnostics,
            **_as_dict(routed.get("diagnostics")),
            "family_routing_attempted": True,
            "product_routing_enabled": True,
        }
        routed_decision = _stamp_shear_fail_family_route_diagnostics(
            _as_dict(routed.get("decision") or decision),
            diagnostics,
        )
        return {
            "used": bool(routed.get("used")),
            "decision": routed_decision,
            "primary_item": _as_dict(routed.get("primary_item") or primary_item),
            "diagnostics": diagnostics,
        }
    except Exception as exc:
        diagnostics = {
            **base_diagnostics,
            "family_routing_attempted": True,
            "fallback_used": True,
            "fallback_reason": "adapter_exception",
            "adapter_error": f"{type(exc).__name__}: {exc}",
        }
        return {
            "used": False,
            "decision": _stamp_shear_fail_family_route_diagnostics(dict(decision), diagnostics),
            "primary_item": dict(primary_item),
            "diagnostics": diagnostics,
        }


def _route_combined_fail_family_decision(
    *,
    decision: dict,
    primary_item: dict,
    overview: dict,
    context: dict,
    evidence: dict,
    active_strength_failures: set[str],
) -> dict:
    active = {str(item or "").strip().lower() for item in set(active_strength_failures or set())}
    base_diagnostics = {
        "family_name": "COMBINED_BENDING_SHEAR_FAIL",
        "governing_state": "COMBINED_BENDING_SHEAR_FAIL",
        "family_routing_attempted": False,
        "family_routing_used": False,
        "fallback_used": False,
        "fallback_reason": None,
        "adapter_error": None,
        "product_routing_enabled": _combined_fail_family_routing_enabled(),
        "active_strength_failures": sorted(active),
        "routing_flag": COMBINED_FAIL_FAMILY_ROUTING_ENV,
        "routing_boundary": "design_brain.engine.resolve_design_guide_decision",
    }
    if not active >= {"bending", "shear"}:
        return {
            "used": False,
            "decision": dict(decision),
            "primary_item": dict(primary_item),
            "diagnostics": {
                **base_diagnostics,
                "fallback_reason": "not_combined_bending_shear_active_strength_failure",
            },
        }
    if not _combined_fail_family_routing_enabled():
        return {
            "used": False,
            "decision": dict(decision),
            "primary_item": dict(primary_item),
            "diagnostics": {
                **base_diagnostics,
                "family_routing_attempted": True,
                "fallback_used": True,
                "fallback_reason": "routing_flag_disabled",
            },
        }
    try:
        from design_brain.families.base import FamilyStrategyContext
        from design_brain.families.registry import family_strategy_for

        strategy = family_strategy_for("COMBINED_BENDING_SHEAR_FAIL")
        if strategy is None or not callable(getattr(strategy, "route_existing_decision", None)):
            diagnostics = {
                **base_diagnostics,
                "family_routing_attempted": True,
                "fallback_used": True,
                "fallback_reason": "combined_fail_family_route_method_missing",
            }
            return {
                "used": False,
                "decision": _stamp_combined_fail_family_route_diagnostics(dict(decision), diagnostics),
                "primary_item": dict(primary_item),
                "diagnostics": diagnostics,
            }
        family_context = FamilyStrategyContext(
            governing_state="COMBINED_BENDING_SHEAR_FAIL",
            payload={
                "guidance_items": [dict(primary_item)],
                "debug_trace": {
                    "overview": dict(overview),
                    "candidate_search_evidence": dict(evidence),
                },
            },
            primary=dict(primary_item),
            summary=dict(overview),
            evidence=dict(evidence),
            debug={
                "overview": dict(overview),
                "candidate_search_evidence": dict(evidence),
                "fail_keys": list(context.get("fail_keys") or overview.get("fail_keys") or []),
            },
            classifier={
                "governing_state": "COMBINED_BENDING_SHEAR_FAIL",
                "active_failures": sorted(active),
            },
        )
        routed = strategy.route_existing_decision(
            family_context,
            decision=dict(decision),
            primary_item=dict(primary_item),
            active_strength_failures=set(active),
        )
        diagnostics = {
            **base_diagnostics,
            **_as_dict(routed.get("diagnostics")),
            "family_routing_attempted": True,
            "product_routing_enabled": True,
        }
        routed_decision = _stamp_combined_fail_family_route_diagnostics(
            _as_dict(routed.get("decision") or decision),
            diagnostics,
        )
        return {
            "used": bool(routed.get("used")),
            "decision": routed_decision,
            "primary_item": _as_dict(routed.get("primary_item") or primary_item),
            "diagnostics": diagnostics,
        }
    except Exception as exc:
        diagnostics = {
            **base_diagnostics,
            "family_routing_attempted": True,
            "fallback_used": True,
            "fallback_reason": "adapter_exception",
            "adapter_error": f"{type(exc).__name__}: {exc}",
        }
        return {
            "used": False,
            "decision": _stamp_combined_fail_family_route_diagnostics(dict(decision), diagnostics),
            "primary_item": dict(primary_item),
            "diagnostics": diagnostics,
        }


def _text_indicates_blocker(text: str | None) -> bool:
    lower = str(text or "").strip().lower()
    if not lower:
        return False
    return any(
        token in lower
        for token in (
            "blocked",
            "cannot safely",
            "cannot be safely",
            "no further safe",
            "no safe one-click",
            "no one-click cleanup",
            "no one-click candidate",
            "no one-click update",
        )
    )


def _item_is_blocker(primary_item: dict) -> bool:
    if str(primary_item.get("guidance_intent") or primary_item.get("intent") or "").strip() == "specific_blocker":
        return True
    if str(primary_item.get("post_click_design_guide_state") or "").strip() == "exact_blocker":
        return True
    blockers = primary_item.get("exact_blockers_by_family") or primary_item.get("post_click_exact_blockers_by_family")
    if isinstance(blockers, dict) and blockers and not bool(primary_item.get("primary_card_actionable")):
        return True
    text = " ".join(
        str(part or "")
        for part in (
            primary_item.get("title"),
            primary_item.get("title_main"),
        )
    )
    return _text_indicates_blocker(text)


def _normalise_button_contract(primary_item: dict, contract: dict, display_truth: dict) -> dict:
    payload = _as_dict(primary_item.get("action_payload"))
    resolved = _as_dict(primary_item.get("resolved_candidate"))
    evidence = _as_dict(
        primary_item.get("candidate_search_evidence")
        or payload.get("candidate_search_evidence")
        or resolved.get("candidate_search_evidence")
    )
    if _item_is_blocker(primary_item):
        family = contract.get("family") or primary_item.get("check_key") or primary_item.get("family")
        reason = (
            contract.get("blocking_reason")
            or primary_item.get("reasoning")
            or "specific_blocker"
        )
        return {
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "family": family,
            "updates": {},
            "preview_pass": False,
            "expected_util": None,
            "blocking_reason": reason,
            "source_candidate_id": None,
            "candidate_id": None,
            "preview_util": None,
            "post_click_expected_util": None,
        }
    updates = _as_dict(contract.get("updates") or payload.get("updates") or payload.get("resolved_candidate_updates"))
    if not updates:
        updates = _as_dict(primary_item.get("updates") or primary_item.get("raw_updates") or primary_item.get("proposed_updates"))
    candidate_id = (
        contract.get("source_candidate_id")
        or contract.get("candidate_id")
        or evidence.get("selected_candidate_id")
        or primary_item.get("candidate_id")
        or resolved.get("candidate_id")
        or resolved.get("id")
    )
    preview_util = _as_float(
        contract.get("expected_util")
        if contract.get("expected_util") is not None
        else display_truth.get("source_candidate_util")
    )
    if preview_util is None:
        preview_util = _candidate_preview_util(primary_item)
    preview_pass = contract.get("preview_pass")
    if preview_pass is None:
        preview_pass = bool(updates) and contract.get("blocking_reason") is None
    out = {
        "enabled": False,
        "actionable": bool(contract.get("actionable") or (updates and (contract.get("action_type") or primary_item.get("action_type")))),
        "action_type": contract.get("action_type") or primary_item.get("action_type"),
        "family": contract.get("family") or primary_item.get("check_key") or primary_item.get("family"),
        "updates": updates,
        "preview_pass": bool(preview_pass),
        "expected_util": preview_util,
        "blocking_reason": contract.get("blocking_reason"),
        "source_candidate_id": candidate_id,
        "candidate_id": candidate_id,
        "preview_util": preview_util,
        "post_click_expected_util": preview_util,
    }
    out["enabled"] = _button_enabled(out)
    return out


def _blocker_from_text(text: str, *, fallback: str | None = None) -> tuple[str | None, str | None]:
    lower = (text or "").lower()
    if "empty" in lower and "update" in lower:
        return "candidate updates are empty", "empty_updates"
    if "spacing" in lower or "detailing" in lower or "minimum shear" in lower or "minimum reinforcement" in lower:
        return "spacing or detailing limits prevent a cleaner one-click move", "spacing_or_detailing_limit"
    if "ductility" in lower:
        return "ductility limits prevent a cleaner one-click move", "ductility_limit"
    if "serviceability" in lower or "crack" in lower or "deflection" in lower:
        return "serviceability limits prevent a cleaner one-click move", "serviceability_would_fail"
    if "bending would fail" in lower or "make bending fail" in lower or "bending fail" in lower:
        return "bending would fail", "bending_would_fail"
    if "shear would fail" in lower or "make shear fail" in lower or "shear fail" in lower:
        return "shear would fail", "shear_would_fail"
    if "discrete" in lower or "catalogue" in lower or "increment" in lower:
        return "available catalogue increments cannot hit the target band exactly", "discrete_increment_limit"
    if "geometry lock" in lower:
        return "geometry lock prevents the needed change", "geometry_lock"
    if "reinforcement lock" in lower:
        return "reinforcement lock prevents the needed change", "reinforcement_lock"
    if "no material" in lower or "no candidate" in lower or "found no candidate" in lower:
        return "no material candidate reached target while preserving all governing checks", "no_material_candidate_reached_target"
    if fallback:
        return fallback, "no_material_candidate_reached_target"
    return None, None


def _normalise_engine_intent(intent: str) -> str:
    intent = str(intent or "").strip()
    if intent == "advisory_warning":
        return "specific_blocker"
    if intent in ENGINE_INTENTS:
        return intent
    return "specific_blocker"


def _build_presentation(context: dict, display_truth: dict, button_contract: dict) -> dict:
    headline = str(context.get("headline") or "Design guidance").strip() or "Design guidance"
    guidance_intent = str(context.get("guidance_intent") or "").strip()
    if guidance_intent not in _COMPAT_INTENTS:
        guidance_intent = "advisory_warning"
    primary_truth_source = str(display_truth.get("display_truth_source") or "").strip()
    primary_truth_in_target = bool(display_truth.get("displayed_within_target_band"))
    primary_item_has_actionable_updates = bool(context.get("primary_item_has_actionable_updates"))
    any_fail = bool(context.get("any_fail"))
    any_warn = bool(context.get("any_warn"))
    all_key_pass = bool(context.get("all_key_pass"))
    near_limit_util = bool(context.get("near_limit_util"))
    terminal_optimal = bool(context.get("terminal_optimal"))
    terminal_very_low_demand = bool(context.get("terminal_very_low_demand"))
    passive_underband_no_action = bool(context.get("passive_underband_no_action"))
    pending = bool(context.get("pending"))
    pending_commit_eligible = bool(context.get("pending_commit_eligible"))
    overdesigned = bool(context.get("overdesigned"))
    in_target_band = bool(context.get("in_target_band"))
    governing_action = str(context.get("governing_action") or "").strip()
    if not governing_action:
        governing_action = "current design"
    button_label = str(context.get("button_label") or "Apply Recommendation")
    pending_blocked_reason = context.get("pending_blocked_reason")
    feedback_blocked_reason = context.get("feedback_blocked_reason")
    solver_result_blocked_reason = context.get("solver_result_blocked_reason")
    feedback_blocks_primary_cta = bool(context.get("feedback_blocks_primary_cta"))
    solver_result_blocks_primary_cta = bool(context.get("solver_result_blocks_primary_cta"))
    candidate_search_evidence = _as_dict(context.get("candidate_search_evidence"))
    failure_detail_text = str(context.get("failure_detail_text") or "").strip()

    def out(
        *,
        theme: str,
        css_bucket: str,
        use_success_style: bool,
        subtext: str,
        button_theme: str,
        critical_status: str,
        headline_override: str | None = None,
        show_apply_button: bool = True,
        design_guide_terminal_state: str | None = None,
    ) -> dict:
        effective_show_apply = bool(show_apply_button)
        contract_allows_apply = bool(
            button_contract.get("enabled")
            or (
                button_contract.get("actionable")
                and _as_dict(button_contract.get("updates"))
                and button_contract.get("preview_pass") is True
                and button_contract.get("blocking_reason") in (None, "")
            )
        )
        effective_show_apply = bool(effective_show_apply and contract_allows_apply)
        if feedback_blocks_primary_cta or solver_result_blocks_primary_cta:
            effective_show_apply = False
        elif pending:
            effective_show_apply = bool(effective_show_apply and pending_commit_eligible)
        return {
            "theme": theme,
            "css_bucket": css_bucket,
            "use_success_style": bool(use_success_style),
            "headline": headline_override if headline_override is not None else headline,
            "subtext": subtext,
            "button_label": button_label,
            "button_theme": button_theme,
            "critical_status": critical_status,
            "governing_check": governing_action,
            "in_target_band": bool(primary_truth_in_target),
            "display_truth_source": primary_truth_source or None,
            "displayed_util": display_truth.get("displayed_util"),
            "displayed_status": display_truth.get("displayed_status"),
            "displayed_within_target_band": bool(primary_truth_in_target),
            "target_low": display_truth.get("target_low"),
            "target_high": display_truth.get("target_high"),
            "source_summary_util": display_truth.get("source_summary_util"),
            "source_candidate_util": display_truth.get("source_candidate_util"),
            "source_post_commit_util": display_truth.get("source_post_commit_util"),
            "overdesigned_unnecessarily": bool(overdesigned),
            "show_apply_button": bool(effective_show_apply),
            "commit_eligible": bool(pending_commit_eligible),
            "blocked_reason": solver_result_blocked_reason or feedback_blocked_reason or pending_blocked_reason,
            "design_guide_terminal_state": design_guide_terminal_state,
            "guidance_intent": guidance_intent,
        }

    if any_fail and guidance_intent != "required_fix":
        fail_subtext = f"Governing check: {governing_action}"
        if failure_detail_text:
            fail_subtext += f". Failing check: {failure_detail_text}"
        return out(
            theme="fail",
            css_bucket="fail",
            use_success_style=False,
            subtext=fail_subtext,
            button_theme="fail",
            critical_status="FAIL",
            show_apply_button=bool(primary_item_has_actionable_updates),
        )

    if guidance_intent == "required_fix":
        required_subtext = f"Governing check: {governing_action}. This card is a required capacity fix."
        if failure_detail_text:
            required_subtext += f" Failing check: {failure_detail_text}."
        if primary_truth_source == "candidate_preview" and not primary_truth_in_target:
            required_subtext += (
                " The preview remains outside the target band, so this is not a valid final "
                "one-click action unless a specific engineering blocker is proven."
            )
            if candidate_search_evidence:
                required_subtext += (
                    " Candidate search did not prove an executor-backed target-band action; "
                    "a physical or code blocker is required before this can be accepted."
                    if int(candidate_search_evidence.get("target_band_candidate_count") or 0) == 0
                    else " Candidate search found a target-band candidate; the selector should prefer it."
                )
        return out(
            theme="fail",
            css_bucket="fail",
            use_success_style=False,
            subtext=required_subtext,
            button_theme="fail",
            critical_status="FAIL",
            show_apply_button=True,
        )

    if guidance_intent == "efficiency_tightening":
        target_phrase = (
            "moves the preview into the target utilisation band"
            if primary_truth_source == "candidate_preview" and primary_truth_in_target
            else "moves the design toward the target utilisation band"
        )
        efficiency_subtext = f"All key checks pass; this lighter option {target_phrase}."
        if primary_truth_source == "candidate_preview" and not primary_truth_in_target:
            efficiency_subtext += (
                " Available discrete catalogue increments can skip the target band, so this "
                "is the closest safe material step found while preserving governing checks."
            )
            if candidate_search_evidence:
                efficiency_subtext += (
                    " Candidate search found no safe executor-backed target-band candidate."
                    if int(candidate_search_evidence.get("target_band_candidate_count") or 0) == 0
                    else " Candidate search found a safe target-band candidate; this recommendation should be reselected."
                )
        return out(
            theme="efficiency",
            css_bucket="efficiency",
            use_success_style=False,
            subtext=efficiency_subtext,
            button_theme="efficiency",
            critical_status="PASS",
            show_apply_button=True,
        )

    if guidance_intent == "optional_cleanup":
        cleanup_family = str(context.get("local_cleanup_family") or button_contract.get("family") or "local").strip().lower()
        if cleanup_family in {"bending", "geometry"}:
            cleanup_copy = (
                "Required target-band cleanup: bending reinforcement or section geometry is conservative "
                "while another check governs the design. This one-click move reduces local over-provision "
                "while keeping bending, shear, serviceability, ductility, and detailing checks acceptable."
            )
        elif cleanup_family == "shear":
            cleanup_copy = (
                "Optional cleanup: shear links are conservative and non-governing; reducing them "
                "can ease congestion but lowers shear reserve."
            )
        else:
            cleanup_copy = (
                "Optional cleanup: one non-governing design family has reserve beyond the material "
                "threshold; this move trims it while keeping all required checks acceptable."
            )
        return out(
            theme="efficiency",
            css_bucket="efficiency",
            use_success_style=False,
            subtext=cleanup_copy,
            button_theme="efficiency",
            critical_status="PASS",
            show_apply_button=bool(primary_item_has_actionable_updates),
        )

    if guidance_intent == "already_efficient":
        util = _as_float(display_truth.get("displayed_util"))
        lo = _as_float(display_truth.get("target_low"))
        hi = _as_float(display_truth.get("target_high"))
        util_text = f"{util:.2f}" if util is not None else "-"
        band_text = f"{lo:.2f}-{hi:.2f}" if lo is not None and hi is not None else "the configured target band"
        efficient_subtext = (
            "The current design is within the target utilisation band. "
            f"Current utilisation: {util_text}. Target band: {band_text}. "
            f"Governing check: {governing_action}. "
            "Further reductions were not selected because they would reduce reserve capacity, "
            "risk another governing check, violate detailing, ductility, or serviceability "
            "constraints, or provide no material benefit."
            if primary_truth_source == "published_summary" and primary_truth_in_target
            else (
                "Further reduction would lower reserve capacity or stiffness; the guide is explaining "
                "why no material one-click change is selected."
            )
        )
        return out(
            theme="healthy",
            css_bucket="pass",
            use_success_style=True,
            subtext=efficient_subtext,
            button_theme="healthy",
            critical_status="OPTIMAL",
            headline_override=(
                "Design is efficient - target band achieved"
                if primary_truth_in_target
                else "Design is efficient - no further safe cleanup available"
            ),
            show_apply_button=False,
            design_guide_terminal_state="optimal",
        )

    if guidance_intent == "advisory_warning" and not bool(primary_item_has_actionable_updates):
        return out(
            theme="fail" if any_fail else ("warn" if any_warn or near_limit_util else "info"),
            css_bucket="fail" if any_fail else ("warn" if any_warn or near_limit_util else "start"),
            use_success_style=False,
            subtext=(
                "The guide is explaining the current condition; no material one-click update is "
                "displayed because the solver found no candidate that preserved bending, shear, "
                "serviceability, and detailing checks."
            ),
            button_theme="fail" if any_fail else ("warn" if any_warn or near_limit_util else "start"),
            critical_status="FAIL" if any_fail else ("NEAR LIMIT" if any_warn or near_limit_util else "PASS"),
            show_apply_button=False,
        )

    if (
        terminal_optimal
        and all_key_pass
        and not any_fail
        and not any_warn
        and primary_truth_source == "published_summary"
        and primary_truth_in_target
        and not bool(primary_item_has_actionable_updates)
    ):
        return out(
            theme="healthy",
            css_bucket="pass",
            use_success_style=True,
            subtext=(
                "The current section is within the target utilisation range. Further reduction would "
                "lower reserve capacity or stiffness."
            ),
            button_theme="healthy",
            critical_status="OPTIMAL",
            headline_override="Design is efficient - further reductions would weaken capacity",
            show_apply_button=False,
            design_guide_terminal_state="optimal",
        )

    if any_fail:
        fail_subtext = f"Governing check: {governing_action}"
        if failure_detail_text:
            fail_subtext += f". Failing check: {failure_detail_text}"
        return out(
            theme="fail",
            css_bucket="fail",
            use_success_style=False,
            subtext=fail_subtext,
            button_theme="fail",
            critical_status="FAIL",
        )

    if any_warn or near_limit_util:
        return out(
            theme="warn",
            css_bucket="warn",
            use_success_style=False,
            subtext=(
                "A governing check is at NEAR LIMIT."
                if any_warn
                else "Utilisation is at the upper guidance threshold (near limit)."
            ),
            button_theme="warn",
            critical_status="NEAR LIMIT",
        )

    if passive_underband_no_action:
        return out(
            theme="info",
            css_bucket="start",
            use_success_style=False,
            subtext=(
                "All current checks pass, but the guide did not find a directly executable local "
                "cleanup that keeps every governing check acceptable."
            ),
            button_theme="start",
            critical_status="PASS",
            headline_override="Cleanup is advisory for this design state",
            show_apply_button=False,
        )

    if terminal_very_low_demand and all_key_pass and not any_fail and not any_warn:
        return out(
            theme="healthy",
            css_bucket="pass",
            use_success_style=True,
            subtext=(
                "Current section is easily adequate for the entered actions. "
                "No optimisation recommendation is shown for this trivial-demand case."
            ),
            button_theme="healthy",
            critical_status="PASS",
            headline_override="Design demand is very low",
            show_apply_button=False,
            design_guide_terminal_state="very_low_demand",
        )

    if in_target_band and (not overdesigned) and all_key_pass:
        band_subtext = (
            "The current design is inside the target band, so capacity is not being increased "
            "unnecessarily."
            if primary_truth_source == "published_summary" and primary_truth_in_target
            else "The guide is explaining the current condition using the published summary."
        )
        return out(
            theme="healthy",
            css_bucket="pass",
            use_success_style=True,
            subtext=band_subtext,
            button_theme="healthy",
            critical_status="PASS",
        )

    if overdesigned:
        return out(
            theme="efficiency",
            css_bucket="efficiency",
            use_success_style=False,
            subtext="The design has reserve beyond the target band; local cleanup is preferred when it stays compliant.",
            button_theme="efficiency",
            critical_status="PASS",
        )

    return out(
        theme="info",
        css_bucket="start",
        use_success_style=False,
        subtext="Complete or review checks for full guidance.",
        button_theme="start",
        critical_status="-",
    )


def resolve_design_guide_card(
    state: dict,
    *,
    summary: dict | None = None,
    target_band: dict | None = None,
    debug: bool = False,
) -> dict:
    """Resolve the single Design Guide card and CTA contract from prepared state."""
    prepared = _as_dict(state)
    primary_item = _as_dict(prepared.get("primary_item"))
    overview = _as_dict(summary or prepared.get("overview"))
    context = _as_dict(prepared.get("presentation_context"))
    goal = str(prepared.get("goal") or context.get("goal") or "balanced")
    band = _target_band(goal, target_band if isinstance(target_band, dict) else prepared.get("target_band"))
    target_low = _as_float(band.get("target_low"))
    target_high = _as_float(band.get("target_high"))
    if target_low is None or target_high is None or target_low >= target_high:
        target_low, target_high = get_target_utilisation_band(goal)
        band = target_band_payload(goal)

    display_truth = _as_dict(prepared.get("display_truth") or primary_item.get("display_truth"))
    display_truth.setdefault("target_low", target_low)
    display_truth.setdefault("target_high", target_high)
    candidate_search_evidence = _as_dict(
        prepared.get("candidate_search_evidence")
        or primary_item.get("candidate_search_evidence")
        or _as_dict(primary_item.get("action_payload")).get("candidate_search_evidence")
        or _as_dict(primary_item.get("resolved_candidate")).get("candidate_search_evidence")
    )
    in_target_primary_refinement = bool(
        primary_item.get("allow_in_target_primary_action")
        or _as_dict(primary_item.get("resolved_candidate")).get("allow_in_target_primary_action")
        or str(primary_item.get("design_guide_refinement_priority") or "").strip()
        == "shear_congestion_reshape"
        or (
            bool(candidate_search_evidence.get("selected_candidate_updates"))
            and "shear congestion" in str(candidate_search_evidence.get("selected_candidate_title") or "").lower()
        )
    )
    local_cleanup_blocks_terminal = bool(
        candidate_search_evidence.get("terminal_state_blocked_by_local_cleanup")
        or int(candidate_search_evidence.get("safe_local_cleanup_count") or 0) > 0
    )
    unresolved_low_util_families = _low_util_families_without_evidence(overview, context, float(target_low))
    if unresolved_low_util_families:
        context["unresolved_low_util_families"] = list(unresolved_low_util_families)
        context["passive_underband_no_action"] = True
    failure_detail_text = _failure_detail_text(overview, context)
    if failure_detail_text:
        context["failure_detail_text"] = failure_detail_text
    source_summary_util = _as_float(
        display_truth.get("source_summary_util")
        if display_truth.get("source_summary_util") is not None
        else overview.get("worst_util")
    )
    current_in_target_terminal = bool(
        source_summary_util is not None
        and float(target_low) <= float(source_summary_util) <= float(target_high)
        and not _has_required_failure(overview, context)
        and not in_target_primary_refinement
        and not local_cleanup_blocks_terminal
        and not unresolved_low_util_families
    )
    if current_in_target_terminal:
        display_truth = {
            **display_truth,
            "display_truth_source": "published_summary",
            "displayed_util": source_summary_util,
            "displayed_status": display_truth.get("source_summary_status") or overview.get("worst_status") or "PASS",
            "displayed_within_target_band": True,
            "source_summary_util": source_summary_util,
            "source_candidate_util": display_truth.get("source_candidate_util"),
            "source_post_commit_util": display_truth.get("source_post_commit_util"),
            "target_low": target_low,
            "target_high": target_high,
        }
        context = {
            **context,
            "guidance_intent": "already_efficient",
            "terminal_optimal": True,
            "in_target_band": True,
            "overdesigned": False,
            "primary_item_has_actionable_updates": False,
            "pending": False,
            "pending_commit_eligible": False,
            "any_fail": False,
        }

    raw_contract = _as_dict(prepared.get("button_contract") or primary_item.get("button_contract"))
    button_contract = _normalise_button_contract(primary_item, raw_contract, display_truth)
    if current_in_target_terminal:
        button_contract = {
            **button_contract,
            "enabled": False,
            "actionable": False,
            "action_type": None,
            "updates": {},
            "preview_pass": False,
            "blocking_reason": "current design is inside the target utilisation band",
            "preview_util": None,
            "post_click_expected_util": None,
        }
    if candidate_search_evidence:
        context["candidate_search_evidence"] = dict(candidate_search_evidence)

    presentation = _build_presentation(context, display_truth, button_contract)
    display_source = str(display_truth.get("display_truth_source") or presentation.get("display_truth_source") or "published_summary")
    displayed_util = _as_float(display_truth.get("displayed_util") if display_truth.get("displayed_util") is not None else presentation.get("displayed_util"))
    current_util = _as_float(
        display_truth.get("source_summary_util")
        if display_truth.get("source_summary_util") is not None
        else overview.get("worst_util")
    )
    preview_util = _as_float(button_contract.get("preview_util") if button_contract.get("preview_util") is not None else display_truth.get("source_candidate_util"))
    post_util = _as_float(display_truth.get("source_post_commit_util"))
    outcome_preview = preview_util if preview_util is not None else displayed_util
    lands_in_band = _within_band(outcome_preview, float(target_low), float(target_high))
    current_distance = _distance_to_band(current_util, float(target_low), float(target_high))
    preview_distance = _distance_to_band(outcome_preview, float(target_low), float(target_high))
    moves_toward = bool(
        current_distance is not None
        and preview_distance is not None
        and preview_distance < current_distance
    )
    blocker_text = " ".join(
        str(v or "")
        for v in (
            button_contract.get("blocking_reason"),
            presentation.get("subtext"),
            primary_item.get("reason"),
            primary_item.get("body"),
        )
    )
    allowed_blocker, allowed_blocker_category = (None, None)
    if not lands_in_band:
        allowed_blocker, allowed_blocker_category = _blocker_from_text(blocker_text)

    engine_intent = _normalise_engine_intent(presentation.get("guidance_intent") or context.get("guidance_intent"))
    card = {
        "title": presentation.get("headline") or primary_item.get("title_main") or "Design guidance",
        "badge": presentation.get("critical_status"),
        "intent": engine_intent,
        "family": button_contract.get("family") or primary_item.get("check_key"),
        "body": presentation.get("subtext") or "",
        "change_text": prepared.get("change_text") or primary_item.get("change_text"),
        "why_text": prepared.get("why_text") or primary_item.get("why_text"),
        "other_options_text": prepared.get("other_options_text") or primary_item.get("other_options_text"),
        "status_text": presentation.get("critical_status"),
        "displayed_util": displayed_util,
        "display_truth_source": display_source,
        "target_low": float(target_low),
        "target_high": float(target_high),
        "target_band_source": band.get("source") or "canonical_config",
        "within_target_band": _within_band(displayed_util, float(target_low), float(target_high)),
        "candidate_search_evidence": dict(candidate_search_evidence),
    }
    target_band_outcome = {
        "current_util": current_util,
        "preview_util": preview_util,
        "post_click_util": post_util,
        "lands_in_target_band": bool(lands_in_band),
        "moves_toward_target": bool(moves_toward),
        "allowed_blocker": allowed_blocker,
        "allowed_blocker_category": allowed_blocker_category,
    }
    raw_count = int(prepared.get("raw_item_count") or (1 if primary_item else 0))
    suppressed_reasons = list(prepared.get("suppressed_reasons") or [])
    decision_reason = str(
        prepared.get("decision_reason")
        or f"selected_{presentation.get('guidance_intent') or engine_intent}"
    )
    engine_debug = {
        "raw_item_count": raw_count,
        "selected_candidate_id": button_contract.get("candidate_id"),
        "suppressed_count": int(prepared.get("suppressed_count") or len(suppressed_reasons)),
        "suppressed_reasons": suppressed_reasons,
        "decision_reason": decision_reason,
        "candidate_search_evidence": dict(candidate_search_evidence),
    }
    result = {
        "card": card,
        "button_contract": button_contract,
        "target_band_outcome": target_band_outcome,
        "debug": engine_debug,
        "presentation": presentation,
    }
    if debug:
        result["target_band"] = dict(band)
    return result


def _item_signature(item: dict) -> tuple:
    payload = _as_dict(item.get("action_payload"))
    contract = _as_dict(item.get("button_contract"))
    updates = _as_dict(
        contract.get("updates")
        or payload.get("resolved_candidate_updates")
        or payload.get("updates")
    )
    return (
        str(item.get("guidance_intent") or ""),
        str(item.get("title_main") or item.get("title") or ""),
        str(item.get("action_type") or ""),
        tuple(sorted((str(k), repr(v)) for k, v in updates.items())),
    )


def _dedupe_raw_items(raw_items: list[dict]) -> tuple[list[dict], list[str]]:
    seen: set[tuple] = set()
    out: list[dict] = []
    suppressed: list[str] = []
    for idx, raw in enumerate(raw_items or []):
        if not isinstance(raw, dict):
            suppressed.append(f"non_dict_item_at_{idx}")
            continue
        sig = _item_signature(raw)
        if sig in seen:
            suppressed.append(f"duplicate_item:{raw.get('title_main') or raw.get('title') or idx}")
            continue
        seen.add(sig)
        out.append(dict(raw))
    return out, suppressed


def _governing_util(summary: dict, display_truth: dict) -> float | None:
    util = _as_float(display_truth.get("source_summary_util"))
    if util is not None:
        return util
    util = _as_float(summary.get("worst_util"))
    if util is not None:
        return util
    utils = summary.get("utils")
    if isinstance(utils, dict):
        values = [_as_float(v) for v in utils.values()]
        values = [v for v in values if v is not None]
        if values:
            return max(values)
    return None


def _current_state_in_target_terminal(summary: dict, display_truth: dict, context: dict, low: float, high: float) -> bool:
    util = _governing_util(summary, display_truth)
    return bool(
        util is not None
        and low <= float(util) <= high
        and not _has_required_failure(summary, context)
    )


def _has_in_target_primary_refinement_candidate(
    raw_candidates: list[dict],
    target_low: float,
    target_high: float,
) -> bool:
    for raw in raw_candidates or []:
        if not isinstance(raw, dict):
            continue
        resolved = _candidate_nested_dict(raw, "resolved_candidate")
        evidence = _as_dict(
            raw.get("candidate_search_evidence")
            or _as_dict(raw.get("action_payload")).get("candidate_search_evidence")
            or resolved.get("candidate_search_evidence")
        )
        updates = _candidate_updates(raw)
        candidate = normalise_design_guide_candidate(raw, target_low, target_high)
        is_executable = bool(candidate.get("safe") and candidate.get("updates"))
        is_local_cleanup = bool(
            raw.get("local_cleanup_candidate")
            or resolved.get("local_cleanup_candidate")
            or str(raw.get("source") or "").strip() == "generate_in_target_local_cleanup_candidates"
            or str(raw.get("guidance_intent") or "").strip() == "optional_cleanup"
        )
        if is_local_cleanup and is_executable:
            return True
        if not (
            bool(raw.get("allow_in_target_primary_action"))
            or bool(resolved.get("allow_in_target_primary_action"))
            or str(raw.get("design_guide_refinement_priority") or resolved.get("design_guide_refinement_priority") or "")
            == "shear_congestion_reshape"
            or (
                bool(evidence.get("selected_candidate_updates"))
                and "shear congestion" in str(evidence.get("selected_candidate_title") or "").lower()
            )
            or (
                bool(updates)
                and _candidate_affects_family("shear", updates)
                and str(raw.get("guidance_intent") or "").strip() == "optional_cleanup"
            )
        ):
            continue
        if is_executable:
            return True
        if bool(updates):
            return True
        if bool(evidence.get("selected_candidate_updates")):
            return True
    return False


def _candidate_search_evidence_from_items(
    *,
    selected_item: dict,
    raw_items: list[dict],
    candidate_evidence: dict | None,
    target_low: float,
    target_high: float,
) -> dict:
    evidence = _as_dict(
        selected_item.get("candidate_search_evidence")
        or _as_dict(selected_item.get("action_payload")).get("candidate_search_evidence")
        or _as_dict(selected_item.get("resolved_candidate")).get("candidate_search_evidence")
        or candidate_evidence
    )
    if evidence:
        evidence.setdefault("target_low", float(target_low))
        evidence.setdefault("target_high", float(target_high))
        return evidence

    candidates: list[dict] = []
    for idx, item in enumerate(raw_items or [], start=1):
        if not isinstance(item, dict):
            continue
        contract = _as_dict(item.get("button_contract"))
        truth = _as_dict(item.get("display_truth"))
        updates = _as_dict(
            contract.get("updates")
            or _as_dict(item.get("action_payload")).get("resolved_candidate_updates")
            or _as_dict(item.get("action_payload")).get("updates")
        )
        util = _as_float(
            contract.get("expected_util")
            if contract.get("expected_util") is not None
            else truth.get("source_candidate_util")
        )
        if util is None:
            util = _as_float(truth.get("displayed_util"))
        candidate_id = (
            contract.get("source_candidate_id")
            or item.get("source_candidate_id")
            or item.get("candidate_id")
            or f"displayed_candidate_{idx:03d}"
        )
        safe = bool(
            updates
            and contract.get("preview_pass") is True
            and contract.get("blocking_reason") in (None, "")
            and str(contract.get("action_type") or item.get("action_type") or "").strip()
        )
        distance = _distance_to_band(util, target_low, target_high)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "title": item.get("title_main") or item.get("title") or f"Displayed candidate {idx}",
                "updates": dict(updates),
                "preview_util": util,
                "candidate_post_util": util,
                "distance_to_band": distance,
                "safe_executor_backed": safe,
            }
        )

    safe_candidates = [c for c in candidates if c.get("safe_executor_backed")]
    target_candidates = [
        c for c in safe_candidates
        if _within_band(_as_float(c.get("preview_util")), target_low, target_high)
    ]
    closest = min(
        safe_candidates,
        key=lambda c: (
            float(c.get("distance_to_band") if c.get("distance_to_band") is not None else 1e9),
            str(c.get("title") or ""),
        ),
        default=None,
    )
    selected_contract = _as_dict(selected_item.get("button_contract"))
    selected_id = (
        selected_contract.get("source_candidate_id")
        or selected_item.get("source_candidate_id")
        or selected_item.get("candidate_id")
        or (candidates[0].get("candidate_id") if candidates else None)
    )
    selected_util = None
    for cand in candidates:
        if str(cand.get("candidate_id")) == str(selected_id):
            selected_util = _as_float(cand.get("preview_util"))
            break
    if selected_util is None:
        selected_util = _as_float(selected_contract.get("expected_util"))
    selected_distance = _distance_to_band(selected_util, target_low, target_high)
    return {
        "candidate_search_exhaustive": False,
        "target_low": float(target_low),
        "target_high": float(target_high),
        "total_candidates_considered": len(candidates),
        "safe_executor_backed_candidates_count": len(safe_candidates),
        "target_band_candidate_count": len(target_candidates),
        "selected_candidate_id": selected_id,
        "selected_candidate_title": selected_item.get("title_main") or selected_item.get("title"),
        "selected_candidate_util": selected_util,
        "selected_candidate_distance_to_band": selected_distance,
        "closest_safe_candidate_id": None if closest is None else closest.get("candidate_id"),
        "closest_safe_candidate_title": None if closest is None else closest.get("title"),
        "closest_safe_candidate_util": None if closest is None else closest.get("preview_util"),
        "closest_safe_candidate_distance_to_band": None if closest is None else closest.get("distance_to_band"),
        "best_target_band_candidate_id": target_candidates[0].get("candidate_id") if target_candidates else None,
        "best_target_band_candidate_title": target_candidates[0].get("title") if target_candidates else None,
        "best_target_band_candidate_util": target_candidates[0].get("preview_util") if target_candidates else None,
        "target_band_candidates": list(target_candidates),
        "rejected_target_band_candidates": [],
        "rejected_target_band_candidate_reasons": [],
        "outside_target_band_allowed": False,
        "outside_target_band_allowed_reason": None,
        "outside_target_band_allowed_category": None,
    }


def _item_button_contract(item: dict) -> dict:
    return _as_dict(item.get("button_contract") or _as_dict(item.get("action_payload")).get("button_contract"))


def _item_updates(item: dict) -> dict:
    contract = _item_button_contract(item)
    return _as_dict(
        contract.get("updates")
        or _as_dict(item.get("action_payload")).get("resolved_candidate_updates")
        or _as_dict(item.get("action_payload")).get("updates")
        or _as_dict(item.get("resolved_candidate")).get("updates")
    )


def _item_preview_util(item: dict) -> float | None:
    contract = _item_button_contract(item)
    truth = _as_dict(item.get("display_truth"))
    value = contract.get("expected_util")
    if value is None:
        value = item.get("resolved_candidate_post_util")
    if value is None:
        value = _as_dict(item.get("action_payload")).get("resolved_candidate_post_util")
    if value is None:
        value = _as_dict(item.get("resolved_candidate")).get("candidate_post_util")
    if value is None:
        value = truth.get("source_candidate_util")
    if value is None:
        value = truth.get("displayed_util")
    return _as_float(value)


def _item_safe_executor_backed(item: dict) -> bool:
    contract = _item_button_contract(item)
    updates = _item_updates(item)
    action_type = str(contract.get("action_type") or item.get("action_type") or "").strip()
    blocking_reason = contract.get("blocking_reason")
    preview_pass = contract.get("preview_pass")
    if preview_pass is None:
        preview_pass = True if updates else False
    return bool(updates and action_type and preview_pass is True and blocking_reason in (None, ""))


def _prefer_target_band_item(
    items: list[dict],
    *,
    target_low: float,
    target_high: float,
    terminal_in_target: bool,
) -> tuple[list[dict], list[str]]:
    if terminal_in_target or not items:
        return items, []
    target_rows: list[tuple[tuple, int, dict]] = []
    target_mid = (float(target_low) + float(target_high)) / 2.0
    for idx, item in enumerate(items):
        if not isinstance(item, dict) or not _item_safe_executor_backed(item):
            continue
        util = _item_preview_util(item)
        if util is None or not _within_band(util, target_low, target_high):
            continue
        target_rows.append(
            (
                (
                    abs(float(util) - target_mid),
                    len(_item_updates(item)),
                    idx,
                ),
                idx,
                item,
            )
        )
    if not target_rows:
        return items, []
    target_rows.sort(key=lambda row: row[0])
    selected_idx = int(target_rows[0][1])
    if selected_idx == 0:
        return items, []
    selected = dict(items[selected_idx])
    remaining = [dict(item) for idx, item in enumerate(items) if idx != selected_idx]
    return [selected] + remaining, [
        f"target_band_candidate_promoted_from_index:{selected_idx}",
    ]


def _outside_target_evidence_allows_recommendation(evidence: dict, selected_util: float | None, low: float, high: float) -> tuple[bool, str | None, str | None]:
    if selected_util is None or _within_band(selected_util, low, high):
        return True, None, None
    if not evidence:
        return False, "candidate search evidence is missing for an outside-target preview", "no_material_candidate_reached_target"
    if not bool(evidence.get("candidate_search_exhaustive")):
        return False, "candidate search was not exhaustive for an outside-target preview", "no_material_candidate_reached_target"
    if int(evidence.get("target_band_candidate_count") or 0) > 0:
        return False, "a safe target-band candidate exists and should be selected", "no_material_candidate_reached_target"
    if int(evidence.get("safe_executor_backed_candidates_count") or 0) <= 0:
        return False, "no safe executor-backed candidate was proven for this outside-target preview", "not_executor_backed"
    if not bool(evidence.get("outside_target_band_allowed")):
        return False, "outside-target recommendation was not explicitly allowed by candidate evidence", "no_material_candidate_reached_target"
    category = str(evidence.get("outside_target_band_allowed_category") or "").strip()
    reason = str(evidence.get("outside_target_band_allowed_reason") or "").strip()
    if not category or category in {"under_current_rules", "manual_review", "no_candidate_attached", "move_set_failed", "unknown"}:
        return False, "outside-target blocker category is not specific", "no_material_candidate_reached_target"
    return True, reason or "no safe executor-backed target-band candidate was found", category


def _specific_blocker_decision(
    *,
    base_decision: dict,
    reason: str,
    category: str,
    target_low: float,
    target_high: float,
    evidence: dict,
) -> dict:
    decision = dict(base_decision)
    card = dict(decision.get("card") or {})
    button = dict(decision.get("button_contract") or {})
    outcome = dict(decision.get("target_band_outcome") or {})
    family = str(card.get("family") or card.get("check_key") or "").strip().lower()
    safe_executor_count = int(evidence.get("safe_executor_backed_candidates_count") or 0)
    existing_executable_action = bool(
        button.get("actionable")
        and _as_dict(button.get("updates"))
        and button.get("preview_pass") is True
        and button.get("blocking_reason") in (None, "")
    )
    if existing_executable_action:
        safe_executor_count = max(safe_executor_count, 1)
    outside_target_allowed = bool(evidence.get("outside_target_band_allowed")) and bool(
        str(evidence.get("outside_target_band_allowed_category") or "").strip()
    )
    allowed_outside_target_action = bool(existing_executable_action and outside_target_allowed)
    if allowed_outside_target_action:
        blocker_theme = "efficiency"
        blocker_bucket = "efficiency"
        blocker_button_theme = "efficiency"
        if family == "shear":
            title = "Shear cleanup - best safe one-click reduction"
            body = (
                "A safe one-click shear cleanup is available. The preview does not land in the "
                "target band, so any remaining utilisation gap must be resolved by the post-click "
                "blocker evidence."
            )
        elif family == "bending":
            title = "Bending cleanup - best safe one-click reduction"
            body = (
                "A safe one-click bending cleanup is available. The preview does not land in the "
                "target band, so any remaining utilisation gap must be resolved by the post-click "
                "blocker evidence."
            )
        else:
            title = "Cleanup - best safe one-click reduction"
            body = (
                "A safe one-click cleanup is available. The preview does not land in the target "
                "band, so any remaining utilisation gap must be resolved by the post-click blocker evidence."
            )
        badge = "RECOMMEND"
        status_text = "OPTIMISE"
        intent = str(card.get("intent") or "efficiency_tightening")
    else:
        blocker_theme = "efficiency"
        blocker_bucket = "efficiency"
        blocker_button_theme = "efficiency"
        title = (
            "Shear cleanup blocked by engineering limits"
            if family == "shear"
            else "Bending cleanup blocked by engineering limits"
            if family == "bending"
            else "Cleanup blocked by engineering limits"
        )
        if safe_executor_count > 0:
            body = (
                "A safe preview was found, but it does not reach the accepted target band. "
                f"Reason: {reason}."
            )
        else:
            body = f"No safe one-click cleanup is available for this state. Reason: {reason}."
        badge = "INFO"
        status_text = "INFO"
        intent = "specific_blocker"
    card.update(
        {
            "title": title,
            "badge": badge,
            "intent": intent,
            "theme": blocker_theme,
            "css_bucket": blocker_bucket,
            "use_success_style": False,
            "body": body,
            "status_text": status_text,
            "candidate_search_evidence": dict(evidence),
        }
    )
    if allowed_outside_target_action:
        button.update(
            {
                "enabled": True,
                "actionable": True,
                "preview_pass": True,
                "blocking_reason": None,
            }
        )
    else:
        button.update(
            {
                "enabled": False,
                "actionable": False,
                "updates": {},
                "blocking_reason": reason,
            }
        )
    outcome.update(
        {
            "lands_in_target_band": False,
            "allowed_blocker": reason,
            "allowed_blocker_category": category,
        }
    )
    presentation = dict(decision.get("presentation") or {})
    presentation.update(
        {
            "theme": blocker_theme,
            "css_bucket": blocker_bucket,
            "use_success_style": False,
            "headline": card["title"],
            "subtext": card["body"],
            "show_apply_button": bool(allowed_outside_target_action and button.get("actionable")),
            "button_theme": blocker_button_theme,
            "critical_status": status_text,
            "guidance_intent": intent,
        }
    )
    debug = dict(decision.get("debug") or {})
    debug["decision_reason"] = f"specific_blocker:{category}"
    debug["candidate_search_evidence"] = dict(evidence)
    decision.update(
        {
            "card": card,
            "button_contract": button,
            "target_band_outcome": outcome,
            "presentation": presentation,
            "candidate_search_evidence": dict(evidence),
            "debug": debug,
        }
    )
    return decision


def resolve_design_guide_decision(
    *,
    current_state: dict,
    summary: dict | None,
    raw_items: list[dict],
    candidate_evidence: dict | None = None,
    raw_candidates: list[dict] | None = None,
    target_band: dict | None = None,
    context: dict | None = None,
) -> dict:
    """Resolve the one user-visible Design Guide decision from raw items.

    Candidate generation remains outside this module for now. This function owns
    the final selection gate, terminal in-target override, button contract,
    display-truth stamping, outside-target evidence gate, and card copy.
    """
    state = _as_dict(current_state)
    overview = _as_dict(summary)
    ctx = _as_dict(context)
    goal = str(ctx.get("goal") or state.get("design_optimisation_goal") or state.get("goal") or "balanced")
    band = _target_band(goal, target_band)
    target_low = float(_as_float(band.get("target_low")) or get_target_utilisation_band(goal)[0])
    target_high = float(_as_float(band.get("target_high")) or get_target_utilisation_band(goal)[1])
    items, suppressed_reasons = _dedupe_raw_items(list(raw_items or []))
    raw_count = len([item for item in raw_items or [] if isinstance(item, dict)])
    primary_item = dict(items[0]) if items else {}
    primary_truth = _as_dict(primary_item.get("display_truth"))
    terminal_in_target = _current_state_in_target_terminal(
        overview,
        primary_truth,
        ctx,
        target_low,
        target_high,
    )
    winner_source_candidates = list(raw_candidates or items or [])
    local_cleanup_evidence, local_cleanup_selected_raw = _build_local_cleanup_evidence(
        raw_candidates=winner_source_candidates,
        current_state=state,
        summary=overview,
        context=ctx,
        target_low=target_low,
        target_high=target_high,
    )
    in_target_primary_refinement = _has_in_target_primary_refinement_candidate(
        winner_source_candidates,
        target_low,
        target_high,
    )
    terminal_blocked_by_local_cleanup = bool(
        terminal_in_target
        and int(local_cleanup_evidence.get("safe_local_cleanup_count") or 0) > 0
    )
    if terminal_blocked_by_local_cleanup:
        terminal_in_target = False
        suppressed_reasons.append("terminal_in_target_blocked_by_safe_local_cleanup")
        if local_cleanup_selected_raw:
            selected_id = _candidate_id(local_cleanup_selected_raw)
            winner_source_candidates = [dict(local_cleanup_selected_raw)] + [
                dict(candidate) for candidate in winner_source_candidates
                if str(_candidate_id(candidate) or "") != str(selected_id or "")
            ]
    if terminal_in_target and in_target_primary_refinement:
        terminal_in_target = False
        suppressed_reasons.append("terminal_in_target_blocked_by_primary_refinement")
    selection_context = {
        **ctx,
        "candidate_search_evidence": dict(candidate_evidence or ctx.get("candidate_search_evidence") or {}),
    }
    winner_result = select_target_band_winner(
        raw_candidates=winner_source_candidates,
        current_state=state,
        summary=overview,
        target_band=dict(band),
        context=selection_context,
    )
    winner_candidate = _as_dict(winner_result.get("selected_candidate"))
    winner_raw = _as_dict(winner_candidate.get("raw"))
    if not terminal_in_target and winner_raw:
        winner_id = str(winner_candidate.get("candidate_id") or "")
        winner_util = _as_float(winner_candidate.get("preview_util"))
        current_primary_id = str(_candidate_id(primary_item) or "")
        current_primary_util = _candidate_preview_util(primary_item)
        if (
            winner_id
            and (
                winner_id != current_primary_id
                or (winner_util is not None and current_primary_util != winner_util)
            )
        ):
            primary_item = dict(winner_raw)
            items = [primary_item] + [
                dict(item) for item in items
                if str(_candidate_id(item) or "") != winner_id
            ]
            suppressed_reasons.append(f"engine_target_band_winner_selected:{winner_id}")
    elif not terminal_in_target:
        items, target_promote_reasons = _prefer_target_band_item(
            items,
            target_low=target_low,
            target_high=target_high,
            terminal_in_target=terminal_in_target,
        )
        suppressed_reasons.extend(target_promote_reasons)
        primary_item = dict(items[0]) if items else {}
    primary_truth = _as_dict(primary_item.get("display_truth"))
    if terminal_in_target:
        suppressed_reasons.extend(
            f"terminal_in_target_suppressed:{item.get('title_main') or item.get('title') or idx}"
            for idx, item in enumerate(items[1:], start=1)
        )
        items = [primary_item] if primary_item else []
    evidence = dict(winner_result.get("candidate_search_evidence") or {})
    if not evidence:
        evidence = _candidate_search_evidence_from_items(
            selected_item=primary_item,
            raw_items=items,
            candidate_evidence=candidate_evidence,
            target_low=target_low,
            target_high=target_high,
        )
    if evidence:
        evidence["selected_candidate_id"] = evidence.get("selected_candidate_id") or _candidate_id(primary_item)
        evidence["selected_candidate_title"] = evidence.get("selected_candidate_title") or _candidate_title(primary_item)
        evidence["selected_candidate_util"] = (
            evidence.get("selected_candidate_util")
            if evidence.get("selected_candidate_util") is not None
            else _candidate_preview_util(primary_item)
        )
        evidence["selected_candidate_updates"] = dict(
            evidence.get("selected_candidate_updates") or _candidate_updates(primary_item)
        )
        primary_item["candidate_search_evidence"] = dict(evidence)
        primary_item["candidate_id"] = evidence.get("selected_candidate_id") or primary_item.get("candidate_id")
        primary_item["source_candidate_id"] = evidence.get("selected_candidate_id") or primary_item.get("source_candidate_id")
        payload_for_evidence = _as_dict(primary_item.get("action_payload"))
        payload_for_evidence["candidate_search_evidence"] = dict(evidence)
        payload_for_evidence["source_candidate_id"] = evidence.get("selected_candidate_id")
        primary_item["action_payload"] = payload_for_evidence
        resolved_for_evidence = _as_dict(primary_item.get("resolved_candidate"))
        resolved_for_evidence["candidate_search_evidence"] = dict(evidence)
        resolved_for_evidence["candidate_id"] = evidence.get("selected_candidate_id")
        resolved_for_evidence["source_candidate_id"] = evidence.get("selected_candidate_id")
        primary_item["resolved_candidate"] = resolved_for_evidence
        contract_for_evidence = _as_dict(primary_item.get("button_contract"))
        if contract_for_evidence:
            contract_for_evidence["source_candidate_id"] = evidence.get("selected_candidate_id")
            primary_item["button_contract"] = contract_for_evidence
    evidence.update(dict(local_cleanup_evidence))
    primary_item["candidate_search_evidence"] = dict(evidence)
    if terminal_blocked_by_local_cleanup:
        cleanup_family = str(primary_item.get("family") or primary_item.get("check_key") or "").strip().lower() or None
        for family in list(local_cleanup_evidence.get("materially_overprovided_families") or []):
            if cleanup_family:
                break
            cleanup_family = str(family or "").strip().lower()
        if cleanup_family == "bending":
            cleanup_title = "Bending cleanup - further reduction reaches target range"
        elif cleanup_family == "shear":
            cleanup_title = "Design is safe - optional shear cleanup available"
        else:
            cleanup_title = "Design is safe - optional local cleanup available"
        primary_item["guidance_intent"] = (
            "efficiency_tightening" if cleanup_family == "bending" else "optional_cleanup"
        )
        primary_item["title_main"] = cleanup_title
        primary_item["title"] = cleanup_title
        primary_item["check_key"] = cleanup_family or primary_item.get("check_key") or "bending"
        primary_item["family"] = cleanup_family or primary_item.get("family")
        primary_truth = {
            **primary_truth,
            "display_truth_source": "candidate_preview",
            "displayed_util": _candidate_preview_util(primary_item),
            "displayed_status": "PASS",
            "displayed_within_target_band": _within_band(_candidate_preview_util(primary_item), target_low, target_high),
            "target_low": target_low,
            "target_high": target_high,
            "source_summary_util": (
                _summary_family_util(overview, cleanup_family)
                if cleanup_family in {"bending", "shear"}
                else _governing_util(overview, {})
            ),
            "source_candidate_util": _candidate_preview_util(primary_item),
        }
        primary_item["display_truth"] = dict(primary_truth)
    prepared = {
        "goal": goal,
        "primary_item": dict(primary_item),
        "overview": dict(overview),
        "efficiency_state": dict(ctx.get("efficiency_state") or {}),
        "display_truth": dict(primary_truth),
        "button_contract": dict(primary_item.get("button_contract") or {}),
        "candidate_search_evidence": dict(evidence),
        "raw_item_count": raw_count,
        "suppressed_count": max(0, raw_count - 1),
        "suppressed_reasons": list(suppressed_reasons),
        "decision_reason": "terminal_in_target" if terminal_in_target else str(winner_result.get("selection_status") or "selected_engine_target_band_winner"),
        "presentation_context": {
            **ctx,
            "candidate_search_evidence": dict(evidence),
            "headline": (
                primary_item.get("title_main")
                if terminal_blocked_by_local_cleanup
                else (ctx.get("headline") or primary_item.get("title_main") or primary_item.get("title") or "Design guidance")
            ),
            "guidance_intent": (
                primary_item.get("guidance_intent")
                if terminal_blocked_by_local_cleanup
                else (ctx.get("guidance_intent") or primary_item.get("guidance_intent"))
            ),
            "local_cleanup_family": primary_item.get("family") or primary_item.get("check_key"),
            "primary_item_has_actionable_updates": bool(
                ctx.get("primary_item_has_actionable_updates")
                or _as_dict(primary_item.get("button_contract")).get("updates")
                or _as_dict(primary_item.get("action_payload")).get("resolved_candidate_updates")
            ),
        },
    }
    decision = resolve_design_guide_card(
        prepared,
        summary=overview,
        target_band=dict(band),
        debug=True,
    )
    card = dict(decision.get("card") or {})
    presentation = dict(decision.get("presentation") or {})
    card.update(
        {
            "theme": presentation.get("theme"),
            "css_bucket": presentation.get("css_bucket"),
            "use_success_style": bool(presentation.get("use_success_style")),
            "governing_check": presentation.get("governing_check"),
        }
    )
    decision["card"] = card
    decision["candidate_search_evidence"] = dict(evidence)
    card.update(
        {
            "family_utils": dict(local_cleanup_evidence.get("family_utils") or {}),
            "materially_overprovided_families": list(local_cleanup_evidence.get("materially_overprovided_families") or []),
            "local_cleanup_search_ran": local_cleanup_evidence.get("local_cleanup_search_ran"),
            "local_cleanup_search_exhaustive": local_cleanup_evidence.get("local_cleanup_search_exhaustive"),
            "safe_local_cleanup_count": local_cleanup_evidence.get("safe_local_cleanup_count"),
            "local_cleanup_candidates": list(local_cleanup_evidence.get("local_cleanup_candidates") or []),
            "local_cleanup_candidate_inventory": list(local_cleanup_evidence.get("local_cleanup_candidate_inventory") or []),
            "local_cleanup_candidate_inventory_count": local_cleanup_evidence.get("local_cleanup_candidate_inventory_count"),
            "candidate_inventory_count": local_cleanup_evidence.get("candidate_inventory_count"),
            "rejected_local_cleanup_count": local_cleanup_evidence.get("rejected_local_cleanup_count"),
            "local_cleanup_blocked_reasons": list(local_cleanup_evidence.get("local_cleanup_blocked_reasons") or []),
            "local_cleanup_blocked_reasons_by_family": dict(local_cleanup_evidence.get("local_cleanup_blocked_reasons_by_family") or {}),
            "unsupported_cleanup_families": list(local_cleanup_evidence.get("unsupported_cleanup_families") or []),
            "terminal_state_reason": local_cleanup_evidence.get("terminal_state_reason"),
            "terminal_state_blocked_by_local_cleanup": local_cleanup_evidence.get("terminal_state_blocked_by_local_cleanup"),
        }
    )
    decision["card"] = card
    preview_util = _as_float((decision.get("target_band_outcome") or {}).get("preview_util"))
    button = _as_dict(decision.get("button_contract"))
    active_strength_failures = _active_strength_failure_families(overview, ctx)
    combined_route_failures = set(active_strength_failures)
    if "shear" in combined_route_failures and _item_signals_bending_active_failure(primary_item):
        combined_route_failures.add("bending")
    active_strength_action = bool(active_strength_failures and _button_enabled(button))
    combined_fail_family_route_used = False
    shear_fail_family_route_used = False
    if combined_route_failures >= {"bending", "shear"}:
        combined_route = _route_combined_fail_family_decision(
            decision=decision,
            primary_item=primary_item,
            overview=overview,
            context=ctx,
            evidence=evidence,
            active_strength_failures=combined_route_failures,
        )
        decision = _as_dict(combined_route.get("decision") or decision)
        primary_item = _as_dict(combined_route.get("primary_item") or primary_item)
        evidence = _as_dict(decision.get("candidate_search_evidence") or evidence)
        button = _as_dict(decision.get("button_contract"))
        combined_fail_family_route_used = bool(combined_route.get("used"))
        if combined_fail_family_route_used:
            active_strength_action = True
            active_strength_failures = set(combined_route_failures)
    elif active_strength_failures == {"shear"}:
        shear_route = _route_shear_fail_family_decision(
            decision=decision,
            primary_item=primary_item,
            overview=overview,
            context=ctx,
            evidence=evidence,
            active_strength_failures=active_strength_failures,
        )
        decision = _as_dict(shear_route.get("decision") or decision)
        primary_item = _as_dict(shear_route.get("primary_item") or primary_item)
        evidence = _as_dict(decision.get("candidate_search_evidence") or evidence)
        button = _as_dict(decision.get("button_contract"))
        shear_fail_family_route_used = bool(shear_route.get("used"))
        if shear_fail_family_route_used:
            active_strength_action = True
    if active_strength_action and not shear_fail_family_route_used and not combined_fail_family_route_used:
        if active_strength_failures >= {"bending", "shear"}:
            active_family = "combined"
            active_title = "Bending and shear capacity are low"
        elif "shear" in active_strength_failures:
            active_family = "shear"
            active_title = "Shear capacity is low"
        else:
            active_family = "bending"
            active_title = "Bending capacity is low"
        card = dict(decision.get("card") or {})
        card.update(
            {
                "title": active_title,
                "badge": "REPAIR",
                "intent": "required_fix",
                "theme": "fail",
                "css_bucket": "fail",
                "use_success_style": False,
                "family": active_family,
                "check_key": active_family,
                "body": (
                    "Active strength capacity is failing; this one-click repair is "
                    "executor-backed and keeps all required checks acceptable."
                ),
                "status_text": "FAIL",
            }
        )
        presentation = dict(decision.get("presentation") or {})
        presentation.update(
            {
                "theme": "fail",
                "css_bucket": "fail",
                "use_success_style": False,
                "headline": active_title,
                "subtext": card["body"],
                "show_apply_button": True,
                "critical_status": "FAIL",
                "guidance_intent": "required_fix",
            }
        )
        button = {
            **button,
            "enabled": True,
            "actionable": True,
            "family": active_family,
            "blocking_reason": None,
        }
        decision["card"] = card
        decision["presentation"] = presentation
        decision["button_contract"] = button
        decision["candidate_search_evidence"] = {
            **dict(decision.get("candidate_search_evidence") or {}),
            "active_strength_repair_action": True,
            "active_strength_repair_family": active_family,
        }
        primary_item["title_main"] = active_title
        primary_item["title"] = active_title
        primary_item["family"] = active_family
        primary_item["check_key"] = active_family
        primary_item["guidance_intent"] = "required_fix"
        contract_for_active = _as_dict(primary_item.get("button_contract"))
        if contract_for_active:
            contract_for_active["family"] = active_family
            contract_for_active["blocking_reason"] = None
            primary_item["button_contract"] = contract_for_active
    if button.get("enabled") and preview_util is not None and not _within_band(preview_util, target_low, target_high):
        allowed, reason, category = _outside_target_evidence_allows_recommendation(
            evidence,
            preview_util,
            target_low,
            target_high,
        )
        if not allowed and not active_strength_action:
            decision = _specific_blocker_decision(
                base_decision=decision,
                reason=reason or "outside-target recommendation lacks candidate-search proof",
                category=category or "no_material_candidate_reached_target",
                target_low=target_low,
                target_high=target_high,
                evidence=evidence,
            )
    debug = dict(decision.get("debug") or {})
    debug.setdefault("raw_item_count", raw_count)
    debug["selected_item_title"] = primary_item.get("title_main") or primary_item.get("title")
    debug["target_band_selection_status"] = winner_result.get("selection_status")
    debug["target_band_selection_reason"] = winner_result.get("selection_reason")
    debug.update(
        {
            "family_utils": dict(local_cleanup_evidence.get("family_utils") or {}),
            "materially_overprovided_families": list(local_cleanup_evidence.get("materially_overprovided_families") or []),
            "local_cleanup_search_ran": local_cleanup_evidence.get("local_cleanup_search_ran"),
            "local_cleanup_search_exhaustive": local_cleanup_evidence.get("local_cleanup_search_exhaustive"),
            "safe_local_cleanup_count": local_cleanup_evidence.get("safe_local_cleanup_count"),
            "local_cleanup_candidates": list(local_cleanup_evidence.get("local_cleanup_candidates") or []),
            "local_cleanup_candidate_inventory": list(local_cleanup_evidence.get("local_cleanup_candidate_inventory") or []),
            "local_cleanup_candidate_inventory_count": local_cleanup_evidence.get("local_cleanup_candidate_inventory_count"),
            "candidate_inventory_count": local_cleanup_evidence.get("candidate_inventory_count"),
            "rejected_local_cleanup_count": local_cleanup_evidence.get("rejected_local_cleanup_count"),
            "local_cleanup_blocked_reasons": list(local_cleanup_evidence.get("local_cleanup_blocked_reasons") or []),
            "local_cleanup_blocked_reasons_by_family": dict(local_cleanup_evidence.get("local_cleanup_blocked_reasons_by_family") or {}),
            "unsupported_cleanup_families": list(local_cleanup_evidence.get("unsupported_cleanup_families") or []),
            "terminal_state_reason": local_cleanup_evidence.get("terminal_state_reason"),
            "terminal_state_blocked_by_local_cleanup": local_cleanup_evidence.get("terminal_state_blocked_by_local_cleanup"),
        }
    )
    debug["suppressed_count"] = max(int(debug.get("suppressed_count") or 0), max(0, raw_count - 1))
    debug["suppressed_reasons"] = list(debug.get("suppressed_reasons") or suppressed_reasons)
    debug["decision_reason"] = debug.get("decision_reason") or prepared["decision_reason"]
    decision["debug"] = debug
    decision.update(
        {
            "family_utils": dict(local_cleanup_evidence.get("family_utils") or {}),
            "materially_overprovided_families": list(local_cleanup_evidence.get("materially_overprovided_families") or []),
            "local_cleanup_search_ran": local_cleanup_evidence.get("local_cleanup_search_ran"),
            "local_cleanup_search_exhaustive": local_cleanup_evidence.get("local_cleanup_search_exhaustive"),
            "safe_local_cleanup_count": local_cleanup_evidence.get("safe_local_cleanup_count"),
            "local_cleanup_candidates": list(local_cleanup_evidence.get("local_cleanup_candidates") or []),
            "local_cleanup_candidate_inventory": list(local_cleanup_evidence.get("local_cleanup_candidate_inventory") or []),
            "local_cleanup_candidate_inventory_count": local_cleanup_evidence.get("local_cleanup_candidate_inventory_count"),
            "candidate_inventory_count": local_cleanup_evidence.get("candidate_inventory_count"),
            "rejected_local_cleanup_count": local_cleanup_evidence.get("rejected_local_cleanup_count"),
            "local_cleanup_blocked_reasons": list(local_cleanup_evidence.get("local_cleanup_blocked_reasons") or []),
            "local_cleanup_blocked_reasons_by_family": dict(local_cleanup_evidence.get("local_cleanup_blocked_reasons_by_family") or {}),
            "unsupported_cleanup_families": list(local_cleanup_evidence.get("unsupported_cleanup_families") or []),
            "terminal_state_reason": local_cleanup_evidence.get("terminal_state_reason"),
            "terminal_state_blocked_by_local_cleanup": local_cleanup_evidence.get("terminal_state_blocked_by_local_cleanup"),
        }
    )
    return decision
