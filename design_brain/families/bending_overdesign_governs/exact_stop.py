from __future__ import annotations

from typing import Any, Callable

from design_brain.bending_overdesign_candidate_evaluation import (
    stable_bending_overdesign_candidate_hash,
)
from design_brain.families.bending_overdesign_governs.contract import geometry_rules


BendingPackEvaluator = Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any] | None]
BottomUpdateResolver = Callable[[dict[str, Any]], dict[str, Any] | None]
PayloadHasher = Callable[[dict[str, Any]], str]


def _parse_util_value(value: Any) -> float | None:
    if value in (None, "", "-", "—"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _int_from_state(state: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(state.get(key, default) or default)
    except Exception:
        return int(default)


def _merge_state(state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(state or {})
    merged.update(dict(updates or {}))
    return merged


def _ductility_governs_overview(overview: dict[str, Any] | None) -> bool:
    rows = (((overview or {}).get("packs") or {}).get("bending") or {}).get("rows") or []
    ductility_row = next((row for row in rows if str(row.get("title") or "") == "Ductility limit"), None)
    flexural_row = next((row for row in rows if str(row.get("title") or "") == "Flexural strength capacity"), None)
    ductility_util = _parse_util_value((ductility_row or {}).get("util"))
    flexural_util = _parse_util_value((flexural_row or {}).get("util"))
    if ductility_util is None:
        return False
    candidates = [value for value in (ductility_util, flexural_util) if value is not None]
    return bool(candidates) and ductility_util >= max(candidates) - 1e-6 and ductility_util >= 0.85


def _default_hash_payload(payload: dict[str, Any]) -> str:
    return stable_bending_overdesign_candidate_hash(payload)


def build_bending_cleanup_exact_stop_contract_proof(
    *,
    base_state: dict[str, Any],
    overview: dict[str, Any] | None,
    width_key: str,
    current_width: float,
    current_depth: float,
    min_width: float,
    min_depth: float,
    geometry_locked: bool,
    update_trials: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    selected_updates: dict[str, Any] | None,
    exhaustive: bool,
    target_band_candidate_count: int,
    evaluate_bending_with_bottom_state: BendingPackEvaluator,
    candidate_bottom_updates: BottomUpdateResolver,
    hash_payload: PayloadHasher | None = None,
) -> dict[str, Any]:
    """Build the family-owned proof that bending cleanup exact-stop followed contract order."""

    base = dict(base_state or {})
    make_hash = hash_payload or _default_hash_payload
    width_aliases = {str(width_key or "b"), "b", "bw"}
    bottom_keys = {
        "bot_row_count",
        "bot_row_1_bars",
        "bot_row_1_dia",
        "bot_row_2_bars",
        "bot_row_2_dia",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "nb_bot",
        "bot_entry",
    }

    def _update_fingerprint(updates: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((str(key), repr(value)) for key, value in dict(updates or {}).items()))

    def _layer_restart_trial(updates: dict[str, Any] | None) -> bool:
        update_map = dict(updates or {})
        row2_before = max(
            0,
            _int_from_state(base, "bot_row_2_bars", _int_from_state(base, "bot2_count", 0)),
        )
        if row2_before <= 0:
            return bool(update_map.get("bot_row_count") == 1 and update_map.get("bot2_count", 0) == 0)
        row2_after = int(update_map.get("bot_row_2_bars", update_map.get("bot2_count", row2_before)) or 0)
        row_count_after = int(update_map.get("bot_row_count", 2 if row2_before > 0 else 1) or 1)
        return row2_after == 0 or row_count_after == 1

    candidate_lookup = {
        _update_fingerprint(dict(candidate.get("updates") or {})): dict(candidate)
        for candidate in list(candidates or [])
        if isinstance(candidate, dict)
    }

    bottom_only_indexes: list[int] = []
    geometry_indexes: list[int] = []
    width_trial_count = 0
    depth_trial_count = 0
    width_restart_bottom_count = 0
    depth_restart_bottom_count = 0
    width_restart_layer_count = 0
    depth_restart_layer_count = 0

    selected_state = _merge_state(base, dict(selected_updates or {}))
    selected_pack = evaluate_bending_with_bottom_state(
        selected_state,
        candidate_bottom_updates(selected_state),
    ) or {}
    selected_ast = _parse_util_value(selected_pack.get("Ast_bot"))
    selected_as_min = _parse_util_value(selected_pack.get("As_min"))
    lighter_trials: list[dict[str, Any]] = []

    for index, updates in enumerate(list(update_trials or []), start=1):
        update_map = dict(updates or {})
        update_keys = set(update_map)
        width_changed = any(key in update_keys for key in width_aliases) and any(
            key in update_map and abs(float(update_map.get(key) or current_width) - float(current_width)) > 1e-9
            for key in width_aliases
            if key in update_map
        )
        depth_changed = "D" in update_map and abs(float(update_map.get("D") or current_depth) - float(current_depth)) > 1e-9
        geometry_trial = bool(width_changed or depth_changed)
        bottom_trial = bool(update_keys & bottom_keys)
        layer_trial = _layer_restart_trial(update_map)

        if bottom_trial and not geometry_trial:
            bottom_only_indexes.append(index)
        if geometry_trial:
            geometry_indexes.append(index)
        if width_changed:
            width_trial_count += 1
            if bottom_trial:
                width_restart_bottom_count += 1
            if layer_trial:
                width_restart_layer_count += 1
        if depth_changed:
            depth_trial_count += 1
            if bottom_trial:
                depth_restart_bottom_count += 1
            if layer_trial:
                depth_restart_layer_count += 1

        if selected_ast is None:
            continue
        trial_state = _merge_state(base, update_map)
        trial_pack = evaluate_bending_with_bottom_state(
            trial_state,
            candidate_bottom_updates(trial_state),
        ) or {}
        trial_ast = _parse_util_value(trial_pack.get("Ast_bot"))
        trial_as_min = _parse_util_value(trial_pack.get("As_min"))
        if trial_ast is None or trial_ast >= float(selected_ast) - 1e-6:
            continue
        trial_candidate = dict(candidate_lookup.get(_update_fingerprint(update_map)) or {})
        lighter_trials.append(
            {
                "update_hash": make_hash(update_map),
                "trial_ast": trial_ast,
                "trial_as_min": trial_as_min,
                "below_or_at_as_min": bool(
                    trial_as_min is not None and trial_ast <= float(trial_as_min) + 1e-6
                ),
                "preview_pass": bool(trial_candidate.get("is_compliant")),
                "failed_check_family": trial_candidate.get("overview", {}).get("governing_check")
                if isinstance(trial_candidate.get("overview"), dict)
                else None,
            }
        )

    width_relief_required = (not bool(geometry_locked)) and float(current_width) > float(min_width) + 1e-9
    depth_relief_required = (not bool(geometry_locked)) and float(current_depth) > float(min_depth) + 1e-9
    geometry_policy = geometry_rules()
    width_step_mm = abs(int(geometry_policy.get("width_increment_mm") or -25))
    depth_step_mm = abs(int(geometry_policy.get("depth_increment_mm") or -25))

    observed_width_relief_values = sorted(
        {
            float(dict(updates or {}).get(width_key))
            for updates in list(update_trials or [])
            if width_key in dict(updates or {})
            and abs(float(dict(updates or {}).get(width_key) or current_width) - float(current_width)) > 1e-9
            and float(dict(updates or {}).get(width_key) or current_width) < float(current_width) - 1e-9
        }
    )
    observed_depth_relief_values = sorted(
        {
            float(dict(updates or {}).get("D"))
            for updates in list(update_trials or [])
            if "D" in dict(updates or {})
            and abs(float(dict(updates or {}).get("D") or current_depth) - float(current_depth)) > 1e-9
            and float(dict(updates or {}).get("D") or current_depth) < float(current_depth) - 1e-9
        }
    )

    def _expected_progressive_values(current: float, minimum: float, step_mm: int) -> list[float]:
        if step_mm <= 0:
            return []
        values: list[float] = []
        value = float(current) - float(step_mm)
        while value >= float(minimum) - 1e-9:
            values.append(round(float(value), 6))
            value -= float(step_mm)
        return values

    expected_width_relief_values = (
        _expected_progressive_values(float(current_width), float(min_width), int(width_step_mm))
        if width_relief_required
        else []
    )
    expected_depth_relief_values = (
        _expected_progressive_values(float(current_depth), float(min_depth), int(depth_step_mm))
        if depth_relief_required
        else []
    )
    width_progressive_relief_exhausted_to_contract_bounds = (
        (not width_relief_required)
        or all(
            any(abs(float(observed) - float(expected)) <= 1e-6 for observed in observed_width_relief_values)
            for expected in expected_width_relief_values
        )
    )
    depth_progressive_relief_exhausted_to_contract_bounds = (
        (not depth_relief_required)
        or all(
            any(abs(float(observed) - float(expected)) <= 1e-6 for observed in observed_depth_relief_values)
            for expected in expected_depth_relief_values
        )
    )
    reo_attempted_first = bool(bottom_only_indexes) and (
        not geometry_indexes or min(bottom_only_indexes) < min(geometry_indexes)
    )
    lighter_trials_blocked_only_by_as_min = bool(lighter_trials) and all(
        bool(row.get("below_or_at_as_min")) for row in lighter_trials
    )
    every_valid_cleanup_path_exhausted = bool(exhaustive) and int(target_band_candidate_count or 0) <= 0
    exact_stop_cleanup_proof_chain_complete = bool(
        every_valid_cleanup_path_exhausted
        and reo_attempted_first
        and (not width_relief_required or width_trial_count > 0)
        and (not depth_relief_required or depth_trial_count > 0)
        and (not width_relief_required or width_restart_bottom_count > 0)
        and (not depth_relief_required or depth_restart_bottom_count > 0)
        and (not width_relief_required or width_restart_layer_count > 0 or _int_from_state(base, "bot2_count", 0) <= 0)
        and (not depth_relief_required or depth_restart_layer_count > 0 or _int_from_state(base, "bot2_count", 0) <= 0)
        and bool(width_progressive_relief_exhausted_to_contract_bounds)
        and bool(depth_progressive_relief_exhausted_to_contract_bounds)
    )
    ductility_governs_cleanup = bool(_ductility_governs_overview(overview))
    minimum_bending_reinforcement_governs = bool(
        selected_ast is not None
        and selected_as_min is not None
        and lighter_trials_blocked_only_by_as_min
        and exact_stop_cleanup_proof_chain_complete
    )
    return {
        "reo_reduction_attempted_first_for_ductility": bool(reo_attempted_first),
        "ductility_governs_cleanup": bool(ductility_governs_cleanup),
        "minimum_bending_reinforcement_governs": bool(minimum_bending_reinforcement_governs),
        "ast_min_governs": bool(minimum_bending_reinforcement_governs),
        "selected_candidate_ast": selected_ast,
        "selected_candidate_as_min": selected_as_min,
        "width_reduction_as_min_relief_required": bool(width_relief_required),
        "depth_reduction_as_min_relief_required": bool(depth_relief_required),
        "width_reduction_as_min_relief_checked": bool(width_trial_count > 0),
        "depth_reduction_as_min_relief_checked": bool(depth_trial_count > 0),
        "width_reduction_progressive_relief_exhausted_to_contract_bounds": bool(
            width_progressive_relief_exhausted_to_contract_bounds
        ),
        "depth_reduction_progressive_relief_exhausted_to_contract_bounds": bool(
            depth_progressive_relief_exhausted_to_contract_bounds
        ),
        "progressive_geometry_relief_exhausted_to_contract_bounds": bool(
            width_progressive_relief_exhausted_to_contract_bounds
            and depth_progressive_relief_exhausted_to_contract_bounds
        ),
        "width_reduction_progressive_relief_expected_values": list(expected_width_relief_values),
        "depth_reduction_progressive_relief_expected_values": list(expected_depth_relief_values),
        "width_reduction_progressive_relief_observed_values": list(observed_width_relief_values),
        "depth_reduction_progressive_relief_observed_values": list(observed_depth_relief_values),
        "width_reduction_restarted_reinforcement_candidate_count": int(width_restart_bottom_count),
        "depth_reduction_restarted_reinforcement_candidate_count": int(depth_restart_bottom_count),
        "width_reduction_restarted_layer_candidate_count": int(width_restart_layer_count),
        "depth_reduction_restarted_layer_candidate_count": int(depth_restart_layer_count),
        "bottom_reo_layer_search_restarted_after_geometry_relief": bool(
            (not width_relief_required or width_restart_bottom_count > 0)
            and (not depth_relief_required or depth_restart_bottom_count > 0)
        ),
        "layer_search_restarted_after_geometry_relief": bool(
            (not width_relief_required or width_restart_layer_count > 0 or _int_from_state(base, "bot2_count", 0) <= 0)
            and (not depth_relief_required or depth_restart_layer_count > 0 or _int_from_state(base, "bot2_count", 0) <= 0)
        ),
        "every_valid_cleanup_path_exhausted_for_contract_defined_reasons": bool(every_valid_cleanup_path_exhausted),
        "exact_stop_cleanup_proof_chain_complete": bool(exact_stop_cleanup_proof_chain_complete),
        "lighter_trial_count_below_selected_ast": len(lighter_trials),
        "lighter_trials_blocked_only_by_as_min": bool(lighter_trials_blocked_only_by_as_min),
        "lighter_trials": list(lighter_trials[:20]),
    }


__all__ = [
    "build_bending_cleanup_exact_stop_contract_proof",
]
