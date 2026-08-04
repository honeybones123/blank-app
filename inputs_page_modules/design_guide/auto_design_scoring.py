"""Auto-design candidate scoring coordination for the Inputs page Design Guide."""

from __future__ import annotations

from typing import Any, Callable
from inputs_application.design_guide_runtime_contracts import AutoDesignScoringRuntime


def _scoring_aliases(runtime: AutoDesignScoringRuntime) -> dict[str, Callable]:
    return {
        "_agent_debug_log": runtime.agent_debug_log,
        "_candidate_bending_demand_util": runtime.candidate_bending_demand_util,
        "_candidate_ductility_governs": runtime.candidate_ductility_governs,
        "_candidate_ductility_reason": runtime.candidate_ductility_reason,
        "_candidate_ductility_util": runtime.candidate_ductility_util,
        "_candidate_in_target_band": runtime.candidate_in_target_band,
        "_candidate_is_practical": runtime.candidate_is_practical,
        "_candidate_objective_util": runtime.candidate_objective_util,
        "_candidate_util_distance": runtime.candidate_util_distance,
        "_candidate_violation_score": runtime.candidate_violation_score,
        "_ductility_fix_tier": runtime.ductility_fix_tier,
        "_ductility_tier_label": runtime.ductility_tier_label,
        "_mode_target_midpoint": runtime.mode_target_midpoint,
        "_failed_check_labels": runtime.failed_check_labels,
        "_reject_heavier_steel_lower_demand_util": runtime.reject_heavier_steel_lower_demand_util,
        "_shallower_beam_candidate_tier": runtime.shallower_beam_candidate_tier,
        "_shallower_beam_metrics": runtime.shallower_beam_metrics,
        "_shear_candidate_practicality_metrics": runtime.shear_candidate_practicality_metrics,
        "compute_reo_complexity": runtime.compute_reo_complexity,
        "utilisation_gap": runtime.utilisation_gap,
    }


