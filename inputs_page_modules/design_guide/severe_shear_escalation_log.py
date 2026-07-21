"""Severe-shear escalation debug logging coordination."""

from __future__ import annotations

from typing import Any


_SEVERE_SHEAR_ESCALATION_LOG_DEPENDENCIES: tuple[str, ...] = (
    "st",
    "_agent_debug_log",
    "_design_optimisation_goal",
    "_geometry_lock_enabled",
    "_secondary_action_reserves",
)


def bind_severe_shear_escalation_log_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SEVERE_SHEAR_ESCALATION_LOG_DEPENDENCIES
            if name in namespace
        }
    )


def _log_severe_shear_escalation(
    *,
    source: str,
    seed_candidate: dict,
    severity_band: str,
    candidates: list[dict],
    selected: dict | None,
    family_audit: dict[str, list[dict]] | None = None,
) -> None:
    if not bool(st.session_state.get("_dev_mode")):
        return
    audit = dict(family_audit or {})
    families = [
        "spacing tighter",
        "more legs",
        "larger link dia",
        "width increase",
        "depth increase",
        "combined geometry + stronger shear",
        "combined geometry + lighter bottom reo",
        "combined shear + lighter bottom reo",
    ]

    def _entry_order(item: dict) -> tuple:
        return (
            0 if bool(item.get("survived_filters")) else 1,
            0 if bool(item.get("selected")) else 1,
            float(item.get("score_total") if item.get("score_total") is not None else float("inf")),
            float(item.get("shear_util") if item.get("shear_util") is not None else float("inf")),
        )

    def _selection_reason_chain(selected_entry: dict | None, contender_entry: dict | None) -> str:
        if not selected_entry:
            return "no candidate selected"
        if contender_entry is None:
            return "selected candidate was the only ranked survivor"
        if selected_entry.get("candidate_key") == contender_entry.get("candidate_key"):
            return "selected as best candidate in its family and overall"
        reasons: list[str] = []
        selected_score = float(selected_entry.get("score_total") if selected_entry.get("score_total") is not None else float("inf"))
        contender_score = float(contender_entry.get("score_total") if contender_entry.get("score_total") is not None else float("inf"))
        reasons.append(f"score_total {selected_score:.2f} vs {contender_score:.2f}")
        selected_primary = float((((selected_entry.get("score_components") or {}).get("primary_shear_recovery_contribution")) or float("inf")))
        contender_primary = float((((contender_entry.get("score_components") or {}).get("primary_shear_recovery_contribution")) or float("inf")))
        if selected_primary != contender_primary:
            reasons.append(f"primary shear recovery {selected_primary:.2f} vs {contender_primary:.2f}")
        selected_secondary = float((((selected_entry.get("score_components") or {}).get("secondary_bending_efficiency_contribution")) or float("inf")))
        contender_secondary = float((((contender_entry.get("score_components") or {}).get("secondary_bending_efficiency_contribution")) or float("inf")))
        if selected_secondary != contender_secondary:
            reasons.append(f"secondary bending efficiency {selected_secondary:.2f} vs {contender_secondary:.2f}")
        selected_geometry = float((((selected_entry.get("score_components") or {}).get("geometry_penalty")) or 0.0))
        contender_geometry = float((((contender_entry.get("score_components") or {}).get("geometry_penalty")) or 0.0))
        if selected_geometry != contender_geometry:
            reasons.append(f"geometry penalty {selected_geometry:.2f} vs {contender_geometry:.2f}")
        selected_goal = float((((selected_entry.get("score_components") or {}).get("goal_bias_adjustment")) or 0.0))
        contender_goal = float((((contender_entry.get("score_components") or {}).get("goal_bias_adjustment")) or 0.0))
        if selected_goal != contender_goal:
            reasons.append(f"goal bias adjustment {selected_goal:.2f} vs {contender_goal:.2f}")
        selected_material = float((((selected_entry.get("score_components") or {}).get("material_complexity_penalty")) or 0.0))
        contender_material = float((((contender_entry.get("score_components") or {}).get("material_complexity_penalty")) or 0.0))
        if selected_material != contender_material:
            reasons.append(f"material/complexity penalty {selected_material:.2f} vs {contender_material:.2f}")
        return "; ".join(reasons)

    candidates_per_family = {}
    survivors_per_family = {}
    best_per_family = {}
    top_3_per_family = {}
    family_key_map = {
        "spacing tighter": "best_spacing_candidate",
        "more legs": "best_more_legs_candidate",
        "larger link dia": "best_larger_dia_candidate",
        "width increase": "best_width_candidate",
        "depth increase": "best_depth_candidate",
        "combined geometry + stronger shear": "best_combined_candidate",
        "combined geometry + lighter bottom reo": "best_combined_geometry_lighter_bottom_candidate",
        "combined shear + lighter bottom reo": "best_combined_shear_lighter_bottom_candidate",
    }
    for family in families:
        entries = list(audit.get(family, []))
        if not entries:
            continue
        ordered = sorted(entries, key=_entry_order)
        candidates_per_family[family] = len(entries)
        survivors_per_family[family] = sum(1 for entry in entries if bool(entry.get("survived_filters")))
        top_3_per_family[family] = {
            "family": family,
            "generated": len(entries),
            "survived": survivors_per_family[family],
            "top_candidates": ordered[:3],
        }
        best_per_family[family] = ordered[0]
    global_selected = next(
        (
            entry
            for family in families
            for entry in audit.get(family, [])
            if bool(entry.get("selected"))
        ),
        None,
    )
    family_comparison = {}
    for family, entry in best_per_family.items():
        family_comparison[family_key_map.get(family, f"best_{family}")] = {
            "label": entry.get("label"),
            "score": entry.get("score_total"),
            "shear_util": entry.get("shear_util"),
            "bending_util": entry.get("bending_util"),
            "b": entry.get("b"),
            "D": entry.get("D"),
            "lig_d": entry.get("lig_d"),
            "lig_legs": entry.get("lig_legs"),
            "s_lig": entry.get("s_lig"),
            "bottom_reo_label": entry.get("bottom_reo_label"),
            "reason": _selection_reason_chain(global_selected, entry),
        }
    losing_entries = [
        entry for family, entry in best_per_family.items()
        if not global_selected or entry.get("candidate_key") != global_selected.get("candidate_key")
    ]
    best_losing_entry = min(losing_entries, key=_entry_order) if losing_entries else None
    final_selected_reason = _selection_reason_chain(global_selected, best_losing_entry)
    _agent_debug_log(
        "Severe shear escalation candidates",
        {
            "source": source,
            "optimisation_goal": _design_optimisation_goal(seed_candidate.get("state") or {}),
            "geometry_lock": _geometry_lock_enabled(seed_candidate.get("state") or {}),
            "primary_action": "shear",
            "secondary_actions_with_reserve": _secondary_action_reserves(seed_candidate),
            "shear_utilisation": ((seed_candidate.get("overview") or {}).get("utils") or {}).get("shear"),
            "severity_band": severity_band,
            "total_candidates_generated": int(sum(candidates_per_family.values())),
            "candidates_generated_by_family": candidates_per_family,
            "total_candidates_survived": int(sum(survivors_per_family.values())),
            "candidates_survived_by_family": survivors_per_family,
            "combined_candidates_generated": bool(
                candidates_per_family.get("combined geometry + stronger shear")
                or candidates_per_family.get("combined geometry + lighter bottom reo")
                or candidates_per_family.get("combined shear + lighter bottom reo")
            ),
            "best_overall_candidate": global_selected,
            "best_candidate_per_family": best_per_family,
            "top_3_per_family": top_3_per_family,
            "family_comparison": {
                **family_comparison,
                "final_selected_candidate": None if global_selected is None else {
                    "label": global_selected.get("label"),
                    "score": global_selected.get("score_total"),
                    "shear_util": global_selected.get("shear_util"),
                    "bending_util": global_selected.get("bending_util"),
                    "b": global_selected.get("b"),
                    "D": global_selected.get("D"),
                    "lig_d": global_selected.get("lig_d"),
                    "lig_legs": global_selected.get("lig_legs"),
                    "s_lig": global_selected.get("s_lig"),
                    "bottom_reo_label": global_selected.get("bottom_reo_label"),
                    "reason": final_selected_reason,
                },
            },
            "final_selected_reason": final_selected_reason,
            "end_of_run_summary": {
                "optimisation_goal": _design_optimisation_goal(seed_candidate.get("state") or {}),
                "geometry_lock": _geometry_lock_enabled(seed_candidate.get("state") or {}),
                "primary_action": "shear",
                "secondary_actions_with_reserve": _secondary_action_reserves(seed_candidate),
                "severity_band": severity_band,
                "total_candidates_generated": int(sum(candidates_per_family.values())),
                "candidates_generated_by_family": candidates_per_family,
                "total_candidates_survived": int(sum(survivors_per_family.values())),
                "final_selected_family": None if global_selected is None else global_selected.get("family"),
                "final_selected_label": None if global_selected is None else global_selected.get("label"),
                "final_selected_score": None if global_selected is None else global_selected.get("score_total"),
                "final_selected_reason": final_selected_reason,
                "best_losing_family": None if best_losing_entry is None else best_losing_entry.get("family"),
                "best_losing_candidate": None if best_losing_entry is None else best_losing_entry.get("label"),
                "best_losing_reason": None if best_losing_entry is None else _selection_reason_chain(global_selected, best_losing_entry),
            },
        },
        location="inputs_page.py:severe_shear_escalation",
        hypothesis_id="H_SHEAR_ESCALATION",
    )
