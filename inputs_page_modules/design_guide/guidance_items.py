"""Owned construction of terminal and general Design Guide guidance items."""

from __future__ import annotations

from inputs_application.geometry_search_policy import (
    design_optimisation_goal as _design_optimisation_goal,
)
from inputs_application.recommendation_support import resolve_geometry_width_context
from inputs_application.state_utils import uls_action_from_state
from design_brain.config import DESIGN_OPTIMISATION_GOAL_LABELS
from inputs_application.policy_constants import (
    EFFICIENCY_TARGET_UTIL_MAX,
    EFFICIENCY_TARGET_UTIL_MIN,
)
def _guidance_bucket(status: str, util: float | None = None) -> str:
    upper = str(status or "—").upper()
    if "START" in upper:
        return "start"
    if "EFFICIENCY" in upper or "TIGHTEN" in upper:
        return "efficiency"
    if "FAIL" in upper or upper == "NG":
        return "fail"
    if "WARN" in upper or "NEAR LIMIT" in upper or upper == "CHECK":
        return "warn"
    if util is not None and util > 1.0:
        return "fail"
    if util is not None and util >= 0.9:
        return "warn"
    return "pass"


def _guidance_priority(bucket: str, util: float | None) -> float:
    util_score = util if util is not None else 0.0
    if bucket == "start":
        return 50.0
    if bucket == "fail":
        return 300.0 + util_score
    if bucket == "warn":
        return 200.0 + util_score
    if bucket == "efficiency":
        return 150.0 + util_score
    return 100.0 - util_score


def _format_guidance_title(title: str, util: float | None) -> str:
    if util is None:
        return title
    return f"{title} (utilisation = {util:.2f})"


def _guidance_item(
    check_key: str,
    title: str,
    primary_action: str,
    secondary_action: str | None,
    reasoning: str,
    levers: str,
    action_type: str | None,
    action_payload: dict | None,
    *,
    status: str,
    util: float | None,
    guidance_before_after: str | None = None,
    guidance_change_lines: list[str] | None = None,
    guidance_why: str | None = None,
) -> dict:
    bucket = _guidance_bucket(status, util)
    out: dict = {
        "check_key": check_key,
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": _format_guidance_title(title, util),
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "reasoning": reasoning,
        "levers": levers,
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": _guidance_priority(bucket, util),
        "action_type": action_type,
        "action_payload": action_payload or {},
    }
    if guidance_before_after:
        out["guidance_before_after"] = guidance_before_after
    if guidance_change_lines:
        out["guidance_change_lines"] = [
            str(line)
            for line in guidance_change_lines
            if str(line).strip()
        ]
    if guidance_why:
        out["guidance_why"] = str(guidance_why)
    return out


def _design_optimisation_goal_label(state: dict | None = None) -> str:
    goal = _design_optimisation_goal(state or {})
    return DESIGN_OPTIMISATION_GOAL_LABELS[goal]


def _optimal_terminal_family_id(state: dict) -> str:
    exact_stop_signal = bool(
        state.get("exact_stop_proven")
        or state.get("exact_stop_available")
        or state.get("exact_stop_proof")
    )
    if exact_stop_signal:
        return "EXACT_STOP_PROVEN"
    return "TARGET_BAND_REACHED"