def _score_auto_design_candidate_components(
    candidate: dict,
    mode_config: dict,
    seed_candidate: dict,
    *,
    runtime: AutoDesignScoringRuntime,
) -> dict:
    aliases = _scoring_aliases(runtime)
    _shear_candidate_practicality_metrics = aliases["_shear_candidate_practicality_metrics"]
    _candidate_objective_util = aliases["_candidate_objective_util"]
    _mode_target_midpoint = aliases["_mode_target_midpoint"]
    _shallower_beam_metrics = aliases["_shallower_beam_metrics"]
    _candidate_ductility_governs = aliases["_candidate_ductility_governs"]
    _ductility_fix_tier = aliases["_ductility_fix_tier"]
    _ductility_tier_label = aliases["_ductility_tier_label"]
    _candidate_ductility_reason = aliases["_candidate_ductility_reason"]
    _candidate_violation_score = aliases["_candidate_violation_score"]
    _candidate_ductility_util = aliases["_candidate_ductility_util"]
    shear_practicality = _shear_candidate_practicality_metrics(
        candidate,
        dict(seed_candidate.get("state") or {}),
    )
    candidate.update(shear_practicality)
    util = _candidate_objective_util(candidate)
    target_min = float(mode_config["target_util_min"])
    target_max = float(mode_config["target_util_max"])
    target_mid = _mode_target_midpoint(mode_config)
    if util < target_min:
        util_penalty = (target_min - util) * 80.0
    elif util > target_max:
        util_penalty = (util - target_max) * 120.0
    else:
        util_penalty = abs(util - target_mid) * 24.0

    depth = float(candidate.get("depth", 0.0) or 0.0)
    width = float(candidate.get("width", 0.0) or 0.0)
    seed_depth = float(seed_candidate.get("depth", depth) or depth)
    depth_growth = max(depth - seed_depth, 0.0)
    depth_penalty = (depth / 50.0) * float(mode_config["geometry_penalty"])
    depth_penalty += (depth_growth / 25.0) * float(mode_config.get("depth_growth_multiplier", 1.0))
    width_penalty = (width / 50.0) * float(mode_config.get("width_penalty", 0.4))

    steel_area = float(candidate.get("Ast_bot", 0.0) or 0.0) + float(candidate.get("Ast_top", 0.0) or 0.0)
    steel_penalty = (steel_area / 100.0) * float(mode_config["steel_penalty"])
    congestion_penalty = float(candidate.get("reo_congestion_index", 0.0) or 0.0) * float(mode_config["reo_congestion_penalty"])
    row_penalty = max(int(candidate.get("row_count", 1) or 1) - 1, 0) * 2.0
    if mode_config.get("prefer_lower_reo_congestion"):
        row_penalty *= 1.75

    shear_density_penalty = 0.0
    if mode_config["label"] == "Less shear reinforcement":
        shear_density_penalty = float(candidate.get("shear_density", 0.0) or 0.0) * 0.08
    shallow_metrics = _shallower_beam_metrics(candidate, seed_candidate)
    shallowness_score = 0.0
    width_growth_penalty = 0.0
    reinforcement_growth_penalty = 0.0
    non_material_shallow_penalty = 0.0
    if str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow":
        shallowness_score = float(shallow_metrics.get("shallowness_score", 0.0) or 0.0)
        width_growth_penalty = float(shallow_metrics.get("width_growth", 0.0) or 0.0) * 0.9
        reinforcement_growth_penalty = float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0) * 0.06
        if not bool(shallow_metrics.get("materially_shallower")) and (
            float(shallow_metrics.get("width_growth", 0.0) or 0.0) >= 100.0
            or float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0) >= 150.0
        ):
            non_material_shallow_penalty = 60.0

    ductility_priority = _candidate_ductility_governs(seed_candidate)
    candidate["_ductility_priority"] = bool(ductility_priority)
    if ductility_priority:
        tier = _ductility_fix_tier(candidate, seed_candidate)
        candidate["_ductility_tier"] = int(tier)
        candidate["_ductility_tier_label"] = _ductility_tier_label(tier)
        candidate["_ductility_reason"] = _candidate_ductility_reason(candidate, seed_candidate)
    else:
        candidate.pop("_ductility_tier", None)
        candidate.pop("_ductility_tier_label", None)
        candidate.pop("_ductility_reason", None)

    if not bool(candidate.get("is_compliant")):
        total_score = (
            10000.0
            + _candidate_violation_score(candidate)
            + float(shear_practicality.get("shear_candidate_total_practicality_penalty", 0.0) or 0.0)
        )
        return {
            "util_penalty": util_penalty,
            "geometry_penalty": depth_penalty + width_penalty,
            "depth_penalty": depth_penalty,
            "width_penalty": width_penalty,
            "steel_penalty": steel_penalty,
            "congestion_penalty": congestion_penalty,
            "row_penalty": row_penalty,
            "shear_density_penalty": shear_density_penalty,
            "goal_bias_penalty": 0.0,
            "shear_improvement_contribution": util_penalty,
            "bending_efficiency_contribution": steel_penalty + row_penalty,
            "shear_candidate_odd_leg_penalty": shear_practicality.get("shear_candidate_odd_leg_penalty"),
            "shear_candidate_total_practicality_penalty": shear_practicality.get("shear_candidate_total_practicality_penalty"),
            "shallowness_score": shallowness_score,
            "width_growth_penalty": width_growth_penalty,
            "reinforcement_growth_penalty": reinforcement_growth_penalty,
            "total_score": total_score,
        }
    if ductility_priority:
        tier = int(candidate.get("_ductility_tier", 4) or 4)
        ductility_util = _candidate_ductility_util(candidate)
        seed_ductility_util = _candidate_ductility_util(seed_candidate)
        ductility_overflow = max((float(ductility_util) if ductility_util is not None else 999.0) - 1.0, 0.0)
        ductility_penalty = ductility_overflow * 1200.0
        if ductility_util is None:
            ductility_penalty += 200.0
        else:
            ductility_penalty += float(ductility_util) * 120.0
        if ductility_util is not None and seed_ductility_util is not None and float(ductility_util) >= float(seed_ductility_util) - 1e-6:
            ductility_penalty += 140.0
        ast_growth = max(float(candidate.get("Ast_bot", 0.0) or 0.0) - float(seed_candidate.get("Ast_bot", 0.0) or 0.0), 0.0)
        steel_growth_penalty = ast_growth * 0.06
        depth_growth_penalty = max(depth - seed_depth, 0.0) * 0.9
        width_growth_penalty = max(width - float(seed_candidate.get("width", width) or width), 0.0) * 0.15
        tier_penalty = {1: 0.0, 2: 10.0, 3: 30.0, 4: 55.0}.get(int(tier), 55.0)
        total_score = (
            (util_penalty * 0.3)
            + ductility_penalty
            + tier_penalty
            + (steel_penalty * 0.4)
            + steel_growth_penalty
            + (congestion_penalty * 0.8)
            + row_penalty
            + width_growth_penalty
            + depth_growth_penalty
            + shear_density_penalty
            + non_material_shallow_penalty
            + float(shear_practicality.get("shear_candidate_total_practicality_penalty", 0.0) or 0.0)
            - max(shallowness_score, 0.0) * 0.1
        )
        return {
            "util_penalty": util_penalty * 0.3,
            "geometry_penalty": width_growth_penalty + depth_growth_penalty,
            "depth_penalty": depth_growth_penalty,
            "width_penalty": width_growth_penalty,
            "steel_penalty": (steel_penalty * 0.4) + steel_growth_penalty,
            "congestion_penalty": congestion_penalty * 0.8,
            "row_penalty": row_penalty,
            "shear_density_penalty": shear_density_penalty,
            "goal_bias_penalty": tier_penalty,
            "shear_improvement_contribution": util_penalty * 0.3,
            "bending_efficiency_contribution": ductility_penalty,
            "shear_candidate_odd_leg_penalty": shear_practicality.get("shear_candidate_odd_leg_penalty"),
            "shear_candidate_total_practicality_penalty": shear_practicality.get("shear_candidate_total_practicality_penalty"),
            "shallowness_score": shallowness_score,
            "width_growth_penalty": width_growth_penalty,
            "reinforcement_growth_penalty": reinforcement_growth_penalty,
            "total_score": total_score,
        }

    shallow_delta_d_extra = 0.0
    shallow_same_d_bonus = 0.0
    if str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow":
        sd = float(seed_candidate.get("depth", depth) or depth)
        delta_d_grow = max(depth - sd, 0.0)
        shallow_delta_d_extra = delta_d_grow * 3.4
        if delta_d_grow <= 1e-9:
            shallow_same_d_bonus = -48.0

    compound_width_reo_bonus = 0.0
    if (
        str(mode_config.get("search_strategy", "balanced") or "balanced") == "shallow"
        and bool(candidate.get("recommendation_compound"))
        and str(candidate.get("compound_geo_axis") or "") == "width"
    ):
        sd = float(seed_candidate.get("depth", depth) or depth)
        if depth <= sd + 1e-9:
            compound_width_reo_bonus = -18.0

    total_score = (
        util_penalty
        + depth_penalty
        + width_penalty
        + steel_penalty
        + congestion_penalty
        + row_penalty
        + shear_density_penalty
        + width_growth_penalty
        + reinforcement_growth_penalty
        + non_material_shallow_penalty
        + shallow_delta_d_extra
        + shallow_same_d_bonus
        + compound_width_reo_bonus
        + float(shear_practicality.get("shear_candidate_total_practicality_penalty", 0.0) or 0.0)
        - max(shallowness_score, 0.0) * 0.6
    )
    return {
        "util_penalty": util_penalty,
        "geometry_penalty": depth_penalty + width_penalty,
        "depth_penalty": depth_penalty,
        "width_penalty": width_penalty,
        "steel_penalty": steel_penalty,
        "congestion_penalty": congestion_penalty,
        "row_penalty": row_penalty,
        "shear_density_penalty": shear_density_penalty,
        "goal_bias_penalty": 0.0,
        "shear_improvement_contribution": util_penalty,
        "bending_efficiency_contribution": steel_penalty + row_penalty,
        "shear_candidate_odd_leg_penalty": shear_practicality.get("shear_candidate_odd_leg_penalty"),
        "shear_candidate_total_practicality_penalty": shear_practicality.get("shear_candidate_total_practicality_penalty"),
        "shallowness_score": shallowness_score,
        "width_growth_penalty": width_growth_penalty,
        "reinforcement_growth_penalty": reinforcement_growth_penalty,
        "shallow_delta_d_extra": shallow_delta_d_extra,
        "shallow_same_d_bonus": shallow_same_d_bonus,
        "compound_width_reo_bonus": compound_width_reo_bonus,
        "total_score": total_score,
    }


