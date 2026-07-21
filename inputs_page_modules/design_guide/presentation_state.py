"""Design Guide presentation-state coordination for the Inputs page."""

from __future__ import annotations

from typing import Any


_PRESENTATION_STATE_DEPENDENCIES: tuple[str, ...] = (
    "DESIGN_GUIDE_INTENTS",
    "EFFICIENCY_TARGET_UTIL_MIN",
    "GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD",
    "TARGET_BAND_EPS",
    "st",
    "_derive_design_guide_guidance_intent",
    "_design_guide_display_truth_for_item",
    "_design_mode_config",
    "_design_optimisation_goal",
    "_guidance_governing_primary_action",
    "_is_in_target_zone_with_eps",
    "_current_design_guide_fail_fingerprint",
    "_design_guide_fail_fingerprints_equivalent",
    "_one_click_feedback_cta_state",
    "_recommendation_blocked_reason",
    "_recommendation_commit_eligible",
    "_recommendation_updates_for_envelope",
    "_ONE_CLICK_CTA_BLOCKING_REASONS",
    "is_unnecessarily_overdesigned",
    "resolve_design_guide_decision",
    "target_band_payload",
)


def bind_presentation_state_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _PRESENTATION_STATE_DEPENDENCIES
            if name in namespace
        }
    )


def _latest_solver_result_cta_state(overview: dict | None) -> dict:
    """
    Presentation-layer guard based on the latest one-click solver result.

    This is intentionally separate from `_one_click_run_feedback` so a blocked solver result
    cannot be visually overwritten by a freshly rebuilt guidance card in the next render.
    """
    result = st.session_state.get("_solver_result")
    if not isinstance(result, dict):
        return {
            "status": "",
            "reason": "",
            "matches_current_state": False,
            "current_fail_fingerprint": {},
            "result_fail_fingerprint": {},
        }

    status = str(result.get("status") or st.session_state.get("auto_design_status") or "").strip()
    stop_reason = str(result.get("stop_reason") or "").strip()
    envelope = dict(result.get("recommendation_envelope") or {})
    blocked_reason = str(envelope.get("blocked_reason") or stop_reason or "").strip()
    commit_eligible = bool(envelope.get("commit_eligible"))

    if commit_eligible:
        return {
            "status": status,
            "reason": blocked_reason,
            "matches_current_state": False,
            "current_fail_fingerprint": {},
            "result_fail_fingerprint": {},
        }

    if blocked_reason not in _ONE_CLICK_CTA_BLOCKING_REASONS and status not in {
        "blocked",
        "no_action",
        "no_actionable_full_coverage_candidate",
        "rejected",
    }:
        return {
            "status": status,
            "reason": blocked_reason,
            "matches_current_state": False,
            "current_fail_fingerprint": {},
            "result_fail_fingerprint": {},
        }

    result_dbg = dict(result.get("one_click_solver_debug") or {})
    result_fp = dict(result_dbg.get("current_fail_fingerprint") or {})
    current_fp = _current_design_guide_fail_fingerprint(overview)
    fingerprints_match = bool(
        result_fp
        and (
            result_fp == current_fp
            or _design_guide_fail_fingerprints_equivalent(result_fp, current_fp)
        )
    )

    return {
        "status": status,
        "reason": blocked_reason,
        "matches_current_state": bool(fingerprints_match),
        "current_fail_fingerprint": dict(current_fp),
        "result_fail_fingerprint": dict(result_fp),
    }


