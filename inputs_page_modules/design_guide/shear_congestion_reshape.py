"""In-target shear congestion reshape coordination for the Inputs page Design Guide."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable


_SHEAR_CONGESTION_RESHAPE_DEPENDENCIES: tuple[str, ...] = (
    "_build_candidate_search_evidence",
    "_candidate_is_materially_actionable",
    "_design_optimisation_goal",
    "_distance_to_target_band",
    "_effective_bottom_design_state",
    "_evaluate_auto_design_candidate",
    "_float_from_state",
    "_geometry_lock_enabled",
    "_guidance_change_lines_for_updates",
    "_guidance_item_from_resolved_candidate",
    "_guidance_state_snapshot",
    "_int_from_state",
    "_parse_util_value",
    "_resolve_geometry_width_context",
    "_resolved_efficiency_target_band",
    "_single_row_bottom_reo_updates",
    "_updates_match_state",
    "math",
)


@dataclass(frozen=True)
class ShearCongestionReshapeRuntime:
    build_candidate_search_evidence: Callable[..., Any]
    candidate_is_materially_actionable: Callable[..., Any]
    design_optimisation_goal: Callable[..., Any]
    distance_to_target_band: Callable[..., Any]
    effective_bottom_design_state: Callable[..., Any]
    evaluate_auto_design_candidate: Callable[..., Any]
    float_from_state: Callable[..., Any]
    geometry_lock_enabled: Callable[..., Any]
    guidance_change_lines_for_updates: Callable[..., Any]
    guidance_item_from_resolved_candidate: Callable[..., Any]
    guidance_state_snapshot: Callable[..., Any]
    int_from_state: Callable[..., Any]
    parse_util_value: Callable[..., Any]
    resolve_geometry_width_context: Callable[..., Any]
    resolved_efficiency_target_band: Callable[..., Any]
    single_row_bottom_reo_updates: Callable[..., Any]
    updates_match_state: Callable[..., Any]


def _bind_shear_congestion_reshape_runtime(
    runtime: ShearCongestionReshapeRuntime,
) -> None:
    globals().update(
        {
            f"_{field.name}": getattr(runtime, field.name)
            for field in runtime.__dataclass_fields__.values()
        }
    )


def bind_shear_congestion_reshape_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _SHEAR_CONGESTION_RESHAPE_DEPENDENCIES
            if name in namespace
        }
    )


def _in_target_shear_congestion_reshape_guidance_item(
    state: dict,
    overview: dict | None,
    mode_config: dict,
    *,
    debug_sink: dict | None = None,
    runtime: ShearCongestionReshapeRuntime | None = None,
) -> dict | None:
    if runtime is not None:
        _bind_shear_congestion_reshape_runtime(runtime)
    """Offer a buildability reshape when bending is efficient but shear links are congested."""
    base = _guidance_state_snapshot(dict(state or {}))
    ov = dict(overview or {})
    if not base or bool(ov.get("any_fail")):
        return None
    t_lo, t_hi, _ = _resolved_efficiency_target_band(mode_config, goal=_design_optimisation_goal(base))
    gov_util = _parse_util_value(ov.get("governing_util"))
    if gov_util is None:
        gov_util = _parse_util_value(ov.get("worst_util"))
    if gov_util is None or not (float(t_lo) <= float(gov_util) <= float(t_hi)):
        return None
    if _geometry_lock_enabled(base):
        if isinstance(debug_sink, dict):
            debug_sink["in_target_shear_congestion_reshape_reason"] = "geometry_locked"
        return None

    utils = dict(ov.get("utils") or {})
    shear_util = _parse_util_value(utils.get("shear"))
    bending_util = _parse_util_value(utils.get("bending"))
    current_spacing = _float_from_state(base, "s_lig", 0.0)
    current_dia = int(_float_from_state(base, "lig_d", 0.0) or 0)
    current_legs = int(_float_from_state(base, "lig_legs", 0.0) or 0)
    if (
        shear_util is None
        or bending_util is None
        or current_spacing <= 0.0
        or current_spacing > 100.0
        or float(shear_util) >= 0.55
        or current_dia <= 0
        or current_legs <= 0
    ):
        if isinstance(debug_sink, dict):
            debug_sink["in_target_shear_congestion_reshape_reason"] = "shear_not_congested_or_not_low_util"
        return None

    width_key, _, base_width = _resolve_geometry_width_context(base)
    base_width = float(base_width or 0.0)
    base_depth = float(_float_from_state(base, "D", 0.0) or 0.0)
    if base_width <= 0.0 or base_depth <= 0.0:
        return None
    bottom_state = _effective_bottom_design_state(base)
    current_ast = float(bottom_state.get("Ast_bot", 0.0) or 0.0)
    explicit_row_ast = 0.0
    try:
        explicit_row_ast += (
            float(_int_from_state(base, "bot_row_1_bars", _int_from_state(base, "bot1_count", 0)))
            * math.pi
            * float(_float_from_state(base, "bot_row_1_dia", _float_from_state(base, "db_bot_1", 0.0))) ** 2
            / 4.0
        )
        explicit_row_ast += (
            float(_int_from_state(base, "bot_row_2_bars", _int_from_state(base, "bot2_count", 0)))
            * math.pi
            * float(_float_from_state(base, "bot_row_2_dia", _float_from_state(base, "db_bot_2", 0.0))) ** 2
            / 4.0
        )
    except Exception:
        explicit_row_ast = 0.0
    if explicit_row_ast > current_ast + 1e-6:
        current_ast = explicit_row_ast
    if current_ast <= 0.0:
        return None

    candidates: list[dict] = []
    seen_updates: set[tuple] = set()
    width_values = [
        base_width + step
        for step in (50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0, 250.0)
    ]
    depth_values = [
        base_depth - step
        for step in (50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0)
    ]
    spacing_values = [
        spacing
        for spacing in (125.0, 150.0, 175.0, 200.0, 225.0, 250.0, 275.0, 300.0)
        if spacing > current_spacing + 1e-9
    ]
    bottom_trials: list[tuple[int, int, float]] = []
    for count in range(3, 9):
        for dia in (16, 20, 24, 28, 32):
            ast = float(count) * math.pi * float(dia) ** 2 / 4.0
            if current_ast * 1.02 <= ast <= current_ast * 1.75:
                bottom_trials.append((count, dia, ast))
    bottom_trials.sort(key=lambda item: (abs(item[2] - current_ast * 1.15), item[0], item[1]))

    def _evaluate_updates(updates: dict, label: str) -> None:
        u = dict(updates or {})
        if not u or _updates_match_state(base, u):
            return
        if not _candidate_is_materially_actionable(base, u):
            return
        sig = tuple(sorted((str(k), str(v)) for k, v in u.items()))
        if sig in seen_updates:
            return
        seen_updates.add(sig)
        try:
            cand = _evaluate_auto_design_candidate(
                base,
                updates=u,
                source="in_target_shear_congestion_reshape",
                label=label,
                action_type="apply_resolved_candidate",
            )
        except Exception:
            cand = None
        if not isinstance(cand, dict):
            return
        cand_ov = dict(cand.get("overview") or {})
        try:
            preview_worst = float(cand_ov.get("worst_util"))
        except (TypeError, ValueError):
            preview_worst = None
        if preview_worst is None or not math.isfinite(preview_worst):
            return
        no_preview_fail = not bool(cand_ov.get("any_fail"))
        cand["is_compliant"] = bool(no_preview_fail)
        cand["preview_pass"] = bool(no_preview_fail)
        cand["candidate_post_util"] = preview_worst
        cand["worst_util"] = preview_worst
        cand["candidate_distance_to_target_band"] = _distance_to_target_band(preview_worst, float(t_lo), float(t_hi))
        cand["candidate_reaches_target_band"] = bool(float(t_lo) <= preview_worst <= float(t_hi))
        cand["updates"] = dict(u)
        cand["action_type"] = "apply_resolved_candidate"
        cand["guidance_change_lines"] = _guidance_change_lines_for_updates(base, u)
        cand["subfamilies"] = ["geometry", "bottom_reo", "shear"]
        cand["recommendation_family_tag"] = "compound"
        cand["label"] = "Reduce shear congestion with a wider, shorter section"
        cand["canonical_winner_label"] = cand["label"]
        cand["title_locked_from_final_winner"] = True
        cand["design_guide_refinement_priority"] = "shear_congestion_reshape"
        cand["allow_in_target_primary_action"] = True
        candidates.append(cand)

    for width in width_values:
        if width < 250.0:
            continue
        for depth in depth_values:
            if depth < 350.0 or depth >= base_depth - 1e-9:
                continue
            geom_updates: dict[str, object] = {width_key: float(width), "D": float(depth)}
            if width_key != "b":
                geom_updates["b"] = float(width)
            for count, dia, _ast in bottom_trials[:28]:
                bottom_updates = _single_row_bottom_reo_updates(count, dia)
                for spacing in spacing_values:
                    updates = dict(geom_updates)
                    updates.update(bottom_updates)
                    updates.update({"lig_d": int(current_dia), "lig_legs": int(current_legs), "s_lig": float(spacing)})
                    _evaluate_updates(updates, "Reduce shear congestion with a wider, shorter section")

    safe = [
        cand
        for cand in candidates
        if not bool((cand.get("overview") or {}).get("any_fail"))
        and cand.get("candidate_post_util") is not None
    ]
    target = [
        cand
        for cand in safe
        if bool(cand.get("candidate_reaches_target_band"))
    ]
    if not target:
        if isinstance(debug_sink, dict):
            debug_sink["in_target_shear_congestion_reshape_reason"] = "no_safe_target_band_reshape"
            debug_sink["in_target_shear_congestion_reshape_candidate_count"] = len(candidates)
        return None

    target_mid = (float(t_lo) + float(t_hi)) / 2.0

    def _reshape_score(cand: dict) -> tuple:
        u = dict(cand.get("updates") or {})
        width_after = float(u.get(width_key, u.get("b", base_width)) or base_width)
        depth_after = float(u.get("D", base_depth) or base_depth)
        spacing_after = float(u.get("s_lig", current_spacing) or current_spacing)
        ast_after = float(_effective_bottom_design_state({**base, **u}).get("Ast_bot", current_ast) or current_ast)
        util_after = float(cand.get("candidate_post_util") or 0.0)
        return (
            -float(spacing_after - current_spacing),
            -float(base_depth - depth_after),
            abs(float(width_after - base_width) - 75.0),
            abs(float(ast_after / max(current_ast, 1.0)) - 1.15),
            abs(util_after - target_mid),
            len(u),
        )

    selected = min(target, key=_reshape_score)
    evidence = _build_candidate_search_evidence(
        selected_candidate=selected,
        all_candidates=candidates,
        target_low=float(t_lo),
        target_high=float(t_hi),
        exhaustive=True,
        search_scope="in_target_shear_congestion_reshape",
        selected_title=str(selected.get("label") or ""),
    )
    selected["candidate_search_evidence"] = dict(evidence)
    selected["candidate_id"] = evidence.get("selected_candidate_id")
    selected["source_candidate_id"] = evidence.get("selected_candidate_id")
    reasoning = (
        "Current bending utilisation is inside the target band, but the shear links are congested. "
        "This reshape widens and shortens the section, adds practical bottom reinforcement, and opens "
        "the link spacing while keeping all checks compliant."
    )
    item = _guidance_item_from_resolved_candidate(
        selected,
        state=base,
        overview=ov,
        title=str(selected.get("label") or "Reduce shear congestion with a wider, shorter section"),
        reasoning=reasoning,
        status="EFFICIENCY",
        primary_action="Apply recommendation",
    )
    item["guidance_intent"] = "efficiency_tightening"
    item["design_guide_refinement_priority"] = "shear_congestion_reshape"
    item["allow_in_target_primary_action"] = True
    item["candidate_search_evidence"] = dict(evidence)
    item["display_truth"] = {
        "display_truth_source": "candidate_preview",
        "displayed_util": selected.get("candidate_post_util"),
        "displayed_status": "PASS",
        "target_low": float(t_lo),
        "target_high": float(t_hi),
        "displayed_within_target_band": True,
        "source_summary_util": float(gov_util),
        "source_candidate_util": selected.get("candidate_post_util"),
        "source_post_commit_util": None,
    }
    item["guidance_alternatives_text_compact"] = (
        "Alternative: keep the current efficient section if the tight shear-link spacing is acceptable for construction."
    )
    payload = dict(item.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["source_candidate_id"] = evidence.get("selected_candidate_id")
    payload["guidance_alternatives_text_compact"] = item["guidance_alternatives_text_compact"]
    item["action_payload"] = payload
    resolved = dict(item.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["candidate_id"] = evidence.get("selected_candidate_id")
    resolved["source_candidate_id"] = evidence.get("selected_candidate_id")
    resolved["design_guide_refinement_priority"] = "shear_congestion_reshape"
    resolved["allow_in_target_primary_action"] = True
    item["resolved_candidate"] = resolved
    if isinstance(debug_sink, dict):
        debug_sink["in_target_shear_congestion_reshape_reason"] = "selected"
        debug_sink["in_target_shear_congestion_reshape_candidate_count"] = len(candidates)
        debug_sink["in_target_shear_congestion_reshape_selected_updates"] = dict(selected.get("updates") or {})
        debug_sink["candidate_search_evidence"] = dict(evidence)
    return item


__all__ = [
    "bind_shear_congestion_reshape_dependencies",
    "_in_target_shear_congestion_reshape_guidance_item",
]
