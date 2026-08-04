"""Deterministic recommendation primitives shared by typed family runtimes."""

from __future__ import annotations

import math
from typing import Callable
from inputs_application.recommendation_support import (
    design_width_value,
    resolve_geometry_width_context,
)
from inputs_application.state_utils import (
    float_from_state,
    uls_action_from_state,
    updates_match_state,
)
from inputs_application.candidate_metrics import int_from_state
from inputs_application.legacy_design_brain_adapter import (
    candidate_ductility_governs,
    candidate_ductility_util,
)


RECOMMENDATION_BAR_DIAMETERS = (10, 12, 16, 20, 24, 28, 32, 36, 40)
RECOMMENDATION_SHEAR_SPACINGS = (75, 100, 125, 150, 175, 200, 225, 250, 275, 300)


def starter_shear_diameter(state: dict) -> int:
    current_dia = int_from_state(state, "lig_d", 0)
    if current_dia > 0:
        return int(current_dia)
    practical_dias = [dia for dia in RECOMMENDATION_BAR_DIAMETERS if dia <= 16]
    return int(practical_dias[0] if practical_dias else 10)


def starter_shear_spacing(state: dict) -> float:
    current_spacing = float_from_state(state, "s_lig", 0.0)
    if current_spacing > 0.0 and RECOMMENDATION_SHEAR_SPACINGS:
        return float(
            min(
                RECOMMENDATION_SHEAR_SPACINGS,
                key=lambda value: abs(float(value) - current_spacing),
            )
        )
    if 200 in RECOMMENDATION_SHEAR_SPACINGS:
        return 200.0
    return 200.0


def activation_shear_state(state: dict) -> dict:
    activated = dict(state)
    activated.update(
        {
            "lig_legs": 2,
            "lig_d": starter_shear_diameter(state),
            "s_lig": starter_shear_spacing(state),
        }
    )
    return activated


def bottom_arrangement_to_shared_updates(arrangement: dict) -> dict:
    count_1 = int(arrangement.get("bot1_count", 0) or 0)
    count_2 = int(arrangement.get("bot2_count", 0) or 0)
    dia_1 = int(arrangement.get("db_bot_1", 0) or 0)
    dia_2 = int(arrangement.get("db_bot_2", dia_1) or dia_1)
    return {
        "bot1_layout_mode": "Count",
        "bot1_count": count_1,
        "db_bot_1": dia_1,
        "bot2_layout_mode": "Count",
        "bot2_count": count_2,
        "db_bot_2": dia_2,
        "bot_row_count": 2 if count_2 > 0 else 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": count_1,
        "bot_row_1_spacing": 0.0,
        "bot_row_1_dia": dia_1,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": count_2,
        "bot_row_2_spacing": 0.0,
        "bot_row_2_dia": dia_2,
    }


def bottom_recommendation_prefilter_ok(
    seed_candidate: dict,
    candidate: dict,
    state: dict,
) -> tuple[bool, str]:
    del state
    if not str(candidate.get("label") or "").strip():
        return False, "missing_label"
    if candidate_ductility_governs(seed_candidate):
        seed_util = candidate_ductility_util(seed_candidate)
        trial_util = candidate_ductility_util(candidate)
        if seed_util is None or trial_util is None:
            return False, "missing_ductility_util"
        if float(trial_util) >= float(seed_util) - 1e-9:
            return False, "ductility_not_improved"
    else:
        seed_bending = ((seed_candidate.get("overview") or {}).get("utils") or {}).get(
            "bending"
        )
        trial_bending = ((candidate.get("overview") or {}).get("utils") or {}).get(
            "bending"
        )
        try:
            if seed_bending is None or trial_bending is None:
                return False, "missing_bending_util"
            if float(trial_bending) >= float(seed_bending) - 1e-9:
                return False, "bending_util_not_improved"
        except (TypeError, ValueError):
            return False, "missing_bending_util"
    return True, "ok"


