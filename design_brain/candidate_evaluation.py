from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from calculations.bending import effective_depth_with_links_mm
from design_brain.contracts import bottom_arrangement_to_shared_updates
from design_brain.repair import (
    build_near_current_bottom_repair_specs,
    build_near_current_geometry_repair_specs,
    build_near_current_shear_repair_specs,
    _parse_util_value as _repair_parse_util_value,
)


def _stable_payload(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_candidate_evaluation_hash(value: Any) -> str:
    return hashlib.sha256(_stable_payload(value).encode("utf-8")).hexdigest()


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(dict(base or {}))
    for key, value in dict(updates or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged.get(key) or {}), value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


_TARGET_BAND_GEOMETRY_UPDATE_KEYS = frozenset(
    {"b", "bw", "D", "bf", "tf", "tw", "bf_bot", "tf_bot"},
)
_TARGET_BAND_BOTTOM_UPDATE_KEYS = frozenset(
    {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "bot1_spacing",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "bot2_spacing",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
        "bot_row_3_mode",
        "bot_row_3_bars",
        "bot_row_3_spacing",
        "bot_row_3_dia",
        "bot_row_4_mode",
        "bot_row_4_bars",
        "bot_row_4_spacing",
        "bot_row_4_dia",
        "Ast_bot",
    },
)
_TARGET_BAND_SHEAR_UPDATE_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})


def diff_candidate_state_updates(base_state: dict[str, Any] | None, final_state: dict[str, Any] | None) -> dict[str, Any]:
    """Return a plain update diff from base state to final candidate state."""

    base = dict(base_state or {})
    delta: dict[str, Any] = {}
    for key, value in dict(final_state or {}).items():
        if key not in base:
            delta[key] = value
            continue
        base_value = base[key]
        if isinstance(value, float) or isinstance(base_value, float):
            try:
                if abs(float(base_value) - float(value)) > 1e-9:
                    delta[key] = value
            except (TypeError, ValueError):
                if base_value != value:
                    delta[key] = value
        elif base_value != value:
            delta[key] = value
    return delta


def resolve_target_band_domains_touched_by_updates(updates: dict[str, Any] | None) -> set[str]:
    """Return target-band domains affected by a plain update payload."""

    keys = set(dict(updates or {}).keys())
    touched: set[str] = set()
    if keys & _TARGET_BAND_SHEAR_UPDATE_KEYS:
        touched.add("shear")
    if keys & (_TARGET_BAND_BOTTOM_UPDATE_KEYS | _TARGET_BAND_GEOMETRY_UPDATE_KEYS):
        touched.add("bending")
    return touched


def resolve_target_band_candidate_domains_for_updates(
    base_domains: list[str] | tuple[str, ...] | set[str] | None,
    updates: dict[str, Any] | None = None,
) -> list[str]:
    """Merge existing target-band domains with domains touched by updates."""

    domains = {str(domain or "").strip().lower() for domain in (base_domains or [])}
    domains |= resolve_target_band_domains_touched_by_updates(updates)
    return [domain for domain in ("bending", "shear") if domain in domains]


def build_target_band_auto_design_context_projection(
    *,
    resolved_seed_state: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    actions: dict[str, Any] | None,
    seed_overview: dict[str, Any] | None = None,
    ductility_priority: bool = False,
    geometry_locked: bool = False,
    disable_shear_strength_candidates: bool = False,
    disable_shear_cleanup_candidates: bool = False,
) -> dict[str, Any]:
    """Build the plain target-band auto-design context projection."""

    resolved_mode_config = dict(mode_config or {})
    resolved_actions = dict(actions or {})
    return {
        "seed_state": dict(resolved_seed_state or {}),
        "mode_config": dict(resolved_mode_config),
        "mode_signature": str(resolved_mode_config.get("search_strategy", "balanced") or "balanced"),
        "actions": dict(resolved_actions),
        "actions_signature": tuple(resolved_actions.get("signature", ())),
        "seed_overview": dict(seed_overview or {}),
        "ductility_priority": bool(ductility_priority),
        "geometry_locked": bool(geometry_locked),
        "disable_shear_strength_candidates": bool(disable_shear_strength_candidates),
        "disable_shear_cleanup_candidates": bool(disable_shear_cleanup_candidates),
        "seen_candidate_keys": set(),
        "layout_fit_cache": {},
    }