def _candidate_sort_key_for_mode(
    candidate: dict,
    mode_config: dict,
    *,
    runtime: AutoDesignScoringRuntime,
) -> tuple:
    aliases = _scoring_aliases(runtime)
    _candidate_is_practical = aliases["_candidate_is_practical"]
    _candidate_violation_score = aliases["_candidate_violation_score"]
    compute_reo_complexity = aliases["compute_reo_complexity"]
    _candidate_util_distance = aliases["_candidate_util_distance"]
    _shallower_beam_candidate_tier = aliases["_shallower_beam_candidate_tier"]
    _shallower_beam_metrics = aliases["_shallower_beam_metrics"]
    _candidate_ductility_util = aliases["_candidate_ductility_util"]
    _candidate_in_target_band = aliases["_candidate_in_target_band"]
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    compliant_penalty = 0 if bool(candidate.get("is_compliant")) else 1
    practical_penalty = 0 if _candidate_is_practical(candidate, mode_config) else 1
    violation = _candidate_violation_score(candidate)
    fail_count = int(candidate.get("fail_count", 0) or 0)
    worst_util = float(candidate.get("worst_util", float("inf")) or float("inf"))
    complexity = float(candidate.get("reo_complexity", compute_reo_complexity(candidate)) or 0.0)
    util_distance = _candidate_util_distance(candidate, mode_config)
    depth = float(candidate.get("depth", 0.0) or 0.0)
    width = float(candidate.get("width", 0.0) or 0.0)
    bar_count = int(candidate.get("bar_count", 0) or 0)
    row_count = int(candidate.get("row_count", 0) or 0)
    steel_area = float(candidate.get("Ast_bot", 0.0) or 0.0) + float(candidate.get("Ast_top", 0.0) or 0.0)
    shallow_tier, _ = _shallower_beam_candidate_tier(candidate)
    shallow_metrics = _shallower_beam_metrics(
        candidate,
        {
            "state": dict(candidate.get("state") or {}),
            "depth": float(candidate.get("_seed_depth", depth) or depth),
            "width": float(candidate.get("_seed_width", width) or width),
            "Ast_bot": float(candidate.get("_seed_ast_bot", candidate.get("Ast_bot", 0.0)) or candidate.get("Ast_bot", 0.0) or 0.0),
        },
    )
    if bool(candidate.get("_ductility_priority")):
        ductility_util = _candidate_ductility_util(candidate)
        ductility_value = float(ductility_util) if ductility_util is not None else float("inf")
        tier = int(candidate.get("_ductility_tier", 4) or 4)
        return (
            compliant_penalty,
            0 if ductility_value <= 1.0 else 1,
            max(ductility_value - 1.0, 0.0),
            ductility_value,
            tier,
            steel_area,
            practical_penalty,
            row_count,
            bar_count,
            depth,
            width,
            util_distance,
            complexity,
        )
    if compliant_penalty:
        if strategy == "shallow":
            return (
                compliant_penalty,
                fail_count,
                violation,
                worst_util,
                0 if shallow_metrics.get("materially_shallower") else 1,
                shallow_tier,
                depth,
                float(shallow_metrics.get("width_growth", 0.0) or 0.0),
                float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0),
                practical_penalty,
                util_distance,
                complexity,
                steel_area,
                width,
            )
        if strategy == "low_reo":
            return (compliant_penalty, fail_count, violation, worst_util, practical_penalty, util_distance, complexity, row_count, bar_count, depth, steel_area)
        return (
            compliant_penalty,
            fail_count,
            violation,
            worst_util,
            practical_penalty,
            util_distance,
            depth,
            complexity,
            width,
            steel_area,
        )
    if strategy == "shallow":
        return (
            compliant_penalty,
            0 if shallow_metrics.get("materially_shallower") else 1,
            shallow_tier,
            depth,
            float(shallow_metrics.get("width_growth", 0.0) or 0.0),
            float(shallow_metrics.get("reinforcement_growth", 0.0) or 0.0),
            practical_penalty,
            util_distance,
            complexity,
            steel_area,
            width,
        )
    if strategy == "low_reo":
        return (compliant_penalty, practical_penalty, complexity, row_count, bar_count, util_distance, depth, steel_area)
    return (
        compliant_penalty,
        0 if _candidate_in_target_band(candidate, mode_config) else 1,
        practical_penalty,
        util_distance,
        depth,
        complexity,
        width,
        steel_area,
    )