def maybe_prefer_compound_over_pure_geometry(
    best: dict | None,
    ranked: list[dict],
    *,
    state: dict,
    seed_candidate: dict,
    mode_config: dict,
) -> dict | None:
    if not best or best.get("recommendation_compound"):
        return best
    if not best.get("recommendation_geometry_trial"):
        return best
    axis = geometry_trial_axis_for_bottom(best, state)
    if axis not in ("width", "depth"):
        return best
    try:
        best_score = float(best.get("score", 1e9) or 1e9)
    except (TypeError, ValueError):
        best_score = 1e9
    strategy = str(mode_config.get("search_strategy", "balanced") or "balanced")
    seed_depth = float(seed_candidate.get("depth", 0.0) or 0.0)
    selected: dict | None = None
    selected_score = float("inf")
    for candidate in ranked:
        if not candidate.get("recommendation_compound"):
            continue
        if str(candidate.get("compound_geo_axis") or "") != axis:
            continue
        if not (best.get("is_compliant") and candidate.get("is_compliant")):
            continue
        if axis == "width" and strategy == "shallow":
            try:
                candidate_depth = float(
                    candidate.get("depth", seed_depth) or seed_depth
                )
            except (TypeError, ValueError):
                continue
            if candidate_depth > seed_depth + 1e-9:
                continue
        try:
            score = float(candidate.get("score", 1e9) or 1e9)
        except (TypeError, ValueError):
            continue
        if score <= best_score + 28.0 and score < selected_score:
            selected = candidate
            selected_score = score
    return selected if selected is not None else best


def practical_bottom_reo_label(count_1: int, count_2: int, diameter: int) -> str:
    return (
        f"{count_1}N{diameter} + {count_2}N{diameter}"
        if count_2 > 0
        else f"{count_1}N{diameter}"
    )


def candidate_materially_improves(current: dict, trial: dict) -> bool:
    if not trial:
        return False
    if bool(trial.get("is_compliant")) and not bool(current.get("is_compliant")):
        return True
    current_worst = float(current.get("worst_util", float("inf")) or float("inf"))
    trial_worst = float(trial.get("worst_util", float("inf")) or float("inf"))
    return trial_worst < current_worst - 1e-6


def geometry_trial_axis_for_bottom(candidate: dict, state: dict) -> str | None:
    if not candidate.get("recommendation_geometry_trial"):
        return None
    updates = dict(candidate.get("updates") or {})
    if "D" in updates:
        return "depth"
    width_key, _, _ = resolve_geometry_width_context(state)
    return "width" if width_key in updates else None


def annotate_bottom_candidate_deltas(
    candidate: dict,
    seed_candidate: dict,
    state: dict,
) -> None:
    seed_state = dict(seed_candidate.get("state") or state)
    candidate_state = dict(candidate.get("state") or {})
    seed_depth = float(
        seed_candidate.get("depth", float_from_state(seed_state, "D", 0.0))
        or float_from_state(seed_state, "D", 0.0)
    )
    candidate_depth = float(
        candidate.get("depth", float_from_state(candidate_state, "D", 0.0))
        or float_from_state(candidate_state, "D", 0.0)
    )
    seed_width = float(
        seed_candidate.get("width", design_width_value(seed_state))
        or design_width_value(seed_state)
    )
    candidate_width = float(
        candidate.get("width", design_width_value(candidate_state))
        or design_width_value(candidate_state)
    )
    candidate["delta_D_mm"] = round(candidate_depth - seed_depth, 3)
    candidate["delta_b_mm"] = round(candidate_width - seed_width, 3)
    candidate["delta_Ast_bot"] = round(
        float(candidate.get("Ast_bot", 0.0) or 0.0)
        - float(seed_candidate.get("Ast_bot", 0.0) or 0.0),
        3,
    )


def efficiency_reduction_profile(overview: dict | None) -> bool:
    if (
        not isinstance(overview, dict)
        or not bool(overview.get("all_key_pass"))
        or bool(overview.get("any_fail"))
    ):
        return False
    try:
        worst = float(
            overview.get("governing_util", overview.get("worst_util", 0.0))
            or 0.0
        )
    except (TypeError, ValueError):
        return False
    return worst <= 0.75


def shear_change_is_reinforcement_growth(seed: dict, candidate: dict) -> bool:
    seed_diameter = int_from_state(seed, "lig_d", 0)
    seed_legs = int_from_state(seed, "lig_legs", 0)
    candidate_diameter = int_from_state(candidate, "lig_d", 0)
    candidate_legs = int_from_state(candidate, "lig_legs", 0)
    seed_spacing = float_from_state(seed, "s_lig", 200.0)
    candidate_spacing = float_from_state(candidate, "s_lig", 200.0)
    if (
        seed_diameter <= 0
        and seed_legs < 2
        and candidate_diameter <= 0
        and candidate_legs < 2
    ):
        return False
    if (
        candidate_diameter <= 0
        and candidate_legs < 2
        and (seed_diameter > 0 or seed_legs >= 2)
    ):
        return False
    if candidate_diameter > seed_diameter or candidate_legs > seed_legs:
        return True
    return bool(
        candidate_diameter > 0
        and candidate_legs >= 2
        and seed_diameter > 0
        and seed_legs >= 2
        and candidate_spacing < seed_spacing - 1e-9
    )


