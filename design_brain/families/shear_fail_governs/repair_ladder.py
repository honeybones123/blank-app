from __future__ import annotations

from typing import Any

from design_brain.evidence import candidate_rows_from_evidence


PREFERRED_MINIMUM_SPACING_MM = 100.0
DEFAULT_WIDTH_STEP_MM = 50.0


def _as_plain_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_plain_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _as_optional_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_family_status(value: Any) -> str:
    return str(value or "").strip().upper()


def shear_fail_candidate_updates(row: dict) -> dict:
    row_d = _as_plain_dict(row)
    return _as_plain_dict(row_d.get("updates") or row_d.get("proposed_updates") or row_d.get("selected_candidate_updates"))


def shear_fail_candidate_id(row: dict, index: int) -> str:
    return str(row.get("candidate_id") or row.get("source_candidate_id") or row.get("id") or f"candidate_{index}")


def is_shear_fail_candidate(row: dict) -> bool:
    row_d = _as_plain_dict(row)
    family_text = " ".join(
        str(row_d.get(key) or "")
        for key in (
            "family",
            "affected_family",
            "recommendation_family_tag",
            "title",
            "label",
            "candidate_id",
        )
    ).lower()
    updates = shear_fail_candidate_updates(row_d)
    return bool(
        "shear" in family_text
        or "lig" in family_text
        or "link" in family_text
        or set(updates) & {"lig_d", "lig_legs", "s_lig"}
    )


def is_safe_shear_fail_executor_backed(row: dict) -> bool:
    row_d = _as_plain_dict(row)
    return bool(
        row_d.get("safe_executor_backed")
        or row_d.get("executor_backed")
        or row_d.get("is_executable")
        or (row_d.get("preview_pass") is True and shear_fail_candidate_updates(row_d))
    )


def find_promotable_shear_fail_repair_candidate(evidence: dict, candidate_rows: list[dict]) -> dict:
    evidence_d = _as_plain_dict(evidence)
    rows = [dict(row) for row in list(candidate_rows or []) if isinstance(row, dict)]
    candidates = [row for row in rows if is_shear_fail_candidate(row) and is_safe_shear_fail_executor_backed(row)]
    if not candidates:
        selected_updates = _as_plain_dict(
            evidence_d.get("selected_candidate_updates")
            or evidence_d.get("closest_safe_candidate_updates")
            or evidence_d.get("best_safe_candidate_updates")
        )
        if selected_updates:
            return {
                "candidate_id": str(
                    evidence_d.get("selected_candidate_id")
                    or evidence_d.get("closest_safe_candidate_id")
                    or evidence_d.get("best_safe_candidate_id")
                    or "shear_fail_selected_repair"
                ),
                "title": str(
                    evidence_d.get("selected_candidate_title")
                    or evidence_d.get("closest_safe_candidate_title")
                    or evidence_d.get("best_safe_candidate_title")
                    or "Shear capacity repair"
                ),
                "updates": dict(selected_updates),
                "preview_pass": evidence_d.get("selected_candidate_preview_pass", True),
                "safe_executor_backed": True,
                "is_executable": True,
                "action_type": "apply_resolved_candidate",
                "candidate_post_util": evidence_d.get("selected_candidate_util") or evidence_d.get("closest_safe_candidate_util"),
                "family": "shear",
            }
        return {}
    closest_id = str(
        evidence_d.get("selected_candidate_id")
        or evidence_d.get("closest_safe_candidate_id")
        or evidence_d.get("best_safe_candidate_id")
        or ""
    ).strip()
    if closest_id:
        for row in candidates:
            if str(row.get("candidate_id") or row.get("source_candidate_id") or "").strip() == closest_id:
                return dict(row)
    return dict(candidates[0])


def build_shear_fail_candidate_rows(evidence: dict) -> list[dict]:
    return [dict(row) for row in candidate_rows_from_evidence(_as_plain_dict(evidence)) if isinstance(row, dict)]


def build_shear_fail_exact_blockers(evidence: dict, primary: dict, debug: dict) -> dict:
    evidence_d = _as_plain_dict(evidence)
    primary_d = _as_plain_dict(primary)
    debug_d = _as_plain_dict(debug)
    merged: dict[str, dict] = {}
    for key in (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    ):
        for source in (
            evidence_d.get(key),
            primary_d.get(key),
            _as_plain_dict(primary_d.get("action_payload")).get(key),
            _as_plain_dict(primary_d.get("resolved_candidate")).get(key),
            debug_d.get(key),
        ):
            if not isinstance(source, dict):
                continue
            row = source.get("shear")
            if isinstance(row, dict):
                merged["shear"] = {**merged.get("shear", {}), **dict(row)}
    return merged