def candidate_materially_worsens(
    new_candidate: dict,
    old_candidate: dict,
    mode_config: dict,
    *,
    phase: str,
    runtime: AutoDesignScoringRuntime,
) -> bool:
    aliases = _scoring_aliases(runtime)
    _candidate_ductility_governs = aliases["_candidate_ductility_governs"]
    _candidate_ductility_util = aliases["_candidate_ductility_util"]
    _agent_debug_log = aliases["_agent_debug_log"]
    _reject_heavier_steel_lower_demand_util = aliases["_reject_heavier_steel_lower_demand_util"]
    _candidate_bending_demand_util = aliases["_candidate_bending_demand_util"]
    _failed_check_labels = aliases["_failed_check_labels"]
    utilisation_gap = aliases["utilisation_gap"]
    compute_reo_complexity = aliases["compute_reo_complexity"]
    if not new_candidate or not old_candidate:
        return False
    old_compliant = bool(old_candidate.get("is_compliant"))
    new_compliant = bool(new_candidate.get("is_compliant"))
    if _candidate_ductility_governs(old_candidate):
        old_du = _candidate_ductility_util(old_candidate)
        new_du = _candidate_ductility_util(new_candidate)
        old_ast = float(old_candidate.get("Ast_bot", 0.0) or 0.0)
        new_ast = float(new_candidate.get("Ast_bot", 0.0) or 0.0)
        if (
            new_ast > old_ast + 1e-6
            and old_du is not None
            and (new_du is None or float(new_du) >= float(old_du) - 0.01)
        ):
            _agent_debug_log(
                "Rejected worse auto-design candidate",
                {
                    "phase": phase,
                    "rejection_reason": "heavier_bottom_steel_without_ductility_gain",
                    "old_Ast_bot": old_ast,
                    "new_Ast_bot": new_ast,
                    "old_ductility_util": old_du,
                    "new_ductility_util": new_du,
                },
                location="inputs_page.py:candidate_materially_worsens",
                hypothesis_id="H31_DUCTILITY",
            )
            return True
    if old_compliant and new_compliant and _reject_heavier_steel_lower_demand_util(old_candidate, new_candidate):
        _agent_debug_log(
            "Rejected worse auto-design candidate",
            {
                "phase": phase,
                "rejection_reason": "heavier_bottom_steel_lower_Mu_star_over_phiMu",
                "old_Ast_bot": float(old_candidate.get("Ast_bot", 0.0) or 0.0),
                "new_Ast_bot": float(new_candidate.get("Ast_bot", 0.0) or 0.0),
                "old_bending_demand_util": _candidate_bending_demand_util(old_candidate),
                "new_bending_demand_util": _candidate_bending_demand_util(new_candidate),
            },
            location="inputs_page.py:candidate_materially_worsens",
            hypothesis_id="H31_STEEL",
        )
        return True
    old_failed = set(_failed_check_labels(old_candidate))
    new_failed = set(_failed_check_labels(new_candidate))
    old_worst = float(old_candidate.get("worst_util", 0.0) or 0.0)
    new_worst = float(new_candidate.get("worst_util", 0.0) or 0.0)
    old_gap = float(utilisation_gap(old_candidate, mode_config))
    new_gap = float(utilisation_gap(new_candidate, mode_config))
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    old_depth = float(old_candidate.get("depth", 0.0) or 0.0)
    new_depth = float(new_candidate.get("depth", 0.0) or 0.0)
    old_complexity = float(old_candidate.get("reo_complexity", compute_reo_complexity(old_candidate)) or 0.0)
    new_complexity = float(new_candidate.get("reo_complexity", compute_reo_complexity(new_candidate)) or 0.0)

    worsens = False
    if not old_compliant:
        if not new_compliant:
            if len(new_failed) > len(old_failed) or new_worst > old_worst + 0.01:
                worsens = True
        if old_compliant and not new_compliant:
            worsens = True
    if old_compliant and new_compliant and new_gap > old_gap + 0.01:
        worsens = True
    if old_compliant and not new_compliant:
        worsens = True
    if old_compliant and new_compliant and strategy == "low_reo":
        if new_complexity > old_complexity + 0.5 and new_gap >= old_gap - 0.01:
            worsens = True
    if old_compliant and new_compliant and strategy == "shallow":
        if new_depth > old_depth + 10.0 and new_gap >= old_gap - 0.01:
            worsens = True

    if worsens:
        _agent_debug_log(
            "Rejected worse auto-design candidate",
            {
                "phase": phase,
                "old_util": old_worst,
                "new_util": new_worst,
                "old_fail_count": int(old_candidate.get("fail_count", 0) or 0),
                "new_fail_count": int(new_candidate.get("fail_count", 0) or 0),
                "old_gap": old_gap,
                "new_gap": new_gap,
            },
            location="inputs_page.py:candidate_materially_worsens",
            hypothesis_id="H31",
        )
    return worsens


__all__ = [
    "AutoDesignScoringRuntime",
    "_candidate_sort_key_for_mode",
    "candidate_materially_worsens",
    "_score_auto_design_candidate_components",
]