def candidate_is_growth_move(seed_candidate: dict, candidate: dict) -> bool:
    if not seed_candidate or not candidate:
        return False
    seed_state = dict(seed_candidate.get("state") or {})
    candidate_state = dict(candidate.get("state") or {})
    seed_depth = float(
        seed_candidate.get("depth", float_from_state(seed_state, "D", 0.0))
        or float_from_state(seed_state, "D", 0.0)
    )
    candidate_depth = float(
        candidate.get("depth", float_from_state(candidate_state, "D", 0.0))
        or float_from_state(candidate_state, "D", 0.0)
    )
    if candidate_depth > seed_depth + 1e-9:
        return True
    seed_width = float(resolve_geometry_width_context(seed_state)[2] or 0.0)
    candidate_width = float(
        candidate.get("width", design_width_value(candidate_state))
        or design_width_value(candidate_state)
    )
    if candidate_width > seed_width + 1e-9:
        return True
    if float(candidate.get("Ast_bot", 0.0) or 0.0) > float(
        seed_candidate.get("Ast_bot", 0.0) or 0.0
    ) + 1e-9:
        return True
    return shear_change_is_reinforcement_growth(seed_state, candidate_state)


def required_ast_for_arrangement(state: dict, arrangement: dict) -> float:
    from bending_core import _get_compute_bending_capacity_pure

    compute = _get_compute_bending_capacity_pure()
    low = 0.0
    high = float(arrangement["Ast_bot"])
    for _ in range(40):
        trial = 0.5 * (low + high)
        result = compute(
            b=design_width_value(state),
            D=float_from_state(state, "D", 600.0),
            fc=float_from_state(state, "fc", 40.0),
            fsy=float_from_state(state, "fsy", 500.0),
            Ast=trial,
            Mu_star=uls_action_from_state(state, "M"),
            phi=float_from_state(state, "phi_bend", 0.85),
            d_input=arrangement["d_centroid"],
            cover_bot=float_from_state(state, "cover_bot", 40.0),
            db_bot=arrangement["db_bot"],
            nb_bot=arrangement["nb_bot"],
            rowgap_bot=float_from_state(state, "rowgap_bot", 60.0),
        )
        if float(result.get("Mu_util", float("inf"))) <= 1.0:
            high = trial
        else:
            low = trial
    return float(high)


def shear_change_is_relevant(overview: dict, actions: dict) -> bool:
    return bool(
        float(actions.get("Vu", 0.0) or 0.0) > 0.0
        and float((overview.get("utils") or {}).get("shear", 0.0) or 0.0) >= 0.2
    )


def candidate_leg_counts(current_legs: int, *, conservative: bool) -> list[int]:
    current = max(int(current_legs or 2), 2)
    return (
        [count for count in range(current - 1, 1, -1)]
        if conservative
        else [count for count in range(current + 1, 9)]
    )


def shear_util_from_candidate(candidate: dict | None) -> float | None:
    if not candidate:
        return None
    try:
        value = (candidate.get("overview") or {}).get("utils", {}).get("shear")
        if value is None:
            return None
        parsed = float(value)
        return None if math.isnan(parsed) else parsed
    except (TypeError, ValueError):
        return None


def shear_change_magnitude(candidate: dict, state: dict) -> tuple:
    candidate_state = dict(candidate.get("state") or {})
    current_legs = max(int_from_state(state, "lig_legs", 2), 2)
    current_spacing = float_from_state(state, "s_lig", 0.0)
    current_diameter = max(int_from_state(state, "lig_d", 10), 10)
    current_width = resolve_geometry_width_context(state)[2]
    current_depth = float_from_state(state, "D", 600.0)
    candidate_legs = max(
        int_from_state(candidate_state, "lig_legs", current_legs),
        0,
    )
    candidate_spacing = float_from_state(
        candidate_state,
        "s_lig",
        current_spacing,
    )
    candidate_diameter = max(
        int_from_state(candidate_state, "lig_d", current_diameter),
        0,
    )
    candidate_width = resolve_geometry_width_context(candidate_state)[2]
    candidate_depth = float_from_state(candidate_state, "D", current_depth)
    depth_delta = abs(candidate_depth - current_depth)
    width_delta = abs(candidate_width - current_width)
    return (
        int(depth_delta > 1e-9 or width_delta > 1e-9),
        abs(candidate_legs - current_legs),
        abs(candidate_spacing - current_spacing),
        abs(candidate_diameter - current_diameter),
        depth_delta,
        width_delta,
    )


