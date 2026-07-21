"""Shear-governing candidate generation coordination for the Inputs Design Guide."""

from __future__ import annotations

from typing import Any


_SHEAR_GOVERNING_CANDIDATE_DEPENDENCIES: tuple[str, ...] = (
    "_generate_escalated_shear_states",
    "_guidance_state_snapshot",
    "_one_click_diff_accumulated_updates",
    "_shear_severity_band",
)


def bind_shear_governing_candidate_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_GOVERNING_CANDIDATE_DEPENDENCIES
            if name in namespace
        }
    )


def _generate_shear_governing_candidates(
    working_state: dict,
    cur_eval: dict,
    mode_config: dict,
) -> tuple[list[dict], dict]:
    """Shear-governing one-click orchestration with staged severity escalation."""
    base_state = _guidance_state_snapshot(dict(working_state or {}))
    overview = dict((cur_eval or {}).get("overview") or {})
    cur_shear_util = ((overview.get("utils") or {}).get("shear"))
    try:
        cur_shear_util = float(cur_shear_util) if cur_shear_util is not None else None
    except Exception:
        cur_shear_util = None
    severity_band = _shear_severity_band(cur_shear_util)
    generated = list(_generate_escalated_shear_states(base_state, severity_band=severity_band) or [])

    family_order = [
        "spacing_reduction",
        "more_legs",
        "larger_dia",
        "material_fc",
        "combined_link_changes",
        "depth_increase",
        "width_increase",
        "combined_geometry_links",
        "cleanup_non_governing",
    ]
    buckets: dict[str, list[dict]] = {k: [] for k in family_order}
    seen_updates: set[tuple] = set()
    for cand_type, cand_state in generated:
        updates = _one_click_diff_accumulated_updates(base_state, cand_state)
        if not updates:
            continue
        uk = tuple(sorted((str(k), str(v)) for k, v in updates.items()))
        if uk in seen_updates:
            continue
        seen_updates.add(uk)
        ctype = str(cand_type or "").strip().lower()
        if ctype == "spacing":
            family = "spacing_reduction"
        elif ctype == "more legs":
            family = "more_legs"
        elif ctype == "larger dia":
            family = "larger_dia"
        elif ctype == "material_fc":
            family = "material_fc"
        elif ctype == "depth increase":
            family = "depth_increase"
        elif ctype == "width increase":
            family = "width_increase"
        elif ctype == "combined":
            has_geom = any(k in updates for k in ("D", "b", "bw"))
            has_links = any(k in updates for k in ("lig_d", "lig_legs", "s_lig"))
            family = "combined_geometry_links" if has_geom and has_links else "combined_link_changes"
        else:
            family = "combined_link_changes"
        buckets[family].append(
            {
                "item": {"action_payload": {"guidance_change_summary_compact": f"Shear-governing {family} candidate"}},
                "action_type": "tightening_domain_candidate",
                "title": f"Shear governing: {family}",
                "raw_updates": dict(updates),
                "_tightening_family": family,
                "_shear_candidate_type": ctype,
            },
        )

    if severity_band == "mild":
        active_order = [
            "spacing_reduction",
            "more_legs",
            "larger_dia",
            "material_fc",
            "combined_link_changes",
            "depth_increase",
            "width_increase",
            "combined_geometry_links",
            "cleanup_non_governing",
        ]
    elif severity_band == "moderate":
        active_order = [
            "spacing_reduction",
            "more_legs",
            "larger_dia",
            "material_fc",
            "combined_link_changes",
            "depth_increase",
            "width_increase",
            "combined_geometry_links",
            "cleanup_non_governing",
        ]
    else:
        active_order = [
            "combined_link_changes",
            "more_legs",
            "larger_dia",
            "spacing_reduction",
            "material_fc",
            "combined_geometry_links",
            "depth_increase",
            "width_increase",
            "cleanup_non_governing",
        ]

    out: list[dict] = []
    family_depth_reached = "none"
    for family in active_order:
        family_items = list(buckets.get(family) or [])
        if severity_band == "mild":
            lim = 6 if family == "spacing_reduction" else 4
        elif severity_band == "moderate":
            lim = 8 if family in ("spacing_reduction", "more_legs", "larger_dia") else 5
        else:
            lim = 10 if family in ("combined_link_changes", "combined_geometry_links") else 6
        for rc in family_items[:lim]:
            out.append(rc)
            family_depth_reached = family

    meta = {
        "governing_domain": "shear",
        "shear_governing_mode_active": True,
        "shear_severity_band": severity_band,
        "shear_candidate_family_order": list(active_order),
        "candidate_families_considered": [f for f in active_order if buckets.get(f)],
        "candidate_families_pruned": ["bending_first_bottom_reduction", "non_governing_cleanup_early"],
        "candidate_family_depth_reached": family_depth_reached,
        "spacing_candidates_considered": len(buckets["spacing_reduction"]),
        "leg_candidates_considered": len(buckets["more_legs"]),
        "dia_candidates_considered": len(buckets["larger_dia"]),
        "geometry_candidates_considered_for_shear": len(buckets["depth_increase"]) + len(buckets["width_increase"]),
        "combined_candidates_considered_for_shear": len(buckets["combined_link_changes"])
        + len(buckets["combined_geometry_links"]),
    }
    return out, meta
