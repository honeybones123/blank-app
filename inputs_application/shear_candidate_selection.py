"""Application-owned ranking and diversification for shear recommendation seeds."""

from __future__ import annotations

from inputs_application.candidate_identity import make_auto_design_candidate_key
from inputs_application.recommendation_primitives import shear_candidate_type
from inputs_application.recommendation_support import (
    resolve_geometry_width_context,
    severe_shear_failure,
)
from inputs_application.state_utils import float_from_state
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
    TARGET_BAND_EPS,
)


def _distance_to_target_band(
    util: float,
    target_min: float,
    target_max: float,
) -> float:
    try:
        value = float(util)
        low = float(target_min)
        high = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if low <= value <= high:
        return 0.0
    return low - value if value < low else value - high


def shear_recommendation_rank_key(
    candidate: dict,
    *,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
) -> tuple:
    resolved = dict(candidate or {})
    overview = dict(resolved.get("overview") or {})
    utils = dict(overview.get("utils") or {})
    updates = dict(resolved.get("updates") or {})
    try:
        shear_util = float(utils.get("shear"))
    except Exception:
        shear_util = None
    if shear_util is None:
        try:
            shear_util = float(resolved.get("candidate_post_util"))
        except Exception:
            shear_util = None
    try:
        seed_util = (
            float(seed_shear_util) if seed_shear_util is not None else None
        )
    except Exception:
        seed_util = None
    target_distance = (
        _distance_to_target_band(
            float(shear_util),
            EFFICIENCY_TARGET_UTIL_MIN,
            EFFICIENCY_TARGET_UTIL_MAX,
        )
        if shear_util is not None
        else 999.0
    )
    improves_shear = bool(
        seed_util is not None
        and shear_util is not None
        and shear_util < seed_util - 1e-9
    )
    reaches_band = bool(
        resolved.get("candidate_reaches_target_band")
        or resolved.get("reaches_target_band")
        or target_distance <= TARGET_BAND_EPS
    )
    compliant = bool(
        resolved.get("is_compliant")
        or resolved.get("preview_pass")
        or resolved.get("all_key_pass")
    )
    candidate_type = str(
        resolved.get("shear_candidate_type")
        or shear_candidate_type(
            dict(base_state or {}),
            dict(resolved.get("state") or {}),
        )
        or ""
    ).strip().lower()
    type_rank = {
        "combined": 0 if severe_shear_failure(seed_util) else 3,
        "spacing": 1,
        "diameter": 2,
        "legs": 2,
        "geometry": 3,
        "no_shear_design_cleanup": 4,
    }.get(candidate_type, 5)
    try:
        score = float(resolved.get("score"))
    except Exception:
        score = 0.0
    update_complexity = len(
        [
            key
            for key, value in updates.items()
            if dict(base_state or {}).get(key) != value
        ]
    )
    severity_rank = (
        0
        if str(severity_band or "").strip().lower() in {"severe", "critical"}
        else 1
    )
    return (
        0 if compliant else 1,
        0 if improves_shear else 1,
        0 if reaches_band else 1,
        severity_rank,
        type_rank,
        float(target_distance),
        -float(score),
        int(update_complexity),
        str(resolved.get("label") or ""),
    )


def shear_family_label(
    candidate_type: str,
    candidate: dict | None,
    *,
    seed_candidate: dict | None = None,
) -> str:
    mapping = {
        "spacing": "spacing tighter",
        "more legs": "more legs",
        "larger dia": "larger link dia",
        "width increase": "width increase",
        "depth increase": "depth increase",
        "combined": "combined geometry + stronger shear",
    }
    kind = str(candidate_type or "")
    label = mapping.get(kind, kind or "spacing tighter")
    if candidate and seed_candidate:
        candidate_state = dict(candidate.get("state") or {})
        seed_state = dict(seed_candidate.get("state") or {})
        candidate_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
        seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
        width_key, _, seed_width = resolve_geometry_width_context(seed_state)
        candidate_width = float_from_state(
            candidate_state,
            width_key,
            seed_width,
        )
        seed_depth = float_from_state(seed_state, "D", 0.0)
        candidate_depth = float_from_state(
            candidate_state,
            "D",
            seed_depth,
        )
        geometry_changed = (
            abs(candidate_width - seed_width) > 1e-9
            or abs(candidate_depth - seed_depth) > 1e-9
        )
        if candidate_ast < seed_ast - 1e-6 and geometry_changed:
            return "combined geometry + lighter bottom reo"
        if kind == "combined" and candidate_ast < seed_ast - 1e-6:
            return "combined shear + lighter bottom reo"
    return label


def combined_shear_seed_candidates(
    candidates: list[dict],
    *,
    seed_candidate: dict,
    base_state: dict,
    severity_band: str,
    seed_shear_util: float | None,
    limit: int = 8,
) -> list[dict]:
    if not candidates:
        return []
    ranked = sorted(
        candidates,
        key=lambda item: shear_recommendation_rank_key(
            item,
            base_state=base_state,
            severity_band=severity_band,
            seed_shear_util=seed_shear_util,
        ),
    )
    selected: dict[str, dict] = {}
    for candidate in ranked:
        family = shear_family_label(
            str(
                candidate.get("shear_candidate_type")
                or shear_candidate_type(
                    base_state,
                    dict(candidate.get("state") or {}),
                )
            ),
            candidate,
            seed_candidate=seed_candidate,
        )
        if family not in selected:
            selected[family] = candidate
    ordered: list[dict] = []
    seen: set[tuple] = set()
    for candidate in list(selected.values()) + ranked[: max(2, limit // 2)]:
        candidate_key = make_auto_design_candidate_key(
            dict(candidate.get("state") or {})
        )
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        ordered.append(candidate)
        if len(ordered) >= limit:
            break
    return ordered


__all__ = [
    "combined_shear_seed_candidates",
    "shear_family_label",
    "shear_recommendation_rank_key",
]