def _build_design_guide_presentation_state(
    *,
    primary_item: dict | None,
    overview: dict | None,
    efficiency_state: dict | None,
    disp_state: dict,
    mode_config: dict | None,
    recommendation_result: dict | None = None,
    pending_recommendation: dict | None = None,
) -> dict:
    """
    Design Guide presentation contract (product rules - do not regress without explicit review).

    - fail beats everything
    - warn / near-limit beats healthy (including utilisation at the upper guidance threshold while
      checks still PASS)
    - healthy means:
        all_key_pass
        no fail
        no warn
        in target band
        not unnecessarily overdesigned
    - efficiency means safe but materially overdesigned
    - the primary recommendation is rendered in one card only (callers must not duplicate titles /
      change lines outside this surface)
    - this function controls card and apply button theme (css_bucket, use_success_style); it does
      not change recommendation semantics or apply payloads

    Evaluation order: fail -> warn -> healthy -> efficiency -> info.
    """
    _ = recommendation_result
    ov = overview if isinstance(overview, dict) else {}
    es = efficiency_state if isinstance(efficiency_state, dict) else {}
    mode_cfg = (
        mode_config
        if isinstance(mode_config, dict)
        else _design_mode_config(_design_optimisation_goal(disp_state))
    )
    governing_action, _primary_utils = _guidance_governing_primary_action(ov)

    headline = str((primary_item or {}).get("title_main") or "").strip() or "Design guidance"
    pending = pending_recommendation if isinstance(pending_recommendation, dict) else {}
    pending_commit_eligible = _recommendation_commit_eligible(pending) if pending else False
    pending_blocked_reason = _recommendation_blocked_reason(pending) if pending else None
    feedback_cta_state = _one_click_feedback_cta_state(ov, clear_stale=True)
    feedback_blocks_primary_cta = bool(feedback_cta_state.get("matches_current_state"))
    feedback_blocked_reason = str(feedback_cta_state.get("reason") or "").strip() or None
    solver_result_cta_state = _latest_solver_result_cta_state(ov)
    solver_result_blocks_primary_cta = bool(solver_result_cta_state.get("matches_current_state"))
    solver_result_blocked_reason = str(solver_result_cta_state.get("reason") or "").strip() or None
    button_label = (
        "Apply Auto Design"
        if str(pending.get("_source") or "").strip() == "auto_design"
        else "Apply Recommendation"
    )
    primary_item_has_actionable_updates = bool(_recommendation_updates_for_envelope(primary_item))

    try:
        worst = float(ov.get("worst_util", 0.0) or 0.0)
    except (TypeError, ValueError):
        worst = 0.0

    any_fail = bool(ov.get("any_fail"))
    any_warn = bool(ov.get("any_warn"))
    all_key_pass = bool(ov.get("all_key_pass"))
    overdesigned = is_unnecessarily_overdesigned(ov, es, recommendation_result=recommendation_result)
    in_target_band = _is_in_target_zone_with_eps(ov, mode_cfg, eps=TARGET_BAND_EPS)
    near_limit_util = bool(all_key_pass and worst >= float(GUIDANCE_NEAR_LIMIT_UTIL_THRESHOLD))
    classification_es = str(es.get("classification") or "").strip()
    terminal_optimal = (
        classification_es == "optimal"
        or str((primary_item or {}).get("design_guide_terminal_state") or "") == "optimal"
    )
    terminal_very_low_demand = (
        classification_es == "very_low_demand"
        or str((primary_item or {}).get("design_guide_terminal_state") or "") == "very_low_demand"
    ) and not bool(primary_item_has_actionable_updates)
    guidance_intent = str((primary_item or {}).get("guidance_intent") or "").strip()
    if guidance_intent not in DESIGN_GUIDE_INTENTS and isinstance(primary_item, dict):
        try:
            guidance_intent = _derive_design_guide_guidance_intent(
                primary_item,
                state=disp_state,
                overview=ov,
                efficiency_state=es,
            )
        except Exception:
            guidance_intent = "advisory_warning"
    primary_truth = dict((primary_item or {}).get("display_truth") or {})
    if not primary_truth and isinstance(primary_item, dict):
        primary_truth = _design_guide_display_truth_for_item(
            primary_item,
            state=disp_state,
            overview=ov,
            mode_config=mode_cfg,
        )
    primary_truth_source = str(primary_truth.get("display_truth_source") or "").strip()
    primary_truth_in_target = bool(primary_truth.get("displayed_within_target_band"))
    passive_underband_threshold = max(
        float(mode_cfg.get("target_lo", EFFICIENCY_TARGET_UTIL_MIN)),
        float(EFFICIENCY_TARGET_UTIL_MIN),
    )
    passive_underband_no_action = bool(
        all_key_pass
        and not any_fail
        and not any_warn
        and worst < float(passive_underband_threshold) - float(TARGET_BAND_EPS)
        and not bool(primary_item_has_actionable_updates)
        and not bool(pending_commit_eligible)
    )

    primary_button_contract = dict((primary_item or {}).get("button_contract") or {})
    primary_candidate_search_evidence = dict(
        (primary_item or {}).get("candidate_search_evidence")
        or ((primary_item or {}).get("action_payload") or {}).get("candidate_search_evidence")
        or ((primary_item or {}).get("resolved_candidate") or {}).get("candidate_search_evidence")
        or {}
    )
    engine_decision = resolve_design_guide_decision(
        current_state=dict(disp_state),
        summary=dict(ov),
        raw_items=[dict(primary_item or {})] if isinstance(primary_item, dict) and primary_item else [],
        candidate_evidence=dict(primary_candidate_search_evidence),
        # Transitional candidate preparation only. Final Design Guide decision,
        # target-band winner selection, and outside-target allowance are owned by
        # design_guidance_engine.resolve_design_guide_decision.
        raw_candidates=[dict(primary_item or {})] if isinstance(primary_item, dict) and primary_item else [],
        target_band=target_band_payload(_design_optimisation_goal(disp_state)),
        context={
            "goal": _design_optimisation_goal(disp_state),
            "headline": headline,
            "governing_action": governing_action,
            "pending": bool(pending),
            "pending_commit_eligible": bool(pending_commit_eligible),
            "pending_blocked_reason": pending_blocked_reason,
            "feedback_blocks_primary_cta": bool(feedback_blocks_primary_cta),
            "feedback_blocked_reason": feedback_blocked_reason,
            "solver_result_blocks_primary_cta": bool(solver_result_blocks_primary_cta),
            "solver_result_blocked_reason": solver_result_blocked_reason,
            "button_label": button_label,
            "primary_item_has_actionable_updates": bool(primary_item_has_actionable_updates),
            "worst": worst,
            "any_fail": bool(any_fail),
            "any_warn": bool(any_warn),
            "all_key_pass": bool(all_key_pass),
            "overdesigned": bool(overdesigned),
            "in_target_band": bool(in_target_band),
            "near_limit_util": bool(near_limit_util),
            "terminal_optimal": bool(terminal_optimal),
            "terminal_very_low_demand": bool(terminal_very_low_demand),
            "guidance_intent": guidance_intent,
            "passive_underband_no_action": bool(passive_underband_no_action),
            "candidate_search_evidence": dict(primary_candidate_search_evidence),
            "efficiency_state": dict(es),
        },
    )
    try:
        st.session_state["_design_guide_engine_decision"] = dict(engine_decision)
    except Exception:
        pass
    return dict(engine_decision.get("presentation") or {})
