"""Shear candidate generation coordination for Inputs one-click actions."""

from __future__ import annotations

from typing import Any


_SHEAR_CANDIDATE_GENERATION_DEPENDENCIES: tuple[str, ...] = (
    "_activation_shear_state",
    "_bottom_reo_state_label",
    "_distance_to_target_band",
    "_evaluate_auto_design_candidate",
    "_generate_secondary_bending_tightening_states",
    "_float_from_state",
    "_geometry_lock_enabled",
    "_int_from_state",
    "_invalid_shear_spacing_change_without_activation",
    "_log_severe_shear_escalation",
    "_log_shear_candidate_debug",
    "_make_auto_design_candidate_key",
    "_resolve_geometry_width_context",
    "_score_auto_design_candidate",
    "_severe_shear_failure",
    "_shear_candidate_type",
    "_shear_reinforcement_is_active",
    "_shear_severity_band",
    "_shear_state_label",
    "_starter_shear_diameter",
    "_starter_shear_spacing",
    "EFFICIENCY_TARGET_UTIL_MAX",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "REO_BAR_DIAS",
    "REO_SPACINGS",
    "SHARED_DEFAULTS",
    "TARGET_BAND_EPS",
)


def bind_shear_candidate_generation_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_CANDIDATE_GENERATION_DEPENDENCIES
            if name in namespace
        }
    )


def _shear_recommendation_rank_key(
    candidate: dict,
    *,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
) -> tuple:
    cand = dict(candidate or {})
    overview = dict(cand.get("overview") or {})
    utils = dict(overview.get("utils") or {})
    updates = dict(cand.get("updates") or {})
    try:
        shear_util = float(utils.get("shear"))
    except Exception:
        shear_util = None
    if shear_util is None:
        try:
            shear_util = float(cand.get("candidate_post_util"))
        except Exception:
            shear_util = None
    try:
        seed_util = float(seed_shear_util) if seed_shear_util is not None else None
    except Exception:
        seed_util = None
    target_distance = (
        _distance_to_target_band(
            float(shear_util),
            float(EFFICIENCY_TARGET_UTIL_MIN),
            float(EFFICIENCY_TARGET_UTIL_MAX),
        )
        if shear_util is not None
        else 999.0
    )
    improves_shear = bool(seed_util is not None and shear_util is not None and shear_util < seed_util - 1e-9)
    reaches_band = bool(
        cand.get("candidate_reaches_target_band")
        or cand.get("reaches_target_band")
        or target_distance <= float(TARGET_BAND_EPS)
    )
    compliant = bool(cand.get("is_compliant") or cand.get("preview_pass") or cand.get("all_key_pass"))
    candidate_type = str(
        cand.get("shear_candidate_type")
        or _shear_candidate_type(dict(base_state or {}), dict(cand.get("state") or {}))
        or ""
    ).strip().lower()
    type_rank = {
        "combined": 0 if _severe_shear_failure(seed_util) else 3,
        "spacing": 1,
        "diameter": 2,
        "legs": 2,
        "geometry": 3,
        "no_shear_design_cleanup": 4,
    }.get(candidate_type, 5)
    try:
        score = float(cand.get("score"))
    except Exception:
        score = 0.0
    update_complexity = len([key for key, value in updates.items() if dict(base_state or {}).get(key) != value])
    severity_rank = 0 if str(severity_band or "").strip().lower() in {"severe", "critical"} else 1
    return (
        0 if compliant else 1,
        0 if improves_shear else 1,
        0 if reaches_band else 1,
        severity_rank,
        type_rank,
        float(target_distance),
        -float(score),
        int(update_complexity),
        str(cand.get("label") or ""),
    )


def _generate_escalated_shear_states(state: dict, *, severity_band: str) -> list[tuple[str, dict]]:
    base_state = _activation_shear_state(state) if not _shear_reinforcement_is_active(state) else dict(state)
    current_spacing = _int_from_state(base_state, "s_lig", 200)
    current_legs = max(_int_from_state(base_state, "lig_legs", 2), 2)
    current_dia = max(_int_from_state(base_state, "lig_d", 10), 10)
    width_key, _, current_width = _resolve_geometry_width_context(base_state)
    current_depth = _float_from_state(base_state, "D", 600.0)
    max_legs = 10 if severity_band == "extreme" else 8
    max_dia = 24 if severity_band == "extreme" else 20
    leg_values = sorted(set([current_legs, min(current_legs + 2, max_legs), min(current_legs + 4, max_legs)]))
    dia_values = sorted(set([dia for dia in REO_BAR_DIAS if current_dia <= dia <= max_dia] + [current_dia]))
    spacing_targets = [value for value in REO_SPACINGS if value <= current_spacing]
    spacing_values = sorted(set(spacing_targets[:3] + [current_spacing])) or [current_spacing]
    width_steps = [current_width + 50.0, current_width + 100.0]
    depth_steps = [current_depth + 50.0, current_depth + 100.0]
    if severity_band == "extreme":
        width_steps.append(current_width + 150.0)
        depth_steps.append(current_depth + 150.0)

    generated: dict[tuple, tuple[str, dict]] = {}

    def _store(candidate_state: dict) -> None:
        key = _make_auto_design_candidate_key(candidate_state)
        generated[key] = (_shear_candidate_type(state, candidate_state), candidate_state)

    for spacing in spacing_values:
        for legs in leg_values:
            for dia in dia_values:
                candidate_state = dict(base_state)
                candidate_state.update({
                    "lig_d": int(dia),
                    "lig_legs": int(legs),
                    "s_lig": float(spacing),
                })
                _store(candidate_state)

    if not _geometry_lock_enabled(state):
        for width in width_steps:
            candidate_state = dict(base_state)
            candidate_state[width_key] = float(width)
            if width_key != "b":
                candidate_state["b"] = float(width)
            _store(candidate_state)
        for depth in depth_steps:
            candidate_state = dict(base_state)
            candidate_state["D"] = float(depth)
            _store(candidate_state)
        strong_spacing = float(min(spacing_values)) if spacing_values else float(current_spacing)
        strong_legs = int(max(leg_values))
        strong_dia = int(max(dia_values))
        for width in width_steps:
            for depth in depth_steps:
                candidate_state = dict(base_state)
                candidate_state.update({
                    width_key: float(width),
                    "D": float(depth),
                    "lig_d": strong_dia,
                    "lig_legs": strong_legs,
                    "s_lig": strong_spacing,
                })
                if width_key != "b":
                    candidate_state["b"] = float(width)
                _store(candidate_state)

    return list(generated.values())