def shortlist_smallest_successful_shear_candidates(
    candidates: list[dict],
    state: dict,
    *,
    target_hi: float | None,
) -> list[dict]:
    acceptable = []
    for candidate in candidates:
        util = shear_util_from_candidate(candidate)
        if (
            bool(candidate.get("is_compliant"))
            and util is not None
            and (target_hi is None or util <= target_hi + 1e-9)
        ):
            acceptable.append(candidate)
    if not acceptable:
        return list(candidates)
    ranked = sorted(
        acceptable,
        key=lambda candidate: (
            shear_change_magnitude(candidate, state),
            float(candidate.get("score", 0.0) or 0.0),
        ),
    )
    smallest_magnitude = shear_change_magnitude(ranked[0], state)
    smallest_score = float(ranked[0].get("score", 999999.0) or 999999.0)
    return [
        candidate
        for candidate in ranked
        if shear_change_magnitude(candidate, state) == smallest_magnitude
        or float(candidate.get("score", 999999.0) or 999999.0)
        <= smallest_score + 0.25
    ]


def candidate_is_within_smallest_fix_band(
    candidate: dict,
    smallest_magnitude: tuple | None,
    state: dict,
) -> bool:
    return bool(
        smallest_magnitude is None
        or shear_change_magnitude(candidate, state) <= smallest_magnitude
    )


def shear_detailing_updates_pure(
    updates: dict | None,
) -> tuple[bool, tuple[str, ...]]:
    if not isinstance(updates, dict) or not updates:
        return True, tuple()
    allowed = {"lig_d", "lig_legs", "s_lig"}
    unexpected = tuple(sorted(key for key in updates if str(key) not in allowed))
    return not bool(unexpected), unexpected


def shear_overview_is_failing(overview: dict) -> bool:
    if str((overview.get("statuses") or {}).get("shear") or "") == "FAIL":
        return True
    try:
        util = (overview.get("utils") or {}).get("shear")
        return bool(util is not None and float(util) > 1.0 + 1e-12)
    except (TypeError, ValueError):
        return False


def shear_candidate_type(base_state: dict, candidate_state: dict) -> str:
    width_key, _, current_width = resolve_geometry_width_context(base_state)
    current_depth = float_from_state(base_state, "D", 0.0)
    next_width = float_from_state(candidate_state, width_key, current_width)
    next_depth = float_from_state(candidate_state, "D", current_depth)
    width_changed = abs(next_width - current_width) > 1e-9
    depth_changed = abs(next_depth - current_depth) > 1e-9
    current_spacing = float_from_state(base_state, "s_lig", 0.0)
    next_spacing = float_from_state(candidate_state, "s_lig", current_spacing)
    current_legs = int_from_state(base_state, "lig_legs", 0)
    next_legs = int_from_state(candidate_state, "lig_legs", current_legs)
    current_dia = int_from_state(base_state, "lig_d", 0)
    next_dia = int_from_state(candidate_state, "lig_d", current_dia)
    if next_legs == 0 and current_legs > 0:
        return "no shear links"
    spacing_tighter = next_spacing < current_spacing - 1e-9
    legs_increased = next_legs > current_legs
    dia_increased = next_dia > current_dia
    if (width_changed or depth_changed) and (
        spacing_tighter or legs_increased or dia_increased
    ):
        return "combined"
    if depth_changed:
        return "depth increase"
    if width_changed:
        return "width increase"
    if dia_increased and not spacing_tighter and not legs_increased:
        return "larger dia"
    if legs_increased and not spacing_tighter:
        return "more legs"
    if spacing_tighter:
        return "spacing"
    if dia_increased:
        return "larger dia"
    if legs_increased:
        return "more legs"
    current_fc = float(float_from_state(base_state, "fc", 0.0) or 0.0)
    next_fc = float(float_from_state(candidate_state, "fc", current_fc) or current_fc)
    if abs(next_fc - current_fc) > 1e-9:
        return "material_fc"
    return "spacing"


def shear_spacing_layout_must_not_trigger_strengthening(
    state: dict,
    overview: dict | None,
) -> bool:
    if not isinstance(state, dict):
        return False
    resolved_overview = overview if isinstance(overview, dict) else {}
    shear_pack = (resolved_overview.get("packs") or {}).get("shear") or {}
    truth_status = str(
        state.get("shear_truth_status")
        or shear_pack.get("shear_truth_status")
        or ""
    ).strip().upper()
    if truth_status != "PASS":
        return False
    governing_source = str(
        state.get("shear_governing_source")
        or shear_pack.get("summary_governing_source")
        or resolved_overview.get("overview_shear_governing_source")
        or ""
    ).strip()
    governing_reason = str(
        state.get("shear_governing_reason")
        or shear_pack.get("summary_governing_reason")
        or resolved_overview.get("overview_shear_governing_reason")
        or ""
    ).strip()
    if (
        governing_source != "sectional_shear_capacity"
        or "sectional_shear_capacity_governs" not in governing_reason
    ):
        return False
    return not bool(state.get("canonical_shear_spacing_override_active"))