def shear_fail_state_float(state: dict, key: str, default: float) -> float:
    value = _as_plain_dict(state).get(key)
    if value in (None, ""):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def shear_fail_state_int(state: dict, key: str, default: int) -> int:
    value = _as_plain_dict(state).get(key)
    if value in (None, ""):
        return int(default)
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def dedupe_shear_fail_repair_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for spec in specs:
        updates = _as_plain_dict(spec.get("updates"))
        key = tuple(sorted((str(key), repr(value)) for key, value in updates.items()))
        if not updates or key in seen:
            continue
        seen.add(key)
        out.append(dict(spec))
    return out


def shear_fail_active_failures(summary: dict, evidence: dict, debug: dict, classifier: dict) -> list[str]:
    summary_d = _as_plain_dict(summary)
    evidence_d = _as_plain_dict(evidence)
    debug_d = _as_plain_dict(debug)
    classifier_d = _as_plain_dict(classifier)
    failures: set[str] = {
        str(item or "").strip().lower()
        for item in _as_plain_list(classifier_d.get("active_failures"))
        if str(item or "").strip()
    }
    for source in (
        evidence_d.get("active_failures"),
        debug_d.get("active_failures"),
        summary_d.get("fail_keys"),
        debug_d.get("fail_keys"),
    ):
        for item in _as_plain_list(source):
            text = str(item or "").strip().lower()
            if text:
                failures.add(text)
    for family, status in _as_plain_dict(summary_d.get("statuses")).items():
        if _normalise_family_status(status) == "FAIL":
            failures.add(str(family or "").strip().lower())
    return sorted(failures)


def shear_fail_status(summary: dict, evidence: dict, debug: dict) -> str:
    summary_d = _as_plain_dict(summary)
    evidence_d = _as_plain_dict(evidence)
    debug_d = _as_plain_dict(debug)
    for source in (
        _as_plain_dict(summary_d.get("statuses")),
        _as_plain_dict(evidence_d.get("statuses")),
        _as_plain_dict(debug_d.get("statuses")),
    ):
        status = _normalise_family_status(source.get("shear"))
        if status:
            return status
    family_status_current = _as_plain_dict(evidence_d.get("family_status_current") or debug_d.get("family_status_current"))
    return _normalise_family_status(_as_plain_dict(family_status_current.get("shear")).get("status"))


def shear_fail_util(summary: dict, evidence: dict, debug: dict) -> float | None:
    summary_d = _as_plain_dict(summary)
    evidence_d = _as_plain_dict(evidence)
    debug_d = _as_plain_dict(debug)
    for source in (
        _as_plain_dict(summary_d.get("utils")),
        _as_plain_dict(evidence_d.get("utils")),
        _as_plain_dict(evidence_d.get("family_utils")),
        _as_plain_dict(debug_d.get("family_utils")),
    ):
        parsed = _as_optional_float(source.get("shear"))
        if parsed is not None:
            return parsed
    family_status_current = _as_plain_dict(evidence_d.get("family_status_current") or debug_d.get("family_status_current"))
    return _as_optional_float(_as_plain_dict(family_status_current.get("shear")).get("util"))


def build_shear_fail_spacing_ladder(
    current_spacing: float,
    reo_spacings: tuple[float, ...],
    *,
    preferred_minimum_spacing_mm: float = PREFERRED_MINIMUM_SPACING_MM,
) -> list[float]:
    current = float(current_spacing or 200.0)
    minimum = float(preferred_minimum_spacing_mm)
    eligible = sorted(
        {
            float(value)
            for value in reo_spacings
            if minimum <= float(value) < current - 1e-9
        }
    )
    if minimum not in eligible and minimum < current - 1e-9:
        eligible.insert(0, minimum)
    # Contract intent is strongest spacing first, then relax if that creates a detailing side effect.
    return sorted(set(eligible))


def build_shear_fail_diameter_ladder(current_dia: int, diameters: tuple[int, ...]) -> list[int]:
    current = int(current_dia or 10)
    return [int(value) for value in diameters if int(value) > current]


def build_shear_fail_width_ladder(
    current_width: float,
    depth: float,
    *,
    step_mm: float = DEFAULT_WIDTH_STEP_MM,
) -> list[float]:
    width = float(current_width or 0.0)
    depth_value = float(depth or 0.0)
    if width <= 0.0 or depth_value <= 0.0 or width >= depth_value - 1e-9:
        return []
    values: list[float] = []
    next_width = width + float(step_mm)
    while next_width <= depth_value + 1e-9:
        values.append(float(min(next_width, depth_value)))
        next_width += float(step_mm)
    return values


def build_shear_fail_normalised_update_diff(base: dict, updates: dict) -> dict:
    base_d = _as_plain_dict(base)
    out: dict[str, Any] = {}
    for key, value in _as_plain_dict(updates).items():
        if key not in base_d or str(base_d.get(key)) != str(value):
            out[key] = value
    return out