def _generate_shear_candidates(state: dict, mode_config: dict) -> list[dict]:
    candidates: list[dict] = []
    current_active = _shear_reinforcement_is_active(state)
    seed_candidate = _evaluate_auto_design_candidate(state, source="seed")
    seed_shear_util = (((seed_candidate or {}).get("overview") or {}).get("utils") or {}).get("shear")
    severity_band = _shear_severity_band(seed_shear_util)
    candidate_state_items: list[tuple[str, dict]] = []
    if current_active:
        candidate_legs = [2, 4, 6]
        candidate_dias = [dia for dia in REO_BAR_DIAS if dia <= 16]
        spacing_values = sorted(REO_SPACINGS, reverse=True)
    else:
        candidate_legs = [2]
        candidate_dias = [_starter_shear_diameter(state)]
        spacing_values = [_starter_shear_spacing(state)]
    for dia in candidate_dias:
        for legs in candidate_legs:
            for spacing in spacing_values:
                candidate_state = dict(state)
                candidate_state.update({
                    "lig_d": dia,
                    "lig_legs": legs,
                    "s_lig": float(spacing),
                })
                candidate_state_items.append((_shear_candidate_type(state, candidate_state), candidate_state))
    if _severe_shear_failure(seed_shear_util):
        candidate_state_items.extend(_generate_escalated_shear_states(state, severity_band=severity_band))
    deduped_items: dict[tuple, tuple[str, dict]] = {}
    for candidate_type, candidate_state in candidate_state_items:
        deduped_items[_make_auto_design_candidate_key(candidate_state)] = (candidate_type, candidate_state)
    for candidate_type, candidate_state in deduped_items.values():
        updates = {
            key: value
            for key, value in candidate_state.items()
            if key in SHARED_DEFAULTS and state.get(key) != value
        }
        if _invalid_shear_spacing_change_without_activation(
            state,
            candidate_state,
            source="_generate_shear_candidates",
        ):
            continue
        candidate = _evaluate_auto_design_candidate(
            state,
            updates=updates,
            source="shear",
            label=f"{candidate_type.title()}: {_shear_state_label(candidate_state)}",
            action_type="apply_shear_recommendation",
        )
        if candidate is None:
            _log_shear_candidate_debug(
                source="_generate_shear_candidates",
                candidate_state=candidate_state,
                candidate=None,
            )
            continue
        candidate["shear_candidate_type"] = candidate_type
        if seed_candidate is not None:
            candidate["score"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)
        _log_shear_candidate_debug(
            source="_generate_shear_candidates",
            candidate_state=candidate_state,
            candidate=candidate,
        )
        candidates.append(candidate)
    if _severe_shear_failure(seed_shear_util) and seed_candidate is not None:
        existing_keys = {_make_auto_design_candidate_key(dict(candidate.get("state") or {})) for candidate in candidates}
        ranked_base = sorted(
            candidates,
            key=lambda item: _shear_recommendation_rank_key(
                item,
                base_state=state,
                severity_band=severity_band,
                seed_shear_util=seed_shear_util,
            ),
        )[:4]
        for base_candidate in ranked_base:
            for combined_state in _generate_secondary_bending_tightening_states(base_candidate, limit=3):
                combined_key = _make_auto_design_candidate_key(combined_state)
                if combined_key in existing_keys:
                    continue
                combined_updates = {
                    key: value
                    for key, value in combined_state.items()
                    if key in SHARED_DEFAULTS and state.get(key) != value
                }
                combined_candidate = _evaluate_auto_design_candidate(
                    state,
                    updates=combined_updates,
                    source="shear_combined",
                    label=(
                        f"Combined: {_shear_state_label(combined_state)}"
                        f" + {_bottom_reo_state_label(combined_state)}"
                    ),
                    action_type="apply_shear_recommendation",
                )
                if combined_candidate is None:
                    continue
                combined_candidate["shear_candidate_type"] = "combined"
                combined_candidate["secondary_actions_combined"] = True
                combined_candidate["score"] = _score_auto_design_candidate(combined_candidate, mode_config, seed_candidate)
                candidates.append(combined_candidate)
                existing_keys.add(combined_key)
    if _severe_shear_failure(seed_shear_util) and seed_candidate is not None:
        _log_severe_shear_escalation(
            source="_generate_shear_candidates",
            seed_candidate=seed_candidate,
            severity_band=severity_band,
            candidates=candidates,
            selected=None,
        )
    return candidates


__all__ = [
    "bind_shear_candidate_generation_dependencies",
    "_generate_escalated_shear_states",
    "_generate_shear_candidates",
    "_shear_recommendation_rank_key",
]