def invalid_shear_spacing_change_without_activation(
    base_state: dict,
    candidate_state: dict,
    *,
    source: str,
    agent_debug_log: Callable[..., None],
) -> bool:
    from inputs_application.engineering_predicates import (
        shear_reinforcement_is_active,
    )

    if shear_reinforcement_is_active(base_state):
        return False
    spacing_before = float_from_state(base_state, "s_lig", 0.0)
    spacing_after = float_from_state(candidate_state, "s_lig", spacing_before)
    candidate_legs = int_from_state(candidate_state, "lig_legs", 0)
    if candidate_legs >= 2 or abs(spacing_after - spacing_before) <= 1e-9:
        return False
    agent_debug_log(
        "Invalid shear candidate: spacing changed without activating stirrups",
        {
            "source": source,
            "lig_legs": candidate_legs,
            "lig_d": int_from_state(candidate_state, "lig_d", 0),
            "s_lig": spacing_after,
            "shear_reinforcement_active": False,
        },
        location="inputs_page.py:invalid_shear_candidate",
        hypothesis_id="H_SHEAR_INVALID",
    )
    return True


def shear_recommendation_prefinal_eligible(
    candidate: dict | None,
    *,
    state: dict,
    conservative: bool,
    baseline_su: float | None,
) -> tuple[bool, str]:
    if not candidate:
        return False, "none"
    updates = candidate.get("updates") or {}
    if not updates:
        return False, "empty_updates"
    if updates_match_state(state, updates):
        return False, "noop"
    if not str(candidate.get("label") or "").strip():
        return False, "missing_label"
    if candidate.get("score") is None:
        return False, "missing_score"
    shear_util = shear_util_from_candidate(candidate)
    if shear_util is None:
        return False, "missing_shear_util"
    if (
        not conservative
        and baseline_su is not None
        and float(shear_util) >= float(baseline_su) - 1e-9
    ):
        return False, "shear_util_not_improved"
    branch = str(candidate.get("shear_ladder_branch") or "")
    candidate_state = dict(candidate.get("state") or {})
    if branch == "spacing_tighter":
        proposed_spacing = float_from_state(
            candidate_state,
            "s_lig",
            float_from_state(state, "s_lig", 0.0),
        )
        current_spacing = float_from_state(state, "s_lig", 0.0)
        if (
            current_spacing > 1e-9
            and proposed_spacing >= current_spacing - 1e-9
        ):
            return False, "spacing_not_reduced"
    if not conservative:
        legs = int_from_state(candidate_state, "lig_legs", 0)
        if 0 < legs < 2:
            return False, "lig_legs_below_2"
    return True, "ok"


def shear_overview_is_conservative_cleanup(overview: dict) -> bool:
    if shear_overview_is_failing(overview) or not bool(overview.get("all_key_pass")):
        return False
    if str((overview.get("statuses") or {}).get("shear") or "") != "PASS":
        return False
    try:
        util = (overview.get("utils") or {}).get("shear")
        return bool(util is not None and float(util) <= 0.75)
    except (TypeError, ValueError):
        return False


__all__ = [
    "RECOMMENDATION_BAR_DIAMETERS",
    "RECOMMENDATION_SHEAR_SPACINGS",
    "activation_shear_state",
    "annotate_bottom_candidate_deltas",
    "bottom_arrangement_to_shared_updates",
    "bottom_recommendation_prefilter_ok",
    "candidate_is_growth_move",
    "candidate_materially_improves",
    "efficiency_reduction_profile",
    "geometry_trial_axis_for_bottom",
    "invalid_shear_spacing_change_without_activation",
    "maybe_prefer_compound_over_pure_geometry",
    "practical_bottom_reo_label",
    "required_ast_for_arrangement",
    "candidate_is_within_smallest_fix_band",
    "candidate_leg_counts",
    "shear_change_is_relevant",
    "shear_change_magnitude",
    "shear_candidate_type",
    "shear_detailing_updates_pure",
    "shear_overview_is_conservative_cleanup",
    "shear_overview_is_failing",
    "shear_recommendation_prefinal_eligible",
    "shear_spacing_layout_must_not_trigger_strengthening",
    "shear_util_from_candidate",
    "shortlist_smallest_successful_shear_candidates",
    "starter_shear_diameter",
    "starter_shear_spacing",
]