def build_shear_fail_repair_ladder_spec_payload(
    *,
    ladder_index: int,
    step: int,
    strategy: str,
    updates: dict,
    restart_point: bool = False,
    escalation: str | None = None,
) -> dict[str, Any]:
    index = int(ladder_index)
    return {
        "ladder_index": index,
        "contract_step": int(step),
        "strategy": strategy,
        "updates": _as_plain_dict(updates),
        "restart_point": bool(restart_point),
        "escalation": escalation,
        "candidate_family_id": "SHEAR_FAIL_GOVERNS",
        "label": f"SHEAR_FAIL_GOVERNS ladder {index}: {strategy}",
    }


def select_shear_fail_repair_candidate_from_ladder(
    candidates: list[dict],
    *,
    target_low: float,
    target_high: float,
    ranking_strategy: str,
) -> dict[str, Any]:
    rows = [dict(row) for row in list(candidates or []) if isinstance(row, dict)]
    safe = [
        row for row in rows
        if bool(row.get("is_compliant"))
        and bool(_as_plain_dict(row.get("overview")).get("all_key_pass"))
        and not bool(_as_plain_dict(row.get("overview")).get("any_fail"))
    ]
    if not safe:
        return {
            "selected": None,
            "ranking_strategy": ranking_strategy,
            "selection_reason": "no_compliant_candidate_in_contract_ladder",
            "candidate_count": len(rows),
            "safe_candidate_count": 0,
        }
    target_mid = (float(target_low) + float(target_high)) / 2.0
    selected = min(
        safe,
        key=lambda row: (
            int(row.get("shear_fail_ladder_index") or row.get("ladder_index") or 999999),
            abs(
                float(
                    row.get("candidate_post_util")
                    or row.get("worst_util")
                    or _as_plain_dict(row.get("overview")).get("worst_util")
                    or 0.0
                )
                - target_mid
            ),
        ),
    )
    return {
        "selected": dict(selected),
        "ranking_strategy": ranking_strategy,
        "selection_reason": "first_compliant_candidate_in_contract_ladder_order",
        "candidate_count": len(rows),
        "safe_candidate_count": len(safe),
        "selected_ladder_index": int(selected.get("shear_fail_ladder_index") or selected.get("ladder_index") or 0),
    }


def build_shear_fail_repair_ladder_evidence_overlay(
    *,
    ladder: dict,
    selected_result: dict,
    family_route_owner: str,
    family_candidate_strategy: str,
    family_ranking_strategy: str,
    family_evidence_strategy: str,
    family_publication_rule: str,
    family_cta_rule: str,
) -> dict[str, Any]:
    ladder_d = _as_plain_dict(ladder)
    selected_result_d = _as_plain_dict(selected_result)
    selected = _as_plain_dict(selected_result_d.get("selected"))
    return {
        "governing_family": "SHEAR_FAIL_GOVERNS",
        "family_name": "SHEAR_FAIL_GOVERNS",
        "family_route_owner": family_route_owner,
        "family_candidate_strategy": family_candidate_strategy,
        "family_ranking_strategy": family_ranking_strategy,
        "family_evidence_strategy": family_evidence_strategy,
        "family_publication_rule": family_publication_rule,
        "family_cta_rule": family_cta_rule,
        "shear_fail_contract_ladder_used": True,
        "shear_fail_contract_ladder_candidate_count": len(list(ladder_d.get("specs") or [])),
        "shear_fail_contract_ladder_spacing_values": list(ladder_d.get("spacing_values_tried") or []),
        "shear_fail_contract_ladder_diameters": list(ladder_d.get("lig_diameters_tried") or []),
        "shear_fail_contract_ladder_widths": list(ladder_d.get("widths_tried") or []),
        "shear_fail_contract_restart_rule": ladder_d.get("restart_rule"),
        "shear_fail_contract_stop_reason_if_no_candidate": ladder_d.get("stop_reason_if_no_candidate"),
        "shear_fail_selected_ladder_index": selected_result_d.get("selected_ladder_index"),
        "shear_fail_selection_reason": selected_result_d.get("selection_reason"),
        "selected_candidate_updates": shear_fail_candidate_updates(selected),
    }


__all__ = [
    "DEFAULT_WIDTH_STEP_MM",
    "PREFERRED_MINIMUM_SPACING_MM",
    "build_shear_fail_candidate_rows",
    "build_shear_fail_diameter_ladder",
    "build_shear_fail_exact_blockers",
    "build_shear_fail_normalised_update_diff",
    "build_shear_fail_repair_ladder_evidence_overlay",
    "build_shear_fail_repair_ladder_spec_payload",
    "build_shear_fail_spacing_ladder",
    "build_shear_fail_width_ladder",
    "dedupe_shear_fail_repair_specs",
    "find_promotable_shear_fail_repair_candidate",
    "is_safe_shear_fail_executor_backed",
    "is_shear_fail_candidate",
    "select_shear_fail_repair_candidate_from_ladder",
    "shear_fail_active_failures",
    "shear_fail_candidate_id",
    "shear_fail_state_float",
    "shear_fail_state_int",
    "shear_fail_status",
    "shear_fail_util",
    "shear_fail_candidate_updates",
]
