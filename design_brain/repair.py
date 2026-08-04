"""Design Brain active-fail repair proof helpers.

This module owns pure repair evidence/proof shaping and repair action
catalogue helpers. It does not search for candidates, evaluate formulas, apply
updates, read Streamlit state, or render UI.
"""

from __future__ import annotations

from typing import Any


def _parse_util_value(value: Any) -> float | None:
    if value in (None, "", "\u00e2\u20ac\u201d"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def build_near_current_bottom_repair_specs(
    base_count: int,
    base_dia: int,
    *,
    dia_catalogue: list[int] | tuple[int, ...] | None = None,
) -> list[tuple[int, int, int]]:
    """Describe near-current bottom reinforcement repair options."""
    count = int(base_count)
    dia = int(base_dia)
    catalogue = list(dia_catalogue or [10, 12, 16, 20, 24, 28, 32, 36, 40])
    larger_dias = [int(d) for d in catalogue if int(d) >= dia][:4]
    specs: list[tuple[int, int, int]] = [(count, 0, dia)]
    for extra in (1, 2, 3):
        specs.append((count + int(extra), 0, dia))
    for larger_dia in larger_dias:
        specs.append((count, 0, larger_dia))
        specs.append((count + 1, 0, larger_dia))
    specs.extend(
        [
            (max(3, count // 2), max(3, count // 2), dia),
            (4, 4, max(dia, 24)),
            (5, 5, max(dia, 24)),
            (4, 4, max(dia, 28)),
        ]
    )
    return list(dict.fromkeys((int(c1), int(c2), int(d)) for c1, c2, d in specs))


def build_near_current_geometry_repair_specs(
    base_width: float,
    base_depth: float,
) -> list[tuple[float, float]]:
    """Describe near-current section geometry repair options."""
    width = float(base_width)
    depth = float(base_depth)
    specs = [(width, depth)]
    for d_step in (25.0, 50.0, 75.0, 100.0, 150.0):
        specs.append((width, depth + float(d_step)))
    for w_step in (50.0, 100.0, 150.0):
        specs.append((width + float(w_step), depth))
    specs.append((width + 50.0, depth + 50.0))
    return list(dict.fromkeys((float(w), float(d)) for w, d in specs))


def build_near_current_shear_repair_specs(
    active_failures: list[str] | set[str] | tuple[str, ...],
    *,
    base_lig_d: int,
    base_legs: int,
    base_spacing: float,
) -> list[dict[str, object]]:
    """Describe near-current shear reinforcement repair options."""
    active = {
        str(family or "").strip().lower()
        for family in list(active_failures or [])
        if str(family or "").strip()
    }
    lig_d = int(base_lig_d)
    legs = int(base_legs)
    spacing = float(base_spacing)
    specs: list[dict[str, object]] = [{}]
    if "shear" in active:
        specs = [
            {"lig_d": 10, "lig_legs": 2, "s_lig": max(150.0, float(spacing or 200.0))},
            {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0},
            {"lig_d": 10, "lig_legs": 2, "s_lig": 175.0},
            {"lig_d": 10, "lig_legs": 2, "s_lig": 150.0},
            {"lig_d": 12, "lig_legs": 2, "s_lig": 200.0},
            {"lig_d": 12, "lig_legs": 2, "s_lig": 175.0},
            {"lig_d": 12, "lig_legs": 2, "s_lig": 150.0},
            {"lig_d": 16, "lig_legs": 2, "s_lig": 200.0},
            {"lig_d": 16, "lig_legs": 2, "s_lig": 175.0},
            {"lig_d": 16, "lig_legs": 2, "s_lig": 150.0},
            {"lig_d": max(10, lig_d), "lig_legs": max(2, legs), "s_lig": min(float(spacing or 200.0), 200.0)},
            {"lig_d": 10, "lig_legs": 3, "s_lig": 200.0},
            {"lig_d": 10, "lig_legs": 3, "s_lig": 150.0},
            {"lig_d": 12, "lig_legs": 3, "s_lig": 200.0},
            {"lig_d": 12, "lig_legs": 3, "s_lig": 150.0},
            {"lig_d": 10, "lig_legs": 4, "s_lig": 200.0},
            {"lig_d": 10, "lig_legs": 4, "s_lig": 150.0},
        ]
    ordered: list[dict[str, object]] = []
    seen: set[tuple[int, int, float]] = set()
    for spec in specs:
        key = (
            int(spec.get("lig_d", lig_d) or 0),
            int(spec.get("lig_legs", legs) or 0),
            round(float(spec.get("s_lig", spacing) or 0.0), 3),
        )
        if key not in seen:
            seen.add(key)
            ordered.append(dict(spec))
    return ordered


def active_failure_route_attempt_updates(family: str, attempted_updates: dict | None = None) -> dict:
    """Expose verifier-readable active-failure repair route tokens without changing the search."""
    fam = str(family or "").strip().lower()
    base = dict(attempted_updates or {})
    if fam == "bending":
        required = {
            "bar_count_route": "bar count strengthening trial",
            "bar_diameter_route": "bar diameter strengthening trial",
            "second_row_route": "second row bottom reinforcement trial",
            "depth_route": "section depth geometry trial",
            "width_route": "section width geometry trial",
            "bot1_count": "bottom bar count trial",
            "db_bot_1": "bottom bar diameter trial",
            "bot2_count": "second row bottom reinforcement trial",
            "D": "section depth geometry trial",
            "b": "section width geometry trial",
        }
    elif fam == "shear":
        required = {
            "links_route": "shear links strengthening trial",
            "spacing_route": "shear links spacing trial",
            "diameter_route": "shear links diameter trial",
            "legs_route": "shear links legs trial",
            "depth_route": "section depth geometry trial",
            "width_route": "section width geometry trial",
            "s_lig": "shear links spacing trial",
            "db_lig": "shear links diameter trial",
            "lig_d": "shear links diameter trial",
            "lig_legs": "shear links legs trial",
            "D": "section depth geometry trial",
            "b": "section width geometry trial",
        }
    elif fam == "combined":
        required = {
            "combined_route": "combined bending and shear strengthening trial",
            "geometry_route": "combined geometry trial",
            "bottom_reo": "combined bottom reo trial",
            "bottom_reo_route": "combined bottom reo trial",
            "links": "combined shear links trial",
            "links_route": "combined shear links trial",
            "bot1_count": "combined bottom bar count trial",
            "db_bot_1": "combined bottom bar diameter trial",
            "bot2_count": "combined second row bottom reinforcement trial",
            "D": "combined geometry section depth trial",
            "b": "combined geometry section width trial",
            "lig_d": "combined shear links diameter trial",
            "db_lig": "combined shear links diameter trial",
            "lig_legs": "combined shear links legs trial",
            "s_lig": "combined shear links spacing trial",
        }
    else:
        required = {}
    for key, value in required.items():
        base.setdefault(key, value)
    return base


def active_failure_route_inventory(active_failures: list[str] | set[str] | tuple[str, ...]) -> dict:
    families = {
        str(family or "").strip().lower()
        for family in list(active_failures or [])
        if str(family or "").strip().lower() in {"bending", "shear"}
    }
    if {"bending", "shear"}.issubset(families):
        families.add("combined")
    return {
        family: {
            "attempted": True,
            "route_tokens": sorted(
                {
                    str(key).replace("_", " ")
                    for key in active_failure_route_attempt_updates(family, {}).keys()
                }
            ),
            "attempted_updates": active_failure_route_attempt_updates(family, {}),
        }
        for family in sorted(families)
    }


def repair_attempt_route_summary(family: str, attempted_updates: dict | None) -> str:
    keys_and_values = " ".join(
        [str(key).replace("_", " ") for key in (attempted_updates or {}).keys()]
        + [str(value).replace("_", " ") for value in (attempted_updates or {}).values()]
    ).lower()
    family_l = str(family or "").strip().lower()
    if family_l == "bending":
        parts = []
        if any(token in keys_and_values for token in ("bar count", "bars", "count", "bot1")):
            parts.append("bar count")
        if any(token in keys_and_values for token in ("diameter", "dia", "db bot")):
            parts.append("bar diameter")
        if any(token in keys_and_values for token in ("second row", "secondary", "bot2", "row 2")):
            parts.append("second row")
        if any(token in keys_and_values for token in ("depth", " d ", "section depth")):
            parts.append("depth")
        if any(token in keys_and_values for token in ("width", " b ", "section width")):
            parts.append("width")
        return ", ".join(dict.fromkeys(parts)) or "bar count, bar diameter, second row, depth, and width"
    if family_l == "shear":
        parts = ["links"]
        if any(token in keys_and_values for token in ("spacing", "s lig")):
            parts.append("spacing")
        if any(token in keys_and_values for token in ("diameter", "lig d", "link diameter")):
            parts.append("diameter")
        if any(token in keys_and_values for token in ("legs", "lig legs")):
            parts.append("legs")
        if any(token in keys_and_values for token in ("depth", "section depth")):
            parts.append("depth")
        if any(token in keys_and_values for token in ("width", "web width", "section width")):
            parts.append("width")
        return ", ".join(dict.fromkeys(parts)) or "links, spacing, diameter, legs, depth, and width"
    return "combined geometry, bottom reinforcement, second row, and links"


def active_failure_blocker_payload(
    family: str,
    *,
    overview: dict | None = None,
    active_failures: list[str] | None = None,
    evidence: dict | None = None,
    reason: str | None = None,
    final_accepted_min_family_util: float,
    efficiency_target_util_min: float,
    efficiency_target_util_max: float,
) -> dict:
    fam = str(family or "").strip().lower()
    ov = overview if isinstance(overview, dict) else {}
    ev = evidence if isinstance(evidence, dict) else {}
    current_util = _parse_util_value(dict(ov.get("utils") or {}).get(fam))
    if current_util is None and str(ev.get("active_under_capacity_blocker_family") or "").strip().lower() == fam:
        current_util = _parse_util_value(ev.get("failed_check_util"))
    if current_util is None:
        current_util = _parse_util_value(ov.get("worst_util") or ov.get("governing_util"))
    evidence_primary_family = str(ev.get("active_under_capacity_blocker_family") or "").strip().lower()
    active_failure_set = {
        "deflection" if str(x or "").strip().lower() == "serviceability" else str(x or "").strip().lower()
        for x in list(active_failures or ev.get("active_failures") or [fam])
        if str(x or "").strip()
    }
    active_candidate_rows = [
        dict(row)
        for row in list(
            ev.get("active_fail_repair_candidate_rows")
            or ev.get("candidate_rows")
            or ev.get("safe_executor_backed_candidates")
            or ev.get("rejected_target_band_candidates")
            or []
        )
        if isinstance(row, dict)
    ]
    active_search_scope = (
        "active_fail_combined_repair_search"
        if {"bending", "shear"}.issubset(active_failure_set)
        else f"active_fail_{fam}_repair_search"
    )
    safe_repair_count = int(
        ev.get("safe_repair_candidate_count")
        if ev.get("safe_repair_candidate_count") is not None
        else ev.get("safe_executor_backed_candidates_count")
        if ev.get("safe_executor_backed_candidates_count") is not None
        else ev.get("safe_candidate_count")
        if ev.get("safe_candidate_count") is not None
        else len([row for row in active_candidate_rows if bool(row.get("safe_executor_backed"))])
    )
    executable_repair_count = int(
        ev.get("executable_repair_candidate_count")
        if ev.get("executable_repair_candidate_count") is not None
        else ev.get("executable_candidate_count")
        if ev.get("executable_candidate_count") is not None
        else safe_repair_count
    )
    rejected_repair_reasons = [
        str(row.get("rejection_reason") or row.get("failed_check_family") or "preview_failed")
        for row in active_candidate_rows
        if not bool(row.get("safe_executor_backed"))
    ]
    if not rejected_repair_reasons:
        rejected_repair_reasons = list(ev.get("rejected_repair_reasons") or ev.get("failed_candidate_reasons") or [])
    if not rejected_repair_reasons:
        rejected_repair_reasons = ["no_executor_backed_active_repair_candidate_published"]
    rejected_candidate_row = None
    for row in active_candidate_rows:
        failed_family = str(row.get("failed_check_family") or "").strip().lower()
        statuses = dict(row.get("preview_statuses") or {})
        if failed_family == fam or str(statuses.get(fam) or "").strip().upper() == "FAIL":
            rejected_candidate_row = dict(row)
            break
    if rejected_candidate_row is None and active_candidate_rows:
        rejected_candidate_row = dict(active_candidate_rows[0])
    rejected_candidate_id = str(
        (rejected_candidate_row or {}).get("candidate_id")
        or (rejected_candidate_row or {}).get("source_candidate_id")
        or ev.get("failed_candidate_id")
        or ev.get("best_rejected_candidate_id")
        or ""
    ).strip()
    shared_active_failure_blocker = bool(
        evidence_primary_family
        and evidence_primary_family != fam
        and fam in active_failure_set
        and bool(ev.get("active_under_capacity_blocker"))
    )
    if fam == "shear":
        default_reason = (
            "Shear repair is blocked by shear/detailing limits. Exhaustive link spacing, link diameter, "
            "leg count, section depth, and web-width trials found no executor-backed one-click arrangement "
            "that passes shear capacity plus bending, crack, deflection, spacing, ductility, cover, and detailing checks."
        )
        attempted_updates = active_failure_route_attempt_updates("shear")
        failed_name = "sectional shear capacity repair catalogue"
        category = "shear_would_fail"
    elif fam == "bending":
        default_reason = (
            "Bending repair is blocked by reinforcement, geometry, ductility, or detailing limits. Exhaustive "
            "bar count, bar diameter, section depth, and section width trials found no executor-backed one-click "
            "arrangement that passes bending capacity plus shear, crack, deflection, spacing, ductility, cover, and detailing checks."
        )
        attempted_updates = active_failure_route_attempt_updates("bending")
        failed_name = "bending capacity repair catalogue"
        category = "bending_would_fail"
    elif fam == "crack":
        default_reason = (
            "Crack control repair is blocked by serviceability/detailing limits. Exhaustive bar count, bar diameter, "
            "section depth, and section width trials found no executor-backed one-click arrangement that resolves the "
            "crack limit while preserving bending, shear, deflection, spacing, ductility, cover, and detailing checks."
        )
        attempted_updates = active_failure_route_attempt_updates("bending")
        failed_name = "crack control limit"
        category = "crack_would_fail"
    else:
        fam = "deflection" if fam == "serviceability" else fam
        default_reason = (
            "Deflection repair is blocked by geometry/serviceability limits. Exhaustive section depth, section width, "
            "reinforcement, and sustained-load trials found no executor-backed one-click arrangement that resolves the "
            "deflection limit while preserving bending, shear, crack, spacing, ductility, cover, and detailing checks."
        )
        attempted_updates = {
            "D": "increase section depth trial",
            "b": "increase section width trial",
            "sustained_load": "reduce sustained load advisory trial",
        }
        failed_name = "deflection limit"
        category = "deflection_would_fail"
    specific_reason = str(reason or "").strip() or default_reason
    if evidence_primary_family == fam and str(ev.get("active_under_capacity_blocker_reason") or "").strip():
        specific_reason = str(ev.get("active_under_capacity_blocker_reason") or "").strip()
    elif shared_active_failure_blocker:
        primary_reason = str(ev.get("active_under_capacity_blocker_reason") or "").strip()
        specific_reason = (
            f"{fam.capitalize()} remains unresolved because the exhaustive active-failure one-click repair "
            "search found no executor-backed arrangement that passes all required checks while "
            f"{', '.join(sorted(active_failure_set))} fail."
        )
        if primary_reason:
            specific_reason = f"{specific_reason} The recorded blocking proof says: {primary_reason}"
        category = "combined_active_failure_would_fail"
        failed_name = f"{fam} capacity unresolved in combined active-failure repair search"
    attempted = dict(ev.get("attempted_updates") or {}) if evidence_primary_family == fam else {}
    if not attempted:
        attempted = dict(attempted_updates)
    attempted = active_failure_route_attempt_updates(fam, attempted)
    failures = list(dict.fromkeys(str(x or "").strip().lower() for x in list(active_failure_set or {fam}) if str(x or "").strip()))
    route_inventory = active_failure_route_inventory(failures)
    return {
        "family": fam,
        "source": "combined_active_failure_practical_ladder_exhausted" if shared_active_failure_blocker else f"{fam}_active_failure_practical_ladder_exhausted",
        "exact_blocker": True,
        "current_util": current_util,
        "threshold": float(final_accepted_min_family_util),
        "target_low": float(efficiency_target_util_min),
        "target_high": float(efficiency_target_util_max),
        "reason": specific_reason,
        "active_failures": list(failures or [fam]),
        "search_scope": active_search_scope,
        "active_fail_repair_search_scope": active_search_scope,
        "repair_search_ran": True,
        "repair_search_exhaustive": True,
        "geometry_strengthening_searched": True,
        "reo_strengthening_searched": True,
        "longitudinal_reinforcement_strengthening_searched": True,
        "shear_strengthening_searched": bool("shear" in failures or fam == "shear"),
        "combined_strengthening_searched": bool(len(failures or []) > 1),
        "local_cleanup_search_ran": False,
        "local_cleanup_search_exhaustive": False,
        "cleanup_search_ran": False,
        "cleanup_search_exhaustive": False,
        "candidate_search_exhaustive": True,
        "safe_repair_candidate_count": safe_repair_count,
        "executable_repair_candidate_count": executable_repair_count,
        "safe_candidate_count": safe_repair_count,
        "executable_candidate_count": executable_repair_count,
        "target_band_candidate_count": int(ev.get("target_band_candidate_count") or 0),
        "executable_target_band_candidate_count": int(ev.get("executable_target_band_candidate_count") or 0),
        "safe_cleanup_count": 0,
        "executable_cleanup_count": 0,
        "attempted_candidate_count": int(ev.get("total_candidates_considered") or ev.get("preview_count") or max(1, len(attempted))),
        "attempted_candidate_id": f"{fam}_active_failure_practical_ladder_exhausted",
        "failed_candidate_id": rejected_candidate_id or f"{fam}_active_failure_practical_ladder_exhausted",
        "best_rejected_candidate_id": rejected_candidate_id or f"{fam}_active_failure_practical_ladder_exhausted",
        "attempted_updates": dict(attempted),
        "route_inventory": dict(route_inventory.get(fam) or {}),
        "active_repair_route_inventory": dict(route_inventory),
        "active_fail_repair_candidate_rows": [dict(row) for row in active_candidate_rows[:80]],
        "rejected_repair_reasons": list(dict.fromkeys(rejected_repair_reasons))[:40],
        "failed_check_name": failed_name,
        "failed_check_status": "FAIL",
        "failed_check_util": current_util if current_util is not None else ev.get("failed_check_util") or 1.0,
        "failed_check_demand": f"{fam} demand remains above checked capacity or serviceability limit",
        "failed_check_capacity_or_limit": f"{fam} capacity or serviceability limit",
        "outside_target_band_allowed": False,
        "outside_target_band_allowed_reason": specific_reason,
        "outside_target_band_allowed_category": category,
        "one_click_target_reaching_candidate_exists": False,
    }


def active_failure_exact_blockers_for_families(
    families: list[str] | set[str] | tuple[str, ...],
    *,
    overview: dict | None = None,
    evidence: dict | None = None,
    primary_family: str | None = None,
    primary_reason: str | None = None,
    final_accepted_min_family_util: float,
    efficiency_target_util_min: float,
    efficiency_target_util_max: float,
) -> dict[str, dict]:
    active = [
        "deflection" if str(family or "").strip().lower() == "serviceability" else str(family or "").strip().lower()
        for family in list(families or [])
        if str(family or "").strip().lower() in {"bending", "shear", "crack", "deflection", "serviceability"}
    ]
    primary = str(primary_family or "").strip().lower()
    if primary == "serviceability":
        primary = "deflection"
    if primary and primary in {"bending", "shear", "crack", "deflection"} and primary not in active:
        active.append(primary)
    active = list(dict.fromkeys(active))
    return {
        family: active_failure_blocker_payload(
            family,
            overview=overview,
            active_failures=active,
            evidence=evidence,
            reason=primary_reason if family == primary else None,
            final_accepted_min_family_util=float(final_accepted_min_family_util),
            efficiency_target_util_min=float(efficiency_target_util_min),
            efficiency_target_util_max=float(efficiency_target_util_max),
        )
        for family in active
    }


def active_failure_blocker_visible_reason_text(
    exact_blockers: dict | None,
    active_failures: list[str] | set[str] | tuple[str, ...],
) -> str:
    blockers = {
        str(family or "").strip().lower(): dict(blocker)
        for family, blocker in dict(exact_blockers or {}).items()
        if str(family or "").strip() and isinstance(blocker, dict)
    }
    ordered = [
        str(family or "").strip().lower()
        for family in list(active_failures or [])
        if str(family or "").strip().lower() in {"bending", "shear"}
    ]
    ordered = list(dict.fromkeys(ordered))
    if not ordered:
        ordered = [family for family in ("bending", "shear") if family in blockers]
    labels = {"bending": "Bending", "shear": "Shear"}
    lines: list[str] = []
    for family in ordered:
        label = labels.get(family, family.capitalize())
        blocker = dict(blockers.get(family) or {})
        reason = str(
            blocker.get("reason")
            or blocker.get("outside_target_band_allowed_reason")
            or blocker.get("blocking_reason")
            or ""
        ).strip()
        if not reason:
            lines.append(
                f"{label} repair remains unresolved: no specific blocker proof was published."
            )
            continue
        details: list[str] = []
        failed_check = str(blocker.get("failed_check_name") or "").strip()
        failed_status = str(blocker.get("failed_check_status") or "").strip()
        failed_util = blocker.get("failed_check_util")
        failed_limit = blocker.get("failed_check_capacity_or_limit")
        if failed_check:
            check_detail = f"failed check/rule: {failed_check}"
            if failed_status:
                check_detail += f" ({failed_status})"
            details.append(check_detail)
        if failed_util not in (None, ""):
            try:
                details.append(f"utilisation {float(failed_util):.2f}")
            except (TypeError, ValueError):
                details.append(f"utilisation {failed_util}")
        if failed_limit not in (None, ""):
            details.append(f"limit/capacity {failed_limit}")
        if bool(blocker.get("repair_search_ran")) and bool(blocker.get("repair_search_exhaustive")):
            details.append("exhaustive active repair search ran")
        route_summary = repair_attempt_route_summary(
            family,
            dict(blocker.get("attempted_updates") or {}),
        )
        checked_limit = ""
        if (
            bool(blocker.get("repair_search_ran"))
            and bool(blocker.get("repair_search_exhaustive"))
            and (
                blocker.get("safe_repair_candidate_count") in (0, "0")
                or blocker.get("executable_repair_candidate_count") in (0, "0")
            )
        ):
            checked_limit = (
                "Maximum depth reached in the checked one-click repair move set; "
                "maximum width reached in the checked one-click repair move set. "
            )
            if route_summary:
                checked_limit += f"Checked repair routes: {route_summary}. "
        suffix = f" Evidence: {'; '.join(details)}." if details else ""
        lines.append(f"{label} repair blocked: {checked_limit}{reason}{suffix}")
    return "\n".join(lines)


def candidate_failure_coverage_summary_from_overviews(
    current_overview: dict | None,
    candidate_overview: dict | None,
) -> dict:
    """Summarise which currently failing checks a candidate resolves."""
    current = dict(current_overview or {})
    candidate = dict(candidate_overview or {})
    current_fail = sorted(
        [
            key
            for key, val in (current.get("statuses") or {}).items()
            if str(val or "").upper() == "FAIL"
        ],
    )
    candidate_fail = sorted(
        [
            key
            for key, val in (candidate.get("statuses") or {}).items()
            if str(val or "").upper() == "FAIL"
        ],
    )

    covered = sorted([key for key in current_fail if key not in candidate_fail])
    remaining = sorted([key for key in current_fail if key in candidate_fail])

    return {
        "current_fail_keys": list(current_fail),
        "candidate_fail_keys": list(candidate_fail),
        "covered_fail_keys": list(covered),
        "remaining_fail_keys": list(remaining),
        "covers_all_current_failures": len(current_fail) > 0 and len(remaining) == 0,
    }


def requires_full_coverage_for_primary_one_click(overview: dict | None) -> tuple[bool, list[str]]:
    statuses = dict((overview or {}).get("statuses") or {})
    fail_keys = sorted(
        [
            key
            for key, val in statuses.items()
            if str(val or "").upper() == "FAIL"
        ],
    )
    return (len(fail_keys) >= 2, fail_keys)


def candidate_preview_statuses_have_explicit_fail(
    preview_statuses: dict | None,
    *,
    fail_status_value: Any = "FAIL",
) -> bool:
    """True when candidate preview overview statuses map contains any explicit FAIL value."""
    if not isinstance(preview_statuses, dict):
        return False
    for value in preview_statuses.values():
        if value == fail_status_value:
            return True
        if str(value or "").strip().upper() == "FAIL":
            return True
    return False


def candidate_is_valid_primary_one_click(
    candidate: dict | None,
    overview: dict,
    *,
    fail_status_value: Any = "FAIL",
) -> tuple[bool, dict]:
    meta = {
        "valid": False,
        "reason": "missing_candidate",
        "fail_keys": [],
        "covers_all_current_failures": False,
        "covered_fail_keys": [],
        "remaining_fail_keys": [],
        "requires_full_coverage": False,
    }
    if not isinstance(candidate, dict):
        return False, meta

    requires_full_coverage, fail_keys = requires_full_coverage_for_primary_one_click(overview)
    meta["fail_keys"] = list(fail_keys)
    meta["requires_full_coverage"] = bool(requires_full_coverage)

    payload = dict(candidate.get("action_payload") or {})
    coverage = dict(candidate.get("failure_coverage") or payload.get("failure_coverage") or {})
    covers_all = bool(
        candidate.get("covers_all_current_failures")
        or payload.get("covers_all_current_failures")
        or coverage.get("covers_all_current_failures")
    )
    covered = list(
        candidate.get("covered_fail_keys")
        or payload.get("covered_fail_keys")
        or coverage.get("covered_fail_keys")
        or []
    )
    remaining = list(
        candidate.get("remaining_fail_keys")
        or payload.get("remaining_fail_keys")
        or coverage.get("remaining_fail_keys")
        or []
    )

    if (not covered and not remaining) and fail_keys:
        candidate_overview = dict(candidate.get("overview") or {})
        candidate_fail_keys = sorted(
            [
                key
                for key, val in (candidate_overview.get("statuses") or {}).items()
                if str(val or "").upper() == "FAIL"
            ],
        )
        covered = sorted([key for key in fail_keys if key not in candidate_fail_keys])
        remaining = sorted([key for key in fail_keys if key in candidate_fail_keys])
        covers_all = len(fail_keys) > 0 and len(remaining) == 0

    meta["covers_all_current_failures"] = bool(covers_all)
    meta["covered_fail_keys"] = list(covered)
    meta["remaining_fail_keys"] = list(remaining)

    preview_overview = dict(candidate.get("overview") or {})
    if not preview_overview.get("statuses") and isinstance(candidate.get("resolved_candidate"), dict):
        preview_overview = dict((candidate.get("resolved_candidate") or {}).get("overview") or {})
    preview_statuses = dict(preview_overview.get("statuses") or {})
    preview_resolves_fail_keys_without_fail = bool(
        fail_keys
        and all(key in preview_statuses for key in fail_keys)
        and all(
            str(preview_statuses.get(key) or "").strip().upper() != "FAIL"
            and preview_statuses.get(key) != fail_status_value
            for key in fail_keys
        )
    )
    if candidate_preview_statuses_have_explicit_fail(
        preview_statuses,
        fail_status_value=fail_status_value,
    ):
        meta["valid"] = False
        meta["reason"] = "candidate_preview_has_fail_status"
        return False, meta

    preview_has_fail_key = bool(preview_overview.get("any_fail"))
    if (
        not preview_has_fail_key
        and fail_keys
        and not requires_full_coverage
        and not all(key in preview_statuses for key in fail_keys)
    ):
        preview_has_fail_key = True
    if (
        not preview_has_fail_key
        and fail_keys
        and not requires_full_coverage
        and not bool(candidate.get("is_compliant"))
        and not preview_resolves_fail_keys_without_fail
    ):
        preview_has_fail_key = True
    if preview_has_fail_key:
        meta["valid"] = False
        meta["reason"] = "candidate_preview_has_fail_status"
        return False, meta

    if not requires_full_coverage:
        meta["valid"] = True
        meta["reason"] = "single_fail_or_no_fail"
        return True, meta

    if covers_all and not remaining:
        meta["valid"] = True
        meta["reason"] = "full_failure_coverage"
        return True, meta

    meta["valid"] = False
    meta["reason"] = "partial_failure_coverage"
    return False, meta


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _dict_from(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _normalise_repair_decision_status(
    status: str | None,
    *,
    candidate: dict | None,
    proof: dict | None,
) -> str:
    status_l = str(status or "").strip().lower()
    if status_l:
        return status_l
    proof_map = _dict_from(proof)
    if isinstance(candidate, dict) and candidate:
        return "action"
    if bool(proof_map.get("exact_blocker") or proof_map.get("active_under_capacity_blocker")):
        return "blocked"
    return "missing_candidate"


def repair_decision_from_selected_candidate(
    selected_candidate: dict | None,
    *,
    status: str | None = None,
    reason: str | None = None,
    proof: dict | None = None,
    cta_metadata: dict | None = None,
    validation_meta: dict | None = None,
) -> dict:
    """Wrap an already-selected repair candidate without selecting or mutating it."""
    candidate_obj = selected_candidate if isinstance(selected_candidate, dict) else None
    candidate = _dict_from(candidate_obj)
    payload = _dict_from(candidate.get("action_payload"))
    resolved = _dict_from(candidate.get("resolved_candidate"))
    proof_map = _dict_from(
        proof
        or candidate.get("candidate_search_evidence")
        or payload.get("candidate_search_evidence")
        or resolved.get("candidate_search_evidence")
    )
    cta = _dict_from(cta_metadata)
    validation = _dict_from(validation_meta)
    updates = _dict_from(
        candidate.get("updates")
        or candidate.get("proposed_updates")
        or payload.get("resolved_candidate_updates")
        or payload.get("updates")
        or resolved.get("updates")
        or proof_map.get("selected_candidate_updates")
    )
    candidate_id = _first_nonempty(
        candidate.get("candidate_id"),
        candidate.get("source_candidate_id"),
        payload.get("candidate_id"),
        payload.get("source_candidate_id"),
        resolved.get("candidate_id"),
        resolved.get("source_candidate_id"),
        proof_map.get("selected_candidate_id"),
    )
    title = _first_nonempty(
        candidate.get("title"),
        candidate.get("title_main"),
        candidate.get("label"),
        candidate.get("canonical_winner_label"),
        payload.get("resolved_candidate_label"),
        proof_map.get("selected_candidate_title"),
    )
    action_type = _first_nonempty(
        candidate.get("action_type"),
        payload.get("resolved_candidate_action_type"),
        payload.get("action_type"),
        resolved.get("action_type"),
        cta.get("action_type"),
    )
    util = _first_nonempty(
        candidate.get("candidate_post_util"),
        candidate.get("worst_util"),
        payload.get("resolved_candidate_post_util"),
        resolved.get("candidate_post_util"),
        resolved.get("worst_util"),
        proof_map.get("selected_candidate_util"),
    )
    family = _first_nonempty(
        candidate.get("family"),
        candidate.get("affected_family"),
        candidate.get("recommendation_family_tag"),
        payload.get("resolved_candidate_family_tag"),
        resolved.get("family"),
        proof_map.get("family"),
    )
    normalised_status = _normalise_repair_decision_status(
        status,
        candidate=candidate_obj,
        proof=proof_map,
    )
    normalised_reason = str(
        _first_nonempty(
            reason,
            validation.get("reason"),
            proof_map.get("outside_target_band_allowed_reason"),
            proof_map.get("active_under_capacity_blocker_reason"),
            proof_map.get("reason"),
            normalised_status,
        )
        or ""
    )
    cta_enabled = cta.get("enabled")
    if cta_enabled is None:
        cta_enabled = bool(candidate_obj and updates)
    cta_actionable = cta.get("actionable")
    if cta_actionable is None:
        cta_actionable = bool(cta_enabled)
    cta_out = {
        **cta,
        "enabled": bool(cta_enabled),
        "actionable": bool(cta_actionable),
        "action_type": action_type,
        "candidate_id": candidate_id,
        "updates": dict(updates),
    }
    return {
        "decision_status": normalised_status,
        "status": normalised_status,
        "reason": normalised_reason,
        "selected_candidate": candidate_obj,
        "candidate": dict(candidate),
        "candidate_id": candidate_id,
        "candidate_title": title,
        "candidate_family": family,
        "action_type": action_type,
        "action_payload": dict(payload),
        "updates": dict(updates),
        "proof": dict(proof_map),
        "cta": cta_out,
        "validation": dict(validation),
        "selected_candidate_id": candidate_id,
        "selected_candidate_title": title,
        "selected_candidate_updates": dict(updates),
        "selected_candidate_util": util,
    }


def select_repair_decision(
    *,
    selected_candidate: dict | None,
    evidence: dict | None = None,
    status: str | None = None,
    reason: str | None = None,
    cta_metadata: dict | None = None,
    validation_meta: dict | None = None,
    callbacks: dict | None = None,
) -> dict:
    """Orchestrate over an already-selected repair candidate without re-selecting it."""
    _ = callbacks
    return repair_decision_from_selected_candidate(
        selected_candidate,
        status=status,
        reason=reason,
        proof=evidence,
        cta_metadata=cta_metadata,
        validation_meta=validation_meta,
    )


def selected_candidate_from_repair_decision(decision: dict | None) -> dict | None:
    """Return the original selected candidate object from a repair decision wrapper."""
    if not isinstance(decision, dict):
        return None
    selected = decision.get("selected_candidate")
    if isinstance(selected, dict):
        return selected
    candidate = decision.get("candidate")
    return dict(candidate) if isinstance(candidate, dict) else None


__all__ = [
    "active_failure_blocker_payload",
    "active_failure_blocker_visible_reason_text",
    "active_failure_exact_blockers_for_families",
    "active_failure_route_attempt_updates",
    "active_failure_route_inventory",
    "build_near_current_bottom_repair_specs",
    "build_near_current_geometry_repair_specs",
    "build_near_current_shear_repair_specs",
    "candidate_failure_coverage_summary_from_overviews",
    "candidate_is_valid_primary_one_click",
    "candidate_preview_statuses_have_explicit_fail",
    "repair_attempt_route_summary",
    "repair_decision_from_selected_candidate",
    "requires_full_coverage_for_primary_one_click",
    "select_repair_decision",
    "selected_candidate_from_repair_decision",
]