def _float_from_state(state: dict, key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _int_from_state(state: dict, key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _fast_start_here_content(state: dict) -> tuple[str, str]:
    _, _, width = resolve_geometry_width_context(state)
    depth = _float_from_state(state, "D", 0.0)
    span = _float_from_state(state, "L", 0.0)
    has_geometry = any(value > 0.0 for value in (width, depth, span))

    action_values = [
        abs(uls_action_from_state(state, "M")),
        abs(uls_action_from_state(state, "V")),
        abs(uls_action_from_state(state, "N")),
        abs(uls_action_from_state(state, "T")),
    ]
    has_actions = max(action_values, default=0.0) > 1e-9

    has_bottom_reo = (
        (
            _int_from_state(state, "bot1_count", 0) > 0
            or _int_from_state(state, "bot_row_1_bars", 0) > 0
            or _int_from_state(state, "nb_bot", 0) > 0
        )
        and (
            _float_from_state(state, "db_bot_1", 0.0) > 0.0
            or _float_from_state(state, "bot_row_1_dia", 0.0) > 0.0
            or _float_from_state(state, "db_bot", 0.0) > 0.0
        )
    )
    has_shear_reo = (
        _int_from_state(state, "lig_legs", 0) > 0
        and _float_from_state(state, "lig_d", 0.0) > 0.0
        and _float_from_state(state, "s_lig", 0.0) > 0.0
    )
    is_continue = has_geometry or has_actions or has_bottom_reo or has_shear_reo
    return (
        "CONTINUE" if is_continue else "START",
        "Add reinforcement or loads to activate checks"
        if is_continue
        else "Start by setting geometry or reinforcement",
    )


def _guidance_not_started(state: dict, overview: dict) -> bool:
    _, _, width = resolve_geometry_width_context(state)
    depth = _float_from_state(state, "D", 0.0)
    span = _float_from_state(state, "L", 0.0)
    required_inputs_missing = width <= 0.0 or depth <= 0.0 or span <= 0.0

    bending_util = overview["utils"].get("bending")
    shear_util = overview["utils"].get("shear")
    no_key_results = all(
        util is None or util <= 0.0
        for util in (bending_util, shear_util)
    )
    if required_inputs_missing or no_key_results:
        return True

    action_values = [
        abs(uls_action_from_state(state, "M")),
        abs(uls_action_from_state(state, "V")),
        abs(uls_action_from_state(state, "N")),
        abs(uls_action_from_state(state, "T")),
    ]
    no_actions = max(action_values, default=0.0) <= 1e-9

    no_bottom_reo = (
        _float_from_state(state, "Ast_bot", 0.0) <= 0.0
        or _int_from_state(state, "nb_bot", 0) <= 0
        or _float_from_state(
            state,
            "db_bot",
            _float_from_state(state, "db_bot_1", 20.0),
        )
        <= 0.0
    )
    no_shear_reo = (
        _int_from_state(state, "lig_legs", 0) <= 0
        or _float_from_state(state, "lig_d", 0.0) <= 0.0
        or _float_from_state(state, "s_lig", 0.0) <= 0.0
    )
    return no_actions and (no_bottom_reo or no_shear_reo)


def _guidance_start_item(state: dict) -> dict:
    _, start_line = _fast_start_here_content(state)
    item = _guidance_item(
        "general",
        "Choose your workflow:",
        start_line,
        None,
        "Or define loads from the Design page",
        "Key levers: geometry, actions, initial reinforcement",
        None,
        None,
        status="START",
        util=None,
    )
    item["start_steps"] = [
        "Fast -> guided design",
        "Detailed -> full control",
    ]
    return item


def _auto_design_solver_recommendation_as_guidance_item(
    solver_rec: dict,
) -> dict | None:
    """Map an auto-design result into the shared guidance-item contract."""
    if not isinstance(solver_rec, dict):
        return None
    meta = dict(solver_rec.get("meta") or {})
    if str(meta.get("status") or "").strip() == "no_action":
        return None
    updates = dict(solver_rec.get("updates") or {})
    if not updates:
        return None
    title = str(solver_rec.get("title") or "Auto Design Solution").strip()
    description = str(solver_rec.get("description") or "").strip()
    util_raw = meta.get("util")
    try:
        util = float(util_raw) if util_raw is not None else None
    except Exception:
        util = None
    resolved_candidate = (
        solver_rec.get("resolved_candidate")
        if isinstance(solver_rec.get("resolved_candidate"), dict)
        else {}
    )
    resolved_updates = dict(resolved_candidate.get("updates") or updates)
    payload = {
        "updates": dict(updates),
        "resolved_candidate_updates": dict(
            solver_rec.get("resolved_candidate_updates") or resolved_updates
        ),
        "resolved_candidate_label": str(
            solver_rec.get("resolved_candidate_label")
            or resolved_candidate.get("label")
            or title
        ),
        "resolved_candidate_action_type": str(
            solver_rec.get("resolved_candidate_action_type")
            or resolved_candidate.get("action_type")
            or "apply_compound_guidance"
        ).strip(),
    }
    return _guidance_item(
        "auto_design_engine",
        title,
        description or title,
        None,
        description,
        "Auto-design solver",
        "apply_compound_guidance",
        payload,
        status="FAIL",
        util=util,
    )


def _guidance_item_is_resolved_one_click(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    raw_payload = item.get("action_payload")
    payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
    return bool(
        (
            str(item.get("action_type") or "") == "apply_resolved_candidate"
            or bool(payload.get("resolved_candidate_updates"))
        )
        and payload.get("resolved_candidate_updates")
        and payload.get("resolved_candidate_reaches_target_band") is not None
    )


def _passing_guidance_item(state: dict, overview: dict) -> dict:
    return _guidance_item(
        "general",
        "Design has workable reserve",
        "Review the optimisation goal before changing geometry or reinforcement.",
        "Optional refinements should be checked against the governing utilisation target.",
        (
            f"Why: the current beam satisfies the published checks for "
            f"{_design_optimisation_goal_label(state).lower()} with worst utilisation {overview['worst_util']:.2f}."
        ),
        "Key levers: depth D, reinforcement, load path",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )


def _optimal_guidance_item(state: dict, overview: dict) -> dict:
    terminal_family_id = _optimal_terminal_family_id(state)
    terminal_reason = (
        "exact_stop_proven"
        if terminal_family_id == "EXACT_STOP_PROVEN"
        else "target_band_reached"
    )
    item = _guidance_item(
        terminal_family_id,
        "Design is efficient - further reductions would weaken capacity",
        "The current section is within the target utilisation range.",
        "The current design is the best practical balance found, not just safe enough.",
        (
            "Why: the solver did not find a smaller practical option that stayed inside the target "
            f"range ({EFFICIENCY_TARGET_UTIL_MIN:.2f}-{EFFICIENCY_TARGET_UTIL_MAX:.2f}). Further reduction "
            "would lower bending reserve, shear reserve, or stiffness."
        ),
        "Key levers: optimisation preference, geometry, reinforcement",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )
    item["design_guide_terminal_state"] = "optimal"
    item.update(
        {
            "family": terminal_family_id,
            "selected_family": terminal_family_id,
            "selected_family_id": terminal_family_id,
            "published_family_id": terminal_family_id,
            "cta_family_id": terminal_family_id,
            "apply_payload_family_id": terminal_family_id,
            "candidate_family_id": terminal_family_id,
            "card_family_id": terminal_family_id,
            "matched_family_ids": [terminal_family_id],
            "display_state": "PASS",
            "critical_status": "PASS",
            "tone": "pass",
            "pill": "PASS",
            "final_state_class": "pass",
            "guidance_intent": "terminal_no_action",
            "primary_card_actionable": False,
            "family_match_passed": True,
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": terminal_family_id,
                "selected_family_id": terminal_family_id,
                "published_family_id": terminal_family_id,
                "cta_family_id": terminal_family_id,
                "apply_payload_family_id": terminal_family_id,
                "action_type": None,
                "updates": {},
                "preview_pass": True,
                "blocking_reason": None,
                "disabled_reason": None,
            },
            "candidate_search_evidence": {
                "source": "optimal_terminal_guidance_item",
                "selected_family_id": terminal_family_id,
                "published_family_id": terminal_family_id,
                "cta_family_id": terminal_family_id,
                "family_match_passed": True,
                "target_band_terminal_signal": terminal_family_id == "TARGET_BAND_REACHED",
                "exact_stop_proven": terminal_family_id == "EXACT_STOP_PROVEN",
                "selection_reason": terminal_reason,
                "updates": {},
            },
            "selection_evidence": {
                "source": "optimal_terminal_guidance_item",
                "selected_family_id": terminal_family_id,
                "matched_family_ids": [terminal_family_id],
                "family_match_passed": True,
                "selection_reason": terminal_reason,
            },
            "final_publication_verifier_payload": {
                "selected_family": terminal_family_id,
                "selected_family_id": terminal_family_id,
                "published_family_id": terminal_family_id,
                "cta_family_id": terminal_family_id,
                "apply_payload_family_id": terminal_family_id,
                "candidate_family_id": terminal_family_id,
                "card_family_id": terminal_family_id,
                "matched_family_ids": [terminal_family_id],
                "family_match_passed": True,
                "outcome_state": "PASS",
                "status": "PASS",
                "display_state": "PASS",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": terminal_family_id,
                    "selected_family_id": terminal_family_id,
                    "action_type": None,
                    "updates": {},
                    "preview_pass": True,
                    "blocking_reason": None,
                },
                "selection_reason": terminal_reason,
            },
        }
    )
    if terminal_family_id == "EXACT_STOP_PROVEN":
        item["exact_stop_proven"] = True
        if isinstance(state.get("exact_stop_proof"), dict):
            item["exact_stop_proof"] = dict(state.get("exact_stop_proof") or {})
    return item


def _very_low_demand_guidance_item(state: dict, overview: dict) -> dict:
    item = _guidance_item(
        "general",
        "Design demand is very low",
        "No optimisation recommendation",
        "Optional: adjust actions or geometry only if you intend a different design intent.",
        (
            f"Why: worst utilisation is {overview['worst_util']:.2f} with all checks passing — demand is "
            "too small for meaningful efficiency tightening guidance."
        ),
        "Key levers: actions, geometry, reinforcement (optional exploration only)",
        None,
        None,
        status="PASS",
        util=overview["worst_util"],
    )
    item["design_guide_terminal_state"] = "very_low_demand"
    return item


__all__ = [
    "_guidance_bucket",
    "_auto_design_solver_recommendation_as_guidance_item",
    "_guidance_item",
    "_guidance_item_is_resolved_one_click",
    "_guidance_not_started",
    "_guidance_start_item",
    "_optimal_guidance_item",
    "_passing_guidance_item",
    "_very_low_demand_guidance_item",
]