def resolve_geometry_width_context(state: dict[str, Any] | None) -> tuple[str, str, float]:
    """Resolve the width-bearing field for plain geometry state."""

    source = dict(state or {})
    sec_shape = str(source.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(source.get("bw", source.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(source.get("tw", source.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(source.get("b", 400.0) or 400.0)


def build_geometry_update_projection(
    *,
    base_state: dict[str, Any] | None,
    width_key: str,
    current_width: int | float | None,
    depth: int | float | None = None,
    width: int | float | None = None,
    minimum_practical_depth_mm: int | float,
    minimum_practical_width_mm: int | float,
    guarded_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build raw and guarded geometry candidate-state projection from plain inputs."""

    candidate_state = dict(base_state or {})
    resolved_width_key = str(width_key or "b")
    try:
        current_width_f = float(current_width if current_width is not None else 0.0)
    except (TypeError, ValueError):
        current_width_f = 0.0
    try:
        min_depth = float(minimum_practical_depth_mm)
    except (TypeError, ValueError):
        min_depth = 0.0
    try:
        min_width = float(minimum_practical_width_mm)
    except (TypeError, ValueError):
        min_width = 0.0

    raw_updates: dict[str, float] = {}
    if depth is not None:
        raw_updates["D"] = float(int(round(max(min_depth, float(depth)) / 10.0) * 10))
    if width is not None:
        resolved_width = float(int(round(max(min_width, float(width)) / 10.0) * 10))
        raw_updates[resolved_width_key] = resolved_width
        if resolved_width_key != "b":
            raw_updates["b"] = resolved_width
    else:
        candidate_state[resolved_width_key] = current_width_f

    applied_updates = dict(raw_updates if guarded_updates is None else guarded_updates)
    candidate_state.update(applied_updates)
    return {
        "candidate_state": candidate_state,
        "raw_updates": raw_updates,
        "guarded_updates": applied_updates,
    }


def generate_smaller_geometry_candidate_states(
    *,
    current_candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    geometry_locked: bool,
    minimum_practical_depth_mm: int | float,
    minimum_practical_width_mm: int | float,
    geometry_state_fn: Callable[..., dict[str, Any]],
    candidate_key_fn: Callable[[dict[str, Any]], Any],
) -> list[dict[str, Any]]:
    """Generate smaller geometry candidates from plain state and injected materializers."""

    candidate = dict(current_candidate or {})
    state = dict(candidate.get("state") or {})
    if bool(geometry_locked):
        return []
    mode = dict(mode_config or {})
    strategy = str(mode.get("search_strategy", "balanced") or "balanced")
    try:
        state_depth = float(state.get("D", 600.0) or 600.0)
    except (TypeError, ValueError):
        state_depth = 600.0
    try:
        current_depth = float(candidate.get("depth", state_depth) or state_depth)
    except (TypeError, ValueError):
        current_depth = state_depth
    width_key, _, current_width = resolve_geometry_width_context(state)
    try:
        min_depth = float(minimum_practical_depth_mm)
    except (TypeError, ValueError):
        min_depth = 0.0
    try:
        min_width = float(minimum_practical_width_mm)
    except (TypeError, ValueError):
        min_width = 0.0

    variants: dict[Any, dict[str, Any]] = {}
    for depth in [current_depth - 50.0, current_depth - 100.0]:
        if depth >= min_depth:
            candidate_state = dict(geometry_state_fn(state, depth=depth) or {})
            variants[candidate_key_fn(candidate_state)] = candidate_state
    if strategy != "shallow":
        narrower = current_width - 50.0
        if narrower >= min_width:
            candidate_state = dict(geometry_state_fn(state, width=narrower) or {})
            variants[candidate_key_fn(candidate_state)] = candidate_state
        if width_key != "b":
            current_rectified = dict(geometry_state_fn(state, width=current_width) or {})
            variants[candidate_key_fn(current_rectified)] = current_rectified
    return list(variants.values())


def _target_band_float(source: dict[str, Any], key: str, default: float) -> float:
    value = source.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _target_band_int(source: dict[str, Any], key: str, default: int) -> int:
    value = source.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def resolve_bottom_reo_candidate_bottom_updates(state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Resolve explicit bottom-reo update keys from a plain candidate state.

    Canonical row-model keys are the authority. Legacy keys remain a fallback
    so shared evaluator plumbing can keep consuming one legacy-shaped update
    payload while family/runtime outputs migrate to canonical candidate states.
    """

    source = dict(state or {})
    count_1 = _target_band_int(source, "bot_row_1_bars", _target_band_int(source, "bot1_count", 0))
    count_2 = _target_band_int(source, "bot_row_2_bars", _target_band_int(source, "bot2_count", 0))
    db_1 = _target_band_int(source, "bot_row_1_dia", _target_band_int(source, "db_bot_1", 0))
    db_2 = _target_band_int(source, "bot_row_2_dia", _target_band_int(source, "db_bot_2", db_1))
    if db_1 <= 0 or (count_1 + count_2) <= 0:
        return None
    return {
        "db_bot_1": db_1,
        "db_bot_2": db_2 if count_2 > 0 else db_1,
        "bot1_count": count_1,
        "bot2_count": count_2,
    }


def resolve_candidate_shear_updates(state: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve shear-link update keys from a plain candidate state."""

    source = dict(state or {})
    return {
        "lig_d": _target_band_int(source, "lig_d", 10),
        "lig_legs": _target_band_int(source, "lig_legs", 2),
        "s_lig": _target_band_float(source, "s_lig", 200.0),
    }


def build_candidate_action_state_projection(
    state: dict[str, Any] | None,
    *,
    actions: dict[str, Any] | None,
    shared_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Overlay resolved design actions onto a plain candidate state."""

    resolved = dict(state or {})
    for key, default in dict(shared_defaults or {}).items():
        resolved.setdefault(key, default)
    action_values = dict(actions or {})
    resolved["uls_Mstar"] = float(action_values.get("Mu", _target_band_float(resolved, "uls_Mstar", 0.0)) or 0.0)
    resolved["uls_Vstar"] = float(action_values.get("Vu", _target_band_float(resolved, "uls_Vstar", 0.0)) or 0.0)
    resolved["uls_Nstar"] = float(action_values.get("Nu", _target_band_float(resolved, "uls_Nstar", 0.0)) or 0.0)
    resolved["Mu_star"] = float(action_values.get("Mu", _target_band_float(resolved, "Mu_star", 0.0)) or 0.0)
    resolved["Vu_star"] = float(action_values.get("Vu", _target_band_float(resolved, "Vu_star", 0.0)) or 0.0)
    resolved["N_star"] = float(action_values.get("Nu", _target_band_float(resolved, "N_star", 0.0)) or 0.0)
    resolved["sls_Mstar"] = float(action_values.get("SLS_M", _target_band_float(resolved, "sls_Mstar", 0.0)) or 0.0)
    resolved["uls_Mstar_pos_manual"] = float(
        _target_band_float(
            resolved,
            "uls_Mstar_pos_manual",
            max(0.0, _target_band_float(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["uls_Mstar_neg_manual"] = float(
        _target_band_float(
            resolved,
            "uls_Mstar_neg_manual",
            max(0.0, -_target_band_float(resolved, "uls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_pos_manual"] = float(
        _target_band_float(
            resolved,
            "sls_Mstar_pos_manual",
            max(0.0, _target_band_float(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Mstar_neg_manual"] = float(
        _target_band_float(
            resolved,
            "sls_Mstar_neg_manual",
            max(0.0, -_target_band_float(resolved, "sls_Mstar", 0.0)),
        )
        or 0.0
    )
    resolved["sls_Vstar"] = float(action_values.get("SLS_V", _target_band_float(resolved, "sls_Vstar", 0.0)) or 0.0)
    resolved["Tu_star"] = float(action_values.get("Tu", _target_band_float(resolved, "Tu_star", 0.0)) or 0.0)
    resolved["P_star"] = float(action_values.get("Pu", _target_band_float(resolved, "P_star", 0.0)) or 0.0)
    resolved["actions_uls"] = {
        "M": resolved["uls_Mstar"],
        "V": resolved["uls_Vstar"],
        "N": resolved["uls_Nstar"],
        "T": resolved["Tu_star"],
        "P": resolved["P_star"],
    }
    return resolved


def build_bottom_reo_candidate_metric_projection(
    state: dict[str, Any] | None,
    *,
    bottom_updates: dict[str, Any] | None = None,
    effective_bottom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build bottom-reo target-band metric projection from plain state.

    This owns only the pure bottom-reo state/metric projection used by
    target-band cleanup lanes. It does not generate candidates, evaluate
    candidate safety, rank/select recommendations, build CTA payloads, render,
    or touch UI/session state.
    """

    source = dict(state or {})
    updates = dict(bottom_updates or {})
    if effective_bottom is not None:
        bottom = dict(effective_bottom or {})
    elif updates:
        db_bot = float(updates["db_bot_1"])
        nb_bot = int(updates["bot1_count"]) + int(updates["bot2_count"])
        ast_bot = (nb_bot * math.pi * db_bot**2) / 4.0
        lig_diameter = _target_band_float(source, "lig_d", 10.0)
        d_centroid = effective_depth_with_links_mm(
            D_mm=_target_band_float(source, "D", 600.0),
            cover_to_ligs_mm=_target_band_float(source, "cover_bot", 40.0),
            lig_diameter_mm=lig_diameter,
            bar_diameter_mm=float(db_bot or 0.0),
        )
        bottom = {
            "Ast_bot": float(ast_bot),
            "db_bot": float(db_bot),
            "nb_bot": int(nb_bot),
            "d_centroid": float(d_centroid),
        }
    else:
        db_bot = _target_band_float(
            source,
            "db_bot",
            _target_band_float(source, "db_bot_1", 20.0),
        )
        nb_bot = _target_band_int(source, "nb_bot", 0)
        ast_bot = _target_band_float(source, "Ast_bot", 0.0)
        lig_diameter = _target_band_float(source, "lig_d", 10.0)
        d_centroid = effective_depth_with_links_mm(
            D_mm=_target_band_float(source, "D", 600.0),
            cover_to_ligs_mm=_target_band_float(source, "cover_bot", 40.0),
            lig_diameter_mm=lig_diameter,
            bar_diameter_mm=float(db_bot or 0.0),
        )
        bottom = {
            "Ast_bot": float(ast_bot),
            "db_bot": float(db_bot),
            "nb_bot": int(nb_bot),
            "d_centroid": float(d_centroid),
        }

    count_1 = _target_band_int(source, "bot1_count", 0)
    count_2 = _target_band_int(source, "bot2_count", 0)
    resolved_bottom_updates = resolve_bottom_reo_candidate_bottom_updates(source)

    explicit_rows = _target_band_int(source, "bot_row_count", 0)
    row_count = explicit_rows if explicit_rows > 0 else (2 if count_2 > 0 else 1)
    resolved_nb_bot = int(bottom.get("nb_bot", 0) or 0)
    bar_count = resolved_nb_bot if resolved_nb_bot > 0 else count_1 + count_2
    bar_dia = float(bottom.get("db_bot", 0.0) or _target_band_float(source, "db_bot_1", 0.0))
    _, _, width = resolve_geometry_width_context(source)
    width = max(float(width or 0.0), 1.0)
    rows_penalty = max(int(row_count) - 1, 0) * 2.5
    density_penalty = (int(bar_count) * max(bar_dia, 1.0)) / width
    congestion_index = float(int(bar_count) + rows_penalty + density_penalty)
    from design_brain.families.bending import calculate_bottom_reo_complexity

    reo_complexity = calculate_bottom_reo_complexity(
        bar_count=bar_count,
        row_count=row_count,
        reo_congestion_index=congestion_index,
        bot1_count=source.get("bot1_count"),
        bot2_count=source.get("bot2_count"),
    )
    return {
        "bottom_updates": resolved_bottom_updates,
        "effective_bottom": bottom,
        "row_count": int(row_count),
        "bar_count": int(bar_count),
        "reo_congestion_index": float(congestion_index),
        "reo_complexity": float(reo_complexity),
    }


def generate_bottom_reo_target_band_candidate_states(
    *,
    current_candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    context: dict[str, Any] | None,
    lane: str,
    candidate_key_fn: Callable[[dict[str, Any]], Any],
    bar_diameters: list[int] | tuple[int, ...],
    default_stage_candidate_limit: int,
) -> list[dict[str, Any]]:
    """Generate bottom-reo target-band lane states from Design Brain services."""

    from design_brain.families.bending import build_bottom_reo_arrangement_pool_from_state

    candidate = dict(current_candidate or {})
    state = dict(candidate.get("state") or {})
    mode = dict(mode_config or {})
    ctx = dict(context or {})
    lane_id = str(lane or "")
    arrangements = build_bottom_reo_arrangement_pool_from_state(
        state,
        mode,
        band=0,
        context=ctx,
        limit=None,
        bar_diameters=bar_diameters,
        default_limit=int(default_stage_candidate_limit),
    )
    variants: dict[Any, dict[str, Any]] = {}
    if lane_id == "less_bottom_reo":
        from design_brain.families.bending import calculate_bottom_reo_complexity

        current_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
        current_complexity = float(
            candidate.get(
                "reo_complexity",
                calculate_bottom_reo_complexity(
                    bar_count=candidate.get("bar_count", 0),
                    row_count=candidate.get("row_count", 1),
                    reo_congestion_index=candidate.get("reo_congestion_index", 0.0),
                    bot1_count=state.get("bot1_count"),
                    bot2_count=state.get("bot2_count"),
                ),
            )
            or 0.0
        )
        for arrangement in arrangements:
            candidate_state = dict(state)
            updates = bottom_arrangement_to_shared_updates(dict(arrangement or {}))
            candidate_state.update(updates)
            projection = build_bottom_reo_candidate_metric_projection(
                candidate_state,
                bottom_updates=resolve_bottom_reo_candidate_bottom_updates(candidate_state),
            )
            preview_bottom = dict(projection.get("effective_bottom") or {})
            preview_complexity = float(projection.get("reo_complexity", 0.0) or 0.0)
            if (
                float(preview_bottom.get("Ast_bot", 0.0) or 0.0) < current_ast - 1e-6
                or preview_complexity < current_complexity - 1e-6
            ):
                variants[candidate_key_fn(candidate_state)] = candidate_state
        return list(variants.values())

    if lane_id == "simpler_layout":
        current_rows = int(candidate.get("row_count", 0) or 0)
        current_bars = int(candidate.get("bar_count", 0) or 0)
        for arrangement in arrangements:
            candidate_state = dict(state)
            candidate_state.update(bottom_arrangement_to_shared_updates(dict(arrangement or {})))
            projection = build_bottom_reo_candidate_metric_projection(
                candidate_state,
                bottom_updates=resolve_bottom_reo_candidate_bottom_updates(candidate_state),
            )
            row_count = int(projection.get("row_count", 0) or 0)
            bar_count = int(projection.get("bar_count", 0) or 0)
            if row_count < current_rows or bar_count < current_bars:
                variants[candidate_key_fn(candidate_state)] = candidate_state
        return list(variants.values())

    return []


def generate_target_band_refinement_candidate_states(
    *,
    current_candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    context: dict[str, Any] | None,
    geometry_variants_fn: Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]],
    bottom_reo_variants_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], list[dict[str, Any]]],
    shear_reo_variants_fn: Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]],
    layout_variants_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], list[dict[str, Any]]],
    candidate_key_fn: Callable[[dict[str, Any]], Any],
    shear_cleanup_possible_fn: Callable[[dict[str, Any]], bool],
    shear_cleanup_allowed_by_truth_fn: Callable[[dict[str, Any]], Any],
    max_candidates: int,
) -> list[dict[str, Any]]:
    """Generate target-band refinement candidate states from injected lanes."""

    candidate = dict(current_candidate or {})
    mode = dict(mode_config or {})
    ctx = dict(context or {})
    candidates: dict[Any, dict[str, Any]] = {}

    for candidate_state in list(geometry_variants_fn(candidate, mode) or []):
        candidates[candidate_key_fn(dict(candidate_state or {}))] = dict(candidate_state or {})
    for candidate_state in list(bottom_reo_variants_fn(candidate, mode, ctx) or []):
        candidates[candidate_key_fn(dict(candidate_state or {}))] = dict(candidate_state or {})

    overview = candidate.get("overview")
    shear_pack = (((overview or {}) if isinstance(overview, dict) else {}).get("packs") or {}).get("shear") or {}
    truth_result = shear_cleanup_allowed_by_truth_fn(shear_pack if isinstance(shear_pack, dict) else {})
    truth_allows_variants = bool(truth_result[0] if isinstance(truth_result, tuple) and truth_result else truth_result)
    if (
        shear_cleanup_possible_fn(dict(candidate.get("state") or {}))
        and not bool(ctx.get("disable_shear_cleanup_candidates"))
        and truth_allows_variants
    ):
        for candidate_state in list(shear_reo_variants_fn(candidate, mode) or []):
            candidates[candidate_key_fn(dict(candidate_state or {}))] = dict(candidate_state or {})

    for candidate_state in list(layout_variants_fn(candidate, mode, ctx) or []):
        candidates[candidate_key_fn(dict(candidate_state or {}))] = dict(candidate_state or {})

    candidates.pop(candidate_key_fn(dict(candidate.get("state") or {})), None)
    limit = max(0, int(max_candidates or 0))
    return list(candidates.values())[:limit]


def build_auto_design_candidate_key(
    state: dict[str, Any] | None,
    *,
    resolved_actions: dict[str, Any] | None = None,
) -> tuple[tuple[str, str], ...]:
    """Build the stable auto-design candidate key from plain state/action data."""

    candidate_state = dict(state or {})
    actions = dict(resolved_actions or {})
    tracked_keys = (
        "sec_shape",
        "b",
        "bw",
        "tw",
        "D",
        "bf",
        "tf",
        "bf_bot",
        "tf_bot",
        "fc",
        "fsy",
        "Ec",
        "Es",
        "phi_bend",
        "phi_shear",
        "cover_top",
        "cover_bot",
        "cover_side",
        "rowgap_top",
        "rowgap_bot",
        "design_optimisation_goal",
        "optimisation_lock_geometry",
        "Ast_top",
        "Tu_star",
        "P_star",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    )
    key_parts = [(key, str(candidate_state.get(key))) for key in tracked_keys]
    key_parts.extend(
        [
            ("resolved_Mu", str(actions.get("Mu"))),
            ("resolved_Vu", str(actions.get("Vu"))),
            ("resolved_Nu", str(actions.get("Nu"))),
            ("resolved_SLS_M", str(actions.get("SLS_M"))),
            ("resolved_SLS_V", str(actions.get("SLS_V"))),
            ("resolved_source", str(actions.get("source"))),
        ]
    )
    return tuple(key_parts)


def resolve_shear_governing_truth_allows_cleanup(
    shear_pack: dict[str, Any] | None,
    *,
    near_limit_threshold: float,
) -> tuple[bool, dict[str, Any]]:
    """Resolve whether shear cleanup may be scheduled from governing shear truth."""

    detail: dict[str, Any] = {
        "shear_overdesign_truth_util": None,
        "shear_overdesign_truth_status": None,
        "shear_overdesign_truth_governing_check": None,
        "shear_cleanup_blocked_due_to_truth_near_limit": False,
    }
    if not isinstance(shear_pack, dict):
        return True, detail
    raw_status = str(shear_pack.get("summary_governing_status") or "").strip().upper()
    util = _repair_parse_util_value(shear_pack.get("summary_governing_util"))
    check = str(shear_pack.get("summary_governing_check_name") or "").strip()
    detail["shear_overdesign_truth_util"] = util
    detail["shear_overdesign_truth_status"] = raw_status or None
    detail["shear_overdesign_truth_governing_check"] = check or None
    if raw_status in {"FAIL", "FAILED"}:
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if "NEAR" in raw_status or raw_status in ("WARN", "CHECK", "NEAR LIMIT"):
        detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
        return False, detail
    if util is not None:
        try:
            if float(util) >= float(near_limit_threshold) - 1e-12:
                detail["shear_cleanup_blocked_due_to_truth_near_limit"] = True
                return False, detail
        except (TypeError, ValueError):
            pass
    return True, detail


def resolve_shear_cleanup_possible(
    *,
    lig_legs: int | float | None,
    spacing_mm: int | float | None,
    max_spacing_mm: int | float | None,
) -> bool:
    """Resolve whether shear-link cleanup can still produce a lighter state."""

    try:
        legs = int(lig_legs or 0)
    except (TypeError, ValueError):
        legs = 0
    try:
        spacing = float(spacing_mm or 0.0)
    except (TypeError, ValueError):
        spacing = 0.0
    try:
        max_spacing = float(max_spacing_mm if max_spacing_mm is not None else 300.0)
    except (TypeError, ValueError):
        max_spacing = 300.0
    return legs > 0 or (spacing > 0.0 and spacing < max_spacing - 1e-9)


def build_candidate_state_hash(base_state: dict[str, Any], updates: dict[str, Any]) -> str:
    return stable_candidate_evaluation_hash(_deep_merge(base_state, updates))


@dataclass(frozen=True)
class BeamCandidateInput:
    base_state: dict[str, Any]
    evaluation_context: dict[str, Any] = field(default_factory=dict)
    target_band: tuple[float, float] | None = None
    source: str = "design_brain_candidate_evaluation"
    state_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_hash", stable_candidate_evaluation_hash(self.base_state))


@dataclass(frozen=True)
class BeamCandidateUpdate:
    updates: dict[str, Any]
    candidate_id: str | None = None
    source_lane: str | None = None
    update_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "update_hash", stable_candidate_evaluation_hash(self.updates))


@dataclass(frozen=True)
class BeamCandidateEvaluation:
    input_hash: str
    candidate_state_hash: str
    update_hash: str
    bending_utilisation: float | None = None
    shear_utilisation: float | None = None
    serviceability_status: dict[str, Any] = field(default_factory=dict)
    geometry_status: dict[str, Any] = field(default_factory=dict)
    detailing_status: dict[str, Any] = field(default_factory=dict)
    spacing_status: dict[str, Any] = field(default_factory=dict)
    capacity_summary: dict[str, Any] = field(default_factory=dict)
    failure_flags: dict[str, Any] = field(default_factory=dict)
    target_band_status: str | None = None
    overview: dict[str, Any] = field(default_factory=dict)
    engineering_status: dict[str, Any] = field(default_factory=dict)
    evaluation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_evaluation_hash(self) -> "BeamCandidateEvaluation":
        payload = self.to_dict()
        payload["evaluation_hash"] = None
        return replace(self, evaluation_hash=stable_candidate_evaluation_hash(payload))


def evaluate_design_candidate_with_updates(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict | None:
    candidate_state = state_snapshot_fn(state)
    if updates:
        candidate_state.update(updates)
    return evaluator_fn(
        candidate_state,
        source=source,
        label=label,
        action_type=action_type,
        updates=updates,
    )


def resolve_design_candidate_overview_for_safety_check(
    *,
    current_state: dict,
    updates: dict | None,
    resolved_candidate: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict[str, Any]:
    """Resolve candidate overview evidence for safety checks.

    Existing resolved-candidate overview evidence wins. If it is missing, use
    the candidate evaluation service path with the same metadata as the former
    page shim fallback.
    """

    candidate = dict(resolved_candidate or {}) if isinstance(resolved_candidate, dict) else {}
    overview = dict(candidate.get("overview") or {})
    if overview:
        return {
            "candidate": dict(candidate),
            "overview": dict(overview),
            "updates": dict(updates or {}),
            "used_fallback_evaluation": False,
            "fallback_source": None,
        }

    evaluated = evaluate_design_candidate_with_updates(
        dict(current_state or {}),
        updates=dict(updates or {}),
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=state_snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    if not isinstance(evaluated, dict):
        return {
            "candidate": {},
            "overview": {},
            "updates": dict(updates or {}),
            "used_fallback_evaluation": True,
            "fallback_source": source,
        }

    candidate = dict(evaluated)
    candidate["updates"] = dict(updates or {})
    return {
        "candidate": dict(candidate),
        "overview": dict(candidate.get("overview") or {}),
        "updates": dict(updates or {}),
        "used_fallback_evaluation": True,
        "fallback_source": source,
    }


def evaluate_shear_low_util_candidate_with_updates(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict | None:
    """Evaluate a shear low-util cleanup candidate through the shared boundary."""

    return evaluate_design_candidate_with_updates(
        state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=state_snapshot_fn,
        evaluator_fn=evaluator_fn,
    )


def evaluate_probe_equivalent_bending_candidate_with_updates(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict | None:
    """Evaluate a probe-equivalent bending cleanup candidate through the shared boundary."""

    return evaluate_design_candidate_with_updates(
        state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=state_snapshot_fn,
        evaluator_fn=evaluator_fn,
    )


def _auto_design_candidate_row_valid(
    *,
    n_bars: int,
    db: float,
    beam_width: float,
    cover: float,
    s_min: float,
) -> bool:
    available = float(beam_width) - (2.0 * float(cover))
    required = (int(n_bars) * float(db)) + ((int(n_bars) - 1) * float(s_min))
    if int(n_bars) < 2:
        return False
    if required > available:
        return False
    return True


def _longitudinal_face_count(source: dict[str, Any], face: str) -> int:
    prefix = "bot" if face == "bottom" else "top"
    row_prefix = "bot" if face == "bottom" else "top"
    row_1 = _target_band_int(
        source,
        f"{row_prefix}1_count",
        _target_band_int(source, f"{row_prefix}_row_1_bars", 0),
    )
    row_2 = _target_band_int(
        source,
        f"{row_prefix}2_count",
        _target_band_int(source, f"{row_prefix}_row_2_bars", 0),
    )
    total_key = "nb_bot" if face == "bottom" else "nb_top"
    total = _target_band_int(source, total_key, 0)
    resolved = int(total or 0)
    row_total = int(row_1 or 0) + int(row_2 or 0)
    if row_total > 0:
        resolved = row_total
    if resolved <= 0 and prefix == "top":
        # Older candidate rows sometimes omit unchanged top reo fields. The
        # absence is not a one-bar proposal; live state normalisation supplies
        # the real top rows before apply.
        return 2
    return int(resolved)


def resolve_minimum_longitudinal_bar_rule(
    state: dict[str, Any] | None,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the shared two-bars-per-face rule for candidate/apply surfaces."""

    trial = dict(state or {})
    trial.update(dict(updates or {}))
    bottom_count = _longitudinal_face_count(trial, "bottom")
    top_count = _longitudinal_face_count(trial, "top")
    violations: list[str] = []
    if bottom_count < 2:
        violations.append("bottom_longitudinal_bars_below_minimum_2")
    if top_count < 2:
        violations.append("top_longitudinal_bars_below_minimum_2")
    return {
        "valid": not violations,
        "minimum_bars_per_face": 2,
        "bottom_bar_count": int(bottom_count),
        "top_bar_count": int(top_count),
        "violations": violations,
        "reason": "minimum_two_longitudinal_bars_per_face" if violations else None,
    }


def resolve_auto_design_candidate_row_layout_validity(
    *,
    beam_width: float,
    cover: float,
    bot1_count: int,
    bot2_count: int,
    db_bot_1: float,
    db_bot_2: float,
    top1_count: int = 2,
    top2_count: int = 0,
    db_top_1: float = 12.0,
    db_top_2: float = 12.0,
    min_spacing_row_1: float | None = None,
    min_spacing_row_2: float | None = None,
) -> dict[str, Any]:
    """Resolve row-layout validity for shared auto-design candidate selection.

    The page remains responsible for normalising state fields into plain scalar
    inputs. This helper owns the pure row-validity policy used by the selector.
    """

    row1_spacing = float(min_spacing_row_1 if min_spacing_row_1 is not None else max(float(db_bot_1), 25.0))
    row2_spacing = float(min_spacing_row_2 if min_spacing_row_2 is not None else max(float(db_bot_2), 25.0))
    row1_valid = _auto_design_candidate_row_valid(
        n_bars=int(bot1_count),
        db=float(db_bot_1),
        beam_width=float(beam_width),
        cover=float(cover),
        s_min=row1_spacing,
    )
    row2_valid = True
    if int(bot2_count) > 0:
        row2_valid = _auto_design_candidate_row_valid(
            n_bars=int(bot2_count),
            db=float(db_bot_2),
            beam_width=float(beam_width),
            cover=float(cover),
            s_min=row2_spacing,
        )
    top_row_1_valid = _auto_design_candidate_row_valid(
        n_bars=int(top1_count),
        db=float(db_top_1),
        beam_width=float(beam_width),
        cover=float(cover),
        s_min=max(float(db_top_1), 25.0),
    )
    top_row_2_valid = True
    if int(top2_count) > 0:
        top_row_2_valid = _auto_design_candidate_row_valid(
            n_bars=int(top2_count),
            db=float(db_top_2),
            beam_width=float(beam_width),
            cover=float(cover),
            s_min=max(float(db_top_2), 25.0),
        )
    minimum_bar_rule = resolve_minimum_longitudinal_bar_rule(
        {
            "bot1_count": int(bot1_count),
            "bot2_count": int(bot2_count),
            "top1_count": int(top1_count),
            "top2_count": int(top2_count),
        }
    )
    return {
        "valid": bool(row1_valid and row2_valid and top_row_1_valid and top_row_2_valid and minimum_bar_rule["valid"]),
        "row1_valid": bool(row1_valid),
        "row2_valid": bool(row2_valid),
        "top_row_1_valid": bool(top_row_1_valid),
        "top_row_2_valid": bool(top_row_2_valid),
        "beam_width": float(beam_width),
        "cover": float(cover),
        "bot1_count": int(bot1_count),
        "bot2_count": int(bot2_count),
        "top1_count": int(top1_count),
        "top2_count": int(top2_count),
        "db_bot_1": float(db_bot_1),
        "db_bot_2": float(db_bot_2),
        "db_top_1": float(db_top_1),
        "db_top_2": float(db_top_2),
        "minimum_bar_rule": minimum_bar_rule,
        "min_spacing_row_1": row1_spacing,
        "min_spacing_row_2": row2_spacing,
    }


def filter_auto_design_candidates_by_row_layout(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """Filter auto-design candidates by the existing bottom-row layout validity rule."""

    input_candidates = [
        candidate
        for candidate in list(candidates or [])
        if isinstance(candidate, dict)
    ]
    filtered: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, candidate in enumerate(input_candidates):
        cs = dict(candidate.get("state") or {})
        _, _, beam_width_raw = resolve_geometry_width_context(cs)
        beam_width = float(beam_width_raw or 0.0)
        cover = float(_target_band_float(cs, "cover_side", 40.0) or 40.0)
        bot1_count = int(_target_band_int(cs, "bot1_count", 0) or 0)
        bot2_count = int(_target_band_int(cs, "bot2_count", 0) or 0)
        db_bot_1 = float(_target_band_float(cs, "db_bot_1", 0.0) or 0.0)
        db_bot_2 = float(_target_band_float(cs, "db_bot_2", db_bot_1) or db_bot_1)
        top1_count = int(_target_band_int(cs, "top1_count", _target_band_int(cs, "top_row_1_bars", 2)) or 2)
        top2_count = int(_target_band_int(cs, "top2_count", _target_band_int(cs, "top_row_2_bars", 0)) or 0)
        db_top_1 = float(_target_band_float(cs, "db_top_1", _target_band_float(cs, "top_row_1_dia", 12.0)) or 12.0)
        db_top_2 = float(_target_band_float(cs, "db_top_2", _target_band_float(cs, "top_row_2_dia", db_top_1)) or db_top_1)
        row_layout = resolve_auto_design_candidate_row_layout_validity(
            beam_width=beam_width,
            cover=cover,
            bot1_count=bot1_count,
            bot2_count=bot2_count,
            db_bot_1=db_bot_1,
            db_bot_2=db_bot_2,
            top1_count=top1_count,
            top2_count=top2_count,
            db_top_1=db_top_1,
            db_top_2=db_top_2,
        )
        if bool(row_layout.get("valid")):
            filtered.append(candidate)
        else:
            rejected.append(
                {
                    "index": index,
                    "label": str(candidate.get("label") or ""),
                    "row_layout": dict(row_layout),
                }
            )
    return {
        "input_candidate_count": len(input_candidates),
        "filtered_candidates": filtered,
        "rejected_candidates": rejected,
        "rejected_candidate_count": len(rejected),
    }


def score_auto_design_candidates_for_selection(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    mode_config: dict[str, Any] | None,
    seed_candidate: dict[str, Any] | None,
    *,
    annotate_candidate_fn: Callable[[dict[str, Any], dict[str, Any]], None],
    score_candidate_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], float],
) -> dict[str, Any]:
    """Apply existing target-band annotation and score callbacks to candidate objects."""

    input_candidates = [
        candidate
        for candidate in list(candidates or [])
        if isinstance(candidate, dict)
    ]
    mode = dict(mode_config or {})
    seed = dict(seed_candidate or {})
    scored: list[dict[str, Any]] = []
    for candidate in input_candidates:
        annotate_candidate_fn(candidate, mode)
        candidate["score"] = score_candidate_fn(candidate, mode, seed)
        scored.append(candidate)
    return {
        "input_candidate_count": len(input_candidates),
        "scored_candidates": scored,
        "scored_candidate_count": len(scored),
    }


def resolve_auto_design_winner_pool_decision(
    compliant_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    band_reaching_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    current_in_band: bool,
) -> dict[str, Any]:
    """Resolve the candidate pool used by the existing auto-design selector."""

    compliant = [
        candidate
        for candidate in list(compliant_candidates or [])
        if isinstance(candidate, dict)
    ]
    band_reachers = [
        candidate
        for candidate in list(band_reaching_candidates or [])
        if isinstance(candidate, dict)
    ]
    band_reacher_available = len(band_reachers) > 0
    force_band_reacher_pool = bool((not bool(current_in_band)) and band_reachers)
    selected_because_band = bool(compliant) and force_band_reacher_pool
    pool = band_reachers if force_band_reacher_pool else compliant
    reason = (
        "at_least_one_compliant_candidate_reaches_target_band_in_one_move"
        if band_reacher_available
        else (
            "no_compliant_candidate_reaches_target_band_in_one_move"
            if compliant
            else "no_compliant_candidates"
        )
    )
    return {
        "band_reacher_available": band_reacher_available,
        "band_reacher_reason": reason,
        "local_step_selected_only_because_no_band_reacher": bool(compliant) and not band_reacher_available,
        "force_band_reacher_pool": force_band_reacher_pool,
        "selected_because_band": selected_because_band,
        "winner_pool_mode": "band_reachers_only" if force_band_reacher_pool else "all_compliant",
        "pool_candidates": pool,
        "compliant_count": len(compliant),
        "band_reacher_count": len(band_reachers),
        "band_reacher_labels_considered": [
            str(candidate.get("label") or "")[:100]
            for candidate in band_reachers[:24]
        ],
    }


def resolve_auto_design_band_reacher_ranked_pool(
    pool_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    seed_candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    strategy: str,
    goal: str,
    current_state: dict[str, Any] | None,
    *,
    goal_score_fn: Callable[[dict[str, Any], str, dict[str, Any], dict[str, Any]], tuple[float, str]],
    delta_metrics_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    shallower_selection_key_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], tuple[Any, ...]],
) -> dict[str, Any]:
    """Rank band-reaching candidates with the existing goal-score callbacks."""

    pool = [
        candidate
        for candidate in list(pool_candidates or [])
        if isinstance(candidate, dict)
    ]
    seed = dict(seed_candidate or {})
    mode = dict(mode_config or {})
    state = dict(current_state or {})
    preference = "shallower" if str(goal or "") == "shallower_beam" else "balanced"
    ranked_pool: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for item in pool:
        goal_score, goal_reason = goal_score_fn(item, str(goal or ""), state, mode)
        deltas = delta_metrics_fn(item, state)
        item["winning_candidate_goal_preference"] = preference
        item["candidate_goal_score"] = goal_score
        item["candidate_goal_tie_break_reason"] = goal_reason
        item["candidate_goal_delta_d_mm"] = deltas.get("delta_d")
        item["candidate_goal_delta_ast_mm2"] = deltas.get("delta_ast")
        item["candidate_goal_delta_w_mm"] = deltas.get("delta_w")
        if str(goal or "") == "shallower_beam":
            rank_key = (
                float(goal_score),
                float(deltas.get("result_depth", item.get("depth", 0.0)) or 0.0),
                float(deltas.get("delta_ast", 0.0) or 0.0),
                float(deltas.get("delta_w", 0.0) or 0.0),
                shallower_selection_key_fn(item, seed, mode) if str(strategy or "") == "shallow" else (),
                float(item.get("score", 0.0) or 0.0),
                float(item.get("depth", 0.0) or 0.0),
                float(item.get("width", 0.0) or 0.0),
            )
        else:
            rank_key = (
                float(goal_score),
                float(item.get("score", 0.0) or 0.0),
                float(deltas.get("congestion", 0.0) or 0.0),
                float(deltas.get("row_pen", 0.0) or 0.0),
                float(deltas.get("delta_d", 0.0) or 0.0),
                float(deltas.get("delta_w", 0.0) or 0.0),
                float(deltas.get("delta_ast", 0.0) or 0.0),
                float(item.get("depth", 0.0) or 0.0),
                float(item.get("width", 0.0) or 0.0),
            )
        ranked_pool.append((rank_key, item))
    ranked_pool.sort(key=lambda row: row[0])
    winner = ranked_pool[0][1] if ranked_pool else None
    winner_goal_score = float(winner.get("candidate_goal_score", 0.0) or 0.0) if winner is not None else None
    goal_tie_break_reason = str(winner.get("candidate_goal_tie_break_reason") or "") if winner is not None else None
    runner_up_goal_score = None
    if winner is not None and len(ranked_pool) > 1:
        runner = ranked_pool[1][1]
        runner_up_goal_score = float(runner.get("candidate_goal_score", 0.0) or 0.0)
        winner["runner_up_goal_score"] = runner_up_goal_score
    return {
        "ranked_pool": ranked_pool,
        "winner": winner,
        "winner_goal_score": winner_goal_score,
        "runner_up_goal_score": runner_up_goal_score,
        "goal_tie_break_reason": goal_tie_break_reason,
        "ranked_candidate_count": len(ranked_pool),
        "preference": preference,
    }


def apply_auto_design_winner_metadata_projection(
    winner: dict[str, Any] | None,
    *,
    selected_because_band: bool,
    winner_pool_mode: str,
    band_reacher_labels_considered: list[str] | tuple[str, ...] | None,
    winner_goal_score: float | None,
    runner_up_goal_score: float | None,
    goal_tie_break_reason: str | None,
    goal_preference: str,
) -> dict[str, Any] | None:
    """Apply existing selected-candidate metadata projection to the winner object."""

    if not isinstance(winner, dict):
        return None
    winner["winning_candidate_post_util"] = winner.get("candidate_post_util")
    winner["winning_candidate_reaches_target_band"] = winner.get("candidate_reaches_target_band")
    winner["winning_candidate_distance_to_target_band"] = winner.get("candidate_distance_to_target_band")
    winner["winning_candidate_selected_because_reaches_band"] = bool(selected_because_band)
    winner["winning_candidate_selected_from_band_reachers"] = bool(selected_because_band)
    winner["winner_pool_mode"] = str(winner_pool_mode or "all_compliant")
    winner["band_reacher_labels_considered"] = [
        str(label or "")[:100]
        for label in list(band_reacher_labels_considered or [])
    ]
    winner["winning_candidate_goal_score"] = winner_goal_score
    winner["runner_up_goal_score"] = runner_up_goal_score
    winner["goal_tie_break_reason"] = goal_tie_break_reason
    winner["winning_candidate_goal_preference"] = str(goal_preference or "balanced")
    label = str(winner.get("label") or "").strip()
    if label:
        winner["canonical_winner_label"] = label
        winner["title_locked_from_final_winner"] = True
    return winner


def resolve_candidate_bending_demand_util(candidate: dict[str, Any] | None) -> float | None:
    """Resolve demand/flexural-capacity utilisation from candidate overview data."""

    if not isinstance(candidate, dict):
        return None
    overview = candidate.get("overview") or {}
    bending_pack = (overview.get("packs") or {}).get("bending") or {}
    phi_mu = float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0)
    mu_star = float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0)
    if phi_mu <= 1e-9:
        return None
    return mu_star / phi_mu


def resolve_auto_design_candidate_objective_util(
    candidate: dict[str, Any] | None,
    *,
    optimisation_goal: str | None = None,
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Resolve the objective utilisation used by target-band candidate ranking."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    state = candidate_d.get("state") if isinstance(candidate_d.get("state"), dict) else {}
    if optimisation_goal is not None:
        goal = str(optimisation_goal or "")
    elif callable(optimisation_goal_resolver):
        goal = str(optimisation_goal_resolver(dict(state or {})) or "")
    else:
        goal = str(state.get("design_optimisation_goal") or "balanced")
    overview = candidate_d.get("overview") if isinstance(candidate_d.get("overview"), dict) else {}
    utils = overview.get("utils") if isinstance(overview.get("utils"), dict) else {}
    target_domain = str(candidate_d.get("target_domain_for_band") or "").strip().lower()
    bending_demand_util = resolve_candidate_bending_demand_util(candidate_d)

    if target_domain == "shear" or goal == "less_shear_reinforcement":
        objective_values = [utils.get("shear")]
    else:
        objective_values = [bending_demand_util, utils.get("shear")]

    resolved_values: list[float] = []
    for value in objective_values:
        if value is None:
            continue
        try:
            resolved = float(value)
        except Exception:
            continue
        if not math.isnan(resolved):
            resolved_values.append(resolved)

    if resolved_values:
        return max(resolved_values)
    return float(candidate_d.get("worst_util", 0.0) or 0.0)


def resolve_auto_design_candidate_target_band_metrics(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Resolve the target-band annotation fields for an auto-design candidate."""

    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except (TypeError, ValueError):
        target_min = float(default_target_min)
        target_max = float(default_target_max)
    util = resolve_auto_design_candidate_objective_util(
        candidate,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    candidate_d = candidate if isinstance(candidate, dict) else {}
    return {
        "candidate_post_util": float(util),
        "candidate_distance_to_target_band": resolve_distance_to_target_band(
            util,
            target_min,
            target_max,
        ),
        "candidate_reaches_target_band": bool(
            bool(candidate_d.get("is_compliant"))
            and
            resolve_candidate_in_target_band(
                candidate,
                mode,
                default_target_min=default_target_min,
                default_target_max=default_target_max,
                fail_status=fail_status,
                optimisation_goal_resolver=optimisation_goal_resolver,
            )
        ),
    }


def resolve_auto_design_candidate_violation_score(candidate: dict[str, Any] | None) -> float:
    """Resolve the non-compliant auto-design candidate violation score."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    util = float(candidate_d.get("worst_util", 0.0) or 0.0)
    overflow = max(util - 1.0, 0.0)
    fail_count = int(candidate_d.get("fail_count", 0) or 0)
    return overflow * 100.0 + fail_count * 25.0


def resolve_auto_design_shear_candidate_practicality_metrics(
    candidate: dict[str, Any] | None,
    current_state: dict[str, Any] | None,
) -> dict[str, float | int]:
    """Resolve shear cleanup/strength candidate practicality metrics from plain state."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    cs = dict(candidate_d.get("state") or {})
    current = dict(current_state or {})
    cur_legs = max(_target_band_int(current, "lig_legs", 0), 0)
    cand_legs = max(_target_band_int(cs, "lig_legs", cur_legs), 0)
    cur_s = float(_target_band_float(current, "s_lig", 0.0) or 0.0)
    cand_s = float(_target_band_float(cs, "s_lig", cur_s) or cur_s)
    cur_dia = max(_target_band_int(current, "lig_d", 0), 0)
    cand_dia = max(_target_band_int(cs, "lig_d", cur_dia), 0)
    cur_depth = float(_target_band_float(current, "D", 0.0) or 0.0)
    cand_depth = float(_target_band_float(cs, "D", cur_depth) or cur_depth)
    _, _, cur_width_raw = resolve_geometry_width_context(current)
    _, _, cand_width_raw = resolve_geometry_width_context(cs)
    cur_width = float(cur_width_raw or 0.0)
    cand_width = float(cand_width_raw or cur_width)
    cur_ast_bot = float(_target_band_float(current, "Ast_bot", 0.0) or 0.0)
    cur_ast_top = float(_target_band_float(current, "Ast_top", 0.0) or 0.0)
    cur_ast = cur_ast_bot + cur_ast_top
    cand_ast = (
        float(candidate_d.get("Ast_bot", _target_band_float(cs, "Ast_bot", cur_ast_bot)) or 0.0)
        + float(candidate_d.get("Ast_top", _target_band_float(cs, "Ast_top", cur_ast_top)) or 0.0)
    )

    leg_delta = abs(int(cand_legs) - int(cur_legs))
    spacing_delta = abs(float(cand_s) - float(cur_s))
    dia_delta = abs(int(cand_dia) - int(cur_dia))
    depth_delta = abs(float(cand_depth) - float(cur_depth))
    width_delta = abs(float(cand_width) - float(cur_width))
    steel_delta = abs(float(cand_ast) - float(cur_ast))
    odd_leg_penalty = 0.015 if cand_legs > 0 and cand_legs % 2 == 1 else 0.0
    total_practicality_penalty = odd_leg_penalty + (float(leg_delta) * 0.01)
    geometry_escalation_flag = 1 if (depth_delta > 1e-9 or width_delta > 1e-9) else 0
    geometry_delta = depth_delta + width_delta
    engineering_change = (
        (5.0 if geometry_escalation_flag else 0.0)
        + float(leg_delta)
        + (spacing_delta / 100.0)
        + (dia_delta / 2.0)
        + (geometry_delta / 100.0)
        + (steel_delta / 500.0)
        + total_practicality_penalty
    )
    return {
        "shear_candidate_leg_count": int(cand_legs),
        "shear_candidate_leg_delta": int(leg_delta),
        "shear_candidate_spacing_delta": float(spacing_delta),
        "shear_candidate_dia_delta": int(dia_delta),
        "shear_candidate_depth_delta": float(depth_delta),
        "shear_candidate_width_delta": float(width_delta),
        "shear_candidate_geometry_delta": float(geometry_delta),
        "shear_candidate_geometry_escalation_flag": int(geometry_escalation_flag),
        "shear_candidate_steel_delta": float(steel_delta),
        "shear_candidate_odd_leg_penalty": float(odd_leg_penalty),
        "shear_candidate_total_practicality_penalty": float(total_practicality_penalty),
        "shear_candidate_engineering_change": float(engineering_change),
    }


def resolve_auto_design_shallower_beam_metrics(
    candidate: dict[str, Any] | None,
    seed_candidate: dict[str, Any] | None,
) -> dict[str, float | bool]:
    """Resolve shallower-beam preference metrics from plain candidate data."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    seed_d = seed_candidate if isinstance(seed_candidate, dict) else {}
    candidate_state = dict(candidate_d.get("state") or {})
    seed_state = dict(seed_d.get("state") or {})
    seed_depth_default = _target_band_float(seed_state, "D", 0.0)
    candidate_depth_default = _target_band_float(candidate_state, "D", 0.0)
    seed_depth = float(seed_d.get("depth", seed_depth_default) or seed_depth_default)
    candidate_depth = float(candidate_d.get("depth", candidate_depth_default) or candidate_depth_default)
    _, _, seed_width_default = resolve_geometry_width_context(seed_state)
    _, _, candidate_width_default = resolve_geometry_width_context(candidate_state)
    seed_width = float(seed_d.get("width", seed_width_default) or seed_width_default)
    candidate_width = float(candidate_d.get("width", candidate_width_default) or candidate_width_default)
    seed_ast = float(seed_d.get("Ast_bot", 0.0) or 0.0)
    candidate_ast = float(candidate_d.get("Ast_bot", 0.0) or 0.0)
    depth_reduction = max(seed_depth - candidate_depth, 0.0)
    width_growth = max(candidate_width - seed_width, 0.0)
    reinforcement_growth = max(candidate_ast - seed_ast, 0.0)
    shallowness_score = depth_reduction - (0.45 * width_growth) - (0.04 * reinforcement_growth)
    materially_shallower = (
        depth_reduction >= 50.0
        or (
            depth_reduction >= 25.0
            and width_growth <= 50.0
            and reinforcement_growth <= 120.0
        )
    )
    return {
        "depth_reduction": float(depth_reduction),
        "width_growth": float(width_growth),
        "reinforcement_growth": float(reinforcement_growth),
        "shallowness_score": float(shallowness_score),
        "materially_shallower": bool(materially_shallower),
    }


def resolve_auto_design_band_reacher_delta_metrics(
    candidate: dict[str, Any] | None,
    current_state: dict[str, Any] | None,
) -> dict[str, float | int]:
    """Resolve band-reaching candidate delta metrics from plain state."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    cs = dict(candidate_d.get("state") or {})
    current = dict(current_state or {})
    d0 = float(_target_band_float(current, "D", 0.0) or 0.0)
    d1 = float(_target_band_float(cs, "D", d0) or d0)
    _, _, w0_raw = resolve_geometry_width_context(current)
    _, _, w1_raw = resolve_geometry_width_context(cs)
    w0 = float(w0_raw or 0.0)
    w1 = float(w1_raw or w0)
    ast0 = float(_target_band_float(current, "Ast_bot", 0.0) or 0.0)
    ast1 = float(candidate_d.get("Ast_bot", _target_band_float(cs, "Ast_bot", ast0)) or ast0)
    return {
        "result_depth": float(d1),
        "delta_d": float(max(d1 - d0, 0.0)),
        "delta_w": float(max(w1 - w0, 0.0)),
        "delta_ast": float(max(ast1 - ast0, 0.0)),
        "congestion": float(candidate_d.get("reo_congestion_index", 0.0) or 0.0),
        "row_pen": int(max(int(candidate_d.get("row_count", 1) or 1) - 2, 0)),
    }


def resolve_auto_design_band_reaching_candidate_goal_score(
    candidate: dict[str, Any] | None,
    goal: str | None,
    current_state: dict[str, Any] | None,
    *,
    target_mid: float,
) -> tuple[float, str]:
    """Resolve the goal-specific score for a candidate that reaches target band."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    deltas = resolve_auto_design_band_reacher_delta_metrics(candidate_d, current_state)
    d1 = float(deltas.get("result_depth", 0.0) or 0.0)
    delta_d = float(deltas.get("delta_d", 0.0) or 0.0)
    delta_w = float(deltas.get("delta_w", 0.0) or 0.0)
    delta_ast = float(deltas.get("delta_ast", 0.0) or 0.0)
    post_util = float(
        candidate_d.get(
            "candidate_post_util",
            resolve_auto_design_candidate_objective_util(candidate_d),
        )
        or 0.0
    )
    congestion = float(deltas.get("congestion", 0.0) or 0.0)
    row_pen = int(deltas.get("row_pen", 0) or 0)

    if str(goal or "") == "shallower_beam":
        score = (
            (delta_d * 2000.0)
            + (d1 * 0.6)
            + (delta_ast * 0.08)
            + (delta_w * 0.04)
            + (congestion * 20.0)
            + (row_pen * 8.0)
        )
        if (
            bool(candidate_d.get("recommendation_compound"))
            and str(candidate_d.get("compound_geo_axis") or "") == "width"
            and delta_d <= 1e-6
        ):
            score -= 30.0
        return float(score), "shallower_prefers_min_depth_then_steel_then_width"

    score = (
        (abs(post_util - float(target_mid)) * 90.0)
        + (delta_d * 0.3)
        + (delta_w * 0.25)
        + (delta_ast * 0.04)
        + (congestion * 18.0)
        + (row_pen * 8.0)
    )
    return float(score), "balanced_prefers_practical_low_congestion_near_target_mid"


def resolve_auto_design_shallower_beam_selection_key(
    candidate: dict[str, Any] | None,
    seed_candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    target_mid: float,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> tuple[Any, ...]:
    """Resolve the shallow-search selector key from plain candidate data."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    seed_d = seed_candidate if isinstance(seed_candidate, dict) else {}
    candidate_state = dict(candidate_d.get("state") or {})
    seed_state = dict(seed_d.get("state") or {})
    seed_depth_default = _target_band_float(seed_state, "D", 0.0)
    candidate_depth_default = _target_band_float(candidate_state, "D", 0.0)
    seed_depth = float(seed_d.get("depth", seed_depth_default) or seed_depth_default)
    cand_depth = float(candidate_d.get("depth", candidate_depth_default) or candidate_depth_default)
    _, _, seed_width_default = resolve_geometry_width_context(seed_state)
    _, _, candidate_width_default = resolve_geometry_width_context(candidate_state)
    seed_width = float(seed_d.get("width", seed_width_default) or seed_width_default)
    cand_width = float(candidate_d.get("width", candidate_width_default) or candidate_width_default)
    seed_ast = float(seed_d.get("Ast_bot", 0.0) or 0.0)
    cand_ast = float(candidate_d.get("Ast_bot", 0.0) or 0.0)
    delta_d_mm = max(cand_depth - seed_depth, 0.0)
    delta_b_mm = max(cand_width - seed_width, 0.0)
    delta_ast_bot = max(cand_ast - seed_ast, 0.0)
    is_geometry = bool(candidate_d.get("recommendation_geometry_trial"))
    in_band = 0 if resolve_candidate_in_target_band(
        candidate_d,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    ) else 1
    congestion = float(candidate_d.get("reo_congestion_index", 0.0) or 0.0)
    util = resolve_auto_design_candidate_objective_util(
        candidate_d,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except (TypeError, ValueError):
        target_min = float(default_target_min)
        target_max = float(default_target_max)
    if util < target_min:
        util_gap = target_min - util
    elif util > target_max:
        util_gap = util - target_max
    else:
        util_gap = abs(util - float(target_mid))
    return (
        0 if bool(candidate_d.get("is_compliant")) else 1,
        in_band,
        delta_d_mm,
        0 if not is_geometry else 1,
        delta_b_mm,
        delta_ast_bot,
        congestion,
        round(float(candidate_d.get("score", float("inf")) or float("inf")), 4),
        float(util_gap),
        float(candidate_d.get("worst_util", float("inf")) or float("inf")),
    )


def resolve_distance_to_target_band(util: Any, target_min: Any, target_max: Any) -> float:
    """Return absolute distance from a utilisation value to a target band."""

    try:
        u = float(util)
        lo = float(target_min)
        hi = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if lo <= u <= hi:
        return 0.0
    if u < lo:
        return lo - u
    return u - hi


def resolve_candidate_target_domains_for_band(candidate: dict[str, Any] | None) -> list[str]:
    """Return normalized target-band domains for a candidate."""

    if not isinstance(candidate, dict):
        return []
    raw = candidate.get("target_domains_for_band")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        domain = str(item or "").strip().lower()
        if domain in ("flexure", "ductility", "bottom", "bottom_reo"):
            domain = "bending"
        if domain not in ("bending", "shear"):
            continue
        if domain not in seen:
            out.append(domain)
            seen.add(domain)
    return out


def resolve_candidate_domain_util(candidate: dict[str, Any] | None, domain: str) -> float | None:
    """Resolve candidate utilisation for a target-band domain."""

    candidate_d = candidate if isinstance(candidate, dict) else {}
    resolved_domain = str(domain or "").strip().lower()
    if resolved_domain == "bending":
        demand_util = resolve_candidate_bending_demand_util(candidate_d)
        if demand_util is not None:
            try:
                value = float(demand_util)
                if math.isfinite(value):
                    return value
            except Exception:
                pass
        raw = ((candidate_d.get("overview") or {}).get("utils") or {}).get("bending")
        try:
            value = float(raw)
            if math.isfinite(value):
                return value
        except Exception:
            return None
        return None
    if resolved_domain == "shear":
        raw = ((candidate_d.get("overview") or {}).get("utils") or {}).get("shear")
        try:
            value = float(raw)
            if math.isfinite(value):
                return value
        except Exception:
            return None
        return None
    return None


def resolve_candidate_domain_score(
    eval_obj: dict[str, Any] | None,
    domain: str,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
) -> dict[str, Any]:
    """Build the target-band score for a single candidate domain."""

    resolved_domain = str(domain or "").strip().lower()
    overview = dict((eval_obj or {}).get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    status = statuses.get(resolved_domain)
    util = resolve_candidate_domain_util(eval_obj or {}, resolved_domain)

    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except Exception:
        target_min = float(default_target_min)
        target_max = float(default_target_max)

    resolved_util = None
    if util is not None:
        try:
            candidate_util = float(util)
            if math.isfinite(candidate_util):
                resolved_util = candidate_util
        except Exception:
            resolved_util = None

    fail = bool(status == fail_status or str(status or "").strip().upper() == "FAIL")
    ok_status = not fail
    distance = (
        float("inf")
        if resolved_util is None
        else resolve_distance_to_target_band(resolved_util, target_min, target_max)
    )

    return {
        "domain": resolved_domain,
        "status": status,
        "util": resolved_util,
        "distance": distance,
        "in_band": bool(resolved_util is not None and target_min <= resolved_util <= target_max and ok_status),
        "pass": bool(ok_status),
        "under": bool(resolved_util is not None and resolved_util < target_min),
        "over": bool(resolved_util is not None and resolved_util > target_max),
    }


def resolve_candidate_eval_domain_scores(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
) -> dict[str, dict[str, Any]]:
    """Build target-band scores for every candidate target domain."""

    return {
        domain: resolve_candidate_domain_score(
            eval_obj,
            domain,
            mode_config,
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
        )
        for domain in resolve_candidate_target_domains_for_band(eval_obj or {})
    }


def resolve_candidate_required_domain_progress(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Summarize required target-domain progress for candidate ranking."""

    scores = resolve_candidate_eval_domain_scores(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )
    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
        target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
    except (TypeError, ValueError, KeyError):
        target_min = float(default_target_min)
        target_max = float(default_target_max)

    if not scores:
        util = resolve_auto_design_candidate_objective_util(
            eval_obj or {},
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        try:
            util = float(util)
        except (TypeError, ValueError):
            util = None
        overview = dict((eval_obj or {}).get("overview") or {})
        statuses = dict(overview.get("statuses") or {})
        all_key_pass = bool(overview.get("all_key_pass"))
        any_fail = any(
            status == fail_status or str(status or "").strip().upper() == "FAIL"
            for status in statuses.values()
        )
        ok_status = bool(all_key_pass and not any_fail)
        in_band = bool(
            util is not None
            and math.isfinite(float(util))
            and target_min <= float(util) <= target_max
            and ok_status
        )
        distance = (
            float("inf")
            if util is None or not math.isfinite(float(util))
            else resolve_distance_to_target_band(float(util), target_min, target_max)
        )
        return {
            "scores": {},
            "required_domain_count": 0,
            "required_fail_count": 0 if ok_status else 1,
            "required_unsatisfied_count": 0 if in_band else 1,
            "required_satisfied_count": 1 if in_band else 0,
            "required_fail_domains": [] if ok_status else ["objective"],
            "required_unsatisfied_domains": [] if in_band else ["objective"],
            "required_satisfied_domains": ["objective"] if in_band else [],
            "domain_total_distance": float(distance),
            "domain_max_distance": float(distance),
        }

    fail_domains: list[str] = []
    unsatisfied_domains: list[str] = []
    satisfied_domains: list[str] = []
    total = 0.0
    max_distance = float("-inf")

    for domain, score in scores.items():
        if not bool(score.get("pass")):
            fail_domains.append(domain)
        if bool(score.get("pass")) and bool(score.get("in_band")):
            satisfied_domains.append(domain)
        else:
            unsatisfied_domains.append(domain)
        dist = score.get("distance")
        if dist is None or not math.isfinite(float(dist)):
            total = float("inf")
            max_distance = float("inf")
            continue
        fd = float(dist)
        if not math.isfinite(total):
            continue
        total += fd
        max_distance = max(max_distance, fd)

    if max_distance == float("-inf"):
        max_distance = float("inf")

    return {
        "scores": scores,
        "required_domain_count": len(scores),
        "required_fail_count": len(fail_domains),
        "required_unsatisfied_count": len(unsatisfied_domains),
        "required_satisfied_count": len(satisfied_domains),
        "required_fail_domains": fail_domains,
        "required_unsatisfied_domains": unsatisfied_domains,
        "required_satisfied_domains": satisfied_domains,
        "domain_total_distance": float(total),
        "domain_max_distance": float(max_distance),
    }


def resolve_candidate_domain_total_distance(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Return total target-band distance for required candidate domains."""

    progress = resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    return float(progress.get("domain_total_distance", float("inf")))


def resolve_candidate_domain_max_distance(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Return maximum target-band distance for required candidate domains."""

    progress = resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    return float(progress.get("domain_max_distance", float("inf")))


def resolve_candidate_required_domains_satisfied(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    """Return whether required target domains are satisfied."""

    if not isinstance(eval_obj, dict):
        return False
    progress = resolve_candidate_required_domain_progress(
        eval_obj,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    return int(progress.get("required_unsatisfied_count", 0) or 0) == 0


def resolve_candidate_in_target_band(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    """Return whether a candidate satisfies its target-band requirement."""

    if not isinstance(candidate, dict):
        return False
    return resolve_candidate_required_domains_satisfied(
        candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )


def resolve_candidate_target_band_distance(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Return the ranking distance to target band for a candidate."""

    domains = resolve_candidate_target_domains_for_band(candidate)
    if not domains:
        util = resolve_auto_design_candidate_objective_util(
            candidate,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        mode = dict(mode_config or {})
        try:
            target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
            target_max = float(mode.get("target_util_max", default_target_max) or default_target_max)
        except Exception:
            target_min = float(default_target_min)
            target_max = float(default_target_max)
        return resolve_distance_to_target_band(util, target_min, target_max)
    return resolve_candidate_domain_max_distance(
        candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )


def resolve_candidate_target_band_total_distance(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> float:
    """Return total target-band distance for candidate ranking."""

    return resolve_candidate_domain_total_distance(
        candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )


def resolve_candidate_target_domain_needing_work(
    candidate: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> str:
    """Return the target-band domain most in need of work."""

    domains = resolve_candidate_target_domains_for_band(candidate)
    if not domains:
        return ""
    scored: list[tuple[int, float, int, str]] = []
    for domain in domains:
        domain_text = str(domain or "").strip().lower()
        score = resolve_candidate_domain_score(
            candidate,
            domain_text,
            mode_config,
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
        )
        if bool(score.get("in_band")):
            continue
        try:
            dist = float(score.get("distance"))
        except (TypeError, ValueError):
            dist = float("inf")
        if not math.isfinite(dist):
            dist = float("inf")
        status_weight = 1 if not bool(score.get("pass")) else 0
        order_weight = 1 if domain_text == "shear" else 0
        scored.append((status_weight, dist, order_weight, domain_text))
    if scored:
        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return str(scored[0][3])
    return ""


def resolve_target_band_eval_domain_attachment(
    eval_obj: dict[str, Any] | None,
    target_domains_for_band: list[str] | tuple[str, ...] | set[str] | None,
    mode_config: dict[str, Any] | None,
    *,
    bending_demand_negligible: bool = False,
    shear_demand_negligible: bool = False,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Resolve demand-aware target-domain attachment for an evaluated candidate."""

    if not isinstance(eval_obj, dict):
        return {"target_domains_for_band": [], "target_domain_for_band": None, "clear": True}
    raw_domains = [
        domain
        for domain in ("bending", "shear")
        if domain in {str(item or "").strip().lower() for item in (target_domains_for_band or [])}
    ]
    overview = dict(eval_obj.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})

    def domain_relevant(domain: str) -> bool:
        status = str(statuses.get(domain) or "").strip().upper()
        if status == str(fail_status).strip().upper():
            return True
        if domain == "shear":
            return not bool(shear_demand_negligible)
        if domain == "bending":
            return not bool(bending_demand_negligible)
        return True

    domains = [domain for domain in raw_domains if domain_relevant(domain)]
    if not domains:
        return {"target_domains_for_band": [], "target_domain_for_band": None, "clear": True}
    candidate = dict(eval_obj)
    candidate["target_domains_for_band"] = list(domains)
    work_domain = resolve_candidate_target_domain_needing_work(
        candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    return {
        "target_domains_for_band": list(domains),
        "target_domain_for_band": str(work_domain or "") or None,
        "clear": False,
    }


def resolve_candidate_step_improves(
    new_eval: dict[str, Any] | None,
    old_eval: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    """Return whether a candidate step improves target-band progress."""

    old_candidate = old_eval if isinstance(old_eval, dict) else {}
    new_candidate = new_eval if isinstance(new_eval, dict) else {}
    old_pass = bool((old_candidate.get("overview") or {}).get("all_key_pass"))
    new_pass = bool((new_candidate.get("overview") or {}).get("all_key_pass"))
    old_ib = resolve_candidate_in_target_band(
        old_candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    new_ib = resolve_candidate_in_target_band(
        new_candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    old_u = resolve_auto_design_candidate_objective_util(
        old_candidate,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    new_u = resolve_auto_design_candidate_objective_util(
        new_candidate,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    old_d = resolve_candidate_target_band_distance(
        old_candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    new_d = resolve_candidate_target_band_distance(
        new_candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if resolve_candidate_target_domains_for_band(old_candidate) or resolve_candidate_target_domains_for_band(new_candidate):
        old_progress = resolve_candidate_required_domain_progress(
            old_candidate,
            mode_config,
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        new_progress = resolve_candidate_required_domain_progress(
            new_candidate,
            mode_config,
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        old_fail = int(old_progress.get("required_fail_count", 0) or 0)
        new_fail = int(new_progress.get("required_fail_count", 0) or 0)
        old_unsatisfied = int(old_progress.get("required_unsatisfied_count", 0) or 0)
        new_unsatisfied = int(new_progress.get("required_unsatisfied_count", 0) or 0)
        old_max = float(old_progress.get("domain_max_distance", float("inf")))
        new_max = float(new_progress.get("domain_max_distance", float("inf")))
        old_total = float(old_progress.get("domain_total_distance", float("inf")))
        new_total = float(new_progress.get("domain_total_distance", float("inf")))
        if new_ib and not old_ib and new_pass:
            return True
        if new_fail < old_fail:
            return True
        if new_unsatisfied < old_unsatisfied:
            return True
        if new_pass and not old_pass:
            max_not_worse = (
                math.isfinite(old_max)
                and math.isfinite(new_max)
                and new_max <= old_max + 1e-6
            )
            total_improved = (
                math.isfinite(old_total)
                and math.isfinite(new_total)
                and new_total < old_total - 1e-6
            )
            return bool(max_not_worse or total_improved)
        if new_max < old_max - 1e-6:
            return True
        if new_max <= old_max + 1e-6 and new_total < old_total - 1e-6:
            return True
        return False
    old_total = resolve_candidate_target_band_total_distance(
        old_candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    new_total = resolve_candidate_target_band_total_distance(
        new_candidate,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if new_pass and not old_pass:
        return True
    if new_ib and not old_ib and new_pass:
        return True
    if new_d < old_d - 1e-6:
        return True
    if new_d <= old_d + 1e-6 and new_total < old_total - 1e-6:
        return True
    mode = dict(mode_config or {})
    lo = float(mode.get("target_util_min", default_target_min) or default_target_min)
    hi = float(mode.get("target_util_max", default_target_max) or default_target_max)
    if old_u < lo and new_u > old_u + 1e-9 and new_pass == old_pass:
        return True
    if old_u > hi and new_u < old_u - 1e-9 and new_pass == old_pass:
        return True
    return False


def resolve_candidate_mixed_direction_rank_adjustment(
    cur_eval: dict[str, Any] | None,
    candidate_eval: dict[str, Any] | None,
    mixed_mode: str | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    primary_improvement_margin: float = 0.02,
) -> dict[str, Any]:
    """Build the mixed-direction target-band ranking overlay."""

    if mixed_mode == "bending_under_shear_over":
        primary_domain = "bending"
        secondary_domain = "shear"
    elif mixed_mode == "bending_over_shear_under":
        primary_domain = "shear"
        secondary_domain = "bending"
    else:
        return {
            "active": False,
            "mixed_mode": None,
            "primary_domain": None,
            "secondary_domain": None,
            "primary_material_improvement": False,
            "primary_distance": float("inf"),
            "secondary_distance": float("inf"),
            "current_secondary_distance": float("inf"),
        }

    current_primary = resolve_candidate_domain_score(
        cur_eval,
        primary_domain,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )
    candidate_primary = resolve_candidate_domain_score(
        candidate_eval,
        primary_domain,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )
    current_secondary = resolve_candidate_domain_score(
        cur_eval,
        secondary_domain,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )
    candidate_secondary = resolve_candidate_domain_score(
        candidate_eval,
        secondary_domain,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )

    current_primary_pass = bool(current_primary.get("pass"))
    candidate_primary_pass = bool(candidate_primary.get("pass"))
    current_primary_distance = float(current_primary.get("distance", float("inf")) or float("inf"))
    candidate_primary_distance = float(candidate_primary.get("distance", float("inf")) or float("inf"))
    current_secondary_distance = float(current_secondary.get("distance", float("inf")) or float("inf"))
    candidate_secondary_distance = float(candidate_secondary.get("distance", float("inf")) or float("inf"))
    margin = float(max(0.0, primary_improvement_margin))

    primary_material_improvement = bool(
        (candidate_primary_pass and not current_primary_pass)
        or (
            math.isfinite(current_primary_distance)
            and math.isfinite(candidate_primary_distance)
            and candidate_primary_distance <= (current_primary_distance - margin)
        )
    )

    return {
        "active": True,
        "mixed_mode": mixed_mode,
        "primary_domain": primary_domain,
        "secondary_domain": secondary_domain,
        "primary_material_improvement": primary_material_improvement,
        "primary_distance": candidate_primary_distance,
        "secondary_distance": candidate_secondary_distance if primary_material_improvement else current_secondary_distance,
        "current_secondary_distance": current_secondary_distance,
    }


def resolve_candidate_mixed_direction_classification(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    shear_demand_meaningful: bool,
    bending_demand_meaningful: bool,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    overdesign_margin: float = 0.03,
) -> str | None:
    """Classify mixed-direction target-band states from plain demand flags."""

    bending = resolve_candidate_domain_score(
        eval_obj,
        "bending",
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )
    shear = resolve_candidate_domain_score(
        eval_obj,
        "shear",
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
    )
    mode = dict(mode_config or {})
    try:
        target_min = float(mode.get("target_util_min", default_target_min) or default_target_min)
    except Exception:
        target_min = float(default_target_min)
    margin = float(max(0.0, overdesign_margin))

    def materially_over(score: dict[str, Any]) -> bool:
        util = score.get("util")
        try:
            resolved_util = float(util)
        except (TypeError, ValueError):
            return False
        return bool(score.get("pass") and resolved_util < (target_min - margin))

    if (
        (not bool(bending.get("pass")))
        and materially_over(shear)
        and bool(shear_demand_meaningful)
    ):
        return "bending_under_shear_over"
    if (
        (not bool(shear.get("pass")))
        and materially_over(bending)
        and bool(bending_demand_meaningful)
    ):
        return "bending_over_shear_under"
    return None


def resolve_target_band_candidate_sort_key(
    *,
    tier: int,
    mixed_sort_prefix: tuple[Any, ...] = (),
    tightening_mode_active: bool,
    governing_domain: str,
    has_target_domains: bool,
    new_max: Any = None,
    new_total: Any = None,
    required_fail_count: int = 0,
    required_unsatisfied_count: int = 0,
    prefer_total_before_max: bool = False,
    shear_sort_util: Any = float("inf"),
    web_sort_util: Any = float("inf"),
    practical_spacing_penalty: int = 0,
    congestion_penalty: int = 0,
    goal_bias: int = 0,
    new_distance: Any = float("inf"),
    wrong_dir_penalty: Any = 0.0,
    directional_tie_key: Any = 0.0,
    reduction_bias: int = 0,
    update_count: int = 0,
) -> tuple[Any, ...]:
    """Build the target-band candidate ranking tuple from plain scoring inputs."""

    prefix = tuple(mixed_sort_prefix or ())
    if bool(tightening_mode_active):
        if str(governing_domain or "").strip().lower() == "shear":
            if bool(has_target_domains) and new_total is not None:
                return (
                    tier,
                    *prefix,
                    int(required_fail_count),
                    int(required_unsatisfied_count),
                    float(new_max),
                    float(new_total),
                    float(shear_sort_util),
                    float(web_sort_util),
                    int(practical_spacing_penalty),
                    int(congestion_penalty),
                    int(goal_bias),
                    float(wrong_dir_penalty),
                    int(reduction_bias),
                    int(update_count),
                )
            return (
                tier,
                *prefix,
                float(shear_sort_util),
                float(web_sort_util),
                int(practical_spacing_penalty),
                int(congestion_penalty),
                int(goal_bias),
                float(new_distance),
                float(wrong_dir_penalty),
                int(reduction_bias),
                int(update_count),
            )
        if bool(has_target_domains) and new_total is not None:
            if bool(prefer_total_before_max):
                return (
                    tier,
                    *prefix,
                    int(required_fail_count),
                    int(required_unsatisfied_count),
                    float(new_total),
                    float(new_max),
                    float(wrong_dir_penalty),
                    int(reduction_bias),
                    int(update_count),
                )
            return (
                tier,
                *prefix,
                int(required_fail_count),
                int(required_unsatisfied_count),
                float(new_max),
                float(new_total),
                float(wrong_dir_penalty),
                int(reduction_bias),
                int(update_count),
            )
        return (
            tier,
            *prefix,
            float(new_distance),
            float(wrong_dir_penalty),
            int(reduction_bias),
            int(update_count),
        )

    if bool(has_target_domains) and new_max is not None and new_total is not None:
        if bool(prefer_total_before_max):
            return (
                tier,
                *prefix,
                int(required_fail_count),
                int(required_unsatisfied_count),
                float(new_total),
                float(new_max),
                float(directional_tie_key),
                int(update_count),
            )
        return (
            tier,
            *prefix,
            int(required_fail_count),
            int(required_unsatisfied_count),
            float(new_max),
            float(new_total),
            float(directional_tie_key),
            int(update_count),
        )
    return (
        tier,
        *prefix,
        float(new_distance),
        float(directional_tie_key),
        int(update_count),
    )


def select_target_band_ranked_candidate(scored_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    """Select the lexicographic best target-band candidate from plain scored rows."""

    rows = [dict(row) for row in list(scored_candidates or []) if isinstance(row, dict)]
    if not rows:
        return None
    return min(rows, key=lambda row: row.get("sort_key"))


def select_probe_equivalent_bending_cleanup_candidate(
    safe_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    final_accepted_min_family_util: int | float,
    target_low: int | float,
    target_high: int | float,
) -> dict[str, Any] | None:
    """Select the best safe probe-equivalent bending cleanup row."""

    rows = [dict(row) for row in list(safe_rows or []) if isinstance(row, dict)]
    if not rows:
        return None
    final_floor = float(final_accepted_min_family_util)
    target_low_f = float(target_low)
    target_high_f = float(target_high)
    selected = min(
        rows,
        key=lambda row: (
            0 if final_floor <= float(row.get("preview_util")) <= 1.0 else 1,
            0 if target_low_f <= float(row.get("preview_util")) <= target_high_f else 1,
            abs(final_floor - float(row.get("preview_util"))),
            len(dict(row.get("updates") or {})),
            str(row.get("candidate_id") or ""),
        ),
    )
    return dict(selected)


def select_zero_bending_demand_cleanup_candidate(
    safe_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    current_material_proxy: int | float,
) -> dict[str, Any] | None:
    """Select the smallest safe zero-bending-demand cleanup candidate."""

    rows = [dict(row) for row in list(safe_candidates or []) if isinstance(row, dict)]
    if not rows:
        return None
    current_proxy = float(current_material_proxy)
    selected = min(
        rows,
        key=lambda candidate: (
            float(candidate.get("candidate_material_proxy") or current_proxy),
            len(dict(candidate.get("updates") or {})),
            str(candidate.get("candidate_id") or ""),
        ),
    )
    return dict(selected)


def build_zero_bending_demand_evaluated_candidate_row(
    candidate: dict[str, Any],
    *,
    candidate_overview: dict[str, Any] | None,
    updates: dict[str, Any],
    width: int | float,
    depth: int | float,
    bars: int,
    dia: int,
    candidate_index: int,
    candidate_material_proxy: int | float,
    preview_statuses_have_explicit_fail: bool,
    geometry_update_keys: set[str] | frozenset[str] | tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Shape a zero-bending cleanup evaluated candidate row without page dependencies."""

    cand = dict(candidate or {})
    overview = dict(candidate_overview or {})
    statuses_after = dict(overview.get("statuses") or {})
    del statuses_after
    safe = bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    if safe and bool(preview_statuses_have_explicit_fail):
        safe = False
    utils_after = dict(overview.get("utils") or {})
    candidate_id = f"zero_bending_cleanup_{int(candidate_index):03d}"
    geometry_keys = set(geometry_update_keys or {"D", "b", "bw"})
    candidate_util = _repair_parse_util_value(
        overview.get("worst_util")
        or overview.get("governing_util")
        or utils_after.get("bending")
        or 0.0
    )
    cand.update(
        {
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "title": f"Zero bending cleanup - {int(width)}x{int(depth)} {int(bars)}N{int(dia)}",
            "label": f"Zero bending cleanup - {int(width)}x{int(depth)} {int(bars)}N{int(dia)}",
            "updates": dict(updates or {}),
            "proposed_updates": dict(updates or {}),
            "family": "bending",
            "recommendation_family_tag": "bending",
            "subfamilies": ["geometry", "bottom_reinforcement"]
            if geometry_keys & set(dict(updates or {}))
            else ["bottom_reinforcement"],
            "action_type": "apply_resolved_candidate",
            "is_compliant": bool(safe),
            "preview_pass": bool(safe),
            "is_executable": bool(safe),
            "safe_executor_backed": bool(safe),
            "candidate_material_proxy": float(candidate_material_proxy),
            "candidate_post_util": candidate_util,
            "preview_util": candidate_util,
            "zero_bending_demand_cleanup": True,
        }
    )
    if not safe:
        cand["rejection_reason"] = "candidate_does_not_keep_all_required_checks_pass"
    return cand


def build_probe_equivalent_bending_evaluated_candidate_row(
    row: dict[str, Any],
    *,
    candidate_overview: dict[str, Any] | None,
    current_bending_util: int | float | None,
) -> dict[str, Any]:
    """Shape a probe-equivalent bending evaluated row without page dependencies."""

    out = dict(row or {})
    overview = dict(candidate_overview or {})
    candidate_bending = _repair_parse_util_value(dict(overview.get("utils") or {}).get("bending"))
    all_pass = bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    current = _repair_parse_util_value(current_bending_util)
    safe_executor_backed = bool(
        all_pass
        and candidate_bending is not None
        and current is not None
        and float(candidate_bending) > float(current) + 1e-6
    )
    out.update(
        {
            "overview": dict(overview),
            "candidate_post_util": candidate_bending,
            "preview_util": candidate_bending,
            "worst_util": overview.get("worst_util", candidate_bending),
            "is_compliant": bool(all_pass),
            "safe_executor_backed": bool(safe_executor_backed),
        }
    )
    if not out["safe_executor_backed"]:
        out["rejection_reason"] = (
            "candidate_does_not_keep_all_required_checks_pass"
            if not all_pass
            else "candidate_does_not_improve_bending_utilisation"
        )
    return out


def select_bending_only_best_safe_partial_cleanup_candidate(
    safe_partial_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    final_accepted_min_family_util: int | float,
) -> dict[str, Any] | None:
    """Select the best safe incremental bending-only cleanup below the final floor."""

    rows = [dict(row) for row in list(safe_partial_candidates or []) if isinstance(row, dict)]
    if not rows:
        return None
    final_floor = float(final_accepted_min_family_util)
    selected = min(
        rows,
        key=lambda candidate: (
            abs(final_floor - float(candidate.get("candidate_bending_util") or 0.0)),
            abs(float(candidate.get("candidate_post_util") or 0.0) - final_floor),
            len(dict(candidate.get("updates") or {})),
            str(candidate.get("candidate_id") or ""),
        ),
    )
    return dict(selected)


def select_bending_only_target_band_cleanup_candidate(
    target_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    target_low: int | float,
    target_high: int | float,
) -> dict[str, Any] | None:
    """Select the bending-only candidate closest to the target band midpoint."""

    rows = [dict(row) for row in list(target_candidates or []) if isinstance(row, dict)]
    if not rows:
        return None
    target_mid = (float(target_low) + float(target_high)) / 2.0
    selected = min(
        rows,
        key=lambda candidate: (
            abs(float(candidate.get("candidate_bending_util") or 0.0) - target_mid),
            abs(float(candidate.get("candidate_post_util") or 0.0) - target_mid),
            len(dict(candidate.get("updates") or {})),
            str(candidate.get("candidate_id") or ""),
        ),
    )
    return dict(selected)


def resolve_target_band_selected_candidate_acceptance(
    *,
    candidate_improves: bool,
    allow_in_band_shear_cleanup_candidate: bool = False,
) -> dict[str, Any]:
    """Resolve whether the ranked target-band candidate should be accepted."""

    accepted = bool(candidate_improves) or bool(allow_in_band_shear_cleanup_candidate)
    if accepted:
        return {
            "accepted": True,
            "stop_reason": None,
            "reason_code": "ranked_candidate_improves",
        }
    return {
        "accepted": False,
        "stop_reason": "no_improving_candidate",
        "reason_code": "ranked_candidate_no_improvement",
    }


def resolve_target_band_exhaustion_refinement_allowed(
    current_eval: dict[str, Any] | None,
    next_hop_payload: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> bool:
    """Return whether an exhaustion fallback refinement candidate may be injected."""

    if not isinstance(current_eval, dict) or not isinstance(next_hop_payload, dict):
        return False
    if not bool((current_eval.get("overview") or {}).get("all_key_pass")):
        return False
    current_domains = list(resolve_candidate_target_domains_for_band(current_eval) or [])
    if len(current_domains) < 2:
        return False
    current_progress = resolve_candidate_required_domain_progress(
        current_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if int(current_progress.get("required_fail_count", 0) or 0) != 0:
        return False
    if int(current_progress.get("required_unsatisfied_count", 0) or 0) <= 1:
        return False
    candidate_eval = next_hop_payload.get("eval")
    if not isinstance(candidate_eval, dict):
        return False
    if not bool((candidate_eval.get("overview") or {}).get("all_key_pass")):
        return False
    candidate_progress = resolve_candidate_required_domain_progress(
        candidate_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if int(candidate_progress.get("required_fail_count", 0) or 0) != 0:
        return False
    if int(candidate_progress.get("required_unsatisfied_count", 0) or 0) > int(
        current_progress.get("required_unsatisfied_count", 0) or 0
    ):
        return False
    current_max = float(current_progress.get("domain_max_distance", float("inf")))
    candidate_max = float(candidate_progress.get("domain_max_distance", float("inf")))
    current_total = float(current_progress.get("domain_total_distance", float("inf")))
    candidate_total = float(candidate_progress.get("domain_total_distance", float("inf")))
    if not (
        math.isfinite(current_max)
        and math.isfinite(candidate_max)
        and math.isfinite(current_total)
        and math.isfinite(candidate_total)
    ):
        return False
    if candidate_max > current_max + 1e-6:
        return False
    if candidate_total >= current_total - 1e-6:
        return False
    return resolve_candidate_step_improves(
        candidate_eval,
        current_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )


def build_target_band_fallback_scored_candidate(
    *,
    next_hop_payload: dict[str, Any] | None,
    updates: dict[str, Any] | None,
    signature: Any = None,
    label: str = "Fallback multi-domain cleanup",
    action_type: str = "fallback_next_hop_cleanup",
) -> dict[str, Any] | None:
    """Build the scored-row shape for an approved target-band fallback candidate."""

    if not isinstance(next_hop_payload, dict):
        return None
    update_payload = dict(updates or {})
    if not update_payload:
        return None
    candidate_eval = dict(next_hop_payload.get("eval") or {})
    if not candidate_eval:
        return None
    overview = dict(candidate_eval.get("overview") or {})
    return {
        "sort_key": (-1,),
        "eval": candidate_eval,
        "updates": update_payload,
        "label": str(label or "Fallback multi-domain cleanup"),
        "action_type": str(action_type or "fallback_next_hop_cleanup"),
        "signature": signature,
        "change_summary": None,
        "worst_util": float(overview.get("worst_util", 0.0) or 0.0),
    }


def resolve_target_band_next_hop_precheck(
    current_eval: dict[str, Any] | None,
    mode_config: dict[str, Any] | None,
    *,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Resolve pure preconditions before generating fallback refinement candidates."""

    if not isinstance(current_eval, dict):
        return {"allowed": False, "reason": "missing_current_eval", "overview": {}, "current_distance": None, "current_state": {}}
    overview = dict((current_eval.get("overview") or {}))
    if not bool(overview.get("all_key_pass")):
        return {"allowed": False, "reason": "current_not_all_pass", "overview": overview, "current_distance": None, "current_state": {}}
    try:
        lo = float((mode_config or {}).get("target_util_min", default_target_min) or default_target_min)
        hi = float((mode_config or {}).get("target_util_max", default_target_max) or default_target_max)
    except Exception:
        lo = float(default_target_min)
        hi = float(default_target_max)
    try:
        worst = float(overview.get("governing_util", overview.get("worst_util", 0.0)) or 0.0)
    except (TypeError, ValueError):
        worst = None
    statuses = dict(overview.get("statuses") or {})
    any_fail = any(
        value == fail_status or str(value or "").strip().upper() == str(fail_status).strip().upper()
        for value in statuses.values()
    )
    if worst is not None and not any_fail and lo <= float(worst) <= hi:
        return {"allowed": False, "reason": "already_in_strict_target_band", "overview": overview, "current_distance": None, "current_state": {}}
    current_distance = resolve_candidate_target_band_distance(
        current_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    if current_distance is None or not math.isfinite(float(current_distance)):
        return {"allowed": False, "reason": "non_finite_current_distance", "overview": overview, "current_distance": current_distance, "current_state": {}}
    current_state = dict(current_eval.get("state") or {})
    if not current_state:
        return {"allowed": False, "reason": "missing_current_state", "overview": overview, "current_distance": current_distance, "current_state": {}}
    return {
        "allowed": True,
        "reason": "allowed",
        "overview": overview,
        "current_distance": float(current_distance),
        "current_state": current_state,
    }


def build_target_band_refinement_payload_if_valid(
    *,
    candidate_state: dict[str, Any] | None,
    candidate_eval: dict[str, Any] | None,
    candidate_updates: dict[str, Any] | None,
    current_eval: dict[str, Any] | None,
    current_distance: Any,
    mode_config: dict[str, Any] | None,
    spacing_envelope_fail: bool = False,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
    improvement_margin: float = 1e-9,
) -> dict[str, Any] | None:
    """Build a target-band refinement payload after pure validity screening."""

    if not isinstance(candidate_eval, dict):
        return None
    overview = dict(candidate_eval.get("overview") or {})
    if not bool(overview.get("all_key_pass")):
        return None
    if bool(spacing_envelope_fail):
        return None
    candidate_distance = resolve_candidate_target_band_distance(
        candidate_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    )
    try:
        resolved_candidate_distance = float(candidate_distance)
        resolved_current_distance = float(current_distance)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(resolved_candidate_distance):
        return None
    if resolved_candidate_distance + float(improvement_margin) >= resolved_current_distance:
        return None
    if not resolve_candidate_step_improves(
        candidate_eval,
        current_eval,
        mode_config,
        default_target_min=default_target_min,
        default_target_max=default_target_max,
        fail_status=fail_status,
        optimisation_goal_resolver=optimisation_goal_resolver,
    ):
        return None
    return {
        "state": dict(candidate_state or {}),
        "eval": candidate_eval,
        "distance": resolved_candidate_distance,
        "updates": dict(candidate_updates or {}),
    }


def select_best_target_band_refinement_candidate(
    *,
    candidate_states: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    current_eval: dict[str, Any] | None,
    current_state: dict[str, Any] | None,
    current_distance: Any,
    current_target_domains: list[str] | tuple[str, ...] | set[str] | None,
    mode_config: dict[str, Any] | None,
    state_pack_fn: Callable[[dict[str, Any]], dict[str, Any]],
    evaluator_fn: Callable[..., dict[str, Any] | None],
    target_domain_attachment_fn: Callable[[dict[str, Any], list[str], dict[str, Any] | None], None],
    spacing_envelope_fail_fn: Callable[[dict[str, Any]], bool],
    source: str,
    label: str,
    action_type: str,
    default_target_min: float,
    default_target_max: float,
    fail_status: str = "FAIL",
    optimisation_goal_resolver: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any] | None:
    """Evaluate generated refinement states and select the best valid payload."""

    best_payload: dict[str, Any] | None = None
    base_state = dict(current_state or {})
    base_domains = list(current_target_domains or [])
    for candidate_state_raw in list(candidate_states or []):
        candidate_state = dict(candidate_state_raw or {})
        candidate_eval = evaluator_fn(
            state_pack_fn(candidate_state),
            source=source,
            label=label,
            action_type=action_type,
            updates={},
        )
        if not isinstance(candidate_eval, dict):
            continue
        candidate_updates = diff_candidate_state_updates(base_state, candidate_state)
        if base_domains:
            candidate_target_domains = resolve_target_band_candidate_domains_for_updates(
                base_domains,
                candidate_updates,
            )
            target_domain_attachment_fn(candidate_eval, candidate_target_domains, mode_config)
        payload = build_target_band_refinement_payload_if_valid(
            candidate_state=candidate_state,
            candidate_eval=candidate_eval,
            candidate_updates=candidate_updates,
            current_eval=current_eval,
            current_distance=current_distance,
            mode_config=mode_config,
            spacing_envelope_fail=bool(spacing_envelope_fail_fn(candidate_eval)),
            default_target_min=default_target_min,
            default_target_max=default_target_max,
            fail_status=fail_status,
            optimisation_goal_resolver=optimisation_goal_resolver,
        )
        if payload is None:
            continue
        best_payload = select_target_band_best_refinement_payload(best_payload, payload)
    return best_payload


def select_target_band_best_refinement_payload(
    current_best: dict[str, Any] | None,
    candidate_payload: dict[str, Any] | None,
    *,
    improvement_margin: float = 1e-9,
) -> dict[str, Any] | None:
    """Select the lower-distance refinement payload from plain candidate payloads."""

    if not isinstance(candidate_payload, dict):
        return dict(current_best) if isinstance(current_best, dict) else None
    if not isinstance(current_best, dict):
        return dict(candidate_payload)
    try:
        candidate_distance = float(candidate_payload.get("distance"))
        current_distance = float(current_best.get("distance"))
    except (TypeError, ValueError):
        return dict(current_best)
    if candidate_distance < current_distance - float(improvement_margin):
        return dict(candidate_payload)
    return dict(current_best)


def build_probe_equivalent_bending_cleanup_candidate_inputs(
    base_state: dict[str, Any],
    *,
    count: int,
    dia: int,
) -> list[dict[str, Any]]:
    """Build probe-equivalent bending cleanup candidate inputs without page/UI dependencies."""

    base = dict(base_state or {})
    rows: list[tuple[str, dict[str, Any]]] = []
    minimum_bottom_bars = 2
    for new_count in range(max(minimum_bottom_bars, int(count) - 1), minimum_bottom_bars - 1, -1):
        if new_count < int(count):
            rows.append((f"bottom_count_{new_count}", {"bot1_count": new_count, "bot_row_1_bars": new_count}))
    for new_dia in reversed([10, 12, 16, 20, 24, 28, 32, 36, 40]):
        if 0 < int(new_dia) < int(dia):
            rows.append((f"bottom_dia_{new_dia}", {"db_bot_1": int(new_dia), "bot_row_1_dia": int(new_dia)}))
            current_area_key = max(1, int(count)) * int(dia) * int(dia)
            for new_count in range(max(minimum_bottom_bars, int(count)), max(minimum_bottom_bars, int(count)) + 5):
                if new_count == int(count):
                    continue
                if new_count * int(new_dia) * int(new_dia) >= current_area_key:
                    continue
                rows.append(
                    (
                        f"bottom_count_{new_count}_dia_{new_dia}",
                        {
                            "bot1_count": int(new_count),
                            "bot_row_1_bars": int(new_count),
                            "db_bot_1": int(new_dia),
                            "bot_row_1_dia": int(new_dia),
                        },
                    )
                )
    if int(base.get("bot2_count") or base.get("bot_row_2_bars") or 0) > 0:
        rows.append(("remove_second_bottom_row", {"bot2_count": 0, "bot_row_2_bars": 0, "bot_row_count": 1}))

    candidates: list[dict[str, Any]] = []
    for label_key, updates in rows:
        candidate_state = dict(base)
        candidate_state.update(dict(updates))
        candidate_id = f"cleanup:bending:{label_key}"
        label_text = f"Bending cleanup - {label_key.replace('_', ' ')}"
        candidates.append(
            {
                "label_key": label_key,
                "updates": dict(updates),
                "candidate_state": candidate_state,
                "candidate_row": {
                    "candidate_id": candidate_id,
                    "label": label_text,
                    "title": label_text,
                    "updates": dict(updates),
                    "proposed_updates": dict(updates),
                    "family": "bending",
                    "action_type": "apply_resolved_candidate",
                    "executor_backed": True,
                },
            }
        )
    return candidates


def _candidate_eval_practical_bottom_reo_label(count_1: int, count_2: int, dia: int) -> str:
    if count_2 > 0:
        return f"{count_1}N{dia} + {count_2}N{dia}"
    return f"{count_1}N{dia}"


def build_bottom_reo_recommendation_arrangement_candidate_inputs(
    arrangements: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    band: int,
) -> list[dict[str, Any]]:
    """Build bottom-reo arrangement candidate input rows.

    This owns only arrangement/update/label row construction for the existing
    bottom-reo recommendation fallback. It does not run candidate evaluation,
    filter/rank/select candidates, build CTA/action payloads, publish, render,
    or touch UI/session state.
    """

    rows: list[dict[str, Any]] = []
    for arrangement in arrangements:
        arrangement_row = dict(arrangement or {})
        updates = bottom_arrangement_to_shared_updates(arrangement_row)
        rows.append(
            {
                "band": int(band),
                "arrangement": arrangement_row,
                "updates": dict(updates),
                "label": _candidate_eval_practical_bottom_reo_label(
                    int(arrangement_row.get("bot1_count", 0) or 0),
                    int(arrangement_row.get("bot2_count", 0) or 0),
                    int(arrangement_row.get("db_bot_1", 0) or 0),
                ),
                "source": "bottom_recommendation",
                "action_type": "apply_bottom_recommendation",
            }
        )
    return rows


def evaluate_bottom_reo_recommendation_arrangement_candidate(
    state: dict[str, Any],
    *,
    arrangement_input: dict[str, Any],
    seed_state: dict[str, Any],
    context: dict[str, Any],
    eval_cache: dict[str, Any],
    metrics: dict[str, Any],
    evaluator_fn: Callable[..., dict | None],
    updates_match_state_fn: Callable[[dict, dict], bool],
) -> dict[str, Any]:
    """Evaluate one bottom-reo arrangement row through the service boundary.

    The page still owns the evaluator callback, trace sinks, ranking, selected
    result packaging, and apply routing. This helper owns only the plain-data
    evaluation handoff and immediate null/no-op status projection.
    """

    row = dict(arrangement_input or {})
    arrangement = dict(row.get("arrangement") or {})
    updates = dict(row.get("updates") or {})
    candidate_state = dict(state or {})
    candidate_state.update(updates)
    label = str(row.get("label") or "")
    source = str(row.get("source") or "bottom_recommendation")
    action_type = str(row.get("action_type") or "apply_bottom_recommendation")
    candidate = evaluator_fn(
        candidate_state,
        seed_state=dict(seed_state or {}),
        context=context,
        eval_cache=eval_cache,
        metrics=metrics,
        source=source,
        label=label,
        action_type=action_type,
    )
    if candidate is None:
        return {
            "status": "rejected",
            "reject_reason": "evaluator_returned_null",
            "evaluator_returned": False,
            "candidate": None,
            "arrangement": arrangement,
            "updates": updates,
            "label": label,
            "candidate_state": candidate_state,
        }
    candidate_updates = dict(candidate.get("updates") or {})
    if updates_match_state_fn(dict(state or {}), candidate_updates):
        return {
            "status": "rejected",
            "reject_reason": "updates_match_state",
            "evaluator_returned": True,
            "candidate": dict(candidate),
            "arrangement": arrangement,
            "updates": updates,
            "label": label,
            "candidate_state": candidate_state,
        }
    return {
        "status": "accepted_for_pool",
        "reject_reason": None,
        "evaluator_returned": True,
        "candidate": dict(candidate),
        "arrangement": arrangement,
        "updates": updates,
        "label": label,
        "candidate_state": candidate_state,
    }


def prepare_bottom_reo_recommendation_candidates_for_selection(
    filtered_candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    seed_candidate: dict[str, Any],
    state: dict[str, Any],
    mode_config: dict[str, Any],
    annotate_deltas_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None],
    score_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], float],
    annotate_target_band_fn: Callable[[dict[str, Any], dict[str, Any]], None],
    keep_top_fn: Callable[..., list[dict[str, Any]]],
    limit: int,
) -> dict[str, Any]:
    """Prepare bottom-reo candidates for selector handoff.

    This owns only the orchestration loop. The page still injects the live
    scoring/annotation callbacks, and still owns selector/result packaging,
    CTA/apply handoff, and trace emission.
    """

    filtered: list[dict[str, Any]] = [
        candidate
        for candidate in list(filtered_candidates or [])
        if isinstance(candidate, dict)
    ]
    for candidate in filtered:
        annotate_deltas_fn(candidate, dict(seed_candidate or {}), dict(state or {}))
    for candidate in filtered:
        if candidate.get("score") is None:
            candidate["score"] = score_fn(candidate, dict(mode_config or {}), dict(seed_candidate or {}))
    for candidate in filtered:
        annotate_target_band_fn(candidate, dict(mode_config or {}))
    ranked = keep_top_fn(
        filtered,
        dict(mode_config or {}),
        limit=min(int(limit or 0), len(filtered)),
    )
    return {
        "filtered_candidates": filtered,
        "ranked_candidates": list(ranked or []),
        "rank_limit": min(int(limit or 0), len(filtered)),
    }


def build_bending_only_target_band_cleanup_update_trials(
    base_state: dict[str, Any],
    *,
    width_key: str,
    current_width: float,
    current_depth: float,
    row_count: int,
    row1_bars: int,
    row2_bars: int,
    row1_dia: int,
    row2_dia: int,
    geometry_locked: bool,
    min_width: float,
    min_depth: float,
    compound_shear_update_keys: set[str] | frozenset[str] | list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Build bending-only target-band cleanup update trials without page/UI dependencies."""

    del row_count
    base = dict(base_state or {})
    shear_keys = {str(key) for key in compound_shear_update_keys or ()}
    common_dias = [10, 12, 16, 20, 24, 28, 32, 36, 40]
    dia_trials = [d for d in common_dias if d <= max(int(row1_dia), 10)]
    if int(row1_dia) not in dia_trials:
        dia_trials.append(int(row1_dia))
    dia_trials = sorted(set(int(d) for d in dia_trials), reverse=True)
    raw_updates: list[dict[str, Any]] = []
    minimum_bottom_bars = 2

    def _append_update(next_row1: int, next_row2: int, next_dia1: int, next_dia2: int | None = None) -> None:
        next_row1 = max(minimum_bottom_bars, int(next_row1))
        next_row2 = max(0, int(next_row2))
        next_dia1 = int(next_dia1)
        next_dia2 = int(next_dia2 if next_dia2 is not None else next_dia1)
        next_row_count = 2 if next_row2 > 0 else 1
        updates = {
            "bot_row_count": next_row_count,
            "bot_row_1_bars": next_row1,
            "bot_row_1_dia": next_dia1,
            "bot1_count": next_row1,
            "db_bot_1": next_dia1,
            "nb_bot": next_row1 + next_row2,
            "bot_entry": float(next_row1 + next_row2),
            "bot_row_2_bars": next_row2,
            "bot2_count": next_row2,
            "bot_row_2_dia": next_dia2,
            "db_bot_2": next_dia2,
        }
        changed = {key: value for key, value in updates.items() if str(base.get(key)) != str(value)}
        if changed and not (set(changed) & shear_keys):
            raw_updates.append(updates)

    def _append_geometry_bottom_update(
        next_width: float,
        next_depth: float,
        next_row1: int,
        next_dia1: int,
    ) -> None:
        next_row1 = max(minimum_bottom_bars, int(next_row1))
        next_dia1 = int(next_dia1)
        next_width = float(next_width)
        next_depth = float(next_depth)
        updates = {
            str(width_key): next_width,
            "D": next_depth,
            "bot_row_count": 1,
            "bot_row_1_bars": next_row1,
            "bot_row_1_dia": next_dia1,
            "bot1_count": next_row1,
            "db_bot_1": next_dia1,
            "nb_bot": next_row1,
            "bot_entry": float(next_row1),
            "bot_row_2_bars": 0,
            "bot2_count": 0,
            "bot_row_2_dia": next_dia1,
            "db_bot_2": next_dia1,
        }
        if str(width_key) != "b":
            updates["b"] = next_width
        if str(width_key) != "bw":
            updates["bw"] = next_width
        changed = {key: value for key, value in updates.items() if str(base.get(key)) != str(value)}
        if changed and not (set(changed) & shear_keys):
            raw_updates.append(updates)

    if int(row2_bars) > 0:
        for bars2 in range(int(row2_bars) - 1, -1, -1):
            _append_update(int(row1_bars), bars2, int(row1_dia), int(row2_dia))
        for bars1 in range(int(row1_bars) - 1, minimum_bottom_bars - 1, -1):
            _append_update(bars1, 0, int(row1_dia), int(row2_dia))
    else:
        for bars1 in range(int(row1_bars) - 1, minimum_bottom_bars - 1, -1):
            _append_update(bars1, 0, int(row1_dia), int(row2_dia))

    for dia in dia_trials:
        if dia >= int(row1_dia):
            continue
        _append_update(int(row1_bars), int(row2_bars), dia, min(int(row2_dia), dia))
        current_area_key = max(1, int(row1_bars + row2_bars)) * int(row1_dia) * int(row1_dia)
        for bars1 in range(int(row1_bars) + 1, int(row1_bars) + 5):
            if bars1 * int(dia) * int(dia) >= current_area_key:
                continue
            _append_update(bars1, 0, dia, dia)
        for bars1 in range(int(row1_bars) - 1, minimum_bottom_bars - 1, -1):
            _append_update(bars1, 0, dia, dia)

    if not bool(geometry_locked):
        def _progressive_descending_trials(current: float, minimum: float, *, include_current: bool) -> list[float]:
            values: set[float] = set()
            if include_current and float(current) >= float(minimum) - 1e-9:
                values.add(float(current))
            step = 25.0
            next_value = float(current) - step
            while next_value >= float(minimum) - 1e-9:
                values.add(round(float(next_value), 6))
                next_value -= step
            if float(minimum) <= float(current) + 1e-9:
                values.add(float(minimum))
            return sorted(values, reverse=True)

        width_trials = [
            value
            for value in _progressive_descending_trials(
                float(current_width),
                float(min_width),
                include_current=False,
            )
            if float(value) < float(current_width) - 1e-9
        ]
        depth_trials = _progressive_descending_trials(
            float(current_depth),
            float(min_depth),
            include_current=True,
        )
        practical_bottom_trials = {
            (int(row1_bars), int(row1_dia)),
            (2, 12),
            (3, 12),
            (4, 12),
            (5, 12),
            (6, 12),
            (2, 16),
            (3, 16),
            (4, 16),
            (2, 20),
        }
        practical_bottom_trials.update(
            (bars1, int(row1_dia))
            for bars1 in range(int(row1_bars) - 1, minimum_bottom_bars - 1, -1)
        )
        for trial_depth in [
            value
            for value in depth_trials
            if float(value) < float(current_depth) - 1e-9
        ]:
            for trial_bars, trial_dia in sorted(practical_bottom_trials):
                _append_geometry_bottom_update(float(current_width), trial_depth, trial_bars, trial_dia)
        for trial_width in width_trials:
            for trial_bars, trial_dia in sorted(practical_bottom_trials):
                _append_geometry_bottom_update(trial_width, float(current_depth), trial_bars, trial_dia)

    seen: set[tuple[tuple[str, str], ...]] = set()
    update_trials: list[dict[str, Any]] = []
    for updates in raw_updates:
        fingerprint = tuple(sorted((str(k), repr(v)) for k, v in updates.items()))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        update_trials.append(dict(updates))

    return {
        "raw_updates": [dict(updates) for updates in raw_updates],
        "update_trials": update_trials,
    }


def evaluate_zero_bending_demand_candidate_with_updates(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict | None:
    """Evaluate a zero-bending-demand cleanup candidate through the shared boundary."""

    return evaluate_design_candidate_with_updates(
        state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=state_snapshot_fn,
        evaluator_fn=evaluator_fn,
    )


def evaluate_bending_only_target_band_candidate_with_updates(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict | None:
    """Evaluate a bending-only target-band cleanup candidate through the shared boundary."""

    return evaluate_design_candidate_with_updates(
        state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=state_snapshot_fn,
        evaluator_fn=evaluator_fn,
    )


def build_direct_target_band_ladder_stage_update_attempts(
    *,
    stage_name: str,
    base_state: dict[str, Any],
    width_key: str = "b",
    base_width: float | None = None,
    base_depth: float | None = None,
    base_lig_d: int | None = None,
    base_lig_legs: int | None = None,
    base_lig_spacing: float | None = None,
    min_cleanup_width: float = 250.0,
    min_cleanup_depth: float = 300.0,
    prebuilt_update_attempts: list[Any] | tuple[Any, ...] | None = None,
) -> list[dict[str, Any]]:
    """Build direct target-band ladder update attempts without page/UI dependencies.

    Callback-heavy arrangement fitting and generated reinforcement variants remain
    page-owned for now and are passed in as prebuilt attempts.
    """

    del base_state
    stage = str(stage_name or "").strip()

    def _normalise(rows: list[Any] | tuple[Any, ...] | None, *, limit: int | None = None) -> list[dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        for row in list(rows or []):
            label: str | None = None
            updates: dict[str, Any] = {}
            if isinstance(row, dict):
                label = str(row.get("label") or row.get("name") or row.get("stage_label") or "")
                updates = dict(row.get("updates") or {})
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                label = str(row[0] or "")
                updates = dict(row[1] or {})
            if not updates:
                continue
            attempts.append({"label": label or "Direct target-band ladder update", "updates": dict(updates)})
            if limit is not None and len(attempts) >= int(limit):
                break
        return attempts

    if stage == "strengthen_reo_nearby":
        return _normalise(prebuilt_update_attempts, limit=12)

    if stage == "strengthen_geometry_nearby":
        return _normalise(prebuilt_update_attempts)

    if stage == "cleanup_reo_nearby":
        return _normalise(prebuilt_update_attempts)

    if stage == "cleanup_shear_nearby":
        return _normalise(prebuilt_update_attempts)

    if stage == "strengthen_shear_nearby":
        attempts: list[dict[str, Any]] = []
        lig_d = int(base_lig_d or 0)
        legs = int(base_lig_legs or 0)
        spacing = float(base_lig_spacing or 0.0)
        if lig_d > 0 and legs >= 2 and spacing > 0:
            for next_spacing in (
                max(75.0, spacing - 25.0),
                max(75.0, spacing - 50.0),
                150.0,
                125.0,
                100.0,
                75.0,
            ):
                if next_spacing < spacing - 1e-9:
                    attempts.append(
                        {
                            "label": f"reduce link spacing to {next_spacing:g}",
                            "updates": {"s_lig": float(next_spacing)},
                        }
                    )
            for dia in (10, 12, 16, 20, 24):
                if int(dia) > lig_d:
                    attempts.append(
                        {
                            "label": f"increase link diameter to {dia}",
                            "updates": {"lig_d": int(dia)},
                        }
                    )
            for next_legs in (legs + 2, 4, 6, 8):
                if int(next_legs) > legs:
                    attempts.append(
                        {
                            "label": f"increase link legs to {next_legs}",
                            "updates": {"lig_legs": int(next_legs)},
                        }
                    )
        return attempts[:18]

    if stage == "cleanup_geometry_nearby":
        attempts: list[dict[str, Any]] = []
        depth = float(base_depth or 0.0)
        width = float(base_width or 0.0)
        key = str(width_key or "b")
        for depth_step in (25.0, 50.0, 75.0):
            next_depth = depth - depth_step
            if next_depth >= float(min_cleanup_depth):
                attempts.append({"label": f"reduce depth {depth_step:g}", "updates": {"D": float(next_depth)}})
        for width_step in (25.0, 50.0, 75.0):
            next_width = width - width_step
            if next_width >= float(min_cleanup_width):
                updates: dict[str, Any] = {key: float(next_width)}
                if key != "b":
                    updates["b"] = float(next_width)
                attempts.append({"label": f"reduce width {width_step:g}", "updates": updates})
        return attempts

    return _normalise(prebuilt_update_attempts)


def build_direct_target_band_broad_shear_options(
    raw_shear_options: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> list[dict[str, Any]]:
    """Build broad direct target-band shear option list without page/UI dependencies."""

    dedup: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
    for option in [{}] + [dict(row or {}) for row in list(raw_shear_options or []) if isinstance(row, dict)]:
        sig = tuple(sorted((str(k), str(v)) for k, v in dict(option or {}).items()))
        dedup[sig] = dict(option or {})
    return list(dedup.values())


def build_direct_target_band_broad_geometry_plan(
    *,
    width_values: list[Any] | tuple[Any, ...] | None,
    depth_values: list[Any] | tuple[Any, ...] | None,
) -> list[dict[str, Any]]:
    """Build broad direct target-band width/depth search plan rows."""

    return [
        {"width": width, "depth": depth}
        for width in list(width_values or [])
        for depth in list(depth_values or [])
    ]


def build_direct_target_band_broad_bottom_trial_attempts(
    *,
    prebuilt_bottom_trials: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    keep_bottom_updates: dict[str, Any] | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Package broad direct target-band bottom trial attempts."""

    rows: list[dict[str, Any]] = []
    if keep_bottom_updates:
        rows.append(
            {
                "updates": dict(keep_bottom_updates or {}),
                "label": "Keep current bottom reinforcement",
            }
        )
    for trial in list(prebuilt_bottom_trials or []):
        if not isinstance(trial, dict):
            continue
        row = dict(trial)
        updates = dict(row.get("updates") or {})
        if not updates:
            continue
        row["updates"] = updates
        row["label"] = str(row.get("label") or "Direct target-band search")
        rows.append(row)
    return rows[: max(0, int(limit or 0))]


def evaluate_direct_target_band_candidate_with_updates(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict | None:
    """Evaluate a direct target-band candidate through the shared boundary."""

    return evaluate_design_candidate_with_updates(
        state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=state_snapshot_fn,
        evaluator_fn=evaluator_fn,
    )


def evaluate_active_fail_executor_candidate_with_updates(
    state: dict,
    *,
    updates: dict | None = None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    state_snapshot_fn: Callable[[dict], dict],
    evaluator_fn: Callable[..., dict | None],
) -> dict | None:
    """Evaluate an active-failure executor candidate through the shared boundary."""

    return evaluate_design_candidate_with_updates(
        state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=state_snapshot_fn,
        evaluator_fn=evaluator_fn,
    )


def resolve_active_fail_executor_candidate_eval_source(family_meta: dict[str, Any] | None = None) -> str:
    """Return the contract source label for an active-fail executor candidate eval."""

    family_id = str((family_meta or {}).get("candidate_family_id") or "").strip().upper()
    if family_id == "BENDING_FAIL_GOVERNS":
        return "bending_fail_contract_ladder"
    if family_id == "SHEAR_FAIL_GOVERNS":
        return "shear_fail_contract_ladder"
    if family_id == "COMBINED_BENDING_SHEAR_FAIL":
        return "combined_fail_contract_ladder"
    return "active_fail_near_current_repair_search"


def _active_fail_executor_parse_util_value(value: Any) -> float | None:
    if value in (None, "", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _active_fail_executor_required_checks_acceptable(overview: dict[str, Any] | None) -> bool:
    if not isinstance(overview, dict):
        return False
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        tracked = [
            str(status or "").strip().upper()
            for status in statuses.values()
            if str(status or "").strip() not in {"", "â€”", "-"}
        ]
    else:
        tracked = []
    if not tracked:
        return bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    return not any(status in {"FAIL", "FAILED", "ERROR"} for status in tracked)


def project_active_fail_executor_evaluated_candidate_result(
    candidate: dict[str, Any] | None,
    *,
    updates: dict[str, Any] | None,
    label: str,
    family_meta: dict[str, Any] | None = None,
    geometry_update_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    bottom_update_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    shear_update_keys: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any] | None:
    """Project an active-fail evaluated candidate into the executor result shape."""

    if not isinstance(candidate, dict):
        return None
    cand = dict(candidate)
    u = dict(updates or {})
    cand_overview = dict(cand.get("overview") or {})
    preview_worst = _active_fail_executor_parse_util_value(
        cand_overview.get("worst_util") or cand_overview.get("governing_util")
    )
    if preview_worst is not None:
        cand["candidate_post_util"] = float(preview_worst)
        cand["worst_util"] = float(preview_worst)
    cand["updates"] = dict(u)
    cand["action_type"] = "apply_resolved_candidate"
    strict_all_pass = bool(cand_overview.get("all_key_pass")) and not bool(cand_overview.get("any_fail"))
    family_id = str((family_meta or {}).get("candidate_family_id") or "").strip().upper()
    if family_id == "BENDING_FAIL_GOVERNS":
        statuses = {
            str(k).strip().lower(): str(v or "").strip().upper()
            for k, v in dict(cand_overview.get("statuses") or {}).items()
        }
        no_bending_fail = statuses.get("bending") not in {"FAIL", "FAILED", "ERROR"}
        family_accepts = bool(_active_fail_executor_required_checks_acceptable(cand_overview)) and bool(no_bending_fail)
        cand["bending_fail_acceptance_basis"] = (
            "required_checks_no_fail_or_error;non_demand_sls_statuses_do_not_block_repair"
        )
        cand["bending_fail_strict_all_key_pass"] = bool(strict_all_pass)
        cand["bending_fail_required_checks_acceptable"] = bool(
            _active_fail_executor_required_checks_acceptable(cand_overview)
        )
    elif family_id == "SHEAR_FAIL_GOVERNS":
        statuses = {
            str(k).strip().lower(): str(v or "").strip().upper()
            for k, v in dict(cand_overview.get("statuses") or {}).items()
        }
        no_shear_fail = statuses.get("shear") not in {"FAIL", "FAILED", "ERROR"}
        family_accepts = bool(_active_fail_executor_required_checks_acceptable(cand_overview)) and bool(no_shear_fail)
        cand["shear_fail_acceptance_basis"] = (
            "required_checks_no_fail_or_error;near_limit_non_governing_statuses_do_not_block_repair"
        )
        cand["shear_fail_strict_all_key_pass"] = bool(strict_all_pass)
        cand["shear_fail_required_checks_acceptable"] = bool(
            _active_fail_executor_required_checks_acceptable(cand_overview)
        )
    else:
        family_accepts = bool(strict_all_pass)
    cand["is_compliant"] = bool(family_accepts)
    cand["preview_pass"] = bool(cand.get("is_compliant"))
    cand["is_executable"] = bool(cand.get("is_compliant"))
    cand["advisory_only"] = not bool(cand.get("is_compliant"))
    cand["label"] = str(label or "")
    if isinstance(family_meta, dict):
        cand.update(dict(family_meta))
    geometry_keys = {str(key) for key in (geometry_update_keys or ())}
    bottom_keys = {str(key) for key in (bottom_update_keys or ())}
    shear_keys = {str(key) for key in (shear_update_keys or ())}
    update_keys = set(u)
    subfamilies: list[str] = []
    if bool(update_keys & geometry_keys):
        subfamilies.append("geometry")
    if bool(update_keys & bottom_keys):
        subfamilies.append("bottom_reo")
    if bool(update_keys & shear_keys):
        subfamilies.append("shear")
    cand["recommendation_family_tag"] = "combined" if len(subfamilies) >= 2 else (
        "shear" if bool(update_keys & shear_keys) else "bending"
    )
    cand["affected_family"] = cand["recommendation_family_tag"]
    return cand


def build_active_fail_executor_candidate_eval_attempt_result(
    *,
    cached_candidate: dict[str, Any] | None = None,
    evaluated_candidate: dict[str, Any] | None = None,
    used_cache: bool = False,
    updates: dict[str, Any] | None = None,
    label: str = "",
    family_meta: dict[str, Any] | None = None,
    geometry_update_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    bottom_update_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    shear_update_keys: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    """Project one active-fail eval attempt without owning page loop/callback state."""

    metrics_delta = {
        "candidate_evaluation_cache_hits": 0,
        "candidate_evaluation_cache_misses": 0,
        "duplicate_candidate_fingerprints_skipped": 0,
        "blocker_attempt_cache_hits": 0,
    }
    raw_candidate: dict[str, Any] | None = None
    cache_candidate: dict[str, Any] | None = None

    if used_cache and isinstance(cached_candidate, dict):
        metrics_delta["candidate_evaluation_cache_hits"] = 1
        metrics_delta["duplicate_candidate_fingerprints_skipped"] = 1
        metrics_delta["blocker_attempt_cache_hits"] = 1
        raw_candidate = dict(cached_candidate)
    else:
        metrics_delta["candidate_evaluation_cache_misses"] = 1
        if isinstance(evaluated_candidate, dict):
            raw_candidate = dict(evaluated_candidate)
            cache_candidate = dict(evaluated_candidate)

    projected_candidate = project_active_fail_executor_evaluated_candidate_result(
        raw_candidate,
        updates=updates,
        label=label,
        family_meta=family_meta if isinstance(family_meta, dict) else None,
        geometry_update_keys=geometry_update_keys,
        bottom_update_keys=bottom_update_keys,
        shear_update_keys=shear_update_keys,
    )

    return {
        "candidate": projected_candidate if isinstance(projected_candidate, dict) else None,
        "metrics_delta": metrics_delta,
        "cache_candidate": cache_candidate,
        "used_cache": bool(used_cache and isinstance(cached_candidate, dict)),
        "eval_source": resolve_active_fail_executor_candidate_eval_source(family_meta),
    }


def apply_active_fail_executor_candidate_eval_loop_attempt_result(
    *,
    eval_attempt: dict[str, Any] | None,
    candidate_fp: str | None,
    eval_cache_by_candidate_fp: dict[str, dict[str, Any]] | None = None,
    repair_eval_metrics: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """Apply one active-fail candidate eval attempt to plain loop accumulators."""

    attempt = dict(eval_attempt or {})
    metrics = dict(repair_eval_metrics or {})
    for key in (
        "candidate_evaluation_cache_hits",
        "candidate_evaluation_cache_misses",
        "duplicate_candidate_fingerprints_skipped",
        "blocker_attempt_cache_hits",
    ):
        try:
            metrics[key] = int(metrics.get(key, 0) or 0)
        except Exception:
            metrics[key] = 0
    cache = {
        str(key): dict(value)
        for key, value in dict(eval_cache_by_candidate_fp or {}).items()
        if isinstance(value, dict)
    }
    candidate_rows = [dict(row) for row in list(candidates or []) if isinstance(row, dict)]
    for metric_key, metric_value in dict(attempt.get("metrics_delta") or {}).items():
        if metric_key in metrics:
            metrics[metric_key] += int(metric_value or 0)
    cache_candidate = attempt.get("cache_candidate")
    if isinstance(cache_candidate, dict) and str(candidate_fp or ""):
        cache[str(candidate_fp)] = dict(cache_candidate)
    candidate = attempt.get("candidate")
    if isinstance(candidate, dict):
        candidate_rows.append(dict(candidate))
    return {
        "candidate": dict(candidate) if isinstance(candidate, dict) else None,
        "candidates": candidate_rows,
        "eval_cache_by_candidate_fp": cache,
        "repair_eval_metrics": metrics,
        "candidate_accepted": isinstance(candidate, dict),
    }


def build_active_fail_executor_candidate_eval_precheck_projection(
    *,
    base_state: dict[str, Any] | None,
    updates: dict[str, Any] | None,
    updates_match_state: bool = False,
    materially_actionable: bool = True,
    seen_update_signatures: set[tuple[Any, ...]] | list[tuple[Any, ...]] | tuple[tuple[Any, ...], ...] | None = None,
) -> dict[str, Any]:
    """Project pure active-fail candidate-loop precheck data without page callbacks."""

    u = dict(updates or {})
    signature = tuple(sorted((str(k), str(v)) for k, v in u.items()))
    seen = {tuple(row) for row in list(seen_update_signatures or [])}
    duplicate_signature = bool(signature and signature in seen)
    skip_reason = None
    if not u:
        skip_reason = "empty_updates"
    elif bool(updates_match_state):
        skip_reason = "updates_match_state"
    elif not bool(materially_actionable):
        skip_reason = "not_materially_actionable"
    elif duplicate_signature:
        skip_reason = "duplicate_update_signature"

    candidate_state = None
    if skip_reason is None:
        candidate_state = copy.deepcopy(dict(base_state or {}))
        candidate_state.update(u)

    return {
        "should_evaluate": skip_reason is None,
        "skip_reason": skip_reason,
        "updates": u,
        "update_signature": signature,
        "duplicate_update_signature": duplicate_signature,
        "candidate_state": candidate_state,
    }


def resolve_active_fail_executor_candidate_eval_cache_lookup(
    *,
    candidate_fp: str | None,
    eval_cache_by_candidate_fp: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve a plain active-fail candidate eval cache hit without owning storage."""

    fp = str(candidate_fp or "")
    cache = {
        str(key): dict(value)
        for key, value in dict(eval_cache_by_candidate_fp or {}).items()
        if isinstance(value, dict)
    }
    cached_candidate = cache.get(fp) if fp else None
    return {
        "candidate_fp": fp,
        "cached_candidate": dict(cached_candidate) if isinstance(cached_candidate, dict) else None,
        "used_cache": isinstance(cached_candidate, dict),
    }


def _active_fail_executor_int(source: dict[str, Any], *keys: str, default: int = 0) -> int:
    for key in keys:
        if key in source:
            try:
                return int(source.get(key) or default)
            except Exception:
                continue
    return int(default)


def _active_fail_executor_float(source: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(source.get(key, default) or default)
    except Exception:
        return float(default)


def _active_fail_executor_width_context(source: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(source.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", _active_fail_executor_float(source, "bw", _active_fail_executor_float(source, "b", 300.0))
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", _active_fail_executor_float(source, "tw", _active_fail_executor_float(source, "b", 200.0))
    return "b", "Width b (mm)", _active_fail_executor_float(source, "b", 400.0)


def build_active_fail_executor_candidate_generation_context(
    base_state: dict[str, Any],
    active_failures: list[str] | set[str] | tuple[str, ...],
    *,
    target_low: float,
    target_high: float,
    canonical_no_shear_spacing: float = 200.0,
) -> dict[str, Any]:
    """Build pure active-fail executor generation inputs without page/session state."""

    base = dict(base_state or {})
    active = {
        str(family or "").strip().lower()
        for family in list(active_failures or [])
        if str(family or "").strip()
    }
    width_key, width_label, base_width = _active_fail_executor_width_context(base)
    base_depth = _active_fail_executor_float(base, "D", 0.0)
    base_count = max(
        1,
        _active_fail_executor_int(
            base,
            "bot1_count",
            "bot_row_1_bars",
            default=1,
        ),
    )
    base_dia = max(
        10,
        _active_fail_executor_int(
            base,
            "db_bot_1",
            "bot_row_1_dia",
            default=16,
        ),
    )
    base_lig_d = _active_fail_executor_int(base, "lig_d", default=0)
    base_legs = _active_fail_executor_int(base, "lig_legs", default=0)
    base_spacing = _active_fail_executor_float(
        base,
        "s_lig",
        float(canonical_no_shear_spacing),
    )
    return {
        "active": sorted(active),
        "target_low": float(target_low),
        "target_high": float(target_high),
        "width_key": width_key,
        "width_label": width_label,
        "base_width": float(base_width),
        "base_depth": float(base_depth),
        "base_count": int(base_count),
        "base_dia": int(base_dia),
        "base_lig_d": int(base_lig_d),
        "base_legs": int(base_legs),
        "base_spacing": float(base_spacing),
        "ordered_bottom": build_near_current_bottom_repair_specs(
            int(base_count),
            int(base_dia),
        ),
        "ordered_geom": build_near_current_geometry_repair_specs(
            float(base_width),
            float(base_depth),
        ),
        "ordered_shear": build_near_current_shear_repair_specs(
            active,
            base_lig_d=int(base_lig_d),
            base_legs=int(base_legs),
            base_spacing=float(base_spacing),
        ),
    }


def build_zero_bending_demand_cleanup_update_trials(
    base_state: dict[str, Any],
    *,
    width_key: str,
    current_width: float,
    current_depth: float,
    row1_bars: int,
    row2_bars: int,
    row1_dia: int,
    row2_dia: int,
    geometry_locked: bool,
    min_width: float,
    min_depth: float,
    updates_match_state_fn: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Build zero-bending-demand cleanup update trials without page/UI dependencies."""

    base = dict(base_state or {})
    common_dias = [10, 12, 16, 20, 24, 28, 32, 36, 40]
    dia_trials = sorted({int(d) for d in common_dias if 10 <= int(d) <= max(int(row1_dia), 10)}, reverse=True)
    if int(row1_dia) not in dia_trials:
        dia_trials.append(int(row1_dia))
        dia_trials = sorted(set(dia_trials), reverse=True)
    bar_trials = list(range(max(2, min(int(row1_bars), 6)), 1, -1))
    if int(row1_bars) not in bar_trials:
        bar_trials.insert(0, int(row1_bars))

    if geometry_locked:
        width_trials = [float(current_width)]
        depth_trials = [float(current_depth)]
    else:
        width_trials = sorted(
            {
                float(value)
                for value in (float(current_width), float(current_width) - 50.0, float(min_width))
                if float(value) >= float(min_width)
            },
            reverse=True,
        )
        depth_trials = sorted(
            {
                float(value)
                for value in (
                    float(current_depth),
                    float(current_depth) - 50.0,
                    float(current_depth) - 100.0,
                    float(current_depth) - 150.0,
                    float(min_depth),
                )
                if float(value) >= float(min_depth)
            },
            reverse=True,
        )

    def _material_proxy(width: float, depth: float, bars: int, dia: int) -> float:
        ast = float(bars) * math.pi * (float(dia) ** 2.0) / 4.0
        return float(width) * float(depth) * 0.001 + ast * 0.05

    current_proxy = _material_proxy(
        float(current_width),
        float(current_depth),
        int(row1_bars) + int(row2_bars),
        int(row1_dia),
    )
    trials: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for width in width_trials:
        for depth in depth_trials:
            for bars in bar_trials:
                for dia in dia_trials:
                    updates: dict[str, Any] = {
                        str(width_key): float(width),
                        "D": float(depth),
                        "bot_row_count": 1,
                        "bot_row_1_bars": int(bars),
                        "bot1_count": int(bars),
                        "nb_bot": int(bars),
                        "bot_entry": float(bars),
                        "bot_row_1_dia": int(dia),
                        "db_bot_1": int(dia),
                        "bot_row_2_bars": 0,
                        "bot2_count": 0,
                        "bot_row_2_dia": int(min(int(row2_dia), int(dia))),
                        "db_bot_2": int(min(int(row2_dia), int(dia))),
                    }
                    if str(width_key) != "b":
                        updates["b"] = float(width)
                    if str(width_key) != "bw":
                        updates["bw"] = float(width)
                    updates = {key: value for key, value in updates.items() if str(base.get(key)) != str(value)}
                    if not updates:
                        continue
                    if updates_match_state_fn is not None and updates_match_state_fn(base, updates):
                        continue
                    key = tuple(sorted(f"{str(k)}={repr(v)}" for k, v in updates.items()))
                    if key in seen:
                        continue
                    seen.add(key)
                    proxy = _material_proxy(float(width), float(depth), int(bars), int(dia))
                    if proxy >= current_proxy - 1e-9:
                        continue
                    trials.append(
                        {
                            "updates": dict(updates),
                            "candidate_material_proxy": float(proxy),
                        }
                    )

    return {
        "current_material_proxy": float(current_proxy),
        "update_trials": trials,
    }


def build_fast_candidate_evaluation_result_projection(
    *,
    candidate_state: dict[str, Any] | None,
    overview: dict[str, Any],
    bottom_state: dict[str, Any],
    width: int | float,
    depth: int | float,
    ast_top: int | float,
    bar_count: int,
    row_count: int,
    reo_congestion_index: int | float,
    shear_density: int | float,
    flexural_util: int | float | None,
    ductility_util: int | float | None,
    min_steel_util: int | float | None,
    bending_present: bool,
    shear_link_detailing_failures: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    """Build the fast candidate evaluation result from plain evaluated facts."""

    overview_d = dict(overview or {})
    bottom_state_d = dict(bottom_state or {})
    failures = [str(reason) for reason in list(shear_link_detailing_failures or [])]
    fail_count = sum(1 for status in dict(overview_d.get("statuses") or {}).values() if status == "FAIL")
    return {
        "source": "fast_eval",
        "label": "Fast Eval",
        "action_type": None,
        "updates": {},
        "state": candidate_state if isinstance(candidate_state, dict) else {},
        "overview": overview_d,
        "bottom_state": bottom_state_d,
        "width": float(width),
        "depth": float(depth),
        "Ast_bot": float(bottom_state_d.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": float(ast_top),
        "bar_count": int(bar_count),
        "row_count": int(row_count),
        "reo_congestion_index": float(reo_congestion_index),
        "shear_density": float(shear_density),
        "bending_components": {
            "flexural_util": flexural_util if bending_present else None,
            "ductility_util": ductility_util if bending_present else None,
            "min_steel_util": min_steel_util if bending_present else None,
        },
        "shear_link_detailing_failures": list(failures),
        "rejection_reason": (
            "shear link detailing fail: " + "; ".join(failures)
            if failures else None
        ),
        "is_compliant": bool(overview_d.get("all_key_pass")),
        "worst_util": float(overview_d.get("worst_util") or 0.0),
        "fail_count": fail_count,
    }


def build_full_candidate_evaluation_result_projection(
    *,
    candidate_state: dict[str, Any] | None,
    source: str,
    label: str | None,
    action_type: str | None,
    updates: dict[str, Any] | None,
    overview: dict[str, Any],
    bottom_state: dict[str, Any],
    width: int | float,
    depth: int | float,
    ast_top: int | float,
    bar_count: int,
    row_count: int,
    reo_congestion_index: int | float,
    shear_density: int | float,
    flexural_util: int | float | None,
    ductility_util: int | float | None,
    min_steel_util: int | float | None,
    bending_present: bool,
) -> dict[str, Any]:
    """Build the full candidate evaluation result from plain evaluated facts."""

    overview_d = dict(overview or {})
    bottom_state_d = dict(bottom_state or {})
    statuses = dict(overview_d.get("statuses") or {})
    fail_count = sum(1 for status in statuses.values() if status == "FAIL")
    source_text = str(source or "")
    return {
        "source": source_text,
        "label": label or source_text.replace("_", " ").title(),
        "action_type": action_type,
        "updates": dict(updates or {}),
        "state": candidate_state if isinstance(candidate_state, dict) else {},
        "overview": overview_d,
        "bottom_state": bottom_state_d,
        "width": float(width),
        "depth": float(depth),
        "Ast_bot": float(bottom_state_d.get("Ast_bot", 0.0) or 0.0),
        "Ast_top": float(ast_top),
        "bar_count": int(bar_count),
        "row_count": int(row_count),
        "reo_congestion_index": float(reo_congestion_index),
        "shear_density": float(shear_density),
        "bending_components": {
            "flexural_util": flexural_util if bending_present else None,
            "ductility_util": ductility_util if bending_present else None,
            "min_steel_util": min_steel_util if bending_present else None,
        },
        "is_compliant": bool(overview_d.get("all_key_pass")),
        "worst_util": float(overview_d.get("worst_util") or 0.0),
        "fail_count": fail_count,
    }


def build_full_candidate_evaluation_overview_status_projection(
    *,
    base_overview: dict[str, Any],
    bending: dict[str, Any] | None,
    shear: dict[str, Any] | None,
    crack: dict[str, Any] | None,
    deflection: dict[str, Any] | None,
    unknown_status: str,
) -> dict[str, Any]:
    """Build full candidate overview/status facts from evaluated solver outputs."""

    base = dict(base_overview or {})
    base_statuses = dict(base.get("statuses") or {})
    base_utils = dict(base.get("utils") or {})
    base_packs = dict(base.get("packs") or {})

    bending_util = None
    bending_status = unknown_status
    flexural_util = None
    ductility_util = None
    min_steel_util = None
    if bending:
        flexural_util = float(bending.get("Mu_util", float("inf")))
        try:
            ductility_util = (
                float(bending.get("ku", 0.0) or 0.0) / 0.36
                if bending.get("ku") is not None
                else None
            )
        except Exception:
            ductility_util = None
        try:
            as_min = float(bending.get("As_min", 0.0) or 0.0)
            ast = float(bending.get("Ast_bot", 0.0) or 0.0)
            if ast > 0.0 and as_min > 0.0:
                min_steel_util = as_min / ast
        except Exception:
            min_steel_util = None
        bending_util = flexural_util
        if bending_util is not None and math.isnan(bending_util):
            bending_util = None
        governs = [
            util
            for util in (flexural_util, ductility_util, min_steel_util)
            if util is not None and not math.isnan(util)
        ]
        if governs:
            if any(util > 1.0 for util in governs):
                bending_status = "FAIL"
            elif any(util >= 0.95 for util in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"
        else:
            bending_status = unknown_status

    shear_util = None
    base_shear_util = None
    try:
        raw_base_shear = base_utils.get("shear")
        base_shear_util = float(raw_base_shear) if raw_base_shear is not None else None
        if base_shear_util is not None and math.isnan(base_shear_util):
            base_shear_util = None
    except Exception:
        base_shear_util = None
    base_shear_status = str(base_statuses.get("shear") or unknown_status)
    if base_shear_util is not None:
        shear_util = base_shear_util
        shear_status = base_shear_status
    elif shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                coerced = float(value)
            except Exception:
                continue
            if not math.isnan(coerced):
                shear_candidates.append(coerced)
        shear_util = max(shear_candidates, default=None)
        shear_status = _fast_candidate_status_from_util(shear_util, unknown_status)
    else:
        shear_util = None
        shear_status = base_shear_status

    statuses = dict(base_statuses)
    statuses["bending"] = bending_status
    statuses["shear"] = shear_status
    if crack is not None:
        crack_util = float(crack.get("util", 0.0) or 0.0)
        statuses["crack"] = _fast_candidate_status_from_util(crack_util, unknown_status)
    else:
        crack_util = None
    if deflection is not None:
        statuses["deflection"] = str(deflection.get("status") or unknown_status)

    utils = dict(base_utils)
    utils["bending"] = bending_util
    utils["shear"] = shear_util
    if crack is not None:
        utils["crack"] = float(crack.get("util", 0.0) or 0.0)
    if deflection is not None:
        utils["deflection"] = deflection.get("util")

    packs = dict(base_packs)
    if deflection is not None:
        packs["deflection"] = dict(deflection.get("pack") or {})

    tracked_statuses = [status for status in statuses.values() if status not in (unknown_status, "")]
    overview = {
        "packs": packs,
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    return {
        "overview": overview,
        "bending_util": bending_util,
        "shear_util": shear_util,
        "flexural_util": flexural_util,
        "ductility_util": ductility_util,
        "min_steel_util": min_steel_util,
    }


def build_fast_candidate_evaluation_overview_status_projection(
    *,
    seed_overview: dict[str, Any] | None,
    bending_status: str,
    shear_status: str,
    crack_status: str,
    deflection_status: str,
    bending_util: int | float | None,
    shear_util: int | float | None,
    crack_util: int | float | None,
    deflection_util: int | float | None,
    bend_pack: dict[str, Any] | None,
    shear_link_detailing_failures: list[str] | tuple[str, ...] | None,
    unknown_status: str | None = None,
) -> dict[str, Any]:
    """Build the fast candidate overview/status projection from plain facts."""

    _ = seed_overview  # Kept in the boundary for parity with the page-side inputs.
    failures = [str(reason) for reason in list(shear_link_detailing_failures or [])]
    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": crack_status,
        "deflection": deflection_status,
    }
    utils = {
        "bending": bending_util,
        "shear": shear_util,
        "crack": crack_util,
        "deflection": deflection_util,
    }
    ignored_statuses = {"", str(unknown_status or "")}
    tracked_statuses = [status for status in statuses.values() if status not in ignored_statuses]
    overview = {
        "packs": {"bending": dict(bend_pack or {})} if bend_pack else {},
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    if failures:
        overview["failure_details_by_family"] = {
            "shear": [
                {
                    "title": "Shear link detailing",
                    "status": "FAIL",
                    "text": reason,
                }
                for reason in failures
            ]
        }
        overview["shear_link_detailing_failures"] = list(failures)
    return overview


def build_fast_candidate_evaluation_bending_summary_pack_projection(
    *,
    bending: dict[str, Any] | None,
    mu_star: int | float | None,
) -> dict[str, Any]:
    """Build the fast candidate bending overview pack from plain bending facts."""

    if not bending:
        return {}
    phi_cap = float(dict(bending).get("phi_Mu_cap", 0.0) or 0.0)
    mu_value = float(mu_star or 0.0)
    dem_util = (mu_value / phi_cap) if phi_cap > 1e-9 else None
    return {
        "summary_phiMu_kNm": phi_cap,
        "summary_Mu_star_kNm": mu_value,
        "summary_util": dem_util,
        "rows": [],
    }


def build_fast_candidate_evaluation_shear_detail_state_projection(
    *,
    eval_state: dict[str, Any] | None,
    candidate_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Overlay candidate shear-detailing spacing keys onto the evaluated state."""

    state = dict(eval_state or {})
    candidate = dict(candidate_state or {})
    for key in (
        "shear_required_spacing_mm",
        "shear_effective_spacing_mm",
        "shear_sectional_check_spacing_mm",
    ):
        if key in candidate:
            state[key] = candidate.get(key)
    return state


def _fast_candidate_status_from_util(util: int | float | None, unknown_status: str) -> str:
    if util is None:
        return unknown_status
    try:
        resolved = float(util)
    except Exception:
        return unknown_status
    if math.isnan(resolved):
        return unknown_status
    if resolved <= 1.0:
        return "NEAR LIMIT" if resolved >= 0.95 else "PASS"
    return "FAIL"


def build_fast_candidate_evaluation_scalar_status_projection(
    *,
    seed_overview: dict[str, Any] | None,
    bending: dict[str, Any] | None,
    shear: dict[str, Any] | None,
    crack: dict[str, Any] | None,
    deflection: dict[str, Any] | None,
    shear_link_detailing_failures: list[str] | tuple[str, ...] | None,
    unknown_status: str,
) -> dict[str, Any]:
    """Build fast candidate scalar status facts from plain evaluated outputs."""

    seed = dict(seed_overview or {})
    seed_statuses = dict(seed.get("statuses") or {})
    seed_utils = dict(seed.get("utils") or {})

    flexural_util = None
    ductility_util = None
    min_steel_util = None
    bending_util = None
    bending_status = unknown_status
    if bending:
        flexural_util = float(bending.get("Mu_util", float("inf")))
        try:
            ductility_util = (
                float(bending.get("ku", 0.0) or 0.0) / 0.36
                if bending.get("ku") is not None
                else None
            )
        except Exception:
            ductility_util = None
        try:
            as_min = float(bending.get("As_min", 0.0) or 0.0)
            ast = float(bending.get("Ast_bot", 0.0) or 0.0)
            if ast > 0.0 and as_min > 0.0:
                min_steel_util = as_min / ast
        except Exception:
            min_steel_util = None
        bending_util = flexural_util
        if bending_util is not None and math.isnan(float(bending_util)):
            bending_util = None
        governs = [
            u
            for u in (flexural_util, ductility_util, min_steel_util)
            if u is not None and not math.isnan(float(u))
        ]
        if governs:
            if any(u > 1.0 for u in governs):
                bending_status = "FAIL"
            elif any(u >= 0.95 for u in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"
        else:
            bending_status = unknown_status

    shear_util = None
    shear_status = unknown_status
    if shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                resolved = float(value)
            except Exception:
                continue
            if not math.isnan(resolved):
                shear_candidates.append(resolved)
        shear_util = max(shear_candidates, default=None)
        shear_status = _fast_candidate_status_from_util(shear_util, unknown_status)

    failures = [str(reason) for reason in list(shear_link_detailing_failures or [])]
    if failures:
        shear_status = "FAIL"

    crack_status = (
        _fast_candidate_status_from_util(float(crack.get("util", 0.0) or 0.0), unknown_status)
        if crack is not None
        else str(seed_statuses.get("crack", "PASS") or "PASS")
    )
    deflection_status = (
        str(deflection.get("status") or "PASS")
        if deflection is not None
        else str(seed_statuses.get("deflection", "PASS") or "PASS")
    )
    crack_util = (
        float(crack.get("util", 0.0) or 0.0)
        if crack is not None
        else seed_utils.get("crack")
    )
    deflection_util = (
        deflection.get("util")
        if deflection is not None
        else seed_utils.get("deflection")
    )

    statuses = {
        "bending": bending_status,
        "shear": shear_status,
        "crack": crack_status,
        "deflection": deflection_status,
    }
    utils = {
        "bending": bending_util,
        "shear": shear_util,
        "crack": crack_util,
        "deflection": deflection_util,
    }
    return {
        "statuses": statuses,
        "utils": utils,
        "flexural_util": flexural_util,
        "ductility_util": ductility_util,
        "min_steel_util": min_steel_util,
        "bending_util": bending_util,
        "shear_util": shear_util,
        "unknown_status": next(
            (
                status
                for status in statuses.values()
                if status not in ("PASS", "FAIL", "NEAR LIMIT", "")
            ),
            unknown_status,
        ),
    }


def build_fast_candidate_evaluation_physical_metric_projection(
    *,
    eval_state: dict[str, Any] | None,
    bottom_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build pure physical metrics for the fast candidate result projection."""

    state = dict(eval_state or {})
    bottom_projection = build_bottom_reo_candidate_metric_projection(
        state,
        bottom_updates=bottom_updates,
    )
    bottom_state = dict(bottom_projection.get("effective_bottom") or {})
    _, _, width_raw = resolve_geometry_width_context(state)
    width = float(width_raw or 0.0)
    depth = float(_target_band_float(state, "D", 600.0))
    lig_legs = _target_band_int(state, "lig_legs", 0)
    lig_diameter = max(_target_band_int(state, "lig_d", 0), 1)
    lig_spacing = max(_target_band_float(state, "s_lig", 200.0), 1.0)
    shear_density = (lig_legs * lig_diameter**2) / lig_spacing
    return {
        "bottom_state": bottom_state,
        "width": float(width),
        "depth": float(depth),
        "ast_top": float(_target_band_float(state, "Ast_top", 0.0)),
        "bar_count": int(bottom_projection.get("bar_count", 0) or 0),
        "row_count": int(bottom_projection.get("row_count", 0) or 0),
        "reo_congestion_index": float(
            bottom_projection.get("reo_congestion_index", 0.0) or 0.0
        ),
        "shear_density": float(shear_density),
        "bottom_updates": dict(bottom_projection.get("bottom_updates") or {}),
    }


def build_fast_candidate_evaluation_runner_metadata_projection(
    *,
    cached_candidate: dict[str, Any] | None,
    candidate_state: dict[str, Any] | None,
    updates: dict[str, Any] | None,
    source: str,
    label: str | None = None,
    action_type: str | None = None,
    seed_width: int | float | None = None,
    seed_depth: int | float | None = None,
    seed_ast_bot: int | float | None = None,
    reo_complexity: int | float | None = None,
) -> dict[str, Any]:
    """Stamp pure runner metadata onto an evaluated fast candidate."""

    candidate = dict(cached_candidate or {})
    source_text = str(source or "")
    candidate["source"] = source_text
    candidate["label"] = label or candidate.get("label") or source_text.replace("_", " ").title()
    candidate["action_type"] = action_type
    candidate["state"] = dict(candidate_state or {})
    candidate["updates"] = dict(updates or {})
    candidate["_seed_width"] = float(seed_width or 0.0)
    candidate["_seed_depth"] = float(seed_depth or 0.0)
    candidate["_seed_ast_bot"] = float(seed_ast_bot or 0.0)
    candidate["reo_complexity"] = float(
        candidate.get("reo_complexity", reo_complexity if reo_complexity is not None else 0.0)
        or 0.0
    )
    return candidate


def resolve_candidate_state_shared_updates(
    seed_state: dict[str, Any] | None,
    candidate_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return shared update fields changed between seed and candidate state."""

    seed = dict(seed_state or {})
    candidate = dict(candidate_state or {})
    tracked_keys = (
        "b",
        "bw",
        "tw",
        "D",
        "fc",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
    )
    updates: dict[str, Any] = {}
    for key in tracked_keys:
        if seed.get(key) != candidate.get(key):
            updates[key] = candidate.get(key)
    return updates


def resolve_fast_candidate_evaluation_cache_cap_decision(
    *,
    local_cached_available: bool,
    global_cached_available: bool,
    use_global_cache: bool,
    unique_eval_count: int,
    max_unique_evals: int,
) -> dict[str, Any]:
    """Resolve the pure cache/cap branch for the fast candidate runner."""

    if bool(local_cached_available):
        return {
            "decision": "use_local_cache",
            "use_local_cached": True,
            "use_global_cached": False,
            "should_evaluate": False,
            "cap_hit": False,
            "metrics_delta": {"cache_hits": 1},
        }
    if bool(use_global_cache) and bool(global_cached_available):
        return {
            "decision": "use_global_cache",
            "use_local_cached": False,
            "use_global_cached": True,
            "should_evaluate": False,
            "cap_hit": False,
            "metrics_delta": {"cache_hits": 1, "global_cache_hits": 1},
        }
    if int(unique_eval_count or 0) >= int(max_unique_evals or 0):
        return {
            "decision": "cap_hit",
            "use_local_cached": False,
            "use_global_cached": False,
            "should_evaluate": False,
            "cap_hit": True,
            "metrics_delta": {},
        }
    return {
        "decision": "evaluate",
        "use_local_cached": False,
        "use_global_cached": False,
        "should_evaluate": True,
        "cap_hit": False,
        "metrics_delta": {"unique_eval_count": 1},
    }


__all__ = [
    "BeamCandidateEvaluation",
    "BeamCandidateInput",
    "BeamCandidateUpdate",
    "build_fast_candidate_evaluation_result_projection",
    "build_full_candidate_evaluation_result_projection",
    "build_full_candidate_evaluation_overview_status_projection",
    "build_fast_candidate_evaluation_overview_status_projection",
    "build_fast_candidate_evaluation_bending_summary_pack_projection",
    "build_fast_candidate_evaluation_shear_detail_state_projection",
    "build_fast_candidate_evaluation_scalar_status_projection",
    "build_fast_candidate_evaluation_physical_metric_projection",
    "build_candidate_action_state_projection",
    "build_fast_candidate_evaluation_runner_metadata_projection",
    "resolve_candidate_state_shared_updates",
    "resolve_candidate_shear_updates",
    "resolve_fast_candidate_evaluation_cache_cap_decision",
    "build_bending_only_target_band_cleanup_update_trials",
    "build_bottom_reo_candidate_metric_projection",
    "build_bottom_reo_recommendation_arrangement_candidate_inputs",
    "build_direct_target_band_broad_bottom_trial_attempts",
    "build_direct_target_band_broad_geometry_plan",
    "build_direct_target_band_broad_shear_options",
    "build_direct_target_band_ladder_stage_update_attempts",
    "build_probe_equivalent_bending_cleanup_candidate_inputs",
    "build_zero_bending_demand_cleanup_update_trials",
    "select_bending_only_best_safe_partial_cleanup_candidate",
    "select_bending_only_target_band_cleanup_candidate",
    "build_probe_equivalent_bending_evaluated_candidate_row",
    "build_zero_bending_demand_evaluated_candidate_row",
    "select_probe_equivalent_bending_cleanup_candidate",
    "select_zero_bending_demand_cleanup_candidate",
    "build_active_fail_executor_candidate_generation_context",
    "build_active_fail_executor_candidate_eval_precheck_projection",
    "build_active_fail_executor_candidate_eval_attempt_result",
    "apply_active_fail_executor_candidate_eval_loop_attempt_result",
    "resolve_active_fail_executor_candidate_eval_cache_lookup",
    "build_candidate_state_hash",
    "generate_bottom_reo_target_band_candidate_states",
    "prepare_bottom_reo_recommendation_candidates_for_selection",
    "resolve_bottom_reo_candidate_bottom_updates",
    "evaluate_active_fail_executor_candidate_with_updates",
    "evaluate_bottom_reo_recommendation_arrangement_candidate",
    "project_active_fail_executor_evaluated_candidate_result",
    "resolve_active_fail_executor_candidate_eval_source",
    "evaluate_bending_only_target_band_candidate_with_updates",
    "evaluate_direct_target_band_candidate_with_updates",
    "evaluate_design_candidate_with_updates",
    "evaluate_probe_equivalent_bending_candidate_with_updates",
    "evaluate_shear_low_util_candidate_with_updates",
    "evaluate_zero_bending_demand_candidate_with_updates",
    "filter_auto_design_candidates_by_row_layout",
    "apply_auto_design_winner_metadata_projection",
    "resolve_auto_design_band_reacher_delta_metrics",
    "resolve_auto_design_band_reaching_candidate_goal_score",
    "resolve_auto_design_candidate_target_band_metrics",
    "resolve_auto_design_candidate_violation_score",
    "resolve_minimum_longitudinal_bar_rule",
    "resolve_auto_design_band_reacher_ranked_pool",
    "resolve_auto_design_shallower_beam_metrics",
    "resolve_auto_design_shallower_beam_selection_key",
    "resolve_auto_design_shear_candidate_practicality_metrics",
    "resolve_auto_design_winner_pool_decision",
    "score_auto_design_candidates_for_selection",
    "resolve_design_candidate_overview_for_safety_check",
    "stable_candidate_evaluation_hash",
]
