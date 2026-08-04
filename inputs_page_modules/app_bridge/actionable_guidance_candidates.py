"""Actionable Design Guide candidate collection for one-click app-bridge flows."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable


_ACTIONABLE_GUIDANCE_CANDIDATE_DEPENDENCIES: tuple[str, ...] = (
    "TARGET_BAND_ACTIONABLE_AST_DELTA_MM2",
    "TARGET_BAND_ACTIONABLE_GEO_DELTA_MM",
    "_append_design_guide_trace",
    "_compute_design_guidance_items",
    "_design_width_value",
    "_ensure_guidance_item_resolved_candidate_payload",
    "_float_from_state",
    "_guidance_action_updates",
    "_resolve_geometry_width_context",
    "_updates_match_state",
)


@dataclass(frozen=True)
class CandidateActionabilityRuntime:
    target_band_actionable_ast_delta_mm2: float
    target_band_actionable_geo_delta_mm: float
    design_width_value: Callable[..., Any]
    float_from_state: Callable[..., Any]
    resolve_geometry_width_context: Callable[..., Any]
    updates_match_state: Callable[..., Any]


@dataclass(frozen=True)
class ActionableGuidanceCollectionRuntime:
    append_design_guide_trace: Callable[..., Any]
    compute_design_guidance_items: Callable[..., dict]
    ensure_guidance_item_resolved_candidate_payload: Callable[..., Any]
    guidance_action_updates: Callable[..., dict | None]


def bind_actionable_guidance_candidate_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _ACTIONABLE_GUIDANCE_CANDIDATE_DEPENDENCIES
            if name in namespace
        }
    )


def _candidate_is_materially_actionable(
    state: dict,
    updates: dict | None,
    *,
    delta_b_mm: float | None = None,
    delta_D_mm: float | None = None,
    delta_Ast_bot: float | None = None,
    guidance_change_lines: list | None = None,
    runtime: CandidateActionabilityRuntime | None = None,
) -> bool:
    if runtime is not None:
        target_ast_delta = runtime.target_band_actionable_ast_delta_mm2
        target_geo_delta = runtime.target_band_actionable_geo_delta_mm
        design_width_value = runtime.design_width_value
        float_from_state = runtime.float_from_state
        resolve_geometry_width_context = runtime.resolve_geometry_width_context
        updates_match_state = runtime.updates_match_state
    else:
        target_ast_delta = TARGET_BAND_ACTIONABLE_AST_DELTA_MM2
        target_geo_delta = TARGET_BAND_ACTIONABLE_GEO_DELTA_MM
        design_width_value = _design_width_value
        float_from_state = _float_from_state
        resolve_geometry_width_context = _resolve_geometry_width_context
        updates_match_state = _updates_match_state

    if guidance_change_lines and any(str(x).strip() for x in guidance_change_lines):
        return True
    u = dict(updates or {})
    if not u or updates_match_state(state, u):
        return False
    try:
        if delta_b_mm is not None and abs(float(delta_b_mm)) > target_geo_delta:
            return True
        if delta_D_mm is not None and abs(float(delta_D_mm)) > target_geo_delta:
            return True
        if delta_Ast_bot is not None and abs(float(delta_Ast_bot)) > target_ast_delta:
            return True
    except (TypeError, ValueError):
        pass
    material_keys = (
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "bot_row_count",
        "bot1_layout_mode",
        "bot2_layout_mode",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "lig_d",
        "lig_legs",
        "s_lig",
    )
    if any(k in u for k in material_keys):
        return True
    wkey, _, _ = resolve_geometry_width_context(state)
    if wkey in u:
        try:
            cur = float(state.get(wkey) or 0.0)
            nu = float(u[wkey])
            if abs(cur - nu) > target_geo_delta:
                return True
        except (TypeError, ValueError):
            return True
    if "D" in u:
        try:
            d0 = float(float_from_state(state, "D", 0.0) or 0.0)
            d1 = float(u["D"])
            if abs(d0 - d1) > target_geo_delta:
                return True
        except (TypeError, ValueError):
            return True
    if "b" in u and wkey != "b":
        try:
            cur = float(design_width_value(state) or 0.0)
            nu = float(u["b"])
            if abs(cur - nu) > target_geo_delta:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _one_click_collect_actionable_guidance_candidates(
    working_state: dict,
    *,
    debug_enabled: bool,
    trace_run_id: str | None = None,
    trace_step: int | None = None,
    runtime: ActionableGuidanceCollectionRuntime | None = None,
) -> tuple[list[dict], int]:
    compute_items = (
        runtime.compute_design_guidance_items
        if runtime is not None
        else _compute_design_guidance_items
    )
    append_trace = (
        runtime.append_design_guide_trace
        if runtime is not None
        else _append_design_guide_trace
    )
    ensure_payload = (
        runtime.ensure_guidance_item_resolved_candidate_payload
        if runtime is not None
        else _ensure_guidance_item_resolved_candidate_payload
    )
    action_updates = (
        runtime.guidance_action_updates
        if runtime is not None
        else _guidance_action_updates
    )
    payload = compute_items(
        working_state,
        guidance_debug_verbose=False,
        debug_enabled=debug_enabled,
        request_kind="design_guide",
    )
    raw_items = list(payload.get("guidance_items") or [])
    if trace_run_id:
        dbg_tr = dict(payload.get("debug_trace") or {})
        gsum = dbg_tr.get("guidance_items_summary")
        if not isinstance(gsum, list):
            gsum = [
                {
                    "action_type": (it or {}).get("action_type"),
                    "title_main": (it or {}).get("title_main"),
                }
                for it in (raw_items[:16] if isinstance(raw_items, list) else [])
                if isinstance(it, dict)
            ]
        append_trace(
            "guidance_pool",
            {
                "step": trace_step,
                "guidance_branch": dbg_tr.get("guidance_branch"),
                "guidance_items_summary": gsum,
                "selected_action_type": dbg_tr.get("selected_action_type"),
                "selected_title": dbg_tr.get("selected_title"),
                "one_click_convergence_available": dbg_tr.get("one_click_convergence_available"),
                "one_click_convergence_reason": dbg_tr.get("one_click_convergence_reason"),
                "actionable_target_band_winner_exists": dbg_tr.get("actionable_target_band_winner_exists"),
                "raw_guidance_item_count": len(raw_items or []),
            },
            run_id=trace_run_id,
            source="one_click_guidance",
        )
    out: list[dict] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        action_type = str(item.get("action_type") or "").strip()
        if not action_type:
            continue
        work = copy.deepcopy(item)
        ensure_payload(work, state=working_state)
        pl = dict(work.get("action_payload") or {})
        updates: dict | None = None
        try:
            resolved = action_updates(action_type, pl, state=working_state)
            if isinstance(resolved, dict) and resolved:
                updates = dict(resolved)
        except Exception:
            updates = None
        if not updates:
            try:
                resolved2 = action_updates(action_type, work, state=working_state)
                if isinstance(resolved2, dict) and resolved2:
                    updates = dict(resolved2)
            except Exception:
                updates = None
        if not updates:
            continue
        title_main = str(work.get("title_main") or work.get("canonical_winner_label") or action_type).strip()
        out.append(
            {
                "item": work,
                "action_type": action_type,
                "title": title_main,
                "raw_updates": updates,
            },
        )
    return out, len(raw_items)


__all__ = [
    "CandidateActionabilityRuntime",
    "ActionableGuidanceCollectionRuntime",
    "bind_actionable_guidance_candidate_dependencies",
    "_candidate_is_materially_actionable",
    "_one_click_collect_actionable_guidance_candidates",
]
